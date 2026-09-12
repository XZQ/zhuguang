from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from dianxun.domain import (
    IncidentCase,
    IncidentService,
    IncidentType,
    Severity,
    Verification,
    VerificationResult,
)
from dianxun.state import StateStore
from dianxun.state.protocols import IncidentConflictError

ROOT = Path(__file__).resolve().parents[1]


class IncidentConcurrencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = StateStore(Path(temporary.name) / "state.db")
        self.store.initialize_from_file(ROOT / "demo/state/seed.json")
        self.service = IncidentService(self.store)
        self.case = self.service.create(
            IncidentCase.create(
                incident_id="INC-CONCURRENT",
                tenant_id="demo",
                store_id="S03",
                incident_type=IncidentType.COLDCHAIN_TEMPERATURE_LOSS,
                severity=Severity.CRITICAL,
                trigger="manual",
                anchor_time=self.store.now(),
            )
        )

    def test_concurrent_snapshots_reject_lost_update_and_allow_explicit_retry(self):
        barrier = threading.Barrier(2)

        def append(ref):
            case = self.service.get(self.case.incident_id)
            case.evidence_refs.append(ref)
            barrier.wait(timeout=5)
            try:
                self.service.save(case)
                return "saved", ref
            except IncidentConflictError:
                return "conflict", ref

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(append, ["A", "B"]))
        self.assertEqual(["conflict", "saved"], sorted(status for status, _ in results))
        retry = next(ref for status, ref in results if status == "conflict")
        final = self.service.append_evidence_ref(self.case.incident_id, retry)
        self.assertEqual({"A", "B"}, set(final.evidence_refs))
        self.assertEqual(3, final.version)

    def test_verification_and_aggregate_roll_back_together(self):
        verification = Verification(
            verification_id="VER-ATOMIC",
            subject="batches",
            method="test",
            expected_condition={},
            observed_value={},
            evidence_ids=[],
            result=VerificationResult.PASSED,
            verifier="Auditor",
            verified_at=self.store.now(),
        )
        with patch.object(self.store, "save_incident", side_effect=IncidentConflictError("test")):
            with self.assertRaises(IncidentConflictError):
                self.service.record_verification(self.case.incident_id, verification)
        self.assertEqual([], self.store.list_verifications(incident_id=self.case.incident_id))
        self.assertEqual([], self.service.get(self.case.incident_id).verifications)
        self.service.record_verification(self.case.incident_id, verification)
        self.assertEqual(1, len(self.store.list_verifications(incident_id=self.case.incident_id)))
        self.assertEqual(1, len(self.service.get(self.case.incident_id).verifications))

    def test_legacy_unversioned_case_remains_readable_and_upgrades_on_write(self):
        raw = self.case.to_dict()
        del raw["version"]
        with self.store.transaction() as conn:
            conn.execute(
                "UPDATE incidents SET case_json = ? WHERE incident_id = ?",
                (json.dumps(raw), self.case.incident_id),
            )
        legacy = self.service.get(self.case.incident_id)
        self.assertEqual(0, legacy.version)
        legacy.evidence_refs.append("upgrade")
        self.service.save(legacy)
        self.assertEqual(1, legacy.version)
        with self.assertRaises(IncidentConflictError):
            self.service.save(IncidentCase.from_dict(raw))

    def test_caught_inner_failure_preserves_outer_writes_but_outer_failure_rolls_back_all(self):
        with self.store.transaction():
            self.store.set_meta("outer", "saved")
            with self.assertRaises(ValueError):
                with self.store.transaction():
                    self.store.set_meta("inner", "discarded")
                    raise ValueError("inner failure")
            self.assertIsNone(self.store.get_meta("inner"))
        self.assertEqual("saved", self.store.get_meta("outer"))
        with self.assertRaises(ValueError):
            with self.store.transaction():
                self.store.set_meta("outer", "discarded")
                with self.store.transaction():
                    self.store.set_meta("inner", "also discarded")
                raise ValueError("outer failure")
        self.assertEqual("saved", self.store.get_meta("outer"))
        self.assertIsNone(self.store.get_meta("inner"))


if __name__ == "__main__":
    unittest.main()
