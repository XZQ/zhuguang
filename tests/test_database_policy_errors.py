from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dianxun.state.postgres import _PostgresConnection
from dianxun.state.protocols import StorePolicyError
from tests import test_stateful_core as fixture


class DatabasePolicyTests(unittest.TestCase):
    setUp = fixture.StatefulCoreTests.setUp
    tearDown = fixture.StatefulCoreTests.tearDown

    def test_p0001_is_typed_and_does_not_disclose_raw_diagnostics(self):
        class DriverError(Exception):
            sqlstate = "P0001"

        driver = SimpleNamespace(
            Error=DriverError, IntegrityError=type("Integrity", (Exception,), {})
        )
        for message, code in [
            ("audit partition month_start must be the first day of a month", "AUDIT_MONTH_INVALID"),
            (
                "audit partition month is outside the allowed maintenance window",
                "AUDIT_WINDOW_REJECTED",
            ),
            ("private database diagnostic", "DATABASE_POLICY_REJECTED"),
        ]:
            error = DriverError("private parameters")
            error.diag = SimpleNamespace(message_primary=message)
            raw = Mock()
            raw.execute.side_effect = error
            raw.cursor.return_value.executemany.side_effect = error
            connection = _PostgresConnection(raw, driver)
            for call in (
                lambda connection=connection: connection.execute("SELECT 1"),
                lambda connection=connection: connection.executemany("SELECT ?", [(1,)]),
            ):
                with self.assertRaises(StorePolicyError) as caught:
                    call()
                self.assertEqual(code, caught.exception.code)
                self.assertFalse(caught.exception.retryable)
                self.assertNotIn("private", str(caught.exception))

    def test_audit_policy_rejection_rolls_back_business_action_and_idempotency(self):
        before = self.store.snapshot_digest()
        with patch.object(
            self.store, "record_audit", side_effect=StorePolicyError("AUDIT_WINDOW_REJECTED")
        ):
            result = self.service.apply_sales_hold(
                incident_id="INC-M1-HOLD",
                action_id="audit-reject-hold",
                store_id="S03",
                batch_ids=["BATCH-S03-DAIRY-001"],
                reason="synthetic test",
                idempotency_key="audit-reject-hold",
                actor="Executor",
            )
        self.assertFalse(result["ok"])
        self.assertEqual("AUDIT_WINDOW_REJECTED", result["error"]["code"])
        self.assertEqual("P0001", result["error"]["sqlstate"])
        self.assertFalse(result["error"]["retryable"])
        self.assertIsNone(result["audit_ref"])
        self.assertEqual(before, self.store.snapshot_digest())
