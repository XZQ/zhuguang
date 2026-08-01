# Skill work-order-dispatch — 工单派发与跟踪

> 店巡 Agent · S6/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:work-order-dispatch
- **用途**:将设备/设施类处置(冷柜维修、货架整修)生成工单,派发给维修服务商,跟踪状态与完成验证
- **输入**:`store_id`、`equipment_id`、`fault_summary`、`severity`、`budget_estimate`
- **输出**:`WorkOrder { id, store_id, equipment_id, assignee, sla_deadline, status(created→assigned→in_progress→done→closed), evidence_photos[] }`
- **调用条件**:诊断确认设备类根因后;金额 > 2000 元需先过审批
- **依赖工具**:MCP-workorder(维修服务商 API)、MCP-im(通知店长/服务商)、MCP-iot(维修后温度核验)
- **失败处理**:服务商拒单 → 自动转派第二顺位 + 通知总控;超 SLA 未响应 → 升级通知总部;审批超时 → 降级为"仅通知店长自修"
- **安全边界**:工单信息仅限本店 + 总部运营域;付款环节绝不由 Agent 直接执行(只生成待付款单)
- **复用价值**:中。行业绑定较深(设备维修),但工单状态机与超时升级逻辑可复用到所有"外部服务依赖"场景
- **协同关系**:处置 Executor 的执行工具之一;完成后由稽核 Auditor 触发 iot 温度核验完成闭环
