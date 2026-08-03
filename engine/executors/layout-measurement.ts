import { z } from "zod";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactParent,
  JsonObject,
  WorkAnswer,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import {
  RENDERER_CONTRACT_VERSION,
  type ArticleMeasurementProfile,
  type LanguageFitProfile,
  type LanguageLayout,
  type RenderManifest,
  type RendererAdapter,
} from "../renderer-adapter/index.ts";
import {
  AdapterWorkspaceOwner,
  permanentAdapterError,
  readJsonArtifact,
  requireExactSequence,
  requireSafeTargetPath,
  stageArtifact,
  writeAdapterRequest,
} from "./adapter-workspace.ts";
import { materializeReducedMeasurementEdition } from "./renderer.ts";
import type { Executor, ExecutorContext } from "./types.ts";

const inputSchema = z.object({
  artifactId: z.string().min(1),
  targetPath: z.string().min(1),
}).strict();

const commonProfileShape = {
  schemaVersion: z.literal(1),
  rendererContractVersion: z.literal(RENDERER_CONTRACT_VERSION),
  editionId: z.string().min(1),
  primaryLanguage: z.string().min(1),
  publicationName: z.string().min(1),
  renderer: z.enum(["reportlab", "weasyprint"]),
  design: z.string().min(1).optional(),
  inputs: z.array(inputSchema).min(1),
  metadata: z.record(z.string(), z.json()).optional(),
} as const;

const articleProfileSchema = z.object({
  ...commonProfileShape,
  articleId: z.string().min(1),
  manuscriptArtifactId: z.string().min(1),
  maximumReaderPages: z.number().int().positive().max(7),
}).strict();

const languageProfileSchema = z.object({
  ...commonProfileShape,
  language: z.string().min(1),
  translatedPieces: z.array(z.object({
    articleId: z.string().min(1),
    artifactId: z.string().min(1),
    maximumReaderPages: z.number().int().positive().max(7),
  }).strict()).min(1),
}).strict();

type MeasurementExecutorOptions = {
  readonly id?: string;
  readonly principalId?: string;
  readonly workDirectory: string;
};

abstract class RendererMeasurementExecutor implements Executor {
  abstract readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities = ["subprocess"] as const;
  protected readonly adapter: RendererAdapter;
  private readonly workspaces: AdapterWorkspaceOwner;

  protected constructor(
    adapter: RendererAdapter,
    workDirectory: string,
    principalId: string,
    displayName: string,
  ) {
    this.adapter = adapter;
    this.workspaces = new AdapterWorkspaceOwner(workDirectory);
    this.worker = {
      principalId,
      authority: "tool",
      capabilities: this.capabilities,
      displayName,
    };
  }

  abstract accepts(offer: WorkOfferView): boolean;
  abstract execute(context: ExecutorContext): Promise<WorkAnswer>;

  protected async renderMeasurement(
    context: ExecutorContext,
    profile: ArticleMeasurementProfile | LanguageFitProfile,
    operation: "measure_article" | "measure_edition",
    languages: readonly string[],
    articleId?: string,
  ): Promise<{
    readonly layouts: readonly LanguageLayout[];
    readonly inputArtifactIds: readonly ArtifactId[];
  }> {
    const workspace = await this.workspaces.create(
      context.claim.attemptId,
      `${operation}-${context.claim.attemptId}`,
    );
    const stagedInputs = await Promise.all(profile.inputs.map(async (input, index) => ({
      artifactId: input.artifactId,
      sourcePath: await stageArtifact(
        context.artifacts,
        input.artifactId,
        workspace.inputRoot,
        index,
      ),
      targetPath: input.targetPath,
    })));
    const measurementPieceId = typeof profile.metadata?.measurementPieceId === "string"
      ? profile.metadata.measurementPieceId
      : undefined;
    const inputs = measurementPieceId === undefined
      ? stagedInputs
      : await materializeReducedMeasurementEdition(
          stagedInputs,
          workspace.inputRoot,
          measurementPieceId,
          profile.primaryLanguage === "es" ? "es" : "en",
        );
    const manifest: RenderManifest = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      operation,
      editionId: profile.editionId,
      ...(articleId === undefined ? {} : { articleId }),
      primaryLanguage: profile.primaryLanguage,
      languages,
      publicationName: profile.publicationName,
      renderer: profile.renderer,
      artifactRoot: workspace.inputRoot,
      inputs,
      ...(profile.design === undefined ? {} : { design: profile.design }),
      metadata: {
        ...(profile.metadata ?? {}),
        measurementProfileArtifactId: context.offer.taskArtifactId,
        attemptId: context.claim.attemptId,
      },
    };
    await writeAdapterRequest(workspace.requestPath, manifest);
    const result = await this.adapter.render(
      workspace.requestPath,
      workspace.outputRoot,
      context.signal,
    );
    if (
      result.schemaVersion !== 1 ||
      result.rendererContractVersion !== RENDERER_CONTRACT_VERSION ||
      result.editionId !== profile.editionId
    ) {
      throw permanentAdapterError("renderer returned the wrong measurement identity");
    }
    if (result.files.length !== 0) {
      throw permanentAdapterError(`${operation} returned render files`);
    }
    requireExactSequence(
      profile.inputs.map((input) => input.artifactId),
      result.inputArtifactIds,
      `${operation} result`,
    );
    requireExactSequence(
      languages,
      result.layouts.map((layout) => layout.language),
      `${operation} layouts`,
    );
    return {
      layouts: result.layouts,
      inputArtifactIds: result.inputArtifactIds,
    };
  }

  async release(context: ExecutorContext): Promise<void> {
    await this.workspaces.release(context.claim.attemptId);
  }
}

export class ArticleMeasurementExecutor extends RendererMeasurementExecutor {
  readonly id: string;

  constructor(adapter: RendererAdapter, options: MeasurementExecutorOptions) {
    const id = options.id ?? "article-measurement";
    super(
      adapter,
      options.workDirectory,
      options.principalId ?? id,
      "Isolated article layout measurement",
    );
    this.id = id;
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "measure_article";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    const record = await requireProfileRecord(
      context,
      "article_measurement_profile",
    );
    const parsed = articleProfileSchema.safeParse(await readJsonArtifact(
      context.artifacts,
      context.offer.taskArtifactId,
      "article measurement profile",
    ));
    if (!parsed.success) {
      throw permanentAdapterError(
        `article measurement profile is invalid: ${parsed.error.message}`,
      );
    }
    const template = parsed.data as unknown as ArticleMeasurementProfile;
    validateProfileInputs(context, template.inputs, record.parents);
    const profile = await currentArticleProfile(context, template);
    if (
      context.offer.subjectArtifactId !== profile.manuscriptArtifactId ||
      !context.offer.inputArtifacts.includes(profile.manuscriptArtifactId)
    ) {
      throw permanentAdapterError(
        "article measurement profile does not bind the exact offered manuscript",
      );
    }
    if (template.manuscriptArtifactId !== "$current") {
      requireParent(
        record.parents,
        profile.manuscriptArtifactId,
        "measured_manuscript",
        "article measurement profile",
      );
    }
    if (!profile.inputs.some((input) => input.artifactId === profile.manuscriptArtifactId)) {
      throw permanentAdapterError("article measurement inputs omit the exact manuscript");
    }

    const measured = await this.renderMeasurement(
      context,
      profile,
      "measure_article",
      [profile.primaryLanguage],
      profile.articleId,
    );
    const layout = measured.layouts[0];
    const pageCount = layout?.articlePages[profile.articleId];
    if (layout === undefined || !Number.isSafeInteger(pageCount) || pageCount === undefined) {
      throw permanentAdapterError(
        `renderer did not return an unambiguous page row for article ${profile.articleId}`,
      );
    }
    const fits = pageCount <= profile.maximumReaderPages;
    const value: JsonObject = {
      schemaVersion: 1,
      articleId: profile.articleId,
      manuscriptArtifactId: profile.manuscriptArtifactId,
      fits,
      openerFits: true,
      pageCount,
      maximumReaderPages: profile.maximumReaderPages,
      layouts: measured.layouts as unknown as readonly JsonObject[],
      inputArtifactIds: measured.inputArtifactIds,
    };
    return {
      contractVersion: context.offer.contractVersion,
      result: {
        fits,
        openerFits: true,
        pageCount,
        articlePages: pageCount,
        status: fits ? "pass" : "blocking",
      },
      artifacts: [measurementArtifact(
        "article_measurement",
        context.offer.contractVersion,
        value,
        context.offer.inputArtifacts,
      )],
      metadata: {
        executorId: this.id,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
      },
    };
  }
}

export class LanguageFitExecutor extends RendererMeasurementExecutor {
  readonly id: string;

  constructor(adapter: RendererAdapter, options: MeasurementExecutorOptions) {
    const id = options.id ?? "language-fit";
    super(
      adapter,
      options.workDirectory,
      options.principalId ?? id,
      "Translated edition layout measurement",
    );
    this.id = id;
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "language_fit";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    const record = await requireProfileRecord(context, "language_fit_profile");
    const parsed = languageProfileSchema.safeParse(await readJsonArtifact(
      context.artifacts,
      context.offer.taskArtifactId,
      "language fit profile",
    ));
    if (!parsed.success) {
      throw permanentAdapterError(`language fit profile is invalid: ${parsed.error.message}`);
    }
    const template = parsed.data as unknown as LanguageFitProfile;
    const profile = await currentLanguageProfile(context, template);
    if (profile.primaryLanguage !== profile.language) {
      throw permanentAdapterError("language fit profile primaryLanguage must equal language");
    }
    validateProfileInputs(context, template.inputs, record.parents);
    requireUnique(
      profile.translatedPieces.map((piece) => piece.articleId),
      "language fit article IDs",
    );
    requireUnique(
      profile.translatedPieces.map((piece) => piece.artifactId),
      "language fit translation artifacts",
    );
    for (const piece of profile.translatedPieces) {
      if (
        !context.offer.inputArtifacts.includes(piece.artifactId) ||
        !profile.inputs.some((input) => input.artifactId === piece.artifactId)
      ) {
        throw permanentAdapterError(
          `language fit profile does not bind translated piece ${piece.articleId}`,
        );
      }
      if (template.translatedPieces.some((candidate) => candidate.artifactId === "$current")) {
        continue;
      }
      requireParent(record.parents, piece.artifactId, "translated_piece", "language fit profile");
    }

    const measured = await this.renderMeasurement(
      context,
      profile,
      "measure_edition",
      [profile.language],
    );
    const layout = measured.layouts[0];
    if (layout === undefined) {
      throw permanentAdapterError(`renderer omitted layout for ${profile.language}`);
    }
    const pieces = profile.translatedPieces.map((piece) => {
      const pageCount = layout.articlePages[piece.articleId];
      if (!Number.isSafeInteger(pageCount) || pageCount === undefined) {
        throw permanentAdapterError(
          `renderer did not return an unambiguous page row for translated piece ${piece.articleId}`,
        );
      }
      return {
        articleId: piece.articleId,
        artifactId: piece.artifactId,
        pageCount,
        maximumReaderPages: piece.maximumReaderPages,
        fits: pageCount <= piece.maximumReaderPages,
      };
    });
    const fits = pieces.every((piece) => piece.fits);
    const articlePages = pieces.reduce((total, piece) => total + piece.pageCount, 0);
    const value: JsonObject = {
      schemaVersion: 1,
      language: profile.language,
      fits,
      pageCount: layout.totalPages,
      articlePages,
      pieces,
      layouts: measured.layouts as unknown as readonly JsonObject[],
      inputArtifactIds: measured.inputArtifactIds,
    };
    return {
      contractVersion: context.offer.contractVersion,
      result: {
        fits,
        ...(fits ? {} : { decision: "revise" }),
        pageCount: layout.totalPages,
        articlePages,
      },
      artifacts: [measurementArtifact(
        "language_measurement",
        context.offer.contractVersion,
        value,
        context.offer.inputArtifacts,
      )],
      metadata: {
        executorId: this.id,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
      },
    };
  }
}

async function requireProfileRecord(
  context: ExecutorContext,
  expectedKind: string,
) {
  if (context.artifacts.readArtifact === undefined) {
    throw permanentAdapterError("layout measurement requires artifact lineage access");
  }
  const record = await context.artifacts.readArtifact(context.offer.taskArtifactId);
  if (record.artifact.kind !== expectedKind) {
    throw permanentAdapterError(
      `layout measurement task must be ${expectedKind}, got ${record.artifact.kind}`,
    );
  }
  return record.artifact;
}

function validateProfileInputs(
  context: ExecutorContext,
  inputs: ArticleMeasurementProfile["inputs"],
  parents: readonly ArtifactParent[],
): void {
  requireUnique(inputs.map((input) => input.artifactId), "measurement input artifacts");
  requireUnique(inputs.map((input) => input.targetPath), "measurement target paths");
  for (const [index, input] of inputs.entries()) {
    requireSafeTargetPath(input.targetPath, `measurement inputs[${index}].targetPath`);
    if (!context.offer.inputArtifacts.includes(input.artifactId)) {
      throw permanentAdapterError(
        `measurement profile input ${input.artifactId} was not offered to this attempt`,
      );
    }
    if (!parents.some((parent) => parent.artifactId === input.artifactId)) {
      throw permanentAdapterError(
        `measurement profile input ${input.artifactId} is absent from profile lineage`,
      );
    }
  }
}

function requireParent(
  parents: readonly ArtifactParent[],
  artifactId: ArtifactId,
  relation: string,
  label: string,
): void {
  if (!parents.some((parent) =>
    parent.artifactId === artifactId && parent.relation === relation
  )) {
    throw permanentAdapterError(`${label} has no ${relation} edge to ${artifactId}`);
  }
}

async function currentArticleProfile(
  context: ExecutorContext,
  template: ArticleMeasurementProfile,
): Promise<ArticleMeasurementProfile> {
  if (template.manuscriptArtifactId !== "$current") return template;
  const manuscriptArtifactId = context.offer.subjectArtifactId;
  if (manuscriptArtifactId === undefined || context.artifacts.readArtifact === undefined) {
    throw permanentAdapterError("dynamic article profile requires the current manuscript subject");
  }
  const record = await context.artifacts.readArtifact(manuscriptArtifactId);
  const targetPath = record.artifact.metadata.rendererTargetPath;
  if (typeof targetPath !== "string") {
    throw permanentAdapterError("current manuscript has no rendererTargetPath metadata");
  }
  return {
    ...template,
    manuscriptArtifactId,
    inputs: [...template.inputs, { artifactId: manuscriptArtifactId, targetPath }],
  };
}

async function currentLanguageProfile(
  context: ExecutorContext,
  template: LanguageFitProfile,
): Promise<LanguageFitProfile> {
  if (!template.translatedPieces.some((piece) => piece.artifactId === "$current")) return template;
  const artifactId = context.offer.subjectArtifactId;
  if (artifactId === undefined || context.artifacts.readArtifact === undefined) {
    throw permanentAdapterError("dynamic language profile requires the current translated piece subject");
  }
  const record = await context.artifacts.readArtifact(artifactId);
  const targetPath = record.artifact.metadata.rendererTargetPath;
  if (typeof targetPath !== "string") {
    throw permanentAdapterError("current translated piece has no rendererTargetPath metadata");
  }
  const offeredRecords = await Promise.all(context.offer.inputArtifacts
    .filter((candidate) => candidate !== artifactId)
    .map(async (candidate) => ({ artifactId: candidate, record: await context.artifacts.readArtifact!(candidate) })));
  const english = offeredRecords.filter(({ record }) =>
    record.artifact.kind === "article_manuscript" || record.artifact.kind === "editorial_manuscript"
  );
  if (english.length !== 1) {
    throw permanentAdapterError("dynamic language profile requires exactly one current English manuscript");
  }
  const englishTarget = english[0]!.record.artifact.metadata.rendererTargetPath;
  if (typeof englishTarget !== "string") {
    throw permanentAdapterError("current English manuscript has no rendererTargetPath metadata");
  }
  return {
    ...template,
    translatedPieces: template.translatedPieces.map((piece) => piece.artifactId === "$current"
      ? { ...piece, artifactId, articleId: piece.articleId === "$current" ? artifactId : piece.articleId }
      : piece),
    inputs: [...template.inputs, { artifactId, targetPath }, { artifactId: english[0]!.artifactId, targetPath: englishTarget }],
  };
}

function requireUnique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) {
    throw permanentAdapterError(`${label} must be unique`);
  }
}

function measurementArtifact(
  kind: "article_measurement" | "language_measurement",
  schemaVersion: string,
  value: JsonObject,
  parents: readonly ArtifactId[],
): AnswerArtifact {
  return {
    kind,
    schemaVersion,
    mediaType: "application/json",
    payload: { kind: "json", value },
    parents: [...new Set(parents)].map((artifactId) => ({
      artifactId,
      relation: "measured_input",
    })),
  };
}
