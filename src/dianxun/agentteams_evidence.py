"""Verifier for redacted evidence exported from a real AgentTeams runtime."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .validation import validate_json

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = _ROOT / "schemas" / "agentteams-run-evidence.v1.schema.json"
DEFAULT_CHECKSUM = _ROOT / "dist" / "dianxun-worker.zip.sha256"
DEFAULT_PROVENANCE = _ROOT / "dist" / "dianxun-worker.provenance.json"
DEFAULT_FACTS = _ROOT / "config" / "project-facts.json"

_WORKERS = {"orchestrator", "sentry", "diagnoser", "executor", "auditor"}
_WORKER_ACTORS = {
    "sentry": "Sentry",
    "diagnoser": "Diagnoser",
    "executor": "Executor",
    "auditor": "Auditor",
}
_SKILLS = {
    ("sentry", "anomaly-detect"),
    ("diagnoser", "coldchain-risk-assess"),
    ("diagnoser", "rootcause-drilldown"),
    ("executor", "work-order-dispatch"),
    ("auditor", "outcome-verify"),
    ("auditor", "review-report"),
}
_PHASE_ORDER = ("DETECT_CONTAIN", "DIAGNOSE_DECIDE", "EXECUTE", "VERIFY", "LEARN")
_PHASES = set(_PHASE_ORDER)
_PHASE_WORKERS = {
    "DETECT_CONTAIN": "sentry",
    "DIAGNOSE_DECIDE": "diagnoser",
    "EXECUTE": "executor",
    "VERIFY": "auditor",
    "LEARN": "auditor",
}
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
_BASE_BUSINESS_CHAIN = {
    "apply_sales_hold",
    "apply_batch_disposition",
    "create_approval",
    "create_workorder",
}
_AUDITOR_PRE_RELEASE_TOOLS = {
    "query_device_context",
    "query_inventory_batches",
    "query_sales_holds",
    "query_workorder",
    "query_approval",
}
_AUDITOR_POST_RELEASE_TOOLS = {
    "query_device_context",
    "query_inventory_batches",
    "query_sales_holds",
}
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
    facts = json.loads(DEFAULT_FACTS.read_text(encoding="utf-8"))
    expected_source_commit = facts["implementation"]["m3_repository_artifacts"][
        "worker_package_source_commit"
    ]
    expected_versions = {item["name"]: item["version"] for item in provenance["skills"]}
    expected_digests = {item["name"]: item["sha256"] for item in provenance["skills"]}
    captured_at = _parse_timestamp(bundle["captured_at"])
    checks["agentteams_version_pinned"] = bundle["agentteams_version"] == "v1.2.3"
    checks["package_source_commit_matches_repository"] = (
        bundle["package_source_commit"] == expected_source_commit
    )
    checks["package_hash_matches_repository"] = bundle["package_sha256"] == expected_hash

    runtime = bundle["runtime"]
    checks["runtime_disclosed"] = (
        runtime["manager_runtime"] == "qwenpaw"
        and runtime["worker_runtime"] == "qwenpaw"
        and runtime["model"] == "qwen3.5-plus"
        and bool(runtime["provider"])
        and bool(runtime["evidence_ref"])
    )

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
        and item["skill_digest"] == expected_digests.get(item["skill"])
        and _timestamp_not_after(item["loaded_at"], captured_at)
        and bool(item["evidence_ref"])
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
                and _timestamp_not_after(security[name]["at"], captured_at)
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
        and len({run["project_id"] for run in bundle["runs"]}) == len(bundle["runs"])
        and len({run["incident_id"] for run in bundle["runs"]}) == len(bundle["runs"])
        and len({run["trace_id"] for run in bundle["runs"]}) == len(bundle["runs"])
    )
    checks["coordination_tenant_consistent"] = (
        len({run["coordination"]["tenant_id"] for run in bundle["runs"]}) == 1
    )
    run_checks = []
    for run in bundle["runs"]:
        phases = {item["phase"] for item in run["handoffs"]}
        recipients = {item["to"] for item in run["handoffs"]}
        delegation_edges = {(item["from"], item["to"], item["phase"]) for item in run["handoffs"]}
        handoff_ids = [item["message_id"] for item in run["handoffs"]]
        task_ids = [item["task_id"] for item in run["handoffs"]]
        handoff_evidence_complete = (
            len(handoff_ids) == len(set(handoff_ids))
            and len(task_ids) == len(set(task_ids))
            and all(
                item["message_id"]
                and item["task_id"]
                and item["evidence_ref"]
                and _timestamp_not_after(item["at"], captured_at)
                for item in run["handoffs"]
            )
        )
        handoff_timeline_ordered = _timeline_is_ordered(
            [item["at"] for item in run["handoffs"]], captured_at
        )
        request_ids = [item["request_id"] for item in run["tool_calls"]]
        linked = all(
            item["incident_id"] == run["incident_id"]
            and item["trace_id"] == run["trace_id"]
            and item["request_id"]
            and (item["worker"], item["skill"]) in _SKILLS
            and item["skill_version"] == expected_versions.get(item["skill"])
            and item["skill_digest"] == expected_digests.get(item["skill"])
            and _timestamp_not_after(item["at"], captured_at)
            and bool(item["evidence_ref"])
            for item in run["tool_calls"]
        ) and len(request_ids) == len(set(request_ids))
        tool_timeline_ordered = _timeline_is_ordered(
            [item["at"] for item in run["tool_calls"]], captured_at
        )
        tool_workers = {item["worker"] for item in run["tool_calls"]}
        tool_names = {item["tool"] for item in run["tool_calls"]}
        tool_roles_authorized = all(
            item["tool"] in _WORKER_TOOLS.get(item["worker"], set()) for item in run["tool_calls"]
        )
        mcp_actor_identity_bound = all(
            item["authenticated_actor"] == _WORKER_ACTORS.get(item["worker"])
            and item["authentication_mode"] == "actor_bound"
            and bool(item["auth_evidence_ref"])
            for item in run["tool_calls"]
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
            and _timestamp_not_after(run["approval"]["at"], captured_at)
        )
        coordination_integrity = _coordination_integrity(run["coordination"], captured_at)
        approval_at = _parse_timestamp(run["approval"]["at"])
        approval_request_times = [
            _parse_timestamp(item["at"])
            for item in run["tool_calls"]
            if item["tool"] == "create_approval"
        ]
        release_positions = [
            index
            for index, item in enumerate(run["tool_calls"])
            if item["tool"] == "release_sales_hold"
        ]
        if run["branch"] == "success":
            business_chain = (
                _BASE_BUSINESS_CHAIN | {"release_sales_hold", "query_sales_holds"}
            ) <= tool_names
            independent_verification = False
            approval_timeline_valid = False
            if len(release_positions) == 1:
                release_index = release_positions[0]
                release_at = _parse_timestamp(run["tool_calls"][release_index]["at"])
                before_release = {
                    item["tool"]
                    for item in run["tool_calls"][:release_index]
                    if item["worker"] == "auditor"
                }
                after_release = {
                    item["tool"]
                    for item in run["tool_calls"][release_index + 1 :]
                    if item["worker"] == "auditor"
                }
                independent_verification = (
                    _AUDITOR_PRE_RELEASE_TOOLS <= before_release
                    and _AUDITOR_POST_RELEASE_TOOLS <= after_release
                )
                approval_timeline_valid = (
                    len(approval_request_times) == 1
                    and approval_at is not None
                    and approval_request_times[0] is not None
                    and release_at is not None
                    and approval_request_times[0] <= approval_at < release_at
                )
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
            auditor_tools = {
                item["tool"] for item in run["tool_calls"] if item["worker"] == "auditor"
            }
            independent_verification = _AUDITOR_PRE_RELEASE_TOOLS <= auditor_tools
            approval_timeline_valid = (
                len(approval_request_times) == 1
                and approval_at is not None
                and approval_request_times[0] is not None
                and approval_request_times[0] <= approval_at
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
                "platform_correlation": bool(run["project_id"] and run["source_room_id"]),
                "five_phases": phases == _PHASES,
                "delegation_roles": _WORKERS <= recipients,
                "delegation_topology": _REQUIRED_DELEGATIONS <= delegation_edges,
                "handoff_evidence_complete": handoff_evidence_complete,
                "handoff_timeline_ordered": handoff_timeline_ordered,
                "correlation_complete": linked,
                "tool_timeline_ordered": tool_timeline_ordered,
                "tool_role_coverage": _TOOL_WORKERS <= tool_workers,
                "tool_roles_authorized": tool_roles_authorized,
                "mcp_actor_identity_bound": mcp_actor_identity_bound,
                "business_chain_complete": business_chain,
                "independent_verification_chain": independent_verification,
                "state_changes_audited": audited_state_changes,
                "human_approval": human_approval,
                "approval_timeline_valid": approval_timeline_valid,
                "coordination_integrity": coordination_integrity,
                "safe_outcome": outcome,
                "final_state_evidenced": _final_state_is_evidenced(run, captured_at),
                "trace_artifact_redacted": (
                    run["trace_artifact"]["redacted"] is True and bool(run["trace_artifact"]["uri"])
                ),
                "trace_digest_non_placeholder": run["trace_artifact"]["sha256"] != "0" * 64,
            }
        )
    checks["timeout_reassignment_observed"] = any(
        any(item.get("predecessor_assignment_id") for item in run["coordination"]["assignments"])
        for run in bundle["runs"]
    )
    checks["checkpoint_resume_observed"] = any(
        run["coordination"]["resumed_from_checkpoint"] for run in bundle["runs"]
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


def _coordination_integrity(coordination: dict[str, Any], captured_at: datetime | None) -> bool:
    assignments = coordination["assignments"]
    checkpoints = coordination["checkpoints"]
    assignment_by_id = {item["assignment_id"]: item for item in assignments}
    if len(assignment_by_id) != len(assignments):
        return False
    checkpoint_by_phase = {item["phase"]: item for item in checkpoints}
    if set(checkpoint_by_phase) != _PHASES or len(checkpoint_by_phase) != len(checkpoints):
        return False
    if [item["phase"] for item in checkpoints] != list(_PHASE_ORDER):
        return False
    context_version = coordination["context_version"]
    checkpoint_versions = [item["context_version"] for item in checkpoints]
    if (
        checkpoint_versions != sorted(checkpoint_versions)
        or len(checkpoint_versions) != len(set(checkpoint_versions))
        or any(version > context_version for version in checkpoint_versions)
    ):
        return False
    expires_at = _parse_timestamp(coordination["expires_at"])
    if expires_at is None:
        return False
    resumed = coordination["resumed_from_checkpoint"]
    resume_ref = coordination["resume_evidence_ref"]
    if (resumed and not resume_ref) or (not resumed and resume_ref is not None):
        return False

    successor_counts: dict[str, int] = {}
    for assignment in assignments:
        assigned_at = _parse_timestamp(assignment["assigned_at"])
        lease_expires_at = _parse_timestamp(assignment["lease_expires_at"])
        heartbeat_at = _parse_timestamp(assignment["heartbeat_at"])
        if (
            assignment["phase"] not in _PHASES
            or assignment["worker"] != _PHASE_WORKERS[assignment["phase"]]
            or assigned_at is None
            or lease_expires_at is None
            or heartbeat_at is None
            or assigned_at > heartbeat_at
            or heartbeat_at > lease_expires_at
            or (captured_at is not None and heartbeat_at > captured_at)
        ):
            return False
        predecessor_id = assignment.get("predecessor_assignment_id")
        if predecessor_id is None:
            if assignment["attempt"] != 1:
                return False
            continue
        predecessor = assignment_by_id.get(predecessor_id)
        if (
            predecessor is None
            or predecessor["status"] != "expired"
            or predecessor["phase"] != assignment["phase"]
            or assignment["attempt"] != predecessor["attempt"] + 1
            or assigned_at <= _parse_timestamp(predecessor["lease_expires_at"])
        ):
            return False
        successor_counts[predecessor_id] = successor_counts.get(predecessor_id, 0) + 1
    expired_ids = {
        assignment["assignment_id"]
        for assignment in assignments
        if assignment["status"] == "expired"
    }
    if any(successor_counts.get(assignment_id) != 1 for assignment_id in expired_ids):
        return False

    initial_counts = {
        phase: sum(
            assignment["phase"] == phase and assignment.get("predecessor_assignment_id") is None
            for assignment in assignments
        )
        for phase in _PHASE_ORDER
    }
    if any(count != 1 for count in initial_counts.values()):
        return False

    for phase, checkpoint in checkpoint_by_phase.items():
        assignment = assignment_by_id.get(checkpoint["assignment_id"])
        checkpoint_at = _parse_timestamp(checkpoint["at"])
        assigned_at = _parse_timestamp(assignment["assigned_at"]) if assignment else None
        heartbeat_at = _parse_timestamp(assignment["heartbeat_at"]) if assignment else None
        lease_expires_at = _parse_timestamp(assignment["lease_expires_at"]) if assignment else None
        if (
            assignment is None
            or assignment["phase"] != phase
            or assignment["status"] != "succeeded"
            or not checkpoint["evidence_refs"]
            or checkpoint_at is None
            or assigned_at is None
            or heartbeat_at is None
            or lease_expires_at is None
            or checkpoint_at < heartbeat_at
            or checkpoint_at > lease_expires_at
            or checkpoint_at > expires_at
            or (captured_at is not None and checkpoint_at > captured_at)
        ):
            return False
    checkpoint_times = [_parse_timestamp(item["at"]) for item in checkpoints]
    if checkpoint_times != sorted(checkpoint_times):
        return False
    if {
        assignment["assignment_id"]
        for assignment in assignments
        if assignment["status"] == "succeeded"
    } != {checkpoint["assignment_id"] for checkpoint in checkpoints}:
        return False
    return True


def _is_timestamp(value: str) -> bool:
    return _parse_timestamp(value) is not None


def _timestamp_not_after(value: str, upper_bound: datetime | None) -> bool:
    parsed = _parse_timestamp(value)
    return parsed is not None and (upper_bound is None or parsed <= upper_bound)


def _timeline_is_ordered(values: list[str], upper_bound: datetime | None) -> bool:
    parsed = [_parse_timestamp(value) for value in values]
    return (
        all(item is not None for item in parsed)
        and parsed == sorted(parsed)
        and (upper_bound is None or not parsed or parsed[-1] <= upper_bound)
    )


def _final_state_is_evidenced(run: dict[str, Any], captured_at: datetime | None) -> bool:
    final_state = run["final_state"]
    observed_at = _parse_timestamp(final_state["observed_at"])
    event_times = [
        *(_parse_timestamp(item["at"]) for item in run["tool_calls"]),
        *(_parse_timestamp(item["at"]) for item in run["coordination"]["checkpoints"]),
    ]
    return (
        bool(final_state["evidence_ref"])
        and observed_at is not None
        and all(item is not None for item in event_times)
        and (not event_times or observed_at >= max(event_times))
        and (captured_at is None or observed_at <= captured_at)
    )


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


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
