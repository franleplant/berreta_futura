import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, test } from "node:test";

import type {
  ActorId,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  ArticleRunSpec,
  EditionRootRunSpec,
  EditionRunSpec,
  JsonObject,
  ModelPolicy,
  RunId,
  RunView,
} from "../contracts/index.ts";
import {
  articleInitial,
  articleTransition,
  type ArticleMachineContext,
  type ArticleMachineEvent,
  type ArticleMachineInput,
} from "../machines/article-machine.ts";
import {
  editionReviewInitial,
  editionReviewTransition,
  type EditionReviewMachineContext,
  type EditionReviewMachineInput,
} from "../machines/edition-review-machine.ts";
import {
  editionInitial,
  editionTransition,
  type EditionMachineContext,
  type EditionMachineInput,
} from "../machines/edition-machine.ts";
import type {
  EditionReviewRunSpec,
  MachineEffect,
  MachineTransitionResult,
  SpawnActorEffect,
} from "../machines/runtime.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";

function actorId(value: string): ActorId {
  return value as ActorId;
}

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

const modelPolicy: ModelPolicy = {
  default: { adapter: "test", model: "deterministic" },
};

function articleSpec(overrides: Partial<ArticleRunSpec> = {}): ArticleRunSpec {
  return {
    articleId: "article-one",
    contentMode: "faithful_edit",
    attribution: {
      kind: "source_author",
      byline: "Source Author",
      sourceAuthors: ["Source Author"],
      sourceIds: ["source-one"],
    },
    editionContext: artifactId("edition-context"),
    articleBrief: artifactId("article-brief"),
    sources: [artifactId("source-one")],
    sourceApprovalArtifacts: [artifactId("source-one-source-review")],
    writerPrompt: artifactId("writer-prompt"),
    judgePrompts: {
      worth: artifactId("worth-prompt"),
      mechanics: artifactId("mechanics-prompt"),
      evidence: artifactId("evidence-prompt"),
      shape: artifactId("shape-prompt"),
      teaching: artifactId("teaching-prompt"),
      craft: artifactId("craft-prompt"),
    },
    writingRules: artifactId("writing-rules"),
    initialManuscript: artifactId("manuscript-v1"),
    policy: {
      maxIterations: 3,
      maximumReaderPages: 7,
      teaching: "applicable",
      enabledLenses: ["worth", "mechanics", "evidence", "shape", "teaching", "craft"],
      blockingLenses: ["mechanics", "evidence"],
    },
    modelPolicy,
    ...overrides,
  };
}

function articleInput(
  spec: ArticleRunSpec = articleSpec(),
  parentActorId?: ActorId,
): ArticleMachineInput {
  return {
    actorId: actorId("actor-article"),
    logicalKey: "article:article-one",
    spec,
    ...(parentActorId === undefined ? {} : { parentActorId }),
  };
}

function textSeed(
  id: ArtifactId,
  kind = "test_input",
  parents: ArtifactSeed["parents"] = [],
  origin: ArtifactSeed["origin"] = "imported",
): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin,
    payload: { kind: "text", text: `fixture ${id}` },
    ...(parents.length === 0 ? {} : { parents }),
  };
}

function articleRootSpec(spec: ArticleRunSpec): ArticleRootRunSpec {
  const references = [
    ...(spec.editionContext === undefined ? [] : [spec.editionContext]),
    spec.articleBrief,
    ...spec.sources,
    ...spec.sourceApprovalArtifacts,
    spec.writerPrompt,
    ...Object.values(spec.judgePrompts).filter(
      (candidate): candidate is ArtifactId => candidate !== undefined,
    ),
    spec.writingRules,
    ...(spec.initialManuscript === undefined ? [] : [spec.initialManuscript]),
  ];
  return {
    schemaVersion: 1,
    kind: "article",
    article: spec,
    artifacts: [...new Set(references)].map((artifactId) =>
      textSeed(artifactId, spec.sources.includes(artifactId) ? "source_extraction" : "test_input")
    ),
  };
}

function effectsOfType<EffectType extends MachineEffect["type"]>(
  result: MachineTransitionResult,
  type: EffectType,
): Extract<MachineEffect, { readonly type: EffectType }>[] {
  return result.effects.filter(
    (effect): effect is Extract<MachineEffect, { readonly type: EffectType }> =>
      effect.type === type,
  );
}

function offerRoles(result: MachineTransitionResult): readonly string[] {
  return effectsOfType(result, "create_work_offer").map((effect) => effect.role);
}

function completeArticleWork(
  result: MachineTransitionResult,
  slot: Extract<ArticleMachineEvent, { readonly type: "WORK_COMPLETED" }>["slot"],
  workResult: JsonObject,
  artifacts: readonly { readonly artifactId: ArtifactId; readonly kind: string }[] = [],
): MachineTransitionResult {
  return articleTransition(result.snapshot, {
    type: "WORK_COMPLETED",
    slot,
    artifacts,
    result: workResult,
  });
}

function settlePassingArticle(input: ArticleMachineInput): MachineTransitionResult {
  let result = articleInitial(input);
  result = articleTransition(result.snapshot, { type: "START" });
  result = completeArticleWork(result, "measure_article", {
    fits: true,
    openerFits: true,
    pageCount: 4,
  });
  result = completeArticleWork(result, "worth", { decision: "pass" });
  result = completeArticleWork(result, "mechanics", { decision: "pass" });
  result = completeArticleWork(result, "evidence", { decision: "pass" });
  result = completeArticleWork(result, "shape", { decision: "pass" });
  result = completeArticleWork(result, "teaching", { decision: "pass" });
  return completeArticleWork(result, "craft", { decision: "pass" });
}

describe("ArticleMachine orchestration", () => {
  test("opens judge stages in order and waits for every result in a stage", () => {
    let result = articleInitial(articleInput());
    result = articleTransition(result.snapshot, { type: "START" });
    assert.equal(result.snapshot.value, "stage_1");
    assert.deepEqual(offerRoles(result), ["measure_article", "worth", "mechanics"]);

    result = completeArticleWork(result, "worth", { decision: "pass" });
    assert.equal(result.snapshot.value, "stage_1");
    assert.deepEqual(result.effects, []);

    result = completeArticleWork(result, "measure_article", {
      fits: true,
      openerFits: true,
      pageCount: 5,
    });
    assert.equal(result.snapshot.value, "stage_1");
    assert.deepEqual(result.effects, []);

    result = completeArticleWork(result, "mechanics", { decision: "pass" });
    assert.equal(result.snapshot.value, "stage_2");
    assert.deepEqual(offerRoles(result), ["evidence", "shape"]);

    result = completeArticleWork(result, "shape", { decision: "pass" });
    assert.equal(result.snapshot.value, "stage_2");
    result = completeArticleWork(result, "evidence", { decision: "pass" });
    assert.equal(result.snapshot.value, "stage_3");
    assert.deepEqual(offerRoles(result), ["teaching", "craft"]);

    result = completeArticleWork(result, "craft", { decision: "pass" });
    assert.equal(result.snapshot.value, "stage_3");
    result = completeArticleWork(result, "teaching", { decision: "pass" });
    assert.equal(result.snapshot.value, "settled");
    assert.equal(effectsOfType(result, "complete_actor").length, 1);
  });

  test("short-circuits later judge stages after a blocking stage-one result", () => {
    let result = articleInitial(articleInput());
    result = articleTransition(result.snapshot, { type: "START" });
    result = completeArticleWork(result, "worth", { decision: "pass" });
    result = completeArticleWork(result, "mechanics", { decision: "pass" });
    result = completeArticleWork(
      result,
      "measure_article",
      { fits: false, openerFits: true, pageCount: 8 },
      [{ artifactId: artifactId("measurement-finding"), kind: "article_measurement" }],
    );

    assert.equal(result.snapshot.value, "drafting");
    assert.deepEqual(offerRoles(result), ["writer"]);
    assert.equal(
      offerRoles(result).some((role) =>
        ["evidence", "shape", "teaching", "craft"].includes(role),
      ),
      false,
    );
    const context = result.snapshot.context as unknown as ArticleMachineContext;
    assert.equal(context.iteration, 2);
    assert.equal(context.history[0]?.checks.evidence.status, "skipped");
    assert.equal(context.history[0]?.checks.shape.status, "skipped");
    assert.equal(context.history[0]?.checks.teaching.status, "skipped");
    assert.equal(context.history[0]?.checks.craft.status, "skipped");
    assert.deepEqual(context.carriedFindingArtifacts, [artifactId("measurement-finding")]);
  });

  test("keeps an explicitly non-applicable teaching lens out of the work queue", () => {
    const base = articleSpec();
    const spec = articleSpec({
      policy: { ...base.policy, teaching: "not_applicable" },
    });
    let result = articleInitial(articleInput(spec));
    result = articleTransition(result.snapshot, { type: "START" });
    result = completeArticleWork(result, "measure_article", {
      fits: true,
      openerFits: true,
      pageCount: 4,
    });
    result = completeArticleWork(result, "worth", { decision: "pass" });
    result = completeArticleWork(result, "mechanics", { decision: "pass" });
    result = completeArticleWork(result, "evidence", { decision: "pass" });
    result = completeArticleWork(result, "shape", { decision: "pass" });

    assert.equal(result.snapshot.value, "stage_3");
    assert.deepEqual(offerRoles(result), ["craft"]);
    const context = result.snapshot.context as unknown as ArticleMachineContext;
    assert.equal(context.checks.teaching.status, "not_applicable");

    result = completeArticleWork(result, "craft", { decision: "pass" });
    assert.equal(result.snapshot.value, "settled");
  });

  test("an evidence-only policy skips empty judge stages and settles", () => {
    const base = articleSpec();
    const spec = articleSpec({
      policy: {
        ...base.policy,
        teaching: "not_applicable",
        enabledLenses: ["evidence"],
        blockingLenses: ["evidence"],
      },
      judgePrompts: { evidence: artifactId("evidence-prompt") },
    });
    let result = articleInitial(articleInput(spec));
    result = articleTransition(result.snapshot, { type: "START" });
    assert.deepEqual(offerRoles(result), ["measure_article"]);
    result = completeArticleWork(result, "measure_article", {
      fits: true,
      openerFits: true,
      pageCount: 4,
    });
    assert.equal(result.snapshot.value, "stage_2");
    assert.deepEqual(offerRoles(result), ["evidence"]);
    result = completeArticleWork(result, "evidence", { decision: "pass" });
    assert.equal(result.snapshot.value, "settled");
    assert.equal(effectsOfType(result, "complete_actor").length, 1);
  });

  test("writer work carries immutable policy artifacts in its ordered input lineage", () => {
    const base = articleSpec();
    const { initialManuscript: _initialManuscript, ...withoutManuscript } = base;
    const spec: ArticleRunSpec = {
      ...withoutManuscript,
      contentModeArtifact: artifactId("content-mode-policy"),
      attributionArtifact: artifactId("attribution-policy"),
      editorialPolicyArtifact: artifactId("editorial-policy"),
      modelPolicyArtifact: artifactId("model-policy"),
    };
    let result = articleInitial(articleInput(spec));
    result = articleTransition(result.snapshot, { type: "START" });
    const writer = effectsOfType(result, "create_work_offer")[0];
    assert.ok(writer);
    assert.deepEqual(
      writer.inputArtifacts.slice(0, 5),
      [
        spec.writerPrompt,
        spec.contentModeArtifact,
        spec.attributionArtifact,
        spec.editorialPolicyArtifact,
        spec.modelPolicyArtifact,
      ],
    );
  });

  test("binds every offer and decision to stable iteration and revision identities", () => {
    let result = articleInitial(articleInput());
    result = articleTransition(result.snapshot, { type: "START" });
    for (const offer of effectsOfType(result, "create_work_offer")) {
      assert.equal(offer.iterationId, "iteration_actor-article_1");
      assert.equal(offer.iterationOrdinal, 1);
      assert.equal(offer.revisionId, "revision_actor-article_1");
    }

    result = completeArticleWork(result, "worth", { decision: "pass" });
    result = completeArticleWork(result, "mechanics", {
      decision: "changes_required",
      findings: ["agreement"],
    }, [{ artifactId: artifactId("mechanics-finding"), kind: "mechanics_review" }]);
    result = completeArticleWork(result, "measure_article", {
      fits: true,
      openerFits: true,
      pageCount: 4,
    });

    assert.equal(result.snapshot.value, "drafting");
    const decision = effectsOfType(result, "record_decision")[0];
    assert.equal(decision?.iterationId, "iteration_actor-article_1");
    const writer = effectsOfType(result, "create_work_offer")[0];
    assert.equal(writer?.role, "writer");
    assert.equal(writer?.iterationId, "iteration_actor-article_2");
    assert.equal(writer?.iterationOrdinal, 2);
    assert.equal(writer?.revisionId, "revision_actor-article_2");
    assert.equal(writer?.parentManuscriptArtifactId, artifactId("manuscript-v1"));
    assert.equal(writer?.inputArtifacts.includes(artifactId("mechanics-finding")), true);

    result = completeArticleWork(
      result,
      "writer",
      {},
      [{ artifactId: artifactId("manuscript-v2"), kind: "article_manuscript" }],
    );
    assert.equal(result.snapshot.value, "stage_1");
    for (const offer of effectsOfType(result, "create_work_offer")) {
      assert.equal(offer.iterationId, "iteration_actor-article_2");
      assert.equal(offer.iterationOrdinal, 2);
      assert.equal(offer.revisionId, "revision_actor-article_2");
      assert.equal(offer.parentManuscriptArtifactId, artifactId("manuscript-v1"));
    }
  });

  test("closes the durable iteration row before opening the next revision", async () => {
    const temporary = await mkdtemp(join(tmpdir(), "mag-article-iteration-"));
    const base = articleSpec();
    const spec = articleSpec({
      policy: {
        ...base.policy,
        enabledLenses: ["mechanics", "evidence"],
        blockingLenses: ["mechanics"],
      },
    });
    const engine = new SqliteRunEngine({
      databasePath: join(temporary, "run.sqlite"),
      artifactDirectory: join(temporary, "artifacts"),
    });
    try {
      const started = await engine.start(await prepareArticleSources(
        engine,
        articleRootSpec(spec),
        "durable-iteration",
      ));
      let view = await engine.inspect(started.runId);
      const mechanics = view.offers.find(
        (offer) => offer.role === "mechanics" && offer.status === "offered",
      );
      const measurement = view.offers.find(
        (offer) => offer.role === "measure_article" && offer.status === "offered",
      );
      assert.ok(mechanics);
      assert.ok(measurement);

      const mechanicsClaim = await engine.claim(mechanics.id, {
        principalId: "mechanics-model",
        authority: "model",
        capabilities: ["text_model", "source_blind"],
      });
      view = await engine.answer(mechanicsClaim, {
        contractVersion: mechanics.contractVersion,
        result: { decision: "changes_required", findings: ["agreement"] },
        artifacts: [
          {
            kind: "mechanics_review",
            schemaVersion: "mechanics/1",
            mediaType: "application/json",
            payload: { kind: "json", value: { finding: "agreement" } },
          },
        ],
      });
      const measurementClaim = await engine.claim(measurement.id, {
        principalId: "measure-tool",
        authority: "tool",
        capabilities: ["subprocess"],
      });
      view = await engine.answer(measurementClaim, {
        contractVersion: measurement.contractVersion,
        result: { fits: true, openerFits: true, pageCount: 4 },
        artifacts: [{
          kind: "article_measurement",
          schemaVersion: "measure/1",
          mediaType: "application/json",
          payload: { kind: "json", value: { fits: true, pageCount: 4 } },
        }],
      });

      const writer = view.offers.find(
        (offer) => offer.role === "writer" && offer.status === "offered",
      );
      assert.ok(writer);
      const actor = view.actors[0];
      assert.ok(actor);
      assert.equal(writer.iterationId, `iteration_${actor.id}_2`);
      assert.equal(writer.revisionId, `revision_${actor.id}_2`);

      const iterations = view.iterations.filter(
        (iteration) => iteration.actorId === actor.id,
      );
      assert.equal(iterations.length, 2);
      assert.equal(iterations[0]?.ordinal, 1);
      assert.notEqual(iterations[0]?.closedEventId, undefined);
      assert.notEqual(iterations[0]?.decisionId, undefined);
      assert.equal(iterations[1]?.ordinal, 2);
      assert.equal(iterations[1]?.parentManuscriptArtifactId, spec.initialManuscript);
      assert.equal(iterations[1]?.closedEventId, undefined);
      assert.equal(iterations[1]?.decisionId, undefined);
    } finally {
      engine.close();
      await rm(temporary, { recursive: true, force: true });
    }
  });

  test("has the same standalone and nested transition behavior", () => {
    const standalone = settlePassingArticle(articleInput());
    const nested = settlePassingArticle(articleInput(articleSpec(), actorId("edition-parent")));

    assert.equal(standalone.snapshot.value, "settled");
    assert.equal(nested.snapshot.value, "settled");
    assert.deepEqual(nested.effects, standalone.effects);
    const { parentActorId: _nestedParent, ...nestedContext } =
      nested.snapshot.context as unknown as ArticleMachineContext;
    assert.deepEqual(nestedContext, standalone.snapshot.context);
  });
});

function editionReviewInput(): EditionReviewMachineInput {
  const spec: EditionReviewRunSpec = {
    editionId: "edition-one",
    editionBrief: artifactId("edition-brief"),
    articleArtifacts: [
      { articleId: "article-one", artifactId: artifactId("article-one-v1") },
      { articleId: "article-two", artifactId: artifactId("article-two-v1") },
    ],
    editorialArtifact: artifactId("editorial-v1"),
    modelPolicy,
  };
  return {
    actorId: actorId("actor-edition-review"),
    logicalKey: "edition-review:0",
    parentActorId: actorId("actor-edition"),
    spec,
  };
}

describe("EditionReviewMachine orchestration", () => {
  test("routes sibling findings, reopens review, and records explicit human approval", () => {
    let result = editionReviewInitial(editionReviewInput());
    result = editionReviewTransition(result.snapshot, { type: "START" });
    assert.equal(result.snapshot.value, "reviewing");
    assert.deepEqual(offerRoles(result), ["edition_review"]);

    result = editionReviewTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "edition_review",
      artifacts: [
        { artifactId: artifactId("edition-review-v1"), kind: "edition_review" },
      ],
      result: {
        decision: "revise",
        routes: [
          { target: "article-one", findingArtifactId: artifactId("finding-one") },
          { target: "article-two", findingArtifactId: artifactId("finding-two") },
        ],
      },
    });
    assert.equal(result.snapshot.value, "revisions_routed");
    const routed = effectsOfType(result, "complete_actor")[0];
    assert.equal(routed?.accepting, false);
    assert.deepEqual(routed?.outputs, [artifactId("edition-review-v1")]);

    result = editionReviewTransition(result.snapshot, {
      type: "REVISION_REQUESTED",
      findingArtifacts: [artifactId("finding-one"), artifactId("finding-two")],
      reason: "siblings revised",
    });
    assert.equal(result.snapshot.value, "reviewing");
    assert.deepEqual(offerRoles(result), ["edition_review"]);
    assert.equal(
      (result.snapshot.context as unknown as EditionReviewMachineContext).revision,
      1,
    );

    result = editionReviewTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "edition_review",
      artifacts: [
        { artifactId: artifactId("edition-review-v2"), kind: "edition_review" },
      ],
      result: { decision: "editor_decision" },
    });
    assert.equal(result.snapshot.value, "awaiting_editor");
    assert.deepEqual(offerRoles(result), ["editor_decision"]);
    const reviewRequest = effectsOfType(result, "register_artifact").find(
      (candidate) => candidate.artifact.kind === "human_decision_request",
    );
    const reviewOffer = effectsOfType(result, "create_work_offer")[0];
    assert.ok(reviewRequest);
    assert.equal(reviewOffer?.taskArtifactId, reviewRequest.artifact.id);

    result = editionReviewTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "editor_decision",
      artifacts: [],
      result: { decision: "approve" },
    });
    assert.equal(result.snapshot.value, "approved");
    const approval = effectsOfType(result, "complete_actor")[0];
    assert.equal(approval?.accepting, true);
    assert.deepEqual(approval?.outputs, [artifactId("edition-review-v2")]);
    assert.equal(effectsOfType(result, "record_decision")[0]?.authority, "human");
  });
});

function editionSpec(overrides: Partial<EditionRunSpec> = {}): EditionRunSpec {
  const articleOne = articleSpec({
    articleId: "article-one",
    initialManuscript: artifactId("article-one-v1"),
  });
  const articleTwo = articleSpec({
    articleId: "article-two",
    initialManuscript: artifactId("article-two-v1"),
  });
  return {
    editionId: "edition-one",
    editionBrief: artifactId("edition-brief"),
    planningArtifact: artifactId("edition-plan"),
    sources: [],
    articles: [articleOne, articleTwo],
    editorial: {
      editorialId: "opening",
      briefArtifact: artifactId("editorial-brief"),
      writingRules: artifactId("writing-rules"),
      initialManuscript: artifactId("editorial-v1"),
      modelPolicy,
    },
    translations: [
      {
        language: "es",
        sourceLanguage: "en",
        englishArtifacts: [],
        promptArtifact: artifactId("translation-es-prompt"),
        maximumReaderPages: 7,
        modelPolicy,
      },
      {
        language: "fr",
        sourceLanguage: "en",
        englishArtifacts: [],
        promptArtifact: artifactId("translation-fr-prompt"),
        maximumReaderPages: 7,
        modelPolicy,
      },
    ],
    art: [
      {
        key: "cover",
        role: "cover",
        artifactId: artifactId("cover-v1"),
        briefArtifact: artifactId("cover-brief"),
        required: true,
      },
      {
        key: "inside",
        role: "interior",
        artifactId: artifactId("inside-v1"),
        briefArtifact: artifactId("inside-brief"),
        required: true,
      },
    ],
    render: {
      renderManifestArtifact: artifactId("render-profile"),
      rendererContractVersion: "renderer-test/1",
      printerProfileArtifact: artifactId("printer-profile"),
      configuredLanguages: ["en", "es", "fr"],
      studioPolicy: "home_ready_studio_blocked",
    },
    release: {
      publicationArtifact: artifactId("publication-placeholder"),
      sourceArtifacts: [],
      dryRun: false,
      target: "private",
    },
    modelPolicy,
    ...overrides,
  };
}

function editionInput(spec: EditionRunSpec = editionSpec()): EditionMachineInput {
  return {
    actorId: actorId("actor-edition"),
    logicalKey: "edition:edition-one",
    spec,
  };
}

function editionRootSpec(spec: EditionRunSpec): EditionRootRunSpec {
  const sourceSeeds = new Map<ArtifactId, ArtifactSeed>();
  for (const source of spec.sources) {
    sourceSeeds.set(source.leadArtifact, textSeed(source.leadArtifact, "submitted_lead"));
    if (source.rawBundleArtifact !== undefined) {
      sourceSeeds.set(source.rawBundleArtifact, textSeed(source.rawBundleArtifact, "raw_source_bundle", [
        { artifactId: source.leadArtifact, relation: "captured_from_lead" },
      ]));
    }
    for (const evidence of source.rawEvidenceArtifacts ?? []) {
      sourceSeeds.set(evidence, textSeed(evidence, "raw_evidence", [
        { artifactId: source.rawBundleArtifact ?? source.leadArtifact, relation: "bundle_content" },
      ]));
    }
    if (source.extractionArtifact !== undefined && source.rawBundleArtifact !== undefined) {
      sourceSeeds.set(source.extractionArtifact, textSeed(source.extractionArtifact, "source_extraction", [
        { artifactId: source.rawBundleArtifact, relation: "extracted_from" },
      ]));
    }
    if (source.metadataArtifact !== undefined && source.rawBundleArtifact !== undefined) {
      sourceSeeds.set(source.metadataArtifact, textSeed(source.metadataArtifact, "source_metadata", [
        { artifactId: source.rawBundleArtifact, relation: "describes_bundle" },
      ]));
    }
    if (
      source.approvalArtifact !== undefined &&
      source.rawBundleArtifact !== undefined &&
      source.extractionArtifact !== undefined
    ) {
      sourceSeeds.set(source.approvalArtifact, textSeed(source.approvalArtifact, "source_review_decision", [
        { artifactId: source.rawBundleArtifact, relation: "reviewed_raw_bundle" },
        { artifactId: source.extractionArtifact, relation: "reviewed_extraction" },
      ], "human"));
    }
  }
  const references: ArtifactId[] = [
    spec.editionBrief,
    ...(spec.planningArtifact === undefined ? [] : [spec.planningArtifact]),
    ...spec.sources.flatMap((source) => [
      source.leadArtifact,
      ...(source.rawBundleArtifact === undefined ? [] : [source.rawBundleArtifact]),
      ...(source.rawEvidenceArtifacts ?? []),
      ...(source.extractionArtifact === undefined ? [] : [source.extractionArtifact]),
      ...(source.metadataArtifact === undefined ? [] : [source.metadataArtifact]),
      ...(source.approvalArtifact === undefined ? [] : [source.approvalArtifact]),
    ]),
    ...spec.articles.flatMap((article) => articleRootSpec(article).artifacts.map((seed) => seed.id)),
    spec.editorial.briefArtifact,
    spec.editorial.writingRules,
    ...(spec.editorial.initialManuscript === undefined
      ? []
      : [spec.editorial.initialManuscript]),
    ...spec.translations.flatMap((translation) => [
      ...translation.englishArtifacts,
      translation.promptArtifact,
      ...(translation.initialTranslationArtifacts ?? []),
    ]),
    ...spec.art.flatMap((art) => [
      art.briefArtifact,
      ...(art.artifactId === undefined ? [] : [art.artifactId]),
    ]),
    spec.render.renderManifestArtifact,
    ...(spec.render.printerProfileArtifact === undefined
      ? []
      : [spec.render.printerProfileArtifact]),
    spec.release.publicationArtifact,
    ...spec.release.sourceArtifacts,
  ];
  return {
    schemaVersion: 1,
    kind: "edition",
    edition: spec,
    artifacts: [...new Set(references)].map((artifactId) =>
      sourceSeeds.get(artifactId) ?? textSeed(artifactId)
    ),
  };
}

function childSpawned(
  result: MachineTransitionResult,
  childKey: string,
  machine: SpawnActorEffect["machine"],
): MachineTransitionResult {
  return editionTransition(result.snapshot, {
    type: "CHILD_SPAWNED",
    childActorId: actorId(`actor-${childKey}`),
    childKey,
    machine,
  });
}

function childStatus(
  result: MachineTransitionResult,
  childKey: string,
  status: "accepting" | "active" | "done" | "failed",
  outputs: readonly ArtifactId[],
  childResult: JsonObject,
): MachineTransitionResult {
  return editionTransition(result.snapshot, {
    type: "CHILD_STATUS",
    childActorId: actorId(`actor-${childKey}`),
    childKey,
    status,
    outputs,
    result: childResult,
  });
}

function beginPreplannedEdition(spec: EditionRunSpec = editionSpec()): MachineTransitionResult {
  let result = editionInitial(editionInput(spec));
  result = editionTransition(result.snapshot, { type: "START" });
  return result;
}

function closeCollection(result: MachineTransitionResult): MachineTransitionResult {
  const snapshotContext = result.snapshot.context as {
    readonly actorId: ActorId;
    readonly closeRequestOrdinal: number;
  };
  return editionTransition(result.snapshot, {
    type: "WORK_COMPLETED",
    slot: "close_collection",
    taskArtifactId:
      `art_${snapshotContext.actorId}_collection_close_request_${snapshotContext.closeRequestOrdinal}` as ArtifactId,
    artifacts: [{
      kind: "collection_decision",
      artifactId: artifactId("collection-close-decision"),
    }],
    result: { choice: "close" },
  });
}

function driveToFirstEditionReview(spec: EditionRunSpec = editionSpec()): MachineTransitionResult {
  let result = beginPreplannedEdition(spec);
  result = closeCollection(result);
  result = childSpawned(result, "article:article-one", "article");
  result = childSpawned(result, "article:article-two", "article");
  result = childSpawned(result, "art:cover", "cover_art");
  result = childSpawned(result, "art:inside", "interior_art");
  result = childStatus(
    result,
    "art:cover",
    "accepting",
    [artifactId("cover-v1")],
    { status: "selected" },
  );
  result = childStatus(
    result,
    "art:inside",
    "accepting",
    [artifactId("inside-v1")],
    { status: "selected" },
  );
  result = childStatus(
    result,
    "article:article-one",
    "accepting",
    [artifactId("article-one-v1")],
    { status: "settled" },
  );
  result = childStatus(
    result,
    "article:article-two",
    "accepting",
    [artifactId("article-two-v1")],
    { status: "settled" },
  );
  assert.equal(result.snapshot.value, "producing_editorial");
  assert.deepEqual(
    effectsOfType(result, "spawn_actor").map((effect) => effect.logicalKey),
    ["editorial"],
  );
  result = childSpawned(result, "editorial", "editorial");
  result = childStatus(
    result,
    "editorial",
    "accepting",
    [artifactId("editorial-v1")],
    { status: "settled" },
  );
  assert.equal(result.snapshot.value, "edition_review");
  return result;
}

describe("EditionMachine orchestration", () => {
  test("requires an explicit collection close before spawning preplanned content", () => {
    let result = beginPreplannedEdition();
    assert.equal(result.snapshot.value, "collecting");
    assert.deepEqual(offerRoles(result), ["close_collection"]);
    assert.deepEqual(effectsOfType(result, "spawn_actor"), []);
    const closeRequest = effectsOfType(result, "register_artifact")[0];
    const closeOffer = effectsOfType(result, "create_work_offer")[0];
    assert.equal(closeRequest?.artifact.kind, "human_decision_request");
    assert.equal(closeOffer?.taskArtifactId, closeRequest?.artifact.id);

    result = closeCollection(result);
    assert.equal(result.snapshot.value, "producing_articles");
    const spawned = effectsOfType(result, "spawn_actor");
    assert.deepEqual(
      spawned.map((effect) => [effect.machine, effect.logicalKey]),
      [
        ["article", "article:article-one"],
        ["article", "article:article-two"],
        ["cover_art", "art:cover"],
        ["interior_art", "art:inside"],
      ],
    );
    const decision = effectsOfType(result, "record_decision")[0];
    assert.equal(decision?.choice, "close_collection");
    assert.equal(decision?.artifactId, artifactId("collection-close-decision"));
  });

  test("settles a sibling revision before reopening editorial with current articles", () => {
    let result = driveToFirstEditionReview();
    const firstReview = effectsOfType(result, "spawn_actor")[0];
    assert.equal(firstReview?.logicalKey, "edition-review:0");
    result = childSpawned(result, "edition-review:0", "edition_review");

    result = childStatus(
      result,
      "edition-review:0",
      "done",
      [artifactId("edition-review-v1")],
      {
        status: "revisions_routed",
        routes: [
          {
            target: "article-one",
            findingArtifactId: artifactId("edition-finding-one"),
          },
        ],
      },
    );
    assert.equal(result.snapshot.value, "revising_content");
    const routed = effectsOfType(result, "send_actor_event");
    assert.deepEqual(
      routed.map((effect) =>
        "childKey" in effect.target ? effect.target.childKey : effect.target.actorId,
      ),
      ["article:article-one"],
    );
    assert.deepEqual(routed[0]?.event.findingArtifacts, [artifactId("edition-finding-one")]);
    const routedContext = result.snapshot.context as unknown as EditionMachineContext;
    assert.equal(routedContext.children["article:article-one"]?.status, "active");
    assert.equal(routedContext.children["article:article-two"]?.status, "accepting");
    assert.equal(routedContext.children.editorial?.status, "active");
    assert.equal(routedContext.reviewCycle, 1);

    result = childStatus(
      result,
      "article:article-one",
      "accepting",
      [artifactId("article-one-v2")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "producing_editorial");
    assert.deepEqual(effectsOfType(result, "spawn_actor"), []);
    const editorialRevision = effectsOfType(result, "send_actor_event");
    assert.equal(editorialRevision.length, 1);
    assert.deepEqual(editorialRevision[0]?.event.findingArtifacts, [
      artifactId("edition-finding-one"),
    ]);
    assert.deepEqual(editorialRevision[0]?.event.articleArtifacts, [
      artifactId("article-one-v2"),
      artifactId("article-two-v1"),
    ]);

    result = childStatus(
      result,
      "editorial",
      "accepting",
      [artifactId("editorial-v2")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "edition_review");
    const nextReview = effectsOfType(result, "spawn_actor")[0];
    assert.equal(nextReview?.logicalKey, "edition-review:1");
    const nextReviewSpec = nextReview?.spec as EditionReviewRunSpec;
    assert.deepEqual(nextReviewSpec.articleArtifacts, [
      { articleId: "article-one", artifactId: artifactId("article-one-v2") },
      { articleId: "article-two", artifactId: artifactId("article-two-v1") },
    ]);
    assert.equal(nextReviewSpec.editorialArtifact, artifactId("editorial-v2"));
  });

  test("passes only the current English artifact IDs into each translation cycle", () => {
    let result = driveToFirstEditionReview();
    result = childSpawned(result, "edition-review:0", "edition_review");
    result = childStatus(
      result,
      "edition-review:0",
      "done",
      [artifactId("edition-review-v1")],
      {
        status: "revisions_routed",
        routes: [
          {
            target: "article-one",
            findingArtifactId: artifactId("edition-finding-one"),
          },
        ],
      },
    );
    result = childStatus(
      result,
      "article:article-one",
      "accepting",
      [artifactId("article-one-v2")],
      { status: "settled" },
    );
    result = childStatus(
      result,
      "editorial",
      "accepting",
      [artifactId("editorial-v2")],
      { status: "settled" },
    );
    result = childSpawned(result, "edition-review:1", "edition_review");
    result = childStatus(
      result,
      "edition-review:1",
      "accepting",
      [artifactId("edition-review-v2")],
      { status: "approved" },
    );

    assert.equal(result.snapshot.value, "translating");
    const translations = effectsOfType(result, "spawn_actor");
    assert.deepEqual(
      translations.map((effect) => effect.logicalKey),
      ["translation:es:1", "translation:fr:1"],
    );
    const expected = [
      artifactId("article-one-v2"),
      artifactId("article-two-v1"),
      artifactId("editorial-v2"),
    ];
    for (const translation of translations) {
      assert.deepEqual(
        (translation.spec as EditionRunSpec["translations"][number]).englishArtifacts,
        expected,
      );
    }
  });

  test("waits for every language and carries the selected art join into rendering", () => {
    let result = driveToFirstEditionReview();
    result = childSpawned(result, "edition-review:0", "edition_review");
    result = childStatus(
      result,
      "edition-review:0",
      "accepting",
      [artifactId("edition-review-v1")],
      { status: "approved" },
    );
    assert.equal(result.snapshot.value, "translating");
    result = childSpawned(result, "translation:es:0", "translation");
    result = childSpawned(result, "translation:fr:0", "translation");

    result = childStatus(
      result,
      "translation:es:0",
      "accepting",
      [artifactId("translation-es-v1")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "translating");
    assert.deepEqual(effectsOfType(result, "register_artifact"), []);
    assert.deepEqual(effectsOfType(result, "spawn_actor"), []);

    result = childStatus(
      result,
      "translation:fr:0",
      "accepting",
      [artifactId("translation-fr-v1")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "rendering");
    const manifestEffect = effectsOfType(result, "register_artifact")[0];
    assert.equal(manifestEffect?.slot, "render_manifest");
    assert.equal(manifestEffect?.artifact.kind, "render_manifest");
    assert.equal(manifestEffect?.artifact.payload.kind, "json");
    if (manifestEffect?.artifact.payload.kind !== "json") {
      assert.fail("render manifest was not a JSON artifact");
    }
    const manifest = manifestEffect.artifact.payload.value as JsonObject;
    assert.deepEqual(manifest.translations, [
      artifactId("translation-es-v1"),
      artifactId("translation-fr-v1"),
    ]);
    assert.deepEqual(manifest.art, [artifactId("cover-v1"), artifactId("inside-v1")]);
    assert.deepEqual(
      manifestEffect.artifact.parents
        ?.filter((parent) => parent.relation === "selected_art")
        .map((parent) => parent.artifactId),
      [artifactId("cover-v1"), artifactId("inside-v1")],
    );
    const render = effectsOfType(result, "spawn_actor")[0];
    assert.equal(render?.machine, "render");
    assert.equal(render?.logicalKey, "render:0");
  });

  test("does not open edition review until every required art child is ready", () => {
    let result = beginPreplannedEdition();
    result = closeCollection(result);
    result = childSpawned(result, "article:article-one", "article");
    result = childSpawned(result, "article:article-two", "article");
    result = childSpawned(result, "art:cover", "cover_art");
    result = childSpawned(result, "art:inside", "interior_art");
    result = childStatus(
      result,
      "article:article-one",
      "accepting",
      [artifactId("article-one-v1")],
      { status: "settled" },
    );
    result = childStatus(
      result,
      "article:article-two",
      "accepting",
      [artifactId("article-two-v1")],
      { status: "settled" },
    );
    result = childSpawned(result, "editorial", "editorial");
    result = childStatus(
      result,
      "editorial",
      "accepting",
      [artifactId("editorial-v1")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "producing_editorial");
    assert.deepEqual(effectsOfType(result, "spawn_actor"), []);

    result = childStatus(
      result,
      "art:cover",
      "accepting",
      [artifactId("cover-v1")],
      { status: "selected" },
    );
    assert.equal(result.snapshot.value, "producing_editorial");
    result = childStatus(
      result,
      "art:inside",
      "accepting",
      [artifactId("inside-v1")],
      { status: "selected" },
    );
    assert.equal(result.snapshot.value, "edition_review");
    assert.equal(effectsOfType(result, "spawn_actor")[0]?.machine, "edition_review");
  });

  test("leaves an escalated child in control of its own durable editor offer", () => {
    let result = beginPreplannedEdition();
    result = closeCollection(result);
    result = childSpawned(result, "article:article-one", "article");
    result = childSpawned(result, "article:article-two", "article");
    result = childSpawned(result, "art:cover", "cover_art");
    result = childSpawned(result, "art:inside", "interior_art");
    result = childStatus(
      result,
      "article:article-one",
      "done",
      [artifactId("article-one-escalated")],
      { status: "escalated" },
    );
    assert.equal(result.snapshot.value, "producing_articles");
    assert.deepEqual(offerRoles(result), []);

    result = childStatus(
      result,
      "article:article-one",
      "accepting",
      [artifactId("article-one-recovered")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "producing_articles");
    result = childStatus(
      result,
      "article:article-two",
      "accepting",
      [artifactId("article-two-v1")],
      { status: "settled" },
    );
    assert.equal(result.snapshot.value, "producing_editorial");
  });

  test("binds an edition-level drop ruling to an immutable editor request", () => {
    let result = beginPreplannedEdition();
    result = closeCollection(result);
    result = childSpawned(result, "article:article-one", "article");
    result = childStatus(
      result,
      "article:article-one",
      "done",
      [],
      { status: "dropped" },
    );
    assert.equal(result.snapshot.value, "awaiting_editor");
    const request = effectsOfType(result, "register_artifact")[0];
    const offer = effectsOfType(result, "create_work_offer")[0];
    assert.equal(request?.artifact.kind, "human_decision_request");
    assert.equal(offer?.taskArtifactId, request?.artifact.id);
  });

  test("offers equivalent article work in standalone and nested durable runs", async () => {
    const temporary = await mkdtemp(join(tmpdir(), "mag-nested-equivalence-"));
    const articleBase = articleSpec();
    const nestedArticle = articleSpec({
      policy: {
        ...articleBase.policy,
        enabledLenses: ["mechanics", "evidence"],
        blockingLenses: ["mechanics"],
      },
    });
    const edition = editionSpec({
      sources: [{
        sourceId: "source-one",
        leadArtifact: artifactId("source-one-lead"),
        rawBundleArtifact: artifactId("source-one-raw-bundle"),
        rawEvidenceArtifacts: [artifactId("source-one-raw-evidence")],
        extractionArtifact: artifactId("source-one"),
        metadataArtifact: artifactId("source-one-metadata"),
      }],
      articles: [nestedArticle],
      translations: [],
      art: [],
      render: {
        ...editionSpec().render,
        configuredLanguages: ["en"],
      },
    });
    const standalone = new SqliteRunEngine({
      databasePath: join(temporary, "standalone.sqlite"),
      artifactDirectory: join(temporary, "standalone-artifacts"),
    });
    const nested = new SqliteRunEngine({
      databasePath: join(temporary, "nested.sqlite"),
      artifactDirectory: join(temporary, "nested-artifacts"),
    });
    try {
      const standaloneRun = await standalone.start(await prepareArticleSources(
        standalone,
        articleRootSpec(nestedArticle),
        "nested-equivalence",
      ));
      const standaloneView = await standalone.inspect(standaloneRun.runId);

      const nestedRun = await nested.start(editionRootSpec(edition));
      let nestedView = await nested.inspect(nestedRun.runId);
      const close = nestedView.offers.find(
        (offer) => offer.role === "close_collection" && offer.status === "offered",
      );
      assert.ok(close);
      const closeClaim = await nested.claim(close.id, {
        principalId: "managing-editor",
        authority: "human",
        capabilities: ["human"],
      });
      nestedView = await nested.answer(closeClaim, {
        contractVersion: close.contractVersion,
        result: { choice: "close" },
        artifacts: [{
          kind: "collection_decision",
          schemaVersion: "1",
          mediaType: "application/json",
          payload: { kind: "json", value: { choice: "close" } },
        }],
      });

      const sourceReview = nestedView.offers.find(
        (offer) => offer.role === "review_source" && offer.status === "offered",
      );
      assert.ok(sourceReview);
      const sourceReviewClaim = await nested.claim(sourceReview.id, {
        principalId: "source-editor",
        authority: "human",
        capabilities: ["human", "source_access"],
      });
      nestedView = await nested.answer(sourceReviewClaim, {
        contractVersion: sourceReview.contractVersion,
        result: { decision: "approved" },
        artifacts: [{
          id: artifactId("nested-equivalence-0-source-review"),
          kind: "source_review_decision",
          schemaVersion: "review-source/1",
          mediaType: "application/json",
          payload: { kind: "json", value: { decision: "approved" } },
        }],
      });

      const nestedActor = nestedView.actors.find(
        (actor) => actor.logicalKey === "article:article-one",
      );
      const standaloneActor = standaloneView.actors.find(
        (actor) => actor.parentActorId === undefined,
      );
      assert.ok(nestedActor);
      assert.ok(standaloneActor);
      const nestedOffers = nestedView.offers.filter(
        (offer) => offer.actorId === nestedActor.id && offer.status === "offered",
      );
      const standaloneOffers = standaloneView.offers.filter(
        (offer) => offer.actorId === standaloneActor.id && offer.status === "offered",
      );
      const normalized = (offers: typeof nestedOffers) =>
        offers
          .map((offer) => ({
            role: offer.role,
            slot: offer.slot,
            state: offer.state,
            taskArtifactId: offer.taskArtifactId,
            inputArtifacts: offer.inputArtifacts,
            contractVersion: offer.contractVersion,
            capabilities: offer.allowedWorkerCapabilities,
          }))
          .sort((left, right) => left.role.localeCompare(right.role));
      assert.deepEqual(normalized(nestedOffers), normalized(standaloneOffers));
      for (const offer of nestedOffers) {
        assert.equal(offer.iterationId, `iteration_${nestedActor.id}_1`);
        assert.equal(offer.revisionId, `revision_${nestedActor.id}_1`);
      }
      for (const offer of standaloneOffers) {
        assert.equal(offer.iterationId, `iteration_${standaloneActor.id}_1`);
        assert.equal(offer.revisionId, `revision_${standaloneActor.id}_1`);
      }

      const replay = async (
        engine: SqliteRunEngine,
        runId: RunId,
        actorId: ActorId,
      ): Promise<RunView> => {
        for (let step = 0; step < 8; step += 1) {
          const view = await engine.inspect(runId);
          const actor = view.actors.find((candidate) => candidate.id === actorId);
          assert.ok(actor);
          if (actor.state === "settled") {
            return view;
          }
          const offer = view.offers.find(
            (candidate) => candidate.actorId === actorId && candidate.status === "offered",
          );
          assert.ok(offer, `article ${actorId} stranded in ${actor.state}`);
          const claim = await engine.claim(offer.id, {
            principalId: `replay-${offer.role}`,
            authority: offer.allowedWorkerCapabilities.includes("text_model") ? "model" : "tool",
            capabilities: offer.allowedWorkerCapabilities,
          });
          await engine.answer(claim, {
            contractVersion: offer.contractVersion,
            result: offer.role === "measure_article"
              ? { fits: true, openerFits: true, pageCount: 1 }
              : { decision: "pass" },
            artifacts: offer.role === "measure_article"
              ? [{
                  id: artifactId("equivalent-measurement"),
                  kind: "article_measurement",
                  schemaVersion: "test/1",
                  mediaType: "application/json",
                  payload: { kind: "json", value: { fits: true, pageCount: 1 } },
                }]
              : [],
          });
        }
        assert.fail(`article ${actorId} did not settle within replay budget`);
      };
      const [settledStandalone, settledNested] = await Promise.all([
        replay(standalone, standaloneRun.runId, standaloneActor.id),
        replay(nested, nestedRun.runId, nestedActor.id),
      ]);
      const graph = (view: RunView, actorId: ActorId) =>
        view.artifacts
          .filter((artifact) => artifact.producingActorId === actorId)
          .map((artifact) => ({
            kind: artifact.kind,
            schemaVersion: artifact.schemaVersion,
            parents: artifact.parents.map((parent) => ({
              ...parent,
              artifactId: parent.artifactId.includes("source-review")
                ? artifactId("equivalent-source-review")
                : parent.artifactId,
            })),
          }))
          .sort((left, right) => left.kind.localeCompare(right.kind));
      assert.deepEqual(graph(settledNested, nestedActor.id), graph(settledStandalone, standaloneActor.id));
      assert.deepEqual(
        settledNested.actors.find((actor) => actor.id === nestedActor.id)?.outputs,
        settledStandalone.actors.find((actor) => actor.id === standaloneActor.id)?.outputs,
      );
    } finally {
      standalone.close();
      nested.close();
      await rm(temporary, { recursive: true, force: true });
    }
  });
});
