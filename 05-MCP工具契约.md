# MCP 工具连接层接口契约

> 赛题要求:MCP 是推荐的外部工具接入协议;如未使用需提供等价集成契约(协议/鉴权/Schema/错误处理/审计/迁移成本)。
> 本文件给出 7 个 MCP 工具的完整契约,复赛阶段按此实现 MCP Server。

## 总则

- 传输协议:Streamable HTTP(MCP 标准);JSON-RPC 2.0
- 鉴权:OAuth 2.0 client-credentials,服务端换取企业内网令牌;密钥存 KMS,Agent 侧无明文
- 审计:每个 MCP 调用请求头带 `trace_id`(OpenTelemetry),工具层记录 request/response 摘要到审计库
- 通用错误码:401 未授权 / 403 越权 / 429 限流 / 5xx 工具故障
- 幂等:所有写操作工具要求调用方携带 `idempotency_key`(由 Skill 层生成),服务端按 key 去重
- 降级:工具超时(默认 5s)→ 重试 2 次 → 熔断 60s → 返回 `degraded=true` 由 Agent 决策兜底

## T1. mcp-pos(销售/收银数据)

| 项 | 内容 |
|---|---|
| 调用 | `query_sales(window, store_ids?, sku_ids?)` / `query_realtime_sales(store_id)` |
| Schema | window: {start, end} ISO8601; 返回 {rows:[{ts, store_id, sku_id, cat, qty, amount}], pagination} |
| 权限 | 只读;门店域数据 + 总部聚合视图 |
| 审计 | 记录查询条件与返回行数 |

## T2. mcp-wms(库存/临期)

| 项 | 内容 |
|---|---|
| 调用 | `query_stock(store_id, sku_ids?)` / `query_expiry(store_id, within_days)` |
| Schema | 返回 {sku_id, stock, safety_stock, days_to_expire, batch_id} |
| 权限 | 只读;SKU 级 |
| 幂等 | 读操作无幂等要求 |

## T3. mcp-iot(冷柜温度)

| 项 | 内容 |
|---|---|
| 调用 | `query_device_series(device_id, window)` / `list_devices(store_id)` |
| Schema | 返回 {device_id, readings:[{ts, temp_c}], status(ok/alarm)} |
| 权限 | 只读;设备级 |
| 降级 | 数据源 15 分钟无数据 → 标记 stale 告警 |

## T4. mcp-price(系统价格/促销)

| 项 | 内容 |
|---|---|
| 调用 | `query_price(store_id, sku_ids?)` / `apply_price_change(store_id, items[], idempotency_key)`(审批后调用) |
| Schema | query 返回 {sku_id, system_price, promo_rules[]};apply 返回 {applied_count, failed[]} |
| 权限 | apply 为写操作:需要审批流水号 `approval_ticket`,金额阈值检查(批量 > 20 SKU 强制人工) |
| 幂等 | apply 必带 idempotency_key,重复调用返回首次结果 |
| 回滚 | 提供 `revert_price_change(change_id)` 快照回退 |

## T5. mcp-im(企业 IM 通知,钉钉/飞书)

| 项 | 内容 |
|---|---|
| 调用 | `send_notice(channel, template_id, payload)` / `send_approval_request(channel, title, content, approve_url)` |
| Schema | 返回 {message_id} |
| 权限 | 仅发消息,无读会话权限 |
| 限流 | 每分钟 60 条,超限排队 |

## T6. mcp-approval(审批流)

| 项 | 内容 |
|---|---|
| 调用 | `create_approval(subject, type, payload, approvers[], timeout_min)` / `check_status(approval_id)` / `cancel(approval_id)` |
| Schema | 返回 {approval_id, status(pending/approved/rejected/timeout)} |
| 权限 | 审批人名单由总部配置,Agent 无权修改 |
| 降级 | 超时未批 → 返回 timeout,调用方按策略降级(如:仅通知不执行) |

## T7. mcp-workorder(维修服务商)

| 项 | 内容 |
|---|---|
| 调用 | `create_workorder(store_id, equipment_id, fault, budget, idempotency_key)` / `track(workorder_id)` / `confirm_done(workorder_id, evidence)` |
| Schema | 返回 {workorder_id, status(created/assigned/in_progress/done/closed), sla} |
| 权限 | 付款动作绝不由工具执行;仅生成待付款单 |
| 降级 | 服务商 API 故障 → 工单落本地队列,RocketMQ 延迟重试 |

## 迁移成本说明(评审可能追问)

- 以上契约均为"工具能力抽象",与 MCP 协议一一对应(读=resources/tools,写=tools)
- 迁移到 MCP Server 时仅需:① 包一层工具名映射;② 鉴权从内网令牌换成 OAuth;③ Schema 转成 JSON Schema 声明
- **无需重设计调用链与参数结构**,故迁移成本为协议适配级,非架构级
