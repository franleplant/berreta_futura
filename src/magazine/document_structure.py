
from __future__ import annotations

from .publication_document import (
    Block,
    BlockQuote,
    Emphasis,
    FencedCode,
    Heading,
    HorizontalRule,
    Inline,
    InlineCode,
    LineBreak,
    Link,
    ListBlock,
    ListItem,
    Paragraph,
    Strong,
    Text,
)


def visible_blocks(blocks: tuple[Block, ...]) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []
    _flatten(blocks, flattened, container=None)
    return flattened


def _flatten(
    blocks: tuple[Block, ...],
    into: list[tuple[str, str]],
    *,
    container: str | None,
) -> None:
    for block in blocks:
        if isinstance(block, Heading):
            into.append((f"h{block.level}", _inline_visible(block.children)))
        elif isinstance(block, Paragraph):
            into.append((container or "p", _inline_visible(block.children)))
        elif isinstance(block, FencedCode):
            into.append(("code", block.code))
        elif isinstance(block, BlockQuote):
            _flatten(block.children, into, container="quote")
        elif isinstance(block, ListBlock):
            item_kind = "ordered" if block.ordered else "bullet"
            for item in block.items:
                _flatten(item.children, into, container=item_kind)
        elif isinstance(block, HorizontalRule):
            continue
        else:
            raise TypeError(f"Unsupported publication block: {type(block).__name__}")


def _inline_visible(inlines: tuple[Inline, ...]) -> str:
    parts: list[str] = []
    for inline in inlines:
        if isinstance(inline, (Text, InlineCode)):
            parts.append(inline.value)
        elif isinstance(inline, (Emphasis, Strong, Link)):
            parts.append(_inline_visible(inline.children))
        elif isinstance(inline, LineBreak):
            parts.append(" ")
        else:
            raise TypeError(f"Unsupported publication inline: {type(inline).__name__}")
    return " ".join("".join(parts).split())


def block_signature(blocks: tuple[Block, ...]) -> list[str]:
    return [_descriptor(block) for block in blocks]


def _descriptor(block: Block) -> str:
    if isinstance(block, Heading):
        return f"h{block.level}"
    if isinstance(block, Paragraph):
        return "body"
    if isinstance(block, FencedCode):
        return "code"
    if isinstance(block, HorizontalRule):
        return "rule"
    if isinstance(block, BlockQuote):
        return "quote[" + ",".join(_descriptor(child) for child in block.children) + "]"
    if isinstance(block, ListBlock):
        name = "ol" if block.ordered else "ul"
        start = f"@{block.start}" if block.ordered and block.start != 1 else ""
        items = ";".join(_item_descriptor(item) for item in block.items)
        return f"{name}{start}[{items}]"
    raise TypeError(f"Unsupported publication block: {type(block).__name__}")


def _item_descriptor(item: ListItem) -> str:
    return ",".join(_descriptor(child) for child in item.children)
