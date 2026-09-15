# 店巡 Agent 文档

复核日期：2026-09-13。队名为逐光，仓库作品名为店巡 Agent；VeriAgent 是决赛准备稿工作标题。代码、配置和实际执行证据优先于文档描述。

## 阅读入口

| 需要做什么 | 文档 |
|---|---|
| 队友部署决赛服务端、执行二轮验收 | [决赛服务端部署与取证手册](operations/finals-server-handoff.md)：配置、命令、证据契约和交接标准 |
| 看当前工作和验收缺口 | [待办](待办.md)：唯一进度入口，含原待办 01/02/03 的结论 |
| 理解架构、角色、Skill、MCP、事务和场景 | [技术说明](技术说明.md) |
| 看已实现能力、测试结果与证据边界 | [测试覆盖矩阵](测试覆盖矩阵.md) |
| 接入 Worker、监测、恢复与回滚 | [运行与恢复](operations/runtime-recovery.md) |
| 部署服务、构建网页与保留 PDF | [部署与发布](operations/Lighthouse部署与验证手册.md) |
| 看当前手册、决赛材料和历史 PDF | [项目与答辩手册](competition/店巡Agent-项目与答辩手册.pdf) / [比赛材料](competition/README.md) |
| 查历史提交的新旧 SHA | [Git 历史映射](operations/git-history-linearization-20260913.md) |

docs 仅保留 operations、competition、assets 三个子目录。业务源码和契约仍在原目录维护：[src](../src/dianxun)、[Skill](../skills/README.md)、[AgentTeams](../agentteams/README.md)、[交付包](../packages/README.md)。

## 维护约定

1. 所有未完成工作只在待办.md 更新。方案完成、代码完成、本地通过、外部验收分别记录；没有证据不标成完成。
2. 技术和运维文档描述当前用法，不再保存另一份待办列表。完成事项只保留结论与证据入口，过程从 Git 追溯。
3. 测试数字只在事实源与测试矩阵维护；其他页面引用入口。更新日期不代表重新验证了服务器、平台或门店。
4. 已被当前说明替代的复赛 Markdown、重复审查稿和阶段交付记录不再留存目录副本；三份历史 PDF 按原路径、原字节保留。
5. 网页和 SVG 从模板生成；当前手册用独立脚本从现行 Markdown 与事实源导出并逐页检查。PPT/PDF/离线包是带日期的制品，修改 Markdown 不会自动更新它们。
6. 修改目录时同步引用和检查脚本，执行[贡献约定](../CONTRIBUTING.md)中的相关门禁。
