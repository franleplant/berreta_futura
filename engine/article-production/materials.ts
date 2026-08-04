import type {
  ArtifactId,
  ArticleContentMode,
  ArticleRunSpec,
  JudgeLens,
  ManuscriptRevisionId,
  WorkRole,
} from "../contracts/index.ts";
import type {
  ResolvedArticleProductionProfile,
  ResolvedReviewPlan,
  ReviewCheckDefinition,
} from "../contracts/production-plan.ts";
import type {
  LoopsArticleEntryInput,
  MaterializedWritePipelineInput,
} from "../durable/write-pipeline.ts";

/**
 * The smallest useful provenance label for an article input. The labels are
 * intentionally independent of the input-revision kind. A source capture is
 * evidence, for example, while a prompt is a task even though both are
 * imported immutable payloads.
 */
export type ArticleArtifactClassification =
  | "article_brief"
  | "edition_context"
  | "judge_prompt"
  | "manuscript"
  | "measurement_input"
  | "measurement_profile"
  | "revision_finding"
  | "source"
  | "working_notes"
  | "writer_policy"
  | "writer_prompt"
  | "writer_review_material"
  | "writing_rules";

export type ClassifiedArticleArtifact = {
  readonly artifactId: ArtifactId;
  readonly articleId: string;
  readonly classification: ArticleArtifactClassification;
};

export type ArticleMaterialAccess =
  | "source_aware"
  | "source_blind"
  | "tool"
  | "human"
  | "machine";

export type ArticleOfferRole =
  | "writer"
  | "measure_article"
  | JudgeLens
  | "editor_decision";

export type ArticleMaterialSet = {
  readonly schemaVersion: "article-material-set/1";
  readonly articleId: string;
  readonly role: ArticleOfferRole | "article_review";
  readonly access: ArticleMaterialAccess;
  readonly checkId?: string;
  readonly manuscriptArtifactId?: ArtifactId;
  readonly artifacts: readonly ClassifiedArticleArtifact[];
  readonly artifactIds: readonly ArtifactId[];
};

export type ArticleMaterialContext = {
  readonly articleId: string;
  readonly contentMode: ArticleContentMode;
  readonly sourceIds: readonly string[];
  readonly productionProfile: ResolvedArticleProductionProfile;
  /** Must be the exact artifact bound by productionProfile.writingRulesArtifactId. */
  readonly writingRulesArtifactId: ArtifactId;
  readonly reviewPlan: ResolvedReviewPlan;
  readonly materializedInputs: readonly MaterializedWritePipelineInput[];
  /** Optional run-local artifacts created outside the write-pipeline resolver. */
  readonly articleBriefArtifactId?: ArtifactId;
  readonly editionContextArtifactId?: ArtifactId;
  readonly sourceApprovalArtifactIds?: readonly ArtifactId[];
  readonly measurementInputArtifactIds?: readonly ArtifactId[];
  readonly writerReviewMaterialArtifacts?: Readonly<Record<string, ArtifactId>>;
};

export type ArticleMaterialContextExtras = Omit<
  ArticleMaterialContext,
  "articleId" | "contentMode" | "sourceIds" | "productionProfile" | "writingRulesArtifactId" | "reviewPlan" | "materializedInputs"
>;

export type ArticleMaterialSelectionContext = {
  readonly manuscriptArtifactId?: ArtifactId;
  readonly findingArtifacts?: readonly ArtifactId[];
  readonly rulingArtifacts?: readonly ArtifactId[];
  readonly workingNotesArtifact?: ArtifactId;
  readonly writerReviewMaterialArtifacts?: Readonly<Record<string, ArtifactId>>;
};

export type LegacyArticleMaterialSelectionInput = {
  readonly articleId: string;
  readonly spec: ArticleRunSpec;
  readonly role: ArticleOfferRole;
  readonly manuscriptArtifact?: ArtifactId;
  readonly findingArtifacts?: readonly ArtifactId[];
  readonly rulingArtifacts?: readonly ArtifactId[];
  readonly workingNotesArtifact?: ArtifactId;
};

export type ArticleExposure = {
  readonly principalId: string;
  readonly manuscriptRevisionId?: ManuscriptRevisionId;
  readonly manuscriptArtifactId: ArtifactId;
  readonly access: "source_aware" | "source_blind";
};

/**
 * Validate the exact material boundary before a magazine-owned execution is
 * claimed. Keeping this check beside material selection prevents a Loops
 * workflow or an adapter from widening source access by accident.
 */
export function assertArticleExecutionMaterials(input: {
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly access: ArticleMaterialAccess;
  readonly materials: ArticleMaterialSet;
}): void {
  if (input.materials.articleId !== input.articleId) {
    throw new ArticleMaterialPolicyError(
      "ARTICLE_MATERIAL_ARTICLE_MISMATCH",
      `material set belongs to ${input.materials.articleId}, not ${input.articleId}`,
    );
  }
  if (input.materials.access !== input.access) {
    throw new ArticleMaterialPolicyError(
      "ARTICLE_MATERIAL_ACCESS_MISMATCH",
      `material set access ${input.materials.access} does not match execution access ${input.access}`,
    );
  }
  assertOneArticle(input.articleId, input.materials.artifacts);
  assertMaterialAccess(input.access, input.materials.artifacts, input.materials.role);
  if (input.materials.manuscriptArtifactId !== undefined && input.materials.manuscriptArtifactId !== input.manuscriptArtifactId) {
    throw new ArticleMaterialPolicyError(
      "ARTICLE_MATERIAL_MANUSCRIPT_MISMATCH",
      `material set is bound to manuscript ${input.materials.manuscriptArtifactId}, not ${input.manuscriptArtifactId}`,
    );
  }
  if (!input.materials.artifactIds.includes(input.manuscriptArtifactId)) {
    throw new ArticleMaterialPolicyError(
      "ARTICLE_MATERIAL_MANUSCRIPT_MISSING",
      `material set does not include manuscript ${input.manuscriptArtifactId}`,
    );
  }
}

export class SourceIsolationError extends Error {
  readonly role: WorkRole | string;
  readonly artifactId: ArtifactId;
  readonly classification: ArticleArtifactClassification;

  constructor(role: WorkRole | string, artifact: ClassifiedArticleArtifact) {
    super(
      `Role ${role} cannot read ${artifact.classification} artifact ${artifact.artifactId}`,
    );
    this.name = "SourceIsolationError";
    this.role = role;
    this.artifactId = artifact.artifactId;
    this.classification = artifact.classification;
  }
}

export class SourceExposureConflictError extends Error {
  readonly principalId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly existingAccess: "source_aware" | "source_blind";
  readonly requestedAccess: "source_aware" | "source_blind";

  constructor(input: {
    readonly principalId: string;
    readonly manuscriptArtifactId: ArtifactId;
    readonly existingAccess: "source_aware" | "source_blind";
    readonly requestedAccess: "source_aware" | "source_blind";
  }) {
    super(
      `Principal ${input.principalId} cannot cross source exposure for manuscript ${input.manuscriptArtifactId}`,
    );
    this.name = "SourceExposureConflictError";
    this.principalId = input.principalId;
    this.manuscriptArtifactId = input.manuscriptArtifactId;
    this.existingAccess = input.existingAccess;
    this.requestedAccess = input.requestedAccess;
  }
}

export class ArticleMaterialPolicyError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ArticleMaterialPolicyError";
    this.code = code;
  }
}

const sourceBlindRoles = new Set<WorkRole>(["mechanics", "shape", "craft"]);

const sourceBlindClasses = new Set<ArticleArtifactClassification>([
  "judge_prompt",
  "manuscript",
  "writing_rules",
]);

const sourceClasses = new Set<ArticleArtifactClassification>(["source"]);

/** Return the one access boundary used by both legacy offers and Loops checks. */
export function accessForRole(role: WorkRole | string): ArticleMaterialAccess {
  if (sourceBlindRoles.has(role as WorkRole)) return "source_blind";
  if (role === "measure_article") return "tool";
  if (role === "editor_decision") return "human";
  if (role === "durable_checkpoint" || role === "compile_revision_brief") return "machine";
  return "source_aware";
}

export function assertOneArticle(
  articleId: string,
  artifacts: readonly ClassifiedArticleArtifact[],
): void {
  for (const artifact of artifacts) {
    if (artifact.articleId !== articleId) {
      throw new TypeError(
        `Article ${articleId} offer cannot include artifact for ${artifact.articleId}`,
      );
    }
  }
}

/**
 * Enforce a material set's boundary. Source-blind work is deliberately
 * allow-listed. New classifications therefore fail closed until this module
 * explicitly decides they are safe for a source-blind reviewer.
 */
export function assertMaterialAccess(
  access: ArticleMaterialAccess,
  artifacts: readonly ClassifiedArticleArtifact[],
  role: WorkRole | string = "article",
): void {
  if (access === "source_blind") {
    for (const artifact of artifacts) {
      if (!sourceBlindClasses.has(artifact.classification)) {
        throw new SourceIsolationError(role, artifact);
      }
    }
  }
  if (access === "tool") {
    for (const artifact of artifacts) {
      if (sourceClasses.has(artifact.classification)) {
        throw new SourceIsolationError(role, artifact);
      }
    }
  }
}

/**
 * The durable authority calls this before registering an execution attempt.
 * Keeping the pure check here means a Loops worker and the legacy RunEngine
 * adapter cannot accidentally grow different exposure rules.
 */
export function assertPrincipalExposureIsolated(
  previous: readonly ArticleExposure[],
  requested: ArticleExposure,
): void {
  for (const exposure of previous) {
    if (
      exposure.principalId === requested.principalId &&
      ((exposure.manuscriptRevisionId !== undefined && requested.manuscriptRevisionId !== undefined && exposure.manuscriptRevisionId === requested.manuscriptRevisionId) ||
        (exposure.manuscriptRevisionId === undefined && requested.manuscriptRevisionId === undefined && exposure.manuscriptArtifactId === requested.manuscriptArtifactId)) &&
      exposure.access !== requested.access
    ) {
      throw new SourceExposureConflictError({
        principalId: requested.principalId,
        manuscriptArtifactId: requested.manuscriptArtifactId,
        existingAccess: exposure.access,
        requestedAccess: requested.access,
      });
    }
  }
}

export function artifactIds(
  artifacts: readonly ClassifiedArticleArtifact[],
): readonly ArtifactId[] {
  const seen = new Set<ArtifactId>();
  const ids: ArtifactId[] = [];
  for (const artifact of artifacts) {
    if (seen.has(artifact.artifactId)) continue;
    seen.add(artifact.artifactId);
    ids.push(artifact.artifactId);
  }
  return ids;
}

function classified(
  articleId: string,
  classification: ArticleArtifactClassification,
  artifactId: ArtifactId | undefined,
): ClassifiedArticleArtifact[] {
  return artifactId === undefined
    ? []
    : [{ artifactId, articleId, classification }];
}

function classifiedMany(
  articleId: string,
  classification: ArticleArtifactClassification,
  artifactIdsValue: readonly ArtifactId[] | undefined,
): ClassifiedArticleArtifact[] {
  return (artifactIdsValue ?? []).map((artifactId) => ({
    artifactId,
    articleId,
    classification,
  }));
}

function dedupe(
  articleId: string,
  artifacts: readonly ClassifiedArticleArtifact[],
): readonly ClassifiedArticleArtifact[] {
  const seen = new Set<ArtifactId>();
  return artifacts.filter((artifact) => {
    if (artifact.articleId !== articleId) {
      throw new TypeError(
        `Article ${articleId} material set cannot include artifact for ${artifact.articleId}`,
      );
    }
    if (seen.has(artifact.artifactId)) return false;
    seen.add(artifact.artifactId);
    return true;
  });
}

function materialSet(
  articleId: string,
  role: ArticleMaterialSet["role"],
  access: ArticleMaterialAccess,
  artifacts: readonly ClassifiedArticleArtifact[],
  options: {
    readonly checkId?: string;
    readonly manuscriptArtifactId?: ArtifactId;
  } = {},
): ArticleMaterialSet {
  const exact = Object.freeze([...dedupe(articleId, artifacts)]);
  assertMaterialAccess(access, exact, options.checkId ?? role);
  const ids = Object.freeze([...artifactIds(exact)]);
  return Object.freeze({
    schemaVersion: "article-material-set/1",
    articleId,
    role,
    access,
    ...(options.checkId === undefined ? {} : { checkId: options.checkId }),
    ...(options.manuscriptArtifactId === undefined
      ? {}
      : { manuscriptArtifactId: options.manuscriptArtifactId }),
    artifacts: exact,
    artifactIds: ids,
  });
}

function sourceArtifacts(context: ArticleMaterialContext): ClassifiedArticleArtifact[] {
  const sourceIds = new Set(context.sourceIds);
  return context.materializedInputs
    .filter((input) => input.ref.kind === "source_extraction" && sourceIds.has(input.ref.logicalId))
    .flatMap((input) => input.artifacts.map(({ artifactId }) => ({
      artifactId,
      articleId: context.articleId,
      classification: "source" as const,
    })));
}

function writerReviewMaterialArtifacts(
  context: ArticleMaterialContext,
  selection: ArticleMaterialSelectionContext,
): ClassifiedArticleArtifact[] {
  const values = selection.writerReviewMaterialArtifacts ?? context.writerReviewMaterialArtifacts;
  const declared = new Set(context.productionProfile.reviewMaterials.map((material) => material.materialId));
  for (const materialId of Object.keys(values ?? {})) {
    if (!declared.has(materialId)) {
      throw new ArticleMaterialPolicyError(
        "WRITER_MATERIAL_UNDECLARED",
        `writer review material ${materialId} is not declared by the production profile`,
      );
    }
  }
  return context.productionProfile.reviewMaterials.flatMap((material) => {
    const artifactId = values?.[material.materialId];
    // A writer's initial offer has no output materials yet. Only include
    // materials carried from an earlier revision; required output material
    // checks happen when the writer result is validated and when reviewers
    // request their inputs.
    if (artifactId === undefined) return [];
    return [{
      artifactId,
      articleId: context.articleId,
      classification: "writer_review_material" as const,
    }];
  });
}

function writingRulesArtifact(context: ArticleMaterialContext): ArtifactId {
  const profileArtifactId = context.productionProfile.writingRulesArtifactId;
  if (context.writingRulesArtifactId !== profileArtifactId) {
    throw new ArticleMaterialPolicyError(
      "WRITING_RULES_MISMATCH",
      `article ${context.articleId} writing-rules artifact does not match its production profile`,
    );
  }
  return profileArtifactId;
}

function commonWriterArtifacts(
  context: ArticleMaterialContext,
  selection: ArticleMaterialSelectionContext,
): ClassifiedArticleArtifact[] {
  const profile = context.productionProfile;
  return [
    ...classified(context.articleId, "writer_prompt", profile.writerPromptArtifactId),
    ...classified(context.articleId, "writer_policy", profile.profileArtifactId),
    ...classified(context.articleId, "writer_policy", profile.reviewPlanArtifactId),
    ...classifiedMany(context.articleId, "writer_policy", profile.writingPolicyArtifactIds),
    ...profile.reviewMaterials.map((material) => ({
      artifactId: material.schemaArtifactId,
      articleId: context.articleId,
      classification: "writer_policy" as const,
    })),
    ...classified(context.articleId, "writing_rules", writingRulesArtifact(context)),
    ...classified(context.articleId, "article_brief", context.articleBriefArtifactId),
    ...classified(context.articleId, "edition_context", context.editionContextArtifactId),
    ...sourceArtifacts(context),
    ...classifiedMany(context.articleId, "source", context.sourceApprovalArtifactIds),
    ...classified(context.articleId, "manuscript", selection.manuscriptArtifactId),
    ...classifiedMany(context.articleId, "revision_finding", selection.findingArtifacts),
    ...classifiedMany(context.articleId, "revision_finding", selection.rulingArtifacts),
    ...classified(context.articleId, "working_notes", selection.workingNotesArtifact),
    ...writerReviewMaterialArtifacts(context, selection),
  ];
}

export function selectArticleWriterMaterials(
  context: ArticleMaterialContext,
  selection: ArticleMaterialSelectionContext = {},
): ArticleMaterialSet {
  return materialSet(
    context.articleId,
    "writer",
    "source_aware",
    commonWriterArtifacts(context, selection),
    selection.manuscriptArtifactId === undefined
      ? {}
      : { manuscriptArtifactId: selection.manuscriptArtifactId },
  );
}

function selectedWriterMaterials(
  context: ArticleMaterialContext,
  check: Extract<ReviewCheckDefinition, { readonly kind: "model_review" }>,
  selection: ArticleMaterialSelectionContext,
): ClassifiedArticleArtifact[] {
  const requested = check.writerMaterialIds ?? [];
  if (requested.length === 0) return [];
  if (check.access === "source_blind") {
    throw new ArticleMaterialPolicyError(
      "SOURCE_BLIND_WRITER_MATERIAL",
      `source-blind review check ${check.id} cannot request writer material`,
    );
  }
  const available = selection.writerReviewMaterialArtifacts ?? context.writerReviewMaterialArtifacts ?? {};
  return requested.map((materialId) => {
    const artifactId = available[materialId];
    if (artifactId === undefined) {
      throw new ArticleMaterialPolicyError(
        "WRITER_MATERIAL_MISSING",
        `review check ${check.id} requests writer material ${materialId}, but no artifact is available`,
      );
    }
    return {
      artifactId,
      articleId: context.articleId,
      classification: "writer_review_material" as const,
    };
  });
}

function commonReviewerArtifacts(
  context: ArticleMaterialContext,
  manuscriptArtifactId: ArtifactId,
  promptArtifactId: ArtifactId,
): ClassifiedArticleArtifact[] {
  return [
    ...classified(context.articleId, "judge_prompt", promptArtifactId),
    ...classified(context.articleId, "manuscript", manuscriptArtifactId),
    ...classified(context.articleId, "writing_rules", writingRulesArtifact(context)),
  ];
}

export function selectArticleReviewerMaterials(
  context: ArticleMaterialContext,
  check: ReviewCheckDefinition,
  manuscriptArtifactId: ArtifactId,
  selection: ArticleMaterialSelectionContext = {},
): ArticleMaterialSet {
  if (check.kind === "article_measurement") {
    return materialSet(
      context.articleId,
      "measure_article",
      "tool",
      [
        ...classified(context.articleId, "manuscript", manuscriptArtifactId),
        ...classified(context.articleId, "article_brief", context.articleBriefArtifactId),
        ...classified(context.articleId, "edition_context", context.editionContextArtifactId),
        ...classified(context.articleId, "measurement_profile", check.measurementProfileArtifactId),
        ...classifiedMany(context.articleId, "measurement_input", context.measurementInputArtifactIds),
      ],
      { checkId: check.id, manuscriptArtifactId },
    );
  }

  const common = commonReviewerArtifacts(context, manuscriptArtifactId, check.promptArtifactId);
  const selectedWriter = selectedWriterMaterials(context, check, selection);
  const sourceAware = check.access === "source_aware";
  return materialSet(
    context.articleId,
    "article_review",
    check.access,
    [
      ...common,
      ...(sourceAware
        ? [
            ...classified(context.articleId, "article_brief", context.articleBriefArtifactId),
            ...classified(context.articleId, "edition_context", context.editionContextArtifactId),
            ...sourceArtifacts(context),
            ...classifiedMany(context.articleId, "source", context.sourceApprovalArtifactIds),
          ]
        : []),
      ...selectedWriter,
    ],
    { checkId: check.id, manuscriptArtifactId },
  );
}

export function applicableReviewCheck(
  check: ReviewCheckDefinition,
  contentMode: ArticleContentMode,
  teaching: "applicable" | "not_applicable" = "not_applicable",
): boolean {
  const condition = check.applicableWhen;
  if (condition === undefined || condition.kind === "always") return true;
  if (condition.kind === "content_mode") return condition.values.includes(contentMode);
  return condition.value === teaching;
}

export type ArticleMaterialSets = {
  readonly writer: ArticleMaterialSet;
  readonly reviews: readonly ArticleMaterialSet[];
};

export function selectArticleMaterialSets(
  context: ArticleMaterialContext,
  manuscriptArtifactId: ArtifactId,
  selection: ArticleMaterialSelectionContext = {},
  teaching: "applicable" | "not_applicable" = "not_applicable",
): ArticleMaterialSets {
  const reviews = context.reviewPlan.checks
    .filter((check) => applicableReviewCheck(check, context.contentMode, teaching))
    .map((check) => selectArticleReviewerMaterials(context, check, manuscriptArtifactId, selection));
  return Object.freeze({
    writer: selectArticleWriterMaterials(context, selection),
    reviews: Object.freeze(reviews),
  });
}

/** Adapt the resolved write-pipeline entry to the policy module's stable input. */
export function articleMaterialContextFromLoops(
  input: LoopsArticleEntryInput,
  extras: ArticleMaterialContextExtras = {},
): ArticleMaterialContext {
  return {
    articleId: input.articleId,
    contentMode: input.contentMode,
    sourceIds: input.sourceIds,
    productionProfile: input.productionProfile,
    writingRulesArtifactId: input.writingRulesArtifactId,
    reviewPlan: input.reviewPlan,
    materializedInputs: input.materializedInputs,
    ...extras,
  };
}

/**
 * Legacy task-composer adapter. It delegates all role/material policy to this
 * module so the old XState path and the Loops path cannot drift.
 */
export function selectLegacyArticleMaterialSet(
  input: LegacyArticleMaterialSelectionInput,
): ArticleMaterialSet {
  const { articleId, spec, role } = input;
  const classifiedInput = (classification: ArticleArtifactClassification, artifactId: ArtifactId | undefined) =>
    classified(articleId, classification, artifactId);
  const many = (classification: ArticleArtifactClassification, artifactIdsValue: readonly ArtifactId[] | undefined) =>
    classifiedMany(articleId, classification, artifactIdsValue);

  let artifacts: ClassifiedArticleArtifact[];
  if (role === "writer") {
    artifacts = [
      ...classifiedInput("writer_prompt", spec.writerPrompt),
      ...classifiedInput("writer_policy", spec.contentModeArtifact),
      ...classifiedInput("writer_policy", spec.attributionArtifact),
      ...classifiedInput("writer_policy", spec.editorialPolicyArtifact),
      ...classifiedInput("writer_policy", spec.modelPolicyArtifact),
      ...classifiedInput("article_brief", spec.articleBrief),
      ...classifiedInput("writing_rules", spec.writingRules),
      ...classifiedInput("edition_context", spec.editionContext),
      ...many("source", spec.sources),
      ...many("source", spec.sourceApprovalArtifacts),
      ...classifiedInput("manuscript", input.manuscriptArtifact),
      ...many("revision_finding", input.findingArtifacts),
      ...many("revision_finding", input.rulingArtifacts),
      ...classifiedInput("working_notes", input.workingNotesArtifact),
    ];
  } else if (role === "measure_article") {
    artifacts = [
      ...classifiedInput("manuscript", input.manuscriptArtifact),
      ...classifiedInput("article_brief", spec.articleBrief),
      ...classifiedInput("edition_context", spec.editionContext),
      ...classifiedInput("measurement_profile", spec.measurementProfileArtifact),
      ...many("measurement_input", spec.measurementInputArtifacts),
    ];
  } else if (role === "editor_decision") {
    artifacts = [
      ...classifiedInput("manuscript", input.manuscriptArtifact),
      ...classifiedInput("article_brief", spec.articleBrief),
      ...many("revision_finding", input.findingArtifacts),
      ...many("revision_finding", input.rulingArtifacts),
      ...classifiedInput("working_notes", input.workingNotesArtifact),
    ];
  } else {
    const prompt = spec.judgePrompts[role];
    if (prompt === undefined) {
      throw new TypeError(`Article ${spec.articleId} has no prompt for ${role}`);
    }
    artifacts = [
      ...classifiedInput("judge_prompt", prompt),
      ...classifiedInput("manuscript", input.manuscriptArtifact),
      ...classifiedInput("writing_rules", spec.writingRules),
      ...(sourceBlindRoles.has(role)
        ? []
        : [
            ...classifiedInput("article_brief", spec.articleBrief),
            ...classifiedInput("edition_context", spec.editionContext),
            ...many("source", spec.sources),
            ...many("source", spec.sourceApprovalArtifacts),
          ]),
    ];
  }

  return materialSet(
    articleId,
    role,
    accessForRole(role),
    artifacts,
    input.manuscriptArtifact === undefined
      ? {}
      : { manuscriptArtifactId: input.manuscriptArtifact },
  );
}
