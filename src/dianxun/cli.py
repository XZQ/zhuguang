"""Developer CLI for state initialization, scenario injection and MCP calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .adapters import LocalDemoAdapter
from .domain import PolicyEngine
from .evaluation import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_SCENARIO_DIR,
    evaluate_suite,
    write_evaluation_artifacts,
)
from .mcp.p0 import (
    DEFAULT_DB_PATH,
    DEFAULT_POLICY_PATH,
    DEFAULT_SCENARIO_PATH,
    DEFAULT_SEED_PATH,
    MCPService,
)
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

    demo = subparsers.add_parser("demo-run", help="run one five-phase cold-chain scenario")
    demo.add_argument("scenario", nargs="?", type=_path, default=DEFAULT_SCENARIO_PATH)
    demo.add_argument("--db", type=_path, default=DEFAULT_DB_PATH)
    demo.add_argument("--output", type=_path, help="optional JSON result path")

    evaluate = subparsers.add_parser("evaluate", help="run the deterministic six-scenario gate")
    evaluate.add_argument("--scenario-dir", type=_path, default=DEFAULT_SCENARIO_DIR)
    evaluate.add_argument("--output-dir", type=_path, default=DEFAULT_EVIDENCE_DIR)

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
    if args.command == "evaluate":
        evaluation = evaluate_suite(args.scenario_dir)
        json_path, report_path = write_evaluation_artifacts(evaluation, args.output_dir)
        _print_json(
            {
                "suite_id": evaluation["suite_id"],
                "gate": evaluation["local_m4_gate"],
                "metrics": evaluation["metrics"],
                "results": str(json_path),
                "report": str(report_path),
            }
        )
        return 0 if evaluation["local_m4_gate"]["passed"] else 1
    if args.command == "demo-run":
        result = LocalDemoAdapter(db_path=args.db, scenario_path=args.scenario).run()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        _print_json(
            {
                "scenario_id": result["scenario_id"],
                "result": result["result"],
                "trace_id": result["trace_id"],
                "incident_status": result["incident"]["incident_status"],
                "phase": result["incident"]["phase"],
                "work_status": result["incident"]["work_status"],
                "acceptance": result["acceptance"],
                "output": str(args.output) if args.output else None,
            }
        )
        return 0 if result["acceptance"]["passed"] else 1
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
