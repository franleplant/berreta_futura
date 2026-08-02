import type {
  ArtifactId,
  ArticleRootRunSpec,
  JsonObject,
  RunId,
  RunOutcome,
} from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/types.ts";
import { compareArticleRuns, type ArticleComparison } from "./comparison.ts";
import {
  startArticleEvaluationCorpus,
  type ArticleEvaluationCorpus,
  type StartedCorpusExperiment,
} from "./corpus.ts";

export type ArticleExperiment = {
  readonly name: string;
  readonly spec: ArticleRootRunSpec;
  readonly difference: JsonObject;
};

export type StartedExperiment = {
  readonly name: string;
  readonly difference: JsonObject;
  readonly outcome: RunOutcome;
};

export type ArticlePreference = {
  readonly selectedRunId: RunId;
  readonly selectedArtifactId: ArtifactId;
  readonly policyArtifactId: ArtifactId;
  readonly reviewer: string;
  readonly rationale: string;
  readonly comparedRunIds: readonly RunId[];
  readonly recordedAt: string;
};

export class ArticleLab {
  private readonly engine: RunEngine;

  constructor(engine: RunEngine) {
    this.engine = engine;
  }

  async start(experiments: readonly ArticleExperiment[]): Promise<readonly StartedExperiment[]> {
    return await Promise.all(
      experiments.map(async (experiment) => ({
        name: experiment.name,
        difference: experiment.difference,
        outcome: await this.engine.start(experiment.spec),
      })),
    );
  }

  async startCorpus(
    corpus: ArticleEvaluationCorpus,
  ): Promise<readonly StartedCorpusExperiment[]> {
    return await startArticleEvaluationCorpus(this.engine, corpus);
  }

  async compare(runIds: readonly RunId[]): Promise<ArticleComparison> {
    return await compareArticleRuns(this.engine, runIds);
  }

  async choose(
    runIds: readonly RunId[],
    selectedRunId: RunId,
    reviewer: string,
    rationale: string,
  ): Promise<ArticlePreference> {
    if (!runIds.includes(selectedRunId)) {
      throw new Error("selected run was not part of the comparison");
    }
    const promotion = await this.engine.promoteArticle(selectedRunId, {
      reviewer,
      rationale,
      comparedRunIds: runIds,
    });
    return {
      selectedRunId,
      selectedArtifactId: promotion.selectedArtifactId,
      policyArtifactId: promotion.policyArtifactId,
      reviewer: promotion.reviewer,
      rationale: promotion.rationale,
      comparedRunIds: promotion.comparedRunIds,
      recordedAt: promotion.createdAt,
    };
  }
}
