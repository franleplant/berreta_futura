from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageChops
from pypdf import PdfReader
import pytest
import yaml

from magazine import Magazine
from magazine.cover import (
    CoverPdfError,
    ORANGE,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    replace_outer_pages,
)
from test_manifest import add_spanish_translation, make_project


SVG = "{http://www.w3.org/2000/svg}"
BACK_TEXT = (
    "The loop is small. The factory is vast. Between them sits the difficult "
    "work: preserving intent, evidence, and human understanding."
)
SPANISH_BACK_TEXT = (
    "El ciclo es pequeño. La fábrica es inmensa. Entre ambos queda el trabajo "
    "difícil: preservar la intención, la evidencia y la comprensión humana."
)


def _make_back_cover_project(root: Path, *, spanish: bool = False) -> Magazine:
    make_project(root)
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["cover"]["back_text"] = BACK_TEXT
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    if spanish:
        add_spanish_translation(root)
        translation_path = (
            root
            / "editions"
            / "issue-001"
            / "translations"
            / "es"
            / "edition.yaml"
        )
        translation = yaml.safe_load(translation_path.read_text(encoding="utf-8"))
        translation["cover"]["back_text"] = SPANISH_BACK_TEXT
        translation_path.write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    return Magazine(root)


def _normalized_text(path: Path) -> str:
    return " ".join((PdfReader(path).pages[0].extract_text() or "").split())


def _write_labeled_pdf(path: Path, labels: tuple[str, ...]) -> None:
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    canvas = reportlab.Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    for label in labels:
        canvas.drawString(36, PAGE_HEIGHT - 48, label)
        canvas.showPage()
    canvas.save()


def test_signal_fold_back_proof_is_outlined_a5_svg_with_orange_on_every_trim_edge(
    tmp_path: Path,
) -> None:
    magazine = _make_back_cover_project(tmp_path)

    artifact = magazine.back_cover_proof("issue-001", languages=("en",))[0]

    root = ElementTree.parse(artifact.svg).getroot()
    slots = {
        element.attrib["data-slot"]
        for element in root.iter()
        if "data-slot" in element.attrib
    }
    assert {
        "field",
        "mass",
        "statement-panel",
        "statement",
        "owner",
        "slug",
        "identity-label",
    } <= slots
    assert list(root.iter(f"{SVG}path")), "back-cover type must be outlined"
    assert not list(root.iter(f"{SVG}text")), "canonical SVG must not use live text"

    pdf = PdfReader(artifact.pdf)
    assert len(pdf.pages) == 1
    assert float(pdf.pages[0].mediabox.width) == pytest.approx(PAGE_WIDTH, abs=.02)
    assert float(pdf.pages[0].mediabox.height) == pytest.approx(PAGE_HEIGHT, abs=.02)

    expected_orange = tuple(int(ORANGE[index : index + 2], 16) for index in (1, 3, 5))
    with Image.open(artifact.png) as opened:
        proof = opened.convert("RGB")
    trim_pixels = (
        *(proof.getpixel((x, 0)) for x in range(proof.width)),
        *(proof.getpixel((x, proof.height - 1)) for x in range(proof.width)),
        *(proof.getpixel((0, y)) for y in range(proof.height)),
        *(proof.getpixel((proof.width - 1, y)) for y in range(proof.height)),
    )
    assert all(
        max(abs(channel - expected) for channel, expected in zip(pixel, expected_orange))
        <= 2
        for pixel in trim_pixels
    ), "the orange field must paint all four outermost trim edges"


def test_back_proof_has_selectable_localized_statement_owner_and_end_labels(
    tmp_path: Path,
) -> None:
    magazine = _make_back_cover_project(tmp_path, spanish=True)

    artifacts = magazine.back_cover_proof("issue-001", languages=("en", "es"))

    by_language = {artifact.language: artifact for artifact in artifacts}
    english = _normalized_text(by_language["en"].pdf)
    spanish = _normalized_text(by_language["es"].pdf)
    assert BACK_TEXT in english
    assert "ISSUE STATEMENT / THE EDITORS" in english
    assert "END" in english
    assert SPANISH_BACK_TEXT in spanish
    assert "DECLARACIÓN DEL NÚMERO / LA REDACCIÓN" in spanish
    assert "FIN" in spanish
    assert BACK_TEXT not in spanish


def test_built_reader_uses_exact_back_proof_and_preserves_both_blank_inside_covers(
    tmp_path: Path,
) -> None:
    magazine = _make_back_cover_project(tmp_path)
    proof = magazine.back_cover_proof("issue-001", languages=("en",))[0]

    result = magazine.build("issue-001")

    reader = PdfReader(result.reader_pdf)
    page_count = len(reader.pages)
    assert page_count >= 4
    assert (reader.pages[1].extract_text() or "").strip() == ""
    assert (reader.pages[-2].extract_text() or "").strip() == ""
    assert BACK_TEXT in " ".join((reader.pages[-1].extract_text() or "").split())

    review = result.output_dir / "render-review" / "reader-pages"
    with Image.open(proof.png) as opened:
        expected = opened.convert("RGB")
    with Image.open(review / f"page-{page_count:03d}.png") as opened:
        actual = opened.convert("RGB")
    assert actual.size == expected.size
    assert ImageChops.difference(actual, expected).getbbox() is None

    for page_number in (2, page_count - 1):
        with Image.open(review / f"page-{page_number:03d}.png") as opened:
            blank = opened.convert("L")
        assert blank.getextrema() == (255, 255)


def test_replace_outer_pages_preserves_interior_order_and_rejects_invalid_inputs(
    tmp_path: Path,
) -> None:
    reader = tmp_path / "reader.pdf"
    front = tmp_path / "front.pdf"
    back = tmp_path / "back.pdf"
    output = tmp_path / "complete.pdf"
    _write_labeled_pdf(reader, ("OLD FRONT", "INTERIOR TWO", "INTERIOR THREE", "OLD BACK"))
    _write_labeled_pdf(front, ("NEW FRONT",))
    _write_labeled_pdf(back, ("NEW BACK",))

    assert replace_outer_pages(reader, front, back, output) == output

    pages = PdfReader(output).pages
    assert [" ".join((page.extract_text() or "").split()) for page in pages] == [
        "NEW FRONT",
        "INTERIOR TWO",
        "INTERIOR THREE",
        "NEW BACK",
    ]

    invalid_reader = tmp_path / "invalid-reader.pdf"
    invalid_back = tmp_path / "invalid-back.pdf"
    _write_labeled_pdf(invalid_reader, ("ONE", "TWO", "THREE"))
    _write_labeled_pdf(invalid_back, ("BACK ONE", "BACK TWO"))
    with pytest.raises(CoverPdfError, match="at least four pages"):
        replace_outer_pages(invalid_reader, front, back, output)
    with pytest.raises(CoverPdfError, match="exactly one"):
        replace_outer_pages(reader, front, invalid_back, output)
