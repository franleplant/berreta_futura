from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError


def load_structured(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValidationError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"{path} must contain a mapping")
    return data


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def safe_project_path(root: Path, value: str, *, must_exist: bool = True) -> Path:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"Path escapes project root: {value}") from exc
    if must_exist and not candidate.is_file():
        raise ValidationError(f"Referenced file does not exist: {value}")
    return candidate
