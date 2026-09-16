"""Shared scope mutex and server-derived inventory checks."""

import json
from contextlib import contextmanager

from .domain.scope import build_scope_snapshot, scope_digest


def scope_device_ids(case):
    """Devices whose current facts support the complete incident scope."""
    devices = set(case.affected_assets)
    if case.scope_version and case.scope_snapshot:
        devices.update(batch["device_id"] for batch in case.scope_snapshot["batches"])
    return devices


@contextmanager
def locked_scope(store, incident_id):
    with store.transaction() as conn:
        case = store.get_incident(incident_id)
        if case and store.backend_name == "postgresql":
            from .recovery import digest

            conn.execute(
                "SELECT pg_advisory_xact_lock(?)",
                (int(digest([case["tenant_id"], case["store_id"]])[:15], 16),),
            )
        yield conn


def current_snapshot(store, case):
    ids = set(case.affected_batches)
    for device_id in case.affected_assets:
        ids.update(
            row["batch_id"]
            for row in store.list_batches(device_id=device_id, store_id=case.store_id)
            if row.get("lifecycle", "active") == "active"
        )
    batches = store.list_batches(batch_ids=sorted(ids))
    if {row["batch_id"] for row in batches} != ids:
        raise ValueError("Inventory source reconciliation is required: missing batch")
    return build_scope_snapshot(
        tenant_id=case.tenant_id,
        store_id=case.store_id,
        asset_ids=case.affected_assets,
        batches=batches,
    )


def require_current_scope(store, case):
    if not case.scope_version and not case.scope_state:
        if store.get_meta("schema:scope-v2") == "1":
            raise ValueError("Legacy incident requires scope migration")
        return
    store.require_scope_schema()
    if case.scope_state != "reconciled":
        raise ValueError("Inventory source reconciliation is required")
    if scope_digest(current_snapshot(store, case)) != case.scope_digest:
        raise ValueError("Inventory source differs from current scope; reconcile before release")


def scope_actions_cover(store, case):
    """A terminal status or parent receipt alone does not authorize current leaf goods."""
    if not case.scope_version:
        return True
    actions = store.list_actions(incident_id=case.incident_id)
    batches = store.list_batches(batch_ids=case.affected_batches)
    for batch in batches:
        current = build_scope_snapshot(
            tenant_id=case.tenant_id,
            store_id=case.store_id,
            asset_ids=case.affected_assets,
            batches=[batch],
        )["batches"][0]
        covered = False
        for action in actions:
            if (
                action["tool_name"] != "apply_batch_disposition"
                or action["status"] != "completed"
                or action["request"].get("disposition") != batch["disposition"]
            ):
                continue
            binding = action.get("target_snapshot_json") or action.get("target_snapshot")
            if isinstance(binding, str):
                binding = json.loads(binding)
            if binding and current in binding["scope"]["batches"]:
                covered = True
                break
        if not covered:
            return False
    return bool(batches)
