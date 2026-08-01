"""The one deterministic check that survives the fidelity ledger.

A reader can copy a code sample out of the magazine and run it, so a code
block is the one kind of prose where a single wrong character is a defect
rather than an edit.  Everything else about how faithfully a manuscript
represents its source is now judged at claim level by the fact-checker, and an
LLM judge is precisely the wrong instrument for eyeballing whitespace: it will
read past a dropped line of a config block, an unindented ``except``, a
smart-quoted flag.

So this module keeps exactly one rule, and points it at the source rather than
at anything the same writer produced in the same sitting: **every fenced code
block in a manuscript must appear, normalized-identically, inside one of the
article's committed source extractions.**  That is what the old
ledger-versus-manuscript comparison never established: the ledger's own code
column was written by the same agent as the manuscript, so agreement between
them proved only self-consistency.

Provenance beyond that is the pin's job, not this check's.  In the collecting
edition every extraction here has already had its body digest verified against
``edition.yaml`` before this runs, so a passing block is traced to committed,
hash-verified evidence.  A released edition may carry an extraction it never
pinned; the block is still checked against it, because "these are the source's
lines as committed" is worth proving even where "and the source has not moved
since" cannot be.

Normalization is deliberately narrow.  Tabs expand to four columns and trailing
whitespace goes, because those are invisible on the page and no reader can act
on them; leading blank lines and a trailing blank line inside the fence go,
because a fence's edges are typography.  Everything else is substantive:
indentation depth, line breaks, and every character of every line have to
match, since all three change what the code means.

The block is matched as a *contiguous run of lines* anywhere in an extraction
body, not against the extraction's own fences.  A source may present code
inside a fence, in an indented block, or inline in a transcript; where the
lines sit is the source's business, and what this check owes the reader is
that the lines themselves are the source's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .document_structure import visible_blocks
from .errors import ValidationError
from .extraction import Extraction
from .publication_document import DocumentParseError, parse_publication_document


def visible_code(text: str) -> str:
    """Normalize one code block to what the printed page actually shows."""

    lines = [line.rstrip() for line in text.expandtabs(4).splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def manuscript_code_blocks(manuscript: Path) -> list[str]:
    """Every fenced code block in a manuscript, normalized, in reading order.

    The blocks come from the same CommonMark parse the renderer typesets, so
    the check sees exactly the fences the reader will see -- including ones
    nested inside list items or block quotes -- and never a line scanner's
    smaller idea of Markdown.
    """

    try:
        document = parse_publication_document(manuscript.read_text(encoding="utf-8"))
    except DocumentParseError as exc:
        raise ValidationError(f"{manuscript}: {exc}") from exc
    return [
        visible_code(text)
        for kind, text in visible_blocks(document.blocks)
        if kind == "code"
    ]


def verify_manuscript_code_blocks(
    manuscript: Path, extractions: Iterable[Extraction]
) -> int:
    """Prove every fenced block in the manuscript is line-exact source code.

    Returns the number of blocks checked.  An article with no committed
    extractions is skipped and reports zero: there is nothing to check
    against, which is the released-edition state, not a failure.  A manuscript
    with no fences is likewise zero and always passes.

    Raises ``ValidationError`` naming the manuscript, the block, and the first
    line that diverges from the closest run of lines found in any extraction --
    the near miss is what an author needs, because a corrupted block is almost
    always right except for one line.
    """

    sources = tuple(extractions)
    if not sources:
        return 0
    blocks = manuscript_code_blocks(manuscript)
    errors: list[str] = []
    for index, block in enumerate(blocks, start=1):
        if not block:
            continue
        wanted = block.split("\n")
        if any(_contains_run(_body_lines(source.body), wanted) for source in sources):
            continue
        errors.append(_divergence(manuscript, index, wanted, sources))
    if errors:
        raise ValidationError(errors)
    return len(blocks)


def _body_lines(body: str) -> list[str]:
    return [line.rstrip() for line in body.expandtabs(4).splitlines()]


def _contains_run(haystack: list[str], wanted: list[str]) -> bool:
    width = len(wanted)
    return any(
        haystack[start : start + width] == wanted
        for start in range(len(haystack) - width + 1)
    )


def _divergence(
    manuscript: Path, index: int, wanted: list[str], sources: tuple[Extraction, ...]
) -> str:
    """Describe the closest near miss across every extraction, or its absence.

    "Closest" is the longest matching prefix: a block that is right for eleven
    lines and wrong on the twelfth reports line 12, which is the whole point.
    A block whose very first line appears nowhere gets the blunter message,
    because there is no near miss to point at and inventing one would send the
    author to an unrelated part of the source.
    """

    best_prefix = -1
    best: tuple[Extraction, int] | None = None
    for source in sources:
        haystack = _body_lines(source.body)
        for start, line in enumerate(haystack):
            if line != wanted[0]:
                continue
            prefix = 0
            while (
                prefix < len(wanted)
                and start + prefix < len(haystack)
                and haystack[start + prefix] == wanted[prefix]
            ):
                prefix += 1
            if prefix > best_prefix:
                best_prefix = prefix
                best = (source, start)
    named = ", ".join(source.source_id for source in sources)
    if best is None:
        return (
            f"{manuscript}: code block {index} does not appear in any pinned source "
            f"extraction ({named}); its first line is {wanted[0]!r}. Code in the "
            "magazine is copied and run by readers, so every fenced block must be "
            "the source's own lines, character for character."
        )
    source, start = best
    haystack = _body_lines(source.body)
    found = (
        haystack[start + best_prefix]
        if start + best_prefix < len(haystack)
        else "<end of extraction>"
    )
    expected = (
        wanted[best_prefix] if best_prefix < len(wanted) else "<end of code block>"
    )
    return (
        f"{manuscript}: code block {index} diverges from {source.path} at line "
        f"{best_prefix + 1}; the extraction has {found!r} where the manuscript has "
        f"{expected!r}. Code line breaks and indentation are substantive and must "
        "match the source exactly."
    )
