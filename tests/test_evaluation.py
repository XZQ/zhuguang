from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from dianxun.evaluation import (
    DEFAULT_SCENARIO_DIR,
    P0_SCENARIO_FILES,
    evaluate_suite,
    write_evaluation_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def test_all_six_scenarios_match_the_frozen_schema(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "scenario.v1.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        self.assertEqual(6, len(P0_SCENARIO_FILES))
        for filename in P0_SCENARIO_FILES:
            scenario = json.loads((DEFAULT_SCENARIO_DIR / filename).read_text(encoding="utf-8"))
            errors = sorted(validator.iter_errors(scenario), key=lambda item: list(item.path))
            self.assertEqual([], errors, filename)

    def test_evaluation_is_reproducible_and_passes_every_local_gate(self) -> None:
        first = evaluate_suite()
        second = evaluate_suite()
        self.assertEqual(first, second)
        self.assertTrue(first["local_m4_gate"]["passed"])
        self.assertEqual(6, first["metrics"]["scenario_passed"])
        self.assertEqual(1.0, first["metrics"]["top3_accuracy"])
        self.assertEqual(1.0, first["metrics"]["evidence_field_completeness"])
        self.assertEqual(1.0, first["metrics"]["trace_phase_coverage"])
        self.assertEqual("not_run", first["external_validation"]["agentteams_dynamic"])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_json, first_report = write_evaluation_artifacts(first, root / "first")
            second_json, second_report = write_evaluation_artifacts(second, root / "second")
            self.assertEqual(first_json.read_bytes(), second_json.read_bytes())
            self.assertEqual(first_report.read_bytes(), second_report.read_bytes())


if __name__ == "__main__":
    unittest.main()
