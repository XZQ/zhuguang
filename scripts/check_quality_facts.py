"""Reject test-inventory drift in current facts and primary documentation.

Discovery is not test execution. CI must run the complete suite separately; the passed/skipped
figures here describe the explicitly dated local run, not a claim about another environment.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(ROOT))
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    if loader.errors:
        raise RuntimeError("Test discovery failed:\n" + "\n".join(loader.errors))
    facts = json.loads((ROOT / "config/project-facts.json").read_text(encoding="utf-8"))
    recorded = facts["implementation"]["m4_evaluation"]
    count = suite.countTestCases()
    passed = recorded["full_unittest_passed"]
    skipped = recorded["conditional_integration_skipped"]
    if count != recorded["full_unittest_count"] or count != passed + skipped:
        raise RuntimeError("Update the recorded test counts after a successful complete run")
    required = {
        "README.md": (f"{count} 项发现：{passed} 通过、{skipped} 个 PolarDB 条件集成测试",),
        "docs/测试覆盖矩阵.md": (
            f"| unittest 发现数 | {count} |",
            f"{count} 发现 / {passed} 通过 / {skipped} 条件 skip",
        ),
        "agentteams/README.md": (f"全量发现 {count} 项测试，其中 {passed} 项通过、{skipped} 项",),
    }
    for name, claims in required.items():
        content = (ROOT / name).read_text(encoding="utf-8")
        if any(claim not in content for claim in claims):
            raise RuntimeError(f"Current test evidence is stale in {name}")
    print(
        f"QUALITY_FACTS_OK (discovered={count}; dated reference={passed} passed/{skipped} skipped)"
    )


if __name__ == "__main__":
    main()
