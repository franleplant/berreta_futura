import { z } from "zod";

import type { ArtifactId, ArticleExecutionId, ManuscriptRevisionId } from "../contracts/index.ts";

/** The reason a new immutable manuscript revision was produced. */
export type ArticleRevisionTrigger = "initial" | "auto_rewrite" | "editor_revise";

/**
 * ID-only writer context. The writer resolves every referenced artifact from
 * the magazine ledger; no manuscript text or model prompt crosses this seam.
 */
export type ArticleRevisionContext = {
  readonly schemaVersion: "article-revision-context/1";
  readonly articleExecutionId: ArticleExecutionId;
  readonly cycleId: string;
  readonly rewriteOrdinal: number;
  readonly trigger: Exclude<ArticleRevisionTrigger, "initial">;
  readonly previousManuscriptArtifactId: ArtifactId;
  readonly revisionBriefArtifactId: ArtifactId;
  readonly routeArtifactId: ArtifactId;
  readonly priorWorkingNotesArtifactId?: ArtifactId;
  readonly priorFindingDispositionsArtifactId?: ArtifactId;
  readonly priorReviewMaterialArtifactIds: readonly ArtifactId[];
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  readonly editorDecisionArtifactId?: ArtifactId;
};

/** Immutable package record for one exact manuscript revision. */
export type ArticleRevisionRecord = {
  readonly schemaVersion: "article-revision-record/1";
  readonly ordinal: number;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly previousRevisionRecordArtifactId?: ArtifactId;
  readonly revisionContextArtifactId?: ArtifactId;
  readonly selectedWriterClaimId?: string;
  readonly selectedWriterOutputArtifactId?: ArtifactId;
  readonly workingNotesArtifactId?: ArtifactId;
  readonly findingDispositionsArtifactId?: ArtifactId;
  readonly reviewMaterialArtifactIds: readonly ArtifactId[];
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  readonly trigger: ArticleRevisionTrigger;
};

const artifactIdSchema = z.string().min(1);

export const articleRevisionContextSchema = z.object({
  schemaVersion: z.literal("article-revision-context/1"),
  articleExecutionId: z.string().min(1),
  cycleId: z.string().min(1),
  rewriteOrdinal: z.number().int().nonnegative(),
  trigger: z.enum(["auto_rewrite", "editor_revise"]),
  previousManuscriptArtifactId: artifactIdSchema,
  revisionBriefArtifactId: artifactIdSchema,
  routeArtifactId: artifactIdSchema,
  priorWorkingNotesArtifactId: artifactIdSchema.optional(),
  priorFindingDispositionsArtifactId: artifactIdSchema.optional(),
  priorReviewMaterialArtifactIds: z.array(artifactIdSchema),
  humanRulingArtifactIds: z.array(artifactIdSchema),
  editorDecisionArtifactId: artifactIdSchema.optional(),
}).strict();

export const articleRevisionRecordSchema = z.object({
  schemaVersion: z.literal("article-revision-record/1"),
  ordinal: z.number().int().nonnegative(),
  manuscriptArtifactId: artifactIdSchema,
  manuscriptRevisionId: artifactIdSchema,
  previousRevisionRecordArtifactId: artifactIdSchema.optional(),
  revisionContextArtifactId: artifactIdSchema.optional(),
  selectedWriterClaimId: z.string().min(1).optional(),
  selectedWriterOutputArtifactId: artifactIdSchema.optional(),
  workingNotesArtifactId: artifactIdSchema.optional(),
  findingDispositionsArtifactId: artifactIdSchema.optional(),
  reviewMaterialArtifactIds: z.array(artifactIdSchema),
  humanRulingArtifactIds: z.array(artifactIdSchema),
  trigger: z.enum(["initial", "auto_rewrite", "editor_revise"]),
}).strict();

export function parseArticleRevisionContext(value: unknown): ArticleRevisionContext {
  const parsed = articleRevisionContextSchema.safeParse(value);
  if (!parsed.success) throw new Error("article revision context does not match article-revision-context/1");
  return parsed.data as unknown as ArticleRevisionContext;
}

export function parseArticleRevisionRecord(value: unknown): ArticleRevisionRecord {
  const parsed = articleRevisionRecordSchema.safeParse(value);
  if (!parsed.success) throw new Error("article revision record does not match article-revision-record/1");
  return parsed.data as unknown as ArticleRevisionRecord;
}

/** Exact parent IDs and relation names for a revision context artifact. */
export function articleRevisionContextParents(input: ArticleRevisionContext): readonly { readonly artifactId: ArtifactId; readonly relation: string }[] {
  const parents = [
    { artifactId: input.previousManuscriptArtifactId, relation: "revision_previous_manuscript" },
    { artifactId: input.revisionBriefArtifactId, relation: "revision_brief" },
    { artifactId: input.routeArtifactId, relation: "review_route" },
    ...(input.priorWorkingNotesArtifactId === undefined ? [] : [{ artifactId: input.priorWorkingNotesArtifactId, relation: "prior_working_notes" }]),
    ...(input.priorFindingDispositionsArtifactId === undefined ? [] : [{ artifactId: input.priorFindingDispositionsArtifactId, relation: "prior_finding_dispositions" }]),
    ...input.priorReviewMaterialArtifactIds.map((artifactId) => ({ artifactId, relation: "prior_review_material" })),
    ...input.humanRulingArtifactIds.map((artifactId) => ({ artifactId, relation: "human_ruling" })),
    ...(input.editorDecisionArtifactId === undefined ? [] : [{ artifactId: input.editorDecisionArtifactId, relation: "editor_decision" }]),
  ];
  assertUniqueParents(parents);
  return Object.freeze(parents);
}

/** Exact parent IDs and relation names for a revision record artifact. */
export function articleRevisionRecordParents(input: ArticleRevisionRecord): readonly { readonly artifactId: ArtifactId; readonly relation: string }[] {
  const parents = [
    { artifactId: input.manuscriptArtifactId, relation: "revision_manuscript" },
    ...(input.revisionContextArtifactId === undefined ? [] : [{ artifactId: input.revisionContextArtifactId, relation: "revision_context" }]),
    ...(input.workingNotesArtifactId === undefined ? [] : [{ artifactId: input.workingNotesArtifactId, relation: "revision_working_notes" }]),
    ...(input.findingDispositionsArtifactId === undefined ? [] : [{ artifactId: input.findingDispositionsArtifactId, relation: "revision_finding_dispositions" }]),
    ...input.reviewMaterialArtifactIds.map((artifactId) => ({ artifactId, relation: "revision_review_material" })),
    ...(input.previousRevisionRecordArtifactId === undefined ? [] : [{ artifactId: input.previousRevisionRecordArtifactId, relation: "previous_revision_record" }]),
    ...input.humanRulingArtifactIds.map((artifactId) => ({ artifactId, relation: "human_ruling" })),
  ];
  assertUniqueParents(parents);
  return Object.freeze(parents);
}

function assertUniqueParents(parents: readonly { readonly artifactId: ArtifactId }[]): void {
  if (new Set(parents.map((parent) => parent.artifactId)).size !== parents.length) {
    throw new Error("article revision artifact parents must be unique");
  }
}
