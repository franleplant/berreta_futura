# WP-0.2r glyph-level display list under Tier E contract (b)

## Base and ownership

Base `art_directed` `73ef1e7`, rebased onto `9c65b66` before landing (has 45fc32a's frame strips, loop direction
and ICC images). Started from `acad53b` (branch `wp-0.2q-full`,
WP-0.2q.md) cherry-picked without committing; the only conflict was one
test line in `canon.rs`. acad53b's frame-strip and ICC parts were already on
the base and merged as identical. Touched: `mag/src/parity/canon.rs`,
`display.rs`, `streams.rs`, `parity.rs`; one line each in two critic tests
that build an `Element::Text` by hand (`mag/src/critic.rs`,
`mag/tests/critic_text.rs`, the new `origin` field, as in acad53b); and one
expectation in `meta/verification/parity.yaml` (see below, outside the
Owns line, flagged for the orchestrator).

## What changed

Contract (b): the display list pins which glyphs appear, their order and
where each line starts; positions inside a line go to the glyph clause.

1. **Glyph split** (from acad53b). After the WP-0.2p normalizations every
   text show becomes one element per inked glyph (face, size, glyph id,
   char, fill, render mode, clip). Outline-less glyphs (`BLANK_GID`, or an
   unresolved glyph whose unit is whitespace) are dropped. The tracer keeps
   the fine show origin (`origin`, glyph quanta, `serde(skip)`) so a glyph's
   absolute position is computed once, unrounded.
2. **Line** (new, `canon::lines`). Inside each maximal run of consecutive
   glyph elements: glyphs are sorted by fine y, and a new baseline starts
   when y drops by more than one display quantum (0.01 pt) from the previous
   glyph. Within a baseline glyphs are sorted by fine x, and a new line
   starts when the origin-to-origin gap from the previous glyph exceeds
   `GAP_EM` = 3 em, em = |(m[0], m[1])| of that previous glyph (its
   device-space size). Every glyph element carries its line's start
   (first glyph's fine position, quantized at 0.01 pt) as `m[4], m[5]`, so
   the display list compares identity, order and line start, never the
   in-line position. Lines are emitted top to bottom, left to right. The
   acad53b paint-order guard is kept: a run whose reordering would swap two
   overlapping glyphs of different fill or render mode stays in paint
   order (`text_runs_in_paint_order`); line starts are assigned either way.
3. **Glyph clause** pairs the two normalized glyph lists index by index.
   Each glyph's difference is measured relative to its own line start on
   each leg: `(a.at - a.start) - (b.at - b.start)`. The bound is unchanged,
   `k * GLYPH_DRIFT_PT`, with `k` = advances from the line start, counting
   dropped blanks (max over the two legs). The one-signed monotone shape
   check runs per segment of pairs that share both a line and a show on
   each leg, because engine drift accumulates per show and resets at a show
   origin. With equal grouping and one show per line this is exactly the
   old per-show clause; the `shows` field now counts these segments.

### Why these line thresholds

Measured on 010 with a temporary instrumented binary (not landed), both
legs (WeasyPrint `render-2026-09-14T01-49-02` and the typst `--run` leg):
- x gaps between consecutive same-baseline glyphs, in em (630909 gaps on
  the typst run, 632445 on WeasyPrint A-vs-A): every in-line gap is at most
  **1.56 em**; the smallest separation gap is **27.54 em**. Nothing lies
  between. 3 em sits about 1.9x above the widest word gap and 9x below the
  narrowest separation, so no plausible drift (0.01 pt against a 1.44 em
  empty band) moves a glyph across it.
- y differences between consecutive y-sorted glyphs (643175): same-baseline
  glyphs differ by exactly 0 (630909); the smallest nonzero difference is
  **0.068 pt**, 6.8x the 0.01 pt threshold. So a baseline is exactly one y
  in both engines, and single linkage at one quantum cannot chain two
  real baselines.

### Fault-suite expectation changed (outside Owns)

`tests/parity_faults.rs::seeded_faults_are_detected` failed because
`swapped_words` ("beta gamma" -> "gamma beta") now also flags
`glyph_positions`: pairing on the normalized list puts glyph 11 5.000 pt
off (bound 0.008 pt). That detection is correct: the words really moved.
`meta/verification/parity.yaml` `expected_detections.swapped_words.must_flag`
now reads `[color, display_list, glyph_positions, text]`.

## Tests

In `display::colour_tests`:
- `the_same_glyphs_pass_whatever_the_show_grouping_or_trailing_space` (acad53b):
  "Hello world" as one show vs two shows passes both clauses, 10 = 10 elements.
- `a_missing_glyph_another_glyph_id_face_or_a_moved_line_start_fails_the_display_list`:
  missing glyph, another gid, another face each fail; the whole line moved by
  one quantum (+x, -x, +y) fails.
- `drift_inside_a_line_passes_the_display_list_and_the_glyph_clause_judges_it`:
  second show 1 glyph quantum off passes both; one display quantum off passes
  the display list and fails the glyph clause; a tail shifted past the bound
  (65 quanta at k=8, bound 64) fails only the glyph clause, 63 passes both;
  a per-show staircase reset inside one line passes both.
- `a_line_is_one_baseline_within_a_quantum_split_at_a_gap_of_three_em`:
  gap just under 3 em is one line, just over is two; y offset of exactly one
  quantum is one line, one quantum plus one is two; moving the second show
  by one quantum inside a line passes the display list and fails the glyph
  clause, across a 3 em gap it fails the display list and passes the glyph
  clause; a raised (superscript-like) show moved by one quantum fails the
  display list.
- `overlapping_glyphs_in_other_colours_keep_their_paint_order` (acad53b).

## Commands and results

```sh
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test --no-fail-fast
python3 tools/nocomments.py
```
fmt 0, clippy 0, nocomments 0. `cargo test`: 28 binaries, **487 passed, 0
failed** (parity unit tests 45 passed) on 73ef1e7; after rebasing onto
`9c65b66` (WP-3.4, WP-5.5a, WP-5.7b rework; no parity code touched, `git diff
--stat 73ef1e7 9c65b66 -- mag/src/parity mag/src/parity.rs`): 29 binaries,
**506 passed, 0 failed**, fmt and clippy exit 0.

Binaries in `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02r-scr/`:
`mag-before` = `art_directed` 73ef1e7, `mag-new` = this change. Floor
script `floor.sh` there (WP-0.2q's, same fixtures `wp02p-fx/r3`).

### WeasyPrint floor

| row | before exit / display / glyph | after exit / display / glyph |
| --- | --- | --- |
| A-vs-A | 0 / pass 1715 = 1715 / pass | 0 / pass 58982 = 58982 / pass, 58755 glyphs, 1488 segments |
| control | 0 / pass / pass | 0 / pass / pass |
| stairdrift | 0 / pass / pass 0.2500, 0 viol | **0 / pass / pass, ratio 0.2500, 0 violations** |
| kern02 | 1 / pass / fail 10.2500, 5 viol | 1 / pass / fail, **ceiling ratio 10.2500**, 5 violations |
| kern001 (must fail) | 1 / pass / fail 0.5625, 1 viol | 1 / pass / fail 0.5625, 1 violation |
| glyphsub (must fail) | 1 / fail 12 pages / pass | 1 / fail, same 12 pages / pass |

Colour passes on every row. Every verdict minus `tier_e.display_list` and
`tier_e.glyph_positions` is identical before and after (python comparison
of the verdict JSONs, all six rows `True`).

### `mag parity 010` (typst leg), before and after

`MAG_PARITY_OUT_DIR=output/parity-wp02r/typst-<bin> <bin> parity 010 --run editions/010/run-2026-09-13T01-34-51`
from the main tree, both exit 1. Verdict minus the two Tier E clauses and
`inputs`: identical.

| clause | before | after |
| --- | --- | --- |
| E display list | fail, 1728 vs 1642 elements, 52 pages | fail, 58850 vs 58775 elements, 52 pages, `text_runs_in_paint_order` 0 |
| E glyph positions | fail, 2837 glyphs, 51 shows, worst ratio 7878.0, 40 violations | fail, 54841 glyphs, 2714 segments, worst ratio 22556.0 (page 40, 325.8 pt: lists misaligned by text differences), 40 violations (list truncated at 40) |

Display-list classes (pages / unmatched elements):

| class | before (show elements) | after (glyph elements) |
| --- | --- | --- |
| text | 47 / 2015 | **36 / 16422** |
| path | 47 / 217 | 47 / 217 |
| clip | 25 / 25 | 25 / 25 |
| image | 25 / 25 | 25 / 25 |
| annotations | 5 / 14 | 5 / 14 |

For comparison (WP-0.2q.md): absolute glyph positions gave text 47 pages /
89742 glyphs, position-free glyph multisets 296. With line starts pinned, 11
pages now have text identical glyph for glyph; the rest differ in glyph
identity or a line start (the WP-1.6 advance drift now lands in the glyph
clause, where it is a real failure). First-difference split unchanged:
42 element, 5 count, 5 annotations.

## What is and is not proven

**Proven.**
- Under contract (b) the stairdrift floor row passes both clauses with the
  old numbers (0.2500, 0 violations); control and A-vs-A pass; kern02
  ceiling stays 10.2500; kern001 and glyphsub still fail by the same clause.
- The display list fails a missing glyph, another glyph id, another face,
  and a line start moved one quantum; it ignores show grouping, dropped
  spaces and in-line drift, which the glyph clause judges against the
  unchanged bound (unit tests).
- On 010 no in-line gap comes within 1.44 em of the 3 em split and no
  baseline difference within 0.058 pt of the 0.01 pt threshold, so line
  segmentation is not a rounding-boundary artefact there.

**Not proven.**
- Thresholds were measured on 010 only. A layout with a word gap above 3 em
  (very loose justification) would split a line and pin the second part's
  start; one with columns closer than 3 em would merge them and leave the
  second column's start to the glyph clause.
- When text differs, index pairing misaligns and the glyph clause's worst
  ratio measures that misalignment, not drift; it is only meaningful on
  pages whose display list text matches.
- The paint-order guard still trusts the vendored faces' glyph boxes.
