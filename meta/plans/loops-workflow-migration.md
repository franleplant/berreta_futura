# Loops workflow migration

Status: **proposed**, not started. Revision 1, 2026-08-03.

This plan supersedes
[`article-review-and-writer-execution.md`](article-review-and-writer-execution.md)
in full. It also supersedes the parts of
[`graph-execution-model.md`](graph-execution-model.md) that make XState the
workflow authority. Its artifact, provenance, human-authority, rendering, and
release requirements remain in force unless this plan changes them explicitly.

## Goal

Replace XState workflow definitions with durable Loops workflow scripts.

Loops owns control flow, composition, parallel work, loops, waiting, and resume.
Magazine modules own artifacts, provenance, editorial policy, authorization,
durable revisions, rendering rules, and release.

There must never be two workflow authorities for one run.

## Dependencies

This migration depends on the Loops durable workflow plan in
`~/code/loopsv2/docs/plans/00003-durable-workflow-runs.md`.

Required Loops features are:

- keyed durable calls;
- immediate progress persistence;
- `step()` for checkpointing arbitrary Node.js work;
- `wait()` for human input;
- version-pinned runs;
- durable nested workflows;
- attempts, leases, fencing, retry, and inspection.

## What stays

Keep and reshape the valuable magazine modules for:

- immutable engine artifacts and exact parent lineage;
- source capture evidence and source identity;
- work-role access rules and source isolation;
- human answer validation and authority;
- durable Git revisions and composition pins;
- renderer and source adapters;
- preflight, visual review, sealing, and release;
- public durability and adversarial tests.

The previous article plan's useful editorial decisions also stay:

- immutable article production profiles;
- data-driven review plans;
- a closed writer role with enforced tool denial;
- one review panel producing one revision brief;
- deterministic routing from review results;
- exact source-aware and source-blind material sets.

## What goes

Remove after migration:

- XState machines and snapshots;
- machine events, guards, entry actions, and machine migrations;
- machine-driver dispatch;
- explicit statechart joins and child-actor routing;
- XState topology export as workflow authority;
- the `xstate` dependency.

## Migration sequence

### Phase 0: freeze XState workflow expansion

- Do not implement the superseded article-machine rewrite.
- Fix only blocking defects in the current engine while Loops durability lands.
- Define the small magazine interfaces that workflow scripts will call.
- Keep current released and sealed runs readable.

### Phase 1: prove one durable article workflow

Create one Loops article workflow that can run both alone and as an edition
child.

It must cover:

- initial writing or supplied manuscript;
- data-driven parallel review;
- deterministic revision brief and routing;
- rewrite iterations and budget exhaustion;
- human accept, revise, or drop decisions;
- durable article promotion;
- exact artifact lineage and role isolation.

Run the existing article durability, authority, provenance, and retry tests
through the new public seam. Do not dual-write a live run through XState and
Loops.

### Phase 2: compose the edition in Loops

Add workflow scripts for:

- source collection and preparation;
- planning;
- articles and opening editorial;
- cover and interior art selection;
- edition review;
- translation;
- measurement and rendering;
- visual review;
- release.

The edition workflow composes these as child workflows and normal TypeScript
functions. It may use `parallel()` and `pipeline()` where useful. Renderer and
source operations remain ordinary Node.js functions, wrapped in `step()` only
when Loops must checkpoint their results.

### Phase 3: make Loops the only authority for new runs

- Start all new article and edition runs through Loops.
- Pin each run to exact workflow code, immutable args, prompts, policies, and
  model configuration.
- Let existing XState runs finish under their original version or explicitly
  fork them into a new Loops run.
- Never resume an XState snapshot as a Loops run.

### Phase 4: simplify the magazine engine

Split the current `RunEngine` implementation into deep magazine modules behind
the workflow scripting seam:

- artifact and lineage store;
- work authority and answer validation;
- durable revision promotion;
- composition and release authority;
- renderer, source, model, and human adapters;
- inspection projections.

Remove workflow lifecycle and state-machine knowledge from those modules.

### Phase 5: remove XState

- Delete `engine/machines/` and `engine/run-engine/machine-driver.ts`.
- Delete machine-specific schema, projection, graph, migration, and tests.
- Remove `xstate` from the package and lockfile.
- Update CLI, viewer, architecture docs, and repository guidance.
- Keep normalized sealed records and immutable artifacts from old runs.

## Migration rules

- One run has one workflow authority.
- Released and sealed runs are immutable.
- Changed frozen inputs create a successor run.
- Old artifacts remain valid evidence and may be reused only through explicit
  immutable references.
- No workflow state is inferred from files or output directories.
- Python remains only the renderer subprocess.
- Edition 4 tests reuse its selected committed art and never regenerate it.

## Verification

Before removing XState, prove:

- crash-safe resume after every durable call type;
- stale and duplicate worker or human answers are rejected;
- late workers cannot commit over a new attempt;
- source-aware and source-blind roles receive the correct artifacts;
- article workflow behavior is the same alone and under an edition;
- parallel joins and revision invalidation are correct;
- render approval names the exact current render artifacts;
- release remains atomic and source identities remain unique;
- the normal Node verification suite passes without Python workflow code.

## Acceptance criteria

- New article and edition runs use readable Loops workflow scripts.
- Loops is the only workflow authority for those runs.
- Magazine provenance, authority, and release guarantees remain enforced.
- The public tests cross one supported execution seam.
- No XState package, machine code, or machine migration remains in the active
  implementation.
- The old article-machine rewrite plan is marked superseded.

## Non-goals

- Rebuilding Loops inside the magazine repository.
- Moving magazine editorial policy into Loops.
- Supporting two active authorities for comparison or fallback.
- Preserving XState topology as the new workflow format.
- Adding Python workflow code.
