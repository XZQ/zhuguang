from __future__ import annotations

import http.client
import json
import os
import shutil
import sqlite3
import unittest
from contextlib import nullcontext
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dianxun import trace
from dianxun.context_bus import TaskContext
from dianxun.replay import write_json
from dianxun.runtime_replay import (
    capture_runtime,
    check_restored,
    database_fingerprint,
    dump_postgres,
    file_digest,
    render_runtime,
    verify_runtime,
)
from dianxun.state import SQLiteStateStore
from tests import test_worker_runtime as fixture


class FinalOperationsTests(unittest.TestCase):
    initialize_runtime_fixture = fixture.WorkerRuntimeTests.initialize_runtime_fixture
    rpc = fixture.WorkerRuntimeTests.rpc
    restart_runtime = fixture.WorkerRuntimeTests.restart_runtime
    assign = fixture.WorkerRuntimeTests.assign
    snapshot = fixture.WorkerRuntimeTests.snapshot

    def setUp(self):
        fixture.WorkerRuntimeTests.setUp(self)
        self.root = self.store.path.parent
        self.enterContext(
            patch.object(
                trace, "_DB_PATH", ContextVar("finals-trace", default=self.root / "trace.db")
            )
        )

    def detect(self):
        return self.rpc("Sentry", "complete", **self.assign("Sentry"))

    def test_scenario_ingress_is_gated_atomic_scoped_and_idempotent(self):
        args = {"scenario_id": "coldchain-compressor-failure", "event_id": "001-device-fault"}
        before = self.store.snapshot_digest()
        self.rpc("Orchestrator", "ingest_scenario", **args, expect_error=True)
        self.assertEqual(before, self.store.snapshot_digest())
        with patch.dict("os.environ", {"DIANXUN_SCENARIO_BRIDGE_ENABLED": "1"}):
            self.rpc("Sentry", "ingest_scenario", **args, expect_error=True)
            result = self.rpc("Orchestrator", "ingest_scenario", **args)
            source = result["context"]["source_events"][0]
            self.assertEqual("scenario", source["source_kind"])
            self.assertNotIn("root_cause", json.dumps(source))
            self.assertEqual("DETECT", result["remaining_stages"][0])
            before = self.store.snapshot_digest()
            again = self.rpc("Orchestrator", "ingest_scenario", **args)
            self.assertEqual(result, again)
            self.assertEqual(before, self.store.snapshot_digest())
            self.server.runtime_service.evidence_clock = lambda: self.now
            with patch.dict("os.environ", {"DIANXUN_SCENARIO_VIRTUAL_CLOCK": "1"}):
                # The linked scenario can use an explicit virtual clock; ordinary runtime
                # incidents still fail on stale historical evidence under the same flags.
                original_incident = self.incident
                self.incident = result["incident"]["incident_id"]
                self.assertTrue(self.detect()["completed"])
                self.incident = original_incident
                self.assertFalse(self.detect()["completed"])
            self.store.set_meta("scenario_digest", "changed")
            self.rpc("Orchestrator", "ingest_scenario", **args, expect_error=True)

    def test_platform_binding_belongs_to_the_active_worker_and_cannot_be_replaced(self):
        lease = self.assign("Sentry")
        refs = dict(
            project_id="test-project",
            task_id="test-task",
            room_id="test-room",
            message_id="test-message",
            evidence_sha256="a" * 64,
        )
        self.rpc("Executor", "link_platform", **lease, **refs, expect_error=True)
        result = self.rpc("Sentry", "link_platform", **lease, **refs)
        self.assertFalse(result["replayed"])
        replayed = self.rpc("Sentry", "link_platform", **lease, **refs)
        self.assertTrue(replayed["replayed"])
        self.rpc(
            "Sentry",
            "link_platform",
            **lease,
            **{**refs, "evidence_sha256": "b" * 64},
            expect_error=True,
        )
        lease["expected_version"] = result["context_version"]
        completed = self.rpc("Sentry", "complete", **lease)
        self.assertTrue(completed["completed"])
        self.rpc(
            "Sentry",
            "link_platform",
            **lease,
            **{**refs, "message_id": "new-message"},
            expect_error=True,
        )
        lease["expected_version"] = completed["context_version"]
        result_refs = {
            **refs,
            "message_id": "result-message",
            "link_kind": "result",
            "output_digest": completed["output_digest"],
        }
        self.rpc(
            "Sentry",
            "link_platform",
            **lease,
            **{**result_refs, "output_digest": "c" * 64},
            expect_error=True,
        )
        self.rpc("Sentry", "link_platform", **lease, **result_refs)
        casefile = self.rpc("Orchestrator", "casefile", incident_id=self.incident)
        self.assertEqual(2, len(casefile["context"]["platform_links"]))
        self.assertEqual("sentry", casefile["context"]["attempt_outputs"][0]["worker_id"])
        self.assertIn("not_platform_verified", result["link"]["verification"])

    def test_casefile_is_scoped_read_only_and_supports_old_contexts(self):
        self.detect()
        before = self.store.snapshot_digest()
        data = self.rpc("Orchestrator", "casefile", incident_id=self.incident)
        self.assertEqual(before, self.store.snapshot_digest())
        self.assertEqual("available", data["trace"]["status"])
        self.assertTrue(any(r["skill_digest"] for r in data["trace"]["rows"]))
        self.rpc("other-store", "casefile", incident_id=self.incident, expect_error=True)
        self.assertEqual([], self.rpc("other-store", "cases")["items"])
        self.assertEqual(
            self.incident, self.rpc("Orchestrator", "cases")["items"][0]["incident_id"]
        )
        old = data["context"].copy()
        for key in ("source_events", "platform_links", "attempt_outputs"):
            old.pop(key)
        restored = TaskContext.from_snapshot(old)
        self.assertEqual([], restored.platform_links)
        with self.store.read_snapshot() as conn:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("UPDATE meta SET value = 'bad'")
        self.assertEqual(before, self.store.snapshot_digest())

    def test_scope_history_and_lineage_are_scoped_read_only_casefile_records(self):
        from dianxun.runtime import RuntimePrincipal

        self.store.migrate_scope_v2()
        runtime = self.server.runtime_service
        human = RuntimePrincipal("Human", "scope-human", "demo", "S03")
        runtime.principals[human.worker_id] = human
        parent = self.store.list_batches(batch_ids=["BATCH-S03-DAIRY-001"])[0]
        snapshot = runtime.snapshot(principal=human, incident_id=self.incident)
        runtime.call(
            "runtime_revise_scope",
            {
                "incident_id": self.incident,
                "expected_versions": {
                    self.incident: {
                        "scope_version": 1,
                        "context_version": snapshot["context"]["version"],
                    }
                },
                "change_id": "casefile-split",
                "source_ref": "synthetic:wms",
                "changes": [
                    {
                        "op": "split",
                        "batch_id": parent["batch_id"],
                        "children": [
                            {"batch_id": "CASE-C1", "quantity": 1},
                            {"batch_id": "CASE-C2", "quantity": parent["quantity"] - 1},
                        ],
                    }
                ],
            },
            human,
        )
        before = self.store.snapshot_digest()
        data = self.rpc("Orchestrator", "casefile", incident_id=self.incident)
        self.assertEqual(before, self.store.snapshot_digest())
        self.assertEqual([1, 2], [r["scope_version"] for r in data["records"]["scope_revisions"]])
        self.assertEqual(
            ["CASE-C1", "CASE-C2"], [r["child_batch_id"] for r in data["records"]["batch_lineage"]]
        )
        self.assertEqual(2, data["scope"]["version"])
        self.assertEqual("synthetic:wms", data["records"]["scope_revisions"][-1]["source_ref"])
        self.rpc("other-store", "casefile", incident_id=self.incident, expect_error=True)

    def test_runtime_capture_roundtrip_and_restored_data_comparison(self):
        self.detect()
        bundle = self.root / "bundle"
        principal = self.principals["Orchestrator"]
        with self.assertRaises(ValueError):
            capture_runtime(bundle, self.mcp, principal, self.incident)
        result = capture_runtime(bundle, self.mcp, principal, self.incident, quiesced=True)
        self.assertTrue(result["passed"])
        before = {p.name: file_digest(p) for p in bundle.iterdir()}
        render_runtime(bundle, self.root / "replay.html")
        self.assertEqual(before, {p.name: file_digest(p) for p in bundle.iterdir()})
        with self.assertRaises(ValueError):
            render_runtime(bundle, bundle / "state.sqlite")
        linked = self.root / "hardlink.html"
        os.link(bundle / "state.sqlite", linked)
        with self.assertRaises(ValueError):
            render_runtime(bundle, linked)
        with self.assertRaisesRegex(ValueError, "separate"):
            check_restored(bundle, self.mcp, principal)
        restored_path = self.root / "restored.sqlite"
        shutil.copyfile(bundle / "state.sqlite", restored_path)
        restored = SimpleNamespace(store=SQLiteStateStore(restored_path), policy=self.mcp.policy)
        self.assertTrue(check_restored(bundle, restored, principal)["database_restore_verified"])
        with restored.store.transaction() as conn:
            conn.execute(
                "UPDATE devices SET health_state = 'offline' WHERE device_id = 'FROST-S03'"
            )
        with self.assertRaisesRegex(ValueError, "records"):
            check_restored(bundle, restored, principal)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        casefile_path = bundle / "casefile.json"
        casefile = json.loads(casefile_path.read_text(encoding="utf-8"))
        casefile["records"]["devices"][0]["health_state"] = "fabricated"
        write_json(casefile_path, casefile)
        manifest["files"]["casefile.json"] = file_digest(casefile_path)
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "records"):
            verify_runtime(bundle)

    def test_capture_rejects_trace_changes_and_keeps_failure_unsealed(self):
        self.detect()
        original = trace.read_trace
        calls = 0

        def changed(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = original(*args, **kwargs)
            return result if calls == 1 else {**result, "rows": []}

        bundle = self.root / "unstable"
        with patch.object(trace, "read_trace", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "Trace changed"):
                capture_runtime(
                    bundle, self.mcp, self.principals["Orchestrator"], self.incident, quiesced=True
                )
        self.assertFalse((bundle / "manifest.json").exists())

    def test_pg_dump_uses_shared_snapshot_and_redacts_subprocess_errors(self):
        store = SimpleNamespace(dsn="postgresql://localhost/replay_test")
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = {
            "database": "replay_test",
            "snapshot": "0001-1",
        }
        output = self.root / "state.pgdump"
        with (
            patch("dianxun.runtime_replay.pg_environment", return_value={}),
            patch("dianxun.runtime_replay.subprocess.run") as run,
        ):
            run.return_value = SimpleNamespace(returncode=1, stderr=b"private diagnostic")
            with self.assertRaises(RuntimeError) as caught:
                dump_postgres(store, conn, output)
            self.assertNotIn("private", str(caught.exception))
            self.assertIn("--snapshot=0001-1", run.call_args.args[0])
            self.assertNotIn(store.dsn, str(run.call_args.args))
            calls = run.call_count
            conn.execute.return_value.fetchone.return_value = {"database": "production"}
            with self.assertRaises(ValueError):
                dump_postgres(
                    SimpleNamespace(dsn="postgresql://localhost/replay_test?dbname=production"),
                    conn,
                    output,
                )
            self.assertEqual(calls, run.call_count)
        conn.execute.return_value.fetchone.return_value = {
            "database": "replay_test",
            "address": "127.0.0.1",
            "port": 5432,
        }
        # Alternate URL spellings must not make the same source appear restored.
        store.backend_name = "postgresql"
        store.read_snapshot = lambda: nullcontext(conn)
        source = database_fingerprint(store)
        store.dsn = "postgresql://alias/other?dbname=replay_test"
        self.assertEqual(source, database_fingerprint(store))

    def test_operations_assets_contain_no_data_and_disallow_inline_scripts(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        self.addCleanup(connection.close)
        connection.request("GET", "/operations")
        response = connection.getresponse()
        self.assertEqual(200, response.status)
        self.assertIn("script-src 'self'", response.getheader("Content-Security-Policy"))
        document = response.read().decode("utf-8")
        self.assertNotIn(self.incident, document)
        connection.request("GET", "/operations.js")
        response = connection.getresponse()
        self.assertEqual(200, response.status)
        script = response.read().decode("utf-8")
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("localStorage", script)


if __name__ == "__main__":
    unittest.main()
