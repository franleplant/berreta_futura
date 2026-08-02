import { resolve } from "node:path";

import { z } from "zod";

import type {
  KnownWorkRole,
  WorkOfferView,
  WorkerCapability,
  WorkerIdentity,
} from "../contracts/index.ts";
import {
  PythonRendererAdapter,
} from "../renderer-adapter/index.ts";
import { PythonSourceAdapter } from "../source-adapter/index.ts";
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
}).strict();

const sourceSchema = z.object({
  kind: z.literal("python_source_archive"),
  id: z.string().min(1).default("python-source-archive"),
  principalId: z.string().min(1).optional(),
  projectRoot: z.string().min(1),
  workDirectory: z.string().min(1),
  adapterTimeoutMs: z.number().int().positive().optional(),
}).strict();

const inspectionSchema = z.object({
  kind: z.literal("render_inspection"),
  id: z.string().min(1).default("render-inspection"),
  principalId: z.string().min(1).optional(),
}).strict();

const workerConfigurationSchema = z.object({
  schemaVersion: z.literal(1),
  executors: z.array(z.discriminatedUnion("kind", [
    subprocessSchema,
    modelSchema,
    rendererSchema,
    sourceSchema,
    inspectionSchema,
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

/** Exhaustive ownership table for every currently declared work role. */
export const WORK_ROLE_EXECUTION = {
  capture_source: "source_archive",
  extract_source: "text_model",
  review_source: "human",
  close_collection: "human",
  plan_edition: "human",
  writer: "text_model",
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
  render_inspection: "render_inspection",
  visual_review: "human",
  release_approval: "human",
  editor_decision: "human",
} as const satisfies Record<KnownWorkRole, ExecutionOwner>;

type ExecutionOwner =
  | "article_measurement"
  | "human"
  | "image_model"
  | "language_fit"
  | "render_inspection"
  | "renderer"
  | "source_archive"
  | "text_model";

export function createConfiguredWorker(value: unknown): ConfiguredWorker {
  const parsed = workerConfigurationSchema.safeParse(value);
  if (!parsed.success) {
    throw new Error(`worker configuration is invalid: ${parsed.error.message}`);
  }
  const registrations = parsed.data.executors.flatMap(createRegistrations);
  const ids = registrations.map(({ executor }) => executor.id);
  if (new Set(ids).size !== ids.length) {
    throw new Error("worker executor IDs must be unique after expansion");
  }
  return {
    resolver: new ConfiguredExecutorResolver(registrations),
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
      );
      const workDirectory = resolve(value.workDirectory);
      const prefix = value.principalId ?? value.id;
      return [
        explicit(
          new RendererExecutor(adapter, {
            id: `${value.id}:edition`,
            principalId: `${prefix}:edition`,
            workDirectory,
          }),
          ["measure_edition", "render"],
        ),
        explicit(
          new ArticleMeasurementExecutor(adapter, {
            id: `${value.id}:article`,
            principalId: `${prefix}:article`,
            workDirectory,
          }),
          ["measure_article"],
        ),
        explicit(
          new LanguageFitExecutor(adapter, {
            id: `${value.id}:language`,
            principalId: `${prefix}:language`,
            workDirectory,
          }),
          ["language_fit"],
        ),
      ];
    }
    case "python_source_archive": {
      const adapter = new PythonSourceAdapter(
        resolve(value.projectRoot),
        value.adapterTimeoutMs,
      );
      return [explicit(new SourceArchiveExecutor(adapter, {
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
