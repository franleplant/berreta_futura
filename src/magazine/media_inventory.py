from __future__ import annotations

import json
import os
import posixpath
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

from .errors import ValidationError


MEDIA_INVENTORY_SCHEMA_VERSION = 1

_DECLARED_MEDIA_ROLES = {"decorative", "diagram", "duplicate", "figure", "photo", "title_card"}
_DECLARED_MEDIA_TEXT_FIELDS = ("alt_text", "description", "heading", "title")

_MIME_BY_FORMAT = {
    "AVIF": "image/avif",
    "BMP": "image/bmp",
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "TIFF": "image/tiff",
    "WEBP": "image/webp",
}


def media_inventory_path(source_dir: Path, bundle_sha256: str) -> Path:
    """Return the generated inventory path without placing it in the raw bundle."""

    return source_dir / "media" / f"{bundle_sha256}.json"


def build_media_inventory(
    *,
    source_id: str,
    bundle_sha256: str,
    artifact_root: Path,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Discover raster images in an already verified capture artifact list."""

    images: list[dict[str, Any]] = []
    for artifact in sorted(artifacts, key=lambda item: str(item["path"])):
        path = artifact_root / Path(str(artifact["path"]))
        image = _inspect_image(path)
        if image is None:
            continue
        images.append(
            {
                "path": str(artifact["path"]),
                "sha256": str(artifact["sha256"]),
                "bytes": int(artifact["bytes"]),
                **image,
            }
        )
    references = _html_image_references(artifact_root, artifacts)
    missing = [item for item in references["local"] if not item["present"]]
    unresolved = references["unresolved"]
    duplicate_groups = [
        {"sha256": sha256, "paths": sorted(paths)}
        for sha256, paths in _paths_by_sha256(images).items()
        if len(paths) > 1
    ]
    return {
        "schema_version": MEDIA_INVENTORY_SCHEMA_VERSION,
        "source_id": source_id,
        "bundle_sha256": bundle_sha256,
        "artifact_count": len(artifacts),
        "image_count": len(images),
        "images": images,
        "duplicate_groups": duplicate_groups,
        "referenced_image_count": len(
            {item["resolved_path"] for item in references["local"]}
        ) + len({item["reference"] for item in unresolved}),
        "local_references": references["local"],
        "missing_references": missing,
        "unresolved_acquisition_references": unresolved,
        "complete": not missing and not unresolved,
    }


def write_media_inventory(path: Path, inventory: dict[str, Any]) -> Path:
    """Atomically write canonical JSON; generated indexes may be safely regenerated."""

    payload = _encoded(inventory)
    if path.is_file() and path.read_bytes() == payload:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.stem}-",
        suffix=".json",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    os.replace(temporary, path)
    return path


def verify_media_inventory(path: Path, expected: dict[str, Any]) -> None:
    if not path.is_file():
        raise ValidationError(f"Missing generated media inventory: {path}")
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot read generated media inventory {path}: {exc}") from exc
    if actual != expected:
        raise ValidationError(f"Generated media inventory is stale or changed: {path}")
    ensure_local_media_complete(actual, path=path)


def ensure_local_media_complete(
    inventory: dict[str, Any],
    *,
    path: Path | None = None,
) -> None:
    """Reject a snapshot that refers to a local image it did not archive."""

    missing = inventory.get("missing_references", [])
    if missing:
        location = f" in {path}" if path else ""
        references = ", ".join(
            f"{item['document_path']} -> {item['resolved_path']}" for item in missing
        )
        raise ValidationError(
            f"Captured HTML has missing local image references{location}: {references}"
        )


def _inspect_image(path: Path) -> dict[str, Any] | None:
    try:
        with Image.open(path) as image:
            image_format = str(image.format or "").upper()
            mime_type = _MIME_BY_FORMAT.get(image_format)
            if mime_type is None:
                return None
            width, height = image.size
            color_mode = str(image.mode)
            icc_profile_present = bool(image.info.get("icc_profile"))
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            frame_count = int(getattr(image, "n_frames", 1))
            animated = bool(getattr(image, "is_animated", False))
            image.verify()
    except UnidentifiedImageError:
        return None
    except (OSError, SyntaxError, ValueError) as exc:
        raise ValidationError(f"Cannot inspect captured image {path}: {exc}") from exc
    if width < 1 or height < 1:
        raise ValidationError(f"Captured image has invalid dimensions: {path}")
    return {
        "mime_type": mime_type,
        "pixel_width": int(width),
        "pixel_height": int(height),
        "aspect_ratio": round(width / height, 6),
        "color_mode": color_mode,
        "icc_profile_present": icc_profile_present,
        "has_alpha": has_alpha,
        "frame_count": frame_count,
        "animated": animated,
    }


def _paths_by_sha256(images: list[dict[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for image in images:
        result.setdefault(str(image["sha256"]), []).append(str(image["path"]))
    return dict(sorted(result.items()))


class _ImageReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.casefold(): value for name, value in attrs if value is not None}
        if tag.casefold() == "img" and values.get("src"):
            self.references.append(("src", str(values["src"])))
        if values.get("srcset"):
            for reference in _srcset_urls(str(values["srcset"])):
                self.references.append(("srcset", reference))


def _html_image_references(
    artifact_root: Path,
    artifacts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    artifact_paths = {str(item["path"]) for item in artifacts}
    local: dict[tuple[str, str, str], dict[str, Any]] = {}
    unresolved: dict[tuple[str, str, str], dict[str, Any]] = {}
    for artifact in sorted(artifacts, key=lambda item: str(item["path"])):
        document_path = str(artifact["path"])
        if PurePosixPath(document_path).name.casefold() == "media-manifest.json":
            _add_declared_media_references(
                artifact_root,
                document_path,
                artifact_paths,
                local,
            )
        if PurePosixPath(document_path).suffix.casefold() not in {".html", ".htm"}:
            continue
        parser = _ImageReferenceParser()
        try:
            parser.feed(
                (artifact_root / Path(document_path)).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except (OSError, UnicodeError) as exc:
            raise ValidationError(
                f"Cannot inspect captured HTML image references {document_path}: {exc}"
            ) from exc
        for attribute, reference in parser.references:
            classification = _classify_reference(document_path, reference)
            if classification[0] == "local":
                resolved = classification[1]
                key = (document_path, attribute, reference)
                local[key] = {
                    "document_path": document_path,
                    "attribute": attribute,
                    "reference": reference,
                    "resolved_path": resolved,
                    "present": resolved in artifact_paths,
                }
            else:
                key = (document_path, attribute, reference)
                unresolved[key] = {
                    "document_path": document_path,
                    "attribute": attribute,
                    "reference": reference,
                    "kind": classification[1],
                }
    return {
        "local": [local[key] for key in sorted(local)],
        "unresolved": [unresolved[key] for key in sorted(unresolved)],
    }


def _add_declared_media_references(
    artifact_root: Path,
    document_path: str,
    artifact_paths: set[str],
    local: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    try:
        data = json.loads((artifact_root / Path(document_path)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            f"Cannot inspect captured media manifest {document_path}: {exc}"
        ) from exc
    assets = data.get("assets", []) if isinstance(data, dict) else []
    if not isinstance(assets, list):
        raise ValidationError(f"Captured media manifest assets must be a list: {document_path}")
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValidationError(f"Captured media manifest has an invalid asset: {document_path}")
        reference = asset.get("relative_url", asset.get("path"))
        if not isinstance(reference, str) or not reference.strip():
            raise ValidationError(
                f"Captured media manifest asset requires relative_url or path: {document_path}"
            )
        classification = _classify_reference(document_path, reference)
        if classification[0] != "local":
            raise ValidationError(
                f"Captured media manifest asset must be a safe local reference: {reference}"
            )
        resolved = classification[1]
        metadata = _declared_media_metadata(asset, document_path=document_path)
        key = (document_path, "manifest", reference)
        local[key] = {
            "document_path": document_path,
            "attribute": "manifest",
            "reference": reference,
            "resolved_path": resolved,
            "present": resolved in artifact_paths,
            **metadata,
        }


def _declared_media_metadata(asset: dict[str, Any], *, document_path: str) -> dict[str, Any]:
    """Validate optional source context carried by a browser media manifest."""

    result: dict[str, Any] = {}
    source_url = asset.get("source_url")
    if source_url is not None:
        if not isinstance(source_url, str) or urlsplit(source_url).scheme.casefold() not in {"http", "https"}:
            raise ValidationError(
                f"Captured media manifest asset source_url must be HTTP(S): {document_path}"
            )
        result["source_url"] = source_url
    source_position = asset.get("source_position")
    if source_position is not None:
        if isinstance(source_position, bool) or not isinstance(source_position, int) or source_position < 1:
            raise ValidationError(
                f"Captured media manifest asset source_position must be a positive integer: {document_path}"
            )
        result["source_position"] = source_position
    role = asset.get("role")
    if role is not None:
        if not isinstance(role, str) or role not in _DECLARED_MEDIA_ROLES:
            raise ValidationError(
                f"Captured media manifest asset has invalid role {role!r}: {document_path}"
            )
        result["role"] = role
    for field in _DECLARED_MEDIA_TEXT_FIELDS:
        value = asset.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValidationError(
                f"Captured media manifest asset {field} must be text: {document_path}"
            )
        result[field] = value.strip()
    duplicate_of = asset.get("duplicate_of")
    if duplicate_of is not None:
        if not isinstance(duplicate_of, str) or not duplicate_of.strip():
            raise ValidationError(
                f"Captured media manifest asset duplicate_of must be a local path: {document_path}"
            )
        classification = _classify_reference(document_path, duplicate_of)
        if classification[0] != "local":
            raise ValidationError(
                f"Captured media manifest asset duplicate_of must be a local path: {duplicate_of}"
            )
        result["duplicate_of"] = classification[1]
    return result


def _srcset_urls(value: str) -> list[str]:
    # Data URLs may contain commas, so keep them as one unresolved acquisition
    # reference. Ordinary srcset entries are comma-separated URL + descriptor.
    if value.lstrip().casefold().startswith("data:"):
        return [value.strip()]
    return [
        candidate.strip().split()[0]
        for candidate in value.split(",")
        if candidate.strip()
    ]


def _classify_reference(document_path: str, reference: str) -> tuple[str, str]:
    value = reference.strip()
    parsed = urlsplit(value)
    if parsed.scheme.casefold() in {"http", "https"} or parsed.netloc:
        return "unresolved", "remote"
    if parsed.scheme:
        return "unresolved", parsed.scheme.casefold()
    raw_path = unquote(parsed.path).replace("\\", "/")
    if raw_path.startswith("/"):
        candidate = raw_path.lstrip("/")
    else:
        candidate = posixpath.join(posixpath.dirname(document_path), raw_path)
    normalized = posixpath.normpath(candidate)
    if not normalized or normalized == "." or normalized == ".." or normalized.startswith("../"):
        return "unresolved", "unsafe_local"
    return "local", normalized


def _encoded(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
