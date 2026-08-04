import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import test from "node:test";
import { join } from "node:path";
import { tmpdir } from "node:os";

import type { ArtifactId, JsonObject, ManuscriptRevisionId, RunId } from "../contracts/index.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import {
  ArtifactLedger,
  ArtifactLedgerError,
  type LedgerOffer,
} from "../workflow-authority/artifact-ledger.ts";
import type { WorkflowWaitContext } from "../workflows/internal-types.ts";
import {
  articleDecisionWaitKey,
  decisionArtifactId,
  decisionTaskId,
  offerId,
} from "../workflows/article-workflow.ts";
import { reviewKey } from "../workflows/article-review-panel.ts";
import {
  articleDecisionTaskSchema,
  articleReviewRouteSchema,
  articleReviewCycleId,
  revisionBriefSchema,
  validateArticleEditorDecision,
  type ArticleDecisionTask,
  type ArticleReviewRoute,
} from "../article-production/review-cycle.ts";

const id = (value: string): ArtifactId => value as ArtifactId;
const runId = "run-decision-authority" as RunId;
const manuscriptRevisionId = "manuscript-revision-authority" as ManuscriptRevisionId;

type CycleFixture = {
  readonly cycleId: string;
  readonly offer: LedgerOffer;
  readonly task: ArticleDecisionTask;
  readonly route: ArticleReviewRoute;
  readonly wait: WorkflowWaitContext;
  readonly request: {
    readonly runId: RunId;
    readonly offerId: string;
    readonly taskArtifactId: ArtifactId;
    readonly inputArtifactIds: readonly ArtifactId[];
    readonly choice: "accept" | "revise" | "drop";
    readonly rationale: string;
    readonly approvedFindingIds?: readonly string[];
    readonly additionalRewriteBudget?: number;
  };
};

test("editor authority keeps invalid answers pending and reuses commit-before-answer decisions", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-decision-authority-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  const authorityStore = await LocalAuthorityStore.init(join(root, "authority"));
  try {
    await authorityStore.enrollHuman({ principalId: "editor", capabilities: ["text_model"] });
    const credential = await authorityStore.createCredentialProfile({ principalId: "editor", credentialProfileId: "editor-profile" });
    await authorityStore.grant({ credentialProfileId: credential.credentialProfileId, grantId: "editor-grant", capabilities: ["text_model"] });
    const human = await authorityStore.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });

    const manuscriptId = id("art-manuscript-authority");
    ledger.createArtifact({
      id: manuscriptId,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "# Article\n" },
      metadata: { articleId: "article-authority", revisionId: manuscriptRevisionId },
    });
    ledger.createRun({
      runId,
      articleExecutionId: "article-execution-authority" as never,
      articleId: "article-authority",
      editionId: "004",
      workflowVersion: "article-workflow-test/1",
      loopsRunId: runId,
      manuscriptArtifactId: manuscriptId,
      args: {} as JsonObject,
    });

    const first = createCycle(ledger, 0, manuscriptId);

    const authority = ledger.createHumanDecisionAuthority();
    const invalidDecision = {
      choice: "accept" as const,
    };
    assert.throws(
      () => validateArticleEditorDecision(first.route, invalidDecision),
      /every exact effective finding ID/iu,
    );
    assert.equal(ledger.getDecision(first.offer.id), undefined);
    assert.equal(ledger.requireOffer(first.offer.id).status, "active");
    await assert.rejects(
      authority.decide(human, { ...first.request, choice: "accept" }, first.wait),
      (error: unknown) => error instanceof ArtifactLedgerError && error.code === "DECISION_VALIDATION_INVALID",
    );
    assert.equal(ledger.getDecision(first.offer.id), undefined);

    const acceptedRequest = {
      ...first.request,
      choice: "accept" as const,
      approvedFindingIds: [...first.route.effectiveMustFixFindingIds],
    };
    const decision = await authority.decide(human, acceptedRequest, first.wait);
    assert.deepEqual(decision.approvedFindingIds, first.route.effectiveMustFixFindingIds);
    assert.deepEqual(decision.canonicalApprovedFindingIds, first.route.effectiveMustFixFindingIds);
    assert.deepEqual(decision.rewriteBudget, {
      rewritesUsed: 0,
      maximumRewrites: 0,
      remainingRewrites: 0,
      additionalRewriteBudget: 0,
      counts: "writer_rewrites_only",
    });
    assert.equal(decision.validatorVersion, "article-editor-decision-validator/1");

    // Validator facts supplied by an untrusted caller are not part of the
    // request contract. The authority ignores them and reuses its own facts.
    const forgedReplay = await authority.decide(human, {
      ...acceptedRequest,
      validatorVersion: "fake-validator/0",
      canonicalApprovedFindingIds: [],
      rewriteBudget: { rewritesUsed: 99, maximumRewrites: 99, remainingRewrites: 99, additionalRewriteBudget: 99, counts: "writer_rewrites_only" },
    } as never, first.wait);
    assert.equal(forgedReplay.artifactId, decision.artifactId);
    assert.deepEqual(forgedReplay.canonicalApprovedFindingIds, first.route.effectiveMustFixFindingIds);

    // The wait has not been answered yet. A retry after the decision commit
    // adopts the exact immutable decision and does not create a new artifact.
    const replay = await authority.decide(human, acceptedRequest, first.wait);
    assert.equal(replay.artifactId, decision.artifactId);
    assert.equal(ledger.requireOffer(first.offer.id).status, "active");
    await assert.rejects(
      authority.decide(human, { ...acceptedRequest, rationale: "changed" }, first.wait),
      (error: unknown) => error instanceof ArtifactLedgerError && error.code === "DECISION_ALREADY_RECORDED",
    );

    // The second cycle has a different offer and can never replay the first
    // cycle's artifact or input set.
    ledger.markOfferAnswered(first.offer.id);
    const second = createCycle(ledger, 1, manuscriptId);
    assert.notEqual(first.cycleId, second.cycleId);
    assert.notEqual(first.offer.id, second.offer.id);
    assert.notEqual(first.task.routeArtifactId, second.task.routeArtifactId);
    assert.notEqual(
      reviewKey({
        articleExecutionId: "article-execution-authority" as never,
        reviewPlanArtifactId: id("review-plan-authority"),
        manuscriptRevisionId,
        cycleId: first.cycleId,
        waveId: "panel",
        checkId: "evidence",
      }),
      reviewKey({
        articleExecutionId: "article-execution-authority" as never,
        reviewPlanArtifactId: id("review-plan-authority"),
        manuscriptRevisionId,
        cycleId: second.cycleId,
        waveId: "panel",
        checkId: "evidence",
      }),
    );
    const secondDecision = await authority.decide(human, second.request, second.wait);
    assert.notEqual(secondDecision.artifactId, decision.artifactId);
    assert.notDeepEqual(secondDecision.inputArtifactIds, decision.inputArtifactIds);
    assert.equal(ledger.requireOffer(second.offer.id).status, "active");
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("the generic ledger decision API cannot bypass article validation", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-decision-ledger-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  try {
    const manuscriptId = id("art-ledger-manuscript");
    const taskId = id("art-ledger-task");
    const inputId = id("art-ledger-input");
    ledger.createArtifact({ id: manuscriptId, kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "# Article\n" }, metadata: { articleId: "article-ledger", revisionId: manuscriptRevisionId } });
    ledger.createRun({ runId: "run-ledger" as RunId, articleId: "article-ledger", workflowVersion: "test/1", loopsRunId: "run-ledger", manuscriptArtifactId: manuscriptId, args: {} as JsonObject });
    ledger.createArtifact({ id: inputId, kind: "evidence", schemaVersion: "evidence/1", mediaType: "text/plain", origin: "imported", payload: { kind: "text", text: "evidence" }, runId: "run-ledger" as RunId });
    ledger.createArtifact({ id: taskId, kind: "article_decision_request", schemaVersion: "article-decision-request/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: {} }, parents: [{ artifactId: inputId, relation: "decision_evidence" }], runId: "run-ledger" as RunId });
    const offer = ledger.createOffer({ id: "offer-ledger", runId: "run-ledger" as RunId, taskArtifactId: taskId, inputArtifactIds: [inputId], allowedChoices: ["accept", "revise", "drop"] });
    assert.throws(
      () => ledger.recordDecision({ id: "decision-ledger", runId: offer.runId, offerId: offer.id, taskArtifactId: taskId, inputArtifactIds: [inputId], principalId: "editor", credentialProfileId: "editor-profile", choice: "accept", rationale: "bypass", artifactId: id("artifact-ledger"), durableContext: { runId: offer.runId, invocationId: "invocation", workflowName: "article", workflowVersion: "1", callId: "call", waitId: "wait", key: "article.decision.cycle", kind: "wait" } }),
      (error: unknown) => error instanceof ArtifactLedgerError && error.code === "DECISION_VALIDATION_REQUIRED",
    );
    assert.equal(ledger.getDecision(offer.id), undefined);
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("human decisions expose only the authenticated facade, never a persistence writer", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-decision-surface-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  try {
    const authority = ledger.createHumanDecisionAuthority();
    assert.deepEqual(Object.getOwnPropertyNames(Object.getPrototypeOf(authority)), ["constructor", "decide"]);
    const ledgerMethods = Object.getOwnPropertyNames(ArtifactLedger.prototype);
    assert.equal(ledgerMethods.includes("recordValidatedEditorDecision"), false);
    assert.equal(ledgerMethods.some((method) => method.toLowerCase().includes("persist") || method.toLowerCase().includes("decisionwriter")), false);
    assert.equal((ledger as unknown as { readonly recordValidatedEditorDecision?: unknown }).recordValidatedEditorDecision, undefined);
    const moduleSurface = await import("../workflow-authority/human-decisions.ts");
    assert.equal("HumanDecisionAuthority" in moduleSurface, false);
    assert.equal(Object.keys(moduleSurface).length, 0);
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

function createCycle(ledger: ArtifactLedger, rewriteOrdinal: number, manuscriptId: ArtifactId): CycleFixture {
  const cycleId = articleReviewCycleId({
    articleExecutionId: "article-execution-authority" as never,
    manuscriptRevisionId,
    reviewPlanArtifactId: id("review-plan-authority"),
    rewriteOrdinal,
  });
  const reviewResultId = id(`art-review-result-${rewriteOrdinal}`);
  const measurementId = id(`art-measurement-${rewriteOrdinal}`);
  const briefId = id(`art-brief-${rewriteOrdinal}`);
  const routeId = id(`art-route-${rewriteOrdinal}`);
  const taskId = decisionTaskId(cycleId);
  const currentOfferId = offerId(cycleId);
  const findingId = `${reviewResultId}#blocking-finding`;
  for (const artifact of [
    { id: reviewResultId, kind: "article_review_result" },
    { id: measurementId, kind: "article_measurement" },
  ]) {
    ledger.createArtifact({ id: artifact.id, kind: artifact.kind, schemaVersion: `${artifact.kind}/1`, mediaType: "application/json", origin: "machine", payload: { kind: "json", value: {} }, runId });
  }
  const brief = {
    schemaVersion: "article-revision-brief/1" as const,
    articleId: "article-authority",
    iterationId: `iteration-${rewriteOrdinal}`,
    manuscriptArtifactId: manuscriptId,
    mustFix: [{ schemaVersion: "article-review-finding/1" as const, findingId: findingId as never, reviewResultArtifactId: reviewResultId, localId: "blocking-finding", reviewerId: "reviewer", waveId: "panel", checkId: "evidence", kind: "model_review" as const, authority: "blocking" as const, severity: "must_fix" as const, scope: { kind: "document" as const }, problem: "problem", requestedOutcome: "fix", evidenceArtifactIds: [manuscriptId] }],
    consider: [],
    humanRulings: [],
    reviewResultArtifactIds: [reviewResultId],
    measurementArtifactId: measurementId,
    reviewOutputArtifactIds: [],
    cycleId,
    manuscriptRevisionId,
    reviewPlanArtifactId: id("review-plan-authority"),
    rewriteOrdinal,
  };
  const route = {
    schemaVersion: "article-review-route/1" as const,
    articleId: "article-authority",
    manuscriptArtifactId: manuscriptId,
    iterationId: brief.iterationId,
    outcome: "editor_wait" as const,
    reason: "rewrite_budget_exhausted" as const,
    effectiveMustFixFindingIds: [findingId],
    effectiveConsiderFindingIds: [],
    humanRequiredFindingIds: [],
    rewriteBudget: { rewritesUsed: 0, maximumRewrites: 0, remainingRewrites: 0, counts: "writer_rewrites_only" as const },
    allowedChoices: ["accept", "revise", "drop"] as const,
    acceptRequiresApprovedFindingIds: true,
    reviseRequiresAdditionalRewriteBudget: true,
    cycleId,
    manuscriptRevisionId,
    reviewPlanArtifactId: id("review-plan-authority"),
    rewriteOrdinal,
  };
  const parsedBrief = revisionBriefSchema.parse(brief) as never;
  const parsedRoute = articleReviewRouteSchema.parse(route) as never;
  ledger.createArtifact({ id: briefId, kind: "article_revision_brief", schemaVersion: "article-revision-brief/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: parsedBrief }, parents: [{ artifactId: manuscriptId, relation: "revision_brief_input" }, { artifactId: reviewResultId, relation: "revision_brief_input" }, { artifactId: measurementId, relation: "revision_brief_input" }], runId });
  ledger.createArtifact({ id: routeId, kind: "article_review_route", schemaVersion: "article-review-route/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: parsedRoute }, parents: [{ artifactId: briefId, relation: "revision_brief" }], runId });
  const inputArtifactIds = [manuscriptId, briefId, routeId, reviewResultId, measurementId] as const;
  const task = {
    schemaVersion: "article-decision-task/1" as const,
    runId,
    articleExecutionId: "article-execution-authority",
    articleId: "article-authority",
    cycleId,
    iterationId: brief.iterationId,
    manuscriptArtifactId: manuscriptId,
    manuscriptRevisionId,
    reviewPlanArtifactId: id("review-plan-authority"),
    rewriteOrdinal,
    revisionBriefArtifactId: briefId,
    routeArtifactId: routeId,
    inputArtifactIds,
    expectedDecisionArtifactId: decisionArtifactId(currentOfferId),
    allowedChoices: ["accept", "revise", "drop"] as const,
  };
  const parsedTask = articleDecisionTaskSchema.parse(task) as unknown as ArticleDecisionTask;
  ledger.createArtifact({ id: taskId, kind: "article_decision_request", schemaVersion: "article-decision-request/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: parsedTask as unknown as JsonObject }, parents: inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_evidence" })), runId });
  const offer = ledger.createOffer({ id: currentOfferId, runId, taskArtifactId: taskId, inputArtifactIds, allowedChoices: ["accept", "revise", "drop"] });
  const wait: WorkflowWaitContext = { runId, invocationId: `invocation-${rewriteOrdinal}`, workflowName: "article", workflowVersion: "1", callId: `call-${rewriteOrdinal}`, waitId: `wait-${rewriteOrdinal}`, key: articleDecisionWaitKey(cycleId), kind: "wait" };
  return {
    cycleId,
    offer,
    task: parsedTask,
    route: parsedRoute,
    wait,
    request: { runId, offerId: currentOfferId, taskArtifactId: taskId, inputArtifactIds, choice: "drop", rationale: `cycle ${rewriteOrdinal}` },
  };
}
