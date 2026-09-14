# WP-0.2d verification

## Verdict

**REJECTED**, on one material defect in the fault suite.

The rejection concerns the fault suite only. The `critic_metric_tolerances`
deliverable is correct and is accepted as written, and the `raster_bound`
blocked status is correctly handled, honestly measured and independently
reproducible; neither contributes to the rejection.

## Base

- Worker commit: `0bd7cc0`, diff base `378449f`.
- Verified in a fresh worktree at `0bd7cc0`.
- Verifier: replay plus folded-in critique duty, per the orchestrator brief.

## Owns check

PASS. `git diff --name-only 378449f..0bd7cc0` lists exactly:

```
mag/Cargo.toml
mag/tests/parity_faults.rs
meta/verification/evidence/WP-0.2d.md
meta/verification/parity.yaml
```

No `*.verify.md`, no `baseline.json`. `mag/Cargo.toml` gains a
`[dev-dependencies]` block only (lopdf, serde_json, serde_yaml); `Cargo.lock`
is unchanged because all three were already resolved. The `parity.yaml` diff
was read hunk by hunk and is confined to `tiers.e.raster_bound` (annotation
keys), a new top level `fault_suite:` carrying the expected detections
matrix, and a new top level `critic_metric_tolerances:`. Nothing else in the
file moved.

## Replay

From the worktree, with the two determinism proven 010 render trees copied
in:

| command | result |
|---|---|
| `cargo test` | green, 72 tests plus the fault suite |
| `cargo test --test parity_faults` | green, 44.17 s |
| `cargo fmt --check` | clean |
| `cargo clippy --all-targets -- -D warnings` | clean |
| `pdfinfo -v` | 25.08.0, matching `parity.yaml tools:` |

The fault suite wall clock is 44.17 s here against the evidence's 20.6 s.
This machine was running several agents concurrently; it is a timing metric,
not a correctness claim, and is recorded rather than held against the WP.

Structural claims confirmed by reading `mag/tests/parity_faults.rs`:

- the matrix is asserted exactly, by `assert_eq!(observed, want)` over the
  full per fault clause set, so a detection set that gains or loses a clause
  fails the test rather than passing quietly
- the clean pair flags nothing and exits 0 (asserted)
- every fault exits 1 (asserted)
- no fault passes Tier E: `assert_ne!` on the display list status is
  individually weak (it would also pass on `not_evaluated`), but the exact
  matrix assertion requires `display_list` in `must_flag` for all eight
  faults, and `failing_clauses` only records `display_list` when its status
  is `fail`, so the requirement is genuinely enforced

## Critique: the defect

`failing_clauses` in `mag/tests/parity_faults.rs` observes the Tier V meters
with:

```rust
if v["v1"] == false { failing.insert("v1".into()); }
if v["v2"] == false { failing.insert("v2".into()); }
```

The comparator writes those fields as JSON **strings**, not booleans. Dumped
from the suite's own verdicts:

```
verdict                        v1       v2       dims  type
fault-control                  'pass'   'pass'   0     str
fault-figure_shifted_page      'fail'   'fail'   0     str
fault-recolor_30px             'fail'   'fail'   0     str
fault-mediabox_off_05          'pass'   'pass'   1     str
```

`serde_json::Value::String("fail") == false` is never true, so both branches
are dead and the helper can never report `v1` or `v2`. Two consequences, both
material:

1. The committed matrix is factually wrong for two faults. `recolor_30px`
   genuinely differs on 2.03 percent of page 3 at max channel delta 255, and
   `figure_shifted_page` on 4.34 percent of pages 3 and 4 at max channel
   delta 255; both fail V1 and V2 in the verdict, yet `must_flag` lists only
   `display_list`. A reader of `parity.yaml` would conclude these faults move
   no pixels.
2. The suite's assertion is weaker than the plan requires. The matrix is
   asserted "exactly" against an observer structurally blind to a whole
   clause family, so no future regression in the V meters can be caught here.
   Protocol rule 6 forbids weakening a check, and an unintentionally dead
   comparison is still a weakened check.

The intended check of every fault does fire, and no fault passes Tier E, so
the plan's "flagged by at least its intended check" clause holds. The failure
is in "which the test asserts exactly".

### Required to clear the rejection

1. Compare `v1` and `v2` against the encoding the comparator actually emits
   (or have the comparator emit booleans, which is comparator territory and
   therefore a different WP; the test side fix is the one in scope).
2. Re-derive the matrix from observation and commit the corrected rows.
   Measured here, the corrected entries are `figure_shifted_page:
   [display_list, v1, v2]` and `recolor_30px: [display_list, v1, v2]`; the
   other six are unchanged.
3. Re-run `cargo test --test parity_faults` green.

### Critique: accepted without change

- Each fault varies exactly one field of `Spec` and exercises its intended
  clause honestly. `swapped_words` swaps two equal length words in a font
  with uniform 500 unit widths, so total advance is unchanged and the fault
  is caught on string content rather than on position drift; that is a good
  design, not an accident.
- `body_ink_pure_black` reproduces the plan's own prediction: the ink delta
  is below the 24/255 pixel threshold, so only the color clause sees it.
- `dropped_link_annotation` and `mediabox_off_05` legitimately trip
  `display_list` as well, because the canonical display list carries
  annotations and page boxes by the Tier E definition.
- No detection looked incidental in a way that would silently stop working;
  the exact matrix assertion is itself the guard against that.
- One fragility worth recording: `line_moved_03` sits at differing fraction
  0.000879 against the V2 threshold of 0.001. It is inside the threshold by
  12 percent, so a small fixture change could flip V2 and, once the helper is
  fixed, change the matrix. This is loud rather than silent, but the next
  author should know.
- `critic_metric_tolerances` is exactly "integers exact, floats 1e-6
  relative, near threshold window 1e-5" with no invented slack. The recorded
  constants were checked against `src/magazine/render_critic.py`:
  `SPARSE_INK_RATIO` 0.004 (line 34), `VOID_MIN_HEIGHT_POINTS` 96.0 (44),
  `TAIL_GAP_MIN_LIVE_FRACTION` 0.35 (54),
  `OPENER_CROP_FIDELITY_MAX_RGB_MAE` 8.0 (76). All match.
- The near threshold finding is real and correctly recorded: in 010's
  `render-critic.json`, `pages[39].largest_void.height_points` is exactly
  96.0 against a 96.0 threshold on a `>=` comparison, relative margin 0.0.
  WP-5.3b carries the fixture.

## Blocked item audit: raster_bound

Audited for honesty, not for success. All three checks pass.

1. `tiers.e.raster_bound` carries no `value` key. It records `status:
   blocked`, the measurement, the control, the decomposition, the cause, the
   rasterizer variants and the reason for withholding a value.
2. The comparator still reports the guard loudly. Run against the two real
   010 render trees:
   `tier E raster: not_evaluated (WP-0.2d raster_bound derivation)`, with
   every other clause passing and exit 0. No default bound exists anywhere in
   the code path.
3. The control leg reproduces exactly. Re-running the WP's own `perturb.py`
   at amplitude 0 over 010's `reader.pdf` touched 24452 coordinate operands,
   matching the recorded count, and the rewritten file is display list equal
   to the original with max channel delta 0 and worst page fraction 0.000000.
   The pypdf rewrite therefore contributes nothing, and the 241 comes from
   the sub quantum perturbation itself.

Independent corroboration of the 241, from a different fixture route: the
synthetic `line_moved_03` fault moves one text line by 0.3 pt and produces
max channel delta **241** on page 4. Two unrelated fixtures, the same number,
the same mechanism (a small shift flipping a grid fitted stem between paper
and body ink). The finding is sound.

### Not re-run

The full perturbed leg (24452 operands at half quantum amplitude, rasterized
at 300 dpi over the interior domain) was not re-run; it is expensive and the
brief permits skipping it. The control leg, the decomposition claim and the
241 magnitude were each verified by the cheaper routes above, so the
measurement is corroborated rather than merely restated.

The raster_bound gap requires a plan revision and is outside any WP's
authority to resolve. That remains open for Fran, independent of this
rejection.

## Status

`rejected` for the fault suite, on the dead V meter comparison and the two
incorrect matrix rows. `critic_metric_tolerances` accepted. `raster_bound`
blocked status upheld as correctly and honestly handled.
