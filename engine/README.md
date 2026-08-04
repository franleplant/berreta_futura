# Magazine execution engine

This directory contains the TypeScript and XState execution authority described
in `meta/plans/graph-execution-model.md`. It is the sole workflow,
orchestration, state, validation, and export authority. The old Python pipeline,
CLI, tests, and source bridge are deleted. Python remains only as a renderer
subprocess implementation, not a shadow authority, contributor workflow, or
acceptance oracle.

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

Routine verification is Node-only. `npm run verify:engine` combines those
checks. Do not invoke Python tests, a Python CLI, or a source bridge. The
TypeScript renderer executor is the only component that invokes the Python seam
when it holds a claimed renderer offer.

The renderer is reachable only through its versioned adapter contract. It
receives an immutable manifest and a caller-owned destination. It does not read
workflow records or write a canonical output directory. Source capture is
TypeScript-only. New workflow behavior, contracts, and tests belong in
TypeScript.

`SourceArchiveExecutor` and `RendererExecutor` are TypeScript worker-loop
executors. `RendererExecutor` alone crosses the Python seam. Their stored
profiles are path-free: they name artifact IDs and safe staging targets only. For
a claimed attempt, the executor copies those bytes into an owned root and creates
the adapter transport request. The renderer also checks the assembly payload
against its artifact-edge lineage, so a profile cannot use an artifact merely by
guessing its ID.

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

The low-level commands accept explicit `--db` and `--artifacts` paths. When
they are omitted, their isolated development state is `.magazine/dev/run.sqlite`
and `.magazine/dev/artifacts`; they never create a `runs/` directory.

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

Worker configuration is versioned JSON. The renderer adapter has separate
edition-render and edition-measure executors. `render_inspection` reads committed
`render_critic_report` and `printer_preflight` artifacts. Text and image models
are explicit command adapters; their commands receive the complete materialized
work package on stdin and must return one `WorkAnswer` JSON object on stdout.

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
      "workDirectory": ".magazine/004/worker-temp",
      "toolchain": {
        "uvExecutable": "/absolute/path/to/uv",
        "pythonExecutable": "/absolute/path/to/python",
        "expected": {
          "uvSha256": "sha256:<64 hex characters>",
          "uvVersion": "0.9.0",
          "pythonSha256": "sha256:<64 hex characters>",
          "pythonVersion": "3.12.11",
          "pythonImplementation": "CPython",
          "pythonCacheTag": "cpython-312",
          "platform": "darwin-arm64"
        }
      }
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

## Repository roots, artifacts, and composition

`inputs/` and `durable/` are Git-tracked immutable revision roots. `inputs/`
holds evidence, specifications, prompts, policies, and bootstrap revisions.
`durable/` holds promoted article, editorial, image, and composition revisions.
`.magazine/` is ignored runtime storage for per-run SQLite databases, engine
artifacts, staging, and worker scratch space. `output/` is ignored, ephemeral
export material. Paths are not workflow evidence.

For edition `004`, each run has one engine-generated name,
`<UTC timestamp>--<RunId>`. Its runtime storage is
`.magazine/004/<UTC timestamp>--<RunId>`; any export uses the matching
`output/004/<UTC timestamp>--<RunId>` root.

An `EngineArtifact` is immutable run-scoped evidence committed by `RunEngine`,
with producing offer, attempt, and parent-artifact lineage. A `DurableRevision`
is a separately immutable, Git-bound promoted revision in `durable/`. Promotion
records the accepted engine artifact IDs, decisions, input revisions, and Git
binding. Do not use a durable path as an artifact ID or an artifact ID as a
durable revision reference.

A `CompositionRevision` is a durable revision whose `composition.yaml` pins the
exact article and editorial language revisions, image revisions, and layout
input revisions. It can mix and match compatible immutable revisions from
different prior runs. Its explicit revision pins and Git binding select the
edition inputs; a filesystem scan, matching content, or a timestamp never does.

## Machine topology export

```sh
npm run graph:export -- output/machine-topology
```

The exporter uses the same ELK layered layout dependency as the run viewer and
writes two separate sets of standalone HTML, SVG, PNG, and JSON files. The
`machine-topology.*` files project every state, guarded transition, internal
transition, and entry action directly from the implemented XState
`machine.config` objects. The compact
`magazine-orchestration.*` files show the ten machines as one connected system
under EditionMachine, including spawn, durable child-status, join, dependency,
and feedback-route edges.

To render one implemented machine as its own standalone graph, pass its runtime
machine kind:

```sh
npm run graph:export -- output/article-machine --machine article
```

This writes `article-machine.html`, `article-machine.svg`,
`article-machine.png`, and `article-machine.json`. Supported kinds are
`edition`, `source`, `article`, `editorial`, `edition_review`, `translation`,
`cover_art`, `interior_art`, `render`, and `release`.

Focused exports use a vertical primary lifecycle. Internal retries, revision
returns, and failures remain exact but move into labeled transition indexes
below the graph instead of crossing the pipeline. State descriptions and entry
actions come from the live XState config and render inside their state nodes.

Cross-machine edges come from `machines/orchestration.ts`. EditionMachine and
RunEngine consume and validate those typed declarations, and the overview only
projects them. The graph test proves every endpoint and declaration is present,
the JSON edges exactly match the runtime projection, and all ten machines are
connected to the EditionMachine lifecycle owner.

## Edition 4 render exercise

```sh
npm run edition4:durable
```

This is the canonical Edition 4 command. It resolves the committed
`run_bootstrap` revision `rev_20260802T230000035Z_poyigg2sur72`, allocates or
resumes its one canonical runtime run, and lets `EditionBootstrapRunner` execute
only the configured non-human offers through `RunEngine`.

The Edition 4 bootstrap reuses only its selected committed article, editorial,
translation, source, and art revisions. It never generates an image. Its final
measurement and render offers cross the versioned Python renderer seam. At the
pending human visual-review boundary, the runner creates a fenced,
non-authoritative projection of the exact render artifacts under the matching
ignored `output/004/<UTC timestamp>--<RunId>/` directory. That projection does
not claim or answer the human offer, does not approve the render, and does not
release the edition.
