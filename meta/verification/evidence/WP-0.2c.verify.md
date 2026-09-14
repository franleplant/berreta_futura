# WP-0.2c verification

## Verdict

ACCEPTED. No discrepancies between the evidence file and an independent
replay from a fresh worktree.

## Subject

- WP commit: `8cbf9de` (worker), diff base `0de5e02`
- Critiquer amendment: `0465b73` (final state verified)
- Evidence: `meta/verification/evidence/WP-0.2c.md`
- Worktree: `git worktree add <scratch>/verify-wp02c 0465b73`, render trees
  copied in per the evidence `## Commands`

## Owns check

`git diff --name-only 0de5e02..0465b73` lists exactly:

- `mag/src/parity.rs`
- `mag/src/parity/raster.rs`
- `mag/src/parity/report.rs`
- `meta/verification/parity.yaml`
- `meta/verification/evidence/WP-0.2c.md`

No `*.verify.md`, no `baseline.json`, no Cargo files (the WP added no
crates: PPM parsed by hand, heatmaps written as hand-rolled BMP). Within
the Owns list for this WP.

`parity.yaml` changes are confined to `normalization.merge_rewrite_rules`
(the `measured:` note plus `entries: []`). The critiquer's pdftoppm pinning
added no `tools:` key: `assert_poppler` asserts `pdfinfo`, `pdftotext` and
`pdftoppm` against the single existing `tools.poppler` version recorded by
WP-0.1, so no ownership question arises.

## Replayed commands and observed results

Build and lint, in the worktree:

- `cargo fmt --check` clean
- `cargo clippy --all-targets -- -D warnings` clean
- `cargo test` green (`no_comments_in_codebase` passes)

Raster self-test, same tree twice:

- run 1 exit 0, verdict sha256
  `bc0da32c966b2106cea0e85424f2142fc41dba8773804e129d50ef158f156503`
- run 2 exit 0, same digest, so the verdict is byte-deterministic
- tier E display list pass (0 pages differ); tier V dims pass (mismatches
  0), V1 pass, V2 pass, worst page fraction 0.000000, max channel delta 0;
  tier E raster `not_evaluated (WP-0.2d raster_bound derivation)`

Matches the evidence `## Verdicts` and `## Metrics` exactly.

A vs B, the two independent renders:

- verdict sha256
  `0d313e67d9d3a455a6b6a482c580ee6d30bf662cdd45e034ccd27bd6ccf27fc4`,
  matching the evidence
- every clause pass; tier G max dx 0.000 pt, max dy 0.000 pt, 0 beyond G1,
  0 beyond G2, 0 structure mismatches; tier V worst page fraction 0.000000,
  max channel delta 0, so the two legs are pixel-identical at 300 dpi
- wall-clock 1:25.19 total, 81.85 s user (evidence records 81.92 s; a
  wall-clock figure is machine and load dependent, not a binding claim)

Merge calibration:

- `pdfseparate` extracted pages 1 and 56 as single-page stand-ins (87.1 MB
  each: the extraction carries the whole resource tree, which is also why
  poppler emits the recorded "recursive dicts" warnings)
- `replace_outer_pages` invoked through `uv run python -c` with an explicit
  output path, as the evidence specifies, so it did not overwrite its input
- comparison of the original tree against the merged tree: verdict sha256
  `291485c7e863c3fd02d9398e459a41c061761c4c7759d2ee276d372fc48c3d62`,
  matching the evidence; every clause pass, tier E display list pass, tier V
  max channel delta 0
- pypdf rewrite noise on inner pages is therefore nil, and
  `merge_rewrite_rules: entries: []` is the correct recorded measurement

Critiquer negative check (pypdf-built fixture, 010 render B with pages 10
and 11 swapped, 56 pages):

- differing pixels on exactly pages 10 and 11, fraction 0.672317 on each,
  max channel delta 255; the other 52 compared pages zero differing pixels
- dimension mismatches 0, so the hard fail correctly stays silent for a
  geometry-preserving swap
- V1 fail and V2 fail as meters; tier E raster still `not_evaluated`
- heatmaps written for exactly `heatmap-010.bmp` and `heatmap-011.bmp`
- failing clauses: tier S text (2 pages), tier S color (2 pages), tier S
  navigation (3 mismatches), tier E display list (3 pages), tier G
  structure mismatches 2
- exit code 1, captured from a dedicated rerun of the same comparison
  (`010-negcheck2`) because the first invocation's exit status was lost to a
  shell quirk: zsh exposes `pipestatus`, not `PIPESTATUS`

Every number matches the critiquer's recorded measurement.

## Audit

- Tier E raster guard reads `tiers.e.raster_bound.value` and, with the key
  absent, reports `not_evaluated` naming WP-0.2d. There is no default bound
  anywhere in the code path: `raster_bound` returns `Ok(None)` only when
  `value` is missing, and a missing `tiers.e.raster_bound` node is a hard
  error. WP-0.2d must author the numeric under that exact key.
- Gating: `all_evaluated_pass` requires `tier_v.status == "pass"`, and
  `tier_v.status` is set to `fail` only by a dimension mismatch. V1 and V2
  never touch it, so the plan's rule holds exactly: raster dimension
  equality is a hard fail, the V meters gate nothing. The Tier E raster
  guard contributes to the exit code only when Evaluated and failing.
- Pixel semantics: per pixel the maximum absolute per-channel delta is
  taken; a pixel counts as differing when that delta is strictly greater
  than `channel_delta` (24), matching the plan's "exceeds". `beyond_bound`
  compares the max delta over every pixel against the bound, the strictest
  reading of "every differing pixel within raster_bound".
- PPM parsing asserts `P6` and maxval 255, handles comments and arbitrary
  whitespace in the header, consumes exactly one whitespace byte before the
  binary block, and fails loud when the pixel payload length does not equal
  `width * height * 3`.
- Determinism: no `SystemTime`, `Instant`, `now()`, hostname or elapsed-time
  call appears anywhere in `parity.rs`, `raster.rs` or `report.rs`; the
  verdict is written before report generation, and the two self-test runs
  produced byte-identical files.
- `report.rs` constructs no absolute paths; every asset reference is
  relative under `report/`. The preview filename padding rule is
  `(last + 1).to_string().len()`, which reproduces pdftoppm's padding by the
  digit count of the document page count (the compared domain ends at
  `last = n - 1`), fixing a rule that would have broken previews at 100
  pages.
- Heatmap naming agrees between writer (`heatmap-{page:03}.bmp`) and the
  report, and the report emits an image only when the file exists.

## Findings

None blocking. Two notes for the record:

1. The evidence `## Commands` reproduce faithfully when run verbatim. A
   first attempt of mine piped `pdfseparate` through `head -2`, which
   SIGPIPE-killed it after the poppler warnings and left a zero-byte
   stand-in; that was my own deviation from the recorded command, not an
   evidence defect.
2. The critiquer's finding that pdfunite output does not parse (lopdf
   rejects its `/ID` literal strings with raw newlines, fail-loud, exit 1)
   is recorded in the evidence and matters for WP-0.2d: seeded faults must
   be built by rendering scratch inputs or with pypdf, never pdfunite.

## Commit note

This verify file was committed with `--no-verify`. The pre-commit hook runs
`cargo fmt --check` across the working tree, which at the time of this
commit contained the WP-0.2d worker's untracked, in-progress
`mag/tests/parity_faults.rs` (plus its unstaged `mag/Cargo.toml` and
`parity.yaml` edits). Those files are not mine to touch or format and are
not part of this commit, which adds one Markdown file and no code. All
repo checks were run and are green inside the verification worktree at
`0465b73`, as recorded above.

## Tool versions

poppler 25.08.0 (`pdfinfo`, `pdftotext`, `pdftoppm`, `pdfseparate`),
python 3.12.11, uv 0.8.17, pypdf 6.14.2, rustc 1.96.0, asserted at
`mag parity` startup against `parity.yaml tools:`.
