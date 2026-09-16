from __future__ import annotations

import unittest
from copy import deepcopy

from dianxun.domain import scope


class ScopeVersioningTests(unittest.TestCase):
    def setUp(self):
        self.scope = scope
        self.parent = {
            "batch_id": "P",
            "store_id": "S03",
            "device_id": "D",
            "sku_id": "SKU",
            "quantity": 10,
            "policy_ref": "policy-v1",
            "lifecycle": "active",
            "disposition": "quarantined",
        }

    def snapshot(self, batches, **changes):
        return self.scope.build_scope_snapshot(
            **{
                "tenant_id": "demo",
                "store_id": "S03",
                "asset_ids": ["D"],
                "batches": batches,
                **changes,
            }
        )

    def test_snapshot_order_and_non_scope_metadata_do_not_change_identity(self):
        other = {**self.parent, "batch_id": "Q", "quantity": 3}
        first = self.snapshot([self.parent, other], asset_ids=["D2", "D"])
        second = self.snapshot(
            [{**other, "updated_at": "2026-09-16T10:00:00Z"}, self.parent],
            asset_ids=["D", "D2"],
        )
        self.assertEqual(["D", "D2"], first["asset_ids"])
        self.assertEqual(["P", "Q"], [r["batch_id"] for r in first["batches"]])
        self.assertEqual(first, second)
        self.assertEqual(self.scope.scope_digest(first), self.scope.scope_digest(second))
        first["batches"][0]["quantity"] = 1
        self.assertEqual(10, self.parent["quantity"])

    def test_quantity_location_policy_and_tenant_changes_change_identity(self):
        baseline = self.scope.scope_digest(self.snapshot([self.parent]))
        for key, value in (
            ("quantity", 9),
            ("device_id", "D2"),
            ("policy_ref", "v2"),
            ("sku_id", "OTHER"),
            ("batch_id", "OTHER"),
        ):
            with self.subTest(field=key):
                changed = self.snapshot([{**self.parent, key: value}])
                self.assertNotEqual(baseline, self.scope.scope_digest(changed))
        self.assertNotEqual(
            baseline, self.scope.scope_digest(self.snapshot([self.parent], tenant_id="other"))
        )

    def test_snapshot_rejects_cross_store_duplicates_and_invalid_quantities(self):
        for quantity in (True, False, -1, 1.5, "10", float("nan")):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.snapshot([{**self.parent, "quantity": quantity}])
        for batches in (
            [self.parent, self.parent],
            [{**self.parent, "store_id": "S04"}],
            [{**self.parent, "lifecycle": "retired"}],
            [{**self.parent, "policy_ref": ""}],
            [],
        ):
            with self.subTest(batches=batches), self.assertRaises(ValueError):
                self.snapshot(batches)
        for key in ("batch_id", "device_id", "sku_id", "quantity", "policy_ref"):
            row = dict(self.parent)
            del row[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                self.snapshot([row])

    def test_split_conserves_quantity_without_mutating_input(self):
        children = [
            {**self.parent, "batch_id": "C2", "quantity": 6},
            {**self.parent, "batch_id": "C1", "quantity": 4},
        ]
        before = deepcopy(children)
        result = self.scope.validate_split(self.parent, children)
        self.assertEqual(["C1", "C2"], [r["batch_id"] for r in result])
        self.assertEqual([4, 6], [r["quantity"] for r in result])
        self.assertEqual(before, children)
        result[0]["quantity"] = 0
        self.assertEqual(before, children)
        self.assertEqual(10, self.parent["quantity"])

    def test_split_rejects_loss_gain_reuse_and_changed_constraints(self):
        first = {**self.parent, "batch_id": "C1", "quantity": 4}
        second = {**self.parent, "batch_id": "C2", "quantity": 6}
        invalid = [
            [],
            [first],
            [first, {**second, "quantity": 5}],
            [first, {**second, "quantity": 7}],
            [{**first, "quantity": 0}, {**second, "quantity": 10}],
            [{**first, "quantity": True}, {**second, "quantity": 9}],
            [{**first, "batch_id": "P"}, second],
            [first, {**second, "batch_id": "C1"}],
        ]
        for key, value in (
            ("store_id", "S04"),
            ("sku_id", "OTHER"),
            ("policy_ref", "v2"),
            ("device_id", "D2"),
            ("disposition", "released"),
            ("lifecycle", "retired"),
            ("safe_for_sale", True),
            ("storage_min_c", -20),
            ("storage_max_c", 99),
            ("tenant_id", "other"),
        ):
            invalid.append([first, {**second, key: value}])
        for children in invalid:
            with self.subTest(children=children), self.assertRaises(ValueError):
                self.scope.validate_split(self.parent, children)
        for disposition in ("released", "transferred", "disposed"):
            with self.subTest(parent=disposition), self.assertRaises(ValueError):
                self.scope.validate_split(
                    {**self.parent, "disposition": disposition}, [first, second]
                )
        with self.assertRaises(ValueError):
            self.scope.validate_split({**self.parent, "lifecycle": "retired"}, [first, second])


if __name__ == "__main__":
    unittest.main()
