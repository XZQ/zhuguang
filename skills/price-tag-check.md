# Skill price-tag-check — 价签与促销合规校验

> 店巡 Agent · S5/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:price-tag-check
- **用途**:比对系统价格、货架价签价、收银价三方一致性,校验促销规则(组合折扣/限时价/会员价)是否冲突,输出价签异常与促销合规报告
- **输入**:`store_id`、`sku_list[]`、`check_time`
- **输出**:`PriceCheckReport { mismatches[{sku, system_price, tag_price, pos_price, rule_violation?, severity}], compliance_summary }`
- **调用条件**:日常巡检(每日)或促销上线前预检;收银价以 POS 流水为准
- **依赖工具**:MCP-pos(收银价)、MCP-price(系统价/促销规则)、价签系统(货架标签)
- **失败处理**:价签系统无响应 → 以"系统价 vs 收银价"两方比对降级执行;促销规则解析失败 → 该规则标黄提示人工
- **安全边界**:**纠错写操作(改价签/改收银价)必须审批**;批量调价(>20 SKU)强制人工确认;操作留痕可回滚
- **复用价值**:中高。零售、电商价格治理同构,合规角度可扩展到广告法违禁词等
- **协同关系**:巡检 Sentry 常规触发;严重不一致(收银价高于标价)直接升级给处置 Executor 走紧急审批
