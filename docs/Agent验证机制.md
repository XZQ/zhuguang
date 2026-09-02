# Agent 结果验证机制

> 本文档说明逐光系统如何通过多层验证机制确保 Agent 输出正确性。

## 1. 验证体系概览

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent 结果验证体系                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: 结构化输出验证（Structured Output）                    │
│  ├── JSON Schema 校验                                          │
│  ├── 枚举值范围检查                                              │
│  └── 必填字段验证                                                │
│                                                                 │
│  Layer 2: 策略合规检查（Policy Check）                          │
│  ├── PolicyEngine.evaluate()                                   │
│  ├── 风险等级判定                                               │
│  └── 审批流触发                                                 │
│                                                                 │
│  Layer 3: 业务规则校验（Business Rules）                        │
│  ├── 事件边界约束（ScopeViolation）                             │
│  ├── 幂等性检查                                                 │
│  └── 状态一致性验证                                             │
│                                                                 │
│  Layer 4: 交叉验证（Cross Validation）                          │
│  ├── Diagnoser → Executor → Auditor 三方验证                    │
│  ├── Auditor release_guard 独立验证                             │
│  └── 知识库候选交叉确认                                          │
│                                                                 │
│  Layer 5: 人工审批（Human Approval）                            │
│  ├── 高风险操作必须人工审批                                      │
│  ├── 预算超限审批                                               │
│  └── 批次处置审批                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 核心验证代码

### 2.1 Skill 运行时输出契约

`src/dianxun/skills/contracts.py` 提供 `enforce_output_contract()` 装饰器。主线 Skill
函数返回后，装饰器把 dataclass、Enum、tuple 等转换为 JSON-compatible 视图，并按各
`skills/<name>/output.schema.json` 校验；缺字段、类型错误或额外字段会抛出
`SkillOutputContractError`，不会把漂移结构继续传入下一阶段。

当前已装饰六个 P0 入口：

- `detect_coldchain_event`
- `coldchain_risk_assess`
- `diagnose_coldchain_hypotheses`
- `dispatch_stateful_workorder`
- `outcome_verify`
- `review_incident`

`tests/test_skill_contracts.py` 同时校验成功/失败静态样例和运行时反例；这解决的是结构
契约，不证明 LLM 语义正确性。

### 2.2 Skill Registry 与 Trace 身份

`skills/registry.json` 将每个 P0 release 固定为 `name + version + digest`。运行时进入
`trace.span(..., kind="skill")` 时会解析 stable/canary release，并在 SQLite Span 中写入：

- `skill_name`、`skill_version`、`skill_digest`；
- `skill_channel`、`skill_registry_version`。

旧 Trace 数据库通过向后兼容的 `ALTER TABLE ADD COLUMN` 自动迁移；历史行保持空值，不伪造
版本身份。canary 按 Skill 名和 trace/incident ID 的 SHA-256 固定分桶，重试不会漂移。
AgentTeams 证据 Schema `1.1` 同时要求 Skill load 和每次工具调用携带 version/digest，校验器
会与当前 Worker provenance 逐项比对。真实平台是否产生这些字段仍以导出 Trace 为准。

### 2.3 策略合规检查

```python
# src/dianxun/domain/policy.py
key = f"{action_type}:{disposition}" if disposition else action_type
rule = policy["actions"].get(key)
if rule is None:
    return PolicyDecision(allowed=False, risk_level="L3", ...)

if actor not in rule["allowed_actors"]:
    return PolicyDecision(
        allowed=False,
        risk_level=rule["risk_level"],
        approval_required=False,
        ...
    )

approval_required = rule.get("approval_required", False)
threshold = rule.get("approval_required_above_amount")
if threshold is not None and amount is not None:
    approval_required = amount > threshold

return PolicyDecision(
    allowed=True,
    risk_level=rule["risk_level"],  # 当前策略使用 L1-L3
    approval_required=approval_required,
    approvers=rule["approvers"] if approval_required else (),
    ...
)
```

PolicyEngine 不按虚构的 L1-L5 数值区间自动推断；它按版本化策略中的 action、
`allowed_actors`、风险等级和审批条件逐项判断。

### 2.4 事件边界约束

```python
# src/dianxun/mcp/p0.py
class ScopeViolation(PermissionError):
    """操作超出事件边界时抛出"""

    pass


def _require_incident_scope(
    conn,
    *,
    incident_id: str,
    store_id: str | None = None,
    batch_ids: list[str] | None = None,
    device_id: str | None = None,
) -> None:
    """
    验证操作是否在事件边界内：
    1. 门店必须在事件关联门店内
    2. 批次必须在事件 affected_batches 内
    3. 设备必须在事件 affected_assets 内
    """
    # 实现细节见 p0.py:_require_incident_scope
```

### 2.5 交叉验证（Auditor 独立验证）

```python
# src/dianxun/mcp/p0.py - release_sales_hold
def release_sales_hold(self, *, verification_id: str, ...) -> dict:
    """
    释放销售冻结必须满足：
    1. 审批通过 (approval_id)
    2. Auditor 独立验证通过 (verification_id)
    3. 验证必须在冻结之后创建
    4. 验证必须覆盖所有目标批次
    """

    # 验证 Auditor 验证存在且有效
    verification = conn.execute("""
        SELECT * FROM verifications
        WHERE verification_id = ?
        AND result = 'passed'
        AND verifier = 'Auditor'
    """, (verification_id,)).fetchone()

    if verification is None:
        raise PermissionError("需要有效的 Auditor 验证")
```

## 3. 关键验证场景

### 3.1 冷柜失温场景验证链

```
Sentry 发现异常
    ↓ 报告设备上下文 (device_context)
Diagnoser 诊断
    ↓ 识别受污染批次 (affected_batches)
Executor 处置
    ↓ 申请销售冻结 (apply_sales_hold)
    ↓ 申请批次处置 (apply_batch_disposition)
    ↓ 创建维修工单 (create_workorder)
人工审批
    ↓ 食品安全 Owner 审批
Auditor 独立验证
    ↓ 验证批次已隔离 (release_guard)
    ↓ 验证设备已修复
知识沉淀
    ↓ Auditor 创建知识候选 (create_knowledge_candidate)
```

### 3.2 验证检查点

| 阶段 | 验证内容 | 失败处理 |
|------|----------|----------|
| Sentry | 温度数据有效性 | 标记为 partial quality |
| Diagnoser | 批次状态一致性 | 拒绝越界操作 |
| Executor | 策略合规 + 审批状态 | 阻止执行 |
| Auditor | 独立验证存在且有效 | 阻止释放 |
| 人工 | 审批决策 | 超时自动拒绝 |

## 4. 评委问题回答

### Q: 如何保证 Agent 结果正确性？

**A**: 通过五层验证体系：

1. **结构化输出**：六个 P0 主线 Skill 在实际返回路径校验 output JSON Schema
2. **策略合规**：PolicyEngine 评估风险等级和审批需求
3. **业务规则**：事件边界约束防止越界操作
4. **交叉验证**：Auditor 独立验证 Executor 的处置结果
5. **人工审批**：高风险操作必须人工确认

### Q: 是否有 formal verification？

**A**: 采用的是**工程化验证**而非形式化验证：

| 方法 | 说明 | 适用场景 |
|------|------|----------|
| 形式化验证 | 数学证明 | 关键安全系统 |
| LLM-as-Judge | AI 评估 | 开放域生成 |
| 工程化验证 | 确定性规则 | 业务系统 ✅ |

**理由**：冷链场景下，规则是明确的（温度阈值、批次状态），工程化验证比 LLM 评估更可靠、可解释、可测试。

### Q: 关键操作有误操作风险？

**A**: 有完善的保护机制：

```python
# 高风险操作示例：批次处置
if decision.approval_required:
    # 必须有有效审批才能执行
    self._require_approval(conn, approval_id=approval_id, ...)
else:
    # 低风险操作自动放行，但仍然在事务内
    self._ensure_new_action(conn, action_id=action_id, ...)

# 幂等性保证：重复调用返回相同结果
previous = store.idempotent_result(conn, idempotency_key=key)
if previous:
    return {**previous["data"], "idempotent_replay": True}
```

## 5. 测试覆盖

```bash
# 验证相关测试
tests/test_skill_contracts.py       # 六个 Skill 静态与运行时输出契约
tests/test_skill_registry.py        # Registry、SemVer、灰度、退役和 Trace 版本身份
tests/test_stateful_core.py         # SQLite/Policy/MCP 状态与聚合门
tests/test_adversarial_hardening.py # scope/审批/release guard/HTTP 边界
tests/test_coldchain_workflow.py    # 六场景端到端验证链
tests/test_knowledge_flywheel.py    # 知识人工发布边界
```

当前全量门禁发现 76 项，其中 74 通过、2 条 PolarDB 条件集成测试因无外部实例跳过。
六个 P0 Skill 运行时输出契约、12 个 P0 MCP registry/调用路径、六场景闭环和主要安全
边界均有自动化证据。仓库尚未生成正式行/分支覆盖率，也没有多线程/多进程争用压测或
真实 AgentTeams/PolarDB 运行证据，不能表述为“所有关键点 100% 覆盖”。
