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

/** A capability describes what a worker can do. It never conveys authority. */
export type WorkerCapability =
  /** @deprecated Human eligibility is represented by OfferRequirements.authority. */
  | "human"
  | "image_model"
  | "source_access"
  | "source_blind"
  | "subprocess"
  | "text_model";

/** The principal class allowed to exercise an offer. */
export type WorkAuthority = "human" | "machine" | "model" | "tool";

/**
 * The assurance that must accompany a claim. `local_bearer` deliberately
 * records the present local-trust boundary without mistaking a capability for
 * an authorization system.
 */
export type WorkAssurance = "local_bearer";

/**
 * The complete eligibility policy for one offer. Authority and capability are
 * separate constraints: a human is an authority, never a capability.
 */
export type OfferRequirements = {
  readonly authority: WorkAuthority;
  readonly capabilities: readonly WorkerCapability[];
  readonly minimumAssurance: WorkAssurance;
};

export type WorkerIdentity = {
  readonly principalId: string;
  readonly authority: WorkAuthority;
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
  /** The authoritative eligibility policy for offers created under contract v3. */
  readonly requirements?: OfferRequirements;
  /**
   * @deprecated Compatibility projection for pre-v3 callers. New code must use
   * `requirements`; in particular, it must not use `human` as a capability.
   */
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
  /** 256-bit bearer secret, returned once and never included in projections or exports. */
  readonly ticket: string;
  readonly worker: WorkerIdentity;
  readonly leaseExpiresAt: string;
};

export type WorkAnswer = {
  readonly contractVersion: string;
  readonly result: JsonObject;
  readonly artifacts: readonly AnswerArtifact[];
  readonly metadata?: JsonObject;
};

/**
 * A human answer must bind itself to the active offer and its exact immutable
 * task context. The authorization decision is issued by RunEngine only after
 * this intent passes validation; callers cannot supply it.
 */
export type HumanDecisionIntent = {
  readonly schemaVersion: "human-decision-intent/1";
  readonly offerId: WorkOfferId;
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  /** Exact result object for the active role contract. */
  readonly result: JsonObject;
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
