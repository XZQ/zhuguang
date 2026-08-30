"""State-store backends for local evidence and managed PolarDB PostgreSQL."""

from .factory import create_state_store
from .postgres import PostgresStateStore
from .protocols import ConnectionProtocol, StateStoreProtocol, StoreIntegrityError
from .store import SQLiteStateStore, StateStore

__all__ = [
    "ConnectionProtocol",
    "PostgresStateStore",
    "SQLiteStateStore",
    "StateStore",
    "StateStoreProtocol",
    "StoreIntegrityError",
    "create_state_store",
]
