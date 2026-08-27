"""Apply deterministic scenario events to a :class:`StateStore`."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..domain.enums import WorkOrderStatus
from ..state import StateStore

if TYPE_CHECKING:
    from ..mcp.p0 import MCPService


class ScenarioEngine:
    """Virtual clock plus an allow-listed event dispatcher."""

    def __init__(
        self,
        store: StateStore,
        scenario_path: str | Path,
        *,
        service: MCPService | None = None,
    ) -> None:
        self.store = store
        self.path = Path(scenario_path)
        self.scenario = json.loads(self.path.read_text(encoding="utf-8"))
        self.service = service
        self._validate(self.scenario)

    def reset(self) -> str:
        seed_path = (self.path.parent / self.scenario["seed_path"]).resolve()
        digest = self.store.initialize_from_file(seed_path, reset=True)
        self.store.set_meta("scenario_id", self.scenario["scenario_id"])
        self.apply_due_events()
        return digest

    def advance(self, *, minutes: int) -> str:
        updated = self.store.advance_time(minutes=minutes)
        self.apply_due_events()
        return updated

    def apply_due_events(self) -> list[str]:
        elapsed = self.elapsed_minutes()
        applied: list[str] = []
        for event in sorted(
            self.scenario.get("events", []),
            key=lambda item: (item["at_minute"], item["event_id"]),
        ):
            marker = f"scenario_event:{self.scenario['scenario_id']}:{event['event_id']}"
            if event["at_minute"] <= elapsed and self.store.get_meta(marker) != "applied":
                self._apply(event)
                self.store.set_meta(marker, "applied")
                applied.append(event["event_id"])
        return applied

    def elapsed_minutes(self) -> int:
        anchor = datetime.fromisoformat(self.store.get_meta("anchor_time") or self.store.now())
        current = datetime.fromisoformat(self.store.now())
        return int((current - anchor).total_seconds() // 60)

    def _apply(self, event: dict[str, Any]) -> None:
        event_type = event["event_type"]
        payload = event.get("payload", {})
        if event_type == "set_device_state":
            device_id = payload["device_id"]
            changes = {key: value for key, value in payload.items() if key != "device_id"}
            self.store.set_device_state(device_id, **changes)
        elif event_type == "append_device_reading":
            self.store.append_device_reading(
                device_id=payload["device_id"],
                observed_at=self.store.now(),
                temp_c=float(payload["temp_c"]),
                quality=payload.get("quality", "good"),
                source="scenario",
            )
        elif event_type == "append_temperature_series":
            anchor = datetime.fromisoformat(self.store.get_meta("anchor_time") or self.store.now())
            for item in payload["series"]:
                observed_at = (anchor + timedelta(minutes=item["offset_minutes"])).isoformat(
                    timespec="seconds"
                )
                self.store.append_device_reading(
                    device_id=payload["device_id"],
                    observed_at=observed_at,
                    temp_c=float(item["temp_c"]),
                    quality=item.get("quality", "good"),
                    source="scenario",
                )
        elif event_type == "set_batch_safety":
            self.store.set_batch_safety(
                payload["batch_id"],
                safe_for_sale=bool(payload["safe_for_sale"]),
            )
        elif event_type == "set_workorder_status":
            workorder_id = payload.get("workorder_id") or self._workorder_for_action(
                payload["action_id"]
            )
            self.store.set_workorder_status(
                workorder_id,
                status=WorkOrderStatus(payload["status"]),
                completion_evidence=payload.get("completion_evidence"),
            )
        elif event_type == "decide_approval":
            if self.service is None:
                raise RuntimeError("decide_approval event requires MCPService")
            approval_id = payload.get("approval_id") or self._approval_for_action(
                payload["action_id"]
            )
            result = self.service.decide_approval(
                approval_id=approval_id,
                decision=payload["decision"],
                reason=payload.get("reason", "scenario decision"),
                idempotency_key=f"scenario:{self.scenario['scenario_id']}:{event['event_id']}",
                actor="ScenarioEngine",
            )
            if not result["ok"]:
                raise RuntimeError(result["error"])
        elif event_type == "record_manual_evidence":
            if self.service is None:
                raise RuntimeError("record_manual_evidence event requires MCPService")
            result = self.service.record_manual_evidence(
                incident_id=payload["incident_id"],
                action_id=payload.get("action_id"),
                evidence_type=payload["evidence_type"],
                observed_at=self.store.now(),
                note=payload.get("note", ""),
                metadata=payload.get("metadata", {}),
                uri=payload.get("uri"),
                sha256=payload.get("sha256"),
                idempotency_key=f"scenario:{self.scenario['scenario_id']}:{event['event_id']}",
                actor="ScenarioEngine",
            )
            if not result["ok"]:
                raise RuntimeError(result["error"])
        elif event_type == "inject_tool_failure":
            self.store.inject_tool_failure(
                tool_name=payload["tool_name"],
                remaining_calls=int(payload.get("remaining_calls", 1)),
                error_code=payload.get("error_code", "SCENARIO_FAILURE"),
                message=payload.get("message", "Injected scenario failure"),
            )
        else:
            raise ValueError(f"Unsupported scenario event {event_type}")

    def _approval_for_action(self, action_id: str) -> str:
        rows = self.store.list_approvals(action_id=action_id)
        if len(rows) != 1:
            raise RuntimeError(f"Expected one approval for {action_id}, found {len(rows)}")
        return str(rows[0]["approval_id"])

    def _workorder_for_action(self, action_id: str) -> str:
        rows = self.store.list_workorders(action_id=action_id)
        if len(rows) != 1:
            raise RuntimeError(f"Expected one workorder for {action_id}, found {len(rows)}")
        return str(rows[0]["workorder_id"])

    @staticmethod
    def _validate(scenario: dict[str, Any]) -> None:
        required = {
            "schema_version",
            "scenario_id",
            "name",
            "seed_path",
            "ground_truth",
            "allowed_hypotheses",
            "prohibited_actions",
            "required_actions",
            "expected_final_state",
            "expected_evidence",
            "maximum_safe_latency_minutes",
            "events",
        }
        missing = sorted(required - scenario.keys())
        if missing:
            raise ValueError(f"Scenario missing fields: {missing}")
        event_ids = [event["event_id"] for event in scenario["events"]]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Scenario event_id values must be unique")
