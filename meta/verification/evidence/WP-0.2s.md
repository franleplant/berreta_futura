# WP-0.2s comparator rework (closes WP-0.2m-r.verify.md rejections)

Base `art_directed` `3f070f4`. Owns `mag/src/parity*`. Scratch:
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02s-bin/` (binaries
`mag-base` = tip, `mag-new` = this WP; floor and 010 verdicts) and
`.../tmp/adv-s/` (copy of the verifier's adversarial harness pointed at this
worktree; `results-s.jsonl`).

## What changed

1. `canon::rect`: a rectangle is now 5 points closing on the start, every
   edge axis-aligned and non-degenerate (exactly one coordinate changes), the
   first four points exactly the four distinct corners of the bounding box,
   and positive width and height. The out-and-back zero-area loops are no
   longer rects, so `contained_clips`, `fill_the_clip`, `strip_fill`/`frame`
   and the stroke `square` test leave them alone.
2. + 4. Stroke geometry: `Element::Path.lw` is now `[i64; 3]`, the pen
   ellipse of the stroke under the CTM as the lower-triangular factor of
   `w^2 L L^T` (`streams::pen`: `w|r0|`, `w (r0.r1)/|r0|`, `w |det|/|r0|`).
   It is rotation-invariant for isotropic CTMs (`[ws, 0, ws]`) and differs
   for any other pen. The clip-drop reach uses the pen's largest semi-axis
   (sqrt of the largest eigenvalue of `T T^T`) instead of the scalar mean.
   Dash lengths keep the `sqrt|det|` scale: two equal pens differ by a user
   space rotation, which preserves dash arc length.
3. Glyph bound: `Glyph.step` is `[inked, blanks, blank runs]`, summed along
   the line. The bound's k is `max(inked) + max(min(blanks_A, blanks_B),
   max(runs_A, runs_B))`. Justification: a blank both legs carry is an
   advance both legs accumulate, so it counts in full; a leg alone can add at
   most one step per gap between inked glyphs (a run of blanks, whatever its
   length, is one step), which keeps the old whole-vs-halves case (one space
   glyph vs a repositioned show) passing and caps one-leg inflation at 2x the
   inked count. Chosen over min(k) because min fails that legitimate case
   (the existing `drift_inside_a_line...` test pins it). Known cost: a run of
   n blanks on one leg against pure positioning on the other gets one step,
   not n; that is the fail-loud direction and did not change any 010 or
   floor verdict (below).
5. CMYK: a DeviceCMYK colour's family carries its 8-bit quantized device
   components (`cmyk [c, m, y, k]`), and its rgb is derived from the
   quantized components, so `1 1 1 0 k` != `0 0 0 1 k` and sub-quantum
   values stay equal. (A new struct field would have touched
   `src/critic.rs`, outside this WP.)
6. Fail loud: a CIDFont whose `/CIDToGIDMap` is present and not `/Identity`;
   a simple font showing a code other than 32 whose ToUnicode is
   whitespace ("only code 32 is provably blank").
7. Links: `Annot.border` compares the drawn border: `/BS` (W default 1, S
   default S, D default [3], other styles fail loud) over `/Border` (default
   `[0 0 1]`, radii and dash kept), and `/C` (absent = transparent). Width 0
   or no colour is `none`, so WeasyPrint's `/BS<</W 0>>` equals typst's
   `/Border[0 0 0]`.

Tests: the three `#[ignore]` tests from the verify are un-ignored and pass
(`a_zero_area_loop_with_rect_corners_is_not_a_rect_region`,
`blanks_on_one_leg_buy_no_drift_allowance`,
`an_anisotropic_stroke_is_not_the_isotropic_one_of_mean_width`); new:
`blanks_on_both_legs_count_each_but_one_leg_alone_adds_one_step_per_gap`,
`cmyk_compares_its_device_components_not_a_conversion`,
`a_simple_font_may_map_only_code_32_to_whitespace`,
`a_cid_to_gid_map_other_than_identity_fails_loud`,
`a_link_border_compares_what_is_drawn_with_spec_defaults`.

## Commands and results

- `cargo fmt --check` 0; `cargo clippy --all-targets -- -D warnings` 0;
  `cargo test --no-fail-fast` in `mag/`: every binary `ok`, 0 failed,
  0 ignored (parity subset 53 passed).
- Adversarial pairs, `python3 adv-s/run.py <all 42 cases>` with `mag-new`
  (verifier's `run.py`, ROOT switched to this worktree). Every pair the
  verify listed as a wrong pass now fails:

| pair | px | tip gate | now |
| --- | --- | --- | --- |
| clip_degenerate_rect | 3585 | pass | exit 1, display fail |
| fill_degenerate_rect_clipped | 137196 | pass | exit 1, display fail |
| strip_degenerate_inner | 17556 | pass | exit 1, display fail |
| clip_anisotropic_stroke_round | 26780 | pass | exit 1, display fail |
| anisotropic_stroke_vs_plain | 41652 | pass | exit 1, display fail |
| blank_inflation (7000 blanks) | 2833 | pass | exit 1, glyph fail |
| col_cmyk_richblack | 347361 | pass | exit 1, colour + display fail |
| link_border_vs_none | 9375 | pass | exit 1, navigation + display fail |
| cid2gid_blank_draws_glyph | 388 | pass | exit 1, fails loud (CIDToGIDMap) |
| simple_font_lying_tounicode | 365 | pass | exit 1, fails loud (code 65) |

  Every legitimate pair still passes with exit 0 (control, box_trim_equal_media,
  clip_rect_contains_legit, col_sgrey_vs_rg, col_srgb_icc_vs_rg,
  col_subhalf_step, fill_clipped_circle_legit, link_rect_order,
  loop_single_reversed, re_vs_path_fill, strip_legit, white_leading), and
  every pair that failed at the tip still fails.
- Floor, `wp02s-bin/floor.sh` from the main tree (leg A
  `editions/010/render-2026-09-14T01-49-02`, fixtures `wp02p-fx/r3`), base
  and new binaries, output `wp02s-bin/floor.txt`. Identical rows for both:
  AvA exit 0 glyph pass 58755 glyphs 1488 segments ratio 0; control exit 0
  ratio 0; **stairdrift exit 0, pass, ratio 0.2500, 0 violations**; drift
  0.2500 pass; smoothdrift 0.6250 pass; **kern02 exit 1, ratio 10.2500, 5
  violations (ceiling)**; kern001 0.5625 / 1; advstep 0.6250 / 1;
  advtail02 10.2500 / 7; glyphsub display fail 12 pages. Matches the verify's
  floor table.
- `mag parity 010 --pre-rendered editions/010/render-2026-09-24T00-34-09
  editions/010/render-2026-09-24T00-35-17` (the verify's two tip legs), base
  and new: both exit 1, and `tier_s`, `tier_e`, `tier_v` are byte-identical
  JSON apart from the output path. Per tier: S page_count pass, boxes pass,
  text fail (2 pages), colour fail (30), navigation fail; E display fail
  58850 vs 58794, 52 pages (classes text 32, path 26, clip 25, image 25,
  order 8, annotations 5); E glyph fail 58623 glyphs, 2881 segments, worst
  ratio 22556.0 (page 40), 40 violations; V pass. No fail-loud fired on 010.

## What is and is not proven

**Proven.** The ten wrong passes from WP-0.2m-r.verify.md now fail (six by
comparison, two by fail-loud, two by the new colour/border keys), each
checked on the verifier's PDFs; the legitimate pairs and the floor rows are
unchanged; on today's 010 legs the verdict is unchanged, so none of the
tightenings (rect, pen, blank rule, CMYK, border, fail-louds) moves a
current 010 number.

**Not proven.** The 010 domain is pages 2..n-1, so the simple-font rule was
not exercised against WeasyPrint's cover-page TrueType/Type1 fonts. The blank
rule under-counts a one-leg run of several advance-carrying blanks (e.g. code
indentation written as spaces on one leg and as positioning on the other);
010 shows no verdict change, but no census of such runs was taken. The pen
compares the ellipse, not caps and joins drawn under a skewed CTM beyond
what the ellipse determines. Pixels are poppler at 300 dpi only.
