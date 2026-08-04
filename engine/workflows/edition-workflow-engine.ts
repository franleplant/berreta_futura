import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";

import {
  createRuntime,
  durableWorkflowVersionFromPin,
  SQLiteDurableRunStore,
  type DurableWorkflowPin,
} from "@loops/core";
import { buildDurableWorkflowPin } from "@loops/workflow";

import type { ArtifactId, JsonObject, RunId, RevisionId } from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  resolveAuthenticatedWritePipelineInputs,
  type AuthenticatedWritePipelineInputs,
} from "../durable/write-pipeline.ts";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import { newArticleExecutionId, newId } from "../contracts/ids.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import type { MagazineWorkflowEngineOptions } from "../contracts/workflow-run.ts";
import { createArticleWorkflowPorts } from "./article-runtime.ts";
import type { ArticleRuntimeStartArgs } from "./internal-types.ts";
import {
  buildAuthenticatedArticleLaunchArgsFromMaterialized,
  type ArticleLaunchBuilderDependencies,
} from "./article-launch.ts";
import { invokeEditionWorkflowWithPorts } from "./edition-loops-entry.ts";
import {
  EDITION_WORKFLOW_NAME,
  parseEditionWorkflowArgs,
  type EditionArticleChild,
  type EditionPlanCheckpoint,
  type EditionSourceLineage,
  type EditionWorkflowArgs,
  type EditionWorkflowResult,
} from "./edition-workflow.ts";
import {
  createMagazineWorkflowResolver,
  MAGAZINE_ARTICLE_WORKFLOW_ENTRY,
} from "./magazine-workflow-resolver.ts";
import { readVerifiedRendererIdentity, type RendererIdentity } from "./renderer-identity.ts";

const EDITION_ENTRY = "engine/workflows/edition-loops-entry.ts";
const EDITION_CONFIG = "engine/workflows/edition-runtime-identity.json";
const ARTICLE_CONFIG = "engine/workflows/article-runtime-identity.json";
const ARTICLE_ENTRY = MAGAZINE_ARTICLE_WORKFLOW_ENTRY;
const NO_AGENT_BACKEND = "magazine-no-agent";

export type EditionStartRequest = {
  readonly pipelineRef: Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>;
  readonly runId?: RunId;
  readonly editionExecutionId?: string;
};

export type EditionWorkflowEngineOptions = MagazineWorkflowEngineOptions & {
  /** Test-only host seam. Production callers use the authenticated adapters. */
  readonly articlePorts?: import("./internal-types.ts").ArticleWorkflowPorts;
  /** Test-only renderer identity when the host supplies a stub article port. */
  readonly rendererIdentity?: RendererIdentity;
};

export type EditionChildView = {
  readonly articleId: string;
  readonly articleExecutionId: string;
  readonly runId: RunId;
  readonly sourceIds: readonly string[];
  readonly sourceLineage: readonly EditionSourceLineage[];
  readonly invocationId?: string;
  readonly status: string;
  readonly result?: unknown;
};

export type EditionWorkflowView = {
  readonly runId: RunId;
  readonly editionExecutionId: string;
  readonly editionId: "004";
  readonly status: "running" | "waiting" | "complete" | "failed";
  readonly pipelineRef: EditionPlanCheckpoint["pipelineRef"];
  readonly pipelineDigest: string;
  readonly planArtifactId: ArtifactId;
  readonly articleExecutionIds: readonly string[];
  readonly selectedImageRevisions: EditionPlanCheckpoint["selectedImageRevisions"];
  readonly imageGenerationAllowed: false;
  readonly children: readonly EditionChildView[];
  readonly workflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly invocations: readonly EditionInspectionInvocation[];
  readonly calls: readonly EditionInspectionCall[];
  readonly waits: readonly EditionInspectionWait[];
};

export type EditionInspectionInvocation = {
  readonly invocationId: string;
  readonly parentInvocationId?: string;
  readonly parentCallId?: string;
  readonly workflowName: string;
  readonly workflowVersion: string;
  readonly status: string;
  readonly args?: unknown;
};

export type EditionInspectionCall = {
  readonly callId: string;
  readonly invocationId: string;
  readonly key: string;
  readonly kind: string;
  readonly status: string;
  readonly result?: unknown;
};

export type EditionInspectionWait = {
  readonly waitId: string;
  readonly callId: string;
  readonly invocationId: string;
  readonly key: string;
  readonly status: string;
  readonly request?: unknown;
  readonly answer?: unknown;
};

/** Public Loops-only Edition 4 root. XState is intentionally not consulted. */
export class EditionWorkflowEngine {
  readonly #ledger: ArtifactLedger;
  readonly #store: SQLiteDurableRunStore;
  readonly #ports: import("./internal-types.ts").ArticleWorkflowPorts;
  readonly #options: EditionWorkflowEngineOptions;
  readonly #projectRoot: string;
  readonly #repositoryRoot: string;
  readonly #clock: { readonly now: () => Date };
  readonly #validateRuntimeResources: () => Promise<void>;
  #articleWorkflowVersionPromise: Promise<string> | undefined;
  #rendererIdentityPromise: Promise<RendererIdentity> | undefined;
  #pinPromise: Promise<DurableWorkflowPin> | undefined;

  constructor(options: EditionWorkflowEngineOptions) {
    this.#options = options;
    this.#projectRoot = resolve(options.projectRoot);
    this.#repositoryRoot = resolve(options.repositoryRoot);
    const defaultNow = new Date();
    this.#clock = options.clock ?? { now: () => defaultNow };
    this.#ledger = new ArtifactLedger(options.databasePath, {
      clock: this.#clock,
      ...(options.attemptClock === undefined ? {} : { attemptClock: options.attemptClock }),
    });
    this.#ports = options.articlePorts ?? createArticleWorkflowPorts({
      ledger: this.#ledger,
      repositoryRoot: this.#repositoryRoot,
      workRoot: options.workRoot,
      renderer: options.renderer,
      projectRoot: this.#projectRoot,
      ...(options.articleReviewWorkers === undefined ? {} : { articleReviewWorkers: options.articleReviewWorkers }),
      ...(options.articleReviewCredentials === undefined ? {} : { articleReviewCredentials: options.articleReviewCredentials }),
      ...(options.articleWriter === undefined ? {} : { articleWriter: options.articleWriter }),
    });
    this.#validateRuntimeResources = this.#ports.validateRuntimeResources ?? (async () => undefined);
    this.#store = new SQLiteDurableRunStore(resolve(options.loopsDatabasePath));
  }

  async startEdition(request: EditionStartRequest): Promise<EditionWorkflowView> {
    const runId = request.runId ?? newId<RunId>("edition");
    const existing = this.#store.getRun(runId);
    if (existing !== null) {
      parseEditionWorkflowArgs(existing.args);
      return await this.#run(runId, existing.args as EditionWorkflowArgs);
    }
    const pin = await this.#loadPin();
    await this.#validateRuntimeResources();
    const materialized = await resolveAuthenticatedWritePipelineInputs(
      this.#repositoryRoot,
      request.pipelineRef,
      new GitCliDurableGit(this.#repositoryRoot),
    );
    const args = await this.#prepareRootArgs(request, runId, materialized, pin);
    return await this.#run(runId, args);
  }

  async resume(runId: RunId): Promise<EditionWorkflowView> {
    const stored = this.#store.getRun(runId);
    if (stored === null) throw new Error(`Edition Loops run ${runId} does not exist`);
    const args = parseEditionWorkflowArgs(stored.args);
    return await this.#run(runId, args);
  }

  async inspect(runId: RunId): Promise<EditionWorkflowView> {
    const args = parseEditionWorkflowArgs(this.#store.getRun(runId)?.args);
    const inspection = this.#store.inspectRun(runId);
    if (inspection === null) throw new Error(`Edition Loops run ${runId} does not exist`);
    this.#assertEditionRunBinding(args);
    if (inspection.calls.some((call) => /(?:image|art)[._-]?(?:generation|offer)/iu.test(call.key))) {
      throw new Error("Edition 4 run contains a forbidden image-generation call");
    }
    const root = inspection.invocations.find((invocation) => invocation.parentInvocationId === undefined);
    if (root !== undefined) {
      this.#ledger.recordLoopsObservation(runId, {
        workflowPin: root.workflowPin as unknown as JsonObject,
        context: {
          runId,
          invocationId: root.invocationId,
          workflowName: root.workflowName,
          workflowVersion: root.workflowVersion,
          kind: "workflow",
          ...(root.workflowPin === undefined ? {} : { workflowPin: root.workflowPin as unknown as JsonObject }),
        },
      });
    }
    const children = args.children.map((planned) => {
      const invocation = inspection.invocations.find((candidate) => {
        if (candidate.parentInvocationId !== root?.invocationId) return false;
        const candidateArgs = candidate.args as Partial<ArticleRuntimeStartArgs>;
        return candidateArgs.articleExecutionId === planned.articleExecutionId;
      });
      const result = invocation?.result;
      const status = invocation?.status ?? "pending";
      return {
        articleId: planned.articleId,
        articleExecutionId: planned.articleExecutionId,
        runId: planned.runId,
        sourceIds: planned.sourceIds,
        sourceLineage: planned.sourceLineage,
        ...(invocation === undefined ? {} : { invocationId: invocation.invocationId }),
        status,
        ...(result === undefined ? {} : { result }),
      };
    });
    const status = inspection.run.status === "waiting"
      ? "waiting"
      : inspection.run.status === "completed"
        ? "complete"
        : inspection.run.status === "failed" || inspection.run.status === "canceled"
          ? "failed"
          : "running";
    return {
      runId,
      editionExecutionId: args.editionExecutionId,
      editionId: args.editionId,
      status,
      pipelineRef: args.plan.pipelineRef,
      pipelineDigest: args.plan.pipelineDigest,
      planArtifactId: args.planArtifactId,
      articleExecutionIds: args.plan.children.map((child) => child.articleExecutionId),
      selectedImageRevisions: args.selectedImageRevisions,
      imageGenerationAllowed: false,
      children,
      workflowVersion: inspection.run.workflowVersion,
      ...(inspection.run.workflowPin === undefined ? {} : { workflowPin: inspection.run.workflowPin as unknown as JsonObject }),
      invocations: inspection.invocations.map((invocation) => ({
        invocationId: invocation.invocationId,
        ...(invocation.parentInvocationId === undefined ? {} : { parentInvocationId: invocation.parentInvocationId }),
        ...(invocation.parentCallId === undefined ? {} : { parentCallId: invocation.parentCallId }),
        workflowName: invocation.workflowName,
        workflowVersion: invocation.workflowVersion,
        status: invocation.status,
        args: invocation.args,
      })),
      calls: inspection.calls.map((call) => ({
        callId: call.callId,
        invocationId: call.invocationId,
        key: call.key,
        kind: call.kind,
        status: call.status,
        ...(call.result === undefined ? {} : { result: call.result }),
      })),
      waits: inspection.waits.map((wait) => ({
        waitId: wait.waitId,
        callId: wait.callId,
        invocationId: wait.invocationId,
        key: wait.key,
        status: wait.status,
        ...(wait.request === undefined ? {} : { request: wait.request }),
        ...(wait.answer === undefined ? {} : { answer: wait.answer }),
      })),
    };
  }

  close(): void {
    this.#ledger.close();
    this.#store.close();
  }

  async #run(runId: RunId, args: EditionWorkflowArgs): Promise<EditionWorkflowView> {
    const pin = await this.#loadPin();
    this.#assertEditionRunBinding(args);
    const stored = this.#store.getRun(runId);
    if (stored?.workflowPin !== undefined && !isDeepStrictEqual(stored.workflowPin, pin)) {
      throw new Error("Edition Loops workflow pin changed after the run was frozen");
    }
    const runtime = createRuntime({
      defaultBackend: NO_AGENT_BACKEND,
      backend: noAgentBackend,
      durable: {
        store: this.#store,
        runId,
        workflowName: EDITION_WORKFLOW_NAME,
        workflowPin: pin,
        args,
      },
      args,
      cwd: this.#projectRoot,
      workflowResolver: createMagazineWorkflowResolver({
        projectRoot: this.#projectRoot,
        articlePorts: this.#ports,
      }),
    });
    try {
      await runtime.run((globals) => invokeEditionWorkflowWithPorts(globals, this.#ports, args));
    } catch (error) {
      if (!isSuspension(error)) throw error;
    }
    return await this.inspect(runId);
  }

  /** Rebuild the immutable root/child binding from ledger evidence on every entry. */
  #assertEditionRunBinding(args: EditionWorkflowArgs): void {
    const root = this.#ledger.requireRun(args.runId);
    if (
      root.editionId !== "004" ||
      root.articleId !== "edition-004" ||
      root.manuscriptArtifactId !== args.planArtifactId ||
      root.loopsRunId !== args.runId ||
      root.argsDigest.length === 0 ||
      !isDeepStrictEqual(root.args, args as unknown as JsonObject)
    ) {
      throw new Error("Edition root run is not bound to its immutable workflow args");
    }
    if (root.workflowPin === undefined) throw new Error("Edition root run has no frozen workflow pin");
    const planArtifact = this.#ledger.requireArtifact(args.planArtifactId);
    if (
      planArtifact.kind !== "edition_plan" ||
      planArtifact.schemaVersion !== "edition-plan-checkpoint/1" ||
      planArtifact.mediaType !== "application/json" ||
      planArtifact.payloadKind !== "json" ||
      planArtifact.producingRunId !== undefined ||
      planArtifact.metadata.editionId !== "004" ||
      planArtifact.metadata.pipelineRevisionId !== args.plan.pipelineRef.revisionId ||
      planArtifact.metadata.pipelineDigest !== args.plan.pipelineDigest ||
      planArtifact.metadata.imageGenerationAllowed !== false ||
      !sameParents(planArtifact.parents, uniqueSourceArtifactIdsFromPlan(args.plan).map((artifactId) => ({ artifactId, relation: "source_lineage" })))
    ) {
      throw new Error("Edition plan artifact is not the exact immutable source-bound plan");
    }
    const planPayload = readJsonArtifact(this.#ledger, planArtifact.id, "Edition plan artifact");
    if (!isDeepStrictEqual(planPayload, args.plan)) throw new Error("Edition plan payload does not match workflow args");
    const entryArtifact = this.#ledger.requireArtifact(args.entryArtifactId);
    if (
      entryArtifact.kind !== "edition_workflow_entry" ||
      entryArtifact.schemaVersion !== "magazine-edition-workflow/1" ||
      entryArtifact.mediaType !== "application/json" ||
      entryArtifact.payloadKind !== "json" ||
      entryArtifact.producingRunId !== args.runId ||
      entryArtifact.metadata.editionId !== "004" ||
      entryArtifact.metadata.imageGenerationAllowed !== false ||
      !sameParents(entryArtifact.parents, [{ artifactId: args.planArtifactId, relation: "edition_plan" }])
    ) {
      throw new Error("Edition workflow entry artifact is not the exact run-owned entry");
    }
    const entryPayload = readJsonArtifact(this.#ledger, entryArtifact.id, "Edition entry artifact");
    if (!isDeepStrictEqual(entryPayload, args)) throw new Error("Edition entry payload does not match workflow args");
    if (
      args.selectedImageRevisions.length !== 13 ||
      args.imageGenerationAllowed !== false ||
      args.plan.imageGenerationAllowed !== false ||
      !isDeepStrictEqual(args.selectedImageRevisions, args.plan.selectedImageRevisions)
    ) {
      throw new Error("Edition 4 image selection is not pinned with generation disabled");
    }
    for (const image of args.selectedImageRevisions) {
      if (image.kind !== "image" || image.editionId !== "004" || !isText(image.logicalId) || !isText(image.revisionId)) {
        throw new Error("Edition 4 selected image is not an immutable image revision");
      }
    }
    const childrenById = new Map(args.children.map((child) => [child.articleId, child]));
    if (childrenById.size !== 7) throw new Error("Edition 4 root must bind seven unique children");
    for (const planned of args.plan.children) {
      const child = childrenById.get(planned.articleId);
      if (child === undefined || !isDeepStrictEqual({
        articleId: child.articleId,
        articleExecutionId: child.articleExecutionId,
        runId: child.runId,
        sourceIds: child.sourceIds,
        sourceLineage: child.sourceLineage,
      }, planned)) {
        throw new Error(`Edition child ${planned.articleId} does not match its immutable plan`);
      }
      const childRun = this.#ledger.requireRun(child.runId);
      if (
        childRun.articleExecutionId !== child.articleExecutionId ||
        childRun.articleId !== child.articleId ||
        childRun.editionId !== "004" ||
        childRun.loopsRunId !== args.runId ||
        childRun.manuscriptArtifactId !== child.args.manuscriptArtifactId ||
        !isDeepStrictEqual(childRun.args, child.args as unknown as JsonObject)
      ) {
        throw new Error(`Edition child ${child.articleId} is not bound to the Edition 4 root`);
      }
      const childEntry = this.#ledger.requireArtifact(child.args.entryArtifactId);
      if (
        childEntry.kind !== "article_workflow_entry" ||
        childEntry.schemaVersion !== "loops-article-entry-input/1" ||
        childEntry.producingRunId !== child.runId ||
        childEntry.metadata.articleId !== child.articleId
      ) {
        throw new Error(`Edition child ${child.articleId} has an invalid entry artifact`);
      }
      const childEntryPayload = readJsonArtifact(this.#ledger, childEntry.id, `Edition child ${child.articleId} entry`);
      if (!isDeepStrictEqual(childEntryPayload, child.args.entry)) throw new Error(`Edition child ${child.articleId} entry payload changed`);
      assertChildSourceLineage(this.#ledger, child);
    }
  }

  async #prepareRootArgs(
    request: EditionStartRequest,
    runId: RunId,
    materialized: AuthenticatedWritePipelineInputs,
    pin: DurableWorkflowPin,
  ): Promise<EditionWorkflowArgs> {
    const pipeline = materialized.pipeline;
    if (pipeline.document.editionId !== "004" || pipeline.document.articles.length !== 7) {
      throw new Error("Edition 4 Loops root requires exactly seven pipeline articles");
    }
    if (pipeline.document.images.length !== 13) throw new Error("Edition 4 Loops root requires thirteen selected image revisions");
    const editionExecutionId = request.editionExecutionId ?? stableIdentity("edition-execution", runId);
    const articleWorkflowVersion = await this.#articleWorkflowVersion();
    const rendererIdentity = await this.#rendererIdentity();
    const dependencies: ArticleLaunchBuilderDependencies = {
      repositoryRoot: this.#repositoryRoot,
      ledger: this.#ledger,
      now: this.#clock.now,
      validateRuntimeResources: async () => undefined,
      getWorkflowVersion: async () => articleWorkflowVersion,
      getRendererIdentity: async () => rendererIdentity,
    };
    const children: EditionArticleChild[] = [];
    for (const article of pipeline.document.articles) {
      const childRunId = stableIdentity("article", `${runId}:${article.articleId}`) as RunId;
      const articleExecutionId = stableIdentity("article-execution", `${runId}:${article.articleId}`);
      const built = await buildAuthenticatedArticleLaunchArgsFromMaterialized(
        dependencies,
        materialized,
        article.articleId,
        {
          runId: childRunId,
          articleExecutionId: articleExecutionId as never,
          loopsRunId: runId,
          promotionId: stableIdentity("promotion", `${runId}:${article.articleId}`) as never,
          revisionId: stableRevision(`${runId}:${article.articleId}`),
        },
      );
      children.push({
        articleId: article.articleId,
        articleExecutionId,
        runId: childRunId,
        sourceIds: article.sourceIds,
        sourceLineage: sourceLineageForArticle(materialized, pipeline.document.sources, article.sourceIds),
        args: built.args,
      });
    }
    const selectedImageRevisions = pipeline.document.images;
    const plan: EditionPlanCheckpoint = {
      schemaVersion: "edition-plan-checkpoint/1",
      editionId: "004",
      pipelineRef: request.pipelineRef,
      pipelineDigest: pipeline.revision.manifestDigest,
      articleIds: pipeline.document.articles.map((article) => article.articleId),
      children: children.map((child) => ({
        articleId: child.articleId,
        articleExecutionId: child.articleExecutionId,
        runId: child.runId,
        sourceIds: child.sourceIds,
        sourceLineage: child.sourceLineage,
      })),
      selectedImageRevisions,
      imageGenerationAllowed: false,
    };
    const planArtifactId = `art-edition-plan-${safeIdentity(runId)}` as ArtifactId;
    const entryArtifactId = `art-edition-workflow-entry-${safeIdentity(runId)}` as ArtifactId;
    const sourceParents = uniqueSourceArtifactIds(plan.children);
    this.#ledger.createArtifact({
      id: planArtifactId,
      kind: "edition_plan",
      schemaVersion: "edition-plan-checkpoint/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: plan as unknown as JsonObject },
      parents: sourceParents.map((artifactId) => ({ artifactId, relation: "source_lineage" })),
      metadata: {
        editionId: "004",
        pipelineRevisionId: request.pipelineRef.revisionId,
        pipelineDigest: pipeline.revision.manifestDigest,
        imageGenerationAllowed: false,
      },
    });
    const args: EditionWorkflowArgs = deepFreeze({
      schemaVersion: "magazine-edition-workflow/1",
      editionId: "004",
      runId,
      editionExecutionId,
      planArtifactId,
      entryArtifactId,
      plan,
      children,
      selectedImageRevisions,
      imageGenerationAllowed: false,
    });
    // The entry artifact is run-owned, so create the root row before inserting
    // it.  The plan itself is unscoped evidence and can safely precede the
    // run row because it has no run foreign key.
    this.#ledger.createRun({
      runId,
      articleExecutionId: editionExecutionId as never,
      articleId: "edition-004",
      editionId: "004",
      workflowVersion: durableWorkflowVersionFromPin(pin),
      loopsRunId: runId,
      manuscriptArtifactId: planArtifactId,
      args: args as unknown as JsonObject,
      workflowPin: pin as unknown as JsonObject,
    });
    this.#ledger.createArtifact({
      id: entryArtifactId,
      kind: "edition_workflow_entry",
      schemaVersion: "magazine-edition-workflow/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: args as unknown as JsonObject },
      parents: [{ artifactId: planArtifactId, relation: "edition_plan" }],
      metadata: { editionId: "004", imageGenerationAllowed: false },
      runId,
    });
    return args;
  }

  async #loadPin(): Promise<DurableWorkflowPin> {
    this.#pinPromise ??= (async () => {
      const config = JSON.parse(await readFile(resolve(this.#projectRoot, EDITION_CONFIG), "utf8")) as Record<string, unknown>;
      return await buildDurableWorkflowPin({
        cwd: this.#projectRoot,
        scriptPath: EDITION_ENTRY,
        configPath: EDITION_CONFIG,
        config,
        backendSelection: NO_AGENT_BACKEND,
      });
    })();
    return await this.#pinPromise;
  }

  async #articleWorkflowVersion(): Promise<string> {
    this.#articleWorkflowVersionPromise ??= (async () => {
      const config = JSON.parse(await readFile(resolve(this.#projectRoot, ARTICLE_CONFIG), "utf8")) as Record<string, unknown>;
      const pin = await buildDurableWorkflowPin({
        cwd: this.#projectRoot,
        scriptPath: ARTICLE_ENTRY,
        configPath: ARTICLE_CONFIG,
        config,
        backendSelection: NO_AGENT_BACKEND,
      });
      return durableWorkflowVersionFromPin(pin);
    })();
    return await this.#articleWorkflowVersionPromise;
  }

  async #rendererIdentity(): Promise<RendererIdentity> {
    if (this.#options.rendererIdentity !== undefined) return this.#options.rendererIdentity;
    this.#rendererIdentityPromise ??= readVerifiedRendererIdentity(
      this.#projectRoot,
      ARTICLE_CONFIG,
      this.#options.renderer.toolchain,
    );
    return await this.#rendererIdentityPromise;
  }
}

const noAgentBackend = {
  name: NO_AGENT_BACKEND,
  capabilities: {
    nativeStructuredOutput: false,
    sessions: false,
    worktreeIsolation: false,
    reportsTokens: false,
  },
  async run(): Promise<never> {
    throw new Error("The magazine edition root does not permit agent calls");
  },
};

function sourceLineageForArticle(
  materialized: AuthenticatedWritePipelineInputs,
  sources: readonly { readonly sourceId: string; readonly capture: InputRevisionRef; readonly extraction: InputRevisionRef }[],
  sourceIds: readonly string[],
): readonly EditionSourceLineage[] {
  return sourceIds.map((sourceId) => {
    const source = sources.find((candidate) => candidate.sourceId === sourceId);
    if (source === undefined) throw new Error(`Edition pipeline has no source ${sourceId}`);
    return {
      sourceId,
      capture: source.capture,
      extraction: source.extraction,
      captureArtifactIds: artifactIdsForRef(materialized, source.capture),
      extractionArtifactIds: artifactIdsForRef(materialized, source.extraction),
    };
  });
}

function artifactIdsForRef(materialized: AuthenticatedWritePipelineInputs, ref: InputRevisionRef): readonly ArtifactId[] {
  const input = materialized.materializedInputs.find((candidate) => sameInput(candidate.ref, ref));
  if (input === undefined || input.artifacts.length === 0) throw new Error(`Edition pipeline did not materialize ${ref.kind}:${ref.logicalId}`);
  return input.artifacts.map((artifact) => artifact.artifactId);
}

function sameInput(left: InputRevisionRef, right: InputRevisionRef): boolean {
  return left.kind === right.kind && left.logicalId === right.logicalId && left.revisionId === right.revisionId && left.editionId === right.editionId;
}

function uniqueSourceArtifactIds(children: readonly Pick<EditionArticleChild, "sourceLineage">[]): readonly ArtifactId[] {
  const ids = children.flatMap((child) => child.sourceLineage.flatMap((lineage) => [...lineage.captureArtifactIds, ...lineage.extractionArtifactIds]));
  return [...new Set(ids)];
}

function uniqueSourceArtifactIdsFromPlan(plan: EditionPlanCheckpoint): readonly ArtifactId[] {
  const ids = plan.children.flatMap((child) => child.sourceLineage.flatMap((lineage) => [
    ...lineage.captureArtifactIds,
    ...lineage.extractionArtifactIds,
  ]));
  return [...new Set(ids)];
}

/**
 * Source lineage is bound to the exact profile-backed entry, not merely to a
 * self-declared list carried beside it.  Materializer order is canonical:
 * source IDs follow the pipeline order, and each revision's artifact IDs
 * follow the materializer's path-sorted order.  We compare that order
 * strictly so a reordered or substituted valid artifact cannot pass.
 */
function assertChildSourceLineage(ledger: ArtifactLedger, child: EditionArticleChild): void {
  const entrySourceIds = child.args.entry.sourceIds;
  if (!isDeepStrictEqual(child.sourceIds, entrySourceIds)) {
    throw new Error(`Edition child ${child.articleId} source IDs do not match its article entry`);
  }
  if (
    child.sourceIds.length === 0 ||
    new Set(child.sourceIds).size !== child.sourceIds.length ||
    child.sourceLineage.length !== child.sourceIds.length ||
    !isDeepStrictEqual(child.sourceLineage.map((lineage) => lineage.sourceId), child.sourceIds)
  ) {
    throw new Error(`Edition child ${child.articleId} source lineage does not follow its exact source order`);
  }

  const sourceInputs = child.args.entry.materializedInputs.filter((input) =>
    input.ref.kind === "source_capture" || input.ref.kind === "source_extraction",
  );
  if (sourceInputs.length !== child.sourceIds.length * 2) {
    throw new Error(`Edition child ${child.articleId} entry does not materialize exactly two source revisions per source`);
  }
  const sourceInputKeys = sourceInputs.map((input) => inputKey(input.ref));
  if (new Set(sourceInputKeys).size !== sourceInputKeys.length) {
    throw new Error(`Edition child ${child.articleId} entry repeats a source revision binding`);
  }

  for (const lineage of child.sourceLineage) {
    if (lineage.capture.kind !== "source_capture" || lineage.extraction.kind !== "source_extraction") {
      throw new Error(`Edition child ${child.articleId} source lineage has invalid kinds`);
    }
    const captureInput = sourceInputs.find((input) => isDeepStrictEqual(input.ref, lineage.capture));
    const extractionInput = sourceInputs.find((input) => isDeepStrictEqual(input.ref, lineage.extraction));
    if (captureInput === undefined || extractionInput === undefined) {
      throw new Error(`Edition child ${child.articleId} source ${lineage.sourceId} is not bound to its entry revisions`);
    }
    if (
      lineage.captureArtifactIds.length === 0 ||
      lineage.extractionArtifactIds.length === 0 ||
      !sameArtifactSequence(captureInput.artifacts.map((artifact) => artifact.artifactId), lineage.captureArtifactIds) ||
      !sameArtifactSequence(extractionInput.artifacts.map((artifact) => artifact.artifactId), lineage.extractionArtifactIds)
    ) {
      throw new Error(`Edition child ${child.articleId} source ${lineage.sourceId} has an inexact materialized artifact set`);
    }
    for (const [artifactId, expected] of [
      ...lineage.captureArtifactIds.map((artifactId) => [artifactId, lineage.capture] as const),
      ...lineage.extractionArtifactIds.map((artifactId) => [artifactId, lineage.extraction] as const),
    ]) {
      const artifact = ledger.requireArtifact(artifactId);
      if (!isDeepStrictEqual(artifact.metadata.inputRevision, expected)) {
        throw new Error(`Edition child ${child.articleId} source artifact ${artifactId} changed identity`);
      }
    }
  }
}

function inputKey(ref: InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

function sameArtifactSequence(left: readonly ArtifactId[], right: readonly ArtifactId[]): boolean {
  return left.length === right.length && left.every((artifactId, index) => artifactId === right[index]);
}

function readJsonArtifact(ledger: ArtifactLedger, artifactId: ArtifactId, label: string): unknown {
  try {
    return JSON.parse(Buffer.from(ledger.readArtifact(artifactId).bytes).toString("utf8")) as unknown;
  } catch (error) {
    throw new Error(`${label} is not valid JSON`, { cause: error });
  }
}

function sameParents(
  left: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
  right: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
): boolean {
  return left.length === right.length && left.every((parent, index) => {
    const expected = right[index];
    return expected !== undefined && parent.artifactId === expected.artifactId && parent.relation === expected.relation;
  });
}

function stableIdentity(prefix: string, value: string): string {
  return `${prefix}-${createHash("sha256").update(value).digest("hex").slice(0, 24)}`;
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function stableRevision(value: string): RevisionId {
  const digest = createHash("sha256").update(value).digest();
  const alphabet = "abcdefghijklmnopqrstuvwxyz234567";
  let bits = 0;
  let buffer = 0;
  let suffix = "";
  for (const byte of digest) {
    buffer = (buffer << 8) | byte;
    bits += 8;
    while (bits >= 5 && suffix.length < 12) {
      bits -= 5;
      suffix += alphabet[(buffer >>> bits) & 31]!;
      buffer &= (1 << bits) - 1;
    }
    if (suffix.length === 12) break;
  }
  return `rev_20260804T000000000Z_${suffix}` as RevisionId;
}

function safeIdentity(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]/gu, "_");
}

function deepFreeze<T>(value: T, seen = new WeakSet<object>()): T {
  if (value === null || typeof value !== "object" || seen.has(value)) return value;
  seen.add(value);
  for (const child of Object.values(value)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function isSuspension(error: unknown): boolean {
  return error instanceof Error && /suspend|wait|pending|durable/iu.test(error.message);
}
