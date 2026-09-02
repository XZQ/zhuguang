# 逐光｜Demo 视频脚本与证据清单

> 状态：录制脚本已完成；最终视频尚未在真实 AgentTeams 环境录制。本文用于保证录屏真实、可复现，不是视频完成证明。

## 1. 交付建议

录制一段不超过 8 分钟的视频，由正常闭环和失败分支两部分构成，目标成片 7 分 15 秒：

1. 正常闭环：场景 A 压缩机故障，约 4 分 20 秒；
2. 失败分支：场景 F 工单查询 partial（可补场景 D 审批超时），约 2 分 10 秒；
3. 片头、转场和结尾总计不超过 45 秒。

每段均保留屏幕时间、命令、incident_id、request_id 和关键业务状态。剪辑只能压缩等待时间，不能替换真实返回或补造平台消息。

## 2. 录制前门禁

```powershell
git status --short --branch
git rev-parse HEAD
uv sync --group dev
uv run dianxun evaluate
uv run dianxun ablation
uv run dianxun command-center
uv run --group dev python -W error::ResourceWarning -m unittest discover -v
uv run --group dev ruff check .
uv run --group dev ruff format --check .
uv run python scripts/generate_demo_data.py --check
uv run python scripts/build_worker_package.py
Get-FileHash dist/dianxun-worker.zip -Algorithm SHA256
```

预期：

- 工作区无非预期改动；
- 六场景 6/6；
- 全量测试 72 项发现：70 项通过、2 项 PolarDB 条件集成测试跳过；
- 四变体消融门禁通过，`evidence/m4/command-center.html` 已确定性生成；
- Ruff、格式、模拟数据和确定性 Worker 构建均通过；
- ZIP SHA-256 为 `3ee0f904974dda8b917693a1e73be3c16f77a50f23975c7de13621d8bbec2a0c`。

## 3. 视频一：正常闭环（场景 A）

### 镜头 1 - 任务与初始状态（20 秒）

展示：

- 场景文件名 `coldchain-compressor-failure.json`；
- 固定 anchor time；
- 设备、受影响批次、预期终态；
- 说明阈值来自比赛 Demo Policy。

话术：

> 这不是把一条温度告警交给多个 Agent 复述。系统要关闭的是一个包含设备和商品批次的 Incident。

### 镜头 2 - AgentTeams 动态委派（50 秒，外部环境必录）

在 Team Room 中提交固定任务并完整展示：

1. Manager 只委派 Orchestrator；
2. Orchestrator 委派 Sentry；
3. Sentry 回执带 incident_id、phase、Evidence refs；
4. Orchestrator 再按阶段委派 Diagnoser、Executor、Auditor。

不得用 YAML、PPT 动画或预制聊天截图替代这一镜头。若目标环境不可用，明确显示“本段未录制”，不要声称视频已完成。

### 镜头 3 - 先遏制后诊断（50 秒）

展示真实 MCP 返回：

- `query_device_context`；
- `apply_sales_hold`；
- `query_inventory_batches`；
- Top-K hypotheses。

同时保留服务端脱敏日志，证明调用 Bearer 已被映射为当前 Worker Actor；另做负向烟测，确认无 Token/错误 Token 被拒绝、错误角色受控动作返回 `FORBIDDEN`，成片只展示脱敏结果。不得显示 Token 或 `gatewayKey` 原文。

强调：

- 商品先停售/隔离；
- 当前 Top-1 是压缩机故障，但其他假设仍保留；
- 跨店正常不是确定根因。

### 镜头 4 - 审批、维修与批次处置（60 秒）

展示：

- 高预算工单的 pending approval；
- Human/真实审批入口批准；
- `create_workorder`；
- 每个批次独立 disposition；
- request_id、approval_id、workorder_id 和 audit_ref。

不得把 ScenarioEngine 的本地决定说成真实企业审批。外部视频应使用可认证人员入口。

### 镜头 5 - 两步放行与关闭（60 秒）

展示：

1. Auditor 首次重查设备、批次、停售、审批、工单；
2. 生成 release guard；
3. Executor 绑定审批和 verification 解除停售；
4. Auditor 第二次重查；
5. Incident 从 `RESOLVED` 进入 LEARN，再迁移 `CLOSED`。

核心话术：

> 设备恢复不等于商品安全；Executor 的成功回执不等于 Auditor 的业务验证。

### 镜头 6 - 证据与复盘（20 秒）

展示：

- Trace 中五阶段；
- Evidence 关键字段；
- review report 和 pending knowledge candidate；
- 明确 P1 知识工具默认关闭；若展示命中，必须同时展示候选、独立审核、脱敏通过和来源引用。

## 4. 视频第二部分：失败分支（场景 F）

### 镜头 1 - 注入 partial（20 秒）

展示场景定义中 `query_workorder` 的部分失败注入和预期终态。

### 镜头 2 - Auditor 独立查询（40 秒）

展示 Executor 已有工单动作记录，但 Auditor 查询得到 `status=partial`。强调动作 receipt 不能替代业务事实。

### 镜头 3 - 阻断关闭（40 秒）

展示：

- `partial_tools` 包含 `query_workorder`；
- sales hold 仍 active；
- incident 为 `CONTAINED`；
- work_status 为 `BLOCKED`；
- 没有错误 `CLOSED`。

### 镜头 4 - 可选审批超时对照（30 秒）

运行场景 D，展示：

- approval=timeout；
- 未创建受控维修工单；
- owner=regional_manager；
- 保持停售和隔离。

## 5. 本地复现命令

本地录制可先展示确定性业务结果，但不能替代 AgentTeams 镜头：

```powershell
uv run dianxun demo-run demo/state/scenarios/coldchain-compressor-failure.json
uv run dianxun demo-run demo/state/scenarios/coldchain-workorder-query-partial.json
uv run dianxun demo-run demo/state/scenarios/coldchain-approval-timeout.json
```

## 6. 最终证据清单

| 证据 | 正常视频 | 失败视频 | 来源 |
|---|---:|---:|---|
| Team Room 与真实委派 | 必须 | 必须 | AgentTeams 平台 |
| Worker 真实 MCP 调用 | 必须 | 必须 | 平台/MCP 日志 |
| Worker → MCP Actor 身份绑定 | 必须 | 必须 | 脱敏服务端日志与负向烟测；不得展示 Token |
| incident_id 与 request_id | 必须 | 必须 | 消息、MCP、Trace |
| 审批主体和状态 | 必须 | 可选 | 审批记录 |
| 设备与批次分别验证 | 必须 | 必须 | Auditor 查询 |
| 解除停售前后两次验证 | 必须 | 不适用 | verification attempts |
| partial/timeout 保持遏制 | 不适用 | 必须 | 业务状态 |
| 最终状态与 Scenario 预期一致 | 必须 | 必须 | IncidentCase |
| 模型/runtime 与用量披露 | 必须 | 必须 | 平台配置/账单；Key 必须遮挡，无法取得账单则标记未测量 |
| 敏感信息脱敏 | 必须 | 必须 | 成片复核 |

## 7. 成片验收

- 不出现 API Key、真实顾客数据、员工手机号、照片原件或内部地址。
- 不用旁白覆盖错误终态；画面中的状态必须与 narration 一致。
- 不把本地 ScenarioEngine 审批说成真实人工审批。
- 不把 YAML `state: Running` 说成集群实际 Running。
- 不把请求带 Bearer Header 说成身份已验证；必须有服务端拒绝与正确 Actor 审计证据。
- 不把本地 RAG/SQL 契约写成真实门店改善、PolarDB/OSS 已运行或生产可用；自动回滚仍不宣称实现。
- 不把本地 M4 结果说成 `qwen3.5-plus` 模型效果；模型 Key 必须遮挡，费用无真实账单时明确“未测量”。
- 当前 P0 为自定义可复用 Skill；只展示真实调用、版本和 Trace，不以云产品或 Skill 数量替代运行证据。
- 提交前由第二人对照本清单逐镜头复核。
