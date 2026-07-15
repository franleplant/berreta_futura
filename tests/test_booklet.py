from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader, PdfWriter

from magazine.booklet import impose_a5_on_a4


class BookletTests(unittest.TestCase):
    def test_booklet_pads_and_imposes_to_a4_landscape(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            reader = tmp_path / "reader.pdf"
            writer = PdfWriter()
            for _ in range(5):
                writer.add_blank_page(width=419.5276, height=595.2756)
            with reader.open("wb") as handle:
                writer.write(handle)
            booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
            pages = PdfReader(str(booklet)).pages
            self.assertEqual(len(pages), 4)
            self.assertEqual(round(float(pages[0].mediabox.width)), 842)
            self.assertEqual(round(float(pages[0].mediabox.height)), 595)
