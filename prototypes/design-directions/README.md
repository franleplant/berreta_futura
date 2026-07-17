# PROTOTYPE — Gallery White studies

Question: how can Gallery White become a more delightful, sophisticated print system without losing its restraint?

This focused round keeps Gallery White as the baseline and explores three structurally different descendants using the same real Issue 001 material:

- **G — Gallery White:** the original baseline, with asymmetric image authority, generous whitespace, and restrained serif typography.
- **N — Salon:** the closest refinement of G, built from optical alignment, low-set openers, and quiet single-column reading pages.
- **O — Monument:** typography becomes the interior artwork, using exact, attributed source language at dramatic scale.
- **P — Paired Rooms:** facing pages form deliberate compositions through mirrored whitespace and binding-aware alignment.

The focused gallery exposes only G and N–P in `index.html`, switchable with `?variant=G`, `N`, `O`, or `P`; O is the default. Earlier prototype files remain on disk as design history but are intentionally absent from this comparison. The prototype archive is independent of the production renderer.

## Artwork constraint

N–P use the cover artwork exactly once, on page 1. Pages 2–6 contain no image, crop, watermark, or repeated fragment. Their interiors use a neutral typographic system that does not inherit the cover artwork's palette, so future editions can change artwork and color freely. Layout code continues to own every masthead, title, cover line, and caption.

Generate the six-page A5 print samples and browser gallery with:

```sh
uv run --locked prototypes/design-directions/generate.py
```

The PDFs are the source of truth for evaluation. The PNGs are 144 dpi gallery previews. Every page assigns separate layout zones to display type, metadata, and body copy so collision checks can be made against realistic content.

## Professional print posture

The focused directions treat the magazine as a paced print sequence rather than six isolated posters. They use mirrored binding margins, measured and non-overlapping zones, readable long-form measures, metadata at 7 pt or larger, and rules at 0.5 pt or heavier. Interior delight comes from typography, proportion, whitespace, and page turns—not from recycling the cover image or its colors.

These are comparison prototypes, not press-ready files. A selected direction still requires mirrored binding margins, the named printer's bleed and safe-area specification, 300 ppi effective image resolution, the printer's CMYK or spot-color profile, complete font embedding, overprint checks, and a passing preflight. It must also survive the longer Spanish edition without collisions before release.

O / Monument was selected for the production renderer on 2026-07-16. This directory remains as the reproducible design record for G and N–P; generated previews are intentionally ignored by Git and can be recreated with the command above.
