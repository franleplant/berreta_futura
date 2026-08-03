import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  editionInputRevisionReferences,
  parseRunSpec,
  RunSpecReferenceError,
  type ArticleRootRunSpec,
  type ArtifactId,
  type ArtifactSeed,
  type EditionRootRunSpec,
} from "../contracts/index.ts";
import { SqliteRunEngine } from "../run-engine/run-engine.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(artifactId: ArtifactId, kind: string): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "test/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text: artifactId },
  };
}

function articleSpec(): ArticleRootRunSpec {
  const source = id("strict-source");
  const evidence = id("strict-evidence-prompt");
  const brief = id("strict-brief");
  const writer = id("strict-writer");
  const rules = id("strict-rules");
  const manuscript = id("strict-manuscript");
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      seed(source, "source_extraction"),
      seed(evidence, "evidence_prompt"),
      seed(brief, "article_brief"),
      seed(writer, "writer_prompt"),
      seed(rules, "writing_rules"),
      seed(manuscript, "article_manuscript"),
    ],
    article: {
      articleId: "strict-article",
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine" },
      articleBrief: brief,
      sources: [source],
      sourceApprovalArtifacts: [],
      writerPrompt: writer,
      judgePrompts: { evidence },
      writingRules: rules,
      initialManuscript: manuscript,
      policy: {
        maxIterations: 1,
        maximumReaderPages: 7,
        teaching: "not_applicable",
        enabledLenses: ["evidence"],
        blockingLenses: ["evidence"],
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
}

test("RunEngine rejects unknown immutable references at start", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-run-spec-reference-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  t.after(() => engine.close());
  const valid = await prepareArticleSources(engine, articleSpec(), "unknown-reference");
  await assert.rejects(
    engine.start({
      ...valid,
      article: { ...valid.article, sources: [id("unknown-source")] },
    }),
    RunSpecReferenceError,
  );
});

test("RunEngine rejects an arbitrary artifact as a standalone article source", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-run-spec-source-kind-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  t.after(() => engine.close());
  const valid = await prepareArticleSources(engine, articleSpec(), "wrong-source-kind");
  const renderProfile = id("not-a-source");
  await assert.rejects(
    engine.start({
      ...valid,
      artifacts: [...valid.artifacts, seed(renderProfile, "render_profile")],
      article: { ...valid.article, sources: [renderProfile] },
    }),
    (error: unknown) =>
      error instanceof Error && error.message.includes("must be a source_extraction"),
  );
});

test("RunEngine rejects standalone sources without an exact persisted approval", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-run-spec-source-approval-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  t.after(() => engine.close());
  const unapproved = articleSpec();
  await assert.rejects(
    engine.start(unapproved),
    /source approvals must be ordered one-for-one with sources/,
  );

  const fakeApproval = id("unpersisted-source-review");
  await assert.rejects(
    engine.start({
      ...unapproved,
      artifacts: [
        ...unapproved.artifacts,
        { ...seed(fakeApproval, "source_review_decision"), origin: "human" },
      ],
      article: { ...unapproved.article, sourceApprovalArtifacts: [fakeApproval] },
    }),
    /not bound to strict-source's lead\/raw\/extraction tuple/,
  );
});

test("RunSpec rejects missing lens prompts and page caps over seven", () => {
  const valid = articleSpec();
  assert.throws(() => parseRunSpec({
    ...valid,
    article: {
      ...valid.article,
      judgePrompts: {},
      policy: { ...valid.article.policy, maximumReaderPages: 8 },
    },
  }));
});

test("fork reuses ancestor artifacts through the public engine interface", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-run-spec-fork-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  t.after(() => engine.close());
  const started = await engine.start(await prepareArticleSources(engine, articleSpec(), "fork"));
  const successor = await engine.fork(started.runId, []);
  assert.notEqual(successor.runId, started.runId);
  await assert.rejects(
    engine.fork(started.runId, [{
      kind: "replace_artifact",
      from: id("strict-source"),
      to: seed(id("strict-not-a-source"), "render_profile"),
    }]),
    (error: unknown) =>
      error instanceof Error && error.message.includes("must be a source_extraction"),
  );
});

test("an edition may begin collection with no sources", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-empty-collection-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  t.after(() => engine.close());
  const ids = ["brief", "plan", "editorial-brief", "rules", "editorial", "render", "release"]
    .map((value) => id(`empty-${value}`));
  const [brief, plan, editorialBrief, rules, editorial, render, release] = ids;
  assert.ok(brief && plan && editorialBrief && rules && editorial && render && release);
  const spec: EditionRootRunSpec = {
    schemaVersion: 1,
    kind: "edition",
    artifacts: ids.map((artifactId) => seed(artifactId, "fixture")),
    edition: {
      editionId: "empty-collection",
      execution: { kind: "produce" },
      editionBrief: brief,
      planningArtifact: plan,
      sources: [],
      articles: [],
      editorial: {
        editorialId: "empty-editorial",
        briefArtifact: editorialBrief,
        writingRules: rules,
        initialManuscript: editorial,
        modelPolicy: { default: { adapter: "test", model: "test" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: render,
        rendererContractVersion: "render-edition/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: release,
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  };
  const started = await engine.start(spec);
  assert.equal(started.status, "waiting");
  const view = await engine.inspect(started.runId);
  assert.equal(view.offers[0]?.role, "close_collection");
});

test("EditionRunSpec makes production and committed-composition execution explicit", () => {
  const produce = parseRunSpec({
    schemaVersion: 1,
    kind: "edition",
    artifacts: [],
    edition: {
      editionId: "bootstrap-contract",
      execution: { kind: "produce" },
      editionBrief: "brief",
      sources: [],
      articles: [],
      editorial: {
        editorialId: "opening",
        briefArtifact: "editorial-brief",
        writingRules: "rules",
        modelPolicy: { default: { adapter: "test", model: "test" } },
      },
      translations: [],
      art: [],
      render: {
        renderManifestArtifact: "render",
        rendererContractVersion: "render/1",
        configuredLanguages: ["en"],
        studioPolicy: "not_applicable",
      },
      release: {
        publicationArtifact: "publication",
        sourceArtifacts: [],
        dryRun: true,
        target: "private",
      },
      modelPolicy: { default: { adapter: "test", model: "test" } },
    },
  });
  assert.equal(produce.kind, "edition");
  assert.equal(produce.edition.execution.kind, "produce");

  const bootstrap = parseRunSpec({
    ...produce,
    edition: {
      ...produce.edition,
      execution: {
        kind: "bootstrap_composition",
        bootstrapRevision: {
          kind: "run_bootstrap",
          editionId: "004",
          logicalId: "run-bootstrap",
          revisionId: "rev_20260802T200641636Z_aaaaaaaaaaaa",
        },
        postRender: "stop_unreleased",
      },
    },
  });
  assert.equal(bootstrap.kind, "edition");
  assert.equal(bootstrap.edition.execution.kind, "bootstrap_composition");
  assert.deepEqual(editionInputRevisionReferences(bootstrap.edition), [{
    kind: "run_bootstrap",
    editionId: "004",
    logicalId: "run-bootstrap",
    revisionId: "rev_20260802T200641636Z_aaaaaaaaaaaa",
  }]);
  assert.throws(() => parseRunSpec({
    ...produce,
    edition: { ...produce.edition, execution: { kind: "bootstrap_composition" } },
  }));
});
