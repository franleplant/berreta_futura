# WP-0.2q glyph-level text (not landed), frame strips, ICC images

## Base and ownership

Base `art_directed` `977c5eb`, rebased onto `2a49650` before landing. Between
the two only `mag/src/critic/rules.rs` changed (`git diff --stat 977c5eb
131d065 -- mag/src`; after that WP-5.7b added `mag/src/pdf_text.rs`), so no parity code moved under this WP.
Landed: `mag/src/parity/canon.rs`, `mag/src/parity/streams.rs`.
Not landed, kept as commit `acad53b` on local branch `wp-0.2q-full`
(also `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02q-full.patch`): items
1 and 2, which touch `display.rs`, `canon.rs`, `streams.rs`, `parity.rs`
and add one line (the new `origin` field) to each of two critic tests that
build an `Element::Text` by hand (`mag/src/critic.rs`,
`mag/tests/critic_text.rs`).

## Verdict: items 1 and 2 break the WeasyPrint floor, so they are not landed

Item 1 as specified (every text show split into glyphs, each glyph carrying
its absolute device position quantized at the Tier E 0.01 pt quantum) makes
the display list fail **stairdrift**, a row that must pass, on **46 pages**,
and **kern001** on 1 page. The mechanism is exact, not a bug in the change:

- stairdrift adds a within-bound intra-show drift of `k * 0.000173` pt
  (mkfixtures.py `RATE`) that the glyph-position clause accepts (worst
  ratio 0.2500). A 60-glyph line ends about 0.0104 pt off, past the 0.01 pt
  quantum, so the absolute glyph position rounds differently. Before this
  change the display list compared only show origins, which drift does not
  touch, so it passed.
- kern001 moves one glyph 0.001 pt and moves it back. One glyph that sat
  near a rounding boundary changes its 0.01 pt value. Show origins could flip
  on a rounding boundary in the same way, but there are 1488 origins and
  58755 glyphs, so glyphs give far more chances.

With per-glyph absolute positions, the display list also checks every
intra-show position to 0.01 pt. That is stricter than the glyph-position
clause's `k * tick` bound, so the tolerance that clause encodes stops having
any effect. Tier E has to pick one of two contracts:
(a) absolute glyph positions at 0.01 pt. stairdrift and kern001 then become
must-fail rows, and the glyph clause only matters below the quantum.
(b) keep drift tolerance. The display list pins glyph identity, order and
line anchors, and positions inside a line stay with the glyph clause.
Either is a plan decision. This WP was not asked to make it.

What the unlanded change measured (binary `mag-new`, `wp-0.2q-full`):

| floor row | display | glyph clause |
| --- | --- | --- |
| A-vs-A, control | pass, 58982 = 58982 elements | pass, 58755 glyphs, 1488 runs |
| stairdrift | **fail, 46 pages** | pass, ratio 0.2500, 0 violations |
| kern02 | fail, 1 page | fail, ratio 10.2500, 5 violations |
| kern001 | **fail, 1 page** (was pass) | fail, ratio 0.5625, 1 violation |
| glyphsub | fail, same 12 pages | pass |

On 010 (typst leg): display list 58850 vs 58775 elements, 52 pages, classes
text 47 pages / 89742 unmatched glyphs, path 47 / 219, clip 25 / 25, image
25 / 25, annotations 5 / 14; `text_runs_in_paint_order` 0, so no run held
overlapping glyphs of different paint. Glyph clause 54841 glyphs, 2714 runs,
40 violations. **Show grouping is fully resolved**: comparing the glyph
multisets with position removed leaves 296 unmatched glyphs over all pages
(89742 with position). On the eight pages WP-0.2o names as nearest (8, 13,
14, 15, 18, 33, 47, 48), text is identical glyph for glyph except position.
x differs by 0 to 14 quanta (0.14 pt), 69% of glyphs by at least one, y
never. That is the WP-1.6 advance drift, a real rendering difference
(scratch analysis of both legs' canonical dumps).

Design of the unlanded change, for whoever picks (a):
glyphs are split after the WP-0.2p normalizations. Outline-less glyphs
(`BLANK_GID`, or an unresolved glyph whose unit is whitespace) are dropped.
Each maximal run of consecutive text elements is ordered by `(-y, x)`, and a
run stays in paint order when two glyphs whose order would swap have
intersecting ink boxes and a different fill or render mode. Those runs are
counted in `text_runs_in_paint_order`. The tracer records a fine show origin
(`origin`, in glyph quanta, `serde(skip)`), so a glyph's absolute position is
rounded once. Without it, a regrouped show's glyphs inherit the 0.005 pt
rounding error of its quantized origin. The glyph clause pairs the two
normalized glyph lists index by index, per maximal run of pairs that share a
show on both legs. When both runs start at the same glyph of their shows,
offsets are relative to the show origins, which is exactly the old
behaviour. Otherwise they are rebased to the run's first glyph.
Tests there: grouping and trailing space pass (display and glyph clause); one
glyph moved by one quantum, another gid, another face and a missing glyph
each fail; glyph clause pairs on the normalized list (1 glyph-quantum origin
shift passes, one glyph moved 40 glyph quanta fails); overlapping
differently coloured glyphs keep paint order (and fail when swapped), and
non-overlapping ones reorder and pass.

## What landed

1. **Frame strips (WP-0.2p item 2).** A fill-only `eofill` path of two nested
   axis-aligned rectangles O and I, whose stack holds a rectangular clip S,
   becomes a `fill` of `(O ∩ S) \ I`, and S leaves the stack. This happens
   only when that region is one rectangle: I misses `O ∩ S` (zero-area
   touching counts as missing), or cuts off one full-width or full-height
   end of it. Anything else (a hole in the middle, an L shape, non-rectangles,
   non-nested pairs) stays as it is.
2. **Single-loop fill direction.** `fill_region` now also canonicalizes the
   direction of a path that has exactly one closed loop, because reversing
   one loop changes its winding number from +1 to -1 and so leaves its
   region the same under both rules. Item 1 could not match without it:
   the strip it built ran counter-clockwise and typst's runs clockwise. Paths
   with several subpaths keep their direction, since for nested loops
   direction decides whether the inner one is a hole. Strokes never pass
   through `fill_region`.
3. **ICCBased images** (coordinator addition, unblocks WP-3.4).
   `image_pixels` accepted only a name for `/ColorSpace`. typst-pdf writes
   `[/ICCBased n]` for every image (WP-3.4.md). It now decodes an ICCBased
   image by the profile it names, through the WP-0.2m `icc_space`: the sRGB
   v4 profile gives 3 channels and the sGrey v4 profile gives 1, and `/N` must
   match the profile. Any other profile fails loud with the same message the
   colour path uses. DeviceRGB/DeviceGray are unchanged.

Tests (landed):
- `canon::tests::a_frame_clipped_to_its_strip_is_that_strip_but_a_moved_edge_is_not`:
  WeasyPrint's 010 accent bar (values from page 5) equals typst's strip fill;
  a strip 1 quantum wider fails; a clip 1 quantum short, or starting 1
  quantum in, fails; a clip reaching past the inner edge is equal (the region
  really is the strip); a hole inside the strip stays unnormalized.
- `re_and_its_closed_four_line_path_compare_equal` gains: a reversed rect
  fill is equal, a reversed rect stroke is not, and reversing one loop of
  two nested ones is not equal.
- `streams::tests::an_icc_image_decodes_as_its_srgb_or_grey_samples_and_nothing_else`:
  sRGB ICC image hash = DeviceRGB hash for the same samples, one sample
  changed differs, sGrey = DeviceGray, a one-bit-altered profile fails loud,
  `/N` 1 on the sRGB profile fails loud.

## Commands and results

```sh
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```
All exit 0 on the landed tree. `cargo test`: 27 binaries, **446 passed, 0
failed**. Rebased onto `2a49650` (WP-5.7b, adds `pdf_text.rs` and a test crate, no parity code): 28 binaries, **457 passed, 0 failed**. The unlanded full version also passed fmt, clippy and the parity
tests (44 passed) before it was set aside.

Binaries in `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02q-bin/`:
`mag-base` = WP-0.2p's `mag-new` (the parity code at `977c5eb`; its floor
digests reproduce WP-0.2p.md's "new" column exactly), `mag-new` = full
unlanded change, `mag-land` = the landed diff.

### WeasyPrint floor

Script `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02q-floor.sh`
(WP-0.2p's plus a kern02 row), fixtures from WP-0.2p's deterministic `r3`.

| row | base exit / digest | land exit / digest | verdict minus display and colour | display base / land | glyph clause (both) |
| --- | --- | --- | --- | --- | --- |
| A-vs-A | 0 / `71a0553ddc50a23c` | 0 / `1567983162065cd9` | identical | pass 1725 / pass 1715 | pass |
| control | 0 / `5e34ccccfef6cb61` | 0 / `a3dbfae2b90c4308` | identical | pass / pass | pass |
| stairdrift | 0 / `a8e2d9315281a3e6` | 0 / `38940d540e184ab5` | identical | pass / pass | **ratio 0.2500, 0 violations** |
| kern02 | 1 / `f1bc21cbc6024cb5` | 1 / `d5b284585f3ed691` | identical | pass / pass | fail, **ceiling ratio 10.2500**, 5 violations |
| kern001 (must fail) | 1 / `942aff3d4bedabff` | 1 / `1873ae3fd365851d` | identical | pass / pass | fail, ratio 0.5625, 1 violation |
| glyphsub (must fail) | 1 / `68d9801fd273b6cd` | 1 / `674701497051cd3f` | identical | fail, same 12 pages / same | pass |

Colour passes on every row, before and after. The 10 fewer WeasyPrint
elements are the accent bars' clips, one per opener.

### `mag parity 010` (typst leg), before and after

`MAG_PARITY_OUT_DIR=output/parity-wp02q/typst-<bin> <bin> parity 010 --run editions/010/run-2026-09-13T01-34-51`
from the main tree, all exit 1. Verdict minus `tier_e.display_list`,
`tier_s.color`, inputs and staleness: identical between base and land.

| tier | before (`mag-base`) | after (`mag-land`) |
| --- | --- | --- |
| S page_count / boxes | pass / pass | same |
| S text | fail, 5 pages | same |
| G | max dx 325.563, dy 167.672, G1 56, G2 141, 9 structure | same |
| S color | fail, 58800 entries, 47 pages | same |
| S navigation | fail, 85 links, 6 mismatches | same |
| E glyph positions | fail, 2837 glyphs, 51 shows, worst ratio 7878.0, 40 violations | same |
| **E display list** | fail, **1738** vs 1642, 52 pages (42 element 0, 5 count 2 vs 0, 5 annotations) | fail, **1728** vs 1642, 52 pages (same split) |
| V | worst 0.624220 | same |

Display-list classes (pages / unmatched elements):

| class | before | after |
| --- | --- | --- |
| text | 47 / 2015 | 47 / 2015 |
| path | 47 / 219 | 47 / **217** |
| clip | 26 / 35 | **25 / 25** |
| image | 25 / 25 | 25 / 25 |
| annotations | 5 / 14 | 5 / 14 |

Every opener's accent-bar clip is gone (10 clips, pages 4, 5, 7, 11, 17, 31,
36, 40, 46, 50). On page 5 the bar now matches typst's path exactly.
On the other nine the normalized bar still differs, because typst draws it
at another y (WP-0.2o class P, template). The 25 clips left are the image
clips that cut their image (class I) and rounded-rect clips.

## What is and is not proven

**Proven.**
- The frame-strip rule is exact region algebra for axis-aligned rectangles
  and fires only when the result is one rectangle. The unit test fails a
  1-quantum change of strip, clip edge or clip start.
- Single-loop direction does not change a fill's region (winding ±1). The
  test keeps multi-loop direction significant.
- ICCBased images decode only for the two recognised profiles, and every
  other profile fails loud (unit test). WP-3.4's comparator blocker is gone
  for those profiles.
- The WeasyPrint floor holds for the landed change: six rows identical
  outside the two touched clauses, and those keep their status and pages.
- Items 1 and 2 as specified conflict with the floor (stairdrift 46 pages,
  kern001 1 page), and the cause is quantizing absolute glyph positions at
  0.01 pt under tolerated drift.

**Not proven.**
- The ICC path was not run on a real typst PDF with rasters in this WP; the
  010 `--run` leg rendered here still has no typst images (class I).
- The overlap guard in the unlanded change trusts the vendored faces' glyph
  boxes, as WP-0.2p's text ink does.
- No normalized page was rasterized.
