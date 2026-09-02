from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dianxun.context_bus import (
    ContextBus,
    ContextExpired,
    ContextTenantMismatch,
    ContextVersionConflict,
)
from dianxun.coordination import (
    ActiveLeaseError,
    AssignmentStateError,
    ContextCoordinator,
    LeaseExpiredError,
    WorkerMismatchError,
)


class ContextLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path = Path(self.temp_dir.name) / "coordination.db"
        self.start = datetime(2026, 9, 2, 1, 0, tzinfo=UTC)

    def bus(self, tenant_id: str = "tenant-a") -> ContextBus:
        return ContextBus(tenant_id=tenant_id, database_path=self.database_path)

    def test_persistent_context_database_uses_wal(self) -> None:
        self.bus()
        with closing(sqlite3.connect(self.database_path)) as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual("wal", journal_mode)

    def test_sqlite_restart_recovers_checkpoint_and_skips_completed_phase(self) -> None:
        first_bus = self.bus()
        first_bus.create("task-1", "trace-1", ttl_seconds=600, now=self.start)
        coordinator = ContextCoordinator(first_bus)
        with self.assertRaises(AssignmentStateError):
            coordinator.assign(
                "task-1", "DIAGNOSE_DECIDE", "Diagnoser", lease_seconds=30, now=self.start
            )
        assignment = coordinator.assign(
            "task-1", "DETECT_CONTAIN", "Sentry", lease_seconds=30, now=self.start
        )
        coordinator.complete(
            "task-1",
            assignment.assignment_id,
            "Sentry",
            evidence_refs=["evidence://temperature/1"],
            output_ref="artifact://detect/1",
            now=self.start + timedelta(seconds=5),
        )

        restarted_bus = self.bus()
        restarted = restarted_bus.get("task-1", now=self.start + timedelta(seconds=6))
        self.assertEqual(3, restarted.version)
        self.assertEqual("succeeded", restarted.assignments[0].status)
        self.assertEqual(
            ["evidence://temperature/1"],
            restarted.checkpoints["DETECT_CONTAIN"].evidence_refs,
        )
        self.assertEqual(3, restarted.checkpoints["DETECT_CONTAIN"].context_version)
        self.assertEqual(
            ["DIAGNOSE_DECIDE", "EXECUTE", "VERIFY", "LEARN"],
            ContextCoordinator(restarted_bus).resume_plan(
                "task-1", now=self.start + timedelta(seconds=6)
            ),
        )

    def test_stale_writer_cannot_overwrite_newer_context(self) -> None:
        first_bus = self.bus()
        first_bus.create("task-1", "trace-1", now=self.start)
        second_bus = self.bus()
        first_writer = first_bus.get("task-1", now=self.start)
        stale_writer = second_bus.get("task-1", now=self.start)
        first_writer.scope["owner"] = "first"
        first_bus.commit(first_writer, now=self.start + timedelta(seconds=1))
        stale_writer.scope["owner"] = "stale"
        with self.assertRaises(ContextVersionConflict):
            second_bus.commit(stale_writer, now=self.start + timedelta(seconds=2))
        self.assertEqual("first", first_bus.get("task-1", now=self.start).scope["owner"])

    def test_tenant_bound_bus_cannot_read_or_write_another_tenant(self) -> None:
        tenant_a = self.bus("tenant-a")
        context_a = tenant_a.create("shared-task", "trace-a", now=self.start)
        tenant_b = self.bus("tenant-b")
        with self.assertRaises(KeyError):
            tenant_b.get("shared-task", now=self.start)
        with self.assertRaises(ContextTenantMismatch):
            tenant_b.commit(context_a, now=self.start)

        context_b = tenant_b.create("shared-task", "trace-b", now=self.start)
        self.assertEqual("tenant-a", tenant_a.get("shared-task", now=self.start).tenant_id)
        self.assertEqual("tenant-b", context_b.tenant_id)
        self.assertEqual(1, len(tenant_a.all(now=self.start)))
        self.assertEqual(1, len(tenant_b.all(now=self.start)))

    def test_expired_active_context_is_rejected_and_not_cleaned_by_default(self) -> None:
        bus = self.bus()
        bus.create("active", "trace-active", ttl_seconds=5, now=self.start)
        expired_at = self.start + timedelta(seconds=6)
        with self.assertRaises(ContextExpired):
            bus.get("active", now=expired_at)
        self.assertEqual([], bus.cleanup_expired(now=expired_at))
        self.assertEqual(
            "active",
            bus.get("active", allow_expired=True, now=expired_at).coordination_status,
        )
        self.assertEqual(["active"], bus.cleanup_expired(include_active=True, now=expired_at))

    def test_expired_terminal_context_is_cleaned_by_default(self) -> None:
        bus = self.bus()
        context = bus.create("done", "trace-done", ttl_seconds=5, now=self.start)
        context.coordination_status = "completed"
        bus.commit(context, now=self.start + timedelta(seconds=1))
        self.assertEqual(
            ["done"],
            bus.cleanup_expired(now=self.start + timedelta(seconds=6)),
        )
        with self.assertRaises(KeyError):
            bus.get("done", allow_expired=True, now=self.start + timedelta(seconds=6))

    def test_heartbeat_extends_lease_and_wrong_worker_is_rejected(self) -> None:
        bus = self.bus()
        bus.create("task-1", "trace-1", now=self.start)
        coordinator = ContextCoordinator(bus, phase_order=("EXECUTE",))
        assignment = coordinator.assign(
            "task-1", "EXECUTE", "Executor", lease_seconds=10, now=self.start
        )
        with self.assertRaises(WorkerMismatchError):
            coordinator.heartbeat(
                "task-1",
                assignment.assignment_id,
                "Auditor",
                now=self.start + timedelta(seconds=1),
            )
        heartbeat = coordinator.heartbeat(
            "task-1",
            assignment.assignment_id,
            "Executor",
            lease_seconds=20,
            now=self.start + timedelta(seconds=5),
        )
        self.assertEqual("running", heartbeat.status)
        self.assertEqual("2026-09-02T01:00:25Z", heartbeat.lease_expires_at)

    def test_reassignment_requires_expiry_and_creates_only_one_successor(self) -> None:
        bus = self.bus()
        bus.create("task-1", "trace-1", now=self.start)
        coordinator = ContextCoordinator(bus, phase_order=("VERIFY",))
        assignment = coordinator.assign(
            "task-1", "VERIFY", "Auditor-1", lease_seconds=10, now=self.start
        )
        with self.assertRaises(ActiveLeaseError):
            coordinator.reassign_expired(
                "task-1",
                assignment.assignment_id,
                "Auditor-2",
                now=self.start + timedelta(seconds=9),
            )

        successor = coordinator.reassign_expired(
            "task-1",
            assignment.assignment_id,
            "Auditor-2",
            now=self.start + timedelta(seconds=11),
        )
        duplicate = ContextCoordinator(self.bus(), phase_order=("VERIFY",)).reassign_expired(
            "task-1",
            assignment.assignment_id,
            "Auditor-3",
            now=self.start + timedelta(seconds=11),
        )
        context = bus.get("task-1", now=self.start + timedelta(seconds=11))
        self.assertEqual(successor.assignment_id, duplicate.assignment_id)
        self.assertEqual(2, len(context.assignments))
        self.assertEqual(["expired", "assigned"], [item.status for item in context.assignments])
        self.assertEqual(2, successor.attempt)
        coordinator.fail(
            "task-1",
            successor.assignment_id,
            "Auditor-2",
            "manual escalation required",
            now=self.start + timedelta(seconds=12),
        )
        with self.assertRaises(AssignmentStateError):
            coordinator.assign(
                "task-1", "VERIFY", "Auditor-3", now=self.start + timedelta(seconds=12)
            )
        self.assertEqual(
            2,
            len(bus.get("task-1", now=self.start + timedelta(seconds=12)).assignments),
        )

    def test_concurrent_timeout_reassignment_converges_on_one_successor(self) -> None:
        bus = self.bus()
        bus.create("task-1", "trace-1", now=self.start)
        assignment = ContextCoordinator(bus, phase_order=("VERIFY",)).assign(
            "task-1", "VERIFY", "Auditor-1", lease_seconds=10, now=self.start
        )

        def reassign(worker: str) -> str:
            return (
                ContextCoordinator(self.bus(), phase_order=("VERIFY",))
                .reassign_expired(
                    "task-1",
                    assignment.assignment_id,
                    worker,
                    now=self.start + timedelta(seconds=11),
                )
                .assignment_id
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            successor_ids = set(executor.map(reassign, ("Auditor-2", "Auditor-3")))
        context = bus.get("task-1", now=self.start + timedelta(seconds=11))
        self.assertEqual(1, len(successor_ids))
        self.assertEqual(2, len(context.assignments))

    def test_expired_worker_cannot_complete_and_checkpoint_is_atomic(self) -> None:
        bus = self.bus()
        bus.create("task-1", "trace-1", now=self.start)
        coordinator = ContextCoordinator(bus, phase_order=("LEARN",))
        assignment = coordinator.assign(
            "task-1", "LEARN", "Auditor", lease_seconds=10, now=self.start
        )
        before = bus.get("task-1", now=self.start)
        with self.assertRaises(LeaseExpiredError):
            coordinator.complete(
                "task-1",
                assignment.assignment_id,
                "Auditor",
                now=self.start + timedelta(seconds=11),
            )
        unchanged = bus.get("task-1", now=self.start)
        self.assertEqual(before.version, unchanged.version)
        self.assertEqual({}, unchanged.checkpoints)
        self.assertEqual("assigned", unchanged.assignments[0].status)


if __name__ == "__main__":
    unittest.main()
