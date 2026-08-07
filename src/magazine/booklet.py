from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .errors import DependencyError

#: The three A4 saddle-stitch documents a package ships.  ``"all"`` is the
#: single-stock booklet that has always been built; ``"cover"`` and
#: ``"interior"`` split the same block the way a bindery does, so the wrap can
#: go on heavier stock than the text pages.
BOOKLET_SECTIONS = ("all", "interior", "cover")

#: One imposed side: two A5 reader pages side by side on landscape A4.
A4_LANDSCAPE_POINTS = (841.8898, 595.2756)

_SECTION_TITLES = {
    "all": "Home booklet",
    "interior": "Home booklet interior",
    "cover": "Home booklet cover",
}


def booklet_spreads(page_count: int) -> tuple[tuple[int, int], ...]:
    """Return left/right reader folios in short-edge duplex print order."""
    total = ((page_count + 3) // 4) * 4
    spreads: list[tuple[int, int]] = []
    for sheet_index in range(total // 4):
        spreads.append((total - 2 * sheet_index, 1 + 2 * sheet_index))
        spreads.append((2 + 2 * sheet_index, total - 1 - 2 * sheet_index))
    return tuple(spreads)


def section_reader_pages(page_count: int, section: str = "all") -> tuple[int, ...]:
    """Return the reader pages a booklet section imposes, in reader order.

    Reader anatomy: page 1 is the front cover, page 2 the blank inside front
    cover, ``page_count - 1`` the blank inside back cover, and ``page_count``
    the back cover.  The cover section is exactly that outer sheet; the interior
    is everything between the two inside covers.  Both are returned in *reader*
    order -- turning that order into print order is
    :func:`imposed_reader_page_plan`'s single job, so all three documents fold
    the same way.
    """
    if section not in BOOKLET_SECTIONS:
        raise ValueError(f"Unknown booklet section {section!r}; expected one of {BOOKLET_SECTIONS}.")
    if section == "all":
        return tuple(range(1, page_count + 1))
    if page_count < 4:
        raise ValueError(
            f"A {page_count}-page reader has no separable cover wrap; a cover sheet needs four pages."
        )
    if section == "cover":
        return (1, 2, page_count - 1, page_count)
    return tuple(range(3, page_count - 1))


def imposed_reader_page_plan(
    reader_pages: Sequence[int],
) -> tuple[tuple[int | None, int | None], ...]:
    """Turn reader pages into per-side ``(left, right)`` reader page numbers.

    The selection is padded with blanks to a whole signature and then folded by
    :func:`booklet_spreads`, so every section -- the whole magazine, the
    interior alone, or the cover wrap -- is short-edge-duplex correct by the
    same rule.  ``None`` marks a padded blank half-side.
    """
    padded: list[int | None] = [*reader_pages]
    padded += [None] * (-len(padded) % 4)
    return tuple(
        (padded[left - 1], padded[right - 1]) for left, right in booklet_spreads(len(padded))
    )


def cover_wrap_plan(page_count: int) -> tuple[tuple[int | None, int | None], ...]:
    """The cover wrap's print plan: one side, back cover beside front cover.

    booklet-a4-cover.pdf prints single-sided (editor's rule, 2026-08-07): the
    wrap's inside faces are blank by contract, so the document carries only
    the outside spread and heavier stock goes through the printer once.  The
    all-in-one and interior booklets keep their duplex plans untouched.
    """
    return imposed_reader_page_plan(section_reader_pages(page_count, "cover"))[:1]


def impose_a5_on_a4(reader_pdf: Path, output: Path, *, section: str = "all") -> Path:
    try:
        from pypdf import PdfReader, PdfWriter, Transformation
        from pypdf._page import PageObject
    except ImportError as exc:
        raise DependencyError("Booklet imposition requires pypdf; run `uv sync --locked`.") from exc
    reader = PdfReader(str(reader_pdf))
    pages = list(reader.pages)
    plan = (
        cover_wrap_plan(len(pages))
        if section == "cover"
        else imposed_reader_page_plan(section_reader_pages(len(pages), section))
    )
    a4_landscape = A4_LANDSCAPE_POINTS
    half = a4_landscape[0] / 2
    writer = PdfWriter()

    def add_spread(left_number: int | None, right_number: int | None):
        sheet = PageObject.create_blank_page(width=a4_landscape[0], height=a4_landscape[1])
        for page_number, x in ((left_number, 0), (right_number, half)):
            if page_number is None:
                continue
            source = pages[page_number - 1]
            width, height = float(source.mediabox.width), float(source.mediabox.height)
            scale = min(half / width, a4_landscape[1] / height)
            sheet.merge_transformed_page(source, Transformation().scale(scale).translate(x, 0))
        writer.add_page(sheet)

    for left_number, right_number in plan:
        add_spread(left_number, right_number)
    writer.add_metadata({"/Title": _SECTION_TITLES[section], "/Creator": "magazine-compiler"})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)
    return output
