from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .io import load_structured, safe_project_path


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    author: str
    source_ids: tuple[str, ...]
    manuscript: Path
    fidelity: Path
    content_mode: str


@dataclass(frozen=True)
class Section:
    kind: str
    title: str
    path: Path


@dataclass(frozen=True)
class Edition:
    id: str
    issue_number: str
    title: str
    publication_date: str
    editorial: Path | None
    articles: tuple[Article, ...]
    sections: tuple[Section, ...]
    cover: dict[str, Any]
    cover_art: Path | None
    raw: dict[str, Any]


def load_edition(root: Path, edition_id: str, known_sources: set[str]) -> Edition:
    manifest_path = root / "editions" / edition_id / "edition.yaml"
    if not manifest_path.is_file():
        raise ValidationError(f"Edition manifest not found: {manifest_path}")
    data = load_structured(manifest_path)
    errors: list[str] = []
    for key in ("id", "issue_number", "title", "publication_date"):
        if data.get(key) in (None, "", []):
            errors.append(f"Edition missing required field: {key}")
    if data.get("id") != edition_id:
        errors.append(f"Edition id {data.get('id')!r} does not match directory {edition_id!r}")
    declared_sources = data.get("sources", [])
    if declared_sources and not isinstance(declared_sources, list):
        errors.append("Edition sources must be a list")
    elif isinstance(declared_sources, list):
        unknown_declared = sorted(set(declared_sources) - known_sources)
        if unknown_declared:
            errors.append(f"Edition references unknown sources: {', '.join(unknown_declared)}")
    if not data.get("sections") and (not data.get("editorial") or not data.get("articles")):
        errors.append("Edition requires either sections, or editorial plus articles")
    article_rows = data.get("articles", [])
    if not isinstance(article_rows, list):
        errors.append("Edition articles must be a list")
        article_rows = []
    ids: set[str] = set()
    articles: list[Article] = []
    for index, row in enumerate(article_rows):
        if not isinstance(row, dict):
            errors.append(f"Article {index + 1} must be a mapping")
            continue
        label = f"Article {row.get('id', index + 1)}"
        missing = [key for key in ("id", "title", "author", "source_ids", "manuscript", "fidelity") if not row.get(key)]
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
            continue
        if row["id"] in ids:
            errors.append(f"Duplicate article id: {row['id']}")
        ids.add(row["id"])
        source_ids = tuple(row["source_ids"])
        unknown = sorted(set(source_ids) - known_sources)
        if unknown:
            errors.append(f"{label} references unknown sources: {', '.join(unknown)}")
        try:
            manuscript = safe_project_path(root, row["manuscript"])
            fidelity = safe_project_path(root, row["fidelity"])
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        content_mode = str(row.get("content_mode", "faithful_edit"))
        if content_mode not in {"faithful_edit", "faithful_synthesis", "selected_extracts", "original_synthesis"}:
            errors.append(f"{label} has invalid content_mode: {content_mode}")
        articles.append(Article(row["id"], row["title"], row["author"], source_ids, manuscript, fidelity, content_mode))
    edition_dir = manifest_path.parent
    try:
        editorial = _edition_path(root, edition_dir, data["editorial"]) if data.get("editorial") else None
    except ValidationError as exc:
        errors.extend(exc.errors)
        editorial = None
    sections: list[Section] = []
    section_rows = data.get("sections", [])
    if section_rows and not isinstance(section_rows, list):
        errors.append("Edition sections must be a list")
        section_rows = []
    for index, row in enumerate(section_rows):
        if not isinstance(row, dict) or not row.get("kind") or not row.get("path"):
            errors.append(f"Section {index + 1} requires kind and path")
            continue
        try:
            path = _edition_path(root, edition_dir, row["path"])
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        sections.append(Section(str(row["kind"]), str(row.get("title") or _section_title(row["kind"])), path))
    cover = dict(data.get("cover") or {})
    cover_art = None
    if cover.get("art_path"):
        try:
            cover_art = _edition_path(root, edition_dir, cover["art_path"])
        except ValidationError as exc:
            errors.extend(exc.errors)
    if errors:
        raise ValidationError(errors)
    return Edition(str(data["id"]), str(data["issue_number"]), str(data["title"]), str(data["publication_date"]), editorial, tuple(articles), tuple(sections), cover, cover_art, data)


def _edition_path(root: Path, edition_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.parts and path.parts[0] == "editions":
        return safe_project_path(root, value)
    relative = (edition_dir / path).resolve()
    try:
        relative.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"Path escapes project root: {value}") from exc
    if not relative.is_file():
        raise ValidationError(f"Referenced file does not exist: {relative.relative_to(root)}")
    return relative


def _section_title(kind: str) -> str:
    return {
        "original_editorial": "Editorial",
        "source_introduction": "Introduction",
        "original_synthesis": "Reading Map",
        "source_record": "Source Record",
        "production_note": "Production Note",
        "colophon": "Colophon",
    }.get(str(kind), str(kind).replace("_", " ").title())
