import Database from "better-sqlite3";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { dirname, resolve } from "node:path";
import { mkdirSync } from "node:fs";
import { durableContext as loopsDurableContext } from "@loops/core";

import type {
  ArticleExecutionId,
  ArtifactId,
  ArtifactOrigin,
  ArtifactParent,
  ArtifactView,
  DecisionView,
  JsonObject,
  JsonValue,
  ManuscriptRevisionId,
  RunView,
  RunId,
  AttemptId,
  WorkOfferView,
} from "../contracts/index.ts";
import type {
  ArticleDecisionRequest,
  AuthenticatedHuman,
} from "../contracts/workflow-run.ts";
import { newId } from "../contracts/ids.ts";
import { AuthorizedWorker, type AuthorizedWorkerDescription } from "../authority/local-authority.ts";
import { articleDecisionWaitKey, decisionArtifactId } from "../workflows/article-workflow.ts";
import type {
  ArticleAttemptClaim,
  ArticleAttemptArtifactSeed,
  WorkflowDurableContext,
  WorkflowAttemptContext,
  WorkflowWaitContext,
} from "../workflows/internal-types.ts";
import {
  assertArticleExecutionMaterials,
  assertPrincipalExposureIsolated,
  type ArticleMaterialAccess,
  type ArticleMaterialSet,
  SourceExposureConflictError,
} from "../article-production/materials.ts";
import {
  articleRevisionContextParents,
  articleRevisionRecordParents,
  parseArticleRevisionContext,
  parseArticleRevisionRecord,
  type ArticleRevisionContext,
  type ArticleRevisionRecord,
} from "../article-production/revision.ts";
import {
  articleDecisionTaskSchema,
  articleEditorDecisionSchema,
  articleReviewRouteSchema,
  revisionBriefParents,
  revisionBriefSchema,
  validateArticleEditorDecision,
  validatedArticleEditorDecision,
  type ArticleDecisionTask,
  type ArticleDecisionBudgetSnapshot,
  type ArticleEditorDecision,
  type ArticleFindingId,
  type ArticleReviewRoute,
  type RevisionBrief,
  type ValidatedArticleEditorDecision,
} from "../article-production/review-cycle.ts";
import type { HumanDecisionAuthority } from "./human-decisions.ts";

export type LedgerPayload =
  | { readonly kind: "text"; readonly text: string }
  | { readonly kind: "json"; readonly value: JsonValue }
  | { readonly kind: "bytes"; readonly bytes: Uint8Array };

/** Operational time used only for attempt leases and fencing. */
export type OperationalLeaseClock = {
  readonly nowMs: () => number;
};

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
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly editionId?: string;
  readonly workflowVersion: string;
  readonly loopsRunId: string;
  readonly manuscriptArtifactId: ArtifactId;
  /** The immutable package record currently selected for this article run. */
  readonly currentRevisionRecordArtifactId?: ArtifactId;
  readonly measurementArtifactId?: ArtifactId;
  readonly decisionArtifactId?: ArtifactId;
  readonly promotionId?: string;
  readonly args: JsonObject;
  readonly argsDigest: string;
  readonly workflowPin?: JsonObject;
  readonly loopsContext?: WorkflowDurableContext;
};

export type ArticleAttemptClaimInput = {
  readonly articleExecutionId: ArticleExecutionId;
  readonly rootRunId: RunId;
  readonly articleId: string;
  readonly operationKey: string;
  readonly role: "model" | "tool";
  readonly access: "source_aware" | "source_blind" | "tool";
  readonly manuscriptArtifactId: ArtifactId;
  readonly operationInputDigest: string;
  readonly principalId: string;
  readonly credentialProfileId: string;
  readonly authority: "model" | "tool";
  readonly capabilities: readonly string[];
  readonly durableContext: WorkflowAttemptContext;
  readonly leaseMs?: number;
};

export type ArticleAttemptCommit =
  | { readonly selected: true; readonly status: "selected" | "already_selected"; readonly artifactIds: readonly ArtifactId[] }
  | { readonly selected: false; readonly status: "stale" | "already_selected"; readonly artifactIds: readonly [] };

type ArticleAttemptStoreInternal = {
  readonly requireArtifact: (artifactId: ArtifactId) => LedgerArtifact;
  readonly registerManuscriptRevision: (input: { readonly manuscriptArtifactId: ArtifactId; readonly articleId: string }) => ManuscriptRevisionId;
  readonly claimArticleAttempt: (input: ArticleAttemptClaimInput) => ArticleAttemptClaim;
  readonly heartbeatArticleAttempt: (claim: ArticleAttemptClaim) => ArticleAttemptClaim;
  readonly createArticleAttemptArtifact: (input: {
    readonly claim: ArticleAttemptClaim;
    readonly key: string;
    readonly artifact: Omit<LedgerArtifactInput, "id" | "runId" | "durableContext">;
  }) => LedgerArtifact;
  readonly completeArticleAttempt: (claim: ArticleAttemptClaim, artifactIds: readonly ArtifactId[]) => ArticleAttemptCommit;
  readonly readSelectedArticleAttempt: (input: {
    readonly articleExecutionId: ArticleExecutionId;
    readonly operationKey: string;
    readonly operationInputDigest: string;
  }) => readonly LedgerArtifact[] | undefined;
  readonly failArticleAttempt: (claim: ArticleAttemptClaim) => void;
};

export type ArticleAttemptRequest = {
  readonly rootRunId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly operationKey: string;
  readonly manuscriptArtifactId: ArtifactId;
  /** Deprecated caller hint. The runner derives and verifies this from the artifact. */
  readonly manuscriptRevisionId?: string;
  readonly access: Extract<ArticleMaterialAccess, "source_aware" | "source_blind" | "tool">;
  readonly materials: ArticleMaterialSet;
  readonly leaseMs?: number;
};

export type ArticleAttemptOperationInput = {
  readonly claim: ArticleAttemptClaim;
  readonly materials: ArticleMaterialSet;
};

export type ArticleAttemptOperationResult<T> = {
  readonly value: T;
  readonly artifacts?: readonly ArticleAttemptArtifactSeed[];
};

/** Inputs for the one atomic writer-revision finalization seam. */
export type ArticleRevisionFinalizeInput = {
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly operationKey: string;
  readonly operationInputDigest: string;
  readonly previousManuscriptArtifactId: ArtifactId;
  readonly previousRevisionRecordArtifactId: ArtifactId;
  readonly targetOrdinal: number;
  readonly cycleId: string;
  readonly rewriteOrdinal: number;
  readonly trigger: "auto_rewrite" | "editor_revise";
  readonly revisionContextArtifactId: ArtifactId;
  readonly writerArtifactIds: readonly ArtifactId[];
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  /** The closed-writer contract pinned by the selected operation. */
  readonly writerExecutionClass: "closed_writer/1";
  readonly writerRuntimeIdentity: JsonObject;
  /** Exact ordered package consumed by the closed writer. */
  readonly expectedWriterInputArtifactIds: readonly ArtifactId[];
  /** The immutable writer output contract declared by the resolved profile. */
  readonly declaredWriterReviewMaterials: readonly {
    readonly materialId: string;
    readonly schemaVersion: string;
    readonly required: boolean;
  }[];
  readonly durableContext?: WorkflowAttemptContext;
};

/** Inputs for the first immutable writer revision produced from source evidence. */
export type ArticleInitialRevisionFinalizeInput = {
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly operationKey: string;
  readonly operationInputDigest: string;
  /** Imported source manuscript used only as writer input, never as accepted prose. */
  readonly sourceManuscriptArtifactId: ArtifactId;
  readonly writerArtifactIds: readonly ArtifactId[];
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  /** The closed-writer contract pinned by the selected operation. */
  readonly writerExecutionClass: "closed_writer/1";
  readonly writerRuntimeIdentity: JsonObject;
  /** Exact ordered package consumed by the closed writer. */
  readonly expectedWriterInputArtifactIds: readonly ArtifactId[];
  /** The immutable writer output contract declared by the resolved profile. */
  readonly declaredWriterReviewMaterials: readonly {
    readonly materialId: string;
    readonly schemaVersion: string;
    readonly required: boolean;
  }[];
  readonly durableContext?: WorkflowAttemptContext;
};

export type ArticleRevisionFinalizeResult = {
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  readonly ordinal: number;
  readonly writerOperationKey: string;
  readonly writerOperationInputDigest: string;
  readonly writerReviewMaterialArtifacts: Readonly<Record<string, ArtifactId>>;
  readonly adopted?: boolean;
};

export type ArticleAttemptOperation<T> = (
  input: ArticleAttemptOperationInput,
) => Promise<ArticleAttemptOperationResult<T>> | ArticleAttemptOperationResult<T>;

export type ArticleAttemptExecutionResult<T> = {
  readonly selected: true;
  readonly value: T;
  readonly adopted?: false;
  readonly claim: ArticleAttemptClaim;
  readonly artifacts: readonly LedgerArtifact[];
} | {
  readonly selected: true;
  readonly adopted: true;
  readonly claim?: ArticleAttemptClaim;
  readonly artifacts: readonly LedgerArtifact[];
} | {
  readonly selected: false;
  readonly reason: "already_selected" | "stale";
  readonly claim?: ArticleAttemptClaim;
  readonly artifacts: readonly LedgerArtifact[];
};

export type LedgerOffer = {
  readonly id: string;
  readonly runId: RunId;
  readonly role: "article_decision";
  readonly status: "active" | "answered";
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly allowedChoices: readonly ("accept" | "revise" | "drop")[];
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
  readonly choice: "accept" | "revise" | "drop";
  readonly rationale: string;
  readonly approvedFindingIds?: readonly string[];
  readonly additionalRewriteBudget?: number;
  /** Validation facts are immutable authority, not a recomputed view. */
  readonly validatorVersion?: string;
  readonly canonicalApprovedFindingIds?: readonly ArticleFindingId[];
  readonly rewriteBudget?: ArticleDecisionBudgetSnapshot;
  readonly artifactId: ArtifactId;
  readonly durableContext?: WorkflowWaitContext;
  readonly createdAt: string;
};

type ArticleEditorDecisionRecordInput = Omit<LedgerDecision, "createdAt" | "durableContext" | "validatorVersion" | "canonicalApprovedFindingIds" | "rewriteBudget"> & {
  readonly durableContext: WorkflowWaitContext;
  readonly createdAt?: string;
};

type ArticleEditorDecisionAuthorityFacts = {
  readonly task: ArticleDecisionTask;
  readonly brief: RevisionBrief;
  readonly route: ArticleReviewRoute;
  readonly validation: ValidatedArticleEditorDecision;
};

type HumanDecisionPersistenceInput = {
  readonly decision: ArticleEditorDecisionRecordInput;
  readonly artifact: LedgerArtifactInput;
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
  readonly article_execution_id: ArticleExecutionId | null;
  readonly article_id: string;
  readonly edition_id: string | null;
  readonly workflow_version: string;
  readonly loops_run_id: string;
  readonly manuscript_artifact_id: ArtifactId;
  readonly current_revision_record_artifact_id: ArtifactId | null;
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
  readonly #attemptClock: OperationalLeaseClock;
  readonly #articleAttemptLeaseMs: number;

  constructor(
    databasePath: string,
    options: {
      readonly clock?: { readonly now: () => Date };
      readonly attemptClock?: OperationalLeaseClock;
      readonly articleAttemptLeaseMs?: number;
    } = {},
  ) {
    mkdirSync(dirname(resolve(databasePath)), { recursive: true, mode: 0o700 });
    this.#db = new Database(resolve(databasePath));
    this.#db.pragma("foreign_keys = ON");
    this.#db.pragma("journal_mode = WAL");
    this.#db.pragma("synchronous = FULL");
    this.#clock = options.clock ?? { now: () => new Date() };
    // Lease/fencing time is operational wall-clock time. It must continue to
    // move even when callers inject a frozen domain clock for deterministic
    // artifact timestamps.
    this.#attemptClock = options.attemptClock ?? { nowMs: () => Date.now() };
    const initialAttemptNow = this.#attemptClock.nowMs();
    if (!Number.isSafeInteger(initialAttemptNow) || initialAttemptNow < 0) {
      throw new ArtifactLedgerError("ATTEMPT_INVALID", "Operational lease clock must return a non-negative safe integer");
    }
    this.#articleAttemptLeaseMs = options.articleAttemptLeaseMs ?? 5 * 60_000;
    if (!Number.isSafeInteger(this.#articleAttemptLeaseMs) || this.#articleAttemptLeaseMs <= 0) {
      throw new ArtifactLedgerError("ATTEMPT_INVALID", "Article attempt lease must be a positive integer");
    }
    this.#applySchema();
  }

  close(): void {
    this.#db.close();
  }

  /**
   * Return the authenticated article-attempt facade. The persistence port is
   * captured here in closures over private ledger methods; it is never exposed
   * as a property, symbol, or caller-supplied identity store.
   */
  createArticleAttemptRunner(): ArticleAttemptRunner {
    return new ArticleAttemptRunner(articleAttemptRunnerToken, {
      requireArtifact: (artifactId) => this.requireArtifact(artifactId),
      registerManuscriptRevision: (input) => this.#registerManuscriptRevision(input),
      claimArticleAttempt: (input) => this.#claimArticleAttempt(input),
      heartbeatArticleAttempt: (claim) => this.#heartbeatArticleAttempt(claim),
      createArticleAttemptArtifact: (input) => this.#createArticleAttemptArtifact(input),
      completeArticleAttempt: (claim, artifactIds) => this.#completeArticleAttempt(claim, artifactIds),
      readSelectedArticleAttempt: (input) => this.#readSelectedArticleAttempt(input),
      failArticleAttempt: (claim) => this.#failArticleAttempt(claim),
    });
  }

  /**
   * Return the only public human-decision seam. The decision authority keeps
   * the persistence capability in this module-private closure, just like the
   * article-attempt runner above. Callers receive validation and decision
   * methods, never a ledger writer or caller-supplied identity port.
   */
  createHumanDecisionAuthority(options: {
    readonly clock?: { readonly now: () => Date };
  } = {}): HumanDecisionAuthority {
    const clock = options.clock ?? this.#clock;
    return new HumanDecisionAuthorityImpl(
      humanDecisionAuthorityToken,
      this,
      (input) => this.#recordValidatedEditorDecision(input),
      clock,
    );
  }

  createRun(input: {
    readonly runId: RunId;
    readonly articleExecutionId?: ArticleExecutionId;
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
    const articleExecutionId = input.articleExecutionId ?? (`article-execution-${safeIdentity(input.runId)}` as ArticleExecutionId);
    const existing = this.#db.prepare("SELECT * FROM magazine_runs WHERE run_id = ?").get(input.runId) as RunRow | undefined;
    if (existing !== undefined) {
      if (
        (existing.article_execution_id ?? (`article-execution-${safeIdentity(existing.run_id)}` as ArticleExecutionId)) !== articleExecutionId
        ||
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
        run_id, article_execution_id, article_id, edition_id, workflow_version, loops_run_id,
        manuscript_artifact_id, measurement_artifact_id, decision_artifact_id,
        promotion_id, args_digest, args_json, workflow_pin_json, loops_context_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?)`,
    ).run(
      input.runId,
      articleExecutionId,
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

  /** Resolve the root run from the article identity carried by an ID-only worker request. */
  requireRunByArticleExecutionId(articleExecutionId: ArticleExecutionId): LedgerRun {
    const row = this.#db.prepare(
      "SELECT * FROM magazine_runs WHERE article_execution_id = ?",
    ).get(articleExecutionId) as RunRow | undefined;
    if (row === undefined) {
      throw new ArtifactLedgerError("RUN_NOT_FOUND", `Article execution ${articleExecutionId} does not exist`);
    }
    return toRun(row);
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

  /**
   * Atomically select the immutable revision package for a run. The record
   * and all of its parents are validated before the pointer is advanced. A
   * replay of the same transition is idempotent; a different successor must
   * name the exact record currently selected by the caller.
   */
  recordCurrentRevisionRecord(
    runId: RunId,
    revisionRecordArtifactId: ArtifactId,
    expectedPreviousRevisionRecordArtifactId?: ArtifactId,
  ): LedgerRun {
    const run = this.requireRun(runId);
    const record = this.#validateRevisionRecordArtifact(run, revisionRecordArtifactId);
    const current = run.currentRevisionRecordArtifactId;
    if (current === revisionRecordArtifactId) {
      if (record.manuscriptArtifactId !== run.manuscriptArtifactId) {
        throw new ArtifactLedgerError("REVISION_RECORD_POINTER_INVALID", "current revision record does not name the run manuscript");
      }
      return run;
    }
    if (expectedPreviousRevisionRecordArtifactId !== undefined && current !== expectedPreviousRevisionRecordArtifactId) {
      throw new ArtifactLedgerError("REVISION_RECORD_POINTER_STALE", "revision record successor does not name the current package record");
    }
    if (current !== undefined && expectedPreviousRevisionRecordArtifactId === undefined) {
      throw new ArtifactLedgerError("REVISION_RECORD_POINTER_STALE", "revision record successor omitted its current package predecessor");
    }
    if (current !== undefined) {
      const previous = this.#validateRevisionRecordArtifact(run, current);
      if (record.ordinal !== previous.ordinal + 1 || record.previousRevisionRecordArtifactId !== current) {
        throw new ArtifactLedgerError("REVISION_RECORD_POINTER_INVALID", "revision record successor is not the exact next package record");
      }
    } else if (record.ordinal !== 0 || record.previousRevisionRecordArtifactId !== undefined) {
      throw new ArtifactLedgerError("REVISION_RECORD_POINTER_INVALID", "the first revision record must have ordinal zero and no predecessor");
    }
    this.#db.transaction(() => {
      this.#db.prepare(
        `UPDATE magazine_runs
         SET manuscript_artifact_id = ?, current_revision_record_artifact_id = ?, updated_at = ?
         WHERE run_id = ? AND (current_revision_record_artifact_id IS ? OR current_revision_record_artifact_id = ?)` ,
      ).run(
        record.manuscriptArtifactId,
        revisionRecordArtifactId,
        this.#clock.now().toISOString(),
        runId,
        current === undefined ? null : current,
        current ?? "",
      );
      const after = this.#db.prepare("SELECT current_revision_record_artifact_id FROM magazine_runs WHERE run_id = ?").get(runId) as { readonly current_revision_record_artifact_id: ArtifactId | null } | undefined;
      if (after?.current_revision_record_artifact_id !== revisionRecordArtifactId) {
        throw new ArtifactLedgerError("REVISION_RECORD_POINTER_STALE", "revision record pointer advanced concurrently");
      }
    })();
    return this.requireRun(runId);
  }

  /**
   * Commit one immutable writer revision package and advance the run pointer
   * in a single SQLite transaction.  The caller supplies IDs only.  This
   * seam re-validates the selected writer outputs, revision context, and
   * predecessor before it writes anything.  If a previous process committed
   * the exact successor before losing its Loops checkpoint, the successor is
   * adopted.  A different successor or predecessor is a conflict.
   */
  finalizeArticleRevision(input: ArticleRevisionFinalizeInput): ArticleRevisionFinalizeResult {
    const run = this.requireRun(input.runId);
    if (run.articleExecutionId !== input.articleExecutionId || run.articleId !== input.articleId) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_IDENTITY", "article revision finalization is not bound to the exact run");
    }
    if (!Number.isSafeInteger(input.targetOrdinal) || input.targetOrdinal < 1 || input.rewriteOrdinal !== input.targetOrdinal) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_ORDINAL", "article revision finalization has an invalid target ordinal");
    }
    if (input.operationKey.trim().length === 0 || input.operationInputDigest.trim().length === 0) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_INPUT", "article revision finalization requires the exact writer key and digest");
    }
    if (input.writerArtifactIds.length === 0 || new Set(input.writerArtifactIds).size !== input.writerArtifactIds.length) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "article revision finalization requires unique selected writer outputs");
    }
    if (input.writerExecutionClass !== "closed_writer/1" || !isJsonObject(input.writerRuntimeIdentity)) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "article revision finalization requires the pinned closed-writer runtime contract");
    }
    if (
      input.expectedWriterInputArtifactIds.length === 0
      || new Set(input.expectedWriterInputArtifactIds).size !== input.expectedWriterInputArtifactIds.length
      || !input.expectedWriterInputArtifactIds.includes(input.previousManuscriptArtifactId)
      || !input.expectedWriterInputArtifactIds.includes(input.revisionContextArtifactId)
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "article revision finalization requires the exact closed-writer input package");
    }
    const previous = this.#validateRevisionRecordArtifact(run, input.previousRevisionRecordArtifactId);
    if (run.currentRevisionRecordArtifactId !== input.previousRevisionRecordArtifactId) {
      if (run.currentRevisionRecordArtifactId === input.revisionRecordArtifactId) {
        return this.#adoptFinalizedRevision(input, run);
      }
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "article revision predecessor is no longer the current package");
    }
    if (previous.manuscriptArtifactId !== input.previousManuscriptArtifactId || previous.ordinal + 1 !== input.targetOrdinal) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_PREDECESSOR", "article revision predecessor does not match the pinned manuscript and ordinal");
    }
    const context = this.#validateRevisionFinalizeContext(input, run);
    const writer = this.#validateRevisionWriterOutputs(input, run);
    const selectedWriterClaimId = textValue(writer.manuscript.metadata.claimId);
    const record: ArticleRevisionRecord = {
      schemaVersion: "article-revision-record/1",
      ordinal: input.targetOrdinal,
      manuscriptArtifactId: input.manuscriptArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      previousRevisionRecordArtifactId: input.previousRevisionRecordArtifactId,
      revisionContextArtifactId: input.revisionContextArtifactId,
      ...(selectedWriterClaimId === undefined ? {} : { selectedWriterClaimId }),
      selectedWriterOutputArtifactId: writer.manuscript.id,
      ...(writer.workingNotes === undefined ? {} : { workingNotesArtifactId: writer.workingNotes.id }),
      ...(writer.findingDispositions === undefined ? {} : { findingDispositionsArtifactId: writer.findingDispositions.id }),
      reviewMaterialArtifactIds: Object.freeze(writer.reviewMaterials.map((artifact) => artifact.id)),
      humanRulingArtifactIds: Object.freeze([...input.humanRulingArtifactIds]),
      trigger: input.trigger,
    };
    const manuscriptText = Buffer.from(this.readArtifact(writer.manuscript.id).bytes).toString("utf8");
    const manuscriptParents = Object.freeze([
      { artifactId: input.previousManuscriptArtifactId, relation: "previous_manuscript" },
      { artifactId: input.revisionContextArtifactId, relation: "revision_context" },
      { artifactId: writer.manuscript.id, relation: "writer_output" },
    ]);
    const manuscriptInput: LedgerArtifactInput = {
      id: input.manuscriptArtifactId,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "model",
      payload: { kind: "text", text: manuscriptText },
      parents: manuscriptParents,
      metadata: {
        articleId: input.articleId,
        revisionId: input.manuscriptRevisionId,
        manuscriptRevisionId: input.manuscriptRevisionId,
        previousManuscriptArtifactId: input.previousManuscriptArtifactId,
        writerOutputArtifactId: writer.manuscript.id,
        revisionContextArtifactId: input.revisionContextArtifactId,
        previousRevisionId: previous.manuscriptRevisionId,
        ...(selectedWriterClaimId === undefined ? {} : { selectedWriterClaimId }),
        selectedWriterOutputArtifactId: writer.manuscript.id,
        textDigest: `sha256:${createHash("sha256").update(manuscriptText, "utf8").digest("hex")}`,
        operationKey: input.operationKey,
        operationInputDigest: input.operationInputDigest,
        cycleId: input.cycleId,
        rewriteOrdinal: input.rewriteOrdinal,
        inputRevisionRecordArtifactId: input.previousRevisionRecordArtifactId,
      },
      runId: input.runId,
      ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
    };
    const recordInput: LedgerArtifactInput = {
      id: input.revisionRecordArtifactId,
      kind: "article_revision_record",
      schemaVersion: "article-revision-record/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: record as unknown as JsonValue },
      parents: articleRevisionRecordParents(record),
      metadata: {
        articleId: input.articleId,
        manuscriptArtifactId: input.manuscriptArtifactId,
        manuscriptRevisionId: input.manuscriptRevisionId,
        ordinal: input.targetOrdinal,
        trigger: input.trigger,
        revisionContextArtifactId: input.revisionContextArtifactId,
        operationKey: input.operationKey,
        operationInputDigest: input.operationInputDigest,
      },
      runId: input.runId,
      ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
    };
    const transaction = this.#db.transaction(() => {
      this.#insertArtifactWithinTransaction(manuscriptInput);
      this.#insertArtifactWithinTransaction(recordInput);
      const changed = this.#db.prepare(
        `UPDATE magazine_runs
         SET manuscript_artifact_id = ?, current_revision_record_artifact_id = ?, updated_at = ?
         WHERE run_id = ? AND current_revision_record_artifact_id = ?`,
      ).run(input.manuscriptArtifactId, input.revisionRecordArtifactId, this.#clock.now().toISOString(), input.runId, input.previousRevisionRecordArtifactId);
      if (changed.changes !== 1) throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "article revision predecessor changed during finalization");
      const revisionConflict = this.#db.prepare("SELECT revision_id, manuscript_artifact_id, article_id FROM magazine_manuscript_revisions WHERE revision_id = ? OR manuscript_artifact_id = ?").all(input.manuscriptRevisionId, input.manuscriptArtifactId) as readonly ManuscriptRevisionRow[];
      for (const row of revisionConflict) {
        if (row.revision_id !== input.manuscriptRevisionId || row.manuscript_artifact_id !== input.manuscriptArtifactId || row.article_id !== input.articleId) {
          throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "manuscript revision identity is already bound to another artifact");
        }
      }
      if (revisionConflict.length === 0) {
        this.#db.prepare(
          `INSERT INTO magazine_manuscript_revisions(revision_id, manuscript_artifact_id, article_id, registered_at) VALUES (?, ?, ?, ?)`,
        ).run(input.manuscriptRevisionId, input.manuscriptArtifactId, input.articleId, this.#clock.now().toISOString());
      }
      // Re-read inside the transaction to prove the pointer names the exact
      // package that was validated above.
      const after = this.#db.prepare("SELECT current_revision_record_artifact_id, manuscript_artifact_id FROM magazine_runs WHERE run_id = ?").get(input.runId) as { readonly current_revision_record_artifact_id: ArtifactId; readonly manuscript_artifact_id: ArtifactId } | undefined;
      if (after?.current_revision_record_artifact_id !== input.revisionRecordArtifactId || after.manuscript_artifact_id !== input.manuscriptArtifactId) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "article revision pointer did not advance to the exact successor");
      }
    });
    transaction();
    const result = this.#finalizeResult(input, writer.reviewMaterials);
    // Force the same strict validation path used by projection inspection.
    this.#validateRevisionRecordArtifact(this.requireRun(input.runId), input.revisionRecordArtifactId);
    return result;
  }

  /**
   * Commit the first writer-produced manuscript and its package record in one
   * transaction. The imported source manuscript is evidence only; it is
   * never selected as the accepted initial prose.
   */
  finalizeInitialArticleRevision(input: ArticleInitialRevisionFinalizeInput): ArticleRevisionFinalizeResult {
    const run = this.requireRun(input.runId);
    if (run.articleExecutionId !== input.articleExecutionId || run.articleId !== input.articleId) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_IDENTITY", "initial article revision finalization is not bound to the exact run");
    }
    if (run.manuscriptArtifactId !== input.sourceManuscriptArtifactId) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_PREDECESSOR", "initial article revision must start from the imported source manuscript");
    }
    if (input.operationKey.trim().length === 0 || input.operationInputDigest.trim().length === 0) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_INPUT", "initial article revision finalization requires the exact writer key and digest");
    }
    if (input.writerArtifactIds.length === 0 || new Set(input.writerArtifactIds).size !== input.writerArtifactIds.length) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "initial article revision finalization requires unique selected writer outputs");
    }
    if (input.writerExecutionClass !== "closed_writer/1" || !isJsonObject(input.writerRuntimeIdentity)) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "initial article revision finalization requires the pinned closed-writer runtime contract");
    }
    if (input.expectedWriterInputArtifactIds.length === 0 || new Set(input.expectedWriterInputArtifactIds).size !== input.expectedWriterInputArtifactIds.length || !input.expectedWriterInputArtifactIds.includes(input.sourceManuscriptArtifactId)) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "initial article revision finalization requires the exact source writer input package");
    }
    if (run.currentRevisionRecordArtifactId !== undefined) {
      if (run.currentRevisionRecordArtifactId !== input.revisionRecordArtifactId) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "initial article revision predecessor is no longer the empty package");
      }
      return this.#adoptInitialFinalizedRevision(input, run);
    }
    const writer = this.#validateRevisionWriterOutputs(input, run);
    const selectedWriterClaimId = textValue(writer.manuscript.metadata.claimId);
    const record: ArticleRevisionRecord = {
      schemaVersion: "article-revision-record/1",
      ordinal: 0,
      manuscriptArtifactId: input.manuscriptArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      ...(selectedWriterClaimId === undefined ? {} : { selectedWriterClaimId }),
      selectedWriterOutputArtifactId: writer.manuscript.id,
      workingNotesArtifactId: writer.workingNotes.id,
      findingDispositionsArtifactId: writer.findingDispositions.id,
      reviewMaterialArtifactIds: Object.freeze(writer.reviewMaterials.map((artifact) => artifact.id)),
      humanRulingArtifactIds: Object.freeze([]),
      trigger: "initial",
    };
    const manuscriptText = Buffer.from(this.readArtifact(writer.manuscript.id).bytes).toString("utf8");
    const manuscriptInput: LedgerArtifactInput = {
      id: input.manuscriptArtifactId,
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "model",
      payload: { kind: "text", text: manuscriptText },
      parents: [
        { artifactId: input.sourceManuscriptArtifactId, relation: "initial_source_manuscript" },
        { artifactId: writer.manuscript.id, relation: "writer_output" },
      ],
      metadata: {
        articleId: input.articleId,
        revisionId: input.manuscriptRevisionId,
        manuscriptRevisionId: input.manuscriptRevisionId,
        sourceManuscriptArtifactId: input.sourceManuscriptArtifactId,
        writerOutputArtifactId: writer.manuscript.id,
        ...(selectedWriterClaimId === undefined ? {} : { selectedWriterClaimId }),
        selectedWriterOutputArtifactId: writer.manuscript.id,
        textDigest: `sha256:${createHash("sha256").update(manuscriptText, "utf8").digest("hex")}`,
        operationKey: input.operationKey,
        operationInputDigest: input.operationInputDigest,
        writerInputArtifactIds: input.expectedWriterInputArtifactIds as unknown as JsonValue,
      },
      runId: input.runId,
      ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
    };
    const recordInput: LedgerArtifactInput = {
      id: input.revisionRecordArtifactId,
      kind: "article_revision_record",
      schemaVersion: "article-revision-record/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: record as unknown as JsonValue },
      parents: articleRevisionRecordParents(record),
      metadata: {
        articleId: input.articleId,
        manuscriptArtifactId: input.manuscriptArtifactId,
        manuscriptRevisionId: input.manuscriptRevisionId,
        ordinal: 0,
        trigger: "initial",
        operationKey: input.operationKey,
        operationInputDigest: input.operationInputDigest,
      },
      runId: input.runId,
      ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
    };
    const transaction = this.#db.transaction(() => {
      this.#insertArtifactWithinTransaction(manuscriptInput);
      this.#insertArtifactWithinTransaction(recordInput);
      const changed = this.#db.prepare(
        `UPDATE magazine_runs
         SET manuscript_artifact_id = ?, current_revision_record_artifact_id = ?, updated_at = ?
         WHERE run_id = ? AND manuscript_artifact_id = ? AND current_revision_record_artifact_id IS NULL`,
      ).run(input.manuscriptArtifactId, input.revisionRecordArtifactId, this.#clock.now().toISOString(), input.runId, input.sourceManuscriptArtifactId);
      if (changed.changes !== 1) throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "initial article revision pointer advanced concurrently");
      const revisionConflict = this.#db.prepare("SELECT revision_id, manuscript_artifact_id, article_id FROM magazine_manuscript_revisions WHERE revision_id = ? OR manuscript_artifact_id = ?").all(input.manuscriptRevisionId, input.manuscriptArtifactId) as readonly ManuscriptRevisionRow[];
      for (const row of revisionConflict) {
        if (row.revision_id !== input.manuscriptRevisionId || row.manuscript_artifact_id !== input.manuscriptArtifactId || row.article_id !== input.articleId) {
          throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "initial manuscript revision identity is already bound to another artifact");
        }
      }
      if (revisionConflict.length === 0) {
        this.#db.prepare(
          `INSERT INTO magazine_manuscript_revisions(revision_id, manuscript_artifact_id, article_id, registered_at) VALUES (?, ?, ?, ?)`,
        ).run(input.manuscriptRevisionId, input.manuscriptArtifactId, input.articleId, this.#clock.now().toISOString());
      }
      const after = this.#db.prepare("SELECT current_revision_record_artifact_id, manuscript_artifact_id FROM magazine_runs WHERE run_id = ?").get(input.runId) as { readonly current_revision_record_artifact_id: ArtifactId; readonly manuscript_artifact_id: ArtifactId } | undefined;
      if (after?.current_revision_record_artifact_id !== input.revisionRecordArtifactId || after.manuscript_artifact_id !== input.manuscriptArtifactId) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "initial article revision pointer did not advance to the exact successor");
      }
    });
    transaction();
    this.#validateRevisionRecordArtifact(this.requireRun(input.runId), input.revisionRecordArtifactId);
    return this.#initialFinalizeResult(input, writer.reviewMaterials);
  }

  #adoptInitialFinalizedRevision(input: ArticleInitialRevisionFinalizeInput, run: LedgerRun): ArticleRevisionFinalizeResult {
    const writer = this.#validateRevisionWriterOutputs(input, run);
    const record = this.#validateRevisionRecordArtifact(run, input.revisionRecordArtifactId);
    if (
      record.ordinal !== 0
      || record.trigger !== "initial"
      || record.previousRevisionRecordArtifactId !== undefined
      || record.revisionContextArtifactId !== undefined
      || record.manuscriptArtifactId !== input.manuscriptArtifactId
      || record.manuscriptRevisionId !== input.manuscriptRevisionId
      || record.selectedWriterOutputArtifactId !== writer.manuscript.id
      || record.workingNotesArtifactId !== writer.workingNotes.id
      || record.findingDispositionsArtifactId !== writer.findingDispositions.id
      || !sameStrings(record.reviewMaterialArtifactIds, writer.reviewMaterials.map((artifact) => artifact.id))
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "persisted initial revision package does not match the exact selected writer outputs");
    }
    const manuscript = this.requireArtifact(input.manuscriptArtifactId);
    if (
      manuscript.metadata.operationKey !== input.operationKey
      || manuscript.metadata.operationInputDigest !== input.operationInputDigest
      || manuscript.metadata.sourceManuscriptArtifactId !== input.sourceManuscriptArtifactId
      || manuscript.metadata.writerOutputArtifactId !== writer.manuscript.id
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "persisted initial manuscript does not match the exact writer transition");
    }
    return this.#initialFinalizeResult(input, writer.reviewMaterials, true);
  }

  #adoptFinalizedRevision(input: ArticleRevisionFinalizeInput, run: LedgerRun): ArticleRevisionFinalizeResult {
    const writer = this.#validateRevisionWriterOutputs(input, run);
    this.#validateRevisionFinalizeContext(input, run);
    const record = this.#validateRevisionRecordArtifact(run, input.revisionRecordArtifactId);
    if (
      record.previousRevisionRecordArtifactId !== input.previousRevisionRecordArtifactId
      || record.manuscriptArtifactId !== input.manuscriptArtifactId
      || record.manuscriptRevisionId !== input.manuscriptRevisionId
      || record.ordinal !== input.targetOrdinal
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "persisted revision successor does not match the exact pinned transition");
    }
    const manuscript = this.requireArtifact(input.manuscriptArtifactId);
    if (manuscript.metadata.operationKey !== input.operationKey || manuscript.metadata.operationInputDigest !== input.operationInputDigest || manuscript.metadata.previousManuscriptArtifactId !== input.previousManuscriptArtifactId || manuscript.metadata.revisionContextArtifactId !== input.revisionContextArtifactId) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "persisted manuscript successor does not match the exact writer transition");
    }
    if (
      record.selectedWriterOutputArtifactId !== writer.manuscript.id
      || record.workingNotesArtifactId !== writer.workingNotes.id
      || record.findingDispositionsArtifactId !== writer.findingDispositions.id
      || !sameStrings(record.reviewMaterialArtifactIds, writer.reviewMaterials.map((artifact) => artifact.id))
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONFLICT", "persisted revision record does not match the exact selected writer outputs");
    }
    const writerMaterials = record.reviewMaterialArtifactIds.reduce<Record<string, ArtifactId>>((map, artifactId) => {
      const material = this.requireArtifact(artifactId);
      const materialId = textValue(material.metadata.materialId);
      if (materialId !== undefined) map[materialId] = artifactId;
      return map;
    }, {});
    return this.#finalizeResult(input, writer.reviewMaterials, true, writerMaterials);
  }

  #finalizeResult(
    input: ArticleRevisionFinalizeInput,
    reviewMaterials: readonly LedgerArtifact[],
    adopted = false,
    suppliedMap?: Readonly<Record<string, ArtifactId>>,
  ): ArticleRevisionFinalizeResult {
    const writerReviewMaterialArtifacts = suppliedMap ?? reviewMaterials.reduce<Record<string, ArtifactId>>((map, artifact) => {
      const materialId = textValue(artifact.metadata.materialId);
      if (materialId !== undefined) map[materialId] = artifact.id;
      return map;
    }, {});
    return {
      manuscriptArtifactId: input.manuscriptArtifactId,
      revisionRecordArtifactId: input.revisionRecordArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      ordinal: input.targetOrdinal,
      writerOperationKey: input.operationKey,
      writerOperationInputDigest: input.operationInputDigest,
      writerReviewMaterialArtifacts: Object.freeze({ ...writerReviewMaterialArtifacts }),
      ...(adopted ? { adopted: true } : {}),
    };
  }

  #initialFinalizeResult(
    input: ArticleInitialRevisionFinalizeInput,
    reviewMaterials: readonly LedgerArtifact[],
    adopted = false,
  ): ArticleRevisionFinalizeResult {
    const writerReviewMaterialArtifacts = reviewMaterials.reduce<Record<string, ArtifactId>>((map, artifact) => {
      const materialId = textValue(artifact.metadata.materialId);
      if (materialId !== undefined) map[materialId] = artifact.id;
      return map;
    }, {});
    return {
      manuscriptArtifactId: input.manuscriptArtifactId,
      revisionRecordArtifactId: input.revisionRecordArtifactId,
      manuscriptRevisionId: input.manuscriptRevisionId,
      ordinal: 0,
      writerOperationKey: input.operationKey,
      writerOperationInputDigest: input.operationInputDigest,
      writerReviewMaterialArtifacts: Object.freeze({ ...writerReviewMaterialArtifacts }),
      ...(adopted ? { adopted: true } : {}),
    };
  }

  #validateRevisionFinalizeContext(input: ArticleRevisionFinalizeInput, run: LedgerRun): ArticleRevisionContext {
    const artifact = this.requireArtifact(input.revisionContextArtifactId);
    if (artifact.kind !== "article_revision_context" || artifact.schemaVersion !== "article-revision-context/1" || artifact.mediaType !== "application/json" || artifact.payloadKind !== "json" || artifact.producingRunId !== run.runId) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONTEXT", "revision finalization context is not an exact run-owned artifact");
    }
    let value: ArticleRevisionContext;
    try {
      value = parseArticleRevisionContext(JSON.parse(Buffer.from(this.readArtifact(artifact.id).bytes).toString("utf8")));
    } catch (error) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONTEXT", "revision finalization context is malformed", { cause: error });
    }
    if (
      value.articleExecutionId !== input.articleExecutionId
      || value.cycleId !== input.cycleId
      || value.rewriteOrdinal !== input.rewriteOrdinal
      || value.trigger !== input.trigger
      || value.previousManuscriptArtifactId !== input.previousManuscriptArtifactId
      || artifact.metadata.articleExecutionId !== input.articleExecutionId
      || artifact.metadata.cycleId !== input.cycleId
      || artifact.metadata.rewriteOrdinal !== input.rewriteOrdinal
      || !sameParents(artifact.parents, articleRevisionContextParents(value))
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_CONTEXT", "revision finalization context is not pinned to the exact predecessor and cycle");
    }
    return value;
  }

  #validateRevisionWriterOutputs(input: ArticleRevisionFinalizeInput | ArticleInitialRevisionFinalizeInput, run: LedgerRun): {
    readonly manuscript: LedgerArtifact;
    readonly workingNotes: LedgerArtifact;
    readonly findingDispositions: LedgerArtifact;
    readonly reviewMaterials: readonly LedgerArtifact[];
  } {
    const artifacts = input.writerArtifactIds.map((artifactId) => this.requireArtifact(artifactId));
    if (artifacts.length < 3) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer finalization requires manuscript, working notes, and finding dispositions");
    }

    // The selected operation row is the authority for output order and the
    // winning claim. A caller cannot supply a plausible-looking artifact list
    // without also naming the exact completed attempt that selected it.
    const selection = this.#db.prepare(
      `SELECT claim_id, artifact_ids_json, operation_input_digest
       FROM magazine_article_operation_selections
       WHERE article_execution_id = ? AND operation_key = ?`,
    ).get(input.articleExecutionId, input.operationKey) as {
      readonly claim_id: AttemptId;
      readonly artifact_ids_json: string;
      readonly operation_input_digest: string | null;
    } | undefined;
    if (selection === undefined || selection.operation_input_digest !== input.operationInputDigest) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer operation has no exact selected operation record");
    }
    let selectedArtifactIds: readonly ArtifactId[];
    try {
      const parsed = JSON.parse(selection.artifact_ids_json) as unknown;
      if (!Array.isArray(parsed) || parsed.some((value) => typeof value !== "string" || value.length === 0)) throw new Error("invalid artifact list");
      selectedArtifactIds = parsed as ArtifactId[];
    } catch (error) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "selected writer operation has malformed artifact order", { cause: error });
    }
    if (!sameStrings(selectedArtifactIds, input.writerArtifactIds)) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer outputs are not in the exact selected operation order");
    }
    if (new Set(selectedArtifactIds).size !== selectedArtifactIds.length) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "selected writer operation repeats an output artifact");
    }
    const initial = "sourceManuscriptArtifactId" in input;
    const predecessorManuscriptArtifactId = initial ? input.sourceManuscriptArtifactId : input.previousManuscriptArtifactId;
    const claim = this.#db.prepare("SELECT * FROM magazine_article_attempts WHERE claim_id = ?").get(selection.claim_id) as ArticleAttemptRow | undefined;
    if (
      claim === undefined
      || claim.status !== "completed"
      || claim.article_execution_id !== input.articleExecutionId
      || claim.run_id !== run.runId
      || claim.article_id !== input.articleId
      || claim.operation_key !== input.operationKey
      || claim.operation_input_digest !== input.operationInputDigest
      || claim.manuscript_artifact_id !== predecessorManuscriptArtifactId
      || claim.role !== "model"
      || claim.access !== "source_aware"
      || claim.authority !== "model"
    ) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer operation selection is not bound to a completed source-aware model claim");
    }
    let claimArtifactIds: readonly ArtifactId[];
    try {
      const parsed = claim.output_artifact_ids_json === null ? undefined : JSON.parse(claim.output_artifact_ids_json) as unknown;
      if (!Array.isArray(parsed) || parsed.some((value) => typeof value !== "string" || value.length === 0)) throw new Error("invalid claim artifact list");
      claimArtifactIds = parsed as ArtifactId[];
    } catch (error) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer claim has malformed output artifacts", { cause: error });
    }
    if (!sameStrings(claimArtifactIds, selectedArtifactIds)) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "selected operation row and claim output order disagree");
    }

    const declarations = new Map<string, { readonly schemaVersion: string; readonly required: boolean }>();
    for (const declaration of input.declaredWriterReviewMaterials) {
      if (textValue(declaration.materialId) === undefined || textValue(declaration.schemaVersion) === undefined || declarations.has(declaration.materialId) || typeof declaration.required !== "boolean") {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer review material declarations are malformed or duplicated");
      }
      declarations.set(declaration.materialId, declaration);
    }
    const expectedParents = input.expectedWriterInputArtifactIds.map((artifactId) => ({ artifactId, relation: "writer_input" }));
    for (const parent of expectedParents) this.requireArtifact(parent.artifactId);
    for (const artifact of artifacts) {
      const claimId = textValue(artifact.metadata.claimId);
      const attemptId = textValue(artifact.metadata.attemptId);
      const operationKey = textValue(artifact.metadata.operationKey);
      const operationInputDigest = textValue(artifact.metadata.operationInputDigest);
      const articleExecutionId = textValue(artifact.metadata.articleExecutionId);
      const loopsRunId = textValue(artifact.metadata.loopsRunId);
      const attemptNumber = artifact.metadata.attemptNumber;
      const writerExecutionClass = textValue(artifact.metadata.writerExecutionClass);
      const writerRuntimeIdentity = artifact.metadata.writerRuntimeIdentity;
      const revisionContextArtifactId = textValue(artifact.metadata.revisionContextArtifactId);
      const writerInputArtifactIds = readArtifactIdArray(artifact.metadata.writerInputArtifactIds);
      if (
        artifact.producingRunId !== run.runId
        || artifact.metadata.articleId !== input.articleId
        || operationKey !== input.operationKey
        || operationInputDigest !== input.operationInputDigest
        || articleExecutionId !== input.articleExecutionId
        || claimId !== selection.claim_id
        || attemptId !== claim.attempt_id
        || loopsRunId !== run.loopsRunId
        || !Number.isSafeInteger(attemptNumber)
        || attemptNumber !== claim.attempt_number
        || writerExecutionClass !== input.writerExecutionClass
        || !isDeepStrictEqual(writerRuntimeIdentity, input.writerRuntimeIdentity)
        || (initial ? revisionContextArtifactId !== undefined : revisionContextArtifactId !== input.revisionContextArtifactId)
        || !sameStrings(writerInputArtifactIds, input.expectedWriterInputArtifactIds)
        || !sameParents(artifact.parents, expectedParents)
      ) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer output is not bound to the exact selected claim, attempt, operation, or parent set");
      }
    }
    const manuscript = artifacts[0]!;
    const workingNotes = artifacts[1]!;
    const findingDispositions = artifacts[2]!;
    if (manuscript.kind !== "article_manuscript" || manuscript.schemaVersion !== "article-manuscript/1" || manuscript.mediaType !== "text/markdown" || manuscript.payloadKind !== "text") {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer finalization requires a Markdown manuscript output first");
    }
    if (workingNotes.kind !== "writer_working_notes" || workingNotes.schemaVersion !== "writer-working-notes/1" || workingNotes.mediaType !== "text/plain" || workingNotes.payloadKind !== "text") {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer finalization requires one working-notes output second");
    }
    if (findingDispositions.kind !== "writer_finding_dispositions" || findingDispositions.schemaVersion !== "writer-finding-dispositions/1" || findingDispositions.mediaType !== "application/json" || findingDispositions.payloadKind !== "json") {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer finalization requires one finding-dispositions output third");
    }
    let dispositionValue: unknown;
    try { dispositionValue = JSON.parse(Buffer.from(this.readArtifact(findingDispositions.id).bytes).toString("utf8")); } catch (error) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer finding dispositions are not valid JSON", { cause: error });
    }
    if (typeof dispositionValue !== "object" || dispositionValue === null || (dispositionValue as { readonly schemaVersion?: unknown }).schemaVersion !== "writer-finding-dispositions/1" || !Array.isArray((dispositionValue as { readonly dispositions?: unknown }).dispositions)) {
      throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer finding dispositions do not match their pinned schema");
    }
    const reviewMaterials = artifacts.slice(3);
    const seenMaterialIds = new Set<string>();
    for (const artifact of reviewMaterials) {
      if (artifact.kind !== "writer_review_material" || artifact.schemaVersion !== "writer-review-material/1" || artifact.mediaType !== "application/json" || artifact.payloadKind !== "json") {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer review material output has the wrong kind, schema, or media type");
      }
      const materialId = textValue(artifact.metadata.materialId);
      const materialSchemaVersion = textValue(artifact.metadata.materialSchemaVersion);
      const declaration = materialId === undefined ? undefined : declarations.get(materialId);
      if (materialId === undefined || materialSchemaVersion === undefined || declaration === undefined || materialSchemaVersion !== declaration.schemaVersion || seenMaterialIds.has(materialId)) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer review material is missing an exact declared identity");
      }
      let payload: unknown;
      try { payload = JSON.parse(Buffer.from(this.readArtifact(artifact.id).bytes).toString("utf8")); } catch (error) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer review material is not valid JSON", { cause: error });
      }
      if (typeof payload !== "object" || payload === null || (payload as { readonly materialId?: unknown }).materialId !== materialId || (payload as { readonly schemaVersion?: unknown }).schemaVersion !== materialSchemaVersion) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", "writer review material payload does not match its declaration");
      }
      seenMaterialIds.add(materialId);
    }
    for (const [materialId, declaration] of declarations) {
      if (declaration.required && !seenMaterialIds.has(materialId)) {
        throw new ArtifactLedgerError("REVISION_FINALIZE_OUTPUTS", `writer omitted required review material ${materialId}`);
      }
    }
    return {
      manuscript,
      workingNotes,
      findingDispositions,
      reviewMaterials: Object.freeze(reviewMaterials),
    };
  }

  #insertArtifactWithinTransaction(input: LedgerArtifactInput): LedgerArtifact {
    const payload = encodePayload(input.payload);
    const metadata = { ...(input.metadata ?? {}), ...(input.durableContext === undefined ? {} : { durableContext: contextObject(input.durableContext) }) };
    const parents = input.parents ?? [];
    const existing = this.#db.prepare("SELECT * FROM magazine_artifacts WHERE id = ?").get(input.id) as ArtifactRow | undefined;
    if (existing !== undefined) {
      if (!sameArtifact(existing, input, payload, metadata, parents, this.parentRows(input.id))) {
        throw new ArtifactLedgerError("ARTIFACT_ID_COLLISION", `Artifact ${input.id} already exists with different immutable content`);
      }
      return this.requireArtifact(input.id);
    }
    for (const parent of parents) this.requireArtifact(parent.artifactId);
    const createdAt = this.#clock.now().toISOString();
    this.#db.prepare(
      `INSERT INTO magazine_artifacts(id, kind, schema_version, media_type, origin, payload_kind, payload, metadata_json, durable_context_json, run_id, created_at, digest)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(input.id, input.kind, input.schemaVersion, input.mediaType, input.origin, input.payload.kind, payload, JSON.stringify(metadata), input.durableContext === undefined ? null : JSON.stringify(contextObject(input.durableContext)), input.runId ?? null, createdAt, digest(payload));
    parents.forEach((parent, ordinal) => {
      this.#db.prepare("INSERT INTO magazine_artifact_edges(child_artifact_id, parent_artifact_id, relation, ordinal) VALUES (?, ?, ?, ?)").run(input.id, parent.artifactId, parent.relation, ordinal);
    });
    return this.requireArtifact(input.id);
  }

  getCurrentRevisionRecord(runId: RunId): LedgerArtifact | undefined {
    const run = this.requireRun(runId);
    return run.currentRevisionRecordArtifactId === undefined
      ? undefined
      : this.requireArtifact(run.currentRevisionRecordArtifactId);
  }

  requireCurrentRevisionRecord(runId: RunId): LedgerArtifact {
    const record = this.getCurrentRevisionRecord(runId);
    if (record === undefined) throw new ArtifactLedgerError("REVISION_RECORD_NOT_FOUND", `Run ${runId} has no current revision record`);
    return record;
  }

  recordDecisionArtifact(runId: RunId, decisionArtifactId: ArtifactId): LedgerRun {
    const row = this.#db.prepare(
      `SELECT * FROM magazine_decisions WHERE run_id = ? AND artifact_id = ?`,
    ).get(runId, decisionArtifactId) as DecisionRow | undefined;
    if (row === undefined) {
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

  /** Register the revision identity carried by an immutable manuscript. */
  #registerManuscriptRevision(input: {
    readonly manuscriptArtifactId: ArtifactId;
    readonly articleId: string;
  }): ManuscriptRevisionId {
    const artifact = this.requireArtifact(input.manuscriptArtifactId);
    if (artifact.metadata.articleId !== input.articleId) {
      throw new ArtifactLedgerError("ATTEMPT_ARTICLE_MISMATCH", "Manuscript artifact belongs to another article");
    }
    const rawRevision = artifact.metadata.revisionId;
    if (typeof rawRevision !== "string" || rawRevision.trim().length === 0) {
      throw new ArtifactLedgerError("ATTEMPT_REVISION_REQUIRED", `Manuscript ${input.manuscriptArtifactId} has no immutable revisionId metadata`);
    }
    const revisionId = rawRevision as ManuscriptRevisionId;
    const existing = this.#db.prepare(
      "SELECT * FROM magazine_manuscript_revisions WHERE revision_id = ? OR manuscript_artifact_id = ?",
    ).all(revisionId, input.manuscriptArtifactId) as readonly ManuscriptRevisionRow[];
    for (const row of existing) {
      if (row.revision_id !== revisionId || row.manuscript_artifact_id !== input.manuscriptArtifactId) {
        throw new ArtifactLedgerError("ATTEMPT_REVISION_CONFLICT", `Revision ${revisionId} is bound to another manuscript artifact`);
      }
      if (row.article_id !== input.articleId) {
        throw new ArtifactLedgerError("ATTEMPT_ARTICLE_MISMATCH", `Revision ${revisionId} belongs to another article`);
      }
      return row.revision_id;
    }
    this.#db.prepare(
      `INSERT INTO magazine_manuscript_revisions(
        revision_id, manuscript_artifact_id, article_id, registered_at
      ) VALUES (?, ?, ?, ?)`,
    ).run(revisionId, input.manuscriptArtifactId, input.articleId, this.#clock.now().toISOString());
    return revisionId;
  }

  /**
   * Atomically claim one magazine-owned model/tool operation. This mirrors the
   * old RunEngine claim fence without importing Loops persistence into the
   * artifact authority.
   */
  #claimArticleAttempt(input: ArticleAttemptClaimInput): ArticleAttemptClaim {
    const nowMs = this.#attemptNowMs();
    const leaseMs = input.leaseMs ?? this.#articleAttemptLeaseMs;
    if (!Number.isSafeInteger(leaseMs) || leaseMs <= 0) {
      throw new ArtifactLedgerError("ATTEMPT_INVALID", "Article attempt lease must be a positive integer");
    }
    if (input.operationKey.trim().length === 0) {
      throw new ArtifactLedgerError("ATTEMPT_INVALID", "Article attempt operation key is required");
    }
    const claim = this.#db.transaction(() => {
      const run = this.requireRun(input.rootRunId);
      if (run.articleExecutionId !== input.articleExecutionId || run.articleId !== input.articleId) {
        throw new ArtifactLedgerError("ATTEMPT_EXECUTION_MISMATCH", "Article attempt is not bound to the exact execution");
      }
      const selection = this.#db.prepare(
        `SELECT claim_id, operation_input_digest FROM magazine_article_operation_selections
         WHERE article_execution_id = ? AND operation_key = ?`,
      ).get(input.articleExecutionId, input.operationKey) as { readonly claim_id: AttemptId; readonly operation_input_digest: string | null } | undefined;
      if (selection !== undefined) {
        if (selection.operation_input_digest !== input.operationInputDigest) {
          throw new ArtifactLedgerError("ATTEMPT_OPERATION_INPUT_MISMATCH", `Article operation ${input.operationKey} was selected for different immutable inputs`);
        }
        throw new ArtifactLedgerError("ATTEMPT_ALREADY_SELECTED", `Article operation ${input.operationKey} already has a selected result`);
      }
      const manuscript = this.requireArtifact(input.manuscriptArtifactId);
      const manuscriptRevisionId = this.#registerManuscriptRevision({
        manuscriptArtifactId: input.manuscriptArtifactId,
        articleId: input.articleId,
      });
      const active = this.#db.prepare(
        `SELECT * FROM magazine_article_attempts
         WHERE article_execution_id = ? AND operation_key = ? AND status = 'active'`,
      ).get(input.articleExecutionId, input.operationKey) as ArticleAttemptRow | undefined;
      if (active !== undefined) {
        if (active.lease_expires_at_ms <= nowMs) {
          this.#db.prepare(
            `UPDATE magazine_article_attempts
             SET status = 'stale', finished_at = ?
             WHERE claim_id = ? AND status = 'active'`,
          ).run(this.#clock.now().toISOString(), active.claim_id);
        } else {
          throw new ArtifactLedgerError("ATTEMPT_UNAVAILABLE", `Article operation ${input.operationKey} is already claimed`);
        }
      }
      assertAttemptAccess(input);
      const exposure = input.access === "tool" ? undefined : input.access;
      if (exposure !== undefined) {
        const previous = this.#db.prepare(
          `SELECT principal_id, manuscript_revision_id, manuscript_artifact_id, access
           FROM magazine_article_exposures
           WHERE principal_id = ? AND manuscript_revision_id = ?`,
        ).all(input.principalId, manuscriptRevisionId) as readonly {
          readonly principal_id: string;
          readonly manuscript_revision_id: ManuscriptRevisionId;
          readonly manuscript_artifact_id: ArtifactId;
          readonly access: "source_aware" | "source_blind";
        }[];
        try {
          assertPrincipalExposureIsolated(
            previous.map((row) => ({
              principalId: row.principal_id,
              manuscriptRevisionId: row.manuscript_revision_id,
              manuscriptArtifactId: row.manuscript_artifact_id,
              access: row.access,
            })),
            { principalId: input.principalId, manuscriptRevisionId, manuscriptArtifactId: input.manuscriptArtifactId, access: exposure },
          );
        } catch (error) {
          if (error instanceof SourceExposureConflictError) {
            throw new ArtifactLedgerError("ATTEMPT_EXPOSURE_CONFLICT", error.message, { cause: error });
          }
          throw error;
        }
      }
      const claimId = newId<AttemptId>("article-attempt");
      const claimNumber = (
        this.#db.prepare(
          `SELECT COALESCE(MAX(attempt_number), 0) + 1 AS value
           FROM magazine_article_attempts
           WHERE article_execution_id = ? AND operation_key = ?`,
        ).get(input.articleExecutionId, input.operationKey) as { readonly value: number }
      ).value;
      const fence = (
        this.#db.prepare(
          `SELECT COALESCE(MAX(fence), 0) + 1 AS value
           FROM magazine_article_attempts
           WHERE article_execution_id = ? AND operation_key = ?`,
        ).get(input.articleExecutionId, input.operationKey) as { readonly value: number }
      ).value;
      const context = articleAttemptContext(input, run);
      const expiresAtMs = nowMs + leaseMs;
      this.#db.prepare(
        `INSERT INTO magazine_article_attempts(
          claim_id, article_execution_id, run_id, article_id, operation_key,
          role, access, manuscript_artifact_id, manuscript_revision_id,
          operation_input_digest,
          attempt_id, attempt_number, fence, principal_id, credential_profile_id,
          authority, capabilities_json, status, lease_expires_at_ms,
          durable_context_json, output_artifact_ids_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL, ?)`,
      ).run(
        claimId,
        input.articleExecutionId,
        run.runId,
        input.articleId,
        input.operationKey,
        input.role,
        input.access,
        input.manuscriptArtifactId,
        manuscriptRevisionId,
        input.operationInputDigest,
        context.attemptId,
        claimNumber,
        fence,
        input.principalId,
        input.credentialProfileId,
        input.authority,
        JSON.stringify([...new Set(input.capabilities)].sort()),
        expiresAtMs,
        JSON.stringify(contextObject(context)),
        this.#clock.now().toISOString(),
      );
      if (exposure !== undefined) {
        this.#db.prepare(
          `INSERT OR IGNORE INTO magazine_article_exposures(
             principal_id, manuscript_revision_id, manuscript_artifact_id,
             access, first_claim_id, exposed_at
           ) VALUES (?, ?, ?, ?, ?, ?)`,
        ).run(input.principalId, manuscriptRevisionId, input.manuscriptArtifactId, exposure, claimId, this.#clock.now().toISOString());
      }
      const attemptId = context.attemptId;
      const attemptNumber = context.attemptNumber;
      return {
        schemaVersion: "article-attempt-claim/1",
        articleExecutionId: input.articleExecutionId,
        articleId: input.articleId,
        operationKey: input.operationKey,
        role: input.role,
        access: input.access,
        manuscriptArtifactId: input.manuscriptArtifactId,
        manuscriptRevisionId,
        operationInputDigest: input.operationInputDigest,
        claimId,
        claimSequence: claimNumber,
        attemptId,
        attemptNumber,
        fence,
        principalId: input.principalId,
        credentialProfileId: input.credentialProfileId,
        authority: input.authority,
        capabilities: Object.freeze([...new Set(input.capabilities)].sort()),
        leaseExpiresAt: new Date(expiresAtMs).toISOString(),
        durableContext: context,
      } satisfies ArticleAttemptClaim;
    })();
    return claim;
  }

  #heartbeatArticleAttempt(claim: ArticleAttemptClaim): ArticleAttemptClaim {
    const nowMs = this.#attemptNowMs();
    const row = this.#requireArticleAttempt(claim.claimId);
    if (!matchesArticleAttempt(row, claim) || row.status !== "active" || row.lease_expires_at_ms <= nowMs) {
      if (row.status === "active" && row.lease_expires_at_ms <= nowMs) this.#markArticleAttemptStale(row.claim_id);
      throw new ArtifactLedgerError("ATTEMPT_STALE", `Article attempt ${claim.claimId} is stale`);
    }
    const expiresAtMs = nowMs + this.#articleAttemptLeaseMs;
    this.#db.prepare(
      `UPDATE magazine_article_attempts SET lease_expires_at_ms = ?
       WHERE claim_id = ? AND status = 'active' AND fence = ?`,
    ).run(expiresAtMs, claim.claimId, claim.fence);
    return { ...claim, leaseExpiresAt: new Date(expiresAtMs).toISOString() };
  }

  #createArticleAttemptArtifact(input: {
    readonly claim: ArticleAttemptClaim;
    readonly key: string;
    readonly artifact: Omit<LedgerArtifactInput, "id" | "runId" | "durableContext">;
  }): LedgerArtifact {
    if (input.key.trim().length === 0) throw new ArtifactLedgerError("ARTIFACT_INVALID", "Attempt artifact key is required");
    const row = this.#requireArticleAttempt(input.claim.claimId);
    if (!matchesArticleAttempt(row, input.claim)) {
      throw new ArtifactLedgerError("ATTEMPT_STALE", `Article attempt ${input.claim.claimId} does not match its fence`);
    }
    const run = this.requireRun(input.claim.durableContext.runId as RunId);
    const authorityMetadata: JsonObject = {
      articleExecutionId: input.claim.articleExecutionId,
      operationKey: input.claim.operationKey,
      claimId: input.claim.claimId,
      attemptId: input.claim.attemptId,
      attemptNumber: input.claim.durableContext.attemptNumber,
      operationInputDigest: input.claim.operationInputDigest,
      principalId: input.claim.principalId,
      access: input.claim.access,
      loopsRunId: input.claim.durableContext.runId,
      invocationId: input.claim.durableContext.invocationId,
      callId: input.claim.durableContext.callId,
      ...(input.claim.durableContext.workflowName === undefined ? {} : { workflowName: input.claim.durableContext.workflowName }),
      ...(input.claim.durableContext.workflowVersion === undefined ? {} : { workflowVersion: input.claim.durableContext.workflowVersion }),
    };
    return this.createArtifact({
      ...input.artifact,
      id: articleAttemptArtifactId(input.claim, input.key),
      metadata: { ...(input.artifact.metadata ?? {}), ...authorityMetadata },
      runId: run.runId,
      durableContext: input.claim.durableContext,
    });
  }

  #completeArticleAttempt(
    claim: ArticleAttemptClaim,
    artifactIds: readonly ArtifactId[],
  ): ArticleAttemptCommit {
    const nowMs = this.#attemptNowMs();
    const now = this.#clock.now().toISOString();
    const result = this.#db.transaction(() => {
      const row = this.#requireArticleAttempt(claim.claimId);
      const existingIds = row.output_artifact_ids_json === null ? undefined : JSON.parse(row.output_artifact_ids_json) as readonly ArtifactId[];
      if (!matchesArticleAttempt(row, claim)) throw new ArtifactLedgerError("ATTEMPT_STALE", `Article attempt ${claim.claimId} does not match its fence`);
      const selected = this.#db.prepare(
        `SELECT claim_id, artifact_ids_json, operation_input_digest FROM magazine_article_operation_selections
         WHERE article_execution_id = ? AND operation_key = ?`,
      ).get(claim.articleExecutionId, claim.operationKey) as { readonly claim_id: AttemptId; readonly artifact_ids_json: string; readonly operation_input_digest: string | null } | undefined;
      if (selected !== undefined) {
        if (selected.operation_input_digest !== claim.operationInputDigest) {
          throw new ArtifactLedgerError("ATTEMPT_OPERATION_INPUT_MISMATCH", `Article operation ${claim.operationKey} was selected for different immutable inputs`);
        }
        const selectedIds = JSON.parse(selected.artifact_ids_json) as readonly ArtifactId[];
        if (selected.claim_id === claim.claimId) {
          if (!sameStrings(selectedIds, artifactIds) && existingIds !== undefined && !sameStrings(selectedIds, existingIds)) {
            throw new ArtifactLedgerError("ATTEMPT_RESULT_CONFLICT", `Article attempt ${claim.claimId} already has a different result`);
          }
          return { selected: true as const, status: "already_selected" as const, artifactIds: selectedIds };
        }
        return { selected: false as const, status: "already_selected" as const, artifactIds: [] as const };
      }
      if (row.status === "completed") {
        if (existingIds === undefined) throw new ArtifactLedgerError("ATTEMPT_RESULT_INVALID", `Completed article attempt ${claim.claimId} has no result`);
        this.#db.prepare(
          `INSERT INTO magazine_article_operation_selections(
             article_execution_id, operation_key, claim_id, artifact_ids_json, operation_input_digest, selected_at
           ) VALUES (?, ?, ?, ?, ?, ?)`,
        ).run(claim.articleExecutionId, claim.operationKey, claim.claimId, JSON.stringify(existingIds), claim.operationInputDigest, now);
        if (!sameStrings(existingIds, artifactIds)) throw new ArtifactLedgerError("ATTEMPT_RESULT_CONFLICT", `Article attempt ${claim.claimId} already has a different result`);
        return { selected: true as const, status: "already_selected" as const, artifactIds: existingIds };
      }
      if (row.status !== "active" || row.lease_expires_at_ms <= nowMs) {
        if (row.status === "active") this.#db.prepare("UPDATE magazine_article_attempts SET status = 'stale', finished_at = ? WHERE claim_id = ? AND status = 'active'").run(now, claim.claimId);
        return { selected: false as const, status: "stale" as const, artifactIds: [] as const };
      }
      for (const artifactId of artifactIds) {
        const artifact = this.requireArtifact(artifactId);
        if (artifact.producingRunId !== row.run_id || artifact.metadata.claimId !== claim.claimId) {
          throw new ArtifactLedgerError("ATTEMPT_RESULT_INVALID", `Artifact ${artifactId} is not produced by article attempt ${claim.claimId}`);
        }
      }
      this.#db.prepare(
        `INSERT INTO magazine_article_operation_selections(
           article_execution_id, operation_key, claim_id, artifact_ids_json, operation_input_digest, selected_at
         ) VALUES (?, ?, ?, ?, ?, ?)`,
      ).run(claim.articleExecutionId, claim.operationKey, claim.claimId, JSON.stringify(artifactIds), claim.operationInputDigest, now);
      this.#db.prepare(
        `UPDATE magazine_article_attempts
         SET status = 'completed', output_artifact_ids_json = ?, finished_at = ?
         WHERE claim_id = ? AND status = 'active' AND fence = ?`,
      ).run(JSON.stringify(artifactIds), now, claim.claimId, claim.fence);
      return { selected: true as const, status: "selected" as const, artifactIds };
    })();
    return result;
  }

  /**
   * Return only the immutable artifacts selected for an exact operation input.
   * This query is intentionally private to the runner facade. Callers cannot
   * turn the operation-selection table into a general workflow-state query.
   */
  #readSelectedArticleAttempt(input: {
    readonly articleExecutionId: ArticleExecutionId;
    readonly operationKey: string;
    readonly operationInputDigest: string;
  }): readonly LedgerArtifact[] | undefined {
    const selection = this.#db.prepare(
      `SELECT artifact_ids_json, operation_input_digest
       FROM magazine_article_operation_selections
       WHERE article_execution_id = ? AND operation_key = ?`,
    ).get(input.articleExecutionId, input.operationKey) as { readonly artifact_ids_json: string; readonly operation_input_digest: string | null } | undefined;
    if (selection === undefined) return undefined;
    if (selection.operation_input_digest !== input.operationInputDigest) {
      throw new ArtifactLedgerError("ATTEMPT_OPERATION_INPUT_MISMATCH", `Article operation ${input.operationKey} was selected for different immutable inputs`);
    }
    const artifactIds = JSON.parse(selection.artifact_ids_json) as readonly ArtifactId[];
    if (!Array.isArray(artifactIds) || artifactIds.some((artifactId) => typeof artifactId !== "string" || artifactId.length === 0)) {
      throw new ArtifactLedgerError("ATTEMPT_RESULT_INVALID", `Article operation ${input.operationKey} has malformed selected artifacts`);
    }
    return Object.freeze(artifactIds.map((artifactId) => this.requireArtifact(artifactId)));
  }

  #failArticleAttempt(claim: ArticleAttemptClaim): void {
    const now = this.#clock.now().toISOString();
    this.#db.prepare(
      `UPDATE magazine_article_attempts SET status = 'failed', finished_at = ?
       WHERE claim_id = ? AND status = 'active' AND fence = ?`,
    ).run(now, claim.claimId, claim.fence);
  }

  #requireArticleAttempt(claimId: AttemptId): ArticleAttemptRow {
    const row = this.#db.prepare("SELECT * FROM magazine_article_attempts WHERE claim_id = ?").get(claimId) as ArticleAttemptRow | undefined;
    if (row === undefined) throw new ArtifactLedgerError("ATTEMPT_NOT_FOUND", `Article attempt ${claimId} does not exist`);
    return row;
  }

  #markArticleAttemptStale(claimId: AttemptId): void {
    this.#db.prepare(
      "UPDATE magazine_article_attempts SET status = 'stale', finished_at = ? WHERE claim_id = ? AND status = 'active'",
    ).run(this.#clock.now().toISOString(), claimId);
  }

  #attemptNowMs(): number {
    const value = this.#attemptClock.nowMs();
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new ArtifactLedgerError("ATTEMPT_INVALID", "Operational lease clock must return a non-negative safe integer");
    }
    return value;
  }

  createOffer(input: {
    readonly id: string;
    readonly runId: RunId;
    readonly taskArtifactId: ArtifactId;
    readonly inputArtifactIds: readonly ArtifactId[];
    readonly allowedChoices: readonly ("accept" | "revise" | "drop")[];
  }): LedgerOffer {
    const existing = this.#db.prepare("SELECT * FROM magazine_offers WHERE id = ?").get(input.id) as OfferRow | undefined;
    if (existing !== undefined) {
      const offer = toOffer(existing);
      const expectedInputs = input.inputArtifactIds;
      const expectedChoices = input.allowedChoices;
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
    const allowedChoices = input.allowedChoices;
    if (!sameStrings(allowedChoices, ["accept", "revise", "drop"])) {
      throw new ArtifactLedgerError("OFFER_INVALID", "Article decision offer must explicitly expose accept, revise, and drop in canonical order");
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

  recordDecision(
    input: Omit<LedgerDecision, "createdAt" | "durableContext"> & {
      readonly durableContext: WorkflowWaitContext;
      readonly createdAt?: string;
    },
  ): LedgerDecision {
    assertWaitContext(input.durableContext, input.runId);
    const offer = this.requireOffer(input.offerId);
    if (offer.role === "article_decision") {
      throw new ArtifactLedgerError(
        "DECISION_VALIDATION_REQUIRED",
        "Article editor decisions must be validated against their parsed task, route, and review brief before persistence",
      );
    }
    return this.#recordDecision(input);
  }

  /**
   * Atomically persist an editor decision and its immutable decision artifact.
   *
   * Only the human request and immutable artifact identity cross this seam.
   * Validation facts are derived again from the task, route, and revision
   * brief stored in this ledger. A caller cannot smuggle validatorVersion,
   * approvals, or rewrite-budget facts into persistence.
   */
  #recordValidatedEditorDecision(input: {
    readonly decision: ArticleEditorDecisionRecordInput;
    readonly artifact: LedgerArtifactInput;
  }): LedgerDecision {
    const decision = input.decision;
    const authority = this.#deriveArticleEditorDecisionAuthority(decision);
    const validation = authority.validation;
    assertWaitContext(decision.durableContext, decision.runId);
    if (input.artifact.id !== decision.artifactId || input.artifact.runId !== decision.runId) {
      throw new ArtifactLedgerError("DECISION_ARTIFACT_MISMATCH", "validated decision artifact must bind the exact run and decision identity");
    }
    assertDecisionArtifactFacts(input.artifact, decision, validation);

    const existing = this.#db.prepare("SELECT * FROM magazine_decisions WHERE offer_id = ?").get(decision.offerId) as DecisionRow | undefined;
    if (existing !== undefined) {
      const persisted = toDecision(existing);
      if (!sameValidatedDecision(persisted, decision, validation)) {
        throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${decision.offerId} already has a different validated decision`);
      }
      this.requireArtifact(persisted.artifactId);
      return persisted;
    }

    const offer = this.requireOffer(decision.offerId);
    if (offer.runId !== decision.runId || offer.status !== "active") throw new ArtifactLedgerError("OFFER_STALE", `Offer ${decision.offerId} is not active for this run`);
    if (!offer.allowedChoices.includes(decision.choice)) throw new ArtifactLedgerError("CHOICE_INVALID", `Choice ${decision.choice} is not allowed for offer ${decision.offerId}`);
    if (offer.taskArtifactId !== decision.taskArtifactId || !sameStrings(offer.inputArtifactIds, decision.inputArtifactIds)) throw new ArtifactLedgerError("OFFER_INPUT_MISMATCH", `Decision does not bind offer ${decision.offerId}'s immutable inputs`);

    const payload = encodePayload(input.artifact.payload);
    const metadata = { ...(input.artifact.metadata ?? {}), durableContext: contextObject(decision.durableContext) };
    const parents = input.artifact.parents ?? [];
    const createdAt = decision.createdAt ?? this.#clock.now().toISOString();
    const transaction = this.#db.transaction(() => {
      const existingArtifact = this.#db.prepare("SELECT * FROM magazine_artifacts WHERE id = ?").get(input.artifact.id) as ArtifactRow | undefined;
      if (existingArtifact !== undefined) {
        if (!sameArtifact(existingArtifact, { ...input.artifact, durableContext: decision.durableContext }, payload, metadata, parents, this.parentRows(input.artifact.id))) {
          throw new ArtifactLedgerError("ARTIFACT_ID_COLLISION", `Artifact ${input.artifact.id} already exists with different immutable content`);
        }
      } else {
        for (const parent of parents) this.requireArtifact(parent.artifactId);
        this.#db.prepare(
          `INSERT INTO magazine_artifacts(
            id, kind, schema_version, media_type, origin, payload_kind, payload,
            metadata_json, durable_context_json, run_id, created_at, digest
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        ).run(
          input.artifact.id,
          input.artifact.kind,
          input.artifact.schemaVersion,
          input.artifact.mediaType,
          input.artifact.origin,
          input.artifact.payload.kind,
          payload,
          JSON.stringify(metadata),
          JSON.stringify(contextObject(decision.durableContext)),
          decision.runId,
          createdAt,
          digest(payload),
        );
        parents.forEach((parent, ordinal) => {
          this.#db.prepare(
            `INSERT INTO magazine_artifact_edges(child_artifact_id, parent_artifact_id, relation, ordinal)
             VALUES (?, ?, ?, ?)`,
          ).run(input.artifact.id, parent.artifactId, parent.relation, ordinal);
        });
      }
      this.#db.prepare(
        `INSERT INTO magazine_decisions(
          id, run_id, offer_id, task_artifact_id, input_artifact_ids_json,
          principal_id, credential_profile_id, choice, rationale,
          approved_finding_ids_json, additional_rewrite_budget,
          validator_version, canonical_approved_finding_ids_json, rewrite_budget_json,
          artifact_id, created_at, durable_context_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        decision.id,
        decision.runId,
        decision.offerId,
        decision.taskArtifactId,
        JSON.stringify(decision.inputArtifactIds),
        decision.principalId,
        decision.credentialProfileId,
        decision.choice,
        decision.rationale,
        decision.approvedFindingIds === undefined ? null : JSON.stringify(decision.approvedFindingIds),
        decision.additionalRewriteBudget ?? null,
        validation.validatorVersion,
        JSON.stringify(validation.canonicalApprovedFindingIds),
        JSON.stringify(validation.rewriteBudget),
        decision.artifactId,
        createdAt,
        JSON.stringify(contextObject(decision.durableContext)),
      );
    });
    transaction();
    return this.requireDecision(decision.offerId);
  }

  /**
   * Rebuild editor authority facts from immutable ledger evidence. This stays
   * private so a caller cannot replace the route or validation with a hint.
   */
  #deriveArticleEditorDecisionAuthority(
    decision: ArticleEditorDecisionRecordInput,
  ): ArticleEditorDecisionAuthorityFacts {
    const offer = this.requireOffer(decision.offerId);
    if (offer.role !== "article_decision") {
      throw new ArtifactLedgerError("DECISION_VALIDATION_REQUIRED", "Only article decision offers use editor authority validation");
    }
    if (offer.runId !== decision.runId || offer.status !== "active") {
      throw new ArtifactLedgerError("OFFER_STALE", `Offer ${decision.offerId} is not active for this run`);
    }
    if (offer.taskArtifactId !== decision.taskArtifactId || !sameStrings(offer.inputArtifactIds, decision.inputArtifactIds)) {
      throw new ArtifactLedgerError("OFFER_INPUT_MISMATCH", `Decision does not bind offer ${decision.offerId}'s immutable inputs`);
    }
    const run = this.requireRun(decision.runId);
    const taskArtifact = this.requireArtifact(offer.taskArtifactId);
    if (taskArtifact.kind !== "article_decision_request" || taskArtifact.schemaVersion !== "article-decision-request/1") {
      throw new ArtifactLedgerError("DECISION_TASK_INVALID", "active decision task has the wrong artifact contract");
    }
    const task = parseLedgerArtifact(this, offer.taskArtifactId, taskArtifact, articleDecisionTaskSchema, "article decision task") as ArticleDecisionTask;
    if (
      task.runId !== run.runId
      || task.articleExecutionId !== run.articleExecutionId
      || task.articleId !== run.articleId
      || task.expectedDecisionArtifactId !== decision.artifactId
      || !sameStrings(task.inputArtifactIds, offer.inputArtifactIds)
      || !sameStrings(task.allowedChoices, ["accept", "revise", "drop"])
    ) {
      throw new ArtifactLedgerError("DECISION_TASK_INVALID", "decision task is not bound to the exact run, offer, and decision artifact");
    }
    assertWaitContext(decision.durableContext, decision.runId);
    if (decision.durableContext.key !== `article.decision.${safeIdentity(task.cycleId)}`) {
      throw new ArtifactLedgerError("DECISION_PROVENANCE_INVALID", "decision wait key is not scoped to the exact review cycle");
    }

    const briefArtifact = this.requireArtifact(task.revisionBriefArtifactId);
    const routeArtifact = this.requireArtifact(task.routeArtifactId);
    if (briefArtifact.kind !== "article_revision_brief" || briefArtifact.schemaVersion !== "article-revision-brief/1") {
      throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", "decision task references the wrong revision brief artifact");
    }
    if (routeArtifact.kind !== "article_review_route" || routeArtifact.schemaVersion !== "article-review-route/1") {
      throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", "decision task references the wrong review route artifact");
    }
    const brief = parseLedgerArtifact(this, task.revisionBriefArtifactId, briefArtifact, revisionBriefSchema, "revision brief") as RevisionBrief;
    const route = parseLedgerArtifact(this, task.routeArtifactId, routeArtifact, articleReviewRouteSchema, "review route") as ArticleReviewRoute;
    if (
      route.outcome !== "editor_wait"
      || !sameStrings(route.allowedChoices, task.allowedChoices)
      || brief.articleId !== task.articleId
      || brief.manuscriptArtifactId !== task.manuscriptArtifactId
      || brief.iterationId !== task.iterationId
      || route.articleId !== brief.articleId
      || route.manuscriptArtifactId !== brief.manuscriptArtifactId
      || route.iterationId !== brief.iterationId
      || brief.cycleId !== task.cycleId
      || route.cycleId !== task.cycleId
      || brief.manuscriptRevisionId !== task.manuscriptRevisionId
      || route.manuscriptRevisionId !== task.manuscriptRevisionId
      || brief.reviewPlanArtifactId !== task.reviewPlanArtifactId
      || route.reviewPlanArtifactId !== task.reviewPlanArtifactId
      || brief.rewriteOrdinal !== task.rewriteOrdinal
      || route.rewriteOrdinal !== task.rewriteOrdinal
      || !sameParents(taskArtifact.parents, task.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_evidence" })))
      || !sameParents(routeArtifact.parents, [{ artifactId: task.revisionBriefArtifactId, relation: "revision_brief" }])
      || !sameStrings(briefArtifact.parents.map((parent) => parent.artifactId), revisionBriefParents({ brief }))
    ) {
      throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", "decision task, brief, route, and immutable parents do not match");
    }
    const editorDecision = {
      choice: decision.choice,
      ...(decision.approvedFindingIds === undefined ? {} : { approvedFindingIds: decision.approvedFindingIds }),
      ...(decision.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: decision.additionalRewriteBudget }),
    } as ArticleEditorDecision;
    const parsedDecision = articleEditorDecisionSchema.safeParse(editorDecision);
    if (!parsedDecision.success) {
      throw new ArtifactLedgerError("DECISION_VALIDATION_INVALID", "editor decision has fields outside the strict article decision contract");
    }
    let validation: ValidatedArticleEditorDecision;
    try {
      validation = validatedArticleEditorDecision(route, parsedDecision.data as ArticleEditorDecision);
    } catch (error) {
      throw new ArtifactLedgerError("DECISION_VALIDATION_INVALID", error instanceof Error ? error.message : "editor decision failed authority validation", { cause: error });
    }
    return { task, brief, route, validation };
  }

  #recordDecision(
    input: Omit<LedgerDecision, "createdAt"> & { readonly createdAt?: string },
  ): LedgerDecision {
    const existing = this.#db.prepare("SELECT * FROM magazine_decisions WHERE offer_id = ?").get(input.offerId) as DecisionRow | undefined;
    if (existing !== undefined) {
      const decision = toDecision(existing);
      if (
        decision.principalId !== input.principalId
        || decision.credentialProfileId !== input.credentialProfileId
        || decision.choice !== input.choice
        || decision.rationale !== input.rationale
        || JSON.stringify(decision.approvedFindingIds ?? null) !== JSON.stringify(input.approvedFindingIds ?? null)
        || decision.additionalRewriteBudget !== input.additionalRewriteBudget
      ) {
        throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${input.offerId} already has a different decision`);
      }
      if (JSON.stringify(decision.durableContext ?? null) !== JSON.stringify(input.durableContext ?? null)) {
        throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${input.offerId} already has different wait provenance`);
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
          principal_id, credential_profile_id, choice, rationale,
          approved_finding_ids_json, additional_rewrite_budget, artifact_id, created_at
          , durable_context_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
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
        input.approvedFindingIds === undefined ? null : JSON.stringify(input.approvedFindingIds),
        input.additionalRewriteBudget ?? null,
        input.artifactId,
        createdAt,
        input.durableContext === undefined ? null : JSON.stringify(contextObject(input.durableContext)),
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

  getDecisionByArtifactId(runId: RunId, artifactId: ArtifactId): LedgerDecision | undefined {
    const row = this.#db.prepare(
      "SELECT * FROM magazine_decisions WHERE run_id = ? AND artifact_id = ?",
    ).get(runId, artifactId) as DecisionRow | undefined;
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

  #validateRevisionRecordArtifact(run: LedgerRun, artifactId: ArtifactId): ArticleRevisionRecord {
    const artifact = this.requireArtifact(artifactId);
    if (artifact.kind !== "article_revision_record" || artifact.schemaVersion !== "article-revision-record/1" || artifact.mediaType !== "application/json" || artifact.payloadKind !== "json" || artifact.producingRunId !== run.runId) {
      throw new ArtifactLedgerError("REVISION_RECORD_INVALID", "current revision pointer does not name an exact run-owned revision record");
    }
    let value: unknown;
    try {
      value = JSON.parse(Buffer.from(this.readArtifact(artifactId).bytes).toString("utf8"));
    } catch (error) {
      throw new ArtifactLedgerError("REVISION_RECORD_INVALID", "revision record payload is not valid JSON", { cause: error });
    }
    let record: ArticleRevisionRecord;
    try {
      record = parseArticleRevisionRecord(value);
    } catch (error) {
      throw new ArtifactLedgerError("REVISION_RECORD_INVALID", "revision record payload does not match its strict schema", { cause: error });
    }
    if (record.manuscriptArtifactId !== artifact.parents[0]?.artifactId || artifact.metadata.articleId !== run.articleId) {
      throw new ArtifactLedgerError("REVISION_RECORD_INVALID", "revision record metadata or manuscript parent is not exact");
    }
    let expectedParents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[];
    try {
      expectedParents = articleRevisionRecordParents(record);
    } catch (error) {
      throw new ArtifactLedgerError("REVISION_RECORD_LINEAGE_INVALID", "revision record parent references are not unique", { cause: error });
    }
    if (!sameParents(artifact.parents, expectedParents)) {
      throw new ArtifactLedgerError("REVISION_RECORD_LINEAGE_INVALID", "revision record parents do not match its canonical package order");
    }
    for (const parent of expectedParents) this.requireArtifact(parent.artifactId);
    const manuscript = this.requireArtifact(record.manuscriptArtifactId);
    if (manuscript.kind !== "article_manuscript" || manuscript.metadata.articleId !== run.articleId || manuscript.metadata.revisionId !== record.manuscriptRevisionId) {
      throw new ArtifactLedgerError("REVISION_RECORD_INVALID", "revision record manuscript identity is not exact");
    }
    if (artifact.metadata.manuscriptArtifactId !== record.manuscriptArtifactId || artifact.metadata.manuscriptRevisionId !== record.manuscriptRevisionId) {
      throw new ArtifactLedgerError("REVISION_RECORD_INVALID", "revision record metadata does not match its payload");
    }
    return record;
  }

  #applySchema(): void {
    this.#db.exec(`
      CREATE TABLE IF NOT EXISTS magazine_runs (
        run_id TEXT PRIMARY KEY,
        article_execution_id TEXT,
        article_id TEXT NOT NULL,
        edition_id TEXT,
        workflow_version TEXT NOT NULL,
        /* One Loops root owns many Magazine article child runs. */
        loops_run_id TEXT NOT NULL,
        manuscript_artifact_id TEXT NOT NULL,
        current_revision_record_artifact_id TEXT,
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
      CREATE TABLE IF NOT EXISTS magazine_article_attempts (
        claim_id TEXT PRIMARY KEY,
        article_execution_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        article_id TEXT NOT NULL,
        operation_key TEXT NOT NULL,
          role TEXT NOT NULL CHECK (role IN ('model', 'tool')),
          access TEXT NOT NULL CHECK (access IN ('source_aware', 'source_blind', 'tool')),
          manuscript_artifact_id TEXT NOT NULL,
          manuscript_revision_id TEXT,
          operation_input_digest TEXT,
          attempt_id TEXT NOT NULL,
        attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
        fence INTEGER NOT NULL CHECK (fence > 0),
        principal_id TEXT NOT NULL,
        credential_profile_id TEXT NOT NULL,
        authority TEXT NOT NULL CHECK (authority IN ('model', 'tool')),
        capabilities_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'failed', 'stale')),
        lease_expires_at_ms INTEGER NOT NULL,
        durable_context_json TEXT NOT NULL,
        output_artifact_ids_json TEXT,
        created_at TEXT NOT NULL,
        finished_at TEXT,
        FOREIGN KEY (run_id) REFERENCES magazine_runs(run_id),
        FOREIGN KEY (manuscript_artifact_id) REFERENCES magazine_artifacts(id),
        UNIQUE (article_execution_id, operation_key, attempt_number),
        UNIQUE (article_execution_id, operation_key, fence)
      );
      CREATE UNIQUE INDEX IF NOT EXISTS magazine_one_active_article_attempt
        ON magazine_article_attempts(article_execution_id, operation_key) WHERE status = 'active';
      CREATE TABLE IF NOT EXISTS magazine_article_exposures (
        principal_id TEXT NOT NULL,
        manuscript_revision_id TEXT NOT NULL,
        manuscript_artifact_id TEXT NOT NULL,
        access TEXT NOT NULL CHECK (access IN ('source_aware', 'source_blind')),
        first_claim_id TEXT NOT NULL,
        exposed_at TEXT NOT NULL,
        PRIMARY KEY (principal_id, manuscript_revision_id),
        FOREIGN KEY (manuscript_artifact_id) REFERENCES magazine_artifacts(id),
        FOREIGN KEY (first_claim_id) REFERENCES magazine_article_attempts(claim_id)
      );
      CREATE TABLE IF NOT EXISTS magazine_manuscript_revisions (
        revision_id TEXT PRIMARY KEY,
        manuscript_artifact_id TEXT NOT NULL UNIQUE,
        article_id TEXT NOT NULL,
        registered_at TEXT NOT NULL,
        FOREIGN KEY (manuscript_artifact_id) REFERENCES magazine_artifacts(id)
      );
      CREATE TABLE IF NOT EXISTS magazine_article_operation_selections (
        article_execution_id TEXT NOT NULL,
        operation_key TEXT NOT NULL,
        claim_id TEXT NOT NULL,
        artifact_ids_json TEXT NOT NULL,
        operation_input_digest TEXT,
        selected_at TEXT NOT NULL,
        PRIMARY KEY (article_execution_id, operation_key),
        FOREIGN KEY (claim_id) REFERENCES magazine_article_attempts(claim_id)
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
        approved_finding_ids_json TEXT,
        additional_rewrite_budget INTEGER,
        validator_version TEXT,
        canonical_approved_finding_ids_json TEXT,
        rewrite_budget_json TEXT,
        artifact_id TEXT NOT NULL,
        durable_context_json TEXT,
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
    this.#ensureColumn("magazine_runs", "article_execution_id", "TEXT");
    this.#ensureColumn("magazine_runs", "current_revision_record_artifact_id", "TEXT");
    this.#ensureColumn("magazine_article_attempts", "operation_input_digest", "TEXT");
    this.#ensureColumn("magazine_article_operation_selections", "operation_input_digest", "TEXT");
    this.#ensureColumn("magazine_decisions", "durable_context_json", "TEXT");
    this.#ensureColumn("magazine_decisions", "approved_finding_ids_json", "TEXT");
    this.#ensureColumn("magazine_decisions", "additional_rewrite_budget", "INTEGER");
    this.#ensureColumn("magazine_decisions", "validator_version", "TEXT");
    this.#ensureColumn("magazine_decisions", "canonical_approved_finding_ids_json", "TEXT");
    this.#ensureColumn("magazine_decisions", "rewrite_budget_json", "TEXT");
    this.#db.prepare(
      "UPDATE magazine_runs SET article_execution_id = ? || run_id WHERE article_execution_id IS NULL",
    ).run("article-execution-");
    this.#db.exec("CREATE UNIQUE INDEX IF NOT EXISTS magazine_runs_article_execution_id ON magazine_runs(article_execution_id)");
    this.#ensureColumn("magazine_promotions", "manifest_digest", "TEXT");
    this.#ensureColumn("magazine_promotions", "git_commit_oid", "TEXT");
    this.#ensureColumn("magazine_promotions", "git_blob_oids_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "revision_id", "TEXT");
    this.#ensureColumn("magazine_promotions", "expected_parent_revision_id", "TEXT");
    this.#ensureColumn("magazine_promotions", "input_revisions_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "accepted_artifact_ids_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "decision_artifact_ids_json", "TEXT");
    this.#ensureColumn("magazine_promotions", "input_artifact_ids_json", "TEXT");
    this.#migrateLoopsRunIdentitySchema();
    this.#migrateArticleExposureSchema();
    this.#migrateRevisionRecordPointers();
  }

  /**
   * A Loops root may own several Magazine child executions.  Early ledgers
   * incorrectly encoded that relationship as a UNIQUE column, so rebuild the
   * parent table once while preserving rows, foreign-key definitions, and
   * explicit indexes.  Foreign keys are disabled only for this SQLite schema
   * transaction; no workflow data is read or written through the migration.
   */
  #migrateLoopsRunIdentitySchema(): void {
    const indexes = this.#db.prepare("PRAGMA index_list(magazine_runs)").all() as readonly {
      readonly name: string;
      readonly unique: number;
    }[];
    const uniqueLoopsIndex = indexes.find((index) => {
      if (index.unique !== 1) return false;
      const columns = this.#db.prepare(`PRAGMA index_info(${quoteIdentifier(index.name)})`).all() as readonly { readonly name: string | null }[];
      return columns.length === 1 && columns[0]?.name === "loops_run_id";
    });
    if (uniqueLoopsIndex === undefined) return;
    if (this.#db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'magazine_runs_legacy'").get() !== undefined) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_REQUIRED", "Loops run identity migration left a legacy table behind");
    }
    const explicitIndexes = this.#db.prepare(
      "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'magazine_runs' AND sql IS NOT NULL",
    ).all() as readonly { readonly name: string; readonly sql: string }[];
    const columns = [
      "run_id", "article_execution_id", "article_id", "edition_id", "workflow_version", "loops_run_id",
      "manuscript_artifact_id", "current_revision_record_artifact_id", "measurement_artifact_id",
      "decision_artifact_id", "promotion_id", "args_digest", "args_json", "workflow_pin_json",
      "loops_context_json", "created_at", "updated_at",
    ] as const;
    const migrate = this.#db.transaction(() => {
      this.#db.exec("ALTER TABLE magazine_runs RENAME TO magazine_runs_legacy");
      this.#db.exec(`
        CREATE TABLE magazine_runs (
          run_id TEXT PRIMARY KEY,
          article_execution_id TEXT,
          article_id TEXT NOT NULL,
          edition_id TEXT,
          workflow_version TEXT NOT NULL,
          loops_run_id TEXT NOT NULL,
          manuscript_artifact_id TEXT NOT NULL,
          current_revision_record_artifact_id TEXT,
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
      `);
      const columnSql = columns.join(", ");
      this.#db.exec(`INSERT INTO magazine_runs(${columnSql}) SELECT ${columnSql} FROM magazine_runs_legacy`);
      this.#db.exec("DROP TABLE magazine_runs_legacy");
      for (const index of explicitIndexes) {
        if (index.name === uniqueLoopsIndex.name) continue;
        // The SQL was captured before the rename and still targets the new
        // table name.  Recreating it preserves any non-inline caller index.
        this.#db.exec(index.sql);
      }
    });
    const foreignKeysWereEnabled = Number(this.#db.pragma("foreign_keys", { simple: true })) === 1;
    try {
      if (foreignKeysWereEnabled) this.#db.pragma("foreign_keys = OFF");
      this.#db.pragma("legacy_alter_table = ON");
      migrate();
    } catch (error) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_INVALID", "Loops run identity schema migration failed", { cause: error });
    } finally {
      this.#db.pragma("legacy_alter_table = OFF");
      if (foreignKeysWereEnabled) this.#db.pragma("foreign_keys = ON");
    }
  }

  /** Validate persisted pointers when opening an older or copied ledger. */
  #migrateRevisionRecordPointers(): void {
    const rows = this.#db.prepare(
      "SELECT * FROM magazine_runs WHERE current_revision_record_artifact_id IS NOT NULL",
    ).all() as RunRow[];
    for (const row of rows) {
      const run = toRun(row);
      const record = this.#validateRevisionRecordArtifact(run, row.current_revision_record_artifact_id!);
      if (record.manuscriptArtifactId !== row.manuscript_artifact_id) {
        throw new ArtifactLedgerError("SCHEMA_MIGRATION_CONFLICT", `Run ${row.run_id} current revision record does not match its manuscript pointer`);
      }
    }
  }

  #ensureColumn(table: string, column: string, definition: string): void {
    const columns = this.#db.prepare(`PRAGMA table_info(${table})`).all() as readonly { readonly name: string }[];
    if (!columns.some((candidate) => candidate.name === column)) {
      this.#db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`);
    }
  }

  /**
   * Upgrade the first-slice exposure table without ever leaving a nullable
   * revision key behind. Every legacy row must resolve to the immutable
   * manuscript revision table or to the artifact's revision metadata.
   */
  #migrateArticleExposureSchema(): void {
    const columns = this.#db.prepare("PRAGMA table_info(magazine_article_exposures)").all() as readonly {
      readonly name: string;
      readonly notnull: number;
      readonly pk: number;
    }[];
    const revisionColumn = columns.find((column) => column.name === "manuscript_revision_id");
    if (revisionColumn !== undefined && revisionColumn.notnull === 1 && revisionColumn.pk === 2) return;
    if (this.#db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'magazine_article_exposures_legacy'").get() !== undefined) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_REQUIRED", "Article exposure migration left a legacy table behind");
    }
    type LegacyExposureRow = {
      readonly principal_id?: unknown;
      readonly manuscript_revision_id?: unknown;
      readonly manuscript_artifact_id?: unknown;
      readonly access?: unknown;
      readonly first_claim_id?: unknown;
      readonly exposed_at?: unknown;
    };
    const migrate = this.#db.transaction(() => {
      const rows = this.#db.prepare("SELECT * FROM magazine_article_exposures").all() as LegacyExposureRow[];
      this.#db.exec("ALTER TABLE magazine_article_exposures RENAME TO magazine_article_exposures_legacy");
      this.#db.exec(`
        CREATE TABLE magazine_article_exposures (
          principal_id TEXT NOT NULL,
          manuscript_revision_id TEXT NOT NULL,
          manuscript_artifact_id TEXT NOT NULL,
          access TEXT NOT NULL CHECK (access IN ('source_aware', 'source_blind')),
          first_claim_id TEXT NOT NULL,
          exposed_at TEXT NOT NULL,
          PRIMARY KEY (principal_id, manuscript_revision_id),
          FOREIGN KEY (manuscript_artifact_id) REFERENCES magazine_artifacts(id),
          FOREIGN KEY (first_claim_id) REFERENCES magazine_article_attempts(claim_id)
        );
      `);
      const seen = new Set<string>();
      for (const row of rows) {
        const principalId = requireMigrationText(row.principal_id, "principal_id");
        const manuscriptArtifactId = requireMigrationText(row.manuscript_artifact_id, "manuscript_artifact_id") as ArtifactId;
        const access = requireMigrationText(row.access, "access");
        if (access !== "source_aware" && access !== "source_blind") {
          throw new ArtifactLedgerError("SCHEMA_MIGRATION_INVALID", `Article exposure ${manuscriptArtifactId} has invalid access ${access}`);
        }
        const claimId = requireMigrationText(row.first_claim_id, "first_claim_id");
        const exposedAt = requireMigrationText(row.exposed_at, "exposed_at");
        const manuscriptRevisionId = this.#resolveExposureRevision(
          manuscriptArtifactId,
          row.manuscript_revision_id,
        );
        const key = `${principalId}\u0000${manuscriptRevisionId}`;
        if (seen.has(key)) {
          throw new ArtifactLedgerError("SCHEMA_MIGRATION_CONFLICT", `Article exposure has duplicate principal/revision ${principalId}/${manuscriptRevisionId}`);
        }
        seen.add(key);
        this.#db.prepare(
          `INSERT INTO magazine_article_exposures(
             principal_id, manuscript_revision_id, manuscript_artifact_id,
             access, first_claim_id, exposed_at
           ) VALUES (?, ?, ?, ?, ?, ?)`,
        ).run(principalId, manuscriptRevisionId, manuscriptArtifactId, access, claimId, exposedAt);
      }
      this.#db.exec("DROP TABLE magazine_article_exposures_legacy");
    });
    try {
      migrate();
    } catch (error) {
      if (error instanceof ArtifactLedgerError) throw error;
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_INVALID", "Article exposure schema migration failed", { cause: error });
    }
  }

  #resolveExposureRevision(manuscriptArtifactId: ArtifactId, supplied: unknown): ManuscriptRevisionId {
    const suppliedRevision = typeof supplied === "string" && supplied.trim().length > 0 ? supplied : undefined;
    const registered = this.#db.prepare(
      "SELECT revision_id FROM magazine_manuscript_revisions WHERE manuscript_artifact_id = ?",
    ).get(manuscriptArtifactId) as { readonly revision_id: ManuscriptRevisionId } | undefined;
    if (registered !== undefined) {
      if (suppliedRevision !== undefined && suppliedRevision !== registered.revision_id) {
        throw new ArtifactLedgerError("SCHEMA_MIGRATION_CONFLICT", `Exposure revision for ${manuscriptArtifactId} disagrees with registered revision`);
      }
      return registered.revision_id;
    }
    const artifact = this.#db.prepare(
      "SELECT metadata_json FROM magazine_artifacts WHERE id = ?",
    ).get(manuscriptArtifactId) as { readonly metadata_json: string } | undefined;
    if (artifact === undefined) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_UNBACKFILLABLE", `Article exposure references missing manuscript ${manuscriptArtifactId}`);
    }
    let metadata: JsonObject;
    try {
      metadata = JSON.parse(artifact.metadata_json) as JsonObject;
    } catch (error) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_UNBACKFILLABLE", `Manuscript ${manuscriptArtifactId} has invalid metadata`, { cause: error });
    }
    const rawRevision = metadata.revisionId;
    if (typeof rawRevision !== "string" || rawRevision.trim().length === 0) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_UNBACKFILLABLE", `Exposure for ${manuscriptArtifactId} has no immutable revision metadata`);
    }
    const revisionId = rawRevision as ManuscriptRevisionId;
    if (suppliedRevision !== undefined && suppliedRevision !== revisionId) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_CONFLICT", `Exposure revision for ${manuscriptArtifactId} disagrees with artifact metadata`);
    }
    const articleId = metadata.articleId;
    if (typeof articleId !== "string" || articleId.trim().length === 0) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_UNBACKFILLABLE", `Manuscript ${manuscriptArtifactId} has no article identity`);
    }
    const conflicting = this.#db.prepare(
      "SELECT manuscript_artifact_id FROM magazine_manuscript_revisions WHERE revision_id = ?",
    ).get(revisionId) as { readonly manuscript_artifact_id: ArtifactId } | undefined;
    if (conflicting !== undefined && conflicting.manuscript_artifact_id !== manuscriptArtifactId) {
      throw new ArtifactLedgerError("SCHEMA_MIGRATION_CONFLICT", `Revision ${revisionId} is already bound to another manuscript`);
    }
    this.#db.prepare(
      `INSERT INTO magazine_manuscript_revisions(
         revision_id, manuscript_artifact_id, article_id, registered_at
       ) VALUES (?, ?, ?, ?)`,
    ).run(revisionId, manuscriptArtifactId, articleId, this.#clock.now().toISOString());
    return revisionId;
  }

  private parentRows(artifactId: ArtifactId): readonly ArtifactParent[] {
    return this.#db.prepare(
      "SELECT parent_artifact_id AS artifactId, relation FROM magazine_artifact_edges WHERE child_artifact_id = ? ORDER BY ordinal",
    ).all(artifactId) as readonly ArtifactParent[];
  }
}

const humanDecisionAuthorityToken = Symbol("magazine.humanDecisionAuthority");

/**
 * Private implementation of the human decision facade. It is deliberately
 * not exported. The only way to obtain it is ArtifactLedger's factory, which
 * captures the persistence closure over the ledger's private method.
 */
class HumanDecisionAuthorityImpl implements HumanDecisionAuthority {
  readonly #ledger: ArtifactLedger;
  readonly #persist: (input: HumanDecisionPersistenceInput) => LedgerDecision;
  readonly #clock: { readonly now: () => Date };

  constructor(
    token: typeof humanDecisionAuthorityToken,
    ledger: ArtifactLedger,
    persist: (input: HumanDecisionPersistenceInput) => LedgerDecision,
    clock: { readonly now: () => Date },
  ) {
    if (token !== humanDecisionAuthorityToken) {
      throw new ArtifactLedgerError("HUMAN_AUTHORITY_REQUIRED", "Human decision authorities must be created by ArtifactLedger");
    }
    this.#ledger = ledger;
    this.#persist = persist;
    this.#clock = clock;
  }

  async decide(
    human: AuthenticatedHuman,
    request: ArticleDecisionRequest,
    durableContext: WorkflowWaitContext,
  ): Promise<LedgerDecision> {
    if (!(human instanceof AuthorizedWorker)) {
      throw new ArtifactLedgerError(
        "HUMAN_AUTHORITY_REQUIRED",
        "A decision requires an AuthorizedWorker session minted by LocalAuthorityStore",
      );
    }
    const description = await human.describe();
    if (description.authority !== "human" || description.grantIds.length === 0 || description.capabilities.length === 0) {
      throw new ArtifactLedgerError(
        "HUMAN_AUTHORITY_REQUIRED",
        "Only an authenticated human with active capabilities may answer an article decision offer",
      );
    }
    const boundary = this.#loadBoundary(request, durableContext);
    if (request.rationale.trim().length === 0) {
      throw new ArtifactLedgerError("DECISION_INVALID", "A human decision requires a rationale");
    }
    const editorDecision: ArticleEditorDecision = {
      choice: request.choice,
      ...(request.approvedFindingIds === undefined ? {} : { approvedFindingIds: request.approvedFindingIds }),
      ...(request.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: request.additionalRewriteBudget }),
    };
    const validation = this.#validate(boundary.route, editorDecision);
    const existing = this.#ledger.getDecision(request.offerId);
    if (existing !== undefined) {
      if (!sameHumanDecision(existing, request, description, durableContext, validation)) {
        throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${request.offerId} already has a different validated decision`);
      }
      return existing;
    }
    if (boundary.offer.status !== "active") {
      throw new ArtifactLedgerError("OFFER_STALE", `Offer ${request.offerId} is no longer active`);
    }

    const rationale = request.rationale.trim();
    const artifactId = decisionArtifactId(request.offerId);
    const artifact = {
      id: artifactId,
      kind: "article_human_decision",
      schemaVersion: "article-human-decision/1",
      mediaType: "application/json",
      origin: "human",
      payload: {
        kind: "json",
        value: {
          schemaVersion: "article-human-decision/1",
          offerId: request.offerId,
          taskArtifactId: request.taskArtifactId,
          inputArtifactIds: request.inputArtifactIds,
          principalId: description.principalId,
          credentialProfileId: description.credentialProfileId,
          capabilities: description.capabilities,
          choice: request.choice,
          rationale,
          ...(request.approvedFindingIds === undefined ? {} : { approvedFindingIds: request.approvedFindingIds }),
          ...(request.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: request.additionalRewriteBudget }),
          validatorVersion: validation.validatorVersion,
          canonicalApprovedFindingIds: validation.canonicalApprovedFindingIds,
          rewriteBudget: validation.rewriteBudget,
        },
      },
      parents: [
        { artifactId: request.taskArtifactId, relation: "decision_task" },
        ...request.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_input" })),
      ],
      metadata: {
        offerId: request.offerId,
        principalId: description.principalId,
        credentialProfileId: description.credentialProfileId,
        capabilities: description.capabilities,
        choice: request.choice,
        ...(request.approvedFindingIds === undefined ? {} : { approvedFindingIds: request.approvedFindingIds }),
        ...(request.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: request.additionalRewriteBudget }),
        validatorVersion: validation.validatorVersion,
        canonicalApprovedFindingIds: validation.canonicalApprovedFindingIds,
        rewriteBudget: validation.rewriteBudget,
      },
      runId: request.runId,
      durableContext,
    } as const;
    const decision = {
      id: `decision-${safeIdentity(request.offerId)}`,
      runId: request.runId,
      offerId: request.offerId,
      taskArtifactId: request.taskArtifactId,
      inputArtifactIds: request.inputArtifactIds,
      principalId: description.principalId,
      credentialProfileId: description.credentialProfileId,
      choice: request.choice,
      ...(request.approvedFindingIds === undefined ? {} : { approvedFindingIds: request.approvedFindingIds }),
      ...(request.additionalRewriteBudget === undefined ? {} : { additionalRewriteBudget: request.additionalRewriteBudget }),
      rationale,
      artifactId,
      durableContext,
      createdAt: this.#clock.now().toISOString(),
    } as const;
    // The closure is the only path to persistence. Validation is rebuilt by
    // the ledger from its immutable evidence before the row is written.
    return this.#persist({ decision, artifact });
  }

  #validate(route: ArticleReviewRoute, decision: ArticleEditorDecision): ValidatedArticleEditorDecision {
    const parsed = articleEditorDecisionSchema.safeParse(decision);
    if (!parsed.success) {
      throw new ArtifactLedgerError("DECISION_VALIDATION_INVALID", "editor decision is not a strict article decision contract");
    }
    try {
      validateArticleEditorDecision(route, parsed.data as ArticleEditorDecision);
      return validatedArticleEditorDecision(route, parsed.data as ArticleEditorDecision);
    } catch (error) {
      throw new ArtifactLedgerError("DECISION_VALIDATION_INVALID", error instanceof Error ? error.message : "editor decision failed authority validation", { cause: error });
    }
  }

  #loadBoundary(request: ArticleDecisionRequest, durableContext: WorkflowWaitContext): {
    readonly task: ArticleDecisionTask;
    readonly brief: RevisionBrief;
    readonly route: ArticleReviewRoute;
    readonly offer: LedgerOffer;
  } {
    const run = this.#ledger.requireRun(request.runId);
    const offer = this.#ledger.requireOffer(request.offerId);
    if (offer.runId !== run.runId) throw new ArtifactLedgerError("OFFER_RUN_MISMATCH", `Offer ${request.offerId} belongs to another run`);
    if (offer.taskArtifactId !== request.taskArtifactId || !sameStrings(offer.inputArtifactIds, request.inputArtifactIds)) {
      throw new ArtifactLedgerError("OFFER_INPUT_MISMATCH", "Decision task and inputs are not the exact active offer evidence");
    }
    if (!offer.allowedChoices.includes(request.choice)) {
      throw new ArtifactLedgerError("CHOICE_INVALID", `Choice ${request.choice} is not allowed by the active offer`);
    }
    assertWaitContext(durableContext, request.runId);
    const taskArtifact = this.#ledger.requireArtifact(offer.taskArtifactId);
    if (taskArtifact.kind !== "article_decision_request" || taskArtifact.schemaVersion !== "article-decision-request/1") {
      throw new ArtifactLedgerError("DECISION_TASK_INVALID", "active decision task has the wrong artifact contract");
    }
    const task = parseLedgerArtifact(this.#ledger, offer.taskArtifactId, taskArtifact, articleDecisionTaskSchema, "article decision task") as ArticleDecisionTask;
    if (
      task.runId !== run.runId
      || task.articleExecutionId !== run.articleExecutionId
      || task.articleId !== run.articleId
      || task.expectedDecisionArtifactId !== decisionArtifactId(offer.id)
      || !sameStrings(task.inputArtifactIds, offer.inputArtifactIds)
      || !sameStrings(task.allowedChoices, ["accept", "revise", "drop"])
      || request.taskArtifactId !== offer.taskArtifactId
    ) {
      throw new ArtifactLedgerError("DECISION_TASK_INVALID", "decision task is not bound to the exact run and offer");
    }
    if (durableContext.key !== articleDecisionWaitKey(task.cycleId)) {
      throw new ArtifactLedgerError("DECISION_PROVENANCE_INVALID", "decision wait key is not scoped to the exact review cycle");
    }
    const briefArtifact = this.#ledger.requireArtifact(task.revisionBriefArtifactId);
    const routeArtifact = this.#ledger.requireArtifact(task.routeArtifactId);
    if (briefArtifact.kind !== "article_revision_brief" || briefArtifact.schemaVersion !== "article-revision-brief/1") {
      throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", "decision task references the wrong revision brief artifact");
    }
    if (routeArtifact.kind !== "article_review_route" || routeArtifact.schemaVersion !== "article-review-route/1") {
      throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", "decision task references the wrong review route artifact");
    }
    const brief = parseLedgerArtifact(this.#ledger, task.revisionBriefArtifactId, briefArtifact, revisionBriefSchema, "revision brief") as RevisionBrief;
    const route = parseLedgerArtifact(this.#ledger, task.routeArtifactId, routeArtifact, articleReviewRouteSchema, "review route") as ArticleReviewRoute;
    if (
      route.outcome !== "editor_wait"
      || !sameStrings(route.allowedChoices, task.allowedChoices)
      || brief.articleId !== task.articleId
      || brief.manuscriptArtifactId !== task.manuscriptArtifactId
      || brief.iterationId !== task.iterationId
      || route.articleId !== brief.articleId
      || route.manuscriptArtifactId !== brief.manuscriptArtifactId
      || route.iterationId !== brief.iterationId
      || brief.cycleId !== task.cycleId
      || route.cycleId !== task.cycleId
      || brief.manuscriptRevisionId !== task.manuscriptRevisionId
      || route.manuscriptRevisionId !== task.manuscriptRevisionId
      || brief.reviewPlanArtifactId !== task.reviewPlanArtifactId
      || route.reviewPlanArtifactId !== task.reviewPlanArtifactId
      || brief.rewriteOrdinal !== task.rewriteOrdinal
      || route.rewriteOrdinal !== task.rewriteOrdinal
      || !sameParentsWithRelation(taskArtifact.parents, task.inputArtifactIds, "decision_evidence")
      || !sameParentsWithRelation(routeArtifact.parents, [task.revisionBriefArtifactId], "revision_brief")
      || !sameStrings(briefArtifact.parents.map((parent) => parent.artifactId), revisionBriefParents({ brief }))
    ) {
      throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", "decision task, brief, route, and immutable parents do not match");
    }
    return { task, brief, route, offer };
  }
}

const articleAttemptRunnerToken = Symbol("magazine.articleAttemptRunner");

/**
 * Magazine-owned model/tool seam. It authenticates through LocalAuthorityStore,
 * claims through the magazine ledger, and never calls Loops agent(). A caller
 * wraps this ordinary function in a durable Loops step when it needs a
 * checkpoint. The constructor token is module-private; callers obtain this
 * facade only from ArtifactLedger.createArticleAttemptRunner().
 */
export class ArticleAttemptRunner {
  readonly #store: ArticleAttemptStoreInternal;

  constructor(token: typeof articleAttemptRunnerToken, store: ArticleAttemptStoreInternal) {
    if (token !== articleAttemptRunnerToken) {
      throw new ArtifactLedgerError("ATTEMPT_AUTHORITY_REQUIRED", "Article attempt runners must be created by ArtifactLedger");
    }
    this.#store = store;
  }

  async claimModel(worker: AuthorizedWorker, request: ArticleAttemptRequest): Promise<ArticleAttemptClaim> {
    return await this.#claim(worker, { ...request, role: "model" });
  }

  async claimTool(worker: AuthorizedWorker, request: ArticleAttemptRequest): Promise<ArticleAttemptClaim> {
    return await this.#claim(worker, { ...request, role: "tool" });
  }

  async executeModel<T>(
    worker: AuthorizedWorker,
    request: ArticleAttemptRequest,
    operation: ArticleAttemptOperation<T>,
  ): Promise<ArticleAttemptExecutionResult<T>> {
    return await this.#execute(worker, { ...request, role: "model" }, operation);
  }

  async executeTool<T>(
    worker: AuthorizedWorker,
    request: ArticleAttemptRequest,
    operation: ArticleAttemptOperation<T>,
  ): Promise<ArticleAttemptExecutionResult<T>> {
    return await this.#execute(worker, { ...request, role: "tool" }, operation);
  }

  heartbeat(claim: ArticleAttemptClaim): ArticleAttemptClaim {
    return this.#store.heartbeatArticleAttempt(claim);
  }

  async #claim(
    worker: AuthorizedWorker,
    input: ArticleAttemptRequest & { readonly role: "model" | "tool" },
  ): Promise<ArticleAttemptClaim> {
    if (!(worker instanceof AuthorizedWorker)) {
      throw new Error("Article attempts require an AuthorizedWorker session minted by LocalAuthorityStore");
    }
    assertArticleExecutionMaterials({
      articleId: input.articleId,
      manuscriptArtifactId: input.manuscriptArtifactId,
      access: input.access,
      materials: input.materials,
    });
    const manuscript = this.#requireManuscript(input.manuscriptArtifactId);
    const rawRevision = manuscript.metadata.revisionId;
    if (typeof rawRevision !== "string" || rawRevision.trim().length === 0) {
      throw new ArtifactLedgerError("ATTEMPT_REVISION_REQUIRED", `Manuscript ${input.manuscriptArtifactId} has no immutable revisionId metadata`);
    }
    if (input.manuscriptRevisionId !== undefined && input.manuscriptRevisionId !== rawRevision) {
      throw new ArtifactLedgerError("ATTEMPT_REVISION_MISMATCH", "Caller manuscriptRevisionId does not match immutable manuscript metadata");
    }
    const durableContext = readAttemptContext(input);
    const operationInputDigest = digestArticleAttemptInput(input, rawRevision as ManuscriptRevisionId);
    this.#store.registerManuscriptRevision({ manuscriptArtifactId: input.manuscriptArtifactId, articleId: input.articleId });
    const identity = await worker.describe();
    assertWorkerIdentity(identity, input.role, input.access);
    const claimInput: ArticleAttemptClaimInput = {
      articleExecutionId: input.articleExecutionId,
      rootRunId: input.rootRunId,
      articleId: input.articleId,
      operationKey: input.operationKey,
      role: input.role,
      access: input.access,
      manuscriptArtifactId: input.manuscriptArtifactId,
      operationInputDigest,
      principalId: identity.principalId,
      credentialProfileId: identity.credentialProfileId,
      // This is the authenticated authority, never a role-derived guess.
      authority: identity.authority,
      capabilities: identity.capabilities,
      durableContext,
      ...(input.leaseMs === undefined ? {} : { leaseMs: input.leaseMs }),
    };
    return this.#store.claimArticleAttempt(claimInput);
  }

  async #execute<T>(
    worker: AuthorizedWorker,
    input: ArticleAttemptRequest & { readonly role: "model" | "tool" },
    operation: ArticleAttemptOperation<T>,
  ): Promise<ArticleAttemptExecutionResult<T>> {
    const operationInputDigest = digestArticleAttemptInput(input, this.#requireManuscript(input.manuscriptArtifactId).metadata.revisionId as ManuscriptRevisionId);
    let claim: ArticleAttemptClaim;
    try {
      claim = await this.#claim(worker, input);
    } catch (error) {
      // A replay after a committed winner is a normal no-value loser. Active
      // contention is not a terminal result and must reach the durable retry
      // policy as ATTEMPT_UNAVAILABLE.
      if (error instanceof Error && "code" in error && (error as { readonly code?: unknown }).code === "ATTEMPT_ALREADY_SELECTED") {
        const adopted = this.#store.readSelectedArticleAttempt({
          articleExecutionId: input.articleExecutionId,
          operationKey: input.operationKey,
          operationInputDigest,
        });
        if (adopted !== undefined && adopted.length > 0) {
          return { selected: true, adopted: true, artifacts: Object.freeze(adopted) };
        }
        return { selected: false, reason: "already_selected", artifacts: [] };
      }
      throw error;
    }
    try {
      const result = await operation({ claim, materials: input.materials });
      const artifacts: LedgerArtifact[] = [];
      for (const artifact of result.artifacts ?? []) {
        artifacts.push(this.#store.createArticleAttemptArtifact({
          claim,
          key: artifact.key,
          artifact,
        }));
      }
      const committed = this.#store.completeArticleAttempt(claim, artifacts.map((artifact) => artifact.id));
      if (committed.selected && committed.status === "already_selected") {
        const adopted = this.#store.readSelectedArticleAttempt({
          articleExecutionId: input.articleExecutionId,
          operationKey: input.operationKey,
          operationInputDigest,
        });
        if (adopted !== undefined && adopted.length > 0) {
          return { selected: true, adopted: true, claim, artifacts: Object.freeze(adopted) };
        }
        return { selected: false, reason: "already_selected", claim, artifacts: [] };
      }
      if (!committed.selected) {
        if (committed.status === "already_selected") {
          const adopted = this.#store.readSelectedArticleAttempt({
            articleExecutionId: input.articleExecutionId,
            operationKey: input.operationKey,
            operationInputDigest,
          });
          if (adopted !== undefined && adopted.length > 0) {
            return { selected: true, adopted: true, claim, artifacts: Object.freeze(adopted) };
          }
        }
        return { selected: false, reason: committed.status === "stale" ? "stale" : "already_selected", claim, artifacts: Object.freeze(artifacts) };
      }
      return { selected: true, value: result.value, claim, artifacts: Object.freeze(artifacts) };
    } catch (error) {
      this.#store.failArticleAttempt(claim);
      throw error;
    }
  }

  #requireManuscript(_artifactId: ArtifactId): LedgerArtifact {
    // The store closure validates and reads the artifact as part of claim. A
    // dedicated reader is supplied by the factory to keep the runner unaware
    // of the ledger's database and public query surface.
    return this.#store.requireArtifact(_artifactId);
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
  readonly choice: "accept" | "revise" | "drop";
  readonly rationale: string;
  readonly approved_finding_ids_json: string | null;
  readonly additional_rewrite_budget: number | null;
  readonly validator_version: string | null;
  readonly canonical_approved_finding_ids_json: string | null;
  readonly rewrite_budget_json: string | null;
  readonly artifact_id: ArtifactId;
  readonly durable_context_json: string | null;
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

type ArticleAttemptRow = {
  readonly claim_id: AttemptId;
  readonly article_execution_id: ArticleExecutionId;
  readonly run_id: RunId;
  readonly article_id: string;
  readonly operation_key: string;
  readonly role: "model" | "tool";
  readonly access: "source_aware" | "source_blind" | "tool";
  readonly manuscript_artifact_id: ArtifactId;
  readonly manuscript_revision_id: string | null;
  readonly operation_input_digest: string | null;
  readonly attempt_id: string;
  readonly attempt_number: number;
  readonly fence: number;
  readonly principal_id: string;
  readonly credential_profile_id: string;
  readonly authority: "model" | "tool";
  readonly capabilities_json: string;
  readonly status: "active" | "completed" | "failed" | "stale";
  readonly lease_expires_at_ms: number;
  readonly durable_context_json: string;
  readonly output_artifact_ids_json: string | null;
  readonly created_at: string;
  readonly finished_at: string | null;
};

type ManuscriptRevisionRow = {
  readonly revision_id: ManuscriptRevisionId;
  readonly manuscript_artifact_id: ArtifactId;
  readonly article_id: string;
  readonly registered_at: string;
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

function requireMigrationText(value: unknown, column: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ArtifactLedgerError("SCHEMA_MIGRATION_UNBACKFILLABLE", `Article exposure migration cannot backfill ${column}`);
  }
  return value;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function textValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readArtifactIdArray(value: unknown): readonly ArtifactId[] {
  if (!Array.isArray(value) || value.some((candidate) => typeof candidate !== "string" || candidate.trim().length === 0)) return [];
  return value as readonly ArtifactId[];
}

function sameParentsWithRelation(
  actual: readonly { readonly artifactId: ArtifactId; readonly relation: string }[],
  expectedIds: readonly ArtifactId[],
  relation: string,
): boolean {
  return actual.length === expectedIds.length
    && actual.every((parent, index) => parent.artifactId === expectedIds[index] && parent.relation === relation);
}

function sameHumanDecision(
  existing: LedgerDecision,
  request: ArticleDecisionRequest,
  description: Awaited<ReturnType<AuthorizedWorker["describe"]>>,
  durableContext: WorkflowWaitContext,
  validation: ValidatedArticleEditorDecision,
): boolean {
  return existing.runId === request.runId
    && existing.offerId === request.offerId
    && existing.taskArtifactId === request.taskArtifactId
    && sameStrings(existing.inputArtifactIds, request.inputArtifactIds)
    && existing.choice === request.choice
    && existing.rationale === request.rationale.trim()
    && JSON.stringify(existing.approvedFindingIds ?? null) === JSON.stringify(request.approvedFindingIds ?? null)
    && existing.additionalRewriteBudget === request.additionalRewriteBudget
    && existing.validatorVersion === validation.validatorVersion
    && sameStrings(existing.canonicalApprovedFindingIds ?? [], validation.canonicalApprovedFindingIds)
    && JSON.stringify(existing.rewriteBudget ?? null) === JSON.stringify(validation.rewriteBudget)
    && existing.principalId === description.principalId
    && existing.credentialProfileId === description.credentialProfileId
    && JSON.stringify(existing.durableContext ?? null) === JSON.stringify(durableContext);
}

function sameValidatedDecision(
  persisted: LedgerDecision,
  expected: Omit<LedgerDecision, "createdAt" | "validatorVersion" | "canonicalApprovedFindingIds" | "rewriteBudget">,
  validation: ValidatedArticleEditorDecision,
): boolean {
  return persisted.runId === expected.runId
    && persisted.offerId === expected.offerId
    && persisted.taskArtifactId === expected.taskArtifactId
    && sameStrings(persisted.inputArtifactIds, expected.inputArtifactIds)
    && persisted.principalId === expected.principalId
    && persisted.credentialProfileId === expected.credentialProfileId
    && persisted.choice === expected.choice
    && persisted.rationale === expected.rationale
    && JSON.stringify(persisted.approvedFindingIds ?? []) === JSON.stringify(expected.approvedFindingIds ?? [])
    && (persisted.additionalRewriteBudget ?? 0) === (expected.additionalRewriteBudget ?? 0)
    && persisted.artifactId === expected.artifactId
    && persisted.validatorVersion === validation.validatorVersion
    && sameStrings(persisted.canonicalApprovedFindingIds ?? [], validation.canonicalApprovedFindingIds)
    && JSON.stringify(persisted.rewriteBudget ?? null) === JSON.stringify(validation.rewriteBudget)
    && JSON.stringify(persisted.durableContext ?? null) === JSON.stringify(expected.durableContext ?? null);
}

function assertAttemptAccess(input: ArticleAttemptClaimInput): void {
  if (input.role === "model" && input.authority !== "model") {
    throw new ArtifactLedgerError("ATTEMPT_AUTHORITY_MISMATCH", "Model article work requires model authority");
  }
  if (input.role === "tool" && input.authority !== "tool") {
    throw new ArtifactLedgerError("ATTEMPT_AUTHORITY_MISMATCH", "Tool article work requires tool authority");
  }
  const capabilities = new Set(input.capabilities);
  if (input.role === "model" && !capabilities.has("text_model")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Model article work requires text_model capability");
  }
  if (input.role === "tool" && !capabilities.has("subprocess")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Tool article work requires subprocess capability");
  }
  if (input.access === "source_aware" && !capabilities.has("source_access")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Source-aware article work requires source_access capability");
  }
  if (input.access === "source_blind" && !capabilities.has("source_blind")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Source-blind article work requires source_blind capability");
  }
  if (input.role === "tool" && input.access !== "tool") {
    throw new ArtifactLedgerError("ATTEMPT_ACCESS_INVALID", "Tool article work must use tool access");
  }
  if (input.role === "model" && input.access === "tool") {
    throw new ArtifactLedgerError("ATTEMPT_ACCESS_INVALID", "Model article work cannot use tool access");
  }
}

function assertWorkerIdentity(
  identity: AuthorizedWorkerDescription,
  role: "model" | "tool",
  access: ArticleAttemptRequest["access"],
): asserts identity is AuthorizedWorkerDescription & { readonly authority: "model" | "tool" } {
  if (role === "model" && identity.authority !== "model") {
    throw new ArtifactLedgerError("ATTEMPT_AUTHORITY_MISMATCH", "Model article work requires an authenticated model authority");
  }
  if (role === "tool" && identity.authority !== "tool") {
    throw new ArtifactLedgerError("ATTEMPT_AUTHORITY_MISMATCH", "Tool article work requires an authenticated tool authority");
  }
  const capabilities = new Set(identity.capabilities);
  if (role === "model" && !capabilities.has("text_model")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Model article work requires text_model capability");
  }
  if (role === "tool" && !capabilities.has("subprocess")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Tool article work requires subprocess capability");
  }
  if (access === "source_aware" && !capabilities.has("source_access")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Source-aware article work requires source_access capability");
  }
  if (access === "source_blind" && !capabilities.has("source_blind")) {
    throw new ArtifactLedgerError("ATTEMPT_CAPABILITY_MISMATCH", "Source-blind article work requires source_blind capability");
  }
  if (role === "tool" && access !== "tool") {
    throw new ArtifactLedgerError("ATTEMPT_ACCESS_INVALID", "Tool article work must use tool access");
  }
  if (role === "model" && access === "tool") {
    throw new ArtifactLedgerError("ATTEMPT_ACCESS_INVALID", "Model article work cannot use tool access");
  }
}

function assertWaitContext(context: WorkflowWaitContext, runId: RunId): void {
  if (
    context.kind !== "wait" ||
    context.runId !== runId ||
    context.invocationId.length === 0 ||
    context.workflowName.length === 0 ||
    context.workflowVersion.length === 0 ||
    context.callId.length === 0 ||
    context.waitId.length === 0 ||
    context.key.length === 0 ||
    "attemptId" in (context as object) ||
    "attemptNumber" in (context as object)
  ) {
    throw new ArtifactLedgerError("DECISION_PROVENANCE_INVALID", "Human decisions require exact wait provenance without attempt fields");
  }
}

function assertAttemptContextBinding(
  context: WorkflowAttemptContext,
  input: ArticleAttemptRequest,
): void {
  if (
    (context.kind !== "agent" && context.kind !== "step")
    || context.runId !== input.rootRunId
    || context.invocationId.length === 0
    || context.workflowName.length === 0
    || context.workflowVersion.length === 0
    || context.callId.length === 0
    || context.attemptId.length === 0
    || context.key.length === 0
    || context.key !== input.operationKey
    || !Number.isSafeInteger(context.attemptNumber)
    || context.attemptNumber < 1
  ) {
    throw new ArtifactLedgerError(
      "ATTEMPT_PROVENANCE_INVALID",
      "Article attempts require exact Loops run, invocation, call, attempt, and operation provenance",
    );
  }
}

/**
 * Read attempt provenance from Loops' own async-local context.  Magazine does
 * not install or accept a caller-supplied equivalent: outside a real Loops
 * call the public primitive throws, which is deliberately reported as a
 * missing provenance failure.
 */
function readAttemptContext(input: ArticleAttemptRequest): WorkflowAttemptContext {
  let raw: ReturnType<typeof loopsDurableContext>;
  try {
    raw = loopsDurableContext();
  } catch {
    throw new ArtifactLedgerError(
      "ATTEMPT_PROVENANCE_REQUIRED",
      "Article attempts may run only inside a real Loops step or agent callback",
    );
  }
  if (raw === undefined) {
    throw new ArtifactLedgerError(
      "ATTEMPT_PROVENANCE_REQUIRED",
      "Article attempts require exact Loops attempt provenance",
    );
  }
  const {
    runId,
    invocationId,
    workflowName,
    workflowVersion,
    workflowPin,
    callId,
    attemptId,
    attemptNumber: rawAttemptNumber,
    key,
    kind,
  } = raw;
  if (
    typeof runId !== "string" || runId.length === 0
    || typeof invocationId !== "string" || invocationId.length === 0
    || typeof workflowName !== "string" || workflowName.length === 0
    || typeof workflowVersion !== "string" || workflowVersion.length === 0
    || (workflowPin !== undefined && (
      typeof workflowPin !== "object"
      || workflowPin === null
      || Array.isArray(workflowPin)
    ))
    || (kind !== "agent" && kind !== "step")
    || typeof callId !== "string" || callId.length === 0
    || typeof attemptId !== "string" || attemptId.length === 0
    || typeof rawAttemptNumber !== "number" || !Number.isSafeInteger(rawAttemptNumber) || rawAttemptNumber < 1
    || typeof key !== "string" || key.length === 0
  ) {
    throw new ArtifactLedgerError(
      "ATTEMPT_PROVENANCE_INVALID",
      "Article attempts require exact Loops invocation, call, attempt, and workflow provenance",
    );
  }
  const context: WorkflowAttemptContext = {
    runId,
    invocationId,
    workflowName,
    workflowVersion,
    ...(workflowPin === undefined ? {} : { workflowPin: workflowPin as JsonObject }),
    callId,
    attemptId,
    attemptNumber: rawAttemptNumber,
    key,
    kind,
  };
  assertAttemptContextBinding(context, input);
  return context;
}

function articleAttemptContext(
  input: ArticleAttemptClaimInput,
  run: LedgerRun,
): WorkflowAttemptContext {
  const supplied = input.durableContext;
  if (supplied === undefined || supplied === null || typeof supplied !== "object") {
    throw new ArtifactLedgerError("ATTEMPT_PROVENANCE_INVALID", "Article attempts require exact Loops attempt provenance");
  }
  if (supplied.runId !== run.loopsRunId) {
    throw new ArtifactLedgerError("ATTEMPT_PROVENANCE_INVALID", "Article attempt Loops run does not match the magazine run");
  }
  if (
    supplied.kind !== "agent" && supplied.kind !== "step"
  ) {
    throw new ArtifactLedgerError("ATTEMPT_PROVENANCE_INVALID", "Article attempt requires an agent or step context, not a wait or workflow context");
  }
  if (
    supplied.invocationId.length === 0 ||
    supplied.workflowName.length === 0 ||
    supplied.workflowVersion.length === 0 ||
    supplied.callId.length === 0 ||
    supplied.attemptId.length === 0 ||
    supplied.key.length === 0 ||
    supplied.key !== input.operationKey ||
    !Number.isSafeInteger(supplied.attemptNumber) || supplied.attemptNumber < 1
  ) {
    throw new ArtifactLedgerError("ATTEMPT_PROVENANCE_INVALID", "Article attempt requires exact Loops invocation, call, attempt, and workflow provenance");
  }
  return supplied;
}

function matchesArticleAttempt(row: ArticleAttemptRow, claim: ArticleAttemptClaim): boolean {
  return row.claim_id === claim.claimId
    && row.article_execution_id === claim.articleExecutionId
    && row.operation_key === claim.operationKey
    && row.fence === claim.fence
    && row.attempt_id === claim.attemptId
    && row.manuscript_revision_id === claim.manuscriptRevisionId
    && row.operation_input_digest === claim.operationInputDigest
    && row.principal_id === claim.principalId;
}

function requireOperationInputDigest(value: string | null): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new ArtifactLedgerError("ATTEMPT_OPERATION_INPUT_MISMATCH", "Article attempt has no immutable operation input digest");
  }
  return value;
}

function articleAttemptArtifactId(claim: ArticleAttemptClaim, key: string): ArtifactId {
  const canonicalTuple = JSON.stringify([
    "article-attempt-artifact/1",
    claim.articleExecutionId,
    claim.operationKey,
    key,
    claim.attemptId,
  ]);
  return `art-attempt-${createHash("sha256").update(canonicalTuple, "utf8").digest("hex")}` as ArtifactId;
}

/** Digest the exact immutable operation inputs before a claim is persisted. */
function digestArticleAttemptInput(
  input: ArticleAttemptRequest & { readonly role: "model" | "tool" },
  manuscriptRevisionId: ManuscriptRevisionId,
): string {
  const material = input.materials.artifacts.map((artifact) => ({
    artifactId: artifact.artifactId,
    articleId: artifact.articleId,
    classification: artifact.classification,
  }));
  const value = [
    "article-attempt-input/1",
    input.articleExecutionId,
    input.articleId,
    input.operationKey,
    input.role,
    input.access,
    input.manuscriptArtifactId,
    manuscriptRevisionId,
    material,
  ];
  return `sha256:${createHash("sha256").update(JSON.stringify(value), "utf8").digest("hex")}`;
}

function articleAttemptFromRow(row: ArticleAttemptRow): ArticleAttemptClaim {
  const durableContext = JSON.parse(row.durable_context_json) as WorkflowDurableContext;
  return {
    schemaVersion: "article-attempt-claim/1",
    articleExecutionId: row.article_execution_id,
    articleId: row.article_id,
    operationKey: row.operation_key,
    role: row.role,
    access: row.access,
    manuscriptArtifactId: row.manuscript_artifact_id,
    manuscriptRevisionId: row.manuscript_revision_id as ManuscriptRevisionId,
    operationInputDigest: requireOperationInputDigest(row.operation_input_digest),
    claimId: row.claim_id,
    claimSequence: row.attempt_number,
    attemptId: row.attempt_id,
    attemptNumber: durableContext.kind === "workflow" || durableContext.kind === "wait"
      ? (() => { throw new ArtifactLedgerError("ATTEMPT_PROVENANCE_INVALID", `Article attempt ${row.claim_id} has non-attempt durable context`); })()
      : durableContext.attemptNumber,
    fence: row.fence,
    principalId: row.principal_id,
    credentialProfileId: row.credential_profile_id,
    authority: row.authority,
    capabilities: JSON.parse(row.capabilities_json) as readonly string[],
    leaseExpiresAt: new Date(row.lease_expires_at_ms).toISOString(),
    durableContext,
  };
}

function safeIdentity(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9_.:-]/gu, "_");
  return normalized.length > 180 ? normalized.slice(0, 180) : normalized;
}

function quoteIdentifier(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
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

function parseLedgerArtifact(
  ledger: ArtifactLedger,
  artifactId: ArtifactId,
  artifact: LedgerArtifact,
  schema: { readonly safeParse: (value: unknown) => { readonly success: boolean; readonly data?: unknown } },
  label: string,
): unknown {
  if (artifact.payloadKind !== "json" || artifact.mediaType !== "application/json") {
    throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", `${label} ${artifactId} is not canonical JSON evidence`);
  }
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(ledger.readArtifact(artifactId).bytes).toString("utf8")) as unknown;
  } catch (error) {
    throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", `${label} ${artifactId} is not valid JSON`, { cause: error });
  }
  const parsed = schema.safeParse(value);
  if (!parsed.success) throw new ArtifactLedgerError("DECISION_LINEAGE_INVALID", `${label} ${artifactId} does not match its strict schema`);
  return parsed.data;
}

function assertDecisionArtifactFacts(
  artifact: LedgerArtifactInput,
  decision: ArticleEditorDecisionRecordInput,
  validation: ValidatedArticleEditorDecision,
): void {
  if (artifact.kind !== "article_human_decision" || artifact.schemaVersion !== "article-human-decision/1" || artifact.mediaType !== "application/json" || artifact.origin !== "human" || artifact.payload.kind !== "json") {
    throw new ArtifactLedgerError("DECISION_ARTIFACT_INVALID", "editor decision artifact does not match the exact human decision contract");
  }
  const payload = artifact.payload.value;
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    throw new ArtifactLedgerError("DECISION_ARTIFACT_INVALID", "editor decision artifact payload must be a JSON object");
  }
  const value = payload as Record<string, unknown>;
  if (
    value.schemaVersion !== "article-human-decision/1"
    || value.offerId !== decision.offerId
    || value.taskArtifactId !== decision.taskArtifactId
    || !sameStrings(readStringArray(value.inputArtifactIds), decision.inputArtifactIds)
    || value.principalId !== decision.principalId
    || value.credentialProfileId !== decision.credentialProfileId
    || value.choice !== decision.choice
    || value.rationale !== decision.rationale
    || JSON.stringify(value.approvedFindingIds ?? null) !== JSON.stringify(decision.approvedFindingIds ?? null)
    || (value.additionalRewriteBudget as number | undefined) !== decision.additionalRewriteBudget
    || value.validatorVersion !== validation.validatorVersion
    || !sameStrings(readStringArray(value.canonicalApprovedFindingIds), validation.canonicalApprovedFindingIds)
    || JSON.stringify(value.rewriteBudget ?? null) !== JSON.stringify(validation.rewriteBudget)
  ) {
    throw new ArtifactLedgerError("DECISION_ARTIFACT_INVALID", "editor decision artifact does not carry the authority-derived facts");
  }
}

function readStringArray(value: unknown): readonly string[] {
  return Array.isArray(value) && value.every((candidate) => typeof candidate === "string")
    ? value as readonly string[]
    : [];
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
    articleExecutionId: row.article_execution_id ?? (`article-execution-${safeIdentity(row.run_id)}` as ArticleExecutionId),
    articleId: row.article_id,
    ...(row.edition_id === null ? {} : { editionId: row.edition_id }),
    workflowVersion: row.workflow_version,
    loopsRunId: row.loops_run_id,
    manuscriptArtifactId: row.manuscript_artifact_id,
    ...(row.current_revision_record_artifact_id === null || row.current_revision_record_artifact_id === undefined ? {} : { currentRevisionRecordArtifactId: row.current_revision_record_artifact_id }),
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
    allowedChoices: JSON.parse(row.allowed_choices_json) as readonly ("accept" | "revise" | "drop")[],
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
    ...(row.approved_finding_ids_json === null ? {} : { approvedFindingIds: JSON.parse(row.approved_finding_ids_json) as readonly string[] }),
    ...(row.additional_rewrite_budget === null ? {} : { additionalRewriteBudget: row.additional_rewrite_budget }),
    ...(row.validator_version === null ? {} : { validatorVersion: row.validator_version }),
    ...(row.canonical_approved_finding_ids_json === null ? {} : { canonicalApprovedFindingIds: JSON.parse(row.canonical_approved_finding_ids_json) as readonly ArticleFindingId[] }),
    ...(row.rewrite_budget_json === null ? {} : { rewriteBudget: JSON.parse(row.rewrite_budget_json) as ArticleDecisionBudgetSnapshot }),
    artifactId: row.artifact_id,
    ...(row.durable_context_json === null ? {} : { durableContext: JSON.parse(row.durable_context_json) as WorkflowWaitContext }),
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
