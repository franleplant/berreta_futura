"""The web adapter's contract: a self-contained, deterministic, paged edition.

These tests exercise :mod:`magazine.web_edition` through its public seam,
:func:`write_web_edition`, against the same hostile fixture edition the
semantic HTML suite uses -- ids and titles full of markup metacharacters, a
cover and a figure sharing one source file -- because the web directory is
where every one of those properties finally meets a real filesystem and a
real browser.  The paging contract is held page by page: the cover index links
onward to one page per piece, the pieces turn into each other in reading
order, and ``edition.html`` keeps the whole document for one scroll.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from magazine import web_edition
from magazine.errors import ValidationError
from magazine.manifest import Article, ClosingPlate, Edition, Editorial, Section
from magazine.media_schema import Figure
from magazine.web_edition import write_web_edition


def _edition(tmp_path: Path, *, locale: str = "en", manuscript: str | None = None) -> Edition:
    article_path = tmp_path / "article.md"
    article_path.write_text(
        manuscript
        or "---\nlabel: FAITHFUL SYNTHESIS\n---\n"
        "# Reader title\n\n"
        "An *emphasis*, **strong phrase**, [working link](https://example.test/a?x=1&y=2 \"Source & title\"), and `code`.\n\n"
        "> A quoted line.\n\n"
        "- First\n  - Nested\n\n"
        "3. Third\n\n"
        "```python\nprint('café')\n```\n\n"
        "## Exact anchor\n\nAfter the anchor.\n",
        encoding="utf-8",
    )
    editorial_path = tmp_path / "editorial.md"
    editorial_path.write_text("---\ntitle: Editorial\n---\nEditorial body.", encoding="utf-8")
    section_path = tmp_path / "section.md"
    section_path.write_text("## Section detail\n\nSection body.", encoding="utf-8")
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"image")
    tail_path = tmp_path / "tail.png"
    tail_path.write_bytes(b"tail")
    plate_path = tmp_path / "plate.png"
    plate_path.write_bytes(b"plate")
    figure = Figure(
        id="exact-figure", source_id="source<&>", asset_id="asset", path=image_path,
        caption="Caption <&>", credit="Credit <&>", alt_text="Alt <&>",
        anchor="Exact anchor", layout="evidence_band", rights_status="unknown",
        bundle_sha256="a" * 64, artifact_sha256="b" * 64, criteria=("important",),
        rationale="Required evidence.",
    )
    opener = Figure(
        id="opener-figure", source_id="source-one", asset_id="opener", path=image_path,
        caption="Opener", credit="Credit", alt_text="Opener alt", anchor="__opener__",
        layout="evidence_band", rights_status="unknown", bundle_sha256="c" * 64,
        artifact_sha256="d" * 64, criteria=("important",), rationale="Opener evidence.",
    )
    article = Article(
        id="article<&>", title="Article <&>", short_title="Article", display_emphasis="",
        opener_variant="edge_medallion", author="Author <&>", author_note="Note <&>",
        source_ids=("source-one", "source-two"), manuscript=article_path,
        fidelity=tmp_path / "fidelity.yaml", content_mode="faithful_synthesis",
        figures=(opener, figure), tail_art=tail_path,
        source_url="https://example.test/source?a=1&b=2",
    )
    return Edition(
        id="edition<&>", publication_name="Magazine <&>", issue_number="7", title="Issue <&>",
        publication_date="2026-07-24", language=locale.split("-")[0], locale=locale,
        editorial=Editorial(editorial_path, "Editorial <&>", "Editors <&>", "ORIGINAL <&>"),
        articles=(article,), sections=(Section("source_record", "Sources <&>", section_path),),
        cover={"headline": "Cover <&>"}, cover_art=image_path,
        closing_plates=(ClosingPlate("Plate <&>", plate_path),), raw={"subtitle": "Sub <&>"},
    )


def _wordmark(tmp_path: Path) -> Path:
    mark = tmp_path / "wordmark.svg"
    mark.write_text("<svg><!-- the lockup --></svg>", encoding="utf-8")
    return mark


def _page_files(result: web_edition.WebEdition) -> list[Path]:
    return [result.index, *result.pages, result.edition_document]


def test_the_web_directory_is_self_contained_and_every_src_resolves(tmp_path: Path):
    """No ``file:`` URI survives, and every ``src`` on any page names a
    shipped file.

    Self-containment is the whole point of the adapter: the directory must be
    servable from any path and openable from the filesystem, so a single
    surviving absolute URI -- or a src whose target was never copied -- is a
    broken page on someone else's machine.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")

    seen: list[str] = []
    for page in _page_files(result):
        html = page.read_text(encoding="utf-8")
        assert "file:" not in html, page.name
        for src in re.findall(r'src="([^"]+)"', html):
            assert not src.startswith("file:")
            assert (result.root / src).is_file(), f"{page.name}: {src}"
            seen.append(src)
    assert seen, "the fixture edition renders figures and plates"


def test_the_edition_is_paged_one_file_per_piece_in_reading_order(tmp_path: Path):
    """Editorial, article and section each get their own page, in order.

    The page files carry the pieces' own destination ids as names, the cover
    index and the one-scroll document stand beside them, and each piece page
    holds exactly its piece -- the editorial page has no article markup and
    the article page no section.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")

    assert result.index.name == "index.html"
    assert result.edition_document.name == "edition.html"
    assert [page.name for page in result.pages][0] == "editorial.html"
    assert len(result.pages) == 3
    for page in result.pages:
        assert page.is_file()

    editorial, article, section = (
        page.read_text(encoding="utf-8") for page in result.pages
    )
    assert 'class="editorial"' in editorial and "<article" not in editorial
    assert "<article" in article and 'class="editorial"' not in article
    assert 'data-section-kind="source_record"' in section and "<article" not in section


def test_the_index_is_the_cover_page_and_links_onward_to_the_piece_pages(tmp_path: Path):
    """The cover index links every contents entry at a page, not an anchor.

    Without a wordmark the index falls back to the raw artwork over the
    semantic edition header; either way it holds the contents whose hrefs are
    the piece files, while the piece markup itself lives only on the piece
    pages.  Closing plates are filler art and never reach the index (their
    own test below owns the whole-tree absence).
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")
    html = result.index.read_text(encoding="utf-8")

    assert 'class="cover-art"' in html
    assert 'class="edition-header"' in html
    assert 'class="closing-plate"' not in html
    assert "<article" not in html

    hrefs = re.findall(r'<a class="entry-title" href="([^"]+)"', html)
    assert hrefs and not [href for href in hrefs if href.startswith("#")]
    for href in hrefs:
        assert (result.root / href).is_file(), href
    assert hrefs[0] == "editorial.html"


def test_the_piece_pages_turn_into_each_other_in_reading_order(tmp_path: Path):
    """Prev/next chain: first page has no previous, last no next, labels are
    the neighbours' own short titles, and every turn names an existing file.

    The masthead on every piece page is the way back to the cover index.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")
    pages = [page.read_text(encoding="utf-8") for page in result.pages]

    for html in pages:
        assert '<nav class="masthead" data-web-chrome="masthead"><a href="index.html">' in html

    first, middle, last = pages
    assert "page-turn-previous" not in first
    assert f'rel="next" href="{result.pages[1].name}"' in first
    assert f'rel="prev" href="{result.pages[0].name}"' in middle
    assert f'rel="next" href="{result.pages[2].name}"' in middle
    assert "page-turn-next" not in last
    assert f'rel="prev" href="{result.pages[1].name}"' in last
    # The labels are the neighbours' short titles as the document wrote them.
    assert ">Article</a>" in first
    assert ">Editorial</a>" in middle


def test_provenance_ids_link_when_an_address_is_known_and_stay_text_when_not(tmp_path: Path):
    """``source_urls`` turns provenance mentions into numbered references.

    A source mention's visible text is its two-digit index in the opener's
    order -- a raw slug set as type wraps mid-filename and reads as build
    infrastructure, the stylistic critics' unanimous worst offender -- while
    the id survives as the ``title``, so the fact stays inspectable.  Mapping
    one address links exactly that mention -- on its piece page and in the
    one-scroll document alike -- and leaves the other a plain span rather
    than a broken link.  Without the mapping nothing links at all.
    """

    edition = _edition(tmp_path)
    result = write_web_edition(
        edition, tmp_path / "web", source_urls={"source-one": "https://example.test/one?a=1&b=2"}
    )

    linked = (
        '<a class="provenance-source" data-source-id="source-one" title="source-one" '
        'aria-label="source-one" href="https://example.test/one?a=1&amp;b=2">01</a>'
    )
    plain = (
        '<span class="provenance-source" data-source-id="source-two" title="source-two" '
        'aria-label="source-two">02</span>'
    )
    article = result.pages[1].read_text(encoding="utf-8")
    whole = result.edition_document.read_text(encoding="utf-8")
    assert linked in article and plain in article
    assert linked in whole and plain in whole
    # The slug never ships as visible text: it lives only in attributes.
    assert ">source-one</a>" not in article and ">source-two</span>" not in article

    unmapped = write_web_edition(edition, tmp_path / "web-unmapped")
    assert "https://example.test/one" not in unmapped.pages[1].read_text(encoding="utf-8")


def test_print_furniture_is_dropped_tail_art_and_closing_plates_bytes_and_all(tmp_path: Path):
    """No page carries a tail figure, a closing plate, or the source-link anchor.

    All three are print furniture (the adapter's docstring states the
    verdicts; the plates are the filler art a printed object closes on).
    The tail's and plates' bytes do not ship either -- not as a page
    reference and not as a file under ``assets/`` -- and the asset inventory
    the caller receives excludes them.  The fixture declares one plate, so
    absence here is a dropped plate, not a plateless edition.
    """

    edition = _edition(tmp_path)
    assert edition.closing_plates
    result = write_web_edition(edition, tmp_path / "web")

    for page in _page_files(result):
        html = page.read_text(encoding="utf-8")
        assert "article-tail" not in html, page.name
        assert "source-link" not in html, page.name
        assert "closing-plate" not in html, page.name
    dropped = {"article_tail", "closing_plate"}
    assert not [web for web in result.assets if web.asset.role in dropped]
    assert not list((result.root / "assets").glob("*tail*"))
    assert not list((result.root / "assets").glob("*plate*"))
    plate_bytes = edition.closing_plates[0].art_path.read_bytes()
    assert not [
        copied
        for copied in (result.root / "assets").iterdir()
        if copied.read_bytes() == plate_bytes
    ]


def test_the_one_scroll_document_keeps_the_whole_edition_and_its_anchors(tmp_path: Path):
    """``edition.html`` is the full document: every piece, anchor links intact.

    Paging is presentation; the one-scroll document stays the reading path for
    whoever wants the edition as one page, so its contents still navigate by
    in-document anchor exactly as the semantic layer wrote them.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")
    html = result.edition_document.read_text(encoding="utf-8")

    assert 'class="editorial"' in html and "<article" in html
    assert 'data-section-kind="source_record"' in html
    assert 'class="cover-art"' in html
    assert re.search(r'<a class="entry-title" href="#', html)
    assert "masthead" not in html and "page-turn" not in html


def test_asset_filenames_are_sanitized_unique_and_carry_their_suffix(tmp_path: Path):
    """Asset ids full of metacharacters become safe, distinct filenames.

    The fixture's ids carry ``<&>`` -- hostile to filesystems and URLs alike --
    and its cover and anchored figure share one source ``figure.png``, so this
    is where sanitisation, uniqueness and the shared-source case all meet: two
    distinct copies, identical bytes, no collision.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")

    hrefs = [web.href for web in result.assets]
    assert len(set(hrefs)) == len(hrefs)
    for href in hrefs:
        assert re.fullmatch(r"assets/[A-Za-z0-9._-]+", href), href
        assert (result.root / href).is_file()

    cover = next(web for web in result.assets if web.asset.role == "cover_art")
    figure = next(web for web in result.assets if web.asset.role == "figure")
    assert cover.href != figure.href
    assert (result.root / cover.href).read_bytes() == b"image"
    assert (result.root / figure.href).read_bytes() == b"image"


def test_two_ids_that_sanitize_to_one_filename_are_a_named_refusal(tmp_path: Path):
    """Two asset ids folding to the same safe filename refuse, never overwrite.

    Sanitisation folds every unsafe character to ``-``, so distinct ids like
    ``fig<1`` and ``fig>1`` become one ``assets/`` name.  A silently
    overwritten image is the kind of failure only a reader would catch, so the
    collision is a validation error naming both ids.
    """

    edition = _edition(tmp_path)
    article = edition.articles[0]
    figure = article.figures[1]
    twins = (
        replace(figure, id="fig<1", anchor="Exact anchor"),
        replace(figure, id="fig>1", anchor="Exact anchor"),
    )
    colliding = replace(edition, articles=(replace(article, figures=twins),))

    with pytest.raises(ValidationError, match="collision"):
        write_web_edition(colliding, tmp_path / "web")


def test_ids_differing_only_by_case_are_refused_everywhere(tmp_path: Path):
    """Case-aliased filenames refuse on every filesystem, not just APFS.

    On a case-insensitive filesystem ``Fig1.png`` and ``fig1.png`` are one
    file: the second copy silently replaces the first while the page
    references both, so a build that passes on macOS ships a 404 on a
    case-sensitive host.  Claiming names casefolded makes the refusal a
    property of the edition rather than of whichever filesystem built it.
    """

    edition = _edition(tmp_path)
    article = edition.articles[0]
    figure = article.figures[1]
    twins = (
        replace(figure, id="Fig1", anchor="Exact anchor"),
        replace(figure, id="fig1", anchor="Exact anchor"),
    )
    colliding = replace(edition, articles=(replace(article, figures=twins),))

    with pytest.raises(ValidationError, match="case-insensitively"):
        write_web_edition(colliding, tmp_path / "web")


def test_every_page_gains_viewport_and_stylesheet_exactly_once_after_charset(tmp_path: Path):
    """The injected head is one viewport and one stylesheet link, in order,
    on the cover index, every piece page, and the one-scroll document alike.

    A doubled viewport is a browser quirk lottery, and a doubled stylesheet is
    a hint the injection anchor matched more than it should.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")

    viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    stylesheet = '<link rel="stylesheet" href="edition.css">'
    for page in _page_files(result):
        html = page.read_text(encoding="utf-8")
        assert html.count(viewport) == 1, page.name
        assert html.count(stylesheet) == 1, page.name
        head = html.split("</head>")[0]
        assert (
            head.index('<meta charset="utf-8">') < head.index(viewport) < head.index(stylesheet)
        ), page.name
        assert "<title>" in head, page.name


def test_a_head_of_unexpected_shape_is_a_named_refusal(tmp_path: Path):
    """A head without exactly one charset anchor refuses instead of skipping.

    The injection is anchored to the one line the semantic renderer is known
    to emit; if that shape ever changes, the failure must be a validation
    error naming the anchor, never a page that quietly ships unstyled.
    """

    with pytest.raises(ValidationError, match="charset"):
        web_edition._inject_head("<html><head></head><body></body></html>")
    doubled = "\n".join(
        ["<head>", '  <meta charset="utf-8">', '  <meta charset="utf-8">', "</head>"]
    )
    with pytest.raises(ValidationError, match="charset"):
        web_edition._inject_head(doubled)


def test_an_unrecognized_top_level_element_is_a_named_refusal(tmp_path: Path):
    """Paging refuses a document whose top level it cannot account for.

    The split is anchored to the boundaries the renderer guarantees; an
    unrecognized line at the top level means the semantic body changed shape,
    and half a paged edition shipped quietly is worse than no edition.
    """

    with pytest.raises(ValidationError, match="does not recognize"):
        web_edition._parse_document(
            "\n".join(
                [
                    "<!doctype html>",
                    '<html lang="en">',
                    "<head>",
                    "  <title>T</title>",
                    "</head>",
                    "<body>",
                    '  <main data-edition-id="e">',
                    "    <p>a stray top-level paragraph</p>",
                    "  </main>",
                    "</body>",
                    "</html>",
                ]
            )
        )


def test_the_wordmark_makes_the_cover_native_and_heads_every_masthead(tmp_path: Path):
    """With a wordmark the cover is composed for the medium, not pasted.

    The index opens on the cover block -- lockup, localized cover headline,
    the framed raw artwork, the contributor register the printed deck derives
    from the article records, the spaced date, and the canto strip carrying
    the issue and the publication identity -- and the semantic edition header
    stands aside.  Every piece page's masthead sets the lockup image in place
    of the text name, the one-scroll document leads with the same block, and
    the SVG bytes ship once under ``assets/wordmark.svg``.
    """

    edition = _edition(tmp_path)
    result = write_web_edition(edition, tmp_path / "web", wordmark=_wordmark(tmp_path))

    shipped = result.root / "assets" / "wordmark.svg"
    assert shipped.read_text(encoding="utf-8") == "<svg><!-- the lockup --></svg>"

    html = result.index.read_text(encoding="utf-8")
    assert '<header class="cover" data-web-chrome="cover">' in html
    assert 'class="edition-header"' not in html
    assert (
        '<img class="cover-wordmark" src="assets/wordmark.svg" '
        'alt="Magazine &lt;&amp;&gt;">' in html
    )
    # The cover headline is the authored cover mapping, localized upstream.
    assert '<h1 class="cover-headline">Cover &lt;&amp;&gt;</h1>' in html
    # The register is the printed deck's own derivation: article authors,
    # joined and uppercased by cover._cover_contributors.
    assert '<p class="cover-roster">AUTHOR &lt;&amp;&gt;</p>' in html
    # The canto restates the printed tab's exact words: the zero-padded issue
    # at the head, the identity line -- city and all -- at the foot, both
    # from the cover module's own derivations, so the two media cannot drift.
    assert (
        '<p class="canto"><span class="canto-issue">ISSUE 007</span>'
        '<span class="canto-identity">MAGAZINE &lt;&amp;&gt; / BUENOS AIRES</span></p>'
    ) in html
    # The first screen says where the reading starts: a cue down to the
    # contents, labelled with the contents' own heading.
    assert '<a class="cover-cue" href="#contents">' in html
    assert '<nav id="contents" ' in html
    # The date is spaced the way the printed footer spaces it.
    assert '<time class="cover-date" datetime="2026-07-24">2026 07 24</time>' in html
    art = re.search(r'<figure class="cover-art"[^>]*><img src="([^"]+)"', html)
    assert art is not None and (result.root / art.group(1)).read_bytes() == b"image"

    for page in result.pages:
        assert (
            '<img class="masthead-wordmark" src="assets/wordmark.svg" '
            'alt="Magazine &lt;&amp;&gt;">' in page.read_text(encoding="utf-8")
        )
    one_scroll = result.edition_document.read_text(encoding="utf-8")
    assert '<header class="cover" data-web-chrome="cover">' in one_scroll

    bare = write_web_edition(
        replace(edition, cover_art=None), tmp_path / "web-bare",
        wordmark=_wordmark(tmp_path),
    )
    bare_html = bare.index.read_text(encoding="utf-8")
    assert '<header class="cover"' in bare_html
    assert 'class="cover-art"' not in bare_html


def test_the_closing_and_navigation_chrome_answer_the_stylistic_critique(tmp_path: Path):
    """The critique fixes that are page chrome, asserted fact by fact.

    The favicon ships beside the wordmark and is linked from every head; a
    derived headline break sets the printed face's own lines while a break
    for some other text falls back to one run; the colophon closes the cover
    page and the one-scroll document with the identity line, the sibling
    document, the sibling languages, and the date; every page turn carries
    the way home to the contents; and every figure image is a link to its
    own shipped bytes.
    """

    edition = _edition(tmp_path)
    favicon = tmp_path / "favicon.svg"
    favicon.write_text("<svg><!-- the slug bar --></svg>", encoding="utf-8")
    result = write_web_edition(
        edition,
        tmp_path / "web",
        wordmark=_wordmark(tmp_path),
        favicon=favicon,
        headline_lines=("Cover", "<&>"),
        alternates={"es": "../es/"},
    )

    shipped = result.root / "assets" / "favicon.svg"
    assert shipped.read_text(encoding="utf-8") == "<svg><!-- the slug bar --></svg>"
    icon = '<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">'
    pages = [result.index, result.edition_document, *result.pages]
    for page in pages:
        assert icon in page.read_text(encoding="utf-8")

    html = result.index.read_text(encoding="utf-8")
    # The derived break sets the printed face's lines inside the h1.
    assert (
        '<h1 class="cover-headline"><span class="cover-headline-line">Cover</span>'
        '<span class="cover-headline-line">&lt;&amp;&gt;</span></h1>'
    ) in html
    # The colophon: identity, sibling document, sibling language, date.
    for document, sibling, label in (
        (html, "edition.html", "ISSUE 007"),
        (result.edition_document.read_text(encoding="utf-8"), "index.html", None),
    ):
        assert '<footer class="colophon" data-web-chrome="colophon">' in document
        assert '<p class="colophon-identity">MAGAZINE &lt;&amp;&gt; / BUENOS AIRES</p>' in document
        assert f'<a class="colophon-sibling" href="{sibling}">' in document
        assert 'hreflang="es"' in document and ">ES</a>" in document
        assert '<time class="colophon-date" datetime="2026-07-24">2026 07 24</time>' in document
        if label:
            assert f'href="{sibling}">{label}</a>' in document
    # Piece pages do not close on the colophon; their foot is the page turn,
    # whose centre is the way home.
    for page in result.pages:
        page_html = page.read_text(encoding="utf-8")
        assert 'class="colophon"' not in page_html
        assert '<a class="page-turn-contents" href="index.html">' in page_html
    # Every evidence figure's image is a link to its own shipped bytes.
    article = result.pages[1].read_text(encoding="utf-8")
    match = re.search(r'<a class="figure-link" href="([^"]+)"><img src="([^"]+)"', article)
    assert match is not None and match.group(1) == match.group(2)
    assert (result.root / match.group(1)).is_file()

    # A break for some other text is refused into the fallback: one run of
    # the edition's own words, never a silently mismatched construction.
    other = write_web_edition(
        edition,
        tmp_path / "web-mismatch",
        wordmark=_wordmark(tmp_path),
        headline_lines=("Some", "Other", "Words"),
    )
    mismatch = other.index.read_text(encoding="utf-8")
    assert '<h1 class="cover-headline">Cover &lt;&amp;&gt;</h1>' in mismatch
    assert "cover-headline-line" not in mismatch


def test_without_a_wordmark_the_mastheads_and_cover_fall_back_to_text(tmp_path: Path):
    """No lockup file, no lockup: the name is set as text and nothing 404s.

    The cover page keeps the semantic edition header led by the raw artwork
    when there is any, the mastheads set the publication name as the text
    span, and no page references ``assets/wordmark.svg``.
    """

    edition = _edition(tmp_path)
    result = write_web_edition(edition, tmp_path / "web")

    assert not (result.root / "assets" / "wordmark.svg").exists()
    html = result.index.read_text(encoding="utf-8")
    assert 'class="edition-header"' in html
    assert 'class="cover-art"' in html
    assert 'data-web-chrome="cover"' not in html
    for page in result.pages:
        page_html = page.read_text(encoding="utf-8")
        assert "wordmark" not in page_html
        assert '<span class="publication-name">Magazine &lt;&amp;&gt;</span>' in page_html

    bare = write_web_edition(replace(edition, cover_art=None), tmp_path / "web-bare")
    assert 'class="cover-art"' not in bare.index.read_text(encoding="utf-8")


def test_an_asset_that_would_shadow_the_wordmark_is_refused(tmp_path: Path):
    """``assets/wordmark.svg`` is publication chrome; an inventory entry may
    not silently overwrite it.

    No current asset id can spell ``wordmark`` -- figures are prefixed
    ``figure-...``, plates ``closing-plate-...`` -- so the guard is exercised
    at the materializer, the seam every future id vocabulary must pass.
    """

    from magazine.html_edition import HtmlAsset

    mark_art = tmp_path / "mark.svg"
    mark_art.write_bytes(b"<svg/>")
    shadowing = HtmlAsset(
        id="wordmark", role="figure", path=mark_art,
        src=mark_art.as_uri(), alt_text="a shadow",
    )
    with pytest.raises(ValidationError, match="collision"):
        web_edition._materialize_assets(
            (shadowing,), tmp_path / "web", _wordmark(tmp_path)
        )


def test_fonts_licenses_and_stylesheet_ship_with_the_page(tmp_path: Path):
    """The bundled faces, their licenses, and ``edition.css`` are all present.

    Deterministic builds must not use system font lookups, on screen as in
    print, and the SIL licenses travel with the fonts they cover.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")

    assert (result.root / "edition.css").read_bytes() == web_edition._read_screen_css()
    fonts = result.root / "fonts"
    assert list(fonts.rglob("*.ttf")), "the bundled faces ship with the page"
    assert [
        path for path in fonts.rglob("*") if path.name.lower().startswith("license")
    ], "the OFL texts travel with the fonts they cover"


def test_two_builds_of_the_same_edition_are_byte_identical(tmp_path: Path):
    """Determinism: the same validated inputs write the same tree twice.

    No timestamps, no enumeration order, no randomness -- the property both
    print engines already contract to, holding across every page, asset and
    font of the web tree as well.
    """

    edition = _edition(tmp_path)
    mark = _wordmark(tmp_path)
    urls = {"source-one": "https://example.test/one"}
    first = write_web_edition(edition, tmp_path / "first", wordmark=mark, source_urls=urls)
    second = write_web_edition(edition, tmp_path / "second", wordmark=mark, source_urls=urls)

    first_files = sorted(
        path.relative_to(first.root) for path in first.root.rglob("*") if path.is_file()
    )
    second_files = sorted(
        path.relative_to(second.root) for path in second.root.rglob("*") if path.is_file()
    )
    assert first_files == second_files
    assert first_files, "an edition writes more than nothing"
    for relative in first_files:
        assert (first.root / relative).read_bytes() == (second.root / relative).read_bytes(), relative
