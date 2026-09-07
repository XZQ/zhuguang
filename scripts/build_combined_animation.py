#!/usr/bin/env python3
"""Build Multi-Store, Multi-Device Fleet Temperature Monitoring + 5-Agent Architecture Animation."""

from pathlib import Path

if __package__:
    from .portal_support import render_asset
else:
    from portal_support import render_asset

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "dist" / "delivery-portal" / "architecture-flow.html"

HTML_CONTENT = render_asset("combined_animation_html_content.html")


def build(output=OUTPUT_FILE):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(HTML_CONTENT, encoding="utf-8", newline="\n")
    print(f"Generated {output} ({len(HTML_CONTENT)} bytes)")


if __name__ == "__main__":
    build()
