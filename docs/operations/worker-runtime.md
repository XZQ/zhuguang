# Worker 运行接口

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

新增 runtime_contexts 表，协调版本和领域变更使用同一个业务数据库事务；嵌套操作使用
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

## 故障恢复协议 v2

见[故障恢复运行手册](runtime-recovery.md)，包含后台扫描器、在线与容量、分层截止、等待/唤醒、Human 运维、通知 Outbox、应急开关及兼容回滚。运行接口改造已进入本地实现验证，目标平台演练另行验收。
