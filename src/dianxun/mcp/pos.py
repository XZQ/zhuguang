"""mcp-pos:销售/收银数据工具。

契约:query_sales(window, store_ids?, sku_ids?) / query_realtime_sales(store_id)
权限:只读;门店域数据 + 总部聚合视图
数据源:data/pos_sales.csv(ts, store_id, sku_id, cat, qty, amount)
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any

from ._csv_store import load_csv, ToolResult

_SALES: list[dict] | None = None


def _ensure() -> list[dict]:
    global _SALES
    if _SALES is None:
        _SALES = load_csv("pos_sales.csv")
    return _SALES


def query_sales(window: dict[str, str] | None = None,
                store_ids: list[str] | None = None,
                sku_ids: list[str] | None = None) -> ToolResult:
    """查询销售流水。window={start,end} ISO8601,可空=近 24h。"""
    rows = _ensure()
    if not rows:
        return ToolResult(degraded=True, error="pos 数据源不可用")
    # 默认近 24h
    end = datetime.now()
    start = end - timedelta(hours=24)
    if window and window.get("start"):
        try:
            start = datetime.fromisoformat(window["start"])
        except ValueError:
            pass
    if window and window.get("end"):
        try:
            end = datetime.fromisoformat(window["end"])
        except ValueError:
            pass

    out: list[dict] = []
    for r in rows:
        try:
            ts = datetime.strptime(r["ts"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError):
            continue
        if not (start <= ts <= end):
            continue
        if store_ids and r.get("store_id") not in store_ids:
            continue
        if sku_ids and r.get("sku_id") not in sku_ids:
            continue
        # 数值转换
        out.append({**r, "qty": int(r["qty"]), "amount": float(r["amount"])})
    return ToolResult(out)


def query_realtime_sales(store_id: str) -> ToolResult:
    """查某店近 1 小时实时销售(用于异常实时核验)。"""
    end = datetime.now()
    start = end - timedelta(hours=1)
    return query_sales({"start": start.isoformat(), "end": end.isoformat()}, store_ids=[store_id])
