from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .errors import ValidationError
from .io import dump_yaml, load_structured

_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}

ARTICLE_FILENAME = "article.md"


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValidationError(f"Expected an http(s) URL, got: {url}")
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING and not key.lower().startswith("utm_")
    ]
    host = parts.hostname.lower() if parts.hostname else ""
    if parts.port and not (
        (parts.scheme == "http" and parts.port == 80)
        or (parts.scheme == "https" and parts.port == 443)
    ):
        host = f"{host}:{parts.port}"
    path = re.sub(r"/{2,}", "/", parts.path) or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(sorted(query)), ""))


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:48] or "source"


def source_id(title: str, canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.encode()).hexdigest()[:8]
    return f"{_slug(title)}-{digest}"


@dataclass(frozen=True)
class SourceRecord:
    id: str
    url: str
    title: str
    captured_at: str
    author: str | None = None
    published_at: str | None = None
    tags: list[str] = field(default_factory=list)
    synopsis: str = ""
    notes: str = ""

    @classmethod
    def create(
        cls,
        url: str,
        *,
        title: str | None = None,
        author: str | None = None,
        published_at: str | None = None,
        captured_at: str | None = None,
        tags: list[str] | None = None,
        synopsis: str = "",
        notes: str = "",
    ) -> "SourceRecord":
        canonical = canonicalize_url(url)
        resolved_title = (title or canonical).strip()
        captured = captured_at or datetime.now(timezone.utc).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
        return cls(
            id=source_id(resolved_title, canonical),
            url=canonical,
            title=resolved_title,
            captured_at=captured,
            author=author.strip() if author else None,
            published_at=published_at,
            tags=sorted({tag.strip().lower() for tag in tags or [] if tag.strip()}),
            synopsis=synopsis.strip(),
            notes=notes.strip(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRecord":
        data = dict(data)

        data["url"] = data.get("url") or data.get("canonical_url") or data.get("submitted_url")
        data["published_at"] = data.get("published_at") or data.get("publication_date")
        for key in ("captured_at", "published_at"):
            if isinstance(data.get(key), (date, datetime)):
                data[key] = data[key].isoformat()
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        data.setdefault("tags", metadata.get("tags", []))
        data.setdefault("synopsis", metadata.get("synopsis", ""))
        required = ["id", "url", "title", "captured_at"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValidationError(f"Source record missing: {', '.join(missing)}")
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in known})

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "captured_at": self.captured_at,
            "published_at": self.published_at,
            "tags": self.tags,
            "synopsis": self.synopsis,
        }
        if self.notes:
            result["notes"] = self.notes
        return result

    def write(self, sources_dir: Path) -> Path:
        directory = sources_dir / self.id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "record.yaml"
        path.write_text(dump_yaml(self.to_dict()), encoding="utf-8")
        return path


def load_records(sources_dir: Path) -> list[SourceRecord]:
    if not sources_dir.exists():
        return []
    records = [
        SourceRecord.from_dict(load_structured(path)) for path in sources_dir.glob("*/record.y*ml")
    ]
    seen: dict[str, str] = {}
    for record in records:
        if record.url in seen:
            raise ValidationError(f"Duplicate URL in {seen[record.url]} and {record.id}")
        seen[record.url] = record.id
    return sorted(records, key=lambda item: (item.captured_at, item.id), reverse=True)
