# Renderer transition record

The Python renderer transition described in earlier versions of this document is
frozen implementation history. It is not a contributor workflow, a release
procedure, or an acceptance oracle for the TypeScript engine.

## Current authority

`RenderMachine` coordinates rendering through `RunEngine`. The renderer is a
versioned deep adapter: it receives an immutable render manifest and a
caller-owned temporary destination, then returns a structured result. It does
not read production records, choose a workflow state, or write a canonical
output directory.

Use `npm run engine -- worker <run-id> <worker-config.json>` to execute a
claimed renderer offer. Lifecycle work, including retries, decisions, and
approval, must use the corresponding `RunEngine` operation through
`npm run engine -- ...`; never use a retained `mag` command or a filesystem
operation to advance a run.

`measureArticle` is per-draft feedback and reports actual opener fit and source
article page count. `measureEdition` is a separate full-issue gate. Rendering
requires current approved content, every configured translation, selected art,
and a printer profile. It produces exact per-language reader, web, booklet,
package, inspection, and preflight artifacts.

An independent visual reviewer must approve the exact current render artifact
IDs at original resolution. A later render has new IDs and cannot inherit that
approval. No edition is press-ready until each configured language has passing
preflight artifacts and explicit studio readiness.

## Retained legacy context

The retained Python typesetter may temporarily implement the adapter interface.
The historical ReportLab and WeasyPrint comparison material is useful only when
maintaining that seam. It neither defines engine state nor permits a legacy
build, review, or release command. Edition 4 remains an opt-in seam fixture:
its selected committed art may be staged for the test, and image generation is
forbidden.
