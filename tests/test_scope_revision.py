from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dianxun.context_bus import ContextVersionConflict
from dianxun.domain import PolicyEngine
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, DEFAULT_SEED_PATH, MCPService
from dianxun.runtime import RuntimePrincipal, RuntimeService
from dianxun.runtime_context import RuntimeContextBus
from dianxun.state import StateStore


class ScopeRevisionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = self.initialize_store(Path(tmp.name) / "revision.db")
        self.human = RuntimePrincipal("Human", "human", "demo", "S03")
        self.orchestrator = RuntimePrincipal("Orchestrator", "orch", "demo", "S03")
        self.runtime = RuntimeService(
            MCPService(self.store, PolicyEngine(DEFAULT_POLICY_PATH)),
            [self.human, self.orchestrator],
        )
        for ident in ("I", "J"):
            self.runtime.call(
                "runtime_open", {"incident_id": ident, "device_id": "FROST-S03"}, self.orchestrator
            )
        self.store.migrate_scope_v2()
        self.parent = self.store.list_batches(batch_ids=["BATCH-S03-DAIRY-001"])[0]
        self.bus = RuntimeContextBus(self.store, "demo")

    def initialize_store(self, path):
        store = StateStore(path)
        store.initialize_from_file(DEFAULT_SEED_PATH)
        return store

    def inject_audit_failure(self):
        with self.store.transaction() as conn:
            conn.execute("""CREATE TRIGGER reject_scope_audit BEFORE INSERT ON audit_log
                BEGIN SELECT RAISE(ABORT, 'injected audit failure'); END""")
        return sqlite3.IntegrityError

    def request(self, **overrides):
        return {
            "incident_id": "I",
            "expected_versions": {
                ident: {
                    "scope_version": 1,
                    "context_version": self.bus.get(ident, allow_expired=True).version,
                }
                for ident in ("I", "J")
            },
            "change_id": "receipt-1",
            "source_ref": "synthetic:wms-1",
            "changes": [
                {
                    "op": "split",
                    "batch_id": self.parent["batch_id"],
                    "children": [
                        {"batch_id": "C1", "quantity": 1},
                        {"batch_id": "C2", "quantity": self.parent["quantity"] - 1},
                    ],
                }
            ],
            **overrides,
        }

    def revise(self, request, principal=None):
        return self.runtime.call("runtime_revise_scope", request, principal or self.human)

    def test_split_updates_every_open_incident_and_replay_does_not_repeat(self):
        request = self.request()
        result = self.revise(request)
        replay = self.revise(request)
        self.assertEqual(result["versions"], replay["versions"])
        self.assertTrue(replay["historical_replay"])
        parent = self.store.list_batches(batch_ids=[self.parent["batch_id"]])[0]
        self.assertEqual((0, "retired"), (parent["quantity"], parent["lifecycle"]))
        self.assertEqual(
            self.parent["quantity"],
            sum(r["quantity"] for r in self.store.list_batches(batch_ids=["C1", "C2"])),
        )
        for ident in ("I", "J"):
            case = self.store.get_incident(ident)
            self.assertEqual(2, case["scope_version"])
            self.assertNotIn(parent["batch_id"], case["affected_batches"])
            self.assertIn("C1", case["affected_batches"])
            context = self.bus.get(ident, allow_expired=True)
            self.assertEqual(1, context.recovery["generation"])
            self.assertEqual(["C1", "C2"], context.recovery["scope_containment_required"])
        with self.store.read_snapshot() as conn:
            self.assertEqual(
                2, conn.execute("SELECT COUNT(*) AS n FROM batch_lineage").fetchone()["n"]
            )
            self.assertEqual(
                2,
                conn.execute(
                    "SELECT COUNT(*) AS n FROM scope_revisions WHERE change_id='receipt-1'"
                ).fetchone()["n"],
            )

    def test_wrong_actor_conflict_and_missing_related_version_leave_inventory_untouched(self):
        request = self.request()
        before = self.store.snapshot_digest()
        with self.assertRaises(PermissionError):
            self.revise(request, self.orchestrator)
        request["expected_versions"]["J"]["scope_version"] = 999
        with self.assertRaises(ContextVersionConflict):
            self.revise(request)
        del request["expected_versions"]["J"]
        with self.assertRaises(ValueError):
            self.revise(request)
        self.assertEqual(before, self.store.snapshot_digest())
        self.assertEqual(1, self.store.get_incident("I")["scope_version"])

    def test_audit_failure_rolls_back_inventory_lineage_and_contexts(self):
        before = self.store.snapshot_digest()
        contexts = {i: self.bus.get(i, allow_expired=True).snapshot() for i in ("I", "J")}
        error = self.inject_audit_failure()
        with self.assertRaises(error):
            self.revise(self.request())
        self.assertEqual(before, self.store.snapshot_digest())
        for ident in contexts:
            self.assertEqual(contexts[ident], self.bus.get(ident, allow_expired=True).snapshot())
        with self.store.read_snapshot() as conn:
            self.assertEqual(
                0, conn.execute("SELECT COUNT(*) AS n FROM batch_lineage").fetchone()["n"]
            )

    def test_reused_change_id_with_different_payload_is_rejected(self):
        request = self.request()
        self.revise(request)
        request["source_ref"] = "synthetic:different"
        with self.assertRaises(ValueError):
            self.revise(request)

    def test_concurrent_identical_splits_only_apply_once(self):
        request = self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.revise(request), range(2)))
        self.assertEqual([False, True], sorted(r["historical_replay"] for r in results))
        self.assertEqual(2, self.store.get_incident("I")["scope_version"])

    def test_move_keeps_responsibility_and_rejects_foreign_device(self):
        before = self.store.snapshot_digest()
        with self.assertRaises(ValueError):
            self.revise(
                self.request(
                    changes=[
                        {
                            "op": "move",
                            "batch_id": self.parent["batch_id"],
                            "device_id": "FROST-S04",
                        }
                    ]
                )
            )
        self.assertEqual(before, self.store.snapshot_digest())
        with self.store.transaction() as conn:
            conn.execute("""INSERT INTO devices SELECT 'D2',store_id,model,health_state,
                door_state,power_state,compressor_state,ambient_temp_c,updated_at
                FROM devices WHERE device_id='FROST-S03'""")
        self.revise(
            self.request(
                changes=[{"op": "move", "batch_id": self.parent["batch_id"], "device_id": "D2"}]
            )
        )
        for ident in ("I", "J"):
            case = self.store.get_incident(ident)
            self.assertIn(self.parent["batch_id"], case["affected_batches"])
            batches = {r["batch_id"]: r for r in case["scope_snapshot"]["batches"]}
            self.assertEqual("D2", batches[self.parent["batch_id"]]["device_id"])

    def test_add_updates_all_incidents_on_anchor_without_claiming_sales_hold(self):
        batch = {
            k: self.parent[k]
            for k in (
                "sku_id",
                "product_name",
                "device_id",
                "storage_min_c",
                "storage_max_c",
                "policy_ref",
            )
        }
        batch.update(batch_id="NEW", quantity=3)
        self.revise(self.request(changes=[{"op": "add", "batch": batch}]))
        for ident in ("I", "J"):
            self.assertIn("NEW", self.store.get_incident(ident)["affected_batches"])
            self.assertEqual(
                ["NEW"],
                self.bus.get(ident, allow_expired=True).recovery["scope_containment_required"],
            )
            self.assertEqual([], self.store.list_sales_holds(incident_id=ident))
