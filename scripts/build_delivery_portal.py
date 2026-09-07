#!/usr/bin/env python3
"""Build the competition delivery portal HTML for mazhi.icu/agentteams/."""

import re
from pathlib import Path

if __package__:
    from .portal_support import render_asset
else:
    from portal_support import render_asset

ROOT = Path(__file__).resolve().parent.parent
COMMAND_CENTER_HTML = ROOT / "evidence" / "m4" / "command-center.html"
OUTPUT_DIR = ROOT / "dist" / "delivery-portal"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


def extract_command_center_panels():
    """Extract panels and tabs from evidence/m4/command-center.html."""
    if not COMMAND_CENTER_HTML.exists():
        return "", ""
    text = COMMAND_CENTER_HTML.read_text(encoding="utf-8")

    # Extract tabs
    nav_match = re.search(r'<nav class="tabs">(.*?)</nav>', text, re.DOTALL)
    tabs_html = nav_match.group(1) if nav_match else ""

    # Extract all section panels
    panels_matches = re.findall(r'(<section class="panel.*?</section>)', text, re.DOTALL)
    panels_html = "\n".join(panels_matches) if panels_matches else ""

    return tabs_html, panels_html


def build_portal(output_dir=OUTPUT_DIR):
    output_dir.mkdir(parents=True, exist_ok=True)
    tabs_html, panels_html = extract_command_center_panels()
    if not tabs_html or not panels_html:
        raise RuntimeError("Generate evidence/m4/command-center.html before building the portal")

    html_content = render_asset(
        "delivery_portal_html_content.html",
        value0=tabs_html,
        value1=panels_html,
        DOSSIER=render_asset("native_defense_web_dossier_html.html"),
    )
    output = output_dir / "index.html"
    output.write_text(html_content, encoding="utf-8", newline="\n")
    print(f"Generated {output} ({len(html_content)} bytes)")


if __name__ == "__main__":
    build_portal()
