#!/usr/bin/env python3
"""Build Native Interactive Web Application for Defense Manual (No PDF needed, 100% Web Native)."""

from pathlib import Path

if __package__:
    from .portal_support import render_asset
else:
    from portal_support import render_asset

ROOT = Path(__file__).resolve().parent.parent
STANDALONE_HTML_PATH = ROOT / "dist" / "delivery-portal" / "defense.html"

# Define the full native HTML content for the defense dossier
DOSSIER_HTML = render_asset("native_defense_web_dossier_html.html")


def update(output=STANDALONE_HTML_PATH):
    standalone_html = render_asset("native_defense_web_standalone_html.html", value0=DOSSIER_HTML)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(standalone_html, encoding="utf-8", newline="\n")
    print(f"Generated standalone defense.html: {output}")


if __name__ == "__main__":
    update()
