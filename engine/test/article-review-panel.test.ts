import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  createDurableWorkflowPin,
  createRuntime,
  SQLiteDurableRunStore,
  type WorkflowGlobals,
} from "@loops/core";

import { LocalAuthorityStore, type AuthorizedWorker } from "../authority/local-authority.ts";
import type { ArticleExecutionId, ArtifactId, JsonValue, RunId } from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import type { ResolvedArticleProductionProfile, ResolvedReviewPlan } from "../contracts/production-plan.ts";
import type { MaterializedWritePipelineInput } from "../durable/write-pipeline.ts";
import { ArtifactLedger, type LedgerArtifact } from "../workflow-authority/artifact-ledger.ts";
import { ArticleAttemptRunner } from "../article-production/attempts.ts";
import { selectArticleReviewerMaterials, type ArticleMaterialContext } from "../article-production/materials.ts";
import type { ArticleMeasurement, MagazineWorkflowContext, WorkflowDurableContext } from "../workflows/internal-types.ts";
import { createArticleWorkflowPorts } from "../workflows/article-runtime.ts";
import {
  canonicalDecisionEvidence,
  canonicalMaterialArtifactIds,
  canonicalMaterialBindings,
} from "../workflows/article-workflow.ts";
import {
  runArticleReviewPanel,
  reviewKey,
  type ArticleReviewModelInput,
  type ArticleReviewPanelInput,
  type ArticleReviewWorkflowPorts,
} from "../workflows/article-review-panel.ts";

const runId = "review-panel-run" as RunId;
const articleExecutionId = "review-panel-article-execution" as ArticleExecutionId;
const manuscriptId = "review-panel-manuscript" as ArtifactId;
const revisionId = "review-panel-revision" as never;
const reviewPin = createDurableWorkflowPin({
  source: { entryPath: "engine/test/article-review-panel.test.ts", graphHash: "sha256:review-panel" },
  dependencies: { lockfilePath: "package-lock.json", lockfileHash: "sha256:review-panel-lock" },
  execution: { backend: "review-panel-test" },
});
const backend = {
  name: "review-panel-test",
  capabilities: { nativeStructuredOutput: false, sessions: false, worktreeIsolation: false, reportsTokens: false },
  async run(): Promise<never> { throw new Error("review panel tests do not call agents"); },
};

const id = (value: string): ArtifactId => value as ArtifactId;
const revision = (kind: InputRevisionRef["kind"], logicalId: string): InputRevisionRef => ({
  kind,
  logicalId,
  revisionId: `revision-${logicalId}` as never,
} as InputRevisionRef);

function profile(): ResolvedArticleProductionProfile {
  return {
    schemaVersion: "resolved-article-production-profile/1",
    profileId: "review-profile",
    formatId: "review-format",
    profileArtifactId: id("profile-artifact"),
    writerPromptArtifactId: id("writer-prompt"),
    writerResultContractVersion: "article-writer-result/1",
    reviewMaterials: [],
    reviewPlanArtifactId: id("review-plan"),
    writingRulesArtifactId: id("writing-rules"),
    writingPolicyArtifactIds: [],
    maximumRewrites: 1,
  };
}

function reviewPlan(): ResolvedReviewPlan {
  return {
    schemaVersion: "resolved-article-review-plan/1",
    reviewPlanArtifactId: id("review-plan"),
    checks: [
      {
        kind: "model_review",
        id: "evidence",
        role: "article_review",
        promptArtifactId: id("evidence-prompt"),
        access: "source_aware",
        authority: "blocking",
      },
      {
        kind: "model_review",
        id: "craft",
        role: "article_review",
        promptArtifactId: id("craft-prompt"),
        access: "source_blind",
        authority: "advisory",
      },
      {
        kind: "article_measurement",
        id: "measure_article",
        role: "measure_article",
        measurementProfileArtifactId: id("measurement-profile"),
        maximumReaderPages: 7,
      },
      {
        kind: "model_review",
        id: "teaching-only",
        role: "article_review",
        promptArtifactId: id("teaching-prompt"),
        access: "source_blind",
        authority: "advisory",
        applicableWhen: { kind: "content_mode", values: ["original_synthesis"] },
      },
    ],
    waves: [{ id: "all", checkIds: ["evidence", "craft", "measure_article", "teaching-only"], stopAfter: "never" }],
  };
}

function materialsContext(): ArticleMaterialContext {
  const source: MaterializedWritePipelineInput = {
    ref: revision("source_extraction", "source-one"),
    artifacts: [{ path: "source.md", artifactId: id("source-artifact") }],
  };
  return {
    articleId: "article-one",
    contentMode: "faithful_synthesis",
    sourceIds: ["source-one"],
    productionProfile: profile(),
    writingRulesArtifactId: id("writing-rules"),
    reviewPlan: reviewPlan(),
    materializedInputs: [source],
  };
}

async function fixture(): Promise<{
  readonly root: string;
  readonly ledger: ArtifactLedger;
  readonly runner: ArticleAttemptRunner;
  readonly aware: AuthorizedWorker;
  readonly blind: AuthorizedWorker;
  readonly tool: AuthorizedWorker;
}> {
  const root = await mkdtemp(join(tmpdir(), "mag-review-panel-"));
  const ledger = new ArtifactLedger(join(root, "magazine.sqlite"));
  ledger.createArtifact({
    id: manuscriptId,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "imported",
    payload: { kind: "text", text: "# Article\n\nBody" },
    metadata: { articleId: "article-one", revisionId },
  });
  for (const artifactId of [
    "source-artifact", "writing-rules", "evidence-prompt", "craft-prompt", "teaching-prompt",
    "measurement-profile", "profile-artifact", "review-plan", "writer-prompt",
  ]) {
    ledger.createArtifact({
      id: id(artifactId),
      kind: "review_input",
      schemaVersion: "review-input/1",
      mediaType: "text/plain",
      origin: "imported",
      payload: { kind: "text", text: artifactId },
      metadata: { articleId: "article-one" },
    });
  }
  ledger.createRun({
    runId,
    articleExecutionId,
    articleId: "article-one",
    editionId: "004",
    workflowVersion: "review-panel/1",
    loopsRunId: runId,
    manuscriptArtifactId: manuscriptId,
    args: { articleId: "article-one" },
  });
  const authority = await LocalAuthorityStore.init(join(root, "authority"));
  await authority.enrollWorker({ principalId: "source-aware-reviewer", authority: "model", capabilities: ["text_model", "source_access", "source_blind"] });
  const awareCredential = await authority.createCredentialProfile({ principalId: "source-aware-reviewer", credentialProfileId: "source-aware-profile" });
  await authority.grant({ credentialProfileId: awareCredential.credentialProfileId, grantId: "source-aware-grant", capabilities: ["text_model", "source_access", "source_blind"] });
  const aware = await authority.authenticate({ credentialProfileId: awareCredential.credentialProfileId, secret: awareCredential.secret });
  await authority.enrollWorker({ principalId: "source-blind-reviewer", authority: "model", capabilities: ["text_model", "source_blind"] });
  const blindCredential = await authority.createCredentialProfile({ principalId: "source-blind-reviewer", credentialProfileId: "source-blind-profile" });
  await authority.grant({ credentialProfileId: blindCredential.credentialProfileId, grantId: "source-blind-grant", capabilities: ["text_model", "source_blind"] });
  const blind = await authority.authenticate({ credentialProfileId: blindCredential.credentialProfileId, secret: blindCredential.secret });
  await authority.enrollWorker({ principalId: "measurement-tool", authority: "tool", capabilities: ["subprocess"] });
  const toolCredential = await authority.createCredentialProfile({ principalId: "measurement-tool", credentialProfileId: "measurement-profile" });
  await authority.grant({ credentialProfileId: toolCredential.credentialProfileId, grantId: "measurement-grant", capabilities: ["subprocess"] });
  const tool = await authority.authenticate({ credentialProfileId: toolCredential.credentialProfileId, secret: toolCredential.secret });
  return { root, ledger, runner: ledger.createArticleAttemptRunner(), aware, blind, tool };
}

function contextFromGlobals(globals: WorkflowGlobals): MagazineWorkflowContext {
  return {
    durableContext: () => globals.durableContext?.() as WorkflowDurableContext | undefined,
    step: async (key, fn, options) => {
      if (options.retry === undefined) return await globals.step(key, fn, { input: options.input });
      const retryOn = options.retry.retryOn;
      return await globals.step(key, fn, {
        input: options.input,
        ...(options.schema === undefined ? {} : { schema: options.schema as never }),
        ...(options.label === undefined ? {} : { label: options.label }),
        retry: {
          ...(options.retry.maxAttempts === undefined ? {} : { maxAttempts: options.retry.maxAttempts }),
          ...(retryOn === undefined ? {} : { retryOn: typeof retryOn === "string" ? retryOn : [...retryOn] }),
        },
      });
    },
    parallel: async (thunks) => await globals.parallel([...thunks]),
    reviewStepResultSchema: undefined,
    wait: async () => { throw new Error("review panel tests do not wait"); },
  };
}

function panelInput(ordinal: number): ArticleReviewPanelInput {
  return {
    runId,
    articleExecutionId,
    articleId: "article-one",
    manuscriptArtifactId: manuscriptId,
    manuscriptRevisionId: revisionId,
    manuscriptOrdinal: ordinal,
    rendererIdentity: {} as never,
    materialContext: materialsContext(),
  };
}

async function runPanel(
  f: Awaited<ReturnType<typeof fixture>>,
  input: ArticleReviewPanelInput,
  ports: ArticleReviewWorkflowPorts,
): Promise<Awaited<ReturnType<typeof runArticleReviewPanel>>> {
  const store = new SQLiteDurableRunStore(join(f.root, `loops-${input.manuscriptOrdinal}.sqlite`));
  try {
    const runtime = createRuntime({
      backend,
      defaultBackend: backend.name,
      durable: { store, runId, workflowName: "review-panel", workflowPin: reviewPin, args: input as never },
    });
    return await runtime.run((globals) => runArticleReviewPanel(input, contextFromGlobals(globals), ports));
  } finally {
    store.close();
  }
}

function portsFor(
  f: Awaited<ReturnType<typeof fixture>>,
  counts: Map<string, number>,
  completion: string[],
  failFirst: string | undefined,
  sharedPrincipal = false,
): ArticleReviewWorkflowPorts {
  return {
    ledger: f.ledger,
    attemptRunner: f.runner,
    reviewerFor: async (check) => sharedPrincipal || check.access === "source_aware" ? f.aware : f.blind,
    toolWorkerFor: async () => f.tool,
    runModelReview: async ({ check, claim }: ArticleReviewModelInput) => {
      counts.set(check.id, (counts.get(check.id) ?? 0) + 1);
      if (failFirst === check.id && claim.attemptNumber === 1) throw new Error(`retry ${check.id}`);
      await new Promise((resolve) => setTimeout(resolve, check.id === "evidence" ? 20 : 1));
      completion.push(check.id);
      return {
        schemaVersion: "article-review-result/1",
        reviewerId: claim.principalId,
        manuscriptArtifactId: manuscriptId,
        assessment: "pass",
        findings: [],
      };
    },
    measureArticle: async ({ articleId, manuscriptArtifactId }) => ({
      schemaVersion: "article-measurement/1",
      articleId,
      manuscriptArtifactId,
      pageCount: 2,
      maximumReaderPages: 7,
      fits: true,
      openerFits: true,
      layouts: [],
      inputArtifactIds: [manuscriptId],
    }),
  };
}

test("parallel review preserves plan order, retries only the failed check, and uses fresh ordinal keys", async () => {
  const f = await fixture();
  try {
    const counts = new Map<string, number>();
    const completion: string[] = [];
    const result = await runPanel(f, panelInput(3), portsFor(f, counts, completion, "craft"));
    assert.deepEqual(result.checks.map((check) => check.checkId), ["evidence", "craft", "measure_article", "teaching-only"]);
    assert.equal(result.checks.find((check) => check.checkId === "teaching-only")?.status, "skipped");
    assert.deepEqual(completion.slice(0, 2), ["craft", "evidence"]);
    assert.equal(counts.get("evidence"), 1);
    assert.equal(counts.get("craft"), 2);
    assert.equal(result.checks.every((check) => check.key.startsWith("review.")), true);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("source-aware and source-blind checks use separate authenticated principals", async () => {
  const f = await fixture();
  try {
    const counts = new Map<string, number>();
    const completion: string[] = [];
    const result = await runPanel(f, panelInput(4), portsFor(f, counts, completion, undefined));
    const identities = result.checks.filter((check) => check.kind === "model_review" && check.status === "completed").map((check) => check.reviewerId);
    assert.deepEqual(identities, ["source-aware-reviewer", "source-blind-reviewer"]);
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("measurement check carries exact page and opener data and reports a fresh key", async () => {
  const f = await fixture();
  try {
    const counts = new Map<string, number>();
    const result = await runPanel(f, panelInput(5), portsFor(f, counts, [], undefined));
    const measurement = result.checks.find((check) => check.checkId === "measure_article");
    assert.ok(measurement);
    assert.equal(measurement.result?.schemaVersion, "article-measurement/1");
    assert.equal((measurement.result as { readonly pageCount: number }).pageCount, 2);
    assert.equal((measurement.result as { readonly openerFits: boolean }).openerFits, true);
    assert.equal(measurement.key, reviewKey({ articleExecutionId, reviewPlanArtifactId: id("review-plan"), manuscriptRevisionId: revisionId, waveId: "all", checkId: "measure_article" }));
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("runtime rejects duplicate authenticated reviewer identities before a panel starts", async () => {
  const f = await fixture();
  try {
    const ports = createArticleWorkflowPorts({
      ledger: f.ledger,
      repositoryRoot: f.root,
      workRoot: f.root,
      projectRoot: process.cwd(),
      renderer: {
        workDirectory: f.root,
        toolchain: {
          uvExecutable: "uv",
          pythonExecutable: "python3",
          expected: {
            uvSha256: "sha256:test-uv",
            uvVersion: "uv-test",
            pythonSha256: "sha256:test-python",
            pythonVersion: "python-test",
            pythonImplementation: "CPython",
            pythonCacheTag: "cpython-test",
            platform: `${process.platform}-test`,
          },
        },
      },
      articleReviewWorkers: {
        sourceAwareReviewer: f.aware,
        sourceBlindReviewer: f.aware,
        measurementTool: f.tool,
      },
    });
    await assert.rejects(
      ports.runReviewPanel(panelInput(6), {} as MagazineWorkflowContext),
      /distinct authenticated principal and credential IDs/u,
    );
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("runtime rejects reviewer capability extras before a panel starts", async () => {
  const f = await fixture();
  try {
    const ports = createArticleWorkflowPorts({
      ledger: f.ledger,
      repositoryRoot: f.root,
      workRoot: f.root,
      projectRoot: process.cwd(),
      renderer: {
        workDirectory: f.root,
        toolchain: {
          uvExecutable: "uv",
          pythonExecutable: "python3",
          expected: {
            uvSha256: "sha256:test-uv",
            uvVersion: "uv-test",
            pythonSha256: "sha256:test-python",
            pythonVersion: "python-test",
            pythonImplementation: "CPython",
            pythonCacheTag: "cpython-test",
            platform: `${process.platform}-test`,
          },
        },
      },
      articleReviewWorkers: {
        // fixture.aware intentionally has source_blind as an extra grant.
        sourceAwareReviewer: f.aware,
        sourceBlindReviewer: f.blind,
        measurementTool: f.tool,
      },
      articleReviewCredentials: {
        schemaVersion: "closed-writer-credential-resource/1",
        read: () => ({ OPENAI_API_KEY: "test-key" }),
      },
    });
    assert.ok(ports.validateRuntimeResources);
    await assert.rejects(
      ports.validateRuntimeResources(),
      /Source-aware reviewer must be an authenticated model with text_model and source_access only/u,
    );
  } finally {
    f.ledger.close();
    await rm(f.root, { recursive: true, force: true });
  }
});

test("canonical material files and decision evidence preserve exact ordered lineage", () => {
  const firstRef = revision("source_capture", "source-one");
  const secondRef = revision("source_extraction", "source-one");
  const entry = {
    materializedInputs: [
      { ref: firstRef, artifacts: [{ path: "capture.html", artifactId: id("capture") }, { path: "headers.json", artifactId: id("headers") }] },
      { ref: secondRef, artifacts: [{ path: "extraction.md", artifactId: id("extraction") }] },
    ],
  };
  assert.deepEqual(canonicalMaterialArtifactIds(entry), [id("capture"), id("headers"), id("extraction")]);
  assert.deepEqual(canonicalMaterialBindings(entry), [
    { artifactId: id("capture"), revision: firstRef },
    { artifactId: id("headers"), revision: firstRef },
    { artifactId: id("extraction"), revision: secondRef },
  ]);
  assert.deepEqual(canonicalDecisionEvidence({
    manuscriptArtifactId: id("manuscript"),
    reviewArtifactIds: [id("review-aware")],
    reviewOutputArtifactIds: [id("review-aware"), id("renderer")],
    measurementArtifactId: id("measurement"),
    inputArtifactIds: [id("capture"), id("manuscript")],
  }), [id("manuscript"), id("review-aware"), id("renderer"), id("measurement"), id("capture")]);
});

type MeasurementArtifactCase =
  | "extra"
  | "missing"
  | "reordered"
  | "measurement-parent-extra"
  | "measurement-parent-missing"
  | "measurement-parent-reordered"
  | "measurement-relation"
  | "measurement-kind"
  | "measurement-schema"
  | "measurement-media"
  | "measurement-payload"
  | "renderer-parent-extra"
  | "renderer-parent-missing"
  | "renderer-parent-reordered"
  | "renderer-relation"
  | "renderer-kind"
  | "renderer-schema"
  | "renderer-media"
  | "renderer-payload";

type MeasurementAttemptMode = "created" | "adopted";

function measurementOnlyInput(ordinal: number): ArticleReviewPanelInput {
  const base = panelInput(ordinal);
  const context = materialsContext();
  const measurementCheck = context.reviewPlan.checks.find((check) => check.kind === "article_measurement");
  if (measurementCheck === undefined || measurementCheck.kind !== "article_measurement") throw new Error("measurement fixture check is missing");
  return {
    ...base,
    materialContext: {
      ...context,
      reviewPlan: {
        ...context.reviewPlan,
        checks: [measurementCheck],
        waves: [{ id: "all", checkIds: [measurementCheck.id], stopAfter: "never" }],
      },
    },
  };
}

function measurementValue(input: ArticleReviewPanelInput): ArticleMeasurement {
  return {
    schemaVersion: "article-measurement/1",
    articleId: input.articleId,
    manuscriptArtifactId: input.manuscriptArtifactId,
    pageCount: 2,
    maximumReaderPages: 7,
    fits: true,
    openerFits: true,
    layouts: [],
    inputArtifactIds: [input.manuscriptArtifactId],
  };
}

function measurementAttemptArtifacts(
  f: Awaited<ReturnType<typeof fixture>>,
  input: ArticleReviewPanelInput,
  malformed: MeasurementArtifactCase | undefined,
): readonly LedgerArtifact[] {
  const check = input.materialContext.reviewPlan.checks[0];
  if (check === undefined || check.kind !== "article_measurement") throw new Error("measurement fixture check is missing");
  const waveId = "all";
  const key = reviewKey({
    articleExecutionId: input.articleExecutionId,
    reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    waveId,
    checkId: check.id,
  });
  const materials = selectArticleReviewerMaterials(input.materialContext, check, input.manuscriptArtifactId);
  const parents = materials.artifactIds.map((artifactId) => ({ artifactId, relation: "measurement_input" }));
  const expectedRendererParents = materials.artifactIds.map((artifactId) => ({ artifactId, relation: "renderer_input" }));
  const context: WorkflowDurableContext = {
    runId,
    invocationId: "review-panel-test-invocation",
    workflowName: "review-panel",
    workflowVersion: "review-panel/1",
    callId: key,
    attemptId: `attempt-${malformed ?? "valid"}`,
    attemptNumber: 1,
    key,
    kind: "step",
  };
  const value = measurementValue(input);
  const measurementPayload = { kind: "json" as const, value: value as unknown as JsonValue };
  const rendererOutput = {
    schemaVersion: "article-renderer-measurement-output/1",
    articleId: input.articleId,
    manuscriptArtifactId: input.manuscriptArtifactId,
    inputArtifactIds: value.inputArtifactIds,
    layouts: value.layouts,
  };
  const rendererPayload = { kind: "json" as const, value: rendererOutput as unknown as JsonValue };
  const metadata = {
    articleId: input.articleId,
    checkId: check.id,
    waveId,
    operationKey: key,
    manuscriptArtifactId: input.manuscriptArtifactId,
    manuscriptRevisionId: input.manuscriptRevisionId,
    reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
    materialArtifactIds: materials.artifactIds as unknown as JsonValue,
  };
  let measurementKind = "article_measurement";
  let measurementSchema = "article-measurement/1";
  let measurementMedia = "application/json";
  let measurementParents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[] = parents;
  let measurementPayloadValue: { readonly kind: "json"; readonly value: JsonValue } | { readonly kind: "text"; readonly text: string } = measurementPayload;
  let rendererKind = "article_measurement_renderer_output";
  let rendererSchema = "article-renderer-measurement-output/1";
  let rendererMedia = "application/json";
  let rendererParents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[] = expectedRendererParents;
  let rendererPayloadValue: { readonly kind: "json"; readonly value: JsonValue } | { readonly kind: "text"; readonly text: string } = rendererPayload;
  switch (malformed) {
    case "measurement-parent-extra": measurementParents = [...parents, { artifactId: id("writing-rules"), relation: "measurement_input" }]; break;
    case "measurement-parent-missing": measurementParents = parents.slice(0, -1); break;
    case "measurement-parent-reordered": measurementParents = [...parents].reverse(); break;
    case "measurement-relation": measurementParents = parents.map((parent) => ({ ...parent, relation: "renderer_input" })); break;
    case "measurement-kind": measurementKind = "wrong_measurement"; break;
    case "measurement-schema": measurementSchema = "wrong-measurement/1"; break;
    case "measurement-media": measurementMedia = "text/plain"; break;
    case "measurement-payload": measurementPayloadValue = { kind: "text", text: JSON.stringify(value) }; break;
    case "renderer-parent-extra": rendererParents = [...expectedRendererParents, { artifactId: id("writing-rules"), relation: "renderer_input" }]; break;
    case "renderer-parent-missing": rendererParents = expectedRendererParents.slice(0, -1); break;
    case "renderer-parent-reordered": rendererParents = [...expectedRendererParents].reverse(); break;
    case "renderer-relation": rendererParents = expectedRendererParents.map((parent) => ({ ...parent, relation: "measurement_input" })); break;
    case "renderer-kind": rendererKind = "wrong_renderer_output"; break;
    case "renderer-schema": rendererSchema = "wrong-renderer/1"; break;
    case "renderer-media": rendererMedia = "text/plain"; break;
    case "renderer-payload": rendererPayloadValue = { kind: "text", text: JSON.stringify(rendererOutput) }; break;
    default: break;
  }
  const measurementArtifact = f.ledger.createArtifact({
    id: id(`measurement-${malformed ?? "valid"}`),
    kind: measurementKind,
    schemaVersion: measurementSchema,
    mediaType: measurementMedia,
    origin: "machine",
    payload: measurementPayloadValue,
    parents: measurementParents,
    metadata,
    runId,
    durableContext: context,
  });
  const rendererArtifact = f.ledger.createArtifact({
    id: id(`renderer-${malformed ?? "valid"}`),
    kind: rendererKind,
    schemaVersion: rendererSchema,
    mediaType: rendererMedia,
    origin: "machine",
    payload: rendererPayloadValue,
    parents: rendererParents,
    metadata,
    runId,
    durableContext: context,
  });
  if (malformed === "missing") return [measurementArtifact];
  if (malformed === "reordered") return [rendererArtifact, measurementArtifact];
  if (malformed === "extra") {
    const extra = f.ledger.createArtifact({
      id: id("renderer-extra"),
      kind: "article_measurement_renderer_output",
      schemaVersion: "article-renderer-measurement-output/1",
      mediaType: "application/json",
      origin: "machine",
      payload: rendererPayload,
      parents: rendererParents,
      metadata,
      runId,
      durableContext: context,
    });
    return [measurementArtifact, rendererArtifact, extra];
  }
  return [measurementArtifact, rendererArtifact];
}

function fakeMeasurementAttemptRunner(
  value: ArticleMeasurement,
  artifacts: readonly LedgerArtifact[],
  mode: MeasurementAttemptMode,
): ArticleAttemptRunner {
  return {
    executeTool: async () => mode === "adopted"
      ? { selected: true, adopted: true, artifacts }
      : { selected: true, value, claim: undefined as never, artifacts },
  } as unknown as ArticleAttemptRunner;
}

for (const malformed of [
  "extra",
  "missing",
  "reordered",
  "measurement-parent-extra",
  "measurement-parent-missing",
  "measurement-parent-reordered",
  "measurement-relation",
  "measurement-kind",
  "measurement-schema",
  "measurement-media",
  "measurement-payload",
  "renderer-parent-extra",
  "renderer-parent-missing",
  "renderer-parent-reordered",
  "renderer-relation",
  "renderer-kind",
  "renderer-schema",
  "renderer-media",
  "renderer-payload",
] as const satisfies readonly MeasurementArtifactCase[]) {
  for (const mode of ["created", "adopted"] as const satisfies readonly MeasurementAttemptMode[]) {
    test(`measurement ${mode} rejects ${malformed} output artifacts`, async () => {
      const f = await fixture();
      try {
        const input = measurementOnlyInput(100 + (malformed.length * 2) + (mode === "adopted" ? 1 : 0));
        const artifacts = measurementAttemptArtifacts(f, input, malformed);
        const ports = portsFor(f, new Map(), [], undefined);
        const malformedRunner = fakeMeasurementAttemptRunner(measurementValue(input), artifacts, mode);
        await assert.rejects(
          runPanel(f, input, { ...ports, attemptRunner: malformedRunner }),
          /review check measure_article|measurement check/u,
        );
      } finally {
        f.ledger.close();
        await rm(f.root, { recursive: true, force: true });
      }
    });
  }
}

for (const mode of ["created", "adopted"] as const satisfies readonly MeasurementAttemptMode[]) {
  test(`measurement ${mode} accepts the exact declared output artifacts`, async () => {
    const f = await fixture();
    try {
      const input = measurementOnlyInput(150 + (mode === "adopted" ? 1 : 0));
      const artifacts = measurementAttemptArtifacts(f, input, undefined);
      const ports = portsFor(f, new Map(), [], undefined);
      const result = await runPanel(f, input, {
        ...ports,
        attemptRunner: fakeMeasurementAttemptRunner(measurementValue(input), artifacts, mode),
      });
      const measurement = result.checks.find((check) => check.checkId === "measure_article");
      assert.ok(measurement);
      assert.deepEqual(measurement.outputArtifactIds, artifacts.map((artifact) => artifact.id));
      assert.equal(measurement.resultArtifactId, artifacts[0]?.id);
    } finally {
      f.ledger.close();
      await rm(f.root, { recursive: true, force: true });
    }
  });
}
