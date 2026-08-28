# dianxun-mcp 镜像

本目录只提供 MCP 服务的 Dockerfile；镜像中的 Python 包、配置、Seed 和 Schema 均从仓库根目录复制，因此构建上下文必须是仓库根目录。

```powershell
docker build -f packages/dianxun-mcp/Dockerfile -t dianxun-mcp:dev .
```

服务入口为 `dianxun-mcp`，默认监听 `0.0.0.0:8080`，运行数据库位于 `/var/lib/dianxun/runtime.db`。生产部署应挂载持久卷并通过运行环境注入凭证；Dockerfile 不承载业务实现或密钥。

Adapter 支持 `MCP_TOKEN`（共享请求认证）和 `MCP_ACTOR_TOKENS_JSON`（Token → Actor 映射）。只有后者或可信网关的等价映射能证明调用角色；未配置时的匿名兼容模式只允许用于回环/受控 Demo。当前 `agentteams/mcp/deployment.yaml` 尚未接入 AgentTeams 动态 Worker `gatewayKey`，因此部署身份绑定仍为外部待验证，不能仅凭 Bearer Header 或 ClusterIP 推断完成。
