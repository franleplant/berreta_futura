import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, test, type TestContext } from "node:test";

import type {
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  HumanDecisionIntent,
  WorkClaim,
  WorkOfferId,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import {
  LocalAuthorityError,
  LocalAuthorityStore,
  type AuthorizedWorker,
  type WorkerClaimPort,
} from "../authority/local-authority.ts";
import {
  createRunEngine,
  RunEngineError,
  StaleClaimError,
  type RunEngineClock,
  type SqliteRunEngine,
} from "../run-engine/index.ts";

type AuthorityHarness = {
  readonly root: string;
  readonly store: LocalAuthorityStore;
};

class ManualClock implements RunEngineClock {
  #milliseconds = Date.UTC(2026, 7, 3);

  now(): Date {
    return new Date(this.#milliseconds);
  }

  advance(milliseconds: number): void {
    this.#milliseconds += milliseconds;
  }
}

type EngineHarness = AuthorityHarness & {
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly clock: ManualClock;
  openEngine(): SqliteRunEngine;
};

async function authorityHarness(testContext: TestContext): Promise<AuthorityHarness> {
  const root = await mkdtemp(join(tmpdir(), "mag-authority-adversarial-"));
  const store = await LocalAuthorityStore.init(join(root, "authority"));
  testContext.after(async () => {
    await rm(root, { recursive: true, force: true });
  });
  return { root, store };
}

async function engineHarness(testContext: TestContext): Promise<EngineHarness> {
  const root = await mkdtemp(join(tmpdir(), "mag-authority-engine-adversarial-"));
  const store = await LocalAuthorityStore.init(join(root, "authority"));
  const databasePath = join(root, "run.sqlite3");
  const artifactDirectory = join(root, "artifacts");
  const clock = new ManualClock();
  const engines: SqliteRunEngine[] = [];
  testContext.after(async () => {
    engines.forEach((engine) => engine.close());
    await rm(root, { recursive: true, force: true });
  });
  return {
    root,
    store,
    databasePath,
    artifactDirectory,
    clock,
    openEngine: () => {
      const engine = createRunEngine({
        databasePath,
        artifactDirectory,
        clock,
        workLeaseMs: 1_000,
      });
      engines.push(engine);
      return engine;
    },
  };
}

function offerId(value: string): WorkOfferId {
  return value as WorkOfferId;
}

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(id: string): ArtifactSeed {
  return {
    id: artifactId(id),
    kind: "test_input",
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: id },
  };
}

function collectionOnlyEdition(): EditionRootRunSpec {
  const ids = [
    "edition-brief",
    "editorial-brief",
    "writing-rules",
    "render-manifest",
    "publication",
  ];
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: ids.map(seed),
    edition: {
      editionId: "authority-test-edition",
      execution: { kind: "produce" },
      editionBrief: artifactId("edition-brief"),
      sources: [],
      articles: [],
      editorial: {
        editorialId: "opening",
        briefArtifact: artifactId("editorial-brief"),
        writingRules: artifactId("writing-rules"),
        modelPolicy: { default: { adapter: "test", model: "deterministic" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: artifactId("render-manifest"),
        rendererContractVersion: "test-renderer/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: artifactId("publication"),
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "deterministic" } },
    },
  };
}

function editionWithSeededSourceApproval(): EditionRootRunSpec {
  const base = collectionOnlyEdition();
  const lead = artifactId("seeded-source-lead");
  const rawBundle = artifactId("seeded-source-raw-bundle");
  const evidence = artifactId("seeded-source-evidence");
  const extraction = artifactId("seeded-source-extraction");
  const metadata = artifactId("seeded-source-metadata");
  const approval = artifactId("seeded-source-approval");
  const sourceArtifacts: readonly ArtifactSeed[] = [
    { ...seed(lead), kind: "submitted_lead" },
    {
      ...seed(rawBundle),
      kind: "raw_source_bundle",
      parents: [{ artifactId: lead, relation: "captured_from_lead" }],
    },
    {
      ...seed(evidence),
      kind: "raw_evidence",
      parents: [{ artifactId: rawBundle, relation: "bundle_content" }],
    },
    {
      ...seed(extraction),
      kind: "source_extraction",
      parents: [{ artifactId: rawBundle, relation: "extracted_from" }],
    },
    {
      ...seed(metadata),
      kind: "source_metadata",
      parents: [{ artifactId: rawBundle, relation: "describes_bundle" }],
    },
    {
      ...seed(approval),
      kind: "source_review_decision",
      origin: "human",
      parents: [
        { artifactId: rawBundle, relation: "reviewed_raw_bundle" },
        { artifactId: extraction, relation: "reviewed_extraction" },
      ],
    },
  ];
  return {
    ...base,
    artifacts: [...base.artifacts, ...sourceArtifacts],
    edition: {
      ...base.edition,
      sources: [{
        sourceId: "seeded-source",
        leadArtifact: lead,
        rawBundleArtifact: rawBundle,
        rawEvidenceArtifacts: [evidence],
        extractionArtifact: extraction,
        metadataArtifact: metadata,
        approvalArtifact: approval,
      }],
    },
  };
}

function offeredClose(view: Awaited<ReturnType<SqliteRunEngine["inspect"]>>): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === "close_collection" && candidate.status === "offered",
  );
  assert.ok(offer, "expected active collection-close offer");
  return offer;
}

async function rejectAuthority(
  operation: Promise<unknown>,
  code: LocalAuthorityError["code"],
): Promise<void> {
  await assert.rejects(
    operation,
    (error: unknown) => error instanceof LocalAuthorityError && error.code === code,
  );
}

class CapturingPort implements WorkerClaimPort {
  readonly workers: WorkerIdentity[] = [];

  async claimAuthorized(requestedOfferId: WorkOfferId, worker: AuthorizedWorker): Promise<WorkClaim> {
    const description = await worker.describe();
    const identity: WorkerIdentity = {
      principalId: description.principalId,
      authority: description.authority,
      capabilities: description.capabilities,
    };
    this.workers.push(identity);
    return {
      offerId: requestedOfferId,
      attemptId: "attempt-captured" as WorkClaim["attemptId"],
      attemptFence: 1,
      ticket: "t".repeat(43),
      worker: identity,
      leaseExpiresAt: "2026-08-03T00:00:00.000Z",
    };
  }
}

async function enrollUsableHuman(store: LocalAuthorityStore, principalId = "editor-alba"): Promise<{
  readonly credentialProfileId: string;
  readonly secret: string;
  readonly worker: AuthorizedWorker;
}> {
  await store.enrollHuman({ principalId, capabilities: ["source_access"] });
  const credential = await store.createCredentialProfile({
    principalId,
    credentialProfileId: `${principalId}-credential`,
  });
  await store.grant({
    credentialProfileId: credential.credentialProfileId,
    grantId: `${principalId}-grant`,
    capabilities: ["source_access"],
  });
  return {
    ...credential,
    worker: await store.authenticate({
      credentialProfileId: credential.credentialProfileId,
      secret: credential.secret,
    }),
  };
}

describe("local authority adversarial boundary", () => {
  test("does not let legacy caller-supplied human identity spoof an authenticated claim", async (testContext) => {
    const { store } = await authorityHarness(testContext);
    const enrolled = await enrollUsableHuman(store);
    const port = new CapturingPort();

    // A session has no identity argument. Extra legacy caller data is ignored at
    // runtime, so this cannot replace the identity reconstructed from grants.
    await (enrolled.worker.claim as unknown as (
      port: WorkerClaimPort,
      offer: WorkOfferId,
      legacyIdentity: WorkerIdentity,
    ) => Promise<WorkClaim>)(port, offerId("human-offer"), {
      principalId: "spoofed-admin",
      authority: "human",
      capabilities: ["human", "source_access", "subprocess"],
    });

    assert.deepEqual(port.workers, [{
      principalId: "editor-alba",
      authority: "human",
      capabilities: ["source_access"],
    }]);
  });

  test("never grants a non-human principal human capability or human authority", async (testContext) => {
    const { store } = await authorityHarness(testContext);

    await rejectAuthority(
      store.enrollWorker({
        principalId: "tool-spoof",
        authority: "tool",
        capabilities: ["human"],
      }),
      "INVALID_ARGUMENT",
    );

    await store.enrollWorker({
      principalId: "tool-renderer",
      authority: "tool",
      capabilities: ["subprocess"],
    });
    const credential = await store.createCredentialProfile({
      principalId: "tool-renderer",
      credentialProfileId: "tool-renderer-credential",
    });
    await rejectAuthority(
      store.grant({
        credentialProfileId: credential.credentialProfileId,
        capabilities: ["human"],
      }),
      "INVALID_ARGUMENT",
    );
    await store.grant({
      credentialProfileId: credential.credentialProfileId,
      grantId: "tool-renderer-grant",
      capabilities: ["subprocess"],
    });

    const port = new CapturingPort();
    await (await store.authenticate({
      credentialProfileId: credential.credentialProfileId,
      secret: credential.secret,
    })).claim(port, offerId("tool-offer"));
    assert.deepEqual(port.workers, [{
      principalId: "tool-renderer",
      authority: "tool",
      capabilities: ["subprocess"],
    }]);
  });

  test("rejects wrong, revoked, and grantless credentials before they can construct claims", async (testContext) => {
    const { store } = await authorityHarness(testContext);
    const enrolled = await enrollUsableHuman(store);

    await rejectAuthority(
      store.authenticate({ credentialProfileId: enrolled.credentialProfileId, secret: "x".repeat(43) }),
      "AUTHORIZATION_DENIED",
    );

    await store.revoke({ grantId: "editor-alba-grant" });
    await rejectAuthority(enrolled.worker.describe(), "AUTHORIZATION_DENIED");
    await rejectAuthority(enrolled.worker.claim(new CapturingPort(), offerId("revoked-grant")), "AUTHORIZATION_DENIED");

    const replacement = await store.createCredentialProfile({
      principalId: "editor-alba",
      credentialProfileId: "editor-alba-replacement",
    });
    await store.grant({
      credentialProfileId: replacement.credentialProfileId,
      grantId: "editor-alba-replacement-grant",
      capabilities: ["source_access"],
    });
    const replacementWorker = await store.authenticate({
      credentialProfileId: replacement.credentialProfileId,
      secret: replacement.secret,
    });
    await store.revoke({ credentialProfileId: replacement.credentialProfileId });
    await rejectAuthority(replacementWorker.describe(), "CREDENTIAL_REVOKED");
    await rejectAuthority(store.authenticate({
      credentialProfileId: replacement.credentialProfileId,
      secret: replacement.secret,
    }), "AUTHORIZATION_DENIED");

    const third = await store.createCredentialProfile({
      principalId: "editor-alba",
      credentialProfileId: "editor-alba-third",
    });
    await store.grant({
      credentialProfileId: third.credentialProfileId,
      grantId: "editor-alba-third-grant",
      capabilities: ["source_access"],
    });
    const thirdWorker = await store.authenticate({
      credentialProfileId: third.credentialProfileId,
      secret: third.secret,
    });
    await store.revoke({ principalId: "editor-alba" });
    await rejectAuthority(thirdWorker.describe(), "IDENTITY_REVOKED");
    await rejectAuthority(store.authenticate({
      credentialProfileId: third.credentialProfileId,
      secret: third.secret,
    }), "IDENTITY_REVOKED");
  });

  test("rejects unknown fields at every untrusted enrollment and credential boundary", async (testContext) => {
    const { store } = await authorityHarness(testContext);

    await rejectAuthority(
      store.enrollHuman({ principalId: "alba", authority: "human" }),
      "INVALID_ARGUMENT",
    );
    await rejectAuthority(
      store.enrollWorker({
        principalId: "renderer",
        authority: "tool",
        capabilities: ["subprocess"],
        role: "human",
      }),
      "INVALID_ARGUMENT",
    );
    await store.enrollHuman({ principalId: "alba" });
    await rejectAuthority(
      store.createCredentialProfile({ principalId: "alba", issueForever: true }),
      "INVALID_ARGUMENT",
    );
    const credential = await store.createCredentialProfile({
      principalId: "alba",
      credentialProfileId: "alba-credential",
    });
    await rejectAuthority(
      store.grant({
        credentialProfileId: credential.credentialProfileId,
        capabilities: ["human"],
        expires: "never",
      }),
      "INVALID_ARGUMENT",
    );
    await rejectAuthority(
      store.authenticate({ ...credential, principalId: "spoofed" }),
      "INVALID_ARGUMENT",
    );
    await rejectAuthority(
      store.revoke({ credentialProfileId: credential.credentialProfileId, principalId: "alba" }),
      "INVALID_ARGUMENT",
    );
  });

  test("never returns or persists an issued credential secret in snapshots or sessions", async (testContext) => {
    const { root, store } = await authorityHarness(testContext);
    const enrolled = await enrollUsableHuman(store);
    const snapshot = await store.snapshot();
    const persisted = await readFile(join(root, "authority", "authority.json"), "utf8");

    assert.equal(JSON.stringify(snapshot).includes(enrolled.secret), false);
    assert.equal(JSON.stringify(enrolled.worker).includes(enrolled.secret), false);
    assert.equal(persisted.includes(enrolled.secret), false);
    assert.equal(persisted.includes("secretHash"), true);
    assert.deepEqual(Object.keys(enrolled.worker), []);
  });
});

describe("RunEngine authority and claim tickets", () => {
  test("rejects a non-human authenticated session for a human offer", async (testContext) => {
    const { store, openEngine } = await engineHarness(testContext);
    const engine = openEngine();
    const outcome = await engine.start(collectionOnlyEdition());
    const close = offeredClose(await engine.inspect(outcome.runId));

    await assert.rejects(
      engine.claim(close.id, {
        principalId: "legacy-spoofed-human",
        authority: "human",
        capabilities: ["human", "source_access"],
      }),
      (error: unknown) => error instanceof RunEngineError && error.code === "CALLER_IDENTITY_REJECTED",
    );

    await store.enrollWorker({
      principalId: "collection-tool",
      authority: "tool",
      capabilities: ["subprocess"],
    });
    const credential = await store.createCredentialProfile({ principalId: "collection-tool" });
    await store.grant({
      credentialProfileId: credential.credentialProfileId,
      capabilities: ["subprocess"],
    });
    const tool = await store.authenticate({
      credentialProfileId: credential.credentialProfileId,
      secret: credential.secret,
    });

    await assert.rejects(
      tool.claim(engine, close.id),
      (error: unknown) => error instanceof RunEngineError && error.code === "WORKER_AUTHORITY_MISMATCH",
    );
  });

  test("keeps claim tickets secret, rejects replay after expiry, and preserves the current ticket across restart", async (testContext) => {
    const { store, clock, openEngine } = await engineHarness(testContext);
    const first = openEngine();
    const outcome = await first.start(collectionOnlyEdition());
    const close = offeredClose(await first.inspect(outcome.runId));
    const human = await enrollUsableHuman(store, "collection-editor");

    const original = await human.worker.claim(first, close.id);
    assert.match(original.ticket, /^[A-Za-z0-9_-]{43}$/u);
    assert.equal(JSON.stringify(await first.inspect(outcome.runId)).includes(original.ticket), false);

    first.close();
    const restarted = openEngine();
    await restarted.heartbeat(original);

    clock.advance(1_001);
    const replacement = await human.worker.claim(restarted, close.id);
    assert.notEqual(replacement.ticket, original.ticket);
    await assert.rejects(restarted.heartbeat(original), StaleClaimError);
    assert.equal(JSON.stringify(await restarted.inspect(outcome.runId)).includes(replacement.ticket), false);

  });

  test("binds human intent to the exact active offer and rejects legacy human answers", async (testContext) => {
    const { store, openEngine } = await engineHarness(testContext);
    const engine = openEngine();
    const outcome = await engine.start(collectionOnlyEdition());
    const close = offeredClose(await engine.inspect(outcome.runId));
    const human = await enrollUsableHuman(store, "decision-editor");
    const preparation = await engine.prepareHumanDecision(close.id, human.worker);
    const choice = preparation.allowedChoices.find((candidate) => candidate === "close");
    assert.ok(choice, "collection close must expose the close choice");
    const intent = {
      schemaVersion: "human-decision-intent/1",
      offerId: preparation.offerId,
      taskArtifactId: preparation.taskArtifactId,
      inputArtifactIds: preparation.inputArtifactIds,
      result: { choice },
    } satisfies HumanDecisionIntent;

    assert.equal(preparation.offerId, close.id);
    assert.equal(preparation.taskArtifactId, close.taskArtifactId);
    assert.deepEqual(preparation.inputArtifactIds, close.inputArtifacts);
    assert.equal(preparation.allowedChoices.includes("close"), true);

    await assert.rejects(
      engine.answer(preparation.claim, {
        contractVersion: close.contractVersion,
        result: { choice: "close" },
        artifacts: [],
      }),
      (error: unknown) => error instanceof RunEngineError && error.code === "HUMAN_DECISION_API_REQUIRED",
    );

    for (const forged of [
      { ...intent, offerId: offerId("different-offer") },
      { ...intent, taskArtifactId: artifactId("different-request") },
      { ...intent, inputArtifactIds: [...intent.inputArtifactIds, artifactId("injected-input")] },
      { ...intent, result: { choice: "unavailable_choice" } },
    ]) {
      await assert.rejects(
        engine.decide(preparation, human.worker, forged),
        (error: unknown) => error instanceof RunEngineError,
      );
    }

    const concurrent = await Promise.allSettled([
      engine.decide(preparation, human.worker, intent),
      engine.decide(preparation, human.worker, intent),
    ]);
    assert.equal(concurrent.filter((result) => result.status === "fulfilled").length, 2);
    const settled = await engine.inspect(outcome.runId);
    assert.equal(
      settled.events.filter(
        (event) => event.type === "WORK_COMPLETED" && event.payload.offerId === close.id,
      ).length,
      1,
    );
  });

  test("does not let a seeded historical source approval skip the current human review offer", async (testContext) => {
    const { store, openEngine } = await engineHarness(testContext);
    const engine = openEngine();
    const outcome = await engine.start(editionWithSeededSourceApproval());
    const human = await enrollUsableHuman(store, "source-editor");
    const close = offeredClose(await engine.inspect(outcome.runId));
    const closePreparation = await engine.prepareHumanDecision(close.id, human.worker);
    await engine.decide(closePreparation, human.worker, {
      schemaVersion: "human-decision-intent/1",
      offerId: closePreparation.offerId,
      taskArtifactId: closePreparation.taskArtifactId,
      inputArtifactIds: closePreparation.inputArtifactIds,
      result: { choice: "close" },
    });

    const view = await engine.inspect(outcome.runId);
    const review = view.offers.find(
      (offer) => offer.role === "review_source" && offer.status === "offered",
    );
    assert.ok(review, "a historical approval must not satisfy the active review offer");
    assert.equal(review.inputArtifacts.includes(artifactId("seeded-source-approval")), false);
  });
});
