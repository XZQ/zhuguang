# Incident Scope Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现已批准的范围版本、精确审批绑定、数量守恒拆批、恢复和关闭门禁，不重复已有副作用。

**Architecture:** 新增小型领域模块统一规范范围与目标快照；范围修订服务复用现有门店锁、业务事务和 Context CAS。库存、谱系、范围、授权适用性和恢复轮次原子提交，既有业务入口统一检查当前范围。

**Tech Stack:** Python 3.11+、unittest、SQLite、PostgreSQL/psycopg、现有 HTTP runtime 与 JSON schema；不引入新运行依赖。

**Spec:** `docs/superpowers/specs/2026-09-16-incident-scope-versioning-design.md`（用户已确认实施）。

## Global Constraints

- 库存保持整数计量；拒绝 bool/浮点/负数及零数量子批。
- 不清库，不伪造旧批准，不自动修改已关闭历史，不复制父批放行凭证。
- 未变化目标的原有效批准可保留；原成功动作不重做，未知副作用先对账。
- 所有关联开放事件一起更新；SQLite/PG 均须验证；真实平台/业务接入另验。
- 主进度入口仍为 `docs/待办.md`；本文件仅追踪实施步骤。未完成所有任务不得宣称 T02 完成。

## 文件职责与接口

- 新建 `src/dianxun/domain/scope.py`：纯函数规范快照、生成摘要、验证拆分。
  `build_scope_snapshot(*, tenant_id: str, store_id: str, asset_ids: list[str], batches: list[dict]) -> dict`；
  `scope_digest(snapshot: dict) -> str`；
  `validate_split(parent: dict, children: list[dict]) -> list[dict]`（返回排序后的完整子对象；输入不变）。
- 新建 `src/dianxun/scope_revision.py`：`ScopeRevisionService(runtime).revise(*, principal, incident_id, expected_versions, change_id, source_ref, changes) -> dict`，负责事务范围修订，禁止 ORM 外第二套事实源。
- 修改 `domain/models.py`、`domain/service.py`：历史兼容、当前范围快照、关闭门禁。
- 修改 `state/store.py`、`state/postgres.py` 和 `state/sql/`：增量迁移、谱系/修订唯一约束、RLS 和受限权限。
- 修改 `mcp/p0.py`、工具 schema、`runtime.py`、`recovery.py`、`coordination.py`：审批目标绑定、版本校验、旧租约拒绝及新轮次。
- 修改 `operations.py`、现有 operations 前端及 `packages/dianxun-worker/`：协议和审计展示。
- 新建 `tests/test_scope_versioning.py`、`tests/test_scope_revision.py`；扩展现有 PG、Worker、恢复、交付测试。

## Task 1：确定性范围与拆分不变量

- [x] 写 `test_scope_versioning.py`：相同对象不同顺序摘要一致；数量/位置/规则/租户变化摘要不同；拒绝跨域、重复 ID、缺字段、不安全整数；拆分 10→4+6 通过，10→4+5、父子同 ID、重复子 ID、跨 SKU/域、终结父批拒绝。不要 mock 领域逻辑。
- [x] 运行 `uv run python -m unittest -v tests.test_scope_versioning`，记录因缺少真实功能失败的输出。
- [x] 实现 `scope.py`。规范对象包含 batch_id/store_id/device_id/sku_id/quantity/policy_ref/lifecycle；服务端 tenant/store 外层必需。排序并深拷贝，SHA-256 使用 UTF-8 的 `json.dumps(...,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)`。非范围 metadata 不改变摘要；真实位置、规则和数量必须改变。
- [x] 运行专项并变异检查：去掉数量守恒、允许 bool、忽略位置任意一项都应使测试失败；通过后提交独立基础模块。

2026-09-16 证据：首次 5 项因模块缺失失败；追加可售标志/温区变更反例后有 3 个预期失败，修复后 5 项通过；三种内存变异分别触发 2/3/2 个断言失败。完整 166 项发现、164 通过、2 项本机无 PG DSN 跳过，86.814 秒。此基础模块尚未接入 runtime，不代表范围协议已实施完成。

可执行行为示例（fixture 使用完整字段）：

```python
parent = {
    "batch_id": "P",
    "store_id": "S03",
    "device_id": "D",
    "sku_id": "SKU",
    "quantity": 10,
    "policy_ref": "policy-v1",
    "lifecycle": "active",
    "disposition": "quarantined",
}
children = [
    {**parent, "batch_id": "C1", "quantity": 4},
    {**parent, "batch_id": "C2", "quantity": 6},
]
assert [r["quantity"] for r in validate_split(parent, children)] == [4, 6]
```

## Task 2：持久化和兼容迁移

- [ ] 在真实 SQLite 文件中建旧版本夹具，记录已完成动作与旧批准；测试升级后旧记录保留，缺失新迁移时 readiness 拒绝，迁移重复执行无重复记录。
- [ ] 增加事件 scope_version/snapshot，库存 lifecycle，修订与谱系表、审批/动作/核验绑定字段。默认 lifecycle active；旧范围版本标为未初始化而非直接证明已对账。
- [ ] 迁移开放旧事件时从原受影响批次建立快照；当前库存不符时记录待核对。旧未消费且无目标绑定批准只能重审，已完成结果保持原字节语义。
- [ ] 给 PG 新表添加 scope/RLS、runtime 最小权限、修订审计不可改删；测试缺迁移与越权写拒绝。
- [ ] 跑 SQLite 迁移、PG 受限连接升级/回滚测试后提交。

关键断言：

```python
assert migrated_case["scope_version"] == 1
assert old_completed_action == reloaded_completed_action
assert migrated_unbound_approval["applicability"] == "requires_review"
assert old_dump_replay["incident_id"] == migrated_case["incident_id"]
```

其中变量由每个测试的旧库夹具和实际查询取得，不能用实现生成预期值。

## Task 3：原子范围修订与谱系

- [ ] 写真实 runtime 测试：Human 可提交同店修订，Orchestrator/跨店身份拒绝；相同变更重送只产生一条修订，异内容同 ID 冲突。
- [ ] `runtime_revise_scope` schema 明确 expected_versions（每个关联事件的 scope/context 版本）、source_ref、changes；服务端枚举所有关联开放事件，拒绝缺失版本。
- [ ] 在现有门店锁内按事件/批次 ID 排序加锁，校验源范围、变化、数量与谱系；单事务写入库存/修订/事件/Context/审计。
- [ ] 完整拆分退休父批，子批保留 SKU/规则和限制，余额显式；不允许通过移柜解除事件责任或跨店归属变更。
- [ ] 注入审计失败及第二事件 CAS 冲突，断言零部分写入；并发两个相同请求只成功一次。
- [ ] 测试已关闭事件变化拒绝修改旧历史，并通过正常开事件接口建立关联新事件；提交。

核心可观测断言：`len(revisions)==1`、`sum(child.quantity)==before.quantity`、`parent.lifecycle=="retired"`；失败后库存、事件、Context 与谱系快照分别与事务前一致。

## Task 4：精确审批、旧请求和独立核验门禁

- [ ] 先复现旧审批尝试作用于新增/数量变化批次，写拒绝断言；保留未变化对象成功反例。
- [ ] 扩展 create_approval 的结构化 target snapshot，由服务器生成并绑定规则和动作约束；decide_approval 与 `_require_approval` 重新验证当前目标适用性。
- [ ] runtime 所有推进/写入请求携带 expected_scope_version；缺失版本明确拒绝。历史相同幂等重放仅返回历史结果，不推进新 checkpoint；异内容同键仍冲突。
- [ ] 所有 release/close/Auditor 路径核对当前完整范围及复核绑定，不仅核对初始批次列表。旧父批凭证不能成为子批证据。
- [ ] 并发修改范围与审批决定/执行/释放/关闭，只有同一有效快照操作可以提交；PG 和 SQLite 实测后提交。

验收反例：批准 `P:10` 后拆成 `C1:4,C2:6`，无新的子批动作批准/独立证据时两者均不可放行；新增 C3 不应重做已成功 C1 工单或改写 C1 历史回执。

## Task 5：恢复轮次及差异遏制

- [ ] 写旧租约迟到、失响应动作、扫描器竞争和进程重启测试。
- [ ] 范围修订归档原 checkpoint/输出而非删除，推进恢复 generation 并失效旧租约；差异对象进入遏制待办，未获得渠道回执不能标已遏制。
- [ ] 复用现有幂等与回执对账；成功动作保留，未知副作用阻断重复执行；当前轮次 Auditor 汇总完整有效叶子范围。
- [ ] 测试变化对象完成后可以实际闭环，避免只实现拒绝导致永久不可完成；提交。

关键断言：旧 Worker 写失败且数据库不变；未知工单只做回查不新增；完成新批准/实物凭证/独立复核后事件实际 CLOSED。

## Task 6：协议、后台、制品与最终回归

- [ ] 更新 Worker 参数、MCP schema、案例详情（范围历史、差异、批准适用性、谱系）；读取并遵守 Worker 子目录 AGENTS.md。
- [ ] 真实 HTTP 测试新旧客户端：旧缺版本写拒绝，历史只读仍可读；当前 Worker 包能完成范围变化后的整条闭环。
- [ ] 完整 unittest、Ruff/format、事实门禁；实际运行后才更新测试数量，不先填通过。
- [ ] 构建 wheel/Worker 包/镜像并做包外安装测试；受限 PG 重跑全部新事务/权限/迁移与 HTTP 正反例。
- [ ] 浏览器核验历史与当前范围展示，不把合成来源隐藏；更新回放/导出兼容和部署回退手册。
- [ ] 更新统一待办，记录 commit、实际测试环境、失败/通过/skip 与仍待真实接入项；最后才进入分支完成审查，不直接覆盖生产部署。

## 计划自检与执行选择

设计第 3 节对应任务 1/2，第 4 节对应 3，第 5 节对应 4，第 6 节对应 4/5，第 7 节对应 2/6，十项验收分布于任务 1–6。所有跨模块签名集中在本计划文件职责段，扩展签名时同步更新消费者。

当前按用户“确认实施”在本会话顺序执行；用户已选择保持原路径，使用 `codex/incident-scope-v2` 开发分支，不直接改 main，不启动第三方会话或修改认证配置。

## 2026-09-16 后续实施检查点（尚非整体完成）

- Task 2：实现显式 `store.migrate_scope_v2()`，SQLite/PG 同事务加字段、建修订与谱系表及回填开放事件。范围仍以 case_json 为单一事实源，不增加重复权威列；旧记录全部待核对，未知或缺失库存不截断责任，已关闭 JSON 与动作回执保持原样。`require_scope_schema()` 只读检查已实现，但启动/readiness 切换、运维 CLI 和回退手册尚未接入。
- Task 3：`ScopeRevisionService` 和 `runtime_revise_scope` 已接入注册身份/门店授权、全体关联开放事件 scope/context CAS、补货、同店移柜、整数拆批、父批退休、谱系与审计原子写入。同 ID 异内容拒绝，相同请求回放不重复执行；新增/变化目标产生遏制待办，不伪造停售回执。关闭后关联新事件、未登记库存差异的完整核对流程仍未完成。
- Task 4：审批申请绑定明确批次快照及策略；决定与执行重新检查目标。批次处置支持 expected_scope_version；旧批准不能转给子批，无关新增不取消未变目标批准，完全相同历史请求标记 historical_replay。其他 MCP 写参数、Worker 参数传递、release/close/独立审核的全链路门禁仍未完成。
- Task 5：修订保存旧 checkpoint/phase 历史，取消旧活动 assignment，增加 generation，保留已完成动作/回执；当前协调状态暂挂起，不能称为新轮次可闭环。仍须接续未知副作用对账、差异遏制与重新独立核验。
- 已执行证据：迁移 6 项、修订核心 7 项 SQLite 检查通过；这时完整发现 179 项、177 通过、2 本机无 PG DSN skip，89.379 秒。随后审批 4 项和 runtime 修订入口 1 项针对性检查通过；没有再跑全量，不能把之前的全量结果覆盖到随后全部改动。
- PG：首尔既有封闭容器内新库 `scope_v2_test_20260916` 的迁移/重复执行/受限追加/跨域拒绝/禁止改删检查通过。`tests.scope_revision_pg_checks` 在七个新建 `scope_v2_test_revisionr1_*` 合成数据库，以独立 NOSUPERUSER/NOBYPASSRLS 登录执行修订核心 7 项，全部通过、零 skip、9.297 秒。此时验证的是修订服务核心，随后 runtime 注册和审批接入未在 PG 重验。
- 首次测试镜像入口误启动 MCP，被无认证非回环保护拒绝；改用显式 python 入口后运行上述测试。传输最初被安全审核拦截；用户明确“不要问我 自己执行”后按已说明的隔离测试范围传输。无凭据上传，未修改现有业务服务。
- 用户随后要求不要无休止测试：停止重复全量和扩充测试矩阵；下一阶段集中协议/恢复功能接入，最终集成点再做一次必要验收。项目事实配置仍为之前已提交的 166/164/2 基线，新增用例尚未同步全量事实门禁与制品，不声称 CI/制品通过。
- 未合并 main、未推送、未部署。以上未完成项不需要再次请求同一方案确认。
