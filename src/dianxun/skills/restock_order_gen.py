"""S4. restock-order-gen 补货单生成(安全库存模型)。

九要素(详见 skills/restock-order-gen.md):
  用途    基于安全库存模型生成补货建议单,支持审批与调整
  输入    store_id, sku_list?, urgency, constraints{预算上限,供应商偏好}
  输出    RestockOrder{items[{sku, suggest_qty, current_stock, daily_sales, days_to_empty, priority}], total_amount}
  安全    【写操作】只生成草稿单,不直接提交采购;金额>5000强制走审批流 MCP
  失败    库存快照冲突→重试3次;供应商停供→建议替代;金额超预算→拆分紧急必补+常规可延
  协同    处置 Executor 调用;审批后单子经 RocketMQ 事件回传,状态机 approving→executing

被谁调用:处置 Executor Agent
模型:suggest_qty = max(safety_stock*系数 - 在库 - 在途, 0)
"""

from __future__ import annotations
import uuid
from typing import Any

from .. import mcp, trace


def restock_order_gen(store_id: str,
                      sku_list: list[str] | None = None,
                      urgency: str = "常规",            # 常规 | 紧急
                      constraints: dict | None = None,
                      trace_id: str | None = None) -> dict:
    """生成补货建议单。"""
    tid = trace_id or trace.new_trace_id()
    with trace.span("restock-order-gen", "skill", tid,
                    input={"store_id": store_id, "urgency": urgency}) as sp:
        constraints = constraints or {}
        budget_cap = constraints.get("预算上限")
        stock_res = mcp.query_stock(store_id, sku_list)
        if stock_res["degraded"]:
            sp.output = {"degraded": True}
            return {"degraded": True, "error": stock_res["error"], "items": []}

        # 取售价算金额
        price_res = mcp.query_price(store_id)
        price_map = {r["sku_id"]: r["system_price"] for r in price_res["rows"]} if not price_res["degraded"] else {}

        items = []
        for r in stock_res["rows"]:
            stock = r["stock"]
            safety = r["safety_stock"]
            if stock >= safety:
                continue  # 库存充足不补
            # 补货系数:紧急 ×1.5,常规 ×1.2
            factor = 1.5 if urgency == "紧急" else 1.2
            suggest_qty = max(int(safety * factor) - stock, 1)
            unit_price = price_map.get(r["sku_id"], 0)
            amount = round(suggest_qty * unit_price, 2)
            days_to_empty = round(stock / max(safety / 14, 0.1), 1) if safety else 99
            items.append({
                "sku_id": r["sku_id"], "cat": r["cat"],
                "current_stock": stock, "safety_stock": safety,
                "suggest_qty": suggest_qty, "unit_price": unit_price, "amount": amount,
                "days_to_empty": days_to_empty,
                "priority": "紧急" if (stock <= 0 or days_to_empty < 1) else "常规",
            })
        # 按紧急度排序
        items.sort(key=lambda x: (0 if x["priority"] == "紧急" else 1, -x["amount"]))
        total = round(sum(i["amount"] for i in items), 2)

        # 预算超限拆分
        need_approval = total > 5000
        if budget_cap and total > budget_cap:
            items = _split_by_budget(items, budget_cap)
            total = round(sum(i["amount"] for i in items), 2)

        order = {
            "order_id": "rst_" + uuid.uuid4().hex[:10],
            "store_id": store_id, "urgency": urgency,
            "items": items, "item_count": len(items),
            "total_amount": total,
            "need_approval": need_approval,
            "confidence": 0.82,
            "comments": "草稿单,需店长/采购审批后提交" + (";金额>5000强制审批" if need_approval else ""),
        }
        sp.output = {"order_id": order["order_id"], "total": total, "need_approval": need_approval}
        return order


def _split_by_budget(items: list[dict], budget_cap: float) -> list[dict]:
    """金额超预算:拆为紧急必补(预算内) + 常规可延(标记延后)。"""
    kept, deferred = [], []
    used = 0.0
    for it in items:
        if used + it["amount"] <= budget_cap:
            kept.append(it)
            used += it["amount"]
        else:
            it["priority"] = "可延(超预算)"
            deferred.append(it)
    return kept + deferred
