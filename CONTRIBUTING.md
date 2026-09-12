# 为逐光贡献代码

感谢参与逐光。项目仍是比赛与验证阶段的开源工程，不是可直接用于真实食品放行或门店生产的成品。

## 开始之前

- 使用 Python 3.11+ 与 `uv`。
- 门户回归需要 Node.js 22+；CI 在 Ubuntu/Python 3.11 与 Windows/Python 3.12 执行相同门禁。
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
uv run python scripts/check_quality_facts.py
uv run dianxun evaluate
uv run dianxun ablation
uv run dianxun command-center
uv run python scripts/build_worker_package.py
uv build
uv run python scripts/check_installed_distribution.py --docker-inputs
uv run python scripts/build_animated_svg.py
uv run python scripts/build_full_delivery_portal.py
git diff --check
```

没有设置隔离的 `DIANXUN_TEST_POSTGRES_DSN` 时，两项 PolarDB 集成测试应明确显示 skipped；不得用 Mock 改成通过。

新增测试后，先运行完整回归，再同步 `config/project-facts.json` 和当前测试材料；`check_quality_facts.py` 只核对发现数及文档，不能代替测试执行。历史带日期记录保留当时口径。门户状态逻辑、旧输出清理和两次完整构建确定性属于单元门禁；现行门户和 SVG 从 `scripts/assets/` 重建，CI 检查生成物漂移。三套旧复赛手册已退役，历史源稿与 PDF 见 [归档](docs/archive/2026-09-semifinals/README.md)，不再运行旧生成器。

有 Docker 引擎时执行以下容器门禁；CI 的独立 Linux job 会真实运行。烟测凭证随机生成，仅绑定回环端口，只清理本次创建的容器：

```bash
docker build -f packages/dianxun-mcp/Dockerfile -t dianxun-mcp:ci .
python scripts/check_docker_image.py --image dianxun-mcp:ci
```

没有 Docker 时须明确记录“镜像烟测未执行”。安装 wheel 的隔离烟测不代表容器已经通过。现行门户构建不导出 PDF，仅复制 PPT 目录中的既有制品和 docs/competition 原路径保留的三份复赛 PDF；新 PDF 需要显式导出与逐页核对。历史 PDF 保留原字节，不能声称随网页重建更新。

## 变更边界

- `src/dianxun/` 是领域实现唯一来源。
- 根目录 `skills/` 是 P0 Skill 契约唯一来源；`packages/dianxun-worker/skills/` 必须与其一致。
- Worker ZIP 只能由 `scripts/build_worker_package.py` 生成，禁止手工修改。
- 评测和指挥台产物由对应 CLI 重建，不能手调结果制造通过；CI 会在干净 checkout 中用 `git diff --exit-code` 检查生成物漂移。
- 新增指标只能使用固定、低基数标签；tenant、incident、request、trace、用户和 Token 不得成为指标标签。

## Pull Request 要求

PR 应保持单一目的，并说明：问题、实现、风险、验证命令、证据边界以及是否影响 Schema/Skill/MCP/Worker 包。提交前检查暂存差异和敏感信息。维护者负责确认业务安全门、兼容性、生成物一致性和文档口径；安全边界或高风险动作至少需要一次独立复核。

漏洞不要放进公开 issue，按 [`SECURITY.md`](SECURITY.md) 私下报告。一般缺陷和功能建议使用仓库 Issue 模板。
