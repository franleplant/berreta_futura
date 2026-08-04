import { createHash } from "node:crypto";
import type { ArtifactId, JsonObject, JsonValue, ManuscriptRevisionId, RunId } from "../contracts/index.ts";
import type {
  ArticleInputBinding,
  ArticleWorkflowResult,
} from "../contracts/workflow-run.ts";
import type { DurableInputBinding, DurablePromotionRequest, InputRevisionRef } from "../durable/types.ts";
import type {
  ArticleRuntimeStartArgs,
  ArticleWorkflowPorts,
  MagazineWorkflowContext,
  WorkflowAttemptContext,
  WorkflowDurableContext,
} from "./internal-types.ts";
import type { ArtifactLedger, ArticleRevisionFinalizeResult } from "../workflow-authority/artifact-ledger.ts";
import { assertRendererIdentity, type RendererIdentity } from "./renderer-identity.ts";
import {
  compileRevisionBrief,
  deriveArticleReviewRoute,
  articleReviewCycleId,
  assertValidatedArticleEditorDecision,
  revisionBriefParents,
  type ArticleReviewRoute,
  type RevisionBrief,
} from "../article-production/review-cycle.ts";
import {
  articleRevisionContextParents,
  articleRevisionRecordParents,
  parseArticleRevisionRecord,
  type ArticleRevisionContext,
  type ArticleRevisionRecord,
  type ArticleRevisionTrigger,
} from "../article-production/revision.ts";

/**
 * The only workflow-owned article state.  A checkpoint is a strict durable
 * value returned by a Loops step or wait; it is never rebuilt from the live
 * ledger projection after a restart.
 */
export type ArticleLoopCheckpoint = {
  readonly schemaVersion: "article-loop-checkpoint/1";
  readonly runId: RunId;
  readonly articleExecutionId: string;
  readonly articleId: string;
  readonly phase: "review" | "waiting" | "rewriting" | "complete" | "dropped";
  readonly ordinal: number;
  readonly rewriteOrdinal: number;
  readonly maximumRewrites: number;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  readonly cycleId?: string;
  readonly measurementProfileArtifactId?: ArtifactId;
  readonly measurementArtifactId?: ArtifactId;
  readonly revisionBriefArtifactId?: ArtifactId;
  readonly routeArtifactId?: ArtifactId;
  readonly offerId?: string;
  readonly taskArtifactId?: ArtifactId;
  readonly decisionArtifactId?: ArtifactId;
  readonly decisionChoice?: "accept" | "revise" | "drop";
  readonly writerOperationKey?: string;
  readonly writerOperationInputDigest?: string;
  readonly writerReviewMaterialArtifacts?: Readonly<Record<string, ArtifactId>>;
};

/** Strict runtime parser for values replayed by Loops. */
export function parseArticleLoopCheckpoint(value: unknown): ArticleLoopCheckpoint {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("article loop checkpoint must be an object");
  const record = value as Record<string, unknown>;
  const allowed = new Set([
    "schemaVersion", "runId", "articleExecutionId", "articleId", "phase", "ordinal", "rewriteOrdinal", "maximumRewrites",
    "manuscriptArtifactId", "manuscriptRevisionId", "revisionRecordArtifactId", "reviewPlanArtifactId", "humanRulingArtifactIds",
    "cycleId", "measurementProfileArtifactId", "measurementArtifactId", "revisionBriefArtifactId", "routeArtifactId", "offerId",
    "taskArtifactId", "decisionArtifactId", "decisionChoice", "writerOperationKey", "writerOperationInputDigest", "writerReviewMaterialArtifacts",
  ]);
  if (Object.keys(record).some((key) => !allowed.has(key))) throw new Error("article loop checkpoint has unknown fields");
  if (record.schemaVersion !== "article-loop-checkpoint/1" || !textValue(record.runId) || !textValue(record.articleExecutionId) || !textValue(record.articleId)) throw new Error("article loop checkpoint identity is invalid");
  if (!new Set(["review", "waiting", "rewriting", "complete", "dropped"]).has(record.phase as string)) throw new Error("article loop checkpoint phase is invalid");
  for (const key of ["ordinal", "rewriteOrdinal", "maximumRewrites"]) {
    if (!Number.isSafeInteger(record[key]) || (record[key] as number) < 0) throw new Error(`article loop checkpoint ${key} is invalid`);
  }
  for (const key of ["manuscriptArtifactId", "manuscriptRevisionId", "revisionRecordArtifactId", "reviewPlanArtifactId"]) {
    if (!textValue(record[key])) throw new Error(`article loop checkpoint ${key} is invalid`);
  }
  if (!Array.isArray(record.humanRulingArtifactIds) || record.humanRulingArtifactIds.some((id) => !textValue(id))) throw new Error("article loop checkpoint human rulings are invalid");
  for (const key of ["cycleId", "measurementProfileArtifactId", "measurementArtifactId", "revisionBriefArtifactId", "routeArtifactId", "offerId", "taskArtifactId", "decisionArtifactId", "writerOperationKey", "writerOperationInputDigest"]) {
    if (record[key] !== undefined && !textValue(record[key])) throw new Error(`article loop checkpoint ${key} is invalid`);
  }
  if (record.decisionChoice !== undefined && !new Set(["accept", "revise", "drop"]).has(record.decisionChoice as string)) throw new Error("article loop checkpoint decision choice is invalid");
  if (record.writerReviewMaterialArtifacts !== undefined) {
    if (typeof record.writerReviewMaterialArtifacts !== "object" || record.writerReviewMaterialArtifacts === null || Array.isArray(record.writerReviewMaterialArtifacts)) throw new Error("article loop checkpoint writer materials are invalid");
    for (const [key, id] of Object.entries(record.writerReviewMaterialArtifacts as Record<string, unknown>)) if (!textValue(key) || !textValue(id)) throw new Error("article loop checkpoint writer materials are invalid");
  }
  return Object.freeze({
    ...record,
    humanRulingArtifactIds: Object.freeze([...(record.humanRulingArtifactIds as ArtifactId[])]),
    ...(record.writerReviewMaterialArtifacts === undefined ? {} : { writerReviewMaterialArtifacts: Object.freeze({ ...(record.writerReviewMaterialArtifacts as Record<string, ArtifactId>) }) }),
  }) as ArticleLoopCheckpoint;
}

function parseArticleRevisionFinalizeResult(value: unknown): ArticleRevisionFinalizeResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("article revision finalization result must be an object");
  const record = value as Record<string, unknown>;
  const required = ["manuscriptArtifactId", "revisionRecordArtifactId", "manuscriptRevisionId", "ordinal", "writerOperationKey", "writerOperationInputDigest", "writerReviewMaterialArtifacts"];
  if (required.some((key) => !Object.prototype.hasOwnProperty.call(record, key))) throw new Error("article revision finalization result is incomplete");
  for (const key of ["manuscriptArtifactId", "revisionRecordArtifactId", "manuscriptRevisionId", "writerOperationKey", "writerOperationInputDigest"]) if (!textValue(record[key])) throw new Error(`article revision finalization result ${key} is invalid`);
  if (!Number.isSafeInteger(record.ordinal) || (record.ordinal as number) < 0) throw new Error("article revision finalization result ordinal is invalid");
  if (typeof record.writerReviewMaterialArtifacts !== "object" || record.writerReviewMaterialArtifacts === null || Array.isArray(record.writerReviewMaterialArtifacts)) throw new Error("article revision finalization result writer materials are invalid");
  for (const [key, id] of Object.entries(record.writerReviewMaterialArtifacts as Record<string, unknown>)) if (!textValue(key) || !textValue(id)) throw new Error("article revision finalization result writer materials are invalid");
  if (record.adopted !== undefined && typeof record.adopted !== "boolean") throw new Error("article revision finalization result adoption flag is invalid");
  return {
    manuscriptArtifactId: record.manuscriptArtifactId as ArtifactId,
    revisionRecordArtifactId: record.revisionRecordArtifactId as ArtifactId,
    manuscriptRevisionId: record.manuscriptRevisionId as ManuscriptRevisionId,
    ordinal: record.ordinal as number,
    writerOperationKey: record.writerOperationKey as string,
    writerOperationInputDigest: record.writerOperationInputDigest as string,
    writerReviewMaterialArtifacts: Object.freeze({ ...(record.writerReviewMaterialArtifacts as Record<string, ArtifactId>) }),
    ...(record.adopted === true ? { adopted: true } : {}),
  };
}

/**
 * Small durable article tracer. Loops owns control flow and lifecycle; this
 * function records immutable magazine facts and policy decisions.
 */
export async function runArticleWorkflow(
  args: ArticleRuntimeStartArgs,
  context: MagazineWorkflowContext,
  ports: ArticleWorkflowPorts,
): Promise<ArticleWorkflowResult> {
  const runIdValue = args.runId ?? context.durableContext?.()?.runId;
  if (runIdValue === undefined) throw new Error("Article workflow requires a durable run identity");
  const runId = runIdValue as RunId;
  if (args.entry.articleId !== args.articleId) throw new Error("Article workflow entry does not match the run article");
  const bindings = [...args.entry.inputBindings];
  const materialArtifactIds = canonicalMaterialArtifactIds(args.entry);
  const inputRevisions = uniqueInputRevisions(bindings.map((binding) => binding.revision));
  const seed = ports.ledger.requireArtifact(args.manuscriptArtifactId);
  if (seed.mediaType !== "text/markdown") {
    throw new Error("Article manuscript seed must be Markdown");
  }
  if (!sameStrings(seed.parents.map((parent) => parent.artifactId), materialArtifactIds)) {
    throw new Error("Article manuscript seed parents do not equal the exact canonical material bindings");
  }
  assertBindingMetadata(ports.ledger, bindings);
  assertCanonicalMaterialMetadata(ports.ledger, args.entry);

  if (ports.runWriter === undefined) throw new Error("Article workflow requires a closed writer for the initial manuscript");
  const productionProfileArtifactId = args.productionProfileArtifactId;
  if (productionProfileArtifactId === undefined) {
    throw new Error("Article workflow requires the exact run-owned resolved production profile artifact");
  }
  const initialOperationKey = "article.writer.initial";
  const initialWriter = await ports.runWriter({
    articleExecutionId: args.articleExecutionId,
    operationKey: initialOperationKey,
    currentManuscriptArtifactId: args.manuscriptArtifactId,
    productionProfileArtifactId,
    mode: "initial",
  }, context);
  if (!initialWriter.selected || initialWriter.artifacts.length === 0) {
    throw new Error(`Writer operation ${initialOperationKey} did not select a durable result`);
  }
  const initialManuscripts = initialWriter.artifacts.filter((artifact) => artifact.kind === "article_manuscript" && artifact.mediaType === "text/markdown");
  if (initialManuscripts.length !== 1) throw new Error(`Writer operation ${initialOperationKey} did not produce exactly one manuscript artifact`);
  const initialWriterOutput = initialManuscripts[0]!;
  const initialWriterExecutionClass = textMetadataString(initialWriterOutput.metadata.writerExecutionClass);
  const initialWriterRuntimeIdentity = jsonObjectMetadata(initialWriterOutput.metadata.writerRuntimeIdentity);
  const initialWriterInputArtifactIds = artifactIdMetadataArray(initialWriterOutput.metadata.writerInputArtifactIds);
  const initialOperationInputDigest = textMetadataString(initialWriterOutput.metadata.operationInputDigest);
  if (initialWriterExecutionClass !== "closed_writer/1" || initialWriterRuntimeIdentity === undefined || initialWriterInputArtifactIds === undefined || initialOperationInputDigest === undefined) {
    throw new Error(`Writer operation ${initialOperationKey} did not persist the exact closed-writer contract`);
  }
  const initialWriterClaimId = initialWriter.claim?.claimId ?? textMetadataString(initialWriterOutput.metadata.claimId);
  const sourceRevision = requireManuscriptRevision(seed, args.manuscriptArtifactId);
  const initialCycleId = articleInitialRevisionCycleId(args.articleExecutionId, sourceRevision);
  const initialText = Buffer.from(ports.ledger.readArtifact(initialWriterOutput.id).bytes).toString("utf8");
  const initialRevisionId = deterministicManuscriptRevisionId(args.articleId, bindings, initialText, materialArtifactIds, {
    articleExecutionId: args.articleExecutionId,
    previousRevisionId: sourceRevision,
    cycleId: initialCycleId,
    rewriteOrdinal: 0,
    ...(initialWriterClaimId === undefined ? {} : { selectedWriterClaimId: initialWriterClaimId }),
    selectedWriterOutputArtifactId: initialWriterOutput.id,
  });
  const initialManuscriptArtifactId = manuscriptArtifactIdForRevision(initialRevisionId);
  const initialRevisionRecordArtifactId = revisionRecordId(initialRevisionId);
  const initialDurableContext = attemptContextFor(context);
  const initialRevisionValue = await context.step(
    "article.revision-finalize.initial",
    () => ports.ledger.finalizeInitialArticleRevision({
        runId,
        articleExecutionId: args.articleExecutionId,
        articleId: args.articleId,
        operationKey: initialOperationKey,
        operationInputDigest: initialOperationInputDigest,
        sourceManuscriptArtifactId: args.manuscriptArtifactId,
        writerArtifactIds: initialWriter.artifacts.map((artifact) => artifact.id),
        manuscriptRevisionId: initialRevisionId,
        manuscriptArtifactId: initialManuscriptArtifactId,
        revisionRecordArtifactId: initialRevisionRecordArtifactId,
        writerExecutionClass: initialWriterExecutionClass,
        writerRuntimeIdentity: initialWriterRuntimeIdentity,
        expectedWriterInputArtifactIds: initialWriterInputArtifactIds,
        declaredWriterReviewMaterials: args.review.materialContext.productionProfile.reviewMaterials,
        ...(initialDurableContext === undefined ? {} : { durableContext: initialDurableContext }),
      }),
    { input: {
      articleExecutionId: args.articleExecutionId,
      operationKey: initialOperationKey,
      operationInputDigest: initialOperationInputDigest,
      sourceManuscriptArtifactId: args.manuscriptArtifactId,
      writerArtifactIds: initialWriter.artifacts.map((artifact) => artifact.id) as unknown as JsonValue,
      manuscriptRevisionId: initialRevisionId,
      manuscriptArtifactId: initialManuscriptArtifactId,
      revisionRecordArtifactId: initialRevisionRecordArtifactId,
      writerExecutionClass: initialWriterExecutionClass,
      writerRuntimeIdentity: initialWriterRuntimeIdentity,
      expectedWriterInputArtifactIds: initialWriterInputArtifactIds as unknown as JsonValue,
      declaredWriterReviewMaterials: args.review.materialContext.productionProfile.reviewMaterials as unknown as JsonValue,
    } },
  );
  const initialRevision = parseArticleRevisionFinalizeResult(initialRevisionValue);
  const acceptedManuscriptArtifactId = initialRevision.manuscriptArtifactId;
  const measurementProfileArtifactId = await context.step(
    "article.measurement-profile",
    async () => {
      const original = ports.ledger.readArtifact(args.measurementProfileArtifactId);
      let value: unknown;
      try {
        value = JSON.parse(Buffer.from(original.bytes).toString("utf8"));
      } catch (error) {
        throw new Error("Article measurement profile is not valid JSON", { cause: error });
      }
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        throw new Error("Article measurement profile must be a JSON object");
      }
      const suppliedIdentity = (value as Record<string, unknown>).rendererIdentity;
      if (suppliedIdentity !== undefined) {
        try {
          assertRendererIdentity(args.rendererIdentity, suppliedIdentity as RendererIdentity, "article measurement profile identity");
        } catch (error) {
          throw new Error(error instanceof Error ? error.message : "article measurement profile identity mismatch");
        }
      }
      const profile: Record<string, unknown> = {
        ...(value as Record<string, unknown>),
        manuscriptArtifactId: acceptedManuscriptArtifactId,
        rendererIdentity: args.rendererIdentity,
      };
      const inputs: unknown[] = Array.isArray(profile.inputs) ? profile.inputs : [];
      profile.inputs = inputs.map((candidate) => {
        if (typeof candidate !== "object" || candidate === null) return candidate;
        const input = { ...(candidate as Record<string, unknown>) };
        if (input.artifactId === args.manuscriptArtifactId) input.artifactId = acceptedManuscriptArtifactId;
        return input;
      });
      ports.ledger.createArtifact({
        id: measurementProfileId(runId),
        kind: "article_measurement_profile",
        schemaVersion: "article-measurement-profile/1",
        mediaType: "application/json",
        origin: "machine",
        payload: { kind: "json", value: profile as unknown as JsonObject },
        parents: [{ artifactId: args.measurementProfileArtifactId, relation: "derived_profile" }, { artifactId: acceptedManuscriptArtifactId, relation: "profile_manuscript" }],
        metadata: {
          articleId: args.articleId,
          manuscriptArtifactId: acceptedManuscriptArtifactId,
          rendererIdentity: args.rendererIdentity as unknown as JsonObject,
        },
        runId,
        ...withContext(context),
      });
      return measurementProfileId(runId);
    },
    { input: { profileArtifactId: args.measurementProfileArtifactId, manuscriptArtifactId: acceptedManuscriptArtifactId } },
  );

  const reviewPlanArtifactId = args.review.materialContext.reviewPlan.reviewPlanArtifactId;
  let state = parseArticleLoopCheckpoint({
    schemaVersion: "article-loop-checkpoint/1",
    runId,
    articleExecutionId: args.articleExecutionId,
    articleId: args.articleId,
    phase: "review",
    ordinal: initialRevision.ordinal,
    rewriteOrdinal: args.rewriteOrdinal ?? initialRevision.ordinal,
    maximumRewrites: args.review.materialContext.productionProfile.maximumRewrites,
    manuscriptArtifactId: initialRevision.manuscriptArtifactId,
    manuscriptRevisionId: initialRevision.manuscriptRevisionId,
    revisionRecordArtifactId: initialRevision.revisionRecordArtifactId,
    reviewPlanArtifactId,
    humanRulingArtifactIds: args.review.materialContext.humanRulingArtifactIds ?? [],
  });

  // Loops replays completed calls after a crash. The loop therefore keeps no
  // authority in process memory: every transition is keyed by the immutable
  // manuscript revision and the persisted route/decision artifacts.
  for (;;) {
    const currentManuscriptArtifactId = state.manuscriptArtifactId;
    const manuscriptRevisionId = state.manuscriptRevisionId;
    const rewriteOrdinal = state.rewriteOrdinal;
    const maximumRewrites = state.maximumRewrites;
    const cumulativeHumanRulingArtifactIds = state.humanRulingArtifactIds;
    const cycleId = articleReviewCycleId({
      articleExecutionId: args.articleExecutionId,
      manuscriptRevisionId,
      reviewPlanArtifactId,
      rewriteOrdinal,
    });
    const cycleMeasurementProfileArtifactId = rewriteOrdinal === 0
      ? measurementProfileArtifactId
      : await ensureCycleMeasurementProfile({
          args,
          runId,
          cycleId,
          sourceManuscriptArtifactId: args.manuscriptArtifactId,
          currentManuscriptArtifactId,
          baseProfileArtifactId: args.measurementProfileArtifactId,
          ports,
          context,
        });
    const materialContext = bindReviewMaterialContext(
      args.review.materialContext,
      cycleMeasurementProfileArtifactId,
      args.manuscriptArtifactId,
      currentManuscriptArtifactId,
      cumulativeHumanRulingArtifactIds,
      state.writerReviewMaterialArtifacts,
    );
    const materialSelection = {
      ...(args.review.materialSelection ?? {}),
      ...(state.writerReviewMaterialArtifacts === undefined ? {} : { writerReviewMaterialArtifacts: state.writerReviewMaterialArtifacts }),
    };
    const reviewPanel = await context.step(
      `article.review-panel.${safeIdentity(cycleId)}`,
      () => ports.runReviewPanel({
        runId,
        articleExecutionId: args.articleExecutionId,
        articleId: args.articleId,
        manuscriptArtifactId: currentManuscriptArtifactId,
        manuscriptRevisionId,
        manuscriptOrdinal: rewriteOrdinal,
        cycleId,
        rewriteOrdinal,
        rendererIdentity: args.rendererIdentity,
        materialContext,
        materialSelection,
        ...(args.review.teaching === undefined ? {} : { teaching: args.review.teaching }),
      }, context),
      { input: {
        runId,
        articleExecutionId: args.articleExecutionId,
        articleId: args.articleId,
        manuscriptArtifactId: currentManuscriptArtifactId,
        manuscriptRevisionId,
        cycleId,
        rewriteOrdinal,
        writerReviewMaterialArtifacts: (state.writerReviewMaterialArtifacts ?? {}) as unknown as JsonObject,
      } },
    );
    assertReviewPanelCheckpoint(reviewPanel, state, cycleId);
    const measurement = reviewPanel.checks.find((check) => check.status === "completed" && check.kind === "article_measurement");
    if (measurement?.resultArtifactId === undefined) throw new Error("Article review panel did not produce a selected measurement artifact");
    const measurementArtifactId = measurement.resultArtifactId;
    ports.ledger.recordMeasurement(runId, measurementArtifactId);
    const iterationId = articleIterationId(cycleId);
    const reviewCycle = await context.step(
      `article.review-routing.${safeIdentity(cycleId)}`,
      () => {
        const brief = compileRevisionBrief({
          articleId: args.articleId,
          iterationId,
          manuscriptArtifactId: currentManuscriptArtifactId,
          manuscriptRevisionId,
          articleExecutionId: args.articleExecutionId,
          reviewPlanArtifactId,
          rewriteOrdinal,
          cycleId,
          reviewPlan: materialContext.reviewPlan,
          reviewResults: reviewPanel.checks,
          measurementArtifactId,
          humanRulings: cumulativeHumanRulingArtifactIds,
        });
        const route = deriveArticleReviewRoute({
          brief,
          reviewPlan: materialContext.reviewPlan,
          reviewResults: reviewPanel.checks,
          rewriteBudget: { rewritesUsed: rewriteOrdinal, maximumRewrites },
        });
        const briefArtifactId = revisionBriefId(cycleId);
        const routeArtifactId = reviewRouteId(cycleId);
        ports.ledger.createArtifact({
          id: briefArtifactId,
          kind: "article_revision_brief",
          schemaVersion: "article-revision-brief/1",
          mediaType: "application/json",
          origin: "machine",
          payload: { kind: "json", value: brief as unknown as JsonValue },
          parents: revisionBriefParents({ brief }).map((artifactId) => ({ artifactId, relation: "revision_brief_input" })),
          metadata: {
            articleId: args.articleId,
            iterationId,
            manuscriptArtifactId: currentManuscriptArtifactId,
            reviewResultArtifactIds: brief.reviewResultArtifactIds as unknown as JsonValue,
            measurementArtifactId,
            reviewOutputArtifactIds: brief.reviewOutputArtifactIds as unknown as JsonValue,
            rewriteOrdinal,
            cycleId,
          },
          runId,
          ...withContext(context),
        });
        ports.ledger.createArtifact({
          id: routeArtifactId,
          kind: "article_review_route",
          schemaVersion: "article-review-route/1",
          mediaType: "application/json",
          origin: "machine",
          payload: { kind: "json", value: route as unknown as JsonValue },
          parents: [{ artifactId: briefArtifactId, relation: "revision_brief" }],
          metadata: {
            articleId: args.articleId,
            iterationId,
            manuscriptArtifactId: currentManuscriptArtifactId,
            revisionBriefArtifactId: briefArtifactId,
            outcome: route.outcome,
            reason: route.reason,
            rewriteOrdinal,
            cycleId,
          },
          runId,
          ...withContext(context),
        });
        return { brief, route, briefArtifactId, routeArtifactId };
      },
      { input: {
        articleId: args.articleId,
        iterationId,
        manuscriptArtifactId: currentManuscriptArtifactId,
        manuscriptRevisionId,
        measurementArtifactId,
        maximumRewrites,
        rewritesUsed: rewriteOrdinal,
        reviewResultArtifactIds: reviewPanel.checks.flatMap((check) => check.resultArtifactId === undefined ? [] : [check.resultArtifactId]),
      } },
    );
    const brief = reviewCycle.brief as RevisionBrief;
    const route = reviewCycle.route as ArticleReviewRoute;
    const revisionBriefArtifactId = reviewCycle.briefArtifactId as ArtifactId;
    const routeArtifactId = reviewCycle.routeArtifactId as ArtifactId;
    state = parseArticleLoopCheckpoint({
      ...state,
      phase: route.outcome === "auto_rewrite" ? "rewriting" : "waiting",
      cycleId,
      measurementProfileArtifactId: cycleMeasurementProfileArtifactId,
      measurementArtifactId,
      revisionBriefArtifactId,
      routeArtifactId,
    });

    if (route.outcome === "auto_rewrite") {
      state = await rewriteManuscript({
        args,
        runId,
        cycleId,
        rewriteOrdinal,
        currentManuscriptArtifactId,
        previousRevisionRecordArtifactId: state.revisionRecordArtifactId,
        revisionBriefArtifactId,
        routeArtifactId,
        trigger: "auto_rewrite",
        humanRulingArtifactIds: cumulativeHumanRulingArtifactIds,
        materialArtifactIds,
        bindings,
        ports,
        context,
        state,
      });
      assertProjectionMatchesCheckpoint(ports.ledger, state);
      continue;
    }

    const taskArtifactId = decisionTaskId(cycleId);
    const offer = offerId(cycleId);
    const decisionArtifact = decisionArtifactId(offer);
    const decisionInputs = canonicalDecisionEvidence({
      manuscriptArtifactId: currentManuscriptArtifactId,
      reviewArtifactIds: [revisionBriefArtifactId, routeArtifactId, ...brief.reviewResultArtifactIds],
      measurementArtifactId,
      measurementProfileArtifactId: cycleMeasurementProfileArtifactId,
      reviewOutputArtifactIds: brief.reviewOutputArtifactIds,
      inputArtifactIds: materialArtifactIds,
    });
    const decisionTask = {
      schemaVersion: "article-decision-task/1" as const,
      runId,
      articleExecutionId: args.articleExecutionId,
      articleId: args.articleId,
      cycleId,
      iterationId,
      manuscriptArtifactId: currentManuscriptArtifactId,
      manuscriptRevisionId,
      reviewPlanArtifactId,
      rewriteOrdinal,
      revisionBriefArtifactId,
      routeArtifactId,
      inputArtifactIds: decisionInputs,
      expectedDecisionArtifactId: decisionArtifact,
      allowedChoices: ["accept", "revise", "drop"] as const,
    };
    const offered = await context.step(
      `article.decision-offer.${safeIdentity(cycleId)}`,
      () => {
        ports.ledger.createArtifact({
          id: taskArtifactId,
          kind: "article_decision_request",
          schemaVersion: "article-decision-request/1",
          mediaType: "application/json",
          origin: "machine",
          payload: { kind: "json", value: decisionTask as unknown as JsonValue },
          parents: decisionInputs.map((artifactId) => ({ artifactId, relation: "decision_evidence" })),
          metadata: {
            articleId: args.articleId,
            cycleId,
            reviewPlanArtifactId,
            manuscriptRevisionId,
            rewriteOrdinal,
            allowedChoices: ["accept", "revise", "drop"],
            decisionArtifactId: decisionArtifact,
            rendererIdentity: args.rendererIdentity as unknown as JsonObject,
          },
          runId,
          ...withContext(context),
        });
        ports.ledger.createOffer({ id: offer, runId, taskArtifactId, inputArtifactIds: decisionInputs, allowedChoices: ["accept", "revise", "drop"] });
        return {
          ...state,
          phase: "waiting" as const,
          offerId: offer,
          taskArtifactId,
        };
      },
      { input: {
        runId,
        articleExecutionId: args.articleExecutionId,
        articleId: args.articleId,
        manuscriptArtifactId: currentManuscriptArtifactId,
        measurementArtifactId,
        measurementProfileArtifactId: cycleMeasurementProfileArtifactId,
        inputArtifactIds: decisionInputs,
        decisionEvidenceArtifactIds: decisionInputs,
        decisionArtifactId: decisionArtifact,
      } },
    );
    state = parseArticleLoopCheckpoint(offered);
    // The initial part of this function may be replaying cached calls from a
    // previous process. Only assert the ledger projection once those calls
    // have rebuilt the local checkpoint up to the durable wait boundary.
    assertProjectionMatchesCheckpoint(ports.ledger, state);

    const answer = await context.wait(articleDecisionWaitKey(cycleId), {
      request: {
        schemaVersion: "magazine-article-decision-request/1",
        runId,
        offerId: offer,
        taskArtifactId,
        decisionArtifactId: decisionArtifact,
        revisionBriefArtifactId,
        routeArtifactId,
        cycleId,
      },
    });
    if (answer.decisionArtifactId !== decisionArtifact) throw new Error("Article decision wait returned a stale decision artifact");
    const decided = await context.step(
      `article.decision.apply.${safeIdentity(cycleId)}`,
      () => {
        const decision = ports.requireDecision(answer.decisionArtifactId);
        if (decision.runId !== runId || decision.offerId !== offer || decision.taskArtifactId !== taskArtifactId || !sameStrings(decision.inputArtifactIds, decisionInputs)) {
          throw new Error("Article decision artifact is not bound to the exact immutable offer");
        }
        assertValidatedArticleEditorDecision(route, {
          choice: decision.choice,
          ...(decision.approvedFindingIds === undefined ? {} : { approvedFindingIds: decision.approvedFindingIds }),
          ...(decision.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: decision.additionalRewriteBudget }),
          ...(decision.validatorVersion === undefined ? {} : { validatorVersion: decision.validatorVersion }),
          ...(decision.canonicalApprovedFindingIds === undefined ? {} : { canonicalApprovedFindingIds: decision.canonicalApprovedFindingIds }),
          ...(decision.rewriteBudget === undefined ? {} : { rewriteBudget: decision.rewriteBudget }),
        });
        return {
          ...state,
          phase: decision.choice === "revise" ? "rewriting" as const : decision.choice === "drop" ? "dropped" as const : "complete" as const,
          decisionArtifactId: decision.artifactId,
          decisionChoice: decision.choice,
          maximumRewrites: state.maximumRewrites + (decision.choice === "revise" ? decision.additionalRewriteBudget ?? 0 : 0),
          humanRulingArtifactIds: decision.choice === "revise" && !state.humanRulingArtifactIds.includes(decision.artifactId)
            ? [...state.humanRulingArtifactIds, decision.artifactId]
            : state.humanRulingArtifactIds,
        };
      },
      { input: {
        ...state,
        decisionArtifactId: decisionArtifact,
        offerId: offer,
        taskArtifactId,
        answer: answer.decisionArtifactId,
      } },
    );
    state = parseArticleLoopCheckpoint(decided);
    const decision = ports.requireDecision(state.decisionArtifactId!);
    if (decision.choice === "drop") {
      assertProjectionMatchesCheckpoint(ports.ledger, state);
      return {
        schemaVersion: "magazine-article-workflow-result/1",
        runId,
        articleExecutionId: args.articleExecutionId,
        articleId: args.articleId,
        status: "dropped",
        manuscriptArtifactId: state.manuscriptArtifactId,
        currentRevisionRecordArtifactId: state.revisionRecordArtifactId,
        measurementArtifactId,
        decisionArtifactId: decision.artifactId,
      };
    }
    if (decision.choice === "revise") {
      state = await rewriteManuscript({
        args,
        runId,
        cycleId,
        rewriteOrdinal,
        currentManuscriptArtifactId,
        previousRevisionRecordArtifactId: state.revisionRecordArtifactId,
        revisionBriefArtifactId,
        routeArtifactId,
        trigger: "editor_revise",
        humanRulingArtifactIds: state.humanRulingArtifactIds,
        editorDecisionArtifactId: decision.artifactId,
        materialArtifactIds,
        bindings,
        ports,
        context,
        state,
      });
      assertProjectionMatchesCheckpoint(ports.ledger, state);
      continue;
    }

    const acceptedManuscript = ports.ledger.requireArtifact(state.manuscriptArtifactId);
    const promotionInputArtifactIds = acceptedManuscript.parents.map((parent) => parent.artifactId);
    const request: DurablePromotionRequest = {
      schemaVersion: "durable-checkpoint-request/1",
      promotionId: requirePromotionId(args, runId),
      revisionId: requireRevisionId(args),
      runId,
      logicalItem: args.logicalItem,
      expectedParentRevisionId: args.expectedParentRevisionId,
      acceptedArtifactIds: [state.manuscriptArtifactId],
      decisionArtifactIds: [decision.artifactId],
      inputRevisions,
      inputArtifactIds: promotionInputArtifactIds,
      decisionEvidenceArtifactIds: decisionInputs,
    };
    const promoted = await context.step(
      `article.promotion.${safeIdentity(cycleId)}`,
      () => ports.promote({
        articleExecutionId: args.articleExecutionId,
        request,
        measurementArtifactId,
        reviewer: decision.principalId,
        rationale: decision.rationale,
        ...withContext(context),
      }),
      { input: request as unknown as JsonObject },
    );
    assertFinalStateMatchesPromotion(state, promoted, ports.ledger);
    return promoted;
  }
}

async function ensureCycleMeasurementProfile(input: {
  readonly args: ArticleRuntimeStartArgs;
  readonly runId: RunId;
  readonly cycleId: string;
  readonly sourceManuscriptArtifactId: ArtifactId;
  readonly currentManuscriptArtifactId: ArtifactId;
  readonly baseProfileArtifactId: ArtifactId;
  readonly ports: ArticleWorkflowPorts;
  readonly context: MagazineWorkflowContext;
}): Promise<ArtifactId> {
  const id = measurementProfileCycleId(input.cycleId);
  return await input.context.step(
    `article.measurement-profile.${safeIdentity(input.cycleId)}`,
    () => {
      const base = input.ports.ledger.readArtifact(input.baseProfileArtifactId);
      let value: unknown;
      try {
        value = JSON.parse(Buffer.from(base.bytes).toString("utf8"));
      } catch (error) {
        throw new Error("Article measurement profile is not valid JSON", { cause: error });
      }
      if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Article measurement profile must be a JSON object");
      const profile: Record<string, unknown> = {
        ...(value as Record<string, unknown>),
        manuscriptArtifactId: input.currentManuscriptArtifactId,
      };
      const values: unknown[] = Array.isArray(profile.inputs) ? profile.inputs : [];
      profile.inputs = values.map((candidate) => {
        if (typeof candidate !== "object" || candidate === null) return candidate;
        const item = { ...(candidate as Record<string, unknown>) };
        if (item.artifactId === input.sourceManuscriptArtifactId) item.artifactId = input.currentManuscriptArtifactId;
        return item;
      });
      input.ports.ledger.createArtifact({
        id,
        kind: "article_measurement_profile",
        schemaVersion: "article-measurement-profile/1",
        mediaType: "application/json",
        origin: "machine",
        payload: { kind: "json", value: profile as unknown as JsonObject },
        parents: [
          { artifactId: input.baseProfileArtifactId, relation: "derived_profile" },
          { artifactId: input.currentManuscriptArtifactId, relation: "profile_manuscript" },
        ],
        metadata: {
          articleId: input.args.articleId,
          manuscriptArtifactId: input.currentManuscriptArtifactId,
          cycleId: input.cycleId,
          rendererIdentity: input.args.rendererIdentity as unknown as JsonObject,
        },
        runId: input.runId,
        ...withContext(input.context),
      });
      return id;
    },
    { input: {
      cycleId: input.cycleId,
      baseProfileArtifactId: input.baseProfileArtifactId,
      manuscriptArtifactId: input.currentManuscriptArtifactId,
    } },
  );
}

async function rewriteManuscript(input: {
  readonly args: ArticleRuntimeStartArgs;
  readonly runId: RunId;
  readonly cycleId: string;
  readonly rewriteOrdinal: number;
  readonly currentManuscriptArtifactId: ArtifactId;
  readonly revisionBriefArtifactId: ArtifactId;
  readonly routeArtifactId: ArtifactId;
  readonly previousRevisionRecordArtifactId: ArtifactId;
  readonly trigger: Exclude<ArticleRevisionTrigger, "initial">;
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  readonly editorDecisionArtifactId?: ArtifactId;
  readonly materialArtifactIds: readonly ArtifactId[];
  readonly bindings: readonly ArticleInputBinding[];
  readonly ports: ArticleWorkflowPorts;
  readonly context: MagazineWorkflowContext;
  readonly state: ArticleLoopCheckpoint;
}): Promise<ArticleLoopCheckpoint> {
  if (input.ports.runWriter === undefined) {
    throw new Error("Article route requires a closed writer, but no writer runtime is configured");
  }
  const productionProfileArtifactId = input.args.productionProfileArtifactId;
  if (productionProfileArtifactId === undefined) {
    throw new Error("Article route requires the exact run-owned resolved production profile artifact");
  }
  const previousRecord = readRevisionRecord(input.ports.ledger, input.previousRevisionRecordArtifactId, input.runId, input.args.articleId);
  const previousRevision = requireManuscriptRevision(input.ports.ledger.requireArtifact(input.currentManuscriptArtifactId), input.currentManuscriptArtifactId);
  const revisionContextRulings = input.editorDecisionArtifactId === undefined
    ? input.humanRulingArtifactIds
    : input.humanRulingArtifactIds.filter((artifactId) => artifactId !== input.editorDecisionArtifactId);
  const revisionContextArtifactId = await input.context.step(
    `article.revision-context.${safeIdentity(input.cycleId)}`,
    () => createRevisionContext({
      args: input.args,
      runId: input.runId,
      cycleId: input.cycleId,
      rewriteOrdinal: input.rewriteOrdinal + 1,
      trigger: input.trigger,
      previousManuscriptArtifactId: input.currentManuscriptArtifactId,
      revisionBriefArtifactId: input.revisionBriefArtifactId,
      routeArtifactId: input.routeArtifactId,
      ...(previousRecord.workingNotesArtifactId === undefined ? {} : { priorWorkingNotesArtifactId: previousRecord.workingNotesArtifactId }),
      ...(previousRecord.findingDispositionsArtifactId === undefined ? {} : { priorFindingDispositionsArtifactId: previousRecord.findingDispositionsArtifactId }),
      priorReviewMaterialArtifactIds: previousRecord.reviewMaterialArtifactIds,
      humanRulingArtifactIds: revisionContextRulings,
      ...(input.editorDecisionArtifactId === undefined ? {} : { editorDecisionArtifactId: input.editorDecisionArtifactId }),
      previousRevisionRecordArtifactId: input.previousRevisionRecordArtifactId,
      ports: input.ports,
      context: input.context,
    }),
    { input: {
      articleExecutionId: input.args.articleExecutionId,
      cycleId: input.cycleId,
      rewriteOrdinal: input.rewriteOrdinal + 1,
      previousManuscriptArtifactId: input.currentManuscriptArtifactId,
      revisionBriefArtifactId: input.revisionBriefArtifactId,
      routeArtifactId: input.routeArtifactId,
      ...(previousRecord.workingNotesArtifactId === undefined ? {} : { priorWorkingNotesArtifactId: previousRecord.workingNotesArtifactId }),
      ...(previousRecord.findingDispositionsArtifactId === undefined ? {} : { priorFindingDispositionsArtifactId: previousRecord.findingDispositionsArtifactId }),
      priorReviewMaterialArtifactIds: previousRecord.reviewMaterialArtifactIds,
      trigger: input.trigger,
      humanRulingArtifactIds: revisionContextRulings as unknown as JsonValue,
      ...(input.editorDecisionArtifactId === undefined ? {} : { editorDecisionArtifactId: input.editorDecisionArtifactId }),
    } },
  );
  const operationKey = `article.writer.${safeIdentity(input.cycleId)}`;
  const execution = await input.ports.runWriter({
    articleExecutionId: input.args.articleExecutionId,
    operationKey,
    currentManuscriptArtifactId: input.currentManuscriptArtifactId,
    productionProfileArtifactId,
    revisionContextArtifactId,
    mode: "rewrite",
  }, input.context);
  if (!execution.selected || execution.artifacts.length === 0) {
    throw new Error(`Writer operation ${operationKey} did not select a durable result`);
  }
  const manuscriptOutputs = execution.artifacts.filter((artifact) => artifact.kind === "article_manuscript" && artifact.mediaType === "text/markdown");
  if (manuscriptOutputs.length !== 1) throw new Error(`Writer operation ${operationKey} did not produce exactly one manuscript artifact`);
  const writerOutput = manuscriptOutputs[0]!;
  const text = Buffer.from(input.ports.ledger.readArtifact(writerOutput.id).bytes).toString("utf8");
  const writerExecutionClass = textMetadataString(writerOutput.metadata.writerExecutionClass);
  const writerRuntimeIdentity = jsonObjectMetadata(writerOutput.metadata.writerRuntimeIdentity);
  const expectedWriterInputArtifactIds = artifactIdMetadataArray(writerOutput.metadata.writerInputArtifactIds);
  if (writerExecutionClass !== "closed_writer/1" || writerRuntimeIdentity === undefined || expectedWriterInputArtifactIds === undefined) {
    throw new Error(`Writer operation ${operationKey} did not persist the exact closed-writer contract`);
  }
  const selectedWriterClaimId = execution.claim?.claimId ?? textMetadataString(writerOutput.metadata.claimId);
  const operationInputDigest = textMetadataString(writerOutput.metadata.operationInputDigest)
    ?? (execution.claim === undefined ? deterministicWriterOperationDigest({
      articleExecutionId: input.args.articleExecutionId,
      operationKey,
      currentManuscriptArtifactId: input.currentManuscriptArtifactId,
      productionProfileArtifactId,
      revisionContextArtifactId,
    }) : undefined);
  if (operationInputDigest === undefined) throw new Error(`Writer operation ${operationKey} did not persist its exact input digest`);
  const revisionId = deterministicManuscriptRevisionId(input.args.articleId, input.bindings, text, input.materialArtifactIds, {
    articleExecutionId: input.args.articleExecutionId,
    previousRevisionId: previousRevision,
    cycleId: input.cycleId,
    rewriteOrdinal: input.rewriteOrdinal + 1,
    ...(selectedWriterClaimId === undefined ? {} : { selectedWriterClaimId }),
    selectedWriterOutputArtifactId: writerOutput.id,
  });
  if (revisionId === previousRevision) throw new Error("Closed writer returned the unchanged manuscript revision");
  const manuscriptArtifactId = manuscriptArtifactIdForRevision(revisionId);
  const recordArtifactId = revisionRecordId(revisionId);
  const writerDurableContext = attemptContextFor(input.context);
  const finalizedValue = await input.context.step(
    `article.revision-finalize.${safeIdentity(input.cycleId)}`,
    () => input.ports.ledger.finalizeArticleRevision({
      runId: input.runId,
      articleExecutionId: input.args.articleExecutionId,
      articleId: input.args.articleId,
      operationKey,
      operationInputDigest,
      previousManuscriptArtifactId: input.currentManuscriptArtifactId,
      previousRevisionRecordArtifactId: input.previousRevisionRecordArtifactId,
      targetOrdinal: input.rewriteOrdinal + 1,
      cycleId: input.cycleId,
      rewriteOrdinal: input.rewriteOrdinal + 1,
      trigger: input.trigger,
      revisionContextArtifactId,
      writerArtifactIds: execution.artifacts.map((artifact) => artifact.id),
      manuscriptRevisionId: revisionId,
      manuscriptArtifactId,
      revisionRecordArtifactId: recordArtifactId,
      humanRulingArtifactIds: input.humanRulingArtifactIds,
      writerExecutionClass,
      writerRuntimeIdentity,
      expectedWriterInputArtifactIds,
      declaredWriterReviewMaterials: input.args.review.materialContext.productionProfile.reviewMaterials,
      ...(writerDurableContext === undefined ? {} : { durableContext: writerDurableContext }),
    }),
    { input: {
      articleExecutionId: input.args.articleExecutionId,
      operationKey,
      operationInputDigest,
      previousManuscriptArtifactId: input.currentManuscriptArtifactId,
      previousRevisionRecordArtifactId: input.previousRevisionRecordArtifactId,
      targetOrdinal: input.rewriteOrdinal + 1,
      cycleId: input.cycleId,
      rewriteOrdinal: input.rewriteOrdinal + 1,
      revisionContextArtifactId,
      writerArtifactIds: execution.artifacts.map((artifact) => artifact.id) as unknown as JsonValue,
      manuscriptArtifactId,
      revisionRecordArtifactId: recordArtifactId,
      humanRulingArtifactIds: input.humanRulingArtifactIds as unknown as JsonValue,
      writerExecutionClass,
      writerRuntimeIdentity,
      expectedWriterInputArtifactIds: expectedWriterInputArtifactIds as unknown as JsonValue,
      declaredWriterReviewMaterials: input.args.review.materialContext.productionProfile.reviewMaterials as unknown as JsonValue,
    } },
  );
  const finalized = parseArticleRevisionFinalizeResult(finalizedValue);
  return parseArticleLoopCheckpoint({
    ...input.state,
    phase: "review",
    ordinal: finalized.ordinal,
    rewriteOrdinal: finalized.ordinal,
    manuscriptArtifactId: finalized.manuscriptArtifactId,
    manuscriptRevisionId: finalized.manuscriptRevisionId,
    revisionRecordArtifactId: finalized.revisionRecordArtifactId,
    cycleId: undefined,
    measurementProfileArtifactId: undefined,
    measurementArtifactId: undefined,
    revisionBriefArtifactId: undefined,
    routeArtifactId: undefined,
    offerId: undefined,
    taskArtifactId: undefined,
    decisionArtifactId: undefined,
    decisionChoice: undefined,
    writerOperationKey: finalized.writerOperationKey,
    writerOperationInputDigest: finalized.writerOperationInputDigest,
    writerReviewMaterialArtifacts: finalized.writerReviewMaterialArtifacts,
  });
}

function createRevisionContext(input: {
  readonly args: ArticleRuntimeStartArgs;
  readonly runId: RunId;
  readonly cycleId: string;
  readonly rewriteOrdinal: number;
  readonly trigger: Exclude<ArticleRevisionTrigger, "initial">;
  readonly previousManuscriptArtifactId: ArtifactId;
  readonly revisionBriefArtifactId: ArtifactId;
  readonly routeArtifactId: ArtifactId;
  readonly priorWorkingNotesArtifactId?: ArtifactId;
  readonly priorFindingDispositionsArtifactId?: ArtifactId;
  readonly priorReviewMaterialArtifactIds?: readonly ArtifactId[];
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  readonly editorDecisionArtifactId?: ArtifactId;
  readonly previousRevisionRecordArtifactId: ArtifactId;
  readonly ports: ArticleWorkflowPorts;
  readonly context: MagazineWorkflowContext;
}): ArtifactId {
  const value: ArticleRevisionContext = {
    schemaVersion: "article-revision-context/1",
    articleExecutionId: input.args.articleExecutionId,
    cycleId: input.cycleId,
    rewriteOrdinal: input.rewriteOrdinal,
    trigger: input.trigger,
    previousManuscriptArtifactId: input.previousManuscriptArtifactId,
    revisionBriefArtifactId: input.revisionBriefArtifactId,
    routeArtifactId: input.routeArtifactId,
    ...(input.priorWorkingNotesArtifactId === undefined ? {} : { priorWorkingNotesArtifactId: input.priorWorkingNotesArtifactId }),
    ...(input.priorFindingDispositionsArtifactId === undefined ? {} : { priorFindingDispositionsArtifactId: input.priorFindingDispositionsArtifactId }),
    priorReviewMaterialArtifactIds: Object.freeze([...(input.priorReviewMaterialArtifactIds ?? [])]),
    humanRulingArtifactIds: Object.freeze([...input.humanRulingArtifactIds]),
    ...(input.editorDecisionArtifactId === undefined ? {} : { editorDecisionArtifactId: input.editorDecisionArtifactId }),
  };
  const artifactId = revisionContextId(input.cycleId);
  input.ports.ledger.createArtifact({
    id: artifactId,
    kind: "article_revision_context",
    schemaVersion: "article-revision-context/1",
    mediaType: "application/json",
    origin: "machine",
    payload: { kind: "json", value: value as unknown as JsonValue },
    parents: articleRevisionContextParents(value),
    metadata: {
      articleId: input.args.articleId,
      articleExecutionId: value.articleExecutionId,
      cycleId: value.cycleId,
      rewriteOrdinal: value.rewriteOrdinal,
      trigger: value.trigger,
      previousRevisionRecordArtifactId: input.previousRevisionRecordArtifactId,
    },
    runId: input.runId,
    ...withContext(input.context),
  });
  return artifactId;
}

/**
 * One content-addressed manuscript identity for every writer path. The
 * ordered immutable input bindings are part of the preimage, so a
 * multi-source manuscript cannot accidentally reuse a single-input revision.
 */
export function deterministicManuscriptRevisionId(
  articleId: string,
  bindings: readonly ArticleInputBinding[],
  text: string,
  materialArtifactIds: readonly ArtifactId[] = [],
  identity?: {
    readonly articleExecutionId: string;
    readonly previousRevisionId: ManuscriptRevisionId;
    readonly cycleId: string;
    readonly rewriteOrdinal: number;
    readonly selectedWriterClaimId?: string;
    readonly selectedWriterOutputArtifactId: ArtifactId;
  },
): ManuscriptRevisionId {
  const value = JSON.stringify({
    schemaVersion: "article-manuscript/1",
    articleId,
    inputBindings: bindings.map((binding) => ({
      artifactId: binding.artifactId,
      revision: binding.revision,
    })),
    materialArtifactIds,
    textDigest: textDigest(text),
    ...(identity === undefined ? {} : {
      articleExecutionId: identity.articleExecutionId,
      previousRevisionId: identity.previousRevisionId,
      cycleId: identity.cycleId,
      rewriteOrdinal: identity.rewriteOrdinal,
      selectedWriterClaimId: identity.selectedWriterClaimId,
      selectedWriterOutputArtifactId: identity.selectedWriterOutputArtifactId,
    }),
  });
  return `manuscript-${createHash("sha256").update(value, "utf8").digest("hex")}` as ManuscriptRevisionId;
}

/** Every materialized payload file, in immutable resolver order. */
export function canonicalMaterialArtifactIds(
  entry: Pick<ArticleRuntimeStartArgs["entry"], "materializedInputs">,
): readonly ArtifactId[] {
  return Object.freeze(entry.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId)));
}

/** Every immutable payload file paired with the exact revision that produced it. */
export function canonicalMaterialBindings(
  entry: Pick<ArticleRuntimeStartArgs["entry"], "materializedInputs">,
): readonly DurableInputBinding[] {
  return Object.freeze(entry.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => ({
    artifactId: artifact.artifactId,
    revision: input.ref,
  }))));
}

function uniqueInputRevisions(values: readonly InputRevisionRef[]): readonly InputRevisionRef[] {
  const seen = new Set<string>();
  return Object.freeze(values.filter((value) => {
    const key = `${value.kind}:${value.editionId ?? ""}:${value.logicalId}:${value.revisionId}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }));
}

/** One ordered evidence list shared by the decision task, offer, and promotion. */
export function canonicalDecisionEvidence(input: {
  readonly manuscriptArtifactId: ArtifactId;
  readonly reviewArtifactIds: readonly ArtifactId[];
  readonly measurementArtifactId: ArtifactId;
  readonly measurementProfileArtifactId?: ArtifactId;
  readonly reviewOutputArtifactIds: readonly ArtifactId[];
  readonly inputArtifactIds: readonly ArtifactId[];
}): readonly ArtifactId[] {
  const values = [
    input.manuscriptArtifactId,
    ...input.reviewArtifactIds,
    ...input.reviewOutputArtifactIds,
    input.measurementArtifactId,
    ...(input.measurementProfileArtifactId === undefined ? [] : [input.measurementProfileArtifactId]),
    ...input.inputArtifactIds,
  ];
  const seen = new Set<ArtifactId>();
  return Object.freeze(values.filter((artifactId) => {
    if (seen.has(artifactId)) return false;
    seen.add(artifactId);
    return true;
  }));
}

export function manuscriptId(runId: RunId): ArtifactId {
  return `art-manuscript-${safeIdentity(runId)}` as ArtifactId;
}

export function measurementProfileId(runId: RunId): ArtifactId {
  return `art-measurement-profile-${safeIdentity(runId)}` as ArtifactId;
}

export function measurementProfileCycleId(cycleId: string): ArtifactId {
  return `art-measurement-profile-${safeIdentity(cycleId)}` as ArtifactId;
}

function articleInitialRevisionCycleId(articleExecutionId: string, sourceRevisionId: ManuscriptRevisionId): string {
  return `article-initial-${safeIdentity(articleExecutionId)}-${safeIdentity(sourceRevisionId)}`;
}

export function manuscriptArtifactIdForRevision(revisionId: ManuscriptRevisionId): ArtifactId {
  return `art-manuscript-${safeIdentity(revisionId)}` as ArtifactId;
}

export function revisionRecordId(revisionId: ManuscriptRevisionId): ArtifactId {
  return `art-revision-record-${safeIdentity(revisionId)}` as ArtifactId;
}

/** Alias kept explicit for ID-only writer callers. */
export function revisionRecordArtifactId(revisionId: ManuscriptRevisionId): ArtifactId {
  return revisionRecordId(revisionId);
}

export function revisionContextId(cycleId: string): ArtifactId {
  return `art-revision-context-${safeIdentity(cycleId)}` as ArtifactId;
}

export function revisionContextArtifactId(cycleId: string): ArtifactId {
  return revisionContextId(cycleId);
}

export function revisionBriefId(cycleId: string): ArtifactId {
  return `art-revision-brief-${safeIdentity(cycleId)}` as ArtifactId;
}

export function reviewRouteId(cycleId: string): ArtifactId {
  return `art-review-route-${safeIdentity(cycleId)}` as ArtifactId;
}

export function measurementId(runId: RunId): ArtifactId {
  return `art-measurement-${safeIdentity(runId)}` as ArtifactId;
}

export function decisionTaskId(cycleId: string): ArtifactId {
  return `art-decision-task-${safeIdentity(cycleId)}` as ArtifactId;
}

export function offerId(cycleId: string): string {
  return `offer-article-decision-${safeIdentity(cycleId)}`;
}

export function decisionArtifactId(offer: string): ArtifactId {
  return `art-decision-${safeIdentity(offer)}` as ArtifactId;
}

function articleIterationId(cycleId: string): string {
  return `iteration-${safeIdentity(cycleId)}`;
}

export function articleDecisionWaitKey(cycleId: string): string {
  return `article.decision.${safeIdentity(cycleId)}`;
}

function assertBindingMetadata(ledger: ArtifactLedger, bindings: readonly ArticleInputBinding[]): void {
  if (bindings.length === 0) throw new Error("Article workflow requires at least one input binding");
  const ids = new Set<string>();
  for (const binding of bindings) {
    if (ids.has(binding.artifactId)) throw new Error("Article input bindings must be unique");
    ids.add(binding.artifactId);
    const artifact = ledger.requireArtifact(binding.artifactId);
    const revisionId = artifact.metadata.revisionId;
    if (revisionId !== binding.revision.revisionId) {
      throw new Error(`Article input ${binding.artifactId} does not carry the bound revision metadata`);
    }
  }
}

function assertCanonicalMaterialMetadata(
  ledger: ArtifactLedger,
  entry: Pick<ArticleRuntimeStartArgs["entry"], "materializedInputs">,
): void {
  for (const input of entry.materializedInputs) {
    for (const material of input.artifacts) {
      const artifact = ledger.requireArtifact(material.artifactId);
      if (artifact.metadata.revisionId !== input.ref.revisionId ||
          JSON.stringify(artifact.metadata.inputRevision ?? null) !== JSON.stringify(input.ref)) {
        throw new Error(`Article material ${material.artifactId} does not carry its exact immutable revision metadata`);
      }
    }
  }
}

/** Read-only projection check. It can fail a transition, but never supplies
 * state used to recover one after a Loops restart. */
function assertProjectionMatchesCheckpoint(ledger: ArtifactLedger, state: ArticleLoopCheckpoint): void {
  const run = ledger.requireRun(state.runId);
  if (run.articleExecutionId !== state.articleExecutionId || run.articleId !== state.articleId || run.manuscriptArtifactId !== state.manuscriptArtifactId || run.currentRevisionRecordArtifactId !== state.revisionRecordArtifactId) {
    throw new Error("Article ledger projection disagrees with the durable loop checkpoint");
  }
}

function assertReviewPanelCheckpoint(
  panel: { readonly manuscriptArtifactId: ArtifactId; readonly manuscriptRevisionId: ManuscriptRevisionId; readonly articleExecutionId: string; readonly articleId: string },
  state: ArticleLoopCheckpoint,
  cycleId: string,
): void {
  if (panel.articleExecutionId !== state.articleExecutionId || panel.articleId !== state.articleId || panel.manuscriptArtifactId !== state.manuscriptArtifactId || panel.manuscriptRevisionId !== state.manuscriptRevisionId || cycleId.trim().length === 0) {
    throw new Error("Article review panel did not return the exact durable checkpoint predecessor");
  }
}

function assertFinalStateMatchesPromotion(
  state: ArticleLoopCheckpoint,
  result: ArticleWorkflowResult,
  ledger: ArtifactLedger,
): void {
  if (result.runId !== state.runId || result.articleExecutionId !== state.articleExecutionId || result.articleId !== state.articleId || result.manuscriptArtifactId !== state.manuscriptArtifactId || (result.currentRevisionRecordArtifactId !== undefined && result.currentRevisionRecordArtifactId !== state.revisionRecordArtifactId) || result.decisionArtifactId !== state.decisionArtifactId) {
    throw new Error("Article promotion result does not agree with the exact durable final checkpoint");
  }
  const run = ledger.requireRun(state.runId);
  if (run.manuscriptArtifactId !== state.manuscriptArtifactId || run.currentRevisionRecordArtifactId !== state.revisionRecordArtifactId || (run.decisionArtifactId !== undefined && run.decisionArtifactId !== state.decisionArtifactId)) {
    throw new Error("Article promotion projection does not agree with the exact durable final checkpoint");
  }
}

function requirePromotionId(args: ArticleRuntimeStartArgs, runId: RunId): import("../contracts/index.ts").PromotionId {
  return args.promotionId ?? (`promotion-${safeIdentity(runId)}` as import("../contracts/index.ts").PromotionId);
}

function requireRevisionId(args: ArticleRuntimeStartArgs): import("../contracts/index.ts").RevisionId {
  return args.revisionId;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function sameParents(
  left: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
  right: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
): boolean {
  return left.length === right.length && left.every((parent, index) => {
    const expected = right[index];
    return expected !== undefined && expected.artifactId === parent.artifactId && expected.relation === parent.relation;
  });
}

function withContext(context: MagazineWorkflowContext): { readonly durableContext: WorkflowDurableContext } | Record<string, never> {
  const durableContext = context.durableContext?.();
  return durableContext === undefined ? {} : { durableContext };
}

function attemptContextFor(context: MagazineWorkflowContext): WorkflowAttemptContext | undefined {
  const durableContext = context.durableContext?.();
  return durableContext === undefined || (durableContext.kind !== "step" && durableContext.kind !== "agent") ? undefined : durableContext;
}

function requireManuscriptRevision(artifact: { readonly metadata: JsonObject }, artifactId: ArtifactId): ManuscriptRevisionId {
  const revisionId = artifact.metadata.revisionId;
  if (typeof revisionId !== "string" || revisionId.trim().length === 0) {
    throw new Error(`Article manuscript ${artifactId} has no immutable revision identity`);
  }
  return revisionId as ManuscriptRevisionId;
}

function readRevisionRecord(
  ledger: ArtifactLedger,
  artifactId: ArtifactId,
  runId: RunId,
  articleId: string,
): ArticleRevisionRecord {
  const artifact = ledger.requireArtifact(artifactId);
  if (artifact.kind !== "article_revision_record" || artifact.schemaVersion !== "article-revision-record/1" || artifact.mediaType !== "application/json" || artifact.payloadKind !== "json" || artifact.producingRunId !== runId || artifact.metadata.articleId !== articleId) {
    throw new Error("Current article revision record is not an exact run-owned artifact");
  }
  let raw: unknown;
  try { raw = JSON.parse(Buffer.from(ledger.readArtifact(artifactId).bytes).toString("utf8")); } catch (error) {
    throw new Error("Current article revision record is not valid JSON", { cause: error });
  }
  let record: ArticleRevisionRecord;
  try { record = parseArticleRevisionRecord(raw); } catch (error) {
    throw new Error("Current article revision record does not match its strict schema", { cause: error });
  }
  if (!sameParents(artifact.parents, articleRevisionRecordParents(record))) throw new Error("Current article revision record parents are not canonical");
  if (record.manuscriptArtifactId !== artifact.metadata.manuscriptArtifactId || record.manuscriptRevisionId !== artifact.metadata.manuscriptRevisionId) {
    throw new Error("Current article revision record metadata does not match its payload");
  }
  return record;
}

function textMetadataString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function jsonObjectMetadata(value: unknown): JsonObject | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as JsonObject : undefined;
}

function artifactIdMetadataArray(value: unknown): readonly ArtifactId[] | undefined {
  return Array.isArray(value) && value.every((candidate) => typeof candidate === "string" && candidate.trim().length > 0)
    ? value as readonly ArtifactId[]
    : undefined;
}

function textValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function textDigest(text: string): string {
  return `sha256:${createHash("sha256").update(text, "utf8").digest("hex")}`;
}

function deterministicWriterOperationDigest(input: {
  readonly articleExecutionId: string;
  readonly operationKey: string;
  readonly currentManuscriptArtifactId: ArtifactId;
  readonly productionProfileArtifactId: ArtifactId;
  readonly revisionContextArtifactId: ArtifactId;
}): string {
  return `sha256:${createHash("sha256").update(JSON.stringify({ schemaVersion: "closed-writer-step-input/1", ...input }), "utf8").digest("hex")}`;
}

function bindReviewMaterialContext(
  context: import("../article-production/materials.ts").ArticleMaterialContext,
  derivedProfileArtifactId: ArtifactId,
  sourceManuscriptArtifactId: ArtifactId,
  derivedManuscriptArtifactId: ArtifactId,
  humanRulingArtifactIds: readonly ArtifactId[],
  writerReviewMaterialArtifacts?: Readonly<Record<string, ArtifactId>>,
): import("../article-production/materials.ts").ArticleMaterialContext {
  return {
    ...context,
    humanRulingArtifactIds: Object.freeze([...humanRulingArtifactIds]),
    ...(writerReviewMaterialArtifacts === undefined ? {} : { writerReviewMaterialArtifacts }),
    ...(context.measurementInputArtifactIds === undefined ? {} : {
      measurementInputArtifactIds: context.measurementInputArtifactIds.map((artifactId) => artifactId === sourceManuscriptArtifactId ? derivedManuscriptArtifactId : artifactId),
    }),
    reviewPlan: {
      ...context.reviewPlan,
      checks: context.reviewPlan.checks.map((check) => check.kind === "article_measurement"
        ? { ...check, measurementProfileArtifactId: derivedProfileArtifactId }
        : check),
    },
  };
}

function safeIdentity(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9_.-]/gu, "_");
  return normalized.length > 160 ? normalized.slice(0, 160) : normalized;
}
