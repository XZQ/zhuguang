"""Structural contracts shared by state-store backends.

The domain and MCP layers depend on these small DB-API-shaped contracts instead
of importing a concrete database driver.  SQLite remains the zero-dependency
local backend; PostgreSQL/PolarDB is loaded lazily when configured.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class CursorProtocol(Protocol):
    """Subset of cursor/result behavior used by the repositories."""

    rowcount: int

    def fetchone(self) -> Mapping[str, Any] | None: ...

    def fetchall(self) -> list[Mapping[str, Any]]: ...


class ConnectionProtocol(Protocol):
    """Driver-neutral connection surface used by explicit SQL mutations."""

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> CursorProtocol: ...

    def executemany(self, sql: str, parameters: Iterable[Sequence[Any]]) -> CursorProtocol: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class StateStoreProtocol(Protocol):
    """Business-state repository contract consumed by services and adapters."""

    backend_name: str
    database_identity: str

    def connect(self) -> ConnectionProtocol: ...

    def transaction(self) -> AbstractContextManager[ConnectionProtocol]: ...

    def create_schema(self) -> None: ...

    def ensure_schema(self) -> None: ...

    def initialize(self, seed: dict[str, Any], *, reset: bool = True) -> str: ...

    def initialize_from_file(self, seed_path: str | Path, *, reset: bool = True) -> str: ...

    def get_meta(self, key: str) -> str | None: ...

    def set_meta(self, key: str, value: str) -> None: ...

    def now(self) -> str: ...

    def advance_time(self, *, minutes: int) -> str: ...

    def next_id(self, conn: ConnectionProtocol, prefix: str) -> str: ...

    def list_devices(
        self,
        *,
        device_id: str | None = None,
        store_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_device_readings(
        self,
        *,
        device_id: str,
        since: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_batches(
        self,
        *,
        device_id: str | None = None,
        store_id: str | None = None,
        batch_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_sales_holds(
        self,
        *,
        incident_id: str | None = None,
        batch_ids: list[str] | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_approvals(
        self,
        *,
        approval_id: str | None = None,
        action_id: str | None = None,
        incident_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_workorders(
        self,
        *,
        workorder_id: str | None = None,
        action_id: str | None = None,
        incident_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_verifications(
        self,
        *,
        incident_id: str,
        subject: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_actions(
        self,
        *,
        incident_id: str,
        action_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_manual_evidence(self, *, incident_id: str) -> list[dict[str, Any]]: ...

    def list_audit_log(self, *, incident_id: str) -> list[dict[str, Any]]: ...

    def get_incident(self, incident_id: str) -> dict[str, Any] | None: ...

    def save_incident(self, case: dict[str, Any]) -> None: ...

    def expire_approvals(self) -> int: ...

    def consume_tool_failure(self, tool_name: str) -> dict[str, str] | None: ...


class StoreIntegrityError(RuntimeError):
    """Normalized integrity failure raised by optional database drivers."""
