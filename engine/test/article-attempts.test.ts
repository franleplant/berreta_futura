import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createDurableWorkflowPin, createRuntime, DurableCallFailedError, SQLiteDurableRunStore } from "@loops/core";

import { LocalAuthorityStore } from "../authority/local-authority.ts";
import { articleExecutionIdFor, type ArticleExecutionId, type ArtifactId, type RunId } from "../contracts/index.ts";
import { ArtifactLedger, ArtifactLedgerError } from "../workflow-authority/artifact-ledger.ts";
import { ArticleAttemptRunner } from "../article-production/attempts.ts";
import type { ArticleMaterialSet } from "../article-production/materials.ts";

const runId = "loops-root" as RunId;
const articleExecutionId = "article-execution-test" as ArticleExecutionId;
const manuscript = "manuscript-v1" as ArtifactId;
const attemptPin = createDurableWorkflowPin({
  source: { entryPath: "engine/test/article-attempts.test.ts", graphHash: "sha256:test-graph" },
  dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:test-lock" },
  execution: { backend: "attempt-test" },
});
const attemptBackend = {
  name: "attempt-test",
  capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
  async run(): Promise<never> { throw new Error("agent calls are not part of this test"); },
};
let attemptInvocation = 0;

function hasErrorCode(error: unknown, code: string): boolean {
  if (error instanceof ArtifactLedgerError) return error.code === code;
  return error instanceof DurableCallFailedError && error.failure.code === code;
}

function materials(access: "source_aware" | "source_blind", manuscriptArtifactIdValue = manuscript): ArticleMaterialSet {
  return {
    schemaVersion: "article-material-set/1",
    articleId: "article-one",
    role: "article_review",
    access,
    manuscriptArtifactId: manuscriptArtifactIdValue,
    artifacts: [{ artifactId: manuscriptArtifactIdValue, articleId: "article-one", classification: "manuscript" }],
    artifactIds: [manuscriptArtifactIdValue],
  };
}

async function fixture(): Promise<{
  readonly root: string;
  readonly ledger: ArtifactLedger;
  readonly runner: ArticleAttemptRunner;
  readonly aware: import("../authority/local-authority.ts").AuthorizedWorker;
  readonly blind: import("../authority/local-authority.ts").AuthorizedWorker;
  readonly clock: { now: () => Date; advance: (ms: number) => void };
}> {
  const root = await mkdtemp(join(tmpdir(), "mag-article-attempt-"));
  let nowMs = Date.parse("2026-08-03T00:00:00.000Z");
  const clock = { now: () => new Date(nowMs), advance: (ms: number) => { nowMs += ms; } };
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"), { clock, articleAttemptLeaseMs: 1_000 });
  ledger.createArtifact({
    id: manuscript,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "imported",
    payload: { kind: "text", text: "# manuscript" },
    metadata: { articleId: "article-one", revisionId: "revision-one" },
  });
  ledger.createRun({
    runId,
    articleExecutionId,
    articleId: "article-one",
    editionId: "004",
    workflowVersion: "workflow/1",
    loopsRunId: runId,
    manuscriptArtifactId: manuscript,
    args: { articleId: "article-one" },
  });
  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollWorker({ principalId: "reviewer", authority: "model", capabilities: ["text_model", "source_access", "source_blind"] });
  const credential = await authority.createCredentialProfile({ principalId: "reviewer", credentialProfileId: "reviewer-profile" });
  await authority.grant({ credentialProfileId: credential.credentialProfileId, grantId: "reviewer-grant", capabilities: ["text_model", "source_access", "source_blind"] });
  const worker = await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });
  await authority.enrollWorker({ principalId: "blind-reviewer", authority: "model", capabilities: ["text_model", "source_blind"] });
  const blindCredential = await authority.createCredentialProfile({ principalId: "blind-reviewer", credentialProfileId: "blind-profile" });
  await authority.grant({ credentialProfileId: blindCredential.credentialProfileId, grantId: "blind-grant", capabilities: ["text_model", "source_blind"] });
  const blind = await authority.authenticate({ credentialProfileId: blindCredential.credentialProfileId, secret: blindCredential.secret });
  return { root, ledger, runner: ledger.createArticleAttemptRunner(), aware: worker, blind, clock };
}

function request(access: "source_aware" | "source_blind", operationKey: string, manuscriptArtifactIdValue = manuscript) {
  return {
    rootRunId: runId,
    articleExecutionId,
    articleId: "article-one",
    operationKey,
    manuscriptArtifactId: manuscriptArtifactIdValue,
    access,
    materials: materials(access, manuscriptArtifactIdValue),
  };
}

async function inAttempt<T>(fixtureValue: { readonly root: string }, operationKey: string, fn: () => Promise<T> | T, _attemptNumber = 1): Promise<T> {
  const store = new SQLiteDurableRunStore(join(fixtureValue.root, `attempt-loops-${attemptInvocation++}.sqlite`));
  const runtime = createRuntime({
    backend: attemptBackend,
    defaultBackend: "attempt-test",
    durable: { store, runId, workflowName: "attempt-test", workflowPin: attemptPin },
  });
  try {
    return await runtime.run(async (globals) => await globals.step(operationKey, fn, { retry: { maxAttempts: 1, retryOn: "always" } }));
  } finally {
    store.close();
  }
}

test("one principal cannot cross source-aware and source-blind article attempts", async () => {
  const f = await fixture();
  try {
    await inAttempt(f, "evidence", () => f.runner.claimModel(f.aware, request("source_aware", "evidence")));
    await assert.rejects(
      inAttempt(f, "craft", () => f.runner.claimModel(f.aware, request("source_blind", "craft"))),
      (error: unknown) => hasErrorCode(error, "ATTEMPT_EXPOSURE_CONFLICT"),
    );
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("claims are fenced under concurrent and retry attempts", async () => {
  const f = await fixture();
  try {
    const claims = await Promise.allSettled([
      inAttempt(f, "parallel", () => f.runner.claimModel(f.aware, request("source_aware", "parallel"))),
      inAttempt(f, "parallel", () => f.runner.claimModel(f.blind, request("source_blind", "parallel"))),
    ]);
    assert.equal(claims.filter((item) => item.status === "fulfilled").length, 1);
    const rejected = claims.find((item) => item.status === "rejected");
    assert.equal(rejected?.status, "rejected");
    assert.equal(hasErrorCode((rejected as PromiseRejectedResult).reason, "ATTEMPT_UNAVAILABLE"), true);
    f.clock.advance(2_000);
    const retry = await inAttempt(f, "parallel", () => f.runner.claimModel(f.aware, request("source_aware", "parallel")), 2);
    assert.equal(retry.claimSequence, 2);
    assert.notEqual(retry.claimId, (claims.find((item) => item.status === "fulfilled") as PromiseFulfilledResult<Awaited<ReturnType<typeof f.runner.claimModel>>>).value.claimId);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("stale attempts can leave orphan artifacts but cannot select a result", async () => {
  const f = await fixture();
  try {
    const old = await inAttempt(f, "stale", () => f.runner.claimModel(f.aware, request("source_aware", "stale")));
    f.clock.advance(2_000);
    const current = await inAttempt(f, "stale", () => f.runner.claimModel(f.aware, request("source_aware", "stale")), 2);
    await assert.rejects(Promise.resolve().then(() => f.runner.heartbeat(old)), (error: unknown) => error instanceof ArtifactLedgerError && error.code === "ATTEMPT_STALE");
    const selected = await inAttempt(f, "winner", () => f.runner.executeModel(f.aware, request("source_aware", "winner"), async () => ({
      value: "ok",
      artifacts: [],
    })));
    assert.equal(selected.selected, true);
    assert.notEqual(current.claimId, old.claimId);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("attempt artifacts retain exact Loops provenance and attempt-scoped IDs", async () => {
  const f = await fixture();
  try {
    const result = await inAttempt(f, "provenance", () => f.runner.executeModel(f.aware, request("source_aware", "provenance"), async () => ({
      value: { ok: true },
      artifacts: [{
        key: "judgment",
        kind: "article_judgment",
        schemaVersion: "article-judgment/1",
        mediaType: "application/json",
        origin: "model" as const,
        payload: { kind: "json" as const, value: { ok: true } },
      }],
    })));
    assert.equal(result.selected, true);
    if (!result.selected) throw new Error("expected selected attempt");
    const artifact = result.artifacts[0]!;
    if (artifact.durableContext === undefined || (artifact.durableContext.kind !== "agent" && artifact.durableContext.kind !== "step")) {
      throw new Error("expected attempt durable context");
    }
    assert.match(artifact.id, /^art-attempt-[0-9a-f]{64}$/u);
    assert.equal(artifact.durableContext?.runId, runId);
    assert.equal(artifact.durableContext?.workflowName, "attempt-test");
    assert.equal(artifact.durableContext?.key, "provenance");
    assert.equal(artifact.durableContext?.callId !== undefined, true);
    assert.equal(artifact.durableContext?.attemptId !== undefined, true);
    assert.equal(artifact.durableContext?.attemptNumber, 1);
    assert.equal(artifact.metadata.articleExecutionId, articleExecutionId);
    assert.equal(artifact.metadata.attemptId, artifact.durableContext?.attemptId);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("a real durable Loops step binds attempt provenance and selects only the successful retry", async () => {
  const f = await fixture();
  const loops = new SQLiteDurableRunStore(join(f.root, "attempt-loops.sqlite"));
  let executions = 0;
  try {
    const runtime = createRuntime({
      backend: attemptBackend,
      defaultBackend: "attempt-test",
      durable: { store: loops, runId, workflowName: "attempt-test", workflowPin: attemptPin },
    });
    await runtime.run(async (globals) => await globals.step("durable-attempt", async () => {
      const raw = globals.durableContext?.();
      if (raw === undefined || raw.kind !== "step" || raw.callId === undefined || raw.attemptId === undefined || raw.attemptNumber === undefined || raw.key === undefined) {
        throw new Error("expected exact Loops step provenance");
      }
      executions += 1;
      if (executions === 1) throw new Error("first durable attempt fails");
      return await f.runner.executeModel(f.aware, request("source_aware", "durable-attempt"), async () => ({
        value: "selected",
        artifacts: [{
          key: "retry-success",
          kind: "article_judgment",
          schemaVersion: "article-judgment/1",
          mediaType: "application/json",
          origin: "model" as const,
          payload: { kind: "json" as const, value: { retry: "success" } },
        }],
      }));
    }, { retry: { maxAttempts: 2, retryOn: "always" } }));
    assert.equal(executions, 2);
    const inspection = loops.inspectRun(runId)!;
    const call = inspection.calls.find((candidate) => candidate.key === "durable-attempt");
    assert.ok(call);
    const attempts = inspection.attempts.filter((attempt) => attempt.callId === call.callId);
    assert.deepEqual(attempts.map((attempt) => attempt.status), ["failed", "completed"]);
    assert.equal(attempts[1]?.attemptNumber, 2);
    const selected = f.ledger.listArtifacts(runId).filter((artifact) => artifact.kind === "article_judgment");
    assert.equal(selected.length, 1);
    assert.equal(selected[0]?.metadata.attemptId, attempts[1]?.attemptId);
    const selectedContext = selected[0]?.durableContext;
    assert.ok(selectedContext !== undefined && "callId" in selectedContext && "attemptId" in selectedContext);
    assert.equal(selectedContext.callId, call.callId);
    assert.equal(selectedContext.attemptId, attempts[1]?.attemptId);
  } finally {
    loops.close();
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("stable article identity ignores the root Loops run", () => {
  const input = { editionId: "004", articleId: "article-one", language: "en", revisionId: "revision-one" };
  assert.equal(articleExecutionIdFor(input), articleExecutionIdFor({ ...input }));
});

test("revision registration binds one immutable revision to one manuscript artifact", async () => {
  const f = await fixture();
  try {
    const other = "manuscript-same-revision" as ArtifactId;
    f.ledger.createArtifact({
      id: other,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "# other" },
      metadata: { articleId: "article-one", revisionId: "revision-one" },
    });
    await inAttempt(f, "register-original", () => f.runner.claimModel(f.aware, request("source_aware", "register-original")));
    await assert.rejects(
      inAttempt(f, "other-manuscript", () => f.runner.claimModel(f.aware, request("source_aware", "other-manuscript", other))),
      (error: unknown) => hasErrorCode(error, "ATTEMPT_REVISION_CONFLICT"),
    );
    const sameAccess = await inAttempt(f, "same-access", () => f.runner.claimModel(f.aware, request("source_aware", "same-access")));
    assert.equal(sameAccess.manuscriptRevisionId, "revision-one");
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("attempts reject a manuscript that has no registered immutable revision", async () => {
  const f = await fixture();
  try {
    const missing = "manuscript-no-revision" as ArtifactId;
    f.ledger.createArtifact({
      id: missing,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "text", text: "# missing" },
      metadata: { articleId: "article-one" },
    });
    await assert.rejects(
      inAttempt(f, "missing-revision", () => f.runner.claimModel(f.aware, request("source_aware", "missing-revision", missing))),
      (error: unknown) => hasErrorCode(error, "ATTEMPT_REVISION_REQUIRED"),
    );
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("replays and losers return a discriminated no-value result without running work", async () => {
  const f = await fixture();
  try {
    const first = await inAttempt(f, "selected", () => f.runner.executeModel(f.aware, request("source_aware", "selected"), async () => ({ value: "winner" })));
    assert.equal(first.selected, true);
    let replayRan = false;
    const replay = await inAttempt(f, "selected", () => f.runner.executeModel(f.aware, request("source_aware", "selected"), async () => {
      replayRan = true;
      return { value: "replay" };
    }));
    assert.equal(replay.selected, false);
    assert.equal("value" in replay, false);
    assert.equal(replayRan, false);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("article exposure migration rebuilds a legacy nullable-key table safely", async () => {
  const f = await fixture();
  const databasePath = join(f.root, "magazine.sqlite");
  try {
    await inAttempt(f, "legacy-exposure", () => f.runner.claimModel(f.aware, request("source_aware", "legacy-exposure")));
    f.ledger.close();
    const legacy = new Database(databasePath);
    legacy.exec("ALTER TABLE magazine_article_exposures RENAME TO magazine_article_exposures_previous");
    legacy.exec(`
      CREATE TABLE magazine_article_exposures (
        principal_id TEXT NOT NULL,
        manuscript_artifact_id TEXT NOT NULL,
        access TEXT NOT NULL,
        first_claim_id TEXT NOT NULL,
        exposed_at TEXT NOT NULL,
        PRIMARY KEY (principal_id, manuscript_artifact_id)
      );
      INSERT INTO magazine_article_exposures(
        principal_id, manuscript_artifact_id, access, first_claim_id, exposed_at
      )
      SELECT principal_id, manuscript_artifact_id, access, first_claim_id, exposed_at
      FROM magazine_article_exposures_previous;
      DROP TABLE magazine_article_exposures_previous;
    `);
    legacy.close();
    const migrated = new ArtifactLedger(databasePath);
    try {
      const inspected = new Database(databasePath);
      const columns = inspected.prepare("PRAGMA table_info(magazine_article_exposures)").all() as readonly { readonly name: string; readonly notnull: number; readonly pk: number }[];
      inspected.close();
      const revision = columns.find((column) => column.name === "manuscript_revision_id");
      assert.equal(revision?.notnull, 1);
      assert.equal(revision?.pk, 2);
      const next = migrated.createArticleAttemptRunner();
      await assert.rejects(
        inAttempt(f, "legacy-migrated-conflict", () => next.claimModel(f.aware, request("source_blind", "legacy-migrated-conflict"))),
        (error: unknown) => hasErrorCode(error, "ATTEMPT_EXPOSURE_CONFLICT"),
      );
    } finally {
      migrated.close();
    }
  } finally {
    // f.ledger was closed before the legacy rewrite.
    await rm(f.root, { recursive: true, force: true });
  }
});

test("article exposure migration rejects an unbackfillable legacy row", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-article-attempt-migration-invalid-"));
  const databasePath = join(root, "magazine.sqlite");
  const ledger = new ArtifactLedger(databasePath);
  ledger.close();
  const legacy = new Database(databasePath);
  legacy.exec("ALTER TABLE magazine_article_exposures RENAME TO magazine_article_exposures_previous");
  legacy.exec(`
    CREATE TABLE magazine_article_exposures (
      principal_id TEXT NOT NULL,
      manuscript_artifact_id TEXT NOT NULL,
      access TEXT NOT NULL,
      first_claim_id TEXT NOT NULL,
      exposed_at TEXT NOT NULL,
      PRIMARY KEY (principal_id, manuscript_artifact_id)
    );
    INSERT INTO magazine_article_exposures(
      principal_id, manuscript_artifact_id, access, first_claim_id, exposed_at
    ) VALUES ('principal', 'missing-manuscript', 'source_aware', 'missing-claim', '2026-08-03T00:00:00.000Z');
    DROP TABLE magazine_article_exposures_previous;
  `);
  legacy.close();
  try {
    assert.throws(
      () => new ArtifactLedger(databasePath),
      (error: unknown) => error instanceof ArtifactLedgerError && error.code === "SCHEMA_MIGRATION_UNBACKFILLABLE",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("independent SQLite connections preserve exposure isolation and one selection", async () => {
  const f = await fixture();
  const second = new ArtifactLedger(join(f.root, "magazine.sqlite"), { clock: f.clock, articleAttemptLeaseMs: 1_000 });
  const secondRunner = second.createArticleAttemptRunner();
  try {
    await inAttempt(f, "cross-connection-aware", () => f.runner.claimModel(f.aware, request("source_aware", "cross-connection-aware")));
    await assert.rejects(
      inAttempt(f, "cross-connection-blind", () => secondRunner.claimModel(f.aware, request("source_blind", "cross-connection-blind"))),
      (error: unknown) => hasErrorCode(error, "ATTEMPT_EXPOSURE_CONFLICT"),
    );

    const first = await inAttempt(f, "cross-connection-selection", () => f.runner.executeModel(f.blind, request("source_blind", "cross-connection-selection"), async () => ({ value: "first" })));
    const replay = await inAttempt(f, "cross-connection-selection", () => secondRunner.executeModel(f.blind, request("source_blind", "cross-connection-selection"), async () => ({ value: "second" })), 2);
    assert.equal(first.selected, true);
    assert.equal(replay.selected, false);
    assert.equal("value" in replay, false);
  } finally {
    second.close();
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("attempt context is required and wait context cannot claim model work", async () => {
  const f = await fixture();
  try {
    await assert.rejects(
      f.runner.claimModel(f.aware, request("source_aware", "outside-loops")),
      (error: unknown) => hasErrorCode(error, "ATTEMPT_PROVENANCE_REQUIRED"),
    );
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("attempt artifact IDs hash a canonical tuple without delimiter collisions", async () => {
  const f = await fixture();
  try {
    const left = await inAttempt(f, "a-b", () => f.runner.executeModel(f.aware, request("source_aware", "a-b"), async () => ({
      value: true,
      artifacts: [{ key: "c", kind: "article_judgment", schemaVersion: "article-judgment/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { side: "left" } } }],
    })));
    const right = await inAttempt(f, "a", () => f.runner.executeModel(f.aware, request("source_aware", "a"), async () => ({
      value: true,
      artifacts: [{ key: "b-c", kind: "article_judgment", schemaVersion: "article-judgment/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { side: "right" } } }],
    })));
    assert.equal(left.selected, true);
    assert.equal(right.selected, true);
    if (!left.selected || !right.selected) throw new Error("expected selected attempts");
    assert.notEqual(left.artifacts[0]?.id, right.artifacts[0]?.id);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("raw attempt persistence is not exposed on ArtifactLedger", async () => {
  const methods = Object.getOwnPropertyNames(ArtifactLedger.prototype);
  assert.equal(methods.includes("claimArticleAttempt"), false);
  assert.equal(methods.includes("completeArticleAttempt"), false);
  assert.equal(methods.includes("createArticleAttemptArtifact"), false);
  const root = await mkdtemp(join(tmpdir(), "mag-article-attempt-reflection-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  try {
    assert.deepEqual(Object.getOwnPropertySymbols(ledger), []);
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});
