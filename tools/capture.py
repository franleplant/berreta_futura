#!/usr/bin/env python3
"""capture.py — scaffold, then validate, a source capture.

    uv run python tools/capture.py <url> [--edition 006] [--tags a,b] \
        [--title ...] [--author ...] [--published YYYY-MM-DD]
    uv run python tools/capture.py --finish <source-id>

The first form does the deterministic part of intake: fetches the page,
derives the source id (48-char title slug + first 8 hex of sha256(url)),
writes library/sources/<id>/ with a record.yaml scaffold, an article.md
stub, and an empty media/, saves the raw HTML under .magazine/capture/,
queues the id in library/release-state.yaml, prepends an entry to
sources.md, and prints the checklist for finishing the capture.

It never writes article body text: filling article.md and media/ verbatim
is the caller's job, following the printed checklist. When that is done,
`--finish <id>` validates the capture and copies the record's synopsis
into the sources.md entry. A capture is not complete until --finish passes.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "library" / "sources"
RELEASE_STATE = ROOT / "library" / "release-state.yaml"
SOURCES_MD = ROOT / "sources.md"
RAW_DIR = ROOT / ".magazine" / "capture"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

CHECKLIST = """\
Scaffolded {sid}
Raw HTML: .magazine/capture/{sid}.html

To finish this capture (do it now; a capture is incomplete until then):
1. Write library/sources/{sid}/article.md from the raw HTML: the source's
   substantive text VERBATIM, in source order — exact wording, headings,
   lists, links, emphasis; fenced code blocks must be contiguous exact runs
   from the source. Drop site chrome only. Keep the source's own typography
   (em dashes, curly quotes) inside captured text; never author U+2014
   yourself. House format: `# <title>`, a byline line, then the body
   (see any existing library/sources/*/article.md).
2. Download each substantive body image at original resolution to
   library/sources/{sid}/media/001.<ext>, 002.<ext>, ... in order of
   appearance, and reference it at its original position as
   ![](media/001.png), keeping meaningful alt text.
3. Set `synopsis:` in library/sources/{sid}/record.yaml to one factual
   sentence (match the tone of the other records).
4. Run: uv run python tools/capture.py --finish {sid}
   It validates the capture and completes the sources.md entry."""


def source_id(title: str, url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48].rstrip("-")
    return f"{slug}-{hashlib.sha256(url.encode()).hexdigest()[:8]}"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def meta_content(html: str, *patterns: str) -> str | None:
    for pat in patterns:
        m = (
            re.search(
                rf'<meta[^>]+(?:property|name)=["\']{pat}["\'][^>]+content=["\']([^"\']+)',
                html,
            )
            or re.search(
                rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{pat}["\']',
                html,
            )
            or re.search(rf'"{pat}"\s*:\s*"([^"]+)"', html)
        )
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return None


def page_title(html: str) -> str | None:
    title = meta_content(html, "og:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        title = html_lib.unescape(m.group(1)).strip() if m else None
    if title:
        title = re.split(r"\s+[|•·]\s+", title)[0].strip()
        title = re.sub(r"\s+", " ", title)
    return title or None


def page_published(html: str) -> str | None:
    stamp = meta_content(html, "article:published_time", "datePublished")
    if not stamp:
        m = re.search(r'datetime=["\'](\d{4}-\d{2}-\d{2})', html)
        stamp = m.group(1) if m else None
    return stamp[:10] if stamp else None


def load_release_state() -> dict:
    return yaml.safe_load(RELEASE_STATE.read_text(encoding="utf-8"))


def queue_source(state: dict, edition: str, sid: str) -> None:
    collecting = state.setdefault("collecting_editions", [])
    entry = next((e for e in collecting if e["id"] == edition), None)
    if entry is None:
        entry = {
            "id": edition,
            "issue_number": int(edition),
            "status": "collecting",
            "source_ids": [],
        }
        collecting.append(entry)
        state["intake_edition_id"] = edition
    if sid not in entry["source_ids"]:
        entry["source_ids"].append(sid)


def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, width=100, default_flow_style=False
    )


def sources_md_entry(record: dict, edition: str) -> list[str]:
    author = record.get("author") or ""
    lines = [
        f"## {record['title']}" + (f" — {author}" if author else ""),
        "",
        f"- ID: `{record['id']}`",
        f"- Source: {record['url']}",
    ]
    if record.get("published_at"):
        lines.append(f"- Published: {record['published_at']}")
    lines.append(f"- Captured: {record['captured_at']}")
    if record.get("tags"):
        lines.append(f"- Tags: {', '.join(record['tags'])}")
    lines.append(f"- Release: queued for `{edition}`")
    return lines


def prepend_sources_md(record: dict, edition: str, queued: int) -> None:
    lines = SOURCES_MD.read_text(encoding="utf-8").splitlines()
    collecting_line = f"_Collecting: `{edition}` ({queued} queued)._"
    for i, line in enumerate(lines):
        if re.fullmatch(rf"_Collecting: `{edition}` \(\d+ queued\)\._", line):
            lines[i] = collecting_line
            break
    else:
        last_meta = max(i for i, line in enumerate(lines[:20]) if line.startswith("_"))
        lines[last_meta + 1 : last_meta + 1] = ["", collecting_line]
    first_entry = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    lines[first_entry:first_entry] = sources_md_entry(record, edition) + [""]
    SOURCES_MD.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def capture(args: argparse.Namespace) -> int:
    html = fetch(args.url)
    title = args.title or page_title(html)
    if not title:
        print(f"could not extract a title from {args.url}; pass --title", file=sys.stderr)
        return 1
    author = args.author or meta_content(html, "author", "article:author") or ""
    published = args.published or page_published(html)

    sid = source_id(title, args.url)
    src_dir = SOURCES / sid
    if src_dir.exists():
        print(f"{src_dir.relative_to(ROOT)} already exists", file=sys.stderr)
        return 1

    (src_dir / "media").mkdir(parents=True)
    record = {
        "id": sid,
        "title": title,
        "author": author,
        "url": args.url,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if published:
        record["published_at"] = published
    record["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    record["synopsis"] = ""
    (src_dir / "record.yaml").write_text(dump_yaml(record), encoding="utf-8")

    stub = f"# {title}\n\n<!-- TODO: verbatim capture pending; raw HTML in .magazine/capture/{sid}.html -->\n"
    (src_dir / "article.md").write_text(stub, encoding="utf-8")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{sid}.html").write_text(html, encoding="utf-8")

    state = load_release_state()
    edition = args.edition or state.get("intake_edition_id")
    if not edition:
        print("no --edition and no intake_edition_id in release-state.yaml", file=sys.stderr)
        return 1
    edition = str(edition)
    queue_source(state, edition, sid)
    RELEASE_STATE.write_text(dump_yaml(state), encoding="utf-8")

    queued = next(len(e["source_ids"]) for e in state["collecting_editions"] if e["id"] == edition)
    prepend_sources_md(record, edition, queued)

    print(CHECKLIST.format(sid=sid))
    return 0


def _capture_problems(src_dir: Path, record: dict, article: str) -> list[str]:
    problems = []
    if "TODO: verbatim capture pending" in article:
        problems.append("article.md still holds the scaffold stub")
    if len(article.split()) < 100:
        problems.append(f"article.md is only {len(article.split())} words")
    if not (record.get("synopsis") or "").strip():
        problems.append("record.yaml synopsis is empty")
    for ref in re.findall(r"\]\((media/[^)]+)\)", article):
        if not (src_dir / ref).exists():
            problems.append(f"article.md references missing {ref}")
    for media_file in sorted((src_dir / "media").glob("*")):
        if f"media/{media_file.name}" not in article:
            problems.append(f"media/{media_file.name} is not referenced in article.md")
    return problems


def _add_synopsis(sid: str, synopsis: str) -> bool:
    lines = SOURCES_MD.read_text(encoding="utf-8").splitlines()
    try:
        id_line = lines.index(f"- ID: `{sid}`")
    except ValueError:
        return False
    end = id_line
    while end < len(lines) and lines[end].startswith("- "):
        end += 1
    if synopsis not in "\n".join(lines[end : end + 2]):
        lines[end:end] = ["", synopsis]
        SOURCES_MD.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return True


def finish(sid: str) -> int:
    src_dir = SOURCES / sid
    record_path = src_dir / "record.yaml"
    article_path = src_dir / "article.md"
    if not record_path.exists():
        print(f"no such source: {sid}", file=sys.stderr)
        return 1

    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    article = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
    problems = _capture_problems(src_dir, record, article)
    if problems:
        print(f"capture of {sid} is incomplete:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if not _add_synopsis(sid, (record.get("synopsis") or "").strip()):
        print(f"sources.md has no entry for {sid}; re-run the capture", file=sys.stderr)
        return 1
    print(f"capture of {sid} is complete")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="page to capture")
    parser.add_argument(
        "--edition", help="collecting edition to queue into (default: intake edition)"
    )
    parser.add_argument("--tags", help="comma-separated tags")
    parser.add_argument("--title", help="override the extracted title")
    parser.add_argument("--author", help="override the extracted author")
    parser.add_argument("--published", help="override the publish date (YYYY-MM-DD)")
    parser.add_argument(
        "--finish",
        metavar="SOURCE_ID",
        help="validate a filled capture and complete its sources.md entry",
    )
    args = parser.parse_args()

    if args.finish:
        return finish(args.finish)
    if not args.url:
        parser.error("a url is required unless --finish is given")
    return capture(args)


if __name__ == "__main__":
    sys.exit(main())
