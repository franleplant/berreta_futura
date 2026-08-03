import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, test, type TestContext } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactPayload,
  ArtifactSeed,
  ArticleRootRunSpec,
  JudgeLens,
  RunView,
  WorkClaim,
  WorkOfferId,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  createRunEngine,
  MachineVersionError,
  RunEngineError,
  StaleClaimError,
  type FailpointContext,
  type FailpointController,
  type RunEngineClock,
  type RunEngineFailpoint,
  type RunEngineOptions,
  type SqliteRunEngine,
} from "../run-engine/index.ts";
import { corruptStoredMachineVersion } from "./internal-schema-test-helper.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

class ManualClock implements RunEngineClock {
  private milliseconds: number;

  constructor(milliseconds = Date.UTC(2026, 0, 1)) {
    this.milliseconds = milliseconds;
  }

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
    this.name = "InjectedCrash";
    this.point = point;
  }
}

class ThrowOnce implements FailpointController {
  didThrow = false;
  readonly point: RunEngineFailpoint;

  constructor(point: RunEngineFailpoint) {
    this.point = point;
  }

  hit(name: RunEngineFailpoint, _context?: FailpointContext): void {
    if (name === this.point && !this.didThrow) {
      this.didThrow = true;
      throw new InjectedCrash(name);
    }
  }
}

type Harness = {
  readonly root: string;
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly clock: ManualClock;
  readonly authority: AuthorityTestHarness;
  open(options?: Omit<RunEngineOptions, "artifactDirectory" | "clock" | "databasePath">): SqliteRunEngine;
};

async function harness(testContext: TestContext): Promise<Harness> {
  const root = await mkdtemp(join(tmpdir(), "mag-run-engine-test-"));
  const databasePath = join(root, "run.sqlite3");
  const artifactDirectory = join(root, "owned-artifacts");
  const clock = new ManualClock();
  const authority = await AuthorityTestHarness.create(root);
  const engines: SqliteRunEngine[] = [];
  testContext.after(async () => {
    for (const engine of engines) {
      engine.close();
    }
    await rm(root, { recursive: true, force: true });
  });
  return {
    root,
    databasePath,
    artifactDirectory,
    clock,
    authority,
    open: (options = {}) => {
      const engine = createRunEngine({
        databasePath,
        artifactDirectory,
        clock,
        ...options,
      });
      engines.push(engine);
      return engine;
    },
  };
}

function seed(
  id: ArtifactId,
  kind: string,
  text: string = id,
): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text },
  };
}

function measurementArtifact(id: string): AnswerArtifact {
  return {
    id: artifactId(id),
    kind: "article_measurement",
    schemaVersion: "measurement/1",
    mediaType: "application/json",
    payload: { kind: "json", value: { fits: true, pageCount: 1 } },
  };
}

const allLenses: readonly JudgeLens[] = [
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
];

type ArticleFixture = {
  readonly spec: ArticleRootRunSpec;
  readonly manuscriptId: ArtifactId;
  readonly sourceIds: readonly ArtifactId[];
};

function articleFixture(
  prefix: string,
  options: {
    readonly maxIterations?: number;
    readonly sourceText?: string;
  } = {},
): ArticleFixture {
  const articleBrief = artifactId(`${prefix}-brief`);
  const writerPrompt = artifactId(`${prefix}-writer-prompt`);
  const writingRules = artifactId(`${prefix}-writing-rules`);
  const manuscriptId = artifactId(`${prefix}-manuscript`);
  const sourceIds = [
    artifactId(`${prefix}-source-one`),
    artifactId(`${prefix}-source-two`),
  ];
  const judgePrompts = Object.fromEntries(
    allLenses.map((lens) => [lens, artifactId(`${prefix}-${lens}-prompt`)]),
  ) as Record<JudgeLens, ArtifactId>;
  const artifacts: ArtifactSeed[] = [
    seed(articleBrief, "article_brief"),
    seed(writerPrompt, "writer_prompt"),
    seed(writingRules, "writing_rules"),
    seed(manuscriptId, "article_manuscript"),
    ...sourceIds.map((id) => seed(id, "source_extraction", options.sourceText)),
    ...allLenses.map((lens) => seed(judgePrompts[lens], `${lens}_prompt`)),
  ];
  return {
    manuscriptId,
    sourceIds,
    spec: {
      schemaVersion: 1,
      kind: "article",
      artifacts,
      article: {
        articleId: `${prefix}-article`,
        contentMode: "faithful_edit",
        attribution: {
          kind: "source_author",
          byline: "Source Author",
          sourceAuthors: ["Source Author"],
          sourceIds: sourceIds.map((_source, index) => `${prefix}-source-${index}`),
        },
        articleBrief,
        sources: sourceIds,
        sourceApprovalArtifacts: [],
        writerPrompt,
        judgePrompts,
        writingRules,
        initialManuscript: manuscriptId,
        policy: {
          maxIterations: options.maxIterations ?? 2,
          maximumReaderPages: 7,
          teaching: "applicable",
          enabledLenses: allLenses,
          blockingLenses: allLenses,
        },
        modelPolicy: {
          default: { adapter: "test", model: "deterministic" },
        },
      },
    },
  };
}

async function prepareArticleFixture(
  testHarness: Harness,
  fixture: ArticleFixture,
): Promise<ArticleFixture> {
  const preparationEngine = testHarness.open();
  try {
    return {
      ...fixture,
      spec: await prepareArticleSources(
        preparationEngine,
        fixture.spec,
        `${fixture.spec.article.articleId}-source-prep`,
        await testHarness.authority.human("durability-source-reviewer"),
      ),
    };
  } finally {
    preparationEngine.close();
  }
}

function replacePayload(
  fixture: ArticleFixture,
  id: ArtifactId,
  payload: ArtifactPayload,
): ArticleFixture {
  return {
    ...fixture,
    spec: {
      ...fixture.spec,
      artifacts: fixture.spec.artifacts.map((artifact) =>
        artifact.id === id ? { ...artifact, payload } : artifact,
      ),
    },
  };
}

function offered(view: RunView, role: string): WorkOfferView {
  const result = view.offers.find(
    (offer) => offer.role === role && offer.status === "offered",
  );
  assert.ok(result, `expected an offered ${role} task`);
  return result;
}

async function claimOffer(
  testHarness: Harness,
  engine: SqliteRunEngine,
  offer: WorkOfferView,
  principalId = `worker-${offer.role}-${offer.id}`,
): Promise<WorkClaim> {
  return await testHarness.authority.claim(engine, offer, { principalId });
}

async function rejectCode(promise: Promise<unknown>, code: string): Promise<void> {
  await assert.rejects(promise, (error: unknown) => {
    assert.ok(error instanceof RunEngineError);
    assert.equal(error.code, code);
    return true;
  });
}

async function completeArticle(
  testHarness: Harness,
  engine: SqliteRunEngine,
  fixture: ArticleFixture,
): Promise<RunView> {
  const outcome = await engine.start(fixture.spec);
  let view = await engine.inspect(outcome.runId);
  for (let step = 0; step < 20 && view.status !== "complete"; step += 1) {
    const offer = view.offers.find((candidate) => candidate.status === "offered");
    assert.ok(offer, `run stranded in ${view.status}`);
    const claim = await claimOffer(testHarness, engine, offer);
    if (offer.role === "durable_checkpoint") {
      view = await engine.answer(claim, await durableCheckpointAnswer(engine, offer));
      continue;
    }
    view = await engine.answer(claim, {
      contractVersion: offer.contractVersion,
      result:
        offer.role === "measure_article"
          ? { fits: true, pageCount: 1, openerFits: true }
          : { approved: true, decision: "pass" },
      artifacts:
        offer.role === "measure_article"
          ? [measurementArtifact(`complete-${offer.id}`)]
          : [],
    });
  }
  assert.equal(view.status, "complete");
  return view;
}

describe("RunEngine concurrency and leases", () => {
  test("a claim crash after commit remains fenced until its lease expires", async (testContext) => {
    const testHarness = await harness(testContext);
    const crashing = testHarness.open({
      failpoints: new ThrowOnce("claim.after_commit"),
      workLeaseMs: 50,
    });
    const fixture = await prepareArticleFixture(testHarness, articleFixture("claim-after-commit"));
    const started = await crashing.start(fixture.spec);
    const measure = offered(await crashing.inspect(started.runId), "measure_article");
    await assert.rejects(
      claimOffer(testHarness, crashing, measure, "crashed-claimer"),
      InjectedCrash,
    );
    const committed = await crashing.inspect(started.runId);
    assert.equal(committed.offers.find((offer) => offer.id === measure.id)?.status, "claimed");
    testHarness.clock.advance(51);
    const replacement = await claimOffer(testHarness, crashing, measure, "crashed-claimer");
    assert.notEqual(replacement.attemptId, committed.attempts[0]?.id);
  });

  test("two engine instances fence duplicate claims and consume one inbox event once", async (testContext) => {
    const testHarness = await harness(testContext);
    const first = testHarness.open({
      coordinatorId: "coordinator-first",
      workLeaseMs: 1_000,
      failpoints: new ThrowOnce("answer.after_commit"),
    });
    const second = testHarness.open({ coordinatorId: "coordinator-second", workLeaseMs: 1_000 });
    const fixture = await prepareArticleFixture(testHarness, articleFixture("duplicate"));
    const outcome = await first.start(fixture.spec);
    const initial = await first.inspect(outcome.runId);
    const measure = offered(initial, "measure_article");

    const claims = await Promise.allSettled([
      claimOffer(testHarness, first, measure, "measure-worker-one"),
      claimOffer(testHarness, second, measure, "measure-worker-two"),
    ]);
    assert.equal(claims.filter((result) => result.status === "fulfilled").length, 1);
    const rejected = claims.find((result) => result.status === "rejected");
    assert.ok(rejected?.status === "rejected");
    assert.ok(rejected.reason instanceof RunEngineError);
    assert.equal(rejected.reason.code, "WORK_UNAVAILABLE");

    const acceptedClaim = claims.find(
      (result): result is PromiseFulfilledResult<Awaited<ReturnType<typeof first.claim>>> =>
        result.status === "fulfilled",
    );
    assert.ok(acceptedClaim);
    await assert.rejects(
      first.answer(acceptedClaim.value, {
        contractVersion: measure.contractVersion,
        result: { fits: true, pageCount: 1 },
        artifacts: [measurementArtifact("duplicate-advance-measurement")],
      }),
      InjectedCrash,
    );
    await Promise.all([first.advance(outcome.runId), second.advance(outcome.runId)]);

    const after = await first.inspect(outcome.runId);
    assert.equal(after.events.filter((event) => event.type === "WORK_COMPLETED").length, 1);
  });

  test("a live outbox dispatch fence blocks another engine until expiry", async (testContext) => {
    const testHarness = await harness(testContext);
    const owner = testHarness.open({
      coordinatorId: "lease-owner",
      coordinatorLeaseMs: 500,
      failpoints: new ThrowOnce("outbox.after_claim"),
    });
    const contender = testHarness.open({
      coordinatorId: "lease-contender",
      coordinatorLeaseMs: 500,
    });
    const spec = (await prepareArticleFixture(testHarness, articleFixture("coordinator-lease"))).spec;
    await assert.rejects(owner.start(spec, { idempotencyKey: "lease-reclaim" }), InjectedCrash);

    const beforeExpiry = await contender.start(spec, { idempotencyKey: "lease-reclaim" });
    assert.equal(beforeExpiry.status, "running");

    testHarness.clock.advance(501);
    const afterExpiry = await contender.start(spec, { idempotencyKey: "lease-reclaim" });
    assert.equal(afterExpiry.runId, beforeExpiry.runId);
    assert.equal(afterExpiry.status, "waiting");
  });

  test("an expired claim is reclaimable and its late answer is retained as stale", async (testContext) => {
    const testHarness = await harness(testContext);
    const first = testHarness.open({ coordinatorId: "late-first", workLeaseMs: 1_000 });
    const second = testHarness.open({ coordinatorId: "late-second", workLeaseMs: 1_000 });
    const fixture = await prepareArticleFixture(testHarness, articleFixture("late-answer"));
    const outcome = await first.start(fixture.spec);
    const measure = offered(await first.inspect(outcome.runId), "measure_article");
    const oldClaim = await claimOffer(testHarness, first, measure, "old-worker");

    testHarness.clock.advance(1_001);
    const newClaim = await claimOffer(testHarness, second, measure, "old-worker");
    await assert.rejects(first.heartbeat(oldClaim), StaleClaimError);

    const staleOutputId = artifactId("late-answer-output");
    const beforeEvents = (await first.inspect(outcome.runId)).events.filter(
      (event) => event.type === "WORK_COMPLETED",
    ).length;
    await first.answer(oldClaim, {
      contractVersion: measure.contractVersion,
      result: { fits: true, pageCount: 1 },
      artifacts: [
        {
          id: staleOutputId,
          kind: "article_measurement",
          schemaVersion: "measurement/1",
          mediaType: "application/json",
          payload: { kind: "json", value: { fits: true, pageCount: 1 } },
        },
      ],
    });

    const current = await second.inspect(outcome.runId);
    const staleArtifacts = current.artifacts.filter(
      (artifact) => artifact.producingAttemptId === oldClaim.attemptId,
    );
    assert.equal(staleArtifacts.length, 2);
    assert.ok(staleArtifacts.some((artifact) => artifact.id === staleOutputId));
    assert.equal(await first.readText(staleOutputId), JSON.stringify({ fits: true, pageCount: 1 }));
    assert.equal(
      current.events.filter((event) => event.type === "WORK_COMPLETED").length,
      beforeEvents,
    );
    assert.equal(
      current.attempts.find((attempt) => attempt.id === oldClaim.attemptId)?.status,
      "timed_out",
    );
    assert.equal(
      current.offers.find((offer) => offer.id === measure.id)?.activeAttemptId,
      newClaim.attemptId,
    );
  });

  test("an active claim survives engine restart and can be answered", async (testContext) => {
    const testHarness = await harness(testContext);
    const first = testHarness.open({ coordinatorId: "restart-first", workLeaseMs: 2_000 });
    const fixture = await prepareArticleFixture(testHarness, articleFixture("restart"));
    const outcome = await first.start(fixture.spec);
    const measure = offered(await first.inspect(outcome.runId), "measure_article");
    const claim = await claimOffer(testHarness, first, measure, "restart-worker");
    first.close();

    const restarted = testHarness.open({ coordinatorId: "restart-second", workLeaseMs: 2_000 });
    const restored = await restarted.inspect(outcome.runId);
    assert.equal(restored.attempts.find((attempt) => attempt.id === claim.attemptId)?.status, "active");
    const renewed = await restarted.heartbeat(claim);
    assert.equal(renewed.attemptId, claim.attemptId);
    const answered = await restarted.answer(renewed, {
      contractVersion: measure.contractVersion,
      result: { fits: true, pageCount: 1, openerFits: true },
      artifacts: [measurementArtifact("restart-measurement")],
    });
    assert.equal(answered.attempts.find((attempt) => attempt.id === claim.attemptId)?.status, "answered");
    assert.equal(answered.events.filter((event) => event.type === "WORK_COMPLETED").length, 1);
  });
});

describe("RunEngine isolation, versions, and escalation", () => {
  test("one principal cannot cross source-aware and source-blind offers for a manuscript", async (testContext) => {
    const testHarness = await harness(testContext);
    const engine = testHarness.open();
    const fixture = await prepareArticleFixture(testHarness, articleFixture("exposure"));
    const outcome = await engine.start(fixture.spec);
    const view = await engine.inspect(outcome.runId);
    const worth = offered(view, "worth");
    const mechanics = offered(view, "mechanics");
    assert.equal(worth.subjectArtifactId, mechanics.subjectArtifactId);
    const worker = await testHarness.authority.workerFor(worth, {
      principalId: "same-principal",
      authority: "model",
      capabilities: ["text_model", "source_access", "source_blind"],
    });
    await worker.claim(engine, worth.id);
    await rejectCode(worker.claim(engine, mechanics.id), "WORKER_EXPOSURE_CONFLICT");
  });

  test("stored machine versions are refused after restart", async (testContext) => {
    const testHarness = await harness(testContext);
    const first = testHarness.open();
    const fixture = await prepareArticleFixture(testHarness, articleFixture("old-version"));
    const outcome = await first.start(fixture.spec);
    first.close();
    corruptStoredMachineVersion(testHarness.databasePath, outcome.runId, "article/0");

    const restarted = testHarness.open();
    await assert.rejects(restarted.advance(outcome.runId), MachineVersionError);
    const measure = offered(await restarted.inspect(outcome.runId), "measure_article");
    await assert.rejects(
      claimOffer(testHarness, restarted, measure, "version-worker"),
      MachineVersionError,
    );
  });

  test("escalation stays repairable, unsealed, and exits after a human budget choice", async (testContext) => {
    const testHarness = await harness(testContext);
    const engine = testHarness.open();
    const fixture = await prepareArticleFixture(
      testHarness,
      articleFixture("escalation", { maxIterations: 0 }),
    );
    const outcome = await engine.start(fixture.spec);
    assert.equal(outcome.status, "escalated");
    if (outcome.status !== "escalated") {
      return;
    }
    const escalated = await engine.inspect(outcome.runId);
    const rootActor = escalated.actors.find((actor) => actor.parentActorId === undefined);
    assert.ok(rootActor);
    assert.equal(rootActor.status, "active");
    assert.ok(outcome.actors.includes(rootActor.id));
    const budget = offered(escalated, "editor_decision");
    assert.equal(budget.slot, "budget_decision");
    await rejectCode(engine.seal(outcome.runId), "RUN_NOT_TERMINAL");

    const worker = await testHarness.authority.workerFor(budget, { principalId: "budget-editor" });
    const preparation = await engine.prepareHumanDecision(budget.id, worker);
    await rejectCode(
      engine.decide(preparation, worker, {
        schemaVersion: "human-decision-intent/1",
        offerId: preparation.offerId,
        taskArtifactId: preparation.taskArtifactId,
        inputArtifactIds: preparation.inputArtifactIds,
        result: { choice: "revise" },
      }),
      "HUMAN_DECISION_CHOICE_INVALID",
    );
    const recovered = await engine.decide(preparation, worker, {
      schemaVersion: "human-decision-intent/1",
      offerId: preparation.offerId,
      taskArtifactId: preparation.taskArtifactId,
      inputArtifactIds: preparation.inputArtifactIds,
      result: { choice: "increase_budget", maxIterations: 2 },
    });
    assert.equal(recovered.status, "waiting");
    const recoveredActor = recovered.actors.find((actor) => actor.id === rootActor.id);
    assert.equal(recoveredActor?.state, "drafting");
    assert.equal(recoveredActor?.status, "active");
    assert.ok(recovered.offers.some((offer) => offer.role === "writer" && offer.status === "offered"));
  });
});

describe("RunEngine crash boundaries", () => {
  for (const point of [
    "artifact.after_rename",
    "start.after_artifact_rename",
    "start.before_commit",
  ] as const) {
    test(`start recovers after ${point}`, async (testContext) => {
      const testHarness = await harness(testContext);
      const failpoints = new ThrowOnce(point);
      const engine = testHarness.open({ failpoints });
      const manuscriptPath = join(testHarness.root, `${point.replaceAll(".", "-")}.txt`);
      await writeFile(manuscriptPath, `payload for ${point}`, "utf8");
      const initial = articleFixture(`start-${point.replaceAll(".", "-")}`);
      const fixture = replacePayload(initial, initial.manuscriptId, {
        kind: "file",
        path: manuscriptPath,
      });
      const preparedFixture = await prepareArticleFixture(testHarness, fixture);

      const startOptions = { idempotencyKey: `start-recovery-${point}` } as const;
      await assert.rejects(engine.start(preparedFixture.spec, startOptions), InjectedCrash);

      const recovered = await engine.start(preparedFixture.spec, startOptions);
      assert.equal(recovered.status, "waiting");
      assert.equal(await engine.readText(fixture.manuscriptId), `payload for ${point}`);
    });
  }

  test("a start crash after commit is resumed without duplicating the run", async (testContext) => {
    const testHarness = await harness(testContext);
    const engine = testHarness.open({ failpoints: new ThrowOnce("start.after_commit") });
    const spec = (await prepareArticleFixture(testHarness, articleFixture("start-after-commit"))).spec;
    await assert.rejects(engine.start(spec, { idempotencyKey: "start-after-commit" }), InjectedCrash);
    engine.close();

    const restarted = testHarness.open();
    const outcome = await restarted.start(spec, { idempotencyKey: "start-after-commit" });
    assert.equal(outcome.status, "waiting");
    const view = await restarted.inspect(outcome.runId);
    assert.equal(view.events.filter((event) => event.type === "@@engine/initialized").length, 1);
  });

  for (const point of [
    "artifact.after_rename",
    "answer.after_artifact_rename",
    "answer.before_artifact_commit",
  ] as const) {
    test(`answer recovers after ${point}`, async (testContext) => {
      const testHarness = await harness(testContext);
      const engine = testHarness.open({
        failpoints: new ThrowOnce(point),
        workLeaseMs: 5_000,
      });
      const fixture = await prepareArticleFixture(
        testHarness,
        articleFixture(`answer-${point.replaceAll(".", "-")}`),
      );
      const outcome = await engine.start(fixture.spec);
      const measure = offered(await engine.inspect(outcome.runId), "measure_article");
      const claim = await claimOffer(testHarness, engine, measure, `worker-${point}`);
      const payloadPath = join(testHarness.root, `answer-${point.replaceAll(".", "-")}.json`);
      await writeFile(payloadPath, JSON.stringify({ fits: true, pageCount: 1 }), "utf8");
      const outputId = artifactId(`output-${point.replaceAll(".", "-")}`);
      const answer = {
        contractVersion: measure.contractVersion,
        result: { fits: true, pageCount: 1, openerFits: true },
        artifacts: [
          {
            id: outputId,
            kind: "article_measurement",
            schemaVersion: "measurement/1",
            mediaType: "application/json",
            payload: { kind: "file" as const, path: payloadPath },
          },
        ],
      };

      await assert.rejects(engine.answer(claim, answer), InjectedCrash);
      await rejectCode(engine.readArtifact(outputId), "ARTIFACT_NOT_FOUND");
      const beforeRecovery = await engine.inspect(outcome.runId);
      assert.equal(
        beforeRecovery.attempts.find((attempt) => attempt.id === claim.attemptId)?.status,
        "active",
      );

      const recovered = await engine.answer(claim, answer);
      assert.equal(recovered.attempts.find((item) => item.id === claim.attemptId)?.status, "answered");
      assert.equal(
        await engine.readText(outputId),
        JSON.stringify({ fits: true, pageCount: 1 }),
      );
      assert.equal(
        recovered.artifacts.filter(
          (artifact) => artifact.producingAttemptId === claim.attemptId,
        ).length,
        2,
      );
    });
  }

  test("an answer crash after commit resumes the pending transition once", async (testContext) => {
    const testHarness = await harness(testContext);
    const engine = testHarness.open({
      failpoints: new ThrowOnce("answer.after_commit"),
      workLeaseMs: 5_000,
    });
    const fixture = await prepareArticleFixture(testHarness, articleFixture("answer-after-commit"));
    const outcome = await engine.start(fixture.spec);
    const measure = offered(await engine.inspect(outcome.runId), "measure_article");
    const claim = await claimOffer(testHarness, engine, measure, "after-commit-worker");
    await assert.rejects(
      engine.answer(claim, {
        contractVersion: measure.contractVersion,
        result: { fits: true, pageCount: 1, openerFits: true },
        artifacts: [measurementArtifact("after-commit-measurement")],
      }),
      InjectedCrash,
    );
    const before = await engine.inspect(outcome.runId);
    assert.equal(before.events.filter((event) => event.type === "WORK_COMPLETED").length, 0);
    engine.close();

    const restarted = testHarness.open();
    await restarted.advance(outcome.runId);
    await restarted.advance(outcome.runId);
    const after = await restarted.inspect(outcome.runId);
    assert.equal(after.events.filter((event) => event.type === "WORK_COMPLETED").length, 1);
  });
});

describe("RunEngine sealing and artifact authority", () => {
  for (const point of ["seal.after_artifact_rename", "seal.after_commit"] as const) {
    test(`sealing recovers across ${point}`, async (testContext) => {
      const testHarness = await harness(testContext);
      const fixture = await prepareArticleFixture(testHarness, articleFixture(`seal-${point}`));
      const initial = testHarness.open();
      const completed = await completeArticle(testHarness, initial, fixture);
      initial.close();

      const crashing = testHarness.open({ failpoints: new ThrowOnce(point) });
      await assert.rejects(crashing.seal(completed.id), InjectedCrash);
      crashing.close();

      const recovered = testHarness.open();
      const sealed = await recovered.seal(completed.id);
      assert.equal((JSON.parse(await recovered.readText(sealed)) as { readonly id: string }).id, completed.id);
    });
  }

  test("a genuinely complete run seals once and rejects later mutation", async (testContext) => {
    const testHarness = await harness(testContext);
    const engine = testHarness.open();
    const fixture = await prepareArticleFixture(testHarness, articleFixture("seal"));
    const completed = await completeArticle(testHarness, engine, fixture);
    const sealed = await engine.seal(completed.id);
    assert.equal(await engine.seal(completed.id), sealed);
    const exportValue = JSON.parse(await engine.readText(sealed)) as { readonly id: string };
    assert.equal(exportValue.id, completed.id);
    await rejectCode(engine.advance(completed.id), "RUN_SEALED");
  });

  test("equal bytes never merge distinct immutable artifact identities", async (testContext) => {
    const testHarness = await harness(testContext);
    const engine = testHarness.open();
    const fixture = await prepareArticleFixture(testHarness, articleFixture("identity", {
      sourceText: "identical-source-bytes",
    }));
    const outcome = await engine.start(fixture.spec);
    const view = await engine.inspect(outcome.runId);

    assert.ok(fixture.sourceIds.every((id) => view.artifacts.some((artifact) => artifact.id === id)));
    assert.equal(new Set(fixture.sourceIds).size, 2);
    assert.equal(await engine.readText(fixture.sourceIds[0]!), "identical-source-bytes");
    assert.equal(await engine.readText(fixture.sourceIds[1]!), "identical-source-bytes");
  });
});
