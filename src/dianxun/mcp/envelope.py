"""Uniform response envelope shared by all P0 MCP functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolEnvelope:
    ok: bool
    data: Any
    error: dict[str, Any] | None
    request_id: str
    source: str
    source_ts: str
    partial: bool
    audit_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "request_id": self.request_id,
            "source": self.source,
            "source_ts": self.source_ts,
            "partial": self.partial,
            "audit_ref": self.audit_ref,
        }
