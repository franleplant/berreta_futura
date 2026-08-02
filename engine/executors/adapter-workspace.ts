import { lstat, mkdir, mkdtemp, realpath, writeFile } from "node:fs/promises";
import { isAbsolute, join, relative, resolve, sep } from "node:path";

import type { ArtifactId } from "../contracts/index.ts";
import type { ArtifactReader } from "./types.ts";
import { SubprocessExecutionError } from "./subprocess.ts";

export type AdapterWorkspace = {
  readonly root: string;
  readonly inputRoot: string;
  readonly outputRoot: string;
  readonly requestPath: string;
};

export async function createAdapterWorkspace(
  workRoot: string,
  prefix: string,
): Promise<AdapterWorkspace> {
  const ownedRoot = resolve(workRoot);
  await mkdir(ownedRoot, { recursive: true, mode: 0o700 });
  const root = await mkdtemp(join(ownedRoot, `${prefix}-`));
  const inputRoot = join(root, "inputs");
  const outputRoot = join(root, "output");
  await mkdir(inputRoot, { mode: 0o700 });
  await mkdir(outputRoot, { mode: 0o700 });
  return {
    root,
    inputRoot,
    outputRoot,
    requestPath: join(root, "request.json"),
  };
}

export async function stageArtifact(
  artifacts: ArtifactReader,
  artifactId: ArtifactId,
  inputRoot: string,
  ordinal: number,
): Promise<string> {
  const directory = join(inputRoot, `input-${String(ordinal).padStart(6, "0")}`);
  await mkdir(directory, { mode: 0o700 });
  const path = join(directory, "payload");
  await writeFile(path, await artifacts.readBytes(artifactId), { mode: 0o600 });
  return path;
}

export async function writeAdapterRequest(
  requestPath: string,
  request: object,
): Promise<void> {
  await writeFile(requestPath, JSON.stringify(request), { encoding: "utf8", mode: 0o600 });
}

export async function requireOwnedOutputFile(
  outputRoot: string,
  adapterPath: string,
): Promise<string> {
  if (!adapterPath || isAbsolute(adapterPath) || adapterPath.includes("\0")) {
    throw permanentAdapterError(`adapter returned an unsafe output path: ${adapterPath}`);
  }
  try {
    const root = await realpath(outputRoot);
    const candidate = resolve(root, adapterPath);
    const lexicalRelation = relative(root, candidate);
    if (!isContainedRelation(lexicalRelation)) {
      throw permanentAdapterError(`adapter output escaped its owned root: ${adapterPath}`);
    }
    const metadata = await lstat(candidate);
    if (metadata.isSymbolicLink() || !metadata.isFile()) {
      throw permanentAdapterError(`adapter output is not a regular owned file: ${adapterPath}`);
    }
    const physical = await realpath(candidate);
    const physicalRelation = relative(root, physical);
    if (!isContainedRelation(physicalRelation)) {
      throw permanentAdapterError(`adapter output resolved outside its owned root: ${adapterPath}`);
    }
    return physical;
  } catch (error) {
    if (error instanceof SubprocessExecutionError) {
      throw error;
    }
    throw permanentAdapterError(
      `adapter output could not be opened as an owned file: ${adapterPath}`,
    );
  }
}

export async function readJsonArtifact(
  artifacts: ArtifactReader,
  artifactId: ArtifactId,
  label: string,
): Promise<unknown> {
  try {
    return JSON.parse(await artifacts.readText(artifactId));
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw permanentAdapterError(`${label} is not valid JSON: ${error.message}`);
    }
    throw error;
  }
}

export function requireSafeTargetPath(targetPath: string, label: string): void {
  if (!targetPath || isAbsolute(targetPath) || targetPath.includes("\0")) {
    throw permanentAdapterError(`${label} is not a safe relative path`);
  }
  const normalized = targetPath.replaceAll("\\", "/");
  if (normalized.split("/").some((part) => part === "" || part === "." || part === "..")) {
    throw permanentAdapterError(`${label} is not a safe relative path`);
  }
}

export function requireExactSequence(
  expected: readonly string[],
  actual: readonly string[],
  label: string,
): void {
  if (
    expected.length !== actual.length ||
    expected.some((value, index) => value !== actual[index])
  ) {
    throw permanentAdapterError(`${label} did not name the exact requested immutable inputs`);
  }
}

export function permanentAdapterError(message: string): SubprocessExecutionError {
  return new SubprocessExecutionError(message, "permanent", null, "");
}

function isContainedRelation(value: string): boolean {
  return (
    value !== "" &&
    value !== ".." &&
    !value.startsWith(`..${sep}`) &&
    !isAbsolute(value)
  );
}
