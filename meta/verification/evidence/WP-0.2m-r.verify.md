# WP-0.2m..0.2r adversarial verify (comparator normalizations)

Verifier, at `art_directed` `d4866a0` (parity code identical to `aad29c1`:
`git diff --stat aad29c1 d4866a0 -- mag/src/parity mag/src/parity.rs` is
empty). Question: can any of the six changes let a visible rendering
difference pass the gate?

## Verdicts

| WP | verdict | why |
| --- | --- | --- |
| WP-0.2m colour spaces | **ACCEPTED** | sRGB/sGrey ICC vs `rg` render pixel-identical and compare equal; a different colour fails |
| WP-0.2n boxes, 8-bit colour | **ACCEPTED** | a cropped page fails; `TrimBox = MediaBox` renders identically and passes; one 8-bit step fails; a sub-half-step pair passes with a 1-level pixel difference, which is the decided quantum |
| WP-0.2o per-glyph colour | **ACCEPTED** | one glyph in another colour fails, invisible vs visible fails |
| WP-0.2p five normalizations | **REJECTED** | three visible differences pass: a zero-area "rect" clip is dropped (the whole line it hides reappears), a zero-area "rect" fill clipped to a circle becomes the circle, and an anisotropic stroke's cut is dropped |
| WP-0.2q (landed part) | **REJECTED** | the frame-strip rule turns an eofill whose inner "rect" has zero area into half the strip it really paints |
| WP-0.2r glyph-level text | **REJECTED** | outline-less glyphs on ONE leg raise the glyph clause bound (k counts dropped blanks, max over legs); 7000 blanks let a word move 5 pt and pass every clause |

Root causes:
1. **`canon::rect`** (WP-0.2p, reused by WP-0.2q's `frame`) accepts any
   closed 4-segment axis-aligned loop whose vertices sit on the bounding
   box's corners, including out-and-back loops of zero area such as
   `m 100 100 l 300 100 l 300 200 l 300 100 h`. Such a path paints and clips
   NOTHING, but `contained_clips`, `fill_the_clip`, `strip_fill` and the
   stroke-reach `square` test all treat it as its bounding rectangle.
2. **Stroke reach** (WP-0.2p) is computed from the tracer's `lw`, which is
   `lw * sqrt|det CTM|` (`streams.rs` `paint_op`). Under `1 0 0 16 0 0 cm` a
   1-unit stroke is 16 pt tall on the page and recorded as 4, so the reach
   (2.85 pt with round joins) sits inside a clip that cuts the stroke. The
   tracer defect itself predates these WPs (see findings).
3. **Glyph bound** (WP-0.2r): `drift` uses `a.step.max(b.step)`, and `step`
   counts dropped outline-less glyphs. Before WP-0.2r the display list
   pinned every show's glyph list including blanks, so both legs had to
   carry the same blanks; now blanks are invisible to the display list and
   one leg alone can inflate k without limit. Taking the minimum over the
   legs (or counting only advances present on both) closes it; the fix is
   the WP owner's.

## Method

Hand-built 3-page A5 PDFs (page 2 under test, pages 1 and 3 blank),
Inter-Regular embedded whole as a CIDFontType2 / Identity-H font so the
tracer resolves glyph identity against the vendored face. Generator and
runner in `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/adv/`
(`pdfgen.py`, `cases.py`, `run.py`, one directory per pair under `cases/`
with both PDFs, rasters and `out/verdict.json`). Per pair:
`pdftoppm -r 300 -f 2 -l 2` on both legs, pixels compared (count of pixels
with any channel difference, count beyond 24, max channel delta), then
`mag parity 010 --pre-rendered <a> <b>` with the tip binary from the repo
root. "Gate" is the exit code; Tier V never gates on pixels (its status
fails only on page-size mismatch, `raster.rs`), so the pixel-level gate is
Tier S text/colour/navigation/boxes plus Tier E display list and glyph
positions. Harness controls: identical PDFs pass (0 px); "Hello world"
moved 1 pt fails the display list (5117 px).

Attribution: every pair that passes at the tip was re-run on
`d5e3629` (before WP-0.2m; cannot load fonts by PostScript name, so only
the font-free pair ran), `e5e3498` (before WP-0.2p), WP-0.2p's own binary,
and `73ef1e7` (before WP-0.2r); binaries from the WPs' scratch dirs.

## Adversarial pairs

px = pixels differing at 300 dpi / beyond delta 24 / max delta.

| pair | WP | px | gate | clause outcome |
| --- | --- | --- | --- | --- |
| `col_one_step` fill 128/255 vs 129/255 | 0.2n | 347361 / 0 / 1 | fail | colour, display fail |
| `col_subhalf_step` 0.1 0.2 0.5 vs 26/255 51/255 128/255 | 0.2n | 347361 / 0 / 1 | pass | equal by the 8-bit decision; 1 level, not visible |
| `col_sgrey_vs_rg` `/c1 cs 0.3 scn` vs `0.3 0.3 0.3 rg` | 0.2m | 0 | pass | correct |
| `col_srgb_icc_vs_rg` `/c0 cs` vs `rg`, same values | 0.2m | 0 | pass | correct |
| `col_cmyk_vs_rgb` `0 0 0 .5 k` vs `.5 .5 .5 rg` | 0.2m | 347361 / 0 / 17 | fail | family differs |
| `col_cmyk_richblack` `0 0 0 1 k` vs `1 1 1 0 k` | (pre-existing) | 347361 / 347361 / 25 | **pass** | naive CMYK conversion maps both to black; poppler paints 25 levels apart. Passes at `e5e3498` too; conversion from `1483f04` |
| `box_trim_equal_media` stated Trim/Bleed = Media | 0.2n | 0 | pass | correct |
| `box_crop_smaller` CropBox 10 pt short | 0.2n | 0 (pdftoppm rasterizes the MediaBox without `-cropbox`; a viewer shows the page 10 pt shorter) | fail | boxes, display fail |
| `glyph_colour_one` "e" red | 0.2o | 3088 / 2924 / 255 | fail | colour, display fail |
| `glyph_invisible` Tr 3 vs Tr 0 | 0.2o | 3585 / 3389 / 255 | fail | colour, display fail |
| `white_over_text` white rect painted after the text | 0.2p | 1898 / 1792 / 255 | fail | colour, display fail |
| `white_leading_then_white_over` full-page white first, second white over text | 0.2p | 1898 / 1792 / 255 | fail | first dropped, second kept |
| `white_leading` white first, text after | 0.2p | 0 | pass | correct |
| `clip_rect_contains_legit` rect clip holding the line | 0.2p | 0 | pass | correct |
| `clip_cuts_descender` clip at the baseline over "gypsy" 24 pt | 0.2p | 287 / 275 / 255 | fail | display fail |
| `clip_descender_tight` clip 0.3 pt above the "g" descender's bottom | 0.2p | 14 / 12 / 143 | fail | display fail |
| `clip_cuts_stroke_width` 4 pt stroke, clip 2 pt tall | 0.2p | 6665 / 6664 / 255 | fail | display fail |
| `clip_anisotropic_stroke` miter join, 16x y scale, clip 8 pt tall | 0.2p | 26657 / 26656 / 255 | fail | reach = miter limit 10 x lw/2 = 20 pt covers it by chance |
| **`clip_anisotropic_stroke_round`** same with round cap/join | 0.2p | 26780 / 26776 / 255 | **pass** | clip dropped; fails at `e5e3498` |
| **`clip_degenerate_rect`** zero-area "rect" clip around "Hello world" (line invisible) vs the line | 0.2p | 3585 / 3389 / 255 | **pass** | clip dropped; fails at `e5e3498` |
| **`fill_degenerate_rect_clipped`** zero-area "rect" fill clipped to a circle (paints nothing) vs the circle filled | 0.2p | 137196 / 136922 / 255 | **pass** | rewritten as the circle; fails at `e5e3498` |
| `fill_clipped_circle_legit` real square clipped to a circle vs circle | 0.2p | 0 | pass | correct |
| `re_vs_path_fill` `re` vs reversed 4-line path, other start | 0.2p/q | 0 | pass | correct |
| `re_vs_path_stroke_dash_start` dashed stroke, other start | 0.2p | 17140 / 17140 / 255 | fail | display fail |
| `loop_single_reversed` triangle both directions | 0.2q | 0 | pass | correct |
| `loop_nested_reversed_inner` nonzero square with inner loop reversed (hole) vs same direction (no hole) | 0.2q | 174306 / 174306 / 255 | fail | display fail |
| `strip_legit` eofill O, I nested, clip strip inside O, vs the strip | 0.2q | 126 / 126 / 89 | pass | region equal; 126 px are clip-edge vs fill-edge antialiasing, one pixel wide |
| `strip_hole_middle` inner rect inside the strip | 0.2q | 10612 / 10610 / 255 | fail | display fail |
| **`strip_degenerate_inner`** inner "rect" of zero area over the left half | 0.2q | 17556 / 17556 / 255 | **pass** | turned into the right half; fails with WP-0.2p's binary, passes at `73ef1e7` |
| `link_rect_order` corners swapped, 2 pt red border | 0.2p | 0 | pass | correct |
| `link_border_vs_none` `/Border [0 0 0]` vs `[0 0 3] /C [1 0 0]` | (pre-existing) | 9375 / 9375 / 255 | **pass** | `Annot` compares subtype, rect, dest only; poppler draws the border |
| `line_word_moved_1em` "cd" 1 em further right, same line | 0.2r | 1546 / 1444 / 255 | fail | display pass, glyph clause fail |
| `line_gap_split` "cd" at 2 em vs 3.5 em | 0.2r | 1596 / 1490 / 255 | fail | display fail (line split) |
| `line_superscript` "cd" raised 4 pt | 0.2r | 1277 / 1176 / 255 | fail | display, glyph, colour fail |
| `line_baseline_ramp` 52 glyphs each 0.01 pt higher than the last (chained into one baseline) vs flat | 0.2r | 11633 / 9599 / 255 | fail | the chain merges the band as the contract says, and the glyph clause fails the y drift (0.01 pt per glyph against 0.00073) |
| `blank_no_inflation` "world" 5 pt right, 1 blank | 0.2r | 2833 / 2657 / 255 | fail | glyph clause fail |
| **`blank_inflation`** same shift, 7000 zero-width space glyphs before "world" on leg B | 0.2r | 2833 / 2657 / 255 | **pass** | k for "w" is 7006 on B, bound 5.13 pt; fails at `73ef1e7` (display list saw the blanks) |
| `cid2gid_blank_draws_glyph` leg A's CIDToGIDMap sends the space CID to "X" | (pre-existing) | 388 / 345 / 255 | **pass** | tracer assumes Identity; sees a blank and drops it. Passes at `e5e3498` |
| `simple_font_lying_tounicode` Helvetica "xAy" with ToUnicode A to space vs "x y" | (pre-existing) | 365 / 344 / 255 | **pass** | unresolved glyph with a whitespace unit is dropped (display list and colour); passes at `e5e3498`, where the show strings were also equal |
| `anisotropic_stroke_vs_plain` 1 w under 16x y scale vs 4 w plain | (pre-existing) | 41652 / 41650 / 255 | **pass** | both record `lw` 400; passes at `d5e3629` |

The "outline-less glyph that is NOT a space" question: on the Type0 path
the blank test reads the embedded outline at gid = CID, so a glyph that
really paints nothing is dropped correctly; the two ways to make a dropped
glyph paint are a non-Identity CIDToGIDMap and a simple font whose
ToUnicode says whitespace. Both predate WP-0.2r and both 010 legs write
`/CIDToGIDMap /Identity` Type0 fonts (mutool census of the four
`render-2026-09-23T23-3*` trees; the WeasyPrint ones also carry 2 TrueType
and 2 Type1 simple fonts, on the cover pages per `font_name_map`'s note).
Cheap closure: fail loud on a non-Identity CIDToGIDMap and on a simple font
inside the compared domain.

## Floor replay at the tip

`mag parity 010 --pre-rendered`, leg A `editions/010/render-2026-09-14T01-49-02`
(sha256 `4e8906ae1beaf58e`), fixtures WP-0.2p's deterministic `r3`; outputs
in `.../tmp/adv/floor/`.

| row | exit | glyph clause | display |
| --- | --- | --- | --- |
| A-vs-A | 0 | pass, 58755 glyphs, 1488 segments, ratio 0 | pass 58982 = 58982 |
| control | 0 | pass, ratio 0 | pass |
| stairdrift | 0 | **pass, ratio 0.2500, 0 violations** | pass |
| drift / smoothdrift | 0 / 0 | pass 0.2500 / pass 0.6250 | pass |
| kern02 | 1 | fail, **ratio 10.2500**, 5 violations | pass |
| kern001 | 1 | fail 0.5625, 1 violation | pass |
| advstep, advmid, advtail_late | 1 | fail 0.6250, 1 violation each | pass |
| advtail_small / advtail02 | 1 | fail 0.5625, 1 / fail 10.2500, 7 | pass |
| glyphsub | 1 | pass | fail, 12 pages |

Colour and text pass on every row. All match WP-0.2r.md.

## `mag parity 010` at the tip

`MAG_PARITY_OUT_DIR=.../tmp/adv/typst010 mag parity 010 --run editions/010/run-2026-09-13T01-34-51`
from the main tree: **exit 1, verdict written**. Legs
`render-2026-09-24T00-34-09` (WeasyPrint), `render-2026-09-24T00-35-17`
(typst).

| clause | tip | WP-0.2r.md after-table |
| --- | --- | --- |
| E display list | fail, 58850 vs **58794**, 52 pages, paint-order runs 0 | fail, 58850 vs 58775, 52 pages, 0 |
| E glyph positions | fail, **58623** glyphs, **2881** segments, worst ratio 22556.0 (page 40), 40 violations | fail, 54841, 2714, 22556.0 (page 40), 40 |
| classes (pages / elements) | text 32 / 10250, path 26 / 124, clip 25 / 25, image 25 / 41, annotations 5 / 14, order 8 | text 36 / 16422, path 47 / 217, clip 25 / 25, image 25 / 25, annotations 5 / 14 |
| S text / colour / navigation | fail 2 pages / fail 30 pages / fail 6 | not tabulated |

The WeasyPrint side (58850), worst ratio and violation count match; the
typst side does not, because the typst leg is not the one WP-0.2r measured:
its numbers were taken on `73ef1e7`, and `mag/src/typeset/{content,layout,template,world}.rs`
changed between `73ef1e7` and the tip (WP-3.4 et al., landed before
WP-0.2r's rebase). To separate comparator from leg, WP-0.2r's own binary
(`wp02r-scr/mag-new`) was run on these two legs with `--pre-rendered`:
`tier_s`, `tier_e` and `tier_g` are **identical** to the tip verdict. So
the comparator at the tip is WP-0.2r's; the after-table is stale for the
typst leg, not wrong for the comparator.

## Tests committed (ignored, pinning the correct value)

Three rejections for lacking an adversarial test, so the pairs are
committed as `#[ignore]` unit tests that fail at this tip (each run with
`--ignored`, all three FAILED; the canon test checks its three cases
independently and gets `[true, true, true]` against `[false; 3]`):
- `canon::tests::a_zero_area_loop_with_rect_corners_is_not_a_rect_region`
  (WP-0.2p clip and clip-fill, WP-0.2q strip)
- `display::colour_tests::blanks_on_one_leg_buy_no_drift_allowance` (WP-0.2r)
- `streams::tests::an_anisotropic_stroke_is_not_the_isotropic_one_of_mean_width`
  (tracer width, the root of the WP-0.2p reach hole)

Whoever fixes removes the `ignore`. `cargo fmt --check` 0, `cargo clippy
--all-targets -D warnings` 0, `tools/nocomments.py` 0, `cargo test
--no-fail-fast` 29 binaries, 506 passed, 0 failed, 18 ignored.

## Findings outside the six WPs (for the orchestrator)

1. Tracer `lw` is `lw * sqrt|det|`: an anisotropic stroke compares equal to
   an isotropic one of another width (41652 px). Record the width per axis
   or fail loud on anisotropic stroking CTMs.
2. CMYK is collapsed through `(1-c)(1-k)`; poppler renders `1 1 1 0 k` 25
   levels from `0 0 0 1 k`. Latent (010 emits no `k`).
3. CIDToGIDMap is ignored; ToUnicode whitespace is trusted for simple
   fonts. Latent on 010 (above).
4. Link `/Border` and `/C` are not compared, and poppler draws them (9375 px).
   Latent if both engines write `/Border [0 0 0]`; not checked here.
5. Tier V's status never fails on pixels, so nothing outside Tier S/E backs
   up a normalization.

## What is and is not proven

**Proven.** Each listed pair's pixel difference and gate outcome at the
tip; the six passing visible differences attributed to WP-0.2p (3),
WP-0.2q (1) and WP-0.2r (1), each failing on the binary before its WP; the
floor rows reproduce WP-0.2r.md; the tip comparator gives WP-0.2r's
binary's verdict on today's 010 legs.

**Not proven.** The pairs are hand-built; neither engine is shown to emit
a zero-area rect, an anisotropic stroke or padding blanks on 010 (no census
was run for them). The ICCBased image path (WP-0.2q item 3) got no
adversarial pair beyond its unit test. Pixel checks are poppler at 300 dpi
only.
