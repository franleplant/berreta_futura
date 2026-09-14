# WP-0.2d verification

## Verdict

**ACCEPTED** for the fault suite and `critic_metric_tolerances`, after rework.

Scope of this verdict, stated explicitly: it covers the fault suite and the
critic tolerances only. **WP-0.2d remains `blocked` on `raster_bound`**, which
no verification can clear: the plan's derivation measures 241/255 and
redefining the Tier E raster guard is a plan revision, not a WP's to make
(rule 4). A planning agent is drafting plan revision 9 for that gate.

## History

First submission `0bd7cc0` was **rejected** by verify commit `83d7bee`. The
defect: `failing_clauses` in `mag/tests/parity_faults.rs` tested the Tier V
meters with `v["v1"] == false` / `v["v2"] == false`, but the comparator emits
those fields as JSON strings (`"pass"` / `"fail"`), so both branches were dead
code. The suite could never report v1 or v2, which made the committed matrix
wrong for two faults and made the "asserted exactly" claim rest on an observer
blind to a whole clause family (rule 6).

Rework: commit `67afdcd`, parent `7283125`.

## Base

- Verified state: `67afdcd`
- Rework parent: `7283125`
- Worktree: `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/verify-wp02d2` (removed after)

## Owns check

`git show --stat 67afdcd` lists exactly three files:

- `mag/tests/parity_faults.rs`
- `meta/verification/parity.yaml`
- `meta/verification/evidence/WP-0.2d.md`

No `*.verify.md`, no `baseline.json`, no Cargo files (`mag/Cargo.toml` and
`mag/Cargo.lock` untouched, as claimed). The `parity.yaml` diff is four lines:
the `must_flag` lists of `figure_shifted_page` and `recolor_30px`. Nothing
else in that file moved. Note the range `83d7bee..67afdcd` is misleading
because other agents' commits landed between them; the per-commit diff is the
correct check and is what is recorded here.

`git diff 0bd7cc0..67afdcd -- meta/verification/parity.yaml` touches
`raster_bound` and `critic_metric_tolerances` on zero lines.

## Commands

```
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/verify-wp02d2 67afdcd
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Perturbation proofs, each applied to the worktree then restored from backup
(`cargo test --test parity_faults` after each edit):

- **A**, extra clause: `swapped_words.must_flag` gains `bogus_clause`.
- **B**, missing clause: `swapped_words.must_flag` loses `text`.
- **C**, unobservable declaration: `clause_vocabulary` gains `bogus_never_observed`.
- **D**, the rejected defect reconstructed: in `clause_states`, the meter read
  `tier_v[meter].as_str()` is replaced with `tier_v[meter].as_bool().map(|_| "fail")`,
  which is the original string-vs-bool blindness.

## Tool versions

poppler 25.08.0 (asserted by the comparator at startup), rustc 1.96.0.
The suite needs no renderer, no Python, and no run directory: it builds both
legs itself with lopdf.

## Metrics

Baseline in the worktree: `cargo fmt --check` exit 0, `cargo clippy
--all-targets -- -D warnings` exit 0, `cargo test` exit 0 with the fault suite
at 19.32 s (the evidence records 19.0 s; the 44.17 s in the rejecting verify
file was a loaded machine).

Matrix measured independently by me, read from perturbation A's own assertion
output (the `left` side is what the suite observed, not what the yaml
declares):

| fault | observed failing clauses |
|---|---|
| swapped_words | color, display_list, text |
| line_moved_005 | display_list |
| line_moved_03 | display_list |
| figure_shifted_page | display_list, v1, v2 |
| recolor_30px | display_list, v1, v2 |
| body_ink_pure_black | color, display_list |
| dropped_link_annotation | display_list, navigation |
| mediabox_off_05 | boxes, display_list, raster_dimensions |

This agrees with `parity.yaml fault_suite.expected_detections` row for row,
and with the corrections the rejecting verifier derived independently. Only
the two disputed rows changed from the first submission.

Perturbation results, all as required:

| proof | expected | observed |
|---|---|---|
| A extra clause | fail | exit 101, `expected-detections matrix` at line 355 |
| B missing clause | fail | exit 101, `expected-detections matrix` at line 355 |
| C undeclared-but-unobservable name | fail | exit 101, `declared clauses unobservable` at line 200 |
| D rejected defect reconstructed | fail | exit 101, `declared clauses unobservable: ["v1", "v2"]` |
| restored | pass | exit 0, worktree `git status` clean |

D is the important one: the exact defect that caused the rejection now fails
the suite loudly instead of passing silently.

## Verdicts

Control verdict `output/parity/fault-control/verdict.json` carries
`tier_e.raster` as `{"status": "not_evaluated", "owner": "WP-0.2d raster_bound
derivation"}`, so the blocked guard is still reported rather than defaulted.
`tiers.e.raster_bound` in `parity.yaml` carries `status: blocked` and
`measured_max_channel_delta: 241` with **no `value` key**.

## Residuals

- The recurrence guard is two-directional and this is worth keeping in view:
  `code_blocks` and `critic` are observable but `not_evaluated`, so they are
  legitimately absent from `clause_vocabulary` today. When WP-3.3 evaluates
  code blocks and WP-5.3g joins the critic verdict, the guard's second check
  fails until the vocabulary is extended. That is the designed behavior, not a
  defect, but those WPs should expect it.
- Fragility confirmed and not tuned away: `line_moved_03` differs on 0.000879
  of its worst page against the V2 threshold of 0.001, inside it by 12 percent.
  The fixture is untouched. If a future change flips that row, the exact matrix
  assertion fails loudly, which is the correct outcome.
- `swapped_words`, `line_moved_005` and `line_moved_03` each show a max channel
  delta of 241 on synthetic fixtures, independently reproducing the
  grid-fitting effect behind the blocked `raster_bound`.
- Verified at `67afdcd`; `mag/tests/model_doc.rs` (WP-5.1a) also ran green in
  the same worktree without its environment variables set, so its edition-010
  oracle is skipped rather than failed in that mode. Out of my scope, noted for
  WP-5.1a's verifier.

## Status

`accepted` for the fault suite and critic tolerances; the WP itself stays
`blocked` on `raster_bound` pending plan revision 9.
