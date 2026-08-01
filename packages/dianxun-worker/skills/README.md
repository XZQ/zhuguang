# 店巡 Skill 目录(QwenPaw 约定)

本目录是 AgentTeams QwenPaw Worker 加载自定义 Skill 的入口。
AgentTeams Controller 会将含 `skills/` 目录的 package zip 推送到 Worker 的 MinIO 空间。

## Skill 清单(7 个,九要素齐全)

实际实现位于 `src/dianxun/skills/`,本目录为 QwenPaw 提供声明与入口包装。

| Skill | 实现文件 | 用途 | 调用方 |
|---|---|---|---|
| `anomaly-detect` | `src/dianxun/skills/anomaly_detect.py` | 多源异常检测与降噪定级 | Sentry |
| `cross-store-benchmark` | `src/dianxun/skills/cross_store_benchmark.py` | 跨店横向对标 | Diagnoser |
| `rootcause-drilldown` | `src/dianxun/skills/rootcause_drilldown.py` | 维度下钻根因 | Diagnoser |
| `restock-order-gen` | `src/dianxun/skills/restock_order_gen.py` | 补货单生成(安全库存) | Executor |
| `price-tag-check` | `src/dianxun/skills/price_tag_check.py` | 价签合规校验 | Sentry/Executor |
| `work-order-dispatch` | `src/dianxun/skills/work_order_dispatch.py` | 工单派发 | Executor |
| `review-report` | `src/dianxun/skills/review_report.py` | 复盘报告+知识沉淀 | Auditor |

## 调用约定

每个 Skill 导出一个同名(连字符转下划线)的主函数,签名见各文件 docstring 与 `skills/*.md` 九要素卡。
所有 Skill:
- 输入输出严格对齐九要素卡的 Schema
- 含失败处理/降级(partial/degraded)
- 含安全边界(只读/写操作审批)
- 通过 `dianxun.mcp` 工具层访问数据,不直接读外部系统
- 经 `dianxun.trace.span` 自动埋点

## 复用与开源

3 个底座 Skill(anomaly-detect / cross-store-benchmark / review-report)MIT 开源,跨便利店/超市/餐饮/药房通用。
便利店行业包(restock/price-tag/work-order)按协议分发。
