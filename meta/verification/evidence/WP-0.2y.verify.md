# WP-0.2y verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`, clean clone `.../tmp/g41/v`, release binary.
Harness: copies of `v30g-out/h/{pdfgen,cases,run}.py`, repointed at the clone. My
pairs are in `.../tmp/g41/adv/mine.py`, and each is compared as
`mag parity 010 --pre-rendered a b`. px = pixels differing on page 2 at 300 dpi (poppler).

## Adversarial pairs of my own

| pair | px | exit | caught by |
|---|---|---|---|
| RGB image, `/Decode [1 0 1 0 1 0]` vs no Decode | 696390 | 1 | display list (paint_sha256) |
| raw Flate SMask, `/Decode [1 0]` vs none | 696390 | 1 | display list |
| `/Decode [0 1 0 1 1 0]` (blue inverted) vs all inverted | 696390 | 1 | display list |
| same image, horizontally mirrored CTM | 695556 | 1 | display list (matrix) |
| image under ExtGState `/ca 0.3` vs `/ca 1` | 696390 | 1 | fail loud ("ExtGState alpha other than 1 unsupported") |
| control: `/Decode [0 1 0 1 0 1]` vs absent | 0 | 0 | display and glyph pass |

Every pair that renders visibly differently fails, and the legit pair passes. The first
three exercise the inversion path WP-0.2y keeps ("identity or inversion"), per channel and
on an SMask. The last one is a conservative refusal, not a trace.

## Replay

`cargo test` at the tip: 953 passed, 0 failed, 0 ignored (the three formerly ignored
image-identity tests included). The gate's two staged runs pass at E. They confirm the
ratchet-target-at-HEAD guard reads a committed E.

## Injected defect

`decode_image` ignores `/Interpolate` (`streams.rs:1720`, `... && false`).
`cargo test streams::` exit 101:
`equal_paint_traces_equal_and_each_painted_key_traces_to_another_picture` and
`image_keys_poppler_paints_by_are_traced_or_fail_loud` FAILED. Restored.

## Not proven

Readers other than poppler (as WP-0.2y.md says). A graded ExtGState alpha is refused, not
compared, so an edition that uses one cannot pass Tier E until the tracer models it.
