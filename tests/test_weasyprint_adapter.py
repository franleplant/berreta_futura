from __future__ import annotations

import re
import sys
import zlib
from collections.abc import Mapping
from dataclasses import replace
from importlib import resources
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from PIL import Image

import magazine.weasyprint_adapter as adapter
from magazine.errors import ValidationError
from magazine.html_edition import HtmlAsset, render_html_edition
from magazine.manifest import Edition
from magazine.reader_layout import RenderLayout
from magazine.weasyprint_adapter import (
    WEASYPRINT_DESIGN,
    _apply_source_codes,
    _apply_tail_arts,
    _configure_macos_library_path,
    _content_page_count,
    _figure_placement,
    _limit_closing_plates,
    _measure_layout,
    _measured_tail_art,
    _read_print_css,
    _render_to_signature,
    _rewrite_landscape_plates,
    _rotated_plate_box,
    _signature_closing_plates,
    _validate_caps,
    _validate_cover_slots,
    _validate_contents_page,
    _validate_layout_caps,
    _weasyprint_types,
    _with_print_slots,
    render_a5_weasyprint,
)
from test_html_edition import _edition

_PAGE_HEIGHT_POINTS = 595.2756
_POINTS_PER_CSS_PIXEL = 72 / 96
_FILLER_PROSE = " ".join(["alpha bravo charlie delta echo foxtrot golf hotel"] * 200)
# The nested-bullet marker U+25E6 is in neither bundled face, so a nested list
# would make Pango fall back to a host font for reasons unrelated to @font-face.
_FONT_SAFE_MANUSCRIPT = (
    "---\nlabel: FAITHFUL SYNTHESIS\n---\n"
    "# Reader title\n\nAn *emphasis*, **strong phrase** and `[label](target)`.\n\n"
    "> A quoted line.\n\n- First\n- Second\n\n"
    "## Exact anchor\n\nAfter the anchor, with “curly quotes”, an ellipsis… and an arrow →.\n"
)


class _Element:
    def __init__(self, tag: str, **attributes: str):
        self.tag = tag
        self.attrib = attributes

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.attrib.get(name, default)


class _Box:
    def __init__(self, tag: str | None = None, *, element: _Element | None = None,
                 children: tuple["_Box", ...] = (), x: float = 0, y: float = 0,
                 width: float = 0, height: float = 0, text: str | None = None):
        self.element_tag = tag
        self.element = element
        self.children = children
        if text is not None:
            # WeasyPrint sets `text` on `TextBox` and on nothing else, which is
            # what `_measured_flow_positions` keys on.
            self.text = text
        self.position_x = x
        self.position_y = y
        self.width = width
        self.height = height

    # WeasyPrint's `position_*` is the margin box corner while `width`/`height`
    # are the content box; these stubs carry no margins, so the two coincide.
    def content_box_x(self) -> float:
        return self.position_x

    def content_box_y(self) -> float:
        return self.position_y

    def padding_box_x(self) -> float:
        return self.position_x

    def padding_box_y(self) -> float:
        return self.position_y

    def margin_height(self) -> float:
        return self.height


# `_measured_byline_baselines` and friends key on WeasyPrint's own class
# names, so the stand-ins carry them.
_BlockBox = type("BlockBox", (_Box,), {})
_LineBox = type("LineBox", (_Box,), {})


def _stub_byline(article_id: str, *, y: float = 150.0, baseline: float = 2.0) -> _Box:
    """A laid-out opener byline: the anchor the code's `top` is measured off."""
    line = _LineBox("p", y=y, height=0)
    line.baseline = baseline
    return _BlockBox(
        "p", element=_Element("p", **{"class": "byline"}), children=(line,), y=y
    )


class _Page:
    def __init__(self, box: _Box, *, named: str | None = None):
        self._page_box = box
        self._page_box.page_type = type("PageType", (), {"name": named})()


class _Document:
    def __init__(self, pages: tuple[_Page, ...]):
        self.pages = pages

    def write_pdf(self, **_kwargs: object) -> bytes:
        return b"%PDF-1.7\n%%EOF\n"


def _raster_edition(tmp_path: Path, **kwargs: object) -> Edition:
    """The synthetic edition with readable rasters, so preflight can measure it.

    Its closing plates are filled out to three because the signature arithmetic --
    not the inventory -- decides how many a reader needs, and a shortfall is a hard
    error in both pipelines rather than a blank filler page.
    """
    edition = _edition(tmp_path, **kwargs)
    _write_rasters(tmp_path)
    plate = edition.closing_plates[0]
    return replace(
        edition,
        closing_plates=tuple(
            replace(plate, title=f"{plate.title} {index}") for index in range(1, 4)
        ),
    )


def _write_rasters(tmp_path: Path) -> None:
    """Rasters the reader will actually accept where it places them.

    `figure.png` is wide enough to clear MIN_FIGURE_PPI across the full
    333.0079pt live width, which is where an evidence band puts it: the reader
    refuses a placement under 300 ppi, so a fixture that under-resolves is a
    fixture the reader would reject rather than a smaller test.
    """
    for name, size in (("figure.png", (1600, 800)), ("tail.png", (2048, 1024)),
                       ("plate.png", (900, 1200))):
        Image.new("RGB", size, "white").save(tmp_path / name)


def _stub_reader_document(
    assets: tuple[HtmlAsset, ...],
    article_id: str = "article<&>",
    *,
    painted: Mapping[str, tuple[float, float, float, float]] | None = None,
) -> _Document:
    """A four-page stand-in that satisfies every structural reader assertion.

    It carries an article box with real extent so the tail-ornament slack the
    adapter measures has something to measure, and no closing-plate box, so the
    signature arithmetic reads the trailing cover slots as the content boundary.

    A curated figure's image sits inside a ``figure`` box carrying its
    ``data-figure-id``, because that is the only shape ``_painted_reader``
    accepts: a reader whose semantic HTML declares curated figures and whose
    layout has no figure image boxes is exactly the silent frame loss that guard
    exists to refuse.  ``painted`` adds the frame each figure earned, in points
    from the figure's own corner, so the double can stand in for the paint pass.
    """
    contents = _Box("nav", element=_Element("nav", **{"data-edition-navigation": "contents"}))
    article = _Box(
        "article",
        element=_Element("article", **{"data-article-id": article_id}),
        children=(_stub_byline(article_id),),
        x=0, y=100, width=400, height=100,
    )
    figures: list[_Box] = []
    for asset in assets:
        if asset.role not in {"figure", "article_tail", "closing_plate"}:
            continue
        image = _Box("img", element=_Element("img", src=asset.src), x=0, y=0, width=100, height=50)
        if asset.role != "figure":
            figures.append(image)
            continue
        children = [image]
        rule = (painted or {}).get(str(asset.figure_id))
        if rule is not None:
            left, top, width, height = (value / _POINTS_PER_CSS_PIXEL for value in rule)
            children.append(
                _Box(
                    "img",
                    element=_Element("img", **{"class": "figure-rule"}),
                    x=left, y=top, width=width, height=height,
                )
            )
        figures.append(
            _Box(
                "figure",
                element=_Element("figure", **{"data-figure-id": str(asset.figure_id)}),
                children=tuple(children),
            )
        )
    return _Document((
        _Page(_Box(), named="outer-cover"),
        _Page(_Box(), named="inside-cover"),
        _Page(_Box(children=(contents, article, *figures)), named="inside-cover"),
        _Page(_Box(), named="outer-cover"),
    ))


def _painted_rule_boxes(tree) -> dict[str, tuple[float, float, float, float]]:
    """Every frame ``_apply_figure_rules`` wrote into ``tree``, read back in points."""
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for figure in tree.iter("figure"):
        for image in figure.iter("img"):
            if image.get("class") != "figure-rule":
                continue
            style = dict(
                (part.split(":", 1)[0].strip(), part.split(":", 1)[1].strip())
                for part in image.get("style").split(";")
            )
            boxes[figure.get("data-figure-id")] = tuple(
                float(style[name].removesuffix("pt")) for name in ("left", "top", "width", "height")
            )
    return boxes


def _base_fonts(pdf: Path) -> set[str]:
    from pypdf import PdfReader

    fonts: set[str] = set()
    for page in PdfReader(str(pdf)).pages:
        resources_dict = (page.get("/Resources") or {})
        font_dict = resources_dict.get("/Font") or {}
        if hasattr(font_dict, "get_object"):
            font_dict = font_dict.get_object()
        for value in font_dict.values():
            value = value.get_object()
            for candidate in (value, *(child.get_object() for child in value.get("/DescendantFonts") or [])):
                if candidate.get("/BaseFont"):
                    fonts.add(str(candidate["/BaseFont"]))
    return fonts


def _line_boxes(box: object):
    if type(box).__name__ == "LineBox":
        yield box
        return
    for child in getattr(box, "children", ()) or ():
        yield from _line_boxes(child)


def _baseline_from_page_foot(line: object) -> float:
    return _PAGE_HEIGHT_POINTS - (
        float(line.position_y) + float(line.baseline)
    ) * _POINTS_PER_CSS_PIXEL


def _translated_down(*boxes: object) -> float:
    """How far ``boxes`` are painted below where they were laid out, in points.

    The stylesheet corrects every baseline whose own first-baseline offset is not
    the body's with a ``translateY``, which WeasyPrint applies when it draws and
    never during layout -- so a laid-out ``position_y`` is the *flow* position and
    the reader's baseline is this much further down.
    """
    total = 0.0
    for box in boxes:
        for name, arguments in box.style["transform"]:
            if name == "translate":
                total += float(arguments[1].value)
    return total * _POINTS_PER_CSS_PIXEL


def _painted_baseline_from_page_foot(line: object, *boxes: object) -> float:
    """``_baseline_from_page_foot`` with the paint corrections of ``boxes``."""
    return _baseline_from_page_foot(line) - _translated_down(*boxes)


def _block_of(page: object, tag: str) -> object:
    return next(
        box
        for box in adapter._walk_boxes(page._page_box)
        if getattr(box, "element_tag", None) == tag and type(box).__name__ == "BlockBox"
    )


def _block_by_class(page: object, name: str) -> object:
    return next(
        box
        for box in adapter._walk_boxes(page._page_box)
        if type(box).__name__ == "BlockBox"
        and getattr(box, "element", None) is not None
        and name in adapter._element_classes(box.element)
    )


def _typeset_document(body: str, *, css_text: str | None = None):
    """Lay out a synthetic document with the bundled print stylesheet."""
    HTML, CSS, FontConfiguration = _weasyprint_types()
    font_config = FontConfiguration()
    stylesheet = CSS(
        string=_read_print_css() if css_text is None else css_text,
        base_url=resources.files("magazine").joinpath("assets").as_uri() + "/",
        font_config=font_config,
    )
    return HTML(
        string=f'<main data-edition-id="metrics">{body}</main>',
        base_url=Path.cwd().as_uri() + "/",
    ).render(stylesheets=[stylesheet], font_config=font_config)


def _semantic(edition: Edition) -> str:
    return render_html_edition(edition).html


def _print_tree(edition: Edition):
    """The parsed print document, exactly as ``_lay_out`` obtains it."""
    HTML, _CSS, _FontConfiguration = _weasyprint_types()
    return HTML(
        string=_with_print_slots(_semantic(edition)), base_url=Path.cwd().as_uri() + "/"
    ).etree_element


def _parse_article_fragment(
    inner: str,
    *,
    plates: int = 0,
    credit: bool = False,
    header: str | None = None,
    author: str = "Author",
    note: str = "",
):
    HTML, _CSS, _FontConfiguration = _weasyprint_types()
    plate_markup = "".join(
        f'<figure class="closing-plate" data-closing-plate="{index + 1}">'
        f'<img src="p{index}"><figcaption>Plate</figcaption></figure>'
        for index in range(plates)
    )
    # The opener credit block the code is set beside.  Built only when a test
    # asks, so the fragment tests of other passes stay minimal.
    header_markup = header
    if header_markup is None and credit:
        note_markup = f'<p class="author-note">{note}</p>' if note else ""
        header_markup = (
            "<header><h1>Title</h1>"
            f'<p class="byline"><span class="byline-prefix">By</span> {author}</p>'
            f"{note_markup}</header>"
        )
    # The anchor `html_edition` writes after the end mark.  The print adapter
    # reads nothing off it -- the code's URL comes from the edition -- and it is
    # here because the real markup has it.
    link = (
        '<a class="source-link" data-source-link="primary" '
        'href="https://example.test/a">https://example.test/a</a>'
        if credit
        else ""
    )
    return HTML(
        string=(
            '<!doctype html><html><body><main data-edition-id="edition">'
            f'<article id="article-article" data-article-id="article">'
            f"{header_markup or ''}{inner}{link}</article>"
            f"{plate_markup}</main></body></html>"
        ),
        base_url=Path.cwd().as_uri() + "/",
    ).etree_element


def _content_streams(pdf: bytes) -> bytes:
    """Every decompressed stream of a PDF, so operators can be asserted on."""
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        raw = match.group(1)
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            continue
        streams.append(raw)
    return b"\n".join(streams)


def _line_boxes_of(page: object, tag: str) -> list[object]:
    return [
        box
        for box in adapter._walk_boxes(page._page_box)
        if type(box).__name__ == "LineBox" and getattr(box, "element_tag", None) == tag
    ]


def _typeset(body: str, *, css_text: str | None = None) -> list[tuple[int, float | None, float | None]]:
    """Per page: page-body line boxes, first body baseline, folio baseline.

    Baselines are points above the page's foot.  The folio's page number is the
    ``@bottom-right`` half of the pair; its ``@bottom-left`` half is the
    publication's name, which a synthetic body does not set.
    """
    document = _typeset_document(body, css_text=css_text)
    measured = []
    for page in document.pages:
        body_lines: list[object] = []
        folio: float | None = None
        for child in page._page_box.children:
            if getattr(child, "at_keyword", None) == "@bottom-right":
                folio_lines = list(_line_boxes(child))
                folio = _baseline_from_page_foot(folio_lines[0]) if folio_lines else None
            elif not getattr(child, "at_keyword", None):
                body_lines.extend(_line_boxes(child))
        measured.append((
            len(body_lines),
            _baseline_from_page_foot(body_lines[0]) if body_lines else None,
            folio,
        ))
    return measured


def _page_chrome(document: object) -> list[dict[str, str]]:
    """Per page: the text of every generated margin box, keyed by at-keyword."""
    chrome: list[dict[str, str]] = []
    for page in document.pages:
        boxes: dict[str, str] = {}
        for child in page._page_box.children:
            keyword = getattr(child, "at_keyword", None)
            if not keyword:
                continue
            text = "".join(
                getattr(box, "text", "")
                for box in adapter._walk_boxes(child)
                if type(box).__name__ == "TextBox"
            )
            boxes[keyword] = text
        chrome.append(boxes)
    return chrome


def _image_asset(tmp_path: Path) -> HtmlAsset:
    path = tmp_path / "figure.png"
    Image.new("RGB", (1200, 600), "white").save(path)
    return HtmlAsset(
        id="figure-article-diagram", role="figure", path=path, src=path.as_uri(),
        alt_text="diagram", article_id="article", figure_id="diagram", source_id="source",
        caption="Caption", credit="Credit", rights_status="author_owned",
    )


def test_print_slots_are_deterministic_and_keep_semantic_html_separate(tmp_path: Path):
    semantic = render_html_edition(_edition(tmp_path)).html
    first = _with_print_slots(semantic)
    assert first == _with_print_slots(semantic)
    assert 'class="outer-cover-slot"' not in semantic
    assert first.count('class="outer-cover-slot"') == 1
    assert first.count('class="inside-cover-slot"') == 1
    assert first.count('class="inside-back-cover-slot"') == 1
    assert first.count('class="back-cover-slot"') == 1
    assert first.index('class="outer-cover-slot"') < first.index('class="inside-cover-slot"')
    assert "café" in first
    assert 'href="https://example.test/a?x=1&amp;y=2"' in first
    # A blank filler page is banned outright: the signature is closed by closing
    # plates, so no print slot may introduce one.
    assert "signature-pad" not in first


def test_bundled_css_uses_only_local_fonts_and_a5_named_pages():
    css = _read_print_css()
    assert "@page" in css and "148mm 210mm" in css
    assert "@page outer-cover" in css and "@page inside-cover" in css
    assert "@page closing-plate" in css
    assert "target-counter(attr(href), page, decimal-leading-zero)" in css
    assert "http://" not in css and "https://" not in css
    assert 'url("fonts/source-serif-4/SourceSerif4SmText-Regular.ttf")' in css
    assert 'url("fonts/inter/Inter-Regular.ttf")' in css


def test_named_blank_cover_slots_are_required_at_reader_edges():
    pages = tuple(_Page(_Box(), named=name) for name in (
        "outer-cover", "inside-cover", "inside-cover", "outer-cover",
    ))
    _validate_cover_slots(_Document(pages))
    bad_pages = tuple(_Page(_Box(), named=name) for name in (
        "outer-cover", "interior", "inside-cover", "outer-cover",
    ))
    with pytest.raises(ValidationError, match="cover placeholders"):
        _validate_cover_slots(_Document(bad_pages))


def test_contents_must_be_on_logical_page_three():
    contents = _Box("nav", element=_Element("nav", **{"data-edition-navigation": "contents"}))
    _validate_contents_page(_Document((_Page(_Box()), _Page(_Box()), _Page(_Box(children=(contents,))))))
    with pytest.raises(ValidationError, match="page 3"):
        _validate_contents_page(_Document((_Page(_Box()), _Page(_Box()), _Page(_Box()))))


def test_closing_plate_count_is_the_signature_arithmetic_of_where_content_ended(tmp_path: Path):
    """`back_cover` (render.py:2198-2209), rederived from a laid-out reader.

    The plates are what closes the fold, so the count is a function of the last
    content page: reserve the two trailing cover slots, round up to four, fill the
    difference.  A configured `format.target_pages` replaces the rounding.
    """
    edition = replace(_edition(tmp_path), raw={})
    assert [_signature_closing_plates(edition, pages) for pages in (28, 29, 30, 31, 32)] == [
        2, 1, 0, 3, 2
    ]
    pinned = replace(edition, raw={"format": {"target_pages": 40}})
    assert _signature_closing_plates(pinned, 31) == 7


def test_reader_pages_up_to_the_first_closing_plate_are_the_content_pages():
    plate = _Box("figure", element=_Element("figure", **{"class": "closing-plate"}))
    with_plates = _Document(tuple(
        _Page(_Box(children=(plate,) if index >= 3 else ()))
        for index in range(6)
    ))
    assert _content_page_count(with_plates) == 3
    # With no plate to mark the boundary the trailing cover slots mark it instead.
    assert _content_page_count(_Document(tuple(_Page(_Box()) for _ in range(6)))) == 4


def test_the_tail_ornament_is_earned_by_open_space_and_centred_when_capped(tmp_path: Path):
    """The ornament is a property of where an article's flow ended and of nothing
    else: a band between the end mark's 31pt clearance and a 24pt foot inset,
    printed wherever that room reaches the 96pt the render critic calls a void
    (`_TAIL_ORNAMENT_MIN_HEIGHT`), never taller than 214pt -- and *centred* in
    its room when that cap bites, half the surplus below and half above, instead
    of pooling the whole surplus over its own head.
    """
    _write_rasters(tmp_path)
    article = SimpleNamespace(id="article", tail_art=tmp_path / "tail.png")

    # Room is `endmark_baseline - 31 - 69`; the floor is the critic's own 96.
    assert _measured_tail_art(article, 197.0) == adapter.TailBand(96.0, 0.0)
    assert _measured_tail_art(article, 196.0) is None
    # A band under the cap fills its room exactly, so it earns no lift at all.
    assert _measured_tail_art(article, 280.0) == adapter.TailBand(179.0, 0.0)
    # A very high ending is capped at the ornament's own maximum and centred:
    # room is 399, so the 185 of surplus splits into two 92.5pt margins.
    assert _measured_tail_art(article, 500.0) == adapter.TailBand(214.0, 92.5)
    # A tight page prints no motif, and an undeclared one never does.
    assert _measured_tail_art(article, 150.0) is None
    assert _measured_tail_art(SimpleNamespace(id="a", tail_art=None), 500.0) is None
    # The committed raster must resolve at 300 ppi across the crop-filled band.
    Image.new("RGB", (400, 200), "white").save(tmp_path / "soft.png")
    soft = SimpleNamespace(id="article", tail_art=tmp_path / "soft.png")
    with pytest.raises(ValidationError, match="ppi"):
        _measured_tail_art(soft, 500.0)


def test_tail_arts_print_at_their_measured_band_or_not_at_all():
    """`_apply_tail_arts` keeps the figure only where the page earned it, and
    states the whole band: the height, and the foot -- the stylesheet's own
    13.9954pt constant plus whatever lift centres a max-capped band."""
    markup = '<figure class="article-tail" data-asset-role="article_tail"><img src="c"></figure>'

    earned = _parse_article_fragment(markup)
    _apply_tail_arts(earned, {"article": adapter.TailBand(179.0, 0.0)})
    figure = next(iter(earned.iter("figure")))
    assert figure.get("style") == "height: 179.0000pt; bottom: 13.9954pt"

    centred = _parse_article_fragment(markup)
    _apply_tail_arts(centred, {"article": adapter.TailBand(214.0, 92.5)})
    figure = next(iter(centred.iter("figure")))
    assert figure.get("style") == "height: 214.0000pt; bottom: 106.4954pt"

    unearned = _parse_article_fragment(markup)
    _apply_tail_arts(unearned, {})
    assert list(unearned.iter("figure")) == []


def test_the_tail_art_ledger_accounts_for_every_article_and_names_the_shortfall():
    """`layout.tail_arts`, row for row: declared, printed, height, drop reason.

    A dropped ornament used to be `article.remove(figure)` and no record
    anywhere; the ledger is the record, and the render critic's own
    `tail-art-dropped` contract is its consumer, so the shape here is the
    contract's -- one row per article, exactly these five keys.
    """
    printed = SimpleNamespace(id="printed", tail_art=Path("printed.png"))
    dropped = SimpleNamespace(id="dropped", tail_art=Path("dropped.png"))
    bare = SimpleNamespace(id="bare", tail_art=None)
    edition = SimpleNamespace(articles=(printed, dropped, bare))
    # Only a *dropped* declaration re-measures its page; the printed row comes
    # from the settled plan, so the stub document carries just the low ending.
    low = _Box(
        "article",
        element=_Element("article", **{"data-article-id": "dropped"}),
        y=500, height=80, width=400,
    )
    document = _Document((_Page(_Box(children=(low,))),))
    plan = adapter.ReaderPlan(closing_plates=0, tail_arts=(("printed", 214.0, 60.0),))

    rows = adapter._tail_art_ledger(document, edition, plan)

    assert [sorted(row) for row in rows] == [
        ["article", "declared", "drop_reason", "height_points", "printed"]
    ] * 3
    assert rows[0] == {
        "article": "printed", "declared": True, "printed": True,
        "height_points": 214.0, "drop_reason": None,
    }
    room = adapter._tail_art_room(adapter._article_flow_bottom(document, "dropped"))
    assert room < adapter._TAIL_ORNAMENT_MIN_HEIGHT
    assert rows[1]["article"] == "dropped"
    assert rows[1]["declared"] and not rows[1]["printed"]
    assert rows[1]["height_points"] is None
    # The reason names the measured shortfall, not a shrug: the room, its two
    # bounds, and the floor the room fell under.
    assert f"{room:.1f}pt" in rows[1]["drop_reason"]
    assert "96pt or more" in rows[1]["drop_reason"]
    assert rows[2] == {
        "article": "bare", "declared": False, "printed": False,
        "height_points": None, "drop_reason": None,
    }


def test_a_render_parks_its_tail_ledger_and_packaging_adopts_it_into_layout(tmp_path: Path):
    """The ledger's route to `layout.tail_arts`, end to end.

    The render seam returns a `RenderLayout` whose fields the compiler copies
    into fixed manifest keys, so the ledger rides the one object that reaches
    packaging whole: `manifest["edition"]` *is* `edition.raw`.  The renderer
    parks it there under a private key; `package._adopt_rendered_layout` moves
    it into the `layout` block the critic reads and pops the scratch key, so
    the written artifact's edition mapping is exactly what was declared.
    `RENDERED_TAIL_ARTS_KEY` is deliberately a restated literal, not an import
    -- packaging must not import a renderer -- so this asserts the two sides
    still name the same key.
    """
    from magazine.package import RENDERED_TAIL_ARTS_KEY, _adopt_rendered_layout

    assert RENDERED_TAIL_ARTS_KEY == adapter._TAIL_ART_LEDGER_KEY

    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    render_a5_weasyprint(edition, tmp_path / "reader.pdf")

    ledger = edition.raw[RENDERED_TAIL_ARTS_KEY]
    assert [row["article"] for row in ledger] == [
        article.id for article in edition.articles
    ]
    for row in ledger:
        assert row["declared"] is True  # the fixture declares its tail art
        assert row["printed"] == (row["height_points"] is not None)
        assert row["printed"] == (row["drop_reason"] is None)

    manifest = {"edition": edition.raw, "layout": {"article_pages": {}}}
    _adopt_rendered_layout(manifest)
    assert manifest["layout"]["tail_arts"] == ledger
    assert RENDERED_TAIL_ARTS_KEY not in edition.raw

    # A build whose renderer wrote no ledger -- ReportLab, or history --
    # packages no key, which the critic reads as nothing to reconcile.
    predates = {"edition": {"format": {}}, "layout": {}}
    _adopt_rendered_layout(predates)
    assert "tail_arts" not in predates["layout"]


def test_an_author_note_that_runs_into_the_standfirst_gap_is_refused():
    """`_validate_opener_credit_depth`: the note is measured type, the field is
    arithmetic, and the finished page is asked -- the note must keep the
    credit's own 13pt line above the field's foot."""

    def reader(note_top: float, note_height: float) -> _Document:
        note = _BlockBox(
            "p", element=_Element("p", **{"class": "author-note"}),
            y=note_top, height=note_height,
        )
        header = _BlockBox(
            "header", element=_Element("header"),
            children=(_BlockBox("h1", element=_Element("h1")), note),
            y=0, height=400,  # a 300pt field: foot at 300pt in page points
        )
        article = _Box(
            "article", element=_Element("article", **{"data-article-id": "a"}),
            children=(header,),
        )
        return _Document((_Page(_Box(children=(article,))),))

    # 277.5pt of note foot against a 300pt field foot: 22.5pt clear, over 13.
    adapter._validate_opener_credit_depth(reader(360.0, 10.0))
    # 297pt against 300: three points is under the credit's own line.
    with pytest.raises(ValidationError, match="author note"):
        adapter._validate_opener_credit_depth(reader(390.0, 6.0))



def test_measure_then_render_settles_the_plan_and_never_pads_the_signature(tmp_path: Path):
    """The adapter renders a probe, measures it, and renders what it measured."""
    edition = replace(_edition(tmp_path), raw={})
    _write_rasters(tmp_path)
    document = _stub_reader_document(())
    tree = _print_tree(edition)
    laid_out: list[str] = []

    class _HTML:
        def __init__(self, *, string: str, base_url: str):
            laid_out.append(string)
            self.etree_element = tree

        def render(self, *, stylesheets, font_config=None):
            return document

    settled, html, plan = _render_to_signature(_HTML, _semantic(edition), object(), edition)

    assert settled is document
    assert "signature-pad" not in html
    # Content ends on page 2 of a four-page reader, so the fold needs no plate at
    # all -- which is not the one plate the probe pass offered, hence two passes.
    assert plan.closing_plates == 0
    assert len(laid_out) == 2 and laid_out[0] == laid_out[1]
    # The bare probe pass carried no code and no ornament; the measured plan
    # carries both -- the code placed off the stub byline the opener laid out,
    # the ornament at the height the stub article's own ending earned -- which
    # is why there are two passes.
    assert [(code.article_id, code.slot) for code in plan.source_codes] == [
        ("article<&>", "opener")
    ]
    # The stub article's flow ends high, so the band is capped at 214 and the
    # measured surplus is split into the lift that centres it in its room.
    room = adapter._tail_art_room(adapter._article_flow_bottom(document, "article<&>"))
    assert plan.tail_arts == (("article<&>", 214.0, (room - 214.0) / 2),)


def test_a_reader_that_is_not_a_signature_is_refused_rather_than_padded(tmp_path: Path):
    edition = _edition(tmp_path)
    _write_rasters(tmp_path)
    plate = edition.closing_plates[0]
    edition = replace(
        edition,
        raw={},
        closing_plates=(plate, plate, plate),
        articles=(replace(edition.articles[0], tail_art=None),),
    )
    # The stub pages still have to carry the article's own flow, because the
    # plan measures every article's `self.y` for its end mark.
    article_box = _Box(
        "article",
        element=_Element("article", **{"data-article-id": edition.articles[0].id}),
        children=(_stub_byline(edition.articles[0].id),),
        height=100,
    )
    document = _Document(
        tuple(_Page(_Box(children=(article_box,))) for _ in range(5))
    )
    tree = _print_tree(edition)

    class _HTML:
        def __init__(self, *, string: str, base_url: str):
            self.etree_element = tree

        def render(self, *, stylesheets, font_config=None):
            return document

    with pytest.raises(ValidationError, match="not an allowed substitute"):
        _render_to_signature(_HTML, _semantic(edition), object(), edition)


def test_landscape_plate_consumes_its_heading_and_a_deferred_plate_waits():
    """Rules F1/F2: render.py:1384-1393 consumes the anchor, 1419-1439 defers."""
    tree = _parse_article_fragment(
        "<h2>Consumed</h2>"
        '<figure data-layout="landscape_plate"><img src="a"></figure>'
        "<p>prose</p>"
        "<h2>Deferring</h2>"
        '<figure data-layout="landscape_plate_after"><img src="b"></figure>'
        "<p>more prose</p>"
        "<h2>Release point</h2>"
        "<p>tail prose</p>"
        '<figure class="article-tail"><img src="c"></figure>'
    )
    _rewrite_landscape_plates(tree)
    article = next(tree.iter("article"))
    shape = [
        (child.tag, child.get("class") or child.get("data-layout") or "", (child.text or "").strip())
        for child in article
    ]

    assert shape == [
        ("div", "landscape-plate", ""),
        ("p", "", "prose"),
        ("h2", "", "Deferring"),
        ("p", "", "more prose"),
        ("div", "landscape-plate", ""),
        ("h2", "", "Release point"),
        ("p", "", "tail prose"),
        ("figure", "article-tail", ""),
    ]
    consumed, deferred = (child for child in article if child.tag == "div")
    # The consumed heading exists only on its plate; the deferred one is repeated.
    assert [element.tag for element in consumed[0]] == ["h2", "figure"]
    assert consumed[0][0].text == "Consumed"
    assert deferred[0][0].text == "Deferring"
    assert [heading.text for heading in tree.iter("h2")] == [
        "Consumed", "Deferring", "Deferring", "Release point",
    ]


def test_a_trailing_deferred_plate_surfaces_at_the_end_of_the_article():
    tree = _parse_article_fragment(
        "<h2>Last heading</h2>"
        '<figure data-layout="landscape_plate_after"><img src="b"></figure>'
        "<p>closing prose</p>"
    )
    _rewrite_landscape_plates(tree)
    article = next(tree.iter("article"))
    assert [child.tag for child in article] == ["h2", "p", "div"]


def test_extra_closing_plates_are_dropped_and_a_shortfall_is_a_hard_error():
    tree = _parse_article_fragment("", plates=3)
    _limit_closing_plates(tree, 2)
    assert len(list(tree.iter("figure"))) == 2
    with pytest.raises(ValidationError, match="requires 5 unique closing plates"):
        _limit_closing_plates(tree, 5)


def test_the_code_opens_the_credit_line_flush_left_with_the_column_beside_it():
    """The code is opener furniture: square, then byline and note as one column.

    The element is appended to the opener's `header`, so it lands on the
    article's first page; its geometry is the plan's own `left`/`top`, stated
    inline because both are measurements.  FLUSH IS FLUSH TO THE INK: the quiet
    zone lives inside the element, so the box begins four light modules before
    the article rail and the *first dark module* lands on it, the same origin the
    kicker's `FEATURE nn`, fitted title and prose take.  NOTHING IS SET UNDER IT.
    """
    code = adapter._fitted_source_code(
        "article", "https://example.test/a", adapter._CODE_OPENER_SIDE_POINTS
    )
    # Placed as `_opener_source_codes` places it: first dark row on a byline
    # cap top of an arbitrary measured baseline, first dark column on the
    # article's centred 325pt reading rail.
    baseline = 150.0
    top = baseline - adapter._BYLINE_SIZE_POINTS * adapter._INTER_CAP_RATIO - code.quiet
    code = replace(
        code,
        left=adapter._CODE_MEASURE_LEFT_POINTS - code.quiet,
        top=top,
    )
    assert code.symbol_left == pytest.approx(adapter._CODE_MEASURE_LEFT_POINTS)
    assert code.symbol_top == pytest.approx(
        baseline - adapter._BYLINE_SIZE_POINTS * adapter._INTER_CAP_RATIO
    )

    tree = _parse_article_fragment(
        "<p>Body.</p>",
        credit=True,
        note="A note that reaches across the live width and must stop short.",
    )
    _apply_source_codes(tree, {"article": code})

    header = next(iter(tree.iter("header")))
    image = next(
        element for element in header.iter("img") if element.get("class") == "source-code"
    )
    assert image.get("data-source-code") == "opener"
    assert image.get("style") == (
        f"left: {code.left:.4f}pt; top: {code.top:.4f}pt; "
        f"width: {code.side:.4f}pt; height: {code.side:.4f}pt"
    )
    # The credit column begins one credit gap past the last dark module and runs
    # to the article rail's right edge.  Both lines of it are inset; only the note,
    # which is prose-length, is also given the width.  The gap is measured from
    # the SYMBOL, so the quiet zone is inside it: growing the square grows the
    # quiet zone and moves the type by exactly as much, which is why the printed
    # ink-to-text distance is this constant and not this constant plus a border.
    symbol_width = code.side - 2 * code.quiet
    inset = symbol_width + adapter._CODE_CREDIT_GAP_POINTS
    assert adapter._CODE_CREDIT_GAP_POINTS == pytest.approx(14.175)
    assert inset - symbol_width == pytest.approx(14.175)
    column = adapter._CODE_MEASURE_POINTS - inset
    assert adapter._credit_column_inset(code) == pytest.approx(inset)
    byline = next(
        element for element in header.iter("p") if element.get("class") == "byline"
    )
    assert byline.get("style") == f"margin-left: {inset:.4f}pt"
    note = next(
        element for element in header.iter("p") if element.get("class") == "author-note"
    )
    assert note.get("style") == f"margin-left: {inset:.4f}pt; width: {column:.4f}pt"
    assert inset + column == pytest.approx(adapter._CODE_MEASURE_POINTS)
    # Nothing hangs under the square.
    assert [element for element in header.iter("p") if element.get("class") == "source-label"] == []
    # The tail figure is no longer the code's business: it stays in the tree
    # for `_apply_tail_arts` to judge.
    with_tail = _parse_article_fragment(
        '<figure class="article-tail"><img src="c"></figure>', credit=True
    )
    _apply_source_codes(with_tail, {"article": code})
    assert any(
        "article-tail" in adapter._element_classes(figure)
        for figure in with_tail.iter("figure")
    )

    without = _parse_article_fragment("<p>Body.</p>")
    _apply_source_codes(without, {})
    assert [element for element in without.iter("img") if element.get("class") == "source-code"] == []


def test_a_qr_opener_prose_shares_the_title_and_symbol_left_edge():
    """The opener's prose must not step right from its visible grid.

    The title, square, lead and running body read as parts of one vertical edge,
    so their line origins must coincide throughout the opener.  This is about
    the article's centred 325pt prose rail, not the credit column beside the
    square.
    """
    from xml.etree.ElementTree import tostring

    code = adapter._fitted_source_code(
        "article", "https://example.test/a", adapter._CODE_OPENER_SIDE_POINTS
    )
    code = replace(
        code,
        left=adapter._CODE_MEASURE_LEFT_POINTS - code.quiet,
        top=120.0,
    )
    tree = _parse_article_fragment(
        '<p class="standfirst">First body prose on the opener.</p>'
        '<p>Running body prose continues on the opener.</p>',
        credit=True,
    )
    _apply_source_codes(tree, {"article": code})
    article = next(tree.iter("article"))
    document = _typeset_document(tostring(article, encoding="unicode"))
    page = document.pages[0]

    title = _block_of(page, "h1")
    standfirst = _block_by_class(page, "standfirst")
    running = _box_of(
        page,
        lambda box: (
            type(box).__name__ == "BlockBox"
            and getattr(box, "element_tag", None) == "p"
            and getattr(box, "element", None) is not None
            and not adapter._element_classes(box.element)
        ),
    )
    image = _box_of(
        page,
        lambda box: (
            getattr(box, "element_tag", None) == "img"
            and getattr(box, "element", None) is not None
            and "source-code" in adapter._element_classes(box.element)
        ),
    )
    title_left = title.content_box_x() * _POINTS_PER_CSS_PIXEL
    symbol_left = image.content_box_x() * _POINTS_PER_CSS_PIXEL + code.quiet
    standfirst_left = standfirst.content_box_x() * _POINTS_PER_CSS_PIXEL
    running_left = running.content_box_x() * _POINTS_PER_CSS_PIXEL

    assert symbol_left == pytest.approx(title_left, abs=5e-4)
    assert standfirst_left == pytest.approx(title_left, abs=5e-4)
    assert running_left == pytest.approx(title_left, abs=5e-4)


def test_a_long_byline_is_compressed_within_a_readability_floor():
    """A source-faithful long credit fits one line without becoming illegible."""
    code = adapter._fitted_source_code(
        "article",
        "https://huggingface.co/blog/agent-intrusion-technical-timeline",
        adapter._CODE_OPENER_SIDE_POINTS,
    )
    code = replace(code, left=-code.quiet, top=140.0)
    tree = _parse_article_fragment(
        "<p>Body.</p>",
        credit=True,
        author="Hugo Larcher, Adrien Carreira, raphael g, Christophe Rannou",
    )
    _apply_source_codes(tree, {"article": code})
    byline = next(
        element for element in tree.iter("p") if element.get("class") == "byline"
    )
    assert "white-space: nowrap" in byline.get("style")
    assert "letter-spacing:" in byline.get("style")

    # The threshold itself: the widest byline the column takes passes, and one
    # letter more is refused.  `_parse_article_fragment` sets the author verbatim
    # and `_fit_credit_measure` upper-cases before measuring, as `.byline` does.
    column = adapter._LIVE_WIDTH_POINTS - adapter._credit_column_inset(code)
    set_as = lambda name: adapter._string_width(  # noqa: E731 - the byline's own ink
        f"BY {name}".upper(), "sans-semibold", adapter._BYLINE_SIZE_POINTS
    )
    longest = next("N" * n for n in range(1, 400) if set_as("N" * (n + 1)) > column)
    assert set_as(longest) <= column < set_as(longest + "N")
    _apply_source_codes(
        _parse_article_fragment("<p>Body.</p>", credit=True, author=longest),
        {"article": code},
    )
    compressed = _parse_article_fragment(
        "<p>Body.</p>", credit=True, author=longest + "N"
    )
    _apply_source_codes(compressed, {"article": code})
    compressed_byline = next(
        element
        for element in compressed.iter("p")
        if element.get("class") == "byline"
    )
    assert "letter-spacing:" in compressed_byline.get("style")

    impossible = "N" * 200
    with pytest.raises(ValidationError, match="excessive horizontal compression"):
        _apply_source_codes(
            _parse_article_fragment("<p>Body.</p>", credit=True, author=impossible),
            {"article": code},
        )

    # And the byline that fits the column is set in it, not refused.
    fits = _parse_article_fragment("<p>Body.</p>", credit=True, author="Author")
    _apply_source_codes(fits, {"article": code})
    byline = next(
        element for element in fits.iter("p") if element.get("class") == "byline"
    )
    assert byline.get("style") == f"margin-left: {adapter._credit_column_inset(code):.4f}pt"



def test_measurement_reports_actual_folios_article_pages_and_figure_box(tmp_path: Path):
    asset = _image_asset(tmp_path)
    article = _Box("article", element=_Element("article", **{"data-article-id": "article"}))
    figure = _Box(
        "img", element=_Element("img", src=asset.src), x=40, y=100, width=200, height=100,
    )
    editorial = _Box("section", element=_Element("section", id="editorial"))
    destination = _Box("article", element=_Element("article", id="article-article", **{"data-article-id": "article"}))
    document = _Document((_Page(_Box(children=(editorial,))), _Page(_Box(children=(article, destination, figure)))))

    layout = _measure_layout(document, (asset,), WEASYPRINT_DESIGN)

    assert layout.toc == {"editorial": 1, "article": 2}
    assert layout.editorial_pages == 1
    assert layout.article_pages == {"article": 1}
    assert len(layout.figure_placements) == 1
    placement = layout.figure_placements[0]
    assert placement.page == 2
    # 595.2756 - 75 - 75 = 445.2756, plus the rasteriser nudge the measured CSS
    # y carries and the reported box must not: 445.2806.
    assert placement.box_points == (30.0, 445.281, 150.0, 75.0)
    assert placement.pixel_dimensions == (1200, 600)
    assert placement.effective_ppi == 576.0


def test_measurement_leaves_furniture_out_of_the_preflight_placements(tmp_path: Path):
    """`render.py` records a placement for a curated figure and for nothing else.

    A placement is preflight's input, and preflight raises a low-resolution
    finding for every placement under MIN_FIGURE_PPI and asks for a contrast
    treatment on every one.  A tail motif and a closing plate are drawn with
    `_draw_image_fill`, are never checked and never contrast-treated, so
    inventorying them here would manufacture findings the reader never had.
    """
    figure = _image_asset(tmp_path)
    tail = replace(figure, id="article-tail-article", role="article_tail", figure_id=None)
    plate = replace(figure, id="closing-plate-1", role="closing_plate", figure_id=None)
    boxes = tuple(
        _Box("img", element=_Element("img", src=asset.src), x=0, y=0, width=200, height=100)
        for asset in (figure, tail, plate)
    )
    document = _Document((_Page(_Box(children=boxes)),))

    layout = _measure_layout(document, (figure, tail, plate), WEASYPRINT_DESIGN)

    assert [placement.figure_id for placement in layout.figure_placements] == [figure.figure_id]


def test_page_caps_fail_after_measured_layout_and_manifest_caps_are_fixed(tmp_path: Path):
    edition = _edition(tmp_path)
    _validate_caps(edition)
    with pytest.raises(ValidationError, match="hard publication rule"):
        _validate_caps(replace(edition, raw={"format": {"max_article_pages": 9}}))
    too_long = RenderLayout({}, {"article": 8}, 3, WEASYPRINT_DESIGN, None, {}, {})
    with pytest.raises(ValidationError, match="article page cap"):
        _validate_layout_caps(edition, too_long)


def test_an_article_below_its_editorial_minimum_is_refused_like_an_overlong_one(
    tmp_path: Path,
):
    """``minimum_reader_pages`` is the edition's floor, not one typesetter's.

    It is declared per article in the manifest and carried through translation,
    and ``render.py`` has always refused a build that falls under it.  This path
    did not, so the floor silently stopped applying when WeasyPrint became the
    default engine.
    """
    article = replace(_edition(tmp_path).articles[0], minimum_reader_pages=3)
    edition = replace(_edition(tmp_path), articles=(article,))

    def layout(pages: int) -> RenderLayout:
        return RenderLayout({}, {article.id: pages}, 1, WEASYPRINT_DESIGN, None, {}, {})

    with pytest.raises(ValidationError, match="editorial minimum 3") as raised:
        _validate_layout_caps(edition, layout(2))
    assert article.id in str(raised.value)
    _validate_layout_caps(edition, layout(3))
    _validate_layout_caps(edition, layout(4))


def test_dependency_failure_has_an_actionable_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    with pytest.raises(ValidationError, match=r"uv sync --locked"):
        _weasyprint_types()


def test_macos_loader_prepends_existing_homebrew_paths_without_losing_user_path(monkeypatch, tmp_path: Path):
    homebrew = tmp_path / "homebrew" / "lib"
    local = tmp_path / "local" / "lib"
    homebrew.mkdir(parents=True)
    local.mkdir(parents=True)
    import magazine.weasyprint_adapter as adapter

    monkeypatch.setattr(adapter.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(adapter, "Path", lambda value: {
        "/opt/homebrew/lib": homebrew,
        "/usr/local/lib": local,
    }[value])
    monkeypatch.setenv("DYLD_FALLBACK_LIBRARY_PATH", "/custom/lib")

    _configure_macos_library_path()

    assert adapter.os.environ["DYLD_FALLBACK_LIBRARY_PATH"] == (
        f"{homebrew}:{local}:/custom/lib"
    )
    _configure_macos_library_path()
    assert adapter.os.environ["DYLD_FALLBACK_LIBRARY_PATH"] == (
        f"{homebrew}:{local}:/custom/lib"
    )


def test_one_font_configuration_reaches_both_stylesheet_parsing_and_layout(
    tmp_path: Path, monkeypatch
):
    """WeasyPrint installs @font-face only for a shared font configuration.

    Parsing the stylesheet registers the bundled faces on the configuration it is
    given, and layout can only use faces registered on the configuration *it* is
    given.  Passing two instances, or dropping either argument, silently typesets
    the whole reader on host fonts, so the identity of the object is the contract.
    """
    # The font-safe manuscript carries a code span that looks like a markdown
    # link and prose the reader folds, so a post-pass over assembled markup
    # cannot slip through the document comparison below unnoticed.  The article
    # is stripped of its source url -- a source record need not carry a
    # canonical one, so this is a real edition shape -- because the layout below
    # is a hand-built double whose `write_pdf` returns four bytes, and the source
    # code gate reads a rasterised page.
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    edition = replace(
        edition, articles=tuple(replace(a, source_url=None) for a in edition.articles)
    )
    assets = render_html_edition(edition).assets
    recorded: dict[str, object] = {}

    class _FontConfiguration:
        pass

    class _CSS:
        def __init__(self, *, string: str, base_url: str, font_config=None):
            recorded["stylesheet"] = font_config

    tree = _print_tree(edition)

    class _HTML:
        def __init__(self, *, string: str, base_url: str):
            recorded["document"] = string
            self.etree_element = tree

        def render(self, *, stylesheets, font_config=None):
            recorded["layout"] = font_config
            # The paint pass lays the same reader out again with the frames it
            # measured, so the double re-measures the tree it was handed rather
            # than returning one fixed document for every pass.
            return _stub_reader_document(assets, painted=_painted_rule_boxes(tree))

    monkeypatch.setattr(
        adapter, "_weasyprint_types", lambda: (_HTML, _CSS, _FontConfiguration)
    )

    render_a5_weasyprint(edition, tmp_path / "reader.pdf")

    assert isinstance(recorded["stylesheet"], _FontConfiguration)
    assert recorded["layout"] is recorded["stylesheet"]
    # The adapter hands WeasyPrint the semantic edition plus print slots and
    # nothing else: no character or markdown pass runs over assembled markup.
    assert recorded["document"] == _with_print_slots(render_html_edition(edition).html)


def test_reader_embeds_only_the_bundled_publication_faces(tmp_path: Path):
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    output = tmp_path / "reader.pdf"

    render_a5_weasyprint(edition, output)

    fonts = _base_fonts(output)
    assert fonts, "the reader embedded no fonts at all"
    assert {font for font in fonts if "+Magazine-" not in font} == set()
    assert any("Magazine-Serif" in font for font in fonts)
    assert any("Magazine-Sans" in font for font in fonts)


def test_reader_keeps_a_code_span_that_looks_like_a_markdown_link(tmp_path: Path):
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    html = _with_print_slots(render_html_edition(edition).html)
    assert "<code>[label](target)</code>" in html


def test_page_metrics_reproduce_the_reader_baseline_grid_and_line_capacity():
    """The derived @page metrics, measured rather than asserted from the source.

    ReportLab's first body baseline is 543.2756 above the page foot and its frame
    holds 38 lines of 13pt body leading, or 40 of the 12.2pt plate leading.  Both
    baselines carry the stylesheet's +0.005pt rasterizer nudge, which is a
    hundredth of a device pixel at 144 DPI and changes no line's capacity.
    """
    body = _typeset(f'<section id="prose"><p>{_FILLER_PROSE}</p></section>')
    plate = _typeset(
        f'<article data-figure-layouts="landscape_plate"><p>{_FILLER_PROSE}</p></article>'
    )

    assert [lines for lines, _, _ in body[:3]] == [38, 38, 38]
    assert body[0][1] == pytest.approx(543.2756 - 0.005, abs=5e-4)
    assert [lines for lines, _, _ in plate[:3]] == [40, 40, 40]
    # A 12.2pt line box carries its baseline 0.4pt higher than the 13pt datum the
    # page is cut for, so the plate path is laid out high and painted back down.
    plate_document = _typeset_document(
        f'<article data-figure-layouts="landscape_plate"><p>{_FILLER_PROSE}</p></article>'
    )
    plate_prose = _block_of(plate_document.pages[0], "p")
    assert plate[0][1] == pytest.approx(543.2756 + 0.4 - 0.005, abs=5e-4)
    assert _painted_baseline_from_page_foot(
        next(_line_boxes(plate_prose)), plate_prose
    ) == pytest.approx(543.2756 - 0.005, abs=5e-4)
    assert round(body[0][2], 4) == 19.5


def test_folio_baseline_is_pinned_to_the_page_foot_not_the_bottom_margin():
    recoupled = _read_print_css().replace("42.0004pt 42.5197pt 54.9996pt 44pt",
                                          "42.0004pt 42.5197pt 45pt 44pt")
    assert recoupled != _read_print_css(), "the @page bottom margin was not overridden"

    measured = _typeset(
        f'<section id="prose"><p>{_FILLER_PROSE}</p></section>', css_text=recoupled
    )

    assert round(measured[0][2], 4) == 19.5


_RUNNING_HEAD = (
    '<div class="running-head"><div class="running-head-row">'
    "<span>Berreta Futura</span><span>Light and Dark</span></div>"
    '<div class="running-head-rule"><i></i></div></div>'
)


def test_folio_is_the_publication_name_and_a_zero_padded_number_on_19_5():
    """H7: `_folio` (render.py:565-577), not a centred bare page number."""
    document = _typeset_document(
        '<p class="folio-name">Berreta Futura</p>'
        f'<section id="prose"><p>{_FILLER_PROSE}</p></section>'
    )
    chrome = _page_chrome(document)

    assert chrome[0]["@bottom-left"] == "BERRETA FUTURA"
    assert [page["@bottom-right"] for page in chrome[:3]] == ["01", "02", "03"]
    # Both halves sit on FOLIO_BASELINE, and the hidden name source prints nothing.
    for keyword in ("@bottom-left", "@bottom-right"):
        line = next(
            _line_boxes(child)
            for child in document.pages[0]._page_box.children
            if getattr(child, "at_keyword", None) == keyword
        )
        assert round(_baseline_from_page_foot(next(line)), 4) == 19.5
    assert "Berreta Futura" not in "".join(
        text for page in chrome for text in page.values()
    )


def test_running_header_prints_on_continuation_pages_only():
    """H1/H5: `new_page` (render.py:653-656) -- never on the page a piece opens."""
    document = _typeset_document(
        f'<article data-article-id="a">{_RUNNING_HEAD}<p>{_FILLER_PROSE}</p></article>'
    )
    chrome = _page_chrome(document)

    assert chrome[0].get("@top-center", "") == ""
    assert chrome[1]["@top-center"] == "BERRETA FUTURALIGHT AND DARK"
    assert chrome[2]["@top-center"] == "BERRETA FUTURALIGHT AND DARK"
    # The publication's name is at the live area's left and the curated short
    # title right-aligned at its right, on a baseline 20pt below the sheet's head.
    header = next(
        child
        for child in document.pages[1]._page_box.children
        if getattr(child, "at_keyword", None) == "@top-center"
    )
    lines = [
        (box.position_x * _POINTS_PER_CSS_PIXEL,
         box.width * _POINTS_PER_CSS_PIXEL,
         round((box.position_y + box.baseline) * _POINTS_PER_CSS_PIXEL, 4))
        for box in _line_boxes(header)
    ]
    assert round(header.width * _POINTS_PER_CSS_PIXEL, 4) == 333.0079
    assert [baseline for _, _, baseline in lines] == [20.0, 20.0]
    assert round(lines[0][0], 4) == 42.5197, "page 2 is a verso: the name is at self.left"
    # The flushed end is asserted as an edge, summing before rounding: the
    # title's own width is shaped type and moves in the fourth decimal when the
    # face kerns, while the edge `space-between` flushes it to does not.
    # Rounding the two terms *separately* and adding them turned that
    # ten-thousandth of a point into a failure and asserted nothing extra; the
    # repair is where the rounding happens, not how much drift is tolerated.
    # A 1e-3 window would accept a real 0.0009pt displacement of the edge.
    assert round(lines[1][0] + lines[1][1], 4) == 375.5276, (
        "and the title at width - self.right"
    )


def test_running_header_rule_and_signal_tick_are_absent_where_the_header_is():
    """H2/H3: the 0.55pt rule and the 14pt signal tick belong to the header."""
    document = _typeset_document(
        f'<article data-article-id="a">{_RUNNING_HEAD}<p>{_FILLER_PROSE}</p></article>'
    )
    header = next(
        child
        for child in document.pages[1]._page_box.children
        if getattr(child, "at_keyword", None) == "@top-center"
    )
    drawn = [
        (getattr(box, "element_tag", None),
         round(box.content_box_y() * _POINTS_PER_CSS_PIXEL, 4),
         round(box.width * _POINTS_PER_CSS_PIXEL, 4),
         round(box.height * _POINTS_PER_CSS_PIXEL, 4))
        for box in adapter._walk_boxes(header)
        if getattr(box, "element_tag", None) in {"div", "i"}
        and getattr(box, "element", None) is not None
        and (adapter._element_classes(box.element) & {"running-head-rule"}
             or getattr(box, "element_tag", None) == "i")
    ]
    # The rule is 0.55pt centred on 28 across the live width; the tick is 1.15pt
    # centred on the same 28 and RUNNING_HEADER_SIGNAL_LENGTH long.
    assert ("div", 27.725, 333.0079, 0.55) in drawn
    assert ("i", 27.425, 14.0, 1.15) in drawn
    # An opener page resolves no running element, so neither is drawn at all.
    opener = next(
        child
        for child in document.pages[0]._page_box.children
        if getattr(child, "at_keyword", None) == "@top-center"
    )
    assert list(adapter._walk_boxes(opener))[1:] == []


def test_closing_plate_pages_drop_the_chrome_and_keep_the_margin_mirror():
    """H10 + the collision: a page name outranks `@page :left` / `@page :right`."""
    document = _typeset_document(
        '<p class="folio-name">Berreta Futura</p>'
        f'<article data-article-id="a">{_RUNNING_HEAD}<p>{_FILLER_PROSE}</p></article>'
        '<figure class="closing-plate"><figcaption>Systems in Motion</figcaption></figure>'
        '<figure class="closing-plate"><figcaption>Intent, Preserved</figcaption></figure>'
    )
    plates = [
        (index, page)
        for index, page in enumerate(document.pages)
        if getattr(getattr(page._page_box, "page_type", None), "name", None) == "closing-plate"
    ]

    assert len(plates) == 2, "each plate owns a page of the named closing-plate type"
    chrome = _page_chrome(document)
    for index, page in plates:
        assert chrome[index] == {}, "a plate carries neither folio nor running header"
        margins = (
            round(page._page_box.margin_left * _POINTS_PER_CSS_PIXEL, 4),
            round(page._page_box.margin_right * _POINTS_PER_CSS_PIXEL, 4),
        )
        assert margins in {(44.0, 42.5197), (42.5197, 44.0)}
        assert margins == ((44.0, 42.5197) if index % 2 == 0 else (42.5197, 44.0))


def test_contents_rows_divide_a_fixed_band_and_read_label_folio_title_author():
    """T3-T10: `row_top` 479, `393 / max(6, len(chunk))`, four values per row."""
    entries = "".join(
        f'<li><span class="entry-label">Feature 0{index}</span>'
        f'<a class="entry-folio" href="#a{index}"></a>'
        f'<a class="entry-title" href="#a{index}">Title {index}</a>'
        f'<span class="entry-author">Author {index}</span></li>'
        for index in range(1, 8)
    )
    document = _typeset_document(
        '<nav data-edition-navigation="contents">'
        '<p class="contents-kicker">Issue 2 / Contents</p><h2>Contents</h2>'
        f"<ol>{entries}</ol></nav>"
    )
    page = document.pages[0]._page_box
    baselines = {}
    for box in adapter._walk_boxes(page):
        if type(box).__name__ != "LineBox":
            continue
        element = getattr(box, "element", None)
        classes = adapter._element_classes(element) if element is not None else frozenset()
        key = next(iter(classes & {"contents-kicker", "entry-label", "entry-folio",
                                   "entry-title", "entry-author"}), None)
        if key or getattr(box, "element_tag", None) == "h2":
            baselines.setdefault(key or "h2", []).append(
                round(595.2756 - (box.position_y + box.baseline) * _POINTS_PER_CSS_PIXEL, 3)
            )

    # The kicker sits above the live area's head and the title 27pt below it.
    # Every value carries the stylesheet's +0.005pt rasterizer nudge.
    assert baselines["contents-kicker"] == [564.271]
    assert baselines["h2"] == [511.271]
    # Row n's head is 479 - n * 56.142857; the label is 8pt down, the folio and
    # the title 23pt down, the author 43pt down.
    heads = [479.0 - 0.005 - index * (393.0 / 7) for index in range(7)]
    assert baselines["entry-label"] == [round(head - 8, 3) for head in heads]
    assert baselines["entry-folio"] == [round(head - 23, 3) for head in heads]
    assert baselines["entry-title"] == [round(head - 23, 3) for head in heads]
    assert baselines["entry-author"] == [round(head - 43, 3) for head in heads]


def test_page_chrome_is_print_only_structure_built_from_the_edition(tmp_path: Path):
    """The running head and the folio's name never enter the semantic edition."""
    edition = _edition(tmp_path)
    semantic = render_html_edition(edition).html
    assert "running-head" not in semantic and "folio-name" not in semantic

    tree = _print_tree(edition)
    adapter._install_page_chrome(tree, edition)
    heads = [
        element
        for element in tree.iter("div")
        if "running-head" in adapter._element_classes(element)
    ]
    names = [
        element
        for element in tree.iter("p")
        if "folio-name" in adapter._element_classes(element)
    ]

    assert [name.text for name in names] == ["Magazine <&>"]
    # One head per piece -- the editorial, the article and the section -- each
    # the piece's own first child so its page is the page the piece opens on.
    assert len(heads) == 3
    assert [
        [span.text for span in head.iter("span")] for head in heads
    ] == [
        ["Magazine <&>", "Editorial"],
        ["Magazine <&>", "Article"],
        ["Magazine <&>", "Sources <&>"],
    ]
    for piece in (*tree.iter("article"), *tree.iter("section")):
        if piece.get("data-short-title"):
            assert "running-head" in adapter._element_classes(piece[0])


def _flow_lines(document: object) -> list[str]:
    """The text of every in-flow line box, page by page, margin boxes excluded."""
    lines: list[str] = []
    for page in document.pages:
        for child in page._page_box.children:
            if getattr(child, "at_keyword", None):
                continue
            for line in _line_boxes(child):
                lines.append(
                    "".join(
                        box.text
                        for box in adapter._walk_boxes(line)
                        if type(box).__name__ == "TextBox"
                    )
                )
    return lines


# Twelve words of filler put the interesting tokens across the measure's edge.
_BREAK_PROSE = (
    "word word alpha bravo charlie delta echo foxtrot golf hotel india juliet "
    "kilo lima the compile-checked interface differed-- some trade-offs remain "
    "here and there"
)


def test_the_reader_kerns_and_therefore_holds_more_per_line_than_reportlab():
    """The shaping scaffolds are gone, so Pango's measure is no longer ReportLab's.

    `_wrap` reproduces `lines` (render.py:658-685), which sums raw glyph
    advances and kerns nothing.  Pango kerns, so the same copy measures narrower
    and a line takes a word the ReportLab reader pushed to the next.  The
    divergence is asserted deliberately: the day it stops holding, either
    kerning has been turned back off or the two measures have been re-coupled,
    and both are regressions now.
    """
    reportlab = adapter._wrap(_BREAK_PROSE, "serif", 10, 325)
    shaped = _flow_lines(
        _typeset_document(f'<section id="prose"><p>{_BREAK_PROSE}</p></section>')
    )

    assert shaped != reportlab
    assert len(shaped[0].split()) > len(reportlab[0].split()), (
        "kerning pulls letters together, so the shaped first line holds more"
    )
    assert " ".join(" ".join(shaped).split()) == " ".join(_BREAK_PROSE.split()), (
        "only the line breaks may move; not one word of copy"
    )


def test_the_reader_now_breaks_inside_a_hyphenated_token():
    """`lines` can only end a line on whitespace; Pango may end it on a hyphen.

    Held down by `.reader-token { white-space: nowrap }` until the re-baseline,
    which is what made the two renderers interchangeable.  It is the intended
    behaviour now: a hyphenated compound that will not fit the measure breaks at
    its hyphen instead of pushing the whole token to the next line.
    """
    prose = " ".join(["alpha"] * 8) + " planner-executor-synthesis remains"
    shaped = _flow_lines(_typeset_document(f'<section id="prose"><p>{prose}</p></section>'))

    assert any(line.endswith("-") for line in shaped), shaped
    assert not any(
        line.endswith("-") for line in adapter._wrap(prose, "serif", 10, 325)
    ), "ReportLab has no such break opportunity, which is the whole difference"


#: The `@font-face` family each `_advance_widths` face is installed under.
_SHAPED_FAMILIES = {"serif": "Magazine Serif", "serif-display": "Magazine Serif Display"}


def _shaped_inline_width(text: str, *, size: float, face: str = "serif") -> float:
    """The width Pango gives one run of `text`, against `_string_width`'s face.

    Measured off the inline box rather than the line box: a line box is as wide
    as the text it holds, but only once nothing else -- indents, the measure's own
    rounding -- is in it, and an inline box is the run and nothing else.  The
    family is named explicitly so the run is set in the same face
    `adapter._string_width` sums, which is the whole point of comparing them, and
    the block is made far wider than the reader's measure so that the run stays
    one fragment: a wrapped inline box reports its first line's width only.
    """
    weight = 600 if face == "serif-display" else 400
    document = _typeset_document(
        f'<section id="prose"><p style="font-size: {size}pt; line-height: {size}pt; '
        f"width: 3000pt; font-family: '{_SHAPED_FAMILIES[face]}'; font-weight: {weight}\">"
        f"<span>{text}</span></p></section>"
    )
    inline = next(
        box
        for page in document.pages
        for box in adapter._walk_boxes(page._page_box)
        if type(box).__name__ == "InlineBox"
    )
    return float(inline.width) * _POINTS_PER_CSS_PIXEL


@pytest.mark.parametrize(
    ("cluster", "shaped", "summed"),
    (("fi", 63.7998, 68.3000), ("ffi", 95.4998, 104.7000)),
)
def test_the_reader_applies_ligatures_and_therefore_sets_narrower_than_reportlab(
    cluster: str, shaped: float, summed: float
):
    """The second scaffold is gone, and this is the measurement that says so.

    `font-variant-ligatures: none` came out at the re-baseline.  Its absence from
    the stylesheet is asserted as a string above, but a string assertion is not a
    pin: `font-feature-settings: "liga" 0, "clig" 0` suppresses exactly the same
    thing under a different spelling and would pass it.  What cannot be spelled
    around is the width -- an `fi` set as one glyph is 4.5pt narrower at 100pt
    than the `f` and the `i` summed, an `ffi` 9.2pt narrower -- so the width is
    what this asserts.  `_wrap` still sums, because it reproduces `lines`
    (render.py:658-685), so the gap is also the divergence between the two
    measures, and it is intended.
    """
    assert _shaped_inline_width(cluster, size=100) == pytest.approx(shaped, abs=1e-3)
    assert adapter._string_width(cluster, "serif", 100) == pytest.approx(summed, abs=1e-3)
    assert _shaped_inline_width(cluster, size=100) < adapter._string_width(cluster, "serif", 100)


def test_no_per_token_markup_reaches_the_print_document(tmp_path: Path):
    """The tree the adapter lays out carries the semantic edition's text nodes.

    `_suppress_intra_token_breaks` used to rebuild every text node under `main`
    as one inline box per whitespace token.  Nothing does that any more, and
    nothing should: the per-token boxes are what cost the reader's text layer
    its space characters, which the next test asserts it has back.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    tree = _print_tree(edition)

    assert not hasattr(adapter, "_suppress_intra_token_breaks")
    # Comments stripped, then whitespace: the stylesheet still *names* the
    # retired rule, in the note that explains why it is gone and must not come
    # back, and a literal `"white-space: nowrap" not in ...` walks straight past
    # the equally valid `white-space:nowrap`.  These are belt to the braces of
    # the three tests that assert the shaped behaviour itself.
    declarations = re.sub(r"\s+", "", re.sub(r"/\*.*?\*/", "", _read_print_css(), flags=re.S))
    assert ".reader-token" not in declarations
    assert "white-space:nowrap" not in declarations
    assert "font-kerning" not in declarations
    assert "font-variant-ligatures" not in declarations
    prose = next(
        paragraph
        for paragraph in next(tree.iter("main")).iter("p")
        if (paragraph.text or "").split()[1:]
    )
    # A whole sentence in one text node, not one span per word.
    assert not list(prose)
    assert " " in (prose.text or "")


def test_the_reader_s_text_layer_carries_real_space_characters():
    """What dropping the per-token boxes gives back, asserted where it was lost.

    WeasyPrint gives every inline box its own text matrix and writes no space
    glyph between two of them, so one box per token reached the PDF as
    `Theoriginalarticle.`  Poppler recovers the words from the glyph advances,
    which is why `pdftotext` always read those pages correctly, but an extractor
    that reads the written characters -- `pypdf` among them -- did not.
    """
    import io

    from pypdf import PdfReader

    document = _typeset_document(
        '<section id="prose"><p>The original article ran here.</p></section>'
    )
    text = PdfReader(io.BytesIO(document.write_pdf())).pages[0].extract_text()

    assert "The original article ran here." in " ".join(text.split())


def test_a_line_wider_than_its_measure_is_refused_rather_than_overflowing():
    """A token with no break opportunity still overflows, and is still refused.

    The guard narrowed when the nowrap boxes came out -- a hyphenated token now
    breaks at its hyphen and never reaches here -- but an unbroken run of
    letters is still set past the column edge, and silently.  It is refused
    rather than styled with `overflow-wrap`: a word that cannot fit the measure
    is an editorial problem, not the typesetter's to hyphenate at random.
    """
    inside = _typeset_document(
        '<section id="prose"><p>' + "supercalifragilistic" * 3 + "</p></section>"
    )
    over = _typeset_document(
        '<section id="prose"><p>' + "supercalifragilistic" * 12 + "</p></section>"
    )
    hyphenated = _typeset_document(
        '<section id="prose"><p>' + "alpha-beta-" * 24 + "omega</p></section>"
    )

    adapter._validate_reader_measures(inside)
    adapter._validate_reader_measures(hyphenated)  # breaks at its own hyphens now
    with pytest.raises(ValidationError, match="wider than its own measure"):
        adapter._validate_reader_measures(over)


# Four ordinary English words whose kern pairs -- `Lo` +21, `Cu` and `ou` and
# `rr` among them -- make Pango set the line *wider* than `_wrap` sums it, which
# is the direction `_advance_widths` used to be documented as unable to take.
_LOOSENING_TITLE = "Current Court Locus Locus"
_LOOSENING_PLATE_TITLE = "Corner Loom Course"


def test_a_kerned_title_wider_than_summed_is_measured_wider_and_not_narrower():
    """The premise the guard exists for, asserted before the guard is.

    `_advance_widths` sums unkerned advances because `lines` (render.py:658-685)
    does, and its docstring used to say the sum was an upper bound on the shaped
    width -- that kerning and ligatures only pull glyphs together, so a fitted
    size always still fits.  Ligatures do.  Kerning does not: 3,019 cp1252 pairs
    of `kern` in the display face push glyphs apart.  If this assertion ever
    inverts, the guard below has lost its subject and the sum has become the
    bound it was claimed to be.
    """
    size, lines = adapter._fitted_display(
        _LOOSENING_TITLE,
        adapter._LIVE_WIDTH_POINTS,
        165.0,
        maximum=adapter._ARTICLE_TITLE_MAX_WITH_FIGURE,
        minimum=24.0,
        maximum_lines=adapter._OPENER_TITLE_MAX_LINES,
        leading_ratio=adapter._OPENER_TITLE_LEADING_RATIO,
    )
    summed = adapter._string_width(_LOOSENING_TITLE, "serif-display", size)
    shaped = _shaped_inline_width(_LOOSENING_TITLE, size=size, face="serif-display")

    assert lines == [_LOOSENING_TITLE], "the unkerned sum fits the whole title on one line"
    assert summed <= adapter._LIVE_WIDTH_POINTS
    assert shaped > adapter._LIVE_WIDTH_POINTS, "and the kerned one does not"
    assert shaped > summed


def test_an_opener_title_that_outgrows_its_reserved_field_is_refused(
    tmp_path: Path, monkeypatch
):
    """The defect: a fitted title takes a line the opener did not reserve room for.

    An opener carrying a figure ends its white field wherever the auto-fitted
    title and credit reached, and the figure's head is that field's foot.  When
    Pango sets the title on more lines than `_fitted_display` predicted, the
    title runs out of the field and into the figure -- silently, because
    `_validate_reader_measures` refuses a line box wider than its measure and a
    title that *wrapped* is not one.

    The message has to be usable by whoever hits it while closing an edition, so
    it is asserted for the four facts that make it actionable: which piece, which
    title, how much room was reserved, how far past it the title actually
    reached -- and what to do instead.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    # AS SHIPPED, which means WITH a source code.  An opener that carries one
    # earns a *deeper* field so the code's square clears the artwork
    # (`_opener_code_field_floor`), and a guard that measured the title against
    # that deeper field would hand the title the code's room and let this very
    # defect through: the reservation the title is judged against is its own.
    overlong = replace(
        edition,
        articles=tuple(
            replace(article, title=_LOOSENING_TITLE) for article in edition.articles
        ),
    )
    assert all(article.source_url for article in overlong.articles)

    render_a5_weasyprint(edition, tmp_path / "reader.pdf")  # as authored, no refusal
    genuine_fit = adapter._fitted_display

    def understated_fit(title, *args, **kwargs):
        # Model the defect directly: the fitter claims this 30pt title occupies
        # one line, while Pango lays it out on two against the 325pt article rail.
        if title == _LOOSENING_TITLE:
            return 30.0, [title]
        return genuine_fit(title, *args, **kwargs)

    monkeypatch.setattr(adapter, "_fitted_display", understated_fit)
    with pytest.raises(ValidationError) as raised:
        render_a5_weasyprint(overlong, tmp_path / "overlong.pdf")

    message = str(raised.value)
    assert "article<&>" in message, "name the piece an editor has to go and fix"
    assert _LOOSENING_TITLE in message
    assert "117.8000pt title field" in message, "the room that was reserved"
    assert "overflowing the field by 12.1127pt" in message, "and how far past it"
    # 117.8 is the title's own reservation -- 59pt of opener chrome plus one
    # fitted 30pt line.  The field this opener really states is 157.6911, because
    # its code has to clear the artwork; measured against *that*, the loosened
    # title's second line comes out 27.78pt clear and the page ships with its
    # code pushed into the figure.
    assert "157.6911" not in message, "the code's room is not the title's"
    assert "Shorten the title, or lower the fit range" in message
    assert not (tmp_path / "overlong.pdf").exists(), "and nothing is written"


def test_a_source_code_that_reaches_into_the_opener_figure_is_refused(
    tmp_path: Path, monkeypatch
):
    """The other half of the pair: the square is *placed* from a measurement.

    The title guard above holds the credit block where the fit put it, so the
    square cannot walk down into the artwork while it passes.  But the code's
    `top` is read off the laid-out byline and the room it needs is predicted from
    the same byline's arithmetic, and two numbers for one line is the shape of
    every defect in this module.  So the finished page is asked the question
    directly, and the way to prove it is asked is to take the room away: with
    `_opener_code_field_floor` returning nothing, the field is the title's alone,
    the title still fits it -- so the guard above passes -- and the square's own
    last dark row lands inside the figure.

    Measured to the SYMBOL: the guard is handed the plan's codes so it can take
    the quiet zone off the element's foot, because the field reserves room for
    ink and a guard reading the box would refuse a build that clears the artwork.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    render_a5_weasyprint(edition, tmp_path / "reader.pdf")  # as authored, no refusal

    monkeypatch.setattr(adapter, "_opener_code_field_floor", lambda *_args: 0.0)
    with pytest.raises(ValidationError) as raised:
        render_a5_weasyprint(edition, tmp_path / "unreserved.pdf")

    message = str(raised.value)
    assert "article<&>" in message, "name the piece"
    # The title's own 117.8pt field, 42.0004pt down the page, and the figure's
    # own 10.0046pt of ink relief below its foot.
    assert "the opener figure's head is 169.8050pt" in message, "and the two boxes"
    # 8.2298pt more than the 45pt square overran by, which is exactly the symbol's
    # own growth: 10.5pt of square less the two quiet zones it also grew.
    assert "reaches 38.1159pt past the field" in message, "and how far past it"
    assert not (tmp_path / "unreserved.pdf").exists(), "and nothing is written"


def test_a_plate_title_set_on_more_lines_than_it_was_fitted_to_is_refused(tmp_path: Path):
    """The same divergence on the other auto-fitted block.

    A plate caption is positioned from its fitted size alone, so a line the fit
    did not budget for hangs below the plate's title box rather than widening it.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    plates = list(edition.closing_plates)
    plates[1] = replace(plates[1], title=_LOOSENING_PLATE_TITLE)
    overlong = replace(edition, closing_plates=tuple(plates))

    with pytest.raises(ValidationError) as raised:
        render_a5_weasyprint(overlong, tmp_path / "overlong.pdf")

    message = str(raised.value)
    assert f"closing plate 2 title {_LOOSENING_PLATE_TITLE!r}" in message
    assert "fitted at 32pt over 1 line(s), but Pango set it on 2" in message


def test_a_plate_caption_is_set_at_the_size_the_shared_fit_chose(tmp_path: Path):
    """The pass that sets a plate and the guard that checks it read one fit range.

    `_fit_closing_plate_titles` states the size on the element and
    `_validate_fitted_display` checks the laid-out caption against it, so both go
    through `_fitted_plate_title` and 32pt-down-to-22 is written once.  A guard
    carrying its own copy of the range would stop guarding the first time the
    range moved, so this asserts the setter against the shared fit across titles
    the fit answers differently.
    """
    titles = ("Short", "Systems in Motion", "Systems in Perpetual Onward Motion")
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    edition = replace(
        edition,
        closing_plates=tuple(
            replace(plate, title=title)
            for plate, title in zip(edition.closing_plates, titles, strict=True)
        ),
    )
    tree = _print_tree(edition)

    adapter._fit_closing_plate_titles(tree, edition)

    sizes = [
        caption.get("style", "").split(";")[0]
        for plate in tree.iter("figure")
        if plate.get("data-closing-plate")
        for caption in plate.iter("figcaption")
    ]
    assert sizes == [
        f"font-size: {adapter._fitted_plate_title(title)[0]:.4f}pt" for title in titles
    ]
    assert len(set(sizes)) > 1, "titles the shared fit answers identically prove nothing"


def test_overflow_wrap_is_not_the_reader_s_per_character_fallback():
    """Why the over-long case is refused rather than styled.

    `lines` (render.py:664-673) fills the whole measure one character at a time
    and never prefers a hyphen.  With the scaffolds in place, `overflow-wrap:
    anywhere` reproduced that exactly for a token with no break opportunity of
    its own, and diverged as soon as the token had one.  Shaping takes the
    remaining case too: a kerned line holds one more character than a summed
    line does, so the chunks no longer agree even for an unbreakable token.
    There is now no stylesheet spelling of the fallback at all, which is why the
    refusal above cannot be replaced by a style.
    """
    css = _read_print_css() + "\n#prose p { overflow-wrap: anywhere; }\n"

    def laid_out(token: str) -> list[str]:
        return _flow_lines(
            _typeset_document(f'<section id="prose"><p>{token}</p></section>', css_text=css)
        )

    plain = "supercalifragilistic" * 12
    hyphenated = "alpha-beta-" * 24 + "omega"

    assert laid_out(plain) != adapter._wrap(plain, "serif", 10, 325)
    assert laid_out(hyphenated) != adapter._wrap(hyphenated, "serif", 10, 325)


def test_bullets_are_drawn_discs_and_a_reference_list_drops_to_source_notes():
    """X16/X17: a violet disc at 14pt of indent; references at SERIF 7.2/9.4.

    And a reference *hangs*.  The baseline set every line of a bibliography
    flush, which puts an entry's turn line on the same left edge as the entry
    numbers -- three references with two turn lines printed as five items, and
    at arm's length the two bare years read as entries of their own.  The
    marker is inside the text here (`4 — `, authored, not a list marker), so
    the indent is the marker's own width and the first line is pulled back out
    of it.
    """
    document = _typeset_document(
        '<article data-article-id="a"><ul><li><p>Bullet one</p></li></ul>'
        "<h3>References</h3>"
        '<ul data-reference-list="true"><li><p>4 — Source note that runs long '
        "enough to turn onto a second line of its own, which is the whole "
        "point of the indent.</p></li></ul>"
        '<p class="provenance">Sources: hidden</p>'
        '<p class="end-mark">End / 01</p></article>'
    )
    page = document.pages[0]._page_box
    items = [
        box
        for box in adapter._walk_boxes(page)
        if getattr(box, "element_tag", None) == "li"
        and type(box).__name__ == "BlockBox"
    ]
    discs = [
        box
        for box in adapter._walk_boxes(page)
        if getattr(box, "element_tag", None) == "li::before"
    ]
    text = " ".join(
        box.text
        for box in adapter._walk_boxes(page)
        if type(box).__name__ == "TextBox"
    )

    assert len(items) == 2
    assert round(items[0].style["font_size"] * _POINTS_PER_CSS_PIXEL, 2) == 10.0
    assert round(items[0].padding_left * _POINTS_PER_CSS_PIXEL, 3) == 14.0
    assert round(items[1].style["font_size"] * _POINTS_PER_CSS_PIXEL, 2) == 7.2
    assert round(items[1].height * _POINTS_PER_CSS_PIXEL, 2) == 18.8, "two lines at 9.4"
    # `4 — ` set in the reading face at 7.2pt, hung: the first line is pulled the
    # same distance back out, so it starts where the body text starts and the
    # turn line starts under the entry's own first letter.
    hang = adapter._string_width("4 — ", "serif", 7.2)
    assert round(hang, 4) == 12.9744
    assert items[1].padding_left * _POINTS_PER_CSS_PIXEL == pytest.approx(hang)
    assert items[1].style["text_indent"].value * _POINTS_PER_CSS_PIXEL == pytest.approx(-hang)
    entry, turn = [
        next(box for box in adapter._walk_boxes(line) if type(box).__name__ == "TextBox")
        for line in list(_line_boxes(items[1]))[:2]
    ]
    # The number sits where the list's own left edge is, one hang outside the
    # column the entry's text -- and its turn line -- is set in.
    assert entry.position_x * _POINTS_PER_CSS_PIXEL == pytest.approx(
        items[1].position_x * _POINTS_PER_CSS_PIXEL
    )
    assert (turn.position_x - entry.position_x) * _POINTS_PER_CSS_PIXEL == (
        pytest.approx(hang)
    )
    # The bullet's marker is a drawn disc, so no marker glyph reaches the text --
    # nor a host font, since neither bundled face carries U+25E6.
    # `render.py:1193-1196` centres a 2.5pt disc 4pt above the first baseline.
    assert len(discs) == 1
    first_line = next(_line_boxes(items[0]))
    baseline = (first_line.position_y + first_line.baseline) * _POINTS_PER_CSS_PIXEL
    centre = (discs[0].position_y * _POINTS_PER_CSS_PIXEL) + 2.5
    assert round(baseline - centre, 3) == 4.0
    assert round(discs[0].width * _POINTS_PER_CSS_PIXEL, 3) == 5.0
    assert "◦" not in text and "•" not in text
    # The reader never prints source ids, and it always prints the end mark.
    assert "Sources:" not in text
    assert "END / 01" in text


def test_a_figureless_opener_field_follows_its_credit_block_not_a_constant(tmp_path: Path):
    """O1, recut: the field is the credit block's lowest ink plus one gap.

    The reader pinned `top=238` -- a 305.2756pt field however short the chrome
    -- and the constant was honest white on exactly one opener, the deepest
    stack the opener can carry.  The field now follows the fitted title the way
    a figure opener's does: the symbol's last dark row (or the note's own last
    line, code or none) plus `_OPENER_STANDFIRST_GAP_POINTS`, so the standfirst
    starts the same deliberate distance under every credit line.
    """
    edition = _edition(tmp_path)
    article = edition.articles[0]
    prose_article = replace(
        article,
        figures=tuple(figure for figure in article.figures if figure.anchor != "__opener__"),
    )
    edition = replace(edition, articles=(prose_article,))
    tree = _print_tree(edition)

    adapter._pin_opener_fields(tree, edition)

    header = next(
        child for piece in tree.iter("article") for child in piece if child.tag == "header"
    )
    size, lines = adapter._fitted_display(
        str(prose_article.title), 333.0079, 165.0,
        maximum=35.0, minimum=24.0, maximum_lines=4, leading_ratio=.96,
    )
    field = adapter._opener_prose_field(prose_article, size, len(lines))
    assert header.get("style") == f"height: {field:.4f}pt"
    # The title is judged against its own reservation, never against the credit
    # block's depth or the gap -- the same two-numbers split a figure opener states.
    assert header.get("data-title-field") == (
        f"{adapter._OPENER_FIGURE_FIELD_BASE + adapter._opener_title_flow(size, len(lines)):.4f}"
    )
    # This opener carries a code, so the governing ink is the symbol's last dark
    # row, and the field stands exactly one gap below it.
    code = adapter._opener_credit_code(prose_article)
    assert field == pytest.approx(
        adapter._opener_symbol_bottom(code, size, len(lines))
        + adapter._OPENER_STANDFIRST_GAP_POINTS
    )

    # The gap is measured, not chosen: the deepest opener the retired constant
    # was cut for -- a four-line title at the 35pt maximum over a 1.5pt-module
    # code -- reproduces the old 305.2756pt field to the fourth decimal, so the
    # one page the constant set right is untouched and every shallower stack
    # tightens to the same breath.
    house_module_code = SimpleNamespace(side=55.5, quiet=6.0)
    assert adapter._opener_symbol_bottom(
        house_module_code, 35.0, 4
    ) + adapter._OPENER_STANDFIRST_GAP_POINTS == pytest.approx(305.2756, abs=5e-4)

    # And the stated field really is where the prose starts: laid out, the
    # standfirst's painted baseline opens the frame the field's foot declares.
    document = _typeset_document(
        f'<article data-article-id="a"><header style="height: {field:.4f}pt">'
        '<h1>Short</h1></header>'
        f'<p class="standfirst">{_FILLER_PROSE}</p></article>'
    )
    page = document.pages[0]
    standfirst = _block_by_class(page, "standfirst")
    assert _painted_baseline_from_page_foot(
        next(_line_boxes(standfirst)), standfirst
    ) == pytest.approx(543.2756 - field - _NUDGE, abs=5e-4)


# The +0.005pt rasterizer nudge on `@page`, which every measured baseline below
# carries because it moves the whole content box and nothing inside it.
_NUDGE = .005


def test_the_editorial_opener_field_is_a_clamp_and_not_a_constant():
    """O2: `_set_reading_frame(top=min(self.y, 390))` (render.py:2091).

    An article's field is pinned at 238 outright.  The editorial's follows its own
    chrome until 390, and stops there -- so a short stack must not push the prose
    below the reader's floor, and a tall one must still carry it down.
    """

    def standfirst_baseline(field: float) -> float:
        document = _typeset_document(
            f'<section class="editorial"><header style="height: {field}pt">'
            '<p class="content-label">Label</p><h1>Title</h1>'
            '<p class="byline">By someone</p></header>'
            f'<p class="standfirst">{_FILLER_PROSE}</p></section>'
        )
        page = document.pages[0]
        standfirst = _block_by_class(page, "standfirst")
        return _painted_baseline_from_page_foot(
            next(_line_boxes(standfirst)), standfirst
        )

    # The floor is `543.2756 - 390`; a field shorter than it must not be honoured.
    assert standfirst_baseline(100.0) == pytest.approx(390.0 - _NUDGE, abs=5e-4)
    assert standfirst_baseline(153.2756) == pytest.approx(390.0 - _NUDGE, abs=5e-4)
    # Above the floor the clamp is inert and the stack carries the prose down.
    assert standfirst_baseline(200.0) == pytest.approx(
        543.2756 - 200.0 - _NUDGE, abs=5e-4
    )


def test_the_editorial_field_is_the_reader_s_own_arithmetic_on_its_fitted_title(tmp_path: Path):
    """The natural height the clamp is applied to: `72 + size * (1 + 0.96 * lines)`."""
    edition = _raster_edition(tmp_path)
    tree = _print_tree(edition)

    adapter._pin_opener_fields(tree, edition)

    header = next(
        child
        for section in tree.iter("section")
        if section.get("id") == "editorial"
        for child in section
        if child.tag == "header"
    )
    size, lines = adapter._fitted_display(
        str(edition.editorial.title), 333.0079, 135.0,
        maximum=35.0, minimum=25.0, maximum_lines=4, leading_ratio=.96,
    )
    expected = 25.0 + 12.0 + 10.0 + 12.0 + 13.0 + size * (1 + .96 * len(lines))
    assert header.get("style") == f"height: {expected:.4f}pt"


def test_an_opener_title_is_set_at_the_size_the_reader_fitted_it_to():
    """O3: `_fitted_title_box` -- first baseline one `size` below 506.2756.

    The size is a measurement and the stylesheet cannot hold it, so the adapter
    states it with the two margins that follow from it: the byline has to land
    back on `title_bottom - 10`, whatever the title turned out to be.
    """

    def opener(size: float, lines: int) -> tuple[float, float]:
        from xml.etree.ElementTree import Element, SubElement

        header = Element("header")
        title = SubElement(header, "h1")
        adapter._set_opener_title(header, size)
        text = "<br>".join(f"line {index}" for index in range(lines))
        document = _typeset_document(
            '<article data-article-id="a"><header style="height: 305.2756pt">'
            '<p class="content-label">Label</p>'
            f'<h1 style="{title.get("style")}">{text}</h1>'
            '<p class="byline">By someone</p></header>'
            '<p class="standfirst">prose</p></article>'
        )
        page = document.pages[0]
        first = _baseline_from_page_foot(next(_line_boxes(_block_of(page, "h1"))))
        byline = _baseline_from_page_foot(
            next(_line_boxes(_block_by_class(page, "byline")))
        )
        return first, byline

    for size, lines in ((35.0, 1), (35.0, 2), (24.0, 3)):
        first, byline = opener(size, lines)
        assert first == pytest.approx(506.2756 - size - _NUDGE, abs=5e-4)
        # `title_bottom` is one leading below the last baseline, and the frame is
        # set 10pt under it; the byline is drawn on that frame's own top.
        title_bottom = first - size * .96 * lines
        assert byline == pytest.approx(title_bottom - 10.0, abs=5e-4)


def _end_mark_case(spacer: float) -> tuple[float, float, float]:
    """(``self.y``, the stylesheet's painted baseline, the planned one)."""
    body = (
        f'<article data-article-id="a"><div style="height: {spacer}pt"></div>'
        '<p>one line of prose</p><p class="end-mark">End / 01</p></article>'
    )

    def painted(markup: str) -> float:
        document = _typeset_document(markup)
        mark = next(
            box
            for box in adapter._walk_boxes(document.pages[-1]._page_box)
            if type(box).__name__ == "BlockBox"
            and getattr(box, "element", None) is not None
            and "end-mark" in adapter._element_classes(box.element)
        )
        return _painted_baseline_from_page_foot(next(_line_boxes(mark)), mark)

    flow_bottom = adapter._article_flow_bottom(_typeset_document(body), "a")
    offset = adapter._end_mark_offset(flow_bottom)
    planned = painted(
        body.replace(
            'class="end-mark"',
            f'class="end-mark" style="transform: translateY({offset:.4f}pt)"',
        )
    )
    return flow_bottom, painted(body), planned


def test_the_end_mark_keeps_its_own_space_and_the_floor_is_a_refusal():
    """`baseline = self.y - 1` (render.py:2009), and the clamp beside it is not.

    Nothing pinned this before, and both halves of it were wrong: the mark was
    painted 8.53085pt high on every article, and it did not follow `self.y` at
    all.  A 20pt filler spacer leaves the article ending high on its page; 478pt
    runs it down past where ReportLab's frame clamp used to stop it.

    THE CLAMP IS GONE, AND THAT IS THE POINT.  `max(self.frame_bottom + 5, ...)`
    is the frame's number and not the mark's: on a page that over-runs it does
    not lower the mark, it *raises* it into the type the mark is meant to stand
    under.  On es p9 it raised it 7.5pt and left 5.0pt between the descenders
    and the rule against 11.2-16.9pt everywhere else, and no horizontal
    clearance rule can see that, because the crowding was never horizontal.  So
    the mark keeps its space; what stops it is a floor against collision with
    the folio, and that floor refuses rather than squeezes.
    """
    # The spacer is the whole control: a one-line article 20pt down the page
    # ends far clear of the old frame clamp, and one 478pt down ends under it.
    high_y, high_css, high_planned = _end_mark_case(20.0)
    low_y, low_css, low_planned = _end_mark_case(478.0)

    assert high_y - 1 > 50.0, "the high case must clear the old clamp or it proves nothing"
    assert low_y - 1 < 50.0, "the low case must reach past it or it proves nothing"
    # Either way the mark sets one point under `self.y`, and the stylesheet's own
    # 28.53085pt is the whole answer.
    assert high_css == pytest.approx(high_y - 1.0, abs=5e-4)
    assert high_planned == pytest.approx(high_y - 1.0, abs=5e-4)
    assert low_css == pytest.approx(low_y - 1.0, abs=5e-4)
    assert low_planned == pytest.approx(low_y - 1.0, abs=5e-4)
    assert low_planned < 50.0, "the mark went where the flow did, clamp or no clamp"
    # And the floor that is left is the folio's own line plus one reading
    # leading, below which `END / nn` and the page number read as one line of
    # chrome.  It refuses the page rather than raising the mark into the type.
    assert adapter._END_MARK_HARD_FLOOR_POINTS == pytest.approx(19.5 + 13.0)
    assert adapter._end_mark_baseline(33.5) == pytest.approx(32.5)
    with pytest.raises(ValidationError, match="over-runs by more than the mark"):
        adapter._end_mark_baseline(33.4)


def test_a_column_figure_labels_itself_one_caption_size_below_its_own_head(tmp_path: Path):
    """`_draw_figure` (render.py:786-787) sets `FIGURE nn` on `top - CAPTION_SIZE`.

    The label was 6.8pt of flow *and* 6.8pt of ink, and nothing pinned either;
    what it must be is a baseline exactly CAPTION_SIZE below the point ReportLab
    calls the figure's head, which is the block's painted top and not its flow one.
    """
    path = tmp_path / "column.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    document = _typeset_document(
        '<article data-article-id="a"><p>lead in</p>'
        '<figure data-figure-id="fig" data-figure-label="Figure">'
        f'<img src="{path.as_uri()}">'
        '<figcaption><span class="caption">Caption</span></figcaption></figure></article>'
    )
    page = document.pages[0]
    figure = _box_of(page, lambda box: getattr(box, "element_tag", None) == "figure")
    label = _box_of(
        page, lambda box: getattr(box, "element_tag", None) == "figure::before"
    )

    head = _PAGE_HEIGHT_POINTS - figure.position_y * _POINTS_PER_CSS_PIXEL
    baseline = _baseline_from_page_foot(next(_line_boxes(label)))
    assert head - baseline == pytest.approx(6.8, abs=5e-4)
    # And the label's zone is CAPTION_SIZE + BASE * 2 of the figure's own height.
    assert label.border_height() * _POINTS_PER_CSS_PIXEL == pytest.approx(13.1, abs=1e-4)


def test_every_colour_is_one_of_the_reader_s_own_tokens():
    """X23: `render.py:53-66`, and h3 is the one heading the reader sets in VIOLET."""
    ink, violet = (.055, .075, .085), (.25, .10, .43)
    document = _typeset_document(
        '<article data-article-id="a" data-figure-layouts="landscape_plate">'
        "<h2>Prose heading</h2><p>body copy</p><h3>References</h3>"
        '<div class="landscape-plate"><div class="landscape-plate-rotor">'
        "<h3>Plate anchor</h3></div></div></article>"
    )
    page = document.pages[0]

    def colour(box) -> tuple[float, ...]:
        return tuple(round(value, 6) for value in box.style["color"].coordinates)

    assert colour(_block_of(page, "p")) == ink, "body copy is INK, not a web grey"
    assert colour(_block_of(page, "h2")) == ink
    assert colour(_block_of(page, "h3")) == violet
    plate_heading = next(
        box
        for box in adapter._walk_boxes(document.pages[-1]._page_box)
        if getattr(box, "element_tag", None) == "h3"
        and type(box).__name__ == "BlockBox"
        and box.style["text_transform"] == "uppercase"
        and box.style["font_size"] * _POINTS_PER_CSS_PIXEL == pytest.approx(9.0)
    )
    assert colour(plate_heading) == ink, "a plate heading is INK whatever its tag"
    # No colour anywhere in the stylesheet that the reader does not have.
    assert "#" not in "".join(
        line.split("/*")[0]
        for line in _read_print_css().splitlines()
        if not line.lstrip().startswith("*")
    )


def test_landscape_plate_owns_its_page_and_places_the_image_as_the_reader_does(tmp_path: Path):
    """F1: 488.2756pt along the long axis, 5pt in, below a 43.6pt heading zone."""
    path = tmp_path / "plate.png"
    Image.new("RGB", (2100, 700), "white").save(path)
    document = _typeset_document(
        '<article data-article-id="a" data-figure-layouts="landscape_plate">'
        '<div class="landscape-plate"><div class="landscape-plate-rotor"><h2>Plate heading</h2>'
        f'<figure><img src="{path.as_uri()}">'
        "<figcaption><span class=\"caption\">Caption</span>"
        "<span class=\"credit\">Credit</span></figcaption></figure>"
        "</div></div><p>after the plate</p></article>"
    )

    rotor = image = None
    for box, frame in adapter._walk_boxes_in_frame(document.pages[0]._page_box):
        if getattr(box, "element_tag", None) == "img":
            rotor, image = frame, box

    assert rotor is not None, "the plate image is laid out inside the rotated frame"
    along = (image.content_box_x() - rotor.position_x) * _POINTS_PER_CSS_PIXEL
    across = (image.content_box_y() - rotor.position_y) * _POINTS_PER_CSS_PIXEL
    assert round(along, 4) == 5.0
    assert round(across, 4) == 43.6
    assert round(image.width * _POINTS_PER_CSS_PIXEL, 4) == 488.2756
    # The plate consumes the whole page: the prose after it starts a new one.
    assert _line_boxes_of(document.pages[0], "p") == []
    assert _line_boxes_of(document.pages[1], "p")
    # And a plate page still carries its folio, as `new_page` without a blank
    # header does (render.py:653-654).
    assert _typeset(
        '<div class="landscape-plate"><div class="landscape-plate-rotor"><h2>H</h2></div></div>'
    )[0][2] == pytest.approx(19.5, abs=1e-3)


def test_a_rotated_plate_box_is_reported_where_its_ink_lands():
    # The measured coordinates are the *shipped* ones: the stylesheet's
    # margin-top is 42.0004pt, i.e. the derived 41.9954 plus the rasteriser
    # nudge, and the nudge has to come back out before the box is reported.
    margin_top = 41.9954 + adapter._RASTER_NUDGE_POINTS
    rotor = _Box("div", element=_Element("div", **{"class": "landscape-plate-rotor"}),
                 x=42.52 / _POINTS_PER_CSS_PIXEL, y=margin_top / _POINTS_PER_CSS_PIXEL)
    left, bottom, width, height = _rotated_plate_box(
        42.52 + 5.0, margin_top + 43.6, 488.2756, 161.408, rotor
    )
    # The frozen ReportLab baseline records [170.52, 50.0, 161.408, 488.276].
    assert (round(left, 3), round(bottom, 3), round(width, 3), round(height, 3)) == (
        170.52, 50.0, 161.408, 488.276
    )


def test_the_tail_ornament_is_out_of_flow_at_the_frame_foot():
    """P5: 325pt wide at the frame's foot, costing no line of prose."""
    document = _typeset_document(
        '<article data-article-id="a"><p>only prose</p>'
        '<figure class="article-tail" style="height: 214pt"><img src="x"></figure></article>'
    )
    tail = next(
        box
        for box in adapter._walk_boxes(document.pages[0]._page_box)
        if getattr(box, "element", None) is not None
        and "article-tail" in (box.element.get("class") or "").split()
    )
    left = tail.position_x * _POINTS_PER_CSS_PIXEL
    bottom = _PAGE_HEIGHT_POINTS - (tail.position_y + tail.height) * _POINTS_PER_CSS_PIXEL
    assert (round(left, 3), round(bottom, 3), round(tail.width * _POINTS_PER_CSS_PIXEL, 3)) == (
        48.004, 68.995, 325.0
    )
    # One page, and its single prose line still opens on the reader's first baseline.
    assert len(document.pages) == 1
    assert _baseline_from_page_foot(
        _line_boxes_of(document.pages[0], "p")[0]
    ) == pytest.approx(543.2756 - 0.005, abs=5e-4)


def test_figure_placement_rejects_non_raster_assets(tmp_path: Path):
    path = tmp_path / "not-an-image.png"
    path.write_text("not a raster", encoding="utf-8")
    asset = HtmlAsset(
        id="figure-article-bad", role="figure", path=path, src=path.as_uri(), alt_text="bad",
        article_id="article", figure_id="bad", source_id="source", caption="", credit="",
    )
    with pytest.raises(ValidationError, match="readable raster"):
        _figure_placement(asset, 3, _Box("img", x=0, y=0, width=10, height=10))


def _band_figure(path: Path, *, layout: str = "evidence_band", anchor: str = "Anchor") -> str:
    return (
        f'<figure data-figure-id="fig" data-article-id="article" data-anchor="{anchor}" '
        f'data-layout="{layout}" data-figure-label="Figure">'
        f'<img src="{path.as_uri()}">'
        '<figcaption><span class="caption">Caption of the evidence band.</span>'
        '<span class="credit">Credit line.</span></figcaption></figure>'
    )


def _box_of(page, predicate):
    for box in adapter._walk_boxes(page._page_box):
        if predicate(box):
            return box
    return None


def test_a_band_figure_is_the_reader_s_own_figure_geometry(tmp_path: Path):
    """F20/F17: 13.1 + image + 6.3 + text * 8.6 + FIGURE_GAP, at the live width."""
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    document = _typeset_document(
        f'<article data-article-id="article"><p>lead in</p>{_band_figure(path)}</article>'
    )
    page = document.pages[0]
    figure = _box_of(page, lambda box: getattr(box, "element_tag", None) == "figure")
    image = _box_of(page, lambda box: getattr(box, "element_tag", None) == "img")
    caption = _box_of(page, lambda box: getattr(box, "element_tag", None) == "figcaption")

    width = figure.width * _POINTS_PER_CSS_PIXEL
    image_height = image.height * _POINTS_PER_CSS_PIXEL
    # `min(333.0079 / 1920, 205 / 1266)` is height-bound, and the image is centred.
    assert (round(width, 3), round(image_height, 3)) == (333.008, 205.0)
    assert round(image.width * _POINTS_PER_CSS_PIXEL, 3) == 310.9
    assert round((image.content_box_x() - figure.content_box_x()) * _POINTS_PER_CSS_PIXEL, 3) == 11.054
    # The label's zone is in flow and is the first 13.1pt of the block.
    assert round((image.position_y - figure.position_y) * _POINTS_PER_CSS_PIXEL, 4) == 13.1
    # BASE * 2 clear of the image, then one 8.6pt line per caption and credit line.
    assert round(caption.margin_top * _POINTS_PER_CSS_PIXEL, 4) == 6.3
    assert round(caption.height * _POINTS_PER_CSS_PIXEL, 4) == 17.2
    # `total_height` = 6.8 + 6.3 + image + 6.3 + text + FIGURE_GAP.
    assert round(figure.margin_height() * _POINTS_PER_CSS_PIXEL, 4) == round(
        13.1 + 205.0 + 6.3 + 17.2 + 15.75, 4
    )


def test_a_band_figure_carries_the_reader_s_caption_typography(tmp_path: Path):
    """F12/F14/F15: SERIF caption, Inter-Medium SLATE credit, and no caption rule."""
    css = _read_print_css()
    assert "border-top: .35pt solid #c9c6c0" not in css, "the caption rule is not the reader's"
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    document = _typeset_document(
        f'<article data-article-id="article"><p>lead in</p>{_band_figure(path)}</article>'
    )
    page = document.pages[0]
    caption = _box_of(page, lambda box: getattr(box, "element_tag", None) == "figcaption")
    credit = _box_of(
        page,
        lambda box: getattr(box, "element", None) is not None
        and "credit" in (box.element.get("class") or "").split(),
    )

    assert round(caption.style["font_size"] * _POINTS_PER_CSS_PIXEL, 3) == 6.8
    assert round(caption.style["line_height"][1] * _POINTS_PER_CSS_PIXEL, 3) == 8.6
    assert caption.style["border_top_width"] == 0
    assert credit.style["font_weight"] == 500
    assert [round(value, 4) for value in credit.style["color"].coordinates] == [.31, .35, .37]


def test_a_figure_frame_is_a_real_stroke_on_the_image_edge_and_costs_the_fit_nothing(
    tmp_path: Path,
):
    """F12: `_draw_contained_image` (render.py:765-767) *strokes* a 0.55pt INK rect.

    Poppler snaps a thin stroke to whole pixels at full ink and antialiases the
    same ink laid down as a fill over twice as many pixels, so a frame that is
    filled rather than stroked is a measurable ink-coverage difference on every
    figure page.  No CSS property strokes -- `outline`, `border` and
    `border-image` are all filled by WeasyPrint's `draw_rect_border` -- so the
    frame is an SVG `rect`, and this test is the guard that it stays one.
    """
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    body = f'<article data-article-id="article"><p>lead in</p>{_band_figure(path)}</article>'

    plain = _typeset_document(body)
    image = _box_of(plain.pages[0], lambda box: getattr(box, "element_tag", None) == "img")
    figure = _box_of(plain.pages[0], lambda box: getattr(box, "element_tag", None) == "figure")
    measured = adapter._measured_figure_rules(plain)
    assert measured == {"fig": adapter.MeasuredRule(1, *adapter._box_inside(figure, image))}

    tree = _parse_article_fragment(f"<p>lead in</p>{_band_figure(path)}")
    adapter._apply_figure_rules(tree, measured)
    rule = next(element for element in tree.iter("img") if element.get("class") == "figure-rule")
    source = unquote(rule.get("src").removeprefix("data:image/svg+xml,"))
    width, height = measured["fig"].width, measured["fig"].height
    # The rect is inset by the bleed and sized to the image, so the stroke it
    # carries is centred on the image's own edge, as ReportLab's is.
    assert f"width='{width:.4f}' height='{height:.4f}'" in source
    assert "fill='none' stroke='rgb(5.5%,7.5%,8.5%)' stroke-width='0.55'" in source

    painted = _typeset_document(
        body.replace(
            "</figcaption></figure>",
            f'</figcaption><img class="figure-rule" src="{rule.get("src")}" '
            f'style="{rule.get("style")}"></figure>',
        )
    )
    # The frame is out of flow: the image, and the figure it sits in, are untouched.
    assert adapter._measured_figure_rules(painted) == measured
    adapter._validate_figure_rules(painted, measured)
    # And it reaches the PDF as an actual stroke: INK, 0.55 wide, `re` then `S`.
    stroke = re.search(
        rb"0\.055 0\.075 0\.085 RG\n0\.55 w\n(?:[^\n]*\n)*?[-\d. ]+ re\nS",
        _content_streams(painted.write_pdf()),
    )
    assert stroke is not None


# --- the paint pass -----------------------------------------------------------
#
# `_painted_reader` is the pass that produces the delivered PDF, so its guard is
# the last thing standing between a frame that moved and a shipped reader.  The
# doubles below are deliberately minimal: a figure box holding an image, a text
# box, and the frame the paint pass is supposed to have added.

_PAINT_RULE = adapter.MeasuredRule(1, 0.0, 0.0, 75.0, 37.5)
_PAINT_FRAME = (-1.0, -1.0, 77.0, 39.5)  # the rule, bled on every side


def _paint_figure(rule: tuple[float, float, float, float] | None = None) -> _Box:
    children = [_Box("img", element=_Element("img", src="figure.png"), x=0, y=0, width=100, height=50)]
    if rule is not None:
        left, top, width, height = (value / _POINTS_PER_CSS_PIXEL for value in rule)
        children.append(
            _Box("img", element=_Element("img", **{"class": "figure-rule"}),
                 x=left, y=top, width=width, height=height)
        )
    return _Box("figure", element=_Element("figure", **{"data-figure-id": "fig"}),
                children=tuple(children))


def _paint_document(
    *,
    rule: tuple[float, float, float, float] | None = None,
    text_y: float = 200.0,
    pages: int = 1,
    figure_on_page: int = 1,
) -> _Document:
    text = _Box("span", element=_Element("span"), x=10, y=text_y, text="prose")
    built = []
    for number in range(1, pages + 1):
        children = [text] if number == 1 else []
        if number == figure_on_page:
            children.append(_paint_figure(rule))
        built.append(_Page(_Box(children=tuple(children))))
    return _Document(tuple(built))


_PAINT_HTML = '<figure data-figure-id="fig"><img src="figure.png"></figure>'


def _paint(monkeypatch, painted: _Document, *, document: _Document | None = None, html: str = _PAINT_HTML):
    monkeypatch.setattr(adapter, "_lay_out", lambda *args, **kwargs: painted)
    edition = SimpleNamespace(id="edition<&>")
    plan = adapter.ReaderPlan(closing_plates=0)
    return adapter._painted_reader(
        object(), html, object(), edition, plan, document or _paint_document()
    )


def test_the_paint_pass_returns_the_painted_reader_when_nothing_moved(monkeypatch):
    """The happy path: same pages, same figure box, same text, frames on the edge."""
    painted = _paint_document(rule=_PAINT_FRAME)

    assert _paint(monkeypatch, painted) is painted
    # And the frame the pass asked for is the measured box bled by 1pt on a side.
    assert adapter._measured_figure_rules(painted) == {"fig": _PAINT_RULE}


def test_the_paint_pass_refuses_a_reader_whose_text_moved(monkeypatch):
    """The docstring claims no line can move; this is what proves it.

    `_measured_figure_rules` alone cannot: `_box_inside` is relative to the
    figure's own padding box, so prose sliding down a page leaves it unchanged.
    """
    painted = _paint_document(rule=_PAINT_FRAME, text_y=200.001)

    with pytest.raises(ValidationError, match=r"moved text in edition .*1 of them displaced"):
        _paint(monkeypatch, painted)


def test_the_paint_pass_refuses_a_frame_that_moved_to_another_page(monkeypatch):
    """A figure measures the same box on any page, so the page is measured too."""
    painted = _paint_document(rule=_PAINT_FRAME, pages=2, figure_on_page=2)
    document = _paint_document(pages=2, figure_on_page=1)

    with pytest.raises(ValidationError, match="figure frames moved"):
        _paint(monkeypatch, painted, document=document)


def test_the_paint_pass_refuses_a_reader_that_lost_its_figure_boxes(monkeypatch):
    """`if not rules: return document` used to swallow a broken selector whole."""
    with pytest.raises(ValidationError, match=r"declares curated figures \['fig'\]"):
        _paint(monkeypatch, _paint_document(), document=_paint_document(rule=None, figure_on_page=0))


def test_the_paint_pass_leaves_a_reader_with_no_curated_figures_alone(monkeypatch):
    """An edition that curates nothing is not the same fact as a broken selector."""
    document = _paint_document(figure_on_page=0)
    laid_out: list[object] = []
    monkeypatch.setattr(adapter, "_lay_out", lambda *a, **k: laid_out.append(a) or document)

    assert _paint(monkeypatch, document, document=document, html="<p>no figures</p>") is document
    assert laid_out == [], "a reader with no frames to paint must not be laid out twice"


def test_a_frame_painted_twice_is_a_surplus_frame_and_not_a_silent_overwrite():
    """Keyed on the figure alone, the second frame overwrote the first and passed."""
    document = _Document((
        _Page(_Box(children=(_paint_figure(_PAINT_FRAME),))),
        _Page(_Box(children=(_paint_figure(_PAINT_FRAME),))),
    ))

    with pytest.raises(ValidationError, match="unexpected frame on page 2"):
        adapter._validate_figure_rules(document, {"fig": _PAINT_RULE})


def test_validate_figure_rules_names_a_missing_frame_and_a_displaced_one():
    absent = _Document((_Page(_Box(children=(_paint_figure(),))),))
    with pytest.raises(ValidationError, match="found None"):
        adapter._validate_figure_rules(absent, {"fig": _PAINT_RULE})

    # 1e-3 is the tolerance, so 0.01pt is displacement and not float noise.
    nudged = _Document((_Page(_Box(children=(_paint_figure((-1.01, -1.0, 77.0, 39.5)),))),))
    with pytest.raises(ValidationError, match="expected .* on page 1, found"):
        adapter._validate_figure_rules(nudged, {"fig": _PAINT_RULE})


def test_measured_figure_rules_refuses_one_figure_laid_out_in_two_boxes():
    figure = _Box("figure", element=_Element("figure", **{"data-figure-id": "fig"}),
                  children=(_Box("img", element=_Element("img"), x=0, y=0, width=100, height=50),))
    moved = _Box("figure", element=_Element("figure", **{"data-figure-id": "fig"}),
                 children=(_Box("img", element=_Element("img"), x=0, y=0, width=100, height=60),))

    with pytest.raises(ValidationError, match="two different"):
        adapter._measured_figure_rules(_Document((_Page(_Box(children=(figure, moved))),)))


def test_the_frame_image_is_not_measured_as_the_figure_it_frames():
    """`_is_figure_rule` is the filter; without it the paint pass never settles."""
    document = _Document((_Page(_Box(children=(_paint_figure(_PAINT_FRAME),))),))

    assert adapter._measured_figure_rules(document) == {"fig": _PAINT_RULE}


def test_the_rasteriser_nudge_is_taken_out_of_reported_geometry_but_not_of_scale(tmp_path: Path):
    """The stylesheet's +0.005pt is a translation, so it moves y and nothing else."""
    asset = _image_asset(tmp_path)
    nudged = _Box("img", element=_Element("img", src=asset.src),
                  x=40, y=100 + adapter._RASTER_NUDGE_POINTS / _POINTS_PER_CSS_PIXEL,
                  width=200, height=100)
    clean = _Box("img", element=_Element("img", src=asset.src), x=40, y=100, width=200, height=100)

    reported = _figure_placement(asset, 2, nudged)
    # 595.2756 - 75 - 75 = 445.2756: the reader's own datum, nudge removed.
    assert reported.box_points == (30.0, 445.276, 150.0, 75.0)
    # A nudged and an unnudged box differ by the nudge in y and in nothing else.
    unnudged = _figure_placement(asset, 2, clean)
    assert unnudged.box_points == (30.0, 445.281, 150.0, 75.0)
    assert reported.effective_ppi == unnudged.effective_ppi == 576.0


def test_the_opener_kicker_is_flushed_by_its_ink_and_still_sets_on_one_line():
    """`_tracked_label` (render.py:1441-1466) puts the *last glyph* on the edge.

    CSS emits a letter-space after the last character too, so `space-between`
    flushes a box that is one `letter-spacing` wider than its ink and the kicker
    hangs .45pt short.  The compensation is a transform, because the obvious
    alternative -- a negative `margin-right` -- shortens the box WeasyPrint
    breaks lines against: measured, `AN ORIGINAL ARGUMENT` wrapped its last word
    onto a second line, which at `line-height: 0` lands in the same extracted
    band and reorders the page's words.  Both halves are asserted here.
    """
    document = _typeset_document(
        '<article data-article-id="article"><header>'
        '<p class="content-label"><span class="label-primary">Feature 01</span>'
        '<span class="label-secondary">An original argument</span></p>'
        "<h1>Title</h1></header><p>body</p></article>"
    )
    page = document.pages[0]
    secondary = _box_of(
        page,
        lambda box: getattr(box, "element", None) is not None
        and "label-secondary" in (box.element.get("class") or "").split(),
    )

    # The flushed item's border box ends on the article rail's right edge; the
    # transform then carries its ink the trailing letter-space further right.
    assert round((secondary.position_x + secondary.width) * _POINTS_PER_CSS_PIXEL, 4) == 373.0039
    ((function, (along, across)),) = secondary.style["transform"]
    assert function == "translate"
    assert (round(along.value * _POINTS_PER_CSS_PIXEL, 4), across.value) == (0.45, 0)
    # One line box, so the three words keep their reading order in the band.
    lines = [box for box in adapter._walk_boxes(secondary) if type(box).__name__ == "LineBox"]
    assert len(lines) == 1
    assert "".join(
        box.text for box in adapter._walk_boxes(lines[0]) if isinstance(getattr(box, "text", None), str)
    ) == "AN ORIGINAL ARGUMENT"


def test_every_raster_the_reader_places_declares_interpolate_false(tmp_path: Path):
    """ReportLab writes no `/Interpolate`, so the baseline's rasters default to false.

    WeasyPrint's default is `image-rendering: auto`, which it maps to
    `/Interpolate true` on the image XObject *and* on its soft mask.  Measured on
    edition 002 that was 17 image objects plus one soft mask per language whose
    pixel data was bit-identical to the baseline's and whose only difference was
    the flag.
    """
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    document = _typeset_document(
        f'<article data-article-id="article"><p>lead in</p>{_band_figure(path)}</article>'
    )
    pdf = document.write_pdf()

    assert b"/Interpolate true" not in pdf
    assert b"/Interpolate false" in pdf


def test_a_compact_band_is_260pt_centred_in_the_live_width(tmp_path: Path):
    """F5: COMPACT_FIGURE_WIDTH, a 170pt image cap and a 12pt gap, not FIGURE_GAP."""
    path = tmp_path / "compact.png"
    Image.new("RGB", (2048, 1146), "white").save(path)
    document = _typeset_document(
        '<article data-article-id="article"><p>lead in</p>'
        + _band_figure(path, layout="compact_band")
        + "</article>"
    )
    page = document.pages[0]
    figure = _box_of(page, lambda box: getattr(box, "element_tag", None) == "figure")
    image = _box_of(page, lambda box: getattr(box, "element_tag", None) == "img")

    assert round(figure.width * _POINTS_PER_CSS_PIXEL, 3) == 260.0
    assert round(image.height * _POINTS_PER_CSS_PIXEL, 3) == 145.488
    # The band is centred in the 333.0079pt live width, not in the reading measure.
    assert round(figure.content_box_x() * _POINTS_PER_CSS_PIXEL, 3) == 80.504
    trailing = figure.margin_height() - figure.height
    assert round(trailing * _POINTS_PER_CSS_PIXEL, 3) == 12.0


def test_a_band_that_leaves_under_four_reading_lines_opens_a_new_page(tmp_path: Path):
    """F3: `band_bottom - 4 * reading_leading < self.bottom` moves what follows."""
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    tree = _parse_article_fragment(
        '<p>' + " ".join(["alpha bravo charlie delta echo foxtrot golf"] * 25) + "</p>"
        + _band_figure(path)
        + "<p>trailing prose</p>"
    )
    adapter._install_flow_clearances(tree)
    clearance = [
        element for element in tree.iter("div")
        if "band-clearance" in adapter._element_classes(element)
    ]
    assert len(clearance) == 1
    # Four 13pt reading lines, and the CSS frame foot is the reader's own.
    assert clearance[0].get("style") == "height: 52.0000pt; margin-bottom: -52.0000pt"


def test_a_landscape_plate_article_reserves_its_own_12_2pt_reading_leading():
    tree = _parse_article_fragment("<h2>Heading</h2>")
    for article in tree.iter("article"):
        article.set("data-figure-layouts", "landscape_plate")
        assert round(adapter._band_clearance_height(article), 4) == 48.8


def test_a_heading_reserves_the_reader_s_25pt_and_a_band_anchor_does_not(tmp_path: Path):
    """X8: `block` reserves 25pt below a heading; a band's anchor is the band's."""
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    tree = _parse_article_fragment(
        "<h2>Prose heading</h2><p>body</p><h2>Anchor</h2>" + _band_figure(path)
    )
    adapter._install_flow_clearances(tree)
    classes = [
        next(iter(adapter._element_classes(child)), child.tag)
        for child in next(tree.iter("article"))
    ]
    assert classes == ["h2", "heading-clearance", "p", "h2", "figure", "band-clearance"]
    heading_clearance = next(
        element for element in tree.iter("div")
        if "heading-clearance" in adapter._element_classes(element)
    )
    assert heading_clearance.get("style") == "height: 25.0000pt; margin-bottom: -25.0000pt"


def test_an_opener_figure_field_is_the_fitted_title_s_own_depth(tmp_path: Path):
    """O1/F6: the field runs to the figure's head, wherever the title reached.

    As shipped, which means with a source code: the field is then the deeper of
    the title's own reservation and the depth the code's own square needs to clear
    the artwork (`_opener_code_field_floor`), and the two are stated separately
    because only the title is judged against the title's.  An opener with no code
    states one number, and it is the title's.
    """
    edition = _edition(tmp_path)
    _write_rasters(tmp_path)
    tree = _print_tree(edition)
    adapter._pin_opener_fields(tree, edition)
    header = next(
        child for article in tree.iter("article") for child in article if child.tag == "header"
    )
    size, lines = adapter._fitted_display(
        "Article <&>", 333.0079, 165.0, maximum=30.0, minimum=24.0, maximum_lines=4,
        leading_ratio=.96,
    )
    title_field = 59 + size * (1 + .96 * len(lines))
    floor = adapter._opener_code_field_floor(edition.articles[0], size, len(lines))

    assert header.get("data-title-field") == f"{title_field:.4f}"
    assert floor > title_field, "this opener's code is what makes the two differ"
    assert header.get("style") == f"height: {floor:.4f}pt"
    # And the depth the field borrowed comes back out of the image's own cap, so
    # the code cannot cost the article a page.
    image = next(
        image
        for article in tree.iter("article")
        for figure in article.iter("figure")
        if figure.get("data-anchor") == "__opener__"
        for image in figure.iter("img")
    )
    assert image.get("style") == f"max-height: {270 - (floor - title_field):.4f}pt"

    bare = replace(edition, articles=(replace(edition.articles[0], source_url=None),))
    bare_tree = _print_tree(bare)
    adapter._pin_opener_fields(bare_tree, bare)
    bare_header = next(
        child for article in bare_tree.iter("article") for child in article if child.tag == "header"
    )
    assert bare_header.get("style") == f"height: {title_field:.4f}pt"
    assert bare_header.get("data-title-field") == f"{title_field:.4f}"


def test_an_adaptive_band_shrinks_to_the_page_it_was_dispatched_from(tmp_path: Path):
    """F4: the image gives back height rather than the band giving up the page."""
    path = tmp_path / "adaptive.png"
    Image.new("RGB", (1920, 1520), "white").save(path)
    figure = type("Figure", (), {})()
    figure.path, figure.caption, figure.credit = path, "Caption.", "Credit."
    image_height, total = adapter._figure_block_geometry(figure, 333.0079, 205.0)

    assert round(image_height, 3) == 205.0
    # 6.8 + 6.3 + 205 + 6.3 + 2 * 8.6 + 15.75
    assert round(total, 3) == round(13.1 + 205.0 + 6.3 + 17.2 + 15.75, 3)
    # A band dispatched from y 330.976 with a one-line h2 above it cannot hold
    # the full 205, and the reader hands the difference to the image.
    # `_evidence_band` measures its anchor heading at 20.5pt + 10, not at the
    # 21.5pt + 11 `block` draws it with -- the quirk the shrink is derived from.
    heading = adapter._band_heading_height("h2", "Model economics")
    assert round(heading, 3) == 30.5
    available = 330.976 - heading - 45.0 - (total - image_height)
    assert available < 205.0
    assert round(adapter._figure_block_geometry(figure, 333.0079, available)[0], 3) == round(
        available, 3
    )


def test_an_adaptive_shrink_merges_onto_the_giveback_the_opener_already_stated(tmp_path: Path):
    """The opener's own `max-height` is the code's giveback and must survive.

    No `adaptive_band` is anchored to an opener in any edition today, but
    `media_schema` permits `layout: adaptive_band` with `anchor: __opener__`, and
    `_apply_adaptive_images` runs after `_pin_opener_fields` in the same pass: a
    style attribute written over rather than merged would drop the depth the
    field borrowed for the code's square, and the opener would come out taller
    than the adapter reserved.
    """
    edition = _edition(tmp_path)
    _write_rasters(tmp_path)
    tree = _print_tree(edition)
    adapter._pin_opener_fields(tree, edition)
    image = next(
        image
        for article in tree.iter("article")
        for figure in article.iter("figure")
        if figure.get("data-anchor") == "__opener__"
        for image in figure.iter("img")
    )
    giveback = image.get("style") or ""
    assert giveback.startswith("max-height: "), "the opener stated its giveback"

    adapter._apply_adaptive_images(tree, {"opener-figure": 180.0})

    assert image.get("style") == f"{giveback}; max-height: 180.0000pt"


def test_a_closing_plate_bleeds_its_art_to_the_head_under_a_fitted_violet_title(tmp_path: Path):
    """P2: grid_box(0, 6) from y 205 to the trim, and a 32 -> 22pt VIOLET title."""
    path = tmp_path / "plate.png"
    Image.new("RGB", (900, 1200), "white").save(path)
    document = _typeset_document(
        f'<figure class="closing-plate" data-closing-plate="1"><img src="{path.as_uri()}">'
        '<figcaption style="font-size: 32.0000pt; line-height: 32.0000pt; top: 390.0642pt">'
        "Systems in Motion</figcaption></figure>"
    )
    page = document.pages[0]
    image = _box_of(page, lambda box: getattr(box, "element_tag", None) == "img")
    caption = _box_of(page, lambda box: getattr(box, "element_tag", None) == "figcaption")

    top = _PAGE_HEIGHT_POINTS - image.content_box_y() * _POINTS_PER_CSS_PIXEL
    assert round(top, 4) == _PAGE_HEIGHT_POINTS, "the art bleeds to the sheet's head"
    assert round(image.height * _POINTS_PER_CSS_PIXEL, 4) == 390.2756
    assert round(image.width * _POINTS_PER_CSS_PIXEL, 4) == 333.0079
    assert image.style["object_fit"] == "cover"
    assert round(caption.width * _POINTS_PER_CSS_PIXEL, 4) == 275.9317
    assert [round(value, 4) for value in caption.style["color"].coordinates] == [.25, .10, .43]
    baseline = _baseline_from_page_foot(next(_line_boxes(caption)))
    # `168 - size`, less the page's own +0.005pt rasterizer nudge.
    assert baseline == pytest.approx(168.0 - 32.0 - 0.005, abs=5e-4)


def test_a_closing_plate_title_is_fitted_and_placed_by_the_adapter(tmp_path: Path):
    edition = _raster_edition(tmp_path)
    tree = _print_tree(edition)
    adapter._limit_closing_plates(tree, 3)
    adapter._fit_closing_plate_titles(tree, edition)
    styles = [
        caption.get("style")
        for plate in tree.iter("figure")
        if "closing-plate" in adapter._element_classes(plate)
        for caption in plate.iter("figcaption")
    ]

    assert len(styles) == 3
    for style, title in zip(styles, [plate.title for plate in edition.closing_plates]):
        size, _lines = adapter._fitted_display(
            title, 275.9317, 92.0, maximum=32.0, minimum=22.0, maximum_lines=2, leading_ratio=1.0
        )
        top = 385.2802 + adapter._DISPLAY_SOLID_BASELINE_HEAD * size
        assert style == f"font-size: {size:.4f}pt; line-height: {size:.4f}pt; top: {top:.4f}pt"


def test_a_figure_under_300_ppi_at_its_placement_is_refused(tmp_path: Path):
    """F18: the reader's own placement floor, in the reader's own words."""
    path = tmp_path / "small.png"
    Image.new("RGB", (600, 300), "white").save(path)
    asset = HtmlAsset(
        id="figure-article-small", role="figure", path=path, src=path.as_uri(), alt_text="a",
        article_id="article", figure_id="small", source_id="source", caption="c", credit="d",
    )
    box = _Box("img", x=0, y=0, width=333.0079 * 96 / 72, height=166.5 * 96 / 72)
    with pytest.raises(ValidationError, match=r"resolves to 129.7 ppi.*minimum is 300 ppi"):
        _figure_placement(asset, 5, box)
    # Furniture is drawn with `_draw_image_fill`, which the reader never checks.
    plate = replace(asset, role="closing_plate", figure_id="plate")
    assert _figure_placement(plate, 5, box).effective_ppi == 129.7


def test_print_contrast_reaches_curated_figures_and_no_other_artwork(tmp_path: Path):
    """F19: `prepare_print_image` reaches figures and the tail ornament beside
    them, and never cover art or a closing plate.  The ornament is authored
    house artwork that should never need the escalation -- which is exactly
    what a preflight exists to verify, so a pale one is treated like a pale
    figure rather than shipped soft."""
    from magazine.image_contrast import prepare_print_image

    pale = tmp_path / "pale.png"
    image = Image.new("RGB", (400, 400), (255, 255, 255))
    for x in range(400):
        image.putpixel((x, 200), (208, 208, 208))
    image.save(pale)
    assert prepare_print_image(pale).adjusted, "the fixture needs the treatment to be a test"

    tree = _parse_article_fragment(
        f'<figure data-figure-id="fig"><img src="{pale.as_uri()}"></figure>'
        f'<figure class="article-tail"><img src="{pale.as_uri()}"></figure>',
        plates=1,
    )
    for plate in tree.iter("figure"):
        for image_element in plate.iter("img"):
            if "closing-plate" in adapter._element_classes(plate):
                image_element.set("src", pale.as_uri())
    adapter._apply_print_contrast(tree)

    treated = {
        next(iter(adapter._element_classes(figure)), figure.get("data-figure-id") or "plate"):
        image_element.get("src").startswith("data:image/png;base64,")
        for figure in tree.iter("figure")
        for image_element in figure.iter("img")
    }
    assert treated == {"fig": True, "article-tail": True, "closing-plate": False}
    # The placement still names the file the edition curated, not the derivative.
    figure = next(element for element in tree.iter("figure") if element.get("data-figure-id"))
    assert next(figure.iter("img")).get("data-print-source") == pale.as_uri()


def test_print_contrast_refuses_an_undecodable_curated_figure(tmp_path: Path):
    path = tmp_path / "broken.png"
    path.write_text("not a raster", encoding="utf-8")
    tree = _parse_article_fragment(
        f'<figure data-figure-id="fig"><img src="{path.as_uri()}"></figure>'
    )
    with pytest.raises(ValidationError, match="Cannot decode curated figure fig"):
        adapter._apply_print_contrast(tree)


def test_print_contrast_names_a_tail_ornament_as_the_ornament_it_is(tmp_path: Path):
    """The pass reaches two kinds of artwork, and a refusal names which it read.

    The ornament prints again, so this branch is live -- and a tail band has no
    `data-figure-id` to be named by, which is exactly why the message cannot call
    everything it reads a curated figure.
    """
    path = tmp_path / "broken-tail.png"
    path.write_text("not a raster", encoding="utf-8")
    tree = _parse_article_fragment(
        f'<figure class="article-tail"><img src="{path.as_uri()}"></figure>'
    )
    with pytest.raises(ValidationError, match="Cannot decode article tail art"):
        adapter._apply_print_contrast(tree)


def test_a_band_pushed_to_a_new_page_keeps_the_previous_page_s_margin_mirror():
    """`band_x` is computed before `can_bridge_current_page` decides (render.py:884)."""
    class _Doc:
        pages = (
            _Page(_Box(children=(
                _Box("p", element=_Element("p", **{"data-band-bridge": "fig"}),
                     x=0, y=100, width=400, height=100),
            ))),
            _Page(_Box(children=(
                _Box("figure", element=_Element("figure", **{"data-figure-id": "fig"}),
                     x=0, y=0, width=400, height=300),
            ))),
        )

    # The bridge ends on page 1 (a recto, inner margin 44) and the band lands on
    # page 2 (a verso, outer margin 42.5197), so the band keeps the recto's edge.
    assert adapter._measured_band_offsets(_Doc()) == (("fig", pytest.approx(1.4803, abs=1e-4)),)

    class _Same(_Doc):
        pages = (_Doc.pages[0], _Page(_Box()))

    # A band that bridges its own page inherits nothing.
    assert adapter._measured_band_offsets(_Same()) == ()


def test_a_band_offset_is_stated_on_the_figure_without_losing_its_style():
    tree = _parse_article_fragment('<figure data-figure-id="fig" style="max-height: 9pt"></figure>')
    adapter._apply_band_offsets(tree, {"fig": -1.4803})
    figure = next(element for element in tree.iter("figure"))
    assert figure.get("style") == "max-height: 9pt; left: -1.4803pt"


# --- Runt control -----------------------------------------------------------
#
# A paragraph whose last line is one short word strands that word over white
# space.  CSS has no primitive for it -- `orphans` and `widows` count lines
# across a *page* break -- so the adapter measures the laid-out page and binds
# the last two words of the offending blocks with U+00A0 on the next pass.

_RUNTING_PROSE = "The harness records every run and the reviewer reads it before each gate."
_SETTLED_PROSE = (
    "The harness records every single run and the reviewer reads it before the gate."
)


def _runt_document(body: str, binds: tuple[str, ...] = ()):
    """``body`` laid out after exactly the two runt passes ``_lay_out`` runs."""
    HTML, CSS, FontConfiguration = _weasyprint_types()
    font_config = FontConfiguration()
    stylesheet = CSS(
        string=_read_print_css(),
        base_url=resources.files("magazine").joinpath("assets").as_uri() + "/",
        font_config=font_config,
    )
    source = HTML(
        string=f'<main data-edition-id="runts">{body}</main>',
        base_url=Path.cwd().as_uri() + "/",
    )
    tree = source.etree_element
    adapter._key_prose_blocks(tree)
    adapter._bind_paragraph_tails(tree, binds)
    return source.render(stylesheets=[stylesheet], font_config=font_config)


def _keyed_lines(document, key: str) -> list[str]:
    return [
        adapter._box_text(line)
        for page in document.pages
        for box in adapter._walk_boxes(page._page_box)
        if type(box).__name__ == "BlockBox"
        and getattr(box, "element", None) is not None
        and box.element.get(adapter._RUNT_KEY) == key
        for line in adapter._walk_boxes(box)
        if type(line).__name__ == "LineBox"
    ]


def _article(prose: str) -> str:
    return f'<article id="a" data-article-id="a"><p>{prose}</p></article>'


def test_a_stranded_last_word_is_bound_to_the_one_before_it():
    """The repair, end to end, on a paragraph engineered to strand its last word.

    The bind costs the paragraph no line: under greedy line breaking the pair
    either fits the line the stranded word's neighbour was on, or moves down
    with it.  It also costs the manuscript no character -- one space becomes a
    non-breaking space and nothing else about the text changes.
    """
    unbound = _runt_document(_article(_RUNTING_PROSE))
    before = _keyed_lines(unbound, "0")

    assert before[-1] == "gate.", "the fixture no longer strands its last word"

    binds = adapter._measured_runt_binds(unbound)
    after = _keyed_lines(_runt_document(_article(_RUNTING_PROSE), binds), "0")

    assert binds == ("0",)
    assert after[-1] == "each gate."
    assert len(after) == len(before)
    assert " ".join(after).replace(" ", " ") == _RUNTING_PROSE


def test_a_last_line_that_already_holds_two_words_is_left_alone():
    document = _runt_document(_article(_SETTLED_PROSE))

    assert _keyed_lines(document, "0")[-1] == "the gate."
    assert adapter._measured_runt_binds(document) == ()


def test_a_final_word_wide_enough_to_read_as_a_short_line_is_not_a_runt():
    """The threshold is the defect's own definition, and it is not zero.

    A single-word last line is only a runt when the word is short.  The
    independent review drew its line between 11.6% and 17.6% of the measure and
    the observations leave 14.6%-16.4% empty, which is why 15% can move either
    way without reclassifying anything.  Both fixtures below end on one word;
    only the short one is repaired.
    """
    measure = 325.0
    short = _runt_document(_article(_RUNTING_PROSE))
    long_word = "The harness records every run and the reviewer reads it before recomposition."
    wide = _runt_document(_article(long_word))

    assert _keyed_lines(wide, "0")[-1] == "recomposition."
    assert adapter._string_width("gate.", "serif", 10.0) < measure * adapter._RUNT_MEASURE_FRACTION
    assert (
        adapter._string_width("recomposition.", "serif", 10.0)
        > measure * adapter._RUNT_MEASURE_FRACTION
    )
    assert adapter._measured_runt_binds(short) == ("0",)
    assert adapter._measured_runt_binds(wide) == ()


def test_a_pair_that_could_not_fit_the_measure_is_never_bound():
    """The cure may not manufacture the disease it would be refused for.

    Binding a pair wider than the measure leaves Pango no break to take, and
    `_validate_reader_measures` would refuse the build over a repair this module
    chose rather than over anything an editor wrote.
    """
    stranded = [(420.0, "supercalifragilistic" * 5), (20.0, "gate.")]

    assert not adapter._is_runt(stranded, measure=433.0, size=13.3)
    # A full penultimate line and a short last word: the case the bind is for.
    assert adapter._is_runt([(420.0, "before each"), (20.0, "gate.")], 433.0, 13.3)


def test_a_bind_that_would_open_a_second_short_line_is_refused():
    """The cure may not be worse than the defect, and the line is at a third.

    The word the bind takes off the penultimate line is known without laying the
    paragraph out again: greedy breaking moves nothing above it, so the line
    comes out exactly as wide as it is now less its own last word.

    THE THRESHOLD WAS A FIFTH AND A FIFTH WAS TOO TIGHT.  It refused en p11,
    en p29 and two reference entries in each language, and every one of them was
    worse for it -- `surrounding context.` at 98.6pt became `context.` at 37.8pt,
    and en p11 came out with three one-word last lines inside twenty lines of a
    column -- because a penultimate line 22-30% short of an *unjustified* measure
    is rag and not a fault, while a last line of one short word is a runt
    whatever stands above it.
    """
    measure, size = 433.0, 13.3
    # The bound word's own width is what the penultimate line pays.
    short_word = adapter._string_width(" each", "serif", size)
    long_word = adapter._string_width(" surrounding", "serif", size)
    assert long_word > short_word

    # A penultimate line that can afford the word it gives up.
    assert adapter._is_runt([(420.0, "before each"), (20.0, "gate.")], measure, size)
    # ...and the same paragraph where it cannot: a third of the measure is the line.
    opened = measure * adapter._RUNT_MAX_RAG_FRACTION
    assert adapter._is_runt(
        [(measure - opened + short_word + 0.5, "before each"), (20.0, "gate.")], measure, size
    )
    assert not adapter._is_runt(
        [(measure - opened + short_word - 0.5, "before each"), (20.0, "gate.")], measure, size
    )
    # A third, and it now stands above every bind edition 002 asks for: they open
    # between 4.9% and 29.5% of their own measures, the largest being en p29's
    # `surrounding context.`, which the old fifth refused and which is the
    # paragraph this rule was written from.
    assert adapter._RUNT_MAX_RAG_FRACTION == pytest.approx(0.33)
    assert adapter._RUNT_MAX_RAG_FRACTION > 0.295


def test_only_reading_flow_prose_is_keyed_for_runt_control(tmp_path: Path):
    """Chrome, contents furniture and fitted display type carry no key.

    An opener title and a plate caption are auto-fitted, and
    `_validate_fitted_display` checks the laid-out line count against the count
    their size was chosen for -- a bind inside one would move that line count
    out from under its own guard.  Opener chrome sits inside a field whose
    height the adapter states, so a bind there would change a reserved field
    rather than a rag.  A loose list item is keyed once, on its paragraph.
    """
    edition = _edition(tmp_path)
    tree = _print_tree(edition)
    adapter._key_prose_blocks(tree)

    keyed = [element for element in tree.iter() if element.get(adapter._RUNT_KEY) is not None]
    tags = {str(element.tag) for element in keyed}
    classes = {name for element in keyed for name in adapter._element_classes(element)}

    # `li` is in the bindable set defensively; this pipeline always wraps a
    # list item's text in a paragraph, so no `li` carries a key of its own.
    assert tags == {"p", "span"} and tags <= adapter._BINDABLE_TAGS
    assert classes <= {"standfirst", "caption", "credit"}
    assert not classes & adapter._UNBINDABLE_CLASSES
    # One key per text block, and never one on a block that contains another.
    assert len({element.get(adapter._RUNT_KEY) for element in keyed}) == len(keyed)
    assert not [
        element for element in keyed if any(child.get(adapter._RUNT_KEY) for child in element)
    ]
    # The contents sheet, the opener headers and the plate caption are outside.
    assert not [
        element
        for parent in tree.iter()
        if str(parent.tag) in {"header", "nav"}
        for element in parent.iter()
        if element.get(adapter._RUNT_KEY) is not None
    ]


def test_a_bind_reaches_the_final_word_through_its_own_markup():
    """The last word may be inside an ``em``, and the space before it elsewhere."""
    HTML, _CSS, _FontConfiguration = _weasyprint_types()
    tree = HTML(
        string=(
            '<main data-edition-id="x"><article id="a" data-article-id="a">'
            "<p>One two three <em>four</em></p>"
            "<p>One two <em>three four</em></p>"
            "</article></main>"
        ),
        base_url=Path.cwd().as_uri() + "/",
    ).etree_element
    adapter._key_prose_blocks(tree)
    adapter._bind_paragraph_tails(tree, ("0", "1"))
    paragraphs = list(next(tree.iter("article")).iter("p"))

    # The separator lives in the paragraph's own text, before the `em`.
    assert paragraphs[0].text == "One two three "
    # ...and here inside the `em`, between its two words.
    assert paragraphs[1].text == "One two "
    assert next(paragraphs[1].iter("em")).text == "three four"


def test_a_bound_pair_reaches_the_pdf_text_layer_as_an_ordinary_space():
    """The bind is one character of layout and no characters of content.

    A `white-space: nowrap` span around the pair would break the text layer the
    way one box per token used to: WeasyPrint gives every inline box its own
    text matrix and writes no space glyph between two of them.  Keeping the pair
    in a single text run keeps the separator extractable, and every bundled face
    carries U+00A0, so nothing falls back to a host font to set it.
    """
    import io

    from pypdf import PdfReader

    document = _runt_document(_article(_RUNTING_PROSE), ("0",))
    text = PdfReader(io.BytesIO(document.write_pdf())).pages[0].extract_text()

    assert " " not in text
    assert _RUNTING_PROSE in " ".join(text.split())


def test_the_runt_binds_are_carried_forward_rather_than_re_measured():
    """A bound paragraph no longer has a runt, so the plan has to accumulate.

    Re-measuring alone would unbind every repaired paragraph on the next pass
    and oscillate; the settle check in `_render_to_signature` is an equality, so
    the field it compares must be monotone.
    """
    document = _runt_document(_article(_RUNTING_PROSE), ("0",))

    assert adapter._measured_runt_binds(document) == ()

    edition = SimpleNamespace(articles=(), closing_plates=(), raw={})
    plan = adapter._measured_plan(document, edition, ("0", "7"))

    assert plan.runt_binds == ("0", "7")


# --- Hyphenation -------------------------------------------------------------
#
# Body prose hyphenates (`hyphens: auto`, limits 6 3 3, in weasyprint-a5.css)
# and nothing else does: headings and fitted titles answer to
# `_validate_fitted_display`'s line counts, chrome is drawn to fixed metrics
# inside stated fields, and a bibliography is proper nouns.  WeasyPrint 69 has
# no `hyphenate-limit-lines`, so ladders are measured off the laid-out lines
# and reported rather than refused.

_HYPHENATING_PROSE = (
    "Extraordinariamente desproporcionadamente incuestionablemente "
    "incomprensiblemente institucionalmente irreversiblemente "
    "internacionalmente descentralizadamente inconstitucionalmente "
    "contraproducentemente gubernamentalmente latinoamericanamente "
    "contemporáneamente responsabilidades."
)


def _hyphenating_document(body: str, binds: tuple[str, ...] = ()):
    """``body`` laid out as ``_runt_document`` lays it, under a Spanish lang.

    WeasyPrint's UA stylesheet maps the ``lang`` attribute to the style the
    hyphenator reads (`[lang] { -weasy-lang: attr(lang) }`), exactly as the
    semantic edition's ``html lang`` reaches a build, so `hyphens: auto` is
    live here iff it is live there.
    """
    HTML, CSS, FontConfiguration = _weasyprint_types()
    font_config = FontConfiguration()
    stylesheet = CSS(
        string=_read_print_css(),
        base_url=resources.files("magazine").joinpath("assets").as_uri() + "/",
        font_config=font_config,
    )
    source = HTML(
        string=f'<main lang="es" data-edition-id="hyphens">{body}</main>',
        base_url=Path.cwd().as_uri() + "/",
    )
    tree = source.etree_element
    adapter._key_prose_blocks(tree)
    adapter._bind_paragraph_tails(tree, binds)
    return source.render(stylesheets=[stylesheet], font_config=font_config)


def test_prose_hyphenates_and_chrome_headings_and_references_never_do():
    """`hyphens: auto` reaches reading prose and only reading prose.

    Every excluded block below carries the same hyphenation-hungry words as
    the paragraph that does hyphenate, so a leak would show as a hyphen and
    not as a silently-passing style assertion.  The styles are read off the
    laid-out boxes rather than restated from the stylesheet, and
    `_measured_hyphenation` -- the runt binder's view of the same styles --
    must agree: the prose block yields the (6, 3, 3) Spanish dictionary the
    stylesheet states, the standfirst yields nothing.
    """
    long_words = _HYPHENATING_PROSE
    body = (
        '<article id="a" data-article-id="a">'
        "<header><h1>Responsabilidades interdepartamentales extraordinariamente"
        " descentralizadas</h1>"
        '<p class="byline">POR DEPARTAMENTOS GUBERNAMENTALES INTERNACIONALES'
        " EXTRAORDINARIAMENTE DESCENTRALIZADOS</p></header>"
        f'<p class="standfirst">{long_words}</p>'
        f"<p>{long_words}</p>"
        "<h2>Independencia interdepartamental extraordinariamente"
        " incuestionable</h2>"
        f"<ul><li>{long_words}</li></ul>"
        f'<ul data-reference-list="true"><li>1 — {long_words}</li></ul>'
        "</article>"
    )
    document = _hyphenating_document(body)

    blocks: dict[tuple[str, str], list] = {}
    for page in document.pages:
        for box in adapter._walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if element is None or type(box).__name__ != "BlockBox":
                continue
            label = (str(box.element_tag), (element.get("class") or "").strip())
            blocks.setdefault(label, []).append(box)

    def lines(box) -> list[str]:
        return [
            adapter._box_text(line)
            for line in adapter._walk_boxes(box)
            if type(line).__name__ == "LineBox"
        ]

    prose = blocks[("p", "")][0]
    assert prose.style["hyphens"] == "auto"
    assert tuple(prose.style["hyphenate_limit_chars"]) == (6, 3, 3)
    assert adapter._measured_hyphenation(prose.style) == adapter._Hyphenation(
        "es", 6, 3, 3, "‐"
    )
    assert any(line.endswith("‐") for line in lines(prose))
    # No fragment shorter than the stated limits reaches a page: 6-letter
    # minimum word, 3 letters on each side of every break the prose takes.
    for line in lines(prose):
        if line.endswith("‐"):
            assert len(line.rstrip("‐").rsplit(" ", 1)[-1]) >= 3

    # The two list items set the same words; only the reading-flow one breaks.
    # A list item can lay out as more than one box, so both are found by the
    # one style that separates them -- the reference demotion to 7.2pt.
    plain_lis = [b for b in blocks[("li", "")] if float(b.style["font_size"]) > 12]
    reference_lis = [b for b in blocks[("li", "")] if float(b.style["font_size"]) < 12]
    assert plain_lis and reference_lis
    assert {b.style["hyphens"] for b in plain_lis} == {"auto"}
    assert {b.style["hyphens"] for b in reference_lis} == {"manual"}
    assert any(line.endswith("‐") for b in plain_lis for line in lines(b))
    assert not any(line.endswith("‐") for b in reference_lis for line in lines(b))

    for label in (("h1", ""), ("h2", ""), ("p", "byline"), ("p", "standfirst")):
        for box in blocks[label]:
            assert box.style["hyphens"] != "auto", label
            assert adapter._measured_hyphenation(box.style) is None, label
            assert not any(line.endswith("‐") for line in lines(box)), label


def test_a_name_roster_paragraph_never_hyphenates():
    """`data-name-roster` -- html_edition's "these are names" stamp -- opts out.

    A signatories roster is proper nouns separated by bullets, and Pyphen
    breaking one ("Door- / Dash", "Y Combin- / ator", edition 003 measured
    both) is a misprint.  The roster below sets the same hyphenation-hungry
    Spanish words as its unstamped twin, so a leak would show as a hyphen on
    a page and not as a silently-passing style assertion.  Both the direct
    case -- a roster paragraph in the article flow, which the prose selectors
    must decline by attribute -- and the inherited one -- a roster inside a
    hyphenating list item, which only the `p[data-name-roster]` rule can
    reach -- stay unbroken.
    """
    words = _HYPHENATING_PROSE.rstrip(".").split()
    roster = " • ".join(words)
    body = (
        '<article id="a" data-article-id="a">'
        f'<p data-name-roster="true">{roster}</p>'
        f"<p>{_HYPHENATING_PROSE}</p>"
        f'<ul><li><p data-name-roster="true">{roster}</p></li></ul>'
        "</article>"
    )
    document = _hyphenating_document(body)

    rosters, prose = [], []
    for page in document.pages:
        for box in adapter._walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if element is None or type(box).__name__ != "BlockBox":
                continue
            if str(box.element_tag) != "p":
                continue
            (rosters if element.get("data-name-roster") else prose).append(box)

    def lines(box) -> list[str]:
        return [
            adapter._box_text(line)
            for line in adapter._walk_boxes(box)
            if type(line).__name__ == "LineBox"
        ]

    assert len(rosters) == 2 and prose
    for box in rosters:
        assert box.style["hyphens"] == "manual"
        assert adapter._measured_hyphenation(box.style) is None
        assert not any(line.endswith("‐") for line in lines(box))
    # The unstamped twin still hyphenates: the opt-out is the attribute, not
    # a change to what prose is.
    assert {b.style["hyphens"] for b in prose} == {"auto"}
    assert any(line.endswith("‐") for b in prose for line in lines(b))


def test_a_hyphen_ladder_is_reported_on_stderr_and_never_refused(capsys):
    """The audit WeasyPrint's missing `hyphenate-limit-lines` would have been.

    A paragraph of adverbs ends three consecutive lines on a hyphen -- one
    past the classical allowance `_HYPHEN_LADDER_LIMIT` states -- and the
    report names the page, the run and the run's first line on stderr, then
    hands the same measurement back to its caller.  Nothing raises: whether a
    ladder is tolerable is a stylesheet decision this evidence exists to
    inform, not a structural defect.  A settled paragraph reports nothing.
    """
    document = _hyphenating_document(_article(_HYPHENATING_PROSE))
    edition = SimpleNamespace(id="003-hyphens")

    ladders = adapter._report_hyphen_ladders(document, edition)

    assert ladders == adapter._measured_hyphen_ladders(document)
    assert [(ladder.key, ladder.page, ladder.run) for ladder in ladders] == [("0", 1, 3)]
    assert ladders[0].sample.endswith("‐")
    err = capsys.readouterr().err
    assert "hyphen ladder: edition 003-hyphens reader page 1 sets 3" in err

    settled = _hyphenating_document(_article(_SETTLED_PROSE))
    assert adapter._report_hyphen_ladders(settled, edition) == ()
    assert capsys.readouterr().err == ""


def test_a_word_tail_stranded_by_the_hyphenator_is_not_a_bindable_runt():
    """The bind repairs a space break, and a hyphen break has no space in it.

    WeasyPrint has no `hyphenate-limit-last`, so a block's final word can be
    hyphenated and its tail stranded as the last line (edition 003 sets
    `...when appro-` / `priate.`).  Binding the last two words re-lays that
    block character for character -- measured, twice, on both languages --
    because U+00A0 removes a break Pango was not taking.  So the tail is
    refused as a bind, on the block's own measured hyphenate character; the
    same lines on an unhyphenated block keep the pre-hyphenation answer, and
    an ordinary short word on a hyphenated block is still repaired.
    """
    hyphenation = adapter._Hyphenation("es", 6, 3, 3, "‐")
    measure, size = 433.0, 13.3
    tail = [(430.0, "que permanece completamente ocu‐"), (30.0, "rriendo.")]
    word = [(430.0, "que permanece completamente aquí"), (30.0, "hoy.")]

    assert not adapter._is_runt(tail, measure, size, hyphenation)
    assert adapter._is_runt(word, measure, size, hyphenation)
    # `hyphenation is None` is the revert path: the clause never fires.
    assert adapter._is_runt(tail, measure, size)


def test_the_band_anchor_clearance_defect_and_the_declaration_that_repairs_it(
    tmp_path: Path,
):
    """The flow defect, pinned together with the one-line flow repair that waits.

    `_evidence_band` replaces the reading frame before it sets its anchor
    heading, and `block` drops space-before whenever `self.y` is the frame's own
    top (render.py:1135) -- so ReportLab sets a band's anchor heading on the
    paragraph's 5.4pt of space-after alone.  On a band that bridges its own page
    that is 2.65pt between the paragraph's descenders and the heading's cap
    height, against 17.65pt everywhere else in the reader, and an independent
    review called it the largest visible defect in the edition.

    Removing `margin-top: 0` repairs the flow exactly, and that is asserted here
    so the repair cannot rot while it waits.  It is not shipped because of what
    it costs the *Spanish* edition -- a mid-article page ~60% white, a lost tail
    ornament, a lost closing plate; see the stylesheet's own note.  What ships
    instead is a *paint-only* clearance on the measured mid-page anchors (the
    next tests), which is exactly why this flow geometry must stay pinned at
    zero: the paint repair is safe only while the boxes do not move.
    """
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    body = (
        '<article id="a" data-article-id="a" data-figure-layouts="evidence_band">'
        "<p>The paragraph the anchor heading must not sit on top of.</p>"
        f"<h2>Anchor</h2>{_band_figure(path)}</article>"
    )
    repaired = _read_print_css().replace(
        "margin-left: -4.004pt; margin-right: -4.004pt; margin-top: 0;",
        "margin-left: -4.004pt; margin-right: -4.004pt;",
    )
    assert repaired != _read_print_css(), "the band anchor rule was respelled"

    def space_before(markup: str, css_text: str | None) -> float:
        page = _typeset_document(markup, css_text=css_text).pages[0]
        paragraph = _block_of(page, "p")
        heading = _block_of(page, "h2")
        return (
            float(heading.content_box_y())
            - float(paragraph.position_y)
            - float(paragraph.margin_height())
        ) * _POINTS_PER_CSS_PIXEL

    plain = (
        '<article id="a" data-article-id="a">'
        "<p>The paragraph the anchor heading must not sit on top of.</p>"
        "<h2>Anchor</h2><p>and the prose under it.</p></article>"
    )
    # What every other prose h2 gets: `paragraph_after + before` collapsed
    # against the paragraph's own 5.4pt.
    ordinary = space_before(plain, None)

    assert ordinary == pytest.approx(20.4 - 5.4, abs=1e-3)
    # The defect, as it ships.
    assert space_before(body, None) == pytest.approx(0.0, abs=1e-3)
    # The repair, as it would ship.
    assert space_before(body, repaired) == pytest.approx(ordinary, abs=1e-3)


def test_a_midpage_band_anchor_is_cleared_in_paint_and_never_in_flow(tmp_path: Path):
    """The shipped repair: ink moves down by the dropped space-before, boxes do not.

    A classed h2 paints 15pt lower (its dropped space-before) and a classed h3
    10pt, each folded into the heading's own standing paint correction because
    transforms override rather than compose.  The heading's *box* must not move
    at all -- a transform is invisible to fragmentation, which is the entire
    reason this repair can ship where removing `margin-top: 0` could not.
    """
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)

    def anchored(tag: str, classed: bool) -> str:
        marker = ' class="band-anchor-midpage"' if classed else ""
        return (
            '<article id="a" data-article-id="a" data-figure-layouts="evidence_band">'
            f"<p>The paragraph above the anchor.</p><{tag}{marker}>Anchor</{tag}>"
            f"{_band_figure(path)}</article>"
        )

    for tag, standing, shipped in (("h2", -7.22965, 7.77035), ("h3", 0.91256, 10.91256)):
        bare = _block_of(_typeset_document(anchored(tag, False)).pages[0], tag)
        cleared = _block_of(_typeset_document(anchored(tag, True)).pages[0], tag)

        assert _translated_down(bare) == pytest.approx(standing, abs=1e-4)
        assert _translated_down(cleared) == pytest.approx(shipped, abs=1e-4)
        # The paint delta is exactly the space-before `_set_custom_frame` drops.
        assert _translated_down(cleared) - _translated_down(bare) == pytest.approx(
            15.0 if tag == "h2" else 10.0, abs=1e-4
        )
        # Paint only: the classed heading's box geometry is the bare heading's.
        assert (cleared.position_y, cleared.content_box_y(), cleared.margin_height()) == (
            bare.position_y,
            bare.content_box_y(),
            bare.margin_height(),
        )


def test_midpage_band_anchors_are_measured_from_the_laid_out_pages(tmp_path: Path):
    """An anchor is mid-page exactly when it starts on its bridge's last page.

    The first document sets bridge, heading and band together on page one: the
    heading follows prose mid-page, so the band is named.  The second pushes the
    heading and its unbreakable band to page two while the bridge stays behind:
    the heading opens a page, which is the case ReportLab's dropped space-before
    was written for, so nothing is named and nothing gets the paint clearance.
    """
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    marked = (
        '<article id="a" data-article-id="a" data-figure-layouts="evidence_band">'
        '{spacer}<p data-band-bridge="fig">The bridge paragraph.</p>'
        f'<h2 data-band-anchor="fig">Anchor</h2>{_band_figure(path)}</article>'
    )

    midpage = _typeset_document(marked.format(spacer=""))
    assert adapter._measured_midpage_anchors(midpage) == ("fig",)

    opening = _typeset_document(
        marked.format(spacer='<div style="height: 430pt"></div>')
    )
    bridge_pages = {page for page, _top in adapter._band_bridges(opening).values()}
    assert len(opening.pages) == 2 and bridge_pages == {1}
    assert adapter._measured_midpage_anchors(opening) == ()


def test_the_adapter_marks_band_anchors_and_classes_only_the_measured_ones(tmp_path: Path):
    path = tmp_path / "band.png"
    Image.new("RGB", (1920, 1266), "white").save(path)
    tree = _parse_article_fragment(f"<p>lead in</p><h2>Anchor</h2>{_band_figure(path)}")

    adapter._mark_band_bridges(tree)
    heading = next(tree.iter("h2"))
    paragraph = next(tree.iter("p"))
    assert heading.get("data-band-anchor") == "fig"
    assert paragraph.get("data-band-bridge") == "fig"

    adapter._apply_anchor_clearances(tree, ())
    assert "band-anchor-midpage" not in adapter._element_classes(heading)
    adapter._apply_anchor_clearances(tree, ("other",))
    assert "band-anchor-midpage" not in adapter._element_classes(heading)
    adapter._apply_anchor_clearances(tree, ("fig",))
    assert "band-anchor-midpage" in adapter._element_classes(heading)


# ---------------------------------------------------------------------------
# The source code: a printed way back to the source an article was built from.
# ---------------------------------------------------------------------------

_CODE_URL = "https://example.test/source?a=1&b=2"
# A 51-character address, the length this edition's canonical URLs actually run
# to, and the length at which the error-correction levels stop tying: ECC-L sets
# it in QR version 3 and ECC-M needs version 4.
_CODE_URL_51 = "https://example.test/source/agent-swarms-and-model"


def _decoded(pdf: Path) -> dict[int, list[str]]:
    """Every QR symbol Poppler and zxing find on every page of ``pdf``."""
    import pypdf

    found: dict[int, list[str]] = {}
    pages = range(1, len(pypdf.PdfReader(str(pdf)).pages) + 1)
    rasters = adapter._rasterised_pages(pdf.read_bytes(), pages)
    for page, raster in rasters.items():
        texts = [text for text, _corners in adapter._decoded_codes(raster)]
        if texts:
            found[page] = texts
    return found


def test_the_square_is_a_constant_and_the_url_buys_density_not_size():
    """One square on every opener; a longer URL is a denser symbol inside it."""
    short = adapter._fitted_source_code(
        "a", "https://buzz.xyz/", adapter._CODE_OPENER_SIDE_POINTS
    )
    long = adapter._fitted_source_code(
        "b",
        "https://www.cs.princeton.edu/~arvindn/talks/icml-2026-annotated-slides/",
        adapter._CODE_OPENER_SIDE_POINTS,
    )

    assert short.side == pytest.approx(adapter._CODE_OPENER_SIDE_POINTS)
    assert long.side == pytest.approx(adapter._CODE_OPENER_SIDE_POINTS)
    assert short.modules < long.modules
    assert short.module > long.module
    # The square is exactly the constant, so the module is its quotient.
    assert long.module == pytest.approx(adapter._CODE_OPENER_SIDE_POINTS / long.modules)


def test_the_widest_cell_wins_and_only_a_tie_goes_to_the_higher_correction():
    """Cell size before redundancy, which is the trade a small printed code needs.

    In the fixed opener square a lower correction is a shorter symbol and a
    shorter symbol is a wider cell, so the level taken is the shortest --
    unless two levels set the same module count, where the extra redundancy is
    free and the higher correction wins the tie.
    """
    import segno

    fitted = adapter._fitted_source_code(
        "a", _CODE_URL_51, adapter._CODE_OPENER_SIDE_POINTS
    )
    widths = {
        level: int(segno.make(_CODE_URL_51, error=level, micro=False).symbol_size(border=4)[0])
        for level in adapter._CODE_ERROR_LEVELS
    }
    # The 51-character URL really exercises the rule: L is strictly shortest.
    assert widths["L"] < min(widths[level] for level in "MQH")
    assert fitted.error == "L"
    assert fitted.modules == widths["L"]
    assert fitted.module == pytest.approx(adapter._CODE_OPENER_SIDE_POINTS / widths["L"])
    # And a URL whose L and M symbols tie goes to M, the higher correction.
    tie_url = next(
        url
        for length in range(20, 60)
        for url in [f"https://example.test/{'a' * length}"]
        if int(segno.make(url, error="L", micro=False).symbol_size(border=4)[0])
        == int(segno.make(url, error="M", micro=False).symbol_size(border=4)[0])
    )
    tied = adapter._fitted_source_code("a", tie_url, adapter._CODE_OPENER_SIDE_POINTS)
    assert tied.error in {"M", "Q", "H"}


def test_a_square_too_small_for_any_level_yields_nothing_rather_than_a_smaller_code(
    tmp_path: Path,
):
    """The floor does not bend: an unscannable square is worse than no square."""
    assert adapter._fitted_source_code("a", _CODE_URL, 8.0) is None

    # And through the plan: a URL too long for the opener square at any error
    # correction level is a loud refusal naming the fix.
    edition = _edition(tmp_path)
    edition = replace(
        edition,
        articles=(replace(edition.articles[0], source_url="https://example.test/" + "x" * 200),),
    )
    document = _stub_reader_document((), edition.articles[0].id)
    with pytest.raises(ValidationError, match="cannot carry a scannable source code"):
        adapter._opener_source_codes(edition, document)


def test_the_code_top_is_measured_off_the_laid_out_byline(tmp_path: Path):
    """The credit line is wherever the title actually ended, which is Pango's
    line count and not the unkerned fit's -- so `top` is a measurement, read
    off the byline's own laid-out line box."""
    edition = _edition(tmp_path)
    document = _stub_reader_document((), edition.articles[0].id)

    (code,) = adapter._opener_source_codes(edition, document)

    # The stub byline's line box sits at y=150 CSS px with a 2px baseline.
    baseline = (150.0 + 2.0) * 72 / 96 - adapter._PAGE_MARGIN_TOP_POINTS
    assert code.slot == "opener"
    assert code.top == pytest.approx(
        baseline - adapter._BYLINE_SIZE_POINTS * adapter._INTER_CAP_RATIO - code.quiet
    )
    assert code.symbol_left == pytest.approx(adapter._CODE_MEASURE_LEFT_POINTS)
    assert code.left == pytest.approx(
        adapter._CODE_MEASURE_LEFT_POINTS - code.quiet
    ), "the flush is to the article-rail ink"
    assert code.side == pytest.approx(adapter._CODE_OPENER_SIDE_POINTS)

    # No source, no code, no error -- the editorial's case, and a source
    # record's canonical url is not guaranteed.
    unlinked = replace(
        edition, articles=(replace(edition.articles[0], source_url=None),)
    )
    assert adapter._opener_source_codes(unlinked, document) == ()

    # An opener that laid out no byline cannot anchor a code, and says so.
    bare = _Document((_Page(_Box(children=(
        _Box("article", element=_Element("article", **{"data-article-id": edition.articles[0].id})),
    ))),))
    with pytest.raises(ValidationError, match="laid out no byline"):
        adapter._opener_source_codes(edition, bare)



def test_the_symbol_is_set_in_one_ink_so_a_mono_printer_cannot_screen_a_finder():
    """The finder patterns were VIOLET and are now INK, on purpose.

    On a colour device the violet is right and measures fine: gray 0.180 against
    the ink's 0.071, and the binariser is untroubled.  A **monochrome** printer
    does not reproduce 0.18 as gray, it halftones it, and a halftone cell at the
    foot code's 0.38mm module is the width of the module -- which puts white
    holes through a finder ring one module thick, in the one part of the symbol
    detection depends on before error correction can help.  This magazine is
    printed at home and that case cannot be measured here, so the symbol is one
    ink -- and the violet label it once moved to is retired, so the square spends
    no house colour at all now.
    """
    code = adapter._fitted_source_code("a", _CODE_URL, adapter._CODE_OPENER_SIDE_POINTS)
    svg = unquote(adapter._source_code_source(code).removeprefix("data:image/svg+xml,"))
    matrix = adapter._source_code_matrix(code)

    assert f"fill='{adapter._CODE_INK}'" in svg
    assert not hasattr(adapter, "_CODE_VIOLET")
    assert not hasattr(adapter, "_is_finder_module")
    assert f"<rect width='{code.side:.4f}' height='{code.side:.4f}' fill='rgb(100%,100%,100%)'/>" in svg
    # One path and not a field of rectangles: a PDF fill computes coverage once
    # over a whole path, so touching modules merge instead of laying a grid of
    # antialiased hairlines through the symbol.  With one ink there is no second
    # path for the first to antialias against either.
    assert svg.count("<path") == 1
    assert "<rect" in svg and svg.count("<rect") == 1
    # Every dark module of the symbol is in that one path, finders included.
    assert svg.count("z") == sum(
        1
        for row in matrix
        for column, cell in enumerate(row)
        if cell and (column == 0 or not row[column - 1])
    )
    # The element carries the standard's four-module quiet zone itself.
    assert code.modules == len(matrix) + 2 * adapter._CODE_QUIET_MODULES
    assert f"width='{code.side:.4f}pt'" in svg
    # The first dark module of the top-left finder starts one quiet zone in.
    inset = adapter._CODE_QUIET_MODULES * code.module
    assert f"M{inset:.4f} {inset:.4f}" in svg


def test_an_opener_figure_field_deepens_for_the_code_that_stands_over_it(tmp_path: Path):
    """The figure's head is the field's foot, and the square must clear it.

    The field is the adapter's own statement (`_pin_opener_fields`); with a code
    in the credit block the lowest ink is the symbol's last dark row -- an opener
    figure hides the author note and nothing hangs under the square -- so the
    stated field runs to it plus the credit's 12pt pad, computed from the fitted
    title, which never under-counts a valid build's lines.
    """
    edition = _edition(tmp_path)
    article = edition.articles[0]
    assert article.source_url  # the fixture's opener carries a code

    size, fitted_lines = adapter._fitted_display(
        str(article.title), adapter._LIVE_WIDTH_POINTS, 165.0,
        maximum=30.0, minimum=24.0, maximum_lines=4, leading_ratio=.96,
    )
    bare = adapter._OPENER_FIGURE_FIELD_BASE + adapter._opener_title_flow(size, len(fitted_lines))
    floor = adapter._opener_code_field_floor(article, size, len(fitted_lines))
    assert floor > bare  # the fixture's short title ends high, so the code binds

    tree = _print_tree(edition)
    adapter._pin_opener_fields(tree, edition)
    header = next(
        header for piece in tree.iter("article") for header in piece if header.tag == "header"
    )
    assert header.get("style") == f"height: {floor:.4f}pt"
    # The depth the field takes for the code comes back out of the opener
    # figure's own 270pt image cap, so a full opener stays one page.
    opener_image = next(
        image
        for piece in tree.iter("article")
        for figure in piece
        if figure.tag == "figure" and figure.get("data-anchor") == "__opener__"
        for image in figure.iter("img")
    )
    assert opener_image.get("style") == f"max-height: {270.0 - (floor - bare):.4f}pt"

    # An article with no code keeps the fitted title's own depth.
    unlinked = replace(
        edition, articles=(replace(article, source_url=None),)
    )
    bare_tree = _print_tree(unlinked)
    adapter._pin_opener_fields(bare_tree, unlinked)
    bare_header = next(
        header for piece in bare_tree.iter("article") for header in piece if header.tag == "header"
    )
    assert bare_header.get("style") == f"height: {bare:.4f}pt"



def test_a_printed_code_reads_back_off_the_rasterized_page_as_its_canonical_url(
    tmp_path: Path,
):
    """The gate on a real build: rendered, written, rasterized, decoded.

    Read with a general barcode reader that is not told where to look, off a
    300 ppi raster of the finished PDF -- the publication's own print floor --
    so what passes here is what a phone would do to the printed sheet.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    output = tmp_path / "reader.pdf"

    layout = render_a5_weasyprint(edition, output)

    # One code, on the article's own OPENER page: the square is title
    # furniture now, not a coda on the last page.
    opener_page = layout.toc[edition.articles[0].id]
    assert _decoded(output) == {opener_page: [_CODE_URL]}


def test_a_code_carrying_the_wrong_url_is_refused_even_though_it_scans(tmp_path: Path, monkeypatch):
    """A perfectly scannable code pointing somewhere else is the silent failure.

    Nothing about the page looks wrong, and no reader could tell -- which is why
    the gate compares the decoded text with the article's canonical url rather
    than merely asserting that something decoded.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    genuine = adapter._source_code_source
    monkeypatch.setattr(
        adapter,
        "_source_code_source",
        lambda code: genuine(replace(code, url="https://example.test/not-the-source")),
    )
    output = tmp_path / "reader.pdf"

    with pytest.raises(ValidationError, match="does not read back off the page"):
        render_a5_weasyprint(edition, output)

    assert "expected 'https://example.test/source?a=1&b=2'" in _error_text(edition, tmp_path)
    # And nothing was written: the gate runs on the bytes before they land.
    assert not output.exists()


def test_a_code_damaged_past_its_own_error_correction_is_refused(tmp_path: Path, monkeypatch):
    """The other half: a code that carries the right URL and cannot be read.

    Half the symbol's rows are inverted, which is far past what any error
    correction level recovers, so the reader finds nothing at all on the page.
    """
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    genuine = adapter._source_code_matrix

    def damaged(code):
        matrix = genuine(code)
        for row in range(len(matrix) // 2, len(matrix)):
            matrix[row] = [not cell for cell in matrix[row]]
        return matrix

    monkeypatch.setattr(adapter, "_source_code_matrix", damaged)
    output = tmp_path / "reader.pdf"

    with pytest.raises(ValidationError, match="nothing decoded on the"):
        render_a5_weasyprint(edition, output)
    assert not output.exists()


def test_a_planned_code_that_never_reached_a_page_is_refused(tmp_path: Path, monkeypatch):
    """Silent absence is the third way this feature can fail, and it is caught."""
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
    monkeypatch.setattr(adapter, "_apply_source_codes", lambda tree, codes: None)

    with pytest.raises(ValidationError, match="laid out no square for it"):
        render_a5_weasyprint(edition, tmp_path / "reader.pdf")


def _error_text(edition: Edition, tmp_path: Path) -> str:
    """The message the caller above already raised, captured for a second look."""
    try:
        render_a5_weasyprint(edition, tmp_path / "again.pdf")
    except ValidationError as exc:
        return str(exc)
    raise AssertionError("expected the source code gate to refuse this reader")
