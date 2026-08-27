# 店巡 Agent（筑光）

面向连锁便利店的多 Agent 异常闭环系统。复赛版本采用“一主两辅”：以冷柜失温作为首要完整验证场景，缺货与价签异常保留为补充展示和独立回归入口。

> 当前状态：M0、M1 已完成，M2～M5 正在按 [`08-复赛改造技术方案.md`](08-复赛改造技术方案.md) 实施。有状态 SQLite 核心和 12 个 P0 MCP 函数已通过本地测试；五阶段 Agent 闭环与真实 AgentTeams 协同仍未完成，不能提前作为完成证据。

## 唯一事实口径

- 拓扑：1 个 AgentTeams Framework Manager + 5 个业务 Agent（Orchestrator、Sentry、Diagnoser、Executor、Auditor）。
- 业务流程：发现与遏制、诊断与决策、处置执行、独立验证、复盘演进。
- 场景：冷柜失温为首要完整验证；缺货、价签为补充展示。
- Skill：目标 9 个，其中 P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个。
- MCP：P0 固定 12 个函数（5 个查询、7 个受控动作）。
- 业务核心：`IncidentService` 是状态迁移和业务状态的唯一事实入口；本地 Demo 与 AgentTeams 都是 Adapter。
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

## 改造前历史入口（非验收入口）

原仓库曾通过下面命令运行静态 CSV 三场景 Demo：

```powershell
$env:PYTHONPATH = "src"
python demo/run_demo.py
```

截至 2026-08-28，已提交 CSV 的时间锚点过期，原入口可能因“无异常”分支的旧状态机缺陷退出非零；审批和验证逻辑也不满足 P0 门禁。因此它只保留作迁移参考，不是当前支持路径。M1 的支持路径是上一节的 SQLite 与 MCP 命令；M2 会提供场景 A、D、E 的五阶段入口。

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
