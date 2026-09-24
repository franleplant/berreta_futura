"""Usage: uv run python mag/tests/highlight_tables.py > mag/src/highlight/tables.json"""

import json
import sys

import pygments
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.lexers._mapping import LEXERS
from pygments.plugin import find_plugin_lexers
from pygments.lexers.c_cpp import CFamilyLexer
from pygments.token import Literal, Name, Operator, Text, _TokenType, string_to_tokentype

REGEX = ["TypeScriptLexer", "JavascriptLexer", "BashLexer", "TOMLLexer", "RustLexer", "SqlLexer"]
REGEX += ["PythonLexer", "CLexer", "HttpLexer"]
EXTENDED = ["YamlLexer"]
NATIVE = {"JsonLexer": "json", "TextLexer": "text"}
FLAGS = {2: "i", 8: "m", 16: "s"}
HTTP = {
    "header_callback": [Name.Attribute, Text, Operator, Text, Literal, Text],
    "continuous_header_callback": [Text, Literal, Text],
    "content_callback": [],
}
C_TYPES = ["stdlib_types", "c99_types", "c11_atomic_types", "linux_types"]
css = HtmlFormatter()._get_css_classes
TOKENS = ["String.Double", "Name.Tag", "Keyword.Constant", "Number.Float", "Number.Integer"]
TOKENS += ["Punctuation", "Comment.Single", "Comment.Multiline", "Error", "Text.Whitespace", "Text"]


def action(a):
    if a is None:
        return None
    if type(a) is _TokenType:
        return {"t": css(a)}
    cells = dict(zip(a.__code__.co_freevars, (c.cell_contents for c in a.__closure__ or ())))
    kind = a.__qualname__.split(".")
    if kind[0] == "bygroups":
        return {"g": [action(x) for x in cells["args"]]}
    if kind[0] == "using" and "_other" not in cells and not cells["kwargs"]:
        return {"u": list(cells["gt_kwargs"].get("stack", ["root"]))}
    if kind[0] == "HttpLexer":
        return {"h": kind[1], "classes": [css(t) for t in HTTP[kind[1]]]}
    if kind[0] != "YamlLexer":
        sys.exit(f"unsupported action {a.__qualname__}")
    row = {"f": kind[1]}
    for cell, key in [
        ("token_class", "t"),
        ("indent_token_class", "t"),
        ("content_token_class", "c"),
    ]:
        if cell in cells:
            row[key] = css(cells[cell])
    if "token_class" in cells:
        row["e"] = css(cells["token_class"].Error)
    if cells.get("start") or cells.get("implicit"):
        row["flag"] = True
    return row


def state(new):
    return list(new) if isinstance(new, tuple) else new


def lexer(name):
    cls = next(c for c in map(type, map(get_lexer_by_name, aliases)) if c.__name__ == name)
    flags = "".join(v for k, v in FLAGS.items() if cls.flags & k)
    states = {
        key: [[rex.__self__.pattern, action(a), state(new)] for rex, a, new in rules]
        for key, rules in cls(stripnl=False)._tokens.items()
    }
    table = {"extended": name in EXTENDED, "flags": flags, "states": states}
    if issubclass(cls, CFamilyLexer):
        table["retype"] = sorted(set().union(*(getattr(cls, t) for t in C_TYPES)))
    return table


if list(find_plugin_lexers()):
    sys.exit("plugin lexers change alias resolution")
aliases = sorted({alias for row in LEXERS.values() for alias in row[2]})
resolved = {alias: type(get_lexer_by_name(alias)).__name__ for alias in aliases}
kinds = {name: name for name in REGEX + EXTENDED} | NATIVE
mimetypes = {}
for name, row in LEXERS.items():
    for mimetype in row[4]:
        mimetypes.setdefault(mimetype, kinds.get(name, ""))
json.dump(
    {
        "pygments": pygments.__version__,
        "aliases": aliases,
        "mimetypes": mimetypes,
        "names": {a: kinds[n] for a, n in resolved.items() if n in kinds},
        "lexers": {name: lexer(name) for name in REGEX + EXTENDED},
        "classes": {name: css(string_to_tokentype(name)) for name in TOKENS},
    },
    sys.stdout,
    indent=0,
    sort_keys=True,
)
sys.stdout.write("\n")
