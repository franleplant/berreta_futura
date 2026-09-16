# WP-5.1d verification

## Verdict

**ACCEPTED.**

Verified commit `cc867a3` (pre-land HEAD `6a9b5cf`) from a fresh worktree.
Critique duty folded in per the orchestrator's brief.

## Why this WP existed

Duplication across the model modules is a demonstrated defect source, not a
tidiness preference. WP-5.1c was rejected because `manifest.rs` carried a
`py_repr` copy with the pre-fix body, the exact defect WP-5.1b had been
rejected for and already fixed in the tree when the copy was made. Closing
it took three further rework cycles. This WP's job was to make that class
impossible with no behaviour change, and it does.

## Owns

`git show --stat cc867a3` touches exactly nine paths, all within Owns:
`mag/src/model.rs`, `mag/src/model/{manifest.rs,records.rs,shared.rs}`,
`mag/tests/{model_helpers.rs,model_manifest.rs,model_records.rs,model_manifest_repr_expected.json}`,
`meta/verification/evidence/WP-5.1d.md`. No `*.verify.md`, no
`baseline.json`, no comparator territory, no Cargo files. `doc.rs` was in
Owns and correctly not touched (0 matches in the stat).

## Pre-lift byte-identity, the claim that makes "no behaviour change" a fact

The worker asserted the two duplicated regions were byte-identical before
the lift, so consolidation had no variant to choose between. Confirmed
independently against the parent commit:

```
git show 6a9b5cf:mag/src/model/records.rs  | sed -n '226,270p' > /tmp/pre_rec.txt
git show 6a9b5cf:mag/src/model/manifest.rs | sed -n '2232,2276p' > /tmp/pre_man.txt
diff /tmp/pre_rec.txt /tmp/pre_man.txt
```

Empty diff. Both regions begin `fn py_repr(text: &str) -> String {`.

Every lifted function was then diffed against its pre-lift original with
visibility normalised away. All seven identical:

| function | result |
|---|---|
| `py_repr` | identical modulo visibility |
| `printable` | identical modulo visibility |
| `nonprintable` | identical modulo visibility |
| `escape` | identical modulo visibility |
| `normalize` | identical modulo visibility |
| `safe_project_path` | identical modulo visibility |
| `load_structured` | identical modulo visibility |

`ValidationError` carries the same `#[derive(Debug, Clone, PartialEq, Eq)]`,
the same `pub struct ValidationError(pub Vec<String>)`, the same `Display`
body (`self.0.join("\n")`, unchanged text), the same `std::error::Error`
impl and the same `pub type Result<T>` alias.

## Nothing lost rather than moved

The orchestrator asked specifically for this, given 172 deletions against
34 insertions in the modified files. Function-name sets compared across all
model modules before and after:

- pre-lift: 129 unique function names
- post-lift: 129 unique function names
- lost (present pre, absent post): **none**
- added: **none**

The line delta is deduplication, not removal.

## Visibility

No gratuitous widening. `printable`, `nonprintable` and `escape` remain
private to `shared.rs`. `py_repr`, `normalize`, `safe_project_path`,
`load_structured` and `ValidationError::one` are `pub(crate)` because they
changed modules and their callers are siblings; `fn one` was private to
`records.rs` before, and private-to-`shared` would now make it unreachable
from `records.rs`, so the widening is forced rather than chosen.

`normalize` is called directly by `manifest.rs:1964-1965`, so it is pulled
for necessity on two counts, not only because `safe_project_path` needs it
as the evidence states.

## The audit: two keys, and they are genuinely complementary

`no_helper_is_defined_in_two_model_modules` keys on (name, signature) with
visibility stripped; `no_body_is_copied_between_model_modules` keys on the
normalised body ignoring names, skipping bodies under 40 characters. Both
parse all four modules and the first carries an `items.len() > 100` sanity
assert so a broken parser cannot pass silently (it finds 129).

Discrimination proved by running three injected defects, not by reading.
The third is mine; the worker did not construct it, and it is the
real-world shape of the original defect:

| injected copy | (name, signature) check | normalised body check |
|---|---|---|
| byte-identical x4, the WP-5.1c defect | **FAIL**, names all four | **FAIL**, names all four |
| **drifted: same name and signature, one line changed** | **FAIL**, names `py_repr` | passes (body differs) |
| renamed: `safe_project_path` as `tidy_project_path` | passes (name differs) | **FAIL** |

Each key catches exactly what the other misses, so neither alone suffices,
as claimed. The drifted probe is the important one: it reproduces WP-5.1c's
defect exactly (manifest stops importing `py_repr` and defines its own with
the pre-fix body) and body-equality cannot see it.

**Visibility normalisation confirmed by the same probe.** The injected copy
is a bare `fn py_repr`, while `shared.rs` has `pub(crate) fn py_repr`. They
collided, so visibility is genuinely normalised out of the signature key.
Had the worker's original defect survived, the signatures would have
differed and only the body check would have fired.

The tree restores clean after every probe (`git status` empty,
`model_helpers` 2 passed).

## Known false positives, all present and correctly unflagged

- `truthy` in both `records.rs:364` (`Option<&String>`) and
  `manifest.rs:2105` (`Option<&Value>`): shares a name, differs in
  signature and body.
- `slashes` (records) / `nonprintable` (shared): differ in name and body.
- `is_absent` (records) / `blank_header_field` (manifest): differ in name
  and body.
- `mapping_get` (records, `:490`) / `insert`: differ in name and body, and
  both bodies fall under the 40-character floor.

This is why the audit uses exact equality rather than a similarity score:
those cross-name pairs are precisely what a similarity metric flags, and
all of them are correct code.

## The repointed test

`py_repr_copies_agree` lost its premise once one definition exists, since
it would compare a function against itself. It was repointed rather than
deleted, which was the right call: a previous verification established the
backslash case is caught **only** there and not by
`cases_match_the_python_loader`.

`repr_cases_match_python` asserts, for each of nine cases, that `py_repr`
matches **Python's own `repr`** from a committed oracle, and that both the
manifest route (`load_translation`) and the records route
(`localize_figures`) produce that rendering. Agreement upgraded to
correctness, with the end-to-end reach through both modules kept.

`REPR_CASES` retains the backslash case
(`"back\\slash\nnew\rret\ttab"`), the apostrophe-only case (`"it's plain"`,
the quote-selection true branch) and the astral case
(`"astral\u{f0000}stop"`). The test asserts
`expected.len() == REPR_CASES.len()`, so a shrunken oracle fails loudly:
the self-weakening-oracle lesson from WP-5.1b was carried across.

**The oracle is Python's output, not Rust's.** Regenerated independently
with `repr()` over the same nine cases and compared:

```
uv run python <regen script> > /tmp/repr_regen.json
diff /tmp/repr_regen.json mag/tests/model_manifest_repr_expected.json
```

Byte-identical. sha256 prefix `e7186560`, matching the evidence.

## Oracles before and after

Every committed oracle compared between `6a9b5cf` and `cc867a3`:

| oracle | pre | post | |
|---|---|---|---|
| critic_metrics_expected.json | c519fdfb | c519fdfb | identical |
| critic_metrics_rounding_expected.json | 1d642913 | 1d642913 | identical |
| model_doc_expected.json | 4a584524 | 4a584524 | identical |
| model_manifest_cases_expected.json | 1045b017 | 1045b017 | identical |
| model_records_cases_expected.json | 34feb1a9 | 34feb1a9 | identical |
| model_records_create_expected.json | be1563b1 | be1563b1 | identical |
| model_records_expected.json | 611d885c | 611d885c | identical |
| model_records_ports_expected.json | 331c78f3 | 331c78f3 | identical |
| model_records_records_expected.json | 1e9bc575 | 1e9bc575 | identical |
| model_records_urls_expected.json | 271f1aed | 271f1aed | identical |
| model_doc_settable.txt | df2687d0 | df2687d0 | identical |
| model_manifest_repr_expected.json | (absent) | e7186560 | new |

WP-5.1a's 010 projection regenerated from the Python side and re-run:
`e17ca71cffabe08b08820dd268863dcbda04615a871e5feaf52c34ca907cda50`,
208,052 bytes, and
`edition_manuscripts_match_the_python_projection` passes against it.

## Deliberate divergences survive

All three present and passing in the full run:
`port_refusal_messages_match_python` (records' port `ValueError`),
`cases_match_the_python_loader` and
`python_crashes_are_reported_as_validation_errors` (manifest's
`_check_unique_art` crash recovery, and the foreign-parser prefix
comparison).

## Baseline

Fresh worktree at `cc867a3`: `cargo fmt --check` exit 0,
`cargo clippy --all-targets -- -D warnings` clean, `cargo test`
**95 passed, 0 failed** across 9 binaries (93 before, the two added being
the audit).

## Residuals

- The body check skips bodies under 40 characters. A duplicated helper that
  is both short **and** renamed would slip both keys. Narrow, since a short
  duplicate with the same name is still caught by the signature key, and
  the floor is what keeps `mapping_get`/`insert` from false-firing. Worth
  knowing rather than fixing.
- The audit parses source text rather than using a syntax tree, so it is
  sensitive to formatting conventions (it keys off a line whose trimmed
  form starts with `fn ` after an optional visibility prefix, and a closing
  brace at the opening indent). `cargo fmt` is enforced by the hook, which
  is what makes this safe in this repo.
- The `items.len() > 100` assert will need revisiting if the model modules
  are ever split further, which is a feature: it forces attention rather
  than silently weakening.
