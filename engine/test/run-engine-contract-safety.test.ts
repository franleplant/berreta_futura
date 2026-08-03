import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, test, type TestContext } from "node:test";

import type {
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  createRunEngine,
  RunEngineError,
  StaleClaimError,
  type SqliteRunEngine,
} from "../run-engine/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

type Harness = {
  readonly engine: SqliteRunEngine;
  readonly root: string;
  readonly authority: AuthorityTestHarness;
};

async function harness(testContext: TestContext): Promise<Harness> {
  const root = await mkdtemp(join(tmpdir(), "mag-contract-safety-"));
  const engine = createRunEngine({
    databasePath: join(root, "run.sqlite3"),
    artifactDirectory: join(root, "artifacts"),
  });
  testContext.after(async () => {
    engine.close();
    await rm(root, { recursive: true, force: true });
  });
  return { engine, root, authority: await AuthorityTestHarness.create(root) };
}

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(id: ArtifactId, kind: string): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: id },
  };
}

function articleSpec(prefix: string): ArticleRootRunSpec {
  const brief = artifactId(`${prefix}-brief`);
  const writerPrompt = artifactId(`${prefix}-writer-prompt`);
  const writingRules = artifactId(`${prefix}-writing-rules`);
  const manuscript = artifactId(`${prefix}-manuscript`);
  const mechanicsPrompt = artifactId(`${prefix}-mechanics-prompt`);
  const worthPrompt = artifactId(`${prefix}-worth-prompt`);
  const evidencePrompt = artifactId(`${prefix}-evidence-prompt`);
  const source = artifactId(`${prefix}-source`);
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      seed(brief, "article_brief"),
      seed(writerPrompt, "writer_prompt"),
      seed(writingRules, "writing_rules"),
      seed(manuscript, "article_manuscript"),
      seed(mechanicsPrompt, "mechanics_prompt"),
      seed(worthPrompt, "worth_prompt"),
      seed(evidencePrompt, "evidence_prompt"),
      seed(source, "source_extraction"),
    ],
    article: {
      articleId: `${prefix}-article`,
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine" },
      articleBrief: brief,
      sources: [source],
      sourceApprovalArtifacts: [],
      writerPrompt,
      judgePrompts: {
        mechanics: mechanicsPrompt,
        worth: worthPrompt,
        evidence: evidencePrompt,
      },
      writingRules,
      initialManuscript: manuscript,
      policy: {
        maxIterations: 1,
        maximumReaderPages: 7,
        teaching: "not_applicable",
        enabledLenses: ["worth", "mechanics", "evidence"],
        blockingLenses: ["worth", "mechanics"],
      },
      modelPolicy: {
        default: { adapter: "test", model: "deterministic" },
      },
    },
  };
}

function offered(view: Awaited<ReturnType<SqliteRunEngine["inspect"]>>, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(offer, `expected an offered ${role} task`);
  return offer;
}

describe("RunEngine answer contracts", () => {
  test("rejects a malformed role result before artifacts or completion are accepted", async (testContext) => {
    const { engine, authority } = await harness(testContext);
    const outcome = await engine.start(await prepareArticleSources(
      engine,
      articleSpec("malformed"),
      "malformed",
      await authority.human("malformed-source-reviewer"),
    ));
    const initial = await engine.inspect(outcome.runId);
    const measure = offered(initial, "measure_article");
    const claim = await authority.claim(engine, measure, {
      principalId: "measurement-worker",
      authority: "tool",
      capabilities: ["subprocess"],
    });
    const rejectedArtifactId = artifactId("malformed-result-artifact");

    await assert.rejects(
      engine.answer(claim, {
        contractVersion: measure.contractVersion,
        result: { fits: true, unexpected: "not in the contract" },
        artifacts: [{
          id: rejectedArtifactId,
          kind: "edition_measurement",
          schemaVersion: "test/1",
          mediaType: "application/json",
          payload: { kind: "json", value: { fits: true } },
        }],
      }),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "ANSWER_RESULT_INVALID",
    );

    const rejected = await engine.inspect(outcome.runId);
    assert.equal(
      rejected.offers.find((candidate) => candidate.id === measure.id)?.status,
      "claimed",
    );
    assert.equal(
      rejected.attempts.find((candidate) => candidate.id === claim.attemptId)?.status,
      "active",
    );
    assert.equal(
      rejected.events.filter((event) => event.type === "WORK_COMPLETED").length,
      0,
    );
    await assert.rejects(
      engine.readArtifact(rejectedArtifactId),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "ARTIFACT_NOT_FOUND",
    );

    const wrongKindArtifactId = artifactId("wrong-measurement-kind");
    await assert.rejects(
      engine.answer(claim, {
        contractVersion: measure.contractVersion,
        result: { fits: true, openerFits: true, pageCount: 1 },
        artifacts: [{
          id: wrongKindArtifactId,
          kind: "edition_measurement",
          schemaVersion: "test/1",
          mediaType: "application/json",
          payload: { kind: "json", value: { fits: true } },
        }],
      }),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "ANSWER_ARTIFACTS_INVALID",
    );
    await assert.rejects(
      engine.readArtifact(wrongKindArtifactId),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "ARTIFACT_NOT_FOUND",
    );

    const accepted = await engine.answer(claim, {
      contractVersion: measure.contractVersion,
      result: { fits: true, openerFits: true, pageCount: 1 },
      artifacts: [{
        kind: "article_measurement",
        schemaVersion: "test/1",
        mediaType: "application/json",
        payload: { kind: "json", value: { fits: true } },
      }],
    });
    assert.equal(
      accepted.offers.find((candidate) => candidate.id === measure.id)?.status,
      "answered",
    );
  });

  test("does not consume a writer offer without exactly one manuscript", async (testContext) => {
    const { engine, authority } = await harness(testContext);
    const withManuscript = await prepareArticleSources(
      engine,
      articleSpec("writer-artifact"),
      "writer-artifact",
      await authority.human("writer-artifact-source-reviewer"),
    );
    const { initialManuscript: _initialManuscript, ...article } = withManuscript.article;
    const outcome = await engine.start({ ...withManuscript, article });
    const initial = await engine.inspect(outcome.runId);
    const writer = offered(initial, "writer");
    const claim = await authority.claim(engine, writer, {
      principalId: "article-writer",
      authority: "model",
      capabilities: ["text_model", "source_access"],
    });

    await assert.rejects(
      engine.answer(claim, {
        contractVersion: writer.contractVersion,
        result: { status: "complete" },
        artifacts: [],
      }),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "ANSWER_ARTIFACTS_INVALID",
    );
    const stillClaimed = await engine.inspect(outcome.runId);
    assert.equal(
      stillClaimed.offers.find((candidate) => candidate.id === writer.id)?.status,
      "claimed",
    );
    assert.equal(
      stillClaimed.events.filter((event) => event.type === "WORK_COMPLETED").length,
      0,
    );

    const accepted = await engine.answer(claim, {
      contractVersion: writer.contractVersion,
      result: { status: "complete" },
      artifacts: [{
        kind: "article_manuscript",
        schemaVersion: "test/1",
        mediaType: "text/markdown",
        payload: { kind: "text", text: "A complete manuscript." },
      }, {
        kind: "writer_working_notes",
        schemaVersion: "test/1",
        mediaType: "text/plain",
        payload: { kind: "text", text: "Working notes for this iteration." },
      }],
    });
    assert.equal(
      accepted.offers.find((candidate) => candidate.id === writer.id)?.status,
      "answered",
    );
    assert.equal(
      accepted.actors.find((candidate) => candidate.parentActorId === undefined)?.state,
      "stage_1",
    );
  });
});

describe("RunEngine state visit fencing", () => {
  test("cancels unfinished sibling offers and stales active attempts when a visit exits", async (testContext) => {
    const { engine, authority } = await harness(testContext);
    const outcome = await engine.start(await prepareArticleSources(
      engine,
      articleSpec("visit-exit"),
      "visit-exit",
      await authority.human("visit-exit-source-reviewer"),
    ));
    const initial = await engine.inspect(outcome.runId);
    const measurement = offered(initial, "measure_article");
    const mechanics = offered(initial, "mechanics");
    const worth = offered(initial, "worth");
    const measurementClaim = await authority.claim(engine, measurement, {
      principalId: "measurement-worker",
      authority: "tool",
      capabilities: ["subprocess"],
    });
    const mechanicsClaim = await authority.claim(engine, mechanics, {
      principalId: "mechanics-worker",
      authority: "model",
      capabilities: ["text_model", "source_blind"],
    });

    const exited = await engine.fail(mechanicsClaim, {
      classification: "retryable",
      message: "mechanics worker returned no usable verdict",
    });
    assert.equal(exited.status, "waiting");
    assert.equal(
      exited.offers.find((candidate) => candidate.id === measurement.id)?.status,
      "canceled",
    );
    assert.equal(
      exited.attempts.find((candidate) => candidate.id === measurementClaim.attemptId)?.status,
      "stale",
    );
    assert.equal(
      exited.offers.find((candidate) => candidate.id === worth.id)?.status,
      "canceled",
    );
    const replacementMeasurement = exited.offers.find(
      (candidate) =>
        candidate.role === "measure_article" && candidate.status === "offered",
    );
    const replacementMechanics = exited.offers.find(
      (candidate) => candidate.role === "mechanics" && candidate.status === "offered",
    );
    assert.ok(replacementMeasurement);
    assert.ok(replacementMechanics);
    assert.notEqual(replacementMeasurement.id, measurement.id);
    assert.notEqual(replacementMechanics.id, mechanics.id);
    assert.notEqual(replacementMeasurement.stateVisitId, measurement.stateVisitId);
    await assert.rejects(
      engine.heartbeat(measurementClaim),
      (error: unknown) => error instanceof StaleClaimError,
    );
    await assert.rejects(
      engine.claim(measurement.id, {
        principalId: "replacement-measurement-worker",
        authority: "tool",
        capabilities: ["subprocess"],
      }),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "CALLER_IDENTITY_REJECTED",
    );

    const eventCount = exited.events.length;
    const lateArtifactId = artifactId("late-measurement-artifact");
    const afterLateAnswer = await engine.answer(measurementClaim, {
      contractVersion: measurement.contractVersion,
      result: { fits: true, openerFits: true, pageCount: 1 },
      artifacts: [{
        id: lateArtifactId,
        kind: "article_measurement",
        schemaVersion: "test/1",
        mediaType: "application/json",
        payload: { kind: "json", value: { fits: true } },
      }],
    });
    assert.equal(afterLateAnswer.events.length, eventCount);
    assert.equal(
      afterLateAnswer.events.filter((event) => event.type === "WORK_COMPLETED").length,
      0,
    );
    assert.equal(
      afterLateAnswer.offers.find((candidate) => candidate.id === measurement.id)?.status,
      "canceled",
    );
    assert.equal(
      afterLateAnswer.attempts.find(
        (candidate) => candidate.id === measurementClaim.attemptId,
      )?.status,
      "stale",
    );
    assert.ok(
      afterLateAnswer.artifacts.some((artifact) => artifact.id === lateArtifactId),
      "late evidence remains retained without becoming a completion event",
    );
  });
});
