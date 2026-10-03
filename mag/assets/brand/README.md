# Berreta Futura logo

This file defines the logo. `tools/logo.py` generates every SVG here from
`mag/assets/fonts/inter/InterDisplay-Black.ttf`; never edit the SVGs by hand.

    uv run --with fonttools --with uharfbuzz tools/logo.py

Running it twice writes identical bytes.

## Files

| File | Contents | Use |
| --- | --- | --- |
| `wordmark.svg` | Stacked wordmark (S04) | Site header, cover masthead, social card |
| `mark.svg` | B + boxed F on a rounded red tile (K01) | Favicon, any square slot at 16 px and up |
| `mark-square.svg` | `mark.svg` with square corners | App icon (apple-touch-icon), avatars: the platform applies its own mask |

`mag site` writes `mark.svg` unchanged as `favicon.svg`, renders
`mark-square.svg` to the 180 px `apple-touch-icon.png`, and centres
`wordmark.svg` at 60% of a white 1200 x 630 `og.png`. The cover masthead
(`mag/src/cover/svg.rs`) embeds the `wordmark.svg` paths.

## Construction

Units: one cap height (C) is the cap height of Inter Display Black at the
size the word is set (0.7275 em).

- Typeface: Inter Display Black 4.001, OFL. Glyph outlines are used
  unchanged: no emboldening, no stroke, no outline cuts.
- Spacing: HarfBuzz shaping with the font's own `kern` feature, plus a
  tracking of -0.02 em between letters. Both words share size and spacing.
- BERRETA: set solid on the first line.
- FUTURA box: the word's ink bounds padded 0.14 em left and right and 0.13 em
  above and below (0.192 C and 0.179 C). The box and the letters it holds are
  skewed 10 degrees about the box's vertical centre, top edge leaning right
  (forward, like an italic).
- Stagger: the box's top sits 0.10 em (0.137 C) under BERRETA's baseline; its
  unskewed left edge sits at BERRETA's right ink edge minus 70% of the box
  width, so the box overhangs BERRETA by 30% of its width.
- Red offset: a red copy of FUTURA sits behind the paper letters, displaced
  (-0.12 C, +0.08 C): left and down. It is clipped by nothing; it shows
  where it leaves the paper letters.
- Mark: B and F at the same cap height. F sits in a box padded 0.16 C on
  every side and skewed 10 degrees as above. The B overlaps the box by
  0.15 C and is drawn on top. The group fills 80% of the 512 unit tile along
  its longer side and is centred. Tile corner radius: 20% of the side.

## Colours

The SVGs carry no fixed colour: every fill is a CSS variable with a fallback.
The web themes them; the Rust consumers substitute concrete values.

| Variable | Fallback | Paints |
| --- | --- | --- |
| `--ink` | `#0a0b0d` | BERRETA |
| `--box` | `#0a0b0d` | FUTURA box, mark F box |
| `--paper` | `#ffffff` | FUTURA letters, mark B and F |
| `--red` | `#f05738` | FUTURA red offset |
| `--tile` | `#f05738` | Mark tile |

On the cover, `--ink` and `--box` take the design's ink, `--paper` its
paper, and `--red` its orange.

## Dark grounds

The box stays near-black on every ground; only BERRETA changes, to the light
ink (site dark mode `#e7e5e0`, cover over dark art: paper). On a dark ground
the box takes a separating hairline in the BERRETA colour at 35% opacity:
1 CSS px (non-scaling) on screen, 1% of C (0.73 units of `wordmark.svg`) in
vector and print output. The mark needs no rule: its red tile separates it.

## Sizes and clear space

| Tier | Asset | Minimum |
| --- | --- | --- |
| Masthead | `wordmark.svg` | 40 px tall on screen, 25 mm wide in print |
| Small | `mark.svg` | 16 px; below 120 px wordmark width use the mark |

Clear space: keep 0.5 C of BERRETA free on every side of the wordmark's
viewBox, and 12.5% of the side around the mark tile. Nothing is placed
inside the tile.
