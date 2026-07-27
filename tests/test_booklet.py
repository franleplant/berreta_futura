from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from magazine.booklet import (
    booklet_spreads,
    impose_a5_on_a4,
    imposed_reader_page_plan,
    section_reader_pages,
)

A5 = (419.5276, 595.2756)


def _numbered_reader(path: Path, page_count: int) -> Path:
    """An A5 reader whose every page says which reader page it is."""
    canvas = Canvas(str(path), pagesize=A5)
    for page in range(1, page_count + 1):
        canvas.setFont("Helvetica", 24)
        canvas.drawString(60, 300, f"READERPAGE{page}")
        canvas.showPage()
    canvas.save()
    return path


def _blank_reader(path: Path, page_count: int) -> Path:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=A5[0], height=A5[1])
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _imposed_page_pairs(booklet: Path) -> list[list[int]]:
    """Recover, per imposed side, the reader page numbers in left-to-right order."""
    sides = []
    for page in PdfReader(str(booklet)).pages:
        text = page.extract_text() or ""
        sides.append(
            [
                int(token.removeprefix("READERPAGE"))
                for token in text.split()
                if token.startswith("READERPAGE")
            ]
        )
    return sides


class BookletTests(unittest.TestCase):
    def test_spread_plan_records_short_edge_duplex_print_order(self):
        self.assertEqual(
            booklet_spreads(8),
            ((8, 1), (2, 7), (6, 3), (4, 5)),
        )

    def test_booklet_pads_and_imposes_to_a4_landscape(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            reader = _blank_reader(tmp_path / "reader.pdf", 5)
            booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
            pages = PdfReader(str(booklet)).pages
            self.assertEqual(len(pages), 4)
            self.assertEqual(round(float(pages[0].mediabox.width)), 842)
            self.assertEqual(round(float(pages[0].mediabox.height)), 595)

    def test_sections_select_the_cover_wrap_and_the_interior_between_inside_covers(self):
        self.assertEqual(section_reader_pages(36, "all"), tuple(range(1, 37)))
        self.assertEqual(section_reader_pages(36, "cover"), (1, 2, 35, 36))
        self.assertEqual(section_reader_pages(36, "interior"), tuple(range(3, 35)))
        with self.assertRaises(ValueError):
            section_reader_pages(36, "middle")
        with self.assertRaises(ValueError):
            section_reader_pages(2, "cover")

    def test_cover_document_prints_back_beside_front_then_the_inside_covers(self):
        self.assertEqual(
            imposed_reader_page_plan(section_reader_pages(36, "cover")),
            ((36, 1), (2, 35)),
        )

    def test_interior_plan_folds_the_body_pages_as_their_own_signature(self):
        plan = imposed_reader_page_plan(section_reader_pages(36, "interior"))
        self.assertEqual(len(plan), 16)
        self.assertEqual(plan[0], (34, 3))
        self.assertEqual(plan[1], (4, 33))
        self.assertEqual(plan[-1], (18, 19))
        self.assertNotIn(1, [page for pair in plan for page in pair])
        self.assertNotIn(2, [page for pair in plan for page in pair])
        self.assertNotIn(35, [page for pair in plan for page in pair])
        self.assertNotIn(36, [page for pair in plan for page in pair])

    def test_interior_pads_a_body_that_is_not_a_whole_signature(self):
        """A ten-page reader leaves six interior pages; the fold needs eight."""
        plan = imposed_reader_page_plan(section_reader_pages(10, "interior"))
        self.assertEqual(section_reader_pages(10, "interior"), (3, 4, 5, 6, 7, 8))
        self.assertEqual(len(plan), 4)
        self.assertEqual(plan, ((None, 3), (4, None), (8, 5), (6, 7)))

    def test_imposed_interior_pdf_carries_only_body_pages_in_print_order(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            reader = _numbered_reader(tmp_path / "reader.pdf", 12)
            interior = impose_a5_on_a4(
                reader, tmp_path / "interior.pdf", section="interior"
            )
            sides = _imposed_page_pairs(interior)
            self.assertEqual(len(PdfReader(str(interior)).pages), 4)
            self.assertEqual(sides, [[10, 3], [4, 9], [8, 5], [6, 7]])

    def test_imposed_cover_pdf_is_one_sheet_with_a_blank_inner_side(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            reader = _numbered_reader(tmp_path / "reader.pdf", 12)
            cover = impose_a5_on_a4(reader, tmp_path / "cover.pdf", section="cover")
            pages = PdfReader(str(cover)).pages
            self.assertEqual(len(pages), 2)
            self.assertEqual(round(float(pages[0].mediabox.width)), 842)
            self.assertEqual(round(float(pages[0].mediabox.height)), 595)
            self.assertEqual(_imposed_page_pairs(cover), [[12, 1], [2, 11]])

    def test_imposed_interior_pdf_pads_a_short_body_block(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            reader = _numbered_reader(tmp_path / "reader.pdf", 10)
            interior = impose_a5_on_a4(
                reader, tmp_path / "interior.pdf", section="interior"
            )
            self.assertEqual(len(PdfReader(str(interior)).pages), 4)
            self.assertEqual(_imposed_page_pairs(interior), [[3], [4], [8, 5], [6, 7]])

    def test_all_in_one_imposition_is_unchanged_by_the_split_sections(self):
        """The single-stock booklet's bytes are a shipped artifact; sectioning must not move them."""
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            reader = _numbered_reader(tmp_path / "reader.pdf", 12)
            default = impose_a5_on_a4(reader, tmp_path / "default.pdf")
            explicit = impose_a5_on_a4(reader, tmp_path / "explicit.pdf", section="all")
            self.assertEqual(default.read_bytes(), explicit.read_bytes())
            self.assertEqual(
                _imposed_page_pairs(default),
                [[12, 1], [2, 11], [10, 3], [4, 9], [8, 5], [6, 7]],
            )
