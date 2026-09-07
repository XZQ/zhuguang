"""Shared deterministic inputs for presentation builders."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "assets"


def project_facts() -> dict:
    return json.loads((ROOT / "config/project-facts.json").read_text(encoding="utf-8"))


def render_asset(name: str, **values: str) -> str:
    facts = project_facts()
    values = {"MODEL": facts["agentteams"]["default_model"], **values}
    template = (ASSETS / name).read_text(encoding="utf-8")

    def replace(match):
        key = match[1]
        if key not in values:
            raise ValueError(f"Missing template input {key} in {name}")
        return str(values[key])

    return re.sub(r"@@(\w+)@@", replace, template)


def export_pdf(html_path: Path, pdf_path: Path, copy_path: Path) -> None:
    """Optional explicit browser dependency; failures propagate when PDF was requested."""
    browser = os.environ.get("DIANXUN_PDF_BROWSER")
    if not browser:
        print("PDF skipped: set DIANXUN_PDF_BROWSER to an installed Chromium browser to export")
        return
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise RuntimeError("Browser did not produce a PDF")
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_bytes(pdf_path.read_bytes())
