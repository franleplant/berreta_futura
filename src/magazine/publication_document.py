from __future__ import annotations

from collections.abc import Mapping as MappingABC
from collections.abc import MutableMapping, MutableSequence, MutableSet
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token


_MARKDOWN = MarkdownIt("commonmark")


_MARKDOWN.normalizeLink = lambda url: url


class DocumentParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Text:
    value: str


@dataclass(frozen=True, slots=True)
class Emphasis:
    children: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Strong:
    children: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class InlineCode:
    value: str


@dataclass(frozen=True, slots=True)
class Link:
    destination: str
    children: tuple[Inline, ...]
    title: str | None = None


@dataclass(frozen=True, slots=True)
class LineBreak:
    hard: bool


Inline: TypeAlias = Text | Emphasis | Strong | InlineCode | Link | LineBreak


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    children: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Paragraph:
    children: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class FencedCode:
    code: str
    info: str


@dataclass(frozen=True, slots=True)
class BlockQuote:
    children: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class ListItem:
    children: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class ListBlock:
    ordered: bool
    items: tuple[ListItem, ...]
    start: int = 1


@dataclass(frozen=True, slots=True)
class HorizontalRule:
    pass


Block: TypeAlias = Heading | Paragraph | FencedCode | BlockQuote | ListBlock | HorizontalRule


@dataclass(frozen=True, slots=True)
class PublicationDocument:
    metadata: Mapping[str, object]
    blocks: tuple[Block, ...]


_GLYPH_FALLBACKS = str.maketrans(
    {
        "‑": "-",
        "−": "-",
        "­": "",
    }
)


def parse_publication_document(markdown: str) -> PublicationDocument:
    metadata, body = split_frontmatter(markdown)
    tokens = _MARKDOWN.parse(body.translate(_GLYPH_FALLBACKS))
    blocks, next_index = _parse_blocks(tokens)
    if next_index != len(tokens):
        raise DocumentParseError("Markdown parser left unconsumed block tokens")
    return PublicationDocument(metadata=metadata, blocks=blocks)


def split_frontmatter(markdown: str) -> tuple[Mapping[str, object], str]:

    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return MappingProxyType({}), markdown

    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") not in {"---", "..."}:
            continue
        header = "".join(lines[1:index])
        try:
            parsed = yaml.safe_load(header)
        except yaml.YAMLError as exc:
            raise DocumentParseError(f"Invalid YAML frontmatter: {exc}") from exc
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
            raise DocumentParseError("YAML frontmatter must be a mapping with string keys")
        return _freeze_mapping(parsed), "".join(lines[index + 1 :])

    return MappingProxyType({}), markdown


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({key: _freeze(value) for key, value in value.items()})


def _freeze(value: object) -> object:
    if isinstance(value, MappingABC):
        if not all(isinstance(key, str) for key in value):
            raise DocumentParseError("YAML frontmatter mappings must use string keys")
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, (MutableMapping, MutableSequence, MutableSet)):
        raise DocumentParseError(
            f"YAML frontmatter contains an unsupported mutable value: {type(value).__name__}"
        )
    return value


def _parse_blocks(
    tokens: list[Token], index: int = 0, *, until: str | None = None
) -> tuple[tuple[Block, ...], int]:
    blocks: list[Block] = []
    while index < len(tokens):
        token = tokens[index]
        if token.type == until:
            return tuple(blocks), index + 1
        if token.type == "heading_open":
            inline = _expect(tokens, index + 1, "inline")
            blocks.append(
                Heading(level=int(token.tag[1:]), children=_parse_inlines(inline.children))
            )
            index = _expect_close(tokens, index + 2, "heading_close")
        elif token.type == "paragraph_open":
            inline = _expect(tokens, index + 1, "inline")
            blocks.append(Paragraph(children=_parse_inlines(inline.children)))
            index = _expect_close(tokens, index + 2, "paragraph_close")
        elif token.type == "blockquote_open":
            children, index = _parse_blocks(tokens, index + 1, until="blockquote_close")
            blocks.append(BlockQuote(children=children))
        elif token.type in {"bullet_list_open", "ordered_list_open"}:
            list_block, index = _parse_list(tokens, index)
            blocks.append(list_block)
        elif token.type == "fence":
            blocks.append(FencedCode(code=token.content, info=token.info))
            index += 1
        elif token.type == "code_block":
            blocks.append(FencedCode(code=token.content, info=""))
            index += 1
        elif token.type == "hr":
            blocks.append(HorizontalRule())
            index += 1
        else:
            raise DocumentParseError(f"Unsupported Markdown block token: {token.type}")
    if until is not None:
        raise DocumentParseError(f"Unclosed Markdown block: expected {until}")
    return tuple(blocks), index


def _parse_list(tokens: list[Token], index: int) -> tuple[ListBlock, int]:
    opening = tokens[index]
    ordered = opening.type == "ordered_list_open"
    closing = "ordered_list_close" if ordered else "bullet_list_close"
    index += 1
    items: list[ListItem] = []
    start = 1
    while index < len(tokens) and tokens[index].type != closing:
        item = _expect(tokens, index, "list_item_open")
        if ordered and not items:
            try:
                start = int(item.info or item.content)
            except ValueError as exc:
                raise DocumentParseError("Ordered list start is not an integer") from exc
        children, index = _parse_blocks(tokens, index + 1, until="list_item_close")
        items.append(ListItem(children=children))
    if index == len(tokens):
        raise DocumentParseError(f"Unclosed Markdown list: expected {closing}")
    return ListBlock(ordered=ordered, items=tuple(items), start=start), index + 1


def _parse_inlines(tokens: list[Token] | None) -> tuple[Inline, ...]:
    if tokens is None:
        return ()
    inlines, index = _parse_inline_sequence(tokens)
    if index != len(tokens):
        raise DocumentParseError("Markdown parser left unconsumed inline tokens")
    return inlines


def _parse_inline_sequence(
    tokens: list[Token], index: int = 0, *, until: str | None = None
) -> tuple[tuple[Inline, ...], int]:
    inlines: list[Inline] = []
    while index < len(tokens):
        token = tokens[index]
        if token.type == until:
            return tuple(inlines), index + 1
        if token.type == "text":
            inlines.append(Text(token.content))
            index += 1
        elif token.type == "code_inline":
            inlines.append(InlineCode(token.content))
            index += 1
        elif token.type in {"softbreak", "hardbreak"}:
            inlines.append(LineBreak(hard=token.type == "hardbreak"))
            index += 1
        elif token.type in {"em_open", "strong_open"}:
            closing = "em_close" if token.type == "em_open" else "strong_close"
            children, index = _parse_inline_sequence(tokens, index + 1, until=closing)
            inlines.append(Emphasis(children) if token.type == "em_open" else Strong(children))
        elif token.type == "link_open":
            children, index = _parse_inline_sequence(tokens, index + 1, until="link_close")
            destination = token.attrGet("href")
            if destination is None:
                raise DocumentParseError("Markdown link has no destination")
            inlines.append(
                Link(destination=destination, children=children, title=token.attrGet("title"))
            )
        else:
            raise DocumentParseError(f"Unsupported Markdown inline token: {token.type}")
    if until is not None:
        raise DocumentParseError(f"Unclosed Markdown inline span: expected {until}")
    return tuple(inlines), index


def _expect(tokens: list[Token], index: int, expected: str) -> Token:
    if index >= len(tokens) or tokens[index].type != expected:
        actual = "end of input" if index >= len(tokens) else tokens[index].type
        raise DocumentParseError(f"Expected {expected}, found {actual}")
    return tokens[index]


def _expect_close(tokens: list[Token], index: int, expected: str) -> int:
    _expect(tokens, index, expected)
    return index + 1
