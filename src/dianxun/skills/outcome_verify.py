"""P0 independent verification based on fresh MCP queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import trace
from ..domain import Verification, VerificationResult
from .contracts import enforce_output_contract

if TYPE_CHECKING:
    from ..domain import IncidentService
    from ..mcp.p0 import MCPService


@enforce_output_contract("outcome-verify")
def outcome_verify(
    *,
    incidents: IncidentService,
    service: MCPService,
    incident_id: str,
    policy: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    """Requery device, batches, holds, workorders and approvals as Auditor."""
    case = incidents.get(incident_id)
    with trace.span(
        "outcome-verify",
        "skill",
        trace_id,
        input={"incident_id": incident_id},
    ) as sp:
        responses = {
            "device": _query(
                service.query_device_context,
                trace_id,
                "query_device_context",
                device_id=case.affected_assets[0],
                store_id=case.store_id,
                incident_id=incident_id,
                actor="Auditor",
            ),
            "batches": _query(
                service.query_inventory_batches,
                trace_id,
                "query_inventory_batches",
                batch_ids=case.affected_batches,
                incident_id=incident_id,
                actor="Auditor",
            ),
            "sales_hold": _query(
                service.query_sales_holds,
                trace_id,
                "query_sales_holds",
                incident_id=incident_id,
                actor="Auditor",
            ),
            "workorder": _query(
                service.query_workorder,
                trace_id,
                "query_workorder",
                incident_id=incident_id,
                actor="Auditor",
            ),
            "approval": _query(
                service.query_approval,
                trace_id,
                "query_approval",
                incident_id=incident_id,
                actor="Auditor",
            ),
        }

        checks = _evaluate(case, responses, policy, service)
        for subject, check in checks.items():
            evidence_ids = _evidence_ids(responses.get(subject, {}))
            if subject == "release_guard":
                evidence_ids = sorted(
                    {
                        evidence_id
                        for response in responses.values()
                        for evidence_id in _evidence_ids(response)
                    }
                )
            verification = Verification(
                verification_id=f"{incident_id}:verify:{subject}",
                subject=subject,
                method="fresh_state_requery" if subject != "audit" else "audit_log_query",
                expected_condition=check["expected"],
                observed_value=check["observed"],
                evidence_ids=evidence_ids,
                result=(
                    VerificationResult.PASSED if check["passed"] else VerificationResult.FAILED
                ),
                verifier="Auditor",
                verified_at=service.store.now(),
            )
            incidents.record_verification(incident_id, verification)

        failed = [name for name, check in checks.items() if not check["passed"]]
        if not failed:
            result = "verified"
        elif failed == ["sales_hold"] and checks.get("release_guard", {}).get("passed"):
            result = "release_ready"
        elif checks["device"]["passed"] and not checks["batches"]["passed"]:
            result = "manual_review"
        else:
            result = "reopened"
        partial_tools = sorted(
            name
            for name, response in responses.items()
            if response.get("partial") or not response.get("ok")
        )
        evidence = [
            item
            for response in responses.values()
            if response.get("ok")
            for item in response["data"].get("evidence", [])
        ]
        refreshed = incidents.recompute(incident_id)
        output = {
            "incident_id": incident_id,
            "result": result,
            "checks": checks,
            "failed_conditions": failed,
            "evidence_refs": sorted(
                {
                    evidence_id
                    for response in responses.values()
                    for evidence_id in _evidence_ids(response)
                }
            ),
            "next_actions": _next_actions(result, failed),
            "partial_tools": partial_tools,
            "evidence": evidence,
            "incident_status": refreshed.incident_status.value,
        }
        sp.output = {
            "result": result,
            "failed_conditions": failed,
            "incident_status": refreshed.incident_status.value,
        }
        return output


def _query(call, trace_id: str, name: str, **kwargs: Any) -> dict[str, Any]:
    with trace.span(name, "mcp", trace_id, input=kwargs) as sp:
        response = call(**kwargs)
        sp.output = {
            "ok": response["ok"],
            "request_id": response["request_id"],
            "partial": response["partial"],
        }
        return response


def _evaluate(case, responses: dict[str, dict[str, Any]], policy: dict[str, Any], service) -> dict:
    recovery_samples = int(policy["temperature"]["device_recovery_samples"])
    maximum = float(policy["temperature"]["refrigerated_max_celsius"])
    device_rows = _rows(responses["device"], "devices")
    device = device_rows[0] if device_rows else {}
    readings = sorted(device.get("temperature_series", []), key=lambda item: item["observed_at"])
    trusted_readings = [
        item for item in readings if str(item.get("quality", "good")).lower() == "good"
    ]
    excluded_readings = [item for item in readings if item not in trusted_readings]
    latest = trusted_readings[-recovery_samples:]
    workorders = _rows(responses["workorder"], "workorders")
    device_passed = (
        len(latest) == recovery_samples
        and all(float(item["temp_c"]) <= maximum for item in latest)
        and device.get("health", {}).get("state") == "normal"
        and device.get("health", {}).get("compressor_state") == "running"
        and bool(workorders)
        and all(
            item.get("status") in {"done", "closed"} and item.get("completion_evidence")
            for item in workorders
        )
    )

    batches = _rows(responses["batches"], "batches")
    terminal = {"transferred", "released", "disposed"}
    batches_passed = bool(batches) and all(item.get("disposition") in terminal for item in batches)
    holds = _rows(responses["sales_hold"], "sales_holds")
    hold_by_batch = {item["batch_id"]: item for item in holds}
    holds_passed = bool(batches) and all(
        item["batch_id"] in hold_by_batch
        and (
            hold_by_batch[item["batch_id"]]["status"] == "released"
            if item["disposition"] == "released"
            else hold_by_batch[item["batch_id"]]["status"] == "active"
        )
        for item in batches
    )
    approvals = _rows(responses["approval"], "approvals")
    approved_actions = {item["action_id"] for item in approvals if item.get("status") == "approved"}
    required_approval_actions = {
        action.action_id for action in case.actions if action.approval_id is not None
    }
    approvals_passed = required_approval_actions <= approved_actions and all(
        item.get("status") == "approved" for item in approvals
    )
    audit_rows = service.store.list_audit_log(incident_id=case.incident_id)
    audit_passed = bool(audit_rows) and all(row.get("request_id") for row in audit_rows)
    checks = {
        "device": {
            "passed": device_passed,
            "expected": {
                "recovery_samples": recovery_samples,
                "max_c": maximum,
                "health": "normal",
                "workorder": "done_with_evidence",
            },
            "observed": {
                "device": device,
                "latest_samples": latest,
                "excluded_readings": excluded_readings,
                "workorders": workorders,
            },
        },
        "batches": {
            "passed": batches_passed,
            "expected": {"dispositions": sorted(terminal)},
            "observed": {"batches": batches},
        },
        "sales_hold": {
            "passed": holds_passed,
            "expected": {"terminal_batches_remain_held_unless_released": True},
            "observed": {"sales_holds": holds},
        },
        "approval": {
            "passed": approvals_passed,
            "expected": {
                "required_actions": sorted(required_approval_actions),
                "status": "approved",
            },
            "observed": {"approvals": approvals},
        },
        "audit": {
            "passed": audit_passed,
            "expected": {"minimum_entries": 1, "request_id_required": True},
            "observed": {"entry_count": len(audit_rows)},
        },
    }
    released_batches = [item for item in batches if item.get("disposition") == "released"]
    if released_batches:
        release_hold_states = {
            item["batch_id"]: hold_by_batch.get(item["batch_id"], {}).get("status")
            for item in released_batches
        }
        checks["release_guard"] = {
            "passed": (
                device_passed
                and batches_passed
                and approvals_passed
                and audit_passed
                and all(status in {"active", "released"} for status in release_hold_states.values())
            ),
            "expected": {
                "device_batches_approvals_audit": "passed",
                "released_batch_hold_state": ["active", "released"],
            },
            "observed": {"released_batch_holds": release_hold_states},
        }
    return checks


def _rows(response: dict[str, Any], key: str) -> list[dict[str, Any]]:
    if not response.get("ok"):
        return []
    return list(response["data"].get(key, []))


def _evidence_ids(response: dict[str, Any]) -> list[str]:
    if not response.get("ok"):
        return []
    return [item["evidence_id"] for item in response["data"].get("evidence", [])]


def _next_actions(result: str, failed: list[str]) -> list[str]:
    if result == "verified":
        return ["enter_learn"]
    if result == "release_ready":
        return ["request_release_approval", "executor_release_sales_hold", "verify_again"]
    if result == "manual_review":
        return ["keep_sales_hold", "request_batch_disposition_approval"]
    return ["keep_sales_hold", "re_diagnose", *[f"recheck_{item}" for item in failed]]
