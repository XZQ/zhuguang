"""Skill 能力抽象层:7 个核心 Skill。

每个 Skill 是赛题「必选项」,作为可复用的任务能力抽象层(非一次性 Agent 行为)。
实现为纯函数,输入输出严格对齐 03-Skill九要素卡.md 与 skills/*.md。
所有 Skill:
- 含失败处理/降级(partial/degraded 标记)
- 含安全边界(只读 Skill 不写;写操作 Skill 强制审批)
- 通过 trace.span 自动埋点
- 不直接调外部系统,只通过 dianxun.mcp 工具层
"""

from .anomaly_detect import anomaly_detect
from .cross_store_benchmark import cross_store_benchmark
from .rootcause_drilldown import rootcause_drilldown
from .restock_order_gen import restock_order_gen
from .price_tag_check import price_tag_check
from .work_order_dispatch import work_order_dispatch
from .review_report import review_report

__all__ = [
    "anomaly_detect", "cross_store_benchmark", "rootcause_drilldown",
    "restock_order_gen", "price_tag_check", "work_order_dispatch", "review_report",
]
