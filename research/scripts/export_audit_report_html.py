#!/usr/bin/env python3
"""Export MARKET_MOOD_OBJECTIVE_DRIFT_AUDIT.md to standalone HTML."""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "MARKET_MOOD_OBJECTIVE_DRIFT_AUDIT.md"
OUT_PATH = ROOT / "MARKET_MOOD_OBJECTIVE_DRIFT_AUDIT.html"

CSS = """
:root {
  --bg: #ffffff;
  --text: #1a1a1a;
  --muted: #555;
  --border: #d9dee7;
  --accent: #0f4c81;
  --accent-light: #e8f1f8;
  --valid: #1b6b3a;
  --warn: #9a6700;
  --discard: #a12622;
  --code-bg: #f4f6f8;
}
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  line-height: 1.55;
  color: var(--text);
  background: #eef1f5;
  margin: 0;
  padding: 0;
}
.wrapper {
  max-width: 980px;
  margin: 0 auto;
  background: var(--bg);
  box-shadow: 0 2px 24px rgba(0,0,0,.08);
}
header {
  background: linear-gradient(135deg, #0f4c81, #1a6fb0);
  color: #fff;
  padding: 2rem 2.5rem 1.5rem;
}
header h1 {
  margin: 0 0 .5rem;
  font-size: 1.75rem;
  line-height: 1.25;
}
header .meta {
  opacity: .92;
  font-size: .95rem;
}
.download-bar {
  background: var(--accent-light);
  border-bottom: 1px solid var(--border);
  padding: .75rem 2.5rem;
  font-size: .92rem;
}
.download-bar strong { color: var(--accent); }
main { padding: 2rem 2.5rem 3rem; }
h2 {
  color: var(--accent);
  border-bottom: 2px solid var(--accent-light);
  padding-bottom: .35rem;
  margin-top: 2.25rem;
}
h3 { margin-top: 1.5rem; color: #243447; }
h4 { margin-top: 1.25rem; color: #36465d; }
p, li { font-size: 1rem; }
blockquote {
  margin: 1rem 0;
  padding: .85rem 1rem;
  border-left: 4px solid var(--accent);
  background: var(--accent-light);
  font-style: italic;
}
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2rem 0;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0 1.5rem;
  font-size: .92rem;
}
th, td {
  border: 1px solid var(--border);
  padding: .55rem .65rem;
  vertical-align: top;
  text-align: left;
}
th {
  background: #f0f4f8;
  font-weight: 600;
}
tr:nth-child(even) td { background: #fafbfc; }
code, pre {
  font-family: Consolas, "Courier New", monospace;
  font-size: .88rem;
}
pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .85rem 1rem;
  overflow-x: auto;
  white-space: pre-wrap;
}
ul { padding-left: 1.25rem; }
strong.valid { color: var(--valid); }
strong.warn { color: var(--warn); }
strong.discard { color: var(--discard); }
footer {
  border-top: 1px solid var(--border);
  padding: 1rem 2.5rem 1.5rem;
  color: var(--muted);
  font-size: .85rem;
}
@media print {
  body { background: #fff; }
  .wrapper { box-shadow: none; max-width: none; }
  .download-bar { display: none; }
  header { background: #0f4c81; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  h2 { break-after: avoid; }
  table, pre, blockquote { break-inside: avoid; }
}
"""


def classify_cell(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(
        r"\*\*(Still valid|Needs revalidation|Needs reinterpretation|Must be discarded)\*\*",
        lambda m: f'<strong class="{m.group(1).lower().replace(" ", "-")}">{m.group(1)}</strong>',
        escaped,
    )
    return escaped.replace("**", "")


def parse_table(lines: list[str]) -> str:
    rows: list[list[str]] = []
    for line in lines:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""

    html_rows = []
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        html_rows.append(
            "<tr>"
            + "".join(f"<{tag}>{classify_cell(c)}</{tag}>" for c in row)
            + "</tr>"
        )
    return "<table>\n" + "\n".join(html_rows) + "\n</table>"


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("|"):
            close_list()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out.append(parse_table(table_lines))
            continue

        if line.startswith("```"):
            close_list()
            fence = line.strip()
            lang = fence[3:].strip()
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(code_lines))
            if lang == "text":
                out.append(f"<pre>{code}</pre>")
            else:
                out.append(f"<pre><code>{code}</code></pre>")
            continue

        if line.startswith("# "):
            close_list()
            out.append(f"<h2>{html.escape(line[2:].strip())}</h2>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            close_list()
            out.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("#### "):
            close_list()
            out.append(f"<h4>{html.escape(line[5:].strip())}</h4>")
        elif line.strip() == "---":
            close_list()
            out.append("<hr>")
        elif line.startswith("> "):
            close_list()
            quote_lines = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                quote_lines.append(lines[i][2:])
                i += 1
            quote = classify_cell(" ".join(quote_lines))
            out.append(f"<blockquote><p>{quote}</p></blockquote>")
            continue
        elif re.match(r"^[-*] ", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = classify_cell(line[2:].strip())
            out.append(f"<li>{item}</li>")
        elif line.strip() == "":
            close_list()
        else:
            close_list()
            text = classify_cell(line.strip())
            out.append(f"<p>{text}</p>")

        i += 1

    close_list()
    return "\n".join(out)


def build_html(md: str) -> str:
    body = md_to_html(md)
    title = "Market Mood Research — Objective-Drift Audit"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="wrapper">
    <header>
      <h1>{html.escape(title)}</h1>
      <div class="meta">Quant Center · Independent Research Audit · July 2026</div>
    </header>
    <div class="download-bar">
      <strong>How to save:</strong> Press <kbd>Ctrl+P</kbd> (or <kbd>Cmd+P</kbd> on Mac) and choose
      <strong>Save as PDF</strong>, or use your browser's <strong>Save Page As</strong> option.
    </div>
    <main>
{body}
    </main>
    <footer>
      Generated from MARKET_MOOD_OBJECTIVE_DRIFT_AUDIT.md · Quant Center Market Intelligence research
    </footer>
  </div>
</body>
</html>
"""


def main() -> None:
    md = MD_PATH.read_text(encoding="utf-8")
    OUT_PATH.write_text(build_html(md), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
