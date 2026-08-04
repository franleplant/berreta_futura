import type { ArtifactId, JsonObject, RunId } from "../contracts/index.ts";
import type {
  ArticleInputBinding,
  ArticleStartRequest,
  ArticleWorkflowResult,
} from "../contracts/workflow-run.ts";
import type { DurablePromotionRequest } from "../durable/types.ts";
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
  const bindings = [...args.inputBindings];
  const inputArtifactIds = bindings.map((binding) => binding.artifactId);
  const inputRevisions = bindings.map((binding) => binding.revision);
  const seed = ports.ledger.requireArtifact(args.manuscriptArtifactId);
  if (seed.mediaType !== "text/markdown") {
    throw new Error("Article manuscript seed must be Markdown");
  }
  if (!sameStrings(seed.parents.map((parent) => parent.artifactId), inputArtifactIds)) {
    throw new Error("Article manuscript seed parents do not equal the exact input bindings");
  }
  assertBindingMetadata(ports.ledger, bindings);

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
        parents: inputArtifactIds.map((artifactId) => ({ artifactId, relation: "input_binding" })),
        metadata: {
          articleId: args.articleId,
          sourceManuscriptArtifactId: args.manuscriptArtifactId,
          rendererIdentity: args.rendererIdentity as unknown as JsonObject,
          inputBindings: bindings as unknown as readonly JsonObject[],
          ...(bindings.length === 1 ? { revisionId: bindings[0]!.revision.revisionId } : {}),
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

  const measurement = await context.step(
    "article.measurement",
    async () => {
      const value = await ports.measureArticle({
        articleId: args.articleId,
        manuscriptArtifactId: acceptedManuscriptArtifactId,
        measurementProfileArtifactId,
        rendererIdentity: args.rendererIdentity,
        ...withContext(context),
      });
      if (
        value.articleId !== args.articleId ||
        value.manuscriptArtifactId !== acceptedManuscriptArtifactId ||
        !Number.isSafeInteger(value.pageCount) ||
        value.pageCount < 0 ||
        !Number.isSafeInteger(value.maximumReaderPages) ||
        value.maximumReaderPages < 1 ||
        value.openerFits !== true
      ) {
        throw new Error("Article measurement returned an invalid or incomplete immutable result");
      }
      ports.ledger.createArtifact({
        id: measurementId(runId),
        kind: "article_measurement",
        schemaVersion: "article-measurement/1",
        mediaType: "application/json",
        origin: "machine",
        payload: { kind: "json", value: value as unknown as JsonObject },
        parents: [
          { artifactId: acceptedManuscriptArtifactId, relation: "measured_manuscript" },
          { artifactId: measurementProfileArtifactId, relation: "measurement_profile" },
          ...inputArtifactIds.map((artifactId) => ({ artifactId, relation: "measurement_input" })),
        ],
        metadata: {
          articleId: args.articleId,
          fits: value.fits,
          openerFits: value.openerFits,
          pageCount: value.pageCount,
          ...(bindings.length === 1 ? { revisionId: bindings[0]!.revision.revisionId } : {}),
          rendererIdentity: args.rendererIdentity as unknown as JsonObject,
        },
        runId,
        ...withContext(context),
      });
      ports.ledger.recordMeasurement(runId, measurementId(runId));
      return value;
    },
    { input: {
      articleId: args.articleId,
      manuscriptArtifactId: acceptedManuscriptArtifactId,
      measurementProfileArtifactId,
      inputBindings: bindings as unknown as readonly JsonObject[],
    } },
  );
  void measurement;

  const taskArtifactId = decisionTaskId(runId);
  const offer = offerId(runId);
  const decisionArtifact = decisionArtifactId(offer);
  const decisionInputs = [acceptedManuscriptArtifactId, measurementId(runId), ...inputArtifactIds];

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
            measurementArtifactId: measurementId(runId),
            measurementProfileArtifactId,
            inputArtifactIds: decisionInputs,
            decisionArtifactId: decisionArtifact,
            allowedChoices: ["accept", "drop"],
          },
        },
        parents: [
          { artifactId: acceptedManuscriptArtifactId, relation: "decision_manuscript" },
          { artifactId: measurementId(runId), relation: "decision_measurement" },
          { artifactId: measurementProfileArtifactId, relation: "decision_profile" },
          ...inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_input" })),
        ],
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
      articleId: args.articleId,
      manuscriptArtifactId: acceptedManuscriptArtifactId,
      measurementArtifactId: measurementId(runId),
      measurementProfileArtifactId,
      inputArtifactIds: decisionInputs,
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
      articleId: args.articleId,
      status: "dropped",
      manuscriptArtifactId: acceptedManuscriptArtifactId,
      measurementArtifactId: measurementId(runId),
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
    inputBindings: bindings.map((binding) => ({ artifactId: binding.artifactId, revision: binding.revision })),
    inputRevisions,
    inputArtifactIds,
  };
  return await context.step(
    "article.promotion",
    () => ports.promote({
      request,
      reviewer: decision.principalId,
      rationale: decision.rationale,
      ...withContext(context),
    }),
    { input: request as unknown as JsonObject },
  );
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

function requirePromotionId(args: ArticleStartRequest, runId: RunId): import("../contracts/index.ts").PromotionId {
  return (args.promotionId ?? `promotion-${safeIdentity(runId)}`) as import("../contracts/index.ts").PromotionId;
}

function requireRevisionId(args: ArticleStartRequest): import("../contracts/index.ts").RevisionId {
  if (args.revisionId === undefined) throw new Error("Article workflow requires a generated durable revision identity");
  return args.revisionId;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function withContext(context: MagazineWorkflowContext): { readonly durableContext: WorkflowDurableContext } | Record<string, never> {
  const durableContext = context.durableContext?.();
  return durableContext === undefined ? {} : { durableContext };
}

function safeIdentity(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9_.-]/gu, "_");
  return normalized.length > 160 ? normalized.slice(0, 160) : normalized;
}
