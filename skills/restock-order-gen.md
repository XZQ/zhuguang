# restock-order-gen

> 当前优先级：P2 补充场景；不进入冷柜 P0 Worker ZIP。

- 名称：`restock-order-gen`
- 用途：基于库存和销量生成补货建议。
- 输入：门店、SKU、库存、销量、约束。
- 输出：建议数量、优先级和原因。
- 调用条件：缺货/低库存补充入口。
- 依赖：改造前 WMS/POS CSV Adapter。
- 失败处理：数据不足时返回降级建议，不提交采购。
- 安全边界：只生成建议；真实采购、预算审批和供应商下单未接入。
- 复用价值：可复用于其他库存补给场景。
- 协同关系：由历史 Executor 流程调用，不属于冷柜 IncidentService P0 链。

回归入口：

```powershell
uv run python demo/run_supplementary.py stockout
```

统一清单见 [`../docs/competition/03-Skill九要素卡.md`](../docs/competition/03-Skill九要素卡.md)。
