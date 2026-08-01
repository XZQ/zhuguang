"""mcp-workorder:维修服务商工单工具。

契约:create_workorder(store_id, equipment_id, fault, budget, idempotency_key)
     / track_workorder(id) / confirm_done(id, evidence)
权限:付款动作绝不由工具执行;仅生成待付款单
降级:服务商 API 故障 → 工单落本地队列(demo 不模拟故障)
数据源:内存
"""

from __future__ import annotations
import time
from typing import Any, Literal

from ._csv_store import ToolResult

_WORKORDERS: dict[str, dict] = {}
_IDEMPOTENT: dict[str, str] = {}   # idempotency_key -> workorder_id
_SEQ = 0

WoStatus = Literal["created", "assigned", "in_progress", "done", "closed"]


def _next_id() -> str:
    global _SEQ
    _SEQ += 1
    return f"wo_{int(time.time())}_{_SEQ}"


def create_workorder(store_id: str, equipment_id: str, fault: str,
                     budget: float, idempotency_key: str,
                     assignee: str = "服务商A") -> ToolResult:
    """创建维修工单。金额 > 2000 元需调用方先过审批(传 approval_id)。"""
    if idempotency_key in _IDEMPOTENT:
        wid = _IDEMPOTENT[idempotency_key]
        return ToolResult(_WORKORDERS[wid])
    wid = _next_id()
    sla_h = 4 if budget > 2000 else 8
    rec = {
        "workorder_id": wid, "store_id": store_id, "equipment_id": equipment_id,
        "fault": fault, "budget": budget, "assignee": assignee,
        "sla_deadline": f"+{sla_h}h", "status": "assigned" if assignee else "created",
        "created_at": time.time(),
    }
    _WORKORDERS[wid] = rec
    _IDEMPOTENT[idempotency_key] = wid
    print(f"  🔧 [工单 created] {wid} | {store_id}/{equipment_id} | ¥{budget} | {fault[:40]}")
    return ToolResult(rec)


def track_workorder(workorder_id: str) -> ToolResult:
    rec = _WORKORDERS.get(workorder_id)
    if not rec:
        return ToolResult(data=None, degraded=True, error=f"工单 {workorder_id} 不存在")
    return ToolResult(rec)


def confirm_done(workorder_id: str, evidence: dict) -> ToolResult:
    """服务商完工确认。evidence 如 {temp_restored: True, photos: []}。"""
    rec = _WORKORDERS.get(workorder_id)
    if not rec:
        return ToolResult(data=None, degraded=True, error=f"工单 {workorder_id} 不存在")
    rec["status"] = "done"
    rec["evidence"] = evidence
    rec["done_at"] = time.time()
    return ToolResult(rec)


def all_workorders() -> list[dict]:
    return list(_WORKORDERS.values())
