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

from .errors import ValidationError
from .manifest import Article, Edition, Section
from .media_schema import Extract, Figure
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
    body: list[str] = [_edition_header(edition), *_render_contents(edition)]

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
    article_opener_format = _article_opener_format(edition)
    opener_format_attribute = (
        ' data-article-opener-format="illustrated_paper_spots_v1"'
        if article_opener_format == "illustrated_paper_spots_v1"
        else ""
    )
    html = "\n".join(
        [
            "<!doctype html>",
            (
                f'<html lang="{_attr(edition.locale)}" '
                f'data-edition-id="{_attr(edition.id)}"{opener_format_attribute}>'
            ),
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


def _render_contents(edition: Edition) -> tuple[str, ...]:
    """The contents sheets, with each entry's own label, title and author.

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
    # A contents row's author line is one line by contract (the row offsets
    # are fixed), and the measure carries about 54 characters of 6.8pt
    # Magazine Sans.  A roster longer than that is cut at an author boundary
    # and closed with "et al." -- the full roster still prints on the
    # article's own opener.
    def clamp_roster(author: str) -> str:
        if len(author) <= 54:
            return author
        head = author[:47]
        cut = head.rfind(", ")
        return (head[:cut] if cut > 0 else head) + " et al."

    entries = [
        (destination, entry_label, title, clamp_roster(author))
        for destination, entry_label, title, author in entries
    ]
    # The author line sits 2.7pt under a ONE-line title (editor's ruling,
    # 2026-08-07: intra-entry space belongs between entries).  A title long
    # enough to wrap would print into it, so it is the editor's to shorten
    # -- loudly, not silently.  ~62 characters of 9.8pt Magazine Serif
    # Display is the 286pt measure's practical ceiling.
    for _destination, _label, title, _author in entries:
        if len(title) > 62:
            raise ValidationError(
                f"Contents title {title!r} ({len(title)} characters) would wrap "
                "onto the entry's author line; shorten the article title to "
                "62 characters or fewer."
            )
    # The row template's fixed offsets (entry-author at 40.5pt) are drawn for
    # the ~49pt row that eight entries leave.  Nine or more rows shrink below
    # that, so the nav declares itself dense and the stylesheet moves the
    # offsets up a few points -- same page, same anatomy, tighter rows.
    density = ' data-contents-density="tight"' if len(entries) > 8 else ""
    rows: list[str] = []
    for destination, entry_label, title, author in entries:
        rows.append(
            f'    <li><span class="entry-label">{_text(entry_label)}</span>'
            f'<a class="entry-folio" href="#{_attr(destination)}" aria-hidden="true"></a>'
            f'<a class="entry-title" href="#{_attr(destination)}">{_text(title)}</a>'
            + (f'<span class="entry-author">{_text(author)}</span>' if author else "")
            + "</li>"
        )
    return (
        "\n".join(
            [
                f'<nav aria-label="{_attr(label)}" data-edition-navigation="contents"{density}>',
                f'  <p class="contents-kicker">{_text(kicker)}</p>',
                f"  <h2>{_text(label)}</h2>",
                "  <ol>",
                *rows,
                "  </ol>",
                "</nav>",
            ]
        ),
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
            f'<span class="label-primary">{_text(label)}</span></p>',
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
    extracts_by_anchor, opener_extracts = _extracts_by_anchor(article)

    if (
        _article_opener_format(edition) == "illustrated_paper_spots_v1"
        and article.opener_art is not None
    ):
        return _render_illustrated_article(
            edition,
            article,
            document,
            article_index,
            opener_figures,
            figures_by_anchor,
        )

    assets: list[HtmlAsset] = []
    lines = [
        f'<article id="{_attr(_article_destination_id(article))}" data-article-id="{_attr(article.id)}" '
        f'data-content-mode="{_attr(article.content_mode)}" data-source-ids="{_attr(" ".join(article.source_ids))}" '
        f'data-figure-layouts="{_attr(_figure_layouts(article))}" '
        f'data-short-title="{_attr(article.short_title)}">',
        "  <header>",
        f'    <p class="content-label" data-content-mode="{_attr(article.content_mode)}">'
        f'<span class="label-primary">{_text(_ui(edition, "feature"))} {article_index:02d}</span>'
        f'<span class="label-secondary">{_text(_content_label(edition, document, article.content_mode))}</span>'
        + (f'<span class="label-separator" aria-hidden="true"> / </span><span class="label-date">{_text(article.dateline)}</span>' if article.dateline else "")
        + "</p>",
        f"    <h1>{_text(article.title)}</h1>",
        f'    <p class="byline" data-byline="true">'
        f'<span class="byline-prefix">{_text(_ui(edition, "by"))}</span> {_text(article.author)}</p>',
    ]
    if article.author_note:
        lines.append(f'    <p class="author-note">{_text(article.author_note)}</p>')
    lines.extend(
        [
            '    <p class="provenance" data-provenance="source-ids">'
            + _text(_ui(edition, "sources"))
            + ": "
            + ", ".join(
                f'<span data-source-id="{_attr(source_id)}">{_text(source_id)}</span>'
                for source_id in article.source_ids
            )
            + "</p>",
            "  </header>",
        ]
    )
    for figure in opener_figures:
        figure_html, asset = _render_figure(edition, article.id, figure)
        lines.extend(_indent((figure_html,), 2))
        assets.append(asset)
    for extract in opener_extracts:
        lines.extend(_indent((_render_extract(edition, article.id, extract),), 2))

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
            for extract in extracts_by_anchor.get(_anchor_key(_inline_text(block.children)), ()):
                lines.extend(_indent((_render_extract(edition, article.id, extract),), 2))

    lines.extend(_indent(_render_key_ideas(edition, article), 2))
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
        tail_art_fit = str(
            (getattr(edition, "raw", {}) or {}).get("tail_art_fit") or "cover"
        )
        asset = _asset(
            id=f"article-tail-{article.id}", role="article_tail", path=article.tail_art,
            alt_text=f"Tail art for {article.title}", article_id=article.id,
        )
        assets.append(asset)
        lines.extend(
            _indent(
                (
                    f'<figure class="article-tail" data-asset-role="article_tail" '
                    f'data-fit="{_attr(tail_art_fit)}">'
                    f'<img src="{_attr(asset.src)}" alt="{_attr(asset.alt_text)}"></figure>',
                ),
                2,
            )
        )
    lines.extend(_indent(_render_source_link(article), 2))
    lines.append("</article>")
    return "\n".join(lines), tuple(assets)


def _render_illustrated_article(
    edition: Edition,
    article: Article,
    document: PublicationDocument,
    article_index: int,
    opener_figures: list[Figure],
    figures_by_anchor: dict[str, list[Figure]],
) -> tuple[str, tuple[HtmlAsset, ...]]:
    """Render the shared semantic structure for the illustrated opener."""

    extracts_by_anchor, opener_extracts = _extracts_by_anchor(article)
    if not document.blocks or not isinstance(document.blocks[0], Paragraph):
        raise ValueError(
            "illustrated_paper_spots_v1 requires a paragraph as the first manuscript block"
        )
    opener_art = article.opener_art
    if opener_art is None:
        raise ValueError("illustrated_paper_spots_v1 requires article opener art")

    art_asset = _asset(
        id=f"article-opener-{article.id}",
        role="article_opener",
        path=opener_art.path,
        alt_text=opener_art.alt_text,
        article_id=article.id,
        credit=opener_art.credit,
    )
    assets: list[HtmlAsset] = [art_asset]
    source_link = _render_source_link(article)
    lines = [
        f'<article id="{_attr(_article_destination_id(article))}" data-article-id="{_attr(article.id)}" '
        f'data-content-mode="{_attr(article.content_mode)}" data-source-ids="{_attr(" ".join(article.source_ids))}" '
        f'data-figure-layouts="{_attr(_figure_layouts(article))}" '
        f'data-short-title="{_attr(article.short_title)}" '
        'data-article-opener="illustrated_paper_spots_v1">',
        '  <header class="article-opener">',
        '    <figure class="article-opener-art" data-asset-role="article_opener">',
        '      <span class="article-opener-art-offset" aria-hidden="true"></span>',
        f'      <img src="{_attr(art_asset.src)}" alt="{_attr(art_asset.alt_text)}">',
        "    </figure>",
        f'    <p class="content-label" data-content-mode="{_attr(article.content_mode)}">'
        f'<span class="label-primary">{_text(_ui(edition, "feature"))} {article_index:02d}</span>'
        '<span class="label-separator" aria-hidden="true"> / </span>'
        f'<span class="label-secondary">{_text(_content_label(edition, document, article.content_mode))}</span>'
        + (f'<span class="label-separator" aria-hidden="true"> / </span><span class="label-date">{_text(article.dateline)}</span>' if article.dateline else "")
        + "</p>",
        f"    <h1>{_text(article.title)}</h1>",
        '    <span class="opener-tick" aria-hidden="true"></span>',
        '    <div class="opener-meta">',
        '      <div class="opener-credit">',
        f'        <p class="byline" data-byline="true">'
        f'<span class="byline-prefix">{_text(_ui(edition, "by"))}</span> {_text(article.author)}</p>',
    ]
    if article.author_note:
        lines.append(f'        <p class="author-note">{_text(article.author_note)}</p>')
    lines.extend(
        [
            "      </div>",
            *_indent(source_link, 6),
            "    </div>",
            "    " + _render_block(document.blocks[0], standfirst=True),
            "  </header>",
        ]
    )

    for figure in opener_figures:
        figure_html, asset = _render_figure(edition, article.id, figure)
        lines.extend(_indent((figure_html,), 2))
        assets.append(asset)
    for extract in opener_extracts:
        lines.extend(_indent((_render_extract(edition, article.id, extract),), 2))

    references = False
    for block in document.blocks[1:]:
        if isinstance(block, Heading):
            references = _is_reference_heading(_inline_text(block.children))
        lines.extend(_indent((_render_block(block, references=references),), 2))
        if isinstance(block, Heading):
            for figure in figures_by_anchor.get(
                _anchor_key(_inline_text(block.children)), ()
            ):
                figure_html, asset = _render_figure(edition, article.id, figure)
                lines.extend(_indent((figure_html,), 2))
                assets.append(asset)
            for extract in extracts_by_anchor.get(
                _anchor_key(_inline_text(block.children)), ()
            ):
                lines.extend(_indent((_render_extract(edition, article.id, extract),), 2))

    lines.extend(_indent(_render_key_ideas(edition, article), 2))
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
        tail_art_fit = str(
            (getattr(edition, "raw", {}) or {}).get("tail_art_fit") or "cover"
        )
        asset = _asset(
            id=f"article-tail-{article.id}",
            role="article_tail",
            path=article.tail_art,
            alt_text=f"Tail art for {article.title}",
            article_id=article.id,
        )
        assets.append(asset)
        lines.extend(
            _indent(
                (
                    f'<figure class="article-tail" data-asset-role="article_tail" '
                    f'data-fit="{_attr(tail_art_fit)}">'
                    f'<img src="{_attr(asset.src)}" alt="{_attr(asset.alt_text)}"></figure>',
                ),
                2,
            )
        )
    lines.append("</article>")
    return "\n".join(lines), tuple(assets)


def _render_key_ideas(edition: Edition, article: Article) -> tuple[str, ...]:
    """The article's closing key-ideas box, or nothing.

    An ``aside`` and not a ``section``: the lines are editorial furniture about
    the article, not a further part of it, and the distinction is load-bearing
    for the print adapter, which addresses the edition's real sections by tag.
    The kicker is a labelled paragraph rather than a heading for the same
    reason a content label is -- a heading here would enter the article's own
    heading sequence, which is what ``edition.yaml``'s figure anchors are
    matched against.
    """
    if not article.key_ideas:
        return ()
    items = "".join(f"<li>{_text(idea)}</li>" for idea in article.key_ideas)
    return (
        f'<aside class="key-ideas" data-key-ideas="{len(article.key_ideas)}" '
        f'data-article-id="{_attr(article.id)}">'
        f'<p class="key-ideas-label">{_text(_ui(edition, "key_ideas"))}</p>'
        f"<ul>{items}</ul></aside>",
    )


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


# The plate window's aspect (weasyprint-a5.css .closing-plate img,
# 333.0079 x 390.2756pt).  Plates draw contained -- never cropped -- so art
# far from this aspect letterboxes; past a factor of two it prints as a
# sliver in white space, which is a build error, not a taste question.
_PLATE_WINDOW_ASPECT = 333.0079 / 390.2756


def _render_closing_plates(edition: Edition, assets: list[HtmlAsset]) -> tuple[str, ...]:
    plates: list[str] = []
    for index, plate in enumerate(edition.closing_plates, start=1):
        try:
            from PIL import Image

            with Image.open(plate.art_path) as image:
                aspect = image.width / image.height
        except (OSError, ValueError, ZeroDivisionError) as exc:
            raise ValidationError(
                f"Closing plate {index} needs a readable raster source: {plate.art_path}"
            ) from exc
        if not _PLATE_WINDOW_ASPECT / 2 <= aspect <= _PLATE_WINDOW_ASPECT * 2:
            raise ValidationError(
                f"Closing plate {index} art {plate.art_path} has aspect {aspect:.2f}; "
                f"contained in the {_PLATE_WINDOW_ASPECT:.2f} plate window it would "
                "print as a sliver. Use art nearer the window's shape."
            )
        asset = _asset(
            id=f"closing-plate-{index}", role="closing_plate", path=plate.art_path,
            alt_text=plate.title,
        )
        assets.append(asset)
        # Image only, no printed title (editor's ruling, 2026-08-07): the
        # plate's configured title survives as alt text and record keeping.
        plates.append(
            '<figure class="closing-plate" data-asset-role="closing_plate" '
            f'data-closing-plate="{index}"><img src="{_attr(asset.src)}" '
            f'alt="{_attr(plate.title)}"></figure>'
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
        anchor=figure.anchor, layout=figure.layout,
    )
    return (
        '<figure data-figure-id="{id}" data-article-id="{article}" data-source-id="{source}" '
        'data-anchor="{anchor}" data-layout="{layout}" '
        'data-figure-label="{word}">'
        '<img src="{src}" alt="{alt}"><figcaption><span class="caption">{caption}</span>'
        '<span class="credit">{credit}</span></figcaption></figure>'.format(
            id=_attr(figure.id), article=_attr(article_id), source=_attr(figure.source_id),
            anchor=_attr(figure.anchor), layout=_attr(figure.layout),
            src=_attr(asset.src), alt=_attr(figure.alt_text),
            caption=_text(figure.caption), credit=_text(figure.credit),
            word=_attr(_ui(edition, "figure")),
        ),
        asset,
    )


def _extracts_by_anchor(
    article: Article,
) -> tuple[dict[str, list[Extract]], list[Extract]]:
    by_anchor: dict[str, list[Extract]] = {}
    opener: list[Extract] = []
    for extract in article.extracts:
        if extract.anchor == "__opener__":
            opener.append(extract)
        else:
            by_anchor.setdefault(_anchor_key(extract.anchor), []).append(extract)
    return by_anchor, opener


def _render_extract(edition: Edition, article_id: str, extract: Extract) -> str:
    """One verbatim extract panel.

    An ``aside``, like the key-ideas box, because the run is editorial
    furniture beside the article rather than a further part of it -- and so it
    stays out of the figure counter and the heading sequence.  The text goes
    through ``_verbatim`` in both styles: the run is byte-exact source
    material, so no quote education and no character folding.
    """

    body: str
    if extract.style == "code":
        # Newlines become explicit breaks and the panel wraps with normal
        # whitespace processing: a preserved trailing space on a soft-wrapped
        # pre-wrap line hangs past the measure and fails the print critic.
        # resolve_extracts refuses code extracts whose whitespace is
        # layout-significant, so collapsing is display-safe here.
        lines = "<br>".join(_verbatim(line) for line in extract.text.split("\n"))
        body = f"<pre><code>{lines}</code></pre>"
    else:
        paragraphs = "".join(
            f"<p>{_verbatim(paragraph.strip())}</p>"
            for paragraph in extract.text.split("\n\n")
            if paragraph.strip()
        )
        body = f"<blockquote>{paragraphs}</blockquote>"
    return (
        f'<aside class="extract" data-extract-id="{_attr(extract.id)}" '
        f'data-article-id="{_attr(article_id)}" data-source-id="{_attr(extract.source_id)}" '
        f'data-anchor="{_attr(extract.anchor)}" data-style="{_attr(extract.style)}" '
        f'data-extract-label="{_attr(_ui(edition, "verbatim"))}">'
        f"{body}"
        f'<p class="extract-caption">{_text(extract.caption)}</p></aside>'
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
        if _is_name_roster(_inline_text(block.children)):
            opening = opening[:-1] + ' data-name-roster="true">'
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


def _article_opener_format(edition: Edition) -> str:
    raw_format = (getattr(edition, "raw", {}) or {}).get("format")
    if not isinstance(raw_format, dict):
        return ""
    return str(raw_format.get("article_opener") or "").strip()


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


# A paragraph whose whole text is short segments separated by bullets is a
# roster of names -- signatories, sponsors, members -- and not running prose,
# the same editorial distinction `_is_reference_heading` draws for a
# bibliography.  The boundary is content-derived and deterministic: running
# prose that happens to quote a bullet yields at most two segments, and prose
# on both sides of two bullets yields a segment that reads as a clause, longer
# than any name.  Every entry in the roster this rule was written against is
# one to four words ("Y Combinator", "American Innovators Network"); six is
# headroom for a longer organization name, not an invitation to a sentence.
_ROSTER_SEPARATOR = "\N{BULLET}"
_ROSTER_MIN_NAMES = 3
_ROSTER_MAX_NAME_WORDS = 6


def _is_name_roster(text: str) -> bool:
    """True when ``text`` is a bullet-separated roster of names, not prose.

    The answer becomes ``data-name-roster`` on the paragraph, so an adapter
    can treat the block as what it is -- proper nouns in a list that happens
    to be set in a paragraph.  The print stylesheet's use is to keep the
    hyphenator out: a broken "DoorDash" or "Y Combinator" is a misprint, not
    a rag repair.
    """
    names = [segment.strip() for segment in text.split(_ROSTER_SEPARATOR)]
    if len(names) < _ROSTER_MIN_NAMES:
        return False
    return all(name and len(name.split()) <= _ROSTER_MAX_NAME_WORDS for name in names)


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
        "article": "ARTICLE",
        "in_a_nutshell": "IN A NUTSHELL",
        "original_editorial": "ORIGINAL EDITORIAL",
        "source_introduction": "THE SOURCE",
        "source_record": "SOURCE RECORD",
        "production_note": "PRODUCTION NOTE",
        "glossary": "GLOSSARY",
        "try_it": "TRY IT",
        "cheat_sheet": "CHEAT SHEET",
        "key_ideas": "KEY IDEAS",
        "verbatim": "VERBATIM",
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
        "article": "ARTÍCULO",
        "in_a_nutshell": "EN POCAS PALABRAS",
        "original_editorial": "EDITORIAL ORIGINAL",
        "source_introduction": "LA FUENTE",
        "source_record": "REGISTRO DE FUENTE",
        "production_note": "NOTA DE PRODUCCIÓN",
        "glossary": "GLOSARIO",
        "try_it": "PRUÉBALO",
        "cheat_sheet": "HOJA DE REFERENCIA",
        "key_ideas": "IDEAS CLAVE",
        "verbatim": "TEXTUAL",
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
