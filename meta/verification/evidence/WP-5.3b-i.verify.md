# WP-5.3b-i verification (second pass, rework)

## Verdict

**ACCEPTED.** The rejection's defect is gone, measured rather than described.

Commit under verification: `80b7b62`, the rework of `26391ab`, which this
verifier's first pass rejected at `3f45d31`. Verified from a fresh worktree at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp53bi3`, created with
`git worktree add ... 80b7b62`. Every figure below was produced in that
worktree against a byte-identical copy of the corpus placed inside it, not
against the main tree.

Five findings are recorded under `## Findings`, none of them a rejection
ground, and one of them is a correction to my own first pass.

## What was replayed, and how

Rule 12's third class says a demonstration must run through the artifact that
will be replayed. The `## Commands` blocks were extracted from
`meta/verification/evidence/WP-5.3b-i.md` PROGRAMMATICALLY and written to
`/tmp/vcmd/block{1..7}.sh`, then executed with `bash`. Nothing was retyped.

    uv run python - <<'PY'
    import re, pathlib, os
    src = pathlib.Path('meta/verification/evidence/WP-5.3b-i.md').read_text()
    sec = src.split('## Commands',1)[1].split('\n## ',1)[0]
    lines = sec.split('\n')
    blocks, cur = [], []
    for l in lines:
        if l.startswith('    '):
            cur.append(l[4:])
        else:
            if cur: blocks.append('\n'.join(cur)); cur=[]
    if cur: blocks.append('\n'.join(cur))
    os.makedirs('/tmp/vcmd', exist_ok=True)
    for i,b in enumerate(blocks,1):
        p = f'/tmp/vcmd/block{i}.sh'
        pathlib.Path(p).write_text(b+'\n')
        print(f'=== BLOCK {i} -> {p}')
        print(b)
    PY

Seven blocks. Six run in my worktree and reproduce; block 4 is finding 1.

The corpus was placed inside the worktree so the relative-path blocks resolve
against my own checkout:

    mkdir -p editions/010/render-2026-09-14T01-47-59/en
    cp /Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en/reader.pdf \
       editions/010/render-2026-09-14T01-47-59/en/reader.pdf
    shasum -a 256 editions/010/render-2026-09-14T01-47-59/en/reader.pdf \
      /Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en/reader.pdf

Both `7b39d11271e335e4928d403a5bfcf6eeca27b6757d5d26a0822f0121527f9156`, so the
main tree and my worktree are reading the same bytes and the cross-tree hazard
of finding 1 changes no number here.

## Claim 1: the fix, and the re-export

Confirmed by reading the diff, not the prose. `git show 80b7b62 -- mag/src/critic/text.rs mag/src/parity.rs`:

    -                    (last[0] - first[0]) * count as i64 / (count as i64 - 1)
    +                    let span = (last[0] - first[0]) * count as i64 / (count as i64 - 1);
    +                    (span as f64 * GLYPH_QUANTUM * 100.0).round() as i64

    -pub(crate) use streams::{Element, Face as TextFace};
    +pub(crate) use streams::{Element, Face as TextFace, GLYPH_QUANTUM};

The conversion is at the point the width is BUILT, in `shows()`, not at the
subtraction, so `Show.width` is qc everywhere it is read and `separator` is
left with one unit in the expression. `GLYPH_QUANTUM` is pt per qo unit and
`* 100.0` is qc per pt, so `qo -> pt -> qc` is the right composition. Block 6,
run as recorded:

    GLYPH_QUANTUM pt = 9.1552734375e-05
    qo units per qc unit = 109.22666666666667

`streams.rs:34` `qc`, `:40` `GLYPH_QUANTUM = GLYPH_DRIFT_PT / 8.0`, `:42` `qo`,
`:432` `m: trm.map(qc)` all read as the evidence describes.

## Claim 2: the counter, both rules

Reproduced EXACTLY, with my own instrumentation rather than the worker's. I
added two `AtomicUsize` counters to `separator` in `mag/src/critic/text.rs` and
a scratch integration test `mag/tests/vscratch.rs` that traces all 56 pages
once and prints the tallies and the per-page fields. Both were removed
afterwards (`git show HEAD:mag/src/critic/text.rs > mag/src/critic/text.rs`,
`mv mag/tests/vscratch.rs /tmp/vcmd/`), and `git status --porcelain` is empty.

| rule | spaces | empties | total |
|---|---|---|---|
| broken (conversion dropped) | **9** | **231** | 240 |
| fixed (as committed) | **118** | **122** | 240 |

Identical denominator, so the two rows are comparable, which is what the
evidence claims and it holds. The fix moves 109 of 240 joins from empty to
space.

## Claim 3: the three fields, re-measured against pypdf

Block 2 run as recorded, from my worktree, against my worktree's copy:

    pages 56
    empty pages [2, 10, 30, 35, 45, 54, 55]
    total body 1110
    page4 body 9   page36 body 3

Tracer against that reference, each row derived by comparing 56 pairs:

| field | broken rule | fixed rule |
|---|---|---|
| text-emptiness | 56 of 56 | **56 of 56** |
| `body_text_lines` | 49 of 56 | **49 of 56** |
| `text_characters` | 16 of 56 | **43 of 56** |

Every one of the six cells matches the evidence. The emptiness partition is
identical on both sides, `[2, 10, 30, 35, 45, 54, 55]`, so the 56 of 56 is a
reproduction of a non-trivial 7/49 partition and not a constant, which is the
rule 10 distinction.

**Rule 9, count derived from the enumeration rather than carried beside it.**
The seven differing `body_text_lines` pages are exactly
`[4, 11, 31, 36, 40, 46, 50]`, and the delta on each is `+1`, so
`7 x (+1) = +7` and `1117 - 1110 = 7` accounts for all of it with nothing left
over. I added the list up rather than accepting the total. Same seven pages
under the broken rule, so the fix genuinely leaves this field untouched.

The headline-merge mechanism, block 7 as recorded:

    4 'Government Rails Site HitHours After CVE Patch'
    36 'The third era of AI softwaredevelopment'

and the tracer's own lines on the same two pages, from my scratch dump:

    RS 4 "Government Rails Site Hit"
    RS 4 "Hours After CVE Patch"
    RS 36 "The third era of AI software"
    RS 36 "development"

The tracer splits what pypdf merges, and every word inside each tracer line is
correctly spaced. This is the qualitative check the numbers cannot give: the
fixed rule produces RIGHT spacing, not merely DIFFERENT spacing.

## Claim 4: the two new unit tests

`a_real_word_gap_yields_a_space` fails with exactly the string claimed when the
unit bug is restored:

    thread 'a_real_word_gap_yields_a_space' panicked at tests/critic_text.rs:177:5:
    assertion `left == right` failed: a 10.7 pt gap against a 5.75 pt threshold must yield a space
      left: "GovernmentRails"
     right: "Government Rails"

Arithmetic checked by hand: first show at x = 91 pt, 10 glyphs spanning 120 pt,
so `span = 120 * 10 / 9 = 133.33 pt`, right edge 224.33 pt; second show at
235 pt; gap 10.67 pt against `23 * 0.25 = 5.75 pt`. The fixture's numbers are
what the test's message says they are.

`a_kerned_join_yields_no_space` exercises the other branch: `soft` at 91 pt
spanning 40 pt over 4 glyphs gives `span = 53.33 pt` and a right edge of
144.33 pt against a next show at 137.5 pt, so the gap is -6.83 pt and the else
branch is taken. It FAILS under the unconditional-space mutation and PASSES
under the unit bug, so it discriminates against one extreme but is not a
regression test for the defect; only the first test is. The evidence claims
exactly that and no more.

## Claim 5: the central claim, all three mutations performed

This is the claim the WP's argument rests on, so I made all three mutations and
ran the committed corpus test under each.

| mutation | `reconstructs_edition_010_text` | the two unit tests |
|---|---|---|
| unit bug restored (conversion dropped) | **ok** | `a_real_word_gap` FAILED |
| `separator` returns `" "` unconditionally | **ok** | `a_kerned_join` FAILED |
| `separator` returns `""` unconditionally | **ok** | `a_real_word_gap` FAILED |

**The claim is TRUE.** The corpus test passes under the bug, under an
unconditional space and under an unconditional empty. It cannot see the join
rule at all, exactly as the evidence says, and the two unit tests between them
catch all three mutations. This is the strongest thing in the WP and it
survives independent reproduction.

**Rule 10's second half, applied.** Both extremes pass, so the question is
whether the code under test does anything at all. Measured answer: it does.
109 of 240 joins flip between the extremes, and `text_characters` changes on 47
of 56 pages. The code is not inert; the CORPUS is insensitive on the two
decision-relevant fields. That distinction is the whole content of the
restatement and it is measured, not asserted.

**Rule 11, applied.** The WP asserts a mechanism: a 109.2267x inflation of
`width` suppresses spaces. I tested it by removing the supposed cause and
measuring whether the effect goes. It goes: 9 spaces with the conversion
dropped, 118 with it restored, and the first decision flips from empty to
space. Unusually for this plan's rule-11 history, the defect was real AND the
explanation was right.

## Claim 6: the env gate and the assert

The hard-coded absolute path at `mag/tests/critic_text.rs:74` is gone,
replaced by `MAG_CRITIC_READER_PDF`. All three modes exercised in my worktree:

    # skipped
    $ bash /tmp/vcmd/block3.sh
    MODE: skipped, MAG_CRITIC_READER_PDF unset
    test result: ok. 5 passed

    # full, against MY checkout
    $ MAG_CRITIC_READER_PDF=$PWD/editions/010/render-2026-09-14T01-47-59/en/reader.pdf \
        cargo test --manifest-path mag/Cargo.toml --test critic_text -- --nocapture
    MODE: full, tracing /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp53bi3/editions/...
    test result: ok. 5 passed

    # set but missing: ASSERTS rather than skipping
    $ MAG_CRITIC_READER_PDF=/tmp/definitely-not-here/reader.pdf \
        cargo test --manifest-path mag/Cargo.toml --test critic_text reconstructs -- --nocapture
    MAG_CRITIC_READER_PDF set but missing: /tmp/definitely-not-here/reader.pdf
    test result: FAILED. 0 passed; 1 failed

The assert fires. A typo cannot pass silently. Rule 12's third class, which
this WP's own test was the repo's only instance of, is closed IN THE TEST.

## The ancestry correction: the worker is right, and the branch was broken

    $ git merge-base --is-ancestor 26391ab a537a24 && echo YES
    YES

`26391ab` IS an ancestor of `a537a24`. My first pass did not check this and
implied the rejection put the code out of reach; it did not. **The branch
carried a width computation known to be wrong from `26391ab` until `80b7b62`
landed**, and in that window every consumer of `mag/src/critic/text.rs` would
have been building on a join rule that suppressed 109 of 120 spaces it should
have inserted. Nothing consumed it in that window (WP-5.3b-ii and -iii are not
started), so no downstream number is contaminated, but the exposure was real
and stating it plainly is the point. Plan revision 41 (`74c8aae`) has already
folded this into the protocol as rule 3b, requiring a rejection to say whether
its defect is LIVE ON THE BRANCH. That rule exists because of this WP.

## Findings

**1. The recorded full-mode command still reads the MAIN tree.** Block 4, as
recorded, is

    MAG_CRITIC_READER_PDF=/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en/reader.pdf \
      cargo test --manifest-path mag/Cargo.toml --test critic_text -- --nocapture

Run verbatim from my worktree it printed
`MODE: full, tracing /Users/franguijarro/code/magazine/...`, so it exercised my
checkout's CODE against the main tree's CORPUS. That is the same cross-tree
shape as the rejected hard-coded path, moved from the test source into the
recorded command. Three things keep it off the rejection list: the TEST is now
hermetic and takes whatever path it is given, which is what rule 12's third
class actually requires; the evidence puts an explicit comment directly above
the command naming the hazard and instructing the reader to copy the tree into
a worktree first; and the corpus is untracked, so no in-checkout path exists to
record. The corrected form runs in MY worktree and produces identical results,
confirmed above and used for every number in this file. **Recommendation for
the next WP in this family: record the `$PWD`-relative form plus the copy step,
so the recorded command is the one that is safe to replay anywhere.**

**2. My own first pass's counter was doubled, and the worker's figures are the
correct ones.** `3f45d31` reported 18 spaces / 462 empties shipped and 236 /
244 converted, over a total of 480. Mine, from a single trace of 56 pages,
gives 9 / 231 and 118 / 122 over 240, exactly half in all four cells. My first
pass accumulated across two invocations of the trace. The RATIO, the direction
and every conclusion drawn from it are unchanged, but the worker's numbers are
right and mine were not. Recorded here because the evidence file carries the
worker's figures and a reader comparing the two verify files would otherwise
see an unexplained contradiction.

**3. `text_characters` does not move monotonically, and the evidence does not
say so.** "16 to 43 of 56" reproduces exactly, and "moves `text_characters` by
27 pages" is a correct NET figure, but derived from the enumeration it is 34
pages GAINING agreement and 7 LOSING it, with 47 of 56 pages changing their
character count at all. The seven that lose agreement are
precisely the seven `body_text_lines` pages, `[4, 11, 31, 36, 40, 46, 50]`,
and on each the tracer is now 2 to 3 characters ABOVE pypdf. Diagnosed: those
pages agreed under the BUG only by coincidence, the missing spaces cancelling
the extra newline from the headline the tracer correctly keeps on two lines. So
the "loss" is the tracer becoming more right, not less. The disclosure gap is
real but the direction is favourable and `text_characters` feeds no issue site;
confirmed by grep that `render_critic.py` WRITES `text_characters` at :1007 and
never reads it in a decision, while the five gating fields are read at :152,
:176, :198, :309, :380.

**4. The rule-10 restatement's headline sentence overstates; the paragraph
below it is exactly right.** "The label belonged to the code, not the corpus"
reads, alone, as though the non-discrimination was caused by the defect. It was
not: with the CORRECT rule in place, the unconditional space and the
unconditional empty still both pass, so the corpus genuinely cannot discriminate
the join rule on emptiness or `body_text_lines`, and that half of the original
label was true of the corpus all along. What was false was the other half, the
word "principled". The very next paragraph of the evidence says precisely this
and every leg of it reproduced, and the sentence is a verbatim echo of the
plan's own revision-40 wording, so this is a compression rather than an error.

**5. `mag/src/parity.rs` is comparator territory the plan assigns elsewhere.**
`80b7b62` touches four files: `mag/src/critic/text.rs`, `mag/src/parity.rs`,
`mag/tests/critic_text.rs` and its own evidence file. Plan line 3526 says the
one-line export "belongs to WP-2.0b, which holds `parity.rs`", and WP-2.0b
landed at `e5e741a` without `GLYPH_QUANTUM` in it. Not a rejection ground: my
first pass ran the Owns check over `26391ab`, which touched the same file, and
recorded it clean; the change is a single `pub(crate) use` addition with no
behaviour; and it survives. `git show art_directed:mag/src/parity.rs` still
carries it at line 20, alongside WP-0.2g's uncommitted 43 insertions in the
main tree, so nothing was clobbered in either direction. Flagged for the
orchestrator rather than held against the WP.

## Residuals, assessed

- **`py_islower` in `critic/text.rs` rather than `shared.rs`.** Honestly
  scoped, and I re-tested the backstop rather than taking my own first pass's
  word for it: appending a divergent `py_islower` to `mag/src/model/shared.rs`
  fails `no_helper_is_defined_in_two_modules` with
  `same name and signature: ["py_islower in [("critic/text.rs", "py_islower"),
  ("model/shared.rs", "py_islower")]"]`. The dangerous case has a mechanical
  backstop. Tidiness with a residual, as claimed.
- **One glyph advance of uncertainty in the width.** Honest and inherent:
  `offs` carries origins, so the last advance is estimated by the mean. Visible
  in the kerned fixture, whose gap is -6.83 pt rather than a small positive
  number. Nothing in this WP's numbers depends on the estimate being tight,
  since the only threshold crossing it must get right is a 10.67 pt gap against
  5.75 pt.
- **The y-tolerance is proven only in the widening direction.** Reproduced
  both directions: `SAME_LINE_TOLERANCE = 1200` FAILS with `left: 1111
  right: 1117`, exactly as claimed; `SAME_LINE_TOLERANCE = 0` PASSES. The
  residual is stated correctly.
- **The Unicode pinning is proven by sweep, not by 010.** Reproduced both
  legs: deleting `661` (U+0295) from the oracle FAILS with `left: 2544
  right: 2543`; replacing `py_islower`'s body with `char::is_lowercase` leaves
  `reconstructs_edition_010_text` PASSING. The corpus contains none of the 53
  divergent codepoints and the evidence says so.
- Block 1 regenerates `mag/tests/critic_text_islower_expected.txt`
  BYTE-IDENTICALLY: sha256 `e6b31f9b0c2f67f2af0ea546a11493d9e1b275d4b094e35fe05af61947e9ee70`
  before and after, Python printing 2544. Rule 12's recorded-command class,
  which rejected three earlier WPs, is closed here for the second time.

## Context the WP could not have recorded

`521ab79` rejected WP-0.2i's rework AFTER `80b7b62` was written, and WP-0.2i
supplies both `offs` and the `GLYPH_QUANTUM` value this WP's arithmetic turns
on. That rejection is **on the record, not the mechanism**. Its own words are
"The quantum fix is correct, and I could not break it. Do not redo the fix." So
this WP's configuration is not expected to move under it. Stated because rule 9
makes a number carry its configuration, and this configuration is under
concurrent verification.

## What this verification CANNOT discriminate

- **Whether the fixed rule is the CORRECT rule, in an absolute sense.** The
  corpus is insensitive on both decision-relevant fields, and I have no
  independent oracle for intra-line spacing. What I have is circumstantial and
  strong: 43 of 56 pages now match pypdf's character count EXACTLY, up from 16,
  and the two pages I read by eye are correctly spaced word by word. Thirteen
  pages still disagree, by +9, +3, +2, +1, +2, +2, +1, +2, +3, +2, +2, -1, +2
  characters; I did not diagnose the nine that are not the headline pages.
- **`WORD_GAP_FRACTION = 0.25`.** Never perturbed, by the WP or by me. The
  corpus cannot tell, so no value of it is proven over any other.
- **The one-glyph-advance width error.** Unmeasurable without per-glyph
  advances, which the display list does not carry. WP-0.2j owns the path that
  could supply them.
- **Anything outside edition 010 English, 56 pages.** The Spanish edition, any
  other edition, and any other page geometry are untested here.
- **Whether `text_characters`' nine undiagnosed disagreements hide a residual
  spacing defect.** They are small and the field gates nothing, but they are
  not explained.

## Commands

    git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp53bi3 80b7b62

    git merge-base --is-ancestor 26391ab a537a24 && echo "ANCESTOR: YES"

    # blocks extracted programmatically, then executed
    bash /tmp/vcmd/block1.sh   # islower oracle, byte-identical
    bash /tmp/vcmd/block2.sh > /tmp/vcmd/pypdf.json
    bash /tmp/vcmd/block3.sh   # MODE: skipped
    bash /tmp/vcmd/block4.sh   # MODE: full, but traces the MAIN tree (finding 1)
    bash /tmp/vcmd/block5.sh   # fmt --check, clippy -D warnings, both exit 0
    bash /tmp/vcmd/block6.sh   # 109.22666666666667
    bash /tmp/vcmd/block7.sh   # the two merged headlines

    # the corrected full-mode form, which is what every number here used
    MAG_CRITIC_READER_PDF=$PWD/editions/010/render-2026-09-14T01-47-59/en/reader.pdf \
      cargo test --manifest-path mag/Cargo.toml --test critic_text -- --nocapture

    # the assert fires when the variable is set but the file is missing
    MAG_CRITIC_READER_PDF=/tmp/definitely-not-here/reader.pdf \
      cargo test --manifest-path mag/Cargo.toml --test critic_text reconstructs -- --nocapture

    # the three mutations of claim 5, each applied with a python replace on
    # mag/src/critic/text.rs and reverted with
    #   git show HEAD:mag/src/critic/text.rs > mag/src/critic/text.rs
    # (a) drop the qo-to-qc conversion; (b) separator returns " "; (c) returns ""
    cargo test --manifest-path mag/Cargo.toml --test critic_text -- --nocapture

    # the residual probes, same apply-and-revert shape
    # SAME_LINE_TOLERANCE 100 -> 1200 (FAILS 1111 vs 1117), -> 0 (PASSES)
    # oracle minus 661 (FAILS 2544 vs 2543)
    # py_islower body -> char::is_lowercase (corpus PASSES)
    # divergent py_islower appended to mag/src/model/shared.rs
    cargo test --manifest-path mag/Cargo.toml --test rust_helpers

    cargo test --manifest-path mag/Cargo.toml

    git status --porcelain   # empty after every probe was reverted

The branch tallies and the per-page table came from two temporary
`AtomicUsize` counters in `separator` plus a scratch integration test
`mag/tests/vscratch.rs` mirroring `critic_text.rs`'s `#[path]` includes. Both
removed; the worktree is clean against `80b7b62` and the full `cargo test` is
green.

## Owns check

`git show --stat 80b7b62` lists exactly four files: `mag/src/critic/text.rs`,
`mag/src/parity.rs`, `mag/tests/critic_text.rs` and
`meta/verification/evidence/WP-5.3b-i.md`. No verify file, no `baseline.json`.
`mag/src/parity.rs` is finding 5.

## Tool versions

rustc 1.96.0, lopdf 0.45.0, `uv run python` 3.12.11 on Unicode 15.0.0, pypdf
6.14.2. System python3 3.9.6 on Unicode 13.0.0 was never invoked.
