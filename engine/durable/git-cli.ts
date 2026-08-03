import { execFile as execFileCallback } from "node:child_process";
import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import { isAbsolute, posix, relative, resolve, sep } from "node:path";
import { promisify } from "node:util";

import type {
  DurableGit,
  GitCheckpointRequest,
  GitRevisionBinding,
} from "./types.ts";

const execFile = promisify(execFileCallback);

export type GitInputMigrationCheckpointRequest = {
  readonly migrationId: string;
  readonly repositoryPaths: readonly string[];
  readonly manifestDigests: Readonly<Record<string, string>>;
};

export class DurableGitError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "DurableGitError";
    this.code = code;
  }
}

/**
 * Scoped Git authority for immutable revisions. It never stages or commits a
 * path outside the one revision supplied by DurableStore.
 */
export class GitCliDurableGit implements DurableGit {
  readonly repositoryRoot: string;

  constructor(repositoryRoot: string) {
    this.repositoryRoot = resolve(repositoryRoot);
  }

  async assertCommitted(
    repositoryPaths: readonly string[],
    expectedBinding?: GitRevisionBinding,
  ): Promise<void> {
    const paths = normalizePaths(repositoryPaths);
    await this.assertRepositoryRoot();
    if (expectedBinding !== undefined) {
      validateBindingShape(expectedBinding, paths);
      await this.git(["cat-file", "-e", `${expectedBinding.commitOid}^{commit}`]);
      await this.git(["merge-base", "--is-ancestor", expectedBinding.commitOid, "HEAD"]);
    }
    for (const path of paths) {
      await this.git(["ls-files", "--error-unmatch", "--", path]);
      await this.git(["diff", "--quiet", "--", path]);
      await this.git(["diff", "--cached", "--quiet", "--", path]);
      const headBlob = await this.objectAt("HEAD", path);
      const workingBlob = (await this.git(["hash-object", "--", path])).trim();
      if (workingBlob !== headBlob) {
        throw conflict(`working bytes for ${path} do not equal the committed blob`);
      }
      if (expectedBinding !== undefined) {
        const expectedBlob = expectedBinding.blobOids[path]!;
        const boundBlob = await this.objectAt(expectedBinding.commitOid, path);
        if (boundBlob !== expectedBlob || headBlob !== expectedBlob) {
          throw conflict(`Git binding for ${path} no longer matches HEAD and working bytes`);
        }
      }
    }
  }

  async checkpoint(request: GitCheckpointRequest): Promise<GitRevisionBinding> {
    const paths = normalizePaths(request.repositoryPaths);
    await this.assertRepositoryRoot();
    validateCheckpointScope(this.repositoryRoot, request.revisionDirectory, paths);
    const manifestPath = paths.find((path) => path.endsWith("/manifest.yaml"));
    if (manifestPath === undefined) {
      throw invalid("durable Git checkpoint has no manifest path");
    }
    const manifestBytes = await readFile(resolve(this.repositoryRoot, manifestPath));
    if (digest(manifestBytes) !== request.manifestDigest) {
      throw conflict("durable manifest changed before its Git checkpoint");
    }
    return this.checkpointPathSet({
      paths,
      anchorPath: manifestPath,
      title: `Checkpoint durable revision ${request.revision.revisionId}`,
      trailerName: "PromotionId",
      checkpointId: request.promotionId,
    });
  }

  async checkpointInputMigration(
    request: GitInputMigrationCheckpointRequest,
  ): Promise<GitRevisionBinding> {
    const paths = normalizePaths(request.repositoryPaths);
    await this.assertRepositoryRoot();
    if (paths.some((path) => !path.startsWith("inputs/"))) {
      throw invalid("input migration Git checkpoint contains a path outside inputs/");
    }
    const manifestPaths = Object.keys(request.manifestDigests).sort();
    if (
      manifestPaths.length === 0 ||
      manifestPaths.some((path) => !paths.includes(path) || !path.endsWith("/manifest.yaml")) ||
      Object.values(request.manifestDigests).some((value) => !/^sha256:[0-9a-f]{64}$/u.test(value))
    ) {
      throw invalid("input migration manifest digest set is invalid");
    }
    for (const path of manifestPaths) {
      if (digest(await readFile(resolve(this.repositoryRoot, path))) !== request.manifestDigests[path]) {
        throw conflict(`input manifest ${path} changed before its Git checkpoint`);
      }
    }
    return this.checkpointPathSet({
      paths,
      anchorPath: manifestPaths[0]!,
      title: `Migrate immutable input revisions ${request.migrationId}`,
      trailerName: "InputMigrationId",
      checkpointId: request.migrationId,
    });
  }

  private async checkpointPathSet(options: {
    readonly paths: readonly string[];
    readonly anchorPath: string;
    readonly title: string;
    readonly trailerName: string;
    readonly checkpointId: string;
  }): Promise<GitRevisionBinding> {
    const recovered = await this.recover(
      options.paths,
      options.anchorPath,
      options.trailerName,
      options.checkpointId,
    );
    if (recovered !== undefined) return recovered;
    const staged = await this.stagedPaths();
    const unrelated = staged.filter((path) => !options.paths.includes(path));
    if (unrelated.length > 0) {
      throw new DurableGitError(
        "DURABLE_GIT_SCOPE_CONFLICT",
        `refusing to checkpoint with unrelated staged paths: ${unrelated.join(", ")}`,
      );
    }
    for (const path of options.paths) {
      const info = await lstat(resolve(this.repositoryRoot, path));
      if (info.isSymbolicLink() || !info.isFile()) {
        throw invalid(`checkpoint path ${path} is not a regular file`);
      }
    }
    await this.git(["add", "--", ...options.paths]);
    const checkpointStaged = await this.stagedPaths();
    if (!sameSequence(checkpointStaged, options.paths)) {
      throw conflict("Git staged set does not equal the immutable checkpoint file set");
    }
    await this.git([
      "commit",
      "--only",
      "-m",
      options.title,
      "-m",
      `${options.trailerName}: ${options.checkpointId}`,
      "--",
      ...options.paths,
    ]);
    const commitOid = (await this.git(["rev-parse", "HEAD"])).trim();
    const binding = await this.bindingAt(commitOid, options.paths);
    await this.assertTrailer(commitOid, options.trailerName, options.checkpointId);
    await this.assertCommitted(options.paths, binding);
    return binding;
  }

  private async recover(
    paths: readonly string[],
    anchorPath: string,
    trailerName: string,
    checkpointId: string,
  ): Promise<GitRevisionBinding | undefined> {
    let commitOid: string;
    try {
      commitOid = (await this.git(["log", "-1", "--format=%H", "--", anchorPath])).trim();
    } catch {
      return undefined;
    }
    if (!validOid(commitOid)) return undefined;
    const message = await this.git(["show", "-s", "--format=%B", commitOid]);
    if (!hasTrailer(message, trailerName, checkpointId)) return undefined;
    const binding = await this.bindingAt(commitOid, paths);
    await this.assertCommitted(paths, binding);
    return binding;
  }

  private async bindingAt(
    commitOid: string,
    paths: readonly string[],
  ): Promise<GitRevisionBinding> {
    if (!validOid(commitOid)) throw conflict("Git returned an invalid commit OID");
    const entries = await Promise.all(paths.map(async (path) => [
      path,
      await this.objectAt(commitOid, path),
    ] as const));
    return { commitOid, blobOids: Object.fromEntries(entries) };
  }

  private async objectAt(commitOid: string, path: string): Promise<string> {
    const oid = (await this.git(["rev-parse", `${commitOid}:${path}`])).trim();
    if (!validOid(oid)) throw conflict(`Git returned an invalid blob OID for ${path}`);
    return oid;
  }

  private async assertTrailer(
    commitOid: string,
    trailerName: string,
    checkpointId: string,
  ): Promise<void> {
    const message = await this.git(["show", "-s", "--format=%B", commitOid]);
    if (!hasTrailer(message, trailerName, checkpointId)) {
      throw conflict(`Git commit ${commitOid} has no exact ${trailerName} trailer`);
    }
  }

  private async stagedPaths(): Promise<readonly string[]> {
    const stdout = await this.git(["diff", "--cached", "--name-only", "-z"]);
    return stdout.split("\0").filter(Boolean).sort();
  }

  private async assertRepositoryRoot(): Promise<void> {
    const actual = await realpath(resolve((await this.git(["rev-parse", "--show-toplevel"])).trim()));
    const configured = await realpath(this.repositoryRoot);
    if (actual !== configured) {
      throw invalid(`Git root ${actual} does not equal configured repository root`);
    }
  }

  private async git(args: readonly string[]): Promise<string> {
    try {
      const result = await execFile("git", ["-C", this.repositoryRoot, ...args], {
        encoding: "utf8",
        maxBuffer: 16 * 1024 * 1024,
      });
      return result.stdout;
    } catch (error) {
      throw new DurableGitError(
        "DURABLE_GIT_COMMAND_FAILED",
        `git ${args[0] ?? "command"} failed`,
        { cause: error },
      );
    }
  }
}

function normalizePaths(paths: readonly string[]): readonly string[] {
  if (paths.length === 0) throw invalid("Git path set must not be empty");
  const normalized = paths.map((path) => {
    if (
      path.includes("\\") || path.includes("\0") || path.includes("\n") ||
      isAbsolute(path) || posix.normalize(path) !== path ||
      path === "." || path.startsWith("../")
    ) {
      throw invalid(`Git path is not a safe repository-relative path: ${path}`);
    }
    return path;
  }).sort();
  if (new Set(normalized).size !== normalized.length) {
    throw invalid("Git path set contains duplicates");
  }
  return normalized;
}

function validateCheckpointScope(
  repositoryRoot: string,
  revisionDirectory: string,
  paths: readonly string[],
): void {
  const absolute = resolve(revisionDirectory);
  if (!absolute.startsWith(`${resolve(repositoryRoot)}${sep}`)) {
    throw invalid("durable revision directory escapes the repository");
  }
  const relativeDirectory = relative(repositoryRoot, absolute).split(sep).join("/");
  if (!relativeDirectory.startsWith("durable/") || paths.some((path) => !path.startsWith(`${relativeDirectory}/`))) {
    throw invalid("Git checkpoint paths are outside the one durable revision directory");
  }
}

function validateBindingShape(
  binding: GitRevisionBinding,
  paths: readonly string[],
): void {
  if (!validOid(binding.commitOid)) throw conflict("expected Git commit OID is invalid");
  const boundPaths = Object.keys(binding.blobOids).sort();
  if (
    !sameSequence(boundPaths, paths) ||
    Object.values(binding.blobOids).some((oid) => !validOid(oid))
  ) {
    throw conflict("expected Git blob binding does not equal the revision path set");
  }
}

function hasTrailer(message: string, trailerName: string, checkpointId: string): boolean {
  return message.split(/\r?\n/u).some((line) => line === `${trailerName}: ${checkpointId}`);
}

function sameSequence(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function validOid(value: string): boolean {
  return /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u.test(value);
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function invalid(message: string): DurableGitError {
  return new DurableGitError("DURABLE_GIT_INVALID", message);
}

function conflict(message: string): DurableGitError {
  return new DurableGitError("DURABLE_GIT_INTEGRITY_CONFLICT", message);
}
