# Renderer transition record

The old Python pipeline, CLI, tests, and source bridge are deleted. Python
survives only as an isolated PDF/web renderer implementation seam. It is not a
contributor workflow, a release procedure, or an acceptance oracle for the
TypeScript engine.

## Current authority

`RenderMachine` coordinates rendering through `RunEngine`. The TypeScript
`RendererExecutor` invokes the renderer through a versioned adapter. It receives
only an immutable render manifest and a caller-owned destination, then returns a
structured result. It does not read production records, choose a workflow state,
validate an edition, export a publication, or write a canonical output directory.

Use `npm run engine -- worker <run-id> <worker-config.json>` to execute a
claimed renderer offer. Lifecycle work, including retries, decisions, and
approval, must use the corresponding `RunEngine` operation through
`npm run engine -- ...`; never use a filesystem operation to advance a run. Do
not invoke the renderer directly or use a Python CLI.

`measureArticle` is per-draft feedback and reports actual opener fit and source
article page count. `measureEdition` is a separate full-issue gate. Rendering
requires current approved content, every configured translation, selected art,
and a printer profile. It produces exact per-language reader, web, booklet,
package, inspection, and preflight artifacts.

An independent visual reviewer must approve the exact current render artifact
IDs at original resolution. A later render has new IDs and cannot inherit that
approval. No edition is press-ready until each configured language has passing
preflight artifacts and explicit studio readiness.

## Repository boundary

The manifest may name only artifacts authorized by the claimed render offer and
is materialized into an owned workspace under `.magazine/`. Renderer files return
to `RunEngine` as immutable engine artifacts. `inputs/` and `durable/` hold
Git-tracked immutable revisions; `output/` is an ignored, ephemeral export
projection. For edition `004`, each runtime and matching export root is named
`<UTC timestamp>--<RunId>`. Renderer output paths never define workflow state.

Routine checks stay Node-only:

```sh
npm run typecheck
npm run test:engine
npm run build:viewer
```
