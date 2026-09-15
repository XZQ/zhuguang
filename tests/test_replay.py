from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dianxun.adapters import LocalDemoAdapter
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, DEFAULT_SCENARIO_PATH
from dianxun.replay import render_run, seal_run, verify_run


class ReplayTests(unittest.TestCase):
    def test_sealed_run_replays_without_execution_or_database_changes_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state, trace = root / "state.db", root / "trace.db"
            adapter = LocalDemoAdapter(
                db_path=state, trace_db_path=trace, scenario_path=DEFAULT_SCENARIO_PATH
            )
            result = adapter.run()
            bundle = root / "bundle"
            seal_run(
                bundle,
                state=state,
                trace=trace,
                result=result,
                scenario=DEFAULT_SCENARIO_PATH,
                policy=DEFAULT_POLICY_PATH,
                provenance={"test": True},
            )
            before = {p.name: p.read_bytes() for p in bundle.iterdir()}
            with patch.object(
                LocalDemoAdapter, "run", side_effect=AssertionError("must not rerun")
            ):
                report = render_run(bundle, root / "replay.html")
            self.assertEqual("CLOSED", report["status"])
            self.assertEqual(before, {p.name: p.read_bytes() for p in bundle.iterdir()})
            with self.assertRaises(ValueError):
                render_run(bundle, bundle / "state.sqlite")
            with self.assertRaises(FileExistsError):
                seal_run(
                    bundle,
                    state=state,
                    trace=trace,
                    result=result,
                    scenario=DEFAULT_SCENARIO_PATH,
                    policy=DEFAULT_POLICY_PATH,
                    provenance={},
                )
            (bundle / "trace.jsonl").write_bytes(b"{}\n")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                verify_run(bundle)
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["trace.jsonl"] = hashlib.sha256(b"{}\n").hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inconsistent export"):
                verify_run(bundle)
            manifest["files"]["../outside"] = "ignored"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incomplete replay manifest"):
                verify_run(bundle)
