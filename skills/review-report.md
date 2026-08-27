# review-report（兼容索引）

> 当前优先级：P0。工程契约唯一入口为 [`review-report/SKILL.md`](review-report/SKILL.md)。

该 Skill 由 Auditor 在独立验证通过、事件进入 LEARN 后调用，生成事件/批次关联的复盘和待审知识候选。当前不自动发布生产知识，不声称 RAG 已命中，也不自动修改 Skill 或 Policy。

输入/输出 Schema、版本、失败样例和权限边界均以独立目录为准。统一清单见 [`../03-Skill九要素卡.md`](../03-Skill九要素卡.md)。
