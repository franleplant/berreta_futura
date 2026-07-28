from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


PALETTE = {
    "paper": "#F1EADB",
    "ink": "#11131A",
    "violet": "#5332C8",
    "signal": "#FF5A1F",
}


def scaled_points(points: list[tuple[float, float]], size: int) -> list[tuple[int, int]]:
    return [(round(x * size), round(y * size)) for x, y in points]


def render_hinge(size: int) -> Image.Image:
    """Render issue 2's three-plane hinge in the publication cover grammar."""
    scale = 4
    canvas = size * scale
    image = Image.new("RGB", (canvas, canvas), PALETTE["paper"])
    draw = ImageDraw.Draw(image)

    planes = (
        (
            PALETTE["violet"],
            [(0.64, 0.19), (1.0, 0.04), (1.0, 0.64), (0.66, 0.54)],
        ),
        (
            PALETTE["violet"],
            [(0.0, 1.0), (0.61, 1.0), (0.61, 0.64), (0.08, 0.91)],
        ),
        (
            PALETTE["ink"],
            [(0.66, 0.68), (1.0, 0.76), (1.0, 1.0), (0.66, 1.0)],
        ),
    )
    for color, points in planes:
        draw.polygon(scaled_points(points, canvas), fill=color)

    hinge_x = round(0.635 * canvas)
    hinge_y = round(0.615 * canvas)
    radius = round(0.055 * canvas)
    draw.ellipse(
        (hinge_x - radius, hinge_y - radius, hinge_x + radius, hinge_y + radius),
        fill=PALETTE["signal"],
    )

    return image.resize((size, size), Image.Resampling.LANCZOS)


def render_relay(size: int) -> Image.Image:
    """Render issue 2's relay: three inputs, one switch, one output."""
    scale = 4
    canvas = size * scale
    image = Image.new("RGB", (canvas, canvas), PALETTE["paper"])
    draw = ImageDraw.Draw(image)

    channels = (
        (
            PALETTE["violet"],
            [(0.00, 0.17), (0.54, 0.42), (0.50, 0.49), (0.00, 0.32)],
        ),
        (
            PALETTE["violet"],
            [(0.00, 0.43), (0.52, 0.46), (0.52, 0.54), (0.00, 0.58)],
        ),
        (
            PALETTE["violet"],
            [(0.00, 0.76), (0.50, 0.51), (0.54, 0.58), (0.00, 0.91)],
        ),
    )
    for color, points in channels:
        draw.polygon(scaled_points(points, canvas), fill=color)

    draw.polygon(
        scaled_points(
            [(0.49, 0.50), (0.59, 0.40), (0.69, 0.50), (0.59, 0.60)],
            canvas,
        ),
        fill=PALETTE["ink"],
    )
    draw.polygon(
        scaled_points(
            [(0.65, 0.46), (1.00, 0.28), (1.00, 0.46), (0.65, 0.54)],
            canvas,
        ),
        fill=PALETTE["ink"],
    )
    pivot_x = round(0.59 * canvas)
    pivot_y = round(0.50 * canvas)
    radius = round(0.035 * canvas)
    draw.ellipse(
        (pivot_x - radius, pivot_y - radius, pivot_x + radius, pivot_y + radius),
        fill=PALETTE["signal"],
    )

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render deterministic BERRETA FUTURA cover artwork.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=1800)
    parser.add_argument("--motif", choices=("hinge", "relay"), default="hinge")
    args = parser.parse_args()

    if args.size < 512:
        parser.error("--size must be at least 512 pixels")
    image = render_relay(args.size) if args.motif == "relay" else render_hinge(args.size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
