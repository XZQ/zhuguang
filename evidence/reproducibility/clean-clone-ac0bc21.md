# 逐光｜干净克隆复现记录（ac0bc21）

> 执行时间：2026-09-03 11:57（UTC+8）
>
> 验证对象：GitHub `main`，commit `ac0bc213dd0a4108deba4474761a575c39cc2a94`
>
> 证据边界：本记录证明公开仓库可在隔离的 Windows 克隆中按锁文件复现；不证明 AgentTeams、PolarDB、真实 HITL 或生产环境已运行。

## 1. 隔离方式与环境

- 从 `https://github.com/XZQ/zhuguang.git` 使用 `--branch main --single-branch` 克隆到新建的随机临时目录；未复制主工作区的 `.venv`、缓存、未跟踪文件或环境文件。
- Windows，Git `2.45.1.windows.1`，uv `0.11.31`，隔离虚拟环境 Python `3.12.13`。
- 凭证未写入命令、日志或仓库；临时目录绝对路径未作为项目事实保存。

克隆后检查：

```text
HEAD=ac0bc213dd0a4108deba4474761a575c39cc2a94
git status --porcelain=v1 => empty
```

## 2. 复现命令

在新克隆根目录依次执行：

```powershell
uv sync --locked --group dev
uv run ruff check .
uv run ruff format --check .
uv run python -W error::ResourceWarning -m unittest discover -v
uv run dianxun evaluate
uv run dianxun ablation
uv run dianxun command-center
uv run python scripts/generate_demo_data.py --check
uv run python scripts/recovery_drill.py --check
uv run python scripts/build_worker_package.py
uv run python -m unittest -v tests.test_agentteams_artifacts
uv build
git diff --exit-code
```

## 3. 结果

| 门禁 | 结果 |
|---|---|
| 锁定依赖安装 | 通过 |
| Ruff lint / format | 通过；144 个 Python 文件格式一致 |
| 自动化测试 | 87 项发现，85 通过，2 项按条件跳过 |
| 条件跳过边界 | 仅 `tests.test_polardb_integration` 的 2 项；未提供隔离 `DIANXUN_TEST_POSTGRES_DSN` 与显式 reset opt-in |
| M4 | 6/6；Evidence 45/45；Trace 阶段 26/26；安全门禁通过 |
| 四变体消融 | 通过；`no_auditor` 无放行尝试、无错误关闭，记录 2 个放行状态不一致 |
| Seed / 恢复演练 / 指挥台 | 通过 |
| Worker 制品 | 35 个文件；SHA-256 `6f3a9e590ee85b7336b529488e82f979ea3e3d04c1d1fbda2f1dd397bbc5289b` |
| Worker artifact contract | 5/5 通过 |
| wheel / sdist 构建 | 通过 |
| 生成物一致性 | `git diff --exit-code` 返回 0，最终工作区无差异 |

## 4. 远端交叉验证

同一 commit 的 GitHub Actions CI 也已成功：

- Run：<https://github.com/XZQ/zhuguang/actions/runs/33712832346>
- Job：`verify`，run id `33712832346`
- 结果：`success`
- 覆盖：Ubuntu 上的 Ruff、87 项测试、M4、消融、指挥台、Seed、恢复演练、Worker 制品、wheel/sdist 与生成物一致性。

## 5. 尚未由本记录覆盖

- AgentTeams Team Room 动态委派、heartbeat、超时 successor 和 checkpoint 恢复；
- Worker 到 MCP Actor 的动态身份绑定及鉴权负向证据；
- 真实人工审批与同一 Run 的回滚/补偿；
- 托管 PolarDB 的两项条件集成测试；
- 不超过 8 分钟的最终 Demo 视频、第二人复核与正式版本发布。
