# WP-0.2c raster zero-diff, report, merge calibration

## Base

0de5e02 (art_directed; code built on f015859, with only
meta/verification/evidence/WP-0.2b.verify.md landing between).

## Commands

Untracked inputs a fresh worktree needs first (paths relative to the worktree
root; the originals live in /Users/franguijarro/code/magazine):

```sh
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 editions/010/
cp -R /Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59 editions/010/
cp -R /Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-49-02 editions/010/
```

(Or regenerate the two render trees, per WP-0.1 evidence: run
`cargo run --manifest-path mag/Cargo.toml -- render 010 --no-model --run
editions/010/run-2026-09-13T01-34-51` twice; renders are proven
deterministic, but regenerated PDFs differ byte-wise in dates/trailer ID, so
verdict digests then differ in the two `inputs.*_sha256` leaves only.)

Build and lint:

```sh
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test && cd ..
```

Raster self-test, same tree twice, verdict byte-determinism:

```sh
A=editions/010/render-2026-09-14T01-47-59
./mag/target/debug/mag parity 010-selftest --pre-rendered $A $A; echo "exit $?"
shasum -a 256 output/parity/010-selftest/verdict.json
./mag/target/debug/mag parity 010-selftest --pre-rendered $A $A; echo "exit $?"
shasum -a 256 output/parity/010-selftest/verdict.json
```

A vs B (independent renders), timed for the full-run wall-clock:

```sh
B=editions/010/render-2026-09-14T01-49-02
time ./mag/target/debug/mag parity 010-ab --pre-rendered $A $B; echo "exit $?"
shasum -a 256 output/parity/010-ab/verdict.json
```

Merge calibration (scratch dir; $T is any writable scratch path):

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02c-merge
mkdir -p $T/orig/en $T/merged/en
R=$A/en/reader.pdf
pdfseparate -f 1 -l 1 $R $T/p1.pdf
pdfseparate -f 56 -l 56 $R $T/p56.pdf
cp $R $T/orig/en/reader.pdf
uv run python -c "
from pathlib import Path
from magazine.cover import replace_outer_pages
t = Path('$T')
print(replace_outer_pages(t/'orig/en/reader.pdf', t/'p1.pdf', t/'p56.pdf', t/'merged/en/reader.pdf'))
"
./mag/target/debug/mag parity 010-merge-cal --pre-rendered $T/orig $T/merged; echo "exit $?"
```

## Tool versions

Per meta/verification/parity.yaml tools: poppler 25.08.0 (pdftoppm,
pdfseparate, pdftotext, pdfinfo), rustc 1.96.0, lopdf 0.45.0 tracer, python
3.12.11 / uv 0.8.17 / pypdf 6.14.2 for the calibration leg. No new crates.

## Metrics

- Tier V self-test (A vs A, 54 interior pages at 300 dpi): worst page
  fraction 0.000000, max channel delta 0, dimension mismatches 0, V1 pass,
  V2 pass, exit 0, verdict byte-identical across two runs.
- Tier V A vs B (independent renders): worst page fraction 0.000000, max
  channel delta 0 across all 54 pages; V1/V2 pass. The two legs are
  pixel-identical at 300 dpi, not merely within threshold.
- Full-run wall-clock (A vs B, debug build, all clauses + raster + report):
  81.92 s (79.48 s user).
- Merge calibration: inner pages after replace_outer_pages are display-list
  equal and raster zero-diff (max channel delta 0) against the original;
  pypdf rewrite noise on inner pages is nil; merge_rewrite_rules recorded as
  an explicit empty list with the measurement note.
- report.html: summary tier table, clause diff tables, per-line beyond-G2
  table (empty on these runs), 108 side-by-side page previews at 54 dpi
  (9.2 MB assets), heatmaps emitted only for pages with differing pixels
  (none on these runs).

## Verdicts

- 010-selftest (A vs A):
  bc0da32c966b2106cea0e85424f2142fc41dba8773804e129d50ef158f156503
  (twice); all evaluated clauses pass, tier E raster not_evaluated
  (WP-0.2d raster_bound).
- 010-ab (A vs B):
  0d313e67d9d3a455a6b6a482c580ee6d30bf662cdd45e034ccd27bd6ccf27fc4;
  all evaluated clauses pass.
- 010-merge-cal (orig vs merged):
  291485c7e863c3fd02d9398e459a41c061761c4c7759d2ee276d372fc48c3d62;
  all evaluated clauses pass.

## Residuals

- The tier E raster guard reads `tiers.e.raster_bound.value` from
  parity.yaml; the key is absent until WP-0.2d derives it, and the clause
  reports not_evaluated naming WP-0.2d (never a default bound). WP-0.2d must
  author the numeric under that exact key.
- Tier V gating: only raster dimension equality gates the exit code (the
  plan's hard fail); V1/V2 are meters and gate nothing, matching the plan.
- The report's per-line table re-parses `pdftotext -bbox-layout` inside
  report.rs: geometry.rs keeps only per-page aggregates and is outside this
  WP's Owns, so the reporter derives its own line rows (reporter-only data,
  never used for verdicts).
- Heatmaps are 24-bit BMP (hand-rolled writer, no new crate); previews are
  pdftoppm PNGs at 54 dpi.
- pdfseparate prints "recursive dicts" syntax warnings reading the 010
  reader; extraction is correct (calibration passed end to end). Poppler
  noise, not a repo bug.
- Raster scratch lives under the OS temp dir keyed by pid and is removed
  after comparison; peak transient disk is two rasterized legs (about
  1.4 GB at 300 dpi for 54 pages).

## Critique (critiquer pass)

Two defects fixed, both verdict-neutral (the A-vs-A self-test digest below is
unchanged from the worker's run):

1. `assert_poppler` pinned `pdfinfo` and `pdftotext` but not `pdftoppm`, which
   this WP introduced as the rasterizer for the Tier V meters and the Tier E
   raster guard. A mismatched `pdftoppm` would have rasterized both legs
   outside the pinned tool set with no startup failure. `pdftoppm` now joins
   the asserted loop (banner format is identical across the three).
2. `report.rs push_gallery` guessed pdftoppm's zero padding as
   `if last >= 100 { 3 } else { 2 }`. Poppler pads by the digit count of the
   document's total page count, and the compared domain ends at `last = n - 1`,
   so a 100-page edition would emit `a-002.png` while the report linked
   `a-02.png` (broken previews, report-only). Replaced with the exact rule,
   `(last + 1).to_string().len()`.

Negative check (the worker's runs were all zero-diff, so raster sensitivity was
unproven). Fixture: 010 render B with pages 10 and 11 swapped, built with pypdf
because pdfunite output does not parse (see the finding below):

    T=<scratch>/wp02c-neg
    mkdir -p $T/swap2/en
    uv run python -c "
    from pypdf import PdfReader, PdfWriter
    r = PdfReader('editions/010/render-2026-09-14T01-49-02/en/reader.pdf')
    w = PdfWriter()
    order = list(range(len(r.pages)))
    order[9], order[10] = order[10], order[9]
    for i in order:
        w.add_page(r.pages[i])
    with open('$T/swap2/en/reader.pdf','wb') as f:
        w.write(f)
    "
    ./mag/target/debug/mag parity 010-negcheck \
      --pre-rendered editions/010/render-2026-09-14T01-47-59 $T/swap2

Measured: differing pixels on exactly pages 10 and 11, fraction 0.672317 each,
max channel delta 255 on both; the other 52 compared pages zero differing
pixels; dimension mismatches 0 (the swap preserves geometry, so the hard fail
correctly stays silent); V1 fail and V2 fail (meters, gating nothing); tier E
raster still not_evaluated pending WP-0.2d; heatmaps written for exactly
`heatmap-010.bmp` and `heatmap-011.bmp`; exit 1, driven by the text, color,
navigation and display-list clauses as expected. Report HTML audit on that run:
zero absolute paths, every `src` relative under `report/`, every referenced
asset present.

Finding for WP-0.2d (fixture construction, not a comparator defect): pdfunite
writes `/ID` as binary literal strings containing raw newlines, and the lopdf
tracer rejects the result with "invalid file trailer". The comparator fails
loud and exits 1, never a silent pass, so the behavior is correct; but seeded
faults must not be built with pdfunite. pypdf output parses (the merge
calibration above already traced a pypdf-written PDF end to end), and WP-0.2d's
planned route, rendering scratch copies of staged inputs, avoids the issue
entirely. The WP-0.2a negative checks predate the tracer and were unaffected.

Accepted without change: PPM parsing (P6 asserted, maxval 255 asserted,
comments and whitespace handled, truncated pixel data fails loud); pixel
differs at `delta > channel_delta` (exceeds, per the plan) with the max taken
per channel; V1/V2 scored on the worst page fraction against `< 0.01` and
`< 0.001`; dimension mismatch sets the tier status to fail and gates the exit
code while V1/V2 do not; the Tier E guard uses max-delta semantics over every
pixel (strictest reading of "every differing pixel within raster_bound") and
reports not_evaluated naming WP-0.2d when `tiers.e.raster_bound.value` is
absent, with no default; `verdict.json` is written before report generation and
carries no timestamps, durations, hostnames or paths; heatmap padding is
self-consistent between writer and reader. Bulk rasterization (both legs
rendered before comparison, pages deleted as they are consumed) is a
disk-for-process-spawns trade already recorded in Residuals; not changed.

Reruns after the fixes: A-vs-A self-test digest
`bc0da32c966b2106cea0e85424f2142fc41dba8773804e129d50ef158f156503`, identical
to the worker's; `cargo fmt`, `cargo clippy --all-targets -D warnings` and
`cargo test` green.

## Status

done
