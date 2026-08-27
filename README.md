# 店巡 Agent（筑光）

面向连锁便利店的多 Agent 异常闭环系统。复赛版本采用“一主两辅”：以冷柜失温作为首要完整验证场景，缺货与价签异常保留为补充展示和独立回归入口。

> 当前状态：M0～M2 已完成；M3 的 Worker ZIP、v1.2.3 YAML、MCP Deployment 和本地 `mcporter` 兼容烟测已完成，真实 Team Room/Worker 委派仍待具备 Docker、Kubernetes 与 AgentTeams 的目标环境验证；M4～M5 正在实施。

## 唯一事实口径

- 拓扑：1 个 AgentTeams Framework Manager + 5 个业务 Agent（Orchestrator、Sentry、Diagnoser、Executor、Auditor）。
- 业务流程：发现与遏制、诊断与决策、处置执行、独立验证、复盘演进。
- 场景：冷柜失温为首要完整验证；缺货、价签为补充展示。
- Skill：目标 9 个，其中 P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个。
- MCP：P0 固定 12 个函数（5 个查询、7 个受控动作）。
- 业务核心：`IncidentService` 是状态迁移和业务状态的唯一事实入口；本地 Demo 直接复用该核心，AgentTeams Worker 通过同一 MCP/Skill 契约接入。
- 证据等级：只有“代码存在、测试通过、Demo 真实调用”才标记为“已实现”；有状态外部系统替身标记为“模拟实现”；仅设计的能力标记为“规划”。

机器可读清单见 [`config/project-facts.json`](config/project-facts.json)，当前实现状态见 [`docs/实现状态矩阵.md`](docs/实现状态矩阵.md)。

## 冻结版本

| 项目 | 锁定值 | 当前证据 |
|---|---|---|
| AgentTeams | `v1.2.3`（commit `223ddc2`） | 官方 Release 与该 Tag 文档已核对 |
| Framework Manager Runtime | `qwenpaw` | 官方推荐值；待目标环境动态验证 |
| Worker Runtime | `qwenpaw` | 官方推荐值；待目标环境动态验证 |
| CRD | `agentteams.io/v1beta1` | 官方 `v1.2.3` 资源文档已核对 |
| Dashboard | `v1.2.4` | AgentTeams `v1.2.3` 默认配套版本 |
| Python | `>=3.11` | 本地核心保持标准库优先 |

AgentTeams 官方来源：

- [v1.2.3 Release](https://github.com/agentscope-ai/AgentTeams/releases/tag/v1.2.3)
- [Resource Management](https://github.com/agentscope-ai/AgentTeams/blob/v1.2.3/docs/usage/resource-management.md)
- [Worker 导入指南](https://github.com/agentscope-ai/AgentTeams/blob/v1.2.3/docs/zh-cn/usage/import-worker.md)

## 目标闭环

```text
发现异常
  -> 先停售/隔离，阻断风险扩散
  -> 形成 Top-K 根因假设和检查计划
  -> 策略判定、审批与受控执行
  -> Auditor 重新查询设备、批次、停售、审批和工单状态
  -> IncidentService 聚合为 RESOLVED
  -> 复盘完成后迁移为 CLOSED
```

设备恢复不等于商品安全，工单完成也不等于事件关闭。Executor 无权宣布成功；Auditor 只能提出验证结果和放行建议，最终状态由 `IncidentService` 按规则计算。

## 当前仓库结构

```text
config/                    冻结事实与版本化 Policy
schemas/                   Incident、MCP、Scenario Schema
src/dianxun/               业务核心、Skill、MCP 与本地 Adapter
demo/                      确定性场景与本地运行入口
agentteams/                AgentTeams 资源与 MCP Deployment
packages/dianxun-worker/   官方格式 Worker 包源目录
packages/dianxun-mcp/      MCP 独立镜像 Dockerfile
scripts/                   确定性构建与验证辅助脚本
dist/                      提交的 Worker ZIP 与 SHA-256
tests/                     单元、集成、契约与评测测试
evidence/                  可复现、脱敏的静态证据和说明
ppt/                       演示稿源文件与导出 PDF
```

上述结构是复赛目标结构；未出现的目录会随对应里程碑加入。不会用规划目录冒充已交付能力。

## 有状态核心与 MCP（M1）

Python 3.11+ 和 [uv](https://docs.astral.sh/uv/) 环境下：

```powershell
# 安装本项目（当前核心无第三方运行依赖）
uv sync

# 用固定 seed 重置 runtime.db
uv run dianxun state-init

# 注入压缩机故障场景；虚拟时钟固定，不依赖系统当前日期
uv run dianxun scenario-reset demo/state/scenarios/coldchain-compressor-failure.json

# 核对 12 个 P0 MCP 函数
uv run dianxun mcp-tools

# 直接查询场景注入后的同一 SQLite 业务状态
uv run dianxun mcp-call query_device_context `
  --arguments '{"device_id":"FROST-S03","facets":["temperature","health"]}'

# 启动 Streamable HTTP / JSON-RPC Adapter（默认 127.0.0.1:8080）
uv run dianxun-mcp
```

运行时数据库位于 `demo/state/runtime.db`，不会提交。重建 Seed 和执行 M1 回归：

```powershell
python 04-模拟数据生成脚本.py --check
$env:PYTHONPATH = "src"
python -W error::ResourceWarning -m unittest -v tests.test_stateful_core
```

M1 已通过 8 项回归验证：相同 seed 的业务快照哈希一致；全新数据库可自动建表；停售、批次处置、审批和工单写入后可通过查询函数看到；审批默认 `pending`；高预算维修未批准时不会执行；相同幂等键不会产生重复副作用。

## 冷柜五阶段闭环（M2）

本地 Adapter 与后续 AgentTeams Adapter 共用 `IncidentService`、Policy、Skill、MCP 和 Scenario。固定三条演示路径：

```powershell
# 场景 A：压缩机故障；审批通过；设备恢复；批次分别转移/报损；最终 CLOSED
uv run dianxun demo-run demo/state/scenarios/coldchain-compressor-failure.json

# 场景 D：维修审批超时；不创建工单；保持停售与隔离；停在 WAITING_EXTERNAL
uv run dianxun demo-run demo/state/scenarios/coldchain-approval-timeout.json

# 场景 E：设备恢复但商品仍不安全；Auditor 拒绝关闭；停在 WAITING_APPROVAL
uv run dianxun demo-run demo/state/scenarios/coldchain-device-recovered-goods-unsafe.json
```

也可执行 `python demo/run_coldchain.py` 跑场景 A。每条命令仅在实际终态与 Scenario 的 `expected_final_state` 一致时退出 `0`。

M2 的 6 个 P0 Skill 均已在 [`skills/`](skills/) 下提供独立 `SKILL.md`、manifest、输入/输出 Schema 与成功/失败样例。验证命令：

```powershell
$env:PYTHONPATH = "src"
python -W error::ResourceWarning -m unittest -v `
  tests.test_stateful_core tests.test_coldchain_workflow
uv run --with jsonschema python -m unittest -v tests.test_skill_contracts
```

当前共 15 项有状态核心/工作流回归和 1 项全量 Skill 契约门禁。场景 A 的 `CLOSED` 必须经过 Auditor 对设备、批次、停售、审批、工单和审计数据的重新查询；场景 E 证明“设备恢复”不会自动放行商品。

## AgentTeams 工程交付（M3 静态部分）

Worker 包已按官方 `v1.2.3` 结构重建，根目录包含 `manifest.json 1.0`、`config/` 和 6 个 P0 `skills/`；Manager/Worker 使用 `qwenpaw + qwen3.5-plus`，Worker YAML 的 `spec.package` 指向仓库中真实 ZIP。MCP 提供 PVC、单副本 Deployment 和 Service，镜像 build context 固定为仓库根目录。

```powershell
uv sync --group dev
uv run python scripts/build_worker_package.py
uv run python -m unittest -v tests.test_agentteams_artifacts
```

当前 Worker ZIP SHA-256 为 `d0689b24bd4610a0a29db16972e67133ae808663c4eeb4dcfe4f5040e7488747`，5 项 AgentTeams artifact 契约测试通过。本机还使用 AgentTeams 同款 `mcporter` 对本地 MCP 完成 12 工具发现和 `query_device_context` 真实调用。部署和动态烟测步骤见 [`agentteams/README.md`](agentteams/README.md)。

这只证明包、资源、MCP 传输和客户端兼容性；本机没有 Docker、Kubernetes 与 `agt`，因此 M3 的 Team Room、Worker 委派、平台运行状态和对应 Trace 仍标记为“外部待验证”。

## 改造前历史入口（非验收入口）

原仓库曾通过下面命令运行静态 CSV 三场景 Demo：

```powershell
$env:PYTHONPATH = "src"
python demo/run_demo.py
```

截至 2026-08-28，已提交 CSV 的时间锚点过期，原入口可能因“无异常”分支的旧状态机缺陷退出非零；审批和验证逻辑也不满足 P0 门禁。因此它只保留作迁移参考，不是冷柜验收入口。冷柜验收使用上一节 A/D/E 命令；缺货和价签独立入口将在 M4 做回归门禁。

## 文档索引

| 文档 | 内容 |
|---|---|
| [`01-作品简介-500字.md`](01-作品简介-500字.md) | 参赛作品简介 |
| [`02-方案PPT结构.md`](02-方案PPT结构.md) | 演示叙事与页级结构 |
| [`03-Skill九要素卡.md`](03-Skill九要素卡.md) | Skill 唯一清单与九要素 |
| [`04-模拟数据生成脚本.py`](04-模拟数据生成脚本.py) | 可重复数据生成入口 |
| [`05-MCP工具契约.md`](05-MCP工具契约.md) | MCP 函数契约 |
| [`06-Agent-Identity清单.md`](06-Agent-Identity清单.md) | 业务 Agent 身份、权限和边界 |
| [`07-多Agent协同设计.md`](07-多Agent协同设计.md) | 五阶段与官方八项要求映射 |
| [`08-复赛改造技术方案.md`](08-复赛改造技术方案.md) | 完整改造与验收方案 |

## 安全与证据边界

- 不提交真实 API Key、审批身份、照片原件或顾客数据。
- 所有 P0 写操作必须校验调用者、Policy、审批和幂等键，并写审计日志。
- 动态数据库和敏感运行日志不提交；只提交脱敏样例、生成命令和校验和。
- 未在真实 AgentTeams 环境跑通前，不声明 Team Room、Worker 委派或平台 Trace 已完成。
- 冷链阈值配置仅用于比赛 Demo，不替代企业 HACCP、设备说明书或当地监管要求。

## License

[MIT](LICENSE)
