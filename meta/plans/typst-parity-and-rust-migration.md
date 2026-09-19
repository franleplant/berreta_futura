# Typst parity and the full-Rust migration

Status: **in execution**, 2026-09-19, revision 54 (Phase 0 built and
verified, the Phase 1 spikes measured and audited, the gate critiqued
adversarially and repaired, the content-final gate narrowed to where it
bites). Companion to `rust-rewrite.md`
(which moved orchestration to Rust and left the renderer in Python). This
plan finishes the job: a Typst-based renderer implemented in Rust inside
`mag`, proven equivalent to the WeasyPrint renderer by rendering **edition
010 (en)** with both engines and comparing mechanically until they are
exactly the same, then porting every remaining Python module to Rust and
deleting `src/magazine/`.

## Revision 54 changelog

**THE PROVENANCE AUDIT IS LANDED (`8a03c1a`) AND CLEAN: no mismatches.**
Five digests and one reader-hash pair check to the byte, so **the `out_dir`
concurrency hazard has not corrupted any recorded number that can be
checked**. 139 parity run citations at `ba9c3ea`, 64 digest-bearing across
19 files (47 distinct, derived programmatically and re-derived by the
replay) and 75 digest-less, both totals re-derivable from the document's
own tables. **139 is a FLOOR, not a total**, since seven of the eleven
digest-less rows are second-hand. That caveat is the rule-10 disclosure
evidence almost never volunteers, and it is the reason the clean result can
be believed.

**`staged_input_digest` IS RETIRED AS A PROVENANCE INSTRUMENT, which is
further than either the coordinator or I had got.** Revision 49 corrected
my claim that every verdict carries it, and revision 51 left the plan
implying it WOULD pin staged inputs if only it were emitted. Measured:
where the field does exist, **it is IDENTICAL across seven render
directories of edition 010**, so it has ZERO discriminating power even in
the staging modes. Not mode-limited, useless. The emitted shapes were
verified from source and from two real verdicts before either of my
corrections reached the audit: `--pre-rendered` emits 8 keys at `521ab79`
(9 at `ba9c3ea`) with no `staged_input_digest` and no `staleness`;
`--oracle-only` emits 12, a strict superset.

**The partition is MEASURED: corpus figures do not move with the render.**
Five renders of 010, five distinct `reader.pdf` hashes, one fixed base:
identical glyphs, shows, domain and page count in all five. So a
disagreement between two corpus figures cannot be a render artefact.
**The audit declined to force the conclusion, and that restraint is
recorded with the result**: it rules out the render, it does not by itself
prove base-mismatch over corruption, and it tested four figures on one
edition rather than the whole clause family. Given the coordinator
over-steered on precisely this question and revision 53 struck my hedge for
the same reason, an audit that stops exactly where its evidence stops is
the behaviour to reinforce.
**One hypothesis retired outright**: a single verdict carries `glyphs
68800`, a **54-page domain** and `page_count 56` TOGETHER, so 68,800 is not
a 56-page count. That independently supports dropping 69,071 rather than
reconciling it, and it arrives from a different direction than WP-0.2i's
enumeration, which is what makes it worth having.

**A STANDING HABIT, not a worklist item: print the verdict's `inputs` block
beside the digest and name the base.** A figure then lands in the checkable
bucket in seconds with no re-run. The argument is empirical: bucket 1 had
ZERO members at `ba9c3ea`, and WP-5.5a's revision made it the first and
only one, its check passing (`0460c081...` and `15d3bd5a...` resolving to
the two worktrees in the order claimed, 85 seconds apart). **One agent
adopting the habit voluntarily moved the corpus from "unverifiable" to "one
verified member"**, which is a better case for standardising it than any
argument from principle.

**URGENT, and load-bearing: WP-0.2i's floor `stairdrift`, the `4.00x`
margin, has NO DIGEST.** It survives only because two agents measured it
separately and agreed. That is THE GATE'S FLOOR. The distinction to hold
onto is epistemic and the coordinator put it correctly to the in-flight
verifier: **its replay ESTABLISHES the provenance rather than confirming
it**, so the digest, the base and the input hashes are recorded as new
facts, not as a check against something already written. Then, in order:
WP-2.0b's unresolved `11a9c0a8` against its verifier's `38f91a94` for the
same oracle-only run, a genuine conflict needing one run at `e5e741a`;
WP-0.2d's 21 digests including the inherited `241`; WP-0.2e/0.2b/0.2c/
0.0c/1.3; then 54 digest-less fixture runs. **WP-0.2k gates all of it.**

**Two environment corrections, and the first is mine.** Revision 49 said
`mag parity` refuses to run outside a repo root so isolation must mean a
WORKTREE. Over-strong: the audit ran everything from a symlink farm, and
the check in `mag/src/main.rs:218` is literally
`Path::new("prompts").is_dir()`, so **one directory named `prompts`
satisfies it**. What actually matters is only that `out_dir` is NOT SHARED.
Second, **`set -o pipefail` ABORTS ON AN EXPECTED-EMPTY `grep`**, since
grep exits 1 when it matches nothing; verified here, the statement after
the pipe never runs. This is a live hazard created by my own revision 49
guidance, which told every agent to set pipefail, and the plan's own
U+2014 scan is exactly that shape. Remedy: `|| true` on any pipeline whose
empty result is the expected one.

**The audit self-corrected through the rule-12 replay**, its section 1a
having stated "seven" and "five" occurrences where re-deriving gave
2 / 4 / 2 = 8, and the same replay caught both command defects. **Third
time the replay has caught something rereading could not**, which is the
evidence rule 12 was written on.

## Revision 53 changelog

**Cut now for one operational rule and one correction to my own steer; the
count reconciliation and the retirement of 69,071 are HELD until WP-0.2i's
verification lands**, per the cadence standard: cut immediately for what
changes an in-flight agent's behaviour, batch what only records.

**CLEARING THE INDEX LEAVES THE WORKING TREE STALE, and the protocol says
how to fix the first while being silent on what the fix leaves behind.**
Check 4's path-scoped reset touches the INDEX only, correctly, since the
rule forbids a path checkout while other agents hold uncommitted work in
that tree. But the working copy then still holds the pre-land content, so
**the next agent to read that tree sees a landed file as DELETED or stale**.
The remedy is the one the protocol already knows for the ref-move case:
refresh with `git show HEAD:<path> > <path>`, which writes the working tree
and touches no index. Now stated as the second half of check 4 rather than
left to be rediscovered; it was caught in the field by the landing agent
flagging it, not by the protocol.

**The base-mismatch hypothesis is DEAD, and it was mine.** Revision 49 said
the fourth cross-spike disagreement MAY be a base mismatch rather than a
domain mismatch, and offered that as the cheap test. It is not, on ground I
verified independently: **WP-0.2f's own `## Commands` block names
`editions/010/render-2026-09-14T01-47-59/en/reader.pdf`** (`WP-0.2f.md:36`),
the same file the rework measured, so no commit difference can sit between
the two numbers at all. The rework tested it anyway across seven distinct
render trees, comparing POPULATIONS rather than totals, and the per-page
`(shows, glyphs)` vector is elementwise identical in all seven. So **the
named-commit rule stands as a rule and does not explain these numbers**,
and the plan must not imply it does. Revision 49's hypothesis is struck
here rather than left hedged, because a hedged wrong steer still steers:
the coordinator pushed it to two agents on my wording.

**What replaces it is revision 42's hypothesis, CONFIRMED by enumeration
rather than by subtraction.** 1,503 = 1,488 + 15, and the 15 are
identified by member: 5 shows on page 1 and 10 on page 56, all `Tj` not
`TJ`, all font `F1`, all at render mode `3 Tr`. The covers carry invisible
text and the larger figure counts all 56 pages while 1,488 covers the
54-page interior. **That is "an aggregate is not a population" used as a
METHOD rather than quoted as a caution**, and it is the difference between
a reconciliation and a coincidence that two numbers differ by 15.

**Two protocol confirmations from the field, both on the same landing.**
The CAS **REFUSED** on the first attempt because the branch had moved, and
refused correctly, the agent having swapped against its rebase base rather
than a re-read tip: revision 50's guard doing exactly what it exists to do,
two days after it was written, and the first evidence that the rule works
in the failing direction rather than only in the passing one. And check 4
fired as a **TRUE POSITIVE**, confirmed persistent across two reads with
contents verified as the reversion before clearing, which is revision 48's
re-read-before-acting discipline reaching its intended outcome.

**Held for WP-0.2i's verification, recorded here so it is not lost**: the
recommendation to carry 68,800/1,488 with its domain named, write 1,503
only with "whole document", and **RETIRE 69,071 rather than correct it**.
The covers carry 537 string bytes giving 69,337 document-wide, and 69,071
is not that, not 450 non-space, and not either cover alone. (Revision 54
adds independent support from a different direction: a single verdict
carries `glyphs 68800`, a 54-page DOMAIN and `page_count 56` together, so
68,800 is not a 56-page count and the two figures are not the same
measurement disagreeing.) The reasoning
for deletion over adjustment is the part to keep: **nobody has shown what
69,071 was ever counting, and a number whose provenance is unrecoverable
should go rather than be adjusted into plausibility.** It appears at nine
sites in this plan, which is the other reason to do it once, after
verification, rather than twice. WP-5.5a's 68,530/1,501 stays named as a
THIRD population and is deliberately not folded in, since folding it would
manufacture agreement between different domains.

## Revision 52 changelog

**A DEFECT TAXONOMY, ruled on because the coordinator is right that the
plan's machinery answers only one of the three cases.** The axis that
matters is NOT severity: it is **what the fix is pinned to, and whether the
item survives WP-6.1.**
- **Class A, a port-fidelity gap**: Rust differs from Python and Python is
  right. Fix by matching Python. This is what every tier, every oracle and
  every fixture in this plan is built for, and the CATEGORY DIES AT WP-6.1,
  because once Python is deleted there is nothing left to diverge from.
- **Class B, a live product defect that SURFACES as a divergence**:
  `content_label` is one. The fix is identical to class A, match Python,
  which is why the machinery handles it and why the class is easy to miss.
  Two things differ and they are the whole reason to name it.
  **Reachability decides SCHEDULE**: a class-A gap in a branch 010 cannot
  reach can wait for the flip, while a class-B defect is reachable from
  ordinary user input and ships wrong output the day someone writes that
  line, so it goes ahead of unreachable gaps.
  **And its regression test must OUTLIVE the oracle**: a class-A test may
  say "equals Python", but a class-B test pins the CORRECT STRING directly,
  because after WP-6.1 a test asserting "matches Python" documents nothing
  and nobody can tell from it why the string was right.
- **Class C, BOTH engines wrong.** Parity is blind to it by construction:
  both legs agree, every tier passes, the output is wrong. **This is not
  hypothetical, and the same function has one.** Executed, not read:
  `label: false` yields the literal string `"False"` in Python (the guard
  is `value is not None`, and `False is not None`) and `"False"` in Rust
  (`py_str(Bool(false))`), so both engines print "False" as a section label
  and no amount of parity work will ever notice.
So the plan says plainly what it does not do: **EQUALITY IS NOT
CORRECTNESS.** This plan proves the two engines agree. Its entire
verification machinery is silent on whether what they agree about is right,
and "010 renders identically" must never be read as "010 renders
correctly". Class C is found by a reader or by a non-parity check, and
nothing in Phases 0 to 4 is looking for it.
Revision 23's "a port must not be stricter than its original" is untouched:
it governs class A, and class B is not a case of the port being stricter.

**`content_label` is a class-B defect, confirmed at source in both
engines.** `mag/src/model/shared.rs:327` maps `py_str` over the raw value
with no None guard, so `Some(Null)` gives `"None"`, non-empty, returned as
the label; `html_edition.py:737` guards `value is not None and
str(value).strip()` and falls through to `_ui`. **A bare `label:` in a
manuscript prints the literal word "None" as a section label.** WP-5.1g.
Its latency is a CORPUS ACCIDENT, not a guarantee: 548 `label:` keys over
20 distinct values with none bare is the corpus rule exactly, a statement
about the corpus rather than about reachability, so the fixture must carry
the case the corpus lacks.

**A harness that aborts on first failure evidences only the first failure,
WHICHEVER LAYER ABORTS, and this generalisation is better than the rule it
replaces.** The narrow form said a short-circuiting `assert_eq!` proves
only the first failure. WP-5.1f then hit the identical truncation one level
UP: `cargo test --test a --test b` stops at the first failing binary, so
its block produced only the label failures while the caption claimed four
cases. **The assertion, the test binary and the test RUNNER are three
separate places the same truncation happens, and only the first is
obvious**, so a WP that carefully writes an accumulating assertion can
still have its evidence truncated by the runner above it. The check is
rule 12's caption clause: read the output against the caption and COUNT THE
FAILURES YOU WERE PROMISED.

**A fixture pattern promoted, because it answers a question this execution
has asked at least five times: "I found something real and cannot fix it
here."** WP-5.1f committed the divergence as fixture data flagged
`known_divergence` plus a tripwire test whose failure message reads *"if
this changed, the divergence was fixed; clear `known_divergence` in the
fixture and delete this test"*. It rejected both alternatives with
reasons worth keeping: committing the Rust value as expected would CEMENT
THE BUG and make the eventual fixer edit a GREEN test, and prose is the
rediscovery problem. This replaces the residual paragraph nobody reads.

**A framing correction, and the lesson is one this execution keeps
relearning.** `content_label`'s whitespace defect was described as confined
to the empty-test fall-through. The fixture proved otherwise:
`label: "  Dispatch  "` shows the strip changing the RETURNED VALUE, so it
was never confined to that branch. Found by writing the fixture rather than
by reading the code, which is the padded/straddle lesson again.

**The `shared.rs` sweep is CLOSED with a statement a reader can rely on**:
the grep returns seven lines and only seven, two definitions
(`is_python_space`, `py_strip`) and five uses, three of which were wrong
and are now pinned (`is_name_roster` twice, `content_label` once), while
`ui` and `clamp_roster` handle no whitespace at all. **The next reader does
not need to re-open the file**, and that is the standard a residual should
meet: a sweep records the boundary it established, not only what it found.

Rule 9's new citation clause has now corrected the coordinator a fourth
time, on a claim that the branch had moved when it had not.

## Revision 51 changelog

**WP-2.1 is ACCEPTED (`9acc797`) and WP-2.2a keeps building on it, but two
findings BOUND what its headline proves, and the plan leaned on the
unbounded reading.**

**The compared boundary was misnamed, and the correction cuts BOTH ways,
which is what makes it credible.** WP-2.1 called its compared text "the
reader-visible text before any layout exists". Measured against
`weasyprint-a5.css` it INCLUDES 835 of 68,758 characters (1.21%) that are
never printed, `display:none` on `.edition-header` (314) and nine
`.source-link` URLs (521), and EXCLUDES text that IS printed, the CSS
`::before` figure and extract labels, which are generated content rather
than layout. The accurate name, and the right seam for a content pipeline:
**the text content of the pre-layout HTML document.**
The method is the part worth keeping. **The verifier TESTED the "boundary
drawn to make the comparison succeed" hypothesis rather than arguing it,
and it failed**: the included-but-unprinted runs make the comparison
HARDER, 835 extra characters both legs must match, and everything
excluded-but-printed reduces to one emitted value, `word:`, whose two
possible strings were checked against Python entry by entry across both
`ui` tables. That is rule 11 applied to a DEFINITIONAL choice rather than
to a mechanism, which this execution had not done before, so it is now
written as a rule: **when a WP defines the boundary of its own comparison,
the test is whether the definition makes the comparison EASIER or HARDER.**

**The oracle is BLIND TO BLOCK STRUCTURE, measured rather than inferred**:
two `#doc-paragraph` calls and the same text merged into one project
BYTE-IDENTICALLY. So WP-2.1 proves *same text in same order* and nothing
about structure. "Byte for byte across all of edition 010" reads far
stronger than it is, and paragraph-level claims are exactly what a reader
would assume it covers, so the two oracles are now named separately
wherever the plan leans on this: **the content oracle proves text and
order; Tier S page boxes and WP-2.2b/2.2c's targets prove structure.**

**Three of the four normalization clauses are vacuous on the whole compared
corpus**: 0 soft hyphens, 0 U+2010, NFC a no-op; only whitespace collapse
does work, on 2,134 of 70,892 characters. Rule 10a's family, unlabelled.
Not a defect, but it is the disclosure rule 10 exists to get.

**A pinning claim in the coordinator's brief was overstated, and the
evidence was more careful than the brief.** `content.rs`'s
`normalize_reader_text` IS Python-pinned and is NOT pinned to its sibling,
which holds. But **`mag/src/parity/text.rs:43 normalize` is pinned to no
Python oracle at all, because none exists** (verified: it normalizes
PDF-extracted text and is used only to compare two PDF extractions against
each other, at `text.rs:79`). WP-2.1's evidence said "the PDF text path",
not "Python", and was accurate. This matters because the duplicate-helper
rule's whole force is that each copy answers to Python, and here one copy
answers to nothing, so the conclusion is sharper than "record the gap":
**these two must NOT be merged.** They are not one function in two places;
they normalize different things for different oracles, and lifting them
into a shared module would silently pin the Python-pinned copy to the
unpinned one, which is the exact failure the rule forbids.

**Rule 9's citation clause now binds BRIEFS and COORDINATION MESSAGES, not
only evidence files.** Two counts in the coordinator's brief were wrong and
neither came from the evidence (47 template functions, not 46; 17 `cargo
test` suites, not 18, which I confirmed). Third wrong count at the point of
citation this week and the first where the citer was the coordinator rather
than a WP, which is the argument for widening the clause: a brief is where
a number enters a WP's reasoning, so it is a citation like any other.

**One real defect in WP-2.1's evidence, not its code**: the rule-2b line at
`mag/src/typeset/content.rs:1170` prints `projection.text.len()`, which is
BYTES, labelled "characters", so `69097 characters` should be 68,758. The
Metrics table is right and the Verdicts section quotes the mislabel.
One-line fix, `.chars().count()`, owned by whoever next holds
`content.rs`; `:1162` carries the same mislabel in its threshold message.

Two more, both good practice worth naming. The guard fires on **12 markup
leaf kinds** beyond the committed heading case, all refusing with
`unprojectable markup`, and rule 11 was applied to what it PROTECTS:
neutering `escape_markup` failed five tests loudly. And the verifier
recorded a **rule-11 result against ITSELF**, hypothesising a Python/Rust
whitespace-split divergence on NBSP and refuting it exhaustively over all
0x110000 codepoints (they differ on exactly U+001C-U+001F, none present,
and that direction fails loud anyway). A verifier disproving its own
hypothesis and recording the refutation is what rule 3c is trying to
produce.

## Revision 50 changelog

**A real defect in the landing protocol itself, and it INVERTS a guard into
the thing it exists to prevent.** Every agent has been told to move the
branch with a compare-and-swap `git update-ref` and never told WHICH value
to swap against, so WP-5.3b-ii rebased onto `883a095`, re-read
`art_directed` at update time as `0fafae1` (revision 49 having landed in
between) and passed THAT as the expected-old. The CAS succeeded, and its
commit's parent was the older `883a095`, dropping revision 49.
The generalization is the agent's own and it is the alarming part: **read
that way, the CAS succeeds precisely in the case it exists to refuse.** A
stale base is exactly the situation where the tip has moved, and re-reading
the tip at update time makes the guard agree with whatever it finds. So the
rule is now stated in the protocol: **the expected-old value is the commit
you REBASED ONTO, captured before the rebase and never re-read.**
Caught within seconds by landing check 2, which is that check working as
designed and the best evidence yet that the three-check discipline earns
its cost; re-landed as `20adcfb`, and I confirmed independently that
`0fafae1` is `20adcfb`'s parent, is an ancestor of `art_directed`, and that
revision 49's changelog is present in the file.

**Check 4 fired for real on the same landing and was handled exactly as
revision 48 specifies**: 1 modify + 17 deletions staged, the reading
PERSISTED across a re-read, the staged content was verified as deletions of
files present in HEAD, and it was cleared path-scoped. That is the
re-read-before-acting rule separating a true positive from the false one a
verifier hit the day before, one day after it was written.

**THREE ports have now been blocked by a PRIVATE SIBLING HELPER, so the
pattern gets a general statement rather than a third ad-hoc fix.**
WP-0.2h's tracer seam (blocker 1), WP-5.4a's `is_python_space` and `py_str`,
and now WP-5.3b-iii's `mag/src/critic/metrics.rs:411 fn resize`, which is
verified private and is the PIL `Image.resize` WP-5.3a already proved.
The two earlier responses went opposite ways: WP-5.4a duplicated and the
plan needed WP-5.1e to lift the copies back out, while WP-5.3b-ii refused
to duplicate **because two copies would be pinned to EACH OTHER rather than
each to Python**, which is the duplicate-helper rule applied with judgment
instead of by rote and is the right call. Routing through the owner with a
scoped Owns extension is the plan's answer, as it was for blocker 1.

**A stale figure in the plan's own prose, found by rule 9 re-derivation.**
`text_characters` 16 of 56 is the PRE-rework number measured under the
`Show.width` unit defect that `80b7b62` fixed; both WP-5.3b-i's evidence
and WP-5.3b-ii's independent measurement give **43 of 56**, and
`body_text_lines` 49 of 56 reproduces exactly. Corrected in place. (The
site is line 4616, not the 3843 reported; I located it by content rather
than by the cited line, which is the habit rule 9 is asking for.)
The two measurements were taken on DIFFERENT renders of the same edition,
with different `reader.pdf` sha256, and produced identical counts, which
cuts usefully against revision 49's named-commit rule: the base matters for
some figures and demonstrably not for these. The rule is about knowing
WHICH, not about assuming every figure moves.

**`serde_json`'s default float parser is NOT round-trip exact, verified
here rather than taken on report.** `97.71500651041667` gives
`0x40586dc2aaaaaaab` through `str::parse` and `0x40586dc2aaaaaaac` through
`Value::as_f64`, one bit apart. `mag/tests/critic_metrics.rs:30` reads
WP-5.3a's metrics through `as_f64()`, so its "exact equality" is exact only
up to that parser. No measured disagreement exists and this is NOT a
defect; what is wrong is the WORD, which claims more than the mechanism can
carry. WP-5.3b-ii handled it properly in its own oracle by carrying
`rgb_mae` as TEXT and committing a test that asserts every float in both
oracles survives the round trip **and that the known-bad literal still
diverges**. That last clause is worth naming: it is rule 10 applied to a
GUARD rather than to evidence, and it is what stops the guard going vacuous
if the parser is ever fixed underneath it.

**WP-5.3b-ii accepted**: 85 of 85 rasters byte-identical to Python's output
and 85 of 85 `_inspect_page` rows identical, 15 fixture rows, 17
discrimination probes every one of which fails under mutation, both
extremes of the punctuation filter failing per rule 10's diagnostic, and
`render_pages` proven shard-invariant across 1, 3, 5, 12 and default
shards. That last is what makes a committed sha oracle machine-independent,
since Python uses `os.cpu_count()` and Rust `available_parallelism()`.

## Revision 49 changelog

**A new rule-12 class, and it is genuinely different from the others: the
CAPTION drifts from the COMMAND.** WP-5.5a's block was captioned "Every
segno call site" and searched only `src/ mag/src/`, returning nothing,
while four call sites sat in the generator it had just written. The command
RAN, the output was ACCURATE, and the caption was the false claim, so where
the other classes are the recorded artifact diverging from what was
EXECUTED, this is it diverging from what was CLAIMED about it. The agent's
own framing is the keeper: **rereading would not have shown it.** The check
is to read each block's output against its caption's SCOPE WORDS on replay.

**A premise I recorded in revision 44 was falsified, and checking it made
it more precise rather than simply wrong.** I wrote that every verdict
records `staged_input_digest`. Verified in the source: the field exists but
is `skip_serializing_if none` and is populated ONLY in the render mode that
stages its own inputs, so every `--pre-rendered` verdict, which is how most
WPs run parity, emits no such key and no `staleness` either. So the claim
is MODE-DEPENDENT, not absent. The audit's power is narrowed accordingly
and now states both halves: the two reader hashes DO catch a verdict wholly
replaced by a run over different artifacts, which is the dangerous case,
and CANNOT pin the staged inputs those PDFs came from. The audit verifies
the emitted field list itself rather than trusting any description of it,
including this one.

**A parity figure is only meaningful against a NAMED COMMIT**, which is
rule 9 applied to a moving render tree: for a figure measured against a
tree that changes, the BASE is the configuration. Three glyph figures are
in circulation and the cardinalities moved with them, explicable by the
source-codes asset landing between measurements, so the fourth cross-spike
disagreement may be a BASE mismatch rather than a domain mismatch. That
would make it a finding about the evidence regime rather than about page
domains, and would retire the cover-pages hypothesis revision 42 offered.
Cheap test: measure one figure at each of the other bases and see whether
they converge.

**A MULTI-STEP perturbation is not evidence of tightness**, only of
non-inertness, which is the weaker claim such evidence is entitled to make.
WP-5.4b's two surviving guards read as verified for exactly that reason:
the wordmark had eight steps of slack and was perturbed by ten, the title
three and was perturbed by eight, and neither smallest flipping move was
the move made. A perturbation must be ONE STEP at the guard's own
granularity. Recorded beside it is what real tightness looks like, from the
same sweep: an 83-character stem differing in ONE GLYPH, flipping because
one line's width changes by 6.64 pt, with no tighter pair possible since
the loop evaluates only multiples of 0.5. And a guard can be HALF-verified:
the line limit discriminated loosening but not tightening, because no
fitting fixture existed, and saying which half is the labelling rule 10
asks for.

**Two environment facts that cost attempts.** `mag parity` refuses to run
outside a repo root, so the standing "isolated cwd" instruction is
unsatisfiable as worded and the WORKTREE form is what satisfies it. And a
pipe MASKS exit status, so `<command> | tail` reports the pipe's success
and cleanup runs even when the command failed; this cost the planner two
rebuilt commits when a failed fast-forward was piped to `tail` and the temp
branch was deleted anyway.

One latent defect recorded, not live: with the headline limit at `<=4` the
fitting fixture lays out four lines and PANICS at `mag/src/cover/svg.rs:537`
because the colour cycle has three entries. Unreachable while the limit is
`<=3`.

## Revision 48 changelog

**The fourth landing check had a flaw, and the flaw is structural rather
than incidental.** `git status` on a shared tree under concurrency is a
SAMPLE, not a state. A reading taken while another agent is
mid-`update-ref`-and-sync shows that agent's land as a mass deletion, which
is EXACTLY the signature check 4 hunts for, so **the false positive is the
check's own success condition arriving from the wrong cause** rather than a
rare coincidence. It has already fired once: a verifier reported a 31-file
reversion of WP-2.1 and retracted it on its own next pass, with the index
empty, the tree clean and all 31 files present.

What makes it worth fixing rather than noting is that the prescribed remedy
is a WRITE. Unstaging another agent's in-flight land is bounded harm, since
a path-scoped reset touches only the index and the landing agent restages,
but it stops being bounded the moment someone reaches for a HARD reset
because the path-scoped form "did not work". So the rule now requires a
re-read after a pause before acting, action only if the reading PERSISTS,
and inspection of the staged CONTENT before resetting, since both real
incidents were identifiable by content: one staged the removal of a
`GLYPH_QUANTUM` export that HEAD had, the other a verify file that existed
in HEAD and on disk. The general form, quoted because it applies past this
check: **any index check on the shared tree is re-read before it is acted
on OR REPORTED.**

**Rule 3c is working, and its limit is precisely rule 3d's gap.** Two
verifier self-corrections in one day, both caught the same way, by the
verifier's own next pass: the doubled counter and this retracted index
reading. So a verifier's re-reading does catch its transient OBSERVATIONS.
What it cannot catch is a wrong ARGUMENT that produced a correct verdict,
because nothing prompts a second look at reasoning that reached the right
answer. Both are true and not in tension, and the contrast is the useful
part: it is why rule 3d is about WHERE a reason is recorded rather than
about re-reading harder.

**WP-2.1 has landed** (`f00e4c7`, 31 files, all additions), so Phase 2's
content pipeline is in and the chain that opens Phase 3 is
WP-2.1 to WP-2.2 to WP-2.3, with WP-0.2k the only other thing in front of
it now that the content-final gate is withdrawn. (Accepted at `9acc797`;
revision 51 renames the compared boundary and BOUNDS the result to text and
order, since the oracle is blind to block structure. Cite it accordingly.)

The gitignored-path residual needs nothing further: revision 47 already
wrote it as standing guidance after the third instance, and WP-0.2g's
`$PWD/editions/010/render-*` is that instance.

## Revision 47 changelog

**Rule 10a amended before the pattern sets, which is why this could not
wait.** Cardinality is derived from LEG A only. Rule 9 sanctions that and
it is harmless on a PASSING clause, where the populations agree by
definition. On a FAILING clause it misleads: an A-vs-stripped run prints
`fail (84 annotations...)` while leg B holds 57, so it "reads like an
agreed population and isn't one". Since revision 44 made this reporting
mandatory across every Tier S collection clause precisely so that close
reading is possible, and since reporting is read most closely exactly when
a clause FAILS, the single-leg form points the reader wrong at the only
moment they are looking hard. **Report one number only when the legs agree,
and both when they differ.** Cheap now, awkward once a dozen clauses have
adopted the single-leg form, and WP-0.2k is implementing the sweep as this
lands.

**The vacuity rule 10a targets is now demonstrated rather than argued**:
emptying every `/Annots` on both legs yields `0 annotations of which 0
links` and THE CLAUSE STILL PASSES. Emptying only page 3's yields
57 = 84 - 27 against an independent pypdf census.

**Rotation confirmed on all three legs, including the hard one.** Body-text
page 3 fails boxes, text, Tier G and both raster meters; blank page 2 has
`boxes` as the ONLY failing clause with everything else at literally zero
delta. Revision 44's narrowing was right, and it is now measured rather
than reasoned.

**Two observations worth more than the WP they came from.** A meter that
gates nothing can still be load-bearing as a PRECONDITION check: a max
channel delta of 0 is itself the proof that page 2 is genuinely blank, so
the Tier V meter earns its keep even though it gates no verdict. And a
residual disclosed as UNMEASURABLE was later DISCHARGED once the mechanism
existed, which is the `## What is and is not proven` regime paying off
exactly as intended: `page_sets_refused` was measured by seeding
`baseline.json` to 64 zeros, and `raster_bound` turned out stronger than
claimed, byte-identical rather than merely equivalent.

**Rule 12's relocation clause gains its standing form, after three
instances in one day: a `$PWD`-relative path is NOT hermetic if what it
points at is GITIGNORED.** Three WPs each believed they had complied; the
form looks portable and resolves only in the tree where the work was done,
because the corpus and render directories exist nowhere else. The fix is a
one-token default.

**And the caveat that bounds all of it, recorded because it is easy to
over-read: BOTH LEGS ARE WEASYPRINT**, so nothing WP-0.2g proved says the
engines agree. 90 and 270 degree rotations are untested, the
fixture-inertness argument is cardinality-level only, and the digest
comparison covers passing-clause serialization only.

## Revision 46 changelog

**Both corrections applied, the hold released by verification `c1253d8`.**
WP-1.7's delta table mixes two normalizations and the error is **FORCED,
not plausible**: no single normalization reproduces all six recorded rows,
three matching collapse and three removal, so there is no reading under
which the table is internally consistent. WP-1.2's headline is the
ARTIFACT-CORRECTED count, and its own file says so twice, since its
`## Verdicts` calls the misses file "the two recorded misses" while the
headline says "misses: 1", and 149-1=148 with 968-5=963 is exactly the
hand-discount of block 4.

**The +0.025000 pt recommendation survives, demonstrated rather than
assumed.** The interval comes from `measure()` in WP-1.7's section 2, not
from the harness, and block 4 is a miss at ALL SIX deltas under collapse
and at NONE under removal, so it can move neither bound; the measured-safe
set is unchanged and the separate "698/698 unstyled lines" claim is
untouched because block 4 is `styled=True`. That is the difference between
"probably harmless" and harmless.

**Rule 3d, for the gap you identified and could not close: a correct
VERDICT immunises a wrong ARGUMENT.** Nothing ever checks a verifier's
reasoning, only its verdict, and once the verdict is right nobody looks
again. Twice in one day, and both caught by a later WP tripping over the
same ground BY ACCIDENT, which is luck rather than a mechanism.
The mechanism I can offer is about WHERE a claim lives. **A verify file is
a TERMINAL document, written once and never re-read; the plan is a LIVING
one, re-read continuously.** This execution has corrected many plan claims
and, until today, no verify-file claim, and that asymmetry is the evidence
rather than a coincidence. So an acceptance resting on a REASON rather than
on reproduction alone restates that reason in the PLAN or the WP's
evidence, where later work collides with it, and a REWORK's verifier
re-reads the ORIGINAL verification rather than only the new evidence.
Neither catches everything; together they replace luck with two cheap
habits, and the first addresses the case that actually bit, where the WP
was never reworked and a DIFFERENT WP collided with it.

**WP-1.9 commissioned, for the one non-discrimination worth closing.**
Whitespace removal is now the sanctioned comparison, adopted because it
reproduces WP-1.2's headline and still fails blocks 135 and 137, and nobody
has shown what it can HIDE. That is the straddle rule applied to a
NORMALIZATION rather than a threshold: a treatment adopted because it
discriminates on the cases at hand is not thereby shown to discriminate on
the cases it was designed to ignore. Three outcomes are legitimate,
including that the question cannot be settled without the engine.

**And a sweep rather than a rule, because the FILE is the common factor.**
The fourth count-beside-enumeration slip is `WP-1.2.md` recording its six
excluded span blocks as "34 lines" where the enumeration carries 8. It
changes no compared population, so it is an erratum, but THREE of the four
instances of this class live in that one file, which says read it once in
full rather than correct it a slip at a time.

## Revision 45 changelog

**WP-1.8 is the cleanest rule-11 result of the execution: the hypothesis
died twice over, and the real cause was one line neither spike suspected.**
The plan supposed WP-1.7's harness lacked WP-1.2's styled-run preservation.
Measured: **the two harnesses are the same program**, and run on a
byte-identical input dump they give identical numbers with neither
producing 148/149. The disagreement was never between the spikes, but
between WP-1.2's recorded harness and WP-1.2's own headline table. The
removal test then showed styled-run preservation cannot move that count in
either direction, though it is not inert. Both extremes were run per
rule 10, and both giving 147 was reported as the RESULT rather than read as
agreement, which is revision 38's diagnostic working as designed.

**The finding that outranks the reconciliation: AN AGGREGATE IS NOT A
POPULATION.** WP-1.2's fix repairs block 39 and simultaneously introduces
block 4, so **the 147 before and the 147 after are two different 147s**. A
total that does not move can conceal two compensating changes underneath,
and that is precisely where the plan's false hypothesis came from: an
unchanged aggregate was read as an unchanged population, and the plan
carried it for revisions. The check is to compare member SETS rather than
totals, which is what named block 4. It sits beside revision 43's
non-monotonic `text_characters` case, and together they make one point from
two directions: a total can move while the population gets healthier, and a
total can sit still while the population changes underneath.

**The cause, named by measurement**: the comparison's whitespace
normalization, shared by both harnesses, collapses RUNS of whitespace but
cannot remove an INSERTED space. Removing whitespace entirely moves both
harnesses to 148/149 and 963/968, WP-1.2's headline exactly, appearing when
added and returning when removed. The extra member is block 4, reader page
6, line index 5: a `pdftotext -bbox-layout` word split at a font change,
first differing character at index 13, exactly the run boundary. Not an
engine divergence. The genuine residual is untouched (block 135, page 47,
WP-1.2's 325.01-against-325 pt miss), and the treatment discriminates
rather than blanket-passing, still failing blocks 135 and 137.

**A correction to WP-1.7 is PENDING rather than applied.** Its delta table
mixes both normalizations, so its "968/968 at the midpoint" holds only
whitespace-insensitively. Its interval and +0.025000 pt recommendation are
UNAFFECTED, since block 4 is a constant one-line offset at every delta and
can move neither bound. The amendment waits on an independent verification
of WP-1.8, because it corrects two accepted WPs and one agent's word should
not amend the plan. Recorded now so the finding is not lost while the
verification runs.

**And an environment trap worth its line**: `TYPST_ROOT` is the typst CLI's
PROJECT ROOT, not an install prefix, and a replay failed outright on it.
Found BY the rule-12 replay rather than by the authoring run, which is rule
12 earning its cost again, and the guard is proven by replaying under a
deliberately hostile value rather than merely unsetting it.

## Revision 44 changelog

**The retrospective audit is a PROVENANCE audit, and it is cheaper than all
three options offered.** `out_dir` is hard-coded to
`output/parity/<edition>` with no override, and WP-0.2g OBSERVED two
agents' runs writing the same `verdict.json` concurrently. The dangerous
outcome is not interleaved bytes, which produce invalid JSON and fail
loudly; it is one write wholly replacing another, so a reader gets a
COMPLETE, VALID verdict from the WRONG run. That also disposes of the
option of accepting the numbers on the argument that corruption would look
obviously broken: the case that matters is precisely the one that looks
fine.
No re-runs are needed to start, because **every verdict records
`a_reader_sha256` and `b_reader_sha256`**, so a crossed-over verdict
carries the wrong artifacts' hashes.
[CORRECTED IN REVISION 49: this entry also claimed `staged_input_digest`,
which is MODE-DEPENDENT rather than universal. Checked in the source: the
field exists on the struct and is `skip_serializing_if none`, and it is
populated ONLY in the render mode that stages its own inputs. Every
`--pre-rendered` verdict, which is how most WPs run parity, sets it to
None and emits no such key, and carries no `staleness` either. The audit's
narrower power is stated in the live text.] Evidence quoting
a verdict digest AND its input hashes is checked by confirming the inputs
are the artifacts that WP claims to compare; evidence quoting only a digest
is re-run to confirm it reproduces, which a verifier does anyway; evidence
quoting neither is re-measured. A check rather than a belief, working on
records already written.
**And recorded as configuration per rule 9's spirit**: every parity number
taken before WP-0.2k lands was measured while six to nine agents shared one
output path, and that belongs with the number as much as hyphenation state
does. The window closes when WP-0.2k lands; the affected class is
parity-derived figures only.

**Rule 10a: a clause that reports HOW MUCH it compared cannot hide a
vacuous pass.** Promoted from one WP's good idea to a rule because it found
something nobody suspected: the navigation clause reports 84 annotations of
which 84 are links, and 0 outlines, 0 Title, 0 Lang, so TWO OF ITS THREE
LEGS had been passing on empty-versus-empty since it was written, invisible
until the clause was made to state its cardinality. Every Tier S clause
comparing a COLLECTION now reports its count, and the plan enumerates them
so none is missed by being the one nobody reached.

**Revision 15's rotation claim was too broad, and the narrower one is what
makes the clause matter.** "Nothing else would catch it" is false: on a
BODY-TEXT page, `text` and Tier G catch a `/Rotate 180` too, since
pdftotext reports rotated coordinates. The clause is the only one that
fails on the BLANK inside front cover, page 2 with 0 text characters and 0
images, where text, colour, navigation, glyph positions, display list and
both raster meters all pass at zero delta. So it is the sole guard on pages
that contain nothing to compare, which is a better reason to keep it than
the one originally given. Another rule 11 result: asserted, then tested by
constructing the case.

**WP-0.2k now carries four targets** (seed the digest, unconditional
refusal, the ratchet, and this revision's `out_dir` fix plus the
cardinality sweep plus the stale `raster.rs:106` pointer). Bundled because
rule 1c serialises `mag/src/parity.rs` owners so a separate WP would queue
behind it and gain nothing, and explicitly told to build in LANDED
INCREMENTS so a late blocker in one target does not strand the other three.

## Revision 43 changelog

**Rule 12 gains a clause ABOVE its third class, because the defect moved
rather than being fixed.** WP-5.3b-i fixed its absolute corpus path
properly, with an env gate that announces its mode and asserts when the
variable is set but the file is missing. The verifier then replayed the
evidence's own `## Commands` block and found the hard-coded path had
MIGRATED OUT OF THE TEST AND INTO THE RECORDED COMMAND. The test was
hermetic; the replay instructions were not, and the existing clause ("a
test must read only its own checkout") passed while its purpose failed.
**Hermeticity is a property of the WHOLE REPLAY PATH, and fixing it in one
artifact can relocate it into another.** The check is cheap and specific:
record the `$PWD`-relative form and **replay from a directory that is not
the one you developed in**, which is the only thing separating a hermetic
instruction from one that looks hermetic. Not a rejection, correctly: the
test is hermetic, the evidence warns above the command, and both PDFs are
sha256-identical so no number moves.

**Owns adjudication: a non-owner asks for an extension, it does not
self-grant.** WP-5.3b-i's `GLYPH_QUANTUM` re-export touched
`mag/src/parity.rs`, which rule 1c gives to WP-2.0b. It stays and is clean.
But the plan had ALREADY answered this for WP-0.2h's seam, where the
one-line fix "belongs to WP-2.0b, which holds `parity.rs`", so permitting
it now would contradict a decision already taken. Two reasons it is not an
exception: "behaviour-free" is a judgment the writer makes about their OWN
change, the class of self-assessment this execution keeps finding wrong;
and a `pub use` is exactly a PUBLIC SURFACE change, which is what WP-0.2h's
seam defect was, in a file another agent had uncommitted work in at the
time. The cost objection is answered by a mechanism already used five
times: a scoped Owns extension from the orchestrator, which keeps the audit
trail without queueing behind the owner.

**Rules 9 to 12 now bind VERIFIERS too.** A verifier recorded counts
exactly DOUBLED (18/462 and 236/244 against the correct 9/231 and 118/122)
and caught it itself on a later pass. Its verdict was right while its
numbers were wrong, and nothing checks a verifier except its own next pass,
so the discipline it enforces applies to it: re-derive cited counts, label
non-discriminating checks, hold causal claims as hypotheses, replay through
the artifact.

**A second example of the dual-defect shape, and the more disorienting
one**: `text_characters` moved NON-MONOTONICALLY, 34 pages gaining and 7
losing, and the 7 losers are exactly the 7 `body_text_lines` pages that had
agreed under the bug only by coincidence, because missing spaces cancelled
an extra newline. A metric getting WORSE was the tracer getting MORE RIGHT.
A future reader watching that number fall would diagnose a regression and
be wrong, which is why it sits beside the generalization rather than in an
evidence file.

Rule 3b confirmed in practice: `26391ab` was an ancestor, so the branch
carried the known-broken width computation until `80b7b62`. No downstream
number is contaminated, since WP-5.3b-ii and -iii had not started, but the
exposure was real.

## Revision 42 changelog

**Three corrections to claims the plan asserts, all from WP-0.2i's third
verification, and all strengthening rather than weakening the gate.**

**The commensurability law is `ratio = n/(8k)`, not "exact sixteenths"**,
with n the quanta and k the worst offender's glyph index; sixteenths is
just k=2. Three counterexamples killed the narrower claim (`advstep` and
`advmid` at 0.640625 = 41/64, a bump family at 1/80). A law covering every
observation beats one covering some, so this CONFIRMS commensurability more
strongly than the claim it replaces. Rule 9 applies to the propagation: any
argument citing "sixteenths" for the gate's tightness reads against
`n/(8k)` now.

**"A compensating kern fails at ANY magnitude" is not literally true, and
rule 10 requires saying so.** A mid-show bump family at seven magnitudes
found a DETECTION FLOOR between 9.16e-08 and 9.16e-07 pt: 2Q, Q, Q/2, Q/4
and Q/100 all fail with 40 violations each, Q/1000 and below go invisible.
Size-independence survives everything that matters, since the floor sits
about 7,000x below one Pango tick and is unreachable by any real engine
difference, but the plan has stated the stronger claim since revision 15
and it is load-bearing, so it now says "every physically reachable
magnitude, with a measured floor at X". Kept beside it is the MECHANISM,
because it corrects a natural wrong intuition: one expects a half-quantum
bump to round away, and it does not, because base offsets spread across the
quantum grid so among ~68,800 glyphs some always cross a boundary.

**A plan premise is falsified under rule 11**: the plan assumed pypdf
perturbation cannot produce display-list-equal fixtures, which is why the
CTM-composing recommendation took its shape. The verifier measured
`display_list` = PASS on the drift fixtures, so it demonstrably can, and
the recommendation inherited from revision 39 is substantively DISCHARGED.
Fourth plan claim retired by remove-the-cause-and-measure.

**A FOURTH cross-spike count disagreement, and a rule that finally sits
where the failure happens.** The plan says 69,071 glyphs / 1,503 shows, the
floor measures 68,800 / 1,488. Revision 38 put the duty on an author
deriving a count from its own enumeration, but all four disagreements were
found by a READER comparing two documents, never by either author. **So a
CITED count is re-derived at the point of citation**, which is the moment
the two numbers meet and the moment nobody checks. A hypothesis is offered
for this one rather than an answer (rule 11): the gaps are 15 shows and 271
glyphs, the plan already carries 1,488 independently from WP-0.2b over the
54-page INTERIOR domain in three places, and the covers carry invisible
`3 Tr` text on both faces, so the larger figures may simply count all 56
pages. One measurement settles it.

**Three rejections on WP-0.2i, all on the RECORD rather than the
mechanism**, and the pattern deserves stating. The gate's logic has now
survived a quantum defect, an unrepresentative floor fixture, and a
deliberate seven-magnitude adversarial attack by a verifier trying to break
it. What keeps failing is the evidence: a floor generator living only at an
absolute scratch path that `exec`s a second scratch file, a `## Commands`
section contradicting its own Residuals, a run loop omitting two fixtures
it claims to cover. Rule 12 was added after two instances and this is more,
so it is worth stating plainly: **for the gate specifically, the artifact
IS the evidence**, because the gate is the one thing in this plan nobody
can re-derive from the code alone.

Noted with satisfaction: revision 41's fourth landing check fired on the
verifier's own land, confirming it catches real events rather than a
hypothesised one.

## Revision 41 changelog

**The mechanism behind both index contaminations is systemic, so the
landing protocol as written could not have prevented them.** Agents commit
from a private worktree and move the branch with `git update-ref`, which
moves the ref and nothing else. The main tree's index still holds the
PRE-LAND content of every file the landing commit touched, so **the index
is left staging a precise reversion of the commit that just landed**, and
any bare `git commit` from the main tree by any of eight agents would
silently undo the whole WP. Syncing the working tree with
`git show HEAD:<path> > <path>`, which the protocol already instructs,
updates the working tree and leaves the index untouched, so following the
protocol exactly still left the trap armed.

**Fourth landing check, owed by the agent that LANDS**: after moving the
branch, `git diff --cached --name-only` must return nothing, cleared with a
PATH-SCOPED reset if not. The constraint is stated beside it because it
nearly bit: paths only, never a bare hard reset and never a path-scoped
checkout, since other agents have uncommitted work in that tree (WP-0.2g
had 43 insertions in `mag/src/parity.rs` plus three more files sitting
there as this was written). A path-scoped checkout and `rm` are denied by
policy here; a hard reset is not, so the rule forbids it.

**The generalization: the landing checks verify what you WROTE, not what
you LEFT BEHIND.** All three earlier checks examine the landed commit,
while this hazard lives in the shared tree's index and only becomes a
defect on the NEXT agent's commit. It also re-explains both earlier
clobbers better than agent error did, since `aa4bc01` and `4f20801` are
each a stale index carrying old content forward, and it moves the burden
from the innocent committer back to the agent that armed the trap.

**A third tool carries the same trap, found by the planner walking into
it.** `git stash push -- <pathspec>` looks narrow and is not: the stash's
INDEX commit snapshots the whole staged state, so a stale index rides in
and is dropped with the stash. The diagnostics differ as well,
`git show <stash> --name-only` showing only the worktree half while
`<stash>^2` holds the index half. Nothing was lost in that instance,
because what rode along WAS the reversion already cleared, and that was
VERIFIED by comparing the stashed content against the pre-land state rather
than assumed. Recorded because the shape generalises: a narrow-looking
operation on a shared tree is wider than it reads.

**And a gap nobody had decided: a REJECTION does not remove anything from
the tree.** WP-5.3b-i's rejected commit `26391ab` is an ancestor of
`a537a24`, so the defect was live on `art_directed` and the rework repaired
SHIPPED code. That is fine for an evidence-only rejection where the code is
sound and only its record is not; it is not fine silently for a code-defect
rejection, because other WPs build on the branch. Rule 3b now requires a
rejection to state whether the defect is LIVE ON THE BRANCH and, if so, to
name the consumers who must not build on it until the rework lands.

## Revision 40 changelog

**The content-final gate is removed, and NOT for the reason it was
questioned.** The proposal was that the digest guard already discharges it
mechanically. Verifying rather than trusting that premise, as the question
itself asked, showed the guard does not currently do what the argument
requires:

- `baseline.json` holds **zero page entries and a null
  `staged_input_digest`**, so `staleness()` returns `"unseeded"` on every
  run today and guards nothing.
- The refusal is **conditional on `--set`**. A bare `mag parity 010` on a
  moved corpus records the staleness and CONTINUES; only page-set scoring
  is skipped.
- **No per-page ratchet comparison exists** anywhere in
  `mag/src/parity.rs`. The bail message promising that "ratchet comparison
  [is] refused" describes something never built.

So "corpus stability is already enforced in code" was false as implemented.
The mechanism was specified and never completed, and the human gate had
been standing in front of that absence.

**The gate still goes, because it fails the plan's OWN test.** Rule 7 says
a Fran gate exists only where the plan must change or something is
irreversible. Freezing a corpus so a ratchet means something is neither. On
the two readings of "content-final": the plan means STABILITY, which is
mechanisable, not a PROMISE about future editorial intent, which no digest
can supply and which no human can truthfully give either. A promise would
reduce the probability of rework, not prevent it, and every path to
invalidation is loud once the digest is seeded. That is not worth routing a
plan's critical path through a person.

**It is replaced by a mechanical precondition rather than deleted**, since
deleting it would leave Phase 3 gated on nothing while its stated
verification remains inexecutable. **WP-0.2k** seeds the digest, makes the
refusal unconditional, and implements the per-page ratchet that the Phase 3
preamble and WP-3.0g both assume. The finding worth carrying beyond this
decision: **Phase 3's verification was not executable today for reasons
that had nothing to do with Fran**, and the human gate concealed that,
because a phase blocked on a person is not examined for whether it is also
blocked on code.

**Nothing is being asked of Fran, and one thing is worth telling him.** Not
a gate, purely informational, one sentence: *if you intend to revise
edition 010's text, saying so before Phase 3 scores pages saves redoing
that scoring, because every per-page attribution is tied to the exact
staged inputs it was measured from.*

**WP-1.8 moved out from behind the gate.** WP-3.1 was carrying the
unreconciled 147/149 versus 148/149 count, which is a measurement someone
can do TODAY and which was scheduled behind a human gate for no reason.
Third instance of this class, and rule 9 exists because of the first two.
Its standing hypothesis, held as a hypothesis under rule 11 rather than
recorded as an answer, is that WP-1.7's harness lacks the styled-run
preservation that took WP-1.2 from 147/149 to 148/149. WP-3.1 keeps
WP-1.2's break miss, which genuinely needs the engine.

## Revision 39 changelog

**Rule 9's propagation failure, in a second medium: the argument was
revised and the SPECIFICATION beside it was not.** The plan's prose has
said since revision 15 that the raster guard is withdrawn and Tier E is
wholly geometric, and revision 21 even rebuked WP-5.4 for citing
"WP-0.2f's derived bound" as an artifact that never existed. But
`### WP-0.2f` itself still said: own `tiers.e.raster_bound`, select a
rasterizer, derive the bound under the two-sided constraint. An agent finds
its own WP section and executes THAT, not the changelog, so the executable
instruction contradicted the argument for three revisions. Nobody re-reads
a section they have already decided about.

**Decided: WHOLLY withdrawn, selection included**, which revision 15 left
implicit. The guard is gone, rasters survive only as Tier V meters, meters
GATE NOTHING, and `pdftoppm -r 300` is already implemented by WP-0.2c and
pinned by WP-0.1, so there is no requirement a different rasterizer would
satisfy and nothing left to select. The section is kept rather than deleted
because its measurements must not be repeated and because a deleted WP
leaves a dangling id in eleven places, but it now opens with **do not
execute this section** and points at WP-0.2i.
Every dangling consequence is closed: `tiers.e.raster_bound` is authored by
NOBODY and holds only WP-0.2d's blocked record; `mupdf` 1.26.4 is installed
but deliberately NOT pinned, so nobody adds it to the toolchain; the floor
and ceiling fixtures are superseded by WP-0.2i, which inherits the `drift`
fixture and the CTM-composing recommendation. The Tier V bullet no longer
promises a pending selection, WP-0.2d's pointer says the destination was
withdrawn, and revision 13's now-void conditional carries a marker. The
discipline generalises: **when a decision withdraws work, grep for the WP
id and check every hit**, exactly as correcting an enumeration means
grepping for its count.

**The straddle rule binds on INHERITANCE, not only on authoring.** Third
instance of the finding and the first in inherited rather than authored
code: WP-5.4b fixed its own deck fixture, and its verifier then found the
same weakness in the HEADLINE refusal it had inherited, which guards two
numbers and discriminates on one (line limit `<= 3` to `<= 6` fails the
test; size floor 20.0 to 15.0 leaves all eleven passing, because the string
sits far enough past the boundary to refuse under a 25% looser floor). A
rule binding only at authoring time exempts every inherited fixture, and
inheritance is common now that WPs re-cut, so successor WPs SWEEP what they
adopt. **WP-5.4b-i** owns the fix, `mag/tests/cover_*` only; the id is
adopted as dispatched.
Recorded because it is the distinction that kept this from being a
rejection: WP-5.4b's evidence claimed only that three of six refusals were
perturbed at their threshold and never asserted the others discriminate, so
rule 10's labelling duty was met. The remaining two are categorical with no
number to move, which the message-only classification covers correctly.

## Revision 38 changelog

**A count that never matched its own enumeration, and it would have cost a
fault.** The plan said "ten issue sites" in prose while the enumeration
beside it listed ELEVEN (`text_order_matches` 3, `blank` 3, `ink_free` 3,
`standalone_punctuation_lines` 1, `body_text_lines` 1). Counted
independently here against `render_critic.py` before correcting, since the
last thing this needs is a third number: eleven is right. WP-5.3c is
briefed off that count and owes fault coverage per site, so at ten it would
have left one unfaulted. The derived figure "the other nine sites" was
wrong for the same reason and is now ten.
The history is the instructive part: the enumeration was corrected in an
earlier revision and the count next to it was not. So **rule 9 gains a
clause: a COUNT stated beside an enumeration must be DERIVED from it, not
carried alongside it.** When correcting an enumeration, grep for its count;
when quoting a count, add up the list.

**Rule 12 gains a third artifact class: a test must read only its OWN
checkout.** `mag/tests/critic_text.rs:74` hard-codes an absolute corpus
path, the only test in the repo that does, so from an isolated
verification worktree it traced the MAIN tree's PDF while exercising the
WORKTREE's code, and anywhere else it would silently skip. Both outcomes
measure something other than the artifact under test, which is rule 12's
family exactly, and since EVERY verification here runs from an isolated
worktree, one absolute path silently invalidates a verification. Paths stay
relative to the checkout, or the corpus arrives through rule 2b's env-gate,
which announces its mode.

**Rule 10 gains its sharpest instance, and it found a CODE defect rather
than an evidence one.** WP-5.3b-i honestly labelled its join rule
non-discriminating on 010. Its verifier ran the OTHER extreme, an
unconditional empty join that the evidence never ran, and that passed too.
Both extremes passing meant the field was less discriminating than even the
honest label claimed, and that pointed at the cause: the rule subtracts
`Show.width`, in GLYPH_QUANTUM units of 9.1552734375e-05 pt, from `Show.x`,
in hundredths of a point, inflating width by 109.2267x. So the rule-10
label was true of the CODE, not of the corpus. The guidance added: **when a
fixture is labelled non-discriminating, run the opposite extreme too, and
if both pass, ask whether the code under test does anything at all.**

## Revision 37 changelog

**A wrong number, an instrument that cannot discriminate, and both were
the plan's rather than the WP's.**

**The QR decline boundary is 78 characters, not 154.** WP-5.5a falsified
its own landed finding: 154 traced `_opener_credit_code`, a MEASUREMENT
path fixed at 55.5 pt, while PRODUCTION is `_opener_source_codes` at
41.0 pt for illustrated openers, and all nine of 010's articles are
illustrated. 010's longest payload is 67 characters, so the compared
edition is still inside, but the margin is ELEVEN characters rather than
eighty-seven, which is close enough that a new source URL could cross it.
The historical changelog entry is marked rather than rewritten.
**The 9-of-9 agreement survives and is stronger than when the decision was
taken**: the chosen level and module count are now proven ROOM-INDEPENDENT,
499 payloads at six rooms with zero disagreements against 387 for a
deliberately room-dependent control, so the asset decision rests on a
property of the fit rather than a fact about 010.

**I specified an instrument that cannot discriminate.** Sanctioned oracle
changes were required to compare "byte-for-byte across BOTH the web tree
and the reader PDF", and the reader-PDF half is unsatisfiable by ANY change
including no change at all: rendering the unchanged tree twice yields PDFs
differing in 420,296 bytes, because cairo writes per-run image XObject
names inside compressed streams. The reader-PDF leg is now verified with
`mag parity --pre-rendered`; the web tree genuinely is byte-comparable and
that half stands. WP-5.5a reported it as a BROKEN INSTRUMENT rather than
reporting a pass, which is rule 10 applied to a tool rather than to
evidence, and is exactly the behaviour the plan wants from a WP that finds
its own check useless.
**Checked rather than assumed, since the same defect would hide anywhere
else it appeared: no other clause rests on PDF-byte stability.** The ladder
opens by stating two engines never produce byte-identical PDFs, WP-0.0
recorded that byte-determinism is not assumed, WP-0.1's whitelist already
treats render-critic.json's PDF hashes as run-to-run noise, and WP-5.5c's
SHA256SUMS oracle digests the SAME files from both implementations rather
than comparing across renders. The plan was consistent; one requirement of
mine was not.

**Two records.** A second Owns extension for WP-5.5a, to `mag/src/render.rs`
for a roughly 15-line `stage_source_codes` row, because the renderer stages
only DECLARED inputs and `source-codes` is not among 010's 47, so the
committed asset would be invisible; flagged because `render.rs` is rule
1b-serialised and WP-5.6 inherits it. And a latent Python bug the port must
NOT fix: `_opener_credit_code` sizes the field floor from a symbol fitted
at 55.5 pt that production places at 41.0, so a payload between 79 and 154
characters exposes the inconsistency. Revision 23 forbids a port stricter
than its oracle, so it is reproduced, and it is recorded so nobody later
reads it as a port defect. One for Fran's product list beside
`studio.ready`.

## Revision 36 changelog

**A refusal matrix can exercise every raise site and prove no threshold.**
WP-5.4b applied revision 35's ask-the-oracle method to its deck-overflow
gap, got a fixture immediately, and then tested the fixture rather than
trusting it: twelve contributors wrap to ten lines, so moving the refusal
limit from 5 to 8 STILL REFUSED. The fixture sat so far past the boundary
that it would have refused under any plausible rule. It measured the wrap
counts, tightened to seven contributors at exactly six lines, added a
companion pinning the fitting side at five, and the test now flips when the
limit moves by ONE. Same perturbation applied to the wordmark floor (25.0
to 20.0) and title floor (12.0 to 8.0); both fail properly.

The general point is new to this plan and correct: **full-message equality
is cheap to satisfy and proves less than it looks.** It proves the message
text and that SOMETHING refused; it does not prove the threshold is right
unless the fixture sits near the boundary.

**Sharpened from "perturb the threshold" to "the fixture PAIR must straddle
the boundary"**, one refusing input and one passing input differing by one
step, because that is what WP-5.4b actually converged on and it is the
stronger statement: a pair is a property of the FIXTURES needing no code
mutation, and a tight pair necessarily flips when the threshold moves by
one, which is how you verify it is tight. Perturbation becomes the check on
the pair rather than the requirement itself.
**And scoped, so nobody burns time on it:** evidence classifies each
refusal as THRESHOLD-DISCRIMINATING or MESSAGE-ONLY, and message-only is
COMPLETE where there is no number to get wrong. For an unknown enum value,
a missing key or a type mismatch, message equality is the whole property.
The rule binds numeric guards only.

**Retroactivity: classification, not re-opening.** Four accepted WPs rest
on large matrices compared by full-message equality (WP-5.1b's 54 cases
with 44 refusing, WP-5.1c's 89 of 91 raise sites over 74 fixtures producing
122 messages, WP-5.5b's eight `_box_invalid` conditions, WP-5.4b's three
originals). None is WRONG, and a message-only refusal test is weak evidence
rather than false evidence, so they are not re-opened. But each should
CLASSIFY its refusals, which is a cheap read of the raise sites and turns
an unknown weakness into a sized one, which is the whole point of rule 10.
**WP-5.1c's classification is the one that should actually happen rather
than being optional**, because `manifest.py`'s raise sites include page
caps and budgets, which are exactly numeric thresholds and are load-bearing
for the plan's own seven and ten page rules.
This disposition is PROVISIONAL in one respect, and the thing that would
change it is already running: WP-5.4b's verifier is applying threshold
perturbation to that WP's three PRE-EXISTING refusals. If those also fail
to discriminate, the weakness is common rather than specific to one
over-wide fixture, and the four accepted WPs need fixture work rather than
classification. Naming the trigger now so the answer is read against it.

## Revision 35 changelog

**Rule 12 generalises, because the same error arrived in a second form.**
An evidence file's `## Commands` block, extracted verbatim and executed,
does not run: three rejections now on work that was otherwise CORRECT.
WP-5.1b's unrecorded oracle provenance, WP-5.4's zone oracle with no
producing command, and WP-5.4b, whose recorded oracle PANICS because
`rb"..."` is a raw bytes literal so the escaped quotes insert literally and
resvg rejects the SVG at char 92, and correcting only the escaping
reproduces
all three digests exactly. The cause is the same every time: an agent runs
a command, then TRANSCRIBES it, and the two diverge precisely where quoting
and escaping live, which is exactly where a reader cannot see the
difference by eye. The transcription is the failure, not the command.

That is the same shape as the `#[path]` seam defect, and the plan takes the
generalization rather than adding a second rule: **a demonstration must be
performed through the ARTIFACT THAT WILL BE REPLAYED**, meaning the
exported path or the recorded command, and not through whatever the author
had at hand.
Both instances are "it worked when I ran it" where the thing that ran was
not the thing recorded, and in both the evidence was ACCURATE about what it
measured while measuring the wrong thing. One rule with two named artifact
classes, because this execution has repeatedly shown that a fix aimed at a
form lets the next form through, and two rules would invite "that is rule
12's problem, not mine". The concrete checks stay concrete: a consumer test
that imports the ordinary way, and extracting each `## Commands` block from
the file itself and executing it before submitting. The second costs one
round trip per block and pairs with rule 3, since replaying `## Commands`
is exactly what the verifier does, so the author simply does it first.

**And a reusable technique from the same verification**: for REFUSAL
coverage, ask the ORACLE which inputs it refuses rather than reasoning about
which are reachable. WP-5.4b understated its refusal coverage (six `bail!`
sites, three tested, one disclosed, two neither) and argued its way out of
deck-overflow coverage when it had already solved that exact problem for
the headline by asking Python which strings it rejects. Enumerating
refusals by reading the Python's raise sites is the same move as
enumerating branches by reading the Python, and it is cheaper than arguing
about reachability.

WP-5.4c's siting is independently confirmed: `mag/src/cover/` has no PDF
module, the `pdf` matches in `svg.rs` being coordinate variables.

## Revision 34 changelog

**The cover PDF writer does not exist, and the honesty section is how we
know.** WP-5.4's `## What is and is not proven` listed it as not built,
WP-5.4b confirmed `mag/src/cover/` holds no PDF module, and all three
layouts are therefore proven at SVG-and-raster level only. That section
became mandatory in revision 27 precisely because claims kept outrunning
evidence; this is its first real test and it moved a discovery from
integration time to planning time. Revision 21's guard, that the writer be
written GENERALLY so WP-5.4b would add coverage rather than a second
writer, could not be applied by WP-5.4b, because there was nothing to be
general.

**It becomes WP-5.4c rather than a re-opened WP-5.4 or a fold into
WP-5.6.** Not WP-5.4b's, whose remit was the corpus-unreachable MODES and
which delivered them. Not a re-opened WP-5.4, which is accepted and whose
evidence was accurate. And explicitly not folded into WP-5.6: that WP's job
is integration, and a WP that both writes new code and integrates five
others is how blocked-on-everything WPs are made, which this execution has
already demonstrated with the original WP-5.5. **WP-5.6 now depends on
WP-5.4c rather than WP-5.4**, which is the edge that would otherwise have
failed at integration with no cover at all.

The gap is small and precisely sized: raster, outlines, zone statistics and
the invisible layer are all proven, and only the assembly step is missing,
with its shape already described in WP-5.4's evidence. Revision 21's
"generally, not per-mode" guard re-attaches to WP-5.4c, which writes for
all three modes at once using WP-5.4b's fixtures as coverage.

**Its oracle is the RENDERED RESULT, never the embedded stream bytes**, for
the reason WP-5.4b already established when it declined to compare SVGs:
Rust and Python encode the graded-art PNG differently, base64 diverging at
char 448 while the rasters hash equal. Tier E already behaves correctly
here, since the display list hashes DECODED RGBA rather than encoded bytes,
so a different PNG encoding passes while a different picture fails. That is
the same structural principle the plan applies elsewhere, arriving at the
same answer from the image side.

## Revision 33 changelog

**Two corrections to revision 32, both found by measuring instead of
reasoning by analogy, and the second inverts the conclusion.**

**The QR asset format was underspecified.** Revision 32 said payload and
level. The print path uses segno TWICE per code, a SEARCH in
`_fitted_source_code` (:1907) looping H, Q, M, L for the largest module and
a REDRAW in `_source_code_matrix` (:1920), and every search input is a
constant, so the asset must record payload, chosen LEVEL, MODULE COUNT and
matrix: without `modules` the search re-runs, and it feeds layout through
`module = room / modules` and `side = quiet * module`. The format also
needs a PRINT-DECLINES state, because the legs agree to 154 characters and
[CORRECTED IN REVISION 37: the boundary is 78, not 154; the 154 figure
traced a measurement path rather than production. The entry is left as
written because a changelog records what a revision claimed.]
diverge at 155, where at most 55 modules fit in 55.5 pt against v8's 57 and
print draws NOTHING; without that a future long URL reads as a missing
asset rather than a correct outcome (010's longest payload is 67). And the
9-of-9 agreement is now EXPLAINED rather than observed: the fit maximises
module size, minimising version, and among ties keeps the earliest of
H, Q, M, L since no tie exceeds epsilon, which is segno's boost rule. That
both legs pick the same level AND version was unverified when the decision
was taken; it now has a mechanism (rule 11). Leg 1 has an Owns extension to
`web_edition.py` and `weasyprint_adapter.py` for the asset-reading change,
recorded alongside WP-0.0b, WP-0.0c and WP-1.5, and noted as HEAVIER than
those since Appendix A deletes the adapter at WP-6.1 and the whole parity
comparison runs through it.

**Pygments: revision 32 was wrong in both halves, and the correction goes
the opposite way from where it was heading.** Measurement ruled out
`syntect`, which revision 32 named as the likely implementation: the
formatter is trivial, the LEXERS are the whole cost (8,559 spans, 31
classes, nine languages), and syntect does not match pygments'
tokenisation. That prompted checking the other half, the print-path
"precedent" revision 32 leaned on, and it does not say what was assumed.
`html_edition.py:660` highlights the PRINT path through the same
`_highlight_code`, the print CSS colours those classes, and Tier S compares
(text-run, fill colour) sequences, so a different tokenisation produces
different colours and FAILS THE GATE. The print clause is therefore
STRICTER than the web question, not a licence for a weaker answer to it,
and the analogy was backwards.
What genuinely relaxes the cost is derived from the clause rather than
conceded: the gate compares COLOURS, not class names, and the print CSS
collapses 31 classes onto about seven values. So the requirement is to
reproduce pygments' tokenisation UP TO THE EQUIVALENCE THE COLOUR MAP
INDUCES, and whoever implements highlighting measures that equivalence
first, because the cost is set by colour classes and not by token classes.
The WEB bar is left contingent rather than decided in the abstract: web
byte-identity needs class NAMES where print needs only colours, so if the
print-forced implementation reproduces classes exactly the web comes free,
and if it reaches only colour equivalence the class attributes are a
declared divergence with the code TEXT byte-identical either way. None of
it lands now, since 010 carries no fenced code and the cost arrives with
WP-3.3's fixture edition.

**Sequencing recorded**: WP-5.5a's remainder is the largest single piece
left in Phase 5, about 1,600 lines at a byte-identical bar, and 010
exercises a narrow slice, with `_render_editorial`, `_render_section`,
`_render_extract`, `_extracts_by_anchor`, `_render_key_ideas` and
`_highlight_code` all corpus-unreachable, so the FIXTURE SURFACE WILL
EXCEED THE CORPUS SURFACE. Built in landed increments rather than one pass.

## Revision 32 changelog

**The duplicate audit is TUNED, not doubted, and the tuning matters because
a tool made someone rename correct code.** A (name, signature) key fires on
`load`, `new`, `open`, `read`, `write` and `default` forever; it caught
`load` in two unrelated modules and WP-5.5b renamed its own function to
`Pdf::read` to get past it. Before changing a key, note what each one
catches: the BODY key catches an exact copy before it drifts, and the NAME
key IS the drift detector, since a drifted copy has an unequal body by
definition, which is how WP-5.1c's pre-fix `py_repr` would have been seen.
So requiring body similarity too would delete the audit's whole purpose,
and letting the allowlist grow turns the signal into noise a real duplicate
can hide in. The key becomes an explicit **REGISTRY of names the shared
module owns**, which may not be defined elsewhere, with nothing else firing
on name: exact rather than heuristic, no false positives on ordinary Rust
vocabulary, and it enforces precisely the rule the plan already states.
Growing a registry is a deliberate act; growing an allowlist is an apology
for a bad key. **And the principle the rename exposed: a tool that makes
you rename CORRECT code is mis-specified, and the fix is the tool.**
WP-5.5b's rename should be revisited on its own merits rather than left as
a monument to a false positive.

**The QR cost was misstated and the route changes, though the logic does
not.** Reproducing segno's pad byte means owning the bitstream, the
Reed-Solomon ECC, mask selection and matrix layout, because `qrcodegen`'s
padding is internal with no hook. So the preferred route is now to treat
the QR SVGs as committed ASSETS for the compared edition and use a
SPEC-CORRECT encoder for new work: both legs read the same asset, Tier E is
satisfied, nobody owns a bug-compatible encoder, and future editions get
correct codes. Two supporting facts are verified here (the payload is a
pure function of `source_url`; the print error level is chosen by a fitting
loop, so an asset must record the LEVEL), two are not and the WP proves
them before committing (that both legs can read the asset, via a sanctioned
oracle change that must render byte-identical; that nothing else
regenerates a code). Falls back to owning the encoder as its own WP.

**Pygments is decided on its own terms, and explicitly not by analogy.**
Revision 30 turned on the QR modules being inside Tier E's compared domain;
highlighted code is `<span>` in the WEB TREE only, which no ladder clause
inspects, so no gate forces reproduction. Highlighted code is therefore
compared STRUCTURALLY, same token boundaries and class names so the CSS
colours it identically, and the web-tree oracle is restated as
byte-identical EXCEPT those spans. This is consistency rather than a new
concession: the plan already compares pygments against syntect at the
(text-run, fill colour) level for the print path and never at the markup
level.

**Two records.** WP-5.5b's f32 enumeration is the clean counter-case to
WP-5.2's, showing the hazard can be DISCHARGED by enumeration rather than
fixed everywhere: every parsed number flows only into
`near(size, expected, 0.75)` with margins 17,595x to 28,550x the tolerance.
And `studio.ready` looks UNREACHABLE for any input, since `studio_blockers`
is seeded unconditionally and never emptied, which is rule 10's family in
the PRODUCT rather than in the evidence: a preflight result that is a
constant dressed as a measurement. If confirmed, the port still reproduces
it, because the Python is the specification, and it is flagged to Fran as a
separate product question.
**A third joins that list, and it is the plan's first named class-C item**
(rule 6a): `label: false` in a manuscript prints the literal string
`"False"` as a section label in BOTH engines, executed rather than read, so
every tier passes and parity is blind to it by construction. Class C is the
class this plan cannot find, which is why the one instance it does know
about is written down rather than left to imply that none exist.

**And WP-5.5a's landed increment validates revision 26's strong form.** Its
four matchers are pinned to PYTHON, not to the author's reading, and that
caught two of its own bugs: a naive structural rewrite would have DELETED
the 18 `source-link opener-source-link` elements in 010's shipped web tree,
which is the exact defect this work exists to fix, inverted.

## Revision 31 changelog

**A third form of one failure, and this one was the planner's.** Revision
29 (`4f20801`) had `c084e16` as its direct parent and REVERTED
`meta/verification/evidence/WP-5.4.md` by exactly the inverse diff, 16
insertions against 65 deletions, removing the zone-oracle provenance
command and the replay hazard that WP-5.4 had been rejected TWICE for
omitting. Restored verbatim as `c5d35f7`, confirmed here as a zero-byte
diff against `c084e16`.

**The fix written for the previous form did not catch it, and the reason
generalises.** Revision 25 required confirming the files you expect are
PRESENT in the resulting tree. `WP-5.4.md` was present. Present and
reverted. **Presence is not content.** Three incidents now, each fix aimed
at the form before it: ancestry passed while 39 files were deleted;
presence passed while a file was reverted; and in both the landing agent's
own checks reported success. Each check verified something ADJACENT to what
mattered, which is why each new form slipped through: ancestry verifies a
commit's presence in history rather than its content's survival, presence
verifies a file's existence rather than its content.

**The check that covers the class is stated about the DIFF**: after
landing, `git show --stat <your sha>` and confirm the file list is EXACTLY
your Owns, no more and no fewer. A deletion, a revert and a stale rider all
appear the same way, as a file you do not own inside your own diff. It
pairs with the pathspec discipline rather than replacing it, since a
pathspec stops contamination going in while the stat check catches it if it
does, and a pathspec can be right while the working copy is stale. On
`4f20801` it would have taken one line and one second.

**And an Owns gap that is the planner's to answer for**: a plan revision
owns the plan file and NOTHING else, so revision 29's diff was rejectable
under rule 1 before any verification. The orchestrator diff check was being
applied to worker and verifier commits but not to plan revisions; rule 1
now says explicitly that it applies to all three.

## Revision 30 changelog

**The QR question is decided by the GATE, not by preference, and checking
rather than assuming is what decided it.** WP-5.5a found segno's matrices
irreproducible because segno is wrong: `segno/encoder.py:330` appends eight
spurious zero bits when the stream already sits on a codeword boundary,
where ISO/IEC 18004 section 7.4.10 adds none, with segno's own docstring
quoting the clause above the line that breaks it. In byte mode the stream
is always congruent to 0 mod 8, so the extra zero byte is always injected,
displacing a pad codeword and changing every ECC codeword.
The disposition offered three options and framed it as a web-tree
question. It is not: `weasyprint_adapter.py` calls segno too
(`_fitted_source_code` at :1902, `_source_code_matrix` at :1918, whose
matrix is drawn into the reader), so **the QR modules are inside Tier E's
compared domain**. A different matrix is different path geometry and the
gate fails on it. Option (b), keeping payload, version and level but not
the matrix, is therefore unavailable for print without weakening Tier E,
which rule 4 forbids; and since print needs matrix equality anyway,
applying (b) to the web alone would buy nothing while splitting the
implementation in two. So **(a)**: reproduce segno's non-ISO pad byte as
one documented deviation with its own test.

**On the "reproduce a hack" objection, upheld four times before now: the
asymmetry is real.** Those four governed output nobody inspects (pypdf's
line merging, a crash's traceback, reportlab's subset bytes, pypdf's line
breaking). This governs a VISIBLE artifact, a pattern of squares on a
printed page. Reproducing a deviation to keep a visible artifact identical
is a different act from reproducing one to keep an invisible intermediate
identical, and the plan now says so where the next person will look.

**The product question is Fran's but does not block.** Whether the magazine
should ship spec-correct QR codes rather than segno-compatible ones has the
exact shape of the hyphenation decision: parity reproduces the old
behaviour, the deliberate improvement is measured afterwards with its own
before and after. Named as a post-flip item alongside WP-4.3. Nothing waits
on it, which is why this did not need escalating to unblock WP-5.5a.

**Cited as the reference application of rule 11**, because it is the best
in this execution: the mechanism was tested rather than asserted, by a
controlled experiment showing that removing the cause removes the effect (0
modules differing with no pad codewords, 158 with twelve), and then used to
PREDICT three fresh cases it was not built from, correct in all three. Rule
11 exists because two earlier mechanisms were asserted and later falsified;
this is what discharging it looks like.

**A protocol hazard found by committing it.** `git commit` commits the
whole INDEX, not the paths you added, so under concurrency another agent's
staged files land inside your commit under your message. The planner did
exactly this in revision 29, carrying WP-5.4's evidence into a docs commit.
Nothing was lost and the content was that agent's own, but the attribution
is wrong and a mid-edit file could have landed. Commit with an explicit
pathspec, or check `git diff --cached --name-only` first.

## Revision 29 changelog

**A demonstration whose harness grants a capability production lacks.**
WP-0.2h built a shared tracer seam for the critic and proved it through a
`#[path]` test include, which bypasses module privacy entirely. The
demonstration passed, its verification confirmed the demonstration, and the
seam was still unusable from the only place it was built for, because
`mag/src/parity.rs` declares `mod display;` and `mod streams;` privately
with no `pub use` and the first real consumer gets
`error[E0603]: module 'streams' is private`. **The mechanism that proved
the seam was the one mechanism that routes around the defect.**
That is neither rule 10 (a claim outrunning its evidence) nor rule 11 (a
mechanism asserted without test): the evidence was accurate about what it
measured, and what it measured was the wrong path. **Rule 12** therefore
requires a capability to be demonstrated THROUGH THE PATH ITS CONSUMER WILL
USE, with a consumer test that imports the ordinary way, and requires a WP
reaching for `#[path]`, relaxed visibility, a test-only feature flag or an
altered search path to say in evidence why and what it has therefore NOT
shown. WP-2.0b holds `parity.rs` and carries both the one-line export and
the consumer test.

**WP-5.3b is re-cut into -i, -ii and -iii** along the dependency seam,
because the critic's decisions span 31 issue sites and a partial port
yields a partial decision set that cannot be compared against Python's full
one. There is no smaller honest unit meeting the stated oracle, so the
choice was to split or to weaken, and splitting is free. Only -iii meets
the decision-level oracle, so WP-5.3c and WP-5.3g depend on it rather than
on the family.

**What WP-5.3b achieved before blocking improves on what the plan said**,
and it did it by re-measuring against the CURRENT tracer rather than
inheriting WP-5.3d's numbers, which is rule 9 working rather than being
cited: text-emptiness now agrees **56 of 56**, up from 54 of 54, because
WP-0.2h's standard-14 decode gained the two cover pages, and it reproduces
pypdf's exact 7-empty / 49-non-empty partition, so it DISCRIMINATES. The
seven `body_text_lines` differences were CONFIRMED as one cause rather than
inherited, by reading pypdf's own output and finding two merged two-line
headlines. And its join rule is labelled under rule 10 as NOT
discriminating on 010 (184 of 1,263 lines carry multiple shows; empty-string
and geometric joins give identical emptiness and `body_text_lines`), chosen
because principled rather than because the corpus can tell. That label is
the plan's reference example of rule 10 used well.

**The Unicode residual gets an owner rather than a note**: `body_text_lines`
uses `char::is_lowercase`, unpinned, so a page containing U+1C89 could
diverge. Unmeasured, revision 22's rule covers it, and
`mag/src/model/shared.rs` already holds the pinned tables, so WP-5.3b-i
pins it or demonstrates whole-plane agreement and says which.

**Two batched items fold in here** under the cadence standard. Rule 3a:
to prove an ACCEPTED oracle did not move, hash the git BLOB across the
range rather than re-running, since git is content-addressed and a constant
blob hash proves the file never changed ANYWHERE in the range, where a
re-run proves only that it produces the same result now. And the dual-defect
generalization, which is better than what revision 24 recorded: the
transposed constant was invisible to STRUCTURAL comparison and visible to
pixels, the luma defect was invisible to PIXELS and visible only to a direct
assertion against Python's numbers, so what generalises is that **a defect
can be invisible to any given oracle level**. That is the argument for a
layered gate, and it changes the oracle designer's question from "structural
or photometric" to "what is invisible at this level, and what sees it".

## Revision 28 changelog

**A test that passes without testing anything, and nothing forces it to say
so.** WP-5.2's `imposition_matches_python_on_the_live_edition` is env-gated
and passes VACUOUSLY under a bare `cargo test`; its verifier put the defect
exactly right, that a reader seeing "4 passed" would believe the live
edition was compared. The WP is fine, its real run recorded at 1527
seconds. What is wrong is that the two modes are indistinguishable in the
output. Env-gating is the RIGHT mechanism, since the corpus lives outside
the repository, and the both-or-neither shape from WP-5.1a is the right
shape; the defect is purely the silence. This is rule 10 one layer down, a
vacuously passing test being evidence that cannot discriminate, so rule 2b
now requires an env-gated test to ANNOUNCE which path it took and its
evidence to record both the gated result and the command producing it.
Binding on WP-5.5b, WP-5.5c and WP-5.3b, all of which need the same
untracked run directory and would otherwise reach for the silent shape. Cut
immediately rather than batched for that reason.

**The deleting commit is named as a VERIFY commit** in the landing-protocol
text, because the instinctive reading of the incident is that a worker
clobbered a worker, and the actual lesson is that verifiers land too and
are subject to every rule in that section.

**The f32 hazard is confirmed at source** and cited in WP-0.2j rather than
restated: `lopdf::Object::Real(f32)` at `object.rs:42`, with `419.527559`
parsing to `419.5275573730469` and `419.5276` to `419.527587890625`,
recomputed here rather than taken on trust, two authored decimals landing
on f32 values that differ only in the eighth significant figure, which is
where the derived ratio moves.

**The corpus rule gains its cleanest demonstration**, and it is a
measurement rather than an argument: WP-5.2's scale-from-CropBox
perturbation failed both the display list and the raster on its `crop`
fixture while the live-010 test passed, because 010's CropBox equals its
MediaBox on every page. The fixture is the only thing that catches it,
shown on a specific defect.

## Revision 27 changelog

**Evidence must now state what it does NOT prove.** WP-5.4's rework added a
`## What is and is not proven` section and gave the reason plainly: the
false claim came from not having one. Its earlier evidence called zone
statistics "proven against Python" when the only assertion in the test was
a final raster hash. Not a lie; a claim nobody had to state precisely, so
nobody noticed it was empty.

That is the shape of nearly every rejection in this execution. WP-5.3a's
blanket coverage claim with a branch uncovered. WP-5.1c's "identical
private copy" that was the pre-fix body. WP-5.1e's search recorded as proof
of absence. WP-5.4a's per-arm coverage claim. In each case the WP knew what
it had tested, and the evidence format never forced it to say what it had
not, so the gap was invisible to its author as much as to anyone else. A
mandatory section makes the boundary explicit, and it is cheap.

Sharpened beyond the suggestion in three places, each earned by a specific
failure. PROVEN items must name the committed test AND how it was shown to
DISCRIMINATE, which is rule 10's requirement moved to where a reader looks.
NOT PROVEN items must name what would prove them or the WP that owns
proving them, and **an item with no owner is a finding escalated in
`## Status`**, because unowned gaps are exactly how `color_space_map`, the
cover-helper seam and the opener-fit vacuity all reached the plan late. And
a SEARCH THAT FOUND NOTHING goes under NOT PROVEN, never PROVEN: WP-5.1e
recorded one as proof of absence, and the luma pair shows why that fails,
since detection missed it at three levels including the manual grep.

Retroactivity, decided rather than left open: required for every WP briefed
after this lands, and NOT retroactive as a re-brief for the five already
running, since mid-flight churn is what rule 1 exists to prevent. Their
verifiers ask for it at acceptance instead, which costs nothing because a
verifier is already reading the evidence and constructing this exact
distinction to decide accept or reject.

Also folded in, as a record-only item under the cadence standard agreed
this session: batch anything that only records or clarifies, cut
immediately for anything that changes what an in-flight or about-to-start
WP would do, and put the reasoning in the changelog either way. This
revision is the second kind, which is why it did not wait.

## Revision 26 changelog

**Pinning a duplicate to its TWIN proves only that they match; pinning it
to the ORACLE proves it is right.** The duplicated-helper rule offered
"import it, or add a test asserting the two copies agree" as if those were
comparable, and they are not: agreement is equally satisfied when both
copies are wrong. The rule now names a STRONG form (each copy pinned to its
own Python original by its own oracle) and a WEAK form (copies pinned to
each other), with the weak form a last resort rather than an equal option.

Three instances from this execution point the same way, which is why this
is a principle and not an anecdote. `art.rs::grey` was caught by WP-5.4's
oracle being unfaithful to `cover.py`'s `convert("L")`, and no Rust-to-Rust
comparison could have caught it. WP-5.4a duplicated helpers it could not
import but pinned them to PYTHON over the whole plane, which is exactly why
its duplication was a structural exposure rather than a live defect.
WP-5.1c's `py_repr` copy was checked only against its sibling and carried
the pre-fix body with nothing noticing.

Also sharpened, because it is the strongest available argument for the
conclusion the plan already draws: detection failed at THREE levels on the
luma pair. The two implementations differ in name, in body, and in
fixed-point scale and rounding, so neither audit key fires, and a manual
grep missed it because `299` and `19595` denote the same coefficient and
share no substring. Widening the audit is still worth doing; it just cannot
close this class, so the rule is the mitigation rather than the scanner.

Cut as its own small revision rather than held for the next one, against
the suggestion to fold it in, because it MODIFIES a rule that WP-5.5a,
WP-5.3b and WP-5.4b will read while choosing how to handle a helper they
cannot import, and until it landed the weak form read as an equal
alternative.

## Revision 25 changelog

**The landing protocol had a hole and it was exercised.** Commit `aa4bc01`
landed from a stale base and DELETED all 39 of WP-5.2's files, while
WP-5.2's own commit stayed an ancestor of `art_directed`, so the prescribed
post-land check passed with the content gone (recovered as `ac443b0`; the
tree is confirmed whole). The check was answering the wrong question:
ancestry proves a commit is in the HISTORY and says nothing about whether a
later land reverted its CONTENT. The protocol now requires confirming the
files you expect are actually PRESENT in the resulting tree.
The principle is worth more than the fix, because this is not really about
git and it has bitten twice: **an invariant that holds over history is not
an invariant over state.** The other instance was the stale working copy
holding old content after a ref move. Check the state you depend on, not a
proxy for it.

**lopdf parses every PDF real as `f32`, and it has already caused a
measured defect.** WP-5.2's sheet-3 mystery, display lists and text passing
while one sheet's raster differed, resolved to exactly this: 010's pages 1
and 56 carry `MediaBox 419.5276` where pages 2 to 55 carry `419.527559`,
which an f32 cannot hold, so the computed scale came out exactly 1.0
against Python's 1.0000000151, shifting edges by about 9e-6 pt and flipping
381 bytes at max channel delta 4. WP-5.2's own display-list comparison was
BLIND to it because it formats operands at 6 decimals.
This sits beneath the comparator itself, since every coordinate, matrix
component and TJ adjustment the tracer reads is an f32 before arithmetic,
so **WP-0.2j** takes it as a shared exact path rather than leaving three
incompatible per-WP raw-byte recoveries to accrete. Object streams must be
handled or named, never silently reduced in precision.
The plan records the arithmetic so the pending measurement can be CHECKED
rather than trusted: f32 ulp is 3.87e-5 pt at 325 pt, which is 5.3% of
WP-0.2i's per-glyph bound at k=1, comfortably a fraction. But against the
SHAPE constraint it is about 22% of one expected step (WP-1.6's 0.000173 pt
per glyph), which is enough to make a monotone sequence look non-monotone
or to mask a small compensating kern. So the honest prior is that it is not
obviously negligible where it matters most, and rule 11 applies to whatever
answer arrives: measured, not asserted.

**The structural-comparison technique earns its keep a third time and
gains a third limit.** WP-5.2 replaces every resource NAME operand with the
SHA256 of the object it resolves to, seeing through pypdf's rename scheme
and both encoders' formatting while still failing on any change to what is
drawn, in what order, against which font or image. And its blindness to the
f32 defect is the limit: **a structural comparison's RESOLUTION is as much
part of its design as its shape**, because formatting operands at 6
decimals silently defines what counts as identical.

## Revision 24 changelog

**A retraction, and the discipline that should have prevented it.**
Revision 23 promoted "a fill-only outline probe is not evidence about
stroked elements" to a method lesson, on the mechanism that `ttf-parser`'s
redundant closing lineto before `Z` renders differently under stroke.
WP-5.4's verifier measured it (commit 06d5cf63) by reverting the
lineto-pop: the SVG changed by 1,251 bytes and the PNG came back
BYTE-IDENTICAL with the test still passing, and synthetic probes agreed
across miter-sharp, round-cap and curve-close cases. The redundant lineto
never reaches the raster. The lesson is retracted in both places it
appeared.

What survives is the half that was measured rather than explained: a
transposed CONSTANT diffed clean on every transform while differing on
10,768 pixels in a bbox of 428,221 to 967,326, and it alone accounts for
the whole difference. That remains the strongest argument in this execution
for raster equality as the cover oracle, and it is the right anchor for the
structural-comparison limit revision 19 recorded, which is re-pointed at it.
The mechanism was misidentified; the limit is real.

**Protocol rule 11**, because this is the second time and the shape was
identical: a MECHANISM asserted by the WP that found the defect is a
hypothesis, not a finding. WP-1.2 blamed WP-1.1's advance residual, ruled
out by WP-1.1's own numbers. WP-5.4 blamed fill-versus-stroke, falsified by
its verifier. Both times the DEFECT was real and the EXPLANATION was wrong,
and both times the plan promoted the explanation to a lesson before
anything independent tested it. Rule 9 already makes a number carry its
configuration; rule 11 does the same for causal claims, and names the test
that settles one, which is what both verifiers actually did: remove the
supposed cause and measure whether the effect goes.

**The luma question is resolved rather than noted.** `art.rs::grey` is not
a faithful port: `cover.py:495` uses `convert("L")` (PIL fixed-point) while
`art.rs` uses per-mille, disagreeing on 540 of 3,110,400 pixels of 010's
art and shifting zone means by 1.238e-04 and 5.652e-05. It passes only
because those statistics feed a threshold a 1e-4 shift does not flip: a
pass by AGGREGATION rather than correctness, which is rule 10's family
(a check that cannot presently discriminate is not evidence that the thing
under it is right). Three WPs have touched this; the answer is not that
both implementations are fine, it is that one is wrong and the fix is to
call `metrics.rs::luma601`, which is exactly what WP-5.1e's lift-and-widen
exists to prevent recurring.

## Revision 23 changelog

**A port can be wrong by being too strict, and that is the quiet direction.**
WP-5.4 blocked because `metrics.rs:95`, WP-5.3a's accepted code, bails on
ANY eXIf chunk while PIL happily returns 010's cover art unrotated (EXIF
tag 34665, no tag 274, and the Python cover compiler never calls
`exif_transpose`), so an accepted port refused the very image it exists to
grade, with WP-5.5b's preflight next in line over the same decoder. The
plan already licensed the opposite direction, a port reporting where Python
crashes; this revision states the mirror, which is NOT licensed, and draws
the line that keeps it consistent with the plan's fail-loud discipline:
fail-loud is right for the COMPARATOR, where an unknown operator must stop
rather than be mis-compared, and wrong for a PORT beyond what its oracle
refuses, where the Python IS the specification. Strictness gets declared
and argued like any other divergence. The Owns extension to `metrics.rs`
for the narrow fix is recorded alongside WP-0.0c's precedent, with the
requirement to re-run WP-5.3a's full oracle before and after.

**Covers move out of the risky column.** The front cover rasterizes to the
SAME sha256 the probe got from the SVG Python emitted before porting began,
0 of 4,335,040 pixels differ, the graded art matches independently, and the
markup skeleton matches to 8 decimal places. `Cargo.lock` gained nothing:
397 entries before and after, since the typst crates already pulled resvg,
usvg and tiny-skia transitively at exactly the versions the Python binding
embeds.

**Two method findings worth more than the WP they came from.**
[RETRACTED IN PART BY REVISION 24: the fill/stroke half below was a
mechanism asserted rather than measured, and WP-5.4's verifier falsified it
by reverting the lineto-pop and getting a byte-identical PNG. The
transposed-constant half stands. The entry is left as written because a
changelog records what a revision claimed; this marker exists so nobody
carries the retracted half forward out of the archive.]
A fill-only outline probe is not evidence about STROKED elements, because
`ttf-parser` emits a redundant closing lineto before `Z` that fontTools
omits, identical under fill and different under stroke; WP-5.4's earlier
834-glyph probe saw nothing for exactly that reason, and the wordmark is
the cover's only stroked element. And a transposed parameter pair
(horizontal_scale 105.1 with stroke_width 0.30 against 106.6 with 0.15)
passed EVERY structural check while differing on 10,768 pixels. That second
one is a limit on the technique revision 19 named, so it is recorded there
too: **a structural comparison cannot see a wrong constant that produces
structurally identical output.** Structure and pixels answer different
questions, and where an artifact can be rasterized the plan asks both.

**The protocol blesses withholding a red test.** WP-5.4 wrote its test,
proved it passes with the blocker removed locally, and deliberately did not
commit it, because a red test in the shared tree blocks every concurrent
agent's pre-commit hook. The naive reading of "commit your evidence" would
have broken six work packages to document one, so rule 5b now says the
evidence carries the test and the proof while the commit waits for the
unblocking WP.

## Revision 22 changelog

**Python and Rust disagree on Unicode, on 55 codepoints, silently.** Python
is on 15.0.0 and Rust's std is newer; `char::to_uppercase` supplies an
uppercase where CPython gives none across U+019B, U+0264, U+1C8A,
U+A7CD-A7DB, Garay (U+10D70-U+10D85) and U+16EBB-U+16EC4, and
`to_lowercase` disagrees on U+1C89. WP-5.4a did not accept the divergence:
it pinned both operations to Python's tables and swept all 1,112,064
codepoints three times. This is a plan rule rather than an evidence note
because of HOW it would have failed: these functions feed the web edition,
whose oracle is byte-identical output, so an unpinned mapping surfaces as a
baffling mismatch long afterwards, only when a manuscript happens to
contain one of 55 codepoints. Three remaining ports are exposed the same
way, one of them non-obviously: WP-5.3b's `body_text_lines` filter is a
lowercase test, which is a case operation.
The cost is recorded rather than left to be discovered: pinning FREEZES
these operations on Unicode 15.0.0, correct while Python is the oracle and
wrong once it is gone, so **WP-6.1 must decide explicitly whether to
unfreeze**. A permanent freeze nobody chose is the failure mode.

**The duplicate-helper audit guards four files out of seven directories,
and WP-5.4a walked into the gap.** It needed `is_python_space` and `py_str`,
both private in modules it does not own, could not import them, and
duplicated them into `cover/text.rs` where the audit cannot see the copies.
It pinned both to Python over the whole plane rather than merely to the
other Rust copy, which is stronger than the rule requires, so the exposure
is structural rather than behavioural.

**WP-5.1e takes BOTH options, not one**, and the reason is that the choice
was posed as a fork when the evidence makes it a conjunction. Lifting alone
is insufficient because the Unicode rule this same revision adds guarantees
the next cross-cutting helper: WP-5.5a and WP-5.3b will need exactly
WP-5.4a's pinned case tables, so leaving them in `cover/text.rs` schedules
the next duplication instead of preventing it. Widening alone leaves
today's duplicates where they are. So: lift `is_python_space`, `py_str` AND
the case tables into the shared module, and widen the audit to every module
under `mag/src/`. The 40-character body floor goes with it, since short
bodies are precisely where trivial Python-semantics helpers live and a
length threshold is the silent exemption rule 10 forbids; genuine
coincidences get an allowlist with reasons.

## Revision 21 changelog

**Covers stop being a risk item.** WP-5.4 blocked on SCOPE, not
feasibility, and both make-or-break questions came back positive, so the
plan now records answers where it used to record hazards. The backend was
never a choice: the `resvg` PyPI package is a thin binding whose compiled
library embeds resvg 0.47.0, usvg 0.47.0, tiny-skia 0.12.0, fontdb 0.23.0
and rustybuzz 0.20.1, so the port calls the same crates at the same
versions. resvg reproduces EXACTLY, decoded RGBA identical on both faces at
4,335,040 pixels each. And the cover SVG has no `<text>` elements at all,
only outlines, so font resolution cannot diverge; across all 834 glyphs of
Archivo Condensed Bold the fontTools and ttf-parser outlines rasterize
identically, differing textually and agreeing geometrically. The method
note is kept because it would cost the next person a day: `RecordingPen` is
the wrong instrument and falsely reports 714 of 834 differing.

**Three decisions.**

1. **Raster EQUALITY for covers, not a bound.** WP-5.4's bullet cited "WP-0.2f's
   derived bound", which never existed: WP-0.2f blocked and revision 15
   withdrew the raster guard outright. Citing a withdrawn artifact is worse
   than citing nothing, since it reads as settled. For covers the stronger
   bar is also the correct one, because the visible marks are two path
   fills and one Form XObject holding the resvg raster, with no text show
   contributing a visible mark, so origin snapping cannot reach them. The
   plan is swept: the only other citation was WP-5.2's, which referred to
   the bound only to say it must not absorb a divergence, and now says so
   without invoking a thing that does not exist.
2. **The invisible text layer is compared by CONTENT AND PLACEMENT, never
   by subset bytes.** Matching reportlab's Inter subsetting byte-for-byte
   is the reproduce-a-hack category, rejected for the fourth time, and it
   contradicts revision 19's division: Tier S for content, Tier E for
   rendering. An invisible layer contributes no rendering, so content is
   the only thing it has. Compared: decoded strings in order, positions at
   the 0.01 pt quantum, render mode 3, and the vendored FACE the subset
   derives from. Not compared: the embedded font program, since two
   subsets of one face legitimately differ.
3. **WP-5.4 splits, with WP-5.4b carrying the modes 010 never exercises.**
   010 uses `footer_caption` only, so `framed`, `honored_plate` and the
   unknown-mode refusal are corpus-unreachable and must be fixtured, along
   with the missing-glyph refusals, the contourless-glyph path, the
   art-analysis branch and the back-cover statement-fitting search. Split
   on the same seam logic as WP-5.5, so the mode that actually ships does
   not wait on fixtures for modes it does not use. **WP-5.6 depends on
   WP-5.4 only; WP-6.1 depends on WP-5.4b**, because deleting the Python
   must not delete a capability nothing has proven. The Rust PDF writer is
   written generally in WP-5.4; WP-5.4b adds coverage, not a second writer.

WP-5.4 also supplied WP-0.2h with the ordering it needs on the covers:
`/F1` is reportlab's default Helvetica, set at the top of the stream and
never shown, and it PRECEDES any `3 Tr`, so the Helvetica decode is the
first stop and the render mode the second. It did not run the tracer itself
and said so, which is why that is recorded as a pointer rather than a
result.

## Revision 20 changelog

**The vacuity pattern turned up inside an argument the plan now relies on**,
which is why this is a revision rather than a footnote. Path B's safety
rests on the tracer AGREEING with pypdf on the fields behind ten of eleven
[REVISION 38: "ten of eleven" is right here; elsewhere the plan said the
total was ten while enumerating eleven. Corrected in the live text.]
issue sites, and WP-5.3d's verifier (accept commit 513a970, decision
upheld) graded those agreements: they are not equally strong.
`text_order_matches` at 27 of 27 traceable sides discriminates, and so does
text-emptiness at 54 of 54, which the evidence UNDERSELLS, since pypdf
partitions 7 empty pages against 47 non-empty (pages 2, 10, 30, 35, 45, 54,
55) and agreement means reproducing that exact partition. But
`standalone_punctuation_lines` at 54 of 54 is `0 == 0` on every page: it
proves the tracer invents nothing, and nothing at all about whether it
would produce the same lines if any existed. In a table where both rows
read "54 of 54", that difference is invisible.

The decision is unaffected and stands on the two discriminating
agreements. What changes is that WP-5.3c's fault coverage for
`standalone_punctuation_lines` is now marked as the ONLY evidence there
will ever be for that field, rather than a belt-and-braces extra.

**Generalized as protocol rule 10**: evidence that cannot discriminate must
say so. The plan already held that a gate which cannot fail is not a gate,
and WP-0.2g makes clauses report their compared cardinality; rule 10 extends
it to evidence, which is where it slipped through this time. The rule names
its four instances so it reads as a pattern rather than a precaution.

**WP-5.3d's numbers carry "pre-WP-0.2i tracer"** (rule 9), so WP-5.3b must
re-measure rather than inherit them. WP-5.3d's verifier declined to rebuild
the probe because WP-0.2i was concurrently editing the two files it
`#[path]`-includes, which would have measured a different tracer than the
one under verification. That restraint was right, and the consequence
belongs in WP-5.3b's brief rather than in a footnote.

Historical changelogs are left as written: revision 17's entry records what
revision 17 claimed, and this entry is the amendment. Only the live WP text
is corrected, which is the same treatment revision 15 gave revision 10's
superseded reasoning.

## Revision 19 changelog

**The undeclared-edge class is closed by reading the imports.** WP-5.5 ended
`blocked` on four dependencies, three of which the graph did not express,
and named the systemic cause: the graph was drawn from the plan's WP
groupings rather than from the Python import graph, which is cheap to read.
That was the third undeclared edge found the expensive way. The whole
internal import graph among modules Appendix A assigns to WPs has now been
reconciled into the dependency graph, and the Phase 5 preamble carries the
rule so the next cut checks imports rather than themes.

**WP-5.5 is re-cut along the seam its dependencies actually create**, into
WP-5.5a (web), WP-5.5b (preflight, which needs only WP-5.2 and WP-5.3a and
is runnable the moment WP-5.2 lands) and WP-5.5c (package and SHA256SUMS,
which needs WP-5.2 and WP-5.3b). WP-5.6 now depends on the three of them
severally rather than on one blocked WP.

**The unassigned cover-helper seam becomes WP-5.4a.** `web_edition.py:18`
imports four PURE TEXT functions from `cover.py` that are not the PDF
compiler at all, and with `mag/src/cover/` not yet existing and the
duplicated-helper rule forbidding a copy, whoever arrived first would have
had to invent the seam. Cut as its own small WP rather than folded into
WP-5.4, so the web path does not wait on the cover compiler.

**The QR codes are decided, and the trap is named.** All nine regenerate
byte-identically, every payload is byte mode so mode segmentation is not a
variable, but segno BOOSTS the requested error level L to M on 6 of 9,
which is a segno policy rather than ISO/IEC 18004. A spec-correct encoder
asked for L would differ on two thirds of this edition's codes while
looking correct in isolation, so the boost is reproduced deliberately and
the effective level asserted per payload. The primary oracle is STRUCTURAL,
comparing the decoded module matrix, payload, version, mask and effective
level; byte-identity stays the web-tree bar, with any divergence declared
and enumerated rather than absorbed.

**`3 Tr` gets a decision, not a fail-loud.** 010's covers use invisible text
as well as non-embedded Helvetica, so they had TWO unowned reasons to break
the gate once WP-5.4g compares them, and only the ToUnicode half had an
owner. WP-0.2h now RECORDS invisible text with the render mode on the
element rather than skipping it: it contributes no pixels, so it is not
what is printed, but it is the selectable-text layer that usually carries
the real title, and a difference there is a real difference in what a
reader can select, copy and search. Recording costs nothing and compares
invisible text only against invisible text; Tier S's extracted-text clause
covers the same content independently, which is the right division, Tier S
for content and Tier E for rendering.

**Structural comparison is named as a general move**, since it has now
rescued two dead ends (the critic's text source and the QR matrices):
compare the decoded structure rather than the serialization, insensitive to
how a library writes bytes while still catching a wrong version, mask,
level or ordering. With the limit stated, because it could otherwise become
an excuse: it is not a licence to weaken an oracle whose BYTES are
themselves the artifact, which is why the web tree keeps byte-identity.

## Revision 18 changelog

**Cargo-file serialization is dropped and replaced by a check.** Rule 1's
clause (a) made Cargo-file owners pairwise serial, and since the Phase 5
preamble gives every port WP the Cargo files, it made the whole phase a
single queue: five deep when this was decided, with WP-5.4 waiting behind
WP-5.5 waiting behind WP-5.2, and WP-5.6 (which gates the flip) depending
on four of them. That is a lot of critical path to spend on conflicts in a
generated file.

The replacement is rule 1a, and it is stricter about the thing that
actually matters. The hazard was never the CONFLICT, which is loud and
mechanical, especially under the landing protocol this execution grew after
a commit was silently dropped: work in your own worktree, rebase onto
current `art_directed` before landing, confirm afterwards that both your
sha and the pre-land HEAD are ancestors. The hazard is a bad RESOLUTION
silently changing a pinned version, and serialization never prevented that,
since one agent resolving badly produces it with no second WP involved. So
rule 1a requires crates to be added last, immediately after a rebase; locks
to be REGENERATED rather than hand-merged on conflict; and a post-landing
check that `Cargo.lock`'s `(name, version)` set has only GAINED entries,
with none removed and none changed. A version that must genuinely move is
declared, and for a crate the plan pins by name it is a plan revision.

Clauses (b) and (c) stand, and the plan now says WHY they are different
rather than leaving the distinction to be re-litigated: they serialize
genuine LOGICAL coupling, where two WPs can each be right and jointly
wrong, while (a) only ever serialized a mechanical conflict in a generated
file. Dropping (a) is therefore not a precedent for dropping them.

## Revision 17 changelog

**A correction to revision 16, which carried a false claim in three
places.** I wrote that `article-stub-last-page` is the only text-derived
decision boundary in the critic, propagating it from WP-5.3d's evidence
without checking the source. It is wrong, a verifier proved it (verify
commit 6c24379, which rejected WP-5.3d while explicitly UPHOLDING its
decision), and I have now confirmed it in `render_critic.py` myself:
`body_text_lines < 5` is the only numeric THRESHOLD, but FIVE text-derived
fields feed TEN issue sites (`text_order_matches` :152 :176 :198, `blank`
:291 :452 :476, `ink_free` :299 :460 :484, `standalone_punctuation_lines`
:309, `body_text_lines` :380; `blank` and `ink_free` are conjunctions on
`not text.strip()`, and `sparse` is ink-ratio only and correctly out).

This mattered because I had narrowed WP-5.3c's obligation on the strength
of it, and marked the narrowing so nobody would inherit the wider version.
A WP-5.3c briefed that way would have fixtured one threshold and left four
fields unfaulted, under a path whose whole premise is that the fault suite
carries the weight. **WP-5.3c now owes fault coverage on all five fields**;
what stays bounded is only the NEAR-THRESHOLD work, since `body_text_lines`
is the one field with a numeric edge to straddle.

The decision itself is unchanged and the argument for it is stronger than
what it replaced: path B is safe not because only one decision consumes
text, but because the tracer AGREES with pypdf on every field behind the
other TEN sites (revision 38 corrected this from nine; the total is
eleven, not ten), measured at 0 of 56 divergences on
`standalone_punctuation_lines` and text-emptiness and 27 of 27 traceable
sides on `text_order_matches`. Absence was the wrong argument; agreement is
the right one, and it was in the measurements all along.

Two consequences of the cover pages being unreadable, now stated where they
cannot be dropped as redundant. `cover-booklet-page-order` cannot be
computed AT ALL under a tracer-fed critic, because `cover_spread_checks`
runs over the wrap carrying reader pages 1 and 56, so **WP-0.2h is a hard
prerequisite of WP-5.3b**, not a quality improvement. And WP-5.4g brings
those same pages into the Tier E compared domain, so a tracer that fails
loud on them is a hole in the gate rather than an inconvenience.

Also carried into WP-5.3b: the corrected join rule has a bounded mirror
failure, where joining with a space gives a word split across two adjacent
shows a spurious space `normalized()` cannot remove. Reachable in principle
("BERRETA FUTURA04"), did not fire on 010.

## Revision 16 changelog

WP-5.3d decided the critic's oracle by measurement, as it was cut to do,
and the answer is **path B with the TRACER as the text source**. What makes
it more than a verdict is the reason path A failed: the tracer cannot
reproduce pypdf's MISTAKES. All seven `body_text_lines` divergences are one
cause, pypdf merging a two-line headline into a single line ("Government
Rails Site HitHours After CVE Patch") where the tracer correctly sees two
shows 28.8 pt apart; `text_characters` diverges because pypdf injects
synthetic spaces into letter-spaced runs. Matching either means
reimplementing `crlf_space_check` and the `abs(op) >= _space_width * 0.95`
rule, which is the "reproduce a hack to stay equal to a tool we are
deleting" category this plan has now rejected three times, here and at
WP-5.7 and at `_check_unique_art`. Three independent measurements, one
principle.

**The luck caveat is measured away, so WP-5.3b's brief is re-cut rather
than inherited.** Revision 15 made the fault suite carry an open-ended
obligation because 010's issue set might have been surviving an extractor
swap by chance. It is not, though revision 16 justified that with a claim
that is false and revision 17 corrects: `body_text_lines < 5` is the only
numeric THRESHOLD, but FIVE text-derived fields feed TEN issue sites. The
argument that actually holds is not "only one decision consumes text", it
is that the tracer AGREES with pypdf on every field feeding the other nine
sites: 0 of 56 divergences on `standalone_punctuation_lines` and on
text-emptiness, and 27 of 27 traceable sides on `text_order_matches`. So
WP-5.3c owes fixtures on all five fields, not one. WP-5.3d also supplies
the measured basis for
the "not worse" requirement the plan had been asserting: 27 of 27 traceable
spread sides against poppler's 7 of 28, and 47 of 54 pages against 16 of
56.

**Two residuals get a home: WP-0.2h**, which revision 15 named only inside
a path that was not taken. It now exists as a comparator WP with two
targets. The seam: expose the tracer's TEXT path without the navigation
path, because `display::extract` resolves annotations and dies on
`booklet-a4.pdf` with a missing `/Names` key while `streams::trace_page`
reads the same file. The decode: 010's COVER PAGES are currently
unreadable, since Helvetica is non-embedded with no `/ToUnicode`, and they
are not empty (page 56 carries 380 characters and 6 body lines). The fix is
specified rather than guessed, since the standard-14 encodings determine
the mapping. That second target is not optional for the critic's sake
alone: WP-5.4g brings the cover pages into the compared domain, so Tier E
needs it too.

Carried into WP-5.3b's brief so it is not rediscovered: the seven headline
merges are one known difference, and the naive join rule is wrong in a way
that looks right (WP-5.3d's first attempt scored 6 of 27 by joining shows
with the empty string, welding one page's last token to the next page's
first).

## Revision 15 changelog

Two blocked WPs, one of which removes the gate's third leg and replaces it.

**The raster guard is withdrawn from Tier E and replaced by per-glyph
positions.** WP-0.2f tried it properly (`meta/verification/evidence/
WP-0.2f.md`, commit 932f90e) and it failed on a mechanism nobody
anticipated: `mutool draw` does not FreeType-grid-fit outlines, which was
the hope, but it ROUNDS TEXT-OBJECT ORIGINS to the device grid, so at
300 dpi it is as sensitive to a sub-pixel origin shift (242) as poppler
(241). Floor 30.125 equals ceiling 30.125, the linear-matrix term brackets
at 151.641 above every ceiling measured, and the window is inverted rather
than narrow. The escape hatch closes too: perturbing origins within
0.001 pt still reaches 122, because among 69,071 glyphs some origin always
crosses a rounding boundary, so no finer display-list quantum rescues it.
Pixels cannot bound what the display list cannot see, at any resolution.

So the display list gets finer instead: **WP-0.2i records per-glyph
device-space offsets**, bounded by `k x 1/1024 px` derived from the
MECHANISM (Pango advances in integer 1/1024 px, Typst sums exact font
units), with a SHAPE constraint doing the harder half of the work: a
legitimate difference accumulates, so the sequence must be one-signed and
monotone, and a compensating kern fails on shape whatever its magnitude.
[REVISION 42: "whatever its magnitude" is corrected in the live Tier E text
to "every physically reachable magnitude"; a detection floor exists between
9.16e-08 and 9.16e-07 pt, about 7,000x below one Pango tick.]
Rasters survive as Tier V meters, where the plan already said they gate
nothing, so runs stay near 82 seconds instead of the 9 to 15 minutes
supersampling would have cost.

**Why not simply declare intra-line placement out of scope** with the
measured caveat (0.0174 pt, 0.07 px at 300 dpi): because that caveat is
not a bound. Zero of 1488 shows inherit a previous advance, so nothing
downstream ever exposes intra-line spacing, and same string plus same
glyph count plus same origin plus same matrix admits ARBITRARY internal
spacing. 0.0174 pt is what these two engines happen to differ by today,
not what the gate would permit. Per-glyph positions are the only way to
bound it at all, which is why this is the answer rather than the cheaper
one.

Consequences recorded: blind spots 1, 2 and 5 close geometrically (2 via
GID mapping through the shared vendored face, since rasters no longer
guard it), 3 and 4 become fail-loud stops, and **Tier E becomes an
entirely geometric claim**, which is a simpler sentence to defend. WP-0.2g
loses its linear-quantum tightening: WP-0.2f measured 26 distinct `trm[0]`
values on the oracle leg which are NOT clean font sizes (13.333 x1068,
9.0664 x169, 12.7998 x55) because a 4/3 px-to-pt scale is composed into
`Tm`, so the premise was false, and per-glyph device-space offsets observe
the effect directly anyway. WP-3.0g's real-pair re-derivation moves to
WP-0.2i.

**WP-5.3b is blocked on the same root cause by a different route**, and
WP-5.7's escape does not transfer: the critic is a live comparison for as
long as both implementations exist. WP-5.3d decides its oracle by
measurement, testing whether the display-list tracer can supply the
critic's text metrics exactly, with paths A and B and the criterion fixed
in advance. That question is now more likely to resolve well, since the
tracer is becoming the canonical geometric source for the whole pipeline.

## Revision 14 changelog

**A mis-scoped WP bullet, corrected before it misbriefs two more.** WP-5.3a
found that the plan pairs `image_contrast.py` with `concurrency.py` as
"critic raster metrics", but only `concurrency.py` feeds
`render_critic.py`. `image_contrast.py` is consumed by `preflight.py`, the
reportlab `render.py` (which dies at WP-6.1) and `weasyprint_adapter.py`,
and its numbers land in preflight.json. Three corrections, all notes rather
than moves, since WP-5.3a is done and its code is right where it is:
`mag/src/critic/metrics.rs` is deliberately not renamed and WP-5.5 is told
it already exists and must consume rather than re-port it; WP-5.3b is told
it inherits `render_critic.py`'s own raster helpers (PIL grayscale,
histograms, `ImageChops.difference`, a LANCZOS resize), which the plan had
left unnamed; and `critic_metric_tolerances` is attributed to WP-5.3b's
oracle, where it will first actually be exercised, since WP-5.3a hit exact
equality and consumed none of it.

## Revision 13 changelog

**A quantum that bounds a length does not bound a ratio.** WP-0.2e's
verifier (which ACCEPTED the WP: the matrices are strictly stronger than
the start point and bounding box they replaced) found that applying the
0.01 pt quantum to the LINEAR components of a text matrix bounds nothing
useful, because those components multiply the accumulated advance inside
the show. A `trm[0]` differing by 0.00499 quantizes identically and still
moves a 34-glyph 226.8 pt line 0.0945 pt at its end, as does a 0.000415
rad rotation; images are unaffected, since their matrix maps the unit
square and the error stays inside the half quantum.

Three consequences, all recorded:

- Tier E now states the quantization rule in two parts, and says what it
  therefore asserts for text: geometric equality of glyph ORIGINS, with
  everything downstream of the origin inside a show covered
  photometrically. That is the division revision 10 already drew for
  intra-line placement; this names the second mechanism feeding it.
- The enumeration of what the display list cannot see gains item 5, phrased
  as a bound with numbers rather than as a hole, since Fran's sentence
  depends on it: up to `(half quantum / font size) x measure`, which is
  0.0945 pt measured at 12 pt and 0.1625 pt derived for 010's body text,
  16x the coordinate quantum and 0.68 px at 300 dpi.
- [REVISION 39: the conditional below is VOID. Revision 15 withdrew the
  raster guard and revision 39 withdrew WP-0.2f entirely, so there is no
  window to collapse and no bound to derive. WP-0.2i's per-glyph floor
  carries the third fixture's role. Kept as the record of what revision 13
  decided.]
- WP-0.2f's floor gains a THIRD fixture for it, and it is the largest of
  the three on paper, so it may be what decides whether the 2x window is
  open. **But the better answer is to remove the term rather than
  accommodate it**, so WP-0.2g now quantizes the linear components finely
  enough that their amplified effect stays inside the coordinate quantum,
  about 3.1e-4 at body measure against 0.01 today, derived from the
  distribution both engines actually emit rather than picked. Both emit
  clean values for these components, so this should cost nothing and it
  shrinks the raster guard's load. If WP-0.2f's window collapses first,
  this tightening is the blocking fix and is done before the floor is
  re-derived.

## Revision 12 changelog

**The content-final gate moves from WP-2.0a to WP-3.1.** Reasoned from the
plan's own design rather than from schedule pressure: every Phase 2
comparison is a SAME-RUN comparison, both legs rendered from one staged
copy in one invocation, so each asserts a property (the two legs agree)
rather than a fact about a particular corpus. A property survives content
churn; a cumulative claim does not. Nothing accumulates across runs until
the ratchet starts recording per-page tiers, and the first WP whose
acceptance depends on a baseline entry surviving from an earlier run is
WP-3.1. WP-2.0b compares against a baseline that is still empty, and the
staleness guard already refuses ratchet comparison and page-set scoring
when the staged-input digest differs, so a mid-Phase-2 content change costs
a re-render and a re-run of that WP's verify clauses, and invalidates
nothing, because there is nothing yet to invalidate. Building the engine
against a corpus that may move is also a better test of it than building
against a frozen snapshot: an engine that only works on one pinned edition
is overfitted, and Phase 2 would not find out.

The two content-sensitive-looking cases are both same-run and therefore
safe: WP-2.2b's Tier S page count compares the two legs of one render, so
if 010 grows both legs grow, and WP-2.3 compares the layout result against
the oracle leg's `edition-manifest.json` from the same staged copy. What
this does require is that no verify clause hard-code a corpus fact, so
rule 9 is extended: a pass condition quoting a number from the corpus must
derive it from the oracle leg per run.

**Duplication across the model ports is now a measured defect source, not a
style question.** Three of six rejections in this run came from one
behavior living in two places and drifting: WP-5.1c reintroduced by copying
the exact `py_repr` defect WP-5.1b had already been rejected for and fixed,
into the module with the widest exposure (25 call sites, any hand-authored
string from edition.yaml). No test caught it because the 74-case corpus has
no non-printable characters. So **WP-5.1d** consolidates the shared
helpers, and the Phase 5 preamble now carries a rule for the remaining
ports.

**WP-5.7's oracle is re-scoped from byte-identity to transcription
fidelity, and split so the fixtures exist first.** The WP confirmed
`pdf2md.py` is deterministic, then blocked for two reasons that hold:
matching it byte for byte means porting pypdf's text layer (1701 lines plus
18452 of tables) and, worse, reproducing its self-described heuristics
rather than the PDF specification; and the three fixtures the oracle names
do not exist, so two would be synthetic and authored by the implementer,
the pattern that has already caused two rejections. Byte-identity here
anchors on an arbitrary choice and governs only FUTURE captures, since
every committed article.md is never re-derived, so it is a counterfactual
rather than a regression check. What the pipeline actually requires,
verbatim source text, is testable directly. This is the one place the plan
deliberately changes what "the same" means, so the reasoning is written out
in WP-5.7, the fallback (a faithful port of pypdf's text layer) is named,
and WP-5.7a builds a real fixture corpus with ground truth established by
cross-extractor disagreement review BEFORE WP-5.7b chooses a library.
Poppler is not a free substitute: it welds hyphenated line breaks, turning
`input-\nheavy` into `inputheavy`, which is word corruption in a verbatim
file.

**And the lesson that keeps repeating, written where port WPs will read
it**: a corpus-based oracle proves only what the corpus contains. Edition
010 has no padded containers (which hid WP-5.1a's defect), no explicit
ports and no non-printable characters (WP-5.1b's two and WP-5.1c's one).
Every port WP must now state which branches its corpus cannot reach and
cover them by fixture.

## Revision 11 changelog

Four dispositions, three of them from completed WPs and one correcting
revision 10's own text.

- **Porting a crash is not fidelity.** WP-5.1c found `manifest.py`'s
  `_check_unique_art` trusting shapes the validator has already rejected,
  so a non-mapping `cover` or `opener_art` dies with AttributeError and a
  non-iterable `closing_plates` with TypeError, DISCARDING diagnoses Python
  had already accumulated. The Rust port returns those diagnoses instead.
  Recorded as a **deliberate divergence**, not fixed in Python: the Phase 5
  preamble now states the rule and its limits, so the remaining porting
  WPs apply it consistently instead of deciding case by case.
- **The web tree stays out of the parity ladder, and the guard moves to
  where the risk actually is.** A ladder clause would compare nothing:
  during Phase 2 and 3 the Typst leg produces no web output at all, so
  there is no second side until WP-5.6. The real exposure is an oracle
  change silently altering the web tree while every PDF clause stays green,
  which is exactly what WP-0.0c's first attempt did. So the mandatory
  web-tree comparison becomes a binding verify clause on sanctioned oracle
  changes (Reference stability), not a tier.
- **A translation smoke test before the Python dies.** WP-5.1c ported
  `load_translation` in full, broader than English-only parity required and
  the right instinct, but it leaves the Rust loader supporting a path
  parity never exercises. WP-6.1 now must compare a translated edition
  through both loaders BEFORE deleting the Python, because deletion is the
  moment the oracle stops existing.
- **Revision 10 quoted a reconciliation that does not hold.** WP-1.6
  explained the gap between its 0.017432 pt and WP-1.1's 0.009897 pt as a
  rounding and per-run difference; the WP-1.5/1.6 verifier showed both
  halves fail, and the real cause is an uncontrolled variable. Corrected in
  place, and generalized into protocol rule 9, because this is the SECOND
  time two spikes measuring different corpora were chained into a causal
  claim.

## Revision 10 changelog

Revision 9 was critiqued adversarially (`meta/verification/evidence/
REVISION-9-CRITIQUE.md`) and came back sound with fixes. The two-sided bound
survives; what did not survive is revision 9's claim to have enumerated the
display list's blind spots. Four repairs, one of them substantive:

- **Glyph identity was an unlisted blind spot, and it is the only one this
  project has observed in the wild.** `Element::Text` records the decoded
  string, not the glyphs, so a ligature and its components are display-list
  equal. WP-1.1 measured exactly that between the engines (rustybuzz formed
  `ft`, Pango suppressed it under letter-spacing). WP-0.2e now records the
  GLYPH COUNT per show, never raw CID codes, which the two engines assign
  independently. Worse than the hole itself: WP-0.2f would have derived its
  ceiling from a fixture set missing a whole fault class, which is the same
  incomplete-enumeration mistake that produced the 241.
- **The containment argument for intra-show kerning was wrong, and it is now
  measured rather than argued.** In 010's reader.pdf, across 54 interior
  pages, 360 text objects and 1488 shows, the number of shows that inherit a
  previous show's advance is **zero**: every show is repositioned by
  `Tm`/`Td`/`TD`/`T*` first, and `Td` resets the text matrix from the line
  matrix, discarding any accumulated advance. So the raster guard is the SOLE
  check on intra-show glyph positioning, for every line. It is load-bearing,
  not a backstop, and WP-0.2f must be sized knowing that.
- **The reachability floor was a random sample, not a bound.** Perturbing
  each coordinate to a random point in its bucket understates the worst
  legitimate case and makes the number seed-dependent, so "derived, never
  chosen" was not true in practice. WP-0.2f now perturbs to the bucket
  extremes in both directions, two deterministic runs, floor = the max.
- **WP-0.0c was missing from Reference stability's sanctioned list**, so a
  verifier applying that sentence literally would have rejected its diff.

Two findings landed while this revision was being written, and both change
the gate rather than merely annotating it:

- **WP-0.0c: a verify clause that would have passed a real regression.** The
  clause for sanctioned oracle changes says "`pdftotext` dumps and critic
  report unchanged", and the opener attribute left both unchanged while
  silently deleting nine articles' source QR links from the web edition,
  because `web_edition.py` recognizes its own markup by exact tag string.
  **A WP that touches the HTML the renderer consumes must compare the web
  output too, not only the reader PDFs.** WP-0.0c's Owns now covers
  `web_edition.py` for the detection fix, and WP-5.5 carries a residual to
  port those string matches as structural tests.
- **WP-1.6: the line-break miss is engine-intrinsic, and it has a second
  consequence nobody had modelled.** WeasyPrint breaks on an integer count
  of 1/1024 px while Typst sums exact font units, so (a) one body line of
  899 breaks differently, fixed by widening the Typst column to an interval
  WP-1.7 must measure rather than a constant anyone picks, and (b) the two
  engines place glyphs WITHIN every line at systematically different
  positions, up to 0.017432 pt, which the display list cannot see at all.
  Revision 9's reachability floor modelled only coordinate quantization, so
  WP-0.2f would have met this as an unexplained failure and blocked. The
  floor now derives from two fixtures, and Tier E states outright what the
  gate does and does not claim about intra-line glyph placement.

Also adopted from the critique's optional list: a required 2x margin between
floor and ceiling rather than bare `floor < ceiling`; WP-0.2f's fallback
written down in advance; and a new WP-0.2g for compared-cardinality
reporting and `/Rotate`.

**What changed for a WP already in flight:** WP-0.2e gains the glyph count
and a fourth fixture (a ligature case: same string, same origin, same total
advance, different glyph sequence, must fail). WP-0.0c is unchanged in
substance but is now explicitly sanctioned to touch `src/magazine/`. Nothing
else in flight changes; cardinality and `/Rotate` went to a new WP rather
than into WP-0.2e's brief precisely because that brief is already executing,
and rule 1 binds a WP to the Owns list it was given.

## Revision 9 changelog

The end claim this plan exists to license is one sentence: **the new
typesetting pipeline renders edition 010 (en) the same as the old one.**
Revision 8 tried to license it with display-list equality plus raster
zero-diff. Phase 0 and the Phase 1 spikes measured that design and found one
half of it broken and the other half slightly blind. This revision repairs
both, and the claim gets stronger rather than weaker.

- **The raster half was measuring the rasterizer, not the engines.**
  WP-0.2d ran the plan's own derivation and measured a max per-channel delta
  of 241/255 from coordinate noise *below* the comparison quantum. The cause
  is FreeType grid-fitting: at 300 dpi a sub-quantum shift moves a stem a
  whole pixel and flips it between paper (255) and body ink (14). It is not
  antialiasing noise, `-aa no` does not touch it, and the same 241 appears
  from an unrelated 0.3 pt fixture shift. Writing 241 into the bound would
  have left the guard passing everything below 242. **WP-0.2f now selects a
  rasterizer configuration that does not grid-fit glyphs and derives the
  bound under two-sided constraints** (see Tier E): reachable given
  sub-quantum noise, and strictly smaller than the pixel signature of the
  faults the display list cannot see. If no configuration satisfies both,
  that is `blocked` and another revision, not a widened bound. The
  derivation itself is also corrected: revision 8 perturbed coordinates
  within HALF a quantum, but two coordinates that quantize equal share a
  bucket 0.01 pt wide and can differ by nearly all of it, so the fixture
  now moves each coordinate within its own bucket and asserts the display
  lists stay equal.
- **The display-list half is blind to three things, two of them cheap to
  fix.** Text shows record a start point and a size magnitude, images record
  a bounding box, so a mirrored or rotated glyph run and a flipped image are
  invisible. **WP-0.2e records the full text and image transforms**, which
  costs nothing and closes both. The third, intra-show TJ kerning, is
  deliberately left to the raster guard: WP-0.2b tracks advances exactly, so
  a kern difference already surfaces in any later show, and recording raw
  kern numbers would fail on Pango's 1/1024 px rounding rather than on any
  real difference.
- **Shaping and breaking agree, and the residual is physical, not
  algorithmic.** WP-1.1: 1488/1488 lines have identical glyph sequences,
  per-glyph advances agree within 0.00073 pt, and cumulative advance is
  within 0.01 pt on 1484/1488, the four misses reaching 0.0174 pt purely
  from Pango's own rounding. WP-1.2: 148/149 paragraphs break identically
  with zero structural misses, the one miss being a line Typst measures
  0.01 pt over the column. Neither is waived: Tier E still has to find them
  equal. The Phase 1 audit also caught WP-1.2 misattributing its miss to
  WP-1.1's residual, which cannot be the cause (WP-1.1's normal-spacing
  lines top out at 0.009897 pt and none crosses the quantum; its larger
  misses are letter-spaced headlines), so **WP-1.6 measures where the
  0.01 pt actually comes from** before WP-3.1 tries to fix it.
- **Hyphenation is off for parity** (WP-1.3 measured zero page-count changes
  and zero new cap violations from disabling it), scoped to `:lang(en)` so
  no Spanish edition is disturbed in the meantime, and WP-4.3 becomes
  mandatory.
- **Typst is pinned and proven measurable** (WP-1.4): the 0.15.1 family,
  frame walk for geometry and introspection query for structure, and the PDF
  export is byte-reproducible, which matters for verdict determinism.

What we can say when `mag parity 010` exits 0 under this revision: every
drawing operation the two engines emit is identical (same text, fonts,
sizes, colours, clip stacks, paint order, vector geometry, images,
annotations, outlines, every coordinate equal at 0.01 pt, every transform
equal), and the two pages rasterized side by side differ nowhere by more
than a bound measured to be below the smallest difference the display list
can miss.

Two decisions define this plan:

- **The target is edition 010, English.** One edition, the current one,
  already rendered (56 pp, figures, two verbatim articles, inline code, no
  extracts, no fenced code blocks, no editorial; `cover.layout:
  footer_caption`). No frozen corpus, no content pinning, no translations:
  `mag parity` renders BOTH engines in one invocation from ONE staged copy
  of the working tree, so the WeasyPrint leg of the same run is the
  reference and there is nothing to pin. 010 is also the live intake
  edition, so every verdict and baseline entry is bound to the
  staged-input digest it was computed from (see Reference stability), and
  PHASE 3 starts only once Fran records 010 content-final. Phase 2 builds
  the engine against whatever 010 currently is: every Phase 2 comparison is
  same-run, so it asserts agreement between the legs rather than a fact
  about a corpus (revision 12).
- **No human in any pass/fail verification.** The gate is display-list
  equality plus a raster comparison within a derived bound, both decidable
  by machine (revision 9 replaced "zero-diff" here; see Tier E). Fran appears
  only where the plan itself must change (a fallback choice, an irreversible
  deletion), never as an approver of sameness.

The plan is executed by independent subagents. Every work package (WP) is a
self-contained brief (protocol rule 8); a WP is done only on verifier
acceptance (rule 3), never on its own say-so.

## End state

- `mag render <NNN>` typesets the A5 reader with an embedded Typst engine,
  natively in Rust.
- Edition 010 (en) rendered by Typst is Tier E-equal to the WeasyPrint
  render: identical display lists (transforms included), rasters agreeing
  within the derived bound, all structural checks green, verified by
  `mag parity 010` exiting 0.
- `measure_article` / `measure_edition` / `render_edition` are native `mag`
  operations; the JSON bridge is gone.
- Booklet imposition, cover compilation, render criticism, preflight,
  packaging, the web edition, and capture's PDF transcription helper are
  Rust, each proven against its Python original on edition 010's outputs
  before that original is deleted.
- No Python runs anywhere in the pipeline (Appendix A dispositions every
  Python file in the repo).

Scope notes, stated up front: the Typst engine targets the current format
(editions 010+: no opening editorial). Translations (es) are not part of
parity; the typeset path gains translation loading when a translated edition
next needs it, as ordinary post-flip work. After WP-6.1 deletes WeasyPrint,
pre-010 editions can no longer be re-rendered byte-faithfully; reprints of
them would need the editorial feature added to the Typst engine first.

## What "EXACTLY the same" means (the parity ladder)

Two engines never produce byte-identical PDF files: object ordering, font
subsetting, and compression differ even when every glyph sits at the same
coordinate. Equality is therefore defined at the level that determines what
a printer or reader receives: the drawing operations.

### The compared artifact

Until the comparator's domain switch (WP-5.4g), the compared unit is the
**interior domain**: pages 2 through n-1 of the WeasyPrint `reader.pdf`
versus pages 2 through n-1 of the Typst `interior.pdf`, with n required
equal. This needs no oracle change: the bridge builds `reader.pdf` by
replacing only the outer pages of the interior with the compiled covers
(`replace_outer_pages` in `src/magazine/cover.py`), so inner pages pass
through pypdf with content intact; WP-0.2c calibrates that rewrite's noise
before stream comparisons are trusted. The Typst interior carries the same
placeholder outer pages, so numbering and folios align. From WP-5.4g on,
`reader.pdf` is compared end to end.

### Tier S (structural, exact, no tolerance)

Over the compared domain of edition 010 (en):

- identical page count, read with `pdfinfo`, never from engine-reported JSON
- per-page MediaBox, CropBox, TrimBox equal within 0.05 pt, and `/Rotate`
  equal exactly (WP-0.2g adds the rotation; it is print-visible, and a 180
  degree difference keeps dimensions equal so nothing else would catch it)
[REVISION 44: "nothing else" is too broad; on a body-text page `text` and
Tier G catch it too. The clause is the only guard on a BLANK page, which is
the narrower and true claim.]
- per-page extracted text identical after normalization
- **code blocks**, in two halves because a PDF has no bytes: at the input
  level, the fenced runs in each engine's staged input byte-equal the
  captured `library/sources/<id>/article.md` runs; at the PDF level, engine
  vs engine only, text runs inside code-block boxes identical under the code
  normalization (internal whitespace preserved). PDF-vs-article.md byte
  comparison is never performed
- every figure and extract on the same page in both outputs
- **color**: per-page (text-run, fill color) sequences and rule/background
  paint from the content streams numerically equal after color-space
  normalization; same color space family (raster thresholds cannot see the
  near-black `rgb(5.5% 7.5% 8.5%)` body ink against pure black; this clause
  can)
- **navigation**: link annotations (subtype, rect quantized 0.5 pt,
  destination page) and outline entries whose destinations land inside the
  compared domain; document Title and Lang; dates/Producer/trailer ID
  stripped and never compared
- the WeasyPrint leg's render-critic result is `pass` (guards reference
  validity); the Typst leg's critic verdict joins at WP-5.3g

### Tier G and Tier V (progress meters only)

Used to measure convergence during Phase 3; they gate nothing final.

- G, from `pdftotext -bbox-layout` (pinned poppler): same line count per
  prose block; per-line first-word x and line y within tolerance; G1 =
  2.0 pt, G2 = 0.5 pt (G3 = 0.1 pt is subsumed by Tier E's quantum)
- V, from the pinned `pdftoppm -r 300` (WP-0.2c's implementation, poppler
  pinned by WP-0.1; revision 39 withdrew WP-0.2f, so no selection is
  pending and the meters are the only raster consumer), hard fail on raster
  dimension mismatch: pixel differs when any channel delta exceeds 24/255;
  V1 = below 1.0% of the page differing, V2 = below 0.1%. One rasterizer
  for both, so the meters, the report and the gate never disagree about
  what a page looks like

### Tier E (exact; the gate; fully mechanical)

- **canonical display list**: both PDFs dumped by the pinned device-level
  tracer (the Rust content-stream interpreter in `mag/src/parity/streams.rs`,
  decided and recorded in parity.yaml `tools.display_tracer` by WP-0.2b) and
  normalized per page IN PAINT ORDER (never sorted: sorting erases z-order;
  the diff REPORTER may sort for readability, the comparison never does):
  every text show as (Unicode string, font name via the `font_name_map`,
  size, fill color, position, **text matrix**, **glyph count**), every
  vector path as
  (operators, points, paint, stroke parameters), every clip operation as an
  ordered entry so each element carries its active clip stack (010's
  interior uses `W`/`W*` clipping heavily), every image as (SHA256 of
  decoded RGBA pixels with any SMask composited into the alpha channel
  before hashing, **placement matrix**), plus annotations, outlines, page
  boxes. Colors in one normalized space.
  **Quantization has two rules, because a matrix carries two kinds of
  number** (WP-0.2e's verifier): TRANSLATION components are lengths, and
  the 0.01 pt quantum bounds them directly, as it does every plain
  coordinate. LINEAR components are ratios, and their positional effect is
  multiplied by the accumulated advance inside the show, so the same
  numeric quantum admits a displacement proportional to the line measure:
  `(half quantum / font size) x measure`. Measured: a 34-glyph 226.8 pt
  line at 12 pt whose `trm[0]` differs by 0.00499 quantizes identically and
  yet ends 0.0945 pt away, and a 0.000415 rad rotation does the same
  vertically. Images are NOT affected, because their matrix maps the unit
  square directly, so the error stays inside the half quantum.
  What Tier E therefore asserts for text is geometric equality of glyph
  ORIGINS; everything downstream of the origin within a show is covered
  photometrically by the raster bound. That is the same division revision
  10 already recorded for intra-line placement, with a second mechanism
  named.
  Any ExtGState alpha other than 1 is fail-loud unsupported (today all 162
  entries in 010 are `/ca 1 /CA 1`). The two canonical lists must be
  **equal**.
  The matrices and the glyph count are WP-0.2e's additions: a start point
  plus a size magnitude cannot see a mirrored glyph run, a bounding box
  cannot see a flipped image, and the decoded string cannot see a ligature
  standing in for its components (WP-1.1 measured that difference between
  these two engines). None of the three is sub-quantum drift, so recording
  them costs nothing and can never false-fail. Glyph COUNT, never raw CID
  codes: the engines subset and assign codes independently, so codes would
  false-fail everywhere.
- **what the display list cannot see, enumerated.** Revision 9 claimed this
  set was one item and was wrong; revision 15 closes most of it
  geometrically rather than photometrically, because WP-0.2f proved pixels
  cannot do the job. Each item says what covers it now:
  1. **intra-line glyph positioning** (TJ kern numbers, and `Tc`/`Tw`/`Tz`
     within one show): CLOSED by per-glyph positions. It was the raster
     clause's whole reason for existing. Measurement that made this urgent:
     in 010's reader.pdf, 54 interior pages carry 360 text objects and 1488
     shows, and **zero** shows inherit a previous show's advance, because
     `Td`/`TD`/`T*` reset the text matrix from the line matrix. Nothing
     downstream ever exposed a difference, so before per-glyph positions
     the intra-line spacing of every line was free: same string, same glyph
     count, same origin and same matrix admitted ARBITRARY internal
     spacing, not merely the 0.0174 pt the two engines happen to differ by
     today. That is why "declare it out of scope with the measured caveat"
     was rejected: the caveat describes today's measurement, not a bound.
  2. **glyph substitution preserving count and advance** (a stylistic
     alternate): CLOSED by WP-0.2i's second target, mapping character codes
     to GIDs through the SHARED vendored face. Raw CID codes stay
     forbidden, since the engines subset independently, but the font-file
     digests are already proven identical, so the GID behind a code is
     comparable. This mattered less while rasters guarded it; with rasters
     demoted it would otherwise be unguarded, so it is scheduled rather
     than tolerated.
  3. **optional content and marked-content groups**: `BMC`/`BDC`/`EMC`/
     `MP`/`DP` are no-ops in the tracer, so content a viewer would hide
     appears as painted. Neither engine emits OCGs today. WP-0.2i turns
     this from a silent blind spot into a FAIL-LOUD stop: an actual
     optional-content membership fails rather than paints.
  4. **annotation appearance streams**: annotations are compared by
     subtype, rect and destination, not by `/AP`. Links draw nothing in
     this design, so WP-0.2i fails loud on an annotation that carries an
     appearance stream rather than leaving it uncompared.
  5. **transform-amplified intra-show displacement**: CLOSED by the same
     per-glyph positions, which are recorded in DEVICE space and therefore
     show the amplified effect directly. A linear-component difference
     below half a quantum displaces glyphs by up to
     `(half quantum / font size) x measure`, 0.0945 pt measured at 12 pt
     over a 226.8 pt line and 0.1625 pt derived at body measure; against a
     drift bound of `k x 0.000732 pt`, which is 0.0512 pt at a 70-glyph
     line, that fails as it should.
  Deliberately out of scope rather than blind: `/PageLabels` and other
  viewer-only metadata, which no printed page shows.
  With 1, 2 and 5 closed and 3 and 4 made fail-loud, Tier E becomes an
  entirely GEOMETRIC claim. That is a simpler sentence to defend than
  "geometric plus photometric", and it no longer depends on a bound in a
  domain (ink) where the noise is 30/255 rather than 0.0174 pt.
- **per-glyph positions** (WP-0.2i), which REPLACE the raster guard as
  Tier E's third leg. Every text show additionally records the quantized
  DEVICE-SPACE offset of each glyph from the show origin, and the two
  sequences must agree within a bound that is DERIVED FROM THE MECHANISM,
  not fitted: WeasyPrint advances by an integer count of 1/1024 px (Pango),
  Typst sums exact font units, so the legitimate difference at glyph k is
  at most `k x 1/1024 px` (0.000732 pt per glyph; WP-1.6 measured the
  realized rate at 0.000173 pt per glyph, well inside it, over all 69,071
  glyphs). The bound is a FUNCTION OF POSITION IN LINE, not a flat number,
  which makes it tighter everywhere except the end of the longest line.
  - **shape, which does the real work**: a legitimate difference
    ACCUMULATES, so the difference sequence must be one-signed and monotone
    non-decreasing in magnitude. A compensating kern produces a bump that
    returns toward zero, so it fails on shape at **every physically
    reachable magnitude**, and the ceiling stops depending on how large a
    fault is. Stated accurately rather than absolutely (revision 42, rule
    10): there IS a detection floor, measured between 9.16e-08 and
    9.16e-07 pt by a mid-show bump family (displace at glyph 10, return at
    glyph 20, all 54 pages) at seven magnitudes: 2Q, Q, Q/2, Q/4 and Q/100
    all fail with 40 violations each, while Q/1000 and below go invisible.
    Size-independence survives everything that matters, because that floor
    is about 7,000x below one Pango tick and therefore unreachable by any
    real engine difference, but "at any magnitude" was the stronger claim
    and it is not literally true.
    **The mechanism, which corrects a natural wrong intuition**: one
    expects a half-quantum bump to round away. It does not, because base
    offsets are spread across the quantum grid, so among ~68,800 glyphs
    some always sit near a boundary and cross it. That is WHY
    size-independence holds, and it is worth keeping beside the number.
  - **two-sided, as before**: floor from the drift fixture WP-0.2f already
    built and proved display-list equal (69,071 glyphs, 1,503 shows);
    ceiling from compensating-kern fixtures at 0.02 pt and below. Derive
    the floor with a CTM-COMPOSING perturbation through the Rust tracer,
    per WP-0.2f's recommendation: perturbing raw operands through pypdf
    cannot produce display-list-equal fixtures, because `Td`/`TD` are
    relative, `cm` composes, and the display list quantizes device space
    while the oracle composes a 4/3 px-to-pt scale into `Tm`.
  **Why the raster guard is gone, and it is not because it was hard.**
  WP-0.2f tried it properly and the record is
  `meta/verification/evidence/WP-0.2f.md`; do not repeat that work. The
  winner, `mutool draw` 1.26.4 supersampled 8x, does NOT FreeType-grid-fit
  outlines, which was the hope, but it ROUNDS TEXT-OBJECT ORIGINS to the
  device grid, so it is as sensitive to a sub-pixel origin shift (242) as
  poppler (241); `pdftocairo` sits near 106 and `-A 8` changes nothing.
  Floor 30.125 against ceiling 30.125 is a ratio of 1.00, and the
  linear-matrix term brackets at 151.641, exceeding every ceiling measured,
  so the window is INVERTED rather than merely narrow. The escape hatch
  closes too: perturbing origins within 0.001 pt still reaches 122, because
  among 69,071 glyphs some origin always crosses a rounding boundary, so no
  finer display-list quantum rescues it. Pixels cannot bound what the
  display list cannot see, at any resolution, because every rasterizer
  snaps text origins. Supersampling moves floor and ceiling together and
  costs 9 to 15 minutes a run against 82 seconds today.
- **rasters are Tier V meters only** from here, which is where the plan
  already said they gate nothing. `pdftoppm -r 300` continues to serve
  them, unchanged, and `mag/src/parity/raster.rs` needs no rewrite.
- every Tier S clause.

**"EXACTLY the same" = Tier E over every compared page of edition 010
(en).** No residual-acceptance path exists: a divergence that cannot be
driven to Tier E is `Status: blocked` and a plan revision (fail loud), never
a waiver.

### Known divergence sources and their treatment

| Source | Treatment |
|---|---|
| Line breaking (Typst optimizes, WeasyPrint is greedy) | `par(linebreaks: "simple")` in the Typst template for the parity phase. MEASURED (WP-1.2): 148/149 paragraphs identical, zero structural misses; the one miss is a 0.01 pt width disagreement whose source is NOT yet established (WP-1.1's shaping numbers do not account for it), measured by WP-1.6 then fixed under WP-3.1 |
| Hyphenation dictionaries (Pyphen vs Typst's hypher) | DECIDED (WP-1.3, option b): off in both engines for parity, scoped to `:lang(en)` so Spanish editions keep it; WP-1.5 applies the switch, WP-4.3 is mandatory. Measured cost of disabling: zero page-count changes, zero new cap violations, 428 lines rebroken |
| Justification | the design is ragged-right. CONFIRMED (WP-1.2) as a selector fact: the stylesheet's only `text-align` declaration is in the `@bottom-right` folio box and body text inherits `start`. Precisely: the word `justify` does occur four times, every one of them a flexbox `justify-content` or comment prose, none a `text-align` |
| Text shaping (Pango+HarfBuzz vs rustybuzz) | same vendored TTFs. MEASURED (WP-1.1): 1488/1488 lines with identical glyph sequences, per-glyph advances within 0.00073 pt. Requires `liga`/`clig` off wherever letter-spacing is set (Pango suppresses ligatures under tracking) and tracking applied as exactly `(n-1) x letter_spacing` |
| Glyph advance quantization (WeasyPrint breaks on `PangoRectangle.width`, an integer count of 1/1024 px; Typst sums exact font units) | RESOLVED as to mechanism by WP-1.6: systematic and one-sided at 0.000173 pt per glyph, mean drift 0.010476 pt, max 0.017432 pt, and 604 of 899 body lines exceed the 0.01 pt quantum. Two distinct consequences, do not conflate them. (a) LINE BREAKING: exactly one line of 899 flips, block 135; fixed by widening the Typst body column to WP-1.7's measured midpoint. (b) INTRA-LINE GLYPH POSITIONS: invisible to the display list at SHOW-level granularity, which is why revision 15 records per-GLYPH positions (WP-0.2i) and derives their bound from this very mechanism; the raster guard that used to carry this was withdrawn when WP-0.2f proved it cannot. do not chain WP-1.1's 0.009897 pt to these figures: it was measured with hyphenation ON over 1402 lines, WP-1.6's over 899 with it OFF, and drift accumulates per glyph, so they describe different line populations rather than different methods (rule 9) |
| Syntax highlighting (pygments vs a Rust highlighter) | (text-run, fill color) sequences at the content-stream level (WP-3.3), never raster; 010 carries NO fenced code blocks or extracts, so WP-3.3 gates on a dedicated fixture edition, not vacuously on 010. Read this clause as STRICT rather than lenient (revision 33): print code is pygments-highlighted via `html_edition.py:660` and coloured by the print CSS, so a different tokenisation gives different colours and FAILS the gate. It is satisfied by reproducing pygments' tokenisation up to the equivalence the CSS colour map induces (about seven colours over 31 classes), not by matching class names. `syntect` is RULED OUT by measurement: it does not match pygments' tokenisation |
| Font names (WeasyPrint embeds aliases: Magazine-Serif, Magazine-Sans, ...; Typst embeds the faces' real names) | `parity.yaml font_name_map`, authored in WP-0.2b, each mapping pair validated by identical font-file digests |
| pypdf rewrite noise on inner pages | measured by WP-0.2c's merge calibration; found noise becomes an explicit normalization rule before it can be mistaken for an engine diff |
| PDF metadata, subset names, object order, compression | normalized away or never compared |

Post-flip Typst-native improvements (optimized breaking, native hyphenation
if disabled during parity) are deliberate design changes with their own
before/after comparisons (WP-4.3); out of scope here.

## Normalization

- extraction by pinned tools for both PDFs
- Unicode NFC; collapse whitespace runs to one space (prose only: inside
  code-block boxes internal whitespace is preserved); rejoin words split by
  a line-end hyphenate character; strip soft hyphens
- the machine-readable spec lives in `meta/verification/parity.yaml` under
  `normalization:` (`strip_pdf_keys`, `whitespace`, `hyphen_rejoin`,
  `merge_rewrite_rules`, `font_name_map`); the comparator implements
  exactly that spec and nothing more
- colour normalization is COMPUTED, not table-driven: `g`/`G` to an rgb
  triple (family gray), `k`/`K` via (1-c)(1-k) (family cmyk), `rg`/`RG`
  kept (family rgb), components quantized at 1e-6, and every other colour
  operator (`cs`/`CS`/`sc`/`scn`) fails loud. Revision 8 listed a
  `color_space_map` key for this; WP-0.2b needed no entries and no WP owned
  it, so WP-0.2e deletes the key. A colour space that needs a mapping table
  arrives as a fail-loud stop, not as a silent default
- `merge_rewrite_rules` is measured empty (WP-0.2c): `replace_outer_pages`
  leaves inner pages display-list equal and raster zero-diff

## Reference stability (no pinning)

- `mag parity 010` stages the working tree's edition 010 inputs ONCE
  (edition.yaml, the run's manuscripts, `library/sources/<ids>` including
  media, the CSS, the fonts) and renders both engines from that one staged
  copy in one invocation. Same bytes in, so one comparison cannot drift; no
  corpus file, no content commit, no golden storage.
- **Staleness guard**: 010 is the live intake edition, so content can
  change between runs. Every verdict and every `baseline.json` entry
  records the staged-input digest it was computed from; `mag parity`
  refuses ratchet comparison and page-set scoring when the current digest
  differs, and the baseline is then rebased by the verifier from a fresh
  run. Page sets are stored as RULES in parity.yaml and computed per run
  from the oracle leg's manifest, never as page-number values.
- **Where the content-final gate sits, and why there** (revision 12):
  **WP-3.1**, the first WP whose acceptance depends on a baseline entry
  surviving from an earlier run. Everything before it compares two legs of
  ONE staged copy in ONE invocation, so it proves the legs agree rather
  than anything about the corpus, and a content change costs a re-render
  and a re-run of that WP's verify clauses. Phase 2 runs against an empty
  baseline; no Phase 2 WP may write or raise a baseline entry, and the
  first is written by WP-3.1's verifier. What a mid-Phase-2 content change
  may NOT invalidate: nothing, because nothing accumulates before WP-3.1.
  Recorded as a decision, not left implicit: gating Phase 2 on a live
  intake edition would stall the whole engine build on a question the
  staleness guard already answers, and would build the engine against a
  frozen snapshot it could overfit to.
- **Zero model calls.** `mag render` can invoke a model to patch figure
  anchors (`patch_anchors` in `mag/src/render.rs`); parity renders run
  `--no-model` (WP-0.0) and abort listing pending anchors instead. Edition
  010's anchors are resolved through the normal pipeline before parity work
  starts, once.
- The run directory is passed explicitly (`--run`, existing flag); parity
  records which run it used in the verdict.
- WP-0.1 proves the WeasyPrint renderer deterministic (render twice,
  identical dumps) so a fresh oracle leg per run is sound. Fields that
  legitimately differ between runs (timestamp-shaped, scratch paths) go in
  `normalization.strip_pdf_keys`; any other difference is `awaiting-fran`
  as a repo bug, never normalized away by the agent.
- **CONCURRENT PARITY RUNS SHARE ONE OUTPUT PATH, and did so for days.**
  `out_dir` is hard-coded to `output/parity/<edition>` with no override,
  and WP-0.2g OBSERVED two agents' runs writing the same `verdict.json`
  concurrently. The dangerous outcome is not interleaved bytes, which
  produce invalid JSON and fail loudly; it is one process's write
  completely replacing the other's, so a reader gets a COMPLETE, VALID
  verdict from the WRONG run: a plausible wrong number with no error. Every
  parity-derived figure measured while another agent ran parity is in the
  affected class, including ones already accepted. WP-0.2k carries the fix
  and proves it by running two invocations CONCURRENTLY rather than by
  reading the code, since the hazard was found by observation.
- **The retrospective audit is a PROVENANCE audit, and it needs no
  re-runs, but its power is NARROWER than revision 44 claimed.** Corrected
  in revision 49 after checking the source rather than trusting the
  claim: every verdict records `a_reader_sha256` and `b_reader_sha256`, so
  a crossed-over verdict carries the WRONG artifacts' hashes. It does NOT
  universally record `staged_input_digest`: that field is
  `skip_serializing_if none` and is populated only in the render mode that
  stages its own inputs, so every `--pre-rendered` verdict, which is how
  most WPs run parity, emits no such key and no `staleness` either.
  **What the two reader hashes DO discriminate**: a verdict wholly
  replaced by a run over DIFFERENT artifacts, which is the dangerous case.
  **What they CANNOT** (rule 10): pin the staged inputs those PDFs came
  from, so two runs over the same two PDFs built from different staged
  inputs are indistinguishable by this check alone. The audit verifies the
  emitted field list itself rather than trusting any description of it,
  re-derives its buckets from the fields that exist, and states that
  limitation.
  **RESULT (revision 54, `8a03c1a`): CLEAN, no mismatches**, five digests
  and one reader-hash pair checking to the byte, over 139 cited parity runs
  at `ba9c3ea` (64 digest-bearing across 19 files, 47 distinct; 75
  digest-less), **139 being a FLOOR rather than a total** since seven of
  the eleven digest-less rows are second-hand. So the `out_dir` hazard has
  corrupted no recorded number that can be checked.
  **And `staged_input_digest` is RETIRED as a provenance instrument
  entirely, which is further than the limitation above.** Where the field
  DOES exist it is IDENTICAL across seven render directories of edition
  010, so it has zero discriminating power even in the staging modes: not
  mode-limited, useless. Emitted shapes verified from source and from two
  real verdicts: `--pre-rendered` 8 keys at `521ab79` (9 at `ba9c3ea`), no
  `staged_input_digest` and no `staleness`; `--oracle-only` 12, a strict
  superset. Nothing in this plan should propose it as a provenance check.
  **Corpus figures do not move with the render**, measured over five
  renders of 010 with five distinct `reader.pdf` hashes at one fixed base:
  identical glyphs, shows, domain and page count in all five. A
  disagreement between two corpus figures therefore cannot be a render
  artefact. The audit deliberately did NOT push further: it rules out the
  render, it does not prove base-mismatch over corruption, and it tested
  four figures on one edition rather than the whole clause family.
  That is the check, and it works on
  evidence already written:
  - evidence recording the verdict digest AND its input hashes: confirm the
    inputs are the artifacts that WP claims to have compared. A foreign
    hash is a crossed verdict. No re-run.
  - evidence recording only a verdict digest: re-run to confirm the digest
    reproduces, which a verifier does anyway.
  - evidence recording neither: re-measure.
  **STANDING HABIT for every WP from here, not a worklist item: print the
  verdict's `inputs` block beside the digest, and name the base.** A figure
  then lands in the first bucket in seconds, with no re-run ever needed.
  The case is empirical rather than principled: bucket 1 had ZERO members
  at `ba9c3ea`, and WP-5.5a adopting the habit on its own initiative made
  it the first and only one, its check passing (`0460c081...` and
  `15d3bd5a...` resolving to the two worktrees in the claimed order, 85
  seconds apart). One agent's voluntary habit moved the corpus from
  unverifiable to one verified member.
  **The audit's worklist, in order, with the first item LOAD-BEARING:**
  - **WP-0.2i's floor `stairdrift`, the `4.00x` margin, has NO DIGEST** and
    survives only on two agents having measured it separately and agreed.
    That is the gate's floor. Its replay therefore **ESTABLISHES the
    provenance rather than confirming it**, so the digest, base and input
    hashes are recorded as new facts, not checked against something already
    written. Keep that distinction in the evidence: a replay that creates
    the record it appears to verify must say so.
  - WP-2.0b's `11a9c0a8` against its verifier's `38f91a94` for the same
    oracle-only run: a genuine conflict, one run at `e5e741a` settles it.
  - WP-0.2d's 21 digests including the inherited `241`; then
    WP-0.2e/0.2b/0.2c/0.0c/1.3; then 54 digest-less fixture runs.
  **WP-0.2k gates all of it.**
  Cheaper than re-running what matters, and unlike accepting them on the
  argument that corruption would look obviously broken, it is a check
  rather than a belief. The argument for acceptance is in fact WRONG for
  the case that matters, since a wholesale replacement is exactly the
  outcome that looks fine.
- **Recorded as configuration, per rule 9's spirit**: every parity number
  taken before WP-0.2k lands was measured under a known-unsafe condition,
  with six to nine agents sharing one output path, and that belongs in the
  number's configuration as much as hyphenation state does. The affected
  window opens where concurrent parity runs began and closes when WP-0.2k
  lands; the affected class is parity-derived figures only.
- Tool versions (python, uv, weasyprint, poppler, mutool if used, typst
  crates, rustc) are recorded in `parity.yaml tools:` and asserted by
  `mag parity` at startup.
- Behavioral changes to `src/magazine/` are forbidden except in WPs naming
  it under Owns (WP-0.0b, WP-0.0c, WP-1.5, and WP-4.3's revert). Phase 1
  spikes may instrument oracle files uncommitted, working tree only,
  `git status` clean at WP end.
- **Every sanctioned oracle change compares the WEB tree as well as the
  reader PDFs**, byte for byte over `en/web/`, and states which files
  changed and why. This is binding, not advisory: WP-0.0c's first attempt
  left `pdftotext` dumps, `pdfinfo` boxes and the critic report all
  unchanged while silently deleting nine articles' source QR links,
  because `web_edition.py` recognizes its own markup by exact tag string.
  A verify clause phrased only in terms of the PDFs would have passed it.
  The comparison is meaningful because web HTML is byte-deterministic
  across renders, which WP-0.0c established over all eleven files and
  WP-0.1 never covered.
- The web tree is deliberately NOT a parity-ladder clause. During Phase 2
  and 3 the Typst leg produces no web output at all, so a tier would
  compare one side against nothing and pass vacuously, which is the defect
  WP-0.2g exists to stop reporting as a pass. The web tree becomes
  engine-comparable only at WP-5.6, where `--engine typst` runs the web
  path natively, and WP-5.5's byte-identical `web/` oracle is what proves
  the port. Until then it is guarded by render determinism plus the clause
  above, and that is the whole of its protection, stated so nobody assumes
  otherwise.

## Architecture

- The Typst engine lives in `mag/src/typeset/`, embedding the Typst crates
  behind a `World` serving the vendored fonts read directly from
  `src/magazine/assets/fonts/` (one copy while both engines coexist; WP-6.1
  relocates). Versions proven and pinned by WP-1.4, all exact:
  `typst`, `typst-layout`, `typst-library`, `typst-pdf`, `typst-syntax`, each
  `=0.15.1`. `typst-layout` and `typst-syntax` are NOT optional (`PagedDocument`,
  `PagedIntrospector` and `Page` live in the former, the main `FileId` needs the
  latter's `RootedPath`/`VirtualRoot`/`VirtualPath`); `comemo` is not needed as a
  direct dependency. MSRV 1.92 against the repo's rustc 1.96.0, no edition bump.
- **`mag parity` needs ONE DIRECTORY NAMED `prompts`, and what an
  "isolated cwd" actually requires is an UNSHARED `out_dir`.** Revision 49
  said parity refuses to run outside a repo root so isolation must mean a
  worktree; that was over-strong, and the audit ran everything from a
  symlink farm. The check at `mag/src/main.rs:218` is literally
  `Path::new("prompts").is_dir()`. A worktree satisfies the instruction and
  so does a symlink farm; neither is the point. The hazard the instruction
  was written for is the SHARED `out_dir`, so that is what an isolated run
  must actually avoid.
- **A pipe MASKS exit status.** `<command> | tail` reports the pipe's
  success, so `set -e` does not abort and any cleanup runs even when the
  command failed. This cost the planner two rebuilt commits when a failed
  `git merge --ff-only` was piped to `tail` and the temp branch was deleted
  anyway. Use `set -o pipefail`, or gate on the real exit status with an
  explicit `if`.
- **But `set -o pipefail` then ABORTS ON AN EXPECTED-EMPTY `grep`**, since
  grep exits 1 when it matches nothing, so under `set -e` the statement
  after the pipe never runs. Verified. This is a hazard the previous note
  CREATED, by telling every agent to set pipefail, and the plan's own
  U+2014 scan is exactly that shape: a grep whose empty result is the
  success condition. Remedy: `|| true` on any pipeline whose empty result
  is the expected one. The pair is the real guidance, since either note
  alone produces the other's failure.
- **Environment trap, found by a rule-12 replay rather than by the
  authoring run**: `TYPST_ROOT` is the typst CLI's PROJECT ROOT, not an
  install prefix. WP-1.8's first replay failed outright with
  `source file must be contained in project root` because the name had been
  used for an install prefix. Command blocks unset it, and the guard is
  proven by running the second replay under a deliberately HOSTILE
  `TYPST_ROOT`, which is the straddle rule's spirit applied to an
  environment variable: do not merely unset it, show that the unset works
  against a value that would break it.
- Measurement uses both Typst APIs, for different questions (WP-1.4): the
  **frame walk** (`pages()` -> `Page::frame` -> `Frame::items()`, recursing
  into `Group` while composing `Transform`) is primary and yields one
  `TextItem` per laid-out line, `Shape` for rules and ornaments, `Image` whose
  `Point`+`Size` IS the figure placement box, and `Link` before PDF export;
  **introspection query** is secondary and is the right tool for toc and opener
  logic. They report different y for the same heading (query anchor vs text
  baseline); the consumer picks deliberately and records which. Typst's PDF
  export is byte-reproducible, so the typst leg of a verdict is stable.
  Faces: Source Serif 4 SmText
  Regular/Italic/Bold + Display Semibold, Inter
  Regular/Medium/SemiBold/Bold, Geist Mono Regular/Medium/SemiBold, Archivo
  Condensed Bold (cover and web edition).
- `mag render <NNN> --engine weasyprint|typst`; the default comes from
  `magazine.toml [render] engine`, today dead wiring (`mag/src/render.rs`
  hardcodes weasyprint; only `[publication] name` is read); WP-2.0a makes
  it real. `weasyprint` = today's bridge call, unchanged.
- The comparator is `mag parity`:
  - `mag parity 010 --pre-rendered <dirA> <dirB>` compares two output
    trees (WP-0.2a..c)
  - `mag parity 010 [--run <dir>]` stages once, renders both engines
    (`--no-model`), compares; exits nonzero below `baseline.json` or on
    any failed clause the baseline says was passing (WP-2.0b)
  - `mag parity 010 --set <page_set>` scores one page set for in-WP
    iteration; acceptance always runs the full command
  - the WeasyPrint leg is cached per staged-input digest within a working
    session (WP-0.1's determinism proof is the license); the verdict
    records the cache key
  - outputs: `output/parity/010/verdict.json` (byte-deterministic: no
    timestamps, durations, hostnames, absolute paths) and `report.html`
    (side-by-side pages, diff heatmaps, per-line and display-list diff
    tables). `output/` is gitignored; durable records are verdict digests
    in evidence files (rule 2)
- **Ratchet.** `meta/verification/baseline.json` records per page the best
  tier achieved (including which S clauses pass). `mag parity` compares the
  working-tree baseline against `git show <base>:...` and refuses to run if
  any entry was lowered; raises are computed and committed only by the
  verifier (rule 3). A change that must temporarily regress a page lands
  together with its fix in one WP (Phase 3 is serial).
- **Page sets.** Phase 3 scoring filters: WP-2.0b writes the derivation
  RULES to `parity.yaml page_sets:` and the comparator evaluates them per
  run from the oracle leg's `edition-manifest.json` (toc and opener fits
  added by WP-0.0b); engine WPs never choose their own scoring pages.
- The Typst engine emits the layout result the bridge reports
  (`RenderLayout` shape: toc, article_pages, editorial_pages, figure
  placements with box_points, frame usage, terminal balance, opener fits);
  compared against the oracle leg's `edition-manifest.json`.
- `measure_article`/`measure_edition` are human-invoked via `mag render
  --operation ...` today; produce does not call them. Layout parity still
  matters: those numbers gate page caps.

## Subagent execution protocol

1. **Owned paths.** A WP may create or modify only the paths its brief
   lists. Every WP implicitly owns its evidence file. A WP adding crate
   dependencies also owns `mag/Cargo.toml` + `mag/Cargo.lock`. Pairwise
   serial regardless of the graph: (b) `mag/src/typeset/**` or
   `mag/src/render.rs` owners, (c) `mag/src/parity*` owners. Clause (a),
   Cargo-file owners, was DROPPED in revision 18 and replaced by rule 1a
   below; (b) and (c) stand, because they serialize genuine LOGICAL
   coupling (two WPs editing the same engine or the same comparator can
   both be individually correct and jointly wrong), where (a) only ever
   serialized a MECHANICAL conflict in a generated file.
   Acceptance includes the verifier running
   `git diff --name-only <base>` against the Owns list. A WP diff touching
   any `evidence/*.verify.md` or `baseline.json` is rejected by the
   orchestrator before a verifier is spawned.
   **A non-owner who needs a change in someone else's file asks for an OWNS
   EXTENSION; it does not self-grant, however small the change.**
   WP-5.3b-i re-exported `GLYPH_QUANTUM` from `mag/src/parity.rs`, which
   rule 1c assigns to WP-2.0b as comparator territory, and got a correct
   result its verifier adjudicated clean twice. It STAYS; this is a rule
   for next time, not a revert. But the plan had ALREADY answered this
   exact question for WP-0.2h's seam, where the one-line fix "belongs to
   WP-2.0b, which holds `parity.rs`", so permitting it now would contradict
   a decision already taken. Two reasons it is not a sanctioned exception:
   "behaviour-free" is a judgment the writer makes about their OWN change,
   which is the class of self-assessment this execution keeps finding
   wrong; and a `pub use` is precisely a change to a module's PUBLIC
   SURFACE, which is what WP-0.2h's seam defect was about, in a file where
   another agent had uncommitted work at the time.
   The cost objection is already answered by a mechanism this plan has used
   five times: a scoped Owns EXTENSION granted by the orchestrator, which
   keeps the audit trail and does not queue behind the owner's schedule.
   Reach for that rather than self-granting or waiting.
   **A PORT BLOCKED BY A PRIVATE SIBLING HELPER IS NOW THE PLAN'S MOST
   REPEATED WALL, hit three times, so treat it as expected rather than as
   an incident.** WP-0.2h's tracer seam (blocker 1), WP-5.4a's
   `is_python_space` and `py_str`, and WP-5.3b-iii's
   `mag/src/critic/metrics.rs:411 fn resize`. The cause is structural: this
   plan ports a Python module tree into a Rust module tree, Python's
   default is that a sibling can reach a `_helper` and Rust's default is
   that it cannot, so **every port that needed a private helper in Python
   needs a visibility decision in Rust**, and the decision falls on an
   agent who does not own the file. Two responses are possible and only one
   is right. WP-5.4a duplicated, and the plan then needed WP-5.1e to lift
   the copies back out. WP-5.3b-ii refused to duplicate **because two
   copies would be pinned to EACH OTHER rather than each to Python**, which
   is the reason the duplicate-helper rule exists and is the right reading
   of it. So: **a blocked port asks for a scoped Owns extension naming the
   ONE item and the ONE word (`pub(crate)`); it does not duplicate, and it
   does not self-grant.** A port that duplicates anyway states in evidence
   what it has therefore pinned the copy TO.
   **And the converse case exists, so the audit must NOT treat every
   same-named pair as a duplicate to be merged.** `normalize_reader_text`
   in `mag/src/typeset/content.rs` is Python-pinned;
   `mag/src/parity/text.rs:43 normalize` is pinned to NO Python oracle,
   because none exists, and normalizes PDF-extracted text purely to compare
   two extractions against each other (`text.rs:79`). They are not one
   function in two places. **Merging them would pin the Python-pinned copy
   to an UNPINNED one**, which is the precise failure this rule forbids,
   arriving through the remedy rather than through the defect. So the audit
   asks WHAT EACH COPY ANSWERS TO before it asks whether the two bodies
   match, and a pair answering to different oracles is recorded as
   deliberately separate rather than queued for consolidation.
   **A PLAN REVISION owns
   `meta/plans/typst-parity-and-rust-migration.md` and NOTHING else**, so a
   revision diff touching any `evidence/*.md` is rejectable on the same
   rule; revision 29 was such a diff and nobody checked, because the
   orchestrator diff check was being applied to worker and verifier commits
   but not to plan revisions. It applies to all three, except a WP whose
   Owns names
   baseline.json explicitly (WP-0.2a: schema and empty state; WP-5.4g:
   cover-page seed rows); only verifiers write those otherwise.
1a. **Dependency hygiene, which replaces Cargo-file serialization.** Rule
   1's clause (a) made every Phase 5 WP wait on every other, since the
   phase preamble gives them all the Cargo files; at the time of dropping
   it the queue was five deep and fed WP-5.6, which gates the flip. It is
   replaced by a check that targets the actual hazard better than the
   queue did. The hazard was never the conflict, which is loud: it is a
   bad resolution silently changing a pinned version, an unpinned `typst`
   or `lopdf` being exactly what this plan pins on purpose. Serialization
   never prevented that, because a single agent resolving badly, or a
   `cargo` run re-resolving, produces it with no second WP involved.
   A WP that adds crates must therefore:
   - add them as its LAST step before landing, and rebase onto current
     `art_directed` immediately before doing so, so the lock it writes is
     resolved against the tree it lands on;
   - on a `Cargo.lock` conflict, REGENERATE rather than hand-merge: take
     the incoming lock wholesale and re-add its own crates, letting cargo
     resolve. A hand-merged lock hunk is never acceptable;
   - verify after landing that the set of `(name, version)` pairs in
     `Cargo.lock` has only GAINED entries: none removed, none changed.
     Its own additions and their transitive dependencies are the only
     permitted delta, and the check is one script over the lock file;
   - a version that must genuinely change is an explicit, declared act in
     the evidence, and for a crate the plan pins by name it is a plan
     revision, not a WP's call.
   The pre-commit hook then runs `fmt`, `clippy` and `cargo test` on the
   REBASED tree, so a resolution that breaks the build is caught before it
   lands rather than after.
2. **Evidence.** A WP is done when its verification commands exit 0 AND it
   has written `meta/verification/evidence/WP-<id>.md` with sections:
   `## Base` (the commit branched from), `## Commands`, `## Tool versions`,
   `## Metrics`, `## Verdicts` (sha256 + tier summary of every verdict.json;
   "attach a verdict" means this), `## What is and is not proven`,
   `## Residuals`, `## Status` (`done`, `blocked`, `awaiting-fran`).

2a. **`## What is and is not proven` is REQUIRED, and has a shape.** Nearly
   every rejection in this execution has been a claim that outran its
   evidence: WP-5.3a's blanket "all 010-unreachable branches are covered by
   fixture" with a branch uncovered, WP-5.1c's "identical private copy"
   that was the pre-fix body, WP-5.1e's search recorded as proof of
   absence, WP-5.4a's per-arm coverage claim, and WP-5.4's zone statistics
   called "proven against Python" when the only assertion in the test was a
   final raster hash. None of those was a lie. In each the WP knew what it
   had tested, and the format never forced it to say what it had NOT, so
   the gap was invisible to everyone including its author. WP-5.4's rework
   added the section and said so plainly: the false claim came from not
   having one.
   - Under PROVEN, each item names the COMMITTED TEST that proves it and
     states how that test was shown to DISCRIMINATE, which is the negative
     check: what was perturbed, and what failed when it was. Rule 10
     already forbids offering an indiscriminate check as evidence; this
     puts the demonstration where a reader looks for it.
   - Under NOT PROVEN, each item names either what would prove it or the WP
     that owns proving it. Without that half the section decays into a
     disclaimer: "not proven: the back cover" is only useful if it says
     whether that is WP-5.4b's job or nobody's. **An item with no owner is
     a finding**, escalated in `## Status` rather than merely listed, since
     unowned gaps are how `color_space_map`, the cover-helper seam and the
     opener-fit vacuity each reached the plan late.
   - A SEARCH THAT FOUND NOTHING belongs under NOT PROVEN, never under
     PROVEN. WP-5.1e recorded one as proof of absence, and the luma pair is
     why that fails: detection missed it at three levels including the
     manual grep, because `299` and `19595` denote the same coefficient and
     share no substring.
   - It is not `## Residuals`. Residuals are things discovered along the
     way that someone else should know; this section is the BOUNDARY of the
     WP's own claims.
   - Applies to every WP briefed after it lands. The WPs already running
     are not re-briefed, since mid-flight churn is what rule 1 exists to
     prevent, but their VERIFIERS ask for it at acceptance: a verifier is
     already reading the evidence and building exactly this distinction to
     decide accept or reject, so asking costs nothing and catches the
     current cohort.
2b. **An env-gated test must ANNOUNCE ITS MODE.** The 010 corpus lives
   outside the repository, so gating a live-edition test on an environment
   variable is the RIGHT mechanism and the both-or-neither shape WP-5.1a
   established is the right shape. The defect is that the skipped mode is
   SILENT: WP-5.2's `imposition_matches_python_on_the_live_edition` passes
   vacuously under a bare `cargo test`, and as its verifier put it, a
   reader seeing "4 passed" would believe the live edition was compared.
   Nothing was wrong with the WP, whose real run is recorded at 1527
   seconds; what is wrong is that a run's output cannot distinguish the two
   modes without reading the source. This is rule 10 one layer down, since
   a vacuously passing test is precisely evidence that cannot discriminate.
   So: the test PRINTS or asserts which path it took, "compared the live
   edition" against "skipped, env not set", and its evidence records BOTH
   the gated result and the command that produces it, as WP-5.2 did.
   Binding on WP-5.5b, WP-5.5c and WP-5.3b, each of which needs the same
   untracked run directory and will otherwise reach for the silent shape.
3c. **Rules 9 to 12 bind VERIFIERS as well as WPs.** Nothing checks a
   verifier except its own next pass, and that is not hypothetical: one
   recorded 18/462 and 236/244 against the worker's correct 9/231 and
   118/122, exactly DOUBLED by its own counter, and caught it itself on a
   later pass. Its VERDICT was right while its NUMBERS were wrong, a
   failure mode the protocol had not named. So a verifier re-derives a
   count where it cites one (rule 9), labels its own non-discriminating
   checks (rule 10), treats its own causal claims as hypotheses (rule 11),
   and replays through the artifact rather than through its shell
   (rule 12). A verifier is not exempt from the discipline it enforces.
   **This rule works, and its limit is exactly rule 3d's gap.** Two
   self-corrections in one day, both caught by the verifier's OWN NEXT
   PASS: the doubled counter, and the retracted 31-file index reading. So
   a verifier's re-reading does catch its transient OBSERVATIONS. What it
   does not catch is a wrong ARGUMENT that produced a correct verdict,
   because nothing prompts a second look at reasoning that reached the
   right answer. Both halves are true and they are not in tension; the
   contrast is the useful part, and it is why rule 3d is about where a
   REASON is recorded rather than about re-reading.
3d. **A correct VERDICT immunises a wrong ARGUMENT, so a load-bearing
   reason must live where it will be re-read.** Nothing ever checks a
   verifier's reasoning, only its verdict, and once the verdict is right
   nobody looks again. Twice in one day: a verifier recorded counts exactly
   DOUBLED and caught it only on a later pass, and
   `WP-1.7.verify.md` section 4 justified ACCEPTANCE with "at the
   recommended constant the harness reports 149/149, so the widening fixes
   it too", **which is false as measured, since widening never fixes block
   4**. Both verdicts were right. Both arguments were wrong. Both were
   caught by a later WP tripping over the same ground BY ACCIDENT, which is
   luck, not a mechanism.
   The mechanism is about WHERE a claim lives. **A verify file is a
   TERMINAL document, written once and never re-read; the plan is a LIVING
   one, re-read continuously.** This execution has corrected many plan
   claims and, until now, no verify-file claim, which is that asymmetry
   showing rather than a coincidence. So:
   - when an acceptance rests on a REASON rather than on reproduction
     alone, that reason is restated in the PLAN or in the WP's own
     evidence, where later work collides with it. Reproduction-only
     acceptances need nothing, which keeps the cost near zero.
   - a REWORK's verifier re-reads the ORIGINAL verification, not only the
     new evidence, since a rework is the one moment the earlier reasoning
     is certain to still matter.
   Neither catches everything. Together they replace luck with two cheap
   habits, and the first addresses the case that actually bit, where the
   WP was never reworked and a different WP collided with it.
3b. **A REJECTION does not remove anything from the tree.** Nothing in this
   protocol said what happens to rejected code between rejection and
   rework, and the answer is that it SHIPS: WP-5.3b-i's rejected commit
   `26391ab` is an ancestor of `a537a24`, so its join-rule defect was live
   on `art_directed` and the rework repaired SHIPPED code rather than
   landing new code. Acceptable for an EVIDENCE-only rejection (unrecorded
   provenance, a non-running command, an unlabelled non-discrimination),
   where the code is sound and only its record is not. NOT acceptable
   silently for a CODE-DEFECT rejection, because other WPs build on the
   branch. So a rejection states explicitly **whether the defect is LIVE ON
   THE BRANCH**, and if it is, names the consumers who must not build on
   the affected code until the rework lands. The verifier writes that line;
   the orchestrator schedules the rework ahead of new work in that area.
3a. **To prove an ACCEPTED oracle did not move, hash the git BLOB.** The
   question "did this WP invalidate an earlier WP's accepted oracle" is
   answered by hashing that oracle's expectation file across every commit
   in the range, not by re-running it. Git is content-addressed, so a
   constant blob hash proves the file NEVER CHANGED ANYWHERE IN THE RANGE,
   where a passing re-run proves only that it produces the same result now:
   a file could change and change back, or a re-run could pass for a
   different reason. Strictly stronger and cheaper. WP-5.4's verifier did
   this across `5a3fa71`, `78711a5` and `e639b32`. Reserve RE-RUNNING for
   the different question of whether the WP's own code changed in a way
   that could alter the oracle's OUTPUT rather than its committed
   expectation; several briefs currently ask for the weaker check.
3. **Verifier acceptance.** The WP agent's green run is a claim. A verifier
   agent, spawned by the orchestrating session (never the WP agent),
   receives the WP's brief + the evidence file + this rule; it checks out a
   fresh worktree at `## Base` with the WP's diff applied, confirms the
   diff touches no verify file or baseline, replays `## Commands` (complete
   enough to rerun from the worktree alone, inline one-liners included),
   compares verdict digests against `## Verdicts`, and runs the Owns diff
   check. The verifier owns `evidence/WP-<id>.verify.md` and
   `baseline.json` (raise-only edits from its own rerun; the verifier is
   the only legal writer of raises). For Phase 1 spikes (uncommitted
   instrumentation, gone at WP end) verification downgrades to an
   evidence-consistency audit, stated in the verify file.
4. **The comparator and an engine never change in the same WP.** Comparator
   territory: `mag/src/parity*`, `parity.yaml`, `baseline.json`. Comparator
   changes get their own WP (WP-0.2e, WP-0.2f, WP-0.2g, WP-3.0g, WP-4.0g,
   WP-5.3g, WP-5.4g are the scheduled ones). Thresholds and the Tier E
   definition may never be loosened by any WP; loosening is a revision of
   this plan, which no WP owns.
5b. **Committing under concurrency.** The pre-commit hook runs `cargo fmt`
   and `cargo clippy` over the WHOLE tree, so a WP touching only docs or
   evidence still fails if another agent has in-progress Rust. Prefer a
   direct staged commit in the main tree when `git status` is clean for
   other agents' paths: it passes the hook first try and cannot lose a
   race. Fall back to committing from a clean worktree on a temp branch and
   fast-forwarding only when the main tree is dirty, and expect to retry
   under load: that dance re-races every time the branch moves, and a WP
   has lost three attempts to it. Never `--no-verify`.
   **THE COMPARE-AND-SWAP EXPECTED-OLD VALUE IS THE COMMIT YOU REBASED
   ONTO. Capture it BEFORE the rebase, and never re-read the branch tip at
   update time.** This protocol has told every agent to move the branch
   with a compare-and-swap `git update-ref` without ever saying which value
   to swap against, and the natural reading is the wrong one: WP-5.3b-ii
   rebased onto `883a095`, read `art_directed` at update time as `0fafae1`
   because revision 49 had landed in between, and passed that as
   expected-old. The CAS SUCCEEDED with its commit's parent at `883a095`,
   dropping revision 49.
   **Read that way, the CAS succeeds precisely in the case it exists to
   refuse.** A stale base is by definition the situation where the tip has
   moved, so re-reading the tip at update time makes the guard agree with
   whatever it finds and the protection inverts into a silent overwrite.
   Concretely: `B=$(git rev-parse art_directed)` before rebasing, rebase
   onto `$B`, then `git update-ref refs/heads/art_directed <new> $B`. If it
   is refused, the branch moved under you and the answer is to rebase again
   onto the new tip, never to re-read and retry.
   Landing check 2 catches this within seconds
   (`git merge-base --is-ancestor <pre-land tip> art_directed` returns
   false), which is why that check stays even though it looks redundant
   beside a CAS: it is the check that catches the CAS being MISUSED.
   **FOURTH LANDING CHECK, owed by the agent that LANDS: leave the shared
   index EMPTY.** Agents commit from a private worktree and move the branch
   with `git update-ref`, which moves the ref and NOTHING else: the main
   tree's index still holds the PRE-LAND content of every file the landing
   commit touched, so git reports them as staged, and what it would commit
   is the OLD content. **The index is left staging a precise reversion of
   the commit that just landed.** Syncing the working tree with
   `git show HEAD:<path> > <path>`, which the protocol already instructs,
   updates the WORKING TREE and leaves the index untouched, so following
   the protocol exactly still leaves the trap armed. After moving the
   branch, confirm `git diff --cached --name-only` returns NOTHING, and
   clear it with **`git reset -- <paths>`** if not.
   **But RE-READ BEFORE ACTING, and certainly before resetting: `git status`
   on a shared tree under concurrency is a SAMPLE, not a state.** A reading
   taken while another agent is mid-`update-ref`-and-sync shows that agent's
   land as a mass deletion, which is EXACTLY the signature this check hunts
   for, so the false positive is not a rare coincidence: **it is the check's
   own success condition arriving from the wrong cause.** It has already
   happened once, a verifier reporting a 31-file reversion of WP-2.1 and
   retracting it on its own next pass, when the index was empty, the tree
   clean, and all 31 files present.
   The danger is that the prescribed remedy is a WRITE. Unstaging another
   agent's in-flight land is bounded harm, since a path-scoped reset touches
   only the index and the landing agent restages, but it stops being
   bounded the moment someone reaches for a HARD reset because the
   path-scoped form "did not work". So:
   - a non-empty index is a reason to RE-READ after a pause, not a reason to
     act; act only if it PERSISTS;
   - when it does persist, INSPECT THE STAGED CONTENT before resetting. Both
     real incidents were identifiable by content: one staged the removal of
     a `GLYPH_QUANTUM` export that HEAD had, the other a verify file that
     existed in HEAD and on disk;
   - the general form, which applies past this check: **any index check on
     the shared tree is re-read before it is acted on OR REPORTED.**
   **AND THE RESET LEAVES THE WORKING TREE STALE, so finish the job.** A
   path-scoped reset touches the INDEX only, which is correct and is why
   the rule forbids the checkout that would fix both. The working copy is
   then still holding pre-land content, so **the next agent to read that
   tree sees a landed file as DELETED or stale**, which is the same
   stale-working-copy symptom the ref move already produces. Refresh with
   **`git show HEAD:<path> > <path>`** for each path you reset: it writes
   the working tree, touches no index, and is already the protocol's
   remedy for the ref-move case. Found in the field by the landing agent
   noticing, not by this protocol, which said how to fix the index and
   nothing about what that fix leaves behind.
   **Path-scoped reset ONLY. Never a bare hard reset, never a path-scoped
   checkout**, because other agents have uncommitted work in that tree: at
   the time this was written WP-0.2g had 43 insertions in
   `mag/src/parity.rs` plus changes in three more files sitting there. A
   path-scoped checkout and `rm` are already denied by policy here; a hard
   reset is not, so this rule forbids it.
   **The generalization: the landing checks verify what you WROTE, not what
   you LEFT BEHIND.** All three earlier checks examine the landed commit,
   its ancestry, the pre-land HEAD's ancestry and its diff, while this
   hazard lives in a different repository entirely, in the shared tree's
   index, and only becomes a defect on the NEXT agent's commit.
   It re-explains both earlier clobbers better than agent error did:
   `aa4bc01` deleted 39 files while ancestry passed and `4f20801` reverted
   `WP-5.4.md` while presence passed, and both are a stale index carrying
   old content into a new commit. The diff check catches them at the moment
   of committing, but only if the committing agent looks, which puts the
   burden on the innocent party rather than on the one who armed the trap.
   This check moves it back.
   **A third tool carries the same trap, found by the planner walking into
   it:** `git stash push -- <pathspec>` is NOT as narrow as it looks. It
   takes the pathspec from the working tree, but the stash's INDEX commit
   snapshots the whole staged state, so a stale index rides into the stash
   and is dropped with it. The diagnostics differ too:
   `git show <stash> --name-only` shows only the worktree half, while
   `<stash>^2` holds the index half. Nothing was lost in that instance
   because what rode along WAS the reversion, verified by comparing the
   stashed content against the pre-land state rather than assumed. The
   shape generalises: a narrow-looking operation on a shared tree is wider
   than it reads.
   **`git commit` commits the whole INDEX, not the paths you added.** Under
   concurrency another agent may have staged its own files, which then land
   inside your commit under your message. The planner did exactly this in
   revision 29, carrying `meta/verification/evidence/WP-5.4.md` into a
   docs commit; nothing was lost, but the attribution is wrong and a
   partially-staged file could have landed mid-edit. Commit with an
   explicit pathspec, or check `git diff --cached --name-only` before
   committing and unstage what is not yours.
   **After landing, run `git show --stat <your sha>` and confirm THE FILE
   LIST IS EXACTLY YOUR OWNS: no more, no fewer.** This is the check that
   covers the class, and it is stated about the DIFF rather than about the
   tree or the history. A deletion, a revert and a stale rider all show up
   the same way, as a file you do not own appearing in your own diff. Pair
   it with the pathspec discipline below rather than choosing between them:
   the pathspec stops contamination going IN, the stat check catches it if
   it does, and a pathspec can be correct while the working copy is stale.
   Three incidents, each fix aimed at the previous form, each new form
   passing the previous check:
   - `aa4bc01`: ancestry passed while 39 files were DELETED.
   - `4f20801` (a plan revision, the planner's own): presence passed while
     `WP-5.4.md` was REVERTED by exactly the inverse diff, 16 insertions
     against 65 deletions, removing the provenance command and replay
     hazard that WP had been rejected TWICE for omitting. Restored verbatim
     as `c5d35f7`.
   - in both, the landing agent's own checks reported success.
   **The generalization, because it keeps outrunning its fixes: each check
   verified something ADJACENT to what mattered.** Ancestry verified the
   commit's presence in history rather than its content's survival.
   Presence verified the file's existence rather than its content. Presence
   is not content. The invariant that actually matters is "my landed change
   is in the tree AND nobody else's was undone by me", and only a statement
   about the diff expresses it.
   The superseded form, kept because it is still worth doing and costs
   nothing: confirm the files you expect are PRESENT in the resulting
   tree. The
   ancestry check alone has a hole and it was exercised: commit `aa4bc01`, a
   VERIFY commit, landed from a stale base and DELETED all 39 of WP-5.2's
   files while
   WP-5.2's own commit remained an ancestor of `art_directed`, so the
   prescribed post-land check PASSED with the content gone (recovered as
   `ac443b0`). Ancestry proves a commit is in the HISTORY; it proves
   nothing about whether a later land reverted its CONTENT.
   The general principle, because this is not really about git and the
   execution has now been bitten by it twice (here, and by the
   stale-working-copy symptom where the main tree held old content after a
   ref move): **an invariant that holds over HISTORY is not an invariant
   over STATE.** Check the state you actually depend on. And note WHICH
   kind of commit did it, because the instinctive reading is that a worker
   clobbered a worker: verifiers land too, and are subject to every rule in
   this section.
5. **Repo rules apply**: `cargo fmt`, `cargo clippy -D warnings`,
   `cargo test` (includes `tools/nocomments.py`), `uvx ruff` for touched
   Python, no comments, no U+2014, hooks installed.
6. **Fail loud.** A WP that cannot meet its target writes the measured gap
   with `Status: blocked` and stops; it never weakens a check, narrows a
   page set, adds a normalization rule, or works around.
6a. **CLASSIFY every defect found, because the plan's machinery answers
   only one of the three kinds.** The axis is not severity; it is what the
   fix is pinned to and whether the item survives WP-6.1.
   - **A, port-fidelity gap**: Rust differs from Python, Python is right.
     Fix by matching Python. Every tier, oracle and fixture here is built
     for this, and the CATEGORY DIES AT WP-6.1, since a deleted oracle
     cannot be diverged from.
   - **B, a live product defect surfacing as a divergence**: the output is
     simply wrong, and would be wrong in Python too but for a guard the
     port dropped. The FIX is identical to class A, which is why this class
     hides inside it. Two things differ. **Reachability decides
     SCHEDULE**: a class-A gap in a branch 010 cannot reach waits for the
     flip, while a class-B defect is reachable from ordinary user input and
     ships wrong output the day a user writes that line. **And the
     regression test must OUTLIVE the oracle**: pin the CORRECT STRING
     directly, never "equals Python", because after WP-6.1 a
     matches-Python assertion documents nothing and no reader can recover
     why the value was right.
   - **C, both engines wrong.** Parity is blind by construction: the legs
     agree, every tier passes, the output is wrong. Not hypothetical.
     `content_label` has one beside its class-B defect: `label: false`
     prints the literal `"False"` in BOTH engines (Python's guard is
     `value is not None`, and `False is not None`; Rust's `py_str` maps
     `Bool(false)` to `"False"`). Verified by execution, not by reading.
   **EQUALITY IS NOT CORRECTNESS.** This plan proves the engines agree and
   says nothing about whether what they agree on is right, so "010 renders
   identically" is never to be written or read as "010 renders correctly".
   Class C is found by a reader or a non-parity check; nothing in Phases 0
   to 4 is looking for it, and the plan states that rather than letting the
   silence imply coverage.
   Revision 23's "a port must not be STRICTER than its original" governs
   class A only. Class B is not the port being stricter; it is the port
   being wrong, and matching Python is the fix rather than the constraint.
6b. **A DEFECT FOUND BUT NOT FIXABLE IN SCOPE IS COMMITTED AS FIXTURE DATA
   FLAGGED `known_divergence`, WITH A TRIPWIRE TEST.** "I found something
   real and cannot fix it here" has come up at least five times in this
   execution and has been handled every time by a residual paragraph nobody
   reads. WP-5.1f's answer is better and becomes the standard: record the
   measured divergence in the fixture, flag it, and commit a test whose
   FAILURE MESSAGE is the instruction, in the shape *"if this changed, the
   divergence was fixed; clear `known_divergence` in the fixture and delete
   this test"*. The two alternatives are rejected with their reasons:
   committing the Rust value as expected CEMENTS THE BUG and leaves the
   eventual fixer editing a GREEN test, which is the worst position to
   discover an intentional divergence from; and prose is the rediscovery
   problem this plan keeps paying for. The tripwire also makes the
   divergence self-retiring, since the only way to make the test stop
   failing is to do the thing the message asks.
   **A defect's LATENCY is a statement about the corpus, never a
   guarantee.** `content_label`'s is latent only because 010's 548 `label:`
   keys over 20 distinct values happen to include no bare one, which is the
   corpus rule in its ordinary form. A class-B fixture therefore carries
   the case the corpus LACKS, since that is the case the corpus cannot
   prove anything about.
7. **Fran gates** exist only where the plan must change or something
   irreversible happens. Revision 9 resolves the Phase 1 gates (1.1's
   residual, 1.2's match rate, 1.3's mechanism) as plan decisions, so what
   remains is: a discovered repo anomaly or failed spike (0.1, 5.7), 010
   [content-final before Phase 3 was REMOVED in revision 40: it failed this
   rule's own test, being neither plan-changing nor irreversible, and is
   replaced by WP-0.2k's mechanical precondition],
   the post-flip typography change (4.3),
   tools disposition and rollback deletion (6.1), and any new `blocked`
   finding that needs the plan changed (as WP-0.2d's raster bound did).
   A gated WP
   ends `Status: awaiting-fran` with its recommendation; the decision is
   recorded by Fran (commit authored by Fran or a line Fran types). No
   verification gate is human.
12. **A DEMONSTRATION MUST BE PERFORMED THROUGH THE ARTIFACT THAT WILL BE
   REPLAYED**, not through whatever the author had at hand. Both known
   instances are "it worked when I ran it", where the thing that ran was
   not the thing that was recorded, and the evidence was ACCURATE about
   what it measured while measuring the wrong thing. That makes this its
   own failure mode, distinct from rule 10's claim outrunning evidence and
   rule 11's untested mechanism. Two artifact classes, two concrete checks:
   - **A capability for another module: prove it with a CONSUMER TEST that
     imports the ordinary way.** WP-0.2h built a shared tracer seam and
     demonstrated it through a `#[path]` test include, which bypasses
     module privacy entirely; the demonstration passed, its verification
     confirmed the demonstration, and `mag/src/parity.rs` declares
     `mod display;` and `mod streams;` privately with no `pub use`, so the
     first real consumer in `mag/src/critic/` fails with
     `error[E0603]: module 'streams' is private`. The mechanism that proved
     the seam was the one mechanism that routes around the defect. A WP
     reaching for `#[path]`, relaxed visibility, a test-only feature flag
     or an altered search path says in evidence why, and what it has
     therefore NOT shown.
   - **THE CAPTION DRIFTS FROM THE COMMAND**, which is a different class
     from every other here: the command RAN, its output was ACCURATE, and
     the CAPTION was the false claim. WP-5.5a's block was captioned
     "**Every** segno call site" and searched only `src/ mag/src/`,
     returning nothing, while four call sites existed in the generator it
     had just written. Its own framing is the part to keep: **rereading
     would not have shown it.** The command looks right and the output
     looks right; only reading the OUTPUT AGAINST THE CAPTION'S CLAIM
     exposes the gap. Where the other classes are about the recorded
     artifact diverging from what was EXECUTED, this is the recorded
     artifact diverging from what was CLAIMED about it. Check, cheap and
     specific: on replay, read each block's output against its caption's
     SCOPE WORDS, "every", "all", "no other", and confirm the command's
     scope matches the claim's.
   - **A HARNESS THAT ABORTS ON FIRST FAILURE EVIDENCES ONLY THE FIRST
     FAILURE, WHICHEVER LAYER ABORTS.** The obvious form is a
     short-circuiting `assert_eq!`, which proves only the first mismatch,
     so a block demonstrating several cases must ACCUMULATE and print them
     all. The form that actually bit is one level up: WP-5.1f ran
     `cargo test --test a --test b`, which stops at the first failing
     BINARY, so its block emitted only the label failures while its caption
     promised four cases. **The assertion, the test binary and the test
     RUNNER are three separate places the same truncation happens, and only
     the first is obvious**, so a WP that carefully writes an accumulating
     assertion can still have its evidence truncated by the runner above
     it. Split the command, or run each binary separately. The check is the
     caption clause above: read the output against the caption and COUNT
     THE FAILURES YOU WERE PROMISED.
   - **HERMETICITY IS A PROPERTY OF THE WHOLE REPLAY PATH, and fixing it in
     one artifact can RELOCATE it into another.** WP-5.3b-i fixed its
     absolute corpus path properly: the test now takes
     `MAG_CRITIC_READER_PDF`, announces `MODE: full` or `MODE: skipped` per
     rule 2b, and ASSERTS when the variable is set but the file is missing,
     so a typo cannot pass silently. The verifier then ran the evidence's
     own `## Commands` block verbatim and found the hard-coded path had
     MIGRATED OUT OF THE TEST AND INTO THE RECORDED COMMAND. The test was
     hermetic; the replay instructions were not. It passed the rule below
     while failing that rule's purpose, which is why this sits above it.
     Concrete check, and it is cheap: record the `$PWD`-relative form, and
     **replay from a directory that is not the one you developed in**,
     which is the only thing that separates a hermetic instruction from one
     that merely looks hermetic.
     **And a `$PWD`-relative path is NOT hermetic if what it points at is
     GITIGNORED.** THREE WPs have now hit this, each believing it had
     complied: the form looks portable and resolves only in the tree where
     the work was done, because the corpus and render directories are
     gitignored and exist nowhere else. WP-0.2g's block 1 fails on its
     first command from a fresh worktree for exactly that reason, and the
     fix is a one-token default (`A=${A:-...}`). Stated as standing
     guidance rather than rediscovered a fourth time.
   - **A test must read only its OWN checkout.** `mag/tests/critic_text.rs:74`
     hard-codes an ABSOLUTE corpus path, the only test in the repo that
     does, so run from an isolated verification worktree it traced the MAIN
     tree's PDF while exercising the WORKTREE's code, and anywhere else it
     would silently SKIP. Both outcomes measure something other than the
     artifact under test, and since EVERY verification in this execution
     runs from an isolated worktree, a single absolute path silently
     invalidates a verification, which is the worst possible place for one.
     Paths are relative to the checkout, or the corpus arrives by the
     env-gate of rule 2b, which announces its mode.
   - **A recorded command: EXTRACT EACH `## Commands` BLOCK FROM THE
     EVIDENCE FILE ITSELF AND EXECUTE IT** before submitting, rather than
     re-running the version in your shell history. Agents run a command,
     then TRANSCRIBE it, and the two diverge exactly where quoting and
     escaping live, which is exactly where a reader cannot see the
     difference. This has caused three rejections on work that was
     otherwise sound: WP-5.1b (unrecorded oracle provenance), WP-5.4 (the
     zone oracle had no producing command) and WP-5.4b, whose recorded
     oracle PANICS because `rb"\1 fill=\"none\""` is a RAW bytes
     literal, so the escaped quotes insert literally and resvg rejects the
     SVG at char 92; correcting only the escaping reproduces all three
     digests exactly. The transcription is the failure, not the command.
     It costs one round trip per block, and it pairs with rule 3: replaying
     `## Commands` is precisely what the verifier does, so the author does
     it first.
11. **A MECHANISM asserted by the WP that found the defect is a
   hypothesis, not a finding.** Rule 9 makes a number carry its
   configuration; this carries the same discipline to causal claims,
   because the plan has now recorded two explanations that measurement
   later falsified. WP-1.2 attributed its break miss to WP-1.1's advance
   residual, which WP-1.1's own numbers ruled out. WP-5.4 attributed its
   wordmark defect to a fill-versus-stroke difference in `ttf-parser`'s
   redundant closing lineto, which its verifier falsified by reverting the
   lineto-pop and getting a byte-identical PNG. **Both times the DEFECT was
   real and the EXPLANATION was wrong**, and both times the plan had
   already promoted the explanation to a lesson before anything
   independent tested it. So: record the defect as measured and the
   mechanism as PROPOSED until an independent measurement confirms it, and
   never generalise a mechanism into a rule on first telling. A WP that
   wants its mechanism believed should test it the way the verifiers did,
   by removing the supposed cause and measuring whether the effect goes.
   **The same discipline applies to a DEFINITION, not only to a mechanism,
   and the test has a specific form: when a WP defines the BOUNDARY of its
   own comparison, ask whether the definition makes the comparison EASIER
   or HARDER.** A boundary drawn to make a comparison succeed is the
   natural suspicion about any self-defined seam, and it is answerable by
   measurement rather than by argument. WP-2.1's verifier did exactly that
   and the hypothesis FAILED: the compared text includes 835 characters
   that are never printed, which both legs must match anyway, and
   everything it excludes reduces to a single emitted value that was then
   checked against Python entry by entry. A seam that costs the author
   extra agreement is not a seam drawn for convenience. Where the answer
   comes out the other way, the WP says so and names what the boundary
   excuses it from proving.
10a. **A clause that reports HOW MUCH it compared cannot hide a vacuous
   pass.** This is rule 10 moved from evidence into the artifact, and it
   earned promotion from one WP's good idea to a rule by finding something
   nobody suspected: the navigation clause reports 84 annotations of which
   84 are links, and **0 outlines, 0 Title, 0 Lang**, so TWO OF ITS THREE
   LEGS were passing on empty-versus-empty and had been since it was
   written. It was invisible until the clause was made to state its
   cardinality. So **every Tier S clause that compares a COLLECTION reports
   the count it compared**, and the plan enumerates them here so none is
   missed by being the one nobody reached: navigation (annotations, links,
   outlines, Title, Lang), code blocks, figures and extracts. Navigation
   reports since WP-0.2g; the rest are WP-0.2k's fourth target. A clause
   comparing zero items reports `pass (0 compared)` and never a bare
   `pass`, which changes no pass/fail semantics, since empty against empty
   is still equal, and makes the vacuity visible to a reader instead of
   only to whoever goes looking.
10. **Evidence that cannot discriminate must say so**, and **when a fixture
   is labelled non-discriminating, RUN THE OPPOSITE EXTREME too: if both
   extremes pass, the question is whether the code under test does anything
   at all.** That second half is not hypothetical and it found a CODE
   defect rather than an evidence one. WP-5.3b-i honestly labelled its join
   rule non-discriminating on 010, "chosen because it is principled, not
   because this corpus can tell"; its verifier then ran the unconditional
   EMPTY join, which the evidence never ran, and that passed too. Both
   extremes passing meant the field was less discriminating than even the
   label claimed, which pointed straight at the cause: the shipped rule
   subtracts `Show.width`, in GLYPH_QUANTUM units of 9.1552734375e-05 pt,
   from `Show.x`, in hundredths of a point, inflating width by 109.2267x.
   The rule-10 label was true of the CODE, not of the corpus, and running
   one extreme rather than both is what would have hidden it. The plan already
   rules that a gate which cannot fail is not a gate, and WP-0.2g makes
   every collection clause report the cardinality it compared. This extends
   the same discipline to EVIDENCE, which is where it slipped through: an
   agreement or equality offered as proof, where both sides are an EMPTY
   SET or the SAME CONSTANT throughout, must be labelled as such at the
   point it is offered. It is still worth recording, since it shows nothing
   was invented, but it is not interchangeable with an agreement that
   reproduces a non-trivial partition, and a table of identical-looking
   ratios conceals exactly that difference. The instances that earned this
   rule: `article_opener_fits` comparing `{}` against `{}` and then nine
   `true`s against nine `true`s, WP-5.3a's tint branch, WP-5.1a's masked
   defect, and WP-5.3d's `standalone_punctuation_lines` at `0 == 0` on
   every page while reading "54 of 54" beside two agreements that do
   discriminate.
9. **A number quoted from another WP carries its configuration.** Any
   figure cited inside a WP's reasoning must travel with what it was
   measured under: which corpus and how many items, which switches (for
   this plan, above all hyphenation on or off), quantized or raw, and per
   what unit (run, line, page). Two spikes measuring different populations
   cannot be chained into a causal claim, and a WP that inherits one is
   fixing a guess. This has now happened twice: WP-1.2 attributed its break
   miss to WP-1.1's residual, and WP-1.6 explained away the gap between its
   own number and WP-1.1's with a methodological difference that does not
   exist. Both were caught by audit rather than by the authoring WP, which
   is why it is a rule and not advice.
   **A PARITY FIGURE IS ONLY MEANINGFUL AGAINST A NAMED COMMIT.** Three
   glyph figures are now in circulation, 69,071/1,503 in the plan,
   68,800/1,488 from WP-0.2i's floor, and 68,530/1,501 from WP-5.5a at
   `c1253d8`, and the cardinalities moved with them (1,733 colour entries
   and 85 annotations against WP-0.2g's 1,720 and 84, explicable by the
   source-codes asset landing in between).
   **STRUCK IN REVISION 53: this rule does NOT explain the fourth
   cross-spike disagreement, and revision 49 was wrong to offer it as the
   likely cause.** WP-0.2f's own `## Commands` block names the same
   `reader.pdf` the rework measured (`WP-0.2f.md:36`), so no commit
   difference can sit between those two numbers; measured across seven
   render trees, the per-page `(shows, glyphs)` vector is elementwise
   identical in all seven. The cause is the DOMAIN, exactly as revision 42
   proposed: 1,503 = 1,488 + 15, the 15 enumerated as 5 shows on page 1 and
   10 on page 56, all `Tj`, font `F1`, render mode `3 Tr`, which is
   invisible cover text. The rule below stands on its own evidence; it
   simply is not what was happening here, and a hedged wrong steer still
   steers, since this one was passed to two agents.
   Every parity figure therefore carries the commit it was measured at,
   exactly as rule 9 makes a number carry its configuration: for a moving
   render tree, the BASE is the configuration.
   **This clause binds BRIEFS and COORDINATION MESSAGES, not only evidence
   files.** A brief is where a number ENTERS a WP's reasoning, so it is a
   citation like any other, and the coordinator's own brief for WP-2.1's
   verifier carried two wrong counts (46 template functions for 47, 18
   `cargo test` suites for 17) neither of which came from the evidence.
   Third wrong count at the point of citation in a week, and the first
   where the citer was the coordinator rather than a WP, which is precisely
   why the duty cannot sit only on the artifacts.
   **A CITED count is RE-DERIVED at the point of citation.** Revision 38
   put the duty on the author deriving a count from its own enumeration,
   and four instances now show that is the wrong place: every one of these
   disagreements was found by a READER comparing two documents, never by
   the author of either. Citation is the moment two numbers come into
   contact and the moment nobody currently checks. So a WP that cites
   another WP's figure re-derives it from the cited WP's own artifact and
   says so, or records that it could not and why. The four:
   WP-1.2 against WP-1.1 (populations differing by hyphenation),
   ten-versus-eleven issue sites (a count beside its own enumeration),
   WP-1.7's 147/149 against WP-1.2's 148/149 (WP-1.8 reconciling), and
   the plan's 69,071 glyphs / 1,503 shows against the floor's
   68,800 / 1,488. A rule per instance stopped working three instances ago;
   this puts the check where the numbers meet.
   **A COUNT stated beside an enumeration must be DERIVED from it, not
   carried alongside it.** The plan said "ten issue sites" in its prose
   while its own enumeration listed eleven (3 + 3 + 3 + 1 + 1), and the
   slip survived several revisions because the enumeration was corrected
   and the count next to it was not. Anything briefed off the count would
   have left a site unfaulted, which is exactly what WP-5.3c is briefed
   off. When correcting an enumeration, grep for its count; when quoting a
   count, add up the list.
   The same applies to the CORPUS: a pass condition may not hard-code a
   number that edition 010 happens to have today (56 pages, nine articles,
   84 link annotations). Derive it from the oracle leg of the same run.
   Corpus figures belong in `## Metrics` as observations, never in a verify
   clause as a threshold. This is what lets Phase 2 run against a live
   intake edition at all.
8. **The brief.** A subagent receives: its WP section verbatim, its phase
   preamble, and these sections: the parity ladder, Normalization,
   Reference stability, Architecture, and this protocol. The brief bounds
   the plan text; every file in the worktree at `## Base` (completed WPs'
   evidence included) is readable. Phase-preamble Owns and commands bind as
   if written in the WP section.

## Phase 0: instrument (no engine work)

### WP-0.0 render determinism switches

- Owns: `mag/src/render.rs`, `mag/src/main.rs` (flag registration lines).
- Target: `mag render` gains `--no-model`: a render that would invoke the
  model (anchor patching) fails listing the pending anchors; the render
  result reports the pending-anchor count either way. Behavior without the
  flag unchanged.
- Verify: a fixture edition with one unresolvable anchor fails under
  `--no-model` naming the figure; edition 010 renders identically with and
  without the flag, compared as `pdftotext` dumps + `pdfinfo` boxes + the
  packaged JSONs (PDF byte-determinism is not assumed).

### WP-0.0b manifest amendment (sanctioned oracle change)

- Owns: `src/magazine/engine_render_bridge.py`.
- Target: `_render_manifest` also emits `layout.toc` and
  `layout.article_opener_fits` (today toc exists only in-process and opener
  fits only in the bridge's stdout rows), so `edition-manifest.json`
  carries everything page-set derivation and layout comparison need.
- Verify: render 010 before and after; the `edition-manifest.json` diff is
  exactly the two new keys; `pdftotext` dumps and critic report unchanged;
  `uvx ruff` clean.
- DONE, and it surfaced the gap WP-0.0c fixes: `layout.toc` carries all nine
  articles, but `article_opener_fits` emits `{}` on every render.

### WP-0.0c opener-fit attribution (sanctioned oracle change)

- Owns: `src/magazine/html_edition.py` and `src/magazine/web_edition.py`
  (the second added in flight, for the one detection fix the first one
  breaks; see the outcome below).
- Why: `article_opener_fits` is empty on every render because
  `html_edition.py` emits the opener as `<header class="article-opener">`
  while the id sits on the parent `<article>`, and the adapter's `_note_box`
  requires `data-article-id` on the header element itself. Left alone,
  WP-2.3's `article_opener_fits` comparison and WP-3.2's "opener-fit
  booleans exact" clause compare `{}` against `{}` and pass vacuously. A
  gate that cannot fail is not a gate.
- Target: the opener header carries `data-article-id`, so
  `edition-manifest.json` reports a fit boolean per article.
- Verify: render 010 before and after; the `edition-manifest.json` diff is
  exactly `layout.article_opener_fits` gaining one entry per article (nine,
  matching `layout.toc`'s ids); `pdftotext` dumps, `pdfinfo` boxes and the
  critic report unchanged modulo WP-0.1's whitelist; `uvx ruff` clean.
- Must land before WP-2.3. If the attribute turns out to change rendered
  output in any way, that is `blocked`, not a workaround.
- OUTCOME (blocked in flight, 2026-09-14, and the clause above is exactly
  why): the reader side of the target is met. `edition-manifest.json` gains
  nine `article_opener_fits` leaves whose ids equal `layout.toc`'s, all
  `true`, zero leaves removed or changed; the reader PDF is untouched
  (`mag parity 010 --pre-rendered` Tier E green, `pdftotext -raw` and
  `pdfinfo -box` byte-identical) and the critic still passes. But the WEB
  edition loses every article's source QR link: nine
  `en/web/article-*.html` plus `en/web/edition.html` change.
- CAUSE and resolution: `web_edition.py:262` detects the illustrated opener
  by matching the ENTIRE header tag as a string
  (`'<header class="article-opener">' in line`), so any added attribute
  makes the match fail, the source link is never upgraded to the
  QR-bearing `opener-source-link`, and the print-only pass then deletes it.
  The QR SVGs are still written to `en/web/assets/` with nothing
  referencing them, which is why no error surfaced. WP-0.0c's Owns was
  extended to `web_edition.py` for that one detection fix. The agent proved
  the loss was its own change rather than render variance with a third
  control render, which also established that the web HTML is
  byte-deterministic across renders, a property WP-0.1 never covered (it
  compared only `pdftotext` dumps, layout JSONs and critic results).
- Verify, amended by the above: the `en/web/` tree must be byte-identical
  except for the opener header line the change is meant to alter, and the
  nine `opener-source-link` QR references must survive. Until WP-0.0c
  lands, WP-2.3 and WP-3.2 must treat the oracle's opener fits as absent
  and say so, rather than comparing `{}` against `{}` and reporting a pass.

### WP-0.1 oracle determinism proof

- Owns: `meta/verification/parity.yaml` (initial `normalization:` +
  `tools:`), evidence.
- Target: rendering edition 010 (en) twice with `--no-model --run <same>`
  produces identical raw `pdftotext` dumps, layout JSONs, and critic
  results, byte-for-byte except fields on a closed whitelist
  (timestamp-shaped values, paths under the scratch root), which are
  recorded as `normalization.strip_pdf_keys`. Any other difference is
  `awaiting-fran` as a repo bug. Also: confirm 010 has zero pending figure
  anchors (else resolve them via the normal pipeline first, once, and
  commit).
- Verify: the double-render comparison script is inline in `## Commands`
  and reproduces for the verifier.

### WP-0.2 comparator (four serial WPs)

All four own `mag/src/parity.rs` (module registration, driver wiring) and
`mag/Cargo.toml` + `mag/Cargo.lock` in addition to the paths below.

**WP-0.2a text, geometry, boxes, verdicts**
- Owns: `mag/src/parity/text.rs`, `mag/src/parity/geometry.rs`,
  `meta/verification/parity.yaml` (tier tables), `meta/verification/
  baseline.json` (schema + empty state).
- Target: `mag parity 010 --pre-rendered` implements Tier S text, page
  count and boxes via `pdfinfo`, and Tier G via `pdftotext -bbox-layout`;
  verdict.json is byte-deterministic.
- Verify: self-test on the same weasyprint output twice: Tier S text green,
  G deltas zero, byte-identical verdict.json twice.

**WP-0.2b the display-list extractor (the Tier E instrument)**
- Owns: `mag/src/parity/display.rs`, `mag/src/parity/streams.rs`,
  `meta/verification/parity.yaml` (`font_name_map` key only).
- Target: the canonical display-list dump and comparison exactly as Tier E
  specifies (paint order preserved, clip stack carried, tracer choice
  recorded in parity.yaml `tools:`), plus the Tier S color and navigation
  clauses (projections of the same data), plus the `font_name_map`
  (WeasyPrint aliases such as Magazine-Serif mapped to the real face
  names Typst embeds), each pair validated by identical font-file
  digests.
- Verify: self-test: same PDF twice gives equal canonical lists;
  hand-built fixtures each caught: one fill color changed, one glyph
  substituted (same width), one annotation dropped, one image re-encoded
  with different bytes but same pixels (must PASS: RGBA hash equal), one
  path point moved 0.02 pt (must FAIL: above quantum), two elements with
  swapped paint order at the same coordinates (must FAIL: z-order), one
  figure clipped vs unclipped with identical paint ops (must FAIL: clip
  state), one SMask'd image with the mask altered (must FAIL: composited
  alpha).

**WP-0.2c raster zero-diff, report, merge calibration**
- Owns: `mag/src/parity/raster.rs`, `mag/src/parity/report.rs`,
  `meta/verification/parity.yaml` (`merge_rewrite_rules` key only).
- Target: Tier V meters and the Tier E raster guard (revision 8 called this
  the zero-diff check; the guard was WITHDRAWN in revision 15 after WP-0.2f,
  and this code now serves the Tier V meters only);
  `report.html`; the pypdf merge calibration: extract page 1 and page n of
  an existing 010 reader.pdf as single-page cover stand-ins (the function
  demands single-page A5 covers), run `replace_outer_pages` with an
  explicit output path (omitted, it overwrites its input), and compare
  inner pages before/after at display-list level; found rewrite noise
  becomes `normalization.merge_rewrite_rules`.
- Verify: raster self-test zero-diff on the same PDF twice; merge
  calibration report in evidence with measured full-run wall-clock.

**WP-0.2d fault suite and calibration**
- Owns: `mag/tests/parity_faults*`, `meta/verification/parity.yaml`
  (expected-detections matrix and `critic_metric_tolerances:` keys only;
  `raster_bound` moved to WP-0.2f in revision 9, and WP-0.2f was WITHDRAWN
  in revision 39, so the key is authored by nobody and carries only this
  WP's blocked measurement).
- Target: seeded faults built by rendering scratch copies of staged
  inputs/CSS (tracked files untouched): swapped words, a line moved
  0.05 pt and 0.3 pt, a figure shifted one page, a 30 px recolor, body ink
  flipped to pure black, a dropped link annotation, a MediaBox off by
  0.5 pt. Each fault flagged by at least its intended check per the
  expected-detections matrix, which the test asserts exactly; no fault
  passes Tier E. One calibration, a derivation rather than a choice:
  `critic_metric_tolerances:` = exact equality for
  integer metrics, and for float metrics a fixed relative epsilon of 1e-6
  (evaluation-order slack between the Python and Rust float pipelines),
  with near-threshold fixtures carrying any metric that sits within 10x
  that epsilon of a critic decision threshold.
- Verify: the suite runs under `cargo test`.
- Reworked and accepted 2026-09-14 (`67afdcd`, verified `b6f9dbc`) after a
  verifier rejection: `failing_clauses` tested the Tier V meters with
  `v["v1"] == false` while the comparator emits `"pass"`/`"fail"` strings,
  so both branches were dead, no V-meter result could ever be observed, and
  two matrix rows were wrong. A clause family the observer cannot see is
  the same defect class as the vacuous opener-fit comparison WP-0.0c fixes:
  assert the observation is possible before asserting its value.
- STILL OWED, after WP-0.2e and WP-0.2f land: re-derive the matrix under
  the new display list and the selected rasterizer (both change what the
  faults trip), and add one fault per blind spot WP-0.2e closes, a mirrored
  image and a mirrored text run. Note `line_moved_03` sits at differing
  fraction 0.000879 against V2's 0.001, inside it by 12%, so that row is
  fixture-fragile and a rasterizer change may well move it.

### WP-0.2e close the display-list blind spots (comparator WP)

- Owns: `mag/src/parity/streams.rs`, `mag/src/parity/display.rs`,
  `meta/verification/parity.yaml` (deletion of the unowned
  `color_space_map` key only).
- Target: the canonical display list records the full text matrix on every
  text show, the full placement matrix on every image, and the GLYPH COUNT
  per show, in place of a start point, a bounding box and a decoded string
  alone. A mirrored, rotated or skewed glyph run or image then differs, and
  so does a ligature standing in for its components; today none of them
  does. Record the count only, never raw CID codes: the engines subset and
  assign codes independently, so codes would false-fail on every page. The
  count is already computed in the decode loop, is exact, and has no
  rounding to false-fail on. Delete `normalization.color_space_map`: colour
  normalization is computed and every unmapped colour operator already
  fails loud, so the key is a promise nothing keeps.
- Verify: 010 A-vs-A and A-vs-B stay Tier E equal with byte-deterministic
  verdicts (these additions can only false-fail if an engine genuinely
  mirrors or re-shapes something, and the oracle leg does neither against
  itself); four new fixtures each FAIL: an image placed with a
  negative-determinant matrix and identical pixels, a text run placed with a
  mirrored text matrix and identical string and origin, a text run rotated
  180 degrees about its origin, and a ligature case (same string, same
  origin, same total advance, different glyph sequence). `cargo test`,
  `fmt`, `clippy -D warnings` green.

### WP-0.2f rasterizer selection and the raster bound (WITHDRAWN)

- **WITHDRAWN AND SUPERSEDED (revision 39). Do not execute this section.**
  It is kept rather than deleted because its MEASUREMENTS are valuable and
  must not be repeated, and because a deleted WP leaves a dangling id in
  eleven other places. The replacement is the per-glyph clause in Tier E
  and **WP-0.2i**; read those instead.
- Why the whole section goes, selection included. Revision 15 withdrew the
  Tier E raster guard after this WP measured that no rasterizer can carry
  it: `mutool draw` 1.26.4 at 8x supersampling does not FreeType-grid-fit
  outlines, which was the hope, but it ROUNDS TEXT-OBJECT ORIGINS to the
  device grid, so it is as sensitive to a sub-pixel origin shift (242) as
  poppler (241); floor 30.125 against ceiling 30.125 is a ratio of 1.00;
  the linear-matrix term brackets at 151.641 above every ceiling; and
  perturbing origins within 0.001 pt still reaches 122, so no finer
  quantum rescues it. Full record:
  `meta/verification/evidence/WP-0.2f.md`, commit 932f90e.
  With the guard gone, the SELECTION half dies too, which revision 15 left
  implicit and this revision states: rasters survive only as Tier V
  meters, meters GATE NOTHING, and `pdftoppm -r 300` is already
  implemented (WP-0.2c) and pinned (WP-0.1). There is no requirement a
  different rasterizer would satisfy, so there is nothing left to select.
- Consequences, so nothing dangles:
  - `tiers.e.raster_bound` is NOT authored by anyone. It carries no
    `value`, and the key exists in `parity.yaml` only as WP-0.2d's blocked
    measurement record.
  - `mupdf` 1.26.4 is installed on the development machine and
    deliberately NOT pinned in `tools:`. Nothing in the pipeline depends
    on it; do not add it.
  - The reachability-floor and ceiling fixtures specified here are
    superseded by WP-0.2i's per-glyph floor, which inherits this WP's
    `drift` fixture (69,071 glyphs, 1,503 shows, display-list equal) and
    its recommendation that the re-derivation use a CTM-COMPOSING
    perturbation through the Rust tracer rather than operand perturbation
    through pypdf.
- **Why this section survived three revisions of prose that contradicted
  it**, recorded because it is rule 9's propagation failure in a second
  medium: revision 15 rewrote the ARGUMENT and left the SPECIFICATION
  beside it, because nobody re-reads a section they have already decided
  about. An agent finds its own WP section and executes that, not the
  changelog, so a withdrawn WP must say so IN ITS OWN SECTION. When a
  decision withdraws work, grep for the WP id and check every hit, exactly
  as when correcting an enumeration you grep for its count.
### WP-0.2g compared cardinality and page rotation (comparator WP)

- Owns: `mag/src/parity/geometry.rs`, `mag/src/parity/display.rs`,
  `mag/src/parity.rs` (verdict fields), `meta/verification/parity.yaml`
  (the boxes clause key). Serial after WP-0.2e and WP-0.2f (rule 1c).
- Why cardinality: on 010, `/Outlines` is empty and `pdfinfo` reports no
  Title and no Lang, so two thirds of the Tier S navigation clause compare
  empty against empty and report `pass` having checked nothing. The link
  half is real (84 `/Link` annotations across 21 `/Annots` pages) and the
  WP-0.2b fixtures prove the instrument works, so this is reporting
  honesty, not a hole. The plan's Risks section already states the
  principle and revision 9 assigned it to nobody, which is how a principle
  becomes decoration.
- Target: every clause that compares a collection records the CARDINALITY
  it compared, and the verdict reports it. A clause that compared zero
  items reports `pass (0 compared)`, never a bare `pass`. This changes no
  pass/fail semantics: an empty collection on both sides is still equal.
  Additionally, compare `/Rotate` per page alongside MediaBox, CropBox and
  TrimBox: it is print-visible and one key wide, and a 180 degree
  difference leaves page dimensions equal. **Narrowed by measurement
  (revision 44, rule 11): "nothing else would catch it" was too broad.**
  WP-0.2g built the `/Rotate 180` fixture and found that on a BODY-TEXT
  page the `text` clause and Tier G catch the turn too, because pdftotext
  reports rotated coordinates. The clause is the ONLY one that fails on the
  BLANK inside front cover (page 2: 0 text characters, 0 images), where
  text, colour, navigation, glyph positions, display list and both raster
  meters all pass at zero delta. The narrower claim is the true one, and it
  is what makes the clause load-bearing rather than decorative: it is the
  sole guard on pages that contain nothing to compare.
- SUPERSEDED TARGET (revision 15): revision 13 asked this WP to quantize
  the text matrix's LINEAR components finely enough to stop their amplified
  positional effect, on the premise that both engines emit clean values so
  it would cost nothing. **The premise is false on the oracle leg**, and
  WP-0.2f measured it: 1,471 text matrices carry 26 distinct `trm[0]`
  values which are NOT clean font sizes, most commonly 13.333 (1,068),
  9.0664 (169), 12.7998 (55), 8.666 and 24.666 (39 each), with 10.0 and
  40.0 appearing only 12 and 9 times, because a 4/3 px-to-pt scale is
  composed into `Tm`. A WP that assumed clean values would have chosen a
  quantum that false-fails. More decisively, the effect the tightening was
  meant to remove is now observed DIRECTLY by WP-0.2i's per-glyph
  device-space offsets, so the tightening buys nothing. Dropped. If a
  later WP revisits it, it must measure the Typst leg too rather than
  assume anything about it.
- Verify: 010 A-vs-A and A-vs-B unchanged in pass/fail with cardinalities
  reported and the navigation clause showing 0 outlines, 0 Title, 0 Lang
  and its link count derived from the run (rule 9: do not hard-code 84); a
  fixture with `/Rotate 180` on one side FAILS the boxes clause; verdict
  stays byte-deterministic.
- ACCEPTED (`be64415`), verified by PERTURBATION rather than code reading
  for every derivation claim. Rotation confirmed on all three legs: control
  inert; body-text page 3 fails boxes AND text AND Tier G (325.839 /
  551.325) and both raster meters at delta 241, which is why revision 15's
  "nothing else would catch it" was too broad; and on BLANK page 2 `boxes`
  is the ONLY failing clause, with `rotation_mismatches:
  [{page:2,a:0,b:180}]` and everything else passing at literally zero
  delta.
- **An observation worth keeping: a meter that gates nothing can still be
  load-bearing as a PRECONDITION check.** A max channel delta of 0 is
  itself the proof that page 2 is genuinely blank, so the Tier V meter
  earns its keep proving the fixture is what it claims even though it gates
  no verdict. The preconditions were re-measured on the fixtures themselves
  (0 characters, 0 images, identical MediaBox) rather than assumed.
- **A disclosed-unmeasurable residual was DISCHARGED once the mechanism
  arrived**, which is the `## What is and is not proven` regime paying off:
  `page_sets_refused` was flagged honestly as unmeasurable at the time, and
  the verifier measured it by copying `meta/` and seeding `baseline.json`
  to 64 zeros, whereupon `--oracle-only` prints `page sets: refused (...)`.
  It also found `raster_bound` stronger than claimed: the key-absent run's
  `verdict.json` is not merely equivalent but BYTE-IDENTICAL
  (`468eac3c32c8a4e2`) to the key-present one.
- **Scope caveat that bounds everything above, recorded because it is easy
  to over-read**: BOTH LEGS ARE WEASYPRINT, so none of this says the
  engines agree. Also unmeasured: 90 and 270 degree rotations; the
  fixture-inertness argument is cardinality-level only; and since A-vs-B is
  a second all-green pair, the digest comparison covers passing-clause
  serialization only.

### WP-0.2h the shared tracer text path (comparator WP)

- Owns: `mag/src/parity/streams.rs`, a new shared module exposing its text
  path, `mag/src/parity/display.rs` (call-site only). Serial with the other
  `mag/src/parity*` owners (rule 1c). Consumers: the comparator, and
  WP-5.3b's critic.
- Target 1, the seam: expose the TEXT path WITHOUT the navigation path.
  `display::extract` is the wrong entry point for a text consumer: it
  resolves annotations and dies on `booklet-a4.pdf` with a missing `/Names`
  key, while `streams::trace_page` reads the same file happily. A consumer
  that only wants glyphs must not fail on an outline structure it never
  asked for.
- Target 2b, INVISIBLE TEXT (`3 Tr`): 010's cover pages use invisible text
  rendering mode as well as non-embedded Helvetica, and the tracer fails
  loud on both, so the covers currently have TWO unowned reasons to break
  the gate once WP-5.4g compares them. **Decision: RECORD it, with the text
  render mode carried on the element**, rather than skipping it. Invisible
  text contributes no pixels, so it is not part of what is printed, but it
  is the selectable-text layer that usually carries the real title, and a
  difference there is a real difference in the artifact: what a reader can
  select, copy and search. Recording costs nothing, keeps the display list
  a faithful record, and compares invisible text only against invisible
  text. Tier S's extracted-text clause independently covers the same
  content, which is the right division of labour: Tier S for content, Tier
  E for rendering. Modes other than 0 and 3 stay fail-loud until something
  needs them; "fail loud forever" was never available here, since the
  covers must eventually be compared.
- Target 2, the standard-14 faces: the tracer currently cannot read 010's
  COVER PAGES at all, because Helvetica is non-embedded and carries no
  `/ToUnicode`, and those pages are not empty (page 56 holds 380 characters
  and 6 body lines). The fix is specified rather than guessed: for a
  non-embedded standard-14 face the code-to-Unicode mapping is determined
  by StandardEncoding or WinAnsiEncoding per the PDF specification. Read
  the spec, implement it, fail loud on anything outside it.
- Why this is not optional, stated so it cannot later be dropped as
  redundant: TWO consumers need it for different reasons, and neither is a
  quality improvement.
  - **WP-5.3b cannot compute an issue without it.** `cover_spread_checks`
    (render_critic.py:184) runs over `cover_wrap_plan`, the wrap carrying
    reader pages 1 and 56, which are precisely the unreadable pages. So
    `cover-booklet-page-order` is not computed DIFFERENTLY under a
    tracer-fed critic, it cannot be computed AT ALL. Hard prerequisite.
  - **Tier E acquires a gap without it.** WP-5.4g makes `reader.pdf`
    compared END TO END, which brings the cover pages into the compared
    domain. A tracer that fails loud on them is then a hole in THE GATE,
    not an inconvenience for a consumer.
- Verify: 010 A-vs-A and A-vs-B verdicts byte-identical to before (this is
  a seam and a decode addition, not a semantic change); the cover pages
  decode, with page 56's character and line counts recorded; a text
  consumer reads `booklet-a4.pdf` without touching navigation; `cargo test`,
  `fmt`, `clippy -D warnings` green.

### WP-0.2j the exact number path (comparator WP)

- Owns: the number-parsing path shared by the tracer and its consumers,
  plus `meta/verification/parity.yaml` if a record is needed. Serial with
  the other `mag/src/parity*` owners (rule 1c).
- Why: **lopdf parses every PDF real as `f32`**, and that has already
  produced a measured defect rather than a theoretical one. Edition 010's
  pages 1 and 56 carry `MediaBox 419.5276` while pages 2 to 55 carry
  `419.527559`, which an f32 cannot hold, so WP-5.2's computed scale came
  out exactly 1.0 against Python's 1.0000000151, shifting edges by about
  9e-6 pt and flipping 381 bytes at max channel delta 4. WP-5.2 recovered
  the authored decimals from the file's raw bytes and refused loudly rather
  than placing a page at reduced precision, but that recovery is per-WP and
  REFUSES on PDFs using object streams.
- Confirmed at source by WP-5.2's verifier: `lopdf::Object::Real(f32)` at
  `object.rs:42`. The concrete consequence on 010's own boxes, recomputed
  here rather than restated: `419.527559` parses to `419.5275573730469` (an
  error of 1.63e-06) and `419.5276` to `419.527587890625` (1.21e-05), two
  authored decimals landing on f32 values that differ only in the eighth
  significant figure, which is where the derived ratio then moves. Cite
  this rather than re-measuring it.
- Scope: every coordinate, matrix component and TJ adjustment the tracer
  reads is an f32 before any arithmetic, so this is beneath WP-0.2h,
  WP-0.2i, WP-5.4 and WP-5.5 alike. A SHARED exact path is the right shape;
  per-WP raw-byte recovery is how three incompatible recoveries start.
  Object streams must be handled, not refused, or the limitation is named
  and fails loud; silently reduced precision is never acceptable.
- The arithmetic this has to answer, recorded so the measurement can be
  checked rather than trusted: f32 ulp is 3.87e-5 pt at a 325 pt magnitude
  and 4.77e-5 pt at 400 pt. Against WP-0.2i's per-glyph bound of
  `k x 0.000732 pt` that is 5.3% of the bound at k=1, which is a fraction
  rather than a multiple. The sharper exposure is the SHAPE constraint: the
  monotone check compares successive differences whose expected increment
  is WP-1.6's 0.000173 pt per glyph, and 3.87e-5 pt of jitter is about 22%
  of one step, which is enough to make a monotone sequence look
  non-monotone or to mask a small compensating kern. So the honest prior is
  that this is NOT obviously negligible for the shape check even though it
  is comfortably inside the magnitude bound.
- **The hazard is scope-dependent and can be DISCHARGED by enumeration
  rather than fixed everywhere**, which WP-5.5b demonstrated as the clean
  counter-case to WP-5.2's: every parsed PDF number in the preflight path
  flows only into `near(size, expected, 0.75)`, with margins 17,595x to
  28,550x the tolerance, so f32 provably cannot reach its outputs. A
  consumer that enumerates where its parsed numbers go, and shows the
  reachable error is orders below any threshold they meet, needs no exact
  path. Record the enumeration; do not assume the hazard applies
  everywhere, and do not assume it applies nowhere.
- **A SECOND parser loses bits the same way, and it sits under the oracle
  comparisons rather than under the PDF reads.** `serde_json`'s default
  float parser is not round-trip exact: `97.71500651041667` gives
  `0x40586dc2aaaaaaab` through `str::parse` and `0x40586dc2aaaaaaac`
  through `Value::as_f64`, one ulp apart, verified by the planner rather
  than taken on report. `mag/tests/critic_metrics.rs:30` reads WP-5.3a's
  metrics through `as_f64()`, so that test's "exact equality" is exact only
  up to that parser. No measured disagreement exists, so this is NOT a
  defect and needs no fix: what needs fixing is the WORD, since "exact" is
  claiming more than the mechanism delivers. Any WP whose oracle is a JSON
  float says which of the two it means.
  **WP-5.3b-ii's handling is the pattern to copy**: it carries `rgb_mae` as
  TEXT, and commits a test asserting that every float in both oracles
  survives the round trip AND **that the known-bad literal still diverges**.
  The second clause is rule 10 applied to a GUARD instead of to evidence,
  and it is what keeps the guard from going vacuous if the parser is ever
  fixed underneath it. A guard that can only pass is worth naming as a
  general requirement: **a guard states what would make it fail, and
  commits a case that does.**
- Verify: the 010 MediaBox case reproduces exactly (authored decimals
  recovered, scale 1.0000000151 rather than 1.0); a PDF using object
  streams either parses or fails loud by name; WP-0.2i's per-glyph verdicts
  are byte-identical before and after, or the differences are enumerated
  with causes. The WP-0.2i verifier's answer on the f32 question lands in
  this WP's evidence either way: "checked, negligible, here are the
  numbers" is as valuable as a defect, and rule 11 applies, so the
  mechanism is measured rather than asserted.

### WP-0.2k seed the baseline and make the ratchet operative (comparator WP)

- Owns: `mag/src/parity.rs`, `meta/verification/baseline.json` (seeding and
  the per-page entries, the second WP besides WP-0.2a licensed to write it
  under rule 1). Serial with the other `mag/src/parity*` owners (rule 1c).
- Why: Phase 3's verification is "`mag parity 010` green against
  `baseline.json` (no page regresses)", and none of that exists. Measured
  rather than assumed (revision 40): `baseline.json` carries zero page
  entries and a null `staged_input_digest`, so `staleness()` returns
  `"unseeded"` for every run and guards nothing; the refusal fires only
  under `--set`, so a bare run on a moved corpus records staleness and
  CONTINUES; and no per-page comparison against a recorded tier exists in
  the comparator at all. The plan has been describing a ratchet it never
  built, and the human content-final gate was standing in front of that
  absence rather than in front of a risk only Fran could retire.
- Target 1: SEED `staged_input_digest` from a fresh oracle run, so
  `staleness()` can return `fresh` or `stale` rather than `unseeded`.
- Target 2: make the refusal UNCONDITIONAL. A stale digest refuses the run,
  not merely page-set scoring under `--set`. A comparator that continues on
  a corpus it cannot vouch for is the vacuity class rule 10 names.
- Target 3: implement the per-page ratchet the Phase 3 preamble and WP-3.0g
  assume: record per page the best tier achieved and which Tier S clauses
  pass, refuse to run when a working-tree entry is LOWER than the committed
  one (the rule-1 check `git show <base>:...` already specifies), and let
  only a verifier raise.
- Target 4 (revision 44): the shared-`out_dir` hazard and the cardinality
  sweep. `out_dir` is hard-coded to `output/parity/<edition>` with no
  override, and WP-0.2g OBSERVED two agents' runs writing the same
  `verdict.json` concurrently; prove the fix by running two invocations
  CONCURRENTLY, not by reading the code, since the hazard was found by
  observation. Extend cardinality reporting to every Tier S collection
  clause per rule 10a. And fix `mag/src/parity/raster.rs:106`, which still
  reads `not_evaluated (WP-0.2d raster_bound derivation)`, naming a
  derivation that will never happen now the guard is withdrawn: the same
  class as the WP-0.2f section revision 39 corrected, living in code this
  time rather than in the plan.
- **Scope note, because this WP has now accreted four targets** (seed the
  digest, unconditional refusal, the ratchet, and the above): they are
  bundled because rule 1c serialises `mag/src/parity.rs` owners, so a
  separate WP would queue behind this one and gain nothing. Build in LANDED
  INCREMENTS rather than one pass, as WP-5.5a was told, so a late blocker
  in one target does not strand the other three.
- Verify: with the digest seeded, a deliberately altered staged input makes
  a bare `mag parity 010` FAIL rather than report; an unaltered run passes
  and writes a byte-deterministic verdict; a hand-lowered baseline entry is
  refused; a raise applied by a verifier is accepted. `cargo test`, `fmt`,
  `clippy -D warnings` green.

### WP-0.2i per-glyph positions (comparator WP)

- Owns: `mag/src/parity/streams.rs`, `mag/src/parity/display.rs`,
  `meta/verification/parity.yaml` (the per-glyph bound and its derivation
  record). Serial with the other `mag/src/parity*` owners (rule 1c).
- Why: WP-0.2f proved the raster guard cannot bound what the display list
  cannot see, at any resolution, because every rasterizer snaps text
  origins. The response is to stop asking pixels and make the display list
  finer. This WP is the gate's third leg, replacing the raster clause.
- Target 1, per-glyph positions: record the quantized device-space offset
  of every glyph from its show origin, and compare the sequences under the
  mechanism-derived bound and the shape constraint Tier E states. Derive
  the floor with a CTM-composing perturbation THROUGH THE RUST TRACER, per
  WP-0.2f's recommendation; perturbing raw operands through pypdf cannot
  produce display-list-equal fixtures. WP-0.2f's `drift` fixture (69,071
  glyphs, 1,503 shows, display-list equal, reproducing WP-1.6's 0.000173 pt
  per glyph) already exists and is the floor fixture; the ceiling fixtures
  are compensating kerns at 0.02 pt and below.
- Target 2, glyph identity: map character codes to GIDs through the SHARED
  vendored face and compare those, closing the equal-count equal-advance
  substitution that the glyph count cannot see. Raw CID codes remain
  forbidden (independent subsetting); the font-file digests are already
  proven identical, which is what makes the GID comparable.
- Target 3, fail loud instead of silently painting: an actual
  optional-content membership (`BDC` with an OC property) and an annotation
  carrying an appearance stream both become fail-loud stops rather than
  unexamined content.
- Verify: 010 A-vs-A and A-vs-B stay Tier E equal with byte-deterministic
  verdicts; the floor and ceiling measurements are recorded with their
  ratio and the 2x margin met, or `Status: blocked` and a plan revision;
  fixtures that must FAIL: a compensating kern of 0.02 pt (shape), a
  linear-matrix difference below half a quantum over a full-measure line
  (0.1625 pt at body measure, against a 0.0512 pt bound at 70 glyphs), an
  equal-advance glyph substitution, an OC membership, an annotation with an
  `/AP`. Record the dump size and the per-run wall-clock: the comparison is
  O(n) over roughly 69,071 glyphs and must stay far cheaper than the 9 to
  15 minutes supersampled rasterization would have cost.
- WP-3.0g's obligation to re-derive the floor from the real
  Typst-vs-WeasyPrint pair MOVES to this clause with it.
- **The commensurability law is `ratio = n/(8k)`, not "exact sixteenths"**
  (revision 42), with n the number of quanta and k the worst offender's
  glyph index; sixteenths is only the k=2 case. Three counterexamples
  killed the narrower claim: `advstep` and `advmid` both at
  0.640625 = 41/64, and a bump family at 1/80. This STRENGTHENS the
  commensurability finding rather than retreating from it, since a law
  covering every observation is worth more than one covering some, and any
  argument that cited "sixteenths" for the gate's tightness should be
  re-read against `n/(8k)` (rule 9: a corrected figure propagates).
- **Plan premise FALSIFIED under rule 11**: the plan assumed pypdf
  perturbation cannot produce display-list-equal fixtures, which is why the
  CTM-composing recommendation took the shape it did. The verifier measured
  `display_list` = PASS on the drift fixtures, so pypdf perturbation
  demonstrably CAN produce them. The CTM-composing recommendation inherited
  from revision 39 is therefore substantively DISCHARGED; the rework names
  it as such. Fourth plan claim retired by remove-the-cause-and-measure.
- **FOURTH cross-spike count disagreement**: the plan says 69,071 glyphs and
  1,503 shows, the floor measures 68,800 and 1,488. Reconcile it or report
  a real divergence with a named cause.
  **Hypothesis, offered as a hypothesis under rule 11 and not as an
  answer**: the differences are 15 shows and 271 glyphs, and the plan
  already carries 1,488 shows independently from WP-0.2b over the 54-page
  INTERIOR domain, in three separate places. 1,503 and 69,071 may therefore
  count all 56 pages, covers included, where the floor counts the interior
  domain. The covers carry invisible `3 Tr` text on both faces (WP-5.4:
  title, deck and back-cover copy), for which 15 shows and 271 glyphs is a
  plausible size. One measurement settles it: count the two cover pages.

### WP-1.1 shaping parity

- Target: for the vendored faces, rustybuzz (Typst) and Pango/HarfBuzz
  (WeasyPrint) produce cumulative line advances agreeing within 0.01 pt on
  every line of edition 010, ligature and kerning cases included.
- Work: dump every (font, size, text) line WeasyPrint lays out for 010 via
  uncommitted adapter instrumentation (the adapter already walks text boxes
  with style access); shape the same strings with rustybuzz; compare.
- Verify: delta distribution, worst offenders, go/no-go in evidence.
  Fallback on no-go: align OpenType feature flags; `awaiting-fran` only if
  alignment fails.
- RESULT (done, decision recorded in revision 9): **go.** 1488/1488 lines
  have identical glyph-id sequences with no font fallback; per-glyph
  advances agree within 1 Pango unit (0.00073 pt); cumulative advance is
  within 0.01 pt on 1484/1488, the four misses reaching 0.0174 pt. The
  misses are Pango's 1/1024 px rounding accumulating with glyph count, not
  shaper disagreement: the error grows with line length (0-9 glyphs:
  0.0013 pt; 60-69: 0.0099 pt) and round rustybuzz the same way and they
  agree to one unit. Feature alignment WAS required and worked: Pango
  suppresses ligatures under letter-spacing, so `liga`/`clig` must be off
  wherever tracking is set (86 letter-spaced runs then match glyph for
  glyph). The residual reaches no Tier E coordinate directly (the CSS has
  no `justify` and no `text-align: center`; the only width-dependent
  positions are `space-between` label rows, worst residual 0.0070 pt,
  inside the quantum), and the raster bound accounts for it. Note the shape
  of the residual precisely, because WP-1.2 read it wrong: the four misses
  are LETTER-SPACED display headlines; at normal spacing the worst line is
  0.009897 pt and none crosses the quantum. So this residual does not
  explain WP-1.2's body-text break miss, and WP-1.6 exists to find what
  does. **Configuration, which must travel with these numbers (rule 9):
  hyphenation ON, 1402 lines, rustybuzz advances compared per laid-out
  line (1488 lines, 1488 runs, 1:1).** They are not comparable to WP-1.6's
  899-line hyphenation-off population.

### WP-1.2 line-break parity and the ragged-right confirmation

- Target: confirm ragged-right (no `text-align: justify` in the CSS); then,
  with identical measure, font, size, leading, greedy breaking, and
  hyphenation off both sides (uncommitted switches), Typst
  (`linebreaks: "simple"`) reproduces WeasyPrint's break points on every
  paragraph of edition 010.
- Verify: break-point match rate with every miss classified `fixable`
  (naming the mechanism and the WP that fixes it) or `structural`; any
  `structural` miss ends `awaiting-fran`. Forced breaks are NOT acceptable
  in the final engine.
- RESULT (done, decision recorded in revision 9): ragged-right confirmed as
  a selector fact (the stylesheet's one `text-align` is inside the
  `@bottom-right` folio box). **148/149 paragraphs, 963/968 lines, zero
  structural misses.** The single miss is `fixable` and owned: Typst
  measures a 67-character line at 325.01 pt against a 325 pt column and
  breaks a word early, cascading through five lines; it reproduces
  WeasyPrint's breaks at 325.01 pt and above but not at 325.005 pt. It is
  NOT a breaking-algorithm difference: `linebreaks: "simple"` agrees
  everywhere else. **The cause is not yet established.** WP-1.2 attributed
  it to WP-1.1's advance residual, and the Phase 1 audit showed that does
  not follow: WP-1.1's normal-spacing lines top out at 0.009897 pt with
  ZERO over 0.01 pt, and its four larger misses are letter-spaced display
  headlines, not body text. The two spikes measured different corpora
  (hyphens on vs off) and different quantities (raw rustybuzz-vs-Pango
  advances vs Typst's own `measure()`), so this is not a formal
  contradiction, but the 67-character body line needs a disagreement of at
  least 0.0100 pt that WP-1.1's numbers do not show. WP-1.6 locates it.
- **Revision 9 changes this clause.** Revision 8 read "100% or a recorded
  Fran decision; nothing in between enters Phase 2", which would block
  Phase 2 on a measurement Phase 3 has to make anyway. The spike's purpose
  was feasibility, and zero structural misses settles that. Phase 2
  proceeds; the miss becomes a named obligation of **WP-1.6 then WP-3.1**,
  where Tier E must find those five lines equal. This relocates the check,
  it does not relax it: an unequal line still fails the gate, and if WP-3.1
  cannot drive it to equality that is `blocked` and another revision.
  WP-1.6 must report before WP-3.1 scores `page_sets.body`, so that WP
  starts knowing which of three mechanisms it is fixing rather than
  guessing.
- Carried into Phase 2 (WP-2.2a's mapping table must hold all of these):
  body paragraphs run at THREE measures, 325 pt, 311 pt (24 blocks) and
  312.1614 pt (one); inline-code paragraphs carry per-run SIZE (8.2 pt
  against 10 pt body) as well as per-run family. Six 6.8 pt `span` blocks
  were outside this spike's target and no spike measures their breaks; they
  are not exempt, Tier E scores them in Phase 3 like every other page.

### WP-1.3 hyphenation measurement and recommendation

- Target: a numbers-backed recommendation between (a) porting Pyphen's en
  dictionary lookup to Rust and injecting soft hyphens into both engines'
  input, and (b) disabling hyphenation in both engines for parity,
  re-enabling native hyphenation post-flip via WP-4.3.
- Work: measure 010's hyphenation incidence (the adapter reports hyphen
  ladders); render with hyphenation off (uncommitted CSS switch); quantify:
  page-count changes per article, page-cap violations, changed line breaks.
- Verify: those three numbers in evidence. "Negligible" = zero page-count
  changes and zero cap violations. Ends `awaiting-fran`.
- RESULT (done, decision recorded in revision 9): **option (b).** Incidence
  is 126 soft-hyphen breaks across 81 of 155 prose blocks, reclaiming 9
  lines and producing 3 hyphen ladders. Disabling it changes **zero** page
  counts per article, leaves the edition at 56 pages, and introduces
  **zero** cap violations (the one violation, a 13-page verbatim article
  against a cap of 10, exists in both renders and predates the switch). By
  the plan's own definition that is negligible, so option (a) would put a
  Rust port of Pyphen's Liang patterns on the critical path for 126 breaks
  and then discard it at the flip. The honest cost of (b): Tier E equality
  is proven against a configuration that does not ship, which is precisely
  what WP-4.3 exists to measure, and WP-4.3 is therefore MANDATORY.

### WP-1.4 Typst measurement interface and version pin

- Target: proof the typst crates expose per-element positions sufficient
  for `RenderLayout` (page and box of every line, figure, heading,
  ornament, sub-0.1 pt) from Rust without parsing the PDF, plus the exact
  crate versions to pin.
- Verify: evidence with the API path (frame walk vs `query`), versions,
  MSRV. WP-2.0a writes the pin into Cargo.toml and parity.yaml from this
  evidence.

### WP-1.6 locate the 0.01 pt measure disagreement

- Owns: evidence only (Phase 1 preamble binds: uncommitted spike code, own
  worktree, `git status` clean at WP end).
- Why: WP-1.2's single break miss needs Typst to measure a 67-character
  body line at least 0.0100 pt wider than WeasyPrint does, and WP-1.1's
  shaping numbers do not account for it (0.009897 pt worst case at normal
  spacing, zero lines over the quantum). Something between raw glyph
  advances and Typst's laid-out line width is adding the difference, and
  nobody has measured which thing. Assigning the miss to WP-1.1 would gate
  on work WP-1.1 says is already done, and the miss would then walk into
  WP-3.1 unexplained.
- Target: for that exact line, and for a sample of the widest body lines,
  decompose the width disagreement into its three candidate sources and say
  which one carries the 0.01 pt:
  1. **rustybuzz vs Pango advances** for the same string, font and size
     (WP-1.1's instrument, re-run on THIS line rather than its corpus);
  2. **Typst's `measure()`** against the sum of those advances, which is
     where per-line rounding, tracking or space handling could enter;
  3. **the column width itself**, 325 pt as transcribed against what
     WeasyPrint's box model actually offers the text (the content box after
     padding and border rounding).
  State the measured contribution of each in pt.
- Verify: the three contributions sum to the observed disagreement within
  0.001 pt, and the WP names the owning mechanism and the WP that fixes it.
  If the dominant term is (1), WP-1.1's go recommendation needs revisiting
  and that is `awaiting-fran`; if (2) or (3), the fix belongs to WP-2.2a's
  template transcription and WP-3.1 scores it.
- Must report before WP-3.1 scores `page_sets.body`.
- RESULT (done, `awaiting-fran`, decision recorded here): candidate (1)
  carries **100%** of it. rustybuzz vs Pango advances contribute
  0.0109765625 pt; Typst's `measure()` contributes 0.0000000000 pt (at upem
  1000 and 10 pt, advances are exact multiples of 0.01 pt); the column
  transcription contributes 0.0000000000 pt (WeasyPrint's content width is
  433.3333333333333 px, exactly 325.0 pt, so the template's 325 pt is
  right); residual against the observed disagreement 0.000000 pt.
  Mechanism, confirmed in WeasyPrint's source: `line_size()` returns
  `logical_extents.width * FROM_UNITS` with `FROM_UNITS = 1/1024` and
  `PangoRectangle.width` an INTEGER, so WeasyPrint breaks on an integer
  count of 1/1024 px while Typst sums exact font units. All 899 measured
  line widths are integer Pango-unit counts. Exactly ONE line of 899 lands
  in the window where Typst overflows while Pango fits, and it is block
  135: an independent instrument on a fresh render predicting the very line
  WP-1.2 found.
- This does NOT overturn WP-1.1, but it does correct what its target
  sentence claimed. WP-1.1's shaping verdict stands (glyph ids 1488/1488,
  per-glyph advances within one Pango unit), and its "cumulative line
  advances within 0.01 pt" is not a per-line guarantee of the quantity that
  decides breaking. WP-1.1's own 8-unit figure (max summed per-glyph
  difference) supports that better than anything else in either spike.
  WP-1.1's stated fallback, aligning OpenType features, cannot fix this:
  the features already agree.
- **Why the two numbers differ, corrected.** WP-1.6 explained the gap
  between its 0.017432 pt and WP-1.1's 0.009897 pt as rustybuzz being
  already rounded onto Pango's grid and measured per run; the WP-1.5/1.6
  verifier showed BOTH halves fail. Per-run cannot explain anything:
  WP-1.1 records 1488 laid-out lines and 1488 runs, an explicit 1:1. And
  the rounding half points the wrong way: 0.009897 pt is 13.5 Pango units,
  which EXCEEDS WP-1.1's own 8-unit max, so that residual looks like the
  UNQUANTIZED quantity, the same one WP-1.6 measures. The likely real
  cause is an uncontrolled variable neither spike connects: **WP-1.1
  measured with hyphenation ON (1402 lines), WP-1.6 with it OFF (899
  lines)**, and since drift accumulates per glyph, the two sampled
  different line populations. Both numbers are correct; they are not
  measurements of the same thing, and the plan must never again quote one
  inside the other's reasoning without its configuration (rule 9).
- DECISION: take the measure-widening route, and make it derived rather
  than tuned. Quantizing Typst's advances onto the 1/1024 px grid is the
  other option and is out of reach: it is engine-internal, unreachable from
  a template, and would mean forking pinned crates. So WP-2.2a sets the
  body column slightly wider than 325 pt, and **WP-1.7 measures the safe
  interval first**. The lower bound is measured (325.010000 pt); the upper
  bound is not, and without it any chosen value is a tuned constant that
  could silently flip a different line. Do not let a number reach WP-2.2a
  by guess.
- Post-flip, this compensation exists only to match an engine that will no
  longer exist. Returning the body column to exactly 325 pt is a deliberate
  design change with its own before/after comparison, and belongs with
  WP-4.3's typography changes rather than being carried forever.

### WP-1.7 the safe body-measure interval

- Owns: evidence only (Phase 1 preamble binds).
- Why: WP-1.6 fixed the mechanism and the lower bound but not the upper,
  and a column width picked without the upper bound can reproduce block
  135's break while breaking a line nobody looked at.
- Target: over every body line of 010, compute the interval of column
  widths that reproduces WeasyPrint's break set EXACTLY: the lower bound is
  the widest line that must still fit (325.010000 pt from WP-1.6), the
  upper bound is the narrowest width at which some line would pull its next
  word up. Report the interval and its midpoint.
- Verify: rendering the Typst leg at the midpoint reproduces WeasyPrint's
  breaks on 899/899 body lines. An EMPTY interval is `Status: blocked` and
  a plan revision: it would mean no single column width satisfies both
  engines, and the fix would have to move to the engine.
- Feeds WP-2.2a's mapping table, which cites this WP for the number.
- RESULT (done, accepted), with two corrections its verifier required.
  The safe interval as MEASURED is `[+0.010, +0.039]` pt: the upper bound
  of `+0.040` was never actually rendered, so the exclusivity at that end
  is model-derived rather than observed, and the plan must not quote a
  closed interval to `+0.040` as measured. **Two decimals suffice for
  WP-2.2a**: both 325.02 and 325.03 sit inside the measured interval, so
  the three-decimal figure in the evidence is unnecessary precision.
- OBLIGATION carried to WP-3.1 (rule 9, third instance): WP-1.7's harness
  reports 147/149 paragraphs and 962/968 lines at the unwidened measure
  where WP-1.2 reports 148/149 and 963/968 for what both describe as the
  same 149-block, 968-line population. One extra divergent block and one
  extra differing line, neither named nor explained. It blocks nothing
  (the interval is derived from `measure()` values independently of the
  harness, and the recommended constant gives 149/149), but it is the
  THIRD unreconciled cross-spike number in this execution, so it does not
  get to sit unexplained. WP-3.1 scores body text at Tier E and will
  surface any real discrepancy; start from WP-1.2's own record of
  improving 147/149 to 148/149 once styled runs were preserved, which is
  the likely difference.

### WP-1.8 reconcile the third cross-spike line count

- Owns: evidence only (Phase 1 preamble binds). Runnable NOW; depends on
  nothing and blocks nothing, which is why revision 40 moved it out of
  WP-3.1.
- Why: WP-1.7's harness reports 147/149 paragraphs and 962/968 lines at the
  unwidened measure where WP-1.2 reports 148/149 and 963/968, for what both
  describe as the same 149-block, 968-line population. One extra divergent
  block and one extra differing line, neither named nor explained. This is
  the THIRD cross-spike count disagreement in this execution, after
  WP-1.2-versus-WP-1.1 and the ten-versus-eleven issue sites, and rule 9
  now exists because of the first two.
- Target: name the cause with a measurement. The standing hypothesis, which
  rule 11 makes a HYPOTHESIS until tested rather than an answer: WP-1.7's
  harness may lack the styled-run preservation that took WP-1.2 from
  147/149 to 148/149, which WP-1.2 records having added. Test it by
  re-running one harness with the other's treatment and seeing whether the
  count moves; if it does not, the populations differ some other way and
  the difference is real.
- Verify: the two counts reconcile with a stated cause, or the residual
  difference is reported as a genuine divergence with its page and block
  named. Either outcome carries its configuration (rule 9).
- **A single sweep of `WP-1.2.md` is owed, because the FILE is the common
  factor rather than the rule.** Three of the four count-beside-enumeration
  slips in this execution live in that one file, the newest being its 6
  excluded span blocks recorded as "34 lines" where the enumeration carries
  **8**. That one changes no compared population, so it is an erratum
  rather than a defect, but a file with three instances should be read once
  in full rather than corrected a slip at a time.
- RESULT (done, `fc1b954` + `da83e2b`), and the HYPOTHESIS IS DEAD TWICE
  OVER. The plan supposed WP-1.7's harness lacked WP-1.2's styled-run
  preservation. In fact **the two harnesses are the SAME PROGRAM**:
  extracted from both evidence files and run on a byte-identical input dump
  (sha256 `e4ab672c...`, the digest both spikes record), they produce
  identical numbers, 147/149 paragraphs and 962/968 lines with misses
  {block 4, block 135}, and **neither produces 148/149**. The disagreement
  was never between the spikes; it is between WP-1.2's RECORDED HARNESS and
  WP-1.2's OWN HEADLINE TABLE. Then the removal test: stripping styled-run
  preservation leaves the paragraph count at 147/149, unmoved. It is not
  inert (lines 962 to 960, misses {4,135} to {39,135}); it simply cannot
  move that count either way. Both extremes were run per rule 10 and both
  giving 147 was reported as the RESULT rather than read as agreement,
  which is revision 38's diagnostic used exactly as intended.
- CAUSE, named by measurement: the comparison's whitespace normalization,
  one line BOTH harnesses share.
  `" ".join(s.replace("\xa0", " ").split())` collapses RUNS of whitespace
  but cannot remove an INSERTED space. Changing it to `"".join(s.split())`
  and nothing else moves both harnesses to **148/149 and 963/968**, which
  is WP-1.2's headline exactly; the effect appears when the treatment is
  added and returns when removed, on both harnesses.
  The extra member is named: block **4**, reader page **6**, 325.0000 pt
  measure, line index **5**, a `pdftotext -bbox-layout` word split at a
  font change (`verification)` in Geist Mono 8.2 pt followed by Source
  Serif 10 pt, first differing character index 13, exactly the run
  boundary, equal once whitespace is removed). Not an engine divergence.
  The genuine residual is unchanged: block **135**, reader page **47**,
  five displaced lines, WP-1.2's known 325.01-against-325 pt miss. And the
  discrimination check passes, so whitespace removal is not a blanket pass:
  it still fails block 135 at +0.000 and block 137 (page 48) at +0.045.
- APPLIED (verification `c1253d8` ACCEPTED, hold released). **WP-1.7's
  delta table mixes both normalizations, and the error is FORCED rather
  than plausible: no single normalization reproduces all six recorded
  rows**, three matching collapse and not removal, three the reverse. There
  is no reading under which that table is internally consistent. Its
  "968/968 at the midpoint" therefore holds only whitespace-insensitively
  and is 967/968 under its own recorded harness.
  **The +0.025000 pt recommendation SURVIVES, and the argument is
  demonstrated rather than asserted**: the interval comes from `measure()`
  in WP-1.7's section 2, not from the harness at all. Under BOTH
  normalizations block 135 fails at +0.000 and +0.005 only and block 137 at
  +0.045 only, while block 4 is a miss at ALL SIX deltas under collapse and
  at NONE under removal, so it can move neither bound. The measured-safe
  set `{+0.010, +0.025, +0.039}` is unchanged, and WP-1.7's separate
  "698/698 unstyled lines" claim is untouched because block 4 is
  `styled=True`.
- **WP-1.2's headline is the artifact-corrected count, and its own file
  says so twice.** Its `## Verdicts` section calls the misses file "the two
  recorded misses" while its headline table says "misses: 1", and
  149-1=148 with 968-5=963 is exactly the hand-discount of block 4. The
  recorded harness never produced 148/149.

### WP-1.9 show what whitespace removal can MASK

- Owns: evidence only (Phase 1 preamble binds). Runnable now.
- Why: whitespace removal (`"".join(s.split())`) is now the SANCTIONED
  comparison for line-break work, adopted because it reproduces WP-1.2's
  headline and because it still fails blocks 135 and 137, which shows it is
  not a blanket pass. Nobody has shown what it CAN hide. WP-1.8's
  verification listed this as its one non-discrimination worth
  commissioning, and it is the straddle rule applied to a NORMALIZATION
  rather than to a threshold: a treatment adopted because it discriminates
  on the cases at hand is not thereby shown to discriminate on the cases it
  was designed to ignore.
- Target: build a fixture in which whitespace removal MASKS a genuine
  divergence, or demonstrate that it cannot. A genuine divergence here
  means one that changes what a reader sees: a real inter-word space
  gained or lost, as against the `pdftotext -bbox-layout` word split at a
  font change that motivated the treatment.
- Verify: either the masking fixture exists and is named, with the
  consequence stated for WP-3.1's scoring, or the argument that no such
  fixture can exist is given in terms of what the treatment removes. A
  third outcome is legitimate and must be said plainly: that the question
  cannot be settled without the engine, in which case it moves to WP-3.1.

### WP-1.5 apply the hyphenation decision (sanctioned oracle change)

- Owns: `src/magazine/assets/weasyprint-a5.css`,
  `meta/verification/parity.yaml` (decision record), evidence.
- Decision, recorded in revision 9: **option (b)**, hyphenation off in both
  engines for parity, re-enabled natively post-flip by WP-4.3.
- Target: disable hyphenation **scoped to `:lang(en)`**, not globally. The
  stylesheet's own comment records Spanish setting about four pages longer
  than English (edition 003: en 36, es 40) with one es article sitting
  exactly on its seven-page cap, and `html lang` is already set per
  language, so the scoped switch costs one selector and keeps every
  Spanish edition rendered between here and WP-4.3 off a cap breach. Read
  the whole comment before weighting this: the same note records edition
  003 paginating IDENTICALLY with and without hyphenation in both
  languages, so the cap breach is a tail risk, not an expectation. One
  selector is cheap enough to buy anyway.
  Parity is en-only, so the scope loses nothing it needs. The Typst leg
  disables hyphenation for the same language in WP-2.2a.
- Verify: WP-0.1's double-render determinism check re-run green; an es
  render's page count is unchanged by the switch (the scoping is the point,
  so prove it rather than assume it); 010 en reproduces WP-1.3's measured
  numbers (56 pages, zero cap changes).
- Erratum (evidence only, accepted): WP-1.5's evidence gives the max run of
  consecutive hyphen-ended lines BEFORE the switch as 3; the verifier
  measured 4, the 3 having been conflated with WP-1.3's separate finding of
  3 hyphen ladders. The number that carries the claim, 2 after the switch,
  is exact and is what parity.yaml records.

## Phase 2: the Typst engine skeleton

### WP-2.0a engine dispatch

- Owns: `mag/src/main.rs` (`--engine` flag, `mod typeset;`),
  `mag/src/render.rs` (engine selection from `magazine.toml [render]
  engine` + `--engine` override; typst branch stubs to a loud "not
  implemented"), `mag/src/typeset/mod.rs` (stub), Cargo files (the five
  exact pins WP-1.4 proved: `typst`, `typst-layout`, `typst-library`,
  `typst-pdf`, `typst-syntax`, each `=0.15.1`; `typst-layout` and
  `typst-syntax` are required, `comemo` is not),
  `meta/verification/parity.yaml` (crate-pin record only).
- Target: `--engine weasyprint` output unchanged (dumps + boxes + JSONs vs
  a pre-change render); `--engine typst` fails loud; the toml key is live,
  default weasyprint.
- Verify: the before/after comparison inline in `## Commands`;
  `cargo test`.

### WP-2.0b parity render mode and page sets

- Owns: `mag/src/parity.rs`, `meta/verification/parity.yaml` (`page_sets:`
  key only).
- Target: `mag parity 010 [--run <dir>]` stages the working tree's 010
  inputs once, renders both engines from the staged copy with `--no-model
  --langs en` (both legs; the typst leg has no translation loading by
  scope, and a stray es render would break the run asymmetrically),
  compares over the interior domain against `baseline.json` with the
  staleness guard; `--set` scores one page set; the oracle-leg cache keyed
  by staged-input digest. Write the page-set RULES to parity.yaml,
  evaluated per run from the oracle leg's manifest: `body` = pages with no
  figure placements and no opener/TOC; `openers` = opener and TOC pages
  (from toc); `placement` = pages with figure/plate/ornament placements;
  `furniture` = all interior pages; `code` = pages where a staged fenced
  run's or resolved extract's first line lands (empty for 010 itself,
  which carries neither; WP-3.3 gates on its fixture instead).
- Verify: with typst stubbed, `mag parity 010` reports the typst failure
  cleanly; an oracle-only mode (`--oracle-only`: weasyprint leg vs itself)
  is Tier E green end to end.

### WP-2.1 content pipeline: staged inputs to Typst source tree

- Owns: `mag/src/typeset/content.rs`, fixtures under `mag/tests/typeset_*`,
  Cargo files.
- Depends: WP-5.1c (consumes `mag/src/model/` for the document model and
  manifest loading; owns neither a markdown parser nor edition validation).
  The refusal fixture list from WP-5.1c's matrix is copied into this brief
  verbatim when the WP is cut.
- Target: the pipeline turns 010's staged inputs (edition.yaml,
  manuscripts, extracts, figures) into a deterministic in-memory Typst
  source tree whose plain-text projection equals the oracle leg's
  normalized text (Tier S text, pre-layout).
- Work: extracts resolution with `manifest.py`'s ambiguity refusals;
  figure/caption/anchor wiring; soft-hyphen injection if WP-1.5 chose (a).
- Verify: `cargo test`: projection vs oracle text for all of 010; extract
  byte-exactness; the refusal matrix re-exercised (ambiguous marker, marker
  not found, run already verbatim in manuscript, unknown source id, figure
  path escaping the source dir).
- RESULT (done, accepted, commit `9acc797`), with the compared boundary
  RENAMED and the claim BOUNDED. Both corrections come from the verifier
  and both narrow what the headline proves:
  - The seam is **the text content of the pre-layout HTML document**, not
    "the reader-visible text before any layout exists". It includes 835 of
    68,758 characters that are never printed (`display:none` on
    `.edition-header`, nine `.source-link` URLs) and excludes the CSS
    `::before` figure and extract labels, which ARE printed. The verifier
    tested rather than argued the obvious suspicion, and the boundary makes
    the comparison HARDER, not easier: 835 extra characters both legs must
    match, and everything excluded reduces to one emitted value checked
    against Python entry by entry.
  - **The oracle is BLIND TO BLOCK STRUCTURE**: two `#doc-paragraph` calls
    and the same text merged into one project byte-identically. WP-2.1
    proves SAME TEXT IN SAME ORDER and nothing about structure. Do not cite
    it for a paragraph-level claim; structure is Tier S page boxes and
    WP-2.2b/2.2c.
  - Three of four normalization clauses are VACUOUS on this corpus (0 soft
    hyphens, 0 U+2010, NFC a no-op); only whitespace collapse acts, on
    2,134 of 70,892 characters. Rule 10a's disclosure, recorded here since
    the clause set is inherited by everything downstream.
  - The guard refuses 12 markup leaf kinds beyond the committed heading
    case; neutering `escape_markup` fails five tests loudly (rule 11
    applied to what the guard protects, not only to the guard).
  - Evidence defect, not a code defect: `content.rs:1170` labels
    `text.len()` BYTES as "characters" (69,097 should be 68,758), and
    `:1162` repeats it. One-line fix for the next holder of the file.

### WP-2.2 the reader template (three serial slices)

Preamble (binds per rule 8): each slice owns `mag/src/typeset/template.rs`,
`mag/src/typeset/**` submodules it introduces, and `mag/assets/typeset/`;
serial; each extends its evidence mapping table: every transcribed value
cites its origin (`weasyprint-a5.css` selector or `weasyprint_adapter.py`
constant). Anything found-but-not-transcribed is listed as pending, never
dropped silently.

**The CSS `::before` figure and extract labels are PRINTED and are NOT in
WP-2.1's content oracle**, so nothing upstream catches them and they are
WP-2.2a's to get right. They go in the mapping table with their selectors
like any other transcribed value. This is the general shape of the seam
WP-2.1's rename exposes: generated content is printed text that no
text-level oracle sees, so the template is its only check.

Template requirements the Phase 1 spikes already established, binding on
WP-2.2a unless a later measurement overrides them:

- `liga` and `clig` OFF wherever letter-spacing is set (Pango suppresses
  ligatures under tracking; WP-1.1 matched 86 letter-spaced runs only after
  this), and tracking applied between glyphs only, as exactly
  `(n-1) x letter_spacing`.
- `par(linebreaks: "simple")`, and hyphenation off for `en` to match
  WP-1.5's scoped switch.
- THREE body measures, not one: 325 pt, 311 pt (24 blocks), 312.1614 pt
  (one block). A template assuming a single measure diverges on 25
  paragraphs. The 325 pt figure is confirmed exact (WeasyPrint's content
  width is 433.3333333333333 px), but the Typst column is set slightly
  WIDER, at the midpoint WP-1.7 measures, to compensate Pango's integer
  1/1024 px line widths (WP-1.6). Cite WP-1.7 for the number; never pick
  one.
- Per-run SIZE as well as per-run family: the inline-code paragraphs set
  8.2 pt against 10 pt body.

**WP-2.2a geometry and body**: A5 geometry, margins, body/quote/code
styles, folios, placeholder outer pages. Target: `mag render 010 --engine
typst` emits an interior.pdf; `mag parity 010` produces a verdict with
every tier evaluated and nonzero exit on failure (digest in evidence);
page boxes pass Tier S.

**WP-2.2b architecture**: article openers, headings, TOC, page caps.
Target: Tier S page count on 010; verdict digest recorded as the running
baseline.

**WP-2.2c placement**: figures, extracts, plates, tail ornaments, anchors.
Target: every 010 figure/extract present on some page (same-page equality
is WP-3.4); verdict digest recorded.

### WP-2.3 layout result and measure operations

- Owns: `mag/src/typeset/layout.rs`, `mag/src/render.rs` (typst measure
  wiring).
- Target: `--engine typst` emits the full RenderLayout JSON and native
  `measure_article`/`measure_edition`; on 010, `article_pages`,
  `editorial_pages`, `article_opener_fits` equal the oracle leg's manifest
  values; every other field compared, mismatches enumerated with the
  Phase 3 WP that owns them (never skipped). The `article_opener_fits`
  comparison requires WP-0.0c: without it the oracle side is `{}` and the
  clause passes vacuously, so assert the oracle side is non-empty before
  comparing it (same for WP-3.2's opener-fit booleans).
- Verify: the field-by-field table under `cargo test`, attached to
  evidence.

## Phase 3: convergence

Preamble (binds per rule 8): **Phase 3 starts when WP-0.2k has SEEDED the
baseline digest and made the ratchet operative, not when a human declares
anything** (revision 40 replaced the content-final gate; see its changelog
for the argument and the measurements). The gate's own stated reason was
that a moving corpus makes a per-page ratchet meaningless, which is a claim
about corpus STABILITY rather than editorial quality, and stability is
mechanisable. By the plan's own rule 7 a Fran gate exists only where the
plan must change or something is irreversible, and freezing a corpus is
neither, so the gate failed the plan's own test for being one.
It is replaced by a MECHANICAL precondition rather than simply deleted,
because verification found the mechanism was specified but never completed:
`baseline.json` holds zero page entries and a null `staged_input_digest`,
so `staleness()` returns `"unseeded"` on every run today and guards
nothing; the refusal fires only when `--set` is passed, so a bare
`mag parity 010` on a moved corpus records staleness and CONTINUES; and no
per-page ratchet comparison exists anywhere in `mag/src/parity.rs`, so the
refusal message's promise that "ratchet comparison [is] refused" is
aspirational. **Phase 3's stated verification, "`mag parity 010` green
against `baseline.json` (no page regresses)", is therefore not executable
today for reasons that have nothing to do with Fran.** WP-0.2k makes it
executable; until then Phase 3 is blocked on code, which someone can write
now. Strictly serial, this order.
Every Phase 3 WP except WP-3.0g owns `mag/src/typeset/**` plus its evidence
file and NOTHING else; comparator territory is out of bounds (rule 4). Each
WP is scored on its named `page_sets:` entry. Verification, identical for
all: `mag parity 010` green against `baseline.json` (no page regresses;
raises are the
verifier's), and the named page set at the named standard.

- **WP-3.1 body text** (`page_sets.body`): Tier S text+color + G2. Also
  carries WP-1.2's single break miss, which needs the engine and so belongs
  here. The 147/149 versus 148/149 count does NOT: see WP-1.8, moved out in
  revision 40 because it is a measurement someone can perform today and was
  sitting behind a gate for no reason.
- **WP-3.2 headings, openers, TOC** (`page_sets.openers`): Tier S + G2;
  opener-fit booleans exact.
- **WP-3.3 code blocks and extracts**: 010 carries neither, so this WP
  gates on a committed fixture edition (fenced code in two languages, one
  extract with begin/end markers, built once under `mag/tests/typeset_*`
  fixtures) rendered by both engines and compared `--pre-rendered`:
  input-level byte-exactness green; (text-run, fill color) sequences
  identical inside code boxes; G2 boxes. `page_sets.code` stays as the
  rule for future editions that do carry them.
- **WP-3.4 figures, plates, ornaments** (`page_sets.placement`): Tier S
  same-page; G2 boxes; effective_ppi equal within 0.5.
- **WP-3.5 furniture and navigation** (`page_sets.furniture`): G2
  everywhere; Tier S navigation clause.
- **WP-3.0g enforcement flip (comparator WP)**: owns `parity.yaml`;
  raises the ratchet target to Tier E (a pure tightening; rule 4). Before
  raising it, re-derives **WP-0.2i's per-glyph floor** from the real
  Typst-vs-WeasyPrint pair that now exists (the obligation moved with the
  clause when WP-0.2f's raster guard was withdrawn), and fails loud if it
  exceeds the synthetic floor: that would mean a divergence outside Tier
  E's enumeration, which is a plan revision rather than a wider bound.
- **WP-3.7 the Tier E burn-down**: drive every compared page to display-
  list equality and raster agreement within the derived bound. Evidence is
  the residual ledger:
  every non-equal page, the exact display-list diff, the cause. Ends only
  when the ledger is empty; an entry that cannot be emptied is
  `Status: blocked` and a plan revision (fail loud). No acceptance path.

## Phase 5: port the rest of Python to Rust

Preamble (binds per rule 8): each WP owns the named Rust module,
`mag/tests/<wp-slug>*`, Cargo files, and its evidence; originals stay until
WP-6.1; none touches `mag/src/typeset/**`, `mag/src/render.rs` (except
WP-5.6), or comparator territory. Oracle-equality tests shell the pinned
tools from `cargo test`; they do not use `mag parity`. Python-side oracle
dumps are produced by full inline invocations (`uv run python -c '...'`)
recorded verbatim in `## Commands` so the verifier reproduces them; no
uncommitted scripts.

**Derive the dependency graph from the IMPORT graph, not from the plan's
own groupings.** Three undeclared edges were each discovered the expensive
way, by a WP walking into an unlanded callee, before anyone simply read the
imports. The reconciliation is now done and the graph carries every
internal edge among modules Appendix A assigns to WPs. When a WP is cut or
re-cut, check it against the imports of the Python it ports; that is a
cheap read and it is authoritative in a way a grouping by theme is not.

**Compare the decoded STRUCTURE, not the serialization.** When an artifact's
bytes are one tool's way of writing a meaning that is itself checkable,
compare the meaning: it is insensitive to how a library formats output
while still catching a wrong version, mask, level or ordering. This has now
rescued two situations that looked like dead ends, the critic's text source
(WP-5.3d, compare decisions and tracer-derived structure rather than
pypdf's exact line breaking) and the QR codes (WP-5.5a, compare the module
matrix rather than segno's SVG). It is the first thing to reach for when an
oracle seems to demand reproducing a library's formatting choices. It is
NOT a licence to weaken an oracle whose bytes are themselves the artifact,
which is why the web tree keeps byte-identity as its bar. And it has a
second, sharper limit, measured by WP-5.4: **a structural comparison cannot
see a wrong CONSTANT that produces structurally identical output.** A
transposed parameter pair on the cover wordmark (horizontal_scale 105.1
with stroke_width 0.30, against the orange tail's 106.6 with 0.15) passed
every structural check while differing on 10,768 pixels in a bbox of
428,221 to 967,326. Where an artifact can be rasterized, structure and
pixels answer different questions, and the plan asks both.
**The deeper generalization, and it is not about pixels.** Revision 24
recorded the transposed constant as the limit of structural comparison, and
WP-5.4's evidence then called the luma defect "the same lesson in a second
form". Its verifier corrected that, and the correction is worth more than
either example: they are DUAL, not the same. The transposed constant was
invisible to STRUCTURAL comparison and visible to pixels. The luma defect
was invisible to PIXELS, the raster hash passing while the zone statistics
were wrong, and visible only to a DIRECT ASSERTION against Python's
numbers.
**AN AGGREGATE IS NOT A POPULATION, and a count that stays put is not
evidence that nothing moved.** WP-1.2 records its styled-run fix as
"147/149 to 148/149". Measured by WP-1.8, the fix repairs block 39 and
SIMULTANEOUSLY INTRODUCES block 4, so **the 147 before and the 147 after
are two different 147s**. That is where the plan's false hypothesis about
WP-1.7's harness came from: someone read an unchanged aggregate as an
unchanged population, and the plan then carried it for several revisions.
The check is to compare the member SETS, not the totals, which is exactly
what named block 4. Sibling of the case below, and together they say the
same thing from two directions: a total can move while the population is
healthier, and a total can sit still while the population changes
underneath.

A second example of the same shape, more disorienting because here a
metric getting WORSE is the port getting MORE RIGHT: WP-5.3b-i's `text_characters`
moved NON-MONOTONICALLY, 34 pages gaining agreement and 7 losing it, net
+27, and the 7 losers are exactly the 7 `body_text_lines` pages that had
agreed under the bug only BY COINCIDENCE, because missing spaces cancelled
an extra newline. A reader watching that number fall would diagnose a
regression and be wrong.
What generalises is therefore **a defect can be invisible to any
given oracle level**, which is the actual argument for a layered gate
rather than an argument for pixels. It changes the question an oracle
designer should ask, from "is my comparison structural or photometric" to
"what class of defect is invisible at THIS level, and what other level sees
it". The two examples are unusually clean proof because they point in
opposite directions and came from the same WP.

A THIRD limit, which is really a design parameter: **a structural
comparison's RESOLUTION is as much a part of its design as its shape.**
WP-5.2's display-list comparison is otherwise the technique applied well,
and is its third earning: it replaces every resource NAME operand with the
SHA256 of the object it resolves to, seeing through pypdf's rename scheme
and both encoders' formatting while still failing on any change to what is
drawn, in what order, against which font or image. But it formats operands
at 6 decimals, and that is exactly what made it BLIND to the f32 defect
below. Choose the resolution deliberately and record it, or the comparison
silently defines what counts as identical.

**A corpus-based oracle proves only what the corpus contains.** This is the
single most repeated lesson of the execution so far. Edition 010 has no
padded containers, which hid WP-5.1a's defect; no explicit ports and no
non-printable characters, which hid WP-5.1b's two and WP-5.1c's one. So
every port WP must state in evidence **which branches of its source module
the corpus cannot reach**, and cover those by fixture. WP-5.1c did this
well for the manifest's refusal branches and badly for character classes,
and the character class is what bit. Enumerate by reading the Python for
branches, not by reading the corpus for cases.
**For a refusal guarding a NUMBER, the fixture pair must STRADDLE the
boundary.** Full-message equality is cheap to satisfy and proves less than
it looks: it proves the message text and that SOMETHING refused, not that
the THRESHOLD is right. WP-5.4b found this on itself. Its first
deck-overflow fixture used twelve contributors, which wrap to ten lines, so
raising the refusal limit from 5 to 8 STILL REFUSED: the fixture sat so far
past the boundary it would have refused under any plausible rule. It
measured the wrap counts, found seven contributors wrap to exactly six
lines, and tightened to that, with a companion test pinning the fitting
side at five. So the requirement is a PAIR at the finest granularity the
guard can distinguish, one input that refuses and one that passes,
differing by one step. Stating it as a pair rather than as "perturb the
threshold" is deliberate: the pair is a property of the FIXTURES and needs
no code mutation, and a tight pair necessarily flips when the threshold
moves by one, which is the verification that it is tight. WP-5.4b then
applied the same perturbation to the wordmark floor (25.0 to 20.0) and the
title floor (12.0 to 8.0) and both fail properly.
**A MULTI-STEP perturbation is not evidence of tightness.** It demonstrates
only that the guard is NOT INERT, which is a weaker claim and the one such
evidence is entitled to make. WP-5.4b's two surviving guards read as
verified for exactly this reason: the wordmark floor is 25.0 and its
fixture first fits at 21.0, eight steps of slack, perturbed by ten; the
title floor is 12.0 and fits at 10.5, three steps of slack, perturbed by
eight. The smallest FLIPPING moves are 25.0 to 21.0 and 12.0 to 10.5, and
neither was the move made. So a perturbation must be ONE STEP at the
guard's own granularity, or the evidence says "not inert" and claims no
more. WP-5.4b-ii owns the fix.
What tightness looks like when it is real, from the same sweep: the
headline pair now shares an 83-character stem and differs in ONE GLYPH,
flipping because only the third line's width changes (300.36 against
307.00 at size 20.0, `A` being 6.64 pt wider than `I`), and no tighter pair
can exist because the guard's loop evaluates only multiples of 0.5. The
line limit meanwhile discriminated LOOSENING but not TIGHTENING, because
there was no fitting headline fixture at all and 010's own headline wraps
to two lines: a guard can be half-verified, and saying which half is the
labelling rule 10 asks for.

**The rule binds on INHERITANCE, not only on authoring.** A WP that adopts
fixtures it did not write has UNVERIFIED pair-tightness for every numeric
guard in them until someone moves the threshold, so re-cut and successor
WPs sweep what they inherit rather than assuming the previous author did
it. This is now the THIRD instance of the finding and the FIRST in
inherited rather than authored code: WP-5.4b fixed its own deck fixture and
then its verifier found the same weakness in the HEADLINE refusal it had
inherited, which guards two numbers and discriminates on only one (moving
the line limit from `<= 3` to `<= 6` fails its test, but dropping the size
floor from 20.0 to 15.0 leaves all eleven tests passing, because the
headline string sits far enough past the boundary to refuse under a 25%
looser floor). A rule that binds only at authoring time exempts every
inherited fixture, and inheritance is common now that WPs re-cut.
**WP-5.4b-i** owns that fix, `mag/tests/cover_*` only.
Note what was NOT a rejection: WP-5.4b's evidence claimed only that three
of six refusals were perturbed at their threshold and never asserted the
other three discriminate, so rule 10's labelling duty was met and the
verifier was right to accept. The remaining two, missing cover art and
unknown layout, are categorical with no number to move, so the
message-only classification covers them correctly.

**And say which refusals are which.** Evidence classifies each refusal as
THRESHOLD-DISCRIMINATING or MESSAGE-ONLY. Message-only is not a weakness
where there is no number to get wrong: for an unknown enum value, a missing
key or a type mismatch, message equality IS the whole property and
perturbing anything would be busywork. The rule targets numeric guards
only, and it costs one step per numeric site. This is rule 10 applied to
refusal tests: a test that cannot presently discriminate must say so.

**For REFUSAL coverage, ask the ORACLE which inputs it refuses** rather
than reasoning about which are reachable. WP-5.4b understated its own
refusal coverage (six `bail!` sites in `svg.rs`, three tested, one
disclosed, two neither) and argued its way out of deck-overflow coverage,
when it had ALREADY solved that exact problem for the headline by asking
Python which strings it rejects. Enumerating refusals by reading the
Python's raise sites is the same move as enumerating branches by reading
the Python, and it is cheaper than arguing about reachability.

The cleanest demonstration so far is WP-5.2's, and it is a MEASUREMENT of
the rule rather than an argument for it: a scale-from-CropBox perturbation
failed both the display list and the raster on its `crop` fixture while the
LIVE-010 test passed, because 010's CropBox equals its MediaBox on every
page. The fixture is the only thing that catches that defect, shown on a
specific defect rather than asserted in general.

**Pin Unicode-dependent operations to Python's tables while Python is the
oracle.** Python runs Unicode 15.0.0 and Rust's std is newer, and they
DISAGREE on 55 codepoints: `char::to_uppercase` supplies an uppercase where
CPython gives none across U+019B, U+0264, U+1C8A, U+A7CD-A7DB, U+10D70-
U+10D85 (Garay) and U+16EBB-U+16EC4, and `to_lowercase` disagrees on
U+1C89. This is not hypothetical and it is not loud: these operations feed
the WEB EDITION, whose oracle is byte-identical output, so an unpinned
mapping surfaces as a baffling byte mismatch months later, only when a
manuscript happens to contain one of 55 codepoints. A port that
upper-cases, lower-cases, casefolds or strips must therefore either PIN the
operation to Python's tables or DEMONSTRATE agreement over the whole plane;
WP-5.4a did both, pinning 1530 and 1525 entries and sweeping all 1,112,064
codepoints three times. Currently exposed: WP-5.5a (web), WP-5.3b (the
critic's `body_text_lines` lowercase filter IS a case operation), and
WP-5.4/WP-5.4b wherever cover typography touches case.
The cost, recorded rather than discovered: this FREEZES those operations on
Unicode 15.0.0, which is right while Python is the oracle and wrong the
moment it is gone. WP-6.1 carries the obligation to revisit it, so the
freeze is a choice someone makes rather than an inheritance nobody noticed.

**A helper that exists twice will drift.** Three of the six rejections in
this run came from one behavior living in two places: WP-5.1c reintroduced,
by copying, the exact `py_repr` defect WP-5.1b had already been rejected
for and fixed, into the module with the widest exposure. A port WP may not
copy a helper out of another model module. Import it, or, where rule 1's
Owns boundary genuinely forbids that, duplicate ONLY under the strong form
below and say in evidence why importing was not possible. WP-5.1d then
consolidates.

**Two ways to defend a duplicate, and they are not equal.** The STRONG form
pins each copy to ITS OWN Python original by its own oracle. The WEAK form
pins the copies to EACH OTHER. The weak form is a last resort, never an
equal alternative, for one reason: **agreement is equally satisfied when
both copies are wrong.** Three instances in this execution point the same
way. `art.rs::grey` was caught by WP-5.4's oracle being unfaithful to
`cover.py`'s `convert("L")`, and no comparison between the two Rust luma
functions could ever have caught it, since they were never compared and a
shared error would have passed if they had been. WP-5.4a, unable to import
the helpers it needed, duplicated them but pinned its copies to PYTHON over
the whole plane rather than to the sibling Rust copy, which is why its
duplication was a structural exposure rather than a live defect. And
WP-5.1c's `py_repr` copy, which WAS only checked against its sibling,
carried the pre-fix body with no test noticing. So when a duplicate is
unavoidable, pin it to the oracle; pinning it to its twin proves only that
they match.

**A port STRICTER than its oracle is a defect too, and a quieter one.**
The deliberate-divergence rule below licenses a port that reports where
Python crashes. Its mirror is not licensed: a port that REFUSES an input
Python accepts is a defect of the same family, and harder to find, because
it only surfaces when someone finally feeds it the input the oracle was
always happy with. Two instances now, pointing opposite ways.
`manifest.rs`'s `_check_unique_art` was LOOSER in a good way and is
recorded below as a deliberate divergence. `metrics.rs:95` was STRICTER: it
bails on ANY eXIf chunk, while PIL's `Image.open().convert("RGB")` returns
edition 010's cover art unrotated at 1440x2160, its EXIF holding tag 34665
(ExifOffset) and NO tag 274 (Orientation), and the Python cover compiler
never calls `exif_transpose`. So the guard was a divergence from PIL
wearing the clothes of a safety measure, and it blocked WP-5.4 from grading
the very image it exists to grade, with WP-5.5b's preflight port next in
line over the same decoder.
The distinction that keeps this from contradicting the plan's fail-loud
discipline: **fail-loud is right for the COMPARATOR**, where an unknown
operator or colour space must stop rather than be mis-compared, and wrong
for a PORT beyond what its oracle refuses, where the Python IS the
specification. A port that wants to be stricter declares and argues it like
any other divergence, never assuming strictness is free.
Prefer NARROWING a guard to deleting it (here: bail on an orientation tag
whose value is not 1), and re-run the original WP's full oracle before and
after, so an accepted verification is not silently invalidated.

**Deliberate divergence, and its limits.** Where the Python CRASHES, the
port does not reproduce the crash. Porting a crash is not fidelity, and
these crashes destroy information: `manifest.py`'s `_check_unique_art` runs
after the validator has recorded shape errors but before raising them and
trusts the shapes it just rejected, so a non-mapping `cover` or
`opener_art` dies with AttributeError and a non-iterable `closing_plates`
with TypeError, throwing away diagnoses Python had already accumulated (for
`cover: text` it records "Edition cover must be a mapping" and then loses
it). The Rust loader returns those diagnoses. Exact-message equality is
untestable for such inputs anyway: a traceback is not a message, so nothing
is weakened by diverging. WP-5.1b set the precedent, WP-5.1c follows it.

The limits are strict, and a WP claiming a divergence must satisfy all of
them or the divergence is a defect:

- the divergence is only ever toward MORE diagnosis, never toward accepting
  what Python refuses. A port that is more permissive than its original is
  a bug, whatever the original does;
- every diverging input is enumerated in evidence with the Python behavior
  and the Rust behavior side by side, and is covered by a test;
- the oracle comparison stays exact for every input Python handles without
  crashing. A divergence is never a reason to loosen the oracle;
- fixing the Python instead is available but not preferred: it needs a
  sanctioned oracle-change WP, costs a re-render and a full verification
  cycle, and improves code scheduled for deletion at WP-6.1. Choose it only
  when the crash would otherwise hide a real difference.

- **WP-5.1a document model** (`publication_document.py`,
  `document_structure.py`, `reader_text.py`): owns `mag/src/model/doc.rs`
  (+ markdown crate). Oracle: plain-text and structural projection of every
  010 manuscript equals the Python model's dump.
- **WP-5.1b records** (`records.py`, `media_schema.py`): owns
  `mag/src/model/records.rs`. Oracle: loaded-record equality over
  `library/sources/`.
- **WP-5.1c manifest** (`manifest.py`): owns `mag/src/model/manifest.rs`.
  Oracle: the loader-owned subset of 010's `edition-manifest.json`,
  extracted identically from both sides with
  `jq -S '{edition, layout: (.layout | {maximum_article_pages,
  article_page_caps, article_content_modes, maximum_editorial_pages})}'`
  (note the `.layout |` pipe; without it every value is null), byte-equal,
  with a no-null sanity check on the oracle extraction; layout-derived
  fields (`article_pages`, `article_terminal_balance`, `figures[*]`) and
  request-derived fields (`publication`, `inputs`) excluded as the
  renderer's. Plus the refusal matrix: every ValidationError raise site in
  `manifest.py`, provoked by fixture, mapped to a Rust error variant +
  message substring; enumerated in evidence, checked by the verifier
  against the raise sites.
- **WP-5.1d consolidate the model helpers**: owns `mag/src/model/doc.rs`,
  `records.rs`, `manifest.rs` and a new shared module. Target: `ValidationError`,
  `py_repr`, and `io.py`'s `load_structured` and `safe_project_path` exist
  in ONE place, with NO behavior change. This WP exists because the
  duplication already shipped a defect: `manifest.rs` carried a copy of
  `records.rs`'s `py_repr` that was the PRE-FIX body, reintroducing the
  exact defect WP-5.1b had been rejected for, in the module with 25 call
  sites over hand-authored `edition.yaml` text where anchors and extract
  markers are pasted from the web. Five of seven probes diverged and no
  test caught it, because the 74-case corpus holds no non-printable
  characters.
  Verify: every oracle in WP-5.1a, WP-5.1b and WP-5.1c replays
  byte-identically before and after, plus a duplicate-helper audit that
  FAILS if any helper is defined in two model modules. Sequencing: lands
  only after WP-5.1b and WP-5.1c are both accepted, or it collides with
  their reworks. It is a refactor, so it may not change a single oracle
  byte; if it does, that is a defect in the consolidation, not a new
  finding.
- **WP-5.1e widen the duplicate-helper audit and lift the Python-semantics
  helpers**: owns `mag/src/model/shared.rs` (or wherever WP-5.1d put the
  shared module), the audit itself, and the call sites it updates,
  including `mag/src/cover/text.rs`. Lands after WP-5.4a's verification.
  **BOTH halves, not one.** The choice was framed as widen-the-audit or
  lift-the-helpers; the evidence says the second alone is already
  insufficient and the first alone leaves today's duplicates in place.
  - **Lift**: `is_python_space` (private in `doc.rs`) and `py_str` (private
    in `manifest.rs`) join `py_repr` in the shared module, because WP-5.4a
    needed both, could not import either, and duplicated them into
    `cover/text.rs`. It pinned its copies to PYTHON over the whole plane
    rather than merely to the other Rust copy, which is stronger than the
    duplicated-helper rule asks, but the exposure is structural, not
    behavioural. **WP-5.4a's pinned case tables belong in the same module**:
    the Unicode rule above guarantees WP-5.5a and WP-5.3b need exactly
    those tables, so leaving them in `cover/text.rs` schedules the next
    duplication rather than preventing it. That is why "these two are the
    only cross-cutting cases" is false: the rule this revision adds creates
    more.
  - **Widen**: the audit from WP-5.1d scans only the four model modules,
    and the codebase now has Rust in `model/`, `critic/`, `cover/`,
    `parity/`, `impose.rs`, and soon `package/` and `web/`. It keys on
    (name, signature, normalised body), so widening to every module under
    `mag/src/` is mechanical.
  - **Detection failed at THREE levels on the luma pair, which is the
    argument for the rule rather than for a better scanner.** The two
    implementations differ in name, in body, and in fixed-point SCALE and
    rounding, so neither audit key fires; and a manual grep missed it too,
    because `299` and `19595` denote the same coefficient and share no
    substring. The audit is worth widening, but it cannot close this class,
    and the mitigation is the strong-form rule above.
  - **The KEY is refined (revision 32), because a (name, signature) key
    fires on `load`, `new`, `open`, `read`, `write` and `default` forever.**
    It fired on `load` defined in both `cover/outline.rs` and
    `package/preflight.rs` with unrelated bodies, the second false positive
    of that class, and WP-5.5b renamed its own function to `Pdf::read` to
    get past it. Note what the two keys actually catch before changing
    either: the BODY key catches an exact copy before it drifts, and the
    NAME key is the DRIFT detector, since a drifted copy has an unequal
    body by definition (WP-5.1c's `py_repr` carried the pre-fix body and
    only the name key could have seen it). So requiring body similarity as
    well would delete the drift detector, which is the audit's whole
    purpose, and letting the allowlist grow turns the signal into noise a
    genuine duplicate can hide in.
    Replace the (name, signature) key with an explicit **REGISTRY of names
    the shared module owns** (`py_repr`, `py_str`, `is_python_space`,
    `luma601`, the pinned case tables, and whatever is lifted later): those
    names may not be defined anywhere else, and nothing else fires on name.
    That is exact rather than heuristic, has NO false positives on ordinary
    Rust vocabulary, and enforces precisely the rule the plan already
    states, that Python-semantics helpers live in one place. Keep the body
    key globally. Growing the registry is a deliberate act when a helper is
    lifted, where growing an allowlist is an apology for a bad key.
    **And the principle the rename exposed, which matters more than the
    key: a tool that makes you rename CORRECT code is mis-specified, and
    the fix is the tool, not the code.** WP-5.5b's rename was reasonable
    under the circumstances and should now be revisited on its own merits,
    keeping `Pdf::read` only if it is genuinely the better name rather than
    as a monument to a false positive. An audit that distorts the code it
    audits has inverted its relationship with it.
    The audit is being TUNED, not doubted: it has already paid for itself
    twice, reaching the `luma601`/`grey` territory and forcing this
    decision before a third `load` appeared.
  - **Remove the 40-character body floor.** The verifier found the audit
    skips short bodies, and a wider scan makes that matter more, because
    short bodies are exactly where trivial Python-semantics helpers live. A
    length threshold is a silent exemption of the kind rule 10 now forbids;
    if the wider scan produces genuine coincidences, the answer is an
    ALLOWLIST with a reason per entry, never a blanket floor.
  - Verify: the audit fails on a deliberately planted duplicate in a
    non-model module and on a planted short-bodied one; every existing
    oracle in WP-5.1a/b/c and WP-5.4a replays byte-identically, since this
    is a refactor and may not change an oracle byte.

- **WP-5.1f pin the shared whitespace helpers to Python**: owns
  `mag/src/model/shared.rs` and its fixtures. Done.
  **The sweep is CLOSED, and its closing statement is the standard other
  residuals should meet**: the grep returns SEVEN LINES AND ONLY SEVEN, two
  definitions (`is_python_space`, `py_strip`) and five uses, three of them
  wrong and now pinned (`is_name_roster` twice, `content_label` once),
  while `ui` and `clamp_roster` handle no whitespace at all. The next
  reader does not need to re-open the file. A sweep records the BOUNDARY it
  established, not only the defects it found; without the boundary the next
  reader repeats the sweep to learn whether it was complete.
  Its whitespace finding also corrected a framing: the defect was described
  as confined to the empty-test fall-through, and the fixture showed
  `label: "  Dispatch  "` strips the RETURNED VALUE too, so it never was.
  Found by WRITING THE FIXTURE rather than by reading the code, which is
  the padded/straddle lesson arriving again.

- **WP-5.1g the `content_label` None guard** (class B per rule 6a): owns
  `mag/src/model/shared.rs:327` and its fixtures. **A bare `label:` in a
  manuscript prints the literal word "None" as a section label**, because
  the Rust maps `py_str` over the raw value with no None guard and
  `py_str(Null)` is `"None"`, while `html_edition.py:737` guards
  `value is not None and str(value).strip()` and falls through to `_ui`.
  Confirmed at source in both engines. Latent in 010 only by CORPUS
  ACCIDENT, 548 `label:` keys over 20 distinct values with none bare, so
  the fixture carries the bare case the corpus lacks.
  Target: `raw=Some(Null)` yields the `ui` fallback, matching Python; the
  regression test pins the CORRECT STRING rather than "equals Python", per
  rule 6a, so it still says something after WP-6.1.
  **Record the class-C neighbour rather than fixing it here**: `label:
  false` prints the literal `"False"` in BOTH engines (executed, not read),
  so parity can never see it. That is a product question, not a port
  question, and it goes to Fran with the others rather than to a WP.
- **WP-5.2 booklet imposition** (`booklet.py`): owns `mag/src/impose.rs`.
  Oracle: impose the same 010 reader.pdf both ways; display-list equality
  and raster zero-diff per sheet, spread order text identical. Zero-diff is
  the right bar here because both implementations place the same page
  content by the same arithmetic; a sub-quantum difference means the
  arithmetic diverged and must be explained in evidence. (Revision 15
  withdrew WP-0.2f's raster bound entirely, so there is no bound to absorb
  it into even if anyone wanted to.)
- **WP-5.3a critic raster metrics** (`image_contrast.py`,
  `concurrency.py`'s role): owns `mag/src/critic/metrics.rs`. Oracle: 010
  metric values within `parity.yaml critic_metric_tolerances:` (fixed by
  WP-0.2d; this WP never authors tolerances).
  **Scope correction, found by the WP itself**: only `concurrency.py`
  actually feeds `render_critic.py`. `image_contrast.py` is not used by the
  critic at all; its consumers are `preflight.py`, the reportlab
  `render.py` (never ported, dies at WP-6.1) and `weasyprint_adapter.py`,
  and its numbers land in **preflight.json**, not render-critic.json. So
  the real downstream consumer of `mag/src/critic/metrics.rs` is **WP-5.5b**
  (preflight), and the module's name is misleading about where it belongs.
  It is deliberately NOT renamed: the code is correct where it sits, it is
  already shipped and verified, and a cross-WP rename to satisfy a taxonomy
  would cost more than the confusion it removes. This note is the fix.
  RESULT (done): the tolerance was entirely unconsumed, because the port
  achieved EXACT equality, relative delta 0.0 across all 14 images,
  asserted at three levels (decoded pixels matching PIL's `convert("RGB")`
  by SHA256, thumbnails matching PIL's LANCZOS pixel for pixel, and every
  analysis field). So `critic_metric_tolerances` has not yet been tested by
  anything; its first real exercise is WP-5.3b. The WP added `png` 0.18
  rather than `image` on purpose: PIL drops alpha WITHOUT compositing and
  ignores `tRNS` on palette images, and a decoder that silently normalises
  to RGBA would hide exactly that behaviour. It also caught two of its own
  fixtures passing vacuously because they were uniform, and recorded that
  one of four revert probes does not discriminate on this corpus (no
  luminance lands on a .5 histogram boundary), adding a direct rounding
  oracle against Python instead. That is the corpus rule working.
- **WP-5.3b RE-CUT (revision 29) into WP-5.3b-i, -ii, -iii.** It ended
  `blocked` with evidence only (commit a430663) on two blockers, the second
  of which is scope: the critic's decisions span 31 issue sites needing
  three PDFs rasterised at 144 dpi, PIL-exact `_inspect_page`, void
  geometry, tail bands, opener offset colour detection and crop fidelity.
  A PARTIAL port yields a partial decision set, which cannot be compared
  against Python's full one, so there is no smaller honest unit that meets
  the stated oracle. Splitting along the dependency seam is the only way to
  make progress without weakening the oracle.
  Everything the original bullet established still binds the successors:
  the decision-level oracle from WP-5.3d, the tracer as text source, the
  five text-derived fields feeding ELEVEN issue sites, the
  `cover_spread_checks`
  dependency on WP-0.2h, the WP-5.2 import edge, and the unnamed raster
  helpers (PIL grayscale, histograms, `ImageChops.difference`, LANCZOS
  resize).

- **WP-5.3b-i the critic's text source**: owns `mag/src/critic/text.rs`.
  Already BUILT and measured; needs only WP-2.0b's export (blocker 1
  below). Re-measured against the CURRENT tracer rather than inheriting
  WP-5.3d's figures, which is rule 9 working: **text-emptiness now agrees
  56 of 56**, up from 54 of 54, because WP-0.2h's standard-14 decode gained
  the two cover pages pypdf could read and the tracer could not, and it
  reproduces pypdf's exact 7-empty / 49-non-empty partition, so it
  DISCRIMINATES. `body_text_lines` 49 of 56. `text_characters` **43 of
  56**, and it feeds no issue site. (Read 16 of 56 until revision 50: that
  was the PRE-rework figure measured under the `Show.width` unit defect
  `80b7b62` fixed. WP-5.3b-i's evidence and WP-5.3b-ii's independent
  measurement both give 43, on different renders with different
  `reader.pdf` sha256, so this figure is base-invariant even though
  revision 49's named-commit rule warns that some are not.)
  The seven `body_text_lines` differences are CONFIRMED as one cause rather
  than inherited as folklore: all seven are opener pages where the tracer
  counts one line more, and reading pypdf's own output on two of them shows
  `'Government Rails Site HitHours After CVE Patch'` and `'The third era of
  AI softwaredevelopment'` as merged two-line headlines. The tracer keeping
  them apart is CORRECT.
  Its join rule (group shows by device y within 1 pt, order by x, insert a
  space when the gap exceeds 0.25 of the larger font size, width from
  WP-0.2i's per-glyph offsets) is labelled under rule 10 as **NOT
  DISCRIMINATING ON 010**: 184 of 1,263 lines carry multiple shows, and
  switching between empty-string and geometric joins changes neither
  emptiness nor `body_text_lines`. It is chosen because it is PRINCIPLED,
  not because this corpus can tell the difference. That is rule 10 working
  as intended and is the plan's reference example of the label.
  **Owns the Unicode residual**: `body_text_lines` uses
  `char::is_lowercase`, which is NOT pinned to Python's tables, so a page
  containing U+1C89 could in principle diverge. Unmeasured. Revision 22's
  rule covers it and `mag/src/model/shared.rs` already holds the pinned
  tables, so this is a naming problem rather than a research one: pin it or
  demonstrate whole-plane agreement, and say which.

- **WP-5.3b-ii page inspection**: owns `mag/src/critic/inspect.rs`. The
  PIL-exact `_inspect_page` and the three 144 dpi rasterisations, plus the
  raster helpers the original bullet named. Depends on WP-5.3b-i and
  WP-5.3a.
  RESULT (done, accepted, commit `20adcfb`): 85 of 85 rasters
  byte-identical to Python's output, 85 of 85 `_inspect_page` rows
  identical, 15 fixture rows, 17 discrimination probes every one of which
  fails under mutation, and both extremes of the punctuation filter failing
  per rule 10's diagnostic. `render_pages` is proven SHARD-INVARIANT across
  1, 3, 5, 12 and default shards, which is what makes a committed sha
  oracle machine-independent given Python uses `os.cpu_count()` and Rust
  `available_parallelism()`; a sharded oracle without that proof is
  machine-specific and nobody would notice until it ran elsewhere.

- **WP-5.3b-iii the checks**: owns `mag/src/critic/rules.rs`. Void
  geometry, tail bands, opener offset colour detection, crop fidelity, and
  the 31 issue sites. Depends on WP-5.3b-ii, WP-5.2 and WP-0.2h. This is
  the WP that meets the decision-level oracle, since only here does a full
  decision set exist to compare. WP-5.3c and WP-5.3g depend on it rather
  than on -i or -ii.
  **BLOCKED on one word**: `_inspect_opener_crop_fidelity` needs
  `mag/src/critic/metrics.rs:411 fn resize`, which is private (verified)
  and is already PIL's `Image.resize` proven by WP-5.3a. WP-5.3b-ii
  correctly did NOT take the `pub(crate)` itself, since `metrics.rs` is not
  its path, and correctly did not write a second LANCZOS, since two copies
  would be pinned to each other rather than each to Python. This is the
  third instance of the private-sibling wall; see rule 1's general
  statement. Resolved by a scoped Owns extension from the orchestrator.

- **Blocker 1, and the reason rule 12 exists**: WP-0.2h's seam is
  UNREACHABLE from the place it was built for. `mag/src/parity.rs:1-6`
  declares `mod display;` and `mod streams;` privately with no `pub use`,
  so `display::trace_elements` cannot be imported by `mag/src/critic/` and
  a consumer fails with `error[E0603]: module 'streams' is private`. The
  fix is one line and belongs to WP-2.0b, which holds `parity.rs`, together
  with a CONSUMER TEST that imports the ordinary way. WP-0.2h demonstrated
  the seam through a `#[path]` test include, which bypasses module privacy
  entirely, so the demonstration passed and its verification confirmed the
  demonstration while the seam stayed unusable. See rule 12.

- **WP-5.3d the critic's text source** (spike, evidence only; Phase 1
  preamble's isolation rules bind). Runs BEFORE WP-5.3b and decides its
  oracle. This exists because the question WP-5.3b ran into is the hardest
  one in Phase 5: how do you verify a port whose INPUT is an extractor you
  are also replacing?
  - The candidate answer, which costs nothing to test and would preserve
    the exact oracle: **derive the critic's text from the display-list
    tracer the comparator already has** (`mag/src/parity/streams.rs`,
    built by WP-0.2b, strengthened by WP-0.2e, verified twice), rather than
    from any general-purpose text extractor. The critic never needs words.
    `body_text_lines` is `splitlines()` filtered for a lowercase character,
    `text_characters` is `len(text.strip())`, and the spread check is an
    ordering question. Those are line-segmentation and ordering
    properties, and this pipeline emits ONE SHOW PER LAID-OUT LINE with
    every line independently positioned (WP-0.2b: 1488 shows, zero
    inheriting a previous advance). So the tracer has exact line structure
    where pypdf and poppler each apply heuristics, and it has exact paint
    order and geometry, which is precisely what poppler gets wrong on the
    imposed sheet.
  - Recorded probe, NOT a result: shows per page on 010's reader.pdf pages
    4 to 7 are 22, 33, 42, 21 against pypdf `body_text_lines` of 9, 29, 33,
    11. Shows are a superset, as they must be, since folios, headings and
    all-caps or numeric lines carry no lowercase character and drop out of
    the filter. Whether the per-show strings REPRODUCE pypdf's numbers once
    the critic's own filters are applied is exactly what this WP measures,
    and nothing here presumes the answer.
  - Target: for all 56 pages and all 28 spread sides, compute every
    text-derived critic field from the tracer and compare against the
    committed pypdf values. Report per-field agreement, and for every
    disagreement give the cause, not just the count.
  - The criterion, fixed in advance so the result decides rather than
    preference: **exact reproduction of every page row and the whole
    spread table** takes path A. Anything less takes path B.
  - Path A: WP-0.2h lifts the tracer into a module both the comparator and
    the critic can consume (a comparator WP, no behavior change, proven by
    parity verdicts staying byte-identical), and WP-5.3b then ports with
    its oracle EXACTLY as written. Nothing is re-scoped, and the pypdf
    text layer is never ported.
  - Path B: WP-5.3b's oracle moves to the critic's DECISIONS ({result,
    issue codes, severities, pages}), each implementation using its own
    text source, and the weight moves to WP-5.3c's fault suite. Path B
    carries a warning that must be honoured rather than noted: 010's issue
    set survives an extractor swap only by luck.
    `article-stub-last-page` fires on `body_text_lines < 5`, and on this
    edition every sub-threshold page is sub-threshold under both
    extractors, while pages 4, 5 and 6 differ by 1, 4 and 5 lines. A
    decision-level oracle on 010 alone is therefore weak evidence, so
    under path B the fault suite MUST carry near-threshold cases on both
    sides of every decision boundary, and the Rust text source must pass
    named not-worse checks in WP-5.7a's shape (no word welding, correct
    reading order per page).
  - RESULT (done, commit 2bc3900): **path B, with the TRACER as the text
    source rather than poppler.** Measured on the same tree WP-5.3b used,
    tracer against the poppler baseline: `text_order_matches` 27 of 27
    traceable sides against 7 of 28; `body_text_lines` 47 of 54 pages
    against 16 of 56; `text_characters` 7 of 54 against 9 of 56; cover
    pages 1 and 56 untraceable, 0 of 2, where pypdf reads both.
  - Path A fails its criterion, and **the reason matters more than the
    verdict: the tracer cannot reproduce pypdf's MISTAKES.** All seven
    `body_text_lines` divergences share one cause, pypdf merging a two-line
    article headline into a single line, visible as a missing space
    ("Government Rails Site HitHours After CVE Patch"), while the tracer is
    geometrically right every time, the two shows sitting at distinct y
    origins 28.8 pt apart. `text_characters` fails the same way: pypdf
    injects synthetic spaces into letter-spaced runs ("BY  FRANK RIETTA").
    Matching either means reimplementing `crlf_space_check`'s merge
    threshold and the `abs(op) >= _space_width * 0.95` rule with its
    half-a-space width, which is the "reproduce a hack to stay equal to a
    tool we are deleting" category this plan has now rejected three times:
    here, at WP-5.7, and at `_check_unique_art`.
  - **The luck caveat is measured away, but not the way WP-5.3d's evidence
    argued it.** Its claim that `article-stub-last-page` is the only
    text-derived decision is false and got the WP rejected (verify commit
    6c24379) while UPHOLDING the decision: five text-derived fields feed
    ELEVEN issue sites (3 + 3 + 3 + 1 + 1, counted from the enumeration
    above and confirmed against `render_critic.py`), and
    `body_text_lines < 5` is merely the only numeric
    threshold. The surviving and stronger argument is agreement rather than
    absence: the tracer matches pypdf on every field behind the other nine
    sites. Its verifier (accept commit 513a970) graded those agreements,
    and they are not equal in strength: `text_order_matches` at 27 of 27
    traceable sides and text-emptiness at 54 of 54 both DISCRIMINATE (pypdf
    partitions 7 empty against 47 non-empty, so agreement reproduces that
    partition, which the evidence undersells), while
    `standalone_punctuation_lines` at 54 of 54 is an EMPTY-SET agreement,
    `0 == 0` on every page. The decision stands on the discriminating two;
    the third is why WP-5.3c must fault that field. Near-threshold work
    is bounded to `body_text_lines` (page 36, 4 against 3, both below);
    fault coverage is not, and spans all five fields.
  - The third disposition stays available and is nobody's first choice:
    port pypdf's text layer as shared work with WP-5.7b, one investment
    serving two consumers, at 1701 lines plus 18452 lines of data tables.
    It is the fallback if both paths fail, and it is a plan revision.
- **WP-5.3c critic faults**: owns `mag/tests/critic_*`. Fault suite:
  swapped spread, missing tail band, low-ppi figure; both critics emit the
  same issue codes.
- **WP-5.3g comparator switch (comparator WP)**: owns `mag/src/parity.rs`
  + `parity.yaml`: the Typst leg's critic verdict (Rust critic) joins
  Tier S.
- **WP-5.4 cover compiler** (`cover.py`, the mode 010 uses): owns
  `mag/src/cover/`. Depends on WP-5.1c (the Rust Edition model) and
  WP-5.4a (the text helpers). The hard questions are now ANSWERED rather
  than open, and the plan should stop treating covers as risky:
  - **The backend is not a choice**: the Python side calls no Python
    rasterizer. The `resvg` PyPI package is a thin binding whose compiled
    library embeds resvg 0.47.0, usvg 0.47.0, tiny-skia 0.12.0, fontdb
    0.23.0 and rustybuzz 0.20.1, recoverable from the binary's build paths.
    The port calls THE SAME crates at THE SAME versions; pin them.
  - **resvg reproduces exactly, not within a bound**: the exact SVG each
    face hands to resvg, rendered through a Rust probe at those versions,
    gives decoded RGBA identical on both faces at 4,335,040 pixels each
    (front `3f853a0a65b06dd5...`, back `beb601e1ff00de84...`).
  - **Glyph outlines agree**: the cover SVG contains NO `<text>` elements
    at all, only outlines as `<path>` (178 front, 312 back), so usvg needs
    no font database and font resolution cannot diverge. Over all 834
    glyphs of Archivo Condensed Bold, the fontTools `SVGPathPen` string and
    the ttf-parser outline rasterize identically, 834 identical and 0
    differing; they differ textually (H/V and implicit lineto against
    explicit) and agree geometrically. Method note worth keeping:
    `RecordingPen` is the WRONG instrument and falsely reports 714 of 834
    differing.
  - **Oracle: display-list equality plus raster EQUALITY** for the front
    and back cover PDFs. Revision 13 wrote "within WP-0.2f's derived
    bound"; that bound never existed, revision 15 withdrew the raster guard
    outright, and for covers equality is both correct and STRONGER. The
    reasoning revision 13 gave (two generators placing outlines sub-quantum
    apart, a grid-fitting rasterizer turning that into pixel flips) does
    not apply: the cover PDF's visible marks are two path fills and one
    full-page Form XObject holding the resvg raster at 300 dpi, and no text
    show contributes a visible mark, so origin snapping cannot reach a
    cover raster at all.
  - **The invisible text layer's oracle is CONTENT AND PLACEMENT, never
    subset bytes.** Both faces carry a `3 Tr` layer via
    `_add_selectable_text_layer` in Inter-Regular holding the real strings
    (front BERRETA FUTURA / THE SPEED LIMIT / the contributor deck; back
    LOOP / CLOSED / the back-cover copy). Matching reportlab's Inter
    SUBSETTING byte-for-byte would be reproducing a hack to stay equal to a
    tool we are deleting, which this plan has now rejected four times. It
    also contradicts the division revision 19 drew: Tier S for content,
    Tier E for rendering. An invisible layer contributes NO rendering, so
    content is the only thing it has. Compare therefore: the decoded
    strings in order, their positions at the 0.01 pt quantum, render mode
    3, and the underlying VENDORED FACE the subset derives from. Never the
    embedded font program or its digest, since two subsets of one face
    legitimately differ.
  - The Rust PDF writer this needs must be written GENERALLY, not for one
    layout mode; WP-5.4b adds coverage, not a second writer.
  - **SETTLED, not merely feasible**: the `footer_caption` front cover
    rasterizes to sha256 `4b4549e9b97ead36...`, the SAME hash the probe
    produced from the SVG PYTHON emitted before any porting began; decoded
    RGB through PIL gives 0 of 4,335,040 pixels differing; the graded cover
    art matches independently at `695de5df97203c55...`; and the markup
    skeleton, every transform, translate and scale, matches Python to 8
    decimal places. `Cargo.lock` gained nothing at all, 397 entries before
    and after, because the typst crates already pulled resvg 0.47.0, usvg
    0.47.0 and tiny-skia 0.12.0 transitively at exactly the versions the
    Python binding embeds; the additions merely promote them to direct
    dependencies. Covers are answered; the plan no longer lists them as a
    risk.
  - **The luma question is resolved: there are two implementations, they
    are NOT both correct, and the fix is to use the correct one.** Three
    WPs have now touched grey-scale conversion. `art.rs::grey` is not a
    faithful port: `cover.py:495` uses `convert("L")`, PIL's fixed-point
    path, while `art.rs` computes per-mille, and they disagree on 540 of
    3,110,400 pixels of 010's actual art, shifting zone means by 1.238e-04
    and 5.652e-05. It passes today only because those statistics feed a
    threshold that a 1e-4 shift does not flip, which is **a pass by
    aggregation rather than by correctness**, the same family rule 10
    names: a check that cannot presently discriminate is not evidence that
    the thing under it is right. Fix by calling the existing
    `metrics.rs::luma601` rather than keeping a second implementation; that
    is also what WP-5.1e's lift-and-widen exists to prevent.
  - **Owns EXTENSION, granted (precedent: WP-0.0c's extension to
    `web_edition.py`)**: `mag/src/critic/metrics.rs` for the eXIf fix only.
    WP-5.3a's accepted code bails on ANY eXIf chunk and 010's cover art has
    one, so `decode_rgb` refused the very image WP-5.4 grades. Narrow the
    guard rather than delete it, and re-run WP-5.3a's FULL oracle (all 14
    images at three levels, plus the tint_band fixture and the rounding
    oracle) recording before and after, so an accepted verification is not
    silently invalidated. The general rule this instance produced is in the
    Phase 5 preamble.
  - **One method finding, and one retraction** (revision 24).
    RETRACTED: revision 23 recorded that a fill-only outline probe is not
    evidence about stroked elements, on the mechanism that `ttf-parser`'s
    redundant closing lineto before `Z` renders differently under stroke.
    WP-5.4's verifier MEASURED it (commit 06d5cf63) by reverting
    `Builder::close`'s lineto-pop: the SVG changed (4,234,729 against
    4,233,478 bytes) and the PNG was BYTE-IDENTICAL with the test still
    passing, and synthetic probes agreed across miter-sharp, round-cap and
    curve-close cases. The redundant lineto never reaches the raster at
    all. Do not carry the fill/stroke lesson forward; it was a mechanism
    asserted, not measured.
    STANDS: a transposed CONSTANT (the white wordmark tail's
    `horizontal_scale=105.1` with `stroke_width=0.30`, against the orange
    tail's 106.6 with 0.15) produced output that diffed clean on every
    transform and differed on 10,768 pixels in a bbox of 428,221 to
    967,326. That alone accounts for the whole difference, and it remains
    the strongest argument in this execution for raster EQUALITY as the
    cover oracle.
  - Note for WP-0.2h, measured here: `/F1` is reportlab's default
    Helvetica, set at the top of the stream and never shown, and by stream
    order it PRECEDES any `3 Tr`. WP-5.3d measured the tracer's failure
    empirically as the Helvetica decode, so that is the first stop and the
    render mode the second. WP-5.4 did not run the tracer itself and says
    so.

- **WP-5.4b cover modes and refusals**: owns `mag/tests/cover_*` fixtures
  and whatever `mag/src/cover/` needs to cover them. Depends on WP-5.4.
  Exists because of the corpus rule: 010 uses `footer_caption` ONLY, so
  `framed`, `honored_plate` and the unknown-mode refusal are unreachable
  from the live edition and must be fixtured. WP-5.4's evidence already
  enumerates the branches 010 cannot reach across 1620 lines, 56 functions
  and 24 raise sites, including the missing-glyph refusals, the
  contourless-glyph path, the art-analysis branch and the back-cover
  statement-fitting search; inherit that enumeration rather than
  re-deriving it. Split from WP-5.4 so the mode 010 actually ships does not
  wait on fixture work for modes it does not use, which is the same seam
  logic as the WP-5.5 re-cut. **WP-5.6 depends on WP-5.4 only; WP-6.1
  depends on WP-5.4b**, because deleting the Python must not delete a
  capability that nothing has yet proven.

- **WP-5.4g comparator switch (comparator WP)**: owns `mag/src/parity.rs`
  + `parity.yaml` + `baseline.json` cover-page seed rows: the compared
  artifact becomes `reader.pdf` end to end. Gated on WP-3.7 + WP-5.4.
- **WP-5.4c cover PDF assembly**: owns `mag/src/cover/pdf.rs`. Depends on
  WP-5.4 and WP-5.4b. **This WP exists because the cover PDF WRITER DOES
  NOT EXIST**, which WP-5.4's own `## What is and is not proven` recorded
  and WP-5.4b confirmed: `mag/src/cover/` contains no PDF module, so all
  three layouts are proven at SVG-AND-RASTER level only. Revision 21's
  guard, that the writer be written GENERALLY in WP-5.4 so WP-5.4b would
  add coverage rather than a second writer, could not be applied by
  WP-5.4b, because there was nothing to be general.
  The gap is precisely sized rather than alarming. PROVEN already: the
  resvg raster matches Python exactly in all three modes (`footer_caption`
  `4b4549e9...`, `framed` `ece03e91...`, `honored_plate` `c46b2db4...`),
  the outlines match across all 834 glyphs, the zone statistics match
  PIL's numbers, and the invisible text layer's content and placement are
  specified. MISSING is only the step that assembles those into a PDF, and
  WP-5.4's evidence already describes its shape: two path fills, one
  full-page Form XObject holding the raster, and the `3 Tr` layer.
  - Written for ALL THREE MODES at once, which is where revision 21's
    "generally, not per-mode" guard now attaches, using WP-5.4b's fixtures
    as its coverage.
  - **Oracle: the RENDERED RESULT, never the embedded stream bytes.**
    WP-5.4b deliberately does not compare SVGs between implementations
    because Rust and Python encode the graded-art PNG differently, the
    base64 diverging at char 448 while the rasters hash equal. The same
    reasoning governs the PDF: compare display lists and rasters, not the
    embedded streams. Tier E already does the right thing here, since the
    display list hashes DECODED RGBA pixels rather than the encoded bytes,
    so a different PNG encoding passes while a different picture fails.
  - Verify: display-list equality and raster EQUALITY (revision 21's bar)
    against Python's cover PDFs for all three modes.

- **WP-5.5 RE-CUT (revision 19) into WP-5.4a, WP-5.5a, WP-5.5b, WP-5.5c.**
  The original WP ended `blocked` with no code written (evidence
  `meta/verification/evidence/WP-5.5.md`) on four measured dependencies,
  three of which the graph did not express, and the re-cut follows the seam
  those dependencies actually create rather than the plan's old grouping.
  Notes that bind ALL of the successors:
  - **`mag/src/critic/metrics.rs` ALREADY EXISTS** (WP-5.3a) and is what
    the preflight port consumes: `image_contrast.py`'s metrics land in
    preflight.json, not render-critic.json. Do not re-port them, and do not
    move the module; it lives under `critic/` for the historical reason
    recorded at WP-5.3a.
  - `html_edition.py`'s interior-HTML role dies with the oracle; only the
    web path is ported.
  - The byte-identical `web/` oracle is sound because web HTML is
    byte-deterministic across renders, which WP-0.0c established with a
    third control render.
  - Archives compare per-entry (name order, mode, timestamp, CRC32,
    uncompressed bytes), never whole-file: zlib and flate2 streams differ
    legitimately.
  - WP-5.5's evidence already enumerates, per module, the branches edition
    010 cannot reach (the corpus rule). The successors inherit that
    enumeration and must not re-derive it.

- **WP-5.4a cover text helpers**: owns `mag/src/cover/text.rs` and its
  tests. Depends on WP-5.1c only. `web_edition.py:18` imports
  `_cover_contributors`, `_cover_date`, `cover_tab_identity` and
  `cover_tab_issue` from `cover.py`, and these are NOT the PDF compiler:
  they are four pure functions over `Edition` producing strings (an author
  roster upper-cased with a deck fallback, a re-spaced date, a tab string,
  a zero-padded issue label). The duplicated-helper rule forbids copying
  them and `mag/src/cover/` does not exist yet, so whoever arrived first
  would have had to invent the seam; the plan assigns it instead. Cut as
  its own WP rather than folded into WP-5.4 so the web path does not wait
  on the cover PDF compiler, which is much larger. Oracle: exact string
  equality against the Python functions over 010 and over fixtures
  exercising the deck fallback and the zero-padding. WP-5.4 and WP-5.5a
  both consume it.

- **WP-5.5a web** (`web_edition.py`, `html_edition.py`'s web path): owns
  `mag/src/web/`. Depends on WP-5.1a/5.1b/5.1c (html_edition imports
  manifest, media_schema, publication_document, reader_text) and on
  WP-5.4a (the cover text helpers above).
  - Oracle: byte-identical `web/` tree files for 010.
  - **The QR codes: DECIDED (revision 30), and the gate decides it, not
    taste.** The feared part is fine: `qrcodegen`'s `boost_ecl` reproduces
    segno's version AND effective error level on 9 of 9 payloads, with the
    L to M boost landing on exactly the 6 the plan recorded, and all nine
    are byte mode with seven carrying no digits, so mode segmentation is
    not a variable.
    The MATRICES are not reproducible, because **segno is wrong**:
    `segno/encoder.py:330` runs `buff.extend([0] * (8 - (length % 8)))`,
    appending EIGHT spurious zero bits when the stream already sits on a
    codeword boundary, where ISO/IEC 18004 section 7.4.10 adds none. Its
    own docstring quotes the clause directly above the line that violates
    it. In byte mode the post-terminator stream is `16 + n*8` bits, always
    congruent to 0 mod 8, so segno always injects an extra zero byte unless
    capacity forces the terminator to truncate; that displaces a pad
    codeword and changes every ECC codeword. Automatic encoding matches 1
    of 9, masks differ on 7 of 9, and forcing version, level and mask so
    only the data layer can vary still leaves 8 of 9 differing by 64 to 144
    modules.
    **The decision is (a): reproduce segno's non-ISO pad byte
    deliberately**, as one documented deviation asserted by its own test.
    It is FORCED by the gate rather than chosen. `weasyprint_adapter.py`
    also calls segno (`_fitted_source_code` at :1902 and
    `_source_code_matrix` at :1918, whose matrix `_source_code_source`
    draws into the reader), so the QR modules are inside Tier E's compared
    domain as ordinary marks. A different matrix is different path geometry
    and Tier E fails on it. So option (b), "same payload, version and
    effective level but NOT the same matrix", is unavailable for print
    without weakening Tier E, which rule 4 forbids any WP to do; and since
    print needs matrix equality regardless, applying (b) to the web tree
    alone would buy nothing while splitting the QR implementation in two.
    **On the "reproduce a hack" objection, which this plan has upheld four
    times: the asymmetry is real and it is why this case differs.** Those
    four governed output nobody inspects (pypdf's line merging, a crash's
    traceback, reportlab's subset bytes, pypdf's exact line breaking).
    This governs a VISIBLE artifact: a different matrix is a visibly
    different pattern of squares on a printed page, even though it scans to
    the same URL. Reproducing a deviation to keep a visible artifact
    identical is not the same act as reproducing one to keep an invisible
    intermediate identical.
    **The product question is real but is NOT a parity-phase decision.**
    Whether the magazine should ship spec-correct QR codes instead of
    segno-compatible ones is Fran's, and it has the exact shape of the
    hyphenation decision: parity reproduces the old behaviour, and the
    deliberate improvement is measured afterwards with its own before and
    after. It is therefore a named POST-FLIP item alongside WP-4.3, not a
    blocker here. Nothing waits on it.
    **Cite this as the reference application of rule 11**, because it is
    the best in the execution: the mechanism was not asserted but tested by
    controlled experiment (at forced v4-M a payload needing no pad
    codewords differs by 0 modules while one needing twelve differs by
    158, so removing the cause removes the effect), and then used to
    PREDICT three fresh cases not used to form it: `"a"x62` matched at 0
    modules, `"a"x61` and `"a"x60` differed at 68 and 82, correct in all
    three.
    Worth reporting upstream if Fran wants it filed: segno's pad-bit
    deviation affects any encoder compared against it.
  - **COST CORRECTION (revision 32), and it changes the route without
    changing the logic.** The deviation reproduces in three lines to
    DESCRIBE and not to IMPLEMENT: `qrcodegen` cannot be used as-is,
    because padding is internal to `encode_segments_advanced` with no hook,
    so reproducing segno's spurious pad byte means owning the bitstream,
    the Reed-Solomon ECC, mask selection and matrix layout. That is a QR
    implementation, not a patch. Revision 30's reasoning is untouched (the
    modules are inside Tier E's compared domain, so a different matrix
    fails the gate and option (b) would weaken Tier E), but the price was
    misstated and the decision deserves the real number.
    **Preferred route: treat the QR SVGs as committed ASSETS for the
    compared edition, and use a SPEC-CORRECT encoder for new work.** Both
    legs then read the same asset, so the matrices are identical and Tier E
    is satisfied without anyone reproducing a bug; future editions get
    spec-correct codes, which is the product improvement already named as
    Fran's post-flip item, and nothing has to own a bug-compatible
    encoder. Two facts this rests on are verified: the payload is a pure
    function of `source_url` (`manifest.py:1261`, scheme and `www.`
    stripped), and the PRINT error level is chosen by a fitting loop over
    available room (`weasyprint_adapter.py:1907`).
    **ASSET FORMAT, corrected by measurement (revision 33).** Revision 32
    said payload and level; that is not enough. There are exactly three
    segno call sites and the print path uses segno TWICE per code for
    different purposes: a SEARCH in `_fitted_source_code` (:1907) looping
    H, Q, M, L to pick the largest module, and a REDRAW in
    `_source_code_matrix` (:1920). Every search input is a constant (room
    55.5, quiet 4, min module 0.35 mm, epsilon 1e-9), so the fit is a pure
    function of the payload, and the asset must therefore record the
    payload, the chosen LEVEL, the MODULE COUNT and the matrix. Without
    `modules` the search has to re-run, and it feeds layout directly
    through `module = room / modules` and `side = quiet * module`.
    **The format also needs a PRINT-DECLINES state, and the boundary is 78
    characters, NOT 154** (corrected revision 37). The 154 figure traced
    `_opener_credit_code`, a MEASUREMENT path fixed at 55.5 pt; PRODUCTION
    is `_opener_source_codes` at 41.0 pt for illustrated openers, and all
    nine of 010's articles are illustrated. Above 78 the legs do not
    disagree about which code to draw: print draws NONE. Unless the format
    can say so, a future long URL reads as a missing asset rather than a
    correct outcome. 010's longest payload is 67 characters, so the
    compared edition is still safely inside, but the margin is ELEVEN
    characters rather than eighty-seven, which is close enough that a new
    source URL could cross it.
    **The 9-of-9 agreement survives and is now stronger than when the
    decision was taken.** The chosen error level and module count are
    proven ROOM-INDEPENDENT rather than merely observed on this corpus:
    499 payloads at six rooms, zero disagreements, against 387
    disagreements for a deliberately room-dependent control. So the asset
    decision rests on a property of the FIT rather than on a fact about
    edition 010, which is what makes it safe to carry forward.
    **And the 9-of-9 agreement is now EXPLAINED rather than observed**,
    which is what makes the decision safe rather than lucky: the fit
    maximises module size, which minimises version, and among ties keeps
    the earliest of H, Q, M, L because no tie exceeds epsilon. That is
    "smallest version, strongest level at that version", which is exactly
    segno's boost rule. When the decision was taken it had NOT been
    verified that both legs pick the same level AND version; it now is,
    with a mechanism (rule 11).
    Leg 1 remains: that both legs can be pointed at the asset. **Owns
    EXTENSION granted** for `src/magazine/web_edition.py` and
    `src/magazine/weasyprint_adapter.py`, the asset-reading change ONLY, as
    a sanctioned oracle change alongside WP-0.0b, WP-0.0c and WP-1.5, with
    the usual obligation, with the reader-PDF half CORRECTED (revision 37,
    and the error was the plan's): render 010 before and after, compare the
    WEB TREE byte-for-byte, and compare the reader PDF with
    `mag parity --pre-rendered`. **Byte-comparing reader PDFs is an
    instrument that cannot discriminate**, so the requirement as written
    was unsatisfiable by ANY change including no change at all: rendering
    the unchanged tree twice yields PDFs differing in 420,296 bytes,
    because cairo writes per-run image XObject names inside compressed
    streams. WP-5.5a reported that as a BROKEN INSTRUMENT rather than
    reporting a pass, which is rule 10 applied to a tool instead of to
    evidence, and is the behaviour the plan wants. Under the corrected
    instrument its change is identical everywhere: web tree byte-for-byte,
    68,530 glyph positions at 0.000000 pt, display list 0 pages differing,
    Tier V delta 0.
    Checked while fixing this, since the same defect would hide anywhere
    else it appeared: **no other clause in this plan rests on PDF-byte
    stability.** The parity ladder opens by stating that two engines never
    produce byte-identical PDFs, WP-0.0's verification recorded that PDF
    byte-determinism is not assumed, WP-0.1's whitelist already treats the
    PDF-byte hashes in render-critic.json as run-to-run noise, and
    WP-5.5c's SHA256SUMS oracle digests the SAME files from both
    implementations rather than comparing across renders. The plan was
    consistent; this one requirement was not.
  - **Owns EXTENSION, second**: `mag/src/render.rs` for a roughly 15-line
    `stage_source_codes` row. The renderer stages only DECLARED inputs
    (`engine_render_bridge.py:158`) and `source-codes` is not among 010's
    47 declared inputs, so the committed asset is INVISIBLE to the render
    without it. Recorded alongside the other sanctioned oracle changes, and
    flagged because `render.rs` is serialised by rule 1b and WP-5.6
    inherits it.
  - **A latent Python bug the port must NOT fix**: `_opener_credit_code`
    sizes the opener field floor from a symbol fitted at 55.5 pt which
    production then places at 41.0, so a payload between 79 and 154
    characters would expose the inconsistency. Revision 23's rule forbids a
    port stricter than its oracle, so this is REPRODUCED rather than
    corrected, and it is recorded here so nobody later reads it as a port
    defect. Fran may want it as a product matter, alongside the
    `studio.ready` field that can never report ready.
    `weasyprint_adapter.py` is a heavier target than those precedents,
    since Appendix A deletes it at WP-6.1 and the whole parity comparison
    runs through it, so the edit stays minimal and leaves the DRAWING path
    alone: `_source_code_source` draws from `code.module` and `code.side`
    as well as from the matrix.
    If either fails, fall back to (a) with the encoder scoped as its OWN
    WP, the segno deviation as a named requirement, and `qrcodegen`'s
    `boost_ecl` retained as an independent check on version and effective
    level, which it matched 9 of 9.
  - **PYGMENTS: decided on its own terms, NOT by analogy to the QR
    decision.** `html_edition.py:681`'s `_highlight_code` calls pygments
    with `HtmlFormatter(nowrap=True)`, so byte-identical web HTML would
    require reproducing its token markup, and 010 cannot reach the branch
    at all (zero `<pre>` blocks and zero pygments token classes across all
    eleven web files), so the corpus rule would demand a fixture and the
    fixture would demand reproducing a second Python library byte for byte.
    Revision 30 does NOT settle this and must not be cited as if it did:
    that turned on the QR modules being inside Tier E's COMPARED DOMAIN,
    and highlighted code is `<span class="...">` in the WEB TREE ONLY,
    which no ladder clause inspects. No gate forces reproduction here.
    **RE-DECIDED (revision 33), and the previous reasoning was wrong in
    both halves.** Revision 32 settled this by consistency with the print
    path and named `syntect` as the likely implementation. Measurement
    killed the second half: the FORMATTER is trivial,
    `<span class="...">escaped</span>` and nothing else, verified over all
    106 corpus blocks, while the LEXERS are the entire cost, 8,559 spans
    across 31 classes and nine languages including where they emit `err`,
    and **syntect would NOT have matched**. Checking rather than assuming
    then killed the first half too.
    **The print path is NOT a precedent for a weaker bar; it is a STRICTER
    requirement, and it is gate-forced.** `html_edition.py:660` emits
    `<pre><code>` through the same `_highlight_code`, so PRINT code blocks
    are pygments-highlighted as well, and `weasyprint-a5.css` colours those
    classes. Tier S's colour clause compares per-page (text-run, fill
    colour) sequences, so a different tokenisation yields different colours
    and **the gate fails**. Reproducing pygments' tokenisation is therefore
    forced for print in exactly the way the QR matrices were forced, and
    the analogy revision 32 drew to justify a weaker web bar had it
    backwards.
    **But the gate compares COLOURS, not class names, and that is a real
    relaxation rather than a concession.** The print CSS collapses the 31
    classes onto about seven distinct values, `inherit` among them. So the
    requirement is to reproduce pygments' tokenisation **up to the
    equivalence induced by the CSS colour map**, which is derived from what
    the clause actually says and may be far cheaper than 31-class
    fidelity. Whoever implements highlighting measures that equivalence
    first: the cost is set by the number of colour classes, not by the
    number of token classes.
    **The WEB bar is contingent and is not decided in the abstract.**
    Byte-identical web HTML needs the class NAMES, where print needs only
    the colours, so web is strictly harder. If the print-forced
    implementation reproduces classes exactly, web byte-identity comes free
    and nothing is declared. If it reaches only colour equivalence, the
    class attributes inside highlighted spans are a DECLARED and enumerated
    divergence, with the code TEXT byte-identical either way, since the
    text is the magazine's verbatim obligation and the colouring is
    presentation. Decide it when the implementation is measured, and record
    which way it went.
    None of this lands now: 010 carries no fenced code, so the cost arrives
    with WP-3.3's fixture edition, which the plan already requires.

  - **Sequencing: this is now the largest single piece left in Phase 5**,
    roughly 1,600 lines at a byte-identical bar (`render_html_edition`, ~45
    functions, then `web_edition.py`'s pipeline, ~30), and 010 exercises a
    narrow slice of it. Zero editorial, sections, extracts, key_ideas and
    fenced code, so `_render_editorial`, `_render_section`,
    `_render_extract`, `_extracts_by_anchor`, `_render_key_ideas` and
    `_highlight_code` are ALL corpus-unreachable and **the fixture surface
    will exceed the corpus surface**, which is the corpus rule at its most
    demanding. Build in landed increments rather than one pass.
  - Carries WP-0.0c's unfinished business: `_PRINT_ONLY_LINE`,
    `_SOURCE_LINK_LINE`, `_PIECE_OPENING`, and the repaired opener regex
    that still requires the class to be exactly `article-opener`. All four
    recognise markup by exact spelling and drop web content silently when
    an attribute is added, which is how nine source QRs vanished. Port
    them as STRUCTURAL tests, with fixtures carrying an extra unrelated
    attribute on a figure, a source link, a closing plate and an opener.

- **WP-5.5b preflight** (`preflight.py`): owns `mag/src/package/preflight.rs`.
  Finding for confirmation, and it is rule 10's family IN THE PRODUCT
  rather than in the evidence: `studio.ready` is reportedly UNREACHABLE for
  any input, because `studio_blockers` is seeded with the PDF/X-4 and bleed
  messages unconditionally and never emptied, so a field the pipeline
  reports can never take one of its values. A preflight result that is a
  CONSTANT dressed as a measurement. If the verifier confirms it in the
  Python, the PORT still reproduces it, since the Python is the
  specification and a port that is looser or stricter than its oracle is a
  defect either way; and it is flagged to Fran as a product bug, which is a
  separate question from whether the port is faithful.
  Depends on WP-5.2 (`preflight.py:8` takes `A4_LANDSCAPE_POINTS` and
  `section_reader_pages` from `booklet.py`, and `section_reader_pages`
  decides `reader_pages` and `expected_sheets`, both preflight.json fields
  inside this WP's own oracle) and on WP-5.3a (`image_contrast`). The
  smallest of the three and runnable the moment WP-5.2 lands. Oracle:
  preflight.json equality on 010.

- **WP-5.5c package and SHA256SUMS** (`package.py`): owns
  `mag/src/package/`. Depends on WP-5.2 (`impose_a5_on_a4` at :11) and
  WP-5.3b (`inspect_render` at :14), plus WP-5.5b. `package_release`
  imposes three times and writes render-critic.json BEFORE preflight.json,
  and SHA256SUMS digests all of it plus the critic's contact sheets, so
  ORDER is part of the oracle, not an implementation detail. Oracle:
  SHA256SUMS, printing instructions and edition-manifest.json byte-equal
  for 010, archives per-entry.
  Do NOT land `package.py`'s portable leaves (`sha256`,
  `_adopt_rendered_layout`, `_printing_instructions`, `_studio_note`) ahead
  of their callees. WP-5.5 explicitly declined to, on the ground that a
  half-orchestrator is how stale copies start, which is the
  duplicated-helper rule applied with judgment rather than by rote.

- **WP-5.6 native render_edition**: owns `mag/src/render.rs`,
  `mag/src/typeset/**` glue (serial per rule 1b; after WP-3.7). Depends:
  WP-2.3, WP-3.7, WP-5.2, WP-5.3b, WP-5.4, WP-5.5a, WP-5.5b, WP-5.5c.
  Target: `--engine
  typst` runs cover, critic, package, web natively; no bridge spawn.
  Verify: bridge outputs pre-generated; with `uv` removed from PATH, render
  010 `--engine typst` and `mag parity 010 --pre-rendered` against the
  bridge outputs: Tier E green, package/web oracles green.
- **WP-5.7 capture's PDF transcription** (`tools/pdf2md.py`): SUPERSEDED by
  WP-5.7a and WP-5.7b below. The original WP asked for byte-identical
  markdown against `pdf2md.py` on three captured-PDF fixtures, and it
  ended `blocked` having established the one thing it was told to check
  first: `pdf2md.py` IS deterministic (three runs byte-identical at both
  the markdown and raw-extraction level, the wrapper provably pure, scoped
  to pypdf 6.14.2 which nothing pins). It blocked on two findings the plan
  had not anticipated, both of which stand up:
  1. byte-identity is a LIBRARY port, not a script port: a real extraction
     drives 90 pypdf functions across 12 modules, and while `lopdf` covers
     the object model, reader and filters, the text layer is 1701 lines
     over four modules plus 18452 lines of data tables. What would be
     reproduced is pypdf's HEURISTICS, not the PDF specification:
     `crlf_space_check` breaks a line at `0.8 * min(...)`, `_handle_tf`
     sets the space width to HALF a space and says so in a comment, and TJ
     is never treated as an operator, being decomposed into synthetic `Tj`
     calls that inject a space when `abs(op) >= _space_width * 0.95`. Since
     `pdf2md.py` derives paragraphs from `splitlines()`, any one of those
     shifting a break shifts the markdown: it is all or nothing.
  2. the oracle's three fixtures do not exist. The repository holds exactly
     ONE real captured PDF and no `library/sources` record carries a `.pdf`
     URL, so two of three would be synthetic and authored by the same agent
     that chose which paths to implement. That is the masked-defect pattern
     which has already produced two rejections in this execution.

  **Decision (revision 12): re-scope the oracle from byte-identity to
  transcription fidelity.** The reasoning, because this is the one place
  the plan deliberately changes what "the same" means:
  - Byte-identity here anchors on an arbitrary choice. pypdf is one
    extractor among several, and the specific numbers that would have to be
    reproduced are self-described hacks. Reproducing a hack to stay
    byte-equal to a tool being deleted is the same category as porting a
    crash, which revision 11 already ruled is not fidelity.
  - Nothing is being regenerated. Every article.md captured so far is
    committed and is NEVER re-derived, so byte-identity could only ever
    govern FUTURE captures, where there is no prior artifact to match. It
    is a counterfactual, not a regression check. Existing sources keep
    their text exactly as captured; this decision changes no committed
    article.md, which the verbatim rule in `CLAUDE.md` requires.
  - What the pipeline actually needs IS testable, and more directly:
    article.md must be the source's substantive text verbatim.
  This is a narrowing of scope only where the old criterion was arbitrary;
  it is not permission to accept worse transcription. If no available Rust
  extractor can meet the quality checks below, the fallback is the faithful
  port of pypdf's text layer as 2 to 3 WPs, and that is a plan revision.
  Keeping `pdf2md.py` as a Python exception is rejected: it strands an
  entire toolchain in the pipeline for one script and defeats WP-6.1.

- **WP-5.7a the PDF fixture corpus and the fidelity spec** (evidence and
  fixtures only; owns `mag/tests/pdf_fixtures/` and its evidence). Exists
  BEFORE any extractor is chosen, and is authored by someone other than
  WP-5.7b's implementer, because implementer-authored fixtures have now
  failed twice.
  - Target: at least five REAL PDFs, captured from the wild rather than
    synthesized, spanning the shapes capture actually meets (a
    multi-column paper, a report with tables, one with code blocks, one
    with ligature-heavy body text, the existing 51-page /Type1 sample).
    For each, ground truth for the passages that matter, established by
    DISAGREEMENT REVIEW rather than by assertion: run two independent
    extractors, and wherever they differ, record which is right and why.
    Agreement is evidence; disagreement is where the work is.
  - Target: the fidelity checks, as machine-decidable assertions, at
    minimum: a line-end hyphen is never silently deleted (poppler 25.08.0
    WELDS them, turning `input-\nheavy` into `inputheavy` and
    `DeepSeek-V4.1-\nFlash` into `DeepSeek-V4.1Flash`, which is word
    corruption in a file the magazine treats as verbatim); real hyphens
    survive; reading order matches the ground truth; fenced code survives
    intact; no text dropped and none duplicated.
  - Verify: the checks run against BOTH pypdf's output and poppler's on
    all five fixtures, and the results are recorded. Neither is required
    to pass. The point is to prove the checks discriminate before anything
    is built against them.

- **WP-5.7b the Rust transcription** (owns `mag/src/pdf_text.rs`,
  `mag/src/capture.rs`'s `uv run` call site). Depends on WP-5.7a.
  - Target: extraction in Rust passing every WP-5.7a check on every
    fixture, with anything unhandled (encrypted, no `/ToUnicode`, CID
    fonts without a usable mapping) failing loud rather than guessing. The
    extractor library is chosen on measured fidelity and recorded.
  - Verify: the WP-5.7a checks green, plus the determinism property the
    original WP established, three runs byte-identical. Record the pypdf
    diff on the real fixture as an observation, not a pass condition: it
    says where the two disagree, which is useful, and proves nothing about
    which is right.

## Phase 4: the gate, the flip, and the hyphenation proof

### WP-4.1 full parity gate (mechanical)

- Owns: evidence only.
- Depends: WP-3.7, WP-5.3g, WP-5.4g.
- Target: `mag parity 010` green at Tier E (all clauses, critic on both
  sides, reader.pdf end to end), run twice from a clean checkout with
  byte-identical verdicts. That exit code is the gate; no human approves
  sameness.

### WP-4.0g ad hoc parity mode (comparator WP)

- Owns: `mag/src/parity.rs`.
- Target: `mag parity --adhoc <NNN> --run <dir>` for any other edition:
  render both engines fresh (`--no-model`; pending anchors resolved via
  the normal pipeline first), evaluate Tier S, report Tier E and G/V
  informationally, no baseline.
- Verify: `--adhoc 010` agrees with `mag parity 010` clause for clause.

### WP-4.2 the flip

- Owns: `magazine.toml`, `CLAUDE.md` (pipeline paragraph), `docs/`
  (transition record superseding `docs/RENDERER_MIGRATION.md`, which still
  describes the deleted TypeScript engine), evidence.
- Gate: WP-4.1's verdict digests in its evidence file.
- Target: `[render] engine = "typst"` default; `weasyprint` stays
  selectable as the rollback exactly as `reportlab` did last migration;
  docs describe the actual pipeline.
- Verify: render 010 and the newest in-flight edition end to end with the
  new default; critic passes; `mag parity --adhoc` on the in-flight
  edition: Tier S must pass, Tier E reported; a template gap it exposes
  blocks the flip until fixed and re-gated.

### WP-4.3 post-flip hyphenation change (MANDATORY)

- Owns: `mag/src/typeset/**` (enable native hyphenation),
  `src/magazine/assets/weasyprint-a5.css` (revert WP-1.5's `:lang(en)`
  switch if WeasyPrint still exists at this point), evidence.
- Why mandatory: WP-1.3 chose option (b), so the whole parity proof runs
  against a configuration the magazine does not ship. This WP is where the
  shipping configuration gets measured. Skipping it would leave the flip
  resting on a claim about a setting nobody uses.
- Target: quantify the deliberate divergence: native-hyphenation render vs
  the parity render, page counts equal, zero cap violations, changed line
  breaks counted. Report the es figures too, since WP-1.5 scoped its switch
  to `:lang(en)` and Spanish never lost hyphenation. This is a design
  change, so it ends `awaiting-fran`: a product decision, not a sameness
  verification.

## Phase 6: decommission

### WP-6.1 delete Python

- Gate: one real edition shipped on the Typst engine (rust-rewrite.md's
  rule: a released edition, not tests). Deleting WeasyPrint deletes the
  rollback AND the ability to re-render pre-010 editions byte-faithfully;
  both are Fran's call, recorded.
- Owns: deletion of `src/magazine/`, `pyproject.toml`, `uv.lock`, ruff
  config; font relocation to `mag/assets/fonts/` (byte-identical, checked);
  `.githooks` update (drop the ruff steps AND the direct
  `python3 tools/nocomments.py` invocation); the no-comments check ported
  into `cargo test` natively; `tools/*.py` disposition per Appendix A,
  each keep/delete confirmed by Fran; `CLAUDE.md`, `docs/`, and deletion of
  the `meta/verification/` scaffolding (history keeps it); a final
  transition record.
- **Unfreeze the Unicode tables, or decide not to.** Phase 5 ports pin
  case operations to Python's Unicode 15.0.0 tables because Python is the
  oracle. Once it is deleted the right behaviour becomes whatever Rust's
  std does, and the pin becomes a frozen copy of a dead dependency's
  tables. Decide explicitly: unpin and accept std's Unicode version, or
  keep the pin and say why. Either is defensible; inheriting it silently is
  not, which is the only outcome this clause exists to prevent.
- **Translation oracle, run before deletion because it cannot be run
  after.** WP-5.1c ported `load_translation` in full (41 of
  `manifest.py`'s 87 raise sites live there), broader than English-only
  parity required and the right instinct, since a partial port of a module
  about to be deleted would break Spanish editions silently. It does leave
  the Rust loader supporting a path parity never exercises. So while both
  implementations still exist: load a translated edition through BOTH
  loaders and compare the loaded structure and every refusal message, and
  render one es edition end to end on the Typst engine. Deletion is the
  moment the oracle stops existing, so this is possible exactly once. A
  mismatch blocks the deletion.
- Target: `git grep -lE "uv run|mag-render-adapter|weasyprint"` over
  tracked files hits only docs history and this plan; `mag render`,
  `mag capture` (including a PDF source), `cargo test`, and a full render
  of the shipped edition pass with no Python toolchain configured for this
  repo.

## Dependency graph (authoritative over section order)

```
DONE: WP-0.0 -> WP-0.0b -> WP-0.1 -> WP-0.2a -> WP-0.2b -> WP-0.2c
DONE: WP-1.1, WP-1.2, WP-1.3, WP-1.4 (spikes; decisions in revision 9)
DONE: WP-5.1a
WP-0.2e -> WP-0.2f (blocked, raster withdrawn) -> WP-0.2h -> WP-0.2j
       -> WP-0.2i
       -> WP-0.2g -> WP-0.2d matrix re-derivation
WP-0.2h -> WP-5.3b   (the critic's text source)
WP-0.2h -> WP-5.4g   (cover pages enter the compared domain there)
                                       (serial: rule 1c, and the matrix
                                        depends on all three)
WP-2.0b is ALSO serial with WP-0.2e/f/g (rule 1c, all own mag/src/parity*),
which the parallel presentation below otherwise hides
WP-0.0c (independent, owns html_edition.py alone) -> WP-2.3
WP-1.5 -> WP-2.0a                      (decision recorded, no Fran gate left)
WP-2.0a -> WP-2.0b
(010 content-final, Fran-recorded) -> WP-3.1   (revision 12: was WP-2.0a;
   Phase 2 is same-run throughout, the ratchet starts at WP-3.1)
WP-5.1a -> WP-5.1b -> WP-5.1c
WP-5.1c + WP-2.0b -> WP-2.1 -> WP-2.2a -> WP-2.2b -> WP-2.2c -> WP-2.3
WP-1.6 (done) -> WP-1.7 (evidence only) -> WP-2.2a (cites its interval)
WP-1.8 (evidence only, runnable now, blocks nothing)
WP-0.2k -> WP-3.1   (the ratchet must exist before Phase 3 can be verified)
WP-2.3 + WP-1.7 -> WP-3.1 -> WP-3.2 -> WP-3.3 -> WP-3.4 -> WP-3.5
WP-3.5 + WP-0.2i -> WP-3.0g -> WP-3.7          (the ratchet cannot be
                                                raised to Tier E before the
                                                per-glyph bound exists)
WP-5.2, WP-5.3a, WP-5.7                        (parallel with Phase 2/3)
WP-5.3a -> WP-5.3b-ii;  WP-5.3b-iii -> WP-5.3c -> WP-5.3g
WP-5.1c -> WP-5.4;  WP-3.7 + WP-5.4 -> WP-5.4g
Phase 5 edges below are RECONCILED AGAINST THE PYTHON IMPORT GRAPH
(revision 19), not against the plan's groupings; three were undeclared
until a WP walked into each one:
  WP-5.1c                       -> WP-5.4a -> WP-5.4 -> WP-5.4b -> WP-5.4c
  WP-5.1d + WP-5.4a             -> WP-5.1e   (lift helpers, widen audit)
  WP-5.4a                       -> WP-5.5a
  WP-5.1a + WP-5.1b + WP-5.1c   -> WP-5.5a   (html_edition imports manifest,
                                              media_schema,
                                              publication_document,
                                              reader_text)
  WP-5.2 + WP-5.3a              -> WP-5.5b   (preflight imports booklet,
                                              image_contrast)
  WP-5.2 + WP-5.3b-iii + WP-5.5b -> WP-5.5c   (package imports booklet,
                                              preflight, render_critic)
  WP-2.0b (pub use export)      -> WP-5.3b-i -> WP-5.3b-ii -> WP-5.3b-iii
  WP-5.2 + WP-0.2h              -> WP-5.3b-iii   (render_critic imports
                                                 booklet, concurrency;
                                                 cover_spread_checks needs
                                                 the cover pages)
  WP-0.2h                       -> WP-5.3b, WP-5.4g
WP-2.3 + WP-3.7 + WP-5.2 + WP-5.3b + WP-5.4c + WP-5.5a + WP-5.5b
       + WP-5.5c -> WP-5.6
WP-3.7 + WP-5.3g + WP-5.4g -> WP-4.1 -> WP-4.2
WP-3.7 -> WP-4.0g -> WP-4.2
WP-5.6 -> WP-4.2
WP-4.2 -> WP-4.3 (MANDATORY, WP-1.3 chose (b)) -> shipped edition
       -> WP-6.1 (Fran gate)
WP-5.7 -> WP-6.1;  WP-5.4b -> WP-6.1   (modes 010 never exercises)
Serialization overrides (rule 1): typeset/render.rs owners pairwise
serial; mag/src/parity* owners pairwise serial. Cargo-file owners are NOT
serialized (revision 18); rule 1a governs them instead, so Phase 5 WPs run
in parallel up to their real dependencies.
```

## Risks

- **rustybuzz/Pango disagreement**: measured by WP-1.1 before engine code
  existed. Glyph sequences agree exactly; the residual is Pango's own
  advance rounding, 0.0174 pt on letter-spaced headlines and 0.009897 pt at
  normal spacing.
- **Attributing a divergence to the nearest measured number**: WP-1.2's
  break miss was assigned to that residual, which its own figures rule out;
  then WP-1.6 explained away the gap to WP-1.1's number with a
  methodological difference that does not exist, when the real cause was
  hyphenation on versus off. Twice is a pattern, so it is now protocol
  rule 9: a number quoted from another WP carries the configuration it was
  measured under, or it is not quotable.
- **The raster guard measuring the rasterizer instead of the engines**:
  this already happened (WP-0.2d, 241/255 from FreeType grid-fitting) and
  is why WP-0.2f derives its bound under a two-sided constraint. The
  failure mode to watch for in WP-0.2f is a configuration that satisfies
  the floor by blurring away real differences; the ceiling measurement is
  exactly the check against that.
- **A gate that cannot fail**: the opener-fit clause was vacuous ({} vs {})
  until WP-0.0c, WP-0.2d's V-meter assertions were dead code until its
  rework, and the navigation clause compares empty outlines and absent
  Title/Lang on 010. All three were caught by a verifier or a critic, never
  by the authoring WP. WP-0.2g makes every collection clause report the
  cardinality it compared, so the artifact stops saying `pass` where
  nothing was checked.
- **Trusting an enumeration because it is written down**: revision 9 stated
  the display list's blind spots as one item and missed glyph identity, the
  only blind spot this project has actually observed between the engines
  (WP-1.1's ligature). WP-0.2f would then have derived its ceiling from an
  incomplete fixture set, repeating the mistake that produced the 241. The
  enumeration in Tier E is now exhaustive and each item names what covers
  it; anything added to the display list later must be checked against it.
- **Typst crate churn**: pinned; upgrades are their own WP with a full
  parity rerun.
- **The 3,000-line adapter encodes behavior nobody remembers**: the
  WP-2.2 mapping tables and WP-3.7's display-list residual ledger force it
  into the open.
- **Gaming**: rules 1, 3, 4, 6; verdicts byte-deterministic and rerun by a
  verifier from a clean worktree; the Tier E definition can only be changed
  by revising this plan.
- **Display-list extraction cost**: the Tier E instrument (WP-0.2b) is the
  largest comparator investment; the fixture suite in its Verify is what
  proves it trustworthy before anything depends on it.
- **010 doesn't exercise everything** (no editorial, no extracts, no
  fenced code blocks, one cover mode): deliberately accepted; fixtures
  gate the misses that matter (code/extracts in WP-3.3, cover modes in
  WP-5.4), the editorial path is out of scope (see Scope notes), and
  `--adhoc` gives a free cross-check on any other edition at any time.
- **010 is the live intake edition**: the staleness guard binds every
  verdict and baseline entry to its staged-input digest, and PHASE 3 waits
  for Fran's content-final record. Phase 2 proceeds against a moving
  corpus by design, since every comparison there is same-run.

## Non-goals

Typst-native typography improvements before the flip (except WP-4.3),
multi-edition frozen corpora, translation parity, CI infrastructure,
InDesign/Prince detours, keeping the reportlab engine (it dies in WP-6.1
with everything else Python), provenance ceremony (the small
`meta/verification/` scaffolding is temporary and dies in WP-6.1).

## Appendix A: Python disposition table

| File | Disposition |
|---|---|
| `src/magazine/manifest.py` | ported, WP-5.1c |
| `src/magazine/records.py` | ported, WP-5.1b |
| `src/magazine/media_schema.py` | ported, WP-5.1b |
| `src/magazine/document_structure.py` | ported, WP-5.1a |
| `src/magazine/publication_document.py` | ported, WP-5.1a (consumed by WP-2.1 via WP-5.1c) |
| `src/magazine/reader_text.py` | ported, WP-5.1a |
| `src/magazine/booklet.py` | ported, WP-5.2 |
| `src/magazine/render_critic.py` | ported, WP-5.3a/b/c |
| `src/magazine/image_contrast.py` | ported, WP-5.3a (into `mag/src/critic/metrics.rs`, though its consumer is preflight, so WP-5.5b is what uses it; not used by the critic at all) |
| `src/magazine/concurrency.py` | absorbed (rayon or std), WP-5.3a |
| `src/magazine/cover.py` | ported, WP-5.4 (footer_caption) + WP-5.4b (other modes, refusals); text helpers WP-5.4a |
| `src/magazine/preflight.py` | ported, WP-5.5b |
| `src/magazine/package.py` | ported, WP-5.5c |
| `src/magazine/web_edition.py` | ported, WP-5.5a (cover text helpers via WP-5.4a) |
| `src/magazine/html_edition.py` | web path ported WP-5.5a; interior-HTML path dies with the oracle |
| `src/magazine/weasyprint_adapter.py` | replaced by `mag/src/typeset/`; deleted WP-6.1 |
| `src/magazine/render.py` (reportlab engine) | deleted WP-6.1, never ported |
| `src/magazine/render_engine.py` | superseded by Rust dispatch (WP-2.0a); deleted WP-6.1 |
| `src/magazine/engine_render_bridge.py` | deleted WP-6.1 |
| `src/magazine/reader_layout.py` | shape ported as the layout JSON (WP-2.3); deleted WP-6.1 |
| `src/magazine/errors.py`, `io.py`, `__init__.py` | die with the package, WP-6.1 |
| `tools/pdf2md.py` | ported, WP-5.7 |
| `tools/nocomments.py` | check ported into `cargo test`, WP-6.1 |
| `tools/capture.py`, `tools/compare.py`, `tools/coverproof.py`, `tools/letter.py`, `tools/read.py` | side tools: keep/port/delete by Fran in WP-6.1; none is pipeline-load-bearing |
| `art-directions/experiments/vignette-wilted-sprout/wordless/letter.py` | experiment artifact: keep/delete by Fran in WP-6.1 |
