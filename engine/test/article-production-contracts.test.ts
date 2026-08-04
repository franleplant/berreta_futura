import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";

import { stringify } from "yaml";

import {
  parseArticleProductionProfileDocument,
  parseArticleReviewPlanDocument,
  parseResolvedArticleProductionProfile,
  parseResolvedReviewPlan,
} from "../contracts/production-plan.ts";
import {
  materializeWritePipelineInputs,
  resolveWritePipeline,
  resolveProfileBackedArticleInput,
  type ResolvedWritePipeline,
  type WritePipelineArticle,
} from "../durable/write-pipeline.ts";
import { inputRevisionRelativeDirectory } from "../durable/paths.ts";

const revision = (kind: string, logicalId: string) => ({
  kind,
  logical_id: logicalId,
  revision_id: "rev_20260803T000000000Z_aaaaaaaaaaaa",
});

test("article production profiles normalize immutable revision references", () => {
  const profile = parseArticleProductionProfileDocument({
    schema_version: "article-production-profile/1",
    profile_id: "source-faithful",
    format_id: "longform",
    writer: {
      prompt_revision: revision("prompt", "writer"),
      result_contract_version: "article-writer-result/1",
      review_materials: [{
        material_id: "claim-map",
        schema_revision: revision("review_material_schema", "claim-map"),
        required: true,
      }],
    },
    review_plan_revision: revision("article_review_plan", "source-faithful-reviews"),
    writing_policy_revisions: [revision("policy", "writing-rules")],
    revision_policy: { maximum_rewrites: 2 },
  });
  assert.equal(profile.profileId, "source-faithful");
  assert.equal(profile.writer.promptRevision.kind, "prompt");
  assert.equal(profile.writer.reviewMaterials[0]?.schemaRevision.kind, "review_material_schema");
  assert.equal(profile.revisionPolicy.maximumRewrites, 2);
});

test("review plans reject duplicate checks and normalize wave membership", () => {
  const plan = parseArticleReviewPlanDocument({
    schema_version: "article-review-plan/1",
    checks: [
      {
        kind: "model_review",
        id: "evidence",
        role: "article_review",
        prompt_revision: revision("prompt", "evidence-review"),
        access: "source_aware",
        authority: "blocking",
      },
      {
        kind: "article_measurement",
        id: "measure_article",
        role: "measure_article",
        measurement_profile_revision: revision("policy", "article-measurement"),
        maximum_reader_pages: 7,
      },
    ],
    waves: [{ id: "panel", check_ids: ["evidence", "measure_article"], stop_after: "never" }],
  });
  assert.deepEqual(plan.waves[0]?.checkIds, ["evidence", "measure_article"]);
  assert.equal(plan.checks[0]?.kind, "model_review");
  assert.equal(plan.checks[1]?.kind, "article_measurement");
  assert.throws(() => parseArticleReviewPlanDocument({
    schema_version: "article-review-plan/1",
    checks: [
      {
        kind: "model_review",
        id: "evidence",
        role: "article_review",
        prompt_revision: revision("prompt", "evidence-review"),
        access: "source_aware",
        authority: "blocking",
      },
      {
        kind: "model_review",
        id: "evidence",
        role: "article_review",
        prompt_revision: revision("prompt", "evidence-review"),
        access: "source_aware",
        authority: "blocking",
      },
    ],
    waves: [{ id: "panel", check_ids: ["evidence"], stop_after: "never" }],
  }), /review check IDs must be unique/u);

  assert.throws(() => parseArticleReviewPlanDocument({
    schema_version: "article-review-plan/1",
    checks: [{
      kind: "article_measurement",
      id: "measure_article",
      role: "measure_article",
      measurement_profile_revision: revision("prompt", "not-a-measurement-profile"),
      maximum_reader_pages: 7,
    }],
    waves: [{ id: "panel", check_ids: ["measure_article"], stop_after: "never" }],
  }), /expected policy input revision/u);
});

test("resolved profile and plan contracts contain artifact identities only", () => {
  const profile = parseResolvedArticleProductionProfile({
    schema_version: "resolved-article-production-profile/1",
    profile_id: "source-faithful",
    format_id: "longform",
    profile_artifact_id: "profile",
    writer_prompt_artifact_id: "prompt",
    writer_result_contract_version: "article-writer-result/1",
    review_materials: [{ material_id: "claim-map", schema_artifact_id: "schema", schema_version: "schema/1", required: true }],
    review_plan_artifact_id: "review-plan",
    writing_policy_artifact_ids: ["writing-rules"],
    maximum_rewrites: 2,
  });
  assert.equal(profile.writerPromptArtifactId, "prompt");
  const plan = parseResolvedReviewPlan({
    schema_version: "resolved-article-review-plan/1",
    review_plan_artifact_id: "review-plan",
    checks: [{
      kind: "model_review",
      id: "evidence",
      role: "article_review",
      prompt_artifact_id: "prompt",
      access: "source_aware",
      authority: "blocking",
    }],
    waves: [{ id: "panel", check_ids: ["evidence"], stop_after: "never" }],
  });
  const first = plan.checks[0];
  assert.equal(first?.kind, "model_review");
  if (first?.kind === "model_review") assert.equal(first.promptArtifactId, "prompt");
});

test("the shared write-pipeline materializer binds exact input revisions once", () => {
  const profileRef = {
    kind: "article_production_profile" as const,
    logicalId: "source-faithful",
    revisionId: "rev_20260803T000000000Z_aaaaaaaaaaaa" as never,
  };
  const materialized = materializeWritePipelineInputs({
    revision: { ref: { kind: "write_pipeline", editionId: "004", logicalId: "edition4-write", revisionId: profileRef.revisionId }, payloadPaths: { "production.yaml": "/tmp/production.yaml" } } as never,
    document: {} as never,
    inputs: [{
      ref: profileRef,
      payloadPaths: { "profile.json": "/tmp/profile.json" },
    }] as never,
  });
  const artifactId = materialized.inputArtifact(profileRef, "profile.json");
  assert.equal(materialized.artifacts.length, 1);
  assert.equal(materialized.artifacts[0]?.id, artifactId);
  assert.deepEqual(materialized.artifacts[0]?.metadata?.inputRevision, profileRef);
  assert.throws(() => materialized.inputArtifact(profileRef, "missing.json"), /did not import/u);
});

test("profile-backed Loops input authenticates nested prompt and measurement revisions", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-profile-input-"));
  try {
    const refs = {
      profile: { kind: "article_production_profile" as const, logicalId: "source-faithful", revisionId: revisionId("profile") },
      plan: { kind: "article_review_plan" as const, logicalId: "source-faithful-reviews", revisionId: revisionId("plan") },
      writer: { kind: "prompt" as const, logicalId: "writer", revisionId: revisionId("writer") },
      evidence: { kind: "prompt" as const, logicalId: "evidence-review", revisionId: revisionId("evidence") },
      policy: { kind: "policy" as const, logicalId: "writing-rules", revisionId: revisionId("policy") },
      measurement: { kind: "policy" as const, logicalId: "article-measurement", revisionId: revisionId("measurement") },
      schema: { kind: "review_material_schema" as const, logicalId: "claim-map", revisionId: revisionId("schema") },
      capture: { kind: "source_capture" as const, logicalId: "source", revisionId: revisionId("capture") },
      extraction: { kind: "source_extraction" as const, logicalId: "source", revisionId: revisionId("extraction") },
    };
    const paths = new Map<string, Readonly<Record<string, string>>>();
    const payload = async (key: string, name: string, value: string): Promise<void> => {
      const path = join(root, key.replace(/[^A-Za-z0-9_-]/gu, "_"), name);
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, value, "utf8");
      paths.set(key, { ...(paths.get(key) ?? {}), [name]: path });
    };
    await payload("profile", "profile.json", JSON.stringify({
      schema_version: "article-production-profile/1",
      profile_id: "source-faithful",
      format_id: "longform",
      writer: {
        prompt_revision: rawRef(refs.writer),
        result_contract_version: "article-writer-result/1",
        review_materials: [{ material_id: "claim-map", schema_revision: rawRef(refs.schema), required: true }],
      },
      review_plan_revision: rawRef(refs.plan),
      writing_policy_revisions: [rawRef(refs.policy)],
      revision_policy: { maximum_rewrites: 2 },
    }));
    const planValue = {
      schema_version: "article-review-plan/1",
      checks: [
        {
          kind: "model_review",
          id: "evidence",
          role: "article_review",
          prompt_revision: rawRef(refs.evidence),
          access: "source_aware",
          authority: "blocking",
          writer_material_ids: ["claim-map"],
        },
        {
          kind: "article_measurement",
          id: "measure_article",
          role: "measure_article",
          measurement_profile_revision: rawRef(refs.measurement),
          maximum_reader_pages: 7,
        },
      ],
      waves: [{ id: "panel", check_ids: ["evidence", "measure_article"], stop_after: "never" }],
    };
    await payload("plan", "review-plan.json", JSON.stringify(planValue));
    await payload("schema", "schema.json", JSON.stringify({ schema_version: "claim-map/1", type: "object" }));
    await payload("writer", "prompt.md", "Write the article.");
    await payload("evidence", "prompt.md", "Check evidence.");
    await payload("policy", "policy.md", "Writing rules.");
    await payload("measurement", "policy.md", "Measurement profile.");
    await payload("capture", "raw/record.yaml", "source: source\n");
    await payload("extraction", "extracted.md", "Source extraction.\n");

    const inputKeys = new Map([
      ["article_production_profile:source-faithful", "profile"],
      ["article_review_plan:source-faithful-reviews", "plan"],
      ["prompt:writer", "writer"],
      ["prompt:evidence-review", "evidence"],
      ["policy:writing-rules", "policy"],
      ["policy:article-measurement", "measurement"],
      ["review_material_schema:claim-map", "schema"],
      ["source_capture:source", "capture"],
      ["source_extraction:source", "extraction"],
    ]);
    const input = (ref: typeof refs[keyof typeof refs]) => ({
      ref,
      manifest: {} as never,
      manifestDigest: "sha256:test",
      relativeDirectory: "inputs/test",
      absoluteDirectory: root,
      repositoryPaths: [],
      payloadPaths: paths.get(inputKeys.get(`${ref.kind}:${ref.logicalId}`) ?? "") ?? {},
    });
    const article: WritePipelineArticle = {
      articleId: "article",
      contentMode: "faithful_synthesis",
      byline: "Source Author",
      sourceIds: ["source"],
      sourceAuthors: ["Source Author"],
      brief: "Write from the complete extraction.",
      productionProfileRevision: refs.profile,
      parent: null,
      maximumReaderPages: 7,
      modelPolicy: { default: { adapter: "test", model: "test" } },
    };
    const pipeline = {
      revision: input({ kind: "write_pipeline", logicalId: "pipeline", revisionId: revisionId("pipeline"), editionId: "004" } as never),
      document: {
        schemaVersion: 1,
        editionId: "004",
        pipelineId: "pipeline",
        editionSpec: { kind: "edition_spec", logicalId: "edition", revisionId: revisionId("edition"), editionId: "004" },
        sources: [{ sourceId: "source", capture: refs.capture, extraction: refs.extraction }],
        articles: [article],
        editorial: {} as never,
        translations: [],
        images: [],
        layoutInputs: [],
        rendererInputs: [],
        render: { primaryLanguage: "en", publicationName: "Test", renderer: "reportlab", configuredLanguages: ["en"], studioPolicy: "not_applicable" },
      },
      inputs: [refs.profile, refs.plan, refs.writer, refs.evidence, refs.policy, refs.measurement, refs.schema, refs.capture, refs.extraction]
        .map(input) as never,
    } satisfies ResolvedWritePipeline;
    const materialized = materializeWritePipelineInputs(pipeline);
    const resolved = await resolveProfileBackedArticleInput(materialized, article);
    assert.equal(resolved.loopsInput.schemaVersion, "loops-article-entry-input/1");
    assert.equal(resolved.productionProfile.writerPromptArtifactId, materialized.inputArtifact(refs.writer, "prompt.md"));
    const measurementCheck = resolved.reviewPlan.checks.find((check) => check.id === "measure_article");
    assert.equal(measurementCheck?.kind, "article_measurement");
    if (measurementCheck?.kind === "article_measurement") {
      assert.equal(measurementCheck.measurementProfileArtifactId, materialized.inputArtifact(refs.measurement, "policy.md"));
    }
    assert.ok(resolved.loopsInput.inputBindings.every((binding) => binding.artifactId.startsWith("art_write_")));

    await writeFile(join(root, "plan", "review-plan.json"), JSON.stringify({
      ...planValue,
      checks: planValue.checks.map((check) => check.id === "evidence" ? { ...check, writer_material_ids: ["missing"] } : check),
    }), "utf8");
    await assert.rejects(
      resolveProfileBackedArticleInput(materialized, article),
      /undeclared writer material/u,
    );
    await writeFile(join(root, "plan", "review-plan.json"), JSON.stringify({
      ...planValue,
      checks: planValue.checks.map((check) => check.id === "evidence"
        ? { ...check, id: "facts", access: "source_blind" }
        : check),
      waves: [{ id: "panel", check_ids: ["facts", "measure_article"], stop_after: "never" }],
    }), "utf8");
    await assert.rejects(
      resolveProfileBackedArticleInput(materialized, article),
      /source-aware evidence review/u,
    );

    await writeFile(join(root, "plan", "review-plan.json"), JSON.stringify({
      ...planValue,
      checks: planValue.checks.map((check) => check.id === "evidence"
        ? { ...check, authority: "advisory" }
        : check),
    }), "utf8");
    await assert.rejects(
      resolveProfileBackedArticleInput(materialized, article),
      /source-aware evidence review/u,
    );

    await writeFile(join(root, "plan", "review-plan.json"), JSON.stringify({
      ...planValue,
      checks: planValue.checks.map((check) => check.id === "measure_article"
        ? { ...check, applicable_when: { kind: "content_mode", values: ["original_synthesis"] } }
        : check),
    }), "utf8");
    await assert.rejects(
      resolveProfileBackedArticleInput(materialized, article),
      /review plan must include measure_article/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("resolveWritePipeline authenticates and materializes a direct and nested article profile graph", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-write-pipeline-auth-"));
  const revisionId = revisionIdValue("pipeline");
  const refs = {
    pipeline: { kind: "write_pipeline", editionId: "004", logicalId: "pipeline", revisionId },
    edition: { kind: "edition_spec", editionId: "004", logicalId: "edition", revisionId },
    capture: { kind: "source_capture", logicalId: "source", revisionId },
    extraction: { kind: "source_extraction", logicalId: "source", revisionId },
    profile: { kind: "article_production_profile", logicalId: "source-faithful", revisionId },
    plan: { kind: "article_review_plan", logicalId: "source-faithful-reviews", revisionId },
    writer: { kind: "prompt", logicalId: "writer", revisionId },
    evidence: { kind: "prompt", logicalId: "evidence-review", revisionId },
    policy: { kind: "policy", logicalId: "writing-rules", revisionId },
    measurement: { kind: "policy", logicalId: "article-measurement", revisionId },
    schema: { kind: "review_material_schema", logicalId: "claim-map", revisionId },
  } as const;
  const asserted: string[][] = [];
  const git = { assertCommitted: async (paths: readonly string[]) => { asserted.push([...paths]); } };
  try {
    await writeInputRevision(root, refs.edition, { "edition.yaml": "edition: test\n" });
    await writeInputRevision(root, refs.capture, { "raw/record.yaml": "source: source\n" });
    await writeInputRevision(root, refs.extraction, { "extracted.md": "Complete source extraction.\n" });
    await writeInputRevision(root, refs.writer, { "prompt.md": "Write the article.\n", "output.schema.json": "{}\n" });
    await writeInputRevision(root, refs.evidence, { "prompt.md": "Check source evidence.\n", "output.schema.json": "{}\n" });
    await writeInputRevision(root, refs.policy, { "policy.md": "Writing rules.\n" });
    await writeInputRevision(root, refs.measurement, { "policy.md": "Article measurement profile.\n" });
    await writeInputRevision(root, refs.schema, { "schema.json": JSON.stringify({ schema_version: "claim-map/1" }) });
    await writeInputRevision(root, refs.plan, {
      "review-plan.json": JSON.stringify({
        schema_version: "article-review-plan/1",
        checks: [
          {
            kind: "model_review",
            id: "evidence",
            role: "article_review",
            prompt_revision: rawRef(refs.evidence),
            access: "source_aware",
            authority: "blocking",
            writer_material_ids: ["claim-map"],
          },
          {
            kind: "article_measurement",
            id: "measure_article",
            role: "measure_article",
            measurement_profile_revision: rawRef(refs.measurement),
            maximum_reader_pages: 7,
          },
        ],
        waves: [{ id: "panel", check_ids: ["evidence", "measure_article"], stop_after: "never" }],
      }),
    });
    await writeInputRevision(root, refs.profile, {
      "profile.json": JSON.stringify({
        schema_version: "article-production-profile/1",
        profile_id: "source-faithful",
        format_id: "longform",
        writer: {
          prompt_revision: rawRef(refs.writer),
          result_contract_version: "article-writer-result/1",
          review_materials: [{ material_id: "claim-map", schema_revision: rawRef(refs.schema), required: true }],
        },
        review_plan_revision: rawRef(refs.plan),
        writing_policy_revisions: [rawRef(refs.policy)],
        revision_policy: { maximum_rewrites: 2 },
      }),
    });

    const articleIds = ["article-one", "article-two", "article-three", "article-four", "article-five", "article-six", "article-seven"];
    const articleParent = (articleId: string, language: string) => ({
      kind: "article",
      edition_id: "004",
      logical_id: articleId,
      language,
      revision_id: revisionId,
    });
    const editorialParent = {
      kind: "editorial",
      edition_id: "004",
      logical_id: "opening",
      language: "en",
      revision_id: revisionId,
    };
    const pipelineDocument = {
      schema_version: 1,
      edition_id: "004",
      pipeline_id: "pipeline",
      edition_spec: rawRef(refs.edition),
      sources: [{ source_id: "source", capture: rawRef(refs.capture), extraction: rawRef(refs.extraction) }],
      articles: articleIds.map((articleId) => ({
        article_id: articleId,
        content_mode: "faithful_synthesis",
        byline: "Source Author",
        source_ids: ["source"],
        source_authors: ["Source Author"],
        brief: `Write ${articleId} from its complete extraction.`,
        production_profile_revision: rawRef(refs.profile),
        parent: articleParent(articleId, "en"),
        maximum_reader_pages: 7,
        model_policy: { default: { adapter: "test", model: "test" } },
      })),
      editorial: {
        editorial_id: "opening",
        brief: "Find the edition's unifying argument.",
        writer_prompt: rawRef(refs.writer),
        input_revisions: [rawRef(refs.policy)],
        parent: editorialParent,
        maximum_reader_pages: 1,
        model_policy: { default: { adapter: "test", model: "test" } },
      },
      translations: [{
        language: "es",
        source_language: "en",
        prompt: rawRef(refs.writer),
        input_revisions: [rawRef(refs.policy)],
        parents: Object.fromEntries([
          ...articleIds.map((articleId) => [articleId, articleParent(articleId, "es")]),
          ["opening", { ...editorialParent, language: "es" }],
        ]),
        maximum_reader_pages: 7,
        model_policy: { default: { adapter: "test", model: "test" } },
      }],
      images: Array.from({ length: 13 }, (_, index) => ({
        kind: "image",
        edition_id: "004",
        logical_id: `image-${index + 1}`,
        revision_id: revisionId,
      })),
      // Naming the nested plan here proves direct resolution is reused, not
      // skipped or resolved through an unauthenticated second path.
      layout_inputs: [rawRef(refs.edition), rawRef(refs.plan)],
      renderer_inputs: [
        {
          input: rawRef(refs.edition),
          payload_path: "edition.yaml",
          renderer_target_path: "editions/004-the-systems-around-the-model/edition.yaml",
        },
        {
          input: rawRef(refs.policy),
          payload_path: "policy.md",
          renderer_target_path: "editions/004-the-systems-around-the-model/design/writing-rules.md",
        },
      ],
      render: {
        primary_language: "en",
        publication_name: "Test",
        renderer: "reportlab",
        configured_languages: ["en", "es"],
        studio_policy: "not_applicable",
      },
    };
    await writeInputRevision(root, refs.pipeline, { "production.yaml": stringify(pipelineDocument, { lineWidth: 0 }) });

    const resolved = await resolveWritePipeline(root, refs.pipeline, git);
    const materialized = materializeWritePipelineInputs(resolved);
    const expectedNested = [refs.profile, refs.plan, refs.writer, refs.evidence, refs.measurement, refs.schema, refs.policy];
    for (const ref of expectedNested) {
      assert.ok(resolved.inputs.some((input) => sameRef(input.ref, ref)), `${ref.kind}:${ref.logicalId} was not resolved`);
      const materializedInput = materialized.materializedInputs.find((input) => sameRef(input.ref, ref));
      assert.ok(materializedInput && materializedInput.artifacts.length > 0, `${ref.kind}:${ref.logicalId} was not materialized`);
      const manifestPath = join("inputs", inputRevisionRelativeDirectory(ref), "manifest.yaml");
      assert.ok(asserted.some((paths) => paths.includes(manifestPath)), `${manifestPath} was not authenticated`);
    }
    const articleResolution = await resolveProfileBackedArticleInput(materialized, resolved.document.articles[0]!);
    const boundRevisions = new Set(articleResolution.loopsInput.inputBindings.map((binding) => `${binding.revision.kind}:${binding.revision.logicalId}`));
    for (const ref of [refs.capture, refs.extraction, ...expectedNested]) {
      assert.ok(boundRevisions.has(`${ref.kind}:${ref.logicalId}`), `${ref.kind}:${ref.logicalId} missing from Loops bindings`);
    }
    assert.equal(articleResolution.reviewPlan.checks.find((check) => check.id === "measure_article")?.kind, "article_measurement");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

function revisionId(label: string): never {
  return `rev_20260803T000000000Z_${label.padEnd(12, "a").slice(0, 12)}` as never;
}

function revisionIdValue(label: string): never {
  return `rev_20260803T000000000Z_${label.padEnd(12, "a").slice(0, 12)}` as never;
}

type TestInputRef = {
  readonly kind: string;
  readonly logicalId: string;
  readonly revisionId: string;
  readonly editionId?: string;
};

function rawRef(ref: TestInputRef): Record<string, string> {
  return {
    kind: ref.kind,
    logical_id: ref.logicalId,
    revision_id: ref.revisionId,
    ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }),
  };
}

function sameRef(left: TestInputRef, right: TestInputRef): boolean {
  return left.kind === right.kind && left.logicalId === right.logicalId && left.revisionId === right.revisionId &&
    left.editionId === right.editionId;
}

async function writeInputRevision(
  root: string,
  ref: TestInputRef,
  payloads: Readonly<Record<string, string>>,
): Promise<void> {
  const directory = join(root, "inputs", inputRevisionRelativeDirectory(ref as never));
  await mkdir(directory, { recursive: true });
  const files = [] as { path: string; media_type: string; sha256: string; size_bytes: number }[];
  for (const [path, value] of Object.entries(payloads)) {
    const bytes = Buffer.from(value, "utf8");
    await mkdir(dirname(join(directory, path)), { recursive: true });
    await writeFile(join(directory, path), bytes);
    files.push({
      path,
      media_type: path.endsWith(".json") ? "application/json" : path.endsWith(".yaml") ? "application/yaml" : "text/markdown",
      sha256: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
      size_bytes: bytes.byteLength,
    });
  }
  const manifest = {
    schema_version: 1,
    revision_kind: ref.kind,
    logical_id: ref.logicalId,
    ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }),
    revision_id: ref.revisionId,
    created_at: "2026-08-03T00:00:00.000Z",
    parent_revision_id: null,
    files,
  };
  await writeFile(join(directory, "manifest.yaml"), stringify(manifest, { lineWidth: 0 }));
}
