# Agent 结果验证机制

> 复核日期：2026-09-12。本文描述结构契约、权限、事务、独立核验与人工审批组成的工程验证；不承诺所有输入语义正确，也不宣称形式化证明。

## 1. 验证层

| 层 | 当前约束 | 证据 |
|---|---|---|
| 输出 | 六个 P0 Skill 在真实函数返回路径校验 output Schema，拒绝字段、类型和枚举漂移 | [运行时契约](../src/dianxun/skills/contracts.py)、[正反例](../tests/test_skill_contracts.py) |
| 策略 | 按版本化 action、allowed_actors、风险与审批判断，不按虚构等级推断 | [Policy](../config/policies/coldchain-demo.v1.json)、[PolicyEngine](../src/dianxun/domain/policy.py) |
| 业务 | 事件/门店/批次/设备范围、指纹、action 唯一性、版本和事务 | [P0 工具](../src/dianxun/mcp/p0.py)、[安全回归](../tests/test_adversarial_hardening.py) |
| 核验 | Auditor 重查当前设备、商品、停售与审批；Executor 不能自证关闭 | [闭环](../tests/test_coldchain_workflow.py)、[并发](../tests/test_incident_concurrency.py) |
| 人工 | 受控处置/超阈值维修先审批，绑定动作、金额与批次；知识发布需审核脱敏 | [核心测试](../tests/test_stateful_core.py)、[知识测试](../tests/test_knowledge_flywheel.py) |

六个运行入口：detect_coldchain_event、coldchain_risk_assess、diagnose_coldchain_hypotheses、dispatch_stateful_workorder、outcome_verify、review_incident。结构合法不等于语义正确；真实输入质量与商品规则须另行验证。

## 2. Skill 和运行证据身份

[Registry](../skills/registry.json)固定 release 的 name/version/digest。Trace 记录 skill_name、skill_version、skill_digest、skill_channel、skill_registry_version。stable/canary 采用确定性摘要分桶；retired 不接受新路由；旧 Trace 行保留空版本，不伪造身份。

[AgentTeams 证据 Schema](../schemas/agentteams-run-evidence.v1.schema.json)为 1.3，[校验器](../src/dianxun/agentteams_evidence.py)将 Skill load、工具调用与 Worker provenance 比对，并检查：

- 官方 Project/Room/Task ID、不可变包来源、模型运行披露；
- Worker 与服务端 Actor、tenant/version/lease/checkpoint；
- 时间须有明确时区并满足因果顺序；无时区时间和因果倒置均拒绝；
- predecessor、超时 successor、checkpoint 恢复和最终状态来源；
- 解除停售前后的 Auditor 独立重查。

[证据测试](../tests/test_agentteams_runtime_evidence.py)验证格式和反伪造边界。静态 YAML/Schema 和本地校验通过，不等于真实平台产生了委派、身份或 Trace。

## 3. 协调与业务状态

独立 ContextBus 使用 WAL/expected_version；Worker runtime 通过业务库的 RuntimeContextBus 与领域动作共用事务。只有 IncidentService 能判断业务终态，Context completed 不能直接关闭事件。CAS/SAVEPOINT 见[一致性说明](分布式一致性方案.md)。

/runtime 校验 Worker/tenant/store/role、版本和有效 assignment。恢复扫描器检查心跳、真实进展、硬截止、总预算和回执；空心跳不能无限延期，partial/未知结果不能写成功 checkpoint。参数与 Human 运维见[恢复手册](operations/runtime-recovery.md)。

## 4. 冷链验证顺序

1. Sentry 检查数据质量并发现异常。
2. Executor 在预授权范围内先停售、遏制，避免诊断期间继续暴露风险。
3. Diagnoser 按批次评估暴露并关联根因证据；建议不直接改变库存。
4. 受控维修/处置先申请独立 Human 审批，再由 Executor 执行。比赛策略中维修金额大于 2000 元要求审批；transferred/released/disposed 和解除停售均有对应审批条件。
5. Auditor 重查设备、商品和处置。设备恢复不等于商品可售，维修完成不等于事故关闭。
6. 需要解禁时，Executor 使用有效审批与 Auditor release_guard；随后 Auditor 再核验当前事实。
7. LEARN 再核验后由服务调用 IncidentService 关闭；知识候选经独立审核脱敏才发布。

审批超时是 timeout，不等同人工 rejected；保持遏制并按预算等待或升级。partial、无效审批、旧版本、失效租约不能当成功。受控 reopen 需要完整失败核验与授权，不能因查询不完整绕过检查开始新轮次。

## 5. 验证与答辩口径

执行命令、职责和最新汇总统一见[测试覆盖矩阵](测试覆盖矩阵.md)。本地使用临时真实 SQLite、真实 Policy、有状态外部替身和 HTTP；尚无正式行/分支覆盖率或生产高争用证明。

[消融结果](../evidence/m4/ablation.md)中，移除 Auditor 后 5 个场景停于 VERIFY/BLOCKED，0 放行尝试、0 错误关闭、0 不安全放行。结论是验证者不可用时保持限制，不能写成“5 个场景被错误放行”。

当前为工程回归与确定性门禁，未做形式化证明；不据此断言工程验证在所有场景优于形式化验证或所有模型判断。现行问答统一见[决赛讲稿](competition/finals/03-决赛逐页讲稿与问答.md)。
