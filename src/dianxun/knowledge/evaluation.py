"""Retrieval metrics for labeled, explicitly sourced knowledge datasets."""

from __future__ import annotations

from typing import Any

from .repository import KnowledgeService


def evaluate_retrieval(
    service: KnowledgeService,
    *,
    tenant_id: str,
    cases: list[dict[str, Any]],
    top_k: int = 3,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("At least one labeled retrieval case is required")
    reciprocal_ranks: list[float] = []
    recalled = 0
    rows = []
    for case in cases:
        expected = set(case.get("expected_knowledge_ids", []))
        if not expected:
            raise ValueError("Every retrieval case needs expected_knowledge_ids")
        result = service.search(tenant_id=tenant_id, query=case["query"], top_k=top_k)
        actual = [hit["knowledge_id"] for hit in result["hits"]]
        rank = next((index for index, item in enumerate(actual, 1) if item in expected), None)
        if rank is not None:
            recalled += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
        rows.append(
            {
                "case_id": case["case_id"],
                "expected_knowledge_ids": sorted(expected),
                "actual_knowledge_ids": actual,
                "first_relevant_rank": rank,
            }
        )
    count = len(cases)
    return {
        "dataset_label": "caller_supplied",
        "case_count": count,
        f"recall_at_{top_k}": recalled / count,
        "mrr": sum(reciprocal_ranks) / count,
        "cases": rows,
        "claim_boundary": (
            "Metrics describe only the supplied labeled dataset; they are not a real-store "
            "business improvement claim."
        ),
    }
