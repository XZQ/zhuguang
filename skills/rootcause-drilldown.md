# Skill rootcause-drilldown — 维度下钻

> 店巡 Agent · S3/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:rootcause-drilldown
- **用途**:对异常指标做维度下钻(门店×品类×时段×供应商×货架位),定位最可疑根因维度组合,输出带证据的根因报告
- **输入**:`anomaly_id`、`metric`、`candidate_dimensions[]`、`evidence_source`
- **输出**:`RootCauseReport { anomaly_id, hypothesis, confidence, drilldown_path[], contributing_factors[], check_plan{下一步核验动作} }`
- **调用条件**:anomaly-detect 输出 severity ≥ 中 的异常;需要历史同期数据可查
- **依赖工具**:MCP-pos(品类/时段)、MCP-wms(供应商/批次)、MCP-iot(设备)、RAG 知识库(历史同型案例)
- **失败处理**:维度数据缺失 → 标记未核验维度;多假设并列 → 输出 top3 按置信度排序,交由总控仲裁;知识库检索无命中 → 明确"无历史案例"避免幻觉
- **安全边界**:只读;供应商级信息仅对总部角色开放(基于调用者身份);禁止将诊断结论直接写回业务系统
- **复用价值**:高。本质是"指标异动归因",可复用到任何带维度模型的数据域(电商、制造、物流)
- **协同关系**:诊断 Diagnoser 产出 → 上下文传递给处置 Executor;报告全文写入审计库供稽核查验
