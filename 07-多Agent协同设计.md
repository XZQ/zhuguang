# 多 Agent 协同设计

> 对应赛题 1.1 / 1.3:多 Agent 以 AgentTeams 为协同基点,说明 5 维度映射;说明 8 步端到端闭环。
> 本设计已落地为可运行代码(`src/dianxun/agents/orchestrator.py`)与 AgentTeams 部署配置(`agentteams/`)。

---

## 一、AgentTeams 五维度映射(赛题 1.1 必答)

赛题要求:多 Agent 设计必须以 AgentTeams 为协同基点,说明**角色编排、任务拆解、上下文传递、协同执行、状态追踪**如何映射到该框架能力。

### 1. 角色编排(Identity & Roles)

| AgentTeams 能力 | 店巡映射 | 落地 |
|---|---|---|
| Worker CR 的 `spec.identity` / `spec.soul` | 5 个 Agent 的身份声明(总控/巡检/诊断/处置/稽核) | `agentteams/workers/*.yaml` |
| Team CR 的 `workerMembers.role`(team_leader/worker) | Orchestrator = team_leader,其余 4 个 = worker | `agentteams/team.yaml` |
| 三层组织(Manager→Team Leader→Workers) | Manager 协调入口 → Team Leader 调度 → Worker 执行 | 见 06-Agent-Identity清单.md |
| 最小权限 + 凭证零暴露 | Worker 只持 consumer token,真实 Key 由 Higress 网关/KMS 管理 | MCP 经网关授权 |

**设计要点**:Manager 与 Team Leader 严格 delegation 边界——Manager 只与 Team Leader 通信,不绕过 Leader 直接调度 Worker。Team Leader 遵循 delegation-first,只拆解调度,不亲自执行领域任务。

### 2. 任务拆解(Task Decomposition)

| AgentTeams 能力 | 店巡映射 |
|---|---|
| Manager 把任务分发给 Team Leader | Manager 收到巡检指令 → 下发给 dianxun-patrol-team 的 Orchestrator |
| Team Leader 把任务拆为子任务 DAG | Orchestrator 把"巡检某区域"拆为:① 检测(→Sentry)② 逐异常诊断(→Diagnoser)③ 处置(→Executor)④ 验证(→Auditor)⑤ 复盘 |
| Team Leader 任务委派(delegation) | 每个子任务 @mention 对应 Worker,不自己执行 |

**代码实现**:`Orchestrator.run_task()` 内的 for 循环即任务拆解 DAG——按异常严重度排序,每个异常走"诊断→处置→验证"子链。

### 3. 上下文传递(Context Sharing)

| AgentTeams 能力 | 店巡映射 |
|---|---|
| Matrix Team Room 共享对话 | 所有 Agent 在同一 Team Room,异常清单/根因/处置状态全程可见 |
| MinIO 共享文件系统 | 任务上下文快照(TaskContext.snapshot)落共享存储,降 Token 消耗 |
| 上下文总线 | `src/dianxun/context_bus.py` 的 `ContextBus` + `TaskContext`,贯穿 anomalies→root_causes→actions→validation→review |

**共享上下文关键字段**:诊断结论、处置状态、审批意见跨 Agent 传递,而非点对点传参(解耦)。

### 4. 协同执行(Coordinated Execution)

| AgentTeams 能力 | 店巡映射 |
|---|---|
| Worker 间 @mention 协同 | Sentry 检出高危 → @Diagnoser;严重价签不一致 → @Executor 紧急;Executor 完工 → @Auditor 验证 |
| peerMentions(允许 Worker 间相互 @mention) | `team.yaml` 的 `peerMentions: true` |
| 协同执行序列 | 检测→诊断→处置→验证 的严格顺序由 Orchestrator 编排;并行场景(多店同时巡检)由 Manager 调度多 Team |
| 冲突仲裁 | 同店多异常按严重度排序;资源冲突时 Orchestrator 优先保障食安/合规类(严重价签>冷柜>缺货) |

**协同执行示例(冷柜超温)**:
1. Sentry @Orchestrator:"S03 冷柜超温,严重度高"
2. Orchestrator @Diagnoser:"诊断 S03"
3. Diagnoser @Orchestrator:"根因=压缩机故障,zscore=3.16 单店孤立"
4. Orchestrator @Executor:"处置 S03,维修>2000 需审批"
5. Executor @Auditor:"工单已派发,请 2h 后验证"
6. Auditor @Orchestrator:"温度已回基线,resolved"

### 5. 状态追踪(State Tracking)

| AgentTeams 能力 | 店巡映射 |
|---|---|
| 任务生命周期管理 | TaskContext 状态机 + transitions 审计记录 |
| 状态可见性 | 所有状态流转写入 Trace + 上下文,人类可随时进 Room 观察 |
| Controller 调和(reconcile) | Worker 容器状态 Running/Sleeping/Stopped;任务状态 created→...→closed |

**状态机**:
```
created → detecting → diagnosing → approving → executing → verifying → reviewing → closed
                                                              ↓ 失败
                                                         reopened → diagnosing(二次)
```
每个流转校验合法性(`_STATE_GRAPH`)并记录 actor/note/时间(可审计)。验证失败走 reopened 分支二次处置。

---

## 二、8 步端到端闭环(赛题 1.3 必答)

赛题要求:说明多 Agent 如何完成**任务输入→任务拆解→上下文传递→工具调用→结果验证→执行证据沉淀→审批与回滚→经验沉淀**。

### 步骤 1 · 任务输入
- **谁**:Sentry(接收) / Orchestrator(解析)
- **来源**:scheduled(每小时定时巡检)/ event(IoT 超温告警推送)/ manual(运营手动触发)
- **示例**:`demo/run_demo.py` 的 `orch.run_task("TASK-COLDCHAIN", scope={"store_ids":["S03","S07"],"data_sources":["iot"]}, trigger="event")`

### 步骤 2 · 任务拆解
- **谁**:Orchestrator(Team Leader)
- **动作**:按严重度排序异常,逐个生成子任务 DAG(诊断→处置→验证)
- **代码**:`orchestrator.py` 的 `for anom in ctx.anomalies` 循环

### 步骤 3 · 上下文传递
- **载体**:ContextBus + Matrix Team Room + MinIO
- **内容**:异常清单(anomalies)→ 根因报告(root_causes)→ 处置动作(actions)→ 验证结果(validation)
- **代码**:`context_bus.py` 的 `TaskContext` 各阶段字段

### 步骤 4 · 工具调用
- **谁**:各 Worker 调对应 Skill + MCP 工具
- **调用链**:Skill(能力抽象层)→ MCP 工具(连接层)→ 数据源(csv 模拟 POS/WMS/IoT)
- **示例**:Diagnoser 调 `cross-store-benchmark` → 内部调 `mcp.query_device_series` → 读 iot_coldchain.csv
- **代码**:`skills/*.py` 内部调 `dianxun.mcp.*`

### 步骤 5 · 结果验证
- **谁**:Auditor
- **方法**:复测核验(冷柜温度回基线/库存回升/价格三方一致)
- **失败处理**:触发 reopened 回 Diagnoser 二次诊断处置
- **代码**:`AuditorAgent.verify()`

### 步骤 6 · 执行证据沉淀
- **载体**:全链路 Trace(data/trace.db,生产 PolarDB)
- **覆盖**:Skill 调用 / MCP 工具 / Agent 编排 / LLM 推理(demo 用规则引擎代理)
- **语义**:对齐 OpenTelemetry GenAI;支持在线检索(`trace.query_trace`)与离线评估
- **代码**:`trace.py` 的 `span()` 自动埋点

### 步骤 7 · 审批与回滚
- **审批**:维修>2000 / 补货>5000 / 批量调价>20SKU → 经 `mcp-approval` 人工确认,超时降级为"仅通知"
- **回滚**:处置指令留快照(`apply_price_change` 的 change_id),验证失败调 `revert_price_change` 回退
- **安全边界**:付款环节绝不由 Agent 执行(只生成待付款单)
- **代码**:`mcp/approval.py` + `mcp/price.py`

### 步骤 8 · 经验沉淀
- **谁**:Auditor 调 `review-report` Skill
- **动作**:生成复盘报告 → 知识条目过质量门(≥0.6 入库,<0.6 待人工)→ 写知识库
- **飞轮**:下次 Diagnoser 的 RAG 检索命中历史经验 → 诊断更准 → "越巡越准"
- **Skill 迭代**:输出 Skill 更新建议(误报调阈值/处置失败补假设)
- **代码**:`skills/review_report.py` + `knowledge/store.py`

---

## 三、验证:8 步闭环已跑通

`demo/run_demo.py` 三场景全跑,每步有 Trace 证据:

| 步骤 | 场景1 冷柜超温 | 场景2 缺货 | 场景3 价签 |
|---|---|---|---|
| 1 输入 | event 触发 S03/S07 | scheduled S05 | scheduled S08 |
| 2 拆解 | 2异常逐个处理 | 6异常排序 | 1异常 |
| 3 上下文 | anomalies→root_causes→actions | 同 | 同 |
| 4 工具 | cross-store-benchmark zscore=3.16 | restock-order-gen | apply_price_change |
| 5 验证 | 温度 resolved | 库存 resolved | 价格 resolved |
| 6 证据 | 9 spans Trace | 15 spans | 5 spans |
| 7 审批 | 维修¥2500 审批 | 补货审批 | 改价审批 |
| 8 沉淀 | 2 知识入库 | 6 知识入库 | 1 知识入库 |

**累计**:29 个 Trace span、9 条知识条目入库(飞轮资产)。运行:`python3 demo/run_demo.py`
