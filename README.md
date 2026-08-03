# Magazine execution engine

This repository builds private-first, source-faithful magazine editions through
one TypeScript and XState execution engine. It is the sole workflow,
orchestration, state, validation, and export authority.

The root `EditionMachine` owns collection, source preparation, planning, English
article and editorial work, art, edition review, translation, assembly, render,
independent visual approval, and release. The same `ArticleMachine` also runs as
a standalone root for fast prompt and model experiments.

`RunEngine` is the public execution boundary. SQLite stores ordered events,
snapshots, offers, attempts, leases, human decisions, immutable artifact lineage,
validation, and export state. Callers do not inspect run directories,
reconstruct state, or send events to live actors.

## Setup and verification

The Node, TypeScript, XState, SQLite, and viewer dependencies are pinned exactly.

```sh
npm ci
npm run verify:engine
```

Routine verification is Node-only. It type-checks the engine, runs the public
engine tests, and builds the viewer. Do not run Python tests or a legacy Python
CLI. When rendering is needed, the TypeScript worker invokes the isolated Python
renderer seam with an immutable manifest and a caller-owned destination.

## Repository roots

Two Git-tracked roots hold immutable, reviewable revisions:

- `inputs/` contains source evidence, source extractions, edition specifications,
  prompts, policies, and run bootstrap revisions.
- `durable/` contains promoted article, editorial, image, and composition
  revisions.

Two ignored roots hold disposable operational material:

- `.magazine/` holds each run's SQLite database, engine artifact store, leases,
  staging, and worker scratch space.
- `output/` holds ephemeral exported files. It is never an input to workflow
  state or validation.

For edition `004`, the engine gives every run one name in the form
`<UTC timestamp>--<RunId>`. Its runtime root is
`.magazine/004/<UTC timestamp>--<RunId>`; a permitted export is written to the
matching `output/004/<UTC timestamp>--<RunId>` root.

### Engine artifacts and durable revisions

An `EngineArtifact` is a `RunEngine` artifact: immutable, scoped to its run,
and linked to the offer, attempt, and parent artifacts that produced it. A
`DurableRevision` is a separately immutable, Git-bound revision under
`durable/`, promoted from accepted engine artifacts. The two identities answer
different questions and must not be substituted for each other.

A `CompositionRevision` is the deliberate selector between them. Its composition
document pins the exact article, editorial, image, and layout-input revisions
for one edition. It may mix and match compatible immutable revisions from prior
work, including revisions produced by different runs. The explicit pins and Git
binding decide what is composed; neither timestamps, matching bytes, nor a
directory scan do.

## Durable CLI

Every command uses the same engine database and artifact repository. Runtime
storage belongs below ignored `.magazine/`; callers may use `--db` and
`--artifacts` only to select an explicit engine-owned runtime location.

```sh
# Start an article or edition from a strict immutable run specification.
npm run engine -- start run-spec.json

# Inspect or advance durable work.
npm run engine -- inspect <run-id>
npm run engine -- continue <run-id>

# Add a source while an edition collection remains open.
npm run engine -- submit-lead <run-id> lead.json

# Run configured non-human executors.
npm run engine -- worker <run-id> worker-config.json

# Answer a human offer, retry an actor, or fork frozen inputs.
npm run engine -- answer <run-id> <offer-id> answer.json --principal reviewer-id
npm run engine -- retry <run-id> <actor-id>
npm run engine -- fork <run-id> changes.json

# Compare and promote settled article experiments.
npm run engine -- compare <run-id-a> <run-id-b>
npm run engine -- promote <run-id> promotion.json

# Export an immutable terminal audit record.
npm run engine -- seal <run-id>
```

Provide an `--idempotency-key` when a caller may retry `start` or `fork` after
losing a response. Equal specifications without the same explicit key create
independent runs.

## Viewer

Build and start the loopback-only viewer:

```sh
npm run build:viewer
npm run engine -- serve
```

The viewer renders the declared actor topology, ordered events, offers,
iterations, decisions, and artifact lineage from `RunEngine.inspect`. Its human
inbox claims and answers exact durable offers. It has no filesystem browser or
second execution path.

## Architecture

- `engine/machines/` owns XState lifecycle and joins.
- `engine/run-engine/` owns persistence, fencing, artifacts, provenance, replay,
  and public projections.
- `engine/task-composer/` owns complete role inputs and source isolation.
- `engine/executors/` owns workers, leases, subprocess transport, and model
  policy routing.
- `engine/renderer-adapter/` and `engine/source-adapter/` define temporary deep
  implementation seams.
- `engine/article-lab/` owns repeated article experiments, comparison, and
  promotion.
- `engine/view/` is a read projection plus revision-safe human inbox.

The old Python pipeline, Python CLI, Python tests, and Python source bridge are
deleted. The remaining Python package implements only the versioned PDF/web
renderer adapter, launched by the TypeScript worker with an immutable manifest
and caller-owned destination. New orchestration, contracts, tests, and
contributor workflows belong in the TypeScript engine.

See [engine/README.md](engine/README.md) for worker configuration and adapter
details, and [meta/plans/graph-execution-model.md](meta/plans/graph-execution-model.md)
for the design model.
