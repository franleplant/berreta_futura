from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Mapping

import yaml

from .document_structure import block_signature
from .errors import ValidationError
from .io import load_structured, safe_project_path
from .media_schema import Figure, localize_figures, resolve_figures
from .publication_document import DocumentParseError, parse_publication_document

if TYPE_CHECKING:
    from .records import SourceRecord


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    short_title: str
    display_emphasis: str
    opener_variant: str
    author: str
    author_note: str
    source_ids: tuple[str, ...]
    manuscript: Path
    fidelity: Path
    content_mode: str
    figures: tuple[Figure, ...] = ()
    minimum_reader_pages: int = 1
    tail_art: Path | None = None
    source_url: str | None = None
    """The canonical URL of the article's *first* source, or nothing.

    ``source_ids`` is authored and ordered, so the first entry is the article's
    primary source and the one a reader is sent back to.  It is resolved here,
    once, from the same source records the rest of the edition is validated
    against, because it is an editorial fact about the article and not something
    a renderer should be reading source records to discover.

    ``None`` is an ordinary state, not a failure: a source record is not
    required to carry a ``canonical_url``, and an editorial has no source at
    all.  Every consumer treats the absence as "no link back", never as an
    error.
    """


@dataclass(frozen=True)
class Section:
    kind: str
    title: str
    path: Path


@dataclass(frozen=True)
class Editorial:
    path: Path
    title: str
    byline: str
    label: str


@dataclass(frozen=True)
class ClosingPlate:
    title: str
    art_path: Path


@dataclass(frozen=True)
class Edition:
    id: str
    publication_name: str
    issue_number: str
    title: str
    publication_date: str
    language: str
    locale: str
    editorial: Editorial | None
    articles: tuple[Article, ...]
    sections: tuple[Section, ...]
    cover: dict[str, Any]
    cover_art: Path | None
    closing_plates: tuple[ClosingPlate, ...]
    raw: dict[str, Any]


def load_edition(
    root: Path,
    edition_id: str,
    known_sources: set[str],
    *,
    publication_name: str = "Magazine",
    source_records: Mapping[str, "SourceRecord"] | None = None,
) -> Edition:
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
        missing = [
            key
            for key in (
                "id",
                "title",
                "short_title",
                "opener_variant",
                "author",
                "source_ids",
                "manuscript",
                "fidelity",
            )
            if not row.get(key)
        ]
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
            continue
        author_note = str(row.get("author_note") or "").strip()
        if "\n" in author_note or len(author_note) > 160:
            errors.append(
                f"{label} author_note must be a single line of at most 160 characters"
            )
        if author_note and str(row["author"]).strip().casefold() in {
            "editors",
            "the editors",
            "editorial team",
            "the editorial team",
        }:
            errors.append(
                f"{label} must omit author_note for the self-explanatory house byline "
                f"{row['author']!r}"
            )
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
            tail_art = (
                safe_project_path(root, row["tail_art_path"])
                if row.get("tail_art_path")
                else None
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        content_mode = str(row.get("content_mode", "faithful_edit"))
        if content_mode not in {"faithful_edit", "faithful_synthesis", "selected_extracts", "original_synthesis"}:
            errors.append(f"{label} has invalid content_mode: {content_mode}")
        if (
            source_records is not None
            and source_ids
            and content_mode != "original_synthesis"
        ):
            primary_record = source_records.get(source_ids[0])
            if primary_record is not None and primary_record.schema_version >= 2:
                captured_author = str(primary_record.author or "").strip()
                captured_profile = primary_record.author_profile
                if not captured_author or captured_profile is None:
                    errors.append(
                        f"{label} primary source {primary_record.id} has no captured "
                        "author identity; recapture it with author profile evidence"
                    )
                else:
                    if str(row["author"]).strip() != captured_author:
                        errors.append(
                            f"{label} byline must match captured source author "
                            f"{captured_author!r}"
                        )
                    if author_note != captured_profile.note:
                        errors.append(
                            f"{label} author_note must match the captured author biography"
                        )
        try:
            minimum_reader_pages = int(row.get("minimum_reader_pages", 1))
        except (TypeError, ValueError):
            minimum_reader_pages = 0
        if not 1 <= minimum_reader_pages <= 7:
            errors.append(f"{label} minimum_reader_pages must be an integer from 1 to 7")
        display_emphasis = str(row.get("display_emphasis") or "").strip()
        if display_emphasis and display_emphasis.casefold() not in str(row["title"]).casefold():
            errors.append(
                f"{label} display_emphasis must occur in its localized title"
            )
        short_title = str(row.get("short_title") or "").strip()
        if "\n" in short_title or len(short_title) > 40:
            errors.append(f"{label} short_title must be a single line of at most 40 characters")
        elif short_title.casefold() not in str(row["title"]).casefold():
            errors.append(f"{label} short_title must occur in its localized title")
        opener_variant = str(row.get("opener_variant") or "").strip()
        if opener_variant not in {"edge_medallion", "split_axis", "stepped_title"}:
            errors.append(f"{label} has invalid opener_variant: {opener_variant}")
        try:
            figures = resolve_figures(
                root,
                article_id=str(row["id"]),
                article_source_ids=source_ids,
                manuscript=manuscript,
                rows=row.get("figures"),
                records=source_records,
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            figures = ()
        articles.append(
            Article(
                row["id"],
                row["title"],
                short_title,
                display_emphasis,
                opener_variant,
                row["author"],
                author_note,
                source_ids,
                manuscript,
                fidelity,
                content_mode,
                figures,
                minimum_reader_pages,
                tail_art,
                _primary_source_url(source_ids, source_records),
            )
        )
    edition_dir = manifest_path.parent
    try:
        editorial_path = _edition_path(root, edition_dir, data["editorial"]) if data.get("editorial") else None
        editorial = _load_editorial(editorial_path) if editorial_path else None
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
        if str(row["kind"]).strip().casefold() == "colophon":
            errors.append("Colophon sections are no longer supported")
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
    closing_rows = data.get("closing_plates") or []
    if not isinstance(closing_rows, list):
        errors.append("Edition closing_plates must be a list")
        closing_rows = []
    closing_plates: list[ClosingPlate] = []
    closing_titles: set[str] = set()
    closing_paths: set[Path] = set()
    for index, row in enumerate(closing_rows, start=1):
        if not isinstance(row, dict) or not row.get("title") or not row.get("art_path"):
            errors.append(f"Closing plate {index} requires title and art_path")
            continue
        title = str(row["title"]).strip()
        try:
            art_path = safe_project_path(root, row["art_path"])
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        if title.casefold() in closing_titles:
            errors.append(f"Closing plate title must be unique: {title}")
        if art_path in closing_paths:
            errors.append(f"Closing plate art_path must be unique: {row['art_path']}")
        closing_titles.add(title.casefold())
        closing_paths.add(art_path)
        closing_plates.append(ClosingPlate(title, art_path))
    if closing_rows and len(closing_rows) != 3:
        errors.append("Edition closing_plates must define exactly three unique padding plates")
    if errors:
        raise ValidationError(errors)
    return Edition(
        str(data["id"]),
        publication_name,
        str(data["issue_number"]),
        str(data["title"]),
        str(data["publication_date"]),
        str(data.get("language") or "en"),
        str(data.get("locale") or data.get("language") or "en"),
        editorial,
        tuple(articles),
        tuple(sections),
        cover,
        cover_art,
        tuple(closing_plates),
        data,
    )


def load_translation(
    root: Path,
    base: Edition,
    language: str,
) -> Edition:
    """Load a complete, hash-pinned language overlay for an edition."""
    translation_dir = root / "editions" / base.id / "translations" / language
    manifest_path = translation_dir / "edition.yaml"
    if not manifest_path.is_file():
        raise ValidationError(
            f"Required {language!r} translation manifest not found: "
            f"{manifest_path.relative_to(root)}"
        )
    data = load_structured(manifest_path)
    errors: list[str] = []
    if str(data.get("language") or "") != language:
        errors.append(
            f"Translation language {data.get('language')!r} does not match directory {language!r}"
        )
    if str(data.get("source_language") or "") != base.language:
        errors.append(
            f"Translation source_language must be {base.language!r}"
        )
    expected_copy_hash = _edition_copy_sha256(base)
    pinned_copy_hash = data.get("base_copy_sha256")
    if pinned_copy_hash != expected_copy_hash:
        # Withholding the expected digest here used to force authors to
        # reconstruct it by hand; the error now states both sides so the fix is
        # a review followed by a re-pin, not an archaeology dig.
        errors.append(
            f"Translation {language!r} is stale: base_copy_sha256 is "
            f"{pinned_copy_hash!r}, but the base edition copy hashes to "
            f"{expected_copy_hash}; the overlay no longer matches the base edition"
        )

    translated_cover = data.get("cover")
    if not isinstance(translated_cover, dict):
        errors.append(f"Translation {language!r} requires translated cover copy")
        translated_cover = {}
    for key in ("headline", "deck", "edition_label", "back_text"):
        if base.cover.get(key) and not translated_cover.get(key):
            errors.append(f"Translation {language!r} cover is missing {key}")

    translated_editorial: Editorial | None = None
    editorial_row = data.get("editorial")
    if base.editorial:
        if not isinstance(editorial_row, dict) or not editorial_row.get("path"):
            errors.append(f"Translation {language!r} requires an editorial path")
        else:
            try:
                translated_path = _edition_path(root, translation_dir, editorial_row["path"])
                _validate_translation_file(
                    base.editorial.path,
                    translated_path,
                    editorial_row.get("source_sha256"),
                    f"Translation {language!r} editorial",
                    errors,
                )
                translated_editorial = _load_editorial(translated_path)
            except ValidationError as exc:
                errors.extend(exc.errors)

    article_rows = data.get("articles")
    if not isinstance(article_rows, list):
        errors.append(f"Translation {language!r} articles must be a list")
        article_rows = []
    translated_by_id = {
        str(row.get("id")): row
        for row in article_rows
        if isinstance(row, dict) and row.get("id")
    }
    base_ids = {article.id for article in base.articles}
    missing_ids = sorted(base_ids - set(translated_by_id))
    extra_ids = sorted(set(translated_by_id) - base_ids)
    if missing_ids:
        errors.append(
            f"Translation {language!r} is missing articles: {', '.join(missing_ids)}"
        )
    if extra_ids:
        errors.append(
            f"Translation {language!r} has unknown articles: {', '.join(extra_ids)}"
        )
    translated_articles: list[Article] = []
    for article in base.articles:
        row = translated_by_id.get(article.id)
        if not row:
            continue
        if (
            not row.get("title")
            or not row.get("short_title")
            or not row.get("manuscript")
        ):
            errors.append(
                f"Translation {language!r} article {article.id} requires title, short_title, "
                "and manuscript"
            )
            continue
        author_note = str(row.get("author_note") or "").strip()
        if article.author_note and not author_note:
            errors.append(
                f"Translation {language!r} article {article.id} requires author_note "
                "because the source article has one"
            )
        elif not article.author_note and author_note:
            errors.append(
                f"Translation {language!r} article {article.id} must omit author_note "
                "because the source article omits it"
            )
        if "\n" in author_note or len(author_note) > 160:
            errors.append(
                f"Translation {language!r} article {article.id} author_note must be a "
                "single line of at most 160 characters"
            )
        # A localized byline is optional: most authors are proper names and
        # carry across languages unchanged, so absence means "use the base
        # author".  Like title and short_title it is a display string, checked
        # against the pinned base copy as a whole rather than pinned itself.
        author = article.author
        if "author" in row:
            author = str(row.get("author") or "").strip()
            if not author:
                errors.append(
                    f"Translation {language!r} article {article.id} author cannot be blank"
                )
        display_emphasis = str(row.get("display_emphasis") or "").strip()
        if display_emphasis and display_emphasis.casefold() not in str(row["title"]).casefold():
            errors.append(
                f"Translation {language!r} article {article.id} display_emphasis must "
                "occur in its localized title"
            )
        short_title = str(row.get("short_title") or "").strip()
        if "\n" in short_title or len(short_title) > 40:
            errors.append(
                f"Translation {language!r} article {article.id} short_title must be a "
                "single line of at most 40 characters"
            )
        elif short_title.casefold() not in str(row["title"]).casefold():
            errors.append(
                f"Translation {language!r} article {article.id} short_title must occur "
                "in its localized title"
            )
        try:
            manuscript = _edition_path(root, translation_dir, row["manuscript"])
            _validate_translation_file(
                article.manuscript,
                manuscript,
                row.get("source_sha256"),
                f"Translation {language!r} article {article.id}",
                errors,
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        try:
            figures = localize_figures(
                article.figures,
                row.get("figures"),
                article_id=article.id,
                manuscript=manuscript,
                language=language,
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            figures = ()
        translated_articles.append(
            Article(
                article.id,
                str(row["title"]),
                short_title,
                display_emphasis,
                article.opener_variant,
                author,
                author_note,
                article.source_ids,
                manuscript,
                article.fidelity,
                article.content_mode,
                figures,
                article.minimum_reader_pages,
                article.tail_art,
                # A translation renders the same article from the same sources,
                # so it points back to the same place.  The link is provenance,
                # not copy, and is never localized.
                article.source_url,
            )
        )

    translated_closing_plates: list[ClosingPlate] = []
    closing_titles = data.get("closing_plate_titles")
    if base.closing_plates:
        if not isinstance(closing_titles, list) or len(closing_titles) != len(base.closing_plates):
            errors.append(
                f"Translation {language!r} requires exactly {len(base.closing_plates)} "
                "closing_plate_titles"
            )
        else:
            normalized_titles = [str(title).strip() for title in closing_titles]
            if any(not title for title in normalized_titles):
                errors.append(f"Translation {language!r} closing_plate_titles cannot be blank")
            elif len({title.casefold() for title in normalized_titles}) != len(normalized_titles):
                errors.append(f"Translation {language!r} closing_plate_titles must be unique")
            else:
                translated_closing_plates = [
                    ClosingPlate(title, plate.art_path)
                    for title, plate in zip(normalized_titles, base.closing_plates)
                ]

    section_rows = data.get("sections")
    if not isinstance(section_rows, list):
        errors.append(f"Translation {language!r} sections must be a list")
        section_rows = []
    if len(section_rows) != len(base.sections):
        errors.append(
            f"Translation {language!r} must contain exactly {len(base.sections)} sections"
        )
    translated_sections: list[Section] = []
    for index, section in enumerate(base.sections):
        if index >= len(section_rows) or not isinstance(section_rows[index], dict):
            continue
        row = section_rows[index]
        if row.get("kind") != section.kind or not row.get("title") or not row.get("path"):
            errors.append(
                f"Translation {language!r} section {index + 1} must preserve kind "
                f"{section.kind!r} and provide title and path"
            )
            continue
        try:
            path = _edition_path(root, translation_dir, row["path"])
            _validate_translation_file(
                section.path,
                path,
                row.get("source_sha256"),
                f"Translation {language!r} section {index + 1}",
                errors,
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        translated_sections.append(Section(section.kind, str(row["title"]), path))

    if errors:
        raise ValidationError(errors)
    raw = dict(base.raw)
    raw.update(
        {
            "title": str(data.get("title") or base.title),
            "subtitle": str(data.get("subtitle") or ""),
            "language": language,
            "locale": str(data.get("locale") or language),
            "translation": {
                "source_language": base.language,
                "fallback_locale": data.get("fallback_locale"),
                "policy": data.get("policy"),
            },
            "cover": dict(translated_cover),
            "closing_plates": [
                {"title": plate.title, "art_path": plate.art_path.relative_to(root).as_posix()}
                for plate in translated_closing_plates
            ],
            "editorial": translated_editorial.path.relative_to(root).as_posix()
            if translated_editorial
            else None,
            "articles": [
                {
                    "id": article.id,
                    "title": article.title,
                    "short_title": article.short_title,
                    "display_emphasis": article.display_emphasis,
                    "opener_variant": article.opener_variant,
                    "author": article.author,
                    "author_note": article.author_note,
                    "content_mode": article.content_mode,
                    "source_ids": list(article.source_ids),
                    "manuscript": article.manuscript.relative_to(root).as_posix(),
                    "fidelity": article.fidelity.relative_to(root).as_posix(),
                    "tail_art_path": (
                        article.tail_art.relative_to(root).as_posix()
                        if article.tail_art
                        else None
                    ),
                    "figures": [
                        {
                            "id": figure.id,
                            "source_id": figure.source_id,
                            "asset_id": figure.asset_id,
                            "caption": figure.caption,
                            "credit": figure.credit,
                            "alt_text": figure.alt_text,
                            "anchor": figure.anchor,
                            "layout": figure.layout,
                            "source_caption_sha256": figure.source_caption_sha256,
                            "source_credit_sha256": figure.source_credit_sha256,
                        }
                        for figure in article.figures
                    ],
                }
                for article in translated_articles
            ],
            "sections": [
                {
                    "kind": section.kind,
                    "title": section.title,
                    "path": section.path.relative_to(root).as_posix(),
                }
                for section in translated_sections
            ],
        }
    )
    return Edition(
        base.id,
        base.publication_name,
        base.issue_number,
        str(data.get("title") or base.title),
        base.publication_date,
        language,
        str(data.get("locale") or language),
        translated_editorial,
        tuple(translated_articles),
        tuple(translated_sections),
        dict(translated_cover),
        base.cover_art,
        tuple(translated_closing_plates),
        raw,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _edition_copy_sha256(edition: Edition) -> str:
    copy = {
        "title": edition.title,
        "subtitle": edition.raw.get("subtitle", ""),
        "cover": {
            key: edition.cover.get(key, "")
            for key in ("headline", "deck", "edition_label", "back_text")
        },
        "closing_plates": [
            {
                "title": plate.title,
                "art_sha256": _sha256(plate.art_path),
            }
            for plate in edition.closing_plates
        ],
        "articles": [
            {
                "id": article.id,
                "title": article.title,
                "short_title": article.short_title,
                "display_emphasis": article.display_emphasis,
                "opener_variant": article.opener_variant,
                "author": article.author,
                "author_note": article.author_note,
                "tail_art_sha256": _sha256(article.tail_art) if article.tail_art else None,
                "figures": [
                    {
                        "id": figure.id,
                        "caption": figure.caption,
                        "credit": figure.credit,
                        "alt_text": figure.alt_text,
                        "anchor": figure.anchor,
                        "layout": figure.layout,
                    }
                    for figure in article.figures
                ],
            }
            for article in edition.articles
        ],
    }
    encoded = json.dumps(copy, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _markdown_signature(path: Path) -> list[str]:
    """Return the manuscript's block structure as the renderer sees it.

    The signature is derived from the same CommonMark parse the reader
    typesets, so a translation is held to the source's *rendered* structure --
    ordered lists with their start numbers, nested lists, block quotes with
    their children, and thematic breaks -- not to a smaller Markdown a
    line scanner happens to know.
    """
    return block_signature(
        parse_publication_document(path.read_text(encoding="utf-8")).blocks
    )


def _validate_translation_file(
    source: Path,
    translation: Path,
    pinned_source_sha256: Any,
    label: str,
    errors: list[str],
) -> None:
    expected_source_sha256 = _sha256(source)
    if pinned_source_sha256 != expected_source_sha256:
        errors.append(
            f"{label} is stale: source_sha256 is {pinned_source_sha256!r}, but "
            f"{source.name} hashes to {expected_source_sha256}; the translation "
            "no longer matches its English source"
        )
    source_signature: list[str] | None = None
    translation_signature: list[str] | None = None
    try:
        source_signature = _markdown_signature(source)
    except DocumentParseError as exc:
        errors.append(
            f"{label} English source {source} cannot be parsed as a publication document: {exc}"
        )
    try:
        translation_signature = _markdown_signature(translation)
    except DocumentParseError as exc:
        errors.append(
            f"{label} translation {translation} cannot be parsed as a publication document: {exc}"
        )
    if source_signature is not None and translation_signature is not None:
        if source_signature != translation_signature:
            errors.append(
                f"{label} does not preserve the source Markdown block structure "
                f"({len(source_signature)} source blocks, {len(translation_signature)} translated blocks)"
            )
    source_links, source_inline_code, source_fenced_code = _markdown_invariants(source)
    translated_links, translated_inline_code, translated_fenced_code = _markdown_invariants(
        translation
    )
    if source_links != translated_links:
        errors.append(f"{label} does not preserve link targets and order")
    if source_inline_code != translated_inline_code:
        errors.append(f"{label} does not preserve inline code identifiers and order")
    if source_fenced_code != translated_fenced_code:
        errors.append(f"{label} does not preserve fenced code exactly")


def _markdown_invariants(path: Path) -> tuple[list[str], list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    fenced = re.findall(r"```[^\n]*\n(.*?)\n```", text, flags=re.DOTALL)
    without_fences = re.sub(r"```[^\n]*\n.*?\n```", "", text, flags=re.DOTALL)
    inline = re.findall(r"(?<!`)`([^`\n]+)`(?!`)", without_fences)
    return links, inline, fenced


def _primary_source_url(
    source_ids: tuple[str, ...], records: Mapping[str, "SourceRecord"] | None
) -> str | None:
    """The canonical URL of the first source, when the records are to hand.

    Deliberately silent about everything it cannot answer.  ``records`` is
    optional on ``load_edition``, a record need not carry a ``canonical_url``,
    and an article's first source may not be one this call was given -- each of
    those is "no link back" and none of them is an error.  Unknown source ids
    are already an edition-level failure by the time this runs, so nothing is
    hidden by the lookup being lenient.
    """
    if not source_ids or not records:
        return None
    record = records.get(source_ids[0])
    url = str(getattr(record, "canonical_url", "") or "").strip()
    return url or None


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
    }.get(str(kind), str(kind).replace("_", " ").title())


def _load_editorial(path: Path) -> Editorial:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise ValidationError(f"Editorial requires YAML frontmatter with a title: {path}")
    header, _, _ = text[4:].partition("\n---\n")
    try:
        metadata = yaml.safe_load(header)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Cannot parse editorial frontmatter {path}: {exc}") from exc
    if not isinstance(metadata, dict) or not str(metadata.get("title", "")).strip():
        raise ValidationError(f"Editorial requires a non-empty title: {path}")
    return Editorial(
        path=path,
        title=str(metadata["title"]).strip(),
        byline=str(metadata.get("byline") or "The editors").strip(),
        label=str(metadata.get("label") or "ORIGINAL EDITORIAL").strip(),
    )
