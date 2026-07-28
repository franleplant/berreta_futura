from pathlib import Path

from PIL import Image, ImageDraw

from magazine import image_contrast
from magazine.image_contrast import (
    MAX_PRINT_CONTRAST_ENHANCEMENT,
    MIN_MARK_PIXEL_RATIO,
    MIN_PRINT_CONTRAST_RATIO,
    _CONTRAST_FACTORS,
    analyze_print_contrast,
    prepare_print_image,
)


def test_paper_dominant_faint_line_art_is_detected_and_strengthened(tmp_path: Path):
    source = tmp_path / "faint-diagram.png"
    image = Image.new("RGB", (800, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 720, 420), outline="#efc9bc", width=4)
    draw.line((120, 250, 680, 250), fill="#e6b09d", width=5)
    image.save(source)

    before = analyze_print_contrast(source)
    prepared = prepare_print_image(source)
    after = analyze_print_contrast(prepared.image)

    assert before.needs_treatment is True
    assert prepared.adjusted is True
    assert prepared.unresolved is False
    assert after.minimum_mark_contrast_ratio >= MIN_PRINT_CONTRAST_RATIO
    with Image.open(prepared.image) as treated:
        assert treated.getpixel((0, 0)) == (255, 255, 255)


def test_photographic_image_is_not_rewritten(tmp_path: Path):
    source = tmp_path / "photo.png"
    image = Image.new("RGB", (800, 500))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    image.save(source)

    prepared = prepare_print_image(source)

    assert prepared.adjusted is False
    assert prepared.unresolved is False
    assert prepared.image == source


def test_legible_dark_on_cream_diagram_is_healthy_and_untouched(tmp_path: Path):
    """Warm paper is paper, not marks.

    The old classifier keyed paper to `min channel >= 245` and marks to
    `min <= 235`, so this cream sheet (min channel 224) was counted wholesale
    as MARKS, its own tint became the "median mark" at a false sub-2.0 ratio,
    and a perfectly legible diagram got a tint-saturating 3x auto-crank. Nine
    library assets flipped untreated->treated that way, three of them figures
    declared in edition 002. The background-relative classifier must read the
    cream as the sheet and measure the dark strokes against IT: healthy,
    untreated, byte-identical output.
    """
    source = tmp_path / "dark-on-cream.png"
    image = Image.new("RGB", (800, 500), (250, 243, 224))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 720, 420), outline=(40, 40, 40), width=4)
    for index in range(5):
        draw.line((120, 130 + index * 55, 680, 130 + index * 55), fill=(60, 60, 60), width=5)
    image.save(source)

    before = analyze_print_contrast(source)
    prepared = prepare_print_image(source)

    assert before.paper_pixel_ratio > 0.8  # the cream sheet counts as paper
    assert before.mark_pixel_ratio >= MIN_MARK_PIXEL_RATIO
    assert before.minimum_mark_contrast_ratio >= MIN_PRINT_CONTRAST_RATIO
    assert before.needs_treatment is False
    assert prepared.adjusted is False
    assert prepared.unresolved is False
    assert prepared.image == source


def test_counterproductive_enhancement_ships_original_bytes_unresolved(tmp_path: Path):
    """When no rung improves the median, the ORIGINAL bytes are the least bad.

    This background sits at the image's own grayscale mean, so PIL's
    midpoint-anchored stretch cannot widen the gap between the marks and
    their background: every rung measures at or below the untreated median.
    The old ladder kept the LAST rung unconditionally and shipped bytes
    measurably worse than untreated (edition 003's lights-on-factory went
    1.419 -> 1.358 that way). The honest outcome is the untouched source file
    with the unresolved verdict preserved for preflight.
    """
    source = tmp_path / "midtone-unrescuable.png"
    image = Image.new("RGB", (800, 500), (190, 190, 190))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 720, 420), outline=(170, 170, 170), width=6)
    for index in range(5):
        draw.line((120, 130 + index * 55, 680, 130 + index * 55), fill=(174, 174, 174), width=4)
    image.save(source)

    before = analyze_print_contrast(source)
    prepared = prepare_print_image(source)

    assert before.needs_treatment is True
    assert prepared.adjusted is False
    assert prepared.image == source  # original bytes, not a "least bad" crank
    assert prepared.unresolved is True
    assert prepared.after == before  # the measured failure, not a rewrite
    assert prepared.after.minimum_mark_contrast_ratio < MIN_PRINT_CONTRAST_RATIO
    # The shipped pixels are untouched: no rung ever posterized the marks.
    with Image.open(prepared.image) as shipped:
        assert shipped.getpixel((400, 130)) == (174, 174, 174)


def test_faint_midtone_diagram_fixable_within_cap_is_strengthened(tmp_path: Path):
    source = tmp_path / "midtone-rescuable.png"
    image = Image.new("RGB", (800, 500), (238, 238, 238))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 720, 420), outline=(200, 200, 200), width=6)
    for index in range(6):
        draw.line((120, 120 + index * 50, 680, 120 + index * 50), fill=(205, 205, 205), width=4)
    image.save(source)

    before = analyze_print_contrast(source)
    prepared = prepare_print_image(source)

    assert before.mark_pixel_ratio >= MIN_MARK_PIXEL_RATIO
    assert before.needs_treatment is True
    assert prepared.adjusted is True
    assert prepared.unresolved is False
    assert prepared.after.minimum_mark_contrast_ratio >= MIN_PRINT_CONTRAST_RATIO


def test_pale_fill_figure_is_never_contrast_cranked(tmp_path: Path):
    """A figure that leans on tint ships untouched, however faint its marks.

    The pastel panel here is semantic — a global contrast stretch would wash
    it toward paper while crushing the bars toward ink, "improving" the
    median as the artwork visibly degrades. Both faint edition-003 figures
    (lights-on-factory, assembled-context-conflicts) have this profile, and
    their verdicts must stay unresolved rather than being resolved by a crank
    that destroys their fills.
    """
    source = tmp_path / "pale-fill.png"
    image = Image.new("RGB", (800, 500), "white")
    draw = ImageDraw.Draw(image)
    # A large pastel fill: tint, neither paper nor mark.
    draw.rectangle((60, 60, 740, 260), fill=(247, 234, 228))
    # Faint placeholder bars: marks below the print floor.
    for index in range(6):
        draw.line((100, 300 + index * 30, 700, 300 + index * 30), fill=(210, 210, 210), width=8)
    image.save(source)

    before = analyze_print_contrast(source)
    prepared = prepare_print_image(source)

    tint_ratio = 1.0 - before.paper_pixel_ratio - before.mark_pixel_ratio
    assert tint_ratio >= 0.05  # the profile that forbids enhancement
    assert before.needs_treatment is True
    assert prepared.adjusted is False
    assert prepared.image == source
    assert prepared.unresolved is True
    assert prepared.after == before


def test_mark_collapse_is_a_measured_failure_not_default_healthy(tmp_path: Path, monkeypatch):
    """Enhancement that bleaches the marks away resolved nothing.

    If a rung pushes the pale marks above the mark threshold, the after
    analysis has mark_pixel_ratio below the floor and would default its
    contrast to the healthy 21.0. That default must never turn a vanished
    mark population into a "resolved" verdict: such a rung is a measured
    failure, the original bytes ship, and the figure stays unresolved.
    """
    source = tmp_path / "mark-collapse.png"
    image = Image.new("RGB", (800, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 720, 420), outline="#efc9bc", width=4)
    draw.line((120, 250, 680, 250), fill="#e6b09d", width=5)
    image.save(source)

    class _BleachingContrast:
        """Stand-in for ImageEnhance.Contrast whose output erases all marks."""

        def __init__(self, target: Image.Image):
            self._size = target.size

        def enhance(self, factor: float) -> Image.Image:
            return Image.new("RGB", self._size, "white")

    monkeypatch.setattr(image_contrast.ImageEnhance, "Contrast", _BleachingContrast)

    before = analyze_print_contrast(source)
    prepared = prepare_print_image(source)

    assert before.needs_treatment is True
    assert prepared.adjusted is False
    assert prepared.image == source
    assert prepared.unresolved is True
    assert prepared.after == before  # never the 21.0 default of an empty mark set
    assert prepared.after.minimum_mark_contrast_ratio < MIN_PRINT_CONTRAST_RATIO


def test_enhancement_ladder_tops_out_at_the_cap():
    assert MAX_PRINT_CONTRAST_ENHANCEMENT == 3.0
    assert max(_CONTRAST_FACTORS) == MAX_PRINT_CONTRAST_ENHANCEMENT
