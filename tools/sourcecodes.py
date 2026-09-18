#!/usr/bin/env python3
"""Usage: tools/sourcecodes.py <edition> [--check]

Writes editions/<edition>/source-codes: one SVG per source for the web leg
and codes.json recording the print fit. --check regenerates into a temporary
directory and compares, without touching the committed tree.
"""

import filecmp
import json
import re
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import segno
import yaml

from magazine.manifest import source_code_payload

ROOT = Path(__file__).resolve().parent.parent
ILLUSTRATED_ROOM = 41.0
PLAIN_ROOM = 55.5
LEVELS = ("H", "Q", "M", "L")
QUIET = 4
MIN_MODULE = 0.35 * 72 / 25.4
EPSILON = 1e-9
UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def fitted(payload: str, room: float) -> dict | None:
    best = None
    for level in LEVELS:
        symbol = segno.make(payload, error=level, micro=False)
        modules = int(symbol.symbol_size(border=QUIET)[0])
        module = room / modules
        if module < MIN_MODULE:
            continue
        if best is None or module > best[2] + EPSILON:
            best = (level, modules, module)
    if best is None:
        return None
    level, modules, _ = best
    symbol = segno.make(payload, error=level, micro=False)
    return {
        "error": level,
        "modules": modules,
        "matrix": ["".join("1" if cell else "0" for cell in row) for row in symbol.matrix],
    }


def web_svg(payload: str) -> bytes:
    buffer = BytesIO()
    segno.make(payload, error="L", micro=False).save(
        buffer,
        kind="svg",
        scale=1,
        border=4,
        dark="#17191c",
        light="#ffffff",
        xmldecl=False,
        svgns=True,
        nl=False,
    )
    return buffer.getvalue()


def sources(edition: str) -> list[tuple[str, str, float]]:
    manifest = yaml.safe_load((ROOT / "editions" / edition / "edition.yaml").read_text())
    rows, seen = [], set()
    for article in manifest["articles"]:
        room = ILLUSTRATED_ROOM if article.get("opener_art") is not None else PLAIN_ROOM
        source_id = (article.get("source_ids") or [article["id"]])[0]
        record = yaml.safe_load(
            (ROOT / "library" / "sources" / source_id / "record.yaml").read_text()
        )
        url = record.get("url")
        if not url or source_id in seen:
            continue
        seen.add(source_id)
        rows.append((source_id, url, room))
    return rows


def generate(edition: str, destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    codes = []
    for source_id, url, room in sources(edition):
        payload = source_code_payload(url)
        name = "source-code-%s.svg" % UNSAFE.sub("-", source_id)
        (destination / name).write_bytes(web_svg(payload))
        codes.append(
            {
                "payload": payload,
                "source_id": source_id,
                "svg": name,
                "print": fitted(payload, room),
            }
        )
    (destination / "codes.json").write_text(
        json.dumps({"codes": codes}, indent=2, sort_keys=True) + "\n"
    )
    return sum(1 for code in codes if code["print"] is None)


def check(edition: str, committed: Path) -> int:
    if not committed.is_dir():
        print("no committed source codes at %s" % committed)
        return 1
    with tempfile.TemporaryDirectory() as scratch:
        fresh = Path(scratch) / "source-codes"
        generate(edition, fresh)
        expected = sorted(path.name for path in fresh.iterdir())
        found = sorted(path.name for path in committed.iterdir())
        if expected != found:
            print("file set differs: expected %s, found %s" % (expected, found))
            return 1
        match, mismatch, errors = filecmp.cmpfiles(fresh, committed, expected, shallow=False)
        if mismatch or errors:
            print("content differs: %s, unreadable: %s" % (mismatch, errors))
            return 1
        print("%d files reproduce byte-for-byte" % len(match))
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    edition = argv[0]
    committed = ROOT / "editions" / edition / "source-codes"
    if "--check" in argv[1:]:
        return check(edition, committed)
    declines = generate(edition, committed)
    print("wrote %s; print declines on %d" % (committed, declines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
