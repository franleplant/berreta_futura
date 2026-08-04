import { createHash, randomUUID } from "node:crypto";

type Brand<Value, Name extends string> = Value & {
  readonly __brand: Name;
};

export type RunId = Brand<string, "RunId">;
/** Magazine-owned identity for one article execution. It is intentionally
 * independent from the root Loops run so the same article function can be
 * launched standalone or as an edition child. */
export type ArticleExecutionId = Brand<string, "ArticleExecutionId">;
/** Immutable revision identity for the manuscript an article worker sees. */
export type ManuscriptRevisionId = Brand<string, "ManuscriptRevisionId">;
export type ActorId = Brand<string, "ActorId">;
export type ArtifactId = Brand<string, "ArtifactId">;
export type RevisionId = Brand<string, "RevisionId">;
export type PromotionId = Brand<string, "PromotionId">;
export type IterationId = Brand<string, "IterationId">;
export type AttemptId = Brand<string, "AttemptId">;
export type WorkOfferId = Brand<string, "WorkOfferId">;
export type DecisionId = Brand<string, "DecisionId">;
export type EventId = Brand<string, "EventId">;
export type StateVisitId = Brand<string, "StateVisitId">;
export type InboxId = Brand<string, "InboxId">;
export type OutboxId = Brand<string, "OutboxId">;

export function newId<Id extends string>(prefix: string): Id {
  return `${prefix}_${randomUUID()}` as Id;
}

export function newRunId(): RunId {
  return newId<RunId>("run");
}

export function newArticleExecutionId(): ArticleExecutionId {
  return newId<ArticleExecutionId>("article-execution");
}

/** Stable article identity for callers that launch the same article function
 * standalone or as an edition child. Root Loops IDs are deliberately absent. */
export function articleExecutionIdFor(input: {
  readonly editionId: string;
  readonly articleId: string;
  readonly language: string;
  readonly revisionId?: string;
}): ArticleExecutionId {
  const identity = JSON.stringify({
    editionId: input.editionId,
    articleId: input.articleId,
    language: input.language,
    ...(input.revisionId === undefined ? {} : { revisionId: input.revisionId }),
  });
  return `article-execution-${createHash("sha256").update(identity, "utf8").digest("hex").slice(0, 32)}` as ArticleExecutionId;
}

export function newArtifactId(): ArtifactId {
  return newId<ArtifactId>("art");
}

export function newPromotionId(): PromotionId {
  return newId<PromotionId>("promotion");
}
