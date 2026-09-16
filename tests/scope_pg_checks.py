"""Run explicitly against a fresh isolated PG database; no reset or credentials embedded."""

import os
import unittest

from dianxun.domain import IncidentCase, IncidentService, IncidentType, Severity
from dianxun.mcp.p0 import DEFAULT_SEED_PATH
from dianxun.state import PostgresStateStore


class ScopePostgresChecks(unittest.TestCase):
    def test_upgrade_and_scoped_append_only_permissions(self):
        admin = PostgresStateStore(os.environ["DIANXUN_TEST_POSTGRES_DSN"])
        self.assertIn("scope_v2_test", admin.database_identity)
        admin.apply_profile("core")
        admin.apply_profile("security")
        admin.initialize_from_file(DEFAULT_SEED_PATH, reset=False)
        case = IncidentCase.create(
            incident_id="scope-upgrade",
            tenant_id="demo",
            store_id="S03",
            incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
            severity=Severity.HIGH,
            trigger="event",
            anchor_time=admin.now(),
        )
        case.affected_assets = ["FROST-S03"]
        case.affected_batches = ["BATCH-S03-DAIRY-001"]
        IncidentService(admin).create(case)
        with self.assertRaises(RuntimeError):
            admin.require_scope_schema()
        admin.migrate_scope_v2()
        admin.migrate_scope_v2()
        admin.require_scope_schema()
        self.assertEqual(1, admin.get_incident(case.incident_id)["scope_version"])
        with admin.transaction() as conn:
            conn.execute("""INSERT INTO dianxun_principal_scope
                (database_role,tenant_id,runtime_role,store_id)
                VALUES ('zhuguang_test_runtime','demo','runtime','S03')""")
        runtime = PostgresStateStore(
            os.environ["DIANXUN_TEST_POSTGRES_RUNTIME_DSN"], tenant_id="demo", store_id="S03"
        )
        runtime.require_scope_schema()
        with runtime.read_snapshot() as conn:
            role = conn.execute(
                "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user"
            ).fetchone()
            self.assertFalse(role["rolsuper"])
            self.assertFalse(role["rolbypassrls"])
            self.assertEqual(
                1, conn.execute("SELECT COUNT(*) AS n FROM scope_revisions").fetchone()["n"]
            )
        for statement in (
            "UPDATE scope_revisions SET actor='forged'",
            "DELETE FROM scope_revisions",
            "TRUNCATE scope_revisions",
            "UPDATE batch_lineage SET child_quantity=100",
            "DELETE FROM batch_lineage",
        ):
            with self.subTest(statement=statement), self.assertRaises(Exception) as caught:
                with runtime.transaction() as conn:
                    conn.execute(statement)
            self.assertEqual("42501", getattr(caught.exception, "sqlstate", None))
        with runtime.transaction() as conn:
            conn.execute("""INSERT INTO scope_revisions SELECT incident_id,2,'valid',
                tenant_id,store_id,'Human','test',after_json,after_json,'{}',created_at
                FROM scope_revisions WHERE scope_version=1""")
        with self.assertRaises(Exception) as caught:
            with runtime.transaction() as conn:
                conn.execute("""INSERT INTO scope_revisions SELECT incident_id,3,'forged',
                    'other','S04','Human','test',after_json,after_json,'{}',created_at
                    FROM scope_revisions WHERE scope_version=1""")
        self.assertEqual("42501", getattr(caught.exception, "sqlstate", None))
        with self.assertRaises(Exception) as caught:
            runtime.migrate_scope_v2()
        self.assertEqual("42501", getattr(caught.exception, "sqlstate", None))
        with admin.transaction() as conn:
            self.assertEqual(
                2, conn.execute("SELECT COUNT(*) AS n FROM scope_revisions").fetchone()["n"]
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
