"""P0 cold-chain batch exposure assessment.

This skill recommends a disposition but never writes inventory state and never
releases a batch. Thresholds come from the versioned competition-demo policy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .. import trace
from ..domain.evidence import coverage_issues, manual_temperatures, temperature_series
from .contracts import enforce_output_contract


@enforce_output_contract("coldchain-risk-assess")
def coldchain_risk_assess(
    *,
    incident_id: str,
    device_series: list[dict[str, Any]],
    affected_batches: list[dict[str, Any]],
    policy: dict[str, Any],
    trace_id: str,
    manual_measurements: list[dict[str, Any]] | None = None,
    assessed_at: str | None = None,
) -> dict[str, Any]:
    """Calculate batch-specific degree-minute exposure and recommendations."""
    with trace.span(
        "coldchain-risk-assess",
        "skill",
        trace_id,
        input={"incident_id": incident_id, "batch_count": len(affected_batches)},
    ) as sp:
        now = assessed_at or datetime.now(UTC).isoformat()
        trusted, excluded = temperature_series(device_series, now=now)
        issues = coverage_issues(trusted, now=now)
        if any(str(item.get("quality", "good")).lower() == "good" for item in excluded):
            issues.append("invalid_or_conflicting_observations")
        manual = manual_measurements or []
        exposure_policy = policy.get("exposure", {})
        transfer_limit = float(exposure_policy.get("transfer_max_degree_minutes", 60.0))
        assessments: list[dict[str, Any]] = []
        for batch in affected_batches:
            maximum = float(batch["storage_max_c"])
            degree_minutes, over_minutes = _degree_minutes(trusted, maximum)
            measured = manual_temperatures(manual, batch=batch, incident_id=incident_id, now=now)
            minimum = float(batch.get("storage_min_c", 0))
            manual_normal = bool(measured) and all(
                minimum <= temperature <= maximum for temperature in measured
            )
            if issues:
                recommendation = "quarantined"
                reason = issues[0]
            elif any(float(item["temp_c"]) < minimum for item in trusted):
                recommendation = "quarantined"
                reason = "below_storage_minimum_requires_review"
            elif excluded and not manual_normal:
                recommendation = "quarantined"
                reason = "suspect_readings_require_independent_corroboration"
            elif degree_minutes <= 0 and manual_normal:
                recommendation = "released"
                reason = "no_trusted_exposure_and_manual_measurement_normal"
            elif degree_minutes <= transfer_limit:
                recommendation = "transferred"
                reason = "limited_exposure_requires_controlled_transfer"
            else:
                recommendation = "disposed"
                reason = "exposure_exceeds_demo_policy"
            assessments.append(
                {
                    "batch_id": batch["batch_id"],
                    "storage_max_c": maximum,
                    "degree_minutes": round(degree_minutes, 2),
                    "over_limit_minutes": round(over_minutes, 2),
                    "recommendation": recommendation,
                    "reason": reason,
                    "policy_ref": batch.get("policy_ref"),
                    "requires_approval": recommendation in {"transferred", "released", "disposed"},
                    "evidence_quality": (
                        "unknown"
                        if issues
                        else "corroborated"
                        if excluded and manual_normal
                        else "uncorroborated"
                        if excluded
                        else "trusted"
                    ),
                    "coverage_status": "unknown" if issues else "observed_window_only",
                    "coverage_issues": issues,
                }
            )
        result = {
            "incident_id": incident_id,
            "affected_batches": [item["batch_id"] for item in affected_batches],
            "exposure_assessment": assessments,
            "containment_actions": ["apply_sales_hold", "quarantine_batches"],
            "required_approvals": [
                {"batch_id": item["batch_id"], "disposition": item["recommendation"]}
                for item in assessments
                if item["requires_approval"]
            ],
            "manual_measurements": manual,
            "data_quality": {
                "total_readings": len(device_series),
                "trusted_readings": len(trusted),
                "excluded_readings": len(excluded),
                "excluded_qualities": sorted(
                    {str(item.get("quality", "unknown")) for item in excluded}
                ),
            },
            "evidence_refs": [],
            "policy": {
                "policy_id": policy["policy_id"],
                "policy_version": policy["policy_version"],
                "source_ref": policy["source_ref"],
                "scope": policy["scope"],
            },
        }
        sp.output = {
            "recommendations": {item["batch_id"]: item["recommendation"] for item in assessments}
        }
        return result


def _degree_minutes(series: list[dict[str, Any]], maximum: float) -> tuple[float, float]:
    degree_minutes = 0.0
    over_minutes = 0.0
    for left, right in zip(series, series[1:], strict=False):
        start = datetime.fromisoformat(left["observed_at"])
        end = datetime.fromisoformat(right["observed_at"])
        minutes = max(0.0, (end - start).total_seconds() / 60.0)
        left_over = max(0.0, float(left["temp_c"]) - maximum)
        right_over = max(0.0, float(right["temp_c"]) - maximum)
        degree_minutes += (left_over + right_over) * 0.5 * minutes
        if left_over > 0 or right_over > 0:
            over_minutes += minutes
    return degree_minutes, over_minutes
