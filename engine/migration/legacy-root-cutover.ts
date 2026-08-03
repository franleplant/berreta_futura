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
import {
  materializeLegacyInputs,
  type LegacyInputMigrationPlan,
} from "../durable/legacy-input-migration.ts";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  assertLegacyRootBaseline,
  planLegacyRootMigration,
  readExactExistingRevisionBindings,
  readLegacyDurableIdentities,
  readLegacyGitSnapshot,
  verifyLegacyRootMigrationPlan,
  type LegacyRootMigrationPlan,
} from "./legacy-root-migration.ts";

const MIGRATION_ID = "legacy-four-root";

async function main(): Promise<void> {
  const [command, sourceCommit, argument, group] = process.argv.slice(2);
  if (sourceCommit === undefined) throw usage();
  if (command === "materialize-inputs") {
    if (argument === undefined || group === undefined) throw usage();
    await materializeInputGroup(process.cwd(), sourceCommit, parseRevisionId(argument), group);
    return;
  }
  if (command === "successor-plan") {
    if (argument === undefined) throw usage();
    await createSuccessorPlan(process.cwd(), sourceCommit, parseRevisionId(argument), group);
    return;
  }
  if (command !== "plan") throw usage();
  const explicitRevision = argument;
  const repositoryRoot = process.cwd();
  const snapshot = await readLegacyGitSnapshot(repositoryRoot, sourceCommit);
  assertLegacyRootBaseline(snapshot);
  const bindingAudit = await readExactExistingRevisionBindings(repositoryRoot, snapshot);
  if (bindingAudit.conflicts.length > 0) {
    throw new Error(`existing revision binding conflicts:\n${bindingAudit.conflicts.join("\n")}`);
  }
  const durableIdentities = await readLegacyDurableIdentities(
    repositoryRoot,
    snapshot,
    bindingAudit.durableIdentitiesBySourcePath,
  );
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
    durableIdentitiesBySourcePath: durableIdentities,
  });
  verifyLegacyRootMigrationPlan(plan);
  if (Object.keys(plan.allocatedRevisionIds).length !== 324) {
    throw new Error(`migration plan must allocate/bind exactly 324 slots, found ${Object.keys(plan.allocatedRevisionIds).length}`);
  }
  await writePlanRevision(repositoryRoot, revisionId, plan, null);
  report(revisionId, plan, bindingAudit.boundSourcePaths, false);
}

async function createSuccessorPlan(
  repositoryRoot: string,
  sourceCommit: string,
  parentPlanRevisionId: RevisionId,
  explicitRevision?: string,
): Promise<void> {
  const parent = await readPlan(repositoryRoot, parentPlanRevisionId);
  verifyLegacyRootMigrationPlan(parent);
  if (parent.sourceSnapshot.sourceCommitOid !== sourceCommit) throw new Error("parent plan source commit mismatch");
  const snapshot = await readLegacyGitSnapshot(repositoryRoot, sourceCommit);
  assertLegacyRootBaseline(snapshot);
  const bindings = await readExactExistingRevisionBindings(repositoryRoot, snapshot);
  if (bindings.conflicts.length > 0) throw new Error(`existing revision binding conflicts:\n${bindings.conflicts.join("\n")}`);
  const durableIdentities = await readLegacyDurableIdentities(
    repositoryRoot,
    snapshot,
    bindings.durableIdentitiesBySourcePath,
  );
  const revisionId = explicitRevision === undefined ? newRevisionId() : parseRevisionId(explicitRevision);
  const next = {
    ...planLegacyRootMigration(snapshot, {
      migrationId: MIGRATION_ID,
      allocatedRevisionIds: parent.allocatedRevisionIds,
      allocateRevisionId: () => newRevisionId(),
      existingBindingsBySourcePath: bindings.bindingsBySourcePath,
      durableIdentitiesBySourcePath: durableIdentities,
      preferExactExistingBindings: true,
    }),
    supersedesPlanRevisionId: parentPlanRevisionId,
  } satisfies LegacyRootMigrationPlan;
  verifyLegacyRootMigrationPlan(next);
  if (Object.keys(next.allocatedRevisionIds).length !== 324) throw new Error("successor plan slot count drifted");
  await writePlanRevision(repositoryRoot, revisionId, next, parentPlanRevisionId);
  report(revisionId, next, bindings.boundSourcePaths, false);
}

async function materializeInputGroup(
  repositoryRoot: string,
  sourceCommit: string,
  planRevisionId: RevisionId,
  group: string,
): Promise<void> {
  if (!["source-1", "source-2", "misc", "archive"].includes(group)) throw usage();
  const plan = await readPlan(repositoryRoot, planRevisionId);
  verifyLegacyRootMigrationPlan(plan);
  if (plan.sourceSnapshot.sourceCommitOid !== sourceCommit) throw new Error("plan source commit does not match command");
  assertLegacyRootBaseline(plan.sourceSnapshot);
  const imported = plan.files.filter((entry) => entry.disposition !== "reuse_existing");
  const sourceSlots = [...new Set(imported
    .filter((entry) => entry.targets[0]?.revisionKind === "source_capture" || entry.targets[0]?.revisionKind === "source_extraction")
    .map((entry) => entry.targets[0]!.revisionSlot))].sort();
  const midpoint = Math.ceil(sourceSlots.length / 2);
  const selectedSlots = new Set(group === "source-1" ? sourceSlots.slice(0, midpoint) :
    group === "source-2" ? sourceSlots.slice(midpoint) :
      imported.filter((entry) => group === "archive"
        ? entry.targets[0]?.revisionKind === "migration_archive"
        : entry.targets[0]?.category === "input" &&
          entry.targets[0]?.revisionKind !== "source_capture" &&
          entry.targets[0]?.revisionKind !== "source_extraction" &&
          entry.targets[0]?.revisionKind !== "migration_archive")
        .map((entry) => entry.targets[0]!.revisionSlot));
  const selected = imported.filter((entry) => selectedSlots.has(entry.targets[0]!.revisionSlot));
  if (selected.length === 0) throw new Error(`input migration group ${group} is empty`);
  const bySlot = new Map<string, typeof selected>();
  for (const entry of selected) {
    const slot = entry.targets[0]!.revisionSlot;
    const current = bySlot.get(slot) ?? [];
    bySlot.set(slot, [...current, entry]);
  }
  const inputPlan: LegacyInputMigrationPlan = {
    schemaVersion: "legacy-input-migration/1",
    migrationId: `${MIGRATION_ID}-${group}`,
    sourceGitBinding: {
      commitOid: sourceCommit,
      blobOids: Object.fromEntries(selected.map((entry) => [entry.source.path, entry.source.blobOid])),
    },
    entries: [...bySlot.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([slot, entries]) => ({
      ref: inputRef(entries[0]!.targets[0]!),
      createdAt: revisionInstant(entries[0]!.targets[0]!.revisionId),
      parentRevisionId: null,
      files: entries.map((entry) => ({
        sourcePath: entry.source.path,
        targetPath: entry.targets[0]!.payloadPath,
        mediaType: mediaType(entry.source.path),
      })),
    })),
  };
  const workRoot = await mkdtemp(join(tmpdir(), `mag-${MIGRATION_ID}-${group}-`));
  try {
    const result = await materializeLegacyInputs(
      repositoryRoot,
      workRoot,
      inputPlan,
      new GitCliDurableGit(repositoryRoot),
    );
    process.stdout.write(`${JSON.stringify({
      status: "materialized",
      group,
      revisions: result.revisions.length,
      repositoryFiles: result.repositoryPaths.length,
      repositoryPaths: result.repositoryPaths,
    }, null, 2)}\n`);
  } finally {
    await rm(workRoot, { recursive: true, force: true });
  }
}

async function writePlanRevision(
  repositoryRoot: string,
  revisionId: RevisionId,
  plan: LegacyRootMigrationPlan,
  parentRevisionId: RevisionId | null,
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
      parent_revision_id: parentRevisionId,
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

function inputRef(target: LegacyRootMigrationPlan["files"][number]["targets"][number]): InputRevisionRef {
  const parts = target.revisionSlot.split(":");
  switch (target.revisionKind) {
    case "source_capture":
    case "source_extraction":
    case "prompt":
    case "policy":
      return { kind: target.revisionKind, logicalId: parts.slice(2).join(":"), revisionId: target.revisionId };
    case "edition_spec": {
      const key = parts.slice(2).join(":");
      return {
        kind: "edition_spec",
        editionId: key === "004-rerun" ? "004" : key,
        logicalId: key === "004-rerun" ? "legacy-rerun" : "main",
        revisionId: target.revisionId,
      };
    }
    case "migration_archive":
      return { kind: "migration_archive", logicalId: MIGRATION_ID, revisionId: target.revisionId };
    default:
      throw new Error(`target ${target.revisionSlot} is not an input revision`);
  }
}

function mediaType(path: string): string {
  const extension = path.toLowerCase().split(".").pop();
  switch (extension) {
    case "md": return "text/markdown";
    case "yaml":
    case "yml": return "application/yaml";
    case "json": return "application/json";
    case "toml": return "application/toml";
    case "png": return "image/png";
    case "jpg":
    case "jpeg": return "image/jpeg";
    case "webp": return "image/webp";
    case "pdf": return "application/pdf";
    case "html": return "text/html";
    case "txt": return "text/plain";
    case "svg": return "image/svg+xml";
    default: return "application/octet-stream";
  }
}

function usage(): Error {
  return new Error(
    "usage: legacy-root-cutover.ts plan <source-commit> [plan-revision-id] | " +
    "successor-plan <source-commit> <parent-plan-revision-id> [new-plan-revision-id] | " +
    "materialize-inputs <source-commit> <plan-revision-id> <source-1|source-2|misc|archive>",
  );
}

await main();
