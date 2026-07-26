# Renderer migration — ReportLab to WeasyPrint

The A5 reader is moving from the bespoke ReportLab typesetter in
`src/magazine/render.py` to an HTML/CSS path
(`html_edition.py` → `weasyprint_adapter.py` + `assets/weasyprint-a5.css`).

**WeasyPrint is the production renderer, and the migration is finished.** It was
proven against ReportLab before cutover by `tools/compare_pipelines.py`, which
renders the candidate, imposes the A4 booklet, and compares both against a
frozen baseline build of edition `002-unreleased` across six gates: geometry,
imposition, per-page content, ink geometry, per-page pixel difference, and
colour. Byte-identical PDFs are not achievable between two producers and were
never the goal; pixel-identical rasterized pages were, and the measured floor
was 0.000000% differing pixels (0 of 1,000,440) for a full page of body copy
rendered through both pipelines and rasterized by the same `pdftoppm`.

**Equivalence is no longer checked, and the harness no longer passes.** The
three shaping scaffolds that made the two renderers interchangeable were removed
after cutover, so WeasyPrint now sets type ReportLab cannot reproduce — that was
the point of migrating. Editions 001 and 002 are archived as printed, outside
the repo; 003 onward is set by this renderer. `tools/compare_pipelines.py` is
kept as a measuring instrument, not a gate: run it to see *how far* output moved
and where, never to get it green. See
[deferred item 1](#1-re-enable-shaping-and-re-baseline--done) for what came out
and what it moved, and
[The rollback window is closed](#the-rollback-window-is-closed) for what
`engine = "reportlab"` means now.

## Switching renderers

Which renderer typesets the A5 reader is configuration, not code.

```toml
[render]
engine = "weasyprint"   # default when the key is absent; "reportlab" is the legacy engine
```

An unrecognised value is a `ValidationError` at `Magazine(root)` construction —
before any work starts — naming the values it will accept. There is no silent
fallback. Note that `[render]`'s neighbouring `body_size` and `leading` are dead
keys that nothing reads (see [Dead configuration](#dead-configuration)); `engine`
is the only live one in that table besides `design`.

**Production:** `engine = "weasyprint"`, or delete the key.
**Legacy engine:** `engine = "reportlab"`. Nothing else changes mechanically —
but since the re-baseline it changes the *publication*; see
[The rollback window is closed](#the-rollback-window-is-closed).

For one build without touching configuration — a side-by-side before committing:

```sh
mag build 002-unreleased --engine reportlab
```

The flag overrides the configured engine for that build only and is never
written back.

### Why `design` is not part of the switch

`render_a5` accepts only `"monument"`, `render_a5_weasyprint` only
`"WeasyPrint / A5 fold proof"`, and each *raises* on the other's value. So the
dispatch in `render_engine.py` never forwards a design across the seam: a
renderer carries the design it renders as part of its identity, read from a
constant in its own module. `[render] design` is the ReportLab engine's design
direction and is consulted only when that engine is selected. Switching engines
is therefore one key, not two, in both directions.

The two engines also stay independent: each is imported lazily inside its own
factory, so a ReportLab build never imports `weasyprint_adapter`, and neither
module has gained a reference to the other.

### What changes in the built package

`layout.design_direction` in `edition-manifest.json` identifies the renderer,
because the two engines have disjoint design vocabularies: `A / Quiet Standard`
for ReportLab, `WeasyPrint / A5 fold proof` for WeasyPrint.

`layout.shaping_scaffolds` records anything a renderer is holding down to match
another producer. Both engines now declare nothing, so no build writes the key —
see [deferred item 1](#1-re-enable-shaping-and-re-baseline--done). The mechanism
is kept for the next time something has to be held down: it puts the admission
in the artifact rather than only in this document, and deliberately not in a
console warning, because a build-time warning that fires on every single build
and cannot be silenced is noise and would be ignored by the second week.

### The editorial page floor was missing on the new path

`minimum_reader_pages` is a per-article floor declared in the edition manifest
and carried through translation: an article that sets out shorter than its
editor allowed has lost source detail. `render.py` has refused such a build
since the field existed; `weasyprint_adapter._validate_layout_caps` checked only
the two maxima, so **the floor stopped applying the moment WeasyPrint became the
default.** Nothing caught it because the build suite was pinned to the rollback
engine at the time. It is enforced on both paths now, and the integration suite
asserts the refusal against whichever engine the project selects.

The two engines still *word* the three page-count refusals differently
(`Article X spans N reader pages; the hard cap is 7` versus `WeasyPrint article
page cap exceeded (maximum 7): X (N pages)`). These are publication rules, not
renderer opinions, and the wording should converge; until it does, no test pins
either string.

### The reader hashes change, so the render review goes stale

Two producers cannot emit identical bytes, so switching engines changes
`reader.pdf` and `booklet-a4.pdf`. Any recorded render review is hash-bound and
immediately reports `status: "stale"` (`mag review status <edition>`), and
`mag release` will refuse the edition until a reviewer records a new decision
with `mag review record`. This is correct — nobody has looked at the new PDFs —
but it is the first thing that bites on cutover. Verified on `002-unreleased`:
the status flips to `stale` with `machine_result: "pass"`, and the refusal is a
clean `error:` line, not a crash.

Verified on `002-unreleased` at cutover: a full `mag build` completes on
WeasyPrint in both languages, `render_critic` returns `pass`, `preflight`
returns `home_ready_studio_blocked` (its pre-existing state), the 8 figure
placements match, and two consecutive WeasyPrint builds are byte-identical to
each other. `engine = "reportlab"` reproduces the pre-cutover build byte for
byte across all 162 packaged files in both languages.

### The rollback window is closed

**`engine = "reportlab"` is no longer a rollback.** It was one only while the
three shaping scaffolds were in place: with kerning, ligatures and intra-token
breaking suppressed, WeasyPrint reproduced ReportLab's line breaking exactly, so
falling back restored the publication rather than altering it. The scaffolds
came out at the re-baseline (see [deferred item 1](#1-re-enable-shaping-and-re-baseline--done)).

From here, selecting ReportLab is a **visible change to the publication**: it
reverts the reader to unkerned, unligatured type set on ReportLab's own
whitespace-only line breaking. 66% of English running words shift, worst case
1.87pt on a single word, and line breaks move. It is still a working engine and
still supported as an escape hatch if the WeasyPrint path ever cannot build an
edition at all — but it produces a different publication, and choosing it is an
editorial decision, not an operational one.

What the engine does still reproduce byte for byte is the *old* publication.
Verified after the re-baseline: `mag build 002-unreleased --engine reportlab`
matches the frozen pre-cutover baseline on all 160 packaged files across both
languages. Nothing in the re-baseline touched `render.py`, `render_critic.py` or
anything the ReportLab path imports.

## The colour gate, and why its exact clause carries it

G6 was added last. It has two clauses: an **exact** per-page comparison of the
chromatic ink each pipeline sets in its content streams, with no tolerance at
all, and a **toleranced** per-channel RGB raster clause.

The exact clause is the one that does the work, and this is the measurement that
shows it. Injecting a channel swap of `VIOLET` and `SIGNAL_ORANGE` — a grossly
wrong hue on every accent, across 32 of the 36 reader pages — was **missed by
every raster gate**: G4's worst ink ratio moved by 0.000013 against a 0.002
tolerance, G5's differing-pixel fraction reached 0.43% against 1%, G5's mean
absolute difference 0.0495 against 2.0, and G6's *own* raster clause 0.2573
against 0.5. The chromatic-ink clause caught it immediately, with **88
failures**.

The accents on this magazine are hairlines, rules and small display type. Their
coverage is too low to move an average past any honest tolerance, so a raster
metric cannot be the thing that catches a hue error here. The raster clause is
kept as the corroborator that also sees hue *inside* an embedded image, where no
colour operator exists to compare.

## What the first review after shaping found, and what it cost

Shaping was reviewed on the printed proof and produced three findings. **Two are
repaired and shipped; the third is repaired, measured, reverted, and still open**
— its cure costs the Spanish edition more than the defect does. Nothing
structural moved for the two that shipped: identical page counts, spans, start
pages and figure placements in both languages.

### Runt control — the reader now has some

**A paragraph whose last line is one short word** was never controlled at all:
before shaping English set 10 and Spanish 6, and shaping reshuffled which
paragraphs landed in the class rather than creating it (13 and 8 after). CSS has
no primitive for it — `orphans` and `widows` count lines across a *page* break
and say nothing about a paragraph's own last line — so the fix is the
typesetter's, older than CSS: bind the last two words with `U+00A0` so they wrap
together. It is a print-path tree mutation in `weasyprint_adapter`
(`_key_prose_blocks` / `_bind_paragraph_tails`), measured off one laid-out pass
and applied on the next, and carried in `ReaderPlan.runt_binds` like every other
measured placement fact. The semantic HTML is untouched, so the character is the
typesetter's and never the manuscript's.

**The threshold is measured, not chosen.** A single-word last line is only a
defect when the word is short. Every one in edition 002, as a fraction of its own
measure, sorts as `3.2 7.5 7.8 7.8 9.9 10.3 10.3 10.5 11.6 13.3 13.7 13.9 14.6 |
16.4 16.8 17.6 18.0 18.2 18.9 21.0 21.4` percent, and the review's own line fell
inside that gap: it refused `context.` at 11.6% and accepted `irreversible.` at
17.6%. Nothing at all is observed between 14.6% and 16.4%, so `15%` can move by
±0.7 points without reclassifying a single paragraph.

Measured on edition 002, single-word last lines in the reading flow (prose
paragraphs, list items, figure captions):

| | before | after |
|---|---|---|
| en | 16 | **2** (18.9%, 18.0% — both above the review's own line) |
| es | 10 | **6** (16.4% to 21.4%) |
| line count of a bound paragraph | — | unchanged on all 18 |
| reader pages | 36 / 36 | 36 / 36 |

Binding can only ever *fit* the pair on the line its neighbour was on or move
both down together, so under greedy line breaking it never adds a line and
sometimes gives one back — verified: 0 of 18 bound blocks changed line count.
What it does spend is rag: the worst case opens 95.7pt (29.5% of the measure) of
white on one English penultimate line, in exchange for a runt the review named.

**The cap on that rag was set at a fifth, and a fifth was wrong.** The refusal
exists for the case where the bound word is long enough that carrying it down
halves the line above; at 20% it instead refused six binds — en p11, en p29 and
two reference entries in each language — and a second review measured every one
of them as worse for it:

| | penultimate rag | last line |
|---|---|---|
| en p11 | 23.7% → 7.3% | 99.4pt → **45.3pt** (`packages.`) |
| en p29 | 30.5% → 12.0% | 98.6pt → **37.8pt** (`context.`) |
| p31 ref 4 (both languages) | 24.5% → 6.5% | 76.5pt → **17.1pt** |
| p31 ref 6 (both languages) | 23.8% → 5.8% | 76.5pt → **17.1pt** |

The distribution argument for 20% was sound and the conclusion drawn from it was
not: the column is set unjustified, so a penultimate line a quarter short of the
measure is rag and every page carries lines shorter than that, while a last line
of one short word is a runt whatever stands above it. On en p11 the refusal put
three one-word last lines — `packages.`, `distribution.`, `and fixes.` — inside
twenty lines of one column. `_RUNT_MAX_RAG_FRACTION` is now **a third**, which
is 3.5 points above the largest rag any bind in this edition asks for, so on
edition 002 it refuses nothing and the table above is again what ships. Verified
by comparing every text box in both languages with the threshold at 20% and at
33%: exactly the four paragraphs above differ, 0 of 684 English and 0 of 733
Spanish boxes moved otherwise, and page counts, spans and start pages are
unchanged.

The bound pair reaches the PDF as an ordinary space — `pdftotext` and `pypdf`
both extract 0 instances of `U+00A0` and full phrase text — and every bundled
face carries the glyph, so nothing falls back to a host font. The reader is set
ragged right, so there is no justification for a bound space to distort. Markup
was rejected as the mechanism for the reason recorded under
[the text layer](#the-text-layer-has-its-spaces-back): a `white-space: nowrap`
span is a second inline box, and WeasyPrint writes no space glyph between two of
them.

### Real quotation marks — the fold stopped degrading them

`reader_text.fold_reader_characters` folded the curly quotation marks, the
ellipsis and the arrow to ASCII, and then encoded through cp1252. **None of that
was typography.** It existed so the reader path matched ReportLab, which writes
through cp1252; with kerning and ligatures correct, straight quotes were the most
conspicuous crudity left in the English edition, and unlike most of what this
migration chased it is obvious at reading distance.

The repertoire is now the **bundled faces'**, not cp1252's: a character is kept
when every one of the eight shipped faces can set it, and replaced with a visible
`?` when it cannot. Measured — all eight carry `U+2018/2019/201C/201D`, `U+2026`,
`U+2192`, `U+00A0`, the dashes and the guillemets, so nothing on the old fold list
needed folding at all. Reaching the built reader now: 4 `“`, 4 `”`, 4 `’` and 2
`→` in English, 4 `«`, 4 `»` and 2 `→` in Spanish. Nothing structural moved:
identical page counts, spans, start pages and figure placements in both languages.

Two things are still folded, and both are deliberate:

- **`U+00A0` to a space.** Not an encoding fold. It is the reader's own
  line-breaking control character now, so a manuscript must not be able to place
  one the typesetter did not choose.
- **Anything no face can set**, to `?`. This is *narrower* than cp1252 in one
  direction and wider in the other: it refuses `U+00AD` SOFT HYPHEN, which cp1252
  encodes but Inter cannot set, and it closes the
  [nested list marker](#5-latent-will-bite-on-a-future-edition) hole — `U+25E6` is
  in Inter and not in Source Serif, and a value does not know which face it is
  bound for. A `?` on a proof is an editor's problem; a Times glyph in the middle
  of Source Serif is a printed one.

`render._plain` keeps its own cp1252 copy untouched, so `engine = "reportlab"`
still reproduces the archived publication byte for byte — verified after this
change on all 162 packaged files across both languages. The test that used to pin
the two implementations together now pins their *difference* in both directions.

**What is left is editorial, not the renderer's.** Seven apostrophes in the
English manuscripts are authored straight (`Coase's`, `Uber's`, `agent's`,
`It's`, …), and the sources they are faithful to are straight too, so setting
them curly would be a substantive edit under `editorial.substantive_edits_require_approval`.

### Heading clearance at a band anchor — 2.65pt, attempted and REVERTED

`_evidence_band` replaces the reading frame before it sets its anchor heading,
and `block` drops space-before whenever `self.y` is the frame's own top
(render.py:1135) — so ReportLab sets a band's anchor heading on the paragraph's
5.4pt of space-after alone, and the heading's own −7.22965pt paint correction
eats most of that again. On a band that bridges its own page that leaves
**2.65pt** between the paragraph's descenders and the heading's cap height,
against 17.65pt everywhere else in the reader: the heading stands 2.65pt above
and 28.2pt below, the association inverted, and it reads as part of the paragraph
it is not part of. The review called it the largest visible defect in the
edition.

**It fires five times, and the list is exhaustive.** Measured on the laid-out
reader, every band anchor in edition 002 that follows a paragraph on its own page
comes out with zero content-box gap where an ordinary prose heading has 15pt:

| | heading | over |
|---|---|---|
| en p17 | `Model economics` | `…split-brain showed up in…` |
| en p30 | `Web UI` | `…to serve requests.` |
| es p17 | `Economía de modelos` | `…la divergencia también apareció…` |
| es p28 | `Planificación y abanico de…` | `…necesitábamos un enfoque…` |
| es p30 | `Interfaz web` | `…Claude Code, o cualquier agente…` |

All five are the same instance of the same rule at the same measurement; a later
review that names one of them as new is reading a list that was written as prose
and never stated its own count. Every other band anchor in the edition opens its
page, where WeasyPrint discards the margin and ReportLab's rule was right.

**The repair works and is one declaration.** Removing the band anchor's
`margin-top: 0` from `assets/weasyprint-a5.css` puts every band anchor on its
rank's own space-before; measured after the change, the tightest prose heading
anywhere in either language clears by 15.85pt and every band anchor by 17.65pt.
A band that *opens* a page is unaffected, because WeasyPrint discards a margin at
a fragmentation break — the only case ReportLab's rule was ever right about.

**It is not shipped, because of what it does to Spanish.** No refusal fires — no
cap breached, no `minimum_reader_pages` floor unmet, the plate arithmetic not
exhausted, `render_critic` pass with zero issues on both languages, both
languages still 36 pages — and English does not move at all. Spanish does:

| | shipped | with the repair |
|---|---|---|
| `agent-swarms-and-model-economics` | 6 pages | **7** — the hard cap exactly |
| start pages, articles 4 / 5 / 6 | 19 / 22 / 25 | **20 / 23 / 26** |
| figure pages (4 of 8) | 17 / 25 / 28 / 30 | **18 / 26 / 29 / 31** |
| closing plates the signature asks for | 3 | **2** |

An independent visual review of the repaired build found three consequences,
each worse than the 2.65pt:

- **es p17 becomes a mid-article page that is ~60% white.** The anchor heading
  and its figure are one atomic block; 20.4pt more above the heading is enough
  that the block no longer fits the remainder of the page and moves whole, and
  the page it left is not an article ending.
- **es article 6 loses its tail ornament**, which English keeps — the article now
  ends on `FIN / 06` and nothing, while es articles 2, 4 and 5 all carry theirs.
- **es loses its third closing plate.** `Las señales regresan` stops being
  printed and the two languages no longer end the same way.

So the trade is a 15pt clearance gain on three Spanish headings against a
half-empty page, a dropped ornament and a dropped plate — and the two English
headings it would also fix come free only because English absorbs the space.
`tests/test_weasyprint_adapter.py` pins **both** states, the defect as it ships
and the repair as it would ship, so neither can rot while this waits. What
unblocks it is editorial, not typographic: Spanish article 3 needs roughly a page
less copy, or an editor has to accept the lost plate and re-break es p17.

## Deferred until after cutover

Ordered by what matters most. Item 1 is done and is kept here, rewritten as a
record of what changed, because everything after it was written against the
world where it had not happened.

### 1. Re-enable shaping and re-baseline — DONE

All three scaffolds are out. The reader now kerns, applies ligatures, and takes
Pango's own intra-token break opportunities. What was removed:

1. `font-kerning: none` in `assets/weasyprint-a5.css`.
2. `font-variant-ligatures: none`, beside it.
3. `.reader-token { white-space: nowrap }`, plus the
   `_suppress_intra_token_breaks` tree pass in `weasyprint_adapter.py` that put
   one such box around every whitespace token.

`weasyprint_adapter.SHAPING_SCAFFOLDS` is now `()`. The constant itself stays,
empty, because it is the artifact's contract: `compiler.py` writes
`layout.shaping_scaffolds` into a build's manifest whenever it is non-empty, so
anything a future change holds down to match another producer has to be declared
there and becomes visible in the packaged edition. Both engines now declare
nothing, and `edition-manifest.json` carries no `shaping_scaffolds` key.

**This deliberately broke equivalence with edition 002's frozen baseline.**
Editions 001 and 002 are archived as printed, outside the repo; 003 onward is
set by this renderer. `tools/compare_pipelines.py` now fails, and that is the
expected result, not a defect to chase. Do not reinstate a scaffold, or tune
anything, to make it green again.

#### What the scaffolds were, and what they cost

ReportLab measures text by summing raw glyph advance widths and has never
kerned. Pango/HarfBuzz kerns and applies ligatures by default. The same 10pt
line measured **321.862pt** shaped against **323.870pt** unshaped — enough for a
word to fit on one line in one pipeline and wrap in the other, which then
shifted every line below it. With shaping off the two agreed to **0.008pt**
across a full 325pt measure. Shaping accounted for 15.49% of the total pixel
difference and took English line-break agreement from 81.8% to 94.8% (Spanish to
100%). Kerning reaches **66% of English running words**, worst case **1.87pt
(~0.19 em)** on a single word — visible on a printed page, and the reason the
scaffold was never a design decision.

The third scaffold was line breaking. `lines` (render.py) splits a paragraph
with `str.split`, so the ReportLab reader can only end a line on whitespace;
Pango also breaks *inside* a token, after a hyphen or a dash — `compile-
checked`, `Opus- planner`, `trade- offs`. `word-break`, `line-break`, `hyphens`
and `overflow-wrap` were all measured no-ops against it, so the only lever was
markup. One nowrap box per token took English line-break agreement from 94.8% to
385/385 lines and 69/69 paragraphs, and left Spanish at the 423/423 it already
had.

#### What the re-baseline actually moved

Measured on edition `002-unreleased`, both languages, WeasyPrint before against
WeasyPrint after (the harness's own numbers, against the frozen ReportLab
baseline, before → after):

| | before | after |
|---|---|---|
| G1 geometry | PASS, reader 36/36 pages, booklet 18/18 sides | PASS, unchanged |
| G2 imposition | PASS | PASS |
| G3 en pages differing | 0 of 36 | **11 of 36** |
| G3 es pages differing | 0 of 36 | **2 of 36** |
| G5 worst differing pixels, en reader | 0.60% | **18.66%** (p15) |
| G5 worst differing pixels, es reader | 0.27% | **12.71%** (p15) |
| G4 worst ink-ratio delta, en reader | 0.000094 | 0.011389 |
| G6 chromatic ink | identical on every page | identical on every page |

Nothing structural moved. Both languages still come out at **36 reader pages and
18 booklet sides**; every article keeps its start page and its span
(5 / 3 / 6 / 3 / 3 / 7 plus the editorial's 1, unchanged in both languages); no
article reached its `minimum_reader_pages` floor; the closing-plate arithmetic
still asks for three plates and the manifest still configures three. Still true
after the three post-shaping repairs above, which is most of why the third of
them was reverted. What
changed is where the lines fall *within* an article: G3 reports four English
entries and one Spanish entry redistributing body copy across their own pages
(for example `agent-swarms-and-model-economics` p15 321 → 287 words, p14 161 →
187). `render_critic` returns `pass` with zero issues on both languages.

The shortening the scaffolds' removal was expected to cause did not materialise
on this edition. Kerning does make lines hold more, but not by enough to release
a whole page anywhere in edition 002. **A future edition may not be so lucky:**
the two things to check on a first build after any measure change remain the
`minimum_reader_pages` floors and the closing-plate count, both of which refuse
loudly rather than shipping something wrong.

#### The text layer has its spaces back

Removing the nowrap boxes resolved the extraction finding recorded here.
WeasyPrint gives each inline box its own text matrix and emits no space glyph
between two of them, so one box per token used to reach the PDF as
`Theoriginalarticle.` Verified after the re-baseline: `pypdf`'s
`extract_text()` on a built reader now returns ordinary spaced prose in both
languages. `tests/test_weasyprint_adapter.py` asserts it directly on a written
PDF.

`tests/test_render_integration.py` still reads pages with `pdftotext`, which is
still the right call — it is what a PDF viewer and a text search do, so the same
assertion means the same thing under either engine — but it no longer does so
because WeasyPrint's own text is unreadable. Its docstrings say so.

#### Long URLs

Dropping the nowrap box lifted this constraint, and measurement then showed the
constraint had no subject. Nothing in either edition's reader flow is anywhere
near the measure: the widest token set anywhere in edition 002's document is 57
characters of source id inside the `display: none` provenance line, no URL is
set at all (the manuscripts carry none, and `href` values never lay out), and no
line box on any of the 36 pages exceeds its own measure by more than float
noise. The 169-character figure recorded here came from `src="file://…"`
attribute values, which are not typeset.

`_validate_reader_measures` is kept, narrowed rather than retired. A hyphenated
token now breaks at its hyphen and never reaches it; an unbroken run of letters
still overflows the column, and silently, which is what the refusal is for. It
is deliberately not repaired with `overflow-wrap: anywhere`: a word that cannot
fit the measure is an editorial problem, not the typesetter's to break at
random. Shaping also removed the last case where `overflow-wrap` reproduced
`lines`'s per-character fallback, so there is no longer any stylesheet spelling
of it to choose instead.

#### One thing shaping exposed, and the guard it needed

`weasyprint_adapter._advance_widths` / `_wrap` sum unkerned advances, because
they reproduce `render.py`'s own decisions — the auto-fitted opener and closing
plate titles, `_evidence_band`'s heading and figure heights. Those measurements
are no longer what Pango does with the same text.

**This section used to claim the difference was one-sided and therefore safe —
that kerning and ligatures only pull glyphs together, so every `_wrap` width is
an upper bound on the shaped one, a fitted size still fits and a predicted line
count is never exceeded. That is false, and it was measured false.** Ligatures
do only ever narrow in these faces, so half the argument holds. Kerning does
not. Restricted to cp1252 pairs in the `kern` feature:

| face | tighten | loosen |
|---|---|---|
| `SourceSerif4Display-Semibold` (every fitted title) | 12,794 | **3,019** |
| `SourceSerif4SmText-Regular` | 10,252 | **1,164** |
| `Inter-SemiBold` | 5,254 | **911** |

The loosening pairs are ordinary: `Lo` +17, `La` +21, `Có` +11, `tr` +10,
`ru` +10, `oo` +9, `co` +5 (units per 1000). Five real edition-002 title lines
already set wider shaped than summed; the worst, `'Cómo construimos'` at 35pt,
by **+1.2568pt**. A fitted size can therefore be one Pango wraps, and a fitted
title can outgrow the white field the opener reserved below it — on the one
opener that carries a figure, straight into the figure. Edition 002 survives on
margin, not on principle: across all 83 fitted title lines and band headings in
both languages there are zero line-count underestimates, and the tightest opener
field clears its title by 16.69pt.

The repair is **`weasyprint_adapter._validate_fitted_display`**, a post-layout
guard in the same family as `_validate_reader_measures` and called beside it. It
asserts, on boxes the adapter already walks, that

* every opener's laid-out `h1` **margin box ends inside the header field** the
  adapter reserved for it (`_pin_opener_fields`'s stated height, or the
  stylesheet's constant for an opener without a figure), and
* every closing plate's caption is **set on the line count it was fitted to**
  (`_fitted_plate_title`).

It names the article, the title, the reserved and actual extents, and tells the
editor to shorten the title or lower the fit range. `_validate_reader_measures`
does not cover this: it refuses a *line box* wider than its own measure, and a
title that merely wrapped is not one. `render_critic` does not cover it either.

The predictor itself is still deliberately **not** corrected by shaping. It
reproduces `render.py`'s own arithmetic, which is done on unshaped advances, so
shaping it would change the publication rather than fix it — and a predictor
that is right more often is still silently wrong at the margin, which is exactly
what the guard exists to stop being possible. If a shape-accurate predictor is
ever added it is a bonus on top of the guard, never a replacement for it. Any
new caller of `_advance_widths` / `_wrap` that reserves space on a prediction
needs its own clause in `_validate_fitted_display`.

### 2. Blank-page check accepts near-white ink

`render_critic._inspect_page` derives `blank` from `WHITE_THRESHOLD = 245`, so
the production critic's own "inside front and inside back covers must be
completely blank" error would pass a 246–254 grey tint or a hairline. This is in
shipping code and independent of the migration. `tools/compare_pipelines.py`
already requires a pure-white raster plus zero extracted characters; production
should match.

### 3. Deduplicate the reader-text fold — WITHDRAWN

The two are **supposed** to differ now, so there is nothing left to deduplicate.
`reader_text.fold_reader_characters` folds to what the bundled faces can set;
`render._plain` folds through cp1252 because ReportLab writes through cp1252 and
that engine has to keep reproducing the archived publication. See
[real quotation marks](#real-quotation-marks--the-fold-stopped-degrading-them).
The test that pinned the two together now pins their difference in both
directions, which is what stops either drifting into the other unnoticed.

What is genuinely still duplicated is the *markdown-link* regex: `render._plain`
strips links, and `weasyprint_adapter._plain` carries a copy of that clause
because it reproduces `render.py`'s own fitted-title arithmetic. Neither has any
business running over HTML, and neither does.

### 4. `render_critic` API friction

`RASTER_DPI` is a module constant rather than a parameter, so the harness
rebinds it inside a context manager. `_booklet_spread_checks` takes left/right
page numbers from its argument rather than deriving them from the booklet PDF,
so its mapping cannot serve as evidence — the harness derives placement
positionally instead.

### 5. Latent, will bite on a future edition

- **Band anchor heading measured at the wrong size.** `render.py:871-874`
  measures at `(SERIF_DISPLAY, 17.5)` / `(SANS_SEMIBOLD, 8.7)` then draws at
  18.5 / 8.5. The CSS uses the drawn sizes. A heading whose 18.5pt width falls
  between 333.008pt and ~352pt wraps in CSS but not in ReportLab. Not exercised
  by edition 002.
- **Terminal balance is not reproduced.** The adapter hardcodes
  `frame_bottom = 45.0`, but `render.py` raises it for the last two pages of any
  article carrying an `ArticleBalancePlan`. Inert today — the frozen manifest has
  `article_terminal_balance: {}` — but the tail-ornament rule and the
  `.article-tail` datum are both silently wrong the first time a plan fires.
- **Long URLs.** Resolved and measured; see
  [Long URLs](#long-urls) under deferred item 1. Nothing in the reader's flow
  approaches the measure, a hyphenated token now breaks at its hyphen, and an
  unbreakable over-measure token is still refused by
  `_validate_reader_measures` rather than styled.
- **Nested list markers — no longer silent.** U+25E6 WHITE BULLET is carried by
  all four Inter faces and by no Source Serif face, and prose is Source Serif, so
  it used to fall back to Times New Roman without saying so. The reader's fold
  now keeps only what *every* bundled face can set, so it comes out as a visible
  `?` instead. The design's own answer is unchanged and still the right one:
  bullets are drawn as boxes rather than set as glyphs, and no marker character
  should be reintroduced. Edition 002 has no nested lists.

### 6. Off-grid type sizes cost 0.29%

Pango quantizes font size to 1/1024 CSS px, so 10pt becomes 9.999756pt
(−24.4 ppm). Only 5 of the design's 18 sizes are exactly representable; 12pt,
22pt and 24pt measure exactly zero pixel difference. This is the entire
irreducible residual and it is a consequence of the type scale, not a tool
limit. **Do not change type sizes to flatter a diff metric** — recorded here
only so the residual is understood.

## Dead configuration

`magazine.toml`'s `[render] body_size = 9.55` and `leading = 12.55` are read by
nothing. The authoritative pair is **10 / 13** in `render.py`. The stylesheet was
originally calibrated against the dead values, which is why its metrics were
wrong. Either wire the config up or delete it.
