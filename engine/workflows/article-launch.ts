import { readFile } from "node:fs/promises";

import type {
  ArticleExecutionId,
  ArtifactId,
  JsonObject,
  JsonValue,
  PromotionId,
  RevisionId,
  RunId,
} from "../contracts/index.ts";
import { newArticleExecutionId, newId } from "../contracts/ids.ts";
import {
  GitCliDurableGit,
  materializeWritePipelineInputs,
  type AuthenticatedWritePipelineInputs,
  resolveProfileBackedArticleInput,
  resolveWritePipeline,
  type InputRevisionRef,
} from "../durable/index.ts";
import { newRevisionId } from "../durable/revision-id.ts";
import { articleMaterialContextFromLoops } from "../article-production/materials.ts";
import { ArtifactLedger } from "../workflow-authority/artifact-ledger.ts";
import type { ArticleRuntimeStartArgs } from "./internal-types.ts";
import type { RendererIdentity } from "./renderer-identity.ts";
import { deterministicManuscriptRevisionId } from "./article-workflow.ts";

export type ArticleLaunchOptions = {
  readonly runId?: RunId;
  readonly articleExecutionId?: ArticleExecutionId;
  readonly expectedParentRevisionId?: RevisionId | null;
  readonly promotionId?: PromotionId;
  readonly revisionId?: RevisionId;
  readonly language?: string;
  /** The Loops root run identity. It differs from args.runId for children. */
  readonly loopsRunId?: string;
};

export type ArticleLaunchBuilderDependencies = {
  readonly repositoryRoot: string;
  readonly ledger: ArtifactLedger;
  readonly now: () => Date;
  readonly validateRuntimeResources: () => Promise<void>;
  readonly getWorkflowVersion: () => Promise<string>;
  readonly getRendererIdentity: () => Promise<RendererIdentity>;
};

export type BuiltArticleLaunch = {
  readonly args: ArticleRuntimeStartArgs;
  readonly workflowVersion: string;
  readonly articleExecutionId: ArticleExecutionId;
  readonly runId: RunId;
};

/**
 * Authenticate and materialize one immutable article launch. The exact same
 * builder is used by standalone roots and by future edition children; only
 * `loopsRunId` changes when the article is nested under an edition runtime.
 */
export async function buildAuthenticatedArticleLaunchArgs(
  dependencies: ArticleLaunchBuilderDependencies,
  pipelineRef: Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>,
  articleId: string,
  options: ArticleLaunchOptions = {},
): Promise<BuiltArticleLaunch> {
  const git = new GitCliDurableGit(dependencies.repositoryRoot);
  const resolved = await resolveWritePipeline(dependencies.repositoryRoot, pipelineRef, git);
  return await buildAuthenticatedArticleLaunchArgsFromMaterialized(
    dependencies,
    materializeWritePipelineInputs(resolved),
    articleId,
    options,
  );
}

/**
 * Build a child launch from an already authenticated pipeline projection.
 *
 * Edition roots call this after resolving and materializing their committed
 * write pipeline once.  It deliberately accepts only the materialized
 * projection, so a child cannot silently re-resolve Git or recapture sources
 * while the parent is being planned or replayed.
 */
export async function buildAuthenticatedArticleLaunchArgsFromMaterialized(
  dependencies: ArticleLaunchBuilderDependencies,
  materialized: AuthenticatedWritePipelineInputs,
  articleId: string,
  options: ArticleLaunchOptions = {},
): Promise<BuiltArticleLaunch> {
  await dependencies.validateRuntimeResources();
  const resolved = materialized.pipeline;
  const article = resolved.document.articles.find((candidate) => candidate.articleId === articleId);
  if (article === undefined) throw new Error(`write pipeline has no article ${articleId}`);
  const profile = await resolveProfileBackedArticleInput(materialized, article);
  const language = options.language ?? "en";
  if (language !== "en") throw new Error("profile-backed article launch currently requires the English source language");

  const runId = options.runId ?? newId<RunId>("run");
  const articleExecutionId = options.articleExecutionId ?? newArticleExecutionId();
  const rendererIdentity = await dependencies.getRendererIdentity();
  const seedId = `art-input-manuscript-${safeIdentity(runId)}` as ArtifactId;
  const measurementProfileArtifactId = `art-input-measurement-profile-${safeIdentity(runId)}` as ArtifactId;
  const entryArtifactId = `art-article-workflow-entry-${safeIdentity(runId)}` as ArtifactId;
  const productionProfileArtifactId = `art-resolved-production-profile-${safeIdentity(runId)}` as ArtifactId;
  const args: ArticleRuntimeStartArgs = {
    runId,
    articleExecutionId,
    rewriteOrdinal: 0,
    articleId,
    editionId: resolved.document.editionId,
    language,
    logicalItem: { kind: "article", editionId: resolved.document.editionId, logicalId: articleId, language },
    manuscriptArtifactId: seedId,
    measurementProfileArtifactId,
    expectedParentRevisionId: options.expectedParentRevisionId ?? article.parent?.revisionId ?? null,
    promotionId: options.promotionId ?? (`promotion-${safeIdentity(runId)}` as PromotionId),
    revisionId: options.revisionId ?? newRevisionId(dependencies.now()),
    entryArtifactId,
    productionProfileArtifactId,
    entry: profile.loopsInput,
    rendererIdentity,
    review: {
      materialContext: articleMaterialContextFromLoops(profile.loopsInput, { measurementInputArtifactIds: [seedId] }),
    },
  };

  for (const seed of materialized.artifacts) await importArtifactSeed(dependencies.ledger, seed);
  const sourceText = sourceTextFromMaterials(dependencies.ledger, materialized, article.sourceIds);
  dependencies.ledger.createArtifact({
    id: seedId,
    kind: "article_manuscript",
    schemaVersion: "article-manuscript/1",
    mediaType: "text/markdown",
    origin: "imported",
    payload: { kind: "text", text: sourceText },
    parents: profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => ({ artifactId: artifact.artifactId, relation: "input_binding" }))),
    metadata: {
      articleId,
      materialArtifactIds: profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId)) as unknown as JsonValue,
      revisionId: deterministicManuscriptRevisionId(profile.loopsInput.articleId, profile.loopsInput.inputBindings, sourceText, profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId))),
      inputBindings: profile.loopsInput.inputBindings as unknown as readonly JsonObject[],
    },
  });
  const workflowVersion = await dependencies.getWorkflowVersion();
  dependencies.ledger.createRun({
    runId,
    articleExecutionId,
    articleId,
    editionId: resolved.document.editionId,
    workflowVersion,
    loopsRunId: options.loopsRunId ?? runId,
    manuscriptArtifactId: seedId,
    args: args as unknown as JsonObject,
  });
  dependencies.ledger.createArtifact({
    id: measurementProfileArtifactId,
    kind: "article_measurement_profile",
    schemaVersion: "article-measurement-profile/1",
    mediaType: "application/json",
    origin: "machine",
    payload: {
      kind: "json",
      value: {
        schemaVersion: 1,
        rendererContractVersion: "magazine-renderer/1",
        editionId: resolved.document.editionId,
        primaryLanguage: language,
        publicationName: resolved.document.render.publicationName,
        renderer: resolved.document.render.renderer,
        articleId,
        manuscriptArtifactId: seedId,
        maximumReaderPages: article.maximumReaderPages,
        inputs: [{ artifactId: seedId, targetPath: `articles/${articleId}/manuscript.md` }],
        rendererIdentity,
      } as unknown as JsonObject,
    },
    parents: [{ artifactId: seedId, relation: "profile_manuscript" }],
    runId,
  });
  dependencies.ledger.createArtifact({
    id: entryArtifactId,
    kind: "article_workflow_entry",
    schemaVersion: "loops-article-entry-input/1",
    mediaType: "application/json",
    origin: "machine",
    payload: { kind: "json", value: profile.loopsInput as unknown as JsonObject },
    parents: profile.loopsInput.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => ({ artifactId: artifact.artifactId, relation: "entry_input" }))),
    metadata: { articleId, entrySchemaVersion: profile.loopsInput.schemaVersion },
    runId,
  });
  dependencies.ledger.createArtifact({
    id: productionProfileArtifactId,
    kind: "resolved_article_production_profile",
    schemaVersion: "resolved-article-production-profile/1",
    mediaType: "application/json",
    origin: "machine",
    payload: {
      kind: "json",
      value: {
        schemaVersion: "resolved-article-production-profile/1",
        entry: profile.loopsInput,
      } as unknown as JsonObject,
    },
    parents: profile.loopsInput.inputBindings.map((binding) => ({ artifactId: binding.artifactId, relation: "input_binding" })),
    metadata: {
      articleId,
      profileArtifactId: productionProfileArtifactId,
      resolvedProfileId: profile.productionProfile.profileId,
    },
    runId,
  });
  return Object.freeze({ args: deepFreeze(args), workflowVersion, articleExecutionId, runId });
}

async function importArtifactSeed(ledger: ArtifactLedger, seed: import("../contracts/index.ts").ArtifactSeed): Promise<void> {
  const payload = seed.payload.kind === "file"
    ? { kind: "bytes" as const, bytes: new Uint8Array(await readFile(seed.payload.path)) }
    : seed.payload.kind === "bytes"
      ? { kind: "bytes" as const, bytes: Buffer.from(seed.payload.dataBase64, "base64") }
      : seed.payload;
  ledger.createArtifact({
    id: seed.id,
    kind: seed.kind,
    schemaVersion: seed.schemaVersion,
    mediaType: seed.mediaType,
    origin: seed.origin,
    payload: payload as never,
    ...(seed.parents === undefined ? {} : { parents: seed.parents }),
    ...(seed.metadata === undefined ? {} : { metadata: seed.metadata }),
  });
}

function sourceTextFromMaterials(
  ledger: ArtifactLedger,
  materialized: ReturnType<typeof materializeWritePipelineInputs>,
  sourceIds: readonly string[],
): string {
  const wanted = new Set(sourceIds);
  const chunks: string[] = [];
  for (const input of materialized.materializedInputs) {
    if (input.ref.kind !== "source_extraction" || !wanted.has(input.ref.logicalId)) continue;
    for (const artifact of [...input.artifacts].sort((left, right) => left.path.localeCompare(right.path))) {
      const read = ledger.readArtifact(artifact.artifactId);
      let text: string;
      try {
        text = new TextDecoder("utf-8", { fatal: true }).decode(read.bytes);
      } catch (error) {
        throw new Error(`source extraction file ${artifact.path} is not UTF-8`, { cause: error });
      }
      chunks.push(`--- source ${input.ref.logicalId} ${artifact.path} sha256:${read.artifact.digest} ---\n${text}\n--- end source ${artifact.path} ---`);
    }
  }
  if (chunks.length === 0) throw new Error("profile-backed article has no source extraction payload");
  return chunks.join("\n\n");
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
