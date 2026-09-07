# Worker 运行接口

`/runtime` 提供独立的 MCP JSON-RPC 工具目录，原 `/mcp` 的 12 个 P0 业务工具保持兼容。
领域实现仍仅位于 src/dianxun。Worker ZIP 保持已有字节和固定下载地址；新增运行接口规则
通过 Worker YAML 的 agents 字段传入，不向包内复制 Python 实现。

服务端从 `DIANXUN_RUNTIME_TOKENS_JSON` 读取 Token 到身份的映射。每个值必须包含
`actor`、`worker_id`、`tenant_id`、`store_id` 四个非空字段。允许的角色为 Orchestrator、
Sentry、Diagnoser、Executor、Auditor；一个 worker_id 不得绑定多个角色或门店。
使用秘密管理器配置 `dianxun-agent-identities/runtime-tokens-json`，并由 AgentTeams
运行环境为对应 Worker 的 MCP 连接注入其 Bearer Token。Token 不写进 YAML、聊天或 Trace。
运行接口不接受旧共享 Token，也不接受请求体自报角色。

## 调用顺序

1. Orchestrator 调用 runtime_open(incident_id, device_id)。租户、门店从身份绑定获得，
   设备和批次范围由数据库校验；重复 open 只能读取同一设备的既有事故。
2. runtime_snapshot 返回 incident、context 和 remaining_stages。
3. Orchestrator 用 runtime_assign(incident_id, worker_id, expected_version) 委派下一阶段。
4. Worker 用 runtime_heartbeat 延长租约；返回的新 context_version 用于后续请求。
5. Executor 用 runtime_tool 调用当前 assignment 允许的业务工具。arguments 保留稳定的
   action_id/idempotency_key；审批必须由独立 Human 身份经原业务接口作出。
6. Worker 用 runtime_complete 提交交接。请求仅包含 incident_id、assignment_id、
   expected_version；不接受业务状态字段。检测、诊断、风险评估和审计由规范 Skill 执行。
7. completed=false 表示核验或执行未满足条件，没有成功 checkpoint；修复外部事实后可重试。
   已完成请求重放返回 replayed=true。超时由 Orchestrator runtime_reassign 创建唯一 successor。

八个协调步骤实现五个领域阶段：DETECT/Sentry、CONTAIN/Executor 对应 DETECT_CONTAIN；
DIAGNOSE_DECIDE/Diagnoser；EXECUTE/Executor；VERIFY/Auditor、RELEASE/Executor、
FINAL_VERIFY/Auditor；LEARN/Auditor。无需解禁的场景中 RELEASE 只检查并完成空操作。
查询 partial 或失败不能写成功 checkpoint。LEARN 再次核验后才调用 IncidentService 关闭。

## 持久化与兼容

新增 runtime_contexts 表，协调版本和领域变更使用同一个业务数据库事务；SQLite 本地自动
建表，PostgreSQL 升级先由迁移管理员执行 core 和 security profile。后者启用 tenant/store
RLS 并授予 runtime 表权限。升级前备份；回滚停止 /runtime 流量、回退程序，保留新增表，
不删除业务数据。旧的独立 ContextBus 数据不自动导入，避免把演练 checkpoint 当真实任务。

`python -m unittest tests.test_worker_runtime -v` 使用实际本地 HTTP 和数据库，覆盖闭环、
重启、幂等重放、partial 查询、事务回滚和身份/租约拒绝。设备读数和人工审批是测试 fixture。
真实 AgentTeams 平台身份注入、Team Room、托管 PolarDB 和外部维修系统仍需要目标环境验收。
