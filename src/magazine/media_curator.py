from __future__ import annotations

from dataclasses import replace
from html import unescape
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit

from resvg import render as render_svg_tree, usvg

from .errors import ValidationError
from .media_schema import MediaCaptureReview, SourceMediaAsset


CURATION_SCHEMA_VERSION = 1
CURATOR_POLICY_VERSION = "editorial-impact-v4"
MAX_IMAGES_PER_ARTICLE = 3
_SVG = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
_STYLE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_HEADING = re.compile(r"<h[1-4]\b[^>]*>(.*?)</h[1-4]>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"[a-z0-9]+")
_VIEWBOX = re.compile(
    r"\bviewBox\s*=\s*['\"]\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)\s*['\"]",
    re.IGNORECASE,
)
_UTILITY_WORDS = {
    "architecture", "citation", "data", "distillation", "embedding", "evidence",
    "flow", "fusion", "pipeline", "planner", "query", "rerank", "retrieval",
    "search", "source", "synthesis", "system", "tool", "vector",
}
_FALLBACK_SVG_STYLE = """
<style>
svg { --paper:#fbfbfb; --ink:#171717; --white:#fff; --cobalt-50:#fff7f3;
  --cobalt-100:#fee8df; --cobalt-200:#f7b9a5; --cobalt-300:#e47d5b;
  --cobalt-500:#cc461f; --cobalt-600:#a93613; --cobalt-700:#7c260f;
  --danger:#b52b33; --label:#777; --hairline:#ddd;
  --font-mono:Helvetica,Arial,sans-serif; }
.svg-label { fill:#a93613; font-family:Helvetica,Arial,sans-serif; font-size:10px; }
.svg-label-muted { fill:#666; font-family:Helvetica,Arial,sans-serif; font-size:9px; }
.stroke { fill:none; stroke:#a93613; stroke-width:1.25; }
.stroke-muted { fill:none; stroke:#e47d5b; stroke-width:1; }
.fill-50 { fill:#fff7f3; } .fill-100 { fill:#fee8df; }
.fill-300 { fill:#e47d5b; } .fill-white { fill:#fff; }
.dash { stroke-dasharray:4 4; } .ink { stroke:#171717; }
.danger-stroke { stroke:#b52b33; } .danger-fill { fill:#fbe9ea; }
</style>
""".strip()


def curation_plan_path(source_dir: Path, bundle_sha256: str) -> Path:
    return source_dir / "media" / f"{bundle_sha256}.curation.json"


def curate_source(record, sources_dir: Path, *, refresh_capture_ids: set[str] | None = None):
    """Automatically curate every capture and return a record plus audit paths.

    Raw evidence is never modified. Inline vectors are converted into generated,
    hash-pinned PNG derivatives so the print renderer has a deterministic input.
    """

    source_dir = sources_dir / record.id
    reviews = {review.capture_id: review for review in record.media_reviews}
    paths: list[Path] = []
    for descriptor in sorted(record.raw_captures, key=lambda row: str(row.get("id", ""))):
        if str(descriptor.get("purpose") or "article") != "article":
            continue
        bundle = str(descriptor.get("id") or "")
        if not bundle:
            raise ValidationError(f"Source {record.id} has an invalid raw capture descriptor")
        existing = reviews.get(bundle)
        plan = curation_plan_path(source_dir, bundle)
        refresh = refresh_capture_ids is not None and bundle in refresh_capture_ids
        if existing is not None and not plan.is_file() and not refresh:
            # Legacy editorial choices are durable. Automatic curation owns new
            # captures and any capture already enrolled through a curation audit.
            continue
        review, path = _curate_capture(record, source_dir, bundle)
        reviews[bundle] = review
        paths.append(path)
    return replace(record, media_reviews=tuple(reviews[key] for key in sorted(reviews))), tuple(paths)


def verify_source_curation(record, sources_dir: Path) -> None:
    """Verify automatic decisions and derivatives without rewriting them."""

    source_dir = sources_dir / record.id
    reviews = {review.capture_id: review for review in record.media_reviews}
    errors: list[str] = []
    for descriptor in record.raw_captures:
        bundle = str(descriptor.get("id") or "")
        path = curation_plan_path(source_dir, bundle)
        if not path.is_file():
            continue  # Pre-automation records retain their durable decisions.
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            manifest = json.loads((source_dir / "raw" / bundle / "manifest.json").read_text(encoding="utf-8"))
            inventory = json.loads((source_dir / "media" / f"{bundle}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot verify automatic curation for {record.id}: {exc}")
            continue
        artifact_rows = {
            str(row.get("path")): row
            for row in manifest.get("artifacts", [])
            if isinstance(row, dict) and row.get("path")
        }
        expected_input = _canonical_hash({
            "inventory": inventory, "artifacts": artifact_rows,
            "title": record.title, "synopsis": record.synopsis,
        })
        if (
            plan.get("source_id") != record.id
            or plan.get("bundle_sha256") != bundle
            or plan.get("policy_version") != CURATOR_POLICY_VERSION
            or plan.get("input_sha256") != expected_input
        ):
            errors.append(f"Automatic media curation is stale for {record.id} capture {bundle}")
            continue
        selected = list(plan.get("selected", []))
        if len(selected) > MAX_IMAGES_PER_ARTICLE or len(selected) != len(set(selected)):
            errors.append(f"Automatic media curation has an invalid selection for {record.id}")
            continue
        candidates = {
            str(row.get("id")): row
            for row in plan.get("candidates", [])
            if isinstance(row, dict) and row.get("id")
        }
        review = reviews.get(bundle)
        asset_ids = [asset.id for asset in review.assets] if review else []
        if asset_ids != selected:
            errors.append(f"Source record media selection is stale for {record.id} capture {bundle}")
            continue
        for asset in review.assets:
            candidate = candidates.get(asset.id, {})
            if candidate.get("origin") == "raw_raster":
                derivative = source_dir / "raw" / bundle / "artifacts" / Path(
                    *PurePosixPath(asset.artifact_path).parts
                )
            else:
                derivative = source_dir / Path(*PurePosixPath(asset.artifact_path).parts)
            if (
                candidate.get("decision") != "include"
                or candidate.get("artifact_path") != asset.artifact_path
                or candidate.get("artifact_sha256") != asset.artifact_sha256
                or not derivative.is_file()
                or hashlib.sha256(derivative.read_bytes()).hexdigest() != asset.artifact_sha256
            ):
                errors.append(f"Automatic media derivative is missing or stale: {asset.id}")
    if errors:
        raise ValidationError(errors)


def _curate_capture(record, source_dir: Path, bundle: str) -> tuple[MediaCaptureReview, Path]:
    manifest_path = source_dir / "raw" / bundle / "manifest.json"
    inventory_path = source_dir / "media" / f"{bundle}.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot curate source media for {record.id}: {exc}") from exc

    artifact_root = manifest_path.parent / "artifacts"
    artifact_rows = {
        str(row.get("path")): row
        for row in manifest.get("artifacts", [])
        if isinstance(row, dict) and row.get("path")
    }
    candidates = _raster_candidates(inventory)
    for path, row in sorted(artifact_rows.items()):
        if PurePosixPath(path).suffix.casefold() != ".json":
            continue
        candidates.extend(
            _inline_svg_candidates(
                artifact_root / Path(path), source_dir=source_dir, bundle=bundle,
                source_artifact=path,
                source_artifact_sha256=str(row.get("sha256") or ""),
            )
        )

    ranked = sorted(candidates, key=lambda row: (-int(row["score"]), str(row["id"])))
    selected = _select_diverse(ranked)
    selected_ids = {str(row["id"]) for row in selected}
    for candidate in candidates:
        candidate["decision"] = "include" if candidate["id"] in selected_ids else "reject"
        if candidate["decision"] == "reject" and not candidate["rejection_reasons"]:
            candidate["rejection_reasons"] = ["lower_editorial_impact_than_selected_candidates"]
    _remove_unselected_derivatives(source_dir, bundle, selected)

    plan = {
        "schema_version": CURATION_SCHEMA_VERSION,
        "curator": "magazine-compiler/automatic-media-curator",
        "policy_version": CURATOR_POLICY_VERSION,
        "source_id": record.id,
        "bundle_sha256": bundle,
        "input_sha256": _canonical_hash({
            "inventory": inventory, "artifacts": artifact_rows,
            "title": record.title, "synopsis": record.synopsis,
        }),
        "candidate_count": len(candidates),
        "selection_limit": MAX_IMAGES_PER_ARTICLE,
        "selected": [row["id"] for row in selected],
        "candidates": sorted(candidates, key=lambda row: str(row["id"])),
    }
    path = curation_plan_path(source_dir, bundle)
    _write_json(path, plan)

    if not candidates:
        return MediaCaptureReview(
            bundle, "no_media", (),
            "Automatic curation found no source images or substantive inline diagrams.",
        ), path
    if not selected:
        counts: dict[str, int] = {}
        for row in candidates:
            for reason in row["rejection_reasons"]:
                counts[reason] = counts.get(reason, 0) + 1
        summary = ", ".join(f"{reason} ({count})" for reason, count in sorted(counts.items()))
        return MediaCaptureReview(
            bundle, "media_rejected", (), f"Automatic curation rejected all candidates: {summary}.",
        ), path

    assets = tuple(
        SourceMediaAsset(
            str(row["id"]), str(row["artifact_path"]), str(row["artifact_sha256"]),
            "image/png" if str(row["artifact_path"]).endswith(".png") else str(row["mime_type"]),
            record.author or _host(record.canonical_url), _credit(record), dict(record.rights),
        )
        for row in selected
    )
    note = (
        f"Automatic curation selected {len(assets)} of {len(candidates)} candidates under "
        f"{CURATOR_POLICY_VERSION}; decisions are hash-pinned in {path.name}."
    )
    return MediaCaptureReview(bundle, "media_curated", assets, note), path


def _raster_candidates(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    referenced = {
        str(row.get("resolved_path"))
        for row in inventory.get("local_references", [])
        if isinstance(row, dict) and row.get("present")
    }
    declared = {
        str(row.get("resolved_path")): row
        for row in inventory.get("local_references", [])
        if isinstance(row, dict) and row.get("attribute") == "manifest" and row.get("present")
    }
    seen_hashes: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, image in enumerate(inventory.get("images", []), start=1):
        path = str(image["path"])
        artifact_sha256 = str(image["sha256"])
        context = declared.get(path, {})
        role = str(context.get("role") or "")
        width = int(image["pixel_width"])
        height = int(image["pixel_height"])
        aspect = width / height
        rejection: list[str] = []
        if aspect < 0.2 or aspect > 5:
            rejection.append("extreme_aspect_ratio_or_full_page_capture")
        if width < 600 or height < 300:
            rejection.append("insufficient_print_resolution")
        if referenced and path not in referenced:
            rejection.append("not_referenced_by_source_content")
        if not referenced:
            rejection.append("no_semantic_source_context")
        if artifact_sha256 in seen_hashes:
            rejection.append("duplicate_media_asset")
        seen_hashes.add(artifact_sha256)
        if role == "title_card":
            rejection.append("article_title_card")
        if role in {"decorative", "duplicate"}:
            rejection.append("non_editorial_media_role")
        score = 0
        if not rejection:
            score = 50 + min(10, (width * height) // 250_000)
            score += 6 if context else 0
            # Explanatory diagrams usually carry a distinct conceptual layer,
            # while charts within one results section often repeat the same
            # comparison. Give diagrams a slight lead before section diversity.
            score += 8 if role == "diagram" else 6 if role == "figure" else 0
        criteria = []
        if score:
            criteria = ["useful"]
            if role in {"diagram", "figure"}:
                criteria.insert(0, "important")
        title = str(context.get("title") or PurePosixPath(path).stem.replace("-", " ").replace("_", " "))
        description = str(context.get("description") or "")
        result.append({
            "id": f"raster-{index:03d}-{str(image['sha256'])[:8]}",
            "origin": "raw_raster", "source_artifact": path,
            "source_artifact_sha256": str(image["sha256"]), "artifact_path": path,
            "artifact_sha256": artifact_sha256, "mime_type": str(image["mime_type"]),
            "pixel_width": width, "pixel_height": height, "aspect_ratio": round(aspect, 6),
            "heading": str(context.get("heading") or ""), "title": title,
            "description": description,
            "source_position": int(context.get("source_position") or index), "score": score,
            "criteria": criteria,
            "rationale": (
                f"{title} is a source-referenced, print-resolvable visual explanation."
                if score else ""
            ),
            "rejection_reasons": rejection,
        })
    return result


def _inline_svg_candidates(
    capture_json: Path, *, source_dir: Path, bundle: str,
    source_artifact: str, source_artifact_sha256: str,
) -> list[dict[str, Any]]:
    try:
        payload = json.loads(capture_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    html = payload.get("main_html") if isinstance(payload, dict) else None
    if not isinstance(html, str) or not html.strip():
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, match in enumerate(_SVG.finditer(html), start=1):
        svg = match.group(0)
        fragment_sha = hashlib.sha256(svg.encode("utf-8")).hexdigest()
        if fragment_sha in seen:
            continue
        seen.add(fragment_sha)
        heading = _last_plain(_HEADING, html[: match.start()])
        style = _last_plain(_STYLE, html[: match.start()], strip_tags=False)
        title = _element_text(svg, "title")
        description = _element_text(svg, "desc")
        visible_text = _plain_text(svg)
        viewbox = _VIEWBOX.search(svg)
        width, height = (float(viewbox.group(1)), float(viewbox.group(2))) if viewbox else (0.0, 0.0)
        aspect = width / height if height else 0.0
        shape_count = len(re.findall(r"<(?:path|rect|circle|ellipse|polygon|polyline|line)\b", svg, re.I))
        text_count = len(re.findall(r"<text\b", svg, re.I))
        rejection: list[str] = []
        if re.search(r"<(?:script|foreignObject|image)\b", svg, re.I):
            rejection.append("unsafe_or_externally_loaded_svg")
        if re.search(r"\b(?:href|xlink:href)\s*=\s*['\"](?!#)", svg, re.I):
            rejection.append("unsafe_or_externally_loaded_svg")
        if re.search(r"\baria-hidden\s*=\s*['\"]true['\"]", svg, re.I):
            rejection.append("decorative_or_aria_hidden")
        if not viewbox or width < 300 or height < 120 or aspect < 0.2 or aspect > 5:
            rejection.append("not_a_print_figure")
        if shape_count < 4 and len(visible_text) < 20:
            rejection.append("insufficient_visual_information")
        if shape_count < 3 and text_count:
            rejection.append("pure_text_image")
        rejection = list(dict.fromkeys(rejection))

        score = _svg_score(
            position=position, heading=heading, title=title, description=description,
            visible_text=visible_text, shape_count=shape_count, text_count=text_count,
            aspect=aspect, rejected=bool(rejection),
        )
        derived_name = f"svg-{position:03d}-{fragment_sha[:12]}.png"
        derived_path = PurePosixPath("media") / "derived" / bundle / derived_name
        artifact_sha = ""
        pixel_width = 0
        pixel_height = 0
        if not rejection:
            output = source_dir / Path(*derived_path.parts)
            rendered = _render_svg(svg, style=style, output_width=1800)
            artifact_sha = hashlib.sha256(rendered).hexdigest()
            _write_bytes(output, rendered)
            pixel_width = 1800
            pixel_height = max(1, round(1800 / aspect))

        criteria = _criteria(score, shape_count, position, len(visible_text)) if not rejection else []
        result.append({
            "id": f"svg-{position:03d}-{fragment_sha[:8]}", "origin": "inline_svg",
            "source_artifact": source_artifact, "source_artifact_sha256": source_artifact_sha256,
            "source_fragment_sha256": fragment_sha, "artifact_path": derived_path.as_posix(),
            "artifact_sha256": artifact_sha, "mime_type": "image/png",
            "pixel_width": pixel_width, "pixel_height": pixel_height,
            "aspect_ratio": round(aspect, 6), "heading": heading, "title": title,
            "description": description, "source_position": position, "score": score,
            "criteria": criteria, "rationale": _rationale(criteria, heading, title) if criteria else "",
            "rejection_reasons": rejection,
        })
    return result


def _svg_score(
    *, position: int, heading: str, title: str, description: str, visible_text: str,
    shape_count: int, text_count: int, aspect: float, rejected: bool,
) -> int:
    if rejected:
        return 0
    words = set(_WORD.findall(f"{heading} {title} {description} {visible_text}".casefold()))
    utility = len(words & _UTILITY_WORDS)
    score = 32 + min(20, utility * 3) + min(14, shape_count // 3)
    score += 10 if title and description else 5 if title else 0
    score += 14 if position == 1 else 0
    score += 6 if 0.75 <= aspect <= 2.5 else 2
    score += 5 if 2 <= text_count <= 30 else 0
    if len(visible_text) > 900:
        score -= 18
    return max(0, min(100, score))


def _select_diverse(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [row for row in ranked if not row["rejection_reasons"] and int(row["score"]) >= 58]
    selected: list[dict[str, Any]] = []
    contexts: set[tuple[str, str]] = set()
    headings: set[str] = set()
    hashes: set[str] = set()

    def add(row: dict[str, Any]) -> bool:
        heading = str(row.get("heading") or "").casefold()
        title = str(row.get("title") or "").casefold()
        context = (heading, title)
        artifact_sha256 = str(row.get("artifact_sha256") or "")
        if context != ("", "") and context in contexts:
            return False
        if artifact_sha256 and artifact_sha256 in hashes:
            return False
        selected.append(row)
        contexts.add(context)
        if heading:
            headings.add(heading)
        if artifact_sha256:
            hashes.add(artifact_sha256)
        return True

    # First spread the scarce print slots across semantic sections. A second
    # pass may use another figure from a strong section when fewer than three
    # distinct headings exist.
    for row in eligible:
        heading = str(row.get("heading") or "").casefold()
        if heading and heading in headings:
            continue
        add(row)
        if len(selected) == MAX_IMAGES_PER_ARTICLE:
            return selected
    for row in eligible:
        add(row)
        if len(selected) == MAX_IMAGES_PER_ARTICLE:
            return selected
    return selected


def _remove_unselected_derivatives(
    source_dir: Path, bundle: str, selected: list[dict[str, Any]]
) -> None:
    directory = source_dir / "media" / "derived" / bundle
    if not directory.is_dir():
        return
    keep = {
        Path(*PurePosixPath(str(row["artifact_path"])).parts)
        for row in selected
        if row.get("origin") == "inline_svg"
    }
    for path in directory.glob("*.png"):
        relative = path.relative_to(source_dir)
        if relative not in keep:
            path.unlink()


def _criteria(score: int, shape_count: int, position: int, text_length: int) -> list[str]:
    criteria = ["useful"]
    if position == 1 or score >= 82:
        criteria.insert(0, "important")
    if shape_count >= 12 and text_length < 700:
        criteria.append("beautiful")
    if shape_count >= 20 and score >= 75:
        criteria.append("cool")
    return criteria


def _rationale(criteria: list[str], heading: str, title: str) -> str:
    subject = title or heading or "This source diagram"
    return f"{subject} is a {', '.join(criteria)} visual explanation that earns its space in print."


def _render_svg(svg: str, *, style: str, output_width: int) -> bytes:
    opening_end = svg.find(">")
    if opening_end < 0:
        raise ValidationError("Cannot rasterize malformed inline SVG")
    opening = svg[:opening_end]
    if "xmlns=" not in opening:
        opening += ' xmlns="http://www.w3.org/2000/svg"'
    source_style = style.replace(".cb-fig ", "").replace(".cb-fig,", "svg,")
    prepared = opening + ">" + f"<style>{source_style}</style>" + _FALLBACK_SVG_STYLE + svg[opening_end + 1 :]
    try:
        options = usvg.Options.default()
        options.load_system_fonts()
        tree = usvg.Tree.from_str(prepared, options)
        width, height = tree.int_size()
        if width < 1:
            raise ValueError("SVG has no renderable width")
        scale = output_width / width
        output_height = max(1, round(height * scale))
        return render_svg_tree(
            tree,
            (scale, 0.0, 0.0, 0.0, scale, 0.0),
            bg_size=(output_width, output_height),
            bg_color=(255, 255, 255, 255),
        )
    except Exception as exc:
        raise ValidationError(f"Cannot rasterize archived inline SVG: {exc}") from exc


def _element_text(source: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", source, re.I | re.S)
    return _plain_text(match.group(1)) if match else ""


def _last_plain(pattern: re.Pattern[str], source: str, *, strip_tags: bool = True) -> str:
    matches = list(pattern.finditer(source))
    if not matches:
        return ""
    value = matches[-1].group(1)
    return _plain_text(value) if strip_tags else value


def _plain_text(value: str) -> str:
    return " ".join(unescape(_TAG.sub(" ", value)).split())


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "Source").removeprefix("www.")


def _credit(record) -> str:
    creator = record.author or _host(record.canonical_url)
    return f"Diagram by {creator}; source: {record.title}."


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_bytes(path, payload)


def _write_bytes(path: Path, payload: bytes) -> None:
    if path.is_file() and path.read_bytes() == payload:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}-", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    os.replace(temporary, path)
