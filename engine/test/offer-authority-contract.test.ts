import assert from "node:assert/strict";
import test from "node:test";

import type { ArtifactId, HumanDecisionIntent } from "../contracts/index.ts";
import { humanDecisionOffer } from "../machines/human-decision.ts";

test("human decision offers separate authority from capabilities and bind v3 intent inputs", () => {
  const requestId = "art-decision-request" as ArtifactId;
  const sourceArtifactId = "art-source" as ArtifactId;
  const effects = humanDecisionOffer({
    actorId: "actor-source" as never,
    actorKey: "source:one",
    state: "awaiting_review",
    role: "review_source",
    slot: "review",
    requestArtifactId: requestId,
    requestSchemaVersion: "source-review-request/1",
    requestKind: "source_review",
    inputArtifacts: [sourceArtifactId],
    allowedChoices: ["approve", "reject"],
    contractVersion: "review-source/1",
    requiredCapabilities: ["source_access"],
  });

  const request = effects.find((effect) => effect.type === "register_artifact");
  const offer = effects.find((effect) => effect.type === "create_work_offer");
  assert.ok(request !== undefined);
  assert.ok(offer !== undefined);
  assert.equal(request.artifact.schemaVersion, "human-decision-request/3");
  assert.deepEqual(request.artifact.payload, {
    kind: "json",
    value: {
      requestKind: "source_review",
      requestSchemaVersion: "source-review-request/1",
      actorKey: "source:one",
      subjectArtifactId: null,
      inputArtifactIds: [sourceArtifactId],
      choices: ["approve", "reject"],
      allowedChoices: ["approve", "reject"],
      intentSchemaVersion: "human-decision-intent/1",
    },
  });

  assert.deepEqual(offer.requirements, {
    authority: "human",
    capabilities: ["source_access"],
    minimumAssurance: "local_bearer",
  });
  assert.deepEqual(offer.allowedWorkerCapabilities, ["human", "source_access"]);

  const intent = {
    schemaVersion: "human-decision-intent/1",
    offerId: "offer-decision" as never,
    taskArtifactId: requestId,
    inputArtifactIds: [requestId, sourceArtifactId],
    result: { decision: "approve", reason: "source is complete" },
  } satisfies HumanDecisionIntent;
  assert.equal(intent.result.decision, "approve");
});
