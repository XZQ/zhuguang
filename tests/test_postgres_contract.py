from __future__ import annotations

import unittest
from importlib import resources

from dianxun.state import PostgresStateStore, create_state_store
from dianxun.state.postgres import qmark_to_postgres, redact_dsn


class PostgresContractTests(unittest.TestCase):
    def test_factory_selects_postgres_without_importing_optional_driver(self) -> None:
        dsn = "postgresql://runtime:secret@db.example:5432/dianxun?sslmode=require"
        store = create_state_store(dsn, tenant_id="tenant-a")
        self.assertIsInstance(store, PostgresStateStore)
        self.assertEqual("postgresql", store.backend_name)
        self.assertEqual(
            "postgresql://runtime@db.example:5432/dianxun",
            store.database_identity,
        )
        self.assertNotIn("secret", redact_dsn(dsn))
        self.assertNotIn("sslmode", redact_dsn(dsn))

    def test_qmark_translation_preserves_quoted_question_marks(self) -> None:
        sql = "SELECT '?' AS literal, value FROM meta WHERE key = ? AND note = 'it''s ?'"
        self.assertEqual(
            "SELECT '?' AS literal, value FROM meta WHERE key = %s AND note = 'it''s ?'",
            qmark_to_postgres(sql),
        )

    def test_migrations_encode_pgvector_partition_rls_readonly_and_safe_cron(self) -> None:
        package = resources.files("dianxun.state.sql")
        core = package.joinpath("postgres_schema.sql").read_text(encoding="utf-8")
        security = package.joinpath("postgres_security.sql").read_text(encoding="utf-8")
        cron = package.joinpath("postgres_cron.sql").read_text(encoding="utf-8")
        archive = package.joinpath("postgres_archive.sql").read_text(encoding="utf-8")

        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", core)
        self.assertIn("embedding vector", core)
        self.assertIn("PARTITION BY RANGE (created_at)", core)
        self.assertIn("ensure_audit_partition", core)
        self.assertIn("ux_active_hold_incident_batch", core)
        self.assertIn("ux_approvals_action", core)
        self.assertIn("ux_workorders_action", core)
        self.assertIn("supplier_contracts", core)
        self.assertIn("ENABLE ROW LEVEL SECURITY", security)
        self.assertIn("dianxun_principal_scope", security)
        self.assertIn("session_user::TEXT", security)
        self.assertIn(
            "principal.tenant_id = '*' OR principal.tenant_id = row_tenant",
            security,
        )
        self.assertNotIn("current_setting('dianxun.runtime_role'", security)
        self.assertIn("supplier_hq_only", security)
        self.assertIn("GRANT SELECT ON stores, devices", security)
        self.assertIn(
            "FROM dianxun_runtime, dianxun_business_ro, dianxun_hq",
            security,
        )
        self.assertNotIn(
            "GRANT SELECT, INSERT, UPDATE ON dianxun_principal_scope",
            security,
        )
        business_grants = [
            statement
            for statement in security.split(";")
            if "GRANT" in statement and "dianxun_business_ro" in statement
        ]
        self.assertTrue(business_grants)
        for statement in business_grants:
            self.assertNotIn("INSERT", statement)
            self.assertNotIn("UPDATE", statement)
            self.assertNotIn("DELETE", statement)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_cron", cron)
        self.assertIn("INSERT INTO review_jobs", cron)
        self.assertIn("dianxun_cron_health", cron)
        self.assertIn("cron.job_run_details", cron)
        self.assertNotIn("AgentTeams", cron)
        self.assertNotIn("http://", cron)
        self.assertIn("stage_audit_partition_to_foreign", archive)
        self.assertIn("REVOKE ALL ON FUNCTION ensure_audit_partition", core)
        self.assertIn("destination_table must be a provisioned foreign table", archive)
        self.assertIn("archive verification mismatch", archive)
        self.assertIn("status = 'verified'", archive)
        self.assertIn("SECURITY DEFINER", archive)
        self.assertIn("verified_at", archive)
        self.assertNotIn("DROP TABLE", archive)
        self.assertNotIn("DELETE FROM audit_log", archive)


if __name__ == "__main__":
    unittest.main()
