import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  RunId,
  WorkAnswer,
  WorkClaim,
  WorkOfferView,
} from "../contracts/index.ts";
import { KNOWN_WORK_ROLES } from "../contracts/index.ts";
import {
  ArticleMeasurementExecutor,
  ConfiguredExecutorResolver,
  ImageModelExecutor,
  InMemoryExecutor,
  LanguageFitExecutor,
  RenderInspectionExecutor,
  RendererExecutor,
  SourceArchiveExecutor,
  TextModelExecutor,
  WORK_ROLE_EXECUTION,
  executeAvailableWork,
  type Executor,
  type WorkEngine,
} from "../executors/index.ts";
import type { RendererAdapter } from "../renderer-adapter/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import type { SourceAdapter } from "../source-adapter/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(
  artifactId: ArtifactId,
  kind: string,
  text: string = artifactId,
): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "fixture/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text },
  };
}

function articleSpec(prefix: string): ArticleRootRunSpec {
  const brief = id(`${prefix}-brief`);
  const writer = id(`${prefix}-writer`);
  const worth = id(`${prefix}-worth`);
  const evidence = id(`${prefix}-evidence`);
  const source = id(`${prefix}-source`);
  const rules = id(`${prefix}-rules`);
  const manuscript = id(`${prefix}-manuscript`);
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      seed(brief, "article_brief"),
      seed(writer, "writer_prompt"),
      seed(worth, "judge_prompt"),
      seed(evidence, "judge_prompt"),
      seed(source, "source_extraction"),
      seed(rules, "writing_rules"),
      seed(manuscript, "article_manuscript", "# Fixture\n\nA measured article."),
    ],
    article: {
      articleId: `${prefix}-article`,
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine" },
      articleBrief: brief,
      sources: [source],
      sourceApprovalArtifacts: [],
      writerPrompt: writer,
      judgePrompts: { worth, evidence },
      writingRules: rules,
      initialManuscript: manuscript,
      policy: {
        maxIterations: 2,
        maximumReaderPages: 7,
        teaching: "not_applicable",
        enabledLenses: ["worth", "evidence"],
        blockingLenses: ["worth", "evidence"],
      },
      modelPolicy: {
        default: { adapter: "fixture-model", model: "fixture-1" },
        roles: { worth: { adapter: "fixture-model", model: "fixture-worth" } },
      },
    },
  };
}

function measurementAnswer(offer: WorkOfferView, marker = "measurement"): WorkAnswer {
  const artifact: AnswerArtifact = {
    kind: "article_measurement",
    schemaVersion: offer.contractVersion,
    mediaType: "application/json",
    payload: {
      kind: "json",
      value: { fits: true, pageCount: 1, openerFits: true, marker },
    },
  };
  return {
    contractVersion: offer.contractVersion,
    result: { fits: true, pageCount: 1, openerFits: true, status: "pass" },
    artifacts: [artifact],
  };
}

function measurementExecutor(
  name: string,
  handler: (offer: WorkOfferView) => Promise<WorkAnswer>,
): InMemoryExecutor {
  return new InMemoryExecutor(
    name,
    {
      principalId: name,
      authority: "tool",
      capabilities: ["subprocess"],
    },
    async ({ offer }) => await handler(offer),
    (offer) => offer.role === "measure_article",
  );
}

async function withEngine(
  prefix: string,
  workLeaseMs: number,
  implementation: (engine: SqliteRunEngine, runId: RunId) => Promise<void>,
): Promise<void> {
  const temporary = await mkdtemp(join(tmpdir(), `${prefix}-`));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
    workLeaseMs,
  });
  try {
    const started = await engine.start(await prepareArticleSources(engine, articleSpec(prefix), prefix));
    await implementation(engine, started.runId);
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
}

test("worker heartbeats keep a long public claim alive", async () => {
  await withEngine("worker-heartbeat", 500, async (engine, runId) => {
    let heartbeatCount = 0;
    const observed: WorkEngine = {
      inspect: async (candidate) => await engine.inspect(candidate),
      claim: async (offerId, worker) => await engine.claim(offerId, worker),
      heartbeat: async (claim) => {
        heartbeatCount += 1;
        return await engine.heartbeat(claim);
      },
      answer: async (claim, answer) => await engine.answer(claim, answer),
      fail: async (claim, failure) => await engine.fail(claim, failure),
      readArtifact: async (artifactId) => await engine.readArtifact(artifactId),
      readBytes: async (artifactId) => await engine.readBytes(artifactId),
      readText: async (artifactId) => await engine.readText(artifactId),
    };
    const executor = measurementExecutor("slow-measurement", async (offer) => {
      await delay(1_200);
      return measurementAnswer(offer);
    });
    const result = await executeAvailableWork(
      observed,
      runId,
      [executor],
      new AbortController().signal,
      { heartbeatIntervalMs: 50, attemptTimeoutMs: 5_000 },
    );
    const completedView = await engine.inspect(runId);
    assert.equal(
      result.answered.length,
      1,
      JSON.stringify({
        result,
        attempts: completedView.attempts.map((attempt) => ({
          id: attempt.id,
          offerId: attempt.offerId,
          status: attempt.status,
          leaseExpiresAt: attempt.leaseExpiresAt,
        })),
      }),
    );
    assert.equal(result.failed.length, 0);
    assert.ok(heartbeatCount >= 3, `expected repeated heartbeats, got ${heartbeatCount}`);
    const view = completedView;
    assert.equal(
      view.attempts.find((attempt) => attempt.offerId === result.answered[0])?.status,
      "answered",
    );
  });
});

test("worker timeout fences ignored late completion and permits durable retry", async () => {
  await withEngine("worker-timeout", 1_000, async (engine, runId) => {
    const slow = measurementExecutor("ignores-abort", async (offer) => {
      await delay(70);
      return measurementAnswer(offer, "too-late");
    });
    const timedOut = await executeAvailableWork(
      engine,
      runId,
      [slow],
      new AbortController().signal,
      { heartbeatIntervalMs: 5, attemptTimeoutMs: 10 },
    );
    assert.equal(timedOut.failed.length, 1, JSON.stringify(timedOut));
    await delay(90);
    let view = await engine.inspect(runId);
    assert.equal(
      view.artifacts.some((artifact) => artifact.kind === "article_measurement"),
      false,
    );
    assert.equal(view.actors[0]?.state, "stage_1");
    const replacement = measurementExecutor(
      "replacement-measurement",
      async (offer) => measurementAnswer(offer, "replacement"),
    );
    const retried = await executeAvailableWork(
      engine,
      runId,
      [replacement],
      new AbortController().signal,
      { heartbeatIntervalMs: 5, attemptTimeoutMs: 100 },
    );
    assert.equal(retried.answered.length, 1, JSON.stringify(retried));
    view = await engine.inspect(runId);
    assert.equal(view.attempts.some((attempt) => attempt.status === "timed_out"), true);
    assert.equal(view.attempts.some((attempt) => attempt.status === "answered"), true);
  });
});

test("caller cancellation reaches the executor and commits a canceled attempt", async () => {
  await withEngine("worker-cancel", 1_000, async (engine, runId) => {
    let observedAbort = false;
    const executor = new InMemoryExecutor(
      "cancel-aware",
      {
        principalId: "cancel-aware",
        authority: "tool",
        capabilities: ["subprocess"],
      },
      async ({ signal }) => await new Promise<WorkAnswer>((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          observedAbort = true;
          reject(signal.reason);
        }, { once: true });
      }),
      (offer) => offer.role === "measure_article",
    );
    const controller = new AbortController();
    setTimeout(() => controller.abort(), 10);
    const result = await executeAvailableWork(
      engine,
      runId,
      [executor],
      controller.signal,
      { heartbeatIntervalMs: 5, attemptTimeoutMs: 500 },
    );
    assert.equal(observedAbort, true);
    assert.equal(result.failed.length, 1, JSON.stringify(result));
    const view = await engine.inspect(runId);
    const attempt = view.attempts.find((candidate) =>
      candidate.offerId === result.failed[0]
    );
    assert.equal(attempt?.status, "failed");
  });
});

test("an expired worker claim is reclaimed and the old answer stays fenced", async () => {
  await withEngine("worker-death", 15, async (engine, runId) => {
    const initial = await engine.inspect(runId);
    const offer = initial.offers.find((candidate) => candidate.role === "measure_article");
    assert.ok(offer);
    const oldClaim = await engine.claim(offer.id, {
      principalId: "dead-worker",
      authority: "tool",
      capabilities: ["subprocess"],
    });
    await delay(35);
    const replacement = measurementExecutor(
      "after-death",
      async (candidate) => measurementAnswer(candidate, "new-worker"),
    );
    const result = await executeAvailableWork(
      engine,
      runId,
      [replacement],
      new AbortController().signal,
      { heartbeatIntervalMs: 5, attemptTimeoutMs: 100 },
    );
    assert.equal(result.answered.length, 1, JSON.stringify(result));
    const afterLate = await engine.answer(oldClaim, measurementAnswer(offer, "old-worker"));
    assert.equal(
      afterLate.attempts.find((attempt) => attempt.id === oldClaim.attemptId)?.status,
      "timed_out",
    );
    assert.equal(
      afterLate.artifacts.some((artifact) => artifact.producingAttemptId === oldClaim.attemptId),
      true,
      "the superseded submission should remain auditable",
    );
    assert.equal(
      afterLate.actors[0]?.context.manuscriptArtifact,
      initial.actors[0]?.context.manuscriptArtifact,
    );
  });
});

test("configured resolver follows frozen per-role model policy and rejects ambiguity", async () => {
  await withEngine("worker-policy", 1_000, async (engine, runId) => {
    const view = await engine.inspect(runId);
    const worth = view.offers.find((offer) => offer.role === "worth");
    assert.ok(worth);
    const model = new InMemoryExecutor(
      "worth-model",
      {
        principalId: "worth-model",
        authority: "model",
        capabilities: ["text_model", "source_access"],
      },
      async () => ({ contractVersion: worth.contractVersion, result: { decision: "pass" }, artifacts: [] }),
      (offer) => offer.role === "worth",
    );
    const registration = {
      executor: model,
      adapter: "fixture-model",
      model: "fixture-worth",
      roles: ["worth"],
    } as const;
    const resolver = new ConfiguredExecutorResolver([registration]);
    const selected = resolver.resolve(view, worth);
    assert.ok(selected);
    assert.match(selected.worker.principalId, new RegExp(`${worth.id}$`));
    assert.throws(
      () => new ConfiguredExecutorResolver([registration, registration]).resolve(view, worth),
      /multiple configured executors/,
    );
  });
});

test("every declared work role has one intentional execution owner", () => {
  assert.deepEqual(Object.keys(WORK_ROLE_EXECUTION).sort(), [...KNOWN_WORK_ROLES].sort());
  const rendererAdapter: RendererAdapter = {
    render: async () => {
      throw new Error("not executed by inventory test");
    },
  };
  const sourceAdapter: SourceAdapter = {
    archive: async () => {
      throw new Error("not executed by inventory test");
    },
  };
  const modelWorker = {
    principalId: "inventory-model",
    authority: "model" as const,
    capabilities: ["text_model", "source_access", "source_blind"] as const,
  };
  const imageWorker = {
    principalId: "inventory-image",
    authority: "model" as const,
    capabilities: ["image_model"] as const,
  };
  const executors: readonly Executor[] = [
    new SourceArchiveExecutor(sourceAdapter, { workDirectory: tmpdir() }),
    new TextModelExecutor("inventory-text", modelWorker, () => inventoryCommand()),
    new ImageModelExecutor("inventory-image", imageWorker, () => inventoryCommand()),
    new ArticleMeasurementExecutor(rendererAdapter, { workDirectory: tmpdir() }),
    new LanguageFitExecutor(rendererAdapter, { workDirectory: tmpdir() }),
    new RendererExecutor(rendererAdapter, { workDirectory: tmpdir() }),
    new RenderInspectionExecutor(),
  ];
  for (const role of KNOWN_WORK_ROLES) {
    const owner = WORK_ROLE_EXECUTION[role];
    if (owner === "human") {
      continue;
    }
    const offer = inventoryOffer(role, owner);
    assert.equal(
      executors.some((executor) => executor.accepts(offer)),
      true,
      `${role} has no executor accepting its declared ${owner} ownership`,
    );
  }
  assert.deepEqual(
    [...new Set(Object.values(WORK_ROLE_EXECUTION))]
      .filter((owner) => owner === "text_model" || owner === "image_model")
      .sort(),
    ["image_model", "text_model"],
    "model calls are the only intentionally external command adapters",
  );
});

function inventoryOffer(
  role: (typeof KNOWN_WORK_ROLES)[number],
  owner: (typeof WORK_ROLE_EXECUTION)[(typeof KNOWN_WORK_ROLES)[number]],
): WorkOfferView {
  const capability = owner === "text_model"
    ? "text_model"
    : owner === "image_model"
      ? "image_model"
      : owner === "source_archive"
        ? "source_access"
        : "subprocess";
  return {
    id: `offer-${role}` as WorkOfferView["id"],
    runId: "run-inventory" as RunId,
    actorId: `actor-${role}` as WorkOfferView["actorId"],
    actorKey: role,
    state: "offered",
    stateVisitId: `visit-${role}` as WorkOfferView["stateVisitId"],
    role,
    slot: role,
    inputArtifacts: [],
    taskArtifactId: id(`task-${role}`),
    contractVersion: "inventory/1",
    allowedWorkerCapabilities: [capability],
    status: "offered",
    createdAt: new Date(0).toISOString(),
  };
}

function inventoryCommand() {
  return {
    executable: "true",
    args: [],
    cwd: tmpdir(),
    timeoutMs: 1_000,
    stdin: "",
  };
}

async function delay(milliseconds: number): Promise<void> {
  await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}
