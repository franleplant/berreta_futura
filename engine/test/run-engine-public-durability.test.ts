import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test, type TestContext } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactPayload,
  ArticleRootRunSpec,
  RunView,
  WorkerIdentity,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  RunEngineError,
  SqliteRunEngine,
  type FailpointContext,
  type FailpointController,
  type RunEngineClock,
  type RunEngineFailpoint,
} from "../run-engine/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

class ManualClock implements RunEngineClock {
  private milliseconds = Date.UTC(2026, 0, 1);

  now(): Date {
    return new Date(this.milliseconds);
  }

  advance(milliseconds: number): void {
    this.milliseconds += milliseconds;
  }
}

class InjectedCrash extends Error {
  readonly point: RunEngineFailpoint;

  constructor(point: RunEngineFailpoint) {
    super(`Injected crash at ${point}`);
    this.point = point;
  }
}

class ThrowOnce implements FailpointController {
  private thrown = false;
  readonly point: RunEngineFailpoint;
  readonly failure: "crash" | "retryable";

  constructor(
    point: RunEngineFailpoint,
    failure: "crash" | "retryable" = "crash",
  ) {
    this.point = point;
    this.failure = failure;
  }

  hit(name: RunEngineFailpoint, _context?: FailpointContext): void {
    if (name !== this.point || this.thrown) {
      return;
    }
    this.thrown = true;
    if (this.failure === "retryable") {
      throw new RunEngineError(
        "SIMULATED_OUTBOX_FAILURE",
        `Retryable dispatch failure at ${name}`,
      );
    }
    throw new InjectedCrash(name);
  }
}

type Harness = {
  readonly root: string;
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly clock: ManualClock;
  open(options?: {
    readonly failpoints?: FailpointController;
    readonly coordinatorLeaseMs?: number;
    readonly artifactWriteLeaseMs?: number;
  }): SqliteRunEngine;
};

async function harness(context: TestContext): Promise<Harness> {
  const root = await mkdtemp(join(tmpdir(), "mag-public-durability-"));
  const engines: SqliteRunEngine[] = [];
  const clock = new ManualClock();
  context.after(async () => {
    for (const engine of engines) {
      engine.close();
    }
    await rm(root, { recursive: true, force: true });
  });
  return {
    root,
    databasePath: join(root, "runs.sqlite"),
    artifactDirectory: join(root, "artifacts"),
    clock,
    open(options = {}) {
      const engine = new SqliteRunEngine({
        databasePath: join(root, "runs.sqlite"),
        artifactDirectory: join(root, "artifacts"),
        clock,
        ...options,
      });
      engines.push(engine);
      return engine;
    },
  };
}

function articleSpec(
  prefix: string,
  manuscriptPayload: ArtifactPayload = {
    kind: "text",
    text: `Initial manuscript for ${prefix}`,
  },
): ArticleRootRunSpec {
  const brief = artifactId(`${prefix}-brief`);
  const writerPrompt = artifactId(`${prefix}-writer-prompt`);
  const worthPrompt = artifactId(`${prefix}-worth-prompt`);
  const evidencePrompt = artifactId(`${prefix}-evidence-prompt`);
  const rules = artifactId(`${prefix}-rules`);
  const manuscript = artifactId(`${prefix}-manuscript`);
  const source = artifactId(`${prefix}-source`);
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      textSeed(brief, "article_brief"),
      textSeed(writerPrompt, "writer_prompt"),
      textSeed(worthPrompt, "judge_prompt"),
      textSeed(evidencePrompt, "judge_prompt"),
      textSeed(rules, "writing_rules"),
      textSeed(source, "source_extraction"),
      {
        id: manuscript,
        kind: "article_manuscript",
        schemaVersion: "test/1",
        mediaType: "text/plain",
        origin: "imported",
        payload: manuscriptPayload,
      },
    ],
    article: {
      articleId: `${prefix}-article`,
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine editors" },
      articleBrief: brief,
      sources: [source],
      sourceApprovalArtifacts: [],
      writerPrompt,
      judgePrompts: { worth: worthPrompt, evidence: evidencePrompt },
      writingRules: rules,
      initialManuscript: manuscript,
      policy: {
        maxIterations: 2,
        maximumReaderPages: 7,
        teaching: "not_applicable",
        enabledLenses: ["worth", "evidence"],
        blockingLenses: ["worth"],
      },
      modelPolicy: { default: { adapter: "test", model: "deterministic" } },
    },
  };
}

async function preparedArticleSpec(
  fixture: Harness,
  prefix: string,
  manuscriptPayload?: ArtifactPayload,
): Promise<ArticleRootRunSpec> {
  const preparationEngine = fixture.open();
  try {
    return await prepareArticleSources(
      preparationEngine,
      articleSpec(prefix, manuscriptPayload),
      `${prefix}-source-prep`,
    );
  } finally {
    preparationEngine.close();
  }
}

function textSeed(id: ArtifactId, kind: string) {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported" as const,
    payload: { kind: "text" as const, text: `Input ${id}` },
  };
}

function offered(view: RunView, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(offer, `Expected an offered ${role} task`);
  return offer;
}

function workerFor(offer: WorkOfferView): WorkerIdentity {
  return {
    principalId: `worker-${offer.id}`,
    authority: "tool",
    capabilities: offer.allowedWorkerCapabilities,
  };
}

function measurement(id: ArtifactId): AnswerArtifact {
  return {
    id,
    kind: "article_measurement",
    schemaVersion: "measurement/1",
    mediaType: "application/json",
    payload: { kind: "json", value: { fits: true, pageCount: 1 } },
  };
}

test("a post-commit start retry resolves the original run identity", async (context) => {
  const fixture = await harness(context);
  const spec = await preparedArticleSpec(fixture, "idempotent-start");
  const engine = fixture.open({ failpoints: new ThrowOnce("start.after_commit") });

  await assert.rejects(
    engine.start(spec, { idempotencyKey: "import-batch-4" }),
    InjectedCrash,
  );
  const recovered = await engine.start(spec, { idempotencyKey: "import-batch-4" });
  const repeated = await engine.start(spec, { idempotencyKey: "import-batch-4" });

  assert.equal(recovered.runId, repeated.runId);
  const view = await engine.inspect(recovered.runId);
  assert.equal(view.events.filter((event) => event.type === "@@engine/initialized").length, 1);
  assert.equal(view.events.filter((event) => event.type === "START").length, 1);

  await assert.rejects(
    engine.start(await preparedArticleSpec(fixture, "different-start"), { idempotencyKey: "import-batch-4" }),
    (error: unknown) =>
      error instanceof RunEngineError && error.code === "START_IDEMPOTENCY_CONFLICT",
  );

  const independentSpec = await preparedArticleSpec(fixture, "independent-equal-spec");
  const firstIndependent = await engine.start(independentSpec);
  const secondIndependent = await engine.start(independentSpec);
  assert.notEqual(firstIndependent.runId, secondIndependent.runId);
});

test("committed outbox work is recovered once after a transition crash", async (context) => {
  const fixture = await harness(context);
  const spec = await preparedArticleSpec(fixture, "committed-outbox");
  const engine = fixture.open({ failpoints: new ThrowOnce("advance.after_commit") });

  await assert.rejects(engine.start(spec, { idempotencyKey: "committed-outbox" }), InjectedCrash);
  const recovered = await engine.start(spec, { idempotencyKey: "committed-outbox" });
  assert.equal(recovered.status, "waiting");
  const view = await engine.inspect(recovered.runId);
  assert.equal(view.offers.filter((offer) => offer.role === "measure_article").length, 1);
  assert.equal(view.events.filter((event) => event.type === "START").length, 1);
});

test("an advance crash after pure effects leaves no phantom transition", async (context) => {
  const fixture = await harness(context);
  const spec = await preparedArticleSpec(fixture, "effects-before-commit");
  const engine = fixture.open({ failpoints: new ThrowOnce("advance.after_effects") });

  await assert.rejects(
    engine.start(spec, { idempotencyKey: "effects-before-commit" }),
    InjectedCrash,
  );
  const recovered = await engine.start(spec, { idempotencyKey: "effects-before-commit" });
  assert.equal(recovered.status, "waiting");
  const view = await engine.inspect(recovered.runId);
  assert.equal(view.events.filter((event) => event.type === "START").length, 1);
  assert.equal(view.offers.filter((offer) => offer.role === "measure_article").length, 1);
});

test("an outbox crash after effect commit recovers without duplicating the offer", async (context) => {
  const fixture = await harness(context);
  const engine = fixture.open({ failpoints: new ThrowOnce("outbox.after_effect_commit") });
  const spec = await preparedArticleSpec(fixture, "outbox-effect-commit");
  await assert.rejects(
    engine.start(spec, { idempotencyKey: "outbox-effect-commit" }),
    InjectedCrash,
  );
  const recovered = await engine.start(
    spec,
    { idempotencyKey: "outbox-effect-commit" },
  );
  const view = await engine.inspect(recovered.runId);
  assert.equal(view.offers.filter((offer) => offer.role === "measure_article").length, 1);
  assert.equal(view.offers.find((offer) => offer.role === "measure_article")?.status, "offered");
});

test("an expired outbox claim is fenced and reclaimed", async (context) => {
  const fixture = await harness(context);
  const spec = await preparedArticleSpec(fixture, "claimed-outbox");
  const engine = fixture.open({
    coordinatorLeaseMs: 50,
    failpoints: new ThrowOnce("outbox.after_claim"),
  });

  await assert.rejects(engine.start(spec, { idempotencyKey: "claimed-outbox" }), InjectedCrash);
  const blocked = await engine.start(spec, { idempotencyKey: "claimed-outbox" });
  assert.equal(blocked.status, "running");
  fixture.clock.advance(51);
  const recovered = await engine.start(spec, { idempotencyKey: "claimed-outbox" });
  assert.equal(recovered.status, "waiting");
  const view = await engine.inspect(recovered.runId);
  assert.equal(view.offers.filter((offer) => offer.role === "measure_article").length, 1);
});

test("a failed outbox dispatch retries from its committed record", async (context) => {
  const fixture = await harness(context);
  const spec = await preparedArticleSpec(fixture, "retry-outbox");
  const engine = fixture.open({
    failpoints: new ThrowOnce("outbox.before_effect_commit", "retryable"),
  });

  await assert.rejects(
    engine.start(spec, { idempotencyKey: "retry-outbox" }),
    (error: unknown) =>
      error instanceof RunEngineError && error.code === "SIMULATED_OUTBOX_FAILURE",
  );
  const beforeRetry = await engine.start(spec, { idempotencyKey: "retry-outbox" });
  assert.equal(beforeRetry.status, "running");
  fixture.clock.advance(101);
  const recovered = await engine.start(spec, { idempotencyKey: "retry-outbox" });
  assert.equal(recovered.status, "waiting");
  const view = await engine.inspect(recovered.runId);
  assert.equal(view.offers.filter((offer) => offer.role === "measure_article").length, 1);
});

test("orphan collection respects live write fences and preserves committed files", async (context) => {
  const fixture = await harness(context);
  const sourcePath = join(fixture.root, "manuscript.md");
  await writeFile(sourcePath, "A durable file manuscript", "utf8");
  const spec = await preparedArticleSpec(fixture, "orphan-file", { kind: "file", path: sourcePath });
  const manuscriptId = spec.article.initialManuscript;
  assert.ok(manuscriptId);
  const engine = fixture.open({
    artifactWriteLeaseMs: 50,
    failpoints: new ThrowOnce("start.after_artifact_rename"),
  });

  await assert.rejects(engine.start(spec), InjectedCrash);
  assert.deepEqual(await engine.collectOrphanedArtifacts(), []);
  fixture.clock.advance(51);
  assert.deepEqual(await engine.collectOrphanedArtifacts(), [manuscriptId]);

  const recovered = await engine.start(spec);
  assert.equal(recovered.status, "waiting");
  assert.deepEqual(await engine.collectOrphanedArtifacts(), []);
  assert.equal(await engine.readText(manuscriptId), "A durable file manuscript");
});

test("a blocking artifact-free judge answer remains immutable writer feedback", async (context) => {
  const fixture = await harness(context);
  const engine = fixture.open();
  const started = await engine.start(await preparedArticleSpec(fixture, "answer-envelope-feedback"));
  const beforeMeasure = await engine.inspect(started.runId);
  const measureOffer = offered(beforeMeasure, "measure_article");
  const measureClaim = await engine.claim(measureOffer.id, workerFor(measureOffer));
  const afterMeasure = await engine.answer(measureClaim, {
    contractVersion: measureOffer.contractVersion,
    result: { fits: true, pageCount: 1 },
    artifacts: [measurement(artifactId("answer-envelope-measurement"))],
  });
  const worthOffer = offered(afterMeasure, "worth");
  const worthClaim = await engine.claim(worthOffer.id, workerFor(worthOffer));
  const finding = "The central claim has no supporting example.";
  const afterWorth = await engine.answer(worthClaim, {
    contractVersion: worthOffer.contractVersion,
    result: {
      status: "blocking",
      blocking: true,
      findings: [{ message: finding }],
    },
    artifacts: [],
  });

  const answerEnvelope = afterWorth.artifacts.find(
    (artifact) =>
      artifact.kind === "work_answer" && artifact.producingOfferId === worthOffer.id,
  );
  assert.ok(answerEnvelope);
  const revisionWriter = offered(afterWorth, "writer");
  assert.ok(revisionWriter.inputArtifacts.includes(answerEnvelope.id));
  const payload = JSON.parse(await engine.readText(answerEnvelope.id)) as {
    readonly result?: { readonly findings?: readonly { readonly message?: string }[] };
  };
  assert.equal(payload.result?.findings?.[0]?.message, finding);
});
