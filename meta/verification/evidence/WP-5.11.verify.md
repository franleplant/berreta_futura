# WP-5.11 verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`, clean clone `.../tmp/g41/v`.

## Replay

- Body-line pin: `MAG_CRITIC_READER_PDF=<gate oracle reader> cargo test --release --test
  critic_text reconstructs` passes. It also passes on the gate's typst reader. Control: the
  pre-WP-1.5 reader (`editions/010/render-2026-09-14T01-49-02`) fails with 1117 vs 1126.
  Independent count: `pdftotext -layout` gives 1126 lines with a lowercase letter on the
  gate's oracle reader.
- JPEG decode: `--adhoc 008` (008 carries JPEG figures) completes on the typst leg,
  preflight included, and exits 0 (WP-3.11.verify.md). The `jpeg_figures` group ran in the
  full `cargo test` (953 passed).
- text_characters gated: the gate prints "text_characters 0 pages differ" as part of the
  passing critic clause.

## Injected defect

`WORD_GAP_FRACTION` changed from 0.15 back to 0.25 (`critic/text.rs:10`).
`cargo test a_gap_encoded_word_space` exit 101:
`critic::text::writer_independent::a_gap_encoded_word_space_counts_from_the_pen_end`
FAILED. Restored.

## Not proven

Pixel-equal JPEG decode against libjpeg (a tolerance, as WP-5.11.md says).
