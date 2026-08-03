import { readFile } from "node:fs/promises";
import { posix } from "node:path";
import { resolve } from "node:path";

import { parse } from "yaml";

import type { AuthorizedWorker } from "./authority/local-authority.ts";
import type {
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  RevisionId,
  RunId,
  RunStatus,
  RunView,
  WorkOfferView,
} from "./contracts/index.ts";
import { parseRunSpec } from "./contracts/index.ts";
import {
  DurableStore,
  GitCliDurableGit,
  resolveCompositionRevision,
  type CompositionRevisionBinding,
  type DurableGit,
  type DurableRevisionRef,
  type InputRevisionRef,
  type RenderStage,
  type ResolvedDurableRevision,
  type ResolvedInputRevision,
} from "./durable/index.ts";
import {
  EditionRunLayout,
  type EditionRunPublishResult,
  type EditionRunReviewProjectionResult,
} from "./edition-run-layout.ts";
import {
  CompositionBootstrapExecutor,
  ConfiguredExecutorResolver,
  DurableCheckpointExecutor,
  DurableStoreCheckpointImplementation,
  RenderInspectionExecutor,
  RendererExecutor,
  executeAvailableWork,
  resolveCompositionBootstrap,
  type CompositionBootstrapResult,
  type ExecutorRegistration,
} from "./executors/index.ts";
import {
  PythonRendererAdapter,
  RENDERER_CONTRACT_VERSION,
  type RenderAssemblyManifest,
  type RendererAdapter,
  type RenderExecutionProfile,
} from "./renderer-adapter/index.ts";
import { RunEngineError } from "./run-engine/types.ts";

type RunBootstrapRevision = Extract<InputRevisionRef, { readonly kind: "run_bootstrap" }>;

export type EditionBootstrapRenderConfiguration = {
  readonly primaryLanguage: string;
  readonly publicationName: string;
  readonly renderer: "reportlab" | "weasyprint";
  readonly design?: string;
};

export type EditionBootstrapPlan = {
  readonly schemaVersion: "edition-bootstrap-plan/1";
  readonly editionKey: string;
  readonly bootstrapRevision: RunBootstrapRevision;
  readonly compositionRevision: CompositionRevisionBinding;
  readonly configuredLanguages: readonly string[];
  readonly selectedImageRevisionRefs: readonly Extract<
    DurableRevisionRef,
    { readonly kind: "image" }
  >[];
  readonly imageGenerationAllowed: false;
  readonly renderer: {
    readonly adapterContractVersion: typeof RENDERER_CONTRACT_VERSION;
    readonly offerContractVersion: string;
    readonly profileArtifactId: ArtifactId;
    readonly assemblyArtifactId: ArtifactId;
    readonly editionPackageId: string;
    readonly editionManifestArtifactId: ArtifactId;
    readonly referencedTargetCount: number;
    readonly primaryLanguage: string;
    readonly publicationName: string;
    readonly implementation: "reportlab" | "weasyprint";
    readonly inputs: readonly {
      readonly artifactId: ArtifactId;
      readonly targetPath: string;
    }[];
  };
  readonly ingestion: {
    readonly durableRevisionCount: number;
    readonly inputRevisionCount: number;
    readonly layoutInputRevisionCount: number;
    readonly rendererInputRevisionCount: number;
    readonly importedArtifactCount: number;
  };
};

export type PreparedEditionBootstrap = {
  readonly plan: EditionBootstrapPlan;
  readonly spec: EditionRootRunSpec;
};

export type EditionBootstrapHumanBoundary = {
  readonly offerId: WorkOfferView["id"];
  readonly role: WorkOfferView["role"];
  readonly contractVersion: string;
  readonly reviewArtifacts: readonly {
    readonly artifactId: ArtifactId;
    readonly kind: string;
    readonly mediaType: string;
    readonly logicalPath: string;
  }[];
};

export type EditionBootstrapRunResult = {
  readonly schemaVersion: "edition-bootstrap-run/1";
  readonly editionKey: string;
  readonly bootstrapRevision: RunBootstrapRevision;
  readonly runId: RunId;
  readonly runName: string;
  readonly internalDirectory: string;
  /** Present only when an exact render was projected or human-approved. */
  readonly publicDirectory?: string;
  readonly status: RunStatus;
  readonly boundary: "human" | "terminal";
  readonly pendingHuman?: EditionBootstrapHumanBoundary;
  /** A fenced, non-authoritative projection for the still-pending visual review. */
  readonly reviewProjection?: EditionRunReviewProjectionResult;
  readonly published?: EditionRunPublishResult;
};

export type EditionBootstrapRunnerOptions = {
  readonly editionKey: string;
  readonly repositoryRoot: string;
  readonly outputRoot: string;
  readonly render: EditionBootstrapRenderConfiguration;
  readonly durableGit?: DurableGit;
  readonly rendererAdapter?: RendererAdapter;
  /** Authenticated subprocess authority for bounded non-human bootstrap work. */
  readonly authority?: EditionBootstrapAutomationAuthority;
};

export type EditionBootstrapAutomationAuthority = {
  readonly toolWorker: AuthorizedWorker;
};

const MAX_AUTONOMOUS_STEPS = 32;
const AUTOMATED_REVIEW_PROJECTION_NOTE =
  "Automated projection of the exact offered render artifacts. This does not answer or approve the human visual-review offer; independent original-resolution visual QA remains required.";

/**
 * Owns the read-only bootstrap plan and the bounded autonomous execution loop.
 * XState and RunEngine remain the only lifecycle authority; this facade only
 * supplies exact immutable inputs and executes configured non-human offers.
 */
export class EditionBootstrapRunner {
  readonly editionKey: string;
  readonly repositoryRoot: string;
  readonly outputRoot: string;

  private readonly render: EditionBootstrapRenderConfiguration;
  private readonly git: DurableGit;
  private readonly rendererAdapter: RendererAdapter;
  private readonly layout: EditionRunLayout;
  private readonly authority: EditionBootstrapAutomationAuthority | undefined;

  constructor(options: EditionBootstrapRunnerOptions) {
    this.editionKey = options.editionKey;
    this.repositoryRoot = resolve(options.repositoryRoot);
    this.render = options.render;
    this.git = options.durableGit ?? new GitCliDurableGit(this.repositoryRoot);
    this.rendererAdapter = options.rendererAdapter ?? new PythonRendererAdapter(this.repositoryRoot);
    this.authority = options.authority;
    this.layout = new EditionRunLayout({
      editionKey: this.editionKey,
      repositoryRoot: this.repositoryRoot,
      outputRoot: options.outputRoot,
      durableGit: this.git,
    });
    this.outputRoot = this.layout.outputRoot;
  }

  /** Resolve and validate the exact committed graph without allocating a run. */
  async plan(bootstrapRevision: RunBootstrapRevision): Promise<EditionBootstrapPlan> {
    return (await this.prepare(bootstrapRevision)).plan;
  }

  async prepare(bootstrapRevision: RunBootstrapRevision): Promise<PreparedEditionBootstrap> {
    if (bootstrapRevision.editionId !== this.editionKey) {
      throw new RunEngineError(
        "EDITION_BOOTSTRAP_EDITION_MISMATCH",
        `Bootstrap edition ${bootstrapRevision.editionId} does not match ${this.editionKey}`,
      );
    }
    const bootstrap = await resolveCompositionBootstrap(
      this.repositoryRoot,
      bootstrapRevision,
      this.git,
    );
    const stage = await resolveCompositionRevision(
      this.repositoryRoot,
      bootstrap.compositionRevision,
      this.git,
    );
    return await buildEditionBootstrapRunSpec(bootstrap, stage, this.render);
  }

  /** Allocate or resume one canonical run and stop at a human or terminal boundary. */
  async run(bootstrapRevision: RunBootstrapRevision): Promise<EditionBootstrapRunResult> {
    const toolWorker = await this.requireToolWorker();
    const prepared = await this.prepare(bootstrapRevision);
    const allocated = await this.layout.allocate(prepared.spec, {
      idempotencyKey: bootstrapRevision.revisionId,
    });
    const paths = {
      runId: allocated.runId,
      runName: allocated.runName,
      internalDirectory: allocated.internalDirectory,
      publicDirectory: allocated.publicDirectory,
    };
    allocated.close();

    const first = await this.inspectBoundary(paths.runId);
    const boundary = first ?? await this.layout.withScratch(paths.runId, async (scratch) => {
      const opened = await this.layout.open(paths.runId);
      try {
        const store = new DurableStore({
          repositoryRoot: this.repositoryRoot,
          workRoot: scratch.stagedDirectory,
          git: this.git,
        });
        const registrations: readonly ExecutorRegistration[] = [
          {
            executor: new CompositionBootstrapExecutor({
              repositoryRoot: this.repositoryRoot,
              git: this.git,
            }),
            authorizedWorker: toolWorker,
            roles: ["composition_bootstrap"],
          },
          {
            executor: new RendererExecutor(this.rendererAdapter, {
              workDirectory: scratch.rendererWorkDirectory,
            }),
            authorizedWorker: toolWorker,
            roles: ["measure_edition", "render"],
          },
          {
            executor: new RenderInspectionExecutor(),
            authorizedWorker: toolWorker,
            roles: ["render_inspection"],
          },
          {
            executor: new DurableCheckpointExecutor(
              new DurableStoreCheckpointImplementation(opened.engine, store),
            ),
            authorizedWorker: toolWorker,
            roles: ["durable_checkpoint"],
          },
        ];
        const resolver = new ConfiguredExecutorResolver(registrations);
        const signal = new AbortController().signal;
        const entryView = await opened.engine.inspect(paths.runId);
        const resume = retryableResumeFromView(entryView);
        if (resume !== undefined) {
          await opened.engine.retry(paths.runId, resume.actorId);
        }
        for (let step = 0; step < MAX_AUTONOMOUS_STEPS; step += 1) {
          const view = await opened.engine.inspect(paths.runId);
          const found = boundaryFromView(view);
          if (found !== undefined) return found;
          const claimable = claimableOffers(view);
          if (claimable.length === 0) {
            throw new RunEngineError(
              "EDITION_BOOTSTRAP_STALLED",
              `Run ${paths.runId} has no claimable offer and is not at a human or terminal boundary`,
            );
          }
          const result = await executeAvailableWork(
            opened.engine,
            paths.runId,
            resolver,
            signal,
            { maxConcurrency: 1 },
          );
          if (result.answered.length === 0 && result.failed.length === 0) {
            throw new RunEngineError(
              "EDITION_BOOTSTRAP_STALLED",
              `Run ${paths.runId} made no progress while executing configured offers`,
            );
          }
        }
        throw new RunEngineError(
          "EDITION_BOOTSTRAP_STEP_BUDGET",
          `Run ${paths.runId} exceeded ${MAX_AUTONOMOUS_STEPS} autonomous work steps`,
        );
      } finally {
        opened.close();
      }
    });

    const reviewProjection = boundary.kind === "human" &&
      boundary.pendingHuman?.role === "visual_review"
      ? await this.layout.projectReview(paths.runId, {
          expectedHeadSequence: await this.currentHeadSequence(paths.runId),
          expectedOfferId: boundary.pendingHuman.offerId,
          independentCritic: {
            result: "not_run",
            note: AUTOMATED_REVIEW_PROJECTION_NOTE,
          },
        })
      : undefined;
    const published = boundary.status === "complete"
      ? await this.layout.publish(paths.runId)
      : undefined;
    const publicDirectory = reviewProjection?.publicDirectory ?? published?.publicDirectory;
    return {
      schemaVersion: "edition-bootstrap-run/1",
      editionKey: this.editionKey,
      bootstrapRevision,
      runId: paths.runId,
      runName: paths.runName,
      internalDirectory: paths.internalDirectory,
      status: boundary.status,
      boundary: boundary.kind,
      ...(boundary.pendingHuman === undefined
        ? {}
        : { pendingHuman: boundary.pendingHuman }),
      ...(publicDirectory === undefined ? {} : { publicDirectory }),
      ...(reviewProjection === undefined ? {} : { reviewProjection }),
      ...(published === undefined ? {} : { published }),
    };
  }

  private async inspectBoundary(runId: RunId): Promise<ExecutionBoundary | undefined> {
    const opened = await this.layout.open(runId);
    try {
      return boundaryFromView(await opened.engine.inspect(runId));
    } finally {
      opened.close();
    }
  }

  private async requireToolWorker(): Promise<AuthorizedWorker> {
    const worker = this.authority?.toolWorker;
    if (worker === undefined) {
      throw new RunEngineError(
        "EDITION_BOOTSTRAP_EXECUTOR_AUTH_REQUIRED",
        "Edition bootstrap run requires an injected authenticated subprocess worker",
      );
    }
    const description = await worker.describe();
    if (description.authority !== "tool" || !description.capabilities.includes("subprocess")) {
      throw new RunEngineError(
        "EDITION_BOOTSTRAP_EXECUTOR_AUTH_INVALID",
        "Edition bootstrap executor authority must be a subprocess-capable tool session",
      );
    }
    return worker;
  }

  private async currentHeadSequence(runId: RunId): Promise<number> {
    const opened = await this.layout.open(runId);
    try {
      return (await opened.engine.inspect(runId)).headSequence;
    } finally {
      opened.close();
    }
  }
}

export async function buildEditionBootstrapRunSpec(
  bootstrap: CompositionBootstrapResult,
  stage: RenderStage,
  render: EditionBootstrapRenderConfiguration,
): Promise<PreparedEditionBootstrap> {
  if (
    stage.compositionDocument.edition_id !== bootstrap.bootstrapRevision.editionId ||
    stage.compositionDocument.composition_id !==
      bootstrap.compositionRevision.revisionRef.compositionId
  ) {
    throw invalidPlan("resolved composition identity does not match the bootstrap authority");
  }
  if (!bootstrap.configuredLanguages.includes(render.primaryLanguage)) {
    throw invalidPlan("renderer primary language is not configured by the bootstrap revision");
  }

  const layoutKeys = new Set(
    stage.compositionDocument.layout_inputs.map((pin) => inputRevisionKey(pin.revision)),
  );
  const imported: ArtifactSeed[] = [];
  const rendererInputs: Array<{ readonly artifactId: ArtifactId; readonly targetPath: string }> = [];
  const content: ArtifactId[] = [];
  const translations: ArtifactId[] = [];
  const art: ArtifactId[] = [];
  const targets = new Map<string, ArtifactId>();
  const inputArtifactsByRevision = new Map<string, ArtifactId[]>();
  const layoutArtifactIds: ArtifactId[] = [];
  const renderableInputRevisionKeys = new Set<string>();
  const editionSpecFiles: EditionSpecStageFile[] = [];

  stage.inputRevisions.forEach((revision, revisionIndex) => {
    const key = inputRevisionKey(revision.ref);
    const renderable = isRendererInputRevision(revision.ref);
    if (renderable) renderableInputRevisionKeys.add(key);
    const revisionArtifactIds: ArtifactId[] = [];
    revision.manifest.files.forEach((file, fileIndex) => {
      const artifactId = importedArtifactId(
        "input",
        revisionIndex,
        fileIndex,
        revision.ref.revisionId,
      );
      const targetPath = renderable
        ? explicitInputRendererTarget(revision, file.path)
        : undefined;
      if (targetPath !== undefined) {
        registerTarget(targets, targetPath, artifactId);
        rendererInputs.push({ artifactId, targetPath });
      }
      if (revision.ref.kind === "edition_spec") {
        if (targetPath === undefined) {
          throw invalidPlan("edition_spec payload is missing its renderer target");
        }
        editionSpecFiles.push({
          artifactId,
          path: file.path,
          payloadPath: requiredInputPayload(revision, file.path),
          targetPath,
        });
      }
      imported.push({
        id: artifactId,
        kind: `${revision.ref.kind}_revision_payload`,
        schemaVersion: "input-revision/1",
        mediaType: file.media_type,
        origin: "imported",
        payload: { kind: "file", path: requiredInputPayload(revision, file.path) },
        metadata: {
          inputRevision: revision.ref,
          manifestDigest: revision.manifestDigest,
          revisionPayloadPath: file.path,
          ...(targetPath === undefined ? {} : { rendererTargetPath: targetPath }),
        },
      });
      revisionArtifactIds.push(artifactId);
      if (layoutKeys.has(key)) layoutArtifactIds.push(artifactId);
    });
    inputArtifactsByRevision.set(key, revisionArtifactIds);
  });

  const durableArtifactIds: ArtifactId[] = [];

  stage.durableInputs.forEach((revision, revisionIndex) => {
    const revisionInputArtifacts = revision.manifest.input_revisions.flatMap((ref) => {
      const ids = inputArtifactsByRevision.get(inputRevisionKey(ref));
      if (ids === undefined) {
        throw invalidPlan(
          `durable revision ${durableRevisionKey(revision.ref)} has an unresolved input revision`,
        );
      }
      return ids;
    });
    revision.manifest.files.forEach((file, fileIndex) => {
      if (file.legacySource === undefined) {
        throw invalidPlan(
          `durable payload ${durableRevisionKey(revision.ref)}:${file.path} has no explicit renderer target`,
        );
      }
      const artifactId = importedArtifactId(
        "durable",
        revisionIndex,
        fileIndex,
        revision.ref.revisionId,
      );
      const targetPath = rendererTarget(file.legacySource.repositoryPath);
      registerTarget(targets, targetPath, artifactId);
      imported.push({
        id: artifactId,
        kind: `${revision.ref.kind}_revision_payload`,
        schemaVersion: "durable-revision/1",
        mediaType: file.mediaType,
        origin: "imported",
        payload: { kind: "file", path: requiredPayload(revision, file.path) },
        parents: revisionInputArtifacts.map((parentId) => ({
          artifactId: parentId,
          relation: "input_revision",
        })),
        metadata: {
          durableRevision: revision.ref,
          manifestDigest: revision.manifestDigest,
          revisionPayloadPath: file.path,
          rendererTargetPath: targetPath,
        },
      });
      durableArtifactIds.push(artifactId);
      rendererInputs.push({ artifactId, targetPath });
      if (revision.ref.kind === "image") {
        art.push(artifactId);
      } else if (revision.ref.language === render.primaryLanguage) {
        content.push(artifactId);
      } else {
        translations.push(artifactId);
      }
    });
  });

  const resolvedLayouts = stage.inputRevisions.filter((revision) =>
    layoutKeys.has(inputRevisionKey(revision.ref))
  );
  if (new Set(resolvedLayouts.map((revision) => inputRevisionKey(revision.ref))).size !== layoutKeys.size) {
    throw invalidPlan("composition layout inputs were not resolved exactly");
  }

  const compositionArtifactIds = stage.composition.manifest.files.map((file, fileIndex) => {
    const artifactId = importedArtifactId(
      "composition",
      0,
      fileIndex,
      stage.composition.ref.revisionId,
    );
    imported.push({
      id: artifactId,
      kind: "composition_revision_payload",
      schemaVersion: "durable-revision/1",
      mediaType: file.mediaType,
      origin: "imported",
      payload: { kind: "file", path: requiredPayload(stage.composition, file.path) },
      parents: [
        ...durableArtifactIds.map((artifactId) => ({
          artifactId,
          relation: "composed_revision",
        })),
        ...layoutArtifactIds.map((artifactId) => ({
          artifactId,
          relation: "layout_input",
        })),
      ],
      metadata: {
        durableRevision: stage.composition.ref,
        manifestDigest: stage.composition.manifestDigest,
        revisionPayloadPath: file.path,
      },
    });
    return artifactId;
  });

  const controlArtifactId = bootstrapArtifactId(
    bootstrap.bootstrapRevision,
    "control",
  );
  const profileArtifactId = bootstrapArtifactId(
    bootstrap.bootstrapRevision,
    "render_profile",
  );
  const assemblyArtifactId = bootstrapArtifactId(
    bootstrap.bootstrapRevision,
    "render_assembly",
  );
  const renderOffer = bootstrap.promptSet.roleInputs.render;
  if (renderOffer.kind !== "contract") {
    throw invalidPlan("bootstrap render role does not bind an execution contract");
  }
  const stageContract = await validateEditionStageInventory(
    editionSpecFiles,
    rendererInputs,
    bootstrap.configuredLanguages,
    render.primaryLanguage,
  );
  const profile: RenderExecutionProfile = {
    schemaVersion: 1,
    rendererContractVersion: RENDERER_CONTRACT_VERSION,
    editionPackageId: stageContract.editionPackageId,
    primaryLanguage: render.primaryLanguage,
    publicationName: render.publicationName,
    renderer: render.renderer,
    ...(render.design === undefined ? {} : { design: render.design }),
    inputs: rendererInputs,
    metadata: {
      bootstrapRevision: bootstrap.bootstrapRevision,
      compositionRevision: bootstrap.compositionRevision.revisionRef,
      imageGenerationAllowed: false,
    },
  };
  const assembly: RenderAssemblyManifest = {
    editionId: bootstrap.bootstrapRevision.editionId,
    content,
    translations,
    translationProofs: [],
    art,
    editionApproval: [],
    configuredLanguages: bootstrap.configuredLanguages,
    renderProfileArtifactId: profileArtifactId,
    printerProfileArtifactId: null,
  };
  const control: JsonObject = {
    schemaVersion: "edition-bootstrap-control/1",
    bootstrapRevision: bootstrap.bootstrapRevision,
    compositionRevision: bootstrap.compositionRevision.revisionRef,
    promptSetId: bootstrap.promptSet.id,
    imageGenerationAllowed: false,
  };
  const artifacts: ArtifactSeed[] = [
    ...imported,
    {
      id: controlArtifactId,
      kind: "edition_bootstrap_control",
      schemaVersion: "edition-bootstrap-control/1",
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: control },
      parents: compositionArtifactIds.map((artifactId) => ({
        artifactId,
        relation: "composition_revision",
      })),
    },
    {
      id: profileArtifactId,
      kind: "render_profile",
      schemaVersion: RENDERER_CONTRACT_VERSION,
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: profile as unknown as JsonObject },
      parents: rendererInputs.map((input) => ({
        artifactId: input.artifactId,
        relation: "render_input",
      })),
    },
    {
      id: assemblyArtifactId,
      kind: "render_manifest",
      schemaVersion: "1",
      mediaType: "application/json",
      origin: "imported",
      payload: { kind: "json", value: assembly as unknown as JsonObject },
      parents: [
        ...content.map((artifactId) => ({ artifactId, relation: "content" })),
        ...translations.map((artifactId) => ({ artifactId, relation: "translation" })),
        ...art.map((artifactId) => ({ artifactId, relation: "selected_art" })),
        { artifactId: profileArtifactId, relation: "render_profile" },
        ...layoutArtifactIds.map((artifactId) => ({ artifactId, relation: "layout_input" })),
        ...compositionArtifactIds.map((artifactId) => ({
          artifactId,
          relation: "composition_source",
        })),
      ],
      metadata: {
        bootstrapRevision: bootstrap.bootstrapRevision,
        compositionRevision: bootstrap.compositionRevision.revisionRef,
      },
    },
  ];
  const modelPolicy = {
    default: { adapter: "committed-bootstrap", model: bootstrap.promptSet.id },
  } as const;
  const spec = parseRunSpec({
    schemaVersion: 1,
    kind: "edition",
    artifacts,
    metadata: {
      bootstrapRevision: bootstrap.bootstrapRevision,
      compositionRevision: bootstrap.compositionRevision.revisionRef,
      imageGenerationAllowed: false,
    },
    edition: {
      editionId: bootstrap.bootstrapRevision.editionId,
      execution: {
        kind: "bootstrap_composition",
        bootstrapRevision: bootstrap.bootstrapRevision,
        postRender: "stop_unreleased",
      },
      editionBrief: controlArtifactId,
      sources: [],
      articles: [],
      editorial: {
        editorialId: "bootstrap-composition",
        briefArtifact: controlArtifactId,
        writingRules: controlArtifactId,
        modelPolicy,
      },
      translations: bootstrap.configuredLanguages
        .filter((language) => language !== render.primaryLanguage)
        .map((language) => ({
          // Bootstrap composition renders the already-bound composition rather
          // than spawning translation actors, but the root spec remains a
          // valid per-piece edition graph.
          pieceKind: "editorial" as const,
          pieceId: "bootstrap-composition",
          language,
          sourceLanguage: render.primaryLanguage,
          englishArtifacts: [controlArtifactId],
          promptArtifact: controlArtifactId,
          maximumReaderPages: 7,
          modelPolicy,
        })),
      art: [],
      render: {
        renderManifestArtifact: assemblyArtifactId,
        rendererContractVersion: renderOffer.contractVersion,
        configuredLanguages: bootstrap.configuredLanguages,
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: controlArtifactId,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy,
    },
  }) as EditionRootRunSpec;
  const plan: EditionBootstrapPlan = {
    schemaVersion: "edition-bootstrap-plan/1",
    editionKey: bootstrap.bootstrapRevision.editionId,
    bootstrapRevision: bootstrap.bootstrapRevision,
    compositionRevision: bootstrap.compositionRevision,
    configuredLanguages: bootstrap.configuredLanguages,
    selectedImageRevisionRefs: bootstrap.selectedImageRevisionRefs,
    imageGenerationAllowed: false,
    renderer: {
      adapterContractVersion: RENDERER_CONTRACT_VERSION,
      offerContractVersion: renderOffer.contractVersion,
      profileArtifactId,
      assemblyArtifactId,
      editionPackageId: stageContract.editionPackageId,
      editionManifestArtifactId: stageContract.editionManifestArtifactId,
      referencedTargetCount: stageContract.referencedTargets.length,
      primaryLanguage: render.primaryLanguage,
      publicationName: render.publicationName,
      implementation: render.renderer,
      inputs: rendererInputs,
    },
    ingestion: {
      durableRevisionCount: stage.durableInputs.length,
      inputRevisionCount: stage.inputRevisions.length,
      layoutInputRevisionCount: resolvedLayouts.length,
      rendererInputRevisionCount: renderableInputRevisionKeys.size,
      importedArtifactCount: imported.length,
    },
  };
  return { plan, spec };
}

type ExecutionBoundary = {
  readonly kind: "human" | "terminal";
  readonly status: RunStatus;
  readonly pendingHuman?: EditionBootstrapHumanBoundary;
};

function boundaryFromView(view: RunView): ExecutionBoundary | undefined {
  if (view.status === "complete" || view.status === "failed") {
    return { kind: "terminal", status: view.status };
  }
  const human = view.offers.find((offer) =>
    (offer.status === "offered" || offer.status === "claimed") &&
    offer.allowedWorkerCapabilities.includes("human")
  );
  if (human === undefined) return undefined;
  const artifacts = new Map(view.artifacts.map((artifact) => [artifact.id, artifact]));
  const reviewArtifacts = human.inputArtifacts.flatMap((artifactId) => {
    const artifact = artifacts.get(artifactId);
    const logicalPath = artifact?.metadata.relativePath;
    return artifact === undefined || typeof logicalPath !== "string"
      ? []
      : [{
          artifactId,
          kind: artifact.kind,
          mediaType: artifact.mediaType,
          logicalPath,
        }];
  });
  return {
    kind: "human",
    status: view.status,
    pendingHuman: {
      offerId: human.id,
      role: human.role,
      contractVersion: human.contractVersion,
      reviewArtifacts,
    },
  };
}

function claimableOffers(view: RunView): readonly WorkOfferView[] {
  const now = Date.now();
  return view.offers.filter((offer) => {
    if (offer.status === "offered") return true;
    if (offer.status !== "claimed" || offer.activeAttemptId === undefined) return false;
    const attempt = view.attempts.find((candidate) => candidate.id === offer.activeAttemptId);
    return attempt?.status === "active" && Date.parse(attempt.leaseExpiresAt) <= now;
  });
}

type RetryableResume = {
  readonly actorId: WorkOfferView["actorId"];
  readonly offerId: WorkOfferView["id"];
  readonly attemptId: NonNullable<WorkOfferView["activeAttemptId"]>;
};

/**
 * Finds one exact persisted machine failure at invocation entry. The caller
 * deliberately invokes this only once, before executing any offers, so a
 * failure produced by this invocation cannot create an implicit retry loop.
 */
function retryableResumeFromView(view: RunView): RetryableResume | undefined {
  if (view.status !== "escalated") return undefined;
  const offers = new Map(view.offers.map((offer) => [offer.id, offer]));
  const candidates = view.actors.flatMap((actor): RetryableResume[] => {
    if (actor.status !== "active") return [];
    const latestEvent = [...view.events].reverse().find(
      (event) => event.actorId === actor.id,
    );
    if (
      latestEvent?.type !== "WORK_FAILED" ||
      latestEvent.payload.classification !== "retryable" ||
      typeof latestEvent.payload.slot !== "string"
    ) {
      return [];
    }
    const attempt = [...view.attempts].reverse().find((candidate) => {
      const offer = offers.get(candidate.offerId);
      return (
        candidate.status === "failed" &&
        candidate.worker.authority !== "human" &&
        !candidate.worker.capabilities.includes("human") &&
        offer?.actorId === actor.id &&
        offer.slot === latestEvent.payload.slot &&
        offer.status === "failed" &&
        !offer.allowedWorkerCapabilities.includes("human")
      );
    });
    if (attempt === undefined) return [];
    const offer = offers.get(attempt.offerId);
    return offer === undefined
      ? []
      : [{ actorId: actor.id, offerId: offer.id, attemptId: attempt.id }];
  });
  return candidates.length === 1 ? candidates[0] : undefined;
}

function importedArtifactId(
  scope: "composition" | "durable" | "input",
  revisionIndex: number,
  fileIndex: number,
  revisionId: RevisionId,
): ArtifactId {
  return `art_bootstrap_${scope}_${String(revisionIndex).padStart(3, "0")}_${String(fileIndex).padStart(3, "0")}_${revisionId}` as ArtifactId;
}

function bootstrapArtifactId(
  revision: RunBootstrapRevision,
  suffix: string,
): ArtifactId {
  return `art_bootstrap_${portable(revision.editionId)}_${revision.revisionId}_${suffix}` as ArtifactId;
}

function portable(value: string): string {
  return value.replaceAll(/[^A-Za-z0-9_.-]/gu, "_");
}

function durableRevisionKey(ref: DurableRevisionRef): string {
  return ref.kind === "composition"
    ? `${ref.kind}:${ref.editionId}:${ref.compositionId}:${ref.revisionId}`
    : `${ref.kind}:${ref.editionId}:${ref.logicalId}:${ref.language ?? ""}:${ref.revisionId}`;
}

function inputRevisionKey(ref: InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

type EditionSpecStageFile = {
  readonly artifactId: ArtifactId;
  readonly path: string;
  readonly payloadPath: string;
  readonly targetPath: string;
};

type EditionStageInventory = {
  readonly editionPackageId: string;
  readonly editionManifestArtifactId: ArtifactId;
  readonly referencedTargets: readonly string[];
};

async function validateEditionStageInventory(
  specFiles: readonly EditionSpecStageFile[],
  rendererInputs: readonly { readonly artifactId: ArtifactId; readonly targetPath: string }[],
  configuredLanguages: readonly string[],
  primaryLanguage: string,
): Promise<EditionStageInventory> {
  const roots = specFiles.filter((file) => file.path === "edition.yaml");
  if (roots.length !== 1) {
    throw invalidPlan(`render stage must contain exactly one edition_spec edition.yaml, found ${roots.length}`);
  }
  const root = roots[0]!;
  const document = await readYamlObject(root.payloadPath, "edition_spec edition.yaml");
  const editionPackageId = requiredPortableId(document.id, "edition_spec id");
  const editionRoot = `editions/${editionPackageId}`;
  const expectedRootTarget = `${editionRoot}/edition.yaml`;
  if (root.targetPath !== expectedRootTarget) {
    throw invalidPlan(
      `edition_spec edition.yaml target must be ${expectedRootTarget}, got ${root.targetPath}`,
    );
  }
  if (document.language !== undefined && document.language !== primaryLanguage) {
    throw invalidPlan("edition_spec primary language does not match renderer configuration");
  }

  const referenced = new Set<string>([expectedRootTarget]);
  addRootEditionReferences(document, editionRoot, referenced);
  for (const language of configuredLanguages) {
    if (language === primaryLanguage) continue;
    const path = `translations/${language}/edition.yaml`;
    const overlays = specFiles.filter((file) => file.path === path);
    if (overlays.length !== 1) {
      throw invalidPlan(`render stage must contain exactly one ${language} edition overlay`);
    }
    const overlay = overlays[0]!;
    const expectedTarget = `${editionRoot}/${path}`;
    if (overlay.targetPath !== expectedTarget) {
      throw invalidPlan(
        `${language} edition overlay target must be ${expectedTarget}, got ${overlay.targetPath}`,
      );
    }
    const overlayDocument = await readYamlObject(
      overlay.payloadPath,
      `${language} edition overlay`,
    );
    if (overlayDocument.language !== language) {
      throw invalidPlan(`${language} edition overlay declares a different language`);
    }
    referenced.add(expectedTarget);
    addTranslationReferences(
      overlayDocument,
      `${editionRoot}/translations/${language}`,
      referenced,
    );
  }

  const targets = new Set(rendererInputs.map((input) => input.targetPath));
  const missing = [...referenced].filter((target) => !targets.has(target)).sort();
  if (missing.length > 0) {
    throw invalidPlan(`render stage omits referenced targets: ${missing.join(", ")}`);
  }
  return {
    editionPackageId,
    editionManifestArtifactId: root.artifactId,
    referencedTargets: [...referenced].sort(),
  };
}

async function readYamlObject(path: string, label: string): Promise<Record<string, unknown>> {
  let decoded: unknown;
  try {
    decoded = parse(await readFile(path, "utf8"));
  } catch (error) {
    throw invalidPlan(
      `${label} is not valid YAML: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  if (!isRecord(decoded)) throw invalidPlan(`${label} must be a mapping`);
  return decoded;
}

function addRootEditionReferences(
  document: Record<string, unknown>,
  editionRoot: string,
  targets: Set<string>,
): void {
  addReference(document.art_direction_path, editionRoot, targets);
  addReference(document.editorial, editionRoot, targets);
  const cover = isRecord(document.cover) ? document.cover : undefined;
  addReference(cover?.art_path, editionRoot, targets);
  for (const article of recordArray(document.articles)) {
    addReference(article.manuscript, editionRoot, targets);
    addReference(article.tail_art_path, editionRoot, targets);
    const opener = isRecord(article.opener_art) ? article.opener_art : undefined;
    addReference(opener?.path, editionRoot, targets);
  }
  for (const section of recordArray(document.sections)) {
    addReference(section.path, editionRoot, targets);
  }
  for (const plate of recordArray(document.closing_plates)) {
    addReference(plate.art_path, editionRoot, targets);
  }
  if (Array.isArray(document.sources)) {
    for (const sourceId of document.sources) {
      const id = requiredPortableId(sourceId, "edition source id");
      targets.add(`library/sources/${id}/record.yaml`);
    }
  }
}

function addTranslationReferences(
  document: Record<string, unknown>,
  translationRoot: string,
  targets: Set<string>,
): void {
  const editorial = isRecord(document.editorial) ? document.editorial : undefined;
  addReference(editorial?.path, translationRoot, targets);
  for (const article of recordArray(document.articles)) {
    addReference(article.manuscript, translationRoot, targets);
  }
}

function addReference(value: unknown, base: string, targets: Set<string>): void {
  if (value === undefined || value === null) return;
  if (typeof value !== "string" || value.length === 0) {
    throw invalidPlan("edition manifest contains an invalid referenced path");
  }
  targets.add(rendererTarget(value.startsWith("editions/") ? value : posix.join(base, value)));
}

function recordArray(value: unknown): readonly Record<string, unknown>[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value) || value.some((entry) => !isRecord(entry))) {
    throw invalidPlan("edition manifest contains an invalid record list");
  }
  return value as readonly Record<string, unknown>[];
}

function requiredPortableId(value: unknown, label: string): string {
  if (typeof value !== "string" || !/^[a-z0-9][a-z0-9._-]*$/u.test(value)) {
    throw invalidPlan(`${label} must be a portable path segment`);
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredPayload(revision: ResolvedDurableRevision, path: string): string {
  const payload = revision.payloadPaths[path];
  if (payload === undefined) {
    throw invalidPlan(`resolved durable revision has no payload ${path}`);
  }
  return payload;
}

function requiredInputPayload(revision: ResolvedInputRevision, path: string): string {
  const payload = revision.payloadPaths[path];
  if (payload === undefined) {
    throw invalidPlan(`resolved input revision has no payload ${path}`);
  }
  return payload;
}

function isRendererInputRevision(ref: InputRevisionRef): boolean {
  return ref.kind === "edition_spec" ||
    ref.kind === "source_capture" ||
    ref.kind === "source_extraction";
}

function explicitInputRendererTarget(
  revision: ResolvedInputRevision,
  path: string,
): string {
  const file = revision.manifest.files.find((candidate) => candidate.path === path);
  if (file?.legacy_source === undefined) {
    throw invalidPlan(
      `renderer input ${inputRevisionKey(revision.ref)}:${path} has no explicit legacy target`,
    );
  }
  return rendererTarget(file.legacy_source.repositoryPath);
}

function rendererTarget(value: string): string {
  const target = value.replaceAll("\\", "/");
  if (
    target.length === 0 ||
    target.startsWith("/") ||
    target.split("/").some((part) => part === "" || part === "." || part === "..")
  ) {
    throw invalidPlan(`renderer target ${JSON.stringify(value)} is not a safe repository path`);
  }
  return target;
}

function registerTarget(
  targets: Map<string, ArtifactId>,
  targetPath: string,
  artifactId: ArtifactId,
): void {
  const collision = [...targets.entries()].find(([existing]) =>
    portablePathKey(existing) === portablePathKey(targetPath)
  );
  if (collision !== undefined) {
    throw invalidPlan(
      `renderer target ${targetPath} collides with ${collision[0]} from ${collision[1]}`,
    );
  }
  targets.set(targetPath, artifactId);
}

function portablePathKey(path: string): string {
  return path.normalize("NFC").toLocaleLowerCase("en-US");
}

function invalidPlan(message: string): RunEngineError {
  return new RunEngineError("EDITION_BOOTSTRAP_PLAN_INVALID", message);
}
