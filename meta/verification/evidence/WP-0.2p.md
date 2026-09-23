# WP-0.2p representation-only normalizations, per-page class counts

## Base and ownership

Base `art_directed` `e5e3498` (WP-0.2o), detached worktree. Written:
`mag/src/parity/canon.rs` (new, a child module of `display.rs` through
`#[path]`, so the five test crates that include `display.rs` compile it
unchanged), `mag/src/parity/display.rs`, one test fixture line in
`mag/src/parity.rs` (the new `PageDiff.classes` field), and one argument in
`mag/tests/parity_glyph_fixtures/mkfixtures.py`.

## What changed

Every normalization runs on BOTH legs through one function,
`canon::canonical(elements, text_ink)`, called by the display-list clause and
by the colour clause's paint sequence. The glyph-position clause, Tier S text,
Tier G and Tier V do not use it.

1. **Leading white fill.** A fill-only path whose colour is `(255, 255, 255)`
   and that precedes every other paint on the page (only clips before it) is
   dropped. It paints white on the white page with nothing beneath it; alpha
   and SMask other than 1/none already fail loud in the tracer.
2. **Rectangular clips that contain their paint.** A clip whose region is one
   axis-aligned rectangle is removed from every stack when the painted box of
   every element it governs lies inside it. Painted boxes: path control-point
   box (contains the curve), grown for strokes by `lw/2 * max(miter limit,
   1.42)` for miter joins, `lw/2 * 1.42` for round/bevel joins and for any
   stroke of an axis-aligned rectangle (every corner is 90 degrees); image unit
   square through its matrix plus one quantum; text as the union of each inked
   glyph's outline box from the vendored face (`ttf-parser`
   `glyph_bounding_box`, gid from the tracer), rounded outward plus one
   quantum. A glyph whose identity is unresolved (non-Type0) or whose font has
   no vendored face gives no box, and a clip governing it stays. Clips that
   then govern no paint are dropped and the survivors re-indexed.
3. **`re` is its definition.** `x y w h re` is recorded as the four corners
   it is defined as (PDF 32000-1 8.5.2.1: `m l l l h`), in that order, for
   every path, stroked or not, so start point and direction are kept. For
   fill-only paths and clip paths (whose region ignores start point and
   closing), each subpath is additionally closed explicitly, zero-length
   `l` segments are dropped, and the loop starts at its lowest vertex. Stroked
   paths get only the `re` expansion, since start point and direction change
   dashes and caps.
4. **Link `/Rect`** is stored as `[llx lly urx ury]` (min/max of the two
   corners, PDF 32000-1 7.9.5), in both the navigation and display clauses.
5. **Fill clipped to a region inside it.** A fill-only rectangle whose clip
   stack holds a clip whose control-point box lies inside the rectangle is
   recorded as a fill of that clip's path (fill or eofill per the clip's
   rule), and the clip leaves its stack. `P ∩ C = C` when `C ⊆ P`.

**Per-page classes.** `PageDiff` gains `classes`: per page, the number of
unmatched elements (multiset, both directions) per kind `text`, `path`,
`clip`, `image`, plus `annotations`, `boxes`, and `order` (1 when every kind
matches as a multiset but the sequence differs). Clip stacks are resolved to
the clip paths for this count, so an index shift alone is not a difference.
`detail` still names the first difference; its element index now counts the
canonical list.

**mkfixtures.py determinism.** `glyphsub` differed per run because fontTools
rewrites `head.modified` on save. `TTFont(..., recalcTimestamp=False)`.

## Tests (7 new, all pairing a normalization with a real difference nearby)

- `canon::tests::a_leading_white_fill_goes_but_a_tinted_or_covering_one_stays`:
  white page fill dropped; `(254, 255, 255)` stays; white painted after a rule
  stays.
- `a_rect_clip_holding_its_paint_goes_but_one_that_cuts_it_stays`: clip = fill
  box dropped, clip 1 quantum inside the fill stays; stroked frame with a clip
  1 pt outside dropped, clip 0.1 pt inside stays; text with ink inside dropped,
  ink 1 quantum past the edge stays, unknown ink stays; a round clip stays.
- `re_and_its_closed_four_line_path_compare_equal`: stroke and fill equal; one
  corner 1 quantum off fails for both; a rotated start point is equal for a
  fill and fails for a stroke.
- `a_square_clipped_by_its_circle_is_that_circle_but_a_moved_point_is_not`:
  WeasyPrint's structure (circle clip with zero-length lines, own-box clip,
  square fill) equals typst's circle fill when the control points agree; the
  010 values (4765/46250 vs 4764/46249) fail; one point 1 quantum off fails;
  a square that does not contain the circle fails.
- `display::colour_tests::a_leading_white_fill_is_not_paint_but_a_rule_after_it_is`,
  `a_link_rect_compares_by_its_corners_not_their_order` (0.5 pt off still
  differs), `every_differing_class_is_counted_beside_the_first_difference`
  (path 2 + text 2; order only; equal pages none).

## Commands and results

```sh
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```
All exit 0. `cargo test`: 26 binaries, **429 passed, 0 failed**. Rebased onto `f5754b8` (WP-5.7a adds a PDF fixture test crate, no parity code): 27 binaries, **434 passed, 0 failed**.

mkfixtures, two full runs into
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02p-fx/r3` and `r4` from
`editions/010/render-2026-09-14T01-49-02`: `cmp` finds **24 of 24 fixture
PDFs byte-identical**. Positive control: two `glyphsub` runs before the fix
(`r1`, `r2`) differ (`cmp`: char 87132768).

Binaries in `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02p-bin/`:
`mag-base` = `e5e3498`, `mag-new` = this diff.

### WeasyPrint floor

Script `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02p-floor.sh`
(WP-0.2o's, fixtures from the deterministic `r3`, both binaries on the same
files).

| row | base exit / digest | new exit / digest | verdict minus the 3 touched clauses | touched clauses base / new |
| --- | --- | --- | --- | --- |
| A-vs-A | 0 / `2d6bbf37da806432` | 0 / `71a0553ddc50a23c` | identical | all pass / all pass |
| control | 0 / `e2e974f132df31b5` | 0 / `5e34ccccfef6cb61` | identical | all pass / all pass |
| stairdrift | 0 / `043e45f673fef59c` | 0 / `a8e2d9315281a3e6` | identical | all pass / all pass |
| kern001 (must fail) | 1 / `7d41dfa3488e3208` | 1 / `942aff3d4bedabff` | identical | all pass / all pass |
| glyphsub (must fail) | 1 / `4b45830ad3fc8d0b` | 1 / `68d9801fd273b6cd` | identical | display fail, same 12 pages, `text: 2` each / same |

Touched clauses: `tier_s.color`, `tier_s.navigation`, `tier_e.display_list`.
Base digests for the first four equal WP-0.2o.md's "new" digests
(`2d6bbf37...`, `e2e974f1...`, `043e45f6...`, `7d41dfa3...`). glyphsub's base digest differs from WP-0.2o's because its fixture now comes
from the deterministic build. Canonical element count on the WeasyPrint leg:
2176 before, 1725 after.

### `mag parity 010` (typst leg), before and after

`MAG_PARITY_OUT_DIR=output/parity-wp02p/typst-<bin> <bin> parity 010 --run editions/010/run-2026-09-13T01-34-51`
from the main tree, both exit 1, staged inputs fresh `d92eca1d...`. Verdict
minus the three touched clauses and `inputs`: identical.

| tier | before (`mag-base`) | after (`mag-new`) |
| --- | --- | --- |
| S page_count | pass 56 vs 56 | same |
| S boxes | pass | same |
| S text | fail, 5 pages | same |
| G | max dx 325.563, dy 167.672, G1 56, G2 141, 9 structure | same |
| **S color** | fail, 58855 entries, 47 pages | **fail, 58800 entries, 47 pages** |
| **S navigation** | fail, 85 links, **22 mismatches** | fail, 85 links, **6 mismatches** (19: 11 vs 9 links; 21, 26, 27, 39: A2, one rect 0.5 pt off; document title/lang/outlines) |
| E glyph positions | fail, 2837 glyphs, worst ratio 7878.0, 40 violations | same |
| **E display list** | fail, **2189 vs 1642** elements, 52 pages (26 element 0, 21 annotations, 5 count 2 vs 0) | fail, **1738 vs 1642**, 52 pages (42 element 0, 5 element N, 5 annotations) |
| V | worst 0.624220 | same |

Colour, after: 3 pages differ at a glyph character (42-44, pagination), 16 at
the rule colour 229 vs 230 (oracle token, WP-0.2o class h), 28 at another
paint first. The 28 are paint ORDER (the running head is typst's first paint,
WeasyPrint's last, WP-0.2o class O) or genuine template paints (typst's white
fill-and-stroke opener frame, figure frames on 12 and 37); none is a white
leading fill, which is gone from every page.

Display list, after, from `classes` (pages carrying the class / unmatched
elements): text 47 / 2015, path 47 / 219, clip 26 / 35, image 25 / 25,
annotations 5 / 14. Text dominates through show segmentation and trailing
space glyphs (WP-0.2o class T), which this WP was not asked to normalize.

**Bullets (item 5): left failing, recorded.** After the structural
normalization, WeasyPrint's bullet and typst's are the same path command for
command (same start, same four curves) and differ ONLY in two control
coordinates per quadrant pair, by one 0.01 pt quantum each (`4765` vs `4764`,
`46250` vs `46249`; pages 20-24, 26-29, 39). Equality would need a tolerance
wider than the Tier E quantum, which the brief forbids; the template change of
the bullet is the fix. The unit test pins that the normalization makes them
equal when the points agree.

**Remaining clips on the WeasyPrint leg (35 elements, 26 pages)**: plate and
tail/figure images whose clip cuts the image (renders, class I), rounded-rect
clips (not rectangular), and the opener accent bar drawn as an eofill of two
nested rectangles clipped to the strip between them (page 5 and like pages).
That last one renders the same strip typst fills directly, but proving it
needs even-odd region algebra, which was not approved; it stays a difference.

## What is and is not proven

**Proven.**
- Each of the five normalizations makes the representation pair equal and
  leaves a 1-quantum (or 1-unit colour) change in the same neighbourhood
  failing (unit tests above).
- The WeasyPrint floor holds: all five rows give identical verdicts outside
  the three touched clauses, and the touched clauses keep their status (pass,
  or glyphsub's display failure on the same 12 pages).
- On 010 the normalizations remove 451 WeasyPrint display elements, 16
  navigation mismatches and 55 colour paints, and change no other tier.
- mkfixtures.py builds byte-identical fixtures across runs.

**Not proven.**
- The text ink box trusts the vendored face's glyph bounding boxes (`glyf`
  header values) and the tracer's gid mapping; a font whose declared glyph box
  understates its outline would let a cutting clip be dropped. Not checked
  against outline extrema.
- No normalized page was rasterized; soundness is argued from PDF semantics
  (and, for strokes, from a conservative reach).
- No 010 page passes the display list yet: every page still carries a class
  WP-0.2o attributes to the template (C, S, L, Y, I, P, h, O, T).
