import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import type { ArtifactId, ArtifactSeed, JsonObject, JsonValue, RunId, RevisionId } from "../contracts/index.ts";
import type {
  ArticleDecisionRequest,
  ArticleStartRequest,
  ArticleWorkflowResult,
  ArticleWorkflowView,
  AuthenticatedHuman,
  MagazineWorkflowEngineOptions,
} from "../contracts/workflow-run.ts";
import { newArticleExecutionId, newId } from "../contracts/ids.ts";
import { newRevisionId } from "../durable/revision-id.ts";
import {
  GitCliDurableGit,
  materializeWritePipelineInputs,
  resolveProfileBackedArticleInput,
  resolveWritePipeline,
  type InputRevisionRef,
  type LoopsArticleEntryInput,
} from "../durable/index.ts";
import { articleMaterialContextFromLoops } from "../article-production/materials.ts";
import { ArtifactLedger, ArtifactLedgerError } from "../workflow-authority/artifact-ledger.ts";
import type { HumanDecisionAuthority } from "../workflow-authority/human-decisions.ts";
import { createArticleWorkflowPorts } from "./article-runtime.ts";
import {
  decisionArtifactId,
  articleDecisionWaitKey,
  measurementProfileId,
} from "./article-workflow.ts";
import {
  articleDecisionTaskSchema,
  articleReviewRouteSchema,
  assertValidatedArticleEditorDecision,
  revisionBriefParents,
  revisionBriefSchema,
  type ArticleDecisionTask,
  type ArticleReviewRoute,
  type RevisionBrief,
} from "../article-production/review-cycle.ts";
import type {
  ArticleRuntimeStartArgs,
  MagazineLoopsInspection,
  WorkflowDurableContext,
} from "./internal-types.ts";
import { createDurableLoopsAdapter } from "./loops-adapter.ts";

export class MagazineWorkflowError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "MagazineWorkflowError";
    this.code = code;
  }
}

/** Public magazine seam. It accepts paths/config only and builds all adapters. */
export class MagazineWorkflowEngine {
  readonly #ledger: ArtifactLedger;
  readonly #loops: ReturnType<typeof createDurableLoopsAdapter>;
  readonly #decisions: HumanDecisionAuthority;
  readonly #clock: { readonly now: () => Date };
  readonly #repositoryRootValue: string;
  readonly #validateRuntimeResources: () => Promise<void>;

  constructor(options: MagazineWorkflowEngineOptions) {
    // Capture the default wall clock outside the Loops deterministic runtime.
    // Calling `new Date()` from a workflow body is forbidden by Loops, while
    // the ledger still needs a stable operational timestamp for run facts.
    const defaultNow = new Date();
    this.#clock = options.clock ?? { now: () => defaultNow };
    this.#repositoryRootValue = options.repositoryRoot;
    this.#ledger = new ArtifactLedger(options.databasePath, {
      clock: this.#clock,
      ...(options.attemptClock === undefined ? {} : { attemptClock: options.attemptClock }),
    });
    const ports = createArticleWorkflowPorts({
      ledger: this.#ledger,
      repositoryRoot: options.repositoryRoot,
      workRoot: options.workRoot,
      renderer: options.renderer,
      projectRoot: options.projectRoot,
      ...(options.articleReviewWorkers === undefined ? {} : { articleReviewWorkers: options.articleReviewWorkers }),
      ...(options.articleReviewCredentials === undefined ? {} : { articleReviewCredentials: options.articleReviewCredentials }),
      ...(options.articleWriter === undefined ? {} : { articleWriter: options.articleWriter }),
    });
    this.#validateRuntimeResources = ports.validateRuntimeResources ?? (async () => undefined);
    this.#loops = createDurableLoopsAdapter({
      storePath: options.loopsDatabasePath,
      projectRoot: options.projectRoot,
      toolchain: options.renderer.toolchain,
      runtime: ports,
    });
    this.#decisions = this.#ledger.createHumanDecisionAuthority({ clock: this.#clock });
  }

  #repositoryRoot(): string {
    return this.#repositoryRootValue;
  }

  async startArticle(request: ArticleStartRequest): Promise<ArticleWorkflowView> {
    throw new MagazineWorkflowError("PROFILE_ENTRY_REQUIRED", "startArticle requires a profile-backed write pipeline; use startArticleFromWritePipeline");
  }

  /**
   * Authenticate one article from the committed write pipeline, materialize
   * its exact immutable entry, and launch Loops with that entry as its args.
   */
  async startArticleFromWritePipeline(
    pipelineRef: Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>,
    articleId: string,
    options: {
      readonly runId?: RunId;
      readonly articleExecutionId?: import("../contracts/index.ts").ArticleExecutionId;
      readonly expectedParentRevisionId?: RevisionId | null;
      readonly promotionId?: import("../contracts/index.ts").PromotionId;
      readonly revisionId?: RevisionId;
      readonly language?: string;
    } = {},
  ): Promise<ArticleWorkflowView> {
    // Resolve and authenticate every process-local runtime resource before
    // importing evidence or creating a magazine/Loops run.
    await this.#validateRuntimeResources();
    const git = new GitCliDurableGit(this.#repositoryRoot());
    const resolved = await resolveWritePipeline(this.#repositoryRoot(), pipelineRef, git);
    const materialized = materializeWritePipelineInputs(resolved);
    const article = resolved.document.articles.find((candidate) => candidate.articleId === articleId);
    if (article === undefined) throw new MagazineWorkflowError("ARTICLE_INVALID", `write pipeline has no article ${articleId}`);
    const profile = await resolveProfileBackedArticleInput(materialized, article);
    const language = options.language ?? "en";
    if (language !== "en") throw new MagazineWorkflowError("ARTICLE_INVALID", "profile-backed article launch currently requires the English source language");
    const runId = options.runId ?? newId<RunId>("run");
    const articleExecutionId = options.articleExecutionId ?? newArticleExecutionId();
    const rendererIdentity = await this.#loops.getRendererIdentity();
    // Keep the imported source manuscript distinct from the run-owned
    // accepted manuscript produced by the durable `article.manuscript` step.
    const seedId = `art-input-manuscript-${safeIdentity(runId)}` as ArtifactId;
    const measurementProfileArtifactId = `art-input-measurement-profile-${safeIdentity(runId)}` as ArtifactId;
    const entryArtifactId = `art-article-workflow-entry-${safeIdentity(runId)}` as ArtifactId;
    const productionProfileArtifactId = `art-resolved-production-profile-${safeIdentity(runId)}` as ArtifactId;
    const args: ArticleRuntimeStartArgs = {
      runId,
      articleExecutionId,
      rewriteOrdinal: 0,
      articleId,
      editionId: resolved.document.editionId,
      language,
      logicalItem: { kind: "article", editionId: resolved.document.editionId, logicalId: articleId, language },
      manuscriptArtifactId: seedId,
      measurementProfileArtifactId,
      expectedParentRevisionId: options.expectedParentRevisionId ?? article.parent?.revisionId ?? null,
      promotionId: options.promotionId ?? (`promotion-${safeIdentity(runId)}` as import("../contracts/index.ts").PromotionId),
      revisionId: options.revisionId ?? newRevisionId(this.#clock.now()),
      entryArtifactId,
      productionProfileArtifactId,
      entry: profile.loopsInput,
      rendererIdentity,
      review: {
        materialContext: articleMaterialContextFromLoops(profile.loopsInput, { measurementInputArtifactIds: [seedId] }),
      },
    };

    for (const seed of materialized.artifacts) await this.#importArtifactSeed(seed);
    const sourceText = await this.#sourceText(materialized, article);
    this.#ledger.createArtifact({
      id: seedId,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: sourceText },
      parents: profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => ({ artifactId: artifact.artifactId, relation: "input_binding" }))),
      metadata: {
        articleId,
        materialArtifactIds: profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId)) as unknown as JsonValue,
        revisionId: deterministicManuscriptRevisionId(profile.loopsInput, sourceText, profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId))),
        inputBindings: profile.loopsInput.inputBindings as unknown as readonly JsonObject[],
      },
    });
    const workflowVersion = await this.#loops.getWorkflowVersion();
    this.#ledger.createRun({
      runId,
      articleExecutionId,
      articleId,
      editionId: resolved.document.editionId,
      workflowVersion,
      loopsRunId: runId,
      manuscriptArtifactId: seedId,
      args: args as unknown as JsonObject,
    });
    this.#ledger.createArtifact({
      id: measurementProfileArtifactId,
      kind: "article_measurement_profile",
      schemaVersion: "article-measurement-profile/1",
      mediaType: "application/json",
      origin: "machine",
      payload: {
        kind: "json",
        value: {
          schemaVersion: 1,
          rendererContractVersion: "magazine-renderer/1",
          editionId: resolved.document.editionId,
          primaryLanguage: language,
          publicationName: resolved.document.render.publicationName,
          renderer: resolved.document.render.renderer,
          articleId,
          manuscriptArtifactId: seedId,
          maximumReaderPages: article.maximumReaderPages,
          inputs: [{ artifactId: seedId, targetPath: `articles/${articleId}/manuscript.md` }],
          rendererIdentity,
        } as unknown as JsonObject,
      },
      parents: [{ artifactId: seedId, relation: "profile_manuscript" }],
      runId,
    });
    this.#ledger.createArtifact({
      id: entryArtifactId,
      kind: "article_workflow_entry",
      schemaVersion: "loops-article-entry-input/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: profile.loopsInput as unknown as JsonObject },
      parents: profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => ({ artifactId: artifact.artifactId, relation: "entry_input" }))),
      metadata: { articleId, entrySchemaVersion: profile.loopsInput.schemaVersion },
      runId,
    });
    this.#ledger.createArtifact({
      id: productionProfileArtifactId,
      kind: "resolved_article_production_profile",
      schemaVersion: "resolved-article-production-profile/1",
      mediaType: "application/json",
      origin: "machine",
      payload: {
        kind: "json",
        value: {
          schemaVersion: "resolved-article-production-profile/1",
          entry: profile.loopsInput,
        } as unknown as JsonObject,
      },
      parents: profile.loopsInput.inputBindings.map((binding) => ({ artifactId: binding.artifactId, relation: "input_binding" })),
      metadata: {
        articleId,
        profileArtifactId: productionProfileArtifactId,
        resolvedProfileId: profile.productionProfile.profileId,
      },
      runId,
    });
    try {
      await this.#loops.startArticle(runId, args);
    } catch (error) {
      if (!isSuspension(error)) throw error;
    }
    return await this.inspect(runId);
  }

  async #importArtifactSeed(seed: ArtifactSeed): Promise<void> {
    const payload = seed.payload.kind === "file"
      ? { kind: "bytes" as const, bytes: new Uint8Array(await readFile(seed.payload.path)) }
      : seed.payload.kind === "bytes"
        ? { kind: "bytes" as const, bytes: Buffer.from(seed.payload.dataBase64, "base64") }
        : seed.payload;
    this.#ledger.createArtifact({
      id: seed.id,
      kind: seed.kind,
      schemaVersion: seed.schemaVersion,
      mediaType: seed.mediaType,
      origin: seed.origin,
      payload: payload as never,
      ...(seed.parents === undefined ? {} : { parents: seed.parents }),
      ...(seed.metadata === undefined ? {} : { metadata: seed.metadata }),
    });
  }

  async #sourceText(
    materialized: ReturnType<typeof materializeWritePipelineInputs>,
    article: { readonly sourceIds: readonly string[] },
  ): Promise<string> {
    const wanted = new Set(article.sourceIds);
    const chunks: string[] = [];
    for (const input of materialized.materializedInputs) {
      if (input.ref.kind !== "source_extraction" || !wanted.has(input.ref.logicalId)) continue;
      for (const artifact of [...input.artifacts].sort((left, right) => left.path.localeCompare(right.path))) {
        const read = this.#ledger.readArtifact(artifact.artifactId);
        let text: string;
        try {
          text = new TextDecoder("utf-8", { fatal: true }).decode(read.bytes);
        } catch (error) {
          throw new MagazineWorkflowError("ARTICLE_INVALID", `source extraction file ${artifact.path} is not UTF-8`, { cause: error });
        }
        chunks.push(`--- source ${input.ref.logicalId} ${artifact.path} sha256:${read.artifact.digest} ---\n${text}\n--- end source ${artifact.path} ---`);
      }
    }
    if (chunks.length === 0) throw new MagazineWorkflowError("ARTICLE_INVALID", "profile-backed article has no source extraction payload");
    return chunks.join("\n\n");
  }

  async resume(runId: RunId): Promise<ArticleWorkflowView> {
    this.#ledger.requireRun(runId);
    try {
      await this.#loops.resumeArticle(runId);
    } catch (error) {
      if (!isSuspension(error)) throw error;
    }
    return await this.inspect(runId);
  }

  async inspect(runId: RunId): Promise<ArticleWorkflowView> {
    const loops = await this.#loops.inspect(runId);
    this.#reconcileAnsweredWait(runId, loops);
    const run = this.#ledger.requireRun(runId);
    const root = loops.invocations.find((invocation) => invocation.parentInvocationId === undefined);
    const observation: { workflowPin?: JsonObject; context?: WorkflowDurableContext } = {};
    if (loops.workflowPin !== undefined) observation.workflowPin = loops.workflowPin;
    if (root !== undefined) {
      observation.context = {
        runId,
        invocationId: root.invocationId,
        workflowName: root.workflowName,
        workflowVersion: root.workflowVersion,
        kind: "workflow",
        ...(root.parentInvocationId === undefined ? {} : { parentInvocationId: root.parentInvocationId }),
        ...(root.workflowPin === undefined ? {} : { workflowPin: root.workflowPin }),
      };
    }
    this.#ledger.recordLoopsObservation(runId, observation);
    const offer = this.#ledger.activeOffer(runId);
    const pending = pendingWaitForOffer(loops, offer?.id);
    const result = loops.result;
    const status = statusFromLoops(loops, result);
    const current = this.#ledger.requireRun(runId);
    const args = current.args as unknown as ArticleStartRequest;
    const decision = current.decisionArtifactId === undefined ? undefined : this.#ledger.getDecision(offer?.id ?? "");
    return {
      runId,
      articleExecutionId: current.articleExecutionId,
      articleId: current.articleId,
      editionId: current.editionId ?? "",
      status,
      manuscriptArtifactId: current.manuscriptArtifactId,
      ...(current.currentRevisionRecordArtifactId === undefined ? {} : { currentRevisionRecordArtifactId: current.currentRevisionRecordArtifactId }),
      measurementProfileArtifactId: args.measurementProfileArtifactId,
      ...(current.measurementArtifactId === undefined ? {} : { measurementArtifactId: current.measurementArtifactId }),
      ...(current.decisionArtifactId === undefined ? {} : { decisionArtifactId: current.decisionArtifactId }),
      ...(current.promotionId === undefined ? {} : { promotionId: current.promotionId as never }),
      ...(result?.schemaVersion !== "magazine-article-workflow-result/1" || result.durableRevisionId === undefined ? {} : { durableRevisionId: result.durableRevisionId }),
      ...(offer === undefined ? {} : {
        activeOffer: {
          id: offer.id,
          runId,
          role: "article_decision" as const,
          status: offer.status,
          taskArtifactId: offer.taskArtifactId,
          inputArtifactIds: offer.inputArtifactIds,
          allowedChoices: offer.allowedChoices,
          createdAt: offer.createdAt,
          decisionArtifactId: decisionArtifactId(offer.id),
          ...(pending === undefined ? {} : { waitId: pending.waitId }),
        },
      }),
      artifacts: this.#ledger.listArtifacts(runId).map((artifact) => artifact.id),
      loopsRunId: current.loopsRunId,
      loopsWorkflowVersion: loops.workflowVersion,
      ...(loops.workflowPin === undefined ? {} : { workflowPin: loops.workflowPin }),
      ...(status === "failed" && loops.status === "failed" ? { error: "durable article workflow failed" } : {}),
    };
  }

  async decide(human: AuthenticatedHuman, request: ArticleDecisionRequest): Promise<ArticleWorkflowView> {
    const run = this.#ledger.requireRun(request.runId);
    const loops = await this.#loops.inspect(request.runId);
    this.#reconcileAnsweredWait(request.runId, loops);
    const offer = this.#ledger.requireOffer(request.offerId);
    if (offer.runId !== run.runId) throw new MagazineWorkflowError("OFFER_RUN_MISMATCH", `Offer ${request.offerId} belongs to another run`);
    const existing = this.#ledger.getDecision(request.offerId);
    const pending = pendingWaitForOffer(loops, request.offerId);
    if (pending === undefined) {
      if (existing !== undefined && waitAnsweredForDecision(loops, existing.artifactId)) {
        await assertReplayMatches(existing, request, human);
        return await this.resume(request.runId);
      }
      throw new MagazineWorkflowError("WAIT_NOT_PENDING", `Article decision wait for ${run.runId} is not pending`);
    }
    validateEditorOfferBoundary(this.#ledger, run, offer, request, pending);
    if (existing === undefined) {
      const context = contextForDecision(request.runId, loops, pending);
      const decision = await this.#decisions.decide(human, request, context);
      this.#ledger.recordDecisionArtifact(request.runId, decision.artifactId);
    } else {
      await assertReplayMatches(existing, request, human);
      const context = contextForDecision(request.runId, loops, pending);
      await this.#decisions.decide(human, request, context);
    }
    const decision = this.#ledger.requireDecision(request.offerId);
    try {
      await this.#loops.answerDecision({
        runId: request.runId,
        waitId: pending.waitId,
        decisionArtifactId: decision.artifactId,
      });
      this.#ledger.markOfferAnswered(request.offerId);
    } catch (error) {
      throw new MagazineWorkflowError("DECISION_RECONCILE_RETRYABLE", "Decision was recorded but the Loops wait still needs answering", { cause: error });
    }
    try {
      return await this.resume(request.runId);
    } catch (error) {
      if (isSuspension(error)) return await this.inspect(request.runId);
      throw error;
    }
  }

  close(): void {
    this.#ledger.close();
    this.#loops.close?.();
  }

  #reconcileAnsweredWait(runId: RunId, inspection: MagazineLoopsInspection): void {
    for (const wait of inspection.waits) {
      if (!isArticleDecisionWait(wait) || wait.status !== "answered") continue;
      const request = wait.request;
      const offerId = typeof request === "object" && request !== null && typeof (request as { offerId?: unknown }).offerId === "string"
        ? (request as { offerId: string }).offerId
        : undefined;
      const answer = wait.answer;
      const answeredArtifact = typeof answer === "object" && answer !== null && typeof (answer as { decisionArtifactId?: unknown }).decisionArtifactId === "string"
        ? (answer as { decisionArtifactId: ArtifactId }).decisionArtifactId
        : undefined;
      if (offerId === undefined || answeredArtifact === undefined) {
        throw new MagazineWorkflowError("DECISION_RECONCILIATION_REQUIRED", `Answered Loops wait ${wait.waitId} has no exact offer or decision artifact`);
      }
      const offer = this.#ledger.requireOffer(offerId);
      if (offer.runId !== runId) throw new MagazineWorkflowError("DECISION_RECONCILIATION_REQUIRED", `Answered wait ${wait.waitId} belongs to another run`);
      const decision = this.#ledger.getDecision(offerId);
      if (decision === undefined || decision.artifactId !== answeredArtifact) {
        throw new MagazineWorkflowError("DECISION_RECONCILIATION_REQUIRED", `Answered wait ${wait.waitId} has no matching ledger decision`);
      }
      if (decision.artifactId !== decisionArtifactId(offer.id)) {
        throw new MagazineWorkflowError("DECISION_RECONCILIATION_REQUIRED", `Answered wait ${wait.waitId} names an unexpected decision artifact`);
      }
      const requestFromDecision: ArticleDecisionRequest = {
        runId,
        offerId,
        taskArtifactId: decision.taskArtifactId,
        inputArtifactIds: decision.inputArtifactIds,
        choice: decision.choice,
        rationale: decision.rationale,
        ...(decision.approvedFindingIds === undefined ? {} : { approvedFindingIds: decision.approvedFindingIds }),
        ...(decision.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: decision.additionalRewriteBudget }),
      };
      const run = this.#ledger.requireRun(runId);
      const boundary = validateEditorOfferBoundary(this.#ledger, run, offer, requestFromDecision, wait);
      try {
        assertValidatedArticleEditorDecision(boundary.route, {
          choice: decision.choice,
          ...(decision.approvedFindingIds === undefined ? {} : { approvedFindingIds: decision.approvedFindingIds }),
          ...(decision.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: decision.additionalRewriteBudget }),
          ...(decision.validatorVersion === undefined ? {} : { validatorVersion: decision.validatorVersion }),
          ...(decision.canonicalApprovedFindingIds === undefined ? {} : { canonicalApprovedFindingIds: decision.canonicalApprovedFindingIds }),
          ...(decision.rewriteBudget === undefined ? {} : { rewriteBudget: decision.rewriteBudget }),
        });
        assertDecisionArtifactMatches(this.#ledger, decision);
      } catch (error) {
        throw new MagazineWorkflowError("DECISION_RECONCILIATION_REQUIRED", `Answered wait ${wait.waitId} has an invalid persisted editor decision`, { cause: error });
      }
      this.#ledger.recordDecisionArtifact(runId, decision.artifactId);
      this.#ledger.markOfferAnswered(offerId);
    }
  }
}

function validateStart(request: ArticleStartRequest, ledger: ArtifactLedger): void {
  if (request.articleId.trim().length === 0 || request.editionId.trim().length === 0 || request.language.trim().length === 0) {
    throw new MagazineWorkflowError("ARTICLE_INVALID", "article, edition, and language identities are required");
  }
  if (request.logicalItem.kind !== "article" || request.logicalItem.editionId !== request.editionId || request.logicalItem.logicalId !== request.articleId || request.logicalItem.language !== request.language) {
    throw new MagazineWorkflowError("ARTICLE_INVALID", "article logical item does not match the run identity");
  }
  const manuscript = ledger.getArtifact(request.manuscriptArtifactId);
  const profile = ledger.getArtifact(request.measurementProfileArtifactId);
  if (manuscript === undefined || manuscript.mediaType !== "text/markdown") throw new MagazineWorkflowError("ARTICLE_INVALID", "manuscript artifact must already exist as Markdown");
  if (profile === undefined || profile.kind !== "article_measurement_profile") throw new MagazineWorkflowError("ARTICLE_INVALID", "measurement profile artifact must already exist");
  const inputIds = request.inputBindings.map((binding) => binding.artifactId);
  if (!sameStrings(manuscript.parents.map((parent) => parent.artifactId), inputIds)) throw new MagazineWorkflowError("ARTICLE_INVALID", "input bindings must equal manuscript parents");
  if (new Set(inputIds).size !== inputIds.length || inputIds.length === 0) throw new MagazineWorkflowError("ARTICLE_INVALID", "article input bindings must be unique and non-empty");
  for (const binding of request.inputBindings) {
    const artifact = ledger.requireArtifact(binding.artifactId);
    if (artifact.metadata.revisionId !== binding.revision.revisionId) throw new MagazineWorkflowError("ARTICLE_INVALID", `input ${binding.artifactId} does not carry its exact revision metadata`);
  }
}

function statusFromLoops(loops: MagazineLoopsInspection, result: ArticleWorkflowResult | import("../contracts/workflow-run.ts").ArticleWorkflowRouteResult | undefined): ArticleWorkflowView["status"] {
  if (loops.status === "waiting") return "waiting";
  if (loops.status === "running") return "running";
  if (loops.status === "failed" || loops.status === "canceled") return "failed";
  if (loops.status === "completed") return result?.status === "dropped" ? "dropped" : result?.status === "rewrite_pending" ? "waiting" : "complete";
  return "running";
}

function pendingWaitForOffer(inspection: MagazineLoopsInspection, offerId?: string): MagazineLoopsInspection["waits"][number] | undefined {
  return inspection.waits.find((wait) => {
    if (wait.status !== "pending" || !isArticleDecisionWait(wait)) return false;
    if (offerId === undefined) return true;
    return typeof wait.request === "object" && wait.request !== null && (wait.request as { readonly offerId?: unknown }).offerId === offerId;
  });
}

function waitAnsweredForDecision(inspection: MagazineLoopsInspection, decisionArtifactIdValue: ArtifactId): boolean {
  return inspection.waits.some((wait) => isArticleDecisionWait(wait) && wait.status === "answered" && typeof wait.answer === "object" && wait.answer !== null && (wait.answer as { decisionArtifactId?: unknown }).decisionArtifactId === decisionArtifactIdValue)
    || (inspection.result?.schemaVersion === "magazine-article-workflow-result/1" && inspection.result.decisionArtifactId === decisionArtifactIdValue);
}

function contextForDecision(runId: RunId, inspection: MagazineLoopsInspection, expectedWait?: MagazineLoopsInspection["waits"][number]): import("./internal-types.ts").WorkflowWaitContext {
  const wait = expectedWait ?? pendingWaitForOffer(inspection);
  if (wait === undefined) {
    throw new MagazineWorkflowError("DECISION_PROVENANCE_REQUIRED", `Run ${runId} has no pending decision wait`);
  }
  const invocation = inspection.invocations.find((candidate) => candidate.invocationId === wait.invocationId);
  if (invocation === undefined) {
    throw new MagazineWorkflowError("DECISION_PROVENANCE_REQUIRED", `Pending decision wait ${wait.waitId} has no exact workflow invocation`);
  }
  if (invocation.workflowName.length === 0 || invocation.workflowVersion.length === 0 || wait.callId.length === 0 || wait.waitId.length === 0 || wait.key.length === 0) {
    throw new MagazineWorkflowError("DECISION_PROVENANCE_INVALID", `Pending decision wait ${wait.waitId} has incomplete workflow provenance`);
  }
  return {
    runId,
    invocationId: invocation.invocationId,
    workflowName: invocation.workflowName,
    workflowVersion: invocation.workflowVersion,
    ...(invocation.parentInvocationId === undefined ? {} : { parentInvocationId: invocation.parentInvocationId }),
    ...(invocation.workflowPin === undefined ? {} : { workflowPin: invocation.workflowPin }),
    callId: wait.callId,
    waitId: wait.waitId,
    key: wait.key,
    kind: "wait",
  };
}

function isArticleDecisionWait(wait: MagazineLoopsInspection["waits"][number]): boolean {
  return wait.key === "article.decision" || wait.key.startsWith("article.decision.");
}

type EditorOfferBoundary = {
  readonly task: ArticleDecisionTask;
  readonly brief: RevisionBrief;
  readonly route: ArticleReviewRoute;
  readonly pending: MagazineLoopsInspection["waits"][number];
};

function validateEditorOfferBoundary(
  ledger: ArtifactLedger,
  run: import("../workflow-authority/artifact-ledger.ts").LedgerRun,
  offer: import("../workflow-authority/artifact-ledger.ts").LedgerOffer,
  request: ArticleDecisionRequest,
  pending: MagazineLoopsInspection["waits"][number],
): EditorOfferBoundary {
  const taskArtifact = ledger.requireArtifact(offer.taskArtifactId);
  const task = parseTaskArtifact(ledger, offer.taskArtifactId);
  const briefArtifact = ledger.requireArtifact(task.revisionBriefArtifactId);
  const routeArtifact = ledger.requireArtifact(task.routeArtifactId);
  const brief = parseJsonArtifact(ledger, task.revisionBriefArtifactId, revisionBriefSchema, "revision brief") as RevisionBrief;
  const route = parseJsonArtifact(ledger, task.routeArtifactId, articleReviewRouteSchema, "review route") as ArticleReviewRoute;
  if (taskArtifact.kind !== "article_decision_request" || taskArtifact.schemaVersion !== "article-decision-request/1") {
    throw new MagazineWorkflowError("DECISION_TASK_INVALID", "active decision task has the wrong artifact contract");
  }
  if (briefArtifact.kind !== "article_revision_brief" || routeArtifact.kind !== "article_review_route") {
    throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", "decision task references the wrong brief or route artifact kind");
  }
  if (run.articleExecutionId !== task.articleExecutionId || run.articleId !== task.articleId || run.runId !== task.runId) {
    throw new MagazineWorkflowError("DECISION_TASK_INVALID", "decision task is not bound to the exact article run");
  }
  if (task.expectedDecisionArtifactId !== decisionArtifactId(offer.id)) {
    throw new MagazineWorkflowError("DECISION_TASK_INVALID", "decision task expected decision artifact does not match the offer");
  }
  if (!sameStrings(task.inputArtifactIds, offer.inputArtifactIds) || !sameStrings(task.inputArtifactIds, request.inputArtifactIds)) {
    throw new MagazineWorkflowError("DECISION_INPUT_MISMATCH", "decision task, offer, and answer do not share the exact immutable inputs");
  }
  // The task ID is represented by the ledger key; an answer cannot name a
  // different task and still use this active offer.
  if (request.taskArtifactId !== offer.taskArtifactId) throw new MagazineWorkflowError("DECISION_TASK_INVALID", "answer names a different decision task");
  if (!sameStrings(offer.allowedChoices, task.allowedChoices) || !sameStrings(task.allowedChoices, ["accept", "revise", "drop"])) {
    throw new MagazineWorkflowError("DECISION_CHOICES_INVALID", "decision offer choices are not the canonical editor choices");
  }
  if (route.outcome !== "editor_wait" || !sameStrings(route.allowedChoices, task.allowedChoices)) {
    throw new MagazineWorkflowError("DECISION_ROUTE_INVALID", "decision task does not reference an editor-wait route with the exact choices");
  }
  if (
    brief.articleId !== task.articleId || brief.manuscriptArtifactId !== task.manuscriptArtifactId
    || brief.iterationId !== task.iterationId
    || route.articleId !== brief.articleId || route.manuscriptArtifactId !== brief.manuscriptArtifactId || route.iterationId !== brief.iterationId
    || brief.cycleId !== task.cycleId || route.cycleId !== task.cycleId
    || brief.manuscriptRevisionId !== task.manuscriptRevisionId || route.manuscriptRevisionId !== task.manuscriptRevisionId
    || brief.reviewPlanArtifactId !== task.reviewPlanArtifactId || route.reviewPlanArtifactId !== task.reviewPlanArtifactId
    || brief.rewriteOrdinal !== task.rewriteOrdinal || route.rewriteOrdinal !== task.rewriteOrdinal
  ) {
    throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", "decision task, brief, and route cross-references do not match");
  }
  if (!sameParents(taskArtifact.parents, task.inputArtifactIds, "decision_evidence")) {
    throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", "decision task parents do not equal its canonical immutable inputs");
  }
  if (!sameParents(routeArtifact.parents, [task.revisionBriefArtifactId], "revision_brief")) {
    throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", "review route does not name exactly its revision brief parent");
  }
  if (!sameStrings(briefArtifact.parents.map((parent) => parent.artifactId), revisionBriefParents({ brief }))) {
    throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", "revision brief parents do not match its declared evidence");
  }
  const waitRequest = pending.request;
  if (
    typeof waitRequest !== "object" || waitRequest === null
    || (waitRequest as { readonly offerId?: unknown }).offerId !== offer.id
    || (waitRequest as { readonly taskArtifactId?: unknown }).taskArtifactId !== offer.taskArtifactId
    || (waitRequest as { readonly decisionArtifactId?: unknown }).decisionArtifactId !== task.expectedDecisionArtifactId
    || (waitRequest as { readonly cycleId?: unknown }).cycleId !== task.cycleId
    || pending.key !== articleDecisionWaitKey(task.cycleId)
  ) {
    throw new MagazineWorkflowError("DECISION_PROVENANCE_INVALID", "pending wait is not the exact scoped decision wait for this task");
  }
  if (request.offerId !== offer.id || request.taskArtifactId !== offer.taskArtifactId) {
    throw new MagazineWorkflowError("DECISION_TASK_INVALID", "answer does not name the exact active offer task");
  }
  return { task, brief, route, pending };
}

function parseTaskArtifact(ledger: ArtifactLedger, artifactId: ArtifactId): ArticleDecisionTask {
  const artifact = ledger.requireArtifact(artifactId);
  const value = parseArtifactJson(ledger, artifactId);
  const parsed = articleDecisionTaskSchema.safeParse(value);
  if (!parsed.success) throw new MagazineWorkflowError("DECISION_TASK_INVALID", "article decision task is not a strict article-decision-task/1 payload");
  return parsed.data as unknown as ArticleDecisionTask;
}

function parseJsonArtifact(
  ledger: ArtifactLedger,
  artifactId: ArtifactId,
  schema: { readonly safeParse: (value: unknown) => { readonly success: boolean; readonly data?: unknown } },
  label: string,
): unknown {
  const value = parseArtifactJson(ledger, artifactId);
  const parsed = schema.safeParse(value);
  if (!parsed.success) throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", `${label} does not match its strict schema`);
  return parsed.data;
}

function parseArtifactJson(ledger: ArtifactLedger, artifactId: ArtifactId): unknown {
  const artifact = ledger.requireArtifact(artifactId);
  if (artifact.payloadKind !== "json" || artifact.mediaType !== "application/json") throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", `Artifact ${artifactId} is not canonical JSON evidence`);
  try {
    return JSON.parse(Buffer.from(ledger.readArtifact(artifactId).bytes).toString("utf8")) as unknown;
  } catch (error) {
    throw new MagazineWorkflowError("DECISION_LINEAGE_INVALID", `Artifact ${artifactId} is not valid JSON`, { cause: error });
  }
}

/** Verify that the immutable decision artifact still carries the ledger row's
 * exact validated facts before reconciliation can close the offer. */
function assertDecisionArtifactMatches(
  ledger: ArtifactLedger,
  decision: import("../workflow-authority/artifact-ledger.ts").LedgerDecision,
): void {
  const artifact = ledger.requireArtifact(decision.artifactId);
  if (
    artifact.kind !== "article_human_decision"
    || artifact.schemaVersion !== "article-human-decision/1"
    || artifact.payloadKind !== "json"
    || artifact.mediaType !== "application/json"
    || artifact.producingRunId !== decision.runId
  ) {
    throw new MagazineWorkflowError("DECISION_ARTIFACT_INVALID", "persisted editor decision artifact is not the exact run-owned contract");
  }
  const value = parseArtifactJson(ledger, decision.artifactId);
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new MagazineWorkflowError("DECISION_ARTIFACT_INVALID", "persisted editor decision artifact payload is not an object");
  }
  const payload = value as Record<string, unknown>;
  if (
    payload.offerId !== decision.offerId
    || payload.taskArtifactId !== decision.taskArtifactId
    || !sameStrings(readStringArray(payload.inputArtifactIds), decision.inputArtifactIds)
    || payload.principalId !== decision.principalId
    || payload.credentialProfileId !== decision.credentialProfileId
    || payload.choice !== decision.choice
    || payload.rationale !== decision.rationale
    || JSON.stringify(payload.approvedFindingIds ?? null) !== JSON.stringify(decision.approvedFindingIds ?? null)
    || (payload.additionalRewriteBudget as number | undefined) !== decision.additionalRewriteBudget
    || payload.validatorVersion !== decision.validatorVersion
    || !sameStrings(readStringArray(payload.canonicalApprovedFindingIds), decision.canonicalApprovedFindingIds ?? [])
    || JSON.stringify(payload.rewriteBudget ?? null) !== JSON.stringify(decision.rewriteBudget ?? null)
  ) {
    throw new MagazineWorkflowError("DECISION_ARTIFACT_INVALID", "persisted editor decision artifact does not match its validated ledger decision");
  }
}

function readStringArray(value: unknown): readonly string[] {
  if (!Array.isArray(value) || value.some((candidate) => typeof candidate !== "string")) return [];
  return value as readonly string[];
}

function sameParents(
  actual: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
  expectedIds: readonly ArtifactId[],
  relation: string,
): boolean {
  return actual.length === expectedIds.length && actual.every((parent, index) => parent.artifactId === expectedIds[index] && parent.relation === relation);
}

function pendingDecisionArtifactId(value: unknown): ArtifactId | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  const candidate = (value as { readonly decisionArtifactId?: unknown }).decisionArtifactId;
  return typeof candidate === "string" ? candidate as ArtifactId : undefined;
}

async function assertReplayMatches(
  existing: import("../workflow-authority/artifact-ledger.ts").LedgerDecision,
  request: ArticleDecisionRequest,
  human: AuthenticatedHuman,
): Promise<void> {
  if (existing.runId !== request.runId || existing.offerId !== request.offerId || existing.taskArtifactId !== request.taskArtifactId || !sameStrings(existing.inputArtifactIds, request.inputArtifactIds) || existing.choice !== request.choice || existing.rationale !== request.rationale.trim() || JSON.stringify(existing.approvedFindingIds ?? null) !== JSON.stringify(request.approvedFindingIds ?? null) || existing.additionalRewriteBudget !== request.additionalRewriteBudget) {
    throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${request.offerId} already has a different decision`);
  }
  const description = await human.describe();
  if (description.authority !== "human" || description.grantIds.length === 0 || existing.principalId !== description.principalId || existing.credentialProfileId !== description.credentialProfileId) {
    throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${request.offerId} was answered by another authorized profile`);
  }
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function safeIdentity(value: string): string {
  return value.replace(/[^A-Za-z0-9_.-]/gu, "_").slice(0, 160);
}

function deterministicManuscriptRevisionId(entry: LoopsArticleEntryInput, text: string, materialArtifactIds: readonly ArtifactId[] = []): import("../contracts/index.ts").ManuscriptRevisionId {
  const digest = createHash("sha256").update(JSON.stringify({
    schemaVersion: "manuscript-revision/1",
    articleId: entry.articleId,
    inputBindings: entry.inputBindings,
    materialArtifactIds,
    text,
  }), "utf8").digest("hex");
  return `manuscript-${digest}` as import("../contracts/index.ts").ManuscriptRevisionId;
}

function isSuspension(error: unknown): boolean {
  return typeof error === "object" && error !== null &&
    ((error as { readonly name?: string }).name === "DurableRunSuspendedError" ||
      (error as { readonly code?: string }).code === "DURABLE_RUN_SUSPENDED" ||
      (error as { readonly code?: string }).code === "DURABLE_WAIT_PENDING");
}
