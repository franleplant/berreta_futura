from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from PIL import Image, ImageChops
from pypdf import PdfReader
import pytest
import yaml

from magazine import Magazine
from magazine.cover import CoverCompiler, ORANGE, PAGE_HEIGHT, PAGE_WIDTH
from test_manifest import make_project


SVG = "{http://www.w3.org/2000/svg}"


def _make_cover_project(root: Path) -> Magazine:
    make_project(root)
    art = root / "editions" / "issue-001" / "art" / "cover.png"
    Image.new("RGB", (1200, 1200), "#101010").save(art)
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["cover"].update(
        {
            "art_path": art.relative_to(root).as_posix(),
            "deck": "A deterministic cover proof used by the compiler test suite.",
        }
    )
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    return Magazine(root)


def test_cover_proof_is_self_contained_outlined_svg_with_a5_pdf_and_full_bleed_tab(
    tmp_path: Path,
) -> None:
    magazine = _make_cover_project(tmp_path)

    artifact = magazine.cover_proof("issue-001", languages=("en",))[0]

    root = ElementTree.parse(artifact.svg).getroot()
    slots = {
        element.attrib["data-slot"]
        for element in root.iter()
        if "data-slot" in element.attrib
    }
    assert {
        "paper",
        "edge-tab",
        "wordmark",
        "headline",
        "art",
        "art-border",
        "deck",
        "footer",
        "issue-label",
        "identity-label",
    } <= slots
    assert list(root.iter(f"{SVG}path")), "cover typography must be materialized as paths"
    assert not list(root.iter(f"{SVG}text")), "canonical SVG must not depend on live fonts"

    cover = PdfReader(artifact.pdf)
    assert len(cover.pages) == 1
    assert float(cover.pages[0].mediabox.width) == pytest.approx(PAGE_WIDTH, abs=.02)
    assert float(cover.pages[0].mediabox.height) == pytest.approx(PAGE_HEIGHT, abs=.02)
    selectable = cover.pages[0].extract_text() or ""
    assert "AUTHOR" in selectable
    assert "A DETERMINISTIC COVER PROOF" not in selectable

    expected_orange = tuple(int(ORANGE[index : index + 2], 16) for index in (1, 3, 5))
    with Image.open(artifact.png) as opened:
        proof = opened.convert("RGB")
    assert all(
        max(
            abs(channel - expected)
            for channel, expected in zip(
                proof.getpixel((proof.width - 1, y)), expected_orange
            )
        )
        <= 2
        for y in range(proof.height)
    ), "the edge tab must paint the outermost trim pixel for the full page height"


def test_built_reader_uses_exact_cover_proof_and_marks_inside_front_cover(
    tmp_path: Path,
) -> None:
    magazine = _make_cover_project(tmp_path)
    proof = magazine.cover_proof("issue-001", languages=("en",))[0]

    result = magazine.build("issue-001")

    with Image.open(proof.png) as opened:
        expected = opened.convert("RGB")
    with Image.open(
        result.output_dir / "render-review" / "reader-pages" / "page-001.png"
    ) as opened:
        actual = opened.convert("RGB")
    assert actual.size == expected.size
    assert ImageChops.difference(actual, expected).getbbox() is None

    reader = PdfReader(result.reader_pdf)
    assert (reader.pages[1].extract_text() or "").strip() == ""
    with Image.open(
        result.output_dir / "render-review" / "reader-pages" / "page-002.png"
    ) as opened:
        inside_cover = opened.convert("L")
    bbox = Image.eval(inside_cover, lambda value: 255 if value < 250 else 0).getbbox()
    assert bbox is not None
    assert bbox[0] < inside_cover.width * .25
    assert bbox[1] > inside_cover.height * .75


def test_cover_proof_cache_reuses_deterministic_svg_pdf_and_png(
    tmp_path: Path,
) -> None:
    magazine = _make_cover_project(tmp_path)
    first = magazine.cover_proof("issue-001", languages=("en",))[0]
    first_proof = json.loads(first.proof_json.read_text(encoding="utf-8"))
    mtimes = {
        path: path.stat().st_mtime_ns
        for path in (first.svg, first.pdf, first.png)
    }

    with (
        patch.object(CoverCompiler, "_svg_to_pdf", side_effect=AssertionError("cache miss")),
        patch.object(CoverCompiler, "_rasterize_pdf", side_effect=AssertionError("cache miss")),
    ):
        second = magazine.cover_proof("issue-001", languages=("en",))[0]

    assert second.input_sha256 == first.input_sha256
    assert second.pdf_sha256 == first.pdf_sha256
    assert second.png_sha256 == first.png_sha256
    assert json.loads(second.proof_json.read_text(encoding="utf-8")) == first_proof
    assert {path: path.stat().st_mtime_ns for path in mtimes} == mtimes
