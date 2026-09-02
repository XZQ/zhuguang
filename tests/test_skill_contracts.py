from __future__ import annotations

import json
import unittest
from pathlib import Path

from dianxun.skills.contracts import SkillOutputContractError, validate_skill_output

try:
    from jsonschema.validators import validator_for
except ImportError:  # pragma: no cover - exercised in the explicit contract gate
    validator_for = None

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"
P0_SKILLS = {
    "anomaly-detect",
    "coldchain-risk-assess",
    "rootcause-drilldown",
    "work-order-dispatch",
    "outcome-verify",
    "review-report",
}


@unittest.skipIf(validator_for is None, "jsonschema is only required by the contract gate")
class SkillContractTests(unittest.TestCase):
    def test_all_p0_skill_packages_have_valid_contracts_and_examples(self) -> None:
        packaged = {path.name for path in SKILL_ROOT.iterdir() if (path / "manifest.json").exists()}
        self.assertEqual(P0_SKILLS, packaged)
        for name in sorted(P0_SKILLS):
            with self.subTest(skill=name):
                root = SKILL_ROOT / name
                manifest = self._json(root / "manifest.json")
                self.assertEqual(name, manifest["name"])
                self.assertEqual("P0", manifest["priority"])
                self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
                self.assertTrue(manifest["error_codes"])
                self.assertTrue(manifest["quality_metrics"])
                skill_doc = (root / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("## Change log", skill_doc)
                self.assertIn("Permissions", skill_doc)

                input_schema = self._json(root / "input.schema.json")
                output_schema = self._json(root / "output.schema.json")
                input_validator = validator_for(input_schema)
                output_validator = validator_for(output_schema)
                input_validator.check_schema(input_schema)
                output_validator.check_schema(output_schema)
                examples = self._json(root / "examples.json")
                for branch in ("success", "failure"):
                    input_validator(input_schema).validate(examples[branch]["input"])
                    output_validator(output_schema).validate(examples[branch]["output"])
                    self.assertIs(
                        examples[branch]["output"],
                        validate_skill_output(name, examples[branch]["output"]),
                    )

                invalid_output = dict(examples["success"]["output"])
                invalid_output.pop(output_schema["required"][0])
                with self.assertRaisesRegex(SkillOutputContractError, "missing required property"):
                    validate_skill_output(name, invalid_output)

    @staticmethod
    def _json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
