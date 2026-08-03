import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type { RevisionId } from "../contracts/index.ts";
import {
  WritePipelineError,
  parseWritePipelineDocument,
  resolveWritePipeline,
} from "../durable/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { prepareWriteProduction } from "../write-production.ts";

const REVISION = "rev_20260803T060000000Z_aaaaaaaaaaaa" as RevisionId;
const PIPELINE_REF = {
  kind: "write_pipeline" as const,
  editionId: "004",
  logicalId: "edition4-write",
  revisionId: REVISION,
};

test("write pipeline pins a fresh seven-piece production graph and exactly thirteen selected images", () => {
  const parsed = parseWritePipelineDocument(fixture(), PIPELINE_REF);

  assert.equal(parsed.articles.length, 7);
  assert.equal(parsed.images.length, 13);
  assert.deepEqual(
    parsed.rendererInputs.map((input) => input.rendererTargetPath),
    [
      "editions/004-the-systems-around-the-model/edition.yaml",
      "editions/004-the-systems-around-the-model/design/writing-rules.md",
    ],
  );
  assert.equal(parsed.translations[0]?.parents["opening"]?.kind, "editorial");
  assert.equal(parsed.articles[0]?.modelPolicy.default.model, "gpt-5.6-terra");
  assert.equal(parsed.articles[0]?.modelPolicy.default.reasoningEffort, "high");
  assert.equal(parsed.articles[0]?.parent?.revisionId, REVISION);
});

test("write pipeline refuses old manuscript reuse, image count drift, and incomplete translation parents", () => {
  const oldManuscript = fixture();
  oldManuscript.articles[0]!.initial_manuscript = "old-artifact";
  assert.throws(
    () => parseWritePipelineDocument(oldManuscript, PIPELINE_REF),
    (error: unknown) => error instanceof WritePipelineError && error.code === "WRITE_PIPELINE_INVALID",
  );

  const imageDrift = fixture();
  imageDrift.images.pop();
  assert.throws(
    () => parseWritePipelineDocument(imageDrift, PIPELINE_REF),
    (error: unknown) => error instanceof WritePipelineError && error.code === "WRITE_PIPELINE_INVALID",
  );

  const missingParent = fixture();
  delete missingParent.translations[0]!.parents.opening;
  assert.throws(() => parseWritePipelineDocument(missingParent, PIPELINE_REF), /parents must name every English piece/u);

  const duplicateTarget = fixture();
  duplicateTarget.renderer_inputs.push({ ...duplicateTarget.renderer_inputs[0] });
  assert.throws(() => parseWritePipelineDocument(duplicateTarget, PIPELINE_REF), /renderer .* must be unique/u);
});

test("the tracked Edition 004 write pipeline resolves its exact committed input graph", async () => {
  const revision = "rev_20260803T144015852Z_jddwkt2gxrf6" as RevisionId;
  const pipeline = await resolveWritePipeline(process.cwd(), { ...PIPELINE_REF, revisionId: revision }, {
    assertCommitted: async () => {},
  });
  assert.equal(pipeline.document.pipelineId, "edition4-write");
  assert.equal(pipeline.document.articles.length, 7);
  assert.equal(pipeline.document.images.length, 13);
  assert.equal(pipeline.document.rendererInputs.length, 4);
  assert.ok(pipeline.inputs.some((input) => input.ref.logicalId === "translation-es"));
});

test("prepared source inputs let the public RunEngine start the real-like write plan awaiting human review", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-write-source-plan-"));
  const revision = "rev_20260803T144015852Z_jddwkt2gxrf6" as RevisionId;
  try {
    const plan = await prepareWriteProduction(process.cwd(), { ...PIPELINE_REF, revisionId: revision }, {
      assertCommitted: async () => {},
    });
    for (const source of plan.spec.edition.sources) {
      assert.ok(source.rawBundleArtifact);
      assert.equal(source.rawEvidenceArtifacts?.length, 1);
      assert.ok(source.extractionArtifact);
      assert.ok(source.metadataArtifact);
      assert.equal(source.approvalArtifact, undefined);
    }
    const renderProfile = plan.spec.artifacts.find((artifact) => artifact.kind === "render_profile_template");
    assert.ok(renderProfile && renderProfile.payload.kind === "json");
    const inputs = (renderProfile.payload.value as { inputs: Array<{ targetPath: string }> }).inputs;
    const targets = new Set(inputs.map((input) => input.targetPath));
    assert.equal(targets.has("editions/004-the-systems-around-the-model/translations/es/edition.yaml"), false);
    assert.equal(targets.has("editions/004-the-systems-around-the-model/translations/es/edition.template.yaml"), true);
    assert.equal(targets.has("design/covers/canto-vivo/design.toml"), true);
    for (const source of plan.pipeline.document.sources) {
      assert.equal(targets.has(`library/sources/${source.sourceId}/record.yaml`), true);
      assert.equal(targets.has(`library/sources/${source.sourceId}/extracted.md`), true);
      assert.equal(
        [...targets].some((target) => target.startsWith(`library/sources/${source.sourceId}/raw/`)),
        true,
      );
    }
    const engine = new SqliteRunEngine({
      databasePath: join(temporary, "run.sqlite"),
      artifactDirectory: join(temporary, "artifacts"),
    });
    try {
      const started = await engine.start(plan.spec);
      assert.ok(started.runId);
      const view = await engine.inspect(started.runId);
      const reviews = view.offers.filter((offer) =>
        offer.role === "review_source" && offer.status === "offered"
      );
      assert.equal(reviews.length, plan.pipeline.document.sources.length);
      assert.ok(reviews.every((offer) =>
        offer.allowedWorkerCapabilities.includes("human") &&
        offer.allowedWorkerCapabilities.includes("source_access")
      ));
    } finally {
      engine.close();
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("a synthetic human source approval seed cannot bypass the live review-source offer", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-write-source-bypass-"));
  const revision = "rev_20260803T144015852Z_jddwkt2gxrf6" as RevisionId;
  try {
    const plan = await prepareWriteProduction(process.cwd(), { ...PIPELINE_REF, revisionId: revision }, {
      assertCommitted: async () => {},
    });
    const source = plan.spec.edition.sources[0];
    assert.ok(source?.rawBundleArtifact);
    assert.ok(source?.extractionArtifact);
    const fakeApproval = "art_fake_human_source_approval" as never;
    const malicious = {
      ...plan.spec,
      artifacts: [
        ...plan.spec.artifacts,
        {
          id: fakeApproval,
          kind: "source_review_decision",
          schemaVersion: "review-source/1",
          mediaType: "application/json",
          origin: "human" as const,
          payload: { kind: "json" as const, value: { decision: "approved" } },
          parents: [
            { artifactId: source.rawBundleArtifact, relation: "reviewed_raw_bundle" },
            { artifactId: source.extractionArtifact, relation: "reviewed_extraction" },
          ],
        },
      ],
      edition: {
        ...plan.spec.edition,
        sources: plan.spec.edition.sources.map((candidate) =>
          candidate.sourceId === source.sourceId
            ? { ...candidate, approvalArtifact: fakeApproval }
            : candidate),
      },
    };
    const engine = new SqliteRunEngine({
      databasePath: join(temporary, "run.sqlite"),
      artifactDirectory: join(temporary, "artifacts"),
    });
    try {
      const started = await engine.start(malicious);
      const view = await engine.inspect(started.runId);
      const review = view.offers.find((offer) =>
        offer.role === "review_source" && offer.actorKey === `source:${source.sourceId}`
      );
      assert.equal(review?.status, "offered");
      assert.equal(
        view.actors.find((actor) => actor.logicalKey === `source:${source.sourceId}`)?.state,
        "awaiting_source_review",
      );
      assert.equal(view.decisions.some((decision) => decision.artifactId === fakeApproval), false);
    } finally {
      engine.close();
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

function fixture(): any {
  const input = (kind: string, logicalId: string, edition = false) => ({
    kind,
    logical_id: logicalId,
    revision_id: REVISION,
    ...(edition ? { edition_id: "004" } : {}),
  });
  const article = (articleId: string, sourceId: string) => ({
    article_id: articleId,
    content_mode: "faithful_synthesis",
    byline: "Source Author",
    source_ids: [sourceId],
    source_authors: ["Source Author"],
    brief: `Write ${articleId} from its complete source extraction.`,
    writer_prompt: input("prompt", "faithful-synthesis"),
    judge_prompts: { evidence: input("prompt", "evidence-review") },
    input_revisions: [input("policy", "writing-rules")],
    parent: durable("article", articleId, "en"),
    maximum_reader_pages: 7,
    max_iterations: 3,
    model_policy: terra(),
  });
  const articleIds = ["frontier", "eval", "pragmatic", "kimi", "factory", "nutshell", "update"];
  return {
    schema_version: 1,
    edition_id: "004",
    pipeline_id: "edition4-write",
    edition_spec: input("edition_spec", "main", true),
    sources: articleIds.map((sourceId) => ({
      source_id: sourceId,
      capture: input("source_capture", sourceId),
      extraction: input("source_extraction", sourceId),
    })),
    articles: articleIds.map((articleId) => article(articleId, articleId)),
    editorial: {
      editorial_id: "opening",
      brief: "Find the edition's unifying argument.",
      writer_prompt: input("prompt", "opening-editorial"),
      input_revisions: [input("policy", "writing-rules")],
      parent: durable("editorial", "opening", "en"),
      maximum_reader_pages: 1,
      model_policy: terra(),
    },
    translations: [{
      language: "es",
      source_language: "en",
      prompt: input("prompt", "translation-es"),
      input_revisions: [input("policy", "writing-rules")],
      parents: Object.fromEntries([...articleIds, "opening"].map((pieceId) => [
        pieceId,
        durable(pieceId === "opening" ? "editorial" : "article", pieceId, "es"),
      ])),
      maximum_reader_pages: 7,
      model_policy: terra(),
    }],
    images: Array.from({ length: 13 }, (_, index) => durable("image", `image-${index}`)),
    layout_inputs: [input("edition_spec", "main", true)],
    renderer_inputs: [
      {
        input: input("edition_spec", "main", true),
        payload_path: "edition.yaml",
        renderer_target_path: "editions/004-the-systems-around-the-model/edition.yaml",
      },
      {
        input: input("policy", "writing-rules"),
        payload_path: "policy.md",
        renderer_target_path: "editions/004-the-systems-around-the-model/design/writing-rules.md",
      },
    ],
    render: {
      primary_language: "en",
      publication_name: "Berreta Futura",
      renderer: "weasyprint",
      configured_languages: ["en", "es"],
      studio_policy: "home_ready_studio_blocked",
    },
  };
}

function durable(kind: "article" | "editorial" | "image", logicalId: string, language?: string) {
  return {
    kind,
    edition_id: "004",
    logical_id: logicalId,
    ...(language === undefined ? {} : { language }),
    revision_id: REVISION,
  };
}

function terra() {
  return { default: { adapter: "cooperative", model: "gpt-5.6-terra", reasoning_effort: "high" } };
}
