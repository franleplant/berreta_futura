# WP-0.2u comparator rework: per-glyph span cap, strict decode, exact arity

Worker, from `art_directed` `efaa065`. Inputs: `WP-0.2j.verify.md` (the
span-cap rejection, its proposed fix, the two tracer holes) and its harness
under `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/v02j/h` (210 pairs).

## What changed

1. **Per-glyph span cap** (`display.rs`, `steps`). k at glyph j is capped
   by `max(reach(a_j), reach(b_j)) / MIN_ADVANCE_PT + 1`, where reach is
   the glyph's own distance from its line start, instead of the widest
   reach on the line. A glyph off the page (or anywhere further along the
   line) no longer buys steps for a glyph before it; nothing else about a
   line feeds the cap, so an off-page glyph contributes nothing to any
   on-page glyph's allowance.
2. **`MIN_ADVANCE_PT` 0.5 -> 1.25 pt**, not the verifier's 1.4. Reason:
   1.4 exceeds 010's smallest real advance, 1.2518 pt typst / 1.2580 pt
   WeasyPrint (WP-0.2j.md, probe binary), which breaks the cap's soundness
   argument ("no advance moves the pen less than MIN"). 1.25 is the largest
   round value under every real advance. Measured against honest lines
   (below), it sits 2.46x under the tightest honest per-glyph reach/(k-1).
   The literal reading "largest value below every honest span/k" would be
   3.07 pt, a 0.3% margin on one edition; I did not take it. The
   verifier's pairs give the same exit at 1.25 as at 1.4 (section 2).
3. **Strict decode** (`streams.rs`, `Tracer::run`): `Content::decode_strict`
   replaces `Content::decode`; unconsumed input fails loud ("content stream
   holds a token lopdf cannot parse (fail loud per Tier E)").
4. **Exact arity** (`streams.rs`, `arity`): every operator the tracer
   interprets with a fixed operand count (0, 1, 2, 3, 4 or 6) must carry
   exactly that many, else "X takes n operands, got m (fail loud per Tier
   E)". `sc`/`scn`/`SC`/`SCN` stay variable and keep `paint`'s check
   against the colour space's component count; unknown operators already
   bail.

Tests:
- `a_glyph_off_the_page_buys_no_steps_for_a_word_on_it` and
  `what_poppler_paints_is_traced_or_fails_loud`: un-ignored, both pass.
  The second is tightened: each written stream (`]`/`@` junk, `1 8 w`,
  `100 100 200 100 50 50 re`, `0 3 Tc`) must now fail loud and its
  painted counterpart must trace (before, a returned `Ok` that matched
  also passed).
- `unsupported_spaces_and_wrong_arity_fail_loud`: `0.5 0.5 rg` now
  reports "rg takes 3 operands, got 2".
- `a_step_counts_each_advance_both_legs_carry_that_moves_the_pen`: the
  fixture spacing was 10,000 quanta (0.916 pt), below any real advance, so
  the new cap bound it; spacing doubled to 1.83 pt (the `ab` case 50,000 ->
  100,000). Pass/fail boundaries asserted are unchanged (k*8 passes,
  k*8+1 fails).

## Measurement: honest per-glyph reach/(k-1) on 010

Temporary probe (a stderr line per glyph with uncapped k >= 2, reverted
before commit; `grep -c PROBE src/parity/display.rs` = 0), release build,
`mag parity 010 --pre-rendered` on two render pairs
(`render-2026-09-24T01-56-37`/`01-58-11` = W/T used by WP-0.2j, and
`04-35-49`/`04-37-08`); outputs `tmp/wp02u-probe-out/`:

| pair | glyphs probed | min reach/(k-1) |
| --- | --- | --- |
| WvW, W2vW2 | 55933 | 3.0788 pt |
| TvT, T2vT2 | 55933 | 3.0790 pt |
| W2vT2 | 55620 | 3.0790 pt |
| WvT | 55520 | 3.6590 pt |

Cap binds only where reach/(k-1) < MIN. Margin: 3.0788 / 1.25 = 2.46x
(1.4 would have been 2.20x). All six runs wrote `verdict.json`, logs hold
no error line: strict decode and arity never fired on any of the four 010
legs.

## Commands and results

Binary: `tmp/v02j/mag-u` (release build of this commit's tree).

- `cargo fmt --check` exit 0; `cargo clippy --all-targets -- -D warnings`
  exit 0; `cargo test --no-fail-fast` exit 0, 31 result lines, **731
  passed, 0 failed, 0 ignored** (`tmp/wp02u-cargo-test.txt`).
- **210 pairs**: `MAG=tmp/v02j/mag-u python3 all_j.py u`, exit 0
  (`v02j/h/results-u.jsonl`). Against the verifier's
  `results-fix14.jsonl` (per-glyph reach + 1.4) exactly five pairs change,
  all 0 -> 1 by fail loud: `junk_bracket_truncates`, `junk_at_truncates`
  (strict decode), `extra_operand_w`, `extra_operand_re`,
  `extra_operand_Tc` (arity). `extra_operand_rg`/`_cm` and
  `junk_bracket_then_real` now fail loud through the new messages. Every
  cap pair fails (`cap_offpage_inflate2_6944_shift5`,
  `cap_tail_stack_651_end_word`, `cap_full_line_400/600/651`,
  `cap_backtrack_325pairs_full`, `cap_blank_stack_200_long`,
  `cap_dots_05pt_400_tick` included); every `*_legit` cap, exact and
  objstm pair passes. Pass count 63, 21 fail loud. Passes with more than 2
  px: `col_subhalf_step` and `strip_legit` (both accepted earlier) and the
  two `honest_line_every_glyph_*` contract-drift pairs. Legitimate pairs
  that fail are the verifier's list, unchanged (raw link keys,
  `clip_rot45_diamond_contains_legit`, display-side pairs).
- **Floor**: `BINS=mag-u bash tmp/v02j/floor.sh`, exit 0
  (`tmp/wp02u-floor.txt`): every row identical to the verifier's
  `floor.txt` (`diff` exit 0). AvA/control pass 0; **stairdrift pass
  0.2500, 0 violations**; drift 0.2500 / smoothdrift 0.6250 pass; kern02
  10.25 (7), kern001 0.5625 (1), advstep 0.625 (2), advtail02 10.25 (8)
  fail; glyphsub display fail 12 pages.
- **`mag parity 010`** `--pre-rendered editions/010/render-2026-09-24T01-56-37
  editions/010/render-2026-09-24T01-58-11`, exit 1, verdict written to
  `tmp/wp02u-p010/verdict.json`, **byte-identical** to the verifier's
  `v02j/p010/verdict.json` (`cmp` exit 0): glyph fail 58623 glyphs, 1802
  shows, ratio 439077.1, 40 violations; display fail 45 pages; same S/G/V.
  Log has 0 error / fail-loud lines.

## Remaining `#[ignore]` in mag/

None. `grep -rn '#\[ignore' mag/src mag/tests` exits 1 (no match), and
`cargo test` reports 0 ignored across all 31 result lines (the verifier's
run at 7bd2fcf reported 14: these two tests in each of the 7 crates that
include the files). No env-gated ignores exist.

## What is and is not proven

**Proven.** A glyph's step allowance depends only on its own reach, so the
off-page inflation pair and the in-page tail/full-line/backtrack pairs all
fail; no floor row, no legitimate harness pair and no 010 verdict byte
moved. Junk tokens and extra operands can no longer pass silently: they
fail loud, positively shown by the five harness pairs and the unit test.
Neither fires on 010's real legs.

**Not proven.** The residual remains: a word at reach R can still move
R / 1.25 ticks (0.186 pt at 318 pt). MIN_ADVANCE_PT is calibrated on 010
only; an edition with advances under 1.25 pt (smaller type) would make the
cap bind on honest lines. Strict decode rejects anything lopdf's lexer
cannot consume even where poppler would paint it correctly (conservative,
fail loud). Operators with a variable count (`sc`/`scn`) are checked
against the space's components, not a fixed number. `pdf_text.rs` and
`impose.rs` still use lenient `Content::decode` (outside this WP).
