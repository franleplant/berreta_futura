# WP-0.2f rasterizer selection and the raster bound

## Base

`6e8abb8` (worktree base, `feat(parity): WP-0.0c opener header carries data-article-id`).
Derived under revision 10's two-sided rule as extended by revision 13's third
floor fixture (linear text-matrix displacement). Plan revisions 11 to 14 landed
from other lanes while this WP ran; none changes the rule this WP was measured
against.

## Status

`blocked`

No rasterizer configuration reaches the required `ceiling >= 2x floor`. The
dominant floor term is the linear text-matrix displacement that revision 13
identified and assigned to WP-0.2g as a removable defect. This WP does not
widen the bound, does not drop a fixture, and writes no
`tiers.e.raster_bound.value`; the Tier E raster clause keeps reporting
`not_evaluated`.

## Tool versions

- poppler 25.08.0 (`pdftoppm`, `pdftocairo`), already pinned in `parity.yaml tools.poppler`
- mupdf 1.26.4 (`mutool draw`), installed by this WP as a candidate, NOT pinned because the WP is blocked
- pypdf 6.14.2, Python 3.12.11, uv 0.8.17
- display tracer lopdf-0.45.0, unchanged

## Commands

Fixture generation, from the repo root. `$F` is the scratch fixture dir and
`$R` the oracle leg used as the base of every fixture:

```
F=/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02f_fix
R=editions/010/render-2026-09-14T01-47-59/en/reader.pdf
uv run python $F/fixtures.py $R $F/trees
uv run python $F/safe_bucket.py $R $F/trees 0.49
uv run python $F/trm_only.py $R $F/trees 0.0045 trm_0045
uv run python $F/trm_only.py $R $F/trees 0.0020 trm_0020
uv run python $F/trm_only.py $R $F/trees 0.0    trm_zero
```

`fixtures.py` writes, from one oracle `reader.pdf`: `orig`; `bucket_lo`/`bucket_hi`
(every coordinate operand snapped to its 0.01 pt bucket centre then offset to the
bucket edge); `drift` (every glyph in every show displaced progressively by
0.000173 pt per glyph, WP-1.6's measured rate, via inserted TJ adjustments);
`kern_<m>` (a compensating TJ kern of magnitude `m` pt inserted at the middle
glyph of each show and reversed immediately after, so the total advance is
preserved); and the identity controls `kern_identity`, `drift_identity`,
`trm_identity` at magnitude 0.

Display-list equality of every fixture, which is what makes a fixture a floor or
ceiling fixture at all:

```
cd <worktree>; T=$F/trees
for v in trm_zero trm_0020 trm_0045 absbucket_lo absbucket_hi \
         kern_identity drift_identity drift kern_0p05 q0p01_all_lo trm_linear; do
  ./mag/target/debug/mag parity "c-$v" --pre-rendered $T/orig $T/$v
done
```

Raster measurement across candidate configurations (`explore.py` renders each
leg with the named tool at `dpi`, box-downsamples by `factor` to 300 dpi, and
reports the max per-channel delta over the named pages):

```
cd $F
uv run --with pillow --with numpy python explore.py 3,20 \
  drift_identity,drift,kern_0p02,kern_0p05,kern_0p1,kern_0p2
```

## Metrics

### Fixture validity, measured not assumed

A fixture only bounds anything if its two legs are display-list equal: that is
the definition of a difference the display list cannot see. Measured with
`mag parity --pre-rendered` over all 54 interior pages:

| fixture | display list | valid as |
|---|---|---|
| `kern_identity`, `drift_identity`, `trm_zero` | pass, max channel delta 0 | controls: the rewrite paths are provably inert |
| `drift` (0.000173 pt/glyph, WP-1.6's rate) | pass, 0 pages differ | floor term (ii) |
| `kern_0p02` .. `kern_0p2` | pass, 0 pages differ | ceiling fixtures |
| `bucket_lo`/`bucket_hi` (all operands) | **fail**, 50 to 52 pages differ | NOT a valid fixture as built |
| `absbucket_lo`/`absbucket_hi` (absolute operands only) | **fail**, 50 to 52 pages differ | NOT a valid fixture as built |
| `trm_linear` (delta 0.00499), `trm_0045`, `trm_0020` | **fail**, 10 to 47 pages differ | NOT a valid fixture as built |

Two construction failures are recorded rather than worked around, because they
bound what this WP could measure:

1. **Relative and accumulating operators.** `Td`/`TD` are relative to the line
   matrix and `cm` composes, so perturbing every occurrence accumulates down the
   page instead of staying inside one bucket. Restricting the fixture to
   absolute operands (`Tm` translation and path points, `absbucket_*`) does not
   fix it either.
2. **The display list quantizes DEVICE space, the fixture perturbs OPERAND
   space.** The oracle leg carries a 4/3 px-to-pt scale (see the `trm[0]`
   distribution below), so snapping an operand to a 0.01 pt grid does not snap
   the device coordinate to one, and an offset of just under half an operand
   bucket can still cross a device-space quantization boundary. Building a
   correct bucket or TRM fixture therefore requires composing the CTM, which
   means reimplementing the tracer on the Python side. Not attempted: the
   conclusion below does not depend on it, and the coordinator's standing
   instruction is to measure honestly and block rather than engineer around the
   dominant term.

### Floor and ceiling, valid fixtures only

Max per-channel delta over pages 3 and 20 (dense body text, no figures):

| fixture | role | mutool@1200/4 | mutool@2400/8 |
|---|---|---|---|
| `drift_identity` | control | 0.000 | 0.000 |
| `drift` 0.000173 pt/glyph | **floor (ii)** | 60.312 | **30.125** |
| `kern` 0.02 pt | ceiling | 60.312 | 30.125 |
| `kern` 0.05 pt | ceiling | 60.312 | 60.250 |
| `kern` 0.1 pt | ceiling | 120.500 | 90.375 |
| `kern` 0.2 pt | ceiling | 180.812 | 151.641 |

At 1200/4 the guard cannot separate WP-1.6's legitimate drift from a 0.05 pt
kern fault: both read exactly 60.312, a ratio of 1.0, because at that sampling
every sub-pixel displacement resolves to the same one-subpixel flip. At 2400/8
they begin to separate, and the best case available is:

- floor (drift alone) = **30.125**
- ceiling, if the quietest fault the guard must catch is a 0.05 pt kern = **60.250**
- ratio = **2.00**, exactly at the margin, with two floor terms still missing

### Why the missing floor terms decide it

Revision 13 establishes that the linear text-matrix components admit a
displacement of **0.1625 pt** at edition 010's body measure (10 pt over 325 pt),
16x the coordinate quantum. That is a floor term. I could not construct it as a
display-list-equal fixture, but its magnitude is bracketed by the ceiling
fixtures, which displace glyphs by a known amount: 0.2 pt of displacement
measures **151.641** at 2400/8. So the linear-matrix floor term is of order
**150**, roughly 5x the drift term and 2.5x the largest ceiling measured.

With that term included the window is not merely below 2x, it is inverted: the
floor exceeds every ceiling. This is the result revision 13 anticipated when it
sequenced WP-0.2g's tightening as the blocking fix.

### Earlier candidates, for the record

Max per-channel delta, `bucket` and `drift` as first built, pages 3 and 20:

| configuration | bucket_lo | bucket_hi | drift | kern 0.05 |
|---|---|---|---|---|
| `pdftoppm -r 300` (revision 8's choice) | 241.000 | 241.000 | 234.000 | 236.000 |
| `pdftocairo -r 300` | 106.000 | 99.000 | 61.000 | 62.000 |
| `pdftoppm` 600, box-downsample 2 | 180.750 | 180.000 | 120.500 | 120.500 |
| `pdftoppm` 1200, box-downsample 4 | 105.438 | 105.375 | 60.250 | 60.250 |
| `mutool draw -r 300` | 242.000 | 242.000 | 0.000 | 124.000 |

`mutool draw` does not grid-fit glyph outlines the way FreeType does, but it
rounds text-object origins to the device grid, so it is equally sensitive to a
sub-pixel origin shift (242) while being insensitive to intra-show kerning below
roughly 0.02 pt. `-A 8` (maximum anti-alias level) changes nothing. Supersampling
is the only lever that moves the floor, and it moves floor and ceiling together.

Decomposition under `mutool draw -r 300`, which locates the problem:

| perturbation | max channel delta |
|---|---|
| path operands only, 0.01 pt buckets | 21.000 |
| path operands only, 0.001 pt buckets | 9.000 |
| text origins only, 0.01 pt buckets | 242.000 |
| text origins only, **0.001 pt** buckets | 122.000 |

Path geometry degrades proportionally, as antialiased vector rendering should.
Text origins do not: a 10x finer quantum still yields 122, because origin
snapping means any nonzero shift can cross a rounding boundary for some glyph
among 69,071. **A finer display-list quantum would not rescue the raster guard**,
which is worth recording because it is the obvious next idea.

### Affordability

At 2400 dpi an A5 page is 277,504,355 pixels, about 5 s per leg to render plus
downsampling. A full 54-page interior comparison is roughly 108 renders, so on
the order of **9 to 15 minutes of rasterization per parity run**, against about
82 s for the whole current run. Revision 10's own standard, "a gate nobody can
afford to run is not a gate", is relevant even if the window had opened.

## Verdicts

| run | display list | max channel delta (pdftoppm@300, all 54 pages) |
|---|---|---|
| `c-trm_zero` | pass, 0 pages | 0 |
| `c-kern_identity` | pass, 0 pages | 0 |
| `c-drift` | pass, 0 pages | 241 |
| `c-kern_0p05` | pass, 0 pages | 241 |
| `c-trm_0020` | fail, 10 pages | 241 |
| `c-trm_0045` | fail, 36 pages | 241 |
| `c-trm_linear` | fail, 47 pages | 241 |
| `c-absbucket_lo` | fail, 50 pages | 241 |
| `c-absbucket_hi` | fail, 52 pages | 241 |
| `c-q0p01_all_lo` | fail, 52 pages | 241 |

`tiers.e.raster_bound.value` is absent, so every one of these runs reports
`tier E raster: not_evaluated`. No verdict digests are recorded as binding,
because no configuration was pinned.

## Residuals

- **For WP-0.2g, the linear component distribution it needs.** Across the oracle
  leg's 1,471 text matrices there are **26 distinct `trm[0]` values**, and they
  are **not** clean font sizes: the most common are 13.333 (1,068
  occurrences), 9.0664 (169), 12.7998 (55), 8.666 (39), 24.666 (39), with 10.0
  and 40.0 appearing only 12 and 9 times. The pattern is a 4/3 px-to-pt scale
  composed into `Tm`, so the values are non-terminating decimals rather than
  whole font sizes. WP-0.2g should not assume "both engines emit clean values"
  without checking the Typst leg; on the WeasyPrint side they are clean only in
  the sense of being a fixed rational multiple of a font size.
- **What a derived bound would and would not have covered.** Following the
  verifier's distinction: the translation components of a matrix are lengths and
  the 0.01 pt quantum bounds their contribution directly; the linear components
  are ratios whose positional effect scales with accumulated run length, so the
  same quantum admits 16x more displacement at body measure. Any bound derived
  from translation-space fixtures alone understates the floor accordingly.
- **Two floor fixtures remain unbuilt**, per the construction failures above.
  When WP-0.2g has tightened the linear quantum and the floor is re-derived,
  building them correctly needs a CTM-composing perturbation, i.e. the
  perturbation applied in device space through the existing Rust tracer rather
  than through pypdf on raw operands. Recommend the re-derivation be done in
  Rust for that reason.
- **mupdf 1.26.4 was installed on this machine** as a candidate and is left
  installed. It is not pinned in `parity.yaml tools:` because no configuration
  was selected; if a later WP adopts it, it must pin the version and assert it
  at startup like the other tools.
- `mag/src/parity/raster.rs` is **unchanged**. A blocked WP ships no half-built
  rasterizer configuration, and the existing `pdftoppm -r 300` path continues to
  serve the Tier V meters, which gate nothing.
- The `drift` fixture reproduces WP-1.6's rate (0.000173 pt per glyph) over all
  69,071 glyphs in 1,503 shows, and is display-list equal, so it is available as
  a ready-made floor fixture for the re-derivation.
