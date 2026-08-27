# 店巡 Agent（筑光）

面向连锁便利店的多 Agent 异常闭环基础设施。项目采用“一主两辅”展示策略：以**冷柜失温事件**作为首要完整验证场景，缺货与价签异常作为可独立运行的补充场景。

当前仓库已完成有状态业务核心、冷柜五阶段闭环、6 个确定性评测场景、AgentTeams `v1.2.3` Worker/MCP 部署产物，以及与实现一致的参赛材料。真实 Team Room、Worker 委派、Kubernetes Running 状态和平台 Trace 仍需在外部 AgentTeams 环境动态验证，仓库内结果不能替代该证据。

## 当前可验证结论

| 结论 | 当前结果 | 证据 |
|---|---:|---|
| 冷柜 P0 场景 | 6/6 通过 | [`evidence/m4/report.md`](evidence/m4/report.md) |
| Ground truth Top-1 / Top-3 | 6/6、6/6 | [`evidence/m4/results.json`](evidence/m4/results.json) |
| Evidence 关键字段完整率 | 45/45 | 同上 |
| 适用阶段 Trace 覆盖率 | 26/26 | 同上 |
| 未授权写、未审批受控写、错误放行、错误关闭、重复副作用 | 均为 0 | 同上 |
| 自动化测试 | 42 项通过 | `uv run --group dev python -W error::ResourceWarning -m unittest discover -v` |
| AgentTeams 动态协同 | 外部待验证 | [`agentteams/README.md`](agentteams/README.md) |

上述指标来自固定 seed 和有状态 Mock，只证明仓库内确定性行为，不代表真实门店收益、监管合规或生产可用性。

## 唯一事实口径

- 拓扑：1 个 AgentTeams Framework Manager + 5 个业务 Agent（Orchestrator、Sentry、Diagnoser、Executor、Auditor）。
- 业务流程：发现与遏制、诊断与决策、处置执行、独立验证、复盘演进。
- Skill：目标 9 个，其中 P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个。
- MCP：P0 固定 12 个函数，包括 5 个查询和 7 个受控动作。
- 业务核心：`IncidentService` 是阶段迁移和事件状态的唯一事实入口。
- 证据等级：代码、测试和真实调用齐全才标记“已实现”；有状态外部替身标记“模拟实现”；必须在目标平台运行的能力标记“外部待验证”。
- 模型：`qwen3.5-plus` 仅声明给目标 AgentTeams Manager/Worker；本地确定性 Demo、42 项测试和 M4 评测不调用 LLM。
- Skill：当前 6 个 P0 均为自定义可复用 Skill；官网与参赛手册 FAQ 对“阿里云官方用云 Skills”的措辞存在差异，状态为“待组委会确认”。

机器可读事实见 [`config/project-facts.json`](config/project-facts.json)，里程碑与限制见 [`docs/实现状态矩阵.md`](docs/实现状态矩阵.md)。

## 为什么把冷柜失温作为主展示场景

项目没有删除缺货和价签能力，而是把展示层次收敛为“一主两辅”。冷柜事件同时具备安全遏制、设备诊断、商品批次处置、人工审批、外部维修、独立验证和失败回开，能够在一条事件链中证明多 Agent 协作的必要性。缺货与价签继续保留独立入口，用于证明底层能力可扩展，但不与冷柜争夺主叙事。

系统坚持两个业务约束：**设备恢复不等于商品安全，工单完成不等于事件关闭**。Executor 只能执行受控动作；Auditor 必须重新查询设备、商品批次、停售、审批和工单状态；最终 `RESOLVED` / `CLOSED` 由 `IncidentService` 按规则聚合。

## 五阶段闭环

```text
1. 发现与遏制
   Sentry 识别异常；Executor 先停售并隔离受影响批次
2. 诊断与决策
   Diagnoser 输出证据关联的 Top-K 假设；Policy 决定是否需要审批
3. 处置执行
   Executor 经授权创建工单、处置批次或等待人工输入
4. 独立验证
   Auditor 重新查询业务事实；partial 或不安全结果会阻断关闭或回开
5. 复盘演进
   Auditor 生成复盘与待审知识候选；不虚构 RAG 命中或自动发布
```

主阶段之外，事件还独立记录 `incident_status`、`work_status`、审批、工单、商品批次和停售状态，以表达等待、失败和并发，而不是把所有信息压进一条线性状态机。

## 快速开始

要求 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```powershell
uv sync --group dev
uv run dianxun evaluate
```

`dianxun evaluate` 会在临时 SQLite/Trace 数据库中逐个运行 6 个场景，并确定性重写：

- `evidence/m4/results.json`
- `evidence/m4/report.md`

命令只有在全部本地 P0 门禁通过时才退出 `0`。

### 运行单个冷柜场景

```powershell
uv run dianxun demo-run demo/state/scenarios/coldchain-compressor-failure.json
uv run dianxun demo-run demo/state/scenarios/coldchain-sensor-false-positive.json
uv run dianxun demo-run demo/state/scenarios/coldchain-door-left-open.json
uv run dianxun demo-run demo/state/scenarios/coldchain-approval-timeout.json
uv run dianxun demo-run demo/state/scenarios/coldchain-device-recovered-goods-unsafe.json
uv run dianxun demo-run demo/state/scenarios/coldchain-workorder-query-partial.json
```

六条路径分别验证：压缩机故障、传感器误报、门未关闭、审批超时、设备恢复但商品仍不安全、工单查询部分失败。每个 Scenario 声明预期终态；不一致时命令退出非零。

### 运行补充场景

```powershell
uv run python demo/run_supplementary.py stockout
uv run python demo/run_supplementary.py price-tag
```

两个入口使用隔离的临时 Trace 数据库，只证明缺货和价签的历史能力仍可运行；冷柜验收以六场景评测为准。

### 调用有状态 MCP

```powershell
uv run dianxun state-init
uv run dianxun scenario-reset demo/state/scenarios/coldchain-compressor-failure.json
uv run dianxun mcp-tools
uv run dianxun mcp-call query_device_context `
  --arguments '{"device_id":"FROST-S03","facets":["temperature","health"]}'
uv run dianxun-mcp
```

默认 Streamable HTTP / JSON-RPC Adapter 监听 `127.0.0.1:8080`。运行时数据库为 `demo/state/runtime.db`，已被 Git 忽略。

Linux/macOS 只需去掉 PowerShell 的反引号续行；其余命令相同。

## 验证与构建

```powershell
# 模拟数据完整性
uv run python 04-模拟数据生成脚本.py --check

# 全量测试
uv run --group dev python -W error::ResourceWarning -m unittest discover -v

# 代码质量
uv run --group dev ruff check .
uv run --group dev ruff format --check .

# 确定性 Worker ZIP
uv run python scripts/build_worker_package.py
uv run --group dev python -m unittest -v tests.test_agentteams_artifacts
```

当前 Worker ZIP SHA-256：

```text
0a905c2b33dc28fb0b2427349fa2ed59af35c1c85afee9b1e54a7f1f7c832fea
```

AgentTeams 版本固定为 `v1.2.3`（commit `223ddc2b8073e4c8b93bcbb15e1d717f196c04d9`），CRD 为 `agentteams.io/v1beta1`，Manager/Worker runtime 为 `qwenpaw`。构建、部署和动态验收步骤见 [`agentteams/README.md`](agentteams/README.md)。

### 模型、凭证、费用与替代边界

- `qwen3.5-plus` 只用于目标 AgentTeams Manager/Worker 的任务拆解、结构化协作和工具编排；本地 `uv run dianxun evaluate` 不调用它，因此 6/6 和 42 项测试不是模型效果指标。
- 模型凭证只允许由目标 AgentTeams/Kubernetes 运行时通过 Secret、环境变量或外部密钥系统注入；仓库 YAML、Worker ZIP、Trace 和视频不得包含 Key。
- 模型费用取决于实际提供商、输入/输出 Token、调用次数和部署资源；当前没有真实平台运行账单，不能给出已验证成本。
- 可替换为 AgentTeams/QwenPaw 支持且满足结构化输出与工具调用要求的兼容模型。迁移通常不改领域模型和 MCP 契约，但必须调整 `spec.model`/提供商凭证，并重跑结构化输出、工具调用、延迟、费用与安全回归。

## 仓库结构

```text
config/                    冻结事实与版本化比赛 Policy
schemas/                   Incident、MCP、Scenario Schema
src/dianxun/               领域核心、Skill、MCP、Adapter 与评测器
demo/                      六个冷柜场景和两个补充入口
agentteams/                Manager/Team/Worker 与 MCP Kubernetes 资源
packages/dianxun-worker/   AgentTeams Worker 包源目录
packages/dianxun-mcp/      MCP 镜像 Dockerfile
scripts/                   确定性构建脚本
dist/                      Worker ZIP 与 SHA-256
tests/                     单元、集成、契约与评测门禁
evidence/m4/               脱敏、可复现的本地评测结果
ppt/                       HTML 演示稿源文件与导出 PDF
docs/                      实现状态、比赛核对和真实场景差距
```

## 文档索引

| 文档 | 内容 |
|---|---|
| [`01-作品简介-500字.md`](01-作品简介-500字.md) | 500 字以内作品简介 |
| [`02-方案PPT结构.md`](02-方案PPT结构.md) | 10 页答辩叙事与证据来源 |
| [`03-Skill九要素卡.md`](03-Skill九要素卡.md) | 9 个目标 Skill 与 6 个 P0 工程契约 |
| [`04-模拟数据生成脚本.py`](04-模拟数据生成脚本.py) | 确定性数据生成与校验入口 |
| [`05-MCP工具契约.md`](05-MCP工具契约.md) | 12 个 P0 MCP 函数、安全和失败语义 |
| [`06-Agent-Identity清单.md`](06-Agent-Identity清单.md) | 1 Manager + 5 业务 Agent 的身份边界 |
| [`07-多Agent协同设计.md`](07-多Agent协同设计.md) | 五阶段与赛事八项要求映射 |
| [`08-复赛改造技术方案.md`](08-复赛改造技术方案.md) | 完整改造方案与里程碑记录 |
| [`docs/实现状态矩阵.md`](docs/实现状态矩阵.md) | 仓库事实、里程碑状态和证据边界 |
| [`docs/比赛要求符合性矩阵.md`](docs/比赛要求符合性矩阵.md) | 官网/手册逐项核对、缺口和可提交口径 |
| [`docs/真实门店差距与演进路线.md`](docs/真实门店差距与演进路线.md) | 与真实门店、HACCP、人员和企业系统的差距及灰度路线 |
| [`docs/Demo视频脚本与证据清单.md`](docs/Demo视频脚本与证据清单.md) | 正常/失败分支录制脚本与真实性门禁 |

## 安全与已知边界

- 冷链 Policy 只用于比赛合成数据，不替代商品标签、企业 HACCP、设备说明书或所在地法规。
- POS、库存、IoT、审批和维修商均为有状态 Mock；没有真实企业接口、真实人员 SLA 或真实食品处置授权。
- RAG、自动回滚、Nacos、Higress、RocketMQ、PolarDB 和 LoongSuite 属于规划或生产替换方向，当前不声明已实现。
- AgentTeams YAML、Worker ZIP 和本地 MCP 兼容烟测不等于真实多 Agent 动态协同。
- 当前 P0 仅使用自定义 Skill；“官方用云 Skills”是否为硬门槛仍需组委会书面确认。
- 不提交 API Key、真实审批身份、顾客数据、照片原件、运行时数据库或含敏感内容的 Trace。

## License

[MIT](LICENSE)
