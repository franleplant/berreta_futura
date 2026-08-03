import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
  JsonObject,
  WorkOfferView,
} from "../contracts/index.ts";
import { LocalAuthorityStore } from "../authority/local-authority.ts";
import { CooperativeModelBridge } from "../cooperative-model-bridge.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";
import {
  executeAvailableWork,
  RenderInspectionExecutor,
  RendererExecutor,
} from "../executors/index.ts";
import {
  InMemoryRendererAdapter,
  RENDERER_CONTRACT_VERSION,
  type RenderManifest,
} from "../renderer-adapter/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { prepareWriteProduction } from "../write-production.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

const id = (value: string) => value as ArtifactId;
const model = { default: { adapter: "cooperative", model: "fake-terra", reasoningEffort: "high" } };
const authorities = new WeakMap<SqliteRunEngine, AuthorityTestHarness>();

test("fresh write pipeline run reaches the visual-review gate with registered selected art", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-write-e2e-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  const authorityFixture = await AuthorityTestHarness.create(temporary);
  authorities.set(engine, authorityFixture);
  try {
    const plan = await prepareWriteProduction(process.cwd(), {
      kind: "write_pipeline",
      editionId: "004",
      logicalId: "edition4-write",
      revisionId: "rev_20260803T144015852Z_jddwkt2gxrf6" as never,
    }, { assertCommitted: async () => {} });
    const seededApproval = id("seeded-source-review-decision");
    const contaminatedSource = plan.spec.edition.sources[0];
    assert.ok(contaminatedSource?.rawBundleArtifact);
    assert.ok(contaminatedSource?.extractionArtifact);
    const runSpec: EditionRootRunSpec = {
      ...plan.spec,
      artifacts: [
        ...plan.spec.artifacts,
        {
          id: seededApproval,
          kind: "source_review_decision",
          schemaVersion: "review-source/1",
          mediaType: "application/json",
          origin: "human",
          payload: { kind: "json", value: { decision: "approved" } },
          parents: [
            { artifactId: contaminatedSource.rawBundleArtifact, relation: "reviewed_raw_bundle" },
            { artifactId: contaminatedSource.extractionArtifact, relation: "reviewed_extraction" },
          ],
        } satisfies ArtifactSeed,
      ],
      edition: {
        ...plan.spec.edition,
        sources: plan.spec.edition.sources.map((source) =>
          source.sourceId === contaminatedSource.sourceId
            ? { ...source, approvalArtifact: seededApproval }
            : source),
      },
    };
    assert.equal(runSpec.edition.articles[0]?.initialManuscript, undefined);
    assert.equal(runSpec.edition.editorial.initialManuscript, undefined);
    assert.ok(runSpec.edition.translations.every((translation) => translation.initialTranslationArtifacts === undefined));
    const selectedArtIds = runSpec.edition.render.selectedArtArtifacts ?? [];
    const selectedArtRevisions = runSpec.edition.render.selectedArtRevisions ?? [];
    assert.equal(runSpec.edition.articles.length, 7);
    assert.equal(runSpec.edition.translations.length, 8);
    assert.equal(selectedArtRevisions.length, 13);
    assert.ok(runSpec.edition.articles.every((article) =>
      "sourceIds" in article && !("sourceApprovalArtifacts" in article)
    ));
    assert.equal(
      runSpec.artifacts.some((artifact) => artifact.id.startsWith("prepared-source-approval:")),
      false,
    );
    const started = await engine.start(runSpec);
    const initialView = await engine.inspect(started.runId);
    const sourceReviews = initialView.offers.filter((offer) =>
      offer.role === "review_source" && offer.status === "offered"
    );
    assert.equal(sourceReviews.length, 9);
    assert.equal(sourceReviews.length, plan.pipeline.document.sources.length);
    assert.ok(sourceReviews.every((offer) => !offer.inputArtifacts.includes(seededApproval)));
    const earlyClose = initialView.offers.find((offer) => offer.role === "close_collection");
    assert.ok(earlyClose);
    assert.equal(earlyClose.inputArtifacts.includes(seededApproval), false);
    const earlyCloseRequest = (await engine.readArtifact(earlyClose.taskArtifactId)).artifact;
    assert.equal(
      earlyCloseRequest.parents.some((parent) => parent.artifactId === seededApproval),
      false,
    );
    await answer(engine, earlyClose, response(earlyClose, { choice: "close" }, "collection_decision"));
    const closedBeforeReviews = await engine.inspect(started.runId);
    assert.equal(closedBeforeReviews.offers.some((offer) => offer.role === "plan_edition"), false);
    assert.equal(
      closedBeforeReviews.actors.find((actor) => actor.parentActorId === undefined)?.state,
      "collection_closed",
    );
    for (const offer of sourceReviews) {
      assert.deepEqual(offer.allowedWorkerCapabilities, ["source_access"]);
      assert.equal(offer.requirements?.authority, "human");
      const sourceId = offer.actorKey.replace(/^source:/u, "");
      const source = runSpec.edition.sources.find((candidate) => candidate.sourceId === sourceId);
      assert.ok(source?.rawBundleArtifact);
      assert.ok(source?.extractionArtifact);
      assert.ok(offer.inputArtifacts.includes(source.rawBundleArtifact));
      assert.ok(offer.inputArtifacts.includes(source.extractionArtifact));
      await assert.rejects(
        async () => await (await authorityFixture.workerFor(offer, {
          principalId: `fake-agent-${sourceId}`,
          authority: "model",
          capabilities: ["source_access"],
        })).claim(engine, offer.id),
        /requires human authority/u,
      );
    }
    for (const offer of sourceReviews) {
      const sourceId = offer.actorKey.replace(/^source:/u, "");
      const reviewer = await authorityFixture.workerFor(offer, {
        principalId: `human-source-reviewer-${sourceId}`,
      });
      const preparation = await engine.prepareHumanDecision(offer.id, reviewer);
      await engine.decide(preparation, reviewer, {
        schemaVersion: "human-decision-intent/1",
        offerId: preparation.offerId,
        taskArtifactId: preparation.taskArtifactId,
        inputArtifactIds: preparation.inputArtifactIds,
        result: { decision: "approved" },
      });
    }
    const reviewed = await engine.inspect(started.runId);
    assert.equal(
      reviewed.decisions.filter((decision) => sourceReviews.some((offer) => offer.id === decision.offerId)).length,
      9,
    );
    assert.equal(reviewed.decisions.some((decision) => decision.artifactId === seededApproval), false);
    const approvalBySourceId = new Map<string, ArtifactId>();
    for (const offer of sourceReviews) {
      const decision = reviewed.decisions.find((candidate) => candidate.offerId === offer.id);
      assert.equal(decision?.authority, "human");
      assert.equal(decision?.choice, "approved");
      assert.ok(decision?.artifactId);
      const artifact = reviewed.artifacts.find((candidate) => candidate.id === decision?.artifactId);
      assert.equal(artifact?.kind, "source_review_decision");
      assert.equal(artifact?.origin, "human");
      assert.ok(artifact?.parents.some((parent) => parent.artifactId === offer.taskArtifactId));
      assert.ok(artifact?.parents.some((parent) => parent.artifactId === offer.subjectArtifactId));
      approvalBySourceId.set(
        offer.actorKey.replace(/^source:/u, ""),
        decision.artifactId!,
      );
    }
    let rendererArtIds: string[] = [];
    const adapter = new InMemoryRendererAdapter(async (requestPath, destination) => {
      const manifest = JSON.parse(await (await import("node:fs/promises")).readFile(requestPath, "utf8")) as RenderManifest;
      assert.ok(manifest.inputs.some((input) => input.targetPath.endsWith("edition.yaml")));
      assert.equal(manifest.inputs.some((input) => input.targetPath.endsWith("edition.template.yaml")), false);
      assert.ok(manifest.inputs.some((input) => input.targetPath.endsWith("translations/es/edition.yaml")));
      assert.ok(manifest.inputs.some((input) => input.targetPath.startsWith("design/covers/")));
      assert.ok(manifest.inputs.some((input) => input.targetPath.startsWith("library/sources/") && input.targetPath.endsWith("/record.yaml")));
      assert.ok(manifest.inputs.some((input) => input.targetPath.startsWith("library/sources/") && input.targetPath.endsWith("/extracted.md")));
      assert.equal(manifest.inputs.filter((input) => /^editions\/[^/]+\/articles\/[^/]+\.md$/u.test(input.targetPath)).length, 7);
      assert.equal(manifest.inputs.filter((input) => /\/translations\/es\/articles\/[^/]+\.md$/u.test(input.targetPath)).length, 7);
      assert.equal(manifest.inputs.filter((input) => input.targetPath.endsWith("/manuscript/editorial.md")).length, 1);
      assert.equal(manifest.inputs.filter((input) => input.targetPath.endsWith("/translations/es/editorial.md")).length, 1);
      const selectedArtInputs = manifest.inputs.filter((input) => selectedArtIds.includes(input.artifactId));
      assert.equal(selectedArtInputs.length, 13);
      rendererArtIds = selectedArtInputs.map((input) => input.artifactId);
      const layouts = manifest.languages.map((language) => ({
        language,
        totalPages: 12,
        editorialPages: 1,
        articlePages: Object.fromEntries(manifest.inputs
          .map((input) => /articles\/([^/]+)\.md$/u.exec(input.targetPath)?.[1])
          .filter((id): id is string => id !== undefined)
          .map((id) => [id, 2])),
        figureCount: 13,
        criticResult: manifest.operation === "render_edition" ? "pass" as const : "not_run" as const,
      }));
      if (manifest.operation === "render_edition") {
        for (const language of manifest.languages) {
          await mkdir(join(destination, language), { recursive: true });
          for (const [path, body] of [
            [`${language}/reader.pdf`, "%PDF"], [`${language}/booklet.pdf`, "%PDF"], [`${language}/web.html`, "<main/>"],
            [`${language}/package.zip`, "zip"], [`${language}/render-critic.json`, '{"result":"pass"}'],
            [`${language}/preflight.json`, '{"studio":{"ready":true,"blockers":[]}}'],
          ] as const) await writeFile(join(destination, path), body);
        }
      }
      return {
        schemaVersion: 1,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
        editionId: manifest.editionId,
        files: manifest.operation === "render_edition" ? manifest.languages.flatMap((language) => [
          { path: `${language}/reader.pdf`, mediaType: "application/pdf", kind: "reader_pdf" },
          { path: `${language}/booklet.pdf`, mediaType: "application/pdf", kind: "booklet_pdf" },
          { path: `${language}/web.html`, mediaType: "text/html", kind: "web_output" },
          { path: `${language}/package.zip`, mediaType: "application/zip", kind: "package_artifact" },
          { path: `${language}/render-critic.json`, mediaType: "application/json", kind: "render_critic_report" },
          { path: `${language}/preflight.json`, mediaType: "application/json", kind: "printer_preflight" },
        ]) : [],
        layouts,
        inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
        tailArtFacts: {},
      };
    });
    const renderer = new RendererExecutor(adapter, { workDirectory: temporary });
    const inspection = new RenderInspectionExecutor();
    const bridge = new CooperativeModelBridge(engine);
    const modelAuthority = await LocalAuthorityStore.init(join(temporary, "model-authority"));
    await modelAuthority.enrollWorker({
      principalId: "fake-cooperative-model",
      authority: "model",
      capabilities: ["text_model", "source_access", "source_blind"],
    });
    const modelCredential = await modelAuthority.createCredentialProfile({
      principalId: "fake-cooperative-model",
    });
    await modelAuthority.grant({
      credentialProfileId: modelCredential.credentialProfileId,
      capabilities: ["text_model", "source_access", "source_blind"],
    });
    const modelWorker = await modelAuthority.authenticate({
      credentialProfileId: modelCredential.credentialProfileId,
      secret: modelCredential.secret,
    });
    const authorizedRenderers = await Promise.all([renderer, inspection].map(async (executor) => {
      const registration = await authorityFixture.registration(executor);
      assert.ok(registration.authorizedWorker);
      return {
        id: executor.id,
        worker: executor.worker,
        capabilities: executor.capabilities,
        authorizedWorker: registration.authorizedWorker,
        accepts: executor.accepts.bind(executor),
        execute: executor.execute.bind(executor),
      };
    }));
    let sawFreshWriter = false;
    let sawFreshTranslation = false;

    for (let turn = 0; turn < 400; turn += 1) {
      const view = await engine.inspect(started.runId);
      const visual = view.offers.find((offer) => offer.role === "visual_review" && offer.status === "offered");
      if (visual !== undefined) {
        assert.equal(
          view.offers.some((offer) => ["cover_art", "interior_art", "art_generation", "art_selection"].includes(offer.role)),
          false,
        );
        assert.equal(view.actors.filter((actor) => actor.logicalKey.startsWith("art:")).length, 0);
        assert.deepEqual([...rendererArtIds].sort(), [...selectedArtIds].sort());
        const composition = view.artifacts.find((artifact) => artifact.kind === "composition_manifest");
        assert.ok(composition);
        const compositionDocument = JSON.parse(await engine.readText(composition.id)) as {
          readonly images: readonly { readonly revision: { readonly revisionId: string } }[];
        };
        assert.deepEqual(
          compositionDocument.images.map((image) => image.revision.revisionId).sort(),
          selectedArtRevisions.map((image) => image.revisionId).sort(),
        );
        assert.equal(view.offers.some((offer) => offer.role === "release_approval" && offer.status === "offered"), false);
        assert.equal(sawFreshWriter, true);
        assert.equal(sawFreshTranslation, true);
        return;
      }
      const pending = view.offers.find((candidate) => candidate.status === "offered");
      if (pending?.role === "render" || pending?.role === "render_inspection") {
        const executable = await executeAvailableWork(engine, started.runId, authorizedRenderers, new AbortController().signal);
        if (executable.answered.length > 0) continue;
        assert.equal(executable.failed.length, 0, JSON.stringify(executable));
      }
      const offer = pending;
      assert.ok(offer, `run stopped before visual review at ${view.actors.map((actor) => actor.state).join(",")}`);
      if (offer.role === "writer" || offer.role === "editorial_writer" || offer.role === "translation_writer") {
        if (offer.role === "writer") {
          const articleId = offer.actorKey.replace(/^article:/u, "");
          const article = plan.pipeline.document.articles.find((candidate) => candidate.articleId === articleId);
          assert.ok(article);
          for (const sourceId of article.sourceIds) {
            assert.ok(offer.inputArtifacts.includes(approvalBySourceId.get(sourceId)!));
          }
          assert.equal(offer.inputArtifacts.includes(seededApproval), false);
        }
        const ticket = await bridge.claim(started.runId, offer.id, modelWorker);
        await bridge.answerMarkdown(ticket, `# Fresh ${offer.actorKey}\n\nFresh model prose.`);
        sawFreshWriter ||= offer.role === "writer" || offer.role === "editorial_writer";
        sawFreshTranslation ||= offer.role === "translation_writer";
        continue;
      }
      if (offer.role === "durable_checkpoint") {
        await answer(engine, offer, await durableCheckpointAnswer(engine, offer));
        continue;
      }
      switch (offer.role) {
        case "close_collection":
          assert.equal(offer.inputArtifacts.includes(seededApproval), false);
          await answer(engine, offer, response(offer, { choice: "close" }, "collection_decision"));
          break;
        case "plan_edition": {
          assert.equal(offer.inputArtifacts.includes(seededApproval), false);
          const planRequest = (await engine.readArtifact(offer.taskArtifactId)).artifact;
          assert.equal(
            planRequest.parents.some((parent) => parent.artifactId === seededApproval),
            false,
          );
          const plan = productionPlanFrom(runSpec);
          await answer(engine, offer, {
            contractVersion: offer.contractVersion,
            result: { choice: "approve", productionPlan: plan },
            artifacts: [{
              kind: "edition_plan",
              schemaVersion: offer.contractVersion,
              mediaType: "application/json",
              payload: { kind: "json", value: plan },
            }],
          });
          break;
        }
        case "measure_article":
          await answer(engine, offer, response(offer, { fits: true, openerFits: true, pageCount: 2 }, "article_measurement"));
          break;
        case "measure_edition":
          await answer(engine, offer, response(offer, { fits: true, pageCount: 12 }, "edition_measurement"));
          break;
        case "evidence":
          await answer(engine, offer, response(offer, { decision: "pass" }));
          break;
        case "worth":
        case "mechanics":
        case "craft":
          await answer(engine, offer, response(offer, { decision: "pass" }));
          break;
        case "edition_review":
          await answer(engine, offer, response(offer, { decision: "approved" }, "edition_review"));
          break;
        case "language_review":
          await answer(engine, offer, response(offer, { decision: "approved" }, "language_review"));
          break;
        case "language_fit":
          await answer(engine, offer, response(offer, { fits: true, pageCount: 2 }, "language_measurement"));
          break;
        default:
          assert.fail(`unexpected offer ${offer.role}`);
      }
    }
    assert.fail("write run did not reach visual review");
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

function productionPlan(): JsonObject {
  const articleBrief = id("article-brief");
  const writerPrompt = id("writer-prompt");
  const writingRules = id("writing-rules");
  const translationPrompt = id("translation-prompt");
  const selectedArt = Array.from({ length: 13 }, (_, index) => id(`selected-art-${index + 1}`));
  return {
    contractVersion: "approved-production-plan/1",
    sourceAssignmentPolicy: "at_least_once",
    articles: [{
      articleId: "one",
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine" },
      articleBrief,
      sourceIds: ["one-source"],
      writerPrompt,
      judgePrompts: { evidence: id("evidence-prompt") },
      writingRules,
      policy: { maxIterations: 1, maximumReaderPages: 7, teaching: "not_applicable", enabledLenses: ["evidence"], blockingLenses: [] },
      modelPolicy: model,
    }],
    art: selectedArt.map((artifactId, index) => ({
      key: `image-${index + 1}`,
      role: index === 0 ? "cover" : "interior",
      artifactId,
      briefArtifact: id("art-brief"),
      required: true,
    })),
    translations: [
      { pieceKind: "article", pieceId: "one", language: "es", sourceLanguage: "en", englishArtifacts: [id("english-article")], promptArtifact: translationPrompt, maximumReaderPages: 7, modelPolicy: model },
      { pieceKind: "editorial", pieceId: "opening", language: "es", sourceLanguage: "en", englishArtifacts: [id("english-editorial")], promptArtifact: translationPrompt, maximumReaderPages: 7, modelPolicy: model },
    ],
  } as JsonObject;
}

function productionPlanFrom(spec: EditionRootRunSpec): JsonObject {
  return {
    contractVersion: "approved-production-plan/1",
    sourceAssignmentPolicy: "exactly_once",
    articles: spec.edition.articles.map((article) => ({
      articleId: article.articleId,
      contentMode: article.contentMode,
      attribution: article.attribution,
      editionContext: article.editionContext,
      articleBrief: article.articleBrief,
      sourceIds: article.attribution.kind === "source_author" ? article.attribution.sourceIds : [],
      writerPrompt: article.writerPrompt,
      judgePrompts: article.judgePrompts,
      writingRules: article.writingRules,
      measurementProfileArtifact: article.measurementProfileArtifact,
      measurementInputArtifacts: article.measurementInputArtifacts,
      policy: article.policy,
      modelPolicy: article.modelPolicy,
    })),
    art: [],
    translations: spec.edition.translations.map((translation) => ({
      pieceKind: translation.pieceKind,
      pieceId: translation.pieceId,
      language: translation.language,
      sourceLanguage: translation.sourceLanguage,
      englishArtifacts: translation.englishArtifacts,
      promptArtifact: translation.promptArtifact,
      measurementProfileArtifact: translation.measurementProfileArtifact,
      measurementInputArtifacts: translation.measurementInputArtifacts,
      inputRevisions: translation.inputRevisions,
      maximumReaderPages: translation.maximumReaderPages,
      modelPolicy: translation.modelPolicy,
    })),
  } as JsonObject;
}

function spec(): EditionRootRunSpec {
  const edition = id("edition-config");
  const source = id("source");
  const sourceApproval = id("source-approval");
  const raw = id("source-raw");
  const evidence = id("source-evidence");
  const metadata = id("source-metadata");
  const profile = id("render-profile");
  const articleBrief = id("article-brief");
  const writerPrompt = id("writer-prompt");
  const writingRules = id("writing-rules");
  const evidencePrompt = id("evidence-prompt");
  const editorialBrief = id("editorial-brief");
  const editorialRules = id("editorial-rules");
  const translationPrompt = id("translation-prompt");
  const artBrief = id("art-brief");
  const englishArticle = id("english-article");
  const englishEditorial = id("english-editorial");
  const selectedArt = Array.from({ length: 13 }, (_, index) => id(`selected-art-${index + 1}`));
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: [
      { id: edition, kind: "edition_spec_revision_payload", schemaVersion: "1", mediaType: "application/yaml", origin: "imported", payload: { kind: "text", text: "id: 004-the-systems-around-the-model\n" }, metadata: { inputRevision: { kind: "edition_spec", editionId: "004", logicalId: "main", revisionId: "revision-layout" }, revisionPayloadPath: "edition.yaml", rendererTargetPath: "editions/004-the-systems-around-the-model/edition.yaml" } },
      { id: source, kind: "source_extraction", schemaVersion: "1", mediaType: "text/markdown", origin: "imported", payload: { kind: "text", text: "source" }, parents: [{ artifactId: raw, relation: "extracted_from" }] },
      { id: raw, kind: "raw_source_bundle", schemaVersion: "1", mediaType: "application/json", origin: "imported", payload: { kind: "json", value: {} }, parents: [{ artifactId: edition, relation: "captured_from_lead" }] },
      { id: evidence, kind: "raw_evidence", schemaVersion: "1", mediaType: "text/plain", origin: "imported", payload: { kind: "text", text: "evidence" }, parents: [{ artifactId: raw, relation: "bundle_content" }] },
      { id: metadata, kind: "source_metadata", schemaVersion: "1", mediaType: "application/json", origin: "imported", payload: { kind: "json", value: {} }, parents: [{ artifactId: raw, relation: "describes_bundle" }] },
      { id: sourceApproval, kind: "source_review_decision", schemaVersion: "1", mediaType: "application/json", origin: "human", payload: { kind: "json", value: { decision: "approved" } }, parents: [{ artifactId: raw, relation: "reviewed_raw_bundle" }, { artifactId: source, relation: "reviewed_extraction" }] },
      ...[articleBrief, writerPrompt, writingRules, evidencePrompt, editorialBrief, editorialRules, translationPrompt, artBrief, englishArticle, englishEditorial].map((artifactId) => ({ id: artifactId, kind: "fixture_input", schemaVersion: "1", mediaType: "text/markdown", origin: "imported" as const, payload: { kind: "text" as const, text: artifactId } })),
      { id: profile, kind: "render_profile", schemaVersion: "1", mediaType: "application/json", origin: "imported", payload: { kind: "json", value: { schemaVersion: 1, rendererContractVersion: RENDERER_CONTRACT_VERSION, primaryLanguage: "en", publicationName: "E2E", renderer: "weasyprint", inputs: [{ artifactId: edition, targetPath: "editions/004-the-systems-around-the-model/edition.yaml" }] } }, parents: [{ artifactId: edition, relation: "layout_input" }] },
      ...selectedArt.map((artifactId, index) => ({ id: artifactId, kind: "selected_image_revision_payload", schemaVersion: "1", mediaType: "image/png", origin: "imported" as const, payload: { kind: "bytes" as const, dataBase64: "iVBORw0KGgo=" }, metadata: { rendererTargetPath: `editions/004-the-systems-around-the-model/art/image-${index + 1}.png` } })),
    ],
    edition: {
      editionId: "004", execution: { kind: "produce" }, editionBrief: edition, sources: [{ sourceId: "one-source", leadArtifact: edition, rawBundleArtifact: raw, rawEvidenceArtifacts: [evidence], extractionArtifact: source, metadataArtifact: metadata, approvalArtifact: sourceApproval }],
      articles: [{ articleId: "one", contentMode: "original_synthesis", attribution: { kind: "magazine", byline: "Magazine" }, articleBrief, sourceIds: ["one-source"], writerPrompt, judgePrompts: { evidence: evidencePrompt }, writingRules, policy: { maxIterations: 1, maximumReaderPages: 7, teaching: "not_applicable", enabledLenses: ["evidence"], blockingLenses: [] }, modelPolicy: model }],
      editorial: { editorialId: "opening", briefArtifact: editorialBrief, writingRules: editorialRules, modelPolicy: model },
      translations: [
        { pieceKind: "article" as const, pieceId: "one", language: "es", sourceLanguage: "en", englishArtifacts: [englishArticle], promptArtifact: translationPrompt, maximumReaderPages: 7, modelPolicy: model },
        { pieceKind: "editorial" as const, pieceId: "opening", language: "es", sourceLanguage: "en", englishArtifacts: [englishEditorial], promptArtifact: translationPrompt, maximumReaderPages: 7, modelPolicy: model },
      ],
      art: selectedArt.map((artifactId, index) => ({ key: `image-${index + 1}`, role: index === 0 ? "cover" as const : "interior" as const, artifactId, briefArtifact: artBrief, required: true })),
      render: { renderManifestArtifact: profile, rendererContractVersion: RENDERER_CONTRACT_VERSION, configuredLanguages: ["en", "es"], studioPolicy: "not_applicable", layoutInputRevisions: [{ kind: "write_pipeline", editionId: "004", logicalId: "e2e", revisionId: "revision-layout" as never }] },
      release: { publicationArtifact: edition, sourceArtifacts: [source], dryRun: true, target: "private" }, modelPolicy: model,
    },
  };
}

function response(offer: WorkOfferView, result: JsonObject, kind?: string) {
  return { contractVersion: offer.contractVersion, result, artifacts: kind === undefined ? [] : [{ kind, schemaVersion: offer.contractVersion, mediaType: "application/json", payload: { kind: "json" as const, value: result } }] };
}

async function answer(engine: SqliteRunEngine, offer: WorkOfferView, work: { readonly contractVersion: string; readonly result: JsonObject; readonly artifacts: readonly AnswerArtifact[] }) {
  const authority = authorities.get(engine);
  assert.ok(authority, "test engine is missing its authority fixture");
  if (offer.requirements?.authority === "human") {
    const worker = await authority.workerFor(offer);
    const preparation = await engine.prepareHumanDecision(offer.id, worker);
    await engine.decide(preparation, worker, {
      schemaVersion: "human-decision-intent/1",
      offerId: preparation.offerId,
      taskArtifactId: preparation.taskArtifactId,
      inputArtifactIds: preparation.inputArtifactIds,
      result: work.result,
    });
    return;
  }
  const claim = await authority.claim(engine, offer);
  await engine.answer(claim, work);
}
