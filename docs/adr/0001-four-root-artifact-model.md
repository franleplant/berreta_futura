# ADR 0001: Four-root immutable artifact model

- Status: Accepted
- Date: 2026-08-02

## Context

The repository accumulated source archives, mutable edition trees, operational
SQLite runs, renderer scratch, and public-looking output in overlapping paths.
The same manuscript or image could appear in several places without one clear
identity or authority boundary. Path presence and content hashes were sometimes
tempting substitutes for workflow state. A retained Python pipeline also made
it possible to imagine a second orchestration authority.

The TypeScript/XState engine already owns execution authority. The filesystem
model must make that ownership obvious while preserving committed raw evidence,
accepted editorial work, selected Edition 4 images, and the complete run audit
graph.

## Decision

The repository uses exactly four top-level storage roles:

1. `inputs/` contains Git-tracked immutable InputRevisions.
2. `durable/` contains Git-tracked immutable DurableRevisions.
3. `.magazine/<edition>/<run-name>/` contains ignored operational RunEngine
   state, artifact bytes, and temporary work.
4. `output/<edition>/<run-name>/` contains ignored reproducible RenderExports.

The repository may contain code and documentation outside these roots. No other
data root may act as an input store, reusable editorial store, run store, or
publication store.

### Identity

InputRevision and DurableRevision identity uses a generated `RevisionId`:
`rev_<UTC-basic-timestamp>_<12-random-base32>`. A parent revision is explicit.
Digests verify bytes but do not choose identity, current state, or reuse.

Directory components are normalized portable lowercase values. Traversal,
case aliases, Unicode normalization aliases, symlinks, and undeclared files are
rejected.

A CompositionRevision has the public identity
`{editionId, compositionId, revisionId}`. Generic internal checkpoint code may
use a logical key, but a resolver must map it one-to-one and reject inequality.

### Authority and promotion

EngineArtifact remains the only run-owned work product. A DurableRevision can
be created only from a graph-visible `durable_checkpoint` offer. `RunEngine`
reserves the PromotionId and RevisionId in the same transaction that persists
the task. The task pins the accepted EngineArtifact, its acceptance decision,
the complete input artifact lineage, InputRevision references, and expected
parent DurableRevision.

The durable worker builds a candidate under the run work directory, validates
the complete tree, atomically renames it into `durable/`, and makes a Git commit
scoped to that one revision. The commit records the PromotionId trailer. A
retry adopts only byte-identical state with the same PromotionId. Any mismatch
becomes an integrity conflict. `RunEngine.answer` then validates the exact
active offer, lease, fence, request, evidence, manifest digest, commit OID, and
blob OIDs before it appends `durable_revision_bound`.

An automatic acceptance without an existing decision artifact receives a new
immutable `durable_acceptance_decision` EngineArtifact. Existing authority is
never rewritten.

### Composition and render

A CompositionRevision orders articles and independently pins every editorial
language, article language, selected image, and layout InputRevision. It is the
only editorial current pointer.

Renderers consume a verified RenderStage resolved from one committed
CompositionRevision. Resolution checks manifest identity, payload digests,
exact Git commit and blob binding, every child DurableRevision, and every layout
InputRevision. Working-tree-only or later-mutated bytes are rejected.

The Python subprocess is only a PDF/web byte renderer. It receives staged
committed inputs and a caller-owned destination. It cannot capture sources,
select art, advance machines, approve QA, release, or publish.

Render reconciliation is graph-visible. Existing render EngineArtifacts may be
adopted only when content, layout, languages, renderer version, artifact IDs,
and output digests match the exact request. Otherwise the edition renders again
with the same selected images. Either path requires fresh machine inspection,
visual review, and release authority.

### Migration

Snapshot migration is explicit, public, adjacent-version only, append-only,
idempotent, and guarded by expected bundle version and head event. Old snapshots
may be inspected and planned, but authority-changing operations return
`MIGRATION_REQUIRED` until migration succeeds.

Physical migration quiesces and checkpoints WAL, clones the complete database
and artifact home, verifies and migrates the clone, then atomically swaps it
into the canonical run path while retaining a read-only rollback backup. No
caller queries or edits SQLite directly.

Legacy repository inputs are imported from an explicit inventory. Source bytes
remain exact and image generation is forbidden. Durable backfill consumes only
normal graph-issued checkpoint tasks and public `RunEngine` methods.

## Consequences

- A reusable revision has a stable identity, complete provenance, and exact Git
  binding.
- Operators can distinguish committed inputs, reusable editorial state,
  operational state, and disposable output from the path alone without treating
  the path as workflow authority.
- Rendering and release can prove the exact content graph they consumed.
- A promotion or migration is more deliberate and creates additional manifests
  and commits.
- Content changes create new revisions and compositions; in-place edits are
  integrity failures.

## Rejected alternatives

- **Mutable `current` or `latest` files and symlinks.** They race, hide history,
  and cannot name the authority that changed them.
- **Content hashes as revision IDs.** Equal bytes can have different provenance
  and decisions. Hashes are integrity evidence, not identity.
- **Treating `output/` as canonical state.** Output is reproducible and cannot
  prove active offers, decisions, or release authority.
- **Direct SQLite discovery or migration.** It bypasses `RunEngine` validation,
  event history, leases, and fencing.
- **Two composition identifiers.** A simultaneous `logicalId` and
  `compositionId` creates ambiguous resolution. Public composition references
  use `compositionId` only.
- **Promoting accepted files outside the graph.** It would omit the exact offer,
  decision, and input lineage.
- **Letting Python retain workflow commands.** That would create a second
  authority and a second test oracle.
- **Reusing old render approval after migration.** Even identical-looking bytes
  do not prove current lineage. Reconciliation still requires new downstream
  QA and human authority.
- **Moving the live run in place.** A verified clone and atomic swap provide a
  recoverable boundary for database and artifact-home relocation.
