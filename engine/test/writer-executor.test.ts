import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { Agent as HttpsAgent, globalAgent } from "node:https";

import { createDurableWorkflowPin, createRuntime, SQLiteDurableRunStore } from "@loops/core";

import { LocalAuthorityStore, type AuthorizedWorker } from "../authority/local-authority.ts";
import type { ArtifactId, ArticleExecutionId, JsonObject, JsonValue, RunId } from "../contracts/index.ts";
import type { ResolvedArticleProductionProfile, ResolvedReviewPlan } from "../contracts/production-plan.ts";
import type { LoopsArticleEntryInput } from "../durable/write-pipeline.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  CLOSED_WRITER_RUNTIME_IDENTITY,
  ClosedWriterError,
  createClosedWriterExecutor,
  type ClosedWriterExecutor,
  type ClosedWriterProfileEnvelope,
  type ClosedWriterStep,
} from "../executors/index.ts";
import {
  OpenAIResponsesError,
  buildOpenAIResponsesRequest,
  classifyOpenAIResponsesStatus,
  parseOpenAIResponsesBytes,
  parseOpenAIResponsesEnvelope,
} from "../executors/closed-writer/openai-responses-v1.ts";
import { buildFindingManifest } from "../executors/closed-writer/runtime.ts";
import { ClosedWriterResultError, parseWriterResult } from "../executors/closed-writer/writer-result.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";

const id = (value: string): ArtifactId => value as ArtifactId;
const RUN_ID = "writer-run" as RunId;
const ARTICLE_EXECUTION_ID = "writer-article-execution" as ArticleExecutionId;
const MANUSCRIPT_ID = id("writer-current-manuscript");
const RESOLVED_PROFILE_ID = id("writer-resolved-profile");

type Fixture = {
  readonly root: string;
  readonly ledger: ArtifactLedger;
  readonly worker: AuthorizedWorker;
  readonly writer: ClosedWriterExecutor;
  readonly close: () => Promise<void>;
};

async function fixture(options: { readonly invalidProfileParents?: boolean; readonly credential?: string } = {}): Promise<Fixture> {
  const root = await mkdtemp(join(tmpdir(), "mag-closed-writer-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  const entry = writerEntry();
  for (const binding of entry.inputBindings) {
    ledger.createArtifact({
      id: binding.artifactId,
      kind: "input_revision_payload",
      schemaVersion: "input-revision-payload/1",
      mediaType: binding.artifactId === id("source-extraction") ? "text/markdown" : "application/json",
      origin: "imported",
      payload: { kind: "text", text: binding.artifactId === id("source-extraction") ? "LEDGER-OWNED-SOURCE-BYTES" : `ledger:${binding.artifactId}` },
      metadata: { revisionId: binding.revision.revisionId, inputRevision: binding.revision as unknown as JsonValue },
    });
  }
  ledger.createArtifact({
    id: MANUSCRIPT_ID,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "imported",
    payload: { kind: "text", text: "# Prior manuscript" },
    parents: entry.inputBindings.map((binding) => ({ artifactId: binding.artifactId, relation: "input_binding" })),
    metadata: { articleId: entry.articleId, revisionId: "writer-revision-zero" },
  });
  const envelope: ClosedWriterProfileEnvelope = {
    schemaVersion: "resolved-article-production-profile/1",
    entry,
  };
  ledger.createRun({
    runId: RUN_ID,
    articleExecutionId: ARTICLE_EXECUTION_ID,
    articleId: entry.articleId,
    workflowVersion: "writer-test/1",
    loopsRunId: RUN_ID,
    manuscriptArtifactId: MANUSCRIPT_ID,
    args: { articleId: entry.articleId },
  });
  ledger.createArtifact({
    id: RESOLVED_PROFILE_ID,
    kind: "resolved_article_production_profile",
    schemaVersion: "resolved-article-production-profile/1",
    mediaType: "application/json",
    origin: "machine",
    payload: { kind: "json", value: envelope as unknown as JsonValue },
    parents: (options.invalidProfileParents ? entry.inputBindings.slice(1) : entry.inputBindings)
      .map((binding) => ({ artifactId: binding.artifactId, relation: "input_binding" })),
    runId: RUN_ID,
  });
  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollWorker({ principalId: "writer", authority: "model", capabilities: ["text_model", "source_access"] });
  const issued = await authority.createCredentialProfile({ principalId: "writer", credentialProfileId: "writer-profile" });
  await authority.grant({ credentialProfileId: issued.credentialProfileId, grantId: "writer-grant", capabilities: ["text_model", "source_access"] });
  const worker = await authority.authenticate({ credentialProfileId: issued.credentialProfileId, secret: issued.secret });
  const writer = createClosedWriterExecutor({
    ledger,
    credentials: {
      schemaVersion: "closed-writer-credential-resource/1",
      read: () => ({ OPENAI_API_KEY: options.credential ?? "test-openai-secret" }),
    },
  });
  return {
    root,
    ledger,
    worker,
    writer,
    close: async () => {
      ledger.close();
      await rm(root, { recursive: true, force: true });
    },
  };
}

function writerEntry(): LoopsArticleEntryInput {
  const refs = {
    source: revision("source_extraction", "source-one"),
    profile: revision("article_production_profile", "profile-one"),
    prompt: revision("prompt", "writer-prompt"),
    reviewPlan: revision("article_review_plan", "review-plan"),
    rules: revision("policy", "writing-rules"),
    policy: revision("policy", "writer-policy"),
  };
  const bindings = [
    [id("source-extraction"), refs.source],
    [id("profile-input"), refs.profile],
    [id("writer-prompt"), refs.prompt],
    [id("review-plan"), refs.reviewPlan],
    [id("writing-rules"), refs.rules],
    [id("writer-policy"), refs.policy],
  ] as const;
  const productionProfile: ResolvedArticleProductionProfile = {
    schemaVersion: "resolved-article-production-profile/1",
    profileId: "writer-profile",
    formatId: "magazine",
    profileArtifactId: id("profile-input"),
    writerPromptArtifactId: id("writer-prompt"),
    writerResultContractVersion: "article-writer-result/1",
    reviewMaterials: [],
    reviewPlanArtifactId: id("review-plan"),
    writingRulesArtifactId: id("writing-rules"),
    writingPolicyArtifactIds: [id("writer-policy")],
    maximumRewrites: 2,
  };
  const reviewPlan: ResolvedReviewPlan = {
    schemaVersion: "resolved-article-review-plan/1",
    reviewPlanArtifactId: id("review-plan"),
    checks: [],
    waves: [],
  };
  return {
    schemaVersion: "loops-article-entry-input/1",
    articleId: "article-one",
    contentMode: "faithful_synthesis",
    byline: "Source Author",
    sourceIds: ["source-one"],
    sourceAuthors: ["Source Author"],
    brief: "LEDGER-OWNED-BRIEF",
    maximumReaderPages: 7,
    modelPolicy: { default: { adapter: "openai-responses-v1", model: "gpt-5.6-terra", reasoningEffort: "high" } },
    productionProfile,
    writingRulesArtifactId: id("writing-rules"),
    reviewPlan,
    materializedInputs: bindings.map(([artifactId, ref]) => ({ ref, artifacts: [{ path: payloadPath(ref), artifactId }] })),
    inputBindings: bindings.map(([artifactId, ref]) => ({ artifactId, revision: ref })),
  };
}

function revision(kind: InputRevisionRef["kind"], logicalId: string): InputRevisionRef {
  return { kind, logicalId, revisionId: `revision-${logicalId}` as never } as InputRevisionRef;
}

function payloadPath(ref: InputRevisionRef): string {
  if (ref.kind === "source_extraction") return "extraction.md";
  if (ref.kind === "prompt") return "prompt.md";
  if (ref.kind === "policy") return "policy.md";
  if (ref.kind === "article_review_plan") return "review-plan.json";
  return "profile.json";
}

function validEnvelope(manuscript = "# Fresh draft"): JsonObject {
  return {
    id: "resp_writer",
    object: "response",
    status: "completed",
    output: [{
      id: "msg_writer",
      type: "message",
      status: "completed",
      role: "assistant",
      content: [{
        type: "output_text",
        text: JSON.stringify({
          schemaVersion: "article-writer-result/1",
          manuscript,
          workingNotes: "notes",
          dispositions: [],
          reviewMaterials: [],
        }),
      }],
    }],
  };
}

async function runWriter(f: Fixture, operationKey: string) {
  return await f.writer.executeInStep(
    (async (_key, operation, options) => {
      assert.deepEqual(options.retry, { maxAttempts: 2, retryOn: "retryable" });
      return await operation();
    }) as ClosedWriterStep,
    {
      worker: f.worker,
      articleExecutionId: ARTICLE_EXECUTION_ID,
      operationKey,
      currentManuscriptArtifactId: MANUSCRIPT_ID,
      productionProfileArtifactId: RESOLVED_PROFILE_ID,
    },
  );
}

test("request codec pins the official one-shot no-tool Responses request", () => {
  const request = buildOpenAIResponsesRequest("LEDGER-OWNED-PROMPT", "test-openai-secret");
  assert.deepEqual(
    { protocol: request.options.protocol, hostname: request.options.hostname, port: request.options.port, path: request.options.path, method: request.options.method },
    { protocol: "https:", hostname: "api.openai.com", port: 443, path: "/v1/responses", method: "POST" },
  );
  assert.equal(request.options.agent, undefined);
  assert.equal(request.options.rejectUnauthorized, true);
  assert.equal(request.options.servername, "api.openai.com");
  const body = JSON.parse(request.body) as Record<string, unknown>;
  assert.deepEqual(Object.keys(body).sort(), ["input", "max_output_tokens", "model", "reasoning", "store", "text"]);
  assert.equal(body.model, "gpt-5.6-terra");
  assert.deepEqual(body.reasoning, { effort: "high" });
  assert.equal(body.store, false);
  assert.equal("tools" in body, false);
  assert.equal("previous_response_id" in body, false);
  assert.match(request.body, /LEDGER-OWNED-PROMPT/u);
});

test("factory accepts a real ledger, creates its own runner, and rejects ledger-shaped objects", async () => {
  const f = await fixture();
  try {
    assert.equal(f.writer.runtimeIdentity, CLOSED_WRITER_RUNTIME_IDENTITY);
    assert.equal(Object.keys(f.writer).sort().join(","), "executeInStep,runtimeIdentity");
    assert.throws(() => createClosedWriterExecutor({
      ledger: { createArticleAttemptRunner: () => f.ledger.createArticleAttemptRunner() } as unknown as ArtifactLedger,
      credentials: { schemaVersion: "closed-writer-credential-resource/1", read: () => ({ OPENAI_API_KEY: "secret" }) },
    }), (error: unknown) => error instanceof ClosedWriterError && error.code === "WRITER_FACTORY_INVALID" && error.retryable === false);
  } finally {
    await f.close();
  }
});

test("profile parent mismatch is permanent and rejects before transport", async () => {
  const f = await fixture({ invalidProfileParents: true });
  try {
    await assert.rejects(runWriter(f, "writer-bad-lineage"), (error: unknown) =>
      error instanceof ClosedWriterError && error.code === "WRITER_PROFILE_LINEAGE_INVALID" && error.retryable === false);
  } finally {
    await f.close();
  }
});

test("writer mode pins revision context requirements before loading any package", async () => {
  const f = await fixture();
  try {
    const run = (request: Parameters<ClosedWriterExecutor["executeInStep"]>[1]) => f.writer.executeInStep(
      (async (_key, operation, _options) => await operation()) as ClosedWriterStep,
      request,
    );
    await assert.rejects(
      run({
        worker: f.worker,
        articleExecutionId: ARTICLE_EXECUTION_ID,
        operationKey: "writer-rewrite-without-context",
        currentManuscriptArtifactId: MANUSCRIPT_ID,
        productionProfileArtifactId: RESOLVED_PROFILE_ID,
        mode: "rewrite",
      } as unknown as Parameters<ClosedWriterExecutor["executeInStep"]>[1]),
      (error: unknown) => error instanceof ClosedWriterError && error.code === "WRITER_MODE_INVALID",
    );
    await assert.rejects(
      run({
        worker: f.worker,
        articleExecutionId: ARTICLE_EXECUTION_ID,
        operationKey: "writer-initial-with-context",
        currentManuscriptArtifactId: MANUSCRIPT_ID,
        productionProfileArtifactId: RESOLVED_PROFILE_ID,
        revisionContextArtifactId: id("unexpected-context"),
      } as unknown as Parameters<ClosedWriterExecutor["executeInStep"]>[1]),
      (error: unknown) => error instanceof ClosedWriterError && error.code === "WRITER_MODE_INVALID",
    );
  } finally {
    await f.close();
  }
});

test("response codec permits validated reasoning and one completed assistant output_text", () => {
  const envelope = validEnvelope();
  (envelope.output as JsonObject[]).unshift({
    id: "reasoning_writer",
    type: "reasoning",
    status: "completed",
    summary: [{ type: "summary_text", text: "brief summary" }],
  });
  const result = parseOpenAIResponsesEnvelope(envelope);
  assert.equal(result.responseId, "resp_writer");
  assert.equal((result.output as JsonObject).schemaVersion, "article-writer-result/1");
});

test("tool, unknown, malformed, and duplicate assistant outputs are permanent", () => {
  const cases: readonly JsonObject[] = [
    { id: "resp_tool", object: "response", status: "completed", output: [{ type: "function_call", name: "shell", arguments: "{}" }] },
    { id: "resp_bad", object: "response", status: "incomplete", output: [] },
    { ...validEnvelope(), output: [...validEnvelope().output as JsonValue[], ...validEnvelope().output as JsonValue[]] },
    { ...validEnvelope(), output: [{ id: "reasoning", type: "reasoning", summary: [{ type: "unknown", text: "bad" }] }, ...validEnvelope().output as JsonValue[]] },
  ];
  for (const envelope of cases) {
    assert.throws(() => parseOpenAIResponsesEnvelope(envelope), (error: unknown) => error instanceof OpenAIResponsesError && error.retryable === false);
  }
});

test("writer result schema failures are permanent", () => {
  assert.throws(() => parseWriterResult({ manuscript: "missing contract envelope" }), (error: unknown) =>
    error instanceof ClosedWriterResultError && error.retryable === false);
});

test("only transport-class HTTP statuses are retryable and redirects are rejected", () => {
  for (const status of [400, 401, 404, 422]) assert.equal(classifyOpenAIResponsesStatus(status).retryable, false);
  for (const status of [408, 409, 429, 500, 502, 503]) assert.equal(classifyOpenAIResponsesStatus(status).retryable, true);
  const redirect = classifyOpenAIResponsesStatus(307);
  assert.equal(redirect.code, "WRITER_REDIRECT_REJECTED");
  assert.equal(redirect.retryable, false);
});

test("response codec enforces the byte ceiling before parsing", () => {
  const oversized = Buffer.alloc(CLOSED_WRITER_RUNTIME_IDENTITY.maxResponseBytes + 1, 0x20);
  assert.throws(() => parseOpenAIResponsesBytes(oversized), (error: unknown) =>
    error instanceof OpenAIResponsesError && error.code === "WRITER_RESPONSE_TOO_LARGE" && error.retryable === false);
});

test("finding manifest has stable exact IDs and content digests", () => {
  const digestA = "a".repeat(64);
  const digestB = "b".repeat(64);
  const manifest = buildFindingManifest([
    { reviewResultArtifactId: "review-b", localId: "finding-2", contentDigest: digestB },
    { reviewResultArtifactId: "review-a", localId: "finding-1", contentDigest: digestA },
  ]);
  assert.deepEqual(manifest, [
    { findingId: "review-a#finding-1", reviewResultArtifactId: "review-a", localId: "finding-1", contentDigest: digestA },
    { findingId: "review-b#finding-2", reviewResultArtifactId: "review-b", localId: "finding-2", contentDigest: digestB },
  ]);
  const copied = (manifest as JsonObject[])[0]!;
  assert.doesNotThrow(() => parseWriterResult({
    schemaVersion: "article-writer-result/1",
    manuscript: "# Draft",
    workingNotes: "",
    dispositions: [{
      finding: { reviewResultArtifactId: copied.reviewResultArtifactId, localId: copied.localId, contentDigest: copied.contentDigest },
      status: "addressed",
      explanation: "fixed",
    }],
    reviewMaterials: [],
  }));
});

test("real executor retries through Loops and keeps credential out of provenance", async () => {
  if (process.env.CLOSED_WRITER_HTTPS_CHILD !== "1") {
    const secret = "closed-writer-child-secret";
    const childEnvironment: NodeJS.ProcessEnv = {
      ...process.env,
      CLOSED_WRITER_HTTPS_CHILD: "1",
      CLOSED_WRITER_TEST_SECRET: secret,
      CLOSED_WRITER_TEST_RESPONSE: JSON.stringify(validEnvelope("# Retry winner")),
      NODE_TLS_REJECT_UNAUTHORIZED: "0",
    };
    delete childEnvironment.NODE_TEST_CONTEXT;
    const child = spawnSync(process.execPath, [
      "--require",
      join(process.cwd(), "engine/test/fixtures/closed-writer-https-preload.cjs"),
      "--test",
      "--test-name-pattern=real executor retries through Loops",
      new URL(import.meta.url).pathname,
    ], {
      cwd: process.cwd(),
      encoding: "utf8",
      env: childEnvironment,
      timeout: 15_000,
    });
    assert.equal(child.status, 0, `${child.stdout}\n${child.stderr}`);
    assert.match(child.stdout, /real executor retries through Loops and keeps credential out of provenance/u);
    return;
  }

  const secret = process.env.CLOSED_WRITER_TEST_SECRET!;
  const records = (globalThis as typeof globalThis & {
    __closedWriterHttpsRecords: Array<{ options: { headers?: Record<string, string>; rejectUnauthorized?: boolean; servername?: string; agent?: HttpsAgent }; body: string }>;
  }).__closedWriterHttpsRecords;
  const f = await fixture({ credential: secret });
  const loops = new SQLiteDurableRunStore(join(f.root, "writer-loops.sqlite"));
  try {
    const pin = createDurableWorkflowPin({
      source: { entryPath: "engine/test/writer-executor.test.ts", graphHash: "sha256:writer-transport-test" },
      dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:writer-transport-lock" },
      execution: { backend: "writer-transport-test" },
    });
    const runtime = createRuntime({
      backend: {
        name: "writer-transport-test",
        capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
        async run(): Promise<never> { throw new Error("agent calls are not part of the writer transport test"); },
      },
      defaultBackend: "writer-transport-test",
      durable: { store: loops, runId: RUN_ID, workflowName: "writer-transport-test", workflowPin: pin },
    });
    const result = await runtime.run(async (globals) => await f.writer.executeInStep(
      (async (key, operation, options) => await globals.step(key, operation, { input: options.input, retry: options.retry })) as ClosedWriterStep,
      {
        worker: f.worker,
        articleExecutionId: ARTICLE_EXECUTION_ID,
        operationKey: "writer-real-retry",
        currentManuscriptArtifactId: MANUSCRIPT_ID,
        productionProfileArtifactId: RESOLVED_PROFILE_ID,
      },
    ));
    assert.equal(result.selected, true);
    assert.equal(records.length, 2);
    for (const record of records) {
      assert.equal(record.options.headers?.authorization, `Bearer ${secret}`);
      assert.deepEqual(Object.entries(record.options.headers ?? {}).filter(([, value]) => String(value).includes(secret)), [["authorization", `Bearer ${secret}`]]);
      assert.equal(record.options.rejectUnauthorized, true);
      assert.equal(record.options.servername, "api.openai.com");
      assert.ok(record.options.agent instanceof HttpsAgent);
      assert.notEqual(record.options.agent, globalAgent);
      assert.equal(record.options.agent.options.rejectUnauthorized, true);
      assert.equal(record.options.agent.options.minVersion, "TLSv1.2");
      assert.equal(record.body.includes(secret), false);
    }
    const inspection = loops.inspectRun(RUN_ID)!;
    const call = inspection.calls.find((candidate) => candidate.key === "writer-real-retry");
    assert.ok(call);
    const attempts = inspection.attempts.filter((attempt) => attempt.callId === call.callId);
    assert.deepEqual(attempts.map((attempt) => attempt.status), ["failed", "completed"]);
    assert.deepEqual(attempts.map((attempt) => attempt.attemptNumber), [1, 2]);
    const selected = f.ledger.listArtifacts(RUN_ID).filter((artifact) => artifact.kind === "article_manuscript");
    assert.equal(selected.length, 1);
    assert.equal(selected[0]?.metadata.attemptId, attempts[1]?.attemptId);
    assert.equal(result.claim?.attemptId, attempts[1]?.attemptId);
    assert.equal(JSON.stringify(inspection).includes(secret), false);
    assert.equal(JSON.stringify(f.ledger.listArtifacts(RUN_ID)).includes(secret), false);
  } finally {
    loops.close();
    await f.close();
  }
});
