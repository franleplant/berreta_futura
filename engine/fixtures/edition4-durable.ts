import { mkdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { parse } from "yaml";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  RunId,
  RunView,
  WorkerIdentity,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  CompositionBootstrapExecutor,
  executeAvailableWork,
  RendererExecutor,
} from "../executors/index.ts";
import type { DurableGit } from "../durable/index.ts";
import {
  EDITION_4_ID,
  mediaTypeForFixture,
  stageEdition4Fixture,
} from "./edition4.ts";
import {
  RENDERER_CONTRACT_VERSION,
  type RenderExecutionProfile,
  type RendererAdapter,
} from "../renderer-adapter/index.ts";
import type { RunEngine } from "../run-engine/index.ts";

type Mapping = Record<string, unknown>;

export type Edition4DurableFixture = {
  readonly spec: EditionRootRunSpec;
  readonly productionPlan: JsonObject;
  readonly stagedRoot: string;
};

export type Edition4DurableDriverOptions = {
  readonly engine: RunEngine;
  readonly projectRoot: string;
  readonly stagingDirectory: string;
  readonly renderer: RendererAdapter;
  readonly rendererWorkDirectory: string;
  readonly runId?: RunId;
  readonly productionPlan?: JsonObject;
  readonly compositionBootstrap?: {
    readonly repositoryRoot: string;
    readonly git: Pick<DurableGit, "assertCommitted">;
  };
  readonly onRunStarted?: (runId: RunId) => Promise<void> | void;
  /** Only test fixtures may advance a visual-review offer without an independent review. */
  readonly approveVisualReview?: boolean;
  /** Only tests may answer the final release offer automatically. */
  readonly approveRelease?: boolean;
};

/**
 * Builds an Edition 4 run whose renderer inputs are frozen committed artifacts.
 * Source preparation remains live. The committed English and Spanish manuscript
 * artifacts are initial revisions so the path-free renderer profile can bind
 * every final-layout input before the run starts.
 */
export async function createEdition4DurableFixture(
  projectRoot: string,
  stagingDirectory: string,
): Promise<Edition4DurableFixture> {
  const root = resolve(projectRoot);
  const stagedRoot = resolve(stagingDirectory);
  const staged = await stageEdition4Fixture(root, stagedRoot);
  const edition = mapping(parse(await readFile(
    join(root, `editions/${EDITION_4_ID}/edition.yaml`),
    "utf8",
  )));
  const sourceIds = strings(edition.sources, "edition.sources");
  const articles = mappings(edition.articles, "edition.articles");
  const entryByTarget = new Map(staged.entries.map((entry) => [entry.target, entry]));
  const entry = (target: string) => {
    const found = entryByTarget.get(target);
    if (found === undefined) {
      throw new Error(`Edition 4 staged fixture lacks ${target}`);
    }
    return found;
  };
  const id = (name: string) => `edition4-durable-${name}` as ArtifactId;
  const editionBrief = id("brief");
  const writingRules = id("writing-rules");
  const editorialBrief = id("editorial-brief");
  const translationPrompt = id("translation-es-prompt");
  const artBrief = id("art-direction-brief");
  const printerProfile = id("printer-profile");
  const releasePlaceholder = id("release-placeholder");
  const renderProfile = id("render-profile");

  const frozenSeeds: ArtifactSeed[] = staged.entries.map((item) => ({
    id: item.artifactId,
    kind: item.kind === "edition_manifest"
      ? "edition_spec_revision_payload"
      : frozenKind(item.kind),
    schemaVersion: "edition4/1",
    mediaType: mediaTypeForFixture(item.target),
    origin: "imported",
    payload: { kind: "file", path: item.source },
    metadata: item.kind === "edition_manifest"
      ? {
          committedPath: item.target,
          editionId: EDITION_4_ID,
          inputRevision: {
            kind: "edition_spec",
            editionId: "004",
            logicalId: "main",
            revisionId: "rev_edition4_fixture",
          },
          revisionPayloadPath: "edition.yaml",
          rendererTargetPath: item.target,
        }
      : { committedPath: item.target, editionId: EDITION_4_ID },
  }));
  const sourceLeads = sourceIds.map((sourceId) => textSeed(
    id(`lead-${sourceId}`),
    `Committed Edition 4 source lead: ${sourceId}`,
    "source_lead",
  ));
  const articleInputs = articles.flatMap((article) => {
    const articleId = required(article, "id");
    return [
      textSeed(id(`article-brief-${articleId}`), `Edition 4 article brief: ${articleId}`, "article_brief"),
      textSeed(id(`writer-prompt-${articleId}`), `Faithful Edition 4 writer prompt: ${articleId}`, "writer_prompt"),
      textSeed(id(`worth-prompt-${articleId}`), "Assess reader value.", "judge_prompt"),
      textSeed(id(`evidence-prompt-${articleId}`), "Assess source evidence.", "judge_prompt"),
      textSeed(id(`craft-prompt-${articleId}`), "Assess editorial craft.", "judge_prompt"),
    ];
  });
  const translationArtifacts = staged.entries
    .filter((item) => item.kind === "translation")
    .map((item) => item.artifactId);
  const profileInputs = [
    ...staged.manifest.inputs.map(({ artifactId, targetPath }) => ({ artifactId, targetPath })),
    { artifactId: printerProfile, targetPath: "profiles/edition4-printer.json" },
  ];
  const profile: RenderExecutionProfile = {
    schemaVersion: 1,
    rendererContractVersion: RENDERER_CONTRACT_VERSION,
    editionPackageId: EDITION_4_ID,
    primaryLanguage: "en",
    publicationName: "Berreta Futura",
    renderer: "weasyprint",
    inputs: profileInputs,
    metadata: { fixture: "edition4-durable", imageGenerationAllowed: false },
  };
  const artifacts: ArtifactSeed[] = [
    ...frozenSeeds,
    ...sourceLeads,
    ...articleInputs,
    textSeed(editionBrief, "The systems around the model.", "edition_brief"),
    textSeed(writingRules, "Edition 4 house writing rules.", "writing_rules"),
    textSeed(editorialBrief, "Opening editorial brief.", "editorial_brief"),
    textSeed(translationPrompt, "Translate Edition 4 into educated castellano.", "translation_prompt"),
    textSeed(artBrief, "Use selected committed Edition 4 art only.", "art_brief"),
    jsonSeed(printerProfile, { name: "Edition 4 private fixture profile" }, "printer_profile"),
    textSeed(releasePlaceholder, "Release is represented by the approved render set.", "release_placeholder"),
    jsonSeed(
      renderProfile,
      profile as unknown as JsonObject,
      "render_profile",
      profileInputs.map((input) => ({ artifactId: input.artifactId, relation: "staged_input" })),
    ),
  ];
  const sourceSpecs = sourceIds.map((sourceId) => ({
    sourceId,
    leadArtifact: id(`lead-${sourceId}`),
  }));
  const plannedArticles = articles.map((article) => {
    const articleId = required(article, "id");
    const sourceArticleIds = strings(article.source_ids, `article ${articleId}.source_ids`);
    const manuscript = entry(required(article, "manuscript")).artifactId;
    return {
      articleId,
      contentMode: required(article, "content_mode") as "faithful_edit" | "faithful_synthesis",
      attribution: {
        kind: "source_author" as const,
        byline: required(article, "author"),
        sourceAuthors: [required(article, "author")],
        sourceIds: sourceArticleIds,
      },
      editionContext: editionBrief,
      articleBrief: id(`article-brief-${articleId}`),
      sourceIds: sourceArticleIds,
      writerPrompt: id(`writer-prompt-${articleId}`),
      judgePrompts: {
        worth: id(`worth-prompt-${articleId}`),
        evidence: id(`evidence-prompt-${articleId}`),
        craft: id(`craft-prompt-${articleId}`),
      },
      writingRules,
      initialManuscript: manuscript,
      policy: {
        maxIterations: 1,
        maximumReaderPages: 7,
        teaching: "not_applicable" as const,
        enabledLenses: ["worth", "evidence", "craft"],
        blockingLenses: [],
      },
      modelPolicy: modelPolicy(),
    };
  });
  const plannedArt = staged.selectedArtArtifactIds.map((artifactId, index) => ({
    key: index === 0 ? "edition4-cover" : `edition4-registered-art-${index}`,
    role: index === 0 ? "cover" as const : "interior" as const,
    artifactId,
    briefArtifact: artBrief,
    required: true,
  }));
  const productionPlan = {
    contractVersion: "approved-production-plan/1",
    sourceAssignmentPolicy: "at_least_once",
    articles: plannedArticles,
    art: plannedArt,
    translations: [{
      language: "es",
      sourceLanguage: "en",
      englishArtifacts: [],
      promptArtifact: translationPrompt,
      initialTranslationArtifacts: translationArtifacts,
      maximumReaderPages: 7,
      modelPolicy: modelPolicy(),
    }],
  } as const;
  const editorialTarget = `editions/${EDITION_4_ID}/${required(edition, "editorial")}`;
  return {
    stagedRoot,
    productionPlan: productionPlan as unknown as JsonObject,
    spec: {
      schemaVersion: 1,
      kind: "edition",
      artifacts,
      metadata: { fixture: "edition4-durable", imageGenerationAllowed: false },
      edition: {
        editionId: EDITION_4_ID,
        execution: { kind: "produce" },
        editionBrief,
        sources: sourceSpecs,
        articles: [],
        editorial: {
          editorialId: "edition4-opening-editorial",
          briefArtifact: editorialBrief,
          writingRules,
          initialManuscript: entry(editorialTarget).artifactId,
          modelPolicy: modelPolicy(),
        },
        translations: [{
          language: "es",
          sourceLanguage: "en",
          englishArtifacts: [],
          promptArtifact: translationPrompt,
          initialTranslationArtifacts: translationArtifacts,
          maximumReaderPages: 7,
          modelPolicy: modelPolicy(),
        }],
        art: [],
        render: {
          renderManifestArtifact: renderProfile,
          rendererContractVersion: RENDERER_CONTRACT_VERSION,
          printerProfileArtifact: printerProfile,
          configuredLanguages: ["en", "es"],
          studioPolicy: "home_ready_studio_blocked",
        },
        release: {
          publicationArtifact: releasePlaceholder,
          sourceArtifacts: [],
          dryRun: true,
          target: "private",
        },
        modelPolicy: modelPolicy(),
      },
    },
  };
}

/** Runs every Edition 4 offer via RunEngine claims and answers. */
export async function driveEdition4Durably(
  options: Edition4DurableDriverOptions,
): Promise<{ readonly runId: RunId; readonly view: RunView }> {
  const fixture = options.runId === undefined
    ? await createEdition4DurableFixture(options.projectRoot, options.stagingDirectory)
    : undefined;
  const runId = options.runId === undefined
    ? (await options.engine.start(fixture!.spec, {
        idempotencyKey: "edition4-durable-driver/1",
      })).runId
    : options.runId;
  if (options.runId === undefined) {
    await options.onRunStarted?.(runId);
  }
  const renderer = new RendererExecutor(options.renderer, {
    id: "edition4-durable-renderer",
    workDirectory: options.rendererWorkDirectory,
  });
  const executors = [
    ...(options.compositionBootstrap === undefined
      ? []
      : [new CompositionBootstrapExecutor({
          repositoryRoot: options.compositionBootstrap.repositoryRoot,
          git: options.compositionBootstrap.git,
          id: "edition4-composition-bootstrap",
        })]),
    renderer,
  ];
  let ordinal = 0;
  const nextId = (kind: string) => `edition4-durable-answer-${kind}-${ordinal += 1}` as ArtifactId;
  for (let steps = 0; steps < 500; steps += 1) {
    const view = await options.engine.inspect(runId);
    if (view.status === "complete") {
      return { runId, view };
    }
    const offered = view.offers.filter((offer) => offer.status === "offered");
    const executableOffer = offered.find((offer) =>
      offer.role === "composition_bootstrap" ||
      offer.role === "measure_edition" ||
      offer.role === "render",
    );
    if (executableOffer !== undefined) {
      const result = await executeAvailableWork(
        options.engine,
        runId,
        executors,
        new AbortController().signal,
      );
      if (result.failed.length > 0 || result.answered.length === 0) {
        const after = await options.engine.inspect(runId);
        const actor = after.actors.find((candidate) => candidate.id === executableOffer.actorId);
        const context = actor?.context as JsonObject | undefined;
        const failure = typeof context?.lastFailure === "string"
          ? `: ${context.lastFailure}`
          : "";
        throw new Error(`Edition 4 executor did not answer ${executableOffer.role}${failure}`);
      }
      continue;
    }
    const offer = offered.find((candidate) => candidate.role !== "close_collection")
      ?? offered.find((candidate) => candidate.role === "close_collection");
    if (offer === undefined) {
      throw new Error(`Edition 4 durable driver stopped at ${view.status}`);
    }
    if (offer.role === "visual_review" && options.approveVisualReview !== true) {
      return { runId, view };
    }
    if (offer.role === "release_approval" && options.approveRelease !== true) {
      return { runId, view };
    }
    const response = await answerForOffer(
      options.engine,
      offer,
      fixture?.productionPlan ?? options.productionPlan,
      nextId,
    );
    const claim = await options.engine.claim(offer.id, workerFor(offer));
    await options.engine.answer(claim, {
      contractVersion: offer.contractVersion,
      result: response.result,
      artifacts: response.artifacts,
    });
  }
  throw new Error("Edition 4 durable driver exceeded its offer budget");
}

async function answerForOffer(
  engine: RunEngine,
  offer: WorkOfferView,
  productionPlan: JsonObject | undefined,
  nextId: (kind: string) => ArtifactId,
): Promise<{ readonly result: JsonObject; readonly artifacts: readonly AnswerArtifact[] }> {
  const artifact = (kind: string, value: JsonObject = { fixture: "edition4-durable" }): AnswerArtifact => ({
    id: nextId(kind),
    kind,
    schemaVersion: "edition4-durable/1",
    mediaType: "application/json",
    payload: { kind: "json", value },
  });
  switch (offer.role) {
    case "capture_source":
      return { result: { status: "complete" }, artifacts: [artifact("raw_source_bundle"), artifact("raw_evidence"), artifact("source_metadata")] };
    case "extract_source":
      return { result: { status: "complete" }, artifacts: [artifact("source_extraction")] };
    case "review_source":
      return { result: { decision: "approved" }, artifacts: [artifact("source_review_decision")] };
    case "close_collection":
      return { result: { choice: "close" }, artifacts: [artifact("collection_decision")] };
    case "plan_edition":
      if (productionPlan === undefined) {
        throw new Error("cannot answer a planning offer while resuming Edition 4");
      }
      return { result: { choice: "approve", productionPlan }, artifacts: [artifact("edition_plan", productionPlan)] };
    case "measure_article":
      return { result: { fits: true, openerFits: true, pageCount: 1 }, artifacts: [artifact("article_measurement")] };
    case "worth":
    case "mechanics":
    case "evidence":
    case "shape":
    case "teaching":
    case "craft":
      return { result: { decision: "pass" }, artifacts: [] };
    case "editorial_writer":
      return { result: { status: "complete" }, artifacts: [artifact("editorial_manuscript")] };
    case "edition_review":
      return { result: { decision: "approved" }, artifacts: [artifact("edition_review")] };
    case "translation_writer":
      return { result: { status: "complete" }, artifacts: [artifact("translation_bundle")] };
    case "language_review":
      return { result: { decision: "approved" }, artifacts: [artifact("language_review")] };
    case "language_fit":
      return { result: { fits: true, pageCount: 1 }, artifacts: [artifact("language_measurement")] };
    case "render_inspection": {
      const renderArtifacts = renderArtifactsForOffer(offer);
      const preflight = await artifactsOfKind(engine, renderArtifacts, "printer_preflight");
      return { result: { result: "pass", renderArtifactIds: renderArtifacts, printerPreflightArtifactIds: preflight, studioReady: false }, artifacts: [artifact("render_inspection")] };
    }
    case "visual_review":
      return { result: { decision: "approved", renderArtifactIds: renderArtifactsForOffer(offer) }, artifacts: [artifact("visual_review_decision")] };
    case "durable_checkpoint": {
      throw new Error(
        "Edition 4 durable checkpoints require a configured DurableCheckpointExecutor",
      );
    }
    case "release_approval": {
      const request = JSON.parse(await engine.readText(offer.taskArtifactId)) as {
        readonly publicationArtifactId: ArtifactId;
        readonly sourceArtifactIds: readonly ArtifactId[];
      };
      return { result: { choice: "approve", publicationArtifactId: request.publicationArtifactId, sourceArtifactIds: request.sourceArtifactIds }, artifacts: [artifact("release_decision")] };
    }
    case "editor_decision":
      return { result: { choice: "accept" }, artifacts: [artifact("editor_decision")] };
    default:
      throw new Error(`Edition 4 durable driver cannot answer ${offer.role}`);
  }
}

function renderArtifactsForOffer(
  offer: WorkOfferView,
): readonly ArtifactId[] {
  // RenderMachine is the authority for this sequence. Inspection inputs are
  // [manifest, printer profile, ...exact render outputs, measurement], while
  // visual-review inputs are [request, manifest, ...exact render outputs,
  // inspection]. Keep auxiliary review artifacts in the identity too.
  return offer.inputArtifacts.slice(2, -1);
}

async function artifactsOfKind(
  engine: RunEngine,
  artifactIds: readonly ArtifactId[],
  kind: string,
): Promise<readonly ArtifactId[]> {
  const artifacts = await Promise.all(artifactIds.map((id) => engine.readArtifact(id)));
  return artifacts.filter((item) => item.artifact.kind === kind).map((item) => item.artifact.id);
}

function workerFor(offer: WorkOfferView): WorkerIdentity {
  const human = offer.allowedWorkerCapabilities.includes("human");
  return {
    principalId: `edition4-durable-${offer.role}-${offer.id}`,
    authority: human ? "human" : offer.allowedWorkerCapabilities.includes("text_model") ? "model" : "tool",
    capabilities: [
      ...offer.allowedWorkerCapabilities,
      ...(offer.role === "review_source" ? ["source_access" as const] : []),
    ],
  };
}

function frozenKind(kind: string): string {
  if (kind === "article") return "article_manuscript";
  if (kind === "editorial") return "editorial_manuscript";
  if (kind === "translation") return "translation_bundle";
  return kind;
}

function textSeed(id: ArtifactId, text: string, kind: string): ArtifactSeed {
  return { id, kind, schemaVersion: "edition4-durable/1", mediaType: "text/plain", origin: "imported", payload: { kind: "text", text } };
}

function jsonSeed(
  id: ArtifactId,
  value: JsonObject,
  kind: string,
  parents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[] = [],
): ArtifactSeed {
  return { id, kind, schemaVersion: "edition4-durable/1", mediaType: "application/json", origin: "imported", payload: { kind: "json", value }, parents };
}

function modelPolicy() {
  return { default: { adapter: "edition4-fixture", model: "committed-artifacts" } } as const;
}

function mapping(value: unknown): Mapping {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("expected mapping");
  return value as Mapping;
}

function mappings(value: unknown, label: string): readonly Mapping[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be a list`);
  return value.map(mapping);
}

function strings(value: unknown, label: string): readonly string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item)) throw new Error(`${label} must be a string list`);
  return value as readonly string[];
}

function required(value: Mapping, key: string): string {
  const candidate = value[key];
  if (typeof candidate !== "string" || !candidate) throw new Error(`${key} must be a non-empty string`);
  return candidate;
}
