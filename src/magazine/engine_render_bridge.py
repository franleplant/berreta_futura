"""Versioned subprocess seam from the XState engine to the deep renderer.

The bridge receives an explicit inventory of immutable files, stages only those
files in a temporary root, and writes only beneath a caller-owned destination.
It does not inspect production records, workflow status, review records, or the
release ledger.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .cover import CoverCompiler, replace_outer_pages
from .errors import MagazineError, ValidationError
from .manifest import Edition, load_edition, load_translation
from .package import package_release
from .reader_layout import RenderLayout, declared_editorial_page_cap
from .records import load_records
from .render_engine import reader_renderer


CONTRACT_VERSION = "magazine-renderer/1"
_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "rendererContractVersion",
    "operation",
    "editionId",
    "articleId",
    "primaryLanguage",
    "languages",
    "publicationName",
    "renderer",
    "artifactRoot",
    "design",
    "inputs",
    "metadata",
}
_INPUT_KEYS = {"artifactId", "sourcePath", "targetPath"}


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return value


def _strict_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValidationError(f"{label} has unknown fields: {', '.join(unknown)}")


def _absolute_directory(value: object, label: str) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        raise ValidationError(f"{label} must be an absolute path")
    if path.is_symlink():
        raise ValidationError(f"{label} must not be a symlink")
    return path.resolve()


def _safe_target(value: object) -> Path:
    raw = str(value or "")
    path = Path(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(f"input targetPath is unsafe: {raw!r}")
    return path


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _load_request(path: Path) -> dict[str, Any]:
    try:
        request = _mapping(json.loads(path.read_text(encoding="utf-8")), "request")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot read render request {path}: {exc}") from exc
    _strict_keys(request, _TOP_LEVEL_KEYS, "render request")
    if request.get("schemaVersion") != 1:
        raise ValidationError("render request schemaVersion must be 1")
    if request.get("rendererContractVersion") != CONTRACT_VERSION:
        raise ValidationError(
            f"rendererContractVersion must be {CONTRACT_VERSION!r}"
        )
    if request.get("operation") not in {
        "measure_article",
        "measure_edition",
        "render_edition",
    }:
        raise ValidationError(
            "operation must be measure_article, measure_edition, or render_edition"
        )
    for key in ("editionId", "primaryLanguage", "publicationName", "renderer"):
        if not isinstance(request.get(key), str) or not request[key].strip():
            raise ValidationError(f"render request {key} must be a non-empty string")
    languages = request.get("languages")
    if (
        not isinstance(languages, list)
        or not languages
        or any(not isinstance(item, str) or not item.strip() for item in languages)
    ):
        raise ValidationError("render request languages must be non-empty strings")
    if len(set(languages)) != len(languages):
        raise ValidationError("render request languages must be unique")
    if request["primaryLanguage"] not in languages:
        raise ValidationError("languages must include primaryLanguage")
    if request["operation"] == "measure_article" and not str(
        request.get("articleId") or ""
    ).strip():
        raise ValidationError("measure_article requires articleId")
    if request["renderer"] not in {"reportlab", "weasyprint"}:
        raise ValidationError("renderer must be reportlab or weasyprint")
    if not isinstance(request.get("inputs"), list) or not request["inputs"]:
        raise ValidationError("render request inputs must be a non-empty list")
    return request


def _stage_inputs(request: dict[str, Any], stage_root: Path) -> list[str]:
    artifact_root = _absolute_directory(request.get("artifactRoot"), "artifactRoot")
    if not artifact_root.is_dir():
        raise ValidationError(f"artifactRoot is not a directory: {artifact_root}")
    artifact_ids: list[str] = []
    targets: set[Path] = set()
    for index, raw in enumerate(request["inputs"]):
        row = _mapping(raw, f"inputs[{index}]")
        _strict_keys(row, _INPUT_KEYS, f"inputs[{index}]")
        artifact_id = str(row.get("artifactId") or "").strip()
        if not artifact_id:
            raise ValidationError(f"inputs[{index}].artifactId must be non-empty")
        source = Path(str(row.get("sourcePath") or ""))
        if not source.is_absolute():
            raise ValidationError(f"inputs[{index}].sourcePath must be absolute")
        if source.is_symlink():
            raise ValidationError(f"inputs[{index}].sourcePath must not be a symlink")
        source = source.resolve()
        if not _inside(source, artifact_root) or not source.is_file():
            raise ValidationError(
                f"inputs[{index}].sourcePath must be a file beneath artifactRoot"
            )
        target = _safe_target(row.get("targetPath"))
        if target in targets:
            raise ValidationError(f"duplicate input targetPath: {target.as_posix()}")
        targets.add(target)
        destination = stage_root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        artifact_ids.append(artifact_id)
    return artifact_ids


def _load_languages(stage_root: Path, request: dict[str, Any]) -> dict[str, Edition]:
    source_records = {
        record.id: record for record in load_records(stage_root / "library" / "sources")
    }
    edition = load_edition(
        stage_root,
        request["editionId"],
        set(source_records),
        publication_name=request["publicationName"],
        source_records=source_records,
    )
    if edition.language != request["primaryLanguage"]:
        raise ValidationError(
            "staged edition language does not match primaryLanguage"
        )
    editions = {request["primaryLanguage"]: edition}
    for language in request["languages"]:
        if language != request["primaryLanguage"]:
            editions[language] = load_translation(stage_root, edition, language)
    return editions


def _layout_row(
    language: str,
    layout: RenderLayout,
    reader_pdf: Path,
    critic_result: str,
) -> dict[str, Any]:
    return {
        "language": language,
        "totalPages": len(PdfReader(str(reader_pdf)).pages),
        "editorialPages": layout.editorial_pages or 0,
        "articlePages": layout.article_pages,
        "figureCount": len(layout.figure_placements),
        "criticResult": critic_result,
    }


def _render_manifest(
    request: dict[str, Any],
    variant: Edition,
    layout: RenderLayout,
    input_artifact_ids: list[str],
    stage_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "renderer_contract_version": CONTRACT_VERSION,
        "publication": {
            "name": request["publicationName"],
            "language": variant.language,
            "locale": variant.locale,
            "available_languages": request["languages"],
        },
        "edition": variant.raw,
        "inputs": {"artifact_ids": input_artifact_ids},
        "layout": {
            "design_direction": layout.design,
            "cover_art_size_points": layout.cover_art_size_points,
            "article_terminal_balance": layout.article_terminal_balance,
            "maximum_article_pages": int(
                (variant.raw.get("format") or {}).get("max_article_pages", 7)
            ),
            "article_pages": layout.article_pages,
            "maximum_editorial_pages": declared_editorial_page_cap(variant.raw, 2),
            "editorial_pages": layout.editorial_pages,
            "figures": [
                {
                    "id": placement.figure_id,
                    "article_id": placement.article_id,
                    "page": placement.page,
                    "path": placement.path.relative_to(stage_root).as_posix(),
                    "pixel_dimensions": list(placement.pixel_dimensions),
                    "box_points": list(placement.box_points),
                    "effective_ppi": placement.effective_ppi,
                    "caption": placement.caption,
                    "credit": placement.credit,
                    "rights_status": placement.rights_status,
                }
                for placement in layout.figure_placements
            ],
        },
        "studio_release_ready": False,
        "studio_blocker": "A named printer profile and preflight are required.",
    }


def _file_kind(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if path.name == "reader.pdf":
            return "reader_pdf", "application/pdf"
        if path.name == "booklet.pdf":
            return "booklet_pdf", "application/pdf"
        return "render_pdf", "application/pdf"
    if suffix == ".png":
        return "render_review_image", "image/png"
    if suffix == ".json":
        if path.name == "preflight.json":
            return "printer_preflight", "application/json"
        if path.name == "render-critic.json":
            return "render_critic_report", "application/json"
        return "render_report", "application/json"
    if suffix == ".md":
        return "render_instructions", "text/markdown"
    return "render_file", "text/plain"


def _render(
    request: dict[str, Any],
    stage_root: Path,
    destination: Path,
    input_artifact_ids: list[str],
) -> dict[str, Any]:
    editions = _load_languages(stage_root, request)
    renderer = reader_renderer(request["renderer"], design=request.get("design"))
    layouts: list[dict[str, Any]] = []
    files: list[dict[str, str]] = []
    tail_art_facts: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="mag-engine-render-work-") as temporary:
        work = Path(temporary)
        cover_compiler = CoverCompiler(stage_root)
        for language in request["languages"]:
            variant = editions[language]
            language_work = work / language
            language_work.mkdir(parents=True, exist_ok=True)
            interior_pdf = language_work / "interior.pdf"
            reader_pdf = language_work / "reader.pdf"
            layout = renderer.render(variant, interior_pdf)
            if request["operation"] in {"measure_article", "measure_edition"}:
                if request["operation"] == "measure_article":
                    article_id = request["articleId"]
                    if article_id not in layout.article_pages:
                        raise ValidationError(f"unknown measured article: {article_id}")
                layouts.append(_layout_row(language, layout, interior_pdf, "not_run"))
                continue
            cover = cover_compiler.compile(variant, language_work / "front")
            back = cover_compiler.compile_back(variant, language_work / "back")
            replace_outer_pages(interior_pdf, cover.pdf, back.pdf, reader_pdf)
            tail_art_facts[language] = variant.raw.get("_rendered_tail_arts", [])
            package_destination = destination / language
            manifest = _render_manifest(
                request, variant, layout, input_artifact_ids, stage_root
            )
            written = package_release(
                reader_pdf,
                package_destination,
                manifest,
                cover_art=variant.cover_art,
                cover_art_size_points=layout.cover_art_size_points,
                figure_placements=layout.figure_placements,
                language=language,
                toc=layout.toc,
                article_pages=layout.article_pages,
                editorial_pages=layout.editorial_pages,
                edition_id=variant.id,
                recorded_review=None,
            )
            report = json.loads(
                (package_destination / "render-critic.json").read_text(encoding="utf-8")
            )
            layouts.append(
                _layout_row(language, layout, package_destination / "reader.pdf", report["result"])
            )
            for path in written:
                kind, media_type = _file_kind(path)
                files.append(
                    {
                        "path": path.relative_to(destination).as_posix(),
                        "mediaType": media_type,
                        "kind": kind,
                    }
                )
    return {
        "schemaVersion": 1,
        "rendererContractVersion": CONTRACT_VERSION,
        "editionId": request["editionId"],
        "files": files,
        "layouts": layouts,
        "inputArtifactIds": input_artifact_ids,
        "tailArtFacts": tail_art_facts,
    }


def render_manifest(request_path: Path, destination: Path) -> dict[str, Any]:
    request_path = request_path.resolve()
    if not request_path.is_file() or request_path.is_symlink():
        raise ValidationError(f"Render request is not a regular file: {request_path}")
    destination = _absolute_directory(destination, "destination")
    if destination.exists() and any(destination.iterdir()):
        raise ValidationError(f"Render destination must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    request = _load_request(request_path)
    with tempfile.TemporaryDirectory(prefix="mag-engine-render-stage-") as temporary:
        # macOS exposes the temporary directory through both /var and
        # /private/var.  Resolve once so paths returned by the renderer and
        # the containment root use the same spelling.
        stage_root = Path(temporary).resolve()
        artifact_ids = _stage_inputs(request, stage_root)
        return _render(request, stage_root, destination, artifact_ids)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: mag-render-adapter <render-manifest.json> <destination>", file=sys.stderr)
        return 2
    try:
        result = render_manifest(Path(args[0]), Path(args[1]))
    except (MagazineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
