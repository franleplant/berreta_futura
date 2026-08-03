import { createHash } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, posix, resolve, sep } from "node:path";
import { promisify } from "node:util";

import { stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import {
  compositionDurableRefs,
  parseCompositionDocument,
  type CompositionDocument,
} from "./composition-schema.ts";
import {
  resolveDurableRevision,
  validateDurableRevisionTree,
} from "./durable-store.ts";
import { resolveInputRevision } from "./input-revision.ts";
import {
  durableRevisionRelativeDirectory,
  portableComponent,
} from "./paths.ts";
import { parseRevisionId } from "./revision-id.ts";
import type {
  DurableFileRecord,
  DurableGit,
  DurableRevisionManifest,
  DurableRevisionRef,
  GitRevisionBinding,
  InputRevisionRef,
  LegacyDurableRevisionManifest,
} from "./types.ts";

const execFile = promisify(execFileCallback);

type LegacyDurableRevisionRef = Exclude<
  DurableRevisionRef,
  { readonly kind: "composition" }
>;

export type LegacyDurableFile = {
  readonly sourcePath: string;
  readonly targetPath: string;
  readonly mediaType: string;
};

export type LegacyDurableRevisionEntry = {
  readonly ref: LegacyDurableRevisionRef;
  readonly createdAt: string;
  readonly parentRevisionId: RevisionId | null;
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly files: readonly LegacyDurableFile[];
};

/**
 * Historical import can install an arbitrary set of legacy revisions,
 * historical compositions, or both. Every referenced revision is resolved
 * through the public Git-backed resolver before any candidate is written.
 */
export type HistoricalCompositionEntry = {
  readonly ref: Extract<DurableRevisionRef, { readonly kind: "composition" }>;
  readonly createdAt: string;
  readonly parentRevisionId: RevisionId | null;
  readonly sourcePaths: readonly string[];
  readonly document: CompositionDocument;
  /** Explicitly explains how this historical assembly was reconstructed. */
  readonly assemblyBasis: string;
  /**
   * Inputs beyond layout pins. This must include the exact migration plan
   * revision which authorized the historical assembly.
   */
  readonly extraInputRevisions: readonly InputRevisionRef[];
};

export type MigrationPlanRevisionRef = {
  readonly kind: "migration_plan";
  readonly logicalId: string;
  readonly revisionId: RevisionId;
};

export type LegacyDurableBatchMigrationPlan = {
  readonly schemaVersion: "legacy-durable-migration/2";
  readonly migrationId: string;
  readonly migrationPlanRevision: MigrationPlanRevisionRef;
  readonly sourceGitBinding: GitRevisionBinding;
  readonly entries: readonly LegacyDurableRevisionEntry[];
  readonly compositions: readonly HistoricalCompositionEntry[];
};

export type MaterializedLegacyDurableMigration = {
  readonly migrationId: string;
  readonly revisions: readonly {
    readonly ref: DurableRevisionRef;
    readonly relativeDirectory: string;
    readonly manifestDigest: string;
  }[];
  readonly repositoryPaths: readonly string[];
  readonly manifestDigests: Readonly<Record<string, string>>;
};

export class LegacyDurableMigrationError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "LegacyDurableMigrationError";
    this.code = code;
  }
}

/**
 * Materializes a durable migration batch without inventing a run, promotion,
 * or decision. Unlike the v1 bootstrap helper, v2 treats every input, parent,
 * and composition child as a committed immutable revision before writing any
 * candidate tree. It supports entry-only and composition-only batches.
 */
export async function materializeLegacyDurableMigrationBatch(
  repositoryRoot: string,
  workRoot: string,
  plan: LegacyDurableBatchMigrationPlan,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<MaterializedLegacyDurableMigration> {
  validateBatchPlan(plan);
  const root = resolve(repositoryRoot);
  const sourcePaths = uniqueSorted([
    ...plan.entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
    ...plan.compositions.flatMap((entry) => entry.sourcePaths),
  ]);
  try {
    await git.assertCommitted(sourcePaths, plan.sourceGitBinding);
  } catch (error) {
    throw new LegacyDurableMigrationError(
      "DURABLE_MIGRATION_SOURCE_UNCOMMITTED",
      "legacy durable sources must be exact committed files",
      { cause: error },
    );
  }
  const readSource = (path: string) => readBoundLegacyFile(root, path, plan.sourceGitBinding);

  // Resolve all cross-revision references before materialization. This makes
  // a partial batch impossible when a parent or pinned child is only present
  // in the working tree.
  await resolveInputRevision(root, plan.migrationPlanRevision, git);
  for (const entry of plan.entries) {
    await resolveInputRefs(root, entry.inputRevisions, git);
    await resolveParent(root, entry.ref, entry.parentRevisionId, git);
  }
  for (const entry of plan.compositions) {
    await resolveInputRefs(root, [
      ...entry.document.layout_inputs.map((pin) => pin.revision),
      ...entry.extraInputRevisions,
    ], git);
    await resolveParent(root, entry.ref, entry.parentRevisionId, git);
    for (const child of compositionDurableRefs(entry.document)) {
      await resolveDurableRevision(root, child, git);
    }
  }

  const revisions: Array<MaterializedLegacyDurableMigration["revisions"][number]> = [];
  const repositoryPaths: string[] = [];
  const manifestDigests: Record<string, string> = {};
  let index = 0;
  for (const entry of plan.entries) {
    const manifest = await legacyManifest(root, plan, entry, readSource);
    const installed = await materializeRevision(
      root,
      workRoot,
      plan.migrationId,
      index++,
      entry.ref,
      manifest,
      entry.files.map((file) => ({
        targetPath: file.targetPath,
        read: async () => {
          const bytes = await readSource(file.sourcePath);
          validateLegacyPayload(bytes, file.mediaType, file.sourcePath);
          return bytes;
        },
      })),
    );
    appendInstalled(installed, revisions, repositoryPaths, manifestDigests);
  }
  for (const entry of plan.compositions) {
    const installed = await materializeHistoricalComposition(
      root,
      workRoot,
      plan.migrationId,
      plan.sourceGitBinding,
      index++,
      entry,
      readSource,
    );
    appendInstalled(installed, revisions, repositoryPaths, manifestDigests);
  }
  const exactPaths = uniqueSorted(repositoryPaths);
  if (exactPaths.length !== repositoryPaths.length) {
    throw invalid("durable migration entries collide on repository paths");
  }
  return { migrationId: plan.migrationId, revisions, repositoryPaths: exactPaths, manifestDigests };
}

async function materializeHistoricalComposition(
  repositoryRoot: string,
  workRoot: string,
  migrationId: string,
  sourceGitBinding: GitRevisionBinding,
  index: number,
  entry: HistoricalCompositionEntry,
  readSource: (path: string) => Promise<Buffer>,
) {
  const compositionBytes = Buffer.from(stringify(entry.document, { lineWidth: 0 }), "utf8");
  const parsed = parseCompositionDocument(compositionBytes, {
    editionId: entry.ref.editionId,
    compositionId: entry.ref.compositionId,
  });
  if (JSON.stringify(parsed) !== JSON.stringify(entry.document)) {
    throw invalid("historical composition is not canonical under its public schema");
  }
  const record: DurableFileRecord = {
    path: "composition.yaml",
    mediaType: "application/yaml",
    sha256: digest(compositionBytes),
    sizeBytes: compositionBytes.byteLength,
    migrationAssembly: { basis: entry.assemblyBasis },
  };
  const manifest: LegacyDurableRevisionManifest = {
    schema_version: 1,
    revision_kind: "composition",
    edition_id: entry.ref.editionId,
    composition_id: entry.ref.compositionId,
    revision_id: entry.ref.revisionId,
    created_at: entry.createdAt,
    parent_revision_id: entry.parentRevisionId,
    provenance_kind: "legacy_import",
    migration_id: migrationId,
    legacy_run_inventory: "absent",
    legacy_source_bindings: await legacySourceBindings(
      repositoryRoot,
      entry.sourcePaths,
      sourceGitBinding,
      readSource,
    ),
    input_revisions: uniqueInputRefs([
      ...entry.document.layout_inputs.map((pin) => pin.revision),
      ...entry.extraInputRevisions,
    ]),
    files: [record],
  };
  return materializeRevision(
    repositoryRoot,
    workRoot,
    migrationId,
    index,
    entry.ref,
    manifest,
    [{ targetPath: "composition.yaml", read: async () => compositionBytes }],
  );
}

async function legacyManifest(
  repositoryRoot: string,
  plan: Pick<LegacyDurableBatchMigrationPlan, "migrationId" | "sourceGitBinding">,
  entry: LegacyDurableRevisionEntry,
  readSource: (path: string) => Promise<Buffer>,
): Promise<LegacyDurableRevisionManifest> {
  const files = entry.files.map((file) => ({
    path: file.targetPath,
    mediaType: file.mediaType,
    sha256: "sha256:" + "0".repeat(64),
    sizeBytes: 1,
    legacySource: {
      repositoryPath: file.sourcePath,
      gitCommitOid: plan.sourceGitBinding.commitOid,
      gitBlobOid: plan.sourceGitBinding.blobOids[file.sourcePath]!,
    },
  } satisfies DurableFileRecord));
  const common = {
    schema_version: 1 as const,
    revision_kind: entry.ref.kind,
    edition_id: entry.ref.editionId,
    revision_id: entry.ref.revisionId,
    created_at: entry.createdAt,
    parent_revision_id: entry.parentRevisionId,
    provenance_kind: "legacy_import" as const,
    migration_id: plan.migrationId,
    legacy_run_inventory: "absent" as const,
    legacy_source_bindings: await legacySourceBindings(
      repositoryRoot,
      entry.files.map((file) => file.sourcePath),
      plan.sourceGitBinding,
      readSource,
    ),
    input_revisions: entry.inputRevisions,
    files,
  };
  switch (entry.ref.kind) {
    case "article":
    case "editorial":
      return {
        ...common,
        revision_kind: entry.ref.kind,
        logical_id: entry.ref.logicalId,
        language: entry.ref.language,
      };
    case "image":
      return {
        ...common,
        revision_kind: "image",
        logical_id: entry.ref.logicalId,
      };
  }
}

async function materializeRevision(
  repositoryRoot: string,
  workRoot: string,
  migrationId: string,
  index: number,
  ref: DurableRevisionRef,
  template: DurableRevisionManifest,
  files: readonly { readonly targetPath: string; readonly read: () => Promise<Buffer> }[],
): Promise<{
  readonly ref: DurableRevisionRef;
  readonly relativeDirectory: string;
  readonly manifestDigest: string;
  readonly repositoryPaths: readonly string[];
}> {
  await mkdir(resolve(workRoot), { recursive: true, mode: 0o700 });
  const candidate = await mkdtemp(join(resolve(workRoot), `${migrationId}-${index}-`));
  try {
    const records: DurableFileRecord[] = [];
    for (const [fileIndex, file] of files.entries()) {
      const bytes = await file.read();
      if (bytes.byteLength === 0) throw invalid(`durable payload ${file.targetPath} is empty`);
      const target = containedPath(candidate, file.targetPath);
      await mkdir(dirname(target), { recursive: true, mode: 0o700 });
      await writeFile(target, bytes, { mode: 0o600 });
      const sourceRecord = template.files[fileIndex];
      if (sourceRecord === undefined || sourceRecord.path !== file.targetPath) {
        throw invalid("durable migration manifest template disagrees with its files");
      }
      records.push({
        ...sourceRecord,
        sha256: digest(bytes),
        sizeBytes: bytes.byteLength,
      });
    }
    const exactManifest = { ...template, files: records } as DurableRevisionManifest;
    await writeFile(
      join(candidate, "manifest.yaml"),
      stringify(exactManifest, { lineWidth: 0 }),
      { mode: 0o600 },
    );
    const relativeDirectory = join("durable", durableRevisionRelativeDirectory(ref));
    const destination = containedPath(repositoryRoot, relativeDirectory);
    const validatedCandidate = await validateDurableRevisionTree(candidate, ref);
    if (await exists(destination)) {
      const existing = await validateDurableRevisionTree(destination, ref);
      if (existing.manifestDigest !== validatedCandidate.manifestDigest) {
        throw conflict(`DurableRevision target ${relativeDirectory} contains different bytes`);
      }
    } else {
      await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
      try {
        await rename(candidate, destination);
      } catch (error) {
        if (!(await exists(destination))) throw error;
        const raced = await validateDurableRevisionTree(destination, ref);
        if (raced.manifestDigest !== validatedCandidate.manifestDigest) {
          throw conflict(`DurableRevision target ${relativeDirectory} raced with different bytes`, error);
        }
      }
    }
    const validated = await validateDurableRevisionTree(destination, ref);
    return {
      ref,
      relativeDirectory,
      manifestDigest: validated.manifestDigest,
      repositoryPaths: [
        join(relativeDirectory, "manifest.yaml"),
        ...validated.payloadPaths.map((path) => join(relativeDirectory, path)),
      ].sort(),
    };
  } finally {
    await rm(candidate, { recursive: true, force: true });
  }
}

function appendInstalled(
  installed: {
    readonly ref: DurableRevisionRef;
    readonly relativeDirectory: string;
    readonly manifestDigest: string;
    readonly repositoryPaths: readonly string[];
  },
  revisions: Array<MaterializedLegacyDurableMigration["revisions"][number]>,
  repositoryPaths: string[],
  manifestDigests: Record<string, string>,
): void {
  revisions.push({
    ref: installed.ref,
    relativeDirectory: installed.relativeDirectory,
    manifestDigest: installed.manifestDigest,
  });
  repositoryPaths.push(...installed.repositoryPaths);
  manifestDigests[join(installed.relativeDirectory, "manifest.yaml")] = installed.manifestDigest;
}

async function resolveInputRefs(
  repositoryRoot: string,
  refs: readonly InputRevisionRef[],
  git: Pick<DurableGit, "assertCommitted">,
): Promise<void> {
  for (const ref of uniqueInputRefs(refs)) {
    await resolveInputRevision(repositoryRoot, ref, git);
  }
}

async function resolveParent(
  repositoryRoot: string,
  ref: DurableRevisionRef,
  parentRevisionId: RevisionId | null,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<void> {
  if (parentRevisionId === null) return;
  if (parentRevisionId === ref.revisionId) {
    throw invalid("durable revision cannot name itself as its parent");
  }
  const parent = { ...ref, revisionId: parentRevisionId } as DurableRevisionRef;
  const resolved = await resolveDurableRevision(repositoryRoot, parent, git);
  if (!sameLogicalIdentity(ref, resolved.ref)) {
    throw invalid("durable revision parent does not match its logical identity");
  }
}

async function readBoundLegacyFile(
  repositoryRoot: string,
  repositoryPath: string,
  binding: GitRevisionBinding,
): Promise<Buffer> {
  const blobOid = binding.blobOids[repositoryPath];
  if (blobOid === undefined || !validGitOid(blobOid)) {
    throw invalid(`legacy durable source ${repositoryPath} has no exact Git blob binding`);
  }
  try {
    const { stdout } = await execFile(
      "git",
      ["-C", repositoryRoot, "cat-file", "blob", blobOid],
      { encoding: "buffer", maxBuffer: 1024 * 1024 * 1024 },
    );
    return Buffer.isBuffer(stdout) ? stdout : Buffer.from(stdout);
  } catch (error) {
    throw new LegacyDurableMigrationError(
      "DURABLE_MIGRATION_SOURCE_UNCOMMITTED",
      `cannot read immutable Git blob ${blobOid} for ${repositoryPath}`,
      { cause: error },
    );
  }
}

function validateLegacyPayload(bytes: Buffer, mediaType: string, sourcePath: string): void {
  if (bytes.byteLength === 0) throw invalid(`legacy durable source ${sourcePath} is empty`);
  if (mediaType === "text/markdown") return;
  const valid = mediaType === "image/png"
    ? bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
    : mediaType === "image/jpeg"
      ? bytes[0] === 0xff && bytes[1] === 0xd8 && bytes.at(-2) === 0xff && bytes.at(-1) === 0xd9
      : mediaType === "image/webp"
        ? bytes.subarray(0, 4).toString("ascii") === "RIFF" &&
          bytes.subarray(8, 12).toString("ascii") === "WEBP"
        : mediaType === "image/svg+xml"
          ? /<svg(?:\s|>)/u.test(bytes.toString("utf8", 0, Math.min(bytes.byteLength, 4096)))
          : false;
  if (!valid) throw invalid(`legacy durable source ${sourcePath} does not match ${mediaType}`);
}

function validateBatchPlan(plan: LegacyDurableBatchMigrationPlan): void {
  if (
    plan.schemaVersion !== "legacy-durable-migration/2" ||
    (plan.entries.length === 0 && plan.compositions.length === 0)
  ) {
    throw invalid("legacy durable batch migration plan is empty or has the wrong schema");
  }
  portableComponent(plan.migrationId, "durable migration ID");
  if (
    plan.migrationPlanRevision.kind !== "migration_plan" ||
    plan.migrationPlanRevision.logicalId !== plan.migrationId
  ) {
    throw invalid("legacy durable batch must name its exact authorizing migration plan");
  }
  parseRevisionId(plan.migrationPlanRevision.revisionId);
  const sourcePaths = uniqueSorted([
    ...plan.entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
    ...plan.compositions.flatMap((entry) => entry.sourcePaths),
  ]);
  if (
    !validGitOid(plan.sourceGitBinding.commitOid) ||
    sourcePaths.length === 0 ||
    !sameSequence(Object.keys(plan.sourceGitBinding.blobOids), sourcePaths) ||
    Object.values(plan.sourceGitBinding.blobOids).some((oid) => !validGitOid(oid))
  ) {
    throw invalid("legacy durable source Git binding does not match the source path set");
  }
  const refs = new Set<string>();
  for (const entry of plan.entries) {
    validateRevisionEntry(entry);
    validateExactMigrationPlanInput(
      entry.inputRevisions,
      plan.migrationPlanRevision,
      "legacy durable revision",
    );
    if (uniqueInputRefs(entry.inputRevisions).length !== entry.inputRevisions.length) {
      throw invalid("legacy durable revision has duplicate input revision references");
    }
    addUniqueRevision(refs, entry.ref);
  }
  for (const entry of plan.compositions) {
    validateHistoricalCompositionEntry(entry, plan.migrationPlanRevision);
    addUniqueRevision(refs, entry.ref);
  }
}

function validateHistoricalCompositionEntry(
  entry: HistoricalCompositionEntry,
  migrationPlanRevision: MigrationPlanRevisionRef,
): void {
  parseRevisionId(entry.ref.revisionId);
  if (entry.parentRevisionId !== null) parseRevisionId(entry.parentRevisionId);
  if (!canonicalInstant(entry.createdAt)) {
    throw invalid("historical composition has an invalid creation time");
  }
  if (entry.sourcePaths.length === 0) {
    throw invalid("historical composition must name its committed legacy source basis");
  }
  for (const sourcePath of entry.sourcePaths) {
    validateRelativePath(sourcePath, "composition legacy source");
  }
  if (entry.assemblyBasis.trim().length === 0) {
    throw invalid("historical composition requires a caller-supplied assembly basis");
  }
  validateExactMigrationPlanInput(
    entry.extraInputRevisions,
    migrationPlanRevision,
    "historical composition",
  );
  const compositionBytes = Buffer.from(stringify(entry.document, { lineWidth: 0 }), "utf8");
  parseCompositionDocument(compositionBytes, {
    editionId: entry.ref.editionId,
    compositionId: entry.ref.compositionId,
  });
  const inputs = [
    ...entry.document.layout_inputs.map((pin) => pin.revision),
    ...entry.extraInputRevisions,
  ];
  if (uniqueInputRefs(inputs).length !== inputs.length) {
    throw invalid("historical composition has duplicate input revision references");
  }
}

function addUniqueRevision(refs: Set<string>, ref: DurableRevisionRef): void {
  const key = revisionKey(ref);
  if (refs.has(key)) throw invalid(`duplicate DurableRevision ${key}`);
  refs.add(key);
}

async function legacySourceBindings(
  _repositoryRoot: string,
  sourcePaths: readonly string[],
  gitBinding: GitRevisionBinding,
  readSource: (path: string) => Promise<Buffer>,
) {
  return Promise.all(uniqueSorted(sourcePaths).map(async (repositoryPath) => {
    const bytes = await readSource(repositoryPath);
    return {
      repositoryPath,
      gitCommitOid: gitBinding.commitOid,
      gitBlobOid: gitBinding.blobOids[repositoryPath]!,
      sha256: digest(bytes),
    };
  }));
}

function validateRevisionEntry(entry: LegacyDurableRevisionEntry): void {
  parseRevisionId(entry.ref.revisionId);
  if (entry.parentRevisionId !== null) parseRevisionId(entry.parentRevisionId);
  if (!canonicalInstant(entry.createdAt) || entry.files.length === 0) {
    throw invalid("legacy durable revision has invalid time or no files");
  }
  const targets = entry.files.map((file) => file.targetPath).sort();
  for (const file of entry.files) {
    validateRelativePath(file.sourcePath, "legacy durable source");
    validateRelativePath(file.targetPath, "durable target");
    if (file.targetPath.includes("/") || file.mediaType.length === 0) {
      throw invalid("durable migration payload must be a direct file with a media type");
    }
  }
  if (new Set(targets).size !== targets.length) {
    throw invalid("durable migration has duplicate target files");
  }
  switch (entry.ref.kind) {
    case "article":
      if (!sameSequence(targets, ["manuscript.md"]) &&
        !sameSequence(targets, ["manuscript.md", "working-notes.md"])) {
        throw invalid("legacy article must contain manuscript.md and optional working-notes.md");
      }
      break;
    case "editorial":
      if (!sameSequence(targets, ["manuscript.md"])) {
        throw invalid("legacy editorial must contain exactly manuscript.md");
      }
      break;
    case "image":
      if (targets.length !== 1 || !/^image\.(?:jpg|png|svg|webp)$/u.test(targets[0]!)) {
        throw invalid("legacy image must contain one canonical image payload");
      }
  }
}

function revisionKey(ref: DurableRevisionRef): string {
  return ref.kind === "composition"
    ? `composition:${ref.editionId}:${ref.compositionId}:${ref.revisionId}`
    : `${ref.kind}:${ref.editionId}:${ref.logicalId}:${ref.language ?? ""}:${ref.revisionId}`;
}

function sameLogicalIdentity(left: DurableRevisionRef, right: DurableRevisionRef): boolean {
  if (left.kind !== right.kind || left.editionId !== right.editionId) return false;
  switch (left.kind) {
    case "article":
    case "editorial":
      return right.kind === left.kind &&
        left.logicalId === right.logicalId && left.language === right.language;
    case "image":
      return right.kind === "image" && left.logicalId === right.logicalId;
    case "composition":
      return right.kind === "composition" && left.compositionId === right.compositionId;
  }
}

function inputKey(ref: InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

function sameInputRevision(left: InputRevisionRef, right: InputRevisionRef): boolean {
  return inputKey(left) === inputKey(right);
}

function validateExactMigrationPlanInput(
  refs: readonly InputRevisionRef[],
  expected: MigrationPlanRevisionRef,
  label: string,
): void {
  const migrationPlans = refs.filter((ref) => ref.kind === "migration_plan");
  if (migrationPlans.length !== 1 || !sameInputRevision(migrationPlans[0]!, expected)) {
    throw invalid(`${label} requires exactly one exact migration plan input revision`);
  }
}

function uniqueInputRefs(refs: readonly InputRevisionRef[]): InputRevisionRef[] {
  const byKey = new Map<string, InputRevisionRef>();
  for (const ref of refs) byKey.set(inputKey(ref), ref);
  return [...byKey.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([, ref]) => ref);
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

function uniqueSorted(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

function sameSequence(left: readonly string[], right: readonly string[]): boolean {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return sortedLeft.length === sortedRight.length &&
    sortedLeft.every((value, index) => value === sortedRight[index]);
}

function validGitOid(value: string): boolean {
  return /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u.test(value);
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function invalid(message: string): LegacyDurableMigrationError {
  return new LegacyDurableMigrationError("DURABLE_MIGRATION_INVALID", message);
}

function conflict(message: string, cause?: unknown): LegacyDurableMigrationError {
  return new LegacyDurableMigrationError(
    "DURABLE_MIGRATION_CONFLICT",
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
