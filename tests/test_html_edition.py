from dataclasses import replace
from pathlib import Path

from magazine import Magazine
from magazine.html_edition import render_html_edition
from magazine.manifest import (
    Article,
    ArticleOpenerArt,
    ClosingPlate,
    Edition,
    Editorial,
    Section,
)
from magazine.media_schema import Figure
from magazine.reader_text import fold_reader_characters
from magazine.render import _plain


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


def test_html_edition_preserves_document_semantics_escaping_and_asset_metadata(tmp_path: Path):
    result = render_html_edition(_edition(tmp_path))

    assert result.html.startswith("<!doctype html>\n<html lang=\"en\"")
    assert '<meta charset="utf-8">' in result.html
    assert "Magazine &lt;&amp;&gt; — Issue &lt;&amp;&gt;" in result.html
    assert "Article &lt;&amp;&gt;" in result.html
    assert "Caption &lt;&amp;&gt;" in result.html
    assert '<em>emphasis</em>' in result.html
    assert '<strong>strong phrase</strong>' in result.html
    assert '<a href="https://example.test/a?x=1&amp;y=2" title="Source &amp; title">working link</a>' in result.html
    assert "<code>code</code>" in result.html
    assert "<blockquote><p>A quoted line.</p></blockquote>" in result.html
    assert "<ul><li><p>First</p><ul><li><p>Nested</p></li></ul></li></ul>" in result.html
    assert '<ol start="3"><li><p>Third</p></li></ol>' in result.html
    assert '<pre><code class="language-python">print(\'café\')\n</code></pre>' in result.html
    assert 'data-content-mode="faithful_synthesis"' in result.html
    assert 'data-provenance="source-ids"' in result.html
    assert 'data-source-id="source-one"' in result.html
    assert 'data-figure-id="exact-figure"' in result.html
    assert 'data-anchor="Exact anchor"' in result.html
    assert '<nav aria-label="Contents" data-edition-navigation="contents">' in result.html
    # A contents entry is a row of four editorial facts, and its folio is a
    # second link to the same destination so the page number can resolve.
    assert (
        '<li><span class="entry-label">Editorial</span>'
        '<a class="entry-folio" href="#editorial" aria-hidden="true"></a>'
        '<a class="entry-title" href="#editorial">Editorial &lt;&amp;&gt;</a>'
        '<span class="entry-author">Editors &lt;&amp;&gt;</span></li>'
    ) in result.html
    assert (
        '<li><span class="entry-label">Feature 01</span>'
        '<a class="entry-folio" href="#article-article&lt;&amp;&gt;" aria-hidden="true"></a>'
        '<a class="entry-title" href="#article-article&lt;&amp;&gt;">Article &lt;&amp;&gt;</a>'
        '<span class="entry-author">Author &lt;&amp;&gt;</span></li>'
    ) in result.html
    assert '<a class="entry-title" href="#section-0">Sources &lt;&amp;&gt;</a>' in result.html
    assert '<p class="contents-kicker">Issue 7 / Contents</p>' in result.html
    # The opener chrome is a pair of labels, a prefixed byline and an end mark.
    assert '<span class="label-primary">Feature 01</span>' in result.html
    assert '<span class="label-secondary">FAITHFUL SYNTHESIS</span>' in result.html
    assert '<span class="label-secondary">An original argument</span>' in result.html
    assert '<span class="byline-prefix">By</span> Author &lt;&amp;&gt;' in result.html
    assert '<p class="end-mark" data-end-mark="true">End / 01</p>' in result.html
    assert 'data-short-title="Article"' in result.html
    assert 'data-figure-label="Figure"' in result.html
    assert '<section id="editorial" class="editorial"' in result.html
    assert '<article id="article-article&lt;&amp;&gt;"' in result.html
    assert (
        '<section id="section-0" data-section-kind="source_record"'
        ' data-short-title="Sources &lt;&amp;&gt;">'
    ) in result.html
    assert (
        result.html.index('href="#editorial"')
        < result.html.index('href="#article-article&lt;&amp;&gt;"')
        < result.html.index('href="#section-0"')
        < result.html.index('id="editorial"')
    )

    exact_heading = result.html.index("<h2>Exact anchor</h2>")
    exact_figure = result.html.index('data-figure-id="exact-figure"')
    after_anchor = result.html.index("<p>After the anchor.</p>")
    opener = result.html.index('data-figure-id="opener-figure"')
    article_heading = result.html.index("<h1>Article &lt;&amp;&gt;</h1>")
    assert article_heading < opener < exact_heading < exact_figure < after_anchor

    assert [asset.id for asset in result.assets] == [
        "figure-article<&>-opener-figure", "figure-article<&>-exact-figure",
        "article-tail-article<&>", "closing-plate-1", "cover-art",
    ]
    figure_asset = result.assets[1]
    assert figure_asset.path == tmp_path / "figure.png"
    assert figure_asset.src == (tmp_path / "figure.png").as_uri()
    assert figure_asset.source_id == "source<&>"
    assert figure_asset.caption == "Caption <&>"
    assert figure_asset.anchor == "Exact anchor"
    assert figure_asset.layout == "evidence_band"
    assert figure_asset.artifact_sha256 == "b" * 64
    assert result.assets[2].rights_status == "author_owned"
    assert result.assets[3].rights_status == "author_owned"


def test_html_edition_uses_edition_locale_for_spanish(tmp_path: Path):
    html = render_html_edition(_edition(tmp_path, locale="es-AR")).html

    assert '<html lang="es-AR"' in html
    assert "data-article-opener-format" not in html
    assert ">Número 7</p>" in html
    assert '<nav aria-label="Índice" data-edition-navigation="contents">' in html
    assert "<h2>Índice</h2>" in html
    assert ">Fuentes: " in html
    assert "café" in html


def test_html_edition_omits_empty_author_note_markup(tmp_path: Path):
    edition = _edition(tmp_path)
    article = replace(edition.articles[0], author_note="")
    html = render_html_edition(replace(edition, articles=(article,))).html

    assert '<p class="author-note">' not in html
    assert '<span class="byline-prefix">By</span> Author &lt;&amp;&gt;' in html


def test_illustrated_article_opener_has_shared_semantic_order_and_asset(tmp_path: Path):
    edition = _edition(
        tmp_path,
        manuscript=(
            "---\nlabel: FAITHFUL SYNTHESIS\n---\n"
            "An opening paragraph with a [working link](https://example.test).\n\n"
            "> A quoted continuation.\n\n"
            "## Exact anchor\n\n"
            "After the anchor.\n"
        ),
    )
    article = replace(
        edition.articles[0],
        opener_art=ArticleOpenerArt(
            path=tmp_path / "figure.png",
            alt_text="Boy and robot connect systems.",
            credit="Original illustration.",
        ),
    )
    edition = replace(
        edition,
        articles=(article,),
        raw={
            **edition.raw,
            "format": {"article_opener": "illustrated_paper_spots_v1"},
        },
    )

    result = render_html_edition(edition)
    html = result.html

    assert 'data-article-opener-format="illustrated_paper_spots_v1"' in html
    article_start = html.index('data-article-opener="illustrated_paper_spots_v1"')
    art = html.index(
        '<figure class="article-opener-art" data-asset-role="article_opener">',
        article_start,
    )
    art_offset = html.index(
        '<span class="article-opener-art-offset" aria-hidden="true"></span>',
        art,
    )
    art_image = html.index('<img src="', art_offset)
    label = html.index('<p class="content-label"', art)
    title = html.index("<h1>Article &lt;&amp;&gt;</h1>", label)
    tick = html.index('<span class="opener-tick" aria-hidden="true"></span>', title)
    meta = html.index('<div class="opener-meta">', tick)
    credit = html.index('<div class="opener-credit">', meta)
    byline = html.index('<p class="byline"', credit)
    bio = html.index('<p class="author-note">', byline)
    source_link = html.index(
        '<a class="source-link" data-source-link="primary"', bio
    )
    standfirst = html.index('<p class="standfirst">', source_link)
    opener_end = html.index("</header>", standfirst)
    evidence = html.index('data-figure-id="opener-figure"', opener_end)
    continuation = html.index("<blockquote>", evidence)

    assert (
        art
        < art_offset
        < art_image
        < label
        < title
        < tick
        < meta
        < credit
        < byline
        < bio
        < source_link
        < standfirst
        < opener_end
        < evidence
        < continuation
    )
    assert '<span class="label-primary">Feature 01</span>' in html
    assert '<span class="label-separator" aria-hidden="true"> / </span>' in html
    assert '<span class="label-secondary">FAITHFUL SYNTHESIS</span>' in html
    assert 'data-source-ids="source-one source-two"' in html
    article_html = html[article_start : html.index("</article>", article_start)]
    assert 'data-provenance="source-ids"' not in article_html
    assert ">Sources:" not in article_html
    assert article_html.count('data-source-link="primary"') == 1
    assert "<figcaption>Original illustration." not in article_html

    opener_asset = result.assets[0]
    assert opener_asset.id == "article-opener-article<&>"
    assert opener_asset.role == "article_opener"
    assert opener_asset.alt_text == "Boy and robot connect systems."
    assert opener_asset.credit == "Original illustration."
    assert opener_asset.rights_status == "author_owned"


def test_reader_keeps_real_quotation_marks_and_educates_the_straight_ones(tmp_path: Path):
    """Authored quotation marks reach the page as real marks, never mixed.

    The fold used to turn every curly quote into its ASCII form for cp1252
    parity with ``render.py``; all eight bundled faces carry the real marks, so
    it no longer does.  A *straight* quote in prose is now educated into the
    mark it stands for -- edition 002 shipped straight apostrophes beside curly
    ones on single pages, and an independent review flagged the mix.  Attribute
    values are not prose: there the straight quote survives, and escaping is
    still what keeps it from terminating the value.
    """
    edition = _edition(tmp_path)
    titled = replace(
        edition.articles[0],
        title='The “Dark” Factory’s ‘case’ study… and its "plain" one',
    )
    html = render_html_edition(replace(edition, articles=(titled,))).html

    assert (
        "<h1>The “Dark” Factory’s ‘case’ study… and its “plain” one</h1>"
        in html
    )
    assert (
        'alt="Tail art for The “Dark” Factory’s ‘case’ study… '
        'and its &quot;plain&quot; one"'
    ) in html
    assert 'href="#article-article&lt;&amp;&gt;"' in html
    assert '<img src="' in html and 'alt="Alt &lt;&amp;&gt;"' in html


def test_prose_apostrophes_are_educated_in_body_and_standfirst_alike(tmp_path: Path):
    """The two straight marks edition 002 actually printed, pinned at the seam.

    En p16 set "the new run's pace" -- a possessive on a word inside numeral-heavy
    copy -- and p26's lede set "It's become" while the same page carried curly
    marks two lines down.  Neither is a special code path: the lede/standfirst
    renders through the same ``Text`` inline as a body paragraph, and both must
    come out as U+2019.  Code spans and fenced code keep their straight quotes:
    a quote there is content.
    """
    manuscript = (
        "It's become one of the most widely adopted internal tools since launching 3 months ago.\n\n"
        "The old run made 68,000 commits in under two hours, about seventy times "
        "the new run's pace, but accumulated more than 70,000 merge conflicts.\n\n"
        "Run `mag build 'edition'` to reproduce.\n\n"
        "```shell\necho 'straight stays'\n```\n"
    )
    html = render_html_edition(_edition(tmp_path, manuscript=manuscript)).html

    assert (
        '<p class="standfirst">It’s become one of the most widely adopted '
        "internal tools since launching 3 months ago.</p>" in html
    )
    assert "seventy times the new run’s pace, but accumulated" in html
    assert "<code>mag build 'edition'</code>" in html
    assert "echo 'straight stays'" in html


def test_educate_reader_quotes_positional_rules():
    from magazine.reader_text import educate_reader_quotes

    for authored, educated in (
        # Possessives and contractions, including after numeral-adjacent words.
        ("the new run's pace", "the new run’s pace"),
        ("It's become", "It’s become"),
        ("the agents' consensus", "the agents’ consensus"),
        ("GPT-5.5's tokens", "GPT-5.5’s tokens"),
        # Paired quotes, single and double, with nesting.
        ('"quoted words"', "“quoted words”"),
        ("a 'case' study", "a ‘case’ study"),
        ('("aside")', "(“aside”)"),
        ('"\'nested\' words"', "“‘nested’ words”"),
        # Elision before a digit is the raised comma, not an opener.
        ("the '90s runs", "the ’90s runs"),
        # Already-real marks and quote-free text pass through untouched.
        ("It’s already “set” right", "It’s already “set” right"),
        ("no quotes at all", "no quotes at all"),
    ):
        assert educate_reader_quotes(authored) == educated, authored


def test_reader_folding_leaves_bracketed_prose_and_code_spans_alone(tmp_path: Path):
    manuscript = (
        "# Reader title\n\n"
        "Write `[label](target)` to link, and see [1] (below) for the “full” list…\n"
    )
    html = render_html_edition(_edition(tmp_path, manuscript=manuscript)).html

    assert "<code>[label](target)</code>" in html
    assert "see [1] (below) for the “full” list…" in html


def test_reader_folding_deliberately_outsets_the_reportlab_renderer():
    """One publication rule, two definitions -- and they no longer agree.

    ``render._plain`` folds through cp1252 because ReportLab writes through
    cp1252, and ``render.py`` has to keep producing the archived publication
    byte for byte.  The reader path folds to what the *bundled faces* can set,
    which is a different repertoire in both directions.  This pins the
    difference, so neither definition can drift into the other unnoticed.
    """
    # Still identical: nothing here is outside either repertoire.
    for sample in (
        "see [1] (below) and [bracketed] prose",
        "An em dash \u2014 and an accented caf\u00e9",
        "A non-breaking\u00a0space",
        "Beyond both: \u65e5\u672c\u8a9e",
        "",
    ):
        assert fold_reader_characters(sample) == _plain(sample), sample

    # Wider: every bundled face carries these, so the reader keeps them and
    # only the cp1252 path degrades them.
    for authored, degraded in (
        ("\u201cCurly\u201d quotes and \u2018single\u2019 ones", "\"Curly\" quotes and 'single' ones"),
        ("An ellipsis\u2026 and an arrow \u2192 onwards", "An ellipsis... and an arrow -> onwards"),
    ):
        assert fold_reader_characters(authored) == authored
        assert _plain(authored) == degraded

    # Narrower: cp1252 encodes a soft hyphen and Inter cannot set one, so the
    # reader refuses it visibly rather than letting a host font supply it.
    assert fold_reader_characters("soft\u00adhyphen") == "soft?hyphen"
    assert _plain("soft\u00adhyphen") == "soft\u00adhyphen"
    # U+25E6 is the nested-list marker the design refuses to set: Inter carries
    # it, the serif that sets prose does not, and a value cannot know its face.
    assert fold_reader_characters("nested \u25e6 marker") == "nested ? marker"


def test_every_printable_ascii_character_is_settable_by_every_bundled_face():
    """The premise of the fold's ASCII shortcut, asserted rather than assumed."""
    from magazine.reader_text import _settable_codepoints

    settable = _settable_codepoints()

    assert [chr(point) for point in range(0x20, 0x7F) if point not in settable] == []


def test_current_edition_languages_render_through_public_interface():
    root = Path(__file__).resolve().parents[1]
    editions = Magazine(root)._validate_languages("002-unreleased")

    assert set(editions) == {"en", "es"}
    for edition in editions.values():
        rendered = render_html_edition(edition)
        assert rendered.html.startswith("<!doctype html>")
        assert f'<html lang="{edition.locale}"' in rendered.html
        assert len(rendered.assets) >= sum(len(article.figures) for article in edition.articles)


def test_the_article_carries_one_working_link_back_to_its_primary_source(tmp_path: Path):
    """The semantic hook the printed code is rendered from.

    It is a link and not a code: what the edition knows is that this article was
    built from a source at a particular address, which is an editorial fact of
    the same kind as the source ids already printed at the opener.  How a print
    adapter that cannot be followed renders it is not expressible here and is not
    expressed here -- there is no size, no slot, no colour and no *name* in this
    output.  A localized `data-source-label` used to ride along for the printed
    square's caption; the caption is retired and so is the attribute, so the
    element is once more nothing but a destination.
    """
    result = render_html_edition(_edition(tmp_path))

    assert (
        '<a class="source-link" data-source-link="primary" data-source-id="source-one" '
        'href="https://example.test/source?a=1&amp;b=2">https://example.test/source?a=1&amp;b=2</a>'
    ) in result.html
    assert "data-source-label" not in result.html
    assert "Source / 01" not in result.html
    # One per article, from the first of its two source ids, and after the end
    # mark: the article's own coda, not a second provenance line.
    assert result.html.count('class="source-link"') == 1
    assert result.html.index('class="end-mark"') < result.html.index('class="source-link"')
    assert 'data-source-link="primary" data-source-id="source-two"' not in result.html


def test_an_article_whose_source_has_no_canonical_url_offers_no_link(tmp_path: Path):
    edition = _edition(tmp_path)
    without = replace(
        edition, articles=tuple(replace(a, source_url=None) for a in edition.articles)
    )

    assert "source-link" not in render_html_edition(without).html
    # And the editorial, which has no source at all, never had one.
    assert "source-link" not in render_html_edition(edition).html.split("<article")[0]


def test_a_bullet_separated_name_roster_is_stamped_and_prose_bullets_are_not(tmp_path: Path):
    """A paragraph of bullet-separated names carries ``data-name-roster``.

    The attribute states an editorial fact -- this block is a list of proper
    nouns set in paragraph clothing, like a signatories roster -- so a print
    stylesheet can keep the hyphenator out of names no dictionary knows.  The
    two prose paragraphs below each carry a bullet and must stay unstamped:
    one bullet yields only two segments, and prose around two bullets yields a
    segment longer than any name.
    """
    manuscript = (
        "# Reader title\n\n"
        "An opening paragraph of ordinary running prose.\n\n"
        "## Signatories\n\n"
        "DoorDash • The Linux Foundation • Prime Intellect • Y Combinator\n\n"
        "Running prose may quote one separator • and simply keep going.\n\n"
        "Alpha • a clause of well over six words is a sentence and not a name"
        " • Omega\n"
    )
    html = render_html_edition(_edition(tmp_path, manuscript=manuscript)).html

    assert (
        '<p data-name-roster="true">DoorDash • The Linux Foundation • '
        "Prime Intellect • Y Combinator</p>"
    ) in html
    assert html.count("data-name-roster") == 1


def test_the_name_roster_boundary_is_three_short_segments():
    """The roster rule's own boundary, stated segment by segment.

    Three or more bullet-separated segments, every one non-empty and at most
    six words: fewer segments is an incidental bullet in prose, a long segment
    is a clause, and an empty segment means the bullets are not separating
    names at all.
    """
    from magazine.html_edition import _is_name_roster

    assert _is_name_roster("AI21 • AMD • Meta")
    assert _is_name_roster(
        "American Innovators Network • Palo Alto Networks • Y Combinator"
    )
    # Two segments: one bullet quoted inside running prose.
    assert not _is_name_roster("A sentence with one • in the middle of it")
    # A seventh word makes a segment a clause rather than a name.
    assert _is_name_roster("Alpha • one two three four five six • Omega")
    assert not _is_name_roster("Alpha • one two three four five six seven • Omega")
    # A trailing or doubled bullet leaves an empty segment: not a roster.
    assert not _is_name_roster("Alpha • Beta • Gamma •")
    assert not _is_name_roster("Alpha •• Beta • Gamma")
    assert not _is_name_roster("No bullets here at all")
