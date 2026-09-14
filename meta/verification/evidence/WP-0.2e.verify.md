# WP-0.2e verification

Verdict: **ACCEPTED**, with one finding directed at WP-0.2f (below). Every
target and verify clause of WP-0.2e is met; the finding concerns how the
plan's floor-fixture set models what the new definition still admits, not
anything this WP did wrong.

## Base

WP commit `4f0828f`, verified in a fresh worktree at that commit.
Pre-change comparator built from `7d79b9d` to establish the failure direction.

## Owns

`git show --stat 4f0828f` lists exactly three files: `mag/src/parity/streams.rs`,
`meta/verification/parity.yaml`, `meta/verification/evidence/WP-0.2e.md`.
No `*.verify.md`, no `baseline.json`, no Cargo files, nothing outside Owns.
`display.rs` is in the WP's Owns and was correctly left untouched (see below).

## Baseline

In the worktree at `4f0828f`: `cargo build` clean, `cargo fmt --check` clean,
`cargo clippy --all-targets -- -D warnings` clean, `cargo test` green
(nocomments plus the WP-0.2d fault suite, 20.78 s).

## Translation preservation, checked arithmetically

The claim that the new translation components reproduce the old `x`/`y`
exactly is the guarantee that no existing positional comparison regressed, so
it was derived from the code rather than taken on trust.

`mul(a, b)` is the row-vector convention, and with `params = [Tfs*Th, 0, 0,
Tfs, 0, Ts]` and `b = Tm . CTM = [a, b, c, d, e, f]`:

    trm_new[4] = params[4]*b[0] + params[5]*b[2] + b[4] = Ts*c + e
    trm_new[5] = params[4]*b[1] + params[5]*b[3] + b[5] = Ts*d + f

The old code recorded `apply(trm_old, 0.0, Ts) = (c*Ts + e, d*Ts + f)`.
Identical, exactly, with no tolerance involved.

`size_eff` is likewise unchanged: old `size * sqrt(c^2 + d^2)` versus new
`sqrt((size*c)^2 + (size*d)^2)`, which is the same value since the size
factors out of the norm.

The change is therefore strictly stronger: the old `(x, y)` and the old image
bounding box are both recoverable from the new matrices, and the sign
information the bounding box destroyed is now retained.

## Fixture matrix, verified in both directions

All four blind-spot fixtures were checked against both comparators, not the
two the brief required. Fixtures were regenerated from the evidence's own
generator (extended with my probes), built programmatically, never `pdfunite`.

| fixture | pre-change (`7d79b9d`) | post-change (`4f0828f`) |
|---|---|---|
| base (control) | pass, exit 0 | pass, exit 0 |
| text_mirror | **pass, exit 0** | fail, exit 1 |
| text_rot180 | **pass, exit 0** | fail, exit 1 |
| image_flip | **pass, exit 0** | fail, exit 1 |
| glyph_ligature | **pass, exit 0** | fail, exit 1 |

All four genuinely pass under the old definition, so they are blind spots
rather than merely undetected faults, as claimed.

Tier S text was checked on `text_mirror`: `text: pass` while
`display_list: fail`, confirming text extraction cannot see these faults and
the display list is what catches them.

## My own false-fail probes

Two probes the worker did not run, both of which MUST compare equal or the
new definition would false-fail on legitimate engine differences:

| probe | construction | result |
|---|---|---|
| `fontsplit` | `Tf 12` with `Tm 1 0 0 1 100 700` versus `Tf 1` with `Tm 12 0 0 12 100 700`; renders identically | **pass, exit 0** |
| `subset_recode` | same glyphs shown as codes 65/66 versus codes 1/2, with matching `FirstChar`, `Widths` and `ToUnicode`, same `BaseFont` | **pass, exit 0** |

`fontsplit` confirms the worker's engine-agnostic argument: baking the font
size into the matrix is what makes the two encodings compare equal, where a
raw `Tm` linear part would have false-failed. `subset_recode` confirms glyph
count does not false-fail under independent subsetting, which is exactly why
count rather than raw CID codes was the right choice.

## Edition 010 regression

Both render trees copied in and compared, twice each:

    A-vs-A run1 exit=0 fd6608a2db8f01fe
    A-vs-A run2 exit=0 fd6608a2db8f01fe
    A-vs-B run1 exit=0 28d7c3a2b0374ab0
    A-vs-B run2 exit=0 28d7c3a2b0374ab0

Both digests match the evidence exactly and are byte-identical across runs.
All clauses pass; `tier E raster` correctly reports
`not_evaluated (WP-0.2d raster_bound derivation)`.

Operational note for the next verifier: a first batch of these runs returned
exit 2 with a stale digest because the 87 MB render trees were still being
copied. Re-running after the copy settled gave exit 0 and the correct
digests. An exit 2 here means the tracer errored, not that a clause failed.

## Other claims

- `normalization.color_space_map` is deleted from `parity.yaml`; the diff
  removes exactly that key and nothing else in the file.
- Glyph count is recorded as a `usize` count; raw character codes are local
  to `decode_show` and are not recorded, as required.
- `display.rs` genuinely needed no change. Its only `Element::Text` use is
  `Element::Text { s, fill, .. }` at line 389 in `color_sequence`, which
  ignores the changed fields, and its `rect` field (lines 18, 97-104) is the
  annotation `/Rect` for the navigation clause, unrelated to image placement.
  No other file in `mag/src` references either variant.
- Fail-loud guards are intact, including `Tr != 0`, ExtGState alpha and
  SMask, unsupported operators, filters, colour spaces and XObject subtypes.

## Finding for WP-0.2f: the linear quantum is not a positional bound

The 0.01 quantum applied to the linear matrix components does not deliver a
0.01 pt positional guarantee for text, because the linear part multiplies the
accumulated intra-show advance. A sub-quantum difference therefore amplifies
with run length.

Measured with two probes on a 34-glyph run (226.848 pt at 12 pt, a realistic
full-measure line):

| probe | construction | quantized | line-end displacement | result |
|---|---|---|---|---|
| `long_aniso` | `Tm[0] = 1.0004158`, so `trm[0] = 12.00499` | 1200, same as base | 0.0943 pt | **pass, exit 0** |
| `long_rot` | rotation 0.000415 rad, so `trm[1] = 0.00498` | 0, same as base | 0.0941 pt | **pass, exit 0** |

So up to roughly 0.094 pt of intra-line displacement passes the display list:
9.4x the 0.01 pt coordinate quantum, and 5.4x the 0.017432 pt drift that
revision 10 adopts as its intra-line floor fixture.

This is not a regression and not grounds for rejection. It is a property of
quantizing a linear map, it does not affect images (their matrix maps the
unit square directly, so the error stays bounded by the half-quantum with no
amplification), and revision 10 already states that intra-line glyph
placement is verified photometrically rather than geometrically. The finding
is that the magnitude which passes geometrically is larger than the plan's
fixture set models.

Why it matters concretely: revision 10 derives WP-0.2f's reachability floor
from two fixtures, bucket extremes and WP-1.6's 0.017432 pt intra-line drift.
Neither models matrix-quantization-admitted displacement of ~0.094 pt. If a
real engine pair exhibits it, the derived floor understates the worst
legitimate case, and WP-0.2f could set a bound that legitimate pairs exceed.

Recommended, for WP-0.2f rather than for this WP:

1. Add a third floor fixture: a text run whose TRM linear components differ
   by just under half a quantum over a full-measure line, and take the floor
   as the max over all three fixtures.
2. In Tier E's wording, distinguish translation components (a direct 0.01 pt
   positional bound) from linear components (a bound scaling with run
   length), so the quantum is not read as a flat positional guarantee.

## Blind-spot enumeration

For text and image placement the enumeration is now complete as far as I can
establish, with the above precision caveat. What remains after this WP, per
revision 10 and confirmed by reading: intra-show glyph positioning
(advances, `Tc`/`Tw`, kerning whose adjustments cancel), equal-count
equal-advance glyph substitution such as a stylistic alternate, optional and
marked content, and annotation appearance streams. `Tr != 0` fails loud
rather than being compared, so it is not a hole.

## Status

done
