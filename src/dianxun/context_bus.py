"""Tenant-scoped coordination context with optional SQLite persistence.

IncidentService remains the only authority for incident and business state. This
module stores orchestration metadata, assignments, checkpoints and evidence refs.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

TaskState = Literal[
    "created",
    "detecting",
    "diagnosing",
    "approving",
    "executing",
    "verifying",
    "reviewing",
    "closed",
    "reopened",
    "failed",
]
CoordinationStatus = Literal["active", "completed", "failed"]
AssignmentStatus = Literal["assigned", "running", "succeeded", "failed", "expired"]

_STATE_GRAPH: dict[str, list[str]] = {
    "created": ["detecting", "failed"],
    "detecting": ["diagnosing", "closed", "failed"],
    "diagnosing": ["approving", "failed"],
    "approving": ["executing", "closed", "failed"],
    "executing": ["verifying", "failed"],
    "verifying": ["reviewing", "reopened", "diagnosing", "failed"],
    "reopened": ["diagnosing", "failed"],
    "reviewing": ["closed", "failed"],
    "closed": [],
    "failed": [],
}


class ContextBusError(RuntimeError):
    """Base class for durable coordination context errors."""


class ContextVersionConflict(ContextBusError):
    """An optimistic update used a stale version."""


class ContextTenantMismatch(ContextBusError):
    """A context was submitted to another tenant's bus."""


class ContextExpired(ContextBusError):
    """An active operation targeted an expired context."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass
class WorkerAssignment:
    """One leased unit of work delegated to a Worker."""

    assignment_id: str
    phase: str
    worker: str
    attempt: int
    lease_expires_at: str
    status: AssignmentStatus = "assigned"
    predecessor_assignment_id: str | None = None
    created_at: str = field(default_factory=lambda: timestamp(utc_now()))
    updated_at: str = field(default_factory=lambda: timestamp(utc_now()))
    last_heartbeat_at: str | None = None
    error: str | None = None

    @classmethod
    def from_snapshot(cls, value: dict) -> WorkerAssignment:
        return cls(**value)

    def is_lease_expired(self, now: datetime) -> bool:
        return parse_timestamp(self.lease_expires_at) <= now.astimezone(UTC)


@dataclass
class PhaseCheckpoint:
    """Durable proof that an orchestration phase finished."""

    phase: str
    assignment_id: str
    worker: str
    completed_at: str
    context_version: int
    evidence_refs: list[str] = field(default_factory=list)
    output_ref: str | None = None

    @classmethod
    def from_snapshot(cls, value: dict) -> PhaseCheckpoint:
        return cls(**value)


@dataclass
class TaskContext:
    """Shared orchestration context for one task.

    The business-shaped fields are retained only for the historical supplementary
    demo. The cold-chain P0 flow uses IncidentService for all business facts.
    """

    task_id: str
    trace_id: str
    trigger: str
    tenant_id: str = "demo"
    scope: dict = field(default_factory=dict)
    state: TaskState = "created"
    anomalies: list[dict] = field(default_factory=list)
    root_causes: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    validation: dict | None = None
    review: dict | None = None
    transitions: list[dict] = field(default_factory=list)
    coordination_status: CoordinationStatus = "active"
    assignments: list[WorkerAssignment] = field(default_factory=list)
    checkpoints: dict[str, PhaseCheckpoint] = field(default_factory=dict)
    version: int = 1
    created_at: str = field(default_factory=lambda: timestamp(utc_now()))
    updated_at: str = field(default_factory=lambda: timestamp(utc_now()))
    expires_at: str | None = None

    @classmethod
    def from_snapshot(cls, value: dict) -> TaskContext:
        data = copy.deepcopy(value)
        data["assignments"] = [
            item if isinstance(item, WorkerAssignment) else WorkerAssignment.from_snapshot(item)
            for item in data.get("assignments", [])
        ]
        data["checkpoints"] = {
            phase: item
            if isinstance(item, PhaseCheckpoint)
            else PhaseCheckpoint.from_snapshot(item)
            for phase, item in data.get("checkpoints", {}).items()
        }
        return cls(**data)

    def clone(self) -> TaskContext:
        return TaskContext.from_snapshot(self.snapshot())

    def transition(self, new_state: TaskState, actor: str, note: str = "") -> None:
        """Run the legacy supplementary-demo state transition."""
        allowed = _STATE_GRAPH.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(f"非法状态流转: {self.state} → {new_state}(合法: {allowed})")
        self.transitions.append(
            {
                "from": self.state,
                "to": new_state,
                "actor": actor,
                "note": note,
                "at": timestamp(utc_now()),
            }
        )
        self.state = new_state

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = (now or utc_now()).astimezone(UTC)
        return parse_timestamp(self.expires_at) <= current

    def is_terminal(self) -> bool:
        return self.coordination_status in {"completed", "failed"} or self.state in {
            "closed",
            "failed",
        }

    def snapshot(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.snapshot(), ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )


class ContextBus:
    """Tenant-bound context repository with optional optimistic SQLite storage."""

    def __init__(
        self,
        *,
        tenant_id: str = "demo",
        database_path: str | Path | None = None,
    ) -> None:
        if not tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        self.tenant_id = tenant_id
        self.database_path = Path(database_path) if database_path is not None else None
        self._tasks: dict[str, TaskContext] = {}
        if self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        if self.database_path is None:
            raise RuntimeError("ContextBus is using in-memory mode")
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize_database(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS coordination_contexts (
                    tenant_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK (version >= 1),
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, task_id)
                );
                CREATE INDEX IF NOT EXISTS idx_coordination_context_expiry
                    ON coordination_contexts (tenant_id, expires_at);
                """
            )

    @staticmethod
    def _serialize(context: TaskContext) -> str:
        return json.dumps(
            context.snapshot(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize(payload: str) -> TaskContext:
        return TaskContext.from_snapshot(json.loads(payload))

    def _assert_tenant(self, context: TaskContext) -> None:
        if context.tenant_id != self.tenant_id:
            raise ContextTenantMismatch(
                f"context tenant {context.tenant_id!r} does not match bus tenant {self.tenant_id!r}"
            )

    def create(
        self,
        task_id: str,
        trace_id: str,
        trigger: str = "scheduled",
        scope: dict | None = None,
        *,
        ttl_seconds: int | None = None,
        now: datetime | None = None,
    ) -> TaskContext:
        if not task_id.strip():
            raise ValueError("task_id must not be empty")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        current = (now or utc_now()).astimezone(UTC)
        current_text = timestamp(current)
        context = TaskContext(
            task_id=task_id,
            trace_id=trace_id,
            trigger=trigger,
            tenant_id=self.tenant_id,
            scope=copy.deepcopy(scope or {}),
            created_at=current_text,
            updated_at=current_text,
            expires_at=(
                timestamp(current + timedelta(seconds=ttl_seconds))
                if ttl_seconds is not None
                else None
            ),
        )
        if self.database_path is None:
            if task_id in self._tasks:
                raise ValueError(f"任务 {task_id} 已存在,不能覆盖原上下文")
            self._tasks[task_id] = context
            return context

        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    """
                    INSERT INTO coordination_contexts (
                        tenant_id, task_id, version, updated_at, expires_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.tenant_id,
                        task_id,
                        context.version,
                        context.updated_at,
                        context.expires_at,
                        self._serialize(context),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"任务 {task_id} 已存在,不能覆盖原上下文") from error
        return context

    def get(
        self,
        task_id: str,
        *,
        allow_expired: bool = False,
        now: datetime | None = None,
    ) -> TaskContext:
        if self.database_path is None:
            try:
                context = self._tasks[task_id].clone()
            except KeyError as error:
                raise KeyError(f"未知任务 {task_id}") from error
        else:
            with closing(self._connect()) as connection, connection:
                row = connection.execute(
                    """
                    SELECT payload_json FROM coordination_contexts
                    WHERE tenant_id = ? AND task_id = ?
                    """,
                    (self.tenant_id, task_id),
                ).fetchone()
            if row is None:
                raise KeyError(f"未知任务 {task_id}")
            context = self._deserialize(row["payload_json"])
        if not allow_expired and context.is_expired(now):
            raise ContextExpired(f"任务 {task_id} 的协调上下文已过期")
        return context

    def commit(
        self,
        context: TaskContext,
        *,
        expected_version: int | None = None,
        allow_expired: bool = False,
        now: datetime | None = None,
    ) -> TaskContext:
        self._assert_tenant(context)
        current = (now or utc_now()).astimezone(UTC)
        if not allow_expired and context.is_expired(current):
            raise ContextExpired(f"任务 {context.task_id} 的协调上下文已过期")
        expected = context.version if expected_version is None else expected_version
        if expected < 1:
            raise ValueError("expected_version must be positive")
        if context.version != expected:
            raise ContextVersionConflict(
                f"任务 {context.task_id} 提交上下文版本不匹配: "
                f"context={context.version}, expected={expected}"
            )
        candidate = context.clone()
        candidate.version = expected + 1
        candidate.updated_at = timestamp(current)

        if self.database_path is None:
            stored = self._tasks.get(context.task_id)
            if stored is None:
                raise KeyError(f"未知任务 {context.task_id}")
            if stored.version != expected:
                raise ContextVersionConflict(
                    f"任务 {context.task_id} 版本冲突: expected={expected}, actual={stored.version}"
                )
            self._tasks[context.task_id] = candidate
        else:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute(
                    """
                    UPDATE coordination_contexts
                    SET version = ?, updated_at = ?, expires_at = ?, payload_json = ?
                    WHERE tenant_id = ? AND task_id = ? AND version = ?
                    """,
                    (
                        candidate.version,
                        candidate.updated_at,
                        candidate.expires_at,
                        self._serialize(candidate),
                        self.tenant_id,
                        candidate.task_id,
                        expected,
                    ),
                )
                if cursor.rowcount != 1:
                    row = connection.execute(
                        """
                        SELECT version FROM coordination_contexts
                        WHERE tenant_id = ? AND task_id = ?
                        """,
                        (self.tenant_id, candidate.task_id),
                    ).fetchone()
                    if row is None:
                        raise KeyError(f"未知任务 {candidate.task_id}")
                    raise ContextVersionConflict(
                        f"任务 {candidate.task_id} 版本冲突: "
                        f"expected={expected}, actual={row['version']}"
                    )
        context.version = candidate.version
        context.updated_at = candidate.updated_at
        return candidate.clone()

    def all(
        self,
        *,
        include_expired: bool = False,
        now: datetime | None = None,
    ) -> list[TaskContext]:
        if self.database_path is None:
            contexts = [context.clone() for context in self._tasks.values()]
        else:
            with closing(self._connect()) as connection, connection:
                rows = connection.execute(
                    """
                    SELECT payload_json FROM coordination_contexts
                    WHERE tenant_id = ? ORDER BY updated_at, task_id
                    """,
                    (self.tenant_id,),
                ).fetchall()
            contexts = [self._deserialize(row["payload_json"]) for row in rows]
        if include_expired:
            return contexts
        return [context for context in contexts if not context.is_expired(now)]

    def cleanup_expired(
        self,
        *,
        include_active: bool = False,
        now: datetime | None = None,
    ) -> list[str]:
        """Delete expired terminal contexts; active deletion must be explicit."""
        current = (now or utc_now()).astimezone(UTC)
        targets = [
            context
            for context in self.all(include_expired=True, now=current)
            if context.is_expired(current) and (include_active or context.is_terminal())
        ]
        if self.database_path is None:
            for context in targets:
                stored = self._tasks.get(context.task_id)
                if stored is not None and stored.version == context.version:
                    del self._tasks[context.task_id]
        elif targets:
            with closing(self._connect()) as connection, connection:
                for context in targets:
                    connection.execute(
                        """
                        DELETE FROM coordination_contexts
                        WHERE tenant_id = ? AND task_id = ? AND version = ?
                        """,
                        (self.tenant_id, context.task_id, context.version),
                    )
        remaining = {context.task_id for context in self.all(include_expired=True, now=current)}
        return [context.task_id for context in targets if context.task_id not in remaining]
