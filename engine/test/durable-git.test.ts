import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import type { PromotionId, RevisionId } from "../contracts/index.ts";
import {
  DurableGitError,
  GitCliDurableGit,
  type GitCheckpointRequest,
} from "../durable/index.ts";

const execFile = promisify(execFileCallback);
const REVISION_ID = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;
const PROMOTION_ID = "promotion_git-fixture" as PromotionId;

test("Git durable checkpoint commits only one revision and recovers the PromotionId", async () => {
  const root = await gitRepository("mag-durable-git-");
  try {
    const fixture = await revisionFixture(root, "first");
    await writeFile(join(root, "untracked.txt"), "leave me alone\n", "utf8");
    const git = new GitCliDurableGit(root);

    const first = await git.checkpoint(fixture.request);
    const retried = await git.checkpoint(fixture.request);
    assert.deepEqual(retried, first);
    assert.equal(await command(root, ["rev-list", "--count", "HEAD"]), "2");
    assert.equal(await command(root, ["status", "--short", "--", "untracked.txt"]), "?? untracked.txt");
    assert.match(await command(root, ["show", "-s", "--format=%B", first.commitOid]), /PromotionId: promotion_git-fixture/u);

    await writeFile(join(root, "later.txt"), "later\n", "utf8");
    await command(root, ["add", "--", "later.txt"]);
    await command(root, ["commit", "-m", "Later unrelated commit"]);
    await git.assertCommitted(fixture.request.repositoryPaths, first);

    await writeFile(join(root, fixture.payloadPath), "mutated after binding\n", "utf8");
    await assert.rejects(
      git.assertCommitted(fixture.request.repositoryPaths, first),
      (error: unknown) => error instanceof DurableGitError,
    );
    await command(root, ["add", "--", fixture.payloadPath]);
    await command(root, ["commit", "-m", "Illegal durable mutation"]);
    await assert.rejects(
      git.assertCommitted(fixture.request.repositoryPaths, first),
      /no longer matches HEAD/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("Git durable checkpoint refuses unrelated staged state and path escape", async () => {
  const root = await gitRepository("mag-durable-git-scope-");
  try {
    const fixture = await revisionFixture(root, "second");
    const git = new GitCliDurableGit(root);
    await writeFile(join(root, "unrelated.txt"), "staged user work\n", "utf8");
    await command(root, ["add", "--", "unrelated.txt"]);
    await assert.rejects(
      git.checkpoint(fixture.request),
      (error: unknown) => error instanceof DurableGitError && error.code === "DURABLE_GIT_SCOPE_CONFLICT",
    );
    await assert.rejects(
      git.assertCommitted(["../escape"]),
      (error: unknown) => error instanceof DurableGitError && error.code === "DURABLE_GIT_INVALID",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

async function revisionFixture(
  root: string,
  logicalId: string,
): Promise<{ readonly request: GitCheckpointRequest; readonly payloadPath: string }> {
  const relativeDirectory = `durable/editions/004/articles/${logicalId}/en/revisions/${REVISION_ID}`;
  const revisionDirectory = join(root, relativeDirectory);
  const payloadPath = `${relativeDirectory}/manuscript.md`;
  const manifestPath = `${relativeDirectory}/manifest.yaml`;
  const manifest = Buffer.from("schema_version: 1\n", "utf8");
  await mkdir(revisionDirectory, { recursive: true });
  await writeFile(join(root, payloadPath), "# Exact durable manuscript\n", "utf8");
  await writeFile(join(root, manifestPath), manifest);
  return {
    payloadPath,
    request: {
      promotionId: PROMOTION_ID,
      revision: {
        kind: "article",
        editionId: "004",
        logicalId,
        language: "en",
        revisionId: REVISION_ID,
      },
      revisionDirectory,
      repositoryPaths: [manifestPath, payloadPath].sort(),
      manifestDigest: digest(manifest),
    },
  };
}

async function gitRepository(prefix: string): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), prefix));
  await command(root, ["init", "--quiet"]);
  await command(root, ["config", "user.email", "durable-test@example.invalid"]);
  await command(root, ["config", "user.name", "Durable Test"]);
  await writeFile(join(root, "README.md"), "fixture\n", "utf8");
  await command(root, ["add", "--", "README.md"]);
  await command(root, ["commit", "--quiet", "-m", "Fixture root"]);
  return root;
}

async function command(root: string, args: readonly string[]): Promise<string> {
  const result = await execFile("git", ["-C", root, ...args], { encoding: "utf8" });
  return result.stdout.trim();
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}
