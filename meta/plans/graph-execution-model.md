# Graph execution model: the XState edition engine

Status: **proposed**, not started. Revision 6, 2026-08-02.

This revision supersedes revisions 1 through 5. It incorporates the adversarial
review and the decisions that followed it:

- One hierarchical state machine encompasses the complete edition lifecycle:
  source collection, capture, extraction, article production, editorial, image
  generation and selection, translation, issue review, rendering, visual review,
  release, and publication.
- `ArticleMachine` is a reusable child actor of `EditionMachine`. The exact same
  machine can also run as the root of an article-only run for fast writing and
  judging experiments.
- XState owns control flow. A small `RunEngine` owns durable execution.
- Runtime identity uses immutable IDs and database transactions, not pervasive
  content hashes and not filesystem scans.
- The old Python production orchestrator is replaced, not preserved, emulated,
  shadowed, or treated as an acceptance oracle.
- Useful deep Python modules, especially the renderer, may remain temporarily
  behind a subprocess interface. Their old orchestration and record formats do not.

The design goal is a smaller system, not a TypeScript translation of the existing
one.

---

## 1. Decisions

### 1.1 One edition machine

There is one root `EditionMachine` for a complete issue. It owns every child actor
and every join required to produce and release the edition.

```text
edition created
  -> collect and prepare sources
  -> freeze edition plan
  -> produce English content and art in parallel
  -> judge the issue and route revisions
  -> translate every configured language
  -> join content and registered art
  -> measure and render
  -> visual review
  -> release approval
  -> released
```

The view may draw this as one graph with nested actors. Runtime ownership follows
the domain. It is never rearranged to accommodate a graph widget.

### 1.2 One reusable article machine

`ArticleMachine` is defined once.

- `EditionMachine` starts one actor per planned article.
- An article-only run starts the same machine as its root.
- An article experiment can fork another article run while reusing immutable source
  artifacts by ID.
- A settled article experiment may seed a new edition run or an article actor that
  has not started. It never mutates an active edition run behind the machine's back.

This is the fast loop for improving article generation, feedback, and judging. It
does not require source collection, images, editorial, translation, or rendering to
run.

### 1.3 Statechart and durable engine are separate modules

XState answers:

- Which states exist?
- Which event may move an actor?
- Which work can run concurrently?
- Which results open another iteration?
- Which child actors must join before the edition may advance?

`RunEngine` answers:

- Which run, actor visit, attempt, and work offer is this?
- Which immutable artifacts were supplied?
- Has this answer become stale?
- Was state committed before a crash?
- May another process claim this work?
- What happened, in causal order?

Neither module pretends to solve the other's problem.

### 1.4 No pervasive hashing

The engine does not hash files to discover state, invalidate work, resume a run, or
decide whether output can be reused.

Runtime identity uses generated IDs:

- `RunId`
- `ActorId`
- `ArtifactId`
- `RevisionId`
- `AttemptId`
- `WorkOfferId`
- `DecisionId`

Once an artifact receives an ID, its bytes never change. Editing creates a new
artifact and a new revision. A work offer names the exact input artifact IDs it was
created from. A late answer is rejected when its offer is no longer active.

Checksums remain allowed only at integrity boundaries where they have a separate
purpose, such as a captured raw bundle, a final distributable package, or optional
large-binary corruption detection. A checksum never determines workflow state.

### 1.5 The old orchestrator dies

There is no migration layer for old production records, no dual writer, no parity
suite against the old graph, and no requirement to preserve its deterministic
checks.

The replacement may retain useful domain text, prompt material, the source archive,
and deep rendering modules. It does not retain the old scheduler, replay algorithm,
fingerprints, checkpoint vocabulary, agent reply directory protocol, or workflow
state derivation.

As replacement slices land, the superseded orchestration code and tests are deleted.
There is no final compatibility phase.

---

## 2. Machine hierarchy

```text
EditionMachine
  SourceMachine[]
  ArticleMachine[]
  EditorialMachine
  EditionReviewMachine
  TranslationMachine[]
  CoverArtMachine
  InteriorArtMachine
    ImageAssetMachine[]
  RenderMachine
  ReleaseMachine
```

Actors have stable IDs allocated by `RunEngine`. Output paths do not identify actors.

The edition actor is the only owner of cross-article joins, editorial dependencies,
edition-level art, rendering, and release.

### 2.1 Edition lifecycle

```text
created
  -> collecting
  -> planning
  -> producing
  -> translating
  -> assembling
  -> rendering
  -> awaiting_visual_review
  -> awaiting_release_approval
  -> released

Any non-recoverable state
  -> failed

Any unresolved human-authority or iteration-budget state
  -> awaiting_editor
```

`producing` contains parallel content and art regions. They synchronize only at
declared dependencies and at `assembling`.

### 2.2 Collection and source preparation

`collecting` accepts lead events until a human closes the collection.

Each lead starts a `SourceMachine`:

```text
lead_received
  -> capturing
  -> extracting
  -> awaiting_source_review
  -> ready

capture or extraction failure
  -> source_failed
```

The source actor produces immutable artifacts for:

- the submitted lead;
- the durable raw evidence bundle;
- extracted text and media;
- source metadata and human annotations;
- the provenance edge from the lead to the captured primary source.

A source is not `ready` merely because a URL exists. The exact source revision used
by an article is an `ArtifactId`, not a live path.

`CLOSE_COLLECTION` is a human event. It freezes the source set for the run and moves
the edition to `planning`. New external sources require a successor edition run.

### 2.3 Planning

Planning creates immutable edition inputs:

- edition brief and thesis;
- article specifications;
- ordered source assignments for every article;
- content modes and author/source attribution;
- configured languages;
- art direction and required image inventory;
- iteration, cost, and concurrency policy;
- renderer and release profile.

The planning decision records who approved the assignments. Article actors cannot
start without complete source assignments.

Changing a planning input after production begins does not edit the current run. It
forks a successor run with explicit changed inputs and retained ancestor artifacts.

### 2.4 Producing English content and art

The `producing` state has two parallel regions:

```text
content region                         art region
--------------                         ----------
ArticleMachine[]                       art direction ready
  -> all features settled                -> CoverArtMachine
  -> EditorialMachine                    -> InteriorArtMachine
  -> EditionReviewMachine                -> all required art registered
  -> English content approved
```

The regions exchange only declared artifact events. For example:

- an article revision may publish an illustration brief artifact;
- the editorial may publish the final editorial reading used by the cover actor;
- an image selection publishes a registered image artifact;
- no image generation is triggered by rendering.

### 2.5 Edition review and revision routing

After all feature articles and the editorial settle, `EditionReviewMachine` judges
the issue as a whole.

Its decision may:

- approve the English issue;
- route findings to one or more named articles;
- route findings to the editorial;
- request a human `editor_decision`;
- escalate when the issue cannot be repaired automatically.

Routing a finding to an article sends a durable event to that `ArticleMachine`. The
article creates a new manuscript revision and re-enters its judging stages. Any
editorial artifact that consumed the earlier article revision is no longer current,
so `EditorialMachine` runs again. The edition review then runs against the new set of
artifact IDs.

Render is unreachable without a current approving edition decision.

### 2.6 Translation

Translation begins only after English content has a current approving edition
decision.

One `TranslationMachine` runs per configured non-English language. It consumes the
exact English article, editorial, furniture, and caption artifact IDs.

```text
translation drafting
  -> language review
  -> per-piece language fit
  -> language settled

revision required
  -> translation drafting
```

If approved English content changes, the old translation artifacts remain in history
but are not current. New translation work consumes the new English artifact IDs.

Every configured language must settle before assembly. A fit breach in Spanish routes
to the Spanish translation actor, not to the English writer unless the editor makes an
explicit cross-language decision.

### 2.7 Assembly, render, and release

Assembly joins:

- current approved English content;
- settled translations for every configured language;
- registered cover art;
- all required registered interior art;
- current edition metadata and printer profile.

Two different measurements exist and keep different names:

- `measureArticle` gives per-draft article feedback inside `ArticleMachine`.
- `measureEdition` checks full-issue pagination, language output, and booklet
  imposition immediately before render.

They are not interchangeable and do not share a state.

`RenderMachine` calls one deep renderer interface. The current Python typesetter may
implement that interface initially, but its workflow gates and canonical output
assumptions do not cross the seam.

```text
assemble immutable render manifest
  -> render all languages
  -> build reader, web, booklet, and package artifacts
  -> machine render inspection
  -> awaiting independent visual review
```

Human visual approval references exact render artifact IDs. Any new render creates new
IDs and therefore cannot inherit the old approval.

`ReleaseMachine` requires an explicit human release decision that names the approved
render set. Release atomically records source assignment, edition identity, package
artifacts, and publication state. A released edition is final.

---

## 3. ArticleMachine

### 3.1 The statechart

```text
initializing
  -> drafting
  -> stage_1
       parallel: measureArticle, worth, mechanics
  -> stage_1_decision
  -> stage_2
       parallel: evidence, shape
  -> stage_2_decision
  -> stage_3
       parallel: teaching?, craft
  -> deciding
       pass             -> settled
       revise           -> drafting
       editor_decision  -> awaiting_editor
       budget_exhausted -> escalated
       drop             -> dropped
```

All lenses do not enter one parallel state. Each stage completes before the next stage
is eligible. A blocking finding can skip later stages for that iteration.

An optional lens produces an explicit `not_applicable` result. Absence never means
both "not applicable" and "crashed."

### 3.2 Inputs

An article run starts from an immutable `ArticleRunSpec`:

```ts
type ArticleRunSpec = {
  articleId: string;
  editionContext?: ArtifactId;
  articleBrief: ArtifactId;
  sources: readonly ArtifactId[];
  writerPrompt: ArtifactId;
  judgePrompts: Readonly<Record<JudgeLens, ArtifactId>>;
  writingRules: ArtifactId;
  initialManuscript?: ArtifactId;
  policy: ArticlePolicy;
  modelPolicy: ModelPolicy;
};
```

The standalone runner supplies the same spec that the edition parent supplies. The
edition context is optional only when the article genuinely does not need it.

### 3.3 Iterations are explicit

A loop is a state transition. Every durable visit through that loop still has an
explicit `IterationId`.

An iteration records:

- its parent manuscript revision;
- the new manuscript artifact;
- writer working notes;
- carried findings and human rulings;
- applicable lenses;
- one attempt and result per lens;
- the decision that settled, revised, escalated, or dropped it.

The next iteration is allocated only from a committed `revise` decision. It is never
inferred by counting files or directories.

### 3.4 Role and context isolation

Dispatch transport is generic. Task composition and worker assignment are not.

The engine enforces:

- one work offer concerns one role, one actor, and one article;
- writer tasks receive every assigned source artifact and the complete revision
  context;
- source-aware evidence work receives sources;
- source-blind work cannot receive sources;
- the same worker identity cannot perform evidence and source-blind line or craft
  review for the same article revision;
- replies must satisfy the role's typed output contract;
- a late or duplicate answer cannot replace the active answer.

These are state and authority semantics, not editorial heuristics.

### 3.5 Fit feedback

`measureArticle` uses the production layout interface on an isolated article document.
It reports actual layout facts, including opener fit and article page count.

Before relying on it, tests must prove that the isolated measurement matches the same
article placed in representative full editions, including left/right page parity,
figures, code, and opener art.

The measurement is feedback to the writer and decision actor. It is not replaced by a
character-count gate.

### 3.6 Human authority and escalation

`awaiting_editor` records the exact finding, manuscript revision, available choices,
and human offer ID. A human ruling is immutable and references that offer.

An escalated article is never accepting. A human may:

- provide a repair;
- change the iteration budget;
- provide an editorial ruling;
- drop the article;
- fork a successor article run with changed policy.

The iteration budget is an explicit input, not a hidden constant.

---

## 4. Article-only experimentation

The article path is the first executable vertical slice because it is where prompt,
model, feedback, and judge design can be improved fastest.

Conceptual command surface:

```text
mag article run <article-spec>
mag article inspect <run-id>
mag article continue <run-id>
mag article fork <run-id> --change <named-input>
mag article compare <run-id> <run-id> [...]
mag article promote <run-id>
```

`continue` advances a waiting run after available answers have arrived. It does not
scan the filesystem.

`fork` creates a successor run. Unchanged immutable artifacts are referenced by ID.
Changed inputs receive new artifact IDs. `RunEngine` computes which actor outputs are
eligible for reuse from declared artifact dependencies and state-contract versions.
No content digest is computed.

`compare` presents:

- final manuscripts;
- revision histories;
- judge findings and decisions;
- human preferences;
- model, prompt, cost, and latency metadata;
- article layout measurements.

It does not collapse quality into one deterministic score.

`promote` marks one settled article artifact as a candidate input. A new edition run or
an unstarted article actor can consume it. Promotion never rewrites an active actor's
current artifact.

### ArticleLab

`ArticleLab` is a thin orchestration mode above `ArticleMachine`, not another article
workflow. It starts several independent article runs with deliberate differences in:

- writer prompt;
- model or model settings;
- revision budget;
- judge prompt or stage policy;
- supplied editor feedback.

It compares outputs and records the human choice. The winning configuration becomes a
new versioned policy artifact. The losing runs remain inspectable.

---

## 5. Durable RunEngine

`RunEngine` is a deep module. XState, SQLite, locking, outbox dispatch, artifact
storage, attempt fencing, replay, and snapshots remain inside it.

### 5.1 External interface

```ts
type RunSpec = EditionRunSpec | ArticleRunSpec;

type RunOutcome =
  | { status: "running"; runId: RunId }
  | { status: "waiting"; runId: RunId; offers: readonly WorkOfferView[] }
  | { status: "awaiting_editor"; runId: RunId; offers: readonly WorkOfferView[] }
  | { status: "complete"; runId: RunId; outputs: readonly ArtifactId[] }
  | { status: "escalated"; runId: RunId; actors: readonly ActorId[] }
  | { status: "failed"; runId: RunId; failures: readonly FailureView[] };

interface RunEngine {
  start(spec: RunSpec): Promise<RunOutcome>;
  advance(runId: RunId): Promise<RunOutcome>;
  answer(
    offerId: WorkOfferId,
    answer: WorkAnswer,
    worker: WorkerIdentity,
  ): Promise<RunOutcome>;
  fork(runId: RunId, changes: readonly RunInputChange[]): Promise<RunOutcome>;
  inspect(runId: RunId): Promise<RunView>;
}
```

Callers do not read SQLite, mutate run directories, send directly to an in-memory
actor, delete outputs, or reconstruct state.

### 5.2 SQLite is operational truth

One SQLite database in WAL mode stores small, transactional state:

- runs and machine versions;
- actor identities and current states;
- ordered events;
- iterations and attempts;
- work offers and claims;
- artifacts and artifact dependencies;
- human and machine decisions;
- outbox effects;
- current XState snapshots.

The engine never scans artifact files to infer progress.

Each mutating operation runs under a short database transaction. The run has one
active coordinator lease with a fencing token. Node claims also carry fencing tokens
so a replaced coordinator or timed-out worker cannot commit late output.

### 5.3 Pure statechart, durable effects

XState does not directly launch long-running subprocesses or model calls.

For each accepted event, `RunEngine`:

1. acquires the run lease;
2. loads the machine version and persisted control state;
3. feeds the event into the statechart;
4. collects pure effects such as `CREATE_WORK_OFFER` or `SPAWN_ARTICLE_ACTOR`;
5. stores the event, new control state, effects, and active pointers atomically;
6. commits;
7. dispatches committed outbox work.

If the process dies before commit, nothing happened. If it dies after commit, the
outbox is still present and another process may dispatch it idempotently.

No XState promise actor is left alive while a human or model works.

### 5.4 Events and snapshots

The ordered event journal is the history used by the viewer and audit tools. Events
include causal IDs, actor IDs, previous and next state, and related offer, attempt,
artifact, or decision IDs.

The current XState snapshot is a resume optimization for the exact machine version.
It is not the timeline and not the provenance record.

A run cannot silently resume under another machine version. It requires an explicit
state migration or a successor run.

### 5.5 Work offers and attempts

A `WorkOffer` contains:

```ts
type WorkOffer = {
  id: WorkOfferId;
  runId: RunId;
  actorId: ActorId;
  state: string;
  iterationId?: IterationId;
  role: WorkRole;
  inputArtifacts: readonly ArtifactId[];
  taskArtifact: ArtifactId;
  contractVersion: string;
  allowedWorkerCapabilities: readonly WorkerCapability[];
};
```

The task artifact contains the complete prompt or human decision request. Rewording a
UI wrapper does not alter it. Changing the actual task creates a new task artifact and
offer.

An executor atomically claims an offer and receives an `AttemptId`. Retries create new
attempt IDs. Only the active attempt may commit an answer. A late answer is retained as
a superseded artifact but cannot advance the machine.

### 5.6 Artifact storage

Small text and JSON artifacts may live in SQLite. Large binaries live under an engine
owned artifact directory:

```text
runs/<run-id>/
  artifacts/<artifact-id>/payload
  exports/
  logs/
```

The directory layout is an implementation detail of `RunEngine`.

Large output commit protocol:

1. write to an attempt-specific temporary path;
2. flush and close;
3. validate the output contract;
4. atomically rename into the immutable artifact location;
5. commit the artifact row and completion event using the active fencing token;
6. leave an unreferenced file for garbage collection if the database commit loses a
   race or fails.

Only a committed artifact row counts as output. File presence has no state meaning.

### 5.7 Artifact lineage without hashes

Every artifact records:

- its generated `ArtifactId`;
- kind and schema version;
- producing run, actor, attempt, and work offer;
- exact parent artifact IDs;
- source or human origin when it was not generated;
- model, tool, command, and timing metadata where applicable;
- whether it supersedes another artifact.

This forms a provenance graph from lead to source to manuscript to judgment to render.
No content digest is required because referenced artifacts are immutable.

Prompt text is stored as an artifact, not merely a mutable path. Model configuration
is stored as data. The machine has an explicit semantic version. Git revision may be
recorded as diagnostic metadata but is not a cache key or work identity.

### 5.8 External changes and successor runs

The event policy is unambiguous:

- Results, judge findings, human decisions, retries, and internal revision loops are
  events within the active run.
- A change to frozen source, planning, prompt, policy, renderer, or other starting
  input creates a successor run through `fork`.
- There is no filesystem watcher and no supported in-place edit of immutable artifacts.
- A mutable working copy is not an artifact until it is submitted, at which point it
  receives a new ID.

`fork` records the parent run and explicit input changes. Reuse is by reference to
unchanged immutable artifact IDs. The engine computes downstream eligibility from
declared dependencies. Callers never copy or delete run directories.

### 5.9 Sealing and repository provenance

SQLite is operational truth while a run is active. When a run reaches a terminal
checkpoint, the engine can export a normalized, append-only text record for Git:

- run specification;
- actor and event journal;
- work offers and answers;
- artifact metadata and lineage;
- human decisions;
- final output references.

The export is generated from the database and is never read to resume a run. A sealed
run does not mutate. Large binaries may use a separate retained artifact store, while
the committed record keeps stable artifact IDs and locations.

---

## 6. Execution adapters

The executor seam is real because multiple adapters exist:

- local subprocess adapter for TypeScript, Python, and other commands;
- text-model adapter for `codex`, `claude`, or another configured model runner;
- image-model adapter;
- human adapter exposed through CLI or web UI;
- in-memory test adapter.

All adapters consume `WorkOffer` and answer through `RunEngine.answer`. They never write
active state directly.

The subprocess adapter owns:

- executable and argument construction;
- stdin and structured input;
- working directory and environment;
- timeout and cancellation;
- process-group termination;
- stdout and stderr capture;
- exit classification;
- model/tool metadata;
- temporary output paths.

The Python renderer sits behind one versioned JSON interface:

```text
render(render-manifest.json, destination-directory)
  -> render-result.json
```

It receives immutable input artifacts and a caller-owned temporary destination. It
does not read old production records, decide workflow readiness, or write a global
canonical output directory.

---

## 7. TypeScript and XState stack

The engine and machines are TypeScript.

Initial choices:

- XState v5, pinned to an exact version;
- an exact Node LTS patch version, not a floating "current LTS" promise;
- native TypeScript execution only if the pinned Node version supports every required
  construct;
- `tsc --noEmit` in verification, because Node execution does not type-check;
- strict TypeScript with `noUncheckedIndexedAccess` and
  `exactOptionalPropertyTypes`;
- SQLite with one selected, pinned Node adapter;
- `node:test` for tests;
- React Flow and ELK for the later viewer;
- a lockfile committed with every dependency change.

The machine definition uses `setup({ types, actors, actions, guards })`. State names,
events, contexts, effects, and child actor inputs are typed centrally.

The implementation is organized around deep modules:

```text
engine/
  machines/
    edition-machine.ts
    source-machine.ts
    article-machine.ts
    editorial-machine.ts
    translation-machine.ts
    art-machines.ts
    render-machine.ts
    release-machine.ts
  run-engine/
  task-composer/
  executors/
  renderer-adapter/
  view/
```

Storage layout, XState snapshots, and SQLite queries stay private to `run-engine`.
Prompt assembly and context-isolation rules stay private to `task-composer`.

---

## 8. Viewer and human work

The viewer consumes two projections from `RunEngine.inspect`:

- run-specific declared topology, including spawned actor instances;
- ordered domain events and current work offers.

It does not crawl run directories or treat raw XState snapshots as a log.

The view must show:

- the full edition hierarchy;
- one article actor expanded through its iterations and judging stages;
- pending, claimed, waiting, failed, superseded, and committed work;
- causal edges between artifacts and decisions;
- art variants at original resolution;
- manuscript and prompt diffs;
- why an iteration opened;
- which findings remain unresolved;
- which exact render a human is approving.

Human actions use a revision-safe interface:

```text
answer(offerId, expected active offer, choice, reviewer identity)
```

Stale and duplicate submissions are rejected visibly. If the web surface is exposed
beyond localhost, authentication and authorization are required. Private source and
manuscript artifacts are never served by an unauthenticated generic file route.

---

## 9. What is deliberately not carried forward

The rewrite does not port old behavior merely because it exists.

Specifically excluded:

- derive-state-from-disk scans;
- content fingerprints as workflow state;
- output presence as completion;
- `cp` and `rm` as rerun operations;
- generated round directories as the definition of current iteration;
- old `settled`, `bench`, `INCONSISTENT`, checkpoint, and score vocabularies;
- old cooperative reply-directory compatibility;
- old production record schemas;
- a blanket port of deterministic content validators;
- a dual Python and TypeScript authority period;
- differential parity with the old scheduler.

The new engine retains only rules that can be justified as one of:

- lifecycle state;
- provenance;
- source or role authority;
- durable execution correctness;
- explicit human decision;
- actual page measurement or render success;
- release integrity.

Output-contract parsing and artifact commit validation remain because malformed or
partial output is not a completed state. They are storage semantics, not editorial
scoring.

---

## 10. Implementation phases

### Phase 1: durable core and standalone ArticleMachine

Build:

- TypeScript workspace and pinned toolchain;
- `RunEngine` with SQLite, events, snapshots, offers, attempts, artifacts, and leases;
- executor interface with in-memory, subprocess, text-model, and human adapters;
- typed task composer;
- standalone `ArticleMachine` with staged judges, fit feedback, revision loop, human
  decision, and escalation;
- article inspect, continue, fork, and compare commands.

Prove:

- one article reaches a settled manuscript;
- a blocking stage prevents later judges from running;
- a revision carries findings and notes;
- a stale or duplicate answer cannot advance the machine;
- crash and restart at every commit point are safe;
- two processes cannot execute the same attempt;
- resume performs no full-file hash or filesystem state scan.

Once this vertical slice owns article production, delete the superseded Python article
orchestration and its implementation-coupled tests. Do not build a compatibility
adapter.

### Phase 2: ArticleLab and output optimization

Build:

- parallel article experiment runs;
- named configuration differences;
- manuscript, finding, cost, and latency comparison;
- human preference recording;
- promotion of a selected settled article artifact;
- a fixed evaluation corpus for repeated prompt and model experiments.

Use this phase to optimize the actual final prose before expanding orchestration.
Quality is judged by focused model roles and humans, not a new deterministic score.

### Phase 3: sources and EditionMachine content

Build:

- root `EditionMachine`;
- dynamic `SourceMachine` and `ArticleMachine` actors;
- collection-close and planning decisions;
- source capture and extraction adapters;
- article fan-out and join;
- `EditorialMachine`;
- edition review, named finding routing, dependent editorial revision, and human
  `editor_decision` states.

Delete the corresponding old source-to-production orchestration as each new path owns
it.

### Phase 4: images, translation, render, and release

Build:

- cover and interior-art actors;
- image-model executor and human selection offers;
- exact art registration by artifact ID;
- per-language translation actors and language fit;
- assembly join;
- versioned renderer subprocess interface;
- machine and independent visual review;
- release approval and atomic release state.

At the end of this phase, one `EditionMachine` run starts from leads and ends at a
released edition.

### Phase 5: viewer

Build the React Flow projection and human inbox over `RunEngine.inspect` and
`RunEngine.answer`. The engine must already work completely from the CLI; the view is
not allowed to become a second execution path.

---

## 11. Verification

Tests cross the `RunEngine` interface. Internal SQLite and XState details are not the
public test surface.

### 11.1 Statechart tests

- every declared state is reachable or intentionally terminal;
- article judge stages enter in order;
- optional lenses finish explicitly;
- edition review findings reach every named actor;
- article revision reopens dependent editorial and edition review work;
- render cannot run before every language and art dependency settles;
- escalation, drop, and human-decision states are non-accepting where required.

### 11.2 Durability tests

- crash before and after every transaction and artifact rename;
- duplicate `advance` from two processes;
- duplicate, stale, malformed, and late answers;
- worker timeout and process death;
- old worker completing after retry;
- interrupted parallel stage;
- outbox committed before dispatch;
- machine-version mismatch on resume;
- explicit state migration or successor-run behavior;
- orphan binary garbage collection without losing committed artifacts.

### 11.3 Provenance and authority tests

- lead to raw source to extraction to article lineage;
- writer receives all and only assigned source artifacts;
- source-blind roles cannot receive source artifacts;
- evidence and source-blind review cannot share a worker for one revision;
- every judgment references the manuscript revision it read;
- every human decision references the exact offered choices;
- every render references exact content, translation, and art artifacts;
- a new render cannot inherit an old visual approval.

### 11.4 Standalone and nested article equivalence

Given the same `ArticleRunSpec`, worker answers, and policy, `ArticleMachine` must make
the same transitions and produce the same artifact graph when:

- run as the root of an article-only run;
- run as a child actor of `EditionMachine`.

This is behavioral equivalence of the new machine in its two supported contexts. It
is not parity with the deleted Python orchestrator.

### 11.5 Layout and release tests

- isolated article measurement matches representative full-edition placement;
- every configured language joins before render;
- selected art artifacts are the ones in the rendered outputs;
- visual review binds the exact render artifact IDs;
- release is atomic and cannot assign one source to two released editions;
- resume and inspection perform no content-hash invalidation scan.

---

## 12. Remaining product decisions

These are policy inputs, not missing execution semantics:

1. Default article iteration budget and who may increase it.
2. Model concurrency and cost limits per run and across runs.
3. Which article experiment comparison is mandatory before promotion.
4. Human identities and permissions for collection close, editorial decisions, art
   selection, visual approval, and release.
5. Retention split between permanent audit artifacts and garbage-collectable large
   binaries.
6. Whether public publication is part of `ReleaseMachine` or a separate explicit
   `PublishMachine` after private release.

None of these changes the core architecture.

---

## 13. Superseded claims

The following claims from revision 5 are explicitly withdrawn:

- "A state is satisfied if its output is present."
- "The whole rerun interface is `cp` and `rm`."
- "Round number can be reconstructed by counting outputs."
- "Snapshots are the run log."
- "All lenses are one parallel state."
- "Art belongs inside each article actor."
- "Translations can be added cheaply after production render."
- "The first machine can omit editorial and edition judgment."
- "A prompt path and machine file SHA are sufficient provenance."
- "Waiting work can be sent directly to an actor that holds no process."
- "The old implementation should remain as a shadow or parity target."

The surviving idea is narrower and stronger: loops are state transitions, XState is a
good host for the hierarchy, and durable execution belongs in a separate deep module.

---

## 14. Research references

Supporting surveys and archived notes remain under [`meta/docs/`](../docs/), including
Argo, Restate, Temporal, Luigi, XState, graph viewers, and native TypeScript runtime
research.

Primary implementation references to pin when Phase 1 starts:

- XState state machines, actors, parallel states, persistence, inspection, and graph
  utilities;
- Node native TypeScript execution and test runner;
- the selected Node SQLite adapter and its transaction/WAL behavior;
- React Flow and ELK for the viewer;
- the existing renderer's callable layout and package interfaces, stripped of old
  orchestration assumptions.

This plan deliberately does not use workflow-engine product behavior as proof of its
durability model. The proof is the `RunEngine` interface and its failure-injection test
suite.
