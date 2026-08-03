import { createHash } from "node:crypto";
import {
  access,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, posix, resolve, sep } from "node:path";

import { stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import type {
  GitInputMigrationCheckpointRequest,
} from "./git-cli.ts";
import {
  validateInputRevisionTree,
  type InputRevisionFile,
  type InputRevisionManifest,
} from "./input-revision.ts";
import { inputRevisionRelativeDirectory, portableComponent } from "./paths.ts";
import { parseRevisionId } from "./revision-id.ts";
import type {
  DurableGit,
  GitRevisionBinding,
  InputRevisionRef,
} from "./types.ts";

type LegacyInputFileBase = {
  readonly targetPath: string;
  readonly mediaType: string;
};

export type LegacyInputFile = LegacyInputFileBase & ({
  readonly sourcePath: string;
  readonly content?: never;
  readonly generationBasis?: never;
} | {
  readonly sourcePath?: never;
  readonly content: string;
  readonly generationBasis: string;
});

export type LegacyInputRevisionEntry = {
  readonly ref: InputRevisionRef;
  readonly createdAt: string;
  readonly parentRevisionId: RevisionId | null;
  readonly files: readonly LegacyInputFile[];
};

export type LegacyInputMigrationPlan = {
  readonly schemaVersion: "legacy-input-migration/1";
  readonly migrationId: string;
  readonly sourceGitBinding: GitRevisionBinding;
  readonly entries: readonly LegacyInputRevisionEntry[];
};

export type MaterializedLegacyInputMigration = {
  readonly migrationId: string;
  readonly revisions: readonly {
    readonly ref: InputRevisionRef;
    readonly relativeDirectory: string;
    readonly manifestDigest: string;
  }[];
  readonly repositoryPaths: readonly string[];
  readonly manifestDigests: Readonly<Record<string, string>>;
};

export type LegacyInputMigrationResult = MaterializedLegacyInputMigration & {
  readonly gitBinding: GitRevisionBinding;
};

export interface LegacyInputMigrationGit extends Pick<DurableGit, "assertCommitted"> {
  checkpointInputMigration(request: GitInputMigrationCheckpointRequest): Promise<GitRevisionBinding>;
}

export class LegacyInputMigrationError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "LegacyInputMigrationError";
    this.code = code;
  }
}

/**
 * Imports explicitly inventoried legacy bytes into immutable InputRevisions.
 * It never discovers workflow state and never deletes the legacy source.
 */
export async function migrateLegacyInputs(
  repositoryRoot: string,
  workRoot: string,
  plan: LegacyInputMigrationPlan,
  git: LegacyInputMigrationGit,
): Promise<LegacyInputMigrationResult> {
  const materialized = await materializeLegacyInputs(repositoryRoot, workRoot, plan, git);
  const gitBinding = await git.checkpointInputMigration({
    migrationId: plan.migrationId,
    repositoryPaths: materialized.repositoryPaths,
    manifestDigests: materialized.manifestDigests,
  });
  return { ...materialized, gitBinding };
}

/** Materializes the exact trees without committing so a larger scoped bootstrap can commit once. */
export async function materializeLegacyInputs(
  repositoryRoot: string,
  workRoot: string,
  plan: LegacyInputMigrationPlan,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<MaterializedLegacyInputMigration> {
  validatePlan(plan);
  const root = resolve(repositoryRoot);
  const sourcePaths = [...new Set(
    plan.entries.flatMap((entry) => entry.files.flatMap((file) =>
      file.sourcePath === undefined ? [] : [file.sourcePath]
    )),
  )].sort();
  if (sourcePaths.length > 0) {
    try {
      await git.assertCommitted(sourcePaths, plan.sourceGitBinding);
    } catch (error) {
      throw new LegacyInputMigrationError(
        "INPUT_MIGRATION_SOURCE_UNCOMMITTED",
        "legacy input sources must be exact committed files",
        { cause: error },
      );
    }
  }

  const revisions: Array<LegacyInputMigrationResult["revisions"][number]> = [];
  const repositoryPaths: string[] = [];
  const manifestDigests: Record<string, string> = {};
  for (const [index, entry] of plan.entries.entries()) {
    const relativeDirectory = join("inputs", inputRevisionRelativeDirectory(entry.ref));
    const destination = containedPath(root, relativeDirectory);
    const materialized = await materializeEntry(
      root,
      workRoot,
      plan.migrationId,
      plan.sourceGitBinding,
      index,
      entry,
    );
    const existing = await exists(destination);
    if (existing) {
      const current = await validateInputRevisionTree(destination, entry.ref);
      if (
        current.manifestDigest !== materialized.manifestDigest ||
        !sameSequence(current.payloadPaths, materialized.payloadPaths)
      ) {
        await rm(materialized.candidate, { recursive: true, force: true });
        throw conflict(`InputRevision target ${relativeDirectory} contains different bytes`);
      }
      await rm(materialized.candidate, { recursive: true, force: true });
    } else {
      await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
      try {
        await rename(materialized.candidate, destination);
      } catch (error) {
        if (!(await exists(destination))) throw error;
        const raced = await validateInputRevisionTree(destination, entry.ref);
        if (raced.manifestDigest !== materialized.manifestDigest) {
          throw conflict(`InputRevision target ${relativeDirectory} raced with different bytes`, error);
        }
      } finally {
        await rm(materialized.candidate, { recursive: true, force: true });
      }
    }
    const validated = await validateInputRevisionTree(destination, entry.ref);
    const paths = [
      join(relativeDirectory, "manifest.yaml"),
      ...validated.payloadPaths.map((path) => join(relativeDirectory, path)),
    ].sort();
    repositoryPaths.push(...paths);
    const manifestPath = join(relativeDirectory, "manifest.yaml");
    manifestDigests[manifestPath] = validated.manifestDigest;
    revisions.push({
      ref: entry.ref,
      relativeDirectory,
      manifestDigest: validated.manifestDigest,
    });
  }
  const exactPaths = [...new Set(repositoryPaths)].sort();
  if (exactPaths.length !== repositoryPaths.length) {
    throw invalid("input migration entries collide on repository paths");
  }
  return {
    migrationId: plan.migrationId,
    revisions,
    repositoryPaths: exactPaths,
    manifestDigests,
  };
}

async function materializeEntry(
  repositoryRoot: string,
  workRoot: string,
  migrationId: string,
  sourceGitBinding: GitRevisionBinding,
  index: number,
  entry: LegacyInputRevisionEntry,
): Promise<{
  readonly candidate: string;
  readonly manifestDigest: string;
  readonly payloadPaths: readonly string[];
}> {
  await mkdir(resolve(workRoot), { recursive: true, mode: 0o700 });
  const candidate = await mkdtemp(join(resolve(workRoot), `${migrationId}-${index}-`));
  try {
    const records: InputRevisionFile[] = [];
    for (const file of entry.files) {
      let bytes: Buffer;
      let provenance: Pick<InputRevisionFile, "legacy_source" | "generated_by_migration">;
      if (file.sourcePath !== undefined) {
        const source = containedPath(repositoryRoot, file.sourcePath);
        const info = await lstat(source);
        if (info.isSymbolicLink() || !info.isFile()) {
          throw invalid(`legacy source ${file.sourcePath} is not a regular file`);
        }
        bytes = await readFile(source);
        provenance = {
          legacy_source: {
            repositoryPath: file.sourcePath,
            gitCommitOid: sourceGitBinding.commitOid,
            gitBlobOid: sourceGitBinding.blobOids[file.sourcePath]!,
          },
        };
      } else {
        bytes = Buffer.from(file.content, "utf8");
        provenance = {
          generated_by_migration: { basis: file.generationBasis },
        };
      }
      const target = containedPath(candidate, file.targetPath);
      await mkdir(dirname(target), { recursive: true, mode: 0o700 });
      await writeFile(target, bytes, { mode: 0o600 });
      records.push({
        path: file.targetPath,
        media_type: file.mediaType,
        sha256: digest(bytes),
        size_bytes: bytes.byteLength,
        ...provenance,
      });
    }
    const manifest: InputRevisionManifest = {
      schema_version: 1,
      revision_kind: entry.ref.kind,
      logical_id: entry.ref.logicalId,
      ...(entry.ref.kind === "edition_spec" || entry.ref.kind === "run_bootstrap"
        ? { edition_id: entry.ref.editionId }
        : {}),
      revision_id: entry.ref.revisionId,
      created_at: entry.createdAt,
      parent_revision_id: entry.parentRevisionId,
      migration_id: migrationId,
      files: records.sort((left, right) => left.path.localeCompare(right.path)),
    };
    const manifestBytes = Buffer.from(stringify(manifest, { lineWidth: 0 }), "utf8");
    await writeFile(join(candidate, "manifest.yaml"), manifestBytes, { mode: 0o600 });
    const validated = await validateInputRevisionTree(candidate, entry.ref);
    return {
      candidate,
      manifestDigest: validated.manifestDigest,
      payloadPaths: validated.payloadPaths,
    };
  } catch (error) {
    await rm(candidate, { recursive: true, force: true });
    throw error;
  }
}

function validatePlan(plan: LegacyInputMigrationPlan): void {
  if (plan.schemaVersion !== "legacy-input-migration/1" || plan.entries.length === 0) {
    throw invalid("legacy input migration plan is empty or has the wrong schema");
  }
  portableComponent(plan.migrationId, "input migration ID");
  const sourcePaths = [...new Set(
    plan.entries.flatMap((entry) => entry.files.flatMap((file) =>
      file.sourcePath === undefined ? [] : [file.sourcePath]
    )),
  )].sort();
  if (
    !validGitOid(plan.sourceGitBinding.commitOid) ||
    !sameSequence(Object.keys(plan.sourceGitBinding.blobOids), sourcePaths) ||
    Object.values(plan.sourceGitBinding.blobOids).some((oid) => !validGitOid(oid))
  ) {
    throw invalid("legacy input source Git binding does not match the source path set");
  }
  const refs = new Set<string>();
  for (const entry of plan.entries) {
    parseRevisionId(entry.ref.revisionId);
    if (entry.parentRevisionId !== null) parseRevisionId(entry.parentRevisionId);
    if (!canonicalInstant(entry.createdAt) || entry.files.length === 0) {
      throw invalid("input migration entry has invalid time or no files");
    }
    const key = inputKey(entry.ref);
    if (refs.has(key)) throw invalid(`duplicate InputRevision ${key}`);
    refs.add(key);
    const targetPaths = new Set<string>();
    for (const file of entry.files) {
      if (file.sourcePath !== undefined) {
        validateRelativePath(file.sourcePath, "legacy source");
      } else if (file.content.length === 0 || file.generationBasis.length === 0) {
        throw invalid("migration-authored input file needs content and a generation basis");
      }
      validateRelativePath(file.targetPath, "input target");
      if (file.mediaType.length === 0 || targetPaths.has(file.targetPath)) {
        throw invalid("input migration file has invalid media type or duplicate target");
      }
      targetPaths.add(file.targetPath);
    }
  }
}

function validateRelativePath(path: string, label: string): void {
  if (
    path.includes("\\") || path.includes("\0") || path.includes("\n") ||
    isAbsolute(path) || posix.isAbsolute(path) || posix.normalize(path) !== path ||
    path === "." || path.startsWith("../")
  ) {
    throw invalid(`${label} path is unsafe: ${path}`);
  }
}

function containedPath(root: string, child: string): string {
  const base = resolve(root);
  const path = resolve(base, child);
  if (path === base || !path.startsWith(`${base}${sep}`)) {
    throw invalid(`path escapes its root: ${child}`);
  }
  return path;
}

function canonicalInstant(value: string): boolean {
  const parsed = new Date(value);
  return Number.isFinite(parsed.valueOf()) && parsed.toISOString() === value;
}

function inputKey(ref: InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

function sameSequence(left: readonly string[], right: readonly string[]): boolean {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return sortedLeft.length === sortedRight.length &&
    sortedLeft.every((value, index) => value === sortedRight[index]);
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function validGitOid(value: string): boolean {
  return /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u.test(value);
}

function invalid(message: string): LegacyInputMigrationError {
  return new LegacyInputMigrationError("INPUT_MIGRATION_INVALID", message);
}

function conflict(message: string, cause?: unknown): LegacyInputMigrationError {
  return new LegacyInputMigrationError(
    "INPUT_MIGRATION_CONFLICT",
    message,
    cause === undefined ? undefined : { cause },
  );
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}
