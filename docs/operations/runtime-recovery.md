# Worker 运行与故障恢复

复核日期：2026-09-13。五个业务角色为 Orchestrator、Sentry、Diagnoser、Executor、Auditor；Human 运维身份单独配置。服务端确定性监督任务，IncidentService 判断业务终态。本文集中维护调用、默认预算、监测和回退，当前进度见[统一待办](../待办.md)。

> 2026-09-15 补充：商品终态新增独立整批接收/销毁凭证检查，旧动作回执不能用于新处置；P0001 拒绝返回稳定错误并回滚。部署、凭证字段、版本识别与离线回放见[决赛服务端交接](finals-server-handoff.md)，未完成验收见统一待办 F01–F08。

## 身份与接入

`/runtime` 提供独立的 MCP JSON-RPC 工具目录，原 `/mcp` 的 12 个 P0 业务工具保持兼容。
领域实现仍仅位于 src/dianxun。Worker ZIP 保持已有字节和固定下载地址；新增运行接口规则
通过 Worker YAML 的 agents 字段传入，不向包内复制 Python 实现。

服务端从 `DIANXUN_RUNTIME_TOKENS_JSON` 读取 Token 到身份的映射。每个值必须包含
`actor`、`worker_id`、`tenant_id`、`store_id` 四个非空字段。Worker 角色为 Orchestrator、
Sentry、Diagnoser、Executor、Auditor；另允许独立 Human 运维身份用于恢复与通知，不能领取 Worker 任务，也不注入模型。一个 worker_id 不得绑定多个角色或门店。
使用秘密管理器配置 `dianxun-agent-identities/runtime-tokens-json`，并由 AgentTeams
运行环境为对应 Worker 的 MCP 连接注入其 Bearer Token。Token 不写进 YAML、聊天或 Trace。
运行接口不接受旧共享 Token，也不接受请求体自报角色。

## 调用顺序

1. Orchestrator 调用 runtime_open(incident_id, device_id)。租户、门店从身份绑定获得，
   设备和批次范围由数据库校验；重复 open 只能读取同一设备的既有事故。
2. runtime_snapshot 返回 incident、context、remaining_stages 和 containment_required。
   后者列出当前缺少有效停售记录的批次，Executor 在 CONTAIN 阶段只对这些批次补做停售。
3. Worker 启动和空闲时先调用 runtime_poll 登记在线；Orchestrator 用 runtime_assign(incident_id, worker_id, expected_version) 委派下一阶段。
4. Worker 用 runtime_heartbeat 延长租约；返回的新 context_version 用于后续请求。
5. Executor 用 runtime_tool 调用当前 assignment 允许的业务工具。arguments 保留稳定的
   action_id/idempotency_key；成功后采用返回的新 context_version。审批必须由独立 Human 身份经原业务接口作出。
6. Worker 用 runtime_complete 提交交接。请求仅包含 incident_id、assignment_id、
   expected_version；不接受业务状态字段。检测、诊断、风险评估和审计由规范 Skill 执行。
7. completed=false 表示核验或执行未满足条件，没有成功 checkpoint；修复外部事实后可重试。
   已完成请求重放返回 replayed=true 和原 output；快照中的 checkpoint.output 同样可读取。
   超时由后台扫描器按预算自动恢复；runtime_reassign 可能返回 assignment=null 和等待原因。
8. 审计确认需重新处置时，Orchestrator 调用 runtime_reopen(incident_id, expected_version)。
   服务端重新独立查询，只有完整且失败的核验才能重启；partial、核验通过、越权和旧版本均拒绝。
   流程从 CONTAIN 开始，再诊断、执行、审计和关闭。旧租约及 checkpoint 连同输出归档在
   context.transitions 的 runtime_reopened 事件中；旧租约失去执行权，新租约保留 predecessor
   和递增 attempt。重放已归档租约也不能跳过新一轮核验。已关闭事故必须新建事件。

八个协调步骤实现五个领域阶段：DETECT/Sentry、CONTAIN/Executor 对应 DETECT_CONTAIN；
DIAGNOSE_DECIDE/Diagnoser；EXECUTE/Executor；VERIFY/Auditor、RELEASE/Executor、
FINAL_VERIFY/Auditor；LEARN/Auditor。无需解禁的场景中 RELEASE 只检查并完成空操作。
查询 partial 或失败不能写成功 checkpoint。LEARN 再次核验后才调用 IncidentService 关闭。

## 持久化与兼容

runtime_contexts 保存协调版本，与领域变更使用同一个业务数据库事务；嵌套操作使用
SAVEPOINT，内部异常即使被转成工具错误结果，也会回滚该操作的业务、审计和幂等记录。
外层提交失败仍会回滚全部变更。SQLite 本地自动
建表，PostgreSQL 升级先由迁移管理员执行 core 和 security profile。后者启用 tenant/store
RLS 并授予 runtime 表权限。升级前备份；回滚停止 /runtime 流量、回退程序，保留新增表，
不删除业务数据。旧的独立 ContextBus 数据不自动导入，避免把演练 checkpoint 当真实任务。

2026-09-12 增加 checkpoint.output，不新增表；阶段结果和 checkpoint 原子持久化，诊断
响应丢失后可从快照或 complete 重放恢复批次评估。旧 checkpoint 缺少 output 时返回
output_available=false、output=null，不重算或伪造历史结果。回退旧程序时，须保留读取
此可选字段的兼容代码；不能让不识别新字段的旧运行接口直接消费升级后的上下文。

`python -m unittest tests.test_worker_runtime -v` 使用实际本地 HTTP 和数据库，覆盖闭环、
重启、幂等重放、partial 查询、事务回滚和身份/租约拒绝。设备读数和人工审批是测试 fixture。
真实 AgentTeams 平台身份注入、Team Room、托管 PolarDB 和外部维修系统仍需要目标环境验收。

## 启动与任务消费

`uv run dianxun-mcp` 在配置 `DIANXUN_RUNTIME_TOKENS_JSON` 后自动启动后台巡查，每 5 秒扫描一次。它不调用模型，也不等待 Agent 主动发起重派。所有 Worker 启动后及空闲期间每 10 秒调用 `runtime_poll({})`，登记在线状态并获取自己的 assignment、incident_id、context_version。只有 Token 配置、没有近期 poll 的实例不会作为健康候选者。

可额外运行 `uv run python -m dianxun.scheduler` 作为独立补扫进程，使用同一数据库和明确配置的租户/门店身份范围。多个扫描器通过 SQLite 写事务或 PostgreSQL 的事务 advisory lock 串行化同一门店的容量决策，runtime_contexts 继续使用版本条件提交。PostgreSQL 不需要为此授予 stores 的 UPDATE 权限，不新增表。独立进程是补扫机制，不是已验证的高可用部署。

主控通过 `runtime_assign` 委派下一阶段；其目标必须在线且有容量。无业务 assignment 时，扫描器生成单独的 `ORCHESTRATE` 主控任务，可在超时后换健康主控。主控不可用或预算耗尽时，服务端只按成功 checkpoint 确定下一阶段并派发合规 Worker，不作根因判断、审批或食品放行。主控任务保存在 `context.recovery.orchestration`，不占用八个业务阶段的 checkpoint。

## 固定预算与状态

| 项目 | 当前默认值 / 行为 |
|---|---|
| 心跳租约 | 60 秒；不能续过硬截止 |
| 在线健康 | 最近 90 秒内有 poll；每实例最多 1 个有效任务，主控任务也计入 |
| 主控 | 单次 60 秒、无进展 30 秒、每次阶段交接总预算 180 秒、最多 3 次，优先换实例，否则确定性派发 |
| 巡检 | 单次 180 秒、无进展 90 秒、阶段总预算 900 秒 |
| 诊断 / 审计 | 单次 300 秒、无进展 120 秒、阶段总预算 1800 秒 |
| 执行（含应急保护） | 单次 300 秒、无进展 120 秒、阶段总预算 21600 秒 |
| 失败重试 | 最多 3 次执行失败，5 秒指数退避、最高 60 秒，加 0–4 秒稳定抖动；失败实例冷却 30 秒 |
| 等待后重新派发 | 不算执行故障；新 assignment / 递增 attempt，阶段最多派发 32 次，仍受原总预算限制 |
| 审批等待 | 使用原审批 deadline；维修最多等待 4 小时；两者都不得超出阶段总截止和 Context TTL |
| 告警 | 持久化责任角色 store_manager、15 分钟响应期限、固定去重 ID、领取和投递状态 |

参数和版本在 Context 第一次初始化时写入 `recovery.policy`。硬截止从尝试开始时间计算；阶段总截止从进入阶段时间计算，包含排队、退避和人工等待。旧快照从原创建时间和已有 checkpoint 初始化一次，重启不刷新预算。部署期间改变代码中的默认策略只影响新上下文；未识别的策略版本拒绝继续执行。

`recovery.phases` 的状态包括 queued、running、retry_wait、waiting_capacity、waiting、manual_intervention、completed。业务事故状态与这些协调状态独立。预算耗尽、非重试故障、等待超时以及无法确认的操作结果进入明确的人工处置状态；保留已生效的保护措施，不伪造成功 checkpoint。

## Worker 接口与副作用恢复

原接口参数保留，以下协议变化需要 Worker YAML 一起更新：

- `runtime_tool` 成功后也返回新的 `context_version`，后续请求使用此版本。版本冲突读取 `runtime_snapshot`，不要覆盖别人的进展。
- `runtime_reassign` 使用同一个恢复调度器；退避或容量等待时返回 `assignment=null` 和 `recovery`，不保证立即生成后继。Worker 等待 poll 获得新任务。
- `runtime_progress` 只接收标准租约三字段。服务端核对新增的有效读数、人工证据、审批/维修状态或业务回执；重复查询产生的 audit_id、重复文本、旧证据消失都不算进展。即便有新证据，也不能刷新硬截止。
- `runtime_fail` 加 `reason`：transient、rate_limited 可退避；forbidden、invalid_input、stale_evidence、unknown_outcome 直接升级。超时由服务端自行识别，无需 Worker 上报。
- `runtime_wait` 加 `kind=approval/repair`、`reference=原 approval_id/workorder_id`。服务端检查对象属于当前事件且确实待处理。assignment 进入 waiting 并释放实例占用，不能再心跳、工具调用或 complete。巡查发现原对象 approved / done / closed 后生成新任务；工单完成只唤醒执行者，不等于设备恢复或审计通过。

重派前核验 `recovery.operations` 中原始 idempotency_key 对应的持久化回执。回执缺失属于 unknown_outcome，转人工核验；不假设外部操作没有发生。相同工具和动作必须保留原幂等键，同一轮维修不能另起 action_id 重复下单。新一轮独立审计返工由 `runtime_reopen` 归档旧任务，并保留恢复预算与历史操作记录。

当前 runtime 允许的业务适配器是本项目的同步数据库工具：业务变更、审计、回执和恢复元数据在一个短事务内落库，工具结束后再次核验截止，迟到结果会回滚本地副作用。模型运行位于外部 Worker，不占这些事务。**尚未接入事务外的真实维修/POS 网络写入**；未来接入时必须拆成短事务记录意图、事务外带稳定幂等身份调用、短事务对账提交。关闭 HTTP socket 或取消模型不能撤销外部副作用，不宣称 exactly-once。

检测、诊断及审计交接前检查最新 GOOD 温度读数：不是未来数据且距服务端时间不超过 5 分钟，时间按实际时区比较。生产默认使用运行时钟；只有测试明确注入 evidence_clock 才使用演练虚拟时间。这是恢复链的基础时效门，不代表已经完成批次证据绑定和完整风险暴露评估，剩余工作见统一待办。

## 人工恢复与通知 Outbox

可在服务端身份配置中另外绑定 `actor=Human` 的运维身份。它不属于五个 Agent，也不能领取 Worker 任务；不要把此凭证注入模型。

`runtime_resume(incident_id, expected_version, stage, reason)` 仅允许同门店 Human 在人工处置阶段调用。它记录操作人、原因与时间，最多授予一次额外恢复机会，不延长原始总截止、不绕过回执核验、不生成业务成功。原始总预算已耗尽的事件保留保护并转线下处置，不能借 resume 无限复活旧租约。

`runtime_notifications(incident_id)` 为独立通知适配器领取最多 10 个告警，租约 60 秒。`runtime_notification_result(incident_id, notification_id, attempt, delivered, receipt)` 只接受当前领取者及当前投递代次；失败后退避，最多 5 次，崩溃未回报也计次数。外部渠道应使用 notification_id 去重，因为本系统是至少一次投递。投递耗尽保留 delivery_failed，供独立监控处理。

这两个接口均要求同范围 Human 运维身份。本轮只实现并验证 Outbox 协议，没有连接或发送真实短信、飞书、邮件，也没有真实责任人通讯录。运维接入时须把 store_manager 映射为实际值班人，并配置接收渠道与升级规则。投递成功与业务问题已处理是两回事。

## 受控应急停售

`DIANXUN_EMERGENCY_CONTAINMENT` 默认为关闭。只有部署方预授权设置为 `1`，主控才可调用 `runtime_emergency(incident_id, expected_version)`；服务端仍要求两条不同采样时间、5 分钟内、质量 GOOD、超过现有温度阈值的读数，且当前设备与批次范围一致。模型超时或数据失联本身不触发自动停售。

通过后创建独立 `EMERGENCY_CONTAIN` 任务，由同门店健康 Executor 经 runtime_tool 执行被授权批次的 apply_sales_hold。该租约不能调用解禁工具，也不能扩大批次范围。完整停售回执只写独立应急完成记录，不写 DETECT checkpoint。正常巡检恢复后，CONTAIN 读取 containment_required 与现有回执汇合，已有保护无需重做；后续解禁和关闭仍需要原审批与独立审计。

当前没有登记真实门店自动处置授权，因此不在部署配置中开启开关。基于“数据失联”的预授权保护策略仍需真实场景与责任方确认，不将其默认为食品风险成立。

## 监测、升级与回滚

配置 runtime 的 HTTP 服务在 `/ready`、`/health` 检查扫描器健康。扫描失败立即不就绪；成功扫描超过 15 秒未更新也不就绪，并拒绝新委派、工具写入、完成、人工恢复和应急请求。`/live` 只表示进程可响应。只读快照和通知记录在条件允许时仍可获取，过期 Context 不会静默消失。

`/metrics` 暴露 `dianxun_recovery_*`：扫描年龄、耗时、失败数、最大排队年龄、容量等待、重试等待、业务等待、人工处置、回执未知、预算耗尽、失效任务和未完成通知数。无租户、Worker、事件、Trace 或 Token 标签。应由服务外监控抓取 readiness/metrics 并监督进程；数据库整体不可用时不能依赖数据库内 Outbox 发送自身故障通知。

兼容字段：WorkerAssignment 增加 hard_deadline、progress_deadline、last_progress_at、progress_fingerprint；TaskContext 增加 recovery。在线健康和冷却存放在同范围 `@runtime-workers:<store>` 元数据 Context，没有 Token、没有新数据表。老 Worker 需要先读取快照和更新上述版本/等待协议。Worker ZIP 仍使用已固定的包地址，新增规则通过五个 Worker YAML 注入。

升级前备份业务库和配置。回滚先停新委派、停止扫描器与 Worker，核对在途回执、导出 recovery 状态；只允许回退到认识新增字段和 waiting 状态的兼容读写版本。禁止用完全不识别这些字段的旧程序直接读取新快照，也不能删除记录、重置截止或恢复旧租约。

## 工具指标

| 指标 | 类型 | 标签 | 含义 |
|---|---|---|---|
| `dianxun_mcp_tool_calls_total` | Counter | `tool`, `outcome` | 工具调用量及 success/error 结果 |
| `dianxun_mcp_tool_duration_seconds` | Histogram | `tool` | 进程内工具执行耗时 |
| `dianxun_mcp_auth_failures_total` | Counter | 无 | 被拒绝的 Bearer 鉴权次数 |

指标仅使用固定 tool/outcome；其他身份、事件、租户和自由文本不作标签。累计值为进程内统计，重启清零；Prometheus 持续抓取才能形成长期样本。

## SLO 口径

下表是目标，不是当前成绩。正式启用前应在目标拓扑中确认流量定义、维护窗口、错误排除规则和告警责任人。

| 服务指标 | 初始目标 | 仓库内证据 | 生产实测 |
|---|---:|---|---|
| MCP 月可用性 | ≥ 99.9% | `/health` 路由和 HTTP 测试通过；没有月度样本 | 未取得 |
| MCP 工具 p95 | ≤ 300 ms | 已有 histogram；未做可复现目标环境压测 | 未取得 |
| MCP 工具错误率 | ≤ 1% | success/error 可计数；合成测试不代表生产流量 | 未取得 |
| 鉴权失败检测 | 5 分钟内发现异常增长 | Counter 与本地负向测试已实现 | 未取得 |
| 协调恢复 RTO | ≤ 5 分钟 | 本地演练验证恢复语义，但未计入真实部署启动/网络时间 | 未取得 |
| 协调恢复 RPO | 最近一次成功提交 | SQLite 版本条件更新与 checkpoint 恢复通过 | 未验证磁盘损坏、备份或跨机恢复 |

本表 300 ms 是端到端初始目标，须在目标环境单独测量；当前工具 histogram 不包含模型和完整网络往返。现行传输限制见[MCP 可靠性](../技术说明.md)。

PromQL 参考：

```promql
# 5 分钟工具错误率
sum(rate(dianxun_mcp_tool_calls_total{outcome="error"}[5m]))
/
clamp_min(sum(rate(dianxun_mcp_tool_calls_total[5m])), 0.000001)

# 全工具 p95
histogram_quantile(
  0.95,
  sum by (le) (rate(dianxun_mcp_tool_duration_seconds_bucket[5m]))
)

# 鉴权失败增长
increase(dianxun_mcp_auth_failures_total[5m])
```

告警必须考虑低流量误差；没有最小请求量时，不应仅凭单个错误触发“错误率超标”。`/metrics` 默认无 Bearer 鉴权，部署时应只允许本机/监控网访问，或由反向代理单独限制，不要暴露到公网。

## 确定性协调恢复演练

生成或更新证据：

```bash
uv run python scripts/recovery_drill.py
```

CI 只校验，不改文件：

```bash
uv run python scripts/recovery_drill.py --check
```

证据位于 [`../../evidence/operations/recovery-drill.json`](../../evidence/operations/recovery-drill.json)，固定验证：

1. SQLite `journal_mode=wal`。
2. stale writer 被 `expected_version` 条件更新拒绝。
3. 有效 lease 不能重派。
4. lease 过期后并发语义收敛到唯一 successor，且 `attempt=2`、predecessor 可追踪。
5. 进程重建 `ContextBus/ContextCoordinator` 后从已完成 checkpoint 继续，不重做首阶段。
6. 五阶段 checkpoint 严格有序并最终完成协调 Context。

演练使用临时 SQLite、固定虚拟时间和合成 ID，不测试真实 AgentTeams Worker、网络、磁盘故障、托管 PolarDB、OSS 恢复、跨可用区容灾或业务 Incident 关闭。

## 故障处置顺序

1. 先区分 `/live` 存活与 `/ready` 就绪，核对扫描器、进程日志和 `/metrics`；不要记录 Token。
2. 若仅 MCP 进程失败，由进程管理器重启；重启后先执行只读查询，再允许受控写。
3. 独立 ContextBus 按 checkpoint 计算 resume_plan；生产入口 `/runtime` 由恢复扫描器按原始截止/预算、健康容量和回执补扫。未知回执或预算耗尽转人工，禁止刷新预算无限重派。
4. 若 SQLite 文件或磁盘异常，停止写入并保存数据库、`-wal`、`-shm` 及日志副本；未验证备份完整性前不要覆盖原文件。
5. PolarDB/OSS 故障必须使用目标环境 Runbook 和经审批的恢复流程；本地脚本不能替代。
6. 恢复后核对 assignment/predecessor、checkpoint/context version、MCP 审计引用与业务 `IncidentService` 状态。Context `completed` 不能替代业务 `RESOLVED/CLOSED`。

## 验证边界

恢复测试使用真实本地 HTTP、SQLite、后台线程、多个 RuntimeService、可控时钟及故障注入；包含主控、备用/容量、截止、等待、旧租约、回执、通知代次与应急汇合。执行结果统一见[测试矩阵](../测试覆盖矩阵.md)。PostgreSQL 条件测试需隔离实例与显式 reset 授权，本地通过不代表托管数据库、实际 Worker 调度、外部通知或门店已验收；未完成项目只在[待办](../待办.md)跟踪。
