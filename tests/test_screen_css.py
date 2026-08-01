"""The screen stylesheet's contract with the semantic edition.

``screen-edition.css`` is the web adapter's stylesheet, and its whole surface
is the vocabulary ``render_html_edition`` emits: a class or ``data-*`` hook
styled here that nothing emits is a stale rule waiting to mislead the next
reader, so the first test extracts every selector the sheet uses and demands
the semantic HTML actually produce it.  The remaining tests hold the sheet's
only external references -- the bundled font files -- to the packaged assets
they resolve against, licenses included, and to the no-network rule the whole
publication builds under.
"""

from __future__ import annotations

from dataclasses import replace
import re
from importlib import resources
from pathlib import Path

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

_ASSETS = resources.files("magazine").joinpath("assets")

# Vocabulary the stylesheet may use that the semantic layer deliberately does
# not emit -- all of it the web adapter's (web_edition.py) own page chrome.
# The ``cover`` family is the native cover block (`_cover_lines`): the
# lockup, headline, framed artwork, contributor register, spaced date, and
# the ``canto`` strip translating the printed fore-edge tab; ``cover-art``
# also stands alone as the wordmark-less fallback figure.  ``masthead`` (and
# its lockup image) heads every piece page with the way back to the cover;
# the ``page-turn`` trio is the previous/next spine between piece pages.
_SCREEN_ONLY_CLASSES = frozenset(
    {
        "cover", "cover-wordmark", "cover-headline", "cover-headline-line",
        "cover-art", "cover-roster", "cover-date", "cover-cue",
        "canto", "canto-issue", "canto-identity",
        "masthead", "masthead-wordmark",
        "page-turn", "page-turn-previous", "page-turn-contents", "page-turn-next",
        "colophon", "colophon-identity", "colophon-links",
        "colophon-sibling", "colophon-language", "colophon-date",
        "provenance-source", "figure-link", "opener-source-link", "source-qr",
    }
)


def _screen_css() -> str:
    return _ASSETS.joinpath("screen-edition.css").read_text(encoding="utf-8")


def _selector_preludes(css: str) -> list[str]:
    """Every selector text in ``css``, at-rule preludes excluded.

    A tiny brace-walk rather than a CSS parser: whatever text accumulates
    since the last ``{``, ``}`` or ``;`` is the prelude of the block a ``{``
    opens.  Nesting (``@media``) falls out naturally, ``@font-face`` and
    ``@media`` preludes are skipped by their ``@``, and declarations are the
    text a ``}`` discards.
    """

    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    preludes: list[str] = []
    current: list[str] = []
    for character in stripped:
        if character == "{":
            prelude = "".join(current).strip()
            current.clear()
            if prelude and not prelude.startswith("@"):
                preludes.append(prelude)
        elif character in "};":
            current.clear()
        else:
            current.append(character)
    return preludes


def _edition(tmp_path: Path) -> Edition:
    """A fixture edition that exercises the sheet's whole vocabulary.

    The manuscript deliberately carries the two content-derived stamps the
    sheet styles by attribute -- a bullet-separated name roster and a list
    under a references heading -- alongside the ordinary prose blocks, and
    the edition carries every optional element with a class of its own:
    subtitle, editorial, author note, opener and anchored figures, tail art,
    source link, section and closing plate.
    """

    article_path = tmp_path / "article.md"
    article_path.write_text(
        "---\nlabel: FAITHFUL SYNTHESIS\n---\n"
        "An opening paragraph with a [working link](https://example.test/a) and `code`.\n\n"
        "# Reader title\n\n"
        "> A quoted line.\n\n"
        "- First point\n\n"
        "## Exact anchor\n\n"
        "After the anchor.\n\n"
        "DoorDash • The Linux Foundation • Y Combinator\n\n"
        "```python\nprint('café')\n```\n\n"
        "## References\n\n"
        "- 1 — Example, *A cited title*, 2026.\n",
        encoding="utf-8",
    )
    editorial_path = tmp_path / "editorial.md"
    editorial_path.write_text(
        "---\ntitle: Editorial\n---\nEditorial standfirst prose.", encoding="utf-8"
    )
    section_path = tmp_path / "section.md"
    section_path.write_text("## Section detail\n\nSection body.", encoding="utf-8")
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"image")
    tail_path = tmp_path / "tail.png"
    tail_path.write_bytes(b"tail")
    plate_path = tmp_path / "plate.png"
    plate_path.write_bytes(b"plate")
    figure = Figure(
        id="exact-figure", source_id="source-one", asset_id="asset", path=image_path,
        caption="Caption", credit="Credit", alt_text="Alt",
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
        id="article-one", title="Article one", short_title="Article", display_emphasis="",
        opener_variant="edge_medallion", author="An Author", author_note="Writes here.",
        source_ids=("source-one", "source-two"), source_pins=(),
        manuscript=article_path, content_mode="faithful_synthesis",
        figures=(opener, figure), tail_art=tail_path,
        source_url="https://example.test/source",
        opener_art=ArticleOpenerArt(
            image_path,
            "A boy and robot inspect a system.",
            "Original illustration.",
        ),
    )
    return Edition(
        id="edition-one", publication_name="Magazine", issue_number="7", title="Issue seven",
        publication_date="2026-07-28", language="en", locale="en",
        editorial=Editorial(editorial_path, "Editorial", "The Editors", "ORIGINAL"),
        articles=(article,), sections=(Section("source_record", "Sources", section_path),),
        cover={"headline": "Cover"}, cover_art=image_path,
        closing_plates=(ClosingPlate("Plate", plate_path),),
        raw={
            "subtitle": "A subtitle",
            "format": {"article_opener": "illustrated_paper_spots_v1"},
        },
    )


def test_every_selector_the_screen_sheet_styles_is_emitted_vocabulary(tmp_path: Path):
    """Each class and ``data-*`` hook in the CSS exists in the semantic HTML.

    The sheet's contract runs one way: html_edition.py owes it nothing, so
    the sheet must style only what is actually emitted.  Screen-only
    vocabulary is a named allowlist, not a loophole -- each entry states the
    adapter that emits it.
    """

    preludes = " ".join(_selector_preludes(_screen_css()))
    styled_classes = set(re.findall(r"\.(-?[A-Za-z_][\w-]*)", preludes))
    styled_data_attributes = set(re.findall(r"\[\s*(data-[\w-]+)", preludes))
    assert styled_classes and styled_data_attributes  # The extraction itself works.

    illustrated = _edition(tmp_path)
    # The legacy opener also carries the other closing object: an article may
    # declare key ideas or tail art, never both, so one variant has to be the
    # one that closes on the box if the sheet is to be held to it at all.
    legacy = replace(
        illustrated,
        articles=(
            replace(
                illustrated.articles[0],
                opener_art=None,
                tail_art=None,
                key_ideas=(
                    "One host can drive several servers without merging them.",
                    "A server states what it can do; the host decides when.",
                ),
            ),
        ),
        raw={"subtitle": "A subtitle"},
    )
    html = (
        render_html_edition(illustrated).html
        + render_html_edition(legacy).html
    )
    emitted_classes = {
        token
        for value in re.findall(r'class="([^"]*)"', html)
        for token in value.split()
    }
    emitted_data_attributes = set(re.findall(r'(data-[\w-]+)="', html))

    unknown_classes = styled_classes - emitted_classes - _SCREEN_ONLY_CLASSES
    assert not unknown_classes, f"CSS styles classes nothing emits: {sorted(unknown_classes)}"
    unknown_attributes = styled_data_attributes - emitted_data_attributes
    assert not unknown_attributes, (
        f"CSS styles data attributes nothing emits: {sorted(unknown_attributes)}"
    )


def test_every_css_url_is_a_local_font_the_package_ships():
    """Each ``url(...)`` resolves to a bundled font file; none leaves the disk.

    The adapter copies ``src/magazine/assets/fonts/`` to ``fonts/`` beside
    ``index.html`` preserving relative structure, so a ``fonts/<rest>`` URL in
    the sheet is exactly ``assets/fonts/<rest>`` in the package.  A URL with a
    scheme would be a network fetch inside a publication that promises never
    to make one.
    """

    urls = [
        url.strip("'\"")
        for url in re.findall(r"url\(\s*([^)]+?)\s*\)", _screen_css())
    ]
    assert urls, "The sheet must embed the bundled faces via @font-face."
    for url in urls:
        assert not re.match(r"^(https?:|data:|//)", url), f"Non-local url: {url}"
        assert url.startswith("fonts/"), f"URL outside the copied fonts tree: {url}"
        packaged = _ASSETS.joinpath("fonts").joinpath(url.removeprefix("fonts/"))
        assert packaged.is_file(), f"CSS references a font the package does not ship: {url}"


def test_illustrated_opener_uses_white_paper_and_locked_spot_marks():
    css = _screen_css()

    assert ":root {" in css
    assert "--paper: #f1eadb;" in css
    assert "--orange: #ff5a1f;" in css
    assert "--rule: rgba(17, 19, 26, 0.18);" in css
    assert 'html[data-article-opener-format="illustrated_paper_spots_v1"]' in css
    assert "--paper: #ffffff;" in css
    assert "--cobalt: #315d8c;" in css
    assert "--orange: #f05738;" in css
    assert "--rule: #c8c0b3;" in css
    assert "aspect-ratio: 348 / 203;" in css
    assert "box-shadow: 0.3125rem 0.3125rem 0 var(--orange);" in css
    assert "border-bottom: 1px solid var(--rule);" in css
    assert ".opener-tick {" in css
    assert "width: 18px;" in css and "height: 3px;" in css
    assert ".opener-meta::before" not in css
    assert ".article-opener > .standfirst::first-letter" in css
    assert "grid-template-columns: minmax(0, 1fr) auto;" in css
    assert "grid-column: 1;" in css and "grid-column: 2;" in css


def test_the_font_licenses_ship_beside_the_faces_they_cover():
    """Both SIL OFL texts live in the packaged font tree the adapter copies.

    The web output redistributes the font binaries, and the OFL's condition
    is that its text travels with them; the adapter copies the tree whole, so
    shipping the licenses here is what puts them in every web edition.
    """

    assert _ASSETS.joinpath("fonts", "inter", "LICENSE.txt").is_file()
    assert _ASSETS.joinpath("fonts", "source-serif-4", "LICENSE.md").is_file()
