import { z } from "zod";

import type { ArtifactId } from "./ids.ts";
import type { ArticleContentMode } from "./run.ts";
import type { InputRevisionRef } from "../durable/types.ts";

export const APPROVED_PRODUCTION_PLAN_CONTRACT_VERSION =
  "approved-production-plan/1" as const;

export const sourceAssignmentPolicySchema = z.enum([
  "at_least_once",
  "exactly_once",
]);

export const productionDependencySchema = z
  .object({
    articleIds: z.array(z.string().min(1)).default([]),
    editorial: z.boolean().default(false),
  })
  .strict();

const artifactIdSchema = z.string().min(1);

const modelChoiceSchema = z
  .object({
    adapter: z.string().min(1),
    model: z.string().min(1),
    reasoningEffort: z.string().min(1).optional(),
    settings: z.record(z.string(), z.json()).optional(),
  })
  .strict();

const modelPolicySchema = z
  .object({
    default: modelChoiceSchema,
    roles: z.record(z.string(), modelChoiceSchema).optional(),
  })
  .strict();

const judgeLensSchema = z.enum([
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
]);

const plannedArticleSchema = z
  .object({
    articleId: z.string().min(1),
    contentMode: z.enum([
      "faithful_edit",
      "faithful_synthesis",
      "original_synthesis",
    ]),
    attribution: z.discriminatedUnion("kind", [
      z
        .object({
          kind: z.literal("source_author"),
          byline: z.string().min(1),
          sourceAuthors: z.array(z.string().min(1)).min(1),
          sourceIds: z.array(z.string().min(1)).min(1),
        })
        .strict(),
      z
        .object({
          kind: z.literal("magazine"),
          byline: z.string().min(1),
        })
        .strict(),
    ]),
    editionContext: artifactIdSchema.optional(),
    articleBrief: artifactIdSchema,
    sourceIds: z.array(z.string().min(1)).min(1),
    writerPrompt: artifactIdSchema,
    contentModeArtifact: artifactIdSchema.optional(),
    attributionArtifact: artifactIdSchema.optional(),
    editorialPolicyArtifact: artifactIdSchema.optional(),
    modelPolicyArtifact: artifactIdSchema.optional(),
    judgePrompts: z
      .object({
        worth: artifactIdSchema.optional(),
        mechanics: artifactIdSchema.optional(),
        evidence: artifactIdSchema.optional(),
        shape: artifactIdSchema.optional(),
        teaching: artifactIdSchema.optional(),
        craft: artifactIdSchema.optional(),
      })
      .strict(),
    writingRules: artifactIdSchema,
    measurementProfileArtifact: artifactIdSchema.optional(),
    measurementInputArtifacts: z.array(artifactIdSchema).optional(),
    initialManuscript: artifactIdSchema.optional(),
    policy: z
      .object({
        maxIterations: z.number().int().positive(),
        maximumReaderPages: z.number().int().positive().max(7),
        teaching: z.enum(["applicable", "not_applicable"]),
        enabledLenses: z.array(judgeLensSchema),
        blockingLenses: z.array(judgeLensSchema),
      })
      .strict(),
    modelPolicy: modelPolicySchema,
  })
  .strict();

const plannedArtSchema = z
  .object({
    key: z.string().min(1),
    role: z.enum(["cover", "interior"]),
    artifactId: artifactIdSchema.optional(),
    briefArtifact: artifactIdSchema,
    required: z.boolean(),
    dependencies: productionDependencySchema.optional(),
  })
  .strict();

const plannedTranslationSchema = z
  .object({
    pieceKind: z.enum(["article", "editorial"]),
    pieceId: z.string().min(1),
    language: z.string().min(1),
    sourceLanguage: z.string().min(1),
    englishArtifacts: z.array(artifactIdSchema).length(1),
    promptArtifact: artifactIdSchema,
    measurementProfileArtifact: artifactIdSchema.optional(),
    measurementInputArtifacts: z.array(artifactIdSchema).optional(),
    inputRevisions: z.array(z.unknown()).optional(),
    initialTranslationArtifacts: z.array(artifactIdSchema).optional(),
    maximumReaderPages: z.number().int().positive(),
    modelPolicy: modelPolicySchema,
  })
  .strict();

export const approvedProductionPlanSchema = z
  .object({
    contractVersion: z.literal(APPROVED_PRODUCTION_PLAN_CONTRACT_VERSION),
    sourceAssignmentPolicy: sourceAssignmentPolicySchema,
    articles: z.array(plannedArticleSchema),
    art: z.array(plannedArtSchema),
    translations: z.array(plannedTranslationSchema),
  })
  .strict();

export type SourceAssignmentPolicy = z.infer<typeof sourceAssignmentPolicySchema>;
export type ProductionDependency = z.infer<typeof productionDependencySchema>;
export type ApprovedProductionPlan = z.infer<typeof approvedProductionPlanSchema>;

export function parseApprovedProductionPlan(value: unknown): ApprovedProductionPlan {
  return approvedProductionPlanSchema.parse(value);
}

/*
 * Article production contracts
 *
 * These documents are Git-bound input revisions. They deliberately contain
 * revision references, never run-scoped artifact IDs. The resolved forms are
 * the corresponding run-local projections produced by the authenticated
 * write-pipeline materializer.
 */

export const ARTICLE_PRODUCTION_PROFILE_CONTRACT_VERSION =
  "article-production-profile/1" as const;
export const ARTICLE_REVIEW_PLAN_CONTRACT_VERSION =
  "article-review-plan/1" as const;
export const RESOLVED_ARTICLE_PRODUCTION_PROFILE_CONTRACT_VERSION =
  "resolved-article-production-profile/1" as const;
export const RESOLVED_ARTICLE_REVIEW_PLAN_CONTRACT_VERSION =
  "resolved-article-review-plan/1" as const;
export const ARTICLE_WRITER_RESULT_CONTRACT_VERSION =
  "article-writer-result/1" as const;

export type PromptRevisionRef = Extract<InputRevisionRef, { readonly kind: "prompt" }>;
export type PolicyRevisionRef = Extract<InputRevisionRef, { readonly kind: "policy" }>;
export type ArticleReviewPlanRevisionRef = Extract<InputRevisionRef, { readonly kind: "article_review_plan" }>;
export type ReviewMaterialSchemaRevisionRef = Extract<InputRevisionRef, { readonly kind: "review_material_schema" }>;
export type MeasurementProfileRevisionRef = PolicyRevisionRef;

export type ReviewMaterialRevisionContract = {
  readonly materialId: string;
  readonly schemaRevision: ReviewMaterialSchemaRevisionRef;
  readonly required: boolean;
};

export type ArticleProductionProfileDocument = {
  readonly schemaVersion: typeof ARTICLE_PRODUCTION_PROFILE_CONTRACT_VERSION;
  readonly profileId: string;
  readonly formatId: string;
  readonly writer: {
    readonly promptRevision: PromptRevisionRef;
    readonly resultContractVersion: typeof ARTICLE_WRITER_RESULT_CONTRACT_VERSION;
    readonly reviewMaterials: readonly ReviewMaterialRevisionContract[];
  };
  readonly reviewPlanRevision: ArticleReviewPlanRevisionRef;
  /** The one exact house-writing-rules policy revision required by every writer. */
  readonly writingRulesRevision: PolicyRevisionRef;
  /** Additional writer policies. These are not a substitute for writingRulesRevision. */
  readonly writingPolicyRevisions: readonly PolicyRevisionRef[];
  readonly revisionPolicy: {
    readonly maximumRewrites: number;
  };
};

export type ResolvedArticleProductionProfile = {
  readonly schemaVersion: typeof RESOLVED_ARTICLE_PRODUCTION_PROFILE_CONTRACT_VERSION;
  readonly profileId: string;
  readonly formatId: string;
  readonly profileArtifactId: ArtifactId;
  readonly writerPromptArtifactId: ArtifactId;
  readonly writerResultContractVersion: typeof ARTICLE_WRITER_RESULT_CONTRACT_VERSION;
  readonly reviewMaterials: readonly {
    readonly materialId: string;
    readonly schemaArtifactId: ArtifactId;
    readonly schemaVersion: string;
    readonly required: boolean;
  }[];
  readonly reviewPlanArtifactId: ArtifactId;
  /** The exact materialized writing-rules payload bound to this profile. */
  readonly writingRulesArtifactId: ArtifactId;
  readonly writingPolicyArtifactIds: readonly ArtifactId[];
  readonly maximumRewrites: number;
};

export type ReviewerId = string;
export type ReviewCheckId = string;
export type ReviewWaveId = string;

export type ReviewCondition =
  | { readonly kind: "always" }
  | { readonly kind: "content_mode"; readonly values: readonly ArticleContentMode[] }
  | { readonly kind: "teaching"; readonly value: "applicable" | "not_applicable" };

export type ModelReviewRevisionDefinition = {
  readonly kind: "model_review";
  readonly id: ReviewerId;
  readonly role: "article_review";
  readonly promptRevision: PromptRevisionRef;
  readonly access: "source_aware" | "source_blind";
  readonly authority: "advisory" | "blocking" | "human_required";
  readonly writerMaterialIds?: readonly string[];
  readonly applicableWhen?: ReviewCondition;
};

export type ArticleMeasurementRevisionDefinition = {
  readonly kind: "article_measurement";
  readonly id: "measure_article";
  readonly role: "measure_article";
  readonly measurementProfileRevision: MeasurementProfileRevisionRef;
  readonly maximumReaderPages: number;
  readonly applicableWhen?: ReviewCondition;
};

export type ReviewCheckRevisionDefinition =
  | ModelReviewRevisionDefinition
  | ArticleMeasurementRevisionDefinition;

export type ArticleReviewPlanDocument = {
  readonly schemaVersion: typeof ARTICLE_REVIEW_PLAN_CONTRACT_VERSION;
  readonly checks: readonly ReviewCheckRevisionDefinition[];
  readonly waves: readonly ReviewWave[];
};

export type ModelReviewDefinition = Omit<ModelReviewRevisionDefinition, "promptRevision"> & {
  readonly promptArtifactId: ArtifactId;
};

export type ArticleMeasurementDefinition = Omit<
  ArticleMeasurementRevisionDefinition,
  "measurementProfileRevision"
> & {
  readonly measurementProfileArtifactId: ArtifactId;
};

export type ReviewCheckDefinition = ModelReviewDefinition | ArticleMeasurementDefinition;

export type ReviewWave = {
  readonly id: ReviewWaveId;
  readonly checkIds: readonly ReviewCheckId[];
  readonly stopAfter: "never" | "blocking" | "human_required";
};

export type ResolvedReviewPlan = {
  readonly schemaVersion: typeof RESOLVED_ARTICLE_REVIEW_PLAN_CONTRACT_VERSION;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly checks: readonly ReviewCheckDefinition[];
  readonly waves: readonly ReviewWave[];
};

const revisionIdSchema = z.string().min(1);
const componentSchema = z.string().min(1).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/u);
const artifactRefSchema = z.string().min(1);

const revisionRefSchema = z.object({
  kind: z.string().min(1),
  logical_id: componentSchema,
  revision_id: revisionIdSchema,
  edition_id: componentSchema.optional(),
}).strict();

const promptRevisionSchema = revisionRefSchema.extend({ kind: z.literal("prompt") }).strict();
const policyRevisionSchema = revisionRefSchema.extend({ kind: z.literal("policy") }).strict();
const reviewPlanRevisionSchema = revisionRefSchema.extend({ kind: z.literal("article_review_plan") }).strict();
const materialSchemaRevisionSchema = revisionRefSchema.extend({ kind: z.literal("review_material_schema") }).strict();

const reviewConditionSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("always") }).strict(),
  z.object({
    kind: z.literal("content_mode"),
    values: z.array(z.enum(["faithful_edit", "faithful_synthesis", "original_synthesis"])).min(1),
  }).strict(),
  z.object({
    kind: z.literal("teaching"),
    value: z.enum(["applicable", "not_applicable"]),
  }).strict(),
]);

const reviewWaveSchema = z.object({
  id: componentSchema,
  check_ids: z.array(componentSchema).min(1),
  stop_after: z.enum(["never", "blocking", "human_required"]),
}).strict();

const modelReviewRevisionSchema = z.object({
  kind: z.literal("model_review"),
  id: componentSchema,
  role: z.literal("article_review"),
  prompt_revision: promptRevisionSchema,
  access: z.enum(["source_aware", "source_blind"]),
  authority: z.enum(["advisory", "blocking", "human_required"]),
  writer_material_ids: z.array(componentSchema).optional(),
  applicable_when: reviewConditionSchema.optional(),
}).strict();

const measurementRevisionSchema = z.object({
  kind: z.literal("article_measurement"),
  id: z.literal("measure_article"),
  role: z.literal("measure_article"),
  measurement_profile_revision: revisionRefSchema,
  maximum_reader_pages: z.number().int().positive().max(7),
  applicable_when: reviewConditionSchema.optional(),
}).strict();

const profileSchema = z.object({
  schema_version: z.literal(ARTICLE_PRODUCTION_PROFILE_CONTRACT_VERSION),
  profile_id: componentSchema,
  format_id: componentSchema,
  writer: z.object({
    prompt_revision: promptRevisionSchema,
    result_contract_version: z.literal(ARTICLE_WRITER_RESULT_CONTRACT_VERSION),
    review_materials: z.array(z.object({
      material_id: componentSchema,
      schema_revision: materialSchemaRevisionSchema,
      required: z.boolean(),
    }).strict()),
  }).strict(),
  review_plan_revision: reviewPlanRevisionSchema,
  writing_rules_revision: policyRevisionSchema,
  writing_policy_revisions: z.array(policyRevisionSchema),
  revision_policy: z.object({ maximum_rewrites: z.number().int().nonnegative() }).strict(),
}).strict();

const reviewPlanSchema = z.object({
  schema_version: z.literal(ARTICLE_REVIEW_PLAN_CONTRACT_VERSION),
  checks: z.array(z.union([modelReviewRevisionSchema, measurementRevisionSchema])).min(1),
  waves: z.array(reviewWaveSchema).min(1),
}).strict();

function inputRevisionRef(value: z.infer<typeof revisionRefSchema>, expectedKind?: InputRevisionRef["kind"]): InputRevisionRef {
  if (expectedKind !== undefined && value.kind !== expectedKind) {
    throw new Error(`expected ${expectedKind} input revision, got ${value.kind}`);
  }
  const editionBound = value.kind === "edition_spec" || value.kind === "run_bootstrap" || value.kind === "write_pipeline";
  if (editionBound !== (value.edition_id !== undefined)) {
    throw new Error(`input ${value.logical_id} has an invalid edition binding`);
  }
  return {
    kind: value.kind,
    logicalId: value.logical_id,
    revisionId: value.revision_id as never,
    ...(editionBound ? { editionId: value.edition_id! } : {}),
  } as InputRevisionRef;
}

function unique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) throw new Error(`${label} must be unique`);
}

function validateCondition(value: ReviewCondition | undefined): void {
  if (value?.kind === "content_mode") unique(value.values, "review condition content modes");
}

function validateReviewPlan(plan: ArticleReviewPlanDocument): ArticleReviewPlanDocument {
  unique(plan.checks.map((check) => check.id), "review check IDs");
  unique(plan.waves.map((wave) => wave.id), "review wave IDs");
  const checkIds = new Set(plan.checks.map((check) => check.id));
  const membership = new Map<string, number>();
  for (const wave of plan.waves) {
    unique(wave.checkIds, `checks in wave ${wave.id}`);
    for (const checkId of wave.checkIds) {
      if (!checkIds.has(checkId)) throw new Error(`review wave ${wave.id} names unknown check ${checkId}`);
      membership.set(checkId, (membership.get(checkId) ?? 0) + 1);
    }
  }
  for (const check of plan.checks) {
    if (membership.get(check.id) !== 1) throw new Error(`review check ${check.id} must belong to exactly one wave`);
    validateCondition(check.applicableWhen);
    if (check.kind === "model_review") {
      unique(check.writerMaterialIds ?? [], `writer material IDs for ${check.id}`);
      if (check.access === "source_blind" && (check.writerMaterialIds?.length ?? 0) > 0) {
        throw new Error(`source-blind review check ${check.id} cannot request writer material`);
      }
    }
  }
  return plan;
}

export function parseArticleProductionProfileDocument(value: unknown): ArticleProductionProfileDocument {
  const parsed = profileSchema.parse(value);
  unique(parsed.writer.review_materials.map((material) => material.material_id), "writer review material IDs");
  unique(parsed.writing_policy_revisions.map((revision) => revision.logical_id), "writing policy revisions");
  if (parsed.writing_policy_revisions.some((revision) => revision.logical_id === parsed.writing_rules_revision.logical_id)) {
    throw new Error("writing-rules revision must not also appear in writing policy revisions");
  }
  return {
    schemaVersion: parsed.schema_version,
    profileId: parsed.profile_id,
    formatId: parsed.format_id,
    writer: {
      promptRevision: inputRevisionRef(parsed.writer.prompt_revision, "prompt") as PromptRevisionRef,
      resultContractVersion: parsed.writer.result_contract_version,
      reviewMaterials: parsed.writer.review_materials.map((material) => ({
        materialId: material.material_id,
        schemaRevision: inputRevisionRef(material.schema_revision, "review_material_schema") as ReviewMaterialSchemaRevisionRef,
        required: material.required,
      })),
    },
    reviewPlanRevision: inputRevisionRef(parsed.review_plan_revision, "article_review_plan") as ArticleReviewPlanRevisionRef,
    writingRulesRevision: inputRevisionRef(parsed.writing_rules_revision, "policy") as PolicyRevisionRef,
    writingPolicyRevisions: parsed.writing_policy_revisions.map((revision) => inputRevisionRef(revision, "policy") as PolicyRevisionRef),
    revisionPolicy: { maximumRewrites: parsed.revision_policy.maximum_rewrites },
  };
}

export function parseArticleReviewPlanDocument(value: unknown): ArticleReviewPlanDocument {
  const parsed = reviewPlanSchema.parse(value);
  return validateReviewPlan({
    schemaVersion: parsed.schema_version,
    checks: parsed.checks.map((check) => check.kind === "model_review"
      ? {
          kind: check.kind,
          id: check.id,
          role: check.role,
          promptRevision: inputRevisionRef(check.prompt_revision, "prompt") as PromptRevisionRef,
          access: check.access,
          authority: check.authority,
          ...(check.writer_material_ids === undefined ? {} : { writerMaterialIds: check.writer_material_ids }),
          ...(check.applicable_when === undefined ? {} : { applicableWhen: check.applicable_when }),
        }
      : {
          kind: check.kind,
          id: check.id,
          role: check.role,
          measurementProfileRevision: inputRevisionRef(check.measurement_profile_revision, "policy") as MeasurementProfileRevisionRef,
          maximumReaderPages: check.maximum_reader_pages,
          ...(check.applicable_when === undefined ? {} : { applicableWhen: check.applicable_when }),
        }),
    waves: parsed.waves.map((wave) => ({
      id: wave.id,
      checkIds: wave.check_ids,
      stopAfter: wave.stop_after,
    })),
  });
}

const resolvedMaterialSchema = z.object({
  material_id: componentSchema,
  schema_artifact_id: artifactRefSchema,
  schema_version: z.string().min(1),
  required: z.boolean(),
}).strict();

export function parseResolvedArticleProductionProfile(value: unknown): ResolvedArticleProductionProfile {
  const parsed = z.object({
    schema_version: z.literal(RESOLVED_ARTICLE_PRODUCTION_PROFILE_CONTRACT_VERSION),
    profile_id: componentSchema,
    format_id: componentSchema,
    profile_artifact_id: artifactRefSchema,
    writer_prompt_artifact_id: artifactRefSchema,
    writer_result_contract_version: z.literal(ARTICLE_WRITER_RESULT_CONTRACT_VERSION),
    review_materials: z.array(resolvedMaterialSchema),
    review_plan_artifact_id: artifactRefSchema,
    writing_rules_artifact_id: artifactRefSchema,
    writing_policy_artifact_ids: z.array(artifactRefSchema),
    maximum_rewrites: z.number().int().nonnegative(),
  }).strict().parse(value);
  unique(parsed.review_materials.map((material) => material.material_id), "resolved writer review material IDs");
  return {
    schemaVersion: parsed.schema_version,
    profileId: parsed.profile_id,
    formatId: parsed.format_id,
    profileArtifactId: parsed.profile_artifact_id as ArtifactId,
    writerPromptArtifactId: parsed.writer_prompt_artifact_id as ArtifactId,
    writerResultContractVersion: parsed.writer_result_contract_version,
    reviewMaterials: parsed.review_materials.map((material) => ({
      materialId: material.material_id,
      schemaArtifactId: material.schema_artifact_id as ArtifactId,
      schemaVersion: material.schema_version,
      required: material.required,
    })),
    reviewPlanArtifactId: parsed.review_plan_artifact_id as ArtifactId,
    writingRulesArtifactId: parsed.writing_rules_artifact_id as ArtifactId,
    writingPolicyArtifactIds: parsed.writing_policy_artifact_ids as ArtifactId[],
    maximumRewrites: parsed.maximum_rewrites,
  };
}

export function parseResolvedReviewPlan(value: unknown): ResolvedReviewPlan {
  const parsed = z.object({
    schema_version: z.literal(RESOLVED_ARTICLE_REVIEW_PLAN_CONTRACT_VERSION),
    review_plan_artifact_id: artifactRefSchema,
    checks: z.array(z.union([
      z.object({
        kind: z.literal("model_review"),
        id: componentSchema,
        role: z.literal("article_review"),
        prompt_artifact_id: artifactRefSchema,
        access: z.enum(["source_aware", "source_blind"]),
        authority: z.enum(["advisory", "blocking", "human_required"]),
        writer_material_ids: z.array(componentSchema).optional(),
        applicable_when: reviewConditionSchema.optional(),
      }).strict(),
      z.object({
        kind: z.literal("article_measurement"),
        id: z.literal("measure_article"),
        role: z.literal("measure_article"),
        measurement_profile_artifact_id: artifactRefSchema,
        maximum_reader_pages: z.number().int().positive().max(7),
        applicable_when: reviewConditionSchema.optional(),
      }).strict(),
    ])).min(1),
    waves: z.array(reviewWaveSchema).min(1),
  }).strict().parse(value);
  return validateResolvedReviewPlan({
    schemaVersion: parsed.schema_version,
    reviewPlanArtifactId: parsed.review_plan_artifact_id as ArtifactId,
    checks: parsed.checks.map((check) => check.kind === "model_review"
      ? {
          kind: check.kind,
          id: check.id,
          role: check.role,
          promptArtifactId: check.prompt_artifact_id as ArtifactId,
          access: check.access,
          authority: check.authority,
          ...(check.writer_material_ids === undefined ? {} : { writerMaterialIds: check.writer_material_ids }),
          ...(check.applicable_when === undefined ? {} : { applicableWhen: check.applicable_when }),
        }
      : {
          kind: check.kind,
          id: check.id,
          role: check.role,
          measurementProfileArtifactId: check.measurement_profile_artifact_id as ArtifactId,
          maximumReaderPages: check.maximum_reader_pages,
          ...(check.applicable_when === undefined ? {} : { applicableWhen: check.applicable_when }),
        }),
    waves: parsed.waves.map((wave) => ({ id: wave.id, checkIds: wave.check_ids, stopAfter: wave.stop_after })),
  });
}

function validateResolvedReviewPlan(plan: ResolvedReviewPlan): ResolvedReviewPlan {
  unique(plan.checks.map((check) => check.id), "resolved review check IDs");
  unique(plan.waves.map((wave) => wave.id), "resolved review wave IDs");
  const checkIds = new Set(plan.checks.map((check) => check.id));
  const membership = new Map<string, number>();
  for (const wave of plan.waves) {
    unique(wave.checkIds, `checks in wave ${wave.id}`);
    for (const id of wave.checkIds) {
      if (!checkIds.has(id)) throw new Error(`resolved review wave ${wave.id} names unknown check ${id}`);
      membership.set(id, (membership.get(id) ?? 0) + 1);
    }
  }
  for (const check of plan.checks) {
    if (membership.get(check.id) !== 1) throw new Error(`resolved review check ${check.id} must belong to exactly one wave`);
    if (check.kind === "model_review") {
      unique(check.writerMaterialIds ?? [], `writer material IDs for ${check.id}`);
      if (check.access === "source_blind" && (check.writerMaterialIds?.length ?? 0) > 0) {
        throw new Error(`source-blind review check ${check.id} cannot request writer material`);
      }
    }
  }
  return plan;
}
