"""The web adapter's contract: a self-contained, deterministic, styled page.

These tests exercise :mod:`magazine.web_edition` through its public seam,
:func:`write_web_edition`, against the same hostile fixture edition the
semantic HTML suite uses -- ids and titles full of markup metacharacters, a
cover and a figure sharing one source file -- because the web directory is
where every one of those properties finally meets a real filesystem and a
real browser.
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


@pytest.fixture(autouse=True)
def _stub_screen_css_when_unauthored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the screen stylesheet until it is authored.

    The stylesheet is its own piece of work; this suite tests the adapter's
    copy path, not the CSS.  When the packaged file exists the stub steps
    aside and the real bytes ship.
    """

    try:
        web_edition._read_screen_css()
    except ValidationError:
        monkeypatch.setattr(web_edition, "_read_screen_css", lambda: b"/* stub */\n")


def _screen_css_is_authored() -> bool:
    try:
        web_edition._read_screen_css()
    except ValidationError:
        return False
    return True


def test_the_web_directory_is_self_contained_and_every_src_resolves(tmp_path: Path):
    """No ``file:`` URI survives, and every ``src`` names a shipped file.

    Self-containment is the whole point of the adapter: the directory must be
    servable from any path and openable from the filesystem, so a single
    surviving absolute URI -- or a src whose target was never copied -- is a
    broken page on someone else's machine.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")
    html = result.index.read_text(encoding="utf-8")

    sources = re.findall(r'src="([^"]+)"', html)
    assert sources, "the fixture edition renders figures, tails and plates"
    for src in sources:
        assert not src.startswith("file:")
        assert (result.root / src).is_file(), src
    assert "file:" not in html


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


def test_the_head_gains_viewport_and_stylesheet_exactly_once_after_charset(tmp_path: Path):
    """The injected head is one viewport and one stylesheet link, in order.

    Both land inside ``<head>`` immediately after the charset declaration, and
    exactly once each: a doubled viewport is a browser quirk lottery, and a
    doubled stylesheet is a hint the injection anchor matched more than it
    should.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")
    html = result.index.read_text(encoding="utf-8")

    viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    stylesheet = '<link rel="stylesheet" href="edition.css">'
    assert html.count(viewport) == 1
    assert html.count(stylesheet) == 1
    head = html.split("</head>")[0]
    assert head.index('<meta charset="utf-8">') < head.index(viewport) < head.index(stylesheet)


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


def test_the_cover_leads_main_and_its_absence_leaves_no_plate(tmp_path: Path):
    """The cover plate is the first child of ``<main>``, or nothing at all.

    The semantic layer records the cover in its inventory but paints nothing,
    because placement is adapter policy; on screen the edition leads with it.
    An edition without cover art gets no empty frame.
    """

    edition = _edition(tmp_path)
    result = write_web_edition(edition, tmp_path / "web")
    lines = result.index.read_text(encoding="utf-8").split("\n")

    (main_index,) = [i for i, line in enumerate(lines) if line.lstrip().startswith("<main ")]
    plate = lines[main_index + 1]
    assert plate.startswith('    <figure class="cover-plate" data-asset-role="cover_art">')
    assert 'alt="Cover &lt;&amp;&gt;"' in plate

    without = replace(edition, cover_art=None)
    bare = write_web_edition(without, tmp_path / "web-bare")
    assert "cover-plate" not in bare.index.read_text(encoding="utf-8")


def test_fonts_licenses_and_stylesheet_ship_with_the_page(tmp_path: Path):
    """The bundled faces, their licenses, and ``edition.css`` are all present.

    Deterministic builds must not use system font lookups, on screen as in
    print, and the SIL licenses travel with the fonts they cover.
    """

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")

    assert (result.root / "edition.css").is_file()
    fonts = result.root / "fonts"
    assert list(fonts.rglob("*.ttf")), "the bundled faces ship with the page"
    assert [
        path for path in fonts.rglob("*") if path.name.lower().startswith("license")
    ], "the OFL texts travel with the fonts they cover"


@pytest.mark.skipif(
    not _screen_css_is_authored(), reason="assets/screen-edition.css not authored yet"
)
def test_the_shipped_stylesheet_is_the_packaged_one_byte_for_byte(tmp_path: Path):
    """``edition.css`` is the packaged screen stylesheet, unmodified."""

    result = write_web_edition(_edition(tmp_path), tmp_path / "web")
    assert (result.root / "edition.css").read_bytes() == web_edition._read_screen_css()


def test_two_builds_of_the_same_edition_are_byte_identical(tmp_path: Path):
    """Determinism: the same validated edition writes the same tree twice.

    No timestamps, no enumeration order, no randomness -- the property both
    print engines already contract to, holding on the web path as well.
    """

    edition = _edition(tmp_path)
    first = write_web_edition(edition, tmp_path / "first")
    second = write_web_edition(edition, tmp_path / "second")

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
