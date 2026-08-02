# Magazine execution engine

This directory contains the TypeScript and XState execution authority described
in `meta/plans/graph-execution-model.md`. The retained Python tree is frozen
legacy code. It is not a shadow authority, contributor workflow, or acceptance
oracle, and the engine never reads its production records to infer state.

The public boundary is `RunEngine`. Its SQLite database is operational truth for
runs, actors, state visits, events, offers, attempts, decisions, and immutable
artifact lineage. XState transitions are pure. Durable effects are committed to
the inbox or outbox before any worker, model, renderer, or human acts on them.

## Toolchain

The exact Node, TypeScript, XState, and SQLite adapter versions are pinned in
`.node-version`, `package.json`, and `package-lock.json`.

```sh
npm ci
npm run typecheck
npm run test:engine
npm run build:viewer
```

Routine verification is Node-only. `npm run verify:engine` combines those checks
and does not run the legacy Python suite. The opt-in
`npm run test:legacy-bridge` command exists only to exercise the temporary deep
renderer seam against Edition 4 without generating images.

The retained typesetter and source archive are reachable only through versioned
adapter contracts. They receive immutable inputs and a caller-owned destination.
They do not read workflow records or write global output directories. New
workflow behavior, contracts, and tests belong in TypeScript.

`SourceArchiveExecutor` and `RendererExecutor` are the concrete worker-loop
bridges. Their stored profiles are path-free: they name artifact IDs and safe
staging targets only. For a claimed attempt, the executor copies those bytes into
an owned root and creates the adapter transport request. The renderer also checks
the assembly payload against its artifact-edge lineage, so a profile cannot use
an artifact merely by guessing its ID.

## CLI

```sh
npm run engine -- article run article-spec.json
npm run engine -- article inspect <run-id>
npm run engine -- article continue <run-id>
npm run engine -- submit-lead <run-id> lead.json
npm run engine -- article fork <run-id> changes.json
npm run engine -- article compare <run-id> <run-id>
npm run engine -- article corpus article-corpus.json
npm run engine -- worker <run-id> worker-config.json --once
npm run engine -- serve
```

Pass `--idempotency-key KEY` to `start` or `fork` when the caller may retry
after losing the response. Reusing that key resumes the committed operation;
reusing it for different immutable inputs is rejected. Starts without a key
are independent operations, even when their specs are equal.

`fork` creates an explicit successor. It may reuse an answered ancestor offer
only when the run and actor machine versions, role, slot, answer contract, task
artifact ID, subject artifact ID, ordered input artifact IDs, worker capability
contract, selected model configuration, state, and iteration dependencies all
match. Reuse references the original answer and output artifact IDs, creates no
worker attempt, and is recorded in both the offer projection and event journal.
A stale machine version can be forked into a current successor, but it cannot be
silently resumed or used as a reuse source.

The `article corpus` command accepts the versioned `article-lab-corpus/1`
contract. Every named case and variant keeps a machine-created evaluation
context artifact whose parents are the fixed corpus artifact IDs. The reusable
fixture at `fixtures/article-lab-corpus.ts` supplies two prompt variants over
one fixed input set; repeated corpus runs keep those identities and create new,
independent run IDs.

`RunEngine.collectOrphanedArtifacts()` performs fenced maintenance of the
engine-owned binary store. It preserves committed payloads and active write
intents, and collects only files that remain unreferenced after a writer lease
expires.

`worker` is the production execution surface. Without `--once` it polls until
the run is terminal or receives `SIGINT`/`SIGTERM`. It claims only offers whose
role and frozen model policy match a configured executor, renews claim leases
while work runs, aborts timed-out adapters, and submits results only through
`RunEngine.answer` or `RunEngine.fail`. Expired claims are reclaimable and late
workers remain fenced.

Worker configuration is versioned JSON. The temporary deep renderer adapter
expands to separate edition render, isolated article measurement, and
translated-language fit executors. `render_inspection` reads committed
`render_critic_report` and `printer_preflight` artifacts. Text and image models
are explicit command adapters; their commands receive the complete materialized
work package on stdin and must return one `WorkAnswer` JSON object on stdout.

TODO: Make generated-PDF QA and visual verification first-class graph behavior:
generate raster pages and contact sheets from the exact reader and booklet
ArtifactIds; model machine critic and preflight state; offer independent human
visual review over those exact artifacts and original-resolution pages; route
findings to rerender or revision; and block release until the current render set
is approved.

```json
{
  "schemaVersion": 1,
  "heartbeatIntervalMs": 30000,
  "attemptTimeoutMs": 1800000,
  "maxConcurrency": 4,
  "executors": [
    {
      "kind": "python_renderer",
      "id": "mag-renderer",
      "projectRoot": ".",
      "workDirectory": "runs/worker-temp"
    },
    {
      "kind": "render_inspection",
      "id": "render-inspection"
    }
  ]
}
```

The viewer binds only to loopback. Its human inbox claims and answers durable work
offers through `RunEngine`; it never sends events directly to an in-memory actor.
Its run-scoped artifact endpoint exposes only artifacts already present in that
run projection, which supports original-resolution art and text comparisons without
accepting filesystem paths.

## Module boundaries

- `machines/` owns lifecycle and transition semantics.
- `run-engine/` hides XState persistence, SQLite, leases, fencing, artifact
  storage, and projections.
- `task-composer/` owns article context selection and source isolation.
- `executors/` owns worker transport and subprocess behavior.
- `renderer-adapter/` and `source-adapter/` own temporary versioned deep seams.
- `view/` consumes `RunEngine.inspect` projections and has no generic filesystem
  route.

Edition 4 is an integration fixture. It stages only selected, committed art and
source media as immutable artifacts. Image generation is disabled for that fixture.

## Machine topology export

```sh
npm run graph:export -- output/machine-topology
```

The exporter uses the same ELK layered layout dependency as the run viewer and
writes two separate sets of standalone HTML, SVG, PNG, and JSON files. The
`machine-topology.*` files project every state and transition directly from the
implemented XState `machine.config` objects. The compact
`magazine-orchestration.*` files show the ten machines as one connected system
under EditionMachine, including spawn, durable child-status, join, dependency,
and feedback-route edges.

Cross-machine edges come from `machines/orchestration.ts`. EditionMachine and
RunEngine consume and validate those typed declarations, and the overview only
projects them. The graph test proves every endpoint and declaration is present,
the JSON edges exactly match the runtime projection, and all ten machines are
connected to the EditionMachine lifecycle owner.

## Edition 4 durable exercise

```sh
npm run edition4:durable
```

The command writes its SQLite run, artifact store, staged fixture, and renderer
workspace below ignored `runs/edition4-durable/`. It advances the source,
planning, article measurement and judgment, editorial, translation proof,
registered-art, renderer, visual-review, and release offers through public
`RunEngine` claims and answers. The final edition measurement and render offers
run through the versioned Python renderer adapter and reuse the committed Edition
4 English, Spanish, and selected-art artifacts. Those committed content artifacts
are intentionally initial revisions in this integration fixture, so the frozen
renderer profile can name every staged layout input before the run begins.
