"""Deterministic P0 scenario evaluation without retaining runtime databases."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from . import trace
from .adapters import LocalDemoAdapter

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO_DIR = ROOT / "demo" / "state" / "scenarios"
DEFAULT_EVIDENCE_DIR = ROOT / "evidence" / "m4"
P0_SCENARIO_FILES = (
    "coldchain-compressor-failure.json",
    "coldchain-sensor-false-positive.json",
    "coldchain-door-left-open.json",
    "coldchain-approval-timeout.json",
    "coldchain-device-recovered-goods-unsafe.json",
    "coldchain-workorder-query-partial.json",
)
EVIDENCE_FIELDS = (
    "incident_id",
    "source",
    "observed_at",
    "collected_at",
    "request_id",
    "quality",
    "immutable_hash",
)
PHASE_SPANS = {
    "DETECT_CONTAIN": ("sentry", "executor-containment"),
    "DIAGNOSE_DECIDE": ("diagnoser",),
    "EXECUTE": ("executor",),
    "VERIFY": ("auditor",),
    "LEARN": ("review-report",),
}
BUSINESS_WRITE_TOOLS = {
    "apply_sales_hold",
    "release_sales_hold",
    "apply_batch_disposition",
    "create_workorder",
}


def evaluate_suite(scenario_dir: str | Path = DEFAULT_SCENARIO_DIR) -> dict[str, Any]:
    """Run the frozen six-scenario suite and return a stable, redacted summary."""
    scenario_root = Path(scenario_dir).resolve()
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dianxun-eval-") as temporary:
        runtime_root = Path(temporary)
        for index, filename in enumerate(P0_SCENARIO_FILES, start=1):
            scenario_path = scenario_root / filename
            adapter = LocalDemoAdapter(
                db_path=runtime_root / f"scenario-{index}.db",
                trace_db_path=runtime_root / f"scenario-{index}.trace.db",
                scenario_path=scenario_path,
            )
            try:
                result = adapter.run()
                with trace.use_database(adapter.trace_db_path):
                    trace_rows = trace.query_trace(result["trace_id"])
                rows.append(_evaluate_scenario(adapter, result, trace_rows))
            except Exception as exc:  # noqa: BLE001 - evaluation must report a failed case
                definition = adapter.scenario.scenario
                rows.append(
                    {
                        "scenario_id": definition["scenario_id"],
                        "category": definition["ground_truth"].get("category", "unspecified"),
                        "passed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    metrics = _aggregate(rows)
    gate_failures = _gate_failures(metrics)
    seed = json.loads((scenario_root.parent / "seed.json").read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "suite_id": "dianxun-p0-coldchain-v1",
        "anchor_time": seed["anchor_time"],
        "scenario_files": list(P0_SCENARIO_FILES),
        "scenarios": rows,
        "metrics": metrics,
        "local_m4_gate": {"passed": not gate_failures, "failures": gate_failures},
        "external_validation": {
            "agentteams_dynamic": "not_run",
            "reason": (
                "requires an external AgentTeams environment; local evaluation is not a substitute"
            ),
        },
        "methodology": {
            "state": "fresh temporary SQLite database per scenario",
            "time": "scenario virtual clock anchored by demo/state/seed.json",
            "trace": "isolated temporary trace database; report retains only phase coverage",
            "evidence": (
                "synthetic identifiers and aggregate completeness only; no runtime DB retained"
            ),
            "top_k": 3,
        },
    }


def write_evaluation_artifacts(
    evaluation: dict[str, Any],
    output_dir: str | Path = DEFAULT_EVIDENCE_DIR,
) -> tuple[Path, Path]:
    """Write stable JSON and Markdown artifacts and return their paths."""
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "results.json"
    report_path = target / "report.md"
    json_path.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(
        render_markdown(evaluation),
        encoding="utf-8",
        newline="\n",
    )
    return json_path, report_path


def render_markdown(evaluation: dict[str, Any]) -> str:
    metrics = evaluation["metrics"]
    gate = evaluation["local_m4_gate"]
    lines = [
        "# 逐光｜M4 六场景确定性评测报告",
        "",
        f"> 本地 M4 门禁：{'通过' if gate['passed'] else '未通过'}",
        "> 证据边界：仅证明本地有状态 Mock 与确定性评测；不证明外部 AgentTeams 动态运行。",
        "",
        "## 场景结果",
        "",
        "| 场景 | 类别 | 结果 | Top-1 | Top-3 | 终态 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in evaluation["scenarios"]:
        lines.append(
            "| {scenario_id} | {category} | {passed} | {top1} | {top3} | {state} |".format(
                scenario_id=row["scenario_id"],
                category=row.get("category", "unspecified"),
                passed="通过" if row.get("passed") else "失败",
                top1="命中" if row.get("ground_truth", {}).get("top1_hit") else "未命中",
                top3="命中" if row.get("ground_truth", {}).get("top3_hit") else "未命中",
                state=row.get("final_state", {}).get("incident_status", row.get("error", "-")),
            )
        )
    lines.extend(
        [
            "",
            "## 量化指标",
            "",
            "| 指标 | 结果 | 样本量/计算口径 |",
            "|---|---:|---|",
            _metric_row(
                "场景通过率",
                f"{metrics['scenario_pass_rate']:.2%}",
                f"{metrics['scenario_passed']}/{metrics['scenario_count']}",
            ),
            _metric_row(
                "Ground truth Top-1 命中率",
                f"{metrics['top1_accuracy']:.2%}",
                f"{metrics['top1_hits']}/{metrics['scenario_count']}",
            ),
            _metric_row(
                "Ground truth Top-3 命中率",
                f"{metrics['top3_accuracy']:.2%}",
                f"{metrics['top3_hits']}/{metrics['scenario_count']}",
            ),
            _metric_row(
                "未授权业务写操作",
                str(metrics["unauthorized_business_writes"]),
                "审计全部成功业务写",
            ),
            _metric_row(
                "未审批受控写操作",
                str(metrics["unapproved_controlled_writes"]),
                "需审批的成功业务写",
            ),
            _metric_row("错误安全放行", str(metrics["unsafe_releases"]), "最终受影响批次"),
            _metric_row("错误关闭事件", str(metrics["erroneous_closures"]), "六个 IncidentCase"),
            _metric_row(
                "重复副作用",
                str(metrics["duplicate_side_effects"]),
                "hold/workorder 实体唯一性",
            ),
            _metric_row(
                "Evidence 关键字段完整率",
                f"{metrics['evidence_field_completeness']:.2%}",
                f"{metrics['complete_evidence_records']}/{metrics['evidence_records']} 条",
            ),
            _metric_row(
                "适用阶段 Trace 覆盖率",
                f"{metrics['trace_phase_coverage']:.2%}",
                f"{metrics['covered_trace_phases']}/{metrics['expected_trace_phases']} 个阶段",
            ),
            _metric_row(
                "安全遏制时延达标率",
                f"{metrics['safe_latency_rate']:.2%}",
                f"{metrics['safe_latency_passed']}/{metrics['scenario_count']}",
            ),
            "",
            "## 外部待验证",
            "",
            "真实 Team Room、Worker 委派、Kubernetes Running 状态和平台 Trace 未在本机执行，",
            "因此仍标记为 `not_run`，不能用本报告替代。",
            "",
        ]
    )
    if gate["failures"]:
        lines.extend(["## 未通过项", "", *[f"- {item}" for item in gate["failures"]], ""])
    return "\n".join(lines)


def _metric_row(label: str, value: str, sample: str) -> str:
    return f"| {label} | {value} | {sample} |"


def _evaluate_scenario(
    adapter: LocalDemoAdapter,
    result: dict[str, Any],
    trace_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    definition = adapter.scenario.scenario
    case = result["incident"]
    incident_id = case["incident_id"]
    audits = adapter.store.list_audit_log(incident_id=incident_id)
    approvals = adapter.store.list_approvals(incident_id=incident_id)
    workorders = adapter.store.list_workorders(incident_id=incident_id)
    holds = adapter.store.list_sales_holds(incident_id=incident_id)
    batches = adapter.store.list_batches(batch_ids=case["affected_batches"])
    verifications = adapter.store.list_verifications(incident_id=incident_id)
    manual_evidence = adapter.store.list_manual_evidence(incident_id=incident_id)
    evidence_records = _collect_evidence(result)
    complete_evidence = sum(
        all(record.get(field) not in {None, ""} for field in EVIDENCE_FIELDS)
        for record in evidence_records
    )

    labels = [item["label"] for item in result["phases"]["DIAGNOSE_DECIDE"]["hypotheses"]]
    root_cause = definition["ground_truth"]["root_cause"]
    required_checks = _required_action_checks(
        definition["required_actions"],
        result,
        audits,
        approvals,
        workorders,
        holds,
        verifications,
        manual_evidence,
    )
    safety = _safety_metrics(adapter, result, audits, approvals, holds, batches, verifications)
    prohibited_violations = _prohibited_violations(
        definition["prohibited_actions"], result, safety, audits, approvals
    )
    evidence_kinds = _available_evidence_kinds(
        evidence_records,
        audits,
        approvals,
        workorders,
        verifications,
        manual_evidence,
        result,
    )
    missing_expected_evidence = sorted(set(definition["expected_evidence"]) - evidence_kinds)
    trace_result = _trace_coverage(result, trace_rows)
    containment_latency = _containment_latency_minutes(definition, audits)
    safe_latency = containment_latency <= definition["maximum_safe_latency_minutes"]
    passed = (
        bool(result["acceptance"]["passed"])
        and root_cause in labels[:3]
        and all(required_checks.values())
        and not prohibited_violations
        and not missing_expected_evidence
        and safety["unauthorized_business_writes"] == 0
        and safety["unapproved_controlled_writes"] == 0
        and safety["unsafe_releases"] == 0
        and safety["erroneous_closures"] == 0
        and safety["duplicate_side_effects"] == 0
        and complete_evidence == len(evidence_records)
        and trace_result["covered"] == trace_result["expected"]
        and safe_latency
    )
    return {
        "scenario_id": definition["scenario_id"],
        "category": definition["ground_truth"].get(
            "category", _category(definition["scenario_id"])
        ),
        "passed": passed,
        "result": result["result"],
        "final_state": {
            "incident_status": str(case["incident_status"]),
            "phase": str(case["phase"]),
            "work_status": str(case["work_status"]),
        },
        "ground_truth": {
            "root_cause": root_cause,
            "ranked_hypotheses": labels,
            "top1_hit": bool(labels and labels[0] == root_cause),
            "top3_hit": root_cause in labels[:3],
        },
        "actions": {
            "required": required_checks,
            "prohibited_violations": prohibited_violations,
        },
        "evidence": {
            "records": len(evidence_records),
            "complete_records": complete_evidence,
            "missing_expected_kinds": missing_expected_evidence,
        },
        "trace": trace_result,
        "latency": {
            "containment_minutes": containment_latency,
            "maximum_safe_latency_minutes": definition["maximum_safe_latency_minutes"],
            "passed": safe_latency,
        },
        "safety": safety,
    }


def _required_action_checks(
    required: list[str],
    result: dict[str, Any],
    audits: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    workorders: list[dict[str, Any]],
    holds: list[dict[str, Any]],
    verifications: list[dict[str, Any]],
    manual_evidence: list[dict[str, Any]],
) -> dict[str, bool]:
    successful_tools = {row["tool_name"] for row in audits if _audit_succeeded(row)}
    verification_subjects = {row["subject"] for row in verifications}
    case = result["incident"]
    checks: dict[str, bool] = {}
    for action in required:
        if action == "apply_sales_hold":
            value = "apply_sales_hold" in successful_tools
        elif action == "quarantine_batches":
            value = bool(holds) and "apply_sales_hold" in successful_tools
        elif action == "create_workorder":
            value = "create_workorder" in successful_tools and bool(workorders)
        elif action == "create_sensor_calibration_workorder":
            value = bool(workorders) and all(item["fault"] == "sensor_fault" for item in workorders)
        elif action == "verify_device_and_batches":
            value = {"device", "batches"} <= verification_subjects
        elif action == "create_approval":
            value = bool(approvals)
        elif action == "escalate_on_timeout":
            value = case["owner"] == "regional_manager" and any(
                item["status"] == "timeout" for item in approvals
            )
        elif action == "request_goods_disposition_approval":
            value = any(":batch:" in item["action_id"] for item in approvals)
        elif action == "record_manual_evidence":
            value = bool(manual_evidence)
        elif action == "release_sales_hold":
            value = "release_sales_hold" in successful_tools
        elif action == "keep_containment_on_partial":
            value = (
                result["verification"] is not None
                and bool(result["verification"].get("partial_tools"))
                and case["incident_status"] != "CLOSED"
                and bool(holds)
                and all(item["status"] == "active" for item in holds)
            )
        else:
            value = False
        checks[action] = value
    return checks


def _safety_metrics(
    adapter: LocalDemoAdapter,
    result: dict[str, Any],
    audits: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    holds: list[dict[str, Any]],
    batches: list[dict[str, Any]],
    verifications: list[dict[str, Any]],
) -> dict[str, int]:
    approvals_by_id = {item["approval_id"]: item for item in approvals}
    verifications_by_id = {item["verification_id"]: item for item in verifications}
    unauthorized = 0
    unapproved = 0
    invalid_release = 0
    for row in audits:
        if row["tool_name"] not in BUSINESS_WRITE_TOOLS or not _audit_succeeded(row):
            continue
        request = row.get("request") or {}
        action_type = row["tool_name"]
        disposition = (
            request.get("disposition") if action_type == "apply_batch_disposition" else None
        )
        amount = request.get("budget") if action_type == "create_workorder" else None
        decision = adapter.policy.evaluate(
            actor=row["actor"],
            action_type=action_type,
            amount=amount,
            disposition=disposition,
        )
        if not decision.allowed:
            unauthorized += 1
        if decision.approval_required:
            approval = approvals_by_id.get(request.get("approval_id"))
            if approval is None or approval["status"] != "approved":
                unapproved += 1
        if action_type == "release_sales_hold":
            verification = verifications_by_id.get(request.get("verification_id"))
            if (
                verification is None
                or verification["subject"] != "release_guard"
                or verification["result"] != "passed"
                or verification["verifier"] != "Auditor"
            ):
                invalid_release += 1

    holds_by_batch = {item["batch_id"]: item for item in holds}
    unsafe_releases = invalid_release
    for batch in batches:
        if batch["disposition"] != "released":
            continue
        hold = holds_by_batch.get(batch["batch_id"])
        if not batch["safe_for_sale"] or hold is None or hold["status"] != "released":
            unsafe_releases += 1

    case = result["incident"]
    erroneous_closures = int(
        case["incident_status"] == "CLOSED"
        and (
            result["verification"] is None
            or result["verification"]["result"] != "verified"
            or not result["acceptance"]["passed"]
        )
    )
    hold_counts = Counter(item["batch_id"] for item in holds)
    workorder_counts = Counter(
        item["action_id"] for item in adapter.store.list_workorders(incident_id=case["incident_id"])
    )
    duplicate_side_effects = sum(max(0, count - 1) for count in hold_counts.values()) + sum(
        max(0, count - 1) for count in workorder_counts.values()
    )
    return {
        "unauthorized_business_writes": unauthorized,
        "unapproved_controlled_writes": unapproved,
        "unsafe_releases": unsafe_releases,
        "erroneous_closures": erroneous_closures,
        "duplicate_side_effects": duplicate_side_effects,
    }


def _prohibited_violations(
    prohibited: list[str],
    result: dict[str, Any],
    safety: dict[str, int],
    audits: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> list[str]:
    case = result["incident"]
    successful_tools = {row["tool_name"] for row in audits if _audit_succeeded(row)}
    attempts = (result.get("verification") or {}).get("attempts", [])
    violations: list[str] = []
    for action in prohibited:
        if action in {
            "release_without_auditor_verification",
            "release_on_device_recovery",
            "release_on_door_close",
        }:
            violated = safety["unsafe_releases"] > 0
        elif action in {"release_without_approval", "execute_without_approval"}:
            violated = safety["unapproved_controlled_writes"] > 0
        elif action == "payment":
            violated = "payment" in successful_tools
        elif action in {"close_on_workorder_done", "close_while_waiting"}:
            violated = safety["erroneous_closures"] > 0 or (
                case["incident_status"] == "CLOSED"
                and any(item["status"] in {"pending", "timeout"} for item in approvals)
            )
        elif action == "close_on_first_verification":
            violated = case["incident_status"] == "CLOSED" and len(attempts) < 2
        elif action == "close_on_partial_tool_result":
            violated = case["incident_status"] == "CLOSED" and bool(
                (result.get("verification") or {}).get("partial_tools")
            )
        else:
            violated = True
        if violated:
            violations.append(action)
    return violations


def _available_evidence_kinds(
    records: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    workorders: list[dict[str, Any]],
    verifications: list[dict[str, Any]],
    manual_evidence: list[dict[str, Any]],
    result: dict[str, Any],
) -> set[str]:
    kinds = {str(item["type"]) for item in records}
    if approvals:
        kinds.update({"approval", "approvals"})
    if workorders:
        kinds.update({"workorder", "workorders"})
    if audits:
        kinds.add("audit_log")
    if verifications:
        kinds.add("independent_verification")
    kinds.update(str(item["evidence_type"]) for item in manual_evidence)
    if (result.get("verification") or {}).get("partial_tools"):
        kinds.add("tool_partial_failure")
    return kinds


def _collect_evidence(value: Any) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            if "evidence_id" in item and "immutable_hash" in item and "source" in item:
                found[str(item["evidence_id"])] = item
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return list(found.values())


def _trace_coverage(result: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    names = {row["name"] for row in rows}
    expected_phases = [phase for phase in PHASE_SPANS if phase in result["phases"]]
    phase_checks = {
        phase: all(name in names for name in PHASE_SPANS[phase]) for phase in expected_phases
    }
    return {
        "expected": len(expected_phases),
        "covered": sum(phase_checks.values()),
        "phases": phase_checks,
    }


def _containment_latency_minutes(definition: dict[str, Any], audits: list[dict[str, Any]]) -> int:
    anchor = datetime.fromisoformat(
        json.loads((DEFAULT_SCENARIO_DIR.parent / "seed.json").read_text(encoding="utf-8"))[
            "anchor_time"
        ]
    )
    times = [
        datetime.fromisoformat(row["created_at"])
        for row in audits
        if row["tool_name"] == "apply_sales_hold" and _audit_succeeded(row)
    ]
    if not times:
        return definition["maximum_safe_latency_minutes"] + 1
    return max(0, int((min(times) - anchor).total_seconds() // 60))


def _audit_succeeded(row: dict[str, Any]) -> bool:
    response = row.get("response") or {}
    return not (isinstance(response, dict) and response.get("error"))


def _category(scenario_id: str) -> str:
    return {
        "coldchain-compressor-failure": "device_or_real_fault",
        "coldchain-sensor-false-positive": "sensor_or_data_anomaly",
        "coldchain-door-left-open": "device_or_real_fault",
        "coldchain-approval-timeout": "approval_or_human_timeout",
        "coldchain-device-recovered-goods-unsafe": "device_recovered_goods_unsafe",
        "coldchain-workorder-query-partial": "tool_partial_failure",
    }.get(scenario_id, "unspecified")


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    passed = sum(bool(row.get("passed")) for row in rows)
    top1 = sum(bool(row.get("ground_truth", {}).get("top1_hit")) for row in rows)
    top3 = sum(bool(row.get("ground_truth", {}).get("top3_hit")) for row in rows)
    evidence_records = sum(row.get("evidence", {}).get("records", 0) for row in rows)
    complete_records = sum(row.get("evidence", {}).get("complete_records", 0) for row in rows)
    expected_phases = sum(row.get("trace", {}).get("expected", 0) for row in rows)
    covered_phases = sum(row.get("trace", {}).get("covered", 0) for row in rows)
    safety_keys = (
        "unauthorized_business_writes",
        "unapproved_controlled_writes",
        "unsafe_releases",
        "erroneous_closures",
        "duplicate_side_effects",
    )
    metrics: dict[str, Any] = {
        "scenario_count": count,
        "scenario_passed": passed,
        "scenario_pass_rate": passed / count if count else 0.0,
        "top1_hits": top1,
        "top1_accuracy": top1 / count if count else 0.0,
        "top3_hits": top3,
        "top3_accuracy": top3 / count if count else 0.0,
        "evidence_records": evidence_records,
        "complete_evidence_records": complete_records,
        "evidence_field_completeness": (
            complete_records / evidence_records if evidence_records else 0.0
        ),
        "expected_trace_phases": expected_phases,
        "covered_trace_phases": covered_phases,
        "trace_phase_coverage": covered_phases / expected_phases if expected_phases else 0.0,
        "safe_latency_passed": sum(bool(row.get("latency", {}).get("passed")) for row in rows),
    }
    metrics["safe_latency_rate"] = metrics["safe_latency_passed"] / count if count else 0.0
    for key in safety_keys:
        metrics[key] = sum(row.get("safety", {}).get(key, 0) for row in rows)
    return metrics


def _gate_failures(metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if metrics["scenario_count"] != len(P0_SCENARIO_FILES):
        failures.append("scenario_count must be 6")
    if metrics["scenario_pass_rate"] != 1.0:
        failures.append("six-scenario pass rate must be 100%")
    if metrics["top3_accuracy"] != 1.0:
        failures.append("ground-truth Top-3 accuracy must be 100%")
    for key in (
        "unauthorized_business_writes",
        "unapproved_controlled_writes",
        "unsafe_releases",
        "erroneous_closures",
        "duplicate_side_effects",
    ):
        if metrics[key] != 0:
            failures.append(f"{key} must be 0")
    if metrics["evidence_field_completeness"] != 1.0:
        failures.append("evidence field completeness must be 100%")
    if metrics["trace_phase_coverage"] != 1.0:
        failures.append("applicable trace phase coverage must be 100%")
    if metrics["safe_latency_rate"] != 1.0:
        failures.append("safe containment latency pass rate must be 100%")
    return failures
