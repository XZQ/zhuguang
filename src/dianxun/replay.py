"""Seal and inspect one finished synthetic run without rerunning its actions."""

from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

FILES = frozenset(
    {
        "state.sqlite",
        "trace.sqlite",
        "result.json",
        "scenario.json",
        "policy.json",
        "trace.jsonl",
        "audit.jsonl",
    }
)


def read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def snapshot(source: Path, destination: Path) -> None:
    # SQLite backup includes committed WAL pages; copying only the main file does not.
    with closing(read_only(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)


def rows(path: Path, table: str) -> list[dict[str, Any]]:
    queries = {
        "spans": "SELECT * FROM spans ORDER BY start_ms, span_id",
        "audit_log": "SELECT * FROM audit_log ORDER BY created_at, audit_id",
        "incidents": "SELECT * FROM incidents ORDER BY incident_id",
    }
    with closing(read_only(path)) as connection:
        return [dict(row) for row in connection.execute(queries[table])]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def seal_run(
    directory: Path,
    *,
    state: Path,
    trace: Path,
    result: dict,
    scenario: Path,
    policy: Path,
    provenance: dict,
) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    snapshot(state, directory / "state.sqlite")
    snapshot(trace, directory / "trace.sqlite")
    write_json(directory / "result.json", result)
    for source, target in [(scenario, "scenario.json"), (policy, "policy.json")]:
        (directory / target).write_bytes(source.read_bytes())
    for database, table, name in [
        ("state.sqlite", "audit_log", "audit.jsonl"),
        ("trace.sqlite", "spans", "trace.jsonl"),
    ]:
        records = rows(directory / database, table)
        (directory / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
            encoding="utf-8",
            newline="\n",
        )
    manifest = {
        "schema_version": 1,
        "source_kind": "synthetic_local_run",
        "incident_id": result["incident"]["incident_id"],
        "trace_id": result["incident"]["trace_id"],
        "scenario_id": json.loads(scenario.read_text(encoding="utf-8"))["scenario_id"],
        "provenance": provenance,
        "claim_boundary": (
            "Local synthetic SQLite run; no AgentTeams, PolarDB, OSS or real-store evidence. "
            "Hashes detect accidental changes, not source authenticity."
        ),
        "files": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in sorted(FILES)
        },
    }
    write_json(directory / "manifest.json", manifest)
    return verify_run(directory)


def verify_run(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or set(manifest.get("files", {})) != FILES:
        raise ValueError("Unsupported or incomplete replay manifest")
    if manifest.get("source_kind") != "synthetic_local_run":
        raise ValueError("This replay format only verifies captured synthetic local runs")
    for name, expected in manifest["files"].items():
        path = directory / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Replay integrity mismatch: {name}")
    for name in ("state.sqlite", "trace.sqlite"):
        with closing(read_only(directory / name)) as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError(f"Invalid SQLite snapshot: {name}")
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    incidents = rows(directory / "state.sqlite", "incidents")
    incident = next(row for row in incidents if row["incident_id"] == manifest["incident_id"])
    stored = json.loads(incident["case_json"])
    for field in (
        "incident_id",
        "trace_id",
        "phase",
        "incident_status",
        "work_status",
        "batch_dispositions",
    ):
        if stored[field] != result["incident"][field]:
            raise ValueError(f"Result and database disagree: {field}")
    if stored["trace_id"] != manifest["trace_id"]:
        raise ValueError("Trace correlation mismatch")
    for database, table, name in [
        ("state.sqlite", "audit_log", "audit.jsonl"),
        ("trace.sqlite", "spans", "trace.jsonl"),
    ]:
        exported = [
            json.loads(line) for line in (directory / name).read_text(encoding="utf-8").splitlines()
        ]
        if not exported or exported != rows(directory / database, table):
            raise ValueError(f"Incomplete or inconsistent export: {name}")
    return {
        "passed": True,
        "incident_id": manifest["incident_id"],
        "status": stored["incident_status"],
        "claim_boundary": manifest["claim_boundary"],
    }


def render_run(directory: Path, output: Path) -> dict:
    result = verify_run(directory)
    if output.resolve() in {(directory / name).resolve() for name in FILES | {"manifest.json"}}:
        raise ValueError("Replay output cannot overwrite sealed evidence")

    def escaped(value):
        return html.escape(json.dumps(value, ensure_ascii=False, indent=2))

    sections = []
    for title, name in [
        ("最终结果与设备／商品状态", "result.json"),
        ("模拟环境事件（虚拟时间）", "scenario.json"),
        ("规则版本", "policy.json"),
    ]:
        data = json.loads((directory / name).read_text(encoding="utf-8"))
        sections.append(f"<details><summary>{title}</summary><pre>{escaped(data)}</pre></details>")
    for title, name, label in [
        ("业务审计（虚拟业务时间）", "audit.jsonl", "tool_name"),
        ("逐条 Trace（真实执行时间戳）", "trace.jsonl", "name"),
    ]:
        sections.append(f"<h2>{title}</h2>")
        for index, line in enumerate(
            (directory / name).read_text(encoding="utf-8").splitlines(), 1
        ):
            data = json.loads(line)
            sections.append(
                f"<details><summary>{index}. {html.escape(str(data[label]))}</summary>"
                f"<pre>{escaped(data)}</pre></details>"
            )
    document = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>店巡事件离线回放</title>
<style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 20px;
background:#f6f8fa;color:#17212b}details{background:white;padding:12px 18px;margin:10px 0;
border:1px solid #dce2e8;border-radius:8px}summary{cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}h1{font-size:28px}</style>
<h1>店巡事件离线回放</h1><p>本地合成运行 · 查看已封存事实 · 不执行任何业务动作</p>"""
    document += (
        f"<p>事件：{html.escape(result['incident_id'])} · 终态：{html.escape(result['status'])}</p>"
    )
    document += "".join(sections) + "</html>"
    output.write_text(document, encoding="utf-8", newline="\n")
    return result
