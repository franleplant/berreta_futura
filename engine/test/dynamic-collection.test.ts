import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactParent,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  RunView,
  SourceRunSpec,
  SubmitLeadRequest,
  WorkerIdentity,
  WorkOfferView,
} from "../contracts/index.ts";
import { RunEngineError, SqliteRunEngine } from "../run-engine/index.ts";

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(
  id: ArtifactId,
  kind = "fixture_input",
  parents: readonly ArtifactParent[] = [],
): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: `immutable ${kind} ${id}` },
    ...(parents.length === 0 ? {} : { parents }),
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

function emptyEdition(prefix: string): EditionRootRunSpec {
  const editionBrief = artifactId(`${prefix}-edition-brief`);
  const editorialBrief = artifactId(`${prefix}-editorial-brief`);
  const writingRules = artifactId(`${prefix}-writing-rules`);
  const renderProfile = artifactId(`${prefix}-render-profile`);
  const publication = artifactId(`${prefix}-publication`);
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: [
      seed(editionBrief, "edition_brief"),
      seed(editorialBrief, "editorial_brief"),
      seed(writingRules, "writing_rules"),
      seed(renderProfile, "render_profile"),
      seed(publication, "release_placeholder"),
    ],
    edition: {
      editionId: `${prefix}-edition`,
      editionBrief,
      sources: [],
      articles: [],
      editorial: {
        editorialId: `${prefix}-editorial`,
        briefArtifact: editorialBrief,
        writingRules,
        modelPolicy: { default: { adapter: "test", model: "deterministic" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: renderProfile,
        rendererContractVersion: "render-edition/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: publication,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "deterministic" } },
    },
  };
}

type ReleaseFixture = {
  readonly spec: EditionRootRunSpec;
  readonly editionBrief: ArtifactId;
  readonly articleBrief: ArtifactId;
  readonly writerPrompt: ArtifactId;
  readonly worthPrompt: ArtifactId;
  readonly evidencePrompt: ArtifactId;
  readonly craftPrompt: ArtifactId;
  readonly writingRules: ArtifactId;
  readonly initialManuscript: ArtifactId;
};

function releaseEdition(prefix: string): ReleaseFixture {
  const editionBrief = artifactId(`${prefix}-edition-brief`);
  const articleBrief = artifactId(`${prefix}-article-brief`);
  const writerPrompt = artifactId(`${prefix}-writer-prompt`);
  const worthPrompt = artifactId(`${prefix}-worth-prompt`);
  const evidencePrompt = artifactId(`${prefix}-evidence-prompt`);
  const craftPrompt = artifactId(`${prefix}-craft-prompt`);
  const writingRules = artifactId(`${prefix}-writing-rules`);
  const initialManuscript = artifactId(`${prefix}-initial-manuscript`);
  const editorialBrief = artifactId(`${prefix}-editorial-brief`);
  const initialEditorial = artifactId(`${prefix}-initial-editorial`);
  const renderProfile = artifactId(`${prefix}-render-profile`);
  const publication = artifactId(`${prefix}-publication`);
  return {
    editionBrief,
    articleBrief,
    writerPrompt,
    worthPrompt,
    evidencePrompt,
    craftPrompt,
    writingRules,
    initialManuscript,
    spec: {
      schemaVersion: 1,
      kind: "edition",
      artifacts: [
        seed(editionBrief, "edition_brief"),
        seed(articleBrief, "article_brief"),
        seed(writerPrompt, "writer_prompt"),
        seed(worthPrompt, "judge_prompt"),
        seed(evidencePrompt, "judge_prompt"),
        seed(craftPrompt, "judge_prompt"),
        seed(writingRules, "writing_rules"),
        seed(initialManuscript, "article_manuscript"),
        seed(editorialBrief, "editorial_brief"),
        seed(initialEditorial, "editorial_manuscript"),
        seed(renderProfile, "render_profile"),
        seed(publication, "release_placeholder"),
      ],
      edition: {
        editionId: `${prefix}-edition`,
        editionBrief,
        sources: [],
        articles: [],
        editorial: {
          editorialId: `${prefix}-editorial`,
          briefArtifact: editorialBrief,
          writingRules,
          initialManuscript: initialEditorial,
          modelPolicy: { default: { adapter: "test", model: "deterministic" } },
        },
        translations: [],
        art: [],
        render: {
          renderManifestArtifact: renderProfile,
          rendererContractVersion: "render-edition/1",
          configuredLanguages: ["en"],
          studioPolicy: "not_applicable",
        },
        release: {
          publicationArtifact: publication,
          sourceArtifacts: [],
          dryRun: false,
          target: "private",
        },
        modelPolicy: { default: { adapter: "test", model: "deterministic" } },
      },
    },
  };
}

function preparedLead(prefix: string, sourceId: string): {
  readonly request: SubmitLeadRequest;
  readonly lead: ArtifactId;
  readonly rawBundle: ArtifactId;
  readonly rawEvidence: ArtifactId;
  readonly extraction: ArtifactId;
  readonly metadata: ArtifactId;
  readonly approval: ArtifactId;
} {
  const lead = artifactId(`${prefix}-lead`);
  const rawBundle = artifactId(`${prefix}-raw-bundle`);
  const rawEvidence = artifactId(`${prefix}-raw-evidence`);
  const extraction = artifactId(`${prefix}-extraction`);
  const metadata = artifactId(`${prefix}-metadata`);
  const approval = artifactId(`${prefix}-source-approval`);
  const source: SourceRunSpec = {
    sourceId,
    leadArtifact: lead,
    rawBundleArtifact: rawBundle,
    rawEvidenceArtifacts: [rawEvidence],
    extractionArtifact: extraction,
    metadataArtifact: metadata,
    approvalArtifact: approval,
  };
  return {
    request: {
      source,
      artifacts: [
        seed(lead, "submitted_lead"),
        seed(rawBundle, "raw_source_bundle", [
          { artifactId: lead, relation: "captured_from_lead" },
        ]),
        seed(rawEvidence, "raw_evidence", [
          { artifactId: rawBundle, relation: "bundle_content" },
        ]),
        seed(extraction, "source_extraction", [
          { artifactId: rawEvidence, relation: "extracted_from" },
        ]),
        seed(metadata, "source_metadata", [
          { artifactId: rawBundle, relation: "describes_bundle" },
        ]),
        {
          ...seed(approval, "source_review_decision", [
            { artifactId: extraction, relation: "reviewed_extraction" },
            { artifactId: rawBundle, relation: "reviewed_raw_bundle" },
          ]),
          origin: "human",
        },
      ],
    },
    lead,
    rawBundle,
    rawEvidence,
    extraction,
    metadata,
    approval,
  };
}

function uncapturedLead(prefix: string, sourceId: string): {
  readonly request: SubmitLeadRequest;
  readonly lead: ArtifactId;
  readonly captureProfile: ArtifactId;
} {
  const lead = artifactId(`${prefix}-lead`);
  const captureProfile = artifactId(`${prefix}-capture-profile`);
  return {
    request: {
      source: {
        sourceId,
        leadArtifact: lead,
        captureProfileArtifact: captureProfile,
      },
      artifacts: [
        seed(lead, "submitted_lead"),
        seed(captureProfile, "capture_profile", [
          { artifactId: lead, relation: "capture_policy_for" },
        ]),
      ],
    },
    lead,
    captureProfile,
  };
}

function offered(view: RunView, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(offer, `run did not expose an offered ${role} task`);
  return offer;
}

function workerFor(offer: WorkOfferView): WorkerIdentity {
  return {
    principalId: `worker-${offer.id}`,
    authority: offer.allowedWorkerCapabilities.includes("human")
      ? "human"
      : offer.allowedWorkerCapabilities.includes("text_model")
        ? "model"
        : "tool",
    capabilities: offer.allowedWorkerCapabilities,
  };
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

function approvedPlan(
  fixture: ReleaseFixture,
  sourceId: string,
): JsonObject {
  return {
    contractVersion: "approved-production-plan/1",
    sourceAssignmentPolicy: "exactly_once",
    articles: [
      {
        articleId: `${sourceId}-article`,
        contentMode: "faithful_edit",
        attribution: {
          kind: "source_author",
          byline: "Source Author",
          sourceAuthors: ["Source Author"],
          sourceIds: [sourceId],
        },
        editionContext: fixture.editionBrief,
        articleBrief: fixture.articleBrief,
        sourceIds: [sourceId],
        writerPrompt: fixture.writerPrompt,
        judgePrompts: {
          worth: fixture.worthPrompt,
          evidence: fixture.evidencePrompt,
          craft: fixture.craftPrompt,
        },
        writingRules: fixture.writingRules,
        initialManuscript: fixture.initialManuscript,
        policy: {
          maxIterations: 2,
          maximumReaderPages: 7,
          teaching: "not_applicable",
          enabledLenses: ["worth", "evidence", "craft"],
          blockingLenses: [],
        },
        modelPolicy: { default: { adapter: "test", model: "deterministic" } },
      },
    ],
    art: [],
    translations: [],
  };
}

async function closeAndPlan(
  engine: SqliteRunEngine,
  view: RunView,
  fixture: ReleaseFixture,
  sourceId: string,
  prefix: string,
): Promise<RunView> {
  const sourceReview = view.offers.find(
    (offer) => offer.role === "review_source" && offer.status === "offered",
  );
  if (sourceReview !== undefined) {
    view = await submit(engine, sourceReview, { decision: "approved" }, [
      answerArtifact(artifactId(`${prefix}-fresh-source-review`), "source_review_decision"),
    ]);
  }
  view = await submit(engine, offered(view, "close_collection"), { choice: "close" }, [
    answerArtifact(artifactId(`${prefix}-collection-decision`), "collection_decision"),
  ]);
  const plan = approvedPlan(fixture, sourceId);
  return await submit(
    engine,
    offered(view, "plan_edition"),
    { choice: "approve", productionPlan: plan },
    [answerArtifact(artifactId(`${prefix}-edition-plan`), "edition_plan", plan)],
  );
}

async function advanceToReleaseApproval(
  engine: SqliteRunEngine,
  runId: RunView["id"],
  prefix: string,
): Promise<{
  readonly view: RunView;
  readonly offer: WorkOfferView;
  readonly publicationArtifactId: ArtifactId;
  readonly sourceArtifactIds: readonly ArtifactId[];
}> {
  let renderArtifactIds: readonly ArtifactId[] = [];
  for (let step = 0; step < 40; step += 1) {
    const view = await engine.inspect(runId);
    const release = view.offers.find(
      (candidate) => candidate.role === "release_approval" && candidate.status === "offered",
    );
    if (release !== undefined) {
      const request = JSON.parse(await engine.readText(release.taskArtifactId)) as {
        readonly publicationArtifactId: ArtifactId;
        readonly sourceArtifactIds: readonly ArtifactId[];
      };
      return {
        view,
        offer: release,
        publicationArtifactId: request.publicationArtifactId,
        sourceArtifactIds: request.sourceArtifactIds,
      };
    }
    const next = view.offers.find((candidate) => candidate.status === "offered");
    assert.ok(next, `run stopped before release approval in ${view.actors[0]?.state}`);
    switch (next.role) {
      case "measure_article":
        await submit(engine, next, { fits: true, pageCount: 1, openerFits: true }, [
          answerArtifact(
            artifactId(`${prefix}-${next.id}-article-measurement`),
            "article_measurement",
          ),
        ]);
        break;
      case "worth":
      case "evidence":
      case "craft":
        await submit(engine, next, { decision: "pass" }, []);
        break;
      case "edition_review":
        await submit(engine, next, { decision: "approved" }, [
          answerArtifact(artifactId(`${prefix}-edition-review`), "edition_review"),
        ]);
        break;
      case "measure_edition":
        await submit(engine, next, { fits: true }, [
          answerArtifact(artifactId(`${prefix}-edition-measurement`), "edition_measurement"),
        ]);
        break;
      case "render": {
        renderArtifactIds = [
          artifactId(`${prefix}-reader`),
          artifactId(`${prefix}-web`),
          artifactId(`${prefix}-booklet`),
          artifactId(`${prefix}-package`),
          artifactId(`${prefix}-render-critic`),
          artifactId(`${prefix}-printer-preflight`),
        ];
        await submit(engine, next, { renderedLanguages: ["en"] }, [
          answerArtifact(
            renderArtifactIds[0] as ArtifactId,
            "reader_pdf",
            { fixture: "reader" },
            { relativePath: "en/reader.pdf" },
          ),
          answerArtifact(
            renderArtifactIds[1] as ArtifactId,
            "web_output",
            { fixture: "web" },
            { relativePath: "en/web.html" },
          ),
          answerArtifact(
            renderArtifactIds[2] as ArtifactId,
            "booklet_pdf",
            { fixture: "booklet" },
            { relativePath: "en/booklet.pdf" },
          ),
          answerArtifact(
            renderArtifactIds[3] as ArtifactId,
            "package_artifact",
            { fixture: "package" },
            { relativePath: "en/package.zip" },
          ),
          answerArtifact(
            renderArtifactIds[4] as ArtifactId,
            "render_critic_report",
            { fixture: "critic" },
            { relativePath: "en/render-critic.json" },
          ),
          answerArtifact(
            renderArtifactIds[5] as ArtifactId,
            "printer_preflight",
            { fixture: "preflight" },
            { relativePath: "en/preflight.json" },
          ),
        ]);
        break;
      }
      case "render_inspection":
        assert.equal(renderArtifactIds.length, 6);
        await submit(
          engine,
          next,
          {
            result: "pass",
            renderArtifactIds,
            printerPreflightArtifactIds: [renderArtifactIds[5] as ArtifactId],
            studioReady: false,
          },
          [answerArtifact(artifactId(`${prefix}-render-inspection`), "render_inspection")],
        );
        break;
      case "visual_review":
        await submit(
          engine,
          next,
          { decision: "approved", renderArtifactIds },
          [
            answerArtifact(
              artifactId(`${prefix}-visual-review-decision`),
              "visual_review_decision",
            ),
          ],
        );
        break;
      default:
        assert.fail(`unexpected work role before release: ${next.role}`);
    }
  }
  assert.fail("run exceeded release preparation step limit");
}

function hasAncestor(
  view: RunView,
  descendant: ArtifactId,
  ancestor: ArtifactId,
): boolean {
  const artifacts = new Map(view.artifacts.map((artifact) => [artifact.id, artifact]));
  const pending = [descendant];
  const visited = new Set<ArtifactId>();
  while (pending.length > 0) {
    const current = pending.pop();
    if (current === undefined || visited.has(current)) {
      continue;
    }
    visited.add(current);
    for (const parent of artifacts.get(current)?.parents ?? []) {
      if (parent.artifactId === ancestor) {
        return true;
      }
      pending.push(parent.artifactId);
    }
  }
  return false;
}

test("dynamic collection survives restart and freezes accepted sources into planning and forks", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-dynamic-collection-"));
  const databasePath = join(temporary, "runs.sqlite");
  const artifactDirectory = join(temporary, "artifacts");
  let engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  try {
    const started = await engine.start(emptyEdition("dynamic"));
    let view = await engine.inspect(started.runId);
    assert.equal(view.actors.find((actor) => actor.parentActorId === undefined)?.state,
      "collecting");
    assert.deepEqual(view.sourceSubmissions, []);

    const archived = preparedLead("archived", "archived-source");
    view = await engine.submitLead(started.runId, archived.request);
    assert.equal(view.sourceSubmissions.length, 1);
    assert.equal(view.sourceSubmissions[0]?.sourceId, "archived-source");
    assert.equal(
      view.actors.find((actor) => actor.logicalKey === "source:archived-source")?.state,
      "awaiting_source_review",
    );
    view = await submit(engine, offered(view, "review_source"), { decision: "approved" }, [
      answerArtifact(artifactId("archived-fresh-source-review"), "source_review_decision"),
    ]);

    const live = uncapturedLead("live", "live-source");
    view = await engine.submitLead(started.runId, live.request);
    assert.equal(view.sourceSubmissions.length, 2);
    assert.equal(
      view.actors.find((actor) => actor.logicalKey === "source:live-source")?.state,
      "capturing",
    );

    engine.close();
    engine = new SqliteRunEngine({ databasePath, artifactDirectory });
    view = await engine.inspect(started.runId);
    assert.equal(view.sourceSubmissions.length, 2);
    assert.equal(offered(view, "capture_source").subjectArtifactId, live.lead);

    const liveBundle = artifactId("live-raw-bundle");
    const liveEvidence = artifactId("live-raw-evidence");
    const liveMetadata = artifactId("live-source-metadata");
    view = await submit(engine, offered(view, "capture_source"), { status: "complete" }, [
      answerArtifact(liveBundle, "raw_source_bundle"),
      answerArtifact(liveEvidence, "raw_evidence"),
      answerArtifact(liveMetadata, "source_metadata"),
    ]);
    const liveExtraction = artifactId("live-extraction");
    view = await submit(engine, offered(view, "extract_source"), { status: "complete" }, [
      answerArtifact(liveExtraction, "source_extraction"),
    ]);
    view = await submit(engine, offered(view, "review_source"), { decision: "approved" }, [
      answerArtifact(artifactId("live-source-review"), "source_review_decision"),
    ]);
    assert.equal(
      view.actors.find((actor) => actor.logicalKey === "source:live-source")?.state,
      "ready",
    );
    assert.equal(hasAncestor(view, archived.extraction, archived.lead), true);
    assert.equal(hasAncestor(view, liveExtraction, live.lead), true);

    await assert.rejects(
      engine.submitLead(started.runId, archived.request),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "LEAD_SOURCE_DUPLICATE",
    );

    const close = offered(view, "close_collection");
    view = await submit(engine, close, { choice: "close" }, [
      answerArtifact(artifactId("dynamic-close-decision"), "collection_decision"),
    ]);
    const plan = offered(view, "plan_edition");
    assert.equal(plan.inputArtifacts.includes(archived.extraction), true);
    assert.equal(plan.inputArtifacts.includes(liveExtraction), true);
    const planRequest = JSON.parse(await engine.readText(plan.taskArtifactId)) as {
      readonly readySources: readonly {
        readonly sourceId: string;
        readonly extractionArtifactId: string;
      }[];
    };
    assert.deepEqual(planRequest.readySources, [
      { sourceId: "archived-source", extractionArtifactId: archived.extraction },
      { sourceId: "live-source", extractionArtifactId: liveExtraction },
    ]);

    const tooLate = uncapturedLead("late", "late-source");
    await assert.rejects(
      engine.submitLead(started.runId, tooLate.request),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "COLLECTION_CLOSED",
    );

    const replacementExtraction = artifactId("archived-extraction-v2");
    const forked = await engine.fork(started.runId, [
      {
        kind: "replace_artifact",
        from: archived.extraction,
        to: seed(replacementExtraction, "source_extraction", [
          { artifactId: archived.rawEvidence, relation: "extracted_from" },
        ]),
      },
    ]);
    const forkView = await engine.inspect(forked.runId);
    const forkRoot = forkView.actors.find((actor) => actor.parentActorId === undefined);
    assert.ok(forkRoot);
    const forkSpec = forkRoot.input.spec as {
      readonly sources: readonly SourceRunSpec[];
    };
    assert.deepEqual(
      forkSpec.sources.map((source) => source.sourceId),
      ["archived-source", "live-source"],
    );
    assert.equal(
      forkSpec.sources.find((source) => source.sourceId === "archived-source")
        ?.extractionArtifact,
      replacementExtraction,
    );
    assert.equal(
      forkSpec.sources.find((source) => source.sourceId === "live-source")
        ?.extractionArtifact,
      liveExtraction,
    );
    assert.equal(hasAncestor(forkView, replacementExtraction, archived.lead), true);
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("release uniqueness includes dynamically collected source identities", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-dynamic-release-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  try {
    const sourceId = "stable-dynamic-source";
    const firstFixture = releaseEdition("dynamic-release-first");
    const firstStarted = await engine.start(firstFixture.spec);
    const firstLead = preparedLead("dynamic-release-first", sourceId);
    let firstView = await engine.submitLead(firstStarted.runId, firstLead.request);
    firstView = await closeAndPlan(
      engine,
      firstView,
      firstFixture,
      sourceId,
      "dynamic-release-first",
    );
    const firstRelease = await advanceToReleaseApproval(
      engine,
      firstStarted.runId,
      "dynamic-release-first",
    );
    firstView = await submit(
      engine,
      firstRelease.offer,
      {
        choice: "approve",
        publicationArtifactId: firstRelease.publicationArtifactId,
        sourceArtifactIds: firstRelease.sourceArtifactIds,
      },
      [answerArtifact(artifactId("dynamic-release-first-decision"), "release_decision")],
    );
    assert.equal(firstView.status, "complete");

    const secondFixture = releaseEdition("dynamic-release-second");
    const secondStarted = await engine.start(secondFixture.spec);
    const secondLead = preparedLead("dynamic-release-second", sourceId);
    let secondView = await engine.submitLead(secondStarted.runId, secondLead.request);
    secondView = await closeAndPlan(
      engine,
      secondView,
      secondFixture,
      sourceId,
      "dynamic-release-second",
    );
    const secondRelease = await advanceToReleaseApproval(
      engine,
      secondStarted.runId,
      "dynamic-release-second",
    );
    secondView = await submit(
      engine,
      secondRelease.offer,
      {
        choice: "approve",
        publicationArtifactId: secondRelease.publicationArtifactId,
        sourceArtifactIds: secondRelease.sourceArtifactIds,
      },
      [answerArtifact(artifactId("dynamic-release-second-decision"), "release_decision")],
    );
    assert.equal(secondView.status, "failed");
    assert.equal(
      secondView.actors.some(
        (actor) => actor.machine === "release" && actor.status === "failed",
      ),
      true,
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
