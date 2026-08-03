import type { AnswerArtifact } from "./artifact.ts";
import type {
  ActorId,
  ArtifactId,
  AttemptId,
  IterationId,
  RevisionId,
  RunId,
  StateVisitId,
  WorkOfferId,
} from "./ids.ts";
import type { JsonObject } from "./json.ts";

export const KNOWN_WORK_ROLES = [
  "capture_source",
  "extract_source",
  "review_source",
  "close_collection",
  "plan_edition",
  "writer",
  "measure_article",
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
  "editorial_writer",
  "edition_review",
  "translation_writer",
  "language_review",
  "language_fit",
  "cover_image",
  "interior_image",
  "select_art",
  "measure_edition",
  "render",
  "render_reconciliation",
  "render_inspection",
  "visual_review",
  "release_approval",
  "durable_checkpoint",
  "composition_bootstrap",
  "editor_decision",
] as const;

export type KnownWorkRole = (typeof KNOWN_WORK_ROLES)[number];

export type WorkRole = KnownWorkRole | (string & {});

export type WorkerCapability =
  | "human"
  | "image_model"
  | "source_access"
  | "source_blind"
  | "subprocess"
  | "text_model";

export type WorkerIdentity = {
  readonly principalId: string;
  readonly authority: "human" | "machine" | "model" | "tool";
  readonly capabilities: readonly WorkerCapability[];
  readonly displayName?: string;
};

export type WorkOfferStatus =
  | "offered"
  | "claimed"
  | "answered"
  | "canceled"
  | "failed"
  | "superseded";

export type WorkOfferView = {
  readonly id: WorkOfferId;
  readonly runId: RunId;
  readonly actorId: ActorId;
  readonly actorKey: string;
  readonly state: string;
  readonly stateVisitId: StateVisitId;
  readonly role: WorkRole;
  readonly slot: string;
  readonly subjectArtifactId?: ArtifactId;
  readonly iterationId?: IterationId;
  readonly revisionId?: RevisionId;
  readonly inputArtifacts: readonly ArtifactId[];
  readonly taskArtifactId: ArtifactId;
  readonly contractVersion: string;
  readonly allowedWorkerCapabilities: readonly WorkerCapability[];
  readonly status: WorkOfferStatus;
  readonly activeAttemptId?: AttemptId;
  readonly reusedFromRunId?: RunId;
  readonly reusedFromOfferId?: WorkOfferId;
  readonly reusedAnswerArtifactId?: ArtifactId;
  readonly createdAt: string;
};

export type WorkClaim = {
  readonly offerId: WorkOfferId;
  readonly attemptId: AttemptId;
  readonly attemptFence: number;
  readonly worker: WorkerIdentity;
  readonly leaseExpiresAt: string;
};

export type WorkAnswer = {
  readonly contractVersion: string;
  readonly result: JsonObject;
  readonly artifacts: readonly AnswerArtifact[];
  readonly metadata?: JsonObject;
};

export type WorkFailure = {
  readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
  readonly message: string;
  readonly details?: JsonObject;
};

export type AttemptView = {
  readonly id: AttemptId;
  readonly offerId: WorkOfferId;
  readonly attemptNumber: number;
  readonly fence: number;
  readonly worker: WorkerIdentity;
  readonly status: "active" | "answered" | "failed" | "stale" | "timed_out";
  readonly claimedAt: string;
  readonly leaseExpiresAt: string;
  readonly finishedAt?: string;
};
