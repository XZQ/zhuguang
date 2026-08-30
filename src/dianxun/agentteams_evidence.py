"""Verifier for redacted evidence exported from a real AgentTeams runtime."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .validation import validate_json

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = _ROOT / "schemas" / "agentteams-run-evidence.v1.schema.json"
DEFAULT_CHECKSUM = _ROOT / "dist" / "dianxun-worker.zip.sha256"
DEFAULT_PROVENANCE = _ROOT / "dist" / "dianxun-worker.provenance.json"

_WORKERS = {"orchestrator", "sentry", "diagnoser", "executor", "auditor"}
_SKILLS = {
    ("sentry", "anomaly-detect"),
    ("diagnoser", "coldchain-risk-assess"),
    ("diagnoser", "rootcause-drilldown"),
    ("executor", "work-order-dispatch"),
    ("auditor", "outcome-verify"),
    ("auditor", "review-report"),
}
_PHASES = {"DETECT_CONTAIN", "DIAGNOSE_DECIDE", "EXECUTE", "VERIFY", "LEARN"}
_REQUIRED_DELEGATIONS = {
    ("manager", "orchestrator", "DETECT_CONTAIN"),
    ("orchestrator", "sentry", "DETECT_CONTAIN"),
    ("orchestrator", "diagnoser", "DIAGNOSE_DECIDE"),
    ("orchestrator", "executor", "EXECUTE"),
    ("orchestrator", "auditor", "VERIFY"),
    ("orchestrator", "auditor", "LEARN"),
}
_TOOL_WORKERS = {"sentry", "diagnoser", "executor", "auditor"}
_WORKER_TOOLS = {
    "sentry": {"query_device_context", "query_inventory_batches"},
    "diagnoser": {"query_device_context", "query_inventory_batches", "search_knowledge"},
    "executor": {
        "query_approval",
        "apply_sales_hold",
        "release_sales_hold",
        "apply_batch_disposition",
        "create_workorder",
        "create_approval",
    },
    "auditor": {
        "query_device_context",
        "query_inventory_batches",
        "query_sales_holds",
        "query_workorder",
        "query_approval",
        "create_knowledge_candidate",
    },
}
_BASE_BUSINESS_CHAIN = {"apply_sales_hold", "create_approval", "create_workorder"}
_STATE_CHANGING_TOOLS = {
    "apply_sales_hold",
    "release_sales_hold",
    "apply_batch_disposition",
    "create_workorder",
    "create_approval",
    "decide_approval",
    "record_manual_evidence",
    "create_knowledge_candidate",
    "review_knowledge_candidate",
}
_DENIED_KEYS = {
    "token",
    "secret",
    "password",
    "apikey",
    "gatewaykey",
    "authorization",
    "credential",
    "privatekey",
}
_SECRET_VALUE = re.compile(r"(?i)(?:bearer\s+\S{8,}|sk-[a-z0-9_-]{12,})")


def verify_agentteams_evidence(
    bundle: dict[str, Any],
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    checksum_path: Path = DEFAULT_CHECKSUM,
    provenance_path: Path = DEFAULT_PROVENANCE,
) -> dict[str, Any]:
    """Return an evidence gate report; never upgrades templates to observed proof."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_json(bundle, schema)
    errors.extend(_secret_errors(bundle))
    checks: dict[str, bool] = {}
    if errors:
        return {"passed": False, "checks": checks, "errors": sorted(set(errors))}

    expected_hash = checksum_path.read_text(encoding="ascii").split()[0]
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    expected_versions = {item["name"]: item["version"] for item in provenance["skills"]}
    checks["agentteams_version_pinned"] = bundle["agentteams_version"] == "v1.2.3"
    checks["package_hash_matches_repository"] = bundle["package_sha256"] == expected_hash

    resources = bundle["resources"]
    worker_names = {item["name"] for item in resources["workers"]}
    checks["all_resources_running"] = (
        resources["manager"]["name"] == "dianxun-manager"
        and resources["team"]["name"] == "dianxun-patrol-team"
        and resources["manager"]["status"] == "Running"
        and resources["team"]["status"] == "Running"
        and bool(resources["manager"]["evidence_ref"])
        and bool(resources["team"]["evidence_ref"])
        and worker_names == _WORKERS
        and all(
            item["status"] == "Running" and bool(item["evidence_ref"])
            for item in resources["workers"]
        )
    )

    loads = {(item["worker"], item["skill"]) for item in bundle["skill_loads"]}
    checks["runtime_skills_loaded"] = loads == _SKILLS and all(
        item["package_sha256"] == expected_hash
        and item["version"] == expected_versions.get(item["skill"])
        and bool(item["loaded_at"])
        for item in bundle["skill_loads"]
    )

    security = {item["check"]: item for item in bundle["security_checks"]}
    expected_security = {
        "missing_token": 401,
        "wrong_token": 401,
        "wrong_role": "FORBIDDEN",
        "authorized_actor_audited": True,
    }
    checks["security_negative_and_positive_cases"] = (
        len(bundle["security_checks"]) == len(expected_security)
        and set(security) == set(expected_security)
        and all(
            (
                name in security
                and security[name]["expected"] == expected
                and security[name]["observed"] == expected
                and bool(security[name]["evidence_ref"])
            )
            for name, expected in expected_security.items()
        )
    )

    branches = {run["branch"] for run in bundle["runs"]}
    checks["success_and_failure_branches"] = len(bundle["runs"]) == 2 and branches == {
        "success",
        "failure",
    }
    checks["run_correlation_ids_unique"] = (
        len({run["scenario_id"] for run in bundle["runs"]}) == len(bundle["runs"])
        and len({run["incident_id"] for run in bundle["runs"]}) == len(bundle["runs"])
        and len({run["trace_id"] for run in bundle["runs"]}) == len(bundle["runs"])
    )
    run_checks = []
    for run in bundle["runs"]:
        phases = {item["phase"] for item in run["handoffs"]}
        recipients = {item["to"] for item in run["handoffs"]}
        delegation_edges = {(item["from"], item["to"], item["phase"]) for item in run["handoffs"]}
        handoff_ids = [item["message_id"] for item in run["handoffs"]]
        handoff_evidence_complete = len(handoff_ids) == len(set(handoff_ids)) and all(
            item["message_id"] and item["at"] for item in run["handoffs"]
        )
        request_ids = [item["request_id"] for item in run["tool_calls"]]
        linked = all(
            item["incident_id"] == run["incident_id"]
            and item["trace_id"] == run["trace_id"]
            and item["request_id"]
            and (item["worker"], item["skill"]) in _SKILLS
            and bool(item["evidence_ref"])
            for item in run["tool_calls"]
        ) and len(request_ids) == len(set(request_ids))
        tool_workers = {item["worker"] for item in run["tool_calls"]}
        tool_names = {item["tool"] for item in run["tool_calls"]}
        tool_roles_authorized = all(
            item["tool"] in _WORKER_TOOLS.get(item["worker"], set()) for item in run["tool_calls"]
        )
        audited_state_changes = all(
            item["tool"] not in _STATE_CHANGING_TOOLS or bool(item.get("audit_ref"))
            for item in run["tool_calls"]
        )
        human_approval = (
            run["approval"]["status"] == "approved"
            and run["approval"]["actor_type"] == "human"
            and bool(run["approval"]["decision_id"])
            and bool(run["approval"]["evidence_ref"])
        )
        if run["branch"] == "success":
            business_chain = (
                _BASE_BUSINESS_CHAIN | {"release_sales_hold", "query_sales_holds"}
            ) <= tool_names
            outcome = (
                run["final_state"]["incident_status"] == "CLOSED"
                and run["final_state"]["work_status"] == "COMPLETED"
                and run["final_state"]["sales_hold_status"] == "released"
            )
        else:
            business_chain = (
                _BASE_BUSINESS_CHAIN | {"query_workorder"} <= tool_names
                and "release_sales_hold" not in tool_names
            )
            outcome = (
                run["final_state"]["incident_status"] in {"BLOCKED", "REOPENED", "CONTAINED"}
                and run["final_state"]["work_status"] in {"BLOCKED", "WAITING", "REOPENED"}
                and run["final_state"]["sales_hold_status"] == "active"
                and any(item["partial"] or not item["ok"] for item in run["tool_calls"])
            )
        run_checks.append(
            {
                "scenario_id": run["scenario_id"],
                "branch": run["branch"],
                "five_phases": phases == _PHASES,
                "delegation_roles": _WORKERS <= recipients,
                "delegation_topology": _REQUIRED_DELEGATIONS <= delegation_edges,
                "handoff_evidence_complete": handoff_evidence_complete,
                "correlation_complete": linked,
                "tool_role_coverage": _TOOL_WORKERS <= tool_workers,
                "tool_roles_authorized": tool_roles_authorized,
                "business_chain_complete": business_chain,
                "state_changes_audited": audited_state_changes,
                "human_approval": human_approval,
                "safe_outcome": outcome,
                "trace_artifact_redacted": (
                    run["trace_artifact"]["redacted"] is True and bool(run["trace_artifact"]["uri"])
                ),
                "trace_digest_non_placeholder": run["trace_artifact"]["sha256"] != "0" * 64,
            }
        )
    checks["runs_pass_runtime_gate"] = all(
        all(value for key, value in item.items() if key not in {"scenario_id", "branch"})
        for item in run_checks
    )

    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "checks": checks,
        "runs": run_checks,
        "errors": [f"failed check: {name}" for name in failed],
        "claim_boundary": (
            "A passing report validates the supplied redacted runtime evidence bundle; "
            "it does not create or substitute AgentTeams runtime evidence."
        ),
    }


def _secret_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", key.casefold())
            if normalized_key in _DENIED_KEYS:
                errors.append(f"{path}: forbidden secret-bearing field {key!r}")
            errors.extend(_secret_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_secret_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str) and _SECRET_VALUE.search(value):
        errors.append(f"{path}: credential-like value must be redacted")
    return errors
