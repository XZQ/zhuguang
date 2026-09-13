from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import reportlab
from pypdf import PdfReader

from scripts import build_project_handbook as handbook

ROOT = Path(__file__).resolve().parents[1]
FONTS = Path(reportlab.__file__).parent / "fonts"


class Links(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.targets = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            self.targets.append(dict(attrs)["href"])


class ProjectHandbookTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for location in [*handbook.INPUTS.values(), *handbook.DATA]:
            target = self.root / location
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / location, target)
        self.output = self.root / "handbook.pdf"

    def export(self):
        # Bundled Vera fonts keep content/link tests portable. Chinese page layout
        # is checked separately on the final artifact with actual Chinese fonts.
        argv = [
            "build_project_handbook.py",
            "--output",
            str(self.output),
            "--date",
            "2026-09-13",
            "--font",
            str(FONTS / "Vera.ttf"),
            "--bold-font",
            str(FONTS / "VeraBd.ttf"),
        ]
        captured = io.StringIO()
        self.paragraphs = []
        original_paragraph = handbook.paragraph

        def capture_paragraph(text, kind="body"):
            self.paragraphs.append(text)
            return original_paragraph(text, kind)

        with (
            patch.object(handbook, "ROOT", self.root),
            patch.object(sys, "argv", argv),
            patch.object(handbook.subprocess, "check_output", return_value="test-commit\n"),
            patch.object(handbook, "paragraph", side_effect=capture_paragraph),
            patch.dict(os.environ),
            contextlib.redirect_stdout(captured),
        ):
            handbook.main()
        return json.loads(captured.getvalue()), PdfReader(io.BytesIO(self.output.read_bytes()))

    def replace_script(self, count):
        path = self.root / handbook.INPUTS["talk"]
        before, start, rest = path.read_text(encoding="utf-8").partition("## 1. 逐页讲稿")
        _, end, after = rest.partition("## 2. 演示操作与口播")
        self.assertTrue(start and end)
        speech = "".join(
            f"### P{index:02}｜讲稿核验\n\nSLIDE_SENTINEL_{index:02}_END\n\n"
            for index in range(1, count + 1)
        )
        path.write_text(f"{before}{start}\n\n{speech}{end}{after}", encoding="utf-8")

    def test_inline_resolves_unicode_local_links_with_query_and_fragment(self):
        for name, bookmark in handbook.LINKS.items():
            for path in (name, quote(name)):
                with self.subTest(path=path):
                    nodes = handbook.MD(f"[来源](../{path}?edition=current#section)")
                    markup = handbook.inline(nodes[0]["children"])
                    self.assertEqual([f"#{bookmark}"], Links(markup).targets)

    def test_inline_preserves_external_urls_with_known_document_names(self):
        for scheme in ("http", "https"):
            for name in ("runtime-recovery.md", quote("待办.md")):
                for suffix in ("", "?a=1&b=2#section"):
                    with self.subTest(scheme=scheme, name=name, suffix=suffix):
                        url = f"{scheme}://example.org/{name}{suffix}"
                        nodes = handbook.MD(f"[外部来源]({url})")
                        markup = handbook.inline(nodes[0]["children"])
                        self.assertEqual([url], Links(markup).targets)

    def test_export_links_point_to_correct_pages(self):
        path = self.root / handbook.INPUTS["intro"]
        local_links = " / ".join(
            f"[REF{index}](../{name})" for index, name in enumerate(handbook.LINKS)
        )
        external = "https://example.org/runtime-recovery.md?a=1&b=2#section"
        path.write_text(
            f"## 500 字作品简介\n\n{local_links}\n\n[EXTERNAL]({external})\n",
            encoding="utf-8",
        )
        manifest, reader = self.export()
        pages = {page.indirect_reference.idnum: index for index, page in enumerate(reader.pages, 1)}
        destinations = Counter()
        external_targets = []
        for reference in reader.pages[0].get("/Annots", []):
            annotation = reference.get_object()
            if "/Dest" in annotation:
                destinations[pages[annotation["/Dest"][0].idnum]] += 1
            elif annotation.get("/A", {}).get("/S") == "/URI":
                external_targets.append(annotation["/A"]["/URI"])
        section_pages = {entry["title"]: entry["page"] for entry in manifest["sections"]}
        expected = Counter(
            section_pages[" ".join(title.split())]
            for title in (
                # Existing cover navigation plus the five source links above.
                "01  现场速查",
                "02  架构与协作",
                "05  评测结果与证据",
                "06  演示与录屏",
                "07  逐页讲稿  01-04",
                "08  评委问答  1/2",
                "09  当前待办与交付",
                "10  版本、来源与复核",
                "02  架构与协作",
                "09  当前待办与交付",
                "05  评测结果与证据",
                "04  运行与故障恢复",
                "07  逐页讲稿  01-04",
            )
        )
        self.assertEqual(expected, destinations)
        self.assertEqual([external], external_targets)

    def test_export_includes_all_script_groups(self):
        for count in (1, 4, 5, 13):
            with self.subTest(count=count):
                self.replace_script(count)
                manifest, reader = self.export()
                text = "\n".join(page.extract_text() for page in reader.pages)
                for index in range(1, count + 1):
                    self.assertEqual(1, text.count(f"SLIDE_SENTINEL_{index:02}_END"))
                expected = [
                    f"07 逐页讲稿 {start + 1:02}-{min(start + 4, count):02}"
                    for start in range(0, count, 4)
                ]
                actual = [
                    entry["title"]
                    for entry in manifest["sections"]
                    if entry["title"].startswith("07 逐页讲稿")
                ]
                self.assertEqual(expected, actual)
                self.assertIn(f"对应 {count} 页决赛工作稿", "\n".join(self.paragraphs))

    def test_export_rejects_empty_script_and_preserves_output(self):
        self.replace_script(0)
        self.output.write_bytes(b"previous handbook")
        with self.assertRaisesRegex(ValueError, "No speech sections"):
            self.export()
        self.assertEqual(b"previous handbook", self.output.read_bytes())

    def test_todo_snapshot_tracks_source_status(self):
        path = self.root / handbook.INPUTS["todo"]
        source = path.read_text(encoding="utf-8")
        original = "| T03 | P0 | 外部待验 |"
        self.assertIn(original, source)
        source = source.replace(original, "| T03 | P0 | 已验收 / DONE |")
        source = source.replace(
            "仓库未提供目标平台验收报告，实际执行与证据归入 T03",
            "隔离验收已完成，报告归入 T03",
        )
        path.write_text(source, encoding="utf-8")
        manifest, reader = self.export()
        first_page = next(
            entry["page"] for entry in manifest["sections"] if entry["title"] == "09 当前待办与交付"
        )
        next_page = next(
            entry["page"]
            for entry in manifest["sections"]
            if entry["title"] == "10 版本、来源与复核"
        )
        text = "".join(page.extract_text() for page in reader.pages[first_page - 1 : next_page - 1])
        self.assertIn("DONE", text)
        self.assertIn("已验收 / DONE", self.paragraphs)
        self.assertNotIn("真实目标平台验收仍待执行", "\n".join(self.paragraphs))
