# WP-5.3b-i verification

## Verdict

**REJECTED.** One code defect, one rule 9 defect, one hermeticity defect.

The Unicode work in this WP is the strongest oracle evidence the plan has
received and none of it is in question. The rejection is on the OTHER half of
the WP, the line reconstruction, where the shipped join rule is not the rule
the evidence describes: it subtracts two quantities denominated in different
units. The evidence records the join as non-discriminating and attributes that
to the corpus. Measured, the corpus is not the reason. The rule is nearly inert
by construction, and its first decision on edition 010 is demonstrably wrong.

Commit under verification: `26391ab`. Verified from a fresh worktree at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/verify-53bi`.

## Owns check

`git show --stat 26391ab` lists exactly the six files the WP claims and nothing
else: `mag/src/critic.rs`, `mag/src/critic/text.rs`, `mag/src/parity.rs`,
`mag/tests/critic_text.rs`, `mag/tests/critic_text_islower_expected.txt`,
`meta/verification/evidence/WP-5.3b-i.md`. Clean.

## Defect 1: the join rule subtracts qc units from qo units

`mag/src/critic/text.rs:85`:

    fn separator(previous: &Show, next: &Show) -> &'static str {
        let gap = next.x - (previous.x + previous.width);

`Show.x` and `Show.y` are `m[4]` and `m[5]`, and `mag/src/parity/streams.rs:432`
builds that matrix as `m: trm.map(qc)`, so they are in `qc` units of 0.01 pt.
`Show.size` is `qc(size_eff)`, same unit, so `threshold` is correct.

`Show.width` is derived in `shows()` from `offs`, and
`mag/src/parity/streams.rs:423` builds those with `qo`, which is
`v / GLYPH_QUANTUM` where `GLYPH_QUANTUM = GLYPH_DRIFT_PT / 8.0 =
9.1552734375e-05`. One qc unit is 109.2267 qo units, so `width` enters the
subtraction inflated by that factor.

**Measured, not asserted.** Instrumenting `separator` to print its operands and
tally its branches over all 56 pages of 010:

| | spaces | empties | total |
|---|---|---|---|
| shipped | **18** | 462 | 480 |
| width converted to qc | **236** | 244 | 480 |

The shipped rule fires 13 times less often than the rule the evidence
describes. The very first decision, read back in real points:

    prev.x 44.00 pt, next.x 91.00 pt, size 23.00 pt, threshold 5.75 pt
    prev.width  = 331606 qo = 30.3594 pt
    TRUE gap    = 91.00 - (44.00 + 30.3594) = 16.6406 pt  >  5.75 pt  -> SPACE
    shipped gap = (9100 - (4400 + 331606)) / 100 = -3269.06 pt         -> EMPTY

A 16.64 pt word gap against a 5.75 pt threshold is not a marginal call, and the
code returns the wrong answer. With the units reconciled the 010 test still
passes, which is exactly why nothing caught this.

**This also falsifies an attribution in the evidence.** Under "Not proven" the
WP writes that the join "does not discriminate on 010" and that "the rule is
chosen because it is PRINCIPLED, not because this corpus can tell." The first
clause is true and the second is not: the shipped rule is not the principled
rule. Recording a rule as principled-but-unexercised, when it is in fact
misimplemented and nearly inert, is the failure rule 10 exists to prevent. The
label was applied to the corpus when it belonged to the code.

Note the defect predates the quantum rework rather than being introduced by it.
At `a0714c3` the factor was exactly 100 rather than 109.2267. It was wrong then
too. This matters for defect 2.

## Defect 2: rule 9, the recorded base is five commits stale

`## Base` records `a0714c3 (plan revision 33)` and the metrics section states
the figures carry "WP-0.2i's per-glyph offsets as they stand at a0714c3."

    git log -1 --format=%h 26391ab^   ->  be6ec61
    git rev-list --count a0714c3..26391ab^  ->  5

`a0714c3` is an ancestor, so nothing was clobbered, but it is not the base the
figures were measured against. The five intervening commits include the one
that reworked the quantum:

    a0714c3:  GLYPH_QUANTUM = 0.0001
    26391ab:  GLYPH_QUANTUM = GLYPH_DRIFT_PT / 8.0  = 9.1552734375e-05

This is not a cosmetic sha slip. `GLYPH_QUANTUM` denominates `offs`, `offs`
denominates `width`, and `width` is the operand defect 1 turns on. The recorded
configuration names the one constant whose value the evidence gets wrong, and
names it at the wrong value. Rule 9 asks that a number carry its configuration
precisely so a reader can tell which arithmetic produced it.

## Defect 3: the test is not hermetic and did not test this tree

`mag/tests/critic_text.rs:74`:

    fn reader_pdf() -> PathBuf {
        PathBuf::from(
            "/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en/reader.pdf",
        )
    }

Run from an isolated worktree, the test printed
`MODE: full, tracing /Users/franguijarro/code/magazine/...`, so it traced the
MAIN tree's PDF while exercising the worktree's code. The corpus is therefore
not part of the tree under verification, and on any other machine or checkout
path the test takes the `SKIPPED` branch and proves nothing.

This is the only test in the repository that hard-codes an absolute path. All
six siblings take their input from an environment variable
(`MAG_MODEL_ARTICLES`, `MAG_IMPOSE_READER`, `MAG_MANIFEST_ROOT`,
`MAG_PREFLIGHT_SPEC`, `MAG_COVER_SVG_OUT`). The rule 2b mode announcement is
present and correct, and it is what made this visible, but announcing the mode
does not make the path portable.

## What verified clean

Everything below reproduced exactly. The oracle half of this WP is solid.

**The recorded command runs as recorded.** Extracted block 1 from
`## Commands` verbatim, without retyping, and ran it. It regenerates
`mag/tests/critic_text_islower_expected.txt` byte-identically to the committed
file. Python prints 2544 and the file holds 2543 newline-separated entries,
consistent with no trailing newline. This is the class that rejected three
earlier WPs, and it is closed here.

**The Unicode figures are exact.** Independently, not through the WP's own
code: `uv run python` reports 3.12.11 on Unicode 15.0.0 and 2,544 lowercase
codepoints; a standalone rustc 1.96.0 probe reports 2,595. The set difference is
1 Python-only (U+0295) and 52 Rust-only, 53 disagreeing. All five named
Rust-only codepoints confirmed, and all 22 of U+10D70 to U+10D85 are in the
Rust-only set. Every figure in the evidence matches.

**The self-invalidating test is sound.** All four codepoints it lists genuinely
have `char::is_lowercase` disagreeing with Python, confirmed against my own
independently computed set, so the `assert_ne!` guard passes today and will fire
if a future rustc ever agrees. It does what it claims.

**Every discrimination probe reproduced.**

| probe | change | claimed | observed |
|---|---|---|---|
| C | delete U+0295 from the oracle | FAIL | FAIL, `critic_text.rs:51` lowercase codepoint count |
| D | `SAME_LINE_TOLERANCE` 100 to 1200 | FAIL 1111 vs 1117 | FAIL, exactly those numbers |
| E | `SAME_LINE_TOLERANCE` to 0 | PASS | PASS, tolerance proven one-directionally only |
| B | `py_islower` to `char::is_lowercase` | PASS | PASS, pin unexercised by 010 |
| F | unconditional space join | PASS | PASS |
| F' | unconditional empty join (mine) | not run | PASS |

Probe F' is additional. Both extremes pass, so the rule 10 label is correct on
both sides rather than one, and the field is more thoroughly non-discriminating
than claimed. It is also the first hint of defect 1.

`SAME_LINE_TOLERANCE = 100` is genuinely 1 pt, since `y` is a `qc` value. The
evidence's parenthetical is right. The unit error is confined to `width`.

**The figures hold at current HEAD.** `git diff 26391ab 6a53a12` over all six
owned files is empty, and no commit since touches `mag/src/parity`,
`mag/src/critic` or `mag/tests/critic_text.rs`. The measurements are current.

**The inheritance lists are accurate.** WP-5.3b-ii: `page_text`,
`body_text_lines` and `trace_text` all exist as `pub(crate)`, and `metrics.rs`
exposes exactly `decode_rgb`, `thumbnail`, `round_half_even`, `round_places`,
`ordered_map` and `worker_count`, with no `getbbox`. One caution for the
successor: `luma601` does exist at `metrics.rs:541` as `pub(crate)`, so a
reader skimming for grayscale will find something. The evidence is right that
it is not the PIL-exact helper `_inspect_page` needs, and the open luma
discrepancy between `art.rs` and `metrics.rs` is still unresolved elsewhere.

WP-5.3b-iii: the five text-derived fields and their issue sites check out
against `render_critic.py`, all eleven cited lines being real sites.
"Only `body_text_lines` differs from pypdf" is correct, because
`text_characters` is not one of the five gating fields. Provenance caution:
this WP measured emptiness, `body_text_lines` and `text_characters` itself, but
`text_order_matches` and `standalone_punctuation_lines` are inherited from
WP-5.3d, and the residual reads as though all five were measured here.

## A plan correction this verification turned up

The plan says "ten issue sites" in three places (lines 906, 3318, 3449) while
its own enumeration at line 906 lists eleven line references:
`text_order_matches` :152 :176 :198, `blank` :291 :452 :476, `ink_free` :299
:460 :484, `standalone_punctuation_lines` :309, `body_text_lines` :380. That is
3 + 3 + 3 + 1 + 1 = 11. I read all eleven lines in `render_critic.py` and every
one is a genuine site. **The evidence's "eleven" is right and the plan's "ten"
is an arithmetic slip.** WP-5.3c is briefed off this count and should get the
corrected one.

## Critique: `py_islower` placement

The evidence puts `py_islower` and its 671-range table in
`mag/src/critic/text.rs` rather than `mag/src/model/shared.rs`, reasoning that
shared.rs is not this WP's Owns, and records lifting it as a residual. **That
judgment is correct and I would not hold the WP for it**, but the evidence
understates its own safety, so here is the measured position.

shared.rs owns nine `py_*` helpers plus `is_python_space`. `py_islower` is the
only one living outside it, so the placement is a real ownership inconsistency.

The mechanism, though, does cover the dangerous case. `mag/tests/rust_helpers.rs`
is an exemption list keyed on (module, name) with duplicates detected by
(name, signature) and by identical body. I tested it rather than reading it:
adding a rival `py_islower` to shared.rs with a DIFFERENT body but the same
signature fails `no_helper_is_defined_in_two_modules` with

    same name and signature: ["py_islower in [("critic/text.rs", "py_islower"),
     ("model/shared.rs", "py_islower")]"]

So two divergent copies of this helper cannot land silently, which is the
failure mode the duplicated-helper rule exists for. What the audit does not do
is assert that a Python-builtin helper belongs in shared.rs at all; it is
reactive to duplication, not to misplacement. A future copy under a different
name and a different body would still escape both tests, which is a known
general weakness of the audit and not specific to this WP.

Net: leave it where it is, keep the residual, and let whoever next owns
shared.rs lift it. It is tidiness with a mechanical backstop, not exposure.

## Required to accept

1. Fix the unit mismatch in `separator`. Convert `width` into `qc` units at the
   point it is built in `shows()`, or carry both in `qo` and convert `x` and
   `size`. Either way, one unit in the expression.
2. Re-measure the join with the fix in place and re-label it. It may well
   remain non-discriminating on 010 for emptiness and `body_text_lines`, as
   probes F and F' show, but then that is a measured statement about a rule
   that does what it says, and `text_characters` will move.
3. Correct `## Base` to `be6ec61` and restate the `GLYPH_QUANTUM` value the
   figures were taken under.
4. Give the corpus path an environment variable like every sibling test, so the
   test exercises the tree it is run from.
5. Re-confirm the 010 figures after 1, since the join feeds `page_text`.

The oracle work in sections "The Unicode obligation" and the whole-plane sweep
needs no rework and should be carried forward unchanged.

## Commands

    cargo test --manifest-path mag/Cargo.toml --test critic_text
    cargo test --manifest-path mag/Cargo.toml --test rust_helpers

    # unit inspection, the operands of the join
    grep -n "m: trm.map(qc)\|qo(v \* base" mag/src/parity/streams.rs
    sed -n '85,93p' mag/src/critic/text.rs

    # base and quantum at the claimed base versus the actual parent
    git log -1 --format=%h 26391ab^
    git show a0714c3:mag/src/parity/streams.rs | grep -n GLYPH_QUANTUM
    git show 26391ab:mag/src/parity/streams.rs | grep -n GLYPH_QUANTUM

    # the figures still hold at HEAD
    git diff --stat 26391ab 6a53a12 -- mag/src/critic.rs mag/src/critic/text.rs \
      mag/src/parity.rs mag/tests/critic_text.rs \
      mag/tests/critic_text_islower_expected.txt \
      meta/verification/evidence/WP-5.3b-i.md

The branch tallies in defect 1 came from a temporary atomic counter in
`separator`, and the corrected-unit row from scaling `span` by
`GLYPH_QUANTUM * 100.0` in `shows()`. Both were reverted; the worktree is clean
against `26391ab` and all five tests pass.

## Tool versions

rustc 1.96.0, lopdf 0.45.0, `uv run python` 3.12.11 on Unicode 15.0.0.
