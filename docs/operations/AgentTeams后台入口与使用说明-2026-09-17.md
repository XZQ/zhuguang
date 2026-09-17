# 逐光队 AgentTeams 后台入口与使用说明

整理时间：2026-09-17 23:18（北京时间）。已通过广州服务器和本机 SSH 隧道实测。

## 直接打开

本机到广州的 SSH 隧道已启动。下列地址适用于当前这台 Mac；在其他电脑或手机上打开 `127.0.0.1` 不会访问到本后台。

| 后台 | 可点击入口 | 用途 | 本次验证 |
|---|---|---|---|
| 逐光集群统一后台门户 | [打开统一门户](https://mazhi.icu/zhuguang/admin/) | 一站式切换 Manager/Higress/Element | HTTP 200，支持快捷登录与内嵌操作 |
| Manager / QwenPaw 控制台 | [打开 Manager](https://mazhi.icu/zhuguang/manager/) 或 [本地隧道](http://127.0.0.1:28888/) | Agent 管理与交互的优先入口 | HTTP 200，QwenPaw Console 完整就绪 |
| Higress AI 网关后台 | [打开 Higress](https://mazhi.icu/zhuguang/higress/) 或 [本地隧道](http://127.0.0.1:28001/) | 模型服务、API 网关、路由管理 | HTTP 200，Higress 控制台就绪 |
| Element 团队聊天 | [打开 Element](https://mazhi.icu/zhuguang/chat/) 或 [本地隧道](http://127.0.0.1:28088/) | Matrix 团队房间、Manager/Worker 协作消息 | HTTP 200，已配置专属 Human 账号与全房间权限 |
| Matrix 协议入口 | [查看服务版本](https://mazhi.icu/zhuguang/matrix/_matrix/client/versions) | Element 使用的消息服务器接口 | HTTP 200，Tuwunel Matrix 协议正常响应 |
| 对外比赛主页 | [打开逐光主页](https://mazhi.icu/zhuguang/) | 演示、PPT 与现场集群看板 | 已挂载后台卡片与实机状态看板 |

### Element 聊天登录凭据 (Matrix Human 账号)
- **服务器地址 (Homeserver)**: `https://mazhi.icu/zhuguang/matrix`（或内网 `matrix-local.agentteams.io:28080`）
- **登录账号 (Username)**: `admin`（或完整 Matrix ID `@admin:matrix-local.agentteams.io:28080`）
- **登录密码 (Password)**: `Zhuguang2026!`
- **已加入房间**: 
  - `Team: dianxun-patrol-team` (主工作团队)
  - `Manager: default` (总控调度)
  - 5 大 Worker 协同房间 (`orchestrator`, `sentry`, `diagnoser`, `executor`, `auditor`)
  - 巡检工单事件房间 (`S03 compressor failure live closure`)
  - Matrix 底层管理房间 (`Admin Room`)

## 后台实际在哪里

后台主要部署在广州服务器 `119.29.105.15`（Tailscale `100.116.162.22`）。

| 服务 | 服务器监听/映射 | 组件 |
|---|---|---|
| Manager | 广州 `127.0.0.1:28888` → 容器 `18799` | `agentteams-manager` |
| Higress | 广州 `127.0.0.1:28001` → 容器 `8001` | `agentteams-controller` 内部服务 |
| Element Web | 广州 `127.0.0.1:28088` → 容器 `8088` | `agentteams-controller` 内部服务 |
| Matrix 网关入口 | 广州 `127.0.0.1:28080` → 容器 `8080` | 网关按路径转发 Matrix 请求 |
| Controller Worker API | 广州 Tailscale `100.116.162.22:8090` | Worker 鉴权、状态及管理接口，非独立网页 |
| 店巡 MCP | 广州 Tailscale `100.116.162.22:18090` | 店巡业务工具服务，非网页控制台 |

Element 当前配置中的 homeserver 为 `http://127.0.0.1:28080`，因此聊天页面与 Matrix 网关两个端口都需要转发。只打开 28088 可能看到页面但不能连接消息服务。

本次没有修改 Nginx 公网路由或开放新的公网管理端口。浏览器通过本机回环端口及加密 SSH 隧道访问已有后台。

## 断线后的恢复方法

连接脚本：`/Users/walle/Documents/zhuguang/agentteams-backend-tunnel.sh`。

启动：

```bash
/Users/walle/Documents/zhuguang/agentteams-backend-tunnel.sh start
```

检查连接：

```bash
/Users/walle/Documents/zhuguang/agentteams-backend-tunnel.sh status
```

关闭本次建立的连接：

```bash
/Users/walle/Documents/zhuguang/agentteams-backend-tunnel.sh stop
```

脚本沿用本机现有 SSH 公钥登录广州，不依赖本机 Tailscale，也不包含密码。隧道在 Mac 重启、网络长时间中断后可能需要重新启动；没有安装开机自启任务。若提示端口占用，先检查占用进程，不要直接终止其他业务。

## 当前 Worker 分布

| Worker | 所在节点 | 现场核查结果 |
|---|---|---|
| Orchestrator | 上海 | 容器运行 |
| Sentry | 上海 | 容器运行 |
| Diagnoser | 首尔 | 容器运行 |
| Executor | AWS 东京（本次从已下线的雅加达腾讯迁移） | 容器运行、心跳 ready、Agent idle、MCP 已连接 |
| Auditor | 新加坡 | 容器运行 |

详细 IP、镜像与验证边界见《逐光队-Worker实际部署服务器核查-2026-09-17.md》。

## 使用时需要区分的状态

- 后台页面可打开：本次已验证。
- 五个 Worker 容器运行：本次已分别验证。
- Executor 心跳与基础连接：本次已验证。
- 控制端状态：Executor 查询仍显示 Pending / not_found，尚未与远端实际状态一致。
- 完整业务闭环成功：本次没有运行该项测试，不能由页面、容器或心跳推定。
- 公开主页及 status.json：含旧快照，不应用作当前全部节点健康状态的依据。
