import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type { ArtifactId, ArtifactSeed, EditionRootRunSpec } from "../contracts/index.ts";
import { SqliteRunEngine, type FailpointController, type RunEngineFailpoint } from "../run-engine/index.ts";
import { prepareLegacyEditionReleaseSnapshot } from "./internal-schema-test-helper.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

test("v1 release-path snapshot preserves legacy authority, then offers a fresh durable backfill", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-v1-v2-migration-"));
  const databasePath = join(root, "run.sqlite");
  const artifactDirectory = join(root, "artifacts");
  let engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  try {
    const runId = (await engine.start(editionSpec())).runId;
    engine.close();
    prepareLegacyEditionReleaseSnapshot(databasePath, runId);

    engine = new SqliteRunEngine({ databasePath, artifactDirectory });
    const plan = await engine.planMigration({ runId, targetBundleVersion: "graph-execution@2" });
    assert.equal(plan.expectedFrom, "graph-execution@1");
    assert.equal(plan.targetBundleVersion, "graph-execution@2");
    assert.equal(plan.actors.length, 1);
    assert.equal(plan.actors[0]?.state, "awaiting_release_approval");
    await assert.rejects(engine.advance(runId), { code: "MIGRATION_REQUIRED" });

    const migrated = await engine.migrate({
      runId,
      expectedFrom: plan.expectedFrom,
      targetBundleVersion: plan.targetBundleVersion,
      expectedHeadEventId: plan.expectedHeadEventId,
      migrationId: "migration_edition4_v1_v2_fixture",
      idempotencyKey: "fixture-v1-v2",
    });
    assert.deepEqual(migrated, plan);
    const view = await engine.inspect(runId);
    const rootActor = view.actors.find((actor) => actor.parentActorId === undefined);
    assert.equal(rootActor?.state, "migration_durable_backfill");
    assert.equal(view.events.at(-1)?.type, "@@engine/snapshot_version_migrated");
    assert.equal(view.offers.every((offer) => offer.status !== "offered"), true);

    await engine.advance(runId);
    const backfilled = await engine.inspect(runId);
    const checkpoint = backfilled.offers.find((offer) => offer.status === "offered");
    assert.equal(checkpoint?.role, "durable_checkpoint");
    assert.equal(checkpoint?.state, "composition_accepted_pending_durable");

    const repeated = await engine.migrate({
      runId,
      expectedFrom: plan.expectedFrom,
      targetBundleVersion: plan.targetBundleVersion,
      expectedHeadEventId: plan.expectedHeadEventId,
      migrationId: "different-id-is-ignored-after-idempotency",
      idempotencyKey: "fixture-v1-v2",
    });
    assert.deepEqual(repeated, plan);
    engine.close();
    engine = new SqliteRunEngine({ databasePath, artifactDirectory });
    const reopened = await engine.inspect(runId);
    assert.equal(
      reopened.actors.find((actor) => actor.parentActorId === undefined)?.state,
      "composition_accepted_pending_durable",
    );
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("migration rollback retains the immutable v1 backup when its transaction fails", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-v1-v2-rollback-"));
  const databasePath = join(root, "run.sqlite");
  const artifactDirectory = join(root, "artifacts");
  let engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  try {
    const runId = (await engine.start(editionSpec())).runId;
    engine.close();
    prepareLegacyEditionReleaseSnapshot(databasePath, runId);
    engine = new SqliteRunEngine({
      databasePath,
      artifactDirectory,
      failpoints: new MigrationCommitFailure(),
    });
    const plan = await engine.planMigration({ runId, targetBundleVersion: "graph-execution@2" });
    await assert.rejects(
      engine.migrate({
        runId,
        expectedFrom: plan.expectedFrom,
        targetBundleVersion: plan.targetBundleVersion,
        expectedHeadEventId: plan.expectedHeadEventId,
        migrationId: "migration_rollback_fixture",
        idempotencyKey: "rollback-fixture",
      }),
      /migration commit failure/,
    );
    assert.equal((await engine.inspect(runId)).actors[0]?.state, "awaiting_release_approval");
    assert.deepEqual(
      await engine.planMigration({ runId, targetBundleVersion: "graph-execution@2" }),
      plan,
    );
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("migration plans are deterministic and reject stale heads, wrong bundles, and a competing migration", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-v1-v2-cas-"));
  const databasePath = join(root, "run.sqlite");
  const artifactDirectory = join(root, "artifacts");
  let engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  try {
    const runId = (await engine.start(editionSpec())).runId;
    engine.close();
    prepareLegacyEditionReleaseSnapshot(databasePath, runId);
    engine = new SqliteRunEngine({ databasePath, artifactDirectory });
    const plan = await engine.planMigration({ runId, targetBundleVersion: "graph-execution@2" });
    assert.deepEqual(
      await engine.planMigration({ runId, targetBundleVersion: "graph-execution@2" }),
      plan,
    );
    await assert.rejects(
      engine.migrate({
        runId,
        ...migrationInput(plan),
        expectedFrom: "graph-execution@2",
        migrationId: "wrong-bundle",
        idempotencyKey: "wrong-bundle",
      }),
      { code: "MIGRATION_CAS_MISMATCH" },
    );
    await assert.rejects(
      engine.migrate({
        runId,
        ...migrationInput(plan),
        expectedHeadEventId: "event_stale_head",
        migrationId: "stale-head",
        idempotencyKey: "stale-head",
      }),
      { code: "MIGRATION_CAS_MISMATCH" },
    );
    await engine.migrate({
      runId,
      ...migrationInput(plan),
      migrationId: "winner",
      idempotencyKey: "winner",
    });
    await assert.rejects(
      engine.migrate({
        runId,
        ...migrationInput(plan),
        migrationId: "competing-migration",
        idempotencyKey: "competing-migration",
      }),
      { code: "MIGRATION_CAS_MISMATCH" },
    );
    assert.notEqual((await engine.inspect(runId)).status, "complete");
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("migration supersedes claimed legacy authority and makes its claim stale", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-v1-v2-claim-"));
  const databasePath = join(root, "run.sqlite");
  const artifactDirectory = join(root, "artifacts");
  let engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  const authority = await AuthorityTestHarness.create(root);
  try {
    const runId = (await engine.start(editionSpec())).runId;
    const oldOffer = (await engine.inspect(runId)).offers.find((offer) => offer.status === "offered");
    assert.ok(oldOffer);
    const worker = await authority.workerFor(oldOffer, {
      principalId: "legacy-editor",
      authority: "human",
    });
    const claim = (await engine.prepareHumanDecision(oldOffer.id, worker)).claim;
    engine.close();
    prepareLegacyEditionReleaseSnapshot(databasePath, runId);
    engine = new SqliteRunEngine({ databasePath, artifactDirectory });
    const plan = await engine.planMigration({ runId, targetBundleVersion: "graph-execution@2" });
    await engine.migrate({
      runId,
      ...migrationInput(plan),
      migrationId: "claim-supersession",
      idempotencyKey: "claim-supersession",
    });
    const migratedOffer = (await engine.inspect(runId)).offers.find((offer) => offer.id === oldOffer.id);
    assert.equal(migratedOffer?.status, "superseded");
    await assert.rejects(engine.heartbeat(claim), { code: "STALE_CLAIM" });
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

class MigrationCommitFailure implements FailpointController {
  hit(name: RunEngineFailpoint): void {
    if (name === "snapshot_migration.before_commit") {
      throw new Error("migration commit failure");
    }
  }
}

function migrationInput(plan: {
  readonly expectedFrom: "graph-execution@1" | "graph-execution@2";
  readonly targetBundleVersion: "graph-execution@1" | "graph-execution@2";
  readonly expectedHeadEventId: string;
}) {
  return {
    expectedFrom: plan.expectedFrom,
    targetBundleVersion: plan.targetBundleVersion,
    expectedHeadEventId: plan.expectedHeadEventId,
  };
}

function editionSpec(): EditionRootRunSpec {
  const artifactIds = ["brief", "editorial", "rules", "render", "publication"] as const;
  const artifacts: ArtifactSeed[] = artifactIds.map((value) => ({
    id: value as ArtifactId,
    kind: "fixture",
    schemaVersion: "fixture/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: value },
  }));
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts,
    edition: {
      editionId: "migration-fixture",
      execution: { kind: "produce" },
      editionBrief: "brief" as ArtifactId,
      sources: [],
      articles: [],
      editorial: {
        editorialId: "opening",
        briefArtifact: "editorial" as ArtifactId,
        writingRules: "rules" as ArtifactId,
        modelPolicy: { default: { adapter: "test", model: "test" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: "render" as ArtifactId,
        rendererContractVersion: "renderer/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: "publication" as ArtifactId,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
}
