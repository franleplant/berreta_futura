import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { ArticleLab } from "../article-lab/index.ts";
import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  JudgeLens,
  RunView,
  WorkOfferView,
} from "../contracts/index.ts";
import { RunEngineError, SqliteRunEngine } from "../run-engine/index.ts";
import { prepareArticleSources } from "./approved-source-fixture.ts";
import { AuthorityTestHarness } from "./authority-fixture.ts";
import { durableCheckpointAnswer } from "./durable-checkpoint-fixture.ts";

const lenses: readonly JudgeLens[] = [
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
];

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

function seed(id: ArtifactId, kind: string, text: string = id): ArtifactSeed {
  return {
    id,
    kind,
    schemaVersion: "fixture/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text },
  };
}

function articleSpec(prefix: string): ArticleRootRunSpec {
  const brief = artifactId(`${prefix}-brief`);
  const source = artifactId(`${prefix}-source`);
  const writerPrompt = artifactId(`${prefix}-writer`);
  const rules = artifactId(`${prefix}-rules`);
  const manuscript = artifactId(`${prefix}-manuscript`);
  const prompts = Object.fromEntries(
    lenses.map((lens) => [lens, artifactId(`${prefix}-${lens}`)]),
  ) as Record<JudgeLens, ArtifactId>;
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      seed(brief, "article_brief"),
      seed(source, "source_extraction"),
      seed(writerPrompt, "writer_prompt"),
      seed(rules, "writing_rules"),
      seed(manuscript, "article_manuscript", `# ${prefix}\n\nSettled manuscript.`),
      ...lenses.map((lens) => seed(prompts[lens], `${lens}_prompt`)),
    ],
    article: {
      articleId: `${prefix}-article`,
      contentMode: "faithful_edit",
      attribution: {
        kind: "source_author",
        byline: "Source Author",
        sourceAuthors: ["Source Author"],
        sourceIds: [`${prefix}-source`],
      },
      articleBrief: brief,
      sources: [source],
      sourceApprovalArtifacts: [],
      writerPrompt,
      judgePrompts: prompts,
      writingRules: rules,
      initialManuscript: manuscript,
      policy: {
        maxIterations: 2,
        maximumReaderPages: 7,
        teaching: "applicable",
        enabledLenses: lenses,
        blockingLenses: lenses,
      },
      modelPolicy: { default: { adapter: "test", model: prefix } },
    },
  };
}

function measurement(offer: WorkOfferView): AnswerArtifact {
  return {
    id: artifactId(`measurement-${offer.id}`),
    kind: "article_measurement",
    schemaVersion: "measurement/1",
    mediaType: "application/json",
    payload: { kind: "json", value: { fits: true, pageCount: 1 } },
  };
}

async function settle(
  engine: SqliteRunEngine,
  spec: ArticleRootRunSpec,
  authority: AuthorityTestHarness,
): Promise<RunView> {
  const started = await engine.start(await prepareArticleSources(
    engine,
    spec,
    `promotion-${spec.article.articleId}`,
    await authority.human(),
  ));
  let view = await engine.inspect(started.runId);
  for (let count = 0; count < 20 && view.status !== "complete"; count += 1) {
    const offer = view.offers.find((candidate) => candidate.status === "offered");
    assert.ok(offer, `article run stranded as ${view.status}`);
    if (offer.requirements?.authority === "human") {
      const worker = await authority.workerFor(offer);
      const preparation = await engine.prepareHumanDecision(offer.id, worker);
      const choice = preparation.allowedChoices.includes("accept") ? "accept" : preparation.allowedChoices[0];
      assert.ok(choice);
      view = await engine.decide(preparation, worker, {
        schemaVersion: "human-decision-intent/1",
        offerId: preparation.offerId,
        taskArtifactId: preparation.taskArtifactId,
        inputArtifactIds: preparation.inputArtifactIds,
        result: { choice },
      });
      continue;
    }
    const claim = await authority.claim(engine, offer);
    if (offer.role === "durable_checkpoint") {
      view = await engine.answer(claim, await durableCheckpointAnswer(engine, offer));
      continue;
    }
    view = await engine.answer(claim, {
      contractVersion: offer.contractVersion,
      result: offer.role === "measure_article"
        ? { fits: true, pageCount: 1 }
        : { approved: true, decision: "pass" },
      artifacts: offer.role === "measure_article" ? [measurement(offer)] : [],
    });
  }
  assert.equal(view.status, "complete");
  return view;
}

test("ArticleLab durably promotes a settled comparison winner and its policy lineage", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-article-promotion-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "runs.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  const authority = await AuthorityTestHarness.create(temporary);
  try {
    const left = await settle(engine, articleSpec("left"), authority);
    const right = await settle(engine, articleSpec("right"), authority);
    const lab = new ArticleLab(engine);
    const preference = await lab.choose(
      [left.id, right.id],
      right.id,
      "editor@example.test",
      "The right-hand policy produced the clearer manuscript.",
    );

    assert.equal(preference.selectedRunId, right.id);
    assert.equal(preference.selectedArtifactId, right.actors[0]?.outputs[0]);
    const stored = await engine.readArtifact(preference.policyArtifactId);
    assert.equal(stored.artifact.kind, "article_promotion_policy");
    assert.equal(stored.artifact.origin, "human");
    assert.ok(
      stored.artifact.parents.some(
        (parent) =>
          parent.artifactId === preference.selectedArtifactId &&
          parent.relation === "selected_manuscript",
      ),
    );
    assert.equal(
      stored.artifact.parents.filter((parent) => parent.relation === "compared_candidate").length,
      2,
    );
    const policy = JSON.parse(Buffer.from(stored.bytes).toString("utf8")) as {
      readonly reviewer: string;
      readonly configuration: { readonly modelPolicy: unknown };
    };
    assert.equal(policy.reviewer, "editor@example.test");
    assert.ok(policy.configuration.modelPolicy);
    const promotedView = await engine.inspect(right.id);
    const visibleIds = new Set(promotedView.artifacts.map((artifact) => artifact.id));
    const leftRoot = left.actors.find((actor) => actor.parentActorId === undefined);
    assert.ok(leftRoot?.outputs[0]);
    assert.ok(visibleIds.has(leftRoot.outputs[0]));
    for (const artifact of promotedView.artifacts) {
      for (const parent of artifact.parents) {
        assert.ok(
          visibleIds.has(parent.artifactId),
          `projection omitted lineage parent ${parent.artifactId}`,
        );
      }
    }

    const repeated = await engine.promoteArticle(right.id, {
      reviewer: preference.reviewer,
      rationale: preference.rationale,
      comparedRunIds: preference.comparedRunIds,
    });
    assert.equal(repeated.policyArtifactId, preference.policyArtifactId);
    await assert.rejects(
      engine.promoteArticle(right.id, {
        reviewer: preference.reviewer,
        rationale: "A changed decision must not rewrite the existing choice.",
        comparedRunIds: preference.comparedRunIds,
      }),
      (error: unknown) =>
        error instanceof RunEngineError && error.code === "ARTICLE_ALREADY_PROMOTED",
    );
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
