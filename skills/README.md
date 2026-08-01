# Skill 目录索引

店巡 Agent 的 7 个核心 Skill,每个含完整 9 要素(名称/用途/输入输出/调用条件/依赖工具/失败处理/安全边界/复用价值/协同关系)。

> 汇总单文件见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

| 序号 | Skill | 文件 | 一句话用途 |
|---|---|---|---|
| S1 | `anomaly-detect` | [anomaly-detect.md](anomaly-detect.md) | 多源异常检测与降噪定级 · 被巡检 Sentry调用 |
| S2 | `cross-store-benchmark` | [cross-store-benchmark.md](cross-store-benchmark.md) | 跨店横向对标找基准 · 被诊断 Diagnoser调用 |
| S3 | `rootcause-drilldown` | [rootcause-drilldown.md](rootcause-drilldown.md) | 维度下钻定位根因 · 被诊断 Diagnoser调用 |
| S4 | `restock-order-gen` | [restock-order-gen.md](restock-order-gen.md) | 补货单生成(安全库存) · 被处置 Executor调用 |
| S5 | `price-tag-check` | [price-tag-check.md](price-tag-check.md) | 价签与促销合规校验 · 被巡检/处置调用 |
| S6 | `work-order-dispatch` | [work-order-dispatch.md](work-order-dispatch.md) | 工单派发与跟踪 · 被处置 Executor调用 |
| S7 | `review-report` | [review-report.md](review-report.md) | 复盘报告与知识沉淀 · 被稽核 Auditor调用 |

**开源**:3 个底座 Skill(`anomaly-detect` / `cross-store-benchmark` / `review-report`)MIT 开源,便利店行业包按协议分发。
