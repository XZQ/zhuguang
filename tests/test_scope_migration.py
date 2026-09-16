from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from dianxun.domain import IncidentCase, IncidentType, Severity
from dianxun.state import StateStore
from dianxun.validation import validate_json


class ScopeMigrationTests(unittest.TestCase):
    """Legacy fixtures deliberately do not use the current schema builder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StateStore(Path(self.tmp.name) / "legacy.db")
        with closing(self.store.connect()) as conn:
            conn.executescript("""
                CREATE TABLE inventory_batches (
                    batch_id TEXT PRIMARY KEY, store_id TEXT, device_id TEXT,
                    sku_id TEXT, product_name TEXT, quantity INTEGER,
                    storage_min_c REAL, storage_max_c REAL, disposition TEXT,
                    safe_for_sale INTEGER, policy_ref TEXT, updated_at TEXT);
                INSERT INTO inventory_batches VALUES
                    ('P','S','D','SKU','milk',10,0,4,'quarantined',0,'v1','now');
                CREATE TABLE incidents (
                    incident_id TEXT PRIMARY KEY, tenant_id TEXT, store_id TEXT,
                    incident_status TEXT, case_json TEXT);
                CREATE TABLE approvals (
                    approval_id TEXT PRIMARY KEY, incident_id TEXT, action_id TEXT,
                    status TEXT);
                INSERT INTO approvals VALUES ('A','I','X','approved');
                CREATE TABLE actions (
                    action_id TEXT PRIMARY KEY, incident_id TEXT, status TEXT,
                    request_json TEXT, response_json TEXT);
                INSERT INTO actions VALUES ('X','I','succeeded','{ "qty": 10 }',
                    '{ "receipt": "physical-1" }');
                CREATE TABLE verifications (verification_id TEXT PRIMARY KEY);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            for ident, status in (("I", "OPEN"), ("C", "CLOSED")):
                case = {
                    "incident_id": ident,
                    "tenant_id": "demo",
                    "store_id": "S",
                    "incident_status": status,
                    "affected_assets": ["D"],
                    "affected_batches": ["P"],
                    "version": 7,
                }
                conn.execute(
                    "INSERT INTO incidents VALUES (?, 'demo', 'S', ?, ?)",
                    (ident, status, json.dumps(case)),
                )
            conn.commit()

    def test_upgrade_preserves_receipts_and_closed_history_and_is_repeatable(self):
        with closing(self.store.connect()) as conn:
            before = tuple(conn.execute("SELECT * FROM actions").fetchone())
            closed = conn.execute(
                "SELECT case_json FROM incidents WHERE incident_id='C'"
            ).fetchone()[0]
        self.store.migrate_scope_v2()
        self.store.migrate_scope_v2()
        with closing(self.store.connect()) as conn:
            self.assertEqual(
                before,
                tuple(
                    conn.execute(
                        "SELECT action_id, incident_id, status, request_json, response_json "
                        "FROM actions"
                    ).fetchone()
                ),
            )
            self.assertEqual(
                closed,
                conn.execute("SELECT case_json FROM incidents WHERE incident_id='C'").fetchone()[0],
            )
            case = json.loads(
                conn.execute("SELECT case_json FROM incidents WHERE incident_id='I'").fetchone()[0]
            )
            self.assertEqual(1, case["scope_version"])
            self.assertEqual(8, case["version"])
            self.assertEqual(10, case["scope_snapshot"]["batches"][0]["quantity"])
            self.assertEqual(
                "requires_review",
                conn.execute(
                    "SELECT applicability FROM approvals WHERE approval_id='A'"
                ).fetchone()[0],
            )
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM scope_revisions").fetchone()[0])
            self.assertEqual(
                "active", conn.execute("SELECT lifecycle FROM inventory_batches").fetchone()[0]
            )

    def test_new_exposure_requires_reconciliation_without_expanding_old_scope(self):
        with closing(self.store.connect()) as conn:
            conn.execute(
                "INSERT INTO inventory_batches SELECT 'Q', store_id, device_id, sku_id, "
                "product_name, 3, storage_min_c, storage_max_c, disposition, safe_for_sale, "
                "policy_ref, updated_at FROM inventory_batches WHERE batch_id='P'"
            )
            conn.commit()
        self.store.migrate_scope_v2()
        case = self.store.get_incident("I")
        self.assertEqual("requires_reconciliation", case["scope_state"])
        self.assertEqual(["P"], case["affected_batches"])
        self.assertEqual(["P"], [r["batch_id"] for r in case["scope_snapshot"]["batches"]])

    def test_missing_inventory_is_not_silently_dropped(self):
        with closing(self.store.connect()) as conn:
            conn.execute("DELETE FROM inventory_batches WHERE batch_id='P'")
            conn.commit()
        self.store.migrate_scope_v2()
        case = self.store.get_incident("I")
        self.assertEqual(0, case["scope_version"])
        self.assertEqual("requires_reconciliation", case["scope_state"])
        self.assertIsNone(case["scope_snapshot"])
        self.assertEqual(["P"], case["affected_batches"])

    def test_failed_backfill_rolls_back_schema_and_all_data(self):
        with closing(self.store.connect()) as conn:
            conn.execute("UPDATE incidents SET case_json='not-json' WHERE incident_id='I'")
            conn.commit()
        with self.assertRaises(ValueError):
            self.store.migrate_scope_v2()
        with closing(self.store.connect()) as conn:
            self.assertNotIn(
                "lifecycle", [r[1] for r in conn.execute("PRAGMA table_info(inventory_batches)")]
            )
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0])

    def test_readiness_does_not_upgrade_database(self):
        with self.assertRaisesRegex(RuntimeError, "scope"):
            self.store.require_scope_schema()
        self.store.migrate_scope_v2()
        self.store.require_scope_schema()
        with closing(self.store.connect()) as conn:
            conn.execute("DROP TABLE batch_lineage")
            conn.commit()
        with self.assertRaises((RuntimeError, sqlite3.OperationalError)):
            self.store.require_scope_schema()

    def test_scope_case_roundtrip_remains_valid_for_export(self):
        case = IncidentCase.create(
            tenant_id="demo",
            store_id="S",
            incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
            severity=Severity.HIGH,
            trigger="event",
            anchor_time="2026-09-16T00:00:00Z",
        )
        schema = json.loads(
            (
                Path(__file__).resolve().parents[1] / "schemas/incident-case.v1.schema.json"
            ).read_text()
        )
        raw = case.to_dict()
        self.assertEqual([], validate_json(raw, schema))
        self.store.migrate_scope_v2()
        migrated = self.store.get_incident("I")
        raw.update(
            {
                k: migrated[k]
                for k in ("scope_version", "scope_snapshot", "scope_digest", "scope_state")
            }
        )
        self.assertEqual(raw, IncidentCase.from_dict(raw).to_dict())
        self.assertEqual([], validate_json(raw, schema))
