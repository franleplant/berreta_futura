import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { access, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import { writeBootstrapRepositoryFixture } from "./bootstrap-repository-fixture.ts";

const execFile = promisify(execFileCallback);
const repositoryRoot = resolve(import.meta.dirname, "../..");

test("low-level CLI defaults are isolated beneath .magazine/dev, never runs", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-engine-cli-default-root-"));
  try {
    await assert.rejects(
      execFile(process.execPath, [
        join(repositoryRoot, "engine/cli.ts"),
        "start",
        "missing-spec.json",
      ], { cwd: root, encoding: "utf8" }),
    );
    await access(join(root, ".magazine", "dev"));
    await access(join(root, ".magazine", "dev", "artifacts"));
    await assert.rejects(access(join(root, "runs")));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("CLI keeps issued local credentials out of stdout and accepts no caller principal flag", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-engine-cli-authority-"));
  try {
    const enrollmentPath = join(root, "human.json");
    const credentialProfilePath = join(root, "credential-profile.json");
    await writeFile(enrollmentPath, JSON.stringify({
      principalId: "local-editor",
      capabilities: ["source_access"],
    }));
    await writeFile(credentialProfilePath, JSON.stringify({
      principalId: "local-editor",
      credentialProfileId: "local-editor-credential",
    }));

    await execFile(process.execPath, [
      join(repositoryRoot, "engine/cli.ts"),
      "authority",
      "init",
    ], { cwd: root, encoding: "utf8" });
    await execFile(process.execPath, [
      join(repositoryRoot, "engine/cli.ts"),
      "authority",
      "enroll-human",
      enrollmentPath,
    ], { cwd: root, encoding: "utf8" });
    const issued = await execFile(process.execPath, [
      join(repositoryRoot, "engine/cli.ts"),
      "authority",
      "issue-credential",
      credentialProfilePath,
    ], { cwd: root, encoding: "utf8" });
    assert.equal(issued.stdout.includes("secret"), false);
    const issuedCredential = JSON.parse(issued.stdout) as { readonly credentialFile: string };
    const credential = JSON.parse(await readFile(issuedCredential.credentialFile, "utf8")) as {
      readonly secret: string;
    };
    assert.match(credential.secret, /^[A-Za-z0-9_-]{43}$/u);
    await assert.rejects(
      execFile(process.execPath, [
        join(repositoryRoot, "engine/cli.ts"),
        "human",
        "decide",
        "run_test",
        "offer_test",
        "decision.json",
        "--principal",
        "spoofed-editor",
      ], { cwd: root, encoding: "utf8" }),
      (error: unknown) => {
        assert.match(String((error as { readonly stderr?: unknown }).stderr), /Unknown option '--principal'/u);
        return true;
      },
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("edition list is a read-only canonical run inventory", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-cli-list-"));
  const outputRoot = join(root, "output");
  try {
    const { stdout, stderr } = await execFile(process.execPath, [
      join(repositoryRoot, "engine/cli.ts"),
      "edition",
      "list",
      "004",
      "--output-root",
      outputRoot,
    ], { cwd: root, encoding: "utf8" });

    assert.equal(stderr, "");
    assert.deepEqual(JSON.parse(stdout), {
      schemaVersion: "edition-run-list/1",
      editionKey: "004",
      runs: [],
    });
    await assert.rejects(access(join(root, ".magazine")));
    await assert.rejects(access(outputRoot));
    await assert.rejects(access(join(root, "runs")));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("edition plan requires an explicit bootstrap revision before touching runtime state", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-cli-plan-"));
  const outputRoot = join(root, "output");
  try {
    await assert.rejects(
      execFile(process.execPath, [
        join(repositoryRoot, "engine/cli.ts"),
        "edition",
        "plan",
        "004",
        "--output-root",
        outputRoot,
      ], { cwd: root, encoding: "utf8" }),
      (error: unknown) => {
        assert.match(
          String((error as { readonly stderr?: unknown }).stderr),
          /--bootstrap-revision REVISION/u,
        );
        return true;
      },
    );
    await assert.rejects(access(join(root, ".magazine")));
    await assert.rejects(access(outputRoot));
    await assert.rejects(access(join(root, "runs")));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("edition project-review requires explicit head, offer, and independent critic fences", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-cli-project-review-"));
  const outputRoot = join(root, "output");
  try {
    await assert.rejects(
      execFile(process.execPath, [
        join(repositoryRoot, "engine/cli.ts"),
        "edition",
        "project-review",
        "004",
        "run_00000000-0000-4000-8000-000000000001",
        "--expected-head",
        "13",
        "--expected-offer",
        "offer_00000000-0000-4000-8000-000000000001",
        "--output-root",
        outputRoot,
      ], { cwd: root, encoding: "utf8" }),
      (error: unknown) => {
        assert.match(
          String((error as { readonly stderr?: unknown }).stderr),
          /non-empty --critic-note TEXT/u,
        );
        return true;
      },
    );
    await assert.rejects(access(join(root, ".magazine")));
    await assert.rejects(access(outputRoot));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("edition plan resolves the explicit committed bootstrap without allocating a run", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-cli-plan-success-"));
  const outputRoot = join(root, "output");
  try {
    const fixture = await writeBootstrapRepositoryFixture(root);
    const { stdout, stderr } = await execFile(process.execPath, [
      join(repositoryRoot, "engine/cli.ts"),
      "edition",
      "plan",
      "004",
      "--bootstrap-revision",
      fixture.bootstrapRevision.revisionId,
      "--output-root",
      outputRoot,
    ], { cwd: root, encoding: "utf8" });

    assert.equal(stderr, "");
    const plan = JSON.parse(stdout) as {
      readonly schemaVersion: string;
      readonly bootstrapRevision: { readonly revisionId: string };
      readonly configuredLanguages: readonly string[];
      readonly renderer: {
        readonly editionPackageId: string;
        readonly editionManifestArtifactId: string;
        readonly referencedTargetCount: number;
        readonly inputs: readonly { readonly targetPath: string }[];
      };
      readonly ingestion: {
        readonly durableRevisionCount: number;
        readonly inputRevisionCount: number;
        readonly layoutInputRevisionCount: number;
        readonly rendererInputRevisionCount: number;
      };
    };
    assert.equal(plan.schemaVersion, "edition-bootstrap-plan/1");
    assert.equal(plan.bootstrapRevision.revisionId, fixture.bootstrapRevision.revisionId);
    assert.deepEqual(plan.configuredLanguages, ["en", "es"]);
    assert.equal(plan.renderer.editionPackageId, "fixture-edition");
    assert.match(plan.renderer.editionManifestArtifactId, /^art_bootstrap_input_/u);
    assert.equal(plan.renderer.referencedTargetCount, 8);
    assert.deepEqual(plan.ingestion, {
      durableRevisionCount: 5,
      inputRevisionCount: 6,
      layoutInputRevisionCount: 1,
      rendererInputRevisionCount: 3,
      importedArtifactCount: 14,
    });
    assert.deepEqual(
      plan.renderer.inputs.map((input) => input.targetPath).sort(),
      [
        "editions/fixture-edition/art/cover.png",
        "editions/fixture-edition/articles/systems.md",
        "editions/fixture-edition/edition.yaml",
        "editions/fixture-edition/manuscript/editorial.md",
        "editions/fixture-edition/translations/es/articles/systems.md",
        "editions/fixture-edition/translations/es/edition.yaml",
        "editions/fixture-edition/translations/es/manuscript/editorial.md",
        "library/sources/fixture-source/extracted.md",
        "library/sources/fixture-source/record.yaml",
      ].sort(),
    );
    await assert.rejects(access(join(root, ".magazine")));
    await assert.rejects(access(outputRoot));
    await assert.rejects(access(join(root, "runs")));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
