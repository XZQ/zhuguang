from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dianxun import trace
from dianxun.adapters import LocalDemoAdapter
from dianxun.knowledge import evaluate_retrieval
from dianxun.mcp.p0 import DEFAULT_SCENARIO_PATH
from dianxun.mcp.server import enabled_tools, tool_call


class KnowledgeFlywheelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.db_path = root / "runtime.db"
        self.trace_path = root / "trace.db"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_candidate_requires_human_review_before_retrieval(self) -> None:
        adapter = LocalDemoAdapter(
            db_path=self.db_path,
            scenario_path=DEFAULT_SCENARIO_PATH,
            trace_db_path=self.trace_path,
            enable_rag=True,
        )
        first = adapter.run()
        knowledge = first["review"]["knowledge"]
        self.assertEqual("pending", knowledge["candidate_status"])
        knowledge_id = knowledge["knowledge_id"]

        before = adapter.knowledge.search(
            tenant_id="demo",
            query="冷柜 压缩机故障 维修后复测",
        )
        self.assertEqual([], before["hits"])
        with self.assertRaises(PermissionError):
            adapter.knowledge.review_candidate(
                knowledge_id=knowledge_id,
                decision="approve",
                reviewer="Auditor",
                reason="self approval must fail",
                redaction_passed=True,
            )
        with self.assertRaises(ValueError):
            adapter.knowledge.review_candidate(
                knowledge_id=knowledge_id,
                decision="approve",
                reviewer="Human",
                reason="redaction missing",
                redaction_passed=False,
            )

        published = adapter.knowledge.review_candidate(
            knowledge_id=knowledge_id,
            decision="approve",
            reviewer="Human",
            reason="evidence and redaction reviewed",
            redaction_passed=True,
        )
        self.assertEqual("published", published["review_status"])
        self.assertEqual("passed", published["redaction_status"])

        second_adapter = LocalDemoAdapter(
            db_path=self.db_path,
            scenario_path=DEFAULT_SCENARIO_PATH,
            trace_db_path=self.trace_path,
            enable_rag=True,
        )
        second = second_adapter.run()
        hits = second["phases"]["DIAGNOSE_DECIDE"]["rag"]["hits"]
        self.assertTrue(hits)
        self.assertEqual(knowledge_id, hits[0]["knowledge_id"])
        self.assertIn("source", hits[0])
        self.assertTrue(hits[0]["source"]["incident_id"])

        metrics = evaluate_retrieval(
            second_adapter.knowledge,
            tenant_id="demo",
            cases=[
                {
                    "case_id": "compressor-history",
                    "query": "冷柜失温 压缩机故障",
                    "expected_knowledge_ids": [knowledge_id],
                }
            ],
        )
        self.assertEqual(1.0, metrics["recall_at_3"])
        self.assertEqual(1.0, metrics["mrr"])
        self.assertIn("not a real-store", metrics["claim_boundary"])

    def test_candidate_deduplicates_and_rejects_credential_like_text(self) -> None:
        adapter = LocalDemoAdapter(
            db_path=self.db_path,
            scenario_path=DEFAULT_SCENARIO_PATH,
            trace_db_path=self.trace_path,
            enable_rag=True,
        )
        run = adapter.run()
        service = adapter.knowledge
        values = {
            "tenant_id": "demo",
            "incident_id": "incident-extra",
            "trace_id": "trace-extra",
            "title": "冷柜门封条复核",
            "body": "门未关闭时保持停售，并在关闭后独立复测。",
            "tags": ["冷柜失温", "门未关闭"],
            "confidence": 0.8,
            "source_evidence_ids": ["evidence-1"],
        }
        first = service.create_candidate(**values)
        second = service.create_candidate(**values)
        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["knowledge_id"], second["knowledge_id"])
        with self.assertRaises(ValueError):
            service.create_candidate(
                **{
                    **values,
                    "title": "泄漏内容",
                    "body": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
                }
            )
        with self.assertRaises(ValueError):
            service.create_candidate(
                **{
                    **values,
                    "title": "标签泄漏",
                    "tags": ["api_key=should-not-enter-knowledge"],
                }
            )
        with self.assertRaises(ValueError):
            service.create_candidate(
                **{
                    **values,
                    "incident_id": run["incident"]["incident_id"],
                    "trace_id": run["trace_id"],
                    "title": "伪造证据引用",
                    "source_evidence_ids": ["evidence-not-linked-to-incident"],
                }
            )

        own_candidate = service.create_candidate(
            **{
                **values,
                "title": "独立审核约束",
                "created_by": "hq_reviewer",
            }
        )
        with self.assertRaises(PermissionError):
            service.review_candidate(
                knowledge_id=own_candidate["knowledge_id"],
                decision="approve",
                reviewer="hq_reviewer",
                reason="creator must not self-review",
                redaction_passed=True,
            )
        with self.assertRaises(ValueError):
            service.search(
                tenant_id="demo",
                query="冷柜",
                minimum_confidence=float("nan"),
            )

    def test_optional_p1_mcp_tools_keep_human_publication_boundary(self) -> None:
        adapter = LocalDemoAdapter(
            db_path=self.db_path,
            scenario_path=DEFAULT_SCENARIO_PATH,
            trace_db_path=self.trace_path,
            enable_rag=True,
        )
        result = adapter.run()
        knowledge_id = result["review"]["knowledge"]["knowledge_id"]
        arguments = {
            "knowledge_id": knowledge_id,
            "decision": "approve",
            "reason": "reviewed by a bound human identity",
            "redaction_passed": True,
            "runtime_trace_id": result["trace_id"],
        }
        with mock.patch.dict("os.environ", {"DIANXUN_ENABLE_P1_TOOLS": "1"}):
            self.assertEqual(15, len(enabled_tools()))
            invalid_search = tool_call(
                "search_knowledge",
                {"tenant_id": "demo", "query": "冷柜", "top_k": 21},
                actor="Diagnoser",
                service=adapter.mcp,
            )
            self.assertTrue(invalid_search["isError"])
            invalid_body = json.loads(invalid_search["content"][0]["text"])
            self.assertEqual("INVALID_ARGUMENT", invalid_body["error"]["code"])

            denied = tool_call(
                "review_knowledge_candidate",
                arguments,
                service=adapter.mcp,
            )
            self.assertTrue(denied["isError"])
            denied_body = json.loads(denied["content"][0]["text"])
            self.assertEqual("FORBIDDEN", denied_body["error"]["code"])

            with trace.use_database(self.trace_path):
                approved = tool_call(
                    "review_knowledge_candidate",
                    arguments,
                    actor="Human",
                    service=adapter.mcp,
                )
                spans = trace.query_trace(result["trace_id"])
            self.assertFalse(approved["isError"])
            approved_body = json.loads(approved["content"][0]["text"])
            self.assertEqual("published", approved_body["data"]["review_status"])
            self.assertTrue(approved_body["audit_ref"])
            audit = adapter.store.list_audit_log(incident_id=result["incident"]["incident_id"])
            self.assertTrue(
                any(item["tool_name"] == "review_knowledge_candidate" for item in audit)
            )
            self.assertTrue(
                any(
                    item["name"] == "review_knowledge_candidate" and item["kind"] == "mcp"
                    for item in spans
                )
            )


if __name__ == "__main__":
    unittest.main()
