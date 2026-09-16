# WP-5.4a verification

## Base

Worker commit `6a84018`, pre-land HEAD `abf79d5`. Verified in a clean worktree
at `6a84018`. Protocol rule 3, critique duty folded in.

## Verdict

**REJECTED**, narrowly. Every substantive claim verified, including the Unicode
pin, which is independently confirmed and is the strongest part of the work. The
rejection is for one uncovered-branch class under a blanket coverage claim, the
same shape WP-5.3a was rejected for at `a3d61c9`, and it is not merely a
documentation gap: the uncovered `Tagged` arm already disagrees with its sibling
implementation in `manifest.rs`. Remedy is two fixtures and three corrected
sentences.

## Owns

`git show --stat 6a84018` lists exactly the seven declared paths: `mag/src/cover.rs`,
`mag/src/cover/text.rs`, `mag/src/main.rs`, `mag/tests/cover_text.rs`,
`mag/tests/cover_text_expected.json`, `mag/tests/cover_text_unicode_expected.json`,
`meta/verification/evidence/WP-5.4a.md`. No verify file, no `baseline.json`, no
Cargo change, nothing under `mag/src/model/`, `mag/src/parity/` or
`mag/src/critic/`. Clean.

## Port fidelity, read against the Python

Read `cover.py`'s four originals line by line against `mag/src/cover/text.rs`:

- `_cover_date`: `all(parts)` is truthiness on strings, so an empty part fails it;
  the port's `!part.is_empty()` is equivalent. Length-3 condition matches.
- `_cover_contributors`: `strip` then `casefold` dedup then `" / ".join(...).upper()`,
  else `str(edition.cover.get("deck", "")).strip()`. The port's `deck()` uses
  `cover.get("deck").map(python_str).unwrap_or_default()`, which reproduces the
  Python default exactly: key absent gives `""` (the `""` default, not `str(None)`),
  key present and null gives the literal `"None"`. Correct and easy to get wrong.
- `cover_tab_issue`: `split("-", 1)[0] == "en"` versus the port's
  `split('-').next() == Some("en")` agree on the first element. `NÚMERO` is
  `N\u{da}MERO`. Correct.
- `cover_tab_identity`: matches.
- `python_zfill`: CPython computes `width - len(self)` from the ORIGINAL length
  including the sign, then emits `sign + zeros + rest`. The port does the same.
  Correct, and the usual place a zfill port goes wrong.

## Baseline

In the worktree at `6a84018`: `cargo fmt --check` clean, `cargo clippy --all-targets
-- -D warnings` clean, `cargo test` green — 20 tests across 6 binaries, the
whole-plane sweep binary taking 22.61s.

## The three whole-plane sweeps: regenerated independently, exact

Regenerated all three from scratch rather than replaying the worker's command, over
every non-surrogate codepoint:

| sweep | mine | committed | result |
|---|---|---|---|
| casefold | 1530 | 1530 | EQUAL |
| upper | 1525 | 1525 | EQUAL |
| python_space | 29 | 29 | EQUAL |

Codepoints swept: 1,112,064, matching the claim. The dict counts also reconcile
with the in-source table sizes (1530 and 1525 entries; a naive `split(";")` over
the source line yields 1531/1526 because of the statement terminator).

**A hazard I hit, which confirms the evidence is right to pin its interpreter.**
My first regeneration used bare `python3` and produced 1490/1485 — forty entries
short in each map, the missing keys clustering in Vithkuqi (U+10570+) and U+A7D8.
The cause is two Pythons on this machine with different Unicode versions: system
`python3` is 3.9.6 / Unicode 13.0.0, while `uv run python` is 3.12.11 / Unicode
15.0.0. Regenerated with `uv run python`, all three sweeps match exactly. The
evidence's `## Commands` pin `uv run python` in all three invocations, so the
recorded method is correct; this is noted because anyone replaying with the
system interpreter would get a different oracle and mistake it for a port defect.

## The Unicode 15.0.0 divergence: real, verified both sides

(a) **The divergence is real.** Compiled a standalone probe with the repo's
`rustc 1.96.0` and compared against `uv run python`:

| codepoint | Python 15.0.0 upper | Rust std upper |
|---|---|---|
| U+019B | identity | U+A7DC |
| U+0264 | identity | U+A7CB |
| U+1C8A | identity | U+1C89 |
| U+A7CD | identity | U+A7CC |
| U+A7DB | identity | U+A7DA |
| U+10D70 | identity | U+10D50 |
| U+10D85 | identity | U+10D65 |
| U+16EBB | identity | U+16EA0 |
| U+16EC4 | identity | U+16EA9 |

and `U+1C89` lower: Python identity, Rust `U+1C8A`. U+A7D0 agrees, as a control.
Had the port used `char::to_uppercase`, it would diverge from the oracle on these.

(b) **The pinned tables exclude them.** All nine keys are absent from `UPPER_DATA`
and `1c89` is absent from `FOLD_DATA`, so each takes the identity fallback and
matches Python.

(c) **The identity fallback is correct everywhere else**, established by the
whole-plane sweeps above: the maps hold exactly the codepoints Python maps, and
every other codepoint is asserted unchanged.

(d) **Freezing on Unicode 15.0.0 is the right call while Python is the oracle**,
and it is a real decision rather than an accident: the alternative silently makes
the port's output depend on the Rust toolchain version, which would have surfaced
later as an inexplicable WP-5.5a web-oracle failure, since these functions feed
the web edition whose oracle is byte-identical output. The evidence flags it for
revisiting at WP-6.1, which is the correct owner: once Python is deleted the pin
becomes a frozen table with no oracle behind it.

## Dedup on live edition 010: fires

From the tracked `editions/010/edition.yaml`, nine articles carry nine author
strings of which `Anthropic` appears twice; the dedup reduces them to eight. The
`edition_010` row is therefore load-bearing rather than decorative, as claimed.

## Discrimination probes

Reproduced three of the seven, each by perturbing `mag/src/cover/text.rs` in the
worktree and restoring afterwards:

| probe | result |
|---|---|
| `is_python_space` loses the `U+001C..U+001F` range | FAIL: `python_strip_matches_python_over_all_codepoints` **and** `cover_contributors_matches_python` |
| `python_casefold` replaced by `value.to_lowercase()` | FAIL: `casefold_matches_python_over_all_codepoints` **and** `cover_contributors_matches_python` |
| `python_zfill` loses its sign branch | FAIL: `cover_tab_issue_matches_python` and `zfill_matches_python_on_sign_and_width` |

**The eighth-probe correction is real.** The worker records that an earlier probe
perturbing the uppercase table's hit branch did not discriminate, and says it
corrected rather than recorded it. I tested the hit branch directly, making
`mapped` return the original character on a map hit: four tests fail, including
both the `upper` and `casefold` sweeps. The hit branch is genuinely covered.

Restored to pristine after every probe; `git status` empty, suite green.

## The defect: two implemented arms reached by no fixture

`## Branches edition 010 cannot reach` claims fixtures cover them all. Two arms of
`python_str` are reached by no fixture and no oracle row:

- **`Value::Mapping`.** `deck_list` covers `Sequence`; there is no mapping deck.
  `deck: {a: 1}` is valid YAML in `edition.yaml`, so the arm is reachable. By
  inspection it looks correct (Python's `str(dict)` reprs both keys and values,
  which `python_repr` does), but inspection is what failed in the four prior
  defects of this class.
- **`Value::Tagged`.** No fixture, and this one is not merely untested: it
  **already disagrees with its sibling implementation**. `cover/text.rs`'s
  `python_str(Tagged(String("x")))` recurses to `python_str` and yields `x`,
  while `manifest.rs`'s `py_str(Tagged(String("x")))` routes through
  `py_repr_value` and yields `'x'` — str versus repr. Unreachable from
  PyYAML-safe-loaded YAML, so not a live defect, but it is precisely the drift
  the duplicated-helper rule exists to prevent, and a fixture would have exposed
  it.

This is the shape WP-5.3a was rejected for at `a3d61c9`: an implemented branch
reached by nothing, under a blanket claim that all unreachable branches are
covered. Consistency requires the same treatment.

## Two errata

- The evidence says "41 committed oracle rows"; the committed file holds **40**,
  and the evidence's own breakdown (`cover_date` 8, `cover_contributors` 18,
  `cover_tab_issue` 10, `cover_tab_identity` 4) sums to 40.
- Rule 10 labelling is honest and correct: `deck_empty`, `deck_absent` and
  `blank_skipped` do all produce `""`, are labelled non-discriminating, and are
  justified as separating three code paths that end at one value.

## Remedy

1. Add a mapping-deck fixture and regenerate the oracle.
2. Either add a `Tagged` fixture, or record a proof that the arm is unreachable
   from `edition.yaml` under PyYAML safe-load semantics — and in either case
   record the `python_str`/`py_str` disagreement on that arm, since it is a live
   inconsistency between two implementations of one Python semantic.
3. Replace the blanket coverage heading with a per-arm statement naming what each
   fixture reaches, as WP-5.3a did after its own rejection.
4. Correct 41 to 40.

## Seam residuals, assessed

- `is_python_space` is **byte-identical** between `mag/src/model/doc.rs:492` and
  `mag/src/cover/text.rs:50`. A genuine duplicate, currently in agreement.
- `py_str` / `python_str` are two structurally different implementations of
  Python's `str()`, disagreeing on `Tagged` as described above.
- `py_repr` was genuinely imported from `model::shared`, not copied. Correct.
- **The audit-scope gap is confirmed.** `mag/tests/model_helpers.rs:4` reads
  `const MODULES: [&str; 4] = ["doc.rs", "manifest.rs", "records.rs", "shared.rs"]`,
  so WP-5.1d's duplicate audit cannot see `mag/src/cover/text.rs` at all. Note
  also that widening the name-keyed check alone would not catch the
  `py_str`/`python_str` pair, because the names differ; only the body-keyed check
  would, and only if the bodies were closer than they are. This is a finding about
  WP-5.1d's scope as much as this WP's, and belongs to the tracked follow-up that
  lifts the Python-semantics helpers into `shared.rs` and widens the audit beyond
  the model modules.

## Status

rejected
