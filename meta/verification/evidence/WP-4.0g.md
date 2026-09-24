# WP-4.0g ad hoc parity mode

## What changed

- `mag parity --adhoc <NNN> --run <dir>` (`mag/src/main.rs`, flag lines
  only: `edition` becomes optional, required unless `--adhoc`; `--adhoc`
  conflicts with a positional edition, `--pre-rendered`, `--oracle-only`).
- `mag/src/parity.rs`, under `Options.adhoc`:
  - no baseline: `guard_baseline` is not read, the staleness refusal is
    skipped (`staleness.status = "adhoc"`, digest still recorded), no page
    measurement, no `baseline-proposed.json`; `ratchet.status = "adhoc"`.
  - both legs render fresh: the oracle cache is not consulted (it is still
    written, keyed by digest as before). Both legs go through
    `render_leg`, i.e. `mag render --no-model`, so a pending figure anchor
    aborts the run listing the anchors (WP-0.0 behaviour); anchors are
    resolved through the normal pipeline before, never by parity.
  - output goes to `output/parity/<NNN>-adhoc` (or `MAG_PARITY_OUT_DIR`),
    never over the baseline run's `verdict.json`.
  - exit status gates on Tier S alone (`tier_s_pass`: typst leg rendered,
    page_count, boxes, text, color, navigation). Tier E, G, V are computed
    by the same `build_verdict` and reported, informational.
    `all_evaluated_pass` now calls `tier_s_pass` for its Tier S half
    (same conditions as before). New verdict field `gate`:
    `"tier_s"` (ad hoc) or `"all_tiers"`.
  - the ratchet tail of `compare` moved into `ratchet_pages` unchanged.
- Tests: `the_adhoc_gate_is_tier_s_alone_so_tier_e_and_v_failures_only_inform`,
  `an_adhoc_run_writes_beside_the_baseline_run_never_over_it` (parity.rs),
  `adhoc_stands_in_for_the_edition_and_refuses_the_baseline_modes`
  (main.rs, clap parse and conflicts).

## Verify: `--adhoc 010` agrees with `mag parity 010` clause for clause

Run from the worktree at fe1bd56 plus this change, run dir
`editions/010/run-2026-09-13T01-34-51`, each with its own
`MAG_PARITY_OUT_DIR` (fresh dirs, so neither used an oracle cache).

- `mag parity 010 --run ...` exit **1** (3m23s). Staleness `fresh`,
  digest `ae9d6daf...7d1f`, ratchet `pass` (54 committed, 54 measured,
  0 regressions).
- `mag parity --adhoc 010 --run ...` exit **1** (3m11s). Staleness
  `adhoc`, same digest, ratchet `adhoc`.

Both print identical clause lines: page_count pass 56 vs 56; boxes pass
(162 boxes, 0 mismatches); text pass (54 pages, 0 differ); color pass
(58800 entries); navigation **fail** (21 mismatches); tier G max dx
0.003 pt, dy 0.006 pt; glyph positions fail (40 violations, worst excess
314.425232 pt); display list fail (45 pages differ); tier V V1 pass, V2
fail, worst fraction 0.008865; raster not_evaluated.

Section-level `jq -S` diff of the two `verdict.json` files:
`tier_s`, `tier_g`, `tier_v`, `tier_e`, `page_sets`, `domain`,
`staged_input_digest`, `self_comparison`, `typst_leg`, `mode` equal.
Differ, by design: `gate`, `ratchet`, `staleness`. Also `inputs.a_reader_sha256`
differs (WeasyPrint reader bytes differ between two fresh renders, the
known timestamp-shaped keys WP-0.1 normalizes; the typst sha
`471998f3...` is identical across the two runs).

Both exit 1 for the same Tier S reason: navigation fails on 010 at this
sha (21 mismatches). That is the current state of the typst leg, owned
by the typeset work in flight, not by this WP; ad hoc mode reports it
rather than hiding it.

## Observation: other editions (expected to diverge)

- **009** (`run-2026-09-08T17-10-16`): exit 1 before any comparison. The
  weasyprint leg refuses the edition: closing plate 'The Listening Shell'
  repeats the art of 'The Shell at Low Tide'. Edition data, not the
  comparator.
- **007** and **008**, as committed: exit 1, weasyprint leg refuses: "No
  committed source code for article ...; regenerate
  editions/<id>/source-codes". Only 010 has `source-codes/` committed.
- **008** with `tools/sourcecodes.py 008` run in the worktree only (not
  committed): both legs render (44 pp each, per-article page counts
  equal), then the comparator fails: `tracing page 6 of <oracle>/reader.pdf:
  operator Do: decoding image: filter DCTDecode unsupported`. The Tier E
  display-list tracer (`parity/streams.rs` `decode_stream`) has no JPEG
  decoder; 008 embeds 4 JPEG images on both legs. Color and navigation
  (Tier S) come from the same extraction, so no verdict is written.
  Adding a decoder needs a Cargo dependency and its own fixture; not done
  here (scope). Measured gap: `--adhoc` cannot evaluate any edition whose
  art includes a JPEG.
- 008 divergence classes seen by hand (`pdftotext`, `pdfimages`, pages
  2..43): 10 pages differ in `-layout` text, 5 (16-20) in word stream.
  Top classes: (1) heading line breaks ("The Pen Moves Faster / Than
  Review" vs "... Than / Review", p4); (2) text order within a page
  (figure label "PRICE PER TOKEN" and running head emitted in different
  stream order, p16-20); (3) cover and back cover (p1, p44, outside the
  interior domain) carry a 1748x2480 image + smask on the oracle and no
  image on the typst leg.

## Commands and status

- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`: clean.
- `cargo test` in `mag/`: all suites ok (208 in the bin, 0 failed).
- The 010 runs used a build that also attached a hint to leg failures;
  it was removed before the 009/008 reruns because it misattributed
  non-anchor failures. Clause computation is unaffected by that line.

## What is and is not proven

- Proven: on 010 the ad hoc mode computes the same clauses as the baseline
  mode, with no baseline read or written, both legs rendered fresh, and
  exit status set by Tier S alone (unit test pins that Tier E/V failures
  do not fail it and a Tier S or typst-leg failure does).
- Not proven: that `--adhoc` works on any edition but 010. Every other
  edition tried fails first on edition data (009 art repeat, missing
  source-codes) and then on the comparator's missing DCTDecode support.
  WP-4.2's "`--adhoc` on the in-flight edition" depends on both.
- Equality is not correctness: both modes agreeing on navigation fail is
  a real typst-leg defect at this sha, not a comparator artefact.
