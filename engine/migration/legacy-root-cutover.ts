import { createHash } from "node:crypto";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";

import { parse, stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import { newRevisionId, parseRevisionId } from "../durable/revision-id.ts";
import { validateInputRevisionTree } from "../durable/input-revision.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  assertLegacyRootBaseline,
  planLegacyRootMigration,
  readExactExistingRevisionBindings,
  readLegacyGitSnapshot,
  verifyLegacyRootMigrationPlan,
  type LegacyRootMigrationPlan,
} from "./legacy-root-migration.ts";

const MIGRATION_ID = "legacy-four-root";

async function main(): Promise<void> {
  const [command, sourceCommit, explicitRevision] = process.argv.slice(2);
  if (command !== "plan" || sourceCommit === undefined) {
    throw new Error("usage: node engine/migration/legacy-root-cutover.ts plan <source-commit> [plan-revision-id]");
  }
  const repositoryRoot = process.cwd();
  const snapshot = await readLegacyGitSnapshot(repositoryRoot, sourceCommit);
  assertLegacyRootBaseline(snapshot);
  const bindingAudit = await readExactExistingRevisionBindings(repositoryRoot, snapshot);
  if (bindingAudit.conflicts.length > 0) {
    throw new Error(`existing revision binding conflicts:\n${bindingAudit.conflicts.join("\n")}`);
  }
  const revisionId = explicitRevision === undefined ? newRevisionId() : parseRevisionId(explicitRevision);
  const existingPlan = await existingPlanRevision(repositoryRoot);
  if (existingPlan !== undefined) {
    if (explicitRevision !== undefined && existingPlan !== revisionId) {
      throw new Error(`migration plan already exists as ${existingPlan}`);
    }
    const plan = await readPlan(repositoryRoot, existingPlan);
    verifyLegacyRootMigrationPlan(plan);
    report(existingPlan, plan, bindingAudit.boundSourcePaths, true);
    return;
  }
  const plan = planLegacyRootMigration(snapshot, {
    migrationId: MIGRATION_ID,
    allocateRevisionId: () => newRevisionId(),
    existingBindingsBySourcePath: bindingAudit.bindingsBySourcePath,
  });
  verifyLegacyRootMigrationPlan(plan);
  if (Object.keys(plan.allocatedRevisionIds).length !== 324) {
    throw new Error(`migration plan must allocate/bind exactly 324 slots, found ${Object.keys(plan.allocatedRevisionIds).length}`);
  }
  await writePlanRevision(repositoryRoot, revisionId, plan);
  report(revisionId, plan, bindingAudit.boundSourcePaths, false);
}

async function writePlanRevision(
  repositoryRoot: string,
  revisionId: RevisionId,
  plan: LegacyRootMigrationPlan,
): Promise<void> {
  const ref: InputRevisionRef = {
    kind: "migration_plan",
    logicalId: MIGRATION_ID,
    revisionId,
  };
  const destination = join(
    resolve(repositoryRoot),
    "inputs",
    "migrations",
    MIGRATION_ID,
    "revisions",
    revisionId,
  );
  if (await exists(destination)) throw new Error(`migration plan target already exists: ${destination}`);
  const candidate = await mkdtemp(join(tmpdir(), "mag-legacy-plan-"));
  try {
    const detachedPlan = JSON.parse(JSON.stringify(plan)) as LegacyRootMigrationPlan;
    const inventory = Buffer.from(stringify(detachedPlan, { lineWidth: 0, sortMapEntries: true }), "utf8");
    const manifest = Buffer.from(stringify({
      schema_version: 1,
      revision_kind: "migration_plan",
      logical_id: MIGRATION_ID,
      revision_id: revisionId,
      created_at: revisionInstant(revisionId),
      parent_revision_id: null,
      migration_id: MIGRATION_ID,
      files: [{
        path: "inventory.yaml",
        media_type: "application/yaml",
        sha256: sha256(inventory),
        size_bytes: inventory.byteLength,
        generated_by_migration: {
          basis: `complete immutable inventory and disposition plan for ${plan.sourceSnapshot.sourceCommitOid}`,
        },
      }],
    }, { lineWidth: 0 }), "utf8");
    await writeFile(join(candidate, "inventory.yaml"), inventory, { flag: "wx", mode: 0o600 });
    await writeFile(join(candidate, "manifest.yaml"), manifest, { flag: "wx", mode: 0o600 });
    await validateInputRevisionTree(candidate, ref);
    await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
    await rename(candidate, destination);
    await validateInputRevisionTree(destination, ref);
  } finally {
    await rm(candidate, { recursive: true, force: true });
  }
}

async function existingPlanRevision(repositoryRoot: string): Promise<RevisionId | undefined> {
  const parent = join(repositoryRoot, "inputs", "migrations", MIGRATION_ID, "revisions");
  try {
    const { readdir } = await import("node:fs/promises");
    const entries = (await readdir(parent, { withFileTypes: true })).filter((entry) => entry.isDirectory());
    if (entries.length > 1) throw new Error("multiple legacy migration plan revisions exist");
    return entries[0] === undefined ? undefined : parseRevisionId(entries[0].name);
  } catch (error) {
    if (isMissing(error)) return undefined;
    throw error;
  }
}

async function readPlan(repositoryRoot: string, revisionId: RevisionId): Promise<LegacyRootMigrationPlan> {
  const path = join(repositoryRoot, "inputs", "migrations", MIGRATION_ID, "revisions", revisionId, "inventory.yaml");
  return parse(await readFile(path, "utf8")) as LegacyRootMigrationPlan;
}

function revisionInstant(revisionId: RevisionId): string {
  const match = /^rev_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z_/u.exec(revisionId);
  if (match === null) throw new Error(`cannot read RevisionId time: ${revisionId}`);
  return `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}.${match[7]}Z`;
}

function report(
  revisionId: RevisionId,
  plan: LegacyRootMigrationPlan,
  boundSourcePaths: number,
  existing: boolean,
): void {
  const count = (name: string) => plan.files.filter((entry) => entry.disposition === name).length;
  process.stdout.write(`${JSON.stringify({
    status: existing ? "existing" : "created",
    migrationId: plan.migrationId,
    planRevisionId: revisionId,
    sourceCommitOid: plan.sourceSnapshot.sourceCommitOid,
    inventorySha256: plan.sourceSnapshot.canonicalInventorySha256,
    fileCount: plan.sourceSnapshot.files.length,
    sizeBytes: plan.sourceSnapshot.files.reduce((total, file) => total + file.sizeBytes, 0),
    revisionSlots: Object.keys(plan.allocatedRevisionIds).length,
    boundSourcePaths,
    dispositions: {
      reuseExisting: count("reuse_existing"),
      importExact: count("import_exact"),
      archiveNonAuthoritative: count("archive_non_authoritative"),
      retireHousekeeping: count("retire_housekeeping"),
    },
  }, null, 2)}\n`);
}

function sha256(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if (isMissing(error)) return false;
    throw error;
  }
}

function isMissing(error: unknown): boolean {
  return typeof error === "object" && error !== null && "code" in error && error.code === "ENOENT";
}

await main();
