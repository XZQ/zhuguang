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

### 2.1 策略合规检查

```python
# src/dianxun/domain/policy.py
class PolicyEngine:
    """策略引擎：评估操作是否合规"""

    def evaluate(
        self,
        actor: str,
        action_type: str,
        amount: float | None = None,
        disposition: str | None = None,
    ) -> PolicyDecision:
        """
        评估结果包含：
        - allowed: 是否允许执行
        - risk_level: 风险等级 (L1-L5)
        - approval_required: 是否需要审批
        - approvers: 审批人列表
        - reason: 决策原因
        """

        # L1: 低风险，自动放行
        if risk_level <= 1:
            return PolicyDecision(allowed=True, ...)

        # L2-L3: 中风险，需要审批
        if risk_level <= 3:
            return PolicyDecision(allowed=True, approval_required=True, ...)

        # L4-L5: 高风险，审批或拒绝
        return PolicyDecision(allowed=False, reason="高风险操作需人工介入")
```

### 2.2 事件边界约束

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

### 2.3 交叉验证（Auditor 独立验证）

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

1. **结构化输出**：JSON Schema 校验输入输出格式
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
tests/test_stateful_core.py        # 结构化验证
tests/test_coldchain_workflow.py   # 端到端验证链
tests/test_knowledge_flywheel.py    # 知识验证链
```

所有关键验证点都有对应的单元测试和集成测试覆盖。
