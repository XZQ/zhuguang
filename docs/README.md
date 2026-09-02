# 逐光｜文档中心

“逐光”是作品名，“店巡 Agent”是产品能力描述，`dianxun` 是工程标识。仓库文档按用途分层，避免比赛材料、事实审计和操作手册继续堆在根目录。项目事实优先级为：可运行代码与测试、`config/project-facts.json`、评测 Evidence、本文档体系。

## 目录

| 目录 | 内容 | 维护原则 |
|---|---|---|
| [`competition/`](competition/) | 01～08 比赛材料及比赛符合性矩阵 | 面向提交与答辩；所有数字必须能回溯到事实或 Evidence |
| [`assessments/`](assessments/) | 实现状态和真实门店差距 | 只记录已验证状态、限制与演进门禁 |
| [`demo/`](demo/) | Demo 视频脚本与证据清单 | 不得用本地 Mock、静态 YAML 或预制截图冒充平台动态证据 |
| [`operations/`](operations/) | Metrics、SLO 与恢复演练 | 严格区分目标、本地探针和生产实测 |

## 相关资料

- 运行、构建与仓库入口：[`../README.md`](../README.md)
- AgentTeams、PolarDB overlay 与动态验收：[`../agentteams/README.md`](../agentteams/README.md)
- P0 Skill 规范：[`../skills/README.md`](../skills/README.md)
- Worker/MCP 交付包边界：[`../packages/README.md`](../packages/README.md)
- M4 评测报告：[`../evidence/m4/report.md`](../evidence/m4/report.md)
- 协调恢复演练：[`../evidence/operations/recovery-drill.json`](../evidence/operations/recovery-drill.json)
- 贡献与安全：[`../CONTRIBUTING.md`](../CONTRIBUTING.md)、[`../SECURITY.md`](../SECURITY.md)
- 演示稿源文件与 PDF：[`../ppt/`](../ppt/)

## 更新规则

1. 数字或版本变化时先更新 `config/project-facts.json` 和自动化证据。
2. 再同步 `competition/`、`assessments/`、AgentTeams README、根 README 和演示稿。
3. 真实 AgentTeams、PolarDB/OSS、真实门店或官方 Skill 未取得证据前，状态必须保留为“外部待验证”或“待确认”。
4. 目录调整必须同步全部相对链接、命令和代码注释，并执行完整门禁。
