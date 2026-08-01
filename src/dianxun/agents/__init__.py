"""5 个职能 Agent(对应赛题 Agent Identity 清单)。

AgentTeams 映射:
  总控 Orchestrator = Team Leader(任务拆解/调度,delegation-first)
  巡检/诊断/处置/稽核 = Workers(各带专属 Skill)

每个 Agent:
- 有清晰身份定义(见 06-Agent-Identity清单.md)
- 通过 Skill + MCP 工具完成职能
- 读写共享上下文总线(ContextBus)
- 每步经 trace.span 埋点

Agent 决策:demo 用规则引擎(确定性),生产可换 LLM(文档说明)。
"""

from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
