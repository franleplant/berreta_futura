import assert from "node:assert/strict";

import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  EditionRootRunSpec,
  SubmitLeadRequest,
  WorkOfferView,
} from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/types.ts";

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(artifactId: ArtifactId, kind: string): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "article-lab-source-prep/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: artifactId },
  };
}

function emptyCollection(prefix: string): EditionRootRunSpec {
  const editionBrief = id(`${prefix}-edition-brief`);
  const editorialBrief = id(`${prefix}-editorial-brief`);
  const writingRules = id(`${prefix}-writing-rules`);
  const renderManifest = id(`${prefix}-render-manifest`);
  const publication = id(`${prefix}-publication`);
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts: [
      seed(editionBrief, "edition_brief"),
      seed(editorialBrief, "editorial_brief"),
      seed(writingRules, "writing_rules"),
      seed(renderManifest, "render_profile"),
      seed(publication, "release_placeholder"),
    ],
    edition: {
      editionId: `${prefix}-edition`,
      execution: { kind: "produce" },
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
        renderManifestArtifact: renderManifest,
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

function offered(view: Awaited<ReturnType<RunEngine["inspect"]>>): WorkOfferView {
  const offer = view.offers.find(
    (candidate) => candidate.role === "review_source" && candidate.status === "offered",
  );
  assert.ok(offer, "prepared source did not offer a human source review");
  return offer;
}

/**
 * Materializes a fixture source through the public collection and answer APIs.
 * The returned article spec reuses the committed extraction and human decision,
 * so standalone article starts cannot bypass source authority.
 */
export async function prepareArticleSources(
  engine: RunEngine,
  spec: ArticleRootRunSpec,
  prefix: string,
): Promise<ArticleRootRunSpec> {
  const approvals: ArtifactId[] = [];
  const rewritten = [...spec.artifacts];
  for (const [index, extraction] of spec.article.sources.entries()) {
    const sourceSeed = rewritten.find((candidate) => candidate.id === extraction);
    assert.ok(sourceSeed, `article source ${extraction} must be seeded for fixture preparation`);
    const token = `${prefix}-${index}`;
    const lead = id(`${token}-lead`);
    const rawBundle = id(`${token}-raw-bundle`);
    const rawEvidence = id(`${token}-raw-evidence`);
    const metadata = id(`${token}-metadata`);
    const decision = id(`${token}-source-review`);
    const extractionSeed: ArtifactSeed = {
      ...sourceSeed,
      kind: "source_extraction",
      parents: [{ artifactId: rawEvidence, relation: "extracted_from" }],
    };
    const request: SubmitLeadRequest = {
      source: {
        sourceId: `${token}-source`,
        leadArtifact: lead,
        rawBundleArtifact: rawBundle,
        rawEvidenceArtifacts: [rawEvidence],
        extractionArtifact: extraction,
        metadataArtifact: metadata,
      },
      artifacts: [
        seed(lead, "submitted_lead"),
        { ...seed(rawBundle, "raw_source_bundle"), parents: [{ artifactId: lead, relation: "captured_from_lead" }] },
        { ...seed(rawEvidence, "raw_evidence"), parents: [{ artifactId: rawBundle, relation: "bundle_content" }] },
        extractionSeed,
        { ...seed(metadata, "source_metadata"), parents: [{ artifactId: rawBundle, relation: "describes_bundle" }] },
      ],
    };
    const collection = await engine.start(emptyCollection(`${token}-collection`));
    const submitted = await engine.submitLead(collection.runId, request);
    const review = offered(submitted);
    const claim = await engine.claim(review.id, {
      principalId: `${token}-source-editor`,
      authority: "human",
      capabilities: ["human", "source_access"],
    });
    await engine.answer(claim, {
      contractVersion: review.contractVersion,
      result: { decision: "approved" },
      artifacts: [{
        id: decision,
        kind: "source_review_decision",
        schemaVersion: "review-source/1",
        mediaType: "application/json",
        payload: { kind: "json", value: { decision: "approved" } },
      } satisfies AnswerArtifact],
    });
    const sourceIndex = rewritten.findIndex((candidate) => candidate.id === extraction);
    rewritten[sourceIndex] = extractionSeed;
    approvals.push(decision);
  }
  return {
    ...spec,
    artifacts: rewritten,
    article: { ...spec.article, sourceApprovalArtifacts: approvals },
  };
}
