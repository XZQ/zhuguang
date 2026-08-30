"""Apply deterministic scenario events to a :class:`StateStore`."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..domain.enums import WorkOrderStatus
from ..state import StateStoreProtocol
from ..validation import validate_json

if TYPE_CHECKING:
    from ..mcp.p0 import MCPService

_ROOT = Path(__file__).resolve().parents[3]
_SHARE = Path(sys.prefix) / "share" / "dianxun"
_SCENARIO_SCHEMA = (
    _ROOT / "schemas" / "scenario.v1.schema.json"
    if (_ROOT / "schemas" / "scenario.v1.schema.json").exists()
    else _SHARE / "schemas" / "scenario.v1.schema.json"
)
_EVENT_REQUIRED_FIELDS = {
    "set_device_state": {"device_id"},
    "append_device_reading": {"device_id", "temp_c"},
    "append_temperature_series": {"device_id", "series"},
    "set_batch_safety": {"batch_id", "safe_for_sale"},
    "set_workorder_status": {"status"},
    "decide_approval": {"decision"},
    "record_manual_evidence": {"incident_id", "evidence_type"},
    "inject_tool_failure": {"tool_name"},
}


class ScenarioEngine:
    """Virtual clock plus an allow-listed event dispatcher."""

    def __init__(
        self,
        store: StateStoreProtocol,
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
        scenario_path = self.path.resolve()
        seed_value = Path(self.scenario["seed_path"])
        if seed_value.is_absolute():
            raise ValueError("Scenario seed_path must be relative")
        seed_path = (scenario_path.parent / seed_value).resolve()
        allowed_root = scenario_path.parent.parent
        if not seed_path.is_relative_to(allowed_root):
            raise ValueError("Scenario seed_path escapes the scenario data directory")
        if not seed_path.is_file():
            raise ValueError(f"Scenario seed file does not exist: {seed_path}")
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
        schema = json.loads(_SCENARIO_SCHEMA.read_text(encoding="utf-8"))
        errors = validate_json(scenario, schema, path="scenario")
        if errors:
            raise ValueError("Invalid scenario: " + "; ".join(errors[:10]))
        ground_truth = scenario["ground_truth"]
        required_ground_truth = {
            "store_id",
            "device_id",
            "root_cause",
            "affected_batches",
        }
        missing_ground_truth = sorted(required_ground_truth - ground_truth.keys())
        if missing_ground_truth:
            raise ValueError(f"Scenario ground_truth missing fields: {missing_ground_truth}")
        if not isinstance(ground_truth["affected_batches"], list) or not all(
            isinstance(item, str) and item for item in ground_truth["affected_batches"]
        ):
            raise ValueError("Scenario ground_truth.affected_batches must be non-empty strings")
        if not ground_truth["affected_batches"]:
            raise ValueError("Scenario ground_truth.affected_batches must not be empty")
        event_ids = [event["event_id"] for event in scenario["events"]]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Scenario event_id values must be unique")
        for event in scenario["events"]:
            payload = event["payload"]
            event_type = event["event_type"]
            missing = sorted(_EVENT_REQUIRED_FIELDS[event_type] - payload.keys())
            if missing:
                raise ValueError(
                    f"Scenario event {event['event_id']} missing payload fields: {missing}"
                )
            direct_reference = {
                "set_workorder_status": "workorder_id",
                "decide_approval": "approval_id",
            }.get(event_type)
            if direct_reference and not (payload.get("action_id") or payload.get(direct_reference)):
                required_reference = (
                    "workorder_id or action_id"
                    if event_type == "set_workorder_status"
                    else "approval_id or action_id"
                )
                raise ValueError(
                    f"Scenario event {event['event_id']} requires {required_reference}"
                )
            if event_type == "append_temperature_series":
                series = payload["series"]
                if not isinstance(series, list) or not series:
                    raise ValueError(
                        f"Scenario event {event['event_id']} temperature series must not be empty"
                    )
                if any(
                    not isinstance(item, dict)
                    or "offset_minutes" not in item
                    or "temp_c" not in item
                    for item in series
                ):
                    raise ValueError(
                        f"Scenario event {event['event_id']} has an invalid temperature series"
                    )
