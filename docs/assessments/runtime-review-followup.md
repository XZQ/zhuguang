# Worker 运行接口复核修复（2026-09-12）

本次针对七项本地修复的再次 review，补齐三个已复现问题，不改变 P0 MCP 的 12 个工具。

## 修复和回归

| 问题 | 修复 | 回归证据 |
|---|---|---|
| `/runtime` 写操作返回失败，业务数据仍被提交 | SQLite/PostgreSQL 嵌套事务使用保存点，失败操作回滚；错误结果不更新 Incident 动作聚合 | 真实 SQLite trigger 拒绝幂等记录插入，核对业务、动作、审计均无残留；解除故障后同一幂等键重试仅执行一次；内外层回滚分别验证 |
| 诊断响应丢失后无法恢复风险评估 | 阶段完整 output 随 checkpoint 原子保存；快照与重放读取原输出 | 诊断后新建 RuntimeService，核对重放与快照中的批次评估和首次结果一致，且版本不变；旧 checkpoint 明确返回输出不可用 |
| 审计失败后无法重新处置 | Orchestrator 通过 `runtime_reopen` 请求服务器重新核验，从 CONTAIN 重走闭环，归档旧租约和 checkpoint | 首次审计失败以及 LEARN 前商品重新不安全均能完成再次处置和独立核验；验证越权、旧版本、partial、核验通过时拒绝重开；旧租约不能写入或完成 |

阶段输出与事件状态、checkpoint 共用业务事务，重新处置发生保存失败时全部回滚。
旧执行轮次的输出保留在 `context.transitions`，新租约延续 predecessor 和 attempt，
不会复用旧 assignment_id。商品处置仍需独立 Human 审批，Orchestrator 不自报验证成功。

## 兼容与部署边界

- 本次无新依赖、无新表；checkpoint JSON 新增可选 output 字段，旧数据可读取。
- 回退旧程序时需要保留新字段读取兼容，不能删改历史业务数据来绕过兼容问题。
- Worker YAML 和调用说明同步新工具；原 `/mcp` 保持兼容。
- PostgreSQL 条件集成测试增加真实 SQL 异常后的保存点恢复检查；未配置隔离实例时仍跳过，不能视为已执行。
- 本地设备、审批和维修回执仍为合成 fixture；本次不证明 AgentTeams、托管数据库、Docker 或生产部署已验收。
- 本地验证结果见当前[测试覆盖矩阵](../测试覆盖矩阵.md)；GitHub CI 需按发布的 SHA 单独核实。
