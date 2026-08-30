"""Quality-gated knowledge candidate, review, publish and retrieval workflow."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from typing import Any

from ..state import StateStoreProtocol
from .embeddings import EmbeddingProvider

_REVIEWERS = {"Human", "food_safety_owner", "hq_reviewer", "knowledge_reviewer"}
_SECRET_PATTERN = re.compile(
    r"(?i)(?:bearer\s+[a-z0-9._-]{12,}|api[_ -]?key\s*[:=]|sk-[a-z0-9_-]{12,})"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list, int, float, bool)):
        return value
    return json.loads(value)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(format(value, ".12g") for value in vector) + "]"


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class KnowledgeService:
    """Knowledge flywheel that never publishes an Auditor candidate automatically."""

    def __init__(self, store: StateStoreProtocol, embedder: EmbeddingProvider) -> None:
        self.store = store
        self.embedder = embedder
        self.store.ensure_schema()

    def create_candidate(
        self,
        *,
        tenant_id: str,
        incident_id: str,
        trace_id: str,
        title: str,
        body: str,
        tags: list[str],
        confidence: float,
        source_evidence_ids: list[str],
        created_by: str = "Auditor",
        dedupe_key: str | None = None,
        audit_request_id: str | None = None,
        audit_created_at: str | None = None,
    ) -> dict[str, Any]:
        title = title.strip()
        body = body.strip()
        if not tenant_id or not incident_id or not trace_id or not title or not body:
            raise ValueError("tenant, incident, trace, title and body are required")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be finite and between 0 and 1")
        normalized_tags = sorted({tag.strip() for tag in tags if tag and tag.strip()})
        evidence_ids = sorted({item for item in source_evidence_ids if item})
        incident = self.store.get_incident(incident_id)
        if incident is not None:
            if incident["tenant_id"] != tenant_id or incident["trace_id"] != trace_id:
                raise ValueError("knowledge tenant/trace does not match its source incident")
            unknown_evidence = sorted(set(evidence_ids) - set(incident.get("evidence_refs", [])))
            if unknown_evidence:
                raise ValueError(
                    "knowledge candidate references evidence outside its source incident: "
                    + ", ".join(unknown_evidence)
                )
        content_to_scan = [title, body, *normalized_tags, *evidence_ids]
        if dedupe_key:
            content_to_scan.append(dedupe_key)
        if _SECRET_PATTERN.search("\n".join(content_to_scan)):
            raise ValueError("knowledge candidate contains a credential-like secret")
        key = (
            dedupe_key
            or hashlib.sha256(
                _canonical(
                    {
                        "tenant_id": tenant_id,
                        "title": title.casefold(),
                        "body": body.casefold(),
                        "tags": normalized_tags,
                    }
                ).encode("utf-8")
            ).hexdigest()
        )
        now = datetime.now(UTC).isoformat(timespec="seconds")
        deduplicated = False
        audit_id = None
        with self.store.transaction() as conn:
            existing = conn.execute(
                """SELECT * FROM knowledge_items
                   WHERE tenant_id = ? AND dedupe_key = ?""",
                (tenant_id, key),
            ).fetchone()
            if existing:
                row = existing
                deduplicated = True
            else:
                knowledge_id = self.store.next_id(conn, "knowledge")
                cursor = conn.execute(
                    """INSERT INTO knowledge_items(
                        knowledge_id, tenant_id, dedupe_key, source_incident_id,
                        source_trace_id, title, body, tags_json, confidence,
                        redaction_status, review_status, source_evidence_ids_json,
                        created_by, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pending', ?, ?, ?)
                    ON CONFLICT(tenant_id, dedupe_key) DO NOTHING""",
                    (
                        knowledge_id,
                        tenant_id,
                        key,
                        incident_id,
                        trace_id,
                        title,
                        body,
                        _canonical(normalized_tags),
                        confidence,
                        _canonical(evidence_ids),
                        created_by,
                        now,
                    ),
                )
                if cursor.rowcount == 0:
                    row = conn.execute(
                        """SELECT * FROM knowledge_items
                           WHERE tenant_id = ? AND dedupe_key = ?""",
                        (tenant_id, key),
                    ).fetchone()
                    deduplicated = True
                else:
                    row = conn.execute(
                        "SELECT * FROM knowledge_items WHERE knowledge_id = ?",
                        (knowledge_id,),
                    ).fetchone()
            if row is not None and audit_request_id and audit_created_at:
                audit_id = self.store.record_audit(
                    conn,
                    request_id=audit_request_id,
                    actor=created_by,
                    tool_name="create_knowledge_candidate",
                    incident_id=incident_id,
                    action_id=None,
                    policy={
                        "policy_id": "knowledge-quality-gate",
                        "policy_version": "1.0",
                        "source_ref": "knowledge_items.review_status",
                    },
                    request={
                        "tenant_id": tenant_id,
                        "trace_id": trace_id,
                        "dedupe_key": key,
                        "confidence": confidence,
                        "source_evidence_ids": evidence_ids,
                    },
                    response={
                        "knowledge_id": row["knowledge_id"],
                        "review_status": row["review_status"],
                        "deduplicated": deduplicated,
                    },
                    created_at=audit_created_at,
                )
        if row is None:
            raise RuntimeError("Knowledge candidate was not persisted")
        return {
            **self._serialize(row),
            "deduplicated": deduplicated,
            "audit_ref": audit_id,
        }

    def review_candidate(
        self,
        *,
        knowledge_id: str,
        decision: str,
        reviewer: str,
        reason: str,
        redaction_passed: bool,
        audit_request_id: str | None = None,
        audit_created_at: str | None = None,
    ) -> dict[str, Any]:
        if reviewer not in _REVIEWERS:
            raise PermissionError("A trusted knowledge reviewer is required")
        normalized = decision.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        if normalized == "approve" and not redaction_passed:
            raise ValueError("A candidate cannot be published before redaction passes")
        if not reason.strip():
            raise ValueError("review reason is required")

        audit_id = None
        with self.store.transaction() as conn:
            lock_clause = " FOR UPDATE" if self.store.backend_name == "postgresql" else ""
            row = conn.execute(
                f"SELECT * FROM knowledge_items WHERE knowledge_id = ?{lock_clause}",
                (knowledge_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown knowledge candidate {knowledge_id}")
            if str(row["created_by"]) == reviewer:
                raise PermissionError("A knowledge candidate cannot be reviewed by its creator")
            target = "published" if normalized == "approve" else "rejected"
            if row["review_status"] == target:
                return {**self._serialize(row), "idempotent_replay": True}
            if row["review_status"] != "pending":
                raise ValueError(
                    f"Candidate is already {row['review_status']} and cannot become {target}"
                )
            now = datetime.now(UTC).isoformat(timespec="seconds")
            redaction_status = "passed" if redaction_passed else "failed"
            if target == "published":
                vector = self.embedder.embed(f"{row['title']}\n{row['body']}")
                if self.store.backend_name == "postgresql":
                    conn.execute(
                        """UPDATE knowledge_items SET review_status = ?, redaction_status = ?,
                           embedding = CAST(? AS vector), embedding_model = ?, reviewed_by = ?,
                           reviewed_at = ?, review_reason = ? WHERE knowledge_id = ?""",
                        (
                            target,
                            redaction_status,
                            _vector_literal(vector),
                            self.embedder.model_name,
                            reviewer,
                            now,
                            reason.strip(),
                            knowledge_id,
                        ),
                    )
                else:
                    conn.execute(
                        """UPDATE knowledge_items SET review_status = ?, redaction_status = ?,
                           embedding_json = ?, embedding_model = ?, reviewed_by = ?,
                           reviewed_at = ?, review_reason = ? WHERE knowledge_id = ?""",
                        (
                            target,
                            redaction_status,
                            _canonical(vector),
                            self.embedder.model_name,
                            reviewer,
                            now,
                            reason.strip(),
                            knowledge_id,
                        ),
                    )
            else:
                conn.execute(
                    """UPDATE knowledge_items SET review_status = ?, redaction_status = ?,
                       reviewed_by = ?, reviewed_at = ?, review_reason = ?
                       WHERE knowledge_id = ?""",
                    (
                        target,
                        redaction_status,
                        reviewer,
                        now,
                        reason.strip(),
                        knowledge_id,
                    ),
                )
            updated = conn.execute(
                "SELECT * FROM knowledge_items WHERE knowledge_id = ?",
                (knowledge_id,),
            ).fetchone()
            if updated is not None and audit_request_id and audit_created_at:
                audit_id = self.store.record_audit(
                    conn,
                    request_id=audit_request_id,
                    actor=reviewer,
                    tool_name="review_knowledge_candidate",
                    incident_id=str(updated["source_incident_id"]),
                    action_id=None,
                    policy={
                        "policy_id": "knowledge-quality-gate",
                        "policy_version": "1.0",
                        "source_ref": "knowledge_items.review_status",
                    },
                    request={
                        "knowledge_id": knowledge_id,
                        "decision": normalized,
                        "redaction_passed": redaction_passed,
                    },
                    response={
                        "review_status": updated["review_status"],
                        "redaction_status": updated["redaction_status"],
                    },
                    created_at=audit_created_at,
                )
        if updated is None:
            raise RuntimeError("Reviewed knowledge item disappeared")
        return {
            **self._serialize(updated),
            "idempotent_replay": False,
            "audit_ref": audit_id,
        }

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        top_k: int = 3,
        minimum_confidence: float = 0.6,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query is required")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        if not math.isfinite(minimum_confidence) or not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be finite and between 0 and 1")
        vector = self.embedder.embed(query)
        if self.store.backend_name == "postgresql":
            literal = _vector_literal(vector)
            connection = self.store.connect()
            try:
                rows = connection.execute(
                    """SELECT knowledge_id, dedupe_key, source_incident_id,
                              source_trace_id, title, body, tags_json, confidence,
                              source_evidence_ids_json, embedding_model,
                              1 - (embedding <=> CAST(? AS vector)) AS score
                       FROM knowledge_items
                       WHERE tenant_id = ? AND review_status = 'published'
                         AND redaction_status = 'passed' AND confidence >= ?
                         AND embedding_model = ? AND embedding IS NOT NULL
                       ORDER BY embedding <=> CAST(? AS vector)
                       LIMIT ?""",
                    (
                        literal,
                        tenant_id,
                        minimum_confidence,
                        self.embedder.model_name,
                        literal,
                        top_k,
                    ),
                ).fetchall()
            finally:
                connection.close()
        else:
            connection = self.store.connect()
            try:
                candidates = connection.execute(
                    """SELECT knowledge_id, dedupe_key, source_incident_id,
                              source_trace_id, title, body, tags_json, confidence,
                              source_evidence_ids_json, embedding_model, embedding_json
                       FROM knowledge_items
                       WHERE tenant_id = ? AND review_status = 'published'
                         AND redaction_status = 'passed' AND confidence >= ?
                         AND embedding_model = ? AND embedding_json IS NOT NULL""",
                    (tenant_id, minimum_confidence, self.embedder.model_name),
                ).fetchall()
            finally:
                connection.close()
            rows = []
            for item in candidates:
                candidate_vector = [float(value) for value in _decode(item["embedding_json"])]
                rows.append({**dict(item), "score": _cosine(vector, candidate_vector)})
            rows.sort(key=lambda item: (-float(item["score"]), item["knowledge_id"]))
            rows = rows[:top_k]

        hits = [self._hit(row) for row in rows]
        return {
            "status": "enabled",
            "provider": self.embedder.model_name,
            "hits": hits,
            "quality_gate": {
                "review_status": "published",
                "redaction_status": "passed",
                "minimum_confidence": minimum_confidence,
            },
        }

    def list_items(
        self,
        *,
        tenant_id: str,
        review_status: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM knowledge_items WHERE tenant_id = ?"
        params: list[Any] = [tenant_id]
        if review_status is not None:
            if review_status not in {"pending", "published", "rejected"}:
                raise ValueError("invalid review status")
            sql += " AND review_status = ?"
            params.append(review_status)
        sql += " ORDER BY created_at, knowledge_id"
        connection = self.store.connect()
        try:
            rows = connection.execute(sql, params).fetchall()
        finally:
            connection.close()
        return [self._serialize(row) for row in rows]

    @staticmethod
    def _serialize(row: Any) -> dict[str, Any]:
        item = dict(row)
        for source, target in (
            ("tags_json", "tags"),
            ("source_evidence_ids_json", "source_evidence_ids"),
        ):
            if source in item:
                item[target] = _decode(item.pop(source))
        item.pop("embedding_json", None)
        item.pop("embedding", None)
        return item

    @staticmethod
    def _hit(row: Any) -> dict[str, Any]:
        item = dict(row)
        body = str(item["body"])
        return {
            "knowledge_id": item["knowledge_id"],
            "dedupe_key": item["dedupe_key"],
            "title": item["title"],
            "score": round(float(item["score"]), 6),
            "confidence": float(item["confidence"]),
            "tags": _decode(item["tags_json"]),
            "source": {
                "incident_id": item["source_incident_id"],
                "trace_id": item["source_trace_id"],
                "evidence_ids": _decode(item["source_evidence_ids_json"]),
                "span": body[:240],
            },
        }
