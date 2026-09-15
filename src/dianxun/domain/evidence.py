"""Conservative measurement gates shared by diagnosis and independent review."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Evidence timestamps require a timezone")
    return parsed.astimezone(UTC)


def temperature_series(
    readings: list[dict[str, Any]], *, now: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deduplicate source timestamps; conflicting duplicates are untrusted."""
    current = timestamp(now)
    groups: dict[tuple, list[dict[str, Any]]] = {}
    excluded = []
    for item in readings:
        try:
            observed = timestamp(item["observed_at"])
            if isinstance(item["temp_c"], bool):
                raise ValueError("Temperature must be numeric, not boolean")
            temperature = float(item["temp_c"])
            if observed > current or not math.isfinite(temperature):
                raise ValueError("Invalid temperature observation")
        except (KeyError, TypeError, ValueError):
            excluded.append(item)
            continue
        key = (observed, item.get("source", "unknown"), item.get("device_id"))
        groups.setdefault(key, []).append(item)
    trusted = []
    for (observed, _, _), items in groups.items():
        values = {float(item["temp_c"]) for item in items}
        if len(values) != 1 or any(
            str(item.get("quality", "good")).lower() != "good" for item in items
        ):
            excluded.extend(items)
        else:
            trusted.append({**items[0], "observed_at": observed.isoformat()})
    # Different sources disagreeing at the same time cannot be averaged into safety.
    by_time: dict[str, list[dict[str, Any]]] = {}
    for item in trusted:
        by_time.setdefault(item["observed_at"], []).append(item)
    unique = []
    for items in by_time.values():
        if len({float(item["temp_c"]) for item in items}) != 1:
            excluded.extend(items)
        else:
            unique.append(items[0])
    return sorted(unique, key=lambda item: item["observed_at"]), excluded


def coverage_issues(series: list[dict[str, Any]], *, now: str, max_gap: float = 30) -> list[str]:
    if len(series) < 2:
        return ["insufficient_distinct_samples"]
    times = [timestamp(item["observed_at"]) for item in series]
    issues = []
    age = (timestamp(now) - times[-1]).total_seconds() / 60
    if age < 0 or age > 5:
        issues.append("latest_sample_not_current")
    if any((b - a).total_seconds() / 60 > max_gap for a, b in zip(times, times[1:], strict=False)):
        issues.append("temperature_coverage_gap")
    return issues


def manual_temperatures(
    items: list[dict[str, Any]], *, batch: dict[str, Any], incident_id: str, now: str
) -> list[float]:
    current = timestamp(now)
    values = []
    for item in items:
        meta = item.get("metadata", {})
        try:
            observed = timestamp(item["observed_at"])
            calibrated = timestamp(meta["calibrated_at"])
            expires = timestamp(meta["calibration_valid_until"])
            temperature = float(meta["temp_c"])
            valid = (
                not isinstance(meta["temp_c"], bool)
                and item.get("incident_id") == incident_id
                and item.get("evidence_type") == "manual_temperature"
                and item.get("actor") in {"Human", "ScenarioEngine"}
                and meta.get("batch_id") == batch["batch_id"]
                and meta.get("device_id") == batch["device_id"]
                and bool(meta.get("instrument_id"))
                and meta.get("measurement_point") == "product"
                and calibrated <= observed <= current <= expires
                and (current - observed).total_seconds() <= 300
                and math.isfinite(temperature)
            )
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            values.append(temperature)
    return values
