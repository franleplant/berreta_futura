import { resolve } from "node:path";

import { z } from "zod";

import {
  LocalAuthorityStore,
  type AuthorizedWorker,
} from "../authority/local-authority.ts";
import type {
  KnownWorkRole,
  WorkOfferView,
  WorkerCapability,
  WorkerIdentity,
} from "../contracts/index.ts";
import type { RendererToolchainResource } from "../contracts/workflow-run.ts";
import {
  PythonRendererAdapter,
} from "../renderer-adapter/index.ts";
import { LocalSourceAdapter } from "../source-adapter/index.ts";
import { ImageModelExecutor } from "./image-model.ts";
import {
  ArticleMeasurementExecutor,
  LanguageFitExecutor,
} from "./layout-measurement.ts";
import { RenderInspectionExecutor } from "./render-inspection.ts";
import { RendererExecutor } from "./renderer.ts";
import { SourceArchiveExecutor } from "./source-archive.ts";
import {
  SubprocessExecutor,
  type SubprocessCommand,
} from "./subprocess.ts";
import { TextModelExecutor } from "./text-model.ts";
import { DurableCheckpointExecutor } from "./durable-checkpoint.ts";
import { CompositionBootstrapExecutor } from "./composition-bootstrap.ts";
import type { Executor } from "./types.ts";
import {
  ConfiguredExecutorResolver,
  type ExecutorRegistration,
  type RunWorkerOptions,
} from "./worker-loop.ts";

const capabilitySchema = z.enum([
  "human",
  "image_model",
  "source_access",
  "source_blind",
  "subprocess",
  "text_model",
]);

const commandSchema = z.object({
  executable: z.string().min(1),
  args: z.array(z.string()),
  cwd: z.string().min(1),
  env: z.record(z.string(), z.string()).optional(),
  timeoutMs: z.number().int().positive(),
  terminateGraceMs: z.number().int().positive().optional(),
}).strict();

const subprocessSchema = z.object({
  kind: z.literal("subprocess"),
  id: z.string().min(1),
  principalId: z.string().min(1).optional(),
  roles: z.array(z.string().min(1)).min(1),
  capabilities: z.array(capabilitySchema).min(1),
  command: commandSchema,
}).strict();

const modelSchema = z.object({
  kind: z.enum(["text_model", "image_model"]),
  id: z.string().min(1),
  principalId: z.string().min(1).optional(),
  roles: z.array(z.string().min(1)).min(1).optional(),
  adapter: z.string().min(1),
  model: z.string().min(1),
  reasoningEffort: z.string().min(1).optional(),
  capabilities: z.array(capabilitySchema).optional(),
  command: commandSchema,
}).strict();

const rendererSchema = z.object({
  kind: z.literal("python_renderer"),
  id: z.string().min(1).default("python-renderer"),
  principalId: z.string().min(1).optional(),
  projectRoot: z.string().min(1),
  workDirectory: z.string().min(1),
  adapterTimeoutMs: z.number().int().positive().optional(),
  toolchain: z.object({
    uvExecutable: z.string().min(1),
    pythonExecutable: z.string().min(1),
    expected: z.object({
      uvSha256: z.string().regex(/^sha256:[0-9a-f]{64}$/u),
      uvVersion: z.string().min(1),
      pythonSha256: z.string().regex(/^sha256:[0-9a-f]{64}$/u),
      pythonVersion: z.string().min(1),
      pythonImplementation: z.string().min(1),
      pythonCacheTag: z.string().min(1),
      platform: z.string().regex(/^[a-z0-9_]+-[a-z0-9_.-]+$/iu),
    }).strict(),
  }).strict(),
}).strict();

const sourceSchema = z.object({
  kind: z.literal("source_archive"),
  id: z.string().min(1).default("source-archive"),
  principalId: z.string().min(1).optional(),
  workDirectory: z.string().min(1),
}).strict();

const inspectionSchema = z.object({
  kind: z.literal("render_inspection"),
  id: z.string().min(1).default("render-inspection"),
  principalId: z.string().min(1).optional(),
}).strict();

const durableCheckpointSchema = z.object({
  kind: z.literal("durable_checkpoint"),
  id: z.string().min(1).default("durable-checkpoint"),
  principalId: z.string().min(1).optional(),
  command: commandSchema,
}).strict();

const compositionBootstrapSchema = z.object({
  kind: z.literal("composition_bootstrap"),
  id: z.string().min(1).default("composition-bootstrap"),
  principalId: z.string().min(1).optional(),
  projectRoot: z.string().min(1),
}).strict();

const workerConfigurationSchema = z.object({
  schemaVersion: z.literal(1),
  executors: z.array(z.discriminatedUnion("kind", [
    subprocessSchema,
    modelSchema,
    rendererSchema,
    sourceSchema,
    inspectionSchema,
    durableCheckpointSchema,
    compositionBootstrapSchema,
  ])).min(1),
  pollIntervalMs: z.number().int().positive().optional(),
  heartbeatIntervalMs: z.number().int().positive().optional(),
  attemptTimeoutMs: z.number().int().positive().optional(),
  maxConcurrency: z.number().int().positive().optional(),
}).strict();

export type WorkerConfiguration = z.infer<typeof workerConfigurationSchema>;

export type ConfiguredWorker = {
  readonly resolver: ConfiguredExecutorResolver;
  readonly options: RunWorkerOptions;
};

export type CreateConfiguredWorkerOptions = {
  /** Owner-private, ignored storage for configured worker credentials. */
  readonly authorityDirectory: string;
};

/** Exhaustive ownership table for every currently declared work role. */
export const WORK_ROLE_EXECUTION = {
  capture_source: "source_archive",
  extract_source: "text_model",
  review_source: "human",
  close_collection: "human",
  plan_edition: "human",
  writer: "closed_writer",
  measure_article: "article_measurement",
  worth: "text_model",
  mechanics: "text_model",
  evidence: "text_model",
  shape: "text_model",
  teaching: "text_model",
  craft: "text_model",
  editorial_writer: "text_model",
  edition_review: "text_model",
  translation_writer: "text_model",
  language_review: "text_model",
  language_fit: "language_fit",
  cover_image: "image_model",
  interior_image: "image_model",
  select_art: "human",
  measure_edition: "renderer",
  render: "renderer",
  render_reconciliation: "human",
  render_inspection: "render_inspection",
  visual_review: "human",
  release_approval: "human",
  durable_checkpoint: "durable_checkpoint",
  composition_bootstrap: "composition_bootstrap",
  editor_decision: "human",
} as const satisfies Record<KnownWorkRole, ExecutionOwner>;

type ExecutionOwner =
  | "article_measurement"
  | "closed_writer"
  | "human"
  | "image_model"
  | "language_fit"
  | "render_inspection"
  | "renderer"
  | "source_archive"
  | "text_model"
  | "durable_checkpoint"
  | "composition_bootstrap";

export async function createConfiguredWorker(
  value: unknown,
  options: CreateConfiguredWorkerOptions,
): Promise<ConfiguredWorker> {
  if (!options.authorityDirectory.trim()) {
    throw new Error("configured worker authorityDirectory must be non-empty");
  }
  const parsed = workerConfigurationSchema.safeParse(value);
  if (!parsed.success) {
    throw new Error(`worker configuration is invalid: ${parsed.error.message}`);
  }
  const registrations = parsed.data.executors.flatMap(createRegistrations);
  const ids = registrations.map(({ executor }) => executor.id);
  if (new Set(ids).size !== ids.length) {
    throw new Error("worker executor IDs must be unique after expansion");
  }
  const authority = await LocalAuthorityStore.init(resolve(options.authorityDirectory));
  const authorizedWorkers = await authorizeConfiguredWorkers(authority, registrations);
  return {
    resolver: new ConfiguredExecutorResolver(registrations.map((registration) => ({
      ...registration,
      authorizedWorker: requiredAuthorizedWorker(authorizedWorkers, registration.executor.worker.principalId),
    }))),
    options: {
      ...(parsed.data.pollIntervalMs === undefined
        ? {}
        : { pollIntervalMs: parsed.data.pollIntervalMs }),
      ...(parsed.data.heartbeatIntervalMs === undefined
        ? {}
        : { heartbeatIntervalMs: parsed.data.heartbeatIntervalMs }),
      ...(parsed.data.attemptTimeoutMs === undefined
        ? {}
        : { attemptTimeoutMs: parsed.data.attemptTimeoutMs }),
      ...(parsed.data.maxConcurrency === undefined
        ? {}
        : { maxConcurrency: parsed.data.maxConcurrency }),
    },
  };
}

function createRegistrations(
  value: WorkerConfiguration["executors"][number],
): readonly ExecutorRegistration[] {
  switch (value.kind) {
    case "subprocess": {
      requireCapability(value.capabilities, "subprocess", value.id);
      const worker = identity(
        value.principalId ?? value.id,
        "tool",
        value.capabilities,
        value.id,
      );
      const roles = [...value.roles];
      return [{
        executor: new SubprocessExecutor(
          value.id,
          worker,
          (_context, task) => command(value.command, task, undefined),
          (offer) => roles.includes(offer.role),
        ),
        roles,
      }];
    }
    case "text_model": {
      const capabilities = uniqueCapabilities([
        "text_model",
        ...(value.capabilities ?? []),
      ]);
      const worker = identity(
        value.principalId ?? value.id,
        "model",
        capabilities,
        value.id,
      );
      const choice = modelChoice(value);
      return [{
        executor: new TextModelExecutor(
          value.id,
          worker,
          (task, offer) => command(value.command, task, { offer, ...choice }),
        ),
        adapter: value.adapter,
        model: value.model,
        ...(value.reasoningEffort === undefined
          ? {}
          : { reasoningEffort: value.reasoningEffort }),
        ...(value.roles === undefined ? {} : { roles: value.roles }),
      }];
    }
    case "image_model": {
      const capabilities = uniqueCapabilities([
        "image_model",
        ...(value.capabilities ?? []),
      ]);
      const worker = identity(
        value.principalId ?? value.id,
        "model",
        capabilities,
        value.id,
      );
      const choice = modelChoice(value);
      return [{
        executor: new ImageModelExecutor(
          value.id,
          worker,
          (task, offer) => command(value.command, task, { offer, ...choice }),
        ),
        adapter: value.adapter,
        model: value.model,
        ...(value.reasoningEffort === undefined
          ? {}
          : { reasoningEffort: value.reasoningEffort }),
        roles: value.roles ?? ["cover_image", "interior_image"],
      }];
    }
    case "python_renderer": {
      const adapter = new PythonRendererAdapter(
        resolve(value.projectRoot),
        value.adapterTimeoutMs,
        undefined,
        value.toolchain as RendererToolchainResource,
      );
      const workDirectory = resolve(value.workDirectory);
      const principalId = value.principalId ?? value.id;
      return [
        explicit(
          new RendererExecutor(adapter, {
            id: `${value.id}:edition`,
            principalId,
            workDirectory,
          }),
          ["measure_edition", "render"],
        ),
        explicit(
          new ArticleMeasurementExecutor(adapter, {
            id: `${value.id}:article`,
            principalId,
            workDirectory,
          }),
          ["measure_article"],
        ),
        explicit(
          new LanguageFitExecutor(adapter, {
            id: `${value.id}:language`,
            principalId,
            workDirectory,
          }),
          ["language_fit"],
        ),
      ];
    }
    case "source_archive": {
      return [explicit(new SourceArchiveExecutor(new LocalSourceAdapter(), {
        id: value.id,
        ...(value.principalId === undefined ? {} : { principalId: value.principalId }),
        workDirectory: resolve(value.workDirectory),
      }), ["capture_source"])];
    }
    case "render_inspection":
      return [explicit(new RenderInspectionExecutor({
        id: value.id,
        ...(value.principalId === undefined ? {} : { principalId: value.principalId }),
      }), ["render_inspection"])];
    case "durable_checkpoint": {
      const worker = identity(
        value.principalId ?? value.id,
        "tool",
        ["subprocess"],
        value.id,
      );
      const delegate = new SubprocessExecutor(
        `${value.id}:promotion`,
        worker,
        (_context, task) => command(value.command, task, undefined),
        (offer) => offer.role === "durable_checkpoint",
      );
      return [explicit(new DurableCheckpointExecutor({
        checkpoint: (context) => delegate.execute(context),
      }, {
        id: value.id,
        ...(value.principalId === undefined ? {} : { principalId: value.principalId }),
      }), ["durable_checkpoint"])];
    }
    case "composition_bootstrap":
      return [explicit(new CompositionBootstrapExecutor({
        repositoryRoot: resolve(value.projectRoot),
        id: value.id,
        ...(value.principalId === undefined ? {} : { principalId: value.principalId }),
      }), ["composition_bootstrap"])];
  }
}

function explicit(executor: Executor, roles: readonly string[]): ExecutorRegistration {
  return { executor, roles };
}

function command(
  configured: z.infer<typeof commandSchema>,
  task: string,
  model: {
    readonly offer: WorkOfferView;
    readonly adapter: string;
    readonly model: string;
    readonly reasoningEffort?: string;
  } | undefined,
): SubprocessCommand {
  return {
    executable: configured.executable,
    args: configured.args.map((argument) => interpolate(argument, model)),
    cwd: resolve(configured.cwd),
    ...(configured.env === undefined ? {} : { env: configured.env }),
    timeoutMs: configured.timeoutMs,
    ...(configured.terminateGraceMs === undefined
      ? {}
      : { terminateGraceMs: configured.terminateGraceMs }),
    stdin: task,
  };
}

function interpolate(
  value: string,
  selection: {
    readonly offer: WorkOfferView;
    readonly adapter: string;
    readonly model: string;
    readonly reasoningEffort?: string;
  } | undefined,
): string {
  if (selection === undefined) {
    return value;
  }
  return value
    .replaceAll("{adapter}", selection.adapter)
    .replaceAll("{model}", selection.model)
    .replaceAll("{reasoningEffort}", selection.reasoningEffort ?? "")
    .replaceAll("{role}", selection.offer.role)
    .replaceAll("{offerId}", selection.offer.id);
}

function identity(
  principalId: string,
  authority: WorkerIdentity["authority"],
  capabilities: readonly WorkerCapability[],
  displayName: string,
): WorkerIdentity {
  return { principalId, authority, capabilities, displayName };
}

function modelChoice(value: {
  readonly adapter: string;
  readonly model: string;
  readonly reasoningEffort?: string | undefined;
}) {
  return {
    adapter: value.adapter,
    model: value.model,
    ...(value.reasoningEffort === undefined
      ? {}
      : { reasoningEffort: value.reasoningEffort }),
  };
}

function requireCapability(
  capabilities: readonly WorkerCapability[],
  required: WorkerCapability,
  id: string,
): void {
  if (!capabilities.includes(required)) {
    throw new Error(`executor ${id} must declare ${required}`);
  }
}

function uniqueCapabilities(
  capabilities: readonly WorkerCapability[],
): readonly WorkerCapability[] {
  return [...new Set(capabilities)];
}

async function authorizeConfiguredWorkers(
  authority: LocalAuthorityStore,
  registrations: readonly ExecutorRegistration[],
): Promise<ReadonlyMap<string, AuthorizedWorker>> {
  const requested = new Map<string, {
    authority: Exclude<WorkerIdentity["authority"], "human">;
    capabilities: Set<Exclude<WorkerCapability, "human">>;
  }>();
  for (const { executor } of registrations) {
    const worker = executor.worker;
    if (worker.authority === "human" || worker.capabilities.includes("human")) {
      throw new Error(`configured executor ${executor.id} may not be enrolled as a human worker`);
    }
    const existing = requested.get(worker.principalId);
    if (existing !== undefined && existing.authority !== worker.authority) {
      throw new Error(`configured principal ${worker.principalId} has conflicting authority`);
    }
    const entry = existing ?? {
      authority: worker.authority,
      capabilities: new Set<Exclude<WorkerCapability, "human">>(),
    };
    for (const capability of worker.capabilities) {
      if (capability !== "human") {
        entry.capabilities.add(capability);
      }
    }
    requested.set(worker.principalId, entry);
  }

  const snapshot = await authority.snapshot();
  const sessions = new Map<string, AuthorizedWorker>();
  for (const [principalId, worker] of requested) {
    const existing = snapshot.principals.find((principal) => principal.principalId === principalId);
    const capabilities = [...worker.capabilities].sort();
    if (existing === undefined) {
      await authority.enrollWorker({ principalId, authority: worker.authority, capabilities });
    } else if (
      existing.revoked ||
      existing.authority !== worker.authority ||
      capabilities.some((capability) => !existing.capabilities.includes(capability))
    ) {
      throw new Error(`configured principal ${principalId} is incompatible with its persisted authority enrollment`);
    }
    const credential = await authority.createCredentialProfile({ principalId, label: "configured-worker" });
    await authority.grant({
      credentialProfileId: credential.credentialProfileId,
      capabilities,
    });
    sessions.set(principalId, await authority.authenticate({
      credentialProfileId: credential.credentialProfileId,
      secret: credential.secret,
    }));
  }
  return sessions;
}

function requiredAuthorizedWorker(
  workers: ReadonlyMap<string, AuthorizedWorker>,
  principalId: string,
): AuthorizedWorker {
  const worker = workers.get(principalId);
  if (worker === undefined) {
    throw new Error(`configured principal ${principalId} has no authenticated credential`);
  }
  return worker;
}
