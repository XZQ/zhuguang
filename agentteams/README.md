# 逐光｜AgentTeams v1.2.3 部署说明

本目录提供逐光（店巡 Agent）的 AgentTeams 声明式资源和有状态 MCP Kubernetes 资源。版本固定为 AgentTeams `v1.2.3`（commit `223ddc2b8073e4c8b93bcbb15e1d717f196c04d9`），Manager 与 Worker runtime 均为 `qwenpaw`。

## 交付物与边界

```text
agentteams/
  namespace.yaml
  manager.yaml
  team.yaml
  workers/*.yaml
  mcp/{pvc,deployment,service}.yaml
  overlays/polardb/{kustomization,deployment-patch}.yaml
packages/dianxun-worker/
  manifest.json
  config/{SOUL,AGENTS}.md
  skills/{registry.json,LIFECYCLE.md}
  skills/<6 个 P0 Skill>/...
packages/dianxun-mcp/Dockerfile
dist/dianxun-worker.zip
dist/dianxun-worker.provenance.json
```

Worker YAML 的 `spec.package` 指向公共仓库中的 HTTP ZIP。当前 SHA-256 为 `6f3a9e590ee85b7336b529488e82f979ea3e3d04c1d1fbda2f1dd397bbc5289b`；`dist/dianxun-worker.provenance.json` 还记录 Registry、生命周期文档和每个 Skill 的版本与内容哈希。MCP Deployment 使用本地镜像名 `dianxun-mcp:0.2.0`；远程集群部署前必须替换为集群可访问的镜像。

当前仓库只提交脱敏、可复现的配置。只有真实平台产生的 Team Room、委派消息、MCP 调用和资源状态才是动态证据；本地契约测试不能替代它们。

## 1. 本地构建与静态验证

在仓库根目录执行：

```powershell
uv sync --group dev
uv run python scripts/build_worker_package.py
uv run python -m unittest -v tests.test_skill_registry
uv run python -m unittest -v tests.test_agentteams_artifacts
```

Linux/macOS 命令相同。构建是确定性的：输入未变化时 ZIP 和 SHA-256 不变化，且测试会确认包内 6 个 Skill 与根目录规范逐字一致。

仓库内有 5 项 AgentTeams artifact 测试、4 项动态证据校验器测试和 10 项协调生命周期测试；全量发现 87 项测试，其中 85 项通过、2 项 PolarDB 条件集成测试因无外部实例跳过。六场景评测为 6/6。这些结果不验证平台动态委派、托管 PolarDB 或 `qwen3.5-plus` 模型效果。

## 2. 模型、凭证、费用与 Skill 类型

- Manager 与 5 个 Worker 的 YAML 均声明 `qwenpaw + qwen3.5-plus`；模型只用于目标 AgentTeams 的任务拆解、结构化协作和工具编排。本地 Demo/M4 不调用 LLM。
- 模型/API 凭证必须由 AgentTeams/Kubernetes 运行时通过 Secret、环境变量或外部密钥系统注入，不得写入 YAML、ZIP、日志、Trace 或视频。
- 费用取决于实际提供商、输入/输出 Token、调用次数和集群资源；当前没有真实平台账单，动态验收时应保存脱敏用量/费用证据，无法取得则标记“未测量”。
- 可换为 AgentTeams/QwenPaw 支持且满足结构化输出和工具调用要求的兼容模型；需修改 `spec.model`/提供商配置，并重跑工具调用、结构化回执、延迟、费用和安全回归。
- 当前 Worker 包中的 6 个 P0 均为自定义可复用 Skill，并内置版本 Registry 与生命周期门禁。复赛规则要求核心 Skill 可发现、可加载、可调用并形成 Trace，不要求指定云厂商 Skill；是否满足以目标 AgentTeams 运行证据为准。

## 3. 构建和部署 MCP

Docker build context 必须是仓库根目录：

```bash
docker build -f packages/dianxun-mcp/Dockerfile -t dianxun-mcp:0.2.0 .
```

本地 kind/minikube 可直接加载镜像；远程集群应推送到私有或公共 Registry，然后修改 Deployment：

```bash
kubectl set image -f agentteams/mcp/deployment.yaml \
  mcp=REGISTRY/dianxun-mcp:0.2.0 --local -o yaml > /tmp/dianxun-mcp-deployment.yaml

kubectl apply -f agentteams/namespace.yaml
kubectl -n dianxun create secret generic dianxun-agent-identities \
  --from-file=actor-tokens-json=/secure/local/actor-tokens.json \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f agentteams/mcp/pvc.yaml
kubectl apply -f /tmp/dianxun-mcp-deployment.yaml
kubectl apply -f agentteams/mcp/service.yaml
kubectl -n dianxun rollout status deployment/dianxun-mcp
kubectl -n dianxun get pod,service,pvc
```

`/secure/local/actor-tokens.json` 必须位于仓库外并限制访问；不要把 Secret YAML、命令输出或真实 Token 保存到仓库和录屏中。

在本地镜像已加载且名称不变时，可直接 apply 原始 `deployment.yaml`。MCP 以单副本运行并使用 PVC 保存 SQLite 状态与 Trace；空卷首次启动时从固定 Seed 初始化。Deployment 强制引用 `dianxun-agent-identities` Secret，未创建时 Pod 不会就绪。Service 的集群内地址为：

```text
http://dianxun-mcp.dianxun.svc.cluster.local/mcp
```

### MCP 身份接线门禁

HTTP Adapter 支持：

- `MCP_TOKEN`：共享 Bearer 请求认证，不区分 Worker 角色，只允许只读工具；
- `MCP_ACTOR_TOKENS_JSON`：Bearer Token → Actor 映射，可将服务身份绑定到业务角色。

未配置时 Adapter 只在回环地址保留匿名 Demo；非回环监听会拒绝启动。`deployment.yaml` 已引用 Actor 映射 Secret，但 Worker CR 的 `mcpServers` 只支持 `name/url/transport`，动态 `gatewayKey` 不能预填进仓库。因此必须在 Worker 创建后由部署者把真实动态身份写入集群 Secret 或可信网关；静态引用本身不能证明 Worker 身份已经验证。

目标环境必须在 Worker 创建后，通过可信网关或运行时 Secret 将动态 Bearer 身份映射到正确 Actor，并限制 MCP Service 的网络入口。Adapter 会再次按工具级角色白名单授权。动态验收至少包括：无 Token/错误 Token 返回 401；错误角色调用不属于自己的查询或动作得到 `FORBIDDEN`；正确调用的 Audit Log 记录实际 Actor；密钥可轮换/撤销。任何日志、命令、视频和提交都不得出现 Token 或 `gatewayKey` 原文。

### PolarDB overlay

`agentteams/overlays/polardb` 将状态库切换为 PolarDB PostgreSQL，并启用 3 个知识工具和远程 embedding。它只引用以下 Secret，不提交真实值：

- `dianxun-polardb-runtime/database-url`：受 RLS 约束的运行账号 DSN；
- `dianxun-embedding-runtime/{endpoint,model,api-key}`：HTTPS embedding 服务配置；
- `dianxun-agent-identities/actor-tokens-json`：动态 Token → Actor 映射。

数据库管理员需先从可信环境按顺序执行：

```powershell
uv run dianxun db-bootstrap --profile core --profile security --profile cron --profile archive
```

迁移/安全管理员还要为每个数据库登录账号登记不可自改的 principal scope。下面只展示无密码示例，角色名、租户和门店需按目标环境替换；密码、DSN 和轮换配置必须由 PolarDB/Kubernetes Secret 或外部密钥系统完成：

```sql
-- 门店运行账号：可执行状态闭环，但被限制在 demo / S03。
CREATE ROLE dianxun_app_demo_s03 LOGIN INHERIT;
GRANT dianxun_runtime TO dianxun_app_demo_s03;
INSERT INTO dianxun_principal_scope(database_role, tenant_id, runtime_role, store_id)
VALUES ('dianxun_app_demo_s03', 'demo', 'runtime', 'S03')
ON CONFLICT(database_role) DO UPDATE SET
    tenant_id = EXCLUDED.tenant_id,
    runtime_role = EXCLUDED.runtime_role,
    store_id = EXCLUDED.store_id;

-- 租户总部账号：可看该租户全部门店及供应商信息，不能跨租户。
CREATE ROLE dianxun_hq_demo LOGIN INHERIT;
GRANT dianxun_hq TO dianxun_hq_demo;
INSERT INTO dianxun_principal_scope(database_role, tenant_id, runtime_role, store_id)
VALUES ('dianxun_hq_demo', 'demo', 'hq', NULL)
ON CONFLICT(database_role) DO UPDATE SET
    tenant_id = EXCLUDED.tenant_id,
    runtime_role = EXCLUDED.runtime_role,
    store_id = EXCLUDED.store_id;

-- 业务只读账号：只能 SELECT 已授权业务表，仍受租户和门店 RLS 限制。
CREATE ROLE dianxun_ro_demo_s03 LOGIN INHERIT;
GRANT dianxun_business_ro TO dianxun_ro_demo_s03;
INSERT INTO dianxun_principal_scope(database_role, tenant_id, runtime_role, store_id)
VALUES ('dianxun_ro_demo_s03', 'demo', 'runtime', 'S03')
ON CONFLICT(database_role) DO UPDATE SET
    tenant_id = EXCLUDED.tenant_id,
    runtime_role = EXCLUDED.runtime_role,
    store_id = EXCLUDED.store_id;
```

`dianxun_principal_scope` 对运行、HQ 和业务只读组角色均不可写，只有迁移/安全管理员可以配置；租户 HQ 不得登记为 `tenant_id='*'`。每类账号应使用独立 DSN 直连，不能依赖 `SET ROLE` 伪装身份，因为 RLS 以 `session_user` 为准。上线门禁必须用三类独立登录分别验证 `SELECT session_user, * FROM dianxun_current_scope()`、跨门店/跨租户不可见、只读写入失败、租户 HQ 仅能访问本租户供应商信息。

随后执行 `kubectl apply -k agentteams/overlays/polardb`。迁移 DSN 与运行 DSN 必须分离；运行账号不得拥有建角色、建扩展或 DELETE 权限。`pg_cron` 只入队，`dianxun_cron_health` 用于监控；OSS foreign table 由云环境预配置，归档函数只复制、复核并记 manifest，不删除源分区。

## 4. 应用 AgentTeams 资源

先安装并运行官方 AgentTeams `v1.2.3`。官方稳定入口是 `install/agentteams-apply.sh -f <yaml>`；当前 `agt apply` 不支持 `--recursive`、`--dry-run`、`--prune` 或 `--watch`。

```bash
export AGENTTEAMS_HOME=/path/to/AgentTeams-v1.2.3

bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/manager.yaml
bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/workers/orchestrator.yaml
bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/workers/sentry.yaml
bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/workers/diagnoser.yaml
bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/workers/executor.yaml
bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/workers/auditor.yaml
bash "$AGENTTEAMS_HOME/install/agentteams-apply.sh" -f agentteams/team.yaml
```

Team 必须最后创建，因为它引用 5 个已存在的 Worker CR。Windows 可在 WSL 执行上面的官方 Bash 入口，或使用官方 `install/agentteams-import.ps1 -File <yaml>` 转发 YAML。

## 5. 动态烟测与证据

```bash
docker exec agentteams-manager agt get managers dianxun-manager -o json
docker exec agentteams-manager agt get workers -o json
docker exec agentteams-manager agt get teams dianxun-patrol-team -o json
kubectl -n dianxun get deployment,pod,service,pvc
```

在 Element Web 的 Team Room 向 Manager 提交固定场景 A，并核对：

1. Manager 只委派 Orchestrator；
2. Orchestrator 分别委派 Sentry、Diagnoser、Executor、Auditor；
3. Worker 回执含 `incident_id`、phase、evidence refs、request ID；
4. 至少一条 Worker 通过 `dianxun-mcp` 产生真实工具返回；
5. Auditor 重新查询设备与商品状态，而非复述 Executor；
6. 每次 Skill/工具调用记录的 Skill version/digest 与 Worker provenance 一致；
7. 最终 Incident 状态、MCP 数据、报告和 Trace ID 一致；
8. 记录实际 model/runtime、脱敏的凭证来源类型和可获得的 Token/费用数据；不得显示 Key；
9. 验证 Worker Bearer → Actor 映射，并保留匿名/错误 Token 拒绝、越权 `FORBIDDEN` 和正确 Actor 审计的脱敏证据。
10. 每次委派保留 tenant、context version、assignment、attempt、lease、heartbeat 和 checkpoint；lease 未过期不得重派，超时只生成一个 successor。
11. 至少演示一次 Worker/Orchestrator 重启后从成功 checkpoint 恢复，跳过已完成副作用；Context completed 不得替代 IncidentService 的 CLOSED。

建议同时录制场景 F（`query_workorder` 返回 `partial`）：Auditor 必须阻断关闭，停售保持 active，事件停在 `CONTAINED / BLOCKED`。正常和失败分支的镜头、脱敏与证据门禁见 [`../docs/demo/Demo视频脚本与证据清单.md`](../docs/demo/Demo视频脚本与证据清单.md)。

保存证据前必须脱敏。若当前机器没有 Docker、Kubernetes 或 AgentTeams，不得把 ZIP 校验、YAML 解析或本地 MCP 调用写成“真实 AgentTeams 已跑通”。

将脱敏后的双分支证据整理为 `schemas/agentteams-run-evidence.v1.schema.json` 对应的 JSON，再运行：

```powershell
uv run dianxun agentteams-verify <evidence.json> --output <gate-report.json>
```

校验器使用证据 Schema `1.2`，除正确角色-阶段委派、四类 Worker 工具调用、人工审批、包/Skill provenance、每次调用的 Skill version/digest、安全正负向结果、唯一关联 ID 和非占位 Trace 哈希外，还要求 tenant-bound Context、单调 checkpoint version、Worker heartbeat、唯一 timeout successor 和至少一次 checkpoint 恢复证据。它只校验提交的证据包，不能生成或替代真实平台证据。

## 安全说明

- YAML 和 ZIP 不含 API Key、审批身份或固定 Bearer Token。
- 当前 ClusterIP 是比赛环境的内部直连接线骨架，Deployment 只声明 Actor Secret 引用，仓库未注入真实动态 Worker 映射值；生产环境必须由可信网关/Adapter 完成认证和工具级 Actor 授权，并限制后端 Service 的网络入口。
- 请求带 Bearer Header 只证明客户端发送了字段，不证明服务端已验证；取得 401、`FORBIDDEN` 和正确 Actor 审计证据前，状态保持“外部待验证”。
- 冷链阈值和 Seed 仅用于比赛 Demo，不替代 HACCP、设备说明书、食品安全人员判断或当地监管要求。
