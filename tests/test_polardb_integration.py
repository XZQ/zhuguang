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
        # Exercise a real PostgreSQL error: the outer transaction must remain usable.
        from dianxun.state.protocols import StoreIntegrityError

        with self.store.transaction() as conn:
            self.store.set_meta("savepoint-outer", "kept")
            with self.assertRaises(StoreIntegrityError):
                with self.store.transaction():
                    self.store.set_meta("savepoint-inner", "discarded")
                    conn.execute(
                        "INSERT INTO meta(key, value) VALUES('savepoint-outer', 'duplicate')"
                    )
            self.assertIsNone(self.store.get_meta("savepoint-inner"))
        self.assertEqual("kept", self.store.get_meta("savepoint-outer"))
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
        self._assert_runtime_recovery_concurrency()

    def _assert_runtime_recovery_concurrency(self):
        from concurrent.futures import ThreadPoolExecutor
        from datetime import UTC, datetime, timedelta
        from threading import Barrier

        from dianxun.domain import PolicyEngine
        from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, MCPService
        from dianxun.runtime import RuntimePrincipal, RuntimeService

        now = [datetime.now(UTC)]
        main = RuntimePrincipal("Orchestrator", "pg-main", "demo", "S03")
        worker = RuntimePrincipal("Sentry", "pg-sentry", "demo", "S03")
        mcp = MCPService(self.store, PolicyEngine(DEFAULT_POLICY_PATH))
        services = [RuntimeService(mcp, [main, worker], clock=lambda: now[0]) for _ in range(2)]
        runtime = services[0]
        incident = "INC-PG-RECOVERY"
        opened = runtime.call(
            "runtime_open", {"incident_id": incident, "device_id": "FROST-S03"}, main
        )
        runtime.call("runtime_poll", {}, worker)
        first = runtime.call(
            "runtime_assign",
            {
                "incident_id": incident,
                "worker_id": worker.worker_id,
                "expected_version": opened["context"]["version"],
            },
            main,
        )
        now[0] += timedelta(seconds=61)
        runtime.recovery.tick()
        now[0] += timedelta(seconds=31)
        runtime.call("runtime_poll", {}, worker)
        barrier = Barrier(2)

        def sweep(service):
            barrier.wait(timeout=10)
            return service.recovery.tick()

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(sweep, service) for service in services]
            for future in futures:
                future.result(timeout=30)
        state = runtime.call("runtime_snapshot", {"incident_id": incident}, main)
        successors = [
            a
            for a in state["context"]["assignments"]
            if a["predecessor_assignment_id"] == first["assignment"]["assignment_id"]
        ]
        self.assertEqual(1, len(successors))

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
