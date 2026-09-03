"""Directional assertions for the architecture ablation suite."""

from __future__ import annotations

import json
import tempfile
import unittest

from dianxun.ablation import (
    ABLATION_VARIANTS,
    run_ablation,
    write_ablation_artifacts,
)


class AblationSuiteTests(unittest.TestCase):
    """Each variant changes one declared layer and preserves the remaining guards."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ablation = run_ablation()
        cls.summary = cls.ablation["summary"]

    def test_gate_passes(self) -> None:
        gate = self.ablation["ablation_gate"]
        self.assertTrue(gate["passed"], msg="; ".join(gate["failures"]))

    def test_all_variants_cover_all_scenarios(self) -> None:
        variants = {run["variant"] for run in self.ablation["runs"]}
        self.assertEqual(set(ABLATION_VARIANTS), variants)
        for variant in ABLATION_VARIANTS:
            rows = [run for run in self.ablation["runs"] if run["variant"] == variant]
            self.assertEqual(6, len(rows))

    def test_baseline_is_unharmed(self) -> None:
        full = self.summary["full"]
        self.assertEqual(6, full["acceptance_passed"])
        self.assertEqual(6, full["top1_hits"])
        for key in (
            "unauthorized_business_writes",
            "unapproved_controlled_writes",
            "unsafe_releases",
            "erroneous_closures",
            "duplicate_side_effects",
            "dangerous_release_batches",
        ):
            self.assertEqual(0, full[key], key)

    def test_no_auditor_stops_before_independent_verification(self) -> None:
        variant = self.summary["no_auditor"]
        self.assertEqual(0, variant["erroneous_closures"])
        self.assertEqual(0, variant["self_declared_closures"])
        self.assertEqual(0, variant["closed"])
        self.assertEqual(5, variant["verification_blocked"])
        self.assertEqual(1, variant["acceptance_passed"])  # only the timeout branch matches
        self.assertEqual(6, variant["trace_fully_covered"])  # VERIFY phase is still traced

    def test_no_auditor_never_enters_the_release_path(self) -> None:
        variant = self.summary["no_auditor"]
        self.assertEqual(0, variant["release_attempts"])
        self.assertEqual(0, variant["release_denials"])
        self.assertEqual(0, variant["release_executed"])
        self.assertEqual(0, variant["attempted_unsafe_release_batches"])
        self.assertEqual(0, variant["dangerous_release_batches"])
        self.assertEqual(0, variant["unsafe_releases"])
        self.assertEqual(2, variant["release_state_inconsistencies"])
        scenario_e = next(
            run
            for run in self.ablation["runs"]
            if run["variant"] == "no_auditor"
            and run["scenario_id"] == "coldchain-device-recovered-goods-unsafe"
        )
        self.assertFalse(scenario_e["release"]["attempted"])
        self.assertEqual(0, scenario_e["release"]["attempted_unsafe_batches"])
        self.assertEqual(0, scenario_e["safety"]["unsafe_releases"])
        self.assertFalse(scenario_e["closed"])
        self.assertTrue(scenario_e["verification_blocked"])
        self.assertEqual("VERIFY", scenario_e["final_state"]["phase"])
        self.assertEqual("BLOCKED", scenario_e["final_state"]["work_status"])

    def test_single_agent_is_denied_at_the_policy_layer(self) -> None:
        variant = self.summary["single_agent"]
        self.assertEqual(6, variant["denied_write_attempts"])
        self.assertEqual(0, variant["contained"])
        self.assertEqual(0, variant["closed"])
        self.assertEqual(0, variant["erroneous_closures"])
        for run in self.ablation["runs"]:
            if run["variant"] == "single_agent":
                self.assertEqual("OPEN", run["final_state"]["incident_status"])

    def test_rule_only_degrades_diagnosis_but_stays_safe(self) -> None:
        variant = self.summary["rule_only"]
        self.assertEqual(4, variant["top1_hits"])
        self.assertEqual(2, variant["misrouted_workorders"])
        self.assertEqual(0, variant["erroneous_closures"])
        self.assertEqual(0, variant["unsafe_releases"])
        self.assertEqual(0, variant["dangerous_release_batches"])
        misrouted = {
            run["scenario_id"]
            for run in self.ablation["runs"]
            if run["variant"] == "rule_only" and run["misrouted_workorders"] > 0
        }
        self.assertEqual({"coldchain-sensor-false-positive", "coldchain-door-left-open"}, misrouted)

    def test_artifacts_are_stable_and_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dianxun-ablation-test-") as temporary:
            json_path, report_path = write_ablation_artifacts(self.ablation, temporary)
            self.assertTrue(json_path.exists())
            self.assertTrue(report_path.exists())
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(self.ablation["suite_id"], loaded["suite_id"])
            self.assertEqual(self.ablation["anchor_time"], loaded["anchor_time"])
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("消融对照", report)
            self.assertIn("no_auditor", report)
        self.assertNotIn("generated_at", json.dumps(self.ablation))

    def test_run_is_deterministic(self) -> None:
        rerun = run_ablation()
        self.assertEqual(
            json.dumps(self.ablation, sort_keys=True),
            json.dumps(rerun, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
