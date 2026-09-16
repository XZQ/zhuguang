# 库存范围协议 v2：升级与交接

本文描述开发分支上的升级流程，不代表生产已部署。真实 WMS/POS、人工身份与外部回执仍须在获授权环境验收。

## 升级顺序

1. 记录旧应用镜像摘要、Worker 包摘要和数据库版本，备份数据库并在独立库验证恢复。
2. 暂停入口、Worker 写调用与全部恢复扫描进程，等待在途请求结束。停止接新任务不等于现有写入者已停止。
3. 使用迁移身份运行下面的显式命令。两个开关是运维人员对已完成步骤的确认，不是自动备份或自动停写。
4. 重新以受限运行身份启动服务，设置 `DIANXUN_SCOPE_V2_REQUIRED=1`，确认 `/ready` 成功。缺迁移、表/字段缺失时不得降级为旧写协议。
5. 同步新 Worker 包与 YAML。旧客户端对 v2 事件缺少范围版本的写请求会被拒绝，不在网关替它填当前版本。
6. 对开放旧事件由同店 Human 根据可信库存来源执行对账；缺失库存不得删去责任，也不得借当前库存自动扩大过去批准。恢复任务后确认新轮次的独立核验和关闭。

SQLite 示例（明确现有数据库路径，不使用 state-init 或 scenario-reset）：

```bash
uv run dianxun migrate-scope-v2 --db /srv/dianxun/runtime.db \
  --backup-verified --writers-stopped
```

PostgreSQL 先完成 `core`、`security` 基础配置，用秘密管理器注入迁移 DSN；不要把密码粘贴到终端记录或文档：

```bash
uv run dianxun migrate-scope-v2 --db "$DIANXUN_DATABASE_URL" \
  --backup-verified --writers-stopped
```

运行身份不执行 DDL。新增修订与谱系表按租户/门店 RLS 限制，业务角色仅可读取、追加，不得改删历史。迁移不改写已关闭事件 JSON，不改已完成动作的 request/response 原文；缺少结构化目标的旧批准不会变成 v2 授权。

## 调用者必须区分三个版本

| 字段 | 用途 | 来源 |
|---|---|---|
| `expected_scope_version` | 防止旧库存范围继续执行 | `runtime_snapshot.incident.scope_version` |
| `expected_version` | Context CAS，防止协调状态丢更新 | `runtime_snapshot.context.version` |
| `generation` | 恢复轮次，隔离旧租约/输出 | `runtime_snapshot.context.recovery.generation` |

已启用 v2 的新事件 `runtime_open` 传 `expected_scope_version=0`。其后的修改请求传实际范围版本；`runtime_tool` 内层 MCP 写参数同样使用该范围版本。遇到冲突必须重新读取并核对任务/租约，不是只把数字替换后重发旧动作。

Human 修订接口：

```json
{
  "name": "runtime_revise_scope",
  "arguments": {
    "incident_id": "INC-EXAMPLE",
    "expected_versions": {
      "INC-EXAMPLE": {"scope_version": 1, "context_version": 3}
    },
    "change_id": "wms-change-unique-id",
    "source_ref": "wms:verified-receipt-reference",
    "changes": [{
      "op": "split", "batch_id": "PARENT",
      "children": [
        {"batch_id": "CHILD-A", "quantity": 4},
        {"batch_id": "CHILD-B", "quantity": 6}
      ]
    }]
  }
}
```

这是格式示例，不是可替代真实来源的回执。实际父批数量必须等于全部子批之和，余额也要明确建子批；共享批次的全部开放事件都必须提供预期版本，否则整笔拒绝。`move` 提交 batch_id/device_id，只允许同门店，不解除原事件责任；`add` 提交明确库存字段，不能夹带“已批准”“已停售”等结论。

旧事件库存对账使用 `runtime_reconcile_scope`，同样包含 `incident_id`、完整 `expected_versions`、唯一 `change_id` 与 `source_ref`，不接受模型编造的来源。关闭后出现新暴露，调用 `runtime_open` 创建新事件，并传 `previous_incident_id` 和 `source_ref` 关联已关闭历史，不重写旧事件。

## 审批与恢复

- 批次处置、解除停售：申请时明确 `target_batch_ids`；不得附带设备目标。服务器绑定当前数量、位置、规则。
- 维修：申请时明确 `target_device_ids=[device_id]`；批次列表为空或省略。无关补货不自动要求重发已成功工单。
- 相同对象与约束仍有效的原批准可以保留；变化对象须新批准。历史批准状态与当前适用性分开显示，不把失效伪造成人工拒绝。
- v2 核验记录编号包含 `:scope:<scope_version>`。放行使用本轮 Auditor 返回的 ID，不硬编码旧 release_guard 编号。
- 完全相同旧请求可能返回 `historical_replay=true`，仅供查历史，不能推进本轮 checkpoint。未知外部执行结果先回查，不更换动作 ID 重做。
- 修订归档旧阶段/输出，失效旧活动租约；只对当前缺少有效遏制证据的对象补做。所有当前叶子批次、数量、必要实物凭证、审批和独立复核满足后才关闭。

## 查询、取证与回退

`/operations` 为只读：显示范围版本、来源修订、拆批谱系、原审批决定与当前适用性。生成遏制待办不代表真实渠道已经停售。原始修订与谱系进入案例档案及封存包，历史回放不执行动作。

切换后若出现问题，先停止写入和自动派发，保留库存限制、回执及审计。已产生 v2 修订的库不得直接交给旧二进制继续写。需要回退时，在独立环境恢复切换前备份，逐笔核对切换后的真实副作用和外部回执；未对账前不重新执行动作，也不为通过旧验收而移除安全门。

Worker 包源码固定于 `ade0e67022cbc1d6c0dc5adab6a353a2575d36cb`，SHA-256 为 `528c2990626eace1d78b3db5f358768a3d27c64db14ab9f4746dc3e8815ed957`。本地提交不等于已发布：对外部署前须确认该提交已推送，固定 URL 可下载且摘要一致。
