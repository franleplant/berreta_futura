"""Renderer-neutral semantic HTML for a validated magazine edition.

The public seam is :func:`render_html_edition`: callers supply an already
validated :class:`~magazine.manifest.Edition` and receive deterministic HTML
plus an inventory of the local assets referenced by it.  The module deliberately
does not know about page size, CSS, PDFs, or a particular HTML renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from .manifest import Article, Edition, Section
from .media_schema import Figure
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
    PublicationDocument,
    Strong,
    Text,
    parse_publication_document,
)
from .reader_text import educate_reader_quotes, fold_reader_characters


@dataclass(frozen=True, slots=True)
class HtmlAsset:
    """A local file referenced by the semantic edition HTML.

    ``path`` stays a :class:`Path` so future adapters do not need to recover a
    filesystem path from HTML. ``src`` is the corresponding local ``file:`` URL
    used in the generated document; neither field ever causes network access.
    """

    id: str
    role: str
    path: Path
    src: str
    alt_text: str
    article_id: str | None = None
    figure_id: str | None = None
    source_id: str | None = None
    caption: str | None = None
    credit: str | None = None
    anchor: str | None = None
    layout: str | None = None
    rights_status: str | None = None
    bundle_sha256: str | None = None
    artifact_sha256: str | None = None
    criteria: tuple[str, ...] = ()
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class HtmlEdition:
    """The complete semantic HTML edition and its explicit local asset inventory."""

    html: str
    assets: tuple[HtmlAsset, ...]


def render_html_edition(edition: Edition) -> HtmlEdition:
    """Render a validated edition into semantic, self-contained HTML.

    The output contains no stylesheet, script, remotely fetched asset, or layout
    policy. Authored links remain working links, including external destinations.
    Its stable ``data-*`` attributes are the provenance hooks for screen and
    print adapters. Repeated calls with the same validated edition produce the
    same string and asset ordering.

    Every text and attribute value is folded through
    :func:`magazine.reader_text.fold_reader_characters` — the publication's own
    character repertoire, not any renderer's — and then escaped, in that order,
    so that whatever the fold produces is still escaped. Prose text is
    additionally educated first through
    :func:`magazine.reader_text.educate_reader_quotes`, so an authored
    typewriter quote prints as the real mark; code spans, fenced code, URLs,
    and attribute values are exempt — a straight quote there is content, and
    the escape is what keeps it from terminating an attribute value.
    """

    assets: list[HtmlAsset] = []
    body: list[str] = [_edition_header(edition), _render_contents(edition)]

    if edition.editorial is not None:
        document = _read_document(edition.editorial.path)
        body.append(
            _render_editorial(
                edition,
                document,
                title=edition.editorial.title,
                label=edition.editorial.label,
                byline=edition.editorial.byline,
            )
        )

    for index, article in enumerate(edition.articles, start=1):
        document = _read_document(article.manuscript)
        article_html, article_assets = _render_article(edition, article, document, index)
        body.append(article_html)
        assets.extend(article_assets)

    for index, section in enumerate(edition.sections):
        body.append(_render_section(edition, index, section, _read_document(section.path)))

    body.extend(_render_closing_plates(edition, assets))
    _add_cover_asset(edition, assets)

    title = f"{edition.publication_name} — {edition.title}"
    html = "\n".join(
        [
            "<!doctype html>",
            f'<html lang="{_attr(edition.locale)}" data-edition-id="{_attr(edition.id)}">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{_text(title)}</title>",
            "</head>",
            "<body>",
            '  <main data-edition-id="' + _attr(edition.id) + '">',
            *_indent(body, 4),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )
    return HtmlEdition(html=html, assets=tuple(assets))


def _edition_header(edition: Edition) -> str:
    subtitle = str(edition.raw.get("subtitle") or "").strip()
    lines = [
        '<header class="edition-header" data-edition-header="true">',
        f'  <p class="publication-name">{_text(edition.publication_name)}</p>',
        f'  <p class="issue-number" data-issue-number="{_attr(edition.issue_number)}">{_text(_ui(edition, "issue"))} {_text(edition.issue_number)}</p>',
        f'  <h1>{_text(edition.title)}</h1>',
    ]
    if subtitle:
        lines.append(f'  <p class="subtitle">{_text(subtitle)}</p>')
    lines.extend(
        [
            f'  <time datetime="{_attr(edition.publication_date)}">{_text(edition.publication_date)}</time>',
            "</header>",
        ]
    )
    return "\n".join(lines)


def _render_contents(edition: Edition) -> str:
    """The contents list, with each entry's own label, title and author.

    An entry is a row of four editorial facts -- what kind of piece it is, where
    it starts, what it is called and who wrote it -- so each is its own element.
    The folio is a second link to the same destination rather than a decoration
    on the first: ``target-counter`` resolves against the element's own ``href``,
    and an entry that cannot be followed to its page is not a contents entry.
    """

    label = _ui(edition, "contents")
    kicker = f"{_ui(edition, 'issue')} {edition.issue_number} / {label}"
    entries: list[tuple[str, str, str, str]] = []
    if edition.editorial is not None:
        entries.append(
            (
                "editorial",
                _ui(edition, "editorial"),
                edition.editorial.title,
                edition.editorial.byline,
            )
        )
    entries.extend(
        (
            _article_destination_id(article),
            f"{_ui(edition, 'feature')} {index:02d}",
            article.title,
            article.author,
        )
        for index, article in enumerate(edition.articles, start=1)
    )
    entries.extend(
        (_section_destination_id(index), _ui(edition, section.kind), section.title, "")
        for index, section in enumerate(edition.sections)
    )
    rows: list[str] = []
    for destination, entry_label, title, author in entries:
        rows.append(
            f'    <li><span class="entry-label">{_text(entry_label)}</span>'
            f'<a class="entry-folio" href="#{_attr(destination)}" aria-hidden="true"></a>'
            f'<a class="entry-title" href="#{_attr(destination)}">{_text(title)}</a>'
            + (f'<span class="entry-author">{_text(author)}</span>' if author else "")
            + "</li>"
        )
    return "\n".join(
        [
            f'<nav aria-label="{_attr(label)}" data-edition-navigation="contents">',
            f'  <p class="contents-kicker">{_text(kicker)}</p>',
            f"  <h2>{_text(label)}</h2>",
            "  <ol>",
            *rows,
            "  </ol>",
            "</nav>",
        ]
    )


def _render_editorial(
    edition: Edition, document: PublicationDocument, *, title: str, label: str, byline: str
) -> str:
    return "\n".join(
        [
            '<section id="editorial" class="editorial" data-section-kind="original_editorial"'
            f' data-short-title="{_attr(_ui(edition, "editorial"))}">',
            "  <header>",
            f'    <p class="content-label" data-content-mode="original_editorial">'
            f'<span class="label-primary">{_text(label)}</span>'
            f'<span class="label-secondary">{_text(_ui(edition, "original_argument"))}</span></p>',
            f"    <h1>{_text(title)}</h1>",
            f'    <p class="byline" data-byline="true">'
            f'<span class="byline-prefix">{_text(_ui(edition, "by"))}</span> {_text(byline)}</p>',
            "  </header>",
            *_indent(_render_blocks(document.blocks, standfirst=True), 2),
            "</section>",
        ]
    )


def _render_article(
    edition: Edition, article: Article, document: PublicationDocument, article_index: int = 1
) -> tuple[str, tuple[HtmlAsset, ...]]:
    figures_by_anchor: dict[str, list[Figure]] = {}
    opener_figures: list[Figure] = []
    for figure in article.figures:
        if figure.anchor == "__opener__":
            opener_figures.append(figure)
        else:
            figures_by_anchor.setdefault(_anchor_key(figure.anchor), []).append(figure)

    assets: list[HtmlAsset] = []
    lines = [
        f'<article id="{_attr(_article_destination_id(article))}" data-article-id="{_attr(article.id)}" '
        f'data-content-mode="{_attr(article.content_mode)}" data-source-ids="{_attr(" ".join(article.source_ids))}" '
        f'data-figure-layouts="{_attr(_figure_layouts(article))}" '
        f'data-short-title="{_attr(article.short_title)}">',
        "  <header>",
        f'    <p class="content-label" data-content-mode="{_attr(article.content_mode)}">'
        f'<span class="label-primary">{_text(_ui(edition, "feature"))} {article_index:02d}</span>'
        f'<span class="label-secondary">{_text(_content_label(edition, document, article.content_mode))}</span></p>',
        f"    <h1>{_text(article.title)}</h1>",
        f'    <p class="byline" data-byline="true">'
        f'<span class="byline-prefix">{_text(_ui(edition, "by"))}</span> {_text(article.author)}</p>',
        f'    <p class="author-note">{_text(article.author_note)}</p>',
        '    <p class="provenance" data-provenance="source-ids">' + _text(_ui(edition, "sources")) + ': '
        + ", ".join(
            f'<span data-source-id="{_attr(source_id)}">{_text(source_id)}</span>'
            for source_id in article.source_ids
        )
        + "</p>",
        "  </header>",
    ]
    for figure in opener_figures:
        figure_html, asset = _render_figure(edition, article.id, figure)
        lines.extend(_indent((figure_html,), 2))
        assets.append(asset)

    references = False
    for index, block in enumerate(document.blocks):
        if isinstance(block, Heading):
            references = _is_reference_heading(_inline_text(block.children))
        lines.extend(
            _indent((_render_block(block, standfirst=index == 0, references=references),), 2)
        )
        if isinstance(block, Heading):
            for figure in figures_by_anchor.get(_anchor_key(_inline_text(block.children)), ()):
                figure_html, asset = _render_figure(edition, article.id, figure)
                lines.extend(_indent((figure_html,), 2))
                assets.append(asset)

    lines.extend(
        _indent(
            (
                f'<p class="end-mark" data-end-mark="true">'
                f"{_text(_ui(edition, 'end'))} / {article_index:02d}</p>",
            ),
            2,
        )
    )
    if article.tail_art is not None:
        asset = _asset(
            id=f"article-tail-{article.id}", role="article_tail", path=article.tail_art,
            alt_text=f"Tail art for {article.title}", article_id=article.id,
            rights_status="author_owned",
        )
        assets.append(asset)
        lines.extend(
            _indent(
                (
                    f'<figure class="article-tail" data-asset-role="article_tail">'
                    f'<img src="{_attr(asset.src)}" alt="{_attr(asset.alt_text)}"></figure>',
                ),
                2,
            )
        )
    lines.extend(_indent(_render_source_link(article), 2))
    lines.append("</article>")
    return "\n".join(lines), tuple(assets)


def _render_source_link(article: Article) -> tuple[str, ...]:
    """The article's own way back to the source it was built from, as a link.

    This is a semantic hook and not print policy, and the distinction is worth
    stating because the thing it exists for is a printed QR code.  What the
    edition *knows* is that this article was built from a source that lives at a
    particular address, and that a reader who wants the original should be sent
    there -- an editorial fact of the same kind as the source ids already
    printed at the opener, and expressible in HTML as what it is: an anchor with
    a working ``href``.  A screen adapter follows it.  The print adapter, which
    cannot, renders it as a QR code set into the opener's title furniture, and
    everything that decision needs -- where the credit line landed, how wide a
    module has to be to survive an inkjet, which error-correction level leaves
    the widest cell, how far the byline is inset beside it -- stays where page
    geometry is known.  None of it is visible here.

    One link, not one per source: ``source_ids`` is authored and ordered, the
    first is the primary source, and the article already prints the full list at
    its opener.  An article whose first source carries no ``canonical_url``
    emits nothing at all rather than a broken destination.

    NOT ONE WORD OF LANGUAGE EITHER, which it used to carry.  A
    ``data-source-label`` held a localized ``Source / nn`` here, on the argument
    that a printed square needs a name beside it or it reads as a sticker; the
    printed square is now made furniture by where it stands on the opener's grid
    instead, the label is retired, and this element is back to being exactly what
    it says -- a destination, in one language, which is the URL's.
    """
    if not article.source_url:
        return ()
    return (
        f'<a class="source-link" data-source-link="primary" '
        f'data-source-id="{_attr(article.source_ids[0] if article.source_ids else "")}" '
        f'href="{_attr(article.source_url)}">{_verbatim(article.source_url)}</a>',
    )


def _render_section(edition: Edition, index: int, section: Section, document: PublicationDocument) -> str:
    return "\n".join(
        [
            f'<section id="{_attr(_section_destination_id(index))}" data-section-kind="{_attr(section.kind)}"'
            f' data-short-title="{_attr(section.title)}">',
            "  <header>",
            f'    <p class="content-label" data-content-mode="{_attr(section.kind)}">'
            f'<span class="label-primary">{_text(_ui(edition, section.kind))}</span></p>',
            f"    <h1>{_text(section.title)}</h1>",
            "  </header>",
            *_indent(_render_blocks(document.blocks, standfirst=True), 2),
            "</section>",
        ]
    )


def _render_closing_plates(edition: Edition, assets: list[HtmlAsset]) -> tuple[str, ...]:
    plates: list[str] = []
    for index, plate in enumerate(edition.closing_plates, start=1):
        asset = _asset(
            id=f"closing-plate-{index}", role="closing_plate", path=plate.art_path,
            alt_text=plate.title, rights_status="author_owned",
        )
        assets.append(asset)
        plates.append(
            '<figure class="closing-plate" data-asset-role="closing_plate" '
            f'data-closing-plate="{index}"><img src="{_attr(asset.src)}" '
            f'alt="{_attr(plate.title)}"><figcaption>{_text(plate.title)}</figcaption></figure>'
        )
    return tuple(plates)


def _add_cover_asset(edition: Edition, assets: list[HtmlAsset]) -> None:
    if edition.cover_art is not None:
        assets.append(
            _asset(
                id="cover-art", role="cover_art", path=edition.cover_art,
                alt_text=str(edition.cover.get("headline") or edition.title),
            )
        )


def _render_figure(edition: Edition, article_id: str, figure: Figure) -> tuple[str, HtmlAsset]:
    asset = _asset(
        id=f"figure-{article_id}-{figure.id}", role="figure", path=figure.path,
        alt_text=figure.alt_text, article_id=article_id, figure_id=figure.id,
        source_id=figure.source_id, caption=figure.caption, credit=figure.credit,
        anchor=figure.anchor, layout=figure.layout, rights_status=figure.rights_status,
        bundle_sha256=figure.bundle_sha256, artifact_sha256=figure.artifact_sha256,
        criteria=figure.criteria, rationale=figure.rationale,
    )
    return (
        '<figure data-figure-id="{id}" data-article-id="{article}" data-source-id="{source}" '
        'data-anchor="{anchor}" data-layout="{layout}" data-rights-status="{rights}" '
        'data-figure-label="{word}">'
        '<img src="{src}" alt="{alt}"><figcaption><span class="caption">{caption}</span>'
        '<span class="credit">{credit}</span></figcaption></figure>'.format(
            id=_attr(figure.id), article=_attr(article_id), source=_attr(figure.source_id),
            anchor=_attr(figure.anchor), layout=_attr(figure.layout),
            rights=_attr(figure.rights_status), src=_attr(asset.src), alt=_attr(figure.alt_text),
            caption=_text(figure.caption), credit=_text(figure.credit),
            word=_attr(_ui(edition, "figure")),
        ),
        asset,
    )


def _render_blocks(blocks: tuple[Block, ...], *, standfirst: bool = False) -> tuple[str, ...]:
    return tuple(
        _render_block(block, standfirst=standfirst and index == 0)
        for index, block in enumerate(blocks)
    )


def _render_block(block: Block, *, standfirst: bool = False, references: bool = False) -> str:
    """Render one block.

    ``standfirst`` marks the opening prose block of an article, editorial or
    section: the standfirst is an editorial role, so it belongs to the semantic
    document rather than to any one adapter's stylesheet.  ``references`` marks
    a list that stands under a references heading, which is a bibliography and
    not a list of points -- the same editorial distinction.
    """

    if isinstance(block, Heading):
        return f"<h{block.level}>{_render_inlines(block.children)}</h{block.level}>"
    if isinstance(block, Paragraph):
        opening = '<p class="standfirst">' if standfirst else "<p>"
        return f"{opening}{_render_inlines(block.children)}</p>"
    if isinstance(block, FencedCode):
        language = block.info.split(maxsplit=1)[0] if block.info else ""
        class_attr = f' class="language-{_attr(language)}"' if language else ""
        return f"<pre><code{class_attr}>{_verbatim(block.code)}</code></pre>"
    if isinstance(block, BlockQuote):
        return "<blockquote>" + "".join(_render_block(child) for child in block.children) + "</blockquote>"
    if isinstance(block, ListBlock):
        tag = "ol" if block.ordered else "ul"
        start = f' start="{block.start}"' if block.ordered and block.start != 1 else ""
        role = ' data-reference-list="true"' if references else ""
        return f"<{tag}{start}{role}>" + "".join(_render_list_item(item) for item in block.items) + f"</{tag}>"
    if isinstance(block, HorizontalRule):
        return "<hr>"
    raise TypeError(f"Unsupported publication block: {type(block).__name__}")


def _render_list_item(item: ListItem) -> str:
    return "<li>" + "".join(_render_block(child) for child in item.children) + "</li>"


def _render_inlines(inlines: tuple[Inline, ...]) -> str:
    rendered: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            rendered.append(_text(inline.value))
        elif isinstance(inline, Emphasis):
            rendered.append(f"<em>{_render_inlines(inline.children)}</em>")
        elif isinstance(inline, Strong):
            rendered.append(f"<strong>{_render_inlines(inline.children)}</strong>")
        elif isinstance(inline, InlineCode):
            rendered.append(f"<code>{_verbatim(inline.value)}</code>")
        elif isinstance(inline, Link):
            title = f' title="{_attr(inline.title)}"' if inline.title is not None else ""
            rendered.append(
                f'<a href="{_attr(inline.destination)}"{title}>{_render_inlines(inline.children)}</a>'
            )
        elif isinstance(inline, LineBreak):
            rendered.append("<br>" if inline.hard else "\n")
        else:
            raise TypeError(f"Unsupported publication inline: {type(inline).__name__}")
    return "".join(rendered)


def _read_document(path: Path) -> PublicationDocument:
    return parse_publication_document(path.read_text(encoding="utf-8"))


def _asset(*, id: str, role: str, path: Path, alt_text: str, **kwargs: object) -> HtmlAsset:
    return HtmlAsset(id=id, role=role, path=path, src=path.as_uri(), alt_text=alt_text, **kwargs)


def _content_label(edition: Edition, document: PublicationDocument, content_mode: str) -> str:
    value = document.metadata.get("label")
    return str(value).strip() if value is not None and str(value).strip() else _ui(edition, content_mode)


def _inline_text(inlines: tuple[Inline, ...]) -> str:
    result: list[str] = []
    for inline in inlines:
        if isinstance(inline, (Text, InlineCode)):
            result.append(inline.value)
        elif isinstance(inline, (Emphasis, Strong, Link)):
            result.append(_inline_text(inline.children))
        elif isinstance(inline, LineBreak):
            result.append("\n")
        else:
            raise TypeError(f"Unsupported publication inline: {type(inline).__name__}")
    return "".join(result)


def _figure_layouts(article: Article) -> str:
    """The distinct curated figure layouts an article declares, in first-use order.

    Editorially a layout belongs to the article as much as to the single figure
    that carries it, but no selector can ask "does this article declare a
    landscape plate?" of the article element alone. The attribute denormalises
    the article's own authored figure metadata so that question is answerable;
    it states nothing about what any adapter should then do with the answer.
    """

    layouts: list[str] = []
    for figure in getattr(article, "figures", ()):
        layout = str(getattr(figure, "layout", "") or "").strip()
        if layout and layout not in layouts:
            layouts.append(layout)
    return " ".join(layouts)


def _article_destination_id(article: Article) -> str:
    return f"article-{article.id}"


def _section_destination_id(index: int) -> str:
    return f"section-{index}"


def _anchor_key(value: str) -> str:
    return value.strip().casefold()


# The publication's own vocabulary for the heading that opens a bibliography.
# It is a closed set rather than a heuristic: a list is demoted to source notes
# only under a heading the publication recognizes as a references heading.
_REFERENCE_HEADINGS = frozenset({"references", "referencias"})


def _is_reference_heading(text: str) -> bool:
    return text.strip().casefold() in _REFERENCE_HEADINGS


def _ui(edition: Edition, key: str) -> str:
    """Small localized chrome vocabulary; authored manuscript labels win."""

    english = {
        "issue": "Issue",
        "contents": "Contents",
        "sources": "Sources",
        "editorial": "Editorial",
        "feature": "Feature",
        "figure": "Figure",
        "end": "End",
        "by": "By",
        "original_argument": "An original argument",
        "faithful_edit": "FAITHFUL EDIT",
        "faithful_synthesis": "FAITHFUL SYNTHESIS",
        "selected_extracts": "SELECTED EXTRACTS",
        "original_synthesis": "ORIGINAL SYNTHESIS",
        "original_editorial": "ORIGINAL EDITORIAL",
        "source_introduction": "THE SOURCE",
        "source_record": "SOURCE RECORD",
        "production_note": "PRODUCTION NOTE",
    }
    spanish = {
        "issue": "Número",
        "contents": "Índice",
        "sources": "Fuentes",
        "editorial": "Editorial",
        "feature": "Artículo",
        "figure": "Figura",
        "end": "Fin",
        "by": "Por",
        "original_argument": "Un argumento original",
        "faithful_edit": "EDICIÓN FIEL",
        "faithful_synthesis": "SÍNTESIS FIEL",
        "selected_extracts": "EXTRACTOS SELECCIONADOS",
        "original_synthesis": "SÍNTESIS ORIGINAL",
        "original_editorial": "EDITORIAL ORIGINAL",
        "source_introduction": "LA FUENTE",
        "source_record": "REGISTRO DE FUENTE",
        "production_note": "NOTA DE PRODUCCIÓN",
    }
    values = spanish if edition.language == "es" else english
    return values.get(key, key.replace("_", " ").replace("-", " ").upper())


def _text(value: object) -> str:
    # Educate first, then fold, then escape: education is prose typography, so
    # it sees the authored characters; the fold keeps whatever education set
    # inside the faces' repertoire; the escape neutralises what remains.
    return escape(fold_reader_characters(educate_reader_quotes(str(value))), quote=False)


def _verbatim(value: object) -> str:
    """Prose escaping without quote education, for values that are not prose.

    Code spans, fenced code, and URLs carry straight quotes as *content*: a
    shell command's quoting or a query string must reach the page (and a screen
    reader's clipboard) exactly as authored.  They are still folded, because the
    faces' repertoire binds every printed character, prose or not.
    """
    return escape(fold_reader_characters(str(value)), quote=False)


def _attr(value: object) -> str:
    # Fold first, escape second: the fold may still emit a character the escape
    # has to neutralise, and only escaping can stop a quotation mark -- authored
    # straight, or produced by a fold -- from terminating the value.
    return escape(fold_reader_characters(str(value)), quote=True)


def _indent(lines: tuple[str, ...] | list[str], spaces: int) -> tuple[str, ...]:
    prefix = " " * spaces
    # Do not indent embedded newlines: in ``pre``/``code`` content those spaces
    # would become authored text and violate the adapter's lossless contract.
    return tuple(prefix + line for line in lines)
