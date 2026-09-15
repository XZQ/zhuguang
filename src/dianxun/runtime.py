"""Authenticated Worker application boundary; no Worker can assert business success."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .context_bus import (
    ContextVersionConflict,
    WorkerAssignment,
    parse_timestamp,
    timestamp,
    utc_now,
)
from .coordination import ContextCoordinator, LeaseExpiredError
from .domain import (
    Action,
    ActionStatus,
    IncidentCase,
    IncidentService,
    IncidentStatus,
    IncidentType,
    Phase,
    Severity,
)
from .recovery import ACTIVE, FAILURES, RecoveryManager, after, digest
from .runtime_context import RuntimeContextBus
from .skills.anomaly_detect import detect_coldchain_event
from .skills.coldchain_risk_assess import coldchain_risk_assess
from .skills.outcome_verify import outcome_verify
from .skills.review_report import review_incident
from .skills.rootcause_drilldown import diagnose_coldchain_hypotheses

# Two containment steps and two release checks implement the five domain phases.
STAGES = {
    "DETECT": "Sentry",
    "CONTAIN": "Executor",
    "DIAGNOSE_DECIDE": "Diagnoser",
    "EXECUTE": "Executor",
    "VERIFY": "Auditor",
    "RELEASE": "Executor",
    "FINAL_VERIFY": "Auditor",
    "LEARN": "Auditor",
}
EXECUTOR_TOOLS = {
    "CONTAIN": {"apply_sales_hold"},
    "EXECUTE": {"create_approval", "query_approval", "create_workorder", "apply_batch_disposition"},
    "RELEASE": {"create_approval", "query_approval", "release_sales_hold", "apply_sales_hold"},
}


@dataclass(frozen=True)
class RuntimePrincipal:
    actor: str
    worker_id: str
    tenant_id: str
    store_id: str


def load_principals(raw: str) -> dict[str, RuntimePrincipal]:
    value = json.loads(raw or "{}")
    if not isinstance(value, dict):
        raise ValueError("Runtime tokens must map to scoped Worker identities")
    principals = {}
    identities = {}
    for token, fields in value.items():
        if (
            not isinstance(fields, dict)
            or set(fields) != {"actor", "worker_id", "tenant_id", "store_id"}
            or not isinstance(token, str)
            or not token
        ):
            raise ValueError("Invalid runtime identity mapping")
        if any(not isinstance(item, str) or not item.strip() for item in fields.values()):
            raise ValueError("Runtime identity fields must be nonempty strings")
        principal = RuntimePrincipal(**fields)
        if principal.actor not in {"Human", "Orchestrator", *STAGES.values()}:
            raise ValueError("Unknown runtime actor")
        previous = identities.setdefault(principal.worker_id, principal)
        if previous != principal:
            raise ValueError("Worker identity has conflicting scopes")
        principals[token] = principal
    return principals


class RuntimeService:
    def __init__(self, mcp, principals, *, clock=utc_now, evidence_clock=None):
        self.mcp = mcp
        self.store = mcp.store
        self.incidents = IncidentService(self.store)
        self.principals = {item.worker_id: item for item in principals}
        self.clock = clock
        # Production evidence freshness uses wall time, never the demo virtual clock.
        self.evidence_clock = evidence_clock or clock
        self.stages = STAGES
        self.recovery = RecoveryManager(self)
        self.scheduler = None

    def call(self, name: str, arguments: dict[str, Any], principal: RuntimePrincipal) -> dict:
        if principal not in self.principals.values():
            raise PermissionError("Unknown Worker identity")
        method = getattr(self, name.removeprefix("runtime_"), None)
        if name not in RUNTIME_SCHEMAS or method is None:
            raise ValueError("Unknown runtime tool")
        from .validation import validate_json

        errors = validate_json(arguments, RUNTIME_SCHEMAS[name])
        if errors:
            raise ValueError("; ".join(errors[:3]))
        # Business changes, receipts and checkpoints share one transaction.
        with self.store.transaction():
            self.recovery.lock_scope(principal)
            if (
                self.scheduler is not None
                and not self.scheduler.healthy()
                and name
                in {
                    "runtime_assign",
                    "runtime_reassign",
                    "runtime_tool",
                    "runtime_emergency",
                    "runtime_complete",
                    "runtime_resume",
                }
            ):
                raise ValueError("Recovery scheduler unavailable; writes suspended")
            return method(principal=principal, **arguments)

    def _context(self, principal, incident_id):
        case = self.incidents.get(incident_id)
        if (case.tenant_id, case.store_id) != (principal.tenant_id, principal.store_id):
            raise PermissionError("Incident is outside Worker scope")
        bus = RuntimeContextBus(self.store, principal.tenant_id)
        context = bus.get(incident_id, allow_expired=True, now=self.clock())
        self.recovery.initialize(context, bus)
        return case, bus, ContextCoordinator(bus, phase_order=tuple(STAGES))

    def open(self, *, principal, incident_id, device_id):
        if principal.actor != "Orchestrator":
            raise PermissionError("Only Orchestrator can open incidents")
        if incident_id.startswith("@runtime-"):
            raise ValueError("Reserved runtime identifier")
        existing = self.store.get_incident(incident_id)
        if existing is not None:
            case, _, _ = self._context(principal, incident_id)
            if case.affected_assets != [device_id]:
                raise ValueError("Incident already has a different device")
            return self.snapshot(principal=principal, incident_id=incident_id)
        with self.store.transaction() as conn:
            row = conn.execute(
                """SELECT d.device_id FROM devices d JOIN stores s ON s.store_id = d.store_id
                   WHERE d.device_id = ? AND s.store_id = ? AND s.tenant_id = ?""",
                (device_id, principal.store_id, principal.tenant_id),
            ).fetchone()
        if row is None:
            raise PermissionError("Device is outside Worker scope")
        case = IncidentCase.create(
            incident_id=incident_id,
            trace_id=f"runtime:{incident_id}",
            tenant_id=principal.tenant_id,
            store_id=principal.store_id,
            incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
            severity=Severity.HIGH,
            trigger="event",
            anchor_time=self.store.now(),
        )
        case.affected_assets = [device_id]
        case.affected_batches = [
            row["batch_id"]
            for row in self.store.list_batches(device_id=device_id, store_id=principal.store_id)
        ]
        if not case.affected_batches:
            raise ValueError("Device has no inventory batches")
        self.incidents.create(case)
        RuntimeContextBus(self.store, principal.tenant_id).create(
            incident_id, case.trace_id, scope={"store_id": principal.store_id}, now=self.clock()
        )
        return self.snapshot(principal=principal, incident_id=incident_id)

    def snapshot(self, *, principal, incident_id):
        case, bus, coordinator = self._context(principal, incident_id)
        held = {
            row["batch_id"]
            for row in self.store.list_sales_holds(incident_id=incident_id)
            if row["status"] == "active"
        }
        context = bus.get(incident_id, allow_expired=True, now=self.clock())
        return {
            "incident": case.to_dict(),
            "context": context.snapshot(),
            "remaining_stages": list(STAGES)[coordinator._checkpoint_prefix_length(context) :],
            "containment_required": sorted(set(case.affected_batches) - held),
        }

    def assign(self, *, principal, incident_id, worker_id, expected_version):
        case, bus, coordinator = self._context(principal, incident_id)
        if principal.actor != "Orchestrator":
            raise PermissionError("Only Orchestrator can assign work")
        remaining = coordinator.resume_plan(incident_id, now=self.clock())
        if not remaining:
            raise ValueError("All stages completed")
        worker = self.principals.get(worker_id)
        if worker is None or (worker.actor, worker.tenant_id, worker.store_id) != (
            STAGES[remaining[0]],
            case.tenant_id,
            case.store_id,
        ):
            raise PermissionError("Worker role or scope does not match the next stage")
        context = bus.get(incident_id, now=self.clock())
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        key = f"{remaining[0]}:{len(context.checkpoints)}:{context.recovery.get('generation', 0)}"
        main_work = [a for a in context.recovery["orchestration"] if a["output_stage"] == key]
        if main_work:
            main = main_work[-1]
            task = WorkerAssignment.from_snapshot(
                {k: v for k, v in main.items() if k != "output_stage"}
            )
            if (
                task.worker != principal.worker_id
                or task.status not in ACTIVE
                or task.is_lease_expired(self.clock())
            ):
                raise LeaseExpiredError("Orchestration work is owned elsewhere or expired")
        assignment, context = self.recovery.dispatch(context, remaining[0], worker_id, coordinator)
        return {
            "assignment": asdict(assignment),
            "context_version": bus.get(incident_id, now=self.clock()).version,
        }

    def _assignment(self, principal, incident_id, assignment_id, expected_version):
        case, bus, coordinator = self._context(principal, incident_id)
        context = bus.get(incident_id, now=self.clock())
        assignment = coordinator._find_assignment(context, assignment_id)
        coordinator._assert_worker(assignment, principal.worker_id)
        if principal.actor != self.recovery.role(assignment.phase):
            raise PermissionError("Wrong actor for assignment")
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        self.recovery.ensure_live(context, assignment)
        if assignment.status not in {"assigned", "running"} or assignment.is_lease_expired(
            self.clock()
        ):
            raise LeaseExpiredError("Assignment is inactive or its lease expired")
        return case, bus, coordinator, assignment

    def heartbeat(self, *, principal, incident_id, assignment_id, expected_version):
        if assignment_id.startswith("main:"):
            return self._main_heartbeat(principal, incident_id, assignment_id, expected_version)
        _, bus, coordinator, _ = self._assignment(
            principal, incident_id, assignment_id, expected_version
        )
        assignment = coordinator.heartbeat(
            incident_id,
            assignment_id,
            principal.worker_id,
            expected_version=expected_version,
            now=self.clock(),
        )
        return {
            "assignment": asdict(assignment),
            "context_version": bus.get(incident_id, now=self.clock()).version,
        }

    def reassign(self, *, principal, incident_id, assignment_id, expected_version):
        _, bus, coordinator = self._context(principal, incident_id)
        if principal.actor != "Orchestrator":
            raise PermissionError("Only Orchestrator can reassign")
        current = bus.get(incident_id, now=self.clock())
        if current.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        predecessor = coordinator._find_assignment(current, assignment_id)
        # The public compatibility entry point invokes the same bounded supervisor.
        # It cannot bypass backoff, capacity, reconciliation or retry budgets.
        if predecessor.status in ACTIVE and not predecessor.is_lease_expired(self.clock()):
            raise ValueError("Assignment is still active")
        self.recovery.scan_context(principal, incident_id)
        current = bus.get(incident_id, now=self.clock())
        successor = next(
            (a for a in current.assignments if a.predecessor_assignment_id == assignment_id), None
        )
        return {
            "assignment": asdict(successor) if successor else None,
            "recovery": current.recovery["phases"][predecessor.phase],
            "context_version": current.version,
        }

    def tool(self, *, principal, incident_id, assignment_id, expected_version, tool, arguments):
        case, bus, _, assignment = self._assignment(
            principal, incident_id, assignment_id, expected_version
        )
        allowed = (
            {"apply_sales_hold"}
            if assignment.phase == "EMERGENCY_CONTAIN"
            else (EXECUTOR_TOOLS.get(assignment.phase, set()))
        )
        if tool not in allowed:
            raise PermissionError("Tool is not allowed for this assignment")
        if arguments.get("incident_id", incident_id) != incident_id:
            raise PermissionError("Cannot change incident scope")
        context = bus.get(incident_id, now=self.clock())
        mutating = tool != "query_approval"
        if assignment.phase == "EMERGENCY_CONTAIN":
            authorized = context.recovery["phases"][assignment.phase]["batch_ids"]
            if not set(arguments.get("batch_ids", [])) <= set(authorized):
                raise PermissionError("Emergency batch scope exceeded")
        operation_id = digest([tool, arguments.get("action_id")])
        previous = context.recovery["operations"].get(operation_id)
        if mutating and previous and previous["key"] != arguments.get("idempotency_key"):
            raise ValueError("Retry must retain the original operation idempotency key")
        if tool == "create_workorder":
            generation = context.recovery.get("generation", 0)
            for operation in context.recovery["operations"].values():
                if (
                    operation["tool"] == tool
                    and operation.get("generation", 0) == generation
                    and operation.get("device_id") == arguments.get("device_id")
                    and operation["action_id"] != arguments.get("action_id")
                ):
                    raise ValueError("Reuse the recorded workorder action and idempotency key")
        from .mcp.server import tool_call

        result = tool_call(
            tool,
            {**arguments, "incident_id": incident_id, "runtime_trace_id": case.trace_id},
            actor=principal.actor,
            service=self.mcp,
        )
        if result.get("isError"):
            return result
        # Deadline check after synchronous adapter work fences late effects too: local
        # adapters share this transaction, so rejection rolls back their writes.
        self.recovery.ensure_live(context, assignment)
        # The aggregate receives persisted receipts, never caller-supplied action status.
        case = self.incidents.get(incident_id)
        case.actions = [
            Action(
                action_id=row["action_id"],
                action_type=row["action_type"],
                tool_name=row["tool_name"],
                target=case.store_id,
                idempotency_key=row["request"].get("idempotency_key", row["action_id"]),
                approval_id=row.get("approval_id"),
                status=ActionStatus(row["status"]),
                request=row["request"],
                response=row.get("response"),
            )
            for row in self.store.list_actions(incident_id=incident_id)
        ]
        self.incidents.save(case)
        if mutating:
            context.recovery["operations"][operation_id] = {
                "tool": tool,
                "key": arguments["idempotency_key"],
                "action_id": arguments["action_id"],
                "phase": assignment.phase,
                "generation": context.recovery.get("generation", 0),
                "device_id": arguments.get("device_id"),
            }
            durable = next(a for a in context.assignments if a.assignment_id == assignment_id)
            self.recovery.progress(context, durable)
            bus.commit(context, now=self.clock())
        result["context_version"] = context.version
        return result

    def complete(self, *, principal, incident_id, assignment_id, expected_version):
        _, existing_bus, existing_coordinator = self._context(principal, incident_id)
        existing = existing_bus.get(incident_id, now=self.clock())
        previous = existing_coordinator._find_assignment(existing, assignment_id)
        existing_coordinator._assert_worker(previous, principal.worker_id)
        if previous.status == "succeeded":
            if previous.phase == "EMERGENCY_CONTAIN":
                return {
                    "completed": True,
                    "replayed": True,
                    "context_version": existing.version,
                    "output": existing.recovery["phases"][previous.phase]["output"],
                }
            checkpoint = existing.checkpoints[previous.phase]
            return {
                "completed": True,
                "replayed": True,
                "output": checkpoint.output,
                "output_available": checkpoint.output is not None,
                "context_version": existing.version,
            }
        case, bus, coordinator, assignment = self._assignment(
            principal, incident_id, assignment_id, expected_version
        )
        stage = assignment.phase
        if stage == "EMERGENCY_CONTAIN":
            return self._complete_emergency(principal, case, bus, assignment)
        if stage in {"DETECT", "DIAGNOSE_DECIDE", "VERIFY", "FINAL_VERIFY", "LEARN"}:
            readings = sorted(
                self.store.list_device_readings(device_id=case.affected_assets[0]),
                key=lambda row: parse_timestamp(row["observed_at"]),
            )
            latest = readings[-1] if readings else None
            if (
                not latest
                or latest["quality"] != "good"
                or not 0
                <= (self.evidence_clock() - parse_timestamp(latest["observed_at"])).total_seconds()
                <= 300
            ):
                result = self.fail(
                    principal=principal,
                    incident_id=incident_id,
                    assignment_id=assignment_id,
                    expected_version=expected_version,
                    reason="stale_evidence",
                )
                return {
                    **result,
                    "completed": False,
                    "output": {"partial": True, "reason": "stale_evidence"},
                }
        common = dict(service=self.mcp, incident_id=incident_id, trace_id=case.trace_id)
        if stage == "DETECT":
            output = detect_coldchain_event(
                **common,
                store_id=case.store_id,
                device_id=case.affected_assets[0],
                alarm_max_c=float(
                    self.mcp.policy.policy["temperature"]["refrigerated_max_celsius"]
                ),
            )
            passed = output["detected"] and not output.get("partial")
        elif stage == "DIAGNOSE_DECIDE":
            output = diagnose_coldchain_hypotheses(
                **common, store_id=case.store_id, device_id=case.affected_assets[0]
            )
            passed = output["quality"] != "partial"
            device = self.mcp.query_device_context(
                device_id=case.affected_assets[0], incident_id=incident_id, actor="Diagnoser"
            )
            batches = self.mcp.query_inventory_batches(
                batch_ids=case.affected_batches, incident_id=incident_id, actor="Diagnoser"
            )
            passed = passed and all(
                response["ok"] and not response["partial"] for response in (device, batches)
            )
            if passed:
                output["risk_assessment"] = coldchain_risk_assess(
                    incident_id=incident_id,
                    device_series=device["data"]["devices"][0]["temperature_series"],
                    affected_batches=batches["data"]["batches"],
                    policy=self.mcp.policy.policy,
                    trace_id=case.trace_id,
                    manual_measurements=self.store.list_manual_evidence(incident_id=incident_id),
                    assessed_at=self.store.now(),
                )
                self.incidents.replace_hypotheses(incident_id, output["hypotheses"])
                self.incidents.transition_phase(
                    incident_id,
                    Phase.EXECUTE,
                    actor="Orchestrator",
                    reason="Worker diagnosis accepted",
                )
            output = {**output, "hypotheses": [asdict(h) for h in output["hypotheses"]]}
        elif stage in {"VERIFY", "FINAL_VERIFY"}:
            output = outcome_verify(
                **common, incidents=self.incidents, policy=self.mcp.policy.policy
            )
            passed = (
                output["result"]
                in ({"verified", "release_ready"} if stage == "VERIFY" else {"verified"})
                and not output["partial_tools"]
            )
            if passed and stage == "FINAL_VERIFY":
                self.incidents.transition_phase(
                    incident_id,
                    Phase.LEARN,
                    actor="Orchestrator",
                    reason="Final independent verification passed",
                )
        elif stage == "LEARN":
            # Recheck immediately before learning/closing; an old checkpoint grants no authority.
            verification = outcome_verify(
                **common, incidents=self.incidents, policy=self.mcp.policy.policy
            )
            passed = verification["result"] == "verified"
            output = verification
            if passed:
                output = review_incident(
                    incident=self.incidents.get(incident_id).to_dict(),
                    verification=verification,
                    scenario={"scenario_id": "runtime"},
                    trace_id=case.trace_id,
                )
                self.incidents.close_after_learning(incident_id)
        else:
            current = self.incidents.recompute(incident_id)
            holds = self.store.list_sales_holds(incident_id=incident_id)
            if stage == "CONTAIN":
                passed = current.incident_status == IncidentStatus.CONTAINED
                if passed:
                    self.incidents.transition_phase(
                        incident_id,
                        Phase.DIAGNOSE_DECIDE,
                        actor="Orchestrator",
                        reason="Goods contained",
                    )
            elif stage == "EXECUTE":
                approvals = self.store.list_approvals(incident_id=incident_id)
                passed = (
                    bool(current.actions)
                    and all(action.status == ActionStatus.COMPLETED for action in current.actions)
                    and all(row["status"] == "approved" for row in approvals)
                )
                if passed:
                    self.incidents.transition_phase(
                        incident_id, Phase.VERIFY, actor="Orchestrator", reason="Receipts recorded"
                    )
            else:
                batches = self.store.list_batches(batch_ids=case.affected_batches)
                released = {row["batch_id"] for row in batches if row["disposition"] == "released"}
                passed = not any(
                    row["status"] == "active" and row["batch_id"] in released for row in holds
                )
            output = {"result": "completed" if passed else "blocked"}
        for evidence in output.get("evidence", []):
            self.incidents.append_evidence_ref(incident_id, evidence["evidence_id"])
        self.recovery.ensure_live(bus.get(incident_id, now=self.clock()), assignment)
        if passed:
            coordinator.complete(
                incident_id,
                assignment_id,
                principal.worker_id,
                evidence_refs=self.incidents.get(incident_id).evidence_refs,
                output_ref=f"assignment:{assignment_id}",
                output=output,
                expected_version=expected_version,
                now=self.clock(),
            )
            context = bus.get(incident_id, now=self.clock())
            context.recovery["phases"][stage]["state"] = "completed"
            bus.commit(context, now=self.clock())
        return {
            "completed": passed,
            "output": output,
            "context_version": bus.get(incident_id, now=self.clock()).version,
        }

    def poll(self, *, principal):
        if principal.actor == "Human":
            raise PermissionError("Human operators do not execute Worker assignments")
        self.recovery.present(principal)
        work = []
        for context in self.recovery.contexts(principal):
            if context.trigger == "worker_registry" or context.is_expired(self.clock()):
                continue
            for assignment in self.recovery.assignments(context):
                if (
                    assignment.worker == principal.worker_id
                    and assignment.status in ACTIVE
                    and not assignment.is_lease_expired(self.clock())
                ):
                    work.append(
                        {
                            "incident_id": context.task_id,
                            "assignment": asdict(assignment),
                            "context_version": context.version,
                        }
                    )
        return {"assignments": work, "poll_after_seconds": 10}

    def _main_heartbeat(self, principal, incident_id, assignment_id, expected_version):
        _, bus, _ = self._context(principal, incident_id)
        context = bus.get(incident_id, now=self.clock())
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        item = next(
            (a for a in context.recovery["orchestration"] if a["assignment_id"] == assignment_id),
            None,
        )
        if not item or principal.actor != "Orchestrator" or item["worker"] != principal.worker_id:
            raise PermissionError("Not the assigned orchestration Worker")
        assignment = WorkerAssignment.from_snapshot(
            {k: v for k, v in item.items() if k != "output_stage"}
        )
        if assignment.status not in ACTIVE or assignment.is_lease_expired(self.clock()):
            raise LeaseExpiredError("Orchestration assignment expired")
        item["lease_expires_at"] = timestamp(
            min(parse_timestamp(item["hard_deadline"]), parse_timestamp(after(self.clock(), 60)))
        )
        item["last_heartbeat_at"] = timestamp(self.clock())
        item["status"] = "running"
        bus.commit(context, now=self.clock())
        return {"assignment": item, "context_version": context.version}

    def progress(self, *, principal, incident_id, assignment_id, expected_version):
        _, bus, _, _ = self._assignment(principal, incident_id, assignment_id, expected_version)
        context = bus.get(incident_id, now=self.clock())
        assignment = next(a for a in context.assignments if a.assignment_id == assignment_id)
        changed = self.recovery.progress(context, assignment)
        if changed:
            bus.commit(context, now=self.clock())
        return {"progress_accepted": changed, "context_version": context.version}

    def fail(self, *, principal, incident_id, assignment_id, expected_version, reason):
        _, bus, _, _ = self._assignment(principal, incident_id, assignment_id, expected_version)
        context = bus.get(incident_id, now=self.clock())
        assignment = next(a for a in context.assignments if a.assignment_id == assignment_id)
        self.recovery.fail(context, assignment, reason)
        bus.commit(context, now=self.clock())
        return {
            "recovery": context.recovery["phases"][assignment.phase],
            "context_version": context.version,
        }

    def wait(self, *, principal, incident_id, assignment_id, expected_version, kind, reference):
        _, bus, _, _ = self._assignment(principal, incident_id, assignment_id, expected_version)
        context = bus.get(incident_id, now=self.clock())
        assignment = next(a for a in context.assignments if a.assignment_id == assignment_id)
        self.recovery.wait(context, assignment, kind, reference)
        bus.commit(context, now=self.clock())
        return {
            "recovery": context.recovery["phases"][assignment.phase],
            "context_version": context.version,
        }

    def emergency(self, *, principal, incident_id, expected_version):
        import os

        if principal.actor != "Orchestrator":
            raise PermissionError("Only Orchestrator can request emergency containment")
        if os.environ.get("DIANXUN_EMERGENCY_CONTAINMENT") != "1":
            raise PermissionError("Emergency containment requires deployment authorization")
        case, bus, _ = self._context(principal, incident_id)
        context = bus.get(incident_id, now=self.clock())
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        if context.coordination_status != "active" or "DETECT" in context.checkpoints:
            raise ValueError("Use the regular containment workflow after detection")
        if "EMERGENCY_CONTAIN" in context.recovery["phases"]:
            return self.snapshot(principal=principal, incident_id=incident_id)
        # Minimal conservative authorization: two GOOD, recent samples over the
        # existing alarm threshold, device identity and inventory scope from the DB.
        readings = sorted(
            self.store.list_device_readings(device_id=case.affected_assets[0]),
            key=lambda row: parse_timestamp(row["observed_at"]),
        )
        # Duplicate observations at the same instant are one sample.
        readings = list({parse_timestamp(r["observed_at"]): r for r in readings}.values())[-2:]
        now = self.evidence_clock()
        threshold = float(self.mcp.policy.policy["temperature"]["refrigerated_max_celsius"])
        if len(readings) != 2 or not all(
            r["quality"] == "good"
            and float(r["temp_c"]) > threshold
            and 0 <= (now - parse_timestamp(r["observed_at"])).total_seconds() <= 300
            for r in readings
        ):
            raise ValueError("Fresh independent risk evidence required")
        batches = self.store.list_batches(device_id=case.affected_assets[0], store_id=case.store_id)
        if {b["batch_id"] for b in batches} != set(case.affected_batches):
            raise ValueError("Inventory scope changed; manual reconciliation required")
        phase = self.recovery.phase(context, "EMERGENCY_CONTAIN", queued_at=timestamp(self.clock()))
        phase.update(
            {
                "batch_ids": list(case.affected_batches),
                "evidence": readings,
                "authorized_by": principal.worker_id,
                "authorization": "deployment_policy_and_fresh_temperature",
            }
        )
        bus.commit(context, now=self.clock())
        return self.snapshot(principal=principal, incident_id=incident_id)

    def _complete_emergency(self, principal, case, bus, assignment):
        context = bus.get(case.incident_id, now=self.clock())
        phase = context.recovery["phases"][assignment.phase]
        held = {
            h["batch_id"]
            for h in self.store.list_sales_holds(incident_id=case.incident_id)
            if h["status"] == "active"
        }
        passed = set(phase["batch_ids"]) <= held
        output = {"result": "contained" if passed else "blocked", "batch_ids": sorted(held)}
        if passed:
            self.recovery.ensure_live(context, assignment)
            durable = next(
                a for a in context.assignments if a.assignment_id == assignment.assignment_id
            )
            durable.status = "succeeded"
            phase.update({"state": "completed", "output": output})
            bus.commit(context, now=self.clock())
        return {"completed": passed, "output": output, "context_version": context.version}

    def resume(self, *, principal, incident_id, expected_version, stage, reason):
        if principal.actor != "Human":
            raise PermissionError("An independently bound Human operator is required")
        _, bus, _ = self._context(principal, incident_id)
        context = bus.get(incident_id, now=self.clock())
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        phase = context.recovery["phases"].get(stage)
        if not phase or phase["state"] != "manual_intervention":
            raise ValueError("Stage is not awaiting manual intervention")
        if parse_timestamp(phase["deadline"]) <= self.clock() or phase.get("manual_retry_grants"):
            raise ValueError("Original budget or one-time manual recovery allowance exhausted")
        if not self.recovery.reconcile(context, stage):
            raise ValueError("Unknown operation outcome must be reconciled first")
        phase.update(
            {
                "state": "queued",
                "next_run_at": timestamp(self.clock()),
                "manual_retry_grants": 1,
                "resumed_by": principal.worker_id,
                "resume_reason": reason,
                "resumed_at": timestamp(self.clock()),
            }
        )
        bus.commit(context, now=self.clock())
        return self.snapshot(principal=principal, incident_id=incident_id)

    def notifications(self, *, principal, incident_id):
        if principal.actor != "Human":
            raise PermissionError("An independently bound notification operator is required")
        _, bus, _ = self._context(principal, incident_id)
        context = bus.get(incident_id, allow_expired=True, now=self.clock())
        claimed = []
        changed = False
        for item in context.recovery["outbox"]:
            if (
                item["status"] not in {"delivered", "delivery_failed"}
                and parse_timestamp(item["next_delivery_at"]) <= self.clock()
            ):
                changed = True
                if item["attempts"] >= 5:
                    item["status"] = "delivery_failed"
                    continue
                item.update(
                    {
                        "status": "delivering",
                        "attempts": item["attempts"] + 1,
                        "claimed_by": principal.worker_id,
                        "next_delivery_at": after(self.clock(), 60),
                    }
                )
                claimed.append(dict(item))
                if len(claimed) == 10:
                    break
        if changed:
            bus.commit(context, allow_expired=True, now=self.clock())
        return {"notifications": claimed}

    def notification_result(
        self, *, principal, incident_id, notification_id, attempt, delivered, receipt
    ):
        if principal.actor != "Human":
            raise PermissionError("An independently bound notification operator is required")
        _, bus, _ = self._context(principal, incident_id)
        context = bus.get(incident_id, allow_expired=True, now=self.clock())
        item = next((n for n in context.recovery["outbox"] if n["id"] == notification_id), None)
        if not item or (item.get("claimed_by"), item["attempts"], item["status"]) != (
            principal.worker_id,
            attempt,
            "delivering",
        ):
            raise PermissionError("Stale or unowned notification delivery lease")
        if parse_timestamp(item["next_delivery_at"]) <= self.clock():
            raise LeaseExpiredError("Notification delivery lease expired")
        item.update(
            {
                "status": "delivered"
                if delivered
                else ("delivery_failed" if attempt >= 5 else "pending"),
                "receipt": receipt,
                "next_delivery_at": after(self.clock(), min(300, 10 * 2**attempt)),
            }
        )
        bus.commit(context, allow_expired=True, now=self.clock())
        return {"notification": item}

    def reopen(self, *, principal, incident_id, expected_version):
        case, bus, coordinator = self._context(principal, incident_id)
        if principal.actor != "Orchestrator":
            raise PermissionError("Only Orchestrator can reopen work")
        context = bus.get(incident_id, now=self.clock())
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        remaining = coordinator.resume_plan(incident_id, now=self.clock())
        if (
            case.phase not in {Phase.VERIFY, Phase.LEARN}
            or not remaining
            or remaining[0] not in {"VERIFY", "FINAL_VERIFY", "LEARN"}
        ):
            raise ValueError("Recovery is only allowed at an unfinished independent audit")
        verification = outcome_verify(
            service=self.mcp,
            incident_id=incident_id,
            trace_id=case.trace_id,
            incidents=self.incidents,
            policy=self.mcp.policy.policy,
        )
        if verification["partial_tools"] or verification["result"] in {"verified", "release_ready"}:
            raise ValueError("Recovery requires a complete, failed independent verification")
        reason = "Independent audit requires rework: " + ", ".join(
            verification["failed_conditions"]
        )
        self.incidents.reopen(incident_id, reason=reason, recontain=True)
        coordinator.restart_from(
            incident_id,
            "CONTAIN",
            reason=reason,
            expected_version=expected_version,
            now=self.clock(),
        )
        context = bus.get(incident_id, now=self.clock())
        context.recovery["generation"] = context.recovery.get("generation", 0) + 1
        for stage, state in context.recovery["phases"].items():
            if stage in STAGES and stage != "DETECT":
                state["state"] = "queued"
        bus.commit(context, now=self.clock())
        return self.snapshot(principal=principal, incident_id=incident_id)


def schema(properties, required):
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_TEXT = {"type": "string", "minLength": 1, "maxLength": 256}
_INCIDENT = {"incident_id": _TEXT}
_LEASE = {
    **_INCIDENT,
    "assignment_id": _TEXT,
    "expected_version": {"type": "integer", "minimum": 1},
}
RUNTIME_SCHEMAS = {
    "runtime_poll": schema({}, []),
    "runtime_emergency": schema(
        {**_INCIDENT, "expected_version": {"type": "integer", "minimum": 1}},
        ["incident_id", "expected_version"],
    ),
    "runtime_progress": schema(_LEASE, list(_LEASE)),
    "runtime_fail": schema({**_LEASE, "reason": {"enum": sorted(FAILURES)}}, [*_LEASE, "reason"]),
    "runtime_wait": schema(
        {**_LEASE, "kind": {"enum": ["approval", "repair"]}, "reference": _TEXT},
        [*_LEASE, "kind", "reference"],
    ),
    "runtime_resume": schema(
        {
            **_INCIDENT,
            "expected_version": {"type": "integer", "minimum": 1},
            "stage": {"enum": [*STAGES, "EMERGENCY_CONTAIN"]},
            "reason": _TEXT,
        },
        ["incident_id", "expected_version", "stage", "reason"],
    ),
    "runtime_notifications": schema(_INCIDENT, list(_INCIDENT)),
    "runtime_notification_result": schema(
        {
            **_INCIDENT,
            "notification_id": _TEXT,
            "attempt": {"type": "integer", "minimum": 1},
            "delivered": {"type": "boolean"},
            "receipt": _TEXT,
        },
        ["incident_id", "notification_id", "attempt", "delivered", "receipt"],
    ),
    "runtime_reopen": schema(
        {**_INCIDENT, "expected_version": {"type": "integer", "minimum": 1}},
        ["incident_id", "expected_version"],
    ),
    "runtime_open": schema({**_INCIDENT, "device_id": _TEXT}, ["incident_id", "device_id"]),
    "runtime_snapshot": schema(_INCIDENT, list(_INCIDENT)),
    "runtime_assign": schema(
        {**_INCIDENT, "worker_id": _TEXT, "expected_version": {"type": "integer", "minimum": 1}},
        ["incident_id", "worker_id", "expected_version"],
    ),
    **{
        f"runtime_{name}": schema(_LEASE, list(_LEASE))
        for name in ("heartbeat", "reassign", "complete")
    },
    "runtime_tool": schema(
        {
            **_LEASE,
            "tool": {"enum": sorted(set().union(*EXECUTOR_TOOLS.values()))},
            "arguments": {"type": "object"},
        },
        [*_LEASE, "tool", "arguments"],
    ),
}
