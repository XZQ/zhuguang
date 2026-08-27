"""mcp-approval:审批流工具。

契约:create_approval(subject, type, payload, approvers, timeout_min)
     / check_status(approval_id) / cancel(approval_id)
权限:审批人名单由总部配置,Agent 无权修改
降级:超时未批 → 返回 timeout,调用方按策略降级(如:仅通知不执行)
数据源:内存(demo 自动审批或模拟人工)
"""

from __future__ import annotations

import time
from typing import Literal

from ._csv_store import ToolResult

_APPROVALS: dict[str, dict] = {}
_SEQ = 0

ApprovalStatus = Literal["pending", "approved", "rejected", "timeout"]


def _next_id() -> str:
    global _SEQ
    _SEQ += 1
    return f"apr_{int(time.time())}_{_SEQ}"


def create_approval(
    subject: str,
    type: str,
    payload: dict,
    approvers: list[str],
    timeout_min: int = 60,
    auto_decide: str | None = "approved",
) -> ToolResult:
    """创建审批单。

    安全边界:审批人名单外部配置,Agent 只能创建不能改。
    demo 默认 auto_decide='approved' 模拟人工即时通过(真实环境由审批人操作)。
    type: price_change | workorder | restock | transfer 等。
    """
    aid = _next_id()
    status: ApprovalStatus = auto_decide if auto_decide else "pending"  # type: ignore
    rec = {
        "approval_id": aid,
        "subject": subject,
        "type": type,
        "payload": payload,
        "approvers": approvers,
        "timeout_min": timeout_min,
        "status": status,
        "created_at": time.time(),
        "decided_at": time.time() if auto_decide else None,
    }
    _APPROVALS[aid] = rec
    print(f"  🔖 [审批 {status}] {type}: {subject}")
    return ToolResult({"approval_id": aid, "status": status})


def check_status(approval_id: str) -> ToolResult:
    """查询审批状态。"""
    rec = _APPROVALS.get(approval_id)
    if not rec:
        return ToolResult(data=None, degraded=True, error=f"审批单 {approval_id} 不存在")
    return ToolResult({"approval_id": approval_id, "status": rec["status"]})


def cancel_approval(approval_id: str) -> ToolResult:
    """撤销审批单(如处置被回滚)。"""
    rec = _APPROVALS.get(approval_id)
    if not rec:
        return ToolResult(data=None, degraded=True, error=f"审批单 {approval_id} 不存在")
    rec["status"] = "rejected"
    return ToolResult({"approval_id": approval_id, "status": "rejected"})


def all_approvals() -> list[dict]:
    return list(_APPROVALS.values())
