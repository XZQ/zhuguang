"""Capture an existing, quiesced runtime and inspect it offline without executing actions."""

from __future__ import annotations

import hashlib
import html
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from . import trace
from .domain.models import stable_hash
from .operations import collect_casefile, decode
from .replay import write_json

BASE_FILES = {"casefile.json", "audit.jsonl", "trace.jsonl"}


def database_fingerprint(store):
    if store.backend_name == "sqlite":
        identity = str(store.path.resolve())
    else:
        # Query parameters, aliases and service files can override URL components.
        # Compare the actual endpoint/database, without keeping connection secrets.
        with store.read_snapshot() as conn:
            identity = dict(
                conn.execute(
                    "SELECT current_database() AS database, "
                    "inet_server_addr()::text AS address, inet_server_port() AS port"
                ).fetchone()
            )
    return stable_hash([store.backend_name, identity])


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pg_environment(dsn):
    from psycopg.conninfo import conninfo_to_dict

    aliases = {
        "dbname": "PGDATABASE",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "host": "PGHOST",
        "hostaddr": "PGHOSTADDR",
        "port": "PGPORT",
        "sslmode": "PGSSLMODE",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcrl": "PGSSLCRL",
        "connect_timeout": "PGCONNECT_TIMEOUT",
        "options": "PGOPTIONS",
        "application_name": "PGAPPNAME",
        "channel_binding": "PGCHANNELBINDING",
        "passfile": "PGPASSFILE",
        "service": "PGSERVICE",
    }
    fields = conninfo_to_dict(dsn)
    if fields.keys() - aliases.keys():
        raise ValueError(
            "Unsupported libpq option for capture; use an explicit service configuration"
        )
    env = dict(os.environ)
    env.update({aliases[key]: value for key, value in fields.items()})
    return env


def dump_postgres(store, conn, output, *, executable="pg_dump"):
    # Full DB snapshots may contain other incidents. Require a dedicated test DB.
    database = conn.execute("SELECT current_database() AS database").fetchone()["database"]
    if "test" not in database.casefold():
        raise ValueError("Runtime pg_dump capture requires a dedicated database named with 'test'")
    snapshot_id = conn.execute("SELECT pg_export_snapshot() AS snapshot").fetchone()["snapshot"]
    try:
        result = subprocess.run(
            [
                executable,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--no-password",
                f"--snapshot={snapshot_id}",
                f"--file={output}",
            ],
            env=pg_environment(store.dsn),
            capture_output=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "pg_dump could not complete; inspect isolated database connectivity"
        ) from exc
    if result.returncode:
        # Raw stderr can contain connection strings and authentication diagnostics.
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}); no evidence sealed")
    if not output.is_file() or output.stat().st_size == 0:
        raise ValueError("pg_dump produced no snapshot")
    return snapshot_id


def capture_runtime(
    directory,
    mcp,
    principal,
    incident_id,
    *,
    quiesced=False,
    allow_isolated_dump=False,
    pg_dump="pg_dump",
):
    if not quiesced:
        raise ValueError("Pause demo writes and Worker execution before capturing DB and Trace")
    store = mcp.store
    if store.backend_name == "postgresql" and not allow_isolated_dump:
        raise ValueError("Explicit isolated full-database dump opt-in required")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    snapshot_name = "state.pgdump" if store.backend_name == "postgresql" else "state.sqlite"
    with store.read_snapshot() as conn:
        casefile = collect_casefile(mcp, principal, incident_id, limit=100000)
        if casefile["truncated"] or casefile["trace"]["status"] != "available":
            raise ValueError("Incomplete runtime records; no evidence sealed")
        if not casefile["trace"]["rows"]:
            raise ValueError("No Trace rows for this incident; no evidence sealed")
        if store.backend_name == "postgresql":
            snapshot_id = dump_postgres(store, conn, directory / snapshot_name, executable=pg_dump)
        else:
            snapshot_id = "sqlite-read-transaction"
            with closing(sqlite3.connect(directory / snapshot_name)) as destination:
                conn.backup(destination)
        after = trace.read_trace(casefile["incident"]["trace_id"], limit=100001)
        if after != casefile["trace"]:
            raise ValueError("Trace changed during capture; pause writers and use a new directory")
    # Detect visible state changes during a long dump too. This does not prove quiescence
    # against unobserved writers; the operator assertion remains explicit in the manifest.
    with store.read_snapshot():
        current = collect_casefile(mcp, principal, incident_id, limit=100000)
    for key in ("incident", "context", "records", "trace", "business_time"):
        if current[key] != casefile[key]:
            raise ValueError("Runtime changed during capture; no evidence sealed")
    write_json(directory / "casefile.json", casefile)
    for filename, records in [
        ("audit.jsonl", casefile["records"]["audit_log"]),
        ("trace.jsonl", casefile["trace"]["rows"]),
    ]:
        (directory / filename).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
            encoding="utf-8",
            newline="\n",
        )
    names = BASE_FILES | {snapshot_name}
    manifest = {
        "schema_version": 2,
        "source_kind": "runtime_database_capture",
        "backend": store.backend_name,
        "incident_id": incident_id,
        "trace_id": casefile["incident"]["trace_id"],
        "snapshot_id": snapshot_id,
        "source_database_fingerprint": database_fingerprint(store),
        "operator_asserted_quiesced": True,
        "platform_authenticity_verified": False,
        "database_restore_verified": False,
        "claim_boundary": "Existing runtime capture. Source authenticity, physical events and "
        "platform messages require independent verification. Trace is a separate store; "
        "quiescence was asserted by the operator and checked for visible changes.",
        "files": {name: file_digest(directory / name) for name in sorted(names)},
    }
    write_json(directory / "manifest.json", manifest)
    return verify_runtime(directory)


def verify_runtime(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    backend = manifest.get("backend")
    database = "state.pgdump" if backend == "postgresql" else "state.sqlite"
    if (
        manifest.get("schema_version") != 2
        or manifest.get("source_kind") != "runtime_database_capture"
        or backend not in {"sqlite", "postgresql"}
        or set(manifest.get("files", {})) != BASE_FILES | {database}
    ):
        raise ValueError("Unsupported runtime replay manifest")
    for name, expected in manifest["files"].items():
        path = directory / name
        if path.is_symlink() or file_digest(path) != expected:
            raise ValueError(f"Runtime evidence integrity mismatch: {name}")
    casefile = json.loads((directory / "casefile.json").read_text(encoding="utf-8"))
    case = casefile["incident"]
    if (case["incident_id"], case["trace_id"], casefile["backend"]) != (
        manifest["incident_id"],
        manifest["trace_id"],
        backend,
    ) or casefile["truncated"]:
        raise ValueError("Runtime case correlation mismatch")
    for filename, expected in [
        ("audit.jsonl", casefile["records"]["audit_log"]),
        ("trace.jsonl", casefile["trace"]["rows"]),
    ]:
        actual = [
            json.loads(line)
            for line in (directory / filename).read_text(encoding="utf-8").splitlines()
        ]
        if actual != expected:
            raise ValueError(f"Runtime export mismatch: {filename}")
    if backend == "sqlite":
        with closing(
            sqlite3.connect((directory / database).resolve().as_uri() + "?mode=ro", uri=True)
        ) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Invalid SQLite snapshot")
            row = conn.execute(
                "SELECT case_json FROM incidents WHERE incident_id = ?", (case["incident_id"],)
            ).fetchone()
            if row is None or json.loads(row[0]) != case:
                raise ValueError("Snapshot and incident differ")
        from .state import SQLiteStateStore

        service = SimpleNamespace(
            store=SQLiteStateStore(directory / database),
            policy=SimpleNamespace(policy=casefile["current_policy"]),
        )
        principal = SimpleNamespace(tenant_id=case["tenant_id"], store_id=case["store_id"])
        _compare_database(casefile, service, principal)
    return {
        "passed": True,
        "incident_id": case["incident_id"],
        "status": case["incident_status"],
        "backend": backend,
        "database_restore_verified": False,
        "claim_boundary": manifest["claim_boundary"],
    }


def render_runtime(directory, output):
    directory, output = Path(directory), Path(output)
    result = verify_runtime(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    protected = [directory / name for name in {*manifest["files"], "manifest.json"}]
    if output.resolve() in {path.resolve() for path in protected} or (
        output.exists() and any(os.path.samefile(output, path) for path in protected)
    ):
        raise ValueError("Replay cannot overwrite sealed evidence")
    casefile = json.loads((directory / "casefile.json").read_text(encoding="utf-8"))

    def section(title, value):
        escaped = html.escape(json.dumps(value, ensure_ascii=False, indent=2))
        return f"<details><summary>{html.escape(title)}</summary><pre>{escaped}</pre></details>"

    body = section(
        "设备与商品终态",
        {
            "incident": casefile["incident"],
            "devices": casefile["records"]["devices"],
            "batches": casefile["records"]["inventory_batches"],
        },
    )
    body += section("场景、平台关联、各轮输出与恢复", casefile["context"])
    for table, records in casefile["records"].items():
        body += section(table, [decode(row) for row in records])
    for index, row in enumerate(casefile["trace"]["rows"], 1):
        body += section(f"Trace {index}: {row['name']}", decode(row))
    body += section(
        "当前规则与 Skill 注册表",
        {"policy": casefile["current_policy"], "registry": casefile["current_skill_registry"]},
    )
    output.write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>店巡运行证据回放</title><style>body{font:16px/1.6 system-ui;"
        "max-width:1100px;margin:40px auto;padding:0 20px;background:#f3f6f8}"
        "details{background:white;border:1px solid #d7e1e6;padding:12px;margin:10px 0}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style>"
        "<h1>店巡运行证据回放</h1><p>查看封存记录，不执行任何业务动作。</p>"
        f"<p>{html.escape(result['claim_boundary'])}</p>" + body + "</html>",
        encoding="utf-8",
        newline="\n",
    )
    return result


def check_restored(directory, mcp, principal):
    """Compare a separately restored DB to its captured logical view. No restore or writes."""
    verify_runtime(directory)
    manifest = json.loads((Path(directory) / "manifest.json").read_text(encoding="utf-8"))
    if database_fingerprint(mcp.store) == manifest["source_database_fingerprint"]:
        raise ValueError("Restore comparison requires a separate database target")
    expected = json.loads((Path(directory) / "casefile.json").read_text(encoding="utf-8"))
    _compare_database(expected, mcp, principal)
    return {
        "passed": True,
        "incident_id": expected["incident"]["incident_id"],
        "database_restore_verified": True,
        "claim_boundary": "Scoped logical comparison only; "
        "no RPO/RTO or full-database recovery claim.",
    }


def _compare_database(expected, mcp, principal):
    with mcp.store.read_snapshot():
        actual = collect_casefile(
            mcp, principal, expected["incident"]["incident_id"], limit=100000, include_trace=False
        )
    if actual["truncated"]:
        raise ValueError("Restored database comparison is incomplete")
    for key in ("incident", "context", "records", "business_time"):
        # PostgreSQL JSONB rendering may differ in whitespace/key ordering after restore.
        if key == "records":

            def normalize(records):
                return {k: [decode(r) for r in v] for k, v in records.items()}

            equal = stable_hash(normalize(actual[key])) == stable_hash(normalize(expected[key]))
        else:
            equal = actual[key] == expected[key]
        if not equal:
            raise ValueError(f"Restored database differs: {key}")
