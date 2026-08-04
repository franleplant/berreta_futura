import { createHash } from "node:crypto";
import { z } from "zod";

import type { AuthorizedWorker } from "../authority/local-authority.ts";
import {
  assertArticleExecutionMaterials,
  applicableReviewCheck,
  selectArticleReviewerMaterials,
  type ArticleMaterialContext,
  type ArticleMaterialSelectionContext,
  type ArticleMaterialSet,
  type ClassifiedArticleArtifact,
} from "../article-production/materials.ts";
import type {
  ArticleExecutionId,
  ArtifactId,
  JsonObject,
  JsonValue,
  ManuscriptRevisionId,
  RunId,
} from "../contracts/index.ts";
import type { ReviewCheckDefinition, ReviewWave } from "../contracts/production-plan.ts";
import {
  ArticleAttemptRunner,
  type ArticleAttemptExecutionResult,
} from "../article-production/attempts.ts";
import type { ArtifactLedger, LedgerArtifact } from "../workflow-authority/artifact-ledger.ts";
import type {
  ArticleMeasurement,
  ArticleAttemptClaim,
  ArticleWorkflowPorts,
  MagazineWorkflowContext,
  WorkflowAttemptContext,
} from "./internal-types.ts";
import type { RendererIdentity } from "./renderer-identity.ts";
import type { ScopedArticleMeasurementArtifactReader } from "../renderer-adapter/article-measurement.ts";

/** The normalized result emitted by a model reviewer. */
export type ArticleReviewResult = {
  readonly schemaVersion: "article-review-result/1";
  readonly reviewerId: string;
  /** Closed reviewer provenance, present for factory-normalized model output. */
  readonly authenticatedPrincipalId?: string;
  readonly checkId?: string;
  readonly access?: "source_aware" | "source_blind";
  readonly authority?: "blocking" | "advisory" | "human_required";
  readonly reviewPlanArtifactId?: ArtifactId;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId?: ManuscriptRevisionId;
  readonly materialArtifactIds?: readonly ArtifactId[];
  readonly assessment: "pass" | "findings" | "human_required" | "not_applicable";
  readonly findings: readonly ArticleReviewFinding[];
};

/** A stable structural location. It is descriptive, never a mutable path authority. */
export type ManuscriptScope = {
  readonly kind: "document" | "heading" | "paragraph" | "span";
  readonly headingId?: string;
  readonly ordinal?: number;
  readonly start?: number;
  readonly end?: number;
};

export type ArticleReviewFinding = {
  readonly localId: string;
  readonly severity: "must_fix" | "consider";
  readonly scope: ManuscriptScope;
  readonly problem: string;
  readonly requestedOutcome: string;
  readonly evidenceArtifactIds: readonly ArtifactId[];
};

/**
 * The only material a model reviewer receives. It is deliberately narrower
 * than LedgerArtifact: there is no ledger handle and no callback that can
 * widen the reviewer's read set after the access check has run.
 */
export type ReviewMaterialPackageEntry = {
  readonly artifactId: ArtifactId;
  readonly articleId: string;
  readonly classification: ClassifiedArticleArtifact["classification"];
  readonly mediaType: string;
  readonly digest: string;
  readonly bytes: Uint8Array;
};

export type ReviewMaterialPackage = {
  readonly schemaVersion: "article-review-material-package/1";
  readonly articleId: string;
  readonly access: "source_aware" | "source_blind";
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly artifactIds: readonly ArtifactId[];
  readonly artifacts: readonly ReviewMaterialPackageEntry[];
};

/** A durable check result. Skipped checks have no result or attempt artifact. */
export type ArticleReviewCheckResult = {
  readonly schemaVersion: "article-review-check-result/2";
  readonly status: "completed" | "skipped";
  readonly waveId: string;
  readonly checkId: string;
  readonly kind: ReviewCheckDefinition["kind"];
  readonly key: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly materialArtifactIds: readonly ArtifactId[];
  readonly outputArtifactIds: readonly ArtifactId[];
  readonly resultArtifactId?: ArtifactId;
  readonly reviewerId?: string;
  readonly assessment: ArticleReviewResult["assessment"];
  readonly findings: readonly ArticleReviewFinding[];
  readonly result?: ArticleReviewResult | ArticleMeasurement;
  readonly skipReason?: string;
  readonly durableContext?: WorkflowAttemptContext;
};

/** Durable step output. Domain payloads stay in immutable ledger artifacts. */
export type ArticleReviewStepCheckpoint = {
  readonly schemaVersion: "article-review-checkpoint/1";
  readonly status: "completed" | "skipped";
  readonly waveId: string;
  readonly checkId: string;
  readonly kind: ReviewCheckDefinition["kind"];
  readonly key: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly materialArtifactIds: readonly ArtifactId[];
  readonly outputArtifactIds: readonly ArtifactId[];
  readonly resultArtifactId?: ArtifactId;
  readonly reviewerId?: string;
  readonly assessment: ArticleReviewResult["assessment"];
  readonly findingArtifactIds: readonly ArtifactId[];
};

export type ArticleReviewPanelResult = {
  readonly schemaVersion: "article-review-panel/2";
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly manuscriptOrdinal: number;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  /** Declared plan order, independent of completion order. */
  readonly checks: readonly ArticleReviewCheckResult[];
};

export type ArticleReviewModelInput = {
  readonly check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>;
  readonly materials: ReviewMaterialPackage;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly claim: ArticleAttemptClaim;
};

/** Ports for one review panel. Loops only calls this through durable steps. */
export type ArticleReviewWorkflowPorts = {
  readonly ledger: ArtifactLedger;
  readonly attemptRunner: ArticleAttemptRunner;
  readonly reviewerFor: (
    check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>,
  ) => AuthorizedWorker | Promise<AuthorizedWorker>;
  readonly toolWorkerFor: (
    check: Extract<ReviewCheckDefinition, { readonly kind: "article_measurement" }>,
  ) => AuthorizedWorker | Promise<AuthorizedWorker>;
  readonly runModelReview: (input: ArticleReviewModelInput) => Promise<ArticleReviewResult> | ArticleReviewResult;
  readonly measureArticle: ArticleWorkflowPorts["measureArticle"];
};

export type ArticleReviewPanelInput = {
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  /** Monotonic ordinal for diagnostics. It is not a key or identity source. */
  readonly manuscriptOrdinal: number;
  readonly rendererIdentity: RendererIdentity;
  readonly materialContext: ArticleMaterialContext;
  readonly materialSelection?: ArticleMaterialSelectionContext;
  readonly teaching?: "applicable" | "not_applicable";
};

export class ArticleReviewPanelError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, options?: { readonly retryable?: boolean; readonly cause?: unknown }) {
    super(message, options?.cause === undefined ? undefined : { cause: options.cause });
    this.name = "ArticleReviewPanelError";
    this.code = code;
    this.retryable = options?.retryable ?? false;
  }
}

const component = z.string().min(1).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/u);
const stepMaterialSchema = z.object({
  artifactId: z.string().min(1),
  classification: component,
}).strict();

/** Strict immutable input persisted on every review step. */
export const articleReviewStepInputSchema = z.object({
  schemaVersion: z.literal("article-review-step-input/1"),
  key: z.string().min(1),
  runId: z.string().min(1),
  articleExecutionId: z.string().min(1),
  articleId: z.string().min(1),
  manuscriptOrdinal: z.number().int().nonnegative(),
  manuscriptArtifactId: z.string().min(1),
  manuscriptRevisionId: z.string().min(1),
  reviewPlanArtifactId: z.string().min(1),
  waveId: component,
  checkId: component,
  checkKind: z.enum(["model_review", "article_measurement"]),
  access: z.enum(["source_aware", "source_blind", "tool"]),
  materialArtifactIds: z.array(z.string().min(1)),
}).strict();

/** Strict result envelope used as the durable step output schema. */
export const articleReviewStepCheckpointSchema = z.object({
  schemaVersion: z.literal("article-review-checkpoint/1"),
  status: z.enum(["completed", "skipped"]),
  waveId: z.string().min(1),
  checkId: z.string().min(1),
  kind: z.enum(["model_review", "article_measurement"]),
  key: z.string().min(1),
  manuscriptArtifactId: z.string().min(1),
  manuscriptRevisionId: z.string().min(1),
  materialArtifactIds: z.array(z.string().min(1)),
  outputArtifactIds: z.array(z.string().min(1)),
  resultArtifactId: z.string().min(1).optional(),
  reviewerId: z.string().min(1).optional(),
  assessment: z.enum(["pass", "findings", "human_required", "not_applicable"]),
  findingArtifactIds: z.array(z.string().min(1)),
}).strict();

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
const reviewResultSchema = z.object({
  schemaVersion: z.literal("article-review-result/1"),
  reviewerId: z.string().min(1),
  authenticatedPrincipalId: z.string().min(1).optional(),
  checkId: component.optional(),
  access: z.enum(["source_aware", "source_blind"]).optional(),
  authority: z.enum(["blocking", "advisory", "human_required"]).optional(),
  reviewPlanArtifactId: z.string().min(1).optional(),
  manuscriptArtifactId: z.string().min(1),
  manuscriptRevisionId: z.string().min(1).optional(),
  materialArtifactIds: z.array(z.string().min(1)).optional(),
  assessment: z.enum(["pass", "findings", "human_required", "not_applicable"]),
  findings: z.array(findingSchema),
}).strict();

/**
 * Run every applicable check in declared waves. Checks in one wave execute in
 * parallel, while the returned panel is always reconstructed in plan order.
 */
export async function runArticleReviewPanel(
  input: ArticleReviewPanelInput,
  context: MagazineWorkflowContext,
  ports: ArticleReviewWorkflowPorts,
): Promise<ArticleReviewPanelResult> {
  validatePanelInput(input, ports.ledger);
  const checksById = new Map(input.materialContext.reviewPlan.checks.map((check) => [check.id, check]));
  const results = new Map<string, ArticleReviewCheckResult>();
  let stopped: string | undefined;

  for (const wave of input.materialContext.reviewPlan.waves) {
    const waveChecks = wave.checkIds.map((checkId) => {
      const check = checksById.get(checkId);
      if (check === undefined) throw new ArticleReviewPanelError("REVIEW_PLAN_INVALID", `review wave ${wave.id} names unknown check ${checkId}`);
      return check;
    });
    for (const check of waveChecks) {
      if (!applicableReviewCheck(check, input.materialContext.contentMode, input.teaching ?? "not_applicable")) {
        results.set(check.id, skippedResult(input, check, wave.id, "not_applicable"));
      }
    }
    if (stopped !== undefined) {
      for (const check of waveChecks) {
        if (!results.has(check.id)) results.set(check.id, skippedResult(input, check, wave.id, stopped));
      }
      continue;
    }

    const applicable = waveChecks.filter((check) => !results.has(check.id));
    if (applicable.length === 0) continue;
    const branchResults = await context.parallel(
      applicable.map((check) => async () => {
        const key = reviewKey({
          articleExecutionId: input.articleExecutionId,
          reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
          manuscriptRevisionId: input.manuscriptRevisionId,
          waveId: wave.id,
          checkId: check.id,
        });
        const stepInput = reviewStepInput(input, check, wave.id, key);
        const checkpoint = await context.step(
          key,
          async () => checkpointFromResult(await executeCheck(input, check, wave.id, key, context, ports)),
          {
            input: stepInput,
            schema: context.reviewStepResultSchema,
            label: `review.${wave.id}.${check.id}`,
            // Renderer/schema failures are permanent; only explicitly
            // retryable adapter/attempt failures should consume a second
            // durable step attempt.
            retry: { maxAttempts: 2, retryOn: "retryable" },
          },
        );
        return reloadSelectedResult(checkpoint, input, check, wave.id, key, ports.ledger, input.materialSelection);
      }),
      { failureMode: "fail-fast" },
    );
    if (branchResults.length !== applicable.length) {
      throw new ArticleReviewPanelError("REVIEW_PARALLEL_SHAPE", "Loops returned the wrong number of review branches");
    }
    for (const [index, result] of branchResults.entries()) {
      if (result === null) {
        throw new ArticleReviewPanelError("REVIEW_CHECK_FAILED", `review check ${applicable[index]!.id} did not produce a durable result`, { retryable: true });
      }
      results.set(applicable[index]!.id, result);
    }
    const completed = applicable.map((check) => results.get(check.id)!);
    const stop = completed.find((result) => shouldStopAfter(wave, checksById.get(result.checkId)!, result));
    if (stop !== undefined && wave.stopAfter !== "never") {
      stopped = `stopped_after:${wave.id}:${stop.checkId}`;
    }
  }

  const ordered = input.materialContext.reviewPlan.waves.flatMap((wave) => wave.checkIds.map((checkId) => {
    const result = results.get(checkId);
    if (result === undefined) {
      const check = checksById.get(checkId);
      if (check === undefined) throw new ArticleReviewPanelError("REVIEW_PLAN_INVALID", `review check ${checkId} is not declared`);
      return skippedResult(input, check, "unassigned", stopped ?? "not_executed");
    }
    return result;
  }));
  return {
    schemaVersion: "article-review-panel/2",
    runId: input.runId,
    articleExecutionId: input.articleExecutionId,
    articleId: input.articleId,
    manuscriptOrdinal: input.manuscriptOrdinal,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    checks: Object.freeze(ordered),
  };
}

export type ReviewKeyParts = {
  readonly articleExecutionId: ArticleExecutionId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly waveId: string;
  readonly checkId: string;
};

/** Stable key for one exact manuscript/check in one frozen review plan. */
export function reviewKey(parts: ReviewKeyParts): string {
  const values = [parts.articleExecutionId, parts.reviewPlanArtifactId, parts.manuscriptRevisionId, parts.waveId, parts.checkId];
  if (values.some((value) => value.trim().length === 0 || value.includes("\u0000"))) {
    throw new ArticleReviewPanelError("REVIEW_KEY_INVALID", "review key components must be non-empty and cannot contain NUL");
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/u.test(parts.waveId) || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/u.test(parts.checkId)) {
    throw new ArticleReviewPanelError("REVIEW_KEY_INVALID", "review wave and check IDs are not stable key components");
  }
  const digest = createHash("sha256").update(values.join("\u0000"), "utf8").digest("hex");
  return `review.${digest}`;
}

async function executeCheck(
  input: ArticleReviewPanelInput,
  check: ReviewCheckDefinition,
  waveId: string,
  key: string,
  context: MagazineWorkflowContext,
  ports: ArticleReviewWorkflowPorts,
): Promise<ArticleReviewCheckResult> {
  const materials = selectArticleReviewerMaterials(input.materialContext, check, input.manuscriptArtifactId, input.materialSelection);
  assertArticleExecutionMaterials({
    articleId: input.articleId,
    manuscriptArtifactId: input.manuscriptArtifactId,
    access: check.kind === "article_measurement" ? "tool" : check.access,
    materials,
  });
  if (check.kind === "model_review") return await executeModelCheck(input, check, materials, waveId, key, context, ports);
  return await executeMeasurementCheck(input, check, materials, waveId, key, context, ports);
}

async function executeModelCheck(
  input: ArticleReviewPanelInput,
  check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>,
  materials: ArticleMaterialSet,
  waveId: string,
  key: string,
  _context: MagazineWorkflowContext,
  ports: ArticleReviewWorkflowPorts,
): Promise<ArticleReviewCheckResult> {
  const worker = await ports.reviewerFor(check);
  const attempt: ArticleAttemptExecutionResult<ArticleReviewResult> = await ports.attemptRunner.executeModel(
    worker,
    {
      rootRunId: input.runId,
      articleExecutionId: input.articleExecutionId,
      articleId: input.articleId,
      operationKey: key,
      manuscriptArtifactId: input.manuscriptArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      access: check.access,
      materials,
    },
    async ({ claim }) => {
      // The access check above is intentionally before this read. A source
      // blind reviewer can never learn that a source exists by causing a
      // ledger read and then being rejected.
      const packageValue = reviewMaterialPackage(ports.ledger, materials, input.manuscriptRevisionId);
      const result = await ports.runModelReview({
        check,
        materials: packageValue,
        manuscriptArtifactId: input.manuscriptArtifactId,
        manuscriptRevisionId: input.manuscriptRevisionId,
        claim,
      });
      validateModelResult(result, check, input, materials, claim);
      return {
        value: result,
        artifacts: [{
          key: "result",
          kind: "article_review_result",
          schemaVersion: "article-review-result/1",
          mediaType: "application/json",
          origin: "model" as const,
          payload: { kind: "json" as const, value: result as unknown as JsonValue },
          parents: materials.artifactIds.map((artifactId) => ({ artifactId, relation: "review_input" })),
          metadata: reviewMetadata(input, check, materials, claim.principalId, key, waveId),
        }],
      };
    },
  );
  if (!attempt.selected || attempt.artifacts.length !== 1) {
    throw new ArticleReviewPanelError("REVIEW_RESULT_NOT_SELECTED", `review check ${check.id} did not select exactly one result`, { retryable: true });
  }
  const artifact = attempt.artifacts[0]!;
  const value = attempt.adopted
    ? readReviewResult(ports.ledger, artifact, input, check, materials)
    : attempt.value;
  validateResultArtifact(artifact, input, check, materials, value, key, waveId);
  return {
    schemaVersion: "article-review-check-result/2",
    status: "completed",
    waveId,
    checkId: check.id,
    kind: check.kind,
    key,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    materialArtifactIds: materials.artifactIds,
    outputArtifactIds: [artifact.id],
    resultArtifactId: artifact.id,
    reviewerId: value.reviewerId,
    assessment: value.assessment,
    findings: value.findings,
    result: value,
    durableContext: requireAttemptContext(artifact, key),
  };
}

async function executeMeasurementCheck(
  input: ArticleReviewPanelInput,
  check: Extract<ReviewCheckDefinition, { readonly kind: "article_measurement" }>,
  materials: ArticleMaterialSet,
  waveId: string,
  key: string,
  context: MagazineWorkflowContext,
  ports: ArticleReviewWorkflowPorts,
): Promise<ArticleReviewCheckResult> {
  const worker = await ports.toolWorkerFor(check);
  const attempt: ArticleAttemptExecutionResult<ArticleMeasurement> = await ports.attemptRunner.executeTool(
    worker,
    {
      rootRunId: input.runId,
      articleExecutionId: input.articleExecutionId,
      articleId: input.articleId,
      operationKey: key,
      manuscriptArtifactId: input.manuscriptArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      access: "tool",
      materials,
    },
    async ({ claim }) => {
      const measurement = await ports.measureArticle({
        articleId: input.articleId,
        manuscriptArtifactId: input.manuscriptArtifactId,
        measurementProfileArtifactId: check.measurementProfileArtifactId,
        rendererIdentity: input.rendererIdentity,
        artifacts: preloadMeasurementArtifacts(ports.ledger, materials),
        durableContext: claim.durableContext,
      });
      validateMeasurement(measurement, check, input, materials);
      const rendererOutput: JsonObject = {
        schemaVersion: "article-renderer-measurement-output/1",
        articleId: measurement.articleId,
        manuscriptArtifactId: measurement.manuscriptArtifactId,
        inputArtifactIds: measurement.inputArtifactIds as unknown as JsonValue,
        layouts: measurement.layouts as unknown as JsonValue,
      };
      return {
        value: measurement,
        artifacts: [
          {
            key: "measurement",
            kind: "article_measurement",
            schemaVersion: "article-measurement/1",
            mediaType: "application/json",
            origin: "machine" as const,
            payload: { kind: "json" as const, value: measurement as unknown as JsonValue },
            parents: materials.artifactIds.map((artifactId) => ({ artifactId, relation: "measurement_input" })),
            metadata: {
              ...reviewMetadata(input, check, materials, claim.principalId, key, waveId),
              assessment: measurementFindings(measurement, check, input.manuscriptArtifactId).length === 0 ? "pass" : "findings",
            },
          },
          {
            key: "renderer-output",
            kind: "article_measurement_renderer_output",
            schemaVersion: "article-renderer-measurement-output/1",
            mediaType: "application/json",
            origin: "machine" as const,
            payload: { kind: "json" as const, value: rendererOutput },
            parents: materials.artifactIds.map((artifactId) => ({ artifactId, relation: "renderer_input" })),
            metadata: reviewMetadata(input, check, materials, claim.principalId, key, waveId),
          },
        ],
      };
    },
  );
  if (!attempt.selected || attempt.artifacts.length !== 2) {
    // In particular, do not return orphan output IDs from a stale attempt.
    throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_NOT_SELECTED", `measurement check ${check.id} did not select its exact output artifacts`, { retryable: true });
  }
  const measurementArtifact = attempt.artifacts[0]!;
  const rendererArtifact = attempt.artifacts[1]!;
  validateMeasurementArtifacts(attempt, input, check, materials, key, waveId);
  const value = attempt.adopted
    ? readMeasurementResult(ports.ledger, measurementArtifact, input, check, materials)
    : attempt.value;
  const findings = measurementFindings(value, check, input.manuscriptArtifactId);
  const measurement: ArticleMeasurement = {
    ...value,
    rendererOutputArtifactIds: [rendererArtifact.id],
  };
  const measurementContext = requireAttemptContext(measurementArtifact, key);
  return {
    schemaVersion: "article-review-check-result/2",
    status: "completed",
    waveId,
    checkId: check.id,
    kind: check.kind,
    key,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    materialArtifactIds: materials.artifactIds,
    outputArtifactIds: [measurementArtifact.id, rendererArtifact.id],
    resultArtifactId: measurementArtifact.id,
    reviewerId: "measure_article",
    assessment: findings.length === 0 ? "pass" : "findings",
    findings,
    result: measurement,
    durableContext: measurementContext,
  };
}

function preloadMeasurementArtifacts(
  ledger: ArtifactLedger,
  materials: ArticleMaterialSet,
): ScopedArticleMeasurementArtifactReader {
  const bytesById = new Map<ArtifactId, Uint8Array>();
  for (const material of materials.artifacts) {
    const read = ledger.readArtifact(material.artifactId);
    bytesById.set(material.artifactId, new Uint8Array(read.bytes));
  }
  const artifactIds = Object.freeze([...materials.artifactIds]);
  const read = (artifactId: ArtifactId): Uint8Array => {
    const bytes = bytesById.get(artifactId);
    if (bytes === undefined) {
      throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_GUESSED_READ", `measurement requested artifact ${artifactId} outside its preloaded package`);
    }
    return new Uint8Array(bytes);
  };
  return Object.freeze({
    artifactIds,
    readBytes: async (artifactId: ArtifactId) => read(artifactId),
    readText: async (artifactId: ArtifactId) => Buffer.from(read(artifactId)).toString("utf8"),
  });
}

function validatePanelInput(input: ArticleReviewPanelInput, ledger: ArtifactLedger): void {
  if (input.articleId !== input.materialContext.articleId) throw new ArticleReviewPanelError("REVIEW_ARTICLE_MISMATCH", "review panel article does not match its material context");
  if (!Number.isSafeInteger(input.manuscriptOrdinal) || input.manuscriptOrdinal < 0) throw new ArticleReviewPanelError("REVIEW_ORDINAL_INVALID", "manuscript ordinal must be a non-negative integer");
  if (input.runId.trim().length === 0 || input.articleExecutionId.trim().length === 0) throw new ArticleReviewPanelError("REVIEW_IDENTITY_INVALID", "review panel requires run and article execution identities");
  const manuscript = ledger.requireArtifact(input.manuscriptArtifactId);
  if (manuscript.kind !== "article_manuscript" || manuscript.mediaType !== "text/markdown") throw new ArticleReviewPanelError("REVIEW_MANUSCRIPT_INVALID", "review panel manuscript must be an article Markdown artifact");
  if (manuscript.metadata.articleId !== input.articleId || manuscript.metadata.revisionId !== input.manuscriptRevisionId) throw new ArticleReviewPanelError("REVIEW_MANUSCRIPT_STALE", "review panel manuscript revision does not match immutable metadata");
}

function reviewMaterialPackage(ledger: ArtifactLedger, materials: ArticleMaterialSet, manuscriptRevisionId: ManuscriptRevisionId): ReviewMaterialPackage {
  if (materials.access === "source_blind") {
    // Fail before the first ledger read. This guards against adapters that
    // inspect bytes while composing a package and only validate afterwards.
    assertArticleExecutionMaterials({ articleId: materials.articleId, manuscriptArtifactId: materials.manuscriptArtifactId!, access: "source_blind", materials });
  }
  const entries = materials.artifacts.map((material) => {
    const loaded = ledger.readArtifact(material.artifactId);
    if (loaded.artifact.id !== material.artifactId) throw new ArticleReviewPanelError("REVIEW_MATERIAL_IDENTITY", `material ${material.artifactId} changed while being packaged`);
    return Object.freeze({
      artifactId: material.artifactId,
      articleId: material.articleId,
      classification: material.classification,
      mediaType: loaded.artifact.mediaType,
      digest: loaded.artifact.digest,
      bytes: new Uint8Array(loaded.bytes),
    });
  });
  return Object.freeze({
    schemaVersion: "article-review-material-package/1",
    articleId: materials.articleId,
    access: materials.access as "source_aware" | "source_blind",
    manuscriptArtifactId: materials.manuscriptArtifactId!,
    manuscriptRevisionId,
    artifactIds: Object.freeze([...materials.artifactIds]),
    artifacts: Object.freeze(entries),
  });
}

function validateModelResult(result: ArticleReviewResult, check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>, input: ArticleReviewPanelInput, materials: ArticleMaterialSet, claim: ArticleAttemptClaim): void {
  const parsed = reviewResultSchema.safeParse(result);
  if (!parsed.success) throw new ArticleReviewPanelError("REVIEW_RESULT_SCHEMA", `review check ${check.id} returned an invalid result envelope`);
  if (result.reviewerId !== claim.principalId) throw new ArticleReviewPanelError("REVIEW_PRINCIPAL_MISMATCH", `review check ${check.id} result principal does not match its authenticated claim`);
  if (result.manuscriptArtifactId !== input.manuscriptArtifactId) throw new ArticleReviewPanelError("REVIEW_MANUSCRIPT_MISMATCH", `review check ${check.id} returned a stale manuscript identity`);
  if (result.assessment === "pass" && result.findings.length > 0) throw new ArticleReviewPanelError("REVIEW_ASSESSMENT_INVALID", `review check ${check.id} cannot pass with findings`);
  if (result.assessment === "not_applicable" && result.findings.length > 0) throw new ArticleReviewPanelError("REVIEW_ASSESSMENT_INVALID", `review check ${check.id} cannot report findings as not applicable`);
  const seen = new Set<string>();
  const allowedEvidence = new Set(materials.artifactIds);
  for (const finding of result.findings) {
    if (seen.has(finding.localId)) throw new ArticleReviewPanelError("REVIEW_FINDING_DUPLICATE", `review check ${check.id} repeats finding ${finding.localId}`);
    seen.add(finding.localId);
    for (const evidence of finding.evidenceArtifactIds) {
      if (!allowedEvidence.has(evidence)) throw new ArticleReviewPanelError("REVIEW_EVIDENCE_OUTSIDE_MATERIALS", `review check ${check.id} cites evidence outside its material set`);
    }
  }
}

function readReviewResult(
  ledger: ArtifactLedger,
  artifact: LedgerArtifact,
  input: ArticleReviewPanelInput,
  check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>,
  materials: ArticleMaterialSet,
): ArticleReviewResult {
  const read = ledger.readArtifact(artifact.id);
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(read.bytes).toString("utf8"));
  } catch (error) {
    throw new ArticleReviewPanelError("REVIEW_REPLAY_RESULT_SCHEMA", `review check ${check.id} selected artifact is not valid JSON`, { cause: error });
  }
  const parsed = reviewResultSchema.safeParse(value);
  if (!parsed.success) throw new ArticleReviewPanelError("REVIEW_REPLAY_RESULT_SCHEMA", `review check ${check.id} selected artifact has malformed review data`);
  const result = value as ArticleReviewResult;
  if (result.manuscriptArtifactId !== input.manuscriptArtifactId) {
    throw new ArticleReviewPanelError("REVIEW_MANUSCRIPT_MISMATCH", `review check ${check.id} replayed a stale manuscript identity`);
  }
  const allowedEvidence = new Set(materials.artifactIds);
  const seen = new Set<string>();
  for (const finding of result.findings) {
    validateFinding(finding, check.id);
    if (seen.has(finding.localId)) throw new ArticleReviewPanelError("REVIEW_FINDING_DUPLICATE", `review check ${check.id} repeats finding ${finding.localId}`);
    seen.add(finding.localId);
    if (finding.evidenceArtifactIds.some((evidence) => !allowedEvidence.has(evidence))) {
      throw new ArticleReviewPanelError("REVIEW_EVIDENCE_OUTSIDE_MATERIALS", `review check ${check.id} cites evidence outside its material set`);
    }
  }
  return result;
}

function validateFinding(finding: ArticleReviewFinding, checkId: string): void {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/u.test(finding.localId)) throw new ArticleReviewPanelError("REVIEW_FINDING_ID_INVALID", `review check ${checkId} has an invalid finding ID`);
  if (finding.problem.trim().length === 0 || finding.requestedOutcome.trim().length === 0) throw new ArticleReviewPanelError("REVIEW_FINDING_TEXT_INVALID", `review check ${checkId} has an empty finding`);
  const keys = Object.keys(finding.scope as unknown as Record<string, unknown>);
  const parsed = scopeSchema.safeParse(finding.scope);
  if (!parsed.success || (finding.scope.kind === "span" && finding.scope.end! < finding.scope.start!)) throw new ArticleReviewPanelError("REVIEW_SCOPE_INVALID", `review check ${checkId} has an invalid scope`);
  const uniqueEvidence = new Set(finding.evidenceArtifactIds);
  if (uniqueEvidence.size !== finding.evidenceArtifactIds.length) throw new ArticleReviewPanelError("REVIEW_EVIDENCE_DUPLICATE", `review check ${checkId} repeats finding evidence`);
  void keys;
}

function validateMeasurement(measurement: ArticleMeasurement, check: Extract<ReviewCheckDefinition, { readonly kind: "article_measurement" }>, input: ArticleReviewPanelInput, materials: ArticleMaterialSet): void {
  if (measurement.schemaVersion !== "article-measurement/1" || measurement.articleId !== input.articleId || measurement.manuscriptArtifactId !== input.manuscriptArtifactId) throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_IDENTITY", `measurement check ${check.id} returned a stale manuscript identity`);
  if (measurement.maximumReaderPages !== check.maximumReaderPages || !Number.isSafeInteger(measurement.pageCount) || measurement.pageCount < 0 || typeof measurement.fits !== "boolean" || typeof measurement.openerFits !== "boolean") throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_INVALID", `measurement check ${check.id} returned invalid page data`);
  if (measurement.fits !== (measurement.pageCount <= check.maximumReaderPages)) throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_INVALID", `measurement check ${check.id} returned inconsistent fit data`);
  const expectedInputs = materials.artifacts.filter((artifact) => artifact.classification === "manuscript" || artifact.classification === "measurement_input").map((artifact) => artifact.artifactId);
  if (!sameStrings(measurement.inputArtifactIds, expectedInputs)) throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_INPUTS", `measurement check ${check.id} did not return its exact renderer input sequence`);
}

function readMeasurementResult(
  ledger: ArtifactLedger,
  artifact: LedgerArtifact,
  input: ArticleReviewPanelInput,
  check: Extract<ReviewCheckDefinition, { readonly kind: "article_measurement" }>,
  materials: ArticleMaterialSet,
): ArticleMeasurement {
  const read = ledger.readArtifact(artifact.id);
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(read.bytes).toString("utf8"));
  } catch (error) {
    throw new ArticleReviewPanelError("REVIEW_REPLAY_MEASUREMENT_SCHEMA", `measurement check ${check.id} selected artifact is not valid JSON`, { cause: error });
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ArticleReviewPanelError("REVIEW_REPLAY_MEASUREMENT_SCHEMA", `measurement check ${check.id} selected artifact has malformed measurement data`);
  }
  const measurement = value as ArticleMeasurement;
  validateMeasurement(measurement, check, input, materials);
  return measurement;
}

function validateMeasurementArtifacts(attempt: ArticleAttemptExecutionResult<ArticleMeasurement>, input: ArticleReviewPanelInput, check: Extract<ReviewCheckDefinition, { readonly kind: "article_measurement" }>, materials: ArticleMaterialSet, key: string, waveId: string): void {
  if (!attempt.selected) throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_NOT_SELECTED", "measurement attempt was not selected", { retryable: true });
  const expectedRendererOutputs = [
    {
      kind: "article_measurement_renderer_output",
      schemaVersion: "article-renderer-measurement-output/1",
      mediaType: "application/json",
      payloadKind: "json",
      relation: "renderer_input",
    },
  ] as const;
  if (attempt.artifacts.length !== 1 + expectedRendererOutputs.length) {
    throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_ARTIFACTS", `measurement check ${check.id} output artifacts do not match its declared renderer outputs`, { retryable: true });
  }
  const measurementArtifact = attempt.artifacts[0]!;
  if (
    measurementArtifact.kind !== "article_measurement"
    || measurementArtifact.schemaVersion !== "article-measurement/1"
    || measurementArtifact.mediaType !== "application/json"
    || measurementArtifact.payloadKind !== "json"
    || !sameArtifactParents(measurementArtifact.parents, materials.artifactIds, "measurement_input")
  ) {
    throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_ARTIFACTS", `measurement check ${check.id} result artifact does not match its exact measurement contract`, { retryable: true });
  }
  for (const [index, artifact] of attempt.artifacts.entries()) {
    if (artifact.producingRunId !== input.runId || artifact.metadata.operationKey !== key || artifact.metadata.checkId !== check.id || artifact.metadata.waveId !== waveId) {
      throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_PROVENANCE", `measurement check ${check.id} output artifact has stale provenance`);
    }
    if (index === 0) continue;
    const expected = expectedRendererOutputs[index - 1];
    if (expected === undefined) {
      throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_ARTIFACTS", `measurement check ${check.id} output artifact ${index} is undeclared`, { retryable: true });
    }
    if (
      artifact.kind !== expected.kind
      || artifact.schemaVersion !== expected.schemaVersion
      || artifact.mediaType !== expected.mediaType
      || artifact.payloadKind !== expected.payloadKind
      || !sameArtifactParents(artifact.parents, materials.artifactIds, expected.relation)
    ) {
      throw new ArticleReviewPanelError("REVIEW_MEASUREMENT_ARTIFACTS", `measurement check ${check.id} renderer output artifact ${index} does not match its declared contract`, { retryable: true });
    }
  }
}

function sameArtifactParents(
  parents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
  expectedArtifactIds: readonly ArtifactId[],
  expectedRelation: string,
): boolean {
  return parents.length === expectedArtifactIds.length
    && parents.every((parent, index) => parent.artifactId === expectedArtifactIds[index] && parent.relation === expectedRelation);
}

function validateResultArtifact(artifact: LedgerArtifact, input: ArticleReviewPanelInput, check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>, materials: ArticleMaterialSet, result: ArticleReviewResult, key: string, waveId: string): void {
  if (artifact.kind !== "article_review_result" || artifact.schemaVersion !== "article-review-result/1" || artifact.payloadKind !== "json" || artifact.producingRunId !== input.runId) throw new ArticleReviewPanelError("REVIEW_ARTIFACT_INVALID", `review check ${check.id} result artifact is not run-owned`);
  if (!sameStrings(artifact.parents.map((parent) => parent.artifactId), materials.artifactIds) || artifact.parents.some((parent) => parent.relation !== "review_input")) throw new ArticleReviewPanelError("REVIEW_ARTIFACT_LINEAGE", `review check ${check.id} result parents do not equal its material set`);
  if (artifact.metadata.articleId !== input.articleId || artifact.metadata.checkId !== check.id || artifact.metadata.waveId !== waveId || artifact.metadata.manuscriptArtifactId !== input.manuscriptArtifactId || artifact.metadata.manuscriptRevisionId !== input.manuscriptRevisionId || artifact.metadata.operationKey !== key || artifact.metadata.access !== check.access || artifact.metadata.authority !== check.authority || !sameJsonArray(artifact.metadata.materialArtifactIds, materials.artifactIds)) throw new ArticleReviewPanelError("REVIEW_ARTIFACT_METADATA", `review check ${check.id} result metadata is not exact`);
  if (artifact.digest.length !== 64 || result.manuscriptArtifactId !== input.manuscriptArtifactId) throw new ArticleReviewPanelError("REVIEW_ARTIFACT_PAYLOAD", `review check ${check.id} result payload is invalid`);
  result.findings.forEach((finding) => validateFinding(finding, check.id));
  if (result.authenticatedPrincipalId !== undefined && result.authenticatedPrincipalId !== result.reviewerId ||
      result.checkId !== undefined && result.checkId !== check.id ||
      result.access !== undefined && result.access !== check.access ||
      result.authority !== undefined && result.authority !== check.authority ||
      result.reviewPlanArtifactId !== undefined && result.reviewPlanArtifactId !== input.materialContext.reviewPlan.reviewPlanArtifactId ||
      result.manuscriptRevisionId !== undefined && result.manuscriptRevisionId !== input.manuscriptRevisionId ||
      result.materialArtifactIds !== undefined && !sameStrings(result.materialArtifactIds, materials.artifactIds)) {
    throw new ArticleReviewPanelError("REVIEW_RESULT_PROVENANCE", `review check ${check.id} result does not carry exact authenticated provenance`);
  }
}

function checkpointFromResult(result: ArticleReviewCheckResult): ArticleReviewStepCheckpoint {
  return {
    schemaVersion: "article-review-checkpoint/1",
    status: result.status,
    waveId: result.waveId,
    checkId: result.checkId,
    kind: result.kind,
    key: result.key,
    manuscriptArtifactId: result.manuscriptArtifactId,
    manuscriptRevisionId: result.manuscriptRevisionId,
    materialArtifactIds: result.materialArtifactIds,
    outputArtifactIds: result.outputArtifactIds,
    ...(result.resultArtifactId === undefined ? {} : { resultArtifactId: result.resultArtifactId }),
    ...(result.reviewerId === undefined ? {} : { reviewerId: result.reviewerId }),
    assessment: result.assessment,
    findingArtifactIds: [],
  };
}

function reloadSelectedResult(
  value: unknown,
  input: ArticleReviewPanelInput,
  check: ReviewCheckDefinition,
  waveId: string,
  key: string,
  ledger: ArtifactLedger,
  materialSelection?: ArticleMaterialSelectionContext,
): ArticleReviewCheckResult {
  const parsed = articleReviewStepCheckpointSchema.safeParse(value);
  if (!parsed.success) throw new ArticleReviewPanelError("REVIEW_REPLAY_CHECKPOINT_SCHEMA", `review check ${check.id} replayed malformed checkpoint`);
  const checkpoint = parsed.data as unknown as ArticleReviewStepCheckpoint;
  if (checkpoint.status === "skipped") {
    return {
      schemaVersion: "article-review-check-result/2",
      status: "skipped",
      waveId: checkpoint.waveId,
      checkId: checkpoint.checkId,
      kind: checkpoint.kind,
      key: checkpoint.key,
      manuscriptArtifactId: checkpoint.manuscriptArtifactId,
      manuscriptRevisionId: checkpoint.manuscriptRevisionId,
      materialArtifactIds: checkpoint.materialArtifactIds,
      outputArtifactIds: [],
      assessment: "not_applicable",
      findings: [],
    };
  }
  if (checkpoint.resultArtifactId === undefined || checkpoint.outputArtifactIds.length === 0) {
    throw new ArticleReviewPanelError("REVIEW_REPLAY_RESULT_MISSING", `review check ${check.id} replayed without selected output artifacts`, { retryable: true });
  }
  const selected = checkpoint.outputArtifactIds.map((artifactId) => ledger.getArtifact(artifactId));
  if (selected.some((artifact) => artifact === undefined)) throw new ArticleReviewPanelError("REVIEW_REPLAY_RESULT_STALE", `review check ${check.id} replayed an orphan output artifact`, { retryable: true });
  const artifacts = selected as LedgerArtifact[];
  if (
    artifacts[0]!.id !== checkpoint.resultArtifactId
    || artifacts.some((artifact) => artifact.producingRunId !== input.runId || artifact.metadata.operationKey !== key || artifact.metadata.waveId !== waveId)
  ) throw new ArticleReviewPanelError("REVIEW_REPLAY_RESULT_STALE", `review check ${check.id} replayed stale output provenance`, { retryable: true });
  const materials = selectArticleReviewerMaterials(input.materialContext, check, input.manuscriptArtifactId, materialSelection);
  if (!sameStrings(checkpoint.materialArtifactIds, materials.artifactIds)) throw new ArticleReviewPanelError("REVIEW_REPLAY_MATERIAL_MISMATCH", `review check ${check.id} replayed a different material set`, { retryable: true });
  if (check.kind === "model_review") {
    const result = readReviewResult(ledger, artifacts[0]!, input, check, materials);
    validateResultArtifact(artifacts[0]!, input, check, materials, result, key, waveId);
    return {
      schemaVersion: "article-review-check-result/2",
      status: "completed",
      waveId,
      checkId: check.id,
      kind: check.kind,
      key,
      manuscriptArtifactId: input.manuscriptArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      materialArtifactIds: materials.artifactIds,
      outputArtifactIds: [artifacts[0]!.id],
      resultArtifactId: artifacts[0]!.id,
      reviewerId: result.reviewerId,
      assessment: result.assessment,
      findings: result.findings,
      result,
      durableContext: requireAttemptContext(artifacts[0]!, key),
    };
  }
  if (artifacts.length !== 2) throw new ArticleReviewPanelError("REVIEW_REPLAY_RESULT_MISSING", `measurement check ${check.id} replayed without its renderer output`, { retryable: true });
  const measurement = readMeasurementResult(ledger, artifacts[0]!, input, check, materials);
  const findings = measurementFindings(measurement, check, input.manuscriptArtifactId);
  validateMeasurementArtifacts({ selected: true, value: measurement, claim: undefined as never, artifacts }, input, check, materials, key, waveId);
  return {
    schemaVersion: "article-review-check-result/2",
    status: "completed",
    waveId,
    checkId: check.id,
    kind: check.kind,
    key,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    materialArtifactIds: materials.artifactIds,
    outputArtifactIds: artifacts.map((artifact) => artifact.id),
    resultArtifactId: artifacts[0]!.id,
    reviewerId: "measure_article",
    assessment: findings.length === 0 ? "pass" : "findings",
    findings,
    result: { ...measurement, rendererOutputArtifactIds: [artifacts[1]!.id] },
    durableContext: requireAttemptContext(artifacts[0]!, key),
  };
}

function requireAttemptContext(artifact: LedgerArtifact, key: string): WorkflowAttemptContext {
  const context = artifact.durableContext;
  if (context === undefined || (context.kind !== "step" && context.kind !== "agent") || context.key !== key || context.callId.length === 0 || context.attemptId.length === 0 || !Number.isSafeInteger(context.attemptNumber)) throw new ArticleReviewPanelError("REVIEW_PROVENANCE_INVALID", `review check ${key} result has incomplete Loops attempt provenance`);
  return context;
}

function reviewMaterialArtifactIds(materials: ArticleMaterialSet): readonly ArtifactId[] {
  return materials.artifactIds;
}

function reviewMetadata(input: ArticleReviewPanelInput, check: ReviewCheckDefinition, materials: ArticleMaterialSet, principalId: string, operationKey: string, waveId: string): JsonObject {
  return {
    articleId: input.articleId,
    checkId: check.id,
    waveId,
    reviewerId: principalId,
    authenticatedPrincipalId: principalId,
    access: check.kind === "model_review" ? check.access : "source_blind",
    ...(check.kind === "model_review" ? { authority: check.authority } : {}),
    operationKey,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
    materialArtifactIds: reviewMaterialArtifactIds(materials) as unknown as JsonValue,
  };
}

function reviewStepInput(input: ArticleReviewPanelInput, check: ReviewCheckDefinition, waveId: string, key: string): JsonObject {
  const materials = selectArticleReviewerMaterials(input.materialContext, check, input.manuscriptArtifactId, input.materialSelection);
  const value = {
    schemaVersion: "article-review-step-input/1" as const,
    key,
    runId: input.runId,
    articleExecutionId: input.articleExecutionId,
    articleId: input.articleId,
    manuscriptOrdinal: input.manuscriptOrdinal,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
    waveId,
    checkId: check.id,
    checkKind: check.kind,
    access: check.kind === "article_measurement" ? "tool" as const : check.access,
    materialArtifactIds: materials.artifactIds,
  };
  const parsed = articleReviewStepInputSchema.parse(value);
  return parsed as unknown as JsonObject;
}

function skippedResult(input: ArticleReviewPanelInput, check: ReviewCheckDefinition, waveId: string, reason: string): ArticleReviewCheckResult {
  const key = reviewKey({
    articleExecutionId: input.articleExecutionId,
    reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    waveId,
    checkId: check.id,
  });
  const materials = selectArticleReviewerMaterials(input.materialContext, check, input.manuscriptArtifactId, input.materialSelection);
  return {
    schemaVersion: "article-review-check-result/2",
    status: "skipped",
    waveId,
    checkId: check.id,
    kind: check.kind,
    key,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    materialArtifactIds: materials.artifactIds,
    outputArtifactIds: [],
    assessment: "not_applicable",
    findings: [],
    skipReason: reason,
  };
}

function shouldStopAfter(wave: ReviewWave, check: ReviewCheckDefinition, result: ArticleReviewCheckResult): boolean {
  if (wave.stopAfter === "never" || result.status !== "completed") return false;
  if (wave.stopAfter === "human_required") return result.assessment === "human_required";
  if (result.assessment === "human_required") return true;
  if (check.kind === "article_measurement") return result.assessment === "findings";
  return check.authority === "blocking" && result.findings.some((finding) => finding.severity === "must_fix");
}

function measurementFindings(measurement: ArticleMeasurement, check: Extract<ReviewCheckDefinition, { readonly kind: "article_measurement" }>, manuscriptArtifactId: ArtifactId): readonly ArticleReviewFinding[] {
  const findings: ArticleReviewFinding[] = [];
  if (!measurement.fits) findings.push({ localId: "measure.page_count", severity: "must_fix", scope: { kind: "document" }, problem: `The article is ${measurement.pageCount} reader pages, above the ${check.maximumReaderPages}-page limit.`, requestedOutcome: "Reduce the article to the pinned reader-page limit.", evidenceArtifactIds: [manuscriptArtifactId] });
  if (!measurement.openerFits) findings.push({ localId: "measure.opener", severity: "must_fix", scope: { kind: "document" }, problem: "The article opener does not fit the production profile.", requestedOutcome: "Revise the opening so the title, label, and byline fit the opener.", evidenceArtifactIds: [manuscriptArtifactId] });
  return Object.freeze(findings);
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function sameJsonArray(value: unknown, expected: readonly string[]): boolean {
  return Array.isArray(value) && value.length === expected.length && value.every((candidate, index) => candidate === expected[index]);
}
