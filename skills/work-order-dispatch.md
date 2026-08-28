# work-order-dispatch（兼容索引）

> 当前优先级：P0。工程契约唯一入口为 [`work-order-dispatch/SKILL.md`](work-order-dispatch/SKILL.md)。

该 Skill 由 Executor 调用，根据 Top-1 当前假设创建幂等维修动作。Demo Policy 中预算大于 2000 的工单必须先获批准；审批 pending、rejected 或 timeout 时不得创建受控工单。付款不在系统权限内。

输入/输出 Schema、版本、失败样例和权限边界均以独立目录为准。统一清单见 [`../docs/competition/03-Skill九要素卡.md`](../docs/competition/03-Skill九要素卡.md)。
