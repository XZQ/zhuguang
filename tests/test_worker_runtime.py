from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from dianxun.domain import IncidentStatus, PolicyEngine, WorkOrderStatus
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, MCPService
from dianxun.mcp.server import MCPHandler
from dianxun.runtime import RuntimeService, load_principals
from dianxun.scenarios import ScenarioEngine
from dianxun.state import StateStore

ROOT = Path(__file__).resolve().parents[1]


class WorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = StateStore(Path(temporary.name) / "runtime.db")
        self.store.initialize_from_file(ROOT / "demo/state/seed.json")
        self.mcp = MCPService(self.store, PolicyEngine(DEFAULT_POLICY_PATH))
        self.scenario = ScenarioEngine(
            self.store,
            ROOT / "demo/state/scenarios/coldchain-compressor-failure.json",
            service=self.mcp,
        )
        self.scenario.reset()
        identities = {
            role: {"actor": role, "worker_id": role.lower(), "tenant_id": "demo", "store_id": "S03"}
            for role in ("Orchestrator", "Sentry", "Diagnoser", "Executor", "Auditor")
        }
        identities["other-store"] = {
            **identities["Sentry"],
            "worker_id": "other",
            "store_id": "S04",
        }
        self.principals = load_principals(json.dumps(identities))
        env = patch.dict("os.environ", {"DIANXUN_RUNTIME_TOKENS_JSON": json.dumps(identities)})
        env.start()
        self.addCleanup(env.stop)
        self.now = datetime(2026, 9, 7, tzinfo=UTC)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), MCPHandler)
        self.restart_runtime()
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.incident = "INC-RUNTIME"
        self.rpc("Orchestrator", "open", incident_id=self.incident, device_id="FROST-S03")

    def restart_runtime(self):
        # Fresh service and context instances; persisted state is the only recovery source.
        self.server.runtime_service = RuntimeService(
            self.mcp, self.principals.values(), clock=lambda: self.now
        )

    def rpc(self, actor, operation, *, expect_error=False, **arguments):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        self.addCleanup(connection.close)
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": f"runtime_{operation}", "arguments": arguments},
        }
        connection.request(
            "POST", "/runtime", json.dumps(body), {"Authorization": f"Bearer {actor}"}
        )
        response = connection.getresponse()
        self.assertEqual(200, response.status)
        result = json.loads(response.read())["result"]
        self.assertEqual(expect_error, result["isError"], result)
        return json.loads(result["content"][0]["text"])

    def snapshot(self):
        return self.rpc("Orchestrator", "snapshot", incident_id=self.incident)

    def assign(self, role):
        value = self.rpc(
            "Orchestrator",
            "assign",
            incident_id=self.incident,
            worker_id=role.lower(),
            expected_version=self.snapshot()["context"]["version"],
        )
        return {
            "incident_id": self.incident,
            "assignment_id": value["assignment"]["assignment_id"],
            "expected_version": value["context_version"],
        }

    def tool(self, lease, name, **arguments):
        value = self.rpc("Executor", "tool", **lease, tool=name, arguments=arguments)
        self.assertFalse(value["isError"], value)
        return json.loads(value["content"][0]["text"])

    def prepare_execution(self):
        detect = self.assign("Sentry")
        self.assertTrue(self.rpc("Sentry", "complete", **detect)["completed"])
        contain = self.assign("Executor")
        self.tool(
            contain,
            "apply_sales_hold",
            action_id="hold",
            store_id="S03",
            batch_ids=self.snapshot()["incident"]["affected_batches"],
            reason="coldchain",
            idempotency_key="runtime:hold",
        )
        self.assertTrue(self.rpc("Executor", "complete", **contain)["completed"])
        diagnose = self.assign("Diagnoser")
        self.assertTrue(self.rpc("Diagnoser", "complete", **diagnose)["completed"])
        execute = self.assign("Executor")
        self.tool(
            execute,
            "create_workorder",
            action_id="repair",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor_failure",
            budget=100,
            idempotency_key="runtime:repair",
        )
        for index, batch_id in enumerate(self.snapshot()["incident"]["affected_batches"]):
            action_id = f"batch-{index}"
            approval = self.tool(
                execute,
                "create_approval",
                action_id=action_id,
                subject="dispose unsafe goods",
                requested_action_type="apply_batch_disposition",
                disposition="disposed",
                timeout_minutes=30,
                idempotency_key=f"approval:{index}",
            )
            # Trusted test fixture simulates a real human approval; no Worker can do this.
            self.mcp.decide_approval(
                approval_id=approval["data"]["approval_id"],
                decision="approved",
                actor="Human",
                idempotency_key=f"human:{index}",
                reason="test fixture",
            )
            self.tool(
                execute,
                "apply_batch_disposition",
                action_id=action_id,
                batch_ids=[batch_id],
                disposition="disposed",
                approval_id=approval["data"]["approval_id"],
                idempotency_key=f"dispose:{index}",
            )
        self.store.advance_time(minutes=5)
        workorder = self.store.list_workorders(incident_id=self.incident)[0]
        self.store.set_workorder_status(
            workorder["workorder_id"],
            status=WorkOrderStatus.DONE,
            completion_evidence={"synthetic_vendor_receipt": True},
        )
        self.store.set_device_state("FROST-S03", health_state="normal", compressor_state="running")
        for minute in range(3):
            self.store.append_device_reading(
                device_id="FROST-S03",
                temp_c=4.8,
                observed_at=(
                    datetime.fromisoformat(self.store.now()) + timedelta(minutes=minute)
                ).isoformat(),
                quality="good",
                source="synthetic-recovery",
            )
        self.assertTrue(self.rpc("Executor", "complete", **execute)["completed"])

    def test_real_http_workflow_recovers_after_restart_and_closes_independently(self):
        self.prepare_execution()
        self.restart_runtime()
        self.assertEqual("VERIFY", self.snapshot()["remaining_stages"][0])
        for role in ("Auditor", "Executor", "Auditor", "Auditor"):
            lease = self.assign(role)
            result = self.rpc(role, "complete", **lease)
            self.assertTrue(result["completed"], result)
            self.restart_runtime()
            self.assertTrue(self.rpc(role, "complete", **lease)["replayed"])
        snapshot = self.snapshot()
        self.assertEqual(IncidentStatus.CLOSED, snapshot["incident"]["incident_status"])
        self.assertEqual([], snapshot["remaining_stages"])
        self.assertEqual(1, len(self.store.list_workorders(incident_id=self.incident)))

    def test_partial_verification_has_no_success_checkpoint_and_can_retry(self):
        self.prepare_execution()
        lease = self.assign("Auditor")
        self.store.inject_tool_failure(
            tool_name="query_workorder",
            remaining_calls=1,
            error_code="UPSTREAM_PARTIAL",
            message="partial fixture",
        )
        result = self.rpc("Auditor", "complete", **lease)
        self.assertFalse(result["completed"])
        self.assertNotIn("VERIFY", self.snapshot()["context"]["checkpoints"])
        self.restart_runtime()
        self.assertTrue(self.rpc("Auditor", "complete", **lease)["completed"])

    def test_scope_actor_lease_and_claims_cannot_be_forged(self):
        self.rpc("other-store", "snapshot", incident_id=self.incident, expect_error=True)
        lease = self.assign("Sentry")
        self.rpc("Executor", "complete", **lease, expect_error=True)
        self.rpc("Sentry", "complete", **lease, verified=True, expect_error=True)
        self.now += timedelta(seconds=61)
        self.rpc("Sentry", "complete", **lease, expect_error=True)

        successor = self.rpc("Orchestrator", "reassign", **lease)
        self.assertEqual(2, successor["assignment"]["attempt"])
        self.assertEqual(
            lease["assignment_id"], successor["assignment"]["predecessor_assignment_id"]
        )
        self.rpc("Sentry", "complete", **lease, expect_error=True)

    def test_checkpoint_failure_rolls_back_domain_transition(self):
        from dianxun.coordination import ContextCoordinator

        self.prepare_execution()
        lease = self.assign("Auditor")
        before = self.snapshot()
        with patch.object(
            ContextCoordinator, "complete", side_effect=ValueError("checkpoint failure")
        ):
            self.rpc("Auditor", "complete", **lease, expect_error=True)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
