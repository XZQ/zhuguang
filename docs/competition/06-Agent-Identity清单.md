# 逐光｜Agent Identity 清单

> 唯一统计口径：1 个 AgentTeams Framework Manager + 5 个业务 Agent。Orchestrator 是 5 个业务 Agent 之一，同时担任 Team Leader；不是额外的第 6 个业务 Agent。

## 1. 拓扑与证据边界

```text
AgentTeams Framework Manager
  └─ dianxun-patrol-team
       ├─ Orchestrator（Team Leader）
       ├─ Sentry
       ├─ Diagnoser
       ├─ Executor
       └─ Auditor
```

仓库已提供 Manager、Team、5 个 Worker YAML 和 Worker ZIP，且静态契约测试通过。当前机器未完成真实 AgentTeams Team Room 和 Worker 委派，因此本文件描述的是**已实现的身份/权限契约和本地逻辑角色**，不是动态运行证据。

目标 YAML 为 Manager/Worker 声明 `qwenpaw + qwen3.5-plus`；本地 Identity、76 项测试、M4 评测和消融对照不调用该模型。凭证只能由目标运行时注入，费用依提供商而定；替换兼容模型不改变下列身份与决策边界，但必须重做结构化回执、工具调用和安全回归。

## 2. 附录 A 标准字段清单

| Name | Role | Capabilities | Inputs | Outputs | Dependencies | Decision Boundary | Trace |
|---|---|---|---|---|---|---|---|
| `dianxun-manager` | Framework Manager | 接收 Admin 任务、选择 Team、汇总阻塞与结果；不能执行领域动作 | 用户任务、Team 状态、结构化回执 | Team 委派、进度和最终摘要 | AgentTeams Manager、`worker-management`、`dianxun-patrol-team` | 只做框架级协调；不穿透 Team 调 Worker，不判定业务成功 | Manager 状态、Team Room 委派消息、任务/消息 ID 和平台审计 |
| `dianxun-orchestrator` | Team Leader / Orchestrator | 拆解事故、委派 Worker、推进阶段、处理等待/超时/失败回开；不能替 Worker 调领域工具 | `incident_id`、scope、各 Worker 回执、Policy 状态 | phase 计划、owner/deadline、Evidence refs、事件摘要 | Manager、5 Worker、`IncidentService`、共享状态 | 可请求合法阶段迁移；不能绕过审批、直接改数据库终态或冒充 Worker | Team 内委派消息、状态迁移、phase span、`incident_id`/Trace ID |
| `dianxun-sentry` | Sentry / 只读巡检 | 检测失温、检查证据质量、分级并提出遏制；不能写业务状态或确认根因 | 门店/设备/时间窗、IoT 上下文、Policy | anomaly、severity、quality、containment request、Evidence refs | `anomaly-detect`、设备/批次查询 MCP、Orchestrator | L0 只读；停售由 Executor 执行，不得解除停售 | Skill/MCP span、request ID、Evidence source/time/hash、结构化回执 |
| `dianxun-diagnoser` | Diagnoser / 只读诊断 | 评估设备和商品风险、输出 Top-K 假设及反证；不能把相关性写成确定因果 | anomaly、设备/批次 Evidence、版本化 Policy | 风险评估、ranked hypotheses、证据缺口、检查计划 | `coldchain-risk-assess`、`rootcause-drilldown`、查询 MCP、Sentry 回执 | L0 只读；不能执行处置、伪造 RAG 或作最终食品安全决定 | 诊断 Skill span、证据引用、假设排序、缺失证据和回执 ID |
| `dianxun-executor` | Executor / 受控执行 | 停售隔离、发起审批、创建工单、执行获批处置；不能自批、自验、自行关闭 | Diagnoser 建议、Policy、approval、Auditor release guard | action/approval/workorder/hold refs、request ID、audit ref | `work-order-dispatch`、5 个写 MCP、Human 审批、Auditor | L1 预授权；L2 需批准；所有写要求幂等键，付款不在权限内 | MCP 请求/响应、审批票据、幂等键、audit ref、补偿记录 |
| `dianxun-auditor` | Auditor / 独立稽核 | 独立重查设备、批次、停售、审批和工单，生成 release guard 与复盘；不能执行写动作 | `incident_id`、期望状态、查询结果、动作和审批引用 | subject verifications、partial tools、结论、复盘和知识候选 | `outcome-verify`、`review-report`、5 类查询、`IncidentService` | L0 查询和验证记录；不得信任 Executor 回执代替重查，不得直接放行 | 独立查询 span、verification ID、Evidence refs、attempts、最终 Trace |

表中 8 个字段逐项对应参赛手册附录 A。`Human` / `ScenarioEngine` 是受限外部主体，不计入业务 Agent 数量，详见第 5 节。

## 3. Framework Manager（框架协调实体）

| 属性 | 定义 |
|---|---|
| 资源 | `agentteams/manager.yaml` |
| 身份 | AgentTeams 框架入口，不计入业务 Agent 数量 |
| 责任 | 接收 Admin 任务、委派给 `dianxun-patrol-team`、汇总阶段回执与阻塞 |
| 可用 Skill | AgentTeams 内置 `worker-management` |
| 领域 MCP | 无 |
| 禁止 | 穿透 Team 指挥领域 Worker、替代 Worker 调工具、根据聊天消息宣布业务成功 |

Manager 的 `state: Running` 是声明式期望状态；只有目标平台实际资源状态才能证明正在运行。

## 4. 五个业务 Agent

### A1. Orchestrator（Team Leader）

| 属性 | 定义 |
|---|---|
| 核心职责 | 事件拆解、角色委派、阶段推进、等待/超时管理、失败回开、向 Manager 汇报 |
| 关键输入 | incident_id、Scenario/业务输入、各 Worker 的结构化回执 |
| 关键输出 | phase 计划、owner/deadline/timeout_action、Evidence refs、事件摘要 |
| Skill / MCP | 不直接执行领域 Skill 或写 MCP；delegation-first |
| 权限 | 可通过 `IncidentService` 请求合法阶段迁移；不能直接改数据库终态 |
| 禁止 | 冒充 Sentry/Diagnoser/Executor/Auditor、绕过审批、把“消息已发送”当成功 |

### A2. Sentry（只读巡检）

| 属性 | 定义 |
|---|---|
| 核心职责 | 冷柜异常检测、证据质量检查、严重度分级、提出遏制请求 |
| 关键输入 | 设备/门店/时间窗、Policy、IoT 上下文 |
| 关键输出 | anomaly、severity、quality、partial、containment_request、Evidence refs |
| Skill | `anomaly-detect` |
| MCP | `query_device_context`；通过 Skill 获取关联批次上下文 |
| 权限 | L0 只读 |
| 禁止 | 写业务状态、确认根因、解除停售 |

### A3. Diagnoser（只读诊断）

| 属性 | 定义 |
|---|---|
| 核心职责 | 设备与商品风险分别评估，形成证据关联的 Top-K 根因假设和检查计划 |
| 关键输入 | anomaly、设备/批次 Evidence、版本化冷链 Policy |
| 关键输出 | batch risk、ranked hypotheses、支持/反证、证据缺口、建议动作 |
| Skill | `coldchain-risk-assess`、`rootcause-drilldown` |
| MCP | `query_device_context`、`query_inventory_batches` |
| 权限 | L0 只读 |
| 禁止 | 把相关性写成确定因果、伪造 RAG 命中、直接执行处置 |

### A4. Executor（受控执行）

| 属性 | 定义 |
|---|---|
| 核心职责 | 先行停售/隔离、发起审批、创建维修工单、执行获批批次处置和解除停售 |
| 关键输入 | Diagnoser 建议、Policy 决策、approval、Auditor release guard |
| 关键输出 | action/approval/workorder/hold refs、request_id、audit_ref、等待状态 |
| Skill | `work-order-dispatch` |
| MCP | 5 个 Executor 动作：`apply_sales_hold`、`release_sales_hold`、`apply_batch_disposition`、`create_workorder`、`create_approval` |
| 权限 | L1 预授权动作；L2 动作需批准；所有写操作要求幂等键 |
| 禁止 | 自批、自验、自行关闭事件、付款、未审批执行 L2 |

### A5. Auditor（独立稽核）

| 属性 | 定义 |
|---|---|
| 核心职责 | 独立重查设备和商品事实，生成 release guard，验证最终状态并复盘 |
| 关键输入 | incident_id、期望状态、MCP 查询结果、动作/审批/工单引用 |
| 关键输出 | subject verifications、partial tools、attempts、结论、复盘和知识候选 |
| Skill | `outcome-verify`、`review-report` |
| MCP | `query_sales_holds`、`query_workorder`、`query_approval`，并通过 Skill 重查设备和批次 |
| 权限 | L0 只读和领域验证记录；不直接执行受控业务写 |
| 禁止 | 信任 Executor 回执代替重查、直接解除停售、把候选知识写成已发布 RAG |

## 5. Human / ScenarioEngine（外部可信主体）

它们不是业务 Agent，但拥有两个受限入口：

- `decide_approval`：批准、拒绝或超时；
- `record_manual_evidence`：记录测温、照片 URI/哈希或人工说明。

本地 Demo 由 ScenarioEngine 确定性模拟人工输入，只验证等待与审批语义。真实部署必须接入可认证人员、排班、SLA、委托关系和不可抵赖审计。

## 6. 权限矩阵

| 能力 | Manager | Orchestrator | Sentry | Diagnoser | Executor | Auditor | Human/ScenarioEngine |
|---|---:|---:|---:|---:|---:|---:|---:|
| Team/任务委派 | 是 | Team 内 | 否 | 否 | 否 | 否 | 否 |
| 设备/批次查询 | 否 | 经委派 | 是 | 是 | 按动作需要 | 是 | 可提供证据 |
| 先行停售/隔离 | 否 | 仅委派 | 否 | 否 | 是 | 否 | 否 |
| 创建审批/工单 | 否 | 仅委派 | 否 | 否 | 是 | 否 | 否 |
| 决定审批 | 否 | 否 | 否 | 否 | 否 | 否 | 是 |
| 批次处置/解除停售 | 否 | 仅委派 | 否 | 否 | 经审批 | 否 | 否 |
| 独立业务验证 | 否 | 否 | 否 | 否 | 否 | 是 | 可补人工证据 |
| 迁移事件阶段 | 否 | 经 IncidentService | 否 | 否 | 否 | 提供依据 | 否 |
| 付款 | 否 | 否 | 否 | 否 | 否 | 否 | 不在本系统 |

此矩阵描述的是业务授权，不是部署身份已经可信。当前 HTTP Adapter 只有在 `MCP_ACTOR_TOKENS_JSON` 将 Bearer Token 映射为 Actor 时，才能把网络调用者绑定到这里的角色；共享 `MCP_TOKEN` 只能认证请求，不能证明角色。AgentTeams 动态 `gatewayKey` 的映射与负向鉴权烟测仍为外部待验证。

## 7. 协作不变量

1. 先遏制，后追求完整诊断。
2. Diagnoser 输出 Top-K，不把证据不足包装成确定根因。
3. Executor 的动作回执不是验证证据。
4. Auditor 必须重查；关键查询 partial 时不能关闭。
5. 设备恢复和商品批次安全分别判定。
6. 只有 `IncidentService` 可聚合 `RESOLVED` 并在 LEARN 后迁移 `CLOSED`。
7. AgentTeams 静态资源、LocalDemoAdapter 或本地 MCP 烟测都不能替代真实 Worker 委派证据。
