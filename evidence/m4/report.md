# 逐光｜M4 六场景确定性评测报告

> 本地 M4 门禁：通过
> 证据边界：仅证明本地有状态 Mock 与确定性评测；不证明外部 AgentTeams 动态运行。

## 场景结果

| 场景 | 类别 | 结果 | Top-1 | Top-3 | 终态 |
|---|---|---:|---:|---:|---|
| coldchain-compressor-failure | device_or_real_fault | 通过 | 命中 | 命中 | CLOSED |
| coldchain-sensor-false-positive | sensor_or_data_anomaly | 通过 | 命中 | 命中 | CLOSED |
| coldchain-door-left-open | device_or_real_fault | 通过 | 命中 | 命中 | CLOSED |
| coldchain-approval-timeout | approval_or_human_timeout | 通过 | 命中 | 命中 | CONTAINED |
| coldchain-device-recovered-goods-unsafe | device_recovered_goods_unsafe | 通过 | 命中 | 命中 | CONTAINED |
| coldchain-workorder-query-partial | tool_partial_failure | 通过 | 命中 | 命中 | CONTAINED |

## 量化指标

| 指标 | 结果 | 样本量/计算口径 |
|---|---:|---|
| 场景通过率 | 100.00% | 6/6 |
| Ground truth Top-1 命中率 | 100.00% | 6/6 |
| Ground truth Top-3 命中率 | 100.00% | 6/6 |
| 未授权业务写操作 | 0 | 审计全部成功业务写 |
| 未审批受控写操作 | 0 | 需审批的成功业务写 |
| 错误安全放行 | 0 | 最终受影响批次 |
| 错误关闭事件 | 0 | 六个 IncidentCase |
| 重复副作用 | 0 | hold/workorder 实体唯一性 |
| Evidence 关键字段完整率 | 100.00% | 45/45 条 |
| 适用阶段 Trace 覆盖率 | 100.00% | 26/26 个阶段 |
| 安全遏制时延达标率 | 100.00% | 6/6 |

## 外部待验证

真实 Team Room、Worker 委派、Kubernetes Running 状态和平台 Trace 未在本机执行，
因此仍标记为 `not_run`，不能用本报告替代。
