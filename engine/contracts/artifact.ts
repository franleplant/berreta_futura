import type {
  ActorId,
  ArtifactId,
  AttemptId,
  RunId,
  WorkOfferId,
} from "./ids.ts";
import type { JsonObject, JsonValue } from "./json.ts";

export type ArtifactOrigin =
  | "human"
  | "imported"
  | "machine"
  | "model"
  | "subprocess";

export type ArtifactPayload =
  | { readonly kind: "bytes"; readonly dataBase64: string }
  | { readonly kind: "file"; readonly path: string }
  | { readonly kind: "json"; readonly value: JsonValue }
  | { readonly kind: "text"; readonly text: string };

export type ArtifactSeed = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schemaVersion: string;
  readonly mediaType: string;
  readonly origin: ArtifactOrigin;
  readonly payload: ArtifactPayload;
  readonly parents?: readonly ArtifactParent[];
  readonly metadata?: JsonObject;
  readonly supersedes?: ArtifactId;
};

export type ArtifactParent = {
  readonly artifactId: ArtifactId;
  readonly relation: string;
};

export type AnswerArtifact = Omit<ArtifactSeed, "id" | "origin"> & {
  readonly id?: ArtifactId;
  readonly origin?: ArtifactOrigin;
};

export type ArtifactView = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schemaVersion: string;
  readonly mediaType: string;
  readonly origin: ArtifactOrigin;
  readonly sizeBytes: number;
  readonly parents: readonly ArtifactParent[];
  readonly producingRunId?: RunId;
  readonly producingActorId?: ActorId;
  readonly producingAttemptId?: AttemptId;
  readonly producingOfferId?: WorkOfferId;
  readonly supersedes?: ArtifactId;
  readonly metadata: JsonObject;
  readonly createdAt: string;
};
