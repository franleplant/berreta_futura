# WP-4.0g verification

Verdict: **ACCEPTED**, with one test gap the orchestrator must queue (below).

Verified at art_directed `b7f7791` (contains `baa65a1`), fresh worktree,
debug build, run dir `editions/010/run-2026-09-13T01-34-51`, each run with
its own fresh `MAG_PARITY_OUT_DIR`.

## Replay of the Verify clause

- `mag parity 010 --run ...`: exit 1 (3m57s). Staleness `fresh`, digest
  `ae9d6daf...7d1f`, ratchet `pass` (54/54/54, 0 regressions),
  `baseline-proposed.json` written.
- `mag parity --adhoc 010 --run ...`: exit 1 (4m01s). Staleness `adhoc`,
  same digest, `baseline: null`, ratchet `adhoc`, no
  `baseline-proposed.json` in its out dir, `gate: tier S only` line printed.
- Key-by-key `jq -S` diff of the two `verdict.json`: equal `domain`,
  `edition`, `mode`, `page_sets`, `self_comparison`,
  `staged_input_digest`, `tier_e`, `tier_g`, `tier_s`, `tier_v`; the
  concatenation `[tier_s, tier_e, tier_g, tier_v]` hashes to
  `aca1ea37...e1aa` on both. Differ: `gate`, `ratchet`, `staleness` (by
  design) and `inputs.a_reader_sha256` only (`1881b2c8...` vs
  `74958af9...`, two fresh WeasyPrint renders; `b_reader_sha256` equal).
- Clause statuses, identical on both: page_count pass (56 vs 56), boxes
  pass, text pass, color pass, navigation **fail** (21 mismatches),
  code_blocks and critic not_evaluated; tier E display_list fail (45
  pages), glyph_positions fail (40 violations, worst 314.425232 pt), raster
  not_evaluated; tier V dims pass. Same numbers as the worker's evidence at
  its older base.
- Both exit 1 for the same Tier S reason (navigation). Equality is not
  correctness: navigation failing on 010 is a real typst-leg defect, not
  this WP's.
- Fresh-render claim, with a positive control: re-running `--adhoc` into
  the out dir that now holds `oracle-cache.json` printed no `oracle leg:
  cached` (0 matches) and rendered the oracle again; re-running the
  baseline mode into its own out dir printed `oracle leg: cached` (1
  match). A third adhoc verdict hashes to the same `aca1ea37...`.

## Suite

`cargo test` exit 0, 32 binaries, 740 passed, 0 failed; `cargo fmt
--check` 0; `cargo clippy --all-targets -- -D warnings` 0.

## Injected defects (mine)

Caught:
1. Adhoc exit uses `!opts.adhoc` (gate swapped): `parity_concurrent`
   FAILS (equal pair exits nonzero).
2. `--adhoc` no longer conflicts with `--pre-rendered`: the clap test FAILS
   at main.rs:422.
3. Adhoc out dir named `<NNN>` instead of `<NNN>-adhoc`: FAILS at
   parity.rs:1642.
4. Control: drop the `text` conjunct from `tier_s_pass`: the gate test
   FAILS.

**Survived** (the gap):
5. Drop the `navigation` conjunct from `tier_s_pass`: full `cargo test`
   green.
6. Drop `page_count`: `cargo test --bin mag` green (208 passed).
7. Drop `color`: `cargo test --bin mag` green.
8. Consult the oracle cache in adhoc mode (remove the `filter`): full
   suite green; only the live rerun above pins it.

Navigation is exactly the clause that sets `--adhoc 010`'s exit today, so
mutant 5 would turn the live 010 run green with no test failing. The same
conjuncts were unpinned inside `all_evaluated_pass` before this WP, so the
gap is inherited, but `tier_s_pass` is the WP's new gate and its test pins
only `text` and `typst_leg`. Not a rejection: the live runs prove the
clauses are present at this sha. **Follow-up to queue**: extend
`the_adhoc_gate_is_tier_s_alone...` to fail each of page_count, boxes,
text, color, navigation in turn (a loop, a few lines).

## What is and is not proven

- Proven: on 010 the two modes compute identical clauses at this tip, ad
  hoc reads no baseline, writes no proposal, re-renders both legs even
  with a cache present, and exits on Tier S.
- Not proven: any edition other than 010 (worker's DCTDecode and
  edition-data blockers stand, not re-run); that the gate refuses a
  page_count, boxes, color or navigation failure under test (mutants 5-7).
