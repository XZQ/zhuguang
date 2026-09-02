# P0 Skill 生命周期

[`registry.json`](registry.json) 是 6 个 P0 Skill 的发布事实源。一次可执行发布由
`name + version + digest` 唯一标识；目录名或 Worker ZIP 文件名不能代替版本身份。
当前 6 个 Skill 均为 `active/stable`，没有正在运行的 canary，也没有伪造灰度数据。

## 状态与渠道

- 状态：`active` → `deprecated` → `retired`。`retired` 禁止新任务路由，但历史 Trace、
  审计和恢复制品仍按留存策略保存。
- 渠道：`canary` 与 `stable`。canary 使用 `skill_name + incident/trace_id` 的 SHA-256
  固定分桶，同一任务不会在重试时漂移；比例上限由 Registry 固定为 25%。
- 版本：遵循 SemVer。patch 只允许兼容修复，minor 允许向后兼容能力，输入或输出契约的
  破坏性变化必须升 major，并保留迁移说明和双读/双写或显式停机窗口。

## 发布与灰度

1. 只修改根目录 `skills/<name>/` 的 canonical 契约，同时更新 manifest 版本和 change log。
2. 运行输入/输出 Schema、成功/失败样例和运行时输出校验；安全边界不得因升版弱化。
3. 将 canonical 目录逐字同步到 Worker 镜像，计算内容 digest，并把新版本登记为 canary；
   原 stable 写入 `rollback_target`，不可覆盖其制品。
4. canary 先跑本地正常/失败金标，再在真实 AgentTeams 中验证发现、加载、调用、异常处理，
   Trace 必须包含 `skill_name`、`skill_version`、`skill_digest` 和渠道。
5. 只有契约、确定性 Worker ZIP、正常/失败回归、平台 Trace 和零新增安全违规全部通过，
   才能将 canary 提升为 stable。每次提升都生成版本摘要、checksum 和 provenance。

## 升级、兼容与回滚

- 调用方按 Registry 解析版本，不读取“latest”或未固定目录；跨版本重试必须沿用原 Trace 的
  release identity。
- patch/minor 升级仍需重跑结构化输出、工具调用、延迟和安全门禁；major 升级必须提供调用方
  迁移计划，并在旧版本停止新路由前完成兼容验证。
- 出现 Schema 失败、危险动作/错误关闭、error/partial 比例或延迟预算回归时，立即把新流量
  切回 `rollback_target`。已执行的外部业务动作按各自补偿语义处理，不能把版本回滚冒充业务回滚。
- 回滚后保留失败 Trace、版本 digest、影响任务、补偿结果和责任人；修复版本重新从 canary 开始。

## 退役

1. 先标记 `deprecated`，给出替代 Skill、Owner、停止新路由时间和留存窗口。
2. 验证没有新任务命中，并完成历史任务、补偿和审计检索演练。
3. 再标记 `retired`；从 Worker 新版本移除前保留最后可恢复制品、checksum、Schema 和变更摘要。
4. 删除历史制品不属于普通发布流程，必须单独审批并满足比赛/业务留存要求。

## 当前验收命令

```powershell
uv run --group dev python -m unittest -v tests.test_skill_registry tests.test_skill_contracts
uv run python scripts/build_worker_package.py
uv run --group dev python -m unittest -v tests.test_agentteams_artifacts
```
