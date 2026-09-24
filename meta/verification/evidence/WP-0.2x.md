# WP-0.2x comparator: no quantum-edge artifacts across legs

Base `art_directed` `361fc76`. Worktree `.../tmp/wp02x`, target `.../tmp/wp02x-target`,
binaries `.../tmp/wp02x-bin/mag-base` (base, release) and `mag-x` (this change, release),
scratch and every verdict below under `.../tmp/wp02x-out/`. Sources: WP-3.7c.md (glyph
clause "blocked", 90 / 48 blips, 903 p4 / 905 p6 QR residual); the orchestrator brief
for this WP (decisions 1 and 2).

## What changed (`mag/src/parity/{streams,canon,display}.rs`)

1. **Exact coordinates ride beside the coarse keys.** The tracer keeps every text
   show's exact text-rendering matrix and per-glyph offsets, and every image's CTM,
   in a side map (`Pose`, keyed by element index; `trace_page` and its callers in
   `critic` are unchanged). Path tokens are written as exact f64 hundredths of a
   point instead of `qc` buckets. Canonicalization still decides on rounded keys:
   the path scalar `C { k, v }` orders and compares by `k = round(v)` only, so
   rotations, reversals, rect detection and tie-breaks (now `key(...)`, the coarse
   render) are what they were; `v` travels through `strip_fill`'s meet/cut.
2. **Display list: tolerance, not bucket equality.** Two legs' coordinates agree
   when `|a - b| <= 0.005 pt` (half the 0.01 quantum), computed in f64: path
   tokens, text matrix (with the exact line start as its translation), text size,
   image matrix, page boxes. Link rects use half their own 0.5 pt quantum
   (`|a - b| <= 0.25 pt`), in the display list and in Tier S navigation. Equal
   values (including two infinities, or two `NaN` tokens) agree. `class_keys` (the
   per-class diagnostic counts) and ordering keys stay on rounded values.
3. **Glyph clause.** The drift is quantized once, from f64:
   `qo((a.x - a.start) - (b.x - b.start))`. Per-advance gaps, travel and reach are
   quantized from f64 differences too (`qo(x1 - x0)`, not `qo(x1) - qo(x0)`).

**Deviation from decision 1, measured.** Decision 1 as written (quantize each leg's
`at - start` in f64, then subtract) was built first (`mag-x` build 1, verdicts
`v-x1-*`): 010 glyph clause still fails (40 printed, the cap), fixtures 18/18/10/6
= 52 (was 48). Cause, from a debug print of 902 p3 glyphs 0..17: the in-line
offsets themselves differ by up to 2.4e-6 pt between legs (accumulating per
advance), so each leg's `at - start` still straddles quantum edges. WP-3.7c's
"in-line offsets agree to 1e-13 pt" holds for 010 body lines, not for every run.
Quantizing the difference between legs removes the edge entirely, which is
decision 2's rule applied to the glyph clause.

## Commands (exit status, key numbers)

```sh
cd .../tmp/wp02x
MAG_PARITY_OUT_DIR=.../wp02x-out/base-run mag-base parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 1
MAG_PARITY_OUT_DIR=.../wp02x-out/x-run    mag-x    parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 0
bash .../wp02x-out/score.sh <bin> <tag>       # 010 + 902-905 --pre-rendered, one comparator per row
BINS="mag-base mag-x" bash .../wp02x-out/floor.sh      # copy of tmp/v02j/floor.sh, output dir changed; exit 0
TAG=<tag> MAG=<bin> python3 .../wp02x-out/adv/all.py <tag>   # tmp/v02j/h/run.py over all 210 pairs, outputs redirected
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # 0, 0, 0: 32 result lines, 862 passed, 0 failed
```

### `mag parity 010` (`--run editions/010/run-2026-09-13T01-34-51`)

Before: legs `render-2026-09-24T08-29-38` (weasyprint) / `08-31-04` (typst, reader.pdf
`6709dc15...`, the same bytes WP-3.7c recorded). After: legs `08-59-08` / `09-00-26`
(typst reader.pdf again `6709dc15...`). Staged inputs fresh `ae9d6daf...` both runs.

| tier / clause | before (`mag-base`) | after (`mag-x`) |
|---|---|---|
| exit | 1 | **0** |
| ratchet | pass, 54 checked, 0 regressions | same |
| S page_count, boxes, text, color, navigation | pass (56 vs 56; 162 boxes; 54 pages; 58800 entries; 85 links) | same |
| G | max dx 0.000, dy 0.006, 0 beyond G1/G2 | same |
| E display list | pass, 58850 vs 58850, 0 pages | same |
| E glyph positions | **fail**, 90 violations (full count, `wp37c-tfull` binary on the before legs; committed verdict prints 40), worst excess 0.000000 pt, ratio 0.0417 | **pass**, 58623 glyphs, 1514 shows, 0 violations, ratio 0.0000 |
| V | V1 pass, V2 pass 0.000336 | same |
| E raster | not_evaluated (no `raster_bound`, owner WP-0.2d) | same |

**010 passes every Tier E clause that is evaluated** (display list, glyph positions),
and every S, G and V clause: verdict
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02x-out/x-run/verdict.json`, exit 0.
Tier E raster is still not evaluated, so Tier E as a whole is not proven.

### Fixtures (oracle renders of WP-3.7a, typst legs rendered fresh at base, `score.sh`)

| fixture | display list before -> after | glyph violations before -> after |
|---|---|---|
| 902 | pass -> pass | 18 -> **0** |
| 903 | fail p4 (QR y 392.864980 vs 392.865103) -> **pass** | 15 -> **0** |
| 904 | pass -> pass | 9 -> **0** |
| 905 | fail p6 (QR) -> **pass** | 6 -> **0** |

All four exit 0 after. S, G, V unchanged.

### Floor (`floor.txt`)

| row | before | after |
|---|---|---|
| AvA, control | pass, 0, 0 | same |
| **stairdrift** | pass 0.2500, 0 viol | **pass 0.2500, 0 viol** |
| drift / smoothdrift | pass 0.2500 / 0.6250 | pass 0.1875 / 0.5208 |
| **kern02** | fail 10.2500, 7 | **fail 10.2500, 7** (ceiling unchanged) |
| kern001 | fail 0.5625, 1 (shape) | fail 0.5000, 1 (shape) |
| advstep | fail 0.6250, 2 (advance + shape) | fail 0.6250, 1 (advance) |
| advtail02 | fail 10.2500, 8 | same |
| glyphsub | display fail 12 pages | same |

### Adversarial replay (all 210 pairs of `tmp/v02j/h/cases`, the superset of `adv*/cases`)

`results-base.jsonl` reproduces `v02j/h/results-u.jsonl` exit-for-exit (0 differ).
Base 63 pass / 147 fail / 21 fail-loud; after 63 / 147 / 21. Two pairs change:

| pair | px | before | after | why |
|---|---|---|---|---|
| `exact_f32inf_distinct_offpage` | 0 | pass | **fail** (display) | rect scaled 1e39 vs 1e40: both `qc` saturated to `i64::MAX`, the exact values differ |
| `cap_dots_125pt_100_tick` | 3331 | fail (shape only, ratio 0.9519) | **pass** (ratio 0.9524) | see below |

**`cap_dots_125pt_100_tick` no longer fails. This does not meet the "every
adversarial pair still fails" requirement.** 100 dots, each 1.25 pt apart, each
one tick (8 quanta) further on leg b: the exact drift is -8, -16, ... -8k, inside
the k-step bound (ratio 0.95), and the pair was caught only because separate
rounding put a blip in that sequence (debug print: -128, -135, -144 at glyphs
21-23). The bound itself admits this pair by construction (WP-0.2t.md "What is
not proven": one tick per advance accumulates), and its 0.5 pt sibling
`cap_dots_05pt_400_tick` still fails on the bound (ratio 2.179). Closing it is a
bound decision (steps per reach, `MIN_ADVANCE_PT`), not a rounding one: open for
the orchestrator.

## Tests

- `coordinates_agree_within_half_a_hundredth_of_a_point_and_not_beyond`: a rule
  moved by 0.004 pt passes, 0.006 pt (either way) fails, the 903 QR pair
  392.86498 / 392.865103 (straddling a 0.01 edge) passes, 0.0099 fails.
- `a_sub_quantum_line_start_or_offset_difference_is_not_a_blip`: a line whose
  third glyph sits 1e-7 pt below a quantum edge, against line starts moved by
  5e-7, 2.05e-5 and 2e-7 pt (the two WP-3.7c noise sizes), and against advances
  each 4.2e-7 pt shorter: glyph clause pass with ratio 0, display list pass.
  Positive control: a 0.6-quantum excursion on one glyph fails the shape check.
- Mutants (each restored, `git diff --stat` checked): separate rounding
  `qo(x) - qo(start)` fails the line-start test (shape violation on the 5e-7
  start); decision 1 as written (`qo(at - start)` per leg) fails it on the
  positive control (the 0.6-quantum excursion is rounded away per leg); bucket
  equality in `within` fails the coordinate test.
- `a_coordinate_whose_f32_crosses_a_quantum_boundary_traces_at_its_authored_value`
  now pins the exact written token `30000.4999` (it pinned the bucket 30000).

## What is and is not proven

- Proven by measurement: 010 glyph blips 90 -> 0 and fixture blips 48 -> 0; 903 p4
  and 905 p6 display lists equal; stairdrift 0.2500/0, AvA and control pass,
  kern02 10.25 (7); 208 of 210 adversarial pairs keep their outcome, one more
  fails, one fails no longer (above).
- Tolerance, not correctness: the display list now admits any coordinate within
  0.005 pt of the other leg, including 0.0099 pt pairs that were in one bucket
  before, and refuses 0.006 pt pairs that were in one bucket before. Neither leg
  is checked against a correct value here.
- Not proven: canonical decisions (rotation start, zero-length line removal, rect
  detection, baseline banding, line splits) still use rounded keys, so two legs
  whose values straddle an edge inside those decisions can still canonicalize
  differently. None fired on 010, 902-905, the floor or the 210 pairs. Stroke
  width, dash and miter are still bucketed (lengths, not coordinates). Link
  tolerance 0.25 pt is the "half the quantum" rule applied to the 0.5 pt link
  quantum, a reading of the brief, not an instruction in it.
