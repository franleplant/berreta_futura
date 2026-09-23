# WP-0.2n effective page boxes and 8-bit colour comparison

## Base and ownership

- Base `art_directed` `bdbcebf` (WP-0.2m), detached worktree. Owns
  `mag/src/parity/display.rs` and `mag/src/parity/streams.rs` and their
  tests; nothing else was written. The two problems are WP-0.2m's findings 1
  and 2 (`meta/verification/evidence/WP-0.2m.md`, "Defects and findings").

## What changed

1. **Effective boxes.** `page_boxes` (`display.rs`) now records every page's
   effective MediaBox, CropBox and TrimBox: a missing CropBox takes the
   MediaBox, a missing TrimBox takes the CropBox (PDF 1.7, 14.11.2), with
   inheritance through `/Parent` as before. A page with no MediaBox fails
   loud. WeasyPrint's stated `TrimBox = MediaBox` and typst's absent TrimBox
   now record the same three boxes; a stated box that differs still records
   differently. (CropBox is not intersected with the MediaBox; neither leg
   states a CropBox outside it.)
2. **Colours at 8 bits (orchestrator decision, recorded here as a known
   divergence source).** typst-pdf 0.15.1 converts every solid colour with
   `to_vec4_u8()` before writing it (`typst-pdf-0.15.1/src/paint.rs:146`, per
   WP-0.2m.md), so a template colour such as INK `rgb(5.5%, 7.5%, 8.5%)` can
   never equal WeasyPrint's exact `0.055 0.075 0.085` at the old 1e-6 quantum.
   `qcolor` (`streams.rs`) now records each channel as the nearest n/255,
   `round(v * 255)`. It is applied when a colour is traced, so it holds for
   both legs and for every clause that compares colours: Tier S colour and
   Tier E display list both read `Color.rgb`. CMYK is converted to rgb first
   and then quantized. Consequence: a difference under half an 8-bit step is
   no longer seen; one full step or more always is (round is monotone and
   `round(x + 1) = round(x) + 1`). The quantum matches the 8-bit output both
   engines' printed and displayed pixels have.

## Tests (3 new, 1 revised)

| test | pins |
| --- | --- |
| `box_tests::a_missing_trim_or_crop_box_takes_its_pdf_default` | MediaBox only = MediaBox+CropBox+TrimBox stated equal (the WeasyPrint/typst case); a stated CropBox becomes the TrimBox |
| `box_tests::a_genuinely_different_effective_box_still_differs` | a different TrimBox, a different CropBox, and a CropBox-derived trim all differ; no MediaBox fails loud |
| `colours_compare_at_the_nearest_eighth_bit_step` | typst's INK `/c0 cs 0.054902 0.07451 0.086275 scn` equals WeasyPrint's `0.055 0.075 0.085 rg`, recorded `[14, 19, 22]`; a 0.4/255 offset on 0.25 compares equal; for every k in 0..=254, +1, +1.0001 and +2 steps from k/255 and from k/255 + 0.49/255 all compare unequal |
| `a_genuinely_different_colour_still_compares_unequal` (revised) | the old 0.001 offset is sub-step now and equal by decision; replaced by 0.004 (1.02 steps) on an sRGB channel and 0.496 vs 0.5 grey (2 steps); stroke 0.1 off and DeviceGray vs rgb family unchanged |

The first test was not run against the base code; by construction it would
fail there (the base records only a MediaBox for the MediaBox-only page, so
the maps differ). The same defect is reproduced on real data below: the
typst base run stops at `page boxes differ` on all 54 pages.

## Commands and results

```sh
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```
All exit 0. `cargo test`: **25 binaries, 327 passed, 0 failed** (312 at
WP-0.2l per WP-0.2m.md; +15 = 3 tests x 5 crates that compile `streams.rs` /
`display.rs` by `#[path]`; grep of the log counts 15 runs of the new tests).

Binaries: `mag-base` = `bdbcebf` (this diff stashed), `mag-new` = this diff,
both in `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02n-bin/`.

### WeasyPrint floor, base vs new on the same inputs

Script `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02n-floor.sh` (WP-0.2m's
floor script with the binary and output paths changed). Leg A =
`editions/010/render-2026-09-14T01-49-02`, fixtures rebuilt from it by
`mkfixtures.py` (self-check `stairdrift flat steps 52549/68800 = 76.3794%`,
WP-0.2i's figure).

| row | mag-base exit / digest | mag-new exit / digest |
| --- | --- | --- |
| A-vs-A | 0 / `4af43e9bb160c9e4` | 0 / `4af43e9bb160c9e4` |
| control | 0 / `dedacd632bef4888` | 0 / `dedacd632bef4888` |
| stairdrift (the floor) | 0 / `27b196e4ec67cd90` | 0 / `27b196e4ec67cd90` |
| kern001 (must fail) | 1 / `222691abb386631d` | 1 / `222691abb386631d` |
| glyphsub (must fail) | 1 / `7f19cdb11d46e132` | 1 / `651fd46754c7b900` |

(Digests differ from WP-0.2m's table because verdict digests move with the
commit, WP-0.2i's finding.) Four rows byte-identical. **glyphsub is not**: a
field-by-field diff of the two verdicts shows the only changed fields are the
12 `tier_e.display_list.pages_differing[i].detail` strings, which quote the
first differing element's JSON and so print its fill in the new unit
(`"rgb":[192157,364706,549020]` becomes `[49,93,140]`, `[250000,100000,430000]`
becomes `[64,26,110]`). Status, exit, page list, element counts and every
other tier are identical. No integer encoding of n/255 can reproduce the old
1e-6 integers (0.25 becomes 64/255 = 0.250980), so byte identity for a
must-fail row that quotes a colour is not attainable under this decision.

### `mag parity 010` (typst leg), base vs new

`MAG_PARITY_OUT_DIR=output/parity-wp02n/typst-<bin> <bin> parity 010 --run editions/010/run-2026-09-13T01-34-51`;
both exit 1, staged inputs `d92eca1d...` fresh (57 edition inputs, 43
renderer files). Verdict sha256 prefixes: base `454baaf54febc721`, new
`bdd855e82398e736`.

| tier | before (mag-base) | after (mag-new) |
| --- | --- | --- |
| S page_count | pass 56 vs 56 | same |
| S boxes | pass (162 boxes, 0 mismatches) | same |
| S text | fail, 30 of 54 pages | same |
| G | max dx 328.844, dy 367.872, beyond G1 118, G2 201, 141 structure | same |
| S color | fail, 1733 entries, 47 pages | fail, 1733 entries, 47 pages (same pages) |
| S navigation | fail, 85 links, 22 mismatches | same |
| E glyph positions | fail, 3295 glyphs, worst ratio 8285.875, 40 violations | same |
| E display list | fail, 54 pages, all `page boxes differ` | fail, 52 pages: 26 `element 0` (typst opens with a Clip where WeasyPrint opens with the running-head text, or the reverse), 21 `annotations differ`, 5 `element count 2 vs 0` (pages 10, 30, 35, 45, 54) |
| V | dims pass, V1 fail, V2 fail, worst 0.624220 | same |
| E raster | not_evaluated | same |

**The display list now reports real element differences**, as asked; 2
pages match whole. **The colour tier's page count did not move**, and that is
not the quantization failing: the clause compares per-page sequences of
`(text:<show>, colour)` entries, and the legs split text into shows
differently (2189 vs 1629 elements), so pages differ by sequence before
colour values matter. Checked directly on the two PDFs
(`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02n-colours.py`, pypdf,
distinct (fill/stroke, rgb) pairs over pages 2-55):

- at 1e-6: WeasyPrint 12, typst 11, 6 common (INK fill and stroke, VIOLET,
  SLATE, COOL-GRAY differ, WP-0.2m's table);
- at n/255: 10 common. Remaining: WeasyPrint-only fill PALE-VIOLET
  `(244, 241, 249)` (WP-0.2m finding 3, port gap) and a **stroke mismatch**:
  WeasyPrint strokes INK `(14, 19, 22)`, typst strokes `(23, 25, 28)`, 9 steps
  apart. That is a genuine template/port difference, new here, and correctly
  still fails.

## Known divergence source (for the plan)

Solid colours are compared at 8 bits per channel because typst-pdf 0.15.1
writes 8-bit colours (`paint.rs:146`). A sub-half-step difference between
the engines is invisible to parity by design; any difference of one 8-bit
step or more is reported.

## What is and is not proven

**Proven.**
- A missing TrimBox/CropBox compares as its PDF default; a genuinely
  different effective box still differs (unit tests), and on 010 the
  display list no longer stops at boxes on any page (0 of 52 details).
- Colours compare at the nearest n/255 on both legs in both colour-reading
  clauses (one quantizer at trace time); the four template colours WP-0.2m
  found now match on the real 010 PDFs; one-step and larger differences fail
  (exhaustive over k in the unit test) and a 0.4/255 difference passes.
- The WeasyPrint floor: A-vs-A, control, stairdrift and kern001 verdicts are
  byte-identical base vs new; glyphsub differs only in the colour notation
  inside its failure detail strings.

**Not proven.**
- That the 26 `element 0` pages differ only in ordering (Clip vs text first)
  and not in content: the clause reports the first difference only.
- How many of the 47 colour-tier pages differ in colour value rather than in
  show segmentation: the clause does not separate the two.
- Tier S text, G, navigation, glyph and V figures are unchanged, as expected
  from code these changes do not touch; nothing about the port is claimed.
