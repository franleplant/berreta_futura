import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  createDurableWorkflowPin,
  createRuntime,
  SQLiteDurableRunStore,
  type WorkflowGlobals,
} from "@loops/core";

import type { ArticleInputBinding } from "../contracts/workflow-run.ts";
import type { ArtifactId, ArticleExecutionId, JsonValue, ManuscriptRevisionId, RunId } from "../contracts/index.ts";
import {
  articleRevisionContextParents,
  articleRevisionRecordParents,
  type ArticleRevisionContext,
  type ArticleRevisionRecord,
} from "../article-production/revision.ts";
import {
  deterministicManuscriptRevisionId,
  revisionRecordId,
} from "../workflows/article-workflow.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import type { ArticleMaterialSet } from "../article-production/materials.ts";
import { CLOSED_WRITER_RUNTIME_IDENTITY } from "../executors/closed-writer/runtime.ts";

const id = (value: string) => value as ArtifactId;
const runId = "revision-package-run" as RunId;
const articleExecutionId = "revision-package-execution" as ArticleExecutionId;

test("rewrite revision identities distinguish A-B-A while replaying byte-stably", () => {
  const bindings: readonly ArticleInputBinding[] = [{
    artifactId: id("source"),
    revision: { kind: "source_extraction", logicalId: "source", revisionId: "source-v1" as never },
  }];
  const first = deterministicManuscriptRevisionId("article", bindings, "same text", [id("source")], {
    articleExecutionId,
    previousRevisionId: "revision-a" as ManuscriptRevisionId,
    cycleId: "cycle-a",
    rewriteOrdinal: 1,
    selectedWriterClaimId: "claim-a",
    selectedWriterOutputArtifactId: id("writer-a"),
  });
  const second = deterministicManuscriptRevisionId("article", bindings, "same text", [id("source")], {
    articleExecutionId,
    previousRevisionId: first,
    cycleId: "cycle-b",
    rewriteOrdinal: 2,
    selectedWriterClaimId: "claim-b",
    selectedWriterOutputArtifactId: id("writer-b"),
  });
  const third = deterministicManuscriptRevisionId("article", bindings, "same text", [id("source")], {
    articleExecutionId,
    previousRevisionId: second,
    cycleId: "cycle-c",
    rewriteOrdinal: 3,
    selectedWriterClaimId: "claim-c",
    selectedWriterOutputArtifactId: id("writer-c"),
  });
  assert.notEqual(first, second);
  assert.notEqual(second, third);
  assert.notEqual(first, third);
  assert.equal(second, deterministicManuscriptRevisionId("article", bindings, "same text", [id("source")], {
    articleExecutionId,
    previousRevisionId: first,
    cycleId: "cycle-b",
    rewriteOrdinal: 2,
    selectedWriterClaimId: "claim-b",
    selectedWriterOutputArtifactId: id("writer-b"),
  }));
});

async function selectWriterAttempt(input: {
  readonly root: string;
  readonly ledger: ArtifactLedger;
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly operationKey: string;
  readonly parentArtifactId: ArtifactId;
  readonly materialId: string;
  readonly materialSchemaVersion: string;
}) {
  const suffix = input.operationKey.replace(/[^A-Za-z0-9_.-]/gu, "_");
  const authority = await LocalAuthorityStore.init(join(input.root, `authority-${suffix}`));
  await authority.enrollWorker({ principalId: `writer-${suffix}`, authority: "model", capabilities: ["text_model", "source_access"] });
  const credential = await authority.createCredentialProfile({ principalId: `writer-${suffix}`, credentialProfileId: `writer-profile-${suffix}` });
  await authority.grant({ credentialProfileId: credential.credentialProfileId, grantId: `writer-grant-${suffix}`, capabilities: ["text_model", "source_access"] });
  const worker = await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });
  const store = new SQLiteDurableRunStore(join(input.root, `writer-loops-${suffix}.sqlite`));
  const pin = createDurableWorkflowPin({
    source: { entryPath: "engine/test/article-revision-package.test.ts", graphHash: `sha256:${suffix}-graph` },
    dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:writer-lock" },
    execution: { backend: "article-revision-writer" },
  });
  const backend = {
    name: "article-revision-writer",
    capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
    async run(): Promise<never> { throw new Error("agent calls are not part of this test"); },
  };
  const runner = input.ledger.createArticleAttemptRunner();
  const writerInputArtifactIds = [input.manuscriptArtifactId, input.parentArtifactId] as const;
  const writerContractMetadata = {
    writerExecutionClass: "closed_writer/1",
    writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY,
    writerInputArtifactIds,
    revisionContextArtifactId: input.parentArtifactId,
  } as const;
  const materials: ArticleMaterialSet = {
    schemaVersion: "article-material-set/1",
    articleId: input.articleId,
    role: "writer",
    access: "source_aware",
    manuscriptArtifactId: input.manuscriptArtifactId,
    artifacts: [
      { artifactId: input.manuscriptArtifactId, articleId: input.articleId, classification: "manuscript" },
      { artifactId: input.parentArtifactId, articleId: input.articleId, classification: "revision_context" },
    ],
    artifactIds: [input.manuscriptArtifactId, input.parentArtifactId],
  };
  try {
    const runtime = createRuntime({
      backend,
      defaultBackend: backend.name,
      durable: { store, runId: input.runId, workflowName: "article-revision-writer", workflowPin: pin },
    });
    return await runtime.run(async (globals) => await globals.step(
      input.operationKey,
      () => runner.executeModel(worker, {
        rootRunId: input.runId,
        articleExecutionId: input.articleExecutionId,
        articleId: input.articleId,
        operationKey: input.operationKey,
        manuscriptArtifactId: input.manuscriptArtifactId,
        access: "source_aware",
        materials,
      }, async () => ({
        value: { schemaVersion: "article-writer-result/1", manuscript: "rewritten", workingNotes: "notes", dispositions: [], reviewMaterials: [{ materialId: input.materialId, schemaVersion: input.materialSchemaVersion, value: { ok: true } }] },
        artifacts: [
          { key: "manuscript", kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "model" as const, payload: { kind: "text" as const, text: "rewritten" }, parents: writerInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" })), metadata: { articleId: input.articleId, revisionId: "writer-revision", ...writerContractMetadata } },
          { key: "working-notes", kind: "writer_working_notes", schemaVersion: "writer-working-notes/1", mediaType: "text/plain", origin: "model" as const, payload: { kind: "text" as const, text: "notes" }, parents: writerInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" })), metadata: { articleId: input.articleId, ...writerContractMetadata } },
          { key: "finding-dispositions", kind: "writer_finding_dispositions", schemaVersion: "writer-finding-dispositions/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { schemaVersion: "writer-finding-dispositions/1", dispositions: [] } }, parents: writerInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" })), metadata: { articleId: input.articleId, ...writerContractMetadata } },
          { key: `review-material:${input.materialId}`, kind: "writer_review_material", schemaVersion: "writer-review-material/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { materialId: input.materialId, schemaVersion: input.materialSchemaVersion, value: { ok: true } } }, parents: writerInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" })), metadata: { articleId: input.articleId, materialId: input.materialId, materialSchemaVersion: input.materialSchemaVersion, ...writerContractMetadata } },
        ],
      })),
      { input: { operationKey: input.operationKey }, retry: { maxAttempts: 1, retryOn: "never" } },
    ));
  } finally {
    store.close();
  }
}

test("current revision package pointer validates exact records and replays idempotently", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-revision-package-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  try {
    const seed = id("revision-seed");
    ledger.createArtifact({
      id: seed,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "seed" },
      metadata: { articleId: "article", revisionId: "revision-seed" },
    });
    ledger.createRun({ runId, articleExecutionId, articleId: "article", workflowVersion: "test/1", loopsRunId: runId, manuscriptArtifactId: seed, args: {} });
    const initial: ArticleRevisionRecord = {
      schemaVersion: "article-revision-record/1",
      ordinal: 0,
      manuscriptArtifactId: seed,
      manuscriptRevisionId: "revision-seed" as ManuscriptRevisionId,
      reviewMaterialArtifactIds: [],
      humanRulingArtifactIds: [],
      trigger: "initial",
    };
    const initialId = revisionRecordId(initial.manuscriptRevisionId);
    ledger.createArtifact({
      id: initialId,
      kind: "article_revision_record",
      schemaVersion: "article-revision-record/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: initial as unknown as JsonValue },
      parents: articleRevisionRecordParents(initial),
      metadata: { articleId: "article", manuscriptArtifactId: seed, manuscriptRevisionId: initial.manuscriptRevisionId },
      runId,
    });
    ledger.recordCurrentRevisionRecord(runId, initialId);
    assert.equal(ledger.recordCurrentRevisionRecord(runId, initialId).currentRevisionRecordArtifactId, initialId);
    assert.equal(ledger.requireCurrentRevisionRecord(runId).id, initialId);

    const next = id("revision-next-manuscript");
    ledger.createArtifact({
      id: next,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "model",
      payload: { kind: "text", text: "next" },
      parents: [{ artifactId: seed, relation: "previous_manuscript" }],
      metadata: { articleId: "article", revisionId: "revision-next" },
      runId,
    });
    const successor: ArticleRevisionRecord = {
      schemaVersion: "article-revision-record/1",
      ordinal: 1,
      manuscriptArtifactId: next,
      manuscriptRevisionId: "revision-next" as ManuscriptRevisionId,
      previousRevisionRecordArtifactId: initialId,
      reviewMaterialArtifactIds: [],
      humanRulingArtifactIds: [],
      trigger: "auto_rewrite",
    };
    const successorId = revisionRecordId(successor.manuscriptRevisionId);
    ledger.createArtifact({
      id: successorId,
      kind: "article_revision_record",
      schemaVersion: "article-revision-record/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: successor as unknown as JsonValue },
      parents: articleRevisionRecordParents(successor),
      metadata: { articleId: "article", manuscriptArtifactId: next, manuscriptRevisionId: successor.manuscriptRevisionId },
      runId,
    });
    ledger.recordCurrentRevisionRecord(runId, successorId, initialId);
    assert.equal(ledger.requireRun(runId).manuscriptArtifactId, next);
    assert.throws(() => ledger.recordCurrentRevisionRecord(runId, initialId, initialId), /current package record|current package predecessor|exact next package/);
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("revision context and record parent order stays canonical", () => {
  const context: ArticleRevisionContext = {
    schemaVersion: "article-revision-context/1",
    articleExecutionId,
    cycleId: "cycle",
    rewriteOrdinal: 1,
    trigger: "editor_revise",
    previousManuscriptArtifactId: id("previous-manuscript"),
    revisionBriefArtifactId: id("brief"),
    routeArtifactId: id("route"),
    priorWorkingNotesArtifactId: id("notes"),
    priorFindingDispositionsArtifactId: id("dispositions"),
    priorReviewMaterialArtifactIds: [id("material-a"), id("material-b")],
    humanRulingArtifactIds: [id("ruling-a")],
    editorDecisionArtifactId: id("decision"),
  };
  assert.deepEqual(articleRevisionContextParents(context), [
    { artifactId: id("previous-manuscript"), relation: "revision_previous_manuscript" },
    { artifactId: id("brief"), relation: "revision_brief" },
    { artifactId: id("route"), relation: "review_route" },
    { artifactId: id("notes"), relation: "prior_working_notes" },
    { artifactId: id("dispositions"), relation: "prior_finding_dispositions" },
    { artifactId: id("material-a"), relation: "prior_review_material" },
    { artifactId: id("material-b"), relation: "prior_review_material" },
    { artifactId: id("ruling-a"), relation: "human_ruling" },
    { artifactId: id("decision"), relation: "editor_decision" },
  ]);
});

test("atomic writer finalization adopts the exact successor and rejects a stale predecessor", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-revision-finalize-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  try {
    const seed = id("finalize-seed");
    ledger.createArtifact({
      id: seed,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "seed" },
      metadata: { articleId: "article", revisionId: "seed-revision" },
    });
    ledger.createRun({ runId, articleExecutionId, articleId: "article", workflowVersion: "test/1", loopsRunId: runId, manuscriptArtifactId: seed, args: {} });
    const initial: ArticleRevisionRecord = { schemaVersion: "article-revision-record/1", ordinal: 0, manuscriptArtifactId: seed, manuscriptRevisionId: "seed-revision" as ManuscriptRevisionId, reviewMaterialArtifactIds: [], humanRulingArtifactIds: [], trigger: "initial" };
    const initialId = revisionRecordId(initial.manuscriptRevisionId);
    ledger.createArtifact({ id: initialId, kind: "article_revision_record", schemaVersion: "article-revision-record/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: initial as unknown as JsonValue }, parents: articleRevisionRecordParents(initial), metadata: { articleId: "article", manuscriptArtifactId: seed, manuscriptRevisionId: initial.manuscriptRevisionId }, runId });
    ledger.recordCurrentRevisionRecord(runId, initialId);

    const brief = id("finalize-brief");
    const route = id("finalize-route");
    for (const artifactId of [brief, route]) ledger.createArtifact({ id: artifactId, kind: artifactId === brief ? "article_revision_brief" : "article_review_route", schemaVersion: artifactId === brief ? "article-revision-brief/1" : "article-review-route/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: {} }, runId });
    const contextId = id("finalize-context");
    const context: ArticleRevisionContext = { schemaVersion: "article-revision-context/1", articleExecutionId, cycleId: "cycle-finalize", rewriteOrdinal: 1, trigger: "auto_rewrite", previousManuscriptArtifactId: seed, revisionBriefArtifactId: brief, routeArtifactId: route, priorReviewMaterialArtifactIds: [], humanRulingArtifactIds: [] };
    ledger.createArtifact({ id: contextId, kind: "article_revision_context", schemaVersion: "article-revision-context/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: context as unknown as JsonValue }, parents: articleRevisionContextParents(context), metadata: { articleId: "article", articleExecutionId, cycleId: context.cycleId, rewriteOrdinal: 1 }, runId });
    const operationKey = "article.writer.cycle-finalize";
    const execution = await selectWriterAttempt({ root, ledger, runId, articleExecutionId, articleId: "article", manuscriptArtifactId: seed, operationKey, parentArtifactId: contextId, materialId: "claims", materialSchemaVersion: "claims/1" });
    assert.equal(execution.selected, true);
    const writer = execution.artifacts[0]!.id;
    const notes = execution.artifacts[1]!.id;
    const dispositions = execution.artifacts[2]!.id;
    const material = execution.artifacts[3]!.id;
    const operationInputDigest = execution.claim?.operationInputDigest ?? execution.artifacts[0]!.metadata.operationInputDigest as string;
    const selectedWriterClaimId = execution.claim?.claimId ?? execution.artifacts[0]!.metadata.claimId as string;
    const revisionId = deterministicManuscriptRevisionId("article", [], "rewritten", [], { articleExecutionId, previousRevisionId: initial.manuscriptRevisionId, cycleId: context.cycleId, rewriteOrdinal: 1, selectedWriterClaimId, selectedWriterOutputArtifactId: writer });
    const input = { runId, articleExecutionId, articleId: "article", operationKey, operationInputDigest, previousManuscriptArtifactId: seed, previousRevisionRecordArtifactId: initialId, targetOrdinal: 1, cycleId: context.cycleId, rewriteOrdinal: 1, trigger: "auto_rewrite" as const, revisionContextArtifactId: contextId, writerArtifactIds: [writer, notes, dispositions, material], manuscriptRevisionId: revisionId, manuscriptArtifactId: id(`art-manuscript-${revisionId}`), revisionRecordArtifactId: id(`art-revision-record-${revisionId}`), humanRulingArtifactIds: [], writerExecutionClass: "closed_writer/1" as const, writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY, expectedWriterInputArtifactIds: [seed, contextId], declaredWriterReviewMaterials: [{ materialId: "claims", schemaVersion: "claims/1", required: false }] };
    const first = ledger.finalizeArticleRevision(input);
    assert.equal(first.ordinal, 1);
    assert.equal(first.writerReviewMaterialArtifacts.claims, material);
    assert.throws(
      () => ledger.finalizeArticleRevision({ ...input, writerExecutionClass: "open_writer/1" as never }),
      /closed-writer|runtime contract|outputs/u,
    );
    assert.throws(
      () => ledger.finalizeArticleRevision({ ...input, expectedWriterInputArtifactIds: [seed] }),
      /exact closed-writer input package|outputs/u,
    );
    const adopted = ledger.finalizeArticleRevision(input);
    assert.equal(adopted.adopted, true);
    assert.equal(ledger.requireRun(runId).currentRevisionRecordArtifactId, input.revisionRecordArtifactId);
    assert.throws(() => ledger.finalizeArticleRevision({ ...input, previousRevisionRecordArtifactId: id("wrong-predecessor") }), /current package|revision record|predecessor/u);
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("a Loops SQLite restart adopts a committed revision after the step checkpoint is lost", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-revision-restart-"));
  const ledgerPath = join(root, "magazine.sqlite");
  const loopsPath = join(root, "loops.sqlite");
  let ledger = new ArtifactLedger(ledgerPath);
  let loops: SQLiteDurableRunStore | undefined;
  try {
    const restartRunId = "revision-restart-run" as RunId;
    const restartExecutionId = "revision-restart-execution" as ArticleExecutionId;
    const seed = id("restart-seed");
    ledger.createArtifact({
      id: seed,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "seed" },
      metadata: { articleId: "article", revisionId: "seed-revision" },
    });
    ledger.createRun({
      runId: restartRunId,
      articleExecutionId: restartExecutionId,
      articleId: "article",
      workflowVersion: "test/1",
      loopsRunId: restartRunId,
      manuscriptArtifactId: seed,
      args: { articleId: "article" },
    });
    const initial: ArticleRevisionRecord = {
      schemaVersion: "article-revision-record/1",
      ordinal: 0,
      manuscriptArtifactId: seed,
      manuscriptRevisionId: "seed-revision" as ManuscriptRevisionId,
      reviewMaterialArtifactIds: [],
      humanRulingArtifactIds: [],
      trigger: "initial",
    };
    const initialId = revisionRecordId(initial.manuscriptRevisionId);
    ledger.createArtifact({
      id: initialId,
      kind: "article_revision_record",
      schemaVersion: "article-revision-record/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: initial as unknown as JsonValue },
      parents: articleRevisionRecordParents(initial),
      metadata: { articleId: "article", manuscriptArtifactId: seed, manuscriptRevisionId: initial.manuscriptRevisionId },
      runId: restartRunId,
    });
    ledger.recordCurrentRevisionRecord(restartRunId, initialId);

    const brief = id("restart-brief");
    const route = id("restart-route");
    ledger.createArtifact({
      id: brief,
      kind: "article_revision_brief",
      schemaVersion: "article-revision-brief/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: {} },
      runId: restartRunId,
    });
    ledger.createArtifact({
      id: route,
      kind: "article_review_route",
      schemaVersion: "article-review-route/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: {} },
      runId: restartRunId,
    });
    const cycleId = "restart-cycle";
    const contextId = id("restart-context");
    const revisionContext: ArticleRevisionContext = {
      schemaVersion: "article-revision-context/1",
      articleExecutionId: restartExecutionId,
      cycleId,
      rewriteOrdinal: 1,
      trigger: "auto_rewrite",
      previousManuscriptArtifactId: seed,
      revisionBriefArtifactId: brief,
      routeArtifactId: route,
      priorReviewMaterialArtifactIds: [],
      humanRulingArtifactIds: [],
    };
    ledger.createArtifact({
      id: contextId,
      kind: "article_revision_context",
      schemaVersion: "article-revision-context/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: revisionContext as unknown as JsonValue },
      parents: articleRevisionContextParents(revisionContext),
      metadata: { articleId: "article", articleExecutionId: restartExecutionId, cycleId, rewriteOrdinal: 1 },
      runId: restartRunId,
    });
    const operationKey = "article.writer.restart-cycle";
    const execution = await selectWriterAttempt({ root, ledger, runId: restartRunId, articleExecutionId: restartExecutionId, articleId: "article", manuscriptArtifactId: seed, operationKey, parentArtifactId: contextId, materialId: "claims", materialSchemaVersion: "claims/1" });
    assert.equal(execution.selected, true);
    const writer = execution.artifacts[0]!.id;
    const notes = execution.artifacts[1]!.id;
    const dispositions = execution.artifacts[2]!.id;
    const material = execution.artifacts[3]!.id;
    const operationInputDigest = execution.claim?.operationInputDigest ?? execution.artifacts[0]!.metadata.operationInputDigest as string;
    const selectedWriterClaimId = execution.claim?.claimId ?? execution.artifacts[0]!.metadata.claimId as string;
    const revisionId = deterministicManuscriptRevisionId("article", [], "rewritten", [], {
      articleExecutionId: restartExecutionId,
      previousRevisionId: initial.manuscriptRevisionId,
      cycleId,
      rewriteOrdinal: 1,
      selectedWriterClaimId,
      selectedWriterOutputArtifactId: writer,
    });
    const finalizerInput = {
      runId: restartRunId,
      articleExecutionId: restartExecutionId,
      articleId: "article",
      operationKey,
      operationInputDigest,
      previousManuscriptArtifactId: seed,
      previousRevisionRecordArtifactId: initialId,
      targetOrdinal: 1,
      cycleId,
      rewriteOrdinal: 1,
      trigger: "auto_rewrite" as const,
      revisionContextArtifactId: contextId,
      writerArtifactIds: [writer, notes, dispositions, material],
      manuscriptRevisionId: revisionId,
      manuscriptArtifactId: id(`art-manuscript-${revisionId}`),
      revisionRecordArtifactId: id(`art-revision-record-${revisionId}`),
      humanRulingArtifactIds: [],
      writerExecutionClass: "closed_writer/1" as const,
      writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY,
      expectedWriterInputArtifactIds: [seed, contextId],
      declaredWriterReviewMaterials: [{ materialId: "claims", schemaVersion: "claims/1", required: false }],
    };

    const pin = createDurableWorkflowPin({
      source: { entryPath: "engine/test/article-revision-package.test.ts", graphHash: "sha256:restart-graph" },
      dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:restart-lock" },
      execution: { backend: "restart-test" },
    });
    const backend = {
      name: "restart-test",
      capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
      async run(): Promise<never> { throw new Error("agent calls are not part of this test"); },
    };
    const workflow = async (globals: WorkflowGlobals) => {
      const checkpoint = await globals.step("article.checkpoint-A", () => ({
        schemaVersion: "article-loop-checkpoint/1",
        runId: restartRunId,
        articleExecutionId: restartExecutionId,
        articleId: "article",
        phase: "rewriting",
        ordinal: 0,
        rewriteOrdinal: 0,
        maximumRewrites: 1,
        manuscriptArtifactId: seed,
        manuscriptRevisionId: initial.manuscriptRevisionId,
        revisionRecordArtifactId: initialId,
      }), { input: { runId: restartRunId, ordinal: 0 } });
      const finalized = await globals.step("article.revision-finalize.restart-cycle", () => ledger.finalizeArticleRevision({
        ...finalizerInput,
        ...(globals.durableContext?.() === undefined ? {} : { durableContext: globals.durableContext!() as never }),
      }), { input: finalizerInput, retry: { maxAttempts: 1, retryOn: "never" } });
      return { checkpoint, finalized, budgetSpent: globals.budget.spent() };
    };

    loops = new SQLiteDurableRunStore(loopsPath);
    const runtime1 = createRuntime({
      backend,
      defaultBackend: "restart-test",
      budget: { total: 10, unit: "tokens" },
      durable: { store: loops, runId: restartRunId, workflowName: "article-restart-test", workflowPin: pin, leaseMs: 1_000 },
    });
    const originalFinalize = ledger.finalizeArticleRevision.bind(ledger);
    let injectedCommitCrash = true;
    ledger.finalizeArticleRevision = ((input) => {
      const result = originalFinalize(input);
      if (injectedCommitCrash) {
        injectedCommitCrash = false;
        throw new Error("simulated process crash after finalizer commit");
      }
      return result;
    }) as typeof ledger.finalizeArticleRevision;
    const originalCompleteAttempt = loops.completeAttempt.bind(loops);
    let lostAttemptCheckpoint = false;
    loops.completeAttempt = ((completion) => {
      if (!lostAttemptCheckpoint && completion.failure !== undefined) {
        lostAttemptCheckpoint = true;
        throw new Error("simulated process crash before step checkpoint");
      }
      return originalCompleteAttempt(completion);
    }) as typeof loops.completeAttempt;
    const originalCompleteInvocation = loops.completeInvocation.bind(loops);
    let lostInvocationCheckpoint = false;
    loops.completeInvocation = ((invocationId, completion) => {
      if (!lostInvocationCheckpoint && completion.failure !== undefined) {
        lostInvocationCheckpoint = true;
        throw new Error("simulated process crash before invocation checkpoint");
      }
      return originalCompleteInvocation(invocationId, completion);
    }) as typeof loops.completeInvocation;
    await assert.rejects(runtime1.run(workflow), /simulated process crash before invocation checkpoint/u);
    const interrupted = loops.inspectRun(restartRunId);
    assert.equal(interrupted?.run.status, "running");
    assert.equal(interrupted?.calls.filter((call) => call.key === "article.checkpoint-A").length, 1);
    assert.equal(interrupted?.calls.filter((call) => call.key === "article.revision-finalize.restart-cycle").length, 1);
    loops.close();
    loops = undefined;
    ledger.close();
    ledger = new ArtifactLedger(ledgerPath);
    await new Promise((resolve) => setTimeout(resolve, 1_050));

    const resumedLoops = new SQLiteDurableRunStore(loopsPath);
    loops = resumedLoops;
    const runtime2 = createRuntime({
      backend,
      defaultBackend: "restart-test",
      budget: { total: 10, unit: "tokens" },
      durable: { store: resumedLoops, runId: restartRunId, workflowName: "article-restart-test", workflowPin: pin, leaseMs: 1_000 },
    });
    const resumed = await runtime2.run(workflow);
    assert.equal(resumed.finalized.ordinal, 1);
    assert.equal(resumed.budgetSpent, 0);
    assert.equal(resumed.checkpoint.ordinal, 0);
    assert.equal(ledger.requireRun(restartRunId).currentRevisionRecordArtifactId, finalizerInput.revisionRecordArtifactId);
    assert.equal(ledger.requireRun(restartRunId).manuscriptArtifactId, finalizerInput.manuscriptArtifactId);
    const revisionArtifacts = ledger.listArtifacts(restartRunId).filter((artifact) => artifact.kind === "article_revision_record");
    assert.equal(revisionArtifacts.length, 2);
    assert.equal(revisionArtifacts.some((artifact) => artifact.id === initialId), true);
    assert.equal(revisionArtifacts.some((artifact) => artifact.id === finalizerInput.revisionRecordArtifactId), true);
    const successor = ledger.requireArtifact(finalizerInput.revisionRecordArtifactId);
    assert.deepEqual(successor.parents, [
      { artifactId: finalizerInput.manuscriptArtifactId, relation: "revision_manuscript" },
      { artifactId: contextId, relation: "revision_context" },
      { artifactId: notes, relation: "revision_working_notes" },
      { artifactId: dispositions, relation: "revision_finding_dispositions" },
      { artifactId: material, relation: "revision_review_material" },
      { artifactId: initialId, relation: "previous_revision_record" },
    ]);
    assert.equal(successor.parents.some((parent) => parent.artifactId === successor.id), false);
    const inspection = resumedLoops.inspectRun(restartRunId)!;
    const finalizeCall = inspection.calls.find((call) => call.key === "article.revision-finalize.restart-cycle");
    assert.ok(finalizeCall);
    assert.deepEqual(resumedLoops.listAttempts(finalizeCall!.callId).map((attempt) => attempt.status), ["expired", "completed"]);
  } finally {
    loops?.close();
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});
