# 逐光｜非 P0 Skill 说明

这里保存未进入冷柜 P0 Worker 的 P1/P2 Skill 设计和补充场景说明。目录名表示交付层级，不等于对应 Python 代码完全不存在。

| Skill | 当前能力 | 进入 P0 Worker |
|---|---|---:|
| [`cross-store-benchmark`](cross-store-benchmark.md) | 保留 Python 实现，作为 P1 诊断增强 | 否 |
| [`restock-order-gen`](restock-order-gen.md) | 保留缺货补充场景入口 | 否 |
| [`price-tag-check`](price-tag-check.md) | 保留价签补充场景入口 | 否 |

只有补齐独立目录、AgentTeams `SKILL.md`、manifest、输入/输出 Schema、成功/失败样例和相应门禁后，才能升级为可装载 Skill；文档状态必须同时更新。
