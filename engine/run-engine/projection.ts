import type Database from "better-sqlite3";

import type {
  ActorId,
  ActorView,
  ArtifactId,
  AttemptId,
  AttemptView,
  DecisionId,
  DecisionView,
  EventId,
  EventView,
  JsonObject,
  IterationId,
  IterationView,
  RunId,
  RunOutcome,
  RunStatus,
  RunView,
  SourceRunSpec,
  SourceSubmissionView,
  StateVisitId,
  WorkerCapability,
  WorkOfferId,
  WorkOfferStatus,
  WorkOfferView,
  WorkRole,
} from "../contracts/index.ts";
import { loadArtifactViews } from "./artifact-repository.ts";
import { parseJson } from "./serialization.ts";
import { RunEngineError } from "./types.ts";

type RunRow = {
  readonly id: RunId;
  readonly kind: "article" | "edition";
  readonly status: RunStatus;
  readonly machine_version: string;
  readonly parent_run_id: RunId | null;
  readonly head_sequence: number;
  readonly created_at: string;
  readonly updated_at: string;
};

type ActorRow = {
  readonly id: ActorId;
  readonly parent_actor_id: ActorId | null;
  readonly logical_key: string;
  readonly machine_name: string;
  readonly machine_version: string;
  readonly status: ActorView["status"];
  readonly current_state: string;
  readonly current_context_json: string;
  readonly current_snapshot_number: number;
  readonly input_json: string;
};

type OfferRow = {
  readonly id: WorkOfferId;
  readonly run_id: RunId;
  readonly actor_id: ActorId;
  readonly actor_key: string;
  readonly state: string;
  readonly state_visit_id: StateVisitId;
  readonly role: WorkRole;
  readonly slot: string;
  readonly subject_artifact_id: ArtifactId | null;
  readonly iteration_id: string | null;
  readonly revision_id: string | null;
  readonly task_artifact_id: ArtifactId;
  readonly contract_version: string;
  readonly status: WorkOfferStatus;
  readonly active_attempt_id: AttemptId | null;
  readonly created_at: string;
  readonly reused_from_run_id: RunId | null;
  readonly reused_from_offer_id: WorkOfferId | null;
  readonly reused_answer_artifact_id: ArtifactId | null;
};

type AttemptRow = {
  readonly id: AttemptId;
  readonly offer_id: WorkOfferId;
  readonly attempt_number: number;
  readonly fence: number;
  readonly worker_principal_id: string;
  readonly worker_authority: "human" | "machine" | "model" | "tool";
  readonly worker_capabilities_json: string;
  readonly worker_display_name: string | null;
  readonly status: AttemptView["status"];
  readonly claimed_at: string;
  readonly lease_expires_at_ms: number;
  readonly finished_at: string | null;
};

type EventRow = {
  readonly id: EventId;
  readonly sequence: number;
  readonly actor_id: ActorId;
  readonly type: string;
  readonly payload_json: string;
  readonly previous_state: string | null;
  readonly next_state: string;
  readonly causation_event_id: EventId | null;
  readonly recorded_at: string;
};

type DecisionRow = {
  readonly id: DecisionId;
  readonly actor_id: ActorId;
  readonly offer_id: WorkOfferId | null;
  readonly subject_artifact_id: ArtifactId | null;
  readonly principal_id: string;
  readonly choice: string;
  readonly authority: string;
  readonly artifact_id: ArtifactId | null;
  readonly details_json: string;
  readonly created_at: string;
};

type IterationRow = {
  readonly id: IterationId;
  readonly actor_id: ActorId;
  readonly ordinal: number;
  readonly parent_manuscript_artifact_id: ArtifactId | null;
  readonly opened_event_id: EventId;
  readonly closed_event_id: EventId | null;
  readonly decision_id: DecisionId | null;
};

type SourceSubmissionRow = {
  readonly source_id: string;
  readonly source_spec_json: string;
  readonly submitted_at: string;
};

export function inspectRun(db: Database.Database, runId: RunId): RunView {
  return db.transaction(() => {
    const run = db.prepare("SELECT * FROM runs WHERE id = ?").get(runId) as RunRow | undefined;
    if (run === undefined) {
      throw new RunEngineError("RUN_NOT_FOUND", `Run ${runId} does not exist`);
    }

    const actors = (db
      .prepare("SELECT * FROM actors WHERE run_id = ? ORDER BY created_at, id")
      .all(runId) as readonly ActorRow[]).map((row): ActorView => {
      const outputRows = db
        .prepare(
          `SELECT artifact_id AS id FROM run_outputs
           WHERE run_id = ? AND output_name = ? ORDER BY ordinal`,
        )
        .all(runId, row.logical_key) as readonly { readonly id: ArtifactId }[];
      return {
        id: row.id,
        logicalKey: row.logical_key,
        machine: row.machine_name,
        machineVersion: row.machine_version,
        state: row.current_state,
        status: row.status,
        snapshotNumber: row.current_snapshot_number,
        outputs: outputRows.map((candidate) => candidate.id),
        input: parseJson<JsonObject>(row.input_json, `actor ${row.id} input`),
        context: parseJson<JsonObject>(row.current_context_json, `actor ${row.id} context`),
        ...(row.parent_actor_id === null ? {} : { parentActorId: row.parent_actor_id }),
      };
    });

    const offers = loadOfferViews(db, runId);
    const attempts = (db
      .prepare(
        `SELECT a.* FROM attempts a
         JOIN work_offers o ON o.id = a.offer_id
         WHERE o.run_id = ? ORDER BY a.claimed_at, a.id`,
      )
      .all(runId) as readonly AttemptRow[]).map((row): AttemptView => ({
      id: row.id,
      offerId: row.offer_id,
      attemptNumber: row.attempt_number,
      fence: row.fence,
      worker: {
        principalId: row.worker_principal_id,
        authority: row.worker_authority,
        capabilities: parseJson<readonly WorkerCapability[]>(
          row.worker_capabilities_json,
          `attempt ${row.id} capabilities`,
        ),
        ...(row.worker_display_name === null ? {} : { displayName: row.worker_display_name }),
      },
      status: row.status,
      claimedAt: row.claimed_at,
      leaseExpiresAt: new Date(row.lease_expires_at_ms).toISOString(),
      ...(row.finished_at === null ? {} : { finishedAt: row.finished_at }),
    }));

    const events = (db
      .prepare("SELECT * FROM events WHERE run_id = ? ORDER BY sequence")
      .all(runId) as readonly EventRow[]).map((row): EventView => ({
      id: row.id,
      sequence: row.sequence,
      actorId: row.actor_id,
      type: row.type,
      payload: parseJson<JsonObject>(row.payload_json, `event ${row.id} payload`),
      nextState: row.next_state,
      recordedAt: row.recorded_at,
      ...(row.previous_state === null ? {} : { previousState: row.previous_state }),
      ...(row.causation_event_id === null
        ? {}
        : { causationEventId: row.causation_event_id }),
    }));

    const decisions = (db
      .prepare("SELECT * FROM decisions WHERE run_id = ? ORDER BY created_at, id")
      .all(runId) as readonly DecisionRow[]).map((row): DecisionView => ({
      id: row.id,
      actorId: row.actor_id,
      principalId: row.principal_id,
      choice: row.choice,
      authority: row.authority,
      details: parseJson<JsonObject>(row.details_json, `decision ${row.id} details`),
      createdAt: row.created_at,
      ...(row.offer_id === null ? {} : { offerId: row.offer_id }),
      ...(row.subject_artifact_id === null
        ? {}
        : { subjectArtifactId: row.subject_artifact_id }),
      ...(row.artifact_id === null ? {} : { artifactId: row.artifact_id }),
    }));

    const iterations = (db
      .prepare(
        `SELECT i.* FROM iterations i
         JOIN actors a ON a.id = i.actor_id
         WHERE a.run_id = ? ORDER BY a.created_at, a.id, i.ordinal`,
      )
      .all(runId) as readonly IterationRow[]).map((row): IterationView => ({
      id: row.id,
      actorId: row.actor_id,
      ordinal: row.ordinal,
      openedEventId: row.opened_event_id,
      ...(row.parent_manuscript_artifact_id === null
        ? {}
        : { parentManuscriptArtifactId: row.parent_manuscript_artifact_id }),
      ...(row.closed_event_id === null ? {} : { closedEventId: row.closed_event_id }),
      ...(row.decision_id === null ? {} : { decisionId: row.decision_id }),
    }));

    const sourceSubmissions = (db
      .prepare(
        `SELECT source_id, source_spec_json, submitted_at
         FROM edition_source_submissions
         WHERE run_id = ? ORDER BY submitted_at, source_id`,
      )
      .all(runId) as readonly SourceSubmissionRow[]).map(
      (row): SourceSubmissionView => ({
        sourceId: row.source_id,
        source: parseJson<SourceRunSpec>(
          row.source_spec_json,
          `dynamic source ${row.source_id}`,
        ),
        submittedAt: row.submitted_at,
      }),
    );

    return {
      id: run.id,
      kind: run.kind,
      status: run.status,
      machineVersion: run.machine_version,
      headSequence: run.head_sequence,
      actors,
      iterations,
      sourceSubmissions,
      offers,
      attempts,
      artifacts: loadArtifactViews(db, runId),
      events,
      decisions,
      createdAt: run.created_at,
      updatedAt: run.updated_at,
      ...(run.parent_run_id === null ? {} : { parentRunId: run.parent_run_id }),
    };
  }).deferred();
}

export function loadOfferViews(
  db: Database.Database,
  runId: RunId,
): readonly WorkOfferView[] {
  const rows = db
    .prepare(
      `SELECT o.*, a.logical_key AS actor_key, sv.state_key AS state,
         reuse.ancestor_run_id AS reused_from_run_id,
         reuse.ancestor_offer_id AS reused_from_offer_id,
         reuse.answer_artifact_id AS reused_answer_artifact_id
       FROM work_offers o
       JOIN actors a ON a.id = o.actor_id
       JOIN state_visits sv ON sv.id = o.state_visit_id
       LEFT JOIN work_reuses reuse ON reuse.offer_id = o.id
       WHERE o.run_id = ? ORDER BY o.created_at, o.id`,
    )
    .all(runId) as readonly OfferRow[];
  const inputStatement = db.prepare(
    "SELECT artifact_id FROM work_offer_inputs WHERE offer_id = ? ORDER BY ordinal",
  );
  const capabilityStatement = db.prepare(
    "SELECT capability FROM work_offer_capabilities WHERE offer_id = ? ORDER BY capability",
  );
  return rows.map((row): WorkOfferView => {
    const inputs = inputStatement.all(row.id) as readonly { readonly artifact_id: ArtifactId }[];
    const capabilities = capabilityStatement.all(row.id) as readonly {
      readonly capability: WorkerCapability;
    }[];
    return {
      id: row.id,
      runId: row.run_id,
      actorId: row.actor_id,
      actorKey: row.actor_key,
      state: row.state,
      stateVisitId: row.state_visit_id,
      role: row.role,
      slot: row.slot,
      inputArtifacts: inputs.map((candidate) => candidate.artifact_id),
      taskArtifactId: row.task_artifact_id,
      contractVersion: row.contract_version,
      allowedWorkerCapabilities: capabilities.map((candidate) => candidate.capability),
      status: row.status,
      createdAt: row.created_at,
      ...(row.subject_artifact_id === null
        ? {}
        : { subjectArtifactId: row.subject_artifact_id }),
      ...(row.iteration_id === null ? {} : { iterationId: row.iteration_id as never }),
      ...(row.revision_id === null ? {} : { revisionId: row.revision_id as never }),
      ...(row.active_attempt_id === null ? {} : { activeAttemptId: row.active_attempt_id }),
      ...(row.reused_from_run_id === null
        ? {}
        : { reusedFromRunId: row.reused_from_run_id }),
      ...(row.reused_from_offer_id === null
        ? {}
        : { reusedFromOfferId: row.reused_from_offer_id }),
      ...(row.reused_answer_artifact_id === null
        ? {}
        : { reusedAnswerArtifactId: row.reused_answer_artifact_id }),
    };
  });
}

export function outcomeFromView(view: RunView): RunOutcome {
  switch (view.status) {
    case "complete": {
      const outputs = view.actors
        .filter((actor) => actor.parentActorId === undefined)
        .flatMap((actor) => actor.outputs);
      return { status: "complete", runId: view.id, outputs };
    }
    case "awaiting_editor":
      return {
        status: "awaiting_editor",
        runId: view.id,
        offers: view.offers.filter((offer) => offer.status === "offered"),
      };
    case "escalated":
      return {
        status: "escalated",
        runId: view.id,
        actors: view.actors
          .filter((actor) => actor.state === "escalated" || actor.state.endsWith(".escalated"))
          .map((actor) => actor.id),
      };
    case "failed":
      return {
        status: "failed",
        runId: view.id,
        failures: view.actors
          .filter((actor) => actor.status === "failed")
          .map((actor) => ({
            actorId: actor.id,
            classification: "actor_failed",
            message: `Actor ${actor.logicalKey} failed in ${actor.state}`,
          })),
      };
    case "waiting":
      return {
        status: "waiting",
        runId: view.id,
        offers: view.offers.filter(
          (offer) => offer.status === "offered" || offer.status === "claimed",
        ),
      };
    case "running":
      return { status: "running", runId: view.id };
  }
}
