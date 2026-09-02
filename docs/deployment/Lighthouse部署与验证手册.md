# 逐光｜店巡 Agent — 腾讯云 Lighthouse 部署与验证手册

> 版本对齐：`config/project-facts.json` @ 0.2.0.dev0（updated_at 2026-09-01）
> 本手册所有命令与参数均取自仓库实际代码，不使用臆测值。
> 编写日期：2026-08-30；仓库口径复核：2026-09-02。

---

## 0. 这份手册解决什么问题

项目当前最大的证据缺口是 `agentteams_runtime_evidence: pending_external_validation`
和 `polardb_postgresql: implemented_code_pending_external_validation`。
在 Lighthouse 上跑一套真实常驻服务，可以把「MCP 契约与状态机」这一类缺口从
**外部待验证** 推进到 **已实现**，但**不能**覆盖 AgentTeams 动态协同与 PolarDB 托管能力。

边界见第 8 节，先读边界再动手。

---

## 1. 2026-08-30 阻塞快照（必读）

托管验证的第一步是有一台机器。根据 **2026-08-30 的 lighthouse-ops 连接器实测快照**，
当时连接器无法创建实例；实施前必须重新查询连接器能力、账号实例和配额，不能把该快照当成实时状态。

该快照中已核实的连接器能力（全量 62 个工具）：

| 类别 | 是否可用 |
|---|---|
| 查询实例 / 镜像 / 地域 / 快照 / 配额 | ✅ |
| **创建实例 / 查询套餐与价格** | ❌ **无 `CreateInstances`、无 `DescribeBundles`** |
| 防火墙 / 远程命令(TAT) / 监控 / 快照 / 域名解析 | ✅，但需已有实例 |

同一快照中，账号下 **15 个地域全部 0 实例**，广州 `GENERAL_BUNDLE_INSTANCE` 配额 50/50 全空，
`SNAPSHOT` 0/0（Lighthouse 快照额度随实例发放，无实例则无额度）。

**若实施时连接器能力仍未变化，实例必须在腾讯云控制台手工开通。** 开完把地域 + InstanceId 交给运维侧，
第 3 节之后的所有步骤都可通过连接器完成。

---

## 2. 实例选型

| 项 | 建议值 | 依据 |
|---|---|---|
| 地域 | `ap-guangzhou` | 2026-08-30 快照中已验证可售；下单前复查 |
| 可用区 | 3 / 4 / 6 / 7 | 2026-08-30 的 `describe_disk_configs` 只返回这四个区，**没有 1/2/5**；下单前复查 |
| 镜像 | `lhbp-2cacsycc`（Ubuntu 24.04 + Docker 29）<br>或 `lhbp-1l4ptuvm`（纯净 Ubuntu 24.04） | 见下 |
| 规格 | 2 核 4G 起 | 5 业务 Agent 并发 + 状态写；2G 偏紧 |
| 系统盘 | `CLOUD_SSD` ≥ 20G | SSD 最小 20G，步长 10G，上限 4000G |

**镜像怎么选**：`dianxun` 核心 **零运行时依赖**（`pyproject.toml` 中 `dependencies = []`），
只要求 Python ≥ 3.11，Ubuntu 24.04 自带 3.12，**不需要 Docker**。
只有当你打算同时跑容器化组件时才选 `lhbp-2cacsycc`。纯验证选 `lhbp-1l4ptuvm` 更干净。

> 2026-08-30 快照中套餐价格连接器查不到（无 `DescribeBundles`），需在控制台确认并以实时页面为准。

---

## 3. 基础环境

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/XZQ/zhuguang.git
cd zhuguang

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

# 核心无依赖；dev 组含 jsonschema / pyyaml / ruff，跑测试与评测需要
uv sync --group dev
```

若后续要接 PolarDB，额外安装可选依赖：

```bash
uv sync --extra postgres
```

---

## 4. 先跑通确定性门禁（不开端口，零风险）

这一层**不依赖任何网络监听**，是判断部署是否成功的第一道关。

```bash
uv run dianxun state-init                 # 从确定性种子重置 runtime.db
uv run dianxun evaluate                   # M4 六场景门禁，期望 6/6
uv run dianxun ablation                   # 四变体架构消融，期望 gate.passed=true
uv run dianxun command-center             # 生成 evidence/m4/command-center.html
uv run dianxun demo-run demo/state/scenarios/coldchain-compressor-failure.json
uv run dianxun mcp-tools                  # 打印 P0(12) 与可选 P1(3) 工具
uv run python -m unittest discover -s tests -v
```

期望结果（对齐 `project-facts.json` 的 `m4_evaluation`）：

| 指标 | 期望值 |
|---|---|
| `scenario_passed` | 6 / 6 |
| `evidence_records` | 45 / 45 |
| `covered_trace_phases` | 26 / 26 |
| `safety_violations` | 0 |
| 单元测试 | 74 通过 / 2 条件跳过（共发现 76） |

> 以上均为**仓库内确定性行为**，不是模型效果或真实门店收益证明。

---

## 5. MCP 服务：监听与鉴权

### 5.1 代码事实（`src/dianxun/mcp/server.py`）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `127.0.0.1` | |
| `PORT` | `8080` | |
| `MCP_TOKEN` | 空 | 共享 token，**只读** |
| `MCP_ACTOR_TOKENS_JSON` | 空 | `{"<token>": "<actor>"}`，状态写必须用它 |
| `DIANXUN_ENABLE_P1_TOOLS` | 未设 | 设为 `1` 才启用 3 个知识工具 |

**硬约束**：`HOST` 非回环（`127.0.0.1` / `localhost` / `::1`）且两个 token 变量都为空时，
进程直接 `SystemExit("Refusing a non-loopback MCP bind without authentication")` —— 起不来。
这是刻意设计，不要用"改代码绕过"的方式解决。

`MCP_ACTOR_TOKENS_JSON` 的 actor 必须落在工具声明白名单内，否则启动即报错。
P0 常驻服务需要的业务 actor：

```
Sentry  Diagnoser  Auditor  Executor  Human  AuthenticatedClient
```

`ScenarioEngine` 只用于确定性测试，不应作为生产人员身份。启用 P1 知识工具后还可配置
`food_safety_owner`、`hq_reviewer`、`knowledge_reviewer`，用于独立人工审核。

7 个 P0 状态动作中，`apply_sales_hold`、`release_sales_hold`、`apply_batch_disposition`、
`create_workorder`、`create_approval` 只允许 `Executor`；`decide_approval` 与
`record_manual_evidence` 只允许 `Human`（测试环境也允许 `ScenarioEngine`）。共享
`MCP_TOKEN` 不能调用任何状态动作。`release_sales_hold` 还要求新鲜的 Auditor
`release_guard` 验证，因此 Executor 不能自证放行。

### 5.2 启动

```bash
export HOST=127.0.0.1
export PORT=8080
export MCP_ACTOR_TOKENS_JSON="$(uv run python -c 'import json,secrets; actors=("Sentry","Diagnoser","Auditor","Executor","Human","AuthenticatedClient"); print(json.dumps({secrets.token_urlsafe(32): actor for actor in actors}, separators=(",",":")))')"
uv run dianxun-mcp
# Dianxun MCP listening on http://127.0.0.1:8080 with 12 tools
```

上面的 Token 每次启动随机生成，只适合本机烟测；不要输出到日志或录屏。常驻环境应由 Secret
Manager、Kubernetes Secret 或权限为 600 的 root-owned `EnvironmentFile` 注入，并通过安全渠道
把各角色 Token 分发给对应调用方。

健康检查：

```bash
curl -s http://127.0.0.1:8080/health
# {"service":"dianxun-mcp","version":"0.2.0","tools":12,"p0_tools":12,"p1_knowledge_enabled":false}
```

### 5.3 传输安全（重要）

服务是标准库 `ThreadingHTTPServer`，**明文 HTTP，无 TLS**。
跨公网裸奔 8080 + Bearer Token 等于把凭据放明文里传输。三选一：

1. **首选**：不开公网端口，用 SSH 隧道访问
   `ssh -L 8080:127.0.0.1:8080 ubuntu@<ip>`，服务 `HOST=127.0.0.1` 即可
2. **次选**：nginx 反代 + TLS（Let's Encrypt），后端仍绑 `127.0.0.1`
3. **兜底**：必须公网暴露时，防火墙来源收紧到固定 IP，且接受明文风险

---

## 6. systemd 托管

凭据**不要**写进 unit 文件，用 `EnvironmentFile`：

```bash
sudo install -d -m 700 /etc/dianxun
sudo python3 - <<'PY'
import json
import os
import secrets
from pathlib import Path

actors = ("Sentry", "Diagnoser", "Auditor", "Executor", "Human", "AuthenticatedClient")
mapping = {secrets.token_urlsafe(32): actor for actor in actors}
content = "HOST=127.0.0.1\nPORT=8080\nMCP_ACTOR_TOKENS_JSON=" + json.dumps(mapping, separators=(",", ":")) + "\n"
os.umask(0o077)
Path("/etc/dianxun/mcp.env").write_text(content, encoding="utf-8")
PY
sudo chmod 600 /etc/dianxun/mcp.env
```

> `MCP_ACTOR_TOKENS_JSON` 必须写成**单行 JSON**，systemd 的 `EnvironmentFile`
> 不做引号内换行解析。

```ini
# /etc/systemd/system/dianxun-mcp.service
[Unit]
Description=Dianxun MCP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/zhuguang
EnvironmentFile=/etc/dianxun/mcp.env
ExecStart=/home/ubuntu/.local/bin/uv run dianxun-mcp
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dianxun-mcp
systemctl status dianxun-mcp
journalctl -u dianxun-mcp -f
```

---

## 7. 防火墙（Lighthouse 控制台 / 连接器）

| 协议 | 端口 | 来源 | 说明 |
|---|---|---|---|
| TCP | 22 | 你的固定 IP | SSH |
| TCP | 8080 | 你的固定 IP，**或不开** | 仅当放弃 SSH 隧道方案时开 |

**不要**对 8080 放行 `0.0.0.0/0`。若走 SSH 隧道方案，8080 完全不需要出现在防火墙里。

---

## 8. 边界：这套部署能证明什么，不能证明什么

| 项 | Lighthouse 部署后 | 说明 |
|---|---|---|
| MCP 契约 12 工具真实可调用 | ✅ 可验证 | 真实 HTTP 进出 |
| 非回环无鉴权拒绝启动 | ✅ 可验证 | 反例测试，第 5.1 节 |
| 共享 token 无法执行写动作 | ✅ 可验证 | 反例测试 |
| 状态机五阶段真实迁移 | ✅ 可验证 | `demo-run` + `evaluate` |
| 服务常驻与自恢复 | ✅ 可验证 | systemd + 重启验证 |
| **AgentTeams 真实多 Agent 动态协同** | ❌ **不能** | 需 AgentTeams 运行时，与本机无关 |
| **PolarDB / pgvector / RLS / pg_cron / OSS 归档** | ❌ **不能** | 需另购 PolarDB 实例，Lighthouse 不提供 |
| **真实门店收益 / 生产可用性** | ❌ **不能** | 无任何真实门店基线 |

一句话：**这台机器能证明"我们的 MCP 与状态机在真实网络环境里站得住"，
不能证明"多 Agent 在 AgentTeams 上真跑起来了"，更不能证明"真实门店有效"。**
对外表述不得越线。

---

## 9. 交付前检查清单

- [ ] `dianxun evaluate` → 6/6，`evidence/m4/report.md` 已重新生成
- [ ] `dianxun ablation` → `gate.passed=true`，四变体结果与 Markdown 报告已重新生成
- [ ] `dianxun command-center` → `evidence/m4/command-center.html` 已重新生成
- [ ] 76 项测试完成（74 通过 + 2 条 PolarDB 条件跳过）
- [ ] `curl /health` 健康检查返回 `tools: 12`
- [ ] 非回环 + 空 token → 进程拒绝启动（反例留证）
- [ ] 共享 `MCP_TOKEN` 调写工具 → 被拒（反例留证）
- [ ] Executor 可创建审批但不能决定审批；Human 可决定审批与记录人工证据
- [ ] systemd 重启后服务自恢复
- [ ] 防火墙未对 8080 放行 `0.0.0.0/0`
- [ ] `/etc/dianxun/mcp.env` 权限 600，未进 Git
- [ ] **无 API Key / 真实审批身份 / 顾客数据 / 含敏感内容 Trace 入仓**

---

## 10. 快照与回滚

实例创建后 `SNAPSHOT` 额度才会出现（2026-08-30 快照为 0/0，实施前重查）。

- 建议在「基础环境装完」和「服务验证通过」两个节点各打一次快照
- 快照回滚是 🔴 高风险操作：**回滚会丢失快照之后的所有状态数据**，包括 `runtime.db`
- 回滚前先备份 SQLite 状态文件与 `evidence/` 目录到对象存储

---

## 附：连接器实测记录（2026-08-30）

| 检查项 | 结果 |
|---|---|
| 授权状态 | 正常（账号级配额接口返回真实数据） |
| `describe_regions` | 15 个地域 |
| `describe_instances`（15 地域全扫） | 全部为空 |
| `describe_general_resource_quotas`（ap-guangzhou） | 实例 50/50、密钥对 10/10、快照 0/0 |
| `describe_blueprints`（ap-guangzhou） | 48 个镜像 |
| `describe_disk_configs`（ap-guangzhou） | SSD 20–4000G，区 3/4/6/7 |
| 创建实例能力 | **缺失** |
