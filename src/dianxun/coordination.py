"""Lease and checkpoint orchestration built on the durable context bus.

The control plane stores only assignment state and evidence references. It never
mutates incident, approval, work-order, inventory or business terminal state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from .context_bus import (
    ContextBus,
    ContextVersionConflict,
    PhaseCheckpoint,
    TaskContext,
    WorkerAssignment,
    parse_timestamp,
    timestamp,
    utc_now,
)

PHASE_ORDER = (
    "DETECT_CONTAIN",
    "DIAGNOSE_DECIDE",
    "EXECUTE",
    "VERIFY",
    "LEARN",
)
_ACTIVE_ASSIGNMENT_STATES = {"assigned", "running"}


class CoordinationError(RuntimeError):
    """Base class for coordination failures."""


class AssignmentNotFound(CoordinationError):
    """An assignment id is not part of the task context."""


class AssignmentStateError(CoordinationError):
    """An assignment operation is invalid for its current state."""


class ActiveLeaseError(CoordinationError):
    """Reassignment was attempted while the current lease is valid."""


class LeaseExpiredError(CoordinationError):
    """A worker tried to heartbeat or complete an expired lease."""


class WorkerMismatchError(CoordinationError):
    """Another Worker tried to acknowledge an assignment."""


class ContextCoordinator:
    """Perform versioned Worker assignment and restart-safe checkpoint operations."""

    def __init__(self, bus: ContextBus, *, phase_order: tuple[str, ...] = PHASE_ORDER) -> None:
        if not phase_order or len(set(phase_order)) != len(phase_order):
            raise ValueError("phase_order must be non-empty and unique")
        self.bus = bus
        self.phase_order = phase_order

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        return (value or utc_now()).astimezone(UTC)

    @staticmethod
    def _find_assignment(context: TaskContext, assignment_id: str) -> WorkerAssignment:
        for assignment in context.assignments:
            if assignment.assignment_id == assignment_id:
                return assignment
        raise AssignmentNotFound(f"未知 assignment {assignment_id}")

    @staticmethod
    def _assert_worker(assignment: WorkerAssignment, worker: str) -> None:
        if assignment.worker != worker:
            raise WorkerMismatchError(
                f"assignment {assignment.assignment_id} 属于 {assignment.worker}, 不是 {worker}"
            )

    @staticmethod
    def _lease_expiry(now: datetime, lease_seconds: int) -> str:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        return timestamp(now + timedelta(seconds=lease_seconds))

    def _assert_phase(self, phase: str) -> None:
        if phase not in self.phase_order:
            raise ValueError(f"未知协调阶段 {phase}")

    def _checkpoint_prefix_length(self, context: TaskContext) -> int:
        unknown = set(context.checkpoints) - set(self.phase_order)
        if unknown:
            raise AssignmentStateError(
                f"上下文含未知 checkpoint 阶段: {', '.join(sorted(unknown))}"
            )
        completed = tuple(phase for phase in self.phase_order if phase in context.checkpoints)
        expected = self.phase_order[: len(completed)]
        if completed != expected:
            raise AssignmentStateError("checkpoint 必须是五阶段顺序前缀")
        return len(completed)

    def _assert_phase_ready(self, context: TaskContext, phase: str) -> None:
        """Require checkpoints to form the configured phase-order prefix."""
        self._checkpoint_prefix_length(context)
        phase_index = self.phase_order.index(phase)
        missing = [
            predecessor
            for predecessor in self.phase_order[:phase_index]
            if predecessor not in context.checkpoints
        ]
        if missing:
            raise AssignmentStateError(
                f"阶段 {phase} 的前序 checkpoint 未完成: {', '.join(missing)}"
            )

    def _assignment_id(
        self,
        task_id: str,
        phase: str,
        attempt: int,
        predecessor_assignment_id: str | None = None,
    ) -> str:
        identity = (
            f"dianxun://{self.bus.tenant_id}/{task_id}/{phase}/{attempt}/"
            f"{predecessor_assignment_id or 'initial'}"
        )
        return uuid.uuid5(uuid.NAMESPACE_URL, identity).hex

    def assign(
        self,
        task_id: str,
        phase: str,
        worker: str,
        *,
        lease_seconds: int = 60,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> WorkerAssignment:
        self._assert_phase(phase)
        current = self._now(now)
        context = self.bus.get(task_id, now=current)
        if context.coordination_status != "active":
            raise AssignmentStateError(
                f"任务 {task_id} 协调状态为 {context.coordination_status}, 不得派发"
            )
        self._assert_phase_ready(context, phase)
        if phase in context.checkpoints:
            raise AssignmentStateError(f"阶段 {phase} 已有成功 checkpoint, 不得重复派发")
        matching = [item for item in context.assignments if item.phase == phase]
        if matching:
            latest = max(matching, key=lambda item: item.attempt)
            if latest.status in _ACTIVE_ASSIGNMENT_STATES:
                if latest.is_lease_expired(current):
                    raise LeaseExpiredError(
                        f"assignment {latest.assignment_id} 已超时, 必须走 reassign_expired"
                    )
                raise ActiveLeaseError(f"阶段 {phase} 仍有有效 lease")
            raise AssignmentStateError(
                f"阶段 {phase} 已有 {latest.status} assignment; "
                "普通 assign 不得生成无 predecessor 的新 attempt"
            )
        attempt = 1
        current_text = timestamp(current)
        assignment = WorkerAssignment(
            assignment_id=self._assignment_id(task_id, phase, attempt),
            phase=phase,
            worker=worker,
            attempt=attempt,
            lease_expires_at=self._lease_expiry(current, lease_seconds),
            created_at=current_text,
            updated_at=current_text,
        )
        context.assignments.append(assignment)
        self.bus.commit(
            context,
            expected_version=context.version if expected_version is None else expected_version,
            now=current,
        )
        return WorkerAssignment.from_snapshot(assignment.__dict__.copy())

    def heartbeat(
        self,
        task_id: str,
        assignment_id: str,
        worker: str,
        *,
        lease_seconds: int = 60,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> WorkerAssignment:
        current = self._now(now)
        context = self.bus.get(task_id, now=current)
        assignment = self._find_assignment(context, assignment_id)
        self._assert_worker(assignment, worker)
        if assignment.status not in _ACTIVE_ASSIGNMENT_STATES:
            raise AssignmentStateError(
                f"assignment {assignment_id} 状态为 {assignment.status}, 不能 heartbeat"
            )
        if assignment.is_lease_expired(current):
            raise LeaseExpiredError(f"assignment {assignment_id} lease 已过期")
        proposed = parse_timestamp(self._lease_expiry(current, lease_seconds))
        existing = parse_timestamp(assignment.lease_expires_at)
        assignment.lease_expires_at = timestamp(max(proposed, existing))
        assignment.status = "running"
        assignment.last_heartbeat_at = timestamp(current)
        assignment.updated_at = timestamp(current)
        self.bus.commit(
            context,
            expected_version=context.version if expected_version is None else expected_version,
            now=current,
        )
        return WorkerAssignment.from_snapshot(assignment.__dict__.copy())

    def complete(
        self,
        task_id: str,
        assignment_id: str,
        worker: str,
        *,
        evidence_refs: list[str] | None = None,
        output_ref: str | None = None,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> PhaseCheckpoint:
        """Atomically mark the lease successful and write its phase checkpoint."""
        current = self._now(now)
        context = self.bus.get(task_id, now=current)
        assignment = self._find_assignment(context, assignment_id)
        self._assert_worker(assignment, worker)
        self._assert_phase_ready(context, assignment.phase)
        existing = context.checkpoints.get(assignment.phase)
        if existing is not None:
            if existing.assignment_id == assignment_id:
                return PhaseCheckpoint.from_snapshot(existing.__dict__.copy())
            raise AssignmentStateError(f"阶段 {assignment.phase} 已由其他 assignment 完成")
        if context.coordination_status != "active":
            raise AssignmentStateError(
                f"任务 {task_id} 协调状态为 {context.coordination_status}, 不得完成"
            )
        if assignment.status not in _ACTIVE_ASSIGNMENT_STATES:
            raise AssignmentStateError(
                f"assignment {assignment_id} 状态为 {assignment.status}, 不能完成"
            )
        if assignment.is_lease_expired(current):
            raise LeaseExpiredError(f"assignment {assignment_id} lease 已过期")
        assignment.status = "succeeded"
        assignment.updated_at = timestamp(current)
        checkpoint = PhaseCheckpoint(
            phase=assignment.phase,
            assignment_id=assignment.assignment_id,
            worker=worker,
            completed_at=timestamp(current),
            context_version=context.version + 1,
            evidence_refs=list(evidence_refs or []),
            output_ref=output_ref,
        )
        context.checkpoints[assignment.phase] = checkpoint
        if all(phase in context.checkpoints for phase in self.phase_order):
            context.coordination_status = "completed"
        self.bus.commit(
            context,
            expected_version=context.version if expected_version is None else expected_version,
            now=current,
        )
        return PhaseCheckpoint.from_snapshot(checkpoint.__dict__.copy())

    def fail(
        self,
        task_id: str,
        assignment_id: str,
        worker: str,
        error: str,
        *,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> WorkerAssignment:
        current = self._now(now)
        context = self.bus.get(task_id, now=current)
        assignment = self._find_assignment(context, assignment_id)
        self._assert_worker(assignment, worker)
        if context.coordination_status != "active":
            raise AssignmentStateError(
                f"任务 {task_id} 协调状态为 {context.coordination_status}, 不得标记失败"
            )
        if assignment.status not in _ACTIVE_ASSIGNMENT_STATES:
            raise AssignmentStateError(
                f"assignment {assignment_id} 状态为 {assignment.status}, 不能标记失败"
            )
        assignment.status = "failed"
        assignment.error = error
        assignment.updated_at = timestamp(current)
        self.bus.commit(
            context,
            expected_version=context.version if expected_version is None else expected_version,
            now=current,
        )
        return WorkerAssignment.from_snapshot(assignment.__dict__.copy())

    def reassign_expired(
        self,
        task_id: str,
        assignment_id: str,
        worker: str,
        *,
        lease_seconds: int = 60,
        expected_version: int | None = None,
        now: datetime | None = None,
    ) -> WorkerAssignment:
        """Create exactly one successor after the predecessor lease expires."""
        current = self._now(now)
        caller_expected_version = expected_version
        for _ in range(2):
            context = self.bus.get(task_id, now=current)
            predecessor = self._find_assignment(context, assignment_id)
            successors = [
                item
                for item in context.assignments
                if item.predecessor_assignment_id == assignment_id
            ]
            if successors:
                return WorkerAssignment.from_snapshot(successors[0].__dict__.copy())
            if context.coordination_status != "active":
                raise AssignmentStateError(
                    f"任务 {task_id} 协调状态为 {context.coordination_status}, 不得重派"
                )
            self._assert_phase_ready(context, predecessor.phase)
            if predecessor.phase in context.checkpoints:
                raise AssignmentStateError(
                    f"阶段 {predecessor.phase} 已有成功 checkpoint, 不得超时重派"
                )
            if predecessor.status not in _ACTIVE_ASSIGNMENT_STATES:
                raise AssignmentStateError(
                    f"assignment {assignment_id} 状态为 {predecessor.status}, 不能超时重派"
                )
            if not predecessor.is_lease_expired(current):
                raise ActiveLeaseError(f"assignment {assignment_id} lease 尚未过期")
            predecessor.status = "expired"
            predecessor.updated_at = timestamp(current)
            successor = WorkerAssignment(
                assignment_id=self._assignment_id(
                    task_id,
                    predecessor.phase,
                    predecessor.attempt + 1,
                    predecessor.assignment_id,
                ),
                phase=predecessor.phase,
                worker=worker,
                attempt=predecessor.attempt + 1,
                lease_expires_at=self._lease_expiry(current, lease_seconds),
                predecessor_assignment_id=predecessor.assignment_id,
                created_at=timestamp(current),
                updated_at=timestamp(current),
            )
            context.assignments.append(successor)
            try:
                self.bus.commit(
                    context,
                    expected_version=(
                        context.version if expected_version is None else expected_version
                    ),
                    now=current,
                )
            except ContextVersionConflict:
                if caller_expected_version is not None:
                    raise
                expected_version = None
                continue
            return WorkerAssignment.from_snapshot(successor.__dict__.copy())
        latest = self.bus.get(task_id, now=current)
        successors = [
            item for item in latest.assignments if item.predecessor_assignment_id == assignment_id
        ]
        if successors:
            return WorkerAssignment.from_snapshot(successors[0].__dict__.copy())
        raise ContextVersionConflict(f"assignment {assignment_id} 重派发生持续版本冲突")

    def resume_plan(self, task_id: str, *, now: datetime | None = None) -> list[str]:
        """Return phases still required after loading durable checkpoints."""
        context = self.bus.get(task_id, now=self._now(now))
        completed = self._checkpoint_prefix_length(context)
        return list(self.phase_order[completed:])
