import { createHash } from "node:crypto";
import { resolve } from "node:path";

import type {
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  ModelPolicy,
  RevisionId,
  RunId,
  RunView,
} from "./contracts/index.ts";
import {
  GitCliDurableGit,
  materializeWritePipelineInputs,
  resolveProfileBackedArticleInput,
  resolveDurableRevision,
  resolveWritePipeline,
  type DurableGit,
  type InputRevisionRef,
  type ResolvedInputRevision,
  type ResolvedWritePipeline,
} from "./durable/index.ts";
import { EditionRunLayout } from "./edition-run-layout.ts";

type WritePipelineRef = Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>;

export type WriteProductionPlan = {
  readonly schemaVersion: "edition-write-production-plan/1";
  readonly pipeline: ResolvedWritePipeline;
  readonly spec: EditionRootRunSpec;
  readonly imageGenerationAllowed: false;
};

export type EditionProductionRunnerOptions = {
  readonly editionKey: string;
  readonly repositoryRoot: string;
  readonly outputRoot: string;
  readonly durableGit?: DurableGit;
};

export type StartedWriteProduction = {
  readonly plan: WriteProductionPlan;
  readonly runId: RunId;
  readonly runName: string;
  readonly internalDirectory: string;
  readonly publicDirectory: string;
  readonly view: RunView;
};

/** Public RunEngine-backed entry point for a true write-production run. */
export class EditionProductionRunner {
  private readonly repositoryRoot: string;
  private readonly git: DurableGit;
  private readonly layout: EditionRunLayout;

  constructor(options: EditionProductionRunnerOptions) {
    this.repositoryRoot = resolve(options.repositoryRoot);
    this.git = options.durableGit ?? new GitCliDurableGit(this.repositoryRoot);
    this.layout = new EditionRunLayout({
      editionKey: options.editionKey,
      repositoryRoot: this.repositoryRoot,
      outputRoot: options.outputRoot,
      durableGit: this.git,
    });
  }

  async plan(pipelineRef: WritePipelineRef): Promise<WriteProductionPlan> {
    return await prepareWriteProduction(this.repositoryRoot, pipelineRef, this.git);
  }

  /** Allocates a resumable run and advances only deterministic prepared-source work. */
  async produce(pipelineRef: WritePipelineRef): Promise<StartedWriteProduction> {
    const plan = await this.plan(pipelineRef);
    const opened = await this.layout.allocate(plan.spec, {
      idempotencyKey: `write-pipeline:${pipelineRef.revisionId}`,
    });
    try {
      let view = await opened.engine.inspect(opened.runId);
      for (let index = 0; index < 32; index += 1) {
        await opened.engine.advance(opened.runId);
        const next = await opened.engine.inspect(opened.runId);
        if (next.headSequence === view.headSequence) break;
        view = next;
      }
      return {
        plan,
        runId: opened.runId,
        runName: opened.runName,
        internalDirectory: opened.internalDirectory,
        publicDirectory: opened.publicDirectory,
        view,
      };
    } finally {
      opened.close();
    }
  }
}

/**
 * Converts one committed WritePipeline InputRevision into a fresh edition run.
 * It never reads a prior manuscript or translation. Existing selected art is
 * imported by its DurableRevision identity only.
 */
export async function prepareWriteProduction(
  repositoryRoot: string,
  pipelineRef: WritePipelineRef,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<WriteProductionPlan> {
  const root = resolve(repositoryRoot);
  const authenticated = await resolveWritePipeline(root, pipelineRef, git);
  const materialized = materializeWritePipelineInputs(authenticated);
  const pipeline = materialized.pipeline;
  const artifacts: ArtifactSeed[] = [...materialized.artifacts];
  const inputArtifact = materialized.inputArtifact;
  // Authenticate profile-backed articles through the same resolver that the
  // future Loops entry point will use. This legacy builder still stops at its
  // explicit XState authority boundary below; it must not silently construct a
  // partial profile or invent artifact IDs first.
  const profileBackedArticles = new Map(
    await Promise.all(pipeline.document.articles
      .filter((article) => article.productionProfileRevision !== undefined)
      .map(async (article) => [
        article.articleId,
        await resolveProfileBackedArticleInput(materialized, article),
      ] as const)),
  );
  const pipelineArtifact = artifactId(`write-pipeline:${pipelineRef.revisionId}`);
  artifacts.push({
    id: pipelineArtifact,
    kind: "write_pipeline_revision",
    schemaVersion: "write-pipeline/1",
    mediaType: "application/yaml",
    origin: "imported",
    payload: { kind: "file", path: pipeline.revision.payloadPaths["production.yaml"]! },
    metadata: { inputRevision: pipelineRef, revisionPayloadPath: "production.yaml" },
  });

  const sourceExtraction = new Map<string, ArtifactId>();
  const staticRendererByTarget = new Map<string, ArtifactId>();
  const bindRendererInput = (artifactId: ArtifactId, targetPath: string): void => {
    const existing = staticRendererByTarget.get(targetPath);
    if (existing !== undefined && existing !== artifactId) {
      throw new Error(`write pipeline binds conflicting renderer inputs at ${targetPath}`);
    }
    staticRendererByTarget.set(targetPath, artifactId);
  };
  for (const binding of pipeline.document.rendererInputs) {
    bindRendererInput(
      inputArtifact(binding.input, binding.payloadPath),
      rendererStaticTarget(binding.input, binding.payloadPath, binding.rendererTargetPath),
    );
  }
  const editionSpec = pipeline.inputs.find((input) => sameInputRevision(input.ref, pipeline.document.editionSpec));
  if (editionSpec === undefined) throw new Error("write pipeline did not resolve its edition spec");
  for (const path of Object.keys(editionSpec.payloadPaths).sort()) {
    bindRendererInput(
      inputArtifact(pipeline.document.editionSpec, path),
      rendererStaticTarget(pipeline.document.editionSpec, path, undefined),
    );
  }
  const sources = pipeline.document.sources.map((source) => {
    const capture = pipeline.inputs.find((input) => sameInputRevision(input.ref, source.capture));
    if (capture === undefined) throw new Error(`write pipeline did not resolve capture ${source.sourceId}`);
    const extractionRevision = pipeline.inputs.find((input) => sameInputRevision(input.ref, source.extraction));
    if (extractionRevision === undefined) throw new Error(`write pipeline did not resolve extraction ${source.sourceId}`);
    const capturePayloads = Object.keys(capture.payloadPaths).sort().map((path) => inputArtifact(source.capture, path));
    const recordPayload = inputArtifact(source.capture, "raw/record.yaml");
    const extractionPayload = inputArtifact(source.extraction, "extracted.md");
    const rawBundle = artifactId(`prepared-source-raw-bundle:${source.sourceId}`);
    const rawEvidence = artifactId(`prepared-source-raw-evidence:${source.sourceId}`);
    const extraction = artifactId(`prepared-source-extraction:${source.sourceId}`);
    const metadata = artifactId(`prepared-source-metadata:${source.sourceId}`);
    const lead = artifactId(`prepared-source-lead:${source.sourceId}`);
    sourceExtraction.set(source.sourceId, extraction);
    for (const path of Object.keys(capture.payloadPaths).sort()) {
      bindRendererInput(
        inputArtifact(source.capture, path),
        captureRendererTarget(source.sourceId, path),
      );
    }
    bindRendererInput(
      extractionPayload,
      `library/sources/${source.sourceId}/extracted.md`,
    );
    artifacts.push({
      id: rawBundle,
      kind: "raw_source_bundle",
      schemaVersion: "prepared-source/1",
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: {
        sourceId: source.sourceId,
        captureInputRevision: source.capture,
        capturePayloadArtifactIds: capturePayloads,
      } },
      parents: [
        { artifactId: lead, relation: "captured_from_lead" },
        { artifactId: pipelineArtifact, relation: "write_pipeline" },
        ...capturePayloads.map((artifactId) => ({ artifactId, relation: "captured_payload" })),
      ],
    }, {
      id: rawEvidence,
      kind: "raw_evidence",
      schemaVersion: "prepared-source/1",
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: {
        sourceId: source.sourceId,
        captureInputRevision: source.capture,
        capturePayloadArtifactIds: capturePayloads,
      } },
      parents: [
        { artifactId: rawBundle, relation: "bundle_content" },
        ...capturePayloads.map((artifactId) => ({ artifactId, relation: "raw_capture_payload" })),
      ],
    }, {
      id: metadata,
      kind: "source_metadata",
      schemaVersion: "prepared-source/1",
      mediaType: "application/yaml",
      origin: "imported",
      payload: { kind: "file", path: capture.payloadPaths["raw/record.yaml"]! },
      parents: [
        { artifactId: rawBundle, relation: "describes_bundle" },
        { artifactId: recordPayload, relation: "capture_record" },
      ],
    }, {
      id: extraction,
      kind: "source_extraction",
      schemaVersion: "prepared-source/1",
      mediaType: "text/markdown",
      origin: "imported",
      payload: { kind: "file", path: extractionRevision.payloadPaths["extracted.md"]! },
      parents: [
        { artifactId: rawBundle, relation: "extracted_from" },
        { artifactId: extractionPayload, relation: "input_revision_payload" },
      ],
    }, {
      id: lead,
      kind: "source_lead",
      schemaVersion: "prepared-source/1",
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: { sourceId: source.sourceId, extractionArtifactId: extraction } },
      parents: [
        { artifactId: pipelineArtifact, relation: "write_pipeline" },
        { artifactId: extraction, relation: "prepared_extraction" },
      ],
    });
    return {
      sourceId: source.sourceId,
      leadArtifact: lead,
      rawBundleArtifact: rawBundle,
      rawEvidenceArtifacts: [rawEvidence],
      extractionArtifact: extraction,
      metadataArtifact: metadata,
    };
  });
  const staticRendererInputs = [...staticRendererByTarget.entries()]
    .map(([targetPath, artifactId]) => ({ artifactId, targetPath }))
    .sort((left, right) => left.targetPath.localeCompare(right.targetPath));
  const staticRendererArtifactIds = staticRendererInputs.map((input) => input.artifactId);
  const staticRendererParents = staticRendererArtifactIds.map((artifactId) => ({
    artifactId,
    relation: "layout_input",
  }));
  const policy = (ref: InputRevisionRef): ArtifactId => inputArtifact(ref, "policy.md");
  const prompt = (ref: InputRevisionRef): ArtifactId => inputArtifact(ref, "prompt.md");
  const articleArtifacts = pipeline.document.articles.map((article) => {
    if (article.productionProfileRevision !== undefined) {
      if (!profileBackedArticles.has(article.articleId)) {
        throw new Error(`article ${article.articleId} profile was not authenticated`);
      }
      throw new Error(`article ${article.articleId} requires the Loops profile-backed launch; the legacy edition builder cannot start it`);
    }
    if (article.writerPrompt === undefined || article.judgePrompts === undefined || article.inputRevisions === undefined || article.maxIterations === undefined) {
      throw new Error(`article ${article.articleId} has incomplete legacy writer inputs`);
    }
    const brief = artifactId(`article-brief:${article.articleId}`);
    const model = artifactId(`article-model-policy:${article.articleId}`);
    const measurementProfile = artifactId(`article-measurement-profile:${article.articleId}`);
    const sourceArtifacts = article.sourceIds.map((sourceId) => sourceExtraction.get(sourceId)!);
    artifacts.push({
      id: brief, kind: "article_brief", schemaVersion: "write-brief/1", mediaType: "text/markdown", origin: "imported",
      payload: { kind: "text", text: article.brief },
      parents: [{ artifactId: pipelineArtifact, relation: "write_pipeline" }, ...sourceArtifacts.map((artifactId) => ({ artifactId, relation: "assigned_extraction" }))],
    }, {
      id: model, kind: "model_policy", schemaVersion: "model-policy/1", mediaType: "application/json", origin: "imported",
      payload: { kind: "json", value: article.modelPolicy }, parents: [{ artifactId: pipelineArtifact, relation: "write_pipeline" }],
    }, {
      id: measurementProfile, kind: "article_measurement_profile", schemaVersion: "article-measurement-profile/1", mediaType: "application/json", origin: "imported",
      payload: { kind: "json", value: {
        schemaVersion: 1, rendererContractVersion: "magazine-renderer/1", editionId: "004-the-systems-around-the-model",
        primaryLanguage: "en", publicationName: pipeline.document.render.publicationName, renderer: pipeline.document.render.renderer,
        articleId: article.articleId, manuscriptArtifactId: "$current", maximumReaderPages: article.maximumReaderPages,
        inputs: staticRendererInputs,
        metadata: { dynamicCurrentArtifact: true, measurementPieceId: article.articleId },
      } }, parents: [...staticRendererParents, { artifactId: pipelineArtifact, relation: "write_pipeline" }],
    });
    const writingRules = article.inputRevisions.find((ref) => ref.kind === "policy" && ref.logicalId === "writing-rules");
    if (writingRules === undefined) throw new Error(`article ${article.articleId} has no writing-rules policy`);
    return {
      articleId: article.articleId,
      contentMode: article.contentMode,
      attribution: { kind: "source_author" as const, byline: article.byline, sourceAuthors: article.sourceAuthors, sourceIds: article.sourceIds },
      editionContext: pipelineArtifact,
      articleBrief: brief,
      sourceIds: article.sourceIds,
      writerPrompt: prompt(article.writerPrompt),
      judgePrompts: Object.fromEntries(Object.entries(article.judgePrompts).map(([lens, ref]) => [lens, prompt(ref)])),
      writingRules: policy(writingRules),
      measurementProfileArtifact: measurementProfile,
      measurementInputArtifacts: staticRendererArtifactIds,
      inputRevisions: article.inputRevisions,
      ...(article.parent === null ? {} : { durableParentRevisionId: article.parent.revisionId }),
      policy: {
        maxIterations: article.maxIterations,
        maximumReaderPages: article.maximumReaderPages,
        teaching: "not_applicable" as const,
        enabledLenses: Object.keys(article.judgePrompts) as ("worth" | "mechanics" | "evidence" | "shape" | "teaching" | "craft")[],
        blockingLenses: ["evidence"] as const,
      },
      modelPolicy: article.modelPolicy,
    };
  });
  const editorialBrief = artifactId("editorial-brief:opening");
  const editorialModel = artifactId("editorial-model-policy:opening");
  artifacts.push({
    id: editorialBrief, kind: "editorial_brief", schemaVersion: "write-brief/1", mediaType: "text/markdown", origin: "imported",
    payload: { kind: "text", text: pipeline.document.editorial.brief },
    parents: [{ artifactId: pipelineArtifact, relation: "write_pipeline" }, ...articleArtifacts.map((article) => ({ artifactId: article.articleBrief, relation: "article_brief" }))],
  }, {
    id: editorialModel, kind: "model_policy", schemaVersion: "model-policy/1", mediaType: "application/json", origin: "imported",
    payload: { kind: "json", value: pipeline.document.editorial.modelPolicy }, parents: [{ artifactId: pipelineArtifact, relation: "write_pipeline" }],
  });
  const editorialRules = pipeline.document.editorial.inputRevisions.find((ref) => ref.kind === "policy" && ref.logicalId === "writing-rules");
  if (editorialRules === undefined) throw new Error("editorial has no writing-rules policy");
  const images = await Promise.all(pipeline.document.images.map(async (ref) => await resolveDurableRevision(root, ref, git)));
  for (const image of images) {
    if (image.ref.kind !== "image") throw new Error("write pipeline image resolution returned a non-image revision");
    const path = image.payloadPaths["image.png"];
    if (path === undefined) throw new Error(`image ${image.ref.logicalId} has no image.png payload`);
    artifacts.push({
      id: artifactId(`selected-image:${image.ref.logicalId}:${image.ref.revisionId}`),
      kind: "selected_image_revision_payload", schemaVersion: "durable-image/1", mediaType: "image/png", origin: "imported",
      payload: { kind: "file", path }, metadata: {
        durableRevision: image.ref,
        rendererTargetPath: selectedImageTarget(image.ref.logicalId),
      },
    });
  }
  const profile = artifactId("edition4-write-render-profile");
  artifacts.push({
    id: profile, kind: "render_profile_template", schemaVersion: "render-profile-template/1", mediaType: "application/json", origin: "imported",
    payload: { kind: "json", value: { schemaVersion: 1, rendererContractVersion: "magazine-renderer/1", primaryLanguage: pipeline.document.render.primaryLanguage, publicationName: pipeline.document.render.publicationName, renderer: pipeline.document.render.renderer, inputs: staticRendererInputs, metadata: { writePipeline: pipelineRef, dynamicCurrentArtifacts: true } } },
    parents: [{ artifactId: pipelineArtifact, relation: "write_pipeline" }, ...staticRendererParents],
  });
  const release = artifactId("unreleased-publication-placeholder");
  artifacts.push({ id: release, kind: "publication_placeholder", schemaVersion: "write-production/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { unreleased: true } }, parents: [{ artifactId: pipelineArtifact, relation: "write_pipeline" }] });
  const defaultModel: ModelPolicy = pipeline.document.articles[0]!.modelPolicy;
  const spec: EditionRootRunSpec = {
    schemaVersion: 1, kind: "edition", artifacts, metadata: { writePipeline: pipelineRef, imageGenerationAllowed: false },
    edition: {
      editionId: pipeline.document.editionId, execution: { kind: "produce" }, editionBrief: pipelineArtifact,
      planningArtifact: pipelineArtifact, sourceAssignmentPolicy: "exactly_once", sources, articles: articleArtifacts,
      editorial: {
        editorialId: pipeline.document.editorial.editorialId,
        briefArtifact: editorialBrief,
        writingRules: policy(editorialRules),
        inputRevisions: pipeline.document.editorial.inputRevisions,
        ...(pipeline.document.editorial.parent === null ? {} : { durableParentRevisionId: pipeline.document.editorial.parent.revisionId }),
        modelPolicy: pipeline.document.editorial.modelPolicy,
      },
      translations: pipeline.document.translations.flatMap((translation) => [
        ...pipeline.document.articles.map((article) => ({
          ...(artifacts.push({
            id: artifactId(`language-fit-profile:${translation.language}:article:${article.articleId}`),
            kind: "language_fit_profile", schemaVersion: "language-fit-profile/1", mediaType: "application/json", origin: "imported",
            payload: { kind: "json", value: {
              schemaVersion: 1, rendererContractVersion: "magazine-renderer/1", editionId: "004-the-systems-around-the-model",
              primaryLanguage: translation.language, publicationName: pipeline.document.render.publicationName, renderer: pipeline.document.render.renderer,
              language: translation.language, translatedPieces: [{ articleId: article.articleId, artifactId: "$current", maximumReaderPages: article.maximumReaderPages }],
              inputs: staticRendererInputs, metadata: { dynamicCurrentArtifact: true, measurementPieceId: article.articleId },
            } }, parents: [...staticRendererParents, { artifactId: pipelineArtifact, relation: "write_pipeline" }],
          }), {}),
          pieceKind: "article" as const,
          pieceId: article.articleId,
          language: translation.language,
          sourceLanguage: translation.sourceLanguage,
          englishArtifacts: [pipelineArtifact] as const,
          promptArtifact: prompt(translation.prompt),
          measurementProfileArtifact: artifactId(`language-fit-profile:${translation.language}:article:${article.articleId}`),
          measurementInputArtifacts: staticRendererArtifactIds,
          inputRevisions: translation.inputRevisions,
          ...(translation.parents[article.articleId] === null ? {} : { durableParentRevisionId: translation.parents[article.articleId]!.revisionId }),
          maximumReaderPages: article.maximumReaderPages,
          modelPolicy: translation.modelPolicy,
        })),
        {
          ...(artifacts.push({
            id: artifactId(`language-fit-profile:${translation.language}:editorial:${pipeline.document.editorial.editorialId}`),
            kind: "language_fit_profile", schemaVersion: "language-fit-profile/1", mediaType: "application/json", origin: "imported",
            payload: { kind: "json", value: {
              schemaVersion: 1, rendererContractVersion: "magazine-renderer/1", editionId: "004-the-systems-around-the-model",
              primaryLanguage: translation.language, publicationName: pipeline.document.render.publicationName, renderer: pipeline.document.render.renderer,
              language: translation.language, translatedPieces: [{ articleId: pipeline.document.editorial.editorialId, artifactId: "$current", maximumReaderPages: pipeline.document.editorial.maximumReaderPages }],
              inputs: staticRendererInputs, metadata: { dynamicCurrentArtifact: true, measurementPieceId: pipeline.document.editorial.editorialId },
            } }, parents: [...staticRendererParents, { artifactId: pipelineArtifact, relation: "write_pipeline" }],
          }), {}),
          pieceKind: "editorial" as const,
          pieceId: pipeline.document.editorial.editorialId,
          language: translation.language,
          sourceLanguage: translation.sourceLanguage,
          englishArtifacts: [pipelineArtifact] as const,
          promptArtifact: prompt(translation.prompt),
          measurementProfileArtifact: artifactId(`language-fit-profile:${translation.language}:editorial:${pipeline.document.editorial.editorialId}`),
          measurementInputArtifacts: staticRendererArtifactIds,
          inputRevisions: translation.inputRevisions,
          ...(translation.parents[pipeline.document.editorial.editorialId] === null ? {} : { durableParentRevisionId: translation.parents[pipeline.document.editorial.editorialId]!.revisionId }),
          maximumReaderPages: pipeline.document.editorial.maximumReaderPages,
          modelPolicy: translation.modelPolicy,
        },
      ]), art: [],
      render: {
        renderManifestArtifact: profile,
        rendererContractVersion: "render-edition/1",
        layoutInputRevisions: pipeline.document.layoutInputs,
        configuredLanguages: pipeline.document.render.configuredLanguages,
        selectedArtArtifacts: images.map((image) => artifactId(`selected-image:${(image.ref as Extract<typeof image.ref, { readonly kind: "image" }>).logicalId}:${image.ref.revisionId}`)),
        selectedArtRevisions: images.map((image) => image.ref as Extract<typeof image.ref, { readonly kind: "image" }>),
        studioPolicy: pipeline.document.render.studioPolicy,
      },
      release: { publicationArtifact: release, sourceArtifacts: [...sourceExtraction.values()], dryRun: true, target: "private" },
      modelPolicy: defaultModel,
    },
  };
  return { schemaVersion: "edition-write-production-plan/1", pipeline, spec, imageGenerationAllowed: false };
}

function artifactId(value: string): ArtifactId {
  return `art_write_${createHash("sha256").update(value).digest("hex").slice(0, 24)}` as ArtifactId;
}

function sameInputRevision(left: InputRevisionRef, right: InputRevisionRef): boolean {
  return left.kind === right.kind &&
    left.editionId === right.editionId &&
    left.logicalId === right.logicalId &&
    left.revisionId === right.revisionId;
}

/**
 * The committed Spanish document is a localization template. The renderer
 * derives its run-local overlay from current immutable English and Spanish
 * manuscript artifacts, so an old manuscript hash can never be staged as an
 * active translation manifest.
 */
function rendererStaticTarget(
  ref: InputRevisionRef,
  payloadPath: string,
  declaredTarget: string | undefined,
): string {
  if (ref.kind === "edition_spec") {
    if (payloadPath === "translations/es/edition.yaml") {
      return "editions/004-the-systems-around-the-model/translations/es/edition.template.yaml";
    }
    if (payloadPath.startsWith("design/")) return payloadPath;
    return `editions/004-the-systems-around-the-model/${payloadPath}`;
  }
  if (declaredTarget === undefined) {
    throw new Error(`write pipeline has no renderer target for ${ref.kind}:${ref.logicalId}:${payloadPath}`);
  }
  return declaredTarget;
}

function captureRendererTarget(sourceId: string, payloadPath: string): string {
  const root = `library/sources/${sourceId}`;
  if (payloadPath.startsWith("raw/captures/")) {
    return `${root}/raw/${payloadPath.slice("raw/captures/".length)}`;
  }
  if (!payloadPath.startsWith("raw/")) {
    throw new Error(`source capture payload is outside raw/: ${payloadPath}`);
  }
  return `${root}/${payloadPath.slice("raw/".length)}`;
}

function selectedImageTarget(logicalId: string): string {
  const root = "editions/004-the-systems-around-the-model";
  if (logicalId === "cover") return `${root}/art/cover-candidate-wildcard-v2.png`;
  if (logicalId.startsWith("closing-")) {
    const names: Readonly<Record<string, string>> = {
      "closing-signal-gates": "closing-signal-gates-manga.png",
      "closing-memory-rings": "closing-memory-rings-manga.png",
      "closing-protocol-exchange": "closing-protocol-exchange-manga.png",
    };
    const name = names[logicalId];
    if (name !== undefined) return `${root}/art/${name}`;
  }
  if (logicalId.endsWith("-tail")) {
    const article = logicalId.slice(0, -"-tail".length);
    const name = article === "mcp-in-a-nutshell" ? "mcp-four-vignettes" : article;
    return `${root}/art/article-tails/${name}.png`;
  }
  if (logicalId.endsWith("-opener")) {
    return `${root}/art/article-openers/${logicalId.slice(0, -"-opener".length)}.png`;
  }
  throw new Error(`Edition 4 write pipeline has no renderer target for selected image ${logicalId}`);
}
