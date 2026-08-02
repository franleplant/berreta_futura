import type Database from "better-sqlite3";

import type {
  ActorId,
  ArtifactId,
  ArtifactOrigin,
  ArtifactParent,
  ArtifactSeed,
  ArtifactView,
  AttemptId,
  JsonObject,
  RunId,
  WorkOfferId,
} from "../contracts/index.ts";
import type { PreparedPayload } from "./artifact-store.ts";
import { parseJson, stringifyJson } from "./serialization.ts";
import { RunEngineError } from "./types.ts";

export type ArtifactDisposition = "accepted" | "seed" | "stale" | "superseded";

export type ArtifactRecord = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schemaVersion: string;
  readonly mediaType: string;
  readonly origin: ArtifactOrigin;
  readonly payload: PreparedPayload;
  readonly parents: readonly ArtifactParent[];
  readonly metadata: JsonObject;
  readonly supersedes?: ArtifactId;
  readonly disposition: ArtifactDisposition;
  readonly producingRunId?: RunId;
  readonly producingActorId?: ActorId;
  readonly producingAttemptId?: AttemptId;
  readonly producingOfferId?: WorkOfferId;
  readonly createdAt: string;
};

type ArtifactRow = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schema_version: string;
  readonly media_type: string;
  readonly origin: ArtifactOrigin;
  readonly size_bytes: number;
  readonly producing_run_id: RunId | null;
  readonly producing_actor_id: ActorId | null;
  readonly producing_attempt_id: AttemptId | null;
  readonly producing_offer_id: WorkOfferId | null;
  readonly supersedes_artifact_id: ArtifactId | null;
  readonly metadata_json: string;
  readonly created_at: string;
};

export function insertArtifactRecords(
  db: Database.Database,
  records: readonly ArtifactRecord[],
): void {
  const seen = new Set<string>();
  for (const record of records) {
    if (seen.has(record.id)) {
      throw new RunEngineError("DUPLICATE_ARTIFACT", `Duplicate artifact id ${record.id}`);
    }
    seen.add(record.id);
    const existing = db.prepare("SELECT 1 FROM artifacts WHERE id = ?").get(record.id);
    if (existing !== undefined) {
      throw new RunEngineError(
        "ARTIFACT_IMMUTABLE",
        `Artifact ${record.id} already exists and cannot be overwritten`,
      );
    }
    db.prepare(
      `INSERT INTO artifacts(
        id, kind, schema_version, media_type, origin, storage_kind,
        inline_payload, relative_path, size_bytes, producing_run_id,
        producing_actor_id, producing_attempt_id, producing_offer_id,
        supersedes_artifact_id, disposition, metadata_json, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      record.id,
      record.kind,
      record.schemaVersion,
      record.mediaType,
      record.origin,
      record.payload.storageKind,
      record.payload.inlinePayload,
      record.payload.relativePath,
      record.payload.sizeBytes,
      record.producingRunId ?? null,
      record.producingActorId ?? null,
      record.producingAttemptId ?? null,
      record.producingOfferId ?? null,
      record.supersedes ?? null,
      record.disposition,
      stringifyJson(record.metadata),
      record.createdAt,
    );
  }

  for (const record of records) {
    record.parents.forEach((parent, ordinal) => {
      const parentExists = db.prepare("SELECT 1 FROM artifacts WHERE id = ?").get(parent.artifactId);
      if (parentExists === undefined) {
        throw new RunEngineError(
          "UNKNOWN_ARTIFACT_PARENT",
          `Artifact ${record.id} references unknown parent ${parent.artifactId}`,
        );
      }
      db.prepare(
        `INSERT INTO artifact_edges(
          child_artifact_id, parent_artifact_id, relation, ordinal
        ) VALUES (?, ?, ?, ?)`,
      ).run(record.id, parent.artifactId, parent.relation, ordinal);
    });
  }
}

export function recordFromSeed(
  seed: ArtifactSeed,
  payload: PreparedPayload,
  createdAt: string,
  producingRunId?: RunId,
): ArtifactRecord {
  const base = {
    id: seed.id,
    kind: seed.kind,
    schemaVersion: seed.schemaVersion,
    mediaType: seed.mediaType,
    origin: seed.origin,
    payload,
    parents: seed.parents ?? [],
    metadata: seed.metadata ?? {},
    disposition: "seed" as const,
    createdAt,
  };
  return {
    ...base,
    ...(seed.supersedes === undefined ? {} : { supersedes: seed.supersedes }),
    ...(producingRunId === undefined ? {} : { producingRunId }),
  };
}

export function loadArtifactViews(
  db: Database.Database,
  runId: RunId,
): readonly ArtifactView[] {
  const rows = db
    .prepare(
      `WITH RECURSIVE visible_artifacts(id) AS (
         SELECT id FROM artifacts WHERE producing_run_id = ?
         UNION
         SELECT artifact_id FROM run_inputs WHERE run_id = ?
         UNION
         SELECT artifact_id FROM run_outputs WHERE run_id = ?
         UNION
         SELECT edge.parent_artifact_id
         FROM artifact_edges edge
         JOIN visible_artifacts visible ON visible.id = edge.child_artifact_id
       )
       SELECT a.*
       FROM artifacts a
       JOIN visible_artifacts visible ON visible.id = a.id
       ORDER BY a.created_at, a.id`,
    )
    .all(runId, runId, runId) as readonly ArtifactRow[];
  const parentStatement = db.prepare(
    `SELECT parent_artifact_id AS artifactId, relation
     FROM artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal`,
  );
  return rows.map((row): ArtifactView => {
    const parents = parentStatement.all(row.id) as readonly ArtifactParent[];
    return {
      id: row.id,
      kind: row.kind,
      schemaVersion: row.schema_version,
      mediaType: row.media_type,
      origin: row.origin,
      sizeBytes: row.size_bytes,
      parents,
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
  });
}
