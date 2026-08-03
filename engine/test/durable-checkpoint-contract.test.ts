import assert from "node:assert/strict";
import { test } from "node:test";

import type { ArtifactId } from "../contracts/index.ts";
import { validateWorkResult } from "../run-engine/work-result-contracts.ts";

const artifactId = (value: string) => value as ArtifactId;

test("durable checkpoint requires one immutable revision evidence artifact", () => {
  const result = {
    promotionId: "promotion_actor_revision",
    revisionId: "revision_actor_1",
    logicalItem: {
      kind: "article",
      editionId: "004",
      logicalId: "one",
      revisionId: "revision_actor_1",
    },
    expectedParentRevisionId: null,
    revisionRef: {
      kind: "article",
      editionId: "004",
      logicalId: "one",
      revisionId: "revision_actor_1",
    },
    manifestDigest: `sha256:${"c".repeat(64)}`,
    gitCommitOid: "a".repeat(40),
    gitBlobOids: { "article.md": "b".repeat(40) },
  };
  const evidence = {
    id: artifactId("art-checkpoint-evidence"),
    kind: "durable_revision_evidence",
    schemaVersion: "durable-revision-evidence/1",
    mediaType: "application/json",
    payload: { kind: "json" as const, value: result },
  };

  assert.doesNotThrow(() =>
    validateWorkResult("durable_checkpoint", "durable-checkpoint/1", result, [evidence]),
  );
  assert.throws(
    () =>
      validateWorkResult("durable_checkpoint", "durable-checkpoint/1", result, []),
    { code: "ANSWER_ARTIFACTS_INVALID" },
  );
});
