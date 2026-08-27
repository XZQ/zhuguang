"""5 个业务 Agent（对应赛题 Agent Identity 清单）。

AgentTeams 映射:
  Framework Manager = 框架协调入口，不计入业务 Agent
  Orchestrator = Team Leader（任务拆解/调度，delegation-first）
  Sentry / Diagnoser / Executor / Auditor = 业务 Workers

每个 Agent:
- 有清晰身份定义(见 06-Agent-Identity清单.md)
- 通过 Skill + MCP 工具完成职能
- 读写共享上下文总线(ContextBus)
- 每步经 trace.span 埋点

本地 Demo 使用确定性规则；AgentTeams 自然语言层可接模型，但不能替代
领域规则、审批门禁或 IncidentService 状态聚合。
"""

from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
