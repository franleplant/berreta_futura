# WP-0.2y: comparator rework (JPEG colour transform, image identity, ratchet target at HEAD)

Worker, based on `art_directed` `78e28d3`. Worktree `.../7d99e27f/tmp/wp02y`, target
`.../tmp/wp02y-target`, outputs under `.../tmp/wp02y-out/`. Inputs: WP-3.0g.verify.md and
its harness in `.../tmp/v30g-out/`.

## What changed

- **JPEG colour transform** (`streams.rs` `jpeg_markers`, `jpeg_ycc`, `dct`). The tracer
  reads the JPEG's own markers and picks the transform the way poppler does: the Adobe
  APP14 transform if present, else JFIF means YCbCr, else component ids `R`,`G`,`B` mean RGB,
  else ids 1,2,3 mean YCbCr. It fails loud when that rule does not decide (3 components with
  other ids and no marker, Adobe transform 2 on 3 components, Adobe 1 on 4). zune now only
  decodes samples: its output space is set to its own input space (Adobe 0 on 3 components
  mapped to RGB, the case that made zune fail with "RGB to CMYK"), and the tracer applies
  YCbCr->RGB itself.
- **Image identity** (`decode_image`, `soft_mask`, `masked`, `stencil`, `unmatted`). The
  element field is renamed `paint_sha256`. It hashes `WxH`, `/Interpolate` (absent reads
  as false) for the image and its SMask, and the RGBA samples, where:
  - a colour-key `/Mask` or a stencil `/Mask` (1 bit, `/Decode` honoured, sample 1 masks,
    which poppler confirmed) sets alpha 0;
  - SMask `/Matte` is removed from the colour (`m + (c - m) * 255 / a`), so a Matte over
    alpha that is only 0 or 255 hashes like no Matte, which is how poppler paints it;
  - any pixel with alpha 0 hashes with colour 0.
  BitsPerComponent must still be 8 and `/Decode` must be identity or inversion (both were
  already fail-loud). Any image, SMask or Mask key outside a fixed list fails loud: `/Intent`,
  `/Alternates`, `/OC`, `/SMaskInData`, `/ImageMask` on a painted image. The neutral keys are
  Type, Subtype, Length, Filter, DecodeParms, Metadata and Name. `/SMask` together with
  `/Mask`, and a colour key together with `/Decode`, also fail loud.
- **Ratchet target at HEAD** (`parity.rs` `at_head`, `guard_target`). `guard_baseline` now
  reads `HEAD:meta/verification/parity.yaml`. If the working `ratchet.target_tier` ranks
  below the committed one, the run fails before measuring anything. When HEAD is
  unavailable, the check is skipped, the same way baseline.json is handled.
- **Tests.** The three `#[ignore]` tests are un-ignored and pass. New tests:
  `equal_paint_traces_equal_and_each_painted_key_traces_to_another_picture` covers
  Interpolate false equal to absent, a colour key and stencils that mask nothing equal to
  no mask, a masking stencil unequal, a stencil equal to its inverse under Decode [1 0], a
  binary-alpha Matte equal to none, and /Intent failing loud.
  `a_jpeg_colour_transform_follows_adobe_then_jfif_then_component_ids` covers six marker
  and id combinations and two fail-loud ones.
  `a_working_ratchet_target_below_the_committed_one_fails_loud` covers the target guard.

## Commands (real exit status, key numbers)

```sh
cargo fmt --check                              # 0
cargo clippy --all-targets -- -D warnings      # 0
cargo test                                     # 0; 32 result lines, 918 passed, 0 failed, 0 ignored
cargo build --release                          # 0
(adv) TAG=y MAG=.../release/mag python3 all.py y   # 0; 210 pairs, 63 pass, 0 changed vs v30g results-tip.jsonl
                                               #   (exit, display, glyph, ratio, navigation, text, colour, boxes, error)
BINS=mag-y bash floor.sh                       # 0; output identical to v30g floor.txt (diff 0):
                                               #   stairdrift pass 0.2500 viol 0, kern02 fail 10.2500 (7)
mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # 0
#   staged fresh bc49b2aa..., ratchet pass (target E, 54/54/54, 0 regressions), S all pass,
#   E glyph 58623 ratio 0.0000, display 58850 vs 58850, V2 0.000336, typst reader.pdf 6709dc15...
#   verdict equals v30g s4 verdict after normalising a_reader_sha256, render-dir stamps and
#   scratch paths (both 430de3f1...); baseline-proposed.json JSON-equal to baseline.json
control: parity.yaml target_tier E -> V2, same command   # 1, "meta/verification/parity.yaml
#   lowers ratchet.target_tier from the committed E to V2, which only a verifier may change"; restored
uv run python tools/sourcecodes.py 008         # 0 (worktree only, not committed, as WP-3.9)
mag parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32   # 0; Tier S all pass
```

The 010 verdict bytes differ from before only in `a_reader_sha256`, which WeasyPrint dates,
and in the render-dir timestamps. On the 008 adhoc run, display-list pages dropped from
[4, 16, 17, 19] (WP-3.9) to [4]. WP-0.0f caused this, not this WP: the WeasyPrint reader
changed (`8d4dde58` -> `63a796ea`), and the base comparator (`v30g-out/fbin/mag-tip`,
pre-rendered on the same two legs) also reports 1 page.

Rebased onto `9bcc6a8` (WP-5.6, typeset and cover). Results: clippy 0, `cargo test` 0
(921 passed, 0 failed, 0 ignored), and staged 010 exit 0 (ratchet pass 54/0, E glyph 0
violations, display 58850 vs 58850). The normalised verdict differs from the pre-rebase run
only in `b_reader_sha256`, `6709dc15...` -> `6c03dda9...`. WP-5.6 changed that typst reader.pdf;
its evidence covers the cover faces on pages 1 and 56, which are outside the interior domain.

## Image and JPEG pairs (px = poppler pixels differing, 300 dpi, page 2)

The verifier's 27 pairs (`v30g-out/h/cases`), plus 14 of mine (`wp02y-out/cases2`, `y_*`).
Base = `v30g-out/fbin/mag-tip`. Every row that changed:

| pair | px | base | new |
|---|---|---|---|
| img_reshape_16x16_vs_32x8 | 674288 | 0 | 1 (display) |
| img_interpolate | 679818 | 0 | 1 |
| img_colorkey_mask_wide | 108941 | 0 | 1 |
| img_stencil_mask | 348194 | 0 | 1 |
| smask_matte_graded | 653022 | 0 | 1 |
| jpeg_rgbids_jfif_vs_rgbids_nojfif | 696390 | 0 | 1 |
| jpeg_rgbids_jfif_vs_plain_legit | 0 | 1 | 0 |
| jpeg_adobe_transform0_*_vs_jfif (x2) | 696390 | 1 (zune error) | 1 (display, traced) |
| y_smask_interpolate | 605204 | 0 | 1 |
| y_stencil_ones_vs_none / y_stencil_half_vs_inverted | 696390 | 0 | 1 |
| y_jpeg_adobe0_jfif_vs_nojfif_legit | 0 | 1 | 0 |
| y_intent (`/Intent /Saturation`) | 0 | 0 | 1 (fail loud) |
| y_jpeg_odd_ids_nojfif (ids 7,8,9) | 0 | 0 | 1 (fail loud) |

Unchanged and correct: img_colorkey_mask, img_same, img_scaled_0049, jpeg_same_bytes,
jpeg_smask legit and inverted, smask_matte (0 px, 0), the y_ legit rows (Interpolate false,
colour key with no match, stencil zeros, stencil ones under Decode [1 0], nojfif ids 1,2,3,
Adobe 1 with JFIF, Adobe 0 RGB ids, odd ids with JFIF), and all the non-image rows.
Unchanged and still conservative, as the verifier accepted: img_indexed_vs_rgb (fail
loud), zerolen_exact_square_vs_nothing (0 px, 1), and all_shift_0049_legit (1997 px, 0,
raster-grid artifact).

## What is and is not proven

- Proven: the three verifier holes and both JPEG misreadings now trace correctly against
  poppler on these pairs. Equal paint compares equal on every legit image pair above. The
  210-pair replay and the floor are unchanged. 010 stays green at target E with the same
  verdict. A working-tree target below HEAD's fails the run.
- The two fail-loud rows are conservative false fails, not errors. Poppler paints ids 7,8,9
  without a marker as YCbCr and ignores `/Intent`. The brief's rule leaves the first
  undecided, and the second may change paint in colour-managed readers. Neither 010 leg
  uses them.
- Not proven: any reader but poppler. From its source, not a run, pdf.js reads JFIF plus `R`,`G`,`B` ids as RGB, but
  this rule (and poppler) reads it as YCbCr. The Matte formula is the PDF one. It is
  compared only between legs, and its rounding against poppler's was not measured. A
  stencil `/Mask` whose size differs from the image fails loud. It is not resampled.
