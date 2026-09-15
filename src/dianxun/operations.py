"""Scoped read-only incident dossiers shared by the live console and evidence capture."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from . import trace
from .domain.models import stable_hash
from .skills.registry import load_skill_registry

RELATED = {
    "actions": "action_id",
    "approvals": "approval_id",
    "workorders": "workorder_id",
    "sales_holds": "hold_id",
    "manual_evidence": "evidence_id",
    "verifications": "verification_id",
    "audit_log": "created_at, audit_id",
}


def decode(row):
    return {
        key.removesuffix("_json"): (json.loads(value) if isinstance(value, str) else value)
        if key.endswith("_json")
        else value
        for key, value in row.items()
    }


def list_incidents(store, principal, *, after="", limit=50):
    with store._reader() as conn:
        rows = conn.execute(
            """SELECT incident_id, case_json FROM incidents
               WHERE tenant_id = ? AND store_id = ? AND incident_id > ?
               ORDER BY incident_id LIMIT ?""",
            (principal.tenant_id, principal.store_id, after, limit + 1),
        ).fetchall()
    cases = [decode(dict(row))["case"] for row in rows[:limit]]
    return {
        "items": [
            {
                key: c[key]
                for key in ("incident_id", "incident_status", "phase", "work_status", "updated_at")
            }
            for c in cases
        ],
        "next_cursor": cases[-1]["incident_id"] if len(rows) > limit else None,
    }


def collect_casefile(mcp, principal, incident_id, *, limit=1000, include_trace=True):
    store = mcp.store
    case = store.get_incident(incident_id)
    if case is None or (case["tenant_id"], case["store_id"]) != (
        principal.tenant_id,
        principal.store_id,
    ):
        raise PermissionError("Incident is outside operator scope")
    records, truncated = {}, []

    def capture(name, query, params):
        with store._reader() as conn:
            rows = [
                dict(row)
                for row in conn.execute(query + " LIMIT ?", [*params, limit + 1]).fetchall()
            ]
        if len(rows) > limit:
            truncated.append(name)
        records[name] = rows[:limit]

    for table, ordering in RELATED.items():
        capture(
            table, f"SELECT * FROM {table} WHERE incident_id = ? ORDER BY {ordering}", [incident_id]
        )
    assets = case["affected_assets"]
    batches = case["affected_batches"]
    if assets:
        markers = ",".join("?" for _ in assets)
        capture(
            "devices",
            f"SELECT * FROM devices WHERE store_id = ? AND device_id IN ({markers}) "
            "ORDER BY device_id",
            [principal.store_id, *assets],
        )
        capture(
            "device_readings",
            "SELECT r.* FROM device_readings r JOIN devices d ON d.device_id = r.device_id "
            f"WHERE d.store_id = ? AND r.device_id IN ({markers}) "
            "ORDER BY r.observed_at DESC, r.reading_id",
            [principal.store_id, *assets],
        )
    else:
        records.update(devices=[], device_readings=[])
    if batches:
        markers = ",".join("?" for _ in batches)
        capture(
            "inventory_batches",
            f"SELECT * FROM inventory_batches WHERE store_id = ? AND batch_id IN ({markers}) "
            "ORDER BY batch_id",
            [principal.store_id, *batches],
        )
    else:
        records["inventory_batches"] = []
    with store._reader() as conn:
        raw = conn.execute(
            "SELECT payload_json FROM runtime_contexts "
            "WHERE tenant_id = ? AND store_id = ? AND task_id = ?",
            (principal.tenant_id, principal.store_id, incident_id),
        ).fetchone()
    context = decode(dict(raw))["payload"] if raw else None
    spans = (
        trace.read_trace(case["trace_id"], limit=limit + 1)
        if include_trace
        else {"status": "unavailable", "rows": []}
    )
    if len(spans["rows"]) > limit:
        truncated.append("trace")
    revision = os.environ.get("DIANXUN_BUILD_SHA", "")
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        revision = "unknown"
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "business_time": store.now(),
        "backend": store.backend_name,
        "build_revision": revision,
        "data_origin": "scenario" if context and context.get("source_events") else "unverified",
        "evidence_clock": "virtual_demo"
        if context
        and context.get("source_events")
        and os.environ.get("DIANXUN_SCENARIO_BRIDGE_ENABLED") == "1"
        and os.environ.get("DIANXUN_SCENARIO_VIRTUAL_CLOCK") == "1"
        else "wall_clock",
        "incident": case,
        "context": context,
        "records": records,
        "trace": {"status": spans["status"], "rows": spans["rows"][:limit]},
        "truncated": truncated,
        "current_policy": mcp.policy.policy,
        "current_policy_digest": stable_hash(mcp.policy.policy),
        "current_skill_registry": load_skill_registry(),
        "claim_boundary": "Database observations; platform references are Worker submissions. "
        "Trace has a separate capture boundary. Current policy/registry do not replace "
        "historical versions.",
    }
