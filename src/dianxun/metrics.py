"""Small, dependency-free Prometheus metrics for the MCP adapter.

The registry deliberately accepts only a fixed tool-name vocabulary and two
outcomes. Tenant, incident, request, trace and actor identifiers are never
labels, which keeps the series bounded and prevents operational metadata from
leaking through the scrape endpoint.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Iterable

DEFAULT_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
)


class MCPMetrics:
    """Thread-safe, bounded-cardinality MCP metric registry."""

    def __init__(
        self,
        tool_names: Iterable[str],
        *,
        duration_buckets: tuple[float, ...] = DEFAULT_DURATION_BUCKETS,
    ) -> None:
        buckets = tuple(sorted(set(duration_buckets)))
        if not buckets or any(not math.isfinite(item) or item <= 0 for item in buckets):
            raise ValueError("duration buckets must be finite positive values")
        self._known_tools = frozenset(tool_names)
        self._duration_buckets = buckets
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Clear process-local metrics; intended for deterministic tests only."""
        with self._lock:
            self._tool_calls: dict[tuple[str, str], int] = {}
            self._duration_counts: dict[str, int] = {}
            self._duration_sums: dict[str, float] = {}
            self._duration_bucket_counts: dict[str, list[int]] = {}
            self._auth_failures = 0

    def observe_tool_call(self, tool_name: object, *, success: bool, duration: float) -> None:
        tool = (
            tool_name
            if isinstance(tool_name, str) and tool_name in self._known_tools
            else "unknown"
        )
        outcome = "success" if success else "error"
        elapsed = max(0.0, duration) if math.isfinite(duration) else 0.0
        with self._lock:
            key = (tool, outcome)
            self._tool_calls[key] = self._tool_calls.get(key, 0) + 1
            self._duration_counts[tool] = self._duration_counts.get(tool, 0) + 1
            self._duration_sums[tool] = self._duration_sums.get(tool, 0.0) + elapsed
            counts = self._duration_bucket_counts.setdefault(
                tool,
                [0] * len(self._duration_buckets),
            )
            for index, upper_bound in enumerate(self._duration_buckets):
                if elapsed <= upper_bound:
                    counts[index] += 1

    def record_auth_failure(self) -> None:
        with self._lock:
            self._auth_failures += 1

    def render_prometheus(self) -> str:
        """Return a Prometheus text exposition snapshot."""
        with self._lock:
            tool_calls = dict(self._tool_calls)
            duration_counts = dict(self._duration_counts)
            duration_sums = dict(self._duration_sums)
            bucket_counts = {
                tool: list(counts) for tool, counts in self._duration_bucket_counts.items()
            }
            auth_failures = self._auth_failures

        lines = [
            "# HELP dianxun_mcp_tool_calls_total MCP tool calls by bounded tool and outcome.",
            "# TYPE dianxun_mcp_tool_calls_total counter",
        ]
        for (tool, outcome), count in sorted(tool_calls.items()):
            labels = f'outcome="{outcome}",tool="{_escape_label(tool)}"'
            lines.append(f"dianxun_mcp_tool_calls_total{{{labels}}} {count}")

        lines.extend(
            [
                "# HELP dianxun_mcp_tool_duration_seconds MCP tool call duration in seconds.",
                "# TYPE dianxun_mcp_tool_duration_seconds histogram",
            ]
        )
        for tool in sorted(duration_counts):
            escaped_tool = _escape_label(tool)
            counts = bucket_counts[tool]
            for upper_bound, count in zip(self._duration_buckets, counts, strict=True):
                lines.append(
                    "dianxun_mcp_tool_duration_seconds_bucket"
                    f'{{le="{_format_bound(upper_bound)}",tool="{escaped_tool}"}} {count}'
                )
            lines.append(
                "dianxun_mcp_tool_duration_seconds_bucket"
                f'{{le="+Inf",tool="{escaped_tool}"}} {duration_counts[tool]}'
            )
            lines.append(
                "dianxun_mcp_tool_duration_seconds_sum"
                f'{{tool="{escaped_tool}"}} {_format_float(duration_sums[tool])}'
            )
            lines.append(
                "dianxun_mcp_tool_duration_seconds_count"
                f'{{tool="{escaped_tool}"}} {duration_counts[tool]}'
            )

        lines.extend(
            [
                "# HELP dianxun_mcp_auth_failures_total Rejected MCP bearer authentications.",
                "# TYPE dianxun_mcp_auth_failures_total counter",
                f"dianxun_mcp_auth_failures_total {auth_failures}",
            ]
        )
        return "\n".join(lines) + "\n"


def _format_bound(value: float) -> str:
    return format(value, ".15g")


def _format_float(value: float) -> str:
    return format(value, ".15g")


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
