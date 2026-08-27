"""The only service allowed to aggregate and transition incident state."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .enums import (
    ActionStatus,
    BatchDisposition,
    IncidentStatus,
    Phase,
    VerificationResult,
    WorkStatus,
)
from .models import Action, Decision, Evidence, Hypothesis, IncidentCase, Verification

if TYPE_CHECKING:
    from ..state.store import StateStore


class InvalidTransition(ValueError):
    """Raised when an actor asks for an illegal phase or status transition."""


_PHASE_GRAPH: dict[Phase, set[Phase]] = {
    Phase.DETECT_CONTAIN: {Phase.DIAGNOSE_DECIDE},
    Phase.DIAGNOSE_DECIDE: {Phase.EXECUTE},
    Phase.EXECUTE: {Phase.VERIFY},
    Phase.VERIFY: {Phase.DIAGNOSE_DECIDE, Phase.LEARN},
    Phase.LEARN: set(),
}

_TERMINAL_BATCH_STATES = {
    BatchDisposition.TRANSFERRED,
    BatchDisposition.RELEASED,
    BatchDisposition.DISPOSED,
}


class IncidentService:
    """Owns phase transitions and computes aggregate incident status.

    Adapters and Agents may append domain facts through this service. They may
    not assign ``RESOLVED`` or ``CLOSED`` directly.
    """

    def __init__(self, store: StateStore) -> None:
        self.store = store

    def create(self, case: IncidentCase) -> IncidentCase:
        if self.store.get_incident(case.incident_id) is not None:
            raise ValueError(f"Incident {case.incident_id} already exists")
        case.touch(self.store.now())
        self.store.save_incident(case.to_dict())
        return case

    def get(self, incident_id: str) -> IncidentCase:
        raw = self.store.get_incident(incident_id)
        if raw is None:
            raise KeyError(f"Unknown incident {incident_id}")
        return IncidentCase.from_dict(raw)

    def save(self, case: IncidentCase) -> IncidentCase:
        case.touch(self.store.now())
        self.store.save_incident(case.to_dict())
        return case

    def transition_phase(
        self,
        incident_id: str,
        target: Phase,
        *,
        actor: str,
        reason: str,
    ) -> IncidentCase:
        case = self.get(incident_id)
        if target not in _PHASE_GRAPH[case.phase]:
            raise InvalidTransition(f"Illegal phase transition {case.phase} -> {target}")
        if target == Phase.LEARN and case.incident_status is not IncidentStatus.RESOLVED:
            raise InvalidTransition("Only a RESOLVED incident may enter LEARN")
        case.phase = target
        case.work_status = WorkStatus.RUNNING
        case.decisions.append(
            Decision(
                decision_id=f"phase:{case.phase}:{len(case.decisions) + 1}",
                policy_id="incident-phase-v1",
                selected_hypothesis_ids=[],
                proposed_actions=[],
                risk_level="L0",
                approval_required=False,
                approvers=[],
                decision_reason=reason,
                evidence_ids=[],
                created_by=actor,
            )
        )
        return self.save(case)

    def reopen(self, incident_id: str, *, reason: str) -> IncidentCase:
        case = self.get(incident_id)
        if case.phase is not Phase.VERIFY:
            raise InvalidTransition("Only VERIFY may reopen to DIAGNOSE_DECIDE")
        case.phase = Phase.DIAGNOSE_DECIDE
        case.incident_status = IncidentStatus.CONTAINED
        case.work_status = WorkStatus.READY
        case.next_wakeup_at = None
        case.decisions.append(
            Decision(
                decision_id=f"reopen:{len(case.decisions) + 1}",
                policy_id="incident-phase-v1",
                selected_hypothesis_ids=[],
                proposed_actions=["re-diagnose"],
                risk_level="L1",
                approval_required=False,
                approvers=[],
                decision_reason=reason,
                evidence_ids=[],
                created_by="Auditor",
            )
        )
        return self.save(case)

    def append_evidence(self, incident_id: str, evidence: Evidence) -> IncidentCase:
        case = self.get(incident_id)
        if evidence.evidence_id not in case.evidence_refs:
            case.evidence_refs.append(evidence.evidence_id)
        return self.save(case)

    def replace_hypotheses(
        self,
        incident_id: str,
        hypotheses: list[Hypothesis],
    ) -> IncidentCase:
        if not hypotheses:
            raise ValueError("At least one hypothesis is required")
        if any(not 0 <= item.confidence <= 1 for item in hypotheses):
            raise ValueError("Hypothesis confidence must be between 0 and 1")
        case = self.get(incident_id)
        case.hypotheses = hypotheses
        return self.save(case)

    def append_action(self, incident_id: str, action: Action) -> IncidentCase:
        case = self.get(incident_id)
        if any(existing.action_id == action.action_id for existing in case.actions):
            raise ValueError(f"Action {action.action_id} already exists")
        case.actions.append(action)
        if action.approval_id and action.approval_id not in case.approval_refs:
            case.approval_refs.append(action.approval_id)
        return self.save(case)

    def update_action(
        self,
        incident_id: str,
        action_id: str,
        *,
        status: ActionStatus,
        response: dict[str, Any] | None = None,
    ) -> IncidentCase:
        case = self.get(incident_id)
        action = next((item for item in case.actions if item.action_id == action_id), None)
        if action is None:
            raise KeyError(f"Unknown action {action_id}")
        action.status = status
        if response is not None:
            action.response = response
        if status in {ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.REJECTED}:
            action.completed_at = self.store.now()
        return self.save(case)

    def record_verification(
        self,
        incident_id: str,
        verification: Verification,
    ) -> IncidentCase:
        case = self.get(incident_id)
        case.verifications = [
            existing
            for existing in case.verifications
            if existing.verification_id != verification.verification_id
        ]
        case.verifications.append(verification)
        with self.store.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO verifications(
                    verification_id, incident_id, subject, result, verifier,
                    evidence_ids_json, expected_json, observed_json, verified_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    verification.verification_id,
                    incident_id,
                    verification.subject,
                    verification.result.value,
                    verification.verifier,
                    json.dumps(verification.evidence_ids, ensure_ascii=False),
                    json.dumps(verification.expected_condition, ensure_ascii=False),
                    json.dumps(verification.observed_value, ensure_ascii=False),
                    verification.verified_at,
                ),
            )
        return self.save(case)

    def recompute(self, incident_id: str) -> IncidentCase:
        """Refresh entity states and derive aggregate status without trusting an Agent claim."""
        case = self.get(incident_id)
        batches = self.store.list_batches(batch_ids=case.affected_batches)
        case.batch_dispositions = {
            row["batch_id"]: BatchDisposition(row["disposition"]) for row in batches
        }
        holds = self.store.list_sales_holds(incident_id=incident_id)
        case.sales_hold_refs = [row["hold_id"] for row in holds]
        approvals = self.store.list_approvals(incident_id=incident_id)
        case.approval_refs = [row["approval_id"] for row in approvals]
        workorders = self.store.list_workorders(incident_id=incident_id)
        case.workorder_refs = [row["workorder_id"] for row in workorders]

        active_holds = {row["batch_id"] for row in holds if row["status"] == "active"}
        contained = bool(case.affected_batches) and set(case.affected_batches) <= active_holds
        if not contained:
            contained = bool(case.affected_batches) and all(
                case.batch_dispositions.get(batch_id) is BatchDisposition.QUARANTINED
                for batch_id in case.affected_batches
            )

        pending_approvals = [row for row in approvals if row["status"] == "pending"]
        pending_actions = [
            action
            for action in case.actions
            if action.status
            in {
                ActionStatus.PROPOSED,
                ActionStatus.PENDING,
                ActionStatus.APPROVED,
                ActionStatus.EXECUTING,
                ActionStatus.FAILED,
            }
        ]
        batch_terminal = bool(case.affected_batches) and all(
            case.batch_dispositions.get(batch_id) in _TERMINAL_BATCH_STATES
            for batch_id in case.affected_batches
        )
        latest_by_subject: dict[str, Verification] = {}
        for verification in case.verifications:
            latest_by_subject[verification.subject] = verification
        required_subjects = {"device", "batches", "sales_hold"}
        verified = required_subjects <= latest_by_subject.keys() and all(
            latest_by_subject[subject].result is VerificationResult.PASSED
            for subject in required_subjects
        )

        if batch_terminal and not pending_actions and not pending_approvals and verified:
            case.incident_status = IncidentStatus.RESOLVED
            case.work_status = WorkStatus.COMPLETED
        elif contained:
            case.incident_status = IncidentStatus.CONTAINED
            case.work_status = (
                WorkStatus.WAITING_APPROVAL if pending_approvals else WorkStatus.RUNNING
            )
        else:
            case.incident_status = IncidentStatus.OPEN
            case.work_status = WorkStatus.RUNNING
        return self.save(case)

    def close_after_learning(self, incident_id: str) -> IncidentCase:
        case = self.get(incident_id)
        if case.phase is not Phase.LEARN or case.incident_status is not IncidentStatus.RESOLVED:
            raise InvalidTransition("CLOSED requires phase LEARN and status RESOLVED")
        case.incident_status = IncidentStatus.CLOSED
        case.work_status = WorkStatus.COMPLETED
        return self.save(case)

    @staticmethod
    def snapshot(case: IncidentCase) -> dict[str, Any]:
        return asdict(case)
