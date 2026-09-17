# Typst parity and the full-Rust migration

Status: **in execution**, 2026-09-17, revision 32 (Phase 0 built and
verified, the Phase 1 spikes measured and audited, the gate critiqued
adversarially and repaired, the content-final gate narrowed to where it
bites). Companion to `rust-rewrite.md`
(which moved orchestration to Rust and left the renderer in Python). This
plan finishes the job: a Typst-based renderer implemented in Rust inside
`mag`, proven equivalent to the WeasyPrint renderer by rendering **edition
010 (en)** with both engines and comparing mechanically until they are
exactly the same, then porting every remaining Python module to Rust and
deleting `src/magazine/`.

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
other nine sites, measured at 0 of 56 divergences on
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
- V, from the same pinned rasterizer configuration the Tier E guard uses
  (WP-0.2f selects it; `pdftoppm -r 300` until then), hard fail on raster
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
    returns toward zero, so it fails on shape whatever its magnitude, and
    the ceiling stops depending on how large a fault is.
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
| Syntax highlighting (pygments vs syntect) | (text-run, fill color) sequences at the content-stream level (WP-3.3), never raster; 010 carries NO fenced code blocks or extracts, so WP-3.3 gates on a dedicated fixture edition, not vacuously on 010 |
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
   orchestrator before a verifier is spawned. **A PLAN REVISION owns
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
7. **Fran gates** exist only where the plan must change or something
   irreversible happens. Revision 9 resolves the Phase 1 gates (1.1's
   residual, 1.2's match rate, 1.3's mechanism) as plan decisions, so what
   remains is: a discovered repo anomaly or failed spike (0.1, 5.7), 010
   content-final before PHASE 3 (revision 12 moved it there from Phase 2),
   the post-flip typography change (4.3),
   tools disposition and rollback deletion (6.1), and any new `blocked`
   finding that needs the plan changed (as WP-0.2d's raster bound did).
   A gated WP
   ends `Status: awaiting-fran` with its recommendation; the decision is
   recorded by Fran (commit authored by Fran or a line Fran types). No
   verification gate is human.
12. **Demonstrate a capability THROUGH THE PATH ITS CONSUMER WILL USE.** A
   test harness that bypasses visibility, linkage or configuration proves
   only that the code RUNS, not that it is REACHABLE. WP-0.2h built a
   shared tracer seam for the critic and demonstrated it through a
   `#[path]` test include, which bypasses module privacy entirely; the
   demonstration worked and its verification confirmed the demonstration,
   while `mag/src/parity.rs` declares `mod display;` and `mod streams;`
   privately with no `pub use`, so the first real consumer in
   `mag/src/critic/` fails with `error[E0603]: module 'streams' is
   private`. **The mechanism that proved the seam was the one mechanism
   that routes around the defect.** This is its own failure mode, not rule
   10's claim outrunning evidence and not rule 11's untested mechanism: the
   evidence was accurate about what it measured, and what it measured was
   the wrong path. So a WP that ships something for another module to
   consume proves it with a CONSUMER TEST that imports the ordinary way,
   and a WP that reaches for `#[path]`, a relaxed visibility, a test-only
   feature flag or an altered search path says in evidence why, and what it
   therefore has NOT shown.
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
10. **Evidence that cannot discriminate must say so.** The plan already
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
  `raster_bound` moved to WP-0.2f in revision 9).
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

### WP-0.2f rasterizer selection and the raster bound (comparator WP)

- Owns: `mag/src/parity/raster.rs`, `meta/verification/parity.yaml`
  (`tiers.e.raster_bound` and the rasterizer entry under `tools:`).
- Target: select a rasterizer configuration and derive
  `tiers.e.raster_bound.value` under the two-sided constraint stated in
  Tier E, recording every measurement:
  - the **reachability floor**: the max per-channel delta over TWO
    fixtures, because the display list is blind to two different things
    and the floor has to cover both:
    (i) **coordinate quantization**, as Tier E defines it: coordinates
    moved to the EXTREMES of their own buckets in both directions (two
    deterministic runs, no seed), display-list equality asserted on both.
    WP-0.2d's `perturb.py` is the starting point and is replayable (at
    amplitude 0 it is provably inert), but it perturbs randomly within half
    a quantum and must be corrected to the bucket-extreme rule before its
    number means anything: its 241 is a floor on the floor.
    (iii) **transform-amplified displacement** (Tier E blind spot 5): a
    text run whose TRM LINEAR components differ by just under half a
    quantum over a full-measure line, display lists asserted equal. This
    term is the largest of the three on paper (0.1625 pt derived at body
    measure against 0.017432 pt for (ii)), so it may be what decides
    whether the 2x window is open. If it collapses the window that is
    `Status: blocked` and another revision, not a wider bound; the
    intended answer in that case is WP-0.2g's finer linear quantum, which
    removes the term rather than accommodating it, after which this
    fixture and the floor are re-derived.
    (ii) **intra-line glyph drift**, which revision 9 did not model at all:
    glyphs displaced progressively within each line up to the 0.017432 pt
    WP-1.6 measured between Pango's integer 1/1024 px line widths and
    Typst's exact font-unit sums. This is systematic and engine-intrinsic,
    not noise, and the display list cannot see it, so a floor derived
    without it would leave WP-0.2f discovering it later as an unexplained
    failure and blocking.
    Both fixtures are synthesized on the oracle leg, so WP-0.2f can run
    before a Typst render exists.
  - **re-derivation on the real pair**: the floor above is synthetic. Once
    a Typst leg exists, WP-3.0g re-derives it from the actual
    Typst-vs-WeasyPrint pair before raising the ratchet to Tier E, and
    fails loud if the real floor exceeds the synthetic one, which would
    mean a divergence nobody has enumerated. A synthetic floor is what lets
    Phase 0 finish; it is not what the gate finally rests on.
  - the **meaningfulness ceiling**: the smallest per-fixture MAX
    per-channel delta across the blind-spot fault fixtures, which after
    WP-0.2e are the items Tier E enumerates as raster-only: a TJ array
    whose kern numbers change but whose total advance is preserved (a
    non-compensating change is visible by other means, so it would not
    measure the blind spot), and an equal-count equal-advance glyph
    substitution if one can be built from the vendored faces. Measure the
    kern fixture at more than one magnitude: intra-show positioning is the
    guard's sole responsibility (Tier E item 1), so the interesting number
    is the SMALLEST kern shift the guard still catches, not the largest.
  - `value` = the floor, and the WP fails loud unless ceiling >= 2x floor.
  Candidates, in the order worth trying: MuPDF `mutool draw` (does not
  grid-fit; needs installing and pinning); `pdftoppm` supersampled and
  box-downsampled to 300 dpi, which bounds a grid-fit flip to a fraction of
  an output pixel and needs no new tool but costs time and disk; anything
  else that measures well. Record the wall-clock of a full parity run under
  the winner: a gate nobody can afford to run is not a gate.
- Verify: the floor and ceiling measurements are in evidence with the
  winning configuration named and pinned; 010 A-vs-A raster-equal and
  A-vs-B raster-equal under the derived bound; the Tier E raster clause
  stops reporting `not_evaluated`; the fixtures that define the ceiling all
  fail. If no candidate reaches the 2x margin, `Status: blocked` with every
  measurement recorded, and the plan is revised again rather than the bound
  widened.
- The fallback, written down now so a blocked WP-0.2f is a decision rather
  than a scramble: close the remaining display-list blind spots so the
  raster guard stops being load-bearing, then demote raster to meters. That
  means encoding intra-show glyph positions in the display list (Tier E
  item 1) alongside the glyph count already added. The catch that keeps
  this a fallback rather than the primary design: per-glyph positions at
  the 0.01 pt quantum would false-fail on letter-spaced headlines, where
  WP-1.1 measured 0.0174 pt of Pango rounding drift, so the encoding needs
  thought first. A per-show advance CHECKSUM at a coarser quantum, or
  positions quantized per-show relative to the show origin, are the two
  shapes worth costing before adopting either.

- OUTCOME: `blocked`, and the fallback above is what revision 15 adopts.
  Evidence `meta/verification/evidence/WP-0.2f.md` (commit 932f90e). The
  measurements are sound and must be CITED, never repeated: controls
  (kern_identity, drift_identity, trm_zero) all 0.000, every fixture's
  display-list equality checked with `mag parity` rather than assumed,
  winner `mutool draw` 1.26.4 at 8x supersampling, floor 30.125 against
  ceiling 30.125 (ratio 1.00), kern ceilings 30.125 / 60.250 / 90.375 /
  151.641 at 0.02 / 0.05 / 0.1 / 0.2 pt, and the linear-matrix term
  bracketing at 151.641 above every ceiling. The WP widened nothing,
  dropped no fixture, wrote no `value`, and left `raster.rs` untouched.
  Two limitations it recorded rather than hid: the bucket and TRM fixtures
  could not be built display-list-EQUAL through operand perturbation, and
  the conclusion does not depend on them, since they can only RAISE the
  floor. `mupdf 1.26.4` is installed on this machine but NOT pinned,
  because no configuration was selected.

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
  difference leaves page dimensions equal, so nothing else would catch it
  now that rasters are meters.
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
- Verify: the 010 MediaBox case reproduces exactly (authored decimals
  recovered, scale 1.0000000151 rather than 1.0); a PDF using object
  streams either parses or fails loud by name; WP-0.2i's per-glyph verdicts
  are byte-identical before and after, or the differences are enumerated
  with causes. The WP-0.2i verifier's answer on the f32 question lands in
  this WP's evidence either way: "checked, negligible, here are the
  numbers" is as valuable as a defect, and rule 11 applies, so the
  mechanism is measured rather than asserted.

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

### WP-2.2 the reader template (three serial slices)

Preamble (binds per rule 8): each slice owns `mag/src/typeset/template.rs`,
`mag/src/typeset/**` submodules it introduces, and `mag/assets/typeset/`;
serial; each extends its evidence mapping table: every transcribed value
cites its origin (`weasyprint-a5.css` selector or `weasyprint_adapter.py`
constant). Anything found-but-not-transcribed is listed as pending, never
dropped silently.

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

Preamble (binds per rule 8): **Phase 3 does not start until Fran has
recorded 010 content-final** (revision 12 moved that gate here from
WP-2.0a: this is where claims start accumulating across runs, and a moving
corpus makes a per-page ratchet meaningless). Strictly serial, this order.
Every Phase 3 WP except WP-3.0g owns `mag/src/typeset/**` plus its evidence
file and NOTHING else; comparator territory is out of bounds (rule 4). Each
WP is scored on its named `page_sets:` entry. Verification, identical for
all: `mag parity 010` green against `baseline.json` (no page regresses;
raises are the
verifier's), and the named page set at the named standard.

- **WP-3.1 body text** (`page_sets.body`): Tier S text+color + G2. Also
  carries WP-1.2's single break miss and WP-1.7's unreconciled 147/149
  versus 148/149 count: both must be resolved here or reported as real
  divergences, not inherited as folklore.
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
numbers. What generalises is therefore **a defect can be invisible to any
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
  five text-derived fields feeding ten issue sites, the `cover_spread_checks`
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
  DISCRIMINATES. `body_text_lines` 49 of 56. `text_characters` 16 of 56, up
  from 9 under the geometric join, and it feeds no issue site.
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

- **WP-5.3b-iii the checks**: owns `mag/src/critic/rules.rs`. Void
  geometry, tail bands, opener offset colour detection, crop fidelity, and
  the 31 issue sites. Depends on WP-5.3b-ii, WP-5.2 and WP-0.2h. This is
  the WP that meets the decision-level oracle, since only here does a full
  decision set exist to compare. WP-5.3c and WP-5.3g depend on it rather
  than on -i or -ii.

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
    ten issue sites, and `body_text_lines < 5` is merely the only numeric
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
    available room (`weasyprint_adapter.py:1907`), so the asset must record
    the chosen LEVEL and not merely the payload. Two are NOT verified and
    the WP proves them before committing to this: that both legs can be
    pointed at the asset (a sanctioned oracle change on the WP-0.0b
    pattern, which must render byte-identical since the asset is exactly
    what segno produces today), and that no other path regenerates a code.
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
    **Decision: compare highlighted code STRUCTURALLY, not byte for byte.**
    Same token boundaries and same class names, so the CSS colours it
    identically; the library's markup formatting is not reproduced. The
    plan already settled the analogous question for the PRINT path, where
    the divergence table compares pygments against syntect at the
    (text-run, fill colour) level and never at the markup level, so this is
    consistency rather than a new concession, and `syntect` is the likely
    implementation since WP-3.3 already contemplates it. The web-tree
    oracle is therefore restated as **byte-identical EXCEPT highlighted-code
    spans, which are structurally equal**, declared and enumerated in
    evidence rather than absorbed, with a fixture edition exercising the
    branch 010 cannot reach.
  - **The increment that landed validates revision 26's strong form**, and
    is worth recording because it caught the author's own errors. The four
    brittle matchers are ported STRUCTURALLY and pinned to PYTHON: over 10
    lines carrying an added attribute or class, Python fails to recognise 8
    while the port recognises 10, which closes the WP-0.0c defect class.
    Pinning to the oracle rather than to the author's reading then caught
    TWO of its own bugs: `source_link()` must EXCLUDE an already-installed
    `opener-source-link`, since its job is finding links that still need a
    QR, and `is_print_only()` must drop `source-link` only when
    `opener-source-link` is ABSENT. Exactly 18 `class="source-link
    opener-source-link"` survive into 010's shipped web tree, so a naive
    structural rewrite would have DELETED the QR links: the very defect
    this work exists to fix, inverted. That is what revision 26 means by
    pinning to the oracle rather than to a sibling or to one's own
    understanding.
    One detail worth keeping: the REORDERED-ATTRIBUTE case is WORSE than
    the unrecognised one, because Python classifies it as print-only and
    DELETES the link entirely rather than merely failing to upgrade it.
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
  WP-5.1c                       -> WP-5.4a -> WP-5.4 -> WP-5.4b
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
WP-2.3 + WP-3.7 + WP-5.2 + WP-5.3b + WP-5.4 + WP-5.5a + WP-5.5b
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
