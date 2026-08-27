#!/usr/bin/env python3
"""Run the P0 cold-chain five-phase demo from a source checkout."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

main = import_module("dianxun.cli").main


if __name__ == "__main__":
    default_scenario = ROOT / "demo" / "state" / "scenarios" / "coldchain-compressor-failure.json"
    raise SystemExit(main(["demo-run", str(default_scenario), *sys.argv[1:]]))
