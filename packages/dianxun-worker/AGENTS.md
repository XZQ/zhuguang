# AGENTS — Worker 包维护规则

本目录是 AgentTeams `v1.2.3` Worker ZIP 的源目录，不是第二套业务实现。

- 根目录 `AGENTS.md` 只约束仓库维护，不进入 ZIP；运行时规则位于 `config/AGENTS.md`。
- `skills/` 必须与仓库根目录的 6 个 P0 Skill 逐字一致，不在这里维护分叉版本。
- Worker 包只放身份、行为规则和 Skill 契约；领域阶段由 `IncidentService` 聚合，工具状态与写操作由共用 MCP/StateStore/Policy 事实层负责。
- 使用 `python scripts/build_worker_package.py` 生成确定性 ZIP，禁止手工修改 `dist/dianxun-worker.zip`。
- 包格式、manifest、runtime 和 YAML 字段固定对齐 AgentTeams `v1.2.3`。
- 不提交 API Key、Token、真实审批身份、Team Room 内容或伪造的运行证据。
