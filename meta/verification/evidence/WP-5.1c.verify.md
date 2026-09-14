# WP-5.1c manifest port, re-verification

## Verdict

**REJECTED**, on one clause only: the Phase 5 preamble's helper-duplication
rule, binding since revision 12 (`caa75e6`) and therefore in force when the
rework was made, requires a test asserting the two copies agree. There is
none. Everything else this re-verification examined is green, including the
fix that caused the rejection, and the remedy is one test inside paths the WP
already owns.

## History

Commit `4120821` was rejected at verify `66f6f90`: `manifest.rs`'s private
`py_repr` carried the pre-fix body, lacking the `printable` predicate and the
`escape` helper, so every non-printable character was emitted raw and five of
seven probes diverged from Python. The corrected body already existed in
`records.rs` when the copy was made, so it was stale rather than
independently written, and it landed in the module that validates
`edition.yaml`, where hand-authored anchors and extract markers arrive. No
test caught it because the 74-case corpus carried no non-printable character.

The rework is commit `9278501`.

## Owns

`9278501` touches exactly four paths: `mag/src/model/manifest.rs`,
`mag/tests/model_manifest_fixtures/cases.yaml`,
`mag/tests/model_manifest_cases_expected.json`,
`meta/verification/evidence/WP-5.1c.md`. Not `records.rs`, not `doc.rs`, not
`mag/src/model.rs`, not the Cargo files, no `*.verify.md`, no `baseline.json`.
Clean.

## What verified green

**Body identity, checked rather than accepted.** "Identical private copy" was
the false claim that caused the rejection, so it was re-derived mechanically:
the `py_repr`, `printable`, `nonprintable` and `escape` bodies were extracted
from both modules and diffed. 42 lines each, **byte-identical**. Compared
against `records.rs` at commit `57d6929` (WP-5.1b's second rework, itself
under its own third verification at the time of writing).

    for f in records manifest; do
      awk '/^fn (py_repr|printable|nonprintable|escape)\(/,/^}/' mag/src/model/$f.rs > /tmp/pr_$f.txt
    done
    diff /tmp/pr_records.txt /tmp/pr_manifest.txt   # no output

**The five fixtures carry Python's own output.** The documented regeneration
block (evidence clause 5, lines 138-183) was extracted and replayed verbatim.
It drives the real `magazine.manifest` loader over every case in
`cases.yaml`. The regenerated file is **byte-identical** to the committed
`model_manifest_cases_expected.json` (`git diff --numstat` empty). So the five
expected messages are Python's, not the port's, and the regeneration is
reproducible from the evidence alone.

Python's three escape widths confirmed independently:

| codepoint | class | Python `repr` |
|---|---|---|
| U+200B | Cf | `\u200b` |
| U+0007 | Cc | `\x07` |
| U+001B | Cc | `\x1b` |
| U+F0000 | Co | `\U000f0000` |

matching the committed expectations, with the astral case the only one
reaching the eight-hex branch.

**Regeneration is purely additive.** `git diff --numstat 4120821 9278501`
on the expectations file reports `29 0`: five new entries, no pre-existing
case altered.

**The discriminating proof reproduced, both directions.** Reverting the two
escaping arms in place (helpers kept under `#[allow(dead_code)]` so
`-D warnings` could not mask the result) fails `cases_match_the_python_loader`
with exactly

    5 cases diverge:
    nonprintable_edition_id
    nonprintable_section_kind
    nonprintable_verbatim_title
    nonprintable_astral_verbatim_title
    nonprintable_translation_language

naming those five and no others; the other 74 pass in **both** states, which
confirms the rejection's diagnosis rather than merely accepting it. Restoring
returns `4 passed`.

**Baseline.** `cargo test --test model_manifest`: 4 passed, both before and
after the revert experiment, with the worktree left clean.

## The stale-copy audit: right conclusion, insufficient method

The evidence's clause 3b compares function **names** (`comm -12` over
`^(pub )?fn \K\w+`). That cannot see a behaviour duplicated under two
different names, which is the failure mode one step removed from the one that
caused this rejection. The audit was therefore redone structurally: every
function body in both modules was extracted, normalised (signature name
elided, whitespace collapsed) and compared pairwise by similarity ratio.

| pair | ratio | judgment |
|---|---|---|
| `records::py_repr` / `manifest::py_repr` | 1.000 | the intended copy, now correct |
| `records::printable` / `manifest::printable` | 1.000 | idem |
| `records::nonprintable` / `manifest::nonprintable` | 1.000 | idem |
| `records::escape` / `manifest::escape` | 1.000 | idem |
| `records::slashes` / `manifest::nonprintable` | 0.953 | NOT a duplicate: both are `OnceLock<Regex>` accessors, different patterns (`/{2,}` versus `^[\p{C}\p{Z}]$`). The similarity is the idiom, not the behaviour |
| `records::is_absent` / `manifest::blank_header_field` | 0.815 | NOT a duplicate: `blank_header_field` also treats an empty `String` as blank, `is_absent` does not; different domains (figure/extract rows versus header fields). Near-twins worth WP-5.1d's attention, but neither is stale |
| `records::mapping_get` / `manifest::insert` | 0.764 | noise on two-line bodies |

**The worker's conclusion holds: no second stale copy exists.** The method
should be structural rather than name-based in future audits, and WP-5.1d's
duplicate-helper audit clause should be written that way.

The clause 3b table is internally accurate: it reports `comm -12` yielding
`py_repr` and `truthy`, which is the pre-fix state, and separately records
that `printable`, `nonprintable` and `escape` were absent and have been
added. Post-fix there are five shared names, four of them the intended
identical copies. No discrepancy.

## The defect: the required cross-copy agreement test is missing

Revision 12 (`caa75e6`) added to the Phase 5 preamble, under **"A helper that
exists twice will drift"**:

> A port WP may not copy a helper out of another model module. Import it, or,
> where rule 1's Owns boundary genuinely forbids that, add a test asserting
> the two copies agree on a shared case list and say in evidence why
> importing was not possible.

`git log -S` confirms that paragraph landed in `caa75e6`, which precedes the
rework `9278501`, so it bound this work.

The rework satisfies two of the three requirements. Copying was genuinely
forced: `records.rs:226 py_repr` is private and `records.rs` is outside this
WP's Owns, so it cannot be made `pub`. The evidence says so. But **no test
asserts the two copies agree**. `mag/tests/model_manifest.rs` defines four
tests (`cases_match_the_python_loader`,
`python_crashes_are_reported_as_validation_errors`, `the_oracle_is_not_vacuous`,
`edition_010_matches_the_python_loader`) and none compares the `records` and
`manifest` escaping behaviour against each other. Evidence clause 10 tabulates
compliance against revision 11's four deliberate-divergence limits, which is a
different rule; this one is untabulated.

This is not a formality. The rule exists because of this exact defect, in this
exact WP, on this exact helper, and the window it guards is **open right
now**: `records.rs` is under active rework (WP-5.1b's third verification is in
flight), so if `py_repr` changes there, `manifest.rs` goes stale again and
`cargo test` stays green. The five new fixtures catch a regression on the
*manifest* side only; nothing catches divergence *between* the copies. That is
precisely how the first defect survived.

**The remedy is small and inside Owns.** Both copies are private, so a test
cannot call either directly across the `#[path]` module boundary, but it does
not need to: feed one shared case list of non-printable strings (at minimum
U+200B, U+0007, U+001B, U+F0000, plus a plain ASCII control and a printable
non-ASCII such as U+00E9) through each module's public refusal path and assert
the escaped forms agree. `mag/tests/model_manifest*` is owned by this WP, so
no boundary is crossed. When WP-5.1d consolidates the helpers the test becomes
redundant and can go with the duplication.

## To clear this rejection

Add that test, confirm it fails when the two copies are made to disagree
(perturb the local copy, not `records.rs`), and record in evidence both the
test and the reason importing was impossible. Nothing else in this WP needs to
change: the fix, the fixtures, the oracle chain, the audit conclusion and the
declared divergences all verified green above and should be left alone.

## Commands

    git show --stat 9278501
    git diff --numstat 4120821 9278501 -- mag/tests/model_manifest_cases_expected.json
    awk 'NR>=138 && NR<=183' meta/verification/evidence/WP-5.1c.md | sed 's/^    //' > /tmp/regen.sh && bash /tmp/regen.sh
    git diff --numstat mag/tests/model_manifest_cases_expected.json
    cd mag && cargo test --test model_manifest
    git log --oneline -S "A helper that exists twice will drift" -- meta/plans/typst-parity-and-rust-migration.md

## Tool versions

python 3.12.11, pyyaml 6.0.3, uv 0.8.17, rustc 1.96.0

## Status

`rejected`
