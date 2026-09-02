# 逐光｜店巡 Agent

> 让连锁门店异常从“告警已读”走到“证据完备、责任清晰、安全关闭”。

**逐光**是面向连锁便利店的多 Agent 异常闭环基础设施，也是 [GOAI Agent Infra 赛道](https://www.goaihz.com/tracks?track=infra)参赛项目。项目采用“一主两辅”展示策略：以**冷柜失温事件**作为首要完整验证场景，缺货与价签异常作为可独立运行的补充场景。

作品名统一为**逐光**；**店巡 Agent**用于说明产品能力，`dianxun` 保持为工程包、命令与资源前缀，仓库地址保持 `zhuguang`。

## 比赛命题与核心回答

| 评审关注点 | 逐光的回答 |
|---|---|
| 解决什么真实问题 | 冷柜失温跨越设备、商品、审批、维修和复核，真正的交付单位不是“发出告警”，而是“安全关闭事件” |
| 为什么需要多 Agent | 总控、巡检、诊断、处置、稽核职责分离；执行者不能自行宣布成功，Auditor 必须独立重查事实 |
| 如何约束风险 | 所有受控写经过业务角色、Policy/审批、幂等和审计；设备恢复不等于商品安全，工单完成不等于事件关闭 |
| 如何证明不是概念稿 | 6 个确定性冷柜场景、87 个测试用例、6 个 P0 Skill、12 个 P0 MCP、3 个可选知识 MCP 和可复现 Evidence 均在仓库内 |
| 如何扩展 | 冷柜承担主叙事；缺货、价签保留独立入口，验证同一闭环基础设施可复用，而不稀释答辩重点 |

当前仓库已完成有状态业务核心、冷柜五阶段闭环、AgentTeams `v1.2.3` Worker/MCP 部署产物，以及与实现一致的参赛材料。真实 Team Room、Worker 委派、Kubernetes Running 状态、Worker → MCP 身份绑定和平台 Trace 仍需在外部 AgentTeams 环境动态验证，仓库内结果不能替代该证据。

## 评委快速验收

要求 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。从仓库根目录执行：

```powershell
uv sync --group dev
uv run dianxun evaluate
```

评测会在临时 SQLite/Trace 数据库中运行 6 个正常与失败分支，确定性重写 `evidence/m4/results.json` 和 `evidence/m4/report.md`；只有全部本地 P0 门禁通过才退出 `0`。

进一步的架构证据与可视化入口：

```powershell
uv run dianxun ablation        # 消融对照:full / no_auditor / single_agent / rule_only
uv run dianxun command-center  # 生成 evidence/m4/command-center.html 事故指挥台
```

消融对照在同样六个场景上分别改变一个声明变量（移除 Auditor 独立验证、合并为单一身份、替换为纯规则根因排序），确定性重写 `evidence/m4/ablation.json` 和 `evidence/m4/ablation.md`；事故指挥台把六个场景的 Agent 交接链、设备状态链、商品批次处置、审批、审计与 Auditor 判决渲染成同屏只读 HTML。

## 当前可验证结论

| 结论 | 当前结果 | 证据 |
|---|---:|---|
| 冷柜 P0 场景 | 6/6 通过 | [`evidence/m4/report.md`](evidence/m4/report.md) |
| Ground truth Top-1 / Top-3 | 6/6、6/6 | [`evidence/m4/results.json`](evidence/m4/results.json) |
| Evidence 关键字段完整率 | 45/45 | 同上 |
| 适用阶段 Trace 覆盖率 | 26/26 | 同上 |
| 未授权写、未审批受控写、错误放行、错误关闭、重复副作用 | 均为 0 | 同上 |
| 消融对照：无 Auditor | 5 个需修复场景安全阻断于 VERIFY/BLOCKED；自证关闭、放行尝试、错误关闭、危险放行均为 0 | [`evidence/m4/ablation.md`](evidence/m4/ablation.md) |
| 消融对照：单一身份 / 纯规则 | 单一身份 6 次受控写全被 Policy 拒绝（保持 OPEN）；纯规则 Top-1 降至 4/6、2 张错派工单、安全违规 0 | 同上 |
| 事故指挥台 | 六场景同屏只读 HTML（交接链、温度曲线、批次处置、审批、审计、判决） | [`evidence/m4/command-center.html`](evidence/m4/command-center.html) |
| 自动化测试 | 87 项发现：85 通过、2 个 PolarDB 条件集成测试因无外部实例跳过 | `uv run --group dev python -W error::ResourceWarning -m unittest discover -v` |
| 协调上下文生命周期 | 租户隔离、TTL、WAL、乐观版本、lease/heartbeat、唯一超时重派和 checkpoint 重启恢复已通过本地并发测试 | `src/dianxun/context_bus.py`、`src/dianxun/coordination.py`、`tests/test_context_lifecycle.py` |
| PolarDB PostgreSQL 后端 | 代码与 SQL 契约已实现，外部待验证 | `src/dianxun/state/postgres.py`、`src/dianxun/state/sql/` |
| 知识飞轮 | 候选、人工审核、发布、检索及 Recall@K/MRR 已实现；真实门店改善率未验证 | `tests/test_knowledge_flywheel.py` |
| AgentTeams 动态协同 | 外部待验证 | [`agentteams/README.md`](agentteams/README.md) |
| AgentTeams → MCP 身份绑定 | 外部待验证 | Adapter 已强制 Token → Actor 和工具级角色白名单；Deployment 仅声明 Secret 引用，尚无动态 Worker 映射实跑证据 |

上述指标来自固定 seed、隔离的真实 SQLite/PolicyEngine 和有状态本地 Adapter/ScenarioEngine，只证明仓库内确定性行为，不代表真实门店收益、监管合规或生产可用性。

## 唯一事实口径

- 拓扑：1 个 AgentTeams Framework Manager + 5 个业务 Agent（Orchestrator、Sentry、Diagnoser、Executor、Auditor）。
- 业务流程：发现与遏制、诊断与决策、处置执行、独立验证、复盘演进。
- Skill：目标 9 个，其中 P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个；P0 由版本化 Registry 和生命周期门禁治理。
- MCP：P0 固定 12 个函数，包括 5 个查询和 7 个受控动作；P1 可选启用 3 个知识工具。
- 业务核心：`IncidentService` 是阶段迁移和事件状态的唯一事实入口。
- 协调控制面：tenant-bound `ContextBus` 只保存 assignment、checkpoint 和 Evidence refs；SQLite 持久化使用 WAL 与 `expected_version` 条件更新，Context 完成不等于业务关闭。
- 状态后端：SQLite 保留为零依赖确定性评测底座；PolarDB PostgreSQL 是托管部署底座，业务层通过同一 StateStore 协议访问。
- 证据等级：代码、测试和真实调用齐全才标记“已实现”；有状态外部替身标记“模拟实现”；必须在目标平台运行的能力标记“外部待验证”。
- 模型：`qwen3.5-plus` 仅声明给目标 AgentTeams Manager/Worker；本地确定性 Demo、87 项测试和 M4 评测不调用 LLM。
- Skill：当前 6 个 P0 均为自定义可复用 Skill；`skills/registry.json` 固定 stable/canary release，`skills/LIFECYCLE.md` 定义发布、兼容、升级、回滚和退役，本地 Span 记录 version/digest。目标 AgentTeams 中的发现、加载、调用和同字段 Trace 仍待动态验收；规则不要求指定云厂商 Skill。
- 鉴权：非回环监听未配置认证时拒绝启动；共享 `MCP_TOKEN` 只能调用只读工具，状态写必须使用 `MCP_ACTOR_TOKENS_JSON` 或可信网关绑定 Actor。部署清单引用 Secret，但动态 Worker 身份映射仍需外部验收。

机器可读事实见 [`config/project-facts.json`](config/project-facts.json)，里程碑与限制见 [`docs/assessments/实现状态矩阵.md`](docs/assessments/实现状态矩阵.md)。

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

## 系统架构

```mermaid
flowchart LR
    Input[异常或人工任务] --> O[Orchestrator<br/>拆解与汇总]
    O --> S[Sentry<br/>发现与遏制]
    O --> D[Diagnoser<br/>诊断与决策]
    O --> E[Executor<br/>受控执行]
    O --> A[Auditor<br/>独立验证与复盘]
    S --> Core[(IncidentService<br/>唯一业务事实入口)]
    D --> Core
    E --> Core
    A --> Core
    Core <--> MCP[12 个 MCP<br/>设备·库存·停售·审批·工单]
    Guard[业务角色·Policy/审批<br/>幂等·审计] -.约束.-> E
    A -.不通过则阻断关闭或回开.-> Core
```

AgentTeams 负责目标平台中的任务拆解与 Worker 委派；`IncidentService`、StateStore、Policy 和 MCP 负责业务事实与安全约束。两层不能互相冒充，平台动态协同仍以真实运行证据为准。

## 更多运行入口

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

默认未配置 Token 的模式只允许回环地址上的本地 Demo；非回环绑定会直接拒绝启动。`MCP_TOKEN` 是共享请求认证，只允许只读工具；所有状态写必须由 `MCP_ACTOR_TOKENS_JSON` 或可信网关完成 Token → Actor 映射。不要把工具默认 Actor 当作网络身份。

### 使用 PolarDB PostgreSQL 与知识飞轮

SQLite 不被删除，它承担无云依赖的确定性回归；PolarDB PostgreSQL 是部署后端。迁移配置必须按 `core → security → cron → archive` 顺序由管理账号执行：

```powershell
uv sync --extra postgres --group dev
$env:DIANXUN_DATABASE_URL = "postgresql://<admin>@<host>:5432/<database>?sslmode=require"
uv run dianxun db-bootstrap --profile core --profile security --profile cron --profile archive
```

四个 profile 分别提供 pgvector/业务表、RLS 与最小 GRANT、23:00 复盘入队及 `cron.job_run_details` 监控视图、面向已配置 OSS 外部表的审计分区复制与复核。`pg_cron` 只入队，不在数据库内执行 Agent 或 LLM；OSS 归档函数默认不删除源分区。

知识链路默认关闭，通过 `DIANXUN_ENABLE_P1_TOOLS=1` 和 `DIANXUN_RAG_ENABLED=1` 启用。Auditor 只能创建 pending 候选；独立人工审核且脱敏通过后才会生成向量并进入检索。离线 hash embedding 只用于确定性测试，生产可配置 HTTPS 的 OpenAI-compatible embedding endpoint。

Linux/macOS 只需去掉 PowerShell 的反引号续行；其余命令相同。

## 验证与构建

```powershell
# 模拟数据完整性
uv run python scripts/generate_demo_data.py --check

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
6f3a9e590ee85b7336b529488e82f979ea3e3d04c1d1fbda2f1dd397bbc5289b
```

AgentTeams 版本固定为 `v1.2.3`（commit `223ddc2b8073e4c8b93bcbb15e1d717f196c04d9`），CRD 为 `agentteams.io/v1beta1`，Manager/Worker runtime 为 `qwenpaw`。构建、部署和动态验收步骤见 [`agentteams/README.md`](agentteams/README.md)。

### 模型、凭证、费用与替代边界

- `qwen3.5-plus` 只用于目标 AgentTeams Manager/Worker 的任务拆解、结构化协作和工具编排；本地 `uv run dianxun evaluate` 不调用它，因此 6/6 和 87 项测试不是模型效果指标。
- 模型凭证只允许由目标 AgentTeams/Kubernetes 运行时通过 Secret、环境变量或外部密钥系统注入；仓库 YAML、Worker ZIP、Trace 和视频不得包含 Key。
- 模型费用取决于实际提供商、输入/输出 Token、调用次数和部署资源；当前没有真实平台运行账单，不能给出已验证成本。
- 可替换为 AgentTeams/QwenPaw 支持且满足结构化输出与工具调用要求的兼容模型。迁移通常不改领域模型和 MCP 契约，但必须调整 `spec.model`/提供商凭证，并重跑结构化输出、工具调用、延迟、费用与安全回归。

## 仓库结构

```text
config/                    机器可读事实与版本化 Demo Policy
data/                      缺货、价签等补充场景的合成样例数据
schemas/                   Incident、MCP、Scenario Schema
src/dianxun/               领域核心、Skill、MCP、Adapter 与评测器
skills/                    P0 Skill 契约、Registry、生命周期及规划/兼容说明
demo/                      六个冷柜场景、两个补充入口和运行时状态
agentteams/                Manager、Team、Worker 与 MCP Kubernetes 资源
packages/                  Worker 包源与 MCP 镜像构建上下文
scripts/                   数据生成和确定性制品构建脚本
dist/                      Worker ZIP 与 SHA-256
tests/                     单元、集成、契约与评测门禁
evidence/m4/               脱敏、可复现的本地评测结果
ppt/                       HTML 演示稿源文件与导出 PDF
docs/
  competition/             连续的 01～08 比赛材料及符合性矩阵
  assessments/             实现状态、真实门店差距与演进门禁
  demo/                    Demo 视频脚本与证据清单
```

完整文档导航见 [`docs/README.md`](docs/README.md)，交付包与业务源码的边界见 [`packages/README.md`](packages/README.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [`docs/competition/01-作品简介-500字.md`](docs/competition/01-作品简介-500字.md) | 500 字以内作品简介 |
| [`docs/competition/02-方案PPT结构.md`](docs/competition/02-方案PPT结构.md) | 答辩叙事、规则必备内容与证据来源 |
| [`docs/competition/03-Skill九要素卡.md`](docs/competition/03-Skill九要素卡.md) | 9 个目标 Skill 与 6 个 P0 工程契约 |
| [`docs/competition/04-模拟数据与场景说明.md`](docs/competition/04-模拟数据与场景说明.md) | 确定性 Seed、Scenario 与数据边界 |
| [`docs/competition/05-MCP工具契约.md`](docs/competition/05-MCP工具契约.md) | 12 个 P0 MCP 函数、安全和失败语义 |
| [`docs/competition/06-Agent-Identity清单.md`](docs/competition/06-Agent-Identity清单.md) | 1 Manager + 5 业务 Agent 的身份边界 |
| [`docs/competition/07-多Agent协同设计.md`](docs/competition/07-多Agent协同设计.md) | 五阶段与赛事八项要求映射 |
| [`docs/competition/08-复赛改造技术方案.md`](docs/competition/08-复赛改造技术方案.md) | 完整改造方案与里程碑记录 |
| [`docs/competition/比赛要求符合性矩阵.md`](docs/competition/比赛要求符合性矩阵.md) | 官网/手册逐项核对、缺口和可提交口径 |
| [`docs/assessments/实现状态矩阵.md`](docs/assessments/实现状态矩阵.md) | 仓库事实、里程碑状态和证据边界 |
| [`docs/assessments/真实门店差距与演进路线.md`](docs/assessments/真实门店差距与演进路线.md) | 与真实门店、HACCP、人员和企业系统的差距及灰度路线 |
| [`docs/demo/Demo视频脚本与证据清单.md`](docs/demo/Demo视频脚本与证据清单.md) | 正常/失败分支录制脚本与真实性门禁 |

模拟数据可执行入口为 [`scripts/generate_demo_data.py`](scripts/generate_demo_data.py)，不与 01～08 文档混放。

## 安全与已知边界

- 冷链 Policy 只用于比赛合成数据，不替代商品标签、企业 HACCP、设备说明书或所在地法规。
- POS、库存、IoT、审批和维修商均为有状态 Mock；没有真实企业接口、真实人员 SLA 或真实食品处置授权。
- PolarDB/pgvector/RLS/分区/pg_cron/归档契约和可选知识飞轮已有代码与静态/本地测试，但尚无托管实例、OSS、真实门店基线和生产性能证据；不得表述为云上已投产。
- 自动回滚、Nacos、Higress、RocketMQ 和 LoongSuite 仍属于规划或生产替换方向。
- AgentTeams YAML、Worker ZIP 和本地 MCP 兼容烟测不等于真实多 Agent 动态协同。
- 当前 Deployment 只强制声明 Actor Secret 引用，仓库不含真实动态 Worker 映射值；取得匿名/错误 Token 拒绝、工具级越权 `FORBIDDEN` 和正确 Actor 审计证据前，不声明部署鉴权闭环。
- 当前 P0 使用自定义可复用 Skill；复赛规则不要求指定云厂商 Skill，不把云产品数量作为完成度证据。
- 不提交 API Key、真实审批身份、顾客数据、照片原件、运行时数据库或含敏感内容的 Trace。

## License

[MIT](LICENSE)
