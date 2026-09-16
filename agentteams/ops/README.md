# 外置 Docker Worker 凭据续期

适用范围：本项目现有隔离比赛拓扑，AgentTeams v1.2.3、嵌入式 Controller、
`default` namespace、默认 `agentteams-` SA 前缀、`containerManaged:false` 的外置
Docker Worker。不是通用 Kubernetes 凭据管理器；其它拓扑先核对官方配置，不直接套用。
当前验收状态只见 [统一待办 F02](../../docs/待办.md)。

## 原因与边界

官方 `ProjectSAToken` 默认签发一小时凭据；`ReconcileMemberContainer` 对外置 Worker
提前返回，不执行 Docker Token 自动投影。首次安装复制的文件会过期，导致 Worker API
正常但 Controller 心跳 401。官方 `agt rotate` 处理 Matrix 凭据，不修复此问题。

`scripts/renew_agentteams_tokens.py` 在 Controller 宿主执行：

1. 用既有 SSH 主机密钥和身份连接目标，检查正在运行的同名 Worker、token-file 环境变量
   和只读挂载。仅允许五个比赛角色；固定文件路径，不创建容器或新账号。
2. 在 Controller 内用其已有本地管理认证和 CA 调用官方 TokenRequest，再 TokenReview
   验证签名、Worker 身份和 audience。仅签发 3600 秒，不转移管理员凭据。
3. 短期 Worker Token 只经子进程管道和 SSH stdin 传递，不在命令参数或日志中出现。
4. 再次检查目标，拒绝错身份、非 0600 文件、符号/硬链接、过期或异常长效 Token。
   对既有文件加写锁并保留 inode，避免 rename 后 Docker 单文件挂载仍读旧 inode。

文件写入并非对无锁读者原子的：Worker 可能碰到极短的读取竞争，随后心跳会重试。
写入异常尝试恢复旧内容并失败退出；宿主崩溃造成损坏时须人工修复同身份投影，不能
绕过校验。长期更适合使用目录挂载和原子替换，但需要单独评审容器重建，当前未实施。
日志成功只证明投影成功，**还必须验证容器读取和 Controller 自然心跳**。

## 安装及验收

前置：Controller 主机的 `ubuntu` 已可用 Docker，目标 SSH 已验证主机密钥，远端该账号
已有 `sudo -n` 权限。脚本不创建或扩大 SSH/sudo 权限。现有 worker token 挂载源必须为
`/home/ubuntu/agentteams-competition/worker-tokens/<worker>.token`，容器目标必须为
`/var/run/secrets/agentteams/token`。禁止同时配置覆盖文件的 `AGENTTEAMS_AUTH_TOKEN`。

把脚本和这两个 systemd 单元复制到 Controller 宿主的受控比赛 `runtime/` 目录。
在该目录创建 `zhuguang-token-targets.json`，使用已验证的 SSH alias/主机，例如：

```json
[
  {"worker": "diagnoser", "ssh_host": "your-verified-worker-alias"}
]
```

非默认 SSH 身份可加 `ssh_identity_file`，它只能是该宿主已有的路径；不填私钥内容。
列表只含逐一核验过的 Worker，不因凑齐五角色而填入未知节点。配置不进 Git。

先运行一次并检查退出码、容器内自己的 authenticated status，以及 Controller 自然
`[READY] Worker ... reported ready` 日志。不要通过手填 CR 状态或手工伪造心跳验收。
嵌入式 Controller 日志在容器 `/var/log/agentteams/agentteams-controller*.log`，
不是仅看 `docker logs`；检查时过滤结果，不导出原始秘密或业务数据。

```bash
python3 /home/ubuntu/agentteams-competition/runtime/renew_agentteams_tokens.py \
  --targets /home/ubuntu/agentteams-competition/runtime/zhuguang-token-targets.json
systemd-analyze verify /home/ubuntu/agentteams-competition/runtime/zhuguang-worker-token-renew.{service,timer}
# 确认不存在同名其它服务后，由获授权管理员安装两个单元到 /etc/systemd/system/。
sudo systemctl daemon-reload
sudo systemctl enable --now zhuguang-worker-token-renew.timer
systemctl show zhuguang-worker-token-renew.service -p Result -p ExecMainStatus
systemctl list-timers --all zhuguang-worker-token-renew.timer
```

定时器开机两分钟后首次触发，此后每次结束 20 分钟再执行。service 为 `oneshot`，
完成后 inactive/dead 是正常状态；验收看退出码、日志、下次触发时间和 Worker 行为。
不能把首次触发成功表述为已经跨越一小时续期窗口验证。失败须检查专用 journal
及该角色认证状态，不自动重启 Worker，也不更换为管理员身份。

## 停用与恢复

```bash
sudo systemctl disable --now zhuguang-worker-token-renew.timer
```

停用不删除凭据，不重启任何业务容器；但最后签发的 Token 到期后 Worker 认证会失败。
因此仅在已有替代投影机制或暂停该比赛环境时停用。恢复时先验证一次投影和真实心跳，
再启用 timer。不要恢复已经过期的 Token 来声称回滚成功。

本脚本不更新 MCP/Matrix/模型凭据，不证明 Team Ready、LLM 配额、Skill 委派、Human
批准、独立 Auditor、PolarDB 或真实业务闭环已完成。
