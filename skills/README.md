# Skill 目录索引

复赛唯一事实口径为 9 个目标 Skill：P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个。P0 Skill 使用独立目录，包含 `SKILL.md`、manifest、输入/输出 Schema 和成功/失败样例；根目录旧 `.md` 仅保留历史兼容说明。

> 汇总单文件见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

| Skill | 优先级 | Agent | 契约入口 |
|---|---|---|---|
| `anomaly-detect` | P0 | Sentry | [SKILL.md](anomaly-detect/SKILL.md) |
| `coldchain-risk-assess` | P0 | Diagnoser | [SKILL.md](coldchain-risk-assess/SKILL.md) |
| `rootcause-drilldown` | P0 | Diagnoser | [SKILL.md](rootcause-drilldown/SKILL.md) |
| `work-order-dispatch` | P0 | Executor | [SKILL.md](work-order-dispatch/SKILL.md) |
| `outcome-verify` | P0 | Auditor | [SKILL.md](outcome-verify/SKILL.md) |
| `review-report` | P0 | Auditor | [SKILL.md](review-report/SKILL.md) |
| `cross-store-benchmark` | P1 | Diagnoser | [历史说明](cross-store-benchmark.md) |
| `restock-order-gen` | P2 | Executor | [历史说明](restock-order-gen.md) |
| `price-tag-check` | P2 | Sentry / Executor | [历史说明](price-tag-check.md) |
