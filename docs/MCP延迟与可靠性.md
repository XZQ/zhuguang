# MCP 延迟与可靠性

> 复核日期：2026-09-12。当前为标准库 BoundedHTTPServer 独立 HTTP 服务，默认监听 127.0.0.1:8080。没有正式目标环境延迟基准，不承诺 P99 或生产 SLA。

## 1. 当前传输限制

| 项目 | 行为 |
|---|---|
| 连接 | 默认最多 32 个；容量满返回 HTTP 503 并关闭连接 |
| 截止 | 默认 10 秒绝对截止，覆盖缓慢请求头和分段滴入的 body；不靠每次读取重置 timeout |
| 请求体 | 最大 1 MiB，超限返回 413 |
| 请求头 | 拒绝重复 Content-Length、Transfer-Encoding 及非法长度；可在读取超大 body 前拒绝 |
| 身份 | /mcp 为共享只读或 Actor Token；/runtime 为独立 Worker/运维身份及 tenant/store scope |
| 健康 | /live 为存活；/ready 和 /health 检查数据库、初始化、Skill 契约及配置 runtime 时的扫描器 |
| 指标 | /metrics 提供固定低基数工具/恢复指标，默认无鉴权，限定监控网访问 |

实现：[transport](../src/dianxun/mcp/http_transport.py)、[server](../src/dianxun/mcp/server.py)。HTTP 状态、JSON-RPC 错误和工具 Envelope 的 partial/error 是不同层次；不能仅凭 HTTP 200 判断业务成功。

## 2. 重试与副作用

/runtime 已有后台巡查、有限重试、退避、健康容量选择、硬截止、总预算、等待和回执核验。默认参数统一见[恢复手册](operations/runtime-recovery.md)；这不是通用 HTTP 客户端重试库，也不证明真实网络故障已演练。

- 同键同请求可重放，同键异请求拒绝；换 key 不能绕过 action 唯一约束重复创建副作用。
- 重派保留原 action_id/idempotency_key 并核对持久化回执；未知结果转人工，响应丢失不能视作未执行。
- 权限、输入和过期证据不能靠无限重试解决。审批/维修等待使用原对象和截止时间，不循环建单。
- 取消模型或关闭 socket 不能撤销外部操作；本地事务验证不证明未来真实网络写入的 exactly-once。

仓库没有 requests/tenacity 统一客户端、通用 CircuitBreaker、gRPC 或同进程嵌入客户端。未来引入前明确幂等性、截止传递、总尝试预算、结果对账和失败注入，不能把规划代码写成已有功能。

## 3. 性能与监控

SLO 目标、PromQL、恢复操作和生产待办统一见[SLO 与恢复演练](operations/SLO与恢复演练.md)。工具 histogram 是进程内执行耗时，不包括模型推理与完整外部网络往返；端到端目标须单独观测。

压测前固定代码版本、硬件、数据库/数据量、读写比例、并发、预热、采样数与错误判定，保留原始样本和 p50/p95/p99、吞吐、错误率、恢复时长。没有这些记录时不填写示例毫秒值或“通过”。

## 4. 验证

~~~bash
uv run python -W error::ResourceWarning -m unittest -v tests.test_http_transport tests.test_adversarial_hardening tests.test_worker_runtime tests.test_runtime_recovery
~~~

[HTTP 测试](../tests/test_http_transport.py)使用真实本地慢速 socket、连接容量、请求头/body 和数据库故障探针。[恢复测试](../tests/test_runtime_recovery.py)使用本地 HTTP、SQLite 与故障注入。场景 F 是本地 query_workorder partial，验证证据不全阻断关闭，不是崩溃、断网或压力测试。

PolarDB 条件集成和真实 AgentTeams/外部系统验收分别执行。汇总见[测试覆盖矩阵](测试覆盖矩阵.md)。
