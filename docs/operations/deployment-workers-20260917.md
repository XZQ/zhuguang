# 逐光队部署与 Worker 运行核查（2026-09-17）

本页为公开脱敏记录，核查时间为 2026-09-17 23:01–23:18（北京时间）。服务器地址、SSH 身份、认证材料、运行数据库和内部管理连接由私有运维文档维护，不提交到公开仓库。

## 实际部署拓扑

| 位置 | 组件 | 本次现场证据 |
|---|---|---|
| 广州 | AgentTeams Controller、Manager、店巡 MCP、逐光展示主页 | Controller / Manager 容器运行；MCP 进程及监听存在；Nginx 主页路由已核对 |
| 上海 | Orchestrator、Sentry | 两个 Worker 容器均 running，Up 2 weeks |
| 首尔 | Diagnoser | Worker 容器 running，Up 2 weeks |
| 新加坡 | Auditor | Worker 容器 running，Up 2 weeks |
| AWS 东京 | Executor | 本次迁入；容器 running、零重启，Agent idle，心跳 ready |
| 雅加达腾讯 | Executor 的旧部署位置 | 维护者确认节点已下线，由东京替代 |

核查基于服务器 SSH、Docker inspect、进程/监听信息及东京 Worker 内部接口；不以展示页面徽章或旧 status.json 作为当前在线证明。

## Worker 角色与版本

| Worker | 容器名 | 职责 | 容器启动时间（北京时间） |
|---|---|---|---|
| Orchestrator | `agentteams-worker-orchestrator` | 计划、委派和跨 Agent 协调 | 2026-09-03 16:28:52 |
| Sentry | `agentteams-worker-sentry` | 巡检、证据采集、异常分级 | 2026-09-03 16:52:58 |
| Diagnoser | `agentteams-worker-diagnoser` | 风险评估和根因诊断 | 2026-09-03 16:56:01 |
| Executor | `agentteams-worker-executor` | 审批后的受控执行 | 2026-09-17 23:14:05 |
| Auditor | `agentteams-worker-auditor` | 独立核验、复盘与关闭建议 | 2026-09-03 16:59:08 |

五个 Worker 镜像标签均为：

```text
higress-registry.cn-hangzhou.cr.aliyuncs.com/agentteams/agentteams-qwenpaw-worker:v1.2.3
```

东京拉取的镜像摘要为 `sha256:6bc61f3857c5cd290d5f75f2d07eb584b6560cdacdce373a7aedf786f95abd0d`。未逐一比较其他节点的镜像摘要，不将相同标签等同于字节一致。

广州项目检出 HEAD 为 `151e92ec0d6a96fb73335969bfac9832fbef9b40`。它只证明该目录版本，不代表运行中的 MCP、Worker 业务包、网页或当前 GitHub main 同步到了该提交；本次未验证整个工作树是否干净。

## Executor 东京迁移

沿用已有 Executor 身份和广州 MinIO 工作区，迁入 Amazon Linux 2023 / x86_64 主机。没有复制 AWS 登录私钥，没有开放 Worker 公网管理端口。

部署配置包括 `unless-stopped` 自动重启、2 GB 内存上限、1.5 核 CPU 上限、10 MB × 3 日志轮转及独立持久卷。既有短期 ServiceAccount 令牌续期配置新增 Executor，按 20 分钟周期续期、有效期 1 小时；单次续期已实测成功，完整过期窗口尚未观察。

| 验证项 | 本次结果 |
|---|---|
| 容器状态 | running，RestartCount=0 |
| Agent 状态接口 | HTTP 200，status=idle |
| 广州 Controller 鉴权 | HTTP 200，续期后再次读取成功 |
| Worker 心跳文件 | status=ready，updatedAt=`2026-09-17T15:17:14.801455+00:00` |
| Controller 心跳确认 | 日志出现 `controller ready report accepted` |
| Matrix | Executor 身份登录并启动消息同步循环 |
| 店巡 MCP | 日志出现 `MCP client connected: dianxun-mcp` |
| 工作区 | IDENTITY.md、AGENTS.md、TEAMS.md 已恢复 |
| Skill 文件 | 工作区及 agent-package 均存在 `work-order-dispatch/SKILL.md` |

**重要边界：** Controller 查询仍返回 `phase=Pending`、`containerState=not_found`，与远端容器及 ready 心跳不同。未改写状态制造通过。文件存在、协议连接成功和容器运行均不等于实际 Skill 执行、审批、受控动作及独立复核完成。F02 主链验收保持未完成，后续工作统一见[待办](../待办.md)。

## 管理后台与展示主页

| 入口/组件 | 用途 | 本次核查 |
|---|---|---|
| [逐光展示主页](https://mazhi.icu/zhuguang/) | 公开演示、PPT、场景资料 | 页面可访问，线上内容不代表最新运行状态 |
| QwenPaw Manager Console | Manager 管理与交互 | SSH 隧道实测 HTTP 200，页面标题 QwenPaw Console |
| Higress Console | 模型服务、API 网关和路由管理 | SSH 隧道实测 HTTP 200，页面标题 Higress Console |
| Element Web / Matrix | 团队房间与协作消息 | 页面及 Matrix versions 接口均 HTTP 200 |

后台当前通过受控连接访问。`/zhuguang/` 同站点的受保护后台接入尚未完成，不能把计划路径写成已上线地址。账号登录及全部管理操作未在本次逐项验收。

`agentscope-ai` 是 GitHub 项目组织；[AgentTeams](https://github.com/agentscope-ai/AgentTeams) 和 [QwenPaw](https://github.com/agentscope-ai/QwenPaw) 是源码仓库，不是这套部署的后台登录入口。

本会话读取的公开 `status.json` 生成时间仍为 9 月 3 日，字段存在冲突；历史快照没有被改写成实时健康状态。

## 证据与维护方式

本页是人工核查摘要，原始内部命令结果与连接细节保留在私有运维记录，不构造平台 Trace 或业务通过结果。后续运行验收继续遵循[服务端部署与取证手册](finals-server-handoff.md)和[统一待办](../待办.md)；认证续期机制见 [AgentTeams 运维说明](../../agentteams/ops/README.md)。

此次提交仅更新文档，不修改业务代码、Schema、Skill 契约或生成的 Worker 包，也不代表远端自动同步部署。
