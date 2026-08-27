from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dianxun.domain import (
    IncidentCase,
    IncidentService,
    IncidentStatus,
    IncidentType,
    Phase,
    PolicyEngine,
    Severity,
)
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, MCPService
from dianxun.mcp.server import TOOLS, tools_list
from dianxun.scenarios import ScenarioEngine
from dianxun.state import StateStore

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "demo" / "state" / "seed.json"
SCENARIO_PATH = ROOT / "demo" / "state" / "scenarios" / "coldchain-compressor-failure.json"


class StatefulCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "runtime.db"
        self.store = StateStore(self.db_path)
        self.seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.store.initialize(self.seed)
        self.service = MCPService(self.store, PolicyEngine(DEFAULT_POLICY_PATH))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_seed_reset_is_repeatable(self) -> None:
        first = self.store.snapshot_digest()
        self.store.set_device_state("FROST-S03", health_state="fault")
        changed = self.store.snapshot_digest()
        self.assertNotEqual(first, changed)
        reset = self.store.initialize(self.seed, reset=True)
        self.assertEqual(first, reset)
        self.assertEqual(first, self.store.snapshot_digest())

    def test_scenario_engine_applies_fault_to_same_world(self) -> None:
        engine = ScenarioEngine(self.store, SCENARIO_PATH, service=self.service)
        engine.reset()
        response = self.service.query_device_context(device_id="FROST-S03")
        self.assertTrue(response["ok"])
        device = response["data"]["devices"][0]
        self.assertEqual("fault", device["health"]["state"])
        self.assertEqual("stalled", device["health"]["compressor_state"])
        self.assertEqual(9.6, device["temperature_series"][-1]["temp_c"])

    def test_sales_hold_is_idempotent_and_requeryable(self) -> None:
        first = self.service.apply_sales_hold(
            incident_id="INC-M1-HOLD",
            action_id="ACT-HOLD",
            store_id="S03",
            batch_ids=["BATCH-S03-DAIRY-001", "BATCH-S03-FRESH-001"],
            reason="sustained temperature rise",
            idempotency_key="m1:hold",
        )
        replay = self.service.apply_sales_hold(
            incident_id="INC-M1-HOLD",
            action_id="ACT-HOLD",
            store_id="S03",
            batch_ids=["BATCH-S03-DAIRY-001", "BATCH-S03-FRESH-001"],
            reason="sustained temperature rise",
            idempotency_key="m1:hold",
        )
        self.assertTrue(first["ok"])
        self.assertTrue(replay["ok"])
        self.assertTrue(replay["data"]["idempotent_replay"])
        self.assertEqual(first["audit_ref"], replay["audit_ref"])
        queried = self.service.query_sales_holds(incident_id="INC-M1-HOLD")
        self.assertEqual(2, len(queried["data"]["sales_holds"]))
        batches = self.service.query_inventory_batches(store_id="S03")
        self.assertTrue(all(not row["safe_for_sale"] for row in batches["data"]["batches"]))
        self.assertTrue(
            all(row["disposition"] == "quarantined" for row in batches["data"]["batches"])
        )

    def test_high_budget_workorder_waits_for_real_approval(self) -> None:
        created = self.service.create_approval(
            incident_id="INC-M1-APPROVAL",
            action_id="ACT-REPAIR",
            subject="compressor repair",
            requested_action_type="create_workorder",
            amount=2500,
            timeout_minutes=30,
            idempotency_key="m1:approval",
        )
        self.assertTrue(created["ok"])
        approval_id = created["data"]["approval_id"]
        self.assertEqual("pending", created["data"]["status"])

        blocked = self.service.create_workorder(
            incident_id="INC-M1-APPROVAL",
            action_id="ACT-REPAIR",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor failure",
            budget=2500,
            idempotency_key="m1:workorder:blocked",
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual("APPROVAL_REQUIRED", blocked["error"]["code"])

        spoofed = self.service.decide_approval(
            approval_id=approval_id,
            decision="approved",
            reason="agent spoof",
            idempotency_key="m1:decision:spoof",
            actor="Executor",
        )
        self.assertFalse(spoofed["ok"])
        self.assertEqual("FORBIDDEN", spoofed["error"]["code"])

        decided = self.service.decide_approval(
            approval_id=approval_id,
            decision="approved",
            reason="store manager approved",
            idempotency_key="m1:decision:human",
            actor="Human",
        )
        self.assertTrue(decided["ok"])
        workorder = self.service.create_workorder(
            incident_id="INC-M1-APPROVAL",
            action_id="ACT-REPAIR",
            store_id="S03",
            device_id="FROST-S03",
            fault="compressor failure",
            budget=2500,
            approval_id=approval_id,
            idempotency_key="m1:workorder:approved",
        )
        self.assertTrue(workorder["ok"])
        queried = self.service.query_workorder(action_id="ACT-REPAIR")
        self.assertEqual("assigned", queried["data"]["workorders"][0]["status"])

    def test_virtual_time_expires_pending_approval(self) -> None:
        created = self.service.create_approval(
            incident_id="INC-M1-TIMEOUT",
            action_id="ACT-TIMEOUT",
            subject="repair timeout",
            requested_action_type="create_workorder",
            amount=2500,
            timeout_minutes=5,
            idempotency_key="m1:approval:timeout",
        )
        approval_id = created["data"]["approval_id"]
        self.store.advance_time(minutes=5)
        queried = self.service.query_approval(approval_id=approval_id)
        self.assertEqual("timeout", queried["data"]["approvals"][0]["status"])

    def test_incident_service_aggregates_containment(self) -> None:
        incidents = IncidentService(self.store)
        case = IncidentCase.create(
            incident_id="INC-M1-DOMAIN",
            tenant_id="demo",
            store_id="S03",
            incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
            severity=Severity.CRITICAL,
            trigger="scenario",
            anchor_time=self.store.now(),
        )
        case.affected_assets = ["FROST-S03"]
        case.affected_batches = ["BATCH-S03-DAIRY-001", "BATCH-S03-FRESH-001"]
        incidents.create(case)
        self.service.apply_sales_hold(
            incident_id=case.incident_id,
            action_id="ACT-DOMAIN-HOLD",
            store_id="S03",
            batch_ids=case.affected_batches,
            reason="containment",
            idempotency_key="m1:domain:hold",
        )
        recomputed = incidents.recompute(case.incident_id)
        self.assertEqual(IncidentStatus.CONTAINED, recomputed.incident_status)
        self.assertNotEqual(IncidentStatus.RESOLVED, recomputed.incident_status)
        advanced = incidents.transition_phase(
            case.incident_id,
            Phase.DIAGNOSE_DECIDE,
            actor="Orchestrator",
            reason="containment complete",
        )
        self.assertEqual(Phase.DIAGNOSE_DECIDE, advanced.phase)

    def test_registry_is_exactly_the_twelve_p0_functions(self) -> None:
        expected = {
            "query_device_context",
            "query_inventory_batches",
            "query_sales_holds",
            "query_workorder",
            "query_approval",
            "apply_sales_hold",
            "release_sales_hold",
            "apply_batch_disposition",
            "create_workorder",
            "create_approval",
            "decide_approval",
            "record_manual_evidence",
        }
        self.assertEqual(expected, set(TOOLS))
        self.assertEqual(12, len(tools_list()))
        self.assertTrue(all(item["inputSchema"]["type"] == "object" for item in tools_list()))

    def test_service_bootstraps_a_brand_new_database(self) -> None:
        fresh_path = Path(self.temp_dir.name) / "fresh.db"
        fresh = MCPService(
            StateStore(fresh_path),
            PolicyEngine(DEFAULT_POLICY_PATH),
            auto_initialize_seed=SEED_PATH,
        )
        response = fresh.query_device_context(device_id="FROST-S03", facets=["health"])
        self.assertTrue(response["ok"])
        self.assertEqual("normal", response["data"]["devices"][0]["health"]["state"])


if __name__ == "__main__":
    unittest.main()
