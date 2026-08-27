"""改造前基线的 7 个 Skill 实现。

复赛唯一事实清单为 9 个目标 Skill，其中 P0 核心 6 个；本模块将在 M2
补齐 coldchain-risk-assess 与 outcome-verify，并把补充场景能力分层。
在改造完成前，这 7 个导出只代表既有代码，不代表 P0 已验收。

每个 Skill 是可复用的任务能力抽象层（非一次性 Agent 行为）。
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
