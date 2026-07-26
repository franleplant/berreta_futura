from dataclasses import replace
from pathlib import Path

from magazine import Magazine
from magazine.html_edition import render_html_edition
from magazine.manifest import Article, ClosingPlate, Edition, Editorial, Section
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
    assert ">Número 7</p>" in html
    assert '<nav aria-label="Índice" data-edition-navigation="contents">' in html
    assert "<h2>Índice</h2>" in html
    assert ">Fuentes: " in html
    assert "café" in html


def test_reader_folding_cannot_terminate_an_attribute_value(tmp_path: Path):
    """A folded curly double quote is an ASCII quote, so folding must precede escaping.

    Every interpolated attribute below carries authored prose, so folding the
    assembled document instead would have produced malformed markup.
    """
    edition = _edition(tmp_path)
    titled = replace(edition.articles[0], title="The “Dark” Factory’s ‘case’ study…")
    html = render_html_edition(replace(edition, articles=(titled,))).html

    assert "<h1>The \"Dark\" Factory's 'case' study...</h1>" in html
    assert (
        'alt="Tail art for The &quot;Dark&quot; Factory&#x27;s &#x27;case&#x27; study..."'
        in html
    )
    assert 'href="#article-article&lt;&amp;&gt;"' in html
    assert '<img src="' in html and 'alt="Alt &lt;&amp;&gt;"' in html


def test_reader_folding_leaves_bracketed_prose_and_code_spans_alone(tmp_path: Path):
    manuscript = (
        "# Reader title\n\n"
        "Write `[label](target)` to link, and see [1] (below) for the “full” list…\n"
    )
    html = render_html_edition(_edition(tmp_path, manuscript=manuscript)).html

    assert "<code>[label](target)</code>" in html
    assert 'see [1] (below) for the "full" list...' in html


def test_reader_folding_agrees_with_the_reportlab_renderer_on_link_free_text():
    """One publication rule, two definitions until the migration lands.

    ``render._plain`` folds the same characters and then also strips markdown
    links, which is why the reader path cannot reuse it.  Until ``render`` is
    deduplicated against :mod:`magazine.reader_text` this pins the two together
    on every input where the markdown clause is inert.
    """
    samples = (
        "“Curly” quotes and ‘single’ ones",
        "An ellipsis… and an arrow → onwards",
        "A non-breaking space",
        "see [1] (below) and [bracketed] prose",
        "An em dash — and an accented café",
        "Outside cp1252: 日本語",
        "",
    )
    for sample in samples:
        assert fold_reader_characters(sample) == _plain(sample), sample


def test_current_edition_languages_render_through_public_interface():
    root = Path(__file__).resolve().parents[1]
    editions = Magazine(root)._validate_languages("002-unreleased")

    assert set(editions) == {"en", "es"}
    for edition in editions.values():
        rendered = render_html_edition(edition)
        assert rendered.html.startswith("<!doctype html>")
        assert f'<html lang="{edition.locale}"' in rendered.html
        assert len(rendered.assets) >= sum(len(article.figures) for article in edition.articles)
