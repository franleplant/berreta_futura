# Magazine Loops migration update

Date: 2026-08-04

## Current checkpoint

The last committed Magazine checkpoint is `5c55d0c`:

```text
feat(engine): produce reviewed opening editorial
```

The working tree also contains an uncommitted translation and composition slice. Do not discard it.

Current uncommitted verification:

- `npm run typecheck` passes.
- `git diff --check` passes.
- Translation and composition focused tests have not been completed.
- The uncommitted slice has not received independent Terra review.

## Completed and committed

### Loops

Loops commit `e7c652f5ace0b74d5574830c37c6f5ac124a291f` provides:

- Explicit `run(ctx)` workflow scripts.
- Frozen, invocation-scoped workflow input.
- Parallel durable child workflows with isolated identities and waits.
- Crash-safe child replay without duplicate work.
- Source-graph pinning and stale callback protection.

Its full suite passed before commit.

### Magazine article workflow

The article workflow now supports:

- Fresh initial writing from committed source extractions.
- A closed authenticated article writer.
- Source-aware and source-blind review isolation.
- Parallel review panels.
- Deterministic briefs and editorial routing.
- Rewrite budgets and exact human decisions.
- Durable revision records, promotion, crash replay, and stale-answer rejection.

Each of the seven Edition 4 articles runs its own complete review and revision cycle.

### Edition 4 root

The Loops Edition root now:

- Authenticates the existing Edition 4 source captures and extractions.
- Resolves the write pipeline once.
- Launches seven article workflows as durable children.
- Keeps article execution identity separate from the Edition Loops root identity.
- Reopens without duplicating child calls.
- Performs no image generation.

### Opening editorial

The opening editorial is intentionally separate from article review. The flow is now:

```text
seven approved articles
-> freeze accepted English set
-> opening editorial write/review/rewrite loop
-> full-English measureEdition gate
-> human accept, revise, or abort
-> durable editorial promotion
```

It includes:

- A separate closed editorial writer.
- A source-blind authenticated editorial reviewer.
- Exact frontmatter checks for label, title, and byline.
- One A5 page and visible/fitting opener checks through `measureEdition`.
- Automatic editorial rewrites for blocking findings.
- Human revision after automatic budget exhaustion.
- Durable promotion and crash-safe replay.
- No edition-wide article review or article rerouting.

The public Edition root integration reaches editorial measurement, human wait, promotion, and English completion. Thirteen focused tests, typecheck, and diff checks passed before commit.

## Current uncommitted work

The dirty worktree is the Spanish translation and composition slice.

Modified paths:

- `engine/article-production/materials.ts`
- `engine/contracts/workflow-run.ts`
- `engine/durable/durable-store.ts`
- `engine/durable/types.ts`
- `engine/executors/index.ts`
- `engine/workflows/article-runtime.ts`
- `engine/workflows/edition-workflow-engine.ts`
- `engine/workflows/edition-workflow.ts`
- `engine/workflows/internal-types.ts`
- `engine/executors/closed-translation-writer/`

Implemented so far:

- Typed durable dependencies for input revisions, durable revisions, and engine artifacts.
- Strict parent validation remains in place.
- A closed authenticated Spanish translation writer.
- Eight planned translation tasks: seven articles plus the opening editorial.
- Exact English digest checks.
- Markdown structure, link, code-fence, frontmatter, and footnote validation.
- Separate deterministic translation runs and execution identities.
- Spanish durable promotion plumbing.
- A deterministic composition payload containing English and Spanish pieces.
- Exact reuse of the 13 selected Edition 4 image revisions.
- No image executor, image offer, or image-generation call.

Still required before this slice can be committed:

- Finish exact artifact-to-input-revision bindings for multi-file inputs.
- Complete Spanish and composition promotion validation.
- Add focused translation, dependency, replay, and composition tests.
- Prove eight parallel translations do not duplicate model calls after restart.
- Prove the composition contains exactly 16 manuscripts and the existing 13 images.
- Run independent Terra review and fix any blockers.

## Remaining work to produce Edition 4 PDFs

1. Finish, verify, and commit the current translation/composition slice.
2. Add the final measure, render, preflight, and visual-review Loops phase.
3. Run the real Edition 4 workflow with authenticated model workers and human decisions.
4. Reuse the existing selected images. Never regenerate them.
5. Render through the TypeScript renderer executor. Python remains only the renderer subprocess.
6. Approve the exact current render artifacts.
7. Export:

```text
output/004/<run-name>/en/reader.pdf
output/004/<run-name>/en/home/booklet-a4.pdf
output/004/<run-name>/es/reader.pdf
output/004/<run-name>/es/home/booklet-a4.pdf
```

8. Only after the real PDF acceptance run, finish release/cutover and remove active XState workflow code.

## Important status

- No final Edition 4 PDFs have been produced by the new Loops workflow yet.
- No Edition 4 images were regenerated.
- No Python workflow code was added or executed.
- The current dirty translation worktree is intentional and must be preserved.
