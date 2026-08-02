import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type {
  ArtifactId,
  ArtifactSeed,
  EditionRootRunSpec,
} from "../contracts/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(value: ArtifactId): ArtifactSeed {
  return {
    id: value,
    kind: "fixture",
    schemaVersion: "fixture/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: `fixture ${value}` },
  };
}

function editionSpec(): EditionRootRunSpec {
  const editionBrief = id("edition-brief");
  const lead = id("source-lead");
  const editorialBrief = id("editorial-brief");
  const writingRules = id("writing-rules");
  const renderProfile = id("render-profile");
  const publication = id("publication");
  const artifacts = [
    editionBrief,
    lead,
    editorialBrief,
    writingRules,
    renderProfile,
    publication,
  ].map(seed);
  return {
    schemaVersion: 1,
    kind: "edition",
    artifacts,
    edition: {
      editionId: "retry-fixture",
      editionBrief,
      sources: [{ sourceId: "source-one", leadArtifact: lead }],
      articles: [],
      editorial: {
        editorialId: "opening",
        briefArtifact: editorialBrief,
        writingRules,
        modelPolicy: { default: { adapter: "test", model: "test" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: renderProfile,
        rendererContractVersion: "renderer/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: publication,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
}

test("durably retries a stranded child state and reactivates the actor", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-retry-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "run.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  try {
    const started = await engine.start(editionSpec());
    let view = await engine.inspect(started.runId);
    const capture = view.offers.find(
      (offer) => offer.role === "capture_source" && offer.status === "offered",
    );
    assert.ok(capture);
    const claim = await engine.claim(capture.id, {
      principalId: "capture-tool",
      authority: "tool",
      capabilities: ["source_access", "subprocess"],
    });
    view = await engine.fail(claim, {
      classification: "retryable",
      message: "temporary capture failure",
    });
    const source = view.actors.find((actor) => actor.logicalKey === "source:source-one");
    assert.ok(source);
    assert.equal(source.state, "capture_failed");
    assert.equal(source.status, "active");

    await engine.retry(view.id, source.id);
    view = await engine.inspect(view.id);
    const retried = view.offers.filter(
      (offer) => offer.role === "capture_source" && offer.status === "offered",
    );
    assert.equal(retried.length, 1);
    assert.notEqual(retried[0]?.id, capture.id);
    assert.equal(
      view.actors.find((actor) => actor.id === source.id)?.state,
      "capturing",
    );

    await assert.rejects(
      engine.retry(view.id, source.id),
      (error: unknown) =>
        error instanceof Error &&
        "code" in error &&
        error.code === "ACTOR_NOT_RETRYABLE",
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
