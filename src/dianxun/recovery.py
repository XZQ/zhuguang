"""Durable, scoped supervision. No model/network calls execute in the scanner.

All mutations run under RuntimeService's scope lock and the existing state
transaction. JSON metadata lives in runtime_contexts; no second business store.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import timedelta

from .context_bus import WorkerAssignment, parse_timestamp, timestamp
from .coordination import ContextCoordinator, LeaseExpiredError
from .runtime_context import RuntimeContextBus

ACTIVE = {"assigned", "running"}
RETRYABLE = {"transient", "rate_limited", "heartbeat_timeout", "hard_timeout", "progress_timeout"}
FAILURES = RETRYABLE | {"invalid_input", "forbidden", "stale_evidence", "unknown_outcome"}
POLICY = {
    "version": 1,
    "lease_seconds": 60,
    "presence_seconds": 90,
    "max_attempts": 3,
    "max_dispatches": 32,
    "backoff_seconds": 5,
    "cooldown_seconds": 30,
    "capacity": 1,
    "roles": {
        "Orchestrator": {"hard": 60, "progress": 30, "total": 180},
        "Sentry": {"hard": 180, "progress": 90, "total": 900},
        "Diagnoser": {"hard": 300, "progress": 120, "total": 1800},
        "Executor": {"hard": 300, "progress": 120, "total": 21600},
        "Auditor": {"hard": 300, "progress": 120, "total": 1800},
    },
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def after(now, seconds):
    return timestamp(now + timedelta(seconds=seconds))


class RecoveryManager:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store
        self.metric_snapshot = {}

    @property
    def now(self):
        return self.runtime.clock()

    def lock_scope(self, principal):
        # Serializes capacity decisions across incidents as well as replica scans.
        # SQLite BEGIN IMMEDIATE provides the corresponding database write lock.
        with self.store.transaction() as conn:
            row = conn.execute(
                "SELECT store_id FROM stores WHERE tenant_id = ? AND store_id = ?",
                (principal.tenant_id, principal.store_id),
            ).fetchone()
            if row is None:
                raise PermissionError("Unknown runtime scope")
            if self.store.backend_name == "postgresql":
                # No UPDATE grant on master data is needed for a scope mutex.
                key = int(digest([principal.tenant_id, principal.store_id])[:15], 16)
                conn.execute("SELECT pg_advisory_xact_lock(?)", (key,))

    def contexts(self, principal):
        with self.store.transaction() as conn:
            rows = conn.execute(
                "SELECT task_id FROM runtime_contexts WHERE tenant_id = ? AND store_id = ? "
                "ORDER BY task_id",
                (principal.tenant_id, principal.store_id),
            ).fetchall()
        bus = RuntimeContextBus(self.store, principal.tenant_id)
        return [bus.get(row["task_id"], allow_expired=True, now=self.now) for row in rows]

    def registry(self, principal):
        bus = RuntimeContextBus(self.store, principal.tenant_id)
        key = "@runtime-workers:" + principal.store_id
        try:
            context = bus.get(key, allow_expired=True, now=self.now)
        except KeyError:
            context = bus.create(
                key,
                key,
                trigger="worker_registry",
                scope={"store_id": principal.store_id},
                ttl_seconds=None,
                now=self.now,
            )
        return bus, context

    def present(self, principal):
        bus, registry = self.registry(principal)
        state = registry.recovery.setdefault(principal.worker_id, {})
        state["last_seen_at"] = timestamp(self.now)
        bus.commit(registry, now=self.now)

    def initialize(self, context, bus):
        if context.recovery:
            if context.recovery.get("policy", {}).get("version") != POLICY["version"]:
                raise ValueError("Unsupported recovery policy; compatible reader required")
            return
        context.recovery = {
            "policy": json.loads(json.dumps(POLICY)),
            "phases": {},
            "operations": {},
            "orchestration": [],
            "outbox": [],
        }
        with self.store.transaction() as conn:
            receipts = conn.execute(
                "SELECT i.idempotency_key, i.tool_name, a.action_id, a.request_json "
                "FROM idempotency i "
                "JOIN audit_log a ON a.audit_id = i.audit_id "
                "WHERE a.incident_id = ? AND a.tenant_id = ? AND a.actor = 'Executor'",
                (context.task_id, context.tenant_id),
            ).fetchall()
        for receipt in receipts:
            request = receipt["request_json"]
            request = json.loads(request) if isinstance(request, str) else request
            context.recovery["operations"][digest([receipt["tool_name"], receipt["action_id"]])] = {
                "tool": receipt["tool_name"],
                "key": receipt["idempotency_key"],
                "action_id": receipt["action_id"],
                "phase": "legacy",
                "device_id": request.get("device_id"),
            }
        # An upgrade never grants a fresh lifetime to an old assignment.
        for assignment in context.assignments:
            phase = self.phase(context, assignment.phase, queued_at=assignment.created_at)
            self.bound(context, assignment, start=parse_timestamp(assignment.created_at))
            phase["dispatches"] = max(phase["dispatches"], assignment.attempt)
        bus.commit(context, now=self.now, allow_expired=True)

    def role(self, stage):
        from .runtime import STAGES

        return {"ORCHESTRATE": "Orchestrator", "EMERGENCY_CONTAIN": "Executor"}.get(
            stage, STAGES.get(stage)
        )

    def phase(self, context, stage, *, queued_at=None):
        phases = context.recovery["phases"]
        if stage not in phases:
            role = self.role(stage)
            if queued_at is None:
                queued_at = max(
                    [context.created_at] + [c.completed_at for c in context.checkpoints.values()]
                )
            deadline = after(
                parse_timestamp(queued_at), context.recovery["policy"]["roles"][role]["total"]
            )
            if context.expires_at:
                deadline = timestamp(
                    min(parse_timestamp(deadline), parse_timestamp(context.expires_at))
                )
            phases[stage] = {
                "queued_at": queued_at,
                "deadline": deadline,
                "failures": 0,
                "dispatches": 0,
                "state": "queued",
                "next_run_at": queued_at,
            }
        return phases[stage]

    def bound(self, context, assignment, *, start=None):
        start = start or self.now
        policy = context.recovery["policy"]["roles"][self.role(assignment.phase)]
        assignment.hard_deadline = timestamp(
            min(
                start + timedelta(seconds=policy["hard"]),
                parse_timestamp(self.phase(context, assignment.phase)["deadline"]),
            )
        )
        assignment.last_progress_at = timestamp(start)
        assignment.progress_deadline = after(start, policy["progress"])

    def ensure_live(self, context, assignment):
        phase = self.phase(context, assignment.phase)
        if phase["state"] in {"manual_intervention", "waiting", "reconciling"}:
            raise LeaseExpiredError("Work is suspended; inspect recovery state")
        if parse_timestamp(phase["deadline"]) <= self.now or context.is_expired(self.now):
            raise LeaseExpiredError("Recovery budget exhausted")
        if assignment.status not in ACTIVE or assignment.is_lease_expired(self.now):
            raise LeaseExpiredError("Assignment is inactive or deadline expired")

    def choose(self, context, stage, *, preferred=None, avoid=None):
        from .runtime import RuntimePrincipal

        scope = RuntimePrincipal("Orchestrator", "", context.tenant_id, context.scope["store_id"])
        _, registry = self.registry(scope)
        policy = context.recovery["policy"]
        busy = {}
        for other in self.contexts(scope):
            for assignment in self.assignments(other):
                if assignment.status in ACTIVE and not assignment.is_lease_expired(self.now):
                    busy[assignment.worker] = busy.get(assignment.worker, 0) + 1
        candidates = []
        for worker in self.runtime.principals.values():
            if (worker.actor, worker.tenant_id, worker.store_id) != (
                self.role(stage),
                context.tenant_id,
                context.scope["store_id"],
            ):
                continue
            health = registry.recovery.get(worker.worker_id, {})
            if (
                not health.get("last_seen_at")
                or (self.now - parse_timestamp(health["last_seen_at"])).total_seconds()
                >= policy["presence_seconds"]
            ):
                continue
            if (
                health.get("cooldown_until")
                and parse_timestamp(health["cooldown_until"]) > self.now
            ):
                continue
            if busy.get(worker.worker_id, 0) >= policy["capacity"]:
                continue
            candidates.append(worker.worker_id)
        if preferred:
            return preferred if preferred in candidates else None
        return next(iter(sorted(candidates, key=lambda w: (w == avoid, w))), None)

    @staticmethod
    def assignments(context):
        return context.assignments + [
            WorkerAssignment.from_snapshot({k: v for k, v in a.items() if k != "output_stage"})
            for a in context.recovery.get("orchestration", [])
        ]

    def alert(self, context, stage, reason, *, suspend=True):
        phase = self.phase(context, stage)
        if suspend:
            phase["state"] = "manual_intervention"
            for assignment in context.assignments:
                if assignment.phase == stage and assignment.status in ACTIVE | {"waiting"}:
                    assignment.status, assignment.error = "expired", reason
                    assignment.updated_at = timestamp(self.now)
        phase["reason"] = reason
        key = digest(
            [context.task_id, stage, reason, phase["queued_at"], phase.get("output_stage")]
        )[:24]
        if not any(n["id"] == key for n in context.recovery["outbox"]):
            context.recovery["outbox"].append(
                {
                    "id": key,
                    "phase": stage,
                    "reason": reason,
                    "owner": "store_manager",
                    "created_at": timestamp(self.now),
                    "deadline": after(self.now, 900),
                    "status": "pending",
                    "attempts": 0,
                    "next_delivery_at": timestamp(self.now),
                }
            )

    def dispatch(self, context, stage, worker, coordinator, *, predecessor=None):
        phase = self.phase(context, stage)
        if phase["state"] == "manual_intervention":
            raise ValueError("Manual intervention required")
        if parse_timestamp(phase["deadline"]) <= self.now:
            raise ValueError("Recovery budget exhausted")
        if parse_timestamp(phase["next_run_at"]) > self.now:
            raise ValueError("Retry backoff is still active")
        if phase["dispatches"] >= context.recovery["policy"]["max_dispatches"]:
            raise ValueError("Dispatch budget exhausted")
        if not self.choose(context, stage, preferred=worker):
            raise ValueError("Worker must poll and have healthy available capacity")
        if predecessor is None and stage != "EMERGENCY_CONTAIN":
            assignment = coordinator.assign(
                context.task_id, stage, worker, expected_version=context.version, now=self.now
            )
            context = coordinator.bus.get(context.task_id, now=self.now)
            phase = self.phase(context, stage)
            assignment = coordinator._find_assignment(context, assignment.assignment_id)
        else:
            attempt = predecessor.attempt + 1 if predecessor else 1
            assignment = WorkerAssignment(
                assignment_id=coordinator._assignment_id(
                    context.task_id,
                    stage,
                    attempt,
                    predecessor.assignment_id if predecessor else None,
                ),
                phase=stage,
                worker=worker,
                attempt=attempt,
                predecessor_assignment_id=predecessor.assignment_id if predecessor else None,
                created_at=timestamp(self.now),
                updated_at=timestamp(self.now),
                lease_expires_at=after(self.now, context.recovery["policy"]["lease_seconds"]),
            )
            context.assignments.append(assignment)
        phase["dispatches"] += 1
        phase["state"] = "running"
        phase.pop("wait", None)
        self.bound(context, assignment)
        assignment.progress_fingerprint = self.fingerprint(context)
        phase["seen_progress"] = self.progress_tokens(context)
        for main in context.recovery["orchestration"]:
            if main["status"] in ACTIVE and stage != "EMERGENCY_CONTAIN":
                main["status"] = "succeeded"
                main["updated_at"] = timestamp(self.now)
        coordinator.bus.commit(context, now=self.now)
        return assignment, context

    def fingerprint(self, context):
        return digest(self.progress_tokens(context))

    def progress_tokens(self, context):
        case = self.runtime.incidents.get(context.task_id)
        # Read receipts, not query audit IDs (a repeated query is not progress).
        sources = {
            "actions": self.store.list_actions(incident_id=context.task_id),
            "manual": self.store.list_manual_evidence(incident_id=context.task_id),
            "approvals": self.store.list_approvals(incident_id=context.task_id),
            "workorders": self.store.list_workorders(incident_id=context.task_id),
            "readings": [
                r
                for d in case.affected_assets
                for r in self.store.list_device_readings(device_id=d)
                if r.get("quality") == "good"
                and 0
                <= (
                    self.runtime.evidence_clock() - parse_timestamp(r["observed_at"])
                ).total_seconds()
                <= 300
            ],
        }
        return sorted({digest([source, row]) for source, rows in sources.items() for row in rows})

    def progress(self, context, assignment):
        tokens = set(self.progress_tokens(context))
        phase = self.phase(context, assignment.phase)
        seen = set(phase.get("seen_progress", tokens))
        if not tokens - seen:
            return False
        phase["seen_progress"] = sorted(seen | tokens)
        assignment.progress_fingerprint = digest(sorted(tokens))
        assignment.last_progress_at = timestamp(self.now)
        seconds = context.recovery["policy"]["roles"][self.role(assignment.phase)]["progress"]
        assignment.progress_deadline = after(self.now, seconds)
        return True

    def fail(self, context, assignment, reason):
        assignment.status, assignment.error = "expired", reason
        assignment.updated_at = timestamp(self.now)
        phase = self.phase(context, assignment.phase)
        phase["failures"] += 1
        phase["reason"] = reason
        if reason not in RETRYABLE or phase["failures"] >= (
            context.recovery["policy"]["max_attempts"] + phase.get("manual_retry_grants", 0)
        ):
            self.alert(
                context,
                assignment.phase,
                reason if reason not in RETRYABLE else "attempts_exhausted",
            )
            return
        # Deterministic jitter survives restarts, bounds every persisted retry schedule.
        jitter = int(digest(assignment.assignment_id)[:4], 16) % 5
        delay = (
            min(60, context.recovery["policy"]["backoff_seconds"] * 2 ** (phase["failures"] - 1))
            + jitter
        )
        phase["next_run_at"] = after(self.now, delay)
        phase["state"] = "retry_wait"
        from .runtime import RuntimePrincipal

        scope = RuntimePrincipal("Orchestrator", "", context.tenant_id, context.scope["store_id"])
        bus, registry = self.registry(scope)
        registry.recovery.setdefault(assignment.worker, {})["cooldown_until"] = after(
            self.now, context.recovery["policy"]["cooldown_seconds"]
        )
        bus.commit(registry, now=self.now)

    def reconcile(self, context, stage):
        if self.role(stage) != "Executor":
            return True
        # Current adapters are transactional local writes. Missing receipts in imported
        # operation records are UNKNOWN, never assumed safe to resend to an external API.
        with self.store.transaction() as conn:
            for operation in context.recovery["operations"].values():
                result = self.store.idempotent_result(conn, idempotency_key=operation["key"])
                if not result or result["tool_name"] != operation["tool"]:
                    self.phase(context, stage)["state"] = "reconciling"
                    self.alert(context, stage, "unknown_outcome")
                    return False
        self.phase(context, stage)["reconciled_at"] = timestamp(self.now)
        return True

    def wait(self, context, assignment, kind, reference):
        if self.role(assignment.phase) != "Executor" or assignment.phase == "EMERGENCY_CONTAIN":
            raise PermissionError("Only regular Executor tasks can wait for business receipts")
        method, key, pending = (
            (self.store.list_approvals, "approval_id", {"pending"})
            if kind == "approval"
            else (
                self.store.list_workorders,
                "workorder_id",
                {"created", "assigned", "in_progress"},
            )
        )
        rows = method(incident_id=context.task_id)
        row = next((r for r in rows if r[key] == reference), None)
        if row is None or row["status"] not in pending:
            raise ValueError("Waiting requires a pending receipt in this incident")
        phase = self.phase(context, assignment.phase)
        # Convert the business clock's deadline to a fixed runtime duration once.
        seconds = (
            (parse_timestamp(row["deadline"]) - self.runtime.evidence_clock()).total_seconds()
            if kind == "approval"
            else 14400
        )
        deadline = timestamp(
            min(self.now + timedelta(seconds=max(0, seconds)), parse_timestamp(phase["deadline"]))
        )
        phase["wait"] = {
            "kind": kind,
            "reference": reference,
            "deadline": deadline,
            "owner": row.get("approvers", [row.get("assignee") or "store_manager"]),
        }
        phase["state"] = "waiting"
        assignment.status = "waiting"

    def wake(self, context, stage, assignment):
        phase = self.phase(context, stage)
        wait = phase["wait"]
        if parse_timestamp(wait["deadline"]) <= self.now:
            self.alert(context, stage, "business_wait_timeout")
            return False
        approval = wait["kind"] == "approval"
        rows = (self.store.list_approvals if approval else self.store.list_workorders)(
            incident_id=context.task_id
        )
        key = "approval_id" if approval else "workorder_id"
        row = next((r for r in rows if r[key] == wait["reference"]), None)
        if row is None or row["status"] in {"rejected", "timeout", "cancelled", "failed"}:
            self.alert(context, stage, "business_wait_rejected")
            return False
        if row["status"] not in ({"approved"} if approval else {"done", "closed"}):
            return False
        assignment.status = "expired"
        assignment.error = "business_wait_resumed"
        phase["state"], phase["next_run_at"] = "queued", timestamp(self.now)
        return True

    def supervise_main(self, context, stage):
        """One separate orchestration work item per next business stage.

        After the main worker times out, deterministic dispatch may continue. It
        chooses only the checkpoint-derived next stage; no business judgment.
        """
        items = context.recovery["orchestration"]
        phase = self.phase(context, "ORCHESTRATE")
        key = f"{stage}:{len(context.checkpoints)}:{context.recovery.get('generation', 0)}"
        if phase.get("output_stage") != key:
            queued = self.phase(context, stage)["queued_at"]
            phase.update(
                {
                    "output_stage": key,
                    "queued_at": queued,
                    "deadline": after(
                        parse_timestamp(queued),
                        context.recovery["policy"]["roles"]["Orchestrator"]["total"],
                    ),
                }
            )
        matching = [a for a in items if a.get("output_stage") == key]
        if parse_timestamp(phase["deadline"]) <= self.now:
            for item in matching:
                if item["status"] in ACTIVE:
                    item.update(
                        {
                            "status": "expired",
                            "error": "budget_exhausted",
                            "updated_at": timestamp(self.now),
                        }
                    )
            self.alert(context, "ORCHESTRATE", "budget_exhausted", suspend=False)
            return True
        previous_id = None
        avoid = None
        if matching:
            latest = matching[-1]
            fields = {k: v for k, v in latest.items() if k != "output_stage"}
            assignment = WorkerAssignment.from_snapshot(fields)
            if assignment.status in ACTIVE and not assignment.is_lease_expired(self.now):
                return False
            if assignment.status in ACTIVE:
                latest["status"] = "expired"
                latest["error"] = assignment.expiry_reason(self.now)
                self.alert(context, "ORCHESTRATE", latest["error"], suspend=False)
            if len(matching) >= context.recovery["policy"]["max_attempts"]:
                self.alert(context, "ORCHESTRATE", "attempts_exhausted", suspend=False)
                return True
            previous_id, avoid = assignment.assignment_id, assignment.worker
        worker = self.choose(context, "ORCHESTRATE", avoid=avoid)
        if worker == avoid:
            worker = None
        if not worker:
            self.alert(context, "ORCHESTRATE", "capacity_unavailable", suspend=False)
            return True
        # Each handoff has its own bounded main task, outside the eight business steps.
        assignment = WorkerAssignment(
            assignment_id="main:" + digest([context.task_id, key, len(matching)])[:24],
            phase="ORCHESTRATE",
            worker=worker,
            attempt=len(matching) + 1,
            predecessor_assignment_id=previous_id,
            lease_expires_at=after(self.now, 60),
            created_at=timestamp(self.now),
            updated_at=timestamp(self.now),
            hard_deadline=timestamp(
                min(parse_timestamp(phase["deadline"]), parse_timestamp(after(self.now, 60)))
            ),
            progress_deadline=after(self.now, 30),
        )
        items.append({**asdict(assignment), "output_stage": key})
        phase["state"] = "running"
        return False

    def scan_context(self, principal, task_id):
        bus = RuntimeContextBus(self.store, principal.tenant_id)
        context = bus.get(task_id, allow_expired=True, now=self.now)
        self.initialize(context, bus)
        before = context.snapshot()
        if context.coordination_status != "active":
            return
        coordinator = ContextCoordinator(bus, phase_order=tuple(self.runtime.stages))
        remaining = [s for s in self.runtime.stages if s not in context.checkpoints]
        stages = remaining[:1]
        if "EMERGENCY_CONTAIN" in context.recovery["phases"]:
            stages.insert(0, "EMERGENCY_CONTAIN")
        for stage in stages:
            phase = self.phase(context, stage)
            if phase["state"] in {"manual_intervention", "completed"}:
                continue
            if context.is_expired(self.now) or parse_timestamp(phase["deadline"]) <= self.now:
                self.alert(context, stage, "budget_exhausted")
                continue
            assignments = [a for a in context.assignments if a.phase == stage]
            latest = assignments[-1] if assignments else None
            if latest and latest.status == "waiting":
                if not self.wake(context, stage, latest):
                    continue
            if latest and latest.status in ACTIVE:
                reason = latest.expiry_reason(self.now)
                if not reason:
                    continue
                self.fail(context, latest, reason)
            if phase["state"] == "manual_intervention":
                continue
            if parse_timestamp(phase["next_run_at"]) > self.now:
                continue
            if phase["dispatches"] >= context.recovery["policy"]["max_dispatches"]:
                self.alert(context, stage, "dispatches_exhausted")
                continue
            if not self.reconcile(context, stage):
                continue
            if not latest and stage != "EMERGENCY_CONTAIN":
                if not self.supervise_main(context, stage):
                    continue
            worker = self.choose(context, stage, avoid=latest.worker if latest else None)
            if not worker:
                phase["state"] = "waiting_capacity"
                continue
            bus.commit(context, now=self.now)
            _, context = self.dispatch(context, stage, worker, coordinator, predecessor=latest)
        if context.snapshot() != before:
            bus.commit(context, now=self.now, allow_expired=True)

    def tick(self):
        scopes = {(p.tenant_id, p.store_id): p for p in self.runtime.principals.values()}
        scanned = 0
        for principal in scopes.values():
            # Inventory is read without holding scope locks over the entire sweep.
            contexts = self.contexts(principal)
            for context in contexts:
                if context.trigger == "worker_registry":
                    continue
                with self.store.transaction():
                    self.lock_scope(principal)
                    self.scan_context(principal, context.task_id)
                    scanned += 1
        metrics = {
            "queued_age_seconds_max": 0,
            "retry_wait": 0,
            "waiting": 0,
            "waiting_capacity": 0,
            "manual_intervention": 0,
            "unknown_outcome": 0,
            "expired_assignments": 0,
            "budget_exhausted": 0,
            "notification_pending": 0,
        }
        for principal in scopes.values():
            for context in self.contexts(principal):
                if context.trigger == "worker_registry":
                    continue
                for phase in context.recovery.get("phases", {}).values():
                    if phase["state"] in metrics:
                        metrics[phase["state"]] += 1
                    if phase.get("reason") in {"unknown_outcome", "budget_exhausted"}:
                        metrics[phase["reason"]] += 1
                    if phase["state"] in {"queued", "waiting_capacity", "retry_wait"}:
                        metrics["queued_age_seconds_max"] = max(
                            metrics["queued_age_seconds_max"],
                            (self.now - parse_timestamp(phase["queued_at"])).total_seconds(),
                        )
                metrics["expired_assignments"] += sum(
                    a.status == "expired" for a in self.assignments(context)
                )
                metrics["notification_pending"] += sum(
                    n["status"] != "delivered" for n in context.recovery.get("outbox", [])
                )
        self.metric_snapshot = metrics
        return scanned
