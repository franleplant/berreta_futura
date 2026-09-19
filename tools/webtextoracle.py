#!/usr/bin/env python3
"""Usage: tools/webtextoracle.py

Checks mag/tests/web_text_cases.json's SPEC-AUTHORED escape expectations
against CPython's html.escape, then writes mag/tests/web_text_expected.json
with the TRANSCRIBED expectations for text/verbatim/attr.
"""

import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from magazine.reader_text import (  # noqa: E402
    educate_reader_quotes,
    fold_reader_characters,
)


def main(argv: list[str]) -> int:
    if argv and argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cases = json.loads((ROOT / "mag" / "tests" / "web_text_cases.json").read_text())
    disagreements = []
    for row in cases["escape"]:
        for flag, key in ((False, "unquoted"), (True, "quoted")):
            actual = escape(row["input"], quote=flag)
            if actual != row[key]:
                disagreements.append(
                    "%s/%s: authored %r, CPython %r" % (row["name"], key, row[key], actual)
                )
    if disagreements:
        print("SPEC-AUTHORED EXPECTATIONS DISAGREE WITH CPYTHON:")
        for line in disagreements:
            print("  " + line)
        return 1
    print("%d spec-authored escape rows agree with CPython" % (len(cases["escape"]) * 2))

    composed = {}
    for row in cases["composed"]:
        value = row["input"]
        composed[row["name"]] = {
            "text": escape(fold_reader_characters(educate_reader_quotes(value)), quote=False),
            "verbatim": escape(fold_reader_characters(value), quote=False),
            "attr": escape(fold_reader_characters(value), quote=True),
        }
    out = ROOT / "mag" / "tests" / "web_text_expected.json"
    out.write_text(json.dumps(composed, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print("wrote %d transcribed composed rows to %s" % (len(composed), out.name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
