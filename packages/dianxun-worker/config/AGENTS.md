# 店巡 Team 运行规则

## 五阶段闭环

1. `DETECT_CONTAIN`：Sentry 收集当前证据并提出遏制请求；Orchestrator 委派 Executor 执行允许的停售和隔离。
2. `DIAGNOSE_DECIDE`：Diagnoser 输出 Top-K 假设、证据矩阵和下一步检查；Orchestrator 根据 Policy 决定是否进入审批。
3. `EXECUTE`：Executor 只执行已授权动作；审批 pending、rejected 或 timeout 时保持遏制并报告等待所有者和截止时间。
4. `VERIFY`：Auditor 重新调用查询工具，分别验证设备、批次、停售、审批和工单，不能复用 Executor 的布尔结论。
5. `LEARN`：Auditor 生成与本事故关联的复盘；只有全部安全门满足时 Orchestrator 才能汇总为已关闭。

## 委派边界

- Manager 只把任务交给 Team Leader；Team Leader 只调度和汇总，不替 Worker 执行业务动作。
- Sentry、Diagnoser、Executor、Auditor 完成任务后在真实 Team Room 中回复 Team Leader。
- Worker 之间需要协同时通过 Team Leader 或获准的 peer mention 传递结构化引用。
- Incident、Action、Approval、Evidence 和 Trace 均传递 ID 与摘要，不复制或虚构整份外部数据。
- 每次 MCP 调用携带同一 `runtime_trace_id`、`incident_id` 和唯一 `request_id`，但不得在消息或 Trace 中包含 Token。

## 结构化交接

每次回复至少包含：`incident_id`、`phase`、`status`、`summary`、`evidence_refs`、`next_owner`、`blocking_reason`、`context_version`、`assignment_id`、`attempt`、`lease_expires_at` 和 `checkpoint_ref`。调用 MCP 时保留返回的 `request_id` 与 `audit_ref`。

## 库存范围协议 v2

- 先读取 `runtime_snapshot` 的 `incident.scope_version`、范围快照和恢复 generation；`scope_version` 与 `context.version` 不可互换。
- 对已启用 v2 的事件，所有 runtime 推进/修改请求携带 `expected_scope_version`，继续保留原 `expected_version`（Context CAS）。`runtime_tool.arguments` 内的 MCP 写请求也携带同一 `expected_scope_version`。不默认填当前版本来重试陈旧任务。
- `runtime_open` 创建 v2 新事件使用 `expected_scope_version=0`；已存在事件必须先读快照，不把打开接口当成重置操作。
- 版本冲突先读快照并核对 assignment/generation；范围修订失效的旧租约、旧输出和 checkpoint 不能推进新轮次。`historical_replay=true` 仅是历史回执，不是本轮新动作成功。
- 批次处置/解除停售申请审批填写明确 `target_batch_ids`，不夹带设备目标；维修审批只填 `target_device_ids=[device_id]`，批次列表留空或省略。数量、位置、规则由服务器生成快照，不能从 subject 文案推断授权。新增或拆分子批不得借父批批准/凭证放行。
- 补货、移柜、拆批及旧事件库存对账只由同门店 Human 经 `runtime_revise_scope` / `runtime_reconcile_scope` 提交来源引用、稳定 `change_id` 和所有关联开放事件的 `expected_versions`；Agent 只报告差异，不虚构 WMS/POS 事实。
- CONTAIN 仅处理当前 `containment_required`；查询原工单及 `context.recovery.operations` 后恢复，不因 generation 增加就重新发工单。未知执行结果先回查；未取得渠道回执不得宣称已经遏制。
- Auditor 汇总当前完整叶子批次范围；旧范围成功不等于当前完整核验通过。历史已完成动作和回执保留，不修改过去决定来掩盖范围变化。
- 放行使用本轮 Auditor 返回的 verification_id；v2 独立核验编号包含 `:scope:<scope_version>`，不得硬编码旧的 `<incident_id>:verify:release_guard`。

## 协调生命周期

- Orchestrator 按租户创建有 TTL 的 Context；Context 只保存协调元数据、assignment、checkpoint 和 Evidence 引用，不得直接写业务终态。
- Worker 领取 assignment 后必须回传心跳；心跳只能延长自己的有效 lease，过期后不得继续提交结果。
- lease 未过期时禁止重派；超时重派必须记录旧 assignment 为 `expired`，新 assignment 的 `attempt + 1` 并引用唯一 predecessor。
- 每个阶段成功回执与 checkpoint 必须在同一个 `context_version` 条件提交中完成；版本冲突时重新读取，不覆盖较新的结果。
- Worker 或 Orchestrator 重启后，从持久化 checkpoint 计算下一阶段，禁止重做已完成的外部副作用。
- Context 过期后拒绝活跃读写；清理默认只删除终态过期记录。任何自动清理 active Context 都必须显式授权并有审计。
- Context 的 `completed` 只表示协调阶段完成；业务 `RESOLVED/CLOSED` 仍只能由 `IncidentService` 聚合。

## MCP

- 使用名为 `dianxun-mcp` 的 Streamable HTTP Server。
- 只调用当前角色获准的工具；写操作必须携带唯一 `idempotency_key`。
- 工具返回 `partial=true` 或错误时，不得将阶段误标为成功。
- P1 知识工具启用时，Diagnoser 只能检索 `published + redaction passed` 条目；Auditor 只能创建 pending 候选，候选发布必须由绑定的人类审核身份完成。
