import { isDeepStrictEqual } from "node:util";

import type { AuthorizedWorker } from "../authority/local-authority.ts";
import type {
  ArtifactId,
  ArtifactView,
  JsonObject,
  RunId,
  RunView,
  WorkClaim,
  WorkOfferView,
} from "../contracts/index.ts";
import type { DurableCheckpointExecutor } from "../executors/durable-checkpoint.ts";
import type { ExecutorContext } from "../executors/types.ts";
import type { RunEngine } from "../run-engine/index.ts";
import type {
  DurableCheckpointResult,
  DurableLogicalItem,
  DurablePromotionRequest,
} from "./types.ts";

export type DurableBackfillExpectation = {
  readonly acceptedArtifactId: ArtifactId;
  readonly logicalItem: DurableLogicalItem;
};

export type DurableBackfillPlan = {
  readonly schemaVersion: "durable-backfill/1";
  readonly runId: RunId;
  readonly expectedCheckpoints: readonly DurableBackfillExpectation[];
};

export type DurableBackfillResult = {
  readonly runId: RunId;
  readonly checkpoints: readonly DurableCheckpointResult["result"][];
  readonly boundArtifactIds: readonly ArtifactId[];
};

/** Authenticated subprocess session permitted to claim durable checkpoints. */
export type DurableBackfillAuthority = {
  readonly worker: AuthorizedWorker;
};

export class DurableBackfillError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "DurableBackfillError";
    this.code = code;
  }
}

/**
 * Executes an exact migration inventory through ordinary public work offers.
 * It cannot invent tasks, revisions, decisions, or state transitions.
 */
export async function runDurableBackfill(
  engine: RunEngine,
  executor: DurableCheckpointExecutor,
  authority: DurableBackfillAuthority,
  plan: DurableBackfillPlan,
  signal: AbortSignal,
): Promise<DurableBackfillResult> {
  validatePlan(plan);
  const expected = new Map(plan.expectedCheckpoints.map((checkpoint) => [
    checkpointKey(checkpoint.acceptedArtifactId, checkpoint.logicalItem),
    checkpoint,
  ]));
  const completed = new Map<string, {
    readonly result: DurableCheckpointResult["result"];
    readonly artifactId: ArtifactId;
  }>();

  for (let cycle = 0; cycle <= plan.expectedCheckpoints.length; cycle += 1) {
    if (signal.aborted) throw new DurableBackfillError("DURABLE_BACKFILL_ABORTED", "durable backfill was canceled");
    const view = await engine.inspect(plan.runId);
    await collectBound(engine, view, expected, completed);
    if (completed.size === expected.size) {
      return result(plan.runId, plan.expectedCheckpoints, completed);
    }
    const offers = view.offers.filter((offer) =>
      offer.role === "durable_checkpoint" && offer.status === "offered"
    );
    if (offers.length === 0) break;
    for (const offer of offers) {
      const request = parseTask(await engine.readText(offer.taskArtifactId));
      const key = requestKey(request);
      if (!expected.has(key)) {
        throw new DurableBackfillError(
          "DURABLE_BACKFILL_UNPLANNED",
          `run exposed unplanned durable checkpoint ${key}`,
        );
      }
      if (completed.has(key)) {
        throw new DurableBackfillError(
          "DURABLE_BACKFILL_DUPLICATE",
          `run exposed a duplicate checkpoint for ${key}`,
        );
      }
      await answerOffer(engine, executor, authority, offer, signal);
    }
  }
  const missing = [...expected.keys()].filter((key) => !completed.has(key));
  throw new DurableBackfillError(
    "DURABLE_BACKFILL_INCOMPLETE",
    `run did not expose planned durable checkpoints: ${missing.join(", ")}`,
  );
}

async function answerOffer(
  engine: RunEngine,
  executor: DurableCheckpointExecutor,
  authority: DurableBackfillAuthority,
  offer: WorkOfferView,
  signal: AbortSignal,
): Promise<void> {
  const claim = await authority.worker.claim(engine, offer.id);
  try {
    const answer = await executor.execute({
      claim,
      offer,
      artifacts: engine,
      signal,
    } as ExecutorContext);
    await engine.answer(claim, answer);
  } catch (error) {
    await failClaim(engine, claim, error);
    throw error;
  }
}

async function failClaim(engine: RunEngine, claim: WorkClaim, error: unknown): Promise<void> {
  try {
    await engine.fail(claim, {
      classification: "permanent",
      message: error instanceof Error ? error.message : String(error),
      details: { operation: "durable_backfill" },
    });
  } catch {
    // The original error is authoritative. A stale/fenced failure is expected
    // if answer committed immediately before a transport failure.
  }
}

async function collectBound(
  engine: Pick<RunEngine, "readArtifact">,
  view: RunView,
  expected: ReadonlyMap<string, DurableBackfillExpectation>,
  completed: Map<string, {
    readonly result: DurableCheckpointResult["result"];
    readonly artifactId: ArtifactId;
  }>,
): Promise<void> {
  for (const artifact of view.artifacts.filter(isBoundArtifact)) {
    const payload = JSON.parse(Buffer.from((await engine.readArtifact(artifact.id)).bytes).toString("utf8")) as JsonObject;
    const request = boundRequest(payload);
    const key = requestKey(request);
    if (!expected.has(key)) continue;
    const result = boundResult(payload);
    const existing = completed.get(key);
    if (existing !== undefined && !isDeepStrictEqual(existing.result, result)) {
      throw new DurableBackfillError(
        "DURABLE_BACKFILL_DUPLICATE",
        `multiple durable bindings disagree for ${key}`,
      );
    }
    completed.set(key, { result, artifactId: artifact.id });
  }
}

function isBoundArtifact(artifact: ArtifactView): boolean {
  return artifact.kind === "durable_revision_bound" &&
    artifact.schemaVersion === "durable-revision-bound/1" &&
    artifact.mediaType === "application/json";
}

function parseTask(text: string): DurablePromotionRequest {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    throw new DurableBackfillError("DURABLE_BACKFILL_TASK_INVALID", "checkpoint task is not JSON", { cause: error });
  }
  if (!mapping(value) || value.schemaVersion !== "durable-checkpoint-request/1") {
    throw new DurableBackfillError("DURABLE_BACKFILL_TASK_INVALID", "checkpoint task has the wrong schema");
  }
  return value as unknown as DurablePromotionRequest;
}

function boundRequest(payload: JsonObject): DurablePromotionRequest {
  return {
    schemaVersion: "durable-checkpoint-request/1",
    promotionId: payload.promotionId as DurablePromotionRequest["promotionId"],
    revisionId: payload.revisionId as DurablePromotionRequest["revisionId"],
    runId: payload.runId as DurablePromotionRequest["runId"],
    logicalItem: payload.logicalItem as unknown as DurableLogicalItem,
    expectedParentRevisionId: payload.expectedParentRevisionId as DurablePromotionRequest["expectedParentRevisionId"],
    acceptedArtifactIds: payload.acceptedArtifactIds as readonly ArtifactId[],
    decisionArtifactIds: payload.decisionArtifactIds as readonly ArtifactId[],
    inputRevisions: payload.inputRevisions as DurablePromotionRequest["inputRevisions"],
    inputArtifactIds: payload.inputArtifactIds as readonly ArtifactId[],
  };
}

function boundResult(payload: JsonObject): DurableCheckpointResult["result"] {
  if (
    typeof payload.promotionId !== "string" ||
    typeof payload.revisionId !== "string" ||
    !mapping(payload.logicalItem) ||
    !mapping(payload.revisionRef) ||
    typeof payload.manifestDigest !== "string" ||
    typeof payload.gitCommitOid !== "string" ||
    !mapping(payload.gitBlobOids)
  ) {
    throw new DurableBackfillError("DURABLE_BACKFILL_BOUND_INVALID", "durable bound artifact is incomplete");
  }
  return {
    promotionId: payload.promotionId as DurableCheckpointResult["result"]["promotionId"],
    revisionId: payload.revisionId as DurableCheckpointResult["result"]["revisionId"],
    logicalItem: payload.logicalItem as unknown as DurableLogicalItem,
    expectedParentRevisionId: payload.expectedParentRevisionId as DurableCheckpointResult["result"]["expectedParentRevisionId"],
    manifestDigest: payload.manifestDigest,
    gitCommitOid: payload.gitCommitOid,
    gitBlobOids: payload.gitBlobOids as Readonly<Record<string, string>>,
    revisionRef: payload.revisionRef as unknown as DurableCheckpointResult["result"]["revisionRef"],
  };
}

function requestKey(request: DurablePromotionRequest): string {
  if (request.acceptedArtifactIds.length !== 1) {
    throw new DurableBackfillError("DURABLE_BACKFILL_TASK_INVALID", "checkpoint must name one accepted artifact");
  }
  return checkpointKey(request.acceptedArtifactIds[0]!, request.logicalItem);
}

function checkpointKey(artifactId: ArtifactId, item: DurableLogicalItem): string {
  switch (item.kind) {
    case "article":
    case "editorial":
      return `${artifactId}:${item.kind}:${item.editionId}:${item.logicalId}:${item.language}`;
    case "image":
      return `${artifactId}:image:${item.editionId}:${item.logicalId}`;
    case "composition":
      return `${artifactId}:composition:${item.editionId}:${item.compositionId}`;
  }
}

function result(
  runId: RunId,
  expected: readonly DurableBackfillExpectation[],
  completed: ReadonlyMap<string, {
    readonly result: DurableCheckpointResult["result"];
    readonly artifactId: ArtifactId;
  }>,
): DurableBackfillResult {
  const ordered = expected.map((checkpoint) =>
    completed.get(checkpointKey(checkpoint.acceptedArtifactId, checkpoint.logicalItem))!
  );
  return {
    runId,
    checkpoints: ordered.map((entry) => entry.result),
    boundArtifactIds: ordered.map((entry) => entry.artifactId),
  };
}

function validatePlan(plan: DurableBackfillPlan): void {
  if (plan.schemaVersion !== "durable-backfill/1" || plan.expectedCheckpoints.length === 0) {
    throw new DurableBackfillError("DURABLE_BACKFILL_PLAN_INVALID", "durable backfill plan is empty or invalid");
  }
  const keys = plan.expectedCheckpoints.map((checkpoint) =>
    checkpointKey(checkpoint.acceptedArtifactId, checkpoint.logicalItem)
  );
  if (new Set(keys).size !== keys.length) {
    throw new DurableBackfillError("DURABLE_BACKFILL_PLAN_INVALID", "durable backfill plan has duplicate checkpoints");
  }
}

function mapping(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
