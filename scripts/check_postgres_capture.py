"""Exercise real pg_dump/pg_restore on explicitly isolated synthetic test databases."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from dianxun import trace
from dianxun.adapters import LocalDemoAdapter
from dianxun.mcp.p0 import DEFAULT_SCENARIO_PATH, DEFAULT_SEED_PATH
from dianxun.runtime import RuntimePrincipal
from dianxun.runtime_replay import (
    capture_runtime,
    check_restored,
    database_fingerprint,
    pg_environment,
    render_runtime,
)
from dianxun.state import PostgresStateStore


def run(output: Path) -> dict:
    if os.environ.get("DIANXUN_ALLOW_TEST_DATABASE_RESET") != "1":
        raise ValueError("Explicit isolated test database reset opt-in required")
    source = PostgresStateStore(os.environ["DIANXUN_TEST_POSTGRES_DSN"])
    restored = PostgresStateStore(os.environ["DIANXUN_TEST_POSTGRES_RESTORE_DSN"])
    for store in (source, restored):
        with store.read_snapshot() as conn:
            name = conn.execute("SELECT current_database() AS name").fetchone()["name"]
            if "test" not in name.casefold():
                raise ValueError("Both actual database names must contain 'test'")
    if database_fingerprint(source) == database_fingerprint(restored):
        raise ValueError("Restore target must be a separate database")
    with restored.read_snapshot() as conn:
        count = conn.execute(
            "SELECT count(*) AS count FROM pg_tables "
            "WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
        ).fetchone()["count"]
        if count:
            raise ValueError("Restore target must be empty; no existing tables are overwritten")
    for executable in ("pg_dump", "pg_restore"):
        if not shutil.which(executable):
            raise ValueError(f"A compatible {executable} must be installed")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    source.apply_profile("core")
    source.initialize_from_file(DEFAULT_SEED_PATH, reset=True)
    trace_path = output / "trace.db"
    adapter = LocalDemoAdapter(
        db_path=source.dsn,
        scenario_path=DEFAULT_SCENARIO_PATH,
        trace_db_path=trace_path,
    )
    scenario = adapter.run()
    principal = RuntimePrincipal("Human", "synthetic-capture-test", "demo", "S03")
    bundle = output / "bundle"
    with trace.use_database(trace_path):
        capture = capture_runtime(
            bundle,
            adapter.mcp,
            principal,
            scenario["incident"]["incident_id"],
            quiesced=True,
            allow_isolated_dump=True,
        )
        restore = subprocess.run(
            [
                "pg_restore",
                "--no-owner",
                "--no-acl",
                "--no-password",
                "--exit-on-error",
                "--single-transaction",
                "--dbname=" + pg_environment(restored.dsn)["PGDATABASE"],
                str(bundle / "state.pgdump"),
            ],
            env=pg_environment(restored.dsn),
            capture_output=True,
            timeout=300,
            check=False,
        )
        if restore.returncode:
            raise RuntimeError(f"pg_restore failed (exit {restore.returncode})")
        verification = check_restored(
            bundle, SimpleNamespace(store=restored, policy=adapter.policy), principal
        )
        replay = render_runtime(bundle, bundle / "replay.html")
    result = {
        "data_origin": "synthetic_local_adapter_on_postgresql",
        "platform_authenticity_verified": False,
        "capture": capture,
        "restore_exit_code": restore.returncode,
        "verification": verification,
        "replay": replay,
    }
    (output / "verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.output)
    except Exception as exc:
        # DSNs, server diagnostics and raw restored data must not enter CI logs.
        raise SystemExit(f"PostgreSQL capture regression failed ({type(exc).__name__})") from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
