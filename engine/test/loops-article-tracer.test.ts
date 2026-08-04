import assert from "node:assert/strict";
import { chmod, cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { promisify } from "node:util";
import { execFile as execFileCallback } from "node:child_process";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import test from "node:test";

import type { ArtifactId, ArticleStartRequest, JsonObject, RevisionId } from "../contracts/index.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import { materializeNativeInputRevision } from "../durable/native-input-revision.ts";
import { SQLiteDurableRunStore } from "@loops/core";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import { HumanDecisionAuthority } from "../workflow-authority/human-decisions.ts";
import { MagazineWorkflowEngine, MagazineWorkflowError } from "../workflows/magazine-workflow-engine.ts";
import type { WorkflowWaitContext } from "../workflows/internal-types.ts";
import { inspectRendererToolchain } from "../renderer-adapter/toolchain.ts";

const execFile = promisify(execFileCallback);
const PROJECT_ROOT = resolve(process.cwd());
const REVISION = "rev_20260803T000000000Z_aaaaaaaaaaaa" as RevisionId;

type Fixture = {
  readonly root: string;
  readonly engine: MagazineWorkflowEngine;
  readonly ledger: ArtifactLedger;
  readonly request: ArticleStartRequest;
  readonly human: import("../contracts/workflow-run.ts").AuthenticatedHuman;
  readonly restorePath: () => void;
};

async function fixture(opener: "true" | "false" | "missing" = "true"): Promise<Fixture> {
  const root = await mkdtemp(join(tmpdir(), "mag-loops-tracer-"));
  const projectRoot = join(root, "project");
  await makeProjectOverlay(projectRoot);
  const repositoryRoot = join(root, "repo");
  const workRoot = join(root, "work");
  await mkdir(repositoryRoot, { recursive: true });
  await mkdir(workRoot, { recursive: true });
  await execFile("git", ["init", "-b", "main"], { cwd: repositoryRoot });
  await execFile("git", ["config", "user.email", "test@example.com"], { cwd: repositoryRoot });
  await execFile("git", ["config", "user.name", "Magazine Test"], { cwd: repositoryRoot });

  const input = await materializeNativeInputRevision(repositoryRoot, workRoot, {
    ref: { kind: "policy", logicalId: "article-policy", revisionId: REVISION },
    createdAt: "2026-08-03T00:00:00.000Z",
    parentRevisionId: null,
    files: [{ path: "policy.md", mediaType: "text/markdown", content: "policy" }],
  });
  const git = new GitCliDurableGit(repositoryRoot);
  await git.checkpointInputMigration({
    migrationId: "test-input",
    repositoryPaths: input.repositoryPaths,
    manifestDigests: { [input.repositoryPaths.find((path) => path.endsWith("/manifest.yaml"))!]: input.manifestDigest },
  });

  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  const sourceId = "art-source" as ArtifactId;
  const manuscriptId = "art-seed-manuscript" as ArtifactId;
  const profileId = "art-profile" as ArtifactId;
  ledger.createArtifact({
    id: sourceId,
    kind: "source_extraction",
    schemaVersion: "source/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: "evidence" },
    metadata: { revisionId: REVISION },
  });
  ledger.createArtifact({
    id: manuscriptId,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "imported",
    payload: { kind: "text", text: "# immutable manuscript" },
    parents: [{ artifactId: sourceId, relation: "source" }],
  });
  ledger.createArtifact({
    id: profileId,
    kind: "article_measurement_profile",
    schemaVersion: "article-measurement-profile/1",
    mediaType: "application/json",
    origin: "imported",
    payload: {
      kind: "json",
      value: {
        schemaVersion: 1,
        rendererContractVersion: "magazine-renderer/1",
        editionId: "004",
        articleId: "tracer",
        primaryLanguage: "en",
        publicationName: "Magazine",
        renderer: "reportlab",
        manuscriptArtifactId: manuscriptId,
        maximumReaderPages: 7,
        inputs: [{ artifactId: manuscriptId, targetPath: "article.md" }],
      } as unknown as JsonObject,
    },
  });

  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollHuman({ principalId: "editor", capabilities: ["text_model"] });
  const credential = await authority.createCredentialProfile({ principalId: "editor", credentialProfileId: "editor-profile" });
  await authority.grant({ credentialProfileId: credential.credentialProfileId, grantId: "editor-grant", capabilities: ["text_model"] });
  const human = await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });

  const executableDirectory = join(root, "bin");
  await mkdir(executableDirectory, { recursive: true });
  const fakeUv = join(executableDirectory, "uv");
  await writeFile(fakeUv, `#!/usr/bin/env node
if (process.argv[2] === "--version") { process.stdout.write("uv fixture-1\\n"); process.exit(0); }
const fs = require("node:fs");
const request = JSON.parse(fs.readFileSync(process.argv.at(-2), "utf8"));
const ids = request.inputs.map((input) => input.artifactId);
const articleId = request.articleId;
const opener = process.env.MAGAZINE_TEST_OPENER;
const layout = { language: request.primaryLanguage, totalPages: 2, editorialPages: 0, articlePages: { [articleId]: 2 }, figureCount: 0, criticResult: "not_run" };
if (opener !== "missing") layout.articleOpenerFits = { [articleId]: opener === "true" };
process.stdout.write(JSON.stringify({ schemaVersion: 1, rendererContractVersion: "magazine-renderer/1", editionId: request.editionId, files: [], layouts: [layout], inputArtifactIds: ids, tailArtFacts: {} }));
`, "utf8");
  await chmod(fakeUv, 0o700);
  const fakePython = join(executableDirectory, "python");
  await writeFile(fakePython, `#!/usr/bin/env node
process.stdout.write(JSON.stringify({ pythonVersion: "3.12.11", pythonImplementation: "CPython", pythonCacheTag: "cpython-312", platform: "darwin-arm64" }));
`, "utf8");
  await chmod(fakePython, 0o700);
  const expectedToolchain = await inspectRendererToolchain(fakeUv, fakePython);
  await writeFile(
    join(projectRoot, "engine", "workflows", "article-runtime-identity.json"),
    `${JSON.stringify(await (await import("../workflows/renderer-identity.ts")).computeRendererIdentity(projectRoot, {
      uvExecutable: fakeUv,
      pythonExecutable: fakePython,
      expected: expectedToolchain,
    }), null, 2)}\n`,
    "utf8",
  );
  const priorPath = process.env.PATH;
  const priorOpener = process.env.MAGAZINE_TEST_OPENER;
  process.env.PATH = `${executableDirectory}${delimiter}${priorPath ?? ""}`;
  process.env.MAGAZINE_TEST_OPENER = opener;

  const request: ArticleStartRequest = {
    articleId: "tracer",
    editionId: "004",
    logicalItem: { kind: "article", editionId: "004", logicalId: "tracer", language: "en" },
    language: "en",
    manuscriptArtifactId: manuscriptId,
    measurementProfileArtifactId: profileId,
    inputBindings: [{ artifactId: sourceId, revision: { kind: "policy", logicalId: "article-policy", revisionId: REVISION } }],
    expectedParentRevisionId: null,
  };
  const engine = new MagazineWorkflowEngine({
    databasePath: join(root, "magazine.sqlite"),
    loopsDatabasePath: join(root, "loops.sqlite"),
    repositoryRoot,
    workRoot,
    projectRoot,
    renderer: {
      workDirectory: join(root, "renderer"),
      projectRoot,
      toolchain: { uvExecutable: fakeUv, pythonExecutable: fakePython, expected: expectedToolchain },
    },
  });
  return {
    root,
    engine,
    ledger,
    request,
    human,
    restorePath: () => {
      if (priorPath === undefined) delete process.env.PATH;
      else process.env.PATH = priorPath;
      if (priorOpener === undefined) delete process.env.MAGAZINE_TEST_OPENER;
      else process.env.MAGAZINE_TEST_OPENER = priorOpener;
    },
  };
}

async function makeProjectOverlay(projectRoot: string): Promise<void> {
  await mkdir(join(projectRoot, "engine", "workflows"), { recursive: true });
  await cp(join(PROJECT_ROOT, "src", "magazine"), join(projectRoot, "src", "magazine"), { recursive: true });
  await cp(join(PROJECT_ROOT, "pyproject.toml"), join(projectRoot, "pyproject.toml"));
  await cp(join(PROJECT_ROOT, "uv.lock"), join(projectRoot, "uv.lock"));
  await cp(join(PROJECT_ROOT, "package-lock.json"), join(projectRoot, "package-lock.json"));
  await execFile("git", ["init", "-q", "-b", "main"], { cwd: projectRoot });
  await execFile("git", ["config", "user.email", "test@example.com"], { cwd: projectRoot });
  await execFile("git", ["config", "user.name", "Magazine Test"], { cwd: projectRoot });
  await execFile("git", ["add", "pyproject.toml", "uv.lock", "src/magazine"], { cwd: projectRoot });
  await execFile("git", ["commit", "-qm", "renderer fixture"], { cwd: projectRoot });
  for (const entry of await readdir(join(PROJECT_ROOT, "engine"), { withFileTypes: true })) {
    if (entry.name === "workflows") continue;
    await symlink(join(PROJECT_ROOT, "engine", entry.name), join(projectRoot, "engine", entry.name), entry.isDirectory() ? "dir" : undefined);
  }
  for (const entry of await readdir(join(PROJECT_ROOT, "engine", "workflows"), { withFileTypes: true })) {
    if (entry.name === "article-runtime-identity.json") continue;
    await symlink(join(PROJECT_ROOT, "engine", "workflows", entry.name), join(projectRoot, "engine", "workflows", entry.name), entry.isDirectory() ? "dir" : undefined);
  }
  await symlink(join(PROJECT_ROOT, "node_modules"), join(projectRoot, "node_modules"), "dir");
}

test("the fixed runtime pins the complete graph and committed config", async () => {
  const f = await fixture();
  try {
    const view = await f.engine.startArticle(f.request);
    assert.equal(view.status, "waiting");
    const pin = view.workflowPin as unknown as { execution: { configPath?: string; configHash?: string }; source: { entryPath: string } };
    assert.equal(pin.execution.configPath, "engine/workflows/article-runtime-identity.json");
    assert.match(String(pin.execution.configHash), /^sha256:/u);
    assert.equal(pin.source.entryPath, "engine/workflows/article-loops-entry.ts");
    assert.ok(view.artifacts.some((artifactId) => String(artifactId) === `art-manuscript-${view.runId}`));
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

test("exact input bindings are required and bind revision metadata", async () => {
  const f = await fixture();
  try {
    await assert.rejects(
      f.engine.startArticle({ ...f.request, inputBindings: [{ ...f.request.inputBindings[0]!, revision: { ...f.request.inputBindings[0]!.revision, revisionId: "rev_20260803T000000001Z_bbbbbbbbbbbb" as RevisionId } }] }),
      /exact revision metadata/iu,
    );
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

test("renderer opener fit is actual data and missing or false values are rejected", async (t) => {
  for (const opener of ["false", "missing"] as const) {
    await t.test(opener, async () => {
      const f = await fixture(opener);
      try {
        await assert.rejects(f.engine.startArticle(f.request), /opener fit/iu);
      } finally {
        f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
      }
    });
  }
});

test("a human decision resumes the same durable run and promotes through DurableStore and Git", async () => {
  const f = await fixture();
  try {
    const waiting = await f.engine.startArticle(f.request);
    const complete = await f.engine.decide(f.human, {
      runId: waiting.runId,
      offerId: waiting.activeOffer!.id,
      taskArtifactId: waiting.activeOffer!.taskArtifactId,
      inputArtifactIds: waiting.activeOffer!.inputArtifactIds,
      choice: "accept",
      rationale: "ready",
    });
    assert.equal(complete.status, "complete");
    assert.equal(complete.durableRevisionId, f.request.revisionId ?? complete.durableRevisionId);
    assert.ok(complete.decisionArtifactId);
    const decisionArtifact = f.ledger.requireArtifact(complete.decisionArtifactId);
    assert.equal(decisionArtifact.durableContext?.kind, "wait");
    assert.equal(decisionArtifact.durableContext && "waitId" in decisionArtifact.durableContext, true);
    assert.equal(decisionArtifact.durableContext && "attemptId" in decisionArtifact.durableContext, false);
    const revisionRoot = join(f.root, "repo", "durable", "editions", "004", "articles", "tracer", "en", "revisions", complete.durableRevisionId!);
    assert.match(await readFile(join(revisionRoot, "manifest.yaml"), "utf8"), /engine_promotion/u);
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

test("inspect reconciles a wait answered just before a worker crash", async () => {
  const f = await fixture();
  try {
    const waiting = await f.engine.startArticle(f.request);
    const offer = waiting.activeOffer!;
    const authority = new HumanDecisionAuthority({ ledger: f.ledger });
    const loops = new SQLiteDurableRunStore(join(f.root, "loops.sqlite"));
    const inspection = loops.inspectRun(waiting.runId)!;
    const pending = inspection.waits.find((candidate) => candidate.waitId === offer.waitId);
    const invocation = pending === undefined
      ? undefined
      : inspection.invocations.find((candidate) => candidate.invocationId === pending.invocationId);
    if (pending === undefined || invocation === undefined) throw new Error("expected pending article decision wait");
    const durableContext: WorkflowWaitContext = {
      runId: waiting.runId,
      invocationId: invocation.invocationId,
      workflowName: invocation.workflowName,
      workflowVersion: invocation.workflowVersion,
      ...(invocation.workflowPin === undefined ? {} : { workflowPin: invocation.workflowPin as unknown as JsonObject }),
      callId: pending.callId,
      waitId: pending.waitId,
      key: pending.key,
      kind: "wait",
    };
    const decision = await authority.decide(f.human, {
      runId: waiting.runId,
      offerId: offer.id,
      taskArtifactId: offer.taskArtifactId,
      inputArtifactIds: offer.inputArtifactIds,
      choice: "drop",
      rationale: "crash replay",
    }, durableContext);
    try {
      await loops.answerWait({ runId: waiting.runId, waitId: offer.waitId!, answer: { decisionArtifactId: decision.artifactId } });
    } finally {
      loops.close();
    }
    const recovered = await f.engine.inspect(waiting.runId);
    assert.equal(recovered.activeOffer, undefined);
    assert.equal(recovered.decisionArtifactId, decision.artifactId);
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

test("fake human objects cannot answer the exact offer", async () => {
  const f = await fixture();
  try {
    const waiting = await f.engine.startArticle(f.request);
    await assert.rejects(f.engine.decide({ describe: async () => ({ authority: "human", principalId: "editor", credentialProfileId: "editor-profile", grantIds: ["editor-grant"] }) } as never, {
      runId: waiting.runId,
      offerId: waiting.activeOffer!.id,
      taskArtifactId: waiting.activeOffer!.taskArtifactId,
      inputArtifactIds: waiting.activeOffer!.inputArtifactIds,
      choice: "accept",
      rationale: "no",
    }), /AuthorizedWorker/iu);
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

void MagazineWorkflowError;
