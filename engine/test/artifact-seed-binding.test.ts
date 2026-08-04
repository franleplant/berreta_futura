import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { Worker } from "node:worker_threads";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

import type { ArtifactId, JsonObject, RunId } from "../contracts/index.ts";
import { ArtifactLedger, ArtifactLedgerError } from "../workflow-authority/artifact-ledger.ts";

const id = (value: string) => value as ArtifactId;

test("pre-run manuscript seed binds once to its exact run", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-seed-bind-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  try {
    const source = id("seed-source");
    const manuscript = id("seed-manuscript");
    const runId = "seed-run" as RunId;
    ledger.createArtifact({ id: source, kind: "source_extraction", schemaVersion: "source-extraction/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "source" } });
    ledger.createArtifact({ id: manuscript, kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "seed" }, parents: [{ artifactId: source, relation: "input_binding" }], metadata: { articleId: "article", revisionId: "seed-revision" } });
    ledger.createRun({ runId, articleExecutionId: "seed-execution" as never, articleId: "article", editionId: "004", workflowVersion: "seed-test/1", loopsRunId: runId, manuscriptArtifactId: manuscript, args: {} as JsonObject });

    const bound = ledger.bindArtifactToRun({ runId, artifactId: manuscript, articleId: "article", expectedParents: [{ artifactId: source, relation: "input_binding" }] });
    assert.equal(bound.producingRunId, runId);
    assert.equal(ledger.bindArtifactToRun({ runId, artifactId: manuscript, articleId: "article", expectedParents: [{ artifactId: source, relation: "input_binding" }] }).producingRunId, runId);

    const otherRun = "other-seed-run" as RunId;
    ledger.createRun({ runId: otherRun, articleExecutionId: "other-seed-execution" as never, articleId: "article", editionId: "004", workflowVersion: "seed-test/1", loopsRunId: otherRun, manuscriptArtifactId: manuscript, args: {} as JsonObject });
    assert.throws(
      () => ledger.bindArtifactToRun({ runId: otherRun, artifactId: manuscript, articleId: "article", expectedParents: [{ artifactId: source, relation: "input_binding" }] }),
      (error: unknown) => error instanceof ArtifactLedgerError && error.code === "ARTIFACT_RUN_MISMATCH",
    );
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("concurrent seed binders elect one run and reject a relation mismatch", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-seed-bind-race-"));
  const databasePath = join(root, "magazine.sqlite");
  const ledger = new ArtifactLedger(databasePath);
  try {
    const source = id("race-source");
    const manuscript = id("race-manuscript");
    const runA = "race-run-a" as RunId;
    const runB = "race-run-b" as RunId;
    ledger.createArtifact({ id: source, kind: "source_extraction", schemaVersion: "source-extraction/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "source" } });
    ledger.createArtifact({ id: manuscript, kind: "article_manuscript", schemaVersion: "article-manuscript/1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "seed" }, parents: [{ artifactId: source, relation: "input_binding" }], metadata: { articleId: "article", revisionId: "race-revision" } });
    for (const candidate of [runA, runB]) {
      ledger.createRun({ runId: candidate, articleExecutionId: `${candidate}-execution` as never, articleId: "article", editionId: "004", workflowVersion: "seed-test/1", loopsRunId: candidate, manuscriptArtifactId: manuscript, args: {} as JsonObject });
    }
    const ledgerUrl = pathToFileURL(join(process.cwd(), "engine/workflow-authority/artifact-ledger.ts")).href;
    const bind = (runId: RunId) => new Promise<{ readonly ok: boolean; readonly runId?: string; readonly code?: string }>((resolve, reject) => {
      const worker = new Worker(`
        const { parentPort, workerData } = require("node:worker_threads");
        (async () => {
          const { ArtifactLedger } = await import(workerData.ledgerUrl);
          const ledger = new ArtifactLedger(workerData.databasePath);
          try {
            const artifact = ledger.bindArtifactToRun({
              runId: workerData.runId,
              artifactId: workerData.artifactId,
              articleId: workerData.articleId,
              expectedParents: [{ artifactId: workerData.sourceId, relation: "input_binding" }],
            });
            parentPort.postMessage({ ok: true, runId: artifact.producingRunId });
          } catch (error) {
            parentPort.postMessage({ ok: false, code: error && typeof error === "object" && "code" in error ? error.code : undefined });
          } finally {
            ledger.close();
          }
        })().catch((error) => parentPort.postMessage({ ok: false, code: error?.code }));
      `, { eval: true, workerData: { databasePath, ledgerUrl, runId, artifactId: manuscript, articleId: "article", sourceId: source } });
      worker.once("message", (message: { readonly ok: boolean; readonly runId?: string; readonly code?: string }) => resolve(message));
      worker.once("error", reject);
    });
    const results = await Promise.all([bind(runA), bind(runB)]);
    assert.equal(results.filter((result) => result.ok).length, 1);
    assert.equal(results.filter((result) => !result.ok && result.code === "ARTIFACT_RUN_MISMATCH").length, 1);
    const winner = ledger.requireArtifact(manuscript).producingRunId;
    assert.ok(winner === runA || winner === runB);

    assert.throws(
      () => ledger.bindArtifactToRun({ runId: winner!, artifactId: manuscript, articleId: "article", expectedParents: [{ artifactId: source, relation: "wrong_relation" }] }),
      (error: unknown) => error instanceof ArtifactLedgerError && error.code === "ARTIFACT_SEED_INVALID",
    );
  } finally {
    ledger.close();
    await rm(root, { recursive: true, force: true });
  }
});
