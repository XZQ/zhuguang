"""上下文总线:跨 Agent 传递任务上下文。

对应赛题 1.3「上下文传递」与 AgentTeams「共享状态管理」能力。
设计:
- 每个任务闭环一个 Context 对象,贯穿 created → diagnosing → ... → closed
- 各 Agent 把中间结论(异常清单/根因报告/处置工单/验证结果)写入共享上下文
- 下游 Agent 从上下文读取,而非点对点传参(解耦 Agent)
- 满足赛题 2.4「上下文增强 4 选 3」中的:共享状态管理 + 轨迹可观测(trace)

生产环境可替换为 AgentTeams Matrix Room 共享状态 / RocketMQ 事件 / PolarDB,
此处用内存对象 + JSON 落盘保证 demo 可离线运行与可审计。
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# 任务状态机:对应赛题 1.3 端到端闭环的 8 步
# created → detecting(巡检) → diagnosing(诊断) → approving(审批) →
# executing(处置) → verifying(验证) → reviewing(复盘) → closed
# 异常分支: any → reopened(验证失败回到诊断)
TaskState = Literal[
    "created", "detecting", "diagnosing", "approving",
    "executing", "verifying", "reviewing", "closed", "reopened",
]

_STATE_GRAPH: dict[str, list[str]] = {
    "created": ["detecting"],
    "detecting": ["diagnosing"],
    "diagnosing": ["approving"],
    "approving": ["executing", "closed"],   # 审批驳回可直收 closed
    "executing": ["verifying"],
    "verifying": ["reviewing", "reopened", "diagnosing"],  # 验证失败回诊断;多异常继续下一个
    "reopened": ["diagnosing"],
    "reviewing": ["closed"],
    "closed": [],
}


@dataclass
class TaskContext:
    """一个端到端任务闭环的共享上下文。

    各 Agent 读写这些字段完成协同:
      Sentry   写 anomalies
      Diagnoser 读 anomalies,写 root_causes
      Executor 读 root_causes,写 actions + approvals
      Auditor  读 actions,写 validation + review
    """
    task_id: str
    trace_id: str
    trigger: str                       # 触发来源: scheduled | event | manual
    scope: dict = field(default_factory=dict)          # 检测范围 {store_ids, window...}
    state: TaskState = "created"
    # 各阶段产物(共享上下文总线)
    anomalies: list[dict] = field(default_factory=list)       # 巡检产出
    root_causes: list[dict] = field(default_factory=list)     # 诊断产出
    actions: list[dict] = field(default_factory=list)         # 处置动作 + 审批记录
    validation: dict | None = None                            # 验证结果
    review: dict | None = None                                # 复盘报告
    # 审计
    transitions: list[dict] = field(default_factory=list)     # 状态流转记录
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def transition(self, new_state: TaskState, actor: str, note: str = "") -> None:
        """状态机流转,校验合法性并记录(可审计)。"""
        allowed = _STATE_GRAPH.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(f"非法状态流转: {self.state} → {new_state}(合法: {allowed})")
        self.transitions.append({
            "from": self.state, "to": new_state, "actor": actor,
            "note": note, "at": datetime.now().isoformat(timespec="seconds"),
        })
        self.state = new_state

    def snapshot(self) -> dict:
        """落盘快照(审计/复盘用)。"""
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2, default=str))


class ContextBus:
    """上下文总线:管理多个并行任务的上下文。

    AgentTeams 映射:对应 Matrix Team Room 中的共享状态 + MinIO 共享文件。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, TaskContext] = {}

    def create(self, task_id: str, trace_id: str, trigger: str = "scheduled",
               scope: dict | None = None) -> TaskContext:
        ctx = TaskContext(task_id=task_id, trace_id=trace_id, trigger=trigger,
                          scope=scope or {})
        self._tasks[task_id] = ctx
        return ctx

    def get(self, task_id: str) -> TaskContext:
        if task_id not in self._tasks:
            raise KeyError(f"未知任务 {task_id}")
        return self._tasks[task_id]

    def all(self) -> list[TaskContext]:
        return list(self._tasks.values())
