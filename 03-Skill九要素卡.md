# Skill 九要素卡

> 唯一统计口径：9 个目标 Skill，其中 P0 核心 6 个、P1 增强 1 个、P2 补充场景 2 个。只有 6 个 P0 Skill 进入 `dianxun-worker.zip` 和六场景门禁。

## 1. 唯一清单

| Skill | 优先级 | Owner | 当前状态 | 契约 |
|---|---|---|---|---|
| `anomaly-detect` | P0 | Sentry | 已实现，版本 1.0.0 | [`skills/anomaly-detect/`](skills/anomaly-detect/) |
| `coldchain-risk-assess` | P0 | Diagnoser | 已实现，版本 1.1.0 | [`skills/coldchain-risk-assess/`](skills/coldchain-risk-assess/) |
| `rootcause-drilldown` | P0 | Diagnoser | 已实现，版本 1.1.0 | [`skills/rootcause-drilldown/`](skills/rootcause-drilldown/) |
| `work-order-dispatch` | P0 | Executor | 已实现，版本 1.0.0 | [`skills/work-order-dispatch/`](skills/work-order-dispatch/) |
| `outcome-verify` | P0 | Auditor | 已实现，版本 1.1.0 | [`skills/outcome-verify/`](skills/outcome-verify/) |
| `review-report` | P0 | Auditor | 已实现，版本 1.0.0 | [`skills/review-report/`](skills/review-report/) |
| `cross-store-benchmark` | P1 | Diagnoser | 代码保留；未进入 P0 Worker/评测 | [`skills/cross-store-benchmark.md`](skills/cross-store-benchmark.md) |
| `restock-order-gen` | P2 | Executor | 缺货补充入口使用；非冷柜 P0 | [`skills/restock-order-gen.md`](skills/restock-order-gen.md) |
| `price-tag-check` | P2 | Sentry / Executor | 价签补充入口使用；非冷柜 P0 | [`skills/price-tag-check.md`](skills/price-tag-check.md) |

“P0 已实现”表示 Python 实现、Skill 工程文件、Schema/样例和自动化门禁同时存在；不表示真实 AgentTeams Worker 已在目标集群动态运行。

## 2. P0 Skill 九要素

### S1. anomaly-detect

| 要素 | 定义 |
|---|---|
| 名称 | `anomaly-detect` |
| 用途 | 从设备时间序列识别持续失温，标记数据质量和传感器可疑性，生成事件级异常证据。 |
| 输入输出 | 输入设备、门店、时间窗和 Policy；输出 anomaly、severity、quality、evidence refs 及是否需要遏制。完整 Schema 见契约目录。 |
| 调用条件 | Sentry 收到场景/IoT 触发并完成最小数据可用性检查后调用。 |
| 依赖工具 | `query_device_context`；必要时由编排层补充人工证据。 |
| 失败处理 | 查询失败返回 partial/degraded；可疑传感器数据不直接驱动商品最终处置；无法证明安全时保持遏制。 |
| 安全边界 | 只读；不得解除停售、创建工单或宣布根因。 |
| 复用价值 | 可复用于其他带时序传感器和质量标记的设备异常发现。 |
| 协同关系 | 输出交给 Orchestrator 建立 IncidentContext，再由 Executor 先遏制、Diagnoser 诊断。 |

### S2. coldchain-risk-assess

| 要素 | 定义 |
|---|---|
| 名称 | `coldchain-risk-assess` |
| 用途 | 按商品批次独立计算温度暴露和处置建议，避免用设备状态覆盖商品安全。 |
| 输入输出 | 输入 incident、设备温度、批次存储策略和版本化 Policy；输出每批次风险、暴露量、建议 disposition 与证据引用。 |
| 调用条件 | 已发现冷柜失温并取得设备关联批次后调用；设备恢复后仍需重新评估。 |
| 依赖工具 | `query_device_context`、`query_inventory_batches`、`coldchain-demo:1.0.0` Policy。 |
| 失败处理 | 缺少批次或温度证据时返回 manual_review/partial，不给出安全放行结论。 |
| 安全边界 | 只读建议；真实部署阈值必须由企业食品安全负责人批准。 |
| 复用价值 | 可复用于冷链仓储、餐饮后厨和药品冷藏，但 Policy 必须按领域替换。 |
| 协同关系 | Diagnoser 将结果写入决策依据；Executor 只执行 Policy 允许且审批完成的处置。 |

### S3. rootcause-drilldown

| 要素 | 定义 |
|---|---|
| 名称 | `rootcause-drilldown` |
| 用途 | 将压缩机故障、传感器故障、门未关闭等候选按证据排序，输出 Top-K 与检查计划。 |
| 输入输出 | 输入 anomaly、设备健康/门/电源/维护证据；输出 ranked hypotheses、confidence、supporting/contradicting evidence 和 next checks。 |
| 调用条件 | 遏制完成且 Diagnoser 获得设备上下文后调用。 |
| 依赖工具 | `query_device_context`；P1 RAG 未启用时明确记录 disabled。 |
| 失败处理 | 证据不足时保留多个假设并降低置信度；工具 partial 时输出证据缺口，不硬编码压缩机故障。 |
| 安全边界 | 只读；不能因跨店或相关性证据直接写入“确定根因”。 |
| 复用价值 | Top-K + 证据缺口模式可复用于设备、供应链和运营异常诊断。 |
| 协同关系 | Orchestrator 使用 Top-1 作为当前工单 fault，保留其余假设供 Auditor/人工复核。 |

### S4. work-order-dispatch

| 要素 | 定义 |
|---|---|
| 名称 | `work-order-dispatch` |
| 用途 | 根据 Top-1 假设生成幂等维修动作，处理审批、超时、派单和状态查询。 |
| 输入输出 | 输入 incident、device、fault、budget、Policy 和幂等键；输出审批/工单引用、当前状态和后续动作。 |
| 调用条件 | Diagnoser 已给出可执行假设；Executor 通过 Policy 校验后调用。 |
| 依赖工具 | `create_approval`、`query_approval`、`create_workorder`、`query_workorder`。 |
| 失败处理 | 高预算未批准不创建工单；审批超时升级区域负责人；工单查询 partial 时阻断关闭。 |
| 安全边界 | 仅 Executor 可创建审批/工单；审批决定只能由 Human/ScenarioEngine；付款永远禁止。 |
| 复用价值 | 可复用于任何“外部服务商 + 审批 + SLA”型任务。 |
| 协同关系 | Executor 执行，Orchestrator 管理等待，Auditor 独立查询最终工单状态。 |

### S5. outcome-verify

| 要素 | 定义 |
|---|---|
| 名称 | `outcome-verify` |
| 用途 | 重新查询设备、批次、停售、审批和工单事实，生成 release guard 与最终验证。 |
| 输入输出 | 输入 incident_id、期望状态和查询结果；输出 attempts、subject verifications、partial tools、release guard 与结论。 |
| 调用条件 | 处置后调用；解除停售前生成放行守卫，Executor 完成放行后必须再次调用完成最终核验。 |
| 依赖工具 | 5 个 P0 查询函数；验证证据由 `IncidentService` 记录。 |
| 失败处理 | 任一关键工具 partial、批次不安全、停售仍异常或工单状态不完整时返回 failed/partial 并回开或阻断关闭。 |
| 安全边界 | Auditor 只验证和建议；解除停售仍由 Executor 经审批执行；不能信任 Executor 的动作回执代替重查。 |
| 复用价值 | 独立验证模式可复用于订单、维修、库存和合规闭环。 |
| 协同关系 | 与 Executor 形成职责分离；`IncidentService` 根据验证结果计算 `RESOLVED`。 |

### S6. review-report

| 要素 | 定义 |
|---|---|
| 名称 | `review-report` |
| 用途 | 按 incident/batch 关联时间线、根因、动作、验证和改进项，输出复盘与知识候选。 |
| 输入输出 | 输入 IncidentCase、actions、verifications、Evidence refs；输出 review、lessons、knowledge candidates 和 Skill 建议。 |
| 调用条件 | Auditor 验证通过且事件进入 LEARN 时调用；未安全关闭的场景不伪造完成复盘。 |
| 依赖工具 | IncidentService 快照和本地 Trace/Evidence；当前不依赖真实 RAG。 |
| 失败处理 | 证据不完整时标记 partial；知识候选保持 pending，不自动发布或宣称未来检索命中。 |
| 安全边界 | 输出需脱敏；不得自动修改生产 Skill、Policy 或正式知识库。 |
| 复用价值 | 可复用于任何需要审计复盘和人工治理的事件闭环。 |
| 协同关系 | Auditor 生成报告；Orchestrator 只有在 `RESOLVED + LEARN` 后请求 `IncidentService` 迁移为 `CLOSED`。 |

## 3. P1/P2 能力边界

### cross-store-benchmark（P1）

保留跨店聚合对标代码，用于判断异常是单店孤立还是集群性。它只能作为诊断辅助证据，不能从“其他门店正常”直接推导“本店压缩机故障”。当前六场景不依赖该 Skill，Worker ZIP 也不包含它。

### restock-order-gen（P2）

保留缺货补充入口使用的补货建议能力。当前入口为：

```powershell
uv run python demo/run_supplementary.py stockout
```

它不属于冷柜 P0 状态核心，也不代表真实采购系统已接入。

### price-tag-check（P2）

保留价签三方一致性检查与补充入口：

```powershell
uv run python demo/run_supplementary.py price-tag
```

当前只证明本地数据链可运行；批量改价、真实价签系统和生产回滚未纳入 P0 声明。

## 4. 工程与验证要求

每个 P0 Skill 目录必须同时包含：

- `SKILL.md`；
- `manifest.json`；
- `input.schema.json`；
- `output.schema.json`；
- 至少一个成功样例和一个失败样例；
- 权限、失败语义、版本与变更记录。

验证命令：

```powershell
uv run --group dev python -m unittest -v tests.test_skill_contracts
uv run python scripts/build_worker_package.py
uv run --group dev python -m unittest -v tests.test_agentteams_artifacts
```

构建脚本会验证根目录规范与 Worker 包副本一致。任何 Skill 新增、删除、改名或升版，都必须同步本文件、`config/project-facts.json`、Worker manifest、YAML、测试和 README。
