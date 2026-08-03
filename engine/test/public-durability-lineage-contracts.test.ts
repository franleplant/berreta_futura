import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";
import { test } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  RunId,
  RunView,
  WorkerIdentity,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  EDITION_4_ID,
  stageEdition4Fixture,
} from "../fixtures/edition4.ts";
import { RENDERER_CONTRACT_VERSION } from "../renderer-adapter/index.ts";
import {
  RunEngineError,
  SqliteRunEngine,
  type RunEngineFailpoint,
} from "../run-engine/index.ts";
import { serveRunViewer } from "../view/server.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function textSeed(
  id: ArtifactId,
  kind = "fixture_input",
  parents: ArtifactSeed["parents"] = [],
  origin: ArtifactSeed["origin"] = "imported",
): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin,
    payload: { kind: "text", text: `immutable fixture ${id}` },
    ...(parents.length === 0 ? {} : { parents }),
  };
}

function answerArtifact(
  id: ArtifactId,
  kind: string,
  metadata?: JsonObject,
): AnswerArtifact {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "application/json",
    payload: { kind: "json", value: { fixture: id } },
    ...(metadata === undefined ? {} : { metadata }),
  };
}

type EditionFixture = {
  readonly spec: EditionRootRunSpec;
  readonly ids: {
    readonly lead: ArtifactId;
    readonly rawBundle: ArtifactId;
    readonly rawEvidence: ArtifactId;
    readonly sourceExtraction: ArtifactId;
    readonly sourceMetadata: ArtifactId;
    readonly sourceApproval: ArtifactId;
    readonly manuscript: ArtifactId;
    readonly editorial: ArtifactId;
    readonly selectedArt: ArtifactId;
    readonly renderProfile: ArtifactId;
    readonly printerProfile: ArtifactId;
  };
};

function editionFixture(
  prefix: string,
  options: {
    readonly sourceExtraction?: ArtifactId;
    readonly seedSourceExtraction?: boolean;
    readonly sourceId?: string;
  } = {},
): EditionFixture {
  const id = (name: string) => artifactId(`${prefix}-${name}`);
  const sourceExtraction = options.sourceExtraction ?? id("source-extraction");
  const ids = {
    lead: id("lead"),
    rawBundle: id("raw-bundle"),
    rawEvidence: id("raw-evidence"),
    sourceExtraction,
    sourceMetadata: id("source-metadata"),
    sourceApproval: id("source-approval"),
    manuscript: id("manuscript"),
    editorial: id("editorial"),
    selectedArt: id("selected-art"),
    renderProfile: id("render-profile"),
    printerProfile: id("printer-profile"),
  };
  const editionBrief = id("edition-brief");
  const planning = id("planning");
  const articleBrief = id("article-brief");
  const writerPrompt = id("writer-prompt");
  const worthPrompt = id("worth-prompt");
  const evidencePrompt = id("evidence-prompt");
  const craftPrompt = id("craft-prompt");
  const writingRules = id("writing-rules");
  const editorialBrief = id("editorial-brief");
  const artBrief = id("art-brief");
  const releasePlaceholder = id("release-placeholder");
  const seeds = [
    textSeed(editionBrief),
    textSeed(planning),
    textSeed(ids.lead),
    textSeed(ids.rawBundle, "raw_source_bundle", [
      { artifactId: ids.lead, relation: "captured_from_lead" },
    ]),
    textSeed(ids.rawEvidence, "raw_evidence", [
      { artifactId: ids.rawBundle, relation: "bundle_content" },
    ]),
    ...(options.seedSourceExtraction === false
      ? []
      : [textSeed(sourceExtraction, "source_extraction", [
        { artifactId: ids.rawBundle, relation: "extracted_from" },
      ])]),
    textSeed(ids.sourceMetadata, "source_metadata", [
      { artifactId: ids.rawBundle, relation: "describes_bundle" },
    ]),
    textSeed(ids.sourceApproval, "source_review_decision", [
      { artifactId: ids.rawBundle, relation: "reviewed_raw_bundle" },
      { artifactId: sourceExtraction, relation: "reviewed_extraction" },
    ], "human"),
    textSeed(articleBrief),
    textSeed(writerPrompt),
    textSeed(worthPrompt),
    textSeed(evidencePrompt),
    textSeed(craftPrompt),
    textSeed(writingRules),
    textSeed(ids.manuscript, "article_manuscript"),
    textSeed(editorialBrief),
    textSeed(ids.editorial, "editorial_manuscript"),
    textSeed(artBrief),
    textSeed(ids.selectedArt, "selected_art"),
    textSeed(ids.renderProfile, "render_profile"),
    textSeed(ids.printerProfile, "printer_profile"),
    textSeed(releasePlaceholder),
  ];

  return {
    ids,
    spec: {
      schemaVersion: 1,
      kind: "edition",
      artifacts: seeds,
      edition: {
        editionId: `${prefix}-edition`,
        execution: { kind: "produce" },
        editionBrief,
        planningArtifact: planning,
        sources: [
          {
            sourceId: options.sourceId ?? `${prefix}-source`,
            leadArtifact: ids.lead,
            rawBundleArtifact: ids.rawBundle,
            rawEvidenceArtifacts: [ids.rawEvidence],
            extractionArtifact: sourceExtraction,
            metadataArtifact: ids.sourceMetadata,
            approvalArtifact: ids.sourceApproval,
          },
        ],
        articles: [
          {
            articleId: `${prefix}-article`,
            contentMode: "faithful_edit",
            attribution: {
              kind: "source_author",
              byline: "Source Author",
              sourceAuthors: ["Source Author"],
              sourceIds: [options.sourceId ?? `${prefix}-source`],
            },
            editionContext: editionBrief,
            articleBrief,
            sources: [sourceExtraction],
            sourceApprovalArtifacts: [ids.sourceApproval],
            writerPrompt,
            judgePrompts: {
              worth: worthPrompt,
              evidence: evidencePrompt,
              craft: craftPrompt,
            },
            writingRules,
            initialManuscript: ids.manuscript,
            policy: {
              maxIterations: 2,
              maximumReaderPages: 7,
              teaching: "not_applicable",
              enabledLenses: ["worth", "evidence", "craft"],
              blockingLenses: [],
            },
            modelPolicy: {
              default: { adapter: "test", model: "deterministic" },
            },
          },
        ],
        editorial: {
          editorialId: `${prefix}-editorial`,
          briefArtifact: editorialBrief,
          writingRules,
          initialManuscript: ids.editorial,
          modelPolicy: {
            default: { adapter: "test", model: "deterministic" },
          },
        },
        translations: [],
        art: [
          {
            key: `${prefix}-cover`,
            role: "cover",
            artifactId: ids.selectedArt,
            briefArtifact: artBrief,
            required: true,
          },
        ],
        render: {
          renderManifestArtifact: ids.renderProfile,
          rendererContractVersion: "render-edition/1",
          printerProfileArtifact: ids.printerProfile,
          configuredLanguages: ["en"],
          studioPolicy: "home_ready_studio_blocked",
        },
        release: {
          publicationArtifact: releasePlaceholder,
          sourceArtifacts: [],
          dryRun: false,
          target: "private",
        },
        modelPolicy: {
          default: { adapter: "test", model: "deterministic" },
        },
      },
    },
  };
}

function preparedSourceArtifacts(fixture: EditionFixture): readonly ArtifactId[] {
  return [
    fixture.ids.lead,
    fixture.ids.rawBundle,
    fixture.ids.rawEvidence,
    fixture.ids.sourceExtraction,
    fixture.ids.sourceMetadata,
    fixture.ids.sourceApproval,
  ];
}

function offered(view: RunView, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(offer, `run did not expose an offered ${role} task`);
  return offer;
}

function workerFor(offer: WorkOfferView): WorkerIdentity {
  const authority = offer.allowedWorkerCapabilities.includes("human")
    ? "human"
    : offer.allowedWorkerCapabilities.includes("text_model") ||
        offer.allowedWorkerCapabilities.includes("image_model")
      ? "model"
      : "tool";
  return {
    principalId: `worker-${offer.id}`,
    authority,
    capabilities: offer.allowedWorkerCapabilities,
  };
}

async function submit(
  engine: SqliteRunEngine,
  offer: WorkOfferView,
  result: JsonObject,
  artifacts: readonly AnswerArtifact[] = [],
): Promise<RunView> {
  const claim = await engine.claim(offer.id, workerFor(offer));
  if (offer.role === "durable_checkpoint") {
    return await engine.answer(claim, await durableCheckpointAnswer(engine, offer));
  }
  return await engine.answer(claim, {
    contractVersion: offer.contractVersion,
    result,
    artifacts,
  });
}

async function advanceToRenderMeasurement(
  engine: SqliteRunEngine,
  runId: RunId,
  prefix: string,
): Promise<{ readonly view: RunView; readonly offer: WorkOfferView }> {
  for (let step = 0; step < 20; step += 1) {
    const view = await engine.inspect(runId);
    const next = view.offers.find((candidate) => candidate.status === "offered");
    assert.ok(next, `run stopped before render measurement in ${view.actors[0]?.state}`);
    switch (next.role) {
      case "close_collection":
        await submit(engine, next, { choice: "close" }, [
          answerArtifact(
            artifactId(`${prefix}-${next.id}-collection-decision`),
            "collection_decision",
          ),
        ]);
        break;
      case "measure_article":
        await submit(
          engine,
          next,
          { fits: true, pageCount: 1, openerFits: true },
          [answerArtifact(
            artifactId(`${prefix}-${next.id}-article-measurement`),
            "article_measurement",
          )],
        );
        break;
      case "worth":
      case "evidence":
      case "craft":
        await submit(engine, next, { decision: "pass" });
        break;
      case "review_source":
        await submit(engine, next, { decision: "approved" }, [
          answerArtifact(artifactId(`${prefix}-${next.id}-source-review`), "source_review_decision"),
        ]);
        break;
      case "edition_review":
        await submit(
          engine,
          next,
          { decision: "approved" },
          [answerArtifact(artifactId(`${prefix}-edition-review`), "edition_review")],
        );
        break;
      case "durable_checkpoint":
        await submit(engine, next, {});
        break;
      case "measure_edition":
        return { view, offer: next };
      default:
        assert.fail(`unexpected pre-render work role ${next.role}`);
    }
  }
  assert.fail("run exceeded the pre-render step limit");
}

async function advanceToVisualReview(
  engine: SqliteRunEngine,
  runId: RunId,
  prefix: string,
): Promise<{
  readonly view: RunView;
  readonly offer: WorkOfferView;
  readonly renderManifestId: ArtifactId;
  readonly renderArtifactIds: readonly [
    ArtifactId,
    ArtifactId,
    ArtifactId,
    ArtifactId,
    ArtifactId,
    ArtifactId,
  ];
  readonly inspectionId: ArtifactId;
}> {
  const measurement = await advanceToRenderMeasurement(engine, runId, prefix);
  const renderManifest = measurement.view.artifacts.find(
    (candidate) => candidate.kind === "render_manifest",
  );
  assert.ok(renderManifest, "edition did not register a render manifest");
  await submit(
    engine,
    measurement.offer,
    { fits: true },
    [answerArtifact(artifactId(`${prefix}-edition-measurement`), "edition_measurement")],
  );

  let view = await engine.inspect(runId);
  const render = offered(view, "render");
  const renderArtifactIds = [
    artifactId(`${prefix}-reader`),
    artifactId(`${prefix}-web`),
    artifactId(`${prefix}-booklet`),
    artifactId(`${prefix}-package`),
    artifactId(`${prefix}-render-critic`),
    artifactId(`${prefix}-printer-preflight`),
  ] as const;
  await submit(
    engine,
    render,
    { renderedLanguages: ["en"] },
    [
      answerArtifact(renderArtifactIds[0], "reader_pdf", {
        relativePath: "en/reader.pdf",
      }),
      answerArtifact(renderArtifactIds[1], "web_output", {
        relativePath: "en/web.html",
      }),
      answerArtifact(renderArtifactIds[2], "booklet_pdf", {
        relativePath: "en/booklet.pdf",
      }),
      answerArtifact(renderArtifactIds[3], "package_artifact", {
        relativePath: "en/package.zip",
      }),
      answerArtifact(renderArtifactIds[4], "render_critic_report", {
        relativePath: "en/render-critic.json",
      }),
      answerArtifact(renderArtifactIds[5], "printer_preflight", {
        relativePath: "en/preflight.json",
      }),
    ],
  );

  view = await engine.inspect(runId);
  const inspection = offered(view, "render_inspection");
  const inspectionId = artifactId(`${prefix}-render-inspection`);
  await submit(
    engine,
    inspection,
    {
      result: "pass",
      renderArtifactIds: [...renderArtifactIds].reverse(),
      printerPreflightArtifactIds: [renderArtifactIds[5]],
      studioReady: false,
    },
    [answerArtifact(inspectionId, "render_inspection")],
  );

  view = await engine.inspect(runId);
  return {
    view,
    offer: offered(view, "visual_review"),
    renderManifestId: renderManifest.id,
    renderArtifactIds,
    inspectionId,
  };
}

async function advanceToReleaseApproval(
  engine: SqliteRunEngine,
  runId: RunId,
  prefix: string,
): Promise<{
  readonly view: RunView;
  readonly offer: WorkOfferView;
  readonly approvedRenderSetId: ArtifactId;
  readonly sourceArtifactIds: readonly ArtifactId[];
}> {
  const visual = await advanceToVisualReview(engine, runId, prefix);
  const view = await submit(
    engine,
    visual.offer,
    {
      decision: "approved",
      renderArtifactIds: visual.renderArtifactIds,
    },
    [
      answerArtifact(
        artifactId(`${prefix}-visual-review-decision`),
        "visual_review_decision",
      ),
    ],
  );
  const approvedRenderSet = view.artifacts.find(
    (candidate) => candidate.kind === "approved_render_set",
  );
  assert.ok(approvedRenderSet, "visual approval did not produce an approved render set");
  const request = JSON.parse(await engine.readText(offered(view, "release_approval").taskArtifactId)) as {
    readonly sourceArtifactIds: readonly ArtifactId[];
  };
  return {
    view,
    offer: offered(view, "release_approval"),
    approvedRenderSetId: approvedRenderSet.id,
    sourceArtifactIds: request.sourceArtifactIds,
  };
}

test("a rejected release is surfaced and the edition can retry it", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-release-rejected-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  t.after(() => engine.close());
  const fixture = editionFixture("release-rejected");
  const started = await engine.start(fixture.spec);
  const release = await advanceToReleaseApproval(
    engine,
    started.runId,
    "release-rejected",
  );
  let view = await submit(
    engine,
    release.offer,
    {
      choice: "reject",
      publicationArtifactId: release.approvedRenderSetId,
      sourceArtifactIds: release.sourceArtifactIds,
      rationale: "Printer handoff is not approved",
    },
    [answerArtifact(
      artifactId("release-rejected-decision"),
      "release_decision",
    )],
  );
  const root = view.actors.find((actor) => actor.parentActorId === undefined);
  assert.equal(root?.state, "release_rejected");
  assert.ok(root);
  await engine.retry(started.runId, root.id);
  view = await engine.inspect(started.runId);
  assert.equal(offered(view, "release_approval").status, "offered");
});

test("Edition 4 stages an immutable request satisfying the renderer contract", async () => {
  const projectRoot = resolve(import.meta.dirname, "../..");
  const temporary = await mkdtemp(join(tmpdir(), "mag-edition4-adapter-contract-"));
  try {
    const artifactRoot = join(temporary, "artifacts");
    const fixture = await stageEdition4Fixture(projectRoot, artifactRoot);
    const { manifest } = fixture;

    assert.equal(manifest.schemaVersion, 1);
    assert.equal(manifest.rendererContractVersion, RENDERER_CONTRACT_VERSION);
    assert.equal(manifest.operation, "render_edition");
    assert.equal(manifest.editionId, EDITION_4_ID);
    assert.equal(manifest.primaryLanguage, "en");
    assert.deepEqual(manifest.languages, ["en", "es"]);
    assert.equal(manifest.renderer, "weasyprint");
    assert.deepEqual(manifest.metadata, {
      fixture: "released-edition-4",
      imageGenerationAllowed: false,
    });

    assert.equal(manifest.inputs.length, fixture.entries.length);
    assert.equal(new Set(manifest.inputs.map(({ artifactId }) => artifactId)).size, manifest.inputs.length);
    assert.equal(new Set(manifest.inputs.map(({ targetPath }) => targetPath)).size, manifest.inputs.length);
    assert.deepEqual(
      manifest.inputs.map(({ artifactId, targetPath }) => ({ artifactId, targetPath })),
      fixture.entries.map(({ artifactId, target }) => ({ artifactId, targetPath: target })),
    );

    for (const input of manifest.inputs) {
      assert.equal(isAbsolute(input.sourcePath), true);
      const relation = relative(artifactRoot, input.sourcePath);
      assert.equal(relation.startsWith("..") || isAbsolute(relation), false);
      assert.deepEqual(
        await readFile(input.sourcePath),
        await readFile(join(projectRoot, input.targetPath)),
        `staged bytes drifted for ${input.targetPath}`,
      );
    }

    const inputIds = new Set(manifest.inputs.map(({ artifactId }) => artifactId));
    assert.equal(fixture.selectedArtArtifactIds.length, 13);
    assert.equal(fixture.sourceFigureArtifactIds.length, 7);
    for (const artifactId of [
      ...fixture.selectedArtArtifactIds,
      ...fixture.sourceFigureArtifactIds,
    ]) {
      assert.equal(inputIds.has(artifactId), true);
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("stale visual approval cannot create an approved render set", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-stale-render-approval-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  try {
    const fixture = editionFixture("stale-render");
    const started = await engine.start(fixture.spec);
    const visual = await advanceToVisualReview(engine, started.runId, "stale-render");
    const decisionId = artifactId("stale-render-visual-decision");

    const view = await submit(
      engine,
      visual.offer,
      {
        decision: "approved",
        renderArtifactIds: [visual.renderArtifactIds[0], "obsolete-booklet"],
      },
      [answerArtifact(decisionId, "visual_review_decision")],
    );

    assert.equal(
      view.actors.some(
        (actor) => actor.machine === "render" && actor.state === "visual_changes_required",
      ),
      true,
    );
    assert.equal(view.artifacts.some((artifact) => artifact.kind === "approved_render_set"), false);
    assert.equal(
      view.offers.some(
        (candidate) => candidate.role === "release_approval" && candidate.status === "offered",
      ),
      false,
    );
    assert.equal(view.status, "waiting");

    const decision = await engine.readArtifact(decisionId);
    assert.deepEqual(
      new Set(decision.artifact.parents.map(({ artifactId: parentId }) => parentId)),
      new Set([
        visual.offer.taskArtifactId,
        visual.renderManifestId,
        ...visual.renderArtifactIds,
        visual.inspectionId,
      ]),
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render lineage binds release to the exact immutable artifacts", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-lineage-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  try {
    const prefix = "approved-render";
    const fixture = editionFixture(prefix);
    const started = await engine.start(fixture.spec);
    const visual = await advanceToVisualReview(engine, started.runId, prefix);
    const editionReviewId = artifactId(`${prefix}-edition-review`);

    const manifestBeforeRelease = await engine.readArtifact(visual.renderManifestId);
    assert.deepEqual(JSON.parse(Buffer.from(manifestBeforeRelease.bytes).toString("utf8")), {
      editionId: `${prefix}-edition`,
      content: [fixture.ids.manuscript, fixture.ids.editorial],
      translations: [],
      translationProofs: [],
      art: [fixture.ids.selectedArt],
      editionApproval: [editionReviewId],
      configuredLanguages: ["en"],
      renderProfileArtifactId: fixture.ids.renderProfile,
      printerProfileArtifactId: fixture.ids.printerProfile,
    });
    assert.deepEqual(manifestBeforeRelease.artifact.parents, [
      { artifactId: fixture.ids.manuscript, relation: "content" },
      { artifactId: fixture.ids.editorial, relation: "content" },
      { artifactId: fixture.ids.selectedArt, relation: "selected_art" },
      { artifactId: editionReviewId, relation: "edition_approval" },
      { artifactId: fixture.ids.renderProfile, relation: "render_profile" },
      { artifactId: fixture.ids.printerProfile, relation: "printer_profile" },
    ]);

    const visualDecisionId = artifactId(`${prefix}-visual-decision`);
    const afterVisualApproval = await submit(
      engine,
      visual.offer,
      {
        decision: "approved",
        renderArtifactIds: [...visual.renderArtifactIds].reverse(),
      },
      [answerArtifact(visualDecisionId, "visual_review_decision")],
    );
    const approvedSet = afterVisualApproval.artifacts.find(
      (candidate) => candidate.kind === "approved_render_set",
    );
    assert.ok(approvedSet, "exact visual approval did not register an approved render set");

    const approvedSetBeforeRelease = await engine.readArtifact(approvedSet.id);
    assert.deepEqual(JSON.parse(Buffer.from(approvedSetBeforeRelease.bytes).toString("utf8")), {
      editionId: `${prefix}-edition`,
      renderArtifactIds: visual.renderArtifactIds,
      inspectionArtifactId: visual.inspectionId,
      visualDecisionArtifactId: visualDecisionId,
      printerProfileArtifactId: fixture.ids.printerProfile,
      printerPreflightArtifactIds: [visual.renderArtifactIds[5]],
      studioPolicy: "home_ready_studio_blocked",
      studioReady: false,
    });
    assert.deepEqual(approvedSetBeforeRelease.artifact.parents, [
      ...visual.renderArtifactIds.map((artifactId) => ({
        artifactId,
        relation: "approved_render",
      })),
      { artifactId: visual.inspectionId, relation: "render_inspection" },
      { artifactId: visualDecisionId, relation: "visual_approval" },
    ]);
    for (const renderArtifactId of visual.renderArtifactIds) {
      const rendered = await engine.readArtifact(renderArtifactId);
      assert.equal(
        rendered.artifact.parents.some(
          (parent) => parent.artifactId === visual.renderManifestId,
        ),
        true,
      );
    }

    const release = offered(afterVisualApproval, "release_approval");
    const releaseRequest = JSON.parse(await engine.readText(release.taskArtifactId)) as {
      readonly sourceArtifactIds: readonly ArtifactId[];
    };
    assert.equal(release.subjectArtifactId, approvedSet.id);
    assert.notEqual(release.taskArtifactId, approvedSet.id);
    assert.deepEqual(release.inputArtifacts, [
      release.taskArtifactId,
      approvedSet.id,
      ...releaseRequest.sourceArtifactIds,
      fixture.ids.printerProfile,
      visual.renderArtifactIds[5],
    ]);

    const releaseDecisionId = artifactId(`${prefix}-release-decision`);
    const released = await submit(
      engine,
      release,
      {
        choice: "approve",
        publicationArtifactId: approvedSet.id,
        sourceArtifactIds: [...releaseRequest.sourceArtifactIds].reverse(),
      },
      [answerArtifact(releaseDecisionId, "release_decision")],
    );
    assert.equal(released.status, "complete");
    assert.equal(
      released.actors.some(
        (actor) => actor.machine === "edition" && actor.state === "released",
      ),
      true,
    );

    const releaseDecision = await engine.readArtifact(releaseDecisionId);
    assert.deepEqual(
      new Set(releaseDecision.artifact.parents.map(({ artifactId: parentId }) => parentId)),
      new Set([
        release.taskArtifactId,
        approvedSet.id,
        ...releaseRequest.sourceArtifactIds,
        fixture.ids.printerProfile,
        visual.renderArtifactIds[5],
      ]),
    );
    assert.deepEqual(await engine.readBytes(visual.renderManifestId), manifestBeforeRelease.bytes);
    assert.deepEqual(await engine.readBytes(approvedSet.id), approvedSetBeforeRelease.bytes);
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("viewer rejects stale and duplicate human answers without advancing the run", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-viewer-revision-safe-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  try {
    const engineFixture = editionFixture("viewer-engine-answer");
    const engineStarted = await engine.start(engineFixture.spec);
    const engineBefore = await engine.inspect(engineStarted.runId);
    const engineOffer = offered(engineBefore, "close_collection");
    const engineClaim = await engine.claim(engineOffer.id, workerFor(engineOffer));
    const engineAnswer = {
      contractVersion: engineOffer.contractVersion,
      result: { choice: "close" },
      artifacts: [{
        kind: "collection_decision",
        schemaVersion: "test/1",
        mediaType: "application/json",
        payload: { kind: "json", value: { choice: "close" } },
      }],
    } as const;
    const engineAccepted = await engine.answer(engineClaim, engineAnswer);
    assert.equal(
      engineAccepted.decisions.filter((decision) => decision.choice === "close_collection").length,
      1,
    );
    await assert.rejects(
      engine.claim(engineOffer.id, workerFor(engineOffer)),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "WORK_UNAVAILABLE",
    );
    const engineDuplicate = await engine.answer(engineClaim, engineAnswer);
    assert.equal(engineDuplicate.headSequence, engineAccepted.headSequence);
    assert.equal(
      engineDuplicate.decisions.filter((decision) => decision.choice === "close_collection").length,
      1,
    );

    let viewer;
    try {
      viewer = await serveRunViewer(engine, {
        host: "127.0.0.1",
        port: 0,
        staticDirectory: temporary,
      });
    } catch (error: unknown) {
      if (
        typeof error === "object" &&
        error !== null &&
        "code" in error &&
        error.code === "EPERM"
      ) {
        t.diagnostic("loopback listen is unavailable; durable engine assertions passed");
        return;
      }
      throw error;
    }

    try {
      const fixture = editionFixture("viewer-http-answer");
      const started = await engine.start(fixture.spec);
      const before = await engine.inspect(started.runId);
      const closeCollection = offered(before, "close_collection");
      const endpoint = `http://${viewer.host}:${viewer.port}/api/offers/${encodeURIComponent(closeCollection.id)}/answer`;

      const staleRoute = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          runId: started.runId,
          expectedOfferId: "a-different-offer",
          result: { choice: "close" },
          artifacts: [answerArtifact(
            artifactId("viewer-http-stale-collection-decision"),
            "collection_decision",
          )],
        }),
      });
      assert.equal(staleRoute.status, 409);
      assert.match(await staleRoute.text(), /expectedOfferId/);
      const afterStaleRoute = await engine.inspect(started.runId);
      assert.equal(afterStaleRoute.headSequence, before.headSequence);
      assert.equal(
        afterStaleRoute.offers.find(({ id }) => id === closeCollection.id)?.status,
        "offered",
      );

      const accepted = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          runId: started.runId,
          expectedOfferId: closeCollection.id,
          result: { choice: "close" },
          artifacts: [answerArtifact(
            artifactId("viewer-http-collection-decision"),
            "collection_decision",
          )],
        }),
      });
      assert.equal(accepted.status, 200);
      const afterAccepted = await engine.inspect(started.runId);
      assert.equal(
        afterAccepted.offers.find(({ id }) => id === closeCollection.id)?.status,
        "answered",
      );
      assert.equal(
        afterAccepted.decisions.filter((decision) => decision.choice === "close_collection").length,
        1,
      );

      const duplicate = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          runId: started.runId,
          expectedOfferId: closeCollection.id,
          result: { choice: "close" },
          artifacts: [answerArtifact(
            artifactId("viewer-http-duplicate-collection-decision"),
            "collection_decision",
          )],
        }),
      });
      assert.equal(duplicate.status, 409);
      assert.match(await duplicate.text(), /not available/);
      const afterDuplicate = await engine.inspect(started.runId);
      assert.equal(afterDuplicate.headSequence, afterAccepted.headSequence);
      assert.equal(
        afterDuplicate.decisions.filter((decision) => decision.choice === "close_collection").length,
        1,
      );
    } finally {
      await viewer.close();
    }
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("release is atomic and one stable source identity cannot cross editions", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-atomic-release-"));
  let crashNextCommit = false;
  const failpoints = {
    hit(name: RunEngineFailpoint): void {
      if (crashNextCommit && name === "advance.before_commit") {
        crashNextCommit = false;
        throw new Error("simulated release commit crash");
      }
    },
  };
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
    failpoints,
  });
  try {
    const stableSourceId = "stable-source-across-revisions";
    const firstFixture = editionFixture("atomic-first", {
      sourceId: stableSourceId,
    });
    const firstStarted = await engine.start(firstFixture.spec);
    const firstRelease = await advanceToReleaseApproval(
      engine,
      firstStarted.runId,
      "atomic-first",
    );

    crashNextCommit = true;
    await assert.rejects(
      submit(
        engine,
        firstRelease.offer,
        {
          choice: "approve",
          publicationArtifactId: firstRelease.approvedRenderSetId,
          sourceArtifactIds: [...firstRelease.sourceArtifactIds].reverse(),
        },
        [answerArtifact(artifactId("atomic-first-release-decision"), "release_decision")],
      ),
      /simulated release commit crash/,
    );
    const afterCrash = await engine.inspect(firstStarted.runId);
    assert.notEqual(afterCrash.status, "complete");
    assert.equal(
      afterCrash.actors.some(
        (actor) => actor.machine === "release" && actor.state === "released",
      ),
      false,
    );

    const recovered = await engine.advance(firstStarted.runId);
    assert.equal(recovered.status, "complete");
    assert.equal((await engine.inspect(firstStarted.runId)).status, "complete");

    const secondFixture = editionFixture("atomic-second", {
      sourceId: stableSourceId,
    });
    assert.notEqual(
      firstFixture.ids.sourceExtraction,
      secondFixture.ids.sourceExtraction,
      "the duplicate release must use a distinct extraction revision",
    );
    const secondStarted = await engine.start(secondFixture.spec);
    const secondRelease = await advanceToReleaseApproval(
      engine,
      secondStarted.runId,
      "atomic-second",
    );
    await submit(
      engine,
      secondRelease.offer,
      {
        choice: "approve",
        publicationArtifactId: secondRelease.approvedRenderSetId,
        sourceArtifactIds: secondRelease.sourceArtifactIds,
      },
      [answerArtifact(artifactId("atomic-second-release-decision"), "release_decision")],
    );

    const refused = await engine.inspect(secondStarted.runId);
    assert.ok(
      refused.status === "failed" || refused.status === "escalated",
      `duplicate source release ended as ${refused.status}`,
    );
    assert.equal(
      refused.actors.some(
        (actor) => actor.machine === "edition" && actor.state === "released",
      ),
      false,
    );
    const sequenceAfterRefusal = refused.headSequence;
    await engine.advance(secondStarted.runId);
    const afterRepeatedAdvance = await engine.inspect(secondStarted.runId);
    assert.equal(afterRepeatedAdvance.headSequence, sequenceAfterRefusal);
    assert.equal(afterRepeatedAdvance.status, refused.status);
    assert.equal((await engine.inspect(firstStarted.runId)).status, "complete");
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
