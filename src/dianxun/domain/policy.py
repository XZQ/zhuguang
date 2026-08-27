"""Versioned, deterministic policy evaluation for controlled writes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    risk_level: str
    approval_required: bool
    approvers: tuple[str, ...]
    policy_id: str
    policy_version: str
    effective_at: str
    source_ref: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "approvers": list(self.approvers),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "effective_at": self.effective_at,
            "source_ref": self.source_ref,
            "reason": self.reason,
        }


class PolicyEngine:
    """Loads one immutable policy document and evaluates an action."""

    def __init__(self, policy_path: str | Path) -> None:
        self.path = Path(policy_path)
        self.policy = json.loads(self.path.read_text(encoding="utf-8"))
        if not self.policy.get("immutable"):
            raise ValueError("Policy document must be immutable and versioned")

    def evaluate(
        self,
        *,
        actor: str,
        action_type: str,
        amount: float | None = None,
        disposition: str | None = None,
    ) -> PolicyDecision:
        key = f"{action_type}:{disposition}" if disposition else action_type
        rule = self.policy["actions"].get(key)
        if rule is None:
            return self._decision(
                allowed=False,
                risk_level="L3",
                approval_required=False,
                approvers=(),
                reason=f"No policy rule for {key}",
            )

        allowed_actors = tuple(rule.get("allowed_actors", []))
        if actor not in allowed_actors:
            return self._decision(
                allowed=False,
                risk_level=rule["risk_level"],
                approval_required=False,
                approvers=(),
                reason=f"Actor {actor} is not allowed to perform {key}",
            )

        approval_required = bool(rule.get("approval_required", False))
        threshold = rule.get("approval_required_above_amount")
        if threshold is not None and amount is not None:
            approval_required = amount > float(threshold)
        return self._decision(
            allowed=True,
            risk_level=rule["risk_level"],
            approval_required=approval_required,
            approvers=tuple(rule.get("approvers", [])) if approval_required else (),
            reason=f"Matched {key} in {self.policy['policy_id']}:{self.policy['policy_version']}",
        )

    def _decision(
        self,
        *,
        allowed: bool,
        risk_level: str,
        approval_required: bool,
        approvers: tuple[str, ...],
        reason: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            allowed=allowed,
            risk_level=risk_level,
            approval_required=approval_required,
            approvers=approvers,
            policy_id=self.policy["policy_id"],
            policy_version=self.policy["policy_version"],
            effective_at=self.policy["effective_at"],
            source_ref=self.policy["source_ref"],
            reason=reason,
        )
