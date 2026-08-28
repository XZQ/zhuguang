"""S6. work-order-dispatch 工单派发与跟踪。

九要素（详见 skills/work-order-dispatch/SKILL.md）：
  用途    设备/设施类处置生成工单,派发维修服务商,跟踪状态与完成验证
  输入    store_id, equipment_id, fault_summary, severity, budget_estimate
  输出    WorkOrder{id, assignee, sla_deadline, status, evidence_photos}
  安全    工单信息仅限本店+总部域;付款环节绝不由 Agent 直接执行(只生成待付款单)
  失败    服务商拒单→转派第二顺位+通知总控;超SLA→升级总部;审批超时→降级"仅通知店长"
  协同    处置 Executor 执行工具之一;完成后稽核 Auditor 触发 IoT 核验闭环

被谁调用:处置 Executor Agent
触发:诊断确认设备类根因后;金额>2000元需先过审批
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import mcp, trace

if TYPE_CHECKING:
    from ..mcp.p0 import MCPService


def work_order_dispatch(
    store_id: str,
    equipment_id: str,
    fault_summary: str,
    severity: str,
    budget_estimate: float,
    approval_id: str | None = None,
    trace_id: str | None = None,
) -> dict:
    """生成并派发维修工单。

    金额 > 2000 元:调用方须先取得 approval_id(经 mcp-approval 审批)。
    """
    tid = trace_id or trace.new_trace_id()
    with trace.span(
        "work-order-dispatch",
        "skill",
        tid,
        input={"store_id": store_id, "equipment": equipment_id, "budget": budget_estimate},
    ) as sp:
        # 安全边界:高额未审批 → 拒绝派发,要求先审批
        if budget_estimate > 2000 and not approval_id:
            sp.output = {"blocked": True, "reason": "需审批"}
            return {
                "blocked": True,
                "reason": "金额>2000元,需先经审批(approval_id)",
                "next_action": "调用 mcp-approval.create_approval 后重试",
            }

        # 幂等 key:用 trace+store+equipment 组合
        idem = f"{tid}:{store_id}:{equipment_id}"
        res = mcp.create_workorder(
            store_id=store_id,
            equipment_id=equipment_id,
            fault=fault_summary,
            budget=budget_estimate,
            idempotency_key=idem,
        )
        if res["degraded"]:
            sp.output = {"degraded": True}
            return {"degraded": True, "error": res["error"]}

        wo = res["rows"][0] if res["rows"] and isinstance(res["rows"][0], dict) else res["rows"]
        # 通知店长 + 服务商
        mcp.send_notice(
            "dingtalk_ops",
            "workorder_dispatched",
            {
                "title": f"维修工单 {wo['workorder_id']} 已派发",
                "store": store_id,
                "equipment": equipment_id,
                "budget": budget_estimate,
                "sla": wo.get("sla_deadline"),
                "approval": approval_id,
            },
        )
        result = {
            **wo,
            "approval_id": approval_id,
            "dispatched": True,
            "note": "工单已派发服务商并通知店长;付款单待服务商完工后人工处理",
        }
        sp.output = {"workorder_id": wo["workorder_id"], "status": wo["status"]}
        return result


def dispatch_stateful_workorder(
    *,
    service: MCPService,
    incident_id: str,
    action_id: str,
    store_id: str,
    device_id: str,
    fault: str,
    budget: float,
    approval_id: str | None,
    idempotency_key: str,
    trace_id: str,
) -> dict[str, Any]:
    """Dispatch through the stateful MCP boundary after rechecking approval."""
    with trace.span(
        "work-order-dispatch",
        "skill",
        trace_id,
        input={"incident_id": incident_id, "action_id": action_id, "budget": budget},
    ) as sp:
        if approval_id:
            approval = service.query_approval(
                approval_id=approval_id,
                action_id=action_id,
                incident_id=incident_id,
                actor="Executor",
            )
            rows = approval["data"]["approvals"] if approval["ok"] else []
            if not rows or rows[0]["status"] != "approved":
                result = {
                    "ok": False,
                    "waiting": True,
                    "approval": rows[0] if rows else None,
                    "error": approval["error"] if not approval["ok"] else None,
                    "compensation": "keep_sales_hold_and_escalate",
                }
                sp.output = result
                return result
        with trace.span(
            "create_workorder",
            "mcp",
            trace_id,
            input={"incident_id": incident_id, "action_id": action_id},
        ) as tool_span:
            response = service.create_workorder(
                incident_id=incident_id,
                action_id=action_id,
                store_id=store_id,
                device_id=device_id,
                fault=fault,
                budget=budget,
                approval_id=approval_id,
                idempotency_key=idempotency_key,
                actor="Executor",
            )
            tool_span.output = {
                "ok": response["ok"],
                "request_id": response["request_id"],
                "audit_ref": response["audit_ref"],
            }
        result = {
            "ok": response["ok"],
            "waiting": False,
            "data": response["data"],
            "error": response["error"],
            "request_id": response["request_id"],
            "audit_ref": response["audit_ref"],
            "compensation": "cancel_or_reassign_workorder",
        }
        sp.output = {"ok": result["ok"], "workorder": result.get("data")}
        return result
