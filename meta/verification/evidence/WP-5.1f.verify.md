# WP-5.1f and WP-5.1g verification (joint)

**Verdict: WP-5.1f ACCEPTED.**
**Verdict: WP-5.1g ACCEPTED.**

Both with required corrections, enumerated in section 9. `WP-5.1g.verify.md`
carries the WP-5.1g verdict and points here for the shared measurements; this
file is the full record. One verifier, both WPs, because WP-5.1g corrected a
fixture defect in WP-5.1f and a verification of either alone would have missed
the interaction.

## Base

Commits under test: `02f1d35` and `160c39e` (WP-5.1f), `3b9cbcb` (WP-5.1g).
Measurement commits are named beside every number below, because three of the
totals in the evidence moved with the branch.

Two fresh worktrees, neither of them the worker's:

- `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp51fg` at `3b9cbcb`
- `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/ver51f-at160` at `160c39e`

WP-5.1f's `## Commands` blocks were replayed at `160c39e`, WP-5.1g's at
`3b9cbcb`. Replaying WP-5.1f's blocks at `3b9cbcb` is not merely stale, it is
destructive; see finding F4.

`art_directed` was at `a911ff1` when work began and `389ad0b` when the
coordinator's update arrived. `B` is captured immediately before rebasing, so
neither reading is load-bearing.

## Commands

Every `## Commands` block was extracted PROGRAMMATICALLY from the evidence
file rather than retyped, per rule 12, and executed from a worktree created
for this verification:

```
uv run python tools-scratch/extract.py meta/verification/evidence/WP-5.1f.md <outdir>
uv run python tools-scratch/extract.py meta/verification/evidence/WP-5.1g.md <outdir>
for b in <outdir>/block*.sh; do bash "$b"; done
```

The extractor splits the `## Commands` section on fenced blocks and writes
each block and its preceding prose to `blockNN.sh` and `blockNN.caption.txt`,
so each block's output is read against its own caption's scope words. WP-5.1f
yields 12 blocks, WP-5.1g yields 7. The extractor and the four scratch Rust
harnesses below live in
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/work/` and are not committed.

Mutation matrix (`zz_verifier_mutants.rs`, `zz_verifier_roster.rs`): six
`content_label` implementations and six `is_name_roster` implementations
evaluated against each fixture case, reporting per case which mutants it kills.
This is the instrument for the rule 10c sweep.

Guard perturbation (`perturb.py`): nine edits to the three committed fixtures,
each followed by the affected test binary, each restored with
`git show HEAD:<path> > <path>`.

Boundary and unenumerated-input probes (`zz_verifier_probe.rs`,
`zz_ver_four.rs`) plus a `uv run python` twin for the Python leg.

All Python is `uv run python`, CPython 3.12.11, Unicode 15.0.0. The system
`python3` (3.9.6, Unicode 13.0.0) was not used anywhere; these WPs are entirely
about Python character semantics and the wrong interpreter would invalidate
every number in this file.

## 1. WP-5.1f, replayed at `160c39e`

Every block reproduced. Reading each output against its caption:

| block | caption's scope words | reproduced |
|---|---|---|
| 1 | roster oracle regenerated "from the Python function itself" | yes, byte-identical to the committed file |
| 2 | label oracle regenerated "through the real frontmatter parse and the real `_content_label`" | yes, byte-identical |
| 3 | whitespace oracle, "as enumerations rather than as totals" | yes, byte-identical; `python 3.12.11 unicode 15.0.0`, count 29 |
| 4 | `isspace` is the right oracle for `strip`/`split`, "checked over every codepoint rather than assumed" | yes: both disagreement lists empty |
| 5 | the Rust half "enumerated" | yes, count 25 |
| 6 | corpus reachability over every tracked `.yaml`/`.yml`/`.md` | yes: `files=1433 by_top_dir={'editions': 1241, 'library': 192}`, occurrences 0 |
| 7 | "every tracked `label:` key" | yes: 548 total, 0 bare, 20 listed lines |
| 8 | whether the roster helper fires at all | yes: 195 U+2022 occurrences in 8 files |
| 9 | the demonstration, both directions | yes, see below |
| 10 | "Every whitespace-handling site in `mag/src/model/shared.rs`" | 7 lines, see finding F2 |
| 11 | "every call site of the two helpers, across all of `mag/src/`" | yes |
| 12 | repository gate | `fmt` clean, `clippy -D warnings` clean, `cargo test` exit 0 |

The three regenerated oracles left `git status --porcelain` EMPTY. The
recorded generators reproduce the committed fixtures exactly, which is the
strongest available statement that the committed files are the ones the
recorded commands produce.

**Block 9, counting the failures the caption promised.** The caption promises
failure "in both binaries, naming the two disagreeing roster cases and the two
disagreeing label cases and neither control". Four failures were promised and
four arrived, in two separately invoked binaries:

```
seven words, but only when U+001E splits: python false, rust true, for "a b c d e f\u{1e}g • C D • E F"
a segment that is empty only after a Python strip: python false, rust true, for "\u{1e} • C D • E F"
```
```
a label that is whitespace only under Python: python "ARTICLE", rust "\u{1e}"
a label padded with U+001E: python "ARTICLE", rust "\u{1e}ARTICLE\u{1e}"
```

then all seven green on the second half. No control appears in either message.
The block splits the two binaries into separate commands precisely because
`cargo test --test a --test b` stops at the first failing binary; the split is
present in the committed block and the replay confirms it delivers 2 + 2
rather than 2.

**The whitespace sets, re-derived rather than cited.** Python `str.isspace()`
holds for **29** codepoints, Rust `char::is_whitespace` for **25**, over all
1,114,112 codepoints with the surrogate range skipped on both sides. The
Python-only set is exactly `U+001C U+001D U+001E U+001F`; the std-only set is
empty. `f"a{c}b".split()` and `f"{c}a{c}".strip()` agree with `c.isspace()` on
every codepoint with zero exceptions, so the WP's decision to MEASURE the
`strip`/`split` equivalence rather than argue it from CPython source is sound
and its result holds on this interpreter.

**Past the convenient end.** The fixtures sample U+001E only, one of the four.
I measured all four end to end in both engines rather than assuming the helper
generalises:

```
U+001C roster_seven=false roster_empty=false roster_inside=true padded="Dispatch" only="ARTICLE"
U+001D ... U+001E ... U+001F   (identical, and the Python leg identical to the Rust leg)
```

All four behave alike and the two engines agree on all four, so the
single-separator sample is representative here. That is measured, not assumed,
and it is the check the "a sample can land inside the agreeing region"
hazard asks for.

## 2. WP-5.1g, replayed at `3b9cbcb`

| block | caption's scope words | reproduced |
|---|---|---|
| 1 | which YAML spellings are null "on both sides" | yes, 12 spellings, Python leg |
| 2 | Python's agreement, "corroboration, not the fixture's basis" | yes: `cases=13 python_disagreements=0 []` |
| 3 | "every tracked `label:` key" | yes: total 548, distinct 20, null spellings 0, booleans 0 |
| 4 | the demonstration, both directions | yes, see below |
| 5 | "Every whitespace-handling and null-handling site" | 8 lines, see finding F2 |
| 6 | every implementation and call site of `content_label` | yes |
| 7 | repository gate | `fmt` clean, `clippy -D warnings` clean, `cargo test` exit 0 |

**Block 4, counted against its caption.** The caption promises the pre-fix
`shared.rs` "must FAIL naming all four null spellings while the four tests
that do not depend on the guard pass". Exactly that:

```
a bare null label: expected "ARTICLE", got "None"
a tilde null label: expected "ARTICLE", got "None"
a spelled null label: expected "ARTICLE", got "None"
a shouted null label: expected "ARTICLE", got "None"
...
test result: FAILED. 4 passed; 3 failed
```

and 7 passed after restoring the fixed file. All four spellings are named by
the accumulating assertion rather than the first one only.

## 3. The interaction: could WP-5.1f's padded case discriminate?

This is the question the two WPs were sent to me together for, and it is
answerable by construction rather than by argument. Six `content_label`
implementations were evaluated against each fixture case:

- `correct` (as shipped at `3b9cbcb`)
- `always_fallback` (returns `ui(language, content_mode)`, discards the label)
- `always_declared` (returns the stripped declared value, no fallback)
- `std_trim` (WP-5.1f's pre-fix body)
- `no_null_guard` (WP-5.1g's pre-fix body)
- `no_return_strip` (`py_strip` decides emptiness, the RAW value is returned)

**Half one: WP-5.1f's padded case genuinely could not discriminate.** Against
WP-5.1f's own five-case fixture at `160c39e`:

```
CASE "label: \"ARTICLE\"" exp="ARTICLE" == fallback? true
     kills=["std_trim(pre-5.1f)", "no_return_strip"]
```

`always_fallback` SURVIVES it. The wrong-branch implementation was constructed
and it passes the case, exactly as WP-5.1g claims. Confirmed.

**Half two: WP-5.1g's replacement genuinely can.** Against the thirteen-case
fixture at `3b9cbcb`:

```
CASE "label: \"Dispatch\"" exp="Dispatch" == fallback? false
     kills=["always_fallback", "std_trim(pre-5.1f)", "no_return_strip"]
```

It is the ONLY case in either fixture that kills all three, and it is
therefore strictly stronger than the case it sits beside. Confirmed.

**What WP-5.1g's framing gets right and what it understates.** The defect is
per CASE, not per fixture SET: at set level, WP-5.1f's two `Dispatch` controls
already killed `always_fallback`, so the set was not blind. WP-5.1g says
exactly this ("it cannot tell the two branches apart, and it was the only
padded case"), and the narrower claim is the true one. The padded case was not
worthless either: it kills the pre-fix body and it kills `no_return_strip`,
which is what establishes the WP's sharpest finding, that the strip changes
the RETURNED VALUE and not only the empty test. Both halves of WP-5.1g's
account survive construction.

The shipped implementation is killed by zero of the thirteen cases, and every
one of the five mutants is killed by at least three.

## 4. The rule 10c sweep, both fixture sets

Rule 10c: an expected value equal to a fallback, default, refusal, or the
input itself proves only that one of two branches ran. Nobody had swept for
this, so every case in both sets was classified mechanically.

**Roster fixture (3 cases): no instance.** `is_name_roster` returns a bool and
has no fallback. Both polarities are present, so constant mutants die:
`always_true` is killed by the two `false` cases, `always_false` by the
control. Each case kills a distinct mutant, and the WP's claim that fixing one
half leaves the other red is confirmed precisely:

```
strip_fixed_only: disagreeing=1 ["seven words, but only when U+001E splits"]
split_fixed_only: disagreeing=1 ["a segment that is empty only after a Python strip"]
```

**Label fixture (13 cases), fallback limb: exactly one instance, and it is the
one already flagged.** Seven cases expect `ARTICLE`, which is the fallback. For
six of the seven the fallback IS the semantically correct destination (four
null spellings, the U+001E-only label, the empty string), so the coincidence is
not a defect: the case's whole purpose is to assert that the fallback branch
was taken, and each still kills `always_declared` or `no_null_guard` or both.
Only WP-5.1f's padded `ARTICLE` case has the DECLARED branch as its correct
destination while its expected value equals the fallback. That is the single
instance, it was found by WP-5.1g, and it is neutralised rather than removed.

**Label fixture, input-itself limb: four instances, NOT flagged by WP-5.1g.**
This is rule 10c's second limb and the evidence addresses only the first.

| case | expected | equals raw input | kills |
|---|---|---|---|
| `label: Dispatch` | `Dispatch` | yes | `always_fallback` only |
| `label: None` | `None` | yes | `always_fallback` only |
| `label: "None"` | `None` | yes | `always_fallback` only |
| `label: false` | `False` | yes (`py_str` of it) | `always_fallback` only |

Each proves only that the declared branch ran, and none can distinguish
"returned the declared value" from "returned the raw input unstripped":
`no_return_strip` survives all four. The SET is rescued, by the two padded
cases and by `label: "  Dispatch  "`, which are the three cases that kill
`no_return_strip`. So this is a finding about four individually weak cases
inside a set that covers the axis, not a hole. Recorded because rule 10c's
second limb is unswept in the evidence and a later reader deleting the
ASCII-padded "control" as redundant would open the hole for real.

`label: "None"` is additionally redundant with `label: None` under every
mutant; it earns its place as the straddle's quoted twin rather than as
discrimination.

No case in either set kills nothing.

## 5. The five guards, each perturbed until it fired

Nine perturbations, each applied to a committed fixture, each followed by the
affected binary, each restored with `git show HEAD:<path> > <path>`. All nine
went red; `git status --porcelain` was empty afterwards.

| # | perturbation | guard that fired | message |
|---|---|---|---|
| P1 | drop `28` (U+001C) from the isspace oracle | guards 1 and 3 | `python-only whitespace`, `python space count` |
| P2 | add `65` (U+0041) to the isspace oracle | guards 1 and 3 | same two |
| P3 | roster case 1, U+001E to ASCII space | guard 2 (roster) | `two cases must expose the std whitespace set, else the fixtures prove nothing` |
| P4 | label U+001E-only case, U+001E to ASCII space | guard 2 (label) | `three cases must expose std trim, else the fixtures prove nothing` |
| P5 | new case with `status: "unknown"` | guard 4 | `every case declares one of the two statuses` |
| P6 | new case with NO `status` key | load assertion | all 7 tests panic at `model_shared_label.rs:38` |
| P7 | new case with `why: ""` | guard 5 | all 7 tests panic at `model_shared_label.rs:30` |
| P8 | delete the tilde-null case | `the_null_cases_are_ones_the_missing_guard_got_wrong` | `every null spelling must expose the missing guard` |
| P9 | revert WP-5.1g's `Dispatch` case to the `ARTICLE` shape | `a_padded_label_proves_the_declared_branch_was_taken` | red |

So: a fixture edited into harmlessness fails rather than going quiet (P3, P4),
a new case cannot be added without choosing a status (P5, P6), and a case with
an empty `why` cannot load (P7). Every guard the brief names does what it
claims.

Guard 1's third assertion, `!character.is_whitespace()` for each of the four,
is the one that matters most and it is present: if a future Rust release
adopts the field separators the fixtures stop discriminating anything, and
this turns that into a red build naming the codepoint rather than a suite that
passes for the wrong reason.

## 6. Is the fixture authored from the spec, or transcribed from the output?

The sharper axis, since transcription from Python's output has the same defect
as generation.

**Not generated, and not regenerable.** Verified, not assumed: the only writer
of `mag/tests/model_shared_label_expected.json` anywhere in the tree is
WP-5.1f.md's superseded block (see F4). WP-5.1g's corroboration block opens the
file with `json.load` and compares, so it CANNOT write it, and no generator
appears in WP-5.1g's evidence, in `tools/`, or anywhere under `mag/`. Python
has no mechanism to silently redefine these values later. That is the half of
the claim that is fully established.

**Spec-derivable, case by case.** Twelve of the thirteen expected values follow
from stated product rules without observing Python at all: a null label
declares nothing so the UI label applies (four spellings); YAML has no `None`
literal so an unquoted `None` is the four-letter string (two cases); a
whitespace-only or empty label declares nothing (two cases); a declared label
prints as written, with padding stripped (four cases). The `why` strings state
those rules in product terms rather than in oracle terms, which is what rule
6a asks for. The thirteenth, `label: false` to `"False"`, is transcribed from
output, and it is the one case explicitly marked `agreed_but_suspect` with a
`why` saying it is pinned as behaviour and NOT as a correct value.

**What I cannot discriminate (rule 10).** Nothing in the artifacts tells me
whether the author wrote those twelve values from the rules and then ran the
corroboration, or read them off block 1's probe, which prints exactly those
values and sits FIRST in the `## Commands` section. Both histories produce
this file. What the artifacts do establish is the durable property: the values
are pinned in committed data with product reasons, nothing regenerates them,
and the corroboration retires cleanly at WP-6.1 leaving the tests still saying
something. On the narrower question the brief asks, whether "pin the correct
value" is meaningful here rather than equals-Python wearing a different hat, I
answer yes, with that caveat named rather than buried.

**One value has generated provenance inside the hand-authored file.** The
padded `ARTICLE` case was produced by WP-5.1f's Python generator and carried
forward. WP-5.1g kept it and recorded its limitation in its `why`. Its
spec-authored twin, the `Dispatch` case, is the one that carries the
discrimination, so the inherited case is decoration on a load-bearing pair
rather than load-bearing itself.

**The roster fixture is a different animal and should stay that way.**
`model_shared_roster_expected.json` still carries a `python` field, is still
generated by a committed command, and
`the_roster_test_matches_python_on_the_committed_cases` is literally a
matches-Python assertion. That is CORRECT under rule 6a: the roster defects are
class A, port-fidelity gaps where Python is right, and class A dies at WP-6.1.
Rule 6a's "pin the correct string, never equals-Python" binds class B. Recorded
so nobody later "fixes" the roster fixture into the label fixture's shape and
loses the distinction.

## 7. The sweep's boundary

The greps reproduce exactly as claimed at their own commits: **7 lines at
`160c39e`**, **8 lines at `3b9cbcb`** (the eighth being WP-5.1g's
`.filter(|value| !value.is_null())`). Both evidence tables account for every
line returned, with two rows spanning two lines each, so 5 rows cover 7 lines
and 6 rows cover 8. The counts are derived from the enumerations rather than
carried beside them.

WP-5.1g's statement of what the boundary EXCLUDES is the part the brief asked
me to check, and it is present and accurate: `shared.rs` only; whitespace and
null only; nothing about other `py_*` helpers on other axes; nothing about the
roughly 180 `trim`/`split_whitespace` sites elsewhere under `mag/src/`. I
confirmed the last of those is a disclaimer rather than a hidden claim, and
that WP-5.1f records the same exclusion.

Where the boundary claim overreaches is the pattern itself, not its arithmetic:
see finding F2.

## 8. What is and is not proven

**PROVEN**

- `is_name_roster`'s strip and split, and `content_label`'s strip, agree with
  their Python originals on the committed cases, and the cases discriminate.
  Shown to discriminate by mutation: the pre-fix body is killed by 2 of 3
  roster cases and 7 of 13 label cases, and fixing one half of the roster
  defect leaves the other half's case red (`zz_verifier_roster.rs`).
- `is_python_space` equals Python `str.isspace` over all 1,114,112 codepoints.
  Shown to discriminate by P1 and P2: dropping one member or adding one
  non-member turns two tests red.
- A null `label:` in all four YAML spellings now behaves as an absent key.
  Shown to discriminate by block 4, which names all four under the pre-fix
  body, and by P8, which shows the guard-dependence assertion is tied to all
  four rather than to the count.
- Every case must declare `status` and a non-empty `why`. Shown to
  discriminate by P5, P6 and P7.
- The four field separators behave identically in both engines through both
  functions, so the fixtures' U+001E sample is representative.
- Zero occurrences of U+001C-U+001F and zero null or boolean `label:` values in
  the corpus, at both the tracked and the on-disk scope.
- The label fixture cannot be regenerated by anything in the tree.

**NOT PROVEN**

- That production is unaffected. It is unaffected only because the corpus
  contains no triggering input; WP-5.1f says this plainly and I confirm it.
  Nothing here discriminates "correct in production" from "correct on fixtures
  and production never exercises this". Owner: nobody, and nobody is needed,
  since the class B defect's point is that the corpus accident is not a
  property of the system.
- That the thirteen label cases are the right thirteen. `content_label` accepts
  inputs nobody has enumerated. WP-5.1g discloses this; see F6 for two
  instances I measured inside the disclosed gap. Owner: unowned, escalated in
  section 9.
- That the tests exercise the SHIPPED function. Both binaries `#[path]`-include
  `shared.rs`, so they compile a second copy inside the test crate. See F5 for
  why this is unavoidable here and what it therefore does not show.
- That the author derived the twelve spec-derivable values without looking at
  Python's printed output first. See section 6.
- Anything about `ui`, `clamp_roster`, the other `py_*` helpers on non-
  whitespace axes, or the roughly 180 `trim`/`split_whitespace` sites under
  `mag/src/`. Owner: a whole-tree audit WP; unassigned.

## 9. Findings, and why they are corrections rather than rejections

**F1. A test total attributed to the wrong commit (WP-5.1g).** Measured at
`160c39e`, by summing the per-binary `test result` lines: **188 tests across 20
binaries**, and the 20 binaries are confirmed against 20 `Running` lines, with
no doc-test section. WP-5.1f's "188 tests across 20 binaries" is therefore
RIGHT. WP-5.1g's "At this WP's base `160c39e` it was 192 across 20" is WRONG by
four: 192 is `160c39e` PLUS this WP's own `+4`, that is, its pre-rebase working
tree, not its base. At `3b9cbcb` I measure **207 tests across 22 binaries**,
which matches WP-5.1g's headline figure exactly, and `cargo test` exits 0 with
`fmt` and `clippy --all-targets -- -D warnings` clean at both commits. The
error sits in the paragraph that states "a total is a measurement with a
timestamp, and the timestamp is the commit", which is the lesson correctly
drawn and then misapplied one line later.

**F2. The sweep's pattern is narrower than the caption's scope words.** The
arithmetic is sound, 7 lines and 8 lines as claimed, but the captions say
"Every whitespace-handling site" and "Every whitespace-handling and
null-handling site in `mag/src/model/shared.rs`", and an independent sweep of
the file finds two in-scope sites the pattern cannot match:

- `mag/src/model/shared.rs:214`, `Value::Null => "None".to_string()` inside
  `py_str`. This is null handling, and it is the exact mechanism of the defect
  WP-5.1g fixes. The pattern's `is_null` term does not match `Value::Null`.
  WP-5.1f's pattern lacks `is_null` altogether, so it misses this too.
- `mag/src/model/shared.rs:54`, `character == ' '` inside `printable()`, a
  whitespace-character test in the `py_repr` path.

Both are CORRECT (Python's `str(None)` is indeed `"None"`, and a space is
indeed printable to Python's `repr`), so no defect hides behind the gap. What
is damaged is the boundary's purpose, stated in the plan as "the next reader
does not need to re-open the file": a reader trusting "eight lines and only
eight" would not learn that `py_str`'s Null arm exists, which is the one site
they would most want named. This is rule 12's caption-drift class, where the
command ran, the output was accurate, and the caption was the false claim.

I considered REJECTING WP-5.1g on this and did not, and the reason is recorded
here rather than left to inference because rule 3d says a load-bearing reason
must live where it is re-read. Three things weigh against rejection: the two
missed sites are correct, so nothing ships wrong; `py_str`'s Null arm is
discussed at length in the SAME document's prose, so the knowledge is not lost,
only mis-indexed; and the sweep's operative claim, that the two functions under
audit are fully pinned to the two primitives, is true and independently
confirmed. The correction is one grep term and two table rows.

**F3. "20 distinct values" is 20 distinct LINES.** Parsing each of the 548
matched lines through `yaml.safe_load` gives **18 distinct values**:
`EDITORIAL` appears both quoted and unquoted, as does
`EDITORIAL: ORIGINAL EDITOR TEXT`. The recorded command (`sort -u | wc -l` over
raw lines) is honest about what it counts; the prose word "values" is not. The
load-bearing counts are unaffected and exact: 548 keys, 0 null, 0 boolean,
re-derived by parsing rather than by grep.

**F4. WP-5.1f's evidence is now destructive on replay.** WP-5.1f.md's
`## Commands` block 2 still redirects a Python generator into
`mag/tests/model_shared_label_expected.json`. Replayed at `3b9cbcb`, as a later
verifier following rule 12 would replay it, it silently overwrites WP-5.1g's
hand-authored 13-case fixture with the superseded 5-case Python-generated one:

```
git status: M mag/tests/model_shared_label_expected.json
5 cases, keys ['content_mode','frontmatter','known_divergence','name','python']
cargo test --test model_shared_label: 7 tests panic at model_shared_label.rs:31
```

Demonstrated and restored. This is the fixture's Python basis coming back
through the door WP-5.1g closed, and it is the sharpest argument for the
hand-authoring decision rather than against it. WP-5.1f.md is a terminal
document that nobody re-reads, which is precisely why the note has to be in it.
Requested correction: one line in WP-5.1f.md's block 2 caption saying the block
is superseded by WP-5.1g and must not be run at or after `3b9cbcb`. I did not
make the edit: WP-5.1f.md is not a verifier's to write.

**F5. The `#[path]` include is undisclosed, and unavoidable.** Both binaries
open with `#[path = "../src/model/shared.rs"] mod shared;`, which rule 12's
first clause says a WP must declare, saying what it has therefore not shown.
Neither evidence file mentions it. The mitigation is decisive rather than
partial: `mag` has **no `lib.rs`**, it is a binary-only crate, so there is no
ordinary import path for an integration test to use, and 15 of the repository's
test files already do this. The tests also need `py_str`, `py_strip` and
`is_python_space`, which are `pub(crate)`. So this is the repository's
established convention and not a seam routed around. What it does not show:
that the BINARY's copy behaves this way, only that the same source compiled
into a test crate does. `shared.rs` contains no `cfg` attributes, so the two
compilations cannot diverge. Disclosure owed, no defect.

Revision 61, which landed onto this verification's base while it was in
flight, sharpens the form to "a `#[path]` include proves something about the
FILE, not about the MODULE", and names the specific hazard: a module nothing
declares still compiles and tests clean, so the gate never checks it. I
therefore checked the declaration chain rather than assuming it, which is the
check that hazard calls for:

```
mag/src/main.rs:11   mod model;
mag/src/model.rs:4   pub mod shared;
```

`shared.rs` IS in the crate's module tree, so `cargo build`, `clippy -D
warnings` and `cargo test` do check the module and not only the file, and the
production consumer at `mag/src/typeset/content.rs:365` and `:535` reaches both
functions through that tree. WP-5.3b-ii's `inspect` case does not reproduce
here. That closes the part of the `#[path]` hazard that could have mattered;
what remains unshown is the narrow residue above, which no mechanism available
in a binary-only crate can show.

**Revision 62 then landed and retires this finding.** It decides the style for
a binary-only crate, finds the `#[path]` pattern is FORCED rather than chosen
(no `[lib]`, no `lib.rs`, 51 instances across 16 of 22 test files), and draws
the line prospectively: a property of the MODULE TREE is asserted in-crate, a
property of an ALGORITHM may be asserted through `#[path]`. Both binaries here
assert algorithm properties, whitespace semantics and label semantics, so they
sit on the sanctioned side of that line and the disclosure sentence is no
longer owed. F5 stands only as the record that the question was asked and
answered by measurement rather than assumed away. The independent check above,
that the module tree declares `shared` from the crate root, is the part that
remains load-bearing.

**F6. Two live divergences confirmed inside WP-5.1g's disclosed gap.** The
residual says `content_label` has inputs nobody enumerated, naming sequences,
mappings, floats and dates. I probed them on both legs:

| frontmatter | Python | Rust |
|---|---|---|
| `label: []` | `'()'` | `"[]"` |
| `label: {}` | `'{}'` | `"{}"` |
| `label: 1.5` | `'1.5'` | `"1.5"` |
| `label: 2026-01-01` | `'2026-01-01'` (a `datetime.date`) | `"2026-01-01"` (a string) |
| `label: !!null` | `None`, so `ARTICLE` | **serde_yaml PARSE ERROR** |
| `label: !!null ''` | `None`, so `ARTICLE` | **serde_yaml PARSE ERROR** |
| `label: !!null 'null'` | `ARTICLE` | `ARTICLE` |

`label: []` is a genuine output divergence, `()` against `[]`, arising in
`py_str`'s `Sequence` arm rather than in anything these WPs touched. The two
`!!null` spellings diverge at PARSE level: PyYAML resolves the standard null
tag, `serde_yaml` refuses the document. Both are outside both WPs' Owns and
outside the boundary either claims. They confirm the residual was worth writing
rather than contradicting anything, and they are recorded here because the
residual has no owner. Escalated: `py_str`'s container arms need a WP.

None of F1 to F6 is a code defect. F1 and F3 are citation corrections, F2 is a
caption-scope correction, F4 is a replay hazard in a superseded document, F5 is
a disclosure omission with an unavoidable cause, and F6 is the confirmation of
a disclosed residual.

## Metrics

Measured at `160c39e`: 188 tests / 20 binaries; 7 grep lines; 1,433 tracked
files (1,241 editions, 192 library) with 0 occurrences of U+001C-U+001F; 1,874
on-disk files (1,682 editions, 192 library) with 0 occurrences; 548 `label:`
keys over 20 distinct lines and 18 distinct parsed values, 0 null, 0 boolean;
195 U+2022 occurrences across 8 files; Python `isspace` 29, Rust
`is_whitespace` 25, difference exactly `[0x1C,0x1D,0x1E,0x1F]`, std-only set
empty; `strip`/`split` versus `isspace` disagreements: 0 over 1,114,112
codepoints.

Measured at `3b9cbcb`: 207 tests / 22 binaries; 8 grep lines; 13 label cases,
0 Python disagreements; 6 mutants evaluated against 13 + 3 cases; 9 fixture
perturbations, 9 red.

Measured on this verification's rebased tree, parent `aa8bdac`: 221 tests / 23
binaries, `cargo test` exit 0, `fmt` and `clippy --all-targets -- -D warnings`
clean. The total moved 188 to 207 to 221 across the three commits without any
file under test changing, which is the timestamp discipline rather than a
discrepancy: `git log 3b9cbcb..aa8bdac -- mag/src/model/shared.rs
mag/tests/model_shared_*` is EMPTY, so nothing in the range owed
re-verification.

Host: 52 GiB free at time of measurement, 95% used. No I/O failure was
encountered; both worktrees built and tested cleanly.

## Verdicts

No parity verdict is produced by either WP and none by this verification.
No `baseline.json` or `parity.yaml` was read or written.

## Residuals

- F1, F2, F3 are corrections owed to `WP-5.1g.md` (and F2 partly to
  `WP-5.1f.md`). They are the authors' files, not a verifier's.
- F4 needs a superseded-block note in `WP-5.1f.md` before the next verifier
  replays it.
- F6 needs an owner for `py_str`'s container and tagged-scalar arms.
- Rule 10c's second limb, an expected value equal to the INPUT, is unswept
  across the plan's other fixture sets. This verification swept only these two.

## Status

done
