# AgentTeams v1.2.3 部署说明

本目录提供店巡 Agent 的 AgentTeams 声明式资源和有状态 MCP Kubernetes 资源。版本固定为 AgentTeams `v1.2.3`（commit `223ddc2b8073e4c8b93bcbb15e1d717f196c04d9`），Manager 与 Worker runtime 均为 `qwenpaw`。

## 交付物与边界

```text
agentteams/
  namespace.yaml
  manager.yaml
  team.yaml
  workers/*.yaml
  mcp/{pvc,deployment,service}.yaml
packages/dianxun-worker/
  manifest.json
  config/{SOUL,AGENTS}.md
  skills/<6 个 P0 Skill>/...
packages/dianxun-mcp/Dockerfile
dist/dianxun-worker.zip
```

Worker YAML 的 `spec.package` 指向公共仓库中真实的 HTTP ZIP，而不是普通目录。ZIP 的 SHA-256 位于 `dist/dianxun-worker.zip.sha256`，当前值为 `0a905c2b33dc28fb0b2427349fa2ed59af35c1c85afee9b1e54a7f1f7c832fea`。MCP Deployment 使用本地镜像名 `dianxun-mcp:0.2.0`；远程集群部署前必须将该镜像推送到可访问的镜像仓库并替换镜像地址。

当前仓库只提交脱敏、可复现的配置。只有真实平台产生的 Team Room、委派消息、MCP 调用和资源状态才是动态证据；本地契约测试不能替代它们。

## 1. 本地构建与静态验证

在仓库根目录执行：

```powershell
uv sync --group dev
uv run python scripts/build_worker_package.py
uv run python -m unittest -v tests.test_agentteams_artifacts
```

Linux/macOS 命令相同。构建是确定性的：输入未变化时 ZIP 和 SHA-256 不变化，且测试会确认包内 6 个 Skill 与根目录规范逐字一致。

仓库内当前有 5 项 AgentTeams artifact 契约测试；整个项目的 42 项自动化测试和六场景评测也已通过。这些结果验证静态包、业务核心和本地 MCP 行为，不验证平台动态委派或 `qwen3.5-plus` 模型效果。

## 2. 模型、凭证、费用与 Skill 类型

- Manager 与 5 个 Worker 的 YAML 均声明 `qwenpaw + qwen3.5-plus`；模型只用于目标 AgentTeams 的任务拆解、结构化协作和工具编排。本地 Demo/M4 不调用 LLM。
- 模型/API 凭证必须由 AgentTeams/Kubernetes 运行时通过 Secret、环境变量或外部密钥系统注入，不得写入 YAML、ZIP、日志、Trace 或视频。
- 费用取决于实际提供商、输入/输出 Token、调用次数和集群资源；当前没有真实平台账单，动态验收时应保存脱敏用量/费用证据，无法取得则标记“未测量”。
- 可换为 AgentTeams/QwenPaw 支持且满足结构化输出和工具调用要求的兼容模型；需修改 `spec.model`/提供商配置，并重跑工具调用、结构化回执、延迟、费用和安全回归。
- 当前 Worker 包中的 6 个 P0 均为自定义可复用 Skill。官网与手册 FAQ 对“阿里云官方用云 Skills”的措辞冲突待组委会确认；未取得结论或真实官方 Skill 调用证据前，不标记为完全满足。

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
kubectl apply -f agentteams/mcp/pvc.yaml
kubectl apply -f /tmp/dianxun-mcp-deployment.yaml
kubectl apply -f agentteams/mcp/service.yaml
kubectl -n dianxun rollout status deployment/dianxun-mcp
kubectl -n dianxun get pod,service,pvc
```

在本地镜像已加载且名称不变时，可直接 apply 原始 `deployment.yaml`。MCP 以单副本运行并使用 PVC 保存 SQLite 状态；空卷首次启动时从固定 Seed 初始化。Service 的集群内地址为：

```text
http://dianxun-mcp.dianxun.svc.cluster.local/mcp
```

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
6. 最终 Incident 状态、MCP 数据、报告和 Trace ID 一致。
7. 记录实际 model/runtime、脱敏的凭证来源类型和可获得的 Token/费用数据；不得显示 Key。

建议同时录制场景 F（`query_workorder` 返回 `partial`）：Auditor 必须阻断关闭，停售保持 active，事件停在 `CONTAINED / BLOCKED`。正常和失败分支的镜头、脱敏与证据门禁见 [`../docs/Demo视频脚本与证据清单.md`](../docs/Demo视频脚本与证据清单.md)。

保存证据前必须脱敏。若当前机器没有 Docker、Kubernetes 或 AgentTeams，不得把 ZIP 校验、YAML 解析或本地 MCP 调用写成“真实 AgentTeams 已跑通”。

## 安全说明

- YAML 和 ZIP 不含 API Key、审批身份或固定 Bearer Token。
- 当前 ClusterIP 是比赛环境的内部直连方式；生产环境应由 AgentTeams/Higress 网关完成身份与授权，并限制后端 Service 的网络入口。
- 冷链阈值和 Seed 仅用于比赛 Demo，不替代 HACCP、设备说明书、食品安全人员判断或当地监管要求。
