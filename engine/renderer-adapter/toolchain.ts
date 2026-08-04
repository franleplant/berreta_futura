import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import { execFile } from "node:child_process";
import { isAbsolute, resolve } from "node:path";
import { promisify } from "node:util";

import type { RendererToolchainResource } from "../contracts/workflow-run.ts";

const execFileAsync = promisify(execFile);

/** Secret-free identity facts for the exact renderer executables. */
export type RendererToolchainIdentity = RendererToolchainResource["expected"];

const PYTHON_FACTS_SCRIPT =
  "import json,platform,sys; print(json.dumps({'pythonVersion':platform.python_version(),'pythonImplementation':platform.python_implementation(),'pythonCacheTag':sys.implementation.cache_tag,'platform':f'{sys.platform}-{platform.machine()}'}))";

/**
 * Validate the configured executable resources, probe their exact bytes and
 * runtime facts, and compare them with the caller's approved identity.
 *
 * Executable paths are deliberately not returned. They are operational
 * handles only; durable manifests carry the hash and version facts below.
 */
export async function probeRendererToolchain(
  resource: RendererToolchainResource,
): Promise<RendererToolchainIdentity> {
  const actual = await inspectRendererToolchain(resource.uvExecutable, resource.pythonExecutable);
  assertToolchainIdentity(resource.expected, actual);
  return actual;
}

/** Probe an executable pair before an approval record exists. */
export async function inspectRendererToolchain(
  uvExecutable: string,
  pythonExecutable: string,
): Promise<RendererToolchainIdentity> {
  const uv = await inspectExecutable(uvExecutable, "uv");
  const python = await inspectExecutable(pythonExecutable, "Python");
  const [uvVersion, pythonFacts] = await Promise.all([
    probeUvVersion(uv.realPath),
    probePythonFacts(python.realPath),
  ]);
  return {
    uvSha256: uv.sha256,
    uvVersion,
    pythonSha256: python.sha256,
    pythonVersion: pythonFacts.pythonVersion,
    pythonImplementation: pythonFacts.pythonImplementation,
    pythonCacheTag: pythonFacts.pythonCacheTag,
    platform: pythonFacts.platform,
  };
}

/** Compare only secret-free facts, never operational paths. */
export function assertToolchainIdentity(
  expected: RendererToolchainIdentity,
  actual: RendererToolchainIdentity,
): void {
  const fields: readonly (keyof RendererToolchainIdentity)[] = [
    "uvSha256",
    "uvVersion",
    "pythonSha256",
    "pythonVersion",
    "pythonImplementation",
    "pythonCacheTag",
    "platform",
  ];
  for (const field of fields) {
    if (expected[field] !== actual[field]) {
      throw new Error(`renderer toolchain ${field} does not match the approved identity`);
    }
  }
}

/** Ensure a resource path is absolute, non-symlink, regular, and byte-pinned. */
export async function inspectExecutable(
  configuredPath: string,
  label: string,
): Promise<{ readonly realPath: string; readonly sha256: `sha256:${string}` }> {
  if (!isAbsolute(configuredPath)) {
    throw new Error(`${label} executable path must be absolute`);
  }
  const path = resolve(configuredPath);
  const stat = await lstat(path);
  if (!stat.isFile() || stat.isSymbolicLink()) {
    throw new Error(`${label} executable must be a regular non-symlink file`);
  }
  const canonical = await realpath(path);
  const canonicalStat = await lstat(canonical);
  if (!canonicalStat.isFile() || canonicalStat.isSymbolicLink()) {
    throw new Error(`${label} executable resolves to a non-regular file`);
  }
  const bytes = await readFile(canonical);
  const digest = createHash("sha256").update(bytes).digest("hex");
  return { realPath: canonical, sha256: `sha256:${digest}` };
}

async function probeUvVersion(path: string): Promise<string> {
  const result = await execFileAsync(path, ["--version"], {
    cwd: "/",
    maxBuffer: 1024 * 1024,
  });
  const output = String(result.stdout).trim();
  const match = /^uv\s+(.+)$/u.exec(output);
  if (match === null || match[1] === undefined || match[1].trim().length === 0) {
    throw new Error("uv --version did not return the expected version record");
  }
  return match[1].trim();
}

async function probePythonFacts(path: string): Promise<{
  readonly pythonVersion: string;
  readonly pythonImplementation: string;
  readonly pythonCacheTag: string;
  readonly platform: `${NodeJS.Platform}-${string}`;
}> {
  const result = await execFileAsync(path, ["-I", "-c", PYTHON_FACTS_SCRIPT], {
    cwd: "/",
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
    },
    maxBuffer: 1024 * 1024,
  });
  let parsed: unknown;
  try {
    parsed = JSON.parse(String(result.stdout));
  } catch (error) {
    throw new Error("Python -I facts probe did not return JSON", { cause: error });
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("Python -I facts probe returned a non-object");
  }
  const facts = parsed as Record<string, unknown>;
  if (
    typeof facts.pythonVersion !== "string" ||
    typeof facts.pythonImplementation !== "string" ||
    typeof facts.pythonCacheTag !== "string" ||
    typeof facts.platform !== "string" ||
    !/^[a-z0-9_]+-[a-z0-9_.-]+$/iu.test(facts.platform)
  ) {
    throw new Error("Python -I facts probe returned malformed facts");
  }
  return {
    pythonVersion: facts.pythonVersion,
    pythonImplementation: facts.pythonImplementation,
    pythonCacheTag: facts.pythonCacheTag,
    platform: facts.platform as `${NodeJS.Platform}-${string}`,
  };
}
