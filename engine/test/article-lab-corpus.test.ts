import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";
import { promisify } from "node:util";

import {
  ArticleLab,
  parseArticleEvaluationCorpus,
  type ArticleEvaluationCorpus,
} from "../article-lab/index.ts";
import type { ArtifactId } from "../contracts/index.ts";
import { FIXED_ARTICLE_EVALUATION_CORPUS } from "../fixtures/article-lab-corpus.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";

const execFileAsync = promisify(execFile);

async function prepareCorpusSources(
  engine: SqliteRunEngine,
  corpus: ArticleEvaluationCorpus,
  authority: AuthorityTestHarness,
): Promise<ArticleEvaluationCorpus> {
  const first = corpus.experiments[0];
  assert.ok(first, "corpus must contain an experiment");
  const prepared = await prepareArticleSources(
    engine,
    first.spec,
    `article-lab-${corpus.corpusId}-${corpus.version}`,
    await authority.human(),
  );
  const sourceSeeds = new Map(
    prepared.article.sources.map((source) => [
      source,
      prepared.artifacts.find((artifact) => artifact.id === source),
    ]),
  );
  return {
    ...corpus,
    experiments: corpus.experiments.map((experiment) => {
      assert.deepEqual(experiment.spec.article.sources, first.spec.article.sources);
      const placeholders = new Set(experiment.spec.article.sourceApprovalArtifacts);
      return {
        ...experiment,
        spec: {
          ...experiment.spec,
          artifacts: experiment.spec.artifacts
            .filter((artifact) => !placeholders.has(artifact.id))
            .map((artifact) => sourceSeeds.get(artifact.id) ?? artifact),
          article: {
            ...experiment.spec.article,
            sourceApprovalArtifacts: prepared.article.sourceApprovalArtifacts,
          },
        },
      };
    }),
  };
}

test("the versioned ArticleLab corpus preserves fixed input IDs and named variants", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-article-corpus-"));
  const engine = new SqliteRunEngine({
    databasePath: join(root, "runs.sqlite"),
    artifactDirectory: join(root, "artifacts"),
  });
  const authority = await AuthorityTestHarness.create(root);
  try {
    const lab = new ArticleLab(engine);
    const corpus = await prepareCorpusSources(engine, FIXED_ARTICLE_EVALUATION_CORPUS, authority);
    const first = await lab.startCorpus(corpus);
    assert.deepEqual(
      first.map((experiment) => experiment.variantName),
      ["baseline", "causal-spine"],
    );
    assert.ok(first.every((experiment) => experiment.corpusVersion === "1.0.0"));
    assert.ok(first.every((experiment) => experiment.outcome.status === "waiting"));
    assert.ok(first.every((experiment) => experiment.difference.model === "gpt-5.6-terra"));
    assert.ok(first.every((experiment) => experiment.difference.reasoningEffort === "high"));

    for (const experiment of first) {
      const view = await engine.inspect(experiment.outcome.runId);
      const visible = new Set(view.artifacts.map((artifact) => artifact.id));
      for (const artifactId of corpus.corpusArtifactIds) {
        assert.ok(visible.has(artifactId), `${experiment.variantName} lost ${artifactId}`);
      }
      assert.ok(visible.has(experiment.contextArtifactId));
      const context = await engine.readArtifact(experiment.contextArtifactId);
      const payload = JSON.parse(Buffer.from(context.bytes).toString("utf8")) as {
        readonly corpusId: string;
        readonly corpusVersion: string;
        readonly caseName: string;
        readonly variantName: string;
        readonly corpusArtifactIds: readonly ArtifactId[];
      };
      assert.equal(payload.corpusId, corpus.corpusId);
      assert.equal(payload.corpusVersion, corpus.version);
      assert.equal(payload.caseName, experiment.caseName);
      assert.equal(payload.variantName, experiment.variantName);
      assert.deepEqual(
        payload.corpusArtifactIds,
        corpus.corpusArtifactIds,
      );
      assert.deepEqual(
        context.artifact.parents,
        corpus.corpusArtifactIds.map((artifactId) => ({
          artifactId,
          relation: "evaluation_corpus_input",
        })),
      );
    }

    const second = await lab.startCorpus(corpus);
    assert.deepEqual(
      second.map((experiment) => experiment.contextArtifactId),
      first.map((experiment) => experiment.contextArtifactId),
    );
    assert.ok(second.every((experiment, index) =>
      experiment.outcome.runId !== first[index]?.outcome.runId
    ));
  } finally {
    engine.close();
    await rm(root, { recursive: true, force: true });
  }
});

test("corpus parsing rejects a variant that omits a fixed corpus artifact", () => {
  const corpus = structuredClone(FIXED_ARTICLE_EVALUATION_CORPUS);
  const first = corpus.experiments[0];
  assert.ok(first);
  assert.throws(() => parseArticleEvaluationCorpus({
    ...corpus,
    experiments: [{
      ...first,
      spec: {
        ...first.spec,
        artifacts: first.spec.artifacts.filter(
          (artifact) => artifact.id !== corpus.corpusArtifactIds[0],
        ),
      },
    }],
  }), /does not seed fixed corpus artifacts/);
});

test("the article corpus CLI starts every named variant", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-article-corpus-cli-"));
  try {
    const corpusPath = join(root, "corpus.json");
    const databasePath = join(root, "runs.sqlite");
    const artifactDirectory = join(root, "artifacts");
    const preparationEngine = new SqliteRunEngine({ databasePath, artifactDirectory });
    const authority = await AuthorityTestHarness.create(root);
    const corpus = await prepareCorpusSources(
      preparationEngine,
      FIXED_ARTICLE_EVALUATION_CORPUS,
      authority,
    );
    preparationEngine.close();
    await writeFile(
      corpusPath,
      `${JSON.stringify(corpus, null, 2)}\n`,
      "utf8",
    );
    const { stdout } = await execFileAsync(process.execPath, [
      "engine/cli.ts",
      "article",
      "corpus",
      corpusPath,
      "--db",
      databasePath,
      "--artifacts",
      artifactDirectory,
    ], { cwd: resolve(import.meta.dirname, "../..") });
    const started = JSON.parse(stdout) as readonly {
      readonly variantName: string;
      readonly contextArtifactId: ArtifactId;
      readonly outcome: { readonly runId: string; readonly status: string };
    }[];
    assert.deepEqual(
      started.map((experiment) => experiment.variantName),
      ["baseline", "causal-spine"],
    );
    assert.ok(started.every((experiment) => experiment.outcome.status === "waiting"));
    assert.ok(started.every((experiment) => experiment.contextArtifactId.length > 0));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
