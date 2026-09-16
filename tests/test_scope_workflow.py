from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta

from dianxun.context_bus import ContextVersionConflict
from dianxun.domain import WorkOrderStatus
from dianxun.runtime import SCOPE_MUTATIONS, RuntimePrincipal
from tests import test_worker_runtime as fixture


class ScopeWorkflowTests(unittest.TestCase):
    setUp = fixture.WorkerRuntimeTests.setUp
    restart_runtime = fixture.WorkerRuntimeTests.restart_runtime
    snapshot = fixture.WorkerRuntimeTests.snapshot
    assign = fixture.WorkerRuntimeTests.assign
    tool = fixture.WorkerRuntimeTests.tool
    prepare_containment = fixture.WorkerRuntimeTests.prepare_containment
    prepare_diagnosis = fixture.WorkerRuntimeTests.prepare_diagnosis

    def initialize_runtime_fixture(self, path):
        fixture.WorkerRuntimeTests.initialize_runtime_fixture(self, path)
        self.store.migrate_scope_v2()

    def rpc(self, actor, operation, *, expect_error=False, **arguments):
        if "runtime_" + operation in SCOPE_MUTATIONS:
            case = self.store.get_incident(arguments.get("incident_id"))
            arguments.setdefault(
                "expected_scope_version", case.get("scope_version", 0) if case else 0
            )
        return fixture.WorkerRuntimeTests.rpc(
            self, actor, operation, expect_error=expect_error, **arguments
        )

    def revise(self, changes, change_id="split"):
        runtime = self.server.runtime_service
        human = RuntimePrincipal("Human", "human", "demo", "S03")
        runtime.principals[human.worker_id] = human
        snapshot = self.snapshot()
        return runtime.call(
            "runtime_revise_scope",
            {
                "incident_id": self.incident,
                "expected_versions": {
                    self.incident: {
                        "scope_version": snapshot["scope_version"],
                        "context_version": snapshot["context"]["version"],
                    }
                },
                "change_id": change_id,
                "source_ref": "synthetic:wms:" + change_id,
                "changes": changes,
            },
            human,
        )

    def execute_goods(self, lease):
        version = self.snapshot()["scope_version"]
        for batch in self.store.list_batches(
            batch_ids=self.snapshot()["incident"]["affected_batches"]
        ):
            if batch["disposition"] == "disposed":
                continue
            action = f"dispose:{batch['batch_id']}:{version}"
            approval = self.tool(
                lease,
                "create_approval",
                action_id=action,
                subject="dispose",
                requested_action_type="apply_batch_disposition",
                disposition="disposed",
                target_batch_ids=[batch["batch_id"]],
                idempotency_key=action + ":approval",
            )
            approval_id = approval["data"]["approval_id"]
            result = self.mcp.decide_approval(
                approval_id=approval_id,
                decision="approved",
                reason="fixture",
                actor="Human",
                expected_scope_version=version,
                idempotency_key=action + ":decision",
            )
            self.assertTrue(result["ok"], result)
            self.tool(
                lease,
                "apply_batch_disposition",
                action_id=action,
                batch_ids=[batch["batch_id"]],
                disposition="disposed",
                approval_id=approval_id,
                idempotency_key=action,
            )
            result = self.mcp.record_manual_evidence(
                incident_id=self.incident,
                action_id=action,
                evidence_type="disposition_receipt",
                observed_at=self.store.now(),
                note="synthetic independent receipt",
                actor="Human",
                expected_scope_version=version,
                idempotency_key=action + ":receipt",
                metadata={
                    "batch_id": batch["batch_id"],
                    "quantity": batch["quantity"],
                    "disposition": "disposed",
                    "source_location": batch["device_id"],
                    "receipt_ref": "synthetic:" + action,
                    "executor_id": "operator",
                    "confirmed_by": "witness",
                    "disposal_method": "destruction",
                    "destroyed": True,
                },
            )
            self.assertTrue(result["ok"], result)

    def finish_stages(self):
        for role in ("Auditor", "Executor", "Auditor", "Auditor"):
            lease = self.assign(role)
            result = self.rpc(role, "complete", **lease)
            self.assertTrue(result["completed"], result)
        self.assertEqual("CLOSED", self.snapshot()["incident"]["incident_status"])

    def test_split_then_add_preserves_completed_effects_and_closes_current_scope(self):
        diagnose = self.prepare_diagnosis()
        self.assertTrue(self.rpc("Diagnoser", "complete", **diagnose)["completed"])
        execute = self.assign("Executor")
        self.tool(
            execute,
            "create_workorder",
            action_id="repair",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor",
            budget=100,
            idempotency_key="repair",
        )
        parent = self.store.list_batches(batch_ids=self.snapshot()["incident"]["affected_batches"])[
            0
        ]
        self.revise(
            [
                {
                    "op": "split",
                    "batch_id": parent["batch_id"],
                    "children": [
                        {"batch_id": "C1", "quantity": 1},
                        {"batch_id": "C2", "quantity": parent["quantity"] - 1},
                    ],
                }
            ]
        )
        before_replay = self.snapshot()["context"]
        replay = self.rpc(
            "Executor",
            "tool",
            **execute,
            expected_scope_version=1,
            tool="create_workorder",
            arguments={
                "action_id": "repair",
                "store_id": "S03",
                "device_id": "FROST-S03",
                "fault": "compressor",
                "budget": 100,
                "idempotency_key": "repair",
            },
        )
        self.assertTrue(json.loads(replay["content"][0]["text"])["data"]["historical_replay"])
        self.assertEqual(before_replay, self.snapshot()["context"])
        self.rpc("Executor", "complete", **execute, expect_error=True)
        diagnose = self.prepare_diagnosis_v2("hold:split")
        self.assertTrue(self.rpc("Diagnoser", "complete", **diagnose)["completed"])
        execute = self.assign("Executor")
        self.execute_goods(execute)
        original_actions = self.store.list_actions(incident_id=self.incident)
        batch = {
            key: parent[key]
            for key in (
                "sku_id",
                "product_name",
                "device_id",
                "storage_min_c",
                "storage_max_c",
                "policy_ref",
            )
        }
        batch.update(batch_id="C3", quantity=3)
        self.revise([{"op": "add", "batch": batch}], "add-C3")
        self.restart_runtime()
        diagnose = self.prepare_diagnosis_v2("hold:add")
        self.assertTrue(self.rpc("Diagnoser", "complete", **diagnose)["completed"])
        execute = self.assign("Executor")
        self.execute_goods(execute)
        self.store.advance_time(minutes=5)
        workorder = self.store.list_workorders(incident_id=self.incident)[0]
        self.store.set_workorder_status(
            workorder["workorder_id"],
            status=WorkOrderStatus.DONE,
            completion_evidence={"synthetic_receipt": True},
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
        self.store.advance_time(minutes=2)
        self.assertTrue(self.rpc("Executor", "complete", **execute)["completed"])
        self.finish_stages()
        self.assertEqual(1, len(self.store.list_workorders(incident_id=self.incident)))
        after = {a["action_id"]: a for a in self.store.list_actions(incident_id=self.incident)}
        for original in original_actions:
            self.assertEqual(original, after[original["action_id"]])
        self.assertEqual(3, self.snapshot()["scope_version"])
        closed = self.store.get_incident(self.incident)
        linked = self.rpc(
            "Orchestrator",
            "open",
            incident_id="LINKED",
            device_id="FROST-S03",
            previous_incident_id=self.incident,
            source_ref="synthetic:new-exposure",
        )
        self.assertEqual(1, linked["scope_version"])
        self.assertEqual(
            self.incident, linked["context"]["recovery"]["previous_incident"]["incident_id"]
        )
        self.assertEqual(closed, self.store.get_incident(self.incident))

    def test_unexplained_inventory_blocks_auditor_until_human_reconciles(self):
        from dianxun.skills.outcome_verify import outcome_verify

        runtime = self.server.runtime_service
        case = self.snapshot()["incident"]
        with self.store.transaction() as conn:
            conn.execute(
                "UPDATE inventory_batches SET quantity=quantity+1 WHERE batch_id=?",
                (case["affected_batches"][0],),
            )
        with self.assertRaisesRegex(ValueError, "reconcile"):
            outcome_verify(
                incidents=runtime.incidents,
                service=self.mcp,
                incident_id=self.incident,
                policy=self.mcp.policy.policy,
                trace_id="test",
            )
        human = RuntimePrincipal("Human", "human", "demo", "S03")
        runtime.principals["human"] = human
        snapshot = self.snapshot()
        request = {
            "incident_id": self.incident,
            "expected_versions": {
                self.incident: {
                    "scope_version": 1,
                    "context_version": snapshot["context"]["version"],
                }
            },
            "change_id": "reconcile-1",
            "source_ref": "synthetic:wms-recount",
        }
        result = runtime.call("runtime_reconcile_scope", request, human)
        self.assertEqual({self.incident: 2}, result["versions"])
        replay = runtime.call("runtime_reconcile_scope", request, human)
        self.assertTrue(replay["historical_replay"])
        self.assertEqual("reconciled", self.snapshot()["incident"]["scope_state"])
        self.assertEqual("active", self.snapshot()["context"]["coordination_status"])

    def test_unknown_operation_is_not_reissued_after_revision(self):
        from dianxun.runtime_context import RuntimeContextBus

        bus = RuntimeContextBus(self.store, "demo")
        context = bus.get(self.incident, now=self.now)
        context.recovery["operations"]["unknown"] = {
            "tool": "create_workorder",
            "key": "lost-receipt",
            "action_id": "unknown",
            "device_id": "FROST-S03",
            "phase": "EXECUTE",
        }
        bus.commit(context, now=self.now)
        parent = self.store.list_batches(batch_ids=self.snapshot()["incident"]["affected_batches"])[
            0
        ]
        self.revise(
            [
                {
                    "op": "split",
                    "batch_id": parent["batch_id"],
                    "children": [
                        {"batch_id": "C1", "quantity": 1},
                        {"batch_id": "C2", "quantity": parent["quantity"] - 1},
                    ],
                }
            ]
        )
        lease = self.assign("Sentry")
        self.assertTrue(self.rpc("Sentry", "complete", **lease)["completed"])
        self.rpc("Executor", "poll")
        self.rpc(
            "Orchestrator",
            "assign",
            incident_id=self.incident,
            worker_id="executor",
            expected_version=self.snapshot()["context"]["version"],
            expect_error=True,
        )
        self.assertEqual([], self.store.list_workorders(incident_id=self.incident))

    def test_old_release_guard_cannot_release_unchanged_batch_after_scope_growth(self):
        from dianxun.domain import Verification, VerificationResult

        batch = self.store.list_batches(batch_ids=self.snapshot()["incident"]["affected_batches"])[
            0
        ]
        held = self.mcp.apply_sales_hold(
            incident_id=self.incident,
            action_id="hold",
            store_id="S03",
            batch_ids=[batch["batch_id"]],
            reason="test",
            expected_scope_version=1,
            idempotency_key="hold",
        )
        self.assertTrue(held["ok"], held)
        approval = self.mcp.create_approval(
            incident_id=self.incident,
            action_id="release",
            subject="release",
            requested_action_type="release_sales_hold",
            target_batch_ids=[batch["batch_id"]],
            expected_scope_version=1,
            idempotency_key="release:approval",
        )
        self.assertTrue(approval["ok"], approval)
        approval_id = approval["data"]["approval_id"]
        decided = self.mcp.decide_approval(
            approval_id=approval_id,
            decision="approved",
            reason="test",
            actor="Human",
            expected_scope_version=1,
            idempotency_key="release:decision",
        )
        self.assertTrue(decided["ok"], decided)
        verification = Verification(
            verification_id="guard",
            subject="release_guard",
            method="fixture",
            expected_condition={},
            observed_value={},
            evidence_ids=["fixture"],
            result=VerificationResult.PASSED,
            verifier="Auditor",
            verified_at=self.store.now(),
        )
        self.server.runtime_service.incidents.record_verification(self.incident, verification)
        new_batch = {
            key: batch[key]
            for key in (
                "sku_id",
                "product_name",
                "device_id",
                "storage_min_c",
                "storage_max_c",
                "policy_ref",
            )
        }
        new_batch.update(batch_id="NEW", quantity=1)
        self.revise([{"op": "add", "batch": new_batch}], "growth")
        response = self.mcp.release_sales_hold(
            incident_id=self.incident,
            action_id="release",
            hold_ids=[self.store.list_sales_holds(incident_id=self.incident)[0]["hold_id"]],
            approval_id=approval_id,
            verification_id=verification.verification_id,
            expected_scope_version=2,
            idempotency_key="release:execute",
        )
        self.assertFalse(response["ok"], response)
        self.assertIn("old scope", response["error"]["message"])
        self.assertEqual(
            "active", self.store.list_sales_holds(incident_id=self.incident)[0]["status"]
        )

    def prepare_diagnosis_v2(self, action):
        contain = self.prepare_containment()
        self.tool(
            contain,
            "apply_sales_hold",
            action_id=action,
            store_id="S03",
            batch_ids=self.snapshot()["containment_required"],
            reason="scope revision",
            idempotency_key=action,
        )
        self.assertTrue(self.rpc("Executor", "complete", **contain)["completed"])
        return self.assign("Diagnoser")

    def test_missing_version_and_stale_direct_mcp_write_are_fenced(self):
        runtime = self.server.runtime_service
        with self.assertRaisesRegex(ContextVersionConflict, "expected_scope_version"):
            runtime.call(
                "runtime_assign",
                {
                    "incident_id": self.incident,
                    "worker_id": "sentry",
                    "expected_version": self.snapshot()["context"]["version"],
                },
                self.principals["Orchestrator"],
            )
        result = self.mcp.apply_sales_hold(
            incident_id=self.incident,
            action_id="bad",
            store_id="S03",
            batch_ids=self.snapshot()["incident"]["affected_batches"],
            reason="bad",
            expected_scope_version=99,
            idempotency_key="bad",
        )
        self.assertFalse(result["ok"], result)
