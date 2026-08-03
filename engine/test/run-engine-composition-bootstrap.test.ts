import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test, type TestContext } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  KnownWorkRole,
  RevisionId,
  RunView,
  WorkerIdentity,
  WorkOfferView,
} from "../contracts/index.ts";
import { KNOWN_WORK_ROLES } from "../contracts/index.ts";
import {
  createRunEngine,
  type RunEngineClock,
  type SqliteRunEngine,
} from "../run-engine/index.ts";

const REVISION = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;
const BOOTSTRAP_REVISION = {
  kind: "run_bootstrap",
  editionId: "004",
  logicalId: "run-bootstrap",
  revisionId: REVISION,
} as const;

class ManualClock implements RunEngineClock {
  private milliseconds = Date.UTC(2026, 7, 2, 20, 6, 41, 636);

  now(): Date {
    return new Date(this.milliseconds);
  }

  advance(milliseconds: number): void {
    this.milliseconds += milliseconds;
  }
}

async function harness(
  context: TestContext,
  options: { readonly clock?: ManualClock; readonly workLeaseMs?: number } = {},
): Promise<SqliteRunEngine> {
  const root = await mkdtemp(join(tmpdir(), "mag-bootstrap-run-engine-"));
  const engine = createRunEngine({
    databasePath: join(root, "run.sqlite3"),
    artifactDirectory: join(root, "artifacts"),
    ...(options.clock === undefined ? {} : { clock: options.clock }),
    ...(options.workLeaseMs === undefined ? {} : { workLeaseMs: options.workLeaseMs }),
  });
  context.after(async () => {
    engine.close();
    await rm(root, { recursive: true, force: true });
  });
  return engine;
}

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(id: ArtifactId, kind: string, value: JsonObject = { fixture: id }): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "application/json",
    origin: "imported",
    payload: { kind: "json", value },
  };
}

function bootstrapSpec(prefix: string): EditionRootRunSpec {
  const editionBrief = artifactId(`${prefix}-edition-brief`);
  const editorialBrief = artifactId(`${prefix}-editorial-brief`);
  const writingRules = artifactId(`${prefix}-writing-rules`);
  const renderAssembly = artifactId(`${prefix}-committed-render-assembly`);
  const publication = artifactId(`${prefix}-publication`);
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: [
      seed(editionBrief, "edition_brief"),
      seed(editorialBrief, "editorial_brief"),
      seed(writingRules, "writing_rules"),
      seed(renderAssembly, "render_manifest", {
        editionId: "004",
        compositionRevision: {
          kind: "composition",
          editionId: "004",
          compositionId: "fresh-v2",
          revisionId: REVISION,
        },
        configuredLanguages: ["en"],
      }),
      seed(publication, "publication"),
    ],
    edition: {
      editionId: "004",
      execution: {
        kind: "bootstrap_composition",
        bootstrapRevision: BOOTSTRAP_REVISION,
        postRender: "stop_unreleased",
      },
      editionBrief,
      sources: [],
      articles: [],
      editorial: {
        editorialId: "opening",
        briefArtifact: editorialBrief,
        writingRules,
        modelPolicy: { default: { adapter: "test", model: "test" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: renderAssembly,
        rendererContractVersion: "magazine-renderer/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: publication,
        sourceArtifacts: [],
        dryRun: false,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
}

function bootstrapResult(): JsonObject {
  return {
    bootstrapRevision: BOOTSTRAP_REVISION,
    compositionRevision: {
      revisionRef: {
        kind: "composition",
        editionId: "004",
        compositionId: "fresh-v2",
        revisionId: REVISION,
      },
      manifestDigest: `sha256:${"c".repeat(64)}`,
      gitCommitOid: "a".repeat(40),
      gitBlobOids: {
        "durable/editions/004/compositions/fresh-v2/revisions/rev/manifest.yaml":
          "b".repeat(40),
      },
    },
    configuredLanguages: ["en"],
    selectedImageRevisionRefs: [{
      kind: "image",
      editionId: "004",
      logicalId: "cover",
      revisionId: REVISION,
    }],
    imageGenerationAllowed: false,
    rendererContractVersion: "magazine-renderer/1",
    promptSet: {
      id: "fresh-v2-prompt-set",
      roleInputs: roleInputs(),
    },
  };
}

function roleInputs(): Record<KnownWorkRole, JsonObject> {
  return Object.fromEntries(KNOWN_WORK_ROLES.map((role) => [role, roleInput(role)])) as
    Record<KnownWorkRole, JsonObject>;
}

function roleInput(role: KnownWorkRole): JsonObject {
  const contracts: Partial<Record<KnownWorkRole, string>> = {
    measure_edition: "measure-edition/1",
    render: "render-edition/1",
    render_inspection: "render-inspection/1",
    composition_bootstrap: "composition-bootstrap/1",
  };
  const contractVersion = contracts[role];
  if (contractVersion !== undefined) {
    return { kind: "contract", contractVersion };
  }
  if (role === "visual_review") {
    return {
      kind: "human",
      authority: "human",
      policyRevision: { kind: "policy", policyId: "render-review", revisionId: REVISION },
    };
  }
  const reasons: Partial<Record<KnownWorkRole, string>> = {
    capture_source: "bootstrap_committed_inputs",
    extract_source: "bootstrap_committed_inputs",
    review_source: "bootstrap_committed_inputs",
    writer: "bootstrap_existing_manuscripts",
    editorial_writer: "bootstrap_existing_manuscripts",
    translation_writer: "bootstrap_existing_translations",
    language_review: "bootstrap_existing_translations",
    language_fit: "bootstrap_existing_translations",
    cover_image: "bootstrap_existing_images",
    interior_image: "bootstrap_existing_images",
    select_art: "bootstrap_existing_images",
    render_reconciliation: "bootstrap_forces_fresh_render",
    release_approval: "stop_unreleased",
  };
  return {
    kind: "disabled",
    reason: reasons[role] ?? "bootstrap_committed_composition",
  };
}

function offered(view: RunView, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(offer, `expected an offered ${role} task`);
  return offer;
}

function workerFor(offer: WorkOfferView, suffix: string = offer.id): WorkerIdentity {
  return {
    principalId: `worker-${suffix}`,
    authority: offer.allowedWorkerCapabilities.includes("human") ? "human" : "tool",
    capabilities: offer.allowedWorkerCapabilities,
  };
}

function answerArtifact(
  id: ArtifactId,
  kind: string,
  value: JsonObject = { fixture: id },
  metadata?: JsonObject,
): AnswerArtifact {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "application/json",
    payload: { kind: "json", value },
    ...(metadata === undefined ? {} : { metadata }),
  };
}

function bootstrapAnswer(prefix: string) {
  const result = bootstrapResult();
  return {
    contractVersion: "composition-bootstrap/1",
    result,
    artifacts: [answerArtifact(
      artifactId(`${prefix}-bootstrap-evidence`),
      "composition_bootstrap_evidence",
      result,
    )],
  } as const;
}

async function submit(
  engine: SqliteRunEngine,
  offer: WorkOfferView,
  result: JsonObject,
  artifacts: readonly AnswerArtifact[],
): Promise<RunView> {
  const claim = await engine.claim(offer.id, workerFor(offer));
  return await engine.answer(claim, {
    contractVersion: offer.contractVersion,
    result,
    artifacts,
  });
}

test("bootstrap composition renders through RunEngine and stops approved but unreleased", async (context) => {
  const engine = await harness(context);
  const spec = bootstrapSpec("success");
  const started = await engine.start(spec);
  let view = await engine.inspect(started.runId);
  const bootstrap = offered(view, "composition_bootstrap");
  assert.deepEqual(
    view.offers.filter((offer) => offer.status === "offered").map((offer) => offer.role),
    ["composition_bootstrap"],
  );
  const request = JSON.parse(await engine.readText(bootstrap.taskArtifactId)) as JsonObject;
  assert.deepEqual(request.bootstrapRevision, BOOTSTRAP_REVISION);
  assert.equal(request.imageGenerationAllowed, false);

  const bootstrapClaim = await engine.claim(bootstrap.id, workerFor(bootstrap));
  view = await engine.answer(bootstrapClaim, bootstrapAnswer("success"));
  const bound = view.artifacts.find((artifact) => artifact.kind === "composition_revision_bound");
  assert.ok(bound);
  assert.deepEqual(JSON.parse(await engine.readText(bound.id)), bootstrapResult());
  assert.ok(bound.parents.some((parent) => parent.artifactId === bootstrap.taskArtifactId));

  const renderAssembly = spec.edition.render.renderManifestArtifact;
  const measurement = offered(view, "measure_edition");
  assert.equal(measurement.taskArtifactId, renderAssembly);
  assert.ok(measurement.inputArtifacts.includes(renderAssembly));
  assert.ok(measurement.inputArtifacts.includes(bound.id));
  view = await submit(engine, measurement, { fits: true }, [
    answerArtifact(artifactId("success-edition-measurement"), "edition_measurement"),
  ]);

  const render = offered(view, "render");
  assert.equal(render.taskArtifactId, renderAssembly);
  const renderArtifactIds = [
    artifactId("success-reader"),
    artifactId("success-web"),
    artifactId("success-booklet"),
    artifactId("success-package"),
    artifactId("success-render-critic"),
    artifactId("success-printer-preflight"),
  ] as const;
  view = await submit(engine, render, { renderedLanguages: ["en"] }, [
    answerArtifact(renderArtifactIds[0], "reader_pdf", {}, { relativePath: "en/reader.pdf" }),
    answerArtifact(renderArtifactIds[1], "web_output", {}, { relativePath: "en/web.html" }),
    answerArtifact(renderArtifactIds[2], "booklet_pdf", {}, { relativePath: "en/booklet.pdf" }),
    answerArtifact(renderArtifactIds[3], "package_artifact", {}, { relativePath: "en/package.zip" }),
    answerArtifact(renderArtifactIds[4], "render_critic_report", {}, { relativePath: "en/render-critic.json" }),
    answerArtifact(renderArtifactIds[5], "printer_preflight", {}, { relativePath: "en/preflight.json" }),
  ]);

  view = await submit(engine, offered(view, "render_inspection"), {
    result: "pass",
    renderArtifactIds,
    printerPreflightArtifactIds: [renderArtifactIds[5]],
    studioReady: false,
  }, [answerArtifact(artifactId("success-render-inspection"), "render_inspection")]);
  view = await submit(engine, offered(view, "visual_review"), {
    decision: "approved",
    renderArtifactIds,
  }, [answerArtifact(artifactId("success-visual-review"), "visual_review_decision")]);

  const edition = view.actors.find((actor) => actor.machine === "edition");
  assert.equal(view.status, "complete");
  assert.equal(edition?.state, "bootstrap_render_approved");
  assert.equal(edition?.status, "done");
  assert.deepEqual(edition?.outputs, renderArtifactIds);
  assert.equal(view.actors.some((actor) => actor.machine === "release"), false);
  assert.equal(view.offers.some((offer) => offer.role === "release_approval"), false);
  assert.equal(view.offers.some((offer) => [
    "writer", "editorial_writer", "cover_image", "interior_image", "select_art",
  ].includes(offer.role)), false);
});

test("a permanent composition bootstrap failure is terminal and has no production fallback", async (context) => {
  const engine = await harness(context);
  const started = await engine.start(bootstrapSpec("failure"));
  let view = await engine.inspect(started.runId);
  const offer = offered(view, "composition_bootstrap");
  const claim = await engine.claim(offer.id, workerFor(offer));
  view = await engine.fail(claim, {
    classification: "permanent",
    message: "committed bootstrap verification failed",
  });

  const edition = view.actors.find((actor) => actor.machine === "edition");
  assert.equal(view.status, "failed");
  assert.equal(edition?.state, "failed");
  assert.equal(view.actors.some((actor) => actor.machine !== "edition"), false);
  assert.equal(view.offers.filter((candidate) => candidate.status === "offered").length, 0);
  assert.deepEqual(new Set(view.offers.map((candidate) => candidate.role)), new Set([
    "composition_bootstrap",
  ]));
});

test("stale and duplicate composition bootstrap answers never advance twice", async (context) => {
  const clock = new ManualClock();
  const engine = await harness(context, { clock, workLeaseMs: 1_000 });
  const started = await engine.start(bootstrapSpec("idempotency"));
  let view = await engine.inspect(started.runId);
  const offer = offered(view, "composition_bootstrap");
  const staleClaim = await engine.claim(offer.id, workerFor(offer, "stale"));
  clock.advance(1_001);
  const acceptedClaim = await engine.claim(offer.id, workerFor(offer, "accepted"));

  view = await engine.answer(staleClaim, bootstrapAnswer("idempotency-stale"));
  assert.equal(view.actors.find((actor) => actor.machine === "edition")?.state, "verifying_bootstrap");
  assert.equal(view.actors.some((actor) => actor.machine === "render"), false);
  assert.equal(
    view.events.filter((event) => event.type === "WORK_COMPLETED").length,
    0,
  );
  assert.equal(
    view.attempts.find((attempt) => attempt.id === staleClaim.attemptId)?.status,
    "timed_out",
  );
  assert.equal(
    view.offers.find((candidate) => candidate.id === offer.id)?.activeAttemptId,
    acceptedClaim.attemptId,
  );

  const acceptedAnswer = bootstrapAnswer("idempotency-accepted");
  const accepted = await engine.answer(acceptedClaim, acceptedAnswer);
  assert.ok(offered(accepted, "measure_edition"));
  const headSequence = accepted.headSequence;
  const artifactCount = accepted.artifacts.length;
  const eventCount = accepted.events.length;

  const duplicate = await engine.answer(acceptedClaim, acceptedAnswer);
  assert.equal(duplicate.headSequence, headSequence);
  assert.equal(duplicate.artifacts.length, artifactCount);
  assert.equal(duplicate.events.length, eventCount);
  assert.equal(
    duplicate.events.filter((event) =>
      event.type === "WORK_COMPLETED" && event.payload.slot === "composition_bootstrap"
    ).length,
    1,
  );
  assert.equal(duplicate.actors.filter((actor) => actor.machine === "render").length, 1);
});
