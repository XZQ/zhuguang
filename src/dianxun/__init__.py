"""店巡 Agent：连锁便利店多 Agent 异常闭环系统。

复赛目标口径为 1 个 AgentTeams Framework Manager 与 5 个业务 Agent，
冷柜失温是首要完整验证场景，缺货和价签是补充展示场景。P0 包含
6 个核心 Skill 与 12 个有状态 MCP 函数；具体事实以
``config/project-facts.json`` 为准。

0.2.0 开发线已完成 IncidentService、SQLite 状态库和 12 个 P0 MCP
函数；旧顺序编排器仍待 M2 迁移。只有通过测试并由对应 Demo 真实调用
的能力才可声明已实现。
"""

__version__ = "0.2.0.dev0"
