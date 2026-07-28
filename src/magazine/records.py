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
from .media_schema import MediaCaptureReview, load_media_reviews

_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
_AUTHOR_SUMMARY = re.compile(
    r"\b(?:writes about|reports (?:on|experiments)|describes|maps a|explains|"
    r"explores|examines|argues|summarizes|outlines|presents experiments)\b",
    re.IGNORECASE,
)
_AUTHOR_IDENTITY = re.compile(
    r"\b(?:is|are|was|were|spent|works?|serves?|served|founded|co-founded|"
    r"creator|founder|chief|president|professor|engineer|researcher|member|"
    r"publishing name|name with which|name under which)\b",
    re.IGNORECASE,
)


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
class AuthorEvidence:
    url: str
    capture_id: str

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        raw_capture_ids: set[str] | None = None,
    ) -> "AuthorEvidence":
        if not isinstance(data, dict):
            raise ValidationError("Author biography evidence must be a mapping")
        url = canonicalize_url(str(data.get("url") or ""))
        capture_id = str(data.get("capture_id") or "").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", capture_id):
            raise ValidationError(
                "Author biography evidence capture_id must be a SHA-256 bundle id"
            )
        if raw_capture_ids is not None and capture_id not in raw_capture_ids:
            raise ValidationError(
                f"Author biography evidence references unknown capture {capture_id}"
            )
        return cls(url, capture_id)

    def to_dict(self) -> dict[str, str]:
        return {"url": self.url, "capture_id": self.capture_id}


@dataclass(frozen=True)
class AuthorProfile:
    """Edition-ready identity copy pinned to durable profile evidence."""

    note: str
    evidence: tuple[AuthorEvidence, ...] = ()

    @classmethod
    def create(
        cls,
        note: str,
        *,
        evidence: list[dict[str, Any] | AuthorEvidence],
        raw_capture_ids: set[str] | None = None,
    ) -> "AuthorProfile":
        normalized_note = str(note or "").strip()
        if "\n" in normalized_note or len(normalized_note) > 160:
            raise ValidationError(
                "Author biography must be a single line of at most 160 characters"
            )
        if normalized_note and (
            _AUTHOR_SUMMARY.search(normalized_note)
            or not _AUTHOR_IDENTITY.search(normalized_note)
        ):
            raise ValidationError(
                "Author biography must contain identity or CV context, not an article summary"
            )
        rows = tuple(
            item
            if isinstance(item, AuthorEvidence)
            else AuthorEvidence.from_dict(item, raw_capture_ids=raw_capture_ids)
            for item in evidence
        )
        if normalized_note and not rows:
            raise ValidationError(
                "Author biography requires archived author profile evidence"
            )
        if not normalized_note and rows:
            raise ValidationError(
                "Institutional author profiles must omit biography evidence"
            )
        unique = {(row.url, row.capture_id) for row in rows}
        if len(unique) != len(rows):
            raise ValidationError("Author biography evidence must be unique")
        return cls(normalized_note, rows)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        raw_capture_ids: set[str],
    ) -> "AuthorProfile":
        if not isinstance(data, dict):
            raise ValidationError("author_profile must be a mapping")
        evidence = data.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValidationError("author_profile evidence must be a list")
        return cls.create(
            str(data.get("note") or ""),
            evidence=evidence,
            raw_capture_ids=raw_capture_ids,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "note": self.note,
            "evidence": [row.to_dict() for row in self.evidence],
        }


@dataclass(frozen=True)
class SourceRecord:
    id: str
    url: str
    canonical_url: str
    title: str
    captured_at: str
    author: str | None = None
    author_profile: AuthorProfile | None = None
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
    raw_captures: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    media_reviews: tuple[MediaCaptureReview, ...] = ()
    rights: dict[str, Any] = field(default_factory=lambda: {
        "status": "unknown",
        "intended_use": "private_reference",
        "attribution_required": True,
        "public_reprint_allowed": False,
    })

    @classmethod
    def create(cls, url: str, *, title: str | None = None, author: str | None = None,
               author_profile: AuthorProfile | None = None,
               published_at: str | None = None, captured_at: str | None = None,
               tags: list[str] | None = None, primary_material: list[str] | None = None,
               synopsis: str = "", notes: str = "") -> "SourceRecord":
        canonical = canonicalize_url(url)
        resolved_title = (title or canonical).strip()
        captured = captured_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return cls(
            id=source_id(resolved_title, canonical), url=url.strip(), canonical_url=canonical,
            title=resolved_title, captured_at=captured, author=author.strip() if author else None,
            author_profile=author_profile,
            published_at=published_at,
            tags=sorted({tag.strip().lower() for tag in tags or [] if tag.strip()}),
            primary_material=sorted({canonicalize_url(item) for item in primary_material or []}),
            synopsis=synopsis.strip(), notes=notes.strip(),
            provenance=[{"relation": "primary_material", "url": canonicalize_url(item)} for item in primary_material or []],
            metadata={"tags": sorted({tag.strip().lower() for tag in tags or [] if tag.strip()}), "synopsis": synopsis.strip()},
            # Every brand-new capture uses the provenance-backed schema. A
            # caller may archive the article before identity research is
            # complete, but edition validation will refuse that pending record.
            schema_version=2,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRecord":
        data = dict(data)
        # The durable record vocabulary uses submitted_url/publication_date. The
        # shorter names remain internal compatibility aliases.
        data["url"] = data.get("submitted_url", data.get("url", data.get("canonical_url")))
        data["published_at"] = data.get("publication_date", data.get("published_at"))
        for key in ("captured_at", "published_at"):
            if isinstance(data.get(key), (date, datetime)):
                data[key] = data[key].isoformat()
        raw_captures = data.get("raw_captures")
        if isinstance(raw_captures, list):
            normalized_captures = []
            for capture in raw_captures:
                capture = dict(capture)
                if isinstance(capture.get("captured_at"), (date, datetime)):
                    capture["captured_at"] = capture["captured_at"].isoformat()
                normalized_captures.append(capture)
            data["raw_captures"] = normalized_captures
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
        raw_capture_ids = {
            str(item.get("id"))
            for item in data.get("raw_captures", [])
            if isinstance(item, dict) and item.get("id")
        }
        profile_data = data.get("author_profile")
        data["author_profile"] = (
            AuthorProfile.from_dict(
                profile_data,
                raw_capture_ids=raw_capture_ids,
            )
            if profile_data is not None
            else None
        )
        data["media_reviews"] = load_media_reviews(
            data.get("media_reviews"),
            source_id=str(data["id"]),
            raw_capture_ids=raw_capture_ids,
        )
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in known})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "title": self.title,
            "author": self.author,
            **(
                {"author_profile": self.author_profile.to_dict()}
                if self.author_profile is not None
                else {}
            ),
            "canonical_url": self.canonical_url,
            "submitted_url": self.url,
            "captured_at": self.captured_at,
            "publication_date": self.published_at,
            "kind": self.kind,
            "status": self.status,
            "content_hash": self.content_hash,
            "raw_captures": self.raw_captures,
            "provenance": self.provenance,
            "rights": self.rights,
            "media_reviews": [review.to_dict() for review in self.media_reviews],
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
