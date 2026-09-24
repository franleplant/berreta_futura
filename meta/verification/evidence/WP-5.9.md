# WP-5.9 evidence: Phase 5 cleanup batch

Four small fixes, one commit each, on top of b31d651.

## 1. `critic/metrics.rs::resize` box as C float

`precompute_coeffs` now takes `in0, in1` as `f32` and computes
`scale = f64::from(in1 - in0) / out_size`, the same shape as Pillow's
`precompute_coeffs(float in0, float in1)` and as `package/contact.rs`
(finding 1 of `WP-5.5c.md`). `resize` keeps its f64 signature and casts
the box at the call, which is what Pillow's `(ffff)` box parse does to a
Python double.

Test `critic::metrics::thumbnail_tests::thumbnail_matches_pillow_when_the_reduce_factor_leaves_a_remainder`:
a 3073x97 synthetic pattern, reduce factor (3, 3), so the box after
`reduce` is (1024.333..., 32.333...), not f32-exact. It asserts the Rust
thumbnail `512 16 <sha256>` equals a pinned string, and that Pillow 12.3.0
run live through `uv run python` prints the same string.

| state | Rust digest | Pillow digest |
| --- | --- | --- |
| before (f64 box) | `72366bd8...5e41c7` | `e0873635...2486fd` |
| after (f32 box) | `e0873635...2486fd` | `e0873635...2486fd` |

So the test was red on the old code (exit 101, `left != right`) and is
green after the change.

Not changed, found while reading: Pillow decides to resample an axis when
`xsize != imIn->xsize || box[0] || box[2] != xsize`; metrics.rs checks only
`width != source.width`. The two differ only for a box offset from 0 or not
equal to the output size on an axis whose size is unchanged, which neither
caller (`thumbnail`, whose factor > 1 always changes that axis, and
`inspect_opener_crop_fidelity`, whose box is the full source) can build.
Latent, left as is.

## 2. `write_png` shared

`critic/rules.rs::write_png` is `pub(crate)`; `package/contact.rs` calls it
and loses its inlined encoder (and the unused `Context` import). Both
contact-sheet tests in `tests/package.rs`
(`contact_sheets_match_pillow_on_equal_wide_tall_and_upscaled_pages`,
`contact_sheets_match_pillow_pixels_over_the_oracle_rasters`) stay green:
`cargo test --test package` exit 0, 43 passed.

## 3. Start-0 ordered list in `wfx`

`wfx/articles/keyed.md` gains a paragraph and a `0. Zeroth.` / `1. First.`
list; `the_fixture_edition_matches_html_edition_byte_for_byte` also asserts
the needle `<ol start="0"><li><p>Zeroth.` (CommonMark keeps `start` for any
start other than 1, so 0 must be written out: the correct value, not only
Python's). `cargo test --test web_port`: exit 0, 13 passed, so Rust equals
Python on the new row in both the semantic HTML and the full web tree.

Mutation from `WP-5.5a.verify.md` (`*start != 1` to `*start > 1` at
`src/web/semantic.rs:854`), applied and restored: 7 of 13 fail (it survived
before this row). `git status` clean after restore.

## 4. Inline-image scan test

`tests/pdf_text.rs::a_scan_drawn_as_an_inline_image_fails_loud`: full-page
`BI /W 1 /H 1 /CS /G /BPC 8 ID A EI`, an 8 pt printed footer (22 glyphs) and
a `3 Tr` OCR word (4 glyphs). It asserts the error names
`4 invisible glyphs, 22 printed, 1 images`. Hidden glyphs are fewer than
printed ones, so only the image clause can fire.

Mutation from `WP-5.7b.verify.md` (`("BI" | "EI", _) => self.images += 1`
to `=> {}` at `src/pdf_text.rs:722`), applied and restored: the new test
fails with `got text "Downloaded from a library\n"` (the OCR layer silently
dropped), and the other 14 still pass. Unmutated: 15 passed.

## Whole suite

In `mag/`, own target dir:

| command | exit | observed |
| --- | --- | --- |
| `cargo test` | 0 | 30 binaries, 562 passed, 0 failed |
| `cargo fmt --check` | 0 | (first run flagged the new pdf_text test's line wrap; fixed before commit) |
| `cargo clippy -q --all-targets -- -D warnings` | 0 | |

## What is and is not proven

Proven: the metrics resize now reproduces Pillow bit for bit on a thumbnail
whose reduce factor leaves a remainder, where the f64 box did not; contact
sheets still match Pillow through the shared writer; the start-0 list
renders `start="0"` identically in both engines and pins the ordered-list
boundary; inline-image counting is pinned by a test that its removal breaks.

Not proven: metrics.rs on real edition images whose reduce factor leaves a
remainder (010 has none, per `WP-5.5c.md`); the axis-skip condition noted
under item 1 is unexercised, since no caller can reach it.
