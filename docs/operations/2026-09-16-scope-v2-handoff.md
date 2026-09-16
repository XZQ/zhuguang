# 2026-09-16 范围协议开发暂停交接

用户要求停止修复，将当天代码和操作记录提交推送，并更新统一待办。当前分支 `codex/incident-scope-v2`，不是可部署版本；不合并 main、不部署生产。

## 当天实现

- `8f2be22`：规范范围快照、摘要、数量守恒与拆批不变量。
- `040aabe`：SQLite/PG 显式迁移、Human 原子修订、多事件 CAS、谱系和审批目标绑定。
- `ade0e67`：新版 Worker 协议 ZIP；`07a6a2a`：Worker 固定引用、后台范围/谱系/审批展示、升级交接手册。
- `cb478e9`：CLI/readiness 切换、scope 写门禁、对账与关联新事件、精确审批、恢复新轮次及当前范围核验。
- 暂停时工作区已有审查修复草稿，全部以 WIP 保存：旧范围漂移检查、移柜目标设备 freshness 集合、legacy/v2 CLOSED 行为区分。尚未完成针对这些草稿的复核，不标记修好。

## 实际验证与操作边界

- 合成 HTTP 定向流程跑通拆批→补货→重启→独立复核→CLOSED，原动作保留且维修工单只有一个。
- `cb478e9` 完整回归：190 发现，186 通过，2 失败，2 PostgreSQL 条件跳过，102.085 秒。失败为 `test_close_rechecks_safety_even_without_clock_advance`、`test_physical_receipt_requires_exact_batch_quantity_action_and_independent_confirmation`。此后草稿未重跑全量。
- cb478e9 的 Ruff、189 文件格式检查通过；wheel 使用 Docker COPY 输入构建，在源码目录外安装与入口烟测通过。不是实际镜像烟测。
- 后台浏览器使用本机合成拆批夹具核验范围版本、来源、数量谱系及待核对提示；预览进程已关闭。
- 较早版本在首尔封闭 PG 容器完成迁移/RLS 1 项及修订核心 7 项。当前版最终传输被安全审核拒绝，未绕过，未取得当前版 PG 结果。
- 本机 Docker daemon 未启动，未启动 OrbStack。没有生产部署、真实库存修改、真实渠道验收或真实 AgentTeams 成功声明。

## 恢复工作时的剩余项

1. 复核普通修订不能把其他批次的未解释数量漂移洗成已对账；只有明确 Human 对账接受完整来源。
2. 复核移柜目标设备健康/压缩机变化必须使旧 Auditor 证据对 release/close 失效。
3. 修复并回归两处 CLOSED 兼容失败；v2 关闭历史不可改，legacy 旧行为及当前安全结果不能被掩盖。
4. 当前草稿定向验证、最终分支审查及全量通过后，再同步事实数字、门户/评测制品；现有 166/164/2 是旧通过基线，不能冒充本分支当前全量结果。
5. 新版受限 PG、实际镜像、真实 AT/Human/WMS/POS、托管数据库/回退与业务验收仍待完成。

Worker 包固定源码 `ade0e67022cbc1d6c0dc5adab6a353a2575d36cb`，摘要 `528c2990626eace1d78b3db5f358768a3d27c64db14ab9f4746dc3e8815ed957`。推送开发分支仅保存工作，不表示发布、远端 CI 通过或可部署。
