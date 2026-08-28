# 逐光｜dianxun-worker 包源

本目录描述 AgentTeams `v1.2.3` QwenPaw Worker 的导入布局，不是第二套业务实现。

| 路径 | 是否进入 ZIP | 作用 |
|---|---:|---|
| `manifest.json` | 是 | Worker runtime、model 与包元数据 |
| `config/` | 是 | 运行时身份、五阶段规则与委派边界 |
| `skills/` | 是 | 根 `skills/` 下 6 个 P0 canonical Skill 的打包镜像 |
| `AGENTS.md` | 否 | 仓库维护约束 |
| `README.md` | 否 | 本说明 |

只能通过仓库根目录的构建器生成制品：

```powershell
uv run python scripts/build_worker_package.py
uv run --group dev python -m unittest -v tests.test_agentteams_artifacts
```

构建器会验证包内 Skill 与 canonical 目录逐字一致，并确定性生成 `dist/dianxun-worker.zip` 及 SHA-256。不要直接修改 `dist/` 或在本目录实现 `IncidentService`、MCP、Policy 和状态存储。
