import { z } from "zod";

import { createHash } from "node:crypto";

import type { ArticleExecutionId, ArtifactId, ManuscriptRevisionId } from "../contracts/index.ts";
import type { ResolvedReviewPlan, ReviewCheckDefinition } from "../contracts/production-plan.ts";
import type {
  ArticleReviewCheckResult,
  ArticleReviewFinding,
  ManuscriptScope,
} from "../workflows/article-review-panel.ts";
import type { ArticleMeasurement } from "../workflows/internal-types.ts";

/** The stable identity of a finding is the producing result plus its local ID. */
export type ArticleFindingId = string;

export type NormalizedReviewFinding = {
  readonly schemaVersion: "article-review-finding/1";
  /** Canonical identity. Keep this field; do not reconstruct it at decision time. */
  readonly findingId: ArticleFindingId;
  readonly reviewResultArtifactId: ArtifactId;
  readonly localId: string;
  readonly reviewerId: string;
  readonly waveId: string;
  readonly checkId: string;
  readonly kind: "model_review" | "article_measurement";
  readonly authority: "advisory" | "blocking" | "human_required";
  readonly severity: "must_fix" | "consider";
  readonly scope: ManuscriptScope;
  readonly problem: string;
  readonly requestedOutcome: string;
  readonly evidenceArtifactIds: readonly ArtifactId[];
};

/** One lossless, deterministic feedback package for one exact manuscript. */
export type RevisionBrief = {
  readonly schemaVersion: "article-revision-brief/1";
  readonly articleId: string;
  readonly iterationId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly mustFix: readonly NormalizedReviewFinding[];
  readonly consider: readonly NormalizedReviewFinding[];
  readonly humanRulings: readonly ArtifactId[];
  /** Model-result artifacts, in declared review-plan order. */
  readonly reviewResultArtifactIds: readonly ArtifactId[];
  readonly measurementArtifactId: ArtifactId;
  /** Renderer and other check outputs, excluding the result IDs above. */
  readonly reviewOutputArtifactIds: readonly ArtifactId[];
  /** The immutable identity of this review cycle, when launched by the article runtime. */
  readonly cycleId?: string;
  readonly manuscriptRevisionId?: ManuscriptRevisionId;
  readonly reviewPlanArtifactId?: ArtifactId;
  readonly rewriteOrdinal?: number;
};

export type RevisionBriefInput = {
  readonly articleId: string;
  readonly iterationId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId?: ManuscriptRevisionId;
  readonly reviewPlan: ResolvedReviewPlan;
  readonly reviewResults: readonly ArticleReviewCheckResult[];
  readonly measurementArtifactId?: ArtifactId;
  readonly humanRulings?: readonly ArtifactId[];
  /** Runtime identity inputs. They are optional for standalone pure-function callers. */
  readonly articleExecutionId?: ArticleExecutionId;
  readonly reviewPlanArtifactId?: ArtifactId;
  readonly rewriteOrdinal?: number;
  readonly cycleId?: string;
};

export type RevisionBriefParentsInput = {
  readonly brief: RevisionBrief;
};

export type ArticleRewriteBudget = {
  /** Number of writer rewrites already consumed, excluding the initial draft. */
  readonly rewritesUsed: number;
  /** Maximum number of writer rewrites allowed by the immutable profile. */
  readonly maximumRewrites: number;
};

export type ArticleReviewRouteReason =
  | "clean"
  | "human_required"
  | "changes_required"
  | "rewrite_budget_exhausted";

export type ArticleReviewRoute = {
  readonly schemaVersion: "article-review-route/1";
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly iterationId: string;
  readonly outcome: "auto_rewrite" | "editor_wait";
  readonly reason: ArticleReviewRouteReason;
  readonly effectiveMustFixFindingIds: readonly ArticleFindingId[];
  readonly effectiveConsiderFindingIds: readonly ArticleFindingId[];
  readonly humanRequiredFindingIds: readonly ArticleFindingId[];
  readonly rewriteBudget: {
    readonly rewritesUsed: number;
    readonly maximumRewrites: number;
    readonly remainingRewrites: number;
    /** Makes it explicit that Loops/provider attempts do not consume this count. */
    readonly counts: "writer_rewrites_only";
  };
  readonly allowedChoices: readonly ["accept", "revise", "drop"] | [];
  readonly acceptRequiresApprovedFindingIds: boolean;
  readonly reviseRequiresAdditionalRewriteBudget: boolean;
  readonly cycleId?: string;
  readonly manuscriptRevisionId?: ManuscriptRevisionId;
  readonly reviewPlanArtifactId?: ArtifactId;
  readonly rewriteOrdinal?: number;
};

export type ArticleReviewCycleIdentity = {
  readonly articleExecutionId: ArticleExecutionId | string;
  readonly manuscriptRevisionId: ManuscriptRevisionId | string;
  readonly reviewPlanArtifactId: ArtifactId | string;
  readonly rewriteOrdinal: number;
};

/** Stable identity for one manuscript/review-plan/rewrite cycle. */
export function articleReviewCycleId(input: ArticleReviewCycleIdentity): string {
  if (input.articleExecutionId.trim().length === 0 || input.manuscriptRevisionId.trim().length === 0 || input.reviewPlanArtifactId.trim().length === 0) {
    throw new ArticleReviewCycleError("CYCLE_ID_INVALID", "review cycle identity requires article execution, manuscript revision, and review plan identities");
  }
  if (!Number.isSafeInteger(input.rewriteOrdinal) || input.rewriteOrdinal < 0) {
    throw new ArticleReviewCycleError("CYCLE_ID_INVALID", "review cycle rewrite ordinal must be a non-negative safe integer");
  }
  const preimage = JSON.stringify({
    schemaVersion: "article-review-cycle/1",
    articleExecutionId: input.articleExecutionId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    reviewPlanArtifactId: input.reviewPlanArtifactId,
    rewriteOrdinal: input.rewriteOrdinal,
  });
  return `cycle-${createHash("sha256").update(preimage, "utf8").digest("hex").slice(0, 32)}`;
}

export type ArticleEditorDecision = {
  readonly choice: "accept" | "revise" | "drop";
  /** Canonical finding IDs, not reviewer-local IDs. */
  readonly approvedFindingIds?: readonly ArticleFindingId[];
  /** New writer rewrites granted by the editor. */
  readonly additionalRewriteBudget?: number;
};

export const ARTICLE_EDITOR_DECISION_VALIDATOR_VERSION = "article-editor-decision-validator/1" as const;

export type ArticleDecisionBudgetSnapshot = {
  readonly rewritesUsed: number;
  readonly maximumRewrites: number;
  readonly remainingRewrites: number;
  readonly additionalRewriteBudget: number;
  readonly counts: "writer_rewrites_only";
};

export type ValidatedArticleEditorDecision = {
  readonly validatorVersion: string;
  readonly canonicalApprovedFindingIds: readonly ArticleFindingId[];
  readonly rewriteBudget: ArticleDecisionBudgetSnapshot;
};

/** The exact immutable task offered to an editor for one review cycle. */
export type ArticleDecisionTask = {
  readonly schemaVersion: "article-decision-task/1";
  readonly runId: string;
  readonly articleExecutionId: string;
  readonly articleId: string;
  readonly cycleId: string;
  readonly iterationId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly rewriteOrdinal: number;
  readonly revisionBriefArtifactId: ArtifactId;
  readonly routeArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly expectedDecisionArtifactId: ArtifactId;
  readonly allowedChoices: readonly ["accept", "revise", "drop"];
};

export class ArticleReviewCycleError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ArticleReviewCycleError";
    this.code = code;
  }
}

const component = z.string().min(1).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/u);
const artifactId = z.string().min(1);
const scopeSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("document") }).strict(),
  z.object({ kind: z.literal("heading"), headingId: component }).strict(),
  z.object({ kind: z.literal("paragraph"), headingId: component.optional(), ordinal: z.number().int().nonnegative() }).strict(),
  z.object({ kind: z.literal("span"), headingId: component.optional(), start: z.number().int().nonnegative(), end: z.number().int().nonnegative() }).strict(),
]);

export const normalizedReviewFindingSchema = z.object({
  schemaVersion: z.literal("article-review-finding/1"),
  findingId: artifactId,
  reviewResultArtifactId: artifactId,
  localId: component,
  reviewerId: artifactId,
  waveId: component,
  checkId: component,
  kind: z.enum(["model_review", "article_measurement"]),
  authority: z.enum(["advisory", "blocking", "human_required"]),
  severity: z.enum(["must_fix", "consider"]),
  scope: scopeSchema,
  problem: z.string().min(1),
  requestedOutcome: z.string().min(1),
  evidenceArtifactIds: z.array(artifactId),
}).strict();

export const revisionBriefSchema = z.object({
  schemaVersion: z.literal("article-revision-brief/1"),
  articleId: artifactId,
  iterationId: artifactId,
  manuscriptArtifactId: artifactId,
  mustFix: z.array(normalizedReviewFindingSchema),
  consider: z.array(normalizedReviewFindingSchema),
  humanRulings: z.array(artifactId),
  reviewResultArtifactIds: z.array(artifactId),
  measurementArtifactId: artifactId,
  reviewOutputArtifactIds: z.array(artifactId),
  cycleId: artifactId.optional(),
  manuscriptRevisionId: artifactId.optional(),
  reviewPlanArtifactId: artifactId.optional(),
  rewriteOrdinal: z.number().int().nonnegative().optional(),
}).strict();

export const articleReviewRouteSchema = z.object({
  schemaVersion: z.literal("article-review-route/1"),
  articleId: artifactId,
  manuscriptArtifactId: artifactId,
  iterationId: artifactId,
  outcome: z.enum(["auto_rewrite", "editor_wait"]),
  reason: z.enum(["clean", "human_required", "changes_required", "rewrite_budget_exhausted"]),
  effectiveMustFixFindingIds: z.array(artifactId),
  effectiveConsiderFindingIds: z.array(artifactId),
  humanRequiredFindingIds: z.array(artifactId),
  rewriteBudget: z.object({
    rewritesUsed: z.number().int().nonnegative(),
    maximumRewrites: z.number().int().nonnegative(),
    remainingRewrites: z.number().int().nonnegative(),
    counts: z.literal("writer_rewrites_only"),
  }).strict(),
  allowedChoices: z.array(z.enum(["accept", "revise", "drop"])),
  acceptRequiresApprovedFindingIds: z.boolean(),
  reviseRequiresAdditionalRewriteBudget: z.boolean(),
  cycleId: artifactId.optional(),
  manuscriptRevisionId: artifactId.optional(),
  reviewPlanArtifactId: artifactId.optional(),
  rewriteOrdinal: z.number().int().nonnegative().optional(),
}).strict();

export const articleEditorDecisionSchema = z.object({
  choice: z.enum(["accept", "revise", "drop"]),
  approvedFindingIds: z.array(artifactId).optional(),
  additionalRewriteBudget: z.number().int().positive().optional(),
}).strict();

export const articleDecisionTaskSchema = z.object({
  schemaVersion: z.literal("article-decision-task/1"),
  runId: artifactId,
  articleExecutionId: artifactId,
  articleId: artifactId,
  cycleId: artifactId,
  iterationId: artifactId,
  manuscriptArtifactId: artifactId,
  manuscriptRevisionId: artifactId,
  reviewPlanArtifactId: artifactId,
  rewriteOrdinal: z.number().int().nonnegative(),
  revisionBriefArtifactId: artifactId,
  routeArtifactId: artifactId,
  inputArtifactIds: z.array(artifactId),
  expectedDecisionArtifactId: artifactId,
  allowedChoices: z.tuple([z.literal("accept"), z.literal("revise"), z.literal("drop")]),
}).strict();

export function parseArticleDecisionTask(value: unknown): ArticleDecisionTask {
  const parsed = articleDecisionTaskSchema.safeParse(value);
  if (!parsed.success) throw new ArticleReviewCycleError("DECISION_TASK_SCHEMA", "article decision task is not a strict article-decision-task/1 value");
  return parsed.data as unknown as ArticleDecisionTask;
}

/**
 * Compile all results for one manuscript into one stable, lossless brief.
 * Plan authority is read from `reviewPlan`; reviewer payload authority is not
 * trusted for routing.
 */
export function compileRevisionBrief(input: RevisionBriefInput): RevisionBrief {
  assertText(input.articleId, "articleId");
  assertText(input.iterationId, "iterationId");
  assertText(input.manuscriptArtifactId, "manuscriptArtifactId");
  const checks = declaredChecks(input.reviewPlan);
  const byId = new Map(checks.map((check) => [check.id, check]));
  const seenChecks = new Set<string>();
  const orderedResults: ArticleReviewCheckResult[] = [];
  for (const result of input.reviewResults) {
    if (seenChecks.has(result.checkId)) throw new ArticleReviewCycleError("REVIEW_RESULT_DUPLICATE", `review check ${result.checkId} appears more than once`);
    seenChecks.add(result.checkId);
    const check = byId.get(result.checkId);
    if (check === undefined) throw new ArticleReviewCycleError("REVIEW_CHECK_UNKNOWN", `review result ${result.checkId} is not declared by the review plan`);
    if (result.manuscriptArtifactId !== input.manuscriptArtifactId) throw new ArticleReviewCycleError("REVIEW_MANUSCRIPT_MISMATCH", `review result ${result.checkId} names another manuscript`);
    if (input.manuscriptRevisionId !== undefined && result.manuscriptRevisionId !== input.manuscriptRevisionId) throw new ArticleReviewCycleError("REVIEW_REVISION_MISMATCH", `review result ${result.checkId} names another manuscript revision`);
    if (result.kind !== check.kind) throw new ArticleReviewCycleError("REVIEW_KIND_MISMATCH", `review result ${result.checkId} has the wrong check kind`);
    if (result.status === "completed" && result.resultArtifactId === undefined) throw new ArticleReviewCycleError("REVIEW_RESULT_ARTIFACT_MISSING", `review result ${result.checkId} has no result artifact`);
  }
  for (const check of checks) {
    const result = input.reviewResults.find((candidate) => candidate.checkId === check.id);
    if (result !== undefined) orderedResults.push(result);
  }

  const measurementResults = orderedResults.filter((result) => result.kind === "article_measurement" && result.status === "completed");
  if (measurementResults.length !== 1) throw new ArticleReviewCycleError("MEASUREMENT_RESULT_INVALID", "a review cycle requires exactly one completed article measurement");
  const measurementResult = measurementResults[0]!;
  const measurementArtifactId = input.measurementArtifactId ?? measurementResult.resultArtifactId;
  if (measurementArtifactId === undefined || measurementResult.resultArtifactId !== measurementArtifactId) throw new ArticleReviewCycleError("MEASUREMENT_ARTIFACT_MISMATCH", "measurement artifact is not the selected measurement result");

  const reviewResultArtifactIds: ArtifactId[] = [];
  const reviewOutputArtifactIds: ArtifactId[] = [];
  const normalized: NormalizedReviewFinding[] = [];
  let humanRulings = [...(input.humanRulings ?? [])];
  assertUnique(humanRulings, "human ruling artifacts");
  for (const result of orderedResults) {
    if (result.status !== "completed" || result.resultArtifactId === undefined) continue;
    if (result.kind === "model_review") reviewResultArtifactIds.push(result.resultArtifactId);
    for (const outputArtifactId of result.outputArtifactIds) {
      if (outputArtifactId !== result.resultArtifactId && !reviewResultArtifactIds.includes(outputArtifactId) && !reviewOutputArtifactIds.includes(outputArtifactId)) reviewOutputArtifactIds.push(outputArtifactId);
    }
    const check = byId.get(result.checkId)!;
    const authority = check.kind === "article_measurement" ? "blocking" as const : check.authority;
    const reviewerId = result.reviewerId ?? check.id;
    const measurement = result.kind === "article_measurement" ? measurementValue(result.result, result.checkId) : undefined;
    const findings = result.kind === "article_measurement" && measurement !== undefined
      ? measurementFailureFindings(result.findings, measurement, check)
      : result.findings;
    for (const finding of findings) {
      normalized.push(normalizeFinding({ result, finding, authority, reviewerId, measurement: result.kind === "article_measurement" }));
    }
  }

  // Result order is plan order. Finding order is severity then immutable scope;
  // no text-based or semantic deduplication is performed.
  normalized.sort((left, right) => findingOrder(left, right, checks));
  const brief: RevisionBrief = {
    schemaVersion: "article-revision-brief/1",
    articleId: input.articleId,
    iterationId: input.iterationId,
    manuscriptArtifactId: input.manuscriptArtifactId,
    mustFix: Object.freeze(normalized.filter((finding) => finding.severity === "must_fix")),
    consider: Object.freeze(normalized.filter((finding) => finding.severity === "consider")),
    humanRulings: Object.freeze(humanRulings),
    reviewResultArtifactIds: Object.freeze(reviewResultArtifactIds),
    measurementArtifactId,
    reviewOutputArtifactIds: Object.freeze(reviewOutputArtifactIds),
    ...(input.cycleId === undefined ? {} : { cycleId: input.cycleId }),
    ...(input.manuscriptRevisionId === undefined ? {} : { manuscriptRevisionId: input.manuscriptRevisionId }),
    ...(input.reviewPlanArtifactId === undefined ? {} : { reviewPlanArtifactId: input.reviewPlanArtifactId }),
    ...(input.rewriteOrdinal === undefined ? {} : { rewriteOrdinal: input.rewriteOrdinal }),
  };
  const parsed = revisionBriefSchema.safeParse(brief);
  if (!parsed.success) throw new ArticleReviewCycleError("REVISION_BRIEF_SCHEMA", "compiled revision brief does not match its strict schema");
  return Object.freeze(brief);
}

/** Exact immutable parent order for a revision brief artifact. */
export function revisionBriefParents(input: RevisionBriefParentsInput): readonly ArtifactId[] {
  const values = [
    input.brief.manuscriptArtifactId,
    ...input.brief.reviewResultArtifactIds,
    input.brief.measurementArtifactId,
    ...input.brief.reviewOutputArtifactIds,
    ...input.brief.humanRulings,
  ];
  assertUnique(values, "revision brief parents");
  return Object.freeze(values);
}

/** Stable bytes are useful for the artifact payload and byte-stability tests. */
export function revisionBriefBytes(brief: RevisionBrief): Uint8Array {
  const parsed = revisionBriefSchema.safeParse(brief);
  if (!parsed.success) throw new ArticleReviewCycleError("REVISION_BRIEF_SCHEMA", "revision brief does not match its strict schema");
  return new TextEncoder().encode(JSON.stringify(brief));
}

/** Derive routing from plan authority, result assessment/findings, measurement, and budget only. */
export function deriveArticleReviewRoute(input: {
  readonly brief: RevisionBrief;
  readonly reviewPlan: ResolvedReviewPlan;
  readonly reviewResults: readonly ArticleReviewCheckResult[];
  readonly rewriteBudget: ArticleRewriteBudget;
}): ArticleReviewRoute {
  const { brief, reviewPlan, reviewResults } = input;
  const parsedBrief = revisionBriefSchema.safeParse(brief);
  if (!parsedBrief.success) throw new ArticleReviewCycleError("REVISION_BRIEF_SCHEMA", "route input brief is invalid");
  validateBudget(input.rewriteBudget);
  const checks = declaredChecks(reviewPlan);
  const results = new Map(reviewResults.map((result) => [result.checkId, result]));
  const effectiveMustFix: ArticleFindingId[] = [];
  const effectiveConsider: ArticleFindingId[] = [];
  const humanRequired: ArticleFindingId[] = [];
  let humanRequiredOutcome = false;
  for (const check of checks) {
    const result = results.get(check.id);
    if (result === undefined || result.status !== "completed") continue;
    const authority = check.kind === "article_measurement" ? "blocking" as const : check.authority;
    if (result.assessment === "human_required") {
      if (authority === "advisory") throw new ArticleReviewCycleError("ADVISORY_HUMAN_REQUIRED", `advisory review ${check.id} cannot require a human`);
      humanRequiredOutcome = true;
      for (const finding of result.findings) humanRequired.push(findingId(result.resultArtifactId, finding.localId));
      continue;
    }
    if (check.kind === "article_measurement") {
      const measurement = measurementValue(result.result, check.id);
      if (measurement === undefined || !measurementPasses(measurement, check)) {
        for (const finding of [...brief.mustFix, ...brief.consider]) if (finding.checkId === check.id) effectiveMustFix.push(finding.findingId);
      }
      continue;
    }
    if (authority === "advisory") {
      if (result.findings.some((finding) => finding.severity === "must_fix")) throw new ArticleReviewCycleError("ADVISORY_MUST_FIX", `advisory review ${check.id} returned a must-fix finding`);
      for (const finding of result.findings) if (finding.severity === "consider") effectiveConsider.push(findingId(result.resultArtifactId, finding.localId));
      continue;
    }
    for (const finding of result.findings) {
      const id = findingId(result.resultArtifactId, finding.localId);
      if (finding.severity === "must_fix") effectiveMustFix.push(id);
      else effectiveConsider.push(id);
    }
  }
  // Keep route IDs in the same deterministic order as the brief, including
  // measurement failures and findings not emitted by a malformed adapter.
  const briefOrder = [...brief.mustFix, ...brief.consider].map((finding) => finding.findingId);
  const order = (ids: readonly string[]) => Object.freeze(briefOrder.filter((id) => ids.includes(id)));
  const mustFix = order(effectiveMustFix);
  const consider = order(effectiveConsider);
  const human = order(humanRequired);
  const remaining = input.rewriteBudget.maximumRewrites - input.rewriteBudget.rewritesUsed;
  const reason: ArticleReviewRouteReason = humanRequiredOutcome
    ? "human_required"
    : mustFix.length === 0
      ? "clean"
      : remaining > 0
        ? "changes_required"
        : "rewrite_budget_exhausted";
  const outcome = reason === "changes_required" ? "auto_rewrite" : "editor_wait";
  const route: ArticleReviewRoute = {
    schemaVersion: "article-review-route/1",
    articleId: brief.articleId,
    manuscriptArtifactId: brief.manuscriptArtifactId,
    iterationId: brief.iterationId,
    outcome,
    reason,
    effectiveMustFixFindingIds: mustFix,
    effectiveConsiderFindingIds: consider,
    humanRequiredFindingIds: human,
    rewriteBudget: {
      rewritesUsed: input.rewriteBudget.rewritesUsed,
      maximumRewrites: input.rewriteBudget.maximumRewrites,
      remainingRewrites: remaining,
      counts: "writer_rewrites_only",
    },
    allowedChoices: outcome === "editor_wait" ? ["accept", "revise", "drop"] : [],
    acceptRequiresApprovedFindingIds: mustFix.length > 0,
    reviseRequiresAdditionalRewriteBudget: remaining <= 0,
    ...(brief.cycleId === undefined ? {} : { cycleId: brief.cycleId }),
    ...(brief.manuscriptRevisionId === undefined ? {} : { manuscriptRevisionId: brief.manuscriptRevisionId }),
    ...(brief.reviewPlanArtifactId === undefined ? {} : { reviewPlanArtifactId: brief.reviewPlanArtifactId }),
    ...(brief.rewriteOrdinal === undefined ? {} : { rewriteOrdinal: brief.rewriteOrdinal }),
  };
  const parsed = articleReviewRouteSchema.safeParse(route);
  if (!parsed.success) throw new ArticleReviewCycleError("ROUTE_SCHEMA", "derived route does not match its strict schema");
  return Object.freeze(route);
}

/** Validate the exact editor response against the route's authority. */
export function validateArticleEditorDecision(route: ArticleReviewRoute, decision: ArticleEditorDecision): void {
  const parsedRoute = articleReviewRouteSchema.safeParse(route);
  if (!parsedRoute.success) throw new ArticleReviewCycleError("ROUTE_SCHEMA", "editor decision route is invalid");
  const parsedDecision = articleEditorDecisionSchema.safeParse(decision);
  if (!parsedDecision.success) throw new ArticleReviewCycleError("EDITOR_DECISION_SCHEMA", "editor decision is invalid");
  if (!(route.allowedChoices as readonly string[]).includes(decision.choice)) throw new ArticleReviewCycleError("EDITOR_CHOICE_INVALID", `editor choice ${decision.choice} is not allowed for route ${route.reason}`);
  const approved = decision.approvedFindingIds ?? [];
  assertUnique(approved, "approved finding IDs");
  if (decision.choice === "accept") {
    if (decision.additionalRewriteBudget !== undefined) throw new ArticleReviewCycleError("EDITOR_BUDGET_INVALID", "additional rewrite budget is only valid with revise");
    const expected = [...route.effectiveMustFixFindingIds];
    if (approved.length !== expected.length || approved.some((id, index) => id !== expected[index])) {
      throw new ArticleReviewCycleError("EDITOR_APPROVALS_REQUIRED", "accepting blockers requires every exact effective finding ID");
    }
    return;
  }
  if (decision.choice === "drop") {
    if (approved.length > 0 || decision.additionalRewriteBudget !== undefined) throw new ArticleReviewCycleError("EDITOR_DECISION_EXTRA_FIELDS", "drop cannot approve findings or change rewrite budget");
    return;
  }
  if (approved.length > 0) throw new ArticleReviewCycleError("EDITOR_DECISION_EXTRA_FIELDS", "revise cannot approve findings");
  if (route.reviseRequiresAdditionalRewriteBudget) {
    if (decision.additionalRewriteBudget === undefined || decision.additionalRewriteBudget <= 0) throw new ArticleReviewCycleError("EDITOR_BUDGET_REQUIRED", "revise after rewrite exhaustion must grant additional rewrite budget");
  } else if (decision.additionalRewriteBudget !== undefined) {
    throw new ArticleReviewCycleError("EDITOR_BUDGET_INVALID", "additional rewrite budget is not allowed while rewrite budget remains");
  }
}

/** Canonical persisted validation facts for an editor response. */
export function validatedArticleEditorDecision(
  route: ArticleReviewRoute,
  decision: ArticleEditorDecision,
): ValidatedArticleEditorDecision {
  validateArticleEditorDecision(route, decision);
  const canonicalApprovedFindingIds = decision.choice === "accept"
    ? Object.freeze([...(decision.approvedFindingIds ?? [])])
    : Object.freeze([] as ArticleFindingId[]);
  return {
    validatorVersion: ARTICLE_EDITOR_DECISION_VALIDATOR_VERSION,
    canonicalApprovedFindingIds,
    rewriteBudget: {
      rewritesUsed: route.rewriteBudget.rewritesUsed,
      maximumRewrites: route.rewriteBudget.maximumRewrites,
      remainingRewrites: route.rewriteBudget.remainingRewrites,
      additionalRewriteBudget: decision.additionalRewriteBudget ?? 0,
      counts: "writer_rewrites_only",
    },
  };
}

/** Verify that a resumed workflow is using the exact persisted validation, not a reinterpreted choice. */
export function assertValidatedArticleEditorDecision(
  route: ArticleReviewRoute,
  decision: ArticleEditorDecision & Partial<ValidatedArticleEditorDecision>,
): asserts decision is ArticleEditorDecision & ValidatedArticleEditorDecision {
  const baseDecision: ArticleEditorDecision = {
    choice: decision.choice,
    ...(decision.approvedFindingIds === undefined ? {} : { approvedFindingIds: decision.approvedFindingIds }),
    ...(decision.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: decision.additionalRewriteBudget }),
  };
  const expected = validatedArticleEditorDecision(route, baseDecision);
  if (decision.validatorVersion !== expected.validatorVersion) throw new ArticleReviewCycleError("DECISION_VALIDATION_MISSING", "persisted editor decision has no supported validator version");
  if (!sameStrings(decision.canonicalApprovedFindingIds ?? [], expected.canonicalApprovedFindingIds)) throw new ArticleReviewCycleError("DECISION_VALIDATION_TAMPERED", "persisted editor approvals are not the canonical approvals validated for the route");
  const actualBudget = decision.rewriteBudget;
  if (actualBudget === undefined || JSON.stringify(actualBudget) !== JSON.stringify(expected.rewriteBudget)) throw new ArticleReviewCycleError("DECISION_VALIDATION_TAMPERED", "persisted editor rewrite budget does not match the validated route");
}

export function findingId(reviewResultArtifactId: ArtifactId | undefined, localId: string): ArticleFindingId {
  if (reviewResultArtifactId === undefined || reviewResultArtifactId.trim().length === 0) throw new ArticleReviewCycleError("FINDING_ID_INVALID", "a finding requires its producing result artifact ID");
  if (localId.trim().length === 0) throw new ArticleReviewCycleError("FINDING_ID_INVALID", "a finding requires a local ID");
  return `${reviewResultArtifactId}#${localId}`;
}

function normalizeFinding(input: {
  readonly result: ArticleReviewCheckResult;
  readonly finding: ArticleReviewFinding;
  readonly authority: "advisory" | "blocking" | "human_required";
  readonly reviewerId: string;
  readonly measurement: boolean;
}): NormalizedReviewFinding {
  if (input.result.resultArtifactId === undefined) throw new ArticleReviewCycleError("FINDING_RESULT_MISSING", `finding ${input.finding.localId} has no producing review artifact`);
  const value: NormalizedReviewFinding = {
    schemaVersion: "article-review-finding/1",
    findingId: findingId(input.result.resultArtifactId, input.finding.localId),
    reviewResultArtifactId: input.result.resultArtifactId,
    localId: input.finding.localId,
    reviewerId: input.reviewerId,
    waveId: input.result.waveId,
    checkId: input.result.checkId,
    kind: input.measurement ? "article_measurement" : "model_review",
    authority: input.authority,
    severity: input.finding.severity,
    scope: input.finding.scope,
    problem: input.finding.problem,
    requestedOutcome: input.finding.requestedOutcome,
    evidenceArtifactIds: Object.freeze([...input.finding.evidenceArtifactIds]),
  };
  const parsed = normalizedReviewFindingSchema.safeParse(value);
  if (!parsed.success) throw new ArticleReviewCycleError("FINDING_SCHEMA", `finding ${input.finding.localId} does not match its strict schema`);
  return Object.freeze(value);
}

function measurementFailureFindings(
  findings: readonly ArticleReviewFinding[],
  measurement: ArticleMeasurement,
  check: ReviewCheckDefinition,
): readonly ArticleReviewFinding[] {
  if (measurementPasses(measurement, check)) return [];
  if (findings.length > 0) return findings.map((finding) => ({ ...finding, severity: "must_fix" as const }));
  const generated: ArticleReviewFinding[] = [];
  if (!measurement.fits) generated.push({ localId: "measure.page_count", severity: "must_fix", scope: { kind: "document" }, problem: `The article is ${measurement.pageCount} reader pages, above the ${check.kind === "article_measurement" ? check.maximumReaderPages : measurement.maximumReaderPages}-page limit.`, requestedOutcome: "Reduce the article to the pinned reader-page limit.", evidenceArtifactIds: [measurement.manuscriptArtifactId] });
  if (!measurement.openerFits) generated.push({ localId: "measure.opener", severity: "must_fix", scope: { kind: "document" }, problem: "The article opener does not fit the production profile.", requestedOutcome: "Revise the opening so the title, label, and byline fit the opener.", evidenceArtifactIds: [measurement.manuscriptArtifactId] });
  return generated;
}

function measurementPasses(measurement: ArticleMeasurement, check: ReviewCheckDefinition): boolean {
  const maximum = check.kind === "article_measurement" ? check.maximumReaderPages : measurement.maximumReaderPages;
  return measurement.fits && measurement.openerFits && measurement.pageCount <= maximum;
}

function measurementValue(value: unknown, checkId: string): ArticleMeasurement | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ArticleReviewCycleError("MEASUREMENT_SCHEMA", `measurement ${checkId} is not an object`);
  const measurement = value as ArticleMeasurement;
  if (measurement.schemaVersion !== "article-measurement/1" || typeof measurement.fits !== "boolean" || typeof measurement.openerFits !== "boolean" || !Number.isSafeInteger(measurement.pageCount)) throw new ArticleReviewCycleError("MEASUREMENT_SCHEMA", `measurement ${checkId} is malformed`);
  return measurement;
}

function declaredChecks(plan: ResolvedReviewPlan): readonly ReviewCheckDefinition[] {
  const byId = new Map(plan.checks.map((check) => [check.id, check]));
  const ordered: ReviewCheckDefinition[] = [];
  for (const wave of plan.waves) {
    for (const checkId of wave.checkIds) {
      const check = byId.get(checkId);
      if (check === undefined) throw new ArticleReviewCycleError("REVIEW_PLAN_INVALID", `review wave ${wave.id} names unknown check ${checkId}`);
      ordered.push(check);
    }
  }
  if (ordered.length !== plan.checks.length) throw new ArticleReviewCycleError("REVIEW_PLAN_INVALID", "review plan does not assign every check exactly once");
  return ordered;
}

function findingOrder(left: NormalizedReviewFinding, right: NormalizedReviewFinding, checks: readonly ReviewCheckDefinition[]): number {
  const checkIndex = (value: NormalizedReviewFinding): number => {
    const index = checks.findIndex((check) => check.id === value.checkId);
    return index < 0 ? Number.MAX_SAFE_INTEGER : index;
  };
  const checkDelta = checkIndex(left) - checkIndex(right);
  if (checkDelta !== 0) return checkDelta;
  const reviewerDelta = left.reviewerId.localeCompare(right.reviewerId);
  if (reviewerDelta !== 0) return reviewerDelta;
  const severityDelta = severityRank(left.severity) - severityRank(right.severity);
  if (severityDelta !== 0) return severityDelta;
  const scopeDelta = scopeCompare(left.scope, right.scope);
  if (scopeDelta !== 0) return scopeDelta;
  return left.findingId.localeCompare(right.findingId);
}

function severityRank(value: "must_fix" | "consider"): number { return value === "must_fix" ? 0 : 1; }

function scopeCompare(left: ManuscriptScope, right: ManuscriptScope): number {
  const rank = (value: ManuscriptScope): number => ({ document: 0, heading: 1, paragraph: 2, span: 3 }[value.kind]);
  const values = [
    rank(left) - rank(right),
    String(left.headingId ?? "").localeCompare(String(right.headingId ?? "")),
    (left.ordinal ?? -1) - (right.ordinal ?? -1),
    (left.start ?? -1) - (right.start ?? -1),
    (left.end ?? -1) - (right.end ?? -1),
  ];
  return values.find((value) => value !== 0) ?? 0;
}

function validateBudget(value: ArticleRewriteBudget): void {
  if (!Number.isSafeInteger(value.rewritesUsed) || value.rewritesUsed < 0 || !Number.isSafeInteger(value.maximumRewrites) || value.maximumRewrites < 0 || value.rewritesUsed > value.maximumRewrites) {
    throw new ArticleReviewCycleError("REWRITE_BUDGET_INVALID", "rewrite budget must be safe, non-negative, and not exhausted beyond its maximum");
  }
}

function assertText(value: string, label: string): void { if (typeof value !== "string" || value.trim().length === 0) throw new ArticleReviewCycleError("INPUT_INVALID", `${label} is required`); }
function assertUnique(values: readonly string[], label: string): void { if (new Set(values).size !== values.length) throw new ArticleReviewCycleError("INPUT_DUPLICATE", `${label} must be unique`); }
function sameStrings(left: readonly string[], right: readonly string[]): boolean { return left.length === right.length && left.every((value, index) => value === right[index]); }
