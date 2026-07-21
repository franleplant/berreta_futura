from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkstemp
from typing import Any

from .errors import ValidationError
from .io import dump_yaml, load_structured


REVIEW_RESULTS = {"approved", "changes_required"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    languages: dict[str, dict[str, Any]] = {}
    for language, package in language_packages.items():
        reader = package / "reader.pdf"
        booklet = package / "home" / "booklet-a4.pdf"
        report_path = package / "render-critic.json"
        if not reader.is_file() or not booklet.is_file() or not report_path.is_file():
            raise ValidationError(
                f"Render review requires a completed {language} build; run `mag build {edition_id}` first"
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("result") != "pass":
            raise ValidationError(f"Cannot record review: {language} render critic has not passed")
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
        "findings": clean_findings,
        "notes": notes.strip(),
        "languages": languages,
    }
    return record


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
        report = json.loads(path.read_text(encoding="utf-8"))
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
