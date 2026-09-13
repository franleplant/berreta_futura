"""Usage: uv run python tools/pdf2md.py <file.pdf>

Print a PDF's text as plain Markdown: hard-wrapped lines rejoined into
paragraphs, numbered section titles as headings. Deterministic, no model.
"""

import re
import sys

from pypdf import PdfReader

HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][^.]{2,80})$")


def paragraphs(pages):
    lines = []
    for page in pages:
        lines.extend((page.extract_text() or "").splitlines())
        lines.append("")
    out, buf = [], []
    for line in lines:
        line = line.strip()
        if not line:
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        m = HEADING.match(line)
        if m:
            if buf:
                out.append(" ".join(buf))
                buf = []
            if not m.group(2).strip()[-1].isdigit():
                depth = min(m.group(1).count(".") + 2, 4)
                out.append("#" * depth + " " + m.group(2).strip())
            continue
        buf.append(line)
        if line.endswith((".", "!", "?", ":")) and len(line) < 55:
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return [p for p in out if not p.isdigit() and ". . ." not in p and p != "Contents"]


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    reader = PdfReader(sys.argv[1])
    print("\n\n".join(paragraphs(reader.pages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
