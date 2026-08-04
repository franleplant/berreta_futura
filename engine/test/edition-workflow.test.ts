import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import test from "node:test";
import Database from "better-sqlite3";
import { canonicalizeDurableValue, hashDurableValue, SQLiteDurableRunStore } from "@loops/core";

import type { ArtifactId, JsonObject, JsonValue, ManuscriptRevisionId, RevisionId } from "../contracts/index.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import { materializeNativeInputRevision } from "../durable/native-input-revision.ts";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import type { ArticleAttemptExecutionResult, ArticleRuntimeStartArgs, ArticleWorkflowPorts, WorkflowWaitContext } from "../workflows/internal-types.ts";
import type { RendererIdentity } from "../workflows/renderer-identity.ts";
import { EditionWorkflowEngine } from "../workflows/edition-workflow-engine.ts";
import type { EditionWorkflowArgs } from "../workflows/edition-workflow.ts";
import { resolveAuthenticatedWritePipelineInputs } from "../durable/write-pipeline.ts";
import { createArticleWorkflowPorts } from "../workflows/article-runtime.ts";
import { articleRevisionRecordParents, type ArticleRevisionRecord } from "../article-production/revision.ts";
import type { RenderManifest, RendererAdapter } from "../renderer-adapter/protocol.ts";

const execFile = promisify(execFileCallback);
const PROJECT_ROOT = resolve(process.cwd());
const REVISION = "rev_20260804T000000000Z_aaaaaaaaaaaa" as RevisionId;

test("legacy ledgers migrate the Loops root identity from unique to one-to-many", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-ledger-migration-"));
  const databasePath = join(root, "legacy.sqlite");
  const legacy = new Database(databasePath);
  legacy.exec(`
    CREATE TABLE magazine_runs (
      run_id TEXT PRIMARY KEY,
      article_execution_id TEXT,
      article_id TEXT NOT NULL,
      edition_id TEXT,
      workflow_version TEXT NOT NULL,
      loops_run_id TEXT NOT NULL UNIQUE,
      manuscript_artifact_id TEXT NOT NULL,
      current_revision_record_artifact_id TEXT,
      measurement_artifact_id TEXT,
      decision_artifact_id TEXT,
      promotion_id TEXT UNIQUE,
      args_digest TEXT NOT NULL,
      args_json TEXT NOT NULL,
      workflow_pin_json TEXT,
      loops_context_json TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE magazine_artifacts (
      id TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      schema_version TEXT NOT NULL,
      media_type TEXT NOT NULL,
      origin TEXT NOT NULL,
      payload_kind TEXT NOT NULL,
      payload BLOB NOT NULL,
      metadata_json TEXT NOT NULL,
      durable_context_json TEXT,
      run_id TEXT,
      created_at TEXT NOT NULL,
      digest TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES magazine_runs(run_id)
    );
    CREATE TABLE magazine_article_exposures (
      principal_id TEXT NOT NULL,
      manuscript_revision_id TEXT NOT NULL,
      manuscript_artifact_id TEXT NOT NULL,
      access TEXT NOT NULL,
      first_claim_id TEXT NOT NULL,
      exposed_at TEXT NOT NULL,
      PRIMARY KEY (principal_id, manuscript_revision_id)
    );
    CREATE TABLE magazine_manuscript_revisions (
      revision_id TEXT PRIMARY KEY,
      manuscript_artifact_id TEXT NOT NULL UNIQUE,
      article_id TEXT NOT NULL,
      registered_at TEXT NOT NULL
    );
  `);
  legacy.prepare(`INSERT INTO magazine_runs(
    run_id, article_execution_id, article_id, edition_id, workflow_version,
    loops_run_id, manuscript_artifact_id, args_digest, args_json
  ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(
    "legacy-root", "legacy-execution", "edition-004", "004", "edition/legacy",
    "loops-root", "seed", "digest", "{}",
  );
  legacy.close();
  const ledger = new ArtifactLedger(databasePath);
  try {
    assert.equal(ledger.requireRun("legacy-root" as never).loopsRunId, "loops-root");
    for (let index = 0; index < 7; index += 1) {
      ledger.createRun({
        runId: `child-${index}` as never,
        articleExecutionId: `article-execution-${index}` as never,
        articleId: `article-${index}`,
        editionId: "004",
        workflowVersion: "article/1",
        loopsRunId: "loops-root",
        manuscriptArtifactId: "seed" as never,
        args: {},
      });
    }
    const inspectionDb = new Database(databasePath, { readonly: true });
    try {
      const indexes = inspectionDb.prepare("PRAGMA index_list(magazine_runs)").all() as readonly { readonly name: string; readonly unique: number }[];
      const uniqueLoopsIndex = indexes.some((index) => {
        if (index.unique !== 1) return false;
        const escaped = index.name.replaceAll('"', '""');
        const columns = inspectionDb.prepare(`PRAGMA index_info("${escaped}")`).all() as readonly { readonly name: string | null }[];
        return columns.length === 1 && columns[0]?.name === "loops_run_id";
      });
      assert.equal(uniqueLoopsIndex, false);
    } finally {
      inspectionDb.close();
    }
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("Edition 4 Loops root plans seven children with exact source lineage and resumes without duplicate work", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-loops-root-"));
  const repositoryRoot = join(root, "repo");
  const workRoot = join(root, "work");
  const databasePath = join(root, "magazine.sqlite");
  const loopsDatabasePath = join(root, "loops.sqlite");
  await mkdir(workRoot, { recursive: true });
  const pipelineRef = await createProfilePipeline(repositoryRoot, workRoot);
  const sharedLedger = new ArtifactLedger(databasePath);
  const waitCalls: string[] = [];
  const articlePorts = waitingArticlePorts(sharedLedger, waitCalls);
  const rendererIdentity = testRendererIdentity();
  const options = {
    databasePath,
    loopsDatabasePath,
    projectRoot: PROJECT_ROOT,
    repositoryRoot,
    workRoot,
    renderer: {
      workDirectory: join(root, "renderer"),
      toolchain: {
        uvExecutable: process.execPath,
        pythonExecutable: process.execPath,
        expected: {
          uvSha256: "sha256:test",
          uvVersion: "test",
          pythonSha256: "sha256:test",
          pythonVersion: "test",
          pythonImplementation: "test",
          pythonCacheTag: "test",
          platform: "darwin-arm64",
        },
      },
    },
    articlePorts,
    rendererIdentity,
  } as const;
  const runId = "edition-test-root" as import("../contracts/index.ts").RunId;
  let engine: EditionWorkflowEngine | undefined;
  try {
    engine = new EditionWorkflowEngine(options);
    const first = await engine.startEdition({ pipelineRef, runId });
    assert.equal(first.status, "waiting");
    assert.equal(first.editionId, "004");
    assert.equal(first.children.length, 7);
    assert.equal(first.articleExecutionIds.length, 7);
    assert.equal(new Set(first.articleExecutionIds).size, 7);
    assert.equal(first.imageGenerationAllowed, false);
    assert.equal(first.selectedImageRevisions.length, 13);
    assert.equal(first.workflowPin?.source && (first.workflowPin.source as { entryPath?: unknown }).entryPath, "engine/workflows/edition-loops-entry.ts");
    assert.equal(first.invocations.filter((invocation) => invocation.parentInvocationId !== undefined).length, 7);
    assert.equal(first.calls.filter((call) => call.kind === "workflow").length, 7);
    assert.equal(first.waits.length, 7);
    assert.equal(new Set(waitCalls).size, 7);
    assert.equal(first.calls.some((call) => /(?:image|art)[._-]?(?:generation|offer)/iu.test(call.key)), false);

    for (const child of first.children) {
      assert.equal(child.sourceLineage.length, child.sourceIds.length);
      assert.equal(child.sourceLineage.length > 0, true);
      const args = first.invocations.find((invocation) => invocation.invocationId === child.invocationId)?.args as { readonly entry?: { readonly materializedInputs?: readonly { readonly ref: InputRevisionRef; readonly artifacts: readonly { readonly artifactId: ArtifactId }[] }[] } } | undefined;
      assert.ok(args?.entry?.materializedInputs?.some((input) => input.ref.kind === "source_extraction"));
      for (const lineage of child.sourceLineage) {
        assert.equal(lineage.capture.kind, "source_capture");
        assert.equal(lineage.extraction.kind, "source_extraction");
        assert.ok(lineage.captureArtifactIds.length > 0);
        assert.ok(lineage.extractionArtifactIds.length > 0);
        for (const [artifactId, expected] of [
          ...lineage.captureArtifactIds.map((artifactId) => [artifactId, lineage.capture] as const),
          ...lineage.extractionArtifactIds.map((artifactId) => [artifactId, lineage.extraction] as const),
        ]) {
          const artifact = sharedLedger.requireArtifact(artifactId);
          assert.deepEqual(artifact.metadata.inputRevision, expected);
        }
      }
    }
    const planDigest = sharedLedger.requireArtifact(first.planArtifactId).digest;
    const initialInvocationIds = first.invocations.map((invocation) => invocation.invocationId);
    const initialCallIds = first.calls.map((call) => call.callId);
    const initialWaitIds = first.waits.map((wait) => wait.waitId);
    engine.close();
    engine = new EditionWorkflowEngine(options);
    const resumed = await engine.resume(runId);
    assert.equal(resumed.status, "waiting");
    assert.deepEqual(resumed.invocations.map((invocation) => invocation.invocationId), initialInvocationIds);
    assert.deepEqual(resumed.calls.map((call) => call.callId), initialCallIds);
    assert.deepEqual(resumed.waits.map((wait) => wait.waitId), initialWaitIds);
    assert.equal(new Set(waitCalls).size, 7);
    assert.equal(sharedLedger.requireArtifact(resumed.planArtifactId).digest, planDigest);
    assert.equal(resumed.calls.filter((call) => call.kind === "workflow").length, 7);
    assert.equal(resumed.children.filter((child) => child.status !== "pending").length, 7);
    assert.equal(resumed.imageGenerationAllowed, false);

    // Tamper with a child lineage using another valid materialized artifact.
    // Update every persisted root binding so the guard reaches the exact
    // source-artifact check instead of merely detecting a stale root digest.
    const storedArgs = sharedLedger.requireRun(runId).args as unknown as EditionWorkflowArgs;
    const firstChild = storedArgs.children[0]!;
    const firstLineage = firstChild.sourceLineage[0]!;
    const wrongCaptureArtifactId = firstLineage.extractionArtifactIds[0]!;
    const tamperedLineage = { ...firstLineage, captureArtifactIds: [wrongCaptureArtifactId] };
    const tamperedChild = { ...firstChild, sourceLineage: [tamperedLineage] };
    const tamperedArgs: EditionWorkflowArgs = {
      ...storedArgs,
      plan: {
        ...storedArgs.plan,
        children: storedArgs.plan.children.map((child) => child.articleId === tamperedChild.articleId
          ? { ...child, sourceLineage: [tamperedLineage] }
          : child),
      },
      children: storedArgs.children.map((child) => child.articleId === tamperedChild.articleId ? tamperedChild : child),
    };
    engine.close();
    engine = undefined;
    sharedLedger.close();
    writeTamperedEditionRootState(databasePath, loopsDatabasePath, tamperedArgs);
    let tamperedLedger = new ArtifactLedger(databasePath);
    engine = new EditionWorkflowEngine({
      ...options,
      articlePorts: waitingArticlePorts(tamperedLedger, waitCalls),
    });
    await assert.rejects(engine.inspect(runId), /inexact materialized artifact set|changed identity/iu);
    await assert.rejects(engine.resume(runId), /inexact materialized artifact set|changed identity/iu);
    engine.close();
    engine = undefined;
    tamperedLedger.close();

    // A separately valid image revision in the plan must not diverge from the
    // root's selected-image list. Exercise both public re-entry paths.
    const imageTamperedArgs: EditionWorkflowArgs = {
      ...tamperedArgs,
      plan: {
        ...tamperedArgs.plan,
        selectedImageRevisions: tamperedArgs.plan.selectedImageRevisions.map((image, index) =>
          index === 0 ? { ...image, revisionId: `${image.revisionId}-different` as RevisionId } : image),
      },
    };
    writeTamperedEditionRootState(databasePath, loopsDatabasePath, imageTamperedArgs);
    const imageTamperedLedger = new ArtifactLedger(databasePath);
    engine = new EditionWorkflowEngine({
      ...options,
      articlePorts: waitingArticlePorts(imageTamperedLedger, waitCalls),
    });
    await assert.rejects(engine.inspect(runId), /image selection/iu);
    await assert.rejects(engine.resume(runId), /image selection/iu);
    engine.close();
    engine = undefined;
    imageTamperedLedger.close();
  } finally {
    engine?.close();
    sharedLedger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("public edition root measures and promotes the opening editorial through the pinned renderer operation", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-editorial-root-"));
  const repositoryRoot = join(root, "repo");
  const workRoot = join(root, "work");
  const databasePath = join(root, "magazine.sqlite");
  const loopsDatabasePath = join(root, "loops.sqlite");
  await mkdir(workRoot, { recursive: true });
  const pipelineRef = await createProfilePipeline(repositoryRoot, workRoot);
  const ledger = new ArtifactLedger(databasePath);
  const manifests: RenderManifest[] = [];
  const adapter: RendererAdapter = {
    render: async (manifestPath) => {
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as RenderManifest;
      manifests.push(manifest);
      return { schemaVersion: 1, rendererContractVersion: "magazine-renderer/1", editionId: manifest.editionId, files: [], layouts: [{ language: "en", totalPages: 8, editorialPages: 1, articlePages: Object.fromEntries(Array.from({ length: 7 }, (_, index) => [`article-${index + 1}`, 1])), figureCount: 0, criticResult: "not_run" }], inputArtifactIds: manifest.inputs.map((input) => input.artifactId), tailArtFacts: {} };
    },
  };
  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  const worker = async (principalId: string, authorityKind: "model" | "tool", capabilities: readonly string[]) => {
    await authority.enrollWorker({ principalId, authority: authorityKind, capabilities: [...capabilities] as never });
    const credential = await authority.createCredentialProfile({ principalId, credentialProfileId: `${principalId}-profile` });
    await authority.grant({ credentialProfileId: credential.credentialProfileId, capabilities: [...capabilities] as never });
    return await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });
  };
  const sourceAware = await worker("source-aware", "model", ["text_model", "source_access"]);
  const sourceBlind = await worker("source-blind", "model", ["text_model", "source_blind"]);
  const measurementTool = await worker("measurement-tool", "tool", ["subprocess"]);
  await authority.enrollHuman({ principalId: "editor", capabilities: ["text_model"] });
  const humanCredential = await authority.createCredentialProfile({ principalId: "editor", credentialProfileId: "editor-profile" });
  await authority.grant({ credentialProfileId: humanCredential.credentialProfileId, capabilities: ["text_model"] });
  const human = await authority.authenticate({ credentialProfileId: humanCredential.credentialProfileId, secret: humanCredential.secret });
  const rendererIdentity = testRendererIdentity();
  const renderer = { workDirectory: join(root, "renderer"), adapter, toolchain: { uvExecutable: process.execPath, pythonExecutable: process.execPath, expected: { uvSha256: "sha256:test" as const, uvVersion: "test", pythonSha256: "sha256:test" as const, pythonVersion: "test", pythonImplementation: "test", pythonCacheTag: "test", platform: "darwin-arm64" as const } } };
  const base = createArticleWorkflowPorts({ ledger, repositoryRoot, workRoot, renderer, projectRoot: PROJECT_ROOT, articleReviewWorkers: { sourceAwareReviewer: sourceAware, sourceBlindReviewer: sourceBlind, measurementTool }, articleReviewCredentials: { schemaVersion: "closed-writer-credential-resource/1", read: () => ({ OPENAI_API_KEY: "test-key" }) } });
  let writerOrdinal = 0;
  const ports: ArticleWorkflowPorts = {
    ...base,
    runEditorialWriter: async (input) => {
      writerOrdinal += 1;
      const title = "A Complete Issue";
      const manuscriptText = `---\nlabel: Opening\ntitle: ${title}\nbyline: Magazine\n---\n\nOne unifying idea.`;
      const inputs = [input.profileArtifactId, ...input.articleArtifactIds, input.currentManuscriptArtifactId, ...(input.revisionContextArtifactIds ?? [])];
      const metadata = { writerExecutionClass: "closed_editorial_writer/1", editorialExecutionId: input.editorialExecutionId, articleId: "opening", access: "source_blind", operationKey: input.operationKey, operationInputDigest: `writer-digest-${writerOrdinal}`, claimId: `writer-claim-${writerOrdinal}`, attemptId: `writer-attempt-${writerOrdinal}`, attemptNumber: 1, principalId: "editorial-writer", writerInputArtifactIds: inputs as unknown as JsonValue };
      const parents = inputs.map((artifactId) => ({ artifactId, relation: "editorial_writer_input" }));
      const manuscript = `stub-editorial-manuscript-${writerOrdinal}` as ArtifactId;
      const notes = `stub-editorial-notes-${writerOrdinal}` as ArtifactId;
      const dispositions = `stub-editorial-dispositions-${writerOrdinal}` as ArtifactId;
      ledger.createArtifact({ id: manuscript, kind: "editorial_manuscript", schemaVersion: "editorial-manuscript/1", mediaType: "text/markdown", origin: "model", payload: { kind: "text", text: manuscriptText }, parents, metadata: { ...metadata, label: "Opening", title, byline: "Magazine", revisionId: `editorial-revision-${writerOrdinal}` }, runId: ledger.requireRunByArticleExecutionId(input.editorialExecutionId as never).runId });
      ledger.createArtifact({ id: notes, kind: "editorial_working_notes", schemaVersion: "editorial-working-notes/1", mediaType: "text/plain", origin: "model", payload: { kind: "text", text: "notes" }, parents, metadata, runId: ledger.requireRunByArticleExecutionId(input.editorialExecutionId as never).runId });
      ledger.createArtifact({ id: dispositions, kind: "editorial_finding_dispositions", schemaVersion: "editorial-finding-dispositions/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: { schemaVersion: "editorial-finding-dispositions/1", dispositions: [] } }, parents, metadata, runId: ledger.requireRunByArticleExecutionId(input.editorialExecutionId as never).runId });
      return { selected: true, value: { schemaVersion: "editorial-writer-result/1", label: "Opening", title, byline: "Magazine", manuscript: manuscriptText, workingNotes: "notes", dispositions: [] }, claim: { claimId: metadata.claimId, operationKey: input.operationKey }, artifacts: [ledger.requireArtifact(manuscript), ledger.requireArtifact(notes), ledger.requireArtifact(dispositions)] };
    },
    runEditorialReview: async (input) => {
      const ids = [input.manuscriptArtifactId, input.reviewPlanArtifactId, input.measurementArtifactId];
      const id = `stub-editorial-review-${input.reviewCycleId}` as ArtifactId;
      const value = { schemaVersion: "editorial-review-result/1", editionId: "004", editorialId: "opening", target: "editorial:opening", manuscriptArtifactId: input.manuscriptArtifactId, measurementArtifactId: input.measurementArtifactId, reviewPlanArtifactId: input.reviewPlanArtifactId, reviewCycleId: input.reviewCycleId, assessment: "pass", findings: [] } as const;
      const childRun = ledger.requireArtifact(input.manuscriptArtifactId).producingRunId!;
      ledger.createArtifact({ id, kind: "editorial_review_result", schemaVersion: "editorial-review-result/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: value as unknown as JsonValue }, parents: ids.map((artifactId) => ({ artifactId, relation: "editorial_review_input" })), metadata: { reviewerExecutionClass: "closed_editorial_reviewer/1", access: "source_blind", claimId: "review-claim", attemptId: "review-attempt", principalId: "reviewer", operationInputDigest: "review-digest", reviewerInputArtifactIds: ids as unknown as JsonValue }, runId: childRun });
      return { selected: true, findings: [], artifacts: [ledger.requireArtifact(id)] };
    },
    promoteEditorial: async (input) => {
      const id = "stub-editorial-promotion" as ArtifactId;
      ledger.createArtifact({ id, kind: "editorial_durable_promotion", schemaVersion: "editorial-durable-promotion/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-durable-promotion/1" } }, parents: [{ artifactId: input.request.acceptedArtifactIds[0]!, relation: "editorial_manuscript" }], runId: input.runId });
      return { promotionArtifactId: id, durableRevisionId: input.request.revisionId, manifestDigest: "sha256:promotion", gitCommitOid: "commit" };
    },
  };
  const completedArticle = (args: ArticleRuntimeStartArgs) => createCompletedArticleStub(ledger, args);
  const engineOptions = { databasePath, loopsDatabasePath, projectRoot: PROJECT_ROOT, repositoryRoot, workRoot, renderer, articlePorts: ports, articleWorkflowStub: completedArticle, rendererIdentity } as const;
  assert.throws(() => new EditionWorkflowEngine({ ...engineOptions, renderer: undefined as never }), /pinned renderer/iu);
  const engine = new EditionWorkflowEngine(engineOptions);
  const editionRunId = "edition-editorial-integration" as import("../contracts/index.ts").RunId;
  try {
    const waiting = await engine.startEdition({ pipelineRef, runId: editionRunId });
    assert.equal(waiting.status, "waiting");
    const store = new SQLiteDurableRunStore(loopsDatabasePath);
    try {
      const inspection = store.inspectRun(editionRunId)!;
      const wait = inspection.waits.find((item) => item.status === "pending" && (item.request as { offerId?: unknown } | undefined)?.offerId !== undefined);
      assert.ok(wait, JSON.stringify({ runStatus: inspection.run.status, waits: inspection.waits.map((item) => ({ key: item.key, status: item.status })), failedCalls: inspection.calls.filter((call) => call.status === "failed").map((call) => ({ key: call.key, status: call.status, failure: call.failure })) }));
      const invocation = inspection.invocations.find((item) => item.invocationId === wait.invocationId)!;
      const offer = ledger.requireOffer((wait.request as { offerId: string }).offerId);
      const durableContext: WorkflowWaitContext = { runId: editionRunId, invocationId: invocation.invocationId, workflowName: invocation.workflowName, workflowVersion: invocation.workflowVersion, ...(invocation.workflowPin === undefined ? {} : { workflowPin: invocation.workflowPin as unknown as JsonObject }), callId: wait.callId, waitId: wait.waitId, key: wait.key, kind: "wait" };
      const decision = await ledger.createHumanDecisionAuthority().decideEditorial(human, { runId: offer.runId, offerId: offer.id, taskArtifactId: offer.taskArtifactId, inputArtifactIds: offer.inputArtifactIds, choice: "accept", rationale: "Ready" }, durableContext);
      await store.answerWait({ runId: editionRunId, waitId: wait.waitId, answer: { decisionArtifactId: decision.artifactId } });
    } finally { store.close(); }
    const complete = await engine.resume(editionRunId);
    assert.equal(complete.status, "complete");
    assert.equal((complete.editorial as { status?: unknown }).status, "complete");
    assert.equal(manifests.length, 1);
    assert.equal(manifests[0]!.operation, "measure_edition");
    assert.deepEqual(manifests[0]!.languages, ["en"]);
    const editorial = complete.editorial as { readonly manuscriptArtifactId: ArtifactId; readonly articleArtifactIds: readonly ArtifactId[] };
    for (const id of [editorial.manuscriptArtifactId, ...editorial.articleArtifactIds]) assert.ok(manifests[0]!.inputs.some((input) => input.artifactId === id));
  } finally {
    engine.close();
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

function createCompletedArticleStub(ledger: ArtifactLedger, args: ArticleRuntimeStartArgs) {
  // The stub completes the launch seed in place. A real article workflow
  // would advance the run to its selected revision; this fixture keeps the
  // immutable launch manuscript identity so the root binding remains exact.
  const manuscript = args.manuscriptArtifactId;
  const seed = ledger.requireArtifact(manuscript);
  const revision = (typeof seed.metadata.revisionId === "string" ? seed.metadata.revisionId : `completed-revision-${args.articleId}`) as ManuscriptRevisionId;
  const recordId = `completed-record-${args.articleId}` as ArtifactId;
  const record: ArticleRevisionRecord = { schemaVersion: "article-revision-record/1", ordinal: 0, manuscriptArtifactId: manuscript, manuscriptRevisionId: revision, reviewMaterialArtifactIds: [], humanRulingArtifactIds: [], trigger: "initial" };
  ledger.createArtifact({ id: recordId, kind: "article_revision_record", schemaVersion: "article-revision-record/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: record as unknown as JsonValue }, parents: articleRevisionRecordParents(record), metadata: { articleId: args.articleId, manuscriptArtifactId: manuscript, manuscriptRevisionId: revision }, runId: args.runId });
  ledger.recordCurrentRevisionRecord(args.runId!, recordId);
  const measurement = `completed-measurement-${args.articleId}` as ArtifactId;
  const decision = `completed-decision-${args.articleId}` as ArtifactId;
  ledger.createArtifact({ id: measurement, kind: "article_measurement", schemaVersion: "article-measurement/1", mediaType: "application/json", origin: "subprocess", payload: { kind: "json", value: {} }, runId: args.runId });
  ledger.createArtifact({ id: decision, kind: "article_human_decision", schemaVersion: "article-human-decision/1", mediaType: "application/json", origin: "human", payload: { kind: "json", value: {} }, runId: args.runId });
  return { schemaVersion: "magazine-article-workflow-result/1", runId: args.runId, articleExecutionId: args.articleExecutionId, articleId: args.articleId, status: "complete", manuscriptArtifactId: manuscript, currentRevisionRecordArtifactId: recordId, measurementArtifactId: measurement, decisionArtifactId: decision, durableRevisionId: `durable-${args.articleId}` };
}

function waitingArticlePorts(ledger: ArtifactLedger, waitCalls: string[]): ArticleWorkflowPorts {
  return {
    ledger,
    validateRuntimeResources: async () => undefined,
    measureArticle: async () => { throw new Error("measurement is not reached in this root test"); },
    runReviewPanel: async () => { throw new Error("review is not reached in this root test"); },
    runWriter: async (input, context): Promise<ArticleAttemptExecutionResult<never>> => {
      waitCalls.push(context.durableContext?.()?.invocationId ?? input.articleExecutionId);
      await context.wait(`test.child.${input.articleExecutionId}`, {
        request: { articleExecutionId: input.articleExecutionId },
      });
      throw new Error("test child remains suspended");
    },
    requireDecision: () => { throw new Error("decision is not reached in this root test"); },
    promote: async () => { throw new Error("promotion is not reached in this root test"); },
  };
}

function testRendererIdentity(): RendererIdentity {
  return {
    schemaVersion: "magazine-article-runtime-identity/1",
    graphHash: "sha256:test",
    manifestHash: "sha256:test",
    rendererAdapter: "python-uv-locked/1",
    rendererEntrypoint: "magazine.engine_render_bridge:main",
    rendererContractVersion: "magazine-renderer/1",
    authorityPolicy: "local-authority-exact-offer/1",
    promotionAdapter: "durable-store-git-cli/1",
    defaultBackend: "magazine-no-agent",
    defaultModel: "none",
    budget: { total: null, unit: "calls" },
    files: [],
  };
}

function writeTamperedEditionRootState(
  databasePath: string,
  loopsDatabasePath: string,
  args: EditionWorkflowArgs,
): void {
  const argsJson = JSON.stringify(args);
  const argsDigest = createHash("sha256").update(argsJson, "utf8").digest("hex");
  const updateJsonArtifact = (database: Database.Database, artifactId: string, value: unknown): void => {
    const payload = Buffer.from(JSON.stringify(value), "utf8");
    const digest = createHash("sha256").update(payload).digest("hex");
    database.prepare("UPDATE magazine_artifacts SET payload = ?, digest = ? WHERE id = ?").run(payload, digest, artifactId);
  };
  const database = new Database(databasePath);
  try {
    updateJsonArtifact(database, args.planArtifactId, args.plan);
    const sourceParentIds = [...new Set(args.plan.children.flatMap((child) => child.sourceLineage.flatMap((lineage) => [
      ...lineage.captureArtifactIds,
      ...lineage.extractionArtifactIds,
    ])))];
    database.prepare("DELETE FROM magazine_artifact_edges WHERE child_artifact_id = ?").run(args.planArtifactId);
    sourceParentIds.forEach((artifactId, ordinal) => {
      database.prepare(
        "INSERT INTO magazine_artifact_edges(child_artifact_id, parent_artifact_id, relation, ordinal) VALUES (?, ?, ?, ?)",
      ).run(args.planArtifactId, artifactId, "source_lineage", ordinal);
    });
    updateJsonArtifact(database, args.entryArtifactId, args);
    database.prepare("UPDATE magazine_runs SET args_json = ?, args_digest = ?, updated_at = ? WHERE run_id = ?").run(
      argsJson,
      argsDigest,
      new Date().toISOString(),
      args.runId,
    );
  } finally {
    database.close();
  }

  const loops = new Database(loopsDatabasePath);
  try {
    const canonical = canonicalizeDurableValue(args);
    loops.exec("DROP TRIGGER IF EXISTS durable_runs_immutable_identity");
    loops.prepare("UPDATE durable_runs SET args_json = ?, args_hash = ? WHERE run_id = ?").run(
      canonical,
      hashDurableValue(canonical, true),
      args.runId,
    );
  } finally {
    loops.close();
  }
}

async function createProfilePipeline(repositoryRoot: string, workRoot: string): Promise<Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>> {
  await execFile("git", ["init", "-q", "-b", "main", repositoryRoot]);
  await execFile("git", ["config", "user.email", "test@example.com"], { cwd: repositoryRoot });
  await execFile("git", ["config", "user.name", "Magazine Test"], { cwd: repositoryRoot });
  const refs = {
    pipeline: { kind: "write_pipeline", editionId: "004", logicalId: "edition4-test", revisionId: REVISION },
    edition: { kind: "edition_spec", editionId: "004", logicalId: "edition4", revisionId: REVISION },
    capture: { kind: "source_capture", logicalId: "source", revisionId: REVISION },
    extraction: { kind: "source_extraction", logicalId: "source", revisionId: REVISION },
    profile: { kind: "article_production_profile", logicalId: "profile", revisionId: REVISION },
    plan: { kind: "article_review_plan", logicalId: "review-plan", revisionId: REVISION },
    writer: { kind: "prompt", logicalId: "writer", revisionId: REVISION },
    evidence: { kind: "prompt", logicalId: "evidence", revisionId: REVISION },
    rules: { kind: "policy", logicalId: "rules", revisionId: REVISION },
    measure: { kind: "policy", logicalId: "measure", revisionId: REVISION },
  } as const;
  const raw = (ref: InputRevisionRef): JsonObject => ({
    kind: ref.kind,
    logical_id: ref.logicalId,
    revision_id: ref.revisionId,
    ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }),
  });
  const articles = Array.from({ length: 7 }, (_, index) => ({
    article_id: `article-${index + 1}`,
    content_mode: "faithful_synthesis",
    byline: "Source Author",
    source_ids: ["source"],
    source_authors: ["Source Author"],
    brief: "Write from the complete source extraction.",
    production_profile_revision: raw(refs.profile),
    parent: null,
    maximum_reader_pages: 7,
    model_policy: { default: { adapter: "test", model: "test" } },
  }));
  const pipeline = {
    schema_version: 1,
    edition_id: "004",
    pipeline_id: "edition4-test",
    edition_spec: raw(refs.edition),
    sources: [{ source_id: "source", capture: raw(refs.capture), extraction: raw(refs.extraction) }],
    articles,
    editorial: { editorial_id: "opening", brief: "Opening", writer_prompt: raw(refs.writer), input_revisions: [raw(refs.rules)], parent: null, maximum_reader_pages: 1, model_policy: { default: { adapter: "test", model: "test" } } },
    translations: [{ language: "es", source_language: "en", prompt: raw(refs.writer), input_revisions: [raw(refs.rules)], parents: Object.fromEntries([...articles.map((article) => [article.article_id, null]), ["opening", null]]), maximum_reader_pages: 7, model_policy: { default: { adapter: "test", model: "test" } } }],
    images: Array.from({ length: 13 }, (_, index) => ({ kind: "image", edition_id: "004", logical_id: `image-${index + 1}`, revision_id: REVISION })),
    layout_inputs: [raw(refs.edition)],
    renderer_inputs: [{ input: raw(refs.edition), payload_path: "edition.yaml", renderer_target_path: "editions/004/edition.yaml" }],
    render: { primary_language: "en", publication_name: "Test", renderer: "reportlab", configured_languages: ["en", "es"], studio_policy: "not_applicable" },
  };
  const requests = [
    { ref: refs.edition, files: [{ path: "edition.yaml", mediaType: "application/yaml", content: "edition_id: 004\n" }] },
    { ref: refs.capture, files: [{ path: "raw/source.json", mediaType: "application/json", content: "{\"url\":\"https://example.test/source\"}\n" }] },
    { ref: refs.extraction, files: [{ path: "extracted.md", mediaType: "text/markdown", content: "# Source\n\nComplete extraction evidence.\n" }] },
    { ref: refs.profile, files: [{ path: "profile.json", mediaType: "application/json", content: JSON.stringify({ schema_version: "article-production-profile/1", profile_id: "profile", format_id: "longform", writer: { prompt_revision: raw(refs.writer), result_contract_version: "article-writer-result/1", review_materials: [] }, review_plan_revision: raw(refs.plan), writing_rules_revision: raw(refs.rules), writing_policy_revisions: [], revision_policy: { maximum_rewrites: 1 } }) }] },
    { ref: refs.plan, files: [{ path: "review-plan.json", mediaType: "application/json", content: JSON.stringify({ schema_version: "article-review-plan/1", checks: [{ kind: "model_review", id: "evidence", role: "article_review", prompt_revision: raw(refs.evidence), access: "source_aware", authority: "blocking" }, { kind: "article_measurement", id: "measure_article", role: "measure_article", measurement_profile_revision: raw(refs.measure), maximum_reader_pages: 7 }], waves: [{ id: "panel", check_ids: ["evidence", "measure_article"], stop_after: "never" }] }) }] },
    { ref: refs.writer, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Write.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.evidence, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Review.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.rules, files: [{ path: "policy.md", mediaType: "text/markdown", content: "Rules.\n" }] },
    { ref: refs.measure, files: [{ path: "policy.md", mediaType: "text/markdown", content: "Measure.\n" }] },
    { ref: refs.pipeline, files: [{ path: "production.yaml", mediaType: "application/yaml", content: JSON.stringify(pipeline) }] },
  ] as const;
  const materialized = [] as Awaited<ReturnType<typeof materializeNativeInputRevision>>[];
  for (const request of requests) materialized.push(await materializeNativeInputRevision(repositoryRoot, workRoot, { ref: request.ref, createdAt: "2026-08-04T00:00:00.000Z", parentRevisionId: null, files: request.files }));
  const git = new GitCliDurableGit(repositoryRoot);
  await git.checkpointInputMigration({ migrationId: "edition4-test-inputs", repositoryPaths: materialized.flatMap((input) => input.repositoryPaths), manifestDigests: Object.fromEntries(materialized.map((input) => [input.repositoryPaths.find((path) => path.endsWith("/manifest.yaml"))!, input.manifestDigest])) });
  const resolved = await resolveAuthenticatedWritePipelineInputs(repositoryRoot, refs.pipeline, git);
  assert.equal(resolved.pipeline.document.articles.length, 7);
  return refs.pipeline;
}
