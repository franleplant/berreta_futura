"""Usage: uv run python mag/tests/highlight_corpus.py <repo root>"""

import json
import subprocess
import sys
from pathlib import Path

from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from magazine.html_edition import _highlight_code
from magazine.publication_document import _GLYPH_FALLBACKS, _MARKDOWN, split_frontmatter
from magazine.reader_text import fold_reader_characters

root = Path(sys.argv[1])
paths = ["library/sources/*/article.md", "editions/*.md"]
files = subprocess.run(["git", "-C", str(root), "ls-files", *paths], capture_output=True, text=True)
css = HtmlFormatter()._get_css_classes


def tokens(code, language):
    try:
        lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False) if language else None
    except ClassNotFound:
        lexer = None
    return lexer and [[value, css(kind)] for kind, value in lexer.get_tokens(code)]


blocks = {}
for name in files.stdout.split():
    body = split_frontmatter((root / name).read_text(encoding="utf-8"))[1]
    for token in _MARKDOWN.parse(body.translate(_GLYPH_FALLBACKS)):
        if token.type in ("fence", "code_block"):
            info = token.info if token.type == "fence" else ""
            language = info.split(maxsplit=1)[0] if info else ""
            row = blocks.setdefault((token.content, language), {"files": []})
            row["files"].append(name)
out = []
for (code, language), row in blocks.items():
    folded = fold_reader_characters(code)
    scratch = all(
        part.startswith(("run-", "render-")) for f in row["files"] for part in f.split("/")[2:3]
    )
    out.append(
        {
            "language": language,
            "code": folded,
            "html": _highlight_code(code, language),
            "tokens": tokens(folded, language),
            "files": row["files"],
            "scratch": scratch,
        }
    )
json.dump(out, sys.stdout, ensure_ascii=False)
