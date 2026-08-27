from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dianxun.adapters import LocalDemoAdapter
from dianxun.domain import ActionStatus, IncidentStatus, Phase, WorkStatus

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "demo" / "state" / "scenarios"


class ColdChainWorkflowTests(unittest.TestCase):
    def run_scenario(self, name: str):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        adapter = LocalDemoAdapter(
            db_path=Path(temporary.name) / "runtime.db",
            scenario_path=SCENARIOS / name,
        )
        return adapter, adapter.run()

    def test_scenario_a_closes_after_device_and_goods_verification(self) -> None:
        adapter, result = self.run_scenario("coldchain-compressor-failure.json")
        case = result["incident"]
        self.assertTrue(result["acceptance"]["passed"])
        self.assertEqual("closed", result["result"])
        self.assertEqual(IncidentStatus.CLOSED, case["incident_status"])
        self.assertEqual(Phase.LEARN, case["phase"])
        self.assertEqual(
            {
                "BATCH-S03-DAIRY-001": "disposed",
                "BATCH-S03-FRESH-001": "transferred",
            },
            case["batch_dispositions"],
        )
        self.assertEqual(
            {"device", "batches", "sales_hold", "approval", "audit"},
            {item["subject"] for item in case["verifications"]},
        )
        self.assertTrue(all(item["verifier"] == "Auditor" for item in case["verifications"]))
        workorders = adapter.store.list_workorders(incident_id=case["incident_id"])
        self.assertTrue(workorders[0]["completion_evidence"])

    def test_scenario_d_timeout_never_dispatches_repair(self) -> None:
        adapter, result = self.run_scenario("coldchain-approval-timeout.json")
        case = result["incident"]
        self.assertTrue(result["acceptance"]["passed"])
        self.assertEqual(IncidentStatus.CONTAINED, case["incident_status"])
        self.assertEqual(WorkStatus.WAITING_EXTERNAL, case["work_status"])
        self.assertEqual([], adapter.store.list_workorders(incident_id=case["incident_id"]))
        repair = next(item for item in case["actions"] if item["action_id"].endswith(":repair"))
        self.assertEqual(ActionStatus.TIMEOUT, repair["status"])
        holds = adapter.store.list_sales_holds(incident_id=case["incident_id"])
        self.assertTrue(holds and all(item["status"] == "active" for item in holds))

    def test_scenario_e_reopens_goods_branch_after_device_recovery(self) -> None:
        adapter, result = self.run_scenario("coldchain-device-recovered-goods-unsafe.json")
        case = result["incident"]
        self.assertTrue(result["acceptance"]["passed"])
        self.assertEqual("manual_review", result["verification"]["result"])
        self.assertEqual({"recovered"}, set(case["asset_states"].values()))
        self.assertEqual({"quarantined"}, set(case["batch_dispositions"].values()))
        self.assertEqual(Phase.EXECUTE, case["phase"])
        self.assertEqual(WorkStatus.WAITING_APPROVAL, case["work_status"])
        self.assertTrue(
            any(item["decision_id"].startswith("reopen:") for item in case["decisions"])
        )
        pending = adapter.store.list_approvals(incident_id=case["incident_id"])
        self.assertEqual(2, sum(item["status"] == "pending" for item in pending))

    def test_diagnosis_is_top_k_evidence_linked_without_fake_rag(self) -> None:
        _, result = self.run_scenario("coldchain-compressor-failure.json")
        diagnosis = result["phases"]["DIAGNOSE_DECIDE"]
        hypotheses = diagnosis["hypotheses"]
        self.assertGreaterEqual(len(hypotheses), 2)
        self.assertEqual("compressor_failure", hypotheses[0]["label"])
        self.assertTrue(hypotheses[0]["supporting_evidence_ids"])
        self.assertEqual({"status": "disabled", "hits": []}, diagnosis["rag"])

    def test_exposure_assessment_is_batch_specific(self) -> None:
        _, result = self.run_scenario("coldchain-compressor-failure.json")
        assessment = result["phases"]["DIAGNOSE_DECIDE"]["risk_assessment"]
        by_batch = {item["batch_id"]: item for item in assessment["exposure_assessment"]}
        self.assertEqual("disposed", by_batch["BATCH-S03-DAIRY-001"]["recommendation"])
        self.assertEqual("transferred", by_batch["BATCH-S03-FRESH-001"]["recommendation"])
        self.assertGreater(
            by_batch["BATCH-S03-DAIRY-001"]["degree_minutes"],
            by_batch["BATCH-S03-FRESH-001"]["degree_minutes"],
        )

    def test_auditor_does_not_trust_executor_action_receipts(self) -> None:
        adapter, result = self.run_scenario("coldchain-device-recovered-goods-unsafe.json")
        case = result["incident"]
        repair = next(item for item in case["actions"] if item["action_id"].endswith(":repair"))
        self.assertEqual(ActionStatus.COMPLETED, repair["status"])
        self.assertNotEqual(IncidentStatus.CLOSED, case["incident_status"])
        self.assertIn("batches", result["verification"]["failed_conditions"])
        batches = adapter.store.list_batches(batch_ids=case["affected_batches"])
        self.assertTrue(all(not item["safe_for_sale"] for item in batches))

    def test_scenario_outcome_is_repeatable(self) -> None:
        _, first = self.run_scenario("coldchain-compressor-failure.json")
        _, second = self.run_scenario("coldchain-compressor-failure.json")
        fields = ("phase", "incident_status", "work_status", "batch_dispositions", "asset_states")
        self.assertEqual(
            {field: first["incident"][field] for field in fields},
            {field: second["incident"][field] for field in fields},
        )


if __name__ == "__main__":
    unittest.main()
