import { z } from "zod";

import type { ArtifactId } from "./ids.ts";
import {
  ARTICLE_LENSES,
  type ArticleRunSpec,
  type EditionRunSpec,
  type RunSpec,
  type SourceRunSpec,
  type SubmitLeadRequest,
} from "./run.ts";
import type { InputRevisionRef } from "../durable/types.ts";

const nonEmpty = z.string().trim().min(1);
const artifactId = nonEmpty;

const jsonObject = z.record(z.string(), z.json());

const artifactParentSchema = z
  .object({
    artifactId,
    relation: nonEmpty,
  })
  .strict();

const artifactPayloadSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("bytes"), dataBase64: z.string() }).strict(),
  z.object({ kind: z.literal("file"), path: nonEmpty }).strict(),
  z.object({ kind: z.literal("json"), value: z.json() }).strict(),
  z.object({ kind: z.literal("text"), text: z.string() }).strict(),
]);

const artifactSeedSchema = z
  .object({
    id: artifactId,
    kind: nonEmpty,
    schemaVersion: nonEmpty,
    mediaType: nonEmpty,
    origin: z.enum(["human", "imported", "machine", "model", "subprocess"]),
    payload: artifactPayloadSchema,
    parents: z.array(artifactParentSchema).optional(),
    metadata: jsonObject.optional(),
    supersedes: artifactId.optional(),
  })
  .strict();

const modelChoiceSchema = z
  .object({
    adapter: nonEmpty,
    model: nonEmpty,
    reasoningEffort: nonEmpty.optional(),
    settings: jsonObject.optional(),
  })
  .strict();

const modelPolicySchema = z
  .object({
    default: modelChoiceSchema,
    roles: z.record(z.string().min(1), modelChoiceSchema).optional(),
  })
  .strict();

const lensSchema = z.enum(ARTICLE_LENSES);

const articlePolicySchema = z
  .object({
    maxIterations: z.number().int().nonnegative(),
    maximumReaderPages: z.number().int().positive().max(7),
    teaching: z.enum(["applicable", "not_applicable"]),
    enabledLenses: z.array(lensSchema),
    blockingLenses: z.array(lensSchema),
  })
  .strict();

const articleAttributionSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("source_author"),
      byline: nonEmpty,
      sourceAuthors: z.array(nonEmpty).min(1),
      sourceIds: z.array(nonEmpty).min(1),
    })
    .strict(),
  z
    .object({
      kind: z.literal("magazine"),
      byline: nonEmpty,
    })
    .strict(),
]);

const articleSchema = z
  .object({
    articleId: nonEmpty,
    contentMode: z.enum([
      "faithful_edit",
      "faithful_synthesis",
      "original_synthesis",
    ]),
    attribution: articleAttributionSchema,
    editionContext: artifactId.optional(),
    articleBrief: artifactId,
    sources: z.array(artifactId).min(1),
    sourceApprovalArtifacts: z.array(artifactId),
    writerPrompt: artifactId,
    contentModeArtifact: artifactId.optional(),
    attributionArtifact: artifactId.optional(),
    editorialPolicyArtifact: artifactId.optional(),
    modelPolicyArtifact: artifactId.optional(),
    judgePrompts: z
      .object({
        worth: artifactId.optional(),
        mechanics: artifactId.optional(),
        evidence: artifactId.optional(),
        shape: artifactId.optional(),
        teaching: artifactId.optional(),
        craft: artifactId.optional(),
      })
      .strict(),
    writingRules: artifactId,
    measurementProfileArtifact: artifactId.optional(),
    measurementInputArtifacts: z.array(artifactId).optional(),
    initialManuscript: artifactId.optional(),
    policy: articlePolicySchema,
    modelPolicy: modelPolicySchema,
  })
  .strict();

const sourceSchema = z
  .object({
    sourceId: nonEmpty,
    leadArtifact: artifactId,
    captureProfileArtifact: artifactId.optional(),
    captureInputArtifacts: z.array(artifactId).optional(),
    rawBundleArtifact: artifactId.optional(),
    rawEvidenceArtifacts: z.array(artifactId).optional(),
    extractionArtifact: artifactId.optional(),
    metadataArtifact: artifactId.optional(),
    approvalArtifact: artifactId.optional(),
  })
  .strict();

const submitLeadSchema = z
  .object({
    source: sourceSchema,
    artifacts: z.array(artifactSeedSchema),
  })
  .strict();

const editorialSchema = z
  .object({
    editorialId: nonEmpty,
    briefArtifact: artifactId,
    writingRules: artifactId,
    articleArtifacts: z.array(artifactId).optional(),
    initialManuscript: artifactId.optional(),
    modelPolicy: modelPolicySchema,
  })
  .strict();

const translationSchema = z
  .object({
    language: nonEmpty,
    sourceLanguage: nonEmpty,
    englishArtifacts: z.array(artifactId),
    promptArtifact: artifactId,
    measurementProfileArtifact: artifactId.optional(),
    measurementInputArtifacts: z.array(artifactId).optional(),
    initialTranslationArtifacts: z.array(artifactId).optional(),
    maximumReaderPages: z.number().int().positive(),
    modelPolicy: modelPolicySchema,
  })
  .strict();

const dependencySchema = z
  .object({
    articleIds: z.array(nonEmpty),
    editorial: z.boolean(),
  })
  .strict();

const artSchema = z
  .object({
    key: nonEmpty,
    role: z.enum(["cover", "interior"]),
    artifactId: artifactId.optional(),
    briefArtifact: artifactId,
    required: z.boolean(),
    dependencies: dependencySchema.optional(),
    dependencyArtifacts: z.array(artifactId).optional(),
  })
  .strict();

const runBootstrapRevisionSchema = z
  .object({
    kind: z.literal("run_bootstrap"),
    logicalId: nonEmpty,
    editionId: nonEmpty,
    revisionId: nonEmpty,
  })
  .strict();

const editionExecutionSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("produce") }).strict(),
  z
    .object({
      kind: z.literal("bootstrap_composition"),
      bootstrapRevision: runBootstrapRevisionSchema,
      postRender: z.literal("stop_unreleased"),
    })
    .strict(),
]);

const editionSchema = z
  .object({
    editionId: nonEmpty,
    execution: editionExecutionSchema,
    editionBrief: artifactId,
    planningArtifact: artifactId.optional(),
    sourceAssignmentPolicy: z.enum(["at_least_once", "exactly_once"]).optional(),
    sources: z.array(sourceSchema),
    articles: z.array(articleSchema),
    editorial: editorialSchema,
    translations: z.array(translationSchema),
    art: z.array(artSchema),
    render: z
      .object({
        renderManifestArtifact: artifactId,
        rendererContractVersion: nonEmpty,
        printerProfileArtifact: artifactId.optional(),
        configuredLanguages: z.array(nonEmpty).min(1),
        studioPolicy: z.enum([
          "not_applicable",
          "home_ready_studio_blocked",
          "require_ready_preflight",
        ]),
      })
      .strict(),
    release: z
      .object({
        publicationArtifact: artifactId,
        sourceArtifacts: z.array(artifactId),
        dryRun: z.boolean(),
        target: z.enum(["press", "private", "web"]),
        printerProfileArtifact: artifactId.optional(),
        printerPreflightArtifacts: z.array(artifactId).optional(),
        studioReady: z.boolean().optional(),
      })
      .strict(),
    modelPolicy: modelPolicySchema,
  })
  .strict();

const baseSchema = z
  .object({
    schemaVersion: z.literal(1),
    artifacts: z.array(artifactSeedSchema),
    metadata: jsonObject.optional(),
  })
  .strict();

const runSpecSchema = z.discriminatedUnion("kind", [
  baseSchema.extend({ kind: z.literal("article"), article: articleSchema }).strict(),
  baseSchema.extend({ kind: z.literal("edition"), edition: editionSchema }).strict(),
]);

function addIssue(
  context: z.RefinementCtx,
  path: readonly PropertyKey[],
  message: string,
): void {
  context.addIssue({ code: "custom", path: [...path], message });
}

function assertUnique(
  context: z.RefinementCtx,
  values: readonly string[],
  path: readonly PropertyKey[],
  label: string,
): void {
  const seen = new Set<string>();
  values.forEach((value, index) => {
    if (seen.has(value)) {
      addIssue(context, [...path, index], `${label} must be unique; duplicate ${value}`);
    }
    seen.add(value);
  });
}

function articleReferences(article: ArticleRunSpec): readonly ArtifactId[] {
  return [
    article.editionContext,
    article.articleBrief,
    ...article.sources,
    ...article.sourceApprovalArtifacts,
    article.writerPrompt,
    article.contentModeArtifact,
    article.attributionArtifact,
    article.editorialPolicyArtifact,
    article.modelPolicyArtifact,
    ...Object.values(article.judgePrompts),
    article.writingRules,
    article.measurementProfileArtifact,
    ...(article.measurementInputArtifacts ?? []),
    article.initialManuscript,
  ].filter((value): value is ArtifactId => value !== undefined);
}

function editionArticleReferences(article: ArticleRunSpec): readonly ArtifactId[] {
  const approvals = new Set(article.sourceApprovalArtifacts);
  return articleReferences(article).filter((artifactId) => !approvals.has(artifactId));
}

function validateArticle(
  article: ArticleRunSpec,
  context: z.RefinementCtx,
  path: readonly PropertyKey[],
): void {
  assertUnique(context, article.sources, [...path, "sources"], "article source artifacts");
  assertUnique(
    context,
    article.policy.enabledLenses,
    [...path, "policy", "enabledLenses"],
    "enabled lenses",
  );
  if (
    article.sourceApprovalArtifacts.length !== article.sources.length
  ) {
    addIssue(
      context,
      [...path, "sourceApprovalArtifacts"],
      "source approvals must be ordered one-for-one with sources",
    );
  }
  assertUnique(
    context,
    article.policy.blockingLenses,
    [...path, "policy", "blockingLenses"],
    "blocking lenses",
  );
  const enabled = new Set(article.policy.enabledLenses);
  for (const lens of article.policy.enabledLenses) {
    if (article.judgePrompts[lens] === undefined) {
      addIssue(
        context,
        [...path, "judgePrompts", lens],
        `enabled lens ${lens} requires a prompt artifact`,
      );
    }
  }
  for (const lens of article.policy.blockingLenses) {
    if (!enabled.has(lens)) {
      addIssue(
        context,
        [...path, "policy", "blockingLenses"],
        `blocking lens ${lens} is not enabled`,
      );
    }
  }
  if (!enabled.has("evidence")) {
    addIssue(
      context,
      [...path, "policy", "enabledLenses"],
      "every source-backed article must enable the evidence lens",
    );
  }
  if (
    article.policy.teaching === "not_applicable" &&
    enabled.has("teaching")
  ) {
    addIssue(
      context,
      [...path, "policy", "teaching"],
      "teaching cannot be enabled when it is not applicable",
    );
  }
  const faithful = article.contentMode !== "original_synthesis";
  if (faithful && article.attribution.kind !== "source_author") {
    addIssue(
      context,
      [...path, "attribution"],
      `${article.contentMode} requires source-author attribution`,
    );
  }
  if (!faithful && article.attribution.kind !== "magazine") {
    addIssue(
      context,
      [...path, "attribution"],
      "original_synthesis must be labeled as magazine-authored",
    );
  }
  if (article.attribution.kind === "source_author") {
    assertUnique(
      context,
      article.attribution.sourceIds,
      [...path, "attribution", "sourceIds"],
      "attributed source IDs",
    );
    assertUnique(
      context,
      article.attribution.sourceAuthors,
      [...path, "attribution", "sourceAuthors"],
      "source authors",
    );
  }
  if (
    (article.measurementProfileArtifact === undefined) !==
    (article.measurementInputArtifacts === undefined)
  ) {
    addIssue(
      context,
      [...path, "measurementProfileArtifact"],
      "article measurement profile and measurement inputs must be supplied together",
    );
  }
  assertUnique(
    context,
    article.measurementInputArtifacts ?? [],
    [...path, "measurementInputArtifacts"],
    "article measurement inputs",
  );
}

function editionReferences(edition: EditionRunSpec): readonly ArtifactId[] {
  return [
    edition.editionBrief,
    edition.planningArtifact,
    ...edition.sources.flatMap((source) => [
      source.leadArtifact,
      source.captureProfileArtifact,
      ...(source.captureInputArtifacts ?? []),
      source.rawBundleArtifact,
      ...(source.rawEvidenceArtifacts ?? []),
      source.extractionArtifact,
      source.metadataArtifact,
      source.approvalArtifact,
    ]),
    // Source approvals for nested articles are not root inputs. The production
    // plan replaces their parse-time placeholders with the exact decisions
    // produced by the collection's source actors before it spawns each article.
    ...edition.articles.flatMap(editionArticleReferences),
    edition.editorial.briefArtifact,
    edition.editorial.writingRules,
    ...(edition.editorial.articleArtifacts ?? []),
    edition.editorial.initialManuscript,
    ...edition.translations.flatMap((translation) => [
      ...translation.englishArtifacts,
      translation.promptArtifact,
      translation.measurementProfileArtifact,
      ...(translation.measurementInputArtifacts ?? []),
      ...(translation.initialTranslationArtifacts ?? []),
    ]),
    ...edition.art.flatMap((art) => [
      art.artifactId,
      art.briefArtifact,
      ...(art.dependencyArtifacts ?? []),
    ]),
    edition.render.renderManifestArtifact,
    edition.render.printerProfileArtifact,
    edition.release.publicationArtifact,
    ...edition.release.sourceArtifacts,
    edition.release.printerProfileArtifact,
    ...(edition.release.printerPreflightArtifacts ?? []),
  ].filter((value): value is ArtifactId => value !== undefined);
}

/**
 * Immutable input revisions are accounted for separately from engine
 * artifacts. In particular, the bootstrap selector is not an artifact ID and
 * must never be resolved through the artifact repository seam.
 */
export function editionInputRevisionReferences(
  edition: EditionRunSpec,
): readonly InputRevisionRef[] {
  return edition.execution.kind === "bootstrap_composition"
    ? [edition.execution.bootstrapRevision]
    : [];
}

function validateEdition(edition: EditionRunSpec, context: z.RefinementCtx): void {
  assertUnique(context, edition.sources.map((source) => source.sourceId), ["edition", "sources"], "source IDs");
  assertUnique(context, edition.articles.map((article) => article.articleId), ["edition", "articles"], "article IDs");
  assertUnique(context, edition.art.map((art) => art.key), ["edition", "art"], "art keys");
  assertUnique(
    context,
    edition.translations.map((translation) => translation.language),
    ["edition", "translations"],
    "translation languages",
  );
  assertUnique(
    context,
    edition.render.configuredLanguages,
    ["edition", "render", "configuredLanguages"],
    "configured languages",
  );

  const configured = new Set(edition.render.configuredLanguages);
  const translations = new Set(edition.translations.map((item) => item.language));
  if (!configured.has("en")) {
    addIssue(context, ["edition", "render", "configuredLanguages"], "English (en) must be configured");
  }
  const expectedTranslations = new Set(
    edition.render.configuredLanguages.filter((language) => language !== "en"),
  );
  if (
    translations.size !== expectedTranslations.size ||
    [...translations].some((language) => !expectedTranslations.has(language))
  ) {
    addIssue(
      context,
      ["edition", "translations"],
      "translations must name every configured non-English language exactly once",
    );
  }
  edition.translations.forEach((translation, index) => {
    if (translation.sourceLanguage !== "en") {
      addIssue(
        context,
        ["edition", "translations", index, "sourceLanguage"],
        "translation sourceLanguage must be en",
      );
    }
    if (translation.language === "en") {
      addIssue(
        context,
        ["edition", "translations", index, "language"],
        "English is the source edition and must not have a translation actor",
      );
    }
    if (
      (translation.measurementProfileArtifact === undefined) !==
      (translation.measurementInputArtifacts === undefined)
    ) {
      addIssue(
        context,
        ["edition", "translations", index, "measurementProfileArtifact"],
        "translation measurement profile and measurement inputs must be supplied together",
      );
    }
    assertUnique(
      context,
      translation.measurementInputArtifacts ?? [],
      ["edition", "translations", index, "measurementInputArtifacts"],
      "translation measurement inputs",
    );
  });
  if (
    !edition.release.dryRun &&
    edition.release.target === "press" &&
    (edition.render.printerProfileArtifact === undefined ||
      edition.render.studioPolicy !== "require_ready_preflight")
  ) {
    addIssue(
      context,
      ["edition", "render", "printerProfileArtifact"],
      "a non-dry press release requires a named printer profile and ready-preflight policy",
    );
  }
  if (
    edition.release.target !== "press" &&
    edition.render.studioPolicy === "require_ready_preflight"
  ) {
    addIssue(
      context,
      ["edition", "render", "studioPolicy"],
      "ready printer preflight may only authorize a press release target",
    );
  }

  const articleIds = new Set(edition.articles.map((article) => article.articleId));
  edition.art.forEach((art, artIndex) => {
    assertUnique(
      context,
      art.dependencies?.articleIds ?? [],
      ["edition", "art", artIndex, "dependencies", "articleIds"],
      "art dependency article IDs",
    );
    for (const articleId of art.dependencies?.articleIds ?? []) {
      if (!articleIds.has(articleId)) {
        addIssue(
          context,
          ["edition", "art", artIndex, "dependencies", "articleIds"],
          `art depends on unknown article ${articleId}`,
        );
      }
    }
  });

  const extractionToSource = new Map<ArtifactId, string>();
  edition.sources.forEach((source, sourceIndex) => {
    assertUnique(
      context,
      source.rawEvidenceArtifacts ?? [],
      ["edition", "sources", sourceIndex, "rawEvidenceArtifacts"],
      "raw evidence artifacts",
    );
    if (
      source.approvalArtifact !== undefined &&
      (source.rawBundleArtifact === undefined ||
        (source.rawEvidenceArtifacts?.length ?? 0) === 0 ||
        source.extractionArtifact === undefined ||
        source.metadataArtifact === undefined)
    ) {
      addIssue(
        context,
        ["edition", "sources", sourceIndex, "approvalArtifact"],
        "an approved source requires raw bundle, raw evidence, extraction, and metadata artifacts",
      );
    }
    if (source.extractionArtifact !== undefined) {
      extractionToSource.set(source.extractionArtifact, source.sourceId);
    }
  });
  const assignmentCounts = new Map<string, number>(
    edition.sources.map((source) => [source.sourceId, 0]),
  );
  edition.articles.forEach((article, articleIndex) => {
    validateArticle(article, context, ["edition", "articles", articleIndex]);
    const assignedSourceIds = article.sources.flatMap((sourceArtifact, sourceIndex) => {
      const sourceId = extractionToSource.get(sourceArtifact);
      if (sourceId === undefined) {
        addIssue(
          context,
          ["edition", "articles", articleIndex, "sources", sourceIndex],
          `article source ${sourceArtifact} is not a prepared source extraction`,
        );
        return [];
      }
      assignmentCounts.set(sourceId, (assignmentCounts.get(sourceId) ?? 0) + 1);
      return [sourceId];
    });
    if (article.attribution.kind === "source_author") {
      const actual = new Set(assignedSourceIds);
      const attributed = new Set(article.attribution.sourceIds);
      if (
        actual.size !== attributed.size ||
        [...actual].some((sourceId) => !attributed.has(sourceId))
      ) {
        addIssue(
          context,
          ["edition", "articles", articleIndex, "attribution", "sourceIds"],
          "attributed source IDs must exactly match the assigned source extractions",
        );
      }
    }
  });
  if (edition.articles.length > 0) {
    for (const [sourceId, count] of assignmentCounts) {
      if (count === 0) {
        addIssue(
          context,
          ["edition", "articles"],
          `prepared source ${sourceId} is not assigned to an article`,
        );
      }
      if (edition.sourceAssignmentPolicy === "exactly_once" && count !== 1) {
        addIssue(
          context,
          ["edition", "articles"],
          `source ${sourceId} must be assigned exactly once, got ${count}`,
        );
      }
    }
  }
}

export const strictRunSpecSchema = runSpecSchema.superRefine((spec, context) => {
  assertUnique(context, spec.artifacts.map((artifact) => artifact.id), ["artifacts"], "artifact IDs");
  const artifacts = new Map(spec.artifacts.map((artifact) => [artifact.id, artifact]));
  const validateMeasurementProfile = (
    profileId: string | undefined,
    maximumReaderPages: number,
    path: readonly PropertyKey[],
  ): void => {
    if (profileId === undefined) {
      return;
    }
    const profile = artifacts.get(profileId);
    if (profile?.payload.kind !== "json") {
      addIssue(context, path, "measurement profile must be an immutable JSON artifact");
      return;
    }
    const value = profile.payload.value;
    if (
      typeof value !== "object" ||
      value === null ||
      Array.isArray(value) ||
      value.maximumReaderPages !== maximumReaderPages
    ) {
      addIssue(
        context,
        path,
        `measurement profile maximumReaderPages must equal policy cap ${maximumReaderPages}`,
      );
    }
  };
  if (spec.kind === "article") {
    validateArticle(spec.article as unknown as ArticleRunSpec, context, ["article"]);
    validateMeasurementProfile(
      spec.article.measurementProfileArtifact,
      spec.article.policy.maximumReaderPages,
      ["article", "measurementProfileArtifact"],
    );
  } else {
    validateEdition(spec.edition as unknown as EditionRunSpec, context);
    spec.edition.articles.forEach((article, index) =>
      validateMeasurementProfile(
        article.measurementProfileArtifact,
        article.policy.maximumReaderPages,
        ["edition", "articles", index, "measurementProfileArtifact"],
      )
    );
    spec.edition.translations.forEach((translation, index) => {
      const profileId = translation.measurementProfileArtifact;
      if (profileId === undefined) {
        return;
      }
      const profile = artifacts.get(profileId);
      const value = profile?.payload.kind === "json" ? profile.payload.value : undefined;
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        addIssue(
          context,
          ["edition", "translations", index, "measurementProfileArtifact"],
          "translation measurement profile must be an immutable JSON artifact",
        );
        return;
      }
      const pieces = value.translatedPieces;
      if (
        !Array.isArray(pieces) ||
        pieces.some(
          (piece) =>
            typeof piece !== "object" ||
            piece === null ||
            Array.isArray(piece) ||
            typeof piece.maximumReaderPages !== "number" ||
            piece.maximumReaderPages > 7 ||
            piece.maximumReaderPages > translation.maximumReaderPages,
        )
      ) {
        addIssue(
          context,
          ["edition", "translations", index, "measurementProfileArtifact"],
          "translation measurement piece caps must be present and no greater than seven or the translation cap",
        );
      }
    });
  }
});

export function parseRunSpec(value: unknown): RunSpec {
  return strictRunSpecSchema.parse(value) as unknown as RunSpec;
}

export function parseSourceRunSpec(value: unknown): SourceRunSpec {
  return sourceSchema.parse(value) as unknown as SourceRunSpec;
}

export function parseSubmitLeadRequest(value: unknown): SubmitLeadRequest {
  return submitLeadSchema.parse(value) as unknown as SubmitLeadRequest;
}

export class RunSpecReferenceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RunSpecReferenceError";
  }
}

/**
 * Resolves immutable references at the repository seam. Forked runs may reuse
 * artifacts already committed by an ancestor, while a fresh start accepts only
 * its seeds. The durable engine supplies the repository lookup.
 */
export function assertRunSpecArtifactReferences(
  spec: RunSpec,
  artifactExists: (artifactId: ArtifactId) => boolean = () => false,
): void {
  const seeded = new Set(spec.artifacts.map((artifact) => artifact.id));
  const known = (artifactId: ArtifactId): boolean =>
    seeded.has(artifactId) || artifactExists(artifactId);
  for (const artifact of spec.artifacts) {
    for (const parent of artifact.parents ?? []) {
      if (!known(parent.artifactId)) {
        throw new RunSpecReferenceError(
          `artifact ${artifact.id} names unknown parent ${parent.artifactId}`,
        );
      }
    }
    if (artifact.supersedes !== undefined && !known(artifact.supersedes)) {
      throw new RunSpecReferenceError(
        `artifact ${artifact.id} supersedes unknown artifact ${artifact.supersedes}`,
      );
    }
  }
  const references = spec.kind === "article"
    ? articleReferences(spec.article)
    : editionReferences(spec.edition);
  for (const reference of references) {
    if (!known(reference)) {
      throw new RunSpecReferenceError(
        `${spec.kind} run references unknown artifact ${reference}`,
      );
    }
  }
}
