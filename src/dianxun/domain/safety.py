"""Current goods facts required for safe incident resolution."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .evidence import timestamp

TERMINAL_BATCH_STATES = frozenset({"transferred", "released", "disposed"})


def batches_are_safe_terminal(
    batches: Sequence[Mapping[str, Any]],
    expected_ids: Sequence[str],
    *,
    receipts: Sequence[Mapping[str, Any]] = (),
    actions: Sequence[Mapping[str, Any]] = (),
    now: str | None = None,
) -> bool:
    """Require complete scope; released goods must still be safe for sale."""
    return (
        bool(expected_ids)
        and len(batches) == len(set(expected_ids))
        and {row.get("batch_id") for row in batches} == set(expected_ids)
        and all(
            row.get("disposition") in TERMINAL_BATCH_STATES
            and (row.get("disposition") != "released" or row.get("safe_for_sale") in (True, 1))
            and (
                row.get("disposition") == "released"
                or _physical_receipts_complete(row, receipts, actions, now)
            )
            for row in batches
        )
    )


def _physical_receipts_complete(batch, receipts, actions, now) -> bool:
    try:
        current = [
            action
            for action in actions
            if action["tool_name"] == "apply_batch_disposition"
            and action["status"] == "completed"
            and batch["batch_id"] in action["request"]["batch_ids"]
            and action["request"]["disposition"] == batch["disposition"]
            and timestamp(action["updated_at"]) == timestamp(batch["updated_at"])
        ]
        # Same-clock re-execution must not borrow a previous action's receipt.
        # When timestamps tie, require evidence for every candidate action.
        return bool(current) and all(
            any(_receipt_matches(batch, receipt, [action], now) for receipt in receipts)
            for action in current
        )
    except (KeyError, TypeError, ValueError):
        return False


def _receipt_matches(batch, receipt, actions, now) -> bool:
    """A status write is not physical receipt; require independent scoped evidence."""
    try:
        meta = receipt["metadata"]
        kind = batch["disposition"]
        action = next(a for a in actions if a["action_id"] == receipt["action_id"])
        request = action["request"]
        quantity = float(meta["quantity"])
        if not (
            now
            and receipt["evidence_type"] == "disposition_receipt"
            and receipt["actor"] in {"Human", "ScenarioEngine"}
            and receipt["incident_id"] == action["incident_id"]
            and action["status"] == "completed"
            and action["tool_name"] == "apply_batch_disposition"
            and batch["batch_id"] in request["batch_ids"]
            and request["disposition"] == kind == meta["disposition"]
            and meta["batch_id"] == batch["batch_id"]
            and timestamp(action["updated_at"]) == timestamp(batch["updated_at"])
            and timestamp(batch["updated_at"])
            <= timestamp(receipt["observed_at"])
            <= timestamp(now)
            and math.isfinite(quantity)
            and not isinstance(meta["quantity"], bool)
            and quantity > 0
            and quantity == float(batch["quantity"])
            and meta["source_location"] == batch["device_id"]
            and meta["receipt_ref"]
            and receipt["sha256"]
            and meta["executor_id"]
            and meta["confirmed_by"]
            and meta["executor_id"] != meta["confirmed_by"]
        ):
            return False
        if kind == "transferred":
            temperature = float(meta["destination_temp_c"])
            return bool(
                meta["destination_location"] != meta["source_location"]
                and meta["destination_location"]
                and meta["received"] is True
                and math.isfinite(temperature)
                and not isinstance(meta["destination_temp_c"], bool)
                and float(batch["storage_min_c"]) <= temperature <= float(batch["storage_max_c"])
            )
        return bool(meta["disposal_method"] and meta["destroyed"] is True)
    except (KeyError, TypeError, ValueError, StopIteration):
        return False
