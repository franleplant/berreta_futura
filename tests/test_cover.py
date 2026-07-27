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
ORANGE_RGB = tuple(int(ORANGE[index : index + 2], 16) for index in (1, 3, 5))


def _classify(pixel: tuple[int, int, int]) -> str:
    """Name a proof pixel as band orange, unprinted paper, or an edge blend."""
    if max(abs(channel - expected) for channel, expected in zip(pixel, ORANGE_RGB)) <= 2:
        return "orange"
    if all(channel >= 253 for channel in pixel):
        return "paper"
    return "edge"


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


def test_cover_proof_is_self_contained_outlined_svg_with_a5_pdf_and_one_solid_tab(
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

    with Image.open(artifact.png) as opened:
        proof = opened.convert("RGB")
    tab = CoverCompiler(tmp_path).design["tab"]
    reveal = float(tab["edge_reveal"])
    band_left = PAGE_WIDTH - float(tab["width"])
    scale = proof.width / PAGE_WIDTH

    # The fore-edge tab is one solid orange band that stops short of the right
    # trim, so the outermost pixel column is unprinted paper for the full page
    # height and the band still bleeds off the head and the foot.
    assert all(
        _classify(proof.getpixel((proof.width - 1, y))) == "paper"
        for y in range(proof.height)
    ), "the paper reveal must own the outermost trim pixel for the full page height"
    inside_band = round((PAGE_WIDTH - reveal - 1.0) * scale)
    assert all(
        _classify(proof.getpixel((inside_band, y))) == "orange"
        for y in range(proof.height)
    ), "the orange band must run unbroken from the head trim to the foot trim"

    # Reading a label-free row outward from the band's inner edge, the page
    # must show exactly one orange run and then one paper hairline: nothing
    # splits the band, and the reveal is the only white in the tab.
    for y_points in (250.0, 380.0):
        row = [
            _classify(proof.getpixel((x, round(y_points * scale))))
            for x in range(round(band_left * scale) + 1, proof.width)
        ]
        runs = []
        for value in row:
            if not runs or runs[-1][0] != value:
                runs.append([value, 0])
            runs[-1][1] += 1
        solid = [(value, length) for value, length in runs if length > 2]
        assert [value for value, _ in solid] == ["orange", "paper"], (
            f"row at {y_points}pt must read as one orange band then one paper "
            f"hairline, got {runs}"
        )
        # The rasterizer snaps both vector edges outward, so the printed
        # hairline may land up to a pixel wider than its authored width.
        assert solid[1][1] / scale == pytest.approx(reveal, abs=2.0 / scale)


def test_built_reader_uses_exact_cover_proof_and_leaves_inside_front_cover_blank(
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
    assert bbox is None


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
