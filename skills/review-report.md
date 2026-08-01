# Skill review-report — 复盘报告与知识沉淀

> 店巡 Agent · S7/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:review-report
- **用途**:对已闭环的异常事件生成复盘报告(时间线、根因、处置、验证、改进项),并沉淀为知识条目/Skill 更新建议
- **输入**:`anomaly_id(s)`、`closed_events[]`、`knowledge_base_schema`
- **输出**:`ReviewReport { timeline[], root_cause, actions_taken, validation_results, lessons_learned, action_items[], knowledge_entries[{title, body, tags, confidence}] }`
- **调用条件**:稽核确认事件 closed 后触发;每日 23:00 批量复盘当日闭环事件
- **依赖工具**:RAG 知识库(PolarDB 向量)、Trace 存储(LoongSuite)、MCP-pos/wms 拉取最终数据
- **失败处理**:Trace 不完整 → 标记"部分证据,可信度降级"仍生成报告;知识条目置信度低 → 标记待人工确认,不直接进正式库
- **安全边界**:报告仅总部可见;知识条目入库前需过质量门(去重/格式校验);敏感信息(供应商议价、员工信息)自动脱敏
- **复用价值**:高。通用复盘机制,任何自动化闭环系统都需要,是"经验沉淀飞轮"的引擎
- **协同关系**:稽核 Auditor 调用,写回知识库 → 下次诊断 Diagnoser 的 RAG 检索命中 → 飞轮闭合
