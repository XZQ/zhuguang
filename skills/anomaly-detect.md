# Skill anomaly-detect — 多源异常检测

> 店巡 Agent · S1/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:anomaly-detect
- **用途**:聚合多源业务数据(POS 销售、库存、IoT 冷柜温度、价签),识别异常事件、降噪并定级(低/中/高/严重)
- **输入**:
  - `window_start / window_end`:检测时间窗(默认近 24h)
  - `store_ids`:门店列表(可空=全部门店)
  - `data_sources`:要检测的数据源(默认全部)
  - `thresholds`:自定义阈值覆盖(可空)
- **输出**:`AnomalyList[ { anomaly_id, store_id, type(缺货/临期/价签/冷柜/损耗/库存不匹配), severity, confidence, evidence{数据源,时间点,当前值,基线值}, matched_rule } ]`
- **调用条件**:定时调度(每小时)或事件触发(数据源推送异常时);数据源健康检查通过
- **依赖工具**:MCP-pos(销售/收银)、MCP-wms(库存/临期)、MCP-iot(冷柜温度)、MCP-price(价签一致性)、基线知识库(同店历史统计)
- **失败处理**:
  - 单一数据源不可用 → 跳过该源并标记 `partial=true`,降级输出
  - 全部数据源不可用 → 返回空清单 + `degraded=true`,通知总控进入"降噪模式"
  - LLM 解析异常 → 重试 1 次,失败则用规则引擎兜底结果
- **安全边界**:只读,无写权限;仅返回聚合后数据,不透传明细 PII(如会员信息);结果需置信度阈值过滤,防刷屏
- **复用价值**:高。所有连锁业态通用(超市/餐饮/药房),仅需替换数据源 Schema 映射,是底座 Skill 之一,开源
- **协同关系**:巡检 Sentry 的看家 Skill;输出喂给诊断 Diagnoser 做下钻,同时写入共享上下文总线供稽核审计

---

