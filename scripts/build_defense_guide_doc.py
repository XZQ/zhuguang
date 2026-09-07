#!/usr/bin/env python3
"""Build Comprehensive Defense Guide in Markdown, HTML and PDF formats."""

from pathlib import Path

if __package__:
    from .portal_support import export_pdf, render_asset
else:
    from portal_support import export_pdf, render_asset

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "docs" / "competition" / "10-2026-GOAI复赛答辩速查手册-逐光队.md"
HTML_PATH = ROOT / "dist" / "delivery-portal" / "defense-guide.html"
PDF_PATH = ROOT / "dist" / "delivery-portal" / "2026-GOAI复赛答辩速查手册-逐光队.pdf"
DOCS_PDF_PATH = ROOT / "docs" / "competition" / "2026-GOAI复赛答辩速查手册-逐光队.pdf"

MD_CONTENT = render_asset("defense_guide_doc_md_content.md")

HTML_TEMPLATE = render_asset("defense_guide_doc_html_template.html")


def generate():
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text(MD_CONTENT, encoding="utf-8")
    print(f"Generated Markdown: {MD_PATH}")

    # Generate HTML using markdown rendering or rich conversion
    # Simple markdown parser for the document
    import html

    body_html = ""
    lines = MD_CONTENT.split("\n")
    in_table = False
    table_rows = []
    in_blockquote = False
    blockquote_lines = []

    def flush_table():
        nonlocal in_table, table_rows, body_html
        if not table_rows:
            in_table = False
            return
        res = "<table>\n"
        for idx, row in enumerate(table_rows):
            cols = [c.strip() for c in row.split("|")[1:-1]]
            tag = "th" if idx == 0 else "td"
            if idx == 1 and all(set(c).issubset({"-", ":"}) for c in cols):
                continue
            res += "  <tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cols) + "</tr>\n"
        res += "</table>\n"
        body_html += res
        table_rows = []
        in_table = False

    def flush_quote():
        nonlocal in_blockquote, blockquote_lines, body_html
        if not blockquote_lines:
            in_blockquote = False
            return
        body_html += "<blockquote>" + "<br>".join(blockquote_lines) + "</blockquote>\n"
        blockquote_lines = []
        in_blockquote = False

    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            if in_blockquote:
                flush_quote()
            in_table = True
            table_rows.append(line)
            continue
        elif in_table:
            flush_table()

        if line.startswith("> "):
            blockquote_lines.append(line[2:])
            in_blockquote = True
            continue
        elif in_blockquote:
            flush_quote()

        if line.startswith("# "):
            body_html += f"<h1>{html.escape(line[2:])}</h1>\n"
        elif line.startswith("## "):
            body_html += f"<h2>{html.escape(line[3:])}</h2>\n"
        elif line.startswith("### "):
            body_html += f"<h3>{html.escape(line[4:])}</h3>\n"
        elif line.startswith("---"):
            body_html += "<hr style='border:none; border-top:1px solid #e2e8f0; margin:16px 0;'>\n"
        elif line.startswith("- "):
            # Format bold and inline code
            txt = line[2:]
            body_html += f"<li>{txt}</li>\n"
        elif line.strip():
            body_html += f"<p>{line}</p>\n"

    if in_table:
        flush_table()
    if in_blockquote:
        flush_quote()

    # Format bold and links
    body_html = body_html.replace("**", "<b>").replace("**", "</b>")
    # Quick fix for unmatched <b> tags
    parts = body_html.split("<b>")
    rebuilt = parts[0]
    for p in parts[1:]:
        if "</b>" in p:
            rebuilt += "<b>" + p
        else:
            rebuilt += "<b>" + p.replace("</b>", "") + "</b>"
    body_html = rebuilt

    full_html = HTML_TEMPLATE.replace("{body_content}", body_html)
    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(full_html, encoding="utf-8")
    print(f"Generated HTML: {HTML_PATH}")

    export_pdf(HTML_PATH, PDF_PATH, DOCS_PDF_PATH)


if __name__ == "__main__":
    generate()
