import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { type TestContext } from "node:test";

import type { RunId, WorkOfferId, WorkOfferView } from "../contracts/index.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import { CooperativeModelBridge } from "../cooperative-model-bridge.ts";
import { HumanExecutor } from "../executors/human.ts";

test("cooperative bridge fences one Markdown writer reply and preserves all offer inputs as parents", async (testContext) => {
  const engine = new FakeEngine(writerOffer());
  const bridge = new CooperativeModelBridge(engine as never);
  const worker = await enrolledWorker(testContext, "terra-writer-a", "model", ["text_model", "source_access"]);
  const ticket = await bridge.claim("run-one" as RunId, "offer-one" as WorkOfferId, worker);
  await bridge.answerMarkdown(ticket, "# Fresh manuscript\n\nNew prose.");

  assert.equal(engine.claimedWorker?.authority, "model");
  assert.ok(engine.claimedWorker?.capabilities.includes("source_access"));
  assert.equal(engine.lastAnswer?.artifacts[0]?.kind, "article_manuscript");
  assert.deepEqual(
    engine.lastAnswer?.artifacts[0]?.parents?.map((parent: { readonly artifactId: string }) => parent.artifactId),
    ["source", "prompt"],
  );
});

test("cooperative bridge gives source-blind judges a YAML path and no source-access capability", async (testContext) => {
  const engine = new FakeEngine({ ...writerOffer(), role: "mechanics", contractVersion: "article-mechanics/1", allowedWorkerCapabilities: ["text_model", "source_blind"] });
  const bridge = new CooperativeModelBridge(engine as never);
  const worker = await enrolledWorker(testContext, "terra-line-a", "model", ["text_model", "source_blind"]);
  const ticket = await bridge.claim("run-one" as RunId, "offer-one" as WorkOfferId, worker);
  await bridge.answerYaml(ticket, "decision: approved\nfindings: []\n");

  assert.ok(engine.claimedWorker?.capabilities.includes("source_blind"));
  assert.ok(!engine.claimedWorker?.capabilities.includes("source_access"));
  assert.equal(engine.lastAnswer?.result.decision, "approved");
  assert.equal(engine.lastAnswer?.artifacts[0]?.kind, "mechanics_judgment");
});

test("model and tool credentials cannot stand in for a human executor", async (testContext) => {
  const tool = await enrolledWorker(testContext, "render-tool", "tool", ["subprocess"]);
  const human = new HumanExecutor(tool);
  let claims = 0;
  await assert.rejects(
    human.claim({
      async claimAuthorized() {
        claims += 1;
        throw new Error("must not be called");
      },
    }, "offer-one" as WorkOfferId),
    /authenticated human credential/u,
  );
  assert.equal(claims, 0);
});

function writerOffer(): WorkOfferView {
  return {
    id: "offer-one" as WorkOfferId,
    runId: "run-one" as RunId,
    actorId: "actor-one" as never,
    actorKey: "article:one",
    state: "drafting",
    stateVisitId: "visit-one" as never,
    role: "writer",
    slot: "writer",
    subjectArtifactId: "source" as never,
    inputArtifacts: ["source", "prompt"] as never,
    taskArtifactId: "prompt" as never,
    contractVersion: "article-writer/1",
    allowedWorkerCapabilities: ["text_model", "source_access"],
    status: "offered",
    createdAt: "2026-08-03T00:00:00.000Z",
  };
}

class FakeEngine {
  private offer: WorkOfferView;
  claimedWorker: { readonly authority: string; readonly capabilities: readonly string[] } | undefined;
  lastAnswer: any;

  constructor(offer: WorkOfferView) { this.offer = offer; }

  async inspect(): Promise<any> { return { offers: [this.offer] }; }
  async claimAuthorized(_offerId: WorkOfferId, worker: any): Promise<any> {
    const identity = await worker.describe();
    this.claimedWorker = identity;
    this.offer = { ...this.offer, status: "claimed", activeAttemptId: "attempt-one" as never };
    return { offerId: this.offer.id, attemptId: "attempt-one" as never, attemptFence: 1, worker: identity, leaseExpiresAt: "2026-08-03T00:01:00.000Z" };
  }
  async heartbeat(claim: any): Promise<any> { return claim; }
  async answer(_claim: any, answer: any): Promise<any> { this.lastAnswer = answer; return {}; }
}

async function enrolledWorker(
  testContext: TestContext,
  principalId: string,
  authority: "model" | "tool",
  capabilities: readonly ("text_model" | "source_access" | "source_blind" | "subprocess")[],
) {
  const root = await mkdtemp(join(tmpdir(), "mag-cooperative-bridge-"));
  testContext.after(async () => await rm(root, { recursive: true, force: true }));
  const store = await LocalAuthorityStore.init(join(root, "authority"));
  await store.enrollWorker({ principalId, authority, capabilities });
  const credential = await store.createCredentialProfile({ principalId });
  await store.grant({ credentialProfileId: credential.credentialProfileId, capabilities });
  return await store.authenticate({
    credentialProfileId: credential.credentialProfileId,
    secret: credential.secret,
  });
}
