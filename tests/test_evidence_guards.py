from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dianxun import trace
from dianxun.adapters import LocalDemoAdapter
from dianxun.domain.evidence import temperature_series
from dianxun.domain.safety import batches_are_safe_terminal
from dianxun.skills.coldchain_risk_assess import coldchain_risk_assess
from dianxun.skills.outcome_verify import outcome_verify

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-28T09:00:00+08:00"


class EvidenceGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(trace.use_database(self.root / "trace.db"))
        self.policy = json.loads(
            (ROOT / "config/policies/coldchain-demo.v1.json").read_text(encoding="utf-8")
        )
        self.batch = {
            "batch_id": "batch-a",
            "device_id": "device-a",
            "storage_min_c": 0,
            "storage_max_c": 6,
        }
        self.readings = [
            {"observed_at": "2026-08-28T08:30:00+08:00", "temp_c": 4, "quality": "good"},
            {"observed_at": NOW, "temp_c": 4, "quality": "good"},
        ]
        self.manual = {
            "incident_id": "incident-a",
            "evidence_type": "manual_temperature",
            "actor": "Human",
            "observed_at": NOW,
            "metadata": {
                "batch_id": "batch-a",
                "device_id": "device-a",
                "temp_c": 4,
                "instrument_id": "synthetic-probe",
                "measurement_point": "product",
                "calibrated_at": "2026-08-01T00:00:00+08:00",
                "calibration_valid_until": "2026-09-01T00:00:00+08:00",
            },
        }

    def assess(self, readings=None, manual=None):
        return coldchain_risk_assess(
            incident_id="incident-a",
            device_series=self.readings if readings is None else readings,
            affected_batches=[self.batch],
            policy=self.policy,
            trace_id="evidence-guard-test",
            manual_measurements=[self.manual if manual is None else manual],
            assessed_at=NOW,
        )["exposure_assessment"][0]

    def test_incomplete_conflicting_future_and_stale_series_never_recommend_release(self):
        cases = [
            [],
            self.readings[:1],
            [self.readings[-1]] * 3,
            [{**self.readings[0], "observed_at": "2026-08-28T07:00:00+08:00"}, self.readings[1]],
            [{**self.readings[0], "observed_at": "2026-08-28T08:00:00+08:00"}, self.readings[0]],
            [*self.readings, {**self.readings[-1], "observed_at": "2026-08-28T09:01:00+08:00"}],
            [*self.readings, {**self.readings[-1], "temp_c": 12}],
            [*self.readings, {**self.readings[-1], "temp_c": float("nan")}],
        ]
        for readings in cases:
            with self.subTest(readings=readings):
                result = self.assess(readings=readings)
                self.assertEqual("quarantined", result["recommendation"])
                self.assertEqual("unknown", result["coverage_status"])
                self.assertEqual("unknown", result["evidence_quality"])

    def test_wrong_batch_time_instrument_or_actor_cannot_corroborate_suspect_readings(self):
        suspect = [
            *self.readings,
            {"observed_at": NOW, "temp_c": 10, "source": "suspect-probe", "quality": "suspect"},
        ]
        self.assertEqual("released", self.assess(readings=suspect)["recommendation"])
        changes = [
            ("batch_id", "another-batch"),
            ("device_id", "another-device"),
            ("instrument_id", ""),
            ("measurement_point", "cabinet_air"),
            ("calibration_valid_until", "2026-08-27T00:00:00+08:00"),
            ("calibrated_at", "2026-08-29T00:00:00+08:00"),
            ("temp_c", -5),
        ]
        for key, value in changes:
            item = copy.deepcopy(self.manual)
            item["metadata"][key] = value
            with self.subTest(key=key):
                self.assertEqual("quarantined", self.assess(suspect, item)["recommendation"])
        for key, value in [
            ("observed_at", "2026-08-28T08:00:00+08:00"),
            ("observed_at", "2026-08-28T09:01:00+08:00"),
            ("actor", "Executor"),
            ("incident_id", "another-incident"),
        ]:
            self.assertEqual(
                "quarantined", self.assess(suspect, {**self.manual, key: value})["recommendation"]
            )

    def test_duplicates_and_equivalent_timezones_do_not_change_exposure(self):
        original = self.assess()
        readings = [
            self.readings[1],
            self.readings[0],
            {**self.readings[1], "observed_at": "2026-08-28T01:00:00+00:00"},
        ]
        self.assertEqual(original, self.assess(readings))
        normalized, _ = temperature_series(readings, now=NOW)
        self.assertEqual(2, len(normalized))

    def test_physical_receipt_requires_exact_batch_quantity_action_and_independent_confirmation(
        self,
    ):
        adapter = LocalDemoAdapter(
            db_path=self.root / "state.db",
            scenario_path=ROOT / "demo/state/scenarios/coldchain-compressor-failure.json",
        )
        result = adapter.run()
        self.assertTrue(result["acceptance"]["passed"])
        incident = result["incident"]["incident_id"]
        rows = adapter.store.list_batches(batch_ids=result["incident"]["affected_batches"])
        receipts = [
            r
            for r in adapter.store.list_manual_evidence(incident_id=incident)
            if r["evidence_type"] == "disposition_receipt"
        ]
        actions = adapter.store.list_actions(incident_id=incident)
        kwargs = dict(actions=actions, now=adapter.store.now())
        ids = [r["batch_id"] for r in rows]
        self.assertTrue(batches_are_safe_terminal(rows, ids, receipts=receipts, **kwargs))
        original_action = next(a for a in actions if a["action_id"] == receipts[0]["action_id"])
        same_tick_reexecution = {**original_action, "action_id": "new-action-same-clock"}
        self.assertFalse(
            batches_are_safe_terminal(
                rows,
                ids,
                receipts=receipts,
                actions=[*actions, same_tick_reexecution],
                now=adapter.store.now(),
            )
        )
        for field, value in [
            ("quantity", 1),
            ("batch_id", "wrong"),
            ("confirmed_by", "synthetic-store-operator"),
        ]:
            invalid = copy.deepcopy(receipts)
            invalid[0]["metadata"][field] = value
            self.assertFalse(batches_are_safe_terminal(rows, ids, receipts=invalid, **kwargs))
        invalid = copy.deepcopy(receipts)
        invalid[0]["action_id"] = "old-action"
        self.assertFalse(batches_are_safe_terminal(rows, ids, receipts=invalid, **kwargs))
        with adapter.store.transaction() as conn:
            conn.execute(
                "DELETE FROM manual_evidence WHERE evidence_type = ?", ("disposition_receipt",)
            )
        verification = outcome_verify(
            incidents=adapter.incidents,
            service=adapter.mcp,
            incident_id=incident,
            policy=adapter.policy.policy,
            trace_id=result["incident"]["trace_id"],
        )
        self.assertIn("batches", verification["failed_conditions"])
        self.assertNotEqual("CLOSED", verification["incident_status"])

    def test_scenario_event_and_dedup_marker_commit_together(self):
        adapter = LocalDemoAdapter(
            db_path=self.root / "state.db",
            scenario_path=ROOT / "demo/state/scenarios/coldchain-compressor-failure.json",
        )
        before = adapter.store.snapshot_digest()
        original = adapter.store.set_meta

        def fail_marker(key, value):
            if key.startswith("scenario_event:"):
                raise RuntimeError("synthetic marker failure")
            return original(key, value)

        with patch.object(adapter.store, "set_meta", side_effect=fail_marker):
            with self.assertRaisesRegex(RuntimeError, "marker failure"):
                adapter.scenario.apply_due_events()
        self.assertEqual(before, adapter.store.snapshot_digest())
        self.assertTrue(adapter.scenario.apply_due_events())
        self.assertEqual([], adapter.scenario.apply_due_events())
