"""Capture a fresh synthetic case; never operates on an existing runtime database."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from dianxun.adapters import LocalDemoAdapter
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, DEFAULT_SCENARIO_DIR
from dianxun.replay import render_run, seal_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["success", "failure"], required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory; existing evidence is never overwritten",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new run directory")
    root = Path(__file__).resolve().parents[1]
    provenance = {
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8"
        ).strip(),
        "dirty_worktree": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                cwd=root,
                text=True,
                encoding="utf-8",
            ).strip()
        ),
    }
    scenario = DEFAULT_SCENARIO_DIR / (
        "coldchain-compressor-failure.json"
        if args.case == "success"
        else "coldchain-device-recovered-goods-unsafe.json"
    )
    with tempfile.TemporaryDirectory(prefix="dianxun-replay-") as temporary:
        state, trace = Path(temporary) / "state.db", Path(temporary) / "trace.db"
        adapter = LocalDemoAdapter(
            db_path=state, trace_db_path=trace, scenario_path=scenario, enable_rag=False
        )
        result = adapter.run()
        if not result["acceptance"]["passed"]:
            raise RuntimeError("Scenario acceptance failed; no successful evidence bundle sealed")
        seal_run(
            args.output,
            state=state,
            trace=trace,
            result=result,
            scenario=scenario,
            policy=DEFAULT_POLICY_PATH,
            provenance=provenance,
        )
    print(json.dumps(render_run(args.output, args.output / "replay.html"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
