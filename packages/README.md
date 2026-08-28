# 逐光｜交付包与镜像上下文

`packages/` 只保存外部运行环境需要的打包描述，不是第二套 Python 业务源码。领域逻辑、MCP 实现和 P0 Skill 契约仍分别以 `src/dianxun/` 与 `skills/` 为唯一事实源。

| 目录 | 用途 | 唯一事实源 |
|---|---|---|
| [`dianxun-mcp/`](dianxun-mcp/) | MCP 容器镜像构建描述 | `src/dianxun/`、`config/`、`demo/state/`、`schemas/` |
| [`dianxun-worker/`](dianxun-worker/) | AgentTeams `v1.2.3` Worker ZIP 源布局 | `skills/` 下 6 个 P0 canonical 目录及 Worker config |

生成制品统一进入 `dist/`，不得手工修改 ZIP、校验和或包内 Skill。
