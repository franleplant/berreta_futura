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
from magazine.render import RenderLayout
from magazine.weasyprint_adapter import (
    WEASYPRINT_DESIGN,
    _apply_tail_ornaments,
    _configure_macos_library_path,
    _content_page_count,
    _figure_placement,
    _limit_closing_plates,
    _measure_layout,
    _read_print_css,
    _render_to_signature,
    _rewrite_landscape_plates,
    _rotated_plate_box,
    _signature_closing_plates,
    _tail_ornament_height,
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
    for name, size in (("figure.png", (1600, 800)), ("tail.png", (400, 200)),
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


def _parse_article_fragment(inner: str, *, plates: int = 0):
    HTML, _CSS, _FontConfiguration = _weasyprint_types()
    plate_markup = "".join(
        f'<figure class="closing-plate" data-closing-plate="{index + 1}">'
        f'<img src="p{index}"><figcaption>Plate</figcaption></figure>'
        for index in range(plates)
    )
    return HTML(
        string=(
            '<!doctype html><html><body><main data-edition-id="edition">'
            f'<article id="article-article" data-article-id="article">{inner}</article>'
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


def test_tail_ornament_is_earned_by_open_space_and_capped():
    """`_article_tail_ornament_box` (render.py:218-231) as a decision, not a figure."""
    # `available` is `y - 101`: 118pt of it is the minimum, 214pt the cap.
    assert _tail_ornament_height(218.9) is None
    assert _tail_ornament_height(219.0) == pytest.approx(118.0)
    assert _tail_ornament_height(280.0) == pytest.approx(179.0)
    assert _tail_ornament_height(500.0) == pytest.approx(214.0)
    # An article that fills its last page earns nothing, floor included.
    assert _tail_ornament_height(40.0) is None


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
    # The tail motif is earned: the stub article ends 435.271pt above the foot.
    assert plan.tail_heights == {"article<&>": pytest.approx(214.0)}


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


def test_an_unearned_tail_ornament_is_removed_and_an_earned_one_is_sized():
    markup = '<figure class="article-tail"><img src="c"></figure>'
    sized = _parse_article_fragment(markup)
    _apply_tail_ornaments(sized, {"article": 146.5756})
    figure = next(sized.iter("figure"))
    assert figure.get("style") == "height: 146.5756pt"

    dropped = _parse_article_fragment(markup)
    _apply_tail_ornaments(dropped, {})
    assert list(dropped.iter("figure")) == []


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
    # cannot slip through the document comparison below unnoticed.
    edition = _raster_edition(tmp_path, manuscript=_FONT_SAFE_MANUSCRIPT)
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


def test_an_opener_title_that_outgrows_its_reserved_field_is_refused(tmp_path: Path):
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
    overlong = replace(
        edition,
        articles=tuple(
            replace(article, title=_LOOSENING_TITLE) for article in edition.articles
        ),
    )

    render_a5_weasyprint(edition, tmp_path / "reader.pdf")  # as authored, no refusal
    with pytest.raises(ValidationError) as raised:
        render_a5_weasyprint(overlong, tmp_path / "overlong.pdf")

    message = str(raised.value)
    assert "article<&>" in message, "name the piece an editor has to go and fix"
    assert _LOOSENING_TITLE in message
    assert "117.8000pt header field" in message, "the room that was reserved"
    assert "overflowing the field by 12.1127pt" in message, "and how far past it"
    assert "Shorten the title, or lower the fit range" in message
    assert not (tmp_path / "overlong.pdf").exists(), "and nothing is written"


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
    """X16/X17: a violet disc at 14pt of indent; references at SERIF 7.2/9.4."""
    document = _typeset_document(
        '<article data-article-id="a"><ul><li><p>Bullet one</p></li></ul>'
        "<h3>References</h3>"
        '<ul data-reference-list="true"><li><p>4 - Source note</p></li></ul>'
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
    assert round(items[1].height * _POINTS_PER_CSS_PIXEL, 2) == 9.4, "one line at 9.4 leading"
    assert round(items[1].padding_left * _POINTS_PER_CSS_PIXEL, 3) == 0.0
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


def test_article_opener_pins_its_prose_to_the_reserved_white_field():
    """O1: `_set_reading_frame(top=238)` -- 14 lines, whatever the chrome above."""

    def opener(chrome: str, figure: str = ""):
        document = _typeset_document(
            f'<article data-article-id="a"><header>{chrome}</header>{figure}'
            f'<p class="standfirst">{_FILLER_PROSE}</p></article>'
        )
        page = document.pages[0]
        standfirst = _block_of(page, "p")
        prose = _line_boxes_of(page, "p")
        return len(prose), round(
            _painted_baseline_from_page_foot(prose[0], standfirst), 3
        )

    short = opener("<h1>Short</h1>")
    tall = opener(
        "<h1>Short</h1>" + "".join(f'<div style="height: 30pt">chrome {i}</div>' for i in range(5))
    )

    # 238 less the page's own +0.005pt rasterizer nudge.  The field is stated as
    # a *flow* height, so the standfirst's own 12pt/16.4pt baseline offset is not
    # in it: the pinned baseline is the flow position plus the paint correction.
    assert short[1] == 237.995, "the standfirst opens on ReportLab's pinned frame top"
    assert tall == short, "the reserved field is pinned, not derived from the chrome"
    # An opener figure replaces the rule rather than the number: ReportLab then
    # uses the space left after the credit, so the header flows again.
    with_figure = opener(
        "<h1>Short</h1>", '<figure data-anchor="__opener__"><figcaption>c</figcaption></figure>'
    )
    assert with_figure[1] > 238.0


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


def test_the_end_mark_lands_on_the_reader_s_baseline_and_stops_at_its_floor():
    """`baseline = max(self.frame_bottom + 5, self.y - 1)` (render.py:2009).

    Nothing pinned this before, and both halves of it were wrong: the mark was
    painted 8.53085pt high on every article, and the clamp did not exist at all.
    A 20pt filler spacer leaves the article ending high on its page; 460pt runs it
    down to the floor, where the reader stops and the unclamped mark would not.
    """
    # The spacer is the whole control: a one-line article 20pt down the page
    # ends far clear of the floor, and one 478pt down ends under it.
    high_y, high_css, high_planned = _end_mark_case(20.0)
    low_y, low_css, low_planned = _end_mark_case(478.0)

    assert high_y - 1 > 50.0, "the high case must clear the floor or it proves nothing"
    assert low_y - 1 < 50.0, "the low case must reach the floor or it proves nothing"
    # Clear of the floor, the stylesheet's own 28.53085pt is the whole answer.
    assert high_css == pytest.approx(high_y - 1.0, abs=5e-4)
    assert high_planned == pytest.approx(high_y - 1.0, abs=5e-4)
    # At the floor it is not: the mark would be painted below `frame_bottom`.
    assert low_css < 50.0 - 1.0
    assert low_planned == pytest.approx(50.0, abs=5e-4)


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
    plan = adapter.ReaderPlan(closing_plates=0, tail_ornaments=())
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

    # The flushed item's border box ends on the live area's right edge; the
    # transform then carries its ink the trailing letter-space further right.
    assert round((secondary.position_x + secondary.width) * _POINTS_PER_CSS_PIXEL, 4) == 377.0079
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
    """O1/F6: the field runs to the figure's head, wherever the title reached."""
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
    assert header.get("style") == f"height: {59 + size * (1 + .96 * len(lines)):.4f}pt"


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
    """F19: `prepare_print_image` is a figure treatment, not an artwork treatment."""
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
    assert treated == {"fig": True, "article-tail": False, "closing-plate": False}
    # The placement still names the file the edition curated, not the derivative.
    figure = next(element for element in tree.iter("figure") if element.get("data-figure-id"))
    assert next(figure.iter("img")).get("data-print-source") == pale.as_uri()


def test_print_contrast_refuses_an_undecodable_curated_figure(tmp_path: Path):
    path = tmp_path / "broken.png"
    path.write_text("not a raster", encoding="utf-8")
    tree = _parse_article_fragment(
        f'<figure data-figure-id="fig"><img src="{path.as_uri()}"></figure>'
    )
    with pytest.raises(ValidationError, match="Cannot decode curated figure"):
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
