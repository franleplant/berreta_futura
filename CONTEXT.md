# Repository context

This repository has one workflow authority and four storage roots. XState owns
lifecycle and joins. The public TypeScript `RunEngine` owns runs, offers,
attempts, decisions, EngineArtifacts, migration, and release authority.

## Four roots

```text
inputs/                         committed immutable source and policy inputs
durable/                        committed reusable editorial revisions
.magazine/<edition>/<run>/      ignored operational RunEngine state
output/<edition>/<run>/         ignored reproducible reader exports
```

Paths never imply workflow state. A file is usable only through the identity and
authority described below.

## Terms

- **InputRevision**: a Git-tracked immutable capture, extraction, prompt, or
  edition specification. Its `manifest.yaml` names its generated `RevisionId`,
  parent revision, payload paths, media types, sizes, and SHA-256 integrity
  digests.
- **EngineArtifact**: immutable run-owned bytes and lineage registered by
  `RunEngine`. It is the only kind of artifact a work answer can create.
- **DurableRevision**: a Git-tracked reusable manuscript, selected image, or
  composition promoted from an exact accepted EngineArtifact and its exact
  decision and input lineage.
- **CompositionRevision**: a DurableRevision that orders articles and pins each
  editorial language, article language, selected image, and layout input by its
  complete revision identity. Its public identity is
  `{editionId, compositionId, revisionId}`.
- **RenderStage**: the read-only set obtained by resolving and verifying one
  committed CompositionRevision and every revision it pins.
- **RenderExport**: reproducible public reader files derived from one approved
  render artifact set. It has no workflow authority.

`RevisionId` has the form
`rev_<UTC-basic-timestamp>_<12-random-base32>`. Content hashes protect bytes;
they are never runtime identities.

## Canonical layout

```text
inputs/sources/<source-id>/captures/<RevisionId>/manifest.yaml
inputs/sources/<source-id>/captures/<RevisionId>/raw/...
inputs/sources/<source-id>/extractions/<RevisionId>/manifest.yaml
inputs/sources/<source-id>/extractions/<RevisionId>/extracted.md
inputs/prompts/<prompt-id>/revisions/<RevisionId>/manifest.yaml
inputs/prompts/<prompt-id>/revisions/<RevisionId>/prompt.md
inputs/prompts/<prompt-id>/revisions/<RevisionId>/output.schema.json
inputs/editions/<edition-id>/specs/<spec-id>/revisions/<RevisionId>/...

durable/editions/<edition-id>/articles/<article-id>/<language>/revisions/<RevisionId>/...
durable/editions/<edition-id>/editorials/<editorial-id>/<language>/revisions/<RevisionId>/...
durable/editions/<edition-id>/images/<image-id>/revisions/<RevisionId>/...
durable/editions/<edition-id>/compositions/<composition-id>/revisions/<RevisionId>/...
```

There is no mutable `latest`, `current`, or canonical output pointer. A
CompositionRevision is the only current editorial selection.

Run directories use the persisted creation time and complete RunId:

```text
.magazine/004/2026-08-02T20-06-41.636Z--run_b2d4026a-d552-4145-83c8-d114a6866f00/
```

## Promotion and rendering

An accepted article, editorial, selected image, or composition enters
`accepted_pending_durable`. `RunEngine` creates an exact `durable_checkpoint`
offer and atomically reserves its PromotionId and RevisionId. The durable worker
materializes under the run work directory, validates manifests and bytes,
atomically installs the new revision, makes a path-scoped Git commit, and
answers through `RunEngine.answer`. Only then does `RunEngine` create the
`durable_revision_bound` EngineArtifact and advance to `durable_bound`.

Rendering resolves the exact committed CompositionRevision, including its Git
commit and blob binding. Python receives only that staged immutable input and a
caller-owned destination. Python may create PDF and web bytes; it may not choose
content, source state, art, approval, release, or output authority.

Each language export contains `reader.pdf`, `booklet.pdf`,
`booklet-cover.pdf`, `booklet-interior.pdf`, `web/`, `web.zip`, `package.zip`,
and QA evidence. The export root contains `export.json`. All output is ignored
and reproducible from committed revisions plus RunEngine artifacts.

## Migration rule

Old snapshots migrate only through public `RunEngine.planMigration` and
`RunEngine.migrate`. Migration is append-only and CAS-guarded. Old decisions and
offers remain history, but migrated editions must create durable checkpoints,
a new CompositionRevision, an exact render reconciliation or fresh render, and
fresh QA, visual review, and release authority. Physical run relocation uses a
verified clone and atomic swap with a retained rollback backup.

See [the artifact-model ADR](docs/adr/0001-four-root-artifact-model.md) and
[the architecture guide](docs/ARCHITECTURE.md) for rationale and implementation
boundaries.
