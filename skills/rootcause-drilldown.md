# rootcause-drilldown（兼容索引）

> 当前优先级：P0。工程契约唯一入口为 [`rootcause-drilldown/SKILL.md`](rootcause-drilldown/SKILL.md)。

该 Skill 由 Diagnoser 调用，输出证据关联的 Top-K 假设、支持/反证和检查计划。它不得把跨店相关性写成确定因果，也不得在没有真实检索时声明 RAG 命中。

输入/输出 Schema、版本、失败样例和权限边界均以独立目录为准。统一清单见 [`../docs/competition/03-Skill九要素卡.md`](../docs/competition/03-Skill九要素卡.md)。
