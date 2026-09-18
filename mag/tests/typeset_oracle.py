"""Stage an edition's render inputs and project the WeasyPrint leg's pre-layout text.

    uv run python mag/tests/typeset_oracle.py stage --request R --into DIR
    uv run python mag/tests/typeset_oracle.py project --root DIR --edition ID \
        --publication-name NAME --out FILE

`stage` reproduces engine_render_bridge._stage_inputs: every inputs[] row of a
render request is copied to its targetPath under one root. That root is the
"staged inputs" both legs of WP-2.1 read, so neither leg can be measured against
a tree the other did not see.

`project` is the oracle. html_edition.render_html_edition is the pure function the
WeasyPrint leg hands to layout; its text nodes are the reader-visible text before
any layout exists, which is what the Typst source tree has to reproduce.
"""

import argparse
import json
import shutil
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

BLOCK = frozenset(
    {
        "html",
        "body",
        "main",
        "header",
        "nav",
        "ol",
        "ul",
        "li",
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
        "aside",
        "figure",
        "figcaption",
        "pre",
        "blockquote",
        "hr",
        "time",
        "div",
        "img",
        "br",
    }
)
INLINE = frozenset({"span", "em", "strong", "code", "a", "sup", "sub"})
HEAD = "head"
HYPHENATE = frozenset("-­‐")
SOFT_HYPHEN = "­"


class Projector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.verbatim: list[str] = []
        self._pre = 0
        self._head = False
        self._run: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == HEAD:
            self._head = True
            return
        if tag == "pre":
            self._pre += 1
            self._run = []
        self._boundary(tag)

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        if not self._head:
            self._boundary(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == HEAD:
            self._head = False
            return
        if self._head:
            return
        if tag == "pre":
            self._pre -= 1
            self.verbatim.append("".join(self._run))
            self._run = []
        self._boundary(tag)

    def _boundary(self, tag: str) -> None:
        if self._head:
            return
        if tag in BLOCK:
            self.chunks.append("\n")
            if self._pre and tag == "br":
                self._run.append("\n")
        elif tag not in INLINE:
            raise SystemExit(f"unclassified tag <{tag}>: classify it before projecting")

    def handle_data(self, data: str) -> None:
        if self._head:
            return
        self.chunks.append(data)
        if self._pre:
            self._run.append(data)


def rejoin(text: str) -> str:
    out: list[str] = []
    chars = list(text)
    index = 0
    while index < len(chars):
        char = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        after = chars[index + 2] if index + 2 < len(chars) else ""
        if (
            char in HYPHENATE
            and index
            and chars[index - 1].isalpha()
            and following == "\n"
            and after.isalpha()
        ):
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def normalize(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw)
    return " ".join(rejoin(text).replace(SOFT_HYPHEN, "").split())


def project_html(html: str) -> dict[str, object]:
    parser = Projector()
    parser.feed(html)
    parser.close()
    return {"text": normalize("".join(parser.chunks)), "verbatim": parser.verbatim}


def stage(request_path: Path, into: Path, artifact_root: Path | None) -> int:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    declared = Path(request["artifactRoot"]).resolve()
    artifact_root = artifact_root.resolve() if artifact_root else declared
    into.mkdir(parents=True, exist_ok=True)
    for row in request["inputs"]:
        source = Path(row["sourcePath"]).resolve()
        if artifact_root != declared:
            source = artifact_root / source.relative_to(declared)
        if not source.is_file():
            raise SystemExit(f"staged input is missing: {source}")
        if artifact_root not in source.parents:
            raise SystemExit(f"staged input escapes artifactRoot: {source}")
        destination = into / row["targetPath"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    print(f"staged {len(request['inputs'])} inputs into {into}")
    return 0


def project(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from magazine.errors import ValidationError
    from magazine.html_edition import render_html_edition
    from magazine.manifest import load_edition
    from magazine.records import load_records

    root = args.root.resolve()
    records = {record.id: record for record in load_records(root / "library" / "sources")}
    try:
        edition = load_edition(
            root,
            args.edition,
            set(records),
            publication_name=args.publication_name,
            source_records=records,
            allow_missing_art=args.allow_missing_art,
            allow_unanchored_figures=args.allow_unanchored_figures,
        )
        projection = project_html(render_html_edition(edition).html)
    except ValidationError as error:
        projection = {"refusal": str(error)}
    args.out.write_text(
        json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    stager = commands.add_parser("stage")
    stager.add_argument("--request", type=Path, required=True)
    stager.add_argument("--into", type=Path, required=True)
    stager.add_argument("--artifact-root", type=Path, default=None)
    projector = commands.add_parser("project")
    projector.add_argument("--root", type=Path, required=True)
    projector.add_argument("--edition", required=True)
    projector.add_argument("--publication-name", required=True)
    projector.add_argument("--out", type=Path, required=True)
    projector.add_argument("--allow-missing-art", action="store_true")
    projector.add_argument("--allow-unanchored-figures", action="store_true")
    args = parser.parse_args()
    if args.command == "stage":
        return stage(args.request, args.into, args.artifact_root)
    return project(args)


if __name__ == "__main__":
    raise SystemExit(main())
