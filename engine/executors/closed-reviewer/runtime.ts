import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";

import type { AuthorizedWorker } from "../../authority/local-authority.ts";
import type { ArticleAttemptClaim, ArticleAttemptExecutionResult } from "../../workflows/internal-types.ts";
import type { ArticleAttemptRunner } from "../../article-production/attempts.ts";
import type { ArtifactId, ArticleExecutionId, JsonObject, JsonValue, ManuscriptRevisionId } from "../../contracts/index.ts";
import type { ReviewCheckDefinition } from "../../contracts/production-plan.ts";
import type {
  ArticleReviewFinding,
  ArticleReviewModelInput,
  ArticleReviewResult,
  ReviewMaterialPackage,
  ReviewMaterialPackageEntry,
} from "../../workflows/article-review-panel.ts";
import { ArtifactLedger } from "../../workflow-authority/artifact-ledger.ts";
import type { ClosedWriterCredentialResource } from "../closed-writer/credentials.ts";
import { digestJson, stableJson } from "../closed-writer/writer-result.ts";
import {
  invokeOpenAIResponsesCore,
  OPENAI_RESPONSES_CORE_POLICY,
  type OpenAIResponsesResult,
} from "../closed-writer/openai-responses-core.ts";

export const CLOSED_REVIEWER_EXECUTION_CLASS = "closed_reviewer/1" as const;
const REVIEW_OUTPUT_VERSION = "article-review-model-output/1" as const;

export type ClosedReviewerRuntimeIdentity = {
  readonly schemaVersion: "closed-reviewer-runtime/1";
  readonly executionClass: typeof CLOSED_REVIEWER_EXECUTION_CLASS;
  readonly providerCodec: typeof OPENAI_RESPONSES_CORE_POLICY.providerCodec;
  readonly officialEndpointIdentity: typeof OPENAI_RESPONSES_CORE_POLICY.endpoint;
  readonly model: typeof OPENAI_RESPONSES_CORE_POLICY.model;
  readonly reasoningEffort: typeof OPENAI_RESPONSES_CORE_POLICY.reasoningEffort;
  readonly outputSchemaDigest: string;
  readonly maxInputBytes: number;
  readonly maxOutputTokens: number;
  readonly maxResponseBytes: number;
  readonly timeoutMs: number;
};

const reviewOutputSchema: JsonObject = {
  type: "object",
  additionalProperties: false,
  required: ["schemaVersion", "assessment", "findings"],
  properties: {
    schemaVersion: { type: "string", const: REVIEW_OUTPUT_VERSION },
    assessment: { type: "string", enum: ["pass", "findings", "human_required", "not_applicable"] },
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["localId", "severity", "scope", "problem", "requestedOutcome", "evidenceArtifactIds"],
        properties: {
          localId: { type: "string", minLength: 1 },
          severity: { type: "string", enum: ["must_fix", "consider"] },
          scope: { type: "object" },
          problem: { type: "string", minLength: 1 },
          requestedOutcome: { type: "string", minLength: 1 },
          evidenceArtifactIds: { type: "array", items: { type: "string", minLength: 1 } },
        },
      },
    },
  },
};

export const CLOSED_REVIEWER_RUNTIME_IDENTITY: ClosedReviewerRuntimeIdentity = Object.freeze({
  schemaVersion: "closed-reviewer-runtime/1",
  executionClass: CLOSED_REVIEWER_EXECUTION_CLASS,
  providerCodec: OPENAI_RESPONSES_CORE_POLICY.providerCodec,
  officialEndpointIdentity: OPENAI_RESPONSES_CORE_POLICY.endpoint,
  model: OPENAI_RESPONSES_CORE_POLICY.model,
  reasoningEffort: OPENAI_RESPONSES_CORE_POLICY.reasoningEffort,
  outputSchemaDigest: `sha256:${digestJson(reviewOutputSchema)}`,
  maxInputBytes: OPENAI_RESPONSES_CORE_POLICY.maxInputBytes,
  maxOutputTokens: OPENAI_RESPONSES_CORE_POLICY.maxOutputTokens,
  maxResponseBytes: OPENAI_RESPONSES_CORE_POLICY.maxResponseBytes,
  timeoutMs: OPENAI_RESPONSES_CORE_POLICY.timeoutMs,
});

const FIXED_RETRY = Object.freeze({ maxAttempts: 2, retryOn: "retryable" as const });

export type ClosedReviewerStep = <T>(
  key: string,
  operation: () => Promise<T> | T,
  options: { readonly input: JsonObject; readonly retry: typeof FIXED_RETRY },
) => Promise<T>;

export type ClosedReviewerCheck = {
  readonly id: string;
  readonly role: string;
  readonly access: "source_aware" | "source_blind";
  readonly authority: "blocking" | "advisory" | "human_required";
  readonly promptArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
};

export type ClosedReviewerReviewInput = {
  readonly check: ClosedReviewerCheck;
  readonly materials: ReviewMaterialPackage;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly claim: ArticleAttemptClaim;
};

export type ClosedReviewerExecutionRequest = Omit<ClosedReviewerReviewInput, "claim"> & {
  readonly worker: AuthorizedWorker;
  readonly articleExecutionId: ArticleExecutionId;
  readonly operationKey: string;
};

export type ClosedReviewerExecutor = {
  readonly runtimeIdentity: ClosedReviewerRuntimeIdentity;
  readonly review: (input: ClosedReviewerReviewInput) => Promise<ArticleReviewResult>;
  readonly executeInStep: (
    step: ClosedReviewerStep,
    request: ClosedReviewerExecutionRequest,
  ) => Promise<ArticleAttemptExecutionResult<ArticleReviewResult>>;
};

export type CreateClosedReviewerExecutorConfig = {
  readonly ledger: ArtifactLedger;
  readonly credentials: ClosedWriterCredentialResource;
  readonly attemptRunner?: ArticleAttemptRunner;
};

export class ClosedReviewerError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, options?: { readonly retryable?: boolean; readonly cause?: unknown }) {
    super(message, options?.cause === undefined ? undefined : { cause: options.cause });
    this.name = "ClosedReviewerError";
    this.code = code;
    this.retryable = options?.retryable ?? false;
  }
}

/** Factory-only reviewer. Transport and result normalization cannot be replaced by callers. */
export function createClosedReviewerExecutor(config: CreateClosedReviewerExecutorConfig): ClosedReviewerExecutor {
  if (!(config.ledger instanceof ArtifactLedger) || config.credentials.read === undefined) {
    throw new ClosedReviewerError("REVIEWER_FACTORY_INVALID", "closed reviewer requires a trusted ledger and credential resource");
  }
  const runner = config.attemptRunner ?? config.ledger.createArticleAttemptRunner();
  return Object.freeze({
    runtimeIdentity: CLOSED_REVIEWER_RUNTIME_IDENTITY,
    review: async (input: ClosedReviewerReviewInput) => await executeReview(config.credentials, input),
    executeInStep: async (step: ClosedReviewerStep, request: ClosedReviewerExecutionRequest) => await step(
      request.operationKey,
      async () => await runner.executeModel(
        request.worker,
        {
          rootRunId: config.ledger.requireRunByArticleExecutionId(request.articleExecutionId).runId,
          articleExecutionId: request.articleExecutionId,
          articleId: request.materials.articleId,
          operationKey: request.operationKey,
          manuscriptArtifactId: request.manuscriptArtifactId,
          manuscriptRevisionId: request.manuscriptRevisionId,
          access: request.check.access,
          materials: request.materials as never,
        },
        async ({ claim, materials }) => {
          if (!isDeepStrictEqual(materials.artifactIds, request.materials.artifactIds)) {
            throw new ClosedReviewerError("REVIEWER_MATERIAL_SCOPE_INVALID", "attempt claim material set differs from the exact reviewer package");
          }
          const scoped = packageFromLedger(config.ledger, request.materials, request.manuscriptRevisionId);
          const value = await executeReview(config.credentials, { ...request, claim, materials: scoped });
          return { value, artifacts: [reviewArtifactSeed(value, { ...request, materials: scoped }, claim)] };
        },
      ),
      { input: reviewStepInput(request), retry: FIXED_RETRY },
    ),
  });
}

async function executeReview(credentials: ClosedWriterCredentialResource, input: ClosedReviewerReviewInput): Promise<ArticleReviewResult> {
  validateReviewInput(input);
  const prompt = buildReviewerPrompt(input);
  if (Buffer.byteLength(prompt, "utf8") > CLOSED_REVIEWER_RUNTIME_IDENTITY.maxInputBytes) {
    throw new ClosedReviewerError("REVIEWER_INPUT_TOO_LARGE", "closed reviewer input exceeds its pinned byte ceiling");
  }
  let response: OpenAIResponsesResult;
  try {
    response = await invokeOpenAIResponsesCore(credentials, prompt, {
      name: "article_review_model_output",
      schema: reviewOutputSchema,
    });
  } catch (error) {
    if (error instanceof Error && "retryable" in error) {
      throw new ClosedReviewerError("REVIEWER_REQUEST_FAILED", error.message, { retryable: Boolean((error as { retryable?: unknown }).retryable), cause: error });
    }
    throw error;
  }
  const raw = parseModelOutput(response.output);
  return normalizeReviewResult(raw, input);
}

export function parseClosedReviewerOutput(value: unknown): ClosedReviewerModelOutput {
  const parsed = reviewOutputZod.safeParse(value);
  if (!parsed.success) throw new ClosedReviewerError("REVIEWER_RESULT_SCHEMA", "closed reviewer response does not match the exact model-output schema");
  return parsed.data as unknown as ClosedReviewerModelOutput;
}

export type ClosedReviewerModelOutput = {
  readonly schemaVersion: typeof REVIEW_OUTPUT_VERSION;
  readonly assessment: ArticleReviewResult["assessment"];
  readonly findings: readonly ArticleReviewFinding[];
};

export function normalizeReviewResult(value: ClosedReviewerModelOutput, input: ClosedReviewerReviewInput): ArticleReviewResult {
  validateReviewInput(input);
  const allowed = new Set(input.materials.artifactIds);
  const seen = new Set<string>();
  for (const finding of value.findings) {
    if (seen.has(finding.localId)) throw new ClosedReviewerError("REVIEWER_FINDING_DUPLICATE", `reviewer repeated finding ${finding.localId}`);
    seen.add(finding.localId);
    if (finding.evidenceArtifactIds.some((artifactId) => !allowed.has(artifactId))) {
      throw new ClosedReviewerError("REVIEWER_EVIDENCE_OUTSIDE_MATERIALS", `reviewer cited evidence outside its scoped material package`);
    }
    if (finding.scope.kind === "span" && (finding.scope.end ?? 0) < (finding.scope.start ?? 0)) {
      throw new ClosedReviewerError("REVIEWER_SCOPE_INVALID", "reviewer returned a reversed span");
    }
  }
  if (value.assessment === "pass" && value.findings.length > 0) throw new ClosedReviewerError("REVIEWER_ASSESSMENT_INVALID", "pass cannot include findings");
  if (value.assessment === "not_applicable" && value.findings.length > 0) throw new ClosedReviewerError("REVIEWER_ASSESSMENT_INVALID", "not_applicable cannot include findings");
  return {
    schemaVersion: "article-review-result/1",
    reviewerId: input.claim.principalId,
    authenticatedPrincipalId: input.claim.principalId,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    checkId: input.check.id,
    access: input.check.access,
    authority: input.check.authority,
    reviewPlanArtifactId: input.check.reviewPlanArtifactId,
    materialArtifactIds: input.materials.artifactIds,
    assessment: value.assessment,
    findings: value.findings,
  } as ArticleReviewResult;
}

export function reviewArtifactSeed(
  result: ArticleReviewResult,
  request: Pick<ClosedReviewerExecutionRequest, "check" | "materials" | "manuscriptArtifactId" | "manuscriptRevisionId" | "operationKey">,
  claim: ArticleAttemptClaim,
): {
  readonly key: "result";
  readonly kind: "article_review_result";
  readonly schemaVersion: "article-review-result/1";
  readonly mediaType: "application/json";
  readonly origin: "model";
  readonly payload: { readonly kind: "json"; readonly value: JsonValue };
  readonly parents: readonly { readonly artifactId: ArtifactId; readonly relation: "review_input" }[];
  readonly metadata: JsonObject;
} {
  const parents = request.materials.artifactIds.map((artifactId) => ({ artifactId, relation: "review_input" as const }));
  return {
    key: "result",
    kind: "article_review_result",
    schemaVersion: "article-review-result/1",
    mediaType: "application/json",
    origin: "model",
    payload: { kind: "json", value: result as unknown as JsonValue },
    parents,
    metadata: {
      articleId: request.materials.articleId,
      manuscriptArtifactId: request.manuscriptArtifactId,
      manuscriptRevisionId: request.manuscriptRevisionId,
      materialArtifactIds: request.materials.artifactIds as unknown as JsonValue,
      checkId: request.check.id,
      access: request.check.access,
      authority: request.check.authority,
      reviewPlanArtifactId: request.check.reviewPlanArtifactId,
      operationKey: request.operationKey,
      authenticatedPrincipalId: claim.principalId,
      reviewerRuntimeIdentity: CLOSED_REVIEWER_RUNTIME_IDENTITY as unknown as JsonObject,
      reviewerPromptDigest: `sha256:${createHash("sha256").update(buildReviewerPrompt({ ...request, claim }), "utf8").digest("hex")}`,
    },
  };
}

function buildReviewerPrompt(input: ClosedReviewerReviewInput): string {
  const sections = [
    "MAGAZINE CLOSED ARTICLE REVIEW REQUEST",
    `runtimeIdentity=${stableJson(CLOSED_REVIEWER_RUNTIME_IDENTITY as unknown as JsonObject)}`,
    `check=${stableJson(input.check as unknown as JsonObject)}`,
    `materialManifest=${stableJson({
      schemaVersion: input.materials.schemaVersion,
      articleId: input.materials.articleId,
      access: input.materials.access,
      manuscriptArtifactId: input.materials.manuscriptArtifactId,
      manuscriptRevisionId: input.materials.manuscriptRevisionId,
      artifactIds: input.materials.artifactIds,
    } as unknown as JsonObject)}`,
    "Return only the JSON value described by the pinned response schema.",
    ...input.materials.artifacts.map((artifact) => artifactSection(artifact)),
  ];
  return sections.join("\n");
}

function artifactSection(artifact: ReviewMaterialPackageEntry): string {
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(artifact.bytes);
  } catch (error) {
    throw new ClosedReviewerError("REVIEWER_MATERIAL_INVALID", `review material ${artifact.artifactId} is not UTF-8`, { cause: error });
  }
  return [
    `--- artifact ${artifact.artifactId} ${artifact.classification} ${artifact.mediaType} sha256:${artifact.digest} ---`,
    text,
    `--- end artifact ${artifact.artifactId} ---`,
  ].join("\n");
}

function packageFromLedger(ledger: ArtifactLedger, materials: ReviewMaterialPackage, revisionId: ManuscriptRevisionId): ReviewMaterialPackage {
  return Object.freeze({
    ...materials,
    manuscriptRevisionId: revisionId,
    artifacts: Object.freeze(materials.artifacts.map((entry) => {
      const read = ledger.readArtifact(entry.artifactId);
      if (read.artifact.id !== entry.artifactId || read.artifact.digest !== entry.digest) throw new ClosedReviewerError("REVIEWER_MATERIAL_CHANGED", "review material changed while being packaged");
      return Object.freeze({ ...entry, bytes: new Uint8Array(read.bytes) });
    })),
  });
}

function reviewStepInput(request: ClosedReviewerExecutionRequest): JsonObject {
  return {
    schemaVersion: "closed-reviewer-step-input/1",
    articleExecutionId: request.articleExecutionId,
    operationKey: request.operationKey,
    manuscriptArtifactId: request.manuscriptArtifactId,
    manuscriptRevisionId: request.manuscriptRevisionId,
    materialArtifactIds: request.materials.artifactIds as unknown as JsonValue,
    check: request.check as unknown as JsonObject,
    reviewerRuntimeIdentity: CLOSED_REVIEWER_RUNTIME_IDENTITY as unknown as JsonObject,
  };
}

function validateReviewInput(input: ClosedReviewerReviewInput): void {
  if (input.claim.access !== input.check.access || input.claim.manuscriptArtifactId !== input.manuscriptArtifactId || input.claim.manuscriptRevisionId !== input.manuscriptRevisionId) {
    throw new ClosedReviewerError("REVIEWER_CLAIM_MISMATCH", "reviewer claim is not bound to the exact scoped input");
  }
  if (input.claim.authority !== "model" || !input.claim.capabilities.includes("text_model") ||
      input.check.access === "source_aware" && (!input.claim.capabilities.includes("source_access") || input.claim.capabilities.includes("source_blind")) ||
      input.check.access === "source_blind" && (!input.claim.capabilities.includes("source_blind") || input.claim.capabilities.includes("source_access"))) {
    throw new ClosedReviewerError("REVIEWER_CAPABILITY_INVALID", "reviewer claim does not carry the exact capability boundary for its check");
  }
  if (input.materials.access !== input.check.access || input.materials.manuscriptArtifactId !== input.manuscriptArtifactId || !isDeepStrictEqual(input.materials.artifactIds, input.materials.artifacts.map((artifact) => artifact.artifactId))) {
    throw new ClosedReviewerError("REVIEWER_MATERIAL_SCOPE_INVALID", "reviewer material package is not exact");
  }
  if (input.materials.artifacts.some((artifact) => artifact.articleId !== input.materials.articleId)) throw new ClosedReviewerError("REVIEWER_MATERIAL_SCOPE_INVALID", "reviewer material package crosses article identity");
}

const component = z.string().min(1).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/u);
const scopeSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("document") }).strict(),
  z.object({ kind: z.literal("heading"), headingId: component }).strict(),
  z.object({ kind: z.literal("paragraph"), headingId: component.optional(), ordinal: z.number().int().nonnegative() }).strict(),
  z.object({ kind: z.literal("span"), headingId: component.optional(), start: z.number().int().nonnegative(), end: z.number().int().nonnegative() }).strict(),
]);
const findingSchema = z.object({
  localId: component,
  severity: z.enum(["must_fix", "consider"]),
  scope: scopeSchema,
  problem: z.string().min(1),
  requestedOutcome: z.string().min(1),
  evidenceArtifactIds: z.array(z.string().min(1)),
}).strict();
const reviewOutputZod = z.object({
  schemaVersion: z.literal(REVIEW_OUTPUT_VERSION),
  assessment: z.enum(["pass", "findings", "human_required", "not_applicable"]),
  findings: z.array(findingSchema),
}).strict();

function parseModelOutput(value: JsonValue): ClosedReviewerModelOutput {
  return parseClosedReviewerOutput(value);
}

void (reviewOutputSchema satisfies JsonObject);
