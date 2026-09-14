# Typst parity and the full-Rust migration

Status: **in execution**, 2026-09-14, revision 12 (Phase 0 built and
verified, the Phase 1 spikes measured and audited, the gate critiqued
adversarially and repaired, the content-final gate narrowed to where it
bites). Companion to `rust-rewrite.md`
(which moved orchestration to Rust and left the renderer in Python). This
plan finishes the job: a Typst-based renderer implemented in Rust inside
`mag`, proven equivalent to the WeasyPrint renderer by rendering **edition
010 (en)** with both engines and comparing mechanically until they are
exactly the same, then porting every remaining Python module to Rust and
deleting `src/magazine/`.

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
  boxes. Coordinates quantized at 0.01 pt; colors in one normalized space.
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
  set was one item and was wrong, so it is now listed exhaustively and each
  item says what covers it:
  1. **intra-line glyph positioning** (TJ kern numbers, and the effect of
     `Tc`/`Tw`/`Tz` within one show). Covered by the raster guard ALONE,
     which revision 9 got wrong: it argued a kern difference surfaces in a
     later show, but measurement says otherwise. In 010's reader.pdf, 54
     interior pages carry 360 text objects and 1488 shows, and **zero**
     shows inherit a previous show's advance, because `Td`/`TD`/`T*` reset
     the text matrix from the line matrix and discard it. Every line is
     independently positioned, so the raster guard is the sole check on
     where glyphs sit inside a line.
     This is not a hypothetical residue: WP-1.6 measured a SYSTEMATIC
     engine difference here. WeasyPrint breaks on `PangoRectangle.width`,
     an INTEGER count of 1/1024 px, while Typst sums exact font units, so
     the two place glyphs within a line at steadily diverging positions,
     one-sided at 0.000173 pt per glyph, mean drift 0.010476 pt and max
     0.017432 pt over 899 body lines. Tier E cannot see any of it.
     **What the gate therefore claims about intra-line placement, stated
     plainly because "renders the same" is the sentence at stake**: every
     line starts at the same point, carries the same string, the same
     glyph count, font, size, colour and matrix, and the rasterized page
     differs nowhere beyond a bound derived to accommodate that measured
     drift. Where individual glyphs sit inside a line is verified
     photometrically, not geometrically. The drift is 0.017 pt at worst,
     which is 0.07 px at 300 dpi and 0.57 dots on a 2400 dpi imagesetter,
     so it is below the resolution of any device the magazine is printed
     on. That is the argument for absorbing it in the bound rather than
     failing on it, and it is recorded here as a decision rather than left
     to whatever the instrument happens to measure.
     Recording per-glyph positions instead would false-fail on exactly this
     drift, which is why the guard carries it, why WP-0.2f's floor must be
     derived to include it, and why WP-0.2f's ceiling must be measured
     against a kern fixture.
  2. **glyph substitution preserving both count and advance** (a stylistic
     alternate, say). The glyph count catches the ligature class, the case
     actually observed; an equal-count equal-advance substitution remains
     raster-only. Closing it properly means mapping codes to GIDs through
     the shared vendored face, which the font-file digests already make
     possible; it is not worth doing until something needs it.
  3. **optional content and marked-content groups**. `BMC`/`BDC`/`EMC`/
     `MP`/`DP` are no-ops in the tracer, so content a viewer would hide
     appears as painted. Neither engine emits OCGs today: latent, not live.
     If either starts, this becomes a fail-loud case, not a silent one.
  4. **annotation appearance streams**. Annotations are compared by
     subtype, rect and destination, not by their `/AP`. Links draw nothing
     in this design; a bordered annotation would reach the raster guard.
  Deliberately out of scope rather than blind: `/PageLabels` and other
  viewer-only metadata, which no printed page shows.
- **raster guard**: both PDFs rasterized at 300 dpi by the configuration
  WP-0.2f selects and parity.yaml pins; every differing pixel within
  `parity.yaml tiers.e.raster_bound.value`. The bound is derived, never
  chosen, and WP-0.2f must satisfy **both** constraints or fail loud:
  - **reachable**: at least the max per-channel delta measured from the
    perturbation fixture, so noise the display list cannot see by
    construction cannot fail the gate. The fixture re-emits the oracle
    leg's streams with every coordinate moved to the EXTREME of its own
    quantization bucket, once toward each edge (two deterministic runs,
    floor = the max of the two), asserting display-list equality both
    times. Two earlier attempts at this were both wrong: revision 8
    perturbed within half a quantum, which understates the worst case by
    half, since two coordinates that quantize equal share a bucket 0.01 pt
    wide and can differ by nearly all of it; revision 9 moved each
    coordinate to a RANDOM point in its bucket, which is a sample rather
    than a bound, understates the maximum over 24452 operands, and makes
    the result seed-dependent, so "derived, never chosen" was untrue. The
    extremes are realizable (each coordinate is independent) and
    reproducible by anyone;
  - **meaningful**: comfortably less than the smallest MAXIMUM. Each
    blind-spot fixture produces a max per-channel delta (most of its pixels
    are unchanged, which is why the minimum is always 0 and meaningless);
    the ceiling is the smallest of those maxima, because that is the
    quietest blind-spot fault the guard still has to flag.
  - **margin**: ceiling >= 2x floor, recorded as a ratio. A bare
    `floor < ceiling` is satisfied by 7 against 8 while leaving no room for
    content that differs from 010 (another edition, a different body size,
    a figure-heavy page), and the squeeze would then be discovered on real
    work rather than here. Below 2x is `blocked`, same as a collapsed
    window.
  Revision 8 assumed one pinned rasterizer would satisfy both. It does not:
  `pdftoppm` grid-fits glyphs through FreeType, which turns sub-quantum
  noise into whole-pixel stem flips (241/255 measured, `-aa no` unchanged),
  collapsing the window. WP-0.2f's job is to find a configuration that
  reopens it (candidates: a non-hinting rasterizer such as MuPDF's `mutool
  draw`; supersampling with `pdftoppm` and box-downsampling, which bounds a
  grid-fit flip to a fraction of an output pixel; any other configuration
  that measures well), and to record the winning configuration, both
  measurements and the resulting bound. No configuration satisfying both is
  `Status: blocked` and a plan revision.
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
| Glyph advance quantization (WeasyPrint breaks on `PangoRectangle.width`, an integer count of 1/1024 px; Typst sums exact font units) | RESOLVED as to mechanism by WP-1.6: systematic and one-sided at 0.000173 pt per glyph, mean drift 0.010476 pt, max 0.017432 pt, and 604 of 899 body lines exceed the 0.01 pt quantum. Two distinct consequences, do not conflate them. (a) LINE BREAKING: exactly one line of 899 flips, block 135; fixed by widening the Typst body column to WP-1.7's measured midpoint. (b) INTRA-LINE GLYPH POSITIONS: invisible to the display list at show-level granularity, so the raster guard is the only observer and WP-0.2f's floor must be derived to include it. do not chain WP-1.1's 0.009897 pt to these figures: it was measured with hyphenation ON over 1402 lines, WP-1.6's over 899 with it OFF, and drift accumulates per glyph, so they describe different line populations rather than different methods (rule 9) |
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
   serial regardless of the graph: (a) Cargo-file owners, (b)
   `mag/src/typeset/**` or `mag/src/render.rs` owners, (c) `mag/src/parity*`
   owners. Acceptance includes the verifier running
   `git diff --name-only <base>` against the Owns list. A WP diff touching
   any `evidence/*.verify.md` or `baseline.json` is rejected by the
   orchestrator before a verifier is spawned, except a WP whose Owns names
   baseline.json explicitly (WP-0.2a: schema and empty state; WP-5.4g:
   cover-page seed rows); only verifiers write those otherwise.
2. **Evidence.** A WP is done when its verification commands exit 0 AND it
   has written `meta/verification/evidence/WP-<id>.md` with sections:
   `## Base` (the commit branched from), `## Commands`, `## Tool versions`,
   `## Metrics`, `## Verdicts` (sha256 + tier summary of every verdict.json;
   "attach a verdict" means this), `## Residuals`, `## Status` (`done`,
   `blocked`, `awaiting-fran`).
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
  the zero-diff check; WP-0.2f supplies its bound);
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
  difference leaves page dimensions equal, so today it would reach only the
  raster guard.
- Verify: 010 A-vs-A and A-vs-B unchanged in pass/fail with cardinalities
  reported and the navigation clause showing 0 outlines, 0 Title, 0 Lang,
  84 links; a fixture with `/Rotate 180` on one side FAILS the boxes
  clause; verdict stays byte-deterministic.

## Phase 1: feasibility spikes (throwaway code, binding numbers)

Preamble (binds per rule 8): spike code lives uncommitted in the working
tree or scratchpad; each WP owns only its evidence file. Instrumenting
`src/magazine/` uncommitted is sanctioned here only, `git status` clean at
WP end. Verifier acceptance is the rule-3 evidence-consistency audit. A
failed spike reports `awaiting-fran` with numbers, never an improvised
fallback.

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
WP is scored on its named `page_sets:` entry. Verification, identical for all: `mag parity
010` green against `baseline.json` (no page regresses; raises are the
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
  raising it, re-derives WP-0.2f's reachability floor from the real
  Typst-vs-WeasyPrint pair that now exists, and fails loud if it exceeds
  the synthetic floor: that would mean a divergence outside Tier E's
  enumeration, which is a plan revision rather than a wider bound.
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

**A corpus-based oracle proves only what the corpus contains.** This is the
single most repeated lesson of the execution so far. Edition 010 has no
padded containers, which hid WP-5.1a's defect; no explicit ports and no
non-printable characters, which hid WP-5.1b's two and WP-5.1c's one. So
every port WP must state in evidence **which branches of its source module
the corpus cannot reach**, and cover those by fixture. WP-5.1c did this
well for the manifest's refusal branches and badly for character classes,
and the character class is what bit. Enumerate by reading the Python for
branches, not by reading the corpus for cases.

**A helper that exists twice will drift.** Three of the six rejections in
this run came from one behavior living in two places: WP-5.1c reintroduced,
by copying, the exact `py_repr` defect WP-5.1b had already been rejected
for and fixed, into the module with the widest exposure. A port WP may not
copy a helper out of another model module. Import it, or, where rule 1's
Owns boundary genuinely forbids that, add a test asserting the two copies
agree on a shared case list and say in evidence why importing was not
possible. WP-5.1d then consolidates.

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
- **WP-5.2 booklet imposition** (`booklet.py`): owns `mag/src/impose.rs`.
  Oracle: impose the same 010 reader.pdf both ways; display-list equality
  and raster zero-diff per sheet, spread order text identical. Zero-diff is
  the right bar here because both implementations place the same page
  content by the same arithmetic; a sub-quantum difference means the
  arithmetic diverged and must be explained in evidence, never absorbed by
  WP-0.2f's bound.
- **WP-5.3a critic raster metrics** (`image_contrast.py`,
  `concurrency.py`'s role): owns `mag/src/critic/metrics.rs`. Oracle: 010
  metric values within `parity.yaml critic_metric_tolerances:` (fixed by
  WP-0.2d; this WP never authors tolerances).
- **WP-5.3b critic rules** (`render_critic.py`): owns
  `mag/src/critic/rules.rs`. Oracle: render-critic.json equality on 010
  over {result, issue codes, severities, pages, spread tables}; metrics
  sitting near a decision threshold get near-threshold fixtures.
- **WP-5.3c critic faults**: owns `mag/tests/critic_*`. Fault suite:
  swapped spread, missing tail band, low-ppi figure; both critics emit the
  same issue codes.
- **WP-5.3g comparator switch (comparator WP)**: owns `mag/src/parity.rs`
  + `parity.yaml`: the Typst leg's critic verdict (Rust critic) joins
  Tier S.
- **WP-5.4 cover compiler** (`cover.py`): owns `mag/src/cover/`. Depends
  on WP-5.1c (consumes the Rust Edition model); needs no typst text stack
  (covers are fontTools glyph outlines rasterized via resvg, placed by
  reportlab). Backend decided in-WP, recorded. Oracle: display-list equality
  plus raster agreement within WP-0.2f's derived bound for front/back cover
  PDFs in 010's cover.layout mode, plus fixture editions covering the other
  modes (framed, footer_caption, honored_plate). The bound applies here for
  the same reason it applies to the engines: two different generators place
  outlines at coordinates that can differ below the quantum, and a
  grid-fitting rasterizer turns that into whole-pixel flips.
- **WP-5.4g comparator switch (comparator WP)**: owns `mag/src/parity.rs`
  + `parity.yaml` + `baseline.json` cover-page seed rows: the compared
  artifact becomes `reader.pdf` end to end. Gated on WP-3.7 + WP-5.4.
- **WP-5.5 preflight + package + web** (`preflight.py`, `package.py`,
  `web_edition.py`, `html_edition.py`): owns `mag/src/package/`,
  `mag/src/web/`. Oracle: byte-identical `web/` tree files, SHA256SUMS,
  preflight.json, printing instructions, edition-manifest.json for 010;
  archives compare per-entry (name order, mode, timestamp, CRC32,
  uncompressed bytes), never whole-file (zlib vs flate2 streams differ
  legitimately). `html_edition.py`'s interior-HTML role dies with the
  oracle; only the web path is ported. The byte-identical `web/` oracle is
  sound because web HTML is byte-deterministic across renders, which
  WP-0.0c established with a third control render.
- **Port the string matches as structural tests** (residual from WP-0.0c):
  `web_edition.py` recognizes its own markup by exact tag strings and by
  regexes keyed to exact attribute order (`_PRINT_ONLY_LINE`,
  `_SOURCE_LINK_LINE`, and the opener match at line 262 that blocked
  WP-0.0c). Any future attribute on a figure, a source link or a closing
  plate silently drops web content the same way the opener attribute
  dropped nine QR links. The Rust port must test structure, not the
  spelling of a tag, and its fixtures must include a tag carrying an extra
  unrelated attribute.
- **WP-5.6 native render_edition**: owns `mag/src/render.rs`,
  `mag/src/typeset/**` glue (serial per rule 1b; after WP-3.7). Depends:
  WP-2.3, WP-3.7, WP-5.2, WP-5.3b, WP-5.4, WP-5.5. Target: `--engine
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
WP-0.2e -> WP-0.2f -> WP-0.2g -> WP-0.2d matrix re-derivation
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
WP-3.5 + WP-0.2f -> WP-3.0g -> WP-3.7          (the ratchet cannot be
                                                raised to Tier E before the
                                                raster bound exists)
WP-5.2, WP-5.3a, WP-5.7                        (parallel with Phase 2/3)
WP-5.3a -> WP-5.3b -> WP-5.3c -> WP-5.3g
WP-5.1c -> WP-5.4;  WP-3.7 + WP-5.4 -> WP-5.4g
WP-5.1c -> WP-5.5
WP-2.3 + WP-3.7 + WP-5.2 + WP-5.3b + WP-5.4 + WP-5.5 -> WP-5.6
WP-3.7 + WP-5.3g + WP-5.4g -> WP-4.1 -> WP-4.2
WP-3.7 -> WP-4.0g -> WP-4.2
WP-5.6 -> WP-4.2
WP-4.2 -> WP-4.3 (MANDATORY, WP-1.3 chose (b)) -> shipped edition
       -> WP-6.1 (Fran gate)
WP-5.7 -> WP-6.1
Serialization overrides (rule 1): Cargo-file owners pairwise serial;
typeset/render.rs owners pairwise serial; mag/src/parity* owners pairwise
serial.
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
| `src/magazine/image_contrast.py` | ported, WP-5.3a |
| `src/magazine/concurrency.py` | absorbed (rayon or std), WP-5.3a |
| `src/magazine/cover.py` | ported, WP-5.4 |
| `src/magazine/preflight.py` | ported, WP-5.5 |
| `src/magazine/package.py` | ported, WP-5.5 |
| `src/magazine/web_edition.py` | ported, WP-5.5 |
| `src/magazine/html_edition.py` | web path ported WP-5.5; interior-HTML path dies with the oracle |
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
