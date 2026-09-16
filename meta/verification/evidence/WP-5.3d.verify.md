# WP-5.3d verification

Verdict: **ACCEPTED**, with one presentation finding recorded below.

Re-verification of the rework at `0b32501`. Rule 3 applies in its
evidence-consistency form (the Phase 1 spike downgrade): the probe code was
uncommitted and removed at WP end, so the tracer half of each measurement is
audited rather than replayed. That downgrade is stated here as the protocol
requires, and the limits of what it let me check are set out under
"What I verified directly".

## History

`2bc3900` was REJECTED at verify `6c24379`. The verdict itself, path B (the
critic oracle moves to the critic's decisions, with the display-list tracer
rather than poppler as the text source), was upheld as correct and well
supported and is not re-litigated here. The rejection was for one
load-bearing claim: "article-stub-last-page is the only text-derived decision
boundary", which is false. The claim had also propagated into plan revision
16 in three places; the planner corrected the plan in revision 17.

## Site count, counted independently

I counted from `src/magazine/render_critic.py` without reference to either
prior count, taking a "site" to be one `issue(...)` call whose guarding
condition reads a text-derived field, and requiring each to emit a distinct
code string.

| field | sites | codes |
|---|---|---|
| `text_order_matches` | `:152`, `:176`, `:198` | `booklet-page-order`, `interior-booklet-page-order`, `cover-booklet-page-order` |
| `blank` | `:291`, `:452`, `:476` | `inside-cover-reader-not-blank`, `inside-cover-booklet-not-blank`, `cover-booklet-inside-not-blank` |
| `ink_free` | `:299`, `:460`, `:484` | `blank-page`, `blank-booklet-side`, `blank-cover-booklet-side` |
| `standalone_punctuation_lines` | `:309` | `orphan-punctuation` |
| `body_text_lines` | `:380` | `article-stub-last-page` |

**Eleven sites, eleven distinct codes.** This matches the rework and not the
rejecting verifier's ten; the third reading breaks the tie in the rework's
favour. `sparse` is ink-ratio only and is correctly excluded. `blank` and
`ink_free` are conjunctions whose text half is `not text.strip()` and whose
raster halves (`pure_white`, `ink_pixels == 0`) do not depend on the text
source.

`STUB_BODY_LINE_MINIMUM = 5` at `:62` is confirmed as the only numeric
threshold over a text-derived field. `standalone_punctuation_lines` is a list
tested for truthiness at `:309`, an empty/non-empty boundary rather than a
tunable numeric one, so the distinction the evidence draws is right.

## `text_characters` drives no issue: CONFIRMED

`grep -rn "text_characters" src/magazine/ mag/src/` returns exactly one hit,
`render_critic.py:1007`, its definition. Nothing consumes it in either the
Python package or the Rust tree. The field with the spike's worst agreement
(7 of 54) therefore feeds no decision, which materially strengthens path B.

## `cover_wrap_plan(56)`: CONFIRMED

    uv run python -c 'from magazine.booklet import cover_wrap_plan; print(cover_wrap_plan(56))'
    ((56, 1),)

Exactly the two pages the tracer cannot read. So `cover-booklet-page-order`
(`:198`, guarded on `cover_spread_checks`, which `:184` computes over
`cover_wrap_plan`) is **not computable at all** under a tracer-fed critic,
rather than computed differently. The evidence draws this correctly, and
records the forward consequence: WP-5.4g brings the same two pages into the
Tier E compared domain, so a tracer that fails loud on them is a gap in the
gate and not only in the critic, with WP-0.2h referenced as the prerequisite
rather than a fix re-proposed.

## What I verified directly

I reproduced the **pypdf half** of both new measurements from the same tree
the spike used (`editions/010/render-2026-09-14T01-47-59/en/reader.pdf`),
using `_STANDALONE_PUNCTUATION` imported from the module under test rather
than a reimplementation:

    uv run python -c '
    import sys; sys.path.insert(0,"src")
    from magazine.render_critic import _STANDALONE_PUNCTUATION
    from pypdf import PdfReader
    r=PdfReader("editions/010/render-2026-09-14T01-47-59/en/reader.pdf")
    empty=[]; punct={}
    for n in range(2,56):
        t=r.pages[n-1].extract_text() or ""
        if not t.strip(): empty.append(n)
        p=[l.strip() for l in t.splitlines() if _STANDALONE_PUNCTUATION.fullmatch(l.strip())]
        if p: punct[n]=p
    print(len(range(2,56)), empty, punct)'

    54 [2, 10, 30, 35, 45, 54, 55] {}

I did **not** rebuild the tracer probe. WP-0.2i is concurrently modifying
`mag/src/parity/streams.rs` and `display.rs`, the two files the probe
`#[path]`-includes, so a probe built now would measure a different tracer
from the one WP-5.3d measured, and agreement or disagreement would be
evidence about neither. Recorded as a limit rather than worked around.

## Finding: the two 54-of-54 figures are not equally strong

Both are true. They are not comparable evidence, and the evidence presents
them in one register.

**text-emptiness is genuinely discriminating, and the evidence understates
it.** pypdf finds text empty on 7 of the 54 interior pages (2, 10, 30, 35,
45, 54, 55) and non-empty on the other 47. For the tracer to agree 54 of 54
it must reproduce that exact partition: find nothing on those seven, find
something on the other 47. A tracer that read a full-page plate as carrying
text, or missed text on a text page, would fail. That is a real result and
the evidence sells it short by tabulating it as a bare count.

**`standalone_punctuation_lines` agrees vacuously.** pypdf produces zero
punctuation-only lines on all 54 pages, so the 54-of-54 agreement is `0 == 0`
on every page. It establishes that the tracer does not *invent* such lines;
it establishes nothing about whether the tracer would produce the *same*
lines where any exist. Presented beside a 7/47 partition and a 27/27 spread
table, it reads as stronger than it is.

This is not a false claim and it does not touch the decision, which is why it
is a finding rather than a rejection. Two things already contain it: the
evidence itself says at `:247` that the measured agreement is evidence the
source is sound on *this* edition rather than a substitute for faulting each
field, and recommendation 3 already names a per-field fault including "a page
ending in an orphaned punctuation line". Both should stay. The wording in the
comparison table should say which agreements discriminate and which are
empty-set agreements, because this execution has now rejected several times
over checks that pass without being able to fail, and WP-0.2g exists to
report exactly this as cardinality.

## Not redone

Established by the first verification and not disturbed by the rework: the
single-cause check on the seven `body_text_lines` divergences (all seven
shown rather than generalised, each page named with the line pypdf merges,
geometric counter-evidence for page 4); denominator fairness (47/54 excludes
the two untraceable covers while poppler's 16/56 does not, disclosed in the
table, and counting the covers as tracer failures gives 47/56 against 16/56
with the conclusion unaffected; poppler's 16/56 reconciles with WP-5.3b's
independent 40 of 56); and the reproducibility assessment, adequate with the
probe given by interface and the crux explicit.

Both smaller notes from the rejection are present: reproducibility honestly
described as thin, and the join rule's bounded mirror failure stated, with a
geometric gap-based rule noted as the real fix for whoever implements the
seam in WP-0.2h.

## Owns

`git show --stat 0b32501` touches exactly
`meta/verification/evidence/WP-5.3d.md`. No tracked source, no `*.verify.md`,
no `baseline.json`.
