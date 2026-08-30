from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .errors import DependencyError


BOOKLET_SECTIONS = ("all", "interior", "cover")


A4_LANDSCAPE_POINTS = (841.8898, 595.2756)

_SECTION_TITLES = {
    "all": "Home booklet",
    "interior": "Home booklet interior",
    "cover": "Home booklet cover",
}


def booklet_spreads(page_count: int) -> tuple[tuple[int, int], ...]:
    total = ((page_count + 3) // 4) * 4
    spreads: list[tuple[int, int]] = []
    for sheet_index in range(total // 4):
        spreads.append((total - 2 * sheet_index, 1 + 2 * sheet_index))
        spreads.append((2 + 2 * sheet_index, total - 1 - 2 * sheet_index))
    return tuple(spreads)


def section_reader_pages(page_count: int, section: str = "all") -> tuple[int, ...]:
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
    padded: list[int | None] = [*reader_pages]
    padded += [None] * (-len(padded) % 4)
    return tuple(
        (padded[left - 1], padded[right - 1]) for left, right in booklet_spreads(len(padded))
    )


def cover_wrap_plan(page_count: int) -> tuple[tuple[int | None, int | None], ...]:
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
