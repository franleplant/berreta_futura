import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, resolve, sep } from "node:path";

import { stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import {
  validateInputRevisionTree,
  type InputRevisionFile,
  type InputRevisionManifest,
} from "./input-revision.ts";
import { inputRevisionRelativeDirectory } from "./paths.ts";
import type { InputRevisionRef } from "./types.ts";

export type NativeInputRevisionFile = {
  readonly path: string;
  readonly mediaType: string;
  readonly content: string | Uint8Array;
};

export type NativeInputRevisionRequest = {
  readonly ref: InputRevisionRef;
  readonly createdAt: string;
  readonly parentRevisionId: RevisionId | null;
  readonly files: readonly NativeInputRevisionFile[];
};

export type MaterializedNativeInputRevision = {
  readonly ref: InputRevisionRef;
  readonly relativeDirectory: string;
  readonly manifestDigest: string;
  readonly repositoryPaths: readonly string[];
};

export class NativeInputRevisionError extends Error {
  readonly code: "INPUT_REVISION_CONFLICT" | "INPUT_REVISION_INVALID";

  constructor(code: NativeInputRevisionError["code"], message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "NativeInputRevisionError";
    this.code = code;
  }
}

/**
 * Creates one native, immutable InputRevision from caller-owned bytes. It
 * atomically installs a fully validated candidate and never assigns legacy or
 * migration provenance to new inputs.
 */
export async function materializeNativeInputRevision(
  repositoryRoot: string,
  workRoot: string,
  request: NativeInputRevisionRequest,
): Promise<MaterializedNativeInputRevision> {
  if (request.files.length === 0) {
    throw invalid("native input revision requires at least one payload file");
  }
  const root = resolve(repositoryRoot);
  const relativeDirectory = join("inputs", inputRevisionRelativeDirectory(request.ref));
  const destination = containedPath(root, relativeDirectory);
  const candidateRoot = await mkdtemp(join(resolve(workRoot), "native-input-"));
  const candidate = join(candidateRoot, "revision");
  try {
    await mkdir(candidate, { recursive: true, mode: 0o700 });
    const records: InputRevisionFile[] = [];
    for (const file of request.files) {
      const target = containedPath(candidate, file.path);
      const bytes = typeof file.content === "string" ? Buffer.from(file.content, "utf8") : Buffer.from(file.content);
      await mkdir(dirname(target), { recursive: true, mode: 0o700 });
      await writeFile(target, bytes, { mode: 0o600 });
      records.push({
        path: file.path,
        media_type: file.mediaType,
        sha256: digest(bytes),
        size_bytes: bytes.byteLength,
      });
    }
    const manifest: InputRevisionManifest = {
      schema_version: 1,
      revision_kind: request.ref.kind,
      logical_id: request.ref.logicalId,
      ...editionBinding(request.ref),
      revision_id: request.ref.revisionId,
      created_at: request.createdAt,
      parent_revision_id: request.parentRevisionId,
      files: records.sort((left, right) => left.path.localeCompare(right.path)),
    };
    await writeFile(join(candidate, "manifest.yaml"), stringify(manifest, { lineWidth: 0 }), { mode: 0o600 });
    const validated = await validateInputRevisionTree(candidate, request.ref);
    try {
      await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
      await rename(candidate, destination);
    } catch (error) {
      const current = await existing(destination, request.ref);
      if (current === undefined || current.manifestDigest !== validated.manifestDigest) {
        throw conflict(`InputRevision target ${relativeDirectory} already contains different bytes`, error);
      }
    }
    const installed = await validateInputRevisionTree(destination, request.ref);
    const repositoryPaths = [
      join(relativeDirectory, "manifest.yaml"),
      ...installed.payloadPaths.map((path) => join(relativeDirectory, path)),
    ].sort();
    return { ref: request.ref, relativeDirectory, manifestDigest: installed.manifestDigest, repositoryPaths };
  } finally {
    await rm(candidateRoot, { recursive: true, force: true });
  }
}

function editionBinding(ref: InputRevisionRef): Pick<InputRevisionManifest, "edition_id"> {
  return ref.kind === "edition_spec" || ref.kind === "run_bootstrap" || ref.kind === "write_pipeline"
    ? { edition_id: ref.editionId! }
    : {};
}

async function existing(directory: string, ref: InputRevisionRef) {
  try {
    return await validateInputRevisionTree(directory, ref);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

function containedPath(root: string, child: string): string {
  const base = resolve(root);
  const path = resolve(base, child);
  if (path === base || !path.startsWith(`${base}${sep}`)) throw invalid(`path escapes its root: ${child}`);
  return path;
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function invalid(message: string, cause?: unknown): NativeInputRevisionError {
  return new NativeInputRevisionError("INPUT_REVISION_INVALID", message, cause === undefined ? undefined : { cause });
}

function conflict(message: string, cause?: unknown): NativeInputRevisionError {
  return new NativeInputRevisionError("INPUT_REVISION_CONFLICT", message, cause === undefined ? undefined : { cause });
}
