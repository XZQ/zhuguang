"""Backward-compatible facade over the quality-gated knowledge workflow.

Legacy supplementary demos keep using this module, but ``add`` now creates a
pending candidate.  It never auto-publishes knowledge into retrieval results.
"""

from __future__ import annotations

from pathlib import Path

from ..state import SQLiteStateStore
from .embeddings import HashEmbeddingProvider
from .repository import KnowledgeService

_DB = Path(__file__).resolve().parents[3] / "data" / "knowledge.db"
_TENANT = "legacy-demo"


def _service() -> KnowledgeService:
    return KnowledgeService(SQLiteStateStore(_DB), HashEmbeddingProvider())


def init() -> None:
    """Create the local candidate schema without publishing any entries."""
    _service()


def add(
    title: str,
    body: str,
    tags: list[str],
    confidence: float,
    trace_id: str = "",
) -> str | None:
    """Create a pending candidate; retained for supplementary-demo compatibility."""
    trace = trace_id or "legacy-unassigned"
    result = _service().create_candidate(
        tenant_id=_TENANT,
        incident_id=f"legacy:{trace}",
        trace_id=trace,
        title=title,
        body=body,
        tags=tags,
        confidence=confidence,
        source_evidence_ids=[],
        created_by="Auditor",
    )
    return str(result["knowledge_id"])


def search(query: str, topk: int = 5) -> list[dict]:
    """Retrieve only reviewed and redaction-passed entries."""
    return _service().search(tenant_id=_TENANT, query=query, top_k=topk)["hits"]


def all_entries() -> list[dict]:
    return _service().list_items(tenant_id=_TENANT)


def review(
    knowledge_id: str,
    *,
    decision: str,
    reviewer: str,
    reason: str,
    redaction_passed: bool,
) -> dict:
    return _service().review_candidate(
        knowledge_id=knowledge_id,
        decision=decision,
        reviewer=reviewer,
        reason=reason,
        redaction_passed=redaction_passed,
    )
