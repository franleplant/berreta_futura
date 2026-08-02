import type {
  ActorId,
  ArticlePromotionRequest,
  ArticlePromotionView,
  ArtifactId,
  ArtifactView,
  RunId,
  RunInputChange,
  RunOutcome,
  RunSpec,
  RunView,
  SubmitLeadRequest,
  WorkAnswer,
  WorkClaim,
  WorkFailure,
  WorkerIdentity,
  WorkOfferId,
} from "../contracts/index.ts";

export type RunEngineFailpoint =
  | "advance.after_effects"
  | "advance.after_commit"
  | "advance.before_commit"
  | "answer.after_artifact_rename"
  | "answer.after_commit"
  | "answer.before_artifact_commit"
  | "artifact.after_file_fsync"
  | "artifact.after_rename"
  | "artifact.before_rename"
  | "claim.after_commit"
  | "outbox.after_claim"
  | "outbox.after_effect_commit"
  | "outbox.before_effect_commit"
  | "seal.after_artifact_rename"
  | "seal.after_commit"
  | "start.after_artifact_rename"
  | "start.after_commit"
  | "start.before_commit";

export type FailpointContext = Readonly<Record<string, string | number | boolean | null>>;

export interface FailpointController {
  hit(name: RunEngineFailpoint, context?: FailpointContext): void;
}

export interface RunEngineClock {
  now(): Date;
}

export interface RunEngineIdGenerator {
  next<Id extends string>(prefix: string): Id;
}

export type RunEngineOptions = {
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly coordinatorId?: string;
  readonly coordinatorLeaseMs?: number;
  readonly workLeaseMs?: number;
  readonly busyTimeoutMs?: number;
  readonly artifactWriteLeaseMs?: number;
  readonly clock?: RunEngineClock;
  readonly ids?: RunEngineIdGenerator;
  readonly failpoints?: FailpointController;
};

export type StartRunOptions = {
  readonly idempotencyKey?: string;
};

export type ForkRunOptions = {
  readonly idempotencyKey?: string;
};

export type ReadArtifactResult = {
  readonly artifact: ArtifactView;
  readonly bytes: Uint8Array;
};

export interface RunEngine {
  start(spec: RunSpec, options?: StartRunOptions): Promise<RunOutcome>;
  advance(runId: RunId): Promise<RunOutcome>;
  retry(runId: RunId, actorId: ActorId): Promise<RunOutcome>;
  submitLead(runId: RunId, request: SubmitLeadRequest): Promise<RunView>;
  promoteArticle(
    runId: RunId,
    request: ArticlePromotionRequest,
  ): Promise<ArticlePromotionView>;
  inspect(runId: RunId): Promise<RunView>;
  fork(
    runId: RunId,
    changes: readonly RunInputChange[],
    options?: ForkRunOptions,
  ): Promise<RunOutcome>;
  claim(offerId: WorkOfferId, worker: WorkerIdentity): Promise<WorkClaim>;
  heartbeat(claim: WorkClaim): Promise<WorkClaim>;
  answer(claim: WorkClaim, answer: WorkAnswer): Promise<RunView>;
  fail(claim: WorkClaim, failure: WorkFailure): Promise<RunView>;
  readArtifact(artifactId: ArtifactId): Promise<ReadArtifactResult>;
  readBytes(artifactId: ArtifactId): Promise<Uint8Array>;
  readText(artifactId: ArtifactId): Promise<string>;
  collectOrphanedArtifacts(): Promise<readonly ArtifactId[]>;
  seal(runId: RunId): Promise<ArtifactId>;
  close(): void;
}

export class RunEngineError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "RunEngineError";
    this.code = code;
  }
}

export class StaleClaimError extends RunEngineError {
  constructor(message: string) {
    super("STALE_CLAIM", message);
    this.name = "StaleClaimError";
  }
}

export class MachineVersionError extends RunEngineError {
  constructor(message: string) {
    super("MACHINE_VERSION_MISMATCH", message);
    this.name = "MachineVersionError";
  }
}
