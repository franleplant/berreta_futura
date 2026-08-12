from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Mapping

import yaml

from .document_structure import block_signature
from .errors import ValidationError
from .io import load_structured, safe_project_path
from .media_schema import Figure, localize_figures, resolve_figures
from .publication_document import DocumentParseError, Paragraph, parse_publication_document

if TYPE_CHECKING:
    from .records import SourceRecord


CONTENT_MODES: frozenset[str] = frozenset(
    {
        "article",
        "in_a_nutshell",
    }
)
"""The magazine's two article writers (2026-08-06 simplification).

``article`` is the standard retell through prompts/article.md; the historical
``faithful_edit`` / ``faithful_synthesis`` / ``selected_extracts`` /
``original_synthesis`` taxonomy is gone.  ``in_a_nutshell`` is the teaching
explainer: the magazine's own Teacher voice grounded in the captured source.
The edition-level editorial is its own third writer and never appears as an
article content_mode.
"""

EDITOR_VOICE_CONTENT_MODES: frozenset[str] = frozenset(
    {"in_a_nutshell"}
)
"""Modes whose byline is an editor's, not the captured source author's.

The byline check below matches an article's byline against the identity its
primary source record captured.  For these two the magazine is the writer, so
the check would demand the editors rename themselves after the author they are
explaining, and staging cannot infer the byline from the source at all.
"""

HOUSE_BYLINES: frozenset[str] = frozenset(
    {"editors", "the editors", "editorial team", "the editorial team"}
)
"""Bylines that are the magazine signing its own work.

They are self-explanatory, so an article carrying one may not also carry an
``author_note``: there is no third party to introduce.  Every rule that asks
after an author biography reads this set, so the two halves -- "must omit" and
"must supply" -- cannot drift into a pair no byline can satisfy.
"""

SECTION_KINDS: tuple[str, ...] = (
    "original_editorial",
    "source_introduction",
    "original_synthesis",
    "source_record",
    "production_note",
    "glossary",
    "try_it",
    "cheat_sheet",
)
"""The edition-level pieces that are not articles, in no particular order.

Adding a kind is four edits and no new machinery: this tuple, the default title
in :func:`_section_title`, and the localized kicker in the two renderers'
label vocabularies (``render.UI_COPY`` and ``html_edition._ui``).  Rendering,
pinning, packaging and translation reconciliation all iterate sections
generically and need no change at all.
"""

KEY_IDEAS_WORD_BUDGET = 90
"""The hard ceiling on an article's key-ideas box, counted across all its lines.

A closing box is paid for in reader pages, and the budget is what keeps a
whole edition's teaching furniture inside about three added pages.  It is
measured here, off ``edition.yaml``, so an over-long box is refused before
anything is laid out.
"""


@dataclass(frozen=True)
class ArticleOpenerArt:
    path: Path
    alt_text: str
    credit: str


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
    opener_art: ArticleOpenerArt | None = None
    key_ideas: tuple[str, ...] = ()
    """The claims a reader must retain to *use* the piece, in editor voice.

    Not a summary and not the manuscript's own words: the lines are authored in
    ``edition.yaml`` rather than in manuscript frontmatter precisely because
    they are editorial furniture -- they flow through translation
    reconciliation like any other localized copy, and their
    :data:`KEY_IDEAS_WORD_BUDGET` can be measured before a single page is laid
    out.

    An article closes with one object, never two, so an article carrying key
    ideas may not also declare ``tail_art_path``; validation refuses the pair.
    """
    dateline: str | None = None
    """One date standing for the article, "YYYY MM", or nothing.

    Resolved at load time from the newest source ``published_at`` (see
    ``_representative_dateline``), the same record-derived editorial fact
    pattern as ``source_url``: absence is an ordinary state, never an error.
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
    allow_missing_art: bool = False,
    allow_unanchored_figures: bool = False,
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
    if not isinstance(declared_sources, list):
        errors.append("Edition sources must be a list")
        declared_sources = []
    elif any(not isinstance(value, str) or not value.strip() for value in declared_sources):
        errors.append("Edition sources must contain non-empty source id strings")
        declared_sources = []
    else:
        unknown_declared = sorted(set(declared_sources) - known_sources)
        if unknown_declared:
            errors.append(f"Edition references unknown sources: {', '.join(unknown_declared)}")
    if not data.get("sections") and (not data.get("editorial") or not data.get("articles")):
        errors.append("Edition requires either sections, or editorial plus articles")
    raw_format = data.get("format")
    if raw_format is None:
        edition_format: dict[str, Any] = {}
    elif not isinstance(raw_format, dict):
        errors.append("Edition format must be a mapping")
        edition_format = {}
    else:
        edition_format = dict(raw_format)
    article_opener_format = str(edition_format.get("article_opener") or "").strip()
    if article_opener_format and article_opener_format != "illustrated_paper_spots_v1":
        errors.append(
            f"Edition has invalid format.article_opener: {article_opener_format}"
        )
    illustrated_article_openers = (
        article_opener_format == "illustrated_paper_spots_v1"
    )
    if illustrated_article_openers and not str(
        data.get("art_direction_path") or ""
    ).strip():
        errors.append(
            "Edition format.article_opener illustrated_paper_spots_v1 requires "
            "art_direction_path"
        )
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
            )
            if not row.get(key)
        ]
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
            continue
        article_id = row["id"]
        if not isinstance(article_id, str) or not article_id.strip():
            errors.append(f"Article {index + 1} id must be a non-empty string")
            continue
        declared_article_sources = row["source_ids"]
        if (
            not isinstance(declared_article_sources, list)
            or not declared_article_sources
            or any(
                not isinstance(source_id, str) or not source_id.strip()
                for source_id in declared_article_sources
            )
        ):
            errors.append(f"{label} source_ids must be a non-empty list of strings")
            continue
        author_note = str(row.get("author_note") or "").strip()
        if "\n" in author_note or len(author_note) > 160:
            errors.append(
                f"{label} author_note must be a single line of at most 160 characters"
            )
        house_byline = str(row["author"]).strip().casefold() in HOUSE_BYLINES
        if author_note and house_byline:
            errors.append(
                f"{label} must omit author_note for the self-explanatory house byline "
                f"{row['author']!r}"
            )
        if article_id in ids:
            errors.append(f"Duplicate article id: {article_id}")
        ids.add(article_id)
        source_ids = tuple(declared_article_sources)
        unknown = sorted(set(source_ids) - known_sources)
        if unknown:
            errors.append(f"{label} references unknown sources: {', '.join(unknown)}")
        try:
            manuscript = _edition_path(root, manifest_path.parent, row["manuscript"])
            tail_art = (
                _edition_path(
                    root,
                    manifest_path.parent,
                    row["tail_art_path"],
                    must_exist=not allow_missing_art,
                )
                if row.get("tail_art_path")
                else None
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        opener_art = None
        if illustrated_article_openers:
            # The illustrated opener sets a biography under the byline, so a
            # republished author owes one.  The house byline is the exception
            # and has to be: the rule just above refuses an author_note for it,
            # so demanding one here would make an editor-voiced piece --
            # `original_synthesis`, `in_a_nutshell` -- impossible to declare in
            # an illustrated edition at all.
            if not author_note and not house_byline:
                errors.append(
                    f"{label} requires author_note for "
                    "format.article_opener illustrated_paper_spots_v1"
                )
            raw_opener_art = row.get("opener_art")
            if not isinstance(raw_opener_art, dict) or not raw_opener_art:
                errors.append(
                    f"{label} requires a non-empty opener_art mapping for "
                    "format.article_opener illustrated_paper_spots_v1"
                )
            else:
                missing_opener_art = [
                    key
                    for key in ("path", "alt_text", "credit")
                    if not isinstance(raw_opener_art.get(key), str)
                    or not raw_opener_art[key].strip()
                ]
                if missing_opener_art:
                    errors.append(
                        f"{label} opener_art requires non-empty "
                        + ", ".join(missing_opener_art)
                    )
                else:
                    try:
                        opener_art_path = _edition_path(
                            root,
                            manifest_path.parent,
                            raw_opener_art["path"],
                            must_exist=not allow_missing_art,
                        )
                    except ValidationError as exc:
                        errors.extend(exc.errors)
                    else:
                        opener_art = ArticleOpenerArt(
                            path=opener_art_path,
                            alt_text=raw_opener_art["alt_text"].strip(),
                            credit=raw_opener_art["credit"].strip(),
                        )
            try:
                opener_document = parse_publication_document(
                    manuscript.read_text(encoding="utf-8")
                )
            except DocumentParseError as exc:
                errors.append(
                    f"{label} manuscript cannot be parsed as a publication document: {exc}"
                )
            else:
                if (
                    not opener_document.blocks
                    or not isinstance(opener_document.blocks[0], Paragraph)
                ):
                    errors.append(
                        f"{label} first manuscript block must be a paragraph for "
                        "format.article_opener illustrated_paper_spots_v1"
                    )
        try:
            key_ideas = _key_ideas(label, row.get("key_ideas"))
        except ValidationError as exc:
            errors.extend(exc.errors)
            key_ideas = ()
        if key_ideas and tail_art is not None:
            errors.append(
                f"{label} declares both key_ideas and tail_art_path; an article "
                "closes with one object, not two -- drop whichever the piece needs less"
            )
        content_mode = str(row.get("content_mode", "faithful_edit"))
        if content_mode not in CONTENT_MODES:
            errors.append(f"{label} has invalid content_mode: {content_mode}")
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
                article_id=article_id,
                article_source_ids=source_ids,
                manuscript=manuscript,
                rows=row.get("figures"),
                allow_unanchored=allow_unanchored_figures,
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            figures = ()
        articles.append(
            Article(
                article_id,
                row["title"],
                short_title,
                display_emphasis,
                opener_variant,
                row["author"],
                author_note,
                source_ids,
                manuscript,
                content_mode,
                figures,
                minimum_reader_pages,
                tail_art,
                _primary_source_url(source_ids, source_records),
                opener_art,
                key_ideas,
                dateline=_representative_dateline(source_ids, source_records),
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
    if section_rows is None:
        section_rows = []
    elif not isinstance(section_rows, list):
        errors.append("Edition sections must be a list")
        section_rows = []
    for index, row in enumerate(section_rows):
        if not isinstance(row, dict) or not row.get("kind") or not row.get("path"):
            errors.append(f"Section {index + 1} requires kind and path")
            continue
        if str(row["kind"]).strip().casefold() == "colophon":
            errors.append("Colophon sections are no longer supported")
            continue
        if str(row["kind"]) not in SECTION_KINDS:
            errors.append(
                f"Section {index + 1} has unknown kind {row['kind']!r}; the known "
                "kinds are " + ", ".join(SECTION_KINDS)
            )
            continue
        try:
            path = _edition_path(root, edition_dir, row["path"])
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        sections.append(Section(str(row["kind"]), str(row.get("title") or _section_title(row["kind"])), path))
    raw_cover = data.get("cover")
    if raw_cover is None:
        cover: dict[str, Any] = {}
    elif not isinstance(raw_cover, dict):
        errors.append("Edition cover must be a mapping")
        cover = {}
    else:
        cover = dict(raw_cover)
    tail_art_fit = str(data.get("tail_art_fit") or "cover").strip()
    if tail_art_fit not in {"cover", "contain"}:
        errors.append("Edition tail_art_fit must be cover or contain")
    cover_art = None
    if cover.get("art_path"):
        try:
            cover_art = _edition_path(root, edition_dir, cover["art_path"])
        except ValidationError as exc:
            errors.extend(exc.errors)
    closing_rows = data.get("closing_plates", [])
    if closing_rows is None:
        closing_rows = []
    elif not isinstance(closing_rows, list):
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
            art_path = _edition_path(
                root,
                edition_dir,
                row["art_path"],
                must_exist=not allow_missing_art,
            )
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
    if closing_rows and len(closing_rows) < 3:
        errors.append("Edition closing_plates must define at least three unique padding plates")
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
        # Key ideas are localized copy, so the overlay carries its own lines --
        # same count, same budget -- rather than inheriting the English ones.
        key_ideas: tuple[str, ...] = ()
        if article.key_ideas or row.get("key_ideas") is not None:
            try:
                key_ideas = _key_ideas(
                    f"Translation {language!r} article {article.id}",
                    row.get("key_ideas"),
                )
            except ValidationError as exc:
                errors.extend(exc.errors)
            if not article.key_ideas:
                errors.append(
                    f"Translation {language!r} article {article.id} must omit key_ideas "
                    "because the source article omits them"
                )
            elif not key_ideas:
                errors.append(
                    f"Translation {language!r} article {article.id} requires key_ideas "
                    "because the source article has them"
                )
            elif len(key_ideas) != len(article.key_ideas):
                errors.append(
                    f"Translation {language!r} article {article.id} must translate all "
                    f"{len(article.key_ideas)} key_ideas lines, not {len(key_ideas)}"
                )
        try:
            manuscript = _edition_path(root, translation_dir, row["manuscript"])
            _validate_translation_file(
                article.manuscript,
                manuscript,
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
                article.content_mode,
                figures,
                article.minimum_reader_pages,
                article.tail_art,
                # A translation renders the same article from the same sources,
                # so it points back to the same place.  The link is provenance,
                # not copy, and is never localized.
                article.source_url,
                article.opener_art,
                key_ideas,
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
                    "tail_art_path": (
                        article.tail_art.relative_to(root).as_posix()
                        if article.tail_art
                        else None
                    ),
                    **({"key_ideas": list(article.key_ideas)} if article.key_ideas else {}),
                    **(
                        {
                            "opener_art": {
                                "path": article.opener_art.path.relative_to(
                                    root
                                ).as_posix(),
                                "alt_text": article.opener_art.alt_text,
                                "credit": article.opener_art.credit,
                            }
                        }
                        if article.opener_art
                        else {}
                    ),
                    "figures": [
                        {
                            "id": figure.id,
                            "source_id": figure.source_id,
                            "path": figure.path.as_posix(),
                            "caption": figure.caption,
                            "credit": figure.credit,
                            "alt_text": figure.alt_text,
                            "anchor": figure.anchor,
                            "layout": figure.layout,
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
    label: str,
    errors: list[str],
) -> None:
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



def _representative_dateline(
    source_ids: tuple[str, ...], records: Mapping[str, "SourceRecord"] | None
) -> str | None:
    """One date standing for the article: its newest source, as "YYYY MM".

    A single-source article dates itself; a synthesis is as current as its
    freshest source, so the newest ``published_at`` wins.  Rendered in the
    cover footer's spaced-digit style, which is also language-neutral.  As
    with the source URL, everything unanswerable is "no dateline": absent
    records, records without ``published_at``, an editorial with no sources.
    """
    if not source_ids or not records:
        return None
    dates = [
        str(getattr(records.get(source_id), "published_at", "") or "").strip()
        for source_id in source_ids
    ]
    dates = [d for d in dates if d]
    if not dates:
        return None
    newest = max(dates)  # ISO dates order lexically
    parts = newest.split("-")
    if len(parts) < 2:
        return parts[0]
    return f"{parts[0]} {parts[1]}"


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
    url = str(getattr(record, "url", "") or "").strip()
    return url or None


def _edition_path(
    root: Path,
    edition_dir: Path,
    value: object,
    *,
    must_exist: bool = True,
) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"Referenced path must be a non-empty string, got {value!r}"
        )
    path = Path(value)
    if path.parts and path.parts[0] == "editions":
        return safe_project_path(root, value, must_exist=must_exist)
    relative = (edition_dir / path).resolve()
    try:
        relative.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"Path escapes project root: {value}") from exc
    if must_exist and not relative.is_file():
        raise ValidationError(
            f"Referenced file does not exist: {relative.relative_to(root.resolve())}"
        )
    return relative


def _key_ideas(label: str, value: object) -> tuple[str, ...]:
    """The article's key-ideas lines, checked against the budget they are paid in.

    Absent is the ordinary case and returns nothing.  Present means a non-empty
    list of single-line claims whose words, counted together, fit
    :data:`KEY_IDEAS_WORD_BUDGET` -- the box is one closing object and is
    measured as one, not line by line.
    """
    if value is None:
        return ()
    if (
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(item, str) or not item.strip() or "\n" in item
            for item in value
        )
    ):
        raise ValidationError(
            f"{label} key_ideas must be a non-empty list of single-line strings"
        )
    ideas = tuple(item.strip() for item in value)
    words = sum(len(idea.split()) for idea in ideas)
    if words > KEY_IDEAS_WORD_BUDGET:
        raise ValidationError(
            f"{label} key_ideas run to {words} words; the budget is "
            f"{KEY_IDEAS_WORD_BUDGET}. State the claims a reader needs to use the "
            "thing, not a summary of the piece"
        )
    return ideas


def _section_title(kind: str) -> str:
    return {
        "original_editorial": "Editorial",
        "source_introduction": "Introduction",
        "original_synthesis": "Reading Map",
        "source_record": "Source Record",
        "production_note": "Production Note",
        "glossary": "Glossary",
        "try_it": "Try It in Fifteen Minutes",
        "cheat_sheet": "Cheat Sheet",
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
