import { rm } from "node:fs/promises";

import { z } from "zod";

import type {
  AnswerArtifact,
  ArtifactId,
  JsonObject,
  WorkAnswer,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import {
  RENDERER_CONTRACT_VERSION,
  type RenderAssemblyManifest,
  type RendererAdapter,
  type RenderExecutionProfile,
  type RenderManifest,
} from "../renderer-adapter/index.ts";
import {
  createAdapterWorkspace,
  permanentAdapterError,
  readJsonArtifact,
  requireExactSequence,
  requireOwnedOutputFile,
  requireSafeTargetPath,
  stageArtifact,
  writeAdapterRequest,
} from "./adapter-workspace.ts";
import type { Executor, ExecutorContext } from "./types.ts";

const profileSchema = z.object({
  schemaVersion: z.literal(1),
  rendererContractVersion: z.literal(RENDERER_CONTRACT_VERSION),
  primaryLanguage: z.string().min(1),
  publicationName: z.string().min(1),
  renderer: z.enum(["reportlab", "weasyprint"]),
  design: z.string().min(1).optional(),
  inputs: z.array(z.object({
    artifactId: z.string().min(1),
    targetPath: z.string().min(1),
  }).strict()).min(1),
  metadata: z.record(z.string(), z.json()).optional(),
}).strict();

const assemblySchema = z.object({
  editionId: z.string().min(1),
  content: z.array(z.string().min(1)),
  translations: z.array(z.string().min(1)),
  translationProofs: z.array(z.string().min(1)),
  art: z.array(z.string().min(1)),
  editionApproval: z.array(z.string().min(1)),
  configuredLanguages: z.array(z.string().min(1)).min(1),
  renderProfileArtifactId: z.string().min(1),
  printerProfileArtifactId: z.string().min(1).nullable(),
}).strict();

export type RendererExecutorOptions = {
  readonly id?: string;
  readonly principalId?: string;
  readonly workDirectory: string;
};

export class RendererExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities = ["subprocess"] as const;
  private readonly adapter: RendererAdapter;
  private readonly workDirectory: string;
  private readonly attemptRoots = new Map<string, string>();

  constructor(adapter: RendererAdapter, options: RendererExecutorOptions) {
    this.adapter = adapter;
    this.id = options.id ?? "renderer";
    this.workDirectory = options.workDirectory;
    this.worker = {
      principalId: options.principalId ?? this.id,
      authority: "tool",
      capabilities: this.capabilities,
      displayName: "Versioned renderer adapter",
    };
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "measure_edition" || offer.role === "render";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    const assemblyResult = assemblySchema.safeParse(await readJsonArtifact(
      context.artifacts,
      context.offer.taskArtifactId,
      "render assembly manifest",
    ));
    if (!assemblyResult.success) {
      throw permanentAdapterError(
        `render assembly manifest is invalid: ${assemblyResult.error.message}`,
      );
    }
    const assembly = assemblyResult.data as unknown as RenderAssemblyManifest;
    if (context.artifacts.readArtifact === undefined) {
      throw permanentAdapterError("renderer executor requires artifact lineage access");
    }
    const assemblyRecord = await context.artifacts.readArtifact(context.offer.taskArtifactId);
    validateAssemblyLineage(assembly, assemblyRecord.artifact.parents);
    const profileResult = profileSchema.safeParse(await readJsonArtifact(
      context.artifacts,
      assembly.renderProfileArtifactId,
      "render execution profile",
    ));
    if (!profileResult.success) {
      throw permanentAdapterError(`render execution profile is invalid: ${profileResult.error.message}`);
    }
    const profile = profileResult.data as unknown as RenderExecutionProfile;
    const profileRecord = await context.artifacts.readArtifact(
      assembly.renderProfileArtifactId,
    );
    validateRenderInputs(
      assembly,
      profile,
      new Set([
        ...assemblyRecord.artifact.parents.map((parent) => parent.artifactId),
        ...profileRecord.artifact.parents.map((parent) => parent.artifactId),
      ]),
    );

    const workspace = await createAdapterWorkspace(
      this.workDirectory,
      `render-${context.claim.attemptId}`,
    );
    this.attemptRoots.set(context.claim.attemptId, workspace.root);
    const inputs = await Promise.all(
      profile.inputs.map(async (input, index) => ({
        artifactId: input.artifactId,
        sourcePath: await stageArtifact(
          context.artifacts,
          input.artifactId,
          workspace.inputRoot,
          index,
        ),
        targetPath: input.targetPath,
      })),
    );
    const operation = context.offer.role === "measure_edition"
      ? "measure_edition"
      : "render_edition";
    const manifest: RenderManifest = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      operation,
      editionId: assembly.editionId,
      primaryLanguage: profile.primaryLanguage,
      languages: assembly.configuredLanguages,
      publicationName: profile.publicationName,
      renderer: profile.renderer,
      artifactRoot: workspace.inputRoot,
      inputs,
      ...(profile.design === undefined ? {} : { design: profile.design }),
      metadata: {
        ...(profile.metadata ?? {}),
        assemblyManifestArtifactId: context.offer.taskArtifactId,
        renderProfileArtifactId: assembly.renderProfileArtifactId,
        attemptId: context.claim.attemptId,
      },
    };
    await writeAdapterRequest(workspace.requestPath, manifest);
    const result = await this.adapter.render(
      workspace.requestPath,
      workspace.outputRoot,
      context.signal,
    );
    validateRenderResult(assembly, profile, result);

    const commonMetadata: JsonObject = {
      editionId: assembly.editionId,
      adapterContractVersion: RENDERER_CONTRACT_VERSION,
      inputArtifactIds: result.inputArtifactIds,
    };
    if (operation === "measure_edition") {
      if (result.files.length !== 0) {
        throw permanentAdapterError("measure_edition returned render files");
      }
      return {
        contractVersion: context.offer.contractVersion,
        result: {
          result: "pass",
          fits: true,
          measuredLanguages: result.layouts.map((layout) => layout.language),
          inputArtifactIds: result.inputArtifactIds,
        },
        artifacts: [{
          kind: "edition_measurement",
          schemaVersion: RENDERER_CONTRACT_VERSION,
          mediaType: "application/json",
          payload: {
            kind: "json",
            value: {
              schemaVersion: 1,
              editionId: assembly.editionId,
              layouts: result.layouts as unknown as readonly JsonObject[],
              inputArtifactIds: result.inputArtifactIds,
            },
          },
          parents: profile.inputs.map((input) => ({
            artifactId: input.artifactId,
            relation: "measured_input",
          })),
          metadata: commonMetadata,
        }],
        metadata: { executorId: this.id, operation },
      };
    }

    if (result.files.length === 0) {
      throw permanentAdapterError("render_edition returned no render files");
    }
    const artifacts: AnswerArtifact[] = [];
    for (const file of result.files) {
      const path = await requireOwnedOutputFile(workspace.outputRoot, file.path);
      artifacts.push({
        kind: file.kind,
        schemaVersion: RENDERER_CONTRACT_VERSION,
        mediaType: file.mediaType,
        payload: { kind: "file", path },
        parents: profile.inputs.map((input) => ({
          artifactId: input.artifactId,
          relation: "render_input",
        })),
        metadata: { ...commonMetadata, relativePath: file.path },
      });
    }
    return {
      contractVersion: context.offer.contractVersion,
      result: {
        renderedLanguages: result.layouts.map((layout) => layout.language),
        inputArtifactIds: result.inputArtifactIds,
        tailArtFacts: result.tailArtFacts,
      },
      artifacts,
      metadata: { executorId: this.id, operation },
    };
  }

  async release(context: ExecutorContext): Promise<void> {
    const root = this.attemptRoots.get(context.claim.attemptId);
    if (root === undefined) {
      return;
    }
    this.attemptRoots.delete(context.claim.attemptId);
    await rm(root, { recursive: true, force: true });
  }
}

function validateRenderInputs(
  assembly: RenderAssemblyManifest,
  profile: RenderExecutionProfile,
  authorizedArtifactIds: ReadonlySet<ArtifactId>,
): void {
  if (new Set(assembly.configuredLanguages).size !== assembly.configuredLanguages.length) {
    throw permanentAdapterError("render assembly languages must be unique");
  }
  if (!assembly.configuredLanguages.includes(profile.primaryLanguage)) {
    throw permanentAdapterError("render profile primary language is not configured by assembly");
  }
  const inputIds = profile.inputs.map((input) => input.artifactId);
  const targets = profile.inputs.map((input) => input.targetPath);
  if (new Set(inputIds).size !== inputIds.length || new Set(targets).size !== targets.length) {
    throw permanentAdapterError("render profile artifact IDs and target paths must be unique");
  }
  profile.inputs.forEach((input, index) =>
    requireSafeTargetPath(input.targetPath, `render profile inputs[${index}].targetPath`),
  );
  const staged = new Set(inputIds);
  const required = [
    ...assembly.content,
    ...assembly.translations,
    ...assembly.art,
    ...(assembly.printerProfileArtifactId === null
      ? []
      : [assembly.printerProfileArtifactId]),
  ];
  const missing = required.filter((artifactId) => !staged.has(artifactId));
  if (missing.length > 0) {
    throw permanentAdapterError(
      `render profile does not bind assembled artifacts: ${missing.join(", ")}`,
    );
  }
  const unauthorized = inputIds.filter((artifactId) => !authorizedArtifactIds.has(artifactId));
  if (unauthorized.length > 0) {
    throw permanentAdapterError(
      `render profile binds artifacts outside its immutable lineage: ${unauthorized.join(", ")}`,
    );
  }
}

function validateAssemblyLineage(
  assembly: RenderAssemblyManifest,
  parents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
): void {
  requireRelation(parents, "content", assembly.content);
  requireRelation(parents, "translation", assembly.translations);
  requireRelation(parents, "translation_approval", assembly.translationProofs);
  requireRelation(parents, "selected_art", assembly.art);
  requireRelation(parents, "edition_approval", assembly.editionApproval);
  requireRelation(parents, "render_profile", [assembly.renderProfileArtifactId]);
  requireRelation(
    parents,
    "printer_profile",
    assembly.printerProfileArtifactId === null ? [] : [assembly.printerProfileArtifactId],
  );
}

function requireRelation(
  parents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
  relation: string,
  expected: readonly ArtifactId[],
): void {
  const actual = parents
    .filter((parent) => parent.relation === relation)
    .map((parent) => parent.artifactId);
  requireExactSequence(expected, actual, `render assembly ${relation} lineage`);
}

function validateRenderResult(
  assembly: RenderAssemblyManifest,
  profile: RenderExecutionProfile,
  result: Awaited<ReturnType<RendererAdapter["render"]>>,
): void {
  if (
    result.schemaVersion !== 1 ||
    result.rendererContractVersion !== RENDERER_CONTRACT_VERSION ||
    result.editionId !== assembly.editionId
  ) {
    throw permanentAdapterError("renderer returned the wrong contract or edition identity");
  }
  requireExactSequence(
    profile.inputs.map((input) => input.artifactId),
    result.inputArtifactIds,
    "renderer result",
  );
  requireExactSequence(
    assembly.configuredLanguages,
    result.layouts.map((layout) => layout.language),
    "renderer layouts",
  );
}
