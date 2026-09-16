"""Explicit, transactional scope-v2 upgrade; never run by a readiness probe."""

from __future__ import annotations

import json
from importlib import resources

from ..domain.scope import build_scope_snapshot, scope_digest

MARKER = "schema:scope-v2"
_COLUMNS = {
    "inventory_batches": {"lifecycle": "TEXT NOT NULL DEFAULT 'active'"},
    "approvals": {
        "scope_version": "INTEGER",
        "target_snapshot_json": "TEXT",
        "applicability": "TEXT NOT NULL DEFAULT 'requires_review'",
    },
    "actions": {"scope_version": "INTEGER", "target_snapshot_json": "TEXT"},
    "verifications": {"scope_version": "INTEGER", "scope_digest": "TEXT"},
}
_TABLES = (
    """CREATE TABLE IF NOT EXISTS scope_revisions (
        incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
        scope_version INTEGER NOT NULL CHECK(scope_version > 0),
        change_id TEXT NOT NULL, tenant_id TEXT NOT NULL, store_id TEXT NOT NULL,
        actor TEXT NOT NULL, source_ref TEXT NOT NULL,
        before_json TEXT, after_json TEXT NOT NULL, request_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(incident_id, scope_version), UNIQUE(incident_id, change_id))""",
    """CREATE TABLE IF NOT EXISTS batch_lineage (
        child_batch_id TEXT PRIMARY KEY REFERENCES inventory_batches(batch_id),
        parent_batch_id TEXT NOT NULL REFERENCES inventory_batches(batch_id),
        tenant_id TEXT NOT NULL, store_id TEXT NOT NULL, change_id TEXT NOT NULL,
        parent_quantity INTEGER NOT NULL CHECK(parent_quantity > 0),
        child_quantity INTEGER NOT NULL CHECK(child_quantity > 0),
        created_at TEXT NOT NULL, CHECK(child_batch_id <> parent_batch_id))""",
)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def migrate(store):
    """Admin-only on PG; caller must stop writers during an offline upgrade."""
    with store.transaction() as conn:
        if store.backend_name == "postgresql":
            # Prevent writes and concurrent migrations while legacy snapshots are captured.
            conn.execute(
                "LOCK TABLE incidents, inventory_batches, approvals, actions, "
                "verifications IN ACCESS EXCLUSIVE MODE"
            )
        for table, columns in _COLUMNS.items():
            if store.backend_name == "sqlite":
                existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            else:
                existing = {
                    r["column_name"]
                    for r in conn.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=?",
                        (table,),
                    ).fetchall()
                }
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        for ddl in _TABLES:
            conn.execute(ddl)
        if store.backend_name == "postgresql":
            script = (
                resources.files("dianxun.state.sql")
                .joinpath("postgres_scope_security.sql")
                .read_text(encoding="utf-8")
            )
            conn._connection.execute(script, prepare=False)
        for row in conn.execute(
            "SELECT incident_id, case_json FROM incidents WHERE incident_status <> 'CLOSED' "
            "ORDER BY incident_id"
        ).fetchall():
            case = row["case_json"]
            case = json.loads(case) if isinstance(case, str) else dict(case)
            if case.get("scope_version", 0) > 0 or case.get("scope_state"):
                continue
            snapshot = None
            batches = []
            for batch_id in case.get("affected_batches", []):
                batch = conn.execute(
                    "SELECT * FROM inventory_batches WHERE batch_id=?", (batch_id,)
                ).fetchone()
                if batch is None:
                    break
                batches.append(dict(batch))
            if len(batches) == len(case.get("affected_batches", [])):
                try:
                    snapshot = build_scope_snapshot(
                        tenant_id=case["tenant_id"],
                        store_id=case["store_id"],
                        asset_ids=case.get("affected_assets", []),
                        batches=batches,
                    )
                except ValueError:
                    pass  # Preserve the original IDs; never silently trim invalid legacy scope.
            case.update(
                scope_version=1 if snapshot else 0,
                scope_snapshot=snapshot,
                scope_digest=scope_digest(snapshot) if snapshot else None,
                # Legacy records cannot prove prior quantity/location or absence of new exposure.
                scope_state="requires_reconciliation",
                version=case.get("version", 0) + 1,
            )
            conn.execute(
                "UPDATE incidents SET case_json=? WHERE incident_id=?",
                (_json(case), row["incident_id"]),
            )
            if snapshot:
                conn.execute(
                    """INSERT INTO scope_revisions
                    (incident_id, scope_version, change_id, tenant_id, store_id, actor,
                     source_ref, before_json, after_json, request_json, created_at)
                    VALUES (?,1,'scope-v2-migration',?,?,'Migration',
                            'legacy-inventory-unreconciled',NULL,?,'{}',CURRENT_TIMESTAMP)""",
                    (row["incident_id"], case["tenant_id"], case["store_id"], _json(snapshot)),
                )
        conn.execute(
            "INSERT INTO meta(key,value) VALUES (?,'1') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (MARKER,),
        )


def require_schema(store):
    with store._reader() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (MARKER,)).fetchone()
        if row is None or row["value"] != "1":
            raise RuntimeError("scope-v2 migration required before enabling scope writes")
        for table, columns in _COLUMNS.items():
            conn.execute(f"SELECT {', '.join(columns)} FROM {table} LIMIT 0")
        conn.execute("SELECT incident_id,scope_version,after_json FROM scope_revisions LIMIT 0")
        conn.execute("SELECT child_batch_id,parent_batch_id FROM batch_lineage LIMIT 0")
