# Skill cross-store-benchmark — 跨店横向对标

> 店巡 Agent · S2/7 · 9 要素说明卡(赛题必选项)
> 项目总索引见 [../README.md](../README.md),全部 7 个 Skill 汇总见 [../03-Skill九要素卡.md](../03-Skill九要素卡.md)

## 九要素

- **名称**:cross-store-benchmark
- **用途**:为异常门店选择同商圈/同店型/同期对标店,计算各指标基准分布,判断异常是否"单店孤立"还是"系统性"
- **输入**:`store_id`(目标门店)、`metric`(如:缺货率/温度达标率/损耗率)、`benchmark_dimensions{商圈,店型,面积段,客流档}`
- **输出**:`BenchmarkReport { target_store, comparable_stores[], metric, target_value, p50/p90/p95, deviation_zscore, conclusion(单店孤立/集群性/行业普遍), evidence[] }`
- **调用条件**:诊断 Diagnoser 收到异常清单后调用;对标店数量 < 3 时需降维(放宽商圈匹配)
- **依赖工具**:MCP-pos(销量/客流)、门店主数据 MCP(店型/面积/商圈标签)、历史基线库
- **失败处理**:对标店不足 → 放宽匹配维度逐级降级,标注置信度下降;无法对标 → 返回"无基准,按固定阈值兜底",不阻塞流程
- **安全边界**:只读;跨店数据聚合仅返回统计值(均值/分位),不返回其他门店明细,防止店间信息泄露
- **复用价值**:高。零售通用底座 Skill;餐饮可扩展"同菜单结构对标",超市可扩展"同货架面积对标"
- **协同关系**:诊断 Diagnoser 的核心决策 Skill,输出直接支撑根因报告;对标结论进入上下文供处置 Executor 参考
