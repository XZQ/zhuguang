# Skill 九要素卡(7 个核心 Skill)

> 赛题要求:Skill 是本赛题必选项,每个方案至少提供核心 Skill 清单,并按 9 要素说明:
> 名称 / 用途 / 输入输出 / 调用条件 / 依赖工具 / 失败处理机制 / 安全边界 / 复用价值 / 与多 Agent 协同流程的关系

---

## S1. anomaly-detect 多源异常检测

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

## S2. cross-store-benchmark 跨店横向对标

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

---

## S3. rootcause-drilldown 维度下钻

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

---

## S4. restock-order-gen 补货单生成

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

---

## S5. price-tag-check 价签与促销合规校验

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

---

## S6. work-order-dispatch 工单派发与跟踪

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

---

## S7. review-report 复盘报告与知识沉淀

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

---

## 附:Skill 版本与生命周期(评审可能追问)

- 版本策略:语义化版本 v1/v2;修复处置规则升级即发布新版本,旧版本保留 30 天可回滚
- 发布机制:Skill 仓库 + 配置中心(Nacos)灰度发布,先 10% 门店试点
- 质量评估:基于复盘报告统计各 Skill 命中率/误报率,月度迭代
- 开源形态:3 个底座 Skill(anomaly-detect / cross-store-benchmark / review-report)MIT 开源,行业包(便利店)闭源或按协议分发
