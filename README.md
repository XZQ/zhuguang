# 店巡 Agent — 连锁便利店多店异常闭环巡检系统

GOAI 世界人工智能开源大赛 · Agent Infra 新智基座赛道

5 职能 Agent + 7 可复用 Skill + 7 MCP 工具,基于 AgentTeams 实现「多源聚合→异常识别→跨店诊断→处置执行→恢复验证→复盘沉淀」端到端闭环。核心创新:跨店横向对比诊断代替人工经验 + 全链路 Trace 可审计 + 经验沉淀飞轮。

## 快速开始

```bash
# 1. 生成模拟数据(12店 40SKU 14天,含冷柜超温/缺货/价签异常注入)
python3 04-模拟数据生成脚本.py

# 2. 跑端到端 Demo(三场景全闭环,零依赖)
PYTHONPATH=src python3 demo/run_demo.py

# 3. 打开复盘报告(终端彩色 + HTML 报告双输出)
open demo/report.html

# 4.(可选)启动 MCP Server,16 个工具可 curl 调用
PYTHONPATH=src PORT=8080 python3 -m dianxun.mcp.server &
curl -X POST http://127.0.0.1:8080 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
# 单工具调用示例:查 S05 库存
curl -X POST http://127.0.0.1:8080 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"query_stock","arguments":{"store_id":"S05"}}}'

# 5.(可选)单独调用某个 Skill 验证
PYTHONPATH=src python3 -c "from dianxun.skills import anomaly_detect; r=anomaly_detect(store_ids=['S03']); print(f'检出{r[\"count\"]}个异常')"

# 6.(可选)导出 PPT 为 PDF(横向 A4,10 页)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --force-prefers-reduced-motion \
  --print-to-pdf="ppt/店巡Agent方案.pdf" --no-pdf-header-footer \
  --virtual-time-budget=8000 "file://$(pwd)/ppt/index.html"
```

Demo 输出:终端彩色流程(各 Agent 专属配色)+ `demo/report.html` 复盘报告(Data-Dense Dashboard 风格,含 8 步流程图/跨店对标柱状图/Trace 时间线/知识飞轮)。

## 文件索引

### 初赛必交材料

| 文件 | 内容 | 状态 |
|---|---|---|
| `01-作品简介-500字.md` | 作品简介(464字) | ✅ |
| `ppt/index.html` | 方案 PPT(瑞士风格 10 页,含动画) | ✅ |
| `ppt/店巡Agent方案.pdf` | PPT 导出 PDF(横向 A4 10 页) | ✅ |
| `06-Agent-Identity清单.md` | Agent Identity 清单(赛题 1.2) | ✅ |
| `07-多Agent协同设计.md` | AgentTeams 5 维度映射 + 8 步闭环(赛题 1.1/1.3) | ✅ |

### 设计文档

| 文件 | 内容 |
|---|---|
| `02-方案PPT结构.md` | PPT 9 页结构(评审权重对照) |
| `03-Skill九要素卡.md` | 7 Skill 汇总(赛题 2.1 必选) |
| `skills/` | 7 Skill 拆分为独立文件(含索引) |
| `05-MCP工具契约.md` | 7 MCP 工具契约(赛题 2.2 推荐) |

### 可运行代码(`src/dianxun/`)

```
src/dianxun/
├── mcp/          工具连接层:7 工具读 csv 模拟外部系统 + MCP Server(Streamable HTTP)
├── skills/       能力抽象层:7 Skill 纯函数(九要素齐全)
├── agents/       Agent 协同层:5 Agent 编排 + 闭环状态机
├── context_bus.py 上下文总线(跨 Agent 传递)
├── trace.py      可观测:全链路 Trace 埋点(OTel GenAI 兼容)
└── knowledge/    RAG:复盘知识条目存储(SQLite→PolarDB 可替换)
```

### AgentTeams 部署(`agentteams/`)

| 文件 | 说明 |
|---|---|
| `manager.yaml` | Manager(协调入口) |
| `team.yaml` | 店巡小队(1 Leader + 4 Worker) |
| `workers/*.yaml` | 5 Worker(总控/巡检/诊断/处置/稽核) |
| `README.md` | 部署步骤(Docker + agt apply) |

### Worker 包(`packages/dianxun-worker/`)

`IDENTITY.md` / `SOUL.md` / `AGENTS.md` / `Dockerfile` / `requirements.txt` — QwenPaw(Python)运行时,可构建为 Docker 镜像或 AgentTeams package。

## 赛题对照

| 赛题要求 | 本方案 | 证据 |
|---|---|---|
| **1.1** ≥3 职能 Agent,以 AgentTeams 为基点 | 5 Agent(Manager+Leader+4Worker),三层架构 | `07-多Agent协同设计.md` |
| **1.1** 5 维度映射(角色编排/任务拆解/上下文传递/协同执行/状态追踪) | 全覆盖 | `07` 第一章 |
| **1.2** Agent Identity 清单 | 6 Agent 身份/能力边界/协同关系 | `06-Agent-Identity清单.md` |
| **1.3** 8 步闭环 | 全跑通,每步有 Trace | `07` 第二章 + `demo/` |
| **2.1** Skill 必选,九要素 | 7 Skill 九要素齐全 | `skills/*.md` + `src/dianxun/skills/` |
| **2.2** MCP 推荐(或等价契约) | 7 MCP 工具 + MCP Server | `05-MCP工具契约.md` + `src/dianxun/mcp/` |
| **2.3** 可观测推荐(Trace/Log/Metrics ≥1) | 全链路 Trace,OTel GenAI 兼容 | `src/dianxun/trace.py` |
| **2.4** RAG/上下文(4 选 ≥2) | 知识库 RAG + 共享状态管理 + 轨迹可观测(实现 3 项) | `knowledge/` + `context_bus.py` |

## 核心设计

- **业态**:连锁便利店(数据丰富、行业普遍、可复制到超市/餐饮/药房)
- **协同基座**:AgentTeams(Manager-Worker 架构,角色编排/任务拆解/上下文传递/协同执行/状态追踪)
- **5 职能 Agent**:总控 Orchestrator / 巡检 Sentry / 诊断 Diagnoser / 处置 Executor / 稽核 Auditor
- **7 可复用 Skill**:anomaly-detect / cross-store-benchmark / rootcause-drilldown / restock-order-gen / price-tag-check / work-order-dispatch / review-report
- **技术栈**:AgentTeams + Nacos + Higress + RocketMQ + PolarDB for PostgreSQL + LoongSuite/AgentLoop
- **核心创新**:① 跨店横向对比诊断代替人工经验;② 全链路 Trace 可审计;③ 复盘自动沉淀 Skill 飞轮

## 赛程提醒

- 初赛提交截止:2026-08-16(作品简介 + 方案 PPT)— **本仓库已就绪**
- 复赛:8.25-9.3(可执行 AgentTeams 代码包 + Demo)— **`src/` + `agentteams/` + `demo/` 已就绪**
- 决赛:9.22 线下答辩
