import type Database from "better-sqlite3";
import { isDeepStrictEqual } from "node:util";

import type {
  ActorId,
  AnswerArtifact,
  ArticlePromotionRequest,
  ArticlePromotionView,
  ArtifactId,
  ArtifactOrigin,
  ArtifactPayload,
  ArtifactSeed,
  ArtifactView,
  AttemptId,
  DecisionId,
  EventId,
  InboxId,
  JsonObject,
  JsonValue,
  RunId,
  PromotionId,
  RevisionId,
  RunInputChange,
  RunOutcome,
  RunSpec,
  RunView,
  SourceRunSpec,
  StateVisitId,
  SubmitLeadRequest,
  WorkerCapability,
  WorkerIdentity,
  WorkAnswer,
  WorkClaim,
  WorkFailure,
  WorkOfferId,
} from "../contracts/index.ts";
import { newRevisionId } from "../durable/revision-id.ts";
import type { DurableLogicalItem, InputRevisionRef } from "../durable/types.ts";
import {
  assertRunSpecArtifactReferences,
  newId,
  parseRunSpec,
  parseSourceRunSpec,
  parseSubmitLeadRequest,
} from "../contracts/index.ts";
import type {
  JsonMachineSnapshot,
  MachineEffect,
  MachineKind,
  MachineTransitionResult,
} from "../machines/runtime.ts";
import {
  currentMachineVersion,
  initialSnapshotFor,
  transitionSnapshotFor,
} from "./machine-driver.ts";
import {
  completionRelationship,
  orchestrationRoute,
  orchestrationSpawn,
} from "../machines/orchestration.ts";
import {
  insertArtifactRecords,
  type ArtifactDisposition,
  type ArtifactRecord,
  recordFromSeed,
} from "./artifact-repository.ts";
import { ArtifactStore, type PreparedPayload } from "./artifact-store.ts";
import {
  assertDatabaseIntegrity,
  immediateTransaction,
  openRunDatabase,
} from "./database.ts";
import { inspectRun, loadOfferViews, outcomeFromView } from "./projection.ts";
import {
  applySpecPath,
  isoFromMs,
  jsonObject,
  parseJson,
  replaceArtifactReference,
  stableStringify,
  stateKey,
  stringifyJson,
} from "./serialization.ts";
import type {
  FailpointController,
  ForkRunOptions,
  ReadArtifactResult,
  RunEngine,
  RunEngineClock,
  RunEngineIdGenerator,
  RunEngineOptions,
  MigrationPlan,
  MigrationRequest,
  MigrationActorPlan,
  MachineBundleVersion,
  PlanMigrationRequest,
  RunIdentityView,
  RunMigrationCheckpoint,
  RunMigrationFence,
  RunMigrationFenceRequest,
  StartRunOptions,
} from "./types.ts";
import {
  MachineVersionError,
  RunEngineError,
  StaleClaimError,
} from "./types.ts";
import {
  assertWorkResultContractRegistered,
  validateWorkResult,
} from "./work-result-contracts.ts";

const DEFAULT_COORDINATOR_LEASE_MS = 30_000;
const DEFAULT_WORK_LEASE_MS = 15 * 60_000;
const DEFAULT_BUSY_TIMEOUT_MS = 5_000;
const DEFAULT_ARTIFACT_WRITE_LEASE_MS = 60 * 60_000;
const OUTBOX_RETRY_BASE_MS = 100;
const OUTBOX_RETRY_MAX_MS = 30_000;
const MAX_TRANSITIONS_PER_ADVANCE = 10_000;
const XSTATE_VERSION = "5.32.5";
const MACHINE_CONTRACT_VERSION = "machine-runtime/1";

/**
 * Snapshot migrations are deliberately narrow. A version may be listed here
 * only when restoring it under the replacement machine is observationally
 * equivalent: same state, same context, and no entry/always effects. Changed
 * work topology is not reconstructed by a metadata migration.
 */
export const machineBundleVersion = "graph-execution@2" as const;

const MACHINE_BUNDLE_V1 = "graph-execution@1" as const;
const MACHINE_BUNDLE_V2 = machineBundleVersion;

const SNAPSHOT_MIGRATION_ALLOWLIST: Readonly<
  Partial<Record<MachineKind, Readonly<Record<string, string>>>>
> = {
  article: { "article/2": "article/3" },
  editorial: { "editorial/1": "editorial/2" },
  cover_art: { "art/1": "art/2" },
  interior_art: { "art/1": "art/2" },
  edition: { "edition/2": "edition/3" },
};

const noFailpoints: FailpointController = { hit: () => undefined };
const systemClock: RunEngineClock = { now: () => new Date() };
const randomIds: RunEngineIdGenerator = {
  next: <Id extends string>(prefix: string): Id => newId<Id>(prefix),
};

type RunMutationRow = {
  readonly id: RunId;
  readonly kind: "article" | "edition";
  readonly status: string;
  readonly machine_name: MachineKind;
  readonly machine_version: string;
  readonly spec_json: string;
  readonly head_sequence: number;
  readonly version: number;
  readonly sealed_at: string | null;
};

type ActorMutationRow = {
  readonly id: ActorId;
  readonly run_id: RunId;
  readonly parent_actor_id: ActorId | null;
  readonly logical_key: string;
  readonly machine_name: MachineKind;
  readonly machine_version: string;
  readonly status: "accepting" | "active" | "done" | "failed";
  readonly current_state: string;
  readonly current_context_json: string;
  readonly current_snapshot_number: number;
  readonly current_visit_id: StateVisitId;
  readonly input_json: string;
};

type InboxRow = {
  readonly id: InboxId;
  readonly run_id: RunId;
  readonly actor_id: ActorId;
  readonly type: string;
  readonly payload_json: string;
  readonly causation_event_id: EventId | null;
  readonly correlation_id: string | null;
};

type OfferClaimRow = {
  readonly id: WorkOfferId;
  readonly run_id: RunId;
  readonly actor_id: ActorId;
  readonly role: string;
  readonly slot: string;
  readonly subject_artifact_id: ArtifactId | null;
  readonly task_artifact_id: ArtifactId;
  readonly contract_version: string;
  readonly status: string;
  readonly claim_fence: number;
  readonly active_attempt_id: AttemptId | null;
  readonly run_machine_name: MachineKind;
  readonly run_machine_version: string;
  readonly run_status: string;
  readonly run_sealed_at: string | null;
  readonly actor_machine_name: MachineKind;
  readonly actor_machine_version: string;
};

type AttemptClaimRow = {
  readonly id: AttemptId;
  readonly offer_id: WorkOfferId;
  readonly fence: number;
  readonly worker_principal_id: string;
  readonly worker_authority: WorkerIdentity["authority"];
  readonly worker_capabilities_json: string;
  readonly worker_display_name: string | null;
  readonly status: string;
  readonly lease_expires_at_ms: number;
};

type StoredArtifactRow = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schema_version: string;
  readonly media_type: string;
  readonly origin: ArtifactOrigin;
  readonly storage_kind: "file" | "inline";
  readonly inline_payload: Buffer | null;
  readonly relative_path: string | null;
  readonly size_bytes: number;
  readonly producing_run_id: RunId | null;
  readonly producing_actor_id: ActorId | null;
  readonly producing_attempt_id: AttemptId | null;
  readonly producing_offer_id: WorkOfferId | null;
  readonly supersedes_artifact_id: ArtifactId | null;
  readonly metadata_json: string;
  readonly created_at: string;
};

type ReusableOfferRow = {
  readonly ancestor_run_id: RunId;
  readonly ancestor_depth: number;
  readonly ancestor_offer_id: WorkOfferId;
  readonly actor_parent_id: ActorId | null;
  readonly actor_logical_key: string;
  readonly actor_machine_name: MachineKind;
  readonly actor_machine_version: string;
  readonly actor_input_json: string;
  readonly iteration_ordinal: number | null;
  readonly parent_manuscript_artifact_id: ArtifactId | null;
  readonly revision_id: string | null;
  readonly answer_artifact_id: ArtifactId;
};

type ReusedWorkAnswer = {
  readonly ancestorRunId: RunId;
  readonly ancestorOfferId: WorkOfferId;
  readonly answerArtifactId: ArtifactId;
  readonly result: JsonObject;
  readonly artifacts: readonly {
    readonly artifactId: ArtifactId;
    readonly kind: string;
  }[];
};

type PreparedEffect = {
  readonly effect: MachineEffect;
  readonly artifacts: readonly ArtifactRecord[];
  readonly spawned?: PreparedSpawn;
};

type OutboxDispatchRow = {
  readonly id: string;
  readonly run_id: RunId;
  readonly effect_id: string;
  readonly status: "pending" | "claimed" | "completed" | "failed";
  readonly claim_fence: number;
  readonly claim_holder: string | null;
  readonly claim_expires_at_ms: number | null;
  readonly available_at_ms: number;
  readonly attempts: number;
  readonly event_id: EventId;
  readonly ordinal: number;
  readonly params_json: string;
  readonly payload_json: string;
};

type ClaimedOutbox = OutboxDispatchRow & {
  readonly claim_fence: number;
  readonly claim_holder: string;
  readonly claim_expires_at_ms: number;
};

type PreparedEffectPayload = {
  readonly artifactIds: readonly ArtifactId[];
  readonly spawned?: {
    readonly actorId: ActorId;
    readonly machine: Exclude<MachineKind, "edition">;
    readonly logicalKey: string;
    readonly parentActorId: ActorId;
    readonly input: JsonObject;
    readonly snapshot: JsonMachineSnapshot;
  };
};

type PreparedSpawn = {
  readonly actorId: ActorId;
  readonly machine: Exclude<MachineKind, "edition">;
  readonly logicalKey: string;
  readonly parentActorId: ActorId;
  readonly input: JsonObject;
  readonly initial: MachineTransitionResult;
  readonly effects: readonly PreparedEffect[];
};

type Lease = {
  readonly runId: RunId;
  readonly fence: number;
  readonly expiresAtMs: number;
};

export class SqliteRunEngine implements RunEngine {
  private readonly db: Database.Database;
  private readonly store: ArtifactStore;
  readonly clock: RunEngineClock;
  readonly ids: RunEngineIdGenerator;
  readonly failpoints: FailpointController;
  readonly coordinatorId: string;
  readonly coordinatorLeaseMs: number;
  readonly workLeaseMs: number;
  readonly artifactWriteLeaseMs: number;
  private closed = false;

  constructor(options: RunEngineOptions) {
    this.clock = options.clock ?? systemClock;
    this.ids = options.ids ?? randomIds;
    this.failpoints = options.failpoints ?? noFailpoints;
    this.coordinatorId =
      options.coordinatorId ?? this.ids.next<string>("coordinator");
    this.coordinatorLeaseMs = options.coordinatorLeaseMs ?? DEFAULT_COORDINATOR_LEASE_MS;
    this.workLeaseMs = options.workLeaseMs ?? DEFAULT_WORK_LEASE_MS;
    this.artifactWriteLeaseMs =
      options.artifactWriteLeaseMs ?? DEFAULT_ARTIFACT_WRITE_LEASE_MS;
    const now = this.now();
    this.db = openRunDatabase({
      path: options.databasePath,
      busyTimeoutMs: options.busyTimeoutMs ?? DEFAULT_BUSY_TIMEOUT_MS,
      now,
    });
    this.store = new ArtifactStore(options.artifactDirectory, this.failpoints);
    assertDatabaseIntegrity(this.db);
  }

  async start(spec: RunSpec, options: StartRunOptions = {}): Promise<RunOutcome> {
    this.assertOpen();
    this.assertNoMigrationFences();
    const validatedSpec = parseRunSpec(spec);
    assertRunSpecArtifactReferences(
      validatedSpec,
      (artifactId) =>
        this.db.prepare("SELECT 1 FROM artifacts WHERE id = ?").get(artifactId) !== undefined,
    );
    this.assertRunSpecSourceProvenance(validatedSpec);
    const startKey = operationStartKey(
      options.idempotencyKey,
      this.ids.next<string>("start"),
    );
    const runId = this.createRun(
      validatedSpec,
      undefined,
      [],
      validatedSpec.artifacts,
      startKey,
    );
    return this.advance(runId);
  }

  async advance(runId: RunId): Promise<RunOutcome> {
    this.assertOpen();
    const lease = this.acquireCoordinatorLease(runId);
    if (lease === undefined) {
      return outcomeFromView(inspectRun(this.db, runId));
    }
    try {
      for (let transitionCount = 0; transitionCount < MAX_TRANSITIONS_PER_ADVANCE; transitionCount += 1) {
        const dispatched = this.dispatchNextOutbox(lease);
        if (dispatched === "completed") {
          continue;
        }
        if (dispatched === "blocked") {
          break;
        }
        const work = this.nextInbox(runId);
        if (work === undefined) {
          break;
        }
        const actor = this.requireActor(work.actor_id);
        this.assertMachineCurrent(actor.machine_name, actor.machine_version);
        const stored = this.db
          .prepare(
            `SELECT snapshot_json FROM actor_snapshots
             WHERE actor_id = ? AND snapshot_number = ?`,
          )
          .get(actor.id, actor.current_snapshot_number) as
          | { readonly snapshot_json: string }
          | undefined;
        if (stored === undefined) {
          throw new RunEngineError(
            "SNAPSHOT_MISSING",
            `Actor ${actor.id} snapshot ${actor.current_snapshot_number} is missing`,
          );
        }
        const snapshot = parseJson<JsonMachineSnapshot>(
          stored.snapshot_json,
          `actor ${actor.id} snapshot`,
        );
        const event = parseJson<JsonObject>(work.payload_json, `inbox ${work.id} payload`);
        const transition = transitionSnapshotFor(actor.machine_name, snapshot, event);
        const prepared = this.prepareEffects(
          runId,
          actor.id,
          transition.effects,
          `advance:${work.id}`,
        );
        this.failpoints.hit("advance.after_effects", {
          runId,
          actorId: actor.id,
          inboxId: work.id,
          effectCount: prepared.length,
        });
        const committed = this.commitTransition(lease, work, actor, transition.snapshot, prepared);
        if (!committed) {
          break;
        }
        this.failpoints.hit("advance.after_commit", {
          runId,
          actorId: actor.id,
          inboxId: work.id,
        });
      }
      const stillPending = this.nextInbox(runId);
      const stillDispatchable = this.nextOutbox(runId);
      if (
        stillPending !== undefined &&
        stillDispatchable === undefined
      ) {
        throw new RunEngineError(
          "TRANSITION_LIMIT",
          `Run ${runId} exceeded ${MAX_TRANSITIONS_PER_ADVANCE} transitions in one advance`,
        );
      }
    } finally {
      this.releaseCoordinatorLease(lease);
    }
    return outcomeFromView(inspectRun(this.db, runId));
  }

  async retry(runId: RunId, actorId: ActorId): Promise<RunOutcome> {
    this.assertOpen();
    const now = this.now();
    immediateTransaction(this.db, () => {
      const run = this.requireMutableRun(runId);
      if (isTerminalStatus(run.status)) {
        throw new RunEngineError(
          "RUN_TERMINAL",
          `Run ${runId} cannot retry actors while status is ${run.status}`,
        );
      }
      const actor = this.requireActor(actorId);
      if (actor.run_id !== runId) {
        throw new RunEngineError(
          "ACTOR_RUN_MISMATCH",
          `Actor ${actorId} does not belong to run ${runId}`,
        );
      }
      this.assertMachineCurrent(actor.machine_name, actor.machine_version);
      const stored = this.db
        .prepare(
          `SELECT snapshot_json FROM actor_snapshots
           WHERE actor_id = ? AND snapshot_number = ?`,
        )
        .get(actor.id, actor.current_snapshot_number) as
        | { readonly snapshot_json: string }
        | undefined;
      if (stored === undefined) {
        throw new RunEngineError(
          "SNAPSHOT_MISSING",
          `Actor ${actor.id} snapshot ${actor.current_snapshot_number} is missing`,
        );
      }
      const snapshot = parseJson<JsonMachineSnapshot>(
        stored.snapshot_json,
        `actor ${actor.id} snapshot`,
      );
      const preview = transitionSnapshotFor(actor.machine_name, snapshot, { type: "RETRY" });
      if (
        stateKey(preview.snapshot.value) === actor.current_state &&
        preview.effects.length === 0
      ) {
        throw new RunEngineError(
          "ACTOR_NOT_RETRYABLE",
          `Actor ${actor.id} cannot retry from ${actor.current_state}`,
        );
      }
      enqueueInbox(this.db, {
        id: this.ids.next<InboxId>("inbox"),
        runId,
        actorId,
        type: "RETRY",
        payload: { type: "RETRY" },
        idempotencyKey: `retry:${actor.current_visit_id}`,
        causationEventId: null,
        correlationId: actor.current_visit_id,
        availableAtMs: this.nowMs(),
        now,
      });
    })();
    return await this.advance(runId);
  }

  async submitLead(runId: RunId, request: SubmitLeadRequest): Promise<RunView> {
    this.assertOpen();
    let validated: SubmitLeadRequest;
    try {
      validated = parseSubmitLeadRequest(request);
    } catch (error) {
      throw new RunEngineError(
        "LEAD_SUBMISSION_INVALID",
        "Lead submission must contain one valid source specification and immutable artifacts",
        { cause: error },
      );
    }
    const source = parseSourceRunSpec(validated.source);
    const sourceReferences = sourceArtifactReferences(source);
    const referenceSet = new Set(sourceReferences);
    const seedIds = validated.artifacts.map((artifact) => artifact.id);
    if (new Set(seedIds).size !== seedIds.length) {
      throw new RunEngineError(
        "LEAD_SUBMISSION_INVALID",
        `Lead ${source.sourceId} repeats an artifact ID`,
      );
    }
    const unrelated = seedIds.find((artifactId) => !referenceSet.has(artifactId));
    if (unrelated !== undefined) {
      throw new RunEngineError(
        "LEAD_SUBMISSION_INVALID",
        `Lead ${source.sourceId} does not reference submitted artifact ${unrelated}`,
      );
    }
    this.assertSourceProvenance(source, validated.artifacts);

    this.requireOpenCollectionActor(runId, source.sourceId);
    const now = this.now();
    const holder = `lead:${runId}:${source.sourceId}:${this.ids.next<string>("submission")}`;
    const prepared = validated.artifacts.flatMap((seed) => {
      const record = this.prepareRunSeed(seed, now, runId, holder);
      return record === undefined ? [] : [record];
    });

    immediateTransaction(this.db, () => {
      const actor = this.requireOpenCollectionActor(runId, source.sourceId);
      const closing = this.db
        .prepare(
          `SELECT 1 FROM inbox
           WHERE run_id = ? AND actor_id = ? AND status = 'pending'
             AND (
               type = 'CLOSE_COLLECTION'
               OR (
                 type = 'WORK_COMPLETED'
                 AND json_extract(payload_json, '$.slot') = 'close_collection'
               )
             )
           LIMIT 1`,
        )
        .get(runId, actor.id);
      if (closing !== undefined) {
        throw new RunEngineError(
          "COLLECTION_CLOSING",
          `Edition run ${runId} already has a committed collection-close decision`,
        );
      }
      const duplicate = this.db
        .prepare(
          `SELECT 1 FROM edition_source_submissions
           WHERE run_id = ? AND source_id = ?`,
        )
        .get(runId, source.sourceId);
      if (duplicate !== undefined) {
        throw new RunEngineError(
          "LEAD_SOURCE_DUPLICATE",
          `Edition run ${runId} already contains source ${source.sourceId}`,
        );
      }

      this.insertPreparedArtifacts(prepared);
      sourceReferences.forEach((artifactId) => requireArtifactExists(this.db, artifactId));
      this.db.prepare(
        `INSERT INTO edition_source_submissions(
           run_id, source_id, source_spec_json, lead_artifact_id, submitted_at
         ) VALUES (?, ?, ?, ?, ?)`,
      ).run(
        runId,
        source.sourceId,
        stringifyJson(source as unknown as JsonObject),
        source.leadArtifact,
        now,
      );
      seedIds.forEach((artifactId, ordinal) => {
        this.db.prepare(
          `INSERT INTO run_inputs(run_id, input_name, ordinal, artifact_id)
           VALUES (?, ?, ?, ?)`,
        ).run(runId, `dynamic-source:${source.sourceId}:artifacts`, ordinal, artifactId);
      });
      sourceReferences.forEach((artifactId, ordinal) => {
        this.db.prepare(
          `INSERT INTO run_inputs(run_id, input_name, ordinal, artifact_id)
           VALUES (?, ?, ?, ?)`,
        ).run(runId, `dynamic-source:${source.sourceId}:references`, ordinal, artifactId);
      });
      enqueueInbox(this.db, {
        id: this.ids.next<InboxId>("inbox"),
        runId,
        actorId: actor.id,
        type: "LEAD_RECEIVED",
        payload: { type: "LEAD_RECEIVED", source: source as unknown as JsonObject },
        idempotencyKey: `lead:${source.sourceId}`,
        causationEventId: null,
        correlationId: source.sourceId,
        priority: -20,
        availableAtMs: this.nowMs(),
        now,
      });
    })();
    await this.advance(runId);
    return inspectRun(this.db, runId);
  }

  async claim(offerId: WorkOfferId, worker: WorkerIdentity): Promise<WorkClaim> {
    this.assertOpen();
    const now = this.now();
    const nowMs = this.nowMs();
    const leaseExpiresAtMs = nowMs + this.workLeaseMs;
    const claim = immediateTransaction(this.db, () => {
      let offer = this.requireOffer(offerId);
      this.requireMutableRun(offer.run_id);
      this.assertOfferMachineCurrent(offer);
      if (offer.run_sealed_at !== null) {
        throw new RunEngineError("RUN_SEALED", `Run ${offer.run_id} is sealed`);
      }
      if (isTerminalStatus(offer.run_status)) {
        throw new RunEngineError(
          "RUN_TERMINAL",
          `Run ${offer.run_id} is already ${offer.run_status}`,
        );
      }
      if (offer.status === "claimed" && offer.active_attempt_id !== null) {
        const active = this.db.prepare("SELECT * FROM attempts WHERE id = ?").get(
          offer.active_attempt_id,
        ) as AttemptClaimRow | undefined;
        if (active !== undefined && active.status === "active" && active.lease_expires_at_ms <= nowMs) {
          this.db.prepare(
            `UPDATE attempts SET status = 'timed_out', finished_at = ?,
               failure_classification = 'timeout', failure_message = 'Claim lease expired'
             WHERE id = ? AND status = 'active'`,
          ).run(now, active.id);
          this.db.prepare(
            `UPDATE work_offers SET status = 'offered', active_attempt_id = NULL,
               updated_at = ? WHERE id = ? AND active_attempt_id = ?`,
          ).run(now, offerId, active.id);
          offer = this.requireOffer(offerId);
        }
      }
      if (offer.status !== "offered" || offer.active_attempt_id !== null) {
        throw new RunEngineError("WORK_UNAVAILABLE", `Work offer ${offerId} is not available`);
      }
      const required = this.offerCapabilities(offerId);
      const available = new Set(worker.capabilities);
      const missing = required.filter((capability) => !available.has(capability));
      if (missing.length > 0) {
        throw new RunEngineError(
          "WORKER_CAPABILITY_MISMATCH",
          `Worker ${worker.principalId} lacks: ${missing.join(", ")}`,
        );
      }
      if (required.includes("human") && worker.authority !== "human") {
        throw new RunEngineError(
          "WORKER_AUTHORITY_MISMATCH",
          `Offer ${offerId} requires human authority`,
        );
      }
      const exposure = exposureClass(required);
      if (exposure !== undefined && offer.subject_artifact_id === null) {
        throw new RunEngineError(
          "EXPOSURE_SUBJECT_MISSING",
          `Isolated offer ${offerId} has no subject artifact`,
        );
      }
      if (exposure !== undefined && offer.subject_artifact_id !== null) {
        const opposite = exposure === "source_aware" ? "source_blind" : "source_aware";
        const conflict = this.db.prepare(
          `SELECT first_attempt_id FROM worker_exposures
           WHERE worker_principal_id = ? AND subject_artifact_id = ? AND exposure_class = ?`,
        ).get(worker.principalId, offer.subject_artifact_id, opposite);
        if (conflict !== undefined) {
          throw new RunEngineError(
            "WORKER_EXPOSURE_CONFLICT",
            `Worker ${worker.principalId} has incompatible permanent exposure for ${offer.subject_artifact_id}`,
          );
        }
      }
      const attemptId = this.ids.next<AttemptId>("attempt");
      const fence = offer.claim_fence + 1;
      const attemptNumber = (
        this.db
          .prepare("SELECT COALESCE(MAX(attempt_number), 0) + 1 AS value FROM attempts WHERE offer_id = ?")
          .get(offerId) as { readonly value: number }
      ).value;
      this.db.prepare(
        `INSERT INTO attempts(
          id, offer_id, attempt_number, fence, worker_principal_id,
          worker_authority, worker_capabilities_json, worker_display_name,
          status, claimed_at, lease_expires_at_ms, heartbeat_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)`,
      ).run(
        attemptId,
        offerId,
        attemptNumber,
        fence,
        worker.principalId,
        worker.authority,
        stringifyJson([...worker.capabilities].sort()),
        worker.displayName ?? null,
        now,
        leaseExpiresAtMs,
        nowMs,
      );
      if (exposure !== undefined && offer.subject_artifact_id !== null) {
        this.db.prepare(
          `INSERT OR IGNORE INTO worker_exposures(
            worker_principal_id, subject_artifact_id, exposure_class,
            first_attempt_id, exposed_at
          ) VALUES (?, ?, ?, ?, ?)`,
        ).run(worker.principalId, offer.subject_artifact_id, exposure, attemptId, now);
      }
      this.db.prepare(
        `UPDATE work_offers SET status = 'claimed', claim_fence = ?,
           active_attempt_id = ?, updated_at = ? WHERE id = ?`,
      ).run(fence, attemptId, now, offerId);
      return {
        offerId,
        attemptId,
        attemptFence: fence,
        worker,
        leaseExpiresAt: isoFromMs(leaseExpiresAtMs),
      } satisfies WorkClaim;
    })();
    this.failpoints.hit("claim.after_commit", { offerId, attemptId: claim.attemptId });
    return claim;
  }

  async heartbeat(claim: WorkClaim): Promise<WorkClaim> {
    this.assertOpen();
    const nowMs = this.nowMs();
    const expiresAtMs = nowMs + this.workLeaseMs;
    const renewed = immediateTransaction(this.db, () => {
      const offer = this.requireOffer(claim.offerId);
      this.requireMutableRun(offer.run_id);
      this.assertOfferMachineCurrent(offer);
      const attempt = this.requireAttempt(claim.attemptId);
      if (!claimMatches(attempt, claim) || !isActiveClaim(offer, attempt, nowMs)) {
        if (attempt.status === "active" && attempt.lease_expires_at_ms <= nowMs) {
          this.expireAttempt(offer, attempt, this.now());
        }
        return false;
      }
      this.db.prepare(
        "UPDATE attempts SET lease_expires_at_ms = ?, heartbeat_at_ms = ? WHERE id = ?",
      ).run(expiresAtMs, nowMs, attempt.id);
      return true;
    })();
    if (!renewed) {
      throw new StaleClaimError(`Claim ${claim.attemptId} is stale or expired`);
    }
    return { ...claim, leaseExpiresAt: isoFromMs(expiresAtMs) };
  }

  async answer(claim: WorkClaim, answer: WorkAnswer): Promise<RunView> {
    this.assertOpen();
    const offerBeforeCopy = this.requireOffer(claim.offerId);
    this.requireMutableRun(offerBeforeCopy.run_id);
    this.assertOfferMachineCurrent(offerBeforeCopy);
    const priorAttempt = this.requireAttempt(claim.attemptId);
    if (priorAttempt.status === "answered" && claimMatches(priorAttempt, claim)) {
      return inspectRun(this.db, offerBeforeCopy.run_id);
    }
    if (answer.contractVersion !== offerBeforeCopy.contract_version) {
      throw new RunEngineError(
        "ANSWER_CONTRACT_MISMATCH",
        `Answer uses ${answer.contractVersion}; offer requires ${offerBeforeCopy.contract_version}`,
      );
    }
    validateWorkResult(
      offerBeforeCopy.role,
      offerBeforeCopy.contract_version,
      answer.result,
      answer.artifacts,
    );
    const durableCheckpoint = offerBeforeCopy.role === "durable_checkpoint"
      ? this.assertDurableCheckpointAnswer(offerBeforeCopy, answer)
      : undefined;
    if (offerBeforeCopy.role === "render_reconciliation") {
      this.assertRenderReconciliationAnswer(offerBeforeCopy, answer);
    }
    const compositionBootstrap = offerBeforeCopy.role === "composition_bootstrap"
      ? this.assertCompositionBootstrapAnswer(offerBeforeCopy, answer)
      : undefined;
    this.assertExactHumanChoice(offerBeforeCopy, answer.result);
    const now = this.now();
    const provenance = this.offerProvenance(claim.offerId);
    const artifactOperationId = `answer:${claim.attemptId}:${claim.attemptFence}`;
    const outputRecords = answer.artifacts.map((artifact) =>
      this.prepareAnswerArtifact(
        artifact,
        claim,
        offerBeforeCopy,
        provenance,
        now,
        artifactOperationId,
      ),
    );
    const durableBound = durableCheckpoint === undefined
      ? undefined
      : this.prepareDurableRevisionBound(
          claim,
          offerBeforeCopy,
          durableCheckpoint,
          answer.result,
          outputRecords,
          now,
          artifactOperationId,
        );
    const bootstrapBound = compositionBootstrap === undefined
      ? undefined
      : this.prepareCompositionBootstrapBound(
          claim,
          offerBeforeCopy,
          answer.result,
          outputRecords,
          now,
        );
    const completedRecords = [
      ...outputRecords,
      ...(durableBound === undefined ? [] : [durableBound]),
      ...(bootstrapBound === undefined ? [] : [bootstrapBound]),
    ];
    const envelopeId = this.ids.next<ArtifactId>("art");
    const envelopePayload: ArtifactPayload = {
      kind: "json",
      value: {
        contractVersion: answer.contractVersion,
        result: answer.result,
        artifactIds: completedRecords.map((record) => record.id),
        ...(answer.metadata === undefined ? {} : { metadata: answer.metadata }),
      },
    };
    const envelope: ArtifactRecord = {
      id: envelopeId,
      kind: "work_answer",
      schemaVersion: answer.contractVersion,
      mediaType: "application/json",
      origin: originForWorker(claim.worker),
      payload: this.store.prepare(envelopeId, envelopePayload),
      parents: deduplicateParents([
        ...provenance,
        ...completedRecords.map((record) => ({
          artifactId: record.id,
          relation: "answer_output",
        })),
      ]),
      metadata: answer.metadata ?? {},
      disposition: "accepted",
      producingRunId: offerBeforeCopy.run_id,
      producingActorId: offerBeforeCopy.actor_id,
      producingAttemptId: claim.attemptId,
      producingOfferId: claim.offerId,
      createdAt: now,
    };
    const prepared = [...completedRecords, envelope];
    this.failpoints.hit("answer.after_artifact_rename", {
      offerId: claim.offerId,
      attemptId: claim.attemptId,
      artifactCount: prepared.length,
    });

    const accepted = immediateTransaction(this.db, () => {
      const offer = this.requireOffer(claim.offerId);
      this.requireMutableRun(offer.run_id);
      this.assertOfferMachineCurrent(offer);
      const attempt = this.requireAttempt(claim.attemptId);
      const active = claimMatches(attempt, claim) && isActiveClaim(offer, attempt, this.nowMs());
      const disposition: ArtifactDisposition = active ? "accepted" : "stale";
      this.insertPreparedArtifacts(
        prepared.map((record) => ({ ...record, disposition })),
      );
      this.db.prepare(
        `INSERT INTO attempt_submissions(
          id, attempt_id, offer_id, artifact_id, disposition, received_at
        ) VALUES (?, ?, ?, ?, ?, ?)`,
      ).run(
        this.ids.next<string>("submission"),
        attempt.id,
        offer.id,
        envelope.id,
        active ? "accepted" : "stale",
        now,
      );
      if (!active) {
        if (attempt.status === "active" && attempt.lease_expires_at_ms <= this.nowMs()) {
          this.expireAttempt(offer, attempt, now);
        }
        this.failpoints.hit("answer.before_artifact_commit", {
          offerId: offer.id,
          attemptId: attempt.id,
          accepted: false,
        });
        return false;
      }
      this.db.prepare(
        "UPDATE attempts SET status = 'answered', finished_at = ? WHERE id = ?",
      ).run(now, attempt.id);
      this.db.prepare(
        `UPDATE work_offers SET status = 'answered', active_attempt_id = NULL,
           updated_at = ? WHERE id = ?`,
      ).run(now, offer.id);
      enqueueInbox(this.db, {
        id: this.ids.next<InboxId>("inbox"),
        runId: offer.run_id,
        actorId: offer.actor_id,
        type: "WORK_COMPLETED",
        payload: {
          type: "WORK_COMPLETED",
          slot: offer.slot,
          offerId: offer.id,
          taskArtifactId: offer.task_artifact_id,
          artifacts: completedRecords.map((record) => ({
            artifactId: record.id,
            kind: record.kind,
          })).concat({ artifactId: envelope.id, kind: envelope.kind }),
          result: answer.result,
        },
        idempotencyKey: `work-answer:${attempt.id}:${attempt.fence}`,
        causationEventId: null,
        correlationId: offer.id,
        availableAtMs: this.nowMs(),
        now,
      });
      this.failpoints.hit("answer.before_artifact_commit", {
        offerId: offer.id,
        attemptId: attempt.id,
        accepted: true,
      });
      return true;
    })();
    this.failpoints.hit("answer.after_commit", {
      offerId: claim.offerId,
      attemptId: claim.attemptId,
      accepted,
    });
    if (accepted) {
      await this.advance(offerBeforeCopy.run_id);
    }
    return inspectRun(this.db, offerBeforeCopy.run_id);
  }

  async fail(claim: WorkClaim, failure: WorkFailure): Promise<RunView> {
    this.assertOpen();
    const now = this.now();
    const result = immediateTransaction(this.db, () => {
      const offer = this.requireOffer(claim.offerId);
      this.requireMutableRun(offer.run_id);
      this.assertOfferMachineCurrent(offer);
      const attempt = this.requireAttempt(claim.attemptId);
      if (!claimMatches(attempt, claim) || !isActiveClaim(offer, attempt, this.nowMs())) {
        if (attempt.status === "active" && attempt.lease_expires_at_ms <= this.nowMs()) {
          this.expireAttempt(offer, attempt, now);
        }
        return { accepted: false, runId: offer.run_id };
      }
      const attemptStatus = failure.classification === "timeout" ? "timed_out" : "failed";
      this.db.prepare(
        `UPDATE attempts SET status = ?, finished_at = ?, failure_classification = ?,
           failure_message = ?, failure_details_json = ? WHERE id = ?`,
      ).run(
        attemptStatus,
        now,
        failure.classification,
        failure.message,
        failure.details === undefined ? null : stringifyJson(failure.details),
        attempt.id,
      );
      this.db.prepare(
        `UPDATE work_offers SET status = ?, active_attempt_id = NULL, updated_at = ?
         WHERE id = ?`,
      ).run(failure.classification === "canceled" ? "canceled" : "failed", now, offer.id);
      enqueueInbox(this.db, {
        id: this.ids.next<InboxId>("inbox"),
        runId: offer.run_id,
        actorId: offer.actor_id,
        type: "WORK_FAILED",
        payload: {
          type: "WORK_FAILED",
          slot: offer.slot,
          classification: failure.classification,
          message: failure.message,
        },
        idempotencyKey: `work-failure:${attempt.id}:${attempt.fence}`,
        causationEventId: null,
        correlationId: offer.id,
        availableAtMs: this.nowMs(),
        now,
      });
      return { accepted: true, runId: offer.run_id };
    })();
    if (result.accepted) {
      await this.advance(result.runId);
    }
    return inspectRun(this.db, result.runId);
  }

  async fork(
    runId: RunId,
    changes: readonly RunInputChange[],
    options: ForkRunOptions = {},
  ): Promise<RunOutcome> {
    this.assertOpen();
    const parent = this.requireMutableRun(runId);
    let specObject = parseJson<JsonObject>(parent.spec_json, `run ${runId} spec`);
    specObject = this.materializeCollectedEditionSpec(runId, specObject);
    const original = specObject as unknown as RunSpec;
    const replacementSeeds: ArtifactSeed[] = [];
    const replacedArtifactIds = new Set<ArtifactId>();
    const changedSourceArtifacts = new Set<ArtifactId>();
    specObject = {
      ...(specObject as Readonly<Record<string, JsonValue>>),
      artifacts: [],
    };
    for (const change of changes) {
      if (change.kind === "replace_artifact") {
        const replaced = replaceArtifactReference(specObject, change.from, change.to.id);
        if (replaced.replacements === 0) {
          throw new RunEngineError(
            "FORK_ARTIFACT_NOT_REFERENCED",
            `Run ${runId} does not reference artifact ${change.from}`,
          );
        }
        specObject = replaced.value;
        replacementSeeds.push(change.to);
        replacedArtifactIds.add(change.from);
        changedSourceArtifacts.add(change.from);
        changedSourceArtifacts.add(change.to.id);
      } else {
        specObject = applySpecPath(specObject, change.path, change.value);
      }
    }
    if (specObject.kind === "edition") {
      const edition = jsonObject(specObject.edition, `run ${runId} edition spec`);
      const sources = Array.isArray(edition.sources) ? edition.sources : [];
      specObject = {
        ...specObject,
        edition: {
          ...edition,
          sources: sources.map((candidate) => {
            const source = jsonObject(candidate, `run ${runId} source spec`);
            const approvalDependsOn = [
              source.rawBundleArtifact,
              ...(Array.isArray(source.rawEvidenceArtifacts)
                ? source.rawEvidenceArtifacts
                : []),
              source.extractionArtifact,
              source.metadataArtifact,
            ].some(
              (artifactId) =>
                typeof artifactId === "string" && changedSourceArtifacts.has(artifactId as ArtifactId),
            );
            if (!approvalDependsOn) {
              return source;
            }
            const { approvalArtifact: _staleApproval, ...unapproved } = source;
            return unapproved;
          }),
        },
      };
    }
    const validationSpec = parseRunSpec({
      ...specObject,
      schemaVersion: 1,
      kind: original.kind,
      artifacts: [
        ...original.artifacts.filter((seed) => !replacedArtifactIds.has(seed.id)),
        ...replacementSeeds,
      ],
    });
    const forkedSpec = {
      ...validationSpec,
      artifacts: replacementSeeds,
    } as RunSpec;
    assertRunSpecArtifactReferences(
      forkedSpec,
      (artifactId) =>
        this.db.prepare("SELECT 1 FROM artifacts WHERE id = ?").get(artifactId) !== undefined,
    );
    this.assertRunSpecSourceProvenance(validationSpec);
    const forkId = this.createRun(
      forkedSpec,
      { parentRunId: runId, sequence: parent.head_sequence },
      changes,
      replacementSeeds,
      operationStartKey(
        options.idempotencyKey,
        this.ids.next<string>("fork-start"),
      ),
    );
    return this.advance(forkId);
  }

  async promoteArticle(
    runId: RunId,
    request: ArticlePromotionRequest,
  ): Promise<ArticlePromotionView> {
    this.assertOpen();
    const reviewer = request.reviewer.trim();
    const rationale = request.rationale.trim();
    if (!reviewer || !rationale) {
      throw new RunEngineError(
        "ARTICLE_PROMOTION_INVALID",
        "Article promotion requires a reviewer and rationale",
      );
    }
    const comparedRunIds = [...new Set(request.comparedRunIds)];
    if (!comparedRunIds.includes(runId)) {
      throw new RunEngineError(
        "ARTICLE_PROMOTION_INVALID",
        `Compared runs must include selected run ${runId}`,
      );
    }
    if (comparedRunIds.length !== request.comparedRunIds.length) {
      throw new RunEngineError(
        "ARTICLE_PROMOTION_INVALID",
        "Compared run IDs must be unique",
      );
    }

    const existing = this.loadArticlePromotion(runId);
    if (existing !== undefined) {
      if (
        existing.reviewer === reviewer &&
        existing.rationale === rationale &&
        sameStrings(existing.comparedRunIds, comparedRunIds)
      ) {
        return existing;
      }
      throw new RunEngineError(
        "ARTICLE_ALREADY_PROMOTED",
        `Article run ${runId} already has an immutable promotion decision`,
      );
    }

    const selectedRun = this.requireMutableRun(runId);
    this.assertMachineCurrent(selectedRun.machine_name, selectedRun.machine_version);
    if (selectedRun.kind !== "article") {
      throw new RunEngineError(
        "ARTICLE_PROMOTION_INVALID",
        `Run ${runId} is not an article run`,
      );
    }
    const candidates = comparedRunIds.map((candidateRunId) =>
      this.requireSettledArticleCandidate(candidateRunId),
    );
    const selected = candidates.find((candidate) => candidate.runId === runId);
    if (selected === undefined) {
      throw new RunEngineError(
        "ARTICLE_PROMOTION_INVALID",
        `Selected run ${runId} has no settled manuscript`,
      );
    }
    const selectedSpec = parseJson<JsonObject>(
      selectedRun.spec_json,
      `article run ${runId} spec`,
    );
    const article = jsonObject(selectedSpec.article, `article run ${runId} article spec`);
    const policyArtifactId = this.ids.next<ArtifactId>("art");
    const promotionId = this.ids.next<string>("promotion");
    const now = this.now();
    const policyValue: JsonObject = {
      schemaVersion: "article-promotion-policy/1",
      selectedRunId: runId,
      selectedArtifactId: selected.manuscriptArtifactId,
      reviewer,
      rationale,
      comparedRunIds,
      configuration: {
        articleId: article.articleId ?? null,
        articleBrief: article.articleBrief ?? null,
        writerPrompt: article.writerPrompt ?? null,
        judgePrompts: article.judgePrompts ?? {},
        writingRules: article.writingRules ?? null,
        policy: article.policy ?? {},
        modelPolicy: article.modelPolicy ?? {},
      },
    };
    const configurationParents = this.db
      .prepare(
        `SELECT artifact_id FROM run_inputs
         WHERE run_id = ? ORDER BY input_name, ordinal`,
      )
      .all(runId) as readonly { readonly artifact_id: ArtifactId }[];
    const record: ArtifactRecord = {
      id: policyArtifactId,
      kind: "article_promotion_policy",
      schemaVersion: "article-promotion-policy/1",
      mediaType: "application/json",
      origin: "human",
      payload: this.store.prepare(policyArtifactId, { kind: "json", value: policyValue }),
      parents: deduplicateParents([
        {
          artifactId: selected.manuscriptArtifactId,
          relation: "selected_manuscript",
        },
        ...candidates.map((candidate) => ({
          artifactId: candidate.manuscriptArtifactId,
          relation: "compared_candidate",
        })),
        ...configurationParents.map((parent) => ({
          artifactId: parent.artifact_id,
          relation: "selected_configuration_input",
        })),
      ]),
      metadata: {
        reviewer,
        selectedRunId: runId,
        comparisonCount: comparedRunIds.length,
      },
      disposition: "accepted",
      producingRunId: runId,
      producingActorId: selected.actorId,
      createdAt: now,
    };

    immediateTransaction(this.db, () => {
      const current = this.requireMutableRun(runId);
      if (current.status !== "complete" || current.head_sequence !== selectedRun.head_sequence) {
        throw new RunEngineError(
          "ARTICLE_PROMOTION_STALE",
          `Article run ${runId} changed while promotion was prepared`,
        );
      }
      const duplicate = this.loadArticlePromotion(runId);
      if (duplicate !== undefined) {
        throw new RunEngineError(
          "ARTICLE_ALREADY_PROMOTED",
          `Article run ${runId} was promoted concurrently`,
        );
      }
      insertArtifactRecords(this.db, [record]);
      this.db.prepare(
        `INSERT INTO article_promotions(
          id, run_id, selected_artifact_id, policy_artifact_id,
          reviewer, rationale, compared_run_ids_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        promotionId,
        runId,
        selected.manuscriptArtifactId,
        policyArtifactId,
        reviewer,
        rationale,
        stringifyJson(comparedRunIds),
        now,
      );
      this.db.prepare(
        `INSERT INTO run_outputs(run_id, output_name, ordinal, artifact_id)
         VALUES (?, 'article_promotion_policy', 0, ?)`,
      ).run(runId, policyArtifactId);
    })();
    return {
      id: promotionId,
      runId,
      selectedArtifactId: selected.manuscriptArtifactId,
      policyArtifactId,
      reviewer,
      rationale,
      comparedRunIds,
      createdAt: now,
    };
  }

  async seal(runId: RunId): Promise<ArtifactId> {
    this.assertOpen();
    const existing = this.db.prepare("SELECT artifact_id FROM sealed_exports WHERE run_id = ?").get(
      runId,
    ) as { readonly artifact_id: ArtifactId } | undefined;
    if (existing !== undefined) {
      return existing.artifact_id;
    }
    const run = this.requireMutableRun(runId);
    this.assertMachineCurrent(run.machine_name, run.machine_version);
    if (!isTerminalStatus(run.status)) {
      throw new RunEngineError(
        "RUN_NOT_TERMINAL",
        `Run ${runId} cannot be sealed while status is ${run.status}`,
      );
    }
    const view = inspectRun(this.db, runId);
    const now = this.now();
    const artifactId = this.ids.next<ArtifactId>("art");
    const exportText = stableStringify(view as unknown as JsonObject);
    const outputRows = this.db
      .prepare("SELECT artifact_id FROM run_outputs WHERE run_id = ? ORDER BY output_name, ordinal")
      .all(runId) as readonly { readonly artifact_id: ArtifactId }[];
    const record: ArtifactRecord = {
      id: artifactId,
      kind: "sealed_run_export",
      schemaVersion: "run-export/1",
      mediaType: "application/json",
      origin: "machine",
      payload: this.store.prepare(artifactId, { kind: "text", text: exportText }),
      parents: deduplicateParents(
        outputRows.map((row) => ({ artifactId: row.artifact_id, relation: "run_output" })),
      ),
      metadata: { runId, headSequence: run.head_sequence },
      disposition: "accepted",
      producingRunId: runId,
      createdAt: now,
    };
    this.failpoints.hit("seal.after_artifact_rename", { runId, artifactId });
    immediateTransaction(this.db, () => {
      const current = this.requireMutableRun(runId);
      this.assertMachineCurrent(current.machine_name, current.machine_version);
      if (current.head_sequence !== run.head_sequence || current.status !== run.status) {
        throw new RunEngineError(
          "RUN_CHANGED_DURING_SEAL",
          `Run ${runId} changed while its export was prepared`,
        );
      }
      if (!isTerminalStatus(current.status)) {
        throw new RunEngineError("RUN_NOT_TERMINAL", `Run ${runId} is no longer terminal`);
      }
      insertArtifactRecords(this.db, [record]);
      this.db.prepare(
        `INSERT INTO run_outputs(run_id, output_name, ordinal, artifact_id)
         VALUES (?, 'sealed_export', 0, ?)`,
      ).run(runId, artifactId);
      this.db.prepare(
        `INSERT INTO sealed_exports(run_id, head_sequence, artifact_id, created_at)
         VALUES (?, ?, ?, ?)`,
      ).run(runId, current.head_sequence, artifactId, now);
      this.db.prepare("UPDATE runs SET sealed_at = ?, updated_at = ? WHERE id = ?").run(
        now,
        now,
        runId,
      );
    })();
    this.failpoints.hit("seal.after_commit", { runId, artifactId });
    return artifactId;
  }

  private acquireCoordinatorLease(runId: RunId): Lease | undefined {
    const nowMs = this.nowMs();
    const expiresAtMs = nowMs + this.coordinatorLeaseMs;
    return immediateTransaction(this.db, () => {
      const run = this.requireMutableRun(runId);
      this.assertMachineCurrent(run.machine_name, run.machine_version);
      if (isTerminalStatus(run.status)) {
        return undefined;
      }
      const existing = this.db.prepare("SELECT * FROM run_leases WHERE run_id = ?").get(runId) as
        | { readonly holder_id: string; readonly fence: number; readonly expires_at_ms: number }
        | undefined;
      if (
        existing !== undefined &&
        existing.expires_at_ms > nowMs &&
        existing.holder_id !== this.coordinatorId
      ) {
        return undefined;
      }
      const fence = (existing?.fence ?? 0) + 1;
      this.db.prepare(
        `INSERT INTO run_leases(run_id, holder_id, fence, expires_at_ms, heartbeat_at_ms)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(run_id) DO UPDATE SET
           holder_id = excluded.holder_id,
           fence = excluded.fence,
           expires_at_ms = excluded.expires_at_ms,
           heartbeat_at_ms = excluded.heartbeat_at_ms`,
      ).run(runId, this.coordinatorId, fence, expiresAtMs, nowMs);
      return { runId, fence, expiresAtMs };
    })();
  }

  private releaseCoordinatorLease(lease: Lease): void {
    immediateTransaction(this.db, () => {
      this.db.prepare(
        `UPDATE run_leases SET expires_at_ms = 0, heartbeat_at_ms = ?
         WHERE run_id = ? AND holder_id = ? AND fence = ?`,
      ).run(this.nowMs(), lease.runId, this.coordinatorId, lease.fence);
    })();
  }

  private nextOutbox(runId: RunId): OutboxDispatchRow | undefined {
    return this.db
      .prepare(
        `SELECT o.*, te.event_id, te.ordinal, te.params_json
         FROM outbox o
         JOIN transition_effects te ON te.id = o.effect_id
         JOIN events e ON e.id = te.event_id
         WHERE o.run_id = ? AND o.status <> 'completed'
         ORDER BY e.sequence, te.ordinal, o.created_at, o.id
         LIMIT 1`,
      )
      .get(runId) as OutboxDispatchRow | undefined;
  }

  private claimNextOutbox(lease: Lease): ClaimedOutbox | "blocked" | undefined {
    const nowMs = this.nowMs();
    return immediateTransaction(this.db, () => {
      const liveLease = this.db
        .prepare("SELECT holder_id, fence, expires_at_ms FROM run_leases WHERE run_id = ?")
        .get(lease.runId) as
        | { readonly holder_id: string; readonly fence: number; readonly expires_at_ms: number }
        | undefined;
      if (
        liveLease === undefined ||
        liveLease.holder_id !== this.coordinatorId ||
        liveLease.fence !== lease.fence ||
        liveLease.expires_at_ms <= nowMs
      ) {
        return undefined;
      }
      const candidate = this.nextOutbox(lease.runId);
      if (candidate === undefined) {
        return undefined;
      }
      const reclaimable =
        (candidate.status === "pending" || candidate.status === "failed") &&
          candidate.available_at_ms <= nowMs ||
        candidate.status === "claimed" &&
          (candidate.claim_expires_at_ms ?? 0) <= nowMs;
      if (!reclaimable) {
        return "blocked";
      }
      const fence = candidate.claim_fence + 1;
      const expiresAtMs = nowMs + this.coordinatorLeaseMs;
      const updated = this.db.prepare(
        `UPDATE outbox SET
           status = 'claimed', claim_holder = ?, claim_fence = ?,
           claim_expires_at_ms = ?, attempts = attempts + 1,
           last_error = NULL
         WHERE id = ? AND claim_fence = ? AND status = ?`,
      ).run(
        this.coordinatorId,
        fence,
        expiresAtMs,
        candidate.id,
        candidate.claim_fence,
        candidate.status,
      );
      if (updated.changes !== 1) {
        return "blocked";
      }
      return {
        ...candidate,
        status: "claimed" as const,
        claim_holder: this.coordinatorId,
        claim_fence: fence,
        claim_expires_at_ms: expiresAtMs,
        attempts: candidate.attempts + 1,
      } as ClaimedOutbox;
    })();
  }

  private dispatchNextOutbox(lease: Lease): "completed" | "blocked" | "empty" {
    const claimed = this.claimNextOutbox(lease);
    if (claimed === undefined) {
      return "empty";
    }
    if (claimed === "blocked") {
      return "blocked";
    }
    this.failpoints.hit("outbox.after_claim", {
      runId: claimed.run_id,
      outboxId: claimed.id,
      fence: claimed.claim_fence,
    });
    try {
      const effect = parseJson<MachineEffect>(
        claimed.params_json,
        `transition effect ${claimed.effect_id}`,
      );
      const payload = parsePreparedEffectPayload(claimed.payload_json, claimed.id);
      immediateTransaction(this.db, () => {
        const now = this.now();
        const nowMs = this.nowMs();
        const live = this.db
          .prepare(
            `SELECT status, claim_holder, claim_fence, claim_expires_at_ms
             FROM outbox WHERE id = ?`,
          )
          .get(claimed.id) as
          | {
              readonly status: string;
              readonly claim_holder: string | null;
              readonly claim_fence: number;
              readonly claim_expires_at_ms: number | null;
            }
          | undefined;
        if (
          live?.status !== "claimed" ||
          live.claim_holder !== this.coordinatorId ||
          live.claim_fence !== claimed.claim_fence ||
          (live.claim_expires_at_ms ?? 0) <= nowMs
        ) {
          throw new RunEngineError(
            "OUTBOX_CLAIM_STALE",
            `Outbox effect ${claimed.id} lost its dispatch fence`,
          );
        }
        const run = this.requireMutableRun(claimed.run_id);
        const cursor = { sequence: run.head_sequence };
        this.applyDispatchedEffect(
          claimed.run_id,
          claimed.event_id,
          effect,
          payload,
          cursor,
          now,
          nowMs,
        );
        const completed = this.db.prepare(
          `UPDATE outbox SET status = 'completed', completed_at = ?,
             claim_expires_at_ms = NULL, last_error = NULL
           WHERE id = ? AND status = 'claimed' AND claim_holder = ? AND claim_fence = ?`,
        ).run(now, claimed.id, this.coordinatorId, claimed.claim_fence);
        if (completed.changes !== 1) {
          throw new RunEngineError(
            "OUTBOX_CLAIM_STALE",
            `Outbox effect ${claimed.id} could not commit its dispatch`,
          );
        }
        this.reconcileRunStatus(claimed.run_id, cursor.sequence, now);
        this.db.prepare(
          `UPDATE run_leases SET expires_at_ms = ?, heartbeat_at_ms = ?
           WHERE run_id = ? AND holder_id = ? AND fence = ?`,
        ).run(
          nowMs + this.coordinatorLeaseMs,
          nowMs,
          claimed.run_id,
          this.coordinatorId,
          lease.fence,
        );
        this.failpoints.hit("outbox.before_effect_commit", {
          runId: claimed.run_id,
          outboxId: claimed.id,
          fence: claimed.claim_fence,
        });
      })();
    } catch (error) {
      if (error instanceof RunEngineError && error.code !== "OUTBOX_CLAIM_STALE") {
        const retryAtMs = this.nowMs() + outboxRetryDelay(claimed.attempts);
        immediateTransaction(this.db, () => {
          this.db.prepare(
            `UPDATE outbox SET status = 'failed', claim_holder = NULL,
               claim_expires_at_ms = NULL, available_at_ms = ?, last_error = ?
             WHERE id = ? AND status = 'claimed' AND claim_holder = ? AND claim_fence = ?`,
          ).run(
            retryAtMs,
            error.message,
            claimed.id,
            this.coordinatorId,
            claimed.claim_fence,
          );
        })();
      }
      throw error;
    }
    this.failpoints.hit("outbox.after_effect_commit", {
      runId: claimed.run_id,
      outboxId: claimed.id,
      fence: claimed.claim_fence,
    });
    return "completed";
  }

  private applyDispatchedEffect(
    runId: RunId,
    eventId: EventId,
    effect: MachineEffect,
    payload: PreparedEffectPayload,
    cursor: { sequence: number },
    now: string,
    nowMs: number,
  ): void {
    switch (effect.type) {
      case "create_work_offer":
        this.applyCreateOffer(runId, eventId, effect, now);
        break;
      case "open_durable_checkpoint":
        this.applyOpenDurableCheckpoint(runId, eventId, effect, now);
        break;
      case "spawn_actor": {
        if (payload.spawned === undefined) {
          throw new RunEngineError(
            "SPAWN_NOT_PREPARED",
            `Spawn effect for ${effect.logicalKey} has no durable actor identity`,
          );
        }
        this.applySpawn(
          runId,
          eventId,
          effect,
          {
            ...payload.spawned,
            initial: { snapshot: payload.spawned.snapshot, effects: [] },
            effects: [],
          },
          cursor,
          now,
          nowMs,
        );
        break;
      }
      case "send_actor_event":
        this.applySendActorEvent(runId, eventId, effect, now, nowMs);
        break;
      case "register_artifact": {
        const artifactId = payload.artifactIds[0];
        if (artifactId === undefined || payload.artifactIds.length !== 1) {
          throw new RunEngineError(
            "EFFECT_ARTIFACT_MISSING",
            `Register artifact effect ${effect.slot} has no durable artifact identity`,
          );
        }
        requireArtifactExists(this.db, artifactId);
        this.db.prepare(
          `INSERT INTO run_outputs(run_id, output_name, ordinal, artifact_id)
           VALUES (?, ?, 0, ?)
           ON CONFLICT(run_id, output_name, ordinal)
           DO UPDATE SET artifact_id = excluded.artifact_id`,
        ).run(runId, `${effect.actorId}:${effect.slot}`, artifactId);
        break;
      }
      case "record_decision":
        this.applyDecision(runId, eventId, effect, now);
        break;
      case "cancel_offer":
        this.applyCancelOffer(eventId, effect.actorId, effect.slot, effect.reason, now);
        break;
      case "complete_actor":
        try {
          this.applyCompleteActor(runId, eventId, effect, now, nowMs);
        } catch (error) {
          if (!(error instanceof RunEngineError) || error.code !== "SOURCE_ALREADY_RELEASED") {
            throw error;
          }
          this.applyFailActor(
            runId,
            eventId,
            {
              type: "fail_actor",
              actorId: effect.actorId,
              classification: "source_already_released",
              message: error.message,
              details: { code: error.code },
            },
            now,
            nowMs,
          );
        }
        break;
      case "fail_actor":
        this.applyFailActor(runId, eventId, effect, now, nowMs);
        break;
    }
  }

  private nextInbox(runId: RunId): InboxRow | undefined {
    return this.db
      .prepare(
        `SELECT * FROM inbox
         WHERE run_id = ? AND status = 'pending' AND available_at_ms <= ?
         ORDER BY available_at_ms, priority, created_at, id LIMIT 1`,
      )
      .get(runId, this.nowMs()) as InboxRow | undefined;
  }

  private prepareEffects(
    runId: RunId,
    actorId: ActorId,
    effects: readonly MachineEffect[],
    artifactOperationId: string,
  ): readonly PreparedEffect[] {
    const now = this.now();
    return effects.map((effect): PreparedEffect => {
      const effectActorId = effect.type === "spawn_actor" ? effect.parentActorId : effect.actorId;
      if (effectActorId !== actorId) {
        throw new RunEngineError(
          "EFFECT_ACTOR_MISMATCH",
          `Actor ${actorId} emitted ${effect.type} for actor ${effectActorId}`,
        );
      }
      if (effect.type === "register_artifact") {
        const artifact = effect.artifact;
        const id = artifact.id ?? this.ids.next<ArtifactId>("art");
        const seed: ArtifactSeed = {
          id,
          kind: artifact.kind,
          schemaVersion: artifact.schemaVersion,
          mediaType: artifact.mediaType,
          origin: artifact.origin ?? "machine",
          payload: artifact.payload,
          ...(artifact.parents === undefined ? {} : { parents: artifact.parents }),
          ...(artifact.metadata === undefined ? {} : { metadata: artifact.metadata }),
          ...(artifact.supersedes === undefined ? {} : { supersedes: artifact.supersedes }),
        };
        const record: ArtifactRecord = {
          ...recordFromSeed(
            seed,
            this.prepareOwnedPayload(id, seed.payload, artifactOperationId),
            now,
            runId,
          ),
          disposition: "accepted",
          producingActorId: actorId,
        };
        return { effect, artifacts: [record] };
      }
      if (effect.type === "open_durable_checkpoint") {
        return { effect, artifacts: [] };
      }
      if (effect.type === "spawn_actor") {
        const childActorId = this.ids.next<ActorId>("actor");
        const input: JsonObject = {
          actorId: childActorId,
          logicalKey: effect.logicalKey,
          parentActorId: effect.parentActorId,
          spec: effect.spec as unknown as JsonObject,
        };
        const initial = initialSnapshotFor(effect.machine, input);
        if (initial.effects.length > 0) {
          throw new RunEngineError(
            "MACHINE_INITIAL_EFFECTS",
            `Machine ${effect.machine} must enter idle without effects before durable START`,
          );
        }
        const childEffects: readonly PreparedEffect[] = [];
        return {
          effect,
          artifacts: flattenEffectArtifacts(childEffects),
          spawned: {
            actorId: childActorId,
            machine: effect.machine,
            logicalKey: effect.logicalKey,
            parentActorId: effect.parentActorId,
            input,
            initial,
            effects: childEffects,
          },
        };
      }
      return { effect, artifacts: [] };
    });
  }

  private commitTransition(
    lease: Lease,
    inbox: InboxRow,
    expectedActor: ActorMutationRow,
    snapshot: JsonMachineSnapshot,
    effects: readonly PreparedEffect[],
  ): boolean {
    const now = this.now();
    const nowMs = this.nowMs();
    return immediateTransaction(this.db, () => {
      const liveLease = this.db
        .prepare("SELECT * FROM run_leases WHERE run_id = ?")
        .get(lease.runId) as
        | { readonly holder_id: string; readonly fence: number; readonly expires_at_ms: number }
        | undefined;
      if (
        liveLease === undefined ||
        liveLease.holder_id !== this.coordinatorId ||
        liveLease.fence !== lease.fence ||
        liveLease.expires_at_ms <= nowMs
      ) {
        return false;
      }
      const liveInbox = this.db.prepare("SELECT status FROM inbox WHERE id = ?").get(inbox.id) as
        | { readonly status: string }
        | undefined;
      const actor = this.requireActor(expectedActor.id);
      if (
        liveInbox?.status !== "pending" ||
        actor.current_snapshot_number !== expectedActor.current_snapshot_number
      ) {
        return false;
      }
      this.assertMachineCurrent(actor.machine_name, actor.machine_version);
      const run = this.requireMutableRun(lease.runId);
      this.assertMachineCurrent(run.machine_name, run.machine_version);
      this.insertPreparedArtifacts(flattenEffectArtifacts(effects));

      const eventId = this.ids.next<EventId>("event");
      const sequence = run.head_sequence + 1;
      const nextSnapshotNumber = actor.current_snapshot_number + 1;
      insertSnapshotEvent(this.db, {
        eventId,
        runId: lease.runId,
        sequence,
        actorId: actor.id,
        type: inbox.type,
        payload: parseJson<JsonObject>(inbox.payload_json, `inbox ${inbox.id} payload`),
        previousSnapshotNumber: actor.current_snapshot_number,
        nextSnapshotNumber,
        previousState: actor.current_state,
        snapshot,
        machineVersion: actor.machine_version,
        causationEventId: inbox.causation_event_id,
        correlationId: inbox.correlation_id,
        inboxId: inbox.id,
        now,
      });

      let visitId = actor.current_visit_id;
      const nextState = stateKey(snapshot.value);
      const reentersCurrentState =
        nextState === actor.current_state &&
        effects.some(
          ({ effect }) =>
            effect.type === "create_work_offer" &&
            effect.actorId === actor.id &&
            effect.state === nextState,
        );
      const exitsCurrentVisit =
        nextState !== actor.current_state || reentersCurrentState;
      if (exitsCurrentVisit) {
        this.db.prepare(
          "UPDATE state_visits SET exited_event_id = ? WHERE id = ? AND exited_event_id IS NULL",
        ).run(eventId, actor.current_visit_id);
        this.cancelVisitOutstandingOffers(
          actor.current_visit_id,
          eventId,
          `Actor ${actor.id} exited state visit ${actor.current_visit_id}`,
          now,
        );
        visitId = this.ids.next<StateVisitId>("visit");
        const visitNumber = (
          this.db
            .prepare("SELECT COALESCE(MAX(visit_number), 0) + 1 AS value FROM state_visits WHERE actor_id = ?")
            .get(actor.id) as { readonly value: number }
        ).value;
        this.db.prepare(
          `INSERT INTO state_visits(
            id, actor_id, state_key, visit_number, entered_event_id, created_at
          ) VALUES (?, ?, ?, ?, ?, ?)`,
        ).run(visitId, actor.id, nextState, visitNumber, eventId, now);
      }

      this.db.prepare(
        `UPDATE actors SET
          current_state = ?, current_context_json = ?, current_snapshot_number = ?,
          current_visit_id = ?,
          status = CASE WHEN ? THEN 'active' ELSE status END,
          updated_at = ?
         WHERE id = ?`,
      ).run(
        nextState,
        stringifyJson(snapshot.context),
        nextSnapshotNumber,
        visitId,
        exitsCurrentVisit ? 1 : 0,
        now,
        actor.id,
      );

      this.recordEffects(lease.runId, eventId, effects, now, nowMs);
      this.db.prepare(
        `UPDATE inbox SET status = 'consumed', consumed_event_id = ?
         WHERE id = ? AND status = 'pending'`,
      ).run(eventId, inbox.id);
      this.reconcileRunStatus(lease.runId, sequence, now);
      this.db.prepare(
        `UPDATE run_leases SET expires_at_ms = ?, heartbeat_at_ms = ?
         WHERE run_id = ? AND holder_id = ? AND fence = ?`,
      ).run(
        nowMs + this.coordinatorLeaseMs,
        nowMs,
        lease.runId,
        this.coordinatorId,
        lease.fence,
      );
      this.failpoints.hit("advance.before_commit", {
        runId: lease.runId,
        actorId: actor.id,
        eventId,
      });
      return true;
    })();
  }

  private recordEffects(
    runId: RunId,
    eventId: EventId,
    effects: readonly PreparedEffect[],
    now: string,
    nowMs: number,
  ): void {
    effects.forEach((prepared, ordinal) => {
      const effect = prepared.effect;
      const effectId = this.ids.next<string>("effect");
      this.db.prepare(
        `INSERT INTO transition_effects(id, event_id, ordinal, effect_type, params_json)
         VALUES (?, ?, ?, ?, ?)`,
      ).run(effectId, eventId, ordinal, effect.type, stringifyJson(effect as unknown as JsonObject));
      this.db.prepare(
        `INSERT INTO outbox(
          id, run_id, effect_id, kind, payload_json, idempotency_key,
          status, claim_fence, available_at_ms, attempts, created_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, 0, ?, NULL)`,
      ).run(
        this.ids.next<string>("outbox"),
        runId,
        effectId,
        effect.type,
        stringifyJson(preparedEffectPayload(prepared) as unknown as JsonObject),
        `transition-effect:${effectId}`,
        nowMs,
        now,
      );
    });
  }

  private applyOpenDurableCheckpoint(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "open_durable_checkpoint" }>,
    now: string,
  ): void {
    const actor = this.requireActor(effect.actorId);
    const accepted = this.requireArtifactRecord(effect.acceptedArtifactId);
    // Reused work may legitimately retain an immutable accepted artifact from
    // an ancestor run. The checkpoint request names that exact artifact and
    // its new decision; it must never be copied or replaced merely to satisfy
    // current-run ownership.
    const inputArtifactIds = this.db.prepare(
      `SELECT parent_artifact_id FROM artifact_edges
       WHERE child_artifact_id = ? ORDER BY ordinal`,
    ).all(accepted.id) as readonly { readonly parent_artifact_id: ArtifactId }[];
    const decisionArtifactId = this.ensureDurableAcceptanceDecision(
      runId,
      eventId,
      actor,
      accepted.id,
      now,
    );
    const promotionId = this.ids.next<PromotionId>("promotion");
    const revisionId = newRevisionId(this.clock.now());
    const taskArtifactId = this.ids.next<ArtifactId>("art");
    const request = {
      schemaVersion: "durable-checkpoint-request/1" as const,
      promotionId,
      revisionId,
      runId,
      logicalItem: effect.logicalItem,
      expectedParentRevisionId: effect.expectedParentRevisionId ?? null,
      acceptedArtifactIds: [accepted.id],
      decisionArtifactIds: [decisionArtifactId],
      inputRevisions: effect.inputRevisions ?? [],
      inputArtifactIds: inputArtifactIds.map((row) => row.parent_artifact_id),
    };
    const task: ArtifactRecord = {
      id: taskArtifactId,
      kind: "durable_checkpoint_request",
      schemaVersion: "durable-checkpoint-request/1",
      mediaType: "application/json",
      origin: "machine",
      payload: this.store.prepare(taskArtifactId, { kind: "json", value: request }),
      parents: deduplicateParents([
        { artifactId: accepted.id, relation: "accepted_output" },
        { artifactId: decisionArtifactId, relation: "accepted_decision" },
        ...inputArtifactIds.map(({ parent_artifact_id }) => ({
          artifactId: parent_artifact_id,
          relation: "checkpoint_input",
        })),
      ]),
      metadata: { promotionId, revisionId },
      disposition: "accepted",
      producingRunId: runId,
      producingActorId: actor.id,
      createdAt: now,
    };
    insertArtifactRecords(this.db, [task]);
    this.applyCreateOffer(runId, eventId, {
      type: "create_work_offer",
      actorId: effect.actorId,
      actorKey: effect.actorKey,
      state: effect.state,
      role: "durable_checkpoint",
      slot: "durable_checkpoint",
      subjectArtifactId: accepted.id,
      revisionId,
      inputArtifacts: [...new Set([
        taskArtifactId,
        accepted.id,
        decisionArtifactId,
        ...inputArtifactIds.map((row) => row.parent_artifact_id),
      ])],
      taskArtifactId,
      contractVersion: "durable-checkpoint/1",
      allowedWorkerCapabilities: ["subprocess"],
    }, now);
  }

  private ensureDurableAcceptanceDecision(
    runId: RunId,
    eventId: EventId,
    actor: ActorMutationRow,
    acceptedArtifactId: ArtifactId,
    now: string,
  ): ArtifactId {
    const decision = this.db.prepare(
      `SELECT id, offer_id, choice, authority, artifact_id FROM decisions
       WHERE run_id = ? AND actor_id = ? ORDER BY created_at DESC, id DESC LIMIT 1`,
    ).get(runId, actor.id) as
      | {
          readonly id: DecisionId;
          readonly offer_id: WorkOfferId | null;
          readonly choice: string;
          readonly authority: string;
          readonly artifact_id: ArtifactId | null;
        }
      | undefined;
    if (decision?.artifact_id !== null && decision?.artifact_id !== undefined) {
      return decision.artifact_id;
    }
    const decisionId = this.ids.next<DecisionId>("decision");
    const artifactId = this.ids.next<ArtifactId>("art");
    const choice = decision?.choice ?? "accept";
    const authority = decision?.authority ?? "machine";
    const record: ArtifactRecord = {
      id: artifactId,
      kind: "durable_acceptance_decision",
      schemaVersion: "durable-acceptance-decision/1",
      mediaType: "application/json",
      origin: "machine",
      payload: this.store.prepare(artifactId, {
        kind: "json",
        value: {
          decisionId,
          offerId: decision?.offer_id ?? null,
          choice,
          authority,
          acceptedArtifactId,
        },
      }),
      parents: [{ artifactId: acceptedArtifactId, relation: "accepted_output" }],
      metadata: { decisionId, choice, authority },
      disposition: "accepted",
      producingRunId: runId,
      producingActorId: actor.id,
      createdAt: now,
    };
    insertArtifactRecords(this.db, [record]);
    this.db.prepare(
      `INSERT INTO decisions(
        id, run_id, actor_id, offer_id, subject_artifact_id, authority,
        principal_id, choice, artifact_id, details_json, event_id, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      decisionId,
      runId,
      actor.id,
      decision?.offer_id ?? null,
      acceptedArtifactId,
      authority,
      `machine:${actor.id}`,
      choice,
      artifactId,
      stringifyJson({ durableCheckpoint: true, sourceDecisionId: decision?.id ?? null }),
      eventId,
      now,
    );
    return artifactId;
  }

  private applyCreateOffer(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "create_work_offer" }>,
    now: string,
  ): void {
    const actor = this.requireActor(effect.actorId);
    if (actor.run_id !== runId || actor.logical_key !== effect.actorKey) {
      throw new RunEngineError(
        "OFFER_ACTOR_MISMATCH",
        `Work offer ${effect.slot} names an actor outside its transition`,
      );
    }
    if (actor.current_state !== effect.state) {
      throw new RunEngineError(
        "OFFER_STATE_MISMATCH",
        `Work offer ${effect.slot} expected state ${effect.state}, got ${actor.current_state}`,
      );
    }
    assertWorkResultContractRegistered(effect.role, effect.contractVersion);
    requireArtifactExists(this.db, effect.taskArtifactId);
    effect.inputArtifacts.forEach((artifactId) => requireArtifactExists(this.db, artifactId));
    if (effect.subjectArtifactId !== undefined) {
      requireArtifactExists(this.db, effect.subjectArtifactId);
    }
    if (
      (effect.iterationId === undefined) !==
      (effect.iterationOrdinal === undefined)
    ) {
      throw new RunEngineError(
        "ITERATION_BINDING_INCOMPLETE",
        `Work offer ${effect.slot} must name both iteration ID and ordinal`,
      );
    }
    if (effect.iterationId !== undefined && effect.iterationOrdinal !== undefined) {
      if (effect.parentManuscriptArtifactId !== undefined) {
        requireArtifactExists(this.db, effect.parentManuscriptArtifactId);
      }
      this.db.prepare(
        `INSERT INTO iterations(
          id, actor_id, ordinal, parent_manuscript_artifact_id, opened_event_id
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(actor_id, ordinal) DO NOTHING`,
      ).run(
        effect.iterationId,
        effect.actorId,
        effect.iterationOrdinal,
        effect.parentManuscriptArtifactId ?? null,
        eventId,
      );
      const iteration = this.db
        .prepare("SELECT id FROM iterations WHERE actor_id = ? AND ordinal = ?")
        .get(effect.actorId, effect.iterationOrdinal) as { readonly id: string } | undefined;
      if (iteration?.id !== effect.iterationId) {
        throw new RunEngineError(
          "ITERATION_ID_MISMATCH",
          `Article iteration ${effect.iterationOrdinal} changed identity`,
        );
      }
    }
    const offerId = this.ids.next<WorkOfferId>("offer");
    const reuse = this.findReusableWorkAnswer(runId, actor, effect);
    this.db.prepare(
      `INSERT INTO work_offers(
        id, run_id, actor_id, state_visit_id, iteration_id, revision_id,
        role, slot, subject_artifact_id, task_artifact_id, contract_version,
        status, created_event_id, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      offerId,
      runId,
      effect.actorId,
      actor.current_visit_id,
      effect.iterationId ?? null,
      effect.revisionId ?? null,
      effect.role,
      effect.slot,
      effect.subjectArtifactId ?? null,
      effect.taskArtifactId,
      effect.contractVersion,
      reuse === undefined ? "offered" : "answered",
      eventId,
      now,
      now,
    );
    effect.inputArtifacts.forEach((artifactId, ordinal) => {
      this.db.prepare(
        "INSERT INTO work_offer_inputs(offer_id, ordinal, artifact_id) VALUES (?, ?, ?)",
      ).run(offerId, ordinal, artifactId);
    });
    effect.allowedWorkerCapabilities.forEach((capability) => {
      this.db.prepare(
        "INSERT INTO work_offer_capabilities(offer_id, capability) VALUES (?, ?)",
      ).run(offerId, capability);
    });
    if (reuse !== undefined) {
      this.applyWorkReuse(runId, actor, offerId, eventId, effect, reuse, now);
    }
  }

  private findReusableWorkAnswer(
    runId: RunId,
    actor: ActorMutationRow,
    effect: Extract<MachineEffect, { readonly type: "create_work_offer" }>,
  ): ReusedWorkAnswer | undefined {
    const run = this.requireRun(runId);
    const candidates = this.db
      .prepare(
        `WITH RECURSIVE ancestors(run_id, depth) AS (
           SELECT parent_run_id, 1 FROM runs
           WHERE id = ? AND parent_run_id IS NOT NULL
           UNION ALL
           SELECT parent.parent_run_id, ancestors.depth + 1
           FROM runs parent
           JOIN ancestors ON ancestors.run_id = parent.id
           WHERE parent.parent_run_id IS NOT NULL
         )
         SELECT
           ancestors.run_id AS ancestor_run_id,
           ancestors.depth AS ancestor_depth,
           offer.id AS ancestor_offer_id,
           candidate_actor.parent_actor_id AS actor_parent_id,
           candidate_actor.logical_key AS actor_logical_key,
           candidate_actor.machine_name AS actor_machine_name,
           candidate_actor.machine_version AS actor_machine_version,
           candidate_actor.input_json AS actor_input_json,
           iteration.ordinal AS iteration_ordinal,
           iteration.parent_manuscript_artifact_id,
           offer.revision_id,
           COALESCE(reuse.answer_artifact_id, submission.artifact_id) AS answer_artifact_id
         FROM ancestors
         JOIN runs ancestor_run ON ancestor_run.id = ancestors.run_id
         JOIN work_offers offer ON offer.run_id = ancestor_run.id
         JOIN actors candidate_actor ON candidate_actor.id = offer.actor_id
         JOIN state_visits visit ON visit.id = offer.state_visit_id
         LEFT JOIN iterations iteration ON iteration.id = offer.iteration_id
         LEFT JOIN work_reuses reuse ON reuse.offer_id = offer.id
         LEFT JOIN attempt_submissions submission
           ON submission.offer_id = offer.id AND submission.disposition = 'accepted'
         WHERE offer.status = 'answered'
           AND COALESCE(reuse.answer_artifact_id, submission.artifact_id) IS NOT NULL
           AND ancestor_run.machine_name = ?
           AND ancestor_run.machine_version = ?
           AND candidate_actor.machine_name = ?
           AND candidate_actor.machine_version = ?
           AND visit.state_key = ?
           AND offer.role = ?
           AND offer.slot = ?
           AND offer.task_artifact_id = ?
           AND offer.contract_version = ?
           AND offer.subject_artifact_id IS ?
         ORDER BY ancestors.depth, offer.created_at, offer.id`,
      )
      .all(
        runId,
        run.machine_name,
        run.machine_version,
        actor.machine_name,
        actor.machine_version,
        effect.state,
        effect.role,
        effect.slot,
        effect.taskArtifactId,
        effect.contractVersion,
        effect.subjectArtifactId ?? null,
      ) as readonly ReusableOfferRow[];
    for (const candidate of candidates) {
      const sameActor =
        actor.parent_actor_id === null
          ? candidate.actor_parent_id === null
          : candidate.actor_parent_id !== null &&
            candidate.actor_logical_key === actor.logical_key;
      if (!sameActor) {
        continue;
      }
      const iterationMatches =
        effect.iterationOrdinal === undefined
          ? candidate.iteration_ordinal === null &&
            candidate.parent_manuscript_artifact_id === null
          : candidate.iteration_ordinal === effect.iterationOrdinal &&
            candidate.parent_manuscript_artifact_id ===
              (effect.parentManuscriptArtifactId ?? null);
      if (!iterationMatches) {
        continue;
      }
      if ((candidate.revision_id === null) !== (effect.revisionId === undefined)) {
        continue;
      }
      const candidateInputs = (
        this.db
          .prepare(
            "SELECT artifact_id FROM work_offer_inputs WHERE offer_id = ? ORDER BY ordinal",
          )
          .all(candidate.ancestor_offer_id) as readonly {
          readonly artifact_id: ArtifactId;
        }[]
      ).map((row) => row.artifact_id);
      if (!sameOrderedValues(candidateInputs, effect.inputArtifacts)) {
        continue;
      }
      const candidateCapabilities = this.offerCapabilities(candidate.ancestor_offer_id);
      if (!sameOrderedValues(candidateCapabilities, [...effect.allowedWorkerCapabilities].sort())) {
        continue;
      }
      if (
        candidateCapabilities.includes("text_model") ||
        candidateCapabilities.includes("image_model")
      ) {
        const ancestorModel = modelDependency(candidate.actor_input_json, effect.role);
        const successorModel = modelDependency(actor.input_json, effect.role);
        if (
          ancestorModel === null ||
          successorModel === null ||
          stableStringify(ancestorModel) !== stableStringify(successorModel)
        ) {
          continue;
        }
      }
      return this.loadReusedWorkAnswer(candidate, effect.contractVersion);
    }
    return undefined;
  }

  private loadReusedWorkAnswer(
    candidate: ReusableOfferRow,
    contractVersion: string,
  ): ReusedWorkAnswer {
    const answer = this.db
      .prepare("SELECT * FROM artifacts WHERE id = ?")
      .get(candidate.answer_artifact_id) as StoredArtifactRow | undefined;
    if (
      answer === undefined ||
      answer.kind !== "work_answer" ||
      answer.schema_version !== contractVersion
    ) {
      throw new RunEngineError(
        "REUSED_ANSWER_INVALID",
        `Reusable offer ${candidate.ancestor_offer_id} has an invalid answer envelope`,
      );
    }
    const payload = jsonObject(
      JSON.parse(this.readStoredArtifactBytes(answer).toString("utf8")) as unknown,
      `work answer ${answer.id}`,
    );
    if (
      payload.contractVersion !== contractVersion ||
      payload.result === null ||
      Array.isArray(payload.result) ||
      typeof payload.result !== "object" ||
      !Array.isArray(payload.artifactIds) ||
      payload.artifactIds.some((artifactId) => typeof artifactId !== "string")
    ) {
      throw new RunEngineError(
        "REUSED_ANSWER_INVALID",
        `Reusable offer ${candidate.ancestor_offer_id} has a malformed answer envelope`,
      );
    }
    const artifacts = (payload.artifactIds as readonly ArtifactId[]).map((artifactId) => {
      const artifact = this.db
        .prepare("SELECT kind FROM artifacts WHERE id = ?")
        .get(artifactId) as { readonly kind: string } | undefined;
      if (artifact === undefined) {
        throw new RunEngineError(
          "REUSED_ANSWER_INVALID",
          `Reusable answer ${answer.id} references missing artifact ${artifactId}`,
        );
      }
      return { artifactId, kind: artifact.kind };
    });
    return {
      ancestorRunId: candidate.ancestor_run_id,
      ancestorOfferId: candidate.ancestor_offer_id,
      answerArtifactId: answer.id,
      result: payload.result as JsonObject,
      artifacts,
    };
  }

  private applyWorkReuse(
    runId: RunId,
    actor: ActorMutationRow,
    offerId: WorkOfferId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "create_work_offer" }>,
    reuse: ReusedWorkAnswer,
    now: string,
  ): void {
    this.db.prepare(
      `INSERT INTO work_reuses(
        run_id, offer_id, ancestor_run_id, ancestor_offer_id,
        answer_artifact_id, created_event_id, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      runId,
      offerId,
      reuse.ancestorRunId,
      reuse.ancestorOfferId,
      reuse.answerArtifactId,
      eventId,
      now,
    );
    this.db.prepare(
      `INSERT INTO run_inputs(run_id, input_name, ordinal, artifact_id)
       VALUES (?, ?, 0, ?)`,
    ).run(runId, `reuse:${offerId}:answer`, reuse.answerArtifactId);
    reuse.artifacts.forEach((artifact, ordinal) => {
      this.db.prepare(
        `INSERT INTO run_inputs(run_id, input_name, ordinal, artifact_id)
         VALUES (?, ?, ?, ?)`,
      ).run(runId, `reuse:${offerId}:output`, ordinal, artifact.artifactId);
    });
    enqueueInbox(this.db, {
      id: this.ids.next<InboxId>("inbox"),
      runId,
      actorId: actor.id,
      type: "WORK_COMPLETED",
      payload: {
        type: "WORK_COMPLETED",
        slot: effect.slot,
        offerId,
        artifacts: reuse.artifacts.concat({
          artifactId: reuse.answerArtifactId,
          kind: "work_answer",
        }),
        result: reuse.result,
        reuse: {
          ancestorRunId: reuse.ancestorRunId,
          ancestorOfferId: reuse.ancestorOfferId,
          answerArtifactId: reuse.answerArtifactId,
        },
      },
      idempotencyKey: `work-reuse:${offerId}`,
      causationEventId: eventId,
      correlationId: offerId,
      availableAtMs: this.nowMs(),
      now,
    });
  }

  private applySpawn(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "spawn_actor" }>,
    child: PreparedSpawn,
    cursor: { sequence: number },
    now: string,
    nowMs: number,
  ): void {
    if (effect.parentActorId !== child.parentActorId) {
      throw new RunEngineError("SPAWN_PARENT_MISMATCH", "Prepared spawn parent changed");
    }
    const parent = this.requireActor(effect.parentActorId);
    if (parent.run_id !== runId) {
      throw new RunEngineError("SPAWN_RUN_MISMATCH", "Cannot spawn an actor into another run");
    }
    const relationship = orchestrationSpawn(effect.relationship);
    if (
      relationship === undefined ||
      relationship.owner !== parent.machine_name ||
      relationship.child !== effect.machine ||
      relationship.child !== child.machine
    ) {
      throw new RunEngineError(
        "ORCHESTRATION_SPAWN_INVALID",
        `Actor ${parent.id} cannot use ${effect.relationship} to spawn ${child.machine}`,
      );
    }
    const machineVersion = currentMachineVersion(child.machine);
    ensureMachineVersion(this.db, child.machine, machineVersion, now);
    const initializationEventId = this.ids.next<EventId>("event");
    const visitId = this.ids.next<StateVisitId>("visit");
    cursor.sequence += 1;
    this.db.prepare(
      `INSERT INTO actors(
        id, run_id, parent_actor_id, logical_key, machine_name, machine_version,
        status, current_state, current_context_json, current_snapshot_number,
        current_visit_id, input_json, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, 1, ?, ?, ?, ?)`,
    ).run(
      child.actorId,
      runId,
      child.parentActorId,
      child.logicalKey,
      child.machine,
      machineVersion,
      stateKey(child.initial.snapshot.value),
      stringifyJson(child.initial.snapshot.context),
      visitId,
      stringifyJson(child.input),
      now,
      now,
    );
    insertSnapshotEvent(this.db, {
      eventId: initializationEventId,
      runId,
      sequence: cursor.sequence,
      actorId: child.actorId,
      type: "@@engine/initialized",
      payload: { type: "@@engine/initialized" },
      previousSnapshotNumber: null,
      nextSnapshotNumber: 1,
      previousState: null,
      snapshot: child.initial.snapshot,
      machineVersion,
      causationEventId: eventId,
      correlationId: eventId,
      inboxId: null,
      now,
    });
    this.db.prepare(
      `INSERT INTO state_visits(
        id, actor_id, state_key, visit_number, entered_event_id, created_at
      ) VALUES (?, ?, ?, 1, ?, ?)`,
    ).run(visitId, child.actorId, stateKey(child.initial.snapshot.value), initializationEventId, now);
    enqueueInbox(this.db, {
      id: this.ids.next<InboxId>("inbox"),
      runId,
      actorId: child.parentActorId,
      type: "CHILD_SPAWNED",
      payload: {
        type: "CHILD_SPAWNED",
        relationship: relationship.id,
        childActorId: child.actorId,
        childKey: child.logicalKey,
        machine: child.machine,
      },
      idempotencyKey: `child-spawned:${child.actorId}`,
      causationEventId: initializationEventId,
      correlationId: eventId,
      priority: -10,
      availableAtMs: nowMs,
      now,
    });
    enqueueInbox(this.db, {
      id: this.ids.next<InboxId>("inbox"),
      runId,
      actorId: child.actorId,
      type: "START",
      payload: { type: "START" },
      idempotencyKey: `start:${child.actorId}`,
      causationEventId: initializationEventId,
      correlationId: eventId,
      availableAtMs: nowMs,
      now,
    });
  }

  private applySendActorEvent(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "send_actor_event" }>,
    now: string,
    nowMs: number,
  ): void {
    const sender = this.requireActor(effect.actorId);
    if (sender.run_id !== runId) {
      throw new RunEngineError(
        "EVENT_SENDER_RUN_MISMATCH",
        "Cannot send an actor event from another run",
      );
    }
    let targetActorId: ActorId;
    if ("actorId" in effect.target) {
      targetActorId = effect.target.actorId;
    } else {
      const child = this.db
        .prepare(
          `SELECT id FROM actors
           WHERE run_id = ? AND parent_actor_id = ? AND logical_key = ?`,
        )
        .get(runId, effect.actorId, effect.target.childKey) as
        | { readonly id: ActorId }
        | undefined;
      if (child === undefined) {
        throw new RunEngineError(
          "EVENT_TARGET_NOT_FOUND",
          `Actor ${effect.actorId} has no child ${effect.target.childKey}`,
        );
      }
      targetActorId = child.id;
    }
    const target = this.requireActor(targetActorId);
    if (target.run_id !== runId) {
      throw new RunEngineError("EVENT_TARGET_RUN_MISMATCH", "Cannot send across run boundaries");
    }
    const route = orchestrationRoute(effect.route);
    if (
      route === undefined ||
      route.owner !== sender.machine_name ||
      route.target !== target.machine_name ||
      route.event !== effect.event.type
    ) {
      throw new RunEngineError(
        "ORCHESTRATION_ROUTE_INVALID",
        `Actor ${sender.id} cannot use ${effect.route} to send ${effect.event.type} to ${target.machine_name}`,
      );
    }
    enqueueInbox(this.db, {
      id: this.ids.next<InboxId>("inbox"),
      runId,
      actorId: targetActorId,
      type: effect.event.type,
      payload: effect.event,
      idempotencyKey: `effect-event:${eventId}:${targetActorId}:${effect.event.type}`,
      causationEventId: eventId,
      correlationId: eventId,
      availableAtMs: nowMs,
      now,
    });
  }

  private applyDecision(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "record_decision" }>,
    now: string,
  ): void {
    if (effect.artifactId !== undefined) {
      requireArtifactExists(this.db, effect.artifactId);
    }
    const eventRow = this.db.prepare("SELECT payload_json FROM events WHERE id = ?").get(
      eventId,
    ) as { readonly payload_json: string } | undefined;
    const payload = eventRow === undefined
      ? {}
      : parseJson<JsonObject>(eventRow.payload_json, `event ${eventId} payload`);
    const offeredId = typeof payload.offerId === "string"
      ? payload.offerId as WorkOfferId
      : undefined;
    const offer = offeredId === undefined
      ? undefined
      : this.db.prepare(
          "SELECT subject_artifact_id FROM work_offers WHERE id = ? AND run_id = ?",
        ).get(offeredId, runId) as
          | { readonly subject_artifact_id: ArtifactId | null }
          | undefined;
    const worker = offeredId === undefined
      ? undefined
      : this.db.prepare(
          `SELECT worker_principal_id, worker_authority FROM attempts
           WHERE offer_id = ? AND status = 'answered'
           ORDER BY attempt_number DESC LIMIT 1`,
        ).get(offeredId) as
          | {
              readonly worker_principal_id: string;
              readonly worker_authority: WorkerIdentity["authority"];
            }
          | undefined;
    if (effect.authority === "human" && worker?.worker_authority !== "human") {
      throw new RunEngineError(
        "DECISION_AUTHORITY_INVALID",
        `Human decision for actor ${effect.actorId} has no answered human offer`,
      );
    }
    const decisionId = this.ids.next<DecisionId>("decision");
    this.db.prepare(
      `INSERT INTO decisions(
        id, run_id, actor_id, offer_id, subject_artifact_id, authority,
        principal_id, choice, artifact_id, details_json, event_id, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      decisionId,
      runId,
      effect.actorId,
      offeredId ?? null,
      offer?.subject_artifact_id ?? null,
      effect.authority,
      worker?.worker_principal_id ?? `machine:${effect.actorId}`,
      effect.choice,
      effect.artifactId ?? null,
      stringifyJson(effect.details ?? {}),
      eventId,
      now,
    );
    if (effect.iterationId !== undefined) {
      const updated = this.db.prepare(
        `UPDATE iterations SET
          closed_event_id = COALESCE(closed_event_id, ?),
          decision_id = COALESCE(decision_id, ?)
         WHERE id = ? AND actor_id = ?`,
      ).run(eventId, decisionId, effect.iterationId, effect.actorId);
      if (updated.changes !== 1) {
        throw new RunEngineError(
          "ITERATION_NOT_FOUND",
          `Decision ${decisionId} names unknown iteration ${effect.iterationId}`,
        );
      }
    }
  }

  private applyCancelOffer(
    eventId: EventId,
    actorId: ActorId,
    slot: string,
    reason: string,
    now: string,
  ): void {
    const offers = this.db
      .prepare(
        `SELECT id, active_attempt_id FROM work_offers
         WHERE actor_id = ? AND slot = ? AND status IN ('offered', 'claimed')`,
      )
      .all(actorId, slot) as readonly {
      readonly id: WorkOfferId;
      readonly active_attempt_id: AttemptId | null;
    }[];
    for (const offer of offers) {
      if (offer.active_attempt_id !== null) {
        this.db.prepare(
          `UPDATE attempts SET status = 'stale', finished_at = ?,
             failure_classification = 'canceled', failure_message = ?
           WHERE id = ? AND status = 'active'`,
        ).run(now, reason, offer.active_attempt_id);
      }
      this.db.prepare(
        `UPDATE work_offers SET status = 'canceled', active_attempt_id = NULL,
           canceled_event_id = ?, updated_at = ? WHERE id = ?`,
      ).run(eventId, now, offer.id);
    }
  }

  private cancelVisitOutstandingOffers(
    visitId: StateVisitId,
    eventId: EventId,
    reason: string,
    now: string,
  ): void {
    const offers = this.db
      .prepare(
        `SELECT id, active_attempt_id FROM work_offers
         WHERE state_visit_id = ? AND status IN ('offered', 'claimed')`,
      )
      .all(visitId) as readonly {
      readonly id: WorkOfferId;
      readonly active_attempt_id: AttemptId | null;
    }[];
    for (const offer of offers) {
      if (offer.active_attempt_id !== null) {
        this.db.prepare(
          `UPDATE attempts SET status = 'stale', finished_at = ?,
             failure_classification = 'canceled', failure_message = ?
           WHERE id = ? AND status = 'active'`,
        ).run(now, reason, offer.active_attempt_id);
      }
      this.db.prepare(
        `UPDATE work_offers SET status = 'canceled', active_attempt_id = NULL,
           claim_fence = claim_fence + 1, canceled_event_id = ?, updated_at = ?
         WHERE id = ? AND status IN ('offered', 'claimed')`,
      ).run(eventId, now, offer.id);
    }
  }

  private supersedeRunOutstandingOffers(
    runId: RunId,
    eventId: EventId,
    reason: string,
    now: string,
  ): void {
    const offers = this.db.prepare(
      `SELECT id, active_attempt_id FROM work_offers
       WHERE run_id = ? AND status IN ('offered', 'claimed')`,
    ).all(runId) as readonly {
      readonly id: WorkOfferId;
      readonly active_attempt_id: AttemptId | null;
    }[];
    for (const offer of offers) {
      if (offer.active_attempt_id !== null) {
        this.db.prepare(
          `UPDATE attempts SET status = 'stale', finished_at = ?,
             failure_classification = 'canceled', failure_message = ?
           WHERE id = ? AND status = 'active'`,
        ).run(now, reason, offer.active_attempt_id);
      }
      this.db.prepare(
        `UPDATE work_offers SET status = 'superseded', active_attempt_id = NULL,
           claim_fence = claim_fence + 1, canceled_event_id = ?, updated_at = ?
         WHERE id = ? AND status IN ('offered', 'claimed')`,
      ).run(eventId, now, offer.id);
    }
  }

  private applyCompleteActor(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "complete_actor" }>,
    now: string,
    nowMs: number,
  ): void {
    const actor = this.requireActor(effect.actorId);
    const escalated = effect.result.status === "escalated";
    if (actor.machine_name === "release" && effect.result.status === "released") {
      this.recordRelease(runId, actor, effect.result, now);
    }
    this.db.prepare("DELETE FROM run_outputs WHERE run_id = ? AND output_name = ?").run(
      runId,
      actor.logical_key,
    );
    effect.outputs.forEach((artifactId, ordinal) => {
      requireArtifactExists(this.db, artifactId);
      this.db.prepare(
        `INSERT OR IGNORE INTO run_outputs(run_id, output_name, ordinal, artifact_id)
         VALUES (?, ?, ?, ?)`,
      ).run(runId, actor.logical_key, ordinal, artifactId);
    });
    const status = escalated ? "active" : effect.accepting ? "accepting" : "done";
    this.db.prepare("UPDATE actors SET status = ?, updated_at = ? WHERE id = ?").run(
      status,
      now,
      actor.id,
    );
    if (actor.parent_actor_id === null) {
      if (escalated) {
        this.db.prepare(
          "UPDATE runs SET status = 'escalated', terminal_at = NULL, updated_at = ? WHERE id = ?",
        ).run(now, runId);
      } else {
        this.db.prepare(
          `UPDATE runs SET status = 'complete', terminal_at = COALESCE(terminal_at, ?),
             updated_at = ? WHERE id = ?`,
        ).run(now, now, runId);
      }
    } else {
      this.enqueueChildStatus(
        runId,
        eventId,
        actor,
        escalated ? "active" : status,
        effect.outputs,
        effect.result,
        now,
        nowMs,
      );
    }
  }

  private recordRelease(
    runId: RunId,
    actor: ActorMutationRow,
    result: JsonObject,
    now: string,
  ): void {
    const publicationArtifactId = result.publicationArtifactId;
    const decisionArtifactId = result.decisionArtifactId;
    const sourceArtifactIds = result.sourceArtifactIds;
    if (
      typeof publicationArtifactId !== "string" ||
      typeof decisionArtifactId !== "string" ||
      !Array.isArray(sourceArtifactIds) ||
      sourceArtifactIds.some((value) => typeof value !== "string")
    ) {
      throw new RunEngineError(
        "RELEASE_CONTRACT_INVALID",
        "Released actor must name its publication, decision, and source artifacts",
      );
    }
    requireArtifactExists(this.db, publicationArtifactId as ArtifactId);
    requireArtifactExists(this.db, decisionArtifactId as ArtifactId);
    const sources = sourceArtifactIds as readonly ArtifactId[];
    sources.forEach((artifactId) => requireArtifactExists(this.db, artifactId));
    const duplicate = sources.find((artifactId) =>
      this.db
        .prepare("SELECT 1 FROM released_source_assignments WHERE source_artifact_id = ?")
        .get(artifactId) !== undefined,
    );
    if (duplicate !== undefined) {
      throw new RunEngineError(
        "SOURCE_ALREADY_RELEASED",
        `Source artifact ${duplicate} is already assigned to a released edition`,
      );
    }
    const run = this.requireRun(runId);
    const spec = parseJson<JsonObject>(run.spec_json, `run ${runId} spec`);
    const edition = jsonObject(spec.edition, `run ${runId} edition spec`);
    const editionId = edition.editionId;
    if (typeof editionId !== "string" || !editionId) {
      throw new RunEngineError("RELEASE_CONTRACT_INVALID", "Edition release has no edition ID");
    }
    const rootActor = this.db
      .prepare(
        `SELECT current_context_json FROM actors
         WHERE run_id = ? AND parent_actor_id IS NULL`,
      )
      .get(runId) as { readonly current_context_json: string } | undefined;
    if (rootActor === undefined) {
      throw new RunEngineError(
        "RELEASE_CONTRACT_INVALID",
        `Edition ${editionId} has no durable root actor`,
      );
    }
    const rootContext = parseJson<JsonObject>(
      rootActor.current_context_json,
      `edition ${editionId} root context`,
    );
    const collectedSources = rootContext.sources;
    if (!Array.isArray(collectedSources)) {
      throw new RunEngineError(
        "RELEASE_CONTRACT_INVALID",
        `Edition ${editionId} has no frozen collected-source identities`,
      );
    }
    const sourceIds = collectedSources.map((candidate, ordinal) => {
      const source = jsonObject(candidate, `edition ${editionId} source ${ordinal}`);
      if (typeof source.sourceId !== "string" || source.sourceId.trim().length === 0) {
        throw new RunEngineError(
          "RELEASE_CONTRACT_INVALID",
          `Edition ${editionId} source ${ordinal} has no stable source ID`,
        );
      }
      return source.sourceId;
    });
    if (new Set(sourceIds).size !== sourceIds.length) {
      throw new RunEngineError(
        "RELEASE_CONTRACT_INVALID",
        `Edition ${editionId} repeats a stable source ID`,
      );
    }
    const duplicateSourceId = sourceIds.find((sourceId) =>
      this.db
        .prepare("SELECT 1 FROM released_source_identities WHERE source_id = ?")
        .get(sourceId) !== undefined,
    );
    if (duplicateSourceId !== undefined) {
      throw new RunEngineError(
        "SOURCE_ALREADY_RELEASED",
        `Source ${duplicateSourceId} is already assigned to a released edition`,
      );
    }
    const releaseId = this.ids.next<string>("release");
    this.db.prepare(
      `INSERT INTO releases(
        id, run_id, actor_id, edition_id, publication_artifact_id,
        decision_artifact_id, released_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      releaseId,
      runId,
      actor.id,
      editionId,
      publicationArtifactId,
      decisionArtifactId,
      now,
    );
    sources.forEach((artifactId, ordinal) => {
      this.db.prepare(
        `INSERT INTO released_source_assignments(source_artifact_id, release_id, ordinal)
         VALUES (?, ?, ?)`,
      ).run(artifactId, releaseId, ordinal);
    });
    sourceIds.forEach((sourceId, ordinal) => {
      this.db.prepare(
        `INSERT INTO released_source_identities(source_id, release_id, ordinal)
         VALUES (?, ?, ?)`,
      ).run(sourceId, releaseId, ordinal);
    });
  }

  private applyFailActor(
    runId: RunId,
    eventId: EventId,
    effect: Extract<MachineEffect, { readonly type: "fail_actor" }>,
    now: string,
    nowMs: number,
  ): void {
    const actor = this.requireActor(effect.actorId);
    this.db.prepare("UPDATE actors SET status = 'failed', updated_at = ? WHERE id = ?").run(
      now,
      actor.id,
    );
    if (actor.parent_actor_id === null) {
      this.db.prepare(
        `UPDATE runs SET status = 'failed', terminal_at = COALESCE(terminal_at, ?),
           updated_at = ? WHERE id = ?`,
      ).run(now, now, runId);
    } else {
      this.enqueueChildStatus(
        runId,
        eventId,
        actor,
        "failed",
        [],
        {
          classification: effect.classification,
          message: effect.message,
          ...(effect.details === undefined ? {} : { details: effect.details }),
        },
        now,
        nowMs,
      );
    }
  }

  private enqueueChildStatus(
    runId: RunId,
    eventId: EventId,
    actor: ActorMutationRow,
    status: "accepting" | "active" | "done" | "failed",
    outputs: readonly ArtifactId[],
    result: JsonObject,
    now: string,
    nowMs: number,
  ): void {
    if (actor.parent_actor_id === null) {
      return;
    }
    const parent = this.requireActor(actor.parent_actor_id);
    const relationship = completionRelationship(parent.machine_name, actor.machine_name);
    if (relationship === undefined) {
      throw new RunEngineError(
        "ORCHESTRATION_COMPLETION_INVALID",
        `Actor ${actor.id} cannot report ${status} from ${actor.machine_name} to ${parent.machine_name}`,
      );
    }
    enqueueInbox(this.db, {
      id: this.ids.next<InboxId>("inbox"),
      runId,
      actorId: actor.parent_actor_id,
      type: "CHILD_STATUS",
      payload: {
        type: "CHILD_STATUS",
        relationship: relationship.id,
        childActorId: actor.id,
        childKey: actor.logical_key,
        status,
        outputs,
        result,
      },
      idempotencyKey: `child-status:${eventId}:${status}`,
      causationEventId: eventId,
      correlationId: eventId,
      availableAtMs: nowMs,
      now,
    });
  }

  private reconcileRunStatus(runId: RunId, headSequence: number, now: string): void {
    const run = this.requireRun(runId);
    let status = run.status;
    if (isTerminalStatus(status)) {
      this.db.prepare("UPDATE inbox SET status = 'dead' WHERE run_id = ? AND status = 'pending'").run(
        runId,
      );
    } else {
      const pending = this.db
        .prepare("SELECT 1 FROM inbox WHERE run_id = ? AND status = 'pending' LIMIT 1")
        .get(runId);
      if (pending !== undefined) {
        status = "running";
      } else {
        const pendingEffect = this.db
          .prepare(
            `SELECT 1 FROM outbox
             WHERE run_id = ? AND status <> 'completed' LIMIT 1`,
          )
          .get(runId);
        if (pendingEffect !== undefined) {
          status = "running";
        } else {
        const offers = loadOfferViews(this.db, runId).filter(
          (offer) => offer.status === "offered" || offer.status === "claimed",
        );
        if (offers.some((offer) => offer.state === "awaiting_editor")) {
          status = "awaiting_editor";
        } else if (offers.some((offer) => offer.state === "escalated")) {
          status = "escalated";
        } else if (offers.length > 0) {
          status = "waiting";
        } else {
          const stranded = this.db
            .prepare(
              `SELECT 1 FROM actors
               WHERE run_id = ? AND status = 'active' AND current_state LIKE '%failed%'
               LIMIT 1`,
            )
            .get(runId);
          status = stranded === undefined ? "waiting" : "escalated";
        }
        }
      }
    }
    this.db.prepare(
      `UPDATE runs SET status = ?, head_sequence = ?, version = version + 1,
         updated_at = ? WHERE id = ?`,
    ).run(status, headSequence, now, runId);
  }

  async inspect(runId: RunId): Promise<RunView> {
    this.assertOpen();
    return inspectRun(this.db, runId);
  }

  async listRuns(): Promise<readonly RunIdentityView[]> {
    this.assertOpen();
    return (this.db.prepare(
      `SELECT id, kind, status, machine_version, head_sequence, metadata_json, created_at, updated_at
       FROM runs ORDER BY created_at, id`,
    ).all() as readonly {
      readonly id: RunId;
      readonly kind: RunIdentityView["kind"];
      readonly status: RunIdentityView["status"];
      readonly machine_version: string;
      readonly head_sequence: number;
      readonly metadata_json: string;
      readonly created_at: string;
      readonly updated_at: string;
    }[]).map((run) => ({
      id: run.id,
      kind: run.kind,
      status: run.status,
      machineVersion: run.machine_version,
      headSequence: run.head_sequence,
      metadata: parseJson<JsonObject>(run.metadata_json, `run ${run.id} metadata`),
      createdAt: run.created_at,
      updatedAt: run.updated_at,
    }));
  }

  async acquireMigrationFence(
    request: RunMigrationFenceRequest,
  ): Promise<RunMigrationFence> {
    this.assertOpen();
    if (
      !Number.isSafeInteger(request.expectedHeadSequence) ||
      request.expectedHeadSequence < 1 ||
      request.idempotencyKey.length < 1 ||
      request.idempotencyKey.length > 500
    ) {
      throw new RunEngineError(
        "MIGRATION_FENCE_INVALID",
        "Migration fence requires a positive head sequence and a non-empty idempotency key",
      );
    }
    return immediateTransaction(this.db, () => {
      const existing = this.db.prepare(
        `SELECT run_id, fence_id, expected_head_sequence, expected_head_event_id,
                idempotency_key, acquired_at
         FROM run_migration_fences WHERE run_id = ? OR idempotency_key = ?`,
      ).get(request.runId, request.idempotencyKey) as {
        readonly run_id: RunId;
        readonly fence_id: string;
        readonly expected_head_sequence: number;
        readonly expected_head_event_id: EventId;
        readonly idempotency_key: string;
        readonly acquired_at: string;
      } | undefined;
      if (existing !== undefined) {
        if (
          existing.run_id !== request.runId ||
          existing.expected_head_sequence !== request.expectedHeadSequence ||
          existing.expected_head_event_id !== request.expectedHeadEventId ||
          existing.idempotency_key !== request.idempotencyKey
        ) {
          throw new RunEngineError(
            "MIGRATION_FENCE_CONFLICT",
            `Run ${request.runId} already has a different migration fence`,
          );
        }
        return migrationFenceFromRow(existing);
      }

      const run = this.requireRun(request.runId);
      const head = this.db.prepare(
        "SELECT id, sequence FROM events WHERE run_id = ? ORDER BY sequence DESC LIMIT 1",
      ).get(request.runId) as {
        readonly id: EventId;
        readonly sequence: number;
      } | undefined;
      if (
        run.head_sequence !== request.expectedHeadSequence ||
        head?.sequence !== request.expectedHeadSequence ||
        head?.id !== request.expectedHeadEventId
      ) {
        throw new RunEngineError(
          "MIGRATION_FENCE_CAS_MISMATCH",
          `Run ${request.runId} changed before its migration fence was acquired`,
        );
      }
      const activeLease = this.db.prepare(
        "SELECT 1 FROM run_leases WHERE run_id = ? AND expires_at_ms > ? LIMIT 1",
      ).get(request.runId, this.nowMs());
      const activeAttempt = this.db.prepare(
        `SELECT 1 FROM attempts AS a
         JOIN work_offers AS o ON o.id = a.offer_id
         WHERE o.run_id = ? AND a.status = 'active' LIMIT 1`,
      ).get(request.runId);
      const activeOutbox = this.db.prepare(
        "SELECT 1 FROM outbox WHERE run_id = ? AND status = 'claimed' LIMIT 1",
      ).get(request.runId);
      const activeArtifactWriter = this.db.prepare(
        "SELECT 1 FROM artifact_write_intents LIMIT 1",
      ).get();
      if (
        activeLease !== undefined ||
        activeAttempt !== undefined ||
        activeOutbox !== undefined ||
        activeArtifactWriter !== undefined
      ) {
        throw new RunEngineError(
          "MIGRATION_ACTIVE_WORK",
          `Run ${request.runId} has an active coordinator, claim, outbox worker, or artifact writer`,
        );
      }
      const fence: RunMigrationFence = {
        schemaVersion: "run-migration-fence/1",
        fenceId: this.ids.next<string>("migration-fence"),
        ...request,
        acquiredAt: this.now(),
      };
      this.db.prepare(
        `INSERT INTO run_migration_fences(
           run_id, fence_id, expected_head_sequence, expected_head_event_id,
           idempotency_key, acquired_at
         ) VALUES (?, ?, ?, ?, ?, ?)`,
      ).run(
        fence.runId,
        fence.fenceId,
        fence.expectedHeadSequence,
        fence.expectedHeadEventId,
        fence.idempotencyKey,
        fence.acquiredAt,
      );
      return fence;
    })();
  }

  async checkpointMigrationFence(
    fence: RunMigrationFence,
  ): Promise<RunMigrationCheckpoint> {
    this.assertOpen();
    this.requireMigrationFence(fence);
    const rows = this.db.pragma("wal_checkpoint(TRUNCATE)") as readonly RunMigrationCheckpoint[];
    const checkpoint = rows[0];
    if (
      checkpoint === undefined ||
      checkpoint.busy !== 0 ||
      checkpoint.log !== checkpoint.checkpointed
    ) {
      throw new RunEngineError(
        "MIGRATION_WAL_BUSY",
        `Run ${fence.runId} could not checkpoint every WAL frame under its migration fence`,
      );
    }
    this.requireMigrationFence(fence);
    return checkpoint;
  }

  async releaseMigrationFence(fence: RunMigrationFence): Promise<void> {
    this.assertOpen();
    immediateTransaction(this.db, () => {
      this.requireMigrationFence(fence);
      const released = this.db.prepare(
        "DELETE FROM run_migration_fences WHERE run_id = ? AND fence_id = ?",
      ).run(fence.runId, fence.fenceId);
      if (released.changes !== 1) {
        throw new RunEngineError(
          "MIGRATION_FENCE_STALE",
          `Migration fence ${fence.fenceId} is stale`,
        );
      }
    })();
  }

  async planMigration(request: PlanMigrationRequest): Promise<MigrationPlan> {
    this.assertOpen();
    return this.buildMigrationPlan(request.runId, request.targetBundleVersion);
  }

  async migrate(request: MigrationRequest): Promise<MigrationPlan> {
    this.assertOpen();
    const { runId } = request;
    return immediateTransaction(this.db, () => {
      const existing = this.db.prepare(
        `SELECT plan_json FROM run_migrations WHERE run_id = ? AND idempotency_key = ?`,
      ).get(runId, request.idempotencyKey) as { readonly plan_json: string } | undefined;
      if (existing !== undefined) {
        return parseJson<MigrationPlan>(existing.plan_json, "stored migration plan");
      }
      const lease = this.db.prepare(
        "SELECT expires_at_ms FROM run_leases WHERE run_id = ?",
      ).get(runId) as { readonly expires_at_ms: number } | undefined;
      if (lease !== undefined && lease.expires_at_ms > this.nowMs()) {
        throw new RunEngineError(
          "MIGRATION_RUN_LEASED",
          `Run ${runId} has an active coordinator lease`,
        );
      }

      // Rebuild inside the write transaction. This is both the final snapshot
      // validation and the optimistic-concurrency boundary for a dry plan.
      const plan = this.buildMigrationPlan(runId, request.targetBundleVersion);
      if (
        request.expectedFrom !== plan.expectedFrom ||
        request.targetBundleVersion !== plan.targetBundleVersion ||
        request.expectedHeadEventId !== plan.expectedHeadEventId
      ) {
        throw new RunEngineError(
          "MIGRATION_CAS_MISMATCH",
          `Migration ${request.migrationId} no longer matches the planned run head`,
        );
      }
      if (request.migrationId.length === 0 || request.idempotencyKey.length === 0) {
        throw new RunEngineError("MIGRATION_REQUEST_INVALID", "Migration IDs must be non-empty");
      }
      if (plan.actors.length === 0) {
        throw new RunEngineError("MIGRATION_NOT_REQUIRED", `Run ${runId} is already v2`);
      }
      const run = this.requireMutableRun(runId);
      const now = this.now();
      const nowMs = this.nowMs();
      let sequence = run.head_sequence;
      let lastMigrationEventId: EventId | undefined;
      for (const migration of plan.actors) {
        const actor = this.requireActor(migration.actorId);
        const stored = this.requireCurrentSnapshot(actor);
        const storedSnapshot = parseJson<JsonMachineSnapshot>(
          stored.snapshot_json,
          `actor ${actor.id} snapshot`,
        );
        const snapshot = this.transformMigrationSnapshot(actor, storedSnapshot);
        this.assertMigrationSnapshotEquivalent(actor, snapshot, migration, storedSnapshot);
        ensureMachineVersion(this.db, migration.machine, migration.toVersion, now);
        const eventId = this.ids.next<EventId>("event");
        lastMigrationEventId = eventId;
        const nextSnapshotNumber = actor.current_snapshot_number + 1;
        sequence += 1;
        insertSnapshotEvent(this.db, {
          eventId,
          runId,
          sequence,
          actorId: actor.id,
          type: "@@engine/snapshot_version_migrated",
          payload: {
            type: "@@engine/snapshot_version_migrated",
            fromVersion: migration.fromVersion,
            toVersion: migration.toVersion,
            backup: {
              actorId: actor.id,
              snapshotNumber: actor.current_snapshot_number,
              machineVersion: actor.machine_version,
            },
          },
          previousSnapshotNumber: actor.current_snapshot_number,
          nextSnapshotNumber,
          previousState: actor.current_state,
          snapshot,
          machineVersion: migration.toVersion,
          causationEventId: null,
          correlationId: `snapshot-migration:${actor.id}:${actor.current_snapshot_number}`,
          inboxId: null,
          now,
        });
        const visitId = this.openMigrationStateVisit(actor, snapshot, eventId, now);
        this.db.prepare(
          `UPDATE actors SET machine_version = ?, current_state = ?, current_context_json = ?,
             current_snapshot_number = ?, current_visit_id = ?, status = 'active', updated_at = ?
           WHERE id = ? AND machine_version = ? AND current_snapshot_number = ?`,
        ).run(
          migration.toVersion,
          stateKey(snapshot.value),
          stringifyJson(snapshot.context),
          nextSnapshotNumber,
          visitId,
          now,
          actor.id,
          migration.fromVersion,
          actor.current_snapshot_number,
        );
        enqueueInbox(this.db, {
          id: this.ids.next<InboxId>("inbox"),
          runId,
          actorId: actor.id,
          type: "MIGRATION_DURABLE_BACKFILL",
          payload: { type: "MIGRATION_DURABLE_BACKFILL" },
          idempotencyKey: `snapshot-migration-backfill:${request.migrationId}:${actor.id}`,
          causationEventId: eventId,
          correlationId: `snapshot-migration:${request.migrationId}`,
          priority: -100,
          availableAtMs: nowMs,
          now,
        });
      }
      if (lastMigrationEventId !== undefined) {
        this.supersedeRunOutstandingOffers(
          runId,
          lastMigrationEventId,
          "Superseded by the v1 to v2 durable migration; fresh reconciliation and approval are required",
          now,
        );
      }
      ensureMachineVersion(this.db, run.machine_name, currentMachineVersion(run.machine_name), now);
      const updated = this.db.prepare(
        `UPDATE runs SET machine_version = ?, head_sequence = ?, version = version + 1,
           updated_at = ? WHERE id = ? AND machine_version = ? AND head_sequence = ?`,
      ).run(
        currentMachineVersion(run.machine_name),
        sequence,
        now,
        runId,
        run.machine_version,
        run.head_sequence,
      );
      if (updated.changes !== 1) {
        throw new RunEngineError(
          "SNAPSHOT_MIGRATION_STALE",
          `Run ${runId} changed while its snapshots were being migrated`,
        );
      }
      this.db.prepare(
        `INSERT INTO run_migrations(
          migration_id, run_id, idempotency_key, expected_from,
          target_bundle_version, expected_head_event_id, plan_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        request.migrationId,
        runId,
        request.idempotencyKey,
        request.expectedFrom,
        request.targetBundleVersion,
        request.expectedHeadEventId,
        stringifyJson(plan as unknown as JsonObject),
        now,
      );
      this.failpoints.hit("snapshot_migration.before_commit", {
        runId,
        migrationCount: plan.actors.length,
      });
      this.reconcileRunStatus(runId, sequence, now);
      return plan;
    })();
  }

  async readArtifact(artifactId: ArtifactId): Promise<ReadArtifactResult> {
    this.assertOpen();
    const row = this.db.prepare("SELECT * FROM artifacts WHERE id = ?").get(artifactId) as
      | StoredArtifactRow
      | undefined;
    if (row === undefined) {
      throw new RunEngineError("ARTIFACT_NOT_FOUND", `Artifact ${artifactId} does not exist`);
    }
    const bytes = this.readStoredArtifactBytes(row);
    const parentRows = this.db
      .prepare(
        `SELECT parent_artifact_id AS artifactId, relation
         FROM artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal`,
      )
      .all(artifactId) as readonly {
      readonly artifactId: ArtifactId;
      readonly relation: string;
    }[];
    const artifact: ArtifactView = {
      id: row.id,
      kind: row.kind,
      schemaVersion: row.schema_version,
      mediaType: row.media_type,
      origin: row.origin,
      sizeBytes: row.size_bytes,
      parents: parentRows,
      metadata: parseJson<JsonObject>(row.metadata_json, `artifact ${row.id} metadata`),
      createdAt: row.created_at,
      ...(row.producing_run_id === null ? {} : { producingRunId: row.producing_run_id }),
      ...(row.producing_actor_id === null ? {} : { producingActorId: row.producing_actor_id }),
      ...(row.producing_attempt_id === null
        ? {}
        : { producingAttemptId: row.producing_attempt_id }),
      ...(row.producing_offer_id === null ? {} : { producingOfferId: row.producing_offer_id }),
      ...(row.supersedes_artifact_id === null
        ? {}
        : { supersedes: row.supersedes_artifact_id }),
    };
    return { artifact, bytes };
  }

  private readStoredArtifactBytes(row: StoredArtifactRow): Buffer {
    return row.storage_kind === "inline"
      ? Buffer.from(row.inline_payload ?? Buffer.alloc(0))
      : this.store.read(requiredStoredPath(row));
  }

  async readBytes(artifactId: ArtifactId): Promise<Uint8Array> {
    return (await this.readArtifact(artifactId)).bytes;
  }

  async readText(artifactId: ArtifactId): Promise<string> {
    return Buffer.from(await this.readBytes(artifactId)).toString("utf8");
  }

  async collectOrphanedArtifacts(): Promise<readonly ArtifactId[]> {
    this.assertOpen();
    return immediateTransaction(this.db, () => {
      this.assertNoMigrationFences();
      const nowMs = this.nowMs();
      const referenced = new Set(
        (this.db
          .prepare(
            `SELECT relative_path FROM artifacts
             WHERE storage_kind = 'file' AND relative_path IS NOT NULL`,
          )
          .all() as readonly { readonly relative_path: string }[])
          .map((row) => row.relative_path),
      );
      const activeIntents = this.db
        .prepare(
          `SELECT artifact_id FROM artifact_write_intents
           WHERE expires_at_ms > ?`,
        )
        .all(nowMs) as readonly { readonly artifact_id: ArtifactId }[];
      for (const intent of activeIntents) {
        referenced.add(`artifacts/${intent.artifact_id}/payload`);
      }
      const collected = this.store.collectUnreferenced(referenced);
      this.db.prepare(
        "DELETE FROM artifact_write_intents WHERE expires_at_ms <= ?",
      ).run(nowMs);
      return collected;
    })();
  }

  close(): void {
    if (!this.closed) {
      try {
        const checkpoint = this.db.pragma("wal_checkpoint(TRUNCATE)") as readonly {
          readonly busy: number;
          readonly log: number;
          readonly checkpointed: number;
        }[];
        if (checkpoint.some((result) => result.busy !== 0)) {
          throw new RunEngineError(
            "WAL_CHECKPOINT_BUSY",
            "RunEngine could not checkpoint every WAL frame before close",
          );
        }
      } finally {
        this.db.close();
        this.closed = true;
      }
    }
  }

  private createRun(
    spec: RunSpec,
    ancestry?: { readonly parentRunId: RunId; readonly sequence: number },
    forkChanges: readonly RunInputChange[] = [],
    onlyPrepare: readonly ArtifactSeed[] = spec.artifacts,
    startKey = operationStartKey(undefined, this.ids.next<string>("start")),
  ): RunId {
    this.assertNoMigrationFences();
    const canonicalSpec = stableStringify(spec as unknown as JsonObject);
    const existingStart = this.loadRunStart(startKey);
    if (existingStart !== undefined) {
      assertSameStartRequest(startKey, canonicalSpec, existingStart.specJson);
      assertSameRunOperation(
        this.db,
        startKey,
        existingStart.runId,
        ancestry?.parentRunId,
        forkChanges,
      );
      return existingStart.runId;
    }
    const runId = this.ids.next<RunId>("run");
    const actorId = this.ids.next<ActorId>("actor");
    const eventId = this.ids.next<EventId>("event");
    const visitId = this.ids.next<StateVisitId>("visit");
    const inboxId = this.ids.next<InboxId>("inbox");
    const now = this.now();
    const machine = spec.kind;
    const machineVersion = currentMachineVersion(machine);
    const logicalKey = `${spec.kind}:${runId}`;
    const input = rootMachineInput(spec, actorId, logicalKey);
    const initial = initialSnapshotFor(machine, input);
    if (initial.effects.length > 0) {
      throw new RunEngineError(
        "MACHINE_INITIAL_EFFECTS",
        `Machine ${machine} must enter idle without effects before durable START`,
      );
    }
    const prepared = onlyPrepare.flatMap((seed) => {
      const record = this.prepareRunSeed(seed, now, runId, `start:${startKey}`);
      return record === undefined ? [] : [record];
    });
    this.failpoints.hit("start.after_artifact_rename", {
      runId,
      artifactCount: prepared.length,
    });

    let committedRunId = runId;
    let created = false;
    immediateTransaction(this.db, () => {
      this.assertNoMigrationFences();
      const duplicate = this.loadRunStart(startKey);
      if (duplicate !== undefined) {
        assertSameStartRequest(startKey, canonicalSpec, duplicate.specJson);
        assertSameRunOperation(
          this.db,
          startKey,
          duplicate.runId,
          ancestry?.parentRunId,
          forkChanges,
        );
        committedRunId = duplicate.runId;
        return;
      }
      if (ancestry !== undefined) {
        const parent = this.requireRun(ancestry.parentRunId);
        if (parent.head_sequence !== ancestry.sequence) {
          throw new RunEngineError(
            "FORK_PARENT_ADVANCED",
            `Parent run ${parent.id} advanced while its fork was being prepared`,
          );
        }
      }
      ensureMachineVersion(this.db, machine, machineVersion, now);
      this.db.prepare(
        `INSERT INTO runs(
          id, kind, status, machine_name, machine_version, spec_json,
          metadata_json, parent_run_id, forked_from_sequence, head_sequence,
          version, created_at, updated_at
        ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)`,
      ).run(
        runId,
        spec.kind,
        machine,
        machineVersion,
        stringifyJson(spec as unknown as JsonObject),
        stringifyJson(spec.metadata ?? {}),
        ancestry?.parentRunId ?? null,
        ancestry?.sequence ?? null,
        now,
        now,
      );
      this.db.prepare(
        `INSERT INTO run_starts(idempotency_key, run_id, spec_json, created_at)
         VALUES (?, ?, ?, ?)`,
      ).run(startKey, runId, canonicalSpec, now);
      this.insertPreparedArtifacts(prepared);
      this.db.prepare(
        `INSERT INTO actors(
          id, run_id, parent_actor_id, logical_key, machine_name,
          machine_version, status, current_state, current_context_json,
          current_snapshot_number, current_visit_id, input_json, created_at, updated_at
        ) VALUES (?, ?, NULL, ?, ?, ?, 'active', ?, ?, 1, ?, ?, ?, ?)`,
      ).run(
        actorId,
        runId,
        logicalKey,
        machine,
        machineVersion,
        stateKey(initial.snapshot.value),
        stringifyJson(initial.snapshot.context),
        visitId,
        stringifyJson(input),
        now,
        now,
      );
      insertSnapshotEvent(
        this.db,
        {
          eventId,
          runId,
          sequence: 1,
          actorId,
          type: "@@engine/initialized",
          payload: { type: "@@engine/initialized" },
          previousSnapshotNumber: null,
          nextSnapshotNumber: 1,
          previousState: null,
          snapshot: initial.snapshot,
          machineVersion,
          causationEventId: null,
          correlationId: null,
          inboxId: null,
          now,
        },
      );
      this.db.prepare(
        `INSERT INTO state_visits(
          id, actor_id, state_key, visit_number, entered_event_id, created_at
        ) VALUES (?, ?, ?, 1, ?, ?)`,
      ).run(visitId, actorId, stateKey(initial.snapshot.value), eventId, now);
      this.attachRunInputs(runId, spec);
      enqueueInbox(this.db, {
        id: inboxId,
        runId,
        actorId,
        type: "START",
        payload: { type: "START" },
        idempotencyKey: `start:${actorId}`,
        causationEventId: eventId,
        correlationId: runId,
        availableAtMs: this.nowMs(),
        now,
      });
      forkChanges.forEach((change, ordinal) => {
        if (change.kind === "replace_artifact") {
          this.db.prepare(
            `INSERT INTO fork_changes(
              run_id, ordinal, kind, old_artifact_id, new_artifact_id
            ) VALUES (?, ?, 'replace_artifact', ?, ?)`,
          ).run(runId, ordinal, change.from, change.to.id);
        } else {
          this.db.prepare(
            `INSERT INTO fork_changes(run_id, ordinal, kind, path, value_json)
             VALUES (?, ?, 'replace_spec', ?, ?)`,
          ).run(runId, ordinal, change.path, stringifyJson(change.value));
        }
      });
      this.failpoints.hit("start.before_commit", { runId });
      created = true;
    })();
    if (!created) {
      return committedRunId;
    }
    this.failpoints.hit("start.after_commit", { runId });
    return runId;
  }

  private attachRunInputs(runId: RunId, spec: RunSpec): void {
    spec.artifacts.forEach((seed, ordinal) => {
      requireArtifactExists(this.db, seed.id);
      this.db.prepare(
        "INSERT INTO run_inputs(run_id, input_name, ordinal, artifact_id) VALUES (?, ?, ?, ?)",
      ).run(runId, "artifacts", ordinal, seed.id);
    });
    const known = new Set(
      (this.db.prepare("SELECT id FROM artifacts").all() as readonly { readonly id: string }[]).map(
        (row) => row.id,
      ),
    );
    for (const reference of collectArtifactReferences(spec, known)) {
      requireArtifactExists(this.db, reference.artifactId);
      this.db.prepare(
        "INSERT INTO run_inputs(run_id, input_name, ordinal, artifact_id) VALUES (?, ?, 0, ?)",
      ).run(runId, reference.path, reference.artifactId);
    }
  }

  private loadRunStart(
    idempotencyKey: string,
  ): { readonly runId: RunId; readonly specJson: string } | undefined {
    const row = this.db
      .prepare(
        `SELECT run_id, spec_json FROM run_starts WHERE idempotency_key = ?`,
      )
      .get(idempotencyKey) as
      | { readonly run_id: RunId; readonly spec_json: string }
      | undefined;
    return row === undefined
      ? undefined
      : { runId: row.run_id, specJson: row.spec_json };
  }

  private prepareRunSeed(
    seed: ArtifactSeed,
    now: string,
    runId: RunId,
    holderId: string,
  ): ArtifactRecord | undefined {
    const existing = this.db
      .prepare("SELECT * FROM artifacts WHERE id = ?")
      .get(seed.id) as StoredArtifactRow | undefined;
    if (existing === undefined) {
      return recordFromSeed(
        seed,
        this.prepareOwnedPayload(seed.id, seed.payload, holderId),
        now,
        runId,
      );
    }
    const expectedPayload = this.store.prepare(seed.id, seed.payload);
    const parents = this.db
      .prepare(
        `SELECT parent_artifact_id AS artifactId, relation
         FROM artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal`,
      )
      .all(seed.id) as readonly {
      readonly artifactId: ArtifactId;
      readonly relation: string;
    }[];
    const payloadMatches =
      existing.storage_kind === expectedPayload.storageKind &&
      existing.size_bytes === expectedPayload.sizeBytes &&
      (existing.storage_kind === "file"
        ? existing.relative_path === expectedPayload.relativePath
        : Buffer.from(existing.inline_payload ?? Buffer.alloc(0)).equals(
            expectedPayload.inlinePayload ?? Buffer.alloc(0),
          ));
    if (
      existing.kind !== seed.kind ||
      existing.schema_version !== seed.schemaVersion ||
      existing.media_type !== seed.mediaType ||
      existing.origin !== seed.origin ||
      existing.supersedes_artifact_id !== (seed.supersedes ?? null) ||
      stableStringify(parseJson<JsonObject>(existing.metadata_json, `artifact ${seed.id} metadata`)) !==
        stableStringify(seed.metadata ?? {}) ||
      stableStringify(parents as unknown as JsonValue) !==
        stableStringify((seed.parents ?? []) as unknown as JsonValue) ||
      !payloadMatches
    ) {
      throw new RunEngineError(
        "ARTIFACT_IMMUTABLE",
        `Artifact ${seed.id} already exists with different immutable content`,
      );
    }
    return undefined;
  }

  private prepareOwnedPayload(
    artifactId: ArtifactId,
    payload: ArtifactPayload,
    holderId: string,
  ): PreparedPayload {
    if (payload.kind !== "file") {
      return this.store.prepare(artifactId, payload);
    }
    const intent = this.reserveArtifactWrite(artifactId, holderId);
    return {
      ...this.store.prepare(artifactId, payload),
      writeIntent: intent,
    };
  }

  private reserveArtifactWrite(
    artifactId: ArtifactId,
    holderId: string,
  ): { readonly holderId: string; readonly fence: number } {
    const now = this.now();
    const nowMs = this.nowMs();
    return immediateTransaction(this.db, () => {
      this.assertNoMigrationFences();
      const existing = this.db
        .prepare(
          `SELECT holder_id, fence, expires_at_ms
           FROM artifact_write_intents WHERE artifact_id = ?`,
        )
        .get(artifactId) as
        | { readonly holder_id: string; readonly fence: number; readonly expires_at_ms: number }
        | undefined;
      if (
        existing !== undefined &&
        existing.expires_at_ms > nowMs &&
        existing.holder_id !== holderId
      ) {
        throw new RunEngineError(
          "ARTIFACT_WRITE_BUSY",
          `Artifact ${artifactId} is being prepared by another fenced writer`,
        );
      }
      const fence =
        existing === undefined
          ? 1
          : existing.holder_id === holderId && existing.expires_at_ms > nowMs
            ? existing.fence
            : existing.fence + 1;
      this.db.prepare(
        `INSERT INTO artifact_write_intents(
           artifact_id, holder_id, fence, expires_at_ms, created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(artifact_id) DO UPDATE SET
           holder_id = excluded.holder_id,
           fence = excluded.fence,
           expires_at_ms = excluded.expires_at_ms,
           updated_at = excluded.updated_at`,
      ).run(
        artifactId,
        holderId,
        fence,
        nowMs + this.artifactWriteLeaseMs,
        now,
        now,
      );
      return { holderId, fence };
    })();
  }

  private insertPreparedArtifacts(records: readonly ArtifactRecord[]): void {
    const nowMs = this.nowMs();
    for (const record of records) {
      if (record.payload.storageKind !== "file") {
        continue;
      }
      const intent = record.payload.writeIntent;
      if (intent === undefined) {
        throw new RunEngineError(
          "ARTIFACT_WRITE_UNFENCED",
          `File artifact ${record.id} has no durable write intent`,
        );
      }
      const live = this.db
        .prepare(
          `SELECT holder_id, fence, expires_at_ms
           FROM artifact_write_intents WHERE artifact_id = ?`,
        )
        .get(record.id) as
        | { readonly holder_id: string; readonly fence: number; readonly expires_at_ms: number }
        | undefined;
      if (
        live === undefined ||
        live.holder_id !== intent.holderId ||
        live.fence !== intent.fence ||
        live.expires_at_ms <= nowMs
      ) {
        throw new RunEngineError(
          "ARTIFACT_WRITE_STALE",
          `File artifact ${record.id} lost its write fence before commit`,
        );
      }
    }
    insertArtifactRecords(this.db, records);
    for (const record of records) {
      const intent = record.payload.writeIntent;
      if (intent === undefined) {
        continue;
      }
      const released = this.db.prepare(
        `DELETE FROM artifact_write_intents
         WHERE artifact_id = ? AND holder_id = ? AND fence = ?`,
      ).run(record.id, intent.holderId, intent.fence);
      if (released.changes !== 1) {
        throw new RunEngineError(
          "ARTIFACT_WRITE_STALE",
          `File artifact ${record.id} lost its write fence during commit`,
        );
      }
    }
  }

  private requireMutableRun(runId: RunId): RunMutationRow {
    const run = this.requireRun(runId);
    const fence = this.db.prepare(
      "SELECT fence_id FROM run_migration_fences WHERE run_id = ?",
    ).get(runId) as { readonly fence_id: string } | undefined;
    if (fence !== undefined) {
      throw new RunEngineError(
        "RUN_MIGRATION_FENCED",
        `Run ${runId} is fenced by migration ${fence.fence_id}`,
      );
    }
    if (run.sealed_at !== null) {
      throw new RunEngineError("RUN_SEALED", `Run ${runId} is sealed and immutable`);
    }
    return run;
  }

  private assertNoMigrationFences(): void {
    const fence = this.db.prepare(
      "SELECT run_id, fence_id FROM run_migration_fences ORDER BY acquired_at LIMIT 1",
    ).get() as { readonly run_id: RunId; readonly fence_id: string } | undefined;
    if (fence !== undefined) {
      throw new RunEngineError(
        "RUN_MIGRATION_FENCED",
        `Run ${fence.run_id} is fenced by migration ${fence.fence_id}`,
      );
    }
  }

  private requireMigrationFence(fence: RunMigrationFence): void {
    if (fence.schemaVersion !== "run-migration-fence/1") {
      throw new RunEngineError("MIGRATION_FENCE_STALE", "Migration fence schema is invalid");
    }
    const stored = this.db.prepare(
      `SELECT run_id, fence_id, expected_head_sequence, expected_head_event_id,
              idempotency_key, acquired_at
       FROM run_migration_fences WHERE run_id = ?`,
    ).get(fence.runId) as {
      readonly run_id: RunId;
      readonly fence_id: string;
      readonly expected_head_sequence: number;
      readonly expected_head_event_id: EventId;
      readonly idempotency_key: string;
      readonly acquired_at: string;
    } | undefined;
    if (
      stored === undefined ||
      stored.fence_id !== fence.fenceId ||
      stored.expected_head_sequence !== fence.expectedHeadSequence ||
      stored.expected_head_event_id !== fence.expectedHeadEventId ||
      stored.idempotency_key !== fence.idempotencyKey ||
      stored.acquired_at !== fence.acquiredAt
    ) {
      throw new RunEngineError(
        "MIGRATION_FENCE_STALE",
        `Migration fence ${fence.fenceId} is stale`,
      );
    }
  }

  private assertRunSpecSourceProvenance(spec: RunSpec): void {
    if (spec.kind === "article") {
      for (const [index, extraction] of spec.article.sources.entries()) {
        this.assertApprovedArticleSource(
          extraction,
          spec.article.sourceApprovalArtifacts[index],
          spec.artifacts,
        );
      }
      return;
    }
    for (const source of spec.edition.sources) {
      this.assertSourceProvenance(source, spec.artifacts);
    }
  }

  /**
   * A standalone article may only receive a committed source extraction. The
   * source actor owns the lead, raw-evidence, and human-review lifecycle; it
   * never treats an arbitrary artifact-store reference as source authority.
   */
  private assertApprovedArticleSource(
    extraction: ArtifactId,
    approval: ArtifactId | undefined,
    seeds: readonly ArtifactSeed[],
  ): void {
    const extractionInfo = this.sourceArtifactInfo(extraction, seeds);
    if (extractionInfo.kind !== "source_extraction") {
      throw new RunEngineError(
        "SOURCE_PROVENANCE_INVALID",
        `Article source ${extraction} must be a source_extraction artifact`,
      );
    }
    if (approval === undefined) {
      throw new RunEngineError(
        "SOURCE_PROVENANCE_INVALID",
        `Article source ${extraction} has no aligned human source-review approval`,
      );
    }
    const approvalInfo = this.sourceArtifactInfo(approval, seeds);
    if (approvalInfo.kind !== "source_review_decision" || approvalInfo.origin !== "human") {
      throw new RunEngineError(
        "SOURCE_PROVENANCE_INVALID",
        `Article source approval ${approval} must be a human source_review_decision`,
      );
    }
    const rawBundle = this.sourceAncestorOfKind(extraction, "raw_source_bundle", seeds);
    const rawEvidence = this.sourceAncestorOfKind(extraction, "raw_evidence", seeds);
    const lead = this.sourceAncestorOfKind(extraction, "submitted_lead", seeds)
      ?? this.sourceAncestorOfKind(extraction, "source_lead", seeds);
    if (rawBundle === undefined || rawEvidence === undefined || lead === undefined ||
      !this.hasSourceArtifactAncestor(approval, extraction, seeds) ||
      !this.hasSourceArtifactAncestor(approval, rawBundle, seeds)) {
      throw new RunEngineError(
        "SOURCE_PROVENANCE_INVALID",
        `Article source approval ${approval} is not bound to ${extraction}'s lead/raw/extraction tuple`,
      );
    }
    const persisted = this.db.prepare(
      `SELECT 1
       FROM decisions decision
       JOIN work_offers offer ON offer.id = decision.offer_id
       WHERE decision.artifact_id = ?
         AND decision.authority = 'human'
         AND decision.choice = 'approved'
         AND offer.role = 'review_source'
       LIMIT 1`,
    ).get(approval);
    if (persisted === undefined) {
      throw new RunEngineError(
        "SOURCE_PROVENANCE_INVALID",
        `Article source approval ${approval} has no persisted human review decision`,
      );
    }
  }

  private sourceAncestorOfKind(
    descendant: ArtifactId,
    kind: string,
    seeds: readonly ArtifactSeed[],
  ): ArtifactId | undefined {
    const pending = [descendant];
    const seen = new Set<ArtifactId>();
    while (pending.length > 0) {
      const current = pending.pop();
      if (current === undefined || seen.has(current)) {
        continue;
      }
      seen.add(current);
      for (const parent of this.sourceArtifactInfo(current, seeds).parents) {
        if (this.sourceArtifactInfo(parent, seeds).kind === kind) {
          return parent;
        }
        pending.push(parent);
      }
    }
    return undefined;
  }

  /**
   * Prepared sources are reusable only when their immutable graph proves the
   * lead, raw capture, extraction, and human approval chain. A URL or boolean
   * marker is intentionally not authority to skip source review.
   */
  private assertSourceProvenance(
    source: SourceRunSpec,
    seeds: readonly ArtifactSeed[],
  ): void {
    if (source.approvalArtifact === undefined) {
      return;
    }
    const rawBundle = source.rawBundleArtifact;
    const extraction = source.extractionArtifact;
    const metadata = source.metadataArtifact;
    const rawEvidence = source.rawEvidenceArtifacts ?? [];
    if (
      rawBundle === undefined ||
      extraction === undefined ||
      metadata === undefined ||
      rawEvidence.length === 0
    ) {
      throw new RunEngineError(
        "SOURCE_PROVENANCE_INVALID",
        `Prepared source ${source.sourceId} needs raw evidence, extraction, metadata, and approval`,
      );
    }
    const expected: readonly (readonly [ArtifactId, string, ArtifactOrigin | undefined])[] = [
      [rawBundle, "raw_source_bundle", undefined],
      [extraction, "source_extraction", undefined],
      [metadata, "source_metadata", undefined],
      [source.approvalArtifact, "source_review_decision", "human"],
      ...rawEvidence.map((artifactId) => [artifactId, "raw_evidence", undefined] as const),
    ];
    for (const [artifactId, kind, origin] of expected) {
      const actual = this.sourceArtifactInfo(artifactId, seeds);
      if (actual.kind !== kind) {
        throw new RunEngineError(
          "SOURCE_PROVENANCE_INVALID",
          `Prepared source ${source.sourceId} expects ${artifactId} to be ${kind}`,
        );
      }
      if (origin !== undefined && actual.origin !== origin) {
        throw new RunEngineError(
          "SOURCE_PROVENANCE_INVALID",
          `Prepared source ${source.sourceId} approval ${artifactId} must be human-authored`,
        );
      }
    }
    const requireAncestor = (child: ArtifactId, ancestor: ArtifactId, label: string): void => {
      if (!this.hasSourceArtifactAncestor(child, ancestor, seeds)) {
        throw new RunEngineError(
          "SOURCE_PROVENANCE_INVALID",
          `Prepared source ${source.sourceId} lacks ${label} provenance`,
        );
      }
    };
    requireAncestor(rawBundle, source.leadArtifact, "lead to raw bundle");
    for (const evidence of rawEvidence) {
      requireAncestor(evidence, source.leadArtifact, "lead to raw evidence");
    }
    requireAncestor(extraction, rawBundle, "raw bundle to extraction");
    requireAncestor(source.approvalArtifact, rawBundle, "raw bundle to approval");
    requireAncestor(source.approvalArtifact, extraction, "extraction to approval");
  }

  private sourceArtifactInfo(
    artifactId: ArtifactId,
    seeds: readonly ArtifactSeed[],
  ): { readonly kind: string; readonly origin: ArtifactOrigin; readonly parents: readonly ArtifactId[] } {
    const seed = seeds.find((candidate) => candidate.id === artifactId);
    if (seed !== undefined) {
      return {
        kind: seed.kind,
        origin: seed.origin,
        parents: (seed.parents ?? []).map((parent) => parent.artifactId),
      };
    }
    const row = this.db.prepare(
      "SELECT kind, origin FROM artifacts WHERE id = ?",
    ).get(artifactId) as { readonly kind: string; readonly origin: ArtifactOrigin } | undefined;
    if (row === undefined) {
      throw new RunEngineError("SOURCE_PROVENANCE_INVALID", `Unknown source artifact ${artifactId}`);
    }
    const parents = this.db.prepare(
      "SELECT parent_artifact_id FROM artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal",
    ).all(artifactId) as readonly { readonly parent_artifact_id: ArtifactId }[];
    return { ...row, parents: parents.map((parent) => parent.parent_artifact_id) };
  }

  private hasSourceArtifactAncestor(
    descendant: ArtifactId,
    ancestor: ArtifactId,
    seeds: readonly ArtifactSeed[],
  ): boolean {
    const pending = [descendant];
    const seen = new Set<ArtifactId>();
    while (pending.length > 0) {
      const current = pending.pop();
      if (current === undefined || seen.has(current)) {
        continue;
      }
      seen.add(current);
      for (const parent of this.sourceArtifactInfo(current, seeds).parents) {
        if (parent === ancestor) {
          return true;
        }
        pending.push(parent);
      }
    }
    return false;
  }

  private requireOpenCollectionActor(
    runId: RunId,
    sourceId: string,
  ): ActorMutationRow {
    const run = this.requireMutableRun(runId);
    if (run.kind !== "edition" || run.machine_name !== "edition") {
      throw new RunEngineError(
        "RUN_KIND_MISMATCH",
        `Run ${runId} is not an edition collection`,
      );
    }
    this.assertMachineCurrent(run.machine_name, run.machine_version);
    if (isTerminalStatus(run.status)) {
      throw new RunEngineError(
        "COLLECTION_CLOSED",
        `Edition run ${runId} is already ${run.status}`,
      );
    }
    const actor = this.db
      .prepare(
        `SELECT * FROM actors
         WHERE run_id = ? AND parent_actor_id IS NULL`,
      )
      .get(runId) as ActorMutationRow | undefined;
    if (actor === undefined) {
      throw new RunEngineError(
        "ACTOR_NOT_FOUND",
        `Edition run ${runId} has no root collection actor`,
      );
    }
    this.assertMachineCurrent(actor.machine_name, actor.machine_version);
    if (actor.current_state !== "collecting") {
      throw new RunEngineError(
        "COLLECTION_CLOSED",
        `Edition run ${runId} cannot accept leads from ${actor.current_state}`,
      );
    }
    const context = parseJson<JsonObject>(
      actor.current_context_json,
      `edition actor ${actor.id} context`,
    );
    const sources = context.sources;
    if (!Array.isArray(sources)) {
      throw new RunEngineError(
        "SNAPSHOT_INVALID",
        `Edition actor ${actor.id} has no durable source collection`,
      );
    }
    const existing = sources.some((candidate) => {
      if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
        return false;
      }
      return candidate.sourceId === sourceId;
    });
    if (existing) {
      throw new RunEngineError(
        "LEAD_SOURCE_DUPLICATE",
        `Edition run ${runId} already contains source ${sourceId}`,
      );
    }
    return actor;
  }

  private materializeCollectedEditionSpec(
    runId: RunId,
    spec: JsonObject,
  ): JsonObject {
    if (spec.kind !== "edition") {
      return spec;
    }
    const edition = jsonObject(spec.edition, `run ${runId} edition spec`);
    if (!Array.isArray(edition.sources)) {
      throw new RunEngineError(
        "SNAPSHOT_INVALID",
        `Edition run ${runId} has no configured source collection`,
      );
    }
    const ordered: SourceRunSpec[] = edition.sources.map((candidate) =>
      parseSourceRunSpec(candidate),
    );
    const sourceIds = new Set(ordered.map((source) => source.sourceId));
    const submissions = this.db
      .prepare(
        `SELECT source_spec_json FROM edition_source_submissions
         WHERE run_id = ? ORDER BY submitted_at, source_id`,
      )
      .all(runId) as readonly { readonly source_spec_json: string }[];
    for (const submission of submissions) {
      const source = parseSourceRunSpec(
        parseJson<JsonObject>(submission.source_spec_json, `run ${runId} source submission`),
      );
      if (!sourceIds.has(source.sourceId)) {
        ordered.push(source);
        sourceIds.add(source.sourceId);
      }
    }

    const sourceContexts = this.db
      .prepare(
        `SELECT current_context_json FROM actors
         WHERE run_id = ? AND machine_name = 'source'
         ORDER BY created_at, id`,
      )
      .all(runId) as readonly { readonly current_context_json: string }[];
    const contexts = new Map<string, JsonObject>();
    for (const row of sourceContexts) {
      const context = parseJson<JsonObject>(
        row.current_context_json,
        `run ${runId} source actor context`,
      );
      if (typeof context.sourceId === "string") {
        contexts.set(context.sourceId, context);
      }
    }
    const materialized = ordered.map((source) =>
      materializeSourceSpec(source, contexts.get(source.sourceId)),
    );
    return {
      ...spec,
      edition: {
        ...edition,
        sources: materialized as unknown as JsonValue,
      },
    };
  }

  private requireActor(actorId: ActorId): ActorMutationRow {
    const actor = this.db.prepare("SELECT * FROM actors WHERE id = ?").get(actorId) as
      | ActorMutationRow
      | undefined;
    if (actor === undefined) {
      throw new RunEngineError("ACTOR_NOT_FOUND", `Actor ${actorId} does not exist`);
    }
    return actor;
  }

  private buildMigrationPlan(
    runId: RunId,
    targetBundleVersion: MachineBundleVersion,
  ): MigrationPlan {
    if (targetBundleVersion !== MACHINE_BUNDLE_V2) {
      throw new RunEngineError(
        "MIGRATION_TARGET_UNSUPPORTED",
        `Only the adjacent ${MACHINE_BUNDLE_V1} to ${MACHINE_BUNDLE_V2} migration is registered`,
      );
    }
    const run = this.requireRun(runId);
    const actors = this.db.prepare(
      `SELECT * FROM actors
       WHERE run_id = ?
       ORDER BY parent_actor_id IS NOT NULL, created_at, id`,
    ).all(runId) as readonly ActorMutationRow[];
    const root = actors.find((actor) => actor.parent_actor_id === null);
    if (root === undefined) {
      throw new RunEngineError(
        "MIGRATION_ROOT_MISSING",
        `Run ${runId} has no live root actor to migrate`,
      );
    }
    if (
      root.machine_name !== run.machine_name ||
      root.machine_version !== run.machine_version
    ) {
      throw new RunEngineError(
        "MIGRATION_INCONSISTENT",
        `Run ${runId} and root actor ${root.id} do not name the same machine version`,
      );
    }

    const migrations: MigrationActorPlan[] = [];
    for (const actor of actors) {
      const targetVersion = currentMachineVersion(actor.machine_name);
      if (actor.machine_version === targetVersion) {
        continue;
      }
      const allowedTarget = SNAPSHOT_MIGRATION_ALLOWLIST[actor.machine_name]?.[
        actor.machine_version
      ];
      if (allowedTarget !== targetVersion) {
        throw new RunEngineError(
          "MIGRATION_UNSUPPORTED",
          `No approved snapshot migration exists for ${actor.machine_name} ${actor.machine_version}`,
        );
      }
      const stored = this.requireCurrentSnapshot(actor);
      if (stored.machine_version !== actor.machine_version) {
        throw new RunEngineError(
          "MIGRATION_INCONSISTENT",
          `Actor ${actor.id} version ${actor.machine_version} disagrees with snapshot ${stored.machine_version}`,
        );
      }
      const snapshot = parseJson<JsonMachineSnapshot>(
        stored.snapshot_json,
        `actor ${actor.id} snapshot`,
      );
      this.assertMigrationSnapshotEquivalent(actor, this.transformMigrationSnapshot(actor, snapshot), {
        actorId: actor.id,
        machine: actor.machine_name,
        fromVersion: actor.machine_version,
        toVersion: targetVersion,
        snapshotNumber: actor.current_snapshot_number,
        state: actor.current_state,
      }, snapshot);
      migrations.push({
        actorId: actor.id,
        machine: actor.machine_name,
        fromVersion: actor.machine_version,
        toVersion: targetVersion,
        snapshotNumber: actor.current_snapshot_number,
        state: actor.current_state,
      });
    }

    const targetRunVersion = currentMachineVersion(run.machine_name);
    const rootMigration = migrations.find((migration) => migration.actorId === root.id);
    if (run.machine_version !== targetRunVersion && rootMigration === undefined) {
      throw new RunEngineError(
        "MIGRATION_INCONSISTENT",
        `Run ${runId} needs ${targetRunVersion}, but its root snapshot is not migratable`,
      );
    }
    const head = this.db.prepare(
      "SELECT id FROM events WHERE run_id = ? AND sequence = ?",
    ).get(runId, run.head_sequence) as { readonly id: EventId } | undefined;
    if (head === undefined) {
      throw new RunEngineError("MIGRATION_INCONSISTENT", `Run ${runId} has no head event`);
    }
    return {
      runId,
      expectedFrom: machineBundleFor(run.machine_name, run.machine_version),
      targetBundleVersion,
      expectedHeadEventId: head.id,
      actors: migrations,
    };
  }

  private requireCurrentSnapshot(actor: ActorMutationRow): {
    readonly machine_version: string;
    readonly snapshot_json: string;
  } {
    const stored = this.db.prepare(
      `SELECT machine_version, snapshot_json FROM actor_snapshots
       WHERE actor_id = ? AND snapshot_number = ?`,
    ).get(actor.id, actor.current_snapshot_number) as
      | { readonly machine_version: string; readonly snapshot_json: string }
      | undefined;
    if (stored === undefined) {
      throw new RunEngineError(
        "SNAPSHOT_MISSING",
        `Actor ${actor.id} snapshot ${actor.current_snapshot_number} is missing`,
      );
    }
    return stored;
  }

  private assertMigrationSnapshotEquivalent(
    actor: ActorMutationRow,
    retainedSnapshot: JsonMachineSnapshot,
    migration: MigrationActorPlan,
    backupSnapshot: JsonMachineSnapshot = retainedSnapshot,
  ): void {
    if (
      stateKey(backupSnapshot.value) !== actor.current_state ||
      stableStringify(backupSnapshot.context) !== stableStringify(parseJson<JsonObject>(
        actor.current_context_json,
        `actor ${actor.id} context`,
      ))
    ) {
      throw new RunEngineError(
        "MIGRATION_INCONSISTENT",
        `Actor ${actor.id} current state does not match its stored snapshot`,
      );
    }
    let preview: MachineTransitionResult;
    try {
      preview = transitionSnapshotFor(actor.machine_name, retainedSnapshot, {
        type: "@@engine/snapshot_migration_validate",
      });
    } catch (error) {
      throw new RunEngineError(
        "MIGRATION_INVALID",
        `Actor ${actor.id} cannot restore as ${migration.toVersion}`,
        { cause: error },
      );
    }
    if (
      preview.effects.length > 0 ||
      stateKey(preview.snapshot.value) !== stateKey(retainedSnapshot.value) ||
      stableStringify(preview.snapshot.context) !== stableStringify(retainedSnapshot.context)
    ) {
      throw new RunEngineError(
        "MIGRATION_INVALID",
        `Actor ${actor.id} ${migration.fromVersion} is not observationally equivalent to ${migration.toVersion}`,
      );
    }
  }

  private openMigrationStateVisit(
    actor: ActorMutationRow,
    snapshot: JsonMachineSnapshot,
    eventId: EventId,
    now: string,
  ): StateVisitId {
    this.db.prepare(
      "UPDATE state_visits SET exited_event_id = ? WHERE id = ? AND exited_event_id IS NULL",
    ).run(eventId, actor.current_visit_id);
    const visitId = this.ids.next<StateVisitId>("visit");
    const visitNumber = (
      this.db
        .prepare("SELECT COALESCE(MAX(visit_number), 0) + 1 AS value FROM state_visits WHERE actor_id = ?")
        .get(actor.id) as { readonly value: number }
    ).value;
    this.db.prepare(
      `INSERT INTO state_visits(
        id, actor_id, state_key, visit_number, entered_event_id, created_at
      ) VALUES (?, ?, ?, ?, ?, ?)`,
    ).run(visitId, actor.id, stateKey(snapshot.value), visitNumber, eventId, now);
    return visitId;
  }

  private transformMigrationSnapshot(
    actor: ActorMutationRow,
    snapshot: JsonMachineSnapshot,
  ): JsonMachineSnapshot {
    const state = stateKey(snapshot.value);
    const targetState =
      (actor.machine_name === "article" || actor.machine_name === "editorial") && state === "settled"
        ? "accepted_pending_durable"
        : (actor.machine_name === "cover_art" || actor.machine_name === "interior_art") &&
            state === "registered"
          ? "accepted_pending_durable"
          : actor.machine_name === "edition" && state === "awaiting_release_approval"
            ? "migration_durable_backfill"
            : state;
    if (targetState === state) return snapshot;
    if (actor.machine_name !== "edition" || targetState !== "migration_durable_backfill") {
      return { ...snapshot, value: targetState };
    }
    const children = jsonObject(snapshot.context.children, `edition ${actor.id} migration children`);
    const resetChildren = Object.fromEntries(Object.entries(children).map(([key, value]) => {
      if (!(key === "editorial" || key.startsWith("article:") || key.startsWith("art:"))) {
        return [key, value];
      }
      const child = jsonObject(value, `edition ${actor.id} migration child ${key}`);
      return [key, { ...child, status: "active", outputs: [], result: {} }];
    }));
    const {
      compositionBoundRevisionId: _oldCompositionRevision,
      compositionDurableRevisionArtifact: _oldCompositionArtifact,
      ...retainedContext
    } = snapshot.context;
    return {
      ...snapshot,
      value: targetState,
      context: {
        ...retainedContext,
        children: resetChildren,
        migrationBackfill: true,
      },
    };
  }

  private requireOffer(offerId: WorkOfferId): OfferClaimRow {
    const offer = this.db
      .prepare(
        `SELECT o.*,
           r.machine_name AS run_machine_name,
           r.machine_version AS run_machine_version,
           r.status AS run_status,
           r.sealed_at AS run_sealed_at,
           a.machine_name AS actor_machine_name,
           a.machine_version AS actor_machine_version
         FROM work_offers o
         JOIN runs r ON r.id = o.run_id
         JOIN actors a ON a.id = o.actor_id
         WHERE o.id = ?`,
      )
      .get(offerId) as OfferClaimRow | undefined;
    if (offer === undefined) {
      throw new RunEngineError("OFFER_NOT_FOUND", `Work offer ${offerId} does not exist`);
    }
    return offer;
  }

  private requireAttempt(attemptId: AttemptId): AttemptClaimRow {
    const attempt = this.db.prepare("SELECT * FROM attempts WHERE id = ?").get(attemptId) as
      | AttemptClaimRow
      | undefined;
    if (attempt === undefined) {
      throw new RunEngineError("ATTEMPT_NOT_FOUND", `Attempt ${attemptId} does not exist`);
    }
    return attempt;
  }

  private assertOfferMachineCurrent(offer: OfferClaimRow): void {
    this.assertMachineCurrent(offer.run_machine_name, offer.run_machine_version);
    this.assertMachineCurrent(offer.actor_machine_name, offer.actor_machine_version);
  }

  private assertMachineCurrent(machine: MachineKind, storedVersion: string): void {
    const current = currentMachineVersion(machine);
    if (current !== storedVersion) {
      if (SNAPSHOT_MIGRATION_ALLOWLIST[machine]?.[storedVersion] === current) {
        throw new RunEngineError(
          "MIGRATION_REQUIRED",
          `Stored ${machine} machine version ${storedVersion} must migrate to ${current} before authority can advance`,
        );
      }
      throw new MachineVersionError(
        `Stored ${machine} machine version ${storedVersion} cannot run as ${current}`,
      );
    }
  }

  private offerCapabilities(offerId: WorkOfferId): readonly WorkerCapability[] {
    return (
      this.db
        .prepare(
          "SELECT capability FROM work_offer_capabilities WHERE offer_id = ? ORDER BY capability",
        )
        .all(offerId) as readonly { readonly capability: WorkerCapability }[]
    ).map((row) => row.capability);
  }

  private offerProvenance(
    offerId: WorkOfferId,
  ): readonly { readonly artifactId: ArtifactId; readonly relation: string }[] {
    const offer = this.requireOffer(offerId);
    const rows = this.db
      .prepare("SELECT artifact_id FROM work_offer_inputs WHERE offer_id = ? ORDER BY ordinal")
      .all(offerId) as readonly { readonly artifact_id: ArtifactId }[];
    const parents = [
      { artifactId: offer.task_artifact_id, relation: "task" },
      ...rows.map((row) => ({ artifactId: row.artifact_id, relation: "input" })),
    ];
    return deduplicateParents(parents);
  }

  /**
   * Human role schemas describe the shape of an answer, but the active
   * machine-owned request is the authority for its allowed choices. Keeping
   * this check beside result-contract validation prevents a valid choice for a
   * different visit from advancing the current offer.
   */
  private assertExactHumanChoice(offer: OfferClaimRow, result: JsonObject): void {
    if (!this.offerCapabilities(offer.id).includes("human")) {
      return;
    }
    const task = this.db.prepare("SELECT * FROM artifacts WHERE id = ?").get(
      offer.task_artifact_id,
    ) as StoredArtifactRow | undefined;
    if (task === undefined || task.kind !== "human_decision_request") {
      throw new RunEngineError(
        "HUMAN_DECISION_REQUEST_MISSING",
        `Human offer ${offer.id} does not name an immutable decision request`,
      );
    }
    let request: JsonObject;
    try {
      request = jsonObject(
        JSON.parse(this.readStoredArtifactBytes(task).toString("utf8")) as unknown,
        `human decision request ${task.id}`,
      );
    } catch (error) {
      throw new RunEngineError(
        "HUMAN_DECISION_REQUEST_INVALID",
        `Human offer ${offer.id} has an unreadable decision request`,
        { cause: error },
      );
    }
    const choices = request.choices;
    if (!Array.isArray(choices) || choices.length === 0 || choices.some((choice) => typeof choice !== "string")) {
      throw new RunEngineError(
        "HUMAN_DECISION_REQUEST_INVALID",
        `Human offer ${offer.id} has no exact choice list`,
      );
    }
    const submitted = typeof result.choice === "string"
      ? result.choice
      : typeof result.decision === "string"
        ? result.decision
        : undefined;
    if (submitted === undefined || !choices.includes(submitted)) {
      throw new RunEngineError(
        "HUMAN_DECISION_CHOICE_INVALID",
        `Human offer ${offer.id} does not permit choice ${submitted ?? "<missing>"}`,
      );
    }
  }

  private prepareAnswerArtifact(
    artifact: AnswerArtifact,
    claim: WorkClaim,
    offer: OfferClaimRow,
    provenance: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
    now: string,
    artifactOperationId: string,
  ): ArtifactRecord {
    const id = artifact.id ?? this.ids.next<ArtifactId>("art");
    if (this.db.prepare("SELECT 1 FROM artifacts WHERE id = ?").get(id) !== undefined) {
      throw new RunEngineError(
        "ARTIFACT_IMMUTABLE",
        `Artifact ${id} already exists and cannot be overwritten`,
      );
    }
    const parents = deduplicateParents([...(artifact.parents ?? []), ...provenance]);
    return {
      id,
      kind: artifact.kind,
      schemaVersion: artifact.schemaVersion,
      mediaType: artifact.mediaType,
      origin: artifact.origin ?? originForWorker(claim.worker),
      payload: this.prepareOwnedPayload(id, artifact.payload, artifactOperationId),
      parents,
      metadata: artifact.metadata ?? {},
      disposition: "accepted",
      producingRunId: offer.run_id,
      producingActorId: offer.actor_id,
      producingAttemptId: claim.attemptId,
      producingOfferId: claim.offerId,
      createdAt: now,
      ...(artifact.supersedes === undefined ? {} : { supersedes: artifact.supersedes }),
    };
  }

  private assertDurableCheckpointAnswer(
    offer: OfferClaimRow,
    answer: WorkAnswer,
  ): JsonObject {
    const task = this.requireArtifactRecord(offer.task_artifact_id);
    if (
      task.kind !== "durable_checkpoint_request" ||
      task.schema_version !== "durable-checkpoint-request/1"
    ) {
      throw new RunEngineError(
        "DURABLE_CHECKPOINT_REQUEST_MISSING",
        `Offer ${offer.id} has no immutable durable checkpoint request`,
      );
    }
    const request = jsonObject(
      JSON.parse(this.readStoredArtifactBytes(task).toString("utf8")) as unknown,
      `durable checkpoint request ${task.id}`,
    );
    const exactKeys = [
      "promotionId",
      "revisionId",
      "logicalItem",
      "expectedParentRevisionId",
    ] as const;
    for (const key of exactKeys) {
      if (!isDeepStrictEqual(answer.result[key], request[key])) {
        throw new RunEngineError(
          "DURABLE_INTEGRITY_CONFLICT",
          `Durable checkpoint answer for ${offer.id} does not match request ${key}`,
        );
      }
    }
    const evidence = answer.artifacts.find((artifact) =>
      artifact.kind === "durable_revision_evidence" &&
      artifact.mediaType === "application/json" &&
      artifact.payload.kind === "json"
    );
    if (evidence === undefined || evidence.payload.kind !== "json") {
      throw new RunEngineError(
        "DURABLE_INTEGRITY_CONFLICT",
        `Durable checkpoint answer for ${offer.id} has no JSON evidence`,
      );
    }
    const evidenceValue = jsonObject(evidence.payload.value, "durable checkpoint evidence");
    if (!isDeepStrictEqual(answer.result, evidenceValue)) {
      const withoutPath = { ...evidenceValue };
      delete withoutPath.revisionPath;
      if (!isDeepStrictEqual(answer.result, withoutPath)) {
        throw new RunEngineError(
          "DURABLE_INTEGRITY_CONFLICT",
          `Durable checkpoint evidence for ${offer.id} does not equal its answer`,
        );
      }
    }
    return request;
  }

  private assertRenderReconciliationAnswer(offer: OfferClaimRow, answer: WorkAnswer): void {
    const task = this.requireArtifactRecord(offer.task_artifact_id);
    const request = parseJson<JsonObject>(
      this.readStoredArtifactBytes(task).toString("utf8"),
      `render reconciliation task ${offer.task_artifact_id}`,
    );
    if (answer.result.choice !== "adopt") return;
    const exact = (key: string, expected: unknown): boolean =>
      isDeepStrictEqual(answer.result[key], expected);
    const required = [
      ["compositionRevisionArtifactId", request.subjectArtifactId],
      ["renderArtifactIds", request.legacyRenderArtifactIds],
      ["rendererVersion", request.rendererVersion],
      ["contentArtifactIds", request.contentArtifactIds],
      ["layoutArtifactIds", request.layoutArtifactIds],
      ["languages", request.languages],
    ] as const;
    if (required.some(([key, expected]) => !exact(key, expected))) {
      throw new RunEngineError(
        "RENDER_RECONCILIATION_MISMATCH",
        "Render adoption proof does not exactly match its immutable composition request",
      );
    }
    const digests = answer.result.outputDigests;
    if (digests === null || typeof digests !== "object" || Array.isArray(digests)) {
      throw new RunEngineError("RENDER_RECONCILIATION_MISMATCH", "Render adoption has no digest proof");
    }
    const digestRecord = digests as JsonObject;
    for (const artifactId of request.legacyRenderArtifactIds as readonly string[]) {
      const artifact = this.requireArtifactRecord(artifactId as ArtifactId);
      const metadata = parseJson<JsonObject>(artifact.metadata_json, `artifact ${artifact.id} metadata`);
      if (typeof metadata.sha256 !== "string" || digestRecord[artifactId] !== metadata.sha256) {
        throw new RunEngineError(
          "RENDER_RECONCILIATION_MISMATCH",
          `Render adoption digest does not bind ${artifactId}`,
        );
      }
    }
  }

  private assertCompositionBootstrapAnswer(offer: OfferClaimRow, answer: WorkAnswer): JsonObject {
    const task = this.requireArtifactRecord(offer.task_artifact_id);
    const request = parseJson<JsonObject>(
      this.readStoredArtifactBytes(task).toString("utf8"),
      `composition bootstrap task ${offer.task_artifact_id}`,
    );
    if (!isDeepStrictEqual(answer.result.bootstrapRevision, request.bootstrapRevision)) {
      throw new RunEngineError(
        "COMPOSITION_BOOTSTRAP_MISMATCH",
        "Bootstrap answer does not name the exact immutable bootstrap revision",
      );
    }
    if (answer.result.imageGenerationAllowed !== false) {
      throw new RunEngineError(
        "COMPOSITION_BOOTSTRAP_MISMATCH",
        "Bootstrap composition may not generate images",
      );
    }
    const evidence = answer.artifacts.find((artifact) => artifact.kind === "composition_bootstrap_evidence");
    if (evidence?.payload.kind !== "json" || !isDeepStrictEqual(evidence.payload.value, answer.result)) {
      throw new RunEngineError(
        "COMPOSITION_BOOTSTRAP_MISMATCH",
        "Bootstrap evidence must exactly equal its answer result",
      );
    }
    return request;
  }

  private prepareCompositionBootstrapBound(
    claim: WorkClaim,
    offer: OfferClaimRow,
    result: JsonObject,
    records: readonly ArtifactRecord[],
    now: string,
  ): ArtifactRecord {
    const evidence = records.find((record) => record.kind === "composition_bootstrap_evidence");
    if (evidence === undefined) {
      throw new RunEngineError("COMPOSITION_BOOTSTRAP_MISMATCH", "Bootstrap evidence was not prepared");
    }
    const artifactId = this.ids.next<ArtifactId>("art");
    return {
      id: artifactId,
      kind: "composition_revision_bound",
      schemaVersion: "composition-bootstrap-bound/1",
      mediaType: "application/json",
      origin: "machine",
      payload: this.store.prepare(artifactId, { kind: "json", value: result }),
      parents: [
        { artifactId: offer.task_artifact_id, relation: "bootstrap_task" },
        { artifactId: evidence.id, relation: "bootstrap_evidence" },
      ],
      metadata: { offerId: offer.id, attemptId: claim.attemptId },
      disposition: "accepted",
      producingRunId: offer.run_id,
      producingActorId: offer.actor_id,
      producingAttemptId: claim.attemptId,
      producingOfferId: offer.id,
      createdAt: now,
    };
  }

  private prepareDurableRevisionBound(
    claim: WorkClaim,
    offer: OfferClaimRow,
    request: JsonObject,
    result: JsonObject,
    outputs: readonly ArtifactRecord[],
    now: string,
    artifactOperationId: string,
  ): ArtifactRecord {
    const evidence = outputs.find((artifact) => artifact.kind === "durable_revision_evidence");
    if (evidence === undefined) {
      throw new RunEngineError("DURABLE_INTEGRITY_CONFLICT", "checkpoint evidence was not prepared");
    }
    const id = this.ids.next<ArtifactId>("art");
    return {
      id,
      kind: "durable_revision_bound",
      schemaVersion: "durable-revision-bound/1",
      mediaType: "application/json",
      origin: "machine",
      payload: this.prepareOwnedPayload(id, {
        kind: "json",
        value: {
          ...request,
          revisionRef: result.revisionRef,
          manifestDigest: result.manifestDigest,
          gitCommitOid: result.gitCommitOid,
          gitBlobOids: result.gitBlobOids,
          evidenceArtifactId: evidence.id,
        } as unknown as JsonObject,
      }, artifactOperationId),
      parents: deduplicateParents([
        { artifactId: offer.task_artifact_id, relation: "checkpoint_request" },
        { artifactId: evidence.id, relation: "checkpoint_evidence" },
        ...(request.acceptedArtifactIds as readonly ArtifactId[]).map((artifactId) => ({
          artifactId,
          relation: "accepted_output",
        })),
        ...(request.decisionArtifactIds as readonly ArtifactId[]).map((artifactId) => ({
          artifactId,
          relation: "accepted_decision",
        })),
        ...(request.inputArtifactIds as readonly ArtifactId[]).map((artifactId) => ({
          artifactId,
          relation: "checkpoint_input",
        })),
      ]),
      metadata: {
        promotionId: request.promotionId ?? null,
        revisionId: request.revisionId ?? null,
      },
      disposition: "accepted",
      producingRunId: offer.run_id,
      producingActorId: offer.actor_id,
      producingAttemptId: claim.attemptId,
      producingOfferId: claim.offerId,
      createdAt: now,
    };
  }

  private expireAttempt(offer: OfferClaimRow, attempt: AttemptClaimRow, now: string): void {
    this.db.prepare(
      `UPDATE attempts SET status = 'timed_out', finished_at = ?,
         failure_classification = 'timeout', failure_message = 'Claim lease expired'
       WHERE id = ? AND status = 'active'`,
    ).run(now, attempt.id);
    this.db.prepare(
      `UPDATE work_offers SET status = 'offered', active_attempt_id = NULL,
         updated_at = ? WHERE id = ? AND active_attempt_id = ?`,
    ).run(now, offer.id, attempt.id);
  }

  private now(): string {
    return this.clock.now().toISOString();
  }

  private nowMs(): number {
    return this.clock.now().getTime();
  }

  private assertOpen(): void {
    if (this.closed) {
      throw new RunEngineError("ENGINE_CLOSED", "RunEngine is closed");
    }
  }

  private requireSettledArticleCandidate(runId: RunId): {
    readonly runId: RunId;
    readonly actorId: ActorId;
    readonly manuscriptArtifactId: ArtifactId;
  } {
    const run = this.requireRun(runId);
    this.assertMachineCurrent(run.machine_name, run.machine_version);
    if (run.kind !== "article" || run.status !== "complete") {
      throw new RunEngineError(
        "ARTICLE_COMPARISON_INVALID",
        `Compared run ${runId} is not a complete article run`,
      );
    }
    const actor = this.db
      .prepare(
        `SELECT * FROM actors
         WHERE run_id = ? AND parent_actor_id IS NULL`,
      )
      .get(runId) as ActorMutationRow | undefined;
    if (
      actor === undefined ||
      (actor.current_state !== "durable_bound" && actor.current_state !== "settled") ||
      (actor.status !== "accepting" && actor.status !== "done")
    ) {
      throw new RunEngineError(
        "ARTICLE_COMPARISON_INVALID",
        `Compared run ${runId} did not settle an article manuscript`,
      );
    }
    const output = this.db
      .prepare(
        `SELECT artifact_id FROM run_outputs
         WHERE run_id = ? AND output_name = ? AND ordinal = 0`,
      )
      .get(runId, actor.logical_key) as
      | { readonly artifact_id: ArtifactId }
      | undefined;
    if (output === undefined) {
      throw new RunEngineError(
        "ARTICLE_COMPARISON_INVALID",
        `Compared run ${runId} has no final manuscript artifact`,
      );
    }
    requireArtifactExists(this.db, output.artifact_id);
    return {
      runId,
      actorId: actor.id,
      manuscriptArtifactId: output.artifact_id,
    };
  }

  private loadArticlePromotion(runId: RunId): ArticlePromotionView | undefined {
    const row = this.db
      .prepare("SELECT * FROM article_promotions WHERE run_id = ?")
      .get(runId) as
      | {
          readonly id: string;
          readonly run_id: RunId;
          readonly selected_artifact_id: ArtifactId;
          readonly policy_artifact_id: ArtifactId;
          readonly reviewer: string;
          readonly rationale: string;
          readonly compared_run_ids_json: string;
          readonly created_at: string;
        }
      | undefined;
    if (row === undefined) {
      return undefined;
    }
    return {
      id: row.id,
      runId: row.run_id,
      selectedArtifactId: row.selected_artifact_id,
      policyArtifactId: row.policy_artifact_id,
      reviewer: row.reviewer,
      rationale: row.rationale,
      comparedRunIds: parseJson<readonly RunId[]>(
        row.compared_run_ids_json,
        `article promotion ${row.id} compared runs`,
      ),
      createdAt: row.created_at,
    };
  }

  private requireRun(runId: RunId): RunMutationRow {
    const run = this.db.prepare("SELECT * FROM runs WHERE id = ?").get(runId) as
      | RunMutationRow
      | undefined;
    if (run === undefined) {
      throw new RunEngineError("RUN_NOT_FOUND", `Run ${runId} does not exist`);
    }
    return run;
  }

  private requireArtifactRecord(artifactId: ArtifactId): StoredArtifactRow {
    const artifact = this.db.prepare("SELECT * FROM artifacts WHERE id = ?").get(artifactId) as
      | StoredArtifactRow
      | undefined;
    if (artifact === undefined) {
      throw new RunEngineError("ARTIFACT_NOT_FOUND", `Artifact ${artifactId} does not exist`);
    }
    return artifact;
  }
}

export function createRunEngine(options: RunEngineOptions): SqliteRunEngine {
  return new SqliteRunEngine(options);
}

type SnapshotEventInput = {
  readonly eventId: EventId;
  readonly runId: RunId;
  readonly sequence: number;
  readonly actorId: ActorId;
  readonly type: string;
  readonly payload: JsonObject;
  readonly previousSnapshotNumber: number | null;
  readonly nextSnapshotNumber: number;
  readonly previousState: string | null;
  readonly snapshot: JsonMachineSnapshot;
  readonly machineVersion: string;
  readonly causationEventId: EventId | null;
  readonly correlationId: string | null;
  readonly inboxId: InboxId | null;
  readonly now: string;
};

function insertSnapshotEvent(db: Database.Database, input: SnapshotEventInput): void {
  const nextState = stateKey(input.snapshot.value);
  db.prepare(
    `INSERT INTO events(
      id, run_id, sequence, actor_id, inbox_id, type, payload_json,
      previous_snapshot_number, next_snapshot_number, previous_state,
      next_state, causation_event_id, correlation_id, recorded_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    input.eventId,
    input.runId,
    input.sequence,
    input.actorId,
    input.inboxId,
    input.type,
    stringifyJson(input.payload),
    input.previousSnapshotNumber,
    input.nextSnapshotNumber,
    input.previousState,
    nextState,
    input.causationEventId,
    input.correlationId,
    input.now,
  );
  db.prepare(
    `INSERT INTO actor_snapshots(
      actor_id, snapshot_number, event_id, machine_version, snapshot_json,
      state_value_json, context_json, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    input.actorId,
    input.nextSnapshotNumber,
    input.eventId,
    input.machineVersion,
    stringifyJson(input.snapshot as unknown as JsonObject),
    stringifyJson(input.snapshot.value),
    stringifyJson(input.snapshot.context),
    input.now,
  );
}

type EnqueueInput = {
  readonly id: InboxId;
  readonly runId: RunId;
  readonly actorId: ActorId;
  readonly type: string;
  readonly payload: JsonObject;
  readonly idempotencyKey: string;
  readonly causationEventId: EventId | null;
  readonly correlationId: string | null;
  readonly priority?: number;
  readonly availableAtMs: number;
  readonly now: string;
};

function enqueueInbox(db: Database.Database, input: EnqueueInput): void {
  db.prepare(
    `INSERT OR IGNORE INTO inbox(
      id, run_id, actor_id, type, payload_json, idempotency_key,
      causation_event_id, correlation_id, status, priority, available_at_ms, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)`,
  ).run(
    input.id,
    input.runId,
    input.actorId,
    input.type,
    stringifyJson(input.payload),
    input.idempotencyKey,
    input.causationEventId,
    input.correlationId,
    input.priority ?? 0,
    input.availableAtMs,
    input.now,
  );
}

function rootMachineInput(spec: RunSpec, actorId: ActorId, logicalKey: string): JsonObject {
  const machineSpec = spec.kind === "article" ? spec.article : spec.edition;
  return {
    actorId,
    logicalKey,
    spec: machineSpec as unknown as JsonObject,
  };
}

function sourceArtifactReferences(source: SourceRunSpec): readonly ArtifactId[] {
  return [...new Set([
    source.leadArtifact,
    source.captureProfileArtifact,
    ...(source.captureInputArtifacts ?? []),
    source.rawBundleArtifact,
    ...(source.rawEvidenceArtifacts ?? []),
    source.extractionArtifact,
    source.metadataArtifact,
    source.approvalArtifact,
  ].filter((value): value is ArtifactId => value !== undefined))];
}

function materializeSourceSpec(
  source: SourceRunSpec,
  context: JsonObject | undefined,
): SourceRunSpec {
  if (context === undefined) {
    return source;
  }
  const rawEvidence = context.rawEvidenceArtifacts;
  return {
    ...source,
    ...(typeof context.rawBundleArtifact === "string"
      ? { rawBundleArtifact: context.rawBundleArtifact as ArtifactId }
      : {}),
    ...(Array.isArray(rawEvidence) && rawEvidence.every((value) => typeof value === "string")
      ? { rawEvidenceArtifacts: rawEvidence as unknown as readonly ArtifactId[] }
      : {}),
    ...(typeof context.extractionArtifact === "string"
      ? { extractionArtifact: context.extractionArtifact as ArtifactId }
      : {}),
    ...(typeof context.metadataArtifact === "string"
      ? { metadataArtifact: context.metadataArtifact as ArtifactId }
      : {}),
    ...(typeof context.approvalArtifact === "string"
      ? { approvalArtifact: context.approvalArtifact as ArtifactId }
      : {}),
  };
}

function collectArtifactReferences(
  spec: RunSpec,
  known: ReadonlySet<string>,
): readonly { readonly path: string; readonly artifactId: ArtifactId }[] {
  const references: { path: string; artifactId: ArtifactId }[] = [];
  const root = spec as unknown as JsonObject;
  const walk = (value: JsonValue, path: readonly string[]): void => {
    if (typeof value === "string" && known.has(value)) {
      references.push({ path: `/${path.join("/")}`, artifactId: value as ArtifactId });
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((child, index) => walk(child, [...path, String(index)]));
      return;
    }
    if (value !== null && typeof value === "object") {
      for (const [key, child] of Object.entries(value)) {
        if (path.length === 0 && key === "artifacts") {
          continue;
        }
        walk(child, [...path, key]);
      }
    }
  };
  walk(root, []);
  return references;
}

function requireArtifactExists(db: Database.Database, artifactId: ArtifactId): void {
  if (db.prepare("SELECT 1 FROM artifacts WHERE id = ?").get(artifactId) === undefined) {
    throw new RunEngineError(
      "ARTIFACT_NOT_FOUND",
      `Run input artifact ${artifactId} does not exist`,
    );
  }
}

function requiredStoredPath(row: StoredArtifactRow): string {
  if (row.relative_path === null) {
    throw new RunEngineError(
      "ARTIFACT_STORAGE_CORRUPT",
      `File artifact ${row.id} has no relative path`,
    );
  }
  return row.relative_path;
}

function sameOrderedValues(
  left: readonly string[],
  right: readonly string[],
): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function modelDependency(serializedActorInput: string, role: string): JsonValue {
  const input = parseJson<JsonObject>(serializedActorInput, "actor input for reuse");
  const spec = input.spec;
  if (spec === null || Array.isArray(spec) || typeof spec !== "object") {
    return null;
  }
  const modelPolicy = (spec as JsonObject).modelPolicy;
  if (
    modelPolicy === null ||
    Array.isArray(modelPolicy) ||
    typeof modelPolicy !== "object"
  ) {
    return null;
  }
  const policy = modelPolicy as JsonObject;
  const roles = policy.roles;
  if (roles !== null && !Array.isArray(roles) && typeof roles === "object") {
    const selected = (roles as JsonObject)[role];
    if (selected !== undefined) {
      return selected;
    }
  }
  return policy.default ?? null;
}

function flattenEffectArtifacts(effects: readonly PreparedEffect[]): readonly ArtifactRecord[] {
  return effects.flatMap((prepared) => prepared.artifacts);
}

function preparedEffectPayload(prepared: PreparedEffect): PreparedEffectPayload {
  return {
    artifactIds: prepared.artifacts.map((artifact) => artifact.id),
    ...(prepared.spawned === undefined
      ? {}
      : {
          spawned: {
            actorId: prepared.spawned.actorId,
            machine: prepared.spawned.machine,
            logicalKey: prepared.spawned.logicalKey,
            parentActorId: prepared.spawned.parentActorId,
            input: prepared.spawned.input,
            snapshot: prepared.spawned.initial.snapshot,
          },
        }),
  };
}

function parsePreparedEffectPayload(serialized: string, outboxId: string): PreparedEffectPayload {
  const value = parseJson<JsonObject>(serialized, `outbox ${outboxId} payload`);
  const artifactIds = value.artifactIds;
  if (!Array.isArray(artifactIds) || artifactIds.some((candidate) => typeof candidate !== "string")) {
    throw new RunEngineError(
      "OUTBOX_PAYLOAD_INVALID",
      `Outbox effect ${outboxId} has invalid artifact identities`,
    );
  }
  if (value.spawned === undefined) {
    return { artifactIds: artifactIds as readonly ArtifactId[] };
  }
  const spawned = jsonObject(value.spawned, `outbox ${outboxId} spawned actor`);
  if (
    typeof spawned.actorId !== "string" ||
    typeof spawned.machine !== "string" ||
    spawned.machine === "edition" ||
    typeof spawned.logicalKey !== "string" ||
    typeof spawned.parentActorId !== "string"
  ) {
    throw new RunEngineError(
      "OUTBOX_PAYLOAD_INVALID",
      `Outbox effect ${outboxId} has an invalid spawned actor identity`,
    );
  }
  return {
    artifactIds: artifactIds as readonly ArtifactId[],
    spawned: {
      actorId: spawned.actorId as ActorId,
      machine: spawned.machine as Exclude<MachineKind, "edition">,
      logicalKey: spawned.logicalKey,
      parentActorId: spawned.parentActorId as ActorId,
      input: jsonObject(spawned.input, `outbox ${outboxId} spawned input`),
      snapshot: jsonObject(
        spawned.snapshot,
        `outbox ${outboxId} spawned snapshot`,
      ) as JsonMachineSnapshot,
    },
  };
}

function outboxRetryDelay(attempt: number): number {
  return Math.min(
    OUTBOX_RETRY_MAX_MS,
    OUTBOX_RETRY_BASE_MS * 2 ** Math.max(0, Math.min(attempt - 1, 20)),
  );
}

function operationStartKey(callerKey: string | undefined, generatedKey: string): string {
  if (callerKey !== undefined) {
    const normalized = callerKey.trim();
    if (normalized.length === 0 || normalized.length > 500) {
      throw new RunEngineError(
        "START_IDEMPOTENCY_KEY_INVALID",
        "Run start idempotency keys must contain between 1 and 500 characters",
      );
    }
    return `caller:${normalized}`;
  }
  return `operation:${generatedKey}`;
}

function assertSameStartRequest(
  idempotencyKey: string,
  requestedSpec: string,
  storedSpec: string,
): void {
  if (requestedSpec !== storedSpec) {
    throw new RunEngineError(
      "START_IDEMPOTENCY_CONFLICT",
      `Run start key ${idempotencyKey} was already used for a different immutable spec`,
    );
  }
}

function assertSameRunOperation(
  db: Database.Database,
  idempotencyKey: string,
  storedRunId: RunId,
  requestedParentRunId: RunId | undefined,
  requestedChanges: readonly RunInputChange[],
): void {
  const storedRun = db
    .prepare("SELECT parent_run_id FROM runs WHERE id = ?")
    .get(storedRunId) as { readonly parent_run_id: RunId | null } | undefined;
  if (
    storedRun === undefined ||
    storedRun.parent_run_id !== (requestedParentRunId ?? null)
  ) {
    throw new RunEngineError(
      "START_IDEMPOTENCY_CONFLICT",
      `Run start key ${idempotencyKey} was already used for a different start or fork parent`,
    );
  }
  const storedChanges = (
    db.prepare(
      `SELECT kind, path, old_artifact_id, new_artifact_id, value_json
       FROM fork_changes WHERE run_id = ? ORDER BY ordinal`,
    ).all(storedRunId) as readonly {
      readonly kind: "replace_artifact" | "replace_spec";
      readonly path: string | null;
      readonly old_artifact_id: ArtifactId | null;
      readonly new_artifact_id: ArtifactId | null;
      readonly value_json: string | null;
    }[]
  ).map((change): JsonValue =>
    change.kind === "replace_artifact"
      ? {
          kind: change.kind,
          from: change.old_artifact_id,
          to: change.new_artifact_id,
        }
      : {
          kind: change.kind,
          path: change.path,
          value: change.value_json === null
            ? null
            : parseJson<JsonValue>(change.value_json, "stored fork change"),
        }
  );
  const requested = requestedChanges.map((change): JsonValue =>
    change.kind === "replace_artifact"
      ? { kind: change.kind, from: change.from, to: change.to.id }
      : { kind: change.kind, path: change.path, value: change.value }
  );
  if (
    stableStringify(storedChanges as JsonValue) !==
      stableStringify(requested as JsonValue)
  ) {
    throw new RunEngineError(
      "START_IDEMPOTENCY_CONFLICT",
      `Run start key ${idempotencyKey} was already used for different explicit changes`,
    );
  }
}

function isTerminalStatus(status: string): boolean {
  return status === "complete" || status === "failed";
}

function ensureMachineVersion(
  db: Database.Database,
  machine: MachineKind,
  semanticVersion: string,
  now: string,
): void {
  db.prepare(
    `INSERT OR IGNORE INTO machine_versions(
      id, machine_name, semantic_version, xstate_version,
      contract_version, created_at
    ) VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(
    `${machine}@${semanticVersion}`,
    machine,
    semanticVersion,
    XSTATE_VERSION,
    MACHINE_CONTRACT_VERSION,
    now,
  );
}

function machineBundleFor(
  machine: MachineKind,
  version: string,
): MachineBundleVersion {
  if (version === currentMachineVersion(machine)) {
    return MACHINE_BUNDLE_V2;
  }
  if (SNAPSHOT_MIGRATION_ALLOWLIST[machine]?.[version] !== undefined) {
    return MACHINE_BUNDLE_V1;
  }
  throw new RunEngineError(
    "MIGRATION_UNSUPPORTED",
    `Machine ${machine} version ${version} is outside the adjacent v1 to v2 migration registry`,
  );
}

function exposureClass(
  capabilities: readonly WorkerCapability[],
): "source_aware" | "source_blind" | undefined {
  const sourceAware = capabilities.includes("source_access");
  const sourceBlind = capabilities.includes("source_blind");
  if (sourceAware && sourceBlind) {
    throw new RunEngineError(
      "INVALID_EXPOSURE_POLICY",
      "A work offer cannot be both source-aware and source-blind",
    );
  }
  if (sourceAware) {
    return "source_aware";
  }
  if (sourceBlind) {
    return "source_blind";
  }
  return undefined;
}

function claimMatches(attempt: AttemptClaimRow, claim: WorkClaim): boolean {
  return (
    attempt.id === claim.attemptId &&
    attempt.offer_id === claim.offerId &&
    attempt.fence === claim.attemptFence &&
    attempt.worker_principal_id === claim.worker.principalId &&
    attempt.worker_authority === claim.worker.authority &&
    attempt.worker_capabilities_json === stringifyJson([...claim.worker.capabilities].sort()) &&
    attempt.worker_display_name === (claim.worker.displayName ?? null)
  );
}

function migrationFenceFromRow(row: {
  readonly run_id: RunId;
  readonly fence_id: string;
  readonly expected_head_sequence: number;
  readonly expected_head_event_id: EventId;
  readonly idempotency_key: string;
  readonly acquired_at: string;
}): RunMigrationFence {
  return {
    schemaVersion: "run-migration-fence/1",
    runId: row.run_id,
    fenceId: row.fence_id,
    expectedHeadSequence: row.expected_head_sequence,
    expectedHeadEventId: row.expected_head_event_id,
    idempotencyKey: row.idempotency_key,
    acquiredAt: row.acquired_at,
  };
}

function isActiveClaim(
  offer: OfferClaimRow,
  attempt: AttemptClaimRow,
  nowMs: number,
): boolean {
  return (
    attempt.status === "active" &&
    attempt.lease_expires_at_ms > nowMs &&
    offer.status === "claimed" &&
    !isTerminalStatus(offer.run_status) &&
    offer.active_attempt_id === attempt.id &&
    offer.claim_fence === attempt.fence
  );
}

function originForWorker(worker: WorkerIdentity): ArtifactOrigin {
  switch (worker.authority) {
    case "human":
      return "human";
    case "model":
      return "model";
    case "machine":
      return "machine";
    case "tool":
      return "subprocess";
  }
}

function deduplicateParents(
  parents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
): readonly { readonly artifactId: ArtifactId; readonly relation: string }[] {
  const seen = new Set<string>();
  return parents.filter((parent) => {
    const key = `${parent.artifactId}\u0000${parent.relation}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
