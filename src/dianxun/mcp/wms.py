"""mcp-wms:库存/临期数据工具。

契约:query_stock(store_id, sku_ids?) / query_expiry(store_id, within_days)
权限:只读;SKU 级
数据源:data/inventory.csv(store_id, sku_id, cat, stock, safety_stock, days_to_expire)
"""

from __future__ import annotations

from ._csv_store import ToolResult, load_csv

_STOCK: list[dict] | None = None


def _ensure() -> list[dict]:
    global _STOCK
    if _STOCK is None:
        _STOCK = load_csv("inventory.csv")
    return _STOCK


def query_stock(store_id: str, sku_ids: list[str] | None = None) -> ToolResult:
    """查询门店库存。返回 {sku_id, cat, stock, safety_stock, days_to_expire}。"""
    rows = _ensure()
    if not rows:
        return ToolResult(degraded=True, error="wms 数据源不可用")
    out: list[dict] = []
    for r in rows:
        if r.get("store_id") != store_id:
            continue
        if sku_ids and r.get("sku_id") not in sku_ids:
            continue
        out.append(
            {
                **r,
                "stock": int(r["stock"]),
                "safety_stock": int(r["safety_stock"]),
                "days_to_expire": int(r["days_to_expire"]),
            }
        )
    return ToolResult(out)


def query_expiry(store_id: str, within_days: int = 3) -> ToolResult:
    """查询临期商品(days_to_expire <= within_days)。"""
    res = query_stock(store_id)
    if res["degraded"]:
        return res
    out = [r for r in res["rows"] if r["days_to_expire"] <= within_days]
    return ToolResult(out)
