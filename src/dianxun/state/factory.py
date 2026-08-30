"""Configuration boundary for selecting a state-store backend."""

from __future__ import annotations

import os
from pathlib import Path

from .postgres import PostgresStateStore
from .protocols import StateStoreProtocol
from .store import SQLiteStateStore


def create_state_store(
    target: str | Path | None = None,
    *,
    tenant_id: str | None = None,
    runtime_role: str | None = None,
    store_id: str | None = None,
) -> StateStoreProtocol:
    """Create SQLite locally or PostgreSQL when a database URL is supplied."""
    configured: str | Path
    if target is None:
        configured = (
            os.environ.get("DIANXUN_DATABASE_URL")
            or os.environ.get("DIANXUN_STATE_DB")
            or Path.cwd() / "demo" / "state" / "runtime.db"
        )
    else:
        configured = target

    raw = str(configured)
    if raw.startswith(("postgresql://", "postgres://")):
        return PostgresStateStore(
            raw,
            tenant_id=tenant_id or os.environ.get("DIANXUN_TENANT_ID"),
            runtime_role=runtime_role or os.environ.get("DIANXUN_RUNTIME_ROLE", "runtime"),
            store_id=store_id or os.environ.get("DIANXUN_STORE_ID"),
        )
    return SQLiteStateStore(Path(raw).expanduser().resolve())
