"""Developer CLI for state initialization, scenario injection and MCP calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .adapters import LocalDemoAdapter
from .agentteams_evidence import verify_agentteams_evidence
from .domain import PolicyEngine
from .evaluation import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_SCENARIO_DIR,
    evaluate_suite,
    write_evaluation_artifacts,
)
from .knowledge import KnowledgeService, embedding_provider_from_env, evaluate_retrieval
from .mcp.p0 import (
    DEFAULT_DB_PATH,
    DEFAULT_POLICY_PATH,
    DEFAULT_SCENARIO_PATH,
    DEFAULT_SEED_PATH,
    MCPService,
)
from .mcp.server import P1_TOOLS, TOOLS, tool_call
from .scenarios import ScenarioEngine
from .state import PostgresStateStore, create_state_store


def _path(value: str) -> Path:
    return Path(value).resolve()


def _database_target(value: str) -> str | Path:
    if value.startswith(("postgresql://", "postgres://")):
        return value
    return _path(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dianxun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("state-init", help="reset runtime.db from a deterministic seed")
    init.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    init.add_argument("--seed", type=_path, default=DEFAULT_SEED_PATH)
    init.add_argument("--allow-remote-reset", action="store_true")

    scenario = subparsers.add_parser("scenario-reset", help="reset and apply minute-zero events")
    scenario.add_argument("scenario", type=_path)
    scenario.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    scenario.add_argument("--allow-remote-reset", action="store_true")

    demo = subparsers.add_parser("demo-run", help="run one five-phase cold-chain scenario")
    demo.add_argument("scenario", nargs="?", type=_path, default=DEFAULT_SCENARIO_PATH)
    demo.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    demo.add_argument("--allow-remote-reset", action="store_true")
    demo.add_argument("--enable-rag", action="store_true")
    demo.add_argument("--output", type=_path, help="optional JSON result path")

    evaluate = subparsers.add_parser("evaluate", help="run the deterministic six-scenario gate")
    evaluate.add_argument("--scenario-dir", type=_path, default=DEFAULT_SCENARIO_DIR)
    evaluate.add_argument("--output-dir", type=_path, default=DEFAULT_EVIDENCE_DIR)

    mcp_tools = subparsers.add_parser("mcp-tools", help="print P0 and optional P1 tools")
    mcp_tools.add_argument("--include-p1", action="store_true")

    call = subparsers.add_parser("mcp-call", help="call one stateful MCP function directly")
    call.add_argument("tool", choices=sorted({**TOOLS, **P1_TOOLS}))
    call.add_argument("--arguments", required=True, help="JSON object")
    call.add_argument("--actor", help="trusted local actor for Human/ScenarioEngine tests")
    call.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)

    bootstrap = subparsers.add_parser(
        "db-bootstrap",
        help="apply an allow-listed PostgreSQL/PolarDB migration profile",
    )
    bootstrap.add_argument(
        "--database-url",
        default=os.environ.get("DIANXUN_DATABASE_URL"),
        help="PostgreSQL URL; defaults to DIANXUN_DATABASE_URL",
    )
    bootstrap.add_argument(
        "--profile",
        action="append",
        choices=("core", "security", "cron", "archive"),
        required=True,
    )

    knowledge_list = subparsers.add_parser(
        "knowledge-list",
        help="list knowledge candidates and their review state",
    )
    knowledge_list.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    knowledge_list.add_argument("--tenant-id", required=True)
    knowledge_list.add_argument(
        "--status",
        choices=("pending", "published", "rejected"),
    )

    knowledge_review = subparsers.add_parser(
        "knowledge-review",
        help="apply a trusted human review decision to one knowledge candidate",
    )
    knowledge_review.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    knowledge_review.add_argument("--knowledge-id", required=True)
    knowledge_review.add_argument("--decision", choices=("approve", "reject"), required=True)
    knowledge_review.add_argument("--reviewer", required=True)
    knowledge_review.add_argument("--reason", required=True)
    knowledge_review.add_argument("--redaction-passed", action="store_true")

    knowledge_search = subparsers.add_parser(
        "knowledge-search",
        help="search only published, redaction-passed knowledge",
    )
    knowledge_search.add_argument("query")
    knowledge_search.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    knowledge_search.add_argument("--tenant-id", required=True)
    knowledge_search.add_argument("--top-k", type=int, default=3)

    knowledge_evaluate = subparsers.add_parser(
        "knowledge-evaluate",
        help="compute Recall@K and MRR for a labeled retrieval dataset",
    )
    knowledge_evaluate.add_argument("dataset", type=_path)
    knowledge_evaluate.add_argument("--db", type=_database_target, default=DEFAULT_DB_PATH)
    knowledge_evaluate.add_argument("--tenant-id", required=True)
    knowledge_evaluate.add_argument("--top-k", type=int, default=3)

    runtime_evidence = subparsers.add_parser(
        "agentteams-verify",
        help="verify redacted evidence captured from real AgentTeams runs",
    )
    runtime_evidence.add_argument("evidence", type=_path)
    runtime_evidence.add_argument("--output", type=_path)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    if args.command == "state-init":
        store = create_state_store(args.db)
        _require_remote_reset(store, args.allow_remote_reset)
        digest = store.initialize_from_file(args.seed, reset=True)
        _print_json(
            {
                "backend": store.backend_name,
                "database": store.database_identity,
                "seed": str(args.seed),
                "seed_digest": digest,
            }
        )
        return 0
    if args.command == "scenario-reset":
        store = create_state_store(args.db)
        _require_remote_reset(store, args.allow_remote_reset)
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
        tools = {**TOOLS, **P1_TOOLS} if args.include_p1 else TOOLS
        _print_json(
            {
                "count": len(tools),
                "p0_count": len(TOOLS),
                "p1_count": len(P1_TOOLS) if args.include_p1 else 0,
                "tools": list(tools),
            }
        )
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
        store = create_state_store(args.db)
        _require_remote_reset(store, args.allow_remote_reset)
        result = LocalDemoAdapter(
            db_path=args.db,
            scenario_path=args.scenario,
            enable_rag=args.enable_rag,
        ).run()
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
        store = create_state_store(args.db)
        knowledge = None
        if args.tool in P1_TOOLS:
            os.environ["DIANXUN_ENABLE_P1_TOOLS"] = "1"
            knowledge = KnowledgeService(store, embedding_provider_from_env())
        service = MCPService(
            store,
            PolicyEngine(DEFAULT_POLICY_PATH),
            auto_initialize_seed=DEFAULT_SEED_PATH,
            knowledge=knowledge,
        )
        result = tool_call(args.tool, arguments, actor=args.actor, service=service)
        _print_json(result)
        return 1 if result["isError"] else 0
    if args.command == "db-bootstrap":
        if not args.database_url:
            print("--database-url or DIANXUN_DATABASE_URL is required", file=sys.stderr)
            return 2
        store = create_state_store(args.database_url, runtime_role="hq")
        if not isinstance(store, PostgresStateStore):
            print("db-bootstrap only supports PostgreSQL/PolarDB URLs", file=sys.stderr)
            return 2
        for profile in args.profile:
            store.apply_profile(profile)
        _print_json(
            {
                "backend": store.backend_name,
                "database": store.database_identity,
                "profiles": args.profile,
            }
        )
        return 0
    if args.command.startswith("knowledge-"):
        store = create_state_store(args.db)
        service = KnowledgeService(store, embedding_provider_from_env())
        if args.command == "knowledge-list":
            _print_json(service.list_items(tenant_id=args.tenant_id, review_status=args.status))
            return 0
        if args.command == "knowledge-review":
            result = service.review_candidate(
                knowledge_id=args.knowledge_id,
                decision=args.decision,
                reviewer=args.reviewer,
                reason=args.reason,
                redaction_passed=args.redaction_passed,
            )
            _print_json(result)
            return 0
        if args.command == "knowledge-search":
            _print_json(
                service.search(tenant_id=args.tenant_id, query=args.query, top_k=args.top_k)
            )
            return 0
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        cases = dataset["cases"] if isinstance(dataset, dict) else dataset
        if not isinstance(cases, list):
            print("knowledge dataset must be a list or an object with cases", file=sys.stderr)
            return 2
        result = evaluate_retrieval(
            service,
            tenant_id=args.tenant_id,
            cases=cases,
            top_k=args.top_k,
        )
        if isinstance(dataset, dict) and dataset.get("dataset_label"):
            result["dataset_label"] = dataset["dataset_label"]
        _print_json(result)
        return 0
    if args.command == "agentteams-verify":
        bundle = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = verify_agentteams_evidence(bundle)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        _print_json(result)
        return 0 if result["passed"] else 1
    raise AssertionError(f"Unhandled command {args.command}")


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _configure_stdio() -> None:
    if os.name == "nt":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure:
                reconfigure(encoding="utf-8", errors="replace")


def _require_remote_reset(store, allowed: bool) -> None:
    if store.backend_name == "postgresql" and not allowed:
        raise SystemExit("Refusing to reset a remote PostgreSQL store without --allow-remote-reset")


if __name__ == "__main__":
    raise SystemExit(main())
