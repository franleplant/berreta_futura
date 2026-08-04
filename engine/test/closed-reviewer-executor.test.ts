import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Agent as HttpsAgent, globalAgent } from "node:https";
import test from "node:test";

import {
  createDurableWorkflowPin,
  createRuntime,
  SQLiteDurableRunStore,
} from "@loops/core";

import { LocalAuthorityStore, type AuthorizedWorker } from "../authority/local-authority.ts";
import type {
  ArticleExecutionId,
  ArtifactId,
  AttemptId,
  JsonObject,
  JsonValue,
  ManuscriptRevisionId,
  RunId,
} from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  CLOSED_REVIEWER_RUNTIME_IDENTITY,
  ClosedReviewerError,
  createClosedReviewerExecutor,
  normalizeReviewResult,
  parseClosedReviewerOutput,
  type ClosedReviewerExecutionRequest,
  type ClosedReviewerReviewInput,
  type ClosedReviewerStep,
  type ClosedReviewerModelOutput,
} from "../executors/closed-reviewer/runtime.ts";
import type {
  ArticleReviewFinding,
  ReviewMaterialPackage,
} from "../workflows/article-review-panel.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";

const id = (value: string): ArtifactId => value as ArtifactId;
const runId = "closed-reviewer-run" as RunId;
const articleExecutionId = "closed-reviewer-execution" as ArticleExecutionId;
const manuscriptArtifactId = id("closed-reviewer-manuscript");
const sourceArtifactId = id("closed-reviewer-source");
const promptArtifactId = id("closed-reviewer-prompt");
const reviewPlanArtifactId = id("closed-reviewer-plan");
const manuscriptRevisionId = "closed-reviewer-manuscript-revision" as ManuscriptRevisionId;

type Fixture = {
  readonly root: string;
  readonly ledger: ArtifactLedger;
  readonly worker: AuthorizedWorker;
  readonly close: () => Promise<void>;
};

function revision(kind: InputRevisionRef["kind"], logicalId: string): InputRevisionRef {
  return { kind, logicalId, revisionId: `revision-${logicalId}` as never } as InputRevisionRef;
}

async function fixture(secret = "closed-reviewer-test-secret"): Promise<Fixture> {
  const root = await mkdtemp(join(tmpdir(), "mag-closed-reviewer-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  ledger.createArtifact({
    id: manuscriptArtifactId,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "imported",
    payload: { kind: "text", text: "# Current manuscript\n\nBody" },
    metadata: { articleId: "article-one", revisionId: manuscriptRevisionId },
  });
  for (const [artifactId, text] of [
    [sourceArtifactId, "Immutable source evidence"],
    [promptArtifactId, "Review prompt"],
    [reviewPlanArtifactId, "Review plan"],
  ] as const) {
    ledger.createArtifact({
      id: artifactId,
      kind: "review_input",
      schemaVersion: "review-input/1",
      mediaType: "text/plain",
      origin: "imported",
      payload: { kind: "text", text },
      metadata: { articleId: "article-one", revisionId: `revision-${artifactId}` },
    });
  }
  ledger.createRun({
    runId,
    articleExecutionId,
    articleId: "article-one",
    editionId: "004",
    workflowVersion: "closed-reviewer-test/1",
    loopsRunId: runId,
    manuscriptArtifactId,
    args: { articleId: "article-one" },
  });

  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollWorker({
    principalId: "closed-reviewer",
    authority: "model",
    capabilities: ["text_model", "source_access"],
  });
  const issued = await authority.createCredentialProfile({
    principalId: "closed-reviewer",
    credentialProfileId: "closed-reviewer-profile",
  });
  await authority.grant({
    credentialProfileId: issued.credentialProfileId,
    grantId: "closed-reviewer-grant",
    capabilities: ["text_model", "source_access"],
  });
  const worker = await authority.authenticate({
    credentialProfileId: issued.credentialProfileId,
    secret: issued.secret,
  });
  void secret;
  return {
    root,
    ledger,
    worker,
    close: async () => {
      ledger.close();
      await rm(root, { recursive: true, force: true });
    },
  };
}

function materials(ledger: ArtifactLedger): ReviewMaterialPackage {
  const artifactIds = [manuscriptArtifactId, sourceArtifactId, promptArtifactId] as const;
  const artifacts = artifactIds.map((artifactId) => {
    const loaded = ledger.readArtifact(artifactId);
    return {
      artifactId,
      articleId: "article-one",
      classification: artifactId === manuscriptArtifactId ? "manuscript" as const : artifactId === sourceArtifactId ? "source" as const : "judge_prompt" as const,
      mediaType: loaded.artifact.mediaType,
      digest: loaded.artifact.digest,
      bytes: new Uint8Array(loaded.bytes),
    };
  });
  return {
    schemaVersion: "article-review-material-package/1",
    articleId: "article-one",
    access: "source_aware",
    manuscriptArtifactId,
    manuscriptRevisionId,
    artifactIds,
    artifacts,
  };
}

function check() {
  return {
    id: "evidence",
    role: "article_review",
    access: "source_aware" as const,
    authority: "blocking" as const,
    promptArtifactId,
    reviewPlanArtifactId,
  };
}

function claim(overrides: Partial<ClosedReviewerReviewInput["claim"]> = {}): ClosedReviewerReviewInput["claim"] {
  return {
    schemaVersion: "article-attempt-claim/1",
    articleExecutionId,
    articleId: "article-one",
    operationKey: "review.evidence",
    role: "model",
    access: "source_aware",
    manuscriptArtifactId,
    manuscriptRevisionId,
    operationInputDigest: "sha256:review-input",
    claimId: "claim-1" as AttemptId,
    claimSequence: 1,
    attemptId: "attempt-1",
    attemptNumber: 1,
    fence: 1,
    principalId: "closed-reviewer",
    credentialProfileId: "closed-reviewer-profile",
    authority: "model",
    capabilities: ["text_model", "source_access"],
    leaseExpiresAt: "2026-08-04T00:00:00.000Z",
    durableContext: {
      kind: "step",
      runId,
      invocationId: "invocation-1",
      workflowName: "closed-reviewer-test",
      workflowVersion: "1",
      callId: "call-1",
      attemptId: "attempt-1",
      attemptNumber: 1,
      key: "review.evidence",
    },
    ...overrides,
  };
}

function directInput(ledger: ArtifactLedger): ClosedReviewerReviewInput {
  return {
    check: check(),
    materials: materials(ledger),
    manuscriptArtifactId,
    manuscriptRevisionId,
    claim: claim(),
  };
}

function responseEnvelope(): JsonObject {
  return {
    id: "resp_reviewer",
    object: "response",
    status: "completed",
    output: [{
      id: "msg_reviewer",
      type: "message",
      status: "completed",
      role: "assistant",
      content: [{
        type: "output_text",
        text: JSON.stringify({
          schemaVersion: "article-review-model-output/1",
          assessment: "pass",
          findings: [],
        }),
      }],
    }],
  };
}

test("reviewer output is strict and normalized with exact provenance", async () => {
  const f = await fixture();
  try {
    const parsed = parseClosedReviewerOutput({
      schemaVersion: "article-review-model-output/1",
      assessment: "pass",
      findings: [],
    });
    assert.equal(parsed.assessment, "pass");
    assert.throws(() => parseClosedReviewerOutput({
      schemaVersion: "article-review-model-output/1",
      assessment: "pass",
      findings: [],
      unexpected: true,
    }), (error: unknown) => error instanceof ClosedReviewerError && error.code === "REVIEWER_RESULT_SCHEMA");

    const input = directInput(f.ledger);
    const normalized = normalizeReviewResult(parsed, input);
    assert.equal(normalized.authenticatedPrincipalId, "closed-reviewer");
    assert.equal(normalized.checkId, "evidence");
    assert.equal(normalized.reviewPlanArtifactId, reviewPlanArtifactId);
    assert.deepEqual(normalized.materialArtifactIds, input.materials.artifactIds);

    const finding: ArticleReviewFinding = {
      localId: "outside",
      severity: "must_fix",
      scope: { kind: "document" },
      problem: "bad evidence",
      requestedOutcome: "fix",
      evidenceArtifactIds: [id("outside-material")],
    };
    assert.throws(() => normalizeReviewResult({
      schemaVersion: "article-review-model-output/1",
      assessment: "findings",
      findings: [finding],
    }, input), (error: unknown) => error instanceof ClosedReviewerError && error.code === "REVIEWER_EVIDENCE_OUTSIDE_MATERIALS");
    assert.throws(() => normalizeReviewResult(parsed, {
      ...input,
      claim: claim({ authority: "tool", capabilities: ["subprocess"] }),
    }), (error: unknown) => error instanceof ClosedReviewerError && error.code === "REVIEWER_CAPABILITY_INVALID");
  } finally {
    await f.close();
  }
});

test("reviewer factory rejects untrusted ledger-shaped objects", async () => {
  const f = await fixture();
  try {
    assert.throws(() => createClosedReviewerExecutor({
      ledger: { createArticleAttemptRunner: () => f.ledger.createArticleAttemptRunner() } as unknown as ArtifactLedger,
      credentials: { schemaVersion: "closed-writer-credential-resource/1", read: () => ({ OPENAI_API_KEY: "secret" }) },
    }), (error: unknown) => error instanceof ClosedReviewerError && error.code === "REVIEWER_FACTORY_INVALID");
  } finally {
    await f.close();
  }
});

test("real closed reviewer retries through Loops and records exact scoped provenance", async () => {
  if (process.env.CLOSED_REVIEWER_HTTPS_CHILD !== "1") {
    const secret = "closed-reviewer-child-secret";
    const childEnvironment: NodeJS.ProcessEnv = {
      ...process.env,
      CLOSED_REVIEWER_HTTPS_CHILD: "1",
      CLOSED_REVIEWER_TEST_SECRET: secret,
      CLOSED_REVIEWER_TEST_RESPONSE: JSON.stringify(responseEnvelope()),
      NODE_TLS_REJECT_UNAUTHORIZED: "0",
    };
    delete childEnvironment.NODE_TEST_CONTEXT;
    const child = spawnSync(process.execPath, [
      "--require",
      join(process.cwd(), "engine/test/fixtures/closed-reviewer-https-preload.cjs"),
      "--test",
      "--test-name-pattern=real closed reviewer retries",
      new URL(import.meta.url).pathname,
    ], {
      cwd: process.cwd(),
      encoding: "utf8",
      env: childEnvironment,
      timeout: 15_000,
    });
    assert.equal(child.status, 0, `${child.stdout}\n${child.stderr}`);
    assert.match(child.stdout, /real closed reviewer retries through Loops and records exact scoped provenance/u);
    return;
  }

  const secret = process.env.CLOSED_REVIEWER_TEST_SECRET!;
  const records = (globalThis as typeof globalThis & {
    __closedReviewerHttpsRecords: Array<{ options: { headers?: Record<string, string>; rejectUnauthorized?: boolean; servername?: string; agent?: HttpsAgent }; body: string }>;
  }).__closedReviewerHttpsRecords;
  const f = await fixture(secret);
  const loops = new SQLiteDurableRunStore(join(f.root, "reviewer-loops.sqlite"));
  try {
    const pin = createDurableWorkflowPin({
      source: { entryPath: "engine/test/closed-reviewer-executor.test.ts", graphHash: "sha256:reviewer-transport" },
      dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:reviewer-lock" },
      execution: { backend: "reviewer-transport-test" },
    });
    const runtime = createRuntime({
      backend: {
        name: "reviewer-transport-test",
        capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
        async run(): Promise<never> { throw new Error("agent calls are not part of reviewer transport test"); },
      },
      defaultBackend: "reviewer-transport-test",
      durable: { store: loops, runId, workflowName: "reviewer-transport-test", workflowPin: pin },
    });
    const executor = createClosedReviewerExecutor({
      ledger: f.ledger,
      credentials: {
        schemaVersion: "closed-writer-credential-resource/1",
        read: () => ({ OPENAI_API_KEY: secret }),
      },
    });
    const request: ClosedReviewerExecutionRequest = {
      worker: f.worker,
      articleExecutionId,
      operationKey: "review.evidence",
      check: check(),
      materials: materials(f.ledger),
      manuscriptArtifactId,
      manuscriptRevisionId,
    };
    const result = await runtime.run(async (globals) => await executor.executeInStep(
      (async (key, operation, options) => await globals.step(key, operation, { input: options.input, retry: options.retry })) as ClosedReviewerStep,
      request,
    ));
    assert.equal(result.selected, true);
    assert.equal(records.length, 2);
    for (const record of records) {
      assert.equal(record.options.headers?.authorization, `Bearer ${secret}`);
      assert.equal(record.options.rejectUnauthorized, true);
      assert.equal(record.options.servername, "api.openai.com");
      assert.ok(record.options.agent instanceof HttpsAgent);
      assert.notEqual(record.options.agent, globalAgent);
      assert.equal(record.options.agent.options.rejectUnauthorized, true);
      assert.equal(record.options.agent.options.minVersion, "TLSv1.2");
      assert.equal(record.body.includes(secret), false);
    }
    const inspection = loops.inspectRun(runId)!;
    const call = inspection.calls.find((candidate) => candidate.key === "review.evidence");
    assert.ok(call);
    const attempts = inspection.attempts.filter((attempt) => attempt.callId === call.callId);
    assert.deepEqual(attempts.map((attempt) => attempt.status), ["failed", "completed"]);
    const artifacts = f.ledger.listArtifacts(runId).filter((artifact) => artifact.kind === "article_review_result");
    assert.equal(artifacts.length, 1);
    const artifact = artifacts[0]!;
    assert.deepEqual(artifact.parents.map((parent) => parent.artifactId), request.materials.artifactIds);
    assert.equal(artifact.metadata.authenticatedPrincipalId, "closed-reviewer");
    assert.deepEqual(artifact.metadata.materialArtifactIds, request.materials.artifactIds);
    assert.equal(JSON.stringify(inspection).includes(secret), false);
    assert.equal(JSON.stringify(f.ledger.listArtifacts(runId)).includes(secret), false);
  } finally {
    loops.close();
    await f.close();
  }
});

void CLOSED_REVIEWER_RUNTIME_IDENTITY;
void ({} as ClosedReviewerModelOutput);
