from __future__ import annotations

import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from dianxun.context_bus import parse_timestamp
from dianxun.domain import WorkOrderStatus
from dianxun.runtime import RuntimeService
from dianxun.scheduler import RecoveryScheduler
from tests import test_worker_runtime as fixture


class RuntimeRecoveryTests(unittest.TestCase):
    # Reuse the real HTTP+SQLite fixture without discovering the base tests twice.
    setUp = fixture.WorkerRuntimeTests.setUp
    initialize_runtime_fixture = fixture.WorkerRuntimeTests.initialize_runtime_fixture
    restart_runtime = fixture.WorkerRuntimeTests.restart_runtime
    rpc = fixture.WorkerRuntimeTests.rpc
    snapshot = fixture.WorkerRuntimeTests.snapshot
    assign = fixture.WorkerRuntimeTests.assign
    tool = fixture.WorkerRuntimeTests.tool
    prepare_containment = fixture.WorkerRuntimeTests.prepare_containment
    prepare_diagnosis = fixture.WorkerRuntimeTests.prepare_diagnosis
    prepare_execution = fixture.WorkerRuntimeTests.prepare_execution

    @property
    def runtime(self):
        return self.server.runtime_service

    def tick(self):
        self.runtime.recovery.tick()

    def direct(self, principal, operation, **kwargs):
        return self.runtime.call("runtime_" + operation, kwargs, principal)

    def extra(self, role, name):
        principal = replace(self.principals[role], worker_id=name)
        self.principals[name] = principal
        self.runtime.principals[name] = principal
        self.direct(principal, "poll")
        return principal

    def current(self, stage):
        snapshot = self.snapshot()
        assignment = next(
            a for a in reversed(snapshot["context"]["assignments"]) if a["phase"] == stage
        )
        return {
            "incident_id": self.incident,
            "assignment_id": assignment["assignment_id"],
            "expected_version": snapshot["context"]["version"],
        }

    def test_heartbeats_and_repeated_progress_cannot_keep_attempt_alive(self):
        lease = self.assign("Sentry")
        for _ in range(2):
            self.now += timedelta(seconds=40)
            value = self.rpc("Sentry", "heartbeat", **lease)
            lease["expected_version"] = value["context_version"]
            progress = self.rpc("Sentry", "progress", **lease)
            self.assertFalse(progress["progress_accepted"])
        self.now += timedelta(seconds=11)
        self.rpc("Sentry", "heartbeat", **lease, expect_error=True)
        self.tick()
        state = self.snapshot()["context"]
        self.assertEqual("progress_timeout", state["assignments"][0]["error"])
        self.assertEqual({}, state["checkpoints"])

    def test_new_receipts_extend_progress_but_never_hard_deadline(self):
        lease = self.prepare_containment()
        deadline = self.snapshot()["context"]["assignments"][-1]["hard_deadline"]
        for index in range(1, 7):
            self.now += timedelta(seconds=45)
            value = self.rpc("Executor", "heartbeat", **lease)
            lease["expected_version"] = value["context_version"]
            # A persisted status change is progress; synthetic fixture only.
            self.store.append_device_reading(
                device_id="FROST-S03",
                temp_c=8 + index / 10,
                observed_at=self.store.now(),
                quality="good",
                source=f"fixture-{index}",
            )
            value = self.rpc("Executor", "progress", **lease)
            self.assertTrue(value["progress_accepted"])
            lease["expected_version"] = value["context_version"]
        self.now += timedelta(seconds=31)
        self.rpc("Executor", "complete", **lease, expect_error=True)
        self.tick()
        assignment = self.snapshot()["context"]["assignments"][-1]
        self.assertEqual(deadline, assignment["hard_deadline"])
        self.assertEqual("hard_timeout", assignment["error"])

    def test_expiry_uses_healthy_backup_and_fences_late_old_worker(self):
        old = self.assign("Sentry")
        backup = self.extra("Sentry", "sentry-backup")
        self.now += timedelta(seconds=61)
        self.tick()
        self.now += timedelta(seconds=10)
        self.direct(backup, "poll")
        self.tick()
        assignment = self.snapshot()["context"]["assignments"][-1]
        self.assertEqual(backup.worker_id, assignment["worker"])
        self.assertEqual(old["assignment_id"], assignment["predecessor_assignment_id"])
        self.rpc("Sentry", "complete", **old, expect_error=True)
        self.rpc("Sentry", "complete", **self.current("DETECT"), expect_error=True)
        self.assertTrue(self.direct(backup, "complete", **self.current("DETECT"))["completed"])

    def test_main_is_supervised_and_model_free_fallback_dispatches(self):
        self.rpc("Orchestrator", "poll")
        self.rpc("Sentry", "poll")
        self.tick()
        first = self.rpc("Orchestrator", "poll")["assignments"][0]
        self.assertEqual("ORCHESTRATE", first["assignment"]["phase"])
        self.now += timedelta(seconds=31)
        self.tick()
        self.assertEqual(
            "DETECT", self.rpc("Sentry", "poll")["assignments"][0]["assignment"]["phase"]
        )
        context = self.snapshot()["context"]
        self.assertEqual("expired", context["recovery"]["orchestration"][0]["status"])
        self.assertTrue(context["recovery"]["outbox"])
        self.rpc(
            "Orchestrator",
            "heartbeat",
            incident_id=self.incident,
            assignment_id=first["assignment"]["assignment_id"],
            expected_version=context["version"],
            expect_error=True,
        )

    def test_main_can_transfer_to_another_scoped_orchestrator(self):
        self.rpc("Orchestrator", "poll")
        backup = self.extra("Orchestrator", "z-main-backup")
        self.tick()
        self.now += timedelta(seconds=31)
        self.tick()
        work = self.direct(backup, "poll")["assignments"]
        self.assertEqual(1, len(work))
        self.assertEqual(2, work[0]["assignment"]["attempt"])
        self.rpc("Sentry", "poll")
        self.rpc(
            "Orchestrator",
            "assign",
            incident_id=self.incident,
            worker_id="sentry",
            expected_version=self.snapshot()["context"]["version"],
            expect_error=True,
        )
        self.direct(
            backup,
            "assign",
            incident_id=self.incident,
            worker_id="sentry",
            expected_version=self.snapshot()["context"]["version"],
        )
        # A long scheduler outage must not mislabel an unresponsive main as successful.
        incident = "INC-MAIN-BUDGET"
        self.rpc("Orchestrator", "open", incident_id=incident, device_id="FROST-S03")
        self.tick()
        self.now += timedelta(seconds=181)
        self.tick()
        state = self.rpc("Orchestrator", "snapshot", incident_id=incident)["context"]
        self.assertEqual("expired", state["recovery"]["orchestration"][-1]["status"])
        self.assertEqual("budget_exhausted", state["recovery"]["orchestration"][-1]["error"])

    def test_competing_schedulers_restart_and_capacity_have_one_successor(self):
        old = self.assign("Sentry")
        self.now += timedelta(seconds=61)
        self.tick()
        self.now += timedelta(seconds=31)
        self.rpc("Sentry", "poll")
        second = RuntimeService(self.mcp, self.principals.values(), clock=lambda: self.now)
        barrier = threading.Barrier(2)

        def sweep(service):
            barrier.wait(timeout=5)
            return service.recovery.tick()

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(sweep, service) for service in (self.runtime, second)]
            for future in futures:
                future.result(timeout=15)
        self.restart_runtime()
        self.tick()
        assignments = self.snapshot()["context"]["assignments"]
        self.assertEqual(
            1, sum(a["predecessor_assignment_id"] == old["assignment_id"] for a in assignments)
        )
        self.rpc("Orchestrator", "open", incident_id="INC-SECOND", device_id="FROST-S03")
        self.tick()
        self.assertEqual(1, len(self.rpc("Sentry", "poll")["assignments"]))

    def test_queue_total_budget_and_all_workers_offline_escalate_once(self):
        self.tick()
        context = self.snapshot()["context"]
        self.assertEqual("waiting_capacity", context["recovery"]["phases"]["DETECT"]["state"])
        deadline = context["recovery"]["phases"]["DETECT"]["deadline"]
        self.restart_runtime()
        self.now = parse_timestamp(deadline) + timedelta(seconds=1)
        self.tick()
        first = self.snapshot()["context"]
        self.tick()
        second = self.snapshot()["context"]
        self.assertEqual(first, second)
        self.assertEqual("manual_intervention", second["recovery"]["phases"]["DETECT"]["state"])
        self.assertEqual([], second["assignments"])

    def test_retry_limit_and_nonretryable_failure_never_skip_stage(self):
        self.assign("Sentry")
        for attempt in range(3):
            result = self.rpc("Sentry", "fail", **self.current("DETECT"), reason="transient")
            if attempt < 2:
                self.assertEqual("retry_wait", result["recovery"]["state"])
                self.now += timedelta(seconds=31)
                self.rpc("Sentry", "poll")
                self.tick()
        context = self.snapshot()["context"]
        self.assertEqual("attempts_exhausted", context["recovery"]["phases"]["DETECT"]["reason"])
        self.assertEqual(3, len(context["assignments"]))
        self.assertEqual({}, context["checkpoints"])
        self.rpc(
            "Orchestrator",
            "resume",
            incident_id=self.incident,
            expected_version=context["version"],
            stage="DETECT",
            reason="try again",
            expect_error=True,
        )

    def test_stale_source_escalates_without_fabricating_detection(self):
        lease = self.assign("Sentry")
        self.store.advance_time(minutes=30)
        value = self.rpc("Sentry", "complete", **lease)
        self.assertFalse(value["completed"])
        self.assertEqual("stale_evidence", value["recovery"]["reason"])
        self.assertEqual({}, self.snapshot()["context"]["checkpoints"])

    def test_approval_wait_releases_capacity_and_resumes_original_receipt(self):
        self.prepare_diagnosis()
        self.rpc("Diagnoser", "complete", **self.current("DIAGNOSE_DECIDE"))
        lease = self.assign("Executor")
        approval = self.tool(
            lease,
            "create_approval",
            action_id="waiting-action",
            subject="batch",
            requested_action_type="apply_batch_disposition",
            disposition="disposed",
            timeout_minutes=30,
            idempotency_key="approval-wait",
        )
        approval_id = approval["data"]["approval_id"]
        self.rpc("Executor", "wait", **lease, kind="approval", reference=approval_id)
        self.assertEqual([], self.rpc("Executor", "poll")["assignments"])
        self.now += timedelta(seconds=600)
        self.tick()
        self.assertEqual("waiting", self.snapshot()["context"]["assignments"][-1]["status"])
        self.mcp.decide_approval(
            approval_id=approval_id,
            decision="approved",
            actor="Human",
            idempotency_key="human-wait",
            reason="fixture",
        )
        self.rpc("Executor", "poll")
        self.tick()
        self.assertEqual(1, len(self.store.list_approvals(incident_id=self.incident)))
        self.assertEqual(
            "running", self.snapshot()["context"]["recovery"]["phases"]["EXECUTE"]["state"]
        )
        self.rpc(
            "Executor", "tool", **lease, tool="create_approval", arguments={}, expect_error=True
        )

    def test_unknown_receipt_blocks_retry_and_human_cannot_override_reconciliation(self):
        lease = self.prepare_containment()
        self.tool(
            lease,
            "apply_sales_hold",
            action_id="hold",
            store_id="S03",
            batch_ids=self.snapshot()["incident"]["affected_batches"],
            reason="fixture",
            idempotency_key="hold-unknown",
        )
        with self.store.transaction() as conn:
            conn.execute("DELETE FROM idempotency WHERE idempotency_key = ?", ("hold-unknown",))
        self.now += timedelta(seconds=61)
        self.tick()
        self.now += timedelta(seconds=31)
        self.rpc("Executor", "poll")
        self.tick()
        context = self.snapshot()["context"]
        self.assertEqual("unknown_outcome", context["recovery"]["phases"]["CONTAIN"]["reason"])
        self.assertEqual(2, len(self.store.list_sales_holds(incident_id=self.incident)))
        self.assertNotIn("CONTAIN", context["checkpoints"])

    def test_lost_workorder_response_reconciles_and_replay_is_idempotent(self):
        self.prepare_diagnosis()
        self.rpc("Diagnoser", "complete", **self.current("DIAGNOSE_DECIDE"))
        lease = self.assign("Executor")
        args = dict(
            action_id="repair-lost",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor",
            budget=80,
            idempotency_key="repair-key",
        )
        self.tool(lease, "create_workorder", **args)
        self.now += timedelta(seconds=61)
        self.tick()
        self.now += timedelta(seconds=31)
        self.rpc("Executor", "poll")
        self.restart_runtime()
        self.tick()
        fresh = self.current("EXECUTE")
        self.tool(fresh, "create_workorder", **args)
        self.assertEqual(1, len(self.store.list_workorders(incident_id=self.incident)))
        self.rpc(
            "Executor",
            "tool",
            **fresh,
            tool="create_workorder",
            arguments={**args, "idempotency_key": "wrong-new-key"},
            expect_error=True,
        )

    def test_late_tool_result_rolls_back_local_effects(self):
        lease = self.prepare_containment()
        original = self.mcp.apply_sales_hold

        def late(**kwargs):
            result = original(**kwargs)
            self.now += timedelta(seconds=301)
            return result

        with patch.object(self.mcp, "apply_sales_hold", side_effect=late):
            self.rpc(
                "Executor",
                "tool",
                **lease,
                tool="apply_sales_hold",
                arguments={
                    "action_id": "late",
                    "store_id": "S03",
                    "batch_ids": self.snapshot()["incident"]["affected_batches"],
                    "reason": "fixture",
                    "idempotency_key": "late-key",
                },
                expect_error=True,
            )
        self.assertEqual([], self.store.list_sales_holds(incident_id=self.incident))
        self.assertEqual([], self.store.list_actions(incident_id=self.incident))

    def test_emergency_evidence_and_scope_guards_then_merges_normal_chain(self):
        for seconds in (30, 0):
            self.store.append_device_reading(
                device_id="FROST-S03",
                temp_c=9,
                observed_at=(
                    parse_timestamp(self.store.now()) - timedelta(seconds=seconds)
                ).isoformat(),
                quality="good",
                source="fresh-emergency-fixture",
            )
        arguments = {
            "incident_id": self.incident,
            "expected_version": self.snapshot()["context"]["version"],
        }
        self.rpc("Orchestrator", "emergency", **arguments, expect_error=True)
        with patch.dict("os.environ", {"DIANXUN_EMERGENCY_CONTAINMENT": "1"}):
            self.rpc("Executor", "emergency", **arguments, expect_error=True)
            self.rpc("Orchestrator", "emergency", **arguments)
        self.rpc("Executor", "poll")
        self.tick()
        lease = self.current("EMERGENCY_CONTAIN")
        self.tool(
            lease,
            "apply_sales_hold",
            action_id="emergency-hold",
            store_id="S03",
            batch_ids=self.snapshot()["incident"]["affected_batches"],
            reason="fresh risk",
            idempotency_key="emergency-key",
        )
        self.assertTrue(self.rpc("Executor", "complete", **lease)["completed"])
        self.assertEqual({}, self.snapshot()["context"]["checkpoints"])
        self.assertTrue(self.rpc("Sentry", "complete", **self.assign("Sentry"))["completed"])
        self.assertEqual([], self.snapshot()["containment_required"])
        self.assertTrue(self.rpc("Executor", "complete", **self.assign("Executor"))["completed"])
        self.assertEqual(1, len(self.store.list_actions(incident_id=self.incident)))

    def test_scheduler_outage_marks_health_and_blocks_dangerous_calls(self):
        scheduler = RecoveryScheduler(self.runtime)
        self.runtime.scheduler = scheduler
        self.assertTrue(scheduler.sweep())
        with patch.object(self.runtime.recovery, "tick", side_effect=RuntimeError("db offline")):
            self.assertFalse(scheduler.sweep())
        self.assertFalse(scheduler.healthy())
        self.assertIn("dianxun_recovery_scan_failures_total 1", scheduler.metrics())
        self.rpc(
            "Orchestrator",
            "assign",
            incident_id=self.incident,
            worker_id="sentry",
            expected_version=self.snapshot()["context"]["version"],
            expect_error=True,
        )
        self.assertTrue(scheduler.sweep())

    def test_legacy_upgrade_initializes_once_and_expired_context_remains_observable(self):
        lease = self.assign("Sentry")
        with self.store.transaction() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_contexts WHERE task_id = ?", (self.incident,)
            ).fetchone()
            raw = json.loads(row["payload_json"])
            del raw["recovery"]
            for assignment in raw["assignments"]:
                for field in (
                    "hard_deadline",
                    "progress_deadline",
                    "last_progress_at",
                    "progress_fingerprint",
                ):
                    del assignment[field]
            conn.execute(
                "UPDATE runtime_contexts SET payload_json = ? WHERE task_id = ?",
                (json.dumps(raw), self.incident),
            )
        self.now += timedelta(seconds=100)
        self.restart_runtime()
        first = self.snapshot()["context"]
        self.restart_runtime()
        self.assertEqual(first, self.snapshot()["context"])
        self.rpc("Sentry", "complete", **lease, expect_error=True)
        self.now += timedelta(days=2)
        self.tick()
        context = self.snapshot()["context"]
        self.assertEqual("budget_exhausted", context["recovery"]["phases"]["DETECT"]["reason"])
        self.assertEqual(first["expires_at"], context["expires_at"])

    def test_notification_lease_dedup_retry_and_cross_scope_rejection(self):
        lease = self.assign("Sentry")
        self.rpc("Sentry", "fail", **lease, reason="forbidden")
        human = replace(self.principals["Orchestrator"], actor="Human", worker_id="human-fixture")
        self.runtime.principals[human.worker_id] = human
        self.rpc("Orchestrator", "notifications", incident_id=self.incident, expect_error=True)
        claimed = self.direct(human, "notifications", incident_id=self.incident)["notifications"]
        self.assertEqual(1, len(claimed))
        self.assertEqual(
            [], self.direct(human, "notifications", incident_id=self.incident)["notifications"]
        )
        item = claimed[0]
        self.direct(
            human,
            "notification_result",
            incident_id=self.incident,
            notification_id=item["id"],
            attempt=item["attempts"],
            delivered=False,
            receipt="fixture transport unavailable",
        )
        self.now += timedelta(seconds=21)
        retry = self.direct(human, "notifications", incident_id=self.incident)["notifications"][0]
        self.assertEqual(item["id"], retry["id"])
        with self.assertRaises(PermissionError):
            self.direct(
                human,
                "notification_result",
                incident_id=self.incident,
                notification_id=item["id"],
                attempt=item["attempts"],
                delivered=True,
                receipt="late fixture",
            )
        self.direct(
            human,
            "notification_result",
            incident_id=self.incident,
            notification_id=item["id"],
            attempt=retry["attempts"],
            delivered=True,
            receipt="fixture console acknowledgement",
        )
        foreign = replace(human, worker_id="foreign-human", store_id="S04")
        self.runtime.principals[foreign.worker_id] = foreign
        with self.assertRaises(PermissionError):
            self.direct(foreign, "notifications", incident_id=self.incident)

    def test_repair_wait_uses_actual_workorder_status_and_preserves_reference(self):
        self.prepare_diagnosis()
        self.rpc("Diagnoser", "complete", **self.current("DIAGNOSE_DECIDE"))
        lease = self.assign("Executor")
        result = self.tool(
            lease,
            "create_workorder",
            action_id="repair-wait",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor",
            budget=80,
            idempotency_key="repair-wait-key",
        )
        reference = result["data"]["workorder_id"]
        self.rpc("Executor", "wait", **lease, kind="repair", reference=reference)
        self.now += timedelta(seconds=600)
        self.tick()
        self.assertEqual("waiting", self.snapshot()["context"]["assignments"][-1]["status"])
        self.store.set_workorder_status(
            reference, status=WorkOrderStatus.DONE, completion_evidence={"fixture_receipt": True}
        )
        self.rpc("Executor", "poll")
        self.tick()
        self.assertEqual(1, len(self.store.list_workorders(incident_id=self.incident)))
        self.assertEqual("assigned", self.snapshot()["context"]["assignments"][-1]["status"])

    def test_approval_deadline_escalates_without_recreating_approval(self):
        self.prepare_diagnosis()
        self.rpc("Diagnoser", "complete", **self.current("DIAGNOSE_DECIDE"))
        lease = self.assign("Executor")
        result = self.tool(
            lease,
            "create_approval",
            action_id="short-wait",
            subject="batch",
            requested_action_type="apply_batch_disposition",
            disposition="disposed",
            timeout_minutes=1,
            idempotency_key="short-wait-key",
        )
        self.rpc(
            "Executor", "wait", **lease, kind="approval", reference=result["data"]["approval_id"]
        )
        self.now += timedelta(seconds=61)
        self.tick()
        phase = self.snapshot()["context"]["recovery"]["phases"]["EXECUTE"]
        self.assertEqual("business_wait_timeout", phase["reason"])
        self.assertEqual(1, len(self.store.list_approvals(incident_id=self.incident)))
        self.assertNotIn("EXECUTE", self.snapshot()["context"]["checkpoints"])

    def test_human_recovery_is_scoped_audited_and_keeps_original_budget(self):
        lease = self.assign("Sentry")
        self.rpc("Sentry", "fail", **lease, reason="invalid_input")
        human = replace(self.principals["Orchestrator"], actor="Human", worker_id="operator")
        self.runtime.principals[human.worker_id] = human
        before = self.snapshot()["context"]
        result = self.direct(
            human,
            "resume",
            incident_id=self.incident,
            expected_version=before["version"],
            stage="DETECT",
            reason="fixture configuration corrected",
        )
        phase = result["context"]["recovery"]["phases"]["DETECT"]
        self.assertEqual(human.worker_id, phase["resumed_by"])
        self.assertEqual(before["recovery"]["phases"]["DETECT"]["deadline"], phase["deadline"])
        self.tick()
        self.assertTrue(self.rpc("Sentry", "complete", **self.current("DETECT"))["completed"])

    def test_background_scanner_dispatches_without_an_http_reassign(self):
        self.rpc("Sentry", "poll")
        scheduler = RecoveryScheduler(self.runtime, interval=0.05)
        finished = threading.Event()
        original = self.runtime.recovery.tick

        def tick():
            result = original()
            finished.set()
            return result

        with patch.object(self.runtime.recovery, "tick", side_effect=tick):
            scheduler.start()
            try:
                self.assertTrue(finished.wait(5))
            finally:
                scheduler.stop()
        self.assertEqual(1, len(self.rpc("Sentry", "poll")["assignments"]))

    def test_expiring_old_evidence_is_not_reported_as_new_progress(self):
        lease = self.assign("Sentry")
        self.store.advance_time(minutes=30)
        self.assertFalse(self.rpc("Sentry", "progress", **lease)["progress_accepted"])


if __name__ == "__main__":
    unittest.main()
