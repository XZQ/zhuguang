"""Architecture ablation: quantify what each safety layer contributes.

Variants
--------
- ``full``: baseline five-role pipeline (Orchestrator/Sentry/Diagnoser/Executor/Auditor)
  with the IncidentService aggregate gate and MCP guards. Expected: 6/6 acceptance.
- ``no_auditor``: roles stay, but VERIFY is replaced by Executor self-certification
  and the incident is self-declared CLOSED, bypassing the aggregate gate. Expected:
  erroneous closures on 5/6 scenarios; physical unsafe release still blocked by the
  MCP ``release_guard`` (verifier must be Auditor) and approval layer.
- ``single_agent``: one identity performs every step. Policy allow-lists reject all
  controlled writes, so containment never happens (fail-safe by refusal).
- ``rule_only``: static base-rate prior replaces evidence-linked diagnosis. Expected:
  Top-1 drops to 4/6 and two misrouted workorders (scenarios B and C), while the
  downstream containment/approval/verification layers keep outcomes safe.

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
from .domain import (
    Action,
    ActionStatus,
    Hypothesis,
    IncidentCase,
    IncidentStatus,
    IncidentType,
    Phase,
    Severity,
    Verification,
    VerificationResult,
    WorkStatus,
)
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

# Batches whose disposition is terminal; releasing holds on any other batch means
# releasing goods whose disposition has not been closed out (the scenario E danger).
_TERMINAL_DISPOSITIONS = ("transferred", "released", "disposed")


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
    # no_auditor: Executor self-certifies and self-declares closure
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
                result["ablation"] = {"variant": self.variant, "self_declared_closure": False}
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
                reason="executor self-certification replaces independent verification",
            )
            verification = self._self_certify(incident_id, trace_id, repair=repair)
            phase_outputs["VERIFY"] = verification

            release = self._execute_naive_release(
                incident_id=incident_id,
                trace_id=trace_id,
                workflow=workflow,
            )
            phase_outputs["EXECUTE"]["naive_release"] = release

            final_case = self._self_declare_closed(incident_id)
            result = self._result(
                phase_outputs=phase_outputs,
                verification=verification,
                review=None,
                case=final_case,
            )
            result["ablation"] = {
                "variant": self.variant,
                "self_declared_closure": True,
                "release": release,
            }
            root.output = {"result": result["result"], "acceptance": result["acceptance"]}
            return result

    def _self_certify(
        self,
        incident_id: str,
        trace_id: str,
        *,
        repair: dict[str, Any],
    ) -> dict[str, Any]:
        """Executor certifies success from its own receipts; no independent requery."""
        with trace.span(
            "executor-self-certify",
            "agent",
            trace_id,
            input={"incident_id": incident_id},
        ) as sp:
            receipts_ok = repair["result"] == "executed"
            for subject in ("device", "release_guard"):
                self.incidents.record_verification(
                    incident_id,
                    Verification(
                        verification_id=f"{incident_id}:verify:{subject}",
                        subject=subject,
                        method="executor_own_receipts",
                        expected_condition={"repair_receipt": "executed"},
                        observed_value={"repair_result": repair["result"]},
                        evidence_ids=[],
                        result=(
                            VerificationResult.PASSED if receipts_ok else VerificationResult.FAILED
                        ),
                        verifier="Executor",
                        verified_at=self.store.now(),
                    ),
                )
            result = {
                "incident_id": incident_id,
                "result": "self_certified" if receipts_ok else "self_check_failed",
                "checks": {
                    "executor_receipts": {
                        "passed": receipts_ok,
                        "expected": {"repair_result": "executed"},
                        "observed": {"repair_result": repair["result"]},
                    }
                },
                "failed_conditions": [] if receipts_ok else ["executor_receipts"],
                "evidence_refs": [],
                "next_actions": [],
                "partial_tools": [],
                "evidence": [],
                "attempts": [
                    {
                        "result": "self_certified" if receipts_ok else "self_check_failed",
                        "failed_conditions": [] if receipts_ok else ["executor_receipts"],
                        "partial_tools": [],
                    }
                ],
                "self_declared": True,
                "verifier": "Executor",
            }
            sp.output = {"result": result["result"]}
            return result

    def _execute_naive_release(
        self,
        *,
        incident_id: str,
        trace_id: str,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        """Monolith tries to release every active hold once the device looks fine."""
        holds = self.store.list_sales_holds(incident_id=incident_id, status="active")
        if not holds:
            return {"attempted": False, "result": "no_active_holds", "batches": []}
        batch_ids = sorted({item["batch_id"] for item in holds})
        batch_rows = {row["batch_id"]: row for row in self.store.list_batches(batch_ids=batch_ids)}
        batches = [
            {
                "batch_id": batch_id,
                "disposition": batch_rows[batch_id]["disposition"],
                "disposition_closed": batch_rows[batch_id]["disposition"] in _TERMINAL_DISPOSITIONS,
            }
            for batch_id in batch_ids
        ]
        action_id = f"{incident_id}:release-holds"
        approval_response = self.mcp.create_approval(
            incident_id=incident_id,
            action_id=action_id,
            subject=f"release sales holds for {incident_id}",
            requested_action_type="release_sales_hold",
            timeout_minutes=int(workflow.get("release_approval_timeout_minutes", 30)),
            idempotency_key=f"{action_id}:approval:v1",
            actor="Executor",
        )
        if not approval_response["ok"]:
            return {
                "attempted": True,
                "result": "denied",
                "stage": "create_approval",
                "error": approval_response.get("error"),
                "batches": batches,
            }
        approval = approval_response["data"]
        self.incidents.append_action(
            incident_id,
            Action(
                action_id=action_id,
                action_type="release_sales_hold",
                tool_name="release_sales_hold",
                target=incident_id,
                idempotency_key=f"{action_id}:execute:v1",
                approval_id=approval["approval_id"],
                status=ActionStatus.PENDING,
                request={"hold_ids": [item["hold_id"] for item in holds]},
                response=approval_response,
                rollback_or_compensation={"type": "reapply_sales_hold"},
                started_at=self.store.now(),
            ),
        )
        decision_minute = workflow.get("release_approval_decision_minute")
        if decision_minute is not None:
            self._advance_to(int(decision_minute))
        queried = self.mcp.query_approval(
            approval_id=approval["approval_id"],
            incident_id=incident_id,
            action_id=action_id,
            actor="Orchestrator",
        )
        row = queried["data"]["approvals"][0]
        if row["status"] != "approved":
            return {
                "attempted": True,
                "result": "denied",
                "stage": "approval",
                "approval_status": row["status"],
                "batches": batches,
            }
        self.incidents.update_action(
            incident_id,
            action_id,
            status=ActionStatus.APPROVED,
            response=queried,
        )
        with trace.span(
            "release_sales_hold",
            "mcp",
            trace_id,
            input={"incident_id": incident_id, "hold_count": len(holds)},
        ) as tool_span:
            response = self.mcp.release_sales_hold(
                incident_id=incident_id,
                action_id=action_id,
                hold_ids=[item["hold_id"] for item in holds],
                approval_id=approval["approval_id"],
                verification_id=f"{incident_id}:verify:release_guard",
                idempotency_key=f"{action_id}:execute:v1",
                actor="Executor",
            )
            tool_span.output = {"ok": response["ok"], "error": response.get("error")}
        self.incidents.update_action(
            incident_id,
            action_id,
            status=ActionStatus.COMPLETED if response["ok"] else ActionStatus.FAILED,
            response=response,
        )
        if not response["ok"]:
            return {
                "attempted": True,
                "result": "denied",
                "stage": "release_guard",
                "error": response.get("error"),
                "batches": batches,
            }
        return {"attempted": True, "result": "executed", "batches": batches}

    def _self_declare_closed(self, incident_id: str) -> IncidentCase:
        """Self-declared closure; deliberately bypasses IncidentService invariants.

        This models a monolithic architecture without the aggregate gate: the
        executing agent marks its own incident CLOSED. The baseline IncidentService
        makes this state unreachable (CLOSED requires LEARN + derived RESOLVED).
        """
        case = self.incidents.get(incident_id)
        case.phase = Phase.LEARN
        case.incident_status = IncidentStatus.CLOSED
        case.work_status = WorkStatus.COMPLETED
        return self.incidents.save(case)

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
    dangerous_release_batches = sum(
        1 for item in batches if item["disposition"] == "released" and not item["safe_for_sale"]
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
                "physically succeeded is reported separately as dangerous_release_batches"
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
            "title": "移除 Auditor 独立验证:执行者自证成功",
            "observed": (
                f"{no_auditor['self_declared_closures']}/6 场景被自我宣告关闭"
                f"(基线错误关闭 {full['erroneous_closures']} 起);"
                f"场景 E 在设备恢复但商品处置未闭环时,尝试放行 "
                f"{no_auditor['attempted_unsafe_release_batches']} 个未闭环批次,"
                f"{no_auditor['release_attempts']} 次放行全部被审批层或 "
                f"MCP release_guard(verifier 必须是 Auditor)拦截,"
                f"不安全批次实际放行 {no_auditor['dangerous_release_batches']} 起;"
                f"场景 B 出现 {no_auditor['unsafe_releases']} 起"
                "放行/停售状态不一致(商品已准放行但停售未解除,过度遏制)。"
            ),
            "interpretation": (
                "独立验证是事件管理层的安全前提;没有它,关闭决定与事实脱钩。"
                "MCP 工具层的 release_guard 构成第二道防线,即使管线退化也不放行实物。"
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
    if no_auditor["erroneous_closures"] != 5:
        failures.append("no_auditor must self-close erroneously on 5/6 scenarios")
    if no_auditor["dangerous_release_batches"] != 0:
        failures.append("no_auditor must not physically release any unsafe batch")
    if no_auditor["attempted_unsafe_release_batches"] != 2:
        failures.append("no_auditor must attempt releasing 2 unclosed batches in scenario E")
    if no_auditor["release_denials"] != 5:
        failures.append("no_auditor release attempts must all be denied (5/5)")
    if single["contained"] != 0 or single["denied_write_attempts"] != 6:
        failures.append("single_agent must be denied on all 6 containment writes")
    if single["closed"] != 0:
        failures.append("single_agent must not close any incident")
    if rule["top1_hits"] != 4 or rule["misrouted_workorders"] != 2:
        failures.append("rule_only must hit Top-1 4/6 with 2 misrouted workorders")
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
        "| no_auditor | Auditor 独立验证与聚合门 | 角色保留,Executor 自证并自我宣告关闭 |",
        "| single_agent | 角色身份分离 | 单一身份执行全部步骤 |",
        "| rule_only | 证据关联诊断 | 静态先验诊断,下游遏制/审批/验证保留 |",
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
        ("必需动作缺失", "required_actions_failed"),
        ("放行尝试被拦截", "release_denials"),
        ("试图放行未闭环批次", "attempted_unsafe_release_batches"),
        ("不安全批次实际放行", "dangerous_release_batches"),
        ("放行/停售状态不一致", "unsafe_releases"),
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
            "- 消融结果来自有状态 Mock 与固定 seed,证明架构各层的相对贡献,",
            "  不代表真实门店收益;LLM 延迟/Token/成本对照需真实 AgentTeams 运行时。",
            "- `no_auditor` 的自我宣告关闭是对单体式架构的建模:真实单 Agent 系统没有",
            "  IncidentService 聚合门,关闭决定同样由执行者自己作出。",
            "",
        ]
    )
    if gate["failures"]:
        lines.extend(["## 未通过项", "", *[f"- {item}" for item in gate["failures"]], ""])
    return "\n".join(lines)
