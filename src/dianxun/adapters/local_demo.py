"""Deterministic five-phase local adapter for cold-chain scenarios."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .. import trace
from ..domain import (
    Action,
    ActionStatus,
    Decision,
    Evidence,
    IncidentCase,
    IncidentService,
    IncidentStatus,
    IncidentType,
    Phase,
    PolicyEngine,
    Severity,
    WorkStatus,
)
from ..knowledge import KnowledgeService, embedding_provider_from_env
from ..mcp.p0 import DEFAULT_POLICY_PATH, DEFAULT_SEED_PATH, MCPService
from ..scenarios import ScenarioEngine
from ..skills import (
    coldchain_risk_assess,
    detect_coldchain_event,
    diagnose_coldchain_hypotheses,
    dispatch_stateful_workorder,
    outcome_verify,
    review_incident,
)
from ..state import StateStoreProtocol, create_state_store


class LocalDemoAdapter:
    """Run the same domain and MCP core without claiming AgentTeams evidence."""

    def __init__(
        self,
        *,
        db_path: str | Path,
        scenario_path: str | Path,
        policy_path: str | Path = DEFAULT_POLICY_PATH,
        seed_path: str | Path = DEFAULT_SEED_PATH,
        trace_db_path: str | Path | None = None,
        enable_rag: bool | None = None,
    ) -> None:
        self.store: StateStoreProtocol = create_state_store(db_path)
        if trace_db_path is not None:
            self.trace_db_path = Path(trace_db_path)
        elif self.store.backend_name == "sqlite":
            self.trace_db_path = Path(db_path).with_suffix(".trace.db")
        else:
            self.trace_db_path = Path(
                os.environ.get("DIANXUN_TRACE_DB", "demo/state/polardb.trace.db")
            ).resolve()
        self.policy = PolicyEngine(policy_path)
        rag_enabled = (
            os.environ.get("DIANXUN_RAG_ENABLED") == "1" if enable_rag is None else enable_rag
        )
        self.knowledge = (
            KnowledgeService(self.store, embedding_provider_from_env()) if rag_enabled else None
        )
        self.mcp = MCPService(
            self.store,
            self.policy,
            auto_initialize_seed=seed_path,
            knowledge=self.knowledge,
        )
        self.scenario = ScenarioEngine(self.store, scenario_path, service=self.mcp)
        self.incidents = IncidentService(self.store)

    def run(self) -> dict[str, Any]:
        with trace.use_database(self.trace_db_path):
            return self._run()

    def _run(self) -> dict[str, Any]:
        self.scenario.reset()
        definition = self.scenario.scenario
        ground_truth = definition["ground_truth"]
        workflow = definition.get("workflow", {})
        incident_id = ground_truth.get("incident_id") or _incident_id(definition["scenario_id"])
        trace_id = f"tr_{definition['scenario_id'].replace('-', '_')}"
        trace.clear_trace(trace_id)
        store_id = ground_truth["store_id"]
        device_id = ground_truth["device_id"]
        policy = self.policy.policy
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
            if not detection["detected"]:
                result = {
                    "scenario_id": definition["scenario_id"],
                    "result": "no_incident",
                    "detection": detection,
                    "acceptance": {
                        "passed": False,
                        "mismatches": ["expected incident not detected"],
                    },
                }
                root.output = result
                return result

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
            contained = self.incidents.recompute(incident_id)
            if contained.incident_status is not IncidentStatus.CONTAINED:
                raise RuntimeError("Cold-chain incident was not contained before diagnosis")

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
                final_case = self.incidents.recompute(incident_id)
                wakeup = repair.get("deadline")
                wait_status = (
                    WorkStatus.WAITING_EXTERNAL
                    if repair["result"] == "timeout"
                    else WorkStatus.BLOCKED
                )
                final_case = self.incidents.set_work_status(
                    incident_id,
                    wait_status,
                    owner=("regional_manager" if repair["result"] == "timeout" else "Orchestrator"),
                    next_wakeup_at=wakeup,
                    reason=(
                        "repair approval did not authorize execution; containment remains active; "
                        "timeout escalation assigned to regional manager"
                        if repair["result"] == "timeout"
                        else "repair execution failed; containment remains active"
                    ),
                )
                result = self._result(
                    phase_outputs=phase_outputs,
                    verification=None,
                    review=None,
                    case=final_case,
                )
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
                reason="execution receipts available; delegate independent requery",
            )
            verification = self._verify(incident_id, trace_id, policy)
            attempts = [_verification_summary(verification)]

            if verification["result"] == "release_ready":
                self.incidents.transition_phase(
                    incident_id,
                    Phase.EXECUTE,
                    actor="Orchestrator",
                    reason="Auditor release guard passed; delegate approved hold release",
                )
                with trace.span(
                    "executor-release",
                    "agent",
                    trace_id,
                    input={"incident_id": incident_id},
                ) as release_span:
                    release = self._execute_sales_hold_release(
                        incident_id=incident_id,
                        trace_id=trace_id,
                        workflow=workflow,
                    )
                    release_span.output = {"result": release["result"]}
                phase_outputs["EXECUTE"]["sales_hold_release"] = release
                if release["result"] != "executed":
                    final_case = self.incidents.recompute(incident_id)
                    pending = self.store.list_approvals(incident_id=incident_id)
                    pending = [item for item in pending if item["status"] == "pending"]
                    final_case = self.incidents.set_work_status(
                        incident_id,
                        WorkStatus.WAITING_APPROVAL if pending else WorkStatus.BLOCKED,
                        owner="Orchestrator",
                        next_wakeup_at=release.get("deadline"),
                        reason="controlled hold release not authorized; containment remains active",
                    )
                    verification["attempts"] = attempts
                    phase_outputs["VERIFY"] = verification
                    result = self._result(
                        phase_outputs=phase_outputs,
                        verification=verification,
                        review=None,
                        case=final_case,
                    )
                    root.output = {"result": result["result"], "acceptance": result["acceptance"]}
                    return result
                self.incidents.transition_phase(
                    incident_id,
                    Phase.VERIFY,
                    actor="Orchestrator",
                    reason="sales holds released; Auditor must independently requery final state",
                )
                verification = self._verify(incident_id, trace_id, policy)
                attempts.append(_verification_summary(verification))
                verification["attempts"] = attempts
            phase_outputs["VERIFY"] = verification

            if verification["result"] == "verified":
                resolved = self.incidents.recompute(incident_id)
                if resolved.incident_status is not IncidentStatus.RESOLVED:
                    raise RuntimeError("Verification passed but aggregate incident did not resolve")
                self.incidents.transition_phase(
                    incident_id,
                    Phase.LEARN,
                    actor="Orchestrator",
                    reason="independent verification passed",
                )
                learned_case = self.incidents.get(incident_id)
                review = review_incident(
                    incident=learned_case.to_dict(),
                    verification=verification,
                    scenario=definition,
                    trace_id=trace_id,
                    knowledge=self.knowledge,
                )
                phase_outputs["LEARN"] = review
                final_case = self.incidents.close_after_learning(incident_id)
            else:
                self.incidents.reopen(
                    incident_id,
                    reason=(
                        f"Auditor result {verification['result']}: "
                        f"{verification['failed_conditions']}"
                    ),
                )
                self.incidents.transition_phase(
                    incident_id,
                    Phase.EXECUTE,
                    actor="Orchestrator",
                    reason="keep containment and route unresolved goods branch",
                )
                pending = self.store.list_approvals(incident_id=incident_id)
                pending = [item for item in pending if item["status"] == "pending"]
                next_wakeup = min((item["deadline"] for item in pending), default=None)
                final_case = self.incidents.set_work_status(
                    incident_id,
                    WorkStatus.WAITING_APPROVAL if pending else WorkStatus.BLOCKED,
                    owner="Orchestrator",
                    next_wakeup_at=next_wakeup,
                    reason="Auditor refused safe closure; wait for controlled goods disposition",
                )
                review = None

            result = self._result(
                phase_outputs=phase_outputs,
                verification=verification,
                review=review,
                case=final_case,
            )
            root.output = {"result": result["result"], "acceptance": result["acceptance"]}
            return result

    def _detect(
        self,
        *,
        trace_id: str,
        incident_id: str,
        store_id: str,
        device_id: str,
    ) -> dict[str, Any]:
        with trace.span(
            "sentry",
            "agent",
            trace_id,
            input={"store_id": store_id, "device_id": device_id},
        ) as sp:
            result = detect_coldchain_event(
                service=self.mcp,
                incident_id=incident_id,
                store_id=store_id,
                device_id=device_id,
                trace_id=trace_id,
                alarm_max_c=float(self.policy.policy["temperature"]["refrigerated_max_celsius"]),
            )
            sp.output = {"detected": result["detected"], "severity": result["severity"]}
            return result

    def _contain(self, incident_id: str, trace_id: str) -> dict[str, Any]:
        case = self.incidents.get(incident_id)
        action_id = f"{incident_id}:hold"
        action = Action(
            action_id=action_id,
            action_type="apply_sales_hold",
            tool_name="apply_sales_hold",
            target=case.store_id,
            idempotency_key=f"{incident_id}:hold:v1",
            status=ActionStatus.EXECUTING,
            request={"batch_ids": case.affected_batches, "reason": "coldchain containment"},
            rollback_or_compensation={"type": "controlled_release_only", "automatic": False},
            started_at=self.store.now(),
        )
        self.incidents.append_action(incident_id, action)
        with trace.span("executor-containment", "agent", trace_id, input=action.request) as sp:
            with trace.span("apply_sales_hold", "mcp", trace_id, input=action.request) as tool_span:
                response = self.mcp.apply_sales_hold(
                    incident_id=incident_id,
                    action_id=action_id,
                    store_id=case.store_id,
                    batch_ids=case.affected_batches,
                    reason="coldchain temperature risk containment",
                    idempotency_key=action.idempotency_key,
                    actor="Executor",
                )
                tool_span.output = {
                    "ok": response["ok"],
                    "request_id": response["request_id"],
                    "audit_ref": response["audit_ref"],
                }
            self.incidents.update_action(
                incident_id,
                action_id,
                status=ActionStatus.COMPLETED if response["ok"] else ActionStatus.FAILED,
                response=response,
            )
            sp.output = {"ok": response["ok"], "audit_ref": response["audit_ref"]}
        if not response["ok"]:
            raise RuntimeError(f"Containment failed: {response['error']}")
        return response

    def _diagnose(
        self,
        *,
        incident_id: str,
        trace_id: str,
        store_id: str,
        device_id: str,
    ) -> dict[str, Any]:
        with trace.span("diagnoser", "agent", trace_id, input={"incident_id": incident_id}) as sp:
            diagnosis = diagnose_coldchain_hypotheses(
                service=self.mcp,
                incident_id=incident_id,
                store_id=store_id,
                device_id=device_id,
                trace_id=trace_id,
                knowledge=self.knowledge,
            )
            self._append_evidence(incident_id, diagnosis["evidence"])
            self.incidents.replace_hypotheses(incident_id, diagnosis["hypotheses"])
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
            self.incidents.append_decision(
                incident_id,
                Decision(
                    decision_id=f"{incident_id}:decision:v1",
                    policy_id=f"{self.policy.policy['policy_id']}:{self.policy.policy['policy_version']}",
                    selected_hypothesis_ids=[top.hypothesis_id],
                    proposed_actions=["create_workorder", *dispositions],
                    risk_level="L2",
                    approval_required=True,
                    approvers=["store_manager", "food_safety_owner"],
                    decision_reason=(
                        f"top hypothesis {top.label} plus batch-specific exposure assessment"
                    ),
                    evidence_ids=list(case.evidence_refs),
                    created_by="Diagnoser",
                ),
            )
            result = {
                "hypotheses": [asdict(item) for item in diagnosis["hypotheses"]],
                "evidence": diagnosis["evidence"],
                "quality": diagnosis["quality"],
                "data_quality": diagnosis.get("data_quality", {}),
                "rag": diagnosis["rag"],
                "risk_assessment": assessment,
            }
            sp.output = {
                "top_hypothesis": top.label,
                "confidence": top.confidence,
                "batch_recommendations": dispositions,
            }
            return result

    def _execute_repair(
        self,
        *,
        incident_id: str,
        trace_id: str,
        store_id: str,
        device_id: str,
        fault: str,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        action_id = f"{incident_id}:repair"
        budget = float(workflow.get("repair_budget", 2500.0))
        timeout = int(workflow.get("repair_approval_timeout_minutes", 2))
        policy_decision = self.policy.evaluate(
            actor="Executor",
            action_type="create_workorder",
            amount=budget,
        )
        approval_id: str | None = None
        approval_row: dict[str, Any] | None = None
        approval_response: dict[str, Any] | None = None
        action_status = ActionStatus.EXECUTING
        if policy_decision.approval_required:
            approval_response = self.mcp.create_approval(
                incident_id=incident_id,
                action_id=action_id,
                subject=f"repair {device_id}",
                requested_action_type="create_workorder",
                amount=budget,
                timeout_minutes=timeout,
                idempotency_key=f"{action_id}:approval:v1",
                actor="Executor",
            )
            if not approval_response["ok"]:
                return {"result": "failed", "error": approval_response["error"]}
            approval_id = approval_response["data"]["approval_id"]
            action_status = ActionStatus.PENDING
        self.incidents.append_action(
            incident_id,
            Action(
                action_id=action_id,
                action_type="create_workorder",
                tool_name="create_workorder",
                target=device_id,
                idempotency_key=f"{action_id}:execute:v1",
                approval_id=approval_id,
                status=action_status,
                request={
                    "store_id": store_id,
                    "device_id": device_id,
                    "fault": fault,
                    "budget": budget,
                },
                response=approval_response,
                rollback_or_compensation={"type": "cancel_or_reassign_workorder"},
                started_at=self.store.now(),
            ),
        )
        if approval_id is not None:
            decision_minute = int(workflow.get("repair_approval_decision_minute", timeout))
            self._advance_to(decision_minute)
            self._append_manual_evidence_refs(incident_id)
            queried = self.mcp.query_approval(
                approval_id=approval_id,
                incident_id=incident_id,
                action_id=action_id,
                actor="Orchestrator",
            )
            approval_row = queried["data"]["approvals"][0]
            status = approval_row["status"]
            if status != "approved":
                mapped = {
                    "pending": ActionStatus.PENDING,
                    "rejected": ActionStatus.REJECTED,
                    "timeout": ActionStatus.TIMEOUT,
                }[status]
                self.incidents.update_action(
                    incident_id,
                    action_id,
                    status=mapped,
                    response=queried,
                )
                return {
                    "result": status,
                    "approval": approval_row,
                    "deadline": approval_row["deadline"],
                }
            self.incidents.update_action(
                incident_id,
                action_id,
                status=ActionStatus.APPROVED,
                response=queried,
            )
        dispatched = dispatch_stateful_workorder(
            service=self.mcp,
            incident_id=incident_id,
            action_id=action_id,
            store_id=store_id,
            device_id=device_id,
            fault=fault,
            budget=budget,
            approval_id=approval_id,
            idempotency_key=f"{action_id}:execute:v1",
            trace_id=trace_id,
        )
        self.incidents.update_action(
            incident_id,
            action_id,
            status=ActionStatus.COMPLETED if dispatched["ok"] else ActionStatus.FAILED,
            response=dispatched,
        )
        return {
            "result": "executed" if dispatched["ok"] else "failed",
            "approval": approval_row,
            "workorder": dispatched,
        }

    def _execute_batch_dispositions(
        self,
        *,
        incident_id: str,
        trace_id: str,
        assessment: dict[str, Any],
        workflow: dict[str, Any],
    ) -> list[dict[str, Any]]:
        pending: list[dict[str, Any]] = []
        for item in assessment["exposure_assessment"]:
            batch_id = item["batch_id"]
            disposition = item["recommendation"]
            action_id = f"{incident_id}:batch:{batch_id}"
            approval_response = self.mcp.create_approval(
                incident_id=incident_id,
                action_id=action_id,
                subject=f"{disposition} {batch_id}",
                requested_action_type="apply_batch_disposition",
                disposition=disposition,
                timeout_minutes=int(workflow.get("disposition_approval_timeout_minutes", 30)),
                idempotency_key=f"{action_id}:approval:v1",
                actor="Executor",
            )
            if not approval_response["ok"]:
                raise RuntimeError(approval_response["error"])
            approval = approval_response["data"]
            self.incidents.append_action(
                incident_id,
                Action(
                    action_id=action_id,
                    action_type=f"apply_batch_disposition:{disposition}",
                    tool_name="apply_batch_disposition",
                    target=batch_id,
                    idempotency_key=f"{action_id}:execute:v1",
                    approval_id=approval["approval_id"],
                    status=ActionStatus.PENDING,
                    request={"batch_ids": [batch_id], "disposition": disposition},
                    response=approval_response,
                    rollback_or_compensation={
                        "type": "manual_correction",
                        "automatic": False,
                    },
                    started_at=self.store.now(),
                ),
            )
            pending.append(
                {
                    "action_id": action_id,
                    "batch_id": batch_id,
                    "disposition": disposition,
                    "approval_id": approval["approval_id"],
                }
            )

        decision_minute = workflow.get("disposition_approval_decision_minute")
        if decision_minute is not None:
            self._advance_to(int(decision_minute))
        results: list[dict[str, Any]] = []
        for item in pending:
            queried = self.mcp.query_approval(
                approval_id=item["approval_id"],
                incident_id=incident_id,
                action_id=item["action_id"],
                actor="Orchestrator",
            )
            approval = queried["data"]["approvals"][0]
            if approval["status"] != "approved":
                status = {
                    "pending": ActionStatus.PENDING,
                    "rejected": ActionStatus.REJECTED,
                    "timeout": ActionStatus.TIMEOUT,
                }[approval["status"]]
                self.incidents.update_action(
                    incident_id,
                    item["action_id"],
                    status=status,
                    response=queried,
                )
                results.append({**item, "result": approval["status"]})
                continue
            self.incidents.update_action(
                incident_id,
                item["action_id"],
                status=ActionStatus.APPROVED,
                response=queried,
            )
            with trace.span(
                "apply_batch_disposition",
                "mcp",
                trace_id,
                input={"batch_id": item["batch_id"], "disposition": item["disposition"]},
            ) as tool_span:
                response = self.mcp.apply_batch_disposition(
                    incident_id=incident_id,
                    action_id=item["action_id"],
                    batch_ids=[item["batch_id"]],
                    disposition=item["disposition"],
                    approval_id=item["approval_id"],
                    idempotency_key=f"{item['action_id']}:execute:v1",
                    actor="Executor",
                )
                tool_span.output = {
                    "ok": response["ok"],
                    "request_id": response["request_id"],
                    "audit_ref": response["audit_ref"],
                }
            self.incidents.update_action(
                incident_id,
                item["action_id"],
                status=ActionStatus.COMPLETED if response["ok"] else ActionStatus.FAILED,
                response=response,
            )
            results.append({**item, "result": "executed" if response["ok"] else "failed"})
        return results

    def _execute_sales_hold_release(
        self,
        *,
        incident_id: str,
        trace_id: str,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        case = self.incidents.recompute(incident_id)
        released_batches = {
            batch_id
            for batch_id, disposition in case.batch_dispositions.items()
            if disposition.value == "released"
        }
        holds = [
            item
            for item in self.store.list_sales_holds(incident_id=incident_id, status="active")
            if item["batch_id"] in released_batches
        ]
        if not holds:
            return {"result": "failed", "error": "no active holds for released batches"}

        action_id = f"{incident_id}:release-holds"
        timeout = int(workflow.get("release_approval_timeout_minutes", 30))
        approval_response = self.mcp.create_approval(
            incident_id=incident_id,
            action_id=action_id,
            subject=f"release sales holds for {incident_id}",
            requested_action_type="release_sales_hold",
            timeout_minutes=timeout,
            idempotency_key=f"{action_id}:approval:v1",
            actor="Executor",
        )
        if not approval_response["ok"]:
            return {"result": "failed", "error": approval_response["error"]}
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
            mapped = {
                "pending": ActionStatus.PENDING,
                "rejected": ActionStatus.REJECTED,
                "timeout": ActionStatus.TIMEOUT,
            }[row["status"]]
            self.incidents.update_action(incident_id, action_id, status=mapped, response=queried)
            return {"result": row["status"], "approval": row, "deadline": row["deadline"]}

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
            tool_span.output = {
                "ok": response["ok"],
                "request_id": response["request_id"],
                "audit_ref": response["audit_ref"],
            }
        self.incidents.update_action(
            incident_id,
            action_id,
            status=ActionStatus.COMPLETED if response["ok"] else ActionStatus.FAILED,
            response=response,
        )
        return {
            "result": "executed" if response["ok"] else "failed",
            "approval": row,
            "release": response,
        }

    def _verify(
        self,
        incident_id: str,
        trace_id: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        with trace.span(
            "auditor",
            "agent",
            trace_id,
            input={"incident_id": incident_id},
        ) as agent_span:
            verification = outcome_verify(
                incidents=self.incidents,
                service=self.mcp,
                incident_id=incident_id,
                policy=policy,
                trace_id=trace_id,
            )
            agent_span.output = {
                "result": verification["result"],
                "failed_conditions": verification["failed_conditions"],
            }
            return verification

    def _append_evidence(self, incident_id: str, items: list[dict[str, Any]]) -> None:
        for item in items:
            self.incidents.append_evidence(incident_id, Evidence(**item))

    def _append_manual_evidence_refs(self, incident_id: str) -> None:
        for item in self.store.list_manual_evidence(incident_id=incident_id):
            self.incidents.append_evidence_ref(incident_id, item["evidence_id"])

    def _advance_to(self, minute: int) -> None:
        current = self.scenario.elapsed_minutes()
        if minute > current:
            self.scenario.advance(minutes=minute - current)
        else:
            self.scenario.apply_due_events()

    def _result(
        self,
        *,
        phase_outputs: dict[str, Any],
        verification: dict[str, Any] | None,
        review: dict[str, Any] | None,
        case: IncidentCase,
    ) -> dict[str, Any]:
        acceptance = _acceptance(
            self.scenario.scenario,
            case,
            verification,
            approvals=self.store.list_approvals(incident_id=case.incident_id),
        )
        if case.incident_status is IncidentStatus.CLOSED:
            result = "closed"
        elif verification is not None:
            result = verification["result"]
        else:
            result = case.work_status.value.lower()
        return {
            "scenario_id": self.scenario.scenario["scenario_id"],
            "result": result,
            "trace_id": case.trace_id,
            "incident": case.to_dict(),
            "phases": phase_outputs,
            "verification": verification,
            "review": review,
            "acceptance": acceptance,
            "evidence_level": {
                "local_demo": "implemented",
                "external_systems": "stateful_mock",
                "agentteams": "not_proven_by_local_adapter",
            },
        }


def _incident_id(scenario_id: str) -> str:
    return "INC-" + scenario_id.upper().replace("-", "_")


def _verification_summary(verification: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": verification["result"],
        "failed_conditions": list(verification["failed_conditions"]),
        "partial_tools": list(verification.get("partial_tools", [])),
    }


def _acceptance(
    scenario: dict[str, Any],
    case: IncidentCase,
    verification: dict[str, Any] | None,
    *,
    approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = scenario["expected_final_state"]
    mismatches: list[str] = []
    scalar_values = {
        "incident_status": case.incident_status.value,
        "phase": case.phase.value,
        "work_status": case.work_status.value,
        "verification_result": verification["result"] if verification else None,
    }
    for key, actual in scalar_values.items():
        if key in expected and expected[key] != actual:
            mismatches.append(f"{key}: expected {expected[key]}, got {actual}")
    if "device_state" in expected:
        actual_states = set(case.asset_states.values())
        if actual_states != {expected["device_state"]}:
            mismatches.append(
                f"device_state: expected {expected['device_state']}, got {sorted(actual_states)}"
            )
    if "batch_states" in expected:
        actual = set(item.value for item in case.batch_dispositions.values())
        allowed = set(expected["batch_states"])
        if not actual or not actual <= allowed:
            mismatches.append(
                f"batch_states: expected subset of {sorted(allowed)}, got {sorted(actual)}"
            )
    if "approval_status" in expected:
        statuses = {item["status"] for item in approvals}
        if expected["approval_status"] not in statuses:
            mismatches.append(
                f"approval_status: expected {expected['approval_status']}, got {sorted(statuses)}"
            )
    return {"passed": not mismatches, "mismatches": mismatches}
