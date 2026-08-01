"""知识条目存储(SQLite)。

满足赛题 2.4 知识库 RAG:检索历史同型异常处置经验,防止幻觉(返回原文引用)。
生产替换路径:SQLite → PolarDB pgvector(向量检索),接口不变。
"""

from __future__ import annotations
import json
import re
import sqlite3
import time
from pathlib import Path

_DB = Path(__file__).resolve().parents[3] / "data" / "knowledge.db"


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.execute("""CREATE TABLE IF NOT EXISTS knowledge(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, body TEXT, tags_json TEXT, confidence REAL,
        trace_id TEXT, created_at REAL,
        UNIQUE(title))""")
    c.commit()
    return c


def init() -> None:
    """建表(幂等)。"""
    _conn().close()


def add(title: str, body: str, tags: list[str], confidence: float,
        trace_id: str = "") -> int | None:
    """新增知识条目。去重(按 title);敏感信息脱敏由调用方处理。"""
    c = _conn()
    try:
        cur = c.execute(
            "INSERT OR IGNORE INTO knowledge(title,body,tags_json,confidence,trace_id,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (title, body, json.dumps(tags, ensure_ascii=False), confidence, trace_id, time.time()),
        )
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def search(query: str, topk: int = 5) -> list[dict]:
    """检索知识条目。

    demo:关键词/标签匹配(标题+正文+标签含查询词)。
    生产:换 pgvector 余弦相似度,返回 {entry, score, source_span}(防幻觉)。
    """
    c = _conn()
    try:
        rows = c.execute(
            "SELECT title,body,tags_json,confidence,trace_id FROM knowledge ORDER BY confidence DESC"
        ).fetchall()
    finally:
        c.close()
    q = query.lower()
    terms = re.split(r"\s+", q)
    scored = []
    for title, body, tags_json, conf, tid in rows:
        hay = (title + " " + body + " " + tags_json).lower()
        score = sum(1 for t in terms if t and t in hay) * conf
        if score > 0:
            scored.append({"title": title, "body": body,
                           "tags": json.loads(tags_json), "confidence": conf,
                           "trace_id": tid, "score": round(score, 3),
                           "source": "knowledge_db"})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:topk]


def all_entries() -> list[dict]:
    c = _conn()
    try:
        rows = c.execute(
            "SELECT title,body,tags_json,confidence,trace_id,created_at FROM knowledge ORDER BY created_at DESC"
        ).fetchall()
    finally:
        c.close()
    return [{"title": t, "body": b, "tags": json.loads(tj), "confidence": cf,
             "trace_id": tid, "created_at": ca}
            for t, b, tj, cf, tid, ca in rows]
