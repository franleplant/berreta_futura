# WP-5.3a verification

## Verdict

REJECTED, on one clause: a reachable branch of `image_contrast.py` is covered by no
fixture and no oracle row, while the evidence claims every branch edition 010 cannot
reach is covered. Everything else verified, including the claims that were hardest to
believe.

## Base

WP commit `5d9d154` (parent `11b1a9f`). Verified in a fresh worktree at `5d9d154`.

## Owns

`git show --stat 5d9d154` touches 20 paths, all within Owns: `mag/src/critic/metrics.rs`,
`mag/src/critic.rs` and the `mod critic;` line in `mag/src/main.rs` (registration, declared
in Residuals), `mag/tests/critic_metrics.rs`, two committed oracle JSONs, eleven fixture
PNGs, `mag/Cargo.toml` + `mag/Cargo.lock`, and the evidence file. No `*.verify.md`, no
`baseline.json`, no comparator territory, no `mag/src/model/**`.

`meta/verification/parity.yaml` is NOT touched, which confirms mechanically that
`critic_metric_tolerances` was consumed and not authored (rule 4).

## Baseline

In the worktree at `5d9d154`: `cargo fmt --check` exit 0, `cargo clippy --all-targets --
-D warnings` clean, `cargo test` all green (metrics suite 21.27 s).

## Verified

**PIL semantics, checked against Python directly rather than accepted.** Both claims that
motivate the `png` crate choice hold: `convert("RGB")` on a fully transparent red RGBA
pixel yields `(255, 0, 0)`, so alpha is dropped and never composited (compositing would
give `(255,255,255)` on white or `(0,0,0)` on black), and a palette image saved with
`transparency=0` converts index 0 to its palette colour `(255,255,255)` rather than
honouring `tRNS`. `rgba_alpha.png` and `palette_trns.png` cover exactly these.

**Round trip: clean, both halves.** Replaying the evidence's fixture-generation block
regenerates all eleven PNGs byte-identically (sha256 before and after identical), and
replaying both oracle blocks regenerates `critic_metrics_expected.json` and
`critic_metrics_rounding_expected.json` byte-identically, with `git status` empty
afterwards. The fixture list is globbed from disk, so it cannot silently shrink. This is
the defect class that rejected WP-5.1b once; it is closed here.

**LANCZOS pixel-for-pixel agreement, probed on shapes no fixture uses.** I added two probe
fixtures, regenerated the oracle over them and ran the port: `zz_probe_prime.png`
(1021x769, both prime, reduce factor 0, so pure LANCZOS at odd sizes) and
`zz_probe_bigreduce.png` (5003x3001, prime dimensions, asymmetric reduce factor 4x2 which
is larger than any committed fixture and exercises remainder columns, rows and corner).
Both pass: 13/13 fixtures plus 3/3 figures match PIL pixel for pixel. The claim survives
inputs the worker did not choose. Probes removed afterwards; tree restored clean.

**Discriminating probes reproduced.** Probe B (dropping `reduce()`'s rounding amend,
`acc = [(scale/2) as u64; 3]` to `[0u64; 3]`) fails both suites, and specifically fails
`extreme_aspect.png` AND `odd_reduce.png` - the two fixtures the worker caught passing
vacuously and regenerated. They are now genuinely discriminating rather than decorative.
Probe D (half-even to half-down in `round_half_even`) leaves all 14 images passing and
fails `rounding_matches_python_round`, exactly as the evidence records: the corpus has no
luminance on a `.5` boundary, which is why the direct rounding oracle exists. The worker's
honest recording of that gap is accurate.

**Concurrency** is exercised by two tests, `worker_count_matches_the_python_bounds` and
`ordered_map_preserves_order_and_reports_the_first_failure`, so `concurrency.py`'s absorbed
role is covered rather than assumed.

**Rounded versus unrounded, a subtle detail the port gets right.** `tint_ratio` is computed
from `before.paper_pixel_ratio` and `before.mark_pixel_ratio`, which are the values already
passed through `round_places(_, 6)`, matching Python's use of the rounded dataclass fields;
`needs_treatment` is computed from the unrounded `mark_ratio` and `contrast`, matching
Python line 129. Getting one of these backwards would shift behaviour at the boundary.

**Scope finding: CONFIRMED.** `image_contrast` is imported only by `render.py:14`,
`weasyprint_adapter.py:1790` and `preflight.py:9`; `render_critic.py` does not import it at
all, taking only `ordered_map` and `worker_count` from `concurrency` at `:22`. Its metrics
land in `preflight.json` (`preflight.py:128`). `render_critic.py` carries its own raster
helpers (`ImageOps.grayscale` and histograms at 968-977, `convert` + LANCZOS resize +
`ImageChops.difference` + histogram at 1084-1089, more at 1139, 1250, 1389-1410), which are
unported work belonging to WP-5.3b and are what the render-critic tolerances apply to.

## The defect

**The tint-ratio early return is implemented but reached by nothing.**
`image_contrast.py:149-150` returns unchanged when
`tint_ratio >= _MAX_ENHANCEABLE_TINT_RATIO` (0.05); the port implements it at
`metrics.rs:543`. No fixture and no oracle row reaches it. Computing
`1 - paper_pixel_ratio - mark_pixel_ratio` across all 14 rows, every image with
`needs_treatment: true` has tint at or below 0.0:

| image | paper | mark | tint | needs_treatment | path taken |
|---|---|---|---|---|---|
| gray8.png | 0.0000 | 1.0000 | 0.0000 | true | enters loop |
| gray_alpha.png | 0.0000 | 1.0000 | 0.0000 | true | enters loop |
| low_contrast.png | 0.9003 | 0.0997 | -0.0000 | true | enters loop |
| palette_trns.png | 0.9003 | 0.0997 | -0.0000 | true | enters loop |

Every other row returns at `:145` before reaching the tint test at all. The closest any
row comes to the 0.05 threshold is a relative margin of 4.06e-1, and those rows never
reach the test.

**The branch is easily reachable, and I demonstrated it.** A 400x300 white page with a 20%
mid-tone band and a 10% light-grey mark band produces `paper 0.70, mark 0.10, tint 0.20,
contrast 1.497, needs_treatment true`, taking the early return, at every band value from
228 through 240. That is an ordinary figure shape (a screenshot with a tinted panel and
grey text), not a contrivance.

**Why this is rejection-level rather than a note.** The evidence states "Branches edition
010 cannot reach, covered by fixture: all of them", which is false. Revision 12's Phase 5
preamble requires a port to state which branches its corpus cannot reach and cover those by
fixture, enumerating by reading the Python for branches rather than the corpus for cases.
This is the same rule family WP-5.1c was rejected under at `11b1a9f`, and the same vacuity
pattern that produced the defects in WP-5.1a, WP-5.1b (twice) and WP-5.1c: a uniformly
well-formed corpus hiding an untested path. The implementation looks correct by inspection,
but inspection is precisely what failed in those four cases.

**Remedy, small and inside Owns:** add a fixture of the shape above, regenerate the oracle
(purely additive), and prove it discriminates by perturbing the comparison at `:543` and
confirming the new row fails. Then correct the completeness claim in the evidence.

## Other findings, not blocking

**The near-threshold survey understates its own number.** The evidence reports a smallest
relative margin of 9.6e-2, but its survey script reads only `r['analysis']` and ignores
`r['after']`. Including both gives 4.85e-2, at `low_contrast.png`'s `after` block
(`minimum_mark_contrast_ratio` 2.097 against the 2.0 threshold). The conclusion is
unaffected: 4.85e-2 is still more than three orders of magnitude outside the 1e-5
near-threshold window, so no metric owned by this WP requires a near-threshold fixture. The
reported figure should be corrected to what the survey actually supports.

**`_open_rgb`'s BinaryIO branch** (`image_contrast.py:70-71`) is exercised by no oracle.
The Python flow reaches the `Image.Image` branch at `:69` (via `_prepared_bytes` passing an
opened image to `analyze_print_contrast`, and again for each enhancement candidate), which
the port covers structurally, but a `BytesIO` source is never tested. No current caller
passes one; worth a recorded line rather than a fixture.

## Status

rejected
