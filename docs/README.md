# 逐光队｜文档中心

队名为逐光，仓库作品名为店巡 Agent；09-12 决赛准备稿使用 VeriAgent 作为工作标题，尚未据此宣布正式更名。冷柜失温是首个验证场景，dianxun 是工程标识。决赛标题和发布版本在交付冻结时统一。

事实优先级：实际代码与执行证据、config/project-facts.json、对应日期/版本的文档。当前说明和历史快照分开维护。

## 当前入口

| 用途 | 文档 |
|---|---|
| 实现与证据 | [实现状态矩阵](assessments/实现状态矩阵.md)、[测试覆盖矩阵](测试覆盖矩阵.md) |
| 验证机制 | [Agent 验证](Agent验证机制.md)、[状态一致性](分布式一致性方案.md)、[MCP 可靠性](MCP延迟与可靠性.md) |
| 决赛材料 | [材料索引](competition/README.md)、[讲稿与问答](competition/finals/03-决赛逐页讲稿与问答.md)、[一页简介](competition/finals/04-项目一页简介.md) |
| 持续待办 | [决赛准备执行清单](competition/finals/02-决赛准备执行清单.md) |
| 业务差距 | [真实场景与产品分析](competition/finals/07-待办02-真实场景差距与产品完善分析.md)、[36 项验收计划](competition/finals/08-待办02-场景与验收清单.md) |
| 运行接口 | [Worker runtime](operations/worker-runtime.md)、[故障恢复](operations/runtime-recovery.md)、[SLO/演练](operations/SLO与恢复演练.md) |
| 部署与展示 | [Lighthouse](deployment/Lighthouse部署与验证手册.md)、[门户构建与模板](operations/delivery-portal.md)、[视频证据清单](demo/Demo视频脚本与证据清单.md) |
| 历史记录 | [复赛归档与勘误](archive/2026-09-semifinals/README.md)、[七项修复](assessments/seven-finding-repairs.md)、[运行接口复核](assessments/runtime-review-followup.md) |
| 架构资产 | [SVG](assets/architecture-flow.svg)，由模板生成，表示配置/流程，不证明在线状态 |

## 工程入口

- [根 README](../README.md)、[贡献约定](../CONTRIBUTING.md)、[安全策略](../SECURITY.md)
- [AgentTeams/PolarDB 与平台取证](../agentteams/README.md)、[Skill](../skills/README.md)、[交付包](../packages/README.md)
- [M4 评测](../evidence/m4/report.md)、[消融](../evidence/m4/ablation.md)、[协调演练](../evidence/operations/recovery-drill.json)
- [决赛 PPT 工作稿](../ppt/finals.html)、[演示稿与历史 PDF](../ppt/)

## 维护规则

1. 数字变化先取得实际执行证据，再更新事实源与测试矩阵；其他说明优先链接权威入口。
2. 发布声明区分本地实现/模拟、外部待验证、规划。静态配置、动画和单元测试不能代替平台或门店证据。
3. 历史文档保留原日期/版本与勘误，不用全局替换数字改写历史；现行导航不再直接使用旧答辩稿。
4. 门户/SVG 从现行模板重建。旧三套复赛手册生成器已停用；三份历史 PDF 保留在 competition 原路径，构建仅原样复制，不宣称已更新。
5. 目录变更同步链接、生成入口和 CI，运行相关检查及完整门禁。提交、推送、发布仍需用户明确要求。
