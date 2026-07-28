import hashlib
import json
from pathlib import Path

import pytest

from magazine import Magazine, ValidationError
from magazine.render_review import (
    create_render_review,
    embed_recorded_review,
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


def test_record_command_embeds_the_decision_without_rebuilding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Recording exposes the decision in the existing package in place.

    The old rebuild's only review-bearing output was render-critic.json's
    ``visual_review`` block and that report's SHA256SUMS line; recording must
    now update exactly those, leave every PDF byte alone, and never re-typeset.
    """
    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    built = magazine.build("issue-001")
    reader_before = built.reader_pdf.read_bytes()
    monkeypatch.setattr(
        Magazine,
        "build",
        lambda *args, **kwargs: pytest.fail("recording must not rebuild"),
    )

    path, output_dir = magazine.record_render_review(
        "issue-001",
        reviewer="Independent critic",
        result="approved",
        reviewed_at="2026-07-21T18:00:00+00:00",
    )

    assert path == tmp_path / "editions" / "issue-001" / "reviews" / "render.yaml"
    assert output_dir == built.output_dir
    assert built.reader_pdf.read_bytes() == reader_before
    report_path = output_dir / "render-critic.json"
    report = json.loads(report_path.read_text())
    assert report["visual_review"]["status"] == "approved"
    assert report["visual_review"]["reviewer"] == "Independent critic"
    # The build's own artifact lists survive the in-place update.
    assert report["visual_review"]["reader_contact_sheets"]
    checksums = {
        name: checksum
        for checksum, name in (
            line.split("  ", 1)
            for line in (output_dir / "SHA256SUMS").read_text().splitlines()
        )
    }
    assert checksums["render-critic.json"] == hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    assert checksums["reader.pdf"] == hashlib.sha256(reader_before).hexdigest()
    recorded = load_render_review(path, edition_id="issue-001")
    manifest = json.loads((output_dir / "edition-manifest.json").read_text())
    assert recorded["engine"] == "weasyprint"
    assert recorded["design_direction"] == manifest["layout"]["design_direction"]

    built.reader_pdf.write_bytes(built.reader_pdf.read_bytes() + b"\nchanged")
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


def test_record_command_refuses_to_expose_a_decision_beside_other_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The in-place update is guarded by the binding itself: a record whose
    hashes miss the package's PDFs must be refused, not embedded -- exposing a
    decision beside pages it never judged would launder staleness."""
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
    with pytest.raises(ValidationError, match="not the bytes the review record binds to"):
        magazine.record_render_review(
            "issue-001", reviewer="Independent critic", result="approved"
        )


def test_record_rebuild_escape_hatch_still_proves_reproducibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """``--rebuild`` keeps the old proof: re-typeset and require the
    deterministic build to reproduce the recorded bytes, erroring at record
    time rather than as a release-time ``status: "stale"`` refusal."""
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
            "issue-001", reviewer="Independent critic", result="approved", rebuild=True
        )


def test_record_with_engine_override_binds_the_reviewed_engines_pages(tmp_path: Path):
    """One renderer resolution serves the whole record.

    The packages are built off-config with ReportLab and the decision is
    recorded with the matching ``--engine``.  The record must name that engine
    and bind to the package the reviewer inspected -- a mismatch against the
    package manifest's design direction is refused by ``create_render_review``.
    """
    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    built = magazine.build("issue-001", engine="reportlab")

    path, output_dir = magazine.record_render_review(
        "issue-001",
        reviewer="Independent critic",
        result="approved",
        engine="reportlab",
    )

    assert output_dir == built.output_dir
    recorded = load_render_review(path, edition_id="issue-001")
    manifest = json.loads((output_dir / "edition-manifest.json").read_text())
    assert recorded["engine"] == "reportlab"
    assert manifest["layout"]["design_direction"] == recorded["design_direction"]
    assert recorded["design_direction"] != WEASYPRINT_DIRECTION
    report = json.loads((output_dir / "render-critic.json").read_text())
    assert report["visual_review"]["status"] == "approved"


def _reviewable_package(path: Path) -> Path:
    """A ``_package`` whose report and checksums look like a real build's."""
    package = _package(path)
    (package / "render-critic.json").write_text(
        json.dumps(
            {
                "result": "pass",
                "page_count": 8,
                "visual_review": {
                    "status": "required_before_release",
                    "reader_contact_sheets": ["render-review/reader-sheet-1.png"],
                },
            }
        ),
        encoding="utf-8",
    )
    (package / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((package / name).read_bytes()).hexdigest()}  {name}\n"
            for name in ("home/booklet-a4.pdf", "reader.pdf", "render-critic.json")
        ),
        encoding="utf-8",
    )
    return package


def _record_for(package: Path) -> dict:
    return create_render_review(
        edition_id="issue-001",
        reviewer="Independent critic",
        result="approved",
        language_packages={"en": package},
        engine="weasyprint",
        design_direction=WEASYPRINT_DIRECTION,
        reviewed_at="2026-07-21T18:00:00+00:00",
    )


def test_embed_updates_the_report_and_refreshes_only_its_checksum_line(tmp_path: Path):
    package = _reviewable_package(tmp_path / "output")
    lines_before = dict(
        line.split("  ", 1)[::-1]
        for line in (package / "SHA256SUMS").read_text().splitlines()
    )

    embed_recorded_review(package, _record_for(package), edition_id="issue-001", language="en")

    report_path = package / "render-critic.json"
    report = json.loads(report_path.read_text())
    assert report["visual_review"]["status"] == "approved"
    assert report["visual_review"]["reviewer"] == "Independent critic"
    # The build's artifact lists inside the block survive the update.
    assert report["visual_review"]["reader_contact_sheets"] == [
        "render-review/reader-sheet-1.png"
    ]
    lines_after = dict(
        line.split("  ", 1)[::-1]
        for line in (package / "SHA256SUMS").read_text().splitlines()
    )
    assert lines_after["render-critic.json"] == hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    assert lines_after["reader.pdf"] == lines_before["reader.pdf"]
    assert lines_after["home/booklet-a4.pdf"] == lines_before["home/booklet-a4.pdf"]


def test_embed_refuses_pdfs_the_record_does_not_bind_to(tmp_path: Path):
    package = _reviewable_package(tmp_path / "output")
    record = _record_for(package)
    (package / "reader.pdf").write_bytes(b"changed reader")

    with pytest.raises(ValidationError, match="not the bytes the review record binds to"):
        embed_recorded_review(package, record, edition_id="issue-001", language="en")


def test_embed_refuses_an_incomplete_package(tmp_path: Path):
    package = _package(tmp_path / "output")
    record = _record_for(package)

    with pytest.raises(ValidationError, match="missing SHA256SUMS"):
        embed_recorded_review(package, record, edition_id="issue-001", language="en")


def test_embed_refuses_checksums_that_never_listed_the_report(tmp_path: Path):
    package = _reviewable_package(tmp_path / "output")
    record = _record_for(package)
    (package / "SHA256SUMS").write_text("0" * 64 + "  reader.pdf\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="does not list render-critic.json"):
        embed_recorded_review(package, record, edition_id="issue-001", language="en")


def test_embed_refuses_a_package_that_fails_its_own_inventory(tmp_path: Path):
    """A reader.pdf tampered after the build but before recording binds
    cleanly -- the record hashes whatever bytes are on disk -- yet the
    package's own SHA256SUMS still names the build's bytes.  Embedding must
    refuse rather than seal an approval inside a package that fails its own
    inventory."""
    package = _reviewable_package(tmp_path / "output")
    (package / "reader.pdf").write_bytes(b"tampered after build")
    record = _record_for(package)  # binds the tampered bytes, so no staleness

    with pytest.raises(ValidationError, match="no longer matches its own inventory"):
        embed_recorded_review(package, record, edition_id="issue-001", language="en")


def test_a_malformed_render_critic_report_is_refused_not_a_traceback(tmp_path: Path):
    """A hand-damaged render-critic.json used to escape as a raw
    json.JSONDecodeError the CLI could not catch; both the recording and the
    embedding seams must refuse it as a validation error naming the file."""
    package = _package(tmp_path / "output")
    (package / "render-critic.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValidationError, match="render-critic.json"):
        create_render_review(
            edition_id="issue-001",
            reviewer="Independent critic",
            result="approved",
            language_packages={"en": package},
            engine="weasyprint",
            design_direction=WEASYPRINT_DIRECTION,
        )

    package = _reviewable_package(tmp_path / "embed")
    record = _record_for(package)
    (package / "render-critic.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValidationError, match="render-critic.json"):
        embed_recorded_review(package, record, edition_id="issue-001", language="en")


def test_a_refused_recording_leaves_no_review_record_behind(tmp_path: Path):
    """The record is written only after every language package has accepted
    the embed: a refusal must not leave an approved render.yaml beside a
    package that exposes nothing."""
    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    built = magazine.build("issue-001")
    built.reader_pdf.write_bytes(built.reader_pdf.read_bytes() + b"\ntampered")

    with pytest.raises(ValidationError, match="no longer matches its own inventory"):
        magazine.record_render_review(
            "issue-001", reviewer="Independent critic", result="approved"
        )

    assert not (tmp_path / "editions" / "issue-001" / "reviews" / "render.yaml").exists()
    report = json.loads((built.output_dir / "render-critic.json").read_text())
    assert report["visual_review"]["status"] == "required_before_release"


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
