"""Versioned immutable-file source archive bridge for the XState engine."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .errors import MagazineError, ValidationError


CONTRACT_VERSION = "magazine-source/1"
_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "sourceContractVersion",
    "sourceId",
    "leadArtifactId",
    "artifactRoot",
    "files",
    "metadata",
}
_FILE_KEYS = {"artifactId", "sourcePath", "targetPath"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_relative(value: object) -> Path:
    raw = str(value or "")
    path = Path(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(f"unsafe targetPath: {raw!r}")
    return path


def archive_request(request_path: Path, destination: Path) -> dict[str, Any]:
    request_path = request_path.resolve()
    if not request_path.is_file() or request_path.is_symlink():
        raise ValidationError(f"Source request is not a regular file: {request_path}")
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot read source request: {exc}") from exc
    if not isinstance(request, dict):
        raise ValidationError("Source request must be a JSON object")
    unknown = sorted(set(request) - _TOP_LEVEL_KEYS)
    if unknown:
        raise ValidationError(f"Source request has unknown fields: {', '.join(unknown)}")
    if request.get("schemaVersion") != 1:
        raise ValidationError("Source request schemaVersion must be 1")
    if request.get("sourceContractVersion") != CONTRACT_VERSION:
        raise ValidationError(f"sourceContractVersion must be {CONTRACT_VERSION!r}")
    source_id = str(request.get("sourceId") or "").strip()
    lead_id = str(request.get("leadArtifactId") or "").strip()
    if not source_id or not lead_id:
        raise ValidationError("sourceId and leadArtifactId must be non-empty")
    artifact_root = Path(str(request.get("artifactRoot") or ""))
    destination = Path(destination)
    if not artifact_root.is_absolute() or not destination.is_absolute():
        raise ValidationError("artifactRoot and destination must be absolute")
    if artifact_root.is_symlink() or destination.is_symlink():
        raise ValidationError("artifactRoot and destination must not be symlinks")
    artifact_root = artifact_root.resolve()
    destination = destination.resolve()
    if not artifact_root.is_dir():
        raise ValidationError("artifactRoot must be a directory")
    if destination.exists() and any(destination.iterdir()):
        raise ValidationError("destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    rows = request.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValidationError("files must be a non-empty list")
    result_files: list[dict[str, str]] = []
    artifact_ids: list[str] = [lead_id]
    targets: set[Path] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValidationError(f"files[{index}] must be an object")
        unknown = sorted(set(row) - _FILE_KEYS)
        if unknown:
            raise ValidationError(f"files[{index}] has unknown fields: {', '.join(unknown)}")
        artifact_id = str(row.get("artifactId") or "").strip()
        source = Path(str(row.get("sourcePath") or ""))
        target = _safe_relative(row.get("targetPath"))
        if not artifact_id or not source.is_absolute() or source.is_symlink():
            raise ValidationError(f"files[{index}] has an invalid artifact or source path")
        source = source.resolve()
        if not _inside(source, artifact_root) or not source.is_file():
            raise ValidationError(f"files[{index}] source must be beneath artifactRoot")
        if target in targets:
            raise ValidationError(f"duplicate targetPath: {target.as_posix()}")
        targets.add(target)
        output = destination / target
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
        artifact_ids.append(artifact_id)
        result_files.append({"path": target.as_posix(), "kind": "raw_evidence"})
    return {
        "schemaVersion": 1,
        "sourceContractVersion": CONTRACT_VERSION,
        "sourceId": source_id,
        "files": result_files,
        "inputArtifactIds": artifact_ids,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: mag-source-adapter <source-request.json> <destination>", file=sys.stderr)
        return 2
    try:
        result = archive_request(Path(args[0]), Path(args[1]))
    except (MagazineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
