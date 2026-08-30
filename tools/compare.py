#!/usr/bin/env python3
"""compare.py — read several produce runs side by side in a browser.

    uv run python tools/compare.py editions/004/run-A editions/004/run-B [...]
    uv run python tools/compare.py --out /tmp/x.html editions/004/run-*

Emits one self-contained HTML file: every piece from every run, its manuscript,
the judge findings that survived, and what `worth` says the reader lost. No
scores, no aggregate metrics — the point is to read the prose and read the
feedback, and to see what changed between variants.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_yaml(path: Path):
    text = read(path)
    return yaml.safe_load(text) if text.strip() else None


def split_label(arg: str) -> tuple[str | None, Path]:
    if "=" in arg:
        label, _, path = arg.partition("=")
        return label.strip(), Path(path)
    return None, Path(arg)


def run_label(run_dir: Path, label: str | None = None) -> tuple[str, str]:
    summary = read(run_dir / "summary.md")
    match = re.search(r"^- writer .*$", summary, re.MULTILINE)
    subtitle = match.group(0).lstrip("- ") if match else ""
    calls = re.search(r"^- (\d+ model calls[^\n]*)$", summary, re.MULTILINE)
    if calls:
        subtitle = f"{subtitle} — {calls.group(1)}" if subtitle else calls.group(1)
    return label or run_dir.name, subtitle


def strip_front_matter(md: str) -> str:
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4 :].lstrip()
    return md


def md_to_html(md: str) -> str:
    out, in_code, in_list = [], False, False
    for raw in strip_front_matter(md).split("\n"):
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
            else:
                out.append("<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if not line:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        esc = html.escape(line)
        esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
        esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
        if line.startswith("#"):
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{min(level + 2, 6)}>{esc.lstrip('# ')}</h{min(level + 2, 6)}>")
        elif line.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{esc[2:]}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{esc}</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def findings_rows(reports) -> list[dict]:
    rows = []
    if not isinstance(reports, dict):
        return rows
    for lens, report in reports.items():
        if not isinstance(report, dict):
            continue
        for f in report.get("findings") or []:
            if not isinstance(f, dict):
                continue
            rows.append(
                {
                    "lens": lens,
                    "severity": str(f.get("severity", "")).lower(),
                    "category": str(f.get("category", "")),
                    "disposition": str(f.get("disposition", "")),
                    "note": str(f.get("note") or "").strip(),
                    "suggestion": str(f.get("suggestion") or "").strip(),
                    "locator": str(f.get("locator") or "").strip(),
                }
            )
    order = {"blocking": 0, "major": 1, "minor": 2}
    rows.sort(key=lambda r: (order.get(r["severity"], 3), r["lens"]))
    return rows


def omissions_rows(reports) -> list[dict]:
    rows = []
    if not isinstance(reports, dict):
        return rows
    worth = reports.get("worth")
    if not isinstance(worth, dict):
        return rows
    for o in worth.get("omissions") or []:
        if isinstance(o, dict):
            rows.append(
                {
                    "fact": str(o.get("fact") or "").strip(),
                    "loses": str(o.get("reader_loses") or "").strip(),
                    "verdict": str(o.get("verdict") or "").strip().lower(),
                }
            )
    rows.sort(key=lambda r: 0 if r["verdict"] == "needed" else 1)
    return rows


def last_round_reports(piece_dir: Path):
    files = sorted(
        piece_dir.glob("findings-*.yaml"), key=lambda p: int(re.findall(r"\d+", p.name)[0])
    )
    return load_yaml(files[-1]) if files else None


def collect(run_dir: Path) -> list[dict]:
    pieces = []
    for piece_dir in sorted((run_dir / "articles").glob("*")) + [run_dir / "editorial"]:
        final = piece_dir / "final.md"
        if not final.exists():
            continue
        status = load_yaml(piece_dir / "status.yaml") or {}
        reports = last_round_reports(piece_dir)
        body = read(final)
        pieces.append(
            {
                "id": piece_dir.name,
                "words": len(strip_front_matter(body).split()),
                "state": status.get("state", ""),
                "rounds": len(status.get("rounds") or []),
                "body": body,
                "findings": findings_rows(reports),
                "omissions": omissions_rows(reports),
            }
        )
    return pieces


def source_words(edition_plan: Path, piece_id: str) -> int:
    plan = load_yaml(edition_plan) or {}
    for article in plan.get("articles") or []:
        if article.get("id") == piece_id:
            total = 0
            for sid in article.get("source_ids") or []:
                total += len(read(ROOT / "library/sources" / sid / "extracted.md").split())
            return total
    return 0


CSS = """
:root { color-scheme: light dark; --fg:#1a1a1a; --bg:#fbfaf8; --muted:#6b6b6b;
  --line:#e2ddd5; --card:#fff; --block:#b4231f; --major:#b06000; --minor:#5b6b7a; --ok:#2f6b3f; }
@media (prefers-color-scheme: dark) { :root { --fg:#e8e6e3; --bg:#151515; --muted:#9a9a9a;
  --line:#333; --card:#1d1d1d; --block:#ff6b63; --major:#e0a04a; --minor:#8fa3b5; --ok:#6fbf85; } }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
header { padding:28px 32px 16px; border-bottom:1px solid var(--line) }
h1 { margin:0 0 6px; font-size:22px; letter-spacing:-.01em }
.sub { color:var(--muted); font-size:14px }
nav { padding:12px 32px; border-bottom:1px solid var(--line); position:sticky; top:0;
  background:var(--bg); z-index:5; display:flex; gap:10px; flex-wrap:wrap; font-size:13px }
nav a { color:var(--fg); text-decoration:none; border:1px solid var(--line);
  padding:4px 10px; border-radius:999px }
nav a:hover { border-color:var(--fg) }
main { padding:24px 32px 80px; max-width:1600px }
.piece { margin:0 0 48px }
.piece > h2 { font-size:18px; margin:0 0 14px; padding-top:12px; border-top:2px solid var(--fg) }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(440px,1fr)); gap:20px; align-items:start }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden }
.card > h3 { margin:0; padding:12px 16px; font-size:14px; border-bottom:1px solid var(--line);
  display:flex; justify-content:space-between; gap:12px; align-items:baseline }
.card > h3 .meta { color:var(--muted); font-weight:400; font-size:12px; text-align:right }
.ms { padding:4px 20px 18px; max-height:62vh; overflow:auto }
.ms p { margin:.8em 0 } .ms h3,.ms h4,.ms h5 { margin:1.4em 0 .4em; font-size:15px }
.ms pre { background:rgba(127,127,127,.12); padding:10px 12px; border-radius:6px;
  overflow-x:auto; font-size:12.5px }
.ms code { font-size:.92em }
.fb { border-top:1px solid var(--line); padding:12px 16px 16px; font-size:13.5px }
.fb h4 { margin:6px 0 8px; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted) }
.f { margin:0 0 10px; padding-left:10px; border-left:3px solid var(--minor) }
.f.blocking { border-color:var(--block) } .f.major { border-color:var(--major) }
.f .tag { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted) }
.f .note { margin:2px 0 0; white-space:pre-wrap }
.om { margin:0 0 8px; padding-left:10px; border-left:3px solid var(--ok) }
.om.needed { border-color:var(--major) }
.om .fact { font-weight:600 } .om .loses { color:var(--muted) }
.none { color:var(--ok); font-size:13px; margin:4px 0 }
table.sum { border-collapse:collapse; font-size:13.5px; margin:8px 0 28px }
table.sum th, table.sum td { border:1px solid var(--line); padding:5px 10px; text-align:left }
table.sum th { background:rgba(127,127,127,.1) }
"""


def render(runs: list[tuple[str | None, Path]], plan_path: Path) -> str:
    data = [(run_label(r, label), collect(r), r) for label, r in runs]
    ids: list[str] = []
    for _, pieces, _ in data:
        for p in pieces:
            if p["id"] not in ids:
                ids.append(p["id"])

    parts = [f"<title>Writing variants — {len(runs)} runs</title>", f"<style>{CSS}</style>"]
    parts.append("<header><h1>Writing variants</h1><div class='sub'>")
    parts.append(
        " &nbsp;·&nbsp; ".join(f"<b>{html.escape(n)}</b> {html.escape(s)}" for (n, s), _, _ in data)
    )
    parts.append("</div></header>")
    parts.append(
        "<nav>" + "".join(f"<a href='#{i}'>{html.escape(i)}</a>" for i in ids) + "</nav><main>"
    )

    parts.append("<table class='sum'><tr><th>piece</th><th>source words</th>")
    for (n, _), _, _ in data:
        parts.append(f"<th>{html.escape(n)}</th>")
    parts.append("</tr>")
    for pid in ids:
        sw = source_words(plan_path, pid)
        parts.append(f"<tr><td>{html.escape(pid)}</td><td>{sw or '—'}</td>")
        for _, pieces, _ in data:
            hit = next((p for p in pieces if p["id"] == pid), None)
            if not hit:
                parts.append("<td>—</td>")
                continue
            pct = f" ({round(100 * hit['words'] / sw)}% of source)" if sw else ""
            need = sum(1 for o in hit["omissions"] if o["verdict"] == "needed")
            blocking = sum(1 for f in hit["findings"] if f["severity"] in ("blocking", "major"))
            parts.append(
                f"<td>{hit['words']} words{pct}<br><span style='color:var(--muted)'>"
                f"{hit['rounds']} rounds · {blocking} open · {need} needed omissions</span></td>"
            )
        parts.append("</tr>")
    parts.append("</table>")

    for pid in ids:
        parts.append(
            f"<section class='piece' id='{html.escape(pid)}'><h2>{html.escape(pid)}</h2><div class='grid'>"
        )
        for (name, _), pieces, _ in data:
            hit = next((p for p in pieces if p["id"] == pid), None)
            if not hit:
                continue
            parts.append("<div class='card'>")
            parts.append(
                f"<h3><span>{html.escape(name)}</span><span class='meta'>{hit['words']} words · "
                f"{html.escape(str(hit['state']))} · {hit['rounds']} rounds</span></h3>"
            )
            parts.append(f"<div class='ms'>{md_to_html(hit['body'])}</div>")
            parts.append("<div class='fb'>")
            parts.append("<h4>What the reader lost (worth)</h4>")
            if hit["omissions"]:
                for o in hit["omissions"]:
                    parts.append(
                        f"<div class='om {html.escape(o['verdict'])}'><div class='fact'>"
                        f"{html.escape(o['fact'])} <span class='tag'>{html.escape(o['verdict'])}</span></div>"
                        f"<div class='loses'>{html.escape(o['loses'])}</div></div>"
                    )
            else:
                parts.append("<p class='none'>no omissions reported</p>")
            parts.append("<h4>Open findings, final round</h4>")
            if hit["findings"]:
                for f in hit["findings"]:
                    loc = f" · {html.escape(f['locator'])}" if f["locator"] else ""
                    sug = (
                        f"<div class='loses'>suggestion: {html.escape(f['suggestion'])}</div>"
                        if f["suggestion"]
                        else ""
                    )
                    parts.append(
                        f"<div class='f {html.escape(f['severity'])}'><div class='tag'>"
                        f"{html.escape(f['severity'])} · {html.escape(f['lens'])} · "
                        f"{html.escape(f['category'])}{loc}</div>"
                        f"<p class='note'>{html.escape(f['note'])}</p>{sug}</div>"
                    )
            else:
                parts.append("<p class='none'>clean</p>")
            parts.append("</div></div>")
        parts.append("</div></section>")
    parts.append("</main>")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs", nargs="+", help="run dir, or label=run-dir for a readable column name")
    ap.add_argument("--plan", type=Path, default=ROOT / "editions/004/plan.yaml")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    pairs = [split_label(a) for a in args.runs]
    runs = [(lab, p) for lab, p in pairs if (p / "articles").exists() or (p / "editorial").exists()]
    if not runs:
        sys.exit("no run dirs with content among: " + ", ".join(str(p) for _, p in pairs))
    out = args.out or (runs[0][1].parent / "compare.html")
    out.write_text(render(runs, args.plan), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
