from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import TYPE_CHECKING, Any, Mapping

from .errors import ValidationError

if TYPE_CHECKING:
    from .records import SourceRecord


MEDIA_TRIAGE_STATES = {
    "no_media",
    "media_rejected",
    "media_curated",
    "media_blocked",
}
FIGURE_LAYOUTS = {
    "evidence_band",
    "evidence_band_prose",
    "adaptive_band",
    "compact_band",
    "column_plate",
    "landscape_plate",
    "landscape_plate_after",
}
CURATION_CRITERIA = {"important", "useful", "beautiful", "cool"}
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceMediaAsset:
    id: str
    artifact_path: str
    artifact_sha256: str
    mime_type: str
    creator: str
    credit: str
    rights: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "mime_type": self.mime_type,
            "creator": self.creator,
            "credit": self.credit,
            "rights": self.rights,
        }


@dataclass(frozen=True)
class MediaCaptureReview:
    capture_id: str
    status: str
    assets: tuple[SourceMediaAsset, ...]
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "capture_id": self.capture_id,
            "status": self.status,
            "assets": [asset.to_dict() for asset in self.assets],
        }
        if self.note:
            result["note"] = self.note
        return result


@dataclass(frozen=True)
class Figure:
    id: str
    source_id: str
    asset_id: str
    path: Path
    caption: str
    credit: str
    alt_text: str
    anchor: str
    layout: str
    rights_status: str
    bundle_sha256: str
    artifact_sha256: str
    criteria: tuple[str, ...]
    rationale: str
    source_caption_sha256: str | None = None
    source_credit_sha256: str | None = None


def load_media_reviews(
    value: Any,
    *,
    source_id: str,
    raw_capture_ids: set[str],
) -> tuple[MediaCaptureReview, ...]:
    """Load hash-pinned media curation; exhaustive inventories stay derived."""

    if value in (None, []):
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"Source {source_id} media_reviews must be a list")
    errors: list[str] = []
    reviews: list[MediaCaptureReview] = []
    seen_captures: set[str] = set()
    seen_assets: set[str] = set()
    for index, row in enumerate(value):
        label = f"Source {source_id} media review {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        capture_id = str(row.get("capture_id") or "").strip()
        status = str(row.get("status") or "").strip()
        if not capture_id:
            errors.append(f"{label} requires capture_id")
        elif capture_id in seen_captures:
            errors.append(f"Source {source_id} has duplicate media review for {capture_id}")
        seen_captures.add(capture_id)
        if status not in MEDIA_TRIAGE_STATES:
            errors.append(f"{label} has invalid status: {status or '<missing>'}")
        assets_value = row.get("assets")
        if not isinstance(assets_value, list):
            errors.append(f"{label} assets must be a list")
            assets_value = []
        assets: list[SourceMediaAsset] = []
        for asset_index, asset_row in enumerate(assets_value):
            asset_label = f"{label} asset {asset_index + 1}"
            asset = _load_source_asset(asset_row, asset_label, errors)
            if not asset:
                continue
            if asset.id in seen_assets:
                errors.append(f"Source {source_id} has duplicate media asset id: {asset.id}")
            seen_assets.add(asset.id)
            assets.append(asset)
        note = str(row.get("note") or "").strip()
        if status in {"no_media", "media_rejected"} and assets:
            errors.append(f"{label} with status {status} must have no selected assets")
        if status in {"media_curated", "media_blocked"} and not assets:
            errors.append(f"{label} with status {status} requires selected assets")
        if status == "media_rejected" and not note:
            errors.append(f"{label} with status media_rejected requires a note")
        reviews.append(
            MediaCaptureReview(
                capture_id,
                status,
                tuple(assets),
                note,
            )
        )
    if seen_captures != raw_capture_ids:
        # Edition validation owns completeness for legacy or externally written
        # records; normal capture runs automatic curation before persisting.
        extra = sorted(seen_captures - raw_capture_ids)
        if extra:
            errors.append(
                f"Source {source_id} media_reviews reference unknown captures: {', '.join(extra)}"
            )
    if errors:
        raise ValidationError(errors)
    return tuple(reviews)


def resolve_figures(
    root: Path,
    *,
    article_id: str,
    article_source_ids: tuple[str, ...],
    manuscript: Path,
    rows: Any,
    records: Mapping[str, "SourceRecord"] | None,
    allow_unanchored: bool = False,
) -> tuple[Figure, ...]:
    """Resolve explicit edition selections against committed source inventories.

    ``allow_unanchored`` keeps a figure whose anchor names a heading the current
    manuscript does not carry. It exists only for the renderer adapter while it
    measures a supplied immutable render manifest and reports a stranded anchor
    by name, with the headings the draft actually has. Refusing to load the
    edition at all would make that renderer diagnostic unavailable. Every other
    caller leaves it false, so a stranded anchor is still a validation error
    everywhere a reader could reach the page.
    """

    if rows in (None, []):
        return ()
    if not isinstance(rows, list):
        raise ValidationError(f"Article {article_id} figures must be a list")
    if len(rows) > 3:
        raise ValidationError(f"Article {article_id} selects {len(rows)} figures; maximum is 3")
    errors: list[str] = []
    figures: list[Figure] = []
    seen: set[str] = set()
    headings = _semantic_headings(manuscript)
    for index, row in enumerate(rows):
        label = f"Article {article_id} figure {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        figure_id = str(row.get("id") or "").strip()
        source_id = str(row.get("source_id") or "").strip()
        asset_id = str(row.get("asset_id") or "").strip()
        decision = str(row.get("decision") or "").strip()
        caption = str(row.get("caption") or "").strip()
        alt_text = str(row.get("alt_text") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        layout = str(row.get("layout") or "").strip()
        rationale = str(row.get("rationale") or "").strip()
        criteria_value = row.get("criteria")
        criteria = tuple(str(item).strip() for item in criteria_value) if isinstance(criteria_value, list) else ()
        missing = [
            name
            for name, value in (
                ("id", figure_id),
                ("source_id", source_id),
                ("asset_id", asset_id),
                ("caption", caption),
                ("alt_text", alt_text),
                ("anchor", anchor),
                ("layout", layout),
                ("rationale", rationale),
            )
            if not value
        ]
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
        if figure_id in seen:
            errors.append(f"Article {article_id} has duplicate figure id: {figure_id}")
        seen.add(figure_id)
        if decision != "include":
            errors.append(f"{label} decision must be include; omit rejected assets")
        if source_id not in article_source_ids:
            errors.append(f"{label} source_id must be one of the article source_ids")
        if not criteria or any(item not in CURATION_CRITERIA for item in criteria):
            errors.append(
                f"{label} criteria must be a non-empty list drawn from "
                f"{', '.join(sorted(CURATION_CRITERIA))}"
            )
        if layout not in FIGURE_LAYOUTS:
            errors.append(f"{label} has invalid layout: {layout or '<missing>'}")
        if anchor != "__opener__" and anchor not in headings and not allow_unanchored:
            errors.append(f"{label} anchor does not match an article heading: {anchor!r}")
        resolved = _resolve_asset(root, source_id, asset_id, records, label, errors)
        if not resolved:
            continue
        review, asset, path = resolved
        if review.status != "media_curated":
            errors.append(
                f"{label} selects asset {asset_id} from capture status {review.status}"
            )
        figures.append(
            Figure(
                figure_id,
                source_id,
                asset_id,
                path,
                caption,
                asset.credit,
                alt_text,
                anchor,
                layout,
                str(asset.rights.get("status") or "unknown"),
                review.capture_id,
                asset.artifact_sha256,
                criteria,
                rationale,
            )
        )
    if errors:
        raise ValidationError(errors)
    return tuple(figures)


def localize_figures(
    base: tuple[Figure, ...],
    rows: Any,
    *,
    article_id: str,
    manuscript: Path,
    language: str,
) -> tuple[Figure, ...]:
    if not base:
        if rows not in (None, []):
            raise ValidationError(
                f"Translation {language!r} article {article_id} has figures absent from English"
            )
        return ()
    if not isinstance(rows, list):
        raise ValidationError(
            f"Translation {language!r} article {article_id} figures must be a list"
        )
    errors: list[str] = []
    by_id = {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }
    expected_ids = {figure.id for figure in base}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        if missing:
            errors.append(
                f"Translation {language!r} article {article_id} is missing figures: {', '.join(missing)}"
            )
        if extra:
            errors.append(
                f"Translation {language!r} article {article_id} has unknown figures: {', '.join(extra)}"
            )
    headings = _semantic_headings(manuscript)
    localized: list[Figure] = []
    for figure in base:
        row = by_id.get(figure.id)
        if not row:
            continue
        caption = str(row.get("caption") or "").strip()
        credit = str(row.get("credit") or "").strip()
        alt_text = str(row.get("alt_text") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        if not caption or not credit or not alt_text or not anchor:
            errors.append(
                f"Translation {language!r} figure {figure.id} requires caption, credit, alt_text, and anchor"
            )
        expected_caption_hash = caption_sha256(figure.id, figure.caption)
        expected_credit_hash = credit_sha256(figure.id, figure.credit)
        # A stale pin is only fixable when the error names the digest the
        # overlay should carry; stating both sides turns re-pinning into a
        # copy after review instead of a private hashing ritual.
        if row.get("source_caption_sha256") != expected_caption_hash:
            errors.append(
                f"Translation {language!r} figure {figure.id} caption pin is stale: "
                f"source_caption_sha256 is {row.get('source_caption_sha256')!r}, but "
                f"the base caption hashes to {expected_caption_hash}"
            )
        if row.get("source_credit_sha256") != expected_credit_hash:
            errors.append(
                f"Translation {language!r} figure {figure.id} credit pin is stale: "
                f"source_credit_sha256 is {row.get('source_credit_sha256')!r}, but "
                f"the base credit hashes to {expected_credit_hash}"
            )
        if anchor != "__opener__" and anchor not in headings:
            errors.append(
                f"Translation {language!r} figure {figure.id} anchor does not match a translated heading"
            )
        localized.append(
            Figure(
                **{
                    **figure.__dict__,
                    "caption": caption,
                    "credit": credit,
                    "alt_text": alt_text,
                    "anchor": anchor,
                    "source_caption_sha256": expected_caption_hash,
                    "source_credit_sha256": expected_credit_hash,
                }
            )
        )
    if errors:
        raise ValidationError(errors)
    return tuple(localized)


def caption_sha256(figure_id: str, caption: str) -> str:
    encoded = json.dumps(
        {"id": figure_id, "caption": caption},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def credit_sha256(figure_id: str, credit: str) -> str:
    encoded = json.dumps(
        {"id": figure_id, "credit": credit},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_source_asset(
    row: Any,
    label: str,
    errors: list[str],
) -> SourceMediaAsset | None:
    if not isinstance(row, dict):
        errors.append(f"{label} must be a mapping")
        return None
    values = {
        key: str(row.get(key) or "").strip()
        for key in ("id", "artifact_path", "artifact_sha256", "mime_type", "creator", "credit")
    }
    missing = [key for key, value in values.items() if not value]
    rights = row.get("rights")
    if not isinstance(rights, dict):
        missing.append("rights")
        rights = {}
    if missing:
        errors.append(f"{label} missing: {', '.join(missing)}")
    relative = PurePosixPath(values["artifact_path"])
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label} has unsafe artifact_path: {values['artifact_path']!r}")
    if not _SHA256.fullmatch(values["artifact_sha256"]):
        errors.append(f"{label} artifact_sha256 must be a lowercase SHA-256 digest")
    if values["mime_type"] not in SUPPORTED_IMAGE_TYPES:
        errors.append(f"{label} has unsupported mime_type: {values['mime_type']!r}")
    required_rights = {"status", "intended_use", "attribution_required", "public_reprint_allowed"}
    missing_rights = sorted(required_rights - set(rights))
    if missing_rights:
        errors.append(f"{label} rights missing: {', '.join(missing_rights)}")
    return SourceMediaAsset(
        values["id"],
        values["artifact_path"],
        values["artifact_sha256"],
        values["mime_type"],
        values["creator"],
        values["credit"],
        dict(rights),
    )


def _resolve_asset(
    root: Path,
    source_id: str,
    asset_id: str,
    records: Mapping[str, "SourceRecord"] | None,
    label: str,
    errors: list[str],
) -> tuple[MediaCaptureReview, SourceMediaAsset, Path] | None:
    if records is None:
        errors.append(f"{label} cannot resolve source media without source records")
        return None
    record = records.get(source_id)
    if not record:
        return None
    matches = [
        (review, asset)
        for review in record.media_reviews
        for asset in review.assets
        if asset.id == asset_id
    ]
    if len(matches) != 1:
        errors.append(f"{label} references unknown media asset: {asset_id}")
        return None
    review, asset = matches[0]
    manifest_path = root / "library" / "sources" / source_id / "raw" / review.capture_id / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} cannot read raw capture manifest: {exc}")
        return None
    artifact_rows = {
        str(item.get("path")): item
        for item in manifest.get("artifacts", [])
        if isinstance(item, dict)
    }
    archived = artifact_rows.get(asset.artifact_path)
    if archived and archived.get("sha256") == asset.artifact_sha256:
        path = manifest_path.parent / "artifacts" / Path(*PurePosixPath(asset.artifact_path).parts)
    elif asset.artifact_path.startswith(f"media/derived/{review.capture_id}/"):
        source_dir = manifest_path.parents[2]
        path = source_dir / Path(*PurePosixPath(asset.artifact_path).parts)
        plan_path = source_dir / "media" / f"{review.capture_id}.curation.json"
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{label} cannot read automatic media curation audit: {exc}")
            return None
        selected = set(plan.get("selected", []))
        matches = [
            row for row in plan.get("candidates", [])
            if isinstance(row, dict) and row.get("id") == asset.id
        ]
        if (
            asset.id not in selected
            or len(matches) != 1
            or matches[0].get("artifact_path") != asset.artifact_path
            or matches[0].get("artifact_sha256") != asset.artifact_sha256
        ):
            errors.append(f"{label} derived asset does not match its automatic curation audit")
            return None
    else:
        errors.append(f"{label} asset does not match its archived bundle or curation audit")
        return None
    if not path.is_file():
        errors.append(f"{label} asset file is missing after capture: {path}")
        return None
    found_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if found_sha256 != asset.artifact_sha256:
        errors.append(
            f"{label} asset file changed after capture: artifact_sha256 is "
            f"{asset.artifact_sha256}, but {path.name} now hashes to {found_sha256}"
        )
        return None
    return review, asset, path


def semantic_headings(path: Path) -> set[str]:
    """Every ``##`` heading a figure anchor may name.

    Public because ``produce`` reconciles anchors against a manuscript it has
    just rewritten, and it has to ask the same question this module answers
    when it validates one.  A second, subtly different heading scanner would
    let produce approve an anchor that validation then refuses.
    """

    return {
        line[3:].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ") and line[3:].strip()
    }


_semantic_headings = semantic_headings
