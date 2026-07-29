"""Edition illustration plans and deterministic authoring prompt packages.

Image generation is an author-time act, never part of ``mag build``.  This
module owns the seam between that nondeterministic act and the deterministic
publication compiler:

* an authored YAML plan names the edition's visual direction and every asset;
* :func:`write_illustration_package` compiles that plan into exact prompts and
  a machine-readable inventory for whichever image tool the editor chooses;
* :func:`validate_illustration_plan` proves that the selected, committed PNGs
  are the same files the edition manifest declares.

The renderer therefore keeps its existing, deliberately small interface:
``tail_art_path`` and ``closing_plates[].art_path``.  It never learns about
models, prompts, retries, candidates, or editorial art direction.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from .errors import ValidationError
from .io import load_structured, safe_project_path
from .manifest import Edition


_ROLES = {"article_tail", "closing_plate"}
_TAIL_MINIMUM = (1536, 1024)
_PLATE_MINIMUM = (1024, 1400)


@dataclass(frozen=True)
class IllustrationDirection:
    name: str
    visual_language: str
    palette: str
    constraints: tuple[str, ...]
    avoid: tuple[str, ...]
    reference_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class IllustrationAsset:
    id: str
    role: str
    art_path: Path
    subject: str
    composition: str
    alt_text: str
    credit: str
    article_id: str | None = None
    plate_index: int | None = None


@dataclass(frozen=True)
class IllustrationPlan:
    path: Path
    direction: IllustrationDirection
    assets: tuple[IllustrationAsset, ...]
    direction_path: Path | None = None


def load_illustration_plan(root: Path, edition: Edition) -> IllustrationPlan | None:
    """Load the optional edition-owned illustration plan.

    Absence is ordinary for historical editions.  Once
    ``art_direction_path`` is declared, however, the plan is a build input and
    every field is strict: a half-authored plan must not silently become an
    untracked art workflow.
    """

    raw_path = edition.raw.get("art_direction_path")
    if not raw_path:
        return None
    path = safe_project_path(root, raw_path)
    if not path.is_file():
        raise ValidationError(f"Illustration plan not found: {path}")
    data = load_structured(path)
    if not isinstance(data, dict):
        raise ValidationError(f"Illustration plan must be a mapping: {path}")
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append(f"Illustration plan {path} requires schema_version: 1")
    direction_row = data.get("direction")
    direction_preset = data.get("direction_preset")
    direction_path: Path | None = None
    if direction_row is not None and direction_preset is not None:
        errors.append(
            f"Illustration plan {path} must declare direction or direction_preset, not both"
        )
        direction_row = {}
    elif direction_preset is not None:
        try:
            direction_path = safe_project_path(root, direction_preset)
        except ValidationError as exc:
            errors.extend(exc.errors)
            direction_row = {}
        else:
            if not direction_path.is_file():
                errors.append(
                    f"Illustration direction preset not found: {direction_path}"
                )
                direction_row = {}
            else:
                preset = load_structured(direction_path)
                if not isinstance(preset, dict):
                    errors.append(
                        f"Illustration direction preset must be a mapping: {direction_path}"
                    )
                    direction_row = {}
                else:
                    if preset.get("schema_version") != 1:
                        errors.append(
                            f"Illustration direction preset {direction_path} "
                            "requires schema_version: 1"
                        )
                    direction_row = preset.get("direction")
    if not isinstance(direction_row, dict):
        errors.append(
            f"Illustration plan {path} requires a direction mapping or direction_preset"
        )
        direction_row = {}
    direction_values: dict[str, str] = {}
    for key in ("name", "visual_language", "palette"):
        value = str(direction_row.get(key) or "").strip()
        if not value:
            errors.append(f"Illustration plan direction requires {key}")
        direction_values[key] = value
    constraints = _string_list(
        direction_row.get("constraints"), "direction.constraints", errors
    )
    avoid = _string_list(direction_row.get("avoid"), "direction.avoid", errors)
    reference_paths = _reference_paths(
        root,
        direction_row.get("reference_images"),
        errors,
    )

    rows = data.get("assets")
    if not isinstance(rows, list) or not rows:
        errors.append(f"Illustration plan {path} requires a non-empty assets list")
        rows = []
    assets: list[IllustrationAsset] = []
    ids: set[str] = set()
    paths: set[Path] = set()
    for index, row in enumerate(rows, start=1):
        label = f"Illustration asset {index}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        asset_id = str(row.get("id") or "").strip()
        role = str(row.get("role") or "").strip()
        if not asset_id:
            errors.append(f"{label} requires id")
        elif asset_id in ids:
            errors.append(f"Illustration asset id must be unique: {asset_id}")
        ids.add(asset_id)
        if role not in _ROLES:
            errors.append(
                f"{label} role must be article_tail or closing_plate, not {role!r}"
            )
        try:
            art_path = safe_project_path(
                root, row.get("art_path", ""), must_exist=False
            )
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        if art_path in paths:
            errors.append(f"Illustration art_path must be unique: {art_path}")
        paths.add(art_path)
        values: dict[str, str] = {}
        for key in ("subject", "composition", "alt_text", "credit"):
            value = str(row.get(key) or "").strip()
            if not value:
                errors.append(f"{label} requires {key}")
            values[key] = value
        article_id = str(row.get("article_id") or "").strip() or None
        plate_index: int | None = None
        if role == "article_tail":
            if not article_id:
                errors.append(f"{label} article_tail requires article_id")
            if row.get("plate_index") is not None:
                errors.append(f"{label} article_tail must not declare plate_index")
        elif role == "closing_plate":
            if article_id:
                errors.append(f"{label} closing_plate must not declare article_id")
            try:
                plate_index = int(row.get("plate_index"))
            except (TypeError, ValueError):
                errors.append(f"{label} closing_plate requires integer plate_index")
            if plate_index not in {1, 2, 3}:
                errors.append(f"{label} plate_index must be 1, 2, or 3")
        assets.append(
            IllustrationAsset(
                id=asset_id,
                role=role,
                art_path=art_path,
                subject=values["subject"],
                composition=values["composition"],
                alt_text=values["alt_text"],
                credit=values["credit"],
                article_id=article_id,
                plate_index=plate_index,
            )
        )
    if errors:
        raise ValidationError(errors)
    return IllustrationPlan(
        path=path,
        direction=IllustrationDirection(
            name=direction_values["name"],
            visual_language=direction_values["visual_language"],
            palette=direction_values["palette"],
            constraints=constraints,
            avoid=avoid,
            reference_paths=reference_paths,
        ),
        assets=tuple(assets),
        direction_path=direction_path,
    )


def validate_illustration_plan(root: Path, edition: Edition) -> IllustrationPlan | None:
    """Validate plan inventory, selected files, dimensions, and raster mode."""

    plan = load_illustration_plan(root, edition)
    if plan is None:
        return None
    errors = _inventory_errors(edition, plan)
    for asset in plan.assets:
        errors.extend(_review_raster(asset))
    if errors:
        raise ValidationError(errors)
    return plan


def _inventory_errors(
    edition: Edition, plan: IllustrationPlan
) -> list[str]:
    errors: list[str] = []
    planned_tails = {
        asset.article_id: asset
        for asset in plan.assets
        if asset.role == "article_tail"
    }
    declared_tails = {
        article.id: article.tail_art
        for article in edition.articles
        if article.tail_art is not None
    }
    if set(planned_tails) != set(declared_tails):
        missing = sorted(set(declared_tails) - set(planned_tails))
        extra = sorted(set(planned_tails) - set(declared_tails))
        if missing:
            errors.append(
                "Illustration plan is missing declared article tails: "
                + ", ".join(missing)
            )
        if extra:
            errors.append(
                "Illustration plan has undeclared article tails: " + ", ".join(extra)
            )
    for article_id in sorted(set(planned_tails) & set(declared_tails)):
        if planned_tails[article_id].art_path != declared_tails[article_id]:
            errors.append(
                f"Illustration plan path for {article_id} does not match "
                f"tail_art_path: {planned_tails[article_id].art_path}"
            )

    planned_plates = {
        asset.plate_index: asset
        for asset in plan.assets
        if asset.role == "closing_plate"
    }
    declared_plates = {
        index: plate.art_path
        for index, plate in enumerate(edition.closing_plates, start=1)
    }
    if set(planned_plates) != set(declared_plates):
        errors.append(
            "Illustration plan closing plates must match the edition's configured "
            f"indices exactly (planned {sorted(planned_plates)}, "
            f"declared {sorted(declared_plates)})"
        )
    for index in sorted(set(planned_plates) & set(declared_plates)):
        if planned_plates[index].art_path != declared_plates[index]:
            errors.append(
                f"Illustration plan path for closing plate {index} does not match "
                f"edition.yaml: {planned_plates[index].art_path}"
            )

    return errors


def illustration_prompt(plan: IllustrationPlan, asset: IllustrationAsset) -> str:
    """Compile one exact, reusable model prompt from edition direction + brief."""

    constraints = "\n".join(f"- {item}" for item in plan.direction.constraints)
    avoid = "\n".join(f"- {item}" for item in plan.direction.avoid)
    references = (
        "\nReference images:\n"
        + "\n".join(
            f"- {path.as_posix()}"
            for path in plan.direction.reference_paths
        )
        + "\nUse them only as visual-language, print-treatment, and composition "
        "references; never copy their characters or exact scenes."
        if plan.direction.reference_paths
        else ""
    )
    size = "1536x1024 landscape" if asset.role == "article_tail" else "1024x1536 portrait"
    slot = (
        "an article-tail illustration crop-filled into a variable-height 325pt-wide "
        "band; keep all essential action in the central horizontal third so both "
        "96pt and 214pt crops remain meaningful"
        if asset.role == "article_tail"
        else "a closing-plate illustration crop-filled above an editor-set title; "
        "the image must work alone because signature arithmetic may print only this plate"
    )
    return (
        "Use case: illustration-story\n"
        f"Asset type: {slot}\n"
        f"Output: exactly one wordless RGB PNG, {size}\n"
        f"Art direction: {plan.direction.name}\n"
        f"Visual language: {plan.direction.visual_language}\n"
        f"Palette: {plan.direction.palette}\n"
        f"{references}\n"
        f"Subject: {asset.subject}\n"
        f"Composition: {asset.composition}\n"
        "Constraints:\n"
        f"{constraints}\n"
        "Avoid:\n"
        f"{avoid}\n"
        "Do not add captions, speech balloons, letters, numbers, logos, QR codes, "
        "watermarks, mastheads, or cover lines."
    )


def write_illustration_package(
    root: Path,
    output_root: Path,
    edition: Edition,
) -> Path:
    """Write deterministic prompts and inventory; return the package directory."""

    plan = load_illustration_plan(root, edition)
    if plan is None:
        raise ValidationError(
            f"Edition {edition.id} declares no art_direction_path"
        )
    errors = _inventory_errors(edition, plan)
    if errors:
        raise ValidationError(errors)
    destination = output_root / edition.id / "illustration-prompts"
    destination.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, Any]] = []
    for asset in plan.assets:
        prompt = illustration_prompt(plan, asset)
        prompt_path = destination / f"{asset.id}.txt"
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        inventory.append(
            {
                "id": asset.id,
                "role": asset.role,
                "article_id": asset.article_id,
                "plate_index": asset.plate_index,
                "art_path": asset.art_path.relative_to(root).as_posix(),
                "prompt": prompt_path.name,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "image_sha256": (
                    _sha256(asset.art_path) if asset.art_path.is_file() else None
                ),
                "alt_text": asset.alt_text,
                "credit": asset.credit,
            }
        )
    payload = {
        "schema_version": 1,
        "edition_id": edition.id,
        "plan_path": plan.path.relative_to(root).as_posix(),
        "plan_sha256": _sha256(plan.path),
        "direction_preset": (
            {
                "path": plan.direction_path.relative_to(root).as_posix(),
                "sha256": _sha256(plan.direction_path),
            }
            if plan.direction_path is not None
            else None
        ),
        "reference_images": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path),
            }
            for path in plan.direction.reference_paths
        ],
        "assets": inventory,
    }
    (destination / "illustrations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _review_raster(asset: IllustrationAsset) -> list[str]:
    if not asset.art_path.is_file():
        return [f"Illustration asset is missing: {asset.art_path}"]
    try:
        with Image.open(asset.art_path) as image:
            width, height = image.size
            mode = image.mode
            format_name = image.format
    except Exception as exc:
        return [f"Illustration asset cannot be decoded: {asset.art_path} ({exc})"]
    errors: list[str] = []
    if format_name != "PNG":
        errors.append(f"Illustration asset must be PNG: {asset.art_path}")
    if mode not in {"RGB", "RGBA"}:
        errors.append(
            f"Illustration asset must be RGB or RGBA, not {mode}: {asset.art_path}"
        )
    minimum = _TAIL_MINIMUM if asset.role == "article_tail" else _PLATE_MINIMUM
    if width < minimum[0] or height < minimum[1]:
        errors.append(
            f"Illustration asset {asset.art_path} is {width}x{height}px; "
            f"{asset.role} requires at least {minimum[0]}x{minimum[1]}px"
        )
    if asset.role == "article_tail" and width <= height:
        errors.append(f"Article-tail illustration must be landscape: {asset.art_path}")
    if asset.role == "closing_plate" and height <= width:
        errors.append(f"Closing-plate illustration must be portrait: {asset.art_path}")
    return errors


def _string_list(value: Any, label: str, errors: list[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        errors.append(f"Illustration plan {label} must be a non-empty list")
        return ()
    normalized = tuple(str(item).strip() for item in value if str(item).strip())
    if len(normalized) != len(value):
        errors.append(f"Illustration plan {label} must contain non-empty strings")
    return normalized


def _reference_paths(
    root: Path,
    value: Any,
    errors: list[str],
) -> tuple[Path, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append("Illustration plan direction.reference_images must be a list")
        return ()
    references: list[Path] = []
    for raw_path in value:
        try:
            path = safe_project_path(root, raw_path)
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        if not path.is_file():
            errors.append(f"Illustration direction reference not found: {path}")
            continue
        references.append(path)
    if len(set(references)) != len(references):
        errors.append("Illustration direction reference_images must be unique")
    return tuple(references)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
