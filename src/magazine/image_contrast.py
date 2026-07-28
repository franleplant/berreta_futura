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
# The floor is calibrated against the MEDIAN mark, so it already tolerates
# mid-tone backgrounds and gradients as long as at least half of an image's
# marks carry printable ink; it is the one verdict the pipeline stands behind,
# and nothing — including how much paper an image shows — may excuse a figure
# from it. Edition 003 shipped a mid-tone diagram at a 1.261 median because an
# earlier paper-dominance exemption did exactly that.
MIN_PRINT_CONTRAST_RATIO = 2.0
MIN_MARK_PIXEL_RATIO = 0.001
# Contrast enhancement is a rescue, not a redesign. Up to 3.0x, PIL's
# midpoint-anchored contrast stretch deepens pale strokes while paper and
# near-paper tones stay put; beyond it, semantic mid-tones collapse toward
# black or white and the figure posterizes — edition 003 carried a visibly
# posterized 12x-enhanced diagram that still measured only 1.463. A figure
# that needs more than 3.0x is telling the editor to re-source it, so the
# ladder stops at the cap and the failure is reported instead.
MAX_PRINT_CONTRAST_ENHANCEMENT = 3.0
_ANALYSIS_MAX_SIZE = (512, 512)
_CONTRAST_FACTORS = (1.4, 1.8, 2.2, 2.6, MAX_PRINT_CONTRAST_ENHANCEMENT)

# Paper is whatever sheet the image was drawn on, not "pixels that are almost
# pure white". The old classifier keyed both classes to absolute channel
# values (paper: min channel >= 245, marks: min <= 235), so a warm cream
# background — min channel far below 245 even though the tone is nearly as
# light as the sheet — was counted wholesale as MARKS, its own tint became
# the "median mark", and perfectly legible dark-on-cream diagrams measured a
# false sub-2.0 verdict and got a visibly tint-saturating auto-crank. The
# classifier now estimates the image's own background (the lightest
# substantial luminance mode) and classifies every pixel by its WCAG-style
# contrast ratio against that background:
#
#   contrast <= _PAPER_CONTRAST_TOLERANCE   -> paper (the sheet, its JPEG
#                                               noise, and anything lighter)
#   contrast >= _MARK_CONTRAST_THRESHOLD    -> a deliberate mark, measured
#                                               against ITS background
#   in between                              -> tint: pale fills and shading
#                                               that are neither sheet nor ink
#
# A background darker than _MIN_BACKGROUND_LUMINANCE is not paper anything
# can print against, and a mode thinner than _MIN_BACKGROUND_MODE_RATIO is
# artwork rather than a sheet; both fall back to white, which reproduces the
# old absolute behaviour for photographs and dark-field images.
_PAPER_CONTRAST_TOLERANCE = 1.08
_MARK_CONTRAST_THRESHOLD = 1.30
_MIN_BACKGROUND_LUMINANCE = 0.60
_MIN_BACKGROUND_MODE_RATIO = 0.18
# Enhancement is only honest for figures whose tones split cleanly into sheet
# and strokes. When a substantial share of pixels sits in the tint band
# between the two cuts, those tones are semantic — pastel panel fills, soft
# shading, placeholder bars — and a global contrast stretch either washes
# them out toward paper or crushes them toward ink; the median may "improve"
# while the artwork visibly degrades — the same pathology as the
# tint-saturating auto-crank above. Such figures ship their original bytes and
# keep the unresolved verdict: the fix is re-sourcing, not more contrast.
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
        """True when the shipped image still fails the print floor.

        ``after`` always describes the bytes in ``image``, so this is a plain
        restatement of its verdict — there is no second heuristic that can
        overrule a measured failure. An unresolved figure may well be
        unadjusted: when no enhancement rung honestly improves the median (or
        the figure's pale fills forbid enhancement altogether), the original
        bytes are the least-bad image and they ship unchanged.
        """
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
    """Return the luminance of the sheet the image was drawn on.

    The background is the LIGHTEST substantial luminance mode: histogram the
    luminances into percent bins, find how massive the biggest light mode is,
    then walk from white downward and take the first mode that is at least
    half that size (and no thinner than ``_MIN_BACKGROUND_MODE_RATIO``).
    Preferring the lightest qualifying mode over the single biggest one keeps
    a large pastel content panel from stealing the sheet's role when the page
    around it is plainly white. When nothing light and substantial exists —
    photographs, dark-field plates — white is assumed, which reproduces the
    previous absolute measurement for exactly those images.
    """
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
    """Measure whether an image's marks will hold up in print."""
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
    # Use the median mark rather than the lightest anti-aliased fringe. A few
    # dark labels still cannot hide a mostly faint diagram because those labels
    # do not make up half of its mark pixels.
    contrast = (
        mark_contrasts[len(mark_contrasts) // 2]
        if mark_contrasts
        else 21.0
    )
    paper_ratio = paper_pixels / total
    # The verdict is the measurement, nothing else: enough marks to matter,
    # median mark below the floor. Paper dominance is still reported as a
    # diagnostic, but it gates nothing — the old `paper_ratio >= 0.70`
    # precondition exempted every mid-tone figure from the floor, and worse,
    # enhancement itself could push a treated image's paper ratio under the
    # threshold, silently converting a measured failure into a pass.
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

    # Figures that lean on tint — pale fills and shading between the paper
    # and mark cuts — cannot be rescued by a global stretch without visibly
    # degrading exactly those tones, so they ship untouched and unresolved.
    tint_ratio = 1.0 - before.paper_pixel_ratio - before.mark_pixel_ratio
    if tint_ratio >= _MAX_ENHANCEABLE_TINT_RATIO:
        return None, before, before

    # Walk the ladder and keep the BEST-measuring rung, not the last one. Two
    # honesty rules bound the walk: a rung whose mark population collapsed
    # below the floor did not fix the marks — it bleached them into paper, a
    # measured failure that must never default to the healthy 21.0 — and when
    # no rung improves on the untreated median, the original bytes ARE the
    # closest we can honestly get, so they ship unchanged and ``after`` keeps
    # the measured pre-treatment verdict for downstream preflight to report.
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
    """Return the source unchanged, or a deterministic in-memory derivative.

    A returned derivative is print-safe when ``after`` clears the floor; when
    no enhancement honestly improves the figure — the ladder found nothing
    better, or the figure's pale fills forbid a global stretch — the original
    bytes ship, ``unresolved`` is True, and the editor should re-source the
    artwork rather than reprocess it.
    """
    payload, before, after = _prepared_bytes(str(path.resolve()))
    if payload is None:
        return PreparedPrintImage(path, False, before, after)
    return PreparedPrintImage(io.BytesIO(payload), True, before, after)
