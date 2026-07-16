from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from .errors import ValidationError

if TYPE_CHECKING:
    from .records import SourceRecord


_FORBIDDEN_NAMES = {
    "cookies",
    "cookies-journal",
    "history",
    "login data",
    "local state",
    "preferences",
    "web data",
}


def archive_snapshot(
    record: SourceRecord,
    sources_dir: Path,
    snapshot: Path,
    *,
    method: str,
    captured_at: str | None = None,
) -> SourceRecord:
    """Copy a raw source artifact bundle into immutable, content-addressed storage."""

    snapshot = snapshot.expanduser().resolve()
    files = _snapshot_files(snapshot)
    artifacts = [_artifact(snapshot, path) for path in files]
    bundle_sha256 = _bundle_hash(artifacts)
    relative_manifest = f"raw/{bundle_sha256}/manifest.json"
    source_dir = sources_dir / record.id
    capture_dir = source_dir / "raw" / bundle_sha256
    manifest = {
        "schema_version": 1,
        "source_id": record.id,
        "submitted_url": record.url,
        "canonical_url": record.canonical_url,
        "captured_at": captured_at or record.captured_at,
        "method": method.strip() or "unspecified",
        "bundle_sha256": bundle_sha256,
        "artifact_count": len(artifacts),
        "byte_count": sum(int(item["bytes"]) for item in artifacts),
        "artifacts": artifacts,
    }

    if capture_dir.exists():
        manifest = _verify_manifest(record, source_dir, relative_manifest, bundle_sha256)
    else:
        raw_dir = source_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".capture-", dir=raw_dir) as temporary:
            staging = Path(temporary)
            artifact_dir = staging / "artifacts"
            for source, item in zip(files, artifacts, strict=True):
                destination = artifact_dir / str(item["path"])
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(staging, capture_dir)

    descriptor = {
        "id": bundle_sha256,
        "path": relative_manifest,
        "method": manifest["method"],
        "captured_at": manifest["captured_at"],
        "artifact_count": manifest["artifact_count"],
        "byte_count": manifest["byte_count"],
    }
    captures = {str(item.get("id")): item for item in record.raw_captures}
    captures[bundle_sha256] = descriptor
    return replace(
        record,
        raw_captures=sorted(captures.values(), key=lambda item: (str(item.get("captured_at", "")), str(item["id"]))),
    )


def verify_snapshots(record: SourceRecord, sources_dir: Path) -> None:
    if not record.raw_captures:
        raise ValidationError(
            f"Source {record.id} has no committed raw capture; ingest it again with --snapshot"
        )
    source_dir = sources_dir / record.id
    seen: set[str] = set()
    for descriptor in record.raw_captures:
        bundle_sha256 = str(descriptor.get("id", ""))
        path = str(descriptor.get("path", ""))
        if not bundle_sha256 or bundle_sha256 in seen:
            raise ValidationError(f"Source {record.id} has an invalid raw capture descriptor")
        seen.add(bundle_sha256)
        expected = f"raw/{bundle_sha256}/manifest.json"
        if path != expected:
            raise ValidationError(f"Source {record.id} raw capture path must be {expected}")
        _verify_manifest(record, source_dir, path, bundle_sha256)


def _snapshot_files(snapshot: Path) -> list[Path]:
    if not snapshot.exists():
        raise ValidationError(f"Raw snapshot does not exist: {snapshot}")
    if snapshot.is_symlink():
        raise ValidationError(f"Raw snapshot may not be a symlink: {snapshot}")
    if snapshot.is_file():
        files = [snapshot]
    elif snapshot.is_dir():
        files = sorted(path for path in snapshot.rglob("*") if path.is_file())
        links = [path for path in snapshot.rglob("*") if path.is_symlink()]
        if links:
            raise ValidationError(f"Raw snapshot contains a symlink: {links[0]}")
    else:
        raise ValidationError(f"Raw snapshot must be a file or directory: {snapshot}")
    if not files:
        raise ValidationError(f"Raw snapshot is empty: {snapshot}")
    for path in files:
        if path.name.casefold() in _FORBIDDEN_NAMES:
            raise ValidationError(f"Refusing browser-session file in raw snapshot: {path.name}")
    return files


def _artifact(root: Path, path: Path) -> dict[str, Any]:
    relative = path.name if root.is_file() else path.relative_to(root).as_posix()
    return {
        "path": relative,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def _bundle_hash(artifacts: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in artifacts:
        digest.update(str(item["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item["sha256"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(item["bytes"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_manifest(
    record: SourceRecord,
    source_dir: Path,
    relative_manifest: str,
    expected_bundle_sha256: str,
) -> dict[str, Any]:
    manifest_path = source_dir / relative_manifest
    if not manifest_path.is_file():
        raise ValidationError(f"Missing raw capture manifest for {record.id}: {relative_manifest}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot read raw capture manifest {manifest_path}: {exc}") from exc
    if manifest.get("source_id") != record.id:
        raise ValidationError(f"Raw capture manifest belongs to another source: {manifest_path}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValidationError(f"Raw capture manifest has no artifacts: {manifest_path}")
    verified: list[dict[str, Any]] = []
    for item in artifacts:
        relative = PurePosixPath(str(item.get("path", "")))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ValidationError(f"Unsafe raw artifact path in {manifest_path}: {relative}")
        artifact_path = manifest_path.parent / "artifacts" / Path(*relative.parts)
        if not artifact_path.is_file():
            raise ValidationError(f"Missing raw artifact for {record.id}: {relative}")
        actual = _artifact(manifest_path.parent / "artifacts", artifact_path)
        if actual != item:
            raise ValidationError(f"Raw artifact changed after capture: {artifact_path}")
        verified.append(actual)
    actual_bundle_sha256 = _bundle_hash(verified)
    if actual_bundle_sha256 != expected_bundle_sha256 or manifest.get("bundle_sha256") != expected_bundle_sha256:
        raise ValidationError(f"Raw capture bundle hash mismatch: {manifest_path}")
    if manifest.get("artifact_count") != len(verified):
        raise ValidationError(f"Raw capture artifact count mismatch: {manifest_path}")
    if manifest.get("byte_count") != sum(int(item["bytes"]) for item in verified):
        raise ValidationError(f"Raw capture byte count mismatch: {manifest_path}")
    return manifest
