import { resolve } from "node:path";
import { readFile } from "node:fs/promises";

import {
  createRuntime,
  durableWorkflowVersionFromPin,
  SQLiteDurableRunStore,
  type DurableWorkflowPin,
  type LoopsConfig,
  type WorkflowGlobals,
} from "@loops/core";
import { buildDurableWorkflowPin } from "@loops/workflow";

import type {
  ArticleDecisionAnswer,
  RendererToolchainResource,
} from "../contracts/workflow-run.ts";
import type {
  ArticleRuntimeStartArgs,
  ArticleWorkflowPorts,
  MagazineLoopsInspection,
} from "./internal-types.ts";
import articleLoopsEntry from "./article-loops-entry.ts";
import {
  assertRendererIdentity,
  hashRendererIdentityManifest,
  readVerifiedRendererIdentity,
  type RendererIdentity,
} from "./renderer-identity.ts";

type LoopsPort = {
  getWorkflowVersion(): Promise<string>;
  getRendererIdentity(): Promise<RendererIdentity>;
  startArticle(runId: string, args: ArticleRuntimeStartArgs): Promise<unknown>;
  resumeArticle(runId: string): Promise<unknown>;
  answerDecision(input: { readonly runId: string; readonly waitId: string; readonly decisionArtifactId: import("../contracts/index.ts").ArtifactId }): Promise<unknown>;
  inspect(runId: string): Promise<MagazineLoopsInspection>;
  close?: () => void;
};

const ARTICLE_WORKFLOW_NAME = "magazine-article";
const ARTICLE_WORKFLOW_ENTRY = "engine/workflows/article-loops-entry.ts";
const ARTICLE_RUNTIME_IDENTITY = "engine/workflows/article-runtime-identity.json";
const ARTICLE_BACKEND = "magazine-no-agent";

type DurableLoopsAdapterOptions = {
  readonly storePath: string;
  readonly projectRoot: string;
  readonly toolchain: RendererToolchainResource;
  readonly runtime: ArticleWorkflowPorts;
};

/** Private fixed adapter used only by MagazineWorkflowEngine. */
export function createDurableLoopsAdapter(options: DurableLoopsAdapterOptions): LoopsPort {
  return new PrivateDurableLoopsAdapter(options);
}

class PrivateDurableLoopsAdapter implements LoopsPort {
  readonly #store: SQLiteDurableRunStore;
  readonly #projectRoot: string;
  readonly #toolchain: RendererToolchainResource;
  readonly #runtime: ArticleWorkflowPorts;

  constructor(options: DurableLoopsAdapterOptions) {
    this.#store = new SQLiteDurableRunStore(resolve(options.storePath));
    this.#projectRoot = resolve(options.projectRoot);
    this.#toolchain = options.toolchain;
    this.#runtime = options.runtime;
  }

  async startArticle(runId: string, args: ArticleRuntimeStartArgs): Promise<unknown> {
    return await this.#run(runId, args);
  }

  async resumeArticle(runId: string): Promise<unknown> {
    const stored = this.#store.getRun(runId);
    if (stored === null) throw new Error(`Loops run ${runId} does not exist`);
    return await this.#run(runId, stored.args as ArticleRuntimeStartArgs);
  }

  async answerDecision(input: {
    readonly runId: string;
    readonly waitId: string;
    readonly decisionArtifactId: import("../contracts/index.ts").ArtifactId;
  }): Promise<unknown> {
    const answer: ArticleDecisionAnswer = { decisionArtifactId: input.decisionArtifactId };
    return this.#store.answerWait({ runId: input.runId, waitId: input.waitId, answer });
  }

  async inspect(runId: string): Promise<MagazineLoopsInspection> {
    await this.#loadPin();
    const inspection = this.#store.inspectRun(runId);
    if (inspection === null) throw new Error(`Loops run ${runId} does not exist`);
    const result = inspection.run.result;
    return {
      runId,
      status: inspection.run.status,
      workflowVersion: inspection.run.workflowVersion,
      ...(inspection.run.workflowPin === undefined ? {} : { workflowPin: inspection.run.workflowPin as never }),
      ...(isArticleResult(result) ? { result } : {}),
      invocations: inspection.invocations.map((invocation) => ({
        invocationId: invocation.invocationId,
        ...(invocation.parentInvocationId === undefined ? {} : { parentInvocationId: invocation.parentInvocationId }),
        workflowName: invocation.workflowName,
        workflowVersion: invocation.workflowVersion,
        ...(invocation.workflowPin === undefined ? {} : { workflowPin: invocation.workflowPin as never }),
        status: invocation.status,
      })),
      calls: inspection.calls.map((call) => ({
        callId: call.callId,
        invocationId: call.invocationId,
        key: call.key,
        kind: call.kind,
        status: call.status,
        ...(call.result === undefined ? {} : { result: call.result }),
        attempts: inspection.attempts
          .filter((attempt) => attempt.callId === call.callId)
          .map((attempt) => ({
            attemptId: attempt.attemptId,
            attemptNumber: attempt.attemptNumber,
            status: attempt.status,
          })),
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
    this.#store.close();
  }

  async getWorkflowVersion(): Promise<string> {
    const { pin } = await this.#loadPin();
    return durableWorkflowVersionFromPin(pin);
  }

  async getRendererIdentity(): Promise<RendererIdentity> {
    return (await this.#loadPin()).rendererIdentity;
  }

  async #run(runId: string, args: ArticleRuntimeStartArgs): Promise<unknown> {
    const { pin, rendererIdentity } = await this.#loadPin();
    assertRendererIdentity(args.rendererIdentity, rendererIdentity, "article run renderer identity");
    if (pin.execution.configPath !== ARTICLE_RUNTIME_IDENTITY) {
      throw new Error("Loops durable pin does not bind the verified renderer identity manifest");
    }
    const stored = this.#store.getRun(runId);
    const storedConfigHash = stored?.workflowPin?.execution.configHash;
    if (storedConfigHash !== undefined && storedConfigHash !== pin.execution.configHash) {
      throw new Error("article run renderer config hash changed after the run was frozen");
    }
    const runtime = createRuntime({
      backend: noAgentBackend,
      defaultBackend: ARTICLE_BACKEND,
      durable: {
        store: this.#store,
        runId,
        workflowName: ARTICLE_WORKFLOW_NAME,
        workflowPin: pin,
        args,
      },
      args,
      cwd: this.#projectRoot,
    });
    return await runtime.run((globals: WorkflowGlobals) => articleLoopsEntry(globals, this.#runtime));
  }

  async #loadPin(): Promise<{ readonly pin: DurableWorkflowPin; readonly rendererIdentity: RendererIdentity }> {
    const rendererIdentity = await readVerifiedRendererIdentity(this.#projectRoot, ARTICLE_RUNTIME_IDENTITY, this.#toolchain);
    const config = JSON.parse(await readFile(resolve(this.#projectRoot, ARTICLE_RUNTIME_IDENTITY), "utf8")) as LoopsConfig;
    const pin = await buildDurableWorkflowPin({
      cwd: this.#projectRoot,
      scriptPath: ARTICLE_WORKFLOW_ENTRY,
      configPath: ARTICLE_RUNTIME_IDENTITY,
      config,
      backendSelection: ARTICLE_BACKEND,
    });
    const manifestHash = await hashRendererIdentityManifest(this.#projectRoot, ARTICLE_RUNTIME_IDENTITY);
    if (pin.execution.configHash !== manifestHash) {
      throw new Error("Loops durable pin configHash does not match the exact renderer identity manifest bytes");
    }
    return { pin, rendererIdentity };
  }
}

const noAgentBackend = {
  name: ARTICLE_BACKEND,
  capabilities: {
    nativeStructuredOutput: false,
    sessions: false,
    worktreeIsolation: false,
    reportsTokens: false,
  },
  async run(): Promise<never> {
    throw new Error("The magazine article workflow does not permit agent calls");
  },
};

function isArticleResult(value: unknown): value is import("../contracts/workflow-run.ts").ArticleWorkflowResult | import("../contracts/workflow-run.ts").ArticleWorkflowRouteResult {
  return typeof value === "object" && value !== null &&
    ((value as { readonly schemaVersion?: unknown }).schemaVersion === "magazine-article-workflow-result/1"
      || (value as { readonly schemaVersion?: unknown }).schemaVersion === "magazine-article-route-result/1");
}
