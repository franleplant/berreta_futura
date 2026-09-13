# Typst parity and the full-Rust migration

Status: **proposed**, 2026-09-12. Companion to `rust-rewrite.md` (which moved
orchestration to Rust and left the renderer in Python). This plan finishes the
job: a Typst-based renderer implemented in Rust inside `mag`, proven equivalent
to the WeasyPrint renderer by rendering the same editions with both and
comparing until they match, then porting every remaining Python module to Rust
and deleting `src/magazine/`.

The plan is written to be executed by independent subagents. Every work
package (WP) is a self-contained brief: what must be provably true when it is
done (the verification target), the work, and the exact verification process.
A subagent gets the WP text, the repo, and nothing else.

## End state

- `mag render <NNN>` typesets the A5 reader with an embedded Typst engine,
  natively in Rust. No Python in the repo.
- The Typst output has been proven equivalent to the WeasyPrint output on a
  frozen corpus of editions, page by page, through the parity ladder below,
  and Fran has signed off on the final side-by-side proof.
- `measure_article` / `measure_edition` / `render_edition` are native `mag`
  operations; the JSON bridge and `uv` are gone.
- Booklet imposition, cover compilation, render criticism, preflight,
  packaging, and the web edition are Rust, each proven against its Python
  original as the oracle before that original is deleted.

## What "EXACTLY the same" means (the parity ladder)

Two different layout engines never produce byte-identical PDFs: object
ordering, font subsetting, and compression differ even when every glyph sits
at the same coordinate. "Exactly the same" is therefore defined at the level
that matters, the printed page, and it is strict:

**Tier S (structural, exact, no tolerance)** for every corpus edition and
language:

- identical total page count and identical `toc`, `article_pages`,
  `editorial_pages`, and `article_opener_fits` in the layout result
- per-page extracted text identical after normalization (see Normalization)
- code blocks byte-exact against the captured source, both engines
- every figure and extract on the same page in both outputs
- render-critic result `pass` for both outputs

**Tier G (geometric, ratcheting tolerance)** per page:

- same line count per prose block; per line, first-glyph x and baseline y
  within tolerance; figure/ornament boxes within tolerance
- ratchet: G1 = 2.0 pt, G2 = 0.5 pt, G3 = 0.1 pt

**Tier V (visual, ratcheting tolerance)** per page, both PDFs rasterized by
the same `pdftoppm` at 300 dpi, pixels counted as differing when any channel
delta exceeds 24/255:

- ratchet: V1 = differing pixels below 1.0% of page, V2 = below 0.1%,
  V3 = below 0.02% and no 4-connected differing cluster larger than 20 px

**Tier F (Fran)**: a proof sheet interleaving both renders page by page at
original resolution, approved by Fran. Approval is per corpus snapshot; a new
render invalidates it.

"EXACTLY the same" = Tier S + G3 + V3 + F on the whole frozen corpus. The
ratchets exist so early WPs can land at G1/V1 and later WPs tighten; the flip
to Typst as default happens only at the full standard. If a specific residual
(one hyphenation point, one justification micro-space) proves irreducible at
G3/V3, it is listed in the parity report with its cause, and only Fran may
accept it; a subagent never may.

Known divergence sources and how each is neutralized during parity:

| Source | Treatment |
|---|---|
| Line breaking (Typst optimizes, WeasyPrint is greedy) | `par(linebreaks: "simple")` in the Typst template for the parity phase |
| Hyphenation dictionaries (Pyphen vs hypher) | Typst hyphenation off; the content pipeline inserts soft hyphens at the exact points WeasyPrint used, read from the oracle's line boxes is forbidden (that would be circular), so instead: WP-1.3 decides between (a) porting Pyphen's dictionary lookup for en/es to the content pipeline and (b) disabling hyphenation in BOTH engines for the parity corpus via a CSS/template switch, comparing that way, and re-enabling native hyphenation after the flip as a Fran-approved deliberate change. Default expectation is (b): parity must never be scored against a moving target |
| Text shaping (Pango+HarfBuzz vs rustybuzz) | same vendored TTFs; WP-1.1 proves advance-width parity before any layout work |
| Justification space distribution | measured in WP-1.2; if Typst distributes differently, the parity template uses ragged-right only if WeasyPrint also does; if the design justifies, G3 tolerance applies to interior word positions but line breaks stay exact |
| PDF metadata (CreationDate, Producer, trailer ID) | stripped by comparator normalization, never compared |
| Font subset names, object order, compression | never compared; only text, geometry, raster |

After the flip, Typst-native improvements (optimized line breaks, native
hyphenation) are separate, Fran-approved design changes with their own
before/after proof sheets. They are out of scope here.

## Normalization (used by every text comparison)

- extraction by one pinned `pdftotext` (poppler) binary for both PDFs
- Unicode NFC, collapse runs of whitespace to one space, strip soft hyphens
  and the hyphenate-character at line ends by rejoining the split word
- strip page footers/folios only if a WP proves they differ solely by
  position, never by content; content differences are always failures

## The oracle is frozen

Parity is meaningless against a moving target.

- The WeasyPrint renderer, `pyproject.toml`, and `uv.lock` are frozen for the
  life of this plan except for WPs explicitly named below. Any behavioral
  change to `src/magazine/` invalidates golden evidence and requires
  regenerating it in the same WP.
- The corpus is pinned in `meta/verification/corpus.yaml`: edition ids,
  languages, the git commit of the content, and the SHA256 of every staged
  input file. WP-0.1 creates it.
- Golden outputs (PDFs) are regenerated on demand from the pinned commit, not
  stored in git; their normalized-text digests, layout JSONs, and critic
  reports (small) are stored under `meta/verification/golden/` so drift is
  detectable without a rebuild.
- Tool versions (python, uv, weasyprint, poppler, typst crates, rustc) are
  recorded in every evidence file. The oracle machine is Fran's; CI is not a
  goal.

## Architecture

- The Typst engine lives in `mag` as a native module (`mag/src/typeset/`),
  embedding the `typst` + `typst-pdf` crates behind a `World` implementation
  that serves the vendored fonts (copied to `mag/assets/fonts/`, checked
  byte-identical to `src/magazine/assets/fonts/` while both exist) and
  in-memory sources. No `typst` CLI subprocess.
- `mag render <NNN> --engine weasyprint|typst|both` selects the path.
  `weasyprint` = today's bridge call, unchanged. `typst` = native. `both` =
  render both from identical staged inputs, then run the comparator and print
  the verdict path. Default stays `weasyprint` (from `magazine.toml
  [render] engine`) until the flip WP.
- The comparator is `mag parity`: `mag parity <NNN> [--lang en]` renders both
  and writes `output/parity/<NNN>/<lang>/verdict.json` (machine) and
  `report.html` (side-by-side pages, diff heatmaps, per-line tables).
  `mag parity --corpus` runs the whole pinned corpus and exits nonzero below
  the enforced tier. Enforced tier and thresholds live in
  `meta/verification/parity.yaml`; the file states in a header that changing
  it requires Fran.
- Comparison during engine development targets `interior.pdf` (the renderer's
  own output). Covers come from `cover.py` and are merged by shared code, so
  they are identical by construction until the cover port (WP-5.4), after
  which `reader.pdf` is compared end to end.
- The Typst engine emits the same layout result the bridge reports
  (`RenderLayout`: toc, article_pages, editorial_pages, figure placements
  with box_points, frame usage, terminal balance, opener fits) so
  `measure_article` keeps feeding the produce loop identical numbers.

## Subagent execution protocol

Every WP below is executed by one subagent with no other context. Standing
rules for all WPs:

1. **Owned paths.** A WP may create/modify only the paths its brief lists.
   Two WPs run in parallel only if their owned paths are disjoint.
2. **Evidence.** A WP is done when its verification commands exit 0 AND it
   has written `meta/verification/evidence/WP-<id>.md`: commands run, tool
   versions, metrics achieved, and any residuals. No evidence, not done.
3. **The comparator and an engine never change in the same WP.** Comparator
   changes get their own WP with a justification; this is the anti-gaming
   rule. Thresholds and tier definitions change only via Fran.
4. **Repo rules apply**: `cargo fmt`, `cargo clippy -D warnings`,
   `cargo test` (includes `tools/nocomments.py`), `uvx ruff` for touched
   Python, no comments, no U+2014, hooks installed. A WP that leaves any of
   these red is not done.
5. **Fail loud.** A WP that cannot meet its target reports the miss and the
   measured gap in its evidence file and stops; it never weakens a check,
   skips a corpus entry, or marks itself done with a workaround.
6. Each WP brief handed to a subagent = the WP section verbatim + this
   protocol section + the parity-ladder section.

## Phase 0: instrument and freeze (no engine work)

### WP-0.1 corpus freeze

- Owns: `meta/verification/corpus.yaml`, `meta/verification/golden/`,
  evidence file.
- Verification target: a pinned corpus of every edition+language that renders
  cleanly with WeasyPrint today, with golden digests recorded, and a
  determinism proof for the oracle itself.
- Work: for each edition in `editions/`, attempt `mag render <NNN>`
  (weasyprint, both configured languages). Record which succeed. For each
  success, render twice into scratch and compare: normalized per-page text,
  layout JSON, critic JSON must be identical across the two runs; list any
  nondeterministic fields found (timestamps etc.) and add them to the
  comparator normalization spec (a section in corpus.yaml for WP-0.2 to
  implement). Write corpus.yaml (edition, languages, content commit, input
  SHA256s) and golden digests.
- Verify: rerunning the freeze script reproduces identical digests; corpus
  contains at least editions 004 and 009; evidence lists any edition that
  fails to render and why (those are excluded, not fixed, unless the failure
  is a regression on main, which is reported to Fran and blocks).

### WP-0.2 comparator: `mag parity`

- Owns: `mag/src/parity.rs` (and submodules), `mag/src/main.rs` (subcommand
  registration only), `meta/verification/parity.yaml`, evidence file.
- Verification target: `mag parity` implements Tier S, G, V exactly as
  specified, proven by self-test: oracle vs oracle scores perfect, and every
  check catches a seeded fault.
- Work: implement the comparator over two already-rendered output
  directories (`mag parity --pre-rendered <dirA> <dirB>` mode first; the
  engine-invoking mode arrives with WP-2.x). Text via pinned `pdftotext`,
  line geometry via `pdftotext -bbox`-style word boxes, raster via
  `pdftoppm -r 300`, cluster analysis in Rust. Emits verdict.json +
  report.html. Write parity.yaml with the tier/threshold table from this
  plan.
- Verify: (a) WeasyPrint output vs a second WeasyPrint run of the same
  edition scores Tier S + G3 + V3 (this calibrates that thresholds tolerate
  oracle self-noise, which should be zero after WP-0.1 normalization);
  (b) a fault-injection suite: swap two words, move a line by 0.3 pt, shift
  a figure one page, recolor 30 px, drop a hyphen; each seeded fault is
  flagged by the intended tier and only that tier. Both suites run under
  `cargo test` where feasible or a documented script otherwise.

## Phase 1: feasibility spikes (throwaway code, binding numbers)

Spike code lives in `mag/src/bin/` or scratch and may be deleted; the
evidence files and go/no-go numbers are the deliverable. A failed spike does
not improvise a fallback: it reports, and Fran picks from the fallback column.

### WP-1.1 shaping parity

- Target: for the vendored faces (Inter 4 weights, Source Serif 4 SmText
  regular/italic/bold + Display Semibold, Archivo Condensed Bold, Geist Mono),
  rustybuzz (as used by Typst) and Pango/HarfBuzz (as used by WeasyPrint)
  produce advance widths agreeing within 0.01 pt per line on real corpus
  text.
- Work: extract every (font, size, text) line WeasyPrint lays out for one
  corpus edition (the adapter already walks boxes; add a scratch dump, do
  not commit engine changes), shape the same strings with rustybuzz at the
  same sizes, compare cumulative advances. Include es text and ligature/kern
  cases.
- Verify: evidence file with the distribution of deltas, worst offenders,
  and a go/no-go. Fallback if no-go: identify the divergent OpenType feature
  set and align Typst's feature flags; escalate to Fran only if alignment is
  impossible.

### WP-1.2 line-break and justification parity

- Target: given identical measure, font, size, and greedy breaking, Typst
  (`linebreaks: "simple"`, hyphenation off) reproduces WeasyPrint's exact
  break points on ≥ 99.5% of corpus paragraphs, and the treatment of the
  residual is understood; justified interior spacing deltas quantified.
- Work: minimal Typst document replicating one article's body-text geometry
  (page size, margins, font, size, leading from `assets/weasyprint-a5.css`);
  compare line-by-line against the oracle with hyphenation disabled on both
  sides.
- Verify: evidence with break-point match rate and interior-word max delta.
  Fallback: forced breaks are NOT an acceptable mechanism for the final
  engine; if simple linebreaking cannot converge, Fran decides between
  tolerance acceptance at Tier G and abandoning pixel-level parity for a
  page-level standard.

### WP-1.3 hyphenation decision

- Target: a decided, Fran-approved mechanism for hyphenation during parity.
- Work: measure how much corpus text hyphenates today (the adapter already
  reports hyphen ladders); prototype option (b) from the divergence table:
  render the oracle with `hyphens: manual` via a temporary CSS switch and
  quantify layout shift (pages gained, cap violations). If shift is zero to
  negligible, recommend (b); otherwise scope (a), porting Pyphen dictionary
  lookup to Rust for en/es and injecting soft hyphens in both engines'
  input.
- Verify: evidence with the measured shift and a one-page recommendation;
  Fran's choice recorded in parity.yaml before Phase 3 starts. If (b) is
  chosen, the CSS switch becomes the one sanctioned oracle change, applied in
  its own WP that also regenerates WP-0.1 goldens.

### WP-1.4 Typst measurement interface

- Target: proof that the embedded Typst crates expose per-element positions
  sufficient to emit `RenderLayout`: page and box of every paragraph line,
  figure, heading, ornament, at sub-0.1 pt precision, from Rust, without
  parsing the PDF.
- Work: spike a `World`, compile a two-page document with a placed image and
  a code block, walk the laid-out frames, print positions; confirm they match
  the PDF (rasterize and overlay).
- Verify: evidence with the API path used (frame introspection vs `query`)
  and its stability across the pinned typst crate version.

## Phase 2: the Typst engine skeleton

### WP-2.1 content pipeline: edition.yaml + manuscripts to typst input

- Owns: `mag/src/typeset/content.rs` and fixtures under `mag/tests/`.
- Target: for every corpus edition, the pipeline turns staged inputs
  (edition.yaml, manuscripts, extracts, figures) into a deterministic
  in-memory Typst source tree; the plain-text projection of that tree equals
  the normalized text of the golden output (Tier S text, pre-layout).
- Work: markdown parsing (comrak or the existing Rust markdown path if one
  exists in `mag`), extracts resolution against captured sources with the
  same ambiguity refusals `manifest.py` enforces, figure/caption/anchor
  wiring, es variant loading.
- Verify: a `cargo test` comparing the projection against golden normalized
  text for the corpus; extracts byte-exactness test; refusal tests
  (ambiguous marker, verbatim-duplicated run) mirroring the Python
  behaviors, with the Python behavior demonstrated in evidence as the spec.

### WP-2.2 the reader template

- Owns: `mag/src/typeset/template.rs` (or `.typ` assets under
  `mag/assets/typeset/`), evidence.
- Target: `mag render <NNN> --engine typst` produces an interior.pdf for one
  designated corpus edition (en) with the full page architecture present:
  A5 geometry, margins, body/heading/code/quote styles, folios, article
  openers, TOC, page caps enforced, figures placed by anchor. Parity NOT yet
  required; target is `mag parity` runs end to end and reports honest
  numbers, and Tier S page-count/TOC/article-pages already hold.
- Work: transcribe `assets/weasyprint-a5.css` and the adapter's constants
  (`_PAGE_HEIGHT_POINTS`, frame insets, plate frames, tail ornament rules)
  into the template; every transcribed value cites its CSS/adapter origin in
  the evidence file's mapping table (not in code comments).
- Verify: `mag parity <NNN> --lang en` produces a verdict; Tier S structural
  fields listed above pass; evidence includes the CSS-to-template mapping
  table and the current G/V numbers as the Phase 3 baseline.

### WP-2.3 layout result and measure operations

- Owns: `mag/src/typeset/layout.rs`, `mag/src/render.rs` (engine dispatch),
  evidence.
- Target: `--engine typst` emits the full layout JSON (RenderLayout shape)
  and supports `measure_article`/`measure_edition` natively; on the corpus,
  Typst-reported `article_pages` and `article_opener_fits` equal the
  bridge-reported ones wherever Tier S already passes.
- Verify: corpus loop comparing both engines' layout JSONs field by field;
  fields gated by unfinished parity are listed as pending in evidence, never
  silently skipped.

## Phase 3: convergence

One WP per feature area, each with the same shape: tighten the Typst template
until the corpus passes the named tier for the pages that feature owns. The
per-WP verification is always `mag parity --corpus` filtered to the relevant
pages, plus no regression anywhere else (full-corpus verdict attached to
evidence). Order matters; each WP starts from the previous baseline.

- **WP-3.1 body text**: prose-only pages to Tier S text + G2. This is where
  shaping/breaking spikes pay off; expect font-size/leading/measure bugs.
- **WP-3.2 headings, openers, TOC**: opener pages to G2; opener-fit booleans
  exact.
- **WP-3.3 code blocks and extracts**: byte-exact text, syntax highlighting
  colors matched to the CSS palette, G2 boxes. Highlighting engines differ
  (pygments vs syntect); the template pins a token-color map derived from
  the rendered oracle, documented in evidence.
- **WP-3.4 figures, plates, ornaments**: placement pages G2, box_points
  within G2, effective_ppi equal within 0.5.
- **WP-3.5 quotes, footers, folios, running furniture**: G2 everywhere.
- **WP-3.6 Spanish corpus**: everything above at the same tier for es.
- **WP-3.7 the G3/V3 ratchet**: raise parity.yaml enforcement to G3+V3 and
  burn down the residuals page by page. This WP's evidence is the residual
  ledger: every page not at V3, its diff cluster, its cause. It ends when
  the ledger is empty or every remaining line is Fran-accepted.

## Phase 4: the gate and the flip

### WP-4.1 full parity gate

- Target: `mag parity --corpus` green at Tier S+G3+V3, both languages, from
  a clean checkout; proof sheets generated for Tier F.
- Work: none but the run; produce `output/parity/proof/` with interleaved
  A/B pages at original resolution and the final verdict.json.
- Verify: the run itself, twice, identical verdicts. Then Fran reviews the
  proof sheets. Fran's approval is recorded in
  `meta/verification/evidence/WP-4.1.md` by Fran or quoted verbatim.

### WP-4.2 the flip

- Owns: `magazine.toml`, `mag/src/render.rs` default, docs
  (`docs/RENDERER_MIGRATION.md` superseded by a new transition record),
  evidence.
- Target: `engine = "typst"` is the default; `weasyprint` remains selectable
  as the rollback exactly as `reportlab` did last time; `mag render` output
  tree is unchanged for downstream consumers (package, web, critic all still
  run through the bridgeless path only after their own Phase 5 WPs; until
  then the typst path feeds interior.pdf into the existing Python
  cover/critic/package steps via the bridge's render_edition with a
  `prerendered interior` input, OR the flip waits for Phase 5; WP-4.2's
  first task is to pick the simpler wiring and record it).
- Verify: render 009 and 010 end to end with the new default; critic passes;
  Fran prints one booklet.

## Phase 5: port the rest of Python to Rust

Each WP: port one module, prove equality against the Python original on the
corpus, then the original stays in place until WP-6.1 deletes them together.
Independent of Phase 3 up to WP-5.4; may run in parallel with it (disjoint
owned paths).

- **WP-5.1 manifest + records + media schema** (`manifest.py`, `records.py`,
  `media_schema.py`, `document_structure.py`, `reader_text.py` folding):
  oracle = `edition-manifest.json` and the bridge's validation refusals.
  Verify: byte-identical edition-manifest.json on the corpus; a refusal
  matrix test (every ValidationError the Python loader raises, provoked by a
  fixture, gets an equivalent Rust refusal; matrix enumerated in evidence).
- **WP-5.2 booklet imposition** (`booklet.py`): oracle = impose the same
  reader.pdf both ways; verify page-wise V3 raster equality of
  booklet-a4*.pdf and identical spread order text (Tier S text per sheet).
- **WP-5.3 render critic** (`render_critic.py`, `image_contrast.py`): oracle
  = normalized render-critic.json equality on the corpus AND a
  fault-injection suite (reuse WP-0.2's seeded faults plus critic-specific
  ones: swapped spread, missing tail band, low-ppi figure); both critics
  must emit the same issue codes.
- **WP-5.4 cover compiler** (`cover.py`): draws with Rust (embed via the
  Typst engine or a direct PDF drawing crate; decide in-WP, recorded in
  evidence); oracle = V3 raster parity of front/back cover PDFs across
  every corpus edition and every cover.layout mode (framed, footer_caption,
  honored_plate).
- **WP-5.5 preflight + package + web edition** (`preflight.py`,
  `package.py`, `web_edition.py`, `html_edition.py` web path): oracle =
  byte-identical web/ tree, package.zip, SHA256SUMS, preflight.json,
  printing instructions on the corpus (all are deterministic text/zip
  outputs; the PDFs inside are the already-proven ones).
- **WP-5.6 native render_edition**: wire cover, critic, package, web into
  the `--engine typst` path so `mag render` no longer spawns the bridge for
  any operation; verify by rendering the corpus with the bridge disabled
  (uv removed from PATH) and re-running `mag parity --pre-rendered` against
  bridge outputs, all tiers green.

## Phase 6: decommission

### WP-6.1 delete Python

- Owns: deletion of `src/magazine/`, `pyproject.toml`, `uv.lock`, ruff
  config, `mag-render-adapter` references, `tools/*.py` that only served the
  renderer (audit each; `nocomments.py` stays if the hook still needs it,
  else its check is ported to `cargo test`), `.githooks` update, `CLAUDE.md`
  and `docs/` updates, a new transition record superseding
  `docs/RENDERER_MIGRATION.md`.
- Target: `git grep -l "uv run\|weasyprint\|mag-render-adapter"` returns
  only docs/history; `mag render`, `mag parity --pre-rendered` (against
  archived goldens), `cargo test`, and a full 010 render all pass on a
  machine with no Python toolchain for this repo.
- Note: deleting WeasyPrint deletes the rollback. This WP runs only after
  one real edition has shipped on the Typst engine (same acceptance rule as
  rust-rewrite.md: a released edition, not tests).

## Dependency graph

```
WP-0.1 -> WP-0.2 -> WP-1.{1,2,3,4} -> WP-2.1 -> WP-2.2 -> WP-2.3
                                   -> WP-3.1 -> ... -> WP-3.7 -> WP-4.1 -> WP-4.2
WP-0.1 -> WP-5.1 -> WP-5.5
WP-0.2 -> WP-5.2, WP-5.3          (parallel with Phase 3)
WP-3.7 -> WP-5.4 -> WP-5.6 -> WP-4.2 (if flip waits for native path)
WP-4.2 + one shipped edition -> WP-6.1
```

## Risks

- **rustybuzz/Pango disagreement** on some feature of these fonts: caught in
  WP-1.1 before any engine code exists; alignment via feature flags, else
  Fran call.
- **Typst crate API churn**: versions pinned in Cargo.toml; upgrades are
  their own WP with a full parity rerun.
- **The 3,000-line adapter encodes behavior nobody remembers**: the
  CSS-to-template mapping table in WP-2.2 and the residual ledger in WP-3.7
  are the forcing functions; anything unexplained lands on the ledger, not
  under the rug.
- **Oracle drift** while other work continues on main: corpus.yaml pins the
  content commit; `mag parity --corpus` stages from that commit, not the
  worktree.
- **Subagents gaming the gate**: protocol rules 3 and 5; the comparator and
  thresholds are outside every engine WP's owned paths.

## Non-goals

Typst-native typography improvements before the flip, CI infrastructure,
rendering editions outside the frozen corpus during parity, InDesign/Prince
detours, keeping the reportlab engine (it is deleted with WP-6.1 alongside
everything else Python), provenance ceremony of any kind.
