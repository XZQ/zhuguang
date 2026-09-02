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
        self.assertTrue(result["checks"]["runtime_skills_loaded"])
        self.assertTrue(result["checks"]["security_negative_and_positive_cases"])
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

        placeholder = self._bundle()
        placeholder["runs"][0]["trace_artifact"]["sha256"] = "0" * 64
        result = verify_agentteams_evidence(placeholder)
        self.assertFalse(result["passed"])
        self.assertTrue(any("does not match pattern" in error for error in result["errors"]))

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
            "schema_version": "1.1",
            "evidence_kind": "agentteams_runtime",
            "capture_status": "observed",
            "captured_at": "2026-08-28T12:10:00+08:00",
            "agentteams_version": "v1.2.3",
            "package_sha256": package_hash,
            "resources": resources,
            "skill_loads": skill_loads,
            "security_checks": [
                {
                    "check": "missing_token",
                    "expected": 401,
                    "observed": 401,
                    "evidence_ref": "artifact:auth-1",
                },
                {
                    "check": "wrong_token",
                    "expected": 401,
                    "observed": 401,
                    "evidence_ref": "artifact:auth-2",
                },
                {
                    "check": "wrong_role",
                    "expected": "FORBIDDEN",
                    "observed": "FORBIDDEN",
                    "evidence_ref": "artifact:auth-3",
                },
                {
                    "check": "authorized_actor_audited",
                    "expected": True,
                    "observed": True,
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
            ("diagnoser", "rootcause-drilldown", "query_device_context"),
            ("executor", "work-order-dispatch", "apply_sales_hold"),
            ("executor", "work-order-dispatch", "create_approval"),
            ("executor", "work-order-dispatch", "create_workorder"),
            ("auditor", "outcome-verify", "query_workorder"),
        ]
        if branch == "success":
            tool_steps.extend(
                [
                    ("executor", "work-order-dispatch", "release_sales_hold"),
                    ("auditor", "outcome-verify", "query_sales_holds"),
                ]
            )
        return {
            "scenario_id": f"scenario-{branch}",
            "branch": branch,
            "incident_id": incident_id,
            "trace_id": trace_id,
            "handoffs": [
                {
                    "from": source,
                    "to": target,
                    "phase": phase,
                    "message_id": f"message-{index}",
                    "at": "2026-08-28T12:00:00+08:00",
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
                    "ok": not (partial and worker == "auditor"),
                    "partial": partial and worker == "auditor",
                    "audit_ref": (
                        f"audit-{branch}-{index}"
                        if tool
                        in {
                            "apply_sales_hold",
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
                "evidence_ref": f"artifact:approval-{branch}",
            },
            "final_state": {
                "incident_status": incident_status,
                "work_status": work_status,
                "sales_hold_status": "active" if partial else "released",
            },
            "trace_artifact": {
                "uri": f"evidence/{branch}-trace.json",
                "sha256": "1" * 64,
                "redacted": True,
            },
        }


if __name__ == "__main__":
    unittest.main()
