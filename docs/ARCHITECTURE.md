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

## Artifact flow

```text
lead URL
  -> immutable source snapshot
  -> normalized source record
  -> assignment to the single open edition
  -> provenance-linked source bundle
  -> edition selection
  -> faithful manuscript + editorial patches
  -> approved content digest
  -> deterministic layout
  -> proof digest
  -> reader/home/studio packages
```

## Invariants

- Raw snapshots and approved artifacts are immutable and content-addressed.
- Every captured source is assigned exactly once: either to the open edition or to one released edition.
- Intake batches never imply edition boundaries; only an explicit release closes the open edition.
- Refetching changed content creates a revision rather than mutating history.
- Every factual claim, quotation, figure, and caption resolves to captured evidence.
- AI output is draft material and cannot approve itself.
- An approval names the exact revision and digest it approves.
- Any manuscript, art, template, font, profile, or tool change invalidates downstream approvals.
- Packaging never invokes AI. It consumes sealed artifacts only.
- Release output is promoted atomically after validation.

## Canonical and generated material

Canonical authored material:

- structured source records and human notes;
- edition manifests and briefs;
- approved manuscripts and clearly labeled editor text;
- cover direction and selected artwork;
- decisions tied to revisions.

Generated material:

- `sources.md`;
- fidelity reports and source/manuscript diffs;
- review PDFs and page images;
- build locks, preflight reports, checksums, and packages.

## Dependency strategy

- In-process logic: hashing, manifests, workflow state, citation resolution, fidelity metrics, and packaging plans.
- Local-substitutable dependencies: filesystem, ReportLab, pypdf, Poppler, clocks, and process execution.
- True external dependencies: websites, authenticated browsers, Codex/model execution, image generation, and printing studios.

Production and recorded/fixture adapters justify seams for web retrieval and AI execution. The initial typesetter has one implementation and therefore remains an internal implementation rather than a speculative public seam.

## AI execution

Editorial jobs receive immutable artifact references and schema-constrained tasks. Each run records source hashes, prompt and schema versions, model configuration, tool versions, timing, trace location, and output hash. Parallel agents write isolated results; the coordinator validates and merges them.

Recommended roles are source researcher, article production editor, evidence checker, copy editor, editorial writer, art director, and visual proof reviewer. Faithful article production uses patch proposals rather than free rewriting.

## Output profiles

- Reader: A5 pages, RGB, links, compact images.
- Home: A5 pages imposed two-up on A4, duplex instructions, no required bleed, page count padded to a multiple of four.
- Studio: printer-specific trim, bleed, output intent, PDF/X target, image limits, font rules, and binding geometry. This profile remains blocked until a printer contract exists.
