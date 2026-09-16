"""Run scope revision cases with actual restricted PG sessions in fresh test databases."""

import hashlib
import os
import unittest
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

from dianxun.domain import PolicyEngine
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, DEFAULT_SEED_PATH, MCPService
from dianxun.runtime_context import RuntimeContextBus
from dianxun.state import PostgresStateStore
from dianxun.state.protocols import StorePolicyError
from tests import test_scope_revision


class LimitedScopeRevisionTests(test_scope_revision.ScopeRevisionTests):
    def initialize_store(self, path):
        base = os.environ["DIANXUN_TEST_POSTGRES_DSN"]
        name = (
            "scope_v2_test_"
            + os.environ["DIANXUN_TEST_RUN_ID"]
            + "_"
            + hashlib.sha256(self._testMethodName.encode()).hexdigest()[:8]
        )
        if not name.replace("_", "").isalnum():
            raise ValueError("Invalid test run identifier")
        with psycopg.connect(base, autocommit=True) as conn:
            # Existing databases cause an error; this runner never drops or resets one.
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        parsed = urlsplit(base)
        self.admin = PostgresStateStore(urlunsplit(parsed._replace(path="/" + name)))
        self.admin.apply_profile("core")
        self.admin.apply_profile("security")
        self.admin.initialize_from_file(DEFAULT_SEED_PATH, reset=False)
        runtime_base = urlsplit(os.environ["DIANXUN_TEST_POSTGRES_RUNTIME_DSN"])
        self.runtime_dsn = urlunsplit(runtime_base._replace(path="/" + name))
        with self.admin.transaction() as conn:
            conn.execute(
                """INSERT INTO dianxun_principal_scope
                (database_role,tenant_id,runtime_role,store_id)
                VALUES (?,'demo','runtime','S03')""",
                (runtime_base.username,),
            )
        return self.admin

    def setUp(self):
        super().setUp()
        # Only fixture creation and migrations use admin. All tested revisions use
        # a distinct NOSUPERUSER/NOBYPASSRLS login, not SET ROLE on the admin connection.
        self.store = PostgresStateStore(self.runtime_dsn, tenant_id="demo", store_id="S03")
        self.store.ensure_schema()
        self.store.require_scope_schema()
        with self.store.read_snapshot() as conn:
            role = conn.execute(
                "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user"
            ).fetchone()
            self.assertFalse(role["rolsuper"])
            self.assertFalse(role["rolbypassrls"])
        from dianxun.runtime import RuntimeService

        self.runtime = RuntimeService(
            MCPService(self.store, PolicyEngine(DEFAULT_POLICY_PATH)),
            [self.human, self.orchestrator],
        )
        self.bus = RuntimeContextBus(self.store, "demo")

    def inject_audit_failure(self):
        with self.admin.transaction() as conn:
            conn._connection.execute(
                """
                CREATE FUNCTION reject_scope_audit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'injected audit failure'; END $$;
                CREATE TRIGGER reject_scope_audit BEFORE INSERT ON audit_log
                    FOR EACH ROW EXECUTE FUNCTION reject_scope_audit();
            """,
                prepare=False,
            )
        return StorePolicyError


if __name__ == "__main__":
    unittest.main(verbosity=2)
