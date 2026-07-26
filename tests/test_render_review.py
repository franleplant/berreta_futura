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


WEASYPRINT_DIRECTION = "WeasyPrint / A5 fold proof"


def _package(
    path: Path,
    *,
    machine_result: str = "pass",
    design_direction: str = WEASYPRINT_DIRECTION,
) -> Path:
    (path / "home").mkdir(parents=True)
    (path / "reader.pdf").write_bytes(b"reader")
    (path / "home" / "booklet-a4.pdf").write_bytes(b"booklet")
    (path / "render-critic.json").write_text(
        json.dumps({"result": machine_result, "page_count": 8}), encoding="utf-8"
    )
    (path / "edition-manifest.json").write_text(
        json.dumps({"layout": {"design_direction": design_direction}}), encoding="utf-8"
    )
    return path


def test_review_record_is_bound_to_exact_reader_and_booklet_hashes(tmp_path: Path):
    package = _package(tmp_path / "output")
    record = create_render_review(
        edition_id="issue-001",
        reviewer="Independent critic",
        result="approved",
        language_packages={"en": package},
        engine="weasyprint",
        design_direction=WEASYPRINT_DIRECTION,
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
    assert loaded["engine"] == "weasyprint"
    assert loaded["design_direction"] == WEASYPRINT_DIRECTION


def test_changed_pdf_makes_an_approved_review_stale(tmp_path: Path):
    package = _package(tmp_path / "output")
    record = create_render_review(
        edition_id="issue-001",
        reviewer="Independent critic",
        result="approved",
        language_packages={"en": package},
        engine="weasyprint",
        design_direction=WEASYPRINT_DIRECTION,
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
            engine="weasyprint",
            design_direction=WEASYPRINT_DIRECTION,
        )


def test_review_refuses_a_package_built_by_a_different_engine(tmp_path: Path):
    """The record binds a decision to pages a named engine set; a package whose
    manifest names another design direction was reviewed on the wrong PDFs."""
    package = _package(tmp_path / "output", design_direction="A / Quiet Standard")

    with pytest.raises(ValidationError, match="rendered as 'A / Quiet Standard'"):
        create_render_review(
            edition_id="issue-001",
            reviewer="Independent critic",
            result="approved",
            language_packages={"en": package},
            engine="weasyprint",
            design_direction=WEASYPRINT_DIRECTION,
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
    recorded = load_render_review(path, edition_id="issue-001")
    manifest = json.loads((result.output_dir / "edition-manifest.json").read_text())
    assert recorded["engine"] == "weasyprint"
    assert recorded["design_direction"] == manifest["layout"]["design_direction"]

    result.reader_pdf.write_bytes(result.reader_pdf.read_bytes() + b"\nchanged")
    assert magazine.render_review_status("issue-001")["languages"]["en"]["status"] == "stale"


def test_record_requires_a_named_engine_and_design_direction(tmp_path: Path):
    """The guard at the seam: a record that cannot say what it reviewed is refused."""
    package = _package(tmp_path / "output")

    for engine, direction in (
        ("   ", WEASYPRINT_DIRECTION),
        ("weasyprint", ""),
    ):
        with pytest.raises(ValidationError, match="engine and design direction"):
            create_render_review(
                edition_id="issue-001",
                reviewer="Independent critic",
                result="approved",
                language_packages={"en": package},
                engine=engine,
                design_direction=direction,
            )


def test_record_command_refuses_a_rebuild_that_misses_the_recorded_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Recording rebuilds and then proves the rebuilt PDFs are the recorded ones.

    A record whose hashes the deterministic rebuild does not reproduce is stale
    the moment it is written; that used to surface only as a release-time
    ``status: "stale"`` refusal, and is an error at record time instead.
    """
    import magazine.compiler as compiler_module

    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    magazine.build("issue-001")

    real = compiler_module.create_render_review

    def corrupted(**kwargs):
        record = real(**kwargs)
        record["languages"]["en"]["reader_sha256"] = "0" * 64
        return record

    monkeypatch.setattr(compiler_module, "create_render_review", corrupted)
    with pytest.raises(ValidationError, match="did not reproduce"):
        magazine.record_render_review(
            "issue-001", reviewer="Independent critic", result="approved"
        )


def test_record_with_engine_override_rebuilds_with_the_recorded_engine(tmp_path: Path):
    """One renderer resolution serves the record *and* the rebuild.

    The packages are built off-config with ReportLab and the decision is
    recorded with the matching ``--engine``.  If the rebuild inside
    ``record_render_review`` ever dropped ``engine=renderer.engine`` it would
    silently repackage with the configured WeasyPrint: the rebuilt hashes would
    miss the recorded ones and the rebuilt manifest would name the wrong design
    direction, and either failure fails this test.
    """
    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    magazine.build("issue-001", engine="reportlab")

    path, result = magazine.record_render_review(
        "issue-001",
        reviewer="Independent critic",
        result="approved",
        engine="reportlab",
    )

    recorded = load_render_review(path, edition_id="issue-001")
    manifest = json.loads((result.output_dir / "edition-manifest.json").read_text())
    assert recorded["engine"] == "reportlab"
    assert manifest["layout"]["design_direction"] == recorded["design_direction"]
    assert recorded["design_direction"] != WEASYPRINT_DIRECTION
    report = json.loads((result.output_dir / "render-critic.json").read_text())
    assert report["visual_review"]["status"] == "approved"


def test_legacy_review_record_without_engine_keys_still_loads(tmp_path: Path):
    """Edition 002's record predates the engine keys and must keep loading."""
    record = {
        "schema_version": 1,
        "edition_id": "issue-001",
        "reviewer": "Independent critic",
        "reviewed_at": "2026-07-21T18:00:00+00:00",
        "result": "approved",
        "findings": [],
        "notes": "",
        "languages": {
            "en": {"reader_sha256": "0" * 64, "booklet_sha256": "1" * 64},
        },
    }
    path = write_render_review(tmp_path / "reviews" / "render.yaml", record)

    loaded = load_render_review(path, edition_id="issue-001")

    assert loaded is not None
    assert "engine" not in loaded

    record["engine"] = "   "
    path = write_render_review(tmp_path / "reviews" / "render.yaml", record)
    with pytest.raises(ValidationError, match="engine must be a non-empty string"):
        load_render_review(path, edition_id="issue-001")
