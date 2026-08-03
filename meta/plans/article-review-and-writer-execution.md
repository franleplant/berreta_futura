# Article review cycle and closed writer execution

Status: **proposed**, not started. Revision 3, 2026-08-03.

Revision 3 adds the infrastructure seam for multiple article formats. It does not
define or ship any concrete magazine format profile. Article-specific editorial
design, prompts, reviewer panels, and policies remain later content work.

Revision 2 incorporates an independent adversarial review of the first draft.
It resolves artifact/materialization ownership, dynamic reviewer identity,
measurement, routing authority, result/output agreement, writer-claim
certification, CLI feasibility and startup preflight, access-class assignment,
external findings, iteration semantics, runtime graph authority, and context
growth.

This plan supersedes section 3 of
[`graph-execution-model.md`](graph-execution-model.md) in full; the
article-revision language in sections 2.5 and 3.5; the generic text-model
execution design in section 6 for writer and article-review roles; the article
viewer and graph requirements in section 8; and the corresponding article
phases and tests in sections 10 and 11. The rest of that plan remains in force.

The design goal is a simple editorial loop with strict execution and provenance:

```text
writer N
  -> independent review panel over manuscript N
  -> one structured revision brief
  -> deterministic routing
  -> writer N+1, human editor, or durable acceptance
```

Adding a reviewer changes immutable review-plan data and prompt artifacts. It
does not add top-level article states or transitions.

---

## 1. Decisions

### 1.1 Keep one understandable article lifecycle

`ArticleMachine` exposes lifecycle states, not individual reviewers:

```text
initializing
  -> drafting       when no manuscript exists
  -> reviewing      when an initial manuscript is supplied
drafting
  -> reviewing
  -> routing_review
       clean                 -> accepted_pending_durable
       changes_required      -> drafting
       human_required        -> awaiting_editor
       iteration_exhausted   -> escalated
  -> durable_bound
```

`dropped` and `failed` remain terminal. `accepted_pending_durable` remains a
real checkpoint state; acceptance is not settled until the immutable durable
revision is bound.

The names `stage_1`, `stage_1_decision`, `stage_2`, `stage_2_decision`, and
`stage_3` are removed from the top-level lifecycle. They describe an existing
optimization, not the editorial domain.

### 1.2 Implement review as a nested, data-driven cycle first

The first implementation keeps review as a nested compound state owned by
`ArticleMachine`. XState continues to own review lifecycle and joins.

```text
reviewing
  -> opening_wave
  -> awaiting_results
  -> evaluating_wave
       more waves -> opening_wave
       stop       -> compiling_brief
  -> compiling_brief
       deterministic work offer
  -> complete
```

A deep `ReviewCycle` module supplies plan validation, offer composition, result
recording, join predicates, early-exit policy, and outcome routing. Its
interface is small enough for `ArticleMachine` to use without understanding
individual reviewer kinds.

The machine is pure and does not read artifacts during a transition. Before the
initial snapshot is created, `RunEngine` reads and validates the pinned resolved
production-profile artifact and its pinned review-plan artifact, then places
normalized `ResolvedArticleProductionProfile` and `ResolvedReviewPlan` values in the
frozen actor input. Review completion events carry a compact validated result summary
plus the immutable result artifact ID. Full finding bodies remain in artifacts.

Brief compilation is an explicit deterministic `compile_revision_brief` work offer.
Its executor reads the exact review-result and ruling artifacts, returns one
validated brief artifact, and sends `REVISION_BRIEF_COMPILED` back to the nested
state. XState owns when that offer opens and joins; `RunEngine` owns the offer,
attempt, artifact, and answer. No machine action or caller queries artifact storage.

Do not introduce an `ArticleReviewMachine` actor in the first slice. Extract the
nested cycle into a child machine only when at least one of these is true:

- another lifecycle, such as editorial or translation, uses the same review
  lifecycle;
- review cycles require independent durable identity, inspection, or resumption;
- review has meaningful lifecycle beyond opening offers, joining results, and
  compiling an outcome;
- the nested implementation makes `ArticleMachine` materially harder to change
  or test.

More reviewers alone are not sufficient reason to add another actor.

### 1.3 Pin one immutable production profile per article

Different article formats share the same lifecycle and execution modules while
selecting different writer programs, reviewer panels, and policies. That variation
lives in one immutable article production-profile revision, not in machine states, executor
kinds, or role names.

The committed input document and the resolved runtime value are distinct contracts:

```ts
type ArticleProductionProfileDocument = {
  schemaVersion: "article-production-profile/1";
  profileId: string;
  formatId: string;
  writer: {
    promptRevision: PromptRevisionRef;
    resultContractVersion: "article-writer-result/1";
    reviewMaterials: readonly ReviewMaterialRevisionContract[];
  };
  reviewPlanRevision: ArticleReviewPlanRevisionRef;
  writingPolicyRevisions: readonly PolicyRevisionRef[];
  revisionPolicy: {
    maximumRewrites: number;
  };
};

type ReviewMaterialRevisionContract = {
  materialId: string;
  schemaRevision: ReviewMaterialSchemaRevisionRef;
  required: boolean;
};

type ResolvedArticleProductionProfile = {
  schemaVersion: "resolved-article-production-profile/1";
  profileId: string;
  formatId: string;
  profileArtifactId: ArtifactId;
  writerPromptArtifactId: ArtifactId;
  writerResultContractVersion: "article-writer-result/1";
  reviewMaterials: readonly {
    materialId: string;
    schemaArtifactId: ArtifactId;
    schemaVersion: string;
    required: boolean;
  }[];
  reviewPlanArtifactId: ArtifactId;
  writingPolicyArtifactIds: readonly ArtifactId[];
  maximumRewrites: number;
};
```

`formatId` is an opaque domain identity. The infrastructure does not enumerate
magazine formats and does not assign meaning to any concrete value. The committed
profile is a Git-bound immutable `article_production_profile` input revision. Its
references pin exact `prompt`, `article_review_plan`, `policy`, and
`review_material_schema` input revisions; it never contains run-scoped artifact
IDs.

The run builder resolves those Git-bound revisions, registers immutable engine
artifacts for their exact payloads, and creates the resolved profile artifact. The
resolved payload contains only the resulting engine artifact IDs and normalized
scalar policy. `RunEngine.start` independently validates that complete artifact
graph against the pinned input revisions before freezing it. `ArticleRunSpec` pins
the resolved profile artifact alongside piece-specific facts:

Input revision payloads are exact and versioned:

- `article_production_profile` contains `profile.json` only;
- `article_review_plan` contains `review-plan.json` only;
- `review_material_schema` contains `schema.json` only.

Their manifests and Git bindings follow the existing immutable input-revision
rules. Unknown files, floating logical IDs, unresolved revisions, duplicate material
IDs, and references to a different revision than the one materialized into the run
are startup errors.

```ts
type ArticleRunSpec = {
  articleId: string;
  productionProfileArtifactId: ArtifactId;
  articleBrief: ArtifactId;
  sources: readonly ArtifactId[];
  sourceApprovalArtifacts: readonly ArtifactId[];
  contentMode: ArticleContentMode;
  attribution: ArticleAttribution;
  editionContext?: ArtifactId;
  modelPolicy: ModelPolicy;
  initialManuscript?: ArtifactId;
  // durable and Git-bound provenance fields remain
};
```

The profile owns reusable production behavior. The run spec owns the exact article
assignment. Model choice remains run policy, and installed CLI configuration remains
operational configuration. Neither is smuggled into the editorial profile.

The approved production plan and committed write-pipeline document pin the exact
`article_production_profile` revision for each article. They do not repeat or
override its writer prompt, review plan, writing policies, review-material schemas,
or rewrite budget. Per-article exceptions require a new immutable profile revision;
there is no merge order for callers to learn and no partially overridden profile
that can escape validation.

Before the first article snapshot, `RunEngine` reads and validates the resolved
profile artifact, then reads its review plan and validates every referenced prompt,
policy, and schema artifact. It commits the normalized
`ResolvedArticleProductionProfile` into frozen machine input. The machine and task
composer receive only this resolved value and its immutable artifact identities;
they never discover a profile by name or directory, and `RunEngine` never reads Git
or reconstructs workflow state from input paths.

Profile validation proves:

- every referenced writer prompt, policy, review plan, and schema exists;
- the writer result contract is supported by the certified `WriterExecutor`;
- every declared review material has a unique identity and supported schema;
- every review-plan request for writer-produced material is declared by the writer;
- required review materials are consumed by at least one applicable review check;
- the review plan is valid under section 1.4;
- rewrite and measurement limits are finite and internally consistent;
- source-access rules remain valid after all profile inputs are expanded.

Changing any profile field or referenced revision creates a successor run. Two
articles may pin the same profile revision, and one article may pin a later profile
revision, without editing `ArticleMachine`, `WriterExecutor`, or reviewer execution.

Do not add `FeatureWriterExecutor`, format-specific work roles, or format-specific
article machines. Different prompts and model choices are writer programs executed
through the existing deep module. A separate executor or machine is justified only
if a future format genuinely requires a different execution policy or lifecycle
contract, not merely different prose instructions or reviewers.

### 1.4 Review checks are immutable plan data

An article profile pins one exact committed `ArticleReviewPlanDocument`. The run
builder resolves its input-revision references into one `ResolvedReviewPlan`
artifact. The plan names every model reviewer and deterministic measurement, its
prompt or profile, access class, authority, applicability rule, and optional wave.
Reviewer identity is separate from execution role: all model reviews use the stable
`article_review` role and `article-review/1` work contract; `reviewerId` identifies
the lens inside the offer. `measure_article` remains its existing renderer-backed
role and typed contract.

```ts
type ArticleReviewPlanDocument = {
  schemaVersion: "article-review-plan/1";
  checks: readonly ReviewCheckRevisionDefinition[];
  waves: readonly ReviewWave[];
};

type ResolvedReviewPlan = {
  schemaVersion: "resolved-article-review-plan/1";
  reviewPlanArtifactId: ArtifactId;
  checks: readonly ReviewCheckDefinition[];
  waves: readonly ReviewWave[];
};

type ModelReviewRevisionDefinition = Omit<
  ModelReviewDefinition,
  "promptArtifactId"
> & {
  promptRevision: PromptRevisionRef;
};

type ArticleMeasurementRevisionDefinition = Omit<
  ArticleMeasurementDefinition,
  "measurementProfileArtifactId"
> & {
  measurementProfileRevision: InputRevisionRef;
};

type ReviewCheckRevisionDefinition =
  | ModelReviewRevisionDefinition
  | ArticleMeasurementRevisionDefinition;

type ReviewCheckDefinition = ModelReviewDefinition | ArticleMeasurementDefinition;

type ModelReviewDefinition = {
  kind: "model_review";
  id: ReviewerId;
  role: "article_review";
  promptArtifactId: ArtifactId;
  access: "source_aware" | "source_blind";
  authority: "advisory" | "blocking" | "human_required";
  writerMaterialIds?: readonly string[];
  applicableWhen?: ReviewCondition;
};

type ArticleMeasurementDefinition = {
  kind: "article_measurement";
  id: "measure_article";
  role: "measure_article";
  measurementProfileArtifactId: ArtifactId;
  maximumReaderPages: number;
};

type ReviewWave = {
  id: ReviewWaveId;
  checkIds: readonly ReviewCheckId[];
  stopAfter: "never" | "blocking" | "human_required";
};
```

`ArticleRunSpec` references the production-profile artifact ID. The resolved profile
references exactly one review-plan artifact. During `start`, `RunEngine` resolves and
validates both and supplies their normalized values as internal
`ArticleMachineInput`. The IDs and normalized values are committed together in the
frozen actor input so replay and resume never require a caller to fetch or
reinterpret either input.

The plan is validated before the run starts:

- check and wave IDs are unique;
- every check belongs to exactly one wave;
- every named prompt exists;
- every requested writer material is declared by the production profile;
- every model check uses the stable `article_review` role and common result
  contract;
- access and authority agree with the approved review-policy schema and the task
  composer's input classification;
- applicability is explicit and deterministic;
- a source-backed article includes the required source-fidelity/evidence review;
- every article includes `measure_article`, including actual opener fit and the
  configured maximum reader-page policy;
- authority is declared by policy, not invented in a model answer;
- the wave order is finite and contains no dynamic backward edge.

Changing the review plan, reviewer prompt, access class, or authority creates a
new immutable input and therefore a successor run. It never mutates an active
review cycle.

### 1.5 One parallel panel is the default

All applicable reviewers inspect the same immutable manuscript independently.
The default plan has one parallel wave containing measurement and all applicable
model reviews. This reduces latency, prevents reviewers from anchoring on one
another, and gives the writer complete feedback in one revision.

Multiple waves are allowed only for a declared reason:

- a later review consumes an earlier result;
- a cheap deterministic preflight prevents materially wasteful expensive work;
- a blocking provenance, legal, or source-fidelity policy must stop later work.

Waves are plan data. No wave receives a dedicated XState state name. A stopped
wave records every unrun check as `skipped` with the exact stop reason.

### 1.6 One rewrite consumes the whole review cycle

The writer does not rewrite once per finding. One completed review cycle creates
one `RevisionBrief`; one writer offer creates one new immutable manuscript.

```text
review results for manuscript N
  -> deterministic revision brief N
  -> one writer offer
  -> manuscript N+1 + dispositions
  -> a completely fresh review cycle
```

This avoids edit thrashing, findings that refer to obsolete intermediate drafts,
and a revision count that grows with the number of reviewers.

Every review of manuscript N becomes stale when manuscript N+1 is created. No
review approval is inherited by a changed manuscript.

### 1.7 The writer is a closed, single-turn model role

The writer receives only the complete immutable work package through standard
input. It does not discover inputs from paths, inspect the repository, browse the
internet, invoke tools, run subagents, or continue an earlier model session.

The writer work package contains:

- the exact writer prompt;
- article brief, writing rules, content mode, attribution, editorial policy, and
  model policy artifacts;
- every assigned source extraction and source-approval artifact;
- optional edition context;
- on revision, the exact parent manuscript, prior working notes, and one lossless
  `RevisionBrief` containing every finding and applicable human ruling.

Original review artifacts remain immutable parents of the brief and therefore
transitive parents of the revised manuscript. Their full prose is not duplicated in
the model-visible prompt. The brief is the single lossless feedback representation
the writer reads.

The writer returns inline structured output containing manuscript text, working
notes, and finding dispositions. It never returns a repository path or a file
payload.

After composing the lossless package, `WriterExecutor` measures it against the
certified adapter profile's pinned input-context ceiling and reserved output
budget. If it does not fit, the offer is not dispatched: the machine receives a
typed permanent-capacity failure and opens the exact human editor offer. The
executor never truncates source text, drops findings, or inserts a model-generated
summary to make the package fit.

### 1.8 Keep Codex and Claude CLI adapters; remove writer ownership from `TextModelExecutor`

Codex CLI and Claude Code remain the initial ways to interact with hosted models.
The executor invokes each CLI non-interactively with its tool access disabled and
with no persisted conversation. A later Ollama adapter implements the same model
turn interface for local open models.

The current `TextModelExecutor` is immediately prohibited from claiming writer
offers. It is a poor writer abstraction: it identifies a large family of roles,
then delegates them to an arbitrary subprocess without expressing the role's input,
output, session, or tool policy.

It cannot yet be deleted because it also owns `extract_source`, `editorial_writer`,
`edition_review`, `translation_writer`, and `language_review`. Keep it as a clearly
deprecated legacy executor for those roles until each receives an explicit role
contract and executor. That migration is tracked as a later cleanup; reviewer and
writer migration alone must not claim to remove it.

Replace it with two layers:

```ts
interface ModelCliAdapter {
  invoke(request: ModelTurnRequest, signal: AbortSignal): Promise<ModelTurnResult>;
}

type ModelTurnRequest = {
  model: string;
  reasoningEffort?: string;
  prompt: string;
  outputSchema: JsonObject;
  toolAccess: "none";
  session: "ephemeral";
};
```

Initial adapters:

- `CodexCliAdapter`;
- `ClaudeCliAdapter`;
- `OllamaAdapter` later, without changing writer contracts or machine state.

The role-level `WriterExecutor` is the only executor allowed to claim certified
`writer` offers. It validates the offer, builds the closed prompt from immutable
artifact text, invokes a certified `ModelCliAdapter`, validates the structured
reply, and returns the exact writer artifacts.

Reviewer execution may later use the same adapter seam through a separate
`ReviewerExecutor`. It does not share the writer's output contract merely because
both roles call a language model.

### 1.9 Tool denial is an enforced adapter contract

Tool-free execution is not represented only by a self-asserted worker capability.
Writer offers require an engine-enforced execution class such as
`closed_writer/1`. At worker startup, configured adapters register a trusted
execution profile and principal with `RunEngine` and receive an opaque claim
credential. `RunEngine.claim` verifies the offer's required execution class,
registered principal, and opaque credential. A caller cannot satisfy this check by
presenting `text_model` and `source_access` strings.

The credential is process-local authority, is never written to an artifact or log,
and can be revoked when the configured worker stops. Cooperative bridges do not
receive it.

Each CLI adapter owns a pinned, tested invocation profile.

For the currently installed CLI families, the implementation must use the
supported non-interactive, ephemeral, tool-denial, no-browser, no-MCP, and
structured-output options. Exact flags are adapter implementation details because
they change between CLI versions.

Before writer implementation, a Phase 0 feasibility spike records and tests the
pinned CLI versions. At plan-writing time the local versions are:

- Codex CLI `0.146.0`;
- Claude Code `2.1.220`.

Claude exposes an explicit empty tool set through `--tools ""` and supports
non-persistent, structured print mode. The adapter may use bare mode only when its
configured authentication supports it; otherwise it must use an equally closed
safe-mode profile that retains the selected authentication mechanism. Codex exposes
non-interactive ephemeral execution, feature/config overrides, sandbox policy, JSON
events, and an output schema, but its help does not establish an empty-tool mode.
The feasibility spike must prove genuine zero-tool invocation against the pinned
version. If a pinned CLI cannot provide one, that adapter is unavailable and worker
startup fails before polling; read-only shell access and post-hoc tool-call rejection
are not accepted as equivalent to preventing tools.

Both adapters:

- receive the complete prompt on standard input;
- run from an adapter-owned scratch directory, never the repository root;
- load no project instructions, plugins, skills, MCP servers, browser integration,
  or prior session;
- pass no source or output filesystem paths to the model;
- accept only standard-output text/JSON matching the writer schema;
- inspect structured CLI events where available and reject any tool call;
- record adapter name, adapter version, model, settings, timing, and usage metadata;
- fail permanently when their installed version does not match a supported
  invocation profile.

The subprocess runner gains an explicit environment policy. Model adapters replace
ambient environment inheritance with a per-adapter allowlist containing only the
runtime, locale, temporary-directory, authentication, and provider settings required
by the selected CLI. Hooks, plugin paths, project configuration, unrelated secrets,
and ambient proxy variables are excluded unless the certified profile explicitly
requires and tests them.

Configured-worker startup performs asynchronous adapter preflight before the polling
loop begins. It probes and validates executable identity, version, supported
zero-tool profile, output-schema behavior, and scratch setup, then registers the
trusted execution profile with `RunEngine`. Version discovery during `execute()` is
too late because the offer has already been claimed.

Network used internally by Codex or Claude to reach its model provider is allowed.
The model receives no web-search or browser tool. The later Ollama adapter talks
only to the configured local Ollama endpoint.

---

## 2. Review result and feedback contracts

### 2.1 One normalized result envelope

Every reviewer produces one immutable result artifact against one exact manuscript
artifact:

```ts
type ReviewResult = {
  schemaVersion: "article-review-result/1";
  reviewerId: ReviewerId;
  manuscriptArtifactId: ArtifactId;
  assessment: "pass" | "findings" | "human_required" | "not_applicable";
  findings: readonly LocalFinding[];
};

type LocalFinding = {
  localId: string;
  severity: "must_fix" | "consider";
  scope: ManuscriptScope;
  problem: string;
  requestedOutcome: string;
  evidenceArtifactIds: readonly ArtifactId[];
};

type ArticleMeasurementResult = {
  schemaVersion: "article-measurement/1";
  manuscriptArtifactId: ArtifactId;
  fits: boolean;
  openerFits: boolean;
  pageCount: number;
};

type FindingRef = {
  reviewResultArtifactId: ArtifactId;
  localId: string;
};
```

The active offer and review plan determine whether an assessment is advisory,
blocking, or allowed to require a human. A model cannot gain authority by returning
the word `blocking` or `drop`. V1 has no model-originated drop transition; an
authorized reviewer may request human judgment, and the human offer may then drop.
Malformed, duplicated, stale, or wrong-manuscript results do not advance the join.

Measurement uses its own subprocess result contract. A fit failure, opener failure,
or page count above the pinned limit deterministically becomes a must-fix blocking
outcome in the same compiled review cycle.

Finding references are namespaced by the committed review-result artifact ID and a
result-local ID. Bare model-provided IDs are never global identity. Local IDs must be
unique within one result. Evidence references must be a subset of the artifacts the
review offer was allowed to read; source-blind results cannot cite source artifacts.
Scope is structured enough to help the writer locate the issue but does not become a
mutable path or line-number authority.

The reviewer executor returns exactly one JSON review-result artifact whose payload
deep-equals the validated `answer.result`. `RunEngine` derives the compact machine
event summary from that validated value. Result JSON and artifact payload cannot
disagree.

### 2.2 Deterministic revision-brief compilation

`ReviewCycle` compiles results into one immutable brief without another model call:

```ts
type RevisionBrief = {
  schemaVersion: "article-revision-brief/1";
  articleId: string;
  iterationId: IterationId;
  manuscriptArtifactId: ArtifactId;
  mustFix: readonly BriefFinding[];
  consider: readonly BriefFinding[];
  humanRulings: readonly ArtifactId[];
  reviewResultArtifactIds: readonly ArtifactId[];
  measurementArtifactId: ArtifactId;
};
```

Compilation:

- retains every finding and its producing result artifact;
- orders findings by declared reviewer order, severity, and scope;
- groups only exact shared identifiers or exact normalized locations;
- never semantically deduplicates or rewrites a reviewer's finding;
- applies an existing human ruling only when it names the exact finding and input
  artifacts;
- never infers semantic conflict from prose, shared scope, or requested outcomes.

Automatic conflict detection is outside v1 because the finding schema does not
contain a deterministic compatibility relation. A later schema may add plan-defined
constraint keys and mutually exclusive outcome enums. Until then, only an authorized
`human_required` assessment or an explicit external human ruling opens conflict
adjudication.

The original review artifacts remain direct or transitive parents of the brief and
the next manuscript. The brief is an ergonomic view, not a replacement for evidence.

### 2.3 Writer result and dispositions

The writer returns one structured envelope:

```ts
type WriterResult = {
  schemaVersion: "article-writer-result/1";
  manuscript: string;
  workingNotes: string;
  dispositions: readonly FindingDisposition[];
  reviewMaterials: readonly WriterReviewMaterial[];
};

type WriterReviewMaterial = {
  materialId: string;
  schemaVersion: string;
  value: JsonValue;
};

type FindingDisposition = {
  finding: FindingRef;
  status: "addressed" | "declined" | "superseded";
  explanation: string;
};
```

For an initial draft, `dispositions` is empty. For a revision, the result must name
every finding reference in the active `RevisionBrief` exactly once. Unknown,
missing, or duplicated references reject the answer.

Review materials are typed, profile-declared writer outputs intended for named
review checks. The writer must return every required material exactly once and may
return only materials declared by the active production profile. Each value is
validated against its pinned schema. Initial infrastructure tests use synthetic
materials only; no concrete magazine-format material contract is introduced here.

A disposition is accountability, not authority. `declined` does not erase the
finding or make the manuscript acceptable. The next fresh review determines whether
the concern remains. Human rulings remain separate immutable decision artifacts.

`WriterExecutor` parses one model result and constructs the complete `WorkAnswer`.
The work-result contract requires exact agreement between the parsed writer envelope
and every emitted artifact payload; `answer.result` contains only routing metadata
and cannot provide a second conflicting manuscript body.

The accepted answer creates exactly three core artifacts:

- an `article_manuscript` text artifact;
- a `writer_working_notes` text artifact;
- a `writer_finding_dispositions` JSON artifact, empty on an initial draft.

It additionally creates one immutable `writer_review_material` JSON artifact for
each returned review material. Each carries the material ID and schema version and
names the production-profile artifact as a parent. The task composer supplies it
only to checks whose `writerMaterialIds` request it. Working notes remain writer-only
revision context and are never used as an untyped reviewer-input channel.

All are produced by the same writer offer and name their complete immutable input
lineage.

### 2.4 Deterministic review routing

`routing_review` is not a model or editorial role. It uses this exact table:

| Check kind or authority | Valid result | Effective routing effect |
| --- | --- | --- |
| article measurement | fit, opener, and page limit pass | none |
| article measurement | any pinned limit fails | must-fix |
| advisory model review | pass or consider findings | record only; never blocks acceptance |
| advisory model review | must-fix or human request | reject as out of contract |
| blocking model review | pass | none |
| blocking model review | one or more must-fix findings | changes required |
| blocking model review | consider findings only | record only |
| human-required model review | pass or findings | apply declared severities |
| human-required model review | human required | human editor |

Routing order is then:

1. any authorized human-required outcome or policy exception -> human editor;
2. no effective must-fix findings -> durable checkpoint;
3. effective must-fix findings and remaining rewrite budget -> one new writer offer;
4. effective must-fix findings with exhausted rewrite budget -> budget decision.

Advisory considerations remain in the review record but do not force endless
rewrites as the panel grows.

Only an explicit human decision can accept an exception, increase the budget, or
drop an article when policy requires human authority.

---

## 3. Machine and context redesign

### 3.1 Article context

Replace the fixed `ArticleChecks` record and hardcoded stage slots with review-cycle
state:

```ts
type ArticleMachineContext = {
  // existing actor, spec, iteration, manuscript, durable, and history fields
  productionProfileArtifactId: ArtifactId;
  resolvedProductionProfile: ResolvedArticleProductionProfile;
  reviewPlanArtifactId: ArtifactId;
  resolvedReviewPlan: ResolvedReviewPlan;
  review: ReviewCycleState;
  writerReviewMaterialArtifacts: Readonly<Record<string, ArtifactId>>;
  activeRevisionBriefArtifactId?: ArtifactId;
  carriedRulingArtifacts: readonly ArtifactId[];
};

type ReviewCycleState = {
  manuscriptArtifactId: ArtifactId;
  waveIndex: number;
  results: Readonly<Record<ReviewCheckId, ReviewResultSummary>>;
};
```

The context stores the normalized frozen profile and plan, immutable artifact
identities, and compact result summaries needed by synchronous guards. Large policy,
material, and finding bodies stay in artifacts rather than being copied into every
snapshot. The deterministic brief executor reads those artifacts only through its
exact work offer.

### 3.2 Events and offers

Use check identity rather than a closed union of lens slots:

```ts
type ArticleMachineEvent =
  | { type: "START" }
  | { type: "WRITER_COMPLETED"; offerId: WorkOfferId; artifacts: WriterArtifacts }
  | { type: "REVIEW_COMPLETED"; checkId: ReviewCheckId; offerId: WorkOfferId; artifactId: ArtifactId; summary: ReviewResultSummary }
  | { type: "REVISION_BRIEF_COMPILED"; offerId: WorkOfferId; artifactId: ArtifactId; outcome: ReviewOutcomeSummary }
  | { type: "WORK_FAILED"; offerId: WorkOfferId; classification: FailureClass; message: string }
  | { type: "REVISION_REQUESTED"; findingArtifacts: readonly ArtifactId[]; rulingArtifacts?: readonly ArtifactId[]; reason: string }
  | { type: "EDITOR_DECISION_REQUIRED"; findingArtifacts: readonly ArtifactId[]; reason: string }
  | { type: "MIGRATION_DURABLE_BACKFILL" };
```

Exact event names may follow existing `WORK_COMPLETED` conventions, but the internal
machine event produced by `RunEngine.answer` must always carry the active offer,
check identity, committed result artifact, and normalized summary. Arbitrary callers
do not construct that trusted summary, and nobody infers the reviewer from state
names.

One offer remains one role, one actor, and one article. Each review offer names the
exact manuscript, production-profile, and review-plan artifacts. Model reviewer
offers use role `article_review` and put `reviewerId` in the slot and task artifact.
Measurement keeps role `measure_article`. Source-aware and source-blind input
composition, including selective writer-review-material access, remains in
`task-composer`, not in the machine.

Brief compilation uses the stable deterministic role `compile_revision_brief` and a
versioned work-result contract. Only the in-process deterministic executor registered
for that role may claim it; no model worker or cooperative bridge can compile the
authoritative brief.

### 3.3 Iteration semantics

The configured budget counts writer rewrites after the first available manuscript,
not reviewer findings, reviewer attempts, waves, or the initial manuscript itself.
Iteration ordinal 1 names either the first generated draft or a supplied seed
manuscript. A transition from manuscript N to N+1 consumes one rewrite from the
budget.

- All review offers for manuscript N share its `IterationId` and `RevisionId`.
- Writer review materials share the manuscript's revision identity and become stale
  whenever that manuscript changes.
- Retrying a failed reviewer creates a new attempt, not a new manuscript iteration.
- One `changes_required` outcome can create at most one writer offer for N+1.
- The writer receives the complete active brief, not findings piecemeal.
- An externally routed edition finding joins the next brief and opens one new
  iteration when budget remains.
- A human budget increase changes `effectiveMaxIterations` through the exact active
  decision offer.

`initializing` preserves a direct path to `reviewing` when `initialManuscript` exists.
When no manuscript exists, it opens `drafting`. A zero rewrite budget still permits a
seeded manuscript to be reviewed and accepted; it prevents an automatic rewrite.
When no manuscript exists and policy permits no initial draft, initialization
escalates through the explicit human offer rather than inventing text.

Edition-level feedback uses a normalized `ExternalRevisionFinding` artifact contract
that names the originating edition-review artifact, target article, current
manuscript, severity, requested outcome, and any human ruling. From `durable_bound`,
`REVISION_REQUESTED` opens the same deterministic brief-compilation offer over these
external findings, then routes to one writer offer or budget decision. External
prose findings never bypass normalization or reach the writer as an untyped blob.

### 3.4 Machine versioning

The redesigned machine receives a new article-machine version. No persisted snapshot
silently resumes under the new topology.

- New runs use the new version, production-profile document/resolution contracts,
  and article-review-plan document/resolution contracts.
- Existing sealed or released work remains immutable.
- Existing durable manuscripts may seed a new run through `initialManuscript` and an
  explicit durable parent revision.
- Existing active runs either finish under their pinned old machine bundle or create
  an explicit successor run. State is never inferred from old stage names or files.

---

## 4. Execution modules

### 4.1 WriterExecutor

`WriterExecutor` is a deep module. Its external interface is the existing executor
interface used by the worker loop. Its implementation owns:

- accepting only `writer` offers with the closed execution policy;
- requiring the exact frozen production-profile artifact and resolved profile;
- reading every declared input artifact through `ArtifactReader`;
- rejecting undeclared, duplicated, missing, or incorrectly classified inputs;
- composing one model-visible prompt with stable labeled sections;
- selecting the configured Codex, Claude, or later Ollama adapter;
- enforcing ephemeral, tool-free invocation;
- validating `WriterResult`;
- validating profile-declared review materials and emitting them as typed artifacts;
- producing inline immutable answer artifacts and complete parent lineage;
- recording model and adapter metadata without credentials or session data.

`WriterExecutor` never exposes CLI flags, scratch layout, response parsing, or model
vendor output to `ArticleMachine` or `RunEngine`.

### 4.2 CLI adapter responsibilities

Each `ModelCliAdapter` owns:

- exact executable and argument construction for one pinned CLI family;
- input on standard input and output on standard output;
- model and reasoning configuration;
- tool, browser, plugin, MCP, project-instruction, and session suppression;
- adapter-owned scratch lifecycle;
- timeout, cancellation, and process-group termination;
- structured response/event parsing;
- detection and rejection of tool activity;
- normalized usage and diagnostic metadata;
- version probing and fail-closed compatibility checks.

The generic subprocess runner may remain as an internal dependency for process
lifecycle. It is not itself a model-role executor and cannot claim writer work.

### 4.3 Configuration

Replace generic text-model registrations with explicit role and adapter
configuration:

```ts
type WriterExecutorConfiguration = {
  kind: "writer_model";
  id: string;
  executionClass: "closed_writer/1";
  principalId: string;
  adapter: "codex_cli" | "claude_cli" | "ollama";
  model: string;
  reasoningEffort?: string;
  executable: string;
  timeoutMs: number;
  supportedAdapterVersion: string;
};
```

Model selection still comes from the immutable article model policy. Operational
configuration selects an installed adapter capable of satisfying it. Configured
worker startup preflights the adapter, registers the principal and execution class
with `RunEngine`, and obtains the opaque claim credential before polling. A mismatch
fails before claiming the offer.

No configuration option may enable writer tools. Tool-enabled roles require a
different executor kind and are outside this writer contract.

### 4.4 Cooperative model bridge

The cooperative bridge may remain for deliberate human-mediated experiments, but it
is not a production writer executor and cannot prove closed execution. It has no
`closed_writer/1` registration or opaque credential, so `RunEngine.claim` rejects it
for production writer offers even if it presents `text_model` and `source_access`.

If cooperative writer answers remain supported, their metadata must label them as
cooperative and tool policy `unverified`; they are not eligible for unattended
production or comparison against certified tool-free runs without an explicit human
ruling.

### 4.5 Review executor assignment and exposure

Model review uses one stable work role but still preserves exposure isolation.
Configured workers register separate principals for source-aware and source-blind
article-review execution. The resolver selects a registration whose certified access
class matches the exact check definition and whose principal has no conflicting
exposure for the manuscript subject.

Worker startup validates that the frozen review plan has eligible configured
execution for every access class before polling the run. A single principal cannot
claim both classes for one manuscript revision. Parallel review tests must exercise
mixed-access plans with distinct principals.

---

## 5. Graphs and inspection

The static graph and runtime review plan answer different questions and remain
separate outputs.

### 5.1 Static topology

The official graph exporter continues to project the live XState config. The default
article graph shows the compact top-level lifecycle. An expanded mode shows nested
`reviewing` states, guards, internal transitions, and entry actions.

```sh
npm run graph:export -- output/article-machine --machine article
npm run graph:export -- output/article-machine-expanded --machine article --expand
```

Adding a reviewer does not change this topology.

### 5.2 Runtime review-plan graph

Inspection can additionally project the exact frozen `ResolvedReviewPlan` for a run:

```text
manuscript revision
  -> wave
       -> reviewer offers
  -> join
  -> review outcome
  -> revision brief
```

The projection names reviewer IDs, roles, access classes, authority, prompt artifact
IDs, offer status, result artifact IDs, skips, and retries. Its header names the exact
production-profile artifact, profile ID, opaque format ID, and review-plan artifact.
It is generated from the resolved profile, plan, and `RunEngine.inspect`, never from
directory discovery or a manually maintained diagram. Format identity is diagnostic
metadata, not a source of graph topology.

The viewer defaults to the compact article lifecycle and links to this expanded
runtime review view. A growing reviewer list therefore increases only the review-plan
view, not the primary statechart.

Static export and runtime projection have separate interfaces:

```text
exportMachineTopology({ machine: "article", nested: "collapsed" | "expanded" })
projectArticleReview(runEngine.inspect(runId), actorId, iterationId)
```

The CLI surface for the runtime projection is:

```sh
npm run engine -- graph-review <run-id> <article-actor-id> <iteration-id> <destination>
```

It writes `article-review-plan.json`, `article-review-plan.svg`,
`article-review-plan.png`, and `article-review-plan.html` using a versioned diagnostic
schema. The command reads state only through public `RunEngine.inspect`; the
projection is never workflow authority.

---

## 6. Implementation sequence

Each phase is a coherent checkpoint. Tests cross the public `RunEngine` interface
except narrowly labeled schema or adapter-conformance tests.

### Phase 0: prove closed CLI execution and claim authority

Before machine changes, build spikes and deterministic fakes that prove:

- the pinned Claude profile exposes an empty tool set without loading project or
  user customizations;
- the pinned Codex profile can genuinely expose an empty tool set, not merely a
  read-only shell;
- unsupported profiles stop configured-worker startup before polling or claiming;
- `RunEngine.claim` enforces an engine-issued `closed_writer/1` registration and
  rejects capability spoofing by the cooperative bridge;
- the subprocess runner can replace ambient environment inheritance with an explicit
  adapter allowlist.

If Codex cannot satisfy zero-tool execution at the pinned version, mark
`CodexCliAdapter` unavailable and proceed with a certified Claude adapter. Do not
weaken the writer contract. Revisit Codex when a supported version passes the same
conformance suite.

### Phase 1: characterize and introduce review contracts

Build:

- `ArticleProductionProfileDocument`, `ResolvedArticleProductionProfile`, the new
  Git-bound input revision kinds, run-builder materialization, and RunEngine profile
  validation;
- `ReviewerId`, `FindingRef`, `ArticleReviewPlanDocument`, `ResolvedReviewPlan`,
  `ReviewResult`,
  `ArticleMeasurementResult`, `ExternalRevisionFinding`, `RevisionBrief`,
  `WriterResult`, `WriterReviewMaterial`, and disposition schemas;
- immutable production-profile artifact input on `ArticleRunSpec`;
- RunEngine materialization of validated `ResolvedArticleProductionProfile` and its
  `ResolvedReviewPlan` into frozen actor input;
- one stable `article_review` role and contract, with reviewer identity in plan/slot;
- validation for check identity, wave membership, prompts, measurement, access,
  authority, required source review, and writer-material dependencies;
- characterization tests for current writer inputs, review provenance, iteration
  budget, human decisions, and durable checkpoint behavior.

Use two synthetic profile fixtures with deliberately different writer prompts,
reviewer sets, policies, and optional writer-review-material contracts. They prove
the infrastructure variation without defining a real magazine format.

Add one public-`RunEngine` tracer test that creates a temporary input repository,
commits both synthetic profile graphs, builds two article run specs, starts both runs,
and drives them through writer, review, brief, rewrite, and durable checkpoint. The
test asserts only public offers, artifacts, events, decisions, and inspection output;
it never queries SQLite or calls machine internals.

Replace direct writer/reviewer production fields in `ApprovedProductionPlan`,
`WritePipelineArticle`, and `ArticleRunSpec` with the appropriate committed profile
revision or resolved profile artifact reference. Keep piece identity, sources,
brief, content/provenance mode, attribution, edition context, model policy, durable
parent, and initial manuscript on the article assignment. Delete direct
`writerPrompt`, `judgePrompts`, enabled/blocking lens lists, writing-policy lists, and
rewrite-budget overrides after the profile path is covered by public-interface
tests.

Keep the old staged machine only long enough to establish the replacement tests. Do
not add a permanent compatibility interface around stage names.

### Phase 2: replace hardcoded stages with nested ReviewCycle

Build:

- the nested `reviewing` compound state;
- data-driven offer creation for the current wave;
- result recording keyed by `ReviewCheckId` with trusted compact summaries;
- XState-owned joins and explicit skipped results;
- deterministic wave stop and completion;
- explicit `compile_revision_brief` work and join;
- `routing_review` with exact ordered guards;
- a new article-machine version.

Delete:

- `ArticleChecks` as a fixed record;
- `ArticleSlot` reviewer unions;
- `stageSlots`, `stageCompleteAfter`, `stageComplete`, and stage-specific guards;
- top-level `stage_1`, `stage_1_decision`, `stage_2`, `stage_2_decision`, and
  `stage_3` states;
- tests whose only purpose is to preserve those implementation names.

### Phase 3: compile feedback and close the writer loop

Build:

- deterministic `RevisionBrief` compilation;
- explicit human-required routing without semantic conflict inference;
- external edition-finding normalization and brief compilation;
- writer input composition containing one lossless brief without duplicated review
  prose;
- `WriterResult` validation and inline artifact creation;
- profile-declared writer review-material validation, artifact creation, and
  selective reviewer delivery;
- exact agreement between validated model result and emitted artifact payloads;
- exact finding disposition coverage;
- one-rewrite-per-review-cycle transition;
- fresh full review of every changed manuscript.

Delete raw, unstructured result-string conventions once every reviewer emits the new
contract. No unlabeled generic summary replaces a reviewer finding.

### Phase 4: certified tool-free CLI writer execution

Build:

- `ModelCliAdapter`;
- `CodexCliAdapter` for the pinned Codex CLI;
- `ClaudeCliAdapter` for the pinned Claude Code CLI;
- `WriterExecutor`;
- adapter-owned scratch and version probes;
- structured-output schemas and tool-activity rejection;
- explicit `writer_model` worker configuration and resolver ownership.

Then remove `writer` from `TextModelExecutor` immediately. Keep a deprecated legacy
executor for `extract_source`, `editorial_writer`, `edition_review`,
`translation_writer`, and `language_review` until separate plans migrate those
roles. Do not delete the generic executor merely because article writer and reviewer
roles have moved.

### Phase 5: graphs, viewer, and cleanup

Build:

- collapsed and expanded nested-state support in the official topology exporter;
- runtime review-plan JSON/SVG projection;
- review-cycle inspection showing offers, results, findings, brief, dispositions, and
  routing reason;
- documentation for review plans and supported CLI adapter versions.

Delete stale staged-review documentation and update the older graph execution plan to
point to this superseding plan.

### Phase 6: Ollama adapter

Add `OllamaAdapter` behind the same `ModelCliAdapter` interface. It consumes the exact
same `ModelTurnRequest` and returns the exact same `ModelTurnResult`. No article state,
writer offer, review plan, or writer-result contract changes.

---

## 7. Verification

### 7.1 Review-plan and lifecycle tests

- two synthetic production profiles run through the same article-machine version;
- each synthetic profile produces its own exact writer prompt, review checks,
  measurement policy, and rewrite budget;
- changing only the profile artifact creates a successor run;
- unknown, missing, malformed, or incompatible profile references prevent run start;
- profile resolution never depends on `formatId`, paths, or a hardcoded registry;
- adding a reviewer changes only plan data and offered review work;
- every applicable reviewer receives the exact manuscript revision;
- every article measurement uses the exact manuscript, measurement profile, opener
  behavior, and page-limit policy;
- all reviewers in a wave are offered independently;
- a wave joins only after every applicable reviewer has a terminal result;
- optional reviewers record `not_applicable` or an explicit skip reason;
- retrying one reviewer does not reopen completed reviewer offers;
- a declared stop policy prevents later waves and records their skips;
- one actionable outcome creates exactly one new writer offer;
- reviewer count does not change the manuscript iteration count;
- exhausted iteration budget creates the exact human budget offer;
- a new manuscript makes every old review result non-current;
- stale, duplicate, wrong-reviewer, and wrong-manuscript answers cannot advance;
- result artifact payloads and trusted event summaries cannot disagree;
- advisory considerations never force a rewrite;
- blocking must-fix findings follow the exact routing table;
- initial manuscripts enter review without consuming a rewrite;
- zero rewrite budget permits acceptance but not an automatic rewrite;
- normalized external edition findings produce one brief and one rewrite offer;
- durable acceptance still requires the exact checkpoint artifact.

### 7.2 Feedback and writer tests

- the revision brief retains every original finding and artifact ID;
- deterministic compilation produces byte-stable ordering for the same inputs;
- semantic findings are never silently deduplicated;
- the revision writer receives prompt, policies, sources, parent manuscript, notes,
  and the lossless brief in declared order;
- original review artifacts remain provenance parents without duplicating their text
  in the model-visible prompt;
- the model-visible input contains artifact text and IDs but no repository paths;
- an initial draft returns no dispositions;
- a revision must disposition every active finding exactly once;
- unknown, missing, and duplicate dispositions reject the answer;
- one writer answer creates one manuscript revision regardless of finding count;
- declined findings remain visible to the next review;
- a writer output cannot be a file payload or repository path.
- source text is framed as untrusted evidence and cannot change the execution policy
  or output contract;
- every required profile-declared review material is emitted exactly once;
- undeclared, duplicate, missing, and schema-invalid review materials reject the
  writer answer;
- each review check receives only its declared writer materials, while working notes
  remain private to the next writer revision;
- writer review materials become stale with their manuscript revision;
- an oversized lossless work package escalates before writer dispatch and is never
  truncated or silently summarized.

### 7.3 CLI adapter conformance tests

Use fake executables for deterministic routine tests. They capture arguments,
standard input, working directory, and emitted output without calling hosted models.

- Codex and Claude invocations are non-interactive and ephemeral;
- the pinned profile disables tools, browser, MCP, plugins, project instructions, and
  session persistence;
- prompt and artifact text arrive only on standard input;
- execution starts outside the repository in adapter-owned scratch;
- structured output is required and validated;
- any tool-call event permanently rejects the answer;
- unsupported CLI versions or profiles prevent worker startup before polling;
- RunEngine rejects an unregistered or spoofed `closed_writer/1` claimant;
- the environment contains only the certified per-adapter allowlist;
- timeout and cancellation terminate the full process group;
- stderr and malformed output cannot become manuscript artifacts;
- credentials, authorization data, session IDs, and CLI home data never enter
  artifacts or logs;
- adapter metadata records the executable family and version without secrets.

Gated local smoke tests may invoke installed Codex and Claude versions with a trivial
closed prompt. They are not part of routine deterministic verification and never use
Edition 4 sources or images.

### 7.4 Access and provenance tests

- writers receive every assigned source and no unassigned source;
- source-blind reviewers cannot receive source artifacts;
- source-aware and source-blind reviewer identities remain isolated as policy
  requires;
- mixed-access parallel review uses separately registered principals;
- review results name the exact offer, reviewer, manuscript, prompt, and plan;
- writer, review, brief, and manuscript artifacts retain the exact production-profile
  artifact in their provenance;
- the revision brief names all producing review artifacts;
- the revised manuscript names its parent manuscript, brief, findings, rulings, and
  writer policy inputs;
- human rulings bind the exact active review-policy or budget offer;
- no cookie, credential, authorization header, browser profile, or model session is
  persisted.

### 7.5 Graph tests

- the compact graph contains `drafting`, `reviewing`, `routing_review`, checkpoint,
  settled, human, drop, and failure paths;
- the expanded graph is generated from the live nested XState config;
- the runtime review-plan graph contains every configured reviewer exactly once;
- static export reads live nested config while runtime export reads only public
  `RunEngine.inspect` state for an explicit run, actor, and iteration;
- graph edges correspond to declared waves, offers, joins, and outcomes;
- adding reviewers does not add top-level article states;
- SVG, PNG, HTML, and JSON exports remain deterministic and readable.

Run the pinned Node verification after each checkpoint:

```sh
npm run typecheck
npm run test:engine
npm run build:viewer
```

Routine verification does not invoke Python, UV, hosted models, or Ollama.

---

## 8. Expected file changes

The exact filenames may change during implementation, but ownership should remain
local to these modules:

```text
engine/
  contracts/
    article-production-profile.ts # reusable writer/review production profile
    article-review.ts           # review plan, result, brief, writer schemas
    run.ts                      # production-profile artifact input
    run-spec.ts                 # frozen profile and plan validation
  machines/
    article-machine.ts          # compact lifecycle and nested reviewing state
    review-cycle.ts             # deep review-cycle implementation
  task-composer/
    article.ts                  # profile-driven immutable input composition
    review.ts                   # reviewer access and prompt composition
  executors/
    writer.ts                   # WriterExecutor
    reviewer.ts                 # later explicit reviewer execution
    revision-brief.ts           # deterministic feedback compiler
    model-cli/
      types.ts                  # ModelCliAdapter interface
      codex.ts                  # pinned Codex CLI profile
      claude.ts                 # pinned Claude CLI profile
      ollama.ts                 # later local adapter
    subprocess.ts               # internal process lifecycle only
    configured-worker.ts        # startup preflight and explicit registration
  run-engine/
    article-profile.ts          # profile resolution and compatibility validation
    execution-profiles.ts       # trusted profile registration and claim credentials
    work-result-contracts.ts    # exact writer and review answer validation
  durable/
    types.ts                    # new profile, review-plan, and schema revision refs
    input-revision.ts           # exact payload validation for those input kinds
    write-pipeline.ts           # article assignments pin profile revisions
  write-production.ts           # materialize resolved profile artifact graphs
  view/
    ...                         # compact lifecycle and runtime review-plan views
  graph-export.ts               # nested and runtime-plan projections
  test/
    article-review-*.test.ts
    writer-executor.test.ts
    model-cli-adapters.test.ts
```

Do not create Python workflow code or tests. Do not move task composition, joins,
authority, validation, or workflow state into CLI adapters.

---

## 9. Acceptance criteria

The redesign is complete when:

1. The top-level article graph expresses `drafting -> reviewing -> routing_review`
   without reviewer-specific states.
2. Every article pins one immutable production-profile artifact, which resolves to
   its exact writer program, policies, review plan, and rewrite policy.
3. Two synthetic profiles can select different writer prompts, reviewer panels, and
   typed review materials while using the same article machine and executors.
4. A frozen plan can add or remove reviewers without editing `ArticleMachine`.
5. XState durably joins every applicable reviewer for one exact manuscript.
6. All feedback becomes one provenance-preserving `RevisionBrief`.
7. One writer offer consumes the complete brief and creates one new manuscript.
8. Every revision finding has exactly one writer disposition.
9. Every changed manuscript and its writer review materials receive a completely
   fresh review cycle.
10. Production writer offers can be claimed only through an engine-registered
   `closed_writer/1` profile owned by `WriterExecutor`.
11. Every enabled Codex or Claude writer adapter is ephemeral, tool-free, path-free,
   structured-output-only, and startup-preflighted under a pinned profile. An
   adapter that cannot satisfy this is unavailable rather than weakened.
12. No writer output enters through a file path.
13. Ollama can be added later without changing article or writer contracts.
14. Compact and expanded graphs are generated from live machine and review-plan
    authority.
15. All public `RunEngine` tests and pinned Node verification pass.

---

## 10. Explicit non-goals

- No model-generated semantic deduplication of reviewer findings.
- No writer rewrite per finding.
- No persistent Codex or Claude conversation between iterations.
- No filesystem or internet exploration by the writer.
- No direct hosted-model implementation that bypasses the selected CLI adapters.
- No reviewer name encoded as a top-level article state.
- No concrete magazine-format profile, format prompt, or format reviewer panel in
  this infrastructure change.
- No committed `inputs/` profile instances in this checkpoint; conformance uses
  synthetic temporary-repository fixtures.
- No format-name switch statement or registry in `ArticleMachine`, `WriterExecutor`,
  task composition, or profile resolution.
- No format-specific writer/reviewer work role, executor, or article machine merely
  because prompts and checks differ.
- No separate review actor until the extraction criteria in section 1.2 are met.
- No reuse of a review approval across manuscript artifact IDs.
- No compatibility restoration for the deleted Python workflow.
- No change to the rule that `RunEngine` and XState are the only execution
  authorities.

---

## 11. Remaining decisions before implementation

These choices do not change the architecture but must be pinned in their relevant
implementation checkpoints. Real magazine production-profile contents are explicitly
deferred until after the infrastructure checkpoint.

1. Whether the writer output schema permits an empty `workingNotes` string.
2. The manuscript-scope representation used by findings: heading identity, structural
   block identity, or another immutable anchor.
3. Which approved review policies may request human judgment. Model-originated drop
   is excluded from v1.
4. The per-adapter input-context ceiling and reserved output budget. Once the exact
   lossless package exists, exceeding that ceiling escalates before writer dispatch;
   truncating or silently summarizing findings is forbidden.
5. Whether certified tool-free execution should become mandatory for reviewer roles
   in the same checkpoint or immediately afterward.
