import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  RunId,
  RunView,
  WorkOfferView,
} from "../contracts/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";
import { prepareLegacyEditionReleaseSnapshot } from "./internal-schema-test-helper.ts";

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function textSeed(id: ArtifactId, kind = "fixture_input"): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: `fixture ${id}` },
  };
}

function answerArtifact(
  id: ArtifactId,
  kind: string,
  value: JsonObject = { fixture: id },
): AnswerArtifact {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "application/json",
    payload: { kind: "json", value },
  };
}

function offered(view: RunView, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(
    offer,
    `run did not expose an offered ${role} task: ${JSON.stringify({
      actors: view.actors.map((actor) => [actor.logicalKey, actor.state, actor.status]),
      offers: view.offers.map((candidate) => [candidate.role, candidate.status]),
    })}`,
  );
  return offer;
}

const authorities = new WeakMap<SqliteRunEngine, AuthorityTestHarness>();

function authorityFor(engine: SqliteRunEngine): AuthorityTestHarness {
  const authority = authorities.get(engine);
  assert.ok(authority, "test engine is missing its authority fixture");
  return authority;
}

async function submit(
  engine: SqliteRunEngine,
  offer: WorkOfferView,
  result: JsonObject,
  artifacts: readonly AnswerArtifact[] = [],
): Promise<RunView> {
  const authority = authorityFor(engine);
  if (offer.requirements?.authority === "human") {
    const worker = await authority.workerFor(offer);
    const preparation = await engine.prepareHumanDecision(offer.id, worker);
    return await engine.decide(preparation, worker, {
      schemaVersion: "human-decision-intent/1",
      offerId: preparation.offerId,
      taskArtifactId: preparation.taskArtifactId,
      inputArtifactIds: preparation.inputArtifactIds,
      result,
    });
  }
  const claim = await authority.claim(engine, offer);
  if (offer.role === "durable_checkpoint") {
    return await engine.answer(claim, await durableCheckpointAnswer(engine, offer));
  }
  return await engine.answer(claim, {
    contractVersion: offer.contractVersion,
    result,
    artifacts,
  });
}

function freshLeadFixture(prefix: string): EditionRootRunSpec {
  const id = (name: string) => artifactId(`${prefix}-${name}`);
  const editionBrief = id("edition-brief");
  const lead = id("lead");
  const articleBrief = id("article-brief");
  const writerPrompt = id("writer-prompt");
  const worthPrompt = id("worth-prompt");
  const evidencePrompt = id("evidence-prompt");
  const craftPrompt = id("craft-prompt");
  const writingRules = id("writing-rules");
  const editorialBrief = id("editorial-brief");
  const coverBrief = id("cover-brief");
  const renderProfile = id("render-profile");
  const releasePlaceholder = id("release-placeholder");
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: [
      textSeed(editionBrief, "edition_brief"),
      textSeed(lead, "source_lead"),
      textSeed(articleBrief, "article_brief"),
      textSeed(writerPrompt, "writer_prompt"),
      textSeed(worthPrompt, "judge_prompt"),
      textSeed(evidencePrompt, "judge_prompt"),
      textSeed(craftPrompt, "judge_prompt"),
      textSeed(writingRules, "writing_rules"),
      textSeed(editorialBrief, "editorial_brief"),
      textSeed(coverBrief, "art_brief"),
      textSeed(renderProfile, "render_profile"),
      textSeed(releasePlaceholder, "release_placeholder"),
    ],
    edition: {
      editionId: `${prefix}-edition`,
      execution: { kind: "produce" },
      editionBrief,
      sources: [{ sourceId: "lead-one", leadArtifact: lead }],
      articles: [],
      editorial: {
        editorialId: "opening-editorial",
        briefArtifact: editorialBrief,
        writingRules,
        modelPolicy: { default: { adapter: "test", model: "test" } },
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
        publicationArtifact: releasePlaceholder,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
}

function plannedArticle(prefix: string, sourceIds: readonly string[]): JsonObject {
  return {
    articleId: "planned-article",
    contentMode: "faithful_edit",
    attribution: {
      kind: "source_author",
      byline: "Source Author",
      sourceAuthors: ["Source Author"],
      sourceIds,
    },
    editionContext: `${prefix}-edition-brief`,
    articleBrief: `${prefix}-article-brief`,
    sourceIds,
    writerPrompt: `${prefix}-writer-prompt`,
    judgePrompts: {
      worth: `${prefix}-worth-prompt`,
      evidence: `${prefix}-evidence-prompt`,
      craft: `${prefix}-craft-prompt`,
    },
    writingRules: `${prefix}-writing-rules`,
    policy: {
      maxIterations: 2,
      maximumReaderPages: 7,
      teaching: "not_applicable",
      enabledLenses: ["worth", "evidence", "craft"],
      blockingLenses: [],
    },
    modelPolicy: { default: { adapter: "test", model: "test" } },
  };
}

function plannedCover(prefix: string, articleIds: readonly string[]): JsonObject {
  return {
    key: "planned-cover",
    role: "cover",
    briefArtifact: `${prefix}-cover-brief`,
    required: true,
    dependencies: {
      articleIds,
      editorial: true,
    },
  };
}

async function readySourceAndOpenPlan(
  engine: SqliteRunEngine,
  runId: RunId,
  prefix: string,
): Promise<{
  readonly view: RunView;
  readonly extraction: ArtifactId;
  readonly planOffer: WorkOfferView;
}> {
  const raw = artifactId(`${prefix}-raw`);
  const metadata = artifactId(`${prefix}-metadata`);
  const rawEvidence = artifactId(`${prefix}-raw-evidence`);
  const extraction = artifactId(`${prefix}-extraction`);
  let view = await engine.inspect(runId);
  view = await submit(engine, offered(view, "capture_source"), { status: "complete" }, [
    answerArtifact(raw, "raw_source_bundle"),
    answerArtifact(rawEvidence, "raw_evidence"),
    answerArtifact(metadata, "source_metadata"),
  ]);
  view = await submit(engine, offered(view, "extract_source"), { status: "complete" }, [
    answerArtifact(extraction, "source_extraction"),
  ]);
  const sourceReview = offered(view, "review_source");
  assert.equal((await engine.readArtifact(sourceReview.taskArtifactId)).artifact.kind, "human_decision_request");
  view = await submit(engine, sourceReview, { decision: "approved" }, [
    answerArtifact(artifactId(`${prefix}-source-decision`), "source_review_decision"),
  ]);
  const closeCollection = offered(view, "close_collection");
  assert.equal((await engine.readArtifact(closeCollection.taskArtifactId)).artifact.kind, "human_decision_request");
  view = await submit(engine, closeCollection, { choice: "close" }, [
    answerArtifact(artifactId(`${prefix}-collection-decision`), "collection_decision"),
  ]);
  const planOffer = offered(view, "plan_edition");
  assert.equal((await engine.readArtifact(planOffer.taskArtifactId)).artifact.kind, "human_decision_request");
  return { view, extraction, planOffer };
}

test("an approved production plan resolves ready source names before spawning articles and editorial", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-dynamic-plan-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "run.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  authorities.set(engine, await AuthorityTestHarness.create(temporary));
  try {
    const prefix = "dynamic";
    const started = await engine.start(freshLeadFixture(prefix));
    const ready = await readySourceAndOpenPlan(engine, started.runId, prefix);
    assert.ok(ready.planOffer.inputArtifacts.includes(ready.extraction));

    const productionPlan = {
      contractVersion: "approved-production-plan/1",
      sourceAssignmentPolicy: "at_least_once",
      articles: [plannedArticle(prefix, ["lead-one"])],
      art: [plannedCover(prefix, ["planned-article"])],
      translations: [],
    } as const;
    let view = await submit(
      engine,
      ready.planOffer,
      { choice: "approve", productionPlan },
      [
      answerArtifact(artifactId(`${prefix}-production-plan`), "edition_plan", productionPlan),
      ],
    );

    const writer = offered(view, "writer");
    assert.ok(writer.inputArtifacts.includes(ready.extraction));
    assert.equal(
      writer.inputArtifacts.filter((candidate) => candidate === ready.extraction).length,
      1,
    );
    const manuscript = artifactId(`${prefix}-manuscript`);
    view = await submit(engine, writer, { status: "complete" }, [
      answerArtifact(manuscript, "article_manuscript"),
      answerArtifact(artifactId(`${prefix}-writer-notes`), "writer_working_notes"),
    ]);
    view = await submit(engine, offered(view, "measure_article"), {
      fits: true,
      openerFits: true,
      pageCount: 1,
    }, [answerArtifact(artifactId(`${prefix}-article-measurement`), "article_measurement")]);
    view = await submit(engine, offered(view, "worth"), { decision: "pass" });
    view = await submit(engine, offered(view, "evidence"), { decision: "pass" });
    view = await submit(engine, offered(view, "craft"), { decision: "pass" });
    view = await submit(engine, offered(view, "durable_checkpoint"), {});

    const editorial = offered(view, "editorial_writer");
    assert.ok(editorial.inputArtifacts.includes(manuscript));
    const editorialManuscript = artifactId(`${prefix}-editorial-manuscript`);
    view = await submit(engine, editorial, { status: "complete" }, [
      answerArtifact(editorialManuscript, "editorial_manuscript"),
    ]);
    view = await submit(engine, offered(view, "durable_checkpoint"), {});

    const planDecision = view.decisions.find((decision) => decision.offerId === ready.planOffer.id);
    assert.ok(planDecision);
    const planView = await engine.readArtifact(planDecision.artifactId);
    assert.ok(planView.artifact.parents.some((parent) => parent.artifactId === ready.extraction));
    const manuscriptView = await engine.readArtifact(manuscript);
    assert.ok(
      manuscriptView.artifact.parents.some((parent) => parent.artifactId === ready.extraction),
    );
    const editorialView = await engine.readArtifact(editorialManuscript);
    assert.ok(
      editorialView.artifact.parents.some((parent) => parent.artifactId === manuscript),
    );
    const cover = offered(view, "cover_image");
    assert.ok(cover.inputArtifacts.includes(manuscript));
    assert.ok(cover.inputArtifacts.includes(editorialManuscript));
    const coverCandidate = artifactId(`${prefix}-cover-candidate`);
    view = await submit(engine, cover, { status: "complete" }, [
      answerArtifact(coverCandidate, "cover_art_candidate"),
    ]);
    const selection = offered(view, "select_art");
    assert.equal((await engine.readArtifact(selection.taskArtifactId)).artifact.kind, "human_decision_request");
    view = await submit(
      engine,
      selection,
      { choice: "select", selectedArtifactId: coverCandidate },
      [answerArtifact(artifactId(`${prefix}-art-selection`), "art_selection")],
    );
    view = await submit(engine, offered(view, "durable_checkpoint"), {});

    const finding = artifactId(`${prefix}-article-finding`);
    view = await submit(
      engine,
      offered(view, "edition_review"),
      {
        decision: "revise",
        routes: [{ target: "planned-article", findingArtifactId: finding }],
      },
      [
        answerArtifact(artifactId(`${prefix}-edition-review`), "edition_review"),
        answerArtifact(finding, "finding"),
      ],
    );
    const revisionWriter = offered(view, "writer");
    assert.ok(revisionWriter.inputArtifacts.includes(finding));
    const revisedManuscript = artifactId(`${prefix}-revised-manuscript`);
    view = await submit(engine, revisionWriter, { status: "complete" }, [
      answerArtifact(revisedManuscript, "article_manuscript"),
      answerArtifact(
        artifactId(`${prefix}-revised-writer-notes`),
        "writer_working_notes",
      ),
    ]);
    view = await submit(engine, offered(view, "measure_article"), {
      fits: true,
      openerFits: true,
      pageCount: 1,
    }, [
      answerArtifact(
        artifactId(`${prefix}-revised-article-measurement`),
        "article_measurement",
      ),
    ]);
    view = await submit(engine, offered(view, "worth"), { decision: "pass" });
    view = await submit(engine, offered(view, "evidence"), { decision: "pass" });
    view = await submit(engine, offered(view, "craft"), { decision: "pass" });
    view = await submit(engine, offered(view, "durable_checkpoint"), {});

    const editorialRevision = offered(view, "editorial_writer");
    assert.ok(editorialRevision.inputArtifacts.includes(revisedManuscript));
    assert.ok(editorialRevision.inputArtifacts.includes(finding));
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("v1 edition migration re-checkpoints every accepted content and art child before composition", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-migration-child-backfill-"));
  const databasePath = join(temporary, "run.sqlite");
  const artifactDirectory = join(temporary, "artifacts");
  let engine = new SqliteRunEngine({ databasePath, artifactDirectory });
  const authority = await AuthorityTestHarness.create(temporary);
  authorities.set(engine, authority);
  try {
    const prefix = "migration-children";
    const started = await engine.start(freshLeadFixture(prefix));
    const ready = await readySourceAndOpenPlan(engine, started.runId, prefix);
    const productionPlan = {
      contractVersion: "approved-production-plan/1",
      sourceAssignmentPolicy: "at_least_once",
      articles: [plannedArticle(prefix, ["lead-one"])],
      art: [plannedCover(prefix, ["planned-article"])],
      translations: [],
    } as const;
    let view = await submit(engine, ready.planOffer, { choice: "approve", productionPlan }, [
      answerArtifact(artifactId(`${prefix}-production-plan`), "edition_plan", productionPlan),
    ]);
    view = await submit(engine, offered(view, "writer"), { status: "complete" }, [
      answerArtifact(artifactId(`${prefix}-manuscript`), "article_manuscript"),
      answerArtifact(artifactId(`${prefix}-writer-notes`), "writer_working_notes"),
    ]);
    view = await submit(engine, offered(view, "measure_article"), {
      fits: true,
      openerFits: true,
      pageCount: 1,
    }, [answerArtifact(artifactId(`${prefix}-measurement`), "article_measurement")]);
    view = await submit(engine, offered(view, "worth"), { decision: "pass" });
    view = await submit(engine, offered(view, "evidence"), { decision: "pass" });
    view = await submit(engine, offered(view, "craft"), { decision: "pass" });
    view = await submit(engine, offered(view, "durable_checkpoint"), {});
    view = await submit(engine, offered(view, "editorial_writer"), { status: "complete" }, [
      answerArtifact(artifactId(`${prefix}-editorial-manuscript`), "editorial_manuscript"),
    ]);
    view = await submit(engine, offered(view, "durable_checkpoint"), {});
    view = await submit(engine, offered(view, "cover_image"), { status: "complete" }, [
      answerArtifact(artifactId(`${prefix}-cover-candidate`), "cover_art_candidate"),
    ]);
    view = await submit(engine, offered(view, "select_art"), {
      choice: "select",
      selectedArtifactId: `${prefix}-cover-candidate`,
    }, [answerArtifact(artifactId(`${prefix}-art-selection`), "art_selection")]);
    view = await submit(engine, offered(view, "durable_checkpoint"), {});
    assert.ok(offered(view, "edition_review"));

    engine.close();
    prepareLegacyEditionReleaseSnapshot(databasePath, started.runId);
    engine = new SqliteRunEngine({ databasePath, artifactDirectory });
    authorities.set(engine, authority);
    const plan = await engine.planMigration({
      runId: started.runId,
      targetBundleVersion: "graph-execution@2",
    });
    assert.deepEqual(
      plan.actors.map((actor) => actor.machine).sort(),
      ["article", "cover_art", "edition", "editorial"],
    );
    await engine.migrate({
      runId: started.runId,
      expectedFrom: plan.expectedFrom,
      targetBundleVersion: plan.targetBundleVersion,
      expectedHeadEventId: plan.expectedHeadEventId,
      migrationId: "migration_child_backfill_fixture",
      idempotencyKey: "migration-child-backfill-fixture",
    });
    await engine.advance(started.runId);
    view = await engine.inspect(started.runId);
    const childOffers = view.offers.filter((offer) =>
      offer.status === "offered" && offer.role === "durable_checkpoint"
    );
    assert.equal(childOffers.length, 3);
    const kinds = await Promise.all(childOffers.map(async (offer) => {
      const task = JSON.parse(await engine.readText(offer.taskArtifactId)) as {
        readonly logicalItem: { readonly kind: string };
      };
      return task.logicalItem.kind;
    }));
    assert.deepEqual(kinds.sort(), ["article", "editorial", "image"]);
    assert.equal(kinds.includes("composition"), false);

    for (const [index, offer] of childOffers.entries()) {
      view = await submit(engine, offer, {});
      const compositionOffers = await Promise.all(
        view.offers
          .filter((candidate) => candidate.status === "offered" && candidate.role === "durable_checkpoint")
          .map(async (candidate) => JSON.parse(await engine.readText(candidate.taskArtifactId)) as {
            readonly logicalItem: { readonly kind: string };
          }),
      );
      assert.equal(
        compositionOffers.some((task) => task.logicalItem.kind === "composition"),
        index === childOffers.length - 1,
        "composition becomes offerable only after every migrated child is durably bound",
      );
    }
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("invalid source assignments fail before any planned production actor is spawned", async () => {
  const cases: readonly {
    readonly name: string;
    readonly sourceAssignmentPolicy: "at_least_once" | "exactly_once";
    readonly sourceIds?: readonly string[];
  }[] = [
    {
      name: "unknown-source",
      sourceAssignmentPolicy: "at_least_once",
      sourceIds: ["not-collected"],
    },
    {
      name: "unassigned-source",
      sourceAssignmentPolicy: "at_least_once",
    },
    {
      name: "duplicate-exact-assignment",
      sourceAssignmentPolicy: "exactly_once",
      sourceIds: ["lead-one", "lead-one"],
    },
  ];

  for (const candidate of cases) {
    const temporary = await mkdtemp(join(tmpdir(), `mag-invalid-plan-${candidate.name}-`));
    const engine = new SqliteRunEngine({
      databasePath: join(temporary, "run.sqlite"),
      artifactDirectory: join(temporary, "artifacts"),
    });
    authorities.set(engine, await AuthorityTestHarness.create(temporary));
    try {
      const started = await engine.start(freshLeadFixture(candidate.name));
      const ready = await readySourceAndOpenPlan(
        engine,
        started.runId,
        candidate.name,
      );
      const productionPlan = {
        contractVersion: "approved-production-plan/1",
        sourceAssignmentPolicy: candidate.sourceAssignmentPolicy,
        articles:
          candidate.sourceIds === undefined
            ? []
            : [plannedArticle(candidate.name, candidate.sourceIds)],
        art: [
          plannedCover(
            candidate.name,
            candidate.sourceIds === undefined ? [] : ["planned-article"],
          ),
        ],
        translations: [],
      };
      const view = await submit(
        engine,
        ready.planOffer,
        { choice: "approve", productionPlan },
        [
          answerArtifact(
            artifactId(`${candidate.name}-plan`),
            "edition_plan",
            productionPlan,
          ),
        ],
      );
      assert.equal(view.status, "failed", candidate.name);
      assert.equal(
        view.actors.some((actor) => actor.logicalKey.startsWith("article:")),
        false,
        candidate.name,
      );
    } finally {
      engine.close();
      await rm(temporary, { recursive: true, force: true });
    }
  }
});
