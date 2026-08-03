import type {
  ActorId,
  ArticlePromotionRequest,
  ArticlePromotionView,
  ArtifactId,
  ArtifactView,
  EventId,
  JsonObject,
  HumanDecisionIntent,
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
import type { MachineKind } from "../machines/runtime.ts";
import type { AuthorizedWorker } from "../authority/local-authority.ts";

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
  | "snapshot_migration.before_commit"
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

/**
 * The compact public identity needed to discover runs in an explicitly
 * configured RunEngine home. Callers must not inspect SQLite directly merely
 * to learn which immutable run IDs a database contains.
 */
export type RunIdentityView = Pick<
  RunView,
  "id" | "kind" | "status" | "machineVersion" | "headSequence" | "createdAt" | "updatedAt"
> & { readonly metadata: JsonObject };

/** The execution graph is versioned as one bundle, never inferred from files. */
export type MachineBundleVersion = "graph-execution@1" | "graph-execution@2";

export type MigrationActorPlan = {
  readonly actorId: ActorId;
  readonly machine: MachineKind;
  readonly fromVersion: string;
  readonly toVersion: string;
  readonly snapshotNumber: number;
  readonly state: string;
};

/**
 * A read-only, deterministic description of a snapshot metadata migration.
 * The old snapshot remains immutable and is retained as the migration event's
 * declared backup. Applying a plan only appends equivalent snapshots; it
 * never dispatches a workflow event or replays authority.
 */
export type MigrationPlan = {
  readonly runId: RunId;
  readonly expectedFrom: MachineBundleVersion;
  readonly targetBundleVersion: MachineBundleVersion;
  readonly expectedHeadEventId: string;
  readonly actors: readonly MigrationActorPlan[];
};

export type PlanMigrationRequest = {
  readonly runId: RunId;
  readonly targetBundleVersion: MachineBundleVersion;
};

export type MigrationRequest = {
  readonly runId: RunId;
  readonly expectedFrom: MachineBundleVersion;
  readonly targetBundleVersion: MachineBundleVersion;
  readonly migrationId: string;
  readonly expectedHeadEventId: string;
  readonly idempotencyKey: string;
};

/**
 * A durable compare-and-swap fence used while a caller clones a complete
 * RunEngine home. While present, every public mutation for the database is
 * rejected, including work claims and heartbeats from already-open handles.
 */
export type RunMigrationFenceRequest = {
  readonly runId: RunId;
  readonly expectedHeadSequence: number;
  readonly expectedHeadEventId: EventId;
  readonly idempotencyKey: string;
};

export type RunMigrationFence = RunMigrationFenceRequest & {
  readonly schemaVersion: "run-migration-fence/1";
  readonly fenceId: string;
  readonly acquiredAt: string;
};

export type RunMigrationCheckpoint = {
  readonly busy: number;
  readonly log: number;
  readonly checkpointed: number;
};

/** Exact machine-owned context presented for one active human decision. */
export type HumanDecisionPreparation = {
  readonly schemaVersion: "human-decision-preparation/1";
  readonly claim: WorkClaim;
  readonly offerId: WorkOfferId;
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly allowedChoices: readonly string[];
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
  listRuns(): Promise<readonly RunIdentityView[]>;
  inspect(runId: RunId): Promise<RunView>;
  planMigration(request: PlanMigrationRequest): Promise<MigrationPlan>;
  migrate(request: MigrationRequest): Promise<MigrationPlan>;
  acquireMigrationFence(request: RunMigrationFenceRequest): Promise<RunMigrationFence>;
  checkpointMigrationFence(fence: RunMigrationFence): Promise<RunMigrationCheckpoint>;
  releaseMigrationFence(fence: RunMigrationFence): Promise<void>;
  fork(
    runId: RunId,
    changes: readonly RunInputChange[],
    options?: ForkRunOptions,
  ): Promise<RunOutcome>;
  /** Claims accept an authenticated session, never caller supplied identity data. */
  claimAuthorized(offerId: WorkOfferId, worker: AuthorizedWorker): Promise<WorkClaim>;
  prepareHumanDecision(
    offerId: WorkOfferId,
    worker: AuthorizedWorker,
  ): Promise<HumanDecisionPreparation>;
  decide(
    preparation: HumanDecisionPreparation,
    worker: AuthorizedWorker,
    intent: HumanDecisionIntent,
  ): Promise<RunView>;
  /**
   * @deprecated This compatibility declaration exists only to give old callers
   * a deterministic rejection. It never authorizes caller-supplied identity.
   */
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
