"""The release package's own write discipline."""

import json
from pathlib import Path

import pytest
from pypdf import PdfReader

import magazine.package as package_module
from magazine import Magazine
from test_manifest import make_project


def test_manifest_is_written_before_the_render_critic_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fresh PDFs must never sit beside a stale manifest, even mid-crash.

    ``package_release`` writes ``edition-manifest.json`` as soon as the PDFs it
    describes exist and before the render critic runs -- the critic reads
    nothing from it -- so a crash (or a critic failure) anywhere later in
    packaging cannot leave ``reader.pdf`` paired with the previous build's
    manifest.  Pinned by crashing the critic itself: the manifest must already
    be on disk describing the new reader, and no critic report may exist.
    """
    make_project(tmp_path)
    magazine = Magazine(tmp_path)

    def crash(*args, **kwargs):
        raise RuntimeError("critic crashed")

    monkeypatch.setattr(package_module, "inspect_render", crash)
    with pytest.raises(RuntimeError, match="critic crashed"):
        magazine.build("issue-001")

    destination = tmp_path / "output" / "issue-001"
    assert (destination / "reader.pdf").is_file()
    assert not (destination / "render-critic.json").exists()
    manifest = json.loads((destination / "edition-manifest.json").read_text(encoding="utf-8"))
    assert manifest["layout"]["design_direction"]


def test_package_ships_and_checksums_all_three_a4_booklets(tmp_path: Path):
    """The split cover and interior are package files, so SHA256SUMS must cover them."""
    make_project(tmp_path)
    result = Magazine(tmp_path).build("issue-001")

    destination = tmp_path / "output" / "issue-001"
    booklets = ["booklet-a4.pdf", "booklet-a4-cover.pdf", "booklet-a4-interior.pdf"]
    for name in booklets:
        assert (destination / "home" / name).is_file()

    listed = {
        line.split("  ", 1)[1]
        for line in (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    }
    for name in booklets:
        assert f"home/{name}" in listed
    assert {path.relative_to(destination).as_posix() for path in result.files} >= {
        f"home/{name}" for name in booklets
    }

    digests = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    }
    for name in booklets:
        assert digests[f"home/{name}"] == package_module.sha256(destination / "home" / name)


def test_printing_instructions_explain_every_booklet_and_its_stock(tmp_path: Path):
    make_project(tmp_path)
    Magazine(tmp_path).build("issue-001")

    destination = tmp_path / "output" / "issue-001"
    reader_pages = len(PdfReader(str(destination / "reader.pdf")).pages)
    interior_sheets = len(
        PdfReader(str(destination / "home" / "booklet-a4-interior.pdf")).pages
    ) // 2
    instructions = (destination / "home" / "printing-instructions.md").read_text(
        encoding="utf-8"
    )

    assert "booklet-a4.pdf — all in one" in instructions
    assert "booklet-a4-interior.pdf — interior on text stock" in instructions
    assert "booklet-a4-cover.pdf — cover wrap on heavier stock" in instructions
    assert "short edge" in instructions
    assert f"Reader pages 3 to {reader_pages - 2}" in instructions
    assert f"{interior_sheets} A4 sheets on ordinary 80-100 gsm" in instructions
    assert "1 A4 sheet." in instructions
    assert "160-250 gsm" in instructions
    assert "its inner side is blank by design" in instructions
    assert "nest the interior inside the folded cover" in instructions


def test_spanish_printing_instructions_cover_the_split_pair(tmp_path: Path):
    make_project(tmp_path)
    text = package_module._printing_instructions(
        "es", reader_page_count=36, all_in_one_sheets=9, interior_sheets=8, cover_sheets=1
    )

    assert "booklet-a4-interior.pdf — interior en papel de texto" in text
    assert "booklet-a4-cover.pdf — cubierta en papel más grueso" in text
    assert "Las páginas 3 a 34" in text
    assert "9 hojas A4" in text
    assert "8 hojas A4" in text
    assert "160 a 250 g/m²" in text
    assert "borde corto" in text
