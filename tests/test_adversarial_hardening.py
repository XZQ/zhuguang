from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

from dianxun.agents import Orchestrator
from dianxun.domain import (
    IncidentCase,
    IncidentService,
    IncidentType,
    PolicyEngine,
    Severity,
    Verification,
    VerificationResult,
)
from dianxun.mcp.iot import query_device_series
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, MCPService
from dianxun.mcp.server import MAX_REQUEST_BYTES, MCPHandler, _validate_server_auth, tool_call
from dianxun.scenarios import ScenarioEngine
from dianxun.state import StateStore

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "demo" / "state" / "seed.json"
SCENARIO_PATH = ROOT / "demo" / "state" / "scenarios" / "coldchain-compressor-failure.json"


class AdversarialHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.temporary.name) / "runtime.db")
        self.store.initialize_from_file(SEED_PATH)
        self.service = MCPService(self.store, PolicyEngine(DEFAULT_POLICY_PATH))
        self.incidents = IncidentService(self.store)
        self.case = IncidentCase.create(
            incident_id="INC-ADVERSARIAL",
            tenant_id="demo",
            store_id="S03",
            incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
            severity=Severity.CRITICAL,
            trigger="test",
            anchor_time=self.store.now(),
        )
        self.case.affected_assets = ["FROST-S03"]
        self.case.affected_batches = [
            "BATCH-S03-DAIRY-001",
            "BATCH-S03-FRESH-001",
        ]
        self.incidents.create(self.case)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_idempotency_key_rejects_a_different_payload(self) -> None:
        first = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-HOLD-ONE",
            store_id="S03",
            batch_ids=["BATCH-S03-DAIRY-001"],
            reason="first request",
            idempotency_key="shared-key",
        )
        conflict = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-HOLD-TWO",
            store_id="S03",
            batch_ids=["BATCH-S03-FRESH-001"],
            reason="different request",
            idempotency_key="shared-key",
        )
        self.assertTrue(first["ok"])
        self.assertFalse(conflict["ok"])
        self.assertEqual("IDEMPOTENCY_CONFLICT", conflict["error"]["code"])
        self.assertEqual(1, len(self.store.list_sales_holds(incident_id=self.case.incident_id)))

    def test_action_id_cannot_create_a_second_side_effect_with_a_new_key(self) -> None:
        first = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-ONE-SIDE-EFFECT",
            store_id="S03",
            batch_ids=["BATCH-S03-DAIRY-001"],
            reason="containment",
            idempotency_key="hold-key-1",
        )
        duplicate = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-ONE-SIDE-EFFECT",
            store_id="S03",
            batch_ids=["BATCH-S03-FRESH-001"],
            reason="second mutation",
            idempotency_key="hold-key-2",
        )
        self.assertTrue(first["ok"])
        self.assertFalse(duplicate["ok"])
        self.assertEqual("INVALID_STATE", duplicate["error"]["code"])
        self.assertEqual(1, len(self.store.list_sales_holds(incident_id=self.case.incident_id)))

    def test_write_cannot_escape_incident_store_scope(self) -> None:
        response = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-CROSS-STORE",
            store_id="S04",
            batch_ids=["BATCH-S03-DAIRY-001"],
            reason="cross-store attempt",
            idempotency_key="cross-store-key",
        )
        self.assertFalse(response["ok"])
        self.assertEqual("FORBIDDEN", response["error"]["code"])
        self.assertFalse(self.store.list_sales_holds(incident_id=self.case.incident_id))

    def test_workorder_approval_is_bound_to_the_exact_amount(self) -> None:
        approval_id = self._approved_action(
            action_id="ACT-REPAIR",
            action_type="create_workorder",
            amount=2500.0,
        )
        response = self.service.create_workorder(
            incident_id=self.case.incident_id,
            action_id="ACT-REPAIR",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor failure",
            budget=5000.0,
            approval_id=approval_id,
            idempotency_key="repair-execute",
        )
        self.assertFalse(response["ok"])
        self.assertEqual("APPROVAL_INVALID", response["error"]["code"])
        self.assertFalse(self.store.list_workorders(incident_id=self.case.incident_id))

        first = self.service.create_workorder(
            incident_id=self.case.incident_id,
            action_id="ACT-REPAIR",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor failure",
            budget=2500.0,
            approval_id=approval_id,
            idempotency_key="repair-execute-first",
        )
        duplicate = self.service.create_workorder(
            incident_id=self.case.incident_id,
            action_id="ACT-REPAIR",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor failure",
            budget=2500.0,
            approval_id=approval_id,
            idempotency_key="repair-execute-second",
        )
        self.assertTrue(first["ok"])
        self.assertFalse(duplicate["ok"])
        self.assertEqual("INVALID_STATE", duplicate["error"]["code"])
        self.assertEqual(1, len(self.store.list_workorders(incident_id=self.case.incident_id)))

    def test_approval_rejects_invalid_amounts_before_policy_evaluation(self) -> None:
        for index, amount in enumerate((-1.0, float("nan"), float("inf"), True)):
            with self.subTest(amount=amount):
                response = self.service.create_approval(
                    incident_id=self.case.incident_id,
                    action_id=f"ACT-INVALID-AMOUNT-{index}",
                    subject="invalid amount",
                    requested_action_type="create_workorder",
                    amount=amount,
                    timeout_minutes=30,
                    idempotency_key=f"invalid-amount-{index}",
                )
                self.assertFalse(response["ok"], response)
                self.assertEqual("INVALID_ARGUMENT", response["error"]["code"])

    def test_batch_approval_is_bound_to_the_exact_disposition(self) -> None:
        approval_id = self._approved_action(
            action_id="ACT-BATCH",
            action_type="apply_batch_disposition",
            disposition="transferred",
        )
        response = self.service.apply_batch_disposition(
            incident_id=self.case.incident_id,
            action_id="ACT-BATCH",
            batch_ids=["BATCH-S03-DAIRY-001"],
            disposition="disposed",
            approval_id=approval_id,
            idempotency_key="batch-execute",
        )
        self.assertFalse(response["ok"])
        self.assertEqual("APPROVAL_INVALID", response["error"]["code"])
        batch = self.store.list_batches(batch_ids=["BATCH-S03-DAIRY-001"])[0]
        self.assertEqual("unknown", batch["disposition"])

    def test_sales_hold_release_requires_release_guard_verification(self) -> None:
        hold = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-HOLD",
            store_id="S03",
            batch_ids=["BATCH-S03-DAIRY-001"],
            reason="containment",
            idempotency_key="hold",
        )
        approval_id = self._approved_action(
            action_id="ACT-RELEASE",
            action_type="release_sales_hold",
        )
        verification = Verification(
            verification_id="VER-DEVICE-ONLY",
            subject="device",
            method="test",
            expected_condition={"healthy": True},
            observed_value={"healthy": True},
            evidence_ids=[],
            result=VerificationResult.PASSED,
            verifier="Auditor",
            verified_at=self.store.now(),
        )
        self.incidents.record_verification(self.case.incident_id, verification)
        response = self.service.release_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-RELEASE",
            hold_ids=[hold["data"]["holds"][0]["hold_id"]],
            approval_id=approval_id,
            verification_id=verification.verification_id,
            idempotency_key="release",
        )
        self.assertFalse(response["ok"])
        self.assertEqual("APPROVAL_INVALID", response["error"]["code"])
        current = self.store.list_sales_holds(incident_id=self.case.incident_id)[0]
        self.assertEqual("active", current["status"])

    def test_sales_hold_release_rejects_a_stale_release_guard(self) -> None:
        verification = Verification(
            verification_id="VER-STALE-RELEASE-GUARD",
            subject="release_guard",
            method="test",
            expected_condition={"safe": True},
            observed_value={"released_batch_holds": {"BATCH-S03-DAIRY-001": "active"}},
            evidence_ids=["EV-STALE"],
            result=VerificationResult.PASSED,
            verifier="Auditor",
            verified_at=self.store.now(),
        )
        self.incidents.record_verification(self.case.incident_id, verification)
        self.store.advance_time(minutes=1)
        hold = self.service.apply_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-LATE-HOLD",
            store_id="S03",
            batch_ids=["BATCH-S03-DAIRY-001"],
            reason="containment after verification",
            idempotency_key="late-hold",
        )
        approval_id = self._approved_action(
            action_id="ACT-STALE-RELEASE",
            action_type="release_sales_hold",
        )
        response = self.service.release_sales_hold(
            incident_id=self.case.incident_id,
            action_id="ACT-STALE-RELEASE",
            hold_ids=[hold["data"]["holds"][0]["hold_id"]],
            approval_id=approval_id,
            verification_id=verification.verification_id,
            idempotency_key="stale-release",
        )
        self.assertFalse(response["ok"])
        self.assertEqual("APPROVAL_INVALID", response["error"]["code"])
        self.assertIn("stale", response["error"]["message"])

    def test_http_boundary_rejects_non_object_and_oversized_requests(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), MCPHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = self._post(server.server_port, b"[]")
            self.assertEqual(400, status)
            self.assertEqual(-32600, json.loads(body)["error"]["code"])

            oversized = b"x" * (MAX_REQUEST_BYTES + 1)
            status, body = self._post(server.server_port, oversized)
            self.assertEqual(400, status)
            self.assertEqual(-32700, json.loads(body)["error"]["code"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_shared_http_token_cannot_authorize_a_state_change(self) -> None:
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "apply_sales_hold",
                    "arguments": {
                        "incident_id": self.case.incident_id,
                        "action_id": "ACT-SHARED-TOKEN",
                        "store_id": "S03",
                        "batch_ids": ["BATCH-S03-DAIRY-001"],
                        "reason": "must not execute",
                        "idempotency_key": "shared-token-write",
                    },
                },
            }
        ).encode("utf-8")
        with patch.dict(
            "os.environ",
            {"MCP_TOKEN": "shared-secret", "MCP_ACTOR_TOKENS_JSON": ""},
        ):
            server = ThreadingHTTPServer(("127.0.0.1", 0), MCPHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, body = self._post(server.server_port, payload, token="shared-secret")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        self.assertEqual(200, status)
        wrapped = json.loads(body)["result"]
        self.assertTrue(wrapped["isError"])
        result = json.loads(wrapped["content"][0]["text"])
        self.assertEqual("FORBIDDEN", result["error"]["code"])

    def test_non_loopback_server_requires_valid_auth_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "without authentication"):
                _validate_server_auth("0.0.0.0")
            _validate_server_auth("127.0.0.1")
        with patch.dict(
            "os.environ",
            {"MCP_ACTOR_TOKENS_JSON": '{"token":"UnknownRole"}'},
            clear=True,
        ):
            with self.assertRaisesRegex(SystemExit, "declared actors"):
                _validate_server_auth("0.0.0.0")

    def test_runtime_tool_schema_rejects_missing_and_non_object_arguments(self) -> None:
        missing = tool_call(
            "apply_sales_hold",
            {"incident_id": self.case.incident_id},
            service=self.service,
        )
        non_object = tool_call("apply_sales_hold", [], service=self.service)
        for wrapped in (missing, non_object):
            self.assertTrue(wrapped["isError"])
            result = json.loads(wrapped["content"][0]["text"])
            self.assertEqual("INVALID_ARGUMENT", result["error"]["code"])

        wrong_role = tool_call(
            "query_workorder",
            {"incident_id": self.case.incident_id},
            actor="Diagnoser",
            service=self.service,
        )
        self.assertTrue(wrong_role["isError"])
        result = json.loads(wrong_role["content"][0]["text"])
        self.assertEqual("FORBIDDEN", result["error"]["code"])

    def test_scenario_schema_and_seed_path_are_enforced_at_runtime(self) -> None:
        definition = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        definition["unexpected"] = True
        invalid_path = Path(self.temporary.name) / "invalid.json"
        invalid_path.write_text(json.dumps(definition), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected property"):
            ScenarioEngine(self.store, invalid_path)

        definition.pop("unexpected")
        definition["seed_path"] = "../../outside.json"
        scenario_dir = Path(self.temporary.name) / "scenarios"
        scenario_dir.mkdir()
        escaping_path = scenario_dir / "escaping.json"
        escaping_path.write_text(json.dumps(definition), encoding="utf-8")
        engine = ScenarioEngine(self.store, escaping_path)
        with self.assertRaisesRegex(ValueError, "escapes"):
            engine.reset()

    def test_static_iot_fixture_uses_its_own_snapshot_anchor(self) -> None:
        result = query_device_series("FROST-S03", window_hours=24 * 14)
        self.assertFalse(result["degraded"])
        self.assertGreater(result["rows"][0]["count"], 0)

    def test_legacy_orchestrator_stops_after_second_failed_verification(self) -> None:
        orchestrator = Orchestrator()
        anomaly = {"type": "缺货", "store_id": "S05", "evidence": {}}
        orchestrator.sentry.detect = Mock(
            side_effect=lambda context: setattr(context, "anomalies", [anomaly])
        )
        orchestrator.diagnoser.diagnose = Mock()
        orchestrator.executor.handle = Mock()
        orchestrator.auditor.verify = Mock(return_value=False)

        result = orchestrator.run_task("ADVERSARIAL-VERIFY", scope={"store_ids": ["S05"]})
        self.assertEqual("failed", result["result"])
        self.assertEqual("failed", orchestrator.bus.get("ADVERSARIAL-VERIFY").state)
        self.assertEqual(2, orchestrator.auditor.verify.call_count)

    def test_legacy_orchestrator_preserves_original_exception(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.sentry.detect = Mock(side_effect=RuntimeError("original failure"))
        with self.assertRaisesRegex(RuntimeError, "original failure"):
            orchestrator.run_task("ADVERSARIAL-ERROR", scope={})
        self.assertEqual("failed", orchestrator.bus.get("ADVERSARIAL-ERROR").state)

    def _approved_action(
        self,
        *,
        action_id: str,
        action_type: str,
        amount: float | None = None,
        disposition: str | None = None,
    ) -> str:
        created = self.service.create_approval(
            incident_id=self.case.incident_id,
            action_id=action_id,
            subject=f"approve {action_id}",
            requested_action_type=action_type,
            amount=amount,
            disposition=disposition,
            timeout_minutes=30,
            idempotency_key=f"{action_id}:approval",
        )
        self.assertTrue(created["ok"], created)
        approval_id = created["data"]["approval_id"]
        decided = self.service.decide_approval(
            approval_id=approval_id,
            decision="approved",
            reason="test approval",
            idempotency_key=f"{action_id}:decision",
            actor="Human",
        )
        self.assertTrue(decided["ok"], decided)
        return approval_id

    @staticmethod
    def _post(port: int, payload: bytes, *, token: str | None = None) -> tuple[int, str]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            connection.request(
                "POST",
                "/mcp",
                body=payload,
                headers=headers,
            )
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
