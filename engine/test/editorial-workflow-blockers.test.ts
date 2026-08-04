import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { LocalAuthorityStore } from "../authority/local-authority.ts";
import type { ArtifactId, JsonObject, JsonValue, RunId } from "../contracts/index.ts";
import type { EditorialWriterResult } from "../executors/closed-editorial-writer/result.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import { runOpeningEditorialWorkflow, type OpeningEditorialWorkflowArgs } from "../workflows/editorial-workflow.ts";
import type { ArticleWorkflowPorts, MagazineWorkflowContext, WorkflowWaitContext } from "../workflows/internal-types.ts";

const artifactId = (value: string): ArtifactId => value as ArtifactId;
const runId = "editorial-blocker-run" as RunId;

test("blocking editorial review automatically rewrites before human acceptance", async () => {
  const fixture = await createFixture({ maximumRewrites: 1, reviewBlocking: [true, false], decisions: ["accept"] });
  try {
    const result = await runOpeningEditorialWorkflow(fixture.args, fixture.context, fixture.ports);
    assert.equal(result.status, "complete");
    assert.equal(fixture.counts.writer, 2);
    assert.equal(fixture.counts.review, 2);
    assert.equal(fixture.counts.measurement, 2);
    assert.equal(fixture.counts.wait, 1);
  } finally { await fixture.close(); }
});

test("failed full-English measurement cannot be accepted or promoted", async () => {
  const fixture = await createFixture({ maximumRewrites: 0, measurementPass: false, decisions: ["abort"], tryForbiddenAccept: true });
  try {
    const result = await runOpeningEditorialWorkflow(fixture.args, fixture.context, fixture.ports);
    assert.equal(result.status, "aborted");
    assert.match(fixture.forbiddenAcceptError?.message ?? "", /stale|invalid/iu);
    assert.deepEqual(fixture.ledger.activeOffer(runId)?.allowedChoices, undefined);
    assert.equal(fixture.counts.promotion, 0);
  } finally { await fixture.close(); }
});

test("human revise at exhausted budget grants one rewrite and reaches a fresh wait", async () => {
  const fixture = await createFixture({ maximumRewrites: 0, decisions: ["revise", "accept"] });
  try {
    const result = await runOpeningEditorialWorkflow(fixture.args, fixture.context, fixture.ports);
    assert.equal(result.status, "complete");
    assert.equal(fixture.counts.writer, 2);
    assert.equal(fixture.counts.wait, 2);
    assert.equal(fixture.counts.review, 2);
    const waiting = fixture.ledger.listArtifacts(runId).filter((artifact) => artifact.kind === "editorial_loop_checkpoint" && artifact.metadata.phase === "waiting");
    assert.equal(waiting.length, 2);
    assert.equal(waiting[1]?.metadata.rewriteOrdinal, 1);
  } finally { await fixture.close(); }
});

test("writer rejects malformed outputs, frontmatter mismatch, and broken lineage", async (t) => {
  for (const [fault, pattern] of [
    ["malformed", /exactly three artifacts/iu],
    ["frontmatter", /frontmatter/iu],
    ["lineage", /exact writer inputs/iu],
  ] as const) {
    await t.test(fault, async () => {
      const fixture = await createFixture({ maximumRewrites: 0, writerFault: fault, decisions: ["abort"] });
      try { await assert.rejects(runOpeningEditorialWorkflow(fixture.args, fixture.context, fixture.ports), pattern); }
      finally { await fixture.close(); }
    });
  }
});

type FixtureOptions = {
  readonly maximumRewrites: number;
  readonly reviewBlocking?: readonly boolean[];
  readonly measurementPass?: boolean;
  readonly decisions: readonly ("accept" | "revise" | "abort")[];
  readonly tryForbiddenAccept?: boolean;
  readonly writerFault?: "malformed" | "frontmatter" | "lineage";
};

async function createFixture(options: FixtureOptions) {
  const root = await mkdtemp(join(tmpdir(), "mag-editorial-blockers-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  const articles = Array.from({ length: 7 }, (_, index) => artifactId(`article-${index + 1}`));
  for (const [index, id] of articles.entries()) ledger.createArtifact({ id, kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "machine", payload: { kind: "text", text: `# Article ${index + 1}` }, metadata: { articleId: `article-${index + 1}`, revisionId: `revision-${index + 1}` } });
  const seed = artifactId("editorial-seed");
  const profile = artifactId("editorial-profile");
  const measureProfile = artifactId("editorial-measurement-profile");
  const reviewPlan = artifactId("editorial-review-plan");
  const accepted = artifactId("accepted-english-inputs");
  const entry = artifactId("editorial-entry");
  ledger.createArtifact({ id: seed, kind: "editorial_input_set", schemaVersion: "editorial-input-set/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { articleArtifactIds: articles } }, parents: articles.map((id) => ({ artifactId: id, relation: "editorial_article_input" })), metadata: { articleId: "opening", revisionId: "seed-revision" } });
  ledger.createArtifact({ id: accepted, kind: "accepted_english_issue_inputs", schemaVersion: "accepted-english-issue-inputs/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "accepted-english-issue-inputs/1", pipelineRef: { kind: "write_pipeline", editionId: "004", logicalId: "edition-004", revisionId: "pipeline-revision" } } }, parents: articles.map((id) => ({ artifactId: id, relation: "accepted_article" })) });
  ledger.createArtifact({ id: reviewPlan, kind: "editorial_review_plan", schemaVersion: "editorial-review-plan/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-review-plan/1" } } });
  ledger.createArtifact({ id: measureProfile, kind: "editorial_measurement_profile", schemaVersion: "editorial-measurement-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-measurement-profile/1", maximumReaderPages: 1 } } });
  const args: OpeningEditorialWorkflowArgs = { schemaVersion: "magazine-opening-editorial/1", editionId: "004", runId, editionRunId: "edition-root" as RunId, editorialExecutionId: "editorial-blocker-execution", editorialId: "opening", seedManuscriptArtifactId: seed, measurementProfileArtifactId: measureProfile, profileArtifactId: profile, entryArtifactId: entry, acceptedEnglishInputsArtifactId: accepted, articleArtifactIds: articles, articleExecutionIds: articles.map((_, index) => `execution-${index + 1}`), maximumReaderPages: 1, maximumRewrites: options.maximumRewrites, reviewPlanArtifactId: reviewPlan };
  ledger.createRun({ runId, articleExecutionId: args.editorialExecutionId as never, articleId: "opening", editionId: "004", workflowVersion: "editorial-blocker/1", loopsRunId: runId, manuscriptArtifactId: seed, args: args as unknown as JsonObject });
  ledger.createArtifact({ id: profile, kind: "resolved_editorial_profile", schemaVersion: "resolved-editorial-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "resolved-editorial-profile/1", brief: "One idea" } }, runId });
  ledger.createArtifact({ id: entry, kind: "editorial_workflow_entry", schemaVersion: "magazine-opening-editorial/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: args as unknown as JsonValue }, parents: [{ artifactId: profile, relation: "editorial_profile" }, { artifactId: accepted, relation: "accepted_inputs" }], runId });

  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollHuman({ principalId: "editor", capabilities: ["text_model"] });
  const credential = await authority.createCredentialProfile({ principalId: "editor", credentialProfileId: "editor-profile" });
  await authority.grant({ credentialProfileId: credential.credentialProfileId, capabilities: ["text_model"] });
  const human = await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });
  const decisions = [...options.decisions];
  const counts = { writer: 0, measurement: 0, review: 0, wait: 0, promotion: 0 };
  const fixture = { forbiddenAcceptError: undefined as Error | undefined };

  const ports: ArticleWorkflowPorts = {
    ledger,
    measureArticle: async () => { throw new Error("out of scope"); },
    runReviewPanel: async () => { throw new Error("out of scope"); },
    runEditorialWriter: async (input) => {
      counts.writer += 1;
      const ordinal = counts.writer;
      const title = `One Idea ${ordinal}`;
      const markdown = options.writerFault === "frontmatter" && ordinal === 1 ? `# ${title}` : `---\nlabel: Opening\ntitle: ${title}\nbyline: Magazine\n---\n\nEditorial ${ordinal}.`;
      const value: EditorialWriterResult = { schemaVersion: "editorial-writer-result/1", label: "Opening", title, byline: "Magazine", manuscript: markdown, workingNotes: `notes ${ordinal}`, dispositions: [] };
      const inputs = [input.profileArtifactId, ...input.articleArtifactIds, input.currentManuscriptArtifactId, ...(input.revisionContextArtifactIds ?? [])];
      const metadata = { writerExecutionClass: "closed_editorial_writer/1", editorialExecutionId: args.editorialExecutionId, access: "source_blind", operationKey: input.operationKey, operationInputDigest: `digest-${ordinal}`, claimId: `claim-${ordinal}`, attemptId: `attempt-${ordinal}`, attemptNumber: 1, principalId: "writer", writerInputArtifactIds: inputs as unknown as JsonValue };
      const parents = inputs.map((id) => ({ artifactId: id, relation: "editorial_writer_input" }));
      const manuscript = artifactId(`writer-${ordinal}-manuscript`);
      const notes = artifactId(`writer-${ordinal}-notes`);
      const dispositions = artifactId(`writer-${ordinal}-dispositions`);
      ledger.createArtifact({ id: manuscript, kind: "editorial_manuscript", schemaVersion: "editorial-manuscript/1", mediaType: "text/markdown", origin: "model", payload: { kind: "text", text: markdown }, parents, metadata: { ...metadata, label: "Opening", title, byline: "Magazine", revisionId: `editorial-revision-${ordinal}` }, runId });
      if (options.writerFault !== "malformed" || ordinal !== 1) ledger.createArtifact({ id: notes, kind: "editorial_working_notes", schemaVersion: "editorial-working-notes/1", mediaType: "text/plain", origin: "model", payload: { kind: "text", text: value.workingNotes }, parents: options.writerFault === "lineage" && ordinal === 1 ? parents.slice(0, -1) : parents, metadata, runId });
      ledger.createArtifact({ id: dispositions, kind: "editorial_finding_dispositions", schemaVersion: "editorial-finding-dispositions/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: { schemaVersion: "editorial-finding-dispositions/1", dispositions: [] } }, parents, metadata, runId });
      const artifacts = [ledger.requireArtifact(manuscript), ...(options.writerFault === "malformed" && ordinal === 1 ? [] : [ledger.requireArtifact(notes)]), ledger.requireArtifact(dispositions)];
      return { selected: true, value, claim: { claimId: `claim-${ordinal}`, operationKey: input.operationKey }, artifacts } as never;
    },
    measureEditorial: async (input) => {
      counts.measurement += 1;
      const pass = options.measurementPass ?? true;
      const value = { schemaVersion: "editorial-measurement/1", operation: "measure_edition", editionId: "004", editorialId: "opening", language: "en", manuscriptArtifactId: input.manuscriptArtifactId, contentArtifactIds: [input.manuscriptArtifactId, ...input.articleArtifactIds], inputArtifactIds: [input.manuscriptArtifactId, ...input.articleArtifactIds], pageCount: pass ? 1 : 2, maximumReaderPages: 1, fits: pass, labelVisible: true, labelFits: true, titleVisible: true, titleFits: true, bylineVisible: true, bylineFits: true } as const;
      const id = artifactId(`measurement-${counts.measurement}`);
      ledger.createArtifact({ id, kind: "editorial_measurement", schemaVersion: "editorial-measurement/1", mediaType: "application/json", origin: "subprocess", payload: { kind: "json", value: value as unknown as JsonValue }, parents: [input.manuscriptArtifactId, ...input.articleArtifactIds, input.measurementProfileArtifactId].map((artifactId) => ({ artifactId, relation: "editorial_measurement_input" })), metadata: { measurementExecutionClass: "authenticated_measure_edition/1", access: "tool", claimId: `measure-claim-${counts.measurement}`, attemptId: `measure-attempt-${counts.measurement}`, principalId: "renderer", operationInputDigest: `measure-digest-${counts.measurement}` }, runId });
      return { selected: true, adopted: true, artifacts: [ledger.requireArtifact(id)] };
    },
    runEditorialReview: async (input) => {
      counts.review += 1;
      const blocking = options.reviewBlocking?.[counts.review - 1] ?? false;
      const findings = blocking ? [{ findingId: `finding-${counts.review}`, target: "editorial:opening" as const, severity: "must_fix" as const, problem: "Weak unifying idea", requestedOutcome: "Strengthen the idea" }] : [];
      const value = { schemaVersion: "editorial-review-result/1", editionId: "004", editorialId: "opening", target: "editorial:opening", manuscriptArtifactId: input.manuscriptArtifactId, measurementArtifactId: input.measurementArtifactId, reviewPlanArtifactId: input.reviewPlanArtifactId, reviewCycleId: input.reviewCycleId, assessment: blocking ? "findings" : "pass", findings } as const;
      const ids = [input.manuscriptArtifactId, input.reviewPlanArtifactId, input.measurementArtifactId];
      const id = artifactId(`review-${counts.review}`);
      ledger.createArtifact({ id, kind: "editorial_review_result", schemaVersion: "editorial-review-result/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: value as unknown as JsonValue }, parents: ids.map((artifactId) => ({ artifactId, relation: "editorial_review_input" })), metadata: { reviewerExecutionClass: "closed_editorial_reviewer/1", access: "source_blind", claimId: `review-claim-${counts.review}`, attemptId: `review-attempt-${counts.review}`, principalId: "reviewer", operationInputDigest: `review-digest-${counts.review}`, reviewerInputArtifactIds: ids as unknown as JsonValue }, runId });
      return { selected: true, findings, artifacts: [ledger.requireArtifact(id)] };
    },
    promoteEditorial: async (input) => {
      counts.promotion += 1;
      const id = artifactId("promotion");
      ledger.createArtifact({ id, kind: "editorial_durable_promotion", schemaVersion: "editorial-durable-promotion/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-durable-promotion/1" } }, parents: [{ artifactId: input.request.acceptedArtifactIds[0]!, relation: "editorial_manuscript" }], runId });
      return { promotionArtifactId: id, durableRevisionId: input.request.revisionId, manifestDigest: "sha256:promotion", gitCommitOid: "commit" };
    },
    requireDecision: () => { throw new Error("out of scope"); },
    promote: async () => { throw new Error("out of scope"); },
  };
  const context: MagazineWorkflowContext = {
    step: async (_key, fn) => await fn(),
    parallel: async (thunks) => await Promise.all(thunks.map(async (thunk) => await thunk())),
    wait: async (_key, request) => {
      counts.wait += 1;
      const offer = ledger.requireOffer(request.request.offerId as string);
      const durableContext: WorkflowWaitContext = { runId, invocationId: "invocation", workflowName: "magazine-opening-editorial", workflowVersion: "test/1", callId: `call-${counts.wait}`, waitId: `wait-${counts.wait}`, key: `wait-${counts.wait}`, kind: "wait" };
      if (options.tryForbiddenAccept && counts.wait === 1) {
        try { await ledger.createHumanDecisionAuthority().decideEditorial(human, { runId, offerId: offer.id, taskArtifactId: offer.taskArtifactId, inputArtifactIds: offer.inputArtifactIds, choice: "accept", rationale: "Try invalid accept" }, durableContext); }
        catch (error) { fixture.forbiddenAcceptError = error as Error; }
      }
      const choice = decisions.shift();
      if (choice === undefined) throw new Error("test has no human choice");
      const decision = await ledger.createHumanDecisionAuthority().decideEditorial(human, { runId, offerId: offer.id, taskArtifactId: offer.taskArtifactId, inputArtifactIds: offer.inputArtifactIds, choice, rationale: `Choose ${choice}` }, durableContext);
      return { decisionArtifactId: decision.artifactId };
    },
  };
  return { root, ledger, args, ports, context, counts, get forbiddenAcceptError() { return fixture.forbiddenAcceptError; }, close: async () => { ledger.close(); await rm(root, { recursive: true, force: true }); } };
}
