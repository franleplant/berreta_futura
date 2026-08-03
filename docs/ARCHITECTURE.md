# Architecture

The magazine workflow is one durable TypeScript execution graph. XState owns
lifecycle and joins. `RunEngine` owns persistence, identity, work dispatch,
artifact lineage, validation, export, and release authority. Together they are
the sole workflow, orchestration, state, validation, and export authority. The
old Python pipeline, CLI, tests, and source bridge are deleted. Python remains
only as the renderer subprocess implementation.

The governing design is
[`meta/plans/graph-execution-model.md`](../meta/plans/graph-execution-model.md).
This document describes the implementation boundary contributors use now.

## Public boundary

Callers interact with `RunEngine`; they do not send events to in-memory actors,
query SQLite, inspect output directories for readiness, or copy run folders to
restart work.

The supported operations are:

- `start(spec)` creates an article or edition run from immutable inputs.
- `advance(runId)` consumes committed events and exposes the next work.
- `claim(offerId, worker)` allocates a fenced attempt for one eligible worker.
- `answer(claim, result)` validates and commits one result against its exact
  active offer.
- `fail(claim, failure)` records an attempt failure without granting a late
  worker authority.
- `retry(runId, actorId)` requests a declared recoverable transition.
- `submitLead(runId, request)` atomically adds a lead while collection is open.
- `fork(runId, changes)` creates a successor for changed frozen inputs.
- `inspect(runId)` returns the declared topology, ordered events, work state,
  decisions, and artifact graph.
- `seal(runId)` exports a normalized immutable audit record for a terminal run.

The CLI under `engine/cli.ts` is an adapter over those methods:

```sh
npm run engine -- start run-spec.json
npm run engine -- inspect <run-id>
npm run engine -- continue <run-id>
npm run engine -- submit-lead <run-id> lead.json
npm run engine -- worker <run-id> worker-config.json
npm run engine -- answer <run-id> <offer-id> answer.json --principal <id>
npm run engine -- retry <run-id> <actor-id>
npm run engine -- fork <run-id> changes.json
npm run engine -- seal <run-id>
```

## Machine hierarchy

`EditionMachine` owns the complete issue:

```text
EditionMachine
  SourceMachine[]
  ArticleMachine[]
  EditorialMachine
  EditionReviewMachine
  TranslationMachine[]
  CoverArtMachine
  InteriorArtMachine
  RenderMachine
  ReleaseMachine
```

`ArticleMachine` is defined once. An edition starts it as a child actor, and
ArticleLab starts the same machine as a root actor. Given the same run spec,
answers, and policy, both placements must make the same transitions and produce
the same artifact graph.

The edition actor alone owns cross-article joins, editorial dependencies,
translation completion, registered art, render readiness, and release. A UI may
draw a different layout, but it cannot rearrange runtime ownership.

## Durable execution

XState transitions are pure. They return effects such as creating an offer,
spawning an actor, or recording a decision. `RunEngine` commits the accepted
event, new snapshot, effects, and active pointers in one short SQLite
transaction before external work starts.

SQLite runs in WAL mode and records runs, actors, ordered events, snapshots,
iterations, offers, attempts, leases, artifacts, decisions, and outbox effects.
The event journal is the audit history. A snapshot is only a resume optimization
for the exact machine version.

Coordinator and worker leases carry fencing tokens. A timed-out or replaced
worker may finish computing, but it cannot commit over the active attempt. A
committed outbox effect can be dispatched again after a crash without creating
another authoritative result.

Large artifacts use a two-part commit:

1. Write and validate an attempt-specific temporary payload.
2. Atomically rename it into the engine-owned immutable store.
3. Commit its artifact row, lineage, and completion event with the active fence.

A file without a committed artifact row has no workflow meaning and is eligible
for orphan collection after its writer lease expires.

## Repository roots and immutable revision layers

`inputs/` and `durable/` are Git-tracked roots of immutable revisions.
`inputs/` records versioned source captures and extractions, edition
specifications, prompts, policies, and run bootstraps. `durable/` records
promoted article, editorial, image, and composition revisions. Revisions never
change in place.

`.magazine/` is ignored runtime storage for each run's SQLite database, engine
artifact store, staging, leases, and worker scratch space. `output/` is ignored,
ephemeral exported material. They are filesystem projections, never workflow
authority. For edition `004`, a run is named `<UTC timestamp>--<RunId>` and uses
`.magazine/004/<UTC timestamp>--<RunId>` privately, with a matching
`output/004/<UTC timestamp>--<RunId>` root only for a permitted export.

`EngineArtifact` and `DurableRevision` are separate immutable layers.
`EngineArtifact` is run-scoped evidence committed by `RunEngine`, with exact
offer, attempt, and parent-artifact lineage. `DurableRevision` is a Git-bound
revision promoted into `durable/`; its manifest records the promotion,
accepted artifacts, decision artifacts, input revisions, and Git binding. A
durable revision is not a workflow event, and an engine artifact is not a
durable revision just because their bytes match.

`CompositionRevision` is a durable composition document that pins exact
article, editorial, image, and layout-input revisions. It may mix and match
compatible immutable revisions from different prior runs. Its explicit pins and
Git binding define the composition; paths, timestamps, and content hashes do
not discover or replace a pin.

## Identity and provenance

Runtime identity uses generated IDs: run, actor, iteration, revision, offer,
attempt, decision, and artifact IDs. Artifact bytes never change. A revision is
a new artifact that may supersede an older one.

Each offer names:

- one run, actor, state, role, and optional iteration;
- its exact ordered input artifact IDs;
- a complete immutable task artifact;
- an answer contract version;
- the worker capabilities allowed to claim it.

Each output records its exact parent artifacts and producing offer and attempt.
This creates the path from lead, raw evidence, and extraction through manuscript,
judgment, translation, art, render, approval, and release. Checksums may protect
captured bundles and distributable packages, but never decide workflow state or
reuse.

A successor may reuse an ancestor answer only when the complete declared work
identity matches by immutable ID. Equal bytes with a different artifact ID are
different inputs. Changes to a prompt, model policy, editorial policy, source,
renderer, or other frozen input create a successor run and invalidate dependent
work through explicit lineage.

## Source and editorial authority

Collection accepts leads until an exact human close decision freezes the source
set. Every accepted lead starts a `SourceMachine`. Closing collection prevents
new sources but allows already-started capture, extraction, and review work to
finish before planning.

A source becomes ready only after durable raw evidence, extraction, metadata,
and the required human source decision exist as immutable artifacts with valid
lineage. A URL or mutable path is never sufficient evidence.

Article work is staged. Deterministic measurement, worth, and mechanics finish
before evidence and shape; teaching and craft follow only when applicable. An
optional lens records `not_applicable` explicitly. A blocking decision may skip
later stages. Each revision carries its parent manuscript, working notes,
findings, human rulings, and explicit iteration budget.

Writers receive every assigned source and policy artifact. Evidence reviewers
are source-aware. Mechanics, shape, teaching, and craft reviewers are
source-blind. One worker identity cannot perform evidence review and a
source-blind review for the same manuscript revision.

Human answers bind the exact active offer, approved input artifacts, advertised
choices, and principal. They become immutable decision artifacts. A stale,
duplicate, unauthorized, or out-of-contract answer cannot advance the machine.

## Render and release

Assembly joins current approved English content, every configured translation,
registered selected art, publication metadata, and the printer profile.
Rendering never generates an image.

`measureArticle` is isolated per-draft feedback. `measureEdition` checks the full
issue immediately before render. The renderer produces complete reader, web,
booklet, package, critic, and preflight artifacts for every configured language.
Independent visual review names the exact current render artifact IDs, so a new
render cannot inherit an old approval.

Release requires the exact approved render set and an explicit human decision.
The release transaction records edition identity, package artifacts, publication
state, and unique source assignment atomically. A released or sealed run cannot
be mutated.

## Executors and retained implementation

Executors claim durable offers and answer only through `RunEngine`. Available
adapters include in-memory tests, subprocess tools, text models, image models,
human surfaces, source capture, layout measurement, rendering, and render
inspection. The worker loop owns concurrency, heartbeat renewal, timeouts,
process-group cancellation, and late-result fencing.

The old Python orchestrator, checkpoints, fingerprints, production records,
reply directories, CLI, tests, and source bridge are deleted and are not read by
the engine. The only Python boundary is the renderer subprocess. The TypeScript
worker supplies it an immutable render manifest and a caller-owned destination;
it cannot decide readiness, state, validation, export, or release.

## Viewer

The loopback-only viewer consumes `RunEngine.inspect`. It shows declared actor
topology, ordered events, offers and attempts, iterations, findings, decisions,
artifact lineage, manuscript diffs, art at original resolution, and the exact
render under review. Its human inbox claims and answers the same durable offers
as the CLI. It is not a second execution path and has no generic filesystem
route.

## Verification

Routine development is Node-only:

```sh
npm ci
npm run typecheck
npm run test:engine
npm run build:viewer
```

Tests exercise behavior through the public `RunEngine` interface. Routine
verification runs only the Node commands above. The TypeScript renderer executor
may invoke the Python renderer seam for a claimed renderer offer; no Python test
suite, Python CLI, or source bridge exists.
