import type {
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
  JsonObject,
  RunOutcome,
} from "../contracts/index.ts";
import { parseRunSpec } from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/types.ts";

export const ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION =
  "article-lab-corpus/1" as const;

export type ArticleEvaluationExperiment = {
  readonly caseName: string;
  readonly variantName: string;
  readonly contextArtifactId: ArtifactId;
  readonly difference: JsonObject;
  readonly spec: ArticleRootRunSpec;
};

export type ArticleEvaluationCorpus = {
  readonly schemaVersion: typeof ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION;
  readonly corpusId: string;
  readonly version: string;
  readonly corpusArtifactIds: readonly ArtifactId[];
  readonly experiments: readonly ArticleEvaluationExperiment[];
};

export type StartedCorpusExperiment = {
  readonly corpusId: string;
  readonly corpusVersion: string;
  readonly caseName: string;
  readonly variantName: string;
  readonly contextArtifactId: ArtifactId;
  readonly corpusArtifactIds: readonly ArtifactId[];
  readonly difference: JsonObject;
  readonly outcome: RunOutcome;
};

export function parseArticleEvaluationCorpus(value: unknown): ArticleEvaluationCorpus {
  const corpus = record(value, "article evaluation corpus");
  if (corpus.schemaVersion !== ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION) {
    throw new TypeError(
      `article evaluation corpus must use ${ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION}`,
    );
  }
  const corpusId = nonemptyString(corpus.corpusId, "corpusId");
  const version = nonemptyString(corpus.version, "version");
  const corpusArtifactIds = artifactIds(corpus.corpusArtifactIds, "corpusArtifactIds");
  if (corpusArtifactIds.length === 0) {
    throw new TypeError("corpusArtifactIds must contain at least one immutable artifact ID");
  }
  if (!Array.isArray(corpus.experiments) || corpus.experiments.length === 0) {
    throw new TypeError("experiments must contain at least one named variant");
  }
  const names = new Set<string>();
  const contexts = new Set<string>();
  const experiments = corpus.experiments.map((candidate, index) => {
    const experiment = record(candidate, `experiments[${index}]`);
    const caseName = nonemptyString(experiment.caseName, `experiments[${index}].caseName`);
    const variantName = nonemptyString(
      experiment.variantName,
      `experiments[${index}].variantName`,
    );
    const identity = `${caseName}\u0000${variantName}`;
    if (names.has(identity)) {
      throw new TypeError(`duplicate corpus experiment ${caseName}/${variantName}`);
    }
    names.add(identity);
    const contextArtifactId = nonemptyString(
      experiment.contextArtifactId,
      `experiments[${index}].contextArtifactId`,
    ) as ArtifactId;
    if (contexts.has(contextArtifactId)) {
      throw new TypeError(`duplicate corpus context artifact ID ${contextArtifactId}`);
    }
    contexts.add(contextArtifactId);
    const difference = record(
      experiment.difference,
      `experiments[${index}].difference`,
    ) as JsonObject;
    const parsed = parseRunSpec(experiment.spec);
    if (parsed.kind !== "article") {
      throw new TypeError(`experiments[${index}].spec must be an article run`);
    }
    const seeded = new Set(parsed.artifacts.map((artifact) => artifact.id));
    const missing = corpusArtifactIds.filter((artifactId) => !seeded.has(artifactId));
    if (missing.length > 0) {
      throw new TypeError(
        `experiments[${index}] does not seed fixed corpus artifacts: ${missing.join(", ")}`,
      );
    }
    if (seeded.has(contextArtifactId)) {
      throw new TypeError(
        `experiments[${index}] already uses context artifact ID ${contextArtifactId}`,
      );
    }
    return { caseName, variantName, contextArtifactId, difference, spec: parsed };
  });
  return {
    schemaVersion: ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION,
    corpusId,
    version,
    corpusArtifactIds,
    experiments,
  };
}

export async function startArticleEvaluationCorpus(
  engine: RunEngine,
  value: ArticleEvaluationCorpus,
): Promise<readonly StartedCorpusExperiment[]> {
  const corpus = parseArticleEvaluationCorpus(value);
  return await Promise.all(
    corpus.experiments.map(async (experiment) => {
      const context = contextArtifact(corpus, experiment);
      const spec: ArticleRootRunSpec = {
        ...experiment.spec,
        artifacts: [...experiment.spec.artifacts, context],
        metadata: {
          ...(experiment.spec.metadata ?? {}),
          articleLabEvaluation: context.payload.kind === "json"
            ? context.payload.value as JsonObject
            : {},
        },
      };
      return {
        corpusId: corpus.corpusId,
        corpusVersion: corpus.version,
        caseName: experiment.caseName,
        variantName: experiment.variantName,
        contextArtifactId: experiment.contextArtifactId,
        corpusArtifactIds: corpus.corpusArtifactIds,
        difference: experiment.difference,
        outcome: await engine.start(spec),
      };
    }),
  );
}

function contextArtifact(
  corpus: ArticleEvaluationCorpus,
  experiment: ArticleEvaluationExperiment,
): ArtifactSeed {
  return {
    id: experiment.contextArtifactId,
    kind: "article_lab_evaluation_context",
    schemaVersion: "article-lab-evaluation-context/1",
    mediaType: "application/json",
    origin: "machine",
    payload: {
      kind: "json",
      value: {
        schemaVersion: "article-lab-evaluation-context/1",
        corpusId: corpus.corpusId,
        corpusVersion: corpus.version,
        caseName: experiment.caseName,
        variantName: experiment.variantName,
        corpusArtifactIds: corpus.corpusArtifactIds,
        difference: experiment.difference,
      },
    },
    parents: corpus.corpusArtifactIds.map((artifactId) => ({
      artifactId,
      relation: "evaluation_corpus_input",
    })),
    metadata: {
      corpusId: corpus.corpusId,
      corpusVersion: corpus.version,
      caseName: experiment.caseName,
      variantName: experiment.variantName,
    },
  };
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${label} must be a JSON object`);
  }
  return value as Record<string, unknown>;
}

function nonemptyString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new TypeError(`${label} must be a non-empty string`);
  }
  return value;
}

function artifactIds(value: unknown, label: string): readonly ArtifactId[] {
  if (!Array.isArray(value) || value.some((candidate) =>
    typeof candidate !== "string" || candidate.length === 0
  )) {
    throw new TypeError(`${label} must be a list of artifact IDs`);
  }
  if (new Set(value).size !== value.length) {
    throw new TypeError(`${label} must contain unique artifact IDs`);
  }
  return value as readonly ArtifactId[];
}
