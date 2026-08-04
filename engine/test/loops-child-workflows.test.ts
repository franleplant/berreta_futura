import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import test from "node:test";

import {
  createDurableWorkflowPin,
  createRuntime,
  SQLiteDurableRunStore,
  type Runtime,
  type WorkflowDescriptor,
  type WorkflowGlobals,
} from "@loops/core";
import { buildDurableWorkflowPin } from "@loops/workflow";
import { invokeWorkflow, type WorkflowContext } from "loops";
import { z } from "zod/v3";

import {
  createMagazineWorkflowResolver,
  magazineArticleWorkflowRef,
  MAGAZINE_ARTICLE_WORKFLOW_ENTRY,
  MAGAZINE_ARTICLE_WORKFLOW_NAME,
} from "../workflows/magazine-workflow-resolver.ts";
import type { ArticleWorkflowPorts } from "../workflows/internal-types.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import { buildAuthenticatedArticleLaunchArgs } from "../workflows/article-launch.ts";
import type { RendererIdentity } from "../workflows/renderer-identity.ts";
import {
  GitCliDurableGit,
  materializeNativeInputRevision,
  type InputRevisionRef,
} from "../durable/index.ts";
import type { ArticleExecutionId, JsonObject, RevisionId, RunId } from "../contracts/index.ts";

const PROJECT_ROOT = resolve(process.cwd());
const execFile = promisify(execFileCallback);

test("the Magazine resolver returns the pinned source-graph descriptor", async () => {
  const resolver = createMagazineWorkflowResolver({
    projectRoot: PROJECT_ROOT,
    articlePorts: {} as ArticleWorkflowPorts,
  });
  const descriptor = await resolver(
    magazineArticleWorkflowRef(),
    {},
    { currentWorkflowBaseDir: () => PROJECT_ROOT } as unknown as Runtime,
  ) as WorkflowDescriptor;
  const pin = await buildDurableWorkflowPin({
    cwd: PROJECT_ROOT,
    scriptPath: MAGAZINE_ARTICLE_WORKFLOW_ENTRY,
    configPath: "engine/workflows/article-runtime-identity.json",
    config: { defaultBackend: "magazine-no-agent" },
    backendSelection: "magazine-no-agent",
  });

  assert.equal(descriptor.name, MAGAZINE_ARTICLE_WORKFLOW_NAME);
  assert.equal(descriptor.version, pin.source.graphHash);
  assert.equal(descriptor.baseDir, join(PROJECT_ROOT, "engine", "workflows"));
  await assert.rejects(
    async () => await resolver({ scriptPath: "engine/workflows/not-the-article.ts" }, {}, { currentWorkflowBaseDir: () => PROJECT_ROOT } as unknown as Runtime),
    /only permits/u,
  );
});

test("the shared article launch preserves only authenticated material and stable article identity", async () => {
  const rootLaunch = await buildProfileLaunch("article-root");
  const childLaunch = await buildProfileLaunch("article-child", "edition-root");
  try {
    assert.equal(rootLaunch.articleExecutionId, childLaunch.articleExecutionId);
    assert.deepEqual(rootLaunch.args.entry, childLaunch.args.entry);
    assert.equal(rootLaunch.args.articleId, childLaunch.args.articleId);
    assert.equal(rootLaunch.args.editionId, childLaunch.args.editionId);
    assert.notEqual(rootLaunch.runId, childLaunch.runId);
    assert.equal(rootLaunch.ledger.requireRun(rootLaunch.runId).loopsRunId, rootLaunch.runId);
    assert.equal(childLaunch.ledger.requireRun(childLaunch.runId).loopsRunId, "edition-root");
    for (const launch of [rootLaunch, childLaunch]) {
      const entry = launch.args.entry;
      const materialArtifactIds = entry.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId));
      assert.ok(materialArtifactIds.length > 0);
      assert.equal(new Set(materialArtifactIds).size, materialArtifactIds.length);
      assert.deepEqual(
        entry.inputBindings.map((binding) => binding.artifactId),
        entry.materializedInputs.map((input) => input.artifacts[0]!.artifactId),
      );
      assert.ok(entry.materializedInputs.some((input) => input.ref.kind === "source_extraction"));
      for (const input of entry.materializedInputs) {
        for (const material of input.artifacts) {
          const artifact = launch.ledger.requireArtifact(material.artifactId);
          assert.deepEqual(artifact.metadata.inputRevision, input.ref);
        }
      }
      assert.equal(Object.isFrozen(entry), true);
      assert.equal(Object.isFrozen(entry.materializedInputs), true);
      assert.equal(Object.isFrozen(entry.inputBindings), true);
      assert.throws(() => {
        (entry.materializedInputs as Array<unknown>).pop();
      }, /read only|Cannot delete property|object is not extensible/iu);
    }
  } finally {
    rootLaunch.close();
    childLaunch.close();
  }
});

test("durable child workflows keep separate invocation and call identities while waiting independently", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-loops-children-"));
  const storePath = join(root, "loops.sqlite");
  const runId = "edition-root";
  const pin = createDurableWorkflowPin({
    source: { entryPath: "engine/test/loops-child-workflows.test.ts", graphHash: "sha256:children-graph" },
    dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:children-lock" },
    execution: { backend: "children-test" },
  });
  const childRef = { scriptPath: "./child-workflow.ts" } as const;
  const backend = {
    name: "children-test",
    capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
    async run(): Promise<never> { throw new Error("agent calls are not part of this test"); },
  };
  const resolver = async (nameOrRef: string | { readonly scriptPath: string }, _args: unknown, _runtime: Runtime): Promise<WorkflowDescriptor> => {
    assert.deepEqual(nameOrRef, childRef);
    return {
      name: "test-child",
      version: "sha256:test-child-graph",
      baseDir: root,
      run: async (childArgs: unknown, runtime: unknown): Promise<unknown> => {
        const globals = (runtime as Runtime).globals;
        return await invokeWorkflow(
          { ...globals, args: childArgs },
          async (context: WorkflowContext<{ readonly childId: string }>) => {
            const identity = context.durableContext();
            const answer = await context.wait(`hold-${context.input.childId}`, {
              schema: z.object({ token: z.string() }).strict() as never,
              request: { childId: context.input.childId },
            }) as { readonly token: string };
            return {
              childId: context.input.childId,
              invocationId: identity?.invocationId,
              callId: identity?.callId,
              token: answer.token,
            };
          },
        );
      },
    };
  };

  const run = async (store: SQLiteDurableRunStore): Promise<unknown> => {
    const runtime = createRuntime({
      backend,
      defaultBackend: backend.name,
      durable: {
        store,
        runId,
        workflowName: "test-root",
        workflowPin: pin,
        args: { kind: "edition" },
      },
      workflowResolver: resolver,
    });
    return await runtime.run(async (globals: WorkflowGlobals) => await globals.parallel([
      () => globals.workflow(childRef, { childId: "a" }, { key: "article-a" }),
      () => globals.workflow(childRef, { childId: "b" }, { key: "article-b" }),
    ]));
  };

  let store: SQLiteDurableRunStore | undefined;
  try {
    store = new SQLiteDurableRunStore(storePath);
    await assert.rejects(run(store), /suspend|wait|pending|durable/iu);
    const first = store.inspectRun(runId);
    assert.ok(first);
    const children = first.invocations.filter((invocation) => invocation.parentInvocationId !== undefined);
    assert.equal(children.length, 2);
    assert.notEqual(children[0]!.invocationId, children[1]!.invocationId);
    assert.deepEqual(new Set(children.map((child) => child.workflowName)), new Set(["test-child"]));
    const childWaits = first.waits.filter((wait) => wait.status === "pending");
    assert.equal(childWaits.length, 2);
    assert.notEqual(childWaits[0]!.waitId, childWaits[1]!.waitId);
    assert.deepEqual(new Set(childWaits.map((wait) => wait.invocationId)), new Set(children.map((child) => child.invocationId)));
    const childCalls = first.calls.filter((call) => call.kind === "workflow");
    assert.equal(childCalls.length, 2);
    assert.notEqual(childCalls[0]!.callId, childCalls[1]!.callId);

    const firstWait = childWaits.find((wait) => (wait.request as { readonly childId?: unknown }).childId === "a");
    const secondWait = childWaits.find((wait) => (wait.request as { readonly childId?: unknown }).childId === "b");
    assert.ok(firstWait);
    assert.ok(secondWait);
    store.answerWait({ runId, waitId: firstWait.waitId, answer: { token: "a" } });
    await assert.rejects(run(store), /suspend|wait|pending|durable/iu);
    const middle = store.inspectRun(runId);
    assert.ok(middle);
    assert.equal(middle.waits.find((wait) => wait.waitId === firstWait.waitId)?.status, "answered");
    assert.equal(middle.waits.find((wait) => wait.waitId === secondWait.waitId)?.status, "pending");

    store.answerWait({ runId, waitId: secondWait.waitId, answer: { token: "b" } });
    const result = await run(store) as readonly [{ readonly childId: string }, { readonly childId: string }];
    assert.deepEqual(result.map((item) => item.childId), ["a", "b"]);
    assert.equal(store.inspectRun(runId)?.run.status, "completed");
  } finally {
    store?.close();
    await rm(root, { recursive: true, force: true });
  }
});

type ProfileLaunch = {
  readonly root: string;
  readonly ledger: ArtifactLedger;
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly args: import("../workflows/internal-types.ts").ArticleRuntimeStartArgs;
  readonly close: () => void;
};

async function buildProfileLaunch(runIdValue: string, loopsRunId?: string): Promise<ProfileLaunch> {
  const root = await mkdtemp(join(tmpdir(), "mag-loops-launch-"));
  const repositoryRoot = join(root, "repo");
  const workRoot = join(root, "work");
  await execFile("git", ["init", "-q", "-b", "main", repositoryRoot]);
  await mkdir(workRoot, { recursive: true });
  await execFile("git", ["config", "user.email", "test@example.com"], { cwd: repositoryRoot });
  await execFile("git", ["config", "user.name", "Magazine Test"], { cwd: repositoryRoot });
  const revision = "rev_20260804T000000000Z_aaaaaaaaaaaa" as RevisionId;
  const refs = {
    pipeline: { kind: "write_pipeline", editionId: "004", logicalId: "profile-pipeline", revisionId: revision },
    edition: { kind: "edition_spec", editionId: "004", logicalId: "edition", revisionId: revision },
    capture: { kind: "source_capture", logicalId: "source", revisionId: revision },
    extraction: { kind: "source_extraction", logicalId: "source", revisionId: revision },
    profile: { kind: "article_production_profile", logicalId: "profile", revisionId: revision },
    plan: { kind: "article_review_plan", logicalId: "review-plan", revisionId: revision },
    writer: { kind: "prompt", logicalId: "writer", revisionId: revision },
    evidence: { kind: "prompt", logicalId: "evidence", revisionId: revision },
    rules: { kind: "policy", logicalId: "rules", revisionId: revision },
    measurement: { kind: "policy", logicalId: "measurement", revisionId: revision },
  } as const;
  const raw = (ref: InputRevisionRef): JsonObject => ({
    kind: ref.kind,
    logical_id: ref.logicalId,
    revision_id: ref.revisionId,
    ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }),
  });
  const articles = Array.from({ length: 7 }, (_, index) => ({
    article_id: `article-${index + 1}`,
    content_mode: "faithful_synthesis",
    byline: "Source Author",
    source_ids: ["source"],
    source_authors: ["Source Author"],
    brief: "Write from the complete source extraction.",
    production_profile_revision: raw(refs.profile),
    parent: null,
    maximum_reader_pages: 7,
    model_policy: { default: { adapter: "test", model: "test" } },
  }));
  const pipeline = {
    schema_version: 1,
    edition_id: "004",
    pipeline_id: "profile-pipeline",
    edition_spec: raw(refs.edition),
    sources: [{ source_id: "source", capture: raw(refs.capture), extraction: raw(refs.extraction) }],
    articles,
    editorial: {
      editorial_id: "opening",
      brief: "Opening",
      writer_prompt: raw(refs.writer),
      input_revisions: [raw(refs.rules)],
      parent: null,
      maximum_reader_pages: 1,
      model_policy: { default: { adapter: "test", model: "test" } },
    },
    translations: [{
      language: "es",
      source_language: "en",
      prompt: raw(refs.writer),
      input_revisions: [raw(refs.rules)],
      parents: Object.fromEntries([...articles.map((article) => article.article_id), "opening"].map((pieceId) => [pieceId, null])),
      maximum_reader_pages: 7,
      model_policy: { default: { adapter: "test", model: "test" } },
    }],
    images: Array.from({ length: 13 }, (_, index) => ({ kind: "image", edition_id: "004", logical_id: `image-${index + 1}`, revision_id: revision })),
    layout_inputs: [raw(refs.edition)],
    renderer_inputs: [{ input: raw(refs.edition), payload_path: "edition.yaml", renderer_target_path: "editions/004/edition.yaml" }],
    render: {
      primary_language: "en",
      publication_name: "Magazine",
      renderer: "reportlab",
      configured_languages: ["en", "es"],
      studio_policy: "not_applicable",
    },
  };
  const inputRequests = [
    { ref: refs.edition, files: [{ path: "edition.yaml", mediaType: "application/yaml", content: "edition_id: 004\n" }] },
    { ref: refs.capture, files: [{ path: "raw/source.yaml", mediaType: "application/yaml", content: "source: source\n" }] },
    { ref: refs.extraction, files: [{ path: "extracted.md", mediaType: "text/markdown", content: "# Source\n\nComplete extraction.\n" }] },
    { ref: refs.profile, files: [{ path: "profile.json", mediaType: "application/json", content: JSON.stringify({
      schema_version: "article-production-profile/1",
      profile_id: "profile",
      format_id: "longform",
      writer: { prompt_revision: raw(refs.writer), result_contract_version: "article-writer-result/1", review_materials: [] },
      review_plan_revision: raw(refs.plan),
      writing_rules_revision: raw(refs.rules),
      writing_policy_revisions: [],
      revision_policy: { maximum_rewrites: 1 },
    }) }] },
    { ref: refs.plan, files: [{ path: "review-plan.json", mediaType: "application/json", content: JSON.stringify({
      schema_version: "article-review-plan/1",
      checks: [
        { kind: "model_review", id: "evidence", role: "article_review", prompt_revision: raw(refs.evidence), access: "source_aware", authority: "blocking" },
        { kind: "article_measurement", id: "measure_article", role: "measure_article", measurement_profile_revision: raw(refs.measurement), maximum_reader_pages: 7 },
      ],
      waves: [{ id: "panel", check_ids: ["evidence", "measure_article"], stop_after: "never" }],
    }) }] },
    { ref: refs.writer, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Write.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.evidence, files: [{ path: "prompt.md", mediaType: "text/markdown", content: "Review.\n" }, { path: "output.schema.json", mediaType: "application/json", content: "{}\n" }] },
    { ref: refs.rules, files: [{ path: "policy.md", mediaType: "text/markdown", content: "Rules.\n" }] },
    { ref: refs.measurement, files: [{ path: "policy.md", mediaType: "text/markdown", content: "Measure.\n" }] },
    { ref: refs.pipeline, files: [{ path: "production.yaml", mediaType: "application/yaml", content: JSON.stringify(pipeline) }] },
  ] as const;
  const materialized = [] as Awaited<ReturnType<typeof materializeNativeInputRevision>>[];
  for (const request of inputRequests) {
    materialized.push(await materializeNativeInputRevision(repositoryRoot, workRoot, {
      ref: request.ref,
      createdAt: "2026-08-04T00:00:00.000Z",
      parentRevisionId: null,
      files: request.files,
    }));
  }
  const git = new GitCliDurableGit(repositoryRoot);
  await git.checkpointInputMigration({
    migrationId: `profile-launch-${runIdValue}`,
    repositoryPaths: materialized.flatMap((input) => input.repositoryPaths),
    manifestDigests: Object.fromEntries(materialized.map((input) => [input.repositoryPaths.find((path) => path.endsWith("/manifest.yaml"))!, input.manifestDigest])),
  });
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  const articleExecutionId = "stable-article-execution" as ArticleExecutionId;
  const built = await buildAuthenticatedArticleLaunchArgs({
    repositoryRoot,
    ledger,
    now: () => new Date("2026-08-04T00:00:00.000Z"),
    validateRuntimeResources: async () => undefined,
    getWorkflowVersion: async () => "loops-test/1",
    getRendererIdentity: async () => ({ defaultBackend: "magazine-no-agent" } as unknown as RendererIdentity),
  }, refs.pipeline, "article-1", {
    runId: runIdValue as RunId,
    articleExecutionId,
    ...(loopsRunId === undefined ? {} : { loopsRunId }),
    promotionId: `promotion-${runIdValue}` as never,
    revisionId: revision,
  });
  return {
    root,
    ledger,
    runId: built.runId,
    articleExecutionId: built.articleExecutionId,
    args: built.args,
    close: () => {
      ledger.close();
      void rm(root, { recursive: true, force: true });
    },
  };
}
