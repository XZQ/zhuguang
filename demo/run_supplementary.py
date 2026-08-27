#!/usr/bin/env python3
"""Run one legacy supplementary scenario from a source checkout."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dianxun import trace  # noqa: E402
from dianxun.agents import Orchestrator  # noqa: E402

SCENARIOS = {
    "stockout": {
        "task_id": "SUPPLEMENT-STOCKOUT",
        "scope": {"store_ids": ["S05"], "data_sources": ["wms"]},
        "trigger": "scheduled",
    },
    "price-tag": {
        "task_id": "SUPPLEMENT-PRICE-TAG",
        "scope": {"store_ids": ["S08"], "data_sources": ["price"]},
        "trigger": "scheduled",
    },
}


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    args = parser.parse_args(argv)
    definition = SCENARIOS[args.scenario]
    with tempfile.TemporaryDirectory(prefix="dianxun-supplement-") as temporary:
        with trace.use_database(Path(temporary) / "trace.db"):
            result = Orchestrator().run_task(
                definition["task_id"],
                scope=definition["scope"],
                trigger=definition["trigger"],
            )
    if result.get("result") in {"no_anomaly", "failed"}:
        print(
            f"Supplementary scenario {args.scenario} did not close safely: {result.get('result')}",
            file=sys.stderr,
        )
        return 1
    print(f"Supplementary scenario {args.scenario} completed")
    return 0


def _configure_stdio() -> None:
    if os.name == "nt":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure:
                reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
