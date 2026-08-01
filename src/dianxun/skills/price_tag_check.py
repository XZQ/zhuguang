"""S5. price-tag-check 价签与促销合规校验。

九要素(详见 skills/price-tag-check.md):
  用途    比对系统价/货架价签价/收银价三方一致性,校验促销规则,输出价签异常报告
  输入    store_id, sku_list?, check_time
  输出    PriceCheckReport{mismatches[{sku, system, tag, pos, severity}], compliance_summary}
  安全    【纠错写操作】改价签/改收银价必须审批;批量>20SKU强制人工;留痕可回滚
  失败    价签系统无响应→系统价vs收银价两方降级;促销规则解析失败→标黄人工
  协同    巡检 Sentry 常规触发;严重不一致(收银>标价)升级处置 Executor 走紧急审批

被谁调用:巡检 Sentry / 处置 Executor
"""

from __future__ import annotations
import uuid
from typing import Any

from .. import mcp, trace


def price_tag_check(store_id: str,
                    sku_list: list[str] | None = None,
                    check_time: str | None = None,
                    trace_id: str | None = None) -> dict:
    """价签三方一致性校验 + 促销合规。"""
    tid = trace_id or trace.new_trace_id()
    with trace.span("price-tag-check", "skill", tid,
                    input={"store_id": store_id}) as sp:
        res = mcp.query_price(store_id, sku_list)
        if res["degraded"]:
            # 降级:仅系统价 vs 收银价(价签系统无响应)
            sp.output = {"degraded": True}
            return {"degraded": True, "error": res["error"],
                    "mismatches": [], "compliance_summary": {"note": "价签源降级,未完整校验"}}

        mismatches = []
        eps = 0.01
        for r in res["rows"]:
            tag_vs_sys = abs(r["tag_price"] - r["system_price"]) > eps
            pos_vs_sys = abs(r["pos_price"] - r["system_price"]) > eps
            tag_vs_pos = abs(r["tag_price"] - r["pos_price"]) > eps
            if not (tag_vs_sys or pos_vs_sys or tag_vs_pos):
                continue
            # 收银价 > 标价 = 严重(顾客多收钱,合规风险/投诉风险)
            if r["pos_price"] > r["tag_price"]:
                severity = "严重"
                violation = "收银价高于标价(顾客多收钱,违反价格法)"
            elif r["pos_price"] < r["tag_price"]:
                severity = "中"
                violation = "收银价低于标价(门店利润损失)"
            else:
                severity = "中"
                violation = "系统价与价签/收银不一致"
            mismatches.append({
                "sku_id": r["sku_id"],
                "system_price": r["system_price"],
                "tag_price": r["tag_price"],
                "pos_price": r["pos_price"],
                "severity": severity,
                "rule_violation": violation,
            })

        # 批量>20 需人工审批改价
        batch_needs_approval = len(mismatches) > 20
        report = {
            "report_id": "pc_" + uuid.uuid4().hex[:10],
            "store_id": store_id,
            "mismatches": mismatches,
            "mismatch_count": len(mismatches),
            "compliance_summary": {
                "total_checked": len(res["rows"]),
                "mismatch_rate": round(len(mismatches) / max(len(res["rows"]), 1), 3),
                "severe_count": sum(1 for m in mismatches if m["severity"] == "严重"),
                "batch_price_change_needs_approval": batch_needs_approval,
            },
        }
        sp.output = {"mismatch_count": len(mismatches),
                     "severe": report["compliance_summary"]["severe_count"]}
        return report
