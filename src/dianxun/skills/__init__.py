"""复赛 Skill 实现入口。

P0 冷柜主线使用 anomaly-detect、coldchain-risk-assess、
rootcause-drilldown、work-order-dispatch、outcome-verify 和 review-report。
cross-store-benchmark 为 P1；补货和价签 Skill 为 P2 补充场景。

每个 Skill 是可复用的任务能力抽象层（非一次性 Agent 行为）。
实现为纯函数，输入输出以 ``skills/<name>/`` 契约为准。
所有 Skill:
- 含失败处理/降级(partial/degraded 标记)
- 含安全边界(只读 Skill 不写;写操作 Skill 强制审批)
- 通过 trace.span 自动埋点
- 不直接调外部系统,只通过 dianxun.mcp 工具层
"""

from .anomaly_detect import anomaly_detect, detect_coldchain_event
from .coldchain_risk_assess import coldchain_risk_assess
from .cross_store_benchmark import cross_store_benchmark
from .outcome_verify import outcome_verify
from .price_tag_check import price_tag_check
from .restock_order_gen import restock_order_gen
from .review_report import review_incident, review_report
from .rootcause_drilldown import diagnose_coldchain_hypotheses, rootcause_drilldown
from .work_order_dispatch import dispatch_stateful_workorder, work_order_dispatch

__all__ = [
    "anomaly_detect",
    "detect_coldchain_event",
    "coldchain_risk_assess",
    "cross_store_benchmark",
    "rootcause_drilldown",
    "diagnose_coldchain_hypotheses",
    "restock_order_gen",
    "price_tag_check",
    "work_order_dispatch",
    "dispatch_stateful_workorder",
    "outcome_verify",
    "review_report",
    "review_incident",
]
