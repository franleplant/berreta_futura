from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .errors import ValidationError
from .io import dump_yaml, load_structured

_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}


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
    if parts.port and not ((parts.scheme == "http" and parts.port == 80) or (parts.scheme == "https" and parts.port == 443)):
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
    canonical_url: str
    title: str
    captured_at: str
    author: str | None = None
    published_at: str | None = None
    content_mode: str = "faithful_edit"
    tags: list[str] = field(default_factory=list)
    primary_material: list[str] = field(default_factory=list)
    synopsis: str = ""
    notes: str = ""
    schema_version: int = 1
    kind: str = "web"
    status: str = "captured"
    content_hash: str | None = None
    provenance: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    rights: dict[str, Any] = field(default_factory=lambda: {
        "status": "unknown",
        "intended_use": "private_reference",
        "attribution_required": True,
        "public_reprint_allowed": False,
    })

    @classmethod
    def create(cls, url: str, *, title: str | None = None, author: str | None = None,
               published_at: str | None = None, captured_at: str | None = None,
               tags: list[str] | None = None, primary_material: list[str] | None = None,
               synopsis: str = "", notes: str = "") -> "SourceRecord":
        canonical = canonicalize_url(url)
        resolved_title = (title or canonical).strip()
        captured = captured_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return cls(
            id=source_id(resolved_title, canonical), url=url.strip(), canonical_url=canonical,
            title=resolved_title, captured_at=captured, author=author.strip() if author else None,
            published_at=published_at,
            tags=sorted({tag.strip().lower() for tag in tags or [] if tag.strip()}),
            primary_material=sorted({canonicalize_url(item) for item in primary_material or []}),
            synopsis=synopsis.strip(), notes=notes.strip(),
            provenance=[{"relation": "primary_material", "url": canonicalize_url(item)} for item in primary_material or []],
            metadata={"tags": sorted({tag.strip().lower() for tag in tags or [] if tag.strip()}), "synopsis": synopsis.strip()},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRecord":
        data = dict(data)
        # The durable record vocabulary uses submitted_url/publication_date. The
        # shorter names remain internal compatibility aliases.
        data["url"] = data.get("submitted_url", data.get("url", data.get("canonical_url")))
        data["published_at"] = data.get("publication_date", data.get("published_at"))
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        data.setdefault("tags", metadata.get("tags", []))
        data.setdefault("synopsis", metadata.get("synopsis", ""))
        provenance = data.get("provenance") if isinstance(data.get("provenance"), list) else []
        data.setdefault("primary_material", [
            edge["url"] for edge in provenance
            if isinstance(edge, dict) and edge.get("relation") == "primary_material" and edge.get("url")
        ])
        required = ["id", "url", "canonical_url", "title", "captured_at"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValidationError(f"Source record missing: {', '.join(missing)}")
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in known})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "canonical_url": self.canonical_url,
            "submitted_url": self.url,
            "captured_at": self.captured_at,
            "publication_date": self.published_at,
            "kind": self.kind,
            "status": self.status,
            "content_hash": self.content_hash,
            "provenance": self.provenance,
            "rights": self.rights,
            "metadata": {**self.metadata, "tags": self.tags, "synopsis": self.synopsis},
            "notes": self.notes,
        }

    def write(self, sources_dir: Path) -> Path:
        directory = sources_dir / self.id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "record.yaml"
        path.write_text(dump_yaml(self.to_dict()), encoding="utf-8")
        return path


def load_records(sources_dir: Path) -> list[SourceRecord]:
    if not sources_dir.exists():
        return []
    records = [SourceRecord.from_dict(load_structured(path)) for path in sources_dir.glob("*/record.y*ml")]
    seen: dict[str, str] = {}
    for record in records:
        if record.canonical_url in seen:
            raise ValidationError(f"Duplicate canonical URL in {seen[record.canonical_url]} and {record.id}")
        seen[record.canonical_url] = record.id
    return sorted(records, key=lambda item: (item.captured_at, item.id), reverse=True)
