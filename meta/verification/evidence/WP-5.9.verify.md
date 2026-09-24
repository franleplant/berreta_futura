# WP-5.9 verification

Verdict: **ACCEPTED**

Verified at art_directed `01ca472`, fresh worktree. Commits `14c7ed5`
(metrics.rs only), `2308fea` (rules.rs, contact.rs), `d8c6478` (web_port
test + wfx fixture), `55788d8` (pdf_text test), evidence `394e0c4`.

## Replay

- Full suite: `cargo test` exit 0 (31 binaries, 637 passed);
  fmt and clippy `-D warnings` exit 0.
- `thumbnail_matches_pillow_when_the_reduce_factor_leaves_a_remainder`:
  passes, and it does run Pillow live through `uv run python`; digest pinned
  `512 16 e0873635...2486fd`, as in the evidence.
- `cargo test --test package` (gated, see WP-5.5c.verify.md): both contact
  sheet tests green, 0 differing channel bytes through the shared
  `rules::write_png`.
- `web_port` 15 passed; `pdf_text` 15 passed.

## Injected defects (mine)

1. `semantic.rs` ordered-list start: `*start != 1` to
   `*start != 1 && *start != 0` (drop `start="0"`): web_port 7 of 15 FAIL.
2. `pdf_text.rs` OCR guard: `it.images > 0` to `it.images > 1`: both scan
   tests FAIL, including the new inline-image one.
3. `metrics.rs` scale computed as `f64::from(in1) - f64::from(in0)` (f64
   subtraction of the f32 box): SURVIVES. This is an equivalent mutant on
   every reachable input: both callers pass a box with `in0 = 0`, so
   `in1 - in0 == in1` in either precision. Not a defect of the WP; noted
   because it is the one place Pillow's float subtraction is unpinned.

All restored, `git status` clean.

## What is and is not proven

Proven: all four items behave as claimed and three of them are pinned by a
test that a fresh mutation breaks. Not proven: the f32 subtraction for a
non-zero box origin (unreachable today), and metrics.rs on real edition
images with a remainder factor (as the evidence says).
