# WP-0.2a verification

## Verdict

ACCEPTED.

## Commits

- Worker: 39158cd (diff base 81b8de3)
- Critiquer amendment: e9c6953 (geometry.rs fail-loud fix + evidence
  negative-check section)
- Verified state: e9c6953, fresh worktree, detached checkout

## Owns check

`git diff --name-only 81b8de3..e9c6953` lists exactly: mag/Cargo.lock,
mag/Cargo.toml, mag/src/main.rs, mag/src/parity.rs,
mag/src/parity/geometry.rs, mag/src/parity/text.rs,
meta/verification/baseline.json, meta/verification/evidence/WP-0.2a.md,
meta/verification/parity.yaml. All within Owns (baseline.json is this WP's
sanctioned schema-and-empty-state exception; the main.rs hunk is only the
`mod parity;` line, the `Parity` clap variant with help text, and its
dispatch arm, per the orchestrator grant recorded in the evidence
Residuals). baseline.json verified as schema note, page-entry shape, null
digest, empty pages map. No *.verify.md touched.

## Replay

From the worktree with the run dir copied in, per evidence ## Commands:

- cargo build; two renders of 010 with --no-model produced
  render-2026-09-14T02-21-39 (A) and render-2026-09-14T02-22-44 (B).
- cargo fmt --check, cargo clippy --all-targets -D warnings, cargo test:
  all green.
- A vs A: page_count pass (56/56), boxes pass (0 mismatches), text pass
  (0 pages differ), tier G max dx/dy 0.000, beyond G1/G2 0, structure
  mismatches 0, exit 0. Two runs produced byte-identical verdict.json
  (sha256 62d367cf05b52c0d1355724fc52d636a43486d79606c3bff9365ba5196ca29ed).
- A vs B: identical all-pass results, exit 0; verdict differs from the
  A-vs-A verdict in exactly one leaf, inputs.b_reader_sha256 (checked with
  a full JSON diff).
- Digest note: my verdict digests differ from the evidence's (38de6b73...,
  2d6bfbfe...) because regenerated PDFs differ byte-wise in dates and
  trailer ID, so the recorded input sha256 leaves differ. What the evidence
  binds is determinism over its own inputs and the clause results; both
  reproduced exactly (byte-identical verdicts across same-input runs;
  identical tier summaries clause for clause).
- Negative checks replayed (pdfseparate/pdfunite fixtures per the
  evidence's critiquer section): dropped last page gives page_count fail
  (56 vs 55), exit 1, later clauses unevaluated; pages 10/11 swapped gives
  page_count and boxes pass, text fail on exactly 2 pages, tier G
  structure mismatches 2, exit 1.

## Audit

- verdict.json carries no timestamps, durations, hostnames, or absolute
  paths (inputs are content digests).
- not_evaluated clauses name their owning WPs (code_blocks: WP-0.2b input
  level / WP-3.3 fixture; color and navigation: WP-0.2b; critic: WP-2.0b
  oracle leg / WP-5.3g typst leg; tier V: WP-0.2c; tier E: WP-0.2b display
  list / WP-0.2c raster).
- parity.yaml tiers tables carry only plan-stated values (boxes 0.05 pt,
  G1 2.0 / G2 0.5, V 300 dpi / 24 channel delta / 1% and 0.1%, E quanta
  0.01 pt and 0.5 pt link rects, raster_bound deferred to WP-0.2d).

## Discrepancies

None.
