import type {
  ArtifactId,
  ArtifactSeed,
  ArticleRootRunSpec,
} from "../contracts/index.ts";
import {
  ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION,
  type ArticleEvaluationCorpus,
} from "../article-lab/index.ts";

const briefId = id("article_lab_systems_corpus_v1_brief");
const sourceId = id("article_lab_systems_corpus_v1_source");
const sourceApprovalPlaceholderId = id("article_lab_systems_corpus_v1_source_approval_placeholder");
const rulesId = id("article_lab_systems_corpus_v1_rules");
const worthPromptId = id("article_lab_systems_corpus_v1_worth_prompt");
const evidencePromptId = id("article_lab_systems_corpus_v1_evidence_prompt");
const craftPromptId = id("article_lab_systems_corpus_v1_craft_prompt");

const fixedArtifacts: readonly ArtifactSeed[] = [
  textSeed(
    briefId,
    "article_brief",
    "Explain why durable workflow identity should follow immutable references and explicit state.",
  ),
  textSeed(
    sourceId,
    "source_extraction",
    "A workflow can survive interruption when its state transitions and inputs have durable identities. Reusing bytes without preserving identity obscures causality.",
  ),
  textSeed(
    rulesId,
    "writing_rules",
    "Prefer concrete nouns and verbs. Preserve qualifications. Make each causal step explicit.",
  ),
  textSeed(
    worthPromptId,
    "worth_prompt",
    "Judge whether the article gives the reader a useful and non-obvious idea.",
  ),
  textSeed(
    evidencePromptId,
    "evidence_prompt",
    "Check every factual claim against the supplied extraction and flag unsupported certainty.",
  ),
  textSeed(
    craftPromptId,
    "craft_prompt",
    "Judge clarity, rhythm, structure, and unnecessary abstraction.",
  ),
];

const corpusArtifactIds = fixedArtifacts.map((artifact) => artifact.id);

const sourceApprovalPlaceholder = textSeed(
  sourceApprovalPlaceholderId,
  "source_review_decision",
  "Template-only source approval placeholder. Corpus startup replaces this with a persisted human decision.",
);

export const FIXED_ARTICLE_EVALUATION_CORPUS: ArticleEvaluationCorpus = {
  schemaVersion: ARTICLE_EVALUATION_CORPUS_SCHEMA_VERSION,
  corpusId: "systems-workflow-article-corpus",
  version: "1.0.0",
  corpusArtifactIds,
  experiments: [
    experiment(
      "baseline",
      id("article_lab_systems_corpus_v1_baseline_context"),
      id("article_lab_systems_corpus_v1_baseline_writer_prompt"),
      "Build the argument from one concrete workflow failure, then explain the durable design.",
    ),
    experiment(
      "causal-spine",
      id("article_lab_systems_corpus_v1_causal_spine_context"),
      id("article_lab_systems_corpus_v1_causal_spine_writer_prompt"),
      "Open with the consequence. Trace a single causal spine from immutable input to recoverable state.",
    ),
  ],
};

function experiment(
  variantName: string,
  contextArtifactId: ArtifactId,
  writerPromptId: ArtifactId,
  writerPrompt: string,
) {
  return {
    caseName: "durable-workflow-identity",
    variantName,
    contextArtifactId,
    difference: {
      writerPromptArtifactId: writerPromptId,
      model: "gpt-5.6-terra",
      reasoningEffort: "high",
    },
    spec: articleSpec(writerPromptId, writerPrompt),
  };
}

function articleSpec(writerPromptId: ArtifactId, writerPrompt: string): ArticleRootRunSpec {
  return {
    schemaVersion: 1,
    kind: "article",
    artifacts: [
      ...fixedArtifacts,
      sourceApprovalPlaceholder,
      textSeed(writerPromptId, "writer_prompt", writerPrompt),
    ],
    article: {
      articleId: "durable-workflow-identity",
      contentMode: "original_synthesis",
      attribution: { kind: "magazine", byline: "Magazine editors" },
      articleBrief: briefId,
      sources: [sourceId],
      sourceApprovalArtifacts: [sourceApprovalPlaceholderId],
      writerPrompt: writerPromptId,
      judgePrompts: {
        worth: worthPromptId,
        evidence: evidencePromptId,
        craft: craftPromptId,
      },
      writingRules: rulesId,
      policy: {
        maxIterations: 3,
        maximumReaderPages: 7,
        teaching: "not_applicable",
        enabledLenses: ["worth", "evidence", "craft"],
        blockingLenses: ["worth", "evidence", "craft"],
      },
      modelPolicy: {
        default: {
          adapter: "openai",
          model: "gpt-5.6-terra",
          reasoningEffort: "high",
        },
      },
    },
  };
}

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

function textSeed(
  artifactId: ArtifactId,
  kind: string,
  text: string,
): ArtifactSeed {
  return {
    id: artifactId,
    kind,
    schemaVersion: "article-lab-corpus-input/1",
    mediaType: "text/plain",
    origin: "imported",
    payload: { kind: "text", text },
  };
}
