import { createHash } from "node:crypto";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import { DurableStore, type DurablePromotionRequest, type DurablePromotionDependency } from "../durable/index.ts";
import { ArticlePromotionAuthority, DurableStoreArticlePromotionSink } from "../workflow-authority/article-promotion.ts";
import { ArtifactLedger, ArtifactLedgerError } from "../workflow-authority/artifact-ledger.ts";
import { measureArticle } from "../renderer-adapter/article-measurement.ts";
import { PythonRendererAdapter } from "../renderer-adapter/python-renderer.ts";
import type { ArticleMeasurement, ArticleWorkflowPorts, EditorialMeasurement, EditorialReviewExecutionResult, EditorialPromotionResult } from "./internal-types.ts";
import type { MagazineWorkflowEngineOptions } from "../contracts/workflow-run.ts";
import type { ArticleWorkflowResult } from "../contracts/workflow-run.ts";
import { measurementId } from "./article-workflow.ts";
import { readVerifiedRendererIdentity } from "./renderer-identity.ts";
import { runArticleReviewPanel } from "./article-review-panel.ts";
import type { AuthorizedWorker } from "../authority/local-authority.ts";
import { createClosedReviewerExecutor, type ClosedReviewerExecutor } from "../executors/closed-reviewer/runtime.ts";
import { createClosedWriterExecutor, type ClosedWriterExecutor } from "../executors/closed-writer/runtime.ts";
import { readOpenAIAPIKey } from "../executors/closed-writer/credentials.ts";
import { createClosedEditorialWriterExecutor, type ClosedEditorialWriterExecutor } from "../executors/closed-editorial-writer/runtime.ts";
import { createClosedEditorialReviewerExecutor, type ClosedEditorialReviewerExecutor } from "../executors/closed-editorial-reviewer/runtime.ts";
import { createClosedTranslationWriterExecutor, type ClosedTranslationWriterExecutor } from "../executors/closed-translation-writer/runtime.ts";
import { parseEditorialReviewResult } from "../executors/closed-editorial-reviewer/result.ts";
import { RendererExecutor } from "../executors/renderer.ts";
import type { ArtifactId, DecisionView, JsonObject, RunView, WorkOfferView } from "../contracts/index.ts";

/** Included in the fixed Loops source graph. */
export const ARTICLE_RUNTIME_GRAPH = "magazine-article-runtime/1" as const;

export function createArticleWorkflowPorts(options: {
  readonly ledger: ArtifactLedger;
  readonly repositoryRoot: string;
  readonly workRoot: string;
  readonly renderer: NonNullable<MagazineWorkflowEngineOptions["renderer"]>;
  readonly projectRoot: string;
  readonly articleReviewWorkers?: NonNullable<MagazineWorkflowEngineOptions["articleReviewWorkers"]>;
  readonly articleWriter?: MagazineWorkflowEngineOptions["articleWriter"];
  readonly editorialWriter?: MagazineWorkflowEngineOptions["editorialWriter"];
  readonly editorialReviewer?: MagazineWorkflowEngineOptions["editorialReviewer"];
  readonly translationWriter?: MagazineWorkflowEngineOptions["translationWriter"];
  readonly articleReviewCredentials?: NonNullable<MagazineWorkflowEngineOptions["articleReviewCredentials"]>;
}): ArticleWorkflowPorts {
  if (options.renderer === undefined || typeof options.renderer.workDirectory !== "string" || options.renderer.toolchain === undefined) throw new Error("Magazine workflow construction requires a pinned renderer resource");
  const rendererProjectRoot = options.renderer.projectRoot ?? options.projectRoot;
  const adapter = options.renderer.adapter ?? new PythonRendererAdapter(
    rendererProjectRoot,
    options.renderer.timeoutMs,
    () => readVerifiedRendererIdentity(rendererProjectRoot, undefined, options.renderer.toolchain),
    options.renderer.toolchain,
  );
  const editionRenderer = new RendererExecutor(adapter, { id: "editorial-measure-edition", principalId: "editorial-measure-edition", workDirectory: options.renderer.workDirectory });
  const promotionSink = new DurableStoreArticlePromotionSink({
    repositoryRoot: options.repositoryRoot,
    workRoot: options.workRoot,
    git: new GitCliDurableGit(options.repositoryRoot),
    evidence: {
      inspect: async (runId) => options.ledger.durableEvidence(runId),
      readArtifact: async (artifactId) => options.ledger.readArtifact(artifactId),
    },
  });
  const durableStore = new DurableStore({
    repositoryRoot: options.repositoryRoot,
    workRoot: options.workRoot,
    git: new GitCliDurableGit(options.repositoryRoot),
  });
  const promotionEngine = (runId: import("../contracts/index.ts").RunId, decisionArtifactId: ArtifactId, inputArtifactIds: readonly ArtifactId[]) => ({
    inspect: async (): Promise<RunView> => {
      const base = options.ledger.durableEvidence(runId);
      return withMachinePromotionDecision(base, decisionArtifactId, inputArtifactIds);
    },
    readArtifact: async (artifactId: ArtifactId) => options.ledger.readArtifact(artifactId),
  });
  const promotions = new ArticlePromotionAuthority({ ledger: options.ledger, sink: promotionSink });
  const attemptRunner = options.ledger.createArticleAttemptRunner();
  let reviewWorkers: Promise<{
    readonly sourceAwareReviewer: AuthorizedWorker;
    readonly sourceBlindReviewer: AuthorizedWorker;
    readonly measurementTool: AuthorizedWorker;
  }> | undefined;
  let reviewerExecutor: ClosedReviewerExecutor | undefined;
  let writerExecutor: ClosedWriterExecutor | undefined;
  let editorialWriterExecutor: ClosedEditorialWriterExecutor | undefined;
  let editorialReviewerExecutor: ClosedEditorialReviewerExecutor | undefined;
  let translationWriterExecutor: ClosedTranslationWriterExecutor | undefined;
  const ensureReviewWorkers = async () => {
    reviewWorkers ??= (async () => {
      const workers = options.articleReviewWorkers;
      if (workers === undefined) throw new Error("Article review runtime requires three authenticated workers");
      const descriptions = await Promise.all([
        workers.sourceAwareReviewer.describe(),
        workers.sourceBlindReviewer.describe(),
        workers.measurementTool.describe(),
      ]);
      const writerDescription = options.articleWriter === undefined ? undefined : await options.articleWriter.describe();
      const editorialWriterDescription = options.editorialWriter === undefined ? undefined : await options.editorialWriter.describe();
      const editorialReviewerDescription = options.editorialReviewer === undefined ? undefined : await options.editorialReviewer.describe();
      const translationWriterDescription = options.translationWriter === undefined ? undefined : await options.translationWriter.describe();
      const allDescriptions = [
        ...descriptions,
        ...(writerDescription === undefined ? [] : [writerDescription]),
        ...(editorialWriterDescription === undefined ? [] : [editorialWriterDescription]),
        ...(editorialReviewerDescription === undefined ? [] : [editorialReviewerDescription]),
        ...(translationWriterDescription === undefined ? [] : [translationWriterDescription]),
      ];
      const principalIds = allDescriptions.map((description) => description.principalId);
      const credentialIds = allDescriptions.map((description) => description.credentialProfileId);
      if (new Set(principalIds).size !== principalIds.length || new Set(credentialIds).size !== credentialIds.length) {
        throw new Error("Article review workers must use distinct authenticated principal and credential IDs");
      }
      const aware = descriptions[0]!;
      const blind = descriptions[1]!;
      const tool = descriptions[2]!;
      if (aware.authority !== "model" || !exactCapabilities(aware.capabilities, ["source_access", "text_model"])) {
        throw new Error("Source-aware reviewer must be an authenticated model with text_model and source_access only");
      }
      if (blind.authority !== "model" || !exactCapabilities(blind.capabilities, ["source_blind", "text_model"])) {
        throw new Error("Source-blind reviewer must be an authenticated model with text_model and source_blind only");
      }
      if (tool.authority !== "tool" || !exactCapabilities(tool.capabilities, ["subprocess"])) {
        throw new Error("Measurement tool must be an authenticated subprocess worker");
      }
      if (writerDescription !== undefined && (writerDescription.authority !== "model" || !exactCapabilities(writerDescription.capabilities, ["source_access", "text_model"]))) {
        throw new Error("Article writer must be an authenticated source-aware model with text_model and source_access only");
      }
      if (editorialWriterDescription !== undefined && (editorialWriterDescription.authority !== "model" || !exactCapabilities(editorialWriterDescription.capabilities, ["source_blind", "text_model"]))) {
        throw new Error("Editorial writer must be an authenticated source-blind model with text_model and source_blind only");
      }
      if (editorialReviewerDescription !== undefined && (editorialReviewerDescription.authority !== "model" || !exactCapabilities(editorialReviewerDescription.capabilities, ["source_blind", "text_model"]))) {
        throw new Error("Editorial reviewer must be an authenticated source-blind model with text_model and source_blind only");
      }
      if (translationWriterDescription !== undefined && (translationWriterDescription.authority !== "model" || !exactCapabilities(translationWriterDescription.capabilities, ["source_blind", "text_model"]))) {
        throw new Error("Translation writer must be an authenticated source-blind model with text_model and source_blind only");
      }
      return workers;
    })();
    return await reviewWorkers;
  };
  return {
    ledger: options.ledger,
    validateRuntimeResources: async () => {
      await ensureReviewWorkers();
      const credentials = options.articleReviewCredentials;
      if (credentials === undefined) throw new Error("Article review runtime requires a closed reviewer credential resource");
      // Validate the resource before any ledger/run/Loops mutation. Do not
      // retain or log the secret returned by this probe.
      await readOpenAIAPIKey(credentials);
      // The writer shares the owner-private credential resource, but has its
      // own authenticated worker identity when supplied. Existing clean
      // review runs do not need to construct a writer until a rewrite route.
      if (options.articleWriter !== undefined) await options.articleWriter.describe();
      if (options.editorialWriter !== undefined) await options.editorialWriter.describe();
      if (options.editorialReviewer !== undefined) await options.editorialReviewer.describe();
      if (options.translationWriter !== undefined) await options.translationWriter.describe();
    },
    measureArticle: async (input): Promise<ArticleMeasurement> => {
      const result = await measureArticle({
        adapter,
        artifacts: input.artifacts ?? {
          readBytes: async (artifactId) => options.ledger.readArtifact(artifactId).bytes,
          readText: async (artifactId) => Buffer.from(options.ledger.readArtifact(artifactId).bytes).toString("utf8"),
        },
        workDirectory: options.renderer.workDirectory,
        articleId: input.articleId,
        manuscriptArtifactId: input.manuscriptArtifactId,
        measurementProfileArtifactId: input.measurementProfileArtifactId,
        rendererIdentity: input.rendererIdentity,
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
      });
      return result;
    },
    runReviewPanel: async (input, context) => {
      const workers = await ensureReviewWorkers();
      const credentials = options.articleReviewCredentials;
      if (credentials === undefined) throw new Error("Article review runtime requires a closed reviewer credential resource");
      reviewerExecutor ??= createClosedReviewerExecutor({ ledger: options.ledger, credentials, attemptRunner });
      return await runArticleReviewPanel(input, context, {
        ledger: options.ledger,
        attemptRunner,
        reviewerFor: async (check) => check.access === "source_aware" ? workers.sourceAwareReviewer : workers.sourceBlindReviewer,
        toolWorkerFor: async () => workers.measurementTool,
        runModelReview: async ({ claim, check, materials, manuscriptArtifactId, manuscriptRevisionId }) => await reviewerExecutor!.review({
          check: {
            id: check.id,
            role: check.role,
            access: check.access,
            authority: check.authority,
            promptArtifactId: check.promptArtifactId,
            reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
          },
          materials,
          manuscriptArtifactId,
          manuscriptRevisionId,
          claim,
        }),
        measureArticle: async (measurement) => await measureArticle({
          adapter,
          artifacts: measurement.artifacts ?? {
            readBytes: async (artifactId) => options.ledger.readArtifact(artifactId).bytes,
            readText: async (artifactId) => Buffer.from(options.ledger.readArtifact(artifactId).bytes).toString("utf8"),
          },
          workDirectory: options.renderer.workDirectory,
          articleId: measurement.articleId,
          manuscriptArtifactId: measurement.manuscriptArtifactId,
          measurementProfileArtifactId: measurement.measurementProfileArtifactId,
          rendererIdentity: measurement.rendererIdentity,
          ...(measurement.durableContext === undefined ? {} : { durableContext: measurement.durableContext }),
        }),
      });
    },
    runWriter: async (input, context) => {
      const workers = await ensureReviewWorkers();
      const credentials = options.articleReviewCredentials;
      if (credentials === undefined) throw new Error("Article writer runtime requires a closed writer credential resource");
      const worker = options.articleWriter;
      if (worker === undefined) throw new Error("Article route requires an authenticated article writer worker");
      writerExecutor ??= createClosedWriterExecutor({ ledger: options.ledger, credentials });
      const writerRequest = input.mode === "initial"
        ? {
          worker,
          mode: "initial" as const,
          articleExecutionId: input.articleExecutionId,
          operationKey: input.operationKey,
          currentManuscriptArtifactId: input.currentManuscriptArtifactId,
          productionProfileArtifactId: input.productionProfileArtifactId,
        }
        : {
          worker,
          mode: "rewrite" as const,
          articleExecutionId: input.articleExecutionId,
          operationKey: input.operationKey,
          currentManuscriptArtifactId: input.currentManuscriptArtifactId,
          productionProfileArtifactId: input.productionProfileArtifactId,
          revisionContextArtifactId: input.revisionContextArtifactId,
        };
      return await writerExecutor.executeInStep(
        async (key, operation, stepOptions) => await context.step(key, operation, {
          input: stepOptions.input,
          retry: stepOptions.retry,
          label: "article.writer",
        }),
        writerRequest,
      );
    },
    runEditorialWriter: async (input, context) => {
      const worker = options.editorialWriter;
      const credentials = options.articleReviewCredentials;
      if (worker === undefined) throw new Error("Opening editorial requires an authenticated closed editorial writer worker");
      if (credentials === undefined) throw new Error("Opening editorial requires a closed writer credential resource");
      editorialWriterExecutor ??= createClosedEditorialWriterExecutor({ ledger: options.ledger, credentials });
      return await editorialWriterExecutor.executeInStep(
        async (key, operation, stepOptions) => await context.step(key, operation, {
          input: stepOptions.input,
          retry: stepOptions.retry,
          label: "opening.editorial.writer",
        }),
        {
          worker,
          editorialExecutionId: input.editorialExecutionId,
          operationKey: input.operationKey,
          currentManuscriptArtifactId: input.currentManuscriptArtifactId,
          profileArtifactId: input.profileArtifactId,
          articleArtifactIds: input.articleArtifactIds,
          ...(input.mode === undefined ? {} : { mode: input.mode }),
          ...(input.revisionContextArtifactIds === undefined ? {} : { revisionContextArtifactIds: input.revisionContextArtifactIds }),
        },
      );
    },
    measureEditorial: async (input) => {
      if (input.durableContext?.kind !== "step") throw new Error("Opening editorial measurement requires a durable Loops step context");
      const workers = await ensureReviewWorkers();
      const expectedContent = [input.manuscriptArtifactId, ...input.articleArtifactIds];
      if (input.articleArtifactIds.length !== 7 || new Set(expectedContent).size !== 8) throw new Error("Opening editorial measurement requires the editorial and exactly seven articles");
      const manuscript = options.ledger.requireArtifact(input.manuscriptArtifactId);
      if (manuscript.producingRunId === undefined) throw new Error("Editorial measurement manuscript has no producing run");
      const run = options.ledger.requireRun(manuscript.producingRunId);
      const measurementProfile = readEditorialMeasurementProfile(options.ledger, input.measurementProfileArtifactId);
      const contentTargets = [measurementProfile.editorialTargetPath, ...measurementProfile.articleTargets.map((target) => target.targetPath)];
      const targetSet = new Set(contentTargets);
      const effectiveInputs = [
        ...measurementProfile.inputs.filter((item) => !targetSet.has(item.targetPath)),
        ...expectedContent.map((artifactId, index) => ({ artifactId, targetPath: contentTargets[index]! })),
      ];
      const materialIds = [...expectedContent, input.measurementProfileArtifactId] as import("../contracts/index.ts").ArtifactId[];
      return await attemptRunner.executeTool(workers.measurementTool, {
        rootRunId: run.runId,
        articleExecutionId: run.articleExecutionId,
        articleId: "opening",
        operationKey: input.durableContext.key,
        manuscriptArtifactId: input.manuscriptArtifactId,
        access: "tool",
        materials: {
          schemaVersion: "article-material-set/1",
          articleId: "opening",
          role: "measure_article",
          access: "tool",
          manuscriptArtifactId: input.manuscriptArtifactId,
          artifacts: [
            ...expectedContent.map((artifactId) => ({ artifactId, articleId: "opening", classification: "manuscript" as const })),
            { artifactId: input.measurementProfileArtifactId, articleId: "opening", classification: "measurement_profile" as const },
          ],
          artifactIds: materialIds,
        },
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
      } as never, async ({ claim }) => {
        const rendered = await editionRenderer.measureEdition({ attemptId: claim.attemptId, editionPackageId: measurementProfile.editionPackageId, primaryLanguage: "en", publicationName: measurementProfile.publicationName, renderer: measurementProfile.renderer, inputs: effectiveInputs, readBytes: (artifactId) => new Uint8Array(options.ledger.readArtifact(artifactId).bytes), rendererIdentity: measurementProfile.rendererIdentity });
        const layout = rendered.layouts[0]!;
        const chromeFits = layout.editorialPages === 1 && layout.criticResult !== "fail";
        const value: EditorialMeasurement = { schemaVersion: "editorial-measurement/1", operation: "measure_edition", editionId: "004", editorialId: "opening", language: "en", manuscriptArtifactId: input.manuscriptArtifactId, contentArtifactIds: expectedContent, inputArtifactIds: rendered.inputArtifactIds, pageCount: layout.editorialPages, maximumReaderPages: 1, fits: chromeFits, labelVisible: chromeFits, labelFits: chromeFits, titleVisible: chromeFits, titleFits: chromeFits, bylineVisible: chromeFits, bylineFits: chromeFits };
        validateEditorialMeasurement(value, expectedContent);
        return { value, artifacts: [{ key: "result", kind: "editorial_measurement", schemaVersion: "editorial-measurement/1", mediaType: "application/json", origin: "subprocess", payload: { kind: "json", value: value as unknown as JsonObject }, parents: materialIds.map((artifactId) => ({ artifactId, relation: "editorial_measurement_input" })), metadata: { editionId: "004", editorialId: "opening", language: "en", operation: "measure_edition", measurementExecutionClass: "authenticated_measure_edition/1", measurementInputArtifactIds: rendered.inputArtifactIds as unknown as JsonObject, contentArtifactIds: expectedContent as unknown as JsonObject, operationInputDigest: claim.operationInputDigest } }] };
      });
    },
    runEditorialReview: async (input, context): Promise<EditorialReviewExecutionResult> => {
      const worker = options.editorialReviewer;
      const credentials = options.articleReviewCredentials;
      if (worker === undefined) throw new Error("Opening editorial requires an authenticated closed editorial reviewer worker");
      if (credentials === undefined) throw new Error("Opening editorial requires a closed reviewer credential resource");
      const manuscript = options.ledger.requireArtifact(input.manuscriptArtifactId);
      if (manuscript.producingRunId === undefined) throw new Error("Editorial review manuscript has no producing run");
      const run = options.ledger.requireRun(manuscript.producingRunId);
      editorialReviewerExecutor ??= createClosedEditorialReviewerExecutor({ ledger: options.ledger, credentials, attemptRunner });
      const execution = await editorialReviewerExecutor.executeInStep(
        async (key, operation, stepOptions) => await context.step(key, operation, { input: stepOptions.input, retry: stepOptions.retry, label: "opening.editorial.reviewer" }),
        { worker, editorialExecutionId: run.articleExecutionId, operationKey: `editorial.reviewer.${safeIdentity(input.reviewCycleId)}`, manuscriptArtifactId: input.manuscriptArtifactId, reviewPlanArtifactId: input.reviewPlanArtifactId, measurementArtifactId: input.measurementArtifactId, reviewCycleId: input.reviewCycleId },
      );
      if (!execution.selected) return { selected: false, reason: execution.reason, artifacts: execution.artifacts };
      const artifact = execution.artifacts.length === 1 ? execution.artifacts[0] : undefined;
      if (artifact === undefined || artifact.kind !== "editorial_review_result" || artifact.schemaVersion !== "editorial-review-result/1" || artifact.origin !== "model") throw new Error("Editorial reviewer did not select one authenticated result artifact");
      let payload: unknown;
      try { payload = JSON.parse(Buffer.from(options.ledger.readArtifact(artifact.id).bytes).toString("utf8")); } catch (error) { throw new Error("Editorial review result is invalid JSON", { cause: error }); }
      const value = parseEditorialReviewResult(payload);
      if (value.manuscriptArtifactId !== input.manuscriptArtifactId || value.measurementArtifactId !== input.measurementArtifactId || value.reviewPlanArtifactId !== input.reviewPlanArtifactId || value.reviewCycleId !== input.reviewCycleId) throw new Error("Editorial review result is not bound to the exact review input");
      return { selected: true, findings: value.findings, artifacts: execution.artifacts };
    },
    runTranslationWriter: async (input, context) => {
      const worker = options.translationWriter;
      const credentials = options.articleReviewCredentials;
      if (worker === undefined) throw new Error("Spanish translation requires an authenticated closed translation writer");
      if (credentials === undefined) throw new Error("Spanish translation requires a closed writer credential resource");
      translationWriterExecutor ??= createClosedTranslationWriterExecutor({ ledger: options.ledger, credentials });
      return await translationWriterExecutor.executeInStep(
        async (key, operation, stepOptions) => await context.step(key, operation, { input: stepOptions.input, retry: stepOptions.retry, label: "translation.writer" }),
        { worker, ...input },
      );
    },
    promoteTranslation: async (input) => {
      if (input.language !== "es") throw new Error("Spanish translation promotion requires language es");
      if (input.inputArtifactIds[0] !== input.englishArtifactId || input.inputArtifactIds[1] !== input.promptArtifactId) {
        throw new Error("Spanish translation promotion must bind English and prompt artifacts first");
      }
      if (input.inputArtifactBindings.length !== input.inputArtifactIds.length - 1) {
        throw new Error("Spanish translation promotion has an incomplete InputRevision projection");
      }
      if (!sameSequence(input.inputArtifactIds.slice(1), input.inputArtifactBindings.map((binding) => binding.artifactId))) {
        throw new Error("Spanish translation promotion input artifacts disagree with their InputRevision bindings");
      }
      const dependencies: DurablePromotionDependency[] = [
        { kind: "artifact", artifactId: input.englishArtifactId },
        ...input.inputArtifactBindings.map((binding) => ({
          kind: "input_revision" as const,
          artifactId: binding.artifactId,
          revision: binding.revision,
        })),
      ];
      const promotionId = `promotion-translation-${safeIdentity(input.runId)}` as import("../contracts/index.ts").PromotionId;
      const revisionId = stableDurableRevision(`${input.runId}:translation:${input.pieceKind}:${input.pieceId}:${input.manuscriptArtifactId}`);
      const checkpoint = await durableStore.promote(
        promotionEngine(input.runId, input.decisionArtifactId, input.inputArtifactIds),
        {
          schemaVersion: "durable-checkpoint-request/1",
          promotionId,
          revisionId,
          runId: input.runId,
          logicalItem: { kind: input.pieceKind, editionId: "004", logicalId: input.pieceId, language: input.language },
          expectedParentRevisionId: input.expectedParentRevisionId,
          acceptedArtifactIds: [input.manuscriptArtifactId],
          decisionArtifactIds: [input.decisionArtifactId],
          decisionEvidenceArtifactIds: [input.decisionArtifactId],
          inputArtifactIds: [...input.inputArtifactIds],
          inputRevisions: [...input.inputRevisions],
          dependencies,
        },
      );
      return {
        durableRevisionId: checkpoint.result.revisionId,
        manifestDigest: checkpoint.result.manifestDigest,
        gitCommitOid: checkpoint.result.gitCommitOid,
        gitBlobOids: checkpoint.result.gitBlobOids,
      };
    },
    promoteComposition: async (input) => {
      if (input.inputRevisions.length === 0 || input.layoutInputBindings.length === 0) {
        throw new Error("Composition promotion requires exact layout InputRevision pins");
      }
      const layoutArtifactIds = input.layoutInputBindings.map((binding) => binding.artifactId);
      if (!sameSequence(layoutArtifactIds, input.inputArtifactIds.slice(-layoutArtifactIds.length))) {
        throw new Error("Composition layout artifacts are not the exact trailing input projection");
      }
      const layoutStart = input.inputArtifactIds.length - layoutArtifactIds.length;
      const dependencies: DurablePromotionDependency[] = [
        ...input.inputArtifactIds.slice(0, layoutStart).map((artifactId) => ({ kind: "artifact" as const, artifactId })),
        ...input.layoutInputBindings.map((binding) => ({
          kind: "input_revision" as const,
          artifactId: binding.artifactId,
          revision: binding.revision,
        })),
      ];
      const promotionId = `promotion-composition-${safeIdentity(input.runId)}` as import("../contracts/index.ts").PromotionId;
      const checkpoint = await durableStore.promote(
        promotionEngine(input.runId, input.decisionArtifactId, input.inputArtifactIds),
        {
          schemaVersion: "durable-checkpoint-request/1",
          promotionId,
          revisionId: input.revisionId,
          runId: input.runId,
          logicalItem: { kind: "composition", editionId: "004", compositionId: input.compositionId },
          expectedParentRevisionId: null,
          acceptedArtifactIds: [input.compositionArtifactId],
          decisionArtifactIds: [input.decisionArtifactId],
          decisionEvidenceArtifactIds: [input.decisionArtifactId],
          inputArtifactIds: [...input.inputArtifactIds],
          inputRevisions: [...input.inputRevisions],
          dependencies,
        },
      );
      return {
        durableRevisionId: checkpoint.result.revisionId,
        manifestDigest: checkpoint.result.manifestDigest,
        gitCommitOid: checkpoint.result.gitCommitOid,
        gitBlobOids: checkpoint.result.gitBlobOids,
      };
    },
    promoteEditorial: async (input): Promise<EditorialPromotionResult> => {
      const promoted = await promotionSink.promote({ request: input.request, reviewer: input.reviewer, rationale: input.rationale });
      const promotionArtifactId = `art-editorial-promotion-${safeIdentity(input.runId)}` as import("../contracts/index.ts").ArtifactId;
      options.ledger.createArtifact({
        id: promotionArtifactId,
        kind: "editorial_durable_promotion",
        schemaVersion: "editorial-durable-promotion/1",
        mediaType: "application/json",
        origin: "machine",
        payload: { kind: "json", value: { schemaVersion: "editorial-durable-promotion/1", promotionId: input.request.promotionId, durableRevisionId: promoted.revisionId, manifestDigest: promoted.manifestDigest, gitCommitOid: promoted.gitCommitOid, runId: input.runId, editorialId: "opening", manuscriptArtifactId: input.request.acceptedArtifactIds[0]!, measurementArtifactId: input.measurementArtifactId, decisionArtifactId: input.decisionArtifactId, reviewer: input.reviewer, rationale: input.rationale } as unknown as JsonObject },
        parents: [{ artifactId: input.decisionArtifactId, relation: "editorial_decision" }, { artifactId: input.measurementArtifactId, relation: "editorial_measurement" }, ...input.request.acceptedArtifactIds.map((artifactId) => ({ artifactId, relation: "editorial_manuscript" }))],
        metadata: { editionId: "004", editorialId: "opening", promotionId: input.request.promotionId, durableRevisionId: promoted.revisionId },
        runId: input.runId,
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
      });
      return { promotionArtifactId, durableRevisionId: promoted.revisionId, manifestDigest: promoted.manifestDigest, gitCommitOid: promoted.gitCommitOid };
    },
    requireDecision: (artifactId) => {
      const artifact = options.ledger.requireArtifact(artifactId);
      const runId = artifact.producingRunId;
      if (runId === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${artifactId} has no producing run`);
      const decision = options.ledger.getDecisionByArtifactId(runId, artifactId);
      if (decision === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${artifactId} is not current`);
      return decision;
    },
    promote: async (input): Promise<ArticleWorkflowResult> => {
      const promotion = await promotions.promote({
        runId: input.request.runId,
        articleId: input.request.logicalItem.kind === "article" ? input.request.logicalItem.logicalId : "",
        manuscriptArtifactId: input.request.acceptedArtifactIds[0]!,
        measurementArtifactId: input.measurementArtifactId ?? measurementId(input.request.runId),
        decisionArtifactId: input.request.decisionArtifactIds[0]!,
        reviewer: input.reviewer,
        rationale: input.rationale,
        request: input.request,
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
      });
      return {
        schemaVersion: "magazine-article-workflow-result/1",
        runId: input.request.runId,
        articleExecutionId: input.articleExecutionId,
        articleId: input.request.logicalItem.kind === "article" ? input.request.logicalItem.logicalId : "",
        status: "complete",
        manuscriptArtifactId: input.request.acceptedArtifactIds[0]!,
        ...(options.ledger.requireRun(input.request.runId).currentRevisionRecordArtifactId === undefined ? {} : { currentRevisionRecordArtifactId: options.ledger.requireRun(input.request.runId).currentRevisionRecordArtifactId }),
        measurementArtifactId: input.measurementArtifactId ?? measurementId(input.request.runId),
        decisionArtifactId: input.request.decisionArtifactIds[0]!,
        promotionId: promotion.promotionId,
        durableRevisionId: promotion.durableRevisionId,
      };
    },
  };
}

function exactCapabilities(actual: readonly string[], expected: readonly string[]): boolean {
  if (actual.length !== expected.length) return false;
  const wanted = new Set(expected);
  return actual.every((capability) => wanted.has(capability));
}

function safeIdentity(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]/gu, "_");
}

/**
 * Translation and composition are machine-owned checkpoint transitions, not
 * human waits. DurableStore still requires the same answered-offer evidence
 * as every other promotion, so this adapter projects the immutable machine
 * decision artifact into that narrow evidence shape without adding workflow
 * authority to the projection.
 */
function withMachinePromotionDecision(
  base: RunView,
  decisionArtifactId: ArtifactId,
  inputArtifactIds: readonly ArtifactId[],
): RunView {
  const artifact = base.artifacts.find((candidate) => candidate.id === decisionArtifactId);
  if (artifact === undefined || artifact.producingRunId !== base.id) {
    throw new Error(`Durable promotion decision ${decisionArtifactId} is not owned by run ${base.id}`);
  }
  const suffix = `${safeIdentity(base.id)}-${safeIdentity(decisionArtifactId)}`;
  const offer: WorkOfferView = {
    id: `offer-durable-promotion-${suffix}` as WorkOfferView["id"],
    runId: base.id,
    actorId: `actor-durable-promotion-${suffix}` as WorkOfferView["actorId"],
    actorKey: "durable-promotion",
    state: "durable_promotion",
    stateVisitId: `visit-durable-promotion-${suffix}` as WorkOfferView["stateVisitId"],
    role: "editor_decision",
    slot: "durable_promotion",
    subjectArtifactId: decisionArtifactId,
    inputArtifacts: [...inputArtifactIds],
    taskArtifactId: decisionArtifactId,
    contractVersion: "durable-checkpoint/1",
    requirements: { authority: "machine", capabilities: [], minimumAssurance: "local_bearer" },
    allowedWorkerCapabilities: [],
    status: "answered",
    createdAt: artifact.createdAt,
  };
  const decision: DecisionView = {
    id: `decision-durable-promotion-${suffix}` as DecisionView["id"],
    actorId: offer.actorId,
    offerId: offer.id,
    subjectArtifactId: decisionArtifactId,
    principalId: "magazine-durable-promotion",
    choice: "accept",
    authority: "machine",
    artifactId: decisionArtifactId,
    details: {
      schemaVersion: "durable-checkpoint-decision/1",
      inputArtifactIds: [...inputArtifactIds],
      decisionArtifactId,
    } as unknown as JsonObject,
    createdAt: artifact.createdAt,
  };
  return { ...base, offers: [...base.offers, offer], decisions: [...base.decisions, decision] };
}

function stableDurableRevision(identity: string): import("../contracts/index.ts").RevisionId {
  const digest = createHash("sha256").update(identity, "utf8").digest();
  const alphabet = "abcdefghijklmnopqrstuvwxyz234567";
  let accumulator = 0;
  let bits = 0;
  let suffix = "";
  for (const byte of digest) {
    accumulator = (accumulator << 8) | byte;
    bits += 8;
    while (bits >= 5 && suffix.length < 12) {
      bits -= 5;
      suffix += alphabet[(accumulator >>> bits) & 31];
      accumulator &= (1 << bits) - 1;
    }
    if (suffix.length === 12) break;
  }
  return `rev_20260804T000000000Z_${suffix}` as import("../contracts/index.ts").RevisionId;
}

function validateEditorialMeasurement(value: EditorialMeasurement, expectedInputs: readonly string[]): void {
  const chromeFits = value.labelVisible && value.labelFits && value.titleVisible && value.titleFits && value.bylineVisible && value.bylineFits;
  if (value.schemaVersion !== "editorial-measurement/1" || value.operation !== "measure_edition" || value.editionId !== "004" || value.editorialId !== "opening" || value.language !== "en" || value.manuscriptArtifactId !== expectedInputs[0] || !sameSequence(value.contentArtifactIds, expectedInputs) || expectedInputs.some((id) => !value.inputArtifactIds.includes(id as never)) || !Number.isSafeInteger(value.pageCount) || value.pageCount < 0 || value.maximumReaderPages !== 1 || value.fits !== (value.pageCount === 1 && chromeFits)) throw new Error("Full-English measureEdition result does not match the strict opening-editorial contract");
}

function sameSequence(actual: readonly string[], expected: readonly string[]): boolean {
  return actual.length === expected.length && actual.every((value, index) => value === expected[index]);
}

type EditorialMeasurementProfile = {
  readonly editionPackageId: string;
  readonly publicationName: string;
  readonly renderer: "reportlab" | "weasyprint";
  readonly inputs: readonly { readonly artifactId: import("../contracts/index.ts").ArtifactId; readonly targetPath: string }[];
  readonly editorialTargetPath: string;
  readonly articleTargets: readonly { readonly articleId: string; readonly targetPath: string }[];
  readonly rendererIdentity: JsonObject;
};

function readEditorialMeasurementProfile(ledger: ArtifactLedger, artifactId: import("../contracts/index.ts").ArtifactId): EditorialMeasurementProfile {
  const artifact = ledger.requireArtifact(artifactId);
  if (artifact.kind !== "editorial_measurement_profile" || artifact.schemaVersion !== "editorial-measurement-profile/1" || artifact.payloadKind !== "json") throw new Error("Opening editorial measurement profile has the wrong artifact contract");
  let value: unknown;
  try { value = JSON.parse(Buffer.from(ledger.readArtifact(artifactId).bytes).toString("utf8")); } catch (error) { throw new Error("Opening editorial measurement profile is invalid JSON", { cause: error }); }
  if (!record(value) || value.schemaVersion !== "editorial-measurement-profile/1" || value.rendererContractVersion !== "magazine-renderer/1" || value.editionId !== "004" || value.editorialId !== "opening" || value.primaryLanguage !== "en" || typeof value.editionPackageId !== "string" || typeof value.publicationName !== "string" || !["reportlab", "weasyprint"].includes(value.renderer as string) || typeof value.editorialTargetPath !== "string" || !Array.isArray(value.inputs) || !Array.isArray(value.articleTargets) || value.articleTargets.length !== 7 || !record(value.rendererIdentity)) throw new Error("Opening editorial measurement profile does not match the pinned renderer contract");
  const inputs = value.inputs.map((item) => {
    if (!record(item) || typeof item.artifactId !== "string" || typeof item.targetPath !== "string") throw new Error("Opening editorial renderer input is invalid");
    ledger.requireArtifact(item.artifactId as import("../contracts/index.ts").ArtifactId);
    return { artifactId: item.artifactId as import("../contracts/index.ts").ArtifactId, targetPath: item.targetPath };
  });
  const articleTargets = value.articleTargets.map((item) => {
    if (!record(item) || typeof item.articleId !== "string" || typeof item.targetPath !== "string") throw new Error("Opening editorial article target is invalid");
    return { articleId: item.articleId, targetPath: item.targetPath };
  });
  return { editionPackageId: value.editionPackageId, publicationName: value.publicationName, renderer: value.renderer as "reportlab" | "weasyprint", inputs, editorialTargetPath: value.editorialTargetPath, articleTargets, rendererIdentity: value.rendererIdentity as JsonObject };
}

function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }

void ARTICLE_RUNTIME_GRAPH;
