from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from scripts.build_full_delivery_portal import build
from scripts.generate_portal_status import build_status
from scripts.portal_support import ROOT, project_facts


class DeliveryPortalTests(unittest.TestCase):
    def test_complete_web_build_is_deterministic_and_does_not_rewrite_sources(self):
        source_paths = [
            *(ROOT / "scripts").glob("*.py"),
            *(path for path in (ROOT / "docs").rglob("*") if path.is_file()),
        ]
        sources = {path: path.read_bytes() for path in source_paths}
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            first.mkdir()
            (first / "defense-guide.html").write_text("obsolete claims", encoding="utf-8")
            (first / "2026-GOAI复赛答辩图文全景手册-逐光队.pdf").write_bytes(b"old export")
            build(first)
            build(second)

            def hashes(root):
                return {
                    path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in root.rglob("*")
                    if path.is_file()
                }

            self.assertEqual(hashes(first), hashes(second))
            self.assertFalse((first / "defense-guide.html").exists())
            for original_pdf in (ROOT / "docs" / "competition").glob("2026-GOAI复赛*.pdf"):
                self.assertEqual(
                    original_pdf.read_bytes(), (first / original_pdf.name).read_bytes()
                )
            self.assertTrue(
                {
                    "index.html",
                    "defense.html",
                    "architecture-flow.html",
                    "status.json",
                    "portal-status.js",
                    "ppt/index.html",
                }
                <= hashes(first).keys()
            )
            page = (first / "index.html").read_text(encoding="utf-8")
            self.assertIn(project_facts()["agentteams"]["default_model"], page)
            self.assertNotIn("qwen3.8-max", page)
            self.assertNotIn("@@", page)
            self.assertIn("运行状态未知", page)
            self.assertIn("均为模拟", page)
            defense = (first / "defense.html").read_text(encoding="utf-8")
            self.assertIn("VERIFY/BLOCKED", defense)
            self.assertIn("ppt/finals.html", defense)
            self.assertNotIn("5 个失败场景被错误放行", page)
            self.assertNotIn("512 台设备实跑", page)
            self.assertEqual(
                "not_observed", json.loads((first / "status.json").read_text())["source"]
            )

            class Scripts(HTMLParser):
                active = False
                blocks = []

                def handle_starttag(self, tag, attrs):
                    self.active = tag == "script" and "src" not in dict(attrs)

                def handle_endtag(self, tag):
                    if tag == "script":
                        self.active = False

                def handle_data(self, data):
                    if self.active:
                        self.blocks.append(data)

            parser = Scripts()
            parser.feed(page)
            javascript = Path(directory) / "inline.js"
            javascript.write_text("\n".join(parser.blocks), encoding="utf-8")
            subprocess.run(
                [shutil.which("node"), "--check", str(javascript)], check=True, timeout=15
            )
        self.assertEqual(sources, {path: path.read_bytes() for path in sources})

    def test_public_status_requires_timestamps_and_omits_private_fields(self):
        with self.assertRaises(ValueError):
            build_status({"workers": [{"name": "sentry", "status": "online"}]})
        public = build_status(
            {
                "workers": [
                    {
                        "name": "sentry",
                        "status": "offline",
                        "observed_at": "2026-09-07T00:00:00Z",
                        "token": "private-value",
                    }
                ]
            }
        )
        self.assertNotIn("private-value", json.dumps(public))
        self.assertEqual("offline", public["workers"][1]["status"])

    def test_status_javascript_handles_zero_stale_unknown_and_model_drift(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required for portal status regression tests")
        subprocess.run([node, str(ROOT / "tests/portal_status.test.cjs")], check=True, timeout=15)


if __name__ == "__main__":
    unittest.main()
