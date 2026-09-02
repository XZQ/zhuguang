# 为逐光贡献代码

感谢参与逐光。项目仍是比赛与验证阶段的开源工程，不是可直接用于真实食品放行或门店生产的成品。

## 开始之前

- 使用 Python 3.11+ 与 `uv`。
- 从 issue 或小范围变更开始；涉及状态模型、数据库迁移、角色权限或公开契约时，先说明兼容和回滚方案。
- 不提交 API Key、Token、真实审批身份、顾客/员工数据、门店照片原件、运行数据库或未脱敏 Trace。
- 本地 Mock、静态 YAML/SQL 和确定性测试不能写成 AgentTeams、PolarDB、OSS 或真实门店已验证。

```bash
uv sync --locked --group dev
uv run python scripts/generate_demo_data.py --check
uv run python scripts/recovery_drill.py --check
uv run ruff check .
uv run ruff format --check .
uv run python -W error::ResourceWarning -m unittest discover -v
uv run dianxun evaluate
uv run dianxun ablation
uv run dianxun command-center
uv run python scripts/build_worker_package.py
uv build
git diff --check
```

没有设置隔离的 `DIANXUN_TEST_POSTGRES_DSN` 时，两项 PolarDB 集成测试应明确显示 skipped；不得用 Mock 改成通过。

## 变更边界

- `src/dianxun/` 是领域实现唯一来源。
- 根目录 `skills/` 是 P0 Skill 契约唯一来源；`packages/dianxun-worker/skills/` 必须与其一致。
- Worker ZIP 只能由 `scripts/build_worker_package.py` 生成，禁止手工修改。
- 评测和指挥台产物由对应 CLI 重建，不能手调结果制造通过；CI 会在干净 checkout 中用 `git diff --exit-code` 检查生成物漂移。
- 新增指标只能使用固定、低基数标签；tenant、incident、request、trace、用户和 Token 不得成为指标标签。

## Pull Request 要求

PR 应保持单一目的，并说明：问题、实现、风险、验证命令、证据边界以及是否影响 Schema/Skill/MCP/Worker 包。提交前检查暂存差异和敏感信息。维护者负责确认业务安全门、兼容性、生成物一致性和文档口径；安全边界或高风险动作至少需要一次独立复核。

漏洞不要放进公开 issue，按 [`SECURITY.md`](SECURITY.md) 私下报告。一般缺陷和功能建议使用仓库 Issue 模板。
