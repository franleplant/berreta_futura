#!/usr/bin/env python3
"""read.py — read a produce run's articles in a browser before rendering the PDF.

    uv run python tools/read.py editions/004/run-<ts> [--out path.html]

Lays each piece out in a column sized to roughly A5 page proportions, with
faint page-break guide lines every ~page height, so density and length are
visible at a glance. This is a quick reading tool, not a renderer — the
guides are approximate, and the markdown-to-HTML conversion is deliberately
tiny. It flags the same density problems a reader would trip over: paragraphs
over 120 words, inline code/tokens over 60 chars, and pieces with no section
headings past 600 words.
"""

from __future__ import annotations

import argparse
import html
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


COL_WIDTH = 460
PAGE_RATIO = 148 / 210
PAGE_HEIGHT_PX = round(COL_WIDTH / PAGE_RATIO)
WORDS_PER_PAGE = 260
DENSE_WORDS = 120
LONG_TOKEN_CHARS = 60


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_yaml(path: Path):
    text = read(path)
    return yaml.safe_load(text) if text.strip() else None


def strip_front_matter(md: str) -> str:
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4 :].lstrip()
    return md


def has_long_token(text: str) -> bool:
    without_code = re.sub(r"`[^`]+`", " ", text)
    for tok in without_code.split():
        if len(re.sub(r"[*_]", "", tok)) > LONG_TOKEN_CHARS:
            return True
    return False


def inline_code_sub(m: re.Match) -> str:
    content = m.group(1)
    if len(content) > LONG_TOKEN_CHARS:
        return f'<code class="toolong">{content}</code><sup class="tag">long</sup>'
    return f"<code>{content}</code>"


def inline_markup(esc: str) -> str:
    esc = re.sub(r"`([^`]+)`", inline_code_sub, esc)
    esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
    return esc


def render_body(md: str) -> tuple[str, dict]:
    body = strip_front_matter(md)
    out: list[str] = []
    in_code = False
    in_list = False
    para_buf: list[str] = []
    stats = {"headings": 0, "dense": 0}

    def flush_para() -> None:
        if not para_buf:
            return
        text = " ".join(para_buf)
        para_buf.clear()
        words = len(text.split())
        esc = inline_markup(html.escape(text))
        classes, flags = [], []
        if words > DENSE_WORDS:
            classes.append("dense")
            flags.append(f"dense · {words} words")
            stats["dense"] += 1
        if has_long_token(text):
            classes.append("toolong")
            flags.append("long token")
        cls = f' class="{" ".join(classes)}"' if classes else ""
        flag_html = f'<span class="flag">{" · ".join(flags)}</span>' if flags else ""
        out.append(f"<p{cls}>{flag_html}{esc}</p>")

    for raw in body.split("\n"):
        line = raw.rstrip()
        if line.startswith("```"):
            flush_para()
            if in_code:
                out.append("</code></pre>")
            else:
                out.append("<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            esc = html.escape(line)
            cls = (
                ' class="toolong"'
                if len(line.strip()) > LONG_TOKEN_CHARS or has_long_token(line)
                else ""
            )
            out.append(f"<span{cls}>{esc}</span>" if cls else esc)
            continue
        if not line.strip():
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if line.startswith("#"):
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            stats["headings"] += 1
            text = line.lstrip("#").strip()
            out.append(f'<h4 class="mdhead">{html.escape(text)}</h4>')
            continue
        if line.startswith(("- ", "* ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = line[2:]
            out.append(f"<li>{inline_markup(html.escape(item))}</li>")
            continue
        para_buf.append(line.strip())

    flush_para()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out), stats


def piece_dirs(run_dir: Path) -> list[Path]:
    dirs = sorted((run_dir / "articles").glob("*"))
    editorial = run_dir / "editorial"
    if editorial.exists():
        dirs.append(editorial)
    return dirs


def collect(run_dir: Path) -> list[dict]:
    pieces = []
    for piece_dir in piece_dirs(run_dir):
        final = piece_dir / "final.md"
        if not final.exists():
            continue
        status = load_yaml(piece_dir / "status.yaml") or {}
        body = read(final)
        words = len(strip_front_matter(body).split())
        est_pages = max(1, math.ceil(words / WORDS_PER_PAGE)) if words else 0
        body_html, stats = render_body(body)
        pieces.append(
            {
                "id": piece_dir.name,
                "words": words,
                "est_pages": est_pages,
                "state": status.get("state", ""),
                "rounds": len(status.get("rounds") or []),
                "headings": stats["headings"],
                "dense": stats["dense"],
                "body_html": body_html,
            }
        )
    return pieces


def page_guides(est_pages: int) -> str:
    n_guides = min(60, max(4, est_pages + 3))
    return "".join(
        f'<div class="guide" style="top:{n * PAGE_HEIGHT_PX}px">page {n + 1}</div>'
        for n in range(1, n_guides + 1)
    )


CSS = f"""
:root {{ color-scheme: light dark; --fg:#1a1a1a; --bg:#fbfaf8; --muted:#6b6b6b;
  --line:#e2ddd5; --card:#fff; --warn:#b06000; --warn2:#b4231f; --ok:#2f6b3f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg:#e8e6e3; --bg:#151515; --muted:#9a9a9a;
  --line:#333; --card:#1d1d1d; --warn:#e0a04a; --warn2:#ff6b63; --ok:#6fbf85; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
header {{ padding:28px 32px 16px; border-bottom:1px solid var(--line) }}
h1 {{ margin:0 0 6px; font-size:22px; letter-spacing:-.01em }}
.sub {{ color:var(--muted); font-size:14px }}
nav {{ padding:12px 32px; border-bottom:1px solid var(--line); position:sticky; top:0;
  background:var(--bg); z-index:5; display:flex; gap:10px; flex-wrap:wrap; font-size:13px }}
nav a {{ color:var(--fg); text-decoration:none; border:1px solid var(--line);
  padding:4px 10px; border-radius:999px }}
nav a:hover {{ border-color:var(--fg) }}
main {{ padding:24px 32px 80px; max-width:1600px }}
table.idx {{ border-collapse:collapse; font-size:13.5px; margin:8px 0 32px }}
table.idx th, table.idx td {{ border:1px solid var(--line); padding:5px 10px; text-align:left }}
table.idx th {{ background:rgba(127,127,127,.1) }}
table.idx td.num {{ text-align:right }}
table.idx a {{ color:var(--fg) }}
.piece {{ margin:0 0 56px }}
.piece-head {{ padding-top:16px; border-top:2px solid var(--fg); margin-bottom:10px;
  display:flex; justify-content:space-between; align-items:baseline; gap:16px; flex-wrap:wrap }}
.piece-head h2 {{ margin:0; font-size:18px }}
.piece-head .meta {{ color:var(--muted); font-size:13px; text-align:right }}
.notice {{ font-size:12.5px; color:var(--warn); border-left:3px solid var(--warn);
  padding:4px 10px; margin:0 0 14px; display:inline-block }}
.page-col {{ position:relative; width:{COL_WIDTH}px; background:var(--card);
  border:1px solid var(--line); border-radius:6px; padding:20px 24px; overflow:hidden }}
.guide {{ position:absolute; left:0; right:0; border-top:1px dashed var(--line);
  font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
  padding-top:3px; z-index:0; pointer-events:none }}
.page-text {{ position:relative; z-index:1;
  font-family:Georgia,'Source Serif 4',serif; font-size:16px; line-height:1.5 }}
.page-text p {{ margin:0 0 .9em }}
.page-text .mdhead {{ font-size:15px; font-weight:700; margin:1.2em 0 .4em;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif }}
.page-text ul {{ margin:.4em 0 .9em; padding-left:1.3em }}
.page-text li {{ margin:.25em 0 }}
.page-text pre {{ background:rgba(127,127,127,.12); padding:10px 12px; border-radius:6px;
  overflow-x:auto; font-size:12.5px; font-family:ui-monospace,Menlo,monospace; white-space:pre }}
.page-text code {{ font-size:.92em; font-family:ui-monospace,Menlo,monospace }}
.page-text .flag {{ display:block; font-size:10px; text-transform:uppercase; letter-spacing:.06em;
  margin-bottom:2px }}
.page-text p.dense {{ border-left:3px solid var(--warn); padding-left:10px; margin-left:-13px }}
.page-text p.dense .flag {{ color:var(--warn) }}
.page-text p.toolong {{ border-left:3px solid var(--warn2); padding-left:10px; margin-left:-13px }}
.page-text p.toolong .flag {{ color:var(--warn2) }}
.page-text p.dense.toolong {{ border-left:3px solid var(--warn2) }}
.page-text code.toolong {{ background:rgba(180,35,31,.15); border-radius:3px; padding:0 2px }}
.page-text sup.tag {{ font-size:9px; color:var(--warn2); vertical-align:super; margin-left:1px }}
.page-text span.toolong {{ background:rgba(180,35,31,.15); border-radius:2px }}
"""


def piece_meta_row(p: dict) -> str:
    return (
        f"<tr><td><a href='#{html.escape(p['id'])}'>{html.escape(p['id'])}</a></td>"
        f"<td class='num'>{p['words']}</td>"
        f"<td class='num'>~{p['est_pages']}</td>"
        f"<td class='num'>{p['headings']}</td>"
        f"<td class='num'>{p['dense']}</td></tr>"
    )


def render(run_dir: Path) -> str:
    pieces = collect(run_dir)

    parts = [
        f"<title>Read — {html.escape(run_dir.name)}</title>",
        f"<style>{CSS}</style>",
        "<header><h1>Read before render</h1>",
        f"<div class='sub'>{html.escape(str(run_dir))} &nbsp;·&nbsp; {len(pieces)} pieces "
        f"&nbsp;·&nbsp; column {COL_WIDTH}px ≈ A5 page, guide every {PAGE_HEIGHT_PX}px "
        f"(~{WORDS_PER_PAGE} words/page)</div></header>",
    ]
    parts.append(
        "<nav>"
        + "".join(f"<a href='#{html.escape(p['id'])}'>{html.escape(p['id'])}</a>" for p in pieces)
        + "</nav>"
    )
    parts.append("<main>")

    parts.append(
        "<table class='idx'><tr><th>piece</th><th>words</th><th>est. pages</th>"
        "<th>headings</th><th>dense paragraphs</th></tr>"
    )
    for p in pieces:
        parts.append(piece_meta_row(p))
    parts.append("</table>")

    for p in pieces:
        parts.append(f"<section class='piece' id='{html.escape(p['id'])}'>")
        parts.append("<div class='piece-head'>")
        parts.append(f"<h2>{html.escape(p['id'])}</h2>")
        parts.append(
            f"<div class='meta'>{p['words']} words · ~{p['est_pages']} pages (est) · "
            f"{html.escape(str(p['state']))} · {p['rounds']} rounds</div>"
        )
        parts.append("</div>")
        if p["headings"] == 0 and p["words"] > 600:
            parts.append(
                f"<div class='notice'>no section headings — {p['words']} words in one block</div>"
            )
        parts.append("<div class='page-col'>")
        parts.append(page_guides(p["est_pages"]))
        parts.append(f"<div class='page-text'>{p['body_html']}</div>")
        parts.append("</div>")
        parts.append("</section>")

    parts.append("</main>")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path, help="produce run directory, e.g. editions/004/run-<ts>")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    run_dir = args.run_dir
    if not (run_dir / "articles").exists() and not (run_dir / "editorial").exists():
        sys.exit(f"no articles/ or editorial/ found under {run_dir}")

    out = args.out or (run_dir / "read.html")
    out.write_text(render(run_dir), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
