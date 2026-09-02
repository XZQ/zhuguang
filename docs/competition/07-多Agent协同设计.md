# 逐光｜多 Agent 协同设计

> 本文把两套视角分开：**五阶段**用于讲业务闭环，**八项要求**用于横向检查协同证据。二者不是两条流程；八项要求分布在五阶段之中。

## 1. 协同基点与当前状态

目标运行基点为 AgentTeams `v1.2.3`：

- 1 个 Framework Manager；
- 1 个 Team：`dianxun-patrol-team`；
- 5 个业务 Agent，其中 Orchestrator 是 Team Leader，另外 4 个为领域 Worker；
- 6 个 P0 Skill 进入确定性 Worker ZIP；
- Worker 通过 `dianxun-mcp` 访问同一有状态业务世界。
- Manager/Worker YAML 声明 `qwenpaw + qwen3.5-plus`；本地确定性 Demo、72 项测试、M4 评测和消融对照不调用 LLM。

仓库已完成 YAML、Worker ZIP、MCP Deployment 和本地兼容烟测。真实 Team Room、Worker 委派、Worker → MCP 身份绑定和平台 Trace 仍是外部待验证，所以下文分别标注“仓库内证据”和“平台待取证”。

## 2. AgentTeams 五维映射

| 维度 | 店巡映射 | 仓库内证据 | 平台待取证 |
|---|---|---|---|
| 角色编排 | Manager → Team Leader → Sentry/Diagnoser/Executor/Auditor | `agentteams/*.yaml`、Identity/Skill/MCP 声明 | 资源实际 Running、Room 成员 |
| 任务拆解 | Orchestrator 按五阶段分派结构化子任务 | Worker 行为契约、LocalDemo 阶段输出 | Orchestrator 的真实 @委派消息 |
| 上下文传递 | 传 incident_id、phase、Evidence refs、request_id，不复制大原始数据 | IncidentCase/Evidence Schema、MCP Envelope | 同一任务跨 Worker 的消息链 |
| 协同执行 | 读、诊断、写、验证职责分离；人工审批可等待/超时 | Policy、ScenarioEngine、六场景测试 | Worker 调 MCP 和人工节点的同一平台 Trace |
| 状态追踪 | phase + incident_status + work_status + 批次/审批/工单实体状态 | StateStore、IncidentService、Trace | 平台任务状态与业务状态关联截图/导出 |

## 3. 五阶段业务闭环

### 阶段 1：DETECT_CONTAIN - 发现与遏制

1. Sentry 调用 `anomaly-detect`，查询设备上下文并检查 Evidence 质量。
2. Orchestrator 建立 IncidentCase 和结构化上下文。
3. 风险成立或证据不足时，立即委派 Executor 对关联商品停售、隔离。
4. 遏制动作写入有状态 MCP，随后可重查。

关键原则：遏制是可逆/受控的风险阻断，不需要等到根因完全确定。

### 阶段 2：DIAGNOSE_DECIDE - 诊断与决策

1. Diagnoser 分别评估设备异常和商品批次暴露。
2. `rootcause-drilldown` 输出 Top-K 假设、支持/反证证据和下一步检查。
3. 当前 Top-1 可以作为维修工单 fault，但不是永久真相。
4. Policy 对维修预算、商品处置和放行逐动作判定权限与审批。

关键原则：规则负责确定性约束，Agent 负责证据收集、不确定性表达和任务协调。

### 阶段 3：EXECUTE - 处置执行

1. Executor 创建必要审批；低预算工单不创建无意义审批。
2. Human/ScenarioEngine 决定 approved/rejected/timeout。
3. 获批后创建幂等工单、执行各批次处置；未获批则保持遏制并记录 owner/deadline/timeout_action。
4. 维修商/ScenarioEngine 推进外部状态，Agent 无权伪造“done”。

关键原则：审批是一个真实等待状态，不是同步布尔值；动作成功不等于事件成功。

### 阶段 4：VERIFY - 独立验证

1. Auditor 重新查询设备、批次、停售、审批和工单。
2. 首次通过可生成 `release_guard`，但 Auditor 不直接解除停售。
3. Executor 绑定审批和 verification 执行解除停售。
4. Auditor 再次重查最终状态。
5. 任一关键查询 `partial`、商品仍不安全或业务事实冲突时，保持遏制并回开/阻断关闭。

关键原则：设备恢复、商品安全和停售解除是三个不同事实。

### 阶段 5：LEARN - 复盘演进

1. `IncidentService` 在独立验证通过后聚合为 `RESOLVED`。
2. Auditor 调用 `review-report` 生成时间线、批次关联、改进项和待审知识候选。
3. Orchestrator 只有在 LEARN 完成后请求迁移 `CLOSED`。
4. 知识候选只有经独立人工审核和脱敏通过后才进入可选检索；当前不宣称真实门店改善率，也不自动修改 Skill/Policy。

## 4. 八项要求如何嵌入五阶段

| 官方检查项 | 主要阶段 | 当前实现证据 |
|---|---|---|
| 任务输入 | 阶段 1 | Scenario Schema、CLI、固定 seed |
| 任务拆解 | 阶段 1～3 | Orchestrator 阶段输出与 AgentTeams Team Leader 契约 |
| 上下文传递 | 全阶段 | IncidentCase、Evidence refs、request_id、ContextBus |
| 工具调用 | 阶段 1～4 | 12 个 MCP 函数、Envelope、审计 |
| 结果验证 | 阶段 4 | outcome-verify、Auditor 重查、两次放行验证 |
| 执行证据沉淀 | 全阶段 | Evidence、audit、隔离 Trace、M4 report |
| 审批与回滚/补偿 | 阶段 3～4 | pending/timeout、审批绑定、停售保持、reopen；通用自动回滚未声明已实现 |
| 经验沉淀 | 阶段 5 | review-report、pending knowledge candidates、可选审核/检索；真实门店基线外部待验证 |

因此：

- “五阶段”回答业务怎样从异常走到安全关闭；
- “八项要求”回答这条链是否具备输入、工具、证据、审批、验证和学习；
- 同一 Evidence 可以同时证明一个业务阶段和一个横向要求，但不能因为文档有映射就宣称平台已运行。

## 5. 六个确定性场景

| ID | 场景 | 协同与安全重点 | 终态 |
|---|---|---|---|
| A | 压缩机故障 | Top-1 工单、审批、商品分批处置、双重验证 | CLOSED |
| B | 传感器误报 | 可疑数据降权、人工证据、两次验证后才解除停售 | CLOSED |
| C | 门未关闭 | 现场证据纠正假设；关门后仍评估商品 | CLOSED |
| D | 审批超时 | 不创建受控工单，owner 升级区域负责人 | CONTAINED / WAITING_EXTERNAL |
| E | 设备恢复但商品不安全 | 拒绝关闭，回到商品处置审批 | CONTAINED / WAITING_APPROVAL |
| F | 工单查询 partial | Auditor 不信动作回执，阻断关闭 | CONTAINED / BLOCKED |

运行：

```powershell
uv run dianxun evaluate
```

当前本地结果：

- 场景、Top-1、Top-3 均 6/6；
- Evidence 关键字段 45/45；
- 适用阶段 Trace 26/26；
- 全量发现 72 项自动化测试：70 项通过，2 项外部 PolarDB 条件测试跳过；
- 四变体消融门禁通过：`no_auditor` 验证缺独立审计时安全阻断，`single_agent` 验证角色写入边界，`rule_only` 暴露诊断退化；
- 事故指挥台将六场景交接链、设备/商品状态、审批、审计和 Auditor 判决同屏呈现；
- 未授权写、未审批受控写、错误放行、错误关闭和重复副作用均为 0。

这些指标来自有状态 Mock 和隔离数据库；不能换写成真实门店经营效果。

## 6. 失败、等待和回开

```text
正常：
DETECT_CONTAIN -> DIAGNOSE_DECIDE -> EXECUTE -> VERIFY -> LEARN
      CONTAINED      CONTAINED        MITIGATING     RESOLVED   CLOSED

审批超时：
EXECUTE + WAITING_EXTERNAL + owner=regional_manager
  └─ 保持停售/隔离，不创建未获批工单

商品仍不安全：
VERIFY -> EXECUTE + WAITING_APPROVAL
  └─ 设备可 recovered，但批次和停售保持受控

工具 partial：
VERIFY -> EXECUTE + BLOCKED
  └─ 记录 partial_tools，保持遏制，等待重试/人工
```

状态迁移必须通过 `IncidentService`。Executor 无权设置 `RESOLVED/CLOSED`；Auditor 只提供验证事实；Orchestrator 只请求合法迁移。

## 7. 上下文和 Evidence 契约

Agent 之间只传递最小必要引用：

```json
{
  "incident_id": "INC-...",
  "phase": "VERIFY",
  "owner": "Auditor",
  "evidence_refs": ["EV-..."],
  "request_ids": ["req-..."],
  "approval_refs": ["APR-..."],
  "workorder_refs": ["WO-..."],
  "expected_output": "verification_result"
}
```

每条关键 Evidence 包含：

- `incident_id`；
- `source`；
- `observed_at` 与 `collected_at`；
- `request_id`；
- `quality`；
- `immutable_hash`。

照片和原始附件只保存 URI、哈希和脱敏摘要，不进入仓库证据。

## 8. 动态 AgentTeams 验收

在目标环境中，只有同一 incident 同时具备以下证据，才可把 M3 从“外部待验证”改为“已实现”：

1. Manager 只委派 Orchestrator；
2. Orchestrator 分别委派四个领域 Worker；
3. Worker 回执包含 incident_id、phase、Evidence refs 和 request_id；
4. 至少一次真实 Worker → `dianxun-mcp` 调用；
5. 审批等待/超时在 Room 中真实可见；
6. Auditor 独立查询，而非复述 Executor；
7. AgentTeams 资源和 MCP Kubernetes 资源为实际 Running；
8. Worker 的动态 Bearer 身份由可信网关或 MCP 映射为正确 Actor，并验证匿名、错误 Token 和越权角色均被拒绝；
9. 平台消息、业务状态、MCP 返回和 Trace 可关联到同一 incident。

静态 YAML、Worker ZIP 校验、本地 LocalDemo 和 `mcporter` 兼容烟测均不能单独满足这 9 项。尤其不能把 AgentTeams 自动发送 Bearer Header 等同于 MCP 已验证该身份；必须取得服务端拒绝证据和审计 Actor 证据。

## 9. 模型与 Skill 生态边界

- `qwen3.5-plus` 只负责目标 AgentTeams 中的任务拆解、结构化协作和工具编排；Policy、权限、幂等和事件终态仍由确定性业务核心约束。
- 模型凭证仅运行时注入，费用随提供商和实际 Token/资源用量变化；当前没有真实平台账单。兼容模型替换后需重跑结构化输出、工具调用、延迟、费用和安全回归。
- 当前 P0 均为自定义可复用 Skill。官网与手册 FAQ 对“阿里云官方用云 Skills”的措辞冲突尚待组委会确认；取得书面结论或真实官方 Skill 调用证据前，不标记为完全满足。
