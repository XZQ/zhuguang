"""Architecture ablation: quantify what each safety layer contributes.

Variants
--------
- ``full``: baseline five-role pipeline (Orchestrator/Sentry/Diagnoser/Executor/Auditor)
  with the IncidentService aggregate gate and MCP guards. Expected: 6/6 acceptance.
- ``no_auditor``: the baseline path is unchanged through execution, but no independent
  verification is available. Repaired branches stop at VERIFY/BLOCKED; no actor may
  self-certify, release holds, or bypass the IncidentService aggregate gate.
- ``single_agent``: one role-less identity reaches the first controlled write. Policy
  allow-lists reject containment, so the pipeline stops immediately (fail-safe by refusal).
- ``rule_only``: a static base-rate prior replaces only root-cause ranking. Batch risk
  assessment remains evidence based; downstream containment/approval/verification layers
  keep outcomes safe while diagnosis quality degrades.

Everything runs on the same deterministic virtual clock as the M4 suite. No LLM is
called; latency/token/cost deltas require the external AgentTeams runtime and are
explicitly out of scope (recorded in ``methodology``).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import trace
from .adapters.local_demo import LocalDemoAdapter
from .domain import Hypothesis, IncidentCase, IncidentType, Phase, Severity, WorkStatus
from .evaluation import (
    BUSINESS_WRITE_TOOLS,
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_SCENARIO_DIR,
    P0_SCENARIO_FILES,
    _audit_succeeded,
    _category,
    _required_action_checks,
    _safety_metrics,
    _trace_coverage,
)

ABLATION_VARIANTS = ("full", "no_auditor", "single_agent", "rule_only")
ABLATION_SUITE_ID = "dianxun-p0-coldchain-ablation-v1"

# Static base-rate prior for the rule_only variant: ignores scenario evidence,
# manual measurements and data-quality signals.
_STATIC_PRIOR = (
    ("compressor_failure", 0.55),
    ("door_left_open", 0.20),
    ("sensor_fault", 0.15),
    ("power_failure", 0.10),
)

_SAFETY_KEYS = (
    "unauthorized_business_writes",
    "unapproved_controlled_writes",
    "unsafe_releases",
    "erroneous_closures",
    "duplicate_side_effects",
)


class AblationAdapter(LocalDemoAdapter):
    """Run one scenario under an ablated architecture variant."""

    def __init__(self, *, variant: str, **kwargs: Any) -> None:
        if variant not in ABLATION_VARIANTS:
            raise ValueError(f"Unknown ablation variant {variant}")
        self.variant = variant
        super().__init__(**kwargs)

    def _run(self) -> dict[str, Any]:
        if self.variant in {"full", "rule_only"}:
            # rule_only only swaps the diagnosis step; every other layer stays intact.
            return super()._run()
        if self.variant == "single_agent":
            return self._run_single_agent()
        return self._run_no_auditor()

    # ------------------------------------------------------------------
    # rule_only: static prior replaces evidence-linked diagnosis
    # ------------------------------------------------------------------
    def _diagnose(self, **kwargs: Any) -> dict[str, Any]:
        if self.variant != "rule_only":
            return super()._diagnose(**kwargs)
        return self._diagnose_static_prior(**kwargs)

    def _diagnose_static_prior(
        self,
        *,
        incident_id: str,
        trace_id: str,
        store_id: str,
        device_id: str,
    ) -> dict[str, Any]:
        from .skills import coldchain_risk_assess

        with trace.span("diagnoser", "agent", trace_id, input={"incident_id": incident_id}) as sp:
            hypotheses = [
                Hypothesis(
                    hypothesis_id=f"{incident_id}:hyp:static:{label}",
                    label=label,
                    confidence=confidence,
                    missing_evidence=["static base-rate prior: scenario evidence not consulted"],
                    policy_notes=["rule_only ablation: fixed prior, evidence not consulted"],
                )
                for label, confidence in _STATIC_PRIOR
            ]
            self.incidents.replace_hypotheses(incident_id, hypotheses)
            device = self.mcp.query_device_context(
                store_id=store_id,
                device_id=device_id,
                incident_id=incident_id,
                actor="Diagnoser",
            )["data"]["devices"][0]
            batches_response = self.mcp.query_inventory_batches(
                store_id=store_id,
                device_id=device_id,
                incident_id=incident_id,
                actor="Diagnoser",
            )
            batches = batches_response["data"]["batches"]
            self._append_evidence(incident_id, batches_response["data"].get("evidence", []))
            assessment = coldchain_risk_assess(
                incident_id=incident_id,
                device_series=device.get("temperature_series", []),
                affected_batches=batches,
                policy=self.policy.policy,
                trace_id=trace_id,
                manual_measurements=self.store.list_manual_evidence(incident_id=incident_id),
            )
            case = self.incidents.get(incident_id)
            top = case.hypotheses[0]
            dispositions = [
                f"{item['recommendation']}:{item['batch_id']}"
                for item in assessment["exposure_assessment"]
            ]
            from .domain import Decision

            self.incidents.append_decision(
                incident_id,
                Decision(
                    decision_id=f"{incident_id}:decision:v1",
                    policy_id=(
                        f"{self.policy.policy['policy_id']}:{self.policy.policy['policy_version']}"
                    ),
                    selected_hypothesis_ids=[top.hypothesis_id],
                    proposed_actions=["create_workorder", *dispositions],
                    risk_level="L2",
                    approval_required=True,
                    approvers=["store_manager", "food_safety_owner"],
                    decision_reason=(
                        f"static prior top hypothesis {top.label} "
                        "plus batch-specific exposure assessment"
                    ),
                    evidence_ids=list(case.evidence_refs),
                    created_by="Diagnoser",
                ),
            )
            result = {
                "hypotheses": [asdict(item) for item in hypotheses],
                "evidence": [],
                "quality": "static_prior_only",
                "data_quality": {},
                "rag": {"enabled": False},
                "risk_assessment": assessment,
            }
            sp.output = {
                "top_hypothesis": top.label,
                "confidence": top.confidence,
                "batch_recommendations": dispositions,
            }
            return result

    # ------------------------------------------------------------------
    # no_auditor: execution completes, but independent verification is unavailable
    # ------------------------------------------------------------------
    def _run_no_auditor(self) -> dict[str, Any]:
        self.scenario.reset()
        definition = self.scenario.scenario
        ground_truth = definition["ground_truth"]
        workflow = definition.get("workflow", {})
        incident_id = ground_truth.get("incident_id") or _incident_id(definition["scenario_id"])
        trace_id = f"tr_{definition['scenario_id'].replace('-', '_')}"
        trace.clear_trace(trace_id)
        store_id = ground_truth["store_id"]
        device_id = ground_truth["device_id"]
        phase_outputs: dict[str, Any] = {}

        with trace.span(
            "coldchain-orchestrator",
            "agent",
            trace_id,
            input={"scenario_id": definition["scenario_id"], "incident_id": incident_id},
        ) as root:
            detection = self._detect(
                trace_id=trace_id,
                incident_id=incident_id,
                store_id=store_id,
                device_id=device_id,
            )
            phase_outputs["DETECT_CONTAIN"] = detection
            case = IncidentCase.create(
                incident_id=incident_id,
                trace_id=trace_id,
                tenant_id=ground_truth.get("tenant_id", "demo"),
                store_id=store_id,
                incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
                severity=Severity(detection["severity"]),
                trigger="scenario",
                anchor_time=self.store.get_meta("anchor_time") or self.store.now(),
                detected_at=self.store.now(),
            )
            case.affected_assets = [device_id]
            case.affected_batches = list(detection["affected_batches"])
            self.incidents.create(case)
            self._append_evidence(incident_id, detection["evidence"])
            containment = self._contain(incident_id, trace_id)
            phase_outputs["DETECT_CONTAIN"]["containment"] = containment
            self.incidents.recompute(incident_id)

            self.incidents.transition_phase(
                incident_id,
                Phase.DIAGNOSE_DECIDE,
                actor="Orchestrator",
                reason="risk contained; delegate evidence-linked diagnosis",
            )
            diagnosis_minute = workflow.get("diagnosis_evidence_minute")
            if diagnosis_minute is not None:
                self._advance_to(int(diagnosis_minute))
                self._append_manual_evidence_refs(incident_id)
            diagnosis = self._diagnose(
                incident_id=incident_id,
                trace_id=trace_id,
                store_id=store_id,
                device_id=device_id,
            )
            phase_outputs["DIAGNOSE_DECIDE"] = diagnosis

            self.incidents.transition_phase(
                incident_id,
                Phase.EXECUTE,
                actor="Orchestrator",
                reason="policy-bound execution plan accepted",
            )
            with trace.span(
                "executor",
                "agent",
                trace_id,
                input={
                    "incident_id": incident_id,
                    "top_hypothesis": diagnosis["hypotheses"][0]["label"],
                },
            ) as executor_span:
                repair = self._execute_repair(
                    incident_id=incident_id,
                    trace_id=trace_id,
                    store_id=store_id,
                    device_id=device_id,
                    fault=diagnosis["hypotheses"][0]["label"],
                    workflow=workflow,
                )
                executor_span.output = {"result": repair["result"]}
            phase_outputs["EXECUTE"] = {"repair": repair}
            if repair["result"] != "executed":
                # Repair never happened (e.g. approval timeout): even a self-certifying
                # executor cannot claim success, so the incident stays open/waiting.
                final_case = self.incidents.recompute(incident_id)
                wait_status = (
                    WorkStatus.WAITING_EXTERNAL
                    if repair["result"] == "timeout"
                    else WorkStatus.BLOCKED
                )
                final_case = self.incidents.set_work_status(
                    incident_id,
                    wait_status,
                    owner=("regional_manager" if repair["result"] == "timeout" else "Orchestrator"),
                    next_wakeup_at=repair.get("deadline"),
                    reason="repair not executed; containment remains active",
                )
                result = self._result(
                    phase_outputs=phase_outputs,
                    verification=None,
                    review=None,
                    case=final_case,
                )
                result["ablation"] = {
                    "variant": self.variant,
                    "self_declared_closure": False,
                    "verification_blocked": False,
                }
                root.output = {"result": result["result"], "acceptance": result["acceptance"]}
                return result

            completion_minute = int(workflow.get("repair_completion_minute", 5))
            self._advance_to(completion_minute)
            self._append_manual_evidence_refs(incident_id)
            dispositions = self._execute_batch_dispositions(
                incident_id=incident_id,
                trace_id=trace_id,
                assessment=diagnosis["risk_assessment"],
                workflow=workflow,
            )
            phase_outputs["EXECUTE"]["batch_dispositions"] = dispositions

            self.incidents.transition_phase(
                incident_id,
                Phase.VERIFY,
                actor="Orchestrator",
                reason="execution complete; independent Auditor verification is required",
            )
            final_case = self.incidents.set_work_status(
                incident_id=incident_id,
                status=WorkStatus.BLOCKED,
                owner="Auditor",
                next_wakeup_at=None,
                reason="independent Auditor verification is unavailable",
            )
            result = self._result(
                phase_outputs=phase_outputs,
                verification=None,
                review=None,
                case=final_case,
            )
            result["ablation"] = {
                "variant": self.variant,
                "self_declared_closure": False,
                "verification_blocked": True,
            }
            root.output = {"result": result["result"], "acceptance": result["acceptance"]}
            return result

    # ------------------------------------------------------------------
    # single_agent: one identity for every step; policy rejects its writes
    # ------------------------------------------------------------------
    def _run_single_agent(self) -> dict[str, Any]:
        self.scenario.reset()
        definition = self.scenario.scenario
        ground_truth = definition["ground_truth"]
        incident_id = ground_truth.get("incident_id") or _incident_id(definition["scenario_id"])
        trace_id = f"tr_{definition['scenario_id'].replace('-', '_')}"
        trace.clear_trace(trace_id)
        store_id = ground_truth["store_id"]
        device_id = ground_truth["device_id"]
        phase_outputs: dict[str, Any] = {}

        with trace.span(
            "coldchain-single-agent",
            "agent",
            trace_id,
            input={"scenario_id": definition["scenario_id"], "incident_id": incident_id},
        ) as root:
            detection = self._detect(
                trace_id=trace_id,
                incident_id=incident_id,
                store_id=store_id,
                device_id=device_id,
            )
            phase_outputs["DETECT_CONTAIN"] = detection
            case = IncidentCase.create(
                incident_id=incident_id,
                trace_id=trace_id,
                tenant_id=ground_truth.get("tenant_id", "demo"),
                store_id=store_id,
                incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
                severity=Severity(detection["severity"]),
                trigger="scenario",
                anchor_time=self.store.get_meta("anchor_time") or self.store.now(),
                detected_at=self.store.now(),
            )
            case.affected_assets = [device_id]
            case.affected_batches = list(detection["affected_batches"])
            self.incidents.create(case)
            self._append_evidence(incident_id, detection["evidence"])
            containment = self._contain_single_agent(incident_id, trace_id)
            phase_outputs["DETECT_CONTAIN"]["containment"] = containment
            final_case = self.incidents.recompute(incident_id)
            result = self._result(
                phase_outputs=phase_outputs,
                verification=None,
                review=None,
                case=final_case,
            )
            result["ablation"] = {
                "variant": self.variant,
                "containment_denied": not containment["ok"],
            }
            root.output = {"result": result["result"], "acceptance": result["acceptance"]}
            return result

    def _contain_single_agent(self, incident_id: str, trace_id: str) -> dict[str, Any]:
        """Containment attempt with a role-less identity; policy denies the write."""
        case = self.incidents.get(incident_id)
        request = {"batch_ids": case.affected_batches, "reason": "coldchain containment"}
        with trace.span("executor-containment", "agent", trace_id, input=request) as sp:
            response = self.mcp.apply_sales_hold(
                incident_id=incident_id,
                action_id=f"{incident_id}:hold",
                store_id=case.store_id,
                batch_ids=case.affected_batches,
                reason="coldchain temperature risk containment",
                idempotency_key=f"{incident_id}:hold:v1",
                actor="SingleAgent",
            )
            sp.output = {"ok": response["ok"], "error": response.get("error")}
        return response


def _incident_id(scenario_id: str) -> str:
    return "INC-" + scenario_id.upper().replace("-", "_")


def _evaluate_run(
    *,
    adapter: AblationAdapter,
    result: dict[str, Any],
    trace_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    definition = adapter.scenario.scenario
    case = result["incident"]
    incident_id = case["incident_id"]
    store = adapter.store
    audits = store.list_audit_log(incident_id=incident_id)
    approvals = store.list_approvals(incident_id=incident_id)
    holds = store.list_sales_holds(incident_id=incident_id)
    batches = store.list_batches(batch_ids=case["affected_batches"])
    verifications = store.list_verifications(incident_id=incident_id)
    workorders = store.list_workorders(incident_id=incident_id)
    manual_evidence = store.list_manual_evidence(incident_id=incident_id)
    safety = _safety_metrics(adapter, result, audits, approvals, holds, batches, verifications)
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
    holds_by_batch = {item["batch_id"]: item for item in holds}
    dangerous_release_batches = sum(
        1
        for item in batches
        if item["disposition"] == "released"
        and not item["safe_for_sale"]
        and holds_by_batch.get(item["batch_id"], {}).get("status") == "released"
    )

    hypotheses = (result["phases"].get("DIAGNOSE_DECIDE") or {}).get("hypotheses") or []
    labels = [item["label"] for item in hypotheses]
    root_cause = definition["ground_truth"]["root_cause"]
    successful_tools = {row["tool_name"] for row in audits if _audit_succeeded(row)}
    denied_writes = [
        row
        for row in audits
        if row["tool_name"] in BUSINESS_WRITE_TOOLS and not _audit_succeeded(row)
    ]
    ablation = result.get("ablation") or {}
    release = ablation.get("release") or {}
    attempted_unsafe_batches = sum(
        1 for item in release.get("batches", []) if not item.get("disposition_closed", True)
    )
    misrouted = sum(1 for item in workorders if item.get("fault") != root_cause)
    trace_result = _trace_coverage(result, trace_rows)
    return {
        "scenario_id": definition["scenario_id"],
        "category": definition["ground_truth"].get(
            "category", _category(definition["scenario_id"])
        ),
        "variant": adapter.variant,
        "acceptance_passed": bool(result["acceptance"]["passed"]),
        "final_state": {
            "incident_status": str(case["incident_status"]),
            "phase": str(case["phase"]),
            "work_status": str(case["work_status"]),
        },
        "ground_truth": {
            "root_cause": root_cause,
            "top1_hit": bool(labels and labels[0] == root_cause) if labels else None,
            "top3_hit": (root_cause in labels[:3]) if labels else None,
        },
        "contained": "apply_sales_hold" in successful_tools,
        "closed": str(case["incident_status"]) == "CLOSED",
        "self_declared_closure": bool(ablation.get("self_declared_closure")),
        "verification_blocked": bool(ablation.get("verification_blocked")),
        "safety": safety,
        "denied_write_attempts": len(denied_writes),
        "release": {
            "attempted": bool(release.get("attempted")),
            "result": release.get("result"),
            "stage": release.get("stage"),
            "attempted_unsafe_batches": attempted_unsafe_batches,
        },
        "misrouted_workorders": misrouted,
        "required_actions_failed": sum(1 for ok in required_checks.values() if not ok),
        "dangerous_release_batches": dangerous_release_batches,
        "trace": trace_result,
    }


def run_ablation(scenario_dir: str | Path = DEFAULT_SCENARIO_DIR) -> dict[str, Any]:
    """Run all six scenarios under every variant and return the comparison."""
    scenario_root = Path(scenario_dir).resolve()
    runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dianxun-ablation-") as temporary:
        runtime_root = Path(temporary)
        for variant in ABLATION_VARIANTS:
            for index, filename in enumerate(P0_SCENARIO_FILES, start=1):
                scenario_path = scenario_root / filename
                adapter = AblationAdapter(
                    variant=variant,
                    db_path=runtime_root / f"{variant}-{index}.db",
                    trace_db_path=runtime_root / f"{variant}-{index}.trace.db",
                    scenario_path=scenario_path,
                )
                result = adapter.run()
                with trace.use_database(adapter.trace_db_path):
                    trace_rows = trace.query_trace(result["trace_id"])
                runs.append(_evaluate_run(adapter=adapter, result=result, trace_rows=trace_rows))

    seed = json.loads((scenario_root.parent / "seed.json").read_text(encoding="utf-8"))
    summaries = {variant: _summarize(runs, variant) for variant in ABLATION_VARIANTS}
    findings = _findings(summaries)
    gate_failures = _gate_failures(summaries)
    return {
        "schema_version": 1,
        "suite_id": ABLATION_SUITE_ID,
        "anchor_time": seed["anchor_time"],
        "baseline_suite_id": "dianxun-p0-coldchain-v1",
        "variants": list(ABLATION_VARIANTS),
        "runs": runs,
        "summary": summaries,
        "findings": findings,
        "ablation_gate": {"passed": not gate_failures, "failures": gate_failures},
        "methodology": {
            "state": "fresh temporary SQLite database per scenario and variant",
            "time": "scenario virtual clock anchored by demo/state/seed.json",
            "llm": "not called; latency/token/cost deltas need the external AgentTeams runtime",
            "counterfactuals": (
                "attempted_unsafe_release_batches counts batches whose disposition was not "
                "terminal when a variant tried to release their holds; whether the release "
                "physically succeeded is reported separately as dangerous_release_batches; "
                "release_state_inconsistencies counts a released disposition while its sales "
                "hold remains active or is missing"
            ),
        },
    }


def _summarize(runs: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    rows = [row for row in runs if row["variant"] == variant]
    count = len(rows)
    top1 = [row for row in rows if row["ground_truth"]["top1_hit"] is not None]
    summary: dict[str, Any] = {
        "scenarios": count,
        "acceptance_passed": sum(row["acceptance_passed"] for row in rows),
        "top1_hits": sum(bool(row["ground_truth"]["top1_hit"]) for row in top1),
        "top3_hits": sum(bool(row["ground_truth"]["top3_hit"]) for row in top1),
        "diagnosed": len(top1),
        "contained": sum(row["contained"] for row in rows),
        "closed": sum(row["closed"] for row in rows),
        "self_declared_closures": sum(row["self_declared_closure"] for row in rows),
        "verification_blocked": sum(row["verification_blocked"] for row in rows),
        "denied_write_attempts": sum(row["denied_write_attempts"] for row in rows),
        "release_attempts": sum(row["release"]["attempted"] for row in rows),
        "release_denials": sum(row["release"]["result"] == "denied" for row in rows),
        "release_executed": sum(row["release"]["result"] == "executed" for row in rows),
        "attempted_unsafe_release_batches": sum(
            row["release"]["attempted_unsafe_batches"] for row in rows
        ),
        "misrouted_workorders": sum(row["misrouted_workorders"] for row in rows),
        "required_actions_failed": sum(row["required_actions_failed"] for row in rows),
        "dangerous_release_batches": sum(row["dangerous_release_batches"] for row in rows),
        "release_state_inconsistencies": sum(
            row["safety"]["release_state_inconsistencies"] for row in rows
        ),
        "trace_fully_covered": sum(
            row["trace"]["covered"] == row["trace"]["expected"] for row in rows
        ),
    }
    for key in _SAFETY_KEYS:
        summary[key] = sum(row["safety"][key] for row in rows)
    return summary


def _findings(summaries: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    full = summaries["full"]
    no_auditor = summaries["no_auditor"]
    single = summaries["single_agent"]
    rule = summaries["rule_only"]
    return [
        {
            "variant": "no_auditor",
            "title": "移除 Auditor 独立验证:安全拒动而非自证关闭",
            "observed": (
                f"{no_auditor['verification_blocked']}/6 场景在执行后停于 VERIFY/BLOCKED;"
                f"自我宣告关闭 {no_auditor['self_declared_closures']} 起,"
                f"放行尝试 {no_auditor['release_attempts']} 次,"
                f"错误关闭 {no_auditor['erroneous_closures']} 起,"
                f"不安全批次实际放行 {no_auditor['dangerous_release_batches']} 起,"
                f"安全阻断导致的处置/停售状态不一致 "
                f"{no_auditor['release_state_inconsistencies']} 起。"
            ),
            "interpretation": (
                "独立验证是进入关闭/放行路径的必要能力;当 Auditor 不可用时,"
                "系统保持遏制并阻断在验证阶段,不会让 Executor 自证或绕过聚合门。"
            ),
        },
        {
            "variant": "single_agent",
            "title": "单一 Agent 身份:受控写在 Policy 层被拒",
            "observed": (
                f"{single['denied_write_attempts']} 次受控写全部被 Policy 拒绝"
                f"(allowed_actors 不含 SingleAgent),"
                f"{single['contained']}/6 场景完成遏制,事件停留在 OPEN。"
            ),
            "interpretation": (
                "角色身份是写入路径的硬前提;单一身份的 Agent 连停售遏制都无法执行,"
                "系统以拒动方式降级保安全(fail-safe by refusal)。"
            ),
        },
        {
            "variant": "rule_only",
            "title": "静态先验替代证据关联诊断",
            "observed": (
                f"Top-1 命中 {rule['top1_hits']}/6(基线 {full['top1_hits']}/6),"
                f"错派工单 {rule['misrouted_workorders']} 张"
                "(B 把传感器故障误判为压缩机故障、C 把门未关误判为压缩机故障);"
                f"安全违规 {sum(rule[key] for key in _SAFETY_KEYS)} 起。"
            ),
            "interpretation": (
                "诊断质量决定维修正确性与成本;误判时下游遏制/审批/验证层仍保证最终安全,"
                "但错误工单在真实门店意味着误修、浪费与故障未除。"
            ),
        },
    ]


def _gate_failures(summaries: dict[str, dict[str, Any]]) -> list[str]:
    full = summaries["full"]
    no_auditor = summaries["no_auditor"]
    single = summaries["single_agent"]
    rule = summaries["rule_only"]
    failures: list[str] = []
    if full["acceptance_passed"] != 6 or any(full[key] != 0 for key in _SAFETY_KEYS):
        failures.append("baseline must pass 6/6 with zero safety violations")
    if (
        no_auditor["closed"] != 0
        or no_auditor["self_declared_closures"] != 0
        or no_auditor["erroneous_closures"] != 0
    ):
        failures.append("no_auditor must never close or self-certify an incident")
    if no_auditor["release_attempts"] != 0 or no_auditor["dangerous_release_batches"] != 0:
        failures.append("no_auditor must never enter the sales-hold release path")
    if no_auditor["verification_blocked"] <= 0:
        failures.append("no_auditor must block repaired branches at independent verification")
    if no_auditor["acceptance_passed"] >= full["acceptance_passed"]:
        failures.append("no_auditor must degrade acceptance relative to the full baseline")
    if single["contained"] != 0 or single["denied_write_attempts"] != 6:
        failures.append("single_agent must be denied on all 6 containment writes")
    if single["closed"] != 0:
        failures.append("single_agent must not close any incident")
    if rule["top1_hits"] >= full["top1_hits"] or rule["misrouted_workorders"] <= 0:
        failures.append("rule_only must degrade diagnosis relative to the evidence-linked baseline")
    if any(rule[key] != 0 for key in _SAFETY_KEYS):
        failures.append("rule_only must keep zero safety violations (downstream layers hold)")
    return failures


def write_ablation_artifacts(
    ablation: dict[str, Any],
    output_dir: str | Path = DEFAULT_EVIDENCE_DIR,
) -> tuple[Path, Path]:
    """Write stable JSON and Markdown artifacts and return their paths."""
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "ablation.json"
    report_path = target / "ablation.md"
    json_path.write_text(
        json.dumps(ablation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(
        render_ablation_markdown(ablation),
        encoding="utf-8",
        newline="\n",
    )
    return json_path, report_path


def render_ablation_markdown(ablation: dict[str, Any]) -> str:
    summary = ablation["summary"]
    gate = ablation["ablation_gate"]
    lines = [
        "# 逐光|消融对照:多 Agent 安全层的增量价值",
        "",
        f"> 消融门禁:{'通过' if gate['passed'] else '未通过'}",
        "> 口径:六场景 x 四架构变体,同一确定性虚拟时钟,不调用 LLM;",
        "> 延迟/Token/成本差异需真实 AgentTeams 运行时,不在本报告范围。",
        "",
        "## 变体定义",
        "",
        "| 变体 | 移除的层 | 其余部分 |",
        "|---|---|---|",
        "| full(基线) | 无 | 五角色 + IncidentService 聚合门 + Policy/MCP 防线 |",
        "| no_auditor | Auditor 独立验证 | 执行路径不变,完成后停于 VERIFY/BLOCKED |",
        "| single_agent | 角色身份分离 | 单一身份在首个受控写处被拒 |",
        "| rule_only | 证据关联的根因排序 | 静态先验排序,证据化批次风险与下游防线保留 |",
        "",
        "## 关键指标对照",
        "",
        "| 指标 | full | no_auditor | single_agent | rule_only |",
        "|---|---:|---:|---:|---:|",
    ]
    rows = [
        ("验收通过场景", "acceptance_passed"),
        ("Top-1 命中", "top1_hits"),
        ("完成遏制", "contained"),
        ("错误关闭事件", "erroneous_closures"),
        ("自我宣告关闭", "self_declared_closures"),
        ("缺独立验证而阻断", "verification_blocked"),
        ("必需动作缺失", "required_actions_failed"),
        ("放行尝试被拦截", "release_denials"),
        ("试图放行未闭环批次", "attempted_unsafe_release_batches"),
        ("不安全批次实际放行", "dangerous_release_batches"),
        ("不安全或未授权的停售解除", "unsafe_releases"),
        ("处置/停售状态不一致", "release_state_inconsistencies"),
        ("被拒受控写", "denied_write_attempts"),
        ("错派工单", "misrouted_workorders"),
        ("未授权业务写", "unauthorized_business_writes"),
        ("未审批受控写", "unapproved_controlled_writes"),
        ("重复副作用", "duplicate_side_effects"),
    ]
    for label, key in rows:
        lines.append(
            "| {label} | {full} | {no_auditor} | {single} | {rule} |".format(
                label=label,
                full=summary["full"][key],
                no_auditor=summary["no_auditor"][key],
                single=summary["single_agent"][key],
                rule=summary["rule_only"][key],
            )
        )
    lines.extend(["", "## 结论", ""])
    for finding in ablation["findings"]:
        lines.extend(
            [
                f"### {finding['title']}",
                "",
                f"- 观察:{finding['observed']}",
                f"- 解读:{finding['interpretation']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 边界",
            "",
            "- 消融结果来自真实临时 SQLite/PolicyEngine、有状态本地 Adapter/ScenarioEngine",
            "  与固定 seed,证明架构各层的相对贡献,",
            "  不代表真实门店收益;LLM 延迟/Token/成本对照需真实 AgentTeams 运行时。",
            "- `no_auditor` 只移除独立验证能力,不改变执行计划、放行策略或聚合门;",
            "  因此结果体现的是系统在验证者不可用时的安全拒动,不是人为构造的错误关闭。",
            "",
        ]
    )
    if gate["failures"]:
        lines.extend(["## 未通过项", "", *[f"- {item}" for item in gate["failures"]], ""])
    return "\n".join(lines)
