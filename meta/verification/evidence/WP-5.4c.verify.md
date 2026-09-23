# WP-5.4c verification: cover PDF writer

Verifier replay at `0494017` (art_directed tip), in a fresh detached worktree.
WP landed at `a911ff1`; `mag/src/cover/pdf.rs` and `mag/tests/cover_pdf*` are
unchanged between `a911ff1` and `0494017` (`git log a911ff1..0494017` over
those paths is empty). No code was changed; mutations below were applied to a
copy of `pdf.rs` and restored, the restore asserted with `cmp`.

## Verdict

**ACCEPTED.** Every number the evidence quotes reproduces exactly, the
committed tests fail under mutations of the code they guard, and the one gap
the evidence left open against the WP's Verify clause (Tier E display-list
equality for `framed` and `honored_plate`) was measured here and holds.

## Replay of `## Commands`

Both blocks extracted programmatically from the evidence file and run from the
worktree root (which built its own `.venv` from scratch). Both exit 0.

| quantity | evidence | replay |
|---|---|---|
| `footer_caption` page sha256 | `5f498b2a...8dd1ef` | identical |
| `framed` page sha256 | `330ae10c...ef67120` | identical |
| `honored_plate` page sha256 | `02d379d8...f82e453` | identical |
| front stream bytes / back stream bytes / widths rows | 768 / 627 / 95 | 768 / 627 / 95 |
| three committed fixtures vs Python regeneration | identical | `cmp` identical, all three |
| stand-in SVG raster sha256 | `4b4549e9...8190b2` | identical |

So the committed expectations are Python's own output at this tip, not values
transcribed once and left to rot.

## Gates

- `cargo test --test cover_pdf`: 8 passed, 0 failed (exit 0).
- `cargo test` (whole tree): exit 0, 25 binaries, 258 passed, 0 failed. The
  evidence's 21 binaries was at parent `62e665a`; the tree has grown since.
- `cargo fmt --check`: exit 0. `cargo clippy --all-targets -- -D warnings`:
  exit 0.

## Mutations (each against the full `cover_pdf` binary, then restored)

| mutation in `pdf.rs` | rendered-page test | stream tests | widths test | other |
|---|---|---|---|---|
| M3: text loop iterates nothing (row A replicated) | **pass** | front FAIL, back FAIL | pass | refusal test FAILs (the refusal lives in the loop) |
| M4: `real()` bypasses `fp` (row E replicated) | pass | back pass; front FAILs on its `/MediaBox` assertion | **FAIL** | |
| M2 (mine, not in the evidence): SMask alpha forced to 255 | **FAIL, 3 of 3 layouts reported** | pass | pass | |

M3 confirms the headline claim: removing the whole invisible text layer leaves
all three rendered-page hashes equal to Python's, so the stream oracle is not
redundant. M2 is a class the evidence did not probe (a wrong soft mask) and
only the rendered-page oracle catches it, reported for all three layouts, so
the accumulate-then-assert harness works as claimed. M4 fails the widths test
as claimed; it also fails the `/MediaBox` assertion, which the evidence's row
E does not list. That is extra coverage, not a contradiction. The "36 of 95
rows" count under E was not re-derived.

## Tier E tracer, extended to what the evidence left unmeasured

A throwaway test (never committed, moved out of the tree afterwards) included
`parity/display.rs` + `parity/streams.rs`, built the font map from
`parity.yaml`, wrote the Rust PDFs through the committed test's own builders,
and compared them against the Python PDFs the replay produced:

| face | `compare_display` | `compare_glyphs` | `compare_color` |
|---|---|---|---|
| `footer_caption` | pass, 8 v 8 | pass, 166 glyphs, 5 shows, worst excess 0.000000 pt | pass, 7 |
| `framed` | pass, 8 v 8 | pass, 166 glyphs, 5 shows, worst excess 0.000000 pt | pass, 7 |
| `honored_plate` | pass, 8 v 8 | pass, 166 glyphs, 5 shows, worst excess 0.000000 pt | pass, 7 |
| back | pass, 7 v 7 | pass, 117 glyphs, 5 shows, worst excess 0.000000 pt | pass, 6 |

Positive control: Python `footer_caption` against Rust `framed` gives
`compare_display` **fail**, 1 page differing, so the display clause sees the
raster (it hashes decoded pixels) and the passes above are not vacuous. The
`footer_caption` row reproduces the evidence's one-off measurement exactly.
The branch then took WP-0.2m (`bdbcebf`), which rewrites
`mag/src/parity/streams.rs`, before landing; the table and the control were
re-run on the rebased tree with that tracer and came out identical.

This makes the WP's Verify clause, display-list equality and raster equality
for all three modes, met: raster by the committed test, display list by this
verifier measurement. It remains a one-off, not a committed test; WP-5.4g is
where it becomes one.

## Claims checked against the tests

- The rendered-page test hashes decoded PNG pixels from `pdftoppm -r 72`, as
  stated; expected hashes are literals in the test and match the replay.
- The stream tests compare the normalized stream to `include_str!` fixtures;
  `the_normalizer_only_loosens_the_python_side` does assert the writer emits
  none of the three reportlab-only tokens and that normalize round-trips, as
  claimed.
- The widths test slices `/Widths[` out of the PDF bytes and compares the
  serialized tokens, so the read-side re-rounding defect the evidence records
  is genuinely gone (M4 fails it).

## Findings (none blocking)

1. **Count domain unlabelled.** "`cover_pdf` 8" is the binary's count: the file
   holds 7 `#[test]`s and the eighth is `metrics::exif_tests`, pulled in by
   `#[path = "../src/critic/metrics.rs"]`. Revision 63's domain rule, which
   post-dates this evidence, asks a count to say which.
2. **Latent scratch collision in `page_hash`.** Its directory is keyed by
   process id only (`wp54c-<pid>/cover.pdf`, `page.png`), and tests in one
   binary run as threads of one process. Only one test calls it today, and it
   calls it serially, so no race exists now; a second caller would race. The
   directory is also never removed.
3. **Class C inheritance, disclosed by the WP and confirmed:** the five back
   lines and the pre-wrapped deck are transcribed from Python, so the back
   stream test cannot see a copy defect Python shares. Owner WP-5.6 as stated.

## What is and is not proven

PROVEN here, independently: every hash and byte count in the evidence at
`0494017`; that the three fixtures equal fresh Python output; that the
committed tests discriminate text-layer deletion, widths precision and
soft-mask corruption; Tier E display, glyph and colour equality for all three
front layouts and the back face, with a failing control.

NOT PROVEN, same as the evidence: the back cover's rendered page, back copy
derivation, any Spanish cover, deck wrapping, `design.toml` loading, the font
program and descriptor reals, width entries above 126. The Tier E rows above
are a one-off verifier measurement, not a committed guard.
