"""Serializable incident entities.

The dataclasses deliberately mirror ``schemas/incident-case.v1.schema.json``.
They are transport-neutral: both the local demo and AgentTeams adapters exchange
the same structure.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from .enums import (
    ActionStatus,
    BatchDisposition,
    IncidentStatus,
    IncidentType,
    Phase,
    Severity,
    VerificationResult,
    WorkStatus,
)


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class Evidence:
    evidence_id: str
    incident_id: str | None
    type: str
    source: str
    observed_at: str
    collected_at: str
    payload: dict[str, Any]
    quality: str
    freshness: str
    request_id: str
    immutable_hash: str

    @classmethod
    def create(
        cls,
        *,
        evidence_type: str,
        source: str,
        observed_at: str,
        collected_at: str,
        payload: dict[str, Any],
        quality: str,
        freshness: str,
        request_id: str,
        incident_id: str | None = None,
    ) -> Evidence:
        immutable = {
            "incident_id": incident_id,
            "type": evidence_type,
            "source": source,
            "observed_at": observed_at,
            "collected_at": collected_at,
            "payload": payload,
            "quality": quality,
            "freshness": freshness,
            "request_id": request_id,
        }
        return cls(
            evidence_id=f"ev_{stable_hash(immutable)[:16]}",
            incident_id=incident_id,
            type=evidence_type,
            source=source,
            observed_at=observed_at,
            collected_at=collected_at,
            payload=payload,
            quality=quality,
            freshness=freshness,
            request_id=request_id,
            immutable_hash=stable_hash(immutable),
        )


@dataclass(slots=True)
class Hypothesis:
    hypothesis_id: str
    label: str
    confidence: float
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    next_checks: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Decision:
    decision_id: str
    policy_id: str
    selected_hypothesis_ids: list[str]
    proposed_actions: list[str]
    risk_level: str
    approval_required: bool
    approvers: list[str]
    decision_reason: str
    evidence_ids: list[str]
    created_by: str


@dataclass(slots=True)
class Action:
    action_id: str
    action_type: str
    tool_name: str
    target: str
    idempotency_key: str
    approval_id: str | None = None
    status: ActionStatus = ActionStatus.PROPOSED
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] | None = None
    rollback_or_compensation: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass(slots=True)
class Verification:
    verification_id: str
    subject: str
    method: str
    expected_condition: dict[str, Any]
    observed_value: Any
    evidence_ids: list[str]
    result: VerificationResult
    verifier: str
    verified_at: str


@dataclass(slots=True)
class IncidentCase:
    incident_id: str
    trace_id: str
    tenant_id: str
    store_id: str
    incident_type: IncidentType
    severity: Severity
    phase: Phase
    incident_status: IncidentStatus
    work_status: WorkStatus
    trigger: str
    detected_at: str
    anchor_time: str
    affected_assets: list[str] = field(default_factory=list)
    affected_batches: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    verifications: list[Verification] = field(default_factory=list)
    asset_states: dict[str, str] = field(default_factory=dict)
    batch_dispositions: dict[str, BatchDisposition] = field(default_factory=dict)
    sales_hold_refs: list[str] = field(default_factory=list)
    approval_refs: list[str] = field(default_factory=list)
    workorder_refs: list[str] = field(default_factory=list)
    owner: str = "Orchestrator"
    next_wakeup_at: str | None = None
    created_at: str = field(default_factory=iso_now)
    updated_at: str = field(default_factory=iso_now)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        store_id: str,
        incident_type: IncidentType,
        severity: Severity,
        trigger: str,
        anchor_time: str,
        trace_id: str | None = None,
        incident_id: str | None = None,
        detected_at: str | None = None,
    ) -> IncidentCase:
        return cls(
            incident_id=incident_id or f"inc_{uuid.uuid4().hex[:16]}",
            trace_id=trace_id or f"tr_{uuid.uuid4().hex[:16]}",
            tenant_id=tenant_id,
            store_id=store_id,
            incident_type=incident_type,
            severity=severity,
            phase=Phase.DETECT_CONTAIN,
            incident_status=IncidentStatus.OPEN,
            work_status=WorkStatus.READY,
            trigger=trigger,
            detected_at=detected_at or anchor_time,
            anchor_time=anchor_time,
        )

    def touch(self, at: str | None = None) -> None:
        self.updated_at = at or iso_now()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IncidentCase:
        data = dict(raw)
        data["incident_type"] = IncidentType(data["incident_type"])
        data["severity"] = Severity(data["severity"])
        data["phase"] = Phase(data["phase"])
        data["incident_status"] = IncidentStatus(data["incident_status"])
        data["work_status"] = WorkStatus(data["work_status"])
        data["hypotheses"] = [Hypothesis(**item) for item in data.get("hypotheses", [])]
        data["decisions"] = [Decision(**item) for item in data.get("decisions", [])]
        data["actions"] = [
            Action(**{**item, "status": ActionStatus(item["status"])})
            for item in data.get("actions", [])
        ]
        data["verifications"] = [
            Verification(**{**item, "result": VerificationResult(item["result"])})
            for item in data.get("verifications", [])
        ]
        data["batch_dispositions"] = {
            batch_id: BatchDisposition(value)
            for batch_id, value in data.get("batch_dispositions", {}).items()
        }
        return cls(**data)
