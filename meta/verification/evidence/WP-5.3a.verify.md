# WP-5.3a verification

Verdict: **ACCEPTED**.

Verifies commit `0a68eb4` (rework). Supersedes the rejection at `a3d61c9`.

## Record of the rejection

The first submission (`5d9d154`) was rejected because the tint-ratio early
return (`image_contrast.py:149-150`, port `metrics.rs:543`) was reached by no
fixture and no oracle row, while the evidence claimed every branch edition 010
cannot reach was covered by fixture. The rework adds `tint_band.png`, replaces
the blanket claim with a traced branch table, and corrects the near-threshold
figure. No production code changed.

## Owns

`git show --stat 0a68eb4` touches exactly three paths:

    mag/tests/critic_metrics_expected.json
    mag/tests/critic_metrics_fixtures/tint_band.png
    meta/verification/evidence/WP-5.3a.md

No verify file, no `baseline.json`, no Cargo files, no comparator territory.

`git diff 5d9d154 0a68eb4 -- mag/src/critic/metrics.rs` is empty (0 lines), so
`metrics.rs` is byte-identical to the accepted state. The defect was missing
coverage, not wrong behaviour, and the rework correctly changed no code.

## Baseline

In a clean worktree at `0a68eb4`:

    cargo test --test critic_metrics    5 passed, 0 failed
    cargo fmt --check                   clean
    cargo clippy --all-targets -D warnings   clean

## Replayed claims

**The fixture.** `tint_band.png` is reached, and it is the sole cover for the
branch. The evidence's trace command reproduces verbatim:

    71  UNREACHED
    102 UNREACHED
    111 UNREACHED
    150 ['tint_band.png']
    158 UNREACHED

**Discriminating proof, both directions, reproduced independently.**

| perturbation of `metrics.rs` | observed |
|---|---|
| delete the `:149` guard | `fixtures_match_the_python_metrics` FAILED on `tint_band.png` alone: "adjusted true expected false", "post-treatment analysis differs". Figures test still ok; no other fixture named. |
| invert the guard to `<` | FAILED on `tint_band.png` (wrongly enhanced) **and** `low_contrast.png` and `palette_trns.png` (both "adjusted false expected true", "unresolved differs") |

Deleting pins the branch from one side and inverting pins it from the other, so
the guard's threshold is constrained in both directions rather than merely
present. Restored from a pristine copy afterwards: `git status` clean, 5/5 green.

**Fixture regeneration.** Re-running the evidence's generation command rewrote
all twelve fixtures with zero drift (`git status` clean afterwards), so the new
fixture is deterministic on the same footing as the eleven pre-existing ones.

**Near-threshold corrected figure confirmed.** The corrected survey reports

    smallest relative margin: 4.8500e-02 at
    ('mag/tests/critic_metrics_fixtures/low_contrast.png', 'after',
     'minimum_mark_contrast_ratio', 2.097)

matching the evidence. The earlier 9.6e-2 came from a script reading only each
row's `analysis` block and skipping `after`; the corrected script scans both and
names the row, so the number is auditable. The conclusion is unchanged: 4.85e-2
is more than three orders of magnitude outside the 1e-5 near-threshold window,
so no metric owned by this WP requires a near-threshold fixture.

## Judgment on the four unreached lines

An uncovered branch is acceptable only as an unreachability claim or a stated
mechanism, so each was examined rather than accepted.

**`:71` `_open_rgb` seeks a `BinaryIO` — disposition correct.** Every production
call site passes a `Path`:

    src/magazine/render.py:701,981      prepare_print_image(path)
    src/magazine/weasyprint_adapter.py:1804  prepare_print_image(path)
    src/magazine/preflight.py:110       prepare_print_image(path)

and `prepare_print_image` reaches `_open_rgb` via `_prepared_bytes(str(path.resolve()))`,
always with a `Path`. The `BinaryIO` arm is an unused affordance of the Python
type signature, not behaviour any caller depends on. A Rust counterpart would be
speculative generality, so `decode_rgb(&Path)` is the right surface. Recording it
as a line rather than adding a fixture is correct.

**`:102` background-estimator fall-through — the unreachability proof HOLDS.**
Checked line by line against the source:

- the guard at `:92` returns unless `dominant / total >= 0.18`, so on reaching
  `:94` we have `dominant >= 0.18 * total`;
- `required = max(0.18 * total, dominant / 2)`, and both terms are `<= dominant`
  (the first by the guard, the second since `dominant >= 0`), so `required <= dominant`;
- `dominant = max(neighborhood(b) for b in range(floor_bin, 101))`, so some
  `b*` in `[floor_bin, 100]` attains it;
- the loop iterates `range(100, floor_bin - 1, -1)`, which covers exactly
  `[floor_bin, 100]` and therefore includes `b*`;
- at `b*`, `neighborhood(b*) = dominant >= required`, so the loop returns at
  `:101` at or before `b*`.

`total >= 1` is guaranteed because `analyze_print_contrast` returns at `:111`
when `not total`, and `dominant = 0` would have returned at `:93`. So `:102` is
genuinely dead code in the Python, faithfully reproduced. Worth having in the
record: it is an upstream redundancy, not a porting gap.

**`:111` empty-image stub — accepted.** `total = len(pixels)` after a thumbnail
of a decoded PNG; the PNG format forbids zero dimensions, so no decodable input
reaches it.

**`:158` `continue` when a candidate loses its marks — accepted as stated, and I
could not construct it.** The worker recorded it as reachable in principle with
the mechanism named, so I attempted the construction rather than take the
argument. A structured search over 315 two- and three-band images (bulk value
110-193, dark fraction 0.02-25%, paper fraction 0-80%), of which **84 passed both
`needs_treatment` and the `tint_ratio < 0.05` guard and entered the enhancement
loop, produced zero hits** on any of the five contrast factors.

The analytic reason matches the worker's and is tighter than "constructions
collapsed". All factors are `> 1`, so `ImageEnhance.Contrast` moves pixels away
from the image mean, and a mark can only lose mark status by moving lighter,
which requires it to sit above the mean. That forces the bulk of the image below
the mark threshold (luminance `0.757` at background `1.0`), and then:

- if that bulk sits above the background floor (`_MIN_BACKGROUND_LUMINANCE` 0.60)
  and carries at least 18% of the mass, `_estimate_background_luminance` makes it
  the background, so it is reclassified as paper and `needs_treatment` is false
  before the loop is reached;
- if it sits below 0.60, lifting it past `0.757` needs `d * (f - 1) > 0.377` for a
  dark fraction `d`, i.e. `d > 0.14` even at the largest factor, and that dark mass
  is itself marks that survive enhancement, so `mark_pixel_ratio` stays far above
  `0.001`.

The two escapes close against each other, which is why the search finds nothing.
Leaving it uncovered with the mechanism stated is the right disposition; proving
full unreachability would cost more than the branch is worth, and the evidence
does not overclaim it.

## Status

ACCEPTED. All previously established findings stand (PIL `convert("RGB")`
semantics justifying `png` over `image`; LANCZOS pixel-identity surviving the
1021x769 and 5003x3001 prime-dimension probes; the clean round trip and globbed
fixture list; the confirmed scope finding that `image_contrast` is consumed by
`preflight.py`, `render.py` and `weasyprint_adapter.py` rather than by
`render_critic.py`).
