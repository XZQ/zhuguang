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
_RUNTIME_DSN = os.environ.get("DIANXUN_TEST_POSTGRES_RUNTIME_DSN", "")
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
        self._assert_partition_guards()
        self._assert_pgvector_workflow()
        self._assert_read_snapshot()
        self._assert_limited_runtime_http()

    def _assert_limited_runtime_http(self):
        # The admin prepares ONLY synthetic fixtures. All MCP/Worker requests use
        # a separate NOSUPERUSER/NOBYPASSRLS login, never SET ROLE or an admin DSN.
        from dianxun.domain import PolicyEngine
        from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, MCPService
        from dianxun.scenarios import ScenarioEngine
        from tests.test_worker_runtime import WorkerRuntimeTests

        if not _RUNTIME_DSN:
            raise RuntimeError("A separate DIANXUN_TEST_POSTGRES_RUNTIME_DSN is required")
        runtime_user = urlsplit(_RUNTIME_DSN).username
        if not runtime_user or runtime_user in {
            urlsplit(_DSN).username,
            urlsplit(_READONLY_DSN).username,
        }:
            raise RuntimeError("Runtime login must differ from admin and readonly logins")
        admin = self.store
        admin.apply_profile("security")
        with admin.transaction() as conn:
            database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
            conn.execute(
                """INSERT INTO dianxun_principal_scope(
                    database_role, tenant_id, runtime_role, store_id
                ) VALUES(?, 'demo', 'runtime', 'S03')
                ON CONFLICT(database_role) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    runtime_role = excluded.runtime_role,
                    store_id = excluded.store_id""",
                (runtime_user,),
            )

        class LimitedRuntimeCase(WorkerRuntimeTests):
            def initialize_runtime_fixture(case, path):
                admin.initialize_from_file(DEFAULT_SEED_PATH, reset=True)
                case.scenario = ScenarioEngine(
                    admin,
                    DEFAULT_SCENARIO_PATH,
                    service=MCPService(admin, PolicyEngine(DEFAULT_POLICY_PATH)),
                )
                case.scenario.reset()
                case.store = PostgresStateStore(
                    _RUNTIME_DSN, tenant_id="demo", runtime_role="runtime", store_id="S03"
                )
                with case.store.read_snapshot() as conn:
                    identity = conn.execute(
                        """SELECT session_user AS login, current_database() AS database,
                        rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
                        FROM pg_roles WHERE rolname = session_user"""
                    ).fetchone()
                    case.assertEqual(runtime_user, identity["login"])
                    case.assertEqual(database, identity["database"])
                    for flag in ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole"):
                        case.assertFalse(identity[flag], flag)
                case.mcp = MCPService(case.store, PolicyEngine(DEFAULT_POLICY_PATH))

        names = [
            "test_real_http_workflow_recovers_after_restart_and_closes_independently",
            "test_scope_actor_lease_and_claims_cannot_be_forged",
            "test_diagnosis_output_survives_lost_response_and_restart",
            "test_failed_audit_can_recontain_reexecute_and_close",
        ]
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.TestSuite(LimitedRuntimeCase(name) for name in names)
        )
        self.assertEqual(4, result.testsRun)
        self.assertFalse(result.skipped)
        self.assertTrue(result.wasSuccessful(), "Non-admin PostgreSQL runtime protocol failed")

    def _assert_read_snapshot(self):
        from psycopg.errors import ReadOnlySqlTransaction

        with self.store.read_snapshot() as conn:
            self.assertEqual(
                "on", conn.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"]
            )
            self.assertEqual(
                "repeatable read",
                conn.execute("SHOW transaction_isolation").fetchone()["transaction_isolation"],
            )
            self.assertTrue(
                conn.execute("SELECT pg_export_snapshot() AS snapshot").fetchone()["snapshot"]
            )
            with self.assertRaises(ReadOnlySqlTransaction):
                with self.store.transaction():
                    conn.execute("UPDATE meta SET value = value WHERE key = 'virtual_time'")
            self.assertEqual(1, conn.execute("SELECT 1 AS healthy").fetchone()["healthy"])

    def _assert_partition_guards(self):
        from datetime import timedelta

        from dianxun.state.protocols import StorePolicyError

        with self.store.transaction() as conn:
            first = conn.execute(
                "SELECT date_trunc('month', CURRENT_DATE)::date AS month"
            ).fetchone()["month"]
            from datetime import date

            month = date.fromisoformat(first)
            for value, code in [
                (month + timedelta(days=1), "AUDIT_MONTH_INVALID"),
                (month.replace(year=month.year + 2), "AUDIT_WINDOW_REJECTED"),
            ]:
                with self.assertRaises(StorePolicyError) as caught:
                    with self.store.transaction():
                        conn.execute(
                            "SELECT ensure_audit_partition(CAST(? AS date))", (value.isoformat(),)
                        )
                self.assertEqual(code, caught.exception.code)
                self.assertFalse(caught.exception.retryable)
            conn.execute("SELECT ensure_audit_partition(CAST(? AS date))", (first,))
            conn.execute(
                "SELECT ensure_audit_partition((CAST(? AS date) + INTERVAL '1 month')::date)",
                (first,),
            )
            self.assertEqual(1, conn.execute("SELECT 1 AS healthy").fetchone()["healthy"])

    def _assert_pgvector_workflow(self):
        # Exercises the actual PostgreSQL vector write/search branch. The offline
        # hash embedder verifies SQL wiring, not semantic quality or store value.
        from unittest.mock import patch

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, {"DIANXUN_EMBEDDING_MODE": "hash"}),
        ):
            adapter = LocalDemoAdapter(
                db_path=_DSN,
                scenario_path=DEFAULT_SCENARIO_PATH,
                trace_db_path=Path(temporary) / "vector-trace.db",
                enable_rag=True,
            )
            result = adapter.run()
            knowledge_id = result["review"]["knowledge"]["knowledge_id"]
            adapter.knowledge.review_candidate(
                knowledge_id=knowledge_id,
                decision="approve",
                reviewer="Human",
                reason="synthetic isolated integration",
                redaction_passed=True,
            )
            hits = adapter.knowledge.search(tenant_id="demo", query="冷柜 压缩机故障 维修后复测")[
                "hits"
            ]
            self.assertTrue(any(hit["knowledge_id"] == knowledge_id for hit in hits))

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
