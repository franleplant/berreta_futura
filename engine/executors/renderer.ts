import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

import { z } from "zod";
import { parse } from "yaml";

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
  AdapterWorkspaceOwner,
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
  editionPackageId: z.string().min(1).optional(),
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
  private readonly workspaces: AdapterWorkspaceOwner;

  constructor(adapter: RendererAdapter, options: RendererExecutorOptions) {
    this.adapter = adapter;
    this.id = options.id ?? "renderer";
    this.workspaces = new AdapterWorkspaceOwner(options.workDirectory);
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
    const effectiveInputs = await deriveEffectiveRenderInputs(context, assembly, profile);
    validateRenderInputs(
      assembly,
      { ...profile, inputs: effectiveInputs },
      new Set([
        ...assemblyRecord.artifact.parents.map((parent) => parent.artifactId),
        ...profileRecord.artifact.parents.map((parent) => parent.artifactId),
      ]),
    );
    const editionPackageId = await resolveEditionPackageId(context, profile, effectiveInputs);

    const workspace = await this.workspaces.create(
      context.claim.attemptId,
      `render-${context.claim.attemptId}`,
    );
    const stagedInputs = await Promise.all(
      effectiveInputs.map(async (input, index) => ({
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
    const inputs = await materializeCurrentTranslationOverlays(stagedInputs, workspace.inputRoot);
    const operation = context.offer.role === "measure_edition"
      ? "measure_edition"
      : "render_edition";
    const manifest: RenderManifest = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      operation,
      editionId: editionPackageId,
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
    validateRenderResult(assembly, effectiveInputs, result, editionPackageId);

    const commonMetadata: JsonObject = {
      editionId: assembly.editionId,
      editionPackageId,
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
          parents: effectiveInputs.map((input) => ({
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
          parents: effectiveInputs.map((input) => ({
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
    await this.workspaces.release(context.claim.attemptId);
  }
}

/**
 * The committed Spanish edition document is a localization template. At the
 * renderer boundary we derive the active overlay solely from already-staged,
 * immutable English and Spanish manuscript artifacts, replacing only its
 * current-English byte pins. The generated file stays in caller-owned scratch
 * and is represented by the immutable template artifact in the transport
 * manifest; Python receives only that completed manifest and staged inputs.
 */
export async function materializeCurrentTranslationOverlays(
  inputs: readonly RenderManifest["inputs"][number][],
  inputRoot: string,
  options: { readonly pieceId?: string } = {},
): Promise<readonly RenderManifest["inputs"][number][]> {
  const byTarget = new Map(inputs.map((input) => [input.targetPath, input]));
  const templates = inputs.filter((input) => input.targetPath.endsWith("/translations/es/edition.template.yaml"));
  if (templates.length === 0) return inputs;
  if (templates.length !== 1) throw permanentAdapterError("renderer has ambiguous Spanish translation templates");
  const template = templates[0]!;
  const root = template.targetPath.slice(0, -"/translations/es/edition.template.yaml".length);
  const required = (targetPath: string): RenderManifest["inputs"][number] => {
    const input = byTarget.get(targetPath);
    if (input === undefined) throw permanentAdapterError(`current Spanish overlay is missing ${targetPath}`);
    return input;
  };
  let document: unknown;
  try {
    document = parse(await readFile(template.sourcePath, "utf8"));
  } catch (error) {
    throw permanentAdapterError(`Spanish translation template cannot be read: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!isRecord(document) || !Array.isArray(document.articles) || !isRecord(document.editorial)) {
    throw permanentAdapterError("Spanish translation template has an invalid overlay shape");
  }
  const articles = document.articles as unknown[];
  if (options.pieceId !== undefined) {
    document.articles = options.pieceId === "opening"
      ? []
      : articles.filter((row) => isRecord(row) && row.id === options.pieceId);
    if (options.pieceId !== "opening") delete document.editorial;
  }
  if (isRecord(document.editorial)) {
    const englishEditorial = required(`${root}/manuscript/editorial.md`);
    document.editorial.source_sha256 = await artifactHash(englishEditorial.sourcePath);
  }
  for (const row of document.articles as unknown[]) {
    if (!isRecord(row) || typeof row.id !== "string") {
      throw permanentAdapterError("Spanish translation template has an invalid article row");
    }
    const english = required(`${root}/articles/${row.id}.md`);
    row.source_sha256 = await artifactHash(english.sourcePath);
  }
  const overlayPath = join(inputRoot, "derived", `${template.artifactId}-es-overlay.yaml`);
  await mkdir(dirname(overlayPath), { recursive: true, mode: 0o700 });
  await writeFile(overlayPath, JSON.stringify(document), { encoding: "utf8", mode: 0o600 });
  return inputs.map((input) => input === template
    ? { ...input, sourcePath: overlayPath, targetPath: `${root}/translations/es/edition.yaml` }
    : input);
}

/** Builds a one-piece renderer manifest only for isolated measurement. */
export async function materializeReducedMeasurementEdition(
  inputs: readonly RenderManifest["inputs"][number][],
  inputRoot: string,
  pieceId: string,
  language: "en" | "es",
): Promise<readonly RenderManifest["inputs"][number][]> {
  const base = inputs.find((input) => /^editions\/[^/]+\/edition\.yaml$/u.test(input.targetPath));
  if (base === undefined) throw permanentAdapterError("measurement is missing its committed edition manifest");
  let document: unknown;
  try {
    document = parse(await readFile(base.sourcePath, "utf8"));
  } catch (error) {
    throw permanentAdapterError(`measurement edition cannot be read: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!isRecord(document) || !Array.isArray(document.articles)) {
    throw permanentAdapterError("measurement edition has an invalid article list");
  }
  const sourceArticle = document.articles.find((row) => isRecord(row) && row.id === pieceId);
  if (pieceId !== "opening" && !isRecord(sourceArticle)) {
    throw permanentAdapterError(`measurement edition has no article ${pieceId}`);
  }
  document.articles = pieceId === "opening" ? [] : [sourceArticle];
  document.sources = pieceId === "opening" ? [] : sourceArticle.source_ids;
  document.closing_plates = [];
  if (pieceId !== "opening") document.editorial = null;
  if (language === "es") {
    const template = inputs.find((input) => input.targetPath.endsWith("/translations/es/edition.template.yaml"));
    if (template === undefined) throw permanentAdapterError("Spanish measurement is missing its immutable template");
    const translation = parse(await readFile(template.sourcePath, "utf8"));
    if (!isRecord(translation)) throw permanentAdapterError("Spanish measurement template is invalid");
    document.language = "es";
    document.locale = typeof translation.locale === "string" ? translation.locale : "es";
    if (pieceId === "opening") {
      if (!isRecord(translation.editorial) || typeof translation.editorial.path !== "string") {
        throw permanentAdapterError("Spanish measurement template has no editorial");
      }
      document.editorial = `editions/${document.id}/translations/es/${translation.editorial.path}`;
    } else {
      const localized = Array.isArray(translation.articles)
        ? translation.articles.find((row) => isRecord(row) && row.id === pieceId)
        : undefined;
      if (!isRecord(localized) || typeof localized.manuscript !== "string") {
        throw permanentAdapterError(`Spanish measurement template has no article ${pieceId}`);
      }
      document.articles = [{
        ...sourceArticle,
        ...localized,
        manuscript: `editions/${document.id}/translations/es/${localized.manuscript}`,
      }];
    }
  }
  const derivedPath = join(inputRoot, "derived", `${base.artifactId}-${language}-${pieceId}-measurement.yaml`);
  await mkdir(dirname(derivedPath), { recursive: true, mode: 0o700 });
  await writeFile(derivedPath, JSON.stringify(document), { encoding: "utf8", mode: 0o600 });
  return inputs.map((input) => input === base ? { ...input, sourcePath: derivedPath } : input);
}

async function artifactHash(path: string): Promise<string> {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

type RenderProfileInput = RenderExecutionProfile["inputs"][number];

const currentAssemblyKinds = new Set([
  "article_manuscript",
  "editorial_manuscript",
  "selected_art",
  "translated_piece",
  "translation",
  "translation_bundle",
]);

/**
 * The immutable profile supplies target paths, while the assembly names the
 * current content revision. A profile may retain stable renderer assets, but
 * it must never silently carry an old manuscript, translation, or selected
 * art into a fresh assembly.
 */
async function deriveEffectiveRenderInputs(
  context: ExecutorContext,
  assembly: RenderAssemblyManifest,
  profile: RenderExecutionProfile,
): Promise<readonly RenderProfileInput[]> {
  if (context.artifacts.readArtifact === undefined) {
    throw permanentAdapterError("renderer executor requires artifact lineage access");
  }
  const current = new Set<ArtifactId>([
    ...assembly.content,
    ...assembly.translations,
    ...assembly.art,
    ...(assembly.printerProfileArtifactId === null ? [] : [assembly.printerProfileArtifactId]),
  ]);
  const effective = await Promise.all(profile.inputs.map(async (input) => {
    if (current.has(input.artifactId)) {
      return input;
    }
    const record = await context.artifacts.readArtifact!(input.artifactId);
    if (currentAssemblyKinds.has(record.artifact.kind)) {
      throw permanentAdapterError(
        `render profile retains stale ${record.artifact.kind} ${input.artifactId} outside the current assembly`,
      );
    }
    return input;
  }));
  const present = new Set(effective.map((input) => input.artifactId));
  const additions = await Promise.all([...current].filter((artifactId) => !present.has(artifactId)).map(async (artifactId) => {
    const record = await context.artifacts.readArtifact!(artifactId);
    const targetPath = typeof record.artifact.metadata.rendererTargetPath === "string"
      ? record.artifact.metadata.rendererTargetPath
      : undefined;
    if (targetPath === undefined) {
      throw permanentAdapterError(`current render artifact ${artifactId} has no rendererTargetPath metadata`);
    }
    return { artifactId, targetPath };
  }));
  return [...effective, ...additions];
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

const editionSpecMetadataSchema = z.object({
  inputRevision: z.object({ kind: z.literal("edition_spec") }).passthrough(),
  revisionPayloadPath: z.literal("edition.yaml"),
  rendererTargetPath: z.string().min(1),
}).passthrough();

const editionSpecDocumentSchema = z.object({
  id: z.string().regex(/^[a-z0-9][a-z0-9._-]*$/u),
}).passthrough();

async function resolveEditionPackageId(
  context: ExecutorContext,
  profile: RenderExecutionProfile,
  effectiveInputs: readonly RenderProfileInput[],
): Promise<string> {
  if (context.artifacts.readArtifact === undefined) {
    throw permanentAdapterError("renderer executor requires artifact lineage access");
  }
  const manifestInputs = effectiveInputs.filter((input) =>
    /^editions\/[^/]+\/edition\.yaml$/u.test(input.targetPath)
  );
  const staged = await Promise.all(manifestInputs.map(async (input) => ({
    input,
    record: await context.artifacts.readArtifact!(input.artifactId),
  })));
  const candidates = staged.filter(({ record }) =>
    record.artifact.kind === "edition_spec_revision_payload" &&
    editionSpecMetadataSchema.safeParse(record.artifact.metadata).success
  );
  if (candidates.length !== 1) {
    throw permanentAdapterError(
      `render profile must bind exactly one committed edition_spec edition.yaml, found ${candidates.length}`,
    );
  }
  const candidate = candidates[0]!;
  const metadata = editionSpecMetadataSchema.parse(candidate.record.artifact.metadata);
  if (
    metadata.rendererTargetPath !== candidate.input.targetPath ||
    candidate.record.artifact.mediaType !== "application/yaml"
  ) {
    throw permanentAdapterError(
      "edition_spec renderer target or media type does not match its immutable artifact metadata",
    );
  }
  let decoded: unknown;
  try {
    decoded = parse(Buffer.from(candidate.record.bytes).toString("utf8"));
  } catch (error) {
    throw permanentAdapterError(
      `committed edition_spec edition.yaml is invalid: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  const document = editionSpecDocumentSchema.safeParse(decoded);
  if (!document.success) {
    throw permanentAdapterError(
      `committed edition_spec edition.yaml has no valid package id: ${document.error.message}`,
    );
  }
  const editionPackageId = document.data.id;
  const expectedTarget = `editions/${editionPackageId}/edition.yaml`;
  if (candidate.input.targetPath !== expectedTarget) {
    throw permanentAdapterError(
      `edition_spec edition.yaml target must be ${expectedTarget}, got ${candidate.input.targetPath}`,
    );
  }
  if (
    profile.editionPackageId !== undefined &&
    profile.editionPackageId !== editionPackageId
  ) {
    throw permanentAdapterError(
      `render profile editionPackageId ${profile.editionPackageId} does not match committed edition_spec ${editionPackageId}`,
    );
  }
  return editionPackageId;
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
  effectiveInputs: readonly RenderProfileInput[],
  result: Awaited<ReturnType<RendererAdapter["render"]>>,
  editionPackageId: string,
): void {
  if (
    result.schemaVersion !== 1 ||
    result.rendererContractVersion !== RENDERER_CONTRACT_VERSION ||
    result.editionId !== editionPackageId
  ) {
    throw permanentAdapterError("renderer returned the wrong contract or edition identity");
  }
  requireExactSequence(
    effectiveInputs.map((input) => input.artifactId),
    result.inputArtifactIds,
    "renderer result",
  );
  requireExactSequence(
    assembly.configuredLanguages,
    result.layouts.map((layout) => layout.language),
    "renderer layouts",
  );
}
