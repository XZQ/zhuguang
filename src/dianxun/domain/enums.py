"""Finite state values used by the incident domain and the mock business world."""

from enum import StrEnum


class Phase(StrEnum):
    DETECT_CONTAIN = "DETECT_CONTAIN"
    DIAGNOSE_DECIDE = "DIAGNOSE_DECIDE"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    LEARN = "LEARN"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class WorkStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(StrEnum):
    COLDCHAIN_TEMPERATURE_LOSS = "coldchain_temperature_loss"
    STOCKOUT = "stockout"
    PRICE_TAG_MISMATCH = "price_tag_mismatch"


class BatchDisposition(StrEnum):
    UNKNOWN = "unknown"
    QUARANTINED = "quarantined"
    TRANSFERRED = "transferred"
    RELEASED = "released"
    DISPOSED = "disposed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class WorkOrderStatus(StrEnum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CLOSED = "closed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    COMPENSATED = "compensated"


class VerificationResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"
