# WP-0.2d fault suite and calibration

## Base

0465b73 (refactor(parity): WP-0.2c critique fixes)

## Rework after verifier rejection (83d7bee)

The verifier rejected the fault suite. `failing_clauses` tested the Tier V
meters with `v["v1"] == false` / `v["v2"] == false`, but the comparator emits
those fields as JSON strings (`"pass"` / `"fail"`, see `RasterTier` in
`mag/src/parity/raster.rs`), so both branches were dead and no verdict could
ever report v1 or v2. The committed matrix was therefore wrong for two faults,
and the "asserted exactly" claim was made against an observer blind to a whole
clause family.

The fix replaces the hand-listed clause checks with `clause_states`, which
reads every clause family generically from the verdict: each `tier_s` and
`tier_e` child carrying a `status` string (so `code_blocks` and `critic`
report `not_evaluated` rather than going unseen), the `v1` and `v2` strings
under `tier_v`, and `raster_dimensions` from `dimension_mismatches`. The
`tier_e.raster` key maps to the vocabulary name `raster_guard`. It also
asserts the comparator invariant that `tier_v.status` fails exactly when
`dimension_mismatches` is non-empty. `failing_clauses` is now a filter over
that map, so it cannot drift from the verdict schema.

`assert_vocabulary_observable` is the recurrence guard, run on the control
verdict and on every fault verdict. It fails if any name declared in
`fault_suite.clause_vocabulary` is unobservable, and it fails if any clause
the verdict actually evaluates (status other than `not_evaluated`) is absent
from the vocabulary. Proven to fire: with the `v1`/`v2` lookup removed, the
suite fails with `declared clauses unobservable: ["v1", "v2"]`, which is
exactly the rejected defect.

Re-derived matrix, measured by the fixed observer (not copied from the verify
file). It agrees with the verifier's corrections in both rows:

| fault | must_flag | worst page fraction | max channel delta | v1/v2 |
|---|---|---|---|---|
| swapped_words | color, display_list, text | 0.000446 | 241 | pass/pass |
| line_moved_005 | display_list | 0.000585 | 241 | pass/pass |
| line_moved_03 | display_list | 0.000879 | 241 | pass/pass |
| figure_shifted_page | display_list, v1, v2 | 0.043412 | 255 | fail/fail |
| recolor_30px | display_list, v1, v2 | 0.020341 | 255 | fail/fail |
| body_ink_pure_black | color, display_list | 0.000000 | 22 | pass/pass |
| dropped_link_annotation | display_list, navigation | 0.000000 | 0 | pass/pass |
| mediabox_off_05 | boxes, display_list, raster_dimensions | 0.000000 | 0 | pass/pass |

Only `figure_shifted_page` and `recolor_30px` changed; the other six rows are
unchanged. `parity.yaml` edits are confined to those two `must_flag` lists.

Fragility, recorded rather than tuned away, per the verifier's note:
`line_moved_03` differs on 0.000879 of its worst page against the V2 threshold
of 0.001, inside it by 12 percent, so a small fixture change could move that
row into `v2`. `line_moved_005` (0.000585) and `swapped_words` (0.000446) sit
further under the same threshold. The fixture is untouched; if a future change
flips the row, the matrix assertion fails loudly and the row is re-derived.

Re-run: `cargo test` green, fault suite 19.0 s; `cargo fmt`, `cargo clippy
--all-targets -- -D warnings`, and the no-comments check all clean.

## Status

blocked

The fault suite deliverable is complete and green after the rework above: it
runs under `cargo test` and asserts the expected-detections matrix exactly,
and `critic_metric_tolerances:` is authored with its near-threshold fixture
list. The third, `tiers.e.raster_bound.value`, is NOT authored: the plan's
prescribed derivation measures 241 of 255, which would leave the Tier E
raster guard accepting every differing pixel below 242 and contradicts the
plan's "raster zero-diff" gate. Protocol rule 4 reserves that change to a
plan revision, so this WP stops rather than recording it. The comparator
keeps reporting the guard as `not_evaluated`, which is the correct loud
state. See "The raster_bound gap" below for the numbers and the
recommendation.

## Commands

All commands run from the repo root. Scratch lives under
`$JOB/tmp/wp02d` (`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02d`);
nothing under it is required to reproduce the committed suite.

The committed suite, which needs no renderer, no Python and no fixtures on
disk (it builds both legs with lopdf):

```
cd mag && cargo test --test parity_faults
```

Seeded faults the plan's way (scratch worktree, tracked files untouched).
Create the worktree, copy the untracked run dir in, then run the seeding
driver, which renders a baseline plus six faults and restores each edit with
`git checkout --` before the next:

```
git worktree add $JOB/tmp/wp02d-faults 0465b73
cp -R editions/010/run-2026-09-13T01-34-51 $JOB/tmp/wp02d-faults/editions/010/
cd $JOB/tmp/wp02d-faults && uv run python $JOB/tmp/wp02d/seed_faults.py
```

`seed_faults.py` applies, one at a time: two adjacent words swapped in the
alignment article's `final.md`; `main { position: relative; top: 0.05pt; }`
appended to `weasyprint-a5.css`; the same at `0.3pt`; the `four-incidents`
figure anchor moved from `How we found the fourth` to `The others` in
`edition.yaml`; 30 pixels inverted in the alignment source's `media/001.png`;
and every `rgb(5.5% 7.5% 8.5%)` in the CSS replaced by `rgb(0% 0% 0%)`. It
prints `worktree status after: ''`, so the worktree ends clean.

The two PDF-level faults are pypdf surgery on the seeded baseline (the plan's
CSS route cannot drop an annotation or move a MediaBox):

```
uv run python - <<'EOF'
from pypdf import PdfWriter
from pypdf.generic import NameObject, ArrayObject
src = "$JOB/tmp/wp02d/trees/baseline/en/reader.pdf"
w = PdfWriter(clone_from=src)
for i, page in enumerate(w.pages[1:-1], start=2):
    annots = page.get("/Annots")
    if annots:
        page[NameObject("/Annots")] = ArrayObject(list(annots)[1:])
        break
open("$JOB/tmp/wp02d/trees/dropped_link_annotation/en/reader.pdf", "wb").write(b"") or w.write(open("$JOB/tmp/wp02d/trees/dropped_link_annotation/en/reader.pdf", "wb"))
w = PdfWriter(clone_from=src)
box = w.pages[3].mediabox
w.pages[3].mediabox.upper_right = (float(box.right), float(box.top) + 0.5)
w.write(open("$JOB/tmp/wp02d/trees/mediabox_off_05/en/reader.pdf", "wb"))
EOF
```

Each seeded fault is then compared against the seeded baseline:

```
./mag/target/debug/mag parity real-<fault> --pre-rendered \
  $JOB/tmp/wp02d/trees/baseline $JOB/tmp/wp02d/trees/<fault>
```

The raster_bound derivation. `perturb.py` clones the oracle leg through
pypdf (`PdfWriter(clone_from=...)`, pages attached to the writer before
`replace_contents`) and adds a uniform random offset within half the 0.01 pt
quantum to every coordinate operand of `m l c v y re cm Td TD Tm`, seed 0;
it writes an unperturbed control through the same path:

```
uv run python $JOB/tmp/wp02d/perturb.py \
  editions/010/render-2026-09-14T01-47-59/en/reader.pdf $JOB/tmp/wp02d/perturb2
./mag/target/debug/mag parity perturb2-control --pre-rendered \
  $JOB/tmp/wp02d/perturb2/orig $JOB/tmp/wp02d/perturb2/control
./mag/target/debug/mag parity perturb2-bound --pre-rendered \
  $JOB/tmp/wp02d/perturb2/orig $JOB/tmp/wp02d/perturb2/perturbed
```

Decomposition by operand class (`text` = Td/TD/Tm only, `path` =
m/l/c/v/y/re only) and the rasterizer-variant probe on one page:

```
uv run python $JOB/tmp/wp02d/perturb.py <src> $JOB/tmp/wp02d/pert-text text
uv run python $JOB/tmp/wp02d/perturb.py <src> $JOB/tmp/wp02d/pert-path path
./mag/target/debug/mag parity pert-text --pre-rendered .../orig .../perturbed
./mag/target/debug/mag parity pert-path --pre-rendered .../orig .../perturbed
pdftoppm -r 300 -f 4 -l 4 [-aa no | -freetype no] <pdf> <prefix>
```

Critic metric survey over the oracle leg's critic report:

```
python3 $JOB/tmp/wp02d/critic_metrics.py \
  editions/010/render-2026-09-14T01-47-59/en/render-critic.json
```

Repo checks:

```
cd mag && cargo fmt --check && cargo clippy -q --all-targets -- -D warnings && cargo test
python3 tools/nocomments.py
git status --short
```

Rework replay (poppler 25.08.0 must be on PATH; no render or run directory is
needed, the suite builds both legs itself):

```
cd mag && cargo test --test parity_faults
```

Per-fault raster numbers behind the re-derived matrix, read from the verdicts
the run above leaves in `output/parity/fault-<name>/verdict.json`:

```
python3 -c "
import json
names=['swapped_words','line_moved_005','line_moved_03','figure_shifted_page','recolor_30px','body_ink_pure_black','dropped_link_annotation','mediabox_off_05']
for n in names:
    v=json.load(open(f'output/parity/fault-{n}/verdict.json'))['tier_v']
    print(n, v['worst_page_fraction'], v['max_channel_delta'], v['v1'], v['v2'])
"
```

Recurrence-guard proof: replace the meter list in `clause_states` with an
empty one, which reproduces the rejected blindness, and confirm the suite
fails with `declared clauses unobservable: ["v1", "v2"]`, then restore it:

```
cp mag/tests/parity_faults.rs /tmp/pf_backup.rs
python3 - <<'EOF'
p='mag/tests/parity_faults.rs'
s=open(p).read().replace('    for meter in ["v1", "v2"] {','    for meter in [] as [&str; 0] {')
open(p,'w').write(s)
EOF
cd mag && cargo test --test parity_faults 2>&1 | grep -E "panicked|unobservable"
cp /tmp/pf_backup.rs mag/tests/parity_faults.rs
```

## Tool versions

As pinned in `meta/verification/parity.yaml tools:` and asserted by
`mag parity` at startup: poppler 25.08.0 (pdfinfo, pdftotext, pdftoppm),
display tracer lopdf 0.45.0, rustc 1.96.0, python 3.12.11, uv 0.8.17,
weasyprint 69.0, pypdf 6.14.2, pillow 12.3.0. Test-only additions to
`mag/Cargo.toml` dev-dependencies: lopdf 0.45.0, serde_json 1, serde_yaml
0.9, all already direct dependencies of the binary.

## Metrics

### Fault suite

`cargo test --test parity_faults`: 1 test, 20.6 s wall clock, 9 comparator
invocations (one clean control plus eight faults). The clean pair flags
nothing and exits 0; every fault exits 1, is flagged by its intended check,
and none passes Tier E display-list equality.

| fault | intended check | clauses flagged |
|---|---|---|
| swapped_words | text | color, display_list, text |
| line_moved_005 | display_list | display_list |
| line_moved_03 | display_list | display_list |
| figure_shifted_page | display_list | display_list |
| recolor_30px | display_list | display_list |
| body_ink_pure_black | color | color, display_list |
| dropped_link_annotation | navigation | display_list, navigation |
| mediabox_off_05 | boxes | boxes, display_list, raster_dimensions |

Two rows are worth reading twice. `line_moved_005` and `line_moved_03` are
caught by Tier E alone: both sit inside G2 (0.5 pt) and neither moves enough
pixels to trip the V meters, so the display list is the only clause that
sees them. `body_ink_pure_black` is caught by the color clause and not by
any raster meter, which is exactly the case the plan's color clause exists
for: the 14/19/22 body ink against pure black is a per-channel delta of at
most 22, below the V threshold of 24.

### Seeded faults, the plan's route

Rendered in a throwaway worktree at 0465b73, six renders at 59-69 s each,
baseline `render-2026-09-14T14-30-57`. The worktree ended clean
(`git status --short` empty), and no tracked file in the main tree changed.

Every seeded fault exits 1, is flagged by its intended check, and none
passes Tier E display-list equality.

| fault | clauses flagged | pages differing (display list) | max channel delta |
|---|---|---|---|
| swapped_words | color, display_list, text | 1 | 241 |
| line_moved_005 | display_list, navigation, v1, v2 | 52 | 255 |
| line_moved_03 | display_list, navigation, v1, v2 | 52 | 255 |
| figure_shifted_page | color, display_list, text, v1, v2 | 5 | 241 |
| recolor_30px | display_list | 1 | 128 |
| body_ink_pure_black | color, display_list | 47 | 22 |
| dropped_link_annotation | display_list, navigation | 1 | 0 |
| mediabox_off_05 | boxes, display_list, raster_dimensions | 1 | 0 |

The two routes agree on every intended check. Rendered faults trip more
clauses than their synthetic counterparts because a real fault propagates
through layout: moving a figure reflows the text around it, and shifting the
page body moves the link annotations with it. The one row that matters most
confirms the plan's own prediction on real output: `body_ink_pure_black`
measures a max channel delta of 22, below the V threshold of 24, so no
raster meter sees it and the color clause is what catches it.

### critic_metric_tolerances

Surveyed over edition 010's `render-critic.json`: 1450 integer leaves, 631
float leaves across 56 pages. Integer metrics compare exactly; float metrics
compare within a fixed relative epsilon of 1e-6, and any metric within 10x
that epsilon of a decision threshold needs a near-threshold fixture.

Exactly one metric qualifies: `pages[39].largest_void.height_points` is
96.0, and `VOID_MIN_HEIGHT_POINTS` is 96.0, so the relative margin is 0.0.
The decision is `void["height_points"] >= VOID_MIN_HEIGHT_POINTS`, so one
ulp of evaluation-order slack between the Python and Rust float pipelines
flips that void between reported and unreported. WP-5.3b carries a fixture
for it.

The next-closest margins are far outside the window: void heights of 92.0
and 100.0 against 96.0 (relative 0.042), `largest_void.width_fraction` 0.939
against 0.9 (0.043), tail-band height against its declared height (0.694),
and the smallest non-zero `ink_ratio` 0.046483 against SPARSE_INK_RATIO
0.004 (10.6).

### The raster_bound gap

The plan's derivation, run exactly as specified: 24452 coordinate operands
perturbed uniformly within half the 0.01 pt quantum, rasterized at 300 dpi
against the original over the interior domain.

| fixture | max per-channel delta | worst page fraction |
|---|---|---|
| control (same rewrite, amplitude 0) | 0 | 0.000000 |
| perturbed, all coordinate operands | 241 | 0.013878 |
| perturbed, text positioning only (Td/TD/Tm) | 241 | 0.002275 |
| perturbed, path operands only (m/l/c/v/y/re) | 241 | 0.000702 |

The control is display-list equal and raster zero-diff, so the pypdf rewrite
contributes nothing of its own; the 241 is the perturbation.

The cause is not image resampling: edition 010 carries figures on pages 12,
37 and 42, while the 241 appears on nearly every compared page, and text
operands alone reach it. It is FreeType grid-fitting. At 300 dpi a glyph
stem snaps to the pixel grid, so a sub-quantum shift can move the stem a
whole pixel and flip that pixel between paper (255) and body ink (14): a
delta of 241.

No rasterizer setting rescues it. On page 4 of the text-only fixture,
`pdftoppm -r 300` measures 241 with 29387 channels beyond the V threshold;
`-aa no` still measures 241 (14832 channels); `-freetype no` measures 0 only
because poppler then fails to build any embedded font ("Couldn't create a
font for DBKKNM+Magazine-Sans-Semi-Bold") and renders no text at all.

Recording 241 would mean the Tier E raster guard passes every differing
pixel below 242 of 255, which is not the "raster zero-diff" the plan gates
on. Since the plan's own rationale for the bound is that it is "exactly as
tight as the quantum permits and nothing more", and the measurement shows
the quantum permits a full ink-to-paper flip, the bound as specified cannot
serve as a guard. Rule 4 reserves that decision to a plan revision.

Recommendation for the revision, in preference order:

1. Drop the raster guard from Tier E and keep raster as Tier V progress
   meters only. Display-list equality already compares every glyph, path,
   clip and image at the 0.01 pt quantum, and the raster pass adds nothing
   a grid-fitting rasterizer can measure reliably.
2. Keep a raster guard but define it as "zero pixels differing beyond the V
   channel threshold of 24", a decidable, tight clause that does not need a
   derived bound. The perturbation fixture would fail it, which is the
   honest answer: sub-quantum noise does change rendered pixels.
3. Keep the derivation but rasterize both legs through a renderer without
   glyph grid-fitting. No poppler flag provides this, so this option needs a
   different rasterizer and a new pinned tool.

## Verdicts

Synthetic suite (`output/parity/fault-*/verdict.json`, digests truncated to
16 hex characters; all Tier E display-list `fail` except the control):

| run | sha256 (first 16) |
|---|---|
| fault-control | 5f6bf1613db46b87 |
| fault-swapped_words | fefe15082038e3a4 |
| fault-line_moved_005 | ed20c6bd967c4eee |
| fault-line_moved_03 | 877f2f9b300cdad3 |
| fault-figure_shifted_page | 5cc6e508bca0f2e9 |
| fault-recolor_30px | b73406b1a9e5b7ce |
| fault-body_ink_pure_black | 9e3126cefa57c8b2 |
| fault-dropped_link_annotation | 5e58651a8980103a |
| fault-mediabox_off_05 | 49d40b1a18aef767 |

Calibration runs:

| run | sha256 (first 16) | result |
|---|---|---|
| perturb2-control | 500ea71ff756eae4 | all clauses pass, max channel delta 0 |
| perturb2-bound | cd203aecebaae483 | display list fail, max channel delta 241 |
| pert-text | 59e66c6240140477 | display list fail, max channel delta 241 |
| pert-path | 9d6d013f93f5a0e1 | display list fail, max channel delta 241 |

Seeded-fault runs (`output/parity/real-*/verdict.json`), all Tier E
display-list `fail`:

| run | sha256 (first 16) |
|---|---|
| real-swapped_words | 1312e3369e7da87f |
| real-line_moved_005 | 4bb5497082d9e80b |
| real-line_moved_03 | 9215054139dca013 |
| real-figure_shifted_page | 28846aae75d2316a |
| real-recolor_30px | 516cb4ad29762c8c |
| real-body_ink_pure_black | 6254f29ed13eba40 |
| real-dropped_link_annotation | f18405803d47d405 |
| real-mediabox_off_05 | d072ed096687aac7 |

These digests bind to the seeded PDFs, which are scratch and not kept; the
verdicts record each leg's reader.pdf sha256, and the seeding driver is
deterministic given the same base commit and run directory.

## Residuals

- `tiers.e.raster_bound` carries the measurement and `status: blocked` but no
  `value`, so `mag parity` continues to report the Tier E raster guard as
  `not_evaluated` naming WP-0.2d. Nothing downstream silently passes.
- The plan says the seeded faults are built by rendering scratch copies and
  that "the test asserts the matrix exactly". Those two cannot both hold for
  a committed test: the seeded PDFs are 87 MB each, they need WeasyPrint,
  and WeasyPrint is deleted in WP-6.1. The committed suite therefore builds
  equivalent faults in Rust and asserts the same matrix, while the rendered
  seeding was performed once here and is recorded above. Both routes agree.
- Perturbation covers page content streams only; drawing inside Form
  XObjects is not perturbed. Unperturbed content contributes zero delta, so
  it cannot inflate the measured maximum.
- `pdftotext` reading order on the contents page (page 3) is unstable under
  sub-quantum perturbation: the perturbed fixture reports a Tier G dy of
  293 pt there because two entries at tied y positions swap in the extracted
  order. It affects Tier G and the text clause on that page only, and it is a
  property of the pinned extractor, not of the comparator.
- `mag/tests/parity_faults.rs` shells the pinned poppler tools through
  `mag parity`, so `cargo test` now requires poppler 25.08.0 on PATH. A
  version mismatch fails loud at comparator startup.
