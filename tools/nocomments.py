#!/usr/bin/env python3
import ast, io, pathlib, re, sys, tokenize

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = ["mag/src", "src/magazine", "tools"]
PRAGMA = re.compile(r"#\s*(pragma|noqa|type:|fmt:)")


def python_offenses(path):
    src = path.read_text()
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type == tokenize.COMMENT and not PRAGMA.search(t.string) and not (t.start[0] == 1 and t.string.startswith("#!")):
            yield t.start[0], "comment"
    for node in ast.walk(ast.parse(src)):
        for st in (node.body if isinstance(getattr(node, "body", None), list) else []):
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
                yield st.lineno, "docstring"


def rust_offenses(path):
    src = path.read_text()
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
        elif src.startswith("//", i) or src.startswith("/*", i):
            yield line, "comment"
            end = src.find("\n" if c == "/" and src[i + 1] == "/" else "*/", i)
            i = n if end < 0 else end
            continue
        elif c == "r" and i + 1 < n and src[i + 1] in '"#' and not (i and (src[i - 1].isalnum() or src[i - 1] == "_")):
            j = i + 1
            while j < n and src[j] == "#":
                j += 1
            if j < n and src[j] == '"':
                close = '"' + "#" * (j - i - 1)
                k = src.find(close, j + 1)
                k = n if k < 0 else k + len(close)
                line += src.count("\n", i, k)
                i = k
                continue
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            line += src.count("\n", i, j)
            i = j + 1
            continue
        elif c == "'" and i + 2 < n and (src[i + 1] == "\\" or src[i + 2] == "'"):
            j = src.find("'", i + 2 if src[i + 1] == "\\" else i + 1)
            i = n if j < 0 else j + 1
            continue
        i += 1


def shell_offenses(path):
    for no, text in enumerate(path.read_text().split("\n"), 1):
        if text.lstrip().startswith("#") and not (no == 1 and text.startswith("#!")):
            yield no, "comment"


def main():
    offenses = []
    for target in TARGETS:
        for path in sorted((ROOT / target).rglob("*")):
            if not path.is_file() or path.name == "nocomments.py":
                continue
            if path.suffix == ".py":
                found = python_offenses(path)
            elif path.suffix == ".rs":
                found = rust_offenses(path)
            elif path.suffix == "" and path.read_text(errors="ignore").startswith("#!/bin/sh"):
                found = shell_offenses(path)
            else:
                continue
            offenses += [f"{path.relative_to(ROOT)}:{line}: {kind}" for line, kind in found]
    print("\n".join(offenses) or "no comments")
    sys.exit(1 if offenses else 0)


if __name__ == "__main__":
    main()
