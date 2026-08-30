"""PostgreSQL/PolarDB implementation of the state-store contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from importlib import resources
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .protocols import ConnectionProtocol, CursorProtocol, StoreIntegrityError
from .store import SQLiteStateStore

_SQL_PACKAGE = "dianxun.state.sql"
_PROFILE_FILES = {
    "core": "postgres_schema.sql",
    "security": "postgres_security.sql",
    "cron": "postgres_cron.sql",
    "archive": "postgres_archive.sql",
}


def _load_driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - exercised without the optional extra
        raise RuntimeError(
            "PostgreSQL support requires the optional dependency: pip install 'dianxun[postgres]'"
        ) from exc
    return psycopg, dict_row


def redact_dsn(dsn: str) -> str:
    """Return a stable database identity without credentials or query secrets."""
    parsed = urlsplit(dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        return "postgresql://configured"
    hostname = parsed.hostname or "configured"
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    username = f"{parsed.username}@" if parsed.username else ""
    return urlunsplit(("postgresql", f"{username}{hostname}", parsed.path, "", ""))


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_row(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: _normalize_value(value) for key, value in row.items()}


def qmark_to_postgres(sql: str) -> str:
    """Translate DB-API qmark placeholders while preserving quoted SQL text."""
    output: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            output.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif char == "?":
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


class _PostgresResult(CursorProtocol):
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    def fetchone(self) -> dict[str, Any] | None:
        return _normalize_row(self._cursor.fetchone())

    def fetchall(self) -> list[dict[str, Any]]:
        return [_normalize_row(row) or {} for row in self._cursor.fetchall()]


class _PostgresConnection(ConnectionProtocol):
    def __init__(self, connection: Any, driver: Any) -> None:
        self._connection = connection
        self._driver = driver

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> _PostgresResult:
        try:
            cursor = self._connection.execute(qmark_to_postgres(sql), parameters)
        except self._driver.IntegrityError as exc:
            raise StoreIntegrityError(str(exc)) from exc
        return _PostgresResult(cursor)

    def executemany(
        self,
        sql: str,
        parameters: Iterable[Sequence[Any]],
    ) -> _PostgresResult:
        try:
            cursor = self._connection.cursor()
            cursor.executemany(qmark_to_postgres(sql), parameters)
        except self._driver.IntegrityError as exc:
            raise StoreIntegrityError(str(exc)) from exc
        return _PostgresResult(cursor)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


class PostgresStateStore(SQLiteStateStore):
    """PolarDB PostgreSQL backend reusing the audited repository operations."""

    backend_name = "postgresql"

    def __init__(
        self,
        dsn: str,
        *,
        tenant_id: str | None = None,
        runtime_role: str = "runtime",
        store_id: str | None = None,
    ) -> None:
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgreSQL DSN must start with postgresql:// or postgres://")
        self.dsn = dsn
        self.tenant_id = tenant_id
        self.runtime_role = runtime_role
        self.runtime_store_id = store_id
        self.database_identity = redact_dsn(dsn)

    def connect(self) -> _PostgresConnection:
        driver, dict_row = _load_driver()
        raw = driver.connect(self.dsn, row_factory=dict_row)
        connection = _PostgresConnection(raw, driver)
        connection.execute(
            "SELECT set_config('dianxun.tenant_id', ?, false)",
            (self.tenant_id or "",),
        )
        connection.execute(
            "SELECT set_config('dianxun.runtime_role', ?, false)",
            (self.runtime_role,),
        )
        connection.execute(
            "SELECT set_config('dianxun.store_id', ?, false)",
            (self.runtime_store_id or "",),
        )
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_schema(self) -> None:
        self.apply_profile("core")

    def ensure_schema(self) -> None:
        connection = self.connect()
        try:
            row = connection.execute("SELECT to_regclass('public.meta') AS relation").fetchone()
            if not row or row["relation"] is None:
                raise RuntimeError(
                    "PostgreSQL schema is not initialized; run "
                    "dianxun db-bootstrap --profile core first"
                )
            security = connection.execute(
                "SELECT to_regclass('public.dianxun_principal_scope') AS relation"
            ).fetchone()
            if security and security["relation"] is not None:
                principal = connection.execute(
                    "SELECT tenant_id, runtime_role, store_id FROM dianxun_current_scope()"
                ).fetchone()
                if principal is None:
                    raise PermissionError(
                        "Database login is not registered in dianxun_principal_scope"
                    )
                principal_tenant = str(principal["tenant_id"])
                if self.tenant_id and principal_tenant not in {"*", self.tenant_id}:
                    raise PermissionError(
                        "Configured tenant does not match database principal scope"
                    )
                principal_role = str(principal["runtime_role"])
                if self.runtime_role == "hq" and principal_role != "hq":
                    raise PermissionError(
                        "Configured HQ role is not granted by database principal scope"
                    )
                principal_store = principal["store_id"]
                if self.runtime_store_id and principal_store not in {None, self.runtime_store_id}:
                    raise PermissionError(
                        "Configured store does not match database principal scope"
                    )
        finally:
            connection.close()

    def apply_profile(self, profile: str) -> None:
        filename = _PROFILE_FILES.get(profile)
        if filename is None:
            raise ValueError(f"Unsupported PostgreSQL profile: {profile}")
        script = resources.files(_SQL_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
        connection = self.connect()
        try:
            raw = connection._connection  # migrations need PostgreSQL's multi-statement parser
            raw.execute(script, prepare=False)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def next_id(self, conn: ConnectionProtocol, prefix: str) -> str:
        key = f"seq:{prefix}"
        row = conn.execute(
            """INSERT INTO meta(key, value) VALUES(?, '1')
               ON CONFLICT(key) DO UPDATE
               SET value = ((meta.value)::bigint + 1)::text
               RETURNING value""",
            (key,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to allocate {prefix} identifier")
        return f"{prefix}_{int(row['value']):06d}"

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
        conn.execute(
            """SELECT ensure_audit_partition(
                   date_trunc('month', CAST(? AS timestamptz))::date
               )""",
            (created_at,),
        )
        return super().record_audit(
            conn,
            request_id=request_id,
            actor=actor,
            tool_name=tool_name,
            incident_id=incident_id,
            action_id=action_id,
            policy=policy,
            request=request,
            response=response,
            created_at=created_at,
        )
