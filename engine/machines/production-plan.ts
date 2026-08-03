import type {
  ApprovedProductionPlan,
  ArticleRunSpec,
  ArtifactId,
  EditionRunSpec,
  ModelChoice,
  ModelPolicy,
  RegisteredArtSpec,
  SourceAssignmentPolicy,
  TranslationRunSpec,
} from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";

export type ReadySourceExtraction = {
  readonly sourceId: string;
  readonly extractionArtifactId: ArtifactId;
  readonly approvalArtifactId?: ArtifactId;
};

export type ResolvedProductionPlan = {
  readonly sourceAssignmentPolicy: SourceAssignmentPolicy;
  readonly articles: readonly ArticleRunSpec[];
  readonly art: readonly RegisteredArtSpec[];
  readonly translations: readonly TranslationRunSpec[];
};

export class ProductionPlanError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProductionPlanError";
  }
}

function isPreplannedArticle(
  article: EditionRunSpec["articles"][number],
): article is import("../contracts/index.ts").PreplannedArticleRunSpec {
  return "sourceIds" in article;
}

type PlannedModelPolicy = ApprovedProductionPlan["articles"][number]["modelPolicy"];
type PlannedModelChoice = PlannedModelPolicy["default"];

function resolveModelChoice(choice: PlannedModelChoice): ModelChoice {
  const { reasoningEffort, settings, ...required } = choice;
  return {
    ...required,
    ...(reasoningEffort === undefined ? {} : { reasoningEffort }),
    ...(settings === undefined ? {} : { settings }),
  } as ModelChoice;
}

function resolveModelPolicy(policy: PlannedModelPolicy): ModelPolicy {
  return {
    default: resolveModelChoice(policy.default),
    ...(policy.roles === undefined
      ? {}
      : {
          roles: Object.fromEntries(
            Object.entries(policy.roles).map(([role, choice]) => [
              role,
              resolveModelChoice(choice),
            ]),
          ),
        }),
  };
}

function uniqueBy<Value>(
  values: readonly Value[],
  key: (value: Value) => string,
  label: string,
): void {
  const seen = new Set<string>();
  for (const value of values) {
    const candidate = key(value);
    if (seen.has(candidate)) {
      throw new ProductionPlanError(`Production plan repeats ${label} ${candidate}`);
    }
    seen.add(candidate);
  }
}

function readySourceMap(
  spec: EditionRunSpec,
  readySources: readonly ReadySourceExtraction[],
): ReadonlyMap<string, ReadySourceExtraction> {
  uniqueBy(readySources, (source) => source.sourceId, "ready source");
  const declared = new Set(spec.sources.map((source) => source.sourceId));
  for (const source of readySources) {
    if (!declared.has(source.sourceId)) {
      throw new ProductionPlanError(`Ready source ${source.sourceId} is not declared`);
    }
  }
  const ready = new Map(readySources.map((source) => [source.sourceId, source] as const));
  const missing = spec.sources
    .map((source) => source.sourceId)
    .filter((sourceId) => !ready.has(sourceId));
  if (missing.length > 0) {
    throw new ProductionPlanError(
      `Production plan cannot run before source extraction is ready: ${missing.join(", ")}`,
    );
  }
  return ready;
}

function validateAssignments(
  policy: SourceAssignmentPolicy,
  sourceIds: readonly string[],
  assignedSourceIds: readonly string[],
): void {
  const counts = new Map<string, number>(
    sourceIds.map((sourceId) => [sourceId, 0] as const),
  );
  for (const sourceId of assignedSourceIds) {
    const previous = counts.get(sourceId);
    if (previous === undefined) {
      throw new ProductionPlanError(`Production plan uses unknown source ${sourceId}`);
    }
    counts.set(sourceId, previous + 1);
  }
  const invalid = [...counts.entries()].filter(([, count]) =>
    policy === "exactly_once" ? count !== 1 : count < 1,
  );
  if (invalid.length > 0) {
    const expectation = policy === "exactly_once" ? "exactly once" : "at least once";
    throw new ProductionPlanError(
      `Every ready source must be assigned ${expectation}: ${invalid
        .map(([sourceId, count]) => `${sourceId} (${count})`)
        .join(", ")}`,
    );
  }
}

function validatePlannedArticle(
  article: ApprovedProductionPlan["articles"][number],
): void {
  uniqueBy(
    article.policy.enabledLenses,
    (lens) => lens,
    `enabled lens in article ${article.articleId}`,
  );
  uniqueBy(
    article.policy.blockingLenses,
    (lens) => lens,
    `blocking lens in article ${article.articleId}`,
  );
  const enabled = new Set(article.policy.enabledLenses);
  for (const lens of article.policy.enabledLenses) {
    if (article.judgePrompts[lens] === undefined) {
      throw new ProductionPlanError(
        `Article ${article.articleId} enables ${lens} without a judge prompt`,
      );
    }
  }
  for (const lens of article.policy.blockingLenses) {
    if (!enabled.has(lens)) {
      throw new ProductionPlanError(
        `Article ${article.articleId} blocks on disabled lens ${lens}`,
      );
    }
  }
  if (!enabled.has("evidence")) {
    throw new ProductionPlanError(
      `Source-backed article ${article.articleId} must enable evidence review`,
    );
  }
  if (article.policy.teaching === "not_applicable" && enabled.has("teaching")) {
    throw new ProductionPlanError(
      `Article ${article.articleId} enables teaching while declaring it not applicable`,
    );
  }
  if (
    article.contentMode === "original_synthesis" &&
    article.attribution.kind !== "magazine"
  ) {
    throw new ProductionPlanError(
      `Original synthesis ${article.articleId} must be magazine-attributed`,
    );
  }
  if (
    article.contentMode !== "original_synthesis" &&
    article.attribution.kind !== "source_author"
  ) {
    throw new ProductionPlanError(
      `${article.contentMode} article ${article.articleId} must retain source-author attribution`,
    );
  }
  if (article.attribution.kind === "source_author") {
    uniqueBy(
      article.attribution.sourceIds,
      (sourceId) => sourceId,
      `attributed source in article ${article.articleId}`,
    );
    const assigned = new Set(article.sourceIds);
    const attributed = new Set(article.attribution.sourceIds);
    if (
      assigned.size !== attributed.size ||
      [...assigned].some((sourceId) => !attributed.has(sourceId))
    ) {
      throw new ProductionPlanError(
        `Article ${article.articleId} attribution must exactly match its source assignments`,
      );
    }
  }
}

export function resolveApprovedProductionPlan(
  plan: ApprovedProductionPlan,
  spec: EditionRunSpec,
  readySources: readonly ReadySourceExtraction[],
): ResolvedProductionPlan {
  const sourceArtifacts = readySourceMap(spec, readySources);
  uniqueBy(plan.articles, (article) => article.articleId, "article");
  uniqueBy(plan.art, (art) => art.key, "art key");
  uniqueBy(
    plan.translations,
    (translation) => `${translation.language}:${translation.pieceKind}:${translation.pieceId}`,
    "translation language and piece",
  );

  const articles = plan.articles.map((planned) => {
    validatePlannedArticle(planned);
    uniqueBy(
      planned.sourceIds,
      (sourceId) => sourceId,
      `source in article ${planned.articleId}`,
    );
    const {
      sourceIds,
      editionContext,
      contentModeArtifact,
      attributionArtifact,
      editorialPolicyArtifact,
      modelPolicyArtifact,
      initialManuscript,
      measurementProfileArtifact,
      measurementInputArtifacts,
      ...article
    } = planned;
    return {
      ...article,
      ...(editionContext === undefined
        ? {}
        : { editionContext: editionContext as ArtifactId }),
      articleBrief: article.articleBrief as ArtifactId,
      writerPrompt: article.writerPrompt as ArtifactId,
      ...(contentModeArtifact === undefined
        ? {}
        : { contentModeArtifact: contentModeArtifact as ArtifactId }),
      ...(attributionArtifact === undefined
        ? {}
        : { attributionArtifact: attributionArtifact as ArtifactId }),
      ...(editorialPolicyArtifact === undefined
        ? {}
        : { editorialPolicyArtifact: editorialPolicyArtifact as ArtifactId }),
      ...(modelPolicyArtifact === undefined
        ? {}
        : { modelPolicyArtifact: modelPolicyArtifact as ArtifactId }),
      judgePrompts: article.judgePrompts as ArticleRunSpec["judgePrompts"],
      writingRules: article.writingRules as ArtifactId,
      modelPolicy: resolveModelPolicy(article.modelPolicy),
      ...(initialManuscript === undefined
        ? {}
        : { initialManuscript: initialManuscript as ArtifactId }),
      ...(measurementProfileArtifact === undefined
        ? {}
        : { measurementProfileArtifact: measurementProfileArtifact as ArtifactId }),
      ...(measurementInputArtifacts === undefined
        ? {}
        : {
            measurementInputArtifacts: measurementInputArtifacts.map(
              (artifactId) => artifactId as ArtifactId,
            ),
          }),
      sources: sourceIds.map((sourceId) => {
        const source = sourceArtifacts.get(sourceId);
        if (source === undefined) {
          throw new ProductionPlanError(`Production plan uses unknown source ${sourceId}`);
        }
        return source.extractionArtifactId;
      }),
      sourceApprovalArtifacts: sourceIds.map((sourceId) => {
        const approval = sourceArtifacts.get(sourceId)?.approvalArtifactId;
        if (approval === undefined) {
          throw new ProductionPlanError(
            `Production plan uses source ${sourceId} without a human review approval`,
          );
        }
        return approval;
      }),
    };
  });
  validateAssignments(
    plan.sourceAssignmentPolicy,
    [...sourceArtifacts.keys()],
    plan.articles.flatMap((article) => article.sourceIds),
  );

  const art = plan.art.map((planned) => {
    for (const articleId of planned.dependencies?.articleIds ?? []) {
      if (!articles.some((article) => article.articleId === articleId)) {
        throw new ProductionPlanError(
          `Art ${planned.key} depends on unknown planned article ${articleId}`,
        );
      }
    }
    const { artifactId, dependencies, ...artSpec } = planned;
    return {
      ...artSpec,
      ...(artifactId === undefined
        ? {}
        : { artifactId: artifactId as ArtifactId }),
      ...(dependencies === undefined ? {} : { dependencies }),
      briefArtifact: planned.briefArtifact as ArtifactId,
    };
  });

  const translations = plan.translations.map((planned) => {
    const {
      initialTranslationArtifacts,
      measurementProfileArtifact,
      measurementInputArtifacts,
      inputRevisions,
      ...translation
    } = planned;
    return {
      ...translation,
      englishArtifacts: planned.englishArtifacts.map(
        (artifactId) => artifactId as ArtifactId,
      ),
      promptArtifact: planned.promptArtifact as ArtifactId,
      modelPolicy: resolveModelPolicy(planned.modelPolicy),
      ...(initialTranslationArtifacts === undefined
        ? {}
        : {
            initialTranslationArtifacts: initialTranslationArtifacts.map(
              (artifactId) => artifactId as ArtifactId,
            ),
          }),
      ...(measurementProfileArtifact === undefined
        ? {}
        : { measurementProfileArtifact: measurementProfileArtifact as ArtifactId }),
      ...(measurementInputArtifacts === undefined
        ? {}
        : {
            measurementInputArtifacts: measurementInputArtifacts.map(
              (artifactId) => artifactId as ArtifactId,
            ),
          }),
      ...(inputRevisions === undefined
        ? {}
        : { inputRevisions: inputRevisions as readonly InputRevisionRef[] }),
    };
  });
  const configuredTranslations = new Set(
    spec.render.configuredLanguages.filter((language) => language !== "en"),
  );
  const plannedTranslationLanguages = new Set(translations.map((translation) => translation.language));
  for (const translation of translations) {
    if (translation.sourceLanguage !== "en") {
      throw new ProductionPlanError(
        `Translation ${translation.language} must use English as its source language`,
      );
    }
  }
  const missingLanguages = [...configuredTranslations].filter(
    (language) => !plannedTranslationLanguages.has(language),
  );
  const unknownLanguages = [...plannedTranslationLanguages].filter(
    (language) => !configuredTranslations.has(language),
  );
  if (missingLanguages.length > 0 || unknownLanguages.length > 0) {
    throw new ProductionPlanError(
      `Planned translations must match configured languages; missing ${
        missingLanguages.join(", ") || "none"
      }, unknown ${unknownLanguages.join(", ") || "none"}`,
    );
  }
  for (const language of configuredTranslations) {
    const requiredPieces = [
      ...articles.map((article) => `article:${article.articleId}`),
      `editorial:${spec.editorial.editorialId}`,
    ];
    const actualPieces = translations
      .filter((translation) => translation.language === language)
      .map((translation) => `${translation.pieceKind}:${translation.pieceId}`);
    if (actualPieces.length !== requiredPieces.length || requiredPieces.some((piece) => !actualPieces.includes(piece))) {
      throw new ProductionPlanError(
        `Translations for ${language} must contain exactly one actor for every planned article and opening editorial`,
      );
    }
  }

  return {
    sourceAssignmentPolicy: plan.sourceAssignmentPolicy,
    articles,
    art,
    translations,
  };
}

export function resolvePreplannedProduction(
  spec: EditionRunSpec,
  readySources: readonly ReadySourceExtraction[],
): ResolvedProductionPlan {
  const sourceAssignmentPolicy = spec.sourceAssignmentPolicy ?? "at_least_once";
  if (spec.sources.length === 0) {
    const legacyArticles = spec.articles.filter(
      (article): article is ArticleRunSpec => !isPreplannedArticle(article),
    );
    if (legacyArticles.length !== spec.articles.length) {
      throw new ProductionPlanError(
        "Preplanned articles with sourceIds require configured sources",
      );
    }
    return {
      sourceAssignmentPolicy,
      articles: legacyArticles,
      art: spec.art,
      translations: spec.translations,
    };
  }
  const sources = readySourceMap(spec, readySources);
  const sourceIdByDeclaredExtraction = new Map(
    spec.sources.flatMap((source) => source.extractionArtifact === undefined
      ? []
      : [[source.extractionArtifact, source.sourceId] as const]),
  );
  const articles = spec.articles.map((article) => {
      const sourceIds = isPreplannedArticle(article)
        ? article.sourceIds
        : article.sources.map((artifactId) => {
            const sourceId = sourceIdByDeclaredExtraction.get(artifactId);
            if (sourceId === undefined) {
              throw new ProductionPlanError(
                `Preplanned article ${article.articleId} uses an unknown source extraction ${artifactId}`,
              );
            }
            return sourceId;
          });
      const current = sourceIds.map((sourceId) => {
        const ready = sources.get(sourceId);
        if (ready?.approvalArtifactId === undefined) {
          throw new ProductionPlanError(
            `Preplanned article ${article.articleId} uses source ${sourceId} without a current human review approval`,
          );
        }
        return ready;
      });
      const resolvedArticle = isPreplannedArticle(article)
        ? (() => {
            const { sourceIds: _plannedSourceIds, ...value } = article;
            return value;
          })()
        : article;
      return {
        ...resolvedArticle,
        sources: current.map((source) => source.extractionArtifactId),
        sourceApprovalArtifacts: current.map((source) => source.approvalArtifactId!),
      };
    });
  validateAssignments(
    sourceAssignmentPolicy,
    [...sources.keys()],
    spec.articles.flatMap((article) => isPreplannedArticle(article)
      ? article.sourceIds
      : article.sources.map((artifactId) => {
          const sourceId = sourceIdByDeclaredExtraction.get(artifactId);
          if (sourceId === undefined) {
            throw new ProductionPlanError(
              `Preplanned article ${article.articleId} uses an unknown source extraction ${artifactId}`,
            );
          }
          return sourceId;
        })),
  );
  return {
    sourceAssignmentPolicy,
    articles,
    art: spec.art,
    translations: spec.translations,
  };
}
