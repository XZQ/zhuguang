# 逐光｜方案 PPT 结构（12 页）

> 目标受众：GOAI Agent Infra 赛道评委。
> 演示目标：让评委确认逐光不是“多 Agent 名称拼接”，而是一个可运行、可审计、会在失败时保持安全的冷柜事件闭环。
> 可见数字必须来自 `config/project-facts.json`、`evidence/m4/results.json` 或实际交付物。

## P1 封面：一条事件，而不是一条告警

- 标题：逐光 - 连锁门店异常闭环基础设施
- 产品说明：店巡 Agent
- 副标题：冷柜失温首要完整验证场景
- 核心句：先遏制风险，再诊断；设备恢复与商品安全分别关闭
- 状态角标：本地 P0 评测已通过；AgentTeams 动态运行外部待验证

## P2 场景价值：真正的交付单位是“安全关闭的事件”

- 输入不只是温度告警，还包括设备、批次、停售、审批、工单和人工证据。
- 业务风险：告警已消失、工单已完成，都不能证明商品可以恢复销售。
- 第一性原理：
  1. 风险扩散必须先被阻断；
  2. 诊断必须表达不确定性；
  3. 执行者不能自己宣布成功；
  4. 关闭必须有独立、可追溯的业务事实。
- 不展示未经真实数据验证的降本增效比例。

## P3 系统边界：一个业务核心，两个运行入口

- 唯一事实入口：`IncidentService + StateStore + PolicyEngine`。
- 本地入口：`LocalDemoAdapter`，用于确定性回归和评测。
- AgentTeams 入口：1 个 Framework Manager + 5 个业务 Worker，通过同一 Skill/MCP 契约接入。
- 数据底座：SQLite 用于零依赖评测；PolarDB PostgreSQL 用于部署，已提供 pgvector、RLS、月分区、pg_cron 和 OSS 外部归档契约。
- 工程口径：6 个 P0 Skill；12 个 P0 MCP 函数 + 3 个可选知识工具；AgentTeams `v1.2.3`；目标运行时声明 `qwenpaw + qwen3.5-plus`。
- 模型边界：本地确定性 Demo/M4 不调用 LLM；凭证仅运行时注入，费用取决于提供商，替换兼容模型后必须重跑结构化输出、工具调用、延迟、费用和安全门禁。
- 明确边界：POS/WMS/IoT/审批/维修商当前均为有状态 Mock；平台动态协同待外部验证。

## P4 多 Agent 协同：五个角色形成职责分离

| 业务 Agent | 负责 | 不允许 |
|---|---|---|
| Orchestrator | 拆解、委派、阶段推进、等待与回开 | 绕过领域服务直接改终态 |
| Sentry | 异常识别、质量判断、风险触发 | 业务写操作 |
| Diagnoser | Top-K 假设、证据缺口、检查计划 | 把相关性写成确定因果 |
| Executor | 经 Policy/审批执行停售、处置、工单 | 审批自己、验证自己、关闭事件 |
| Auditor | 独立重查、放行守卫、复盘 | 直接执行受控业务动作 |

页脚说明：Manager 是框架调度实体，不计入 5 个业务 Agent。

## P5 五阶段主线：业务叙事与运行状态分层

1. 发现与遏制：先停售、隔离受影响批次。
2. 诊断与决策：输出证据关联的 Top-K 假设。
3. 处置执行：审批、维修和商品处置分别推进。
4. 独立验证：Auditor 重查设备、批次、停售、审批、工单。
5. 复盘演进：输出复盘和待审知识候选；独立人工审核、脱敏通过后才可被后续诊断检索。

同时展示 `phase`、`incident_status`、`work_status` 和实体状态，说明“等待审批”“工具 partial”“商品仍不安全”不会被一条线性状态覆盖。

## P6 六场景：正常路径和失败路径同等重要

| 场景 | 关键证明 | 预期结果 |
|---|---|---|
| A 压缩机故障 | 审批、工单、批次处置、双重验证 | `CLOSED` |
| B 传感器误报 | 可疑传感器不直接驱动处置，放行需两次验证 | `CLOSED` |
| C 门未关闭 | 设备恢复后仍单独评估商品 | `CLOSED` |
| D 审批超时 | 升级区域负责人并保持遏制 | `CONTAINED` |
| E 设备恢复但商品不安全 | 回到商品处置审批，不错误放行 | `CONTAINED` |
| F 工单查询 partial | 阻断关闭并保持停售 | `CONTAINED` |

## P7 Skill 工程：六个 P0 契约进入 Worker ZIP

- P0：`anomaly-detect`、`coldchain-risk-assess`、`rootcause-drilldown`、`work-order-dispatch`、`outcome-verify`、`review-report`。
- P1：`cross-store-benchmark`；P2：`restock-order-gen`、`price-tag-check`。
- 每个 P0 Skill 都有 `SKILL.md`、manifest、输入/输出 Schema、成功/失败样例和版本记录。
- Worker ZIP 只包含 6 个 P0 Skill，避免把规划能力冒充已交付能力。
- 当前 SHA-256：`3ee0f904974dda8b917693a1e73be3c16f77a50f23975c7de13621d8bbec2a0c`。
- 当前 P0 均为自定义可复用 Skill；复赛规则不要求指定云厂商 Skill，目标运行时的发现、加载、调用和 Trace 才是验收证据。

## P8 MCP 与安全：五查、七动作、四道闸

- 查询：设备上下文、库存批次、停售、工单、审批。
- 动作：停售、解除停售、批次处置、创建工单、创建审批、人工决定审批、记录人工证据。
- 四道闸：业务角色权限、Policy/审批、幂等键、审计记录。
- 解除停售必须同时绑定已批准审批和 Auditor 验证。
- `decide_approval` 与 `record_manual_evidence` 只允许 Human/ScenarioEngine。
- payment 为 L3，任何 Agent 都不可执行。
- 非回环无认证时 MCP 拒绝启动；共享 Token 只读，状态写必须使用 Actor-bound Token。
- 数据库再以登录账号绑定的 RLS、业务只读账号和最小 GRANT 强制权限；目标 AgentTeams 动态身份映射仍需烟测，不能由静态 YAML 推断完成。

## P9 评测证据：本地门禁全部通过

- 6/6 场景通过；Top-1 与 Top-3 均为 6/6。
- Evidence 关键字段完整 45/45。
- 适用阶段 Trace 覆盖 26/26。
- 未授权业务写、未审批受控写、错误放行、错误关闭、重复副作用均为 0。
- 全量发现 72 项自动化测试：70 项通过，2 项 PolarDB 条件集成测试因无外部实例跳过。
- 四变体消融门禁通过；无 Auditor 时 5 个需修复场景安全阻断于 VERIFY/BLOCKED，单一身份的 6 次受控写全部被 Policy 拒绝，纯规则诊断 Top-1 降至 4/6。
- 只读事故指挥台把六场景的 Agent 交接、设备/商品状态、审批、审计和 Auditor 判决同屏呈现。
- 标注口径：固定 seed + 隔离 SQLite/Trace + 有状态 Mock；不是生产 KPI 或真实经营收益。

## P10 交付与边界：仓库内可复现，平台证据不冒充

- 已交付：代码、六场景、评测与消融报告、事故指挥台、6 个 P0 Skill 契约、12+3 MCP、Worker ZIP/provenance、AgentTeams/Kubernetes/PolarDB overlay、HTML 演示稿和 PDF。
- 可复现命令：`uv run dianxun evaluate`。
- 外部待验证：Team Room、Worker 委派、Kubernetes Running、Worker → MCP 身份绑定、同一任务的平台 MCP/Trace，以及托管 PolarDB、OSS 归档和真实知识基线。
- Skill 验收：必须展示目标 AgentTeams 运行时中的实际调用、版本、失败处理和 Trace，不能装饰性堆叠。
- 结束句：不是让 Agent 更会“说已完成”，而是让事件只有在证据闭环后才能关闭。
- 仓库：[github.com/XZQ/zhuguang](https://github.com/XZQ/zhuguang)

## 演示稿验收清单

- [ ] HTML 与 PDF 均为 12 页，页码、标题和本文一致。
- [ ] 不出现“设备恢复即商品安全”“跨店正常即压缩机故障”。
- [ ] 只把 RAG/PolarDB 写成“代码已实现、云上与真实基线待验证”，不写成已投产或已改善经营指标。
- [ ] 所有评测数字能在 `evidence/m4/results.json` 追溯。
- [ ] “AgentTeams 外部待验证”在架构页和收尾页均可见。
- [ ] 不把本地可选 Bearer 或业务角色门禁写成 AgentTeams 部署侧身份鉴权已闭环。
- [ ] 录屏使用 [`../demo/Demo视频脚本与证据清单.md`](../demo/Demo视频脚本与证据清单.md)，不得用静态截图冒充平台动态证据。
