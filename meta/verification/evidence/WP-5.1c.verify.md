# WP-5.1c verification

## Verdict

**REJECTED.** One material defect: `manifest.rs` carries a copy of `py_repr`
that is NOT identical to the one in `records.rs`. It is the pre-fix body,
missing non-printable escaping entirely, which is the exact defect WP-5.1b
was rejected for at verify commit `44fb08c` and fixed at `b39ccf3`.

Everything else in the submission verifies. The oracle chain, the refusal
coverage, the shared `ValidationError`, both declared divergences and the
test's comparison discipline are all sound, and the rework should leave them
alone.

## Base

WP commit `4120821` (feat(model): WP-5.1c manifest port), verified in a
fresh worktree at that commit.

## Owns check: PASS

`git show --stat 4120821` lists exactly six files, all within Owns:
`mag/src/model/manifest.rs`, `mag/src/model.rs` (one line),
`mag/tests/model_manifest.rs`, `mag/tests/model_manifest_fixtures/cases.yaml`,
`mag/tests/model_manifest_cases_expected.json`,
`meta/verification/evidence/WP-5.1c.md`. No `*.verify.md`, no
`baseline.json`, no comparator territory, no Cargo files, no `doc.rs` or
`records.rs`.

## The defect

`records.rs:226` and `manifest.rs:2232` both define `fn py_repr(text: &str)`.
The evidence claims manifest carries "an identical private copy". It does
not. The final match arm differs:

    records.rs:   other if printable(other) => out.push(other),
                  other => out.push_str(&escape(other)),

    manifest.rs:  other => out.push(other),

`manifest.rs` has no `printable` predicate and no `escape` helper, so every
non-printable character is emitted raw.

Measured against Python, running the manifest copy verbatim on seven probes:

| input | Python `repr` | manifest.rs `py_repr` |
|---|---|---|
| `id<ZWSP>x` | `'id​x'` | `'id<raw ZWSP>x'` |
| `a<NUL>b` | `'a\x00b'` | `'a<raw NUL>b'` |
| `bell<BEL>` | `'bell\x07'` | `'bell<raw BEL>'` |
| `esc<ESC>` | `'esc\x1b'` | `'esc<raw ESC>'` |
| `nel<NEL>` | `'nel\x85'` | `'nel<raw NEL>'` |
| `ok-normal` | `'ok-normal'` | `'ok-normal'` (agrees) |
| `café` | `'café'` | `'café'` (agrees) |

Five of seven diverge. The two that agree are the two that should.

### Why this is material rather than cosmetic

The WP-5.1b rework fix (`b39ccf3`) is an ancestor of `4120821`
(`git merge-base --is-ancestor` confirms), so the corrected body existed in
the tree when this copy was made. The copy is stale, not merely independent.

There are 25 `py_repr` call sites in `manifest.rs`, and they carry
user-authored text: `edition_id` (:223), `author` (:397), `record.title`
(:770), `kind` (:839), `section.kind` (:1535), `language` (many), and
critically `py_repr_value` at :2203, whose `Value::String(text) =>
py_repr(text)` arm reprs ANY string value drawn from `edition.yaml`.

That is the worst possible home for this bug. WP-5.1b's verifier flagged the
same defect in `records.rs` precisely because anchors and extract begin/end
markers "are hand-authored in edition.yaml and routinely pasted from the web,
where a zero-width space is an ordinary artifact" — and `manifest.py` is the
module that validates `edition.yaml`. The defect was fixed in the module
that rarely sees those fields and reintroduced in the module that owns them.

### Why no test caught it

`grep -cP` for non-printables over
`mag/tests/model_manifest_fixtures/cases.yaml` returns **0**. The 74-case
fixture corpus contains no non-printable character anywhere, so all 122
compared messages exercise only the agreeing path. This is the same vacuity
pattern that hid WP-5.1a's container-collapse defect (010 contained no
padded container) and WP-5.1b's own two divergences (the corpus has no
explicit port and no non-printable).

### To clear

1. Make the two `py_repr` bodies share one implementation, or make the
   manifest copy behaviorally identical (the `printable` predicate over
   `[\p{C}\p{Z}]` with space excepted, plus `\xNN` / `\uNNNN` / `\UNNNNNNNN`
   escape forms). The evidence already recommends lifting `ValidationError`,
   `py_repr`, and `io.py`'s helpers into a shared module; that follow-up now
   has a demonstrated defect behind it, not just tidiness.
2. Add fixture cases carrying non-printables in the fields that reach
   `py_repr`, at minimum an anchor or extract marker containing a zero-width
   space, so this cannot regress silently.
3. Re-run the case oracle and confirm the new cases compare exactly.

## What verifies and should be left alone

**Baseline, in a clean worktree at 4120821**: `cargo fmt --check` exit 0,
`cargo clippy --all-targets -- -D warnings` clean, `cargo test` green
(model_manifest 4 passed, model_records 8 passed, nocomments 1, parity_faults
1). Note the 4 model_manifest tests pass with `edition_010_matches_the_python_loader`
early-returning, because it is env-gated on `MAG_MANIFEST_ROOT` +
`MAG_MANIFEST_ORACLE`; this is disclosed in the evidence and matches WP-5.1a's
precedent, and I ran it properly below.

**Shared `ValidationError`: confirmed.** `pub struct ValidationError` is
defined only at `records.rs:11`; `manifest.rs:4` imports it from
`super::records`. One type, not two, as claimed.

**The 010 oracle chain: replayed in full and it holds.** Staged root built
from the evidence's script, reporting `manuscripts=9 art=24` as documented.
Python loader output is 12,926 bytes, matching the claim exactly. The Rust
comparison passes. The plan's `jq -S` extraction against the real rendered
manifest `editions/010/render-2026-09-14T01-47-59/en/edition-manifest.json`
gives an EMPTY diff against the fresh Python load, and the no-null sanity
check prints `true`. So Rust port = Python loader = shipped artifact, as
claimed; the worker chaining it to the real artifact was worth doing.

**The oracle is not vacuous, on my own perturbation.** I perturbed a
different field than the worker (changed `article_content_modes` for
`an-alignment-assessment-of-recent-cybersecurity` to `in_a_nutshell`, rather
than the worker's page cap) and the test fails with "edition 010 diverges
from the Python loader".

**Refusal-site count: reconciled, not disputed.** My raw count is 12
`raise ValidationError` statements in `manifest.py` and 4 in `io.py`; the
worker's "87 + 4" counts diagnostic-emitting sites (84 `.append(` calls plus
raises), which is the meaningful unit for a module that accumulates errors
and raises aggregates. The evidence carries an inline enumeration script, so
the convention is reproducible rather than asserted. The two uncovered
aggregate sites at `manifest.py:158` and `:702` are both
`raise ValidationError(errors)` as claimed, exercised by every refusing case.

**Ordering IS compared, not set-compared.** `cases_match_the_python_loader`
compares `&got != want` over whole JSON values, so error arrays compare
ordered. `BTreeSet` appears only for input `known_sources` (:203, :367), never
in the comparison path. The accounting assertion
`compared + PYTHON_CRASHES.len() == expected.len()` prevents a case being
silently dropped from the corpus, which is the right guard for a suite that
skips two categories.

## Judgment on the two declared divergences

**1. The pre-existing Python crash: correctly handled and adequately
recorded.** `_check_unique_art` trusting shapes the validator already
rejected is a real Python bug, and it discards diagnoses Python itself
accumulated. Returning those diagnoses beats reproducing a crash, and the
port is not merely different: `python_crashes_are_reported_as_validation_errors`
asserts the exact recovered list per case and asserts the Python side
genuinely recorded `AttributeError`/`TypeError`, so the divergence is pinned
rather than hand-waved. I agree with the worker that fixing `manifest.py`
needs a sanctioned-oracle-change assignment (the WP-0.0b / WP-0.0c / WP-1.5
pattern), since no current WP owns `src/magazine/manifest.py`.

**2. The foreign-parser prefix comparison: drawn at the right point.**
`compare_parser_diagnostics` (:417) checks count and ordering first, then for
each differing pair requires the shared prefix to BOTH end with `": "` AND
contain `<ROOT>`. So the message template the port authors and the path it
interpolates are inside the compared region, and only PyYAML's own wording
falls outside. Nothing the port authors escapes comparison. This correctly
mirrors WP-5.1b's filesystem-order precedent.

## Control flow

No ordering or control-flow divergence surfaced. The exact-list assertions
would expose a reordered accumulation, and the fixture corpus drives 122
compared messages through them. I did not find a fixture whose claimed site
is short-circuited by an earlier refusal, though I note that with 74 cases I
checked the comparison machinery rather than each case's provocation
individually.

## Residuals

- The fixture corpus contains zero non-printable characters, which is what
  allowed the defect. Worth stating as a standing rule for the remaining
  Phase 5 ports: a port whose oracle corpus is uniformly well-formed proves
  less than its case count suggests.
- Duplicated helpers across `records.rs` and `manifest.rs` (`py_repr`, and
  the `printable`/`escape` pair by its absence) are now a demonstrated
  defect source, not a style matter. The shared-module follow-up spans two
  WPs' owned files and needs a WP that owns both, or WP-6.1.
- `edition_010_matches_the_python_loader` is env-gated and silently skips
  under plain `cargo test`. It fails loudly if exactly one variable is set,
  which is the right guard, but the 010 proof is a verifier obligation
  rather than a CI one.

## Status

rejected
