import { copyFile, lstat, mkdir, readFile, readdir, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";

import type { ArtifactId } from "../contracts/index.ts";

import {
  SOURCE_CONTRACT_VERSION,
  type SourceAdapter,
  type SourceRequest,
  type SourceResult,
} from "./protocol.ts";

/**
 * Copies exactly the immutable files named in a source adapter request.
 *
 * This is deliberately a local TypeScript adapter rather than a workflow
 * participant: `SourceArchiveExecutor` owns the claim, input staging, and
 * durable answer. The adapter only validates containment and materializes its
 * caller-owned output tree.
 */
export class LocalSourceAdapter implements SourceAdapter {
  async archive(
    requestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<SourceResult> {
    throwIfAborted(signal);
    const request = await readRequest(requestPath);
    const artifactRoot = await regularDirectory(request.artifactRoot, "artifactRoot");
    const outputRoot = await emptyDestination(destination);
    const files: Array<{ path: string; kind: string }> = [];
    const targets = new Set<string>();

    for (const file of request.files) {
      throwIfAborted(signal);
      const targetPath = safeTargetPath(file.targetPath);
      if (targets.has(targetPath)) {
        throw new Error(`duplicate targetPath: ${targetPath}`);
      }
      targets.add(targetPath);
      const source = await regularFileWithin(file.sourcePath, artifactRoot);
      const output = resolve(outputRoot, targetPath);
      if (!isWithin(output, outputRoot)) {
        throw new Error(`unsafe targetPath: ${file.targetPath}`);
      }
      await mkdir(resolve(output, ".."), { recursive: true });
      await copyFile(source, output);
      files.push({ path: targetPath, kind: "raw_evidence" });
    }

    return {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: request.sourceId,
      files,
      inputArtifactIds: [request.leadArtifactId, ...request.files.map((file) => file.artifactId)],
    };
  }
}

async function readRequest(path: string): Promise<SourceRequest> {
  const requestPath = await regularFile(path, "source request");
  let value: unknown;
  try {
    value = JSON.parse(await readFile(requestPath, "utf8"));
  } catch (error) {
    throw new Error(`cannot read source request: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!isRecord(value)) {
    throw new Error("source request must be an object");
  }
  rejectUnknownKeys(value, [
    "schemaVersion",
    "sourceContractVersion",
    "sourceId",
    "leadArtifactId",
    "artifactRoot",
    "files",
    "metadata",
  ], "source request");
  if (value.schemaVersion !== 1 || value.sourceContractVersion !== SOURCE_CONTRACT_VERSION) {
    throw new Error("source request has an unsupported contract version");
  }
  if (!nonEmptyString(value.sourceId) || !nonEmptyString(value.leadArtifactId) || !nonEmptyString(value.artifactRoot)) {
    throw new Error("source request requires sourceId, leadArtifactId, and artifactRoot");
  }
  if (!Array.isArray(value.files) || value.files.length === 0) {
    throw new Error("source request files must be a non-empty list");
  }
  const files = value.files.map((candidate, index) => {
    if (!isRecord(candidate)) {
      throw new Error(`source request files[${index}] must be an object`);
    }
    rejectUnknownKeys(candidate, ["artifactId", "sourcePath", "targetPath"], `source request files[${index}]`);
    if (!nonEmptyString(candidate.artifactId) || !nonEmptyString(candidate.sourcePath) || !nonEmptyString(candidate.targetPath)) {
      throw new Error(`source request files[${index}] requires artifactId, sourcePath, and targetPath`);
    }
    return {
      artifactId: candidate.artifactId as ArtifactId,
      sourcePath: candidate.sourcePath,
      targetPath: candidate.targetPath,
    };
  });
  return {
    schemaVersion: 1,
    sourceContractVersion: SOURCE_CONTRACT_VERSION,
    sourceId: value.sourceId,
    leadArtifactId: value.leadArtifactId as ArtifactId,
    artifactRoot: value.artifactRoot,
    files,
  };
}

async function emptyDestination(path: string): Promise<string> {
  if (!isAbsolute(path)) {
    throw new Error("destination must be absolute");
  }
  const resolved = resolve(path);
  try {
    const info = await lstat(resolved);
    if (info.isSymbolicLink() || !info.isDirectory()) {
      throw new Error("destination must be a non-symlink directory");
    }
    if ((await readdir(resolved)).length > 0) {
      throw new Error("destination must be empty");
    }
  } catch (error) {
    if (isMissing(error)) {
      await mkdir(resolved, { recursive: true });
    } else {
      throw error;
    }
  }
  return resolved;
}

async function regularDirectory(path: string, label: string): Promise<string> {
  if (!isAbsolute(path)) {
    throw new Error(`${label} must be absolute`);
  }
  const resolved = resolve(path);
  const info = await lstat(resolved);
  if (info.isSymbolicLink() || !info.isDirectory()) {
    throw new Error(`${label} must be a non-symlink directory`);
  }
  return await realpath(resolved);
}

async function regularFileWithin(path: string, root: string): Promise<string> {
  if (!isAbsolute(path)) {
    throw new Error("sourcePath must be absolute");
  }
  const resolved = resolve(path);
  // The physical path is the containment boundary: an intermediate symlink
  // can otherwise redirect an apparently in-root path to an arbitrary file
  // outside the artifact root. Do not use lexical containment here because a
  // caller may itself enter the physical root through a symlinked ancestor.
  await regularFile(resolved, "sourcePath");
  const physical = await realpath(resolved);
  if (!isWithin(physical, root)) {
    throw new Error("sourcePath must physically resolve beneath artifactRoot");
  }
  return physical;
}

async function regularFile(path: string, label: string): Promise<string> {
  const resolved = resolve(path);
  const info = await lstat(resolved);
  if (info.isSymbolicLink() || !info.isFile()) {
    throw new Error(`${label} must be a regular file`);
  }
  return resolved;
}

function safeTargetPath(path: string): string {
  if (!path || isAbsolute(path) || path.split(/[\\/]/u).some((part) => part === "" || part === "." || part === "..")) {
    throw new Error(`unsafe targetPath: ${path}`);
  }
  return path;
}

function isWithin(path: string, root: string): boolean {
  const difference = relative(root, path);
  return difference !== "" && difference !== ".." && !difference.startsWith(`..${sep}`) && !isAbsolute(difference);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function rejectUnknownKeys(value: Record<string, unknown>, allowed: readonly string[], label: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length > 0) {
    throw new Error(`${label} has unknown fields: ${unknown.sort().join(", ")}`);
  }
}

function isMissing(error: unknown): error is NodeJS.ErrnoException {
  return typeof error === "object" && error !== null && "code" in error && error.code === "ENOENT";
}

function throwIfAborted(signal: AbortSignal): void {
  if (signal.aborted) {
    throw signal.reason ?? new Error("source archive aborted");
  }
}
