import { createHash } from "node:crypto";
import { lstat, readFile, readdir } from "node:fs/promises";
import { join, posix, resolve, sep } from "node:path";

import { parse } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import { inputRevisionRelativeDirectory, portableComponent } from "./paths.ts";
import { parseRevisionId } from "./revision-id.ts";
import type {
  DurableGit,
  InputRevisionKind,
  InputRevisionRef,
  LegacySourceBinding,
} from "./types.ts";

export type InputRevisionFile = {
  readonly path: string;
  readonly media_type: string;
  readonly sha256: string;
  readonly size_bytes: number;
  readonly legacy_source?: LegacySourceBinding;
  readonly generated_by_migration?: {
    readonly basis: string;
  };
};

export type InputRevisionManifest = {
  readonly schema_version: 1;
  readonly revision_kind: InputRevisionKind;
  readonly logical_id: string;
  readonly edition_id?: string;
  readonly revision_id: RevisionId;
  readonly created_at: string;
  readonly parent_revision_id: RevisionId | null;
  readonly migration_id?: string;
  readonly files: readonly InputRevisionFile[];
};

export type ResolvedInputRevision = {
  readonly ref: InputRevisionRef;
  readonly manifest: InputRevisionManifest;
  readonly manifestDigest: string;
  readonly relativeDirectory: string;
  readonly absoluteDirectory: string;
  readonly repositoryPaths: readonly string[];
  readonly payloadPaths: Readonly<Record<string, string>>;
};

export type ValidatedInputRevisionTree = {
  readonly manifest: InputRevisionManifest;
  readonly manifestDigest: string;
  readonly payloadPaths: readonly string[];
};

export class InputRevisionError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "InputRevisionError";
    this.code = code;
  }
}

/**
 * Resolves one immutable input by identity, validates every declared byte, and
 * rejects working-tree-only state through the injected Git authority.
 */
export async function resolveInputRevision(
  repositoryRoot: string,
  ref: InputRevisionRef,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<ResolvedInputRevision> {
  const relativeDirectory = join("inputs", inputRevisionRelativeDirectory(ref));
  const directory = containedPath(repositoryRoot, relativeDirectory);
  const validated = await validateInputRevisionTree(directory, ref);
  const { manifest } = validated;
  const repositoryPaths = [
    join(relativeDirectory, "manifest.yaml"),
    ...manifest.files.map((file) => join(relativeDirectory, file.path)),
  ].sort();
  try {
    await git.assertCommitted(repositoryPaths);
  } catch (error) {
    throw new InputRevisionError(
      "INPUT_REVISION_UNCOMMITTED",
      `input revision ${relativeDirectory} is not committed exactly`,
      { cause: error },
    );
  }
  return {
    ref,
    manifest,
    manifestDigest: validated.manifestDigest,
    relativeDirectory,
    absoluteDirectory: directory,
    repositoryPaths,
    payloadPaths: Object.fromEntries(manifest.files.map((file) => [
      file.path,
      containedPath(directory, file.path),
    ])),
  };
}

/** Validates a staged tree before it is atomically installed or committed. */
export async function validateInputRevisionTree(
  directory: string,
  ref: InputRevisionRef,
): Promise<ValidatedInputRevisionTree> {
  const manifestPath = join(directory, "manifest.yaml");
  const manifestBytes = await regularFile(manifestPath, "input manifest");
  let decoded: unknown;
  try {
    decoded = parse(manifestBytes.toString("utf8"));
  } catch (error) {
    throw invalid("input manifest is not valid YAML", error);
  }
  const manifest = validateManifest(decoded, ref);
  const actualFiles = await listFiles(directory);
  const expectedFiles = ["manifest.yaml", ...manifest.files.map((file) => file.path)].sort();
  if (!sameSequence(actualFiles, expectedFiles)) {
    throw invalid("input revision tree differs from its manifest");
  }
  for (const file of manifest.files) {
    const bytes = await regularFile(containedPath(directory, file.path), `input payload ${file.path}`);
    if (bytes.byteLength !== file.size_bytes || digest(bytes) !== file.sha256) {
      throw invalid(`input payload ${file.path} failed digest validation`);
    }
  }
  return {
    manifest,
    manifestDigest: digest(manifestBytes),
    payloadPaths: manifest.files.map((file) => file.path),
  };
}

function validateManifest(value: unknown, ref: InputRevisionRef): InputRevisionManifest {
  if (!mapping(value)) throw invalid("input manifest must be a mapping");
  if (
    value.schema_version !== 1 ||
    value.revision_kind !== ref.kind ||
    value.logical_id !== ref.logicalId ||
    typeof value.revision_id !== "string" ||
    value.revision_id !== ref.revisionId ||
    typeof value.created_at !== "string" ||
    (value.parent_revision_id !== null && typeof value.parent_revision_id !== "string") ||
    !Array.isArray(value.files)
  ) {
    throw invalid("input manifest identity or required fields do not match its revision reference");
  }
  portableComponent(value.logical_id, "input logical ID");
  parseRevisionId(value.revision_id);
  if (value.parent_revision_id !== null) parseRevisionId(value.parent_revision_id);
  if (!isCanonicalInstant(value.created_at)) {
    throw invalid("input manifest created_at must be a canonical UTC instant");
  }
  if (
    ref.kind === "edition_spec" ||
    ref.kind === "run_bootstrap" ||
    ref.kind === "write_pipeline"
  ) {
    if (value.edition_id !== ref.editionId) {
      throw invalid("edition spec manifest does not match its edition ID");
    }
    portableComponent(value.edition_id as string, "input edition ID");
  } else if (value.edition_id !== undefined) {
    throw invalid(`${ref.kind} manifest must not declare edition_id`);
  }

  const files = value.files.map((file, index) => validateFile(file, index));
  if (files.length === 0 || new Set(files.map((file) => file.path)).size !== files.length) {
    throw invalid("input manifest must declare unique payload files");
  }
  validatePayloadConvention(ref.kind, files);
  const provenanceFiles = files.filter((file) =>
    file.legacy_source !== undefined || file.generated_by_migration !== undefined
  );
  if (provenanceFiles.length !== 0 && provenanceFiles.length !== files.length) {
    throw invalid("migrated input revision must bind or explain every payload file");
  }
  if (provenanceFiles.length === files.length) {
    if (typeof value.migration_id !== "string" || value.migration_id.length === 0) {
      throw invalid("legacy input revision must declare its migration_id");
    }
    portableComponent(value.migration_id, "input migration ID");
  } else if (value.migration_id !== undefined) {
    throw invalid("native input revision must not declare migration_id");
  }
  return value as unknown as InputRevisionManifest;
}

function validateFile(value: unknown, index: number): InputRevisionFile {
  if (!mapping(value)) throw invalid(`input file record ${index} must be a mapping`);
  if (
    typeof value.path !== "string" ||
    typeof value.media_type !== "string" || value.media_type.length === 0 ||
    typeof value.sha256 !== "string" || !/^sha256:[0-9a-f]{64}$/u.test(value.sha256) ||
    typeof value.size_bytes !== "number" || !Number.isSafeInteger(value.size_bytes) || value.size_bytes < 0
  ) {
    throw invalid(`input file record ${index} is invalid`);
  }
  validatePortableRelativePath(value.path);
  if (value.legacy_source !== undefined) {
    const source = value.legacy_source;
    if (
      !mapping(source) ||
      typeof source.repositoryPath !== "string" ||
      typeof source.gitCommitOid !== "string" ||
      typeof source.gitBlobOid !== "string" ||
      !validGitOid(source.gitCommitOid) ||
      !validGitOid(source.gitBlobOid)
    ) {
      throw invalid(`input file record ${index} has invalid legacy Git provenance`);
    }
    validateLegacyRepositoryPath(source.repositoryPath);
  }
  if (value.generated_by_migration !== undefined) {
    const generated = value.generated_by_migration;
    if (
      value.legacy_source !== undefined ||
      !mapping(generated) ||
      typeof generated.basis !== "string" ||
      generated.basis.length === 0
    ) {
      throw invalid(`input file record ${index} has invalid migration-authored provenance`);
    }
  }
  return value as unknown as InputRevisionFile;
}

function validatePayloadConvention(
  kind: InputRevisionKind,
  files: readonly InputRevisionFile[],
): void {
  const paths = files.map((file) => file.path).sort();
  switch (kind) {
    case "source_capture":
      if (paths.some((path) => !path.startsWith("raw/"))) {
        throw invalid("source capture payloads must live under raw/");
      }
      return;
    case "source_extraction":
      if (!sameSequence(paths, ["extracted.md"])) {
        throw invalid("source extraction must contain exactly extracted.md");
      }
      return;
    case "prompt":
      if (!sameSequence(paths, ["output.schema.json", "prompt.md"])) {
        throw invalid("prompt revision must contain prompt.md and output.schema.json");
      }
      return;
    case "policy":
      if (!sameSequence(paths, ["policy.md"])) {
        throw invalid("policy revision must contain exactly policy.md");
      }
      return;
    case "migration_plan":
      if (!sameSequence(paths, ["inventory.yaml"])) {
        throw invalid("migration plan must contain exactly inventory.yaml");
      }
      return;
    case "migration_attestation":
      if (!sameSequence(paths, ["attestation.yaml"])) {
        throw invalid("migration attestation must contain exactly attestation.yaml");
      }
      return;
    case "article_production_profile":
      if (!sameSequence(paths, ["profile.json"])) {
        throw invalid("article production profile must contain exactly profile.json");
      }
      return;
    case "article_review_plan":
      if (!sameSequence(paths, ["review-plan.json"])) {
        throw invalid("article review plan must contain exactly review-plan.json");
      }
      return;
    case "review_material_schema":
      if (!sameSequence(paths, ["schema.json"])) {
        throw invalid("review material schema must contain exactly schema.json");
      }
      return;
    case "migration_archive":
      if (paths.length === 0 || paths.some((path) => !path.startsWith("archive/"))) {
        throw invalid("migration archive payloads must live under archive/");
      }
      return;
    case "edition_spec":
      if (!paths.includes("edition.yaml")) {
        throw invalid("edition spec revision must contain edition.yaml");
      }
      return;
    case "run_bootstrap":
      if (!sameSequence(paths, ["bootstrap.yaml"])) {
        throw invalid("run bootstrap revision must contain exactly bootstrap.yaml");
      }
      return;
    case "write_pipeline":
      if (!sameSequence(paths, ["production.yaml"])) {
        throw invalid("write pipeline revision must contain exactly production.yaml");
      }
      return;
  }
}

function validatePortableRelativePath(path: string): void {
  if (path.includes("\\") || posix.isAbsolute(path) || posix.normalize(path) !== path) {
    throw invalid(`input payload path is not a normalized relative path: ${path}`);
  }
  const components = path.split("/");
  if (components.length === 0) throw invalid("input payload path is empty");
  for (const component of components) portableComponent(component, "input payload path component");
}

function validateLegacyRepositoryPath(path: string): void {
  if (
    path.includes("\\") || path.includes("\0") || path.includes("\n") ||
    posix.isAbsolute(path) || posix.normalize(path) !== path ||
    path === "." || path.startsWith("../")
  ) {
    throw invalid(`legacy source repository path is unsafe: ${path}`);
  }
}

async function listFiles(root: string, prefix = ""): Promise<readonly string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const relativePath = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
    if (entry.isSymbolicLink() || (!entry.isDirectory() && !entry.isFile())) {
      throw invalid(`input revision contains unsupported entry ${relativePath}`);
    }
    if (entry.isDirectory()) {
      files.push(...await listFiles(join(root, entry.name), relativePath));
    } else {
      files.push(relativePath);
    }
  }
  return files.sort();
}

async function regularFile(path: string, label: string): Promise<Buffer> {
  let info;
  try {
    info = await lstat(path);
  } catch (error) {
    throw invalid(`${label} does not exist`, error);
  }
  if (info.isSymbolicLink() || !info.isFile()) throw invalid(`${label} is not a regular file`);
  return readFile(path);
}

function containedPath(root: string, child: string): string {
  const base = resolve(root);
  const path = resolve(base, child);
  if (path === base || !path.startsWith(`${base}${sep}`)) {
    throw invalid(`path escapes repository root: ${child}`);
  }
  return path;
}

function isCanonicalInstant(value: string): boolean {
  const parsed = new Date(value);
  return Number.isFinite(parsed.valueOf()) && parsed.toISOString() === value;
}

function mapping(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function sameSequence(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function validGitOid(value: string): boolean {
  return /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u.test(value);
}

function invalid(message: string, cause?: unknown): InputRevisionError {
  return new InputRevisionError(
    "INPUT_REVISION_INVALID",
    message,
    cause === undefined ? undefined : { cause },
  );
}
