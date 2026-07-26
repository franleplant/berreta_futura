"""The publication's reader character folding.

A printed reader restricts itself to a small, typographically safe repertoire:
curly quotation marks fold to their ASCII forms, an arrow and an ellipsis fold
to the sequences a reader can set in any bundled face, a non-breaking space
folds to an ordinary space, and anything still outside cp1252 becomes a visible
replacement rather than a silent hole.

The rule is a property of the publication, not of one typesetter, so it lives
here on its own and deliberately contains no markup or markdown knowledge: it
is applied to individual text and attribute values, never to assembled markup.
"""

from __future__ import annotations


_FOLDED_CHARACTERS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2192": "->",
    "\u2026": "...",
    "\u00a0": " ",
}


def fold_reader_characters(text: str) -> str:
    """Fold one authored string into the reader's character repertoire."""

    for character, replacement in _FOLDED_CHARACTERS.items():
        text = text.replace(character, replacement)
    return text.encode("cp1252", errors="replace").decode("cp1252")
