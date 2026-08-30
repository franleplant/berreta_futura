from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import io
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageEnhance, ImageOps


MIN_PRINT_CONTRAST_RATIO = 2.0
MIN_MARK_PIXEL_RATIO = 0.001


MAX_PRINT_CONTRAST_ENHANCEMENT = 3.0
_ANALYSIS_MAX_SIZE = (512, 512)
_CONTRAST_FACTORS = (1.4, 1.8, 2.2, 2.6, MAX_PRINT_CONTRAST_ENHANCEMENT)


_PAPER_CONTRAST_TOLERANCE = 1.08
_MARK_CONTRAST_THRESHOLD = 1.30
_MIN_BACKGROUND_LUMINANCE = 0.60
_MIN_BACKGROUND_MODE_RATIO = 0.18


_MAX_ENHANCEABLE_TINT_RATIO = 0.05


@dataclass(frozen=True)
class PrintContrastAnalysis:
    paper_pixel_ratio: float
    mark_pixel_ratio: float
    minimum_mark_contrast_ratio: float
    needs_treatment: bool

    def to_dict(self) -> dict[str, float | bool]:
        return asdict(self)


@dataclass(frozen=True)
class PreparedPrintImage:
    image: Path | io.BytesIO
    adjusted: bool
    before: PrintContrastAnalysis
    after: PrintContrastAnalysis

    @property
    def unresolved(self) -> bool:
        return self.after.needs_treatment


_SRGB_LINEAR = tuple(
    (value / 255) / 12.92
    if (value / 255) <= 0.04045
    else (((value / 255) + 0.055) / 1.055) ** 2.4
    for value in range(256)
)


def _relative_luminance(pixel: tuple[int, int, int]) -> float:
    return (
        0.2126 * _SRGB_LINEAR[pixel[0]]
        + 0.7152 * _SRGB_LINEAR[pixel[1]]
        + 0.0722 * _SRGB_LINEAR[pixel[2]]
    )


def _open_rgb(source: Path | BinaryIO | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if hasattr(source, "seek"):
        source.seek(0)
    with Image.open(source) as opened:
        return ImageOps.exif_transpose(opened).convert("RGB")


def _estimate_background_luminance(luminances: list[float]) -> float:
    total = len(luminances)
    histogram = [0] * 101
    for luminance in luminances:
        histogram[round(luminance * 100)] += 1

    def neighborhood(bin_index: int) -> int:
        mass = histogram[bin_index]
        if bin_index > 0:
            mass += histogram[bin_index - 1]
        if bin_index < 100:
            mass += histogram[bin_index + 1]
        return mass

    floor_bin = round(_MIN_BACKGROUND_LUMINANCE * 100)
    dominant = max(neighborhood(b) for b in range(floor_bin, 101))
    if dominant / total < _MIN_BACKGROUND_MODE_RATIO:
        return 1.0
    required = max(_MIN_BACKGROUND_MODE_RATIO * total, dominant / 2)
    for bin_index in range(100, floor_bin - 1, -1):
        if neighborhood(bin_index) >= required:
            low = max(0, bin_index - 1)
            high = min(100, bin_index + 1)
            weighted = sum(histogram[b] * (b / 100) for b in range(low, high + 1))
            mass = sum(histogram[b] for b in range(low, high + 1))
            return weighted / mass
    return 1.0


def analyze_print_contrast(source: Path | BinaryIO | Image.Image) -> PrintContrastAnalysis:
    image = _open_rgb(source)
    image.thumbnail(_ANALYSIS_MAX_SIZE, Image.Resampling.LANCZOS)
    pixels = list(image.get_flattened_data())
    total = len(pixels)
    if not total:
        return PrintContrastAnalysis(0.0, 0.0, 21.0, False)

    luminances = [_relative_luminance(pixel) for pixel in pixels]
    background = _estimate_background_luminance(luminances)
    paper_pixels = 0
    mark_contrasts = []
    for luminance in luminances:
        contrast = (background + 0.05) / (luminance + 0.05)
        if contrast <= _PAPER_CONTRAST_TOLERANCE:
            paper_pixels += 1
        elif contrast >= _MARK_CONTRAST_THRESHOLD:
            mark_contrasts.append(contrast)
    mark_contrasts.sort()
    mark_ratio = len(mark_contrasts) / total


    contrast = (
        mark_contrasts[len(mark_contrasts) // 2]
        if mark_contrasts
        else 21.0
    )
    paper_ratio = paper_pixels / total


    needs_treatment = (
        mark_ratio >= MIN_MARK_PIXEL_RATIO
        and contrast < MIN_PRINT_CONTRAST_RATIO
    )
    return PrintContrastAnalysis(
        round(paper_ratio, 6),
        round(mark_ratio, 6),
        round(contrast, 3),
        needs_treatment,
    )


@lru_cache(maxsize=64)
def _prepared_bytes(path_value: str) -> tuple[bytes | None, PrintContrastAnalysis, PrintContrastAnalysis]:
    path = Path(path_value)
    image = _open_rgb(path)
    before = analyze_print_contrast(image)
    if not before.needs_treatment:
        return None, before, before


    tint_ratio = 1.0 - before.paper_pixel_ratio - before.mark_pixel_ratio
    if tint_ratio >= _MAX_ENHANCEABLE_TINT_RATIO:
        return None, before, before


    best_candidate: Image.Image | None = None
    best_after = before
    for factor in _CONTRAST_FACTORS:
        candidate = ImageEnhance.Contrast(image).enhance(factor)
        candidate_after = analyze_print_contrast(candidate)
        if candidate_after.mark_pixel_ratio < MIN_MARK_PIXEL_RATIO:
            continue
        if (
            best_candidate is None
            or candidate_after.minimum_mark_contrast_ratio
            > best_after.minimum_mark_contrast_ratio
        ):
            best_candidate, best_after = candidate, candidate_after
        if best_after.minimum_mark_contrast_ratio >= MIN_PRINT_CONTRAST_RATIO:
            break
    if (
        best_candidate is None
        or best_after.minimum_mark_contrast_ratio
        <= before.minimum_mark_contrast_ratio
    ):
        return None, before, before
    output = io.BytesIO()
    best_candidate.save(output, format="PNG", optimize=False)
    return output.getvalue(), before, best_after


def prepare_print_image(path: Path) -> PreparedPrintImage:
    payload, before, after = _prepared_bytes(str(path.resolve()))
    if payload is None:
        return PreparedPrintImage(path, False, before, after)
    return PreparedPrintImage(io.BytesIO(payload), True, before, after)
