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


_OPENING_CONTEXT = frozenset("([{\u2018\u201c\u00ab\u00a1\u00bf-\u2010\u2013\u2014/")


def educate_reader_quotes(text: str) -> str:

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
            characters[index] = _APOSTROPHE
    return "".join(characters)


@lru_cache(maxsize=1)
def _settable_codepoints() -> frozenset[int]:
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

    for character, replacement in _FOLDED_CHARACTERS.items():
        text = text.replace(character, replacement)
    if text.isascii():
        return text
    settable = _settable_codepoints()
    return "".join(
        character
        if character.isspace() or ord(character) < 0x20 or ord(character) in settable
        else _REPLACEMENT
        for character in text
    )
