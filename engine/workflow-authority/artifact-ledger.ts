import Database from "better-sqlite3";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { mkdirSync } from "node:fs";

import type {
  ArtifactId,
  ArtifactOrigin,
  ArtifactParent,
  ArtifactView,
  DecisionView,
  JsonObject,
  JsonValue,
  RunView,
  RunId,
  WorkOfferView,
} from "../contracts/index.ts";
import type { WorkflowDurableContext } from "../workflows/internal-types.ts";

export type LedgerPayload =
  | { readonly kind: "text"; readonly text: string }
  | { readonly kind: "json"; readonly value: JsonValue }
  | { readonly kind: "bytes"; readonly bytes: Uint8Array };

export type LedgerArtifactInput = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schemaVersion: string;
  readonly mediaType: string;
  readonly origin: ArtifactOrigin;
  readonly payload: LedgerPayload;
  readonly parents?: readonly ArtifactParent[];
  readonly metadata?: JsonObject;
  readonly runId?: RunId;
  readonly durableContext?: WorkflowDurableContext;
};

export type LedgerArtifact = ArtifactView & {
  readonly payloadKind: LedgerPayload["kind"];
  readonly digest: string;
  readonly durableContext?: WorkflowDurableContext;
};

export type LedgerRun = {
  readonly runId: RunId;
  readonly articleId: string;
  readonly editionId?: string;
  readonly workflowVersion: string;
  readonly loopsRunId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId?: ArtifactId;
  readonly decisionArtifactId?: ArtifactId;
  readonly promotionId?: string;
  readonly args: JsonObject;
  readonly argsDigest: string;
  readonly workflowPin?: JsonObject;
  readonly loopsContext?: WorkflowDurableContext;
};

export type LedgerOffer = {
  readonly id: string;
  readonly runId: RunId;
  readonly role: "article_decision";
  readonly status: "active" | "answered";
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly allowedChoices: readonly ("accept" | "drop")[];
  readonly createdAt: string;
};

export type LedgerDecision = {
  readonly id: string;
  readonly runId: RunId;
  readonly offerId: string;
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly principalId: string;
  readonly credentialProfileId: string;
  readonly choice: "accept" | "drop";
  readonly rationale: string;
  readonly artifactId: ArtifactId;
  readonly createdAt: string;
};

export type LedgerPromotion = {
  readonly promotionId: string;
  readonly runId: RunId;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly decisionArtifactId: ArtifactId;
  readonly reviewer: string;
  readonly rationale: string;
  readonly durableRevisionId: string;
  readonly manifestDigest: string;
  readonly gitCommitOid: string;
  readonly gitBlobOids: Readonly<Record<string, string>>;
  readonly revisionId: string;
  readonly expectedParentRevisionId: string | null;
  readonly inputRevisions: readonly JsonObject[];
  readonly acceptedArtifactIds: readonly ArtifactId[];
  readonly decisionArtifactIds: readonly ArtifactId[];
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly createdAt: string;
};

export class ArtifactLedgerError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "ArtifactLedgerError";
    this.code = code;
  }
}

type ArtifactRow = {
  readonly id: ArtifactId;
  readonly kind: string;
  readonly schema_version: string;
  readonly media_type: string;
  readonly origin: ArtifactOrigin;
  readonly payload_kind: LedgerPayload["kind"];
  readonly payload: Buffer;
  readonly metadata_json: string;
  readonly durable_context_json: string | null;
  readonly run_id: RunId | null;
  readonly created_at: string;
  readonly digest: string;
};

type RunRow = {
  readonly run_id: RunId;
  readonly article_id: string;
  readonly edition_id: string | null;
  readonly workflow_version: string;
  readonly loops_run_id: string;
  readonly manuscript_artifact_id: ArtifactId;
  readonly measurement_artifact_id: ArtifactId | null;
  readonly decision_artifact_id: ArtifactId | null;
  readonly promotion_id: string | null;
  readonly args_json: string;
  readonly args_digest: string;
  readonly workflow_pin_json: string | null;
  readonly loops_context_json: string | null;
};

/**
 * Magazine's immutable record seam.  It intentionally knows nothing about
 * Loops persistence.  Loops IDs are copied into metadata so provenance can be
 * inspected without granting callers access to the Loops store.
 */
export class ArtifactLedger {
  readonly #db: Database.Database;
  readonly #clock: { readonly now: () => Date };

  constructor(
    databasePath: string,
    options: { readonly clock?: { readonly now: () => Date } } = {},
  ) {
    mkdirSync(dirname(resolve(databasePath)), { recursive: true, mode: 0o700 });
    this.#db = new Database(resolve(databasePath));
    this.#db.pragma("foreign_keys = ON");
    this.#db.pragma("journal_mode = WAL");
    this.#db.pragma("synchronous = FULL");
    this.#clock = options.clock ?? { now: () => new Date() };
    this.#applySchema();
  }

  close(): void {
    this.#db.close();
  }

  createRun(input: {
    readonly runId: RunId;
    readonly articleId: string;
    readonly editionId?: string;
    readonly workflowVersion: string;
    readonly loopsRunId: string;
    readonly manuscriptArtifactId: ArtifactId;
    readonly args: JsonValue;
    readonly workflowPin?: JsonObject;
    readonly loopsContext?: WorkflowDurableContext;
  }): LedgerRun {
    const argsDigest = digestJson(input.args);
    const existing = this.#db.prepare("SELECT * FROM magazine_runs WHERE run_id = ?").get(input.runId) as RunRow | undefined;
    if (existing !== undefined) {
      if (
        existing.article_id !== input.articleId
        || existing.workflow_version !== input.workflowVersion
        || existing.loops_run_id !== input.loopsRunId
        || existing.manuscript_artifact_id !== input.manuscriptArtifactId
        || existing.args_digest !== argsDigest
        || !sameJsonOptional(existing.workflow_pin_json, input.workflowPin)
      ) {
        throw new ArtifactLedgerError("RUN_ID_COLLISION", `Run ${input.runId} already has a different immutable identity`);
      }
      return toRun(existing);
    }
    this.#db.prepare(
      `INSERT INTO magazine_runs(
        run_id, article_id, edition_id, workflow_version, loops_run_id,
        manuscript_artifact_id, measurement_artifact_id, decision_artifact_id,
        promotion_id, args_digest, args_json, workflow_pin_json, loops_context_json
      ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?)`,
    ).run(
      input.runId,
      input.articleId,
      input.editionId ?? null,
      input.workflowVersion,
      input.loopsRunId,
      input.manuscriptArtifactId,
      argsDigest,
      JSON.stringify(input.args),
      input.workflowPin === undefined ? null : JSON.stringify(input.workflowPin),
      input.loopsContext === undefined ? null : JSON.stringify(contextObject(input.loopsContext)),
    );
    return this.requireRun(input.runId);
  }

  getRun(runId: RunId): LedgerRun | undefined {
    const row = this.#db.prepare("SELECT * FROM magazine_runs WHERE run_id = ?").get(runId) as RunRow | undefined;
    return row === undefined ? undefined : toRun(row);
  }

  requireRun(runId: RunId): LedgerRun {
    const run = this.getRun(runId);
    if (run === undefined) throw new ArtifactLedgerError("RUN_NOT_FOUND", `Magazine run ${runId} does not exist`);
    return run;
  }

  #recordRunFacts(
    runId: RunId,
    patch: {
      readonly manuscriptArtifactId?: ArtifactId;
      readonly measurementArtifactId?: ArtifactId;
      readonly decisionArtifactId?: ArtifactId;
      readonly promotionId?: string;
    },
  ): LedgerRun {
    this.requireRun(runId);
    const fields: string[] = [];
    const values: unknown[] = [];
    if (patch.manuscriptArtifactId !== undefined) { fields.push("manuscript_artifact_id = ?"); values.push(patch.manuscriptArtifactId); }
    if (patch.measurementArtifactId !== undefined) { fields.push("measurement_artifact_id = ?"); values.push(patch.measurementArtifactId); }
    if (patch.decisionArtifactId !== undefined) { fields.push("decision_artifact_id = ?"); values.push(patch.decisionArtifactId); }
    if (patch.promotionId !== undefined) { fields.push("promotion_id = ?"); values.push(patch.promotionId); }
    if (fields.length > 0) {
      fields.push("updated_at = ?");
      values.push(this.#clock.now().toISOString());
      values.push(runId);
      this.#db.prepare(`UPDATE magazine_runs SET ${fields.join(", ")} WHERE run_id = ?`).run(...values);
    }
    return this.requireRun(runId);
  }

  /** Persist execution observations only. Lifecycle remains in Loops. */
  recordLoopsObservation(
    runId: RunId,
    input: { readonly workflowPin?: JsonObject; readonly context?: WorkflowDurableContext },
  ): LedgerRun {
    this.requireRun(runId);
    const fields: string[] = [];
    const values: unknown[] = [];
    if (input.workflowPin !== undefined) {
      fields.push("workflow_pin_json = ?");
      values.push(JSON.stringify(input.workflowPin));
    }
    if (input.context !== undefined) {
      fields.push("loops_context_json = ?");
      values.push(JSON.stringify(contextObject(input.context)));
    }
    if (fields.length === 0) return this.requireRun(runId);
    fields.push("updated_at = ?");
    values.push(this.#clock.now().toISOString(), runId);
    this.#db.prepare(`UPDATE magazine_runs SET ${fields.join(", ")} WHERE run_id = ?`).run(...values);
    return this.requireRun(runId);
  }

  recordMeasurement(runId: RunId, measurementArtifactId: ArtifactId): LedgerRun {
    this.requireArtifact(measurementArtifactId);
    return this.#recordRunFacts(runId, { measurementArtifactId });
  }

  recordManuscriptArtifact(runId: RunId, manuscriptArtifactId: ArtifactId): LedgerRun {
    this.requireArtifact(manuscriptArtifactId);
    return this.#recordRunFacts(runId, { manuscriptArtifactId });
  }

  recordDecisionArtifact(runId: RunId, decisionArtifactId: ArtifactId): LedgerRun {
    const decision = this.requireDecisionForRun(runId);
    if (decision.artifactId !== decisionArtifactId) {
      throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${decisionArtifactId} is not current for run ${runId}`);
    }
    return this.#recordRunFacts(runId, { decisionArtifactId });
  }

  /**
   * DurableStore evidence adapter. It projects persisted facts into the
   * narrow RunView shape DurableStore validates; it cannot change lifecycle.
   */
  durableEvidence(runId: RunId): RunView {
    const run = this.requireRun(runId);
    const artifacts = this.listArtifacts(runId) as readonly ArtifactView[];
    const offers = this.#db.prepare("SELECT * FROM magazine_offers WHERE run_id = ? ORDER BY created_at, id").all(runId) as OfferRow[];
    const decisions = this.#db.prepare("SELECT * FROM magazine_decisions WHERE run_id = ? ORDER BY created_at, id").all(runId) as DecisionRow[];
    return {
      id: runId,
      kind: "article",
      status: "waiting",
      machineVersion: run.workflowVersion,
      headSequence: 0,
      actors: [],
      iterations: [],
      sourceSubmissions: [],
      offers: offers.map(toDurableOffer),
      attempts: [],
      artifacts,
      events: [],
      decisions: decisions.map(toDurableDecision),
      createdAt: artifacts[0]?.createdAt ?? new Date(0).toISOString(),
      updatedAt: this.#clock.now().toISOString(),
    };
  }

  createArtifact(input: LedgerArtifactInput): LedgerArtifact {
    const payload = encodePayload(input.payload);
    const metadata = { ...(input.metadata ?? {}), ...(input.durableContext === undefined ? {} : { durableContext: contextObject(input.durableContext) }) };
    const parents = input.parents ?? [];
    const createdAt = this.#clock.now().toISOString();
    const existing = this.#db.prepare("SELECT * FROM magazine_artifacts WHERE id = ?").get(input.id) as ArtifactRow | undefined;
    if (existing !== undefined) {
      if (!sameArtifact(existing, input, payload, metadata, parents, this.parentRows(input.id))) {
        throw new ArtifactLedgerError("ARTIFACT_ID_COLLISION", `Artifact ${input.id} already exists with different immutable content`);
      }
      return this.requireArtifact(input.id);
    }
    const transaction = this.#db.transaction(() => {
      for (const parent of parents) this.requireArtifact(parent.artifactId);
      this.#db.prepare(
        `INSERT INTO magazine_artifacts(
          id, kind, schema_version, media_type, origin, payload_kind, payload,
          metadata_json, durable_context_json, run_id, created_at, digest
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        input.id,
        input.kind,
        input.schemaVersion,
        input.mediaType,
        input.origin,
        input.payload.kind,
        payload,
        JSON.stringify(metadata),
        input.durableContext === undefined ? null : JSON.stringify(contextObject(input.durableContext)),
        input.runId ?? null,
        createdAt,
        digest(payload),
      );
      parents.forEach((parent, ordinal) => {
        this.#db.prepare(
          `INSERT INTO magazine_artifact_edges(child_artifact_id, parent_artifact_id, relation, ordinal)
           VALUES (?, ?, ?, ?)`,
        ).run(input.id, parent.artifactId, parent.relation, ordinal);
      });
    });
    transaction();
    return this.requireArtifact(input.id);
  }

  getArtifact(artifactId: ArtifactId): LedgerArtifact | undefined {
    const row = this.#db.prepare("SELECT * FROM magazine_artifacts WHERE id = ?").get(artifactId) as ArtifactRow | undefined;
    return row === undefined ? undefined : this.#toArtifact(row);
  }

  requireArtifact(artifactId: ArtifactId): LedgerArtifact {
    const artifact = this.getArtifact(artifactId);
    if (artifact === undefined) throw new ArtifactLedgerError("ARTIFACT_NOT_FOUND", `Artifact ${artifactId} does not exist`);
    return artifact;
  }

  readArtifact(artifactId: ArtifactId): { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array } {
    const artifact = this.requireArtifact(artifactId);
    const row = this.#db.prepare("SELECT payload FROM magazine_artifacts WHERE id = ?").get(artifactId) as { readonly payload: Buffer };
    return { artifact, bytes: new Uint8Array(Buffer.from(row.payload)) };
  }

  listArtifacts(runId: RunId): readonly LedgerArtifact[] {
    const rows = this.#db.prepare(
      "SELECT * FROM magazine_artifacts WHERE run_id = ? ORDER BY created_at, id",
    ).all(runId) as ArtifactRow[];
    return rows.map((row) => this.#toArtifact(row));
  }

  createOffer(input: {
    readonly id: string;
    readonly runId: RunId;
    readonly taskArtifactId: ArtifactId;
    readonly inputArtifactIds: readonly ArtifactId[];
    readonly allowedChoices?: readonly ("accept" | "drop")[];
  }): LedgerOffer {
    const existing = this.#db.prepare("SELECT * FROM magazine_offers WHERE id = ?").get(input.id) as OfferRow | undefined;
    if (existing !== undefined) {
      const offer = toOffer(existing);
      const expectedInputs = input.inputArtifactIds;
      const expectedChoices = input.allowedChoices ?? ["accept", "drop"];
      if (
        offer.runId !== input.runId
        || offer.taskArtifactId !== input.taskArtifactId
        || !sameStrings(offer.inputArtifactIds, expectedInputs)
        || !sameStrings(offer.allowedChoices, expectedChoices)
      ) {
        throw new ArtifactLedgerError("OFFER_ID_COLLISION", `Offer ${input.id} already has a different immutable identity`);
      }
      return offer;
    }
    this.requireRun(input.runId);
    this.requireArtifact(input.taskArtifactId);
    for (const artifactId of input.inputArtifactIds) this.requireArtifact(artifactId);
    const allowedChoices = input.allowedChoices ?? ["accept", "drop"];
    if (allowedChoices.length === 0 || allowedChoices.some((choice) => !["accept", "drop"].includes(choice))) {
      throw new ArtifactLedgerError("OFFER_INVALID", "Article decision offer must expose accept or drop");
    }
    this.#db.prepare(
      `INSERT INTO magazine_offers(
        id, run_id, role, status, task_artifact_id, input_artifact_ids_json,
        allowed_choices_json, created_at
      ) VALUES (?, ?, 'article_decision', 'active', ?, ?, ?, ?)`,
    ).run(
      input.id,
      input.runId,
      input.taskArtifactId,
      JSON.stringify(input.inputArtifactIds),
      JSON.stringify(allowedChoices),
      this.#clock.now().toISOString(),
    );
    return this.requireOffer(input.id);
  }

  getOffer(offerId: string): LedgerOffer | undefined {
    const row = this.#db.prepare("SELECT * FROM magazine_offers WHERE id = ?").get(offerId) as OfferRow | undefined;
    return row === undefined ? undefined : toOffer(row);
  }

  requireOffer(offerId: string): LedgerOffer {
    const offer = this.getOffer(offerId);
    if (offer === undefined) throw new ArtifactLedgerError("OFFER_NOT_FOUND", `Offer ${offerId} does not exist`);
    return offer;
  }

  activeOffer(runId: RunId): LedgerOffer | undefined {
    const row = this.#db.prepare(
      "SELECT * FROM magazine_offers WHERE run_id = ? AND status = 'active' ORDER BY created_at, id LIMIT 1",
    ).get(runId) as OfferRow | undefined;
    return row === undefined ? undefined : toOffer(row);
  }

  recordDecision(input: Omit<LedgerDecision, "createdAt"> & { readonly createdAt?: string }): LedgerDecision {
    const existing = this.#db.prepare("SELECT * FROM magazine_decisions WHERE offer_id = ?").get(input.offerId) as DecisionRow | undefined;
    if (existing !== undefined) {
      const decision = toDecision(existing);
      if (decision.principalId !== input.principalId || decision.choice !== input.choice || decision.rationale !== input.rationale) {
        throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${input.offerId} already has a different decision`);
      }
      return decision;
    }
    const offer = this.requireOffer(input.offerId);
    if (offer.runId !== input.runId || offer.status !== "active") throw new ArtifactLedgerError("OFFER_STALE", `Offer ${input.offerId} is not active for this run`);
    if (!offer.allowedChoices.includes(input.choice)) throw new ArtifactLedgerError("CHOICE_INVALID", `Choice ${input.choice} is not allowed for offer ${input.offerId}`);
    if (offer.taskArtifactId !== input.taskArtifactId || !sameStrings(offer.inputArtifactIds, input.inputArtifactIds)) throw new ArtifactLedgerError("OFFER_INPUT_MISMATCH", `Decision does not bind offer ${input.offerId}'s immutable inputs`);
    const createdAt = input.createdAt ?? this.#clock.now().toISOString();
    const transaction = this.#db.transaction(() => {
      this.#db.prepare(
        `INSERT INTO magazine_decisions(
          id, run_id, offer_id, task_artifact_id, input_artifact_ids_json,
          principal_id, credential_profile_id, choice, rationale, artifact_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        input.id,
        input.runId,
        input.offerId,
        input.taskArtifactId,
        JSON.stringify(input.inputArtifactIds),
        input.principalId,
        input.credentialProfileId,
        input.choice,
        input.rationale,
        input.artifactId,
        createdAt,
      );
    });
    transaction();
    return this.requireDecision(input.offerId);
  }

  markOfferAnswered(offerId: string): LedgerOffer {
    const offer = this.requireOffer(offerId);
    if (offer.status === "active") {
      this.#db.prepare("UPDATE magazine_offers SET status = 'answered' WHERE id = ? AND status = 'active'").run(offerId);
    }
    return this.requireOffer(offerId);
  }

  getDecision(offerId: string): LedgerDecision | undefined {
    const row = this.#db.prepare("SELECT * FROM magazine_decisions WHERE offer_id = ?").get(offerId) as DecisionRow | undefined;
    return row === undefined ? undefined : toDecision(row);
  }

  requireDecisionForRun(runId: RunId): LedgerDecision {
    const row = this.#db.prepare(
      `SELECT d.* FROM magazine_decisions d
       JOIN magazine_offers o ON o.id = d.offer_id
       WHERE d.run_id = ? ORDER BY d.created_at, d.id LIMIT 1`,
    ).get(runId) as DecisionRow | undefined;
    if (row === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Run ${runId} has no human decision`);
    return toDecision(row);
  }

  requireDecision(offerId: string): LedgerDecision {
    const decision = this.getDecision(offerId);
    if (decision === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision for ${offerId} does not exist`);
    return decision;
  }

  recordPromotion(input: LedgerPromotion): LedgerPromotion {
    const existing = this.#db.prepare("SELECT * FROM magazine_promotions WHERE run_id = ?").get(input.runId) as PromotionRow | undefined;
    if (existing !== undefined) {
      const promotion = toPromotion(existing);
      if (JSON.stringify(promotion) !== JSON.stringify(input)) throw new ArtifactLedgerError("PROMOTION_CONFLICT", `Run ${input.runId} already has a different promotion`);
      return promotion;
    }
    this.requireRun(input.runId);
    this.requireArtifact(input.manuscriptArtifactId);
    this.requireArtifact(input.measurementArtifactId);
    this.requireArtifact(input.decisionArtifactId);
    this.#db.prepare(
      `INSERT INTO magazine_promotions(
        promotion_id, run_id, article_id, manuscript_artifact_id,
        measurement_artifact_id, decision_artifact_id, reviewer, rationale,
        durable_revision_id, manifest_digest, git_commit_oid, git_blob_oids_json,
        revision_id, expected_parent_revision_id, input_revisions_json,
        accepted_artifact_ids_json, decision_artifact_ids_json, input_artifact_ids_json, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      input.promotionId,
      input.runId,
      input.articleId,
      input.manuscriptArtifactId,
      input.measurementArtifactId,
      input.decisionArtifactId,
      input.reviewer,
      input.rationale,
      input.durableRevisionId,
      input.manifestDigest,
      input.gitCommitOid,
      JSON.stringify(input.gitBlobOids),
      input.revisionId,
      input.expectedParentRevisionId,
      JSON.stringify(input.inputRevisions),
      JSON.stringify(input.acceptedArtifactIds),
      JSON.stringify(input.decisionArtifactIds),
      JSON.stringify(input.inputArtifactIds),
      input.createdAt,
    );
    this.#recordRunFacts(input.runId, { promotionId: input.promotionId });
    return this.requirePromotion(input.runId);
  }

  getPromotion(runId: RunId): LedgerPromotion | undefined {
    const row = this.#db.prepare("SELECT * FROM magazine_promotions WHERE run_id = ?").get(runId) as PromotionRow | undefined;
    return row === undefined ? undefined : toPromotion(row);
  }

  requirePromotion(runId: RunId): LedgerPromotion {
    const promotion = this.getPromotion(runId);
    if (promotion === undefined) throw new ArtifactLedgerError("PROMOTION_NOT_FOUND", `Run ${runId} has no promotion`);
    return promotion;
  }

  #toArtifact(row: ArtifactRow): LedgerArtifact {
    const parents = this.#db.prepare(
      "SELECT parent_artifact_id AS artifactId, relation FROM magazine_artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal",
    ).all(row.id) as readonly ArtifactParent[];
    const metadata = JSON.parse(row.metadata_json) as JsonObject;
    return {
      id: row.id,
      kind: row.kind,
      schemaVersion: row.schema_version,
      mediaType: row.media_type,
      origin: row.origin,
      sizeBytes: row.payload.byteLength,
      parents,
      metadata,
      createdAt: row.created_at,
      payloadKind: row.payload_kind,
      digest: row.digest,
      ...(row.run_id === null ? {} : { producingRunId: row.run_id }),
      ...(row.durable_context_json === null ? {} : { durableContext: JSON.parse(row.durable_context_json) as WorkflowDurableContext }),
    };
  }

  #applySchema(): void {
    this.#db.exec(`
      CREATE TABLE IF NOT EXISTS magazine_runs (
        run_id TEXT PRIMARY KEY,
        article_id TEXT NOT NULL,
        edition_id TEXT,
        workflow_version TEXT NOT NULL,
        loops_run_id TEXT NOT NULL UNIQUE,
        manuscript_artifact_id TEXT NOT NULL,
        measurement_artifact_id TEXT,
        decision_artifact_id TEXT,
        promotion_id TEXT UNIQUE,
        args_digest TEXT NOT NULL,
        args_json TEXT NOT NULL,
        workflow_pin_json TEXT,
        loops_context_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS magazine_artifacts (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        schema_version TEXT NOT NULL,
        media_type TEXT NOT NULL,
        origin TEXT NOT NULL,
        payload_kind TEXT NOT NULL,
        payload BLOB NOT NULL,
        metadata_json TEXT NOT NULL,
        durable_context_json TEXT,
        run_id TEXT,
        created_at TEXT NOT NULL,
        digest TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES magazine_runs(run_id)
      );
      CREATE TABLE IF NOT EXISTS magazine_artifact_edges (
        child_artifact_id TEXT NOT NULL,
        parent_artifact_id TEXT NOT NULL,
        relation TEXT NOT NULL,
        ordinal INTEGER NOT NULL,
        PRIMARY KEY (child_artifact_id, ordinal),
        FOREIGN KEY (child_artifact_id) REFERENCES magazine_artifacts(id),
        FOREIGN KEY (parent_artifact_id) REFERENCES magazine_artifacts(id)
      );
      CREATE TABLE IF NOT EXISTS magazine_offers (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT NOT NULL,
        task_artifact_id TEXT NOT NULL,
        input_artifact_ids_json TEXT NOT NULL,
        allowed_choices_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES magazine_runs(run_id),
        FOREIGN KEY (task_artifact_id) REFERENCES magazine_artifacts(id)
      );
      CREATE UNIQUE INDEX IF NOT EXISTS magazine_one_active_offer
        ON magazine_offers(run_id) WHERE status = 'active';
      CREATE TABLE IF NOT EXISTS magazine_decisions (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        offer_id TEXT NOT NULL UNIQUE,
        task_artifact_id TEXT NOT NULL,
        input_artifact_ids_json TEXT NOT NULL,
        principal_id TEXT NOT NULL,
        credential_profile_id TEXT NOT NULL,
        choice TEXT NOT NULL,
        rationale TEXT NOT NULL,
        artifact_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES magazine_runs(run_id),
        FOREIGN KEY (offer_id) REFERENCES magazine_offers(id),
        FOREIGN KEY (task_artifact_id) REFERENCES magazine_artifacts(id),
        FOREIGN KEY (artifact_id) REFERENCES magazine_artifacts(id)
      );
      CREATE TABLE IF NOT EXISTS magazine_promotions (
        promotion_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        article_id TEXT NOT NULL,
        manuscript_artifact_id TEXT NOT NULL,
        measurement_artifact_id TEXT NOT NULL,
        decision_artifact_id TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        rationale TEXT NOT NULL,
        durable_revision_id TEXT NOT NULL,
        manifest_digest TEXT NOT NULL,
        git_commit_oid TEXT NOT NULL,
        git_blob_oids_json TEXT NOT NULL,
        revision_id TEXT NOT NULL,
        expected_parent_revision_id TEXT,
        input_revisions_json TEXT NOT NULL,
        accepted_artifact_ids_json TEXT NOT NULL,
        decision_artifact_ids_json TEXT NOT NULL,
        input_artifact_ids_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES magazine_runs(run_id),
        FOREIGN KEY (manuscript_artifact_id) REFERENCES magazine_artifacts(id),
        FOREIGN KEY (measurement_artifact_id) REFERENCES magazine_artifacts(id),
        FOREIGN KEY (decision_artifact_id) REFERENCES magazine_artifacts(id)
      );
    `);
    this.#ensureColumn("magazine_runs", "workflow_pin_json", "TEXT");
    this.#ensureColumn("magazine_runs", "loops_context_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "manifest_digest", "TEXT");
    this.#ensureColumn("magazine_promotions", "git_commit_oid", "TEXT");
    this.#ensureColumn("magazine_promotions", "git_blob_oids_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "revision_id", "TEXT");
    this.#ensureColumn("magazine_promotions", "expected_parent_revision_id", "TEXT");
    this.#ensureColumn("magazine_promotions", "input_revisions_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "accepted_artifact_ids_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "decision_artifact_ids_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "input_artifact_ids_json", "TEXT");
  }

  #ensureColumn(table: string, column: string, definition: string): void {
    const columns = this.#db.prepare(`PRAGMA table_info(${table})`).all() as readonly { readonly name: string }[];
    if (!columns.some((candidate) => candidate.name === column)) {
      this.#db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`);
    }
  }

  private parentRows(artifactId: ArtifactId): readonly ArtifactParent[] {
    return this.#db.prepare(
      "SELECT parent_artifact_id AS artifactId, relation FROM magazine_artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal",
    ).all(artifactId) as readonly ArtifactParent[];
  }
}

type OfferRow = {
  readonly id: string;
  readonly run_id: RunId;
  readonly role: "article_decision";
  readonly status: "active" | "answered";
  readonly task_artifact_id: ArtifactId;
  readonly input_artifact_ids_json: string;
  readonly allowed_choices_json: string;
  readonly created_at: string;
};

type DecisionRow = {
  readonly id: string;
  readonly run_id: RunId;
  readonly offer_id: string;
  readonly task_artifact_id: ArtifactId;
  readonly input_artifact_ids_json: string;
  readonly principal_id: string;
  readonly credential_profile_id: string;
  readonly choice: "accept" | "drop";
  readonly rationale: string;
  readonly artifact_id: ArtifactId;
  readonly created_at: string;
};

type PromotionRow = {
  readonly promotion_id: string;
  readonly run_id: RunId;
  readonly article_id: string;
  readonly manuscript_artifact_id: ArtifactId;
  readonly measurement_artifact_id: ArtifactId;
  readonly decision_artifact_id: ArtifactId;
  readonly reviewer: string;
  readonly rationale: string;
  readonly durable_revision_id: string;
  readonly manifest_digest: string | null;
  readonly git_commit_oid: string | null;
  readonly git_blob_oids_json: string | null;
  readonly revision_id: string | null;
  readonly expected_parent_revision_id: string | null;
  readonly input_revisions_json: string | null;
  readonly accepted_artifact_ids_json: string | null;
  readonly decision_artifact_ids_json: string | null;
  readonly input_artifact_ids_json: string | null;
  readonly created_at: string;
};

function encodePayload(payload: LedgerPayload): Buffer {
  if (payload.kind === "text") return Buffer.from(payload.text, "utf8");
  if (payload.kind === "bytes") return Buffer.from(payload.bytes);
  return Buffer.from(JSON.stringify(payload.value), "utf8");
}

function digest(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function digestJson(value: JsonValue): string {
  return digest(Buffer.from(JSON.stringify(value), "utf8"));
}

function contextObject(context: WorkflowDurableContext): JsonObject {
  return Object.fromEntries(Object.entries(context).filter(([, value]) => value !== undefined)) as JsonObject;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function sameJsonOptional(serialized: string | null, value: JsonValue | undefined): boolean {
  return serialized === (value === undefined ? null : JSON.stringify(value));
}

function sameArtifact(
  row: ArtifactRow,
  input: LedgerArtifactInput,
  payload: Buffer,
  metadata: JsonObject,
  parents: readonly ArtifactParent[],
  existingParents: readonly ArtifactParent[],
): boolean {
  return row.kind === input.kind
    && row.schema_version === input.schemaVersion
    && row.media_type === input.mediaType
    && row.origin === input.origin
    && row.payload_kind === input.payload.kind
    && Buffer.from(row.payload).equals(payload)
    && metadataWithoutContext(row.metadata_json) === JSON.stringify(stripContext(metadata))
    && row.run_id === (input.runId ?? null)
    && sameParents(parents, existingParents);
}

function metadataWithoutContext(serialized: string): string {
  const value = JSON.parse(serialized) as JsonObject;
  return JSON.stringify(stripContext(value));
}

function stripContext(value: JsonObject): JsonObject {
  const { durableContext: _durableContext, ...rest } = value;
  return rest;
}

function sameParents(left: readonly ArtifactParent[], right: readonly ArtifactParent[]): boolean {
  return left.length === right.length && left.every((parent, index) => {
    const other = right[index];
    return other !== undefined && other.artifactId === parent.artifactId && other.relation === parent.relation;
  });
}

function toRun(row: RunRow): LedgerRun {
  return {
    runId: row.run_id,
    articleId: row.article_id,
    ...(row.edition_id === null ? {} : { editionId: row.edition_id }),
    workflowVersion: row.workflow_version,
    loopsRunId: row.loops_run_id,
    manuscriptArtifactId: row.manuscript_artifact_id,
    ...(row.measurement_artifact_id === null ? {} : { measurementArtifactId: row.measurement_artifact_id }),
    ...(row.decision_artifact_id === null ? {} : { decisionArtifactId: row.decision_artifact_id }),
    ...(row.promotion_id === null ? {} : { promotionId: row.promotion_id }),
    args: JSON.parse(row.args_json) as JsonObject,
    argsDigest: row.args_digest,
    ...(row.workflow_pin_json === null ? {} : { workflowPin: JSON.parse(row.workflow_pin_json) as JsonObject }),
    ...(row.loops_context_json === null ? {} : { loopsContext: JSON.parse(row.loops_context_json) as WorkflowDurableContext }),
  };
}

function toOffer(row: OfferRow): LedgerOffer {
  return {
    id: row.id,
    runId: row.run_id,
    role: row.role,
    status: row.status,
    taskArtifactId: row.task_artifact_id,
    inputArtifactIds: JSON.parse(row.input_artifact_ids_json) as readonly ArtifactId[],
    allowedChoices: JSON.parse(row.allowed_choices_json) as readonly ("accept" | "drop")[],
    createdAt: row.created_at,
  };
}

function toDecision(row: DecisionRow): LedgerDecision {
  return {
    id: row.id,
    runId: row.run_id,
    offerId: row.offer_id,
    taskArtifactId: row.task_artifact_id,
    inputArtifactIds: JSON.parse(row.input_artifact_ids_json) as readonly ArtifactId[],
    principalId: row.principal_id,
    credentialProfileId: row.credential_profile_id,
    choice: row.choice,
    rationale: row.rationale,
    artifactId: row.artifact_id,
    createdAt: row.created_at,
  };
}

function toPromotion(row: PromotionRow): LedgerPromotion {
  return {
    promotionId: row.promotion_id,
    runId: row.run_id,
    articleId: row.article_id,
    manuscriptArtifactId: row.manuscript_artifact_id,
    measurementArtifactId: row.measurement_artifact_id,
    decisionArtifactId: row.decision_artifact_id,
    reviewer: row.reviewer,
    rationale: row.rationale,
    durableRevisionId: row.durable_revision_id,
    manifestDigest: row.manifest_digest ?? "",
    gitCommitOid: row.git_commit_oid ?? "",
    gitBlobOids: row.git_blob_oids_json === null ? {} : JSON.parse(row.git_blob_oids_json) as Readonly<Record<string, string>>,
    revisionId: row.revision_id ?? row.durable_revision_id,
    expectedParentRevisionId: row.expected_parent_revision_id,
    inputRevisions: row.input_revisions_json === null ? [] : JSON.parse(row.input_revisions_json) as readonly JsonObject[],
    acceptedArtifactIds: row.accepted_artifact_ids_json === null ? [row.manuscript_artifact_id] : JSON.parse(row.accepted_artifact_ids_json) as readonly ArtifactId[],
    decisionArtifactIds: row.decision_artifact_ids_json === null ? [row.decision_artifact_id] : JSON.parse(row.decision_artifact_ids_json) as readonly ArtifactId[],
    inputArtifactIds: row.input_artifact_ids_json === null ? [] : JSON.parse(row.input_artifact_ids_json) as readonly ArtifactId[],
    createdAt: row.created_at,
  };
}

function toDurableOffer(row: OfferRow): WorkOfferView {
  return {
    id: row.id as WorkOfferView["id"],
    runId: row.run_id,
    actorId: `actor-${row.run_id}` as WorkOfferView["actorId"],
    actorKey: "magazine.article",
    state: "awaiting_decision",
    stateVisitId: `visit-${row.id}` as WorkOfferView["stateVisitId"],
    role: "editor_decision",
    slot: "article-decision",
    subjectArtifactId: row.task_artifact_id,
    inputArtifacts: JSON.parse(row.input_artifact_ids_json) as readonly ArtifactId[],
    taskArtifactId: row.task_artifact_id,
    contractVersion: "article-decision-request/1",
    allowedWorkerCapabilities: ["human"],
    requirements: { authority: "human", capabilities: [], minimumAssurance: "local_bearer" },
    status: row.status === "active" ? "offered" : "answered",
    createdAt: row.created_at,
  };
}

function toDurableDecision(row: DecisionRow): DecisionView {
  return {
    id: row.id as DecisionView["id"],
    actorId: `actor-${row.run_id}` as DecisionView["actorId"],
    offerId: row.offer_id as NonNullable<DecisionView["offerId"]>,
    subjectArtifactId: row.task_artifact_id,
    principalId: row.principal_id,
    choice: row.choice,
    authority: "human",
    artifactId: row.artifact_id,
    authorizationId: row.credential_profile_id,
    details: { rationale: row.rationale, credentialProfileId: row.credential_profile_id },
    createdAt: row.created_at,
  };
}
