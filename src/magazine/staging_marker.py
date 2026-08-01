"""What an unwritten manuscript slot looks like, and how to refuse one.

``mag article stage`` opens a piece by writing a marker rather than prose: YAML
frontmatter declaring ``stage_status: todo`` under the reader-visible label
``EDITORIAL WORK REQUIRED``, and a body that says only that no source prose was
generated.  The marker exists to be replaced.  Nothing downstream of production
may treat it as writing.

It was treated as writing.  Edition ``rerun-004-the-systems-around-the-model``
validated, built and preflighted clean while its opening editorial was still a
marker, and the words ``EDITORIAL WORK REQUIRED`` were typeset onto reader page
four under the title ``Untitled editorial``.  Every gate said yes because the
marker is, structurally, a perfectly well-formed short manuscript.

So recognition here is structural and never a length heuristic -- a two-hundred
word editorial is still an editorial, and must pass.  Three signals are read,
and any one of them condemns the file:

``stage_status``
    Frontmatter ``stage_status: todo``.  This is the authoritative signal.
    Staging is the only thing that writes the key, no authored manuscript
    carries it, and it has exactly one meaning: this slot has not been written.
    Whoever writes the piece deletes it.

``label``
    Frontmatter ``label: EDITORIAL WORK REQUIRED``.  Corroborating, and
    sufficient on its own, because ``label`` is *printed* on the opener -- the
    real ones read ``FAITHFUL EDIT``, ``FAITHFUL SYNTHESIS``, ``EDITORIAL:
    ORIGINAL EDITOR TEXT``.  A file still carrying the staged label would set
    those three words in type even if its body had since been written.

``body``
    A reader-visible body consisting of nothing but the single staging TODO
    paragraph.  Corroborating, and sufficient on its own, because a body that
    is only an instruction to write the body is not prose under any reading.
    It is decided from the parsed block tree -- exactly one paragraph, whose
    text opens with the TODO prefix -- rather than by searching the file for
    the sentence, so an article that quotes or explains the marker is
    untouched, and so is one that mentions ``stage_status`` in a code block.

The refusal names every unfinished piece in one error, because the answer to
all of them is one command, and finding them one build at a time is how the
first one got through.

The check deliberately does not stop ``mag produce``: markers are produce's
input.  Produce reaches validation through
:meth:`~magazine.produce.DefaultProductionGates.check_edition`, which runs it
guarded and records the refusal as the failing edition gate it already knows
how to carry as a pre-existing failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError
from .io import load_structured
from .line_review import EDITORIAL_ARTICLE_ID
from .publication_document import (
    DocumentParseError,
    Paragraph,
    Text,
    parse_publication_document,
    split_frontmatter,
)

STAGE_STATUS_KEY = "stage_status"
STAGE_STATUS_TODO = "todo"
STAGING_LABEL = "EDITORIAL WORK REQUIRED"
STAGING_TODO_PREFIX = "TODO(editor):"
STAGING_TODO = (
    f"{STAGING_TODO_PREFIX} Replace this staging marker with a source-faithful "
    "manuscript. No source prose was generated."
)

_SIGNAL_DESCRIPTIONS = {
    "stage_status": f"frontmatter declares {STAGE_STATUS_KEY}: {STAGE_STATUS_TODO}",
    "label": f"frontmatter label is still {STAGING_LABEL}",
    "body": "the body is only the staging TODO paragraph",
}


def staging_marker_signals(manuscript: Path) -> tuple[str, ...]:
    """Which of the three structural signals this file raises, in order.

    An empty tuple means the file is a manuscript as far as this module can
    tell.  A file that does not exist raises nothing here: whether a declared
    manuscript is missing is the manifest loader's complaint, not this one's,
    and reporting it twice would put two different instructions on one problem.
    """

    try:
        text = manuscript.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    try:
        metadata, body = split_frontmatter(text)
    except DocumentParseError:
        # Unparseable frontmatter is its own failure, reported by whoever
        # loads the edition; it is not evidence about whether prose exists.
        return ()
    signals: list[str] = []
    if _text(metadata.get(STAGE_STATUS_KEY)).lower() == STAGE_STATUS_TODO:
        signals.append("stage_status")
    if _text(metadata.get("label")) == STAGING_LABEL:
        signals.append("label")
    if _body_is_only_the_todo(body):
        signals.append("body")
    return tuple(signals)


def is_staging_marker(manuscript: Path) -> bool:
    """Whether this file is still the slot ``mag article stage`` created."""

    return bool(staging_marker_signals(manuscript))


def declared_manuscript_paths(
    root: Path,
    edition_dir: Path,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Path]:
    """Every piece the edition declares, by piece id, from the raw manifest.

    Raw, so a manifest that will not load for an unrelated reason still reports
    which pieces are undrafted rather than collapsing into one opaque error.
    The opening editorial has no article row of its own -- it is a path, not an
    id -- so it joins under :data:`~magazine.line_review.EDITORIAL_ARTICLE_ID`.
    """

    paths: dict[str, Path] = {}
    rows = (manifest or {}).get("articles")
    for index, row in enumerate(rows if isinstance(rows, list) else (), start=1):
        if not isinstance(row, Mapping):
            continue
        declared = _text(row.get("manuscript"))
        if not declared:
            continue
        paths[_text(row.get("id")) or f"article-{index}"] = _declared_file(
            root, edition_dir, declared
        )
    editorial = _text((manifest or {}).get("editorial"))
    if editorial:
        paths[EDITORIAL_ARTICLE_ID] = _declared_file(root, edition_dir, editorial)
    return paths


def unwritten_pieces(paths: Mapping[str, Path]) -> dict[str, tuple[str, ...]]:
    """The subset of ``paths`` that is still staged, with each one's signals."""

    return {
        piece_id: signals
        for piece_id in sorted(paths)
        if (signals := staging_marker_signals(paths[piece_id]))
    }


def require_written_manuscripts(root: Path, editions_dir: Path, edition_id: str) -> None:
    """Refuse an edition any of whose declared pieces is still a staging marker.

    Silent when the manifest is absent or unreadable: an edition that cannot be
    loaded at all is the loader's error to report, and pre-empting it with a
    guess about staging would bury it.
    """

    edition_dir = editions_dir / edition_id
    manifest_path = edition_dir / "edition.yaml"
    if not manifest_path.is_file():
        return
    try:
        manifest = load_structured(manifest_path)
    except ValidationError:
        return
    if not isinstance(manifest, Mapping):
        return
    paths = declared_manuscript_paths(root, edition_dir, manifest)
    unwritten = unwritten_pieces(paths)
    if not unwritten:
        return
    named = [
        f"{piece_id}: {_relative(root, paths[piece_id])} is a staging marker "
        f"({'; '.join(_SIGNAL_DESCRIPTIONS[signal] for signal in signals)})"
        for piece_id, signals in unwritten.items()
    ]
    raise ValidationError(
        [
            f"{edition_id}: {len(unwritten)} piece(s) are still unwritten staging "
            "markers and cannot be validated, built, packaged or released.",
            *named,
            "Draft every piece named above with "
            f"`uv run --locked mag produce {edition_id}`.",
        ]
    )


def _body_is_only_the_todo(body: str) -> bool:
    try:
        document = parse_publication_document(body)
    except DocumentParseError:
        # The staged skeleton's body is an HTML comment, which has no
        # reader-visible content and no document tree.  Its frontmatter has
        # already spoken; nothing here can add to that.
        return False
    if len(document.blocks) != 1:
        return False
    block = document.blocks[0]
    if not isinstance(block, Paragraph):
        return False
    text = "".join(
        child.value for child in block.children if isinstance(child, Text)
    ).strip()
    return text.startswith(STAGING_TODO_PREFIX)


def _declared_file(root: Path, edition_dir: Path, declared: str) -> Path:
    """Resolve a manifest path the way the manifest loader does.

    A path beginning ``editions/`` is project-relative; anything else is
    relative to this edition's own directory, which is how a manuscript can
    legitimately live outside ``editions/``.
    """

    path = Path(declared)
    if path.parts and path.parts[0] == "editions":
        return root / path
    return edition_dir / path


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: object) -> str:
    return str(value or "").strip()
