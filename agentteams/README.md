# AgentTeams 部署配置

本目录是店巡 Agent 的 AgentTeams 声明式部署配置(Kubernetes CRD 风格 YAML)。

## 架构(三层)

```
Admin(人类)
  └─ Manager(dianxun-manager)              ← 协调入口,编排 Team
       └─ Team(dianxun-patrol-team)
            ├─ orchestrator [Team Leader]  ← 总控:任务拆解/调度/状态追踪
            ├─ sentry      [Worker]        ← 巡检:异常识别
            ├─ diagnoser   [Worker]        ← 诊断:跨店对标/根因
            ├─ executor    [Worker]        ← 处置:工单/补货/改价
            └─ auditor     [Worker]        ← 稽核:验证/复盘
```

## 文件

| 文件 | 说明 |
|---|---|
| `namespace.yaml` | dianxun 命名空间 |
| `manager.yaml` | Manager(协调入口) |
| `team.yaml` | 店巡小队(1 Leader + 4 Worker) |
| `workers/orchestrator.yaml` | Team Leader · 总控 |
| `workers/sentry.yaml` | Worker · 巡检 |
| `workers/diagnoser.yaml` | Worker · 诊断 |
| `workers/executor.yaml` | Worker · 处置 |
| `workers/auditor.yaml` | Worker · 稽核 |

## 部署步骤

### 前置条件
- Docker Desktop(macOS/Windows)或 Docker Engine(Linux),最低 2C4G
- AgentTeams v1.2.0+,已通过 `install/agentteams-install.sh` 完成安装
- MCP Server 已部署(见 `../packages/dianxun-worker/`)

### 1. 部署 MCP Server
```bash
# 构建 MCP Server 镜像(见 packages/dianxun-worker/Dockerfile)
cd packages/dianxun-worker
docker build -t dianxun-mcp:0.1.0 .
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata: { name: dianxun-mcp, namespace: dianxun }
spec:
  selector: { app: dianxun-mcp }
  ports: [{ port: 80, targetPort: 8080 }]
EOF
```

### 2. 部署 AgentTeams 资源
```bash
# 创建命名空间
kubectl apply -f namespace.yaml

# 部署 Manager + Team + Workers(声明式,Controller 自动调和)
agt apply -f manager.yaml
agt apply -f workers/         # 5 个 Worker
agt apply -f team.yaml        # Team 引用(须在 Worker 之后)

# 或一次性
agt apply -f . --recursive
```

### 3. 验证
```bash
agt get workers               # 应见 5 个 Worker Running
agt get teams                 # 应见 dianxun-patrol-team
docker ps | grep agentteams   # 应见 5 个 worker 容器 + manager
```

### 4. 触发任务
在 Element Web(http://127.0.0.1:18088)进入店巡 Team Room,向 orchestrator 发送:
> 巡检 S03/S05/S08 三店

Manager 收到后下发给 Team Leader,触发完整闭环。

## 关键设计决策

1. **runtime: copaw(QwenPaw/Python)**:与本项目 Python Skill 栈一致,无需跨语言
2. **package 共享**:5 个 Worker 引用同一 `packages/dianxun-worker`,内含全部 7 个 Skill,按 `agents` 规则决定各自调用哪些
3. **MCP 经 Higress 网关**:Worker 不持有真实凭证,只拿 consumer token,凭证由网关管理(企业级安全)
4. **delegation-first**:Manager 只与 Team Leader 通信,不绕过 Leader 直接调度 Worker

## 替代方案说明

若不使用 AgentTeams 容器化部署,本项目的 `src/dianxun/agents/orchestrator.py` 提供了纯 Python 编排实现,
`demo/run_demo.py` 可直接跑通三场景闭环(无需 Docker)。生产部署时 AgentTeams 提供更强的可观测、可审计与人工介入能力。
