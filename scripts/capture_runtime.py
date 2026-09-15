"""Capture or check an existing isolated runtime. Never initializes or resets databases."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from dianxun import trace
from dianxun.domain import PolicyEngine
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH
from dianxun.runtime import RuntimePrincipal
from dianxun.runtime_replay import capture_runtime, check_restored, render_runtime
from dianxun.state import create_state_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--state", type=Path, help="Existing SQLite database")
    source.add_argument("--database-env", help="Environment variable holding a PostgreSQL DSN")
    parser.add_argument("--trace-db", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--incident")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--quiesced", action="store_true")
    parser.add_argument("--allow-isolated-dump", action="store_true")
    parser.add_argument("--pg-dump", default="pg_dump", help="Installed pg_dump executable")
    parser.add_argument(
        "--check-restored", type=Path, help="Existing bundle; compare restored DB only"
    )
    args = parser.parse_args()
    if args.database_env:
        database = os.environ.get(args.database_env, "")
        if not database.startswith(("postgresql://", "postgres://")):
            parser.error("database environment must contain an explicit PostgreSQL URL")
        store = create_state_store(database, tenant_id=args.tenant, store_id=args.store)
    else:
        if not args.state.is_file():
            parser.error("state database does not exist")
        store = create_state_store(args.state)
    principal = RuntimePrincipal("Human", "offline-capture", args.tenant, args.store)
    # MCPService.__init__ ensures/migrates schema; capture must never do that.
    mcp = SimpleNamespace(store=store, policy=PolicyEngine(args.policy))
    with trace.use_database(args.trace_db):
        if args.check_restored:
            result = check_restored(args.check_restored, mcp, principal)
        else:
            if not args.incident or not args.output:
                parser.error("capture requires --incident and a new --output directory")
            capture_runtime(
                args.output,
                mcp,
                principal,
                args.incident,
                quiesced=args.quiesced,
                allow_isolated_dump=args.allow_isolated_dump,
                pg_dump=args.pg_dump,
            )
            result = render_runtime(args.output, args.output / "replay.html")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Driver messages may include credentials. Keep command-line failures stable.
        raise SystemExit(
            "Runtime capture/check failed; inspect scope, quiescence and isolated DB configuration"
        ) from None
