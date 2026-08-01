"""Block structure and reader-visible text, derived from the CommonMark parse.

The validation gates used to scan manuscripts with hand-rolled line parsers
that knew a smaller Markdown than the renderer's: an ordered list folded
silently into a paragraph while the reader printed an ``<ol>``, so a gate and
the printed page could disagree about the same file.  Both gates now read the
same :mod:`magazine.publication_document` tree the renderer typesets, through
the two views here:

:func:`visible_blocks`
    flattens a document into ``(kind, text)`` pairs in reading order -- the
    content view, where what matters is every reader-visible word and which
    blocks are code.  List markers and thematic breaks are structure,
    not words: the reader draws them as furniture, so they contribute no text.

:func:`block_signature`
    serializes each top-level block into one structural descriptor -- the
    translation gate's view, where what matters is that two manuscripts carry
    the same shapes in the same order, including list nesting, ordered-list
    start numbers, and thematic breaks.

Neither view invents a third parser: both walk the blocks that
:func:`magazine.publication_document.parse_publication_document` produced, so
a construct the renderer learns is one the gates see the same way.
"""

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
    """Flatten a document into ``(kind, text)`` pairs in reading order.

    Kinds are ``h1``..``h6``, ``p``, ``quote`` (a paragraph inside a block
    quote), ``bullet`` / ``ordered`` (a paragraph inside a list item of that
    list kind), and ``code``.  ``code`` text is the fence's raw content;
    every other text is whitespace-normalized prose with inline markup
    resolved the way the renderer resolves it (emphasis unwrapped, a link's
    words kept and its destination dropped).  A thematic break contributes
    nothing visible and is omitted.
    """
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
    """One structural descriptor per top-level block, in reading order.

    A descriptor spells the whole shape of its block: ``body``, ``h2``,
    ``code``, ``rule``, ``quote[body,body]``, ``ul[body;body]``,
    ``ol@3[body;body,ul[body]]`` -- items joined with ``;``, an item's own
    blocks with ``,``, and an ordered list's start number carried whenever it
    is not 1.  Two manuscripts with equal signatures render the same block
    structure; a translation that flattens an ordered list into prose, drops
    a thematic break, or regroups a nested list therefore no longer matches.
    """
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
