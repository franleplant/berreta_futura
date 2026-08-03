import assert from "node:assert/strict";
import { copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { test } from "node:test";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  EditionRootRunSpec,
  JsonObject,
  RunId,
  RunView,
  WorkClaim,
  WorkOfferView,
} from "../contracts/index.ts";
import {
  executeAvailableWork,
  ArticleMeasurementExecutor,
  LanguageFitExecutor,
  RenderInspectionExecutor,
  RendererExecutor,
  SourceArchiveExecutor,
  type ExecutorResolver,
} from "../executors/index.ts";
import {
  InMemoryRendererAdapter,
  RENDERER_CONTRACT_VERSION,
  type ArticleMeasurementProfile,
  type LanguageFitProfile,
  type RenderExecutionProfile,
  type RenderManifest,
} from "../renderer-adapter/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";
import {
  InMemorySourceAdapter,
  SOURCE_CONTRACT_VERSION,
  type SourceCaptureProfile,
  type SourceRequest,
} from "../source-adapter/index.ts";

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function textSeed(
  artifactId: ArtifactId,
  text: string,
  kind = "fixture_input",
  parents: ArtifactSeed["parents"] = [],
  origin: ArtifactSeed["origin"] = "imported",
): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "fixture/1",
    mediaType: "text/plain",
    origin,
    payload: { kind: "text", text },
    ...(parents.length === 0 ? {} : { parents }),
  };
}

function jsonSeed(
  artifactId: ArtifactId,
  value: JsonObject,
  kind: string,
  parents: readonly { readonly artifactId: ArtifactId; readonly relation: string }[] = [],
): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "fixture/1",
    mediaType: "application/json",
    origin: "imported",
    payload: { kind: "json", value },
    parents,
  };
}

function baseEdition(
  prefix: string,
  extraArtifacts: readonly ArtifactSeed[],
): EditionRootRunSpec {
  const editionBrief = id(`${prefix}-edition-brief`);
  const planning = id(`${prefix}-planning`);
  const editorialBrief = id(`${prefix}-editorial-brief`);
  const writingRules = id(`${prefix}-writing-rules`);
  const editorial = id(`${prefix}-editorial`);
  const renderProfile = id(`${prefix}-unused-render-profile`);
  const release = id(`${prefix}-release`);
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: [
      textSeed(editionBrief, "edition brief"),
      textSeed(planning, "planning"),
      textSeed(editorialBrief, "editorial brief"),
      textSeed(writingRules, "writing rules"),
      textSeed(editorial, "editorial", "editorial_manuscript"),
      textSeed(renderProfile, "unused render profile", "render_profile"),
      textSeed(release, "release placeholder"),
      ...extraArtifacts,
    ],
    edition: {
      editionId: `${prefix}-edition`,
      execution: { kind: "produce" },
      editionBrief,
      planningArtifact: planning,
      sources: [],
      articles: [],
      editorial: {
        editorialId: `${prefix}-editorial`,
        briefArtifact: editorialBrief,
        writingRules,
        initialManuscript: editorial,
        modelPolicy: { default: { adapter: "fixture", model: "fixture" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: renderProfile,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: release,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "fixture", model: "fixture" } },
    },
  };
}

test("SourceMachine capture offer runs through the versioned archive executor", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-source-executor-"));
  const authority = await AuthorityTestHarness.create(temporary);
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "engine-artifacts"),
  });
  try {
    const lead = id("source-executor-lead");
    const page = id("source-executor-page");
    const profileId = id("source-executor-profile");
    const profile: SourceCaptureProfile = {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: "source-executor",
      leadArtifactId: lead,
      files: [
        { artifactId: lead, targetPath: "raw/lead.txt" },
        { artifactId: page, targetPath: "raw/page.html" },
      ],
      metadata: { fixture: true },
    };
    const spec = baseEdition("source-executor", [
      textSeed(lead, "https://example.invalid/article", "submitted_lead"),
      textSeed(page, "<main>captured evidence</main>", "captured_page"),
      jsonSeed(
        profileId,
        profile as unknown as JsonObject,
        "source_capture_profile",
        [
          { artifactId: lead, relation: "captures_lead" },
          { artifactId: page, relation: "capture_input" },
        ],
      ),
    ]);
    const sourceSpec: EditionRootRunSpec = {
      ...spec,
      edition: {
        ...spec.edition,
        sources: [{
          sourceId: "source-executor",
          leadArtifact: lead,
          captureProfileArtifact: profileId,
          captureInputArtifacts: [page],
        }],
      },
    };
    let observedRequest: SourceRequest | undefined;
    const adapter = new InMemorySourceAdapter(async (requestPath, destination) => {
      observedRequest = JSON.parse(await readFile(requestPath, "utf8")) as SourceRequest;
      assert.equal(isAbsolute(observedRequest.artifactRoot), true);
      assert.equal(observedRequest.artifactRoot.startsWith(resolve(temporary)), true);
      for (const file of observedRequest.files) {
        assert.equal(file.sourcePath.startsWith(observedRequest.artifactRoot), true);
        const output = join(destination, file.targetPath);
        await mkdir(dirname(output), { recursive: true });
        await copyFile(file.sourcePath, output);
      }
      return {
        schemaVersion: 1,
        sourceContractVersion: SOURCE_CONTRACT_VERSION,
        sourceId: observedRequest.sourceId,
        files: observedRequest.files.map((file) => ({
          path: file.targetPath,
          kind: "raw_evidence",
        })),
        inputArtifactIds: [
          observedRequest.leadArtifactId,
          ...observedRequest.files.map((file) => file.artifactId),
        ],
      };
    });
    const started = await engine.start(sourceSpec);
    const result = await executeAvailableWork(
      engine,
      started.runId,
      await configured(authority, [{
        executor: new SourceArchiveExecutor(adapter, { workDirectory: temporary }),
        roles: ["capture_source"],
      }]),
      new AbortController().signal,
    );
    assert.equal(result.answered.length, 1);
    assert.equal(result.failed.length, 0);
    assert.ok(observedRequest);

    const view = await engine.inspect(started.runId);
    const sourceActor = view.actors.find((actor) => actor.machine === "source");
    assert.equal(sourceActor?.state, "extracting");
    const bundle = view.artifacts.find((artifact) => artifact.kind === "raw_source_bundle");
    assert.ok(bundle);
    const raw = view.artifacts.filter((artifact) => artifact.kind === "raw_evidence");
    assert.equal(raw.length, 2);
    assert.equal(
      raw.every((artifact) => artifact.producingOfferId === result.answered[0]),
      true,
    );
    assert.equal(
      bundle.parents.filter((parent) => parent.relation === "raw_evidence").length,
      2,
    );
    assert.equal(
      await engine.readText(
        raw.find((artifact) => artifact.metadata.relativePath === "raw/page.html")?.id ??
          id("missing"),
      ),
      "<main>captured evidence</main>",
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("RenderMachine measure and render offers run through one versioned renderer executor", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-render-executor-"));
  const authority = await AuthorityTestHarness.create(temporary);
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "engine-artifacts"),
  });
  try {
    const editionBrief = id("render-executor-edition-brief");
    const planning = id("render-executor-planning");
    const articleBrief = id("render-executor-article-brief");
    const writerPrompt = id("render-executor-writer-prompt");
    const worthPrompt = id("render-executor-worth-prompt");
    const evidencePrompt = id("render-executor-evidence-prompt");
    const craftPrompt = id("render-executor-craft-prompt");
    const writingRules = id("render-executor-writing-rules");
    const manuscript = id("render-executor-manuscript");
    const editorialBrief = id("render-executor-editorial-brief");
    const editorial = id("render-executor-editorial");
    const printer = id("render-executor-printer");
    const stagedEdition = id("render-executor-staged-edition");
    const renderProfileId = id("render-executor-profile");
    const release = id("render-executor-release");
    const sourceLead = id("render-executor-source-lead");
    const sourceRaw = id("render-executor-source-raw");
    const sourceEvidence = id("render-executor-source-evidence");
    const sourceExtraction = id("render-executor-source-extraction");
    const sourceMetadata = id("render-executor-source-metadata");
    const sourceApproval = id("render-executor-source-approval");
    const profile: RenderExecutionProfile = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      primaryLanguage: "en",
      publicationName: "Executor Fixture",
      renderer: "weasyprint",
      inputs: [
        { artifactId: stagedEdition, targetPath: "editions/render-package/edition.yaml" },
        { artifactId: manuscript, targetPath: "editions/render-executor/article.md" },
        { artifactId: editorial, targetPath: "editions/render-executor/editorial.md" },
        { artifactId: printer, targetPath: "profiles/printer.json" },
      ],
      metadata: { fixture: true, imageGenerationAllowed: false },
    };
    const artifacts = [
      textSeed(editionBrief, "edition brief"),
      textSeed(planning, "planning"),
      textSeed(articleBrief, "article brief"),
      textSeed(writerPrompt, "writer prompt"),
      textSeed(worthPrompt, "worth prompt"),
      textSeed(evidencePrompt, "evidence prompt"),
      textSeed(craftPrompt, "craft prompt"),
      textSeed(writingRules, "writing rules"),
      textSeed(manuscript, "article manuscript", "article_manuscript"),
      textSeed(editorialBrief, "editorial brief"),
      textSeed(editorial, "editorial manuscript", "editorial_manuscript"),
      jsonSeed(printer, { name: "Fixture printer" }, "printer_profile"),
      {
        ...textSeed(stagedEdition, "id: render-package\n", "edition_spec_revision_payload"),
        mediaType: "application/yaml",
        metadata: {
          inputRevision: {
            kind: "edition_spec",
            editionId: "004",
            logicalId: "main",
            revisionId: "rev_fixture",
          },
          revisionPayloadPath: "edition.yaml",
          rendererTargetPath: "editions/render-package/edition.yaml",
        },
      },
      jsonSeed(
        renderProfileId,
        profile as unknown as JsonObject,
        "render_profile",
        profile.inputs.map((input) => ({
          artifactId: input.artifactId,
          relation: "staged_input",
        })),
      ),
      textSeed(release, "release placeholder"),
      textSeed(sourceLead, "source lead", "submitted_lead"),
      textSeed(sourceRaw, "raw bundle", "raw_source_bundle", [
        { artifactId: sourceLead, relation: "captured_from_lead" },
      ]),
      textSeed(sourceEvidence, "raw evidence", "raw_evidence", [
        { artifactId: sourceRaw, relation: "bundle_content" },
      ]),
      textSeed(sourceExtraction, "source extraction", "source_extraction", [
        { artifactId: sourceRaw, relation: "extracted_from" },
      ]),
      textSeed(sourceMetadata, "source metadata", "source_metadata", [
        { artifactId: sourceRaw, relation: "describes_bundle" },
      ]),
    ];
    const spec: EditionRootRunSpec = {
      schemaVersion: 1,
      kind: "edition",
      artifacts,
      edition: {
        editionId: "render-executor",
        execution: { kind: "produce" },
        editionBrief,
        planningArtifact: planning,
        sources: [{
          sourceId: "render-executor-source",
          leadArtifact: sourceLead,
          rawBundleArtifact: sourceRaw,
          rawEvidenceArtifacts: [sourceEvidence],
          extractionArtifact: sourceExtraction,
          metadataArtifact: sourceMetadata,
        }],
        articles: [{
          articleId: "render-executor-article",
          contentMode: "original_synthesis",
          attribution: { kind: "magazine", byline: "Magazine" },
          articleBrief,
          sourceIds: ["render-executor-source"],
          writerPrompt,
          judgePrompts: {
            worth: worthPrompt,
            evidence: evidencePrompt,
            craft: craftPrompt,
          },
          writingRules,
          initialManuscript: manuscript,
          policy: {
            maxIterations: 1,
            maximumReaderPages: 7,
            teaching: "not_applicable",
            enabledLenses: ["worth", "evidence", "craft"],
            blockingLenses: [],
          },
          modelPolicy: { default: { adapter: "fixture", model: "fixture" } },
        }],
        editorial: {
          editorialId: "render-executor-editorial",
          briefArtifact: editorialBrief,
          writingRules,
          initialManuscript: editorial,
          modelPolicy: { default: { adapter: "fixture", model: "fixture" } },
        },
        translations: [],
        art: [],
        render: {
          renderManifestArtifact: renderProfileId,
          rendererContractVersion: RENDERER_CONTRACT_VERSION,
          printerProfileArtifact: printer,
          configuredLanguages: ["en"],
          studioPolicy: "home_ready_studio_blocked",
        },
        release: {
          publicationArtifact: release,
          sourceArtifacts: [],
          dryRun: true,
          target: "private",
        },
        modelPolicy: { default: { adapter: "fixture", model: "fixture" } },
      },
    };
    const operations: RenderManifest["operation"][] = [];
    const adapter = new InMemoryRendererAdapter(async (manifestPath, destination) => {
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as RenderManifest;
      operations.push(manifest.operation);
      assert.equal(manifest.editionId, "render-package");
      assert.equal(manifest.artifactRoot.startsWith(resolve(temporary)), true);
      assert.equal(manifest.inputs.every((input) => input.sourcePath.startsWith(manifest.artifactRoot)), true);
      assert.equal(manifest.metadata?.imageGenerationAllowed, false);
      const layouts = [{
        language: "en",
        totalPages: 12,
        editorialPages: 1,
        articlePages: { "render-executor-article": 1 },
        figureCount: 0,
        criticResult: manifest.operation === "render_edition" ? "pass" as const : "not_run" as const,
      }];
      if (manifest.operation === "render_edition") {
        await mkdir(join(destination, "en"), { recursive: true });
        await writeFile(join(destination, "en", "reader.pdf"), "%PDF fixture", "utf8");
        await writeFile(join(destination, "en", "web.html"), "<main>fixture</main>", "utf8");
        await writeFile(join(destination, "en", "booklet.pdf"), "%PDF booklet fixture", "utf8");
        await writeFile(join(destination, "en", "package.zip"), "fixture package", "utf8");
        await writeFile(
          join(destination, "en", "render-critic.json"),
          JSON.stringify({ result: "pass" }),
          "utf8",
        );
        await writeFile(
          join(destination, "en", "preflight.json"),
          JSON.stringify({
            schema_version: 1,
            result: "ready",
            studio: { ready: true, blockers: [] },
          }),
          "utf8",
        );
      }
      return {
        schemaVersion: 1,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
        editionId: manifest.editionId,
        files: manifest.operation === "render_edition"
          ? [
              { path: "en/reader.pdf", mediaType: "application/pdf", kind: "reader_pdf" },
              { path: "en/web.html", mediaType: "text/html", kind: "web_output" },
              { path: "en/booklet.pdf", mediaType: "application/pdf", kind: "booklet_pdf" },
              { path: "en/package.zip", mediaType: "application/zip", kind: "package_artifact" },
              { path: "en/render-critic.json", mediaType: "application/json", kind: "render_critic_report" },
              { path: "en/preflight.json", mediaType: "application/json", kind: "printer_preflight" },
            ]
          : [],
        layouts,
        inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
        tailArtFacts: {},
      };
    });

    const started = await engine.start(spec);
    await advanceToRenderMeasurement(engine, started.runId, authority);
    const executor = new RendererExecutor(adapter, { workDirectory: temporary });
    const measurement = await executeAvailableWork(
      engine,
      started.runId,
      await configured(authority, [{ executor, roles: ["measure_edition", "render"] }]),
      new AbortController().signal,
    );
    assert.equal(measurement.answered.length, 1, JSON.stringify(measurement));
    assert.equal(measurement.failed.length, 0);
    let view = await engine.inspect(started.runId);
    assert.equal(offered(view, "render").status, "offered");
    const rendering = await executeAvailableWork(
      engine,
      started.runId,
      await configured(authority, [{ executor, roles: ["measure_edition", "render"] }]),
      new AbortController().signal,
    );
    assert.equal(rendering.answered.length, 1);
    assert.equal(rendering.failed.length, 0);
    assert.deepEqual(operations, ["measure_edition", "render_edition"]);

    view = await engine.inspect(started.runId);
    assert.equal(offered(view, "render_inspection").status, "offered");
    const outputArtifacts = view.artifacts.filter(
      (artifact) => ["reader_pdf", "web_output", "booklet_pdf", "package_artifact", "render_critic_report", "printer_preflight"].includes(
        artifact.kind,
      ),
    );
    assert.equal(outputArtifacts.length, 6);
    assert.equal(
      outputArtifacts.every((artifact) =>
        artifact.producingOfferId === rendering.answered[0] &&
        artifact.parents.some((parent) => parent.artifactId === manuscript),
      ),
      true,
    );
    assert.equal(await engine.readText(outputArtifacts.find((artifact) => artifact.kind === "reader_pdf")?.id ?? id("missing")), "%PDF fixture");

    const inspection = await executeAvailableWork(
      engine,
      started.runId,
      await configured(authority, [{ executor: new RenderInspectionExecutor(), roles: ["render_inspection"] }]),
      new AbortController().signal,
    );
    assert.equal(inspection.answered.length, 1, JSON.stringify(inspection));
    view = await engine.inspect(started.runId);
    assert.equal(offered(view, "visual_review").status, "offered");
    const inspectionArtifact = view.artifacts.find(
      (artifact) => artifact.kind === "render_inspection",
    );
    assert.ok(inspectionArtifact);
    assert.deepEqual(
      inspectionArtifact.parents
        .filter((parent) => parent.relation === "inspected_render")
        .map((parent) => parent.artifactId)
        .sort(),
      outputArtifacts.map((artifact) => artifact.id).sort(),
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("ArticleMachine uses the renderer-backed isolated measurement profile", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-article-measurement-"));
  const authority = await AuthorityTestHarness.create(temporary);
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "engine-artifacts"),
  });
  try {
    const brief = id("article-measure-brief");
    const manuscript = id("article-measure-manuscript");
    const editionInput = id("article-measure-edition-input");
    const profileId = id("article-measure-profile");
    const writerPrompt = id("article-measure-writer");
    const worthPrompt = id("article-measure-worth");
    const evidencePrompt = id("article-measure-evidence");
    const source = id("article-measure-source");
    const rules = id("article-measure-rules");
    const profile: ArticleMeasurementProfile = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      editionId: "article-measure-edition",
      articleId: "measured-article",
      manuscriptArtifactId: manuscript,
      maximumReaderPages: 7,
      primaryLanguage: "en",
      publicationName: "Measurement Fixture",
      renderer: "reportlab",
      inputs: [
        { artifactId: editionInput, targetPath: "editions/fixture/edition.yaml" },
        { artifactId: manuscript, targetPath: "editions/fixture/manuscript.md" },
      ],
      metadata: { imageGenerationAllowed: false },
    };
    const spec: ArticleRootRunSpec = {
      schemaVersion: 1,
      kind: "article",
      artifacts: [
        textSeed(brief, "measure article", "article_brief"),
        textSeed(manuscript, "# Measured\n\nArticle.", "article_manuscript"),
        textSeed(editionInput, "edition: fixture", "renderer_input"),
        jsonSeed(profileId, profile as unknown as JsonObject, "article_measurement_profile", [
          { artifactId: manuscript, relation: "measured_manuscript" },
          { artifactId: editionInput, relation: "renderer_input" },
        ]),
        textSeed(writerPrompt, "writer", "writer_prompt"),
        textSeed(worthPrompt, "worth", "judge_prompt"),
        textSeed(evidencePrompt, "evidence", "judge_prompt"),
        textSeed(source, "source", "source_extraction"),
        textSeed(rules, "rules", "writing_rules"),
      ],
      article: {
        articleId: "measured-article",
        contentMode: "original_synthesis",
        attribution: { kind: "magazine", byline: "Magazine" },
        articleBrief: brief,
        sources: [source],
        sourceApprovalArtifacts: [],
        writerPrompt,
        judgePrompts: { worth: worthPrompt, evidence: evidencePrompt },
        writingRules: rules,
        measurementProfileArtifact: profileId,
        measurementInputArtifacts: [editionInput],
        initialManuscript: manuscript,
        policy: {
          maxIterations: 2,
          maximumReaderPages: 7,
          teaching: "not_applicable",
          enabledLenses: ["worth", "evidence"],
          blockingLenses: ["worth"],
        },
        modelPolicy: { default: { adapter: "fixture", model: "fixture" } },
      },
    };
    const operations: RenderManifest[] = [];
    const adapter = new InMemoryRendererAdapter(async (requestPath) => {
      const request = JSON.parse(await readFile(requestPath, "utf8")) as RenderManifest;
      operations.push(request);
      return {
        schemaVersion: 1,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
        editionId: request.editionId,
        files: [],
        layouts: [{
          language: "en",
          totalPages: 10,
          editorialPages: 1,
          articlePages: { "measured-article": 6 },
          figureCount: 0,
          criticResult: "not_run",
        }],
        inputArtifactIds: request.inputs.map((input) => input.artifactId),
        tailArtFacts: {},
      };
    });

    const started = await engine.start(await prepareArticleSources(
      engine,
      spec,
      "article-measurement",
      await authority.human(),
    ));
    const result = await executeAvailableWork(
      engine,
      started.runId,
      await configured(authority, [{
        executor: new ArticleMeasurementExecutor(adapter, { workDirectory: temporary }),
        roles: ["measure_article"],
      }]),
      new AbortController().signal,
    );
    assert.equal(result.answered.length, 1, JSON.stringify(result));
    assert.equal(result.failed.length, 0);
    assert.equal(operations.length, 1);
    assert.equal(operations[0]?.operation, "measure_article");
    assert.equal(operations[0]?.articleId, "measured-article");
    assert.deepEqual(
      operations[0]?.inputs.map((input) => input.artifactId),
      [editionInput, manuscript],
    );
    const view = await engine.inspect(started.runId);
    assert.equal(
      (view.actors[0]?.input.spec as JsonObject | undefined)?.measurementProfileArtifact,
      profileId,
    );
    const measurement = view.artifacts.find(
      (artifact) => artifact.kind === "article_measurement",
    );
    assert.ok(measurement);
    assert.equal(
      measurement.parents.some((parent) => parent.artifactId === manuscript),
      true,
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});

test("language fit measures every translated piece and binds review lineage", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-language-fit-"));
  try {
    const profileId = id("language-fit-profile");
    const editionInput = id("language-fit-edition");
    const translation = id("language-fit-translation");
    const review = id("language-fit-review");
    const profile: LanguageFitProfile = {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      editionId: "language-fit-edition",
      language: "es",
      primaryLanguage: "es",
      publicationName: "Language Fit Fixture",
      renderer: "reportlab",
      inputs: [
        { artifactId: editionInput, targetPath: "editions/fixture/es/edition.yaml" },
        { artifactId: translation, targetPath: "editions/fixture/es/article.md" },
      ],
      translatedPieces: [{
        articleId: "translated-article",
        artifactId: translation,
        maximumReaderPages: 6,
      }],
      metadata: { imageGenerationAllowed: false },
    };
    const payloads = new Map<ArtifactId, Uint8Array>([
      [profileId, Buffer.from(JSON.stringify(profile))],
      [editionInput, Buffer.from("edition: fixture")],
      [translation, Buffer.from("# Traducción")],
      [review, Buffer.from(JSON.stringify({ decision: "approved" }))],
    ]);
    const profileArtifact = {
      id: profileId,
      kind: "language_fit_profile",
      schemaVersion: "language-fit-profile/1",
      mediaType: "application/json",
      origin: "machine" as const,
      sizeBytes: payloads.get(profileId)?.byteLength ?? 0,
      parents: [
        { artifactId: editionInput, relation: "renderer_input" },
        { artifactId: translation, relation: "translated_piece" },
      ],
      metadata: {},
      createdAt: new Date(0).toISOString(),
    };
    const offer: WorkOfferView = {
      id: "offer-language-fit" as WorkOfferView["id"],
      runId: "run-language-fit" as RunId,
      actorId: "actor-language-fit" as WorkOfferView["actorId"],
      actorKey: "translation:es",
      state: "language_fit",
      stateVisitId: "visit-language-fit" as WorkOfferView["stateVisitId"],
      role: "language_fit",
      slot: "language_fit",
      inputArtifacts: [translation, review, profileId, editionInput],
      taskArtifactId: profileId,
      contractVersion: "language-fit/1",
      allowedWorkerCapabilities: ["subprocess"],
      status: "claimed",
      createdAt: new Date(0).toISOString(),
    };
    const claim: WorkClaim = {
      offerId: offer.id,
      attemptId: "attempt-language-fit" as WorkClaim["attemptId"],
      attemptFence: 1,
      ticket: "test-render-ticket",
      worker: {
        principalId: "language-fit-worker",
        authority: "tool",
        capabilities: ["subprocess"],
      },
      leaseExpiresAt: new Date(Date.now() + 60_000).toISOString(),
    };
    let operation: RenderManifest["operation"] | undefined;
    const adapter = new InMemoryRendererAdapter(async (requestPath) => {
      const request = JSON.parse(await readFile(requestPath, "utf8")) as RenderManifest;
      operation = request.operation;
      return {
        schemaVersion: 1,
        rendererContractVersion: RENDERER_CONTRACT_VERSION,
        editionId: request.editionId,
        files: [],
        layouts: [{
          language: "es",
          totalPages: 14,
          editorialPages: 1,
          articlePages: { "translated-article": 7 },
          figureCount: 0,
          criticResult: "not_run",
        }],
        inputArtifactIds: request.inputs.map((input) => input.artifactId),
        tailArtFacts: {},
      };
    });
    const executor = new LanguageFitExecutor(adapter, { workDirectory: temporary });
    const answer = await executor.execute({
      claim,
      offer,
      artifacts: {
        readArtifact: async (artifactId) => {
          assert.equal(artifactId, profileId);
          return { artifact: profileArtifact, bytes: payloads.get(profileId) ?? new Uint8Array() };
        },
        readBytes: async (artifactId) => payloads.get(artifactId) ?? new Uint8Array(),
        readText: async (artifactId) => Buffer.from(
          payloads.get(artifactId) ?? new Uint8Array(),
        ).toString("utf8"),
      },
      signal: new AbortController().signal,
    });
    await executor.release({
      claim,
      offer,
      artifacts: {
        readBytes: async (artifactId) => payloads.get(artifactId) ?? new Uint8Array(),
        readText: async (artifactId) => Buffer.from(
          payloads.get(artifactId) ?? new Uint8Array(),
        ).toString("utf8"),
      },
      signal: new AbortController().signal,
    });
    assert.equal(operation, "measure_edition");
    assert.equal(answer.result.fits, false);
    assert.equal(answer.result.decision, "revise");
    const measurement = answer.artifacts[0];
    assert.equal(measurement?.kind, "language_measurement");
    assert.equal(
      measurement?.parents?.some((parent) => parent.artifactId === review),
      true,
    );
    assert.equal(
      measurement?.parents?.some((parent) => parent.artifactId === translation),
      true,
    );
    assert.equal(
      measurement?.payload.kind === "json" &&
        Array.isArray((measurement.payload.value as JsonObject).layouts),
      true,
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

async function advanceToRenderMeasurement(
  engine: SqliteRunEngine,
  runId: RunId,
  authority: AuthorityTestHarness,
): Promise<void> {
  for (let step = 0; step < 30; step += 1) {
    const view = await engine.inspect(runId);
    if (view.offers.some((offer) => offer.role === "measure_edition" && offer.status === "offered")) {
      return;
    }
    const offers = view.offers.filter((offer) => offer.status === "offered");
    assert.ok(offers.length > 0, `run stopped before render measurement at ${view.actors[0]?.state}`);
    for (const offer of offers) {
      switch (offer.role) {
        case "close_collection":
          await submit(engine, offer, authority, { choice: "close" }, [{
            kind: "collection_decision",
            schemaVersion: "close-collection/1",
            mediaType: "application/json",
            payload: { kind: "json", value: { choice: "close" } },
          }]);
          break;
        case "measure_article":
          await submit(
            engine,
            offer,
            authority,
            { fits: true, pageCount: 1, openerFits: true },
            [{
              kind: "article_measurement",
              schemaVersion: "article-measure_article/1",
              mediaType: "application/json",
              payload: {
                kind: "json",
                value: { fits: true, pageCount: 1, openerFits: true },
              },
            }],
          );
          break;
        case "worth":
        case "evidence":
        case "craft":
          await submit(engine, offer, authority, { decision: "pass" });
          break;
        case "review_source":
          await submit(engine, offer, authority, { decision: "approved" }, [{
            kind: "source_review_decision",
            schemaVersion: "review-source/1",
            mediaType: "application/json",
            payload: { kind: "json", value: { decision: "approved" } },
          }]);
          break;
        case "edition_review":
          await submit(engine, offer, authority, { decision: "approved" }, [{
            kind: "edition_review",
            schemaVersion: "edition-review/1",
            mediaType: "application/json",
            payload: { kind: "json", value: { decision: "approved" } },
          }]);
          break;
        case "durable_checkpoint":
          await submit(engine, offer, authority, {});
          break;
        default:
          assert.fail(`unexpected offer before render: ${offer.role}`);
      }
    }
  }
  assert.fail("run exceeded the render setup step limit");
}

function offered(view: RunView, role: string): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === role && candidate.status === "offered",
  );
  assert.ok(offer, `run did not offer ${role}`);
  return offer;
}

async function submit(
  engine: SqliteRunEngine,
  offer: WorkOfferView,
  authority: AuthorityTestHarness,
  result: JsonObject,
  artifacts: readonly AnswerArtifact[] = [],
): Promise<RunView> {
  if (offer.requirements?.authority === "human" || offer.allowedWorkerCapabilities.includes("human")) {
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

async function configured(
  authority: AuthorityTestHarness,
  executors: readonly {
    readonly executor: Parameters<AuthorityTestHarness["registration"]>[0];
    readonly roles: readonly string[];
  }[],
): Promise<ExecutorResolver> {
  const registrations = await Promise.all(
    executors.map(async ({ executor, roles }) => await authority.registration(executor, { roles })),
  );
  return {
    resolve: (_view, offer) => {
      const registration = registrations.find(({ executor, roles }) =>
        executor.accepts(offer) && roles?.includes(offer.role),
      );
      if (registration === undefined || registration.authorizedWorker === undefined) return undefined;
      const executor = registration.executor;
      return {
        id: executor.id,
        worker: executor.worker,
        capabilities: executor.capabilities,
        authorizedWorker: registration.authorizedWorker,
        accepts: (candidate) => executor.accepts(candidate),
        execute: async (context) => await executor.execute(context),
        ...(executor.release === undefined
          ? {}
          : { release: async (context) => await executor.release?.(context) }),
      };
    },
  };
}
