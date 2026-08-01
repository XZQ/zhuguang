# AGENTS — 店巡 Worker 行为规则

> 闭环状态机驱动,对应赛题 1.3 八步闭环。

## 闭环状态机
```
created → detecting → diagnosing → approving → executing → verifying → reviewing → closed
                                                              ↓
                                                         reopened → diagnosing (二次)
```

## 8 步闭环行为

### 1. 任务输入(detecting)
Sentry 接收 scheduled/event 触发,聚合 POS/WMS/IoT/价格多源数据。
- 调用 `anomaly-detect` Skill,输出带置信度的异常清单
- 数据源降级标记 partial/degraded,不阻塞流程

### 2. 任务拆解(diagnosing)
Orchestrator 按严重度排序异常,逐个派给 Diagnoser。
- Diagnoser 调 `cross-store-benchmark` 选对标指标做横向对比
- 调 `rootcause-drilldown` 维度下钻,输出多假设根因报告

### 3. 上下文传递
通过共享上下文总线传递:异常清单 → 根因报告 → 处置动作 → 验证结果。
- 对应 AgentTeams Matrix Team Room + MinIO 共享存储
- 关键字段贯穿:诊断结论、处置状态、审批意见

### 4. 工具调用(executing)
Executor 按异常类型调对应 Skill + MCP 工具:
- 冷柜超温 → `work-order-dispatch`(>2000 审批)
- 缺货 → `restock-order-gen`(>5000 审批)
- 价签 → `apply_price_change`(>20SKU 审批,幂等 key)
- 所有写操作经 `create_approval` 审批流

### 5. 结果验证(verifying)
Auditor 复测:温度回基线 / 库存回升 / 价格三方一致。
- 失败触发 reopened 回 diagnoser 二次处置

### 6. 执行证据沉淀
全链路 Trace 落 SQLite(生产 PolarDB),覆盖 Skill/MCP/Agent/LLM。
- 遵循 OpenTelemetry GenAI 语义

### 7. 审批与回滚
- 超阈值金额/批量调价/跨店调拨 → 人工确认,超时降级为"仅通知"
- 处置指令留快照,验证失败自动回滚(调价回退/调拨取消)

### 8. 经验沉淀(reviewing)
Auditor 调 `review-report`:
- 知识条目按置信度过质量门(≥0.6 入库,<0.6 待人工)
- 输出 Skill 更新建议(调阈值/补假设),驱动飞轮
- 下次 Diagnoser 的 RAG 检索命中 → 诊断更准
