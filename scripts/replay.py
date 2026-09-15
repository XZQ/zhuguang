"""Verify and render sealed evidence offline. Does not execute a scenario or write its databases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dianxun.replay import render_run, verify_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    result = render_run(args.bundle, args.html) if args.html else verify_run(args.bundle)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
