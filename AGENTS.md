# Magazine project guidance

This repository builds private-first, source-faithful magazine editions. The
TypeScript and XState execution engine is the only workflow authority.

## Execution authority

- Run edition and article work through `engine/` and its public `RunEngine`
  interface. Use `npm run engine -- ...` from the CLI.
- XState owns lifecycle and joins. `RunEngine` owns durable runs, immutable
  artifacts, attempts, leases, fencing, events, decisions, validation, exports,
  and release state. It is the sole workflow, orchestration, state, validation,
  and export authority.
- Do not infer workflow state from paths, output presence, hashes, or mutable
  files. Do not send events directly to in-memory actors or query SQLite from
  callers.
- Results enter through `RunEngine.answer`. Retries enter through
  `RunEngine.retry`. Frozen input changes create successor runs through
  `RunEngine.fork`. New collection leads enter through `RunEngine.submitLead`.
- A human decision must answer the exact active offer, name the immutable inputs
  it approves, and create the role's decision artifact. Stale and duplicate
  answers never advance a run.
- A released or sealed run is immutable. Revisions create new artifact IDs and
  preserve the old graph.

## Python renderer seam

- The previous Python pipeline, `mag` CLI, Python tests, and source bridge are
  deleted. Do not restore, invoke, or document them.
- Python implements only the versioned PDF/web renderer subprocess. It receives
  an immutable manifest and a caller-owned destination from the TypeScript
  worker, then returns its structured result. It is not workflow authority, a
  compatibility target, or a place for orchestration.
- Do not add Python workflow code or Python workflow tests. Routine verification
  remains Node-only. Source capture is a TypeScript adapter and may not invoke
  Python.

## Repository roots and revisions

- `inputs/` and `durable/` are Git-tracked repositories of immutable revisions.
  `inputs/` contains versioned source evidence, specifications, prompts, and
  policies. `durable/` contains promoted article, editorial, image, and
  composition revisions. Never mutate a revision in place.
- `.magazine/` is ignored runtime storage for SQLite, engine artifacts, staging,
  leases, and worker scratch space. `output/` is ignored, ephemeral export
  material. Neither path confers workflow authority.
- For edition `004`, one run name is generated as `<UTC timestamp>--<RunId>`.
  Its private runtime root is `.magazine/004/<run-name>` and any public export
  root is `output/004/<run-name>`.
- An `EngineArtifact` is an immutable, run-scoped `RunEngine` artifact with
  offer, attempt, and parent-artifact provenance. A `DurableRevision` is a
  Git-bound, immutable revision in `durable/`, promoted from accepted engine
  artifacts. They are distinct identities, not interchangeable names.
- A `CompositionRevision` selects exact article, editorial, image, and layout
  input revisions. It can mix and match those exact immutable revisions from
  compatible prior work; its pins and Git binding, not directory discovery,
  define the selected edition inputs.

## Editorial and provenance rules

- Preserve provenance from every submitted lead through durable raw evidence,
  extraction, manuscript, judgments, render artifacts, and release.
- A source is not captured merely because a URL exists. Its raw evidence must be
  committed as immutable artifacts before the source can become ready. Never
  store cookies, credentials, authorization headers, browser profiles, or
  session data.
- Treat `sources.md` as generated output. Human annotations belong in source
  records or immutable annotation artifacts.
- Never replace a source article with an unlabeled generic summary. New
  magazine-authored arguments use `original_synthesis`. Length-driven
  condensation uses attributed, source-mapped `faithful_synthesis`.
- Write `faithful_synthesis` in the source author's grammatical person and point
  of view. Do not add framing such as "the author argues" unless it appears in
  the source. Preserve the argument, evidence, qualifications, and conclusion.
- Label magazine-authored text so it cannot be mistaken for a source author's
  words. Faithful modes require source-author attribution. Original synthesis
  requires magazine attribution.
- Source articles may occupy at most seven A5 reader pages. Layout feedback must
  come from the production measurement interface, including actual opener fit,
  not character counts or hand-reproduced wrapping.
- The opening editorial must visibly render a title and fit on one A5 reader
  page including its label, title, and byline. It develops a unifying idea or
  narrative and must not become an article-by-article summary.
- Every fenced code block in a manuscript must be a contiguous exact run from a
  committed source extraction. Drop a block whole if it cannot be preserved.
- Never use CommonMark footnote syntax such as `[^1]` in a manuscript.
- `docs/WRITING_RULES.md` is the house method for editor-authored prose. In a
  faithful mode it governs editor additions, never a source author's voice.
- Social copy must be concise, direct, source-linked, and human-approved.

## Work and authority isolation

- One offer is one role, one actor, and one piece. Do not batch briefs across
  roles or pieces.
- Writers receive every assigned source extraction and the complete revision
  context. Evidence reviewers are source-aware. Mechanics, shape, and craft
  reviewers are source-blind.
- Never let one worker identity perform both source-aware evidence review and a
  source-blind review for the same manuscript revision.
- Each writer revision carries the previous manuscript, working notes, findings,
  and human rulings. Iteration budgets are explicit inputs. Exhaustion is an
  editor state, not an implicit retry loop.
- Edition-level findings route to named article or editorial actors as durable
  events. Any dependent editorial, translation, render, or approval artifact is
  stale when its input artifact changes.
- AI and deterministic workers propose artifacts or findings. Only declared
  machine transitions and explicit human decisions advance authority state.

## Art, languages, render, and release

- Image generation and human art selection are separate work offers. Rendering
  may consume only registered selected art and must never generate an image.
- Cover art contains no baked-in masthead or cover lines. Layout owns all
  typography.
- Keep the inside front cover and inside back cover blank, including their
  imposed sheet sides.
- Generate every configured language before assembly. English is the source
  edition. Spanish uses educated castellano with restrained Argentine
  preferences, avoids slang and generic regionalisms, and preserves Markdown
  structure.
- `measureArticle` and `measureEdition` are different renderer operations. The
  first gives per-draft feedback. The second gates full-issue render and booklet
  assembly.
- Machine inspection and independent visual review must reference the exact
  current render artifact IDs. A new render cannot inherit an old approval.
- Never label an edition press-ready without a named printer profile, passing
  per-language preflight artifacts, and explicit studio readiness.
- Release approval names the exact publication and source artifacts. Release is
  atomic, and a source identity may belong to only one released edition.
- Never regenerate Edition 4 images during tests. Reuse only its selected,
  committed art artifacts.

## Repository prose and files

- Never author Unicode U+2014 in repository prose, code comments, prompts, UI
  copy, or social copy. Use normal punctuation. Preserve it only in immutable
  raw evidence or an exact quotation.
- Keep `.magazine/`, `output/`, temporary runs, databases, artifact stores,
  credentials, and browser-session data out of Git. Keep immutable revisions in
  `inputs/` and `durable/` tracked.
- Do not hand-edit generated hashes or operational records. Runtime identity is
  generated immutable IDs, not content digests.
- Commit structured inputs, prompts, source records, manuscripts, machine code,
  contracts, tests, and normalized sealed run exports as coherent checkpoints.

## Verification

Use the pinned Node toolchain and lockfile:

```sh
npm ci
npm run typecheck
npm run test:engine
npm run build:viewer
```

`npm run verify:engine` runs the same TypeScript checks. Routine verification
must not invoke Python or UV. The TypeScript renderer executor invokes the
Python renderer seam only when a claimed renderer offer requires it.

Tests should cross the public `RunEngine` interface. A narrowly labeled schema
migration test may use internal helpers, but workflow behavior must not depend
on direct database access.

After a meaningful layout change, use an independent render critic to inspect
every language's exact reader and booklet artifacts at original resolution.
Record the decision through the active visual-review offer. Do not hand-edit a
review record or approve a resized preview.

## Git checkpoints

- Work on the branch requested by the user. Inspect the staged diff and run
  proportionate Node verification before committing.
- Preserve unrelated user changes and all immutable source evidence.
- Commit each verified engine, edition, or source-intake checkpoint as a
  coherent unit.
