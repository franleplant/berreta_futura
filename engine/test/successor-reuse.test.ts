import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test, type TestContext } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  RunId,
  RunView,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  RunEngineError,
  SqliteRunEngine,
  type FailpointController,
  type RunEngineClock,
  type RunEngineFailpoint,
} from "../run-engine/index.ts";
import { corruptStoredMachineVersion } from "./internal-schema-test-helper.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";

type Harness = {
  readonly engine: SqliteRunEngine;
  readonly databasePath: string;
  readonly artifactDirectory: string;
};

class CrashOnce implements FailpointController {
  private crashed = false;

  hit(name: RunEngineFailpoint): void {
    if (!this.crashed && name === "outbox.before_effect_commit") {
      this.crashed = true;
      throw new Error("injected successor reuse crash");
    }
  }
}

class ManualClock implements RunEngineClock {
  private milliseconds = Date.now();

  now(): Date {
    return new Date(this.milliseconds);
  }

  advance(milliseconds: number): void {
    this.milliseconds += milliseconds;
  }
}

async function harness(context: TestContext): Promise<Harness> {
  const root = await mkdtemp(join(tmpdir(), "mag-successor-reuse-"));
  const databasePath = join(root, "runs.sqlite");
  const artifactDirectory = join(root, "artifacts");
  const engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  context.after(async () => {
    engine.close();
    await rm(root, { recursive: true, force: true });
  });
  return { engine, databasePath, artifactDirectory };
}

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function textSeed(
  artifactId: ArtifactId,
  kind: string,
  text = `fixture:${artifactId}`,
): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "successor-fixture/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text },
  };
}

function articleSpec(prefix: string): ArticleRootRunSpec {
  const brief = id(`${prefix}-brief`);
  const source = id(`${prefix}-source`);
  const writerPrompt = id(`${prefix}-writer-prompt`);
  const worthPrompt = id(`${prefix}-worth-prompt`);
  const evidencePrompt = id(`${prefix}-evidence-prompt`);
  const craftPrompt = id(`${prefix}-craft-prompt`);
  const rules = id(`${prefix}-rules`);
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      textSeed(brief, "article_brief"),
      textSeed(source, "source_extraction"),
      textSeed(writerPrompt, "writer_prompt", "Write a concise systems article."),
      textSeed(worthPrompt, "worth_prompt"),
      textSeed(evidencePrompt, "evidence_prompt"),
      textSeed(craftPrompt, "craft_prompt"),
      textSeed(rules, "writing_rules"),
    ],
    article: {
      articleId: `${prefix}-article`,
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine editors" },
      articleBrief: brief,
      sources: [source],
      sourceApprovalArtifacts: [],
      writerPrompt,
      judgePrompts: { worth: worthPrompt, evidence: evidencePrompt, craft: craftPrompt },
      writingRules: rules,
      policy: {
        maxIterations: 2,
        maximumReaderPages: 7,
        teaching: "not_applicable",
        enabledLenses: ["worth", "evidence", "craft"],
        blockingLenses: ["worth", "evidence", "craft"],
      },
      modelPolicy: { default: { adapter: "fixture", model: "writer-v1" } },
    },
  };
}

function worker(offer: WorkOfferView) {
  return {
    principalId: `worker:${offer.id}`,
    authority: offer.allowedWorkerCapabilities.includes("text_model")
      ? "model" as const
      : "tool" as const,
    capabilities: offer.allowedWorkerCapabilities,
  };
}

function outputArtifact(
  artifactId: ArtifactId,
  kind: string,
  text: string,
): AnswerArtifact {
  return {
    id: artifactId,
    kind,
    schemaVersion: "successor-output/1",
    mediaType: "text/plain",
    payload: { kind: "text", text },
  };
}

async function answerOffer(
  engine: SqliteRunEngine,
  offer: WorkOfferView,
  outputPrefix: string,
): Promise<RunView> {
  const claim = await engine.claim(offer.id, worker(offer));
  if (offer.role === "durable_checkpoint") {
    return await engine.answer(claim, await durableCheckpointAnswer(engine, offer));
  }
  if (offer.role === "writer") {
    return await engine.answer(claim, {
      contractVersion: offer.contractVersion,
      result: { status: "complete" },
      artifacts: [
        outputArtifact(
          id(`${outputPrefix}-${offer.id}-manuscript`),
          "article_manuscript",
          `# ${outputPrefix}\n\nA settled article.`,
        ),
        outputArtifact(
          id(`${outputPrefix}-${offer.id}-notes`),
          "writer_working_notes",
          "Keep the causal chain explicit.",
        ),
      ],
    });
  }
  if (offer.role === "measure_article") {
    return await engine.answer(claim, {
      contractVersion: offer.contractVersion,
      result: { fits: true, pageCount: 1 },
      artifacts: [{
        id: id(`${outputPrefix}-${offer.id}-measurement`),
        kind: "article_measurement",
        schemaVersion: "successor-measurement/1",
        mediaType: "application/json",
        payload: { kind: "json", value: { fits: true, pageCount: 1 } },
      }],
    });
  }
  return await engine.answer(claim, {
    contractVersion: offer.contractVersion,
    result: { decision: "pass" },
    artifacts: [],
  });
}

async function settle(
  engine: SqliteRunEngine,
  runId: RunId,
  outputPrefix: string,
): Promise<RunView> {
  for (let step = 0; step < 20; step += 1) {
    const view = await engine.inspect(runId);
    if (view.status === "complete") {
      return view;
    }
    const offer = view.offers.find((candidate) => candidate.status === "offered");
    assert.ok(offer, `run ${runId} stranded in ${view.actors[0]?.state}`);
    await answerOffer(engine, offer, outputPrefix);
  }
  assert.fail(`run ${runId} exceeded its settlement budget`);
}

function rootOutputs(view: RunView): readonly ArtifactId[] {
  const root = view.actors.find((actor) => actor.parentActorId === undefined);
  assert.ok(root);
  return root.outputs;
}

test("an unchanged successor reuses exact ancestor answers without attempts", async (context) => {
  const { engine, databasePath, artifactDirectory } = await harness(context);
  const original = await engine.start(await prepareArticleSources(engine, articleSpec("exact"), "exact"));
  const settled = await settle(engine, original.runId, "ancestor");

  const firstFork = await engine.fork(settled.id, [], {
    idempotencyKey: "unchanged-successor",
  });
  const checkpoint = (await engine.inspect(firstFork.runId)).offers.find(
    (offer) => offer.role === "durable_checkpoint" && offer.status === "offered",
  );
  assert.ok(checkpoint);
  await answerOffer(engine, checkpoint, "successor-checkpoint");
  assert.equal((await engine.inspect(firstFork.runId)).status, "complete");
  engine.close();
  const restarted = new SqliteRunEngine({ databasePath, artifactDirectory });
  context.after(() => restarted.close());
  const repeatedFork = await restarted.fork(settled.id, [], {
    idempotencyKey: "unchanged-successor",
  });
  assert.equal(repeatedFork.runId, firstFork.runId);

  const successor = await restarted.inspect(firstFork.runId);
  assert.deepEqual(rootOutputs(successor), rootOutputs(settled));
  assert.equal(successor.attempts.length, 1);
  assert.ok(successor.offers.length > 0);
  assert.ok(successor.offers.every((offer) => offer.status === "answered"));
  assert.ok(successor.offers.every((offer) =>
    offer.role === "durable_checkpoint" || offer.reusedFromRunId !== undefined
  ));
  assert.ok(successor.offers.every((offer) =>
    offer.role === "durable_checkpoint" || offer.reusedFromOfferId !== undefined
  ));
  assert.ok(successor.offers.every((offer) =>
    offer.role === "durable_checkpoint" || offer.reusedAnswerArtifactId !== undefined
  ));
  const visible = new Set(successor.artifacts.map((artifact) => artifact.id));
  for (const offer of successor.offers.filter((offer) => offer.role !== "durable_checkpoint")) {
    assert.ok(visible.has(offer.reusedAnswerArtifactId as ArtifactId));
  }
  const reuseEvents = successor.events.filter(
    (event) => event.type === "WORK_COMPLETED" && event.payload.reuse !== undefined,
  );
  assert.equal(
    reuseEvents.length,
    successor.offers.filter((offer) => offer.role !== "durable_checkpoint").length,
  );

  const grandchildOutcome = await restarted.fork(successor.id, []);
  const grandchildCheckpoint = (await restarted.inspect(grandchildOutcome.runId)).offers.find(
    (offer) => offer.role === "durable_checkpoint" && offer.status === "offered",
  );
  assert.ok(grandchildCheckpoint);
  await answerOffer(restarted, grandchildCheckpoint, "grandchild-checkpoint");
  assert.equal((await restarted.inspect(grandchildOutcome.runId)).status, "complete");
  const grandchild = await restarted.inspect(grandchildOutcome.runId);
  assert.deepEqual(rootOutputs(grandchild), rootOutputs(settled));
  assert.equal(grandchild.attempts.length, 1);
  assert.ok(grandchild.offers.every(
    (offer) => offer.role === "durable_checkpoint" || offer.reusedFromRunId === successor.id,
  ));
});

test("an old machine run forks as a fresh explicit successor instead of resuming", async (context) => {
  const { engine, databasePath, artifactDirectory } = await harness(context);
  const original = await engine.start(await prepareArticleSources(engine, articleSpec("old-machine"), "old-machine"));
  const settled = await settle(engine, original.runId, "ancestor");
  engine.close();
  corruptStoredMachineVersion(databasePath, settled.id, "article/old");

  const restarted = new SqliteRunEngine({ databasePath, artifactDirectory });
  context.after(() => restarted.close());
  const successor = await restarted.fork(settled.id, []);
  assert.equal(successor.status, "waiting");
  const view = await restarted.inspect(successor.runId);
  const writer = view.offers.find((offer) => offer.role === "writer");
  assert.ok(writer);
  assert.equal(writer.status, "offered");
  assert.equal(writer.reusedFromRunId, undefined);
});

test("reuse dispatch recovers atomically after a crash", async (context) => {
  const { engine, databasePath, artifactDirectory } = await harness(context);
  const original = await engine.start(await prepareArticleSources(engine, articleSpec("reuse-crash"), "reuse-crash"));
  const settled = await settle(engine, original.runId, "ancestor");
  engine.close();

  const clock = new ManualClock();
  const crashing = new SqliteRunEngine({
    databasePath,
    artifactDirectory,
    clock,
    failpoints: new CrashOnce(),
  });
  await assert.rejects(
    crashing.fork(settled.id, [], { idempotencyKey: "reuse-crash-successor" }),
    /injected successor reuse crash/,
  );
  crashing.close();
  clock.advance(60_000);

  const restarted = new SqliteRunEngine({ databasePath, artifactDirectory, clock });
  context.after(() => restarted.close());
  const recovered = await restarted.fork(settled.id, [], {
    idempotencyKey: "reuse-crash-successor",
  });
  const checkpoint = (await restarted.inspect(recovered.runId)).offers.find(
    (offer) => offer.role === "durable_checkpoint" && offer.status === "offered",
  );
  assert.ok(checkpoint);
  await answerOffer(restarted, checkpoint, "recovered-checkpoint");
  assert.equal((await restarted.inspect(recovered.runId)).status, "complete");
  const view = await restarted.inspect(recovered.runId);
  assert.equal(view.attempts.length, 1);
  assert.ok(view.offers.every((offer) =>
    offer.role === "durable_checkpoint" || offer.reusedFromOfferId !== undefined
  ));
});

test("a fork idempotency key is bound to its exact parent operation", async (context) => {
  const { engine } = await harness(context);
  const spec = await prepareArticleSources(engine, articleSpec("fork-operation-key"), "fork-operation-key");
  const firstParent = await engine.start(spec);
  const secondParent = await engine.start(spec);
  assert.notEqual(firstParent.runId, secondParent.runId);

  const firstFork = await engine.fork(firstParent.runId, [], {
    idempotencyKey: "parent-bound-fork",
  });
  assert.ok(firstFork.runId);
  await assert.rejects(
    engine.fork(secondParent.runId, [], {
      idempotencyKey: "parent-bound-fork",
    }),
    (error: unknown) =>
      error instanceof RunEngineError && error.code === "START_IDEMPOTENCY_CONFLICT",
  );
});

test("a changed writer prompt reruns the writer and all dependent work", async (context) => {
  const { engine } = await harness(context);
  const spec = await prepareArticleSources(engine, articleSpec("changed"), "changed");
  const original = await engine.start(spec);
  const settled = await settle(engine, original.runId, "ancestor");
  const changedPrompt = textSeed(
    id("changed-writer-prompt-v2"),
    "writer_prompt",
    "Write a different argument with a new opening.",
  );

  const successor = await engine.fork(settled.id, [{
    kind: "replace_artifact",
    from: spec.article.writerPrompt,
    to: changedPrompt,
  }]);
  assert.equal(successor.status, "waiting");
  let view = await engine.inspect(successor.runId);
  const writer = view.offers.find(
    (offer) => offer.role === "writer" && offer.status === "offered",
  );
  assert.ok(writer);
  assert.equal(writer.reusedFromOfferId, undefined);

  view = await answerOffer(engine, writer, "successor");
  const dependent = view.offers.filter((offer) => offer.status === "offered");
  assert.ok(dependent.some((offer) => offer.role === "measure_article"));
  assert.ok(dependent.some((offer) => offer.role === "worth"));
  assert.ok(dependent.every((offer) => offer.reusedFromOfferId === undefined));
  const completed = await settle(engine, view.id, "successor");
  assert.ok(completed.offers.some((offer) => offer.role === "evidence"));
  assert.ok(completed.offers.some((offer) => offer.role === "craft"));
  assert.ok(completed.offers.every((offer) => offer.reusedFromOfferId === undefined));
  assert.equal(completed.attempts.length, completed.offers.length);
});

test("equal bytes under a new prompt ArtifactId never qualify for reuse", async (context) => {
  const { engine } = await harness(context);
  const spec = await prepareArticleSources(engine, articleSpec("identity"), "identity");
  const original = await engine.start(spec);
  const settled = await settle(engine, original.runId, "ancestor");
  const sameBytesNewIdentity = textSeed(
    id("identity-writer-prompt-new-id"),
    "writer_prompt",
    "Write a concise systems article.",
  );

  const successor = await engine.fork(settled.id, [{
    kind: "replace_artifact",
    from: spec.article.writerPrompt,
    to: sameBytesNewIdentity,
  }]);
  const view = await engine.inspect(successor.runId);
  const writer = view.offers.find((offer) => offer.role === "writer");
  assert.ok(writer);
  assert.equal(writer.status, "offered");
  assert.equal(writer.reusedFromRunId, undefined);
  assert.equal(view.attempts.length, 0);
});

test("ordered artifact dependencies are part of reuse identity", async (context) => {
  const { engine } = await harness(context);
  const base = articleSpec("ordered-inputs");
  const secondSource = id("ordered-inputs-source-two");
  const spec: ArticleRootRunSpec = {
    ...base,
    artifacts: [
      ...base.artifacts,
      textSeed(secondSource, "source_extraction", "A second fixed source."),
    ],
    article: {
      ...base.article,
      sources: [...base.article.sources, secondSource],
    },
  };
  const prepared = await prepareArticleSources(engine, spec, "ordered-inputs");
  const original = await engine.start(prepared);
  const settled = await settle(engine, original.runId, "ancestor");

  const successor = await engine.fork(settled.id, [{
    kind: "replace_spec",
    path: "/article/sources",
    value: [...prepared.article.sources].reverse(),
  }, {
    kind: "replace_spec",
    path: "/article/sourceApprovalArtifacts",
    value: [...prepared.article.sourceApprovalArtifacts].reverse(),
  }]);
  const view = await engine.inspect(successor.runId);
  const writer = view.offers.find((offer) => offer.role === "writer");
  assert.ok(writer);
  assert.equal(writer.status, "offered");
  assert.equal(writer.reusedFromRunId, undefined);
});

test("replace_spec accepts scalar and array successor inputs", async (context) => {
  const { engine } = await harness(context);
  const spec = await prepareArticleSources(engine, articleSpec("json-values"), "json-values");
  const original = await engine.start(spec);
  const settled = await settle(engine, original.runId, "ancestor");
  const scalar = await engine.fork(settled.id, [{
    kind: "replace_spec",
    path: "/article/modelPolicy/default/model",
    value: "writer-v2",
  }]);
  const scalarView = await engine.inspect(scalar.runId);
  assert.ok(scalarView.offers.some(
    (offer) => offer.role === "writer" && offer.status === "offered",
  ));
  assert.equal(
    (scalarView.actors[0]?.input.spec as { modelPolicy?: { default?: { model?: string } } })
      .modelPolicy?.default?.model,
    "writer-v2",
  );

  const array = await engine.fork(settled.id, [{
    kind: "replace_spec",
    path: "/article/policy/blockingLenses",
    value: ["evidence"],
  }]);
  const arrayView = await engine.inspect(array.runId);
  assert.deepEqual(
    (arrayView.actors[0]?.input.spec as { policy?: { blockingLenses?: readonly string[] } })
      .policy?.blockingLenses,
    ["evidence"],
  );
});
