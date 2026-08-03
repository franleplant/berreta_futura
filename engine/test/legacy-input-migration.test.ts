import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import type { RevisionId } from "../contracts/index.ts";
import {
  GitCliDurableGit,
  LegacyInputMigrationError,
  migrateLegacyInputs,
  type LegacyInputMigrationPlan,
} from "../durable/index.ts";

const execFile = promisify(execFileCallback);
const EXTRACTION_REVISION = "rev_20260801T010203004Z_aaaaaaaaaaaa" as RevisionId;
const SPEC_REVISION = "rev_20260801T010204004Z_bbbbbbbbbbbb" as RevisionId;
const BOOTSTRAP_REVISION = "rev_20260801T010205004Z_cccccccccccc" as RevisionId;

test("legacy input migration creates exact immutable revisions and recovers its Git checkpoint", async () => {
  const root = await repositoryFixture();
  try {
    const git = new GitCliDurableGit(root);
    const plan = await migrationPlan(root);
    await writeFile(join(root, "untracked.txt"), "leave untouched\n", "utf8");
    const first = await migrateLegacyInputs(
      root,
      join(root, ".magazine/004/migration/work/inputs"),
      plan,
      git,
    );
    const retried = await migrateLegacyInputs(
      root,
      join(root, ".magazine/004/migration/work/inputs"),
      plan,
      git,
    );
    assert.deepEqual(retried, first);
    assert.equal(await readFile(join(
      root,
      `inputs/sources/source-one/extractions/${EXTRACTION_REVISION}/extracted.md`,
    ), "utf8"), "# Legacy extraction\n");
    assert.match(await readFile(join(
      root,
      `inputs/editions/004/specs/main/revisions/${SPEC_REVISION}/manifest.yaml`,
    ), "utf8"), /edition_id: "?004"?/u);
    assert.match(await readFile(join(
      root,
      `inputs/editions/004/specs/fresh-v2/revisions/${BOOTSTRAP_REVISION}/manifest.yaml`,
    ), "utf8"), /generated_by_migration:\n\s+basis: fresh v2 role and revision binding/u);
    assert.equal(await command(root, ["rev-list", "--count", "HEAD"]), "2");
    assert.match(await command(root, ["show", "-s", "--format=%B", first.gitBinding.commitOid]), /InputMigrationId: edition4-inputs/u);
    await access(join(root, "legacy/source-one.md"));
    assert.equal(await command(root, ["status", "--short", "--", "untracked.txt"]), "?? untracked.txt");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("legacy input migration rejects dirty sources, unsafe targets, and conflicting immutable IDs", async () => {
  const root = await repositoryFixture();
  try {
    const git = new GitCliDurableGit(root);
    await writeFile(join(root, "legacy/source-one.md"), "dirty\n", "utf8");
    await assert.rejects(
      migrateLegacyInputs(root, join(root, ".magazine/work"), await migrationPlan(root), git),
      (error: unknown) => error instanceof LegacyInputMigrationError &&
        error.code === "INPUT_MIGRATION_SOURCE_UNCOMMITTED",
    );
    await command(root, ["restore", "--", "legacy/source-one.md"]);

    const unsafe = await migrationPlan(root);
    await assert.rejects(
      migrateLegacyInputs(root, join(root, ".magazine/work"), {
        ...unsafe,
        sourceGitBinding: {
          commitOid: unsafe.sourceGitBinding.commitOid,
          blobOids: {
            "legacy/source-one.md": unsafe.sourceGitBinding.blobOids["legacy/source-one.md"]!,
          },
        },
        entries: [{
          ...unsafe.entries[0]!,
          ref: {
            kind: "source_capture",
            logicalId: "source-one",
            revisionId: EXTRACTION_REVISION,
          },
          files: [{
            sourcePath: "legacy/source-one.md",
            targetPath: "capture.md",
            mediaType: "text/markdown",
          }],
        }],
      }, git),
      /source capture payloads must live under raw/u,
    );

    await migrateLegacyInputs(root, join(root, ".magazine/work"), await migrationPlan(root), git);
    const manifestPath = join(
      root,
      `inputs/sources/source-one/extractions/${EXTRACTION_REVISION}/manifest.yaml`,
    );
    await writeFile(manifestPath, `${await readFile(manifestPath, "utf8")}tampered: true\n`, "utf8");
    await assert.rejects(
      migrateLegacyInputs(root, join(root, ".magazine/work"), await migrationPlan(root), git),
      (error: unknown) => error instanceof LegacyInputMigrationError &&
        error.code === "INPUT_MIGRATION_CONFLICT",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

async function migrationPlan(root: string): Promise<LegacyInputMigrationPlan> {
  const sourcePaths = ["legacy/edition.yaml", "legacy/source-one.md"];
  const commitOid = await command(root, ["rev-parse", "HEAD"]);
  return {
    schemaVersion: "legacy-input-migration/1",
    migrationId: "edition4-inputs",
    sourceGitBinding: {
      commitOid,
      blobOids: Object.fromEntries(await Promise.all(sourcePaths.map(async (path) => [
        path,
        await command(root, ["rev-parse", `${commitOid}:${path}`]),
      ] as const))),
    },
    entries: [{
      ref: {
        kind: "source_extraction",
        logicalId: "source-one",
        revisionId: EXTRACTION_REVISION,
      },
      createdAt: "2026-08-01T01:02:03.004Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "legacy/source-one.md",
        targetPath: "extracted.md",
        mediaType: "text/markdown",
      }],
    }, {
      ref: {
        kind: "edition_spec",
        editionId: "004",
        logicalId: "main",
        revisionId: SPEC_REVISION,
      },
      createdAt: "2026-08-01T01:02:04.004Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "legacy/edition.yaml",
        targetPath: "edition.yaml",
        mediaType: "application/yaml",
      }],
    }, {
      ref: {
        kind: "run_bootstrap",
        editionId: "004",
        logicalId: "fresh-v2",
        revisionId: BOOTSTRAP_REVISION,
      },
      createdAt: "2026-08-01T01:02:05.004Z",
      parentRevisionId: null,
      files: [{
        content: "prompt_set: fresh_v2_prompt_set\n",
        generationBasis: "fresh v2 role and revision binding",
        targetPath: "bootstrap.yaml",
        mediaType: "application/yaml",
      }],
    }],
  };
}

async function repositoryFixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "mag-legacy-input-migration-"));
  await command(root, ["init", "--quiet"]);
  await command(root, ["config", "user.email", "migration-test@example.invalid"]);
  await command(root, ["config", "user.name", "Migration Test"]);
  await mkdir(join(root, "legacy"));
  await writeFile(join(root, "legacy/source-one.md"), "# Legacy extraction\n", "utf8");
  await writeFile(join(root, "legacy/edition.yaml"), "edition_id: '004'\n", "utf8");
  await command(root, ["add", "--", "legacy/source-one.md", "legacy/edition.yaml"]);
  await command(root, ["commit", "--quiet", "-m", "Legacy fixture"]);
  return root;
}

async function command(root: string, args: readonly string[]): Promise<string> {
  const result = await execFile("git", ["-C", root, ...args], { encoding: "utf8" });
  return result.stdout.trim();
}
