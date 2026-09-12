# Worker 故障恢复运行手册

本实现对应[待办 01](../competition/finals/06-待办01-多Agent故障恢复技术方案.md)。五个业务角色为 Orchestrator、Sentry、Diagnoser、Executor、Auditor。服务端负责恢复调度，IncidentService 仍是业务终态唯一入口。这里的默认参数是本地演练起点，需要在目标平台测量后校准。

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

检测、诊断及审计交接前检查最新 GOOD 温度读数：不是未来数据且距服务端时间不超过 5 分钟，时间按实际时区比较。生产默认使用运行时钟；只有测试明确注入 evidence_clock 才使用演练虚拟时间。这是恢复链的基础时效门，不代表已经完成待办 02 的批次证据绑定和完整风险暴露评估。

## 人工恢复与通知 Outbox

可在服务端身份配置中另外绑定 `actor=Human` 的运维身份。它不属于五个 Agent，也不能领取 Worker 任务；不要把此凭证注入模型。

`runtime_resume(incident_id, expected_version, stage, reason)` 仅允许同门店 Human 在人工处置阶段调用。它记录操作人、原因与时间，最多授予一次额外恢复机会，不延长原始总截止、不绕过回执核验、不生成业务成功。原始总预算已耗尽的事件保留保护并转线下处置，不能借 resume 无限复活旧租约。

`runtime_notifications(incident_id)` 为独立通知适配器领取最多 10 个告警，租约 60 秒。`runtime_notification_result(incident_id, notification_id, attempt, delivered, receipt)` 只接受当前领取者及当前投递代次；失败后退避，最多 5 次，崩溃未回报也计次数。外部渠道应使用 notification_id 去重，因为本系统是至少一次投递。投递耗尽保留 delivery_failed，供独立监控处理。

这两个接口均要求同范围 Human 运维身份。本轮只实现并验证 Outbox 协议，没有连接或发送真实短信、飞书、邮件，也没有真实责任人通讯录。运维接入时须把 store_manager 映射为实际值班人，并配置接收渠道与升级规则。投递成功与业务问题已处理是两回事。

## 受控应急停售

`DIANXUN_EMERGENCY_CONTAINMENT` 默认为关闭。只有部署方预授权设置为 `1`，主控才可调用 `runtime_emergency(incident_id, expected_version)`；服务端仍要求两条不同采样时间、5 分钟内、质量 GOOD、超过现有温度阈值的读数，且当前设备与批次范围一致。模型超时或数据失联本身不触发自动停售。

通过后创建独立 `EMERGENCY_CONTAIN` 任务，由同门店健康 Executor 经 runtime_tool 执行被授权批次的 apply_sales_hold。该租约不能调用解禁工具，也不能扩大批次范围。完整停售回执只写独立应急完成记录，不写 DETECT checkpoint。正常巡检恢复后，CONTAIN 读取 containment_required 与现有回执汇合，已有保护无需重做；后续解禁和关闭仍需要原审批与独立审计。

本轮没有真实门店自动处置授权，因此不在部署配置中开启开关。基于“数据失联”的预授权保护策略仍需真实场景与责任方确认，不将其默认为食品风险成立。

## 监测、升级与回滚

配置 runtime 的 HTTP 服务在 `/ready`、`/health` 检查扫描器健康。扫描失败立即不就绪；成功扫描超过 15 秒未更新也不就绪，并拒绝新委派、工具写入、完成、人工恢复和应急请求。`/live` 只表示进程可响应。只读快照和通知记录在条件允许时仍可获取，过期 Context 不会静默消失。

`/metrics` 暴露 `dianxun_recovery_*`：扫描年龄、耗时、失败数、最大排队年龄、容量等待、重试等待、业务等待、人工处置、回执未知、预算耗尽、失效任务和未完成通知数。无租户、Worker、事件、Trace 或 Token 标签。应由服务外监控抓取 readiness/metrics 并监督进程；数据库整体不可用时不能依赖数据库内 Outbox 发送自身故障通知。

兼容字段：WorkerAssignment 增加 hard_deadline、progress_deadline、last_progress_at、progress_fingerprint；TaskContext 增加 recovery。在线健康和冷却存放在同范围 `@runtime-workers:<store>` 元数据 Context，没有 Token、没有新数据表。老 Worker 需要先读取快照和更新上述版本/等待协议。Worker ZIP 仍使用已固定的包地址，新增规则通过五个 Worker YAML 注入。

升级前备份业务库和配置。回滚先停新委派、停止扫描器与 Worker，核对在途回执、导出 recovery 状态；只允许回退到认识新增字段和 waiting 状态的兼容读写版本。禁止用完全不识别这些字段的旧程序直接读取新快照，也不能删除记录、重置截止或恢复旧租约。

## 验证边界

`tests/test_runtime_recovery.py` 使用真实本地 HTTP、SQLite、后台线程、两个独立 RuntimeService、可控时钟及故障注入。覆盖空心跳、硬截止、健康备用、主控恢复、容量、并发唯一后继、重试预算、失效证据、审批/维修等待、丢失响应、回执未知、迟到回滚、应急汇合、升级兼容与通知代次。PostgreSQL 并发恢复演练编入现有条件集成测试，需要隔离测试库及显式 reset 授权。

SQLite 通过不等于 PostgreSQL、AgentTeams 或真实门店已经通过。平台实例取消/替换、实际 Token 注入、外部工具对账和断网恢复仍需目标环境演练；这里不把本地 fixture 当作平台证据。

2026-09-12 本地验收记录：全量 134 项发现、132 通过、2 项 PostgreSQL 条件跳过；后续受影响接口复核 44 项通过，主控预算/旧快照/通知补验 3 项通过。Ruff、格式检查、事实一致性、六场景 6/6、消融门禁、恢复演练、Worker ZIP、wheel 隔离安装烟测及生成物重建通过。无 Docker 命令，镜像烟测未执行；PDF 未重导出，沿用历史文件。平台验收与部署仍待开展；代码发布以 Git 提交记录为准。
