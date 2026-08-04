import assert from "node:assert/strict";
import { chmod, cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { promisify } from "node:util";
import { execFile as execFileCallback, spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import test, { type TestContext } from "node:test";

import type { ArtifactId, JsonObject, RevisionId } from "../contracts/index.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import { materializeNativeInputRevision } from "../durable/native-input-revision.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import { SQLiteDurableRunStore } from "@loops/core";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import { MagazineWorkflowEngine, MagazineWorkflowError } from "../workflows/magazine-workflow-engine.ts";
import type { WorkflowWaitContext } from "../workflows/internal-types.ts";
import { inspectRendererToolchain } from "../renderer-adapter/toolchain.ts";

const execFile = promisify(execFileCallback);
const PROJECT_ROOT = resolve(process.cwd());
const REVISION = "rev_20260803T000000000Z_aaaaaaaaaaaa" as RevisionId;

const tracerReviewerResponse = JSON.stringify({
  id: "resp_tracer_reviewer",
  object: "response",
  status: "completed",
  output: [{
    id: "msg_tracer_reviewer",
    type: "message",
    status: "completed",
    role: "assistant",
    content: [{
      type: "output_text",
      text: JSON.stringify({
        schemaVersion: "article-review-model-output/1",
        assessment: "pass",
        findings: [],
      }),
    }],
  }],
});

function guardedTest(name: string, fn: (context: TestContext) => Promise<void>): void {
  if (process.env.MAGAZINE_TRACER_REVIEWER_CHILD === "1") test(name, fn);
}

if (process.env.MAGAZINE_TRACER_REVIEWER_CHILD !== "1") {
  test("tracer workflow integration runs in one isolated reviewer child", { timeout: 150_000 }, async () => {
    const secret = "magazine-tracer-reviewer-secret";
    const childEnvironment: NodeJS.ProcessEnv = {
      ...process.env,
      MAGAZINE_TRACER_REVIEWER_CHILD: "1",
      MAGAZINE_TRACER_REVIEWER_SECRET: secret,
      MAGAZINE_TRACER_REVIEWER_RESPONSE: tracerReviewerResponse,
      NODE_TLS_REJECT_UNAUTHORIZED: "0",
    };
    delete childEnvironment.NODE_TEST_CONTEXT;
    const child = await runTracerReviewerChild([
      "--require",
      join(process.cwd(), "engine/test/fixtures/closed-reviewer-static-preload.cjs"),
      "--test",
      "--test-reporter=tap",
      new URL(import.meta.url).pathname,
    ], childEnvironment, 150_000);
    const output = `${child.stdout}\n${child.stderr}`;
    assert.equal(child.timedOut, false, output);
    assert.equal(child.error, undefined, output);
    assert.equal(child.exitCode, 0, output);
    // A clean exit is not enough: the parent must prove the isolated child
    // actually discovered and ran its TAP tests.
    assert.match(child.stdout, /^TAP version 13\s*$/mu, output);
    const plan = [...child.stdout.matchAll(/^1\.\.(\d+)\s*$/gmu)].at(-1)?.[1];
    assert.ok(plan !== undefined && Number(plan) > 0, output);
    const results = [...child.stdout.matchAll(/^(ok|not ok) \d+ - /gmu)];
    assert.equal(results.length, Number(plan), output);
    assert.equal(results.filter((match) => match[1] === "not ok").length, 0, output);
  });
}

type TracerChildResult = {
  readonly stdout: string;
  readonly stderr: string;
  readonly exitCode: number | null;
  readonly signal: NodeJS.Signals | null;
  readonly error?: Error;
  readonly timedOut: boolean;
};

function runTracerReviewerChild(
  args: readonly string[],
  env: NodeJS.ProcessEnv,
  timeoutMs: number,
): Promise<TracerChildResult> {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [...args], {
      cwd: process.cwd(),
      env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let error: Error | undefined;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, timeoutMs);
    child.stdout.on("data", (chunk: Buffer | string) => {
      const text = String(chunk);
      stdout += text;
      process.stdout.write(text);
    });
    child.stderr.on("data", (chunk: Buffer | string) => {
      const text = String(chunk);
      stderr += text;
      process.stderr.write(text);
    });
    child.once("error", (cause) => {
      error = cause instanceof Error ? cause : new Error(String(cause));
    });
    child.once("close", (exitCode, signal) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, exitCode, signal, ...(error === undefined ? {} : { error }), timedOut });
    });
  });
}

type Fixture = {
  readonly root: string;
  readonly engine: MagazineWorkflowEngine;
  readonly ledger: ArtifactLedger;
  readonly pipelineRef: Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>;
  readonly human: import("../contracts/workflow-run.ts").AuthenticatedHuman;
  readonly restorePath: () => void;
};

async function fixture(
  opener: "true" | "false" | "missing" = "true",
  resources: "valid" | "missing_review_resources" = "valid",
): Promise<Fixture> {
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

  const pipelineRef = { kind: "write_pipeline", editionId: "004", logicalId: "tracer", revisionId: REVISION } as const;
  const refs = {
    pipeline: pipelineRef,
    edition: { kind: "edition_spec", editionId: "004", logicalId: "tracer-edition", revisionId: REVISION } as const,
    capture: { kind: "source_capture", logicalId: "tracer", revisionId: REVISION } as const,
    extraction: { kind: "source_extraction", logicalId: "tracer", revisionId: REVISION } as const,
    profile: { kind: "article_production_profile", logicalId: "tracer-profile", revisionId: REVISION } as const,
    plan: { kind: "article_review_plan", logicalId: "tracer-plan", revisionId: REVISION } as const,
    writer: { kind: "prompt", logicalId: "tracer-writer", revisionId: REVISION } as const,
    evidence: { kind: "prompt", logicalId: "tracer-evidence", revisionId: REVISION } as const,
    editorial: { kind: "prompt", logicalId: "tracer-editorial", revisionId: REVISION } as const,
    rules: { kind: "policy", logicalId: "tracer-rules", revisionId: REVISION } as const,
    measurement: { kind: "policy", logicalId: "tracer-measurement", revisionId: REVISION } as const,
    schema: { kind: "review_material_schema", logicalId: "tracer-claim-map", revisionId: REVISION } as const,
  };
  const rawRef = (ref: InputRevisionRef): Record<string, string> => ({
    kind: ref.kind,
    logical_id: ref.logicalId,
    revision_id: ref.revisionId,
    ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }),
  });
  const articleDocuments = Array.from({ length: 7 }, (_, index) => ({
    article_id: index === 0 ? "tracer" : `tracer-${index + 1}`,
    content_mode: "faithful_synthesis",
    byline: "Source Author",
    source_ids: ["tracer"],
    source_authors: ["Source Author"],
    brief: "Rewrite the source extraction faithfully.",
    production_profile_revision: rawRef(refs.profile),
    parent: null,
    maximum_reader_pages: 7,
    model_policy: { default: { adapter: "test", model: "test" } },
  }));
  const translationParents = Object.fromEntries([
    ...articleDocuments.map((article) => article.article_id),
    "opening",
  ].map((pieceId) => [pieceId, null]));
  const pipelineDocument = {
    schema_version: 1,
    edition_id: "004",
    pipeline_id: "tracer",
    edition_spec: rawRef(refs.edition),
    sources: [{ source_id: "tracer", capture: rawRef(refs.capture), extraction: rawRef(refs.extraction) }],
    articles: articleDocuments,
    editorial: {
      editorial_id: "opening",
      brief: "Opening editorial.",
      writer_prompt: rawRef(refs.editorial),
      input_revisions: [rawRef(refs.rules)],
      parent: null,
      maximum_reader_pages: 1,
      model_policy: { default: { adapter: "test", model: "test" } },
    },
    translations: [{
      language: "es",
      source_language: "en",
      prompt: rawRef(refs.editorial),
      input_revisions: [rawRef(refs.rules)],
      parents: translationParents,
      maximum_reader_pages: 7,
      model_policy: { default: { adapter: "test", model: "test" } },
    }],
    images: Array.from({ length: 13 }, (_, index) => ({
      kind: "image",
      edition_id: "004",
      logical_id: `tracer-image-${index + 1}`,
      revision_id: REVISION,
    })),
    layout_inputs: [rawRef(refs.edition)],
    renderer_inputs: [{
      input: rawRef(refs.edition),
      payload_path: "edition.yaml",
      renderer_target_path: "editions/004/edition.yaml",
    }],
    render: {
      primary_language: "en",
      publication_name: "Magazine",
      renderer: "reportlab",
      configured_languages: ["en", "es"],
      studio_policy: "not_applicable",
    },
  };
  const inputRequests = [
    { ref: refs.edition, files: [{ path: "edition.yaml", mediaType: "application/yaml", content: "edition_id: '004'\n" }] },
    { ref: refs.capture, files: [{ path: "raw/record.yaml", mediaType: "application/yaml", content: "source: tracer\n" }] },
    { ref: refs.extraction, files: [{ path: "extracted.md", mediaType: "text/markdown", content: "# Source\n\nComplete source extraction.\n" }] },
    { ref: refs.profile, files: [{ path: "profile.json", mediaType: "application/json", content: JSON.stringify({
      schema_version: "article-production-profile/1",
      profile_id: "tracer-profile",
      format_id: "longform",
      writer: {
        prompt_revision: rawRef(refs.writer),
        result_contract_version: "article-writer-result/1",
        review_materials: [],
      },
      review_plan_revision: rawRef(refs.plan),
      writing_rules_revision: rawRef(refs.rules),
      writing_policy_revisions: [],
      revision_policy: { maximum_rewrites: 2 },
    }) }] },
    { ref: refs.plan, files: [{ path: "review-plan.json", mediaType: "application/json", content: JSON.stringify({
      schema_version: "article-review-plan/1",
      checks: [
        { kind: "model_review", id: "evidence", role: "article_review", prompt_revision: rawRef(refs.evidence), access: "source_aware", authority: "blocking" },
        { kind: "article_measurement", id: "measure_article", role: "measure_article", measurement_profile_revision: rawRef(refs.measurement), maximum_reader_pages: 7 },
      ],
      waves: [{ id: "panel", check_ids: ["evidence", "measure_article"], stop_after: "never" }],
    }) }] },
    { ref: refs.writer, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Write the article.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.evidence, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Check source evidence.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.editorial, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Write the opening.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.rules, files: [{ path: "policy.md", mediaType: "text/markdown", content: "Writing rules.\n" }] },
    { ref: refs.measurement, files: [{ path: "policy.md", mediaType: "text/markdown", content: "Measurement profile.\n" }] },
    { ref: refs.schema, files: [{ path: "schema.json", mediaType: "application/json", content: JSON.stringify({ schema_version: "claim-map/1", type: "object" }) }] },
    { ref: refs.pipeline, files: [{ path: "production.yaml", mediaType: "application/yaml", content: JSON.stringify(pipelineDocument) }] },
  ] as const;
  const materializedInputs = [] as Awaited<ReturnType<typeof materializeNativeInputRevision>>[];
  for (const request of inputRequests) {
    materializedInputs.push(await materializeNativeInputRevision(repositoryRoot, workRoot, {
      ref: request.ref,
      createdAt: "2026-08-03T00:00:00.000Z",
      parentRevisionId: null,
      files: request.files,
    }));
  }
  const git = new GitCliDurableGit(repositoryRoot);
  await git.checkpointInputMigration({
    migrationId: "test-input",
    repositoryPaths: materializedInputs.flatMap((input) => input.repositoryPaths),
    manifestDigests: Object.fromEntries(materializedInputs.map((input) => [input.repositoryPaths.find((path) => path.endsWith("/manifest.yaml"))!, input.manifestDigest])),
  });

  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));

  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollHuman({ principalId: "editor", capabilities: ["text_model"] });
  const credential = await authority.createCredentialProfile({ principalId: "editor", credentialProfileId: "editor-profile" });
  await authority.grant({ credentialProfileId: credential.credentialProfileId, grantId: "editor-grant", capabilities: ["text_model"] });
  const human = await authority.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });

  await authority.enrollWorker({ principalId: "tracer-source-aware", authority: "model", capabilities: ["text_model", "source_access"] });
  const awareCredential = await authority.createCredentialProfile({ principalId: "tracer-source-aware", credentialProfileId: "tracer-source-aware-profile" });
  await authority.grant({ credentialProfileId: awareCredential.credentialProfileId, grantId: "tracer-source-aware-grant", capabilities: ["text_model", "source_access"] });
  const sourceAwareReviewer = await authority.authenticate({ credentialProfileId: awareCredential.credentialProfileId, secret: awareCredential.secret });

  await authority.enrollWorker({ principalId: "tracer-source-blind", authority: "model", capabilities: ["text_model", "source_blind"] });
  const blindCredential = await authority.createCredentialProfile({ principalId: "tracer-source-blind", credentialProfileId: "tracer-source-blind-profile" });
  await authority.grant({ credentialProfileId: blindCredential.credentialProfileId, grantId: "tracer-source-blind-grant", capabilities: ["text_model", "source_blind"] });
  const sourceBlindReviewer = await authority.authenticate({ credentialProfileId: blindCredential.credentialProfileId, secret: blindCredential.secret });

  await authority.enrollWorker({ principalId: "tracer-measurement-tool", authority: "tool", capabilities: ["subprocess"] });
  const toolCredential = await authority.createCredentialProfile({ principalId: "tracer-measurement-tool", credentialProfileId: "tracer-measurement-profile" });
  await authority.grant({ credentialProfileId: toolCredential.credentialProfileId, grantId: "tracer-measurement-grant", capabilities: ["subprocess"] });
  const measurementTool = await authority.authenticate({ credentialProfileId: toolCredential.credentialProfileId, secret: toolCredential.secret });

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
    ...(resources === "valid" ? {
      articleReviewWorkers: { sourceAwareReviewer, sourceBlindReviewer, measurementTool },
      articleReviewCredentials: {
        schemaVersion: "closed-writer-credential-resource/1" as const,
        read: () => ({ OPENAI_API_KEY: process.env.MAGAZINE_TRACER_REVIEWER_SECRET ?? "magazine-tracer-reviewer-secret" }),
      },
    } : {}),
  });
  return {
    root,
    engine,
    ledger,
    pipelineRef,
    human,
    restorePath: () => {
      if (priorPath === undefined) delete process.env.PATH;
      else process.env.PATH = priorPath;
      if (priorOpener === undefined) delete process.env.MAGAZINE_TEST_OPENER;
      else process.env.MAGAZINE_TEST_OPENER = priorOpener;
    },
  };
}

async function start(f: Fixture): Promise<Awaited<ReturnType<MagazineWorkflowEngine["inspect"]>>> {
  return await f.engine.startArticleFromWritePipeline(f.pipelineRef, "tracer");
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

guardedTest("the fixed runtime pins the complete graph and committed config", async () => {
  const f = await fixture();
  try {
    const view = await start(f);
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

guardedTest("profile-backed launches reject unknown article identities", async () => {
  const f = await fixture();
  try {
    await assert.rejects(
      f.engine.startArticleFromWritePipeline(f.pipelineRef, "missing"),
      /no article missing/iu,
    );
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

guardedTest("missing review resources fail before ledger or Loops mutation", async () => {
  const f = await fixture("true", "missing_review_resources");
  try {
    await assert.rejects(
      start(f),
      /Article review runtime requires three authenticated workers/u,
    );
    assert.deepEqual(f.ledger.listArtifacts("run-tracer" as never), []);
    assert.equal(f.ledger.getRun("run-tracer" as never), undefined);
    const loops = new SQLiteDurableRunStore(join(f.root, "loops.sqlite"));
    try {
      assert.equal(loops.inspectRun("run-tracer"), null);
    } finally {
      loops.close();
    }
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

guardedTest("renderer opener fit is actual data and missing or false values are rejected", async (t) => {
  for (const opener of ["false", "missing"] as const) {
    await t.test(opener, async () => {
      const f = await fixture(opener);
      try {
        await assert.rejects(start(f), /opener fit/iu);
      } finally {
        f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
      }
    });
  }
});

guardedTest("a human decision resumes the same durable run and promotes through DurableStore and Git", async () => {
  const f = await fixture();
  try {
    const waiting = await start(f);
    const complete = await f.engine.decide(f.human, {
      runId: waiting.runId,
      offerId: waiting.activeOffer!.id,
      taskArtifactId: waiting.activeOffer!.taskArtifactId,
      inputArtifactIds: waiting.activeOffer!.inputArtifactIds,
      choice: "accept",
      rationale: "ready",
    });
    assert.equal(complete.status, "complete");
    assert.ok(complete.durableRevisionId);
    assert.ok(complete.decisionArtifactId);
    const decisionArtifact = f.ledger.requireArtifact(complete.decisionArtifactId);
    assert.equal(decisionArtifact.durableContext?.kind, "wait");
    assert.equal(decisionArtifact.durableContext && "waitId" in decisionArtifact.durableContext, true);
    assert.equal(decisionArtifact.durableContext && "attemptId" in decisionArtifact.durableContext, false);
    const offer = waiting.activeOffer!;
    const decisionTask = f.ledger.requireArtifact(offer.taskArtifactId);
    assert.deepEqual(decisionTask.parents, offer.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_evidence" })));
    const decision = f.ledger.requireDecisionForRun(waiting.runId);
    assert.deepEqual(decision.inputArtifactIds, offer.inputArtifactIds);
    const promotionArtifact = f.ledger.listArtifacts(waiting.runId).find((artifact) => artifact.kind === "article_durable_promotion");
    assert.ok(promotionArtifact);
    assert.deepEqual(promotionArtifact.parents, offer.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_evidence" })));
    assert.deepEqual(promotionArtifact.metadata.decisionEvidenceArtifactIds, offer.inputArtifactIds);
    const revisionRoot = join(f.root, "repo", "durable", "editions", "004", "articles", "tracer", "en", "revisions", complete.durableRevisionId!);
    assert.match(await readFile(join(revisionRoot, "manifest.yaml"), "utf8"), /engine_promotion/u);
  } finally {
    f.engine.close(); f.restorePath(); await rm(f.root, { recursive: true, force: true });
  }
});

guardedTest("inspect reconciles a wait answered just before a worker crash", async () => {
  const f = await fixture();
  try {
    const waiting = await start(f);
    const offer = waiting.activeOffer!;
    const authority = f.ledger.createHumanDecisionAuthority();
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

guardedTest("fake human objects cannot answer the exact offer", async () => {
  const f = await fixture();
  try {
    const waiting = await start(f);
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
