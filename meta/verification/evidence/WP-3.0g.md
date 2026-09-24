# WP-3.0g enforcement flip (comparator WP)

Base `art_directed` `50dec1e`. Worktree `.../7d99e27f/tmp/wp30g`, target
`.../tmp/wp30g-target`, every output below under `.../tmp/wp30g-out/`. Sources:
WP-0.2i.md and parity.yaml `tiers.e.glyph_positions.floor` (synthetic floor);
WP-0.2x.md (010 green at `e1822cf`); QUEUE.md orchestrator decisions.

## What changed

- `parity.yaml` gains `ratchet:` with `target_tier: E` and the real-pair floor
  measured below. `mag/src/parity.rs` reads it (missing key fails the run), and
  `ratchet_pages` appends every measured page whose tier ranks below the target to
  `ratchet.regressions` (`below_target`), so the ratchet fails and the run exits 1.
  The verdict records `ratchet.target_tier`. Before this, a page could sit at any
  tier as long as it did not drop below its baseline entry, and the baseline held
  `none` on all 54 pages.
- `baseline.json`: all 54 interior pages (2..55) ratcheted from `none` to `E` with
  `s_clauses_passing` [page_count, boxes, text, color, navigation], taken from the
  staged run's `baseline-proposed.json` (`pre-seed/`); digest unchanged,
  `ae9d6daf...7d1f`, which is the fresh staged digest of every run below. Key
  order kept; schema_note gains one sentence naming this ratchet.
- `mag/src/parity/raster.rs`: the withdrawn raster clause's owner read "WP-0.2d
  raster_bound derivation", a derivation that will never happen (WP-0.2k target 4
  named this string). It now names the withdrawal; the summary line says rasters
  are Tier V meters only.

## (1) Real-pair per-glyph floor versus the synthetic floor

Measured with an env-gated `eprintln!` harness in `display.rs` (never committed:
`tmp/wp30g-harness.diff`, reverted with `git checkout` before any commit), run
`WP30G_DUMP=1 mag parity 010 --run editions/010/run-2026-09-13T01-34-51`, exit 0,
58623 glyph lines on stderr (`dump-run.stderr`), one per compared glyph.

| sub-check of the glyph clause | real 010 pair | synthetic floor (stairdrift, parity.yaml) |
|---|---|---|
| magnitude, worst ratio of `k x 0.000732 pt` (quantized, as gated) | **0.0000**; 0 of 58623 glyphs with a nonzero quantized drift | 0.2500 |
| magnitude, worst ratio unquantized (k > 0) | 0.002389 (page 50 glyph 64, k 1, 1.75e-6 pt) | n/a |
| raw in-line drift distribution | p50 2.8e-14 pt, p90 1.48e-6, p99 8.75e-6, p99.9 1.38e-5, max 1.75e-5 pt (0.19 quantum); 18597 exactly 0 | 0.000173 pt per glyph staircase |
| shape (one-signed, monotone) | 0 violations (every quantized sequence is all zero) | 0 violations |
| advance, one tick (10 quanta) | worst paired gap difference 0 quanta over 57109 paired glyphs (1514 show openers unpaired) | not recorded per fixture |
| line starts (display list, 0.005 pt tolerance) | worst 1.67e-4 pt | display-list equal by construction |

k ranges 0..104 (1353 glyphs at k 0). **The real pair sits inside the synthetic
floor on every sub-check, so no divergence outside Tier E's enumeration exists and
the flip proceeds.** Why it is lower rather than equal: stairdrift models WP-1.6's
realized 0.000173 pt per glyph, measured before the `WEASYPRINT_69` shim
(QUEUE.md decision, WP-3.7b.md) made the typst leg write WeasyPrint's advances;
what remains is f64 noise below one quantum. That makes the real pair useless as a
calibration of the bound (equality is not correctness: both legs now write the same
advances, right or wrong), so the bound stays mechanism-derived and stairdrift stays
the floor that must pass. Recorded in parity.yaml `ratchet.real_pair_floor`.

## (2)+(3) Target raised, baseline ratcheted

- Positive control of the wiring, before seeding (baseline still `none`):
  `tiers.g.g1_pt` set to 0.0 in the worktree's parity.yaml for one staged run
  (`control/`), restored by copy afterwards (`git diff --stat` checked): exit **1**,
  `ratchet: fail (target E, ... 47 regressions)`, all 47 of the form `page N: tier
  none is below the ratchet target E`. Every other gating clause passed in that run,
  so the exit came from the ratchet alone.
- Unmutated staged run, baseline still `none` (`pre-seed/`): exit 0, ratchet pass, 0
  regressions, proposal 54 x E. That proposal became baseline.json.
- Unit test `a_page_below_the_ratchet_target_is_a_regression_and_an_unknown_target_fails_loud`.
- `tests/parity_ratchet.rs` now runs in full against the committed E entries:
  `MODE: full, 54 committed page entries, exercising page 10 at tier E`, so the
  lowered-entry refusal (E to V2) is exercised for the first time; before this
  the committed tier was `none` and that branch printed "not exercised".

## Verify

```sh
MAG_PARITY_OUT_DIR=.../wp30g-out/v1 mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 0
MAG_PARITY_OUT_DIR=.../wp30g-out/v2 mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 0
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)          # 0, 0, 0: 32 result lines, 865 passed, 0 failed
```

Both runs (release build of `de89ba5`, fresh out dirs): staged inputs fresh
`ae9d6daf...`; `ratchet: pass (target E, 54 committed entries checked, 54
recorded, 54 measured, 0 regressions)`; S page_count/boxes/text/color/navigation
pass; E display list pass (58850 vs 58850); E glyph positions pass (58623 glyphs,
1514 shows, ratio 0.0000, 0 violations); V1, V2 pass (0.000336); E raster
`not_evaluated`. Typst reader.pdf `6709dc15...` in both, as in WP-0.2x.

Determinism: raw verdicts differ only in `inputs.a_reader_sha256` (the WeasyPrint
leg's PDF bytes, `8a2c2c44...` vs `96c049ed...`: embedded dates and trailer ID,
WP-0.1.md "PDF files themselves are not byte-identical run to run"). With that
field and render-dir timestamps / out-dir paths normalized (the latter two do not
occur), both verdicts hash `fc82287f...eda4db` (`cmp` exit 0). The two
`baseline-proposed.json` are byte-identical and JSON-equal to the committed
baseline.json.

## (4) Raster clause `not_evaluated` is what the plan intends

Plan line 3917: "**rasters are Tier V meters only** from here, which is where the
plan already said they gate nothing", with line 3861 ("per-glyph positions
(WP-0.2i), which REPLACE the raster guard as Tier E's third leg") and line 3310
(revision 15, "The raster guard is withdrawn from Tier E"). parity.yaml
`tiers.e.raster_bound.status: withdrawn`, `gates: nothing`. The comparator reports
`not_evaluated` because the key has no value, and `all_evaluated_pass` fails only
on an EVALUATED raster fail, so the clause gates nothing, as intended. Only its
stale owner label was wrong (fixed above).

## What is and is not proven

- Proven: 010 staged exits 0 with the ratchet at target E and 0 regressions, twice,
  verdicts identical after the one WP-0.1 normalization; a page below the target
  fails the run (control, exit 1, 47 named pages); the real pair's glyph drift is
  inside the synthetic floor on every sub-check.
- Not proven: the target check does not run in `--pre-rendered` or `--adhoc` mode,
  which carry no staged digest and so never reach `ratchet_pages` (unchanged
  behaviour). Tier S `code_blocks` and `critic` remain not_evaluated, so an E page
  records five of the seven S clauses. The real pair calibrates nothing about the
  bound (see (1)). QUEUE.md's "Tier V never fails on pixels ... decide at WP-3.0g"
  is a threshold question (rule 4, plan revision) and was not acted on here.
- This WP wrote baseline raises itself, as its brief directs; rule 3 reserves raises
  to verifiers, so the verifier should re-derive the proposal and confirm.
