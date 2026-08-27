# MCP 工具连接层接口契约

> P0 唯一口径：12 个有状态 MCP 函数，包括 5 个查询与 7 个受控动作。当前实现位于 `src/dianxun/mcp/p0.py`，协议 Adapter 位于 `src/dianxun/mcp/server.py`。

## 1. 实现边界

当前 Server 通过 Streamable HTTP / JSON-RPC 暴露工具，后端是同一 SQLite 业务世界。它用于比赛 Demo 和确定性评测，不是已接入的真实 POS、WMS、IoT、审批或维修商 API。

所有响应使用统一 Envelope：

```json
{
  "request_id": "req-...",
  "status": "ok | partial | error",
  "data": {},
  "evidence": [],
  "error": null,
  "meta": {
    "source": "stateful-mock",
    "observed_at": "ISO-8601",
    "collected_at": "ISO-8601"
  }
}
```

关键语义：

- `ok`：请求成功，不代表业务事件已关闭。
- `partial`：返回可用子结果和缺失项；调用方必须显式降级，关键验证不得据此关闭。
- `error`：包含稳定错误码，不用空数组伪装成功。
- 查询与动作都返回 `request_id`；Evidence 可通过 `incident_id` 关联事件。
- 每次写操作必须携带 `idempotency_key`，并进入审计记录。

## 2. 五个查询函数

| 函数 | 默认调用者 | 主要输入 | 返回事实 | partial 处理 |
|---|---|---|---|---|
| `query_device_context` | Sentry | device/store/incident、facets、window | 温度、健康、门、电源、维护上下文 | 标记缺失 facet，不能将可疑传感器直接当商品安全依据 |
| `query_inventory_batches` | Diagnoser | device/store/batch/incident | 设备关联批次、存储策略、处置和安全状态 | 缺批次时转人工，不允许默认安全 |
| `query_sales_holds` | Auditor | incident/batch/status | 当前停售及解除状态 | 无法确认时保持停售 |
| `query_workorder` | Auditor | workorder/action/incident | 工单与维修商状态 | `partial` 会阻断关闭并触发回开/等待 |
| `query_approval` | Auditor | approval/action/incident | 审批状态、决定人和原因 | 未批准或超时不能执行受控动作 |

查询函数只读，但仍记录请求 ID 和 Evidence；它们的返回值是业务验证依据，不是 Agent 的自然语言复述。

## 3. 七个受控动作

| 函数 | 允许调用者 | 风险与前置条件 | 幂等副作用 |
|---|---|---|---|
| `apply_sales_hold` | Executor | L1；先行遏制，可不等待维修诊断 | 同一批次停售只创建一次 |
| `release_sales_hold` | Executor | L2；必须绑定已批准审批与通过的 Auditor verification | 同一 hold 只解除一次 |
| `apply_batch_disposition` | Executor | quarantine 为 L1；transfer/release/dispose 为 L2 且需审批 | 批次状态按 action/idempotency 去重 |
| `create_workorder` | Executor | 预算大于 2000 的 Demo Policy 需审批 | 同一 action 只创建一个工单 |
| `create_approval` | Executor | 只创建 pending 审批，不代表批准 | 同一 action 只创建一个审批 |
| `decide_approval` | Human / ScenarioEngine | Agent 无权调用；仅 approved/rejected/timeout | 决策按幂等键去重并记录决定人 |
| `record_manual_evidence` | Human / ScenarioEngine | 记录测温、照片 URI/哈希或人工说明；不得嵌入敏感原件 | 相同证据动作不重复写入 |

`decide_approval` 和 `record_manual_evidence` 的调用身份必须由可信入口注入。HTTP Adapter 不接受客户端用普通参数伪造 Human。

## 4. Policy 与权限

版本化 Demo Policy：`config/policies/coldchain-demo.v1.json`。

| 级别 | 含义 | 当前例子 |
|---|---|---|
| L0 | 只读 | 五个查询 |
| L1 | 预授权、可逆或先行遏制 | apply_sales_hold、quarantined、低预算工单 |
| L2 | 必须人工审批 | transfer/release/dispose、解除停售、高预算工单 |
| L3 | 任何 Agent 禁止 | payment |

解除停售还有额外 release guard：

1. 商品批次已经分别处置；
2. Auditor 对设备、批次、停售等事实完成验证；
3. 对应审批状态为 approved；
4. Executor 执行解除停售；
5. Auditor 再次重查最终状态。

因此“设备恢复”“工单 done”或“Executor 返回成功”均不足以放行商品。

## 5. 幂等、审计与错误语义

### 幂等

- 所有动作必须提供非空 `idempotency_key`。
- 同键同请求返回同一业务结果，不产生第二个 hold、approval 或 workorder。
- 同键不同语义必须拒绝，不能静默覆盖历史动作。

### 审计

审计至少记录：

- `incident_id`、`action_id`、`request_id`；
- actor、tool_name、Policy 决策和 approval_id；
- 脱敏后的请求/响应摘要；
- created_at/updated_at；
- 成功、拒绝、partial 或 error 状态。

### 稳定错误类别

| 类别 | 示例 | 调用方行为 |
|---|---|---|
| `INVALID_ARGUMENT` | 缺少幂等键、Schema 不合法 | 不重试，修正请求 |
| `FORBIDDEN` | 调用者越权、伪造 Human | 记录安全事件，不降级绕过 |
| `APPROVAL_REQUIRED` | 受控动作缺少审批 | 创建/查询审批并等待 |
| `APPROVAL_INVALID` | 审批不存在、未批准或与动作不匹配 | 停止执行并重查审批 |
| `NOT_FOUND` | 设备、审批等目标不存在 | 重新取上下文或转人工 |
| `INVALID_STATE` | 幂等冲突或业务状态不允许 | 重读业务状态后重新规划 |
| Envelope `status=partial` | 外部查询只有部分结果 | 保持遏制，禁止关闭 |

当前 Adapter 未实现生产级 OAuth、熔断器和分布式重试；这些属于真实系统接入层，文档不得写成已交付。

## 6. 直接验证

```powershell
uv run dianxun state-init
uv run dianxun scenario-reset demo/state/scenarios/coldchain-compressor-failure.json
uv run dianxun mcp-tools
uv run dianxun mcp-call query_device_context --arguments '{"device_id":"FROST-S03"}'
uv run --group dev python -m unittest -v tests.test_stateful_core
```

`mcp-tools` 的输出必须与 `config/project-facts.json` 中 12 个名称完全一致。新增、删除或重命名函数时，必须同步 Server registry、Schema、测试、README、本文和 Worker Skill。

## 7. 生产凭证与替换边界

- 当前 Stateful Mock 只验证契约和状态语义；生产 Adapter 必须按企业系统分别实现 OAuth/mTLS、服务身份、最小权限、超时、重试、熔断和对账。
- POS/WMS/IoT/审批/维修商凭证以及模型 Key 都只能由运行时 Secret、环境变量或外部密钥系统注入，不得出现在 MCP 参数、YAML、ZIP、日志、Trace、测试 fixture 或提交记录中。
- 模型提供商不是 MCP 契约的一部分。替换 `qwen3.5-plus` 或接入网关时，12 个函数的 Schema、权限、幂等和审计语义保持稳定；仍需重跑 Agent 结构化输出与工具调用回归。
