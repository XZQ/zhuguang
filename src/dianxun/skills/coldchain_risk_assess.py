"""P0 cold-chain batch exposure assessment.

This skill recommends a disposition but never writes inventory state and never
releases a batch. Thresholds come from the versioned competition-demo policy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .. import trace


def coldchain_risk_assess(
    *,
    incident_id: str,
    device_series: list[dict[str, Any]],
    affected_batches: list[dict[str, Any]],
    policy: dict[str, Any],
    trace_id: str,
    manual_measurements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calculate batch-specific degree-minute exposure and recommendations."""
    with trace.span(
        "coldchain-risk-assess",
        "skill",
        trace_id,
        input={"incident_id": incident_id, "batch_count": len(affected_batches)},
    ) as sp:
        ordered = sorted(device_series, key=lambda item: item["observed_at"])
        trusted = [item for item in ordered if str(item.get("quality", "good")).lower() == "good"]
        excluded = [item for item in ordered if item not in trusted]
        manual = manual_measurements or []
        exposure_policy = policy.get("exposure", {})
        transfer_limit = float(exposure_policy.get("transfer_max_degree_minutes", 60.0))
        assessments: list[dict[str, Any]] = []
        for batch in affected_batches:
            maximum = float(batch["storage_max_c"])
            degree_minutes, over_minutes = _degree_minutes(trusted, maximum)
            manual_temperatures = _manual_temperatures(manual)
            manual_normal = bool(manual_temperatures) and all(
                temperature <= maximum for temperature in manual_temperatures
            )
            if not trusted:
                recommendation = "quarantined"
                reason = "trusted_temperature_series_missing"
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
                    "evidence_quality": "corroborated" if excluded and manual_normal else "trusted",
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
                "total_readings": len(ordered),
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


def _manual_temperatures(items: list[dict[str, Any]]) -> list[float]:
    temperatures: list[float] = []
    for item in items:
        metadata = item.get("metadata") or {}
        if metadata.get("temp_c") is not None:
            temperatures.append(float(metadata["temp_c"]))
    return temperatures
