"""mcp-price:系统价格/促销工具。

契约:query_price(store_id, sku_ids?) / apply_price_change(..., idempotency_key)(审批后)
     / revert_price_change(change_id)
权限:query 只读;apply 为写操作,需 approval_ticket + 金额阈值检查
幂等:apply 必带 idempotency_key,重复调用返回首次结果
数据源:data/price.csv(store_id, sku_id, system_price, tag_price, pos_price)
"""

from __future__ import annotations

import time

from ._csv_store import ToolResult, load_csv

_PRICE: list[dict] | None = None
_APPLY_CACHE: dict[str, dict] = {}  # idempotency_key -> 结果
_CHANGE_LOG: list[dict] = []


def _ensure() -> list[dict]:
    global _PRICE
    if _PRICE is None:
        _PRICE = load_csv("price.csv")
    return _PRICE


def query_price(store_id: str, sku_ids: list[str] | None = None) -> ToolResult:
    """查询三方价格(系统价/货架价签价/收银价)。"""
    rows = _ensure()
    if not rows:
        return ToolResult(degraded=True, error="price 数据源不可用")
    out: list[dict] = []
    for r in rows:
        if r.get("store_id") != store_id:
            continue
        if sku_ids and r.get("sku_id") not in sku_ids:
            continue
        out.append(
            {
                **r,
                "system_price": float(r["system_price"]),
                "tag_price": float(r["tag_price"]),
                "pos_price": float(r["pos_price"]),
            }
        )
    return ToolResult(out)


def apply_price_change(
    store_id: str, items: list[dict], idempotency_key: str, approval_ticket: str | None = None
) -> ToolResult:
    """批量改价(审批后调用)。items=[{sku_id, new_price}]。

    安全边界:批量 > 20 SKU 强制人工(需 approval_ticket);无 ticket 拒绝。
    幂等:同 idempotency_key 返回首次结果。
    """
    if idempotency_key in _APPLY_CACHE:
        return ToolResult(_APPLY_CACHE[idempotency_key])
    batch_size = len(items)
    if batch_size > 20 and not approval_ticket:
        return ToolResult(
            data={"applied_count": 0, "failed": items, "reason": "批量>20需审批 ticket"},
            degraded=True,
            error="missing_approval",
        )
    change_id = "pr_" + str(int(time.time() * 1000))[-10:]
    applied = [
        {"sku_id": it["sku_id"], "old_price": None, "new_price": it["new_price"]} for it in items
    ]
    result = {
        "change_id": change_id,
        "applied_count": len(applied),
        "applied": applied,
        "approval_ticket": approval_ticket,
    }
    _APPLY_CACHE[idempotency_key] = result
    _CHANGE_LOG.append(
        {
            "change_id": change_id,
            "store_id": store_id,
            "items": applied,
            "approval_ticket": approval_ticket,
            "ts": time.time(),
        }
    )
    return ToolResult(result)


def revert_price_change(change_id: str) -> ToolResult:
    """回滚一次改价(快照回退)。"""
    entry = next((c for c in _CHANGE_LOG if c["change_id"] == change_id), None)
    if not entry:
        return ToolResult(data=None, degraded=True, error=f"未找到改价记录 {change_id}")
    return ToolResult({"reverted": change_id, "items_count": len(entry["items"])})
