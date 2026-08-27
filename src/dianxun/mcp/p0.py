"""The 12 stateful P0 MCP functions.

Every write is permission checked, policy evaluated, idempotent and audited in
the same SQLite transaction as its business-state mutation.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import sys
import uuid
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from ..domain.enums import ApprovalStatus, BatchDisposition, WorkOrderStatus
from ..domain.models import Evidence
from ..domain.policy import PolicyDecision, PolicyEngine
from ..state import StateStore
from .envelope import ToolEnvelope

_ROOT = Path(__file__).resolve().parents[3]
_SHARE = Path(sys.prefix) / "share" / "dianxun"


def _resource(repo_path: Path, installed_path: Path) -> Path:
    return repo_path if repo_path.exists() else installed_path


DEFAULT_DB_PATH = Path.cwd() / "demo" / "state" / "runtime.db"
DEFAULT_SEED_PATH = _resource(
    _ROOT / "demo" / "state" / "seed.json",
    _SHARE / "demo" / "state" / "seed.json",
)
DEFAULT_POLICY_PATH = _resource(
    _ROOT / "config" / "policies" / "coldchain-demo.v1.json",
    _SHARE / "config" / "policies" / "coldchain-demo.v1.json",
)
DEFAULT_SCENARIO_DIR = _resource(
    _ROOT / "demo" / "state" / "scenarios",
    _SHARE / "demo" / "state" / "scenarios",
)
DEFAULT_SCENARIO_PATH = DEFAULT_SCENARIO_DIR / "coldchain-compressor-failure.json"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_finite_nonnegative_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


class ScopeViolation(PermissionError):
    """Raised when an action targets state outside its incident boundary."""


class MCPService:
    """Stateful implementation used directly and through JSON-RPC."""

    def __init__(
        self,
        store: StateStore,
        policy: PolicyEngine,
        *,
        auto_initialize_seed: str | Path | None = None,
    ) -> None:
        self.store = store
        self.policy = policy
        self.store.create_schema()
        if self.store.get_meta("virtual_time") is None:
            if auto_initialize_seed is None:
                raise RuntimeError("State store is not initialized")
            self.store.initialize_from_file(auto_initialize_seed)

    # ----- five queries -------------------------------------------------

    def query_device_context(
        self,
        *,
        device_id: str | None = None,
        store_id: str | None = None,
        incident_id: str | None = None,
        facets: list[str] | None = None,
        window_minutes: int = 180,
        request_id: str | None = None,
        actor: str = "Sentry",
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        failure = self._failure("query_device_context", rid)
        if failure:
            return failure
        selected = set(facets or ["temperature", "health", "door", "power", "maintenance"])
        devices = self.store.list_devices(device_id=device_id, store_id=store_id)
        if not devices:
            return self._error(rid, "NOT_FOUND", "No matching device")
        collected_at = self.store.now()
        since = (
            self._parse_time(collected_at) - timedelta(minutes=max(1, window_minutes))
        ).isoformat(timespec="seconds")
        output: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        for device in devices:
            item: dict[str, Any] = {
                "device_id": device["device_id"],
                "store_id": device["store_id"],
            }
            if "health" in selected:
                item["health"] = {
                    "state": device["health_state"],
                    "compressor_state": device["compressor_state"],
                    "model": device["model"],
                }
            if "door" in selected:
                item["door"] = {"state": device["door_state"]}
            if "power" in selected:
                item["power"] = {"state": device["power_state"]}
            if "maintenance" in selected:
                item["maintenance"] = {"summary": "No open history in seed"}
            series: list[dict[str, Any]] = []
            if "temperature" in selected:
                series = self.store.list_device_readings(device_id=device["device_id"], since=since)
                item["temperature_series"] = series
                item["ambient_temp_c"] = device["ambient_temp_c"]
            observed_at = series[-1]["observed_at"] if series else device["updated_at"]
            ev = Evidence.create(
                evidence_type="device_context",
                source="state_store.devices",
                observed_at=observed_at,
                collected_at=collected_at,
                payload=item,
                quality="good" if series or "temperature" not in selected else "partial",
                freshness=self._freshness(observed_at, collected_at),
                request_id=rid,
                incident_id=incident_id,
            )
            evidence.append(self._evidence_dict(ev))
            output.append(item)
        return self._ok(rid, {"devices": output, "evidence": evidence})

    def query_inventory_batches(
        self,
        *,
        device_id: str | None = None,
        store_id: str | None = None,
        batch_ids: list[str] | None = None,
        incident_id: str | None = None,
        request_id: str | None = None,
        actor: str = "Diagnoser",
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        failure = self._failure("query_inventory_batches", rid)
        if failure:
            return failure
        batches = self.store.list_batches(
            device_id=device_id,
            store_id=store_id,
            batch_ids=batch_ids,
        )
        collected_at = self.store.now()
        ev = Evidence.create(
            evidence_type="inventory_batches",
            source="state_store.inventory_batches",
            observed_at=max((row["updated_at"] for row in batches), default=collected_at),
            collected_at=collected_at,
            payload={"batches": batches},
            quality="good",
            freshness="current",
            request_id=rid,
            incident_id=incident_id,
        )
        return self._ok(rid, {"batches": batches, "evidence": [self._evidence_dict(ev)]})

    def query_sales_holds(
        self,
        *,
        incident_id: str | None = None,
        batch_ids: list[str] | None = None,
        status: str | None = None,
        request_id: str | None = None,
        actor: str = "Auditor",
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        failure = self._failure("query_sales_holds", rid)
        if failure:
            return failure
        holds = self.store.list_sales_holds(
            incident_id=incident_id,
            batch_ids=batch_ids,
            status=status,
        )
        return self._query_rows(rid, "sales_holds", holds, incident_id=incident_id)

    def query_workorder(
        self,
        *,
        workorder_id: str | None = None,
        action_id: str | None = None,
        incident_id: str | None = None,
        request_id: str | None = None,
        actor: str = "Auditor",
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        failure = self._failure("query_workorder", rid)
        if failure:
            return failure
        rows = self.store.list_workorders(
            workorder_id=workorder_id,
            action_id=action_id,
            incident_id=incident_id,
        )
        return self._query_rows(rid, "workorders", rows, incident_id=incident_id)

    def query_approval(
        self,
        *,
        approval_id: str | None = None,
        action_id: str | None = None,
        incident_id: str | None = None,
        request_id: str | None = None,
        actor: str = "Auditor",
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        failure = self._failure("query_approval", rid)
        if failure:
            return failure
        rows = self.store.list_approvals(
            approval_id=approval_id,
            action_id=action_id,
            incident_id=incident_id,
        )
        return self._query_rows(rid, "approvals", rows, incident_id=incident_id)

    # ----- seven actions ------------------------------------------------

    def apply_sales_hold(
        self,
        *,
        incident_id: str,
        action_id: str,
        store_id: str,
        batch_ids: list[str],
        reason: str,
        idempotency_key: str,
        actor: str = "Executor",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        if not batch_ids:
            return self._error(rid, "INVALID_ARGUMENT", "batch_ids must not be empty")
        decision = self.policy.evaluate(actor=actor, action_type="apply_sales_hold")
        request = {
            "incident_id": incident_id,
            "action_id": action_id,
            "store_id": store_id,
            "batch_ids": batch_ids,
            "reason": reason,
        }

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            self._require_incident_scope(
                conn,
                incident_id=incident_id,
                store_id=store_id,
                batch_ids=batch_ids,
            )
            self._ensure_new_action(conn, incident_id=incident_id, action_id=action_id)
            if len(batch_ids) != len(set(batch_ids)):
                raise ValueError("batch_ids must not contain duplicates")
            placeholders = ",".join("?" for _ in batch_ids)
            existing = conn.execute(
                f"""SELECT batch_id FROM sales_holds
                    WHERE incident_id = ? AND status = 'active'
                    AND batch_id IN ({placeholders})""",
                [incident_id, *batch_ids],
            ).fetchall()
            if existing:
                raise ValueError(
                    "One or more batches already have an active hold for this incident"
                )
            holds = []
            for batch_id in batch_ids:
                hold_id = self.store.next_id(conn, "hold")
                conn.execute(
                    """INSERT INTO sales_holds(
                        hold_id, incident_id, action_id, store_id, batch_id, sku_id,
                        status, reason, applied_at
                    ) SELECT ?, ?, ?, ?, ?, sku_id, 'active', ?, ?
                      FROM inventory_batches WHERE batch_id = ?""",
                    (
                        hold_id,
                        incident_id,
                        action_id,
                        store_id,
                        batch_id,
                        reason,
                        now,
                        batch_id,
                    ),
                )
                conn.execute(
                    """UPDATE inventory_batches SET disposition = ?, safe_for_sale = 0,
                       updated_at = ? WHERE batch_id = ?""",
                    (BatchDisposition.QUARANTINED.value, now, batch_id),
                )
                holds.append({"hold_id": hold_id, "batch_id": batch_id, "status": "active"})
            self._upsert_action(
                conn,
                action_id=action_id,
                incident_id=incident_id,
                action_type="apply_sales_hold",
                tool_name="apply_sales_hold",
                status="completed",
                request=request,
                response={"holds": holds},
                now=now,
            )
            return {"holds": holds}

        return self._mutate(
            tool_name="apply_sales_hold",
            rid=rid,
            actor=actor,
            incident_id=incident_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
            decision=decision,
            request=request,
            mutation=mutate,
        )

    def release_sales_hold(
        self,
        *,
        incident_id: str,
        action_id: str,
        hold_ids: list[str],
        approval_id: str,
        verification_id: str,
        idempotency_key: str,
        actor: str = "Executor",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        decision = self.policy.evaluate(actor=actor, action_type="release_sales_hold")
        request = {
            "incident_id": incident_id,
            "action_id": action_id,
            "hold_ids": hold_ids,
            "approval_id": approval_id,
            "verification_id": verification_id,
        }

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            self._require_incident_scope(conn, incident_id=incident_id)
            self._require_approval(
                conn,
                approval_id=approval_id,
                incident_id=incident_id,
                action_id=action_id,
                action_type="release_sales_hold",
            )
            verification = conn.execute(
                """SELECT * FROM verifications WHERE verification_id = ?
                   AND incident_id = ? AND subject = 'release_guard'
                   AND result = 'passed' AND verifier = 'Auditor'""",
                (verification_id, incident_id),
            ).fetchone()
            if verification is None:
                raise PermissionError("A passed Auditor release_guard verification is required")
            if not hold_ids:
                raise ValueError("hold_ids must not be empty")
            if len(hold_ids) != len(set(hold_ids)):
                raise ValueError("hold_ids must not contain duplicates")
            placeholders = ",".join("?" for _ in hold_ids)
            rows = conn.execute(
                f"""SELECT h.hold_id, h.status, h.batch_id, h.applied_at,
                           b.updated_at AS batch_updated_at
                    FROM sales_holds AS h
                    JOIN inventory_batches AS b ON b.batch_id = h.batch_id
                    WHERE h.hold_id IN ({placeholders}) AND h.incident_id = ?""",
                [*hold_ids, incident_id],
            ).fetchall()
            if len(rows) != len(set(hold_ids)):
                raise ValueError("One or more holds do not belong to the incident")
            if any(row["status"] != "active" for row in rows):
                raise ValueError("Only active holds may be released")
            verified_at = self._parse_time(verification["verified_at"])
            if any(
                verified_at < self._parse_time(row["applied_at"])
                or verified_at < self._parse_time(row["batch_updated_at"])
                for row in rows
            ):
                raise PermissionError("The Auditor release_guard verification is stale")
            evidence_ids = json.loads(verification["evidence_ids_json"])
            observed = json.loads(verification["observed_json"])
            verified_hold_states = observed.get("released_batch_holds", {})
            if not evidence_ids or not isinstance(verified_hold_states, dict):
                raise PermissionError("The Auditor release_guard lacks fresh evidence")
            if any(verified_hold_states.get(row["batch_id"]) != "active" for row in rows):
                raise PermissionError("The Auditor release_guard does not cover the target holds")
            conn.execute(
                f"""UPDATE sales_holds SET status = 'released', released_at = ?,
                    approval_id = ?, verification_id = ?
                    WHERE hold_id IN ({placeholders}) AND incident_id = ?""",
                [now, approval_id, verification_id, *hold_ids, incident_id],
            )
            data = {"hold_ids": hold_ids, "status": "released"}
            self._upsert_action(
                conn,
                action_id=action_id,
                incident_id=incident_id,
                action_type="release_sales_hold",
                tool_name="release_sales_hold",
                status="completed",
                request=request,
                response=data,
                now=now,
                approval_id=approval_id,
            )
            return data

        return self._mutate(
            tool_name="release_sales_hold",
            rid=rid,
            actor=actor,
            incident_id=incident_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
            decision=decision,
            request=request,
            mutation=mutate,
        )

    def apply_batch_disposition(
        self,
        *,
        incident_id: str,
        action_id: str,
        batch_ids: list[str],
        disposition: str,
        idempotency_key: str,
        approval_id: str | None = None,
        actor: str = "Executor",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        try:
            target = BatchDisposition(disposition)
        except ValueError:
            return self._error(rid, "INVALID_ARGUMENT", f"Unsupported disposition {disposition}")
        if target is BatchDisposition.UNKNOWN:
            return self._error(rid, "INVALID_ARGUMENT", "Cannot apply unknown disposition")
        decision = self.policy.evaluate(
            actor=actor,
            action_type="apply_batch_disposition",
            disposition=target.value,
        )
        request = {
            "incident_id": incident_id,
            "action_id": action_id,
            "batch_ids": batch_ids,
            "disposition": target.value,
            "approval_id": approval_id,
        }

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            self._require_incident_scope(
                conn,
                incident_id=incident_id,
                batch_ids=batch_ids,
            )
            if decision.approval_required:
                self._require_approval(
                    conn,
                    approval_id=approval_id,
                    incident_id=incident_id,
                    action_id=action_id,
                    action_type="apply_batch_disposition",
                    disposition=target.value,
                )
            else:
                self._ensure_new_action(conn, incident_id=incident_id, action_id=action_id)
            if not batch_ids:
                raise ValueError("batch_ids must not be empty")
            if len(batch_ids) != len(set(batch_ids)):
                raise ValueError("batch_ids must not contain duplicates")
            placeholders = ",".join("?" for _ in batch_ids)
            found = conn.execute(
                f"SELECT batch_id FROM inventory_batches WHERE batch_id IN ({placeholders})",
                batch_ids,
            ).fetchall()
            if len(found) != len(set(batch_ids)):
                raise ValueError("One or more batches do not exist")
            safe = int(target is BatchDisposition.RELEASED)
            conn.execute(
                f"""UPDATE inventory_batches SET disposition = ?, safe_for_sale = ?,
                    updated_at = ? WHERE batch_id IN ({placeholders})""",
                [target.value, safe, now, *batch_ids],
            )
            data = {
                "batch_ids": batch_ids,
                "disposition": target.value,
                "safe_for_sale": bool(safe),
            }
            self._upsert_action(
                conn,
                action_id=action_id,
                incident_id=incident_id,
                action_type=f"apply_batch_disposition:{target.value}",
                tool_name="apply_batch_disposition",
                status="completed",
                request=request,
                response=data,
                now=now,
                approval_id=approval_id,
            )
            return data

        return self._mutate(
            tool_name="apply_batch_disposition",
            rid=rid,
            actor=actor,
            incident_id=incident_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
            decision=decision,
            request=request,
            mutation=mutate,
        )

    def create_workorder(
        self,
        *,
        incident_id: str,
        action_id: str,
        store_id: str,
        device_id: str,
        fault: str,
        budget: float,
        idempotency_key: str,
        approval_id: str | None = None,
        assignee: str = "vendor-a",
        actor: str = "Executor",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        if not _is_finite_nonnegative_number(budget):
            return self._error(
                rid, "INVALID_ARGUMENT", "budget must be a finite non-negative number"
            )
        budget = float(budget)
        decision = self.policy.evaluate(actor=actor, action_type="create_workorder", amount=budget)
        request = {
            "incident_id": incident_id,
            "action_id": action_id,
            "store_id": store_id,
            "device_id": device_id,
            "fault": fault,
            "budget": budget,
            "approval_id": approval_id,
            "assignee": assignee,
        }

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            self._require_incident_scope(
                conn,
                incident_id=incident_id,
                store_id=store_id,
                device_id=device_id,
            )
            if decision.approval_required:
                self._require_approval(
                    conn,
                    approval_id=approval_id,
                    incident_id=incident_id,
                    action_id=action_id,
                    action_type="create_workorder",
                    amount=budget,
                )
            else:
                self._ensure_new_action(conn, incident_id=incident_id, action_id=action_id)
            device = conn.execute(
                "SELECT device_id FROM devices WHERE device_id = ? AND store_id = ?",
                (device_id, store_id),
            ).fetchone()
            if device is None:
                raise ValueError("Device does not belong to the store")
            workorder_id = self.store.next_id(conn, "wo")
            status = WorkOrderStatus.ASSIGNED.value if assignee else WorkOrderStatus.CREATED.value
            conn.execute(
                """INSERT INTO workorders(
                    workorder_id, incident_id, action_id, store_id, device_id, fault,
                    budget, status, assignee, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workorder_id,
                    incident_id,
                    action_id,
                    store_id,
                    device_id,
                    fault,
                    budget,
                    status,
                    assignee,
                    now,
                    now,
                ),
            )
            data = {"workorder_id": workorder_id, "status": status}
            self._upsert_action(
                conn,
                action_id=action_id,
                incident_id=incident_id,
                action_type="create_workorder",
                tool_name="create_workorder",
                status="completed",
                request=request,
                response=data,
                now=now,
                approval_id=approval_id,
            )
            return data

        return self._mutate(
            tool_name="create_workorder",
            rid=rid,
            actor=actor,
            incident_id=incident_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
            decision=decision,
            request=request,
            mutation=mutate,
        )

    def create_approval(
        self,
        *,
        incident_id: str,
        action_id: str,
        subject: str,
        requested_action_type: str,
        idempotency_key: str,
        timeout_minutes: int = 30,
        amount: float | None = None,
        disposition: str | None = None,
        actor: str = "Executor",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        if amount is not None:
            if not _is_finite_nonnegative_number(amount):
                return self._error(
                    rid,
                    "INVALID_ARGUMENT",
                    "amount must be a finite non-negative number",
                )
            amount = float(amount)
        if (
            isinstance(timeout_minutes, bool)
            or not isinstance(timeout_minutes, int)
            or timeout_minutes <= 0
        ):
            return self._error(
                rid,
                "INVALID_ARGUMENT",
                "timeout_minutes must be a positive integer",
            )
        decision = self.policy.evaluate(
            actor=actor,
            action_type=requested_action_type,
            amount=amount,
            disposition=disposition,
        )
        request = {
            "incident_id": incident_id,
            "action_id": action_id,
            "subject": subject,
            "requested_action_type": requested_action_type,
            "timeout_minutes": timeout_minutes,
            "amount": amount,
            "disposition": disposition,
        }

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            self._require_incident_scope(conn, incident_id=incident_id)
            self._ensure_new_action(conn, incident_id=incident_id, action_id=action_id)
            approval_id = self.store.next_id(conn, "approval")
            deadline = (self._parse_time(now) + timedelta(minutes=timeout_minutes)).isoformat(
                timespec="seconds"
            )
            approvers = list(decision.approvers) or ["store_manager"]
            conn.execute(
                """INSERT INTO approvals(
                    approval_id, incident_id, action_id, subject, status,
                    approvers_json, deadline, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval_id,
                    incident_id,
                    action_id,
                    subject,
                    ApprovalStatus.PENDING.value,
                    _canonical(approvers),
                    deadline,
                    now,
                ),
            )
            data = {
                "approval_id": approval_id,
                "action_id": action_id,
                "status": ApprovalStatus.PENDING.value,
                "deadline": deadline,
                "approvers": approvers,
            }
            self._upsert_action(
                conn,
                action_id=action_id,
                incident_id=incident_id,
                action_type=requested_action_type,
                tool_name="create_approval",
                status="pending",
                request=request,
                response=data,
                now=now,
                approval_id=approval_id,
            )
            return data

        return self._mutate(
            tool_name="create_approval",
            rid=rid,
            actor=actor,
            incident_id=incident_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
            decision=decision,
            request=request,
            mutation=mutate,
            allow_when_approval_required=True,
        )

    def decide_approval(
        self,
        *,
        approval_id: str,
        decision: str,
        reason: str,
        idempotency_key: str,
        actor: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        if actor not in {"Human", "ScenarioEngine"}:
            return self._error(rid, "FORBIDDEN", "Only Human or ScenarioEngine may decide approval")
        try:
            target = ApprovalStatus(decision)
        except ValueError:
            return self._error(rid, "INVALID_ARGUMENT", f"Unsupported decision {decision}")
        if target is ApprovalStatus.PENDING:
            return self._error(rid, "INVALID_ARGUMENT", "Decision cannot be pending")
        self.store.expire_approvals()
        rows = self.store.list_approvals(approval_id=approval_id)
        if not rows:
            return self._error(rid, "NOT_FOUND", f"Unknown approval {approval_id}")
        approval = rows[0]
        request = {"approval_id": approval_id, "decision": target.value, "reason": reason}

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            row = conn.execute(
                "SELECT status, action_id FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown approval {approval_id}")
            if row["status"] != ApprovalStatus.PENDING.value:
                raise ValueError(f"Approval is already {row['status']}")
            conn.execute(
                """UPDATE approvals SET status = ?, decided_at = ?, decided_by = ?,
                   decision_reason = ? WHERE approval_id = ?""",
                (target.value, now, actor, reason, approval_id),
            )
            action_status = {
                ApprovalStatus.APPROVED: "approved",
                ApprovalStatus.REJECTED: "rejected",
                ApprovalStatus.TIMEOUT: "timeout",
            }[target]
            conn.execute(
                "UPDATE actions SET status = ?, updated_at = ? WHERE action_id = ?",
                (action_status, now, row["action_id"]),
            )
            return {"approval_id": approval_id, "status": target.value, "decided_by": actor}

        synthetic_policy = PolicyDecision(
            allowed=True,
            risk_level="L2",
            approval_required=False,
            approvers=(),
            policy_id=self.policy.policy["policy_id"],
            policy_version=self.policy.policy["policy_version"],
            effective_at=self.policy.policy["effective_at"],
            source_ref=self.policy.policy["source_ref"],
            reason="Human decision boundary",
        )
        return self._mutate(
            tool_name="decide_approval",
            rid=rid,
            actor=actor,
            incident_id=approval["incident_id"],
            action_id=approval["action_id"],
            idempotency_key=idempotency_key,
            decision=synthetic_policy,
            request=request,
            mutation=mutate,
        )

    def record_manual_evidence(
        self,
        *,
        incident_id: str,
        evidence_type: str,
        observed_at: str,
        note: str,
        metadata: dict[str, Any],
        idempotency_key: str,
        actor: str,
        action_id: str | None = None,
        uri: str | None = None,
        sha256: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rid = request_id or self._request_id()
        if actor not in {"Human", "ScenarioEngine"}:
            return self._error(rid, "FORBIDDEN", "Only Human or ScenarioEngine may record evidence")
        if not isinstance(observed_at, str):
            return self._error(rid, "INVALID_ARGUMENT", "observed_at must be an ISO-8601 timestamp")
        try:
            self._parse_time(observed_at)
        except ValueError:
            return self._error(rid, "INVALID_ARGUMENT", "observed_at must be an ISO-8601 timestamp")
        if sha256 is not None:
            try:
                if not isinstance(sha256, str) or len(sha256) != 64:
                    raise ValueError
                bytes.fromhex(sha256)
            except ValueError:
                return self._error(rid, "INVALID_ARGUMENT", "sha256 must contain 64 hex characters")
        digest = (
            sha256
            or hashlib.sha256(
                _canonical({"note": note, "metadata": metadata, "uri": uri}).encode("utf-8")
            ).hexdigest()
        )
        request = {
            "incident_id": incident_id,
            "action_id": action_id,
            "evidence_type": evidence_type,
            "observed_at": observed_at,
            "note": note,
            "metadata": metadata,
            "uri": uri,
            "sha256": digest,
        }

        def mutate(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
            self._require_incident_scope(conn, incident_id=incident_id)
            if action_id is not None:
                self._require_action_reference(
                    conn,
                    incident_id=incident_id,
                    action_id=action_id,
                )
            evidence_id = self.store.next_id(conn, "manual_ev")
            conn.execute(
                """INSERT INTO manual_evidence(
                    evidence_id, incident_id, action_id, actor, evidence_type,
                    observed_at, uri, note, sha256, metadata_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    evidence_id,
                    incident_id,
                    action_id,
                    actor,
                    evidence_type,
                    observed_at,
                    uri,
                    note,
                    digest,
                    _canonical(metadata),
                    now,
                ),
            )
            return {"evidence_id": evidence_id, "sha256": digest, "uri": uri}

        synthetic_policy = PolicyDecision(
            allowed=True,
            risk_level="L1",
            approval_required=False,
            approvers=(),
            policy_id=self.policy.policy["policy_id"],
            policy_version=self.policy.policy["policy_version"],
            effective_at=self.policy.policy["effective_at"],
            source_ref=self.policy.policy["source_ref"],
            reason="Human evidence boundary",
        )
        return self._mutate(
            tool_name="record_manual_evidence",
            rid=rid,
            actor=actor,
            incident_id=incident_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
            decision=synthetic_policy,
            request=request,
            mutation=mutate,
        )

    # ----- internals ----------------------------------------------------

    def _mutate(
        self,
        *,
        tool_name: str,
        rid: str,
        actor: str,
        incident_id: str | None,
        action_id: str | None,
        idempotency_key: str,
        decision: PolicyDecision,
        request: dict[str, Any],
        mutation: Callable[[sqlite3.Connection, str], dict[str, Any]],
        allow_when_approval_required: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            return self._error(rid, "INVALID_ARGUMENT", "idempotency_key is required")
        failure = self._failure(tool_name, rid)
        if failure:
            return failure
        if not decision.allowed:
            return self._audit_denial(
                rid=rid,
                actor=actor,
                tool_name=tool_name,
                incident_id=incident_id,
                action_id=action_id,
                decision=decision,
                request=request,
                code="FORBIDDEN",
                message=decision.reason,
            )
        if decision.approval_required and not allow_when_approval_required:
            supplied = request.get("approval_id")
            if not supplied:
                return self._audit_denial(
                    rid=rid,
                    actor=actor,
                    tool_name=tool_name,
                    incident_id=incident_id,
                    action_id=action_id,
                    decision=decision,
                    request=request,
                    code="APPROVAL_REQUIRED",
                    message="Approved approval_id is required by policy",
                )
        try:
            with self.store.transaction() as conn:
                previous = self.store.idempotent_result(
                    conn,
                    idempotency_key=idempotency_key,
                )
                if previous:
                    same_request = previous["request"] is not None and _canonical(
                        previous["request"]
                    ) == _canonical(request)
                    if (
                        previous["tool_name"] != tool_name
                        or previous["actor"] != actor
                        or not same_request
                    ):
                        error = {
                            "code": "IDEMPOTENCY_CONFLICT",
                            "message": (
                                "idempotency_key was already used with a different "
                                "tool, actor, or request"
                            ),
                        }
                        audit_id = self.store.record_audit(
                            conn,
                            request_id=rid,
                            actor=actor,
                            tool_name=tool_name,
                            incident_id=incident_id,
                            action_id=action_id,
                            policy=decision.to_dict(),
                            request=request,
                            response={"error": error},
                            created_at=self.store.now(),
                        )
                        return self._error(
                            rid,
                            error["code"],
                            error["message"],
                            audit_ref=audit_id,
                        )
                    data = {**previous["data"], "idempotent_replay": True}
                    return self._ok(rid, data, audit_ref=previous["audit_id"])
                now = self.store.now()
                data = mutation(conn, now)
                policy_data = decision.to_dict()
                audit_id = self.store.record_audit(
                    conn,
                    request_id=rid,
                    actor=actor,
                    tool_name=tool_name,
                    incident_id=incident_id,
                    action_id=action_id,
                    policy=policy_data,
                    request=request,
                    response=data,
                    created_at=now,
                )
                self.store.save_idempotent_result(
                    conn,
                    tool_name=tool_name,
                    idempotency_key=idempotency_key,
                    data=data,
                    audit_id=audit_id,
                    created_at=now,
                )
            return self._ok(rid, data, audit_ref=audit_id)
        except ScopeViolation as exc:
            return self._error(rid, "FORBIDDEN", str(exc))
        except PermissionError as exc:
            return self._error(rid, "APPROVAL_INVALID", str(exc))
        except (KeyError, ValueError, sqlite3.IntegrityError) as exc:
            return self._error(rid, "INVALID_STATE", str(exc))

    def _audit_denial(
        self,
        *,
        rid: str,
        actor: str,
        tool_name: str,
        incident_id: str | None,
        action_id: str | None,
        decision: PolicyDecision,
        request: dict[str, Any],
        code: str,
        message: str,
    ) -> dict[str, Any]:
        error = {"code": code, "message": message}
        with self.store.transaction() as conn:
            audit_id = self.store.record_audit(
                conn,
                request_id=rid,
                actor=actor,
                tool_name=tool_name,
                incident_id=incident_id,
                action_id=action_id,
                policy=decision.to_dict(),
                request=request,
                response={"error": error},
                created_at=self.store.now(),
            )
        return self._error(rid, code, message, audit_ref=audit_id)

    @staticmethod
    def _require_approval(
        conn: sqlite3.Connection,
        *,
        approval_id: str | None,
        incident_id: str,
        action_id: str,
        action_type: str,
        amount: float | None = None,
        disposition: str | None = None,
    ) -> None:
        if not approval_id:
            raise PermissionError("approval_id is required")
        row = conn.execute(
            """SELECT a.incident_id, a.action_id, a.status,
                      x.action_type, x.tool_name, x.request_json
               FROM approvals AS a
               JOIN actions AS x ON x.action_id = a.action_id
               WHERE a.approval_id = ?""",
            (approval_id,),
        ).fetchone()
        if row is None:
            raise PermissionError(f"Unknown approval {approval_id}")
        if row["incident_id"] != incident_id:
            raise PermissionError("Approval does not belong to this incident")
        if row["action_id"] != action_id:
            raise PermissionError("Approval does not belong to this action")
        if row["status"] != ApprovalStatus.APPROVED.value:
            raise PermissionError(f"Approval status is {row['status']}, not approved")
        if row["tool_name"] != "create_approval":
            raise PermissionError("Approval has already been consumed by this action")
        approved_request = json.loads(row["request_json"])
        if (
            row["action_type"] != action_type
            or approved_request.get("requested_action_type") != action_type
        ):
            raise PermissionError("Approval is for a different action type")
        if amount is not None:
            approved_amount = approved_request.get("amount")
            if approved_amount is None or float(approved_amount) != float(amount):
                raise PermissionError("Approval amount does not match the requested action")
        if disposition is not None and approved_request.get("disposition") != disposition:
            raise PermissionError("Approval disposition does not match the requested action")

    @staticmethod
    def _require_incident_scope(
        conn: sqlite3.Connection,
        *,
        incident_id: str,
        store_id: str | None = None,
        batch_ids: list[str] | None = None,
        device_id: str | None = None,
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT store_id, case_json FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown incident {incident_id}")
        case = json.loads(row["case_json"])
        incident_store = str(row["store_id"])
        if store_id is not None and store_id != incident_store:
            raise ScopeViolation("Requested store does not belong to the incident")

        if batch_ids:
            affected = set(case.get("affected_batches", []))
            if not set(batch_ids) <= affected:
                raise ScopeViolation("One or more batches are outside the incident scope")
            placeholders = ",".join("?" for _ in batch_ids)
            rows = conn.execute(
                f"""SELECT batch_id, store_id FROM inventory_batches
                    WHERE batch_id IN ({placeholders})""",
                batch_ids,
            ).fetchall()
            if len(rows) != len(set(batch_ids)):
                raise ValueError("One or more batches do not exist")
            if any(item["store_id"] != incident_store for item in rows):
                raise ScopeViolation("One or more batches belong to another store")

        if device_id is not None:
            if device_id not in set(case.get("affected_assets", [])):
                raise ScopeViolation("Requested device is outside the incident scope")
            device = conn.execute(
                "SELECT store_id FROM devices WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if device is None:
                raise ValueError(f"Unknown device {device_id}")
            if device["store_id"] != incident_store:
                raise ScopeViolation("Requested device belongs to another store")
        return case

    @staticmethod
    def _ensure_new_action(
        conn: sqlite3.Connection,
        *,
        incident_id: str,
        action_id: str,
    ) -> None:
        row = conn.execute(
            "SELECT incident_id, tool_name FROM actions WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            return
        if row["incident_id"] != incident_id:
            raise ScopeViolation("action_id is already owned by another incident")
        raise ValueError(f"Action {action_id} is already claimed by {row['tool_name']}")

    @staticmethod
    def _require_action_reference(
        conn: sqlite3.Connection,
        *,
        incident_id: str,
        action_id: str,
    ) -> None:
        row = conn.execute(
            "SELECT incident_id FROM actions WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown action {action_id}")
        if row["incident_id"] != incident_id:
            raise ScopeViolation("Referenced action belongs to another incident")

    @staticmethod
    def _upsert_action(
        conn: sqlite3.Connection,
        *,
        action_id: str,
        incident_id: str,
        action_type: str,
        tool_name: str,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any],
        now: str,
        approval_id: str | None = None,
    ) -> None:
        existing = conn.execute(
            "SELECT incident_id, tool_name FROM actions WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        values = (
            action_type,
            tool_name,
            status,
            approval_id,
            _canonical(request),
            _canonical(response),
            now,
        )
        if existing is None:
            conn.execute(
                """INSERT INTO actions(
                    action_id, incident_id, action_type, tool_name, status,
                    approval_id, request_json, response_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action_id,
                    incident_id,
                    action_type,
                    tool_name,
                    status,
                    approval_id,
                    _canonical(request),
                    _canonical(response),
                    now,
                    now,
                ),
            )
            return
        if existing["incident_id"] != incident_id:
            raise ScopeViolation("action_id is already owned by another incident")
        if existing["tool_name"] != "create_approval":
            raise ValueError(f"Action {action_id} has already been executed")
        conn.execute(
            """UPDATE actions SET action_type = ?, tool_name = ?, status = ?,
               approval_id = COALESCE(?, approval_id), request_json = ?, response_json = ?,
               updated_at = ? WHERE action_id = ?""",
            (*values, action_id),
        )

    def _query_rows(
        self,
        rid: str,
        entity: str,
        rows: list[dict[str, Any]],
        *,
        incident_id: str | None = None,
    ) -> dict[str, Any]:
        now = self.store.now()
        ev = Evidence.create(
            evidence_type=entity,
            source=f"state_store.{entity}",
            observed_at=now,
            collected_at=now,
            payload={entity: rows},
            quality="good",
            freshness="current",
            request_id=rid,
            incident_id=incident_id,
        )
        return self._ok(rid, {entity: rows, "evidence": [self._evidence_dict(ev)]})

    def _failure(self, tool_name: str, rid: str) -> dict[str, Any] | None:
        failure = self.store.consume_tool_failure(tool_name)
        if failure is None:
            return None
        return ToolEnvelope(
            ok=False,
            data=None,
            error=failure,
            request_id=rid,
            source="dianxun-state-store",
            source_ts=self.store.now(),
            partial=True,
            audit_ref=None,
        ).to_dict()

    def _ok(
        self,
        rid: str,
        data: Any,
        *,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        return ToolEnvelope(
            ok=True,
            data=data,
            error=None,
            request_id=rid,
            source="dianxun-state-store",
            source_ts=self.store.now(),
            partial=False,
            audit_ref=audit_ref,
        ).to_dict()

    def _error(
        self,
        rid: str,
        code: str,
        message: str,
        *,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        return ToolEnvelope(
            ok=False,
            data=None,
            error={"code": code, "message": message},
            request_id=rid,
            source="dianxun-state-store",
            source_ts=self.store.now(),
            partial=False,
            audit_ref=audit_ref,
        ).to_dict()

    @staticmethod
    def _request_id() -> str:
        return f"req_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _parse_time(value: str):
        from datetime import datetime

        return datetime.fromisoformat(value)

    @classmethod
    def _freshness(cls, observed_at: str, collected_at: str) -> str:
        age = cls._parse_time(collected_at) - cls._parse_time(observed_at)
        return "fresh" if age <= timedelta(minutes=30) else "stale"

    @staticmethod
    def _evidence_dict(evidence: Evidence) -> dict[str, Any]:
        return {
            "evidence_id": evidence.evidence_id,
            "incident_id": evidence.incident_id,
            "type": evidence.type,
            "source": evidence.source,
            "observed_at": evidence.observed_at,
            "collected_at": evidence.collected_at,
            "payload": evidence.payload,
            "quality": evidence.quality,
            "freshness": evidence.freshness,
            "request_id": evidence.request_id,
            "immutable_hash": evidence.immutable_hash,
        }


_SERVICE_CACHE: tuple[Path, MCPService] | None = None


def default_service() -> MCPService:
    """Return a process-local service bound to ``DIANXUN_STATE_DB``."""
    global _SERVICE_CACHE
    db_path = Path(os.environ.get("DIANXUN_STATE_DB", str(DEFAULT_DB_PATH))).resolve()
    if _SERVICE_CACHE is None or _SERVICE_CACHE[0] != db_path:
        _SERVICE_CACHE = (
            db_path,
            MCPService(
                StateStore(db_path),
                PolicyEngine(DEFAULT_POLICY_PATH),
                auto_initialize_seed=DEFAULT_SEED_PATH,
            ),
        )
    return _SERVICE_CACHE[1]
