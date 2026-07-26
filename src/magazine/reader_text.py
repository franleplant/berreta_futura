"""The publication's reader character rules: folding and quote education.

A printed reader can only set what its own faces carry.  This module holds that
rule -- a character the bundled faces cannot set is folded into a sequence
they can, or -- failing that -- replaced with a visible ``?`` rather than left
as a silent hole for a host font to fill -- and its converse for quotation
marks: an authored typewriter quote is educated into the real mark the faces
do carry (:func:`educate_reader_quotes`), so straight and curly marks cannot
mix on one printed page.

The rule is a property of the publication, not of one typesetter, so it lives
here on its own and deliberately contains no markup or markdown knowledge: it
is applied to individual text and attribute values, never to assembled markup.

**The repertoire is the faces', not cp1252's.**  It used to be cp1252, and the
fold list used to include the curly quotation marks, the ellipsis and the
arrow.  None of that was typography: ``render.py`` writes through ReportLab's
cp1252 encoder, and the reader path folded the same characters only so the two
producers stayed byte-comparable.  That comparison is over (see
``docs/RENDERER_MIGRATION.md``), and the fold was the last thing degrading real
quotation marks into ASCII ones -- the most conspicuous crudity left in the
English edition once the type started kerning.  Measured against every bundled
face: all eight carry U+2018/2019/201C/201D, U+2026, U+2192, U+00A0, the
dashes, and the Spanish guillemets, so none of them needs folding at all.
``render._plain`` keeps its own cp1252 copy, deliberately: the ReportLab engine
must stay byte-identical, and it is a different engine's business.

What is still folded, and why:

``U+00A0``
    to an ordinary space.  Not an encoding fold -- cp1252 carries it and so do
    the faces.  A non-breaking space is the reader's own line-breaking control
    character: ``weasyprint_adapter`` writes one between the last two words of a
    paragraph to suppress a runt, and a manuscript must not be able to place
    one the typesetter did not choose.

Anything the faces cannot set
    becomes ``?``.  ``U+25E6`` WHITE BULLET is the standing example: Inter
    carries it, Source Serif 4 does not, and prose is Source Serif -- so before
    this rule a nested list marker would have reached the page silently set in
    whatever font the host preferred.  ``U+00AD`` SOFT HYPHEN is the same case
    the other way round, and is refused for the same reason: it is settable in
    the serif and not in the sans, and no value here knows which face it is
    bound for.  A ``?`` on a proof is an editor's problem; a Times glyph in the
    middle of Source Serif is a printed one.  Whitespace and control characters
    are exempt -- a newline is layout, not a glyph, and no face carries one.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path

from .errors import ValidationError


_FOLDED_CHARACTERS = {
    "\u00a0": " ",
}

_REPLACEMENT = "?"

_APOSTROPHE = "\u2019"
_OPEN_SINGLE = "\u2018"
_OPEN_DOUBLE = "\u201c"
_CLOSE_DOUBLE = "\u201d"

# What may stand before an *opening* mark: nothing, whitespace, an opening
# bracket, a dash, or another opening quotation mark (nested quotes).
_OPENING_CONTEXT = frozenset("([{\u2018\u201c\u00ab\u00a1\u00bf-\u2010\u2013\u2014/")


def educate_reader_quotes(text: str) -> str:
    """Set authored typewriter quotation marks as the real marks they stand for.

    The publication's faces carry U+2018/2019/201C/201D and most manuscripts
    author them directly; where one authors the ASCII stand-in instead, the two
    kinds would otherwise mix on a single printed page -- edition 002 shipped
    seven straight apostrophes beside curly ones, two of them flagged by an
    independent review.  Which mark prints is typesetting, not authorship, so
    the straight characters are educated here rather than edited in the
    manuscripts.

    The rules are positional and deliberately small.  A ``'`` after a letter or
    digit is an apostrophe or a closing quote (``run's``, ``agents'``) and both
    are U+2019; after an opening context and before a letter it opens, except
    before a digit, where it is an elision (``'90s``).  A ``"`` after an
    opening context opens; anything else closes.  This is applied to *prose*
    values only -- code spans, fenced code, and URLs are quoted verbatim by the
    caller, because a straight quote inside them is content, not typography.
    """

    if "'" not in text and '"' not in text:
        return text
    characters = list(text)
    for index, character in enumerate(characters):
        if character not in {"'", '"'}:
            continue
        previous = characters[index - 1] if index else ""
        following = characters[index + 1] if index + 1 < len(characters) else ""
        opens = not previous or previous.isspace() or previous in _OPENING_CONTEXT
        if character == '"':
            characters[index] = _OPEN_DOUBLE if opens else _CLOSE_DOUBLE
        elif previous.isalnum():
            characters[index] = _APOSTROPHE
        elif opens and following.isalpha():
            characters[index] = _OPEN_SINGLE
        else:
            # An elision ('90s), a mark after closing punctuation, or a lone
            # quote: all read as the raised-comma form.
            characters[index] = _APOSTROPHE
    return "".join(characters)


@lru_cache(maxsize=1)
def _settable_codepoints() -> frozenset[int]:
    """Every codepoint *all* bundled faces can set.

    The intersection and not the union: a value folded here does not know which
    face will set it -- prose is Source Serif, chrome is Inter, and a caption is
    both -- so a character only one family carries is not one the publication
    can promise to set.  Measured on this edition, the intersection is 896
    codepoints and covers every character either language's manuscripts use.
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:  # pragma: no cover - fontTools ships with WeasyPrint
        raise ValidationError(
            "Folding the reader's characters requires fontTools, which WeasyPrint "
            f"itself depends on. Run `uv sync --locked`. Original error: {exc}"
        ) from exc
    folder = resources.files("magazine").joinpath("assets", "fonts")
    with resources.as_file(folder) as resolved:
        faces = sorted(Path(resolved).rglob("*.ttf"))
        if not faces:
            raise ValidationError(
                f"The publication ships no reader faces under {resolved}, so no "
                "character can be shown to be settable"
            )
        return frozenset.intersection(
            *(frozenset(TTFont(str(face)).getBestCmap()) for face in faces)
        )


def fold_reader_characters(text: str) -> str:
    """Fold one authored string into the reader's character repertoire."""

    for character, replacement in _FOLDED_CHARACTERS.items():
        text = text.replace(character, replacement)
    if text.isascii():
        # The common case by a wide margin, and every printable ASCII
        # character is in the intersection -- asserted by the test suite, so
        # the shortcut cannot quietly start passing an unsettable character.
        return text
    settable = _settable_codepoints()
    return "".join(
        character
        if character.isspace() or ord(character) < 0x20 or ord(character) in settable
        else _REPLACEMENT
        for character in text
    )
