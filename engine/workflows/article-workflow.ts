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
  WorkflowDurableContext,
} from "./internal-types.ts";
import type { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import { assertRendererIdentity, type RendererIdentity } from "./renderer-identity.ts";

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

  const acceptedManuscriptArtifactId = await context.step(
    "article.manuscript",
    async () => {
      const source = ports.ledger.readArtifact(args.manuscriptArtifactId);
      const text = Buffer.from(source.bytes).toString("utf8");
      ports.ledger.createArtifact({
        id: manuscriptId(runId),
        kind: "article_manuscript",
        schemaVersion: "article-manuscript/1",
        mediaType: "text/markdown",
        origin: "machine",
        payload: { kind: "text", text },
        parents: materialArtifactIds.map((artifactId) => ({ artifactId, relation: "input_binding" })),
        metadata: {
          articleId: args.articleId,
          sourceManuscriptArtifactId: args.manuscriptArtifactId,
          rendererIdentity: args.rendererIdentity as unknown as JsonObject,
          inputBindings: bindings as unknown as readonly JsonObject[],
          materialArtifactIds: materialArtifactIds as unknown as readonly JsonValue[],
          revisionId: deterministicManuscriptRevisionId(args.articleId, bindings, text, materialArtifactIds),
        },
        runId,
        ...withContext(context),
      });
      ports.ledger.recordManuscriptArtifact(runId, manuscriptId(runId));
      return manuscriptId(runId);
    },
    { input: {
      articleId: args.articleId,
      sourceManuscriptArtifactId: args.manuscriptArtifactId,
      inputBindings: bindings as unknown as readonly JsonObject[],
      materialArtifactIds: materialArtifactIds as unknown as readonly JsonValue[],
    } },
  );

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

  const manuscriptRevisionId = requireManuscriptRevision(ports.ledger.requireArtifact(acceptedManuscriptArtifactId), acceptedManuscriptArtifactId);
  const reviewPanel = await ports.runReviewPanel({
    runId,
    articleExecutionId: args.articleExecutionId,
    articleId: args.articleId,
    manuscriptArtifactId: acceptedManuscriptArtifactId,
    manuscriptRevisionId,
    manuscriptOrdinal: 0,
    rendererIdentity: args.rendererIdentity,
    materialContext: bindReviewMaterialContext(
      args.review.materialContext,
      measurementProfileArtifactId,
      args.manuscriptArtifactId,
      acceptedManuscriptArtifactId,
    ),
    ...(args.review.materialSelection === undefined ? {} : { materialSelection: args.review.materialSelection }),
    ...(args.review.teaching === undefined ? {} : { teaching: args.review.teaching }),
  }, context);

  const measurement = reviewPanel.checks.find((check) => check.status === "completed" && check.kind === "article_measurement");
  if (measurement?.resultArtifactId === undefined) throw new Error("Article review panel did not produce a selected measurement artifact");
  const measurementArtifactId = measurement.resultArtifactId;
  const reviewArtifactIds = reviewPanel.checks
    .filter((check) => check.kind === "model_review")
    .flatMap((check) => check.resultArtifactId === undefined ? [] : [check.resultArtifactId]);
  const reviewOutputArtifactIds = reviewPanel.checks
    .filter((check) => check.kind === "article_measurement")
    .flatMap((check) => check.outputArtifactIds.filter((artifactId) => artifactId !== measurementArtifactId));
  ports.ledger.recordMeasurement(runId, measurementArtifactId);

  const taskArtifactId = decisionTaskId(runId);
  const offer = offerId(runId);
  const decisionArtifact = decisionArtifactId(offer);
  const decisionInputs = canonicalDecisionEvidence({
    manuscriptArtifactId: acceptedManuscriptArtifactId,
    reviewArtifactIds,
    measurementArtifactId,
    measurementProfileArtifactId,
    reviewOutputArtifactIds,
    inputArtifactIds: materialArtifactIds,
  });

  await context.step(
    "article.decision-offer",
    () => {
      ports.ledger.createArtifact({
        id: taskArtifactId,
        kind: "article_decision_request",
        schemaVersion: "article-decision-request/1",
        mediaType: "application/json",
        origin: "machine",
        payload: {
          kind: "json",
          value: {
            schemaVersion: "article-decision-request/1",
            runId,
            articleId: args.articleId,
            manuscriptArtifactId: acceptedManuscriptArtifactId,
            measurementArtifactId,
            measurementProfileArtifactId,
            inputArtifactIds: decisionInputs,
            decisionEvidenceArtifactIds: decisionInputs,
            decisionArtifactId: decisionArtifact,
            allowedChoices: ["accept", "drop"],
          },
        },
        // The canonical evidence list is the one lineage authority for the
        // task, offer, decision, and promotion. Do not add convenience edges
        // here: that creates duplicate parents and lets the arrays drift.
        parents: decisionInputs.map((artifactId) => ({ artifactId, relation: "decision_evidence" })),
        metadata: {
          articleId: args.articleId,
          allowedChoices: ["accept", "drop"],
          decisionArtifactId: decisionArtifact,
          rendererIdentity: args.rendererIdentity as unknown as JsonObject,
        },
        runId,
        ...withContext(context),
      });
      ports.ledger.createOffer({ id: offer, runId, taskArtifactId, inputArtifactIds: decisionInputs });
      return { taskArtifactId, offerId: offer };
    },
    { input: {
      runId,
      articleExecutionId: args.articleExecutionId,
      articleId: args.articleId,
      manuscriptArtifactId: acceptedManuscriptArtifactId,
      measurementArtifactId,
      measurementProfileArtifactId,
      inputArtifactIds: decisionInputs,
      decisionEvidenceArtifactIds: decisionInputs,
      decisionArtifactId: decisionArtifact,
    } },
  );

  const answer = await context.wait("article.decision", {
    request: {
      schemaVersion: "magazine-article-decision-request/1",
      runId,
      offerId: offer,
      taskArtifactId,
      decisionArtifactId: decisionArtifact,
    },
  });
  if (answer.decisionArtifactId !== decisionArtifact) {
    throw new Error("Article decision wait returned a stale decision artifact");
  }
  const decision = ports.requireDecision(answer.decisionArtifactId);
  if (
    decision.runId !== runId ||
    decision.offerId !== offer ||
    decision.taskArtifactId !== taskArtifactId ||
    !sameStrings(decision.inputArtifactIds, decisionInputs)
  ) {
    throw new Error("Article decision artifact is not bound to the exact immutable offer");
  }
  if (decision.choice === "drop") {
    return {
      schemaVersion: "magazine-article-workflow-result/1",
      runId,
      articleExecutionId: args.articleExecutionId,
      articleId: args.articleId,
      status: "dropped",
      manuscriptArtifactId: acceptedManuscriptArtifactId,
      measurementArtifactId,
      decisionArtifactId: decision.artifactId,
    };
  }

  const request: DurablePromotionRequest = {
    schemaVersion: "durable-checkpoint-request/1",
    promotionId: requirePromotionId(args, runId),
    revisionId: requireRevisionId(args),
    runId,
    logicalItem: args.logicalItem,
    expectedParentRevisionId: args.expectedParentRevisionId,
    acceptedArtifactIds: [acceptedManuscriptArtifactId],
    decisionArtifactIds: [decision.artifactId],
    inputBindings: canonicalMaterialBindings(args.entry),
    inputRevisions,
    inputArtifactIds: materialArtifactIds,
    decisionEvidenceArtifactIds: decisionInputs,
  };
  return await context.step(
    "article.promotion",
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
): ManuscriptRevisionId {
  const value = JSON.stringify({
    schemaVersion: "article-manuscript/1",
    articleId,
    inputBindings: bindings.map((binding) => ({
      artifactId: binding.artifactId,
      revision: binding.revision,
    })),
    materialArtifactIds,
    text,
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

export function measurementId(runId: RunId): ArtifactId {
  return `art-measurement-${safeIdentity(runId)}` as ArtifactId;
}

export function decisionTaskId(runId: RunId): ArtifactId {
  return `art-decision-task-${safeIdentity(runId)}` as ArtifactId;
}

export function offerId(runId: RunId): string {
  return `offer-article-decision-${safeIdentity(runId)}`;
}

export function decisionArtifactId(offer: string): ArtifactId {
  return `art-decision-${safeIdentity(offer)}` as ArtifactId;
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

function requirePromotionId(args: ArticleRuntimeStartArgs, runId: RunId): import("../contracts/index.ts").PromotionId {
  return args.promotionId ?? (`promotion-${safeIdentity(runId)}` as import("../contracts/index.ts").PromotionId);
}

function requireRevisionId(args: ArticleRuntimeStartArgs): import("../contracts/index.ts").RevisionId {
  return args.revisionId;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function withContext(context: MagazineWorkflowContext): { readonly durableContext: WorkflowDurableContext } | Record<string, never> {
  const durableContext = context.durableContext?.();
  return durableContext === undefined ? {} : { durableContext };
}

function requireManuscriptRevision(artifact: { readonly metadata: JsonObject }, artifactId: ArtifactId): ManuscriptRevisionId {
  const revisionId = artifact.metadata.revisionId;
  if (typeof revisionId !== "string" || revisionId.trim().length === 0) {
    throw new Error(`Article manuscript ${artifactId} has no immutable revision identity`);
  }
  return revisionId as ManuscriptRevisionId;
}

function bindReviewMaterialContext(
  context: import("../article-production/materials.ts").ArticleMaterialContext,
  derivedProfileArtifactId: ArtifactId,
  sourceManuscriptArtifactId: ArtifactId,
  derivedManuscriptArtifactId: ArtifactId,
): import("../article-production/materials.ts").ArticleMaterialContext {
  return {
    ...context,
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
