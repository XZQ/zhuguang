"""店巡 Agent — 连锁便利店多店异常闭环巡检系统。

核心包结构:
- mcp/      工具连接层:7 个 MCP 工具(读 csv 模拟 POS/WMS/IoT/价格/IM/审批/工单)
- skills/   能力抽象层:7 个核心 Skill(九要素齐全)
- agents/   Agent 协同层:闭环状态机编排
- context_bus 上下文总线:跨 Agent 传递诊断结论/处置状态
- trace    可观测:全链路 Trace 埋点(LoongSuite/OpenTelemetry GenAI 兼容)
- knowledge/ RAG:复盘知识条目存储(本地 SQLite,PolarDB 可替换)
"""

__version__ = "0.1.0"
