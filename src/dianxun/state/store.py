"""Persistent business state shared by the demo, MCP adapter and AgentTeams adapter."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..domain.enums import ApprovalStatus, BatchDisposition, WorkOrderStatus
from .protocols import ConnectionProtocol

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    model TEXT NOT NULL,
    health_state TEXT NOT NULL,
    door_state TEXT NOT NULL,
    power_state TEXT NOT NULL,
    compressor_state TEXT NOT NULL,
    ambient_temp_c REAL NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_readings (
    reading_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    temp_c REAL NOT NULL,
    quality TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_readings
    ON device_readings(device_id, observed_at);

CREATE TABLE IF NOT EXISTS inventory_batches (
    batch_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    storage_min_c REAL NOT NULL,
    storage_max_c REAL NOT NULL,
    disposition TEXT NOT NULL,
    safe_for_sale INTEGER NOT NULL,
    policy_ref TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batches_device ON inventory_batches(device_id);

CREATE TABLE IF NOT EXISTS sales_holds (
    hold_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    batch_id TEXT,
    sku_id TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    released_at TEXT,
    approval_id TEXT,
    verification_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_holds_incident ON sales_holds(incident_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_hold_incident_batch
    ON sales_holds(incident_id, batch_id)
    WHERE status = 'active' AND batch_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    approvers_json TEXT NOT NULL,
    deadline TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_approvals_action ON approvals(action_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_approvals_action ON approvals(action_id);

CREATE TABLE IF NOT EXISTS workorders (
    workorder_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    fault TEXT NOT NULL,
    budget REAL NOT NULL,
    status TEXT NOT NULL,
    assignee TEXT,
    completion_evidence_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workorders_incident ON workorders(incident_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_workorders_action ON workorders(action_id);

CREATE TABLE IF NOT EXISTS manual_evidence (
    evidence_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT,
    actor TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    uri TEXT,
    note TEXT,
    sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    incident_status TEXT NOT NULL,
    work_status TEXT NOT NULL,
    case_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_id TEXT,
    request_json TEXT NOT NULL,
    response_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_incident ON actions(incident_id);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    result TEXT NOT NULL,
    verifier TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    observed_json TEXT NOT NULL,
    verified_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verifications_incident
    ON verifications(incident_id, subject);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    trace_id TEXT,
    tenant_id TEXT,
    actor TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    incident_id TEXT,
    action_id TEXT,
    policy_id TEXT,
    policy_version TEXT,
    policy_source_ref TEXT,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_log(request_id);

CREATE TABLE IF NOT EXISTS idempotency (
    idempotency_key TEXT PRIMARY KEY,
    tenant_id TEXT,
    tool_name TEXT NOT NULL,
    response_json TEXT NOT NULL,
    audit_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_failures (
    tool_name TEXT PRIMARY KEY,
    remaining_calls INTEGER NOT NULL,
    error_code TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    knowledge_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    source_incident_id TEXT NOT NULL,
    source_trace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    redaction_status TEXT NOT NULL CHECK (redaction_status IN ('pending', 'passed', 'failed')),
    review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'published', 'rejected')),
    source_evidence_ids_json TEXT NOT NULL,
    embedding_json TEXT,
    embedding_model TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_reason TEXT,
    UNIQUE (tenant_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_quality
    ON knowledge_items(tenant_id, review_status, redaction_status, confidence DESC);

CREATE TABLE IF NOT EXISTS review_jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    review_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    requested_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    UNIQUE (tenant_id, review_date)
);

CREATE TABLE IF NOT EXISTS supplier_contracts (
    supplier_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    contract_terms_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, supplier_id)
);
"""

_RESET_TABLES = (
    "tool_failures",
    "idempotency",
    "audit_log",
    "verifications",
    "actions",
    "incidents",
    "manual_evidence",
    "workorders",
    "approvals",
    "sales_holds",
    "inventory_batches",
    "device_readings",
    "devices",
    "stores",
    "meta",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ensure_tz(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class SQLiteStateStore:
    """Small repository with explicit, auditable SQL mutations."""

    backend_name = "sqlite"

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.database_identity = str(self.path.resolve())

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_schema(self) -> None:
        with closing(self.connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def ensure_schema(self) -> None:
        """Create the local schema; remote backends only verify readiness."""
        self.create_schema()

    def initialize(self, seed: dict[str, Any], *, reset: bool = True) -> str:
        """Initialize a deterministic world and return its canonical digest."""
        self.create_schema()
        with self.transaction() as conn:
            if reset:
                for table in _RESET_TABLES:
                    conn.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed allow-list
            anchor_time = seed["anchor_time"]
            meta = {
                "seed_id": seed["seed_id"],
                "seed_schema_version": str(seed["schema_version"]),
                "anchor_time": anchor_time,
                "virtual_time": anchor_time,
            }
            conn.executemany(
                """INSERT INTO meta(key, value) VALUES(?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                meta.items(),
            )
            for row in seed.get("stores", []):
                conn.execute(
                    "INSERT INTO stores(store_id, tenant_id, name, timezone) VALUES(?, ?, ?, ?)",
                    (row["store_id"], row["tenant_id"], row["name"], row["timezone"]),
                )
            for row in seed.get("devices", []):
                conn.execute(
                    """INSERT INTO devices(
                        device_id, store_id, model, health_state, door_state, power_state,
                        compressor_state, ambient_temp_c, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["device_id"],
                        row["store_id"],
                        row["model"],
                        row["health_state"],
                        row["door_state"],
                        row["power_state"],
                        row["compressor_state"],
                        row["ambient_temp_c"],
                        anchor_time,
                    ),
                )
            for row in seed.get("device_readings", []):
                conn.execute(
                    """INSERT INTO device_readings(
                        reading_id, device_id, observed_at, temp_c, quality, source
                    ) VALUES(?, ?, ?, ?, ?, ?)""",
                    (
                        row["reading_id"],
                        row["device_id"],
                        row["observed_at"],
                        row["temp_c"],
                        row.get("quality", "good"),
                        row.get("source", "seed"),
                    ),
                )
            for row in seed.get("inventory_batches", []):
                conn.execute(
                    """INSERT INTO inventory_batches(
                        batch_id, store_id, device_id, sku_id, product_name, quantity,
                        storage_min_c, storage_max_c, disposition, safe_for_sale,
                        policy_ref, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["batch_id"],
                        row["store_id"],
                        row["device_id"],
                        row["sku_id"],
                        row["product_name"],
                        row["quantity"],
                        row["storage_min_c"],
                        row["storage_max_c"],
                        row.get("disposition", BatchDisposition.UNKNOWN.value),
                        int(row.get("safe_for_sale", True)),
                        row["policy_ref"],
                        anchor_time,
                    ),
                )
        digest = self.snapshot_digest()
        self.set_meta("seed_digest", digest)
        return digest

    def initialize_from_file(self, seed_path: str | Path, *, reset: bool = True) -> str:
        seed = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        return self.initialize(seed, reset=reset)

    def get_meta(self, key: str) -> str | None:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO meta(key, value) VALUES(?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )

    def now(self) -> str:
        value = self.get_meta("virtual_time")
        if value is None:
            raise RuntimeError("State store is not initialized")
        return value

    def advance_time(self, *, minutes: int) -> str:
        if minutes < 0:
            raise ValueError("Virtual time cannot move backwards")
        current = _ensure_tz(self.now())
        updated = (current + timedelta(minutes=minutes)).isoformat(timespec="seconds")
        self.set_meta("virtual_time", updated)
        self.expire_approvals()
        return updated

    def snapshot_digest(self) -> str:
        snapshot: dict[str, list[dict[str, Any]]] = {}
        with closing(self.connect()) as conn:
            for table, order_by in (
                ("stores", "store_id"),
                ("devices", "device_id"),
                ("device_readings", "reading_id"),
                ("inventory_batches", "batch_id"),
            ):
                rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
                snapshot[table] = [dict(row) for row in rows]
        return hashlib.sha256(_canonical(snapshot).encode("utf-8")).hexdigest()

    def next_id(self, conn: ConnectionProtocol, prefix: str) -> str:
        key = f"seq:{prefix}"
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        value = int(row["value"]) + 1 if row else 1
        conn.execute(
            """INSERT INTO meta(key, value) VALUES(?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, str(value)),
        )
        return f"{prefix}_{value:06d}"

    def list_devices(
        self,
        *,
        device_id: str | None = None,
        store_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if device_id:
            clauses.append("device_id = ?")
            params.append(device_id)
        if store_id:
            clauses.append("store_id = ?")
            params.append(store_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM devices{where} ORDER BY device_id",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_device_readings(
        self,
        *,
        device_id: str,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM device_readings WHERE device_id = ?"
        params: list[Any] = [device_id]
        if since:
            sql += " AND observed_at >= ?"
            params.append(since)
        sql += " ORDER BY observed_at"
        with closing(self.connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def list_batches(
        self,
        *,
        device_id: str | None = None,
        store_id: str | None = None,
        batch_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if device_id:
            clauses.append("device_id = ?")
            params.append(device_id)
        if store_id:
            clauses.append("store_id = ?")
            params.append(store_id)
        if batch_ids:
            placeholders = ",".join("?" for _ in batch_ids)
            clauses.append(f"batch_id IN ({placeholders})")
            params.extend(batch_ids)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM inventory_batches{where} ORDER BY batch_id",
                params,
            ).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["safe_for_sale"] = bool(item["safe_for_sale"])
        return result

    def list_sales_holds(
        self,
        *,
        incident_id: str | None = None,
        batch_ids: list[str] | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if incident_id:
            clauses.append("incident_id = ?")
            params.append(incident_id)
        if batch_ids:
            placeholders = ",".join("?" for _ in batch_ids)
            clauses.append(f"batch_id IN ({placeholders})")
            params.extend(batch_ids)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM sales_holds{where} ORDER BY hold_id",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_approvals(
        self,
        *,
        approval_id: str | None = None,
        action_id: str | None = None,
        incident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._filtered_rows(
            "approvals",
            "approval_id",
            {"approval_id": approval_id, "action_id": action_id, "incident_id": incident_id},
        )
        return [self._decode_json_columns(row) for row in rows]

    def list_workorders(
        self,
        *,
        workorder_id: str | None = None,
        action_id: str | None = None,
        incident_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._filtered_rows(
            "workorders",
            "workorder_id",
            {
                "workorder_id": workorder_id,
                "action_id": action_id,
                "incident_id": incident_id,
            },
        )
        return [self._decode_json_columns(row) for row in rows]

    def list_verifications(
        self,
        *,
        incident_id: str,
        subject: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._filtered_rows(
            "verifications",
            "verification_id",
            {"incident_id": incident_id, "subject": subject},
        )
        return [self._decode_json_columns(row) for row in rows]

    def list_actions(
        self,
        *,
        incident_id: str,
        action_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._filtered_rows(
            "actions",
            "action_id",
            {"incident_id": incident_id, "action_id": action_id},
        )
        return [self._decode_json_columns(row) for row in rows]

    def list_manual_evidence(self, *, incident_id: str) -> list[dict[str, Any]]:
        rows = self._filtered_rows(
            "manual_evidence",
            "evidence_id",
            {"incident_id": incident_id},
        )
        return [self._decode_json_columns(row) for row in rows]

    def list_audit_log(self, *, incident_id: str) -> list[dict[str, Any]]:
        rows = self._filtered_rows(
            "audit_log",
            "created_at, audit_id",
            {"incident_id": incident_id},
        )
        return [self._decode_json_columns(row) for row in rows]

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as conn:
            row = conn.execute(
                "SELECT case_json FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        value = row["case_json"]
        return json.loads(value) if isinstance(value, str) else dict(value)

    def save_incident(self, case: dict[str, Any]) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO incidents(
                    incident_id, trace_id, tenant_id, store_id, phase, incident_status,
                    work_status, case_json, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    trace_id=excluded.trace_id,
                    tenant_id=excluded.tenant_id,
                    store_id=excluded.store_id,
                    phase=excluded.phase,
                    incident_status=excluded.incident_status,
                    work_status=excluded.work_status,
                    case_json=excluded.case_json,
                    updated_at=excluded.updated_at""",
                (
                    case["incident_id"],
                    case["trace_id"],
                    case["tenant_id"],
                    case["store_id"],
                    case["phase"],
                    case["incident_status"],
                    case["work_status"],
                    _canonical(case),
                    case["updated_at"],
                ),
            )

    def idempotent_result(
        self,
        conn: ConnectionProtocol,
        *,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT i.tool_name, i.response_json, i.audit_id, a.actor, a.request_json
               FROM idempotency AS i
               LEFT JOIN audit_log AS a ON a.audit_id = i.audit_id
               WHERE i.idempotency_key = ?""",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "tool_name": row["tool_name"],
            "actor": row["actor"],
            "request": self._decode_json_value(row["request_json"]),
            "data": self._decode_json_value(row["response_json"]),
            "audit_id": row["audit_id"],
            "replayed": True,
        }

    def save_idempotent_result(
        self,
        conn: ConnectionProtocol,
        *,
        tool_name: str,
        idempotency_key: str,
        data: dict[str, Any],
        audit_id: str,
        created_at: str,
    ) -> None:
        conn.execute(
            """INSERT INTO idempotency(
                idempotency_key, tenant_id, tool_name, response_json, audit_id, created_at
            ) SELECT ?, tenant_id, ?, ?, ?, ? FROM audit_log WHERE audit_id = ?""",
            (
                idempotency_key,
                tool_name,
                _canonical(data),
                audit_id,
                created_at,
                audit_id,
            ),
        )

    def record_audit(
        self,
        conn: ConnectionProtocol,
        *,
        request_id: str,
        actor: str,
        tool_name: str,
        incident_id: str | None,
        action_id: str | None,
        policy: dict[str, Any] | None,
        request: dict[str, Any],
        response: dict[str, Any],
        created_at: str,
    ) -> str:
        audit_id = self.next_id(conn, "audit")
        policy = policy or {}
        tenant_id: str | None = getattr(self, "tenant_id", None)
        trace_id: str | None = None
        if incident_id:
            incident = conn.execute(
                "SELECT tenant_id, trace_id FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
            if incident:
                tenant_id = str(incident["tenant_id"])
                trace_id = str(incident["trace_id"])
        conn.execute(
            """INSERT INTO audit_log(
                audit_id, request_id, trace_id, tenant_id, actor, tool_name, incident_id, action_id,
                policy_id, policy_version, policy_source_ref, request_json,
                response_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                audit_id,
                request_id,
                trace_id,
                tenant_id,
                actor,
                tool_name,
                incident_id,
                action_id,
                policy.get("policy_id"),
                policy.get("policy_version"),
                policy.get("source_ref"),
                _canonical(request),
                _canonical(response),
                created_at,
            ),
        )
        return audit_id

    def set_device_state(self, device_id: str, **changes: Any) -> None:
        allowed = {
            "health_state",
            "door_state",
            "power_state",
            "compressor_state",
            "ambient_temp_c",
        }
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"Unsupported device fields: {sorted(invalid)}")
        if not changes:
            return
        changes["updated_at"] = self.now()
        assignments = ", ".join(f"{key} = ?" for key in changes)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE devices SET {assignments} WHERE device_id = ?",
                [*changes.values(), device_id],
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown device {device_id}")

    def append_device_reading(
        self,
        *,
        device_id: str,
        observed_at: str,
        temp_c: float,
        quality: str = "good",
        source: str = "scenario",
    ) -> str:
        with self.transaction() as conn:
            reading_id = self.next_id(conn, "reading")
            conn.execute(
                """INSERT INTO device_readings(
                    reading_id, device_id, observed_at, temp_c, quality, source
                ) VALUES(?, ?, ?, ?, ?, ?)""",
                (reading_id, device_id, observed_at, temp_c, quality, source),
            )
        return reading_id

    def set_batch_safety(self, batch_id: str, *, safe_for_sale: bool) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE inventory_batches
                   SET safe_for_sale = ?, updated_at = ? WHERE batch_id = ?""",
                (int(safe_for_sale), self.now(), batch_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown batch {batch_id}")

    def set_workorder_status(
        self,
        workorder_id: str,
        *,
        status: WorkOrderStatus,
        completion_evidence: dict[str, Any] | None = None,
    ) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE workorders SET status = ?, completion_evidence_json = ?,
                   updated_at = ? WHERE workorder_id = ?""",
                (
                    status.value,
                    _canonical(completion_evidence) if completion_evidence is not None else None,
                    self.now(),
                    workorder_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown workorder {workorder_id}")

    def expire_approvals(self) -> int:
        now = self.now()
        with self.transaction() as conn:
            expiring = conn.execute(
                "SELECT approval_id FROM approvals WHERE status = ? AND deadline <= ?",
                (ApprovalStatus.PENDING.value, now),
            ).fetchall()
            approval_ids = []
            for row in expiring:
                cursor = conn.execute(
                    """UPDATE approvals SET status = ?, decided_at = ?, decided_by = ?,
                       decision_reason = ? WHERE approval_id = ? AND status = ?
                       AND deadline <= ?""",
                    (
                        ApprovalStatus.TIMEOUT.value,
                        now,
                        "ScenarioEngine",
                        "virtual deadline reached",
                        row["approval_id"],
                        ApprovalStatus.PENDING.value,
                        now,
                    ),
                )
                if cursor.rowcount == 1:
                    approval_ids.append(row["approval_id"])
            if approval_ids:
                placeholders = ",".join("?" for _ in approval_ids)
                conn.execute(
                    f"""UPDATE actions SET status = 'timeout', updated_at = ?
                        WHERE approval_id IN ({placeholders})""",
                    [now, *approval_ids],
                )
            return len(approval_ids)

    def inject_tool_failure(
        self,
        *,
        tool_name: str,
        remaining_calls: int,
        error_code: str,
        message: str,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO tool_failures(
                    tool_name, remaining_calls, error_code, message
                ) VALUES(?, ?, ?, ?)
                ON CONFLICT(tool_name) DO UPDATE SET
                    remaining_calls = excluded.remaining_calls,
                    error_code = excluded.error_code,
                    message = excluded.message""",
                (tool_name, remaining_calls, error_code, message),
            )

    def consume_tool_failure(self, tool_name: str) -> dict[str, str] | None:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM tool_failures WHERE tool_name = ?",
                (tool_name,),
            ).fetchone()
            if row is None or row["remaining_calls"] <= 0:
                return None
            cursor = conn.execute(
                """UPDATE tool_failures SET remaining_calls = remaining_calls - 1
                   WHERE tool_name = ? AND remaining_calls > 0""",
                (tool_name,),
            )
            if cursor.rowcount != 1:
                return None
            return {"code": row["error_code"], "message": row["message"]}

    def _filtered_rows(
        self,
        table: str,
        order_by: str,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        allowed = {
            "approvals": {"approval_id", "action_id", "incident_id"},
            "workorders": {"workorder_id", "action_id", "incident_id"},
            "verifications": {"incident_id", "subject"},
            "actions": {"incident_id", "action_id"},
            "manual_evidence": {"incident_id"},
            "audit_log": {"incident_id"},
        }
        if table not in allowed or set(filters) - allowed[table]:
            raise ValueError("Unsafe table or filter")
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in filters.items():
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self.connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM {table}{where} ORDER BY {order_by}",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _decode_json_columns(row: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        for key, value in list(decoded.items()):
            if key.endswith("_json"):
                decoded[key.removesuffix("_json")] = SQLiteStateStore._decode_json_value(value)
                del decoded[key]
        return decoded

    @staticmethod
    def _decode_json_value(value: Any) -> Any:
        if value is None or isinstance(value, (dict, list, int, float, bool)):
            return value
        return json.loads(value)


# Backward-compatible constructor used by the deterministic local demo.
StateStore = SQLiteStateStore
