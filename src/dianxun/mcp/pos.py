"""mcp-pos:销售/收银数据工具。

契约:query_sales(window, store_ids?, sku_ids?) / query_realtime_sales(store_id)
权限:只读;门店域数据 + 总部聚合视图
数据源:data/pos_sales.csv(ts, store_id, sku_id, cat, qty, amount)
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ._csv_store import ToolResult, load_csv

_SALES: list[dict] | None = None


def _ensure() -> list[dict]:
    global _SALES
    if _SALES is None:
        _SALES = load_csv("pos_sales.csv")
    return _SALES


def query_sales(
    window: dict[str, str] | None = None,
    store_ids: list[str] | None = None,
    sku_ids: list[str] | None = None,
) -> ToolResult:
    """查询销售流水。window={start,end} ISO8601,可空=近 24h。"""
    rows = _ensure()
    if not rows:
        return ToolResult(degraded=True, error="pos 数据源不可用")
    parsed_rows: list[tuple[datetime, dict]] = []
    for row in rows:
        try:
            parsed_rows.append((datetime.strptime(row["ts"], "%Y-%m-%d %H:%M"), row))
        except (KeyError, ValueError):
            continue
    if not parsed_rows:
        return ToolResult(degraded=True, error="pos 数据源没有有效时间戳")
    # CSV 是确定性历史快照，未指定窗口时以数据集最后一条记录为锚点。
    end = max(timestamp for timestamp, _ in parsed_rows)
    start = end - timedelta(hours=24)
    if window and window.get("start"):
        try:
            start = datetime.fromisoformat(window["start"])
        except ValueError:
            return ToolResult(degraded=True, error="window.start 不是有效 ISO-8601 时间")
    if window and window.get("end"):
        try:
            end = datetime.fromisoformat(window["end"])
        except ValueError:
            return ToolResult(degraded=True, error="window.end 不是有效 ISO-8601 时间")
    if start > end:
        return ToolResult(degraded=True, error="window.start 不能晚于 window.end")

    out: list[dict] = []
    for ts, r in parsed_rows:
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
    """查历史快照锚点前 1 小时销售(用于确定性 Demo 核验)。"""
    result = query_sales(store_ids=[store_id])
    if result["degraded"] or not result["rows"]:
        return result
    end = max(datetime.strptime(row["ts"], "%Y-%m-%d %H:%M") for row in result["rows"])
    start = end - timedelta(hours=1)
    rows = [
        row
        for row in result["rows"]
        if start <= datetime.strptime(row["ts"], "%Y-%m-%d %H:%M") <= end
    ]
    return ToolResult(rows)
