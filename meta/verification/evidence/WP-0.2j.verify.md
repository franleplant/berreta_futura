# WP-0.2r, 0.2s, 0.2t, 0.2j adversarial verify

Verifier, at `art_directed` `7bd2fcf` (WP-0.2j `d68b309` + queue doc;
`git diff --stat d68b309 7bd2fcf -- mag` is empty). Question: can a pair
that renders visibly differently at 300 dpi pass the gate, and does
stairdrift still pass?

## Verdicts

| WP | verdict | why |
| --- | --- | --- |
| WP-0.2r glyph-level text (as reworked by 0.2t/0.2j) | **ACCEPTED** | its rejecting pair `blank_both_7000_5000_shift3` fails; no new pair passes through a 0.2r rule |
| WP-0.2s rework (as reworked by 0.2t) | **ACCEPTED** | the `min(blanks)` rule is gone and the link key is raw; every 0.2s adversarial pair fails. Its conservative cost is live on 010 (below) |
| WP-0.2t glyph steps, raw link keys, annotation fail-louds, hairline | **ACCEPTED** | paired-advance bound and blank-gap rules held against every new pair; the only passes are the linear-model residual 0.2t disclosed and handed to 0.2j |
| WP-0.2j exact number path | **ACCEPTED** | every malformed or unusual real fails loud or reads its authored value; object streams bind; no pass through the exact path |
| WP-0.2j span cap | **REJECTED** | (1) glyphs off the page widen a line's span, so "world" moves **5.08 pt on the page and passes** (`cap_offpage_inflate2_6944_shift5`, 3833 px); the same line without the off-page dots fails. (2) The disclosed in-page residual is visible: a word at the line end moves **0.477 pt and passes** (`cap_tail_stack_651_end_word` 1594 px, `cap_full_line_651` and `cap_backtrack_325pairs_full` 15833 px), ten times the 0.047 pt of an honest full line drifting one tick per glyph |

Independent of these four WPs, the tracer has two pre-existing holes (pass
at `e5e3498`, before WP-0.2p, and at the tip) that let a large visible
difference through. They need an owner:

1. **lopdf's lenient decode.** `Tracer::run` calls `Content::decode`, which
   stops at the first token it cannot parse and silently returns the
   operations before it. Poppler reports the token and keeps painting. A
   stray `]` or `@` followed by `0 0 0 rg 100 100 200 100 re f` paints a
   200x100 pt black box that the comparator never sees: exit 0 at 347361
   px. The exact path catches it only when the dropped tail holds a real
   (`junk_bracket_then_real` fails loud). Closure: `Content::decode_strict`
   (lopdf 0.45 has it; it refuses unconsumed input).
2. **Operand arity.** The tracer reads `args[0]` (`w`, `Tc`, `Tw`, ...) and
   `nums[0..4]` (`re`); poppler, given too many operands, drops the FIRST
   extras and uses the last. `1 8 w` (24159 px), `100 100 200 100 50 50 re`
   (303680 px) and `0 3 Tc` (5109 px) pass. `rg` and `cm` already fail loud
   on count. Closure: exact arity per operator, fail loud otherwise.

Both are latent on 010 (neither engine writes junk or extra operands), but
each is a visible difference the gate passes.

## Method

The WP-0.2j harness (`wp02j-run/h`: `run.py`, `pdfgen.py`, `cases.py`,
160 prebuilt pairs) copied to
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/v02j/h/`; new pairs in
`gen_v.py`. Per pair: `pdftoppm -r 300` page 2 of both legs, pixels
differing, then `mag parity 010 --pre-rendered`; gate = exit status.
Binary: release build of the tip in a fresh worktree (`v02j/target`).
Attribution: `wp02p-bin/mag-base` (`e5e3498`), `wp02j-run/mag-base`
(WP-0.2t). Fix probes: `v02j/mag-fix` (per-glyph reach),
`v02j/mag-fix1.4` and `mag-fix2.5` (per-glyph reach plus
`MIN_ADVANCE_PT` 1.4 / 2.5), built from scratch edits that were reverted
(`git diff --stat` after: only the two test hunks below).

Pixels are not a usable criterion on their own for text drift: the
contract's own licensed drift renders differently (`honest_line_every_glyph_tick`,
every glyph of a 64-glyph line one tick wider: 0.047 pt, 1122 px, passes;
half a tick: 489 px). A text pass is judged wrong when its drift exceeds
what an honest line can accumulate (010: at most 104 steps per line,
0.076 pt, WP-0.2j.md) or when it is not text drift at all.

## 1. Replay of every earlier pair

`all_j.py tip` over all 160 pairs (`results-tip.jsonl`, exit 0): **no exit
status changes** against WP-0.2j's `results-new.jsonl`. Every adversarial
pair of `WP-0.2m-r.verify.md`, `WP-0.2s.verify.md`, WP-0.2t and WP-0.2j
fails, including `tick_ladder_7000_shift5`. 47 pass; the only passes with
more than 2 px are the two already accepted (`col_subhalf_step`, one
level; `strip_legit`, 126 px edge AA). 9 fail loud, same messages.

Legitimate pairs that fail (px 0), all unchanged from WP-0.2t:
`link_bs_vs_border_same_legit`, `link_bs_w0_vs_border0_legit`,
`link_bs_dash_default`, `link_c_absent_vs_black_w3`, `link_c_gray_vs_rgb`
(raw link keys, conservative by design); `box_crop_smaller`; five `clip_*`,
two `rot_*` and eight `skew*` display pairs; `gstate_blend_mode`,
`overprint_op` (fail loud). **Only the link keys matter for 010**:
WeasyPrint writes `/BS <</W 0>>` and typst `/Border [0 0 0]`, which is
navigation's 22 mismatches below. The typst template must write the
oracle's spelling; the comparator is right to refuse to equate them.

## 2. New pairs

px = pixels differing at 300 dpi. Gate: exit 0 = pass.

**Span cap and kern backtrack (WP-0.2j item 2, WP-0.2t residual).** Each
stacks n no-outline blanks (`uni00A0`) of width 0 on leg A and one tick
(0.061 units at 12 pt) on leg B inside one TJ, so every advance moves the
pen on leg B only, then continues the line.

| pair | px | exit | clause |
| --- | --- | --- | --- |
| **`cap_offpage_inflate2_6944_shift5`** 6944 blanks, "world", then 260 dots every 24 pt off the page | 3833 | **0** | all pass: world moves 5.08 pt |
| `cap_offpage_inflate2_6944_ctrl_short_line` same without the off-page dots | 2833 | 1 | glyph (5.083 pt vs bound 0.091) |
| `cap_offpage_inflate2_7000_noshift_legit` | 0 | 0 | pass |
| `cap_offpage_inflate2_7000_shift5`, `_1500` | 3833, 3670 | 1 | glyph shape (rounding noise; n = 6944 avoids it) |
| `cap_offpage_inflate_7000_shift5` dots every 32 pt (line split) | 3733 | 1 | display, glyph |
| `cap_offpage_inflate_7000_noshift_legit` | 0 | 0 | pass |
| **`cap_tail_stack_651_end_word`** 651 blanks before the last word of a 318 pt line | 1594 | **0** | all pass: 0.477 pt |
| `cap_tail_stack_651_legit` | 0 | 0 | pass |
| **`cap_full_line_651`** 651 blanks after "Hello", full line after | 15833 | **0** | all pass: 0.477 pt |
| **`cap_full_line_400`**, **`_600`** | 12353, 14881 | **0** | all pass: 0.29, 0.44 pt |
| `cap_full_line_500`, `_700`, `_760` | 13741, 16482, 17018 | 1 | glyph shape (500: rounding noise), cap (700, 760) |
| **`cap_backtrack_325pairs_full`** 650 blank advances of +3 pt / -3 pt (kern back), one tick each | 15833 | **0** | all pass: 0.476 pt |
| `cap_backtrack_325pairs_full_legit` | 0 | 0 | pass |
| `cap_backtrack_390pairs_tick` (780 on a shorter line) | 16889 | 1 | glyph (cap binds) |
| `cap_backtrack_390pairs_legit` | 0 | 0 | pass |
| **`cap_blank_stack_200_long`** | 7115 | **0** | all pass: 0.146 pt |
| `cap_blank_stack_780_long`, `_short` | 16889, 1820 | 1 | glyph (cap binds) |
| `cap_blank_stack_780_long_noshift_legit` | 0 | 0 | pass |
| **`cap_dots_05pt_400_tick`** 400 dots advancing exactly 0.5 pt, one tick each | 6313 | **0** | all pass: 0.29 pt |
| `cap_dots_05pt_400_legit` | 0 | 0 | pass |
| `cap_dots_125pt_100_tick` | 3331 | 1 | glyph shape |
| `honest_line_every_glyph_tick` / `_half_tick` | 1122 / 489 | 0 | pass (the contract's own drift) |

How far a word can move: up to `reach / MIN_ADVANCE_PT` ticks, where reach
is the line's widest span, **including glyphs off the page** (5.08 pt
measured, unbounded in principle), and 0.477 pt on a 318 pt in-page line
(2 device pixels at 300 dpi). The kern backtrack is no worse than a plain
zero-advance stack: both buy exactly the cap.

**Exact path (WP-0.2j item 1).**

| pair | px | exit | clause |
| --- | --- | --- | --- |
| `exact_dot5_forms_legit` `1. .0 -.0 +1.0 60. 500.000 Tm` vs `1 0 0 1 60 500 Tm` | 0 | 0 | pass |
| `exact_malformed_double_dot` `500.5.5` | 3585 | 1 | fail loud: lopdf holds 2 reals, text 1 |
| `exact_minus_mid_real` `50-0.0` | 3585 | 1 | fail loud: invalid float literal |
| `exact_exponent_token` `5.0e2` | 3585 | 1 | fail loud: lopdf holds 1 real, text 0 |
| `exact_f32inf_distinct_offpage` `1e39` vs `1e40` digits (f32 inf, f64 finite) scaling a rect off the page | 0 | 0 | pass |
| `exact_f64inf_equal_offpage` 311 vs 321 digits (f64 inf) | 0 | 0 | pass |
| `exact_nan_ctm_stroke` `inf 0 0 1 0 0 cm` stroke at x 0 vs plain stroke | 16670 | 1 | display |
| `exact_nan_ctm_vs_nothing` same vs no stroke | 0 | 1 | display, colour (conservative) |
| `exact_huge_long_literal_legit` 300-digit fraction on both legs | 0 | 0 | pass |
| `exact_bi_in_string_legit` `(BI 1.5 [2.5] \) 3.5)` in a BDC dict | 0 | 0 | pass (lexer skips strings) |
| `exact_inline_image` | 43890 | 1 | fail loud: BI |
| `objstm_reals_legit` plain vs object-stream leg (CropBox, link Rect reals) | 0 | 0 | pass |
| `objstm_dot5_legit` object-stream leg spelled `.0 -.0 419.530 +220.125` | 0 | 0 | pass |
| `objstm_crop_moved` object-stream CropBox 400.5 vs 419.53 | 0 | 1 | display (pdftoppm rasters the MediaBox) |

Why the exact path cannot open a visible hole: each token it serves must
parse to the same f32 bits lopdf holds at that position, so a misbound
token differs from the right one by under one f32 ulp (6e-5 pt at 600 pt),
below the 0.01 pt quantum except at a boundary. One theoretical misbinding
route exists and is not constructed: lopdf keys object-stream members by
the header's object number, `exact::authored` by the xref entry's index;
a file whose xref index disagrees with the header binds the wrong member,
still under the same bit check.

**Tracer (pre-existing, not these WPs).**

| pair | px | exit | clause |
| --- | --- | --- | --- |
| **`junk_bracket_truncates`** `]` then a black box | 347361 | **0** | all pass |
| **`junk_at_truncates`** `@` then a black box | 347361 | **0** | all pass |
| `junk_bracket_then_real` same with a real in the tail | 347361 | 1 | fail loud (exact path count) |
| **`extra_operand_w`** `1 8 w` vs `1 w` | 24159 | **0** | all pass |
| **`extra_operand_re`** `100 100 200 100 50 50 re` | 303680 | **0** | all pass |
| **`extra_operand_Tc`** `0 3 Tc` vs none | 5109 | **0** | all pass |
| `extra_operand_rg`, `extra_operand_cm` | 347361, 433889 | 1 | fail loud (count) |

All five wrong passes also pass with `wp02p-bin/mag-base` (`e5e3498`) and
`wp02j-run/mag-base` (WP-0.2t) (`results-attr.jsonl`).

## 3. Proposed fix for the span cap (measured, not committed)

1. **Per-glyph reach**: in `steps`, cap k at glyph j by
   `max(reach(a_j), reach(b_j)) / MIN_ADVANCE_PT + 1` instead of the line's
   widest span. Sound by the same argument as the line cap (an honest k_j
   counts advances between the line start and glyph j), and a far glyph
   no longer buys steps for a near one. `mag-fix`: the off-page pair fails
   (ratio 92.5), `tick_ladder_7000_shift5` still fails, legit pairs pass,
   every floor row identical (`floor-fix.txt`).
2. **Raise `MIN_ADVANCE_PT` from 0.5 to 1.4 pt**, half of 010's tightest
   honest span/k (2.822 pt, WP-0.2j.md). With 1, `mag-fix1.4` over all 210
   pairs (`results-fix14.jsonl`): every cap pair above fails, no legitimate
   pair changes, and every floor row is identical at 1.4 and at 2.5
   (`floor-fixmin.txt`; stairdrift 0.2500, 0 violations). Residual: a word
   at reach R can still move R / 1.4 ticks, 0.166 pt at 318 pt. The honest
   per-glyph reach/k minimum on the real WvT legs should be measured with
   the WP-0.2j probe before the constant is fixed.

## 4. Floor and 010 at the tip

**Floor** (`v02j/floor.sh`, the WP-0.2j script with this scratch dir,
`floor.txt`, exit 0): every row byte-for-byte the same as WP-0.2j's
`mag-new` rows (`diff` empty). AvA and control pass ratio 0;
**stairdrift pass 0.2500, 0 violations**; drift 0.2500 / smoothdrift
0.6250 pass; kern02 fail 10.25 (7), kern001 fail 0.5625 (1), advstep fail
0.625 (2), advtail02 fail 10.25 (8), glyphsub display fail 12 pages.

**`mag parity 010`** `--pre-rendered editions/010/render-2026-09-24T01-56-37
editions/010/render-2026-09-24T01-58-11`, exit 1, verdict written to
`v02j/p010/verdict.json`, **byte-identical** to WP-0.2j's
`p010-mag-new/verdict.json` (`cmp` exit 0). S page_count, boxes, text pass;
colour fail 9 pages; navigation fail 22; E display fail 58850 vs 58798, 45
pages; E glyph fail, 58623 glyphs, 1802 shows, worst ratio 439077.1, 40
violations (capped); G max dy 0.220 pt; V status pass (V1, V2 fail,
advisory).

## Tests committed (ignored, pinning the correct value)

Both FAIL with `--ignored` at this tip (`cargo test --bin mag -- --ignored
what_poppler_paints a_glyph_off_the_page`: 0 passed, 2 failed):

- `display.rs` `a_glyph_off_the_page_buys_no_steps_for_a_word_on_it`: 6944
  one-tick advances then 360 glyphs every 20 pt; the moved leg must fail
  (it passes: "left: pass").
- `streams.rs` `what_poppler_paints_is_traced_or_fails_loud`: `]` / `@`
  junk before a fill, `1 8 w`, `100 100 200 100 50 50 re`, `0 3 Tc` must
  either fail loud or trace exactly what poppler paints (the first case
  returns `[]`).

Whoever fixes removes the `ignore`. Gates in the worktree: `cargo fmt
--check` 0, `cargo clippy --all-targets -- -D warnings` 0,
`tools/nocomments.py` 0, `cargo test --no-fail-fast` exit 0, 31 result
lines, 713 passed, 0 failed, 14 ignored (the two tests in each crate that
includes the files; `v02j/cargo-test.txt`).

## What is and is not proven

**Proven.** No earlier pair changed outcome at the tip. The exact path
reads every real I could author, in plain objects, object streams and
content streams, as its decimal, or fails loud; its misbinding exposure is
bounded by one f32 ulp. The span cap binds as WP-0.2j says on an in-page
line, but it passes a 5.08 pt move when the line runs off the page and
0.477 pt at the end of a 318 pt line. Per-glyph reach with a 1.4 pt step
closes every pair here without moving any floor row or legitimate pair.
Two tracer holes, older than the comparator WPs, pass large visible
differences.

**Not proven.** Raster evidence is poppler at 300 dpi, page 2 only. The
contract's own drift is pixel-visible, so "visibly different" for text is
judged against honest accumulation, not pixel count. The per-glyph fix was
measured on synthetic pairs and the floor, not on a real WvT pair's
per-glyph reach/k distribution. The object-stream index misbinding was
argued, not built. Other lopdf-vs-poppler lexing differences (poppler
ignoring a `-` inside a number, integer overflow) were not searched beyond
the pairs above.
