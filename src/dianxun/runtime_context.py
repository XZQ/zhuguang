"""ContextCoordinator storage participating in the business-state transaction."""

from __future__ import annotations

import json

from .context_bus import ContextBus, ContextExpired, ContextVersionConflict, TaskContext, timestamp


class RuntimeContextBus(ContextBus):
    def __init__(self, store, tenant_id: str):
        super().__init__(tenant_id=tenant_id)
        self.store = store

    def create(
        self, task_id, trace_id, trigger="manual", scope=None, *, ttl_seconds=86400, now=None
    ):
        # Reuse context validation/defaults without retaining an in-memory authoritative copy.
        context = ContextBus(tenant_id=self.tenant_id).create(
            task_id, trace_id, trigger, scope, ttl_seconds=ttl_seconds, now=now
        )
        with self.store.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO runtime_contexts(tenant_id, task_id, store_id, version, payload_json)
                   VALUES(?, ?, ?, ?, ?) ON CONFLICT(tenant_id, task_id) DO NOTHING""",
                (self.tenant_id, task_id, context.scope["store_id"], 1, self._serialize(context)),
            )
            if cursor.rowcount != 1:
                raise ContextVersionConflict("Runtime context already exists")
        return context

    def get(self, task_id, *, allow_expired=False, now=None):
        with self.store.transaction() as conn:
            lock = " FOR UPDATE" if self.store.backend_name == "postgresql" else ""
            row = conn.execute(
                "SELECT payload_json FROM runtime_contexts WHERE tenant_id = ? AND task_id = ?"
                + lock,
                (self.tenant_id, task_id),
            ).fetchone()
        if row is None:
            raise KeyError("Unknown runtime context")
        raw = row["payload_json"]
        context = TaskContext.from_snapshot(json.loads(raw) if isinstance(raw, str) else raw)
        if not allow_expired and context.is_expired(now):
            raise ContextExpired("Runtime context expired")
        return context

    def commit(self, context, *, expected_version=None, allow_expired=False, now=None):
        from .context_bus import utc_now

        self._assert_tenant(context)
        current = now or utc_now()
        if not allow_expired and context.is_expired(current):
            raise ContextExpired("Runtime context expired")
        expected = context.version if expected_version is None else expected_version
        if context.version != expected or expected < 1:
            raise ContextVersionConflict("Runtime context version conflict")
        candidate = context.clone()
        candidate.version += 1
        candidate.updated_at = timestamp(current)
        with self.store.transaction() as conn:
            cursor = conn.execute(
                """UPDATE runtime_contexts SET version = ?, payload_json = ?
                   WHERE tenant_id = ? AND task_id = ? AND version = ?""",
                (
                    candidate.version,
                    self._serialize(candidate),
                    self.tenant_id,
                    context.task_id,
                    expected,
                ),
            )
            if cursor.rowcount != 1:
                raise ContextVersionConflict("Runtime context version conflict")
        context.version = candidate.version
        context.updated_at = candidate.updated_at
        return candidate
