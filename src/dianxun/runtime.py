"""Authenticated Worker application boundary; no Worker can assert business success."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .context_bus import ContextVersionConflict, utc_now
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
        if principal.actor not in {"Orchestrator", *STAGES.values()}:
            raise ValueError("Unknown runtime actor")
        previous = identities.setdefault(principal.worker_id, principal)
        if previous != principal:
            raise ValueError("Worker identity has conflicting scopes")
        principals[token] = principal
    return principals


class RuntimeService:
    def __init__(self, mcp, principals, *, clock=utc_now):
        self.mcp = mcp
        self.store = mcp.store
        self.incidents = IncidentService(self.store)
        self.principals = {item.worker_id: item for item in principals}
        self.clock = clock

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
            return method(principal=principal, **arguments)

    def _context(self, principal, incident_id):
        case = self.incidents.get(incident_id)
        if (case.tenant_id, case.store_id) != (principal.tenant_id, principal.store_id):
            raise PermissionError("Incident is outside Worker scope")
        bus = RuntimeContextBus(self.store, principal.tenant_id)
        return case, bus, ContextCoordinator(bus, phase_order=tuple(STAGES))

    def open(self, *, principal, incident_id, device_id):
        if principal.actor != "Orchestrator":
            raise PermissionError("Only Orchestrator can open incidents")
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
        return {
            "incident": case.to_dict(),
            "context": bus.get(incident_id, now=self.clock()).snapshot(),
            "remaining_stages": coordinator.resume_plan(incident_id, now=self.clock()),
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
        assignment = coordinator.assign(
            incident_id,
            remaining[0],
            worker_id,
            expected_version=expected_version,
            now=self.clock(),
        )
        return {
            "assignment": asdict(assignment),
            "context_version": bus.get(incident_id, now=self.clock()).version,
        }

    def _assignment(self, principal, incident_id, assignment_id, expected_version):
        case, bus, coordinator = self._context(principal, incident_id)
        context = bus.get(incident_id, now=self.clock())
        assignment = coordinator._find_assignment(context, assignment_id)
        coordinator._assert_worker(assignment, principal.worker_id)
        if principal.actor != STAGES[assignment.phase]:
            raise PermissionError("Wrong actor for assignment")
        if context.version != expected_version:
            raise ContextVersionConflict("Reload the current context version")
        if assignment.status not in {"assigned", "running"} or assignment.is_lease_expired(
            self.clock()
        ):
            raise LeaseExpiredError("Assignment is inactive or its lease expired")
        return case, bus, coordinator, assignment

    def heartbeat(self, *, principal, incident_id, assignment_id, expected_version):
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
        predecessor = coordinator._find_assignment(current, assignment_id)
        successor = coordinator.reassign_expired(
            incident_id,
            assignment_id,
            predecessor.worker,
            expected_version=expected_version,
            now=self.clock(),
        )
        return {
            "assignment": asdict(successor),
            "context_version": bus.get(incident_id, now=self.clock()).version,
        }

    def tool(self, *, principal, incident_id, assignment_id, expected_version, tool, arguments):
        case, _, _, assignment = self._assignment(
            principal, incident_id, assignment_id, expected_version
        )
        if tool not in EXECUTOR_TOOLS.get(assignment.phase, set()):
            raise PermissionError("Tool is not allowed for this assignment")
        if arguments.get("incident_id", incident_id) != incident_id:
            raise PermissionError("Cannot change incident scope")
        from .mcp.server import tool_call

        result = tool_call(
            tool,
            {**arguments, "incident_id": incident_id, "runtime_trace_id": case.trace_id},
            actor=principal.actor,
            service=self.mcp,
        )
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
        return result

    def complete(self, *, principal, incident_id, assignment_id, expected_version):
        _, existing_bus, existing_coordinator = self._context(principal, incident_id)
        existing = existing_bus.get(incident_id, now=self.clock())
        previous = existing_coordinator._find_assignment(existing, assignment_id)
        existing_coordinator._assert_worker(previous, principal.worker_id)
        if previous.status == "succeeded":
            return {"completed": True, "replayed": True, "context_version": existing.version}
        case, bus, coordinator, assignment = self._assignment(
            principal, incident_id, assignment_id, expected_version
        )
        stage = assignment.phase
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
        if passed:
            coordinator.complete(
                incident_id,
                assignment_id,
                principal.worker_id,
                evidence_refs=self.incidents.get(incident_id).evidence_refs,
                output_ref=f"incident:{incident_id}:{stage}",
                expected_version=expected_version,
                now=self.clock(),
            )
        return {
            "completed": passed,
            "output": output,
            "context_version": bus.get(incident_id, now=self.clock()).version,
        }


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
