from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkstemp
from typing import Any, Iterable

from .errors import ValidationError
from .io import dump_yaml, load_structured


REVIEW_RESULTS = {"approved", "changes_required"}
IDENTITY_REVIEW_RASTER_DIRS = (
    "reader-pages",
    "booklet-sides",
    "cover-booklet-sides",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def projection_sha256(projection: Any) -> str:
    """One hash over a *projection* of authored data rather than over a file.

    Two review kinds bind a projection instead of bytes: the learning record
    hashes the editor-authored furniture, and the edition record hashes the
    manifest with its filesystem identity removed.  What they need in common is
    not the projection -- those differ, deliberately and by kind -- but the
    canonicalization, so it lives here beside :func:`sha256` with the rest of
    the mechanics every kind shares.

    ``sort_keys=True`` makes the hash independent of mapping order,
    ``separators`` without spaces independent of the serializer's whitespace
    habits, and ``ensure_ascii=False`` keeps a Spanish deck hashing as the
    characters an editor typed rather than as escape sequences.  Values YAML
    parses into something JSON cannot hold -- an unquoted date, most often --
    canonicalize to their string form, which is what a projection over a
    hand-edited manifest has to survive.
    """

    encoded = json.dumps(
        projection,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Any:
    """Parse a package artifact, refusing corruption as a validation error.

    A hand-damaged ``render-critic.json`` used to escape as a raw
    ``json.JSONDecodeError`` traceback the CLI could not catch; every seam
    that reads a JSON artifact goes through here so the refusal names the
    file and stays inside the module's own error type.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"{path} is not valid JSON ({error}); run `mag build` to regenerate it"
        ) from error


def load_render_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = load_structured(path)
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("Render review schema_version must be 1")
    if data.get("edition_id") != edition_id:
        errors.append(
            f"Render review edition_id {data.get('edition_id')!r} does not match {edition_id!r}"
        )
    if str(data.get("result") or "") not in REVIEW_RESULTS:
        errors.append("Render review result must be approved or changes_required")
    for key in ("reviewer", "reviewed_at"):
        if not str(data.get(key) or "").strip():
            errors.append(f"Render review requires {key}")
    # ``engine`` / ``design_direction`` were added after edition 002's record
    # was written, so their absence is legal; an empty value is not.
    for key in ("engine", "design_direction"):
        if key in data and not str(data.get(key) or "").strip():
            errors.append(f"Render review {key} must be a non-empty string when present")
    languages = data.get("languages")
    if not isinstance(languages, dict) or not languages:
        errors.append("Render review requires a languages mapping")
        languages = {}
    for language, row in languages.items():
        if not isinstance(row, dict):
            errors.append(f"Render review language {language} must be a mapping")
            continue
        for key in ("reader_sha256", "booklet_sha256"):
            value = str(row.get(key) or "")
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                errors.append(f"Render review language {language} has invalid {key}")
    findings = data.get("findings", [])
    if not isinstance(findings, list) or any(not str(item).strip() for item in findings):
        errors.append("Render review findings must be a list of non-empty strings")
    if data.get("result") == "changes_required" and not findings:
        errors.append("A changes_required render review needs at least one finding")
    if errors:
        raise ValidationError(errors)
    return dict(data)


def visual_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    language: str,
    reader_pdf: Path,
    booklet_pdf: Path,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "reader_sha256": sha256(reader_pdf),
        "booklet_sha256": sha256(booklet_pdf),
    }
    if review is None:
        return base
    row = review.get("languages", {}).get(language)
    shared = {
        "reviewer": review.get("reviewer"),
        "reviewed_at": review.get("reviewed_at"),
        "result": review.get("result"),
        "findings": list(review.get("findings", [])),
    }
    base.update(shared)
    if review.get("edition_id") != edition_id or not isinstance(row, dict):
        base["status"] = "stale"
        return base
    if (
        row.get("reader_sha256") != base["reader_sha256"]
        or row.get("booklet_sha256") != base["booklet_sha256"]
    ):
        base["status"] = "stale"
    elif review.get("result") == "approved":
        base["status"] = "approved"
    else:
        base["status"] = "changes_required"
    return base


def create_render_review(
    *,
    edition_id: str,
    reviewer: str,
    result: str,
    language_packages: dict[str, Path],
    engine: str,
    design_direction: str,
    findings: list[str] | tuple[str, ...] = (),
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    reviewer = reviewer.strip()
    result = result.strip()
    clean_findings = [str(item).strip() for item in findings if str(item).strip()]
    if not reviewer:
        raise ValidationError("Render review requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError("Render review result must be approved or changes_required")
    if result == "changes_required" and not clean_findings:
        raise ValidationError("A changes_required render review needs at least one finding")
    if not engine.strip() or not design_direction.strip():
        raise ValidationError("Render review requires the engine and design direction under review")
    languages: dict[str, dict[str, Any]] = {}
    for language, package in language_packages.items():
        reader = package / "reader.pdf"
        booklet = package / "home" / "booklet-a4.pdf"
        report_path = package / "render-critic.json"
        manifest_path = package / "edition-manifest.json"
        if (
            not reader.is_file()
            or not booklet.is_file()
            or not report_path.is_file()
            or not manifest_path.is_file()
        ):
            raise ValidationError(
                f"Render review requires a completed {language} build; run `mag build {edition_id}` first"
            )
        report = _read_json(report_path)
        if report.get("result") != "pass":
            raise ValidationError(f"Cannot record review: {language} render critic has not passed")
        # The built manifest is the record of which renderer set the PDFs under
        # review; a review recorded against another engine's output would bind
        # the decision to pages the named engine never produced.
        manifest = _read_json(manifest_path)
        built_direction = manifest.get("layout", {}).get("design_direction")
        if built_direction != design_direction:
            raise ValidationError(
                f"Cannot record review: the {language} package was rendered as "
                f"{built_direction!r}, not {design_direction!r} ({engine}); rebuild with "
                "the reviewed engine or record with the matching --engine"
            )
        languages[language] = {
            "reader_sha256": sha256(reader),
            "booklet_sha256": sha256(booklet),
            "page_count": int(report.get("page_count", 0)),
            "machine_result": "pass",
        }
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    record = {
        "schema_version": 1,
        "edition_id": edition_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "result": result,
        "engine": engine.strip(),
        "design_direction": design_direction.strip(),
        "findings": clean_findings,
        "notes": notes.strip(),
        "languages": languages,
    }
    return record


def rebind_equivalent_render_review(
    record: dict[str, Any],
    *,
    baseline_edition_id: str,
    edition_id: str,
    baseline_packages: dict[str, Path],
    candidate_packages: dict[str, Path],
    engine: str,
    design_direction: str,
) -> dict[str, Any]:
    """Carry a visual approval across an identity-only PDF rebuild.

    A stable edition id can change PDF metadata and therefore PDF hashes
    without moving any printed mark. The approval may follow only when every
    reviewed baseline package is still current and every final reader and
    imposed-booklet raster matches it byte for byte.
    """

    errors: list[str] = []
    if record.get("result") != "approved":
        errors.append("The existing render decision is not approved")
    expected_languages = set(record.get("languages", {}))
    if set(baseline_packages) != expected_languages:
        errors.append("Baseline language packages do not match the render review")
    if set(candidate_packages) != expected_languages:
        errors.append("Candidate language packages do not match the render review")

    evidence_counts: dict[str, int] = {}
    for language in sorted(expected_languages):
        baseline = baseline_packages.get(language)
        candidate = candidate_packages.get(language)
        if baseline is None or candidate is None:
            continue
        required_pdfs = (
            baseline / "reader.pdf",
            baseline / "home" / "booklet-a4.pdf",
        )
        missing = [str(path) for path in required_pdfs if not path.is_file()]
        if missing:
            errors.append(
                f"{language}: baseline review package is incomplete "
                f"({', '.join(missing)})"
            )
            continue
        status = visual_review_status(
            record,
            edition_id=edition_id,
            language=language,
            reader_pdf=baseline / "reader.pdf",
            booklet_pdf=baseline / "home" / "booklet-a4.pdf",
        )
        if status["status"] != "approved":
            errors.append(
                f"{language}: the baseline PDFs are not the approved review bytes"
            )
            continue
        baseline_inventory = _render_raster_inventory(baseline)
        candidate_inventory = _render_raster_inventory(candidate)
        if not baseline_inventory or not candidate_inventory:
            errors.append(f"{language}: render review page rasters are missing")
            continue
        if set(baseline_inventory) != set(candidate_inventory):
            errors.append(
                f"{language}: baseline and candidate raster inventories differ"
            )
            continue
        changed = [
            path
            for path in baseline_inventory
            if baseline_inventory[path] != candidate_inventory[path]
        ]
        if changed:
            errors.append(
                f"{language}: final pages differ from the approved edition "
                f"({changed[0]})"
            )
            continue
        evidence_counts[language] = len(baseline_inventory)
    if errors:
        raise ValidationError(
            [
                "Cannot carry the render approval across the stable-id transition.",
                *errors,
            ]
        )

    rebound = create_render_review(
        edition_id=edition_id,
        reviewer=str(record.get("reviewer") or ""),
        result="approved",
        language_packages=candidate_packages,
        engine=engine,
        design_direction=design_direction,
        findings=tuple(record.get("findings", [])),
        notes=str(record.get("notes") or ""),
        reviewed_at=str(record.get("reviewed_at") or ""),
    )
    rebound["identity_rebind"] = {
        "from_edition_id": baseline_edition_id,
        "method": "exact_reader_and_booklet_raster_match",
        "raster_counts": evidence_counts,
    }
    return rebound


def _render_raster_inventory(package: Path) -> dict[str, str]:
    review_root = package / "render-review"
    inventory: dict[str, str] = {}
    for directory_name in IDENTITY_REVIEW_RASTER_DIRS:
        directory = review_root / directory_name
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.png")):
            inventory[path.relative_to(review_root).as_posix()] = sha256(path)
    return inventory


def check_recorded_review_embeddable(
    package: Path, record: dict[str, Any], *, edition_id: str, language: str
) -> dict[str, Any]:
    """Every refusal :func:`embed_recorded_review` can raise, with no writes.

    Recording embeds the decision into every language package, so a caller
    runs this over all of them *before* writing the review record: a package
    that would refuse the embed then leaves no record behind -- neither an
    approved ``render.yaml`` beside a package exposing nothing, nor earlier
    languages embedded when a later one fails.  Returns the parsed report so
    the embed that follows does not re-read it.
    """

    reader = package / "reader.pdf"
    booklet = package / "home" / "booklet-a4.pdf"
    report_path = package / "render-critic.json"
    checksums_path = package / "SHA256SUMS"
    missing = [
        path.relative_to(package).as_posix()
        for path in (reader, booklet, report_path, checksums_path)
        if not path.is_file()
    ]
    if missing:
        raise ValidationError(
            f"Cannot expose the review in the {language} package: missing "
            f"{', '.join(missing)}; run `mag build {edition_id}` first"
        )
    row = record.get("languages", {}).get(language)
    if (
        not isinstance(row, dict)
        or row.get("reader_sha256") != sha256(reader)
        or row.get("booklet_sha256") != sha256(booklet)
    ):
        raise ValidationError(
            f"The {language} package's PDFs are not the bytes the review record "
            "binds to; rebuild, re-inspect the current PDFs, and record again"
        )
    # The record binds whatever bytes are on disk, so a PDF tampered after the
    # build binds cleanly -- but the package's own inventory still names the
    # build's bytes.  Recording into a package that fails its own SHA256SUMS
    # would seal an approval over a package no verifier can accept.
    listed: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        checksum, separator, name = line.partition("  ")
        if separator:
            listed[name] = checksum
    if "render-critic.json" not in listed:
        raise ValidationError(
            f"SHA256SUMS in {package} does not list render-critic.json; "
            "rebuild the package instead of patching it"
        )
    tampered = [
        path.relative_to(package).as_posix()
        for path in (reader, booklet)
        if listed.get(path.relative_to(package).as_posix()) != sha256(path)
    ]
    if tampered:
        raise ValidationError(
            f"The {language} package no longer matches its own inventory "
            f"({', '.join(tampered)} disagrees with SHA256SUMS); run "
            f"`mag build {edition_id}`"
        )
    report = _read_json(report_path)
    if not isinstance(report.get("visual_review"), dict):
        raise ValidationError(
            f"The {language} render-critic.json carries no visual_review block "
            f"to update; run `mag build {edition_id}` first"
        )
    return report


def embed_recorded_review(
    package: Path, record: dict[str, Any], *, edition_id: str, language: str
) -> Path:
    """Expose a recorded decision in an existing package without re-typesetting.

    Recording used to rebuild every language so the packages would carry the
    decision, but the only package content that changes when a review lands is
    ``render-critic.json``'s ``visual_review`` block -- its status, reviewer,
    timestamp, result, and findings all derive from the record -- plus that
    report's line in ``SHA256SUMS``.  So this rewrites exactly those, in place.
    The contact-sheet and raster path lists inside the block describe artifacts
    the build produced and are left untouched, as is every PDF.

    The determinism guarantee moves with it: instead of rebuilding and proving
    the bytes came out identical, the record must bind to the exact bytes on
    disk, and the package must still vouch for those bytes itself.  Every
    refusal lives in :func:`check_recorded_review_embeddable` so a caller can
    dry-run the whole edition before writing anything.
    """

    report = check_recorded_review_embeddable(
        package, record, edition_id=edition_id, language=language
    )
    report_path = package / "render-critic.json"
    checksums_path = package / "SHA256SUMS"
    reader = package / "reader.pdf"
    booklet = package / "home" / "booklet-a4.pdf"
    # The same computation the render critic composes into a fresh report, so
    # a report updated in place says exactly what a rebuilt one would.
    report["visual_review"].update(
        visual_review_status(
            record,
            edition_id=edition_id,
            language=language,
            reader_pdf=reader,
            booklet_pdf=booklet,
        )
    )
    # Byte-identical serialization to package_release's, so the only diff in
    # the report is the review state itself.
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    refresh_checksum_lines(checksums_path, package, [report_path])
    return report_path


def refresh_checksum_lines(
    checksums_path: Path, package: Path, updated: Iterable[Path]
) -> None:
    """Re-hash only the named files' lines in an existing ``SHA256SUMS``.

    Every other line is preserved byte for byte: the inventory keeps vouching
    for files this operation never touched.  A file the inventory does not
    list cannot be refreshed -- that is a package from some other shape of
    build, and the caller should rebuild rather than patch it.
    """

    relative = {path.relative_to(package).as_posix(): path for path in updated}
    lines = checksums_path.read_text(encoding="utf-8").splitlines()
    refreshed: list[str] = []
    replaced: set[str] = set()
    for line in lines:
        _, separator, name = line.partition("  ")
        if separator and name in relative:
            refreshed.append(f"{sha256(relative[name])}  {name}")
            replaced.add(name)
        else:
            refreshed.append(line)
    unlisted = sorted(set(relative) - replaced)
    if unlisted:
        raise ValidationError(
            f"SHA256SUMS in {package} does not list {', '.join(unlisted)}; "
            "rebuild the package instead of patching it"
        )
    checksums_path.write_text("\n".join(refreshed) + "\n", encoding="utf-8")


def write_render_review(path: Path, record: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = dump_yaml(record).encode("utf-8")
    descriptor, temporary_name = mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def require_approved_reports(language_packages: dict[str, Path]) -> None:
    errors: list[str] = []
    for language, package in language_packages.items():
        path = package / "render-critic.json"
        if not path.is_file():
            errors.append(f"{language}: render-critic.json is missing")
            continue
        report = _read_json(path)
        status = report.get("visual_review", {}).get("status")
        if status != "approved":
            errors.append(f"{language}: visual review is {status or 'missing'}")
    if errors:
        raise ValidationError(
            [
                "Release requires a current approved render review recorded with `mag review record`.",
                *errors,
            ]
        )
