import type {
  JsonObject,
  WorkAnswer,
  WorkOfferView,
} from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/index.ts";

/** A contract-valid synthetic checkpoint used only by generic engine harnesses. */
export async function durableCheckpointAnswer(
  engine: Pick<RunEngine, "readText">,
  offer: WorkOfferView,
): Promise<WorkAnswer> {
  const request = JSON.parse(await engine.readText(offer.taskArtifactId)) as {
    readonly promotionId: string;
    readonly revisionId: string;
    readonly logicalItem: JsonObject;
    readonly expectedParentRevisionId: string | null;
  };
  const result: JsonObject = {
    promotionId: request.promotionId,
    revisionId: request.revisionId,
    logicalItem: request.logicalItem,
    expectedParentRevisionId: request.expectedParentRevisionId,
    revisionRef: { ...request.logicalItem, revisionId: request.revisionId },
    manifestDigest: `sha256:${"c".repeat(64)}`,
    gitCommitOid: "a".repeat(40),
    gitBlobOids: { "durable/fixture/manifest.yaml": "b".repeat(40) },
  };
  return {
    contractVersion: offer.contractVersion,
    result,
    artifacts: [{
      kind: "durable_revision_evidence",
      schemaVersion: "durable-checkpoint/1",
      mediaType: "application/json",
      payload: { kind: "json", value: result },
    }],
  };
}
