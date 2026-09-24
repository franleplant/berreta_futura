# WP-0.2p, 0.2q, 0.2r + rework WP-0.2s adversarial verify

Verifier, at `art_directed` `c7ff204` (WP-0.2s `d7c970c` + queue doc).
Question: after the rework, can a pair that renders visibly differently at
300 dpi pass the gate?

## Verdicts

| WP | verdict | why |
| --- | --- | --- |
| WP-0.2p five normalizations (as reworked) | **ACCEPTED** | all three earlier wrong passes fail; no new rect, pen, clip-reach or white-fill pair passes with a visible difference (below) |
| WP-0.2q landed part (as reworked) | **ACCEPTED** | `strip_degenerate_inner` fails; inner = outer, reversed-inner nonzero and hole-in-middle fail; `strip_legit` passes |
| WP-0.2r glyph-level text | **REJECTED** | blanks on BOTH legs in different counts still buy drift: 7000 vs 5000 zero-width blanks let "world" move 3 pt and pass (2661 px). Fails at `73ef1e7` (before 0.2r), passes with 0.2r's and 0.2s's binaries |
| WP-0.2s rework | **REJECTED** | (1) the blank rule `min(blanks_A, blanks_B)` keeps the 0.2r hole above; (2) the new link-border key contradicts what poppler draws: an absent `/C` is drawn black, not transparent, so a link with no `/Border` and no `/C` (poppler: 1 pt black box) equals `/Border [0 0 0]` and passes (3296 px); a hidden (`/F 2`) or NoView (`/F 32`) bordered link equals a drawn one (9375 px) |

Both 0.2s holes are latent on 010 (both legs write width-0 link borders per
WP-0.2s.md, and no leg is shown to pad lines with thousands of blanks), but
each is a visible difference the WP's own new rule lets through.

Root causes and cheap closures (the fix is the WP owner's):
1. **Glyph bound.** k grows by one full step per blank both legs carry, and
   a blank of zero advance (or a run of real-width spaces undone by a TJ
   kern) is not an accumulated advance. Pre-existing sibling, same root:
   the bound is linear in any k both legs share, so 7000 zero-width inked
   dots stacked on both legs (`inked_stack_7000_shift5`) or 7000 blanks in
   equal counts (`blank_both_7000_shift5`) buy 5 pt; both pass already at
   `e5e3498` (before WP-0.2p). Closure: count a step only for an advance
   that moves the pen, or cap k by the line's inked span in glyph widths.
2. **Link border.** `link_border` maps absent `/C` to `none` (and the
   existing test `a_link_border_compares_what_is_drawn_with_spec_defaults`
   pins `border({}) == "none"`); poppler draws absent `/C` in black
   (`link_c_absent_vs_black_w3`: 0 px, and it fails, so the key is wrong in
   both directions). `/F` Hidden/NoView bits are not read.

## Method

The previous verify's harness (`WP-0.2m-r.verify.md` Method), copied to
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/adv-v/` and pointed at a
worktree of the tip: `pdfgen.py` (gained a `program=` font file override and
an `xres=` resource hook), `cases.py` (the 42 earlier pairs, unchanged),
`cases2.py` (new pairs), `go.py` (build + run), `results-replay.jsonl`,
`results-v.jsonl`. Per pair: `pdftoppm -r 300` page 2 of both legs, pixel
counts (any / beyond 24 / max delta), then `mag parity 010 --pre-rendered`;
gate = exit status. Attribution binaries: `wp02p-bin/mag-base` (`e5e3498`),
`wp02r-scr/mag-before` (`73ef1e7`), `wp02r-scr/mag-new` (WP-0.2r),
`wp02s-bin/mag-base` (pre-0.2s tip), all under `.../tmp/`.

## 1. Replay of every earlier pair (tip binary)

All 42 pairs of `WP-0.2m-r.verify.md` re-run (`results-replay.jsonl`).
Every adversarial pair fails, including the ten former wrong passes:
`clip_degenerate_rect`, `fill_degenerate_rect_clipped`,
`strip_degenerate_inner`, `clip_anisotropic_stroke_round`,
`anisotropic_stroke_vs_plain` (display fail), `blank_inflation` (glyph
fail), `col_cmyk_richblack` (colour + display), `link_border_vs_none`
(navigation + display), `cid2gid_blank_draws_glyph` and
`simple_font_lying_tounicode` (fail loud). Every legitimate pair passes
with exit 0: control, box_trim_equal_media, clip_rect_contains_legit,
col_sgrey_vs_rg, col_srgb_icc_vs_rg, col_subhalf_step (1 level),
fill_clipped_circle_legit, link_rect_order, loop_single_reversed,
re_vs_path_fill, strip_legit (126 px edge AA), white_leading. The harness
positive control `control_moved_word` fails (5117 px).

## 2. New pairs against the new rules

px = pixels differing / beyond 24 / max delta. Gate: pass = exit 0.

**Wrong passes (visible difference, exit 0):**

| pair | px | gate | attribution |
| --- | --- | --- | --- |
| **`blank_both_7000_5000_shift3`** 7000 vs 5000 zero-width blanks, "world" 3 pt right | 2661 / 2484 / 255 | **pass** | WP-0.2r (fails at `73ef1e7`), kept by 0.2s `min` |
| **`link_no_border_no_c_vs_zero`** no `/Border`, no `/C` vs `/Border [0 0 0]` | 3296 / 3296 / 255 | **pass** | 0.2s default (absent C = none); passed before too |
| **`link_c_absent_vs_empty_w1`** `/Border [0 0 1]` without `/C` vs with `/C []` | 3296 / 3296 / 255 | **pass** | same |
| **`link_hidden_flag`** / **`link_noview_flag`** `/F 2` / `/F 32` on a red 3 pt border vs no flag | 9375 / 9375 / 255 | **pass** | 0.2s key ignores `/F` |
| **`link_hidden_flag_black_default`** same, black | 9339 / 9339 / 255 | **pass** | same |
| `blank_both_7000_shift5` equal 7000 blanks both legs, 5 pt | 2833 / 2657 / 255 | **pass** | pre-existing (passes at `e5e3498`) |
| `blank_both_real_width_7000_shift5` 7000 real-width spaces undone by a kern, both legs | 2833 / 2657 / 255 | **pass** | pre-existing |
| `inked_stack_7000_shift5` 7000 zero-width "." stacked on both legs | 2833 / 2657 / 255 | **pass** | pre-existing |
| `hairline_zero_vs_tiny` `0 w` vs `0.004 w` (both pen `[0,0,0]`; poppler: dark 1 px row vs faint) | 835 / 835 / 255 | **pass** | pre-existing (`lw` quantization at 0.01 pt; passes at `e5e3498`) |
| `square_annot_interior` Square annot `/IC` red vs none | 234600 / 234600 / 255 | **pass** | pre-existing: non-Link annots compare subtype/rect/border only |
| `freetext_da_colour` FreeText `/DA` red vs black | 14335 / 14051 / 255 | **pass** | pre-existing (same) |

**Correct outcomes:**

| pair | px | gate | clause |
| --- | --- | --- | --- |
| `blank_both_1_shift5_control` 1 blank both legs, 5 pt | 2833 | fail | glyph |
| `blank_both_7000_noshift_legit`, `..._7000_5000_noshift_legit` | 0 | pass | correct |
| `blank_runs_one_leg_shift1` one blank per gap on B only, last glyph 1 pt | 397 | fail | glyph |
| `blank_runs_one_leg_shift003` same, 0.03 pt | 162 | fail | glyph |
| `blank_runs_one_leg_legit` | 0 | pass | correct |
| `inked_stack_7000_noshift_legit` | 0 | pass | correct |
| `skew3_g8`, `skew3_g9` shear-3 miter-joined stroked rect, rect clip 8/9 pt out | 0 | fail | conservative (reach 9.4 pt) |
| `skew3_g10..g30` (+ `_M50`) | 0 | pass | correct: clip holds the stroke |
| `skew3_g2..g6` | 16530 .. 1740 | fail | display |
| `skew4.5_g2..g9` (+ `_M50`) | 26970 .. 1305 | fail | display |
| `skew4.5_g10`, `g12` | 0 | fail | conservative (reach 13.4 pt) |
| `skew4.5_g16..g30` | 0 | pass | correct |
| `rot_square_cap_clip2_g1..g4` 45 deg rotated 6 w square-cap line, clip 1..4 pt past the ends | 740 .. 17 | fail | display |
| `rot_square_cap_clip2_g5` | 0 | fail | conservative |
| `aniso_butt_vs_square_cap` under `1 0 0 16` | 264 | fail | display |
| `aniso_dash_phase` under `1 0 0 16` | 35574 | fail | display |
| `rot_aniso_round_vs_square_cap` rotated + 16x | 0 | fail | conservative |
| `pen_skew_vs_scale_same_det` shear vs plain, same `|det|` | 1813 | fail | display (pen differs) |
| `pen_skew_vertical_line` | 1712 | fail | display |
| `pen_rotation_equivalent_legit` `1 0 0 4` vs `0 4 -1 0`, same device stroke | 0 | pass | correct |
| `pen_reflection_equivalent_legit` `1 0 0 4` vs `1 0 0 -4` | 2 / 0 / 11 | pass | correct |
| `hairline_zero_vs_quarter` `0 w` vs `0.25 w` | 2 | fail | display |
| `rot90_rect_fill_legit` rect filled under a 90 deg CTM vs `re` | 0 | pass | correct |
| `clip_rot45_square_cuts2` 45 deg square clip over the text | 3585 | fail | display, glyph, colour |
| `clip_near_rect_trapezoid` clip corner 18 pt low (text still inside) | 0 | fail | conservative (not a rect) |
| `clip_near_rect_trapezoid_tiny` corner 0.004 pt low | 0 | pass | quantizes to the rect |
| `clip_rect_extra_collinear_vertex`, `clip_rect_extra_vertex_cutting`, `clip_two_rects_union`, `clip_bowtie_axis` | 0 | fail | conservative |
| `clip_rect_with_lone_moveto` | 0 | pass | correct |
| `fill_rect_pinched` 5-vertex pinched "rect" vs `re` | 88820 | fail | display |
| `fill_rect_vs_eofill_selfoverlap` same rect twice, `f*` (paints nothing) | 348195 | fail | display |
| `fill_rect_vs_nonzero_double` same rect twice, `f` | 1667 / 1666 / 90 | fail | display (poppler AA darkens edges) |
| `strip_inner_equals_outer` eofill O = I under a strip clip | 35070 | fail | display |
| `strip_inner_reversed_nonzero_as_eo` nonzero fill with reversed inner | 126 | fail | conservative |
| `cmyk_subquantum_legit` `0 0 0 1 k` vs `0 0 0 0.999 k` | 0 | pass | correct |
| `cmyk_stroke_richblack` `1 1 1 0 K` vs `0 0 0 1 K` | 20826 / 20825 / 25 | fail | colour, display |
| `cmyk_near_equal_c` `.2` vs `.21` cyan | 347361 / 0 / 3 | fail | colour |
| `cmyk_vs_gray_same_conversion` `0 0 0 .5 k` vs `.5 g` | 347361 / 0 / 17 | fail | colour |
| `overprint_op` ExtGState `/OP /op /OPM` | 0 | fail | fail loud (key OP) |
| `gstate_lw_via_gs` ExtGState `/LW 8` | 24159 | fail | fail loud (key LW) |
| `gstate_blend_mode` ExtGState `/BM /Multiply` | 0 | fail | fail loud (key BM) |
| `link_bs_vs_border_same_legit` `/BS <</W 3>>` vs `/Border [0 0 3]` | 0 | pass | correct |
| `link_border_default_width_legit` absent `/Border` vs `[0 0 1]` | 0 | pass | correct |
| `link_bs_w0_vs_border0_legit` | 0 | pass | correct |
| `link_bs_dash_default` `/S /D` vs `/D [3]` | 0 | pass | correct |
| `link_border_dash_vs_solid` | 3125 | fail | navigation, display |
| `link_c_gray_vs_rgb` `/C [0]` vs `[0 0 0]` | 0 (poppler warns "AnnotColor different than RGB") | fail | conservative |
| `link_c_absent_vs_black_w3` no `/C` vs `/C [0 0 0]` | 0 | fail | conservative, but shows the key is wrong |
| `freetext_contents` FreeText other words | 9420 | fail | Tier S text only |
| `font_program_swap_bold` leg A embeds Inter-Bold under `/BaseFont /Inter-Regular` | 2769 | fail | fail loud (glyph identity) |

Mis-built pairs, not counted: `clip_rot45_square_cuts` and
`rot_square_cap_clip_g*` (clip popped before painting / far from the
stroke; 0 px), `skew_square_cap_clip_g*` (clip misses the line entirely,
2963 px, all fail), `clip_rot45_diamond_contains_legit` (the diamond hides
the text, 3585 px, fails).

Rect predicate: the four distinct bounding-box corners as the first four
points, each edge moving along exactly one axis, closing on the start,
forces a genuine rectangle traversal; every near-rect, extra-vertex,
bow-tie and multi-loop clip was left alone. Pen: the Cholesky factor of
`w^2 M M^T` is invariant exactly under user-space isometries, which leave
the stroke (caps, joins, dash arc length) unchanged, so it separates every
other pen; rotation/reflection equivalents pass, skew and anisotropic
variants fail. Square exemption from the miter spike is sound: for a
device-space rectangle the miter tip is the corner of the offset box, at
most `sqrt 2` times the pen's largest semi-axis (the skew rows confirm:
visible extent below the reach every time).

## 3. Floor at the tip

`floor.sh` from WP-0.2s (leg A `editions/010/render-2026-09-14T01-49-02`,
fixtures `wp02p-fx/r3`) with the tip binary from the main tree; output
`adv-v/floor/floor.txt`.

| row | exit | glyph clause | display |
| --- | --- | --- | --- |
| A-vs-A | 0 | pass, 58755 glyphs, 1488 segments, ratio 0 | pass 58982 = 58982 |
| control | 0 | pass, ratio 0 | pass |
| stairdrift | 0 | **pass, ratio 0.2500, 0 violations** | pass |
| drift / smoothdrift | 0 / 0 | pass 0.2500 / pass 0.6250 | pass |
| kern02 | 1 | fail, **ratio 10.2500 (ceiling)**, 5 violations | pass |
| kern001 / advstep | 1 / 1 | fail 0.5625 / fail 0.6250, 1 each | pass |
| advtail02 | 1 | fail 10.2500, 7 | pass |
| glyphsub | 1 | pass | fail, 12 pages |

Identical to WP-0.2s.md's floor table.

## 4. `mag parity 010` at the tip

`MAG_PARITY_OUT_DIR=.../adv-v/typst010 mag parity 010 --run
editions/010/run-2026-09-13T01-34-51` from the main tree: **exit 1, verdict
written** (`adv-v/typst010/verdict.json`). Fresh legs
`render-2026-09-24T01-56-37` (WeasyPrint), `render-2026-09-24T01-58-11`
(typst). S: page_count pass, boxes pass, text pass, colour fail,
navigation fail. E display list fail 58850 vs 58798, 43 pages; E glyph fail
58623 glyphs, 1802 segments, worst ratio 17294.0 (page 7), 40 violations.
V pass. No fail-loud fired. These differ from WP-0.2s.md's 010 numbers
because the typst leg is re-rendered from today's typeset code (WP-3.5,
WP-5.5d landed since); the WeasyPrint side (58850) matches.

## Tests committed (ignored, pinning the correct value)

In `mag/src/parity/display.rs` `colour_tests`, both FAIL with `--ignored`
at this tip:
- `blanks_both_legs_carry_buy_no_visible_move`: 7000 vs 5000 blanks with a
  3 pt move, and 7000 vs 7000 with 5 pt, each must fail the glyph clause;
  got `[("pass","pass"), ("pass","pass")]`. (Shares a new `padded` helper
  with `blanks_on_one_leg_buy_no_drift_allowance`, which now calls it.)
- `a_link_border_follows_what_poppler_draws`: absent `/C` equals black,
  `{}` is not `none`, `/F 2` is `none`; got `[false, false, false]`. The
  fixer also flips the `border({}) == none` line of
  `a_link_border_compares_what_is_drawn_with_spec_defaults`.

`cargo fmt --check` 0, `cargo clippy --all-targets -- -D warnings` 0,
`tools/nocomments.py` 0, `cargo test --no-fail-fast`: 31 result lines all
ok, 637 passed, 0 failed, 14 ignored.

## Findings outside these WPs (for the orchestrator)

1. Glyph bound linear in shared k (`inked_stack_7000_shift5`,
   `blank_both_7000_shift5`): predates WP-0.2p.
2. Non-Link annotations without `/AP` are compared by subtype, rect and
   border only; poppler synthesizes their appearance from `/IC`, `/DA`,
   `/Contents`. Fail loud on any non-Link annotation.
3. `0 w` hairline vs a sub-0.005 pt width compares equal; poppler draws
   them differently (835 px, one row).

## What is and is not proven

**Proven.** Every earlier pair has the right outcome at the tip; each wrong
pass above is a visible 300 dpi difference with exit 0 at the tip, with
attribution by binary where stated; the floor rows match WP-0.2s.md; `mag
parity 010` writes a verdict.

**Not proven.** The pairs are hand-built and poppler at 300 dpi is the only
rasterizer; Acrobat's rendering of an absent `/C` was not checked. No
census shows either engine emitting padded blank runs, hidden links or
absent-`/C` bordered links on 010. The rect/pen soundness arguments are
checked by pairs, not exhaustively.
