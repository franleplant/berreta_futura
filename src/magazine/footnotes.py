"""Refuse footnote syntax that this magazine's renderer would print literally.

``publication_document`` parses manuscripts with ``MarkdownIt("commonmark")``
and no plugins.  CommonMark has no footnotes, so ``[^1]`` is not a reference
and ``[^1]: the note`` is not a definition: both are ordinary text.  They parse
cleanly, they validate, they build, and they arrive on the printed page as the
literal characters ``[^1]``, twice, with no link between them and no note at
the foot of anything.

Nothing caught this because no article had ever used the syntax.  A staged
placeholder finally did, and it was noticed only because a writer happened to
read the renderer.  "Somebody reads the renderer" is not a control.

**Why refusing rather than supporting.**  Supporting footnotes is not a plugin
line.  It is a new inline node and a new block node in the document tree, and
then every adapter that walks that tree -- the print renderer, the booklet
imposition, the HTML edition, the web edition, the reader-text dump, the
pagination measurement, the translation block-structure gate -- has to be
taught what to do with them, in a fixed A5 page where "the foot of the page"
is a layout decision nobody has made.  Sources do use footnotes, and a
``faithful_edit`` of one has to put the note somewhere; the honest answer today
is that it goes inline, in the sentence or in parentheses, which is what every
shipped article has done.  When the house wants real footnotes it should want
them deliberately, with a page design; until then the cheap, loud refusal is
worth far more than a silent literal.

The check reads the parsed document rather than the raw file, so a marker
inside a code fence or inline code is untouched: code is quoted, not typeset as
prose, and an article *about* footnote syntax must remain writable.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import ValidationError
from .publication_document import (
    Block,
    BlockQuote,
    DocumentParseError,
    Emphasis,
    FencedCode,
    Heading,
    Inline,
    Link,
    ListBlock,
    Paragraph,
    Strong,
    Text,
    parse_publication_document,
)

# A CommonMark link label opening with a caret: the footnote reference and the
# definition alike, since a definition is just a reference followed by a colon.
# The label may not be empty and may not contain a bracket, which is what keeps
# ordinary prose -- an array index, a regex class -- out of the net.
_FOOTNOTE = re.compile(r"\[\^[^\[\]\s][^\[\]]*\]")


def footnote_markers(manuscript: Path) -> list[str]:
    """Every footnote-looking marker in this manuscript's reader-visible prose.

    In reading order and with duplicates kept, because a reference and its
    definition are two separate places a writer has to go and edit.  A file
    that cannot be read or parsed yields nothing: whether a manuscript is
    well-formed is somebody else's error to raise, and two errors about one
    file is one error too many.
    """

    try:
        text = manuscript.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        document = parse_publication_document(text)
    except DocumentParseError:
        return []
    found: list[str] = []
    _walk_blocks(document.blocks, found)
    return found


def _walk_blocks(blocks: tuple[Block, ...], found: list[str]) -> None:
    """Collect markers from prose only: never from code, fenced or inline.

    ``document_structure.visible_blocks`` would be the obvious view to reuse,
    but it folds inline code into the prose it returns -- correct for a word
    count, wrong here, because an article explaining that ``[^1]`` does not
    work would then be unable to say so.
    """

    for block in blocks:
        if isinstance(block, (Heading, Paragraph)):
            _walk_inlines(block.children, found)
        elif isinstance(block, BlockQuote):
            _walk_blocks(block.children, found)
        elif isinstance(block, ListBlock):
            for item in block.items:
                _walk_blocks(item.children, found)
        elif isinstance(block, FencedCode):
            continue


def _walk_inlines(inlines: tuple[Inline, ...], found: list[str]) -> None:
    for inline in inlines:
        if isinstance(inline, Text):
            found.extend(_FOOTNOTE.findall(inline.value))
        elif isinstance(inline, (Emphasis, Strong, Link)):
            _walk_inlines(inline.children, found)


def footnote_errors(label: str, manuscript: Path) -> list[str]:
    """The refusal for one manuscript, or no errors at all."""

    markers = footnote_markers(manuscript)
    if not markers:
        return []
    unique = sorted(set(markers))
    return [
        f"{label} carries footnote syntax that would be typeset literally: "
        + ", ".join(unique)
        + ". This publication renders CommonMark with no footnote extension, so "
        "these print as the characters you see rather than as notes. Fold each "
        "note into its sentence or into a parenthetical, or drop it."
    ]


def verify_manuscript_footnotes(label: str, manuscript: Path) -> None:
    """Raise when a manuscript would print a footnote marker as text."""

    errors = footnote_errors(label, manuscript)
    if errors:
        raise ValidationError(errors)
