import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";
import { describe, test } from "node:test";

import type {
  ActorId,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  ArticleRunSpec,
  AttemptId,
  RunId,
  StateVisitId,
  WorkClaim,
  WorkOfferId,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import {
  materializeWorkPackage,
  SubprocessExecutionError,
  SubprocessExecutor,
} from "../executors/subprocess.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { RunEngineError } from "../run-engine/types.ts";
import { composeArticleWorkOffer } from "../task-composer/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

function actorId(value: string): ActorId {
  return value as ActorId;
}

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function attemptId(value: string): AttemptId {
  return value as AttemptId;
}

function runId(value: string): RunId {
  return value as RunId;
}

function stateVisitId(value: string): StateVisitId {
  return value as StateVisitId;
}

function workOfferId(value: string): WorkOfferId {
  return value as WorkOfferId;
}

function articleSpec(): ArticleRunSpec {
  return {
    articleId: "article-one",
    contentMode: "faithful_edit",
    attribution: {
      kind: "source_author",
      byline: "Source Author",
      sourceAuthors: ["Source Author"],
      sourceIds: ["source-one"],
    },
    editionContext: artifactId("edition-context"),
    articleBrief: artifactId("article-brief"),
    sources: [
      artifactId("source-extraction-a"),
      artifactId("source-extraction-b"),
      artifactId("source-extraction-c"),
    ],
    sourceApprovalArtifacts: [],
    writerPrompt: artifactId("writer-prompt"),
    judgePrompts: {
      worth: artifactId("worth-prompt"),
      mechanics: artifactId("mechanics-prompt"),
      evidence: artifactId("evidence-prompt"),
      shape: artifactId("shape-prompt"),
      teaching: artifactId("teaching-prompt"),
      craft: artifactId("craft-prompt"),
    },
    writingRules: artifactId("writing-rules"),
    policy: {
      maxIterations: 3,
      maximumReaderPages: 7,
      teaching: "applicable",
      enabledLenses: [
        "worth",
        "mechanics",
        "evidence",
        "shape",
        "teaching",
        "craft",
      ],
      blockingLenses: ["mechanics", "evidence"],
    },
    modelPolicy: {
      default: { adapter: "test", model: "deterministic" },
    },
  };
}

describe("article work provenance and role isolation", () => {
  test("writer input provenance contains every assigned source extraction", () => {
    const spec = articleSpec();
    const offer = composeArticleWorkOffer({
      actorId: actorId("article-actor"),
      actorKey: "article:one",
      state: "drafting",
      spec,
      role: "writer",
      slot: "writer",
    });

    assert.deepEqual(
      offer.inputArtifacts.filter((candidate) => spec.sources.includes(candidate)),
      spec.sources,
    );
    for (const source of spec.sources) {
      assert.equal(
        offer.inputArtifacts.includes(source),
        true,
        `writer offer omitted assigned source ${source}`,
      );
    }
    assert.equal(offer.taskArtifactId, spec.writerPrompt);
    assert.deepEqual(offer.allowedWorkerCapabilities, ["text_model", "source_access"]);
  });

  test("source-blind lenses receive only their prompt, manuscript, and writing rules", () => {
    const spec = articleSpec();
    const manuscript = artifactId("manuscript-v1");

    for (const role of ["mechanics", "shape", "craft"] as const) {
      const offer = composeArticleWorkOffer({
        actorId: actorId("article-actor"),
        actorKey: "article:one",
        state: "judging",
        spec,
        role,
        slot: role,
        manuscriptArtifact: manuscript,
      });

      assert.deepEqual(offer.inputArtifacts, [
        spec.judgePrompts[role],
        manuscript,
        spec.writingRules,
      ]);
      assert.equal(
        offer.inputArtifacts.some((candidate) => spec.sources.includes(candidate)),
        false,
      );
      assert.equal(offer.inputArtifacts.includes(spec.articleBrief), false);
      assert.equal(offer.inputArtifacts.includes(spec.editionContext!), false);
      assert.deepEqual(offer.allowedWorkerCapabilities, ["text_model", "source_blind"]);
    }
  });

  test("evidence receives every source and is explicitly source-aware", () => {
    const spec = articleSpec();
    const manuscript = artifactId("manuscript-v1");
    const offer = composeArticleWorkOffer({
      actorId: actorId("article-actor"),
      actorKey: "article:one",
      state: "judging",
      spec,
      role: "evidence",
      slot: "evidence",
      manuscriptArtifact: manuscript,
    });

    for (const source of spec.sources) {
      assert.equal(offer.inputArtifacts.includes(source), true);
    }
    assert.equal(offer.subjectArtifactId, manuscript);
    assert.deepEqual(offer.allowedWorkerCapabilities, ["text_model", "source_access"]);
  });
});

function textSeed(id: ArtifactId): ArtifactSeed {
  return {
    id,
    kind: "test_input",
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: `fixture for ${id}` },
  };
}

function isolationRunSpec(): ArticleRootRunSpec {
  const base = articleSpec();
  const initialManuscript = artifactId("manuscript-v1");
  const article: ArticleRunSpec = {
    ...base,
    initialManuscript,
    policy: {
      ...base.policy,
      enabledLenses: ["mechanics", "evidence"],
      blockingLenses: [],
    },
  };
  const references = [
    article.editionContext!,
    article.articleBrief,
    ...article.sources,
    article.writerPrompt,
    ...Object.values(article.judgePrompts).filter(
      (candidate): candidate is ArtifactId => candidate !== undefined,
    ),
    article.writingRules,
    initialManuscript,
  ];
  return {
    schemaVersion: 1,
    kind: "article",
    article,
    artifacts: [...new Set(references)].map((id) => ({
      ...textSeed(id),
      ...(article.sources.includes(id) ? { kind: "source_extraction" } : {}),
    })),
  };
}

describe("durable source exposure isolation", () => {
  test("rejects evidence after the same principal performed a source-blind review", async () => {
    const temporary = await mkdtemp(join(tmpdir(), "magazine-role-isolation-"));
    const engine = new SqliteRunEngine({
      databasePath: join(temporary, "run.sqlite"),
      artifactDirectory: join(temporary, "artifact-store"),
    });
    const authority = await AuthorityTestHarness.create(temporary);
    try {
      const started = await engine.start(await prepareArticleSources(
        engine,
        isolationRunSpec(),
        "isolation",
        await authority.human("source-reviewer"),
      ));
      const initial = await engine.inspect(started.runId);
      const mechanics = initial.offers.find(
        (candidate) => candidate.role === "mechanics" && candidate.status === "offered",
      );
      const measurement = initial.offers.find(
        (candidate) =>
          candidate.role === "measure_article" && candidate.status === "offered",
      );
      assert.ok(mechanics, "article run did not offer mechanics work");
      assert.ok(measurement, "article run did not offer measurement work");

      const dualExposureWorker = await authority.workerFor(mechanics, {
        principalId: "same-reviewer",
        authority: "model",
        capabilities: ["text_model", "source_blind", "source_access"],
      });
      const mechanicsClaim = await dualExposureWorker.claim(engine, mechanics.id);
      await engine.answer(mechanicsClaim, {
        contractVersion: mechanics.contractVersion,
        result: { decision: "pass" },
        artifacts: [],
      });

      const measurementWorker = await authority.workerFor(measurement, {
        principalId: "measurement-tool",
        authority: "tool",
        capabilities: ["subprocess"],
      });
      const measurementClaim = await measurementWorker.claim(engine, measurement.id);
      const afterMeasurement = await engine.answer(measurementClaim, {
        contractVersion: measurement.contractVersion,
        result: { fits: true, pageCount: 1, openerFits: true },
        artifacts: [{
          kind: "article_measurement",
          schemaVersion: "measure/1",
          mediaType: "application/json",
          payload: { kind: "json", value: { fits: true, pageCount: 1 } },
        }],
      });
      const evidence = afterMeasurement.offers.find(
        (candidate) => candidate.role === "evidence" && candidate.status === "offered",
      );
      assert.ok(evidence, "article run did not advance to evidence work");

      await assert.rejects(
        dualExposureWorker.claim(engine, evidence.id),
        (error: unknown) =>
          error instanceof RunEngineError && error.code === "WORKER_EXPOSURE_CONFLICT",
      );
    } finally {
      engine.close();
      await rm(temporary, { recursive: true, force: true });
    }
  });
});

const subprocessWorker: WorkerIdentity = {
  principalId: "subprocess-test-worker",
  authority: "tool",
  capabilities: ["subprocess"],
};

const subprocessOffer: WorkOfferView = {
  id: workOfferId("offer-subprocess"),
  runId: runId("run-subprocess"),
  actorId: actorId("actor-subprocess"),
  actorKey: "test:subprocess",
  state: "running",
  stateVisitId: stateVisitId("visit-subprocess"),
  role: "measure_article",
  slot: "measure",
  inputArtifacts: [artifactId("task-subprocess")],
  taskArtifactId: artifactId("task-subprocess"),
  contractVersion: "measure-article/1",
  allowedWorkerCapabilities: ["subprocess"],
  status: "claimed",
  activeAttemptId: attemptId("attempt-subprocess"),
  createdAt: "2026-08-02T00:00:00.000Z",
};

const subprocessClaim: WorkClaim = {
  offerId: subprocessOffer.id,
  attemptId: attemptId("attempt-subprocess"),
  attemptFence: 1,
  ticket: "test-subprocess-ticket",
  worker: subprocessWorker,
  leaseExpiresAt: "2026-08-02T00:15:00.000Z",
};

async function executeSubprocessOutput(stdout: string): Promise<unknown> {
  const executor = new SubprocessExecutor(
    "subprocess-contract-test",
    subprocessWorker,
    () => ({
      executable: process.execPath,
      args: ["-e", `process.stdout.write(${JSON.stringify(stdout)})`],
      cwd: process.cwd(),
      timeoutMs: 5_000,
      stdin: "",
    }),
  );
  return await executor.execute({
    claim: subprocessClaim,
    offer: subprocessOffer,
    artifacts: {
      readBytes: async () => new TextEncoder().encode("test task"),
      readText: async () => "test task",
    },
    signal: new AbortController().signal,
  });
}

describe("subprocess work-answer validation", () => {
  test("materializes the complete immutable input set for the worker", async () => {
    const sourceA = artifactId("source-a");
    const sourceB = artifactId("source-b");
    const offer = {
      ...subprocessOffer,
      inputArtifacts: [subprocessOffer.taskArtifactId, sourceA, sourceB],
    };
    const texts = new Map<ArtifactId, string>([
      [subprocessOffer.taskArtifactId, "the task"],
      [sourceA, "source A"],
      [sourceB, "source B"],
    ]);
    const workPackage = JSON.parse(await materializeWorkPackage({
      claim: subprocessClaim,
      offer,
      artifacts: {
        readBytes: async (id) => new TextEncoder().encode(texts.get(id) ?? ""),
        readText: async (id) => texts.get(id) ?? "",
      },
      signal: new AbortController().signal,
    })) as {
      task: { artifactId: ArtifactId; text: string };
      inputs: { artifactId: ArtifactId; text: string }[];
    };

    assert.deepEqual(workPackage.task, {
      artifactId: subprocessOffer.taskArtifactId,
      text: "the task",
    });
    assert.deepEqual(workPackage.inputs, [
      { artifactId: sourceA, text: "source A" },
      { artifactId: sourceB, text: "source B" },
    ]);
  });

  test("rejects output that is not JSON", async () => {
    await assert.rejects(
      executeSubprocessOutput("not-json"),
      (error: unknown) =>
        error instanceof SubprocessExecutionError &&
        error.classification === "permanent" &&
        error.message.includes("invalid JSON"),
    );
  });

  test("rejects an artifact that does not satisfy the answer artifact contract", async () => {
    const malformed = JSON.stringify({
      contractVersion: subprocessOffer.contractVersion,
      result: { fits: true },
      artifacts: [{ kind: "article_measurement" }],
    });

    await assert.rejects(
      executeSubprocessOutput(malformed),
      (error: unknown) =>
        error instanceof SubprocessExecutionError &&
        error.classification === "permanent" &&
        error.message.includes("work-answer contract"),
    );
  });

  test("rejects file artifacts outside an executor-owned output directory", async () => {
    const escaped = JSON.stringify({
      contractVersion: subprocessOffer.contractVersion,
      result: { fits: true },
      artifacts: [{
        kind: "article_measurement",
        schemaVersion: "measure/1",
        mediaType: "application/json",
        payload: { kind: "file", path: "/tmp/not-owned-by-this-attempt" },
      }],
    });

    await assert.rejects(
      executeSubprocessOutput(escaped),
      (error: unknown) =>
        error instanceof SubprocessExecutionError &&
        error.classification === "permanent" &&
        error.message.includes("owned output directory"),
    );
  });
});
