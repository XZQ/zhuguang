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

## P2 场景价值：总部运营要的是可安全放行的闭环

- 目标用户：连锁总部运营负责人、区域督导和门店店长。
- 当前痛点：告警、电话/群聊、工单和表格割裂，设备、商品与审批事实分散；失败代价是误放行、错误关闭和追责断链。
- 输入：温度读数与质量、设备/门店上下文、库存批次、停售、审批、工单和人工证据。
- 输出：风险遏制、证据关联 Top-K 诊断、获批处置，以及 Auditor 的独立写后重查。
- 完成条件：设备恢复、逐批商品安全、停售状态一致、审计可追溯同时成立。
- 价值口径：把人肉串联改造成职责分离的证据链；真实效率和损耗收益必须在门店基线建立后量化，不展示未经验证的比例。

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

## P7 Skill 工程：六个 P0 契约进入版本化 Registry 与 Worker ZIP

- P0：`anomaly-detect`、`coldchain-risk-assess`、`rootcause-drilldown`、`work-order-dispatch`、`outcome-verify`、`review-report`。
- P1：`cross-store-benchmark`；P2：`restock-order-gen`、`price-tag-check`。
- 每个 P0 Skill 都有 `SKILL.md`、manifest、输入/输出 Schema、成功/失败样例和版本记录。
- Registry 当前固定 6 个 stable、0 个 canary；release identity 为 `name + version + digest`。
- 生命周期覆盖 SemVer、确定性灰度、promotion、兼容升级、rollback target 和 retirement；本地 Span 自动记录 version/digest。
- Worker ZIP 只包含 6 个 P0 Skill 及 Registry/生命周期文件，避免把规划能力冒充已交付能力。
- 当前 SHA-256：`2f7e7d86ae7b115a966c5bcd57091ded7597df5939bb3031e91015e151979ffe`。
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
- 回滚/补偿必须区分：
  - 可逆：解除停售后发现验证失效，事件 `reopen` 并重新停售；原语已存在，同 Run 演练待可靠性阶段补齐。
  - 跨系统：维修工单不能物理回滚，应取消或改派并写后对账；当前有 compensation metadata，执行路径待补。
  - 不可逆：食品处置执行前由独立人工审批与 Policy 阻断；执行后只允许追踪与审计，不伪造“回滚”。

## P9 评测证据：本地门禁全部通过

- 6/6 场景通过；Top-1 与 Top-3 均为 6/6。
- Evidence 关键字段完整 45/45。
- 适用阶段 Trace 覆盖 26/26。
- 未授权业务写、未审批受控写、错误放行、错误关闭、重复副作用均为 0。
- 全量发现 76 项自动化测试：74 项通过，2 项 PolarDB 条件集成测试因无外部实例跳过。
- 四变体消融门禁通过；无 Auditor 时 5 个需修复场景安全阻断于 VERIFY/BLOCKED，单一身份的 6 次受控写全部被 Policy 拒绝，纯规则诊断 Top-1 降至 4/6。
- 只读事故指挥台把六场景的 Agent 交接、设备/商品状态、审批、审计和 Auditor 判决同屏呈现。
- 标注口径：固定 seed + 隔离 SQLite/Trace + 有状态 Mock；不是生产 KPI 或真实经营收益。

## P10 初赛反馈：反馈 → 标红改造 → 可验证证据

红色只表示初赛后新增或强化，不代表尚未实跑的平台能力已经完成。

| 初赛反馈方向 | 改造前 | 标红改造 | 验证证据 |
|---|---|---|---|
| 场景要聚焦、闭环要讲深 | 冷柜、缺货、价签平均展开；设备恢复容易被写成业务完成 | 冷柜升级为唯一 P0 主线；设备与商品分别验收，停售经审批和 Auditor 二次重查后解除 | A～F 六场景、45/45 Evidence、26/26 Trace |
| 多 Agent 要证明协作增益 | 本地类顺序调用；动作记录曾被当作验证结果 | 5 个业务 Agent 职责分离；Executor 不可自验；增加无 Auditor、单身份、纯规则诊断消融 | 0 错误关闭、5 个失败场景阻断、6 次越权拒绝 |
| 工程声明必须可复现 | 自动审批、强因果诊断与云上能力缺少对应运行证据 | pending/timeout、Top-K + 证据缺口、制品 provenance，并拆分“本地已验证”和“外部待验证” | 76 项测试、Worker checksum、事实 JSON |

## P11 复制路径：保留控制面，替换领域契约

- 保持不变：Incident 状态机、Manager + 职责分离、Evidence/Context 契约、Policy + HITL、幂等、审计和独立验收。
- 路径 A - 连锁餐饮冷链：
  1. 输入替换为仓温、车温、交接记录和供应批次；
  2. Policy 替换为暴露窗口、责任节点和放行审批人；
  3. MCP Adapter 替换为 IoT/WMS/供应商工单；
  4. 以温控恢复、批次处置和交接审计复验。
- 路径 B - 工业设备巡检：
  1. 输入替换为振动、电流、告警、点检和备件；
  2. Policy 替换为停机阈值、检修等级和复产审批人；
  3. Skill 替换为设备诊断、维修计划和复产验证；
  4. 以设备状态、安全检查和工单闭环复验。
- 统一迁移步骤：映射实体与风险 → 替换 Policy/Skill/MCP → 重建正常与失败金标 → 以真实 AgentTeams Trace 验收。

## P12 交付与边界：仓库证明不等于平台证明

- 仓库已验证：有状态核心、六场景、6 个 P0 Skill、12+3 MCP、Worker ZIP/provenance、76 项测试、消融、指挥台和 HTML/PDF。
- 可部署但不声称已运行：AgentTeams/Kubernetes 配置，以及 PostgreSQL Store、pgvector、RLS、分区、pg_cron 和 OSS 复制复核归档契约。
- 最终外部验收：同一事故中的 Team Room 委派、Skill Trace、Worker → MCP Actor 正负向鉴权、真实 HITL、正常/partial 分支，以及不超过 8 分钟的最终成片。
- 结束句：温度恢复不等于商品安全；Agent 的完成声明不等于业务事实。事件只有在证据闭环后才能关闭。
- 仓库：[github.com/XZQ/zhuguang](https://github.com/XZQ/zhuguang)

## 演示稿验收清单

- [x] HTML 与 PDF 均为 12 页，页码、标题和本文一致。
- [x] 不出现“设备恢复即商品安全”“跨店正常即压缩机故障”。
- [x] 只把 RAG/PolarDB 写成“代码已实现、云上与真实基线待验证”，不写成已投产或已改善经营指标。
- [x] 所有评测数字能在 `evidence/m4/results.json` 追溯。
- [x] “AgentTeams 外部待验证”在架构页和收尾页均可见。
- [x] 初赛反馈页使用红色明确标出初赛后新增/强化内容，并保持外部证据边界。
- [x] 场景页包含目标用户、人工流程痛点、失败代价、输入、输出、完成条件和价值口径。
- [x] 安全页明确区分可逆动作、跨系统补偿和不可逆动作。
- [x] 复制页包含至少一条跨业态和一条跨行业的具体替换及复验路径。
- [x] 不把本地可选 Bearer 或业务角色门禁写成 AgentTeams 部署侧身份鉴权已闭环。
- [x] 录屏使用 [`../demo/Demo视频脚本与证据清单.md`](../demo/Demo视频脚本与证据清单.md)，不得用静态截图冒充平台动态证据。
