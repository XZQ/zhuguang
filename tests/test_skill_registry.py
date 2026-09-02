from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dianxun import trace
from dianxun.skills.registry import (
    SkillRegistryError,
    classify_version_change,
    compute_skill_digest,
    load_skill_registry,
    resolve_skill_release,
)

ROOT = Path(__file__).resolve().parents[1]


class SkillRegistryTests(unittest.TestCase):
    def test_registry_stable_releases_match_manifests_and_content(self) -> None:
        registry = load_skill_registry()
        self.assertEqual("1.0.0", registry["registry_version"])
        self.assertEqual(6, len(registry["skills"]))
        self.assertTrue(all(item["status"] == "active" for item in registry["skills"]))
        self.assertTrue(all(item["canary"] is None for item in registry["skills"]))
        for item in registry["skills"]:
            with self.subTest(skill=item["name"]):
                release = resolve_skill_release(
                    item["name"], routing_key="trace-stable", registry=registry
                )
                self.assertEqual("stable", release.channel)
                self.assertEqual(item["stable"]["version"], release.version)
                self.assertEqual(
                    compute_skill_digest(ROOT / "skills" / item["name"]),
                    release.digest,
                )

    def test_canary_routing_is_bounded_deterministic_and_retirement_blocks_new_work(self) -> None:
        registry = copy.deepcopy(load_skill_registry())
        skill = registry["skills"][0]
        skill["canary"] = {
            "version": "1.1.0",
            "digest": "f" * 64,
            "channel": "canary",
            "artifact": "artifact://anomaly-detect/1.1.0",
            "rollout_percent": 25,
        }
        channels: dict[str, str] = {}
        for index in range(200):
            key = f"incident-{index}"
            first = resolve_skill_release(skill["name"], routing_key=key, registry=registry)
            second = resolve_skill_release(skill["name"], routing_key=key, registry=registry)
            self.assertEqual(first, second)
            channels.setdefault(first.channel, key)
            if set(channels) == {"stable", "canary"}:
                break
        self.assertEqual({"stable", "canary"}, set(channels))

        with tempfile.TemporaryDirectory() as temporary:
            registry_path = Path(temporary) / "registry.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaisesRegex(SkillRegistryError, "rollback_target"):
                load_skill_registry(registry_path, verify_digests=False)

            skill["rollback_target"] = {
                "version": skill["stable"]["version"],
                "digest": skill["stable"]["digest"],
            }
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            loaded = load_skill_registry(registry_path, verify_digests=False)
            self.assertEqual(skill["name"], loaded["skills"][0]["name"])

            skill["rollback_target"] = {"version": skill["stable"]["version"]}
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaisesRegex(SkillRegistryError, "missing required property 'digest'"):
                load_skill_registry(registry_path, verify_digests=False)

        skill["status"] = "retired"
        skill["canary"] = None
        with self.assertRaisesRegex(SkillRegistryError, "does not accept new routing"):
            resolve_skill_release(skill["name"], routing_key="new-incident", registry=registry)

    def test_semver_change_classification_requires_explicit_rollback_for_downgrade(self) -> None:
        self.assertEqual("unchanged", classify_version_change("1.2.3", "1.2.3"))
        self.assertEqual("backward_compatible_fix", classify_version_change("1.2.3", "1.2.4"))
        self.assertEqual("backward_compatible_feature", classify_version_change("1.2.3", "1.3.0"))
        self.assertEqual("breaking", classify_version_change("1.2.3", "2.0.0"))
        with self.assertRaisesRegex(SkillRegistryError, "rollback workflow"):
            classify_version_change("1.2.3", "1.2.2")

    def test_skill_span_migrates_old_database_and_records_release_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy-trace.db"
            connection = sqlite3.connect(path)
            connection.execute(
                """CREATE TABLE spans(
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    parent_id TEXT,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    input_json TEXT,
                    output_json TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL
                )"""
            )
            connection.commit()
            connection.close()

            with trace.use_database(path):
                with trace.span(
                    "anomaly-detect", "skill", "trace-registry", input={"source": "test"}
                ) as skill_span:
                    skill_span.output = {"status": "ok"}
                with trace.span("price-tag-check", "skill", "trace-registry"):
                    pass
                rows = trace.query_trace("trace-registry")

            registered = rows[0]
            self.assertEqual("anomaly-detect", registered["skill_name"])
            self.assertEqual("1.0.0", registered["skill_version"])
            self.assertRegex(registered["skill_digest"], r"^[a-f0-9]{64}$")
            self.assertEqual("stable", registered["skill_channel"])
            self.assertEqual("1.0.0", registered["skill_registry_version"])
            self.assertIsNone(rows[1]["skill_name"])


if __name__ == "__main__":
    unittest.main()
