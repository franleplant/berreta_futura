# WP-5.3d verification

Worker commit `2bc3900`, evidence `meta/verification/evidence/WP-5.3d.md`.
Verifier base `53d8b60`.

## Scope and downgrade

The spike instrumentation was uncommitted and removed at WP end, so per the
Phase 1 preamble this is an **evidence-consistency audit**, not a replay.
Audited harder than a pure measurement because the output decides a plan
clause: it is the basis for moving WP-5.3b's oracle to decisions and for
making the display-list tracer the critic's text source.

## Verdict: REJECTED

Narrowly, and not on the decision. **Path B is correct and well supported**:
path A's criterion was fixed in advance, the tracer fails it on three
independent grounds, and the failures are measured rather than asserted. I am
not disputing the recommendation's direction.

The rejection is on the claim that carries recommendation 3, and on a residual
that is recorded without its consequence.

## Finding 1, material: the text-derived decision surface is understated

The evidence states that `article-stub-last-page` is "the only text-derived
decision boundary in the critic", and recommendation 3 scopes WP-5.3c to
"near-threshold cases on both sides of that one threshold".

`body_text_lines < 5` is indeed the only numeric **threshold** on a text-derived
count (`STUB_BODY_LINE_MINIMUM = 5` at `render_critic.py:62`, so the `< 5` is
right). But **five** text-derived fields feed **ten** issue sites:

| field | sites | issue codes |
|---|---|---|
| `text_order_matches` | :152, :176, :198 | `booklet-page-order`, `interior-booklet-page-order`, `cover-booklet-page-order` |
| `blank` | :291, :452, :476 | `inside-cover-reader-not-blank`, `inside-cover-booklet-not-blank`, `cover-booklet-inside-not-blank` |
| `ink_free` | :299, :460, :484 | `blank-page`, `blank-booklet-side`, `blank-cover-booklet-side` |
| `standalone_punctuation_lines` | :309 | `orphan-punctuation` |
| `body_text_lines` | :380 | `article-stub-last-page` |

`blank` (`:1008`) and `ink_free` (`:1009`) are conjunctions that include
`not text.strip()`, so both are partly text-derived; `sparse` (`:1010`) is
ink-ratio only and is correctly excluded.

Why this is material rather than pedantic: path B's whole premise is that the
**fault suite carries the weight** instead of 010's agreement. A WP-5.3c
briefed from recommendation 3 as written would build faults for one threshold
and leave four fields with no fault coverage. The under-scoping is caused by
the overstated claim, which is the same defect family this execution has
already rejected twice (WP-5.3a's blanket coverage claim, WP-5.1c's).

The substance survives: WP-5.3b measured `standalone_punctuation_lines` and
text-emptiness differing on 0 of 56 pages, and this spike measures
`text_order_matches` at 27 of 27. So no decision is known to flip. That is the
argument the evidence should make, and it is a different argument from "there
is only one".

## Finding 2, material: the cover residual disables a specific issue

The evidence records that the tracer cannot read reader pages 1 and 56
(`font Helvetica lacks ToUnicode`) and says WP-5.3b "needs a named decision".
It does not connect that to the decision it actually disables.

`cover_spread_checks` (`:184`) is computed from `cover_booklet_texts` and
`reader_texts` over `cover_wrap_plan(page_count)`, which is exactly the wrap
carrying reader pages 1 and 56. So under a tracer-fed critic,
`cover-booklet-page-order` cannot be computed at all, and the evidence's own
"side 1 is untraceable because it carries reader pages 56 and 1" is the same
fact seen from the other end without the inference being drawn. An issue code
that cannot be evaluated is not a near-threshold worry; it is a missing check.

## Finding 3, forward gap the evidence does not notice

The cover residual reaches beyond the critic. The Tier E compared domain is
today pages 2..n-1, which excludes the covers; **WP-5.4g makes `reader.pdf`
compared end to end**, at which point the cover pages enter the compared domain
and the tracer that fails loud on them becomes a gap in the gate itself, not
only in the critic. The evidence says the residual "binds whichever path is
taken" but scopes it to WP-5.3b. Whoever owns the standard-14
StandardEncoding/WinAnsiEncoding fix (or WP-5.4's port emitting a `ToUnicode`)
should know it is on the gate's critical path, not just the critic's.

## Checks that passed

**Owns**: `2bc3900` touches only `meta/verification/evidence/WP-5.3d.md`. No
tracked source, no `*.verify.md`, no `baseline.json`; the working tree carried
nothing of the spike's.

**Single-cause claim: shows all seven, does not generalise from one.** The
table names each divergent page with the merged line pypdf emits, every page is
an article opener, and each merge is visible as a missing space at the join.
Every row is internally consistent (tracer exactly one more line than pypdf in
all seven). The geometric counter-evidence is given for page 4 (two shows at
30011 and 27131, a 28.8 pt leading).

**Denominators: fairly stated.** The tracer's 47/54 and 7/54 exclude the two
untraceable covers while poppler's 16/56 and 9/56 do not, so the pairs are not
like-for-like. The table discloses this in its own fourth row ("0 of 2,
untraceable") and the Commands section states 54 traceable interior pages up
front. Counting the covers as tracer failures gives 47/56 against poppler's
16/56, so the conclusion is unaffected in direction or magnitude. Poppler's
16/56 also reconciles with WP-5.3b's independently reported 40/56 divergences.

**Reproducibility: adequate, thin in one place.** The pypdf oracle is a full
inline invocation and reruns as written. The probe is described by its `#[path]`
module shape, its env-var interface and the fields it writes, rather than given
verbatim, so a rerun means reconstructing roughly twenty lines; the crux, the
line-grouping and join rule, is stated explicitly in Metrics. Sufficient, but a
verbatim probe would have been better.

**Self-caution is right, and the corrected rule has a bounded failure mode.**
The empty-string join welding `BERRETA FUTURA04objects` across a page boundary
is a real trap and correctly recorded. The corrected rule (join shows with a
space, sound because `normalized()` at `:113` collapses whitespace) has the
mirror failure: a single word split across two shows gains a spurious space,
which `normalized()` cannot remove because the comparison is `actual ==
expected` on normalized text. The evidence's own `text_characters` finding shows
within-line shows do sit adjacent without spaces (`BERRETA FUTURA04`), so the
mode is reachable in principle; it did not fire here (27 of 27). Worth a line in
the re-cut brief, not a defect.

## Remedy

Small, and all in the evidence:

1. Replace "the only text-derived decision boundary" with the accurate
   statement: one numeric threshold, five text-derived fields, ten issue sites,
   and the measured argument that none is known to flip (0 of 56 on
   `standalone_punctuation_lines` and text-emptiness, 27 of 27 on
   `text_order_matches`).
2. Extend recommendation 3 so WP-5.3c's fault surface names all five fields,
   not just the one threshold.
3. Connect the cover residual to `cover-booklet-page-order`, which it disables.
4. Record finding 3: the same residual becomes a gate gap at WP-5.4g.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01E6ATvPwrSFQPyq3AtsB9bE
