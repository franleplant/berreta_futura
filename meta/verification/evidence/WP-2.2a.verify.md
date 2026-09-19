# WP-2.2a verification

**Verdict: REJECTED**, on a CODE defect and an evidence defect together.

Every measured claim in the evidence reproduced exactly, including the two
tables the `## Commands` block does not produce, and the geometry this slice is
named for — page frame, three body measures, column rail, datum — is correct
against the stylesheet to the last digit. Two things fail.

1. **A code defect, live on the branch: the folio is wrong on 36 of the typst
   leg's 43 folio pages.** `numbering("01", index)` reads `0` as a literal
   prefix rather than a pad, so from page 10 on the folio prints `010`, `011`,
   `020`, `045`. Found by WP-2.2b, recorded in plan revision 61 as rule 10d,
   and **re-measured here independently**. This is the one piece of page
   furniture the slice owns, and the evidence's PROVEN bullet claims it
   reproduces.
2. **The WP-2.2 preamble's mapping-table obligation is not met**, and it is
   this WP's own stated main deliverable: at least ten values the template
   carries and edition 010 exercises are cited in neither the Transcribed table
   nor the PENDING list, and **two of them are invented rather than ported** —
   the exact failure the obligation exists to catch and which no downstream
   oracle detects.

**WP-2.2b SHOULD KEEP BUILDING on `03db604`** — it owns
`mag/assets/typeset/` and `template.rs` now, it found the folio defect itself,
and the geometry it depends on is sound. Rule 3b's required line: **the folio
defect IS live on `art_directed`**, and its consumers are **WP-2.2b** (which
already holds the file and must land the fix) and **WP-2.3**, whose
`measure_article` reads a leg whose folios are wrong today. Nothing else in the
tree needs reverting.

## Base and Owns

Verified at the landed commit **`03db604`**, in a worktree created for this
verification and used for nothing else
(`.../jobs/7d99e27f/tmp/vwp22a`), a third absolute path distinct from both the
development and replay worktrees the evidence names.

The evidence's `## Base` is `3b57c36`. The commit's actual parent is `c8ba566`,
seven commits later (WP-5.1f `02f1d35`/`160c39e`, WP-0.2i `0ec67a9`,
`8a03c1a`, `b271911` WP-0.2k, and two plan revisions). `3b57c36` is an ancestor
of `03db604`, and `src/magazine/assets/weasyprint-a5.css` has not changed since
`5504e5a` (WP-1.5), well before either, so every stylesheet citation in the
evidence is checkable against the landed tree. Two evidence counts are
base-specific and are stale at the landed commit; see Defect H.

Rule 1, `git show --stat 03db604`: exactly eight files —
`mag/assets/typeset/root.typ`, `mag/assets/typeset/template.typ`,
`mag/src/render.rs`, `mag/src/typeset/content.rs`, `mag/src/typeset/mod.rs`,
`mag/src/typeset/template.rs`, `mag/src/typeset/world.rs`,
`meta/verification/evidence/WP-2.2a.md`. **No verify file, no
`baseline.json`, no `mag/src/parity*`, no `meta/plans/`.** The Owns list plus
the two declared extensions and nothing else.

**Both declared out-of-Owns hunks are exactly what was declared.**

- `mag/src/typeset/content.rs`: two lines, `want.len()` -> `want.chars().count()`
  and `projection.text.len()` -> `projection.text.chars().count()`, both inside
  `println!`/`assert!` **messages**. The guard `want.len() > 10_000` is
  untouched, so nothing measured changed. Confirmed by reading the hunk.
- `mag/src/render.rs`: the four-line hunk is **byte-identical** to the diff
  quoted in the evidence's `## Base`. It is the minimum that makes
  `--engine typst` reach the render dir and the staged request; WP-2.0a's stub
  took no arguments. Recommend the orchestrator ratify it as declared.

## Rule 12 replay

The `## Commands` block was extracted **programmatically** from
`meta/verification/evidence/WP-2.2a.md` (first ```sh fence, 9,035 bytes) and
executed from the verification worktree. **Block exit 0.**

One earlier attempt died on the host's disk exhaustion
(`[Errno 28] No space left on device`, reported by the coordinator). That run is
discarded entirely, not partially credited. The results below are from the
clean run at 56 GiB free.

Caption check (rule 12's caption clause): every block caption's scope words
were read against its output. Step 5 claims "the domain the two legs share" and
compares 2..51, which is `min(56,52)-1` and the comparator's own `first = 2`.
Step 6 claims the verso rail "needs no matching content" and uses a modal
statistic, which is true of what it computes. Step 8 claims it removes the path
difference by rendering twice in ONE worktree, and it does. No caption drift
found in the block. Two caption defects sit **outside** the block; see Defects
D and G.

## What reproduced

### Claim 1, the render

`mag render 010 --engine typst --no-model --langs en` writes `en/reader.pdf`:
**52 pages, 419.528 x 595.276 pt.** Reproduced.

Page structure independently confirmed: pages 1, 2 blank; page 3 the contents;
pages 4..45 the nine articles; 46..50 the five plates, all blank; 51, 52 blank.
`52 - 4 outer - 5 plates = 43` folio pages, which is the census's 43.

### Claim 2, the direct box measurement

Every figure reproduced to the digit:

| quantity | evidence | replay |
| --- | --- | --- |
| pages a / b, domain | 56 / 52, 2..51 | 56 / 52, 2..51 |
| boxes compared | 150 / 150 | 150 / 150 |
| box mismatches beyond 0.05 pt | 0 | **0** |
| worst single-coordinate delta | 0.000000 pt | **0.000000 pt** |
| rotations compared / mismatches | 50 / 0 | 50 / **0** |
| p5 first body line xMin | 48.003929 / 48.003930 | identical |
| p5 body line advance | 13.000000 both | identical |
| modal recto rail, pp 5..45 | 48.003930 (380 / 541) | identical, counts included |
| modal verso rail, pp 5..45 | 46.523630 (331 / 415) | identical, counts included |
| folio name xMin, p4 and p5, both legs | 42.519700 | **42.519700** |
| folio number xMax | 377.009154 / 377.010581 / 377.007853 / 377.007859 | identical |
| folio baseline yMin | 569.186587 / 569.188100 | identical |
| 47 required / 0 undefined / 38 exercised / 9 not | as stated | identical, same 9 names |

The tolerance is `parity.yaml`'s own `tiers.s.box_tolerance_pt: 0.05`, confirmed
unchanged, and `/Rotate` is compared exactly, as the comparator does. The
boundary is the largest domain the two legs share; per rule 11's boundary test
it makes the comparison **harder** (150 boxes rather than three), and what it
excuses the WP from proving is pages 52..55, which is the page-count gap itself
and is accounted for rather than dropped. Confirmed.

**The left-edge census reproduces, and it has no producing command** (Defect D).
Derived here from the typst leg over pages 3..45 with an independently written
script: 56 distinct `xMin` values — 42.5197 x43 (folio name = `MARGIN-OUTER`),
46.5236 x446 and 48.0039 x574 (verso / recto column rails), 59.3622 x2
(blockquote verso), 60.5236 x116 and 62.0039 x38 (list items), 70.5236 x4 and
72.0039 x5 (end marks, **nine in total, one per article**), 33 folio-number
values summing to 43, and 15 page-3-only values. Every one resolves to a derived
constant exactly as tabulated. One nit: the census row reads "15 further values |
1 each"; the fifteen values are right, but one of them (83.7379) occurs three
times, not once.

The arithmetic behind those constants was re-derived from first principles and
is correct to the last digit: `148mm = 419.5275590551 pt`;
`LIVE-WIDTH = 419.5275590551 - 44 - 42.5197 = 333.0078590551`, which is the
stylesheet's own `width: 333.0079pt` at `:174`;
`RAIL = (333.0078590551 - 325) / 2 = 4.0039295276`; recto `44 + RAIL =
48.0039295`; verso `42.5197 + RAIL = 46.5236295`; content height
`595.2755906 - 42.0004 - 54.9996 = 498.2755906`.

### Claim 3, the WP-1.7 cross-check

**Confirmed, by an agent that did not produce WP-1.7's numbers and did not
produce this WP's either.** Re-derived from WP-1.7's own artifact:
`WP-1.7.md:35` reads `311.0000 pt | 24 | 154`, and `:36` reads
`312.1614 pt | 1 | 2`. The typst leg's rendered line boxes put **116 + 38 = 154**
lines at the 14 pt list indent, and the emitted tree carries exactly **24
`#doc-item`** calls and exactly **1 `#doc-quote`**. Two independent
reproductions of WP-1.7 from the opposite direction, both exact.

The widened measures check out too. WP-1.7's intersection is
`[+0.010000, +0.040000)` with midpoint `+0.025000`, re-derived from its own
table; `template.typ` carries `MEASURE-DELTA = 0.025pt`; the committed test
pins the window to `325.010000 .. 325.040000`, which is WP-1.7's interval, and
asserts both neighbours fail. Blockquote: `325.025 - (1.5 + 4mm) =
325.025 - 12.838583 = 312.186417`, against WP-1.7's widened `312.186400`, and
the unwidened form `325 - 1.5 - 11.338583 = 312.161417` is WP-1.7's
`312.1614`. Correct.

**The fourth measure's derivation is correct.** `ul[data-reference-list] li`
(`:843-848`) sets `padding-left: 12.9744pt; text-indent: -12.9744pt`, and
`ul, ol { margin: 0; padding: 0 }` at `:836` means the list box is the full
measure, so continuation lines run at `325 - 12.9744 = 312.0256 pt` while the
first line recovers the full 325. The template transcribes 7.2/9.4/3pt and
`REFERENCE-HANG = 12.9744pt` exactly. All eight of 010's lists emit
`references: false`, confirmed in the emitted tree, so nothing exercises it —
correctly folded into WP-3.3's fixture.

### Claim 4, the verdict and its provenance

`mag parity 010` exit **1**. `staged_input_digest`
**`e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`** —
identical to the evidence. `b_reader_sha256`
**`3196b6ceb5173afa22f86d0f7908e9f91f16abae46901ae094b49c379aad45b0`** —
identical. Tier summary identical clause for clause: `mode: render`,
`self_comparison: false`, **no `typst_leg` key**, `page_count: fail (a 56, b
52)`, `boxes`/`text`/`color`/`navigation` null, `tier_g` null, `tier_v` null,
all three `tier_e` clauses null, `code_blocks` and `critic` `not_evaluated`
with the owners quoted.

`verdict.json` sha256 **`336dbbd8...`** against the evidence's `7653875a...`,
and `a_reader_sha256` **`605f5cc5...`** against `26a29054...`. **Exactly as the
evidence predicts**, for exactly the reason it gives.

**The gating mechanism is code, not argument.** `mag/src/parity.rs:1072` reads
`if !counts_equal { return Ok(verdict); }`, with
`counts_equal = na == nb && na >= 3` at `:1026`. Nothing past `page_count` can
be evaluated while the counts differ. So `blocked` was the right status and
revision 56 was right to move those targets to WP-2.2c: **no slice before
page-count parity can hold a target requiring the comparator to proceed.** The
evidence demonstrated this rather than arguing it, which is the right shape.

Correction to my own reading, recorded per rule 3c: I first reported
`a_reader_sha256` as null. It is not; it lives under `inputs`, not at the top
level, and I had read the wrong key. The figure above is the corrected one.

## The folio defect, re-measured here

Plan revision 61 landed while this verification was running and records, as
rule 10d, that WP-2.2b found WP-2.2a's folio wrong past page 9. **Re-derived
here from this verification's own PDFs rather than cited**, per rule 9:

| page | typst leg | oracle leg |
| --- | --- | --- |
| 5 | `05` | `05` |
| 9 | `09` | `09` |
| 10 | **`010`** | (plate, no folio) |
| 11 | **`011`** | `11` |
| 20 | **`020`** | `20` |
| 45 | **`045`** | (plate, no folio) |

The cause is `template.typ:76`, `numbering("01", index)`. Typst's `numbering`
treats `1` as the counting symbol and every other character as a literal, so
`"01"` emits a literal `0` followed by the unpadded number. The CSS it is
transcribed from, `content: counter(page, decimal-leading-zero)` at `:153`,
**pads to a minimum of two digits and does not prefix**. The two agree on
exactly one decade.

Counted at the point of citation, and stating its population because rule 9
requires it: the typst leg carries folios on **43** pages (3..45, confirmed by
the left-edge census's 43 hits at `MARGIN-OUTER`). Pages 3..9, **seven** pages,
are correct; pages 10..45, **36** pages, are wrong. The plan's "43 of 010's 46
folio pages" counts against the ORACLE's folio pages, a different population
from the typst leg's 43; both figures are right about the thing they count and
they are not the same thing.

**This is rule 10d's own instance and it indicts this verification too.** The
evidence checks the folio at pages 4 and 5; so does the `## Commands` block;
so, therefore, did my replay, which reproduced those two pages to six decimals
and learned nothing. Pages 4 and 5 are inside the region where the two
formatting rules agree, and no amount of precision there could have exposed it.
I did not apply rule 10d on my own initiative — it reached me through a plan
revision landing mid-verification — and that is worth recording rather than
smoothing over, because the sample I would have defended was the sample that
could not fail.

**Classification, rule 6a: class A.** Rust differs from Python, Python is
right, and the fix is to match it. It is not class B, because the oracle's
folio is correct and no user input reaches the defect. It is reachable on every
edition of ten or more folio pages, which is every edition.

**What it costs the rest of this verification.** Nothing measured moves: the
folio's POSITION reproduces exactly (name `xMin` 42.519700 on both legs and
both parities, number right edge within 0.0027 pt, baseline within 0.0016 pt),
and the defect is in the glyphs, not the geometry. The page count is unaffected,
since a three-glyph folio occupies the same out-of-flow box. So the box, rail
and page-span results above stand as measured.

**And it shows the mapping table's limit from a third direction.** This row IS
in the Transcribed table, and its citation IS correct: "folio numbering `01`
zero-padded | `content: counter(page, decimal-leading-zero)` (:153)". The
citation is right and the implementation does not realise it. So a correct
citation does not certify a correct transcription, and the table's honesty
problem is not only the ten missing rows below — a present row can be wrong
too, in a way only output measurement catches.

## The three findings

### Finding 1, the page-gap attribution — the evidence OVERCLAIMS it

**The per-article page-span table reproduces exactly**, derived here two ways
the evidence does not record: the oracle column from the oracle leg's own
`en/edition-manifest.json` `layout.article_pages`, and the typst column by
locating each article's first page in the typst PDF. Deltas +1, 0, -1, -1, 0,
-1, -1, 0, -1; totals 46 and 42; net **-4**. The three figures sit on oracle
pages **12, 37 and 42** (confirmed independently from the manifest's
`layout.figures` and from the render-review crop names), on articles 3, 6 and 7,
each of which loses exactly one page. Every number is right.

**The inference drawn from them is stated as established and is not.** The
evidence says "**Three of the four missing pages are the three figures WP-2.2c
places**" in a section headed "where the four missing pages **are**", repeats it
in `## Status`, and repeats it in the commit message. Nowhere is it labelled a
hypothesis. Rule 11 requires the opposite: a mechanism asserted by the WP that
found the defect is PROPOSED until an independent measurement confirms it, and
this one is untested by construction, since no mechanism exists to remove.
Notably the evidence DOES hedge correctly one paragraph later, calling the
orphan/widow contribution to the residual "a hypothesis and rule 11 says so" —
so the discipline was available and was applied to the weaker claim and not to
the stronger one.

**The corpus falsifies the inference's evidential weight, and this is
measurable rather than rhetorical.** Of the six FIGURELESS articles, three
moved: two lost a page and one **gained** one. That is a per-article drift rate
of 3/6 = 0.5 with no figure involved at all. At that base rate, three
figure-carrying articles all moving is `0.5^3 = 0.125` — one run in eight —
and the direction is not even tested, since the observed drift goes both ways.
Taking the combinatorial form instead, five of nine articles lost a page, and
the chance that the three figure articles are all among the five losers is
`C(6,2)/C(9,5) = 15/126 = 0.119`. **A correlation of three items at p ~ 0.12
against a null the same corpus supplies is not a cause.**

Two further points the evidence does not make. Each figure box is 205.0,
187.317 and 187.317 pt tall (manifest `layout.figures`), so with its caption and
the 15.75 pt gap each consumes roughly 42-47% of the 498.2756 pt content box —
removing it drops a page only when that article's tail happens to fall inside
that band, which is a coincidence needed three times, not a mechanism. And
**the fourth missing page is unexplained under either account**: the evidence
labels it "flow", which names the residual rather than explaining it.

This matches the plan's current framing at revision 58 verbatim, and that
framing postdates the evidence. **Finding 1, as written, overclaims; the
numbers under it are sound.**

### Finding 2, the non-reproducible oracle hash — CONFIRMED, both halves

- **The WeasyPrint leg is not byte-reproducible.** Step 8 renders the oracle
  twice in ONE worktree from the same staged run, which removes the
  path-difference cause per rule 11. Result: `605f5cc5...` and `de2addc6...`,
  **different**, with the request's staged input rows verified identical
  between them. Together with the four hashes the evidence records, that is
  **six distinct hashes from six oracle renders across two agents and three
  absolute paths, with zero repeats**, all at the same
  `staged_input_digest e48eb5c6...`.
- **The typst leg is byte-reproducible.** Four renders in this worktree (two
  from the discarded disk-full attempt, two from the clean block) all produced
  `3196b6ce...`, matching the evidence's six renders in two other worktrees.
  **Ten renders, three absolute paths, one hash.**

The consequence the evidence draws is correct and is worth the standing-guidance
change it has already caused: `a_reader_sha256` identifies which run produced a
verdict but cannot be matched by a replay, while `b_reader_sha256` and
`staged_input_digest` can. A verifier of any Phase 2 or 3 WP should compare
those two and the tier summary, and should expect the verdict digest to differ.

### Finding 3, orphan/widow control — CONFIRMED, and the escalation was right

`p { margin: 0 0 5.4pt; orphans: 2; widows: 2; }` at `weasyprint-a5.css:549`,
with the comment at `:527` reading "orphans and widows are 2: three would break
pages earlier than the reader does" — a deliberate editorial choice, exactly as
reported. The template sets no equivalent because Typst 0.15.1 has none.

The search result is also right: `grep -rn "orphan\|widow"` over the plan **as
the WP saw it (revision 54, in the worktree)** returns **zero** hits. Nothing
owned it. The evidence correctly filed this under NOT PROVEN rather than
offering the empty search as proof of absence, and escalated it in `## Status`
per rule 2a. The plan has since assigned it to WP-2.2c with a sanctioned oracle
change. **This finding is the WP's most valuable output and the process worked
as designed.**

## The mapping table — the preamble obligation, and why this is REJECTED

I checked the table against `src/magazine/assets/weasyprint-a5.css` myself,
rather than reading it for plausibility, and then ran the check in the opposite
direction: every numeric literal in `template.typ` against the table's text.

**What is right.** Of the forty-odd Transcribed rows, **every value I checked is
the stylesheet's own**, and the ones that matter most for what WP-2.2b builds on
are right to the last digit: the page frame (`:119-120`), the recto/verso mirror
(`:177-187`), `MEASURE` (`:265`), `MEASURE-DELTA` (WP-1.7, re-derived above),
the palette (`:217-224`, `:248`), the flow/ink ratios and `DATUM` (`:397-398`,
`:403-405`, `:414`), the folio (`:122-123`, `:143-158`, `:181`, `:186`), the
paragraph and editorial spacing (`:549`, `:551`), the three headings
(`:489-509`), the standfirst (`:710-713`), the list (`:836-842`), the reference
list (`:843-850`), the blockquote (`:918`), `pre` and `code` (`:940`,
`:946-954`), the end mark including the 28.53085 / 0.07625 / 2.47375 triple
(`:851-890`), key ideas (`:907-917`), the outer and plate pages (`:189-214`),
and the three `display: none` rules. **No invented value among them**, and
`HALF-MONO` is honestly flagged as derived from the font rather than
transcribed, which is the disclosure the obligation wants.

**What is wrong, and it is the obligation itself.** The preamble binds the table
to two things: every transcribed value cites its origin, and anything
found-but-not-transcribed is listed as PENDING, never dropped silently. **A
value in neither list is the failure mode**, and there are at least ten, all of
them exercised by 010:

| value in `template.typ` | its CSS origin | in the table? |
| --- | --- | --- |
| `content-label`: 6.8pt / 500 / tracking 0.45pt / INK / caps / spacing 7.53085pt | `.content-label` `:740-744` | **neither** |
| `label-date`: rgb(93, 96, 96) weight 600 | `.label-date` `:1548` | **neither** |
| `byline`: 7.4pt / 600 / above 12pt / caps | `.byline` `:790` | **neither** |
| `author-note`: SLATE 6.8pt / 400 / 9.45pt / above 7.49326pt | `.author-note` `:796` | **neither** |
| `extract`: above and below 5mm, unbreakable | `.extract` `:923` | **neither** |
| `extract-caption`: VIOLET sans 6.8pt / 1.35 / above 2pt | `.extract-caption` `:934-937` | **neither** |
| `entry-label` / `entry-title` / `entry-author` type: 6.8pt 500 caps, 9.8pt/10.2pt display 600, SLATE, spacings 8.6 / 2.7 | `:357-383` | listed **PENDING** (WP-2.2b) while in fact transcribed |
| `figure-block` below 15.75pt | figure geometry | listed **PENDING** (WP-2.2c) while in fact transcribed |
| `doc-rule`: 0.55pt COOL-GRAY | **none — see below** | **neither** |
| `byline-prefix`: 6.2pt **VIOLET** | `:1531`, which says rgb(49 93 140) | **neither** |

**Two of those are invented rather than ported, which is precisely the risk the
obligation exists to catch:**

1. **`doc-rule` has no origin at all.** `html_edition.py:677` emits a bare
   `<hr>`, and the stylesheet contains **no `hr` selector anywhere** —
   confirmed with `grep -nE '(^|[,{}[:space:]>])hr([,{[:space:]]|$)'`, which
   returns nothing; all 19 "hr" hits are substrings inside comment words. So the
   oracle's rule is whatever the UA sheet gives it, and the template's
   `0.55pt + COOL-GRAY` is borrowed from `.running-head-rule` (`:300`), a
   different object. The evidence's NOT PROVEN section calls all nine
   unexercised functions "transcriptions"; for this one that is not true, and
   the distinction between "unverified transcription" and "invented value" is
   the whole point of the table. **Class A under rule 6a; latent, since 010
   emits zero horizontal rules.**
2. **`byline-prefix` is exercised and its colour is wrong.** All nine of 010's
   articles declare `article_opener: illustrated_paper_spots_v1`, and the
   emitted tree calls `#byline-prefix` once per article, confirmed in all nine
   piece files. The applicable rule is `:1531-1536`: `color: rgb(49 93 140)`,
   `font-size: 6.2pt`, `letter-spacing: .15em`, `margin-right: .35em`. The
   template has the size right and sets **VIOLET**, with no tracking and no
   margin. **Class A, live on the branch, and reachable today.**

A third value is a placeholder presented as nothing: `piece-title` is hard-coded
at 24pt on a 1.08 leading. The stylesheet is explicit at `:468-482` that family,
weight and colour live in CSS while the display **size is a measurement the
adapter states per opener** (`_fitted_title_box`). The table lists that stepped
size as PENDING for WP-2.2b, which is honest about the mechanism, but never
records that the template meanwhile carries an invented 24pt. A reader of the
table cannot learn that.

**So: the mapping table is accurate but NOT complete, and the preamble's
obligation is not met.** The commit message's claim — "each cited in the evidence
mapping table; everything found and not transcribed is listed PENDING" — is
false as measured, in both directions: values transcribed without citation, and
values listed PENDING that were in fact transcribed.

**One binding-preamble deviation is undeclared.** The WP-2.2 preamble says of
the `::before` figure and extract labels: "nothing upstream catches them and
they are **WP-2.2a's to get right**. They go in the mapping table with their
selectors like any other transcribed value." The evidence instead lists both as
PENDING for WP-2.2c. The deferral is defensible on its merits — the figure block
the label attaches to is not placed until 2.2c, and 010 carries no extracts —
but it is a deviation from a clause that binds per rule 8, and it is presented
as a routine assignment rather than as a departure. **WP-2.2c's holder must know
these were assigned to 2.2a by the preamble.**

## Other defects found

**D. Two `## Metrics` sub-tables have no producing command**, under a sentence
reading "Every number below is produced by the command block". The block's eight
steps produce neither the left-edge census nor the per-article page spans. This
is rule 12's recorded shape (WP-5.4's zone oracle, WP-5.4b's SVG oracle), and it
caused rejections there. Mitigating, and the reason this is listed here rather
than as the head of the rejection: **I reproduced both tables independently and
both are exact**, so what is missing is the provenance, not the truth.

**E. About a dozen CSS line citations in the second half of the file are
wrong**, drifting by 20 to 85 lines, while the selectors they name are correct
and findable. Measured: `figcaption` is at `:1214`, cited `:1129-1140`;
`figcaption .credit` at `:1233`, cited `:1148-1151`; `.source-link` at `:1416`,
cited `:1414`; `.closing-plate { break-before: page }` at `:1634`, cited
`:1611`; `.closing-plate img` at `:1647-1649`, cited `:1616-1621`;
`article > figure[data-figure-id]::before` at `:1065`, cited `:1117-1122`;
`.band-clearance` at `:1131` and `band-anchor-midpage` at `:1198-1200`, cited
`:1101-1113` and `:1216-1232`. Every citation before roughly `:1110` is exact.
The stylesheet has not moved since `5504e5a`, so this is not a base drift. The
table still functions as a table of selectors; it does not function as a table
of locations.

**F. `## Tool versions` records a poppler version the run cannot have used.**
It states "poppler 25.09.1 as pinned in `meta/verification/parity.yaml`".
`parity.yaml:271` pins **25.08.0**; the installed `pdfinfo` is **25.08.0**; and
`mag/src/parity.rs:920` calls `assert_poppler`, which refuses when the two
disagree. The author's own `mag parity` run therefore ran at 25.08.0. No
measurement is affected — the assertion guarantees that — but `## Tool versions`
exists for provenance and this entry is wrong twice over.

**G. Three small caption or count slips**, none affecting a result:
- "the run directory under `editions/010/` is **gitignored**" is false. `runs`
  are tracked (21 files under `git ls-files`), and `.gitignore` says so in
  terms: "runs are tracked: they are the content of record. renders stay
  local." Only `editions/*/render-*/` is ignored. The `RUN=${RUN:-...}` default
  is harmless and the block is hermetic, but its stated justification is not the
  real one.
- "`grep -n "characters"` returns five hits" — the command as written returns
  **ten**; five are the `fold_reader_characters` identifier. The five message
  sites enumerated are the right five.
- "There is no third site" is scoped to `content.rs` while a third site exists
  in `mag/src/typeset/mod.rs:81`, a file this WP itself edits. Benign, because
  that site already uses `chars().count()` — correct by construction rather than
  by the sweep.

**H. Two counts are stale at the landed commit.** "17 `mag/tests/*.rs` files /
18 `cargo test` binaries / 186 tests" is correct at the stated Base `3b57c36`.
At `03db604` it is **21 files / 22 binaries / 203 tests**, all passing,
re-derived here by the evidence's own step-2 commands; the four extra binaries
are `model_shared_label`, `model_shared_roster`, `parity_concurrent` and
`parity_ratchet`, from WP-5.1f, WP-0.2i and WP-0.2k. Rule 9: **a total is a
measurement with a timestamp**, and the "17 versus 18" section settles a naming
collision correctly while omitting the timestamp that keeps it settled. For the
record, the naming collision itself is real and the evidence's account of it is
right: `.rs` files in `mag/tests/` is one population, `cargo test` binaries is
that population plus the `mag` binary target's in-crate tests.

**I. One committed test's name and its PROVEN bullet overstate it.**
`the_page_frame_constants_are_the_stylesheet_s_own` reads no stylesheet; it
compares `template.typ`'s `#let` lines against six numbers hard-coded in the
test. It catches `template.typ` drifting from the test, not from
`weasyprint-a5.css`, and its failure message says "drifted from
weasyprint-a5.css". This is the authored-from-spec-versus-transcribed-from-output
axis: the six numbers are a hand transcription of the spec, which is the right
kind, but the test cannot see the spec change. **I checked all six against the
stylesheet directly and they are correct** (42.0004, 42.5197, 54.9996, 44,
10.0046, 19.5, all at `:119-123` and `:178`). The derived half of the same test
— live width and content height — is genuinely derived and does discriminate.

The other four committed tests are sound and their discrimination claims hold:
`the_a5_page_box_check_discriminates` runs both a 1pt-wider box and A4 and
asserts **every** page fails (rule 10's opposite-extreme half, done);
`the_template_defines_every_function_the_fixture_editions_call` inserts a fake
name and asserts exactly it is reported;
`the_body_measure_straddles_wp17s_admissible_window` asserts both neighbours
fail, not just that the value is inside.

## What this WP proves, restated for the next reader (rule 3d)

The load-bearing reasons, put here because a verify file is terminal and this is
where the next slice will collide with them:

- **Page frame, body measures, column rail, folio POSITION and datum are
  correct and independently verified against the stylesheet.** WP-2.2b, WP-2.2c
  and WP-2.3 can build on all of them without re-deriving them. **The folio's
  NUMBERING is not among them** — `numbering("01", n)` is wrong from page 10
  on, and WP-2.2b owns the fix.
- **A correct citation in the mapping table does not certify a correct
  transcription.** The folio-numbering row cites the right CSS declaration and
  the template does not implement it. Read the table as a record of where a
  value came from, never as a record that it arrived intact.
- **`blocked` was structurally right**, and `parity.rs:1072` is the proof.
- **The oracle leg is not byte-reproducible; the typst leg is.** Ten typst
  renders, one hash; six oracle renders, six hashes.
- **The page gap is not attributed.** Three of four pages correlate with
  figures at p ~ 0.12 against a null the corpus itself supplies, and the fourth
  is unexplained under either account.
- **The mapping table is a table of selectors, not of line numbers, and it is
  incomplete.** Do not read a value's absence from it as evidence the value was
  not transcribed.

## Rework, and what must not wait for it

One code fix and a set of record corrections. Nothing measured needs
re-deriving.

0. **`template.typ:76`: replace `numbering("01", index)` with a form that pads
   rather than prefixes**, matching `decimal-leading-zero`. WP-2.2b holds the
   file and found the defect, so this lands there rather than in a WP-2.2a
   rework. Per rule 10d, the regression check must include at least one page
   past 9; per rule 6b, if it cannot be fixed in scope it needs a tripwire, not
   a residual paragraph.

1. Add the ten uncited rows to the Transcribed table with the selectors above,
   and move the contents-entry typography and the 15.75 pt figure gap out of
   PENDING, since they are transcribed.
2. Fix the two invented values in `mag/assets/typeset/template.typ`:
   `byline-prefix` to `rgb(49, 93, 140)` with `.15em` tracking and `.35em`
   trailing margin, and either drop `doc-rule`'s styling or record it
   explicitly as having no CSS origin. Record `piece-title`'s 24pt as a
   placeholder pending `_fitted_title_box`.
3. Relabel the page-gap attribution as a hypothesis in `## Metrics` and
   `## Status`, per rule 11 and the plan at revision 58.
4. Correct the poppler entry to 25.08.0, the twelve drifted line citations, the
   "gitignored" and "five hits" statements, and timestamp the 17/18 counts.
5. Add producing commands for the census and the page-span tables, or mark both
   as derived outside the block. Both scripts are short; this verification wrote
   them from scratch in a few lines each.
6. Note the preamble deviation on the two `::before` labels, and tell WP-2.2c's
   holder they were assigned to 2.2a.

**Rule 3b, stated explicitly.** Three defects are live on `art_directed`, in
descending order of consequence:

- **the folio numbering**, wrong on 36 of 43 folio pages and on every edition
  with ten or more. Consumers: **WP-2.2b**, which owns the file and must land
  the fix, and **WP-2.3**, which will measure a leg whose folios are wrong
  until it does;
- **`byline-prefix`'s VIOLET**, exercised on all nine of 010's articles, inside
  the illustrated opener that WP-2.2b will rewrite. A Tier S colour question
  three slices from being evaluable;
- **`doc-rule`'s invented hairline**, unexercised by 010 and latent until an
  edition carries a horizontal rule.

**WP-2.2b should keep building on `03db604` and should not wait for a WP-2.2a
rework.** Two things it should take from this file: the opener values already
in `template.typ` are not all ported, so re-derive them from `:740-796` and
`:1433-1614` rather than inherit them; and the folio fix belongs in its own
slice, since it holds the file.

## Tool versions

rustc 1.96.0; typst crates all `=0.15.1` (unchanged, no Cargo files touched);
lopdf 0.45.0; **poppler 25.08.0**, matching `parity.yaml:271` and asserted by
`mag parity` at startup; CPython 3.12.11 through `uv run python`, no bare
`python3`; the typst CLI is not installed and `TYPST_ROOT` is irrelevant to
this leg.

## Status

**REJECTED**, on one code defect and one evidence defect.

The code defect is the folio numbering, live on the branch, found by WP-2.2b
and re-measured here; it belongs to WP-2.2b's slice because WP-2.2b holds the
file. The evidence defect is the mapping table, which is this WP's stated main
deliverable and is incomplete in both directions, with two invented values
among the omissions and one wrong implementation behind a correct citation.

**The geometry is sound and cleared for downstream use**, and WP-2.2b should
keep building on `03db604` without waiting for the rework.
