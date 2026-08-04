import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createDurableWorkflowPin, createRuntime, SQLiteDurableRunStore } from "@loops/core";

import type { ArticleInputBinding, ArticleWorkflowResult } from "../contracts/workflow-run.ts";
import type { ArtifactId, ArticleExecutionId, JsonObject, RunId } from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import type { LoopsArticleEntryInput } from "../durable/write-pipeline.ts";
import type { ArticleMaterialContext, ArticleMaterialSet } from "../article-production/materials.ts";
import type { ArticleReviewCheckResult, ArticleReviewPanelResult } from "../workflows/article-review-panel.ts";
import type { MagazineWorkflowContext } from "../workflows/internal-types.ts";
import { ArtifactLedger, type LedgerDecision } from "../workflow-authority/artifact-ledger.ts";
import { LocalAuthorityStore, type AuthorizedWorker } from "../authority/local-authority.ts";
import { runArticleWorkflow } from "../workflows/article-workflow.ts";
import type { ArticleWorkflowPorts } from "../workflows/internal-types.ts";
import type { RendererIdentity } from "../workflows/renderer-identity.ts";
import { z } from "zod/v3";
import { CLOSED_WRITER_RUNTIME_IDENTITY } from "../executors/closed-writer/runtime.ts";

const id = (value: string) => value as ArtifactId;
const runId = "loop-run" as RunId;
const articleExecutionId = "loop-article-execution" as ArticleExecutionId;
const revision = { kind: "source_extraction", logicalId: "source", revisionId: "source-revision" as never } as InputRevisionRef;

test("article workflow rewrites with fresh cycle keys and promotes the final manuscript", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-article-loop-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  const writerStores: SQLiteDurableRunStore[] = [];
  try {
    const source = id("source-artifact");
    const seed = id("seed-manuscript");
    const baseProfile = id("base-measurement-profile");
    ledger.createArtifact({
      id: source,
      kind: "source_extraction",
      schemaVersion: "source-extraction/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "source" },
      metadata: { revisionId: revision.revisionId, inputRevision: revision as unknown as JsonObject },
    });
    ledger.createArtifact({
      id: seed,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "initial" },
      parents: [{ artifactId: source, relation: "input_binding" }],
      metadata: { articleId: "article", revisionId: "seed-revision" },
    });
    ledger.createArtifact({
      id: baseProfile,
      kind: "article_measurement_profile",
      schemaVersion: "article-measurement-profile/1",
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: { inputs: [{ artifactId: seed }] } },
      parents: [{ artifactId: seed, relation: "profile_manuscript" }],
    });
    ledger.createRun({
      runId,
      articleExecutionId,
      articleId: "article",
      editionId: "004",
      workflowVersion: "loop-test/1",
      loopsRunId: runId,
      manuscriptArtifactId: seed,
      args: { articleId: "article" },
    });
    const entry = entryInput(source);
    const authority = await LocalAuthorityStore.init(join(root, "authority"));
    await authority.enrollWorker({ principalId: "writer", authority: "model", capabilities: ["text_model", "source_access"] });
    const writerCredential = await authority.createCredentialProfile({ principalId: "writer", credentialProfileId: "writer-profile" });
    await authority.grant({ credentialProfileId: writerCredential.credentialProfileId, grantId: "writer-grant", capabilities: ["text_model", "source_access"] });
    const writerWorker = await authority.authenticate({ credentialProfileId: writerCredential.credentialProfileId, secret: writerCredential.secret });
    const writerRunner = ledger.createArticleAttemptRunner();
    const writerPin = createDurableWorkflowPin({
      source: { entryPath: "engine/test/article-workflow-loop.test.ts", graphHash: "sha256:writer-graph" },
      dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:writer-lock" },
      execution: { backend: "article-loop-writer" },
    });
    const writerBackend = {
      name: "article-loop-writer",
      capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
      async run(): Promise<never> { throw new Error("agent calls are not part of this test"); },
    };
    let writerAttempts = 0;
    const args = {
      runId,
      articleExecutionId,
      rewriteOrdinal: 0,
      articleId: "article",
      editionId: "004",
      language: "en",
      logicalItem: { kind: "article", editionId: "004", logicalId: "article", language: "en" } as const,
      manuscriptArtifactId: seed,
      measurementProfileArtifactId: baseProfile,
      expectedParentRevisionId: null,
      promotionId: "promotion-loop" as never,
      revisionId: "revision-loop" as never,
      entryArtifactId: source,
      productionProfileArtifactId: baseProfile,
      entry,
      rendererIdentity: {} as never,
      review: { materialContext: materialContext(entry) },
    } as const;
    const steps = new Map<string, unknown>();
    const stepKeys: string[] = [];
    const stepAttempts = new Map<string, number>();
    let panels = 0;
    let writes = 0;
    let initialWriterInputIds: readonly ArtifactId[] | undefined;
    let decisionRequest: { readonly offerId: string; readonly taskArtifactId: ArtifactId; readonly inputArtifactIds: readonly ArtifactId[] } | undefined;
    const context: MagazineWorkflowContext = {
      step: async (key, fn) => {
        stepKeys.push(key);
        if (!steps.has(key)) {
          let attempt = 0;
          for (;;) {
            attempt += 1;
            stepAttempts.set(key, attempt);
            try {
              steps.set(key, await fn());
              break;
            } catch (error) {
              if (!key.startsWith("article.writer.") || attempt >= 2) throw error;
            }
          }
        }
        return steps.get(key) as never;
      },
      parallel: async (thunks) => Object.freeze(await Promise.all(thunks.map((thunk) => thunk()))),
      wait: async (_key, options) => {
        decisionRequest = {
          offerId: options.request.offerId as string,
          taskArtifactId: options.request.taskArtifactId as ArtifactId,
          inputArtifactIds: (() => {
            const bytes = ledger.readArtifact(options.request.taskArtifactId as ArtifactId).bytes;
            const value = JSON.parse(Buffer.from(bytes).toString("utf8")) as { readonly inputArtifactIds?: readonly ArtifactId[] };
            return value.inputArtifactIds ?? [];
          })(),
        };
        return { decisionArtifactId: options.request.decisionArtifactId as ArtifactId };
      },
    };
    const reviewResults = (): ArticleReviewPanelResult => {
      panels += 1;
      const manuscriptArtifactId = ledger.requireRun(runId).manuscriptArtifactId;
      const manuscriptRevisionId = ledger.requireArtifact(manuscriptArtifactId).metadata.revisionId as never;
      const resultId = id(`review-result-${panels}`);
      const measurementId = id(`measurement-${panels}`);
      const finding = panels === 1 ? [{ localId: "fix", severity: "must_fix" as const, scope: { kind: "document" as const }, problem: "fix", requestedOutcome: "fix", evidenceArtifactIds: [manuscriptArtifactId] }] : [];
      ledger.createArtifact({ id: resultId, kind: "article_review_result", schemaVersion: "article-review-result/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: { schemaVersion: "article-review-result/1", reviewerId: "reviewer", manuscriptArtifactId, assessment: finding.length ? "findings" : "pass", findings: finding } }, parents: [{ artifactId: manuscriptArtifactId, relation: "review_input" }], runId });
      ledger.createArtifact({ id: measurementId, kind: "article_measurement", schemaVersion: "article-measurement/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "article-measurement/1", articleId: "article", manuscriptArtifactId, pageCount: 1, maximumReaderPages: 7, fits: true, openerFits: true, layouts: [], inputArtifactIds: [manuscriptArtifactId] } }, parents: [{ artifactId: manuscriptArtifactId, relation: "measurement_input" }], runId });
      const checks: ArticleReviewCheckResult[] = [
        { schemaVersion: "article-review-check-result/2", status: "completed", waveId: "wave", checkId: "evidence", kind: "model_review", key: `review-${panels}`, manuscriptArtifactId, manuscriptRevisionId, materialArtifactIds: [manuscriptArtifactId], outputArtifactIds: [resultId], resultArtifactId: resultId, reviewerId: "reviewer", assessment: finding.length ? "findings" : "pass", findings: finding, result: { schemaVersion: "article-review-result/1", reviewerId: "reviewer", manuscriptArtifactId, assessment: finding.length ? "findings" : "pass", findings: finding } },
        { schemaVersion: "article-review-check-result/2", status: "completed", waveId: "wave", checkId: "measure_article", kind: "article_measurement", key: `measure-${panels}`, manuscriptArtifactId, manuscriptRevisionId, materialArtifactIds: [manuscriptArtifactId], outputArtifactIds: [measurementId], resultArtifactId: measurementId, reviewerId: "measure", assessment: "pass", findings: [], result: { schemaVersion: "article-measurement/1", articleId: "article", manuscriptArtifactId, pageCount: 1, maximumReaderPages: 7, fits: true, openerFits: true, layouts: [], inputArtifactIds: [manuscriptArtifactId] } },
      ];
      return { schemaVersion: "article-review-panel/2", runId, articleExecutionId, articleId: "article", manuscriptOrdinal: panels - 1, manuscriptArtifactId, manuscriptRevisionId, checks };
    };
    const ports: ArticleWorkflowPorts = {
      ledger,
      runReviewPanel: async () => reviewResults(),
      measureArticle: async ({ articleId, manuscriptArtifactId }) => ({ schemaVersion: "article-measurement/1", articleId, manuscriptArtifactId, pageCount: 1, maximumReaderPages: 7, fits: true, openerFits: true, layouts: [], inputArtifactIds: [manuscriptArtifactId] }),
      runWriter: async (input, _writerContext) => {
        writes += 1;
        const writerStore = new SQLiteDurableRunStore(join(root, `writer-loops-${writes}.sqlite`));
        writerStores.push(writerStore);
        const runtime = createRuntime({
          backend: writerBackend,
          defaultBackend: writerBackend.name,
          durable: { store: writerStore, runId, workflowName: "article-loop-writer", workflowPin: writerPin },
        });
        return await runtime.run(async (globals) => await globals.step(
          input.operationKey,
          async () => {
            writerAttempts += 1;
            return await writerRunner.executeModel(
              writerWorker,
              {
                rootRunId: runId,
                articleExecutionId,
                articleId: "article",
                operationKey: input.operationKey,
                manuscriptArtifactId: input.currentManuscriptArtifactId,
                access: "source_aware",
                materials: writerMaterials(source, input.currentManuscriptArtifactId),
              },
              async () => {
                if (writerAttempts === 1) throw new Error("provider retry");
                const writerInputArtifactIds = input.revisionContextArtifactId === undefined
                  ? [source, input.currentManuscriptArtifactId] as const
                  : [source, input.currentManuscriptArtifactId, input.revisionContextArtifactId] as const;
                if (input.mode === "initial") initialWriterInputIds = writerInputArtifactIds;
                const parents = writerInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" }));
                const writerContractMetadata = {
                  writerExecutionClass: "closed_writer/1",
                  writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY,
                  writerInputArtifactIds,
                  ...(input.revisionContextArtifactId === undefined ? {} : { revisionContextArtifactId: input.revisionContextArtifactId }),
                } as const;
                return {
                  value: { schemaVersion: "article-writer-result/1", manuscript: "rewritten", workingNotes: "notes", dispositions: [], reviewMaterials: [] },
                  artifacts: [
                    { key: "manuscript", kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "model" as const, payload: { kind: "text" as const, text: "rewritten" }, parents, metadata: { articleId: "article", revisionId: "writer-revision", ...writerContractMetadata } },
                    { key: "working-notes", kind: "writer_working_notes", schemaVersion: "writer-working-notes/1", mediaType: "text/plain", origin: "model" as const, payload: { kind: "text" as const, text: "notes" }, parents, metadata: { articleId: "article", ...writerContractMetadata } },
                    { key: "finding-dispositions", kind: "writer_finding_dispositions", schemaVersion: "writer-finding-dispositions/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { schemaVersion: "writer-finding-dispositions/1", dispositions: [] } }, parents, metadata: { articleId: "article", ...writerContractMetadata } },
                  ],
                };
              },
            );
          },
          { input: { operationKey: input.operationKey }, retry: { maxAttempts: 2, retryOn: "always" } },
        ));
      },
      requireDecision: (decisionArtifactId) => ({ id: "decision", runId, offerId: decisionRequest?.offerId ?? "offer", taskArtifactId: decisionRequest?.taskArtifactId ?? id("task"), inputArtifactIds: decisionRequest?.inputArtifactIds ?? [], principalId: "editor", credentialProfileId: "editor", choice: "accept", rationale: "accept", artifactId: decisionArtifactId, validatorVersion: "article-editor-decision-validator/1", canonicalApprovedFindingIds: [], rewriteBudget: { rewritesUsed: 1, maximumRewrites: 1, remainingRewrites: 0, additionalRewriteBudget: 0, counts: "writer_rewrites_only" }, createdAt: "2026-01-01T00:00:00.000Z" } satisfies LedgerDecision),
      promote: async (input) => ({ schemaVersion: "magazine-article-workflow-result/1", runId, articleExecutionId, articleId: "article", status: "complete", manuscriptArtifactId: input.request.acceptedArtifactIds[0]!, measurementArtifactId: input.measurementArtifactId!, decisionArtifactId: input.request.decisionArtifactIds[0]! } satisfies ArticleWorkflowResult),
    };
    const result = await runArticleWorkflow(args, context, ports);
    assert.equal(result.status, "complete");
    assert.equal(writes, 2);
    assert.equal(writerAttempts, 3);
    assert.equal(panels, 2);
    assert.equal(writes, 2);
    assert.deepEqual(initialWriterInputIds, [source, seed]);
    assert.notEqual(Buffer.from(ledger.readArtifact(result.manuscriptArtifactId).bytes).toString("utf8"), "source");
    assert.ok(stepKeys.filter((key) => key.startsWith("article.review-routing.")).length === 2);
  } finally {
    for (const store of writerStores) store.close();
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("real Loops restart replays a committed writer revision and returns the same wait", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-article-loop-restart-"));
  const ledgerPath = join(root, "magazine.sqlite");
  const loopsPath = join(root, "loops.sqlite");
  const restartRunId = "loop-restart-run" as RunId;
  const restartExecutionId = "loop-restart-execution" as ArticleExecutionId;
  const source = id("restart-source");
  const seed = id("restart-seed");
  const profile = id("restart-profile");
  const entryArtifactId = id("restart-entry");
  const entry = entryInput(source);
  const ledgerClock = { now: () => new Date("2026-01-01T00:00:00.000Z") };
  let ledger = new ArtifactLedger(ledgerPath, { clock: ledgerClock });
  let loops: SQLiteDurableRunStore | undefined;
  let writerAttempts = 0;
  let panelCalls = 0;
  let decisionRequest: { readonly offerId: string; readonly taskArtifactId: ArtifactId; readonly inputArtifactIds: readonly ArtifactId[]; readonly decisionArtifactId: ArtifactId } | undefined;
  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollWorker({ principalId: "restart-writer", authority: "model", capabilities: ["text_model", "source_access"] });
  const credential = await authority.createCredentialProfile({ principalId: "restart-writer", credentialProfileId: "restart-writer-profile" });
  await authority.grant({ credentialProfileId: credential.credentialProfileId, grantId: "restart-writer-grant", capabilities: ["text_model", "source_access"] });
  const writerWorker = await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });
  const pin = createDurableWorkflowPin({
    source: { entryPath: "engine/test/article-workflow-loop.test.ts", graphHash: "sha256:restart-graph" },
    dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:restart-lock" },
    execution: { backend: "article-loop-restart" },
  });
  const backend = {
    name: "article-loop-restart",
    capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
    async run(): Promise<never> { throw new Error("agent calls are not part of this test"); },
  };
  const args = {
    runId: restartRunId,
    articleExecutionId: restartExecutionId,
    rewriteOrdinal: 0,
    articleId: "article",
    editionId: "004",
    language: "en",
    logicalItem: { kind: "article", editionId: "004", logicalId: "article", language: "en" } as const,
    manuscriptArtifactId: seed,
    measurementProfileArtifactId: profile,
    expectedParentRevisionId: null,
    promotionId: "restart-promotion" as never,
    revisionId: "restart-revision" as never,
    entryArtifactId,
    productionProfileArtifactId: profile,
    entry,
    rendererIdentity: {} as unknown as RendererIdentity,
    review: { materialContext: materialContext(entry) },
  } as const;

  const installLedger = () => {
    ledger.createArtifact({ id: source, kind: "source_extraction", schemaVersion: "source-extraction/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "source" }, metadata: { revisionId: revision.revisionId, inputRevision: revision as unknown as JsonObject } });
    ledger.createArtifact({ id: seed, kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "initial" }, parents: [{ artifactId: source, relation: "input_binding" }], metadata: { articleId: "article", revisionId: "seed-revision" } });
    ledger.createArtifact({ id: profile, kind: "article_measurement_profile", schemaVersion: "article-measurement-profile/1", mediaType: "application/json", origin: "imported", payload: { kind: "json", value: { inputs: [{ artifactId: seed }] } }, parents: [{ artifactId: seed, relation: "profile_manuscript" }] });
    ledger.createRun({ runId: restartRunId, articleExecutionId: restartExecutionId, articleId: "article", editionId: "004", workflowVersion: "restart-test/1", loopsRunId: restartRunId, manuscriptArtifactId: seed, args: args as unknown as JsonObject });
    ledger.createArtifact({ id: entryArtifactId, kind: "article_workflow_entry", schemaVersion: "loops-article-entry-input/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: entry as unknown as JsonObject }, parents: [{ artifactId: source, relation: "entry_input" }], metadata: { articleId: "article" }, runId: restartRunId });
  };
  installLedger();

  const portsForCurrentLedger = (): ArticleWorkflowPorts => {
    const runner = ledger.createArticleAttemptRunner();
    return {
      ledger,
      runReviewPanel: async (input) => {
        panelCalls += 1;
        const resultId = id(`restart-review-result-${input.rewriteOrdinal}`);
        const measurementId = id(`restart-measurement-${input.rewriteOrdinal}`);
        const findings = input.rewriteOrdinal === 0
          ? [{ localId: "fix", severity: "must_fix" as const, scope: { kind: "document" as const }, problem: "fix", requestedOutcome: "fix", evidenceArtifactIds: [input.manuscriptArtifactId] }]
          : [];
        ledger.createArtifact({ id: resultId, kind: "article_review_result", schemaVersion: "article-review-result/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: { schemaVersion: "article-review-result/1", reviewerId: "restart-reviewer", manuscriptArtifactId: input.manuscriptArtifactId, assessment: findings.length > 0 ? "findings" : "pass", findings } }, parents: [{ artifactId: input.manuscriptArtifactId, relation: "review_input" }], runId: restartRunId });
        ledger.createArtifact({ id: measurementId, kind: "article_measurement", schemaVersion: "article-measurement/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "article-measurement/1", articleId: "article", manuscriptArtifactId: input.manuscriptArtifactId, pageCount: 1, maximumReaderPages: 7, fits: true, openerFits: true, layouts: [], inputArtifactIds: [input.manuscriptArtifactId] } }, parents: [{ artifactId: input.manuscriptArtifactId, relation: "measurement_input" }], runId: restartRunId });
        const checks: ArticleReviewCheckResult[] = [
          { schemaVersion: "article-review-check-result/2", status: "completed", waveId: "wave", checkId: "evidence", kind: "model_review", key: `restart-review-${input.rewriteOrdinal}`, manuscriptArtifactId: input.manuscriptArtifactId, manuscriptRevisionId: input.manuscriptRevisionId, materialArtifactIds: [input.manuscriptArtifactId], outputArtifactIds: [resultId], resultArtifactId: resultId, reviewerId: "restart-reviewer", assessment: findings.length > 0 ? "findings" : "pass", findings, result: { schemaVersion: "article-review-result/1", reviewerId: "restart-reviewer", manuscriptArtifactId: input.manuscriptArtifactId, assessment: findings.length > 0 ? "findings" : "pass", findings } },
          { schemaVersion: "article-review-check-result/2", status: "completed", waveId: "wave", checkId: "measure_article", kind: "article_measurement", key: `restart-measure-${input.rewriteOrdinal}`, manuscriptArtifactId: input.manuscriptArtifactId, manuscriptRevisionId: input.manuscriptRevisionId, materialArtifactIds: [input.manuscriptArtifactId], outputArtifactIds: [measurementId], resultArtifactId: measurementId, reviewerId: "restart-measure", assessment: "pass", findings: [], result: { schemaVersion: "article-measurement/1", articleId: "article", manuscriptArtifactId: input.manuscriptArtifactId, pageCount: 1, maximumReaderPages: 7, fits: true, openerFits: true, layouts: [], inputArtifactIds: [input.manuscriptArtifactId] } },
        ];
        return { schemaVersion: "article-review-panel/2", runId: restartRunId, articleExecutionId: restartExecutionId, articleId: "article", manuscriptOrdinal: input.rewriteOrdinal ?? 0, manuscriptArtifactId: input.manuscriptArtifactId, manuscriptRevisionId: input.manuscriptRevisionId, checks };
      },
      measureArticle: async ({ articleId, manuscriptArtifactId }) => ({ schemaVersion: "article-measurement/1", articleId, manuscriptArtifactId, pageCount: 1, maximumReaderPages: 7, fits: true, openerFits: true, layouts: [], inputArtifactIds: [manuscriptArtifactId] }),
      runWriter: async (input, context) => await context.step(
        input.operationKey,
        async () => {
          writerAttempts += 1;
          const writerInputArtifactIds = input.revisionContextArtifactId === undefined
            ? [source, input.currentManuscriptArtifactId] as const
            : [source, input.currentManuscriptArtifactId, input.revisionContextArtifactId] as const;
          const parents = writerInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" }));
          const writerContractMetadata = {
            writerExecutionClass: "closed_writer/1",
            writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY,
            writerInputArtifactIds,
            ...(input.revisionContextArtifactId === undefined ? {} : { revisionContextArtifactId: input.revisionContextArtifactId }),
          } as const;
          return await runner.executeModel(writerWorker, { rootRunId: restartRunId, articleExecutionId: restartExecutionId, articleId: "article", operationKey: input.operationKey, manuscriptArtifactId: input.currentManuscriptArtifactId, access: "source_aware", materials: writerMaterials(source, input.currentManuscriptArtifactId) }, async () => ({
            value: { schemaVersion: "article-writer-result/1", manuscript: "rewritten", workingNotes: "notes", dispositions: [], reviewMaterials: [] },
            artifacts: [
              { key: "manuscript", kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "model" as const, payload: { kind: "text" as const, text: "rewritten" }, parents, metadata: { articleId: "article", revisionId: "writer-revision", ...writerContractMetadata } },
              { key: "working-notes", kind: "writer_working_notes", schemaVersion: "writer-working-notes/1", mediaType: "text/plain", origin: "model" as const, payload: { kind: "text" as const, text: "notes" }, parents, metadata: { articleId: "article", ...writerContractMetadata } },
              { key: "finding-dispositions", kind: "writer_finding_dispositions", schemaVersion: "writer-finding-dispositions/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { schemaVersion: "writer-finding-dispositions/1", dispositions: [] } }, parents, metadata: { articleId: "article", ...writerContractMetadata } },
            ],
          }));
        },
        { input: { operationKey: input.operationKey }, retry: { maxAttempts: 1, retryOn: "never" } },
      ),
      requireDecision: (decisionArtifactId) => {
        const request = decisionRequest;
        if (request === undefined) throw new Error("restart test decision was not offered");
        return { id: "restart-decision", runId: restartRunId, offerId: request.offerId, taskArtifactId: request.taskArtifactId, inputArtifactIds: request.inputArtifactIds, principalId: "editor", credentialProfileId: "editor", choice: "accept", rationale: "accept", artifactId: decisionArtifactId, validatorVersion: "article-editor-decision-validator/1", canonicalApprovedFindingIds: [], rewriteBudget: { rewritesUsed: 1, maximumRewrites: 1, remainingRewrites: 0, additionalRewriteBudget: 0, counts: "writer_rewrites_only" }, createdAt: "2026-01-01T00:00:00.000Z" } satisfies LedgerDecision;
      },
      promote: async (input): Promise<ArticleWorkflowResult> => ({
        schemaVersion: "magazine-article-workflow-result/1", runId: restartRunId, articleExecutionId: restartExecutionId, articleId: "article", status: "complete", manuscriptArtifactId: input.request.acceptedArtifactIds[0]!,
        ...(ledger.requireRun(restartRunId).currentRevisionRecordArtifactId === undefined ? {} : { currentRevisionRecordArtifactId: ledger.requireRun(restartRunId).currentRevisionRecordArtifactId }),
        measurementArtifactId: input.measurementArtifactId!, decisionArtifactId: input.request.decisionArtifactIds[0]!,
      }),
    };
  };

  const runWithRuntime = async (store: SQLiteDurableRunStore, ports: ArticleWorkflowPorts) => {
    const runtime = createRuntime({ backend, defaultBackend: backend.name, durable: { store, runId: restartRunId, workflowName: "article-loop-restart", workflowPin: pin, args } });
    const contextFactory = (globals: import("@loops/core").WorkflowGlobals): MagazineWorkflowContext => ({
      durableContext: () => globals.durableContext?.() as never,
      step: async (key, fn, options) => await (globals.step as unknown as (stepKey: string, operation: () => Promise<unknown> | unknown, stepOptions: unknown) => Promise<unknown>)(key, fn, {
        input: options.input,
        ...(options.retry === undefined ? {} : {
          retry: {
            ...options.retry,
            ...(Array.isArray(options.retry.retryOn) ? { retryOn: [...options.retry.retryOn] } : {}),
          },
        }),
      }) as never,
      parallel: async (thunks, options) => await globals.parallel([...thunks], options ?? {}) as never,
      wait: async (key, options) => {
        const request = options.request as unknown as { readonly offerId: string; readonly taskArtifactId: ArtifactId; readonly decisionArtifactId: ArtifactId };
        const task = JSON.parse(Buffer.from(ledger.readArtifact(request.taskArtifactId).bytes).toString("utf8")) as { readonly inputArtifactIds?: readonly ArtifactId[] };
        decisionRequest = { ...request, inputArtifactIds: task.inputArtifactIds ?? [] };
        return await (globals.wait as unknown as (waitKey: string, waitOptions: unknown) => Promise<unknown>)(key, { schema: z.object({ decisionArtifactId: z.string().min(1) }).strict(), request: options.request }) as never;
      },
    });
    return await runtime.run(async (globals) => await runArticleWorkflow(args, contextFactory(globals), ports));
  };

  try {
    loops = new SQLiteDurableRunStore(loopsPath);
    await assert.rejects(runWithRuntime(loops, portsForCurrentLedger()), /suspend|wait|pending|durable/iu);
    const firstInspection = loops.inspectRun(restartRunId)!;
    const firstWait = firstInspection.waits.find((wait) => wait.status === "pending");
    assert.ok(firstWait);
    const firstRun = ledger.requireRun(restartRunId);
    assert.equal(firstRun.currentRevisionRecordArtifactId !== undefined, true);
    const firstRecord = ledger.requireCurrentRevisionRecord(restartRunId);
    assert.equal(JSON.parse(Buffer.from(ledger.readArtifact(firstRecord.id).bytes).toString("utf8")).ordinal, 1);
    const firstPanelCalls = panelCalls;
    loops.close();
    loops = undefined;
    ledger.close();
    ledger = new ArtifactLedger(ledgerPath, { clock: ledgerClock });
    loops = new SQLiteDurableRunStore(loopsPath);
    await assert.rejects(runWithRuntime(loops, portsForCurrentLedger()), /suspend|wait|pending|durable/iu);
    const secondInspection = loops.inspectRun(restartRunId)!;
    const secondWaits = secondInspection.waits.filter((wait) => wait.status === "pending");
    assert.equal(secondWaits.length, 1);
    assert.equal(secondWaits[0]!.waitId, firstWait!.waitId);
    assert.equal(panelCalls, firstPanelCalls);
    assert.equal(ledger.requireRun(restartRunId).currentRevisionRecordArtifactId, firstRun.currentRevisionRecordArtifactId);
    const successor = ledger.requireCurrentRevisionRecord(restartRunId);
    assert.equal(JSON.parse(Buffer.from(ledger.readArtifact(successor.id).bytes).toString("utf8")).ordinal, 1);
    const decisionTask = ledger.listArtifacts(restartRunId).find((artifact) => artifact.kind === "article_decision_request");
    assert.ok(decisionTask);
    assert.ok(decisionRequest);
    loops.answerWait({ runId: restartRunId, waitId: secondWaits[0]!.waitId, answer: { decisionArtifactId: decisionRequest.decisionArtifactId } });
    const completed = await runWithRuntime(loops, portsForCurrentLedger());
    assert.equal((completed as ArticleWorkflowResult).status, "complete");
  } finally {
    loops?.close();
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

function entryInput(source: ArtifactId): LoopsArticleEntryInput {
  const ref = revision;
  return {
    schemaVersion: "loops-article-entry-input/1",
    articleId: "article",
    contentMode: "faithful_synthesis",
    byline: "Source",
    sourceIds: ["source"],
    sourceAuthors: ["Source"],
    brief: "brief",
    maximumReaderPages: 7,
    modelPolicy: { default: { adapter: "test", model: "test" } },
    productionProfile: { schemaVersion: "resolved-article-production-profile/1", profileId: "profile", formatId: "format", profileArtifactId: source, writerPromptArtifactId: source, writerResultContractVersion: "article-writer-result/1", reviewMaterials: [], reviewPlanArtifactId: source, writingRulesArtifactId: source, writingPolicyArtifactIds: [], maximumRewrites: 1 },
    writingRulesArtifactId: source,
    reviewPlan: { schemaVersion: "resolved-article-review-plan/1", reviewPlanArtifactId: source, checks: [{ kind: "model_review", id: "evidence", role: "article_review", promptArtifactId: source, access: "source_aware", authority: "blocking" }, { kind: "article_measurement", id: "measure_article", role: "measure_article", measurementProfileArtifactId: source, maximumReaderPages: 7 }], waves: [{ id: "wave", checkIds: ["evidence", "measure_article"], stopAfter: "never" }] },
    materializedInputs: [{ ref, artifacts: [{ path: "source.md", artifactId: source }] }],
    inputBindings: [{ artifactId: source, revision: ref }],
  };
}

function materialContext(entry: LoopsArticleEntryInput): ArticleMaterialContext {
  return { articleId: entry.articleId, contentMode: entry.contentMode, sourceIds: entry.sourceIds, productionProfile: entry.productionProfile, writingRulesArtifactId: entry.writingRulesArtifactId, reviewPlan: entry.reviewPlan, materializedInputs: entry.materializedInputs, measurementInputArtifactIds: [id("seed-manuscript")] };
}

function writerMaterials(source: ArtifactId, manuscriptArtifactId: ArtifactId): ArticleMaterialSet {
  return {
    schemaVersion: "article-material-set/1",
    articleId: "article",
    role: "writer",
    access: "source_aware",
    manuscriptArtifactId,
    artifacts: [
      { artifactId: source, articleId: "article", classification: "source" },
      { artifactId: manuscriptArtifactId, articleId: "article", classification: "manuscript" },
    ],
    artifactIds: [source, manuscriptArtifactId],
  };
}
