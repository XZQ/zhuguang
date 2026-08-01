# Skill restock-order-gen — 补货单生成

> 店巡 Agent · S4/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:restock-order-gen
- **用途**:基于安全库存模型(日均销量 × 补货周期 × 系数 − 在库 − 在途),生成补货建议单,支持审批与调整
- **输入**:`store_id`、`sku_list[]`(可空=全量)、`urgency(常规/紧急)`、`constraints{预算上限, 供应商偏好}`
- **输出**:`RestockOrder { store_id, items[{sku, suggest_qty, current_stock, daily_sales, days_to_empty, priority}], total_amount, confidence, comments }`
- **调用条件**:缺货/低库存异常处置时;生成前校验库存实时快照,防止并发覆盖
- **依赖工具**:MCP-wms(实时库存)、MCP-pos(销量趋势)、MCP-price(进价/售价)、供应商目录
- **失败处理**:库存快照冲突 → 锁冲突重试 3 次后放弃本次并提示人工;供应商停供 → 建议替代供应商清单;金额超预算 → 拆分为"紧急必补 + 常规可延"
- **安全边界**:**写操作,只生成草稿单,不直接提交采购**;必须经店长/采购审批;涉及金额 > 5000 元强制走审批流 MCP
- **复用价值**:中高。零售通用,模型可参数化复用(餐饮改效期权重)
- **协同关系**:处置 Executor 调用;审批后单子经 RocketMQ 事件回传,状态机 approving → executing
