"""Artistic source codes: an authored artwork pass over the article-tail QR.

The plain source code is furniture the build manufactures on its own
(``weasyprint_adapter._source_code_source``); this module is the *authored*
pass that function's docstring reserved space for.  An editor runs ``mag
source-art <edition-id>`` once per edition, an image model composes hard-edged
cover-grammar shapes around each article's true QR symbol, and everything the
model touched is then judged by machines: the symbol must decode to the
article's canonical URL character for character, at the sizes the tail slot can
actually print, in grayscale as well as colour, inside the cover ink set, with
signal orange held under its five percent, with every dark module set in INK so
a monochrome printer cannot screen a finder, with the quiet zone genuinely
quiet, and with the label's own band left as clear paper.  A candidate that
fails any of that is thrown away and regenerated; an article whose attempts run
out keeps the plain vector code, because a build must never wait on aesthetics.

Two halves live here on purpose.  The *measurement* half
(:func:`measure_source_code_art`) is shared with the build: the print adapter
re-measures the committed PNG on every plan pass, so the placed box, the
label's position, and the final decode gate all derive from the artwork itself
rather than from anything this command recorded about it.  There is no sidecar
to trust and none to go stale.  The *authoring* half
(:func:`generate_source_art`) is the only nondeterministic step in the
publication and it runs at author time, never at build time: the build consumes
whatever PNG the edition committed, byte for byte -- and re-judges its ink
discipline (:func:`review_source_code_inks`) on every plan pass, so an artwork
edited after acceptance is refused by the build that would have printed it.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .errors import DependencyError, MagazineError, ValidationError

if TYPE_CHECKING:
    from .manifest import Article, Edition

# The cover ink set (docs/DESIGN_SYSTEM.md, "Cover artwork"), which is also the
# artwork's whole permitted palette.  The unprinted sheet leads because it is
# the artwork's GROUND: the canvas must read as the page itself, not as a
# tinted rectangle pasted onto it, so pure white is the ground and the warm
# paper survives only as a shape colour.
ART_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0xF1, 0xEA, 0xDB),  # warm paper (a shape colour, never the ground)
    (0x11, 0x13, 0x1A),  # near-black ink
    (0x53, 0x32, 0xC8),  # ultraviolet
    (0xFF, 0x5A, 0x1F),  # signal orange
    (0xFF, 0xFF, 0xFF),  # unprinted sheet: the ground
)
_PAPER_INDEX = 0
_ORANGE_INDEX = 3
_WHITE_INDEX = 4
_LIGHT_INDICES = (_PAPER_INDEX, _WHITE_INDEX)
_INK = (0x11, 0x13, 0x1A)

# Euclidean RGB distance within which a pixel counts as one of the inks, and
# the share of pixels that must be within it.  Hard-edged fields at 1024px put
# only their antialiased edges outside the set; a wash, a gradient or a
# photograph puts most of itself outside.
ART_PALETTE_TOLERANCE = 60.0
ART_MIN_PALETTE_SHARE = 0.97
# Signal orange stays under five percent of the artwork area, as on the cover.
ART_MAX_ORANGE_SHARE = 0.05
# Within the symbol's own footprint, dark pixels must be INK: a violet module
# survives this room's colour decode and then halftones into holes on the
# monochrome printer the magazine is actually made on.
ART_MIN_INK_MODULE_SHARE = 0.98
_DARK_LUMINANCE = 128

# THE QUIET ZONE IS MEASURED, NOT ASSUMED.  A ring four modules wide around the
# symbol's measured footprint -- the QR standard's own quiet zone, its width
# derived from the ink span divided by the symbol's actual module count -- must
# be paper or sheet.  A shape one module from the ink decodes on a phone held
# square over a clean print and then fails on the same phone held at an angle
# over a creased one, which is exactly the print this magazine is.  The ring
# must also lie entirely inside the canvas: a symbol whose quiet zone runs off
# the edge borrows it from whatever the page puts there.
ART_QUIET_ZONE_MODULES = 4
ART_MIN_QUIET_LIGHT_SHARE = 0.99

# THE GROUND GATE, which is what kills the sticker.  The artwork prints on the
# white sheet, so a canvas whose ground is the warm paper sits on the page as a
# visibly tinted pasted rectangle.  Judged at the canvas borders, where ground
# is what shows: within a band ``ART_GROUND_BAND_FRACTION`` of the canvas width
# along all four edges, at least ``ART_MIN_GROUND_WHITE_SHARE`` of the pixels
# must classify as the unprinted sheet (nearest palette ink, within tolerance),
# and at most ``ART_MAX_GROUND_PAPER_SHARE`` as the warm paper.  Shapes may
# still reach the edges -- half the band is theirs -- but the sheet must show
# through, and the warm paper may never masquerade as it.  The paper cap is
# measured, not tasted: a warm-paper *ground* puts 50%+ of the band in paper
# (the retired warm-canvas artwork measured 51.9%), while a genuine warm shape
# touching a corner measured 14.4%; 20% stands in the gap and would classify
# both the same anywhere between 15% and 50%.
ART_GROUND_BAND_FRACTION = 0.04
ART_MIN_GROUND_WHITE_SHARE = 0.40
ART_MAX_GROUND_PAPER_SHARE = 0.20

# THE LABEL BAND.  The build sets ``SOURCE / nn`` on the symbol's own bottom
# edge, one gap to the right of its last dark module -- inside the canvas, over
# whatever the artwork put there.  So the artwork must put paper there: from
# the symbol's right edge to the canvas's own right edge, over the label's
# metric height above the symbol's foot, at least this share of pixels must be
# light.  The band's fractional geometry is computed against the smallest
# square the tail slot can award, which is where the label is fractionally
# largest; see ``_label_band_box``.
ART_MIN_LABEL_BAND_LIGHT_SHARE = 0.99

# The symbol's dark modules must span at least this fraction of the canvas --
# the build's position gate (`_code_box_matches`) demands half the placed box,
# and this margin keeps downscale rounding from ever dipping under it -- and at
# most this much, or there is no artwork to speak of.  WHERE it stands is the
# composition's own business: the build places and labels the symbol off the
# *measured* footprint, so the symbol may sit anywhere that keeps the full
# quiet zone and the label band inside the canvas.  Centring was once required
# here and bought nothing but perimeter decoration.
ART_MIN_SYMBOL_FRACTION = 0.55
ART_MAX_SYMBOL_FRACTION = 0.85

# The largest square the tail slot can ever place is the retired ornament's own
# 214pt maximum, and the artwork must carry 300 ppi there: ceil(214/72*300).
ART_MIN_PIXELS = 892
# The decode gate's print simulation: the nominal tail code (41.65mm at
# 300 ppi) and the smallest square the tail slot can award (twice the foot
# room, ~81.7pt).  Each is read in colour and in grayscale, because the reader
# is printed on a monochrome device.
ART_DECODE_PIXEL_SIZES = (492, 341)

DEFAULT_SOURCE_ART_MODEL = "gpt-5.5"
DEFAULT_SOURCE_ART_ATTEMPTS = 3
_CODEX_TIMEOUT_SECONDS = 600


class GenerationError(MagazineError):
    """One generation attempt failed to run (timeout, crash, bad exit).

    Raised by the runner and caught by the attempt loop: a generator that
    stumbles costs one attempt and the next one proceeds, because an edition's
    authoring session must not abort on a transient model failure.  A *missing*
    generator is still :class:`DependencyError` and still aborts -- retrying
    cannot install a CLI.
    """


@dataclass(frozen=True)
class SymbolMeasurement:
    """Where the QR symbol actually stands inside a committed artwork.

    ``box`` is the symbol's dark-module footprint as fractions of the square
    canvas -- left, top, right, bottom in image coordinates, y down -- read
    back by the same independent decoder the build gate uses.  ``modules`` is
    the symbol's own width in modules (no quiet zone), read from the decoded
    symbol's version, so the module arithmetic the build does -- the quiet
    ring's width, the printed cell's size against the 0.35mm floor -- derives
    from the symbol the artwork actually carries and not from whatever symbol
    the plain code would have fitted.  Everything the print adapter needs to
    place the artwork derives from this: no sidecar records the geometry, so
    none can go stale against the pixels.
    """

    payload: str
    box: tuple[float, float, float, float]
    pixels: int
    modules: int

    @property
    def fraction(self) -> float:
        left, top, right, bottom = self.box
        return max(right - left, bottom - top)


_MEASUREMENTS: dict[tuple[str, int, int], SymbolMeasurement] = {}
_INK_REVIEWS: dict[tuple[str, int, int], tuple[str, ...]] = {}


def _file_key(path: Path) -> tuple[str, int, int]:
    try:
        stat = path.stat()
    except OSError as exc:
        raise ValidationError(f"Source code artwork cannot be read: {path} ({exc})") from exc
    return (str(path), stat.st_mtime_ns, stat.st_size)


def measure_source_code_art(path: Path) -> SymbolMeasurement:
    """Decode the artwork's symbol and report its footprint, or refuse.

    Refusals are :class:`ValidationError` with the file named, because every
    caller -- the authoring gate and the build's plan pass -- treats an
    unmeasurable artwork as a fault in the declared input, never as "no art".
    Measurements are cached against the file's identity; the build re-measures
    the same PNG on every settle pass and the answer cannot differ.
    """
    from PIL import Image

    key = _file_key(path)
    cached = _MEASUREMENTS.get(key)
    if cached is not None:
        return cached
    try:
        with Image.open(path) as raw:
            image = raw.convert("RGB")
    except Exception as exc:  # Pillow's failures differ by format.
        raise ValidationError(f"Source code artwork cannot be decoded: {path} ({exc})") from exc
    width, height = image.size
    if width != height:
        raise ValidationError(
            f"Source code artwork must be square, and {path} is {width}x{height}px; "
            "the tail slot places a square."
        )
    decoded = _read_symbols(image)
    if len(decoded) != 1:
        raise ValidationError(
            f"Source code artwork {path} carries {len(decoded)} decodable QR symbols; "
            "exactly one is the artwork's contract, because the page gate matches "
            "one symbol to one placed square."
        )
    text, corners, modules = decoded[0]
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    box = (
        min(xs) / width,
        min(ys) / height,
        (max(xs) + 1) / width,
        (max(ys) + 1) / height,
    )
    measurement = SymbolMeasurement(text, box, width, modules)
    _MEASUREMENTS[key] = measurement
    return measurement


def _read_symbols(image: Any) -> list[tuple[str, tuple[tuple[float, float], ...], int]]:
    """Every QR symbol an independent reader finds: text, pixel corners (y
    down), and the symbol's width in modules.

    The module count comes from the decoded symbol itself -- zxing reports the
    QR version, and a version-``v`` symbol is ``17 + 4v`` modules across -- so
    it describes the symbol the artwork actually carries, whatever error
    correction level generated it.  Where a build of zxing does not report the
    version, the count is recovered by re-encoding the payload at the reported
    error correction level, which reproduces the minimal-version symbol the
    reference generator emits.
    """
    try:
        import zxingcpp
    except ImportError as exc:  # pragma: no cover - a declared dependency
        raise ValidationError(
            "Judging source code artwork requires zxing-cpp. Run `uv sync --locked`. "
            f"Original error: {exc}"
        ) from exc
    results = []
    for found in zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode):
        position = found.position
        corners = tuple(
            (float(point.x), float(point.y))
            for point in (
                position.top_left,
                position.top_right,
                position.bottom_right,
                position.bottom_left,
            )
        )
        results.append((found.text, corners, _symbol_modules(found)))
    return results


def _symbol_modules(found: Any) -> int:
    extra = getattr(found, "extra", None) or {}
    version = extra.get("Version")
    if version is not None:
        try:
            return 17 + 4 * int(version)
        except (TypeError, ValueError):
            pass
    import segno

    level = str(getattr(found, "ec_level", "") or "H")
    symbol = segno.make(found.text, error=level, micro=False)
    return int(symbol.symbol_size(border=0)[0])


def review_source_code_art(path: Path, url: str) -> list[str]:
    """Every reason this artwork cannot stand in a tail slot; empty means accepted.

    This is the acceptance gate the authoring command runs on each candidate,
    and the tests' definition of "accepted".  It is deliberately a *list* of
    sentences rather than a boolean: the command reports why an attempt was
    thrown away, and the difference between "off palette" and "does not decode
    at print size" is what an editor tunes the next attempt with.
    """
    from PIL import Image

    try:
        measurement = measure_source_code_art(path)
    except ValidationError as exc:
        return list(exc.errors)
    failures: list[str] = []
    if measurement.payload != url:
        failures.append(
            f"the symbol decodes to {measurement.payload!r}, not the article's "
            f"canonical URL {url!r}"
        )
    if measurement.pixels < ART_MIN_PIXELS:
        failures.append(
            f"the canvas is {measurement.pixels}px wide and the largest tail square "
            f"needs {ART_MIN_PIXELS}px to hold 300 ppi"
        )
    if not ART_MIN_SYMBOL_FRACTION <= measurement.fraction <= ART_MAX_SYMBOL_FRACTION:
        failures.append(
            f"the symbol spans {measurement.fraction:.2f} of the canvas; the contract "
            f"is {ART_MIN_SYMBOL_FRACTION:.2f} to {ART_MAX_SYMBOL_FRACTION:.2f}, so the "
            "placed square always contains a symbol the page gate can match"
        )
    with Image.open(path) as raw:
        image = raw.convert("RGB")
    for size in ART_DECODE_PIXEL_SIZES:
        if size >= measurement.pixels:
            continue
        printed = image.resize((size, size), Image.LANCZOS)
        for label, sample in (("colour", printed), ("grayscale", printed.convert("L"))):
            found = [text for text, _corners, _modules in _read_symbols(sample)]
            if found != [url]:
                failures.append(
                    f"at {size}px -- a printed tail square at 300 ppi -- the {label} "
                    f"raster decodes to {found!r} instead of the URL"
                )
    failures.extend(review_source_code_inks(path))
    return failures


def review_source_code_inks(path: Path) -> list[str]:
    """The ink-discipline half of the gate, re-runnable by the build.

    Palette conformance, the orange budget, ink-only modules, the quiet ring,
    the ground gate and the label band -- everything about the artwork that can
    be vandalised after acceptance without breaking the decode.  The print
    adapter calls this on every plan pass (``_dressed_source_code``), so a
    committed PNG edited into violet modules or a dirtied quiet zone refuses
    the build instead of halftoning into holes on the printed page.  Cached
    against the file's identity, like the measurement, because the build asks
    several times per settle and the pixels cannot have changed.
    """
    measurement = measure_source_code_art(path)
    key = _file_key(path)
    cached = _INK_REVIEWS.get(key)
    if cached is None:
        from PIL import Image

        with Image.open(path) as raw:
            image = raw.convert("RGB")
        cached = tuple(_review_inks(image, measurement))
        _INK_REVIEWS[key] = cached
    return list(cached)


def _review_inks(image: Any, measurement: SymbolMeasurement) -> list[str]:
    """Palette, orange budget, ink modules, quiet ring, ground and label band.

    Statistics are read off a nearest-neighbour thumbnail: resampling that
    blended pixels would manufacture off-palette colours the artwork does not
    contain, and the shares being judged are area shares, which a uniform
    subsample preserves.
    """
    from PIL import Image

    sample = (
        image
        if image.width <= 512
        else image.resize((512, 512), Image.NEAREST)
    )
    width, height = sample.width, sample.height
    data = sample.tobytes()
    total = width * height
    tolerance_squared = ART_PALETTE_TOLERANCE**2
    # Nearest palette ink per pixel, or -1 outside the tolerance, computed once
    # and shared by every area gate below.
    classes = bytearray(total)  # palette index + 1; 0 means off-palette
    for offset, (red, green, blue) in enumerate(
        zip(data[0::3], data[1::3], data[2::3])
    ):
        best = None
        best_index = 0
        for index, (pr, pg, pb) in enumerate(ART_PALETTE):
            distance = (red - pr) ** 2 + (green - pg) ** 2 + (blue - pb) ** 2
            if best is None or distance < best:
                best, best_index = distance, index
        if best is not None and best <= tolerance_squared:
            classes[offset] = best_index + 1
    conforming = total - classes.count(0)
    orange = classes.count(_ORANGE_INDEX + 1)
    failures: list[str] = []
    if conforming / total < ART_MIN_PALETTE_SHARE:
        failures.append(
            f"only {conforming / total:.1%} of the artwork is within the cover ink "
            f"set (paper, ink, violet, orange); at least "
            f"{ART_MIN_PALETTE_SHARE:.0%} must be"
        )
    if orange / total > ART_MAX_ORANGE_SHARE:
        failures.append(
            f"signal orange covers {orange / total:.1%} of the artwork; the cover "
            f"grammar holds it under {ART_MAX_ORANGE_SHARE:.0%}"
        )
    failures.extend(_review_ground(classes, width, height))
    failures.extend(_review_symbol_ink(sample, measurement, tolerance_squared))
    failures.extend(_review_quiet_ring(classes, width, height, measurement))
    failures.extend(_review_label_band(classes, width, height, measurement))
    return failures


def _review_ground(classes: bytearray, width: int, height: int) -> list[str]:
    """The ground gate: the canvas borders must read as the unprinted sheet.

    See ``ART_GROUND_BAND_FRACTION`` for the definition.  The band is judged on
    palette classes so "white" means "nearest ink is the sheet", which the
    tolerance keeps distinct from the warm paper even though the two are only
    44 RGB units apart.
    """
    band = max(2, round(ART_GROUND_BAND_FRACTION * width))
    counted = 0
    white = 0
    paper = 0
    for y in range(height):
        edge_row = y < band or y >= height - band
        for x in range(width):
            if not (edge_row or x < band or x >= width - band):
                continue
            counted += 1
            klass = classes[y * width + x] - 1
            if klass == _WHITE_INDEX:
                white += 1
            elif klass == _PAPER_INDEX:
                paper += 1
    if not counted:
        return []
    problems: list[str] = []
    if white / counted < ART_MIN_GROUND_WHITE_SHARE:
        problems.append(
            f"only {white / counted:.1%} of the canvas border band is the unprinted "
            f"sheet (#FFFFFF); at least {ART_MIN_GROUND_WHITE_SHARE:.0%} must be, so "
            "the artwork's ground reads as the page and not as a pasted rectangle"
        )
    if paper / counted > ART_MAX_GROUND_PAPER_SHARE:
        problems.append(
            f"warm paper (#F1EADB) covers {paper / counted:.1%} of the canvas border "
            f"band, over the {ART_MAX_GROUND_PAPER_SHARE:.0%} that keeps it a shape "
            "colour rather than a tinted ground"
        )
    return problems


def _review_symbol_ink(
    sample: Any, measurement: SymbolMeasurement, tolerance_squared: float
) -> list[str]:
    """Within the symbol's footprint, dark pixels must be INK; see module head."""
    left, top, right, bottom = measurement.box
    crop = sample.crop((
        int(left * sample.width),
        int(top * sample.height),
        int(right * sample.width),
        int(bottom * sample.height),
    ))
    dark = 0
    inked = 0
    crop_data = crop.tobytes()
    for red, green, blue in zip(crop_data[0::3], crop_data[1::3], crop_data[2::3]):
        if 0.299 * red + 0.587 * green + 0.114 * blue >= _DARK_LUMINANCE:
            continue
        dark += 1
        distance = (red - _INK[0]) ** 2 + (green - _INK[1]) ** 2 + (blue - _INK[2]) ** 2
        if distance <= tolerance_squared:
            inked += 1
    if dark and inked / dark < ART_MIN_INK_MODULE_SHARE:
        return [
            f"only {inked / dark:.1%} of the symbol's dark modules are set in INK; "
            "a violet or orange module decodes in this room and then halftones "
            "into holes on a monochrome printer"
        ]
    return []


def _review_quiet_ring(
    classes: bytearray, width: int, height: int, measurement: SymbolMeasurement
) -> list[str]:
    """The four-module quiet zone, measured as the ring it is; see module head."""
    left, top, right, bottom = measurement.box
    module = measurement.fraction / measurement.modules
    ring = ART_QUIET_ZONE_MODULES * module
    outer = (left - ring, top - ring, right + ring, bottom + ring)
    slack = 1.0 / width  # half a thumbnail pixel of decoder slack, doubled
    if (
        outer[0] < -slack
        or outer[1] < -slack
        or outer[2] > 1.0 + slack
        or outer[3] > 1.0 + slack
    ):
        return [
            f"the symbol's {ART_QUIET_ZONE_MODULES}-module quiet zone runs off the "
            "canvas edge; the artwork must carry the whole quiet zone itself rather "
            "than borrow it from the page"
        ]
    import math

    x0 = max(0, int(outer[0] * width))
    y0 = max(0, int(outer[1] * height))
    x1 = min(width, math.ceil(outer[2] * width))
    y1 = min(height, math.ceil(outer[3] * height))
    bx0, by0 = int(left * width), int(top * height)
    bx1, by1 = math.ceil(right * width), math.ceil(bottom * height)
    counted = 0
    light = 0
    for y in range(y0, y1):
        inside_rows = by0 <= y < by1
        for x in range(x0, x1):
            if inside_rows and bx0 <= x < bx1:
                continue
            counted += 1
            if classes[y * width + x] - 1 in _LIGHT_INDICES:
                light += 1
    if counted and light / counted < ART_MIN_QUIET_LIGHT_SHARE:
        return [
            f"only {light / counted:.1%} of the symbol's {ART_QUIET_ZONE_MODULES}-"
            f"module quiet zone is paper or sheet; at least "
            f"{ART_MIN_QUIET_LIGHT_SHARE:.0%} must be, because a shape one module "
            "from the ink fails the very scan the print exists for"
        ]
    return []


def _label_band_box(
    measurement: SymbolMeasurement,
) -> tuple[float, float, float, float]:
    """Where the printed label may land on the canvas, in canvas fractions.

    The build sets the label's left edge one ``_CODE_LABEL_GAP_POINTS`` right
    of the symbol's last dark module and its baseline
    ``_ZERO_LEADING_SANS_BASELINE`` above the symbol's bottom edge, in
    ``_CODE_LABEL_SIZE_POINTS`` caps -- all in points of the *printed* square,
    whose smallest tail size is ``_CODE_TAIL_MIN_ROOM_POINTS``.  The band is
    computed against that smallest square, where the label occupies the largest
    fraction of the canvas, so an artwork accepted here is clear under every
    placement the slot can award.  The text's own width is unknowable at
    acceptance time (it is localized at build time), so the band runs to the
    canvas's right edge; beyond the canvas the label stands on the page's own
    paper, which needs no gate.
    """
    from .weasyprint_adapter import (
        _CODE_LABEL_SIZE_POINTS,
        _CODE_TAIL_MIN_ROOM_POINTS,
        _ZERO_LEADING_SANS_BASELINE,
    )

    _left, _top, right, bottom = measurement.box
    rise = (
        _ZERO_LEADING_SANS_BASELINE + _CODE_LABEL_SIZE_POINTS
    ) / _CODE_TAIL_MIN_ROOM_POINTS
    return (right, max(0.0, bottom - rise), 1.0, bottom)


def _review_label_band(
    classes: bytearray, width: int, height: int, measurement: SymbolMeasurement
) -> list[str]:
    """The label band must be paper: type never prints over artwork ink."""
    import math

    left, top, right, bottom = _label_band_box(measurement)
    x0, x1 = int(left * width), width if right >= 1.0 else int(right * width)
    y0, y1 = int(top * height), min(height, math.ceil(bottom * height))
    counted = 0
    light = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            counted += 1
            if classes[y * width + x] - 1 in _LIGHT_INDICES:
                light += 1
    if counted and light / counted < ART_MIN_LABEL_BAND_LIGHT_SHARE:
        return [
            f"only {light / counted:.1%} of the label band -- right of the symbol, "
            "on its bottom edge, where the build sets the printed SOURCE label -- "
            f"is paper or sheet; at least {ART_MIN_LABEL_BAND_LIGHT_SHARE:.0%} must "
            "be, because type never prints over artwork ink"
        ]
    return []


# ---------------------------------------------------------------------------
# The authoring command.
# ---------------------------------------------------------------------------


def generate_source_art(
    root: Path,
    edition: "Edition",
    *,
    articles: Iterable[str] = (),
    regenerate: bool = False,
    model: str = DEFAULT_SOURCE_ART_MODEL,
    attempts: int = DEFAULT_SOURCE_ART_ATTEMPTS,
    runner: Callable[[list[str], Path], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> list[str]:
    """Generate, judge, and save artwork for every article that can carry one.

    Returns the report the CLI prints: one line per article naming what
    happened, followed by pastable YAML for each ``source_code_art_path``
    declaration.  The command never edits the manifest itself -- the edition
    directory is authored space, and declaring the artwork is the editor's
    decision, made file by file.

    ``runner`` is the seam the tests stand a stub in: it receives the assembled
    ``codex`` command and the working directory the candidate must appear in.
    The default runner requires the real ``codex`` CLI and fails with an
    actionable message, not a traceback, when it is missing -- but it is built
    lazily, on the first article that actually needs generating, so an edition
    whose artwork is already accepted reports without demanding the CLI at all.
    """
    say = log or (lambda _line: None)
    if attempts < 1:
        raise ValidationError("--attempts must be at least 1")
    wanted = set(articles)
    known = {article.id for article in edition.articles}
    unknown = sorted(wanted - known)
    if unknown:
        raise ValidationError(
            f"Edition {edition.id} has no article {', '.join(unknown)}"
        )
    generate = runner

    def invoke(command: list[str], cwd: Path) -> None:
        nonlocal generate
        if generate is None:
            generate = _codex_runner()
        generate(command, cwd)

    art_dir = root / "editions" / edition.id / "art" / "source-codes"
    work_root = root / "output" / ".source-art" / edition.id
    report: list[str] = []
    declarations: list[tuple[str, Path]] = []
    for article in edition.articles:
        if wanted and article.id not in wanted:
            continue
        url = (article.source_url or "").strip()
        if not url:
            report.append(f"{article.id}: no canonical source URL, no code, no art")
            continue
        destination = art_dir / f"{article.id}.png"
        if destination.is_file() and not regenerate:
            failures = review_source_code_art(destination, url)
            if failures:
                report.append(
                    f"{article.id}: existing artwork no longer passes the gate "
                    f"({'; '.join(failures)}); rerun with --regenerate"
                )
            else:
                report.append(f"{article.id}: artwork already accepted at {destination.relative_to(root).as_posix()}")
                declarations.append((article.id, destination))
            continue
        say(f"{article.id}: composing artwork for {url}")
        accepted, tried, last_failures = _attempt_article(
            article, url, work_root / article.id, invoke, attempts, model, say
        )
        if accepted is None:
            report.append(
                f"{article.id}: no candidate passed the acceptance gate in {tried} "
                f"attempt(s); the article keeps the plain vector code. Last failures: "
                + ("; ".join(last_failures) if last_failures else "none produced")
            )
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(accepted, destination)
        report.append(
            f"{article.id}: accepted attempt {tried} -> "
            f"{destination.relative_to(root).as_posix()}"
        )
        declarations.append((article.id, destination))
    if declarations:
        report.append("")
        report.append(
            f"Declare the artwork in editions/{edition.id}/edition.yaml -- each "
            "pair of lines below pastes onto its article's own list row:"
        )
        for article_id, path in declarations:
            report.append(f"  # {article_id}")
            report.append(
                f"  source_code_art_path: {path.relative_to(root).as_posix()}"
            )
    return report


def _attempt_article(
    article: "Article",
    url: str,
    work_dir: Path,
    runner: Callable[[list[str], Path], None],
    attempts: int,
    model: str,
    say: Callable[[str], None],
) -> tuple[Path | None, int, list[str]]:
    """Up to ``attempts`` fresh generations, each judged; first acceptance wins.

    Each attempt directory is CLEARED before its generator runs.  The prompt
    mandates one fixed output name (``art.png``), so a directory reused from an
    earlier session still holds the rejected candidate under exactly that name;
    a run that trusted "files that appeared" would see nothing new, burn the
    generator call, and report a produced image as no image.  A generator that
    fails to *run* (:class:`GenerationError`: timeout, crash, bad exit) costs
    the attempt and the loop continues, because a transient model failure must
    not abort the edition's session.
    """
    last_failures: list[str] = []
    for attempt in range(1, attempts + 1):
        attempt_dir = work_dir / f"attempt-{attempt}"
        shutil.rmtree(attempt_dir, ignore_errors=True)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        reference = attempt_dir / "qr.png"
        _write_reference_qr(url, reference)
        prompt = attempt_dir / "prompt.txt"
        prompt.write_text(_art_prompt(url), encoding="utf-8")
        try:
            runner(_codex_command(reference, model), attempt_dir)
        except GenerationError as exc:
            last_failures = [str(exc)]
            say(f"{article.id}: attempt {attempt} failed to run: {exc}")
            continue
        candidates = sorted(
            path for path in attempt_dir.glob("*.png") if path.name != reference.name
        )
        if not candidates:
            last_failures = ["the generator produced no PNG in its working directory"]
            say(f"{article.id}: attempt {attempt} produced no image")
            continue
        for candidate in candidates:
            failures = review_source_code_art(candidate, url)
            if not failures:
                return candidate, attempt, []
            last_failures = failures
            say(
                f"{article.id}: attempt {attempt} rejected "
                f"({candidate.name}): " + "; ".join(failures)
            )
    return None, attempts, last_failures


def _codex_runner() -> Callable[[list[str], Path], None]:
    """The real generator: the ``codex`` CLI, or an actionable refusal.

    A missing CLI is :class:`DependencyError` and aborts -- nothing transient
    about it.  A CLI that runs and fails (timeout, non-zero exit) is
    :class:`GenerationError`, which the attempt loop counts as one failed
    attempt and retries, because image-model sessions do sometimes crash and
    an edition's authoring run should outlive one crash.
    """
    executable = shutil.which("codex")
    if executable is None:
        raise DependencyError(
            "Generating source code artwork requires the `codex` CLI on PATH "
            "(it drives the image model). Install it and authenticate with "
            "`codex login`, or pass no articles and keep the plain vector codes."
        )

    def run(command: list[str], cwd: Path) -> None:
        prompt = (cwd / "prompt.txt").read_bytes()
        try:
            completed = subprocess.run(
                [executable, *command[1:]],
                cwd=cwd,
                input=prompt,
                capture_output=True,
                timeout=_CODEX_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GenerationError(
                f"codex did not finish within {_CODEX_TIMEOUT_SECONDS}s: {exc}"
            ) from exc
        if completed.returncode:
            detail = (completed.stderr or completed.stdout or b"").decode(
                "utf-8", "replace"
            ).strip()
            raise GenerationError(
                "codex failed while generating source code artwork. Check "
                f"`codex login` and the configured model: {detail[-2000:]}"
            )

    return run


def _codex_command(reference: Path, model: str) -> list[str]:
    """The generator invocation, relative to its own working directory.

    The prompt travels on stdin (``-``) because ``-i`` swallows a trailing
    positional argument, and the working directory is where the model writes
    its output -- both facts of the codex CLI, pinned here so the tests can
    assert the shape without running it.
    """
    return [
        "codex", "exec", "--skip-git-repo-check", "-s", "workspace-write",
        "-m", model, "-i", reference.name, "-",
    ]


def _write_reference_qr(url: str, destination: Path) -> None:
    """The true symbol the artwork must carry, at the tail slot's own geometry.

    The error correction level is not chosen here: it is whatever the print
    adapter's own fitting picks for a roomy tail slot (ECC-H for every URL this
    publication has printed), so the artwork's reference symbol is the symbol
    the plain code would have been.  Its light ground is the unprinted sheet,
    as the plain vector code's is, because the artwork's whole ground must read
    as the page (see the ground gate) and a warm-tinted reference would seed
    the sticker the gate exists to kill.
    """
    import segno

    from .weasyprint_adapter import _TAIL_ORNAMENT_MAX_HEIGHT, _fitted_source_code

    fitted = _fitted_source_code("reference", "tail", url, _TAIL_ORNAMENT_MAX_HEIGHT)
    if fitted is None:
        raise ValidationError(
            f"No QR error correction level can set {url!r} in the tail slot; "
            "shorten the canonical URL."
        )
    symbol = segno.make(url, error=fitted.error, micro=False)
    symbol.save(
        str(destination), kind="png", scale=16, border=4,
        dark="#11131A", light="#FFFFFF",
    )


def _art_prompt(url: str) -> str:
    """The style brief, derived from the design system's cover grammar.

    Two ideas carry it.  The ground is the page: the canvas is white because it
    prints on a white sheet, and an artwork whose ground reads as its own tint
    is a sticker, which the ground gate refuses.  And the composition is ONE
    proposition: shapes that engage the symbol's own geometry -- its grid, its
    module rhythm, its finders' concentric logic -- rather than decoration
    arranged around the perimeter of a centred stamp.  The symbol may stand
    anywhere the measured contract allows, because the build places and labels
    it off the measurement.
    """
    return f"""You are composing print artwork for a small magazine's article-tail page:
a working QR code hidden inside one hard-edged geometric composition, in the
magazine's cover grammar.

INPUT: qr.png in this directory is the working QR symbol (payload: {url}).

TASK: produce exactly one file named art.png in this directory: a square RGB
PNG of at least 1024x1024 pixels in which the symbol and the shapes read as ONE
proposition -- not a stamp with decoration around it.

COMPOSITION:
- The canvas ground IS the printed page. Leave it pure white #FFFFFF; the
  artwork must dissolve into the sheet it prints on, never read as a pasted
  tinted rectangle. Warm paper #F1EADB may appear only as a shape, never as
  the ground.
- Make the shapes engage the symbol's own geometry: extend its grid, echo its
  module rhythm, continue a finder square's concentric logic, run a single bar
  off one of its edges. Two to five shapes committed to one idea beat any
  amount of perimeter filler. Keep at least one large uninterrupted field of
  plain sheet.
- The symbol may stand anywhere on the canvas -- centred or not -- as long as
  its dark modules span 55-85% of the canvas width and its full 4-module light
  quiet zone stays inside the canvas.
- Keep the band to the RIGHT of the symbol, level with its BOTTOM edge, clear
  white all the way to the canvas edge: the magazine prints a small caps label
  there and type never sits on artwork ink.

STRICT RULES -- every one is machine-checked and a violation discards the image:
1. The symbol must remain scannable and decode to exactly the payload above.
   The safest method: write a small Python (Pillow) script that pastes qr.png
   UNCHANGED (nearest-neighbour resize only) onto the white canvas and draws
   shapes around it, then run the script. Do not redraw or restyle the modules.
2. The QR's dark modules stay near-black ink #11131A on white. Never colour
   any module violet or orange, and never let any shape enter the 4-module
   quiet zone around the symbol.
3. Use ONLY these inks, as flat hard-edged fields: white #FFFFFF (the ground),
   warm paper #F1EADB (shapes only), near-black ink #11131A, ultraviolet
   #5332C8, signal orange #FF5A1F. No gradients, no textures, no photographs,
   no glow, no noise.
4. Keep signal orange under 5% of the total area.
5. No people, robots, machinery, circuit boards, or literal diagrams.
6. NO letters, numbers, words, logos, or typographic marks anywhere in the art.

Save the result as art.png (RGB PNG) in the current directory and nothing else.
"""
