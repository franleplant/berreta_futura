import { z } from "zod";

import type { ArtifactId, JsonObject } from "../contracts/index.ts";
import type { WorkflowDurableContext } from "../workflows/internal-types.ts";
import {
  AdapterWorkspaceOwner,
  permanentAdapterError,
  requireExactSequence,
  requireSafeTargetPath,
  stageArtifact,
  writeAdapterRequest,
} from "../executors/adapter-workspace.ts";
import type { RendererAdapter, ArticleMeasurementProfile, RenderManifest } from "./protocol.ts";
import { RENDERER_CONTRACT_VERSION } from "./protocol.ts";
import { assertRendererIdentity, type RendererIdentity } from "../workflows/renderer-identity.ts";

export interface ArticleMeasurementArtifactReader {
  readBytes(artifactId: ArtifactId): Promise<Uint8Array>;
  readText(artifactId: ArtifactId): Promise<string>;
}

export type ArticleMeasurementResult = {
  readonly schemaVersion: "article-measurement/1";
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly pageCount: number;
  readonly maximumReaderPages: number;
  readonly fits: boolean;
  readonly openerFits: boolean;
  readonly layouts: readonly JsonObject[];
  readonly inputArtifactIds: readonly ArtifactId[];
};

const profileSchema = z.object({
  schemaVersion: z.literal(1),
  rendererContractVersion: z.literal(RENDERER_CONTRACT_VERSION),
  editionId: z.string().min(1),
  primaryLanguage: z.string().min(1),
  publicationName: z.string().min(1),
  renderer: z.enum(["reportlab", "weasyprint"]),
  design: z.string().min(1).optional(),
  inputs: z.array(z.object({ artifactId: z.string().min(1), targetPath: z.string().min(1) }).strict()).min(1),
  metadata: z.record(z.string(), z.json()).optional(),
  articleId: z.string().min(1),
  manuscriptArtifactId: z.string().min(1),
  maximumReaderPages: z.number().int().positive().max(7),
  rendererIdentity: z.record(z.string(), z.json()).optional(),
}).strict();

/**
 * Shared production measurement seam. It is the same renderer protocol used
 * by the worker executor, so workflow measurement cannot silently fall back
 * to a character-count estimate.
 */
export async function measureArticle(input: {
  readonly adapter: RendererAdapter;
  readonly artifacts: ArticleMeasurementArtifactReader;
  readonly workDirectory: string;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly rendererIdentity: RendererIdentity;
  readonly durableContext?: WorkflowDurableContext;
  readonly signal?: AbortSignal;
}): Promise<ArticleMeasurementResult> {
  const parsed = profileSchema.safeParse(JSON.parse(await input.artifacts.readText(input.measurementProfileArtifactId)));
  if (!parsed.success) {
    throw permanentAdapterError(`article measurement profile is invalid: ${parsed.error.message}`);
  }
  const profile = parsed.data as unknown as ArticleMeasurementProfile;
  if (profile.articleId !== input.articleId || profile.manuscriptArtifactId !== input.manuscriptArtifactId) {
    throw permanentAdapterError("article measurement profile does not bind the exact manuscript");
  }
  if (profile.rendererIdentity === undefined) {
    throw permanentAdapterError("article measurement profile does not bind the renderer identity");
  }
  try {
    assertRendererIdentity(input.rendererIdentity, profile.rendererIdentity, "article measurement profile identity");
  } catch (error) {
    throw permanentAdapterError(error instanceof Error ? error.message : "article measurement profile identity mismatch");
  }
  const manuscriptIncluded = profile.inputs.some((candidate) => candidate.artifactId === input.manuscriptArtifactId);
  if (!manuscriptIncluded) throw permanentAdapterError("article measurement profile omits the exact manuscript");
  const inputIds = profile.inputs.map((candidate) => candidate.artifactId);
  if (new Set(inputIds).size !== inputIds.length) throw permanentAdapterError("article measurement inputs must be unique");
  for (const [index, candidate] of profile.inputs.entries()) {
    requireSafeTargetPath(candidate.targetPath, `article measurement input ${index}`);
  }

  const attemptId = input.durableContext !== undefined && (input.durableContext.kind === "agent" || input.durableContext.kind === "step")
    ? input.durableContext.attemptId
    : `measurement-${input.measurementProfileArtifactId}`;
  const workspaces = new AdapterWorkspaceOwner(input.workDirectory);
  const workspace = await workspaces.create(attemptId, `measure-article-${safeIdentity(input.articleId)}`);
  try {
    const stagedInputs = await Promise.all(profile.inputs.map(async (candidate, index) => ({
      artifactId: candidate.artifactId,
      sourcePath: await stageArtifact(input.artifacts, candidate.artifactId, workspace.inputRoot, index),
      targetPath: candidate.targetPath,
    })));
    const manifest: RenderManifest = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      operation: "measure_article",
      editionId: profile.editionId,
      articleId: profile.articleId,
      primaryLanguage: profile.primaryLanguage,
      languages: [profile.primaryLanguage],
      publicationName: profile.publicationName,
      renderer: profile.renderer,
      artifactRoot: workspace.inputRoot,
      ...(profile.design === undefined ? {} : { design: profile.design }),
      inputs: stagedInputs,
      metadata: {
        ...(profile.metadata ?? {}),
        rendererIdentity: input.rendererIdentity as unknown as JsonObject,
        measurementProfileArtifactId: input.measurementProfileArtifactId,
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext as unknown as JsonObject }),
      },
    };
    await writeAdapterRequest(workspace.requestPath, manifest);
    const result = await input.adapter.render(
      workspace.requestPath,
      workspace.outputRoot,
      input.signal ?? new AbortController().signal,
    );
    if (
      result.schemaVersion !== 1 ||
      result.rendererContractVersion !== RENDERER_CONTRACT_VERSION ||
      result.editionId !== profile.editionId ||
      result.files.length !== 0
    ) {
      throw permanentAdapterError("renderer returned the wrong article measurement identity");
    }
    requireExactSequence(inputIds, result.inputArtifactIds, "article measurement result");
    const layout = result.layouts.find((candidate) => candidate.language === profile.primaryLanguage);
    const pageCount = layout?.articlePages[profile.articleId];
    const openerFits = layout?.articleOpenerFits?.[profile.articleId];
    if (layout === undefined || !Number.isSafeInteger(pageCount) || pageCount === undefined) {
      throw permanentAdapterError(`renderer omitted an unambiguous page row for ${profile.articleId}`);
    }
    if (openerFits !== true) {
      throw permanentAdapterError(`renderer omitted or rejected opener fit for ${profile.articleId}`);
    }
    return {
      schemaVersion: "article-measurement/1",
      articleId: profile.articleId,
      manuscriptArtifactId: profile.manuscriptArtifactId,
      pageCount,
      maximumReaderPages: profile.maximumReaderPages,
      fits: pageCount <= profile.maximumReaderPages,
      openerFits,
      layouts: result.layouts as unknown as readonly JsonObject[],
      inputArtifactIds: result.inputArtifactIds,
    };
  } finally {
    await workspaces.release(attemptId);
  }
}

function safeIdentity(value: string): string {
  return value.replace(/[^A-Za-z0-9_.-]/gu, "_").slice(0, 80);
}
