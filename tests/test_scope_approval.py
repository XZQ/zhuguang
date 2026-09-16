from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor

from tests import test_scope_revision


class ScopeApprovalTests(unittest.TestCase):
    setUp = test_scope_revision.ScopeRevisionTests.setUp
    initialize_store = test_scope_revision.ScopeRevisionTests.initialize_store
    request = test_scope_revision.ScopeRevisionTests.request
    revise = test_scope_revision.ScopeRevisionTests.revise

    def test_decision_racing_split_never_authorizes_children(self):
        result = self.runtime.mcp.create_approval(
            incident_id="I",
            action_id="dispose-1",
            subject="dispose",
            requested_action_type="apply_batch_disposition",
            disposition="disposed",
            target_batch_ids=[self.parent["batch_id"]],
            expected_scope_version=1,
            idempotency_key="race-create",
        )
        self.assertTrue(result["ok"], result)
        approval_id = result["data"]["approval_id"]
        request = self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            decision = pool.submit(
                self.runtime.mcp.decide_approval,
                approval_id=approval_id,
                decision="approved",
                reason="race",
                actor="Human",
                expected_scope_version=1,
                idempotency_key="race-decide",
            )
            revision = pool.submit(self.revise, request)
            self.assertEqual(2, revision.result()["versions"]["I"])
            result = decision.result()
        approval = self.store.list_approvals(approval_id=approval_id)[0]
        self.assertEqual("approved" if result["ok"] else "pending", approval["status"])
        self.assertEqual("requires_review", approval["applicability"])
        self.assertFalse(self.execute(approval_id, ["C1", "C2"], 2)["ok"])

    def approve(self, targets):
        mcp = self.runtime.mcp
        result = mcp.create_approval(
            incident_id="I",
            action_id="dispose-1",
            subject="dispose",
            requested_action_type="apply_batch_disposition",
            disposition="disposed",
            target_batch_ids=targets,
            expected_scope_version=1,
            idempotency_key="approve-create",
        )
        self.assertTrue(result["ok"], result)
        approval_id = result["data"]["approval_id"]
        result = mcp.decide_approval(
            approval_id=approval_id,
            decision="approved",
            reason="test",
            actor="Human",
            expected_scope_version=1,
            idempotency_key="approve-decide",
        )
        self.assertTrue(result["ok"], result)
        return approval_id

    def execute(self, approval_id, targets, version):
        return self.runtime.mcp.apply_batch_disposition(
            incident_id="I",
            action_id="dispose-1",
            batch_ids=targets,
            disposition="disposed",
            approval_id=approval_id,
            expected_scope_version=version,
            idempotency_key="dispose-execute",
        )

    def test_old_approval_cannot_be_redirected_to_children(self):
        approval_id = self.approve([self.parent["batch_id"]])
        self.revise(self.request())
        response = self.execute(approval_id, ["C1", "C2"], 2)
        self.assertFalse(response["ok"])
        self.assertEqual("unknown", self.store.list_batches(batch_ids=["C1"])[0]["disposition"])
        self.assertEqual(
            "approved", self.store.list_approvals(approval_id=approval_id)[0]["status"]
        )

    def test_unchanged_target_approval_survives_unrelated_scope_growth(self):
        approval_id = self.approve([self.parent["batch_id"]])
        batch = {
            k: self.parent[k]
            for k in (
                "sku_id",
                "product_name",
                "device_id",
                "storage_min_c",
                "storage_max_c",
                "policy_ref",
            )
        }
        batch.update(batch_id="NEW", quantity=3)
        self.revise(self.request(changes=[{"op": "add", "batch": batch}]))
        self.assertTrue(self.execute(approval_id, [self.parent["batch_id"]], 2)["ok"])
        self.assertEqual("unknown", self.store.list_batches(batch_ids=["NEW"])[0]["disposition"])

    def test_missing_scope_version_and_unbound_targets_cannot_create_v2_approval(self):
        mcp = self.runtime.mcp
        request = dict(
            incident_id="I",
            action_id="dispose-1",
            subject="dispose",
            requested_action_type="apply_batch_disposition",
            disposition="disposed",
            idempotency_key="unbound",
        )
        response = mcp.create_approval(**request)
        self.assertFalse(response["ok"])
        response = mcp.create_approval(**request, expected_scope_version=1)
        self.assertFalse(response["ok"])
        self.assertEqual([], self.store.list_approvals(incident_id="I"))

    def test_stale_scope_write_fails_but_exact_historical_replay_is_marked(self):
        approval_id = self.approve([self.parent["batch_id"]])
        self.assertTrue(self.execute(approval_id, [self.parent["batch_id"]], 1)["ok"])
        batch = {
            k: self.parent[k]
            for k in (
                "sku_id",
                "product_name",
                "device_id",
                "storage_min_c",
                "storage_max_c",
                "policy_ref",
            )
        }
        batch.update(batch_id="NEW", quantity=3)
        self.revise(self.request(changes=[{"op": "add", "batch": batch}]))
        result = self.execute(approval_id, [self.parent["batch_id"]], 1)
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["historical_replay"])
        response = self.runtime.mcp.apply_batch_disposition(
            incident_id="I",
            action_id="new",
            batch_ids=["NEW"],
            disposition="quarantined",
            expected_scope_version=1,
            idempotency_key="stale-new",
        )
        self.assertFalse(response["ok"])
        self.assertEqual("unknown", self.store.list_batches(batch_ids=["NEW"])[0]["disposition"])
