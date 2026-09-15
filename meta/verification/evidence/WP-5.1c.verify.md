# WP-5.1c verification (fourth pass)

## Verdict

**ACCEPTED.** Commit `b12a2a3` closes the copy-agreement clause that stood
open across three rejections.

## Rejection history

| submission | verdict | cause |
|---|---|---|
| `4120821` | rejected at `66f6f90` | `manifest.rs`'s private `py_repr` copy carried the pre-fix body; 5 of 7 probes diverged |
| `9278501` | rejected at `11b1a9f` | revision 12 requires a forced helper copy to carry a test asserting the two copies agree; no such test existed |
| `17eb66b` | rejected at `507d10c` | the test discriminated over the branches it reached, but five branches were unreached and two were proved to admit an undetected divergence |
| `b12a2a3` | **accepted** | two cases added; all four perturbations now caught |

## Scope

Narrow, per the outstanding clause plus non-regression. Facts established by
the earlier passes were not redone: the `py_repr`/`printable`/`nonprintable`/
`escape` bodies are byte-identical to `records.rs`; the 010 oracle chain holds
(Rust port = Python loader = shipped `edition-manifest.json`); the stale-copy
audit was confirmed structurally; the test genuinely reads both copies.

`mag/src/model/manifest.rs` is byte-identical between `9278501` and `b12a2a3`
(`git diff` empty over `manifest.rs`, `records.rs`, `doc.rs`, `model.rs`), so
the 010 oracle chain was correctly not re-run. The Cargo delta in that range
belongs to WP-2.0a's typst pins, not to this commit.

## Owns

`git show --stat b12a2a3` lists exactly four paths: `mag/tests/model_manifest.rs`,
`mag/tests/model_manifest_fixtures/cases.yaml`,
`mag/tests/model_manifest_cases_expected.json`,
`meta/verification/evidence/WP-5.1c.md`. No source module, no Cargo file, no
verify file, no `baseline.json`.

## The two added cases

`REPR_CASES` gains `"back\\slash\nnew\rret\ttab"` (backslash, LF, CR, tab) and
`"it's plain"` (apostrophe, no double quote).

## Perturbation reproductions

Each perturbs only the `manifest.rs` copy; all four reproduced, each naming its
distinguishing case.

| perturbation | previous pass | this pass |
|---|---|---|
| revert the escaping arms | FAIL `zero\u{200b}width` | FAIL `zero\u{200b}width` |
| drop the astral branch of `escape` | FAIL `astral\u{f0000}stop` | FAIL `astral\u{f0000}stop` |
| diverge the `'\\'` arm | **PASS, undetected** | FAIL `back\\slash\nnew\rret\ttab` |
| force quote selection to `'` | **PASS, undetected** | FAIL `it's plain` |

The two previously undetected divergences are now caught, which is the defect
the third rejection named.

One observation strengthening the clause: the backslash perturbation is caught
**only** by `py_repr_copies_agree`; `cases_match_the_python_loader` still passes
under it. So the copy-agreement test does work the corpus test cannot, rather
than duplicating it. The quote-selection perturbation is caught by both.

## The corpus addition

`apostrophe_only_edition_id` was the right call, and the worker's reasoning
holds: `py_repr_copies_agree` asserts the copies **agree**, not that either
matches Python, so both could be wrong identically and still pass. Only
`cases_match_the_python_loader` checks correctness, and it was missing that
branch.

Verified by replaying the clause-5 regeneration command verbatim: it drives the
real Python loader over every case and reproduces
`model_manifest_cases_expected.json` **byte-identically** (`git diff --stat`
empty, `cmp` identical). The committed expectation for that case is therefore
Python's own output:

    Edition id "010'" does not match directory '010'

which confirms the `"` selection independently of the Rust side.

## The unreachable-by-construction branch

Sound, and I checked the implication rather than the wording.

`py_repr` selects `quote = '"'` only when `text.contains('\'') && !text.contains('"')`.
The `other if other == quote` arm fires only when the text contains the quote
character. With `quote == '"'` that requires `text.contains('"')`, which
contradicts the selection condition. The branch is therefore unreachable, not
merely uncovered.

The companion is reachable and covered: with `quote == '\''` the arm fires on
`"it's \"both\""`, where both quote kinds are present so `'` is selected and
escaped. This matches Python, which prefers `'`, switches to `"` only for a
string containing `'` and not `"`, and escapes `'` when both are present.

## Branch enumeration

Confirmed against the source. `py_repr` carries two quote outcomes and seven
character arms (`'\\'`, `'\n'`, `'\r'`, `'\t'`, `other == quote`, `printable`,
`escape`); `escape` carries three width branches (`< 0x100`, `< 0x10000`, else).
The evidence's table names a reaching case for each, with the single
unreachable-by-construction entry argued rather than asserted. The blanket
coverage claim that caused earlier rejections is gone.

## Baseline

In a clean worktree at `b12a2a3`: `cargo fmt --check` clean;
`cargo clippy --all-targets -- -D warnings` clean; full `cargo test` green
(69 + 5 + 8 + 5 + 3 + 1 + 1 + 1 passing across targets), `model_manifest` at 5
tests. Worktree `git status` empty after all perturbations were restored.

## Residuals

- The duplicated `py_repr` remains a forced copy. WP-5.1d's consolidation is
  still the structural fix, and its duplicate-helper audit should be written
  structurally over normalised bodies rather than by function name, per the
  third pass's finding.
