"""Transactional scope revision core. Public write cutover requires the v2 safety gates."""

from __future__ import annotations

import json
import math
from dataclasses import asdict

from .context_bus import ContextVersionConflict, timestamp
from .domain import IncidentStatus, Phase, WorkStatus
from .domain.scope import build_scope_snapshot, scope_digest, validate_split
from .runtime_context import RuntimeContextBus


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ScopeRevisionService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store

    def reconcile(self, *, principal, incident_id, expected_versions, change_id, source_ref):
        """Human source attestation snapshots facts, never manufactures inventory or receipts."""
        if principal.actor != "Human" or principal not in self.runtime.principals.values():
            raise PermissionError("Only a registered Human can reconcile inventory scope")
        if not all(isinstance(v, str) and v.strip() for v in (change_id, source_ref)):
            raise ValueError("Stable change ID and source reference are required")
        from .scope_guard import current_snapshot

        request = dict(
            incident_id=incident_id,
            expected_versions=expected_versions,
            change_id=change_id,
            source_ref=source_ref,
            worker_id=principal.worker_id,
            operation="reconcile",
        )
        with self.store.transaction() as conn:
            self.store.require_scope_schema()
            self.runtime.recovery.lock_scope(principal)
            case = self.runtime.incidents.get(incident_id)
            if (case.tenant_id, case.store_id) != (principal.tenant_id, principal.store_id):
                raise PermissionError("Incident is outside Human scope")
            prior = conn.execute(
                "SELECT incident_id,scope_version,request_json FROM scope_revisions "
                "WHERE tenant_id=? AND store_id=? AND change_id=?",
                (principal.tenant_id, principal.store_id, change_id),
            ).fetchall()
            if prior:
                if any(row["request_json"] != _json(request) for row in prior):
                    raise ValueError("Change ID already belongs to a different request")
                return {
                    "versions": {r["incident_id"]: r["scope_version"] for r in prior},
                    "historical_replay": True,
                }
            if case.incident_status == IncidentStatus.CLOSED:
                raise ValueError("Closed history is immutable; open a linked incident")
            rows = conn.execute(
                "SELECT incident_id FROM incidents WHERE tenant_id=? AND store_id=? "
                "AND incident_status <> 'CLOSED' ORDER BY incident_id",
                (principal.tenant_id, principal.store_id),
            ).fetchall()
            cases = [self.runtime.incidents.get(row["incident_id"]) for row in rows]
            selected = {incident_id}
            assets, batches = set(case.affected_assets), set(case.affected_batches)
            while True:
                related = [
                    c
                    for c in cases
                    if set(c.affected_assets) & assets or set(c.affected_batches) & batches
                ]
                ids = {c.incident_id for c in related}
                if ids == selected:
                    break
                selected = ids
                assets.update(a for c in related for a in c.affected_assets)
                batches.update(b for c in related for b in c.affected_batches)
            if set(expected_versions) != selected:
                raise ValueError("Expected versions must cover every related open incident")
            bus = RuntimeContextBus(self.store, principal.tenant_id)
            versions = {}
            for current in related:
                context = bus.get(current.incident_id, allow_expired=True, now=self.runtime.clock())
                expected = expected_versions[current.incident_id]
                if expected != {
                    "scope_version": current.scope_version,
                    "context_version": context.version,
                } or any(type(v) is not int for v in expected.values()):
                    raise ContextVersionConflict("Related incident scope/context version changed")
                snapshot = current_snapshot(self.store, current)
                before = current.scope_snapshot
                current.scope_version += 1
                current.scope_snapshot = snapshot
                current.scope_digest = scope_digest(snapshot)
                current.scope_state = "reconciled"
                current.affected_batches = [b["batch_id"] for b in snapshot["batches"]]
                current.phase = Phase.DETECT_CONTAIN
                current.incident_status = IncidentStatus.OPEN
                current.work_status = WorkStatus.READY
                self.runtime.incidents.save(current)
                self._record_revision(
                    conn, current, principal, source_ref, change_id, before, request
                )
                self._restart(conn, current, context, bus, current.affected_batches)
                versions[current.incident_id] = current.scope_version
            return {"versions": versions, "historical_replay": False}

    def _record_revision(
        self,
        conn,
        current,
        principal,
        source_ref,
        change_id,
        before,
        request,
        tool_name="runtime_reconcile_scope",
    ):
        conn.execute(
            "INSERT INTO scope_revisions "
            "(incident_id,scope_version,change_id,tenant_id,store_id,actor,source_ref,"
            "before_json,after_json,request_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                current.incident_id,
                current.scope_version,
                change_id,
                current.tenant_id,
                current.store_id,
                principal.worker_id,
                source_ref,
                _json(before),
                _json(current.scope_snapshot),
                _json(request),
                self.store.now(),
            ),
        )
        self.store.record_audit(
            conn,
            request_id=change_id,
            actor=principal.worker_id,
            tool_name=tool_name,
            incident_id=current.incident_id,
            action_id=None,
            policy=None,
            request=request,
            response={"scope_version": current.scope_version, "scope_digest": current.scope_digest},
            created_at=self.store.now(),
        )

    def _restart(self, conn, current, context, bus, changed_ids):
        context.recovery.setdefault("scope_history", []).append(
            {
                "scope_version": current.scope_version - 1,
                "generation": context.recovery.get("generation", 0),
                "checkpoints": {k: asdict(v) for k, v in context.checkpoints.items()},
                "phases": context.recovery.get("phases", {}),
            }
        )
        for assignment in context.assignments:
            if assignment.status in {"assigned", "running", "waiting"}:
                assignment.status = "cancelled"
                assignment.error = "scope_revision"
                assignment.updated_at = timestamp(self.runtime.clock())
        for main in context.recovery.get("orchestration", []):
            if main["status"] in {"assigned", "running", "waiting"}:
                main["status"] = "cancelled"
        context.checkpoints.clear()
        context.recovery["generation"] = context.recovery.get("generation", 0) + 1
        context.recovery["generation_started_at"] = timestamp(self.runtime.clock())
        context.recovery["phases"] = {}
        context.recovery["scope_containment_required"] = sorted(changed_ids)
        context.coordination_status = "active"
        for row in conn.execute(
            "SELECT a.approval_id FROM approvals a JOIN actions x ON x.action_id=a.action_id "
            "WHERE a.incident_id=? AND x.tool_name='create_approval'",
            (current.incident_id,),
        ).fetchall():
            try:
                self.runtime.mcp._validate_approval_binding(
                    conn, row["approval_id"], current.incident_id
                )
            except (ValueError, PermissionError):
                conn.execute(
                    "UPDATE approvals SET applicability='requires_review' WHERE approval_id=?",
                    (row["approval_id"],),
                )
        bus.commit(context, allow_expired=True, now=self.runtime.clock())

    def revise(self, *, principal, incident_id, expected_versions, change_id, source_ref, changes):
        if principal.actor != "Human" or principal not in self.runtime.principals.values():
            raise PermissionError("Only a registered Human can revise inventory scope")
        if not all(isinstance(v, str) and v.strip() for v in (change_id, source_ref)):
            raise ValueError("A stable change ID and source reference are required")
        if not isinstance(changes, list) or not changes:
            raise ValueError("At least one structured inventory change is required")
        request = dict(
            incident_id=incident_id,
            expected_versions=expected_versions,
            change_id=change_id,
            source_ref=source_ref,
            changes=changes,
            worker_id=principal.worker_id,
        )
        with self.store.transaction() as conn:
            self.store.require_scope_schema()
            self.runtime.recovery.lock_scope(principal)
            case = self.runtime.incidents.get(incident_id)
            if (case.tenant_id, case.store_id) != (principal.tenant_id, principal.store_id):
                raise PermissionError("Incident is outside Human scope")
            prior = conn.execute(
                "SELECT incident_id,scope_version,request_json FROM scope_revisions "
                "WHERE tenant_id=? AND store_id=? AND change_id=? ORDER BY incident_id",
                (principal.tenant_id, principal.store_id, change_id),
            ).fetchall()
            if prior:
                if any(row["request_json"] != _json(request) for row in prior):
                    raise ValueError("Change ID already belongs to a different request")
                return {
                    "versions": {r["incident_id"]: r["scope_version"] for r in prior},
                    "historical_replay": True,
                }
            if case.incident_status == IncidentStatus.CLOSED:
                raise ValueError("Closed history cannot be revised; open a linked incident")
            touched = []
            additions = []
            for change in changes:
                if not isinstance(change, dict) or change.get("op") not in {"split", "move", "add"}:
                    raise ValueError("Unsupported scope change")
                if change["op"] == "add":
                    if set(change) != {"op", "batch"} or not isinstance(change["batch"], dict):
                        raise ValueError("Unexpected add fields")
                    batch = change["batch"]
                    required = {
                        "batch_id",
                        "device_id",
                        "sku_id",
                        "product_name",
                        "quantity",
                        "storage_min_c",
                        "storage_max_c",
                        "policy_ref",
                    }
                    if set(batch) != required or batch["device_id"] not in case.affected_assets:
                        raise ValueError("New batch must identify an original incident asset")
                    if (
                        not isinstance(batch["product_name"], str)
                        or not batch["product_name"].strip()
                    ):
                        raise ValueError("Product name is required")
                    if any(
                        type(batch[k]) not in {int, float} or not math.isfinite(batch[k])
                        for k in ("storage_min_c", "storage_max_c")
                    ) or (batch["storage_min_c"] > batch["storage_max_c"]):
                        raise ValueError("Invalid storage limits")
                    new_batch = {
                        **batch,
                        "store_id": principal.store_id,
                        "disposition": "unknown",
                        "safe_for_sale": 0,
                        "lifecycle": "active",
                        "updated_at": self.store.now(),
                    }
                    build_scope_snapshot(
                        tenant_id=principal.tenant_id,
                        store_id=principal.store_id,
                        asset_ids=case.affected_assets,
                        batches=[new_batch],
                    )
                    if batch["quantity"] <= 0:
                        raise ValueError("New inventory quantity must be positive")
                    self._require_device(conn, batch["device_id"], principal)
                    additions.append(new_batch)
                    continue
                extra = "children" if change["op"] == "split" else "device_id"
                if set(change) != {"op", "batch_id", extra}:
                    raise ValueError("Unexpected change fields")
                batch_id = change["batch_id"]
                if not isinstance(batch_id, str) or batch_id not in case.affected_batches:
                    raise ValueError("Split parent must belong to the incident")
                if batch_id in touched:
                    raise ValueError("A batch can change only once per request")
                touched.append(batch_id)
            lock = " FOR UPDATE" if self.store.backend_name == "postgresql" else ""
            rows = conn.execute(
                "SELECT incident_id FROM incidents WHERE tenant_id=? AND store_id=? "
                "AND incident_status <> 'CLOSED' ORDER BY incident_id" + lock,
                (principal.tenant_id, principal.store_id),
            ).fetchall()
            affected = [self.runtime.incidents.get(r["incident_id"]) for r in rows]
            affected = [
                c
                for c in affected
                if set(c.affected_batches).intersection(touched)
                or any(b["device_id"] in c.affected_assets for b in additions)
                or any(
                    change["op"] == "move" and change["device_id"] in c.affected_assets
                    for change in changes
                )
            ]
            if set(expected_versions) != {c.incident_id for c in affected}:
                raise ValueError("Expected versions must cover every related open incident")
            bus = RuntimeContextBus(self.store, principal.tenant_id)
            contexts = {}
            for current in affected:
                expected = expected_versions[current.incident_id]
                context = bus.get(current.incident_id, allow_expired=True, now=self.runtime.clock())
                if (
                    set(expected) != {"scope_version", "context_version"}
                    or type(expected["scope_version"]) is not int
                    or type(expected["context_version"]) is not int
                    or expected["scope_version"] != current.scope_version
                    or expected["context_version"] != context.version
                ):
                    raise ContextVersionConflict("Related incident scope/context version changed")
                contexts[current.incident_id] = context
            replacements = {}
            changed_ids = set()
            for batch in additions:
                self._insert_batch(conn, batch)
                changed_ids.add(batch["batch_id"])
            existing_changes = [c for c in changes if c["op"] != "add"]
            for change in sorted(existing_changes, key=lambda c: c["batch_id"]):
                parent_row = conn.execute(
                    "SELECT * FROM inventory_batches WHERE batch_id=?" + lock,
                    (change["batch_id"],),
                ).fetchone()
                if parent_row is None or parent_row["store_id"] != principal.store_id:
                    raise ValueError("Split parent is missing or outside store")
                parent = dict(parent_row)
                if parent["lifecycle"] != "active" or parent["disposition"] not in {
                    "unknown",
                    "quarantined",
                }:
                    raise ValueError("Only active nonterminal inventory can change")
                if change["op"] == "move":
                    self._require_device(conn, change["device_id"], principal)
                    if change["device_id"] == parent["device_id"]:
                        raise ValueError("Move does not change inventory scope")
                    conn.execute(
                        "UPDATE inventory_batches SET device_id=?,updated_at=? WHERE batch_id=?",
                        (change["device_id"], self.store.now(), parent["batch_id"]),
                    )
                    changed_ids.add(parent["batch_id"])
                    continue
                children = change["children"]
                if not isinstance(children, list) or any(
                    not isinstance(c, dict) or set(c) != {"batch_id", "quantity"} for c in children
                ):
                    raise ValueError("Children may only specify new IDs and integer quantities")
                children = validate_split(parent, [{**parent, **c} for c in children])
                for child in children:
                    child["updated_at"] = self.store.now()
                    self._insert_batch(conn, child)
                    changed_ids.add(child["batch_id"])
                    conn.execute(
                        """INSERT INTO batch_lineage
                        (child_batch_id,parent_batch_id,tenant_id,store_id,change_id,
                         parent_quantity,child_quantity,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            child["batch_id"],
                            parent["batch_id"],
                            principal.tenant_id,
                            principal.store_id,
                            change_id,
                            parent["quantity"],
                            child["quantity"],
                            self.store.now(),
                        ),
                    )
                conn.execute(
                    "UPDATE inventory_batches SET quantity=0,lifecycle='retired', "
                    "safe_for_sale=0,updated_at=? WHERE batch_id=?",
                    (self.store.now(), parent["batch_id"]),
                )
                replacements[parent["batch_id"]] = [c["batch_id"] for c in children]
            versions = {}
            for current in affected:
                before = current.scope_snapshot
                new_ids = []
                for batch_id in current.affected_batches:
                    new_ids.extend(replacements.get(batch_id, [batch_id]))
                new_ids.extend(
                    b["batch_id"] for b in additions if b["device_id"] in current.affected_assets
                )
                new_ids.extend(
                    change["batch_id"]
                    for change in changes
                    if change["op"] == "move"
                    and change["device_id"] in current.affected_assets
                    and change["batch_id"] not in new_ids
                )
                batches = self.store.list_batches(batch_ids=new_ids)
                if {r["batch_id"] for r in batches} != set(new_ids):
                    raise ValueError("Current incident inventory requires reconciliation")
                snapshot = build_scope_snapshot(
                    tenant_id=current.tenant_id,
                    store_id=current.store_id,
                    asset_ids=current.affected_assets,
                    batches=batches,
                )
                current.affected_batches = sorted(new_ids)
                current.scope_version += 1
                current.scope_snapshot = snapshot
                current.scope_digest = scope_digest(snapshot)
                # A split does not attest other unexplained inventory differences.
                current.phase = Phase.DETECT_CONTAIN
                current.incident_status = IncidentStatus.OPEN
                current.work_status = WorkStatus.READY
                self.runtime.incidents.save(current)
                conn.execute(
                    """INSERT INTO scope_revisions
                    (incident_id,scope_version,change_id,tenant_id,store_id,actor,source_ref,
                     before_json,after_json,request_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        current.incident_id,
                        current.scope_version,
                        change_id,
                        current.tenant_id,
                        current.store_id,
                        principal.worker_id,
                        source_ref,
                        _json(before),
                        _json(snapshot),
                        _json(request),
                        self.store.now(),
                    ),
                )
                context = contexts[current.incident_id]
                self._restart(conn, current, context, bus, changed_ids.intersection(new_ids))
                versions[current.incident_id] = current.scope_version
                self.store.record_audit(
                    conn,
                    request_id=change_id,
                    actor=principal.worker_id,
                    tool_name="runtime_revise_scope",
                    incident_id=current.incident_id,
                    action_id=None,
                    policy=None,
                    request=request,
                    response={
                        "scope_version": current.scope_version,
                        "scope_digest": current.scope_digest,
                    },
                    created_at=self.store.now(),
                )
            return {"versions": versions, "historical_replay": False}

    def _require_device(self, conn, device_id, principal):
        if (
            not isinstance(device_id, str)
            or not conn.execute(
                "SELECT d.device_id FROM devices d JOIN stores s ON s.store_id=d.store_id "
                "WHERE d.device_id=? AND s.store_id=? AND s.tenant_id=?",
                (device_id, principal.store_id, principal.tenant_id),
            ).fetchone()
        ):
            raise ValueError("Target device is outside Human scope")

    def _insert_batch(self, conn, batch):
        if conn.execute(
            "SELECT batch_id FROM inventory_batches WHERE batch_id=?", (batch["batch_id"],)
        ).fetchone():
            raise ValueError("Batch ID already exists")
        columns = (
            "batch_id",
            "store_id",
            "device_id",
            "sku_id",
            "product_name",
            "quantity",
            "storage_min_c",
            "storage_max_c",
            "disposition",
            "safe_for_sale",
            "policy_ref",
            "updated_at",
            "lifecycle",
        )
        conn.execute(
            f"INSERT INTO inventory_batches ({','.join(columns)}) "
            f"VALUES ({','.join('?' for _ in columns)})",
            tuple(batch[k] for k in columns),
        )
