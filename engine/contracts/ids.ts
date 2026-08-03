import { randomUUID } from "node:crypto";

type Brand<Value, Name extends string> = Value & {
  readonly __brand: Name;
};

export type RunId = Brand<string, "RunId">;
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

export function newArtifactId(): ArtifactId {
  return newId<ArtifactId>("art");
}

export function newPromotionId(): PromotionId {
  return newId<PromotionId>("promotion");
}
