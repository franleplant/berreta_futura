# Magazine execution engine

This repository builds private-first, source-faithful magazine editions through
one durable TypeScript and XState workflow.

The root `EditionMachine` owns collection, source preparation, planning, English
article and editorial work, art, edition review, translation, assembly, render,
independent visual approval, and release. The same `ArticleMachine` also runs as
a standalone root for fast prompt and model experiments.

`RunEngine` is the public execution boundary. SQLite stores ordered events,
snapshots, offers, attempts, leases, human decisions, immutable artifact lineage,
and atomic release state. Callers do not inspect run directories, reconstruct
state, or send events to live actors.

## Setup and verification

The Node, TypeScript, XState, SQLite, and viewer dependencies are pinned exactly.

```sh
npm ci
npm run verify:engine
```

Routine verification is Node-only. It type-checks the engine, runs the public
engine tests, and builds the viewer. The retained Edition 4 bridge check is
explicit and opt-in:

```sh
npm run test:legacy-bridge
```

That integration reuses Edition 4's committed art and never generates images.

## Durable CLI

Every command uses the same engine database and artifact repository. The default
locations are under ignored `runs/` paths and may be overridden with `--db` and
`--artifacts`.

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

The retained Python tree is legacy implementation, not workflow authority. It
stays only until its removal is explicitly requested. New orchestration,
contracts, tests, and contributor workflows belong in the TypeScript engine.

See [engine/README.md](engine/README.md) for worker configuration and adapter
details, and [meta/plans/graph-execution-model.md](meta/plans/graph-execution-model.md)
for the design model.
