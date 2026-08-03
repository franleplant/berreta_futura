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
import {
  compositionDurableRefs,
  parseCompositionDocument,
  type CompositionDocument,
} from "./composition-schema.ts";
import { validateDurableRevisionTree } from "./durable-store.ts";
import { validateInputRevisionTree } from "./input-revision.ts";
import {
  durableRevisionRelativeDirectory,
  inputRevisionRelativeDirectory,
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

export type BootstrapCompositionEntry = {
  readonly ref: Extract<DurableRevisionRef, { readonly kind: "composition" }>;
  readonly createdAt: string;
  readonly parentRevisionId: RevisionId | null;
  readonly sourcePaths: readonly string[];
  readonly document: CompositionDocument;
};

export type LegacyDurableMigrationPlan = {
  readonly schemaVersion: "legacy-durable-migration/1";
  readonly migrationId: string;
  readonly sourceGitBinding: GitRevisionBinding;
  readonly entries: readonly LegacyDurableRevisionEntry[];
  readonly composition: BootstrapCompositionEntry;
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
 * Copies an explicit legacy inventory into immutable DurableRevisions, then
 * assembles one fresh composition from exact revision references. It does not
 * invent a legacy RunId, decision, or PromotionId.
 */
export async function materializeLegacyDurableRevisions(
  repositoryRoot: string,
  workRoot: string,
  plan: LegacyDurableMigrationPlan,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<MaterializedLegacyDurableMigration> {
  validatePlan(plan);
  const root = resolve(repositoryRoot);
  const sourcePaths = uniqueSorted(
    [
      ...plan.entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
      ...plan.composition.sourcePaths,
    ],
  );
  try {
    await git.assertCommitted(sourcePaths, plan.sourceGitBinding);
  } catch (error) {
    throw new LegacyDurableMigrationError(
      "DURABLE_MIGRATION_SOURCE_UNCOMMITTED",
      "legacy durable sources must be exact committed files",
      { cause: error },
    );
  }

  const revisions: Array<MaterializedLegacyDurableMigration["revisions"][number]> = [];
  const repositoryPaths: string[] = [];
  const manifestDigests: Record<string, string> = {};
  for (const [index, entry] of plan.entries.entries()) {
    await validateInputRefs(root, entry.inputRevisions);
    const manifest = await legacyManifest(root, plan, entry);
    const installed = await materializeRevision(
      root,
      workRoot,
      plan.migrationId,
      index,
      entry.ref,
      manifest,
      entry.files.map((file) => ({
        targetPath: file.targetPath,
        read: async () => {
          const bytes = await readCommittedLegacyFile(root, file.sourcePath);
          validateLegacyPayload(bytes, file.mediaType, file.sourcePath);
          return bytes;
        },
      })),
    );
    appendInstalled(installed, revisions, repositoryPaths, manifestDigests);
  }

  const composition = await materializeBootstrapComposition(
    root,
    workRoot,
    plan.migrationId,
    plan.sourceGitBinding,
    plan.entries.length,
    plan.composition,
  );
  appendInstalled(composition, revisions, repositoryPaths, manifestDigests);

  const exactPaths = uniqueSorted(repositoryPaths);
  if (exactPaths.length !== repositoryPaths.length) {
    throw invalid("durable migration entries collide on repository paths");
  }
  return {
    migrationId: plan.migrationId,
    revisions,
    repositoryPaths: exactPaths,
    manifestDigests,
  };
}

async function materializeBootstrapComposition(
  repositoryRoot: string,
  workRoot: string,
  migrationId: string,
  sourceGitBinding: GitRevisionBinding,
  index: number,
  entry: BootstrapCompositionEntry,
) {
  await validateInputRefs(
    repositoryRoot,
    entry.document.layout_inputs.map((pin) => pin.revision),
  );
  for (const ref of compositionDurableRefs(entry.document)) {
    const directory = join(repositoryRoot, "durable", durableRevisionRelativeDirectory(ref));
    await validateDurableRevisionTree(directory, ref);
  }
  const compositionBytes = Buffer.from(stringify(entry.document, { lineWidth: 0 }), "utf8");
  const parsed = parseCompositionDocument(compositionBytes, {
    editionId: entry.ref.editionId,
    compositionId: entry.ref.compositionId,
  });
  if (JSON.stringify(parsed) !== JSON.stringify(entry.document)) {
    throw invalid("bootstrap composition is not canonical under its public schema");
  }
  const record: DurableFileRecord = {
    path: "composition.yaml",
    mediaType: "application/yaml",
    sha256: digest(compositionBytes),
    sizeBytes: compositionBytes.byteLength,
    migrationAssembly: {
      basis: "fresh_v2_composition_from_committed_legacy_inventory",
    },
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
    ),
    input_revisions: entry.document.layout_inputs.map((pin) => pin.revision),
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
  plan: LegacyDurableMigrationPlan,
  entry: LegacyDurableRevisionEntry,
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

async function validateInputRefs(
  repositoryRoot: string,
  refs: readonly InputRevisionRef[],
): Promise<void> {
  for (const ref of refs) {
    const directory = join(repositoryRoot, "inputs", inputRevisionRelativeDirectory(ref));
    await validateInputRevisionTree(directory, ref);
  }
}

async function readCommittedLegacyFile(root: string, path: string): Promise<Buffer> {
  const source = containedPath(root, path);
  const info = await lstat(source);
  if (info.isSymbolicLink() || !info.isFile()) {
    throw invalid(`legacy durable source ${path} is not a regular file`);
  }
  return readFile(source);
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

function validatePlan(plan: LegacyDurableMigrationPlan): void {
  if (
    plan.schemaVersion !== "legacy-durable-migration/1" ||
    plan.entries.length === 0
  ) {
    throw invalid("legacy durable migration plan is empty or has the wrong schema");
  }
  portableComponent(plan.migrationId, "durable migration ID");
  const sourcePaths = uniqueSorted(
    [
      ...plan.entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
      ...plan.composition.sourcePaths,
    ],
  );
  if (
    !validGitOid(plan.sourceGitBinding.commitOid) ||
    !sameSequence(Object.keys(plan.sourceGitBinding.blobOids), sourcePaths) ||
    Object.values(plan.sourceGitBinding.blobOids).some((oid) => !validGitOid(oid))
  ) {
    throw invalid("legacy durable source Git binding does not match the source path set");
  }
  const refs = new Set<string>();
  for (const entry of plan.entries) {
    validateRevisionEntry(entry);
    const key = revisionKey(entry.ref);
    if (refs.has(key)) throw invalid(`duplicate DurableRevision ${key}`);
    refs.add(key);
  }
  parseRevisionId(plan.composition.ref.revisionId);
  if (plan.composition.parentRevisionId !== null) {
    parseRevisionId(plan.composition.parentRevisionId);
  }
  if (!canonicalInstant(plan.composition.createdAt)) {
    throw invalid("bootstrap composition has an invalid creation time");
  }
  if (plan.composition.sourcePaths.length === 0) {
    throw invalid("migrated composition must name its committed legacy source basis");
  }
  for (const sourcePath of plan.composition.sourcePaths) {
    validateRelativePath(sourcePath, "composition legacy source");
  }
}

async function legacySourceBindings(
  repositoryRoot: string,
  sourcePaths: readonly string[],
  gitBinding: GitRevisionBinding,
) {
  return Promise.all(uniqueSorted(sourcePaths).map(async (repositoryPath) => {
    const bytes = await readCommittedLegacyFile(repositoryRoot, repositoryPath);
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
