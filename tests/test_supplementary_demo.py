from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "demo" / "run_supplementary.py"


class SupplementaryDemoTests(unittest.TestCase):
    def test_stockout_and_price_tag_entries_exit_zero(self) -> None:
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        for scenario in ("stockout", "price-tag"):
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), scenario],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn(f"Supplementary scenario {scenario} completed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
