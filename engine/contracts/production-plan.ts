import { z } from "zod";

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
