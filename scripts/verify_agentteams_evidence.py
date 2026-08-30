"""Verify a redacted bundle captured from a real AgentTeams run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dianxun.agentteams_evidence import verify_agentteams_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = verify_agentteams_evidence(bundle)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
