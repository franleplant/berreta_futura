import assert from "node:assert/strict";
import test from "node:test";

import type { ArtifactId, ManuscriptRevisionId } from "../contracts/index.ts";
import type { ResolvedReviewPlan } from "../contracts/production-plan.ts";
import type { ArticleReviewCheckResult } from "../workflows/article-review-panel.ts";
import type { ArticleMeasurement } from "../workflows/internal-types.ts";
import {
  ArticleReviewCycleError,
  compileRevisionBrief,
  deriveArticleReviewRoute,
  revisionBriefBytes,
  revisionBriefParents,
  validateArticleEditorDecision,
  type RevisionBriefInput,
} from "../article-production/review-cycle.ts";

const id = (value: string): ArtifactId => value as ArtifactId;
const revision = "review-cycle-revision" as ManuscriptRevisionId;

const plan: ResolvedReviewPlan = {
  schemaVersion: "resolved-article-review-plan/1",
  reviewPlanArtifactId: id("plan"),
  checks: [
    { kind: "model_review", id: "evidence", role: "article_review", promptArtifactId: id("evidence-prompt"), access: "source_aware", authority: "blocking" },
    { kind: "model_review", id: "craft", role: "article_review", promptArtifactId: id("craft-prompt"), access: "source_blind", authority: "advisory" },
    { kind: "article_measurement", id: "measure_article", role: "measure_article", measurementProfileArtifactId: id("measurement-profile"), maximumReaderPages: 7 },
    { kind: "model_review", id: "human", role: "article_review", promptArtifactId: id("human-prompt"), access: "source_aware", authority: "human_required" },
  ],
  waves: [
    { id: "panel", checkIds: ["evidence", "craft", "measure_article", "human"], stopAfter: "never" },
  ],
};

const finding = (localId: string, severity: "must_fix" | "consider", text = "same problem") => ({
  localId,
  severity,
  scope: { kind: "paragraph" as const, ordinal: 1 },
  problem: text,
  requestedOutcome: "fix it",
  evidenceArtifactIds: [id("manuscript")],
});

const measurement: ArticleMeasurement = {
  schemaVersion: "article-measurement/1",
  articleId: "article",
  manuscriptArtifactId: id("manuscript"),
  pageCount: 8,
  maximumReaderPages: 7,
  fits: false,
  openerFits: true,
  layouts: [],
  inputArtifactIds: [id("manuscript")],
};

function result(input: Partial<ArticleReviewCheckResult> & Pick<ArticleReviewCheckResult, "checkId" | "kind" | "resultArtifactId">): ArticleReviewCheckResult {
  return {
    schemaVersion: "article-review-check-result/2",
    status: "completed",
    waveId: "panel",
    key: `review.${input.checkId}`,
    manuscriptArtifactId: id("manuscript"),
    manuscriptRevisionId: revision,
    materialArtifactIds: [id("manuscript")],
    outputArtifactIds: [input.resultArtifactId!],
    reviewerId: input.checkId,
    assessment: "pass",
    findings: [],
    ...input,
  };
}

function baseInput(overrides: Partial<RevisionBriefInput> = {}): RevisionBriefInput {
  return {
    articleId: "article",
    iterationId: "iteration-1",
    manuscriptArtifactId: id("manuscript"),
    manuscriptRevisionId: revision,
    reviewPlan: plan,
    reviewResults: [
      result({ checkId: "evidence", kind: "model_review", resultArtifactId: id("review-evidence"), reviewerId: "reviewer-evidence", assessment: "findings", findings: [finding("e-2", "consider"), finding("e-1", "must_fix")] }),
      result({ checkId: "craft", kind: "model_review", resultArtifactId: id("review-craft"), reviewerId: "reviewer-craft", assessment: "findings", findings: [finding("c-1", "consider")] }),
      result({ checkId: "measure_article", kind: "article_measurement", resultArtifactId: id("measurement"), reviewerId: "measure_article", assessment: "findings", result: measurement, findings: [finding("measure.page_count", "must_fix")] }),
      result({ checkId: "human", kind: "model_review", resultArtifactId: id("review-human"), reviewerId: "reviewer-human", assessment: "pass" }),
    ],
    measurementArtifactId: id("measurement"),
    ...overrides,
  };
}

test("revision brief preserves every finding and has stable exact parents and bytes", () => {
  const input = baseInput();
  const brief = compileRevisionBrief(input);
  assert.deepEqual(brief.mustFix.map((finding) => finding.findingId), ["review-evidence#e-1", "measurement#measure.page_count"]);
  assert.deepEqual(brief.consider.map((finding) => finding.findingId), ["review-evidence#e-2", "review-craft#c-1"]);
  assert.deepEqual(brief.reviewResultArtifactIds, [id("review-evidence"), id("review-craft"), id("review-human")]);
  assert.deepEqual(brief.reviewOutputArtifactIds, []);
  assert.deepEqual(revisionBriefParents({ brief }), [id("manuscript"), id("review-evidence"), id("review-craft"), id("review-human"), id("measurement")]);
  assert.deepEqual(revisionBriefBytes(brief), revisionBriefBytes(compileRevisionBrief(input)));
  assert.equal(brief.mustFix[0]!.problem, brief.mustFix[1]!.problem);
  assert.notEqual(brief.mustFix[0]!.findingId, brief.mustFix[1]!.findingId);
});

test("routing uses plan authority and routes blocking findings to automatic rewrite while budget remains", () => {
  const input = baseInput();
  const brief = compileRevisionBrief(input);
  const route = deriveArticleReviewRoute({ brief, reviewPlan: plan, reviewResults: input.reviewResults, rewriteBudget: { rewritesUsed: 0, maximumRewrites: 2 } });
  assert.equal(route.outcome, "auto_rewrite");
  assert.equal(route.reason, "changes_required");
  assert.equal(route.rewriteBudget.remainingRewrites, 2);
  assert.deepEqual(route.effectiveMustFixFindingIds, ["review-evidence#e-1", "measurement#measure.page_count"]);
  assert.deepEqual(route.allowedChoices, []);
});

test("clean, human-required, and exhausted routes wait for an editor", () => {
  const cleanInput = baseInput({
    reviewResults: baseInput().reviewResults.map((candidate) => ({ ...candidate, assessment: "pass", findings: [], ...(candidate.kind === "article_measurement" ? { result: { ...measurement, pageCount: 7, fits: true } } : {}) })),
  });
  const cleanBrief = compileRevisionBrief(cleanInput);
  const clean = deriveArticleReviewRoute({ brief: cleanBrief, reviewPlan: plan, reviewResults: cleanInput.reviewResults, rewriteBudget: { rewritesUsed: 0, maximumRewrites: 0 } });
  assert.equal(clean.outcome, "editor_wait");
  assert.equal(clean.reason, "clean");
  assert.deepEqual(clean.allowedChoices, ["accept", "revise", "drop"]);
  validateArticleEditorDecision(clean, { choice: "accept" });

  const humanBrief = compileRevisionBrief(baseInput());
  const human = deriveArticleReviewRoute({ brief: humanBrief, reviewPlan: plan, reviewResults: baseInput().reviewResults.map((candidate) => candidate.checkId === "human" ? { ...candidate, assessment: "human_required" } : candidate), rewriteBudget: { rewritesUsed: 0, maximumRewrites: 2 } });
  assert.equal(human.reason, "human_required");
  assert.equal(human.outcome, "editor_wait");

  const exhausted = deriveArticleReviewRoute({ brief: humanBrief, reviewPlan: plan, reviewResults: baseInput().reviewResults, rewriteBudget: { rewritesUsed: 2, maximumRewrites: 2 } });
  assert.equal(exhausted.reason, "rewrite_budget_exhausted");
  assert.throws(() => validateArticleEditorDecision(exhausted, { choice: "accept" }), (error: unknown) => error instanceof ArticleReviewCycleError && error.code === "EDITOR_APPROVALS_REQUIRED");
  validateArticleEditorDecision(exhausted, { choice: "accept", approvedFindingIds: [...exhausted.effectiveMustFixFindingIds] });
  validateArticleEditorDecision(exhausted, { choice: "revise", additionalRewriteBudget: 1 });
  assert.throws(() => validateArticleEditorDecision(exhausted, { choice: "revise" }), /additional rewrite budget/iu);
});

test("advisory must-fix findings are rejected instead of gaining blocking authority", () => {
  const input = baseInput({
    reviewResults: baseInput().reviewResults.map((candidate) => candidate.checkId === "craft" ? { ...candidate, findings: [finding("craft-bad", "must_fix")], assessment: "findings" } : candidate),
  });
  const brief = compileRevisionBrief(input);
  assert.throws(() => deriveArticleReviewRoute({ brief, reviewPlan: plan, reviewResults: input.reviewResults, rewriteBudget: { rewritesUsed: 0, maximumRewrites: 2 } }), (error: unknown) => error instanceof ArticleReviewCycleError && error.code === "ADVISORY_MUST_FIX");
});
