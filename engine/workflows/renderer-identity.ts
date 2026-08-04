import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { lstat, readdir, readFile } from "node:fs/promises";
import { join, relative, resolve, sep } from "node:path";
import { promisify } from "node:util";

import type { RendererToolchainResource } from "../contracts/workflow-run.ts";
import {
  probeRendererToolchain,
  type RendererToolchainIdentity,
} from "../renderer-adapter/toolchain.ts";

/** The immutable identity of the renderer closure used by article runs. */
export const RENDERER_RUNTIME_IDENTITY_SCHEMA = "magazine-article-runtime-identity/1" as const;
export const RENDERER_ADAPTER_IDENTITY = "python-uv-locked/1" as const;
export const RENDERER_ENTRYPOINT_IDENTITY = "magazine.engine_render_bridge:main" as const;
export const RENDERER_CONTRACT_IDENTITY = "magazine-renderer/1" as const;
export const AUTHORITY_POLICY_IDENTITY = "local-authority-exact-offer/1" as const;
export const PROMOTION_ADAPTER_IDENTITY = "durable-store-git-cli/1" as const;

const LOOPS_DEFAULT_BACKEND = "magazine-no-agent" as const;
const LOOPS_DEFAULT_MODEL = "none" as const;

export type RendererIdentityFile = {
  readonly path: string;
  readonly sizeBytes: number;
  readonly sha256: string;
};

export type { RendererToolchainIdentity } from "../renderer-adapter/toolchain.ts";

export type RendererIdentity = {
  readonly schemaVersion: typeof RENDERER_RUNTIME_IDENTITY_SCHEMA;
  readonly graphHash: string;
  readonly manifestHash: string;
  readonly rendererAdapter: typeof RENDERER_ADAPTER_IDENTITY;
  readonly rendererEntrypoint: typeof RENDERER_ENTRYPOINT_IDENTITY;
  readonly rendererContractVersion: typeof RENDERER_CONTRACT_IDENTITY;
  readonly authorityPolicy: typeof AUTHORITY_POLICY_IDENTITY;
  readonly promotionAdapter: typeof PROMOTION_ADAPTER_IDENTITY;
  readonly defaultBackend: typeof LOOPS_DEFAULT_BACKEND;
  readonly defaultModel: typeof LOOPS_DEFAULT_MODEL;
  readonly budget: { readonly total: null; readonly unit: "calls" };
  readonly files: readonly RendererIdentityFile[];
  /** Secret-free facts for the exact operational renderer toolchain. */
  readonly toolchain?: RendererToolchainIdentity;
};

type RendererIdentityWithoutHash = Omit<RendererIdentity, "manifestHash">;

const execFileAsync = promisify(execFile);

/**
 * Compute the renderer identity from the project checkout.
 *
 * Only the locked Python project and the regular files in `src/magazine` are
 * in the closure. Paths are sorted and the graph digest uses NUL framing so
 * neither path boundaries nor arbitrary source bytes can be ambiguous.
 */
export async function computeRendererIdentity(
  projectRoot: string,
  toolchain?: RendererToolchainResource,
): Promise<RendererIdentity> {
  const root = resolve(projectRoot);
  const files = await collectRendererFiles(root);
  const graph = createHash("sha256");
  const records: RendererIdentityFile[] = [];
  for (const file of files) {
    const bytes = await readFile(join(root, file));
    const digest = createHash("sha256").update(bytes).digest("hex");
    records.push({ path: file, sizeBytes: bytes.byteLength, sha256: `sha256:${digest}` });
    graph.update(file, "utf8");
    graph.update(Buffer.of(0));
    graph.update(bytes);
    graph.update(Buffer.of(0));
  }
  const unsigned: RendererIdentityWithoutHash = {
    schemaVersion: RENDERER_RUNTIME_IDENTITY_SCHEMA,
    graphHash: `sha256:${graph.digest("hex")}`,
    rendererAdapter: RENDERER_ADAPTER_IDENTITY,
    rendererEntrypoint: RENDERER_ENTRYPOINT_IDENTITY,
    rendererContractVersion: RENDERER_CONTRACT_IDENTITY,
    authorityPolicy: AUTHORITY_POLICY_IDENTITY,
    promotionAdapter: PROMOTION_ADAPTER_IDENTITY,
    defaultBackend: LOOPS_DEFAULT_BACKEND,
    defaultModel: LOOPS_DEFAULT_MODEL,
    budget: { total: null, unit: "calls" },
    files: records,
    ...(toolchain === undefined ? {} : { toolchain: await probeRendererToolchain(toolchain) }),
  };
  return {
    ...unsigned,
    manifestHash: hashManifest(unsigned),
  };
}

/** Read the tracked manifest and prove that it describes the current checkout. */
export async function readVerifiedRendererIdentity(
  projectRoot: string,
  manifestPath = "engine/workflows/article-runtime-identity.json",
  toolchain?: RendererToolchainResource,
): Promise<RendererIdentity> {
  const root = resolve(projectRoot);
  const path = resolve(root, manifestPath);
  const parsed = JSON.parse(await readFile(path, "utf8")) as unknown;
  const stored = parseRendererIdentity(parsed);
  const computed = await computeRendererIdentity(root, toolchain);
  assertRendererIdentity(stored, computed, "tracked renderer identity");
  if (stored.manifestHash !== hashManifest(stored)) {
    throw new Error("tracked renderer identity manifestHash does not match its contents");
  }
  return stored;
}

/** Hash the exact manifest bytes used as Loops' configHash. */
export async function hashRendererIdentityManifest(
  projectRoot: string,
  manifestPath = "engine/workflows/article-runtime-identity.json",
): Promise<string> {
  const bytes = await readFile(resolve(resolve(projectRoot), manifestPath));
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

/** Assert that two renderer identities are byte-for-byte equivalent. */
export function assertRendererIdentity(
  expected: RendererIdentity,
  actual: RendererIdentity,
  label = "renderer identity",
): void {
  if (stableJson(expected) !== stableJson(actual)) {
    throw new Error(`${label} mismatch: the renderer closure is not the pinned identity`);
  }
}

/** The canonical hash preimage for an identity manifest. */
export function hashManifest(identity: RendererIdentityWithoutHash | RendererIdentity): string {
  const { manifestHash: _ignored, ...unsigned } = identity as RendererIdentity;
  return `sha256:${createHash("sha256").update(stableJson(unsigned), "utf8").digest("hex")}`;
}

function parseRendererIdentity(value: unknown): RendererIdentity {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("renderer identity manifest must be a JSON object");
  }
  const candidate = value as Record<string, unknown>;
  if (candidate.schemaVersion !== RENDERER_RUNTIME_IDENTITY_SCHEMA) {
    throw new Error("renderer identity manifest has an unsupported schema version");
  }
  const files = candidate.files;
  if (!Array.isArray(files)) throw new Error("renderer identity manifest files must be an array");
  const parsedFiles: RendererIdentityFile[] = files.map((file, index) => {
    if (typeof file !== "object" || file === null || Array.isArray(file)) {
      throw new Error(`renderer identity file ${index} is not an object`);
    }
    const item = file as Record<string, unknown>;
    if (typeof item.path !== "string" || typeof item.sizeBytes !== "number" || !Number.isSafeInteger(item.sizeBytes) || item.sizeBytes < 0 || typeof item.sha256 !== "string") {
      throw new Error(`renderer identity file ${index} is malformed`);
    }
    return { path: item.path, sizeBytes: item.sizeBytes, sha256: item.sha256 };
  });
  const parsed = candidate as unknown as RendererIdentity;
  if (
    parsed.rendererAdapter !== RENDERER_ADAPTER_IDENTITY ||
    parsed.rendererEntrypoint !== RENDERER_ENTRYPOINT_IDENTITY ||
    parsed.rendererContractVersion !== RENDERER_CONTRACT_IDENTITY ||
    parsed.authorityPolicy !== AUTHORITY_POLICY_IDENTITY ||
    parsed.promotionAdapter !== PROMOTION_ADAPTER_IDENTITY ||
    parsed.defaultBackend !== LOOPS_DEFAULT_BACKEND ||
    parsed.defaultModel !== LOOPS_DEFAULT_MODEL ||
    typeof parsed.graphHash !== "string" ||
    typeof parsed.manifestHash !== "string"
  ) {
    throw new Error("renderer identity manifest has an invalid semantic identity");
  }
  if (parsed.budget === undefined || parsed.budget.total !== null || parsed.budget.unit !== "calls") {
    throw new Error("renderer identity manifest has an invalid durable budget");
  }
  const sorted = [...parsedFiles].sort((a, b) => comparePaths(a.path, b.path));
  if (stableJson(sorted) !== stableJson(parsedFiles)) {
    throw new Error("renderer identity files are not sorted");
  }
  const toolchain = candidate.toolchain === undefined
    ? undefined
    : parseToolchainIdentity(candidate.toolchain);
  return {
    ...parsed,
    files: parsedFiles,
    ...(toolchain === undefined ? {} : { toolchain }),
  };
}

function parseToolchainIdentity(value: unknown): RendererToolchainIdentity {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("renderer identity toolchain must be an object");
  }
  const candidate = value as Record<string, unknown>;
  const fields = [
    "uvSha256",
    "uvVersion",
    "pythonSha256",
    "pythonVersion",
    "pythonImplementation",
    "pythonCacheTag",
    "platform",
  ] as const;
  for (const field of fields) {
    if (typeof candidate[field] !== "string" || candidate[field].length === 0) {
      throw new Error(`renderer identity toolchain field ${field} is malformed`);
    }
  }
  return {
    uvSha256: candidate.uvSha256 as `sha256:${string}`,
    uvVersion: candidate.uvVersion as string,
    pythonSha256: candidate.pythonSha256 as `sha256:${string}`,
    pythonVersion: candidate.pythonVersion as string,
    pythonImplementation: candidate.pythonImplementation as string,
    pythonCacheTag: candidate.pythonCacheTag as string,
    platform: candidate.platform as `${NodeJS.Platform}-${string}`,
  };
}

async function collectRendererFiles(root: string): Promise<string[]> {
  const tracked = await listTrackedRendererFiles(root);
  const required = ["pyproject.toml", "uv.lock"] as const;
  const violations: string[] = [];

  for (const path of required) {
    if (!tracked.has(path)) violations.push(path);
  }

  const trackedSource = [...tracked.keys()].filter((path) => path.startsWith("src/magazine/"));
  const sourceRoot = join(root, "src", "magazine");
  await inspectSourceClosure(root, sourceRoot, new Set(trackedSource), violations);

  for (const path of [...tracked.keys()].filter((candidate) => candidate.startsWith("src/magazine/"))) {
    const absolute = join(root, path);
    try {
      await assertRegularFile(absolute, path);
    } catch {
      violations.push(path);
    }
  }

  for (const path of required) {
    if (tracked.has(path)) {
      try {
        await assertRegularFile(join(root, path), path);
      } catch {
        violations.push(path);
      }
    }
  }

  const uniqueViolations = [...new Set(violations)].sort(comparePaths);
  if (uniqueViolations.length > 0) {
    throw new Error(
      `renderer identity source closure has unapproved or missing paths: ${uniqueViolations.join(", ")}`,
    );
  }

  return [...tracked.keys()]
    .filter((path) => path === "pyproject.toml" || path === "uv.lock" || path.startsWith("src/magazine/"))
    .sort(comparePaths);
}

async function listTrackedRendererFiles(root: string): Promise<Map<string, string>> {
  let stdout: string;
  try {
    ({ stdout } = await execFileAsync(
      "git",
      ["ls-files", "--cached", "--stage", "-z", "--", "pyproject.toml", "uv.lock", "src/magazine"],
      { cwd: root, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 },
    ));
  } catch (error) {
    throw new Error("renderer identity requires a Git checkout with an accessible index", { cause: error });
  }
  const tracked = new Map<string, string>();
  for (const record of stdout.split("\0")) {
    if (record.length === 0) continue;
    const separator = record.indexOf("\t");
    if (separator < 0) throw new Error("renderer identity received malformed Git path data");
    const metadata = record.slice(0, separator).split(" ");
    const path = record.slice(separator + 1);
    const mode = metadata[0];
    if (mode === undefined || path.length === 0) throw new Error("renderer identity received malformed Git path data");
    tracked.set(path, mode);
  }
  return tracked;
}

async function inspectSourceClosure(
  root: string,
  directory: string,
  tracked: ReadonlySet<string>,
  violations: string[],
): Promise<void> {
  await assertDirectory(directory, toProjectPath(root, directory));
  const entries = await readdir(directory, { withFileTypes: true });
  entries.sort((a, b) => comparePaths(a.name, b.name));
  for (const entry of entries) {
    const next = join(directory, entry.name);
    const relativePath = toProjectPath(root, next);
    if (entry.isDirectory()) {
      const prefix = `${relativePath}/`;
      const hasTrackedDescendant = [...tracked].some((path) => path.startsWith(prefix));
      if (!hasTrackedDescendant) {
        violations.push(relativePath);
      }
      await inspectSourceClosure(root, next, tracked, violations);
      continue;
    }
    if (!entry.isFile() || !tracked.has(relativePath)) {
      violations.push(relativePath);
      continue;
    }
    try {
      await assertRegularFile(next, relativePath);
    } catch {
      violations.push(relativePath);
    }
  }
}

async function assertRegularFile(path: string, relativePath: string): Promise<void> {
  const stat = await lstat(path);
  if (!stat.isFile()) throw new Error(`renderer identity refuses non-regular path ${relativePath}`);
}

async function assertDirectory(path: string, relativePath: string): Promise<void> {
  const stat = await lstat(path);
  if (!stat.isDirectory()) throw new Error(`renderer identity refuses non-directory path ${relativePath}`);
}

function toProjectPath(root: string, path: string): string {
  return relative(root, path).split(sep).join("/");
}

function stableJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => stableJson(item)).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`).join(",")}}`;
}

function comparePaths(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}
