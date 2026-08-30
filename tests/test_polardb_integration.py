from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from dianxun.adapters import LocalDemoAdapter
from dianxun.mcp.p0 import DEFAULT_SCENARIO_PATH, DEFAULT_SEED_PATH
from dianxun.state import PostgresStateStore

_DSN = os.environ.get("DIANXUN_TEST_POSTGRES_DSN", "")
_READONLY_DSN = os.environ.get("DIANXUN_TEST_POSTGRES_READONLY_DSN", "")
_RESET_ALLOWED = os.environ.get("DIANXUN_ALLOW_TEST_DATABASE_RESET") == "1"


@unittest.skipUnless(
    _DSN and _RESET_ALLOWED,
    "set an isolated DIANXUN_TEST_POSTGRES_DSN and explicit reset opt-in",
)
class PolarDBIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_name = urlsplit(_DSN).path.casefold()
        if "test" not in database_name:
            raise RuntimeError("Integration DSN database name must contain 'test'")
        cls.store = PostgresStateStore(_DSN, tenant_id="demo", runtime_role="hq")
        cls.store.apply_profile("core")
        cls.store.initialize_from_file(DEFAULT_SEED_PATH, reset=True)

    def test_same_scenario_has_sqlite_and_postgres_state_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sqlite_result = LocalDemoAdapter(
                db_path=root / "runtime.db",
                scenario_path=DEFAULT_SCENARIO_PATH,
                trace_db_path=root / "sqlite-trace.db",
            ).run()
            postgres_result = LocalDemoAdapter(
                db_path=_DSN,
                scenario_path=DEFAULT_SCENARIO_PATH,
                trace_db_path=root / "postgres-trace.db",
            ).run()

        for key in ("result", "acceptance"):
            self.assertEqual(sqlite_result[key], postgres_result[key])
        for key in ("phase", "incident_status", "work_status", "batch_dispositions"):
            self.assertEqual(sqlite_result["incident"][key], postgres_result["incident"][key])
        self.assertEqual(
            sqlite_result["phases"]["DIAGNOSE_DECIDE"]["hypotheses"][0]["label"],
            postgres_result["phases"]["DIAGNOSE_DECIDE"]["hypotheses"][0]["label"],
        )

    @unittest.skipUnless(
        _READONLY_DSN,
        "set a separately provisioned DIANXUN_TEST_POSTGRES_READONLY_DSN",
    )
    def test_security_profile_enforces_readonly_and_hq_supplier_boundary(self) -> None:
        from psycopg.errors import InsufficientPrivilege

        self.store.apply_profile("security")
        hq = PostgresStateStore(_DSN, tenant_id="demo", runtime_role="hq")
        with hq.transaction() as conn:
            conn.execute(
                """INSERT INTO supplier_contracts(
                    supplier_id, tenant_id, supplier_name, risk_level,
                    contract_terms_json, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, supplier_id) DO UPDATE SET
                    risk_level = excluded.risk_level,
                    updated_at = excluded.updated_at""",
                (
                    "supplier-test",
                    "demo",
                    "redacted supplier",
                    "medium",
                    "{}",
                    "2026-08-28T12:00:00+08:00",
                ),
            )
            readonly_user = urlsplit(_READONLY_DSN).username
            if not readonly_user:
                raise RuntimeError("Readonly integration DSN requires a username")
            conn.execute(
                """INSERT INTO dianxun_principal_scope(
                    database_role, tenant_id, runtime_role, store_id
                ) VALUES(?, 'demo', 'runtime', 'S03')
                ON CONFLICT(database_role) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    runtime_role = excluded.runtime_role,
                    store_id = excluded.store_id""",
                (readonly_user,),
            )

        scoped = PostgresStateStore(
            _READONLY_DSN,
            tenant_id="demo",
            runtime_role="runtime",
            store_id="S03",
        )
        connection = scoped.connect()
        try:
            rows = connection.execute("SELECT store_id FROM stores ORDER BY store_id").fetchall()
            self.assertEqual(["S03"], [row["store_id"] for row in rows])
            with self.assertRaises(InsufficientPrivilege):
                connection.execute(
                    "UPDATE devices SET health_state = 'fault' WHERE device_id = 'FROST-S03'"
                )
        finally:
            connection.rollback()
            connection.close()

        non_hq = PostgresStateStore(
            _READONLY_DSN,
            tenant_id="demo",
            runtime_role="runtime",
            store_id="S03",
        )
        connection = non_hq.connect()
        try:
            with self.assertRaises(InsufficientPrivilege):
                connection.execute("SELECT supplier_id FROM supplier_contracts").fetchall()
        finally:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
