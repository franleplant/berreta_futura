from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError

FIGURE_LAYOUTS = {
    "evidence_band",
    "evidence_band_prose",
    "adaptive_band",
    "compact_band",
    "column_plate",
    "landscape_plate",
    "landscape_plate_after",
}


@dataclass(frozen=True)
class Figure:
    id: str
    source_id: str
    path: Path
    caption: str
    credit: str
    alt_text: str
    anchor: str
    layout: str


def resolve_figures(
    root: Path,
    *,
    article_id: str,
    article_source_ids: tuple[str, ...],
    manuscript: Path,
    rows: Any,
    allow_unanchored: bool = False,
) -> tuple[Figure, ...]:
    if rows in (None, []):
        return ()
    if not isinstance(rows, list):
        raise ValidationError(f"Article {article_id} figures must be a list")
    if len(rows) > 3:
        raise ValidationError(f"Article {article_id} selects {len(rows)} figures; maximum is 3")
    errors: list[str] = []
    figures: list[Figure] = []
    seen: set[str] = set()
    headings = semantic_headings(manuscript)
    for index, row in enumerate(rows):
        label = f"Article {article_id} figure {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        fields = _figure_fields(label, row, errors)
        if fields is None:
            continue
        if fields["id"] in seen:
            errors.append(f"Article {article_id} has duplicate figure id: {fields['id']}")
        seen.add(fields["id"])
        figure = _resolve_figure(
            root, label, fields, article_source_ids, headings, allow_unanchored, errors
        )
        if figure is not None:
            figures.append(figure)
    if errors:
        raise ValidationError(errors)
    return tuple(figures)


def _figure_fields(label: str, row: dict[str, Any], errors: list[str]) -> dict[str, str] | None:
    fields = {
        name: str(row.get(name) or "").strip()
        for name in ("id", "source_id", "path", "caption", "credit", "alt_text", "anchor", "layout")
    }
    missing = [name for name, value in fields.items() if name != "credit" and not value]
    if missing:
        errors.append(f"{label} missing: {', '.join(missing)}")
        return None
    return fields


def _resolve_figure(
    root: Path,
    label: str,
    fields: dict[str, str],
    article_source_ids: tuple[str, ...],
    headings: set[str],
    allow_unanchored: bool,
    errors: list[str],
) -> Figure | None:
    if fields["source_id"] not in article_source_ids:
        errors.append(f"{label} source_id must be one of the article source_ids")
    relative = PurePosixPath(fields["path"])
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label} has unsafe path: {fields['path']!r}")
        return None
    if fields["layout"] not in FIGURE_LAYOUTS:
        errors.append(f"{label} has invalid layout: {fields['layout'] or '<missing>'}")
    anchor = fields["anchor"]
    if anchor != "__opener__" and anchor not in headings and not allow_unanchored:
        errors.append(f"{label} anchor does not match an article heading: {anchor!r}")
    path = root / "library" / "sources" / fields["source_id"] / Path(*relative.parts)
    if not path.is_file():
        errors.append(f"{label} image file is missing: {path}")
        return None
    return Figure(
        fields["id"],
        fields["source_id"],
        path,
        fields["caption"],
        fields["credit"],
        fields["alt_text"],
        anchor,
        fields["layout"],
    )


def localize_figures(
    base: tuple[Figure, ...],
    rows: Any,
    *,
    article_id: str,
    manuscript: Path,
    language: str,
) -> tuple[Figure, ...]:

    if not base:
        if rows not in (None, []):
            raise ValidationError(
                f"Translation {language!r} article {article_id} has figures absent from English"
            )
        return ()
    if not isinstance(rows, list):
        raise ValidationError(
            f"Translation {language!r} article {article_id} figures must be a list"
        )
    errors: list[str] = []
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}
    expected_ids = {figure.id for figure in base}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        if missing:
            errors.append(
                f"Translation {language!r} article {article_id} is missing figures: {', '.join(missing)}"
            )
        if extra:
            errors.append(
                f"Translation {language!r} article {article_id} has unknown figures: {', '.join(extra)}"
            )
    headings = semantic_headings(manuscript)
    localized: list[Figure] = []
    for figure in base:
        row = by_id.get(figure.id)
        if not row:
            continue
        caption = str(row.get("caption") or "").strip()
        credit = str(row.get("credit") or "").strip() or figure.credit
        alt_text = str(row.get("alt_text") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        if not caption or not alt_text or not anchor:
            errors.append(
                f"Translation {language!r} figure {figure.id} requires caption, alt_text, and anchor"
            )
        if anchor != "__opener__" and anchor not in headings:
            errors.append(
                f"Translation {language!r} figure {figure.id} anchor does not match a translated heading"
            )
        localized.append(
            replace(figure, caption=caption, credit=credit, alt_text=alt_text, anchor=anchor)
        )
    if errors:
        raise ValidationError(errors)
    return tuple(localized)


EXTRACT_STYLES = {"code", "quote"}


@dataclass(frozen=True)
class Extract:
    id: str
    source_id: str
    text: str
    style: str
    caption: str
    anchor: str


def resolve_extracts(
    root: Path,
    *,
    article_id: str,
    article_source_ids: tuple[str, ...],
    manuscript: Path,
    rows: Any,
    allow_unanchored: bool = False,
) -> tuple[Extract, ...]:
    if rows in (None, []):
        return ()
    if not isinstance(rows, list):
        raise ValidationError(f"Article {article_id} extracts must be a list")
    if len(rows) > 2:
        raise ValidationError(f"Article {article_id} selects {len(rows)} extracts; maximum is 2")
    errors: list[str] = []
    extracts: list[Extract] = []
    seen: set[str] = set()
    manuscript_text = manuscript.read_text(encoding="utf-8")
    headings = semantic_headings(manuscript)
    for index, row in enumerate(rows):
        label = f"Article {article_id} extract {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        fields = _extract_fields(label, row, errors)
        if fields is None:
            continue
        if fields["id"] in seen:
            errors.append(f"Article {article_id} has duplicate extract id: {fields['id']}")
        seen.add(fields["id"])
        if fields["source_id"] not in article_source_ids:
            errors.append(f"{label} source_id must be one of the article source_ids")
            continue
        _check_extract_style(label, fields, headings, allow_unanchored, errors)
        text = _extract_run(root, label, fields, errors)
        if text is None:
            continue
        _check_extract_text(label, fields["style"], text, manuscript_text, errors)
        extracts.append(
            Extract(
                fields["id"],
                fields["source_id"],
                text,
                fields["style"],
                fields["caption"],
                fields["anchor"],
            )
        )
    if errors:
        raise ValidationError(errors)
    return tuple(extracts)


def _extract_fields(label: str, row: dict[str, Any], errors: list[str]) -> dict[str, str] | None:
    fields = {
        "id": str(row.get("id") or "").strip(),
        "source_id": str(row.get("source_id") or "").strip(),
        "begin": str(row.get("begin") or ""),
        "end": str(row.get("end") or ""),
        "style": str(row.get("style") or "").strip(),
        "caption": str(row.get("caption") or "").strip(),
        "anchor": str(row.get("anchor") or "").strip(),
    }
    missing = [name for name, value in fields.items() if not value]
    if missing:
        errors.append(f"{label} missing: {', '.join(missing)}")
        return None
    return fields


def _check_extract_style(
    label: str,
    fields: dict[str, str],
    headings: set[str],
    allow_unanchored: bool,
    errors: list[str],
) -> None:
    style, anchor = fields["style"], fields["anchor"]
    if style not in EXTRACT_STYLES:
        errors.append(f"{label} has invalid style: {style!r}; known: {sorted(EXTRACT_STYLES)}")
    if anchor != "__opener__" and anchor not in headings and not allow_unanchored:
        errors.append(f"{label} anchor does not match an article heading: {anchor!r}")


def _extract_run(root: Path, label: str, fields: dict[str, str], errors: list[str]) -> str | None:
    source_path = root / "library" / "sources" / fields["source_id"] / "article.md"
    if not source_path.is_file():
        errors.append(f"{label} source article is missing: {source_path}")
        return None
    source_text = source_path.read_text(encoding="utf-8")
    begin, end = fields["begin"], fields["end"]
    if source_text.count(begin) != 1:
        errors.append(
            f"{label} begin marker must occur exactly once in the source "
            f"(found {source_text.count(begin)}): {begin!r}"
        )
        return None
    start = source_text.index(begin)
    if source_text.count(end, start) != 1:
        errors.append(
            f"{label} end marker must occur exactly once at or after begin "
            f"(found {source_text.count(end, start)}): {end!r}"
        )
        return None
    return source_text[start : source_text.index(end, start) + len(end)]


def _check_extract_text(
    label: str, style: str, text: str, manuscript_text: str, errors: list[str]
) -> None:
    if style == "code" and ("\t" in text or "  " in text):
        errors.append(
            f"{label} run carries layout-significant whitespace (tabs or "
            "space runs), which a wrapping code panel cannot preserve; "
            "use begin/end markers that avoid it or style: quote"
        )
    if text in manuscript_text:
        errors.append(
            f"{label} run already appears verbatim in the manuscript; "
            "drop the extract row or the manuscript's own copy"
        )


def localize_extracts(
    base: tuple[Extract, ...],
    rows: Any,
    *,
    article_id: str,
    manuscript: Path,
    language: str,
) -> tuple[Extract, ...]:

    if not base:
        if rows not in (None, []):
            raise ValidationError(
                f"Translation {language!r} article {article_id} has extracts absent from English"
            )
        return ()
    if not isinstance(rows, list):
        raise ValidationError(
            f"Translation {language!r} article {article_id} extracts must be a list"
        )
    errors: list[str] = []
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}
    expected_ids = {extract.id for extract in base}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        if missing:
            errors.append(
                f"Translation {language!r} article {article_id} is missing extracts: {', '.join(missing)}"
            )
        if extra:
            errors.append(
                f"Translation {language!r} article {article_id} has unknown extracts: {', '.join(extra)}"
            )
    headings = semantic_headings(manuscript)
    localized: list[Extract] = []
    for extract in base:
        row = by_id.get(extract.id)
        if not row:
            continue
        caption = str(row.get("caption") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        if not caption or not anchor:
            errors.append(
                f"Translation {language!r} extract {extract.id} requires caption and anchor"
            )
        if anchor != "__opener__" and anchor not in headings:
            errors.append(
                f"Translation {language!r} extract {extract.id} anchor does not match a translated heading"
            )
        localized.append(replace(extract, caption=caption, anchor=anchor))
    if errors:
        raise ValidationError(errors)
    return tuple(localized)


def semantic_headings(path: Path) -> set[str]:

    headings: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        for prefix in ("## ", "### "):
            if line.startswith(prefix) and line[len(prefix) :].strip():
                headings.add(line[len(prefix) :].strip())
    return headings
