# 2026 年 9 月复赛材料归档

归档日期：2026-09-12。来源为本地分支 codex/fix-seven-audit-findings、基线 55860eae7d109d48b4cdb798baafe8093b63248e 及当时工作区。这里保留历史稿和当时验证记录，不能作为当前能力、正式决赛时长或线上版本的证明。

现行入口：[文档中心](../../README.md)、[决赛讲稿与问答](../../competition/finals/03-决赛逐页讲稿与问答.md)、[测试矩阵](../../测试覆盖矩阵.md)、[业务差距与试点路线](../../competition/finals/07-待办02-真实场景差距与产品完善分析.md)。

## 归档内容

| 原位置 | 历史文件入口 | 原文件 SHA-256 |
|---|---|---|
| docs/competition/02-方案PPT结构.md | [02-方案PPT结构.md](02-方案PPT结构.md) | 5d7f5a71802ef48a6705c5917f60bb0229ca6658ed4eb27a219112dd894eadb9 |
| docs/competition/08-复赛改造技术方案.md | [08-复赛改造技术方案.md](08-复赛改造技术方案.md) | 78615cf366756083494b3b7cfcdc092eb912409e5eb70dd3ce4f03ba2558ccf6 |
| docs/competition/09-复赛答辩提纲与1分钟演练口诀.md | [09-复赛答辩提纲与1分钟演练口诀.md](09-复赛答辩提纲与1分钟演练口诀.md) | 36592013d08d838631ecbe8ac77f84734cf23da81e3a79e631f679b1e2a7573e |
| docs/competition/10-2026-GOAI复赛答辩速查手册-逐光队.md | [10-2026-GOAI复赛答辩速查手册-逐光队.md](10-2026-GOAI复赛答辩速查手册-逐光队.md) | 1b5de28f51eab5862ec8b37e17a11dae939224d0e92b7f2e273c40d0b47e5cba |
| docs/competition/11-2026-GOAI复赛答辩图文全景手册-逐光队.md | [11-2026-GOAI复赛答辩图文全景手册-逐光队.md](11-2026-GOAI复赛答辩图文全景手册-逐光队.md) | 93eafd986eabcf2ab0d09338796cdf2add88ac013b997e8e4f0ac090c827d0af |
| docs/competition/12-2026-GOAI复赛答辩终极全景大纲-逐光队.md | [12-2026-GOAI复赛答辩终极全景大纲-逐光队.md](12-2026-GOAI复赛答辩终极全景大纲-逐光队.md) | 649f4d4e5fac8dc1e9568ea1b6eb61a9b46839d7ad876e3875e7009db68bb752 |
| docs/competition/比赛要求符合性矩阵.md | [比赛要求符合性矩阵.md](比赛要求符合性矩阵.md) | 762f25702e2ab90c2705c95cc238b777f7249a85cdc9a5ffc8400273316f043e |
| docs/competition/2026-GOAI复赛答辩速查手册-逐光队.pdf | [原位置保留：速查手册](../../competition/2026-GOAI复赛答辩速查手册-逐光队.pdf) | 4d51aec5ee4ac7305f32611ad3a955ccd783a9b8bacd4430b2ea3e26bc5cf2df |
| docs/competition/2026-GOAI复赛答辩图文全景手册-逐光队.pdf | [原位置保留：图文全景手册](../../competition/2026-GOAI复赛答辩图文全景手册-逐光队.pdf) | fbb3b163b2fd4bed3ad747f4bcf57896183b7c1a0c5e759832bed59999515ce1 |
| docs/competition/2026-GOAI复赛答辩终极全景大纲-逐光队.pdf | [原位置保留：终极全景大纲](../../competition/2026-GOAI复赛答辩终极全景大纲-逐光队.pdf) | 434b5b18f261638791189ddae17d199b01fa792fa5eb24b8d7aadcf8ce654a0f |
| docs/复赛QA预案.md | [复赛QA预案.md](复赛QA预案.md) | 5b9b3b19a19c36fbf4b4adb129e736869c003941e0352ca7e55f03355b9921d4 |
| docs/assessments/真实门店差距与演进路线.md | [真实门店差距与演进路线.md](真实门店差距与演进路线.md) | 3dfdb3a64cd4eed0ea2e7e273200cf4913cecd565adb57eb959c741a579a9eb1 |

旧 QA 的有效问答已合并到现行讲稿；早期门店路线中的 R0-R4、试点 KPI 和生产准入要求已汇入现行业务差距。原稿仍在本目录追溯，不再维护第二套“当前”事实。

本目录实际归档 9 份 Markdown。三份 PDF 保留在 docs/competition 原路径，保留原字节和 2026-09-04 导出日期（分别 5、8、9 页），没有删除或重导出。旧手册生成器与重复源模板已退役，正常构建仅原样复制 PDF，不再重建这些材料。

## 使用前必须阅读的勘误

| 历史材料中的问题 | 正确边界与现行依据 |
|---|---|
| 12 终极大纲称移除 Auditor 后 5 个场景错误放行 | 实际 5/6 停于 VERIFY/BLOCKED，0 放行尝试、0 错误关闭、0 不安全放行；见[消融报告](../../../evidence/m4/ablation.md) |
| 10/11/12 的减亏 60%、降噪 90%、512 设备实跑、500ms POS 等 | 没有真实经营/规模/延迟证据；动画与合成场景不能支持这些声明 |
| 09 将 ¥680 维修描述为超审批阈值；08 将同店转移当预授权 | 比赛 Policy 为维修金额大于 2000 元要求相应审批，所有 transferred 处置需食品安全审批；见[策略](../../../config/policies/coldchain-demo.v1.json) |
| 12 将 F 描述为崩溃/断网压测和自动熔断 | F 是 query_workorder partial 的本地合成分支，不能证明生产熔断/网络恢复 |
| 15 页 PPT、旧模型、87 项测试、旧运行集群说明 | 本地复赛与决赛 HTML 各 12 页；模型/测试以当前事实源和带日期的执行结果为准 |
| 鲜奶超温必然变质、熟食天然耐受、金融级/最严苛合规 | 无对应商品验证、经营或合规证据；Demo 策略不可直接决定真实食品放行 |
| QA/早期路线称没有 WAL、CAS、Metrics 或并发验证 | 独立 ContextBus 有 WAL，Incident/RuntimeContext 有版本控制，已有本地指标与并发回归；见[一致性](../../分布式一致性方案.md)及[运行手册](../../operations/runtime-recovery.md) |
| 复赛 ≤8 分钟、评分/排期、旧网站入口 | 只适用于原阶段；决赛通知与线上发布状态须分别核对 |
| 08 长方案 phase/Envelope 与当前不同 | 它是历史设计；现行领域阶段、status/data/evidence/meta 与审批规则见[协同](../../competition/07-多Agent协同设计.md)和[MCP 契约](../../competition/05-MCP工具契约.md) |

历史正文保留原叙述，以上勘误优先；其中 105/103/2、112/110/2 等带日期记录不做全局替换。图文 PDF 中的 Mermaid 源码和目录格式问题也保留为历史导出缺陷，不用于正式当前交付。

## 恢复与构建边界

归档是可通过 Git 追溯和回退的文件整理，不代表线上展示站已同步。不要把原手册正文重新作为当前能力说明，也不要恢复旧生成器覆盖现行内容。若需修订成新材料，应从现行讲稿与事实源重新组织，并独立验收输出。
