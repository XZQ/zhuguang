"""Developer CLI for state initialization, scenario injection and MCP calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .domain import PolicyEngine
from .mcp.p0 import DEFAULT_DB_PATH, DEFAULT_POLICY_PATH, DEFAULT_SEED_PATH, MCPService
from .mcp.server import TOOLS, tool_call
from .scenarios import ScenarioEngine
from .state import StateStore


def _path(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dianxun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("state-init", help="reset runtime.db from a deterministic seed")
    init.add_argument("--db", type=_path, default=DEFAULT_DB_PATH)
    init.add_argument("--seed", type=_path, default=DEFAULT_SEED_PATH)

    scenario = subparsers.add_parser("scenario-reset", help="reset and apply minute-zero events")
    scenario.add_argument("scenario", type=_path)
    scenario.add_argument("--db", type=_path, default=DEFAULT_DB_PATH)

    subparsers.add_parser("mcp-tools", help="print the exact P0 MCP tool names")

    call = subparsers.add_parser("mcp-call", help="call one stateful MCP function directly")
    call.add_argument("tool", choices=sorted(TOOLS))
    call.add_argument("--arguments", required=True, help="JSON object")
    call.add_argument("--actor", help="trusted local actor for Human/ScenarioEngine tests")
    call.add_argument("--db", type=_path, default=DEFAULT_DB_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    if args.command == "state-init":
        digest = StateStore(args.db).initialize_from_file(args.seed, reset=True)
        _print_json({"db": str(args.db), "seed": str(args.seed), "seed_digest": digest})
        return 0
    if args.command == "scenario-reset":
        store = StateStore(args.db)
        service = MCPService(
            store,
            PolicyEngine(DEFAULT_POLICY_PATH),
            auto_initialize_seed=DEFAULT_SEED_PATH,
        )
        engine = ScenarioEngine(store, args.scenario, service=service)
        digest = engine.reset()
        _print_json(
            {
                "db": str(args.db),
                "scenario": engine.scenario["scenario_id"],
                "seed_digest": digest,
                "virtual_time": store.now(),
            }
        )
        return 0
    if args.command == "mcp-tools":
        _print_json({"count": len(TOOLS), "tools": list(TOOLS)})
        return 0
    if args.command == "mcp-call":
        try:
            arguments = json.loads(args.arguments)
        except json.JSONDecodeError as exc:
            print(f"Invalid --arguments JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(arguments, dict):
            print("--arguments must be a JSON object", file=sys.stderr)
            return 2
        service = MCPService(
            StateStore(args.db),
            PolicyEngine(DEFAULT_POLICY_PATH),
            auto_initialize_seed=DEFAULT_SEED_PATH,
        )
        result = tool_call(args.tool, arguments, actor=args.actor, service=service)
        _print_json(result)
        return 1 if result["isError"] else 0
    raise AssertionError(f"Unhandled command {args.command}")


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _configure_stdio() -> None:
    if os.name == "nt":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure:
                reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
