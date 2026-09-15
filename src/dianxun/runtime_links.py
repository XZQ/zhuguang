"""Bind applied scenario inputs and Worker-supplied platform references to runtime tasks."""

from __future__ import annotations

import json
import os
from datetime import timedelta

from .context_bus import parse_timestamp, timestamp
from .domain.models import stable_hash
from .mcp.p0 import DEFAULT_SCENARIO_DIR


def ingest_scenario(runtime, principal, scenario_id, event_id):
    if principal.actor != "Orchestrator":
        raise PermissionError("Only Orchestrator can ingest scenario events")
    if os.environ.get("DIANXUN_SCENARIO_BRIDGE_ENABLED") != "1":
        raise PermissionError("Scenario bridge is disabled; enable only in an isolated demo")
    candidates = [p for p in DEFAULT_SCENARIO_DIR.glob("*.json") if p.stem == scenario_id]
    if len(candidates) != 1:
        raise ValueError("Unknown installed scenario")
    scenario = json.loads(candidates[0].read_text(encoding="utf-8"))
    if (runtime.store.get_meta("scenario_id"), runtime.store.get_meta("scenario_digest")) != (
        scenario_id,
        stable_hash(scenario),
    ):
        raise ValueError("Scenario does not match the initialized isolated store")
    event = next((e for e in scenario["events"] if e["event_id"] == event_id), None)
    if not event or event["event_type"] not in {
        "set_device_state",
        "append_device_reading",
        "append_temperature_series",
    }:
        raise ValueError("Only applied device events can open runtime incidents")
    marker = f"scenario_event:{scenario_id}:{event_id}"
    if runtime.store.get_meta(marker) != "applied":
        raise ValueError("Scenario event has not been applied")
    identity = [principal.tenant_id, principal.store_id, scenario_id, event_id]
    incident_id = "scenario-" + stable_hash(identity)[:32]
    # open() enforces actual device ownership and creates a recoverable runtime context.
    runtime.open(
        principal=principal, incident_id=incident_id, device_id=event["payload"]["device_id"]
    )
    _, bus, _ = runtime._context(principal, incident_id)
    context = bus.get(incident_id, now=runtime.clock())
    source = {
        "source_kind": "scenario",
        "scenario_id": scenario_id,
        "event_id": event_id,
        "scenario_digest": stable_hash(scenario),
        "event_digest": stable_hash(event),
        "event_type": event["event_type"],
        "payload": event["payload"],
        "occurred_at": timestamp(
            parse_timestamp(runtime.store.get_meta("anchor_time"))
            + timedelta(minutes=event["at_minute"])
        ),
    }
    if context.source_events:
        if context.source_events[0] != source:
            raise ValueError("Incident source cannot be replaced")
    else:
        context.source_events.append(source)
        context.trigger = "scenario"
        bus.commit(context, now=runtime.clock())
        _audit(runtime, principal, incident_id, "runtime_ingest_scenario", source)
    return runtime.snapshot(principal=principal, incident_id=incident_id)


def link_platform(
    runtime,
    principal,
    *,
    incident_id,
    assignment_id,
    expected_version,
    link_kind="assignment",
    **refs,
):
    _, bus, coordinator = runtime._context(principal, incident_id)
    context = bus.get(incident_id, now=runtime.clock())
    assignment = coordinator._find_assignment(context, assignment_id)
    coordinator._assert_worker(assignment, principal.worker_id)
    identity = {
        "link_kind": link_kind,
        "assignment_id": assignment_id,
        "worker_id": principal.worker_id,
        "actor": principal.actor,
        "stage": assignment.phase,
        **refs,
    }
    for previous in context.platform_links:
        if (previous["room_id"], previous["message_id"]) == (refs["room_id"], refs["message_id"]):
            if any(previous.get(key) != value for key, value in identity.items()):
                raise ValueError("Platform message already has a different binding")
            return {"link": previous, "context_version": context.version, "replayed": True}
    if link_kind == "result":
        if context.version != expected_version:
            raise ValueError("Reload the current context version")
        if principal.actor != runtime.recovery.role(assignment.phase):
            raise PermissionError("Wrong actor for assignment")
        if not any(
            item["assignment_id"] == assignment_id
            and stable_hash(item["output"]) == refs.get("output_digest")
            for item in context.attempt_outputs
        ):
            raise ValueError("Result binding requires a recorded server output digest")
    else:
        if "output_digest" in refs:
            raise ValueError("Only result bindings accept an output digest")
        runtime._assignment(principal, incident_id, assignment_id, expected_version)
    if len(context.platform_links) >= 1000:
        raise ValueError("Incident platform reference limit reached")
    link = {
        **identity,
        "recorded_at": timestamp(runtime.clock()),
        "verification": "worker_submitted_not_platform_verified",
    }
    context.platform_links.append(link)
    bus.commit(context, now=runtime.clock())
    _audit(runtime, principal, incident_id, "runtime_link_platform", link)
    return {"link": link, "context_version": context.version, "replayed": False}


def _audit(runtime, principal, incident_id, tool, request):
    with runtime.store.transaction() as conn:
        runtime.store.record_audit(
            conn,
            request_id=f"{tool}:{stable_hash(request)}",
            actor=principal.actor,
            tool_name=tool,
            incident_id=incident_id,
            action_id=None,
            policy=None,
            request=request,
            response={"ok": True, "worker_id": principal.worker_id},
            created_at=runtime.store.now(),
        )
