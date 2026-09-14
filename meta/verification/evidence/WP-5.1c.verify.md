# WP-5.1c verification (manifest port)

## Base

Verified commit: `17eb66b` (second rework, parent `b8bd499`, plan revision 14).
Verification worktree at `17eb66b`, detached.

## Verdict

**REJECTED**, narrowly, on the same clause as the previous verification.

The test that was missing now exists, is well built, and discriminates at branch
granularity on the branches its case list reaches. It is rejected because the
case list leaves five of `py_repr`'s branches unreached, two of which I proved
empirically admit an undetected divergence between the two copies, and because
the evidence states a coverage claim that is false.

Everything else about this WP is sound and is recorded below as not needing
rework.

## Rejection history

- `4120821` rejected at `66f6f90`: `manifest.rs`'s private `py_repr` copy
  carried the pre-fix body, 5 of 7 probes diverging. Material because 25 call
  sites carry user-authored text and `py_repr_value` reprs any string drawn
  from `edition.yaml`.
- `9278501` rejected at `11b1a9f`: revision 12's Phase 5 preamble requires a
  forced helper copy to carry a test asserting the two copies agree on a shared
  case list. No such test existed. Everything else verified.
- `17eb66b` (this verification): the test exists; its case list has a
  demonstrated hole.

## Owns

`git show --stat 17eb66b` touches exactly two paths:

- `mag/tests/model_manifest.rs`
- `meta/verification/evidence/WP-5.1c.md`

No `records.rs`, no `doc.rs`, no `mag/src/model.rs`, no Cargo files, no
`*.verify.md`, no `baseline.json`. Clean.

`git diff 9278501 17eb66b -- mag/src/model/manifest.rs` is empty, so
`manifest.rs` is byte-identical to the state the previous verification checked.
Skipping the 010 oracle chain was therefore correct rather than a shortcut: the
change is test-only and cannot affect that comparison.

## Commands

Baseline in the worktree:

    cargo test                                   # 93 passed, 0 failed
    cargo fmt --check                            # clean
    cargo clippy --all-targets -- -D warnings    # clean

`model_manifest` is 5 tests as claimed. The evidence's total of 88 predates
WP-5.3a landing 5 further `critic_metrics` tests; 93 is the current figure and
the discrepancy is sibling commits, not a defect.

Perturbations and probes were applied to `mag/src/model/manifest.rs` in the
worktree from a pristine copy, one at a time, restoring between each.

## Metrics

### Reproduced: both discriminating perturbations

| perturbation | result | case named |
|---|---|---|
| escaping arms reverted to the pre-fix body | FAILED | `"zero\u{200b}width"` |
| astral branch of `escape` dropped to 4-hex | FAILED | `"astral\u{f0000}stop"` |
| restored to pristine | passes | n/a |

Each perturbation names exactly the case that distinguishes it, so the test
does discriminate at branch granularity over the branches it reaches.

### Both copies are genuinely read

Perturbations A and B changed only the `manifest.rs` copy and the test failed.
Had `records_py_repr` routed through the same implementation, both sides would
have moved together and the test would have passed. It did not, so the two
sides are independent. Confirmed in source: `records.rs:1140` calls its own
`py_repr(language)` before any filesystem access, and `manifest.rs`'s
`load_translation` reprs its argument likewise, so both entry points are pure
and reach production code paths without altering visibility in `records.rs`.

A copy-agreement test asserts agreement, not correctness: two copies that
diverge identically from Python would still pass. Correctness is asserted
separately by `cases_match_the_python_loader` against the real Python loader,
so the pair is sound in combination. Recorded because the distinction matters
for WP-5.1d.

### The defect: five unreached branches, two proved to admit divergence

`py_repr` has seven arms plus a two-way quote selection. The seven cases reach:
the printable arm (`plain`, `caf\u{e9}`), the quote-escape arm (`it's "both"`),
and all three widths of `escape` (`\x07`/`\x1b`, `​`, `\U000f0000`).

They do not reach:

| unreached | why |
|---|---|
| `'\\' => "\\\\"` | no case contains a backslash |
| `'\n' => "\\n"` | no case contains a newline |
| `'\r' => "\\r"` | no case contains a carriage return |
| `'\t' => "\\t"` | no case contains a tab |
| quote selection's true branch (`'"'` chosen) | the only quote case contains **both** quote kinds, so `contains('\'') && !contains('"')` is false and it takes the else |

Two probes, each diverging the `manifest.rs` copy only and running the whole
`model_manifest` suite:

| probe | divergence introduced | suite result |
|---|---|---|
| C | `'\\' => out.push('\\')` (backslash no longer doubled) | **5 passed, 0 failed** |
| D | `let quote = if false` (never selects `'"'`) | **5 passed, 0 failed** |

Both are exactly the failure the clause exists to prevent: a divergence between
the two copies that `cargo test` reports green. Probe D also shows that no
fixture among the 79 cases carries an apostrophe-without-double-quote string,
so `cases_match_the_python_loader` does not cover that branch either.

This is not a hypothetical class. A string with an apostrophe and no double
quote is ordinary in hand-authored `edition.yaml` content (a possessive in a
title or an anchor), which makes the quote-selection branch the more likely of
the two to be hit in production.

### The evidence's coverage claim is false

The evidence states the cases "cover every branch of both the escape width and
the quote selection". Escape width: true, all three widths are reached. Quote
selection: false, one of two branches is reached. Accepting would enter a false
coverage claim into the verified record.

## Verdicts

No verdict.json is produced by this WP.

## Residuals

Remedy, small and entirely inside this WP's Owns: add two cases to
`REPR_CASES`, and no code change is required.

1. A string containing a backslash, a newline, a carriage return and a tab,
   covering all four literal-escape arms at once.
2. A string containing an apostrophe and **no** double quote, covering the
   quote-selection branch that selects `'"'`.

Re-run the two existing perturbations plus probes C and D; C and D must then
fail where they currently pass.

Not to be redone on rework, all confirmed by this or the previous verification:
the `py_repr`/`printable`/`nonprintable`/`escape` bodies are byte-identical to
`records.rs` at `57d6929`; the regeneration block reproduces all 79 committed
expectations byte-identically; `git diff --numstat 4120821 9278501` is `29 0`,
purely additive; Python's three escape widths are confirmed; the stale-copy
audit's conclusion holds (no second stale copy), redone structurally; both
declared divergences are soundly reasoned; the 010 oracle chain holds
(Rust port = Python loader = shipped `edition-manifest.json`).

For WP-5.1d: this verification is the third demonstration in this execution
that a guard proves only what its cases contain. Its duplicate-helper audit
clause should be written structurally over normalised function bodies rather
than by name, and consolidation would remove the need for a copy-agreement
test on this helper entirely.

## Status

rejected
