from pathlib import Path

from PIL import Image, ImageDraw

from magazine.image_contrast import (
    MIN_PRINT_CONTRAST_RATIO,
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
    assert prepared.image == source
