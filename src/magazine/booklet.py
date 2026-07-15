from __future__ import annotations

from pathlib import Path

from .errors import DependencyError


def impose_a5_on_a4(reader_pdf: Path, output: Path) -> Path:
    try:
        from pypdf import PdfReader, PdfWriter, Transformation
        from pypdf._page import PageObject
    except ImportError as exc:
        raise DependencyError("Booklet imposition requires pypdf (`pip install pypdf`).") from exc
    reader = PdfReader(str(reader_pdf))
    pages = list(reader.pages)
    while len(pages) % 4:
        pages.append(None)
    total = len(pages)
    a4_landscape = (841.8898, 595.2756)
    half = a4_landscape[0] / 2
    writer = PdfWriter()

    def add_spread(left_number: int, right_number: int):
        sheet = PageObject.create_blank_page(width=a4_landscape[0], height=a4_landscape[1])
        for page_number, x in ((left_number, 0), (right_number, half)):
            source = pages[page_number - 1]
            if source is None:
                continue
            width, height = float(source.mediabox.width), float(source.mediabox.height)
            scale = min(half / width, a4_landscape[1] / height)
            sheet.merge_transformed_page(source, Transformation().scale(scale).translate(x, 0))
        writer.add_page(sheet)

    for sheet_index in range(total // 4):
        add_spread(total - 2 * sheet_index, 1 + 2 * sheet_index)
        add_spread(2 + 2 * sheet_index, total - 1 - 2 * sheet_index)
    writer.add_metadata({"/Title": "Home booklet", "/Creator": "magazine-compiler"})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)
    return output

