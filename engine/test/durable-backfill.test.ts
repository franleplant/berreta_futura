import assert from "node:assert/strict";
import test from "node:test";

import type {
  ArtifactId,
  ArtifactView,
  AttemptId,
  PromotionId,
  RevisionId,
  RunId,
  RunView,
  WorkAnswer,
  WorkClaim,
  WorkOfferId,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  DurableBackfillError,
  runDurableBackfill,
  type DurableBackfillPlan,
  type DurablePromotionRequest,
} from "../durable/index.ts";
import { DurableCheckpointExecutor } from "../executors/durable-checkpoint.ts";
import type { RunEngine } from "../run-engine/index.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

const RUN_ID = "run_backfill" as RunId;
const ACCEPTED = "art_accepted" as ArtifactId;
const BOUND = "art_bound" as ArtifactId;
const TASK = "art_task" as ArtifactId;
const OFFER = "offer_checkpoint" as WorkOfferId;
const REVISION = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;

test("durable backfill executes and replays an exact declarative inventory through public offers", async (context) => {
  const harness = new BackfillEngine();
  const authority = await AuthorityTestHarness.create();
  context.after(async () => await authority.dispose());
  const worker = await authority.workerFor(harness.offer());
  const executor = executorFor(harness.request);
  const first = await runDurableBackfill(
    harness as unknown as RunEngine,
    executor,
    { worker },
    plan(),
    new AbortController().signal,
  );
  assert.equal(harness.claimCount, 1);
  assert.deepEqual(first.boundArtifactIds, [BOUND]);
  assert.equal(first.checkpoints[0]?.revisionId, REVISION);

  const replayed = await runDurableBackfill(
    harness as unknown as RunEngine,
    executor,
    { worker },
    plan(),
    new AbortController().signal,
  );
  assert.deepEqual(replayed, first);
  assert.equal(harness.claimCount, 1, "replay adopts the graph-visible durable binding");
});

test("durable backfill rejects an offer outside the declarative inventory", async (context) => {
  const harness = new BackfillEngine();
  const authority = await AuthorityTestHarness.create();
  context.after(async () => await authority.dispose());
  await assert.rejects(
    runDurableBackfill(
      harness as unknown as RunEngine,
      executorFor(harness.request),
      { worker: await authority.workerFor(harness.offer()) },
      {
        ...plan(),
        expectedCheckpoints: [{
          acceptedArtifactId: ACCEPTED,
          logicalItem: {
            kind: "article",
            editionId: "004",
            logicalId: "different",
            language: "en",
          },
        }],
      },
      new AbortController().signal,
    ),
    (error: unknown) => error instanceof DurableBackfillError && error.code === "DURABLE_BACKFILL_UNPLANNED",
  );
  assert.equal(harness.claimCount, 0);
});

function plan(): DurableBackfillPlan {
  return {
    schemaVersion: "durable-backfill/1",
    runId: RUN_ID,
    expectedCheckpoints: [{
      acceptedArtifactId: ACCEPTED,
      logicalItem: {
        kind: "article",
        editionId: "004",
        logicalId: "example",
        language: "en",
      },
    }],
  };
}

function executorFor(request: DurablePromotionRequest): DurableCheckpointExecutor {
  const result = checkpointResult(request);
  return new DurableCheckpointExecutor({
    checkpoint: async () => ({
      contractVersion: "durable-checkpoint/1",
      result,
      artifacts: [{
        kind: "durable_revision_evidence",
        schemaVersion: "durable-checkpoint/1",
        mediaType: "application/json",
        payload: { kind: "json", value: result },
      }],
    }),
  });
}

function checkpointResult(request: DurablePromotionRequest) {
  return {
    promotionId: request.promotionId,
    revisionId: request.revisionId,
    logicalItem: request.logicalItem,
    expectedParentRevisionId: request.expectedParentRevisionId,
    revisionRef: { ...request.logicalItem, revisionId: request.revisionId },
    manifestDigest: `sha256:${"c".repeat(64)}`,
    gitCommitOid: "a".repeat(40),
    gitBlobOids: { "durable/revision/manifest.yaml": "b".repeat(40) },
  };
}

class BackfillEngine {
  readonly request: DurablePromotionRequest = {
    schemaVersion: "durable-checkpoint-request/1",
    promotionId: "promotion_backfill" as PromotionId,
    revisionId: REVISION,
    runId: RUN_ID,
    logicalItem: {
      kind: "article",
      editionId: "004",
      logicalId: "example",
      language: "en",
    },
    expectedParentRevisionId: null,
    acceptedArtifactIds: [ACCEPTED],
    decisionArtifactIds: ["art_decision" as ArtifactId],
    inputRevisions: [],
    inputArtifactIds: ["art_input" as ArtifactId],
  };
  claimCount = 0;
  private answered = false;
  private boundBytes: Buffer | undefined;

  async inspect(): Promise<RunView> {
    return {
      id: RUN_ID,
      offers: [this.offer()],
      artifacts: this.answered ? [this.boundArtifact()] : [],
    } as unknown as RunView;
  }

  async readText(artifactId: ArtifactId): Promise<string> {
    assert.equal(artifactId, TASK);
    return JSON.stringify(this.request);
  }

  async readArtifact(artifactId: ArtifactId) {
    assert.equal(artifactId, BOUND);
    return { artifact: this.boundArtifact(), bytes: this.boundBytes! };
  }

  async claimAuthorized(): Promise<WorkClaim> {
    this.claimCount += 1;
    return {
      offerId: OFFER,
      attemptId: "attempt_backfill" as AttemptId,
      attemptFence: 1,
      ticket: "test-backfill-ticket",
      worker: {
        principalId: "durable-checkpoint",
        authority: "tool",
        capabilities: ["subprocess"],
      },
      leaseExpiresAt: "2026-08-02T21:00:00.000Z",
    };
  }

  async answer(_claim: WorkClaim, answer: WorkAnswer): Promise<RunView> {
    this.answered = true;
    this.boundBytes = Buffer.from(JSON.stringify({ ...this.request, ...answer.result }));
    return this.inspect();
  }

  async fail(): Promise<RunView> {
    throw new Error("unexpected failure");
  }

  async readBytes(artifactId: ArtifactId): Promise<Uint8Array> {
    return Buffer.from(await this.readText(artifactId));
  }

  offer(): WorkOfferView {
    return {
      id: OFFER,
      runId: RUN_ID,
      role: "durable_checkpoint",
      status: this.answered ? "answered" : "offered",
      taskArtifactId: TASK,
      allowedWorkerCapabilities: ["subprocess"],
    } as unknown as WorkOfferView;
  }

  private boundArtifact(): ArtifactView {
    return {
      id: BOUND,
      kind: "durable_revision_bound",
      schemaVersion: "durable-revision-bound/1",
      mediaType: "application/json",
    } as ArtifactView;
  }
}
