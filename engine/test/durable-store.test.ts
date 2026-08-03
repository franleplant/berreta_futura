import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, readdir, rm, writeFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { stringify } from "yaml";

import type {
  ArtifactId,
  ArtifactView,
  PromotionId,
  RevisionId,
  RunId,
  RunView,
} from "../contracts/index.ts";
import {
  DurableStore,
  DurableStoreError,
  newRevisionId,
  parseRevisionId,
  type DurableGit,
  type DurablePromotionRequest,
  type GitCheckpointRequest,
  type GitRevisionBinding,
} from "../durable/index.ts";
import { DurableStoreCheckpointImplementation } from "../executors/durable-checkpoint.ts";
import type { ExecutorContext } from "../executors/types.ts";

const RUN_ID = "run_durable-store" as RunId;
const PROMOTION_ID = "promotion_durable-store" as PromotionId;
const REVISION_ID = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;
const MANUSCRIPT = "art_durable-manuscript" as ArtifactId;
const INPUT = "art_durable-input" as ArtifactId;
const DECISION = "art_durable-decision" as ArtifactId;
const INPUT_REVISION = "rev_20260801T010203004Z_bbbbbbbbbbbb" as RevisionId;

test("RevisionId uses sortable UTC basic time plus a portable random identity", () => {
  assert.equal(
    newRevisionId(new Date("2026-08-02T20:06:41.636Z"), new Uint8Array(8)),
    REVISION_ID,
  );
  assert.equal(parseRevisionId(REVISION_ID), REVISION_ID);
  assert.throws(() => parseRevisionId("rev_20261302T200641636Z_aaaaaaaaaaaa"));
  assert.throws(() => parseRevisionId("rev_20260802T200641636Z_AAAAAAAAAAAA"));
  assert.ok(
    newRevisionId(new Date("2026-08-02T20:06:41.636Z"), new Uint8Array(8))
      < newRevisionId(new Date("2026-08-02T20:06:41.637Z"), new Uint8Array(8)),
  );
});

test("DurableStore promotes exact accepted EngineArtifacts atomically and adopts an identical retry", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-durable-store-"));
  try {
    await writeInputRevision(temporary);
    const git = new FakeGit();
    const store = new DurableStore({
      repositoryRoot: temporary,
      workRoot: join(temporary, ".magazine", "004", "fixture", "work", "materialize"),
      git,
      clock: { now: () => new Date("2026-08-02T20:07:00.000Z") },
    });
    const engine = fixtureEngine();

    const first = await store.promote(engine, request());
    const retried = await store.promote(engine, request());
    const revisionDirectory = join(
      temporary,
      "durable/editions/004/articles/example/en/revisions",
      REVISION_ID,
    );

    assert.deepEqual(retried.result, first.result);
    assert.equal(await readFile(join(revisionDirectory, "manuscript.md"), "utf8"), "# Accepted manuscript\n");
    const manifest = await readFile(join(revisionDirectory, "manifest.yaml"), "utf8");
    assert.match(manifest, /promotion_id: promotion_durable-store/u);
    assert.match(manifest, /accepted_engine_artifact_ids:\n  - art_durable-manuscript/u);
    assert.match(first.result.manifestDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.equal(first.result.gitCommitOid, "a".repeat(40));
    assert.deepEqual(await readdir(join(temporary, ".magazine", "004", "fixture", "work", "materialize")), []);
    assert.equal(git.checkpoints.length, 2, "retry recovers the same PromotionId through the Git checkpoint seam");
    assert.deepEqual(Object.keys(first.result.gitBlobOids), [
      `durable/editions/004/articles/example/en/revisions/${REVISION_ID}/manifest.yaml`,
      `durable/editions/004/articles/example/en/revisions/${REVISION_ID}/manuscript.md`,
    ]);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("DurableStore preserves a renamed candidate for PromotionId crash recovery", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-durable-recovery-"));
  try {
    await writeInputRevision(temporary);
    const git = new FakeGit();
    git.failNextCheckpoint = true;
    const store = new DurableStore({
      repositoryRoot: temporary,
      workRoot: join(temporary, ".magazine", "004", "fixture", "work", "materialize"),
      git,
      clock: { now: () => new Date("2026-08-02T20:07:00.000Z") },
    });
    await assert.rejects(store.promote(fixtureEngine(), request()), /injected Git failure/u);

    const recovered = await store.promote(fixtureEngine(), request());
    assert.equal(recovered.result.promotionId, PROMOTION_ID);
    assert.equal((await readdir(join(
      temporary,
      "durable/editions/004/articles/example/en/revisions",
    ))).length, 1);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("DurableStore rejects parent drift, provenance drift, and a mismatched existing target", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-durable-conflict-"));
  try {
    await writeInputRevision(temporary);
    const store = new DurableStore({
      repositoryRoot: temporary,
      workRoot: join(temporary, ".magazine", "004", "fixture", "work", "materialize"),
      git: new FakeGit(),
      clock: { now: () => new Date("2026-08-02T20:07:00.000Z") },
    });
    await store.promote(fixtureEngine(), request());

    const nextRevision = "rev_20260802T200700001Z_cccccccccccc" as RevisionId;
    await assert.rejects(
      store.promote(fixtureEngine(), { ...request(), promotionId: "promotion_next" as PromotionId, revisionId: nextRevision }),
      (error: unknown) => error instanceof DurableStoreError && error.code === "DURABLE_PARENT_MISMATCH",
    );
    await assert.rejects(
      store.promote(fixtureEngine({ parents: [] }), request()),
      (error: unknown) => error instanceof DurableStoreError && error.code === "DURABLE_INPUT_MISMATCH",
    );

    const manifestPath = join(
      temporary,
      `durable/editions/004/articles/example/en/revisions/${REVISION_ID}/manifest.yaml`,
    );
    await writeFile(manifestPath, `${await readFile(manifestPath, "utf8")}tampered: true\n`, "utf8");
    await assert.rejects(
      store.promote(fixtureEngine(), request()),
      (error: unknown) => error instanceof DurableStoreError && error.code === "DURABLE_INTEGRITY_CONFLICT",
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("DurableStore rejects traversal, case, and Unicode aliases before materialization", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-durable-paths-"));
  try {
    await writeInputRevision(temporary);
    const store = new DurableStore({
      repositoryRoot: temporary,
      workRoot: join(temporary, ".magazine", "004", "fixture", "work", "materialize"),
      git: new FakeGit(),
    });
    for (const logicalId of ["../escape", "Example", "café", "cafe\u0301"]) {
      await assert.rejects(
        store.promote(fixtureEngine(), {
          ...request(),
          logicalItem: {
            kind: "article",
            editionId: "004",
            logicalId,
            language: "en",
          },
        }),
        /portable lowercase path component/u,
      );
    }
    await assert.rejects(
      store.promote(fixtureEngine(), {
        ...request(),
        inputRevisions: [
          request().inputRevisions[0]!,
          { ...request().inputRevisions[0]!, logicalId: "source" },
        ],
      }),
      /InputRevision references must be unique/u,
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("durable checkpoint worker materializes only its immutable RunEngine task", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-durable-worker-"));
  try {
    await writeInputRevision(temporary);
    const store = new DurableStore({
      repositoryRoot: temporary,
      workRoot: join(temporary, ".magazine", "004", "fixture", "work", "materialize"),
      git: new FakeGit(),
      clock: { now: () => new Date("2026-08-02T20:07:00.000Z") },
    });
    const task = request();
    const implementation = new DurableStoreCheckpointImplementation(fixtureEngine(), store);
    const answer = await implementation.checkpoint({
      offer: {
        runId: RUN_ID,
        taskArtifactId: "art_task" as ArtifactId,
      },
      artifacts: {
        readText: async () => JSON.stringify(task),
        readBytes: async () => Buffer.from(JSON.stringify(task)),
      },
      signal: new AbortController().signal,
    } as unknown as ExecutorContext);

    assert.equal(answer.contractVersion, "durable-checkpoint/1");
    assert.deepEqual(answer.result.revisionRef, { ...task.logicalItem, revisionId: REVISION_ID });

    await assert.rejects(
      implementation.checkpoint({
        offer: { runId: "run_wrong", taskArtifactId: "art_task" },
        artifacts: {
          readText: async () => JSON.stringify(task),
          readBytes: async () => Buffer.from(JSON.stringify(task)),
        },
        signal: new AbortController().signal,
      } as unknown as ExecutorContext),
      /does not match its offered run/u,
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

function request(): DurablePromotionRequest {
  return {
    schemaVersion: "durable-checkpoint-request/1",
    promotionId: PROMOTION_ID,
    revisionId: REVISION_ID,
    runId: RUN_ID,
    logicalItem: {
      kind: "article",
      editionId: "004",
      logicalId: "example",
      language: "en",
    },
    expectedParentRevisionId: null,
    acceptedArtifactIds: [MANUSCRIPT],
    decisionArtifactIds: [DECISION],
    inputRevisions: [{
      kind: "source_extraction",
      logicalId: "source",
      revisionId: INPUT_REVISION,
    }],
    inputArtifactIds: [INPUT],
  };
}

function fixtureEngine(
  overrides: { readonly parents?: ArtifactView["parents"] } = {},
): Parameters<DurableStore["promote"]>[0] {
  const manuscript: ArtifactView = {
    id: MANUSCRIPT,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "model",
    sizeBytes: 22,
    parents: overrides.parents ?? [{ artifactId: INPUT, relation: "source" }],
    producingRunId: RUN_ID,
    metadata: {},
    createdAt: "2026-08-02T20:06:50.000Z",
  };
  const decisionArtifact: ArtifactView = {
    id: DECISION,
    kind: "craft_decision",
    schemaVersion: "decision/1",
    mediaType: "application/json",
    origin: "human",
    sizeBytes: 2,
    parents: [],
    producingRunId: RUN_ID,
    metadata: {},
    createdAt: "2026-08-02T20:06:55.000Z",
  };
  const view = {
    id: RUN_ID,
    artifacts: [manuscript, decisionArtifact],
    decisions: [{
      id: "decision_durable",
      artifactId: DECISION,
      offerId: "offer_durable",
      choice: "approved",
      authority: "human",
      details: {},
      createdAt: "2026-08-02T20:06:55.000Z",
    }],
    offers: [{ id: "offer_durable", status: "answered" }],
  } as unknown as RunView;
  return {
    inspect: async () => view,
    readArtifact: async (artifactId) => {
      assert.equal(artifactId, MANUSCRIPT);
      return { artifact: manuscript, bytes: Buffer.from("# Accepted manuscript\n") };
    },
  };
}

async function writeInputRevision(root: string): Promise<void> {
  const directory = join(
    root,
    "inputs/sources/source/extractions",
    INPUT_REVISION,
  );
  await mkdir(directory, { recursive: true });
  const extracted = Buffer.from("# Committed source extraction\n", "utf8");
  await writeFile(join(directory, "extracted.md"), extracted);
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: "source_extraction",
    logical_id: "source",
    revision_id: INPUT_REVISION,
    created_at: "2026-08-01T01:02:03.004Z",
    parent_revision_id: null,
    files: [{
      path: "extracted.md",
      media_type: "text/markdown",
      sha256: `sha256:${createHash("sha256").update(extracted).digest("hex")}`,
      size_bytes: extracted.byteLength,
    }],
  }, { lineWidth: 0 }), "utf8");
}

class FakeGit implements DurableGit {
  readonly checkpoints: GitCheckpointRequest[] = [];
  failNextCheckpoint = false;

  async assertCommitted(_repositoryPaths: readonly string[]): Promise<void> {}

  async checkpoint(request: GitCheckpointRequest): Promise<GitRevisionBinding> {
    this.checkpoints.push(request);
    if (this.failNextCheckpoint) {
      this.failNextCheckpoint = false;
      throw new Error("injected Git failure");
    }
    return {
      commitOid: "a".repeat(40),
      blobOids: Object.fromEntries(request.repositoryPaths.map((path) => [path, "b".repeat(40)])),
    };
  }
}
