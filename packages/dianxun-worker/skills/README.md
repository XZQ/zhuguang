# 逐光｜Worker 包 Skill 清单

本目录镜像仓库根目录 [`skills/`](../../../skills/) 中的 6 个 P0 Skill，供 AgentTeams `v1.2.3` QwenPaw Worker 加载。

| Skill | Agent | 主要权限 |
|---|---|---|
| `anomaly-detect` | Sentry | 设备与批次查询 |
| `coldchain-risk-assess` | Diagnoser | 设备与批次查询 |
| `rootcause-drilldown` | Diagnoser | 设备上下文查询；P1 启用时可检索已审核知识 |
| `work-order-dispatch` | Executor | Policy、审批与工单写入 |
| `outcome-verify` | Auditor | 独立重查与验证证据记录 |
| `review-report` | Auditor | 事故复盘与 pending 知识候选；无审核发布权限 |

每个目录包含 AgentTeams 可识别的 `SKILL.md` frontmatter、实际 MCP 调用步骤，以及 manifest、输入/输出 Schema 和成功/失败样例。代码实现仍在 `src/dianxun/skills/`；领域阶段由 `IncidentService` 聚合，工具状态与写操作统一进入远端 `dianxun-mcp` 的 StateStore/Policy 事实层。

不要直接编辑这里的 Skill 副本。修改根目录的规范后同步，并运行：

```powershell
python scripts/build_worker_package.py
uv run --group dev python -m unittest -v tests.test_agentteams_artifacts
```

构建脚本会在副本与规范不一致时失败。
