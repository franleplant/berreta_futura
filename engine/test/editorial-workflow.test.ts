import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createDurableWorkflowPin, createRuntime, SQLiteDurableRunStore } from "@loops/core";

import { LocalAuthorityStore } from "../authority/local-authority.ts";
import type { ArtifactId, JsonObject, JsonValue, RunId } from "../contracts/index.ts";
import { createClosedEditorialWriterExecutor } from "../executors/closed-editorial-writer/runtime.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import {
  invokeEditorialWorkflowWithPorts,
  type OpeningEditorialWorkflowArgs,
} from "../workflows/index.ts";
import type { ArticleWorkflowPorts, WorkflowWaitContext } from "../workflows/internal-types.ts";

const id = (value: string): ArtifactId => value as ArtifactId;
const RUN_ID = "editorial-run" as RunId;
const EXECUTION_ID = "editorial-execution";

test("seven accepted manuscripts produce, review, accept, promote, and replay one opening editorial", async () => {
  if (process.env.CLOSED_EDITORIAL_HTTPS_CHILD !== "1") {
    const environment: NodeJS.ProcessEnv = {
      ...process.env,
      CLOSED_EDITORIAL_HTTPS_CHILD: "1",
      CLOSED_WRITER_TEST_SECRET: "editorial-test-secret",
      CLOSED_WRITER_TEST_RESPONSE: JSON.stringify(openAIEnvelope()),
      NODE_TLS_REJECT_UNAUTHORIZED: "0",
    };
    delete environment.NODE_TEST_CONTEXT;
    const child = spawnSync(process.execPath, [
      "--require",
      join(process.cwd(), "engine/test/fixtures/closed-writer-https-preload.cjs"),
      "--test",
      "--test-name-pattern=seven accepted manuscripts",
      new URL(import.meta.url).pathname,
    ], { cwd: process.cwd(), encoding: "utf8", env: environment, timeout: 30_000 });
    assert.equal(child.status, 0, `${child.stdout}\n${child.stderr}`);
    return;
  }

  const root = await mkdtemp(join(tmpdir(), "mag-editorial-workflow-"));
  const ledgerPath = join(root, "magazine.sqlite");
  const loopsPath = join(root, "loops.sqlite");
  let ledger = new ArtifactLedger(ledgerPath);
  let store = new SQLiteDurableRunStore(loopsPath);
  try {
    const articles = Array.from({ length: 7 }, (_, index) => id(`accepted-article-${index + 1}`));
    for (const [index, artifactId] of articles.entries()) {
      ledger.createArtifact({ id: artifactId, kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "machine", payload: { kind: "text", text: `# Article ${index + 1}` }, metadata: { articleId: `article-${index + 1}`, revisionId: `article-revision-${index + 1}` } });
    }
    const acceptedId = id("accepted-english-inputs");
    const seedId = id("editorial-seed");
    const profileId = id("editorial-profile");
    const measurementProfileId = id("editorial-measurement-profile");
    const reviewPlanId = id("editorial-review-plan");
    const entryId = id("editorial-entry");
    ledger.createArtifact({ id: acceptedId, kind: "accepted_english_issue_inputs", schemaVersion: "accepted-english-issue-inputs/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "accepted-english-issue-inputs/1", pipelineRef: { kind: "write_pipeline", editionId: "004", logicalId: "edition-004", revisionId: "pipeline-revision" }, articles: articles.map((manuscriptArtifactId, index) => ({ articleId: `article-${index + 1}`, manuscriptArtifactId })) } }, parents: articles.map((artifactId) => ({ artifactId, relation: "accepted_article" })) });
    ledger.createArtifact({ id: seedId, kind: "editorial_input_set", schemaVersion: "editorial-input-set/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-input-set/1", articleArtifactIds: articles } }, parents: articles.map((artifactId) => ({ artifactId, relation: "editorial_article_input" })), metadata: { articleId: "opening", revisionId: "editorial-seed-revision" } });
    ledger.createArtifact({ id: reviewPlanId, kind: "editorial_review_plan", schemaVersion: "editorial-review-plan/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-review-plan/1", editionId: "004" } } });
    ledger.createArtifact({ id: measurementProfileId, kind: "editorial_measurement_profile", schemaVersion: "editorial-measurement-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-measurement-profile/1", maximumReaderPages: 1 } } });
    const args: OpeningEditorialWorkflowArgs = {
      schemaVersion: "magazine-opening-editorial/1", editionId: "004", runId: RUN_ID, editionRunId: "edition-root" as RunId,
      editorialExecutionId: EXECUTION_ID, editorialId: "opening", seedManuscriptArtifactId: seedId,
      measurementProfileArtifactId: measurementProfileId, profileArtifactId: profileId, entryArtifactId: entryId,
      acceptedEnglishInputsArtifactId: acceptedId, articleArtifactIds: articles,
      articleExecutionIds: articles.map((_, index) => `article-execution-${index + 1}`), maximumReaderPages: 1,
      maximumRewrites: 0, reviewPlanArtifactId: reviewPlanId,
    };
    ledger.createRun({ runId: RUN_ID, articleExecutionId: EXECUTION_ID as never, articleId: "opening", editionId: "004", workflowVersion: "editorial-test/1", loopsRunId: RUN_ID, manuscriptArtifactId: seedId, args: args as unknown as JsonObject });
    ledger.createArtifact({ id: profileId, kind: "resolved_editorial_profile", schemaVersion: "resolved-editorial-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "resolved-editorial-profile/1", editionId: "004", editorialId: "opening", brief: "Develop one unifying idea", modelPolicy: { default: { adapter: "openai-responses-v1", model: "gpt-5.6-terra", reasoningEffort: "high" } } } }, parents: articles.map((artifactId) => ({ artifactId, relation: "editorial_profile_input" })), metadata: { editionId: "004", editorialId: "opening" }, runId: RUN_ID });
    ledger.createArtifact({ id: entryId, kind: "editorial_workflow_entry", schemaVersion: "magazine-opening-editorial/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: args as unknown as JsonValue }, parents: [{ artifactId: profileId, relation: "editorial_profile" }, { artifactId: acceptedId, relation: "accepted_english_inputs" }], metadata: { editionId: "004", editorialId: "opening" }, runId: RUN_ID });

    const authority = await LocalAuthorityStore.init(join(root, "authority"));
    await authority.enrollWorker({ principalId: "editorial-writer", authority: "model", capabilities: ["text_model", "source_blind"] });
    const writerCredential = await authority.createCredentialProfile({ principalId: "editorial-writer", credentialProfileId: "editorial-writer-profile" });
    await authority.grant({ credentialProfileId: writerCredential.credentialProfileId, capabilities: ["text_model", "source_blind"] });
    const writerWorker = await authority.authenticate({ credentialProfileId: writerCredential.credentialProfileId, secret: writerCredential.secret });
    await authority.enrollHuman({ principalId: "editor", capabilities: ["text_model"] });
    const humanCredential = await authority.createCredentialProfile({ principalId: "editor", credentialProfileId: "editor-profile" });
    await authority.grant({ credentialProfileId: humanCredential.credentialProfileId, capabilities: ["text_model"] });
    const human = await authority.authenticate({ credentialProfileId: humanCredential.credentialProfileId, secret: humanCredential.secret });
    const writer = createClosedEditorialWriterExecutor({ ledger, credentials: { schemaVersion: "closed-writer-credential-resource/1", read: () => ({ OPENAI_API_KEY: process.env.CLOSED_WRITER_TEST_SECRET! }) } });
    let reviewCalls = 0;
    let measurementCalls = 0;
    let promotionCalls = 0;
    const ports: ArticleWorkflowPorts = {
      ledger,
      measureArticle: async () => { throw new Error("article measurement is out of scope"); },
      runReviewPanel: async () => { throw new Error("article review is out of scope"); },
      runEditorialWriter: async (input, context) => await writer.executeInStep(
        async (key, operation, options) => await context.step(key, operation, { input: options.input, retry: options.retry }),
        { worker: writerWorker, ...input },
      ),
      measureEditorial: async (input) => {
        measurementCalls += 1;
        const value = { schemaVersion: "editorial-measurement/1", operation: "measure_edition", editionId: "004", editorialId: "opening", language: "en", manuscriptArtifactId: input.manuscriptArtifactId, contentArtifactIds: [input.manuscriptArtifactId, ...input.articleArtifactIds], inputArtifactIds: [input.manuscriptArtifactId, ...input.articleArtifactIds], pageCount: 1, maximumReaderPages: 1, fits: true, labelVisible: true, labelFits: true, titleVisible: true, titleFits: true, bylineVisible: true, bylineFits: true } as const;
        const artifactId = id(`editorial-measurement-${input.manuscriptArtifactId}`);
        ledger.createArtifact({ id: artifactId, kind: "editorial_measurement", schemaVersion: "editorial-measurement/1", mediaType: "application/json", origin: "subprocess", payload: { kind: "json", value: value as unknown as JsonValue }, parents: [input.manuscriptArtifactId, ...input.articleArtifactIds, input.measurementProfileArtifactId].map((artifactId) => ({ artifactId, relation: "editorial_measurement_input" })), metadata: { measurementExecutionClass: "authenticated_measure_edition/1", access: "tool", claimId: "claim-measure", attemptId: "attempt-measure", principalId: "renderer", operationInputDigest: "digest-measure" }, runId: RUN_ID });
        return { selected: true, adopted: true, artifacts: [ledger.requireArtifact(artifactId)] };
      },
      runEditorialReview: async (input) => {
        reviewCalls += 1;
        const artifactId = id(`editorial-review-${reviewCalls}`);
        const value = { schemaVersion: "editorial-review-result/1", editionId: "004", editorialId: "opening", target: "editorial:opening", manuscriptArtifactId: input.manuscriptArtifactId, measurementArtifactId: input.measurementArtifactId, reviewPlanArtifactId: input.reviewPlanArtifactId, reviewCycleId: input.reviewCycleId, assessment: "pass", findings: [] } as const;
        const inputs = [input.manuscriptArtifactId, input.reviewPlanArtifactId, input.measurementArtifactId];
        ledger.createArtifact({ id: artifactId, kind: "editorial_review_result", schemaVersion: "editorial-review-result/1", mediaType: "application/json", origin: "model", payload: { kind: "json", value: value as unknown as JsonValue }, parents: inputs.map((artifactId) => ({ artifactId, relation: "editorial_review_input" })), metadata: { reviewerExecutionClass: "closed_editorial_reviewer/1", access: "source_blind", claimId: "claim-review", attemptId: "attempt-review", principalId: "reviewer", operationInputDigest: "digest-review", reviewerInputArtifactIds: inputs as unknown as JsonValue }, runId: RUN_ID });
        return { selected: true, findings: [], artifacts: [ledger.requireArtifact(artifactId)] };
      },
      promoteEditorial: async (input) => {
        promotionCalls += 1;
        const artifactId = id("editorial-promotion");
        ledger.createArtifact({ id: artifactId, kind: "editorial_durable_promotion", schemaVersion: "editorial-durable-promotion/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-durable-promotion/1", request: input.request as unknown as JsonValue } }, parents: [{ artifactId: input.request.acceptedArtifactIds[0]!, relation: "accepted_editorial" }, { artifactId: input.decisionArtifactId, relation: "human_decision" }], runId: RUN_ID });
        return { promotionArtifactId: artifactId, durableRevisionId: input.request.revisionId, manifestDigest: "sha256:editorial", gitCommitOid: "editorial-commit" };
      },
      requireDecision: () => { throw new Error("article decisions are out of scope"); },
      promote: async () => { throw new Error("article promotion is out of scope"); },
    };
    const pin = createDurableWorkflowPin({ source: { entryPath: "engine/workflows/editorial-loops-entry.ts", graphHash: "sha256:editorial-test" }, dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:editorial-lock" }, execution: { backend: "editorial-test" } });
    const runtime = createRuntime({ backend: { name: "editorial-test", capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false }, async run(): Promise<never> { throw new Error("no agents"); } }, defaultBackend: "editorial-test", durable: { store, runId: RUN_ID, workflowName: "magazine-opening-editorial", workflowPin: pin, args }, args });
    await assert.rejects(runtime.run((globals) => invokeEditorialWorkflowWithPorts(globals, ports, args)), /suspend|waiting/iu);
    const waiting = store.inspectRun(RUN_ID)!;
    const wait = waiting.waits.find((candidate) => candidate.status === "pending")!;
    const invocation = waiting.invocations.find((candidate) => candidate.invocationId === wait.invocationId)!;
    const offer = ledger.activeOffer(RUN_ID)!;
    const durableContext: WorkflowWaitContext = { runId: RUN_ID, invocationId: invocation.invocationId, workflowName: invocation.workflowName, workflowVersion: invocation.workflowVersion, ...(invocation.workflowPin === undefined ? {} : { workflowPin: invocation.workflowPin as unknown as JsonObject }), callId: wait.callId, waitId: wait.waitId, key: wait.key, kind: "wait" };
    const decision = await ledger.createHumanDecisionAuthority().decideEditorial(human, { runId: RUN_ID, offerId: offer.id, taskArtifactId: offer.taskArtifactId, inputArtifactIds: offer.inputArtifactIds, choice: "accept", rationale: "Ready" }, durableContext);
    await store.answerWait({ runId: RUN_ID, waitId: wait.waitId, answer: { decisionArtifactId: decision.artifactId } });
    const completed = await runtime.run((globals) => invokeEditorialWorkflowWithPorts(globals, ports, args)) as { readonly status: string; readonly promotionArtifactId: ArtifactId };
    assert.equal(completed.status, "complete");
    assert.equal(completed.promotionArtifactId, id("editorial-promotion"));
    const transportRecords = (globalThis as typeof globalThis & { __closedWriterHttpsRecords: unknown[] }).__closedWriterHttpsRecords;
    assert.equal(transportRecords.length, 2);
    const reopened = await runtime.run((globals) => invokeEditorialWorkflowWithPorts(globals, ports, args)) as { readonly status: string };
    assert.equal(reopened.status, "complete");
    assert.equal(transportRecords.length, 2);
    assert.equal(reviewCalls, 1);
    assert.equal(measurementCalls, 1);
    assert.equal(promotionCalls, 1);
    assert.equal(ledger.listArtifacts(RUN_ID).filter((artifact) => artifact.kind === "editorial_manuscript").length, 1);
    assert.equal(ledger.listArtifacts(RUN_ID).filter((artifact) => artifact.kind === "editorial_durable_promotion").length, 1);
    store.close();
    ledger.close();
    store = new SQLiteDurableRunStore(loopsPath);
    ledger = new ArtifactLedger(ledgerPath);
    const reopenedRuntime = createRuntime({ backend: { name: "editorial-test", capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false }, async run(): Promise<never> { throw new Error("no agents"); } }, defaultBackend: "editorial-test", durable: { store, runId: RUN_ID, workflowName: "magazine-opening-editorial", workflowPin: pin, args }, args });
    const afterReopen = await reopenedRuntime.run((globals) => invokeEditorialWorkflowWithPorts(globals, ports, args)) as { readonly status: string };
    assert.equal(afterReopen.status, "complete");
    assert.equal(transportRecords.length, 2);
    assert.equal(reviewCalls, 1);
    assert.equal(measurementCalls, 1);
    assert.equal(promotionCalls, 1);
  } finally {
    store.close();
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

function openAIEnvelope(): JsonObject {
  return { id: "resp_editorial", object: "response", status: "completed", output: [{ id: "msg_editorial", type: "message", status: "completed", role: "assistant", content: [{ type: "output_text", text: JSON.stringify({ schemaVersion: "editorial-writer-result/1", label: "Opening", title: "One Idea", byline: "Magazine", manuscript: "---\nlabel: Opening\ntitle: One Idea\nbyline: Magazine\n---\n\nThe opening.", workingNotes: "", dispositions: [] }) }] }] };
}
