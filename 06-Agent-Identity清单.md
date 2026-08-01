# Agent Identity 清单

> 对应赛题 1.2:说明多 Agent 系统中各 Agent 的身份属性、能力边界和协同关系。
> 部署态:见 `agentteams/workers/*.yaml`(AgentTeams Worker CR 的 spec.identity/soul/agents)。
> 代码态:见 `src/dianxun/agents/orchestrator.py`。

## 概览

店巡 Agent 采用 **Manager → Team Leader → Workers** 三层架构,共 6 个 Agent 实体(1 Manager + 1 Team Leader + 4 Worker),形成端到端闭环。

```
Admin(人类运营)
  └─ Manager · dianxun-manager         协调入口,编排 Team
       └─ Team · dianxun-patrol-team
            ├─ Orchestrator [Team Leader]  总控
            ├─ Sentry      [Worker]        巡检
            ├─ Diagnoser   [Worker]        诊断
            ├─ Executor    [Worker]        处置
            └─ Auditor     [Worker]        稽核
```

---

## Agent 1 · Manager(协调入口)

| 属性 | 内容 |
|---|---|
| **名称** | dianxun-manager |
| **身份** | 协调型 Agent,任务分发与 Team/Worker 编排入口 |
| **运行时** | copaw(QwenPaw / Python) |
| **能力边界** | 只做编排,不执行领域任务(delegation-first);不持有真实 API Key,仅 consumer token |
| **可用 Skill** | worker-management(AgentTeams 内置) |
| **MCP 工具** | 经 dianxun-mcp 网关访问全部 7 工具(只读为主) |
| **数据权限** | 全部门店域(总部视角) |
| **协同关系** | 接收 Admin 指令 → 下发 Team Leader → 不绕过 Leader 直接调度 Worker |

## Agent 2 · Orchestrator(总控 / Team Leader)

| 属性 | 内容 |
|---|---|
| **名称** | orchestrator |
| **身份** | Team Leader,任务拆解、调度、状态追踪、冲突仲裁 |
| **运行时** | copaw |
| **能力边界** | 遵循 delegation-first,把任务分派给 Worker,自己不做异常检测/诊断/处置等执行 |
| **可用 Skill** | 全部 7 个(调度层,按规则选择) |
| **关键产出** | 任务子图 DAG、状态机流转记录 |
| **数据权限** | 全部门店域 |
| **协同关系** | 派 Sentry(检测)→ Diagnoser(诊断)→ Executor(处置)→ Auditor(验证);验证失败触发 reopened 二次闭环 |
| **代码** | `src/dianxun/agents/orchestrator.py` → `Orchestrator` 类 |

## Agent 3 · Sentry(巡检 / Worker)

| 属性 | 内容 |
|---|---|
| **名称** | sentry |
| **身份** | 巡检员,多源聚合、异常识别、降噪定级 |
| **运行时** | copaw |
| **能力边界** | **只读**,绝不写业务数据;聚合数据不透传明细 PII;结果经置信度过滤防刷屏 |
| **可用 Skill** | `anomaly-detect`(看家)、`price-tag-check` |
| **关键产出** | 异常清单(带 anomaly_id / type / severity / confidence / evidence / matched_rule) |
| **数据权限** | 全部门店只读(POS/WMS/IoT/价格) |
| **降级策略** | 单源不可用标 partial;全源不可用标 degraded 进降噪模式 |
| **协同关系** | 输出喂 Diagnoser;严重价签不一致(收银>标价)直接升级 Executor |
| **代码** | `SentryAgent.detect()` |

## Agent 4 · Diagnoser(诊断 / Worker)

| 属性 | 内容 |
|---|---|
| **名称** | diagnoser |
| **身份** | 运营专家,跨店横向对标、维度下钻、根因定位(**差异化核心**) |
| **运行时** | copaw |
| **能力边界** | **只读**;供应商级信息仅总部角色;禁止把诊断结论直接写回业务系统(只生成建议) |
| **可用 Skill** | `cross-store-benchmark`(看家)、`rootcause-drilldown` |
| **关键产出** | 根因报告(多假设按置信度排序 + 下钻路径 + 核验计划) |
| **数据权限** | 全部门店聚合统计(不返回其他门店明细,防信息泄露) |
| **防幻觉机制** | 知识库 RAG 无命中时明确"无历史案例",不编造;多假设并列不武断 |
| **协同关系** | 读 Sentry 异常清单;输出经上下文总线传 Executor;报告全文写审计库供 Auditor |
| **代码** | `DiagnoserAgent.diagnose()` |

## Agent 5 · Executor(处置 / Worker)

| 属性 | 内容 |
|---|---|
| **名称** | executor |
| **身份** | 店务专员,处置方案生成、执行、审批触发、回滚 |
| **运行时** | copaw |
| **能力边界** | **写操作必审批**:维修>2000 / 补货>5000 / 批量调价>20SKU 强制人工;**付款环节绝不执行**(只生成待付款单);写操作带 idempotency_key 可回滚 |
| **可用 Skill** | `restock-order-gen`、`work-order-dispatch`(写操作) |
| **关键产出** | 处置工单、补货单、改价单(均含审批记录) |
| **数据权限** | 本店写权限(经审批);跨店调拨需额外授权 |
| **协同关系** | 读 Diagnoser 根因;执行后状态写上下文;触发 Auditor 验证 |
| **代码** | `ExecutorAgent.handle()` |

## Agent 6 · Auditor(稽核 / Worker)

| 属性 | 内容 |
|---|---|
| **名称** | auditor |
| **身份** | 稽核员,恢复验证、效果评估、复盘沉淀(**经验飞轮引擎**) |
| **运行时** | copaw |
| **能力边界** | 验证用数据说话(温度回基线/库存回升/价格一致);知识入库前过质量门(去重/置信度/脱敏);报告仅总部可见 |
| **可用 Skill** | `review-report`(看家) |
| **关键产出** | 验证报告(带置信度/方法)、复盘报告、知识条目、Skill 更新建议 |
| **数据权限** | 全门店只读 + 知识库读写 |
| **飞轮机制** | 复盘写入知识库 → 下次 Diagnoser 的 RAG 检索命中 → 诊断更准 |
| **协同关系** | 读 Executor 处置;验证失败触发 reopened;复盘后驱动经验沉淀 |
| **代码** | `AuditorAgent.verify()` / `.review()` |

---

## 能力边界矩阵(防越权)

| Agent | 读写 | 审批 | 跨店数据 | 付款 | 知识库 |
|---|---|---|---|---|---|
| Manager | — | — | 全域 | ❌ | — |
| Orchestrator | 调度 | 触发 | 全域 | ❌ | — |
| Sentry | 只读 | ❌ | 聚合 | ❌ | — |
| Diagnoser | 只读 | ❌ | 仅统计值 | ❌ | 读(RAG) |
| Executor | **写(经审批)** | **触发** | 本店 | **❌ 绝不** | — |
| Auditor | 只读+知识库 | ❌ | 全域 | ❌ | **读写** |

**核心安全原则**:付款环节任何 Agent 都不可执行;所有写操作经审批且可回滚;跨店数据只暴露聚合统计。
