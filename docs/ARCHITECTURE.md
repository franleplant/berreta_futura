# Architecture

## Purpose

The project compiles unstable internet sources into private-first, source-faithful magazine editions. It separates acquisition, editorial judgment, and production so an approved manuscript can be rebuilt without fetching the web or invoking AI again.

## External interface

The publishing module exposes four conceptual operations:

1. `capture(inputs)` records and materializes source candidates.
2. `run(edition)` advances an edition until the next unresolved checkpoint.
3. `decide(checkpoint)` records an approval, rejection, or change request against an exact revision.
4. `status(edition)` explains current state, warnings, and recoveries.

The CLI and conversational interface are adapters over this interface. Individual extractors, AI roles, renderers, and packaging steps are private implementation details.

The concrete publishing seam is now:

```python
mag.workflow_status(edition_id)       # read-only, complete checkpoint report
mag.workflow_run(edition_id)          # conservative deterministic advancement
mag.stage_article(versioned_brief)    # source, ledger, manifest, translation unit
mag.cover_studio_*()                  # immutable rounds and explicit selection
mag.illustration_studio_*()           # explicit inventory and asset registration
```

`workflow_status` is the single source of recovery instructions. A checkpoint
classifies its next action as deterministic, authorial, or human review.
`workflow_run` dispatches only a finite allowlist of deterministic actions and
stops when the remaining work requires prose, image generation, selection,
review, or release. Repeating it is safe.

Article staging owns the first post-capture transaction. A schema-versioned
brief names one collecting edition, one article identity, and one or more
queued source ids. The article staging module prepares the manuscript TODO,
exact extraction pins, fidelity skeleton, and manifest row without inventing
source text. The publishing module then reconciles every configured
non-source-language overlay. Those writes are exposed as one transaction: an
overlay refusal conditionally restores only files this invocation changed.
Unrelated concurrent files are preserved. A concurrently edited touched file
is also preserved and reported while every other safely restorable write rolls
back.

Creative studios are intentionally outside `run`. The Cover Studio owns
append-only candidate rounds, computed asset hashes, prompt evidence, all-round
localized full-cover proofs, comparison sheets, and an explicit atomic
selection. The Illustration Studio owns article openers plus an explicit subset
of article tails and closing plates, prompt packages, validated asset
registration, and review sheets. Neither studio invokes image generation.
Their revisions support
optimistic concurrency so a stale caller refuses instead of replacing newer
work.

The CLI mirrors these boundaries:

```text
mag status <edition> [--json]
mag run <edition> [--json]
mag article stage <brief> [--dry-run]
mag cover-art <status|next-round|prompts|register|proof-plan|proof|compare|select>
mag interior-art <status|scaffold|prompts|register|review-plan|review-sheet>
```

Legacy focused commands remain compatibility adapters. In particular,
`illustrate` retains its combined prompt-package behavior and `cover-proof`
retains the canonical selected-cover fast proof.

## Artifact flow

```text
lead URL
  -> immutable source snapshot
  -> normalized source record
  -> assignment to the selected intake edition
  -> provenance-linked source bundle
  -> versioned article brief
  -> transactional manuscript, fidelity, manifest, and translation staging
  -> faithful manuscript + editorial patches
  -> seven-page article-budget check (faithful synthesis when over budget)
  -> emergent-narrative editorial drafted under docs/WRITING_RULES.md
  -> titled one-page editorial-budget check (per-edition, two-page ceiling)
  -> append-only cover rounds + full-cover comparisons + human selection
  -> explicit opener and interior-art inventory + validated registered assets
  -> approved content digest
  -> canonical front/back SVGs -> one-page cover PDFs -> proof PNGs
  -> deterministic interior layout
  -> exact outer-cover PDF splice into reader pages 1 and N
  -> proof digest
  -> reader/home/studio packages
```

## Invariants

- Raw snapshots are committed beside their source record and approved artifacts are immutable and content-addressed.
- Every captured source is assigned exactly once: either to one collecting edition or to one released edition.
- Several editions may collect concurrently, but one explicit intake target receives new sources by default; intake batches never create collections implicitly.
- Release first reconciles all source records, then requires exact equality between the target edition's queue and rendered articles' `source_ids`; sources queued to other collecting editions are unaffected.
- Release state advances only after validation and a complete deterministic build succeed.
- The edition manifest is replaced before the authoritative ledger, and both are restored if either replacement fails.
- Release preserves private distribution and rights restrictions; it records production completion, not public reprint permission.
- Refetching changed content creates a revision rather than mutating history.
- Every factual claim, quotation, figure, and caption resolves to captured evidence.
- AI output is draft material and cannot approve itself.
- An approval names the exact revision and digest it approves.
- Any manuscript, art, template, font, profile, or tool change invalidates downstream approvals.
- Packaging never invokes AI. It consumes sealed artifacts only.
- Each browser proof is rasterized from the same one-page outer-cover PDF
  inserted into the reader; proof and production faces cannot be separate
  implementations.
- ReportLab owns interior pages only. Cover geometry, outlined typography,
  artwork placement, trim behavior, and comparison evidence for both outer
  faces are local to the cover compiler and its authored design contract.
- Release output is promoted atomically after validation.

## Canonical and generated material

Canonical authored material:

- immutable raw source bundles and their SHA-256 manifests;
- structured source records and human notes;
- edition manifests and briefs;
- approved manuscripts and clearly labeled editor text;
- cover direction and selected artwork;
- article-opener art declarations and committed opener images;
- `design/covers/canto-vivo/design.toml` and approved cover references;
- hash-bound independent render-review decisions;
- decisions tied to revisions.

Generated material:

- `sources.md`;
- fidelity reports and source/manuscript diffs;
- review PDFs and page images;
- render-critic reports and numbered visual-review contact sheets;
- build locks, preflight reports, checksums, and packages.

## Dependency strategy

- In-process logic: hashing, manifests, workflow state, citation resolution, fidelity metrics, and packaging plans.
- Local-substitutable dependencies: filesystem, ReportLab, pypdf, FontTools,
  resvg, Poppler, clocks, and process execution.
- True external dependencies: websites, authenticated browsers, Codex/model execution, image generation, and printing studios.

Production and recorded/fixture adapters justify seams for web retrieval and AI execution. The initial typesetter has one implementation and therefore remains an internal implementation rather than a speculative public seam.

## AI execution

Editorial jobs receive immutable artifact references and schema-constrained tasks. Each run records source hashes, prompt and schema versions, model configuration, tool versions, timing, trace location, and output hash. Parallel agents write isolated results; the coordinator validates and merges them.

Recommended roles are source researcher, article production editor, evidence checker, copy editor, editorial writer, art director, and visual proof reviewer. Faithful article production uses patch proposals rather than free rewriting. The editorial writer applies `docs/WRITING_RULES.md` to one original unifying idea, set of ideas, or emergent narrative across the edition, never to an article-by-article summary.

## Output profiles

- Reader: A5 pages, RGB, links, compact images.
- Home: A5 pages imposed two-up on A4, duplex instructions, no required bleed, page count padded to a multiple of four.
- Studio: printer-specific trim, bleed, output intent, PDF/X target, image limits, font rules, and binding geometry. This profile remains blocked until a printer contract exists.
- Web: per-language, self-contained HTML directory for screens (`mag web`). Private profile: never part of a build or release package, and outside the hash-bound render review, which binds PDFs only.

Print and web output share one renderer-neutral seam: `render_html_edition`
produces the semantic edition both adapters consume. When
`format.article_opener` is `illustrated_paper_spots_v1`, that seam emits one
`article-opener` header containing the first-class art, inline provenance
kicker, title, author and biography, source anchor, and first manuscript
paragraph. The opener art is not a captured evidence figure. The source anchor
retains the canonical URL as semantic text for provenance and accessibility.
The PDF adapter replaces its visible presentation with a verified QR, while
the web adapter presents it as a clickable QR, so neither finished output shows
the URL or a `SOURCE` label. The print adapter also forces the remaining
manuscript onto the next page. Page geometry and print policy stay in the
WeasyPrint adapter; responsive screen policy stays in the web adapter; neither
leaks into the seam. Editions without the format key keep the legacy semantic
and adapter paths for reproducible historical builds.
