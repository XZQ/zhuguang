"""Current goods facts required for safe incident resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TERMINAL_BATCH_STATES = frozenset({"transferred", "released", "disposed"})


def batches_are_safe_terminal(
    batches: Sequence[Mapping[str, Any]], expected_ids: Sequence[str]
) -> bool:
    """Require complete scope; released goods must still be safe for sale."""
    return (
        bool(expected_ids)
        and len(batches) == len(set(expected_ids))
        and {row.get("batch_id") for row in batches} == set(expected_ids)
        and all(
            row.get("disposition") in TERMINAL_BATCH_STATES
            and (row.get("disposition") != "released" or row.get("safe_for_sale") in (True, 1))
            for row in batches
        )
    )
