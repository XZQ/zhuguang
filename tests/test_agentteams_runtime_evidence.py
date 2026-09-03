from __future__ import annotations

import json
import unittest
from pathlib import Path

from dianxun.agentteams_evidence import verify_agentteams_evidence

ROOT = Path(__file__).resolve().parents[1]


class AgentTeamsRuntimeEvidenceTests(unittest.TestCase):
    def test_complete_observed_bundle_passes_and_is_correlated(self) -> None:
        result = verify_agentteams_evidence(self._bundle())
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["checks"]["package_source_commit_matches_repository"])
        self.assertTrue(result["checks"]["runtime_disclosed"])
        self.assertTrue(result["checks"]["runtime_skills_loaded"])
        self.assertTrue(result["checks"]["security_negative_and_positive_cases"])
        self.assertTrue(result["runs"][0]["independent_verification_chain"])
        self.assertTrue(result["runs"][0]["mcp_actor_identity_bound"])
        self.assertTrue(result["runs"][0]["approval_timeline_valid"])
        self.assertEqual(2, len(result["runs"]))

    def test_bundle_cannot_hide_secret_or_substitute_template_status(self) -> None:
        secret = self._bundle()
        secret["token"] = "Bearer not-redacted-value"
        result = verify_agentteams_evidence(secret)
        self.assertFalse(result["passed"])
        self.assertTrue(any("secret-bearing" in error for error in result["errors"]))

        template = self._bundle()
        template["capture_status"] = "template"
        result = verify_agentteams_evidence(template)
        self.assertFalse(result["passed"])
        self.assertTrue(any("constant" in error for error in result["errors"]))

    def test_bundle_rejects_role_phase_mismatch_and_placeholder_trace(self) -> None:
        mismatched = self._bundle()
        mismatched["runs"][0]["handoffs"][-1]["phase"] = "EXECUTE"
        result = verify_agentteams_evidence(mismatched)
        self.assertFalse(result["passed"])
        self.assertIn(
            "failed check: runs_pass_runtime_gate",
            result["errors"],
        )

        wrong_tool_role = self._bundle()
        wrong_tool_role["runs"][0]["tool_calls"][0]["tool"] = "create_workorder"
        wrong_tool_role["runs"][0]["tool_calls"][0]["audit_ref"] = "audit-wrong-role"
        result = verify_agentteams_evidence(wrong_tool_role)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["tool_roles_authorized"])

        wrong_skill_digest = self._bundle()
        wrong_skill_digest["runs"][0]["tool_calls"][0]["skill_digest"] = "f" * 64
        result = verify_agentteams_evidence(wrong_skill_digest)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["correlation_complete"])

        incomplete_chain = self._bundle()
        incomplete_chain["runs"][0]["tool_calls"] = [
            item
            for item in incomplete_chain["runs"][0]["tool_calls"]
            if item["tool"] != "release_sales_hold"
        ]
        result = verify_agentteams_evidence(incomplete_chain)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["business_chain_complete"])

        missing_post_release_check = self._bundle()
        release_calls = missing_post_release_check["runs"][0]["tool_calls"]
        release_index = next(
            index
            for index, item in enumerate(release_calls)
            if item["tool"] == "release_sales_hold"
        )
        release_calls[:] = [
            item
            for index, item in enumerate(release_calls)
            if not (index > release_index and item["tool"] == "query_inventory_batches")
        ]
        result = verify_agentteams_evidence(missing_post_release_check)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["independent_verification_chain"])

        wrong_bound_actor = self._bundle()
        wrong_bound_actor["runs"][0]["tool_calls"][0]["authenticated_actor"] = "Executor"
        result = verify_agentteams_evidence(wrong_bound_actor)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["mcp_actor_identity_bound"])

        approval_before_request = self._bundle()
        approval_before_request["runs"][0]["approval"]["at"] = "2026-08-28T12:15:00+08:00"
        result = verify_agentteams_evidence(approval_before_request)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["approval_timeline_valid"])

        premature_final_state = self._bundle()
        premature_final_state["runs"][0]["final_state"]["observed_at"] = "2026-08-28T12:25:00+08:00"
        result = verify_agentteams_evidence(premature_final_state)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["final_state_evidenced"])

        missing_platform_id = self._bundle()
        del missing_platform_id["runs"][0]["project_id"]
        result = verify_agentteams_evidence(missing_platform_id)
        self.assertFalse(result["passed"])
        self.assertTrue(any("project_id" in error for error in result["errors"]))

        placeholder = self._bundle()
        placeholder["runs"][0]["trace_artifact"]["sha256"] = "0" * 64
        result = verify_agentteams_evidence(placeholder)
        self.assertFalse(result["passed"])
        self.assertTrue(any("does not match pattern" in error for error in result["errors"]))

    def test_bundle_requires_restart_checkpoint_and_single_timeout_successor(self) -> None:
        no_resume = self._bundle()
        for run in no_resume["runs"]:
            run["coordination"]["resumed_from_checkpoint"] = False
            run["coordination"]["resume_evidence_ref"] = None
        result = verify_agentteams_evidence(no_resume)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["checkpoint_resume_observed"])

        invalid_successor = self._bundle()
        successor = next(
            item
            for item in invalid_successor["runs"][1]["coordination"]["assignments"]
            if item["predecessor_assignment_id"] is not None
        )
        successor["attempt"] = 3
        result = verify_agentteams_evidence(invalid_successor)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][1]["coordination_integrity"])

        early_successor = self._bundle()
        successor = next(
            item
            for item in early_successor["runs"][1]["coordination"]["assignments"]
            if item["predecessor_assignment_id"] is not None
        )
        successor["assigned_at"] = "2026-08-28T12:01:30+08:00"
        result = verify_agentteams_evidence(early_successor)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][1]["coordination_integrity"])

        out_of_order = self._bundle()
        checkpoints = out_of_order["runs"][0]["coordination"]["checkpoints"]
        checkpoints[0], checkpoints[1] = checkpoints[1], checkpoints[0]
        result = verify_agentteams_evidence(out_of_order)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][0]["coordination_integrity"])

        orphaned_timeout = self._bundle()
        assignments = orphaned_timeout["runs"][1]["coordination"]["assignments"]
        assignments[:] = [item for item in assignments if item["predecessor_assignment_id"] is None]
        result = verify_agentteams_evidence(orphaned_timeout)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runs"][1]["coordination_integrity"])

    @staticmethod
    def _bundle() -> dict:
        package_hash = (
            (ROOT / "dist" / "dianxun-worker.zip.sha256").read_text(encoding="ascii").split()[0]
        )
        provenance = json.loads(
            (ROOT / "dist" / "dianxun-worker.provenance.json").read_text(encoding="utf-8")
        )
        versions = {item["name"]: item["version"] for item in provenance["skills"]}
        digests = {item["name"]: item["sha256"] for item in provenance["skills"]}
        facts = json.loads((ROOT / "config" / "project-facts.json").read_text(encoding="utf-8"))
        package_source_commit = facts["implementation"]["m3_repository_artifacts"][
            "worker_package_source_commit"
        ]
        resources = {
            "manager": {
                "name": "dianxun-manager",
                "status": "Running",
                "evidence_ref": "artifact:manager",
            },
            "team": {
                "name": "dianxun-patrol-team",
                "status": "Running",
                "evidence_ref": "artifact:team",
            },
            "workers": [
                {"name": name, "status": "Running", "evidence_ref": f"artifact:{name}"}
                for name in ("orchestrator", "sentry", "diagnoser", "executor", "auditor")
            ],
        }
        skill_loads = [
            {
                "worker": worker,
                "skill": skill,
                "version": versions[skill],
                "skill_digest": digests[skill],
                "package_sha256": package_hash,
                "loaded_at": "2026-08-28T12:00:00+08:00",
                "evidence_ref": f"artifact:skill-load-{worker}-{skill}",
            }
            for worker, skill in (
                ("sentry", "anomaly-detect"),
                ("diagnoser", "coldchain-risk-assess"),
                ("diagnoser", "rootcause-drilldown"),
                ("executor", "work-order-dispatch"),
                ("auditor", "outcome-verify"),
                ("auditor", "review-report"),
            )
        ]
        return {
            "schema_version": "1.3",
            "evidence_kind": "agentteams_runtime",
            "capture_status": "observed",
            "captured_at": "2026-08-28T13:10:00+08:00",
            "agentteams_version": "v1.2.3",
            "package_source_commit": package_source_commit,
            "package_sha256": package_hash,
            "runtime": {
                "manager_runtime": "qwenpaw",
                "worker_runtime": "qwenpaw",
                "model": "qwen3.5-plus",
                "provider": "qwen",
                "credential_source_type": "gateway",
                "usage_status": "not_measured",
                "evidence_ref": "artifact:runtime-config",
            },
            "resources": resources,
            "skill_loads": skill_loads,
            "security_checks": [
                {
                    "check": "missing_token",
                    "expected": 401,
                    "observed": 401,
                    "at": "2026-08-28T12:01:00+08:00",
                    "evidence_ref": "artifact:auth-1",
                },
                {
                    "check": "wrong_token",
                    "expected": 401,
                    "observed": 401,
                    "at": "2026-08-28T12:02:00+08:00",
                    "evidence_ref": "artifact:auth-2",
                },
                {
                    "check": "wrong_role",
                    "expected": "FORBIDDEN",
                    "observed": "FORBIDDEN",
                    "at": "2026-08-28T12:03:00+08:00",
                    "evidence_ref": "artifact:auth-3",
                },
                {
                    "check": "authorized_actor_audited",
                    "expected": True,
                    "observed": True,
                    "at": "2026-08-28T12:04:00+08:00",
                    "evidence_ref": "artifact:auth-4",
                },
            ],
            "runs": [
                AgentTeamsRuntimeEvidenceTests._run("success", "CLOSED", "COMPLETED", False),
                AgentTeamsRuntimeEvidenceTests._run("failure", "BLOCKED", "BLOCKED", True),
            ],
        }

    @staticmethod
    def _run(
        branch: str,
        incident_status: str,
        work_status: str,
        partial: bool,
    ) -> dict:
        incident_id = f"incident-{branch}"
        trace_id = f"trace-{branch}"
        provenance = json.loads(
            (ROOT / "dist" / "dianxun-worker.provenance.json").read_text(encoding="utf-8")
        )
        versions = {item["name"]: item["version"] for item in provenance["skills"]}
        digests = {item["name"]: item["sha256"] for item in provenance["skills"]}
        phases = (
            ("manager", "orchestrator", "DETECT_CONTAIN"),
            ("orchestrator", "sentry", "DETECT_CONTAIN"),
            ("orchestrator", "diagnoser", "DIAGNOSE_DECIDE"),
            ("orchestrator", "executor", "EXECUTE"),
            ("orchestrator", "auditor", "VERIFY"),
            ("orchestrator", "auditor", "LEARN"),
        )
        tool_steps = [
            ("sentry", "anomaly-detect", "query_device_context"),
            ("sentry", "anomaly-detect", "query_inventory_batches"),
            ("diagnoser", "coldchain-risk-assess", "query_inventory_batches"),
            ("diagnoser", "rootcause-drilldown", "query_device_context"),
            ("executor", "work-order-dispatch", "apply_sales_hold"),
            ("executor", "work-order-dispatch", "create_approval"),
            ("executor", "work-order-dispatch", "create_workorder"),
            ("executor", "work-order-dispatch", "apply_batch_disposition"),
            ("auditor", "outcome-verify", "query_device_context"),
            ("auditor", "outcome-verify", "query_inventory_batches"),
            ("auditor", "outcome-verify", "query_sales_holds"),
            ("auditor", "outcome-verify", "query_workorder"),
            ("auditor", "outcome-verify", "query_approval"),
        ]
        actors = {
            "sentry": "Sentry",
            "diagnoser": "Diagnoser",
            "executor": "Executor",
            "auditor": "Auditor",
        }
        if branch == "success":
            tool_steps.extend(
                [
                    ("executor", "work-order-dispatch", "release_sales_hold"),
                    ("auditor", "outcome-verify", "query_device_context"),
                    ("auditor", "outcome-verify", "query_inventory_batches"),
                    ("auditor", "outcome-verify", "query_sales_holds"),
                ]
            )
        phase_workers = {
            "DETECT_CONTAIN": "sentry",
            "DIAGNOSE_DECIDE": "diagnoser",
            "EXECUTE": "executor",
            "VERIFY": "auditor",
            "LEARN": "auditor",
        }
        successful_assignment_ids = {
            phase: f"assignment-{branch}-{phase.lower()}" for phase in phase_workers
        }
        assignments = [
            {
                "assignment_id": successful_assignment_ids[phase],
                "phase": phase,
                "worker": worker,
                "attempt": 1,
                "status": "succeeded",
                "assigned_at": "2026-08-28T12:00:00+08:00",
                "lease_expires_at": "2026-08-28T13:00:00+08:00",
                "heartbeat_at": "2026-08-28T12:20:00+08:00",
                "predecessor_assignment_id": None,
                "evidence_ref": f"artifact:assignment-{branch}-{phase.lower()}",
            }
            for phase, worker in phase_workers.items()
        ]
        if branch == "failure":
            expired_id = "assignment-failure-verify-expired"
            assignments.insert(
                -1,
                {
                    "assignment_id": expired_id,
                    "phase": "VERIFY",
                    "worker": "auditor",
                    "attempt": 1,
                    "status": "expired",
                    "assigned_at": "2026-08-28T12:00:00+08:00",
                    "lease_expires_at": "2026-08-28T12:02:00+08:00",
                    "heartbeat_at": "2026-08-28T12:01:00+08:00",
                    "predecessor_assignment_id": None,
                    "evidence_ref": "artifact:assignment-failure-verify-expired",
                },
            )
            verify_successor = next(
                item for item in assignments if item["assignment_id"].endswith("verify")
            )
            verify_successor["attempt"] = 2
            verify_successor["predecessor_assignment_id"] = expired_id
            verify_successor["assigned_at"] = "2026-08-28T12:03:00+08:00"
            verify_successor["heartbeat_at"] = "2026-08-28T12:20:00+08:00"
            verify_successor["lease_expires_at"] = "2026-08-28T13:00:00+08:00"

        return {
            "scenario_id": f"scenario-{branch}",
            "branch": branch,
            "project_id": f"project-{branch}",
            "source_room_id": "!dianxun-patrol:matrix.local",
            "incident_id": incident_id,
            "trace_id": trace_id,
            "coordination": {
                "tenant_id": "demo",
                "context_version": 13 if branch == "failure" else 12,
                "expires_at": "2026-08-28T13:00:00+08:00",
                "resumed_from_checkpoint": branch == "success",
                "resume_evidence_ref": (
                    "artifact:context-restart-success" if branch == "success" else None
                ),
                "assignments": assignments,
                "checkpoints": [
                    {
                        "phase": phase,
                        "assignment_id": successful_assignment_ids[phase],
                        "context_version": 3 + index * 2,
                        "at": f"2026-08-28T12:{30 + index:02d}:00+08:00",
                        "evidence_refs": [f"artifact:checkpoint-{branch}-{phase.lower()}"],
                    }
                    for index, phase in enumerate(phase_workers)
                ],
            },
            "handoffs": [
                {
                    "from": source,
                    "to": target,
                    "phase": phase,
                    "task_id": f"task-{branch}-{index}",
                    "message_id": f"message-{index}",
                    "at": f"2026-08-28T12:{index:02d}:00+08:00",
                    "evidence_ref": f"artifact:handoff-{branch}-{index}",
                }
                for index, (source, target, phase) in enumerate(phases, 1)
            ],
            "tool_calls": [
                {
                    "worker": worker,
                    "skill": skill,
                    "skill_version": versions[skill],
                    "skill_digest": digests[skill],
                    "tool": tool,
                    "request_id": f"request-{branch}-{index}",
                    "incident_id": incident_id,
                    "trace_id": trace_id,
                    "authenticated_actor": actors[worker],
                    "authentication_mode": "actor_bound",
                    "auth_evidence_ref": f"artifact:mcp-auth-{branch}-{index}",
                    "at": f"2026-08-28T12:{10 + index:02d}:00+08:00",
                    "ok": not (partial and tool == "query_workorder"),
                    "partial": partial and tool == "query_workorder",
                    "audit_ref": (
                        f"audit-{branch}-{index}"
                        if tool
                        in {
                            "apply_sales_hold",
                            "apply_batch_disposition",
                            "create_approval",
                            "create_workorder",
                            "release_sales_hold",
                        }
                        else None
                    ),
                    "evidence_ref": f"artifact:tool-{branch}-{index}",
                }
                for index, (worker, skill, tool) in enumerate(tool_steps, 1)
            ],
            "approval": {
                "status": "approved",
                "actor_type": "human",
                "decision_id": f"approval-{branch}",
                "at": "2026-08-28T12:20:00+08:00",
                "evidence_ref": f"artifact:approval-{branch}",
            },
            "final_state": {
                "incident_status": incident_status,
                "work_status": work_status,
                "sales_hold_status": "active" if partial else "released",
                "observed_at": "2026-08-28T12:40:00+08:00",
                "evidence_ref": f"artifact:final-state-{branch}",
            },
            "trace_artifact": {
                "uri": f"evidence/{branch}-trace.json",
                "sha256": "1" * 64,
                "redacted": True,
            },
        }


if __name__ == "__main__":
    unittest.main()
