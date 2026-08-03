import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, lstat, mkdir, mkdtemp, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";

import type {
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  WorkerIdentity,
  WorkOfferView,
} from "../contracts/index.ts";
import type { RunId } from "../contracts/index.ts";
import { EditionRunLayout, editionRunName } from "../edition-run-layout.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { prepareLegacyEditionReleaseSnapshot } from "./internal-schema-test-helper.ts";

test("EditionRunLayout bootstraps one durable run under its createdAt name and reopens it", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-run-layout-"));
  const outputRoot = join(root, "output");
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot });
  try {
    const allocated = await layout.allocate(editionSpec());
    const view = await allocated.engine.inspect(allocated.runId);
    const expectedName = `${view.createdAt.replaceAll(":", "-")}--${view.id}`;

    assert.equal(allocated.runName, expectedName);
    assert.equal(allocated.internalDirectory, join(root, ".magazine", "004", expectedName));
    assert.equal(allocated.publicDirectory, join(outputRoot, "004", expectedName));
    assert.equal(layout.inputsRoot, join(root, "inputs"));
    assert.equal(layout.durableRoot, join(root, "durable"));
    await access(join(allocated.internalDirectory, "run.sqlite"));
    assert.deepEqual(await readdir(join(root, ".magazine", "004", ".creating")), []);
    await assert.rejects(access(allocated.publicDirectory));

    allocated.close();
    await assert.rejects(access(join(allocated.internalDirectory, "run.sqlite-wal")));
    await assert.rejects(access(join(allocated.internalDirectory, "run.sqlite-shm")));
    const reopened = await layout.open(allocated.runId);
    try {
      assert.equal(reopened.runName, expectedName);
      assert.equal((await reopened.engine.inspect(reopened.runId)).createdAt, view.createdAt);
    } finally {
      reopened.close();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("RunEngine lists compact persisted identities without direct database access", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-discovery-"));
  const engine = new SqliteRunEngine({
    databasePath: join(root, "run.sqlite"),
    artifactDirectory: join(root, "artifacts"),
  });
  try {
    const first = await engine.start(editionSpec());
    const second = await engine.start(editionSpec());
    const identities = await engine.listRuns();
    assert.deepEqual(
      identities.map((run) => run.id).sort(),
      [first.runId, second.runId].sort(),
    );
    assert.deepEqual(
      Object.keys(identities[0] ?? {}).sort(),
      [
        "createdAt",
        "headSequence",
        "id",
        "kind",
        "machineVersion",
        "metadata",
        "status",
        "updatedAt",
      ],
    );
    assert.ok(identities.every((run, index) =>
      index === 0 ||
      `${identities[index - 1]!.createdAt}:${identities[index - 1]!.id}` <=
        `${run.createdAt}:${run.id}`
    ));
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout reuses one canonical run for an immutable bootstrap allocation", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-allocation-"));
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  let preparations = 0;
  try {
    const first = await layout.allocate(async () => {
      preparations += 1;
      return editionSpec();
    }, { idempotencyKey: "rev_20260802T200641636Z_aaaaaaaaaaaa" });
    const firstId = first.runId;
    first.close();

    const repeated = await layout.allocate(async () => {
      preparations += 1;
      throw new Error("repeat must not prepare another run");
    }, { idempotencyKey: "rev_20260802T200641636Z_aaaaaaaaaaaa" });
    try {
      assert.equal(repeated.runId, firstId);
      assert.equal(preparations, 1);
      const listed = await layout.list();
      assert.equal(listed.length, 1);
      assert.equal(
        listed[0]?.metadata.editionRunAllocationKey,
        "rev_20260802T200641636Z_aaaaaaaaaaaa",
      );
    } finally {
      repeated.close();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout concurrent allocation and abandoned-lock recovery converge on one run", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-allocation-race-"));
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  const allocationKey = "rev_20260803T010203004Z_concurrent001";
  let preparations = 0;
  try {
    const [first, second] = await Promise.all([
      layout.allocate(async () => {
        preparations += 1;
        return editionSpec();
      }, { idempotencyKey: allocationKey }),
      layout.allocate(async () => {
        preparations += 1;
        return editionSpec();
      }, { idempotencyKey: allocationKey }),
    ]);
    try {
      assert.equal(first.runId, second.runId);
      assert.equal(preparations, 1);
      assert.equal((await layout.list()).length, 1);
    } finally {
      first.close();
      second.close();
    }

    const recoveryKey = "rev_20260803T010203004Z_recovery0001";
    const lockDigest = createHash("sha256").update(recoveryKey, "utf8").digest("hex");
    const abandoned = join(
      layout.internalEditionRoot,
      ".creating",
      `allocation-${lockDigest}.lock`,
    );
    await mkdir(abandoned, { recursive: true });
    await writeFile(join(abandoned, "owner.json"), `${JSON.stringify({
      schemaVersion: "edition-run-allocation-lock/1",
      allocationKey: recoveryKey,
      pid: 2_147_483_647,
      token: "abandoned-owner",
    })}\n`);
    const recovered = await layout.allocate(editionSpec(), { idempotencyKey: recoveryKey });
    recovered.close();
    assert.equal((await layout.list()).length, 2);
    assert.deepEqual(await readdir(join(layout.internalEditionRoot, ".creating")), []);

    const invalidKey = "rev_20260803T010203004Z_invalidlock01";
    const invalidDigest = createHash("sha256").update(invalidKey, "utf8").digest("hex");
    const invalidLock = join(
      layout.internalEditionRoot,
      ".creating",
      `allocation-${invalidDigest}.lock`,
    );
    await mkdir(invalidLock);
    await writeFile(join(invalidLock, "owner.json"), "{}\n");
    await assert.rejects(
      layout.allocate(editionSpec(), { idempotencyKey: invalidKey }),
      (error: unknown) => hasCode(error, "RUN_LAYOUT_ALLOCATION_LOCK_INVALID"),
    );
    await access(invalidLock);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout names sort by canonical UTC creation time and reject non-portable aliases", () => {
  const first = editionRunName({
    id: "run_00000000-0000-4000-8000-000000000001" as RunId,
    createdAt: "2026-08-02T20:06:41.636Z",
  });
  const second = editionRunName({
    id: "run_00000000-0000-4000-8000-000000000002" as RunId,
    createdAt: "2026-08-02T20:06:42.001Z",
  });
  assert.equal(
    first,
    "2026-08-02T20-06-41.636Z--run_00000000-0000-4000-8000-000000000001",
  );
  assert.ok(first < second);
  for (const editionKey of ["../004", "Edition4", "edición", "004/next"]) {
    assert.throws(
      () => new EditionRunLayout({ editionKey, outputRoot: "/tmp/output" }),
      { code: "RUN_LAYOUT_EDITION_KEY" },
    );
  }
  for (const runId of ["run_../escape", "RUN_case", "run_café"]) {
    assert.throws(
      () => editionRunName({ id: runId as RunId, createdAt: "2026-08-02T20:06:41.636Z" }),
      { code: "RUN_LAYOUT_RUN_ID" },
    );
  }
  for (const outputRoot of [
    "/tmp/mag-layout-project",
    "/tmp/mag-layout-project/inputs/export",
    "/tmp/mag-layout-project/durable/export",
    "/tmp/mag-layout-project/.magazine/export",
  ]) {
    assert.throws(
      () => new EditionRunLayout({
        editionKey: "004",
        repositoryRoot: "/tmp/mag-layout-project",
        outputRoot,
      }),
      { code: "RUN_LAYOUT_OUTPUT_COLLISION" },
    );
  }
  assert.throws(
    () => new EditionRunLayout({
      editionKey: "004",
      repositoryRoot: "/tmp/mag-layout-project",
      outputRoot: "/tmp/mag-layout-project/output/../inputs/export",
    }),
    { code: "RUN_LAYOUT_OUTPUT_TRAVERSAL" },
  );
  for (const outputRoot of [
    "/tmp/mag-layout-project/Output",
    "/tmp/mag-layout-project/salída",
  ]) {
    assert.throws(
      () => new EditionRunLayout({
        editionKey: "004",
        repositoryRoot: "/tmp/mag-layout-project",
        outputRoot,
      }),
      { code: "RUN_LAYOUT_OUTPUT_ROOT" },
    );
  }
});

test("EditionRunLayout keeps staged and renderer scratch private and cleans every outcome", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-run-scratch-"));
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  const allocated = await layout.allocate(editionSpec());
  const workDirectory = allocated.workDirectory;
  allocated.close();
  try {
    const result = await layout.withScratch(allocated.runId, async (scratch) => {
      assert.ok(scratch.stagedDirectory.startsWith(workDirectory));
      assert.ok(scratch.rendererWorkDirectory.startsWith(workDirectory));
      await access(scratch.stagedDirectory);
      await access(scratch.rendererWorkDirectory);
      return "complete";
    });
    assert.equal(result, "complete");
    await assert.rejects(access(workDirectory));

    await assert.rejects(
      layout.withScratch(allocated.runId, async () => {
        throw new Error("fixture failure");
      }),
      /fixture failure/,
    );
    await assert.rejects(access(workDirectory));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout discovers an exact legacy identity only after public artifact verification", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-run-discovery-"));
  const sourceDirectory = join(root, "legacy-run");
  const sourcePayload = join(root, "payload.txt");
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  await writeFile(sourcePayload, "discoverable artifact", "utf8");
  const source = new SqliteRunEngine({
    databasePath: join(sourceDirectory, "run.sqlite"),
    artifactDirectory: join(sourceDirectory, "artifacts"),
  });
  let runId: RunId;
  try {
    runId = (await source.start(editionSpec(sourcePayload))).runId;
  } finally {
    source.close();
  }
  try {
    const missing = await layout.discover(join(root, "absent"), runId);
    assert.equal(missing.databasePresent, false);
    assert.equal(missing.identityMatch, false);
    await assert.rejects(access(join(root, "absent")));

    const mismatch = await layout.discover(
      sourceDirectory,
      "run_00000000-0000-4000-8000-000000000099" as RunId,
    );
    assert.equal(mismatch.runs.length, 1);
    assert.equal(mismatch.identityMatch, false);

    const discovered = await layout.discover(sourceDirectory, runId);
    assert.equal(discovered.identityMatch, true);
    assert.equal(discovered.verifiedRunName?.endsWith(`--${runId}`), true);
    assert.equal(discovered.verifiedArtifactIds?.length, 1);
    assert.ok(discovered.artifactFileCount > 0);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout relocates a whole run atomically, reopens its artifact store, and is idempotent", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-run-relocate-"));
  const sourceDirectory = join(root, "legacy-run");
  const sourcePayload = join(root, "payload.txt");
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  await writeFile(sourcePayload, "portable artifact bytes", "utf8");
  const source = new SqliteRunEngine({
    databasePath: join(sourceDirectory, "run.sqlite"),
    artifactDirectory: join(sourceDirectory, "artifacts"),
  });
  let runId: RunId;
  try {
    runId = (await source.start(editionSpec(sourcePayload))).runId;
  } finally {
    source.close();
  }
  try {
    const relocated = await layout.relocate(sourceDirectory, runId);
    const destination = relocated.internalDirectory;
    try {
      assert.equal((await relocated.engine.inspect(runId)).id, runId);
      assert.equal(await relocated.engine.readText(FILE_ARTIFACT_ID), "portable artifact bytes");
      await assert.rejects(access(sourceDirectory));
    } finally {
      relocated.close();
    }

    const repeated = await layout.relocate(sourceDirectory, runId);
    try {
      assert.equal(repeated.internalDirectory, destination);
      assert.equal(await repeated.engine.readText(FILE_ARTIFACT_ID), "portable artifact bytes");
    } finally {
      repeated.close();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("RunEngine migration fence rejects active work and checkpoints WAL under exact CAS", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-migration-fence-"));
  const home = join(root, "legacy-run");
  const engine = new SqliteRunEngine({
    databasePath: join(home, "run.sqlite"),
    artifactDirectory: join(home, "artifacts"),
  });
  try {
    const runId = (await engine.start(editionSpec())).runId;
    const view = await engine.inspect(runId);
    const head = view.events.find((event) => event.sequence === view.headSequence)!;
    await assert.rejects(
      engine.acquireMigrationFence({
        runId,
        expectedHeadSequence: view.headSequence - 1,
        expectedHeadEventId: head.id,
        idempotencyKey: "stale-fence",
      }),
      (error: unknown) => hasCode(error, "MIGRATION_FENCE_CAS_MISMATCH"),
    );

    const offer = requiredOfferedWork(view);
    const claim = await engine.claim(offer.id, workerFor(offer, "active-migration-worker"));
    await assert.rejects(
      engine.acquireMigrationFence({
        runId,
        expectedHeadSequence: view.headSequence,
        expectedHeadEventId: head.id,
        idempotencyKey: "active-work-fence",
      }),
      (error: unknown) => hasCode(error, "MIGRATION_ACTIVE_WORK"),
    );
    await engine.fail(claim, { classification: "canceled", message: "finish fence fixture" });
    const settled = await engine.inspect(runId);
    const settledHead = settled.events.find((event) => event.sequence === settled.headSequence)!;
    assert.ok((await lstat(join(home, "run.sqlite-wal"))).size > 0);
    const fence = await engine.acquireMigrationFence({
      runId,
      expectedHeadSequence: settled.headSequence,
      expectedHeadEventId: settledHead.id,
      idempotencyKey: "checkpoint-fence",
    });
    const checkpoint = await engine.checkpointMigrationFence(fence);
    assert.equal(checkpoint.busy, 0);
    assert.equal(checkpoint.log, checkpoint.checkpointed);
    assert.equal((await lstat(join(home, "run.sqlite-wal"))).size, 0);
    await engine.releaseMigrationFence(fence);
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout relocation fence rejects a concurrent worker from an already-open engine", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-relocate-worker-race-"));
  const sourceDirectory = join(root, "legacy-run");
  let announceFence!: () => void;
  let continueRelocation!: () => void;
  const fenced = new Promise<void>((resolve) => {
    announceFence = resolve;
  });
  const proceed = new Promise<void>((resolve) => {
    continueRelocation = resolve;
  });
  const layout = new EditionRunLayout({
    editionKey: "004",
    outputRoot: join(root, "output"),
    migrationHook: async (point) => {
      if (point === "relocate.after_fence") {
        announceFence();
        await proceed;
      }
    },
  });
  const creator = new SqliteRunEngine({
    databasePath: join(sourceDirectory, "run.sqlite"),
    artifactDirectory: join(sourceDirectory, "artifacts"),
  });
  const runId = (await creator.start(editionSpec())).runId;
  creator.close();
  const worker = new SqliteRunEngine({
    databasePath: join(sourceDirectory, "run.sqlite"),
    artifactDirectory: join(sourceDirectory, "artifacts"),
  });
  try {
    const relocation = layout.relocate(sourceDirectory, runId);
    await fenced;
    const offer = requiredOfferedWork(await worker.inspect(runId));
    await assert.rejects(
      worker.claim(offer.id, workerFor(offer, "concurrent-worker")),
      (error: unknown) => hasCode(error, "RUN_MIGRATION_FENCED"),
    );
    worker.close();
    continueRelocation();
    const relocated = await relocation;
    try {
      assert.equal((await relocated.engine.inspect(runId)).id, runId);
    } finally {
      relocated.close();
    }
  } finally {
    continueRelocation();
    try {
      worker.close();
    } catch {
      // The successful cutover may already have closed and removed its fenced backup.
    }
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout rolls an installed clone back and releases its source fence", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-relocate-cutover-rollback-"));
  const sourceDirectory = join(root, "legacy-run");
  const layout = new EditionRunLayout({
    editionKey: "004",
    outputRoot: join(root, "output"),
    migrationHook: (point) => {
      if (point === "relocate.after_candidate_install") throw new Error("cutover fixture failure");
    },
  });
  const source = new SqliteRunEngine({
    databasePath: join(sourceDirectory, "run.sqlite"),
    artifactDirectory: join(sourceDirectory, "artifacts"),
  });
  const runId = (await source.start(editionSpec())).runId;
  const view = await source.inspect(runId);
  source.close();
  const destination = layout.pathsFor(view).internalDirectory;
  try {
    await assert.rejects(layout.relocate(sourceDirectory, runId), /cutover fixture failure/u);
    await access(sourceDirectory);
    await assert.rejects(access(destination));
    assert.deepEqual(await readdir(join(layout.internalEditionRoot, ".migrating")), []);

    const restored = new SqliteRunEngine({
      databasePath: join(sourceDirectory, "run.sqlite"),
      artifactDirectory: join(sourceDirectory, "artifacts"),
    });
    try {
      const restoredView = await restored.inspect(runId);
      const offer = requiredOfferedWork(restoredView);
      const claim = await restored.claim(offer.id, workerFor(offer, "restored-worker"));
      assert.equal(claim.offerId, offer.id);
    } finally {
      restored.close();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout rolls a failed post-move artifact verification back to the source", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-run-rollback-"));
  const sourceDirectory = join(root, "legacy-run");
  const sourcePayload = join(root, "payload.txt");
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  await writeFile(sourcePayload, "x".repeat(10_000), "utf8");
  const source = new SqliteRunEngine({
    databasePath: join(sourceDirectory, "run.sqlite"),
    artifactDirectory: join(sourceDirectory, "artifacts"),
  });
  let runId: RunId;
  try {
    runId = (await source.start(editionSpec(sourcePayload))).runId;
  } finally {
    source.close();
  }
  await rm(join(sourceDirectory, "artifacts", "artifacts", FILE_ARTIFACT_ID, "payload"));
  try {
    await assert.rejects(layout.relocate(sourceDirectory, runId));
    await access(sourceDirectory);
    await assert.rejects(access(join(layout.internalEditionRoot, `anything--${runId}`)));
    const reopened = new SqliteRunEngine({
      databasePath: join(sourceDirectory, "run.sqlite"),
      artifactDirectory: join(sourceDirectory, "artifacts"),
    });
    try {
      assert.equal((await reopened.inspect(runId)).id, runId);
    } finally {
      reopened.close();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("EditionRunLayout migrates a cloned v1 run before atomically cutting over its relative artifact store", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-run-migration-"));
  const payload = join(root, "relative-artifact.txt");
  const layout = new EditionRunLayout({ editionKey: "004", outputRoot: join(root, "output") });
  await writeFile(payload, "kept through migration", "utf8");
  try {
    const allocated = await layout.allocate(editionSpec(payload));
    const { runId, internalDirectory } = allocated;
    allocated.close();
    prepareLegacyEditionReleaseSnapshot(join(internalDirectory, "run.sqlite"), runId);

    const legacy = await layout.open(runId);
    const plan = await legacy.engine.planMigration({
      runId,
      targetBundleVersion: "graph-execution@2",
    });
    legacy.close();

    const migrated = await layout.migrate(runId, {
      expectedFrom: plan.expectedFrom,
      targetBundleVersion: plan.targetBundleVersion,
      expectedHeadEventId: plan.expectedHeadEventId,
      migrationId: "layout-v1-v2",
      idempotencyKey: "layout-v1-v2",
    });
    assert.equal(migrated.plan.runId, runId);
    const reopened = await layout.open(runId);
    try {
      assert.equal(await reopened.engine.readText(FILE_ARTIFACT_ID), "kept through migration");
      assert.equal(
        (await reopened.engine.inspect(runId)).offers.some(
          (offer) => offer.status === "offered" && offer.role === "durable_checkpoint",
        ),
        true,
      );
    } finally {
      reopened.close();
    }
    assert.deepEqual(await readdir(join(layout.internalEditionRoot, ".migrating")), []);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

const FILE_ARTIFACT_ID = "layout-file-artifact" as ArtifactId;

function requiredOfferedWork(view: Awaited<ReturnType<SqliteRunEngine["inspect"]>>): WorkOfferView {
  const offer = view.offers.find((candidate) => candidate.status === "offered");
  assert.ok(offer, `run ${view.id} must expose offered work`);
  return offer;
}

function workerFor(offer: WorkOfferView, principalId: string): WorkerIdentity {
  return {
    principalId,
    authority: offer.allowedWorkerCapabilities.includes("human") ? "human" : "model",
    capabilities: offer.allowedWorkerCapabilities,
  };
}

function hasCode(error: unknown, code: string): boolean {
  return error instanceof Error && "code" in error &&
    (error as Error & { readonly code: unknown }).code === code;
}

function editionSpec(filePayload?: string): EditionRootRunSpec {
  const id = (value: string): ArtifactId => value as ArtifactId;
  const editionBrief = id("layout-edition-brief");
  const editorialBrief = id("layout-editorial-brief");
  const writingRules = id("layout-writing-rules");
  const renderProfile = id("layout-render-profile");
  const publication = id("layout-publication");
  const artifacts: ArtifactSeed[] = [
    editionBrief,
    editorialBrief,
    writingRules,
    renderProfile,
    publication,
  ].map((artifactId) => ({
    id: artifactId,
    kind: "fixture",
    schemaVersion: "fixture/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: artifactId },
  }));
  if (filePayload !== undefined) {
    artifacts.push({
      id: FILE_ARTIFACT_ID,
      kind: "fixture_file",
      schemaVersion: "fixture/1",
      mediaType: "text/plain",
      origin: "imported",
      payload: { kind: "file", path: filePayload },
    });
  }
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts,
    edition: {
      editionId: "layout-fixture",
      execution: { kind: "produce" },
      editionBrief,
      sources: [],
      articles: [],
      editorial: {
        editorialId: "opening",
        briefArtifact: editorialBrief,
        writingRules,
        modelPolicy: { default: { adapter: "test", model: "test" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: renderProfile,
        rendererContractVersion: "renderer/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: publication,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
}
