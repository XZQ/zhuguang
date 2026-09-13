# 部署与发布手册

复核日期：2026-09-13。适用于已有 Linux/Lighthouse 测试主机。本文是可执行操作说明，不是部署回执；地域、套餐、镜像、实例、账号配额以实际控制台为准，不沿用旧连接器快照。平台验收与最终交付状态只在[待办](../待办.md)维护。

## 环境与版本

核心运行要求 Python 3.11+，开发门禁需要 uv、Node.js 22+。仓库核心没有必选运行时依赖，PostgreSQL 是可选依赖。先记录部署 SHA、系统与数据库版本、构建制品摘要和配置来源。

~~~bash
git clone https://github.com/XZQ/zhuguang.git
cd zhuguang
uv sync --locked --group dev
node --version
uv run python --version
# 使用 PostgreSQL 时：
uv sync --locked --group dev --extra postgres
~~~

新部署先通过[贡献约定](../../CONTRIBUTING.md)中的门禁。完整测试使用临时数据库和本地 HTTP，不代表测试主机的常驻服务或 AgentTeams 已验收。

## 数据库初始化与升级

服务优先使用 DIANXUN_DATABASE_URL，再使用 DIANXUN_STATE_DB；都未配置时使用默认 Demo SQLite。初始化和启动必须指向同一个数据库，不能初始化 runtime.db 后让服务读另一个默认路径。

以下只用于新的本地 SQLite 演示目录；执行前确认没有设置 DIANXUN_DATABASE_URL：

~~~bash
export DIANXUN_STATE_DB="$PWD/runtime.db"
if [ ! -e "$DIANXUN_STATE_DB" ]; then
  uv run dianxun state-init --db "$DIANXUN_STATE_DB"
else
  printf '%s\n' '数据库已存在：停止初始化，按升级流程处理。'
fi
~~~

已有服务先备份业务库和配置，不执行 state-init/reset。PostgreSQL 由迁移管理员核对 core/security profile、schema、RLS 与应用身份，参考[AgentTeams/PolarDB 操作](../../agentteams/README.md)。两项集成测试只使用隔离测试实例与显式重置授权。

SQLite 备份须得到一致快照：停止写入或使用数据库备份接口，涉及 WAL 时同时考虑未检查点数据；不能随意复制一个仍在写的主库文件当作已验证备份。回滚先保存当前状态和在途回执，不能直接覆盖后丢失新业务。

## 监听、身份与访问

| 变量 | 默认 / 用途 |
|---|---|
| HOST / PORT | 127.0.0.1 / 8080 |
| DIANXUN_STATE_DB | SQLite 路径；与初始化和 systemd 配置一致 |
| DIANXUN_DATABASE_URL | 可选 PostgreSQL 连接；优先于 SQLite 路径 |
| MCP_TOKEN | 共享只读认证 |
| MCP_ACTOR_TOKENS_JSON | 业务 Token 到 Actor 的可信映射 |
| DIANXUN_RUNTIME_TOKENS_JSON | 独立 Worker/Human 运维的 actor、worker_id、tenant_id、store_id |
| DIANXUN_ENABLE_P1_TOOLS | 设为 1 启用三个知识工具 |
| DIANXUN_EMERGENCY_CONTAINMENT | 默认关闭，只能在明确预授权范围开启 |

非回环绑定且 MCP_TOKEN/MCP_ACTOR_TOKENS_JSON 都为空时拒绝启动；仅 runtime Token 不满足该启动要求。五个 Worker 各用独立身份，Human 审批/运维身份不注入模型，调用协议见[运行与恢复](runtime-recovery.md)。

~~~bash
export HOST=127.0.0.1
export PORT=8080
# 通过现有秘密管理方式注入需要的身份变量，再启动：
uv run dianxun-mcp
~~~

常驻凭证由 Secret Manager、Kubernetes Secret 或受限 EnvironmentFile 注入，不写源码、unit 正文、终端输出、截图或公开 Trace。共享 Token 不能调用写动作，Executor 不能决定审批；商品处置与解除还需对应批准及独立核验。

服务本身为明文 HTTP。对远程访问使用 SSH 隧道，或 TLS 反向代理并把后端保留在回环地址；公网不直接开放带 Bearer 的 8080。SSH 来源收紧到运维地址，/metrics 仅监控网可访问。

~~~bash
ssh -L 8080:127.0.0.1:8080 ubuntu@<测试主机>
~~~

## systemd 示例

以下路径按实际服务用户和部署目录调整。配置文件应由管理员创建为 600 权限，不覆盖已有凭证。EnvironmentFile 一行一个变量；JSON 值使用外层单引号，内部保留合法 JSON，例如变量格式为 MCP_ACTOR_TOKENS_JSON='<通过安全方式提供的单行 JSON>'，占位符不能直接用于启动。

配置中明确写入 HOST、PORT、DIANXUN_STATE_DB 或 DIANXUN_DATABASE_URL，以及对应的身份映射；恢复扫描器需要 runtime 身份。示例不包含任何可用凭据。

~~~ini
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
~~~

~~~bash
sudo systemctl daemon-reload
sudo systemctl enable --now dianxun-mcp
systemctl status dianxun-mcp
journalctl -u dianxun-mcp -f
curl -fsS http://127.0.0.1:8080/live
curl -fsS http://127.0.0.1:8080/ready
curl -fsS http://127.0.0.1:8080/metrics
~~~

/live 只表示进程响应；/ready 与 /health 检查数据库、必要表、Skill 和已配置的扫描器，失败为 503。重启后核对任务、截止、回执与恢复结果，不以进程存在代替业务可用。固定低基数指标、PromQL、故障处置与兼容回退见[运行手册](runtime-recovery.md)。

## 门户、PPT 与 PDF 构建

从仓库根目录执行：

~~~bash
uv run dianxun command-center
uv run python scripts/build_animated_svg.py
uv run python scripts/build_full_delivery_portal.py
uv run python -m unittest tests.test_delivery_portal -v
~~~

输出 dist/delivery-portal。构建和部署是不同步骤；当前命令不会上传展示站。

| 源 | 生成器 | 输出 |
|---|---|---|
| scripts/assets/delivery_portal_html_content.html | build_delivery_portal.py | index.html |
| native_defense_web_dossier_html.html / native_defense_web_standalone_html.html | build_native_defense_web.py | defense.html；主页也嵌入 dossier |
| combined_animation_html_content.html | build_combined_animation.py | architecture-flow.html，浏览器模拟 |
| animated_svg_svg_content.svg | build_animated_svg.py | docs/assets/architecture-flow.svg |
| 现行 Markdown、project-facts、消融结果与 Skill registry | build_project_handbook.py（独立执行） | docs/competition/店巡Agent-项目与答辩手册.pdf |
| ppt/ | build_full_delivery_portal.py | 原样复制；准备入口 ppt/finals.html |
| docs/competition/ 的当前手册 PDF | build_full_delivery_portal.py | 原样复制至输出根目录 |
| docs/competition/ 的三份复赛 PDF | build_full_delivery_portal.py | 原名、原字节复制至输出根目录 |
| config/project-facts.json 与公开观测 | generate_portal_status.py | status.json |

旧三套手册生成器与六个重复模板已停用；构建清理已退役的 defense-guide.html、defense-guide-illustrated.html、defense-master.html，保留三份历史 PDF。当前构建不导出 PDF；新 PDF 必须从选定源单独导出并逐页核对。旧 PDF 与离线 ZIP 的日期和勘误见[比赛索引](../competition/README.md)。

### 当前手册 PDF 的独立导出

~~~bash
uv run scripts/build_project_handbook.py
~~~

脚本通过 PEP 723 声明固定版本的 ReportLab 和 Mistune，uv 使用隔离脚本环境，不增加 MCP 服务运行依赖。正文从现行 Markdown 的标题区段提取；测试数字、模型配置和消融结果读取结构化事实。Markdown 标题变化后应同步生成脚本，缺失区段会拒绝生成。

Windows 默认读取并嵌入微软雅黑常规/粗体字体。其他系统通过 `--font <中文TrueType字体路径>` 与 `--bold-font <中文粗体TrueType字体路径>` 指定允许嵌入的字体；同日期、同源文件、同字体和工具版本可重复构建。可用 `--date YYYY-MM-DD` 固定资料日期、`--manifest <路径>` 保存来源哈希与页码记录。资料日期不替代正文独立记录的测试日期。

导出后渲染全部页面，检查文字、表格、架构图、代码换行、目录跳转和证据口径，再执行完整门户构建复制新 PDF。三份复赛 PDF 不参与重写，目标路径也受生成脚本保护。已有 PPT/PDF 的修订与对外发布仍单独验收。

## 状态观测和发布核对

没有观测时 Worker 为 unknown，不从配置推断在线。仅接收 online/offline/unknown，并要求原始 observed_at；配置模型和观测模型分开显示。以下是格式示例，不是实际状态：

~~~json
{"workers":[{"name":"sentry","status":"offline","observed_at":"2026-09-07T00:00:00Z","model":null}]}
~~~

~~~bash
uv run python scripts/generate_portal_status.py --observations observations.json
~~~

页面每 15 秒刷新，3 秒超时；观测超过 120 秒或明显未来时按过期处理，零在线不能回退为五。温度曲线、128 店/512 设备和审批按钮为模拟，不是传感器/人员证据。

有部署授权后，发布前核对本地构建、目标路径和冻结版本；发布后实查目标页面/版本、静态资源、健康、原始观测时间及功能，保存实际回执。Git push 或本地文件生成不能代替发布验收。新一期材料不要把历史 PDF 描述成自动更新后的当前稿。

## 容器与外部验收

~~~bash
docker build -f packages/dianxun-mcp/Dockerfile -t dianxun-mcp:ci .
uv run python scripts/check_docker_image.py --image dianxun-mcp:ci
uv run python scripts/check_installed_distribution.py --docker-inputs
~~~

最后一条检查安装包及镜像输入，不等于已运行 Docker。无引擎时明确记录容器烟测未执行。Lighthouse 上运行 MCP 可验证常驻 HTTP、身份、重启与业务核心；AgentTeams 动态协作、托管 PolarDB/OSS、真实通知和门店效果需分别取得证据，具体项目统一见[待办](../待办.md)。
