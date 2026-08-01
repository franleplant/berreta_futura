"""Fast page-budget measurement, off the reader's real pagination.

The page budgets -- seven rendered A5 pages per source article, the declared
editorial cap -- used to be checkable only by running a whole build: the caps
are enforced deep inside ``render_a5_weasyprint`` after the complete HTML
document is laid out, so an author finished a manuscript, a
translation and every hash pin before learning the piece does not fit, and the
English package was fully rastered before Spanish was measured at all.  During
layout rework the same gap grew six throwaway ``tmp/`` scripts that reached
into the adapter's privates to ask "where does this land on the page".

This module is that seam, supported.  It compiles the edition's semantic HTML
and paginates it with WeasyPrint exactly as a build would -- the same CSS, the
same fonts, the same measure-then-settle passes -- and then stops: no PDF, no
rasters, no imposition, no covers, no package.  The *pagination* is honest by
construction: the front half is the adapter's own functions called with the
same arguments a build passes, so the box tree cannot differ.  The *counting*
of that tree is not imported -- ``_measured_spans`` restates
``_measure_layout``'s article and editorial box tests rather than calling it,
because ``_measure_layout`` also validates raster placement and would drag
PIL and figure checks into a text-only question.  That restatement is the one
place this module could drift from the build, and the tripwire is the
build-equality test in ``tests/test_measure.py``, which builds a real package
and asserts the measured spans equal its recorded layout: change the
adapter's counting and that test, not this docstring, is what objects.
What a build enforces as a refusal, this
module *reports* -- an over-budget article is a row in the result, not an
exception -- because the whole point is to hear the verdict before the rest of
the work is done.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError
from .html_edition import render_html_edition
from .manifest import Edition
from .reader_layout import declared_editorial_page_cap
from . import weasyprint_adapter as adapter


@dataclass(frozen=True)
class ParagraphMeasurement:
    """One prose block's rag, read off its laid-out line boxes.

    ``key`` is the adapter's own runt key -- the block's ordinal among the
    semantic edition's prose blocks -- so a row here names the same paragraph
    a ``ReaderPlan.runt_binds`` entry names.  ``last_line_fraction`` is the
    last line's width over its own block's measure, which differs between the
    reading column, a band escape and a list item's indent; ``runt`` flags a
    final line that is a single word stranded on its own.  Blocks of one line
    are not reported: a one-line block is a short paragraph, not a rag.  The
    raw numbers are all kept because rag thresholds are editorial judgments
    that get tried and reverted; the table exists so that judging one no
    longer requires a throwaway script.
    """

    key: str
    page: int
    lines: int
    last_line_words: int
    last_line_fraction: float
    runt: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "page": self.page,
            "lines": self.lines,
            "last_line_words": self.last_line_words,
            "last_line_fraction": self.last_line_fraction,
            "runt": self.runt,
        }


@dataclass(frozen=True)
class ArticleMeasurement:
    """One article's pages against its budgets, plus its last page's shape.

    ``pages`` counts the reader pages the article's element appears on --
    the same set ``_measure_layout`` counts into a build manifest's
    ``layout.article_pages`` -- and ``first_page``/``last_page`` are that
    set's span.  ``last_page_body_lines`` counts the in-flow line boxes on the
    final page (the tail ornament, end mark and opener code are out of flow
    and excluded, as the adapter's own flow walk excludes them).
    ``flow_bottom`` is where the article's flow ended, in points above the
    page foot -- the number the tail ornament and end mark are placed from --
    and ``end_mark_offset``/``tail_art_height`` are the plan's own measured
    answers for both, ``None`` where the page earned no ornament.
    """

    id: str
    first_page: int
    last_page: int
    pages: int
    cap: int
    minimum: int
    last_page_body_lines: int
    flow_bottom: float
    end_mark_offset: float | None
    tail_art_height: float | None

    @property
    def over(self) -> bool:
        return self.pages > self.cap

    @property
    def under_minimum(self) -> bool:
        return self.pages < self.minimum

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "first_page": self.first_page,
            "last_page": self.last_page,
            "pages": self.pages,
            "cap": self.cap,
            "minimum": self.minimum,
            "over": self.over,
            "under_minimum": self.under_minimum,
            "last_page_body_lines": self.last_page_body_lines,
            "flow_bottom": self.flow_bottom,
            "end_mark_offset": self.end_mark_offset,
            "tail_art_height": self.tail_art_height,
        }


@dataclass(frozen=True)
class EditorialMeasurement:
    """The opening editorial's span against the cap this edition declared."""

    first_page: int
    last_page: int
    pages: int
    cap: int

    @property
    def over(self) -> bool:
        return self.pages > self.cap

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_page": self.first_page,
            "last_page": self.last_page,
            "pages": self.pages,
            "cap": self.cap,
            "over": self.over,
        }


@dataclass(frozen=True)
class LanguageMeasurement:
    """One language's laid-out reader, measured and never written."""

    language: str
    total_pages: int
    content_pages: int
    closing_plates: int
    contents_pages: int
    editorial: EditorialMeasurement | None
    articles: tuple[ArticleMeasurement, ...]
    paragraphs: tuple[ParagraphMeasurement, ...]

    @property
    def breaches(self) -> tuple[str, ...]:
        """Every budget this language's pages break, in the build's own terms.

        The same three rules ``_validate_layout_caps`` refuses a build over,
        phrased as facts rather than raised, so a breach is something a caller
        ranks and fixes instead of the first one encountered.
        """

        found: list[str] = []
        for article in self.articles:
            if article.over:
                found.append(
                    f"{self.language}: article {article.id} spans {article.pages} pages "
                    f"(maximum {article.cap})"
                )
            if article.under_minimum:
                found.append(
                    f"{self.language}: article {article.id} spans {article.pages} pages "
                    f"(editorial minimum {article.minimum})"
                )
        if self.editorial is not None and self.editorial.over:
            found.append(
                f"{self.language}: editorial spans {self.editorial.pages} pages "
                f"(maximum {self.editorial.cap})"
            )
        return tuple(found)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "total_pages": self.total_pages,
            "content_pages": self.content_pages,
            "closing_plates": self.closing_plates,
            "contents_pages": self.contents_pages,
            "editorial": self.editorial.to_dict() if self.editorial else None,
            "articles": [article.to_dict() for article in self.articles],
            "paragraphs": [paragraph.to_dict() for paragraph in self.paragraphs],
        }


@dataclass(frozen=True)
class EditionMeasurement:
    """Every configured language's measurement, and the one-word verdict."""

    edition_id: str
    engine: str
    languages: tuple[LanguageMeasurement, ...]

    @property
    def breaches(self) -> tuple[str, ...]:
        return tuple(
            breach for language in self.languages for breach in language.breaches
        )

    @property
    def ok(self) -> bool:
        return not self.breaches

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "engine": self.engine,
            "ok": self.ok,
            "breaches": list(self.breaches),
            "languages": {
                language.language: language.to_dict() for language in self.languages
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"


def measure_edition(
    root: Path, edition_id: str, language: str | None = None
) -> EditionMeasurement:
    """Measure ``edition_id``'s pagination in every configured language.

    The convenience entry for scripts and agents; ``Magazine.measure`` is the
    same call for a compiler a caller already holds.  Imported lazily because
    the compiler imports this module's measurement for its thin method.
    """

    from .compiler import Magazine

    return Magazine(root).measure(edition_id, language=language)


def measure_editions(
    edition_id: str, editions: Mapping[str, Edition]
) -> EditionMeasurement:
    """Paginate each localized edition with the real adapter path and read it.

    ``editions`` maps language to its loaded :class:`Edition`, exactly as the
    compiler's language loader returns them; iteration order is report order.
    """

    if not editions:
        raise ValidationError("Measurement requires at least one language")
    return EditionMeasurement(
        edition_id=edition_id,
        engine="weasyprint",
        languages=tuple(
            _measure_language(language, edition)
            for language, edition in editions.items()
        ),
    )


def _measure_language(language: str, edition: Edition) -> LanguageMeasurement:
    """One language's reader, laid out by the adapter and measured in place.

    This is the front half of ``render_a5_weasyprint`` verbatim -- the same
    semantic HTML, the same ``@font-face`` configuration, the same
    measure-then-settle pagination -- ending at the settled document instead
    of continuing into paint, PDF serialization and the raster gates.  Every
    call is the adapter's own function, so this measurement cannot disagree
    with a build of the same bytes.
    """

    HTML, CSS, FontConfiguration = adapter._weasyprint_types()
    semantic = render_html_edition(edition)
    font_config = FontConfiguration()
    stylesheet = CSS(
        string=adapter._read_print_css(),
        base_url=resources.files("magazine").joinpath("assets").as_uri() + "/",
        font_config=font_config,
    )
    document, _html, plan = adapter._render_to_signature(
        HTML, semantic.html, stylesheet, edition, font_config=font_config
    )

    article_pages, editorial_pages, contents_pages = _measured_spans(document)
    editorial_cap = declared_editorial_page_cap(
        edition.raw, adapter._MAX_EDITORIAL_PAGES
    )
    editorial = (
        EditorialMeasurement(
            first_page=min(editorial_pages),
            last_page=max(editorial_pages),
            pages=len(editorial_pages),
            cap=editorial_cap,
        )
        if editorial_pages
        else None
    )
    end_marks = plan.end_mark_offsets
    tail_arts = plan.tail_art_heights
    articles: list[ArticleMeasurement] = []
    for article in edition.articles:
        pages = article_pages.get(article.id)
        if not pages:
            raise ValidationError(
                f"WeasyPrint laid out no pages for article {article.id}; "
                "the reader has nothing to measure"
            )
        articles.append(
            ArticleMeasurement(
                id=article.id,
                first_page=min(pages),
                last_page=max(pages),
                pages=len(pages),
                cap=adapter._MAX_ARTICLE_PAGES,
                minimum=article.minimum_reader_pages,
                last_page_body_lines=_last_page_body_lines(
                    document, article.id, max(pages)
                ),
                flow_bottom=round(
                    adapter._article_flow_bottom(document, article.id), 3
                ),
                end_mark_offset=_rounded(end_marks.get(article.id)),
                tail_art_height=_rounded(tail_arts.get(article.id)),
            )
        )
    return LanguageMeasurement(
        language=language,
        total_pages=len(document.pages),
        content_pages=adapter._content_page_count(document),
        closing_plates=plan.closing_plates,
        contents_pages=len(contents_pages),
        editorial=editorial,
        articles=tuple(articles),
        paragraphs=_measured_paragraphs(document),
    )


def _measured_spans(
    document: Any,
) -> tuple[dict[str, set[int]], set[int], set[int]]:
    """Which reader pages carry each article, the editorial, and the contents.

    The article and editorial tests are ``_measure_layout``'s own, walked over
    the same box tree, which is what makes a span here equal that function's
    ``article_pages`` count for the same document; the contents test is the
    one ``_validate_contents_page`` applies to logical page three.
    """

    article_pages: dict[str, set[int]] = {}
    editorial_pages: set[int] = set()
    contents_pages: set[int] = set()
    for page_number, page in enumerate(document.pages, start=1):
        for box in adapter._walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if element is None:
                continue
            attributes = getattr(element, "attrib", {})
            article_id = attributes.get("data-article-id")
            if article_id and getattr(box, "element_tag", None) == "article":
                article_pages.setdefault(article_id, set()).add(page_number)
            if (
                attributes.get("id") == "editorial"
                and getattr(box, "element_tag", None) == "section"
            ):
                editorial_pages.add(page_number)
            if attributes.get("data-edition-navigation") == "contents":
                contents_pages.add(page_number)
    return article_pages, editorial_pages, contents_pages


def _last_page_body_lines(document: Any, article_id: str, last_page: int) -> int:
    """How many in-flow lines the article sets on its final page.

    The number a trim toward the cap is negotiated against: cutting a page
    means finding this many lines plus a heading's clearance, and a last page
    of three lines is a different editing problem than one of thirty.  Counted
    through the adapter's own flow walk, so the tail ornament, end mark and
    opener code are out of the count exactly as they are out of the flow.
    """

    page = document.pages[last_page - 1]
    return sum(
        1
        for box in adapter._article_flow_boxes(page._page_box, article_id)
        if type(box).__name__ == "LineBox"
    )


def _measured_paragraphs(document: Any) -> tuple[ParagraphMeasurement, ...]:
    """Every multi-line prose block's rag, in the semantic edition's order.

    The collection walk is ``_measured_runt_binds``'s: line boxes accumulate
    across a block's page fragments under the block's runt key, and only the
    block box is read so a line is never counted twice.  What that function
    reduces to a bind decision is reported here whole, because the reverted
    rag threshold showed the decision needs its inputs on the table.
    """

    lines: dict[str, list[tuple[float, str]]] = {}
    measures: dict[str, float] = {}
    first_pages: dict[str, int] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in adapter._walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = (
                getattr(element, "attrib", {}).get(adapter._RUNT_KEY)
                if element is not None
                else None
            )
            if key is None or type(box).__name__ != "BlockBox":
                continue
            measures[key] = float(box.width)
            first_pages.setdefault(key, page_number)
            lines.setdefault(key, []).extend(
                (float(line.width), adapter._box_text(line))
                for line in adapter._walk_boxes(box)
                if type(line).__name__ == "LineBox"
            )
    paragraphs: list[ParagraphMeasurement] = []
    for key in sorted(lines, key=int):
        set_lines = lines[key]
        if len(set_lines) < 2:
            continue
        width, text = set_lines[-1]
        words = len(text.split())
        paragraphs.append(
            ParagraphMeasurement(
                key=key,
                page=first_pages[key],
                lines=len(set_lines),
                last_line_words=words,
                last_line_fraction=round(width / measures[key], 4),
                runt=words == 1,
            )
        )
    return tuple(paragraphs)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def fit_table(measurement: EditionMeasurement) -> str:
    """The compact human verdict ``mag fit`` prints.

    One line per budgeted span, its pages over its cap, and OK or OVER --
    written so that the eye finds the breach rather than the format.
    """

    width = max(
        [len("editorial")]
        + [len(article.id) for language in measurement.languages for article in language.articles]
    )
    rows = [f"{measurement.edition_id} — {measurement.engine} pagination"]
    for language in measurement.languages:
        rows.append(
            f"\n{language.language}  {language.total_pages} pages "
            f"(content {language.content_pages}, closing plates {language.closing_plates})"
        )
        if language.editorial is not None:
            rows.append(
                "  "
                + _fit_row(
                    "editorial",
                    width,
                    language.editorial.first_page,
                    language.editorial.last_page,
                    language.editorial.pages,
                    language.editorial.cap,
                    "OVER" if language.editorial.over else "OK",
                )
            )
        for article in language.articles:
            verdict = "OK"
            if article.over:
                verdict = "OVER"
            elif article.under_minimum:
                verdict = f"UNDER (minimum {article.minimum})"
            rows.append(
                "  "
                + _fit_row(
                    article.id,
                    width,
                    article.first_page,
                    article.last_page,
                    article.pages,
                    article.cap,
                    verdict,
                )
            )
    rows.append("")
    if measurement.ok:
        rows.append("fit: every page budget holds")
    else:
        rows.extend(f"over budget: {breach}" for breach in measurement.breaches)
    return "\n".join(rows)


def _fit_row(
    name: str, width: int, first: int, last: int, pages: int, cap: int, verdict: str
) -> str:
    span = f"p{first:02d}" if first == last else f"p{first:02d}-p{last:02d}"
    return f"{name:<{width}s}  {span:<9s}  {pages}/{cap}  {verdict}"
