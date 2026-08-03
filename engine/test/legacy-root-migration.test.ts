import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import type { RevisionId } from "../contracts/index.ts";
import {
  LegacyRootMigrationError,
  lintLegacyRootReferences,
  planLegacyRootMigration,
  verifyLegacyRootMigrationPlan,
  type LegacyGitFile,
  type LegacyGitSnapshot,
} from "../migration/legacy-root-migration.ts";

test("legacy-root planner maps every committed byte and does not invent missing extractions", () => {
  const snapshot = corpusSnapshot();
  const plan = planLegacyRootMigration(snapshot, {
    migrationId: "legacy-four-root",
    allocateRevisionId: revisionAllocator(),
  });

  assert.equal(plan.files.length, snapshot.files.length);
  assert.equal(plan.files.filter((entry) => entry.source.path.startsWith("library/sources/")).length > 0, true);
  assert.equal(new Set(plan.files.map((entry) => entry.source.path)).size, snapshot.files.length);
  assert.equal(plan.files.filter((entry) => entry.targets[0]?.revisionKind === "source_capture").length, 36);
  assert.equal(plan.files.filter((entry) => entry.targets[0]?.revisionKind === "source_extraction").length, 25);
  assert.equal(plan.files.filter((entry) => entry.disposition === "archive_non_authoritative").length > 0, true);
  assert.deepEqual(
    plan.historicalCompositions.map((entry) => [entry.editionId, entry.compositionId, entry.state]),
    [
      ["001", "legacy-current-snapshot", "legacy-current-snapshot"],
      ["002", "legacy-current-snapshot", "legacy-current-snapshot"],
      ["003", "legacy-current-snapshot", "legacy-current-snapshot"],
      ["004", "fresh-v2", "reuse-existing"],
    ],
  );
  verifyLegacyRootMigrationPlan(plan);

  const replay = planLegacyRootMigration(snapshot, {
    migrationId: "legacy-four-root",
    allocatedRevisionIds: plan.allocatedRevisionIds,
    allocateRevisionId: () => {
      throw new Error("replay must not allocate a new RevisionId");
    },
  });
  assert.deepEqual(replay.allocatedRevisionIds, plan.allocatedRevisionIds);
});

test("legacy-root planner rejects alias, traversal, symlink, and unmapped-byte attempts", () => {
  const snapshot = corpusSnapshot();
  const invalid = (files: readonly LegacyGitFile[]) => ({
    ...snapshot,
    files,
    canonicalInventorySha256: snapshot.canonicalInventorySha256,
  } as LegacyGitSnapshot);
  assert.throws(
    () => planLegacyRootMigration(invalid([{ ...snapshot.files[0]!, path: "library/sources/A/record.yaml" }, {
      ...snapshot.files[1]!, path: "library/sources/a/record.yaml",
    }]), { migrationId: "legacy-four-root", allocateRevisionId: revisionAllocator() }),
    LegacyRootMigrationError,
  );
  assert.throws(
    () => planLegacyRootMigration(invalid([{ ...snapshot.files[0]!, path: "library/../prompts/x.md" }]), {
      migrationId: "legacy-four-root", allocateRevisionId: revisionAllocator(),
    }), LegacyRootMigrationError);
  assert.throws(
    () => planLegacyRootMigration(invalid([{ ...snapshot.files[0]!, mode: "120000" as "100644" }]), {
      migrationId: "legacy-four-root", allocateRevisionId: revisionAllocator(),
    }), LegacyRootMigrationError);
});

test("cutover lint permits provenance-only migration readers and blocks production rediscovery", () => {
  assert.deepEqual(lintLegacyRootReferences([
    { path: "engine/migration/legacy-root-migration.ts", text: '"library/sources/x"' },
    { path: "engine/run-engine/run-engine.ts", text: '"library/sources/x"' },
    { path: "engine/test/legacy-root-migration.test.ts", text: '"editions/001"' },
  ]), ["engine/run-engine/run-engine.ts"]);
});

function corpusSnapshot(): LegacyGitSnapshot {
  const files: LegacyGitFile[] = [];
  for (let index = 0; index < 36; index += 1) {
    const sourceId = `source-${String(index).padStart(2, "0")}`;
    files.push(file(`library/sources/${sourceId}/record.yaml`, index));
    if (index < 25) files.push(file(`library/sources/${sourceId}/extracted.md`, 100 + index));
  }
  for (const name of ["faithful-edit", "faithful-synthesis", "in-a-nutshell"]) {
    files.push(file(`prompts/${name}.md`, files.length));
  }
  files.push(file("prompts/README.md", files.length));
  for (const edition of ["001-old", "002-old", "003-old"]) {
    files.push(file(`editions/${edition}/edition.yaml`, files.length));
    files.push(file(`editions/${edition}/articles/a.md`, files.length));
    files.push(file(`editions/${edition}/manuscript/editorial.md`, files.length));
  }
  files.push(file("editions/004-the-systems-around-the-model/edition.yaml", files.length));
  files.push(file("editions/004-the-systems-around-the-model/art/cover-candidate-wildcard-v2.png", files.length));
  files.push(file("editions/005-unreleased/art/cover-candidates.yaml", files.length));
  files.push(file("editions/002-old/reviews/render.yaml", files.length));
  const canonical = inventoryDigest(files);
  return {
    sourceCommitOid: "a".repeat(40),
    files,
    canonicalInventorySha256: canonical,
  };
}

function file(path: string, seed: number): LegacyGitFile {
  const value = Buffer.from(`${path}:${seed}`);
  return {
    path,
    mode: "100644",
    blobOid: seed.toString(16).padStart(40, "0"),
    sha256: `sha256:${createHash("sha256").update(value).digest("hex")}`,
    sizeBytes: value.byteLength,
  };
}

function inventoryDigest(files: readonly LegacyGitFile[]): string {
  const canonical = [...files].sort((a, b) => a.path.localeCompare(b.path)).map((entry) =>
    `${entry.path}\0${entry.mode}\0${entry.blobOid}\0${entry.sha256}\0${entry.sizeBytes}\n`
  ).join("");
  return `sha256:${createHash("sha256").update(canonical).digest("hex")}`;
}

function revisionAllocator(): () => RevisionId {
  let value = 0;
  return () => {
    value += 1;
    const alphabet = "abcdefghijklmnopqrstuvwxyz234567";
    let remaining = value;
    let encoded = "";
    do {
      encoded = alphabet[remaining % alphabet.length]! + encoded;
      remaining = Math.floor(remaining / alphabet.length);
    } while (remaining > 0);
    const suffix = encoded.padStart(12, "a");
    return `rev_20260803T000000000Z_${suffix}` as RevisionId;
  };
}
