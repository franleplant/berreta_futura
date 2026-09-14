# Typst parity and the full-Rust migration

Status: **proposed**, 2026-09-13, revision 6 (after four critic rounds;
revision 6 removes humans from every pass/fail verification: the gate is
display-list equality plus raster zero-diff, both mechanical. Fran appears
only where the plan itself must change).
Companion to `rust-rewrite.md` (which moved orchestration to Rust and left the
renderer in Python). This plan finishes the job: a Typst-based renderer
implemented in Rust inside `mag`, proven equivalent to the WeasyPrint renderer
by rendering the same editions with both engines and comparing until they
match, then porting every remaining Python module to Rust and deleting
`src/magazine/`.

The plan is executed by independent subagents. Every work package (WP) is a
self-contained brief. Protocol rule 8 defines exactly what a subagent
receives; a WP is done only on verifier acceptance (rule 3), never on its own
say-so.

One standing sanction this plan needs from Fran up front: the verification
scaffolding under `meta/verification/` (corpus pins, golden artifacts,
baselines, evidence files) is temporary migration tooling, deleted with
WP-6.1. It exists despite the repo's no-pinning rule because parity against a
moving target is meaningless; approving this plan approves that exception for
the plan's lifetime.

## End state

- `mag render <NNN>` typesets the A5 reader with an embedded Typst engine,
  natively in Rust.
- The Typst output has been proven equivalent to the WeasyPrint output on a
  frozen corpus of editions, page by page, through the parity ladder below,
  and Fran has signed off on the final side-by-side proof.
- `measure_article` / `measure_edition` / `render_edition` are native `mag`
  operations; the JSON bridge is gone.
- Booklet imposition, cover compilation, render criticism, preflight,
  packaging, the web edition, and capture's PDF transcription helper are
  Rust, each proven against its Python original as the oracle before that
  original is deleted.
- No Python runs anywhere in the pipeline. `tools/*.py` side tools are
  individually dispositioned (ported, deleted, or explicitly kept by Fran) in
  WP-6.1; the module disposition table in Appendix A covers every Python file
  in the repo.

## What "EXACTLY the same" means (the parity ladder)

Two different layout engines never produce byte-identical PDFs: object
ordering, font subsetting, and compression differ even when every glyph sits
at the same coordinate. "Exactly the same" is therefore defined at the level
of the printed and read page, and it is strict.

### The compared artifact

Until the comparator's domain switch (WP-5.4g), the compared unit is the
**interior domain**: pages 2 through n-1 of the oracle's `reader.pdf` versus
pages 2 through n-1 of the Typst engine's `interior.pdf`, with n required
equal (Tier S). This works because the bridge builds `reader.pdf` by
replacing only the outer pages of the interior with the compiled covers
(`replace_outer_pages` in `src/magazine/cover.py`), so interior pages 2..n-1
pass through pypdf untouched in content, and it requires no change to the
frozen oracle. Because the oracle side has passed through a pypdf rewrite and
the Typst side has not, WP-0.2c calibrates merge invariance (see its verify)
before any content-stream comparison is trusted. The Typst engine renders its
interior with the same placeholder outer pages the WeasyPrint interior
carries, so page numbering and folios align. From WP-5.4g on, `reader.pdf`
is compared end to end, covers included.

### Tier S (structural and content, exact, no tolerance)

For every corpus edition and language, over the compared domain:

- identical page count, read from the PDFs with `pdfinfo`, not from
  engine-reported JSON
- per-page MediaBox, CropBox, and TrimBox equal within 0.05 pt
- per-page extracted text identical after normalization (see Normalization)
- **code blocks**, in two halves because a PDF has no bytes to compare: at
  the input level, the fenced runs in each engine's staged input (manuscript
  for the oracle, source-tree projection for Typst) byte-equal the captured
  `library/sources/<id>/article.md` runs; at the PDF level, engine vs engine
  only, per-line word sequences and x-positions inside code-block boxes
  (from `pdftotext -bbox-layout`, or content-stream text runs) identical
  under the code normalization, which preserves internal whitespace.
  PDF-vs-article.md byte comparison is never performed
- every figure and extract on the same page in both outputs
- **color**: the sequence of (text-run, fill color) pairs and the set of
  rule/background fill and stroke colors per page, extracted from the PDF
  content streams, numerically equal after color-space normalization, and
  both PDFs in the same color space family. Rasters cannot see near-black
  ink differences (the body ink is `rgb(5.5% 7.5% 8.5%)`, not black); this
  clause is what catches them
- **navigation**: normalized link-annotation list per page (subtype, rect
  quantized to 0.5 pt, destination page) and the outline/bookmark tree,
  restricted to entries whose destinations land inside the compared domain;
  entries targeting outer pages join at WP-5.4g. Document Title and Lang
  equal; CreationDate/ModDate/Producer/trailer ID stripped and never
  compared
- the oracle's render-critic result is `pass` (guards oracle validity). The
  critic verdict on the Typst output joins Tier S at WP-5.3g; the final gate
  (WP-4.1) requires it

### Tier G (geometric, ratcheting tolerance)

Per page over the compared domain, from `pdftotext -bbox-layout`
(flow/block/line/word structure) emitted by the pinned poppler:

- same line count per prose block; per line, x of the first word box and the
  line box's y within tolerance; figure/ornament boxes within tolerance
- ratchet: G1 = 2.0 pt, G2 = 0.5 pt, G3 = 0.1 pt
- if WP-0.2a finds the extractor's coordinate precision too coarse for G3,
  G3 geometry is measured from the content streams (WP-0.2b machinery)
  instead; the choice is recorded in parity.yaml, once, before Phase 3

### Tier V (visual, ratcheting tolerance)

Per page, both PDFs rasterized by the same pinned `pdftoppm -r 300`; the
comparator hard-fails (never skips) if the two rasters differ in pixel
dimensions. A pixel differs when any channel delta exceeds 24/255; a cluster
is a 4-connected component measured by pixel area:

- ratchet: V1 = differing pixels below 1.0% of the page, V2 = below 0.1%,
  V3 = below 0.02% with a cluster-area cap, AND per-page mean absolute
  channel delta at or below 1/255 (catches large-area uniform shifts that
  per-pixel thresholds ignore)
- V3's numbers are **provisional**: a glyph edge shifted by the 0.4 px that
  G3 still allows can antialias into clusters far larger than any naive
  cap, so WP-0.2d measures cluster-area distributions at seeded offsets of
  0.02/0.05/0.1/0.2 pt and the final V3 thresholds (cluster cap, or
  per-word-box cluster evaluation gated on that page having passed G3) are
  set from that data by the Fran-gated tightening WP-3.0g before WP-3.7

### Tier F (Fran)

A proof sheet interleaving both renders page by page at original resolution
(`mag parity --proof-sheet`, WP-0.2c), with a SHA256 manifest of the sheets.
Approval is per manifest; a new render invalidates it. The approval is
recorded by Fran personally: a commit authored by Fran or a line Fran types
into the evidence file, citing the manifest digest. A subagent transcribing
"Fran approved" is not a record.

**"EXACTLY the same" = Tier S + G3 + V3 + F over the whole frozen corpus.**
The ratchets exist so early WPs land at G1/V1 and later WPs tighten; the
default-engine flip happens only at the full standard. If a specific residual
proves irreducible at G3/V3, it goes on the residual ledger (WP-3.7) with its
cause, and only Fran may accept it; a subagent never may.

### Known divergence sources and their treatment

| Source | Treatment |
|---|---|
| Line breaking (Typst optimizes, WeasyPrint is greedy) | `par(linebreaks: "simple")` in the Typst template for the parity phase |
| Hyphenation dictionaries (Pyphen vs Typst's hypher) | the design hyphenates today (`hyphens: auto` in `src/magazine/assets/weasyprint-a5.css`, with `manual` carve-outs for code, reference lists, name rosters). WP-1.3 measures and recommends; WP-1.5 applies the Fran-approved choice to both engines and regenerates goldens. Parity is never scored against a moving target |
| Justification | the design is ragged-right (no `text-align: justify` in the CSS); WP-1.2 confirms this and the justification contingency is dropped unless the confirmation fails |
| Text shaping (Pango+HarfBuzz vs rustybuzz) | same vendored TTFs; WP-1.1 proves advance-width parity before any layout work |
| Syntax highlighting (pygments vs syntect) | token-boundary and color parity checked at the content-stream level (WP-3.3), never by raster |
| pypdf rewrite noise on the oracle's inner pages | measured by WP-0.2c's merge-invariance calibration; any rewrite-induced stream difference becomes a normalization rule, recorded, before it can be mistaken for an engine diff |
| PDF metadata, font subset names, object order, compression | normalized away or never compared, as listed in Tier S |

After the flip, Typst-native improvements (optimized line breaks, native
hyphenation if it was disabled) are separate, Fran-approved design changes
with their own before/after proofs. They are out of scope here, except the
mandatory post-flip hyphenation proof (WP-4.3, if WP-1.5 chose option (b)).

## Normalization (used by every text comparison)

- extraction by the pinned `pdftotext` for both PDFs
- Unicode NFC; collapse whitespace runs to one space (prose only: inside
  code-block boxes internal whitespace is preserved and compared); rejoin
  words split by a line-end hyphenate character; strip soft hyphens
- folios and running furniture are compared as content like everything else;
  only position differences within the active G tolerance are tolerated
- the machine-readable normalization spec lives in
  `meta/verification/parity.yaml` under `normalization:` with keys
  `strip_pdf_keys`, `whitespace`, `hyphen_rejoin`, `color_space_map`,
  `merge_rewrite_rules` (from WP-0.2c's calibration); the comparator
  implements exactly that spec and nothing more

## The oracle is frozen (mechanically)

- `meta/verification/corpus.yaml` pins: edition ids and languages, the
  content git commit, the run directory per edition (`--run` is always
  passed explicitly, and WP-0.1 asserts each pinned run directory is fully
  git-tracked and clean at the pinned commit; "newest complete run"
  auto-selection is never used in parity work), SHA256 of every staged input
  file including the staged `edition.yaml`, and `oracle_tree_sha`: one
  digest over `src/magazine/**`, `pyproject.toml`, and `uv.lock`.
- `mag parity` embeds in every `verdict.json` the digests of the oracle
  tree, `parity.yaml`, `corpus.yaml`, and `meta/verification/golden/`, and
  **refuses to run** if any differs from the pinned values. (The golden
  digest check activates at WP-0.2a, when normalized digests first exist.)
  Gaming a gate by touching the oracle, the thresholds, the normalization
  spec, or the goldens is therefore a refused run, not a passed one.
- **Zero model calls during parity.** `mag render` invokes a model to patch
  figure anchors that match no run heading (`patch_anchors` in
  `mag/src/render.rs`). WP-0.0 gives render a `--no-model` mode that errors
  instead, and reports the pending-anchor count; every freeze and parity
  render passes it. Corpus entries are frozen with zero pending anchors.
- Golden PDFs are regenerated on demand from the pins; raw extraction dumps,
  layout JSONs, and critic reports live under `meta/verification/golden/`,
  and their normalized digests in `meta/verification/golden/digests.json`
  (computed by WP-0.2a). Regenerating goldens is legal only in a WP whose
  Owns list names `meta/verification/golden/` and whose brief carries a Fran
  gate; there is no "regenerate in the same WP" escape hatch.
- Behavioral changes to `src/magazine/` are forbidden except in the WPs that
  name it under Owns (WP-0.0b and WP-1.5 only). Phase 1 spikes may instrument oracle
  files uncommitted, in the working tree only, provided `git status` is
  clean when the WP ends and no golden or pin is touched; this sentence is
  the sanction protocol rule 1 defers to.
- Tool versions (python, uv, weasyprint, poppler pdftotext/pdftoppm/pdfinfo,
  typst crates, rustc) are pinned in `parity.yaml` under `tools:` at freeze
  time and asserted by `mag parity` at startup. The oracle machine is
  Fran's; CI is not a goal.

## Architecture

- The Typst engine lives in `mag` as a native module (`mag/src/typeset/`),
  embedding the `typst` + `typst-pdf` crates (exact versions decided by
  WP-1.4, recorded in `parity.yaml`, pinned in `mag/Cargo.toml`) behind a
  `World` implementation serving the vendored fonts and in-memory sources.
  Fonts are read directly from `src/magazine/assets/fonts/` while both
  engines coexist (one copy, zero drift risk); WP-6.1 relocates them. The
  faces in play: Source Serif 4 SmText Regular/Italic/Bold + Display
  Semibold, Inter Regular/Medium/SemiBold/Bold, Geist Mono
  Regular/Medium/SemiBold, Archivo Condensed Bold (cover and web edition).
- `mag render <NNN> --engine weasyprint|typst` selects the path; the default
  comes from `magazine.toml [render] engine`, which today is **dead wiring**
  (`mag/src/render.rs` hardcodes `weasyprint`; only `[publication] name` is
  read from the toml); WP-2.0a makes the key real. `weasyprint` = today's
  bridge call, unchanged.
- The comparator is `mag parity`:
  - `mag parity freeze` builds/refreshes `corpus.yaml` pins and golden raw
    artifacts (WP-0.1)
  - `mag parity <NNN> --lang <l> --pre-rendered <dirA> <dirB>` compares two
    output trees (WP-0.2a..c)
  - `mag parity <NNN> [--lang <l>]` stages once from the pins into a git
    worktree at the pinned content commit (the worktree is the cwd for both
    renders; `mag` requires the repo root layout), asserts `--no-model`,
    runs both engines on the identical staged tree, compares (WP-2.0b)
  - `mag parity --corpus` runs the whole pinned corpus and is
    baseline-relative: it exits nonzero if any page scores below its
    `meta/verification/baseline.json` entry, where an entry records the
    achieved tier including which Tier S clauses pass (mid-convergence,
    clauses owned by later WPs legitimately still fail). The absolute
    full-Tier-S bar is enforced only at the WP-4.1 gate
  - `mag parity --proof-sheet` emits the Tier F interleaved sheets plus
    their SHA256 manifest (WP-0.2c)
  - `mag parity <NNN> --set <page_set>` scores one page set for in-WP
    iteration; acceptance always runs the full `--corpus`
  - the oracle render is cached per (edition, language) keyed by
    `oracle_tree_sha` + staged-input digests (WP-0.1's determinism proof is
    the license); verdict.json records the cache key
  - outputs per run: `output/parity/<NNN>/<lang>/verdict.json` (machine) and
    `report.html` (side-by-side pages, diff heatmaps, per-line tables);
    `output/` is gitignored, so durable records are the verdict digests
    embedded in evidence files (rule 2). verdict.json is byte-deterministic:
    no timestamps, durations, hostnames, or absolute paths
- **Ratchet mechanics.** `baseline.json` records, per corpus page, the best
  tier ever achieved. `mag parity --corpus` fails if any page scores below
  its recorded tier; the comparator refuses a baseline edit that lowers any
  entry. Raises are computed and committed only by the verifier (rule 3)
  from its own rerun's verdict. A change that must temporarily regress a
  page (for example a figure fix that reflows prose) lands together with
  its fix in one WP, or waits for a Fran-gated baseline adjustment; the
  serial ordering of Phase 3 makes this workable.
- **Page sets.** Per-WP page-set filters for Phase 3 are derived from the
  golden layout JSONs and written into `parity.yaml page_sets:` by WP-2.0b
  (rules enumerated there), before any Phase 3 WP starts. Engine WPs never
  choose their own scoring pages.
- The Typst engine emits the same layout result the bridge reports
  (`RenderLayout` shape: toc, article_pages, editorial_pages, figure
  placements with box_points, frame usage, terminal balance, opener fits).
  The oracle's toc, opener fits, and figure placements are read from the
  packaged `edition-manifest.json` (toc and opener fits added to it by
  WP-0.0b; today they exist only in-process or in the bridge's stdout rows).
- `measure_article`/`measure_edition` are today human-invoked via
  `mag render --operation ...`; produce does not call them. Layout-result
  parity still matters because those numbers gate page caps.

## Subagent execution protocol

1. **Owned paths.** A WP may create or modify only the paths its brief
   lists. Every WP implicitly owns its evidence file. A WP that adds crate
   dependencies also owns `mag/Cargo.toml` + `mag/Cargo.lock`. Pairwise
   serial regardless of the dependency graph: (a) WPs touching Cargo files,
   (b) WPs touching `mag/src/typeset/**` or `mag/src/render.rs`, (c) WPs
   touching `meta/verification/golden/`. Acceptance includes the verifier
   running `git diff --name-only <base>` (the `## Base` SHA from evidence)
   against the Owns list. Also pairwise serial: (d) WPs touching
   `mag/src/parity*`. A WP diff that touches any `evidence/*.verify.md` or
   `baseline.json` is rejected by the orchestrator before a verifier is
   spawned, except a WP whose Owns names baseline.json explicitly (WP-0.2a:
   schema and empty state; WP-5.4g: cover-page seed rows); only verifiers
   write those otherwise.
2. **Evidence.** A WP is done when its verification commands exit 0 AND it
   has written `meta/verification/evidence/WP-<id>.md` with the skeleton:
   `## Base` (the commit the WP branched from), `## Commands`,
   `## Tool versions`, `## Metrics`, `## Verdicts` (sha256 + tier summary of
   every verdict.json produced; "attach a verdict" always means this),
   `## Residuals`, `## Status` (`done`, `blocked`, or `awaiting-fran`).
3. **Verifier acceptance.** The WP agent's green run is a claim, not an
   acceptance. A verifier agent, spawned by the orchestrating session (or
   Fran), never by the WP agent, receives the WP's brief + the evidence file
   + this rule; it checks out a fresh worktree at `## Base` with the WP's
   diff applied, confirms the diff touches no verify file or baseline,
   replays `## Commands` (which must be complete enough to rerun from that
   worktree alone, inline one-liners included), compares verdict digests
   against `## Verdicts`, and runs the Owns diff check. The verifier owns
   `meta/verification/evidence/WP-<id>.verify.md` and
   `meta/verification/baseline.json` (raise-only edits computed from its own
   rerun; the verifier is the only legal writer of raises). Monotonicity is
   mechanical: `mag parity` compares the working-tree baseline against
   `git show <base>:meta/verification/baseline.json` and refuses to run if
   any entry was lowered. For Phase 1 spikes (uncommitted instrumentation,
   gone at WP end) verification downgrades to an evidence-consistency audit,
   stated in the verify file.
4. **The comparator and an engine never change in the same WP.** Comparator
   territory: `mag/src/parity*`, `parity.yaml`, `corpus.yaml`,
   `baseline.json`, `golden/`. Comparator changes get their own WP. Three
   exceptions, all Fran-gated one-line WPs: tier enforcement may be
   *tightened* (never loosened), the two scheduled comparator switches
   (WP-5.3g, WP-5.4g), and WP-3.0g (final V3 thresholds from calibration
   data).
5. **Repo rules apply**: `cargo fmt`, `cargo clippy -D warnings`,
   `cargo test` (includes `tools/nocomments.py`), `uvx ruff` for touched
   Python, no comments, no U+2014, hooks installed. A WP that leaves any of
   these red is not done.
6. **Fail loud.** A WP that cannot meet its target writes the measured gap
   into its evidence file with `Status: blocked` and stops; it never weakens
   a check, narrows a corpus or page set, adds a normalization rule, or
   marks itself done with a workaround.
7. **Fran gates.** A WP whose completion requires a human decision ends by
   writing `Status: awaiting-fran` plus its recommendation and stops. The
   decision is recorded by Fran (commit authored by Fran, or a line Fran
   types into the file); a successor WP resumes from it. Fran-gated WPs:
   0.1 (regression discoveries), 1.3/1.5 (hyphenation), 3.0g (final V3
   thresholds), 3.7 (residual ledger), 4.1 (proof sheets), 4.2 (the flip),
   5.3g/5.4g (comparator switches), 6.1 (tools disposition, rollback
   deletion).
8. **The brief.** A subagent receives: its WP section verbatim, the preamble
   of its phase, and these plan sections: the parity ladder, Normalization,
   the oracle freeze, Architecture, and this protocol. The brief bounds the
   plan text an agent receives; every file in the worktree at `## Base`
   (evidence files of completed WPs included) is readable. Where a phase
   preamble states Owns or commands, they bind as if written in the WP
   section.

## Phase 0: instrument and freeze (no engine work)

### WP-0.0 render determinism switches

- Owns: `mag/src/render.rs`, `mag/src/main.rs` (flag registration lines).
- Target: `mag render` gains `--no-model`, under which a render that would
  invoke the model (anchor patching) fails with the pending-anchor list
  instead; the render result reports the pending-anchor count either way.
  Behavior without the flag is unchanged (verified against an existing
  rendered edition).
- Verify: a fixture edition with one unresolvable anchor fails under
  `--no-model` naming the figure; a clean edition renders identically with
  and without the flag, compared as `pdftotext` dumps plus `pdfinfo` page
  boxes plus the packaged JSONs (PDF byte-determinism is not established
  and not assumed).

### WP-0.0b manifest amendment (sanctioned oracle change)

- Owns: `src/magazine/engine_render_bridge.py`.
- Target: `_render_manifest` also emits `layout.toc` and
  `layout.article_opener_fits` (today `toc` exists only in-process on
  `RenderLayout` and opener fits only in the bridge's stdout rows), so the
  packaged `edition-manifest.json` carries every field the comparator and
  page-set derivation need. No other behavioral change; runs before the
  freeze, so no golden regeneration exists to do.
- Verify: render one edition before and after; the `edition-manifest.json`
  diff is exactly the two new keys, and the `pdftotext` dumps and critic
  report are unchanged; `uvx ruff` clean.

### WP-0.1 corpus freeze and `mag parity freeze`

- Owns: `mag/src/parity.rs` (freeze subcommand only), `mag/src/main.rs`
  (subcommand registration lines only), `mag/Cargo.toml` +
  `mag/Cargo.lock`, `meta/verification/corpus.yaml`,
  `meta/verification/golden/`.
- Target: a pinned corpus of every edition+language that renders cleanly
  with WeasyPrint today, with raw golden artifacts stored, a determinism
  proof for the oracle, and zero model calls in any corpus render.
- Work: implement `mag parity freeze`. For each edition directory under
  `editions/` (corpus ids are the numeric ids `mag render` accepts; where
  both a bare and a slugged directory exist for one number, the one
  `mag render` resolves is the corpus entry), attempt `mag render <NNN>
  --run <newest complete run at freeze time> --no-model` for every language
  with committed translations (record per-edition languages; that is the es
  scope: nothing is generated for the occasion). Assert each pinned run
  directory is fully git-tracked and clean at the pinned commit (top-level
  `runs/` is gitignored but `editions/*/run-*` are tracked; `editions/*/
  render-*` are not and are never pinned). A corpus render that would need
  the model is excluded and reported. Render each entry twice into scratch;
  raw per-page `pdftotext` dumps, layout JSONs (`edition-manifest.json`,
  `render-critic.json`), and critic results must be identical across the
  two runs byte-for-byte except fields on a closed whitelist: values
  matching an ISO-8601 timestamp pattern or containing a path under the
  scratch root. Any other differing field is unexplained nondeterminism and
  ends the WP `awaiting-fran`; it never becomes a normalization rule by the
  agent's own hand. List every whitelisted field in corpus.yaml under
  `observed_nondeterminism:` for WP-0.2a to turn into normalization rules.
  Store the raw artifacts under `golden/` (not normalized digests;
  normalization does not exist yet). Write corpus.yaml: entries, pinned
  runs, content commit, staged-input SHA256s, `oracle_tree_sha`, and
  `dev_edition:` / `dev_article:` naming the development target, chosen by
  a coverage table (per-candidate counts of figures, extracts, code blocks,
  plates) recorded in corpus.yaml so the choice is checkable.
- Verify: `mag parity freeze` rerun reproduces identical raw artifacts;
  corpus contains at least editions 004 and 009; evidence lists every
  excluded edition and why. An edition that fails to render on main is a
  regression: `Status: awaiting-fran`, and the plan blocks.

### WP-0.2 comparator (four serial WPs)

All four own `mag/src/parity.rs` (module registration and driver wiring) and
`mag/Cargo.toml` + `mag/Cargo.lock` in addition to the paths below.

**WP-0.2a text, geometry, boxes**
- Owns: `mag/src/parity.rs`, `mag/src/parity/text.rs`,
  `mag/src/parity/geometry.rs`, `meta/verification/parity.yaml`
  (normalization + tools + tier tables), `meta/verification/golden/
  digests.json`, `meta/verification/baseline.json` (schema + empty state).
- Target: `mag parity --pre-rendered` implements Tier S text, page count and
  page boxes via `pdfinfo`, and Tier G from `pdftotext -bbox-layout`;
  verdict.json carries the freeze digests, refuses on mismatch, and is
  byte-deterministic (no timestamps, durations, hostnames, or absolute
  paths); normalized golden digests computed over WP-0.1's raw artifacts
  and stored.
- Verify: oracle self-test: one corpus edition rendered twice compares at
  Tier S text + G3 (zero tolerance consumed) and produces byte-identical
  verdict.json twice; the extractor's coordinate precision is measured and
  the G3 source (bbox vs content streams) recorded in parity.yaml.

**WP-0.2b content streams**
- Owns: `mag/src/parity/streams.rs`.
- Target: Tier S color and navigation clauses implemented (extraction crate
  or pinned `mutool`, decided in-WP and recorded in parity.yaml tools).
- Verify: oracle self-test extended to the stream clauses; a hand-built
  two-PDF fixture with one changed fill color and one dropped annotation is
  caught.

**WP-0.2c raster, clusters, report, proof sheets, merge calibration**
- Owns: `mag/src/parity/raster.rs`, `mag/src/parity/report.rs`,
  `meta/verification/parity.yaml` (`merge_rewrite_rules` key only).
- Target: Tier V, `report.html`, `--proof-sheet` with SHA256 manifest, and
  the pypdf merge-invariance calibration: extract
  page 1 and page n of a golden `reader.pdf` as single-page cover stand-ins
  (the function demands single-page A5 covers), run `replace_outer_pages`
  with an explicit output path (omitted, it overwrites its input), and
  compare inner pages before/after at the stream level; rewrite noise found
  becomes `normalization.merge_rewrite_rules`.
- Verify: oracle self-test at V3; the merge calibration report and the
  measured full-corpus wall-clock (so Fran knows the per-WP verification
  cost before Phase 3) in evidence.

**WP-0.2d fault suite and calibration**
- Owns: `mag/tests/parity_faults*`, `meta/verification/parity.yaml`
  (expected-detections matrix key only).
- Target: a seeded fault suite built by rendering scratch copies of staged
  inputs/CSS (never touching tracked files): swapped words, a line moved
  0.3 pt, a figure shifted one page, a 30 px recolor, body ink flipped to
  pure black, a dropped link annotation, a MediaBox off by 0.5 pt. Each
  fault is flagged by **at least** its intended tier (coarser tiers may also
  fire; the matrix states exactly which checks fire per fault and the test
  asserts the matrix); no seeded fault passes the full ladder. Additionally
  the V3 calibration: line offsets seeded at 0.02/0.05/0.1/0.2 pt, with the
  measured cluster-area distribution and per-page mean delta per offset
  recorded in evidence; this data is what WP-3.0g turns into the final V3
  thresholds. Also write `parity.yaml critic_metric_tolerances:` from the
  measured corpus metric distributions (the fixed pass bars WP-5.3a is held
  to; that WP never authors its own).
- Verify: the suite runs under `cargo test`.

## Phase 1: feasibility spikes (throwaway code, binding numbers)

Preamble (binds per rule 8): spike code lives uncommitted in the working
tree or scratchpad; each WP owns only its evidence file. Instrumenting
`src/magazine/` uncommitted is sanctioned here only (see the oracle-freeze
section), with `git status` clean at WP end. Verifier acceptance for this
phase is the rule-3 evidence-consistency audit. A failed spike does not
improvise a fallback: it reports `awaiting-fran` with the numbers.

### WP-1.1 shaping parity

- Target: for the vendored faces listed in Architecture, rustybuzz (as used
  by Typst) and Pango/HarfBuzz (as used by WeasyPrint) produce cumulative
  line advances agreeing within 0.01 pt on real corpus text from
  `dev_edition` (corpus.yaml), en and es, including ligature and kerning
  cases.
- Work: dump every (font, size, text) line WeasyPrint lays out for
  `dev_edition` via uncommitted adapter instrumentation (the adapter already
  walks text boxes with style access); shape the same strings with rustybuzz
  at the same sizes; compare.
- Verify: evidence with the delta distribution, worst offenders, go/no-go.
  Fallback on no-go: identify the divergent OpenType feature set and align
  Typst's feature flags; `awaiting-fran` only if alignment fails.

### WP-1.2 line-break parity and the ragged-right confirmation

- Target: confirm the design is ragged-right (no `text-align: justify` in
  the CSS); then, given identical measure, font, size, leading, and greedy
  breaking, Typst (`linebreaks: "simple"`, hyphenation off both sides via
  uncommitted switches) reproduces WeasyPrint's break points on at least
  99.5% of `dev_edition` body paragraphs, with every miss explained. The
  target for Phase 3 remains 100% (Tier S text equality corpus-wide);
  unexplained residuals here mean `awaiting-fran` before Phase 2 starts, not
  a tolerance.
- Work: minimal Typst document replicating `dev_article` body-text geometry
  (page size, margins, font, size, leading transcribed from the CSS);
  line-by-line comparison against the instrumented oracle.
- Verify: evidence with the break-point match rate and per-miss causes,
  every miss classified `fixable` (naming the mechanism and the Phase 2/3
  WP that fixes it) or `structural`; any `structural` miss ends the WP
  `awaiting-fran` exactly like an unexplained one. 100% or a recorded Fran
  decision; nothing in between enters Phase 2. Forced breaks are NOT an
  acceptable mechanism for the final engine; if simple linebreaking cannot
  converge, `awaiting-fran`: tolerance acceptance at Tier G versus
  abandoning line-level parity for a page-level standard.

### WP-1.3 hyphenation measurement and recommendation

- Target: a numbers-backed recommendation between (a) porting Pyphen's en/es
  dictionary lookup to Rust and injecting soft hyphens into both engines'
  input, and (b) disabling hyphenation in both engines for the parity
  corpus, re-enabling native hyphenation after the flip as a Fran-approved
  change (with the WP-4.3 proof).
- Work: measure current hyphenation incidence (the adapter reports hyphen
  ladders); render the oracle with hyphenation off (uncommitted CSS switch)
  and quantify: page-count changes per article, page-cap violations, count
  of changed line breaks.
- Verify: evidence with those three numbers. "Negligible" means exactly:
  zero page-count changes and zero cap violations; the line-break delta is
  reported for Fran to weigh. Ends `awaiting-fran`.

### WP-1.4 Typst measurement interface and version pin

- Target: proof that the typst crates expose per-element positions
  sufficient to emit `RenderLayout` (page and box of every paragraph line,
  figure, heading, ornament, at sub-0.1 pt precision) from Rust without
  parsing the PDF, and a concrete crate-version pin.
- Work: spike a `World`, compile a two-page document with a placed image and
  a code block, walk the laid-out frames, confirm positions against a
  rasterized overlay.
- Verify: evidence with the API path used (frame introspection vs `query`),
  the exact `typst`/`typst-pdf` versions to pin, and their MSRV. WP-2.0a
  writes the pin into `parity.yaml` and `Cargo.toml` from this evidence.

### WP-1.5 apply the hyphenation decision (sanctioned oracle change)

- Owns: `src/magazine/assets/weasyprint-a5.css` (the switch, if (b)),
  `meta/verification/corpus.yaml`, `meta/verification/golden/`,
  `meta/verification/parity.yaml` (decision record + regenerated digests),
  evidence.
- Gate: starts only from Fran's recorded WP-1.3 decision. Serial with
  WP-2.0a (golden-mutating; protocol rule 1c) and ordered before it in the
  graph.
- If (a): records the decision; the Pyphen-equivalent soft-hyphen injection
  lands in WP-2.1 (its brief says so).
- If (b): apply the CSS switch, regenerate goldens via `mag parity freeze`,
  recompute `golden/digests.json`, update `oracle_tree_sha`; WP-4.3 becomes
  mandatory.
- Verify: `mag parity freeze` reproducible twice; WP-0.2a's oracle
  self-test re-run green against the new goldens.

## Phase 2: the Typst engine skeleton

### WP-2.0a engine dispatch

- Owns: `mag/src/main.rs` (`--engine` flag, `mod typeset;` registration),
  `mag/src/render.rs` (engine selection: `magazine.toml [render] engine` +
  `--engine` override; typst branch stubs to a clear "not implemented"
  error), `mag/src/typeset/mod.rs` (stub), `mag/Cargo.toml` +
  `mag/Cargo.lock` (typst crates pinned per WP-1.4 evidence),
  `meta/verification/parity.yaml` (the crate-pin record only).
- Target: `mag render <NNN> --engine weasyprint` matches the golden raw
  artifacts; `--engine typst` fails loud; the toml key is live and defaults
  to weasyprint.
- Verify: render the corpus to scratch, extract with the pinned tools, and
  compare normalized digests against `golden/digests.json` (the only
  comparison machinery existing at this graph position is `--pre-rendered`
  plus the digest file); `cargo test`.

### WP-2.0b parity render mode and page sets

- Owns: `mag/src/parity.rs`, `meta/verification/parity.yaml` (`page_sets:`
  key only).
- Target: `mag parity <NNN> [--lang]` stages exactly once from the
  corpus.yaml pins into a git worktree at the pinned content commit (the
  worktree is the cwd for both renders; note `mag` requires the repo-root
  layout with `prompts/` present, and pinned runs are tracked so the
  worktree carries them), passes `--no-model`, runs both engines on the
  identical staged tree, compares over the interior domain.
  `mag parity --corpus` iterates the corpus against `baseline.json`, and
  `--set <page_set>` scores one set. Implement the oracle render cache.
  Derive the Phase 3 page sets and write them under `parity.yaml
  page_sets:`: `body` = pages with no figure placements and no opener/TOC
  (from the golden manifests' toc and figure placements); `openers` =
  opener and TOC pages (from toc); `placement` = pages with
  figure/plate/ornament placements; `furniture` = all interior pages;
  `code` cannot come from the layout JSONs (they carry no code-block
  pages): match the staged manuscripts' fenced runs and resolved extract
  texts against the golden per-page `pdftotext` dumps, a page joining
  `code` when a run's first line lands on it, with the matched-run count in
  evidence; per-language variants of each set.
- Verify: with the typst branch still stubbed, `mag parity dev_edition`
  reports the typst failure cleanly and oracle-vs-golden digests hold; an
  oracle-only dry-run mode (`--corpus --oracle-only`, comparing oracle to
  golden) is green.

### WP-2.1 content pipeline: staged inputs to Typst source tree

- Owns: `mag/src/typeset/content.rs`, fixtures under `mag/tests/typeset_*`,
  `mag/Cargo.toml` + `mag/Cargo.lock`.
- Depends: WP-5.1c (consumes the ported document model and manifest loader
  under `mag/src/model/`; it owns neither a markdown parser nor edition
  validation of its own). The refusal fixture list from WP-5.1c's matrix is
  copied into this brief verbatim when the WP is cut.
- Target: for every corpus edition and language, the pipeline turns the
  staged inputs (edition.yaml, manuscripts, translations, extracts, figures)
  into a deterministic in-memory Typst source tree whose plain-text
  projection equals the golden normalized text (Tier S text, pre-layout).
- Work: extracts resolution with the same ambiguity refusals `manifest.py`
  enforces; figure/caption/anchor wiring; es variant loading equivalent to
  `load_translation`. If WP-1.5 recorded decision (a), the soft-hyphen
  injection is in scope here, driven by the dictionaries named in
  parity.yaml.
- Verify: `cargo test` comparing the projection against golden normalized
  text for the whole corpus; extracts byte-exactness; the refusal matrix
  from WP-5.1c re-exercised through this pipeline (ambiguous begin/end
  marker, marker not found, manuscript already carrying the run verbatim,
  unknown source id, figure path escaping the source dir).

### WP-2.2 the reader template (three serial slices)

Preamble (binds per rule 8): each slice owns `mag/src/typeset/template.rs`,
`mag/src/typeset/**` submodules it introduces, and `mag/assets/typeset/`;
slices are serial and each extends the mapping table in its evidence file:
every transcribed value cites its origin (`src/magazine/assets/
weasyprint-a5.css` selector or `weasyprint_adapter.py` constant). The
adapter is 3,000 lines nobody fully remembers; the mapping table is the
forcing function, and anything found-but-not-transcribed is listed as
pending, never dropped silently.

**WP-2.2a geometry and body**: A5 page geometry, margins, body/quote/code
text styles, folios, placeholder outer pages. Target: `mag render
dev_edition --engine typst` emits an interior.pdf; `mag parity dev_edition`
produces a verdict.json with every tier evaluated and a nonzero exit on
failure (digest in evidence); page boxes pass Tier S.

**WP-2.2b architecture**: article openers, headings, TOC, editorial (for
pre-010 corpus editions), page caps. Target: Tier S page count on
`dev_edition`; verdict digests recorded in evidence as the running baseline.

**WP-2.2c placement**: figures, extracts, plates, tail ornaments, anchor
resolution. Target: every corpus figure/extract present on some page;
Tier S same-page not yet required (that is WP-3.4); verdict digests
recorded.

### WP-2.3 layout result and measure operations

- Owns: `mag/src/typeset/layout.rs`, `mag/src/render.rs` (typst branch
  wiring of measure operations).
- Target: `--engine typst` emits the full layout JSON (RenderLayout shape)
  and supports `measure_article`/`measure_edition` natively. Minimum
  comparison set: on `dev_edition`, Typst-reported `article_pages`,
  `editorial_pages`, and `article_opener_fits` equal the oracle's (from
  `edition-manifest.json`); across the rest of the corpus every field is
  compared and every mismatch enumerated in evidence (mismatches gated on
  unfinished Phase 3 parity are listed as pending with their WP, never
  skipped).
- Verify: a corpus loop under `cargo test` attaching the field-by-field
  table to evidence.

## Phase 3: convergence

Preamble (binds per rule 8): one WP per feature area, strictly serial, in
this order. Every Phase 3 WP except WP-3.0g owns `mag/src/typeset/**` plus
its evidence file and NOTHING else; comparator territory is out of bounds
(rule 4, whose third exception is WP-3.0g). Each
WP is scored on its named `page_sets:` entry from parity.yaml, already
written by WP-2.0b. Verification for every Phase 3 WP is the same two
commands: `mag parity --corpus` green against `baseline.json` (no page
anywhere regresses; raises are the verifier's), and the WP's named page set
reaching its named tier.

- **WP-3.1 body text** (`page_sets.body`): Tier S text+color + G2.
- **WP-3.2 headings, openers, TOC** (`page_sets.openers`): Tier S + G2;
  opener-fit booleans exact corpus-wide.
- **WP-3.3 code blocks and extracts** (`page_sets.code`): byte-exact text;
  per-code-block (text-run, fill color) sequences from the content streams
  identical (raster similarity is not accepted: near-palette colors sit
  under the V threshold); G2 boxes.
- **WP-3.4 figures, plates, ornaments** (`page_sets.placement`): Tier S
  same-page + G2 boxes; effective_ppi equal within 0.5.
- **WP-3.5 furniture and navigation** (`page_sets.furniture`): G2
  everywhere; Tier S navigation clause corpus-wide.
- **WP-3.6 Spanish corpus**: every prior tier held on the es entries.
- **WP-3.0g tier tightening (Fran-gated comparator WP, rule 4 exception)**:
  owns `parity.yaml`; writes the final V3 thresholds from WP-0.2d's offset
  calibration data and raises the ratchet targets WP-3.7 must reach (the
  corpus-wide pass bar stays baseline-relative; the absolute bar is
  WP-4.1's).
- **WP-3.7 the G3/V3 ratchet**: burn residuals page by page under the
  WP-3.0g thresholds. Evidence is the residual ledger: every page not at
  G3/V3, its diff, its cause. Ends when the ledger is empty or every
  remaining line carries Fran's recorded acceptance (`awaiting-fran` until
  then).

## Phase 5: port the rest of Python to Rust

Numbered 5 for historical reasons but starts alongside Phase 2/3: the gate
and the flip need the Rust critic and cover. Preamble (binds per rule 8):
each WP owns the named new Rust module, `mag/tests/<wp-slug>*`, Cargo files,
and its evidence file; originals stay in place until WP-6.1; none of these
WPs touches `mag/src/typeset/**`, `mag/src/render.rs` (except WP-5.6), or
comparator territory. Oracle-equality tests that need rasters shell the
pinned `pdftoppm` from `cargo test`; they do not use `mag parity`.

- **WP-5.1 model ports (three serial WPs)**
  - Dump replayability rule for all three: the Python-side oracle dump is
    produced by a full inline invocation (`uv run python -c '...'`) recorded
    verbatim in `## Commands`, so the rule-3 verifier reproduces it from the
    worktree alone; no uncommitted scripts.
  - **WP-5.1a document model** (`publication_document.py`,
    `document_structure.py`, `reader_text.py`): owns `mag/src/model/doc.rs`
    (+ the markdown crate decision). Oracle: the plain-text and structural
    projection of every corpus manuscript equals the Python model's dump.
  - **WP-5.1b records** (`records.py`, `media_schema.py`): owns
    `mag/src/model/records.rs`. Oracle: loaded-record equality dump over
    `library/sources/` at the pinned commit.
  - **WP-5.1c manifest** (`manifest.py`): owns `mag/src/model/manifest.rs`.
    Oracle: the loader-owned subset of `edition-manifest.json`, extracted
    identically from golden and Rust dump with
    `jq -S '{edition, layout: (.layout | {maximum_article_pages,
    article_page_caps, article_content_modes, maximum_editorial_pages})}'`
    (note the `.layout |` pipe: without it jq builds the keys from the root
    and every value is null), byte-equal for the corpus, with a sanity
    clause: the extraction of one golden manifest must contain no null
    values (layout-derived fields such as `layout.article_pages`,
    `article_terminal_balance`, and `layout.figures[*]` placements, and
    request-derived fields such as `publication` and `inputs`, are
    excluded: they are the renderer's, not the loader's; note the es
    `edition:` is synthesized by `_translation_raw`, which the port must
    reproduce). Plus the refusal matrix: every ValidationError raise site
    in `manifest.py`, provoked by fixture, mapped to a Rust error variant +
    message substring; the matrix is enumerated in the WP evidence and
    checked by the verifier against `manifest.py`'s raise sites.
- **WP-5.2 booklet imposition** (`booklet.py`): owns `mag/src/impose.rs`.
  Oracle: impose the same golden reader.pdf both ways; page-wise raster
  equality at the V3 thresholds and Tier S text per sheet in spread order,
  computed inside its own cargo tests.
- **WP-5.3 render critic (three serial WPs)**
  - **WP-5.3a raster metrics** (`image_contrast.py`, `concurrency.py`'s
    role): owns `mag/src/critic/metrics.rs`. Oracle: metric values on
    corpus pages within per-metric tolerances fixed BEFORE the WP starts
    (exact equality for integer metrics; named epsilons for float metrics,
    written into this brief or parity.yaml by a prior comparator WP); the
    WP agent never authors its own tolerances.
  - **WP-5.3b rules** (`render_critic.py` checks): owns
    `mag/src/critic/rules.rs`. Oracle: render-critic.json equality on the
    corpus over the exact-match field set {result, issue codes, severities,
    pages, spread tables}; corpus metrics must sit outside a stated margin
    of every decision threshold, with near-threshold fixtures added where
    they do not.
  - **WP-5.3c calibration and faults**: owns `mag/tests/critic_*`. The
    critic fault suite: swapped spread, missing tail band, low-ppi figure;
    both critics emit the same issue codes.
  - **WP-5.3g comparator switch (Fran-gated, one line)**: owns
    `mag/src/parity.rs` + `parity.yaml`: the Typst side's critic verdict
    (Rust critic) joins Tier S.
- **WP-5.4 cover compiler** (`cover.py`): owns `mag/src/cover/`. Depends on
  WP-5.1c (consumes the Rust Edition model), not on the typst text stack:
  covers are fontTools glyph outlines rasterized through resvg and placed
  by reportlab, no typeset text runs. Drawing backend decided in-WP and
  recorded. Oracle: raster parity at V3 thresholds + stream-level color
  parity of front/back cover PDFs across every corpus edition and every
  cover.layout mode (framed, footer_caption, honored_plate), in its own
  cargo tests; the brief enumerates which corpus entries exercise which
  mode, with fixture editions added for any mode the corpus misses.
  - **WP-5.4g comparator switch (Fran-gated, one line)**: owns
    `mag/src/parity.rs` + `parity.yaml` + `baseline.json` seed rows for
    cover pages: the compared artifact becomes `reader.pdf` end to end.
    Gated on WP-3.7 + WP-5.4 (switching mid-Phase-3 would score cover pages
    against baselines that only cover the interior).
- **WP-5.5 preflight + package + web edition** (`preflight.py`,
  `package.py`, `web_edition.py`, `html_edition.py`): owns
  `mag/src/package/`, `mag/src/web/`. Oracle: byte-identical `web/` tree
  files, SHA256SUMS, preflight.json, printing instructions,
  edition-manifest.json on the corpus. Archives (`package.zip`,
  `web-output.zip`) compare per-entry (name order, unix mode, timestamp,
  CRC32, uncompressed bytes), never as whole-file bytes: Python zlib and
  Rust flate2 streams differ legitimately. Note: `html_edition.py` also
  builds the WeasyPrint interior HTML; that role dies with the oracle and
  is not ported, only the web path is.
- **WP-5.6 native render_edition**: owns `mag/src/render.rs`,
  `mag/src/typeset/**` glue (serial with Phase 3 per rule 1b; scheduled
  after WP-3.7). Depends: WP-2.3, WP-3.7, WP-5.2, WP-5.3b, WP-5.4, WP-5.5.
  Target: `--engine typst` runs cover, critic, package, web natively; no
  bridge spawn for any operation on that path. Verify: bridge outputs
  pre-generated from the pins; then, with `uv` removed from PATH, render
  the corpus `--engine typst` and run `mag parity --pre-rendered` against
  those bridge outputs: all tiers at their current baseline, package/web
  oracles green.
- **WP-5.7 capture's PDF transcription** (`tools/pdf2md.py`): owns
  `mag/src/capture.rs` (the `uv run python tools/pdf2md.py` call site),
  `mag/src/pdf_text.rs`. The brief's first step is reading `tools/
  pdf2md.py` and recording in evidence whether it is deterministic; oracle:
  byte-identical markdown on three captured-PDF fixtures named in evidence
  if deterministic, else `awaiting-fran` with the observed variance and a
  proposed structural oracle.

## Phase 4: the gate, the flip, and the hyphenation proof

### WP-4.1 full parity gate

- Owns: evidence and `output/parity/proof/` only.
- Depends: WP-3.7, WP-5.3g, WP-5.4g.
- Target: `mag parity --corpus` green at Tier S (all clauses, critic on
  both sides, reader.pdf end to end) + G3 + V3, both languages, run twice
  from a clean checkout with identical verdicts; proof sheets via
  `mag parity --proof-sheet` with their SHA256 manifest embedded in
  evidence.
- Then `Status: awaiting-fran`; Tier F approval recorded by Fran per rule 7,
  citing the manifest digest.

### WP-4.0g ad hoc parity mode (comparator WP)

- Owns: `mag/src/parity.rs`.
- Target: `mag parity --adhoc <NNN> --run <dir>` for editions outside the
  corpus: skip pin/baseline assertions, render both engines fresh from the
  working tree in one staged worktree (still `--no-model`; pending anchors
  must be resolved through the normal pipeline first), evaluate Tier S only,
  report G/V informationally.
- Verify: `--adhoc` on a corpus edition agrees with the pinned run's Tier S
  verdict.

### WP-4.2 the flip

- Owns: `magazine.toml`, `CLAUDE.md` (pipeline paragraph), `docs/`
  (transition record superseding `docs/RENDERER_MIGRATION.md`, which still
  describes the deleted TypeScript engine), evidence.
- Gate: WP-4.1's recorded Tier F approval.
- Target: `[render] engine = "typst"` default; `weasyprint` remains
  selectable as the rollback exactly as `reportlab` did in the last
  migration; CLAUDE.md and docs describe the actual pipeline.
- Verify: render every corpus edition plus the newest in-flight edition end
  to end with the new default; critic passes; `mag parity --adhoc` (WP-4.0g)
  on the in-flight edition: Tier S must pass, G/V numbers reported to Fran;
  a template gap exposed by the in-flight edition blocks the flip until
  fixed and re-gated. Fran prints one booklet.

### WP-4.3 post-flip hyphenation proof (only if WP-1.5 chose (b))

- Owns: `mag/src/typeset/**` (enable native hyphenation), evidence.
- Target: Typst with native hyphenation vs the ORIGINAL pre-WP-1.5
  hyphenating goldens: Tier S text with hyphen-normalization + equal page
  counts + zero cap violations; the line-break residual quantified.
  `awaiting-fran` for acceptance.

## Phase 6: decommission

### WP-6.1 delete Python

- Gate: one real edition shipped on the Typst engine (same acceptance rule
  as rust-rewrite.md: a released edition, not tests). Deleting WeasyPrint
  deletes the rollback; that is Fran's call, recorded.
- Owns: deletion of `src/magazine/`, `pyproject.toml`, `uv.lock`, ruff
  config; font relocation to `mag/assets/fonts/` (byte-identical, checked);
  `.githooks` update (drop the ruff steps AND the direct
  `python3 tools/nocomments.py` invocation); the no-comments check ported
  into `cargo test` natively so `tools/nocomments.py` can go; `tools/*.py`
  disposition per Appendix A, each keep/delete confirmed by Fran;
  `CLAUDE.md`, `docs/`, and `meta/verification/` scaffolding deletion
  (corpus, goldens, baselines, evidence remain in git history); a final
  transition record.
- Target: `git grep -lE "uv run|mag-render-adapter|weasyprint"` over
  tracked files hits only docs history and this plan; `mag render`,
  `mag capture` (including a PDF source), `cargo test`, and a full render
  of the shipped edition all pass on a machine with no Python toolchain
  configured for this repo.

## Dependency graph (authoritative over section order)

```
WP-0.0 -> WP-0.0b -> WP-0.1 -> WP-0.2a -> WP-0.2b -> WP-0.2c -> WP-0.2d
WP-0.2d -> WP-1.1, WP-1.2, WP-1.3, WP-1.4      (1.1-1.4 parallel)
WP-1.3 -> WP-1.5 (Fran gate between)
WP-1.5 -> WP-2.0a (also serial via rule 1c)
WP-1.4 -> WP-2.0a -> WP-2.0b
WP-0.2d -> WP-5.1a -> WP-5.1b -> WP-5.1c
WP-5.1c + WP-2.0b -> WP-2.1 -> WP-2.2a -> WP-2.2b -> WP-2.2c -> WP-2.3
WP-2.3 -> WP-3.1 -> WP-3.2 -> WP-3.3 -> WP-3.4 -> WP-3.5 -> WP-3.6
WP-3.6 -> WP-3.0g (Fran gate) -> WP-3.7
WP-0.2d -> WP-5.2, WP-5.3a, WP-5.7             (parallel with Phase 2/3)
WP-5.3a -> WP-5.3b -> WP-5.3c -> WP-5.3g (Fran gate)
WP-5.1c -> WP-5.4;  WP-3.7 + WP-5.4 -> WP-5.4g (Fran gate)
WP-5.1c -> WP-5.5
WP-2.3 + WP-3.7 + WP-5.2 + WP-5.3b + WP-5.4 + WP-5.5 -> WP-5.6
WP-3.7 + WP-5.3g + WP-5.4g -> WP-4.1 (Fran gate) -> WP-4.2
WP-3.7 -> WP-4.0g -> WP-4.2
WP-5.6 -> WP-4.2
WP-4.2 -> WP-4.3 (if applicable) -> shipped edition -> WP-6.1 (Fran gate)
Serialization overrides (rule 1): Cargo-file owners pairwise serial;
typeset/render.rs owners pairwise serial; golden-mutating WPs pairwise
serial; mag/src/parity* owners pairwise serial.
```

## Risks

- **rustybuzz/Pango disagreement** on these fonts: caught by WP-1.1 before
  any engine code exists.
- **Typst crate API churn**: versions pinned; upgrades are their own WP with
  a full `mag parity --corpus` rerun.
- **The 3,000-line adapter encodes behavior nobody remembers**: the mapping
  tables (WP-2.2a/b/c) and the residual ledger (WP-3.7) force everything
  into the open; anything unexplained lands on the ledger, not under the
  rug.
- **Oracle drift**: `oracle_tree_sha` + verdict digest checks make drift a
  refused run.
- **Subagents gaming gates**: rules 1, 3, 4, 6; digests over thresholds,
  goldens, and oracle; verifier reruns from clean worktrees; baseline
  monotonicity enforced by the comparator with the verifier as the only
  legal writer.
- **Corpus too thin in es**: scope is honestly "editions with committed
  translations at freeze time"; if that is only legacy editions, WP-0.1
  reports it and Fran may commission one modern es translation before the
  freeze (a content decision, outside this plan's WPs).

## Non-goals

Typst-native typography improvements before the flip (except the WP-4.3
proof), CI infrastructure, rendering editions outside the frozen corpus
during parity (the WP-4.2 in-flight check excepted), InDesign/Prince
detours, keeping the reportlab engine (it dies with WP-6.1 alongside
everything else Python), provenance ceremony beyond the sanctioned,
temporary `meta/verification/` scaffolding.

## Appendix A: Python disposition table

Every Python file in the repo and where it goes.

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
| `src/magazine/render_engine.py` | superseded by Rust engine dispatch (WP-2.0a); deleted WP-6.1 |
| `src/magazine/engine_render_bridge.py` | deleted WP-6.1 |
| `src/magazine/reader_layout.py` | shape ported as the layout JSON (WP-2.3); deleted WP-6.1 |
| `src/magazine/errors.py`, `io.py`, `__init__.py` | die with the package, WP-6.1 |
| `tools/pdf2md.py` | ported, WP-5.7 |
| `tools/nocomments.py` | check ported into `cargo test`, WP-6.1 |
| `tools/capture.py`, `tools/compare.py`, `tools/coverproof.py`, `tools/letter.py`, `tools/read.py` | side tools: individually keep/port/delete by Fran in WP-6.1; none is pipeline-load-bearing |
| `art-directions/experiments/vignette-wilted-sprout/wordless/letter.py` | experiment artifact: keep/delete by Fran in WP-6.1 |
