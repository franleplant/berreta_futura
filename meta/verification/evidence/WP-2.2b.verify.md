# WP-2.2b verification

**Verdict: REJECTED**, on one CODE defect live on the branch and the evidence
claims that sit on top of it. Every measured figure in the evidence reproduced
from a fresh worktree: 159 boxes and 53 rotations at zero mismatches, the
running head and contents grid to the stated deltas, all nine openers, the
folio correct on every page past 9, 55 against 56 pages, `b_reader`
`0c137d27...`, 22/209 and 23/221. The targets the plan set for this slice are
met as measured. What fails is the same thing that failed WP-2.2a: a mapping
table that is accurate about where a value came from and wrong about whether
it arrived.

1. **A code defect, live on `art_directed`, exercised on all nine 010
   openers: the opener title's `-.045em` tracking is declared, tabled as
   transcribed, described in Residual 2 as rendered, and never applied.**
   `OPENER-TITLE-TRACKING = -0.045` at `template.typ:89` has exactly one
   occurrence in the file, its declaration (positive control:
   `OPENER-LABEL-TRACKING` has two). `opener-title-text` (`:387-395`) sets
   font, size, weight, fill, hyphenation and edges, and no tracking. The CSS
   at `:1494-1498` sets `letter-spacing: -.045em`. Measured on the rendered
   legs: the first title line is **25.1 to 33.0 pt wider on the typst leg**
   on the six openers whose first line carries the same words on both legs,
   and **the line break differs on the other three plus DeepSeek** (Dario 5
   words against 4, third-era 6 against 5, Storage 5 against 4, DeepSeek 4
   against 3). Word by word on opener 1: `Government` spans 143.16 pt on the
   oracle and 155.07 pt on typst, +11.91 pt over nine glyph gaps at about
   30 pt, which is `9 x 1.35 = 12.15` to within the space glyph, and the word
   gaps are 3.36 against 6.00. **Class A** under rule 6a: Python is right, the
   fix is one `..tracked(OPENER-TITLE-TRACKING * size)` in
   `opener-title-text`. It changes no page boundary, since the opener page is
   filled to its foot either way and every title stays within two lines, so
   nothing measured in this file moves; it is a Tier E divergence on nine
   pages that WP-3.x will meet, and it also makes the evidence's attribution
   of the four opener-row differences to `_split_standfirst_overflow` alone a
   hypothesis (rule 11), since a second cause that changes title line count
   now exists on four of those pages.
2. **The evidence asserts the opposite of the code, twice, in the place a
   reader would check.** The Transcribed row "opener title: `PAPER-INK`,
   tracking -.045em, margin-top 8pt" cites `:1494-1498` correctly and the
   template does not do it. Residual 2 then says "the template mirrors the
   adapter (fit without tracking, render with it)"; the render half is false.
   And the class-C mechanism it offers is inverted: the tracking is
   NEGATIVE, so a title `_wrap` puts on two lines cannot reach three under
   tracking; the real blind spot both engines share is the other way, a fit
   that steps DOWN when the tracked title would have fitted at a larger size.
   The blind spot is real and class C; the stated consequence ("overflow the
   box unnoticed") cannot happen.

**WP-2.2c SHOULD KEEP BUILDING on `f3bec3e`.** The geometry, the opener page
ownership, the contents grid, the running head, the folio and the page spans
are all sound and independently measured here. Rule 3b's line: **the
tracking defect IS live on `art_directed`**; its consumers are **WP-2.2c**,
which holds `mag/assets/typeset/template.typ` now and lands the one-line fix
in its own slice exactly as WP-2.2b landed WP-2.2a's folio, and **WP-2.3**,
whose `measure_article` reads a leg whose opener titles are set untracked
until it does. Nothing needs reverting.

## Base and Owns

Verified at the landed commit **`f3bec3e`** (parent `096e163`) in a worktree
created for this verification and used for nothing else
(`.../jobs/7d99e27f/tmp/vwp22b2`), a path distinct from the development
worktree the evidence names (`.../tmp/wp22b`). `## Base` is `1ed37df`, an
ancestor of `f3bec3e` seven commits back; the evidence records the two
rebases and the refused compare-and-swap honestly under `## Landing`.

Rule 1, `git diff --name-only 096e163 f3bec3e` and `git show --stat`:
exactly three files, `mag/assets/typeset/template.typ`,
`mag/src/typeset/template.rs`, `meta/verification/evidence/WP-2.2b.md`. The
preamble's Owns and nothing else: **no verify file, no `baseline.json`, no
`mag/src/parity*`, no `meta/plans/`, no Cargo file.** `git diff --stat
1ed37df..096e163 -- mag/` touches only `cover*`, `model/shared.rs` and their
tests, none of which this slice reads, so the evidence's decision to carry
the measurement-commit numbers to the landing commit is sound and was in any
case re-measured (below).

One brief instruction did not hold and is recorded rather than followed
silently: "renders need `editions/010/run-2026-09-13T01-34-51` copied in".
The run is TRACKED (21 files under `git ls-files`), so the worktree carried
it and nothing was copied. The evidence's own line "the run directory under
`editions/010/` is gitignored" is false for the same reason, inherited
verbatim from WP-2.2a's evidence where its verifier already flagged it
(defect G). Only `editions/*/render-*/` is ignored.

## Rule 12 replay

The `## Commands` block was extracted **programmatically** from
`meta/verification/evidence/WP-2.2b.md` (the file's only ```sh fence, 9,409
bytes, 178 lines) to a file and executed with `bash` from the verification
worktree root with no variables set, so both defaults (`RUN`, `OUT`) were
exercised. **Block exit 0.** Hermetic from a directory not developed in.

| quantity | evidence | replay at `f3bec3e` |
| --- | --- | --- |
| `cargo fmt --check`, `clippy --all-targets -D warnings`, `cargo test` | clean | clean (grep for `^warning`, `^error`, `^Diff in`, `could not compile` over the log: rc 1, absent; positive control `^test result` 23 hits) |
| `cargo test` binaries / tests at the landing commit | 23 / 221 | **23 / 221** |
| `cargo test` binaries / tests at `1ed37df` with the diff | 22 / 209 | **22 / 209**, built and run in a second worktree at `1ed37df` with `f3bec3e` cherry-picked (clean apply) |
| `mag parity 010` exit | 1 | 1 |
| `staged_input_digest` | `e48eb5c6...` | **`e48eb5c6...`**, identical to WP-2.2a's as well |
| `inputs.b_reader_sha256` | `0c137d27...` | **`0c137d27...`** |
| `inputs.a_reader_sha256` | `e010c14c...` | `738605ba...`, a **seventh** distinct oracle hash from one staged input set |
| `verdict.json` sha256 | `6d73960d...` | `23c22ed6...`, differing exactly as the evidence predicts and for the reason it gives |
| tier summary | as quoted | `mode: render`, `self_comparison: false`, `page_count fail (56 vs 55)`, page sets body 34 / code 0 / furniture 54 / openers 9 / placement 11, ratchet not_measured (54 checked, 54 recorded, 0 measured) |
| pages a / b, domain | 56 / 55, 2..54 | **56 / 55, 2..54** |
| boxes compared, mismatches beyond 0.05 pt | 159 / 159, 0 | **159 / 159, 0** (53 pages x 3 names, re-derived) |
| rotations compared / mismatches | 53 / 0 | **53 / 0** |
| worst single-coordinate delta | 0.000000 pt | **0.000000 pt** |
| typst determinism | 3 renders, one hash | **3 renders in two worktrees**, one hash `0c137d27...` (two in the block, one in the base worktree) |
| folio p4 / p9 / p12 / p23 / p44 | `04 09 12 23 44` both legs | identical, number right edge 377.00786 typst against 377.00915 / 377.0118 / 377.00625 / 377.0064 / 377.00391 |
| running head xMin recto / verso | 44.00000 / 42.51970 vs oracle 43.99998 / 42.51968 | identical |
| running head baseline | 13.41250 vs 13.41099 | identical |
| contents kicker / title baseline | 24.41753 / 56.03290 vs 24.41599 / 56.03300 | identical |
| contents entry columns | 44.00000 / 91.00000 both legs | identical, all 36 rows on both legs |
| opener label / title baselines, 9 openers | within 0.00142 / 0.00019 pt | identical (256.7426 vs 256.7412; 264.0850 vs 264.0850 etc.) |
| running heads on opener pages | 0 both legs | **0 both legs** |
| opener-page text rows | equal on 5 of 9, off by one on 4 | identical pattern (16/15, 14/15, 7/8, 15/14 on articles 1, 2, 6, 7) |

Per-article spans on the typst leg re-derived: 3, 3, 5, 13, 4, 4, 5, 4, 4
= **45** against the oracle's 46, the one -1 on `an-alignment-assessment`,
Dario 13 on both legs. The last row is where the block and the table part
company, see Defect C.

Caption check (rule 12's caption clause), each block step's scope words read
against its output: step 1 "the two totals this file quotes" prints 23 and
221, both quoted; step 3 "largest domain the two legs share" compares
`2..min-1` = 2..54; step 5 "every page" iterates every page of both
documents; step 6 "past page 9" checks 12, 23 and 44. **Step 4's caption
drifts from its code**, Defect C.

## The brief's named checks

### The folio fix, checked past page 9 on every page (rule 10d)

Independently, not only at the block's five pages: on the typst leg the foot
digits equal the zero-padded page index on **every page 3..48**, seven pages
in 3..9 and **39 pages in 10..48, zero wrong**; pages 49..55 carry no folio
(five plates and two outer pages), so the typst leg's folio population is 46
and every member is right. The oracle's is right on every folio page 10..53
as well (page 56's foot carries the back cover's `2026 09 13`, not a folio).
`leading-zero(index)` (`template.typ:138`) is `"0" + str(index)` below ten
and `str(index)` otherwise, which is `decimal-leading-zero` for every value an
edition reaches, and it is the same function the contents entry folio uses
(`:288`), so the two agree by construction; the contents prints
`04 07 10 15 28 32 36 41 45`, which is exactly the typst leg's nine article
starts, and the oracle's `04 07 11 17 31 36 40 46 50` is exactly its own.
**This is the discriminating check WP-2.2a's sample could not make, and it
is the one WP-2.2a's verifier said its own replay lacked.**

Not committed as a test: no committed test pins `leading-zero` past page 9;
the check lives only in the evidence block's step 6 and here. A regression
would be caught by the parity gate once page counts match, and by nothing
before. Residual, not rejection.

### The blockquote fix

`ruled()` (`:625-633`) is `pad(left: QUOTE-RULE / 2, block(stroke: (left:
QUOTE-RULE + VIOLET), inset: (left: pad-left + QUOTE-RULE / 2, ...), width:
100%))`. Content left edge is `0.75 + (4mm + 0.75) = 12.838583 pt` and the
content width is `325.025 - 12.838583 = 312.186417 pt`, WP-2.2a's measured
value, preserved. **Measured on both legs**: 010's one blockquote (`#doc-quote`
called once in the emitted pieces, re-derived) sits on **page 5 of both legs,
two lines, first-glyph xMin 60.8425 on both**, which is the recto rail
`48.0039 + 12.8386`; page 5 carries other body rows on both legs, so the
quote no longer takes its page. `rect(height: 100%)` occurs nowhere in the
template except as the test's `OLD_QUOTE_RULE` constant, and `doc-code`
(`:644-659`) uses the same `ruled(3mm, 3mm, PALE-VIOLET, body)`, exercised by
no 010 piece. The committed test
`a_short_quote_does_not_swallow_the_rest_of_its_page` substitutes WP-2.2a's
exact grid text back in with an `assert_ne!` that the substitution happened
and requires the old form to take more pages: the failing case is committed.

### Heading clearance: the sweep exists, discriminates, and the corpus cannot

`the_heading_clearance_reserves_twenty_five_points_below_a_heading`
(`template.rs:301-319`) sweeps 24..40 paragraphs and requires at least one
count where the transcribed template takes more pages than one with the
constant replaced by `0pt`. Four measurements in the second worktree, each a
full rebuild and a render of 010:

| template | pages | article starts | reader.pdf |
| --- | --- | --- | --- |
| 25 pt (transcribed) | 55 | 4, 7, 10, 15, 28, 32, 36, 41, 45 | `0c137d27` |
| 0 pt | 55 | 4, 7, 10, 15, 28, 32, 36, 41, 45 | `6d15526d` |
| **200 pt** | **57** | 4, 7, **11, 17, 30, 34, 38, 43, 47** | `e045dc9b` |
| 25 pt, reservation block and pull-back REMOVED | committed sweep **FAILS**: `no paragraph count put a heading inside the 25pt reservation` | | |

The evidence's "identical pagination, different bytes" reproduces exactly.
Rule 10's opposite extreme, which the evidence did not run: at 200 pt the
mechanism BINDS on 010, two pages and seven article starts move from article
3 on, so the 25 pt reservation is live and slack rather than inert, which is
rule 10e's distinction (unfalsifiable on 010, not unreachable) confirmed from
the side the evidence left open. And the sweep fails when the mechanism is
removed with the constant still declared at 25, so it tests the mechanism
and not the `#let`. 010's heading population re-derived from the emitted
pieces: 38 at level 2, 3 at level 3, **41**, as stated.

### Page caps: what is enforced, precisely

`page-cap(id, kind)` (`template.typ:786-795`) runs at compile time at the end
of every piece and asserts **`kind == "verbatim" or span <= ARTICLE-PAGE-CAP`**
with the oracle's own message text. So:

- the **7-page hard cap is enforced at compile time for every non-verbatim
  kind**, and a violation refuses the whole document;
- a **verbatim piece is exempt from every cap**. `VERBATIM-PAGE-CAP = 10` has
  **one occurrence in the template, its declaration**; nothing reads it. The
  test's `declared("VERBATIM-PAGE-CAP") == 10.0` pins the number and not a
  behaviour;
- the oracle **warns** on a verbatim overrun (`render.py:2086-2091`, and the
  replay log carries the adapter's line verbatim: `WARNING: verbatim article
  past the page cap, rendering anyway: dario-amodei-we-must-pace-the-frontier
  (13 pages, cap 10)`); the typst leg is silent. Dario, `kind: "verbatim"` in
  its emitted piece (7 `article`, 2 `verbatim` on 010), spans 13 on both legs
  and neither refuses, exactly as the evidence says.

The reconciliation the brief asked for: "enforced at compile time" is true of
the 7 and **not of the 10**, which is enforced nowhere and carried as a
constant. The evidence's mapping row and Residual 3 say this accurately
("asserts the hard branch and is silent on the advisory one"); its target
table's "7 hard / 10 advisory, enforced at compile time" reads as if both
were, and is the looser of the two statements. Defect D.

Also inside the cited `render.py:2082-2096` and neither transcribed nor
PENDING: the **`minimum_reader_pages` floor** at `:2093-2096`, which raises
when an article is SHORTER than its editorial minimum. Found (the range is
cited) and dropped silently, which is the preamble's one prohibition.
Defect E.

**Rule 10c, both limbs, on the cap tests.** Fallback limb:
`the_page_cap_refuses_an_article_past_seven_reader_pages` expects a refusal
naming "the hard cap is 1", which no template without a cap produces.
`a_verbatim_piece_is_not_refused_by_the_article_cap` expects a clean compile,
which a template with no cap ALSO produces, and rescues itself by compiling
the same 400-paragraph run under `kind: "article"` and requiring refusal.
Input limb: does the pair separate "verbatim exempt" from "verbatim capped at
10"? Only if the 400-paragraph run exceeds ten pages. By the sweep's own
boundary (about 27 one-line paragraphs per frame) it is about 15 pages,
derived not measured; and live on 010, **Dario at 13 verbatim pages compiles
on the typst leg**, which is a measurement of the same branch. Both limbs
hold.

### `_split_standfirst_overflow` and `_fitted_display` (the two disclosures)

- `_split_standfirst_overflow` (`weasyprint_adapter.py:2808-2833`), called at
  `:1272` only when even compact density overflows the page, cuts the
  standfirst at a Pango word count, builds a new `<p>` from the tail, and
  `article.insert(index(header) + 1, remainder)`: the tail becomes the first
  BODY paragraph after the header. The template keeps the whole standfirst on
  the opener page. **Confirmed as a second concrete instance of WP-2.1's
  oracle blindness**: the content oracle compares text and order, both
  unchanged by the move. Measured effect reproduces (rows 16/15, 14/15, 7/8,
  15/14 on four openers), though see the attribution caveat in point 1.
- `_fitted_display` (`:378-395`) calls `_wrap(text, face, size, width)`
  (`:348`), whose signature has no tracking argument, so the fit is measured
  untracked while `:1496` renders the h1 at `-.045em`. **The class-C blind
  spot is confirmed. Its stated direction is not**: negative tracking
  narrows, so the untracked fit is conservative and can only choose a size
  smaller than the tracked title needed; it cannot overflow. And the
  template's half of the comparison is not "render with it" (point 1).

### Rule 6a per value, and the boundary no artifact settles

`leading-zero` is authored from the CSS keyword `decimal-leading-zero` and
not from output: its two-branch body is a definition, not a transcription of
observed folios, and it disagrees with WP-2.2a's output on 36 pages, which is
what an authored value does when the output was wrong. `OPENER-ART-FLOW`
195.1 is transcribed from an adapter CONSTANT (`:203`, `:213`), which is the
spec side. The fitted title size is DERIVED (Typst `measure()` standing in
for `_wrap`) and the evidence says so; its 9-of-9 agreement is labelled a
corpus observation, correctly. The +2.2656 pt standfirst offset is recorded
as unexplained with two hypotheses refuted by substitution, which is rule 11
done properly. Per rule 6a's own boundary, whether any value was written from
the stylesheet or read off the oracle's PDF is not recoverable from the
artifact; the checkable half, that no generator writes the template and the
block only reads, holds.

## The mapping table: inherited invented values, and one of its own

The brief asked whether this slice inherits WP-2.2a's two invented values or
adds its own. Both, in part.

| value | at `f3bec3e` | in WP-2.2b's table or PENDING? |
| --- | --- | --- |
| `doc-rule` 0.55 pt COOL-GRAY (`:581-585`) | **unchanged**. No `hr` selector in the stylesheet: `grep -nE '(^|[,{}[:space:]>])hr([,{[:space:]]|$)'` rc 1 (absent), positive control `blockquote` by the same pattern 3 hits. 010 emits `#doc-rule` **zero** times (the manuscripts' `---` are frontmatter fences) | **neither** |
| `byline-prefix` VIOLET | **fixed on the exercised branch**: the illustrated branch (`:429-435`) is `PAPER-BLUE`, `.15em` tracking, `.35em` gap, matching `:1531-1536`, all nine 010 calls take it. **Unchanged on the plain branch** (`:427`, `fill: VIOLET`, no tracking), for which the stylesheet has no `.byline-prefix` rule at all (`grep -n byline-prefix` returns only `:1531`), so it would inherit `.byline`'s ink. Unexercised by 010 | the illustrated row is tabled; the plain VIOLET is in **neither** |
| `piece-title` plain 24pt / 1.08 (`:419`) | **unchanged placeholder** | the PENDING row for `_fitted_title_box` names the mechanism and not that the template meanwhile carries 24pt |
| **`OPENER-TITLE-TRACKING`, this slice's own** | declared `:89`, applied nowhere | tabled as **transcribed**; point 1 |

The first three were assigned to WP-2.2a's rework by its verifier and this
slice was told to re-derive the opener values rather than inherit them; it
did so for every exercised one but the title tracking, and it did not list
the three it left standing. The fourth is this slice's own, and it is the
inverse of the folio: there the citation was right and the value wrong; here
the citation is right, the constant is right, and the value never reaches
the ink. **A row in the Transcribed table certifies where a value came
from, not that it arrived**, which WP-2.2a's verifier wrote as this table's
limit and which this slice has now demonstrated from the other side.

What is right, checked against `src/magazine/assets/weasyprint-a5.css` and
`weasyprint_adapter.py` line by line rather than for plausibility: every
running-head row (`:161-175`, `:283-306`), every contents row (`:315-388`,
including the `.entry-label` correction, which is real: `.contents-kicker` at
`:325` tracks and `.entry-label` at `:354` does not), the heading clearance
(`:522`, and `render.py:1084` is indeed `self.y - needed - 25 <
self.frame_bottom`), and every illustrated-opener row (`:1436-1610`), all of
whose numbers are the stylesheet's own to the digit, the compact set
included. `.label-date` at `:1548` (rgb(93 96 96), 600) matches both
branches. Line citations are exact throughout, unlike WP-2.2a's second half.

## Other defects found

**C. Block step 4 prints a wrong number for a cell the table gets right.**
Its caption says the typst leg's plates "trail the last article" and are
subtracted, but `spans(nb, sb, [])` passes an empty plate list, so the last
typst article runs to `n + 1` and prints **11** with a total of **52**, where
the `## Metrics` table records **4** and **45**. The table is correct (pages
49..55 carry no folio, so `rapidly-scaling` is 45..48), so "every number
below is produced by the command block" is false for that row, in rule 12's
caption-drift shape. The truth is verified here; the provenance is not.

**D.** The target table's "7 hard / 10 advisory, enforced at compile time"
overstates the 10; see Page caps.

**E.** The `minimum_reader_pages` floor inside a cited range, neither ported
nor PENDING; see Page caps.

**F. "19 recto and 18 verso pages on each leg" is wrong for the typst leg**,
whose running heads are **18 recto and 18 verso, 36**. Its own Metrics row
says 37 / 36 correctly. The census keys on rounded `xMin`, and on the typst
leg the contents kicker on page 3 lands on exactly `44.0`, the same key as
the recto running head, so the kicker page was counted as a running head;
the oracle's kicker rounds to `44.0` while its running heads round to
`43.99998`, so the oracle count escaped the collision. Rule 9: a count
carries its domain, and this one merged two.

**G. `## Tool versions` records poppler 25.09.1.** `parity.yaml:271` pins
**25.08.0**, the installed `pdfinfo` is 25.08.0, and `mag parity` asserts the
two agree at startup, so the run used 25.08.0. WP-2.2a's verifier reported
this exact line as defect F; it was carried forward uncorrected. Provenance
only; no measurement is affected.

**H.** The "gitignored" run directory, inherited and false; see Base.

## What reproduced beyond the block, for the next reader (rule 3d)

- **Every value WP-2.2c depends on is sound**: the opener owns its page on 9
  of 9 with the art field, frame, offset, label, tick, meta grid and
  standfirst at the stylesheet's geometry; the running head is on every body
  page and no opener page; the contents grid is pinned; the folio is right
  on every page; page spans match on 8 of 9 with the -1 on the one article
  whose figure is unplaced.
- **The opener title's glyphs are NOT at the oracle's positions**, by the
  tracking, on all nine openers; WP-2.2c lands the fix in
  `opener-title-text`, and until then any opener-page glyph measurement
  compares against a known divergence.
- **The heading clearance is live on 010 and slack at 25 pt**, binding at
  200; the committed sweep tests the mechanism, not the constant.
- **The 7-page cap refuses at compile time; verbatim is exempt; the 10 is a
  number nobody reads.** WP-2.3's `article_pages` is the natural home for the
  warning and for the unported minimum floor.
- **The oracle leg is still not byte-reproducible**: seven hashes from seven
  renders across three agents; compare `b_reader`, the staged digest and the
  tier summary, never `a_reader` or the verdict digest.

## Rework

Code, one line, owned by WP-2.2c as holder of the file: apply
`OPENER-TITLE-TRACKING` in `opener-title-text` and in `fitted-title`'s
measurement ONLY IF the oracle's fit is also changed, which it is not, so the
fit stays untracked and the render gets `..tracked(OPENER-TITLE-TRACKING *
size)`. Verify on the nine opener pages by first-line width, which today
differs by 25 to 33 pt, and by line count on Dario, third-era, DeepSeek and
Storage.

Record: correct the title-tracking row and Residual 2 (both halves), list
`doc-rule`, the plain `byline-prefix` and the 24pt `piece-title` as inherited
placeholders awaiting WP-2.2a's rework, add the `minimum_reader_pages` floor
to PENDING with an owner, fix step 4's plate subtraction or mark the last row
as derived outside the block, correct the typst recto count to 18, poppler to
25.08.0, and the "gitignored" line.

## Tool versions

rustc 1.96.0; `typst` and its crates `=0.15.1`, `lopdf` 0.45.0, no Cargo
file touched; **poppler 25.08.0**, matching `parity.yaml:271` and asserted by
`mag parity`; CPython 3.12.11 through `uv run python`, no bare `python3`; no
typst CLI, `TYPST_ROOT` unset.

## Status

**REJECTED**, on the opener-title tracking defect, live on the branch and
exercised on all nine 010 openers, and on the two evidence statements that
assert the opposite of what the template does. Every other claim reproduced
from a fresh worktree, the folio and blockquote fixes are correct and
measured on every page rather than a sample, the sweep discriminates, and
the targets are met as measured. **WP-2.2c should keep building on `f3bec3e`
and should land the one-line fix in its own slice.**
