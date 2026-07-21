import json
from pathlib import Path

import pytest

from magazine import Magazine, ValidationError
from magazine.render_review import (
    create_render_review,
    load_render_review,
    visual_review_status,
    write_render_review,
)
from test_manifest import make_project


def _package(path: Path, *, machine_result: str = "pass") -> Path:
    (path / "home").mkdir(parents=True)
    (path / "reader.pdf").write_bytes(b"reader")
    (path / "home" / "booklet-a4.pdf").write_bytes(b"booklet")
    (path / "render-critic.json").write_text(
        json.dumps({"result": machine_result, "page_count": 8}), encoding="utf-8"
    )
    return path


def test_review_record_is_bound_to_exact_reader_and_booklet_hashes(tmp_path: Path):
    package = _package(tmp_path / "output")
    record = create_render_review(
        edition_id="issue-001",
        reviewer="Independent critic",
        result="approved",
        language_packages={"en": package},
        reviewed_at="2026-07-21T18:00:00+00:00",
    )
    path = write_render_review(tmp_path / "reviews" / "render.yaml", record)

    loaded = load_render_review(path, edition_id="issue-001")
    status = visual_review_status(
        loaded,
        edition_id="issue-001",
        language="en",
        reader_pdf=package / "reader.pdf",
        booklet_pdf=package / "home" / "booklet-a4.pdf",
    )

    assert status["status"] == "approved"
    assert status["reviewer"] == "Independent critic"
    assert status["reviewed_at"] == "2026-07-21T18:00:00+00:00"


def test_changed_pdf_makes_an_approved_review_stale(tmp_path: Path):
    package = _package(tmp_path / "output")
    record = create_render_review(
        edition_id="issue-001",
        reviewer="Independent critic",
        result="approved",
        language_packages={"en": package},
    )
    (package / "reader.pdf").write_bytes(b"changed reader")

    status = visual_review_status(
        record,
        edition_id="issue-001",
        language="en",
        reader_pdf=package / "reader.pdf",
        booklet_pdf=package / "home" / "booklet-a4.pdf",
    )

    assert status["status"] == "stale"


def test_changes_required_review_needs_a_finding(tmp_path: Path):
    package = _package(tmp_path / "output")

    with pytest.raises(ValidationError, match="needs at least one finding"):
        create_render_review(
            edition_id="issue-001",
            reviewer="Independent critic",
            result="changes_required",
            language_packages={"en": package},
        )


def test_record_command_rebuilds_packages_with_approved_status(tmp_path: Path):
    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    magazine.build("issue-001")

    path, result = magazine.record_render_review(
        "issue-001",
        reviewer="Independent critic",
        result="approved",
        reviewed_at="2026-07-21T18:00:00+00:00",
    )

    report = json.loads((result.output_dir / "render-critic.json").read_text())
    assert path == tmp_path / "editions" / "issue-001" / "reviews" / "render.yaml"
    assert report["visual_review"]["status"] == "approved"
    assert report["visual_review"]["reviewer"] == "Independent critic"
    assert "render-critic.json" in (result.output_dir / "SHA256SUMS").read_text()

    result.reader_pdf.write_bytes(result.reader_pdf.read_bytes() + b"\nchanged")
    assert magazine.render_review_status("issue-001")["languages"]["en"]["status"] == "stale"
