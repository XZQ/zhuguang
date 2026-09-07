#!/usr/bin/env python3
"""Generate an animated SVG architecture diagram suitable for GitHub README rendering."""

from pathlib import Path

if __package__:
    from .portal_support import render_asset
else:
    from portal_support import render_asset

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "docs" / "assets"
OUTPUT_SVG = OUTPUT_DIR / "architecture-flow.svg"

SVG_CONTENT = render_asset("animated_svg_svg_content.svg")


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_SVG.write_text(SVG_CONTENT, encoding="utf-8")
    print(f"Generated {OUTPUT_SVG} ({len(SVG_CONTENT)} bytes)")


if __name__ == "__main__":
    build()
