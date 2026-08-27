# price-tag-check

> 当前优先级：P2 补充场景；不进入冷柜 P0 Worker ZIP。

- 名称：`price-tag-check`
- 用途：比较系统价、价签价和 POS 价，识别不一致。
- 输入：门店、SKU、检查时间。
- 输出：不一致项、严重度和建议。
- 调用条件：价签补充入口。
- 依赖：改造前 price/POS CSV Adapter。
- 失败处理：数据缺失时降级为可用来源比对并标记 partial。
- 安全边界：当前只做本地演示；真实改价审批、价签设备和生产回滚未接入。
- 复用价值：可复用于零售价格一致性检查。
- 协同关系：由历史 Sentry/Executor 流程调用，不属于冷柜 P0 主链。

回归入口：

```powershell
uv run python demo/run_supplementary.py price-tag
```

统一清单见 [`../03-Skill九要素卡.md`](../03-Skill九要素卡.md)。
