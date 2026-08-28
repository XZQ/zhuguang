# anomaly-detect（兼容索引）

> 当前优先级：P0。工程契约唯一入口为 [`anomaly-detect/SKILL.md`](anomaly-detect/SKILL.md)。

该 Skill 由 Sentry 调用，用于读取设备上下文、识别持续失温并标记 Evidence 质量。它只读，不确认根因，不执行停售或商品处置。可疑传感器数据必须降权，不能直接驱动商品最终放行。

输入/输出 Schema、版本、失败样例和权限边界均以独立目录为准。9 个目标 Skill 的统一清单见 [`../docs/competition/03-Skill九要素卡.md`](../docs/competition/03-Skill九要素卡.md)。
