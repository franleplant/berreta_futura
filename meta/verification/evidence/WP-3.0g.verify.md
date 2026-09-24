# WP-3.0g verify: final adversarial comparator verify (WP-0.2u, 0.2v, 0.2w, 0.2x, 3.0g)

Verifier, at `art_directed` `bb63247` (parity code = `4c3697b`; since WP-0.2x `e1822cf`
only `parity.rs` ratchet target and the `raster.rs` owner label changed). Worktree
`.../7d99e27f/tmp/v30g`, target `.../tmp/v30g-target`, every output under
`.../tmp/v30g-out/`. Inputs: WP-0.2u/v/w/x.md, WP-3.0g.md, QUEUE.md orchestrator decisions
(one-tick-per-step drift allowance, link rects within 0.25 pt, half-quantum 0.005 pt).

## Verdicts

| WP | verdict | why |
|---|---|---|
| WP-0.2u | **ACCEPTED** | 210 pairs and the floor replay unchanged; residual is the accepted drift limit |
| WP-0.2v | **REJECTED** | `jpeg_rgbids_jfif_vs_rgbids_nojfif` passes with 696390 px differing (below) |
| WP-0.2w | **ACCEPTED** | gate, impose exact path and doc tests green; no impose hole found |
| WP-0.2x | **ACCEPTED** | tolerance compares absolute device coordinates, nothing accumulates; pairs below |
| WP-3.0g | **ACCEPTED** | raise re-derived from a `none` baseline, equal pages; target check sound; two clean staged runs identical |

Separate from these WPs, the image tracer has four older identity holes that pass visible
differences (below). The orchestrator has to open a WP for them.

## 1. Replay at the tip

`TAG=tip MAG=v30g-target/release/mag python3 all.py tip` (copy of `wp02x-out/adv`, ROOT
set to this worktree), exit 0, `v30g-out/adv/results-tip.jsonl`: 63 pass / 147 fail, 21 of
the fails loud. Against `wp02x-out/adv/results-x.jsonl`, 0 of 210 pairs change exit,
display, glyph, glyph ratio, navigation, text, colour, boxes or error presence. There is
nothing new to judge.
Floor (`v30g-out/floor.sh`, the WP-0.2x script with this binary), exit 0, output identical
to the WP-0.2x `mag-x` rows (`diff` exit 0): stairdrift pass 0.2500, kern02 fail 10.25 (7).

## 2. Attacks (new pairs, `v30g-out/h/gen.py`, results `results-new*.jsonl`)

px = pixels differing at 300 dpi, page 2, pdftoppm.

**Half-quantum comparison (WP-0.2x).** Every compared number is an absolute device-space
value: path tokens, clip tokens, image CTM, text matrix, box edges. Each is checked on its
own, so no difference can build up along a path or across elements. Text scale or rotation
under the tolerance moves glyphs along the line, and that is the glyph clause's job.

| pair | exit | px | judgement |
|---|---|---|---|
| `all_shift_0049_legit` (fill, stroke, clip, image, text all +0.0049 pt) | 0 | 1997 | legit: the clip edge y=140 lands exactly on a 300 dpi row edge and flips one row (417 px); the rest is glyph-bitmap binning. Geometry moved 0.0049 pt, so this is a raster-grid artifact |
| `img_scaled_0049_legit` (200 vs 200.0049 pt) | 0 | 0 | legit |
| `rule_height_010_vs_0198` (edges each 0.0049 off) | 0 | 0 | legit |
| `thin_rule_0098_vs_degenerate` | 1 | 1251 | caught (display) |
| `text_rot_subtol` (Tm rotation 4e-4 rad, m within 0.005) | 1 | 1899 | caught (glyph, ratio 4.875) |
| `zerolen_*` (round-cap dots, 0.004 pt and exact zero, vs butt / nothing / inside a path) | 1 x5 | 0-529 | caught; rounded zero-length removal never drops a painting dot |

**JPEG decode (WP-0.2v).** Both legs share one decoder, so a 2-level decoder error cannot make
two different pictures equal. The risk is a different colour-transform decision:

| pair | exit | px | judgement |
|---|---|---|---|
| `jpeg_rgbids_jfif_vs_rgbids_nojfif` | **0** | **696390** | **hole**: zune reads component ids 'R','G','B' as RGB in both; libjpeg (poppler) reads the JFIF one as YCbCr |
| `jpeg_rgbids_jfif_vs_plain_legit` | 1 | 0 | false fail (same rule, other direction) |
| `jpeg_adobe_transform0_*` (x2) | 1 | 696390 | fail loud (zune: "RGB to CMYK" mapping; misleading message, correct direction) |
| `jpeg_colortransform0_param` | 1 | 696390 | fail loud |
| `jpeg_smask_jpeg_legit` / `_inverted` (DCT SMask, Decode [1 0]) | 0 / 1 | 0 / 693634 | correct |
| `img_indexed_vs_rgb` | 1 | 0 | fail loud ("expected name"), as WP-0.2v says |

WP-0.2v's "not proven" section names the 'R','G','B' rule, but the code does not fail loud
on it, and the pair passes. The fix is to choose the transform the way the reader does: the
Adobe marker if present, else JFIF means YCbCr, else ids 'R','G','B' mean RGB. The other
option is to fail loud on a 3-component JPEG with no Adobe marker whose ids are not 1,2,3.

**Image identity (older tracer code, not these WPs).** `decode_image` hashes the samples
only. `Element::Image` drops Width/Height, and the tracer never reads `/Interpolate`,
`/Mask` or SMask `/Matte`:

| pair | exit | px |
|---|---|---|
| `img_reshape_16x16_vs_32x8` (same 768 bytes) | **0** | **674288** |
| `img_interpolate` (true vs absent, 16x16 at 200 pt) | **0** | **679818** |
| `img_colorkey_mask_wide` (`/Mask [0 160 ...]`) | **0** | **108941** |
| `img_stencil_mask` (`/Mask` ImageMask stream) | **0** | **348194** |
| `smask_matte_graded` (`/Matte [1 1 1]`) | **0** | **653022** |

On 010 neither leg carries `/Mask` or `/Matte`. The WeasyPrint leg writes `/Interpolate
false` 26 times and typst writes nothing, which paints the same (`grep -a -c`,
pdfimages `interp` all "no"). So 010's green verdict stands, but a leg that changes any of
these keys would pass the gate. A fix must treat `false` the same as an absent key.

**Ratchet target (WP-3.0g).** `ratchet_pages` runs on every staged non-adhoc run.
`below_target` covers every measured page, including pages the baseline does not hold.
Every way out that skips measurement fails the gate: `not_measured` and `unseeded` are not
in `all_evaluated_pass`, a stale digest refuses to run, and a failed typst leg fails
`tier_s_pass`. `self_comparison` passes only when both legs are the same bytes, which is
the oracle-only mode. Control, run once in this worktree with `tiers.g.g1_pt` set to 0.005
(page 3's dy is 0.005792) and parity.yaml then restored (`git status` clean): exit **1**,
exactly `page 3: tier lowered from E to none` and `page 3: tier none is below the ratchet
target E`, with every other clause passing. One page below E fails the run.
The target itself is read from the working parity.yaml, not checked against HEAD the way
baseline.json is. Weakening it means editing the spec, which review sees. Recorded here,
not a defect.

**Impose exact path (WP-0.2w).** `exact::authored` binds reals in lopdf order to lexed
tokens. It fails loud on a count mismatch and on any token whose f32 is not lopdf's real.
It skips strings, names, comments and hex, and stops at `stream`/`endobj`. Duplicate
keys produce a count mismatch. I found no input that binds a wrong decimal silently. The
committed ObjStm test passes inside `cargo test`.

## 3. Baseline raise re-derived (rule 3)

Comparing a tip run's proposal with baseline.json proves nothing on its own: `raised` keeps
the committed E. So I built scratch worktree `tmp/v30g-raise` at the tip, committed
`50dec1e`'s baseline.json there (54 x `none`, commit `a69af82`, never landed), and ran
`MAG_PARITY_OUT_DIR=v30g-out/raise mag parity 010 --run editions/010/run-2026-09-13T01-34-51`:
exit 0. The proposal's `pages` (54 x E, clauses page_count, boxes, text, color, navigation)
and `staged_input_digest` (`ae9d6daf...7d1f`) equal the committed baseline.json. The only
difference is `schema_note`, which is carried over from the recorded file (the 3.0g sentence).
**The raise is confirmed.**

## 4. Two clean staged runs

`MAG_PARITY_OUT_DIR=v30g-out/s{1,2} mag parity 010 --run editions/010/run-2026-09-13T01-34-51`,
release build of the tip: exit **0**, exit **0**. Both runs: staged inputs fresh `ae9d6daf...`;
ratchet pass (target E, 54 checked/recorded/measured, 0 regressions); S all pass; E display
58850 vs 58850 pass; glyph 58623 glyphs, ratio 0.0000, 0 violations; V2 0.000336. The typst
reader.pdf is `6709dc15...` in both, the same as WP-0.2x. With `a_reader_sha256`
(`aeb81112...` / `25c2101e...`, WeasyPrint's dates) and render-dir timestamps normalized,
the verdicts are identical (sha256 `54f50b72...`). Both `baseline-proposed.json` files are
byte-identical and JSON-equal to the committed baseline.json.

## 4b. Re-run after the tip moved (`5f73d8d`, WP-3.9 + WP-0.0f)

WP-0.0f changed the WeasyPrint adapter, and its worker rebased `staged_input_digest` in
baseline.json to `bc49b2aa...`. Rule 3 reserves baseline edits to verifiers, so I checked
it. Rebuilt at `5f73d8d` and ran staged twice again (`v30g-out/s3`, `s4`): exit **0**, exit
**0**. Staged inputs fresh `bc49b2aa...`, ratchet pass (54, 0 regressions), display
58850 vs 58850, glyph ratio 0.0000, V2 0.000336, typst reader.pdf `6709dc15...`. The
normalized verdicts are identical (`f08ea943...`). Both proposals are JSON-equal to the
committed baseline.json, digest included, so **the digest rebase is confirmed**. Pages
are unchanged. Sections 3 and 4 above were measured at the previous digest `ae9d6daf...`.

## Tests committed (`mag/src/parity/streams.rs`, `#[ignore]`, each fails today)

- `the_same_samples_in_another_shape_are_another_picture`
- `image_keys_poppler_paints_by_are_traced_or_fail_loud`, which today reports
  `["Interpolate", "Mask colour key", "Mask stencil", "SMask Matte"]`
- `a_jpeg_whose_colour_transform_readers_infer_differently_is_told_apart_or_fails_loud`

Each test requires the plain image to trace (`expect`) and requires the variant either to
trace to a different element or to fail loud. `cargo test -- --ignored` on these: 3
failed, each at its assertion. `cargo fmt --check` 0, `cargo clippy --all-targets -- -D
warnings` 0, `cargo test` 0: 32 result lines, 865 passed, 0 failed, 27 ignored (3 tests x
9 crates that include streams.rs).
  Rebased onto `3a9c434` (WP-3.9, typeset only; its evidence records the 010 typst
  reader.pdf still `6709dc15...`): fmt 0, clippy 0, `cargo test` 0, 870 passed, 0 failed,
  27 ignored.

## What is and is not proven

- Proven: the replay and the floor are unchanged since WP-0.2x. 010 staged exits 0 twice
  with identical verdicts after normalization. The E baseline equals a proposal measured
  from a `none` baseline. One page below target fails the run. Sub-tolerance shifts,
  scales and thin rules paint no visible difference, beyond raster-grid artifacts from
  real 0.0049 pt moves.
- Not proven: agreement with any renderer other than poppler. The JPEG colour-inference
  rule follows libjpeg, so a reader that follows the PDF default (YCbCr without an Adobe
  marker) would paint `rgbids_nojfif` differently again. Image keys beyond the ones
  attacked here (`/Intent`, `/Alternates`, `/OC`) were not probed. The zero-length dot and
  canonical rounded-key decisions were probed on these pairs only.
