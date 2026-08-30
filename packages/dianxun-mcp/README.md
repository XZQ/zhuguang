# 逐光｜dianxun-mcp 镜像

本目录只提供 MCP 服务的 Dockerfile；镜像中的 Python 包、配置、Seed 和 Schema 均从仓库根目录复制，因此构建上下文必须是仓库根目录。

```powershell
docker build -f packages/dianxun-mcp/Dockerfile -t dianxun-mcp:dev .
```

服务入口为 `dianxun-mcp`，默认监听 `0.0.0.0:8080`，运行数据库位于 `/var/lib/dianxun/runtime.db`。生产部署应挂载持久卷并通过运行环境注入凭证；Dockerfile 不承载业务实现或密钥。

Adapter 支持 `MCP_TOKEN`（共享请求认证，只读）和 `MCP_ACTOR_TOKENS_JSON`（Token → Actor 映射，状态写必需），并对每个工具强制角色白名单。非回环无认证时服务拒绝启动；基础 Deployment 已强制引用 Actor Secret。动态 Worker `gatewayKey` 的真实映射和正负向烟测仍为外部待验证，不能仅凭 Secret 引用、Bearer Header 或 ClusterIP 推断完成。

默认镜像同时包含 SQLite 与可选 PostgreSQL 驱动。SQLite 用于零依赖 Demo；设置 `DIANXUN_DATABASE_URL` 后使用 PolarDB PostgreSQL。数据库迁移必须在镜像外由管理账号执行，运行容器只使用最小权限 DSN。P1 知识工具、embedding 和 PolarDB overlay 见 [`../../agentteams/README.md`](../../agentteams/README.md)。
