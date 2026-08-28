# Skill 目录索引

复赛唯一事实口径为 9 个目标 Skill：P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个。只有根目录下 6 个同名目录是 P0 工程契约源；规划说明和旧入口分区存放，避免与可装载 Skill 混淆。

> 汇总材料见 [../docs/competition/03-Skill九要素卡.md](../docs/competition/03-Skill九要素卡.md)

| Skill | 优先级 | Agent | 契约入口 |
|---|---|---|---|
| `anomaly-detect` | P0 | Sentry | [SKILL.md](anomaly-detect/SKILL.md) |
| `coldchain-risk-assess` | P0 | Diagnoser | [SKILL.md](coldchain-risk-assess/SKILL.md) |
| `rootcause-drilldown` | P0 | Diagnoser | [SKILL.md](rootcause-drilldown/SKILL.md) |
| `work-order-dispatch` | P0 | Executor | [SKILL.md](work-order-dispatch/SKILL.md) |
| `outcome-verify` | P0 | Auditor | [SKILL.md](outcome-verify/SKILL.md) |
| `review-report` | P0 | Auditor | [SKILL.md](review-report/SKILL.md) |
| `cross-store-benchmark` | P1 | Diagnoser | [规划说明](planned/cross-store-benchmark.md) |
| `restock-order-gen` | P2 | Executor | [补充场景说明](planned/restock-order-gen.md) |
| `price-tag-check` | P2 | Sentry / Executor | [补充场景说明](planned/price-tag-check.md) |

## 目录边界

| 路径 | 定位 | 维护规则 |
|---|---|---|
| `skills/<p0-name>/` | 6 个 P0 Skill 的唯一契约源 | `SKILL.md`、manifest、Schema 和样例必须一起维护 |
| [`planned/`](planned/) | P1/P2 设计与补充入口说明 | 不代表已形成可导入的 AgentTeams Skill 包 |
| [`legacy/`](legacy/) | 旧 P0 单文件入口的兼容索引 | 只指向 canonical 目录，不复制契约正文 |
| `packages/dianxun-worker/skills/` | AgentTeams Worker 打包镜像 | 不独立设计；必须与 6 个 canonical 目录逐字一致 |

修改 P0 契约后必须同步 Worker 镜像，并运行 `uv run python scripts/build_worker_package.py` 与 `tests.test_agentteams_artifacts`；构建器会拒绝内容分叉。
