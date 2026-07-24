from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import io
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageEnhance, ImageOps


# A 2:1 median-mark ratio is a conservative print floor for non-text imagery:
# enough to survive uncoated paper and office printers without recoloring
# already healthy photographs or turning pale semantic fills into solid ink.
MIN_PRINT_CONTRAST_RATIO = 2.0
PAPER_DOMINANT_RATIO = 0.70
MIN_MARK_PIXEL_RATIO = 0.001
_ANALYSIS_MAX_SIZE = (512, 512)
_CONTRAST_FACTORS = (1.4, 1.8, 2.2, 2.8, 3.5, 4.5, 6.0, 8.0, 12.0)


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


def _relative_luminance(pixel: tuple[int, int, int]) -> float:
    channels = []
    for value in pixel:
        normalized = value / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _open_rgb(source: Path | BinaryIO | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if hasattr(source, "seek"):
        source.seek(0)
    with Image.open(source) as opened:
        return ImageOps.exif_transpose(opened).convert("RGB")


def analyze_print_contrast(source: Path | BinaryIO | Image.Image) -> PrintContrastAnalysis:
    """Measure whether marks in paper-dominant line art will hold up in print."""
    image = _open_rgb(source)
    image.thumbnail(_ANALYSIS_MAX_SIZE, Image.Resampling.LANCZOS)
    pixels = list(image.get_flattened_data())
    total = len(pixels)
    if not total:
        return PrintContrastAnalysis(0.0, 0.0, 21.0, False)

    paper_pixels = sum(1 for red, green, blue in pixels if min(red, green, blue) >= 245)
    mark_contrasts = sorted(
        (1.05 / (_relative_luminance(pixel) + 0.05))
        for pixel in pixels
        if min(pixel) <= 235
    )
    mark_ratio = len(mark_contrasts) / total
    # Use the median mark rather than the lightest anti-aliased fringe. A few
    # dark labels still cannot hide a mostly faint diagram because those labels
    # do not make up half of its mark pixels.
    contrast = (
        mark_contrasts[len(mark_contrasts) // 2]
        if mark_contrasts
        else 21.0
    )
    paper_ratio = paper_pixels / total
    needs_treatment = (
        paper_ratio >= PAPER_DOMINANT_RATIO
        and mark_ratio >= MIN_MARK_PIXEL_RATIO
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

    treated = image
    after = before
    for factor in _CONTRAST_FACTORS:
        candidate = ImageEnhance.Contrast(image).enhance(factor)
        candidate_after = analyze_print_contrast(candidate)
        treated, after = candidate, candidate_after
        if after.minimum_mark_contrast_ratio >= MIN_PRINT_CONTRAST_RATIO:
            break
    output = io.BytesIO()
    treated.save(output, format="PNG", optimize=False)
    return output.getvalue(), before, after


def prepare_print_image(path: Path) -> PreparedPrintImage:
    """Return the source unchanged, or a deterministic print-safe in-memory derivative."""
    payload, before, after = _prepared_bytes(str(path.resolve()))
    if payload is None:
        return PreparedPrintImage(path, False, before, after)
    return PreparedPrintImage(io.BytesIO(payload), True, before, after)
