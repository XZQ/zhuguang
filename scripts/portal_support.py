"""Shared deterministic inputs for presentation builders."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "assets"


def project_facts() -> dict:
    return json.loads((ROOT / "config/project-facts.json").read_text(encoding="utf-8"))


def render_asset(name: str, **values: str) -> str:
    facts = project_facts()
    evaluation = facts["implementation"]["m4_evaluation"]
    values = {
        "MODEL": facts["agentteams"]["default_model"],
        "TEST_COUNT": evaluation["full_unittest_count"],
        "TEST_PASSED": evaluation["full_unittest_passed"],
        "TEST_SKIPPED": evaluation["conditional_integration_skipped"],
        "TEST_DATE": evaluation["unittest_verified_at"],
        **values,
    }
    template = (ASSETS / name).read_text(encoding="utf-8")

    def replace(match):
        key = match[1]
        if key not in values:
            raise ValueError(f"Missing template input {key} in {name}")
        return str(values[key])

    return re.sub(r"@@(\w+)@@", replace, template)
