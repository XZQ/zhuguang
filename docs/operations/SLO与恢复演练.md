# SLO 与恢复演练

> 本文把“目标”“仓库内探针”“生产实测”分开记录。当前只有本地确定性证据，不能据此宣称生产 SLO、AgentTeams、托管 PolarDB 或 OSS 灾备已经达标。

## 1. 可观测性接口

MCP 服务提供两个只读端点：

- `GET /health`：进程与工具注册信息。
- `GET /metrics`：Prometheus text format 0.0.4。

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/metrics
```

指标固定为：

| 指标 | 类型 | 标签 | 含义 |
|---|---|---|---|
| `dianxun_mcp_tool_calls_total` | Counter | `tool`, `outcome` | 工具调用量及 success/error 结果 |
| `dianxun_mcp_tool_duration_seconds` | Histogram | `tool` | 进程内工具执行耗时 |
| `dianxun_mcp_auth_failures_total` | Counter | 无 | 被拒绝的 Bearer 鉴权次数 |

`tool` 只能取已声明的 12 个 P0、3 个 P1 工具或 `unknown`，`outcome` 只能取 `success/error`。tenant、incident、request、trace、actor、用户、Token 和自由文本不得作为标签。指标为进程内累计值，服务重启会清零；生产应由 Prometheus 持久抓取，不从单次 scrape 推断长期可用性。

## 2. SLO 口径

下表是目标，不是当前成绩。正式启用前应在目标拓扑中确认流量定义、维护窗口、错误排除规则和告警责任人。

| 服务指标 | 初始目标 | 仓库内证据 | 生产实测 |
|---|---:|---|---|
| MCP 月可用性 | ≥ 99.9% | `/health` 路由和 HTTP 测试通过；没有月度样本 | 未取得 |
| MCP 工具 p95 | ≤ 300 ms | 已有 histogram；未做可复现目标环境压测 | 未取得 |
| MCP 工具错误率 | ≤ 1% | success/error 可计数；合成测试不代表生产流量 | 未取得 |
| 鉴权失败检测 | 5 分钟内发现异常增长 | Counter 与本地负向测试已实现 | 未取得 |
| 协调恢复 RTO | ≤ 5 分钟 | 本地演练验证恢复语义，但未计入真实部署启动/网络时间 | 未取得 |
| 协调恢复 RPO | 最近一次成功提交 | SQLite 版本条件更新与 checkpoint 恢复通过 | 未验证磁盘损坏、备份或跨机恢复 |

`docs/MCP延迟与可靠性.md` 中更激进的本地 SQLite 延迟数值仍是微基准设计目标；本表的 300 ms 是待目标环境确认的端到端初始目标，两者均不是已实测 SLA。

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

## 3. 确定性协调恢复演练

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

## 4. 故障处置顺序

1. 先检查 `/health`、进程日志和 `/metrics` 的错误/鉴权增长；不要记录 Token。
2. 若仅 MCP 进程失败，由进程管理器重启；重启后先执行只读查询，再允许受控写。
3. 若协调进程中断，从持久化 checkpoint 计算 `resume_plan`；有效 lease 未过期前禁止重派，过期后必须走唯一 successor 流程。
4. 若 SQLite 文件或磁盘异常，停止写入并保存数据库、`-wal`、`-shm` 及日志副本；未验证备份完整性前不要覆盖原文件。
5. PolarDB/OSS 故障必须使用目标环境 Runbook 和经审批的恢复流程；本地脚本不能替代。
6. 恢复后核对 assignment/predecessor、checkpoint/context version、MCP 审计引用与业务 `IncidentService` 状态。Context `completed` 不能替代业务 `RESOLVED/CLOSED`。

## 5. 生产验收待办

- 在目标环境连续采集至少一个代表性周期的请求量、p50/p95/p99、错误率和可用性。
- 完成进程重启、节点故障、数据库连接中断、备份恢复和告警通知演练，记录 RTO/RPO 实测值。
- 在真实 AgentTeams Run 中验证 heartbeat、超时 successor、checkpoint 恢复和 MCP Actor 绑定。
- 在隔离 PolarDB/OSS 环境验证迁移、RLS、cron、归档哈希/行数和恢复，不执行未经审批的源删除。
- 只有完成以上证据后，才把“目标/未取得”更新为生产实测结果。
