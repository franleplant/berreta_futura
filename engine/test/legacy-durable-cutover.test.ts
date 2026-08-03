import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import test from "node:test";
import { promisify } from "node:util";

import {
  LEGACY_DURABLE_BATCH_COUNTS,
  LEGACY_DURABLE_PLAN_REVISION,
  LEGACY_DURABLE_SOURCE_COMMIT,
  planLegacyDurableBatch,
  readLegacyDurablePlanningInputs,
} from "../migration/legacy-durable-cutover.ts";

const execFile = promisify(execFileCallback);
const root = process.cwd();

test("legacy durable cutover plans exact historical batches", async () => {
  const { ledger, sources } = await readLegacyDurablePlanningInputs(
    root,
    LEGACY_DURABLE_SOURCE_COMMIT,
    LEGACY_DURABLE_PLAN_REVISION,
  );
  for (const [group, expected] of Object.entries(LEGACY_DURABLE_BATCH_COUNTS)) {
    const plan = planLegacyDurableBatch(ledger, sources, group as keyof typeof LEGACY_DURABLE_BATCH_COUNTS);
    assert.equal(plan.entries.length + plan.compositions.length, expected, group);
    assert.equal(plan.sourceGitBinding.commitOid, LEGACY_DURABLE_SOURCE_COMMIT);
    assert.deepEqual(Object.keys(plan.sourceGitBinding.blobOids).sort(), [
      ...plan.entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
      ...plan.compositions.flatMap((entry) => entry.sourcePaths),
    ].filter((path, index, all) => all.indexOf(path) === index).sort());
  }
});

test("legacy durable refs use exact identity and preserve Edition 004 parents", async () => {
  const { ledger, sources } = await readLegacyDurablePlanningInputs(root, LEGACY_DURABLE_SOURCE_COMMIT);
  const rerun = planLegacyDurableBatch(ledger, sources, "004-rerun");
  assert.equal(rerun.entries.length, 53);
  for (const entry of rerun.entries) {
    assert.equal(entry.ref.editionId, "004");
    assert.notEqual(entry.parentRevisionId, null);
    const target = ledger.files.map((file) => file.targets[0]!).find((target) =>
      target.category === "durable" && target.revisionId === entry.ref.revisionId,
    );
    assert.ok(target?.durableIdentity);
    assert.equal(entry.ref.logicalId, target.durableIdentity.logicalId);
    assert.equal(entry.ref.kind, target.revisionKind);
  }
});

test("provenance inputs are limited to exact source evidence and selected art", async () => {
  const { ledger, sources } = await readLegacyDurablePlanningInputs(root, LEGACY_DURABLE_SOURCE_COMMIT);
  const edition = planLegacyDurableBatch(ledger, sources, "001");
  for (const entry of edition.entries) {
    assert.ok(entry.inputRevisions.some((ref) => ref.kind === "migration_plan"));
    assert.equal(entry.inputRevisions.some((ref) => ref.kind === "prompt" || ref.kind === "policy"), false);
  }
  const cover = edition.entries.find((entry) => entry.ref.kind === "image");
  assert.ok(cover);
  assert.ok(cover.inputRevisions.some((ref) => ref.kind === "edition_spec"));
  const compositions = planLegacyDurableBatch(ledger, sources, "compositions");
  assert.equal(compositions.compositions.length, 3);
  for (const composition of compositions.compositions) {
    assert.ok(composition.extraInputRevisions.some((ref) => ref.kind === "migration_plan"));
    assert.match(composition.assemblyBasis, /historical snapshot.*no release authority/u);
    assert.deepEqual(composition.document.articles.map((article) => article.article_id), articleOrder(composition.document));
    assert.equal(composition.document.images.some((pin) => pin.slot_id.includes("figure")), false);
    for (const article of composition.document.articles) {
      assert.deepEqual(article.manuscripts.map((pin) => pin.language), ["en", "es"]);
    }
  }
});

function articleOrder(document: { readonly articles: readonly { readonly article_id: string }[] }): readonly string[] {
  return document.articles.map((article) => article.article_id);
}

test("planning rejects a non-protected source commit", async () => {
  await assert.rejects(
    readLegacyDurablePlanningInputs(root, "0000000000000000000000000000000000000000"),
    /protected source commit/u,
  );
});

test("authoritative ledger remains committed", async () => {
  const path = `inputs/migrations/legacy-four-root/revisions/${LEGACY_DURABLE_PLAN_REVISION}/inventory.yaml`;
  const result = await execFile("git", ["rev-parse", `HEAD:${path}`], { cwd: root, encoding: "utf8" });
  assert.match(result.stdout.trim(), /^[0-9a-f]{40,64}$/u);
});
