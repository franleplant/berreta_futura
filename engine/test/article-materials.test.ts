import assert from "node:assert/strict";
import { describe, test } from "node:test";

import type { ArtifactId } from "../contracts/index.ts";
import type {
  ResolvedArticleProductionProfile,
  ResolvedReviewPlan,
} from "../contracts/production-plan.ts";
import type { MaterializedWritePipelineInput } from "../durable/write-pipeline.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  articleMaterialContextFromLoops,
  assertMaterialAccess,
  assertPrincipalExposureIsolated,
  selectArticleMaterialSets,
  selectArticleReviewerMaterials,
  selectArticleWriterMaterials,
  SourceExposureConflictError,
  SourceIsolationError,
  type ArticleMaterialContext,
} from "../article-production/materials.ts";

const id = (value: string): ArtifactId => value as ArtifactId;
const revision = (kind: InputRevisionRef["kind"], logicalId: string): InputRevisionRef => ({
  kind,
  logicalId,
  revisionId: `rev-${logicalId}` as never,
} as InputRevisionRef);

function materialized(
  ref: InputRevisionRef,
  artifactId: ArtifactId,
  path = pathFor(ref.kind),
): MaterializedWritePipelineInput {
  return { ref, artifacts: [{ path, artifactId }] };
}

function pathFor(kind: InputRevisionRef["kind"]): string {
  switch (kind) {
    case "source_extraction": return "extracted.md";
    case "prompt": return "prompt.md";
    case "policy": return "policy.md";
    case "article_production_profile": return "profile.json";
    case "article_review_plan": return "review-plan.json";
    case "review_material_schema": return "schema.json";
    default: return "payload";
  }
}

function profile(): ResolvedArticleProductionProfile {
  return {
    schemaVersion: "resolved-article-production-profile/1",
    profileId: "profile",
    formatId: "format",
    profileArtifactId: id("profile-artifact"),
    writerPromptArtifactId: id("writer-prompt"),
    writerResultContractVersion: "article-writer-result/1",
    reviewMaterials: [{
      materialId: "claim-map",
      schemaArtifactId: id("claim-schema"),
      schemaVersion: "claim-map/1",
      required: true,
    }],
    reviewPlanArtifactId: id("review-plan"),
    writingRulesArtifactId: id("writing-rules"),
    writingPolicyArtifactIds: [id("writing-policy")],
    maximumRewrites: 2,
  };
}

function plan(): ResolvedReviewPlan {
  return {
    schemaVersion: "resolved-article-review-plan/1",
    reviewPlanArtifactId: id("review-plan"),
    checks: [
      {
        kind: "model_review",
        id: "evidence",
        role: "article_review",
        promptArtifactId: id("evidence-prompt"),
        access: "source_aware",
        authority: "blocking",
        writerMaterialIds: ["claim-map"],
      },
      {
        kind: "model_review",
        id: "craft",
        role: "article_review",
        promptArtifactId: id("craft-prompt"),
        access: "source_blind",
        authority: "advisory",
      },
      {
        kind: "article_measurement",
        id: "measure_article",
        role: "measure_article",
        measurementProfileArtifactId: id("measurement-profile"),
        maximumReaderPages: 7,
      },
    ],
    waves: [{ id: "all", checkIds: ["evidence", "craft", "measure_article"], stopAfter: "never" }],
  };
}

function context(): ArticleMaterialContext {
  const source = revision("source_extraction", "source-one");
  const writingRules = revision("policy", "writing-rules");
  const input = articleMaterialContextFromLoops({
    schemaVersion: "loops-article-entry-input/1",
    articleId: "article-one",
    contentMode: "faithful_synthesis",
    byline: "Source Author",
    sourceIds: ["source-one"],
    sourceAuthors: ["Source Author"],
    brief: "brief",
    maximumReaderPages: 7,
    modelPolicy: { default: { adapter: "test", model: "deterministic" } },
    productionProfile: profile(),
    writingRulesArtifactId: id("writing-rules"),
    reviewPlan: plan(),
    materializedInputs: [
      materialized(source, id("source-extraction")),
      materialized(writingRules, id("writing-rules")),
    ],
    inputBindings: [],
  }, {
    articleBriefArtifactId: id("brief"),
    editionContextArtifactId: id("edition"),
    writerReviewMaterialArtifacts: { "claim-map": id("claim-map-v1") },
  });
  return {
    ...input,
    materializedInputs: [
      ...input.materializedInputs,
      materialized(revision("policy", "writing-policy"), id("writing-policy")),
    ],
  };
}

describe("article material policy", () => {
  test("writer receives exact profile, source, and revision material order", () => {
    const selected = selectArticleWriterMaterials(context(), {
      manuscriptArtifactId: id("manuscript-v1"),
      findingArtifacts: [id("finding-1")],
      rulingArtifacts: [id("ruling-1")],
      workingNotesArtifact: id("notes-v1"),
    });

    assert.deepEqual(selected.artifactIds, [
      id("writer-prompt"),
      id("profile-artifact"),
      id("review-plan"),
      id("writing-policy"),
      id("claim-schema"),
      id("writing-rules"),
      id("brief"),
      id("edition"),
      id("source-extraction"),
      id("manuscript-v1"),
      id("finding-1"),
      id("ruling-1"),
      id("notes-v1"),
      id("claim-map-v1"),
    ]);
    assert.equal(selected.access, "source_aware");
  });

  test("source-aware and source-blind checks receive distinct exact sets", () => {
    const article = context();
    const manuscript = id("manuscript-v1");
    const evidenceCheck = article.reviewPlan.checks.find((check) => check.id === "evidence");
    const craftCheck = article.reviewPlan.checks.find((check) => check.id === "craft");
    assert.ok(evidenceCheck?.kind === "model_review");
    assert.ok(craftCheck?.kind === "model_review");
    const evidence = selectArticleReviewerMaterials(article, evidenceCheck, manuscript);
    const craft = selectArticleReviewerMaterials(article, craftCheck, manuscript);

    assert.deepEqual(evidence.artifactIds, [
      id("evidence-prompt"),
      manuscript,
      id("writing-rules"),
      id("brief"),
      id("edition"),
      id("source-extraction"),
      id("claim-map-v1"),
    ]);
    assert.deepEqual(craft.artifactIds, [
      id("craft-prompt"),
      manuscript,
      id("writing-rules"),
    ]);
    assert.equal(craft.artifacts.some((artifact) => artifact.classification === "source"), false);
  });

  test("material-set expansion covers only applicable checks and enforces writer material at review selection", () => {
    const article = context();
    const sets = selectArticleMaterialSets(article, id("manuscript-v1"));
    assert.deepEqual(sets.reviews.map((review) => review.checkId), [
      "evidence",
      "craft",
      "measure_article",
    ]);

    const missing = {
      ...article,
      writerReviewMaterialArtifacts: {},
    };
    const evidenceCheck = article.reviewPlan.checks.find((check) => check.id === "evidence");
    assert.ok(evidenceCheck?.kind === "model_review");
    assert.throws(
      () => selectArticleReviewerMaterials(missing, evidenceCheck, id("manuscript-v1")),
      /requests writer material claim-map/u,
    );
    assert.deepEqual(selectArticleWriterMaterials(missing).artifactIds, [
      id("writer-prompt"),
      id("profile-artifact"),
      id("review-plan"),
      id("writing-policy"),
      id("claim-schema"),
      id("writing-rules"),
      id("brief"),
      id("edition"),
      id("source-extraction"),
    ]);
  });

  test("writer review materials follow the profile order and reject undeclared IDs", () => {
    const article = context();
    const productionProfile = {
      ...article.productionProfile,
      reviewMaterials: [
        ...article.productionProfile.reviewMaterials,
        {
          materialId: "writer-notes",
          schemaArtifactId: id("writer-notes-schema"),
          schemaVersion: "writer-notes/1",
          required: false,
        },
      ],
    };
    const reordered = selectArticleWriterMaterials({
      ...article,
      productionProfile,
      writerReviewMaterialArtifacts: {
        "writer-notes": id("writer-notes-v1"),
        "claim-map": id("claim-map-v1"),
      },
    });
    assert.deepEqual(reordered.artifactIds.slice(-2), [id("claim-map-v1"), id("writer-notes-v1")]);

    assert.throws(
      () => selectArticleWriterMaterials({
        ...article,
        writerReviewMaterialArtifacts: {
          "claim-map": id("claim-map-v1"),
          extra: id("extra-v1"),
        },
      }),
      /writer review material extra is not declared/u,
    );
    const withoutMaterials = selectArticleWriterMaterials({
      ...article,
      writerReviewMaterialArtifacts: {},
    });
    assert.equal(
      withoutMaterials.artifacts.some((artifact) => artifact.classification === "writer_review_material"),
      false,
    );
  });

  test("initial writer selection succeeds without prior revision materials", () => {
    const article = context();
    const { writerReviewMaterialArtifacts: _priorMaterials, ...withoutPrior } = article;
    const selected = selectArticleWriterMaterials(withoutPrior);

    assert.equal(
      selected.artifacts.some((artifact) => artifact.classification === "writer_review_material"),
      false,
    );
  });

  test("writer rules must be the exact profile-bound artifact", () => {
    const article = context();
    assert.throws(
      () => selectArticleWriterMaterials({ ...article, writingRulesArtifactId: id("other-rules") }),
      /writing-rules artifact does not match/u,
    );
    assert.throws(
      () => selectArticleWriterMaterials({ ...article, writingRulesArtifactId: undefined as never }),
      /writing-rules artifact does not match/u,
    );
  });

  test("source-blind checks reject writer material even when bypassing the parsed plan", () => {
    const article = context();
    const check = {
      kind: "model_review" as const,
      id: "craft",
      role: "article_review" as const,
      promptArtifactId: id("craft-prompt"),
      access: "source_blind" as const,
      authority: "advisory" as const,
      writerMaterialIds: ["claim-map"],
    };
    assert.throws(
      () => selectArticleReviewerMaterials(article, check, id("manuscript-v1")),
      /source-blind review check craft cannot request writer material/u,
    );
  });

  test("source-blind policy fails closed for a source artifact", () => {
    assert.throws(
      () => assertMaterialAccess("source_blind", [{
        articleId: "article-one",
        artifactId: id("source-leak"),
        classification: "source",
      }], "craft"),
      SourceIsolationError,
    );
  });

  test("one principal cannot cross source exposure for one manuscript", () => {
    assert.throws(
      () => assertPrincipalExposureIsolated([
        {
          principalId: "reviewer",
          manuscriptArtifactId: id("manuscript-v1"),
          access: "source_blind",
        },
      ], {
        principalId: "reviewer",
        manuscriptArtifactId: id("manuscript-v1"),
        access: "source_aware",
      }),
      SourceExposureConflictError,
    );
  });
});
