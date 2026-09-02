"""可观测埋点:全链路 Trace。

设计:
- 每次任务闭环生成一个 root trace_id,所有 Skill/MCP/Agent 调用挂同一个 trace_id
- Span 记录:调用方(agent/skill/mcp)、入参摘要、返回摘要、耗时、状态
- 后端存储:默认 SQLite(评审可跑),生产可替换 LoongSuite / AgentLoop / OTel Collector
- 语义规范:字段命名对齐 OpenTelemetry GenAI(gen_ai.* / gen_ai.tool.name)
- 不依赖第三方库,纯标准库实现,保证 demo 可离线运行

满足赛题 2.3:覆盖 Skill 调用 / MCP 工具 / LLM 推理(此处以规则引擎代理)全链路,
至少覆盖 Trace 一类数据,支持在线检索与离线评估。
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_DB_PATH = (
    Path(
        os.environ.get(
            "DIANXUN_TRACE_DB",
            Path(__file__).resolve().parent.parent.parent / "data" / "trace.db",
        )
    )
    .expanduser()
    .resolve()
)
_DB_PATH: ContextVar[Path] = ContextVar("dianxun_trace_db", default=_DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    db_path = _DB_PATH.get()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS spans(
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_id TEXT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,           -- skill | mcp | agent | llm
            input_json TEXT,
            output_json TEXT,
            status TEXT NOT NULL,         -- ok | error | degraded
            error TEXT,
            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,
            skill_name TEXT,
            skill_version TEXT,
            skill_digest TEXT,
            skill_channel TEXT,
            skill_registry_version TEXT
        )"""
    )
    existing_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(spans)").fetchall()}
    for column in (
        "skill_name",
        "skill_version",
        "skill_digest",
        "skill_channel",
        "skill_registry_version",
    ):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE spans ADD COLUMN {column} TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trace ON spans(trace_id)")
    conn.commit()
    return conn


@contextmanager
def use_database(path: str | Path) -> Iterator[None]:
    """Scope trace persistence to one runtime/evaluation database."""
    token = _DB_PATH.set(Path(path).resolve())
    try:
        yield
    finally:
        _DB_PATH.reset(token)


def clear_trace(trace_id: str) -> None:
    """Remove a previous run of the same deterministic scenario trace."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM spans WHERE trace_id = ?", (trace_id,))
        conn.commit()
    finally:
        conn.close()


def new_trace_id() -> str:
    """生成 root trace_id。一个端到端任务闭环对应一个 trace_id。"""
    return "tr_" + uuid.uuid4().hex[:16]


@dataclass
class Span:
    name: str
    kind: str  # skill | mcp | agent | llm
    trace_id: str
    parent_id: str | None = None
    span_id: str = field(default_factory=lambda: "sp_" + uuid.uuid4().hex[:12])
    input: Any = None
    output: Any = None
    status: str = "ok"
    error: str | None = None
    start_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    end_ms: int = 0
    skill_name: str | None = None
    skill_version: str | None = None
    skill_digest: str | None = None
    skill_channel: str | None = None
    skill_registry_version: str | None = None

    def finish(self, output: Any = None, status: str = "ok", error: str | None = None):
        self.end_ms = int(time.time() * 1000)
        if output is not None:
            self.output = output
        self.status = status
        self.error = error
        _persist(self)


def _persist(span: Span) -> None:
    """落库。生产环境替换为 OTel exporter / LoongSuite SDK。"""
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO spans(
                span_id, trace_id, parent_id, name, kind, input_json, output_json,
                status, error, start_ms, end_ms, skill_name, skill_version,
                skill_digest, skill_channel, skill_registry_version
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                span.span_id,
                span.trace_id,
                span.parent_id,
                span.name,
                span.kind,
                json.dumps(span.input, ensure_ascii=False, default=str)[:2000],
                json.dumps(span.output, ensure_ascii=False, default=str)[:2000],
                span.status,
                span.error,
                span.start_ms,
                span.end_ms,
                span.skill_name,
                span.skill_version,
                span.skill_digest,
                span.skill_channel,
                span.skill_registry_version,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def span(
    name: str, kind: str, trace_id: str, parent_id: str | None = None, input: Any = None
) -> Iterator[Span]:
    """便捷上下文管理器:自动记录起止时间与异常。

    用法:
        with trace.span("anomaly-detect", "skill", tid, input={"window":"24h"}) as s:
            result = do_something()
            s.output = result
    """
    skill_fields: dict[str, str] = {}
    if kind == "skill":
        from .skills.registry import registered_skill_trace_fields

        skill_fields = registered_skill_trace_fields(name, routing_key=trace_id) or {}
    sp = Span(
        name=name,
        kind=kind,
        trace_id=trace_id,
        parent_id=parent_id,
        input=input,
        **skill_fields,
    )
    try:
        yield sp
        if sp.status == "ok" and sp.end_ms == 0:
            sp.finish(output=sp.output, status="ok")
    except Exception as e:  # noqa: BLE001
        sp.finish(status="error", error=f"{type(e).__name__}: {e}")
        raise


def query_trace(trace_id: str) -> list[dict]:
    """检索某次任务闭环的全部 span(按时间排序),供复盘/审计。"""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT span_id, trace_id, parent_id, name, kind, input_json, output_json,
                      status, error, start_ms, end_ms, skill_name, skill_version,
                      skill_digest, skill_channel, skill_registry_version
               FROM spans WHERE trace_id=? ORDER BY start_ms""",
            (trace_id,),
        ).fetchall()
    finally:
        conn.close()
    cols = [
        "span_id",
        "trace_id",
        "parent_id",
        "name",
        "kind",
        "input_json",
        "output_json",
        "status",
        "error",
        "start_ms",
        "end_ms",
        "skill_name",
        "skill_version",
        "skill_digest",
        "skill_channel",
        "skill_registry_version",
    ]
    return [dict(zip(cols, r, strict=True)) for r in rows]


def trace_summary(trace_id: str) -> str:
    """生成一次任务闭环的可读 Trace 摘要(用于 demo 输出/报告)。"""
    spans = query_trace(trace_id)
    if not spans:
        return f"[trace {trace_id}] 无记录"
    total_ms = spans[-1]["end_ms"] - spans[0]["start_ms"]
    lines = [f"[trace {trace_id}] {len(spans)} spans · {total_ms}ms"]
    for s in spans:
        dur = s["end_ms"] - s["start_ms"]
        mark = "✓" if s["status"] == "ok" else "✗"
        identity = ""
        if s["skill_version"] and s["skill_digest"]:
            identity = f" @{s['skill_version']}#{s['skill_digest'][:12]}"
        lines.append(f"  {mark} {s['kind']:<6} {s['name']:<26} {dur:>5}ms{identity}")
        if s["status"] == "error":
            lines.append(f"        └─ {s['error']}")
    return "\n".join(lines)
