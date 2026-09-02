#!/usr/bin/env python3
"""Run a deterministic local SQLite coordination recovery drill."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dianxun.context_bus import ContextBus, ContextVersionConflict  # noqa: E402
from dianxun.coordination import (  # noqa: E402
    PHASE_ORDER,
    ActiveLeaseError,
    ContextCoordinator,
)

DEFAULT_OUTPUT = ROOT / "evidence" / "operations" / "recovery-drill.json"
ANCHOR = datetime(2026, 9, 3, 0, 0, tzinfo=UTC)
TASK_ID = "RECOVERY-DRILL-001"
TENANT_ID = "local-recovery-drill"


def run_recovery_drill() -> dict[str, object]:
    """Exercise WAL, optimistic locking, leases, reassignment and restart recovery."""
    with tempfile.TemporaryDirectory(prefix="dianxun-recovery-") as temporary:
        database_path = Path(temporary) / "coordination.db"
        first_bus = ContextBus(tenant_id=TENANT_ID, database_path=database_path)
        first_bus.create(
            TASK_ID,
            "trace-recovery-drill",
            trigger="deterministic_local_drill",
            scope={"store_ids": ["S03"]},
            ttl_seconds=3600,
            now=ANCHOR,
        )

        with closing(sqlite3.connect(database_path)) as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        _require(journal_mode == "wal", "SQLite coordination database did not use WAL")

        second_bus = ContextBus(tenant_id=TENANT_ID, database_path=database_path)
        primary_writer = first_bus.get(TASK_ID, now=ANCHOR)
        stale_writer = second_bus.get(TASK_ID, now=ANCHOR)
        primary_writer.scope["writer"] = "primary"
        first_bus.commit(primary_writer, now=ANCHOR + timedelta(seconds=1))
        stale_writer.scope["writer"] = "stale"
        stale_writer_denied = False
        try:
            second_bus.commit(stale_writer, now=ANCHOR + timedelta(seconds=2))
        except ContextVersionConflict:
            stale_writer_denied = True
        _require(stale_writer_denied, "stale optimistic writer unexpectedly committed")
        _require(
            first_bus.get(TASK_ID, now=ANCHOR).scope["writer"] == "primary",
            "stale writer changed durable context",
        )

        coordinator = ContextCoordinator(first_bus)
        predecessor = coordinator.assign(
            TASK_ID,
            "DETECT_CONTAIN",
            "Sentry-1",
            lease_seconds=10,
            now=ANCHOR + timedelta(seconds=2),
        )
        active_lease_denied = False
        try:
            coordinator.reassign_expired(
                TASK_ID,
                predecessor.assignment_id,
                "Sentry-2",
                lease_seconds=30,
                now=ANCHOR + timedelta(seconds=11),
            )
        except ActiveLeaseError:
            active_lease_denied = True
        _require(active_lease_denied, "valid lease was reassigned")

        def recover(worker: str):
            recovery_bus = ContextBus(tenant_id=TENANT_ID, database_path=database_path)
            return ContextCoordinator(recovery_bus).reassign_expired(
                TASK_ID,
                predecessor.assignment_id,
                worker,
                lease_seconds=30,
                now=ANCHOR + timedelta(seconds=13),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            successor, duplicate = executor.map(recover, ("Sentry-2", "Sentry-3"))
        _require(
            successor.assignment_id == duplicate.assignment_id,
            "timeout recovery created more than one successor",
        )
        coordinator.complete(
            TASK_ID,
            successor.assignment_id,
            successor.worker,
            evidence_refs=["evidence://recovery/detect-contain"],
            output_ref="artifact://recovery/detect-contain",
            now=ANCHOR + timedelta(seconds=14),
        )

        restarted_bus = ContextBus(tenant_id=TENANT_ID, database_path=database_path)
        restarted = ContextCoordinator(restarted_bus)
        resume_plan = restarted.resume_plan(TASK_ID, now=ANCHOR + timedelta(seconds=15))
        expected_resume_plan = list(PHASE_ORDER[1:])
        _require(resume_plan == expected_resume_plan, "restart did not recover checkpoint prefix")

        workers = {
            "DIAGNOSE_DECIDE": "Diagnoser",
            "EXECUTE": "Executor",
            "VERIFY": "Auditor",
            "LEARN": "Auditor",
        }
        for index, phase in enumerate(resume_plan, start=1):
            assigned_at = ANCHOR + timedelta(seconds=20 + index * 2)
            assignment = restarted.assign(
                TASK_ID,
                phase,
                workers[phase],
                lease_seconds=30,
                now=assigned_at,
            )
            restarted.complete(
                TASK_ID,
                assignment.assignment_id,
                workers[phase],
                evidence_refs=[f"evidence://recovery/{phase.casefold()}"],
                output_ref=f"artifact://recovery/{phase.casefold()}",
                now=assigned_at + timedelta(seconds=1),
            )

        final_context = restarted_bus.get(TASK_ID, now=ANCHOR + timedelta(seconds=40))
        checkpoint_order = [phase for phase in PHASE_ORDER if phase in final_context.checkpoints]
        successor_count = sum(
            item.predecessor_assignment_id == predecessor.assignment_id
            for item in final_context.assignments
        )
        _require(final_context.coordination_status == "completed", "drill did not complete")
        _require(checkpoint_order == list(PHASE_ORDER), "five-stage checkpoint order changed")
        _require(successor_count == 1, "predecessor has a non-unique successor")

        return {
            "schema_version": "1.0",
            "drill_id": "local-sqlite-coordination-recovery-v1",
            "virtual_anchor_time": "2026-09-03T00:00:00Z",
            "environment": {
                "backend": "sqlite",
                "clock": "deterministic_virtual_time",
                "journal_mode": journal_mode,
            },
            "checks": {
                "sqlite_wal": True,
                "stale_writer_denied": stale_writer_denied,
                "valid_lease_reassignment_denied": active_lease_denied,
                "expired_assignment_has_one_successor": successor_count == 1,
                "checkpoint_recovered_after_restart": resume_plan == expected_resume_plan,
                "five_stage_completion": final_context.coordination_status == "completed",
            },
            "recovery": {
                "predecessor_assignment_id": predecessor.assignment_id,
                "successor_assignment_id": successor.assignment_id,
                "successor_attempt": successor.attempt,
                "resume_plan_after_restart": resume_plan,
            },
            "final": {
                "coordination_status": final_context.coordination_status,
                "context_version": final_context.version,
                "checkpoint_order": checkpoint_order,
                "checkpoint_versions": {
                    phase: final_context.checkpoints[phase].context_version
                    for phase in checkpoint_order
                },
                "assignment_statuses": [item.status for item in final_context.assignments],
            },
            "claim_boundary": (
                "Deterministic local SQLite control-plane drill only; not evidence of AgentTeams, "
                "managed PolarDB, OSS disaster recovery, or production SLO attainment."
            ),
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _render(result: dict[str, object]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the drill and require the tracked evidence to match without writing it",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_recovery_drill()
    rendered = _render(result)
    output = args.output.resolve()
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            print(f"恢复演练证据缺失或已过期：{output}", file=sys.stderr)
            return 1
        print(f"恢复演练与证据一致：{output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": all(result["checks"].values()),
                "context_version": result["final"]["context_version"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
