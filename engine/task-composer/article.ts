import type {
  ActorId,
  ArtifactId,
  ArticleRunSpec,
  JudgeLens,
  RevisionId,
  IterationId,
  WorkRole,
  WorkerCapability,
} from "../contracts/index.ts";
import type { CreateWorkOfferEffect } from "../machines/runtime.ts";
import {
  artifactIds,
  assertOneArticle,
  assertRoleArtifactAccess,
  type ArticleArtifactClassification,
  type ClassifiedArticleArtifact,
} from "./artifacts.ts";

export type ArticleOfferRole =
  | "writer"
  | "measure_article"
  | JudgeLens
  | "editor_decision";

export type ComposeArticleOfferInput = {
  readonly actorId: ActorId;
  readonly actorKey: string;
  readonly state: string;
  readonly spec: ArticleRunSpec;
  readonly role: ArticleOfferRole;
  readonly slot: string;
  readonly manuscriptArtifact?: ArtifactId;
  readonly findingArtifacts?: readonly ArtifactId[];
  readonly rulingArtifacts?: readonly ArtifactId[];
  readonly workingNotesArtifact?: ArtifactId;
  readonly iterationId?: IterationId;
  readonly iterationOrdinal?: number;
  readonly parentManuscriptArtifactId?: ArtifactId;
  readonly revisionId?: RevisionId;
};

function classified(
  articleId: string,
  classification: ArticleArtifactClassification,
  artifactId: ArtifactId | undefined,
): ClassifiedArticleArtifact[] {
  return artifactId === undefined
    ? []
    : [{ artifactId, articleId, classification }];
}

function classifiedMany(
  articleId: string,
  classification: ArticleArtifactClassification,
  artifactIds: readonly ArtifactId[] | undefined,
): ClassifiedArticleArtifact[] {
  return (artifactIds ?? []).map((artifactId) => ({
    artifactId,
    articleId,
    classification,
  }));
}

function judgePrompt(spec: ArticleRunSpec, lens: JudgeLens): ArtifactId {
  const prompt = spec.judgePrompts[lens];
  if (prompt === undefined) {
    throw new TypeError(`Article ${spec.articleId} has no prompt for ${lens}`);
  }
  return prompt;
}

function writerArtifacts(
  input: ComposeArticleOfferInput,
): readonly ClassifiedArticleArtifact[] {
  const { articleId } = input.spec;
  return [
    ...classified(articleId, "writer_prompt", input.spec.writerPrompt),
    ...classified(articleId, "writer_policy", input.spec.contentModeArtifact),
    ...classified(articleId, "writer_policy", input.spec.attributionArtifact),
    ...classified(articleId, "writer_policy", input.spec.editorialPolicyArtifact),
    ...classified(articleId, "writer_policy", input.spec.modelPolicyArtifact),
    ...classified(articleId, "article_brief", input.spec.articleBrief),
    ...classified(articleId, "writing_rules", input.spec.writingRules),
    ...classified(articleId, "edition_context", input.spec.editionContext),
    ...classifiedMany(articleId, "source", input.spec.sources),
    ...classifiedMany(articleId, "source", input.spec.sourceApprovalArtifacts),
    ...classified(articleId, "manuscript", input.manuscriptArtifact),
    ...classifiedMany(articleId, "revision_finding", input.findingArtifacts),
    ...classifiedMany(articleId, "revision_finding", input.rulingArtifacts),
    ...classified(articleId, "working_notes", input.workingNotesArtifact),
  ];
}

function judgeArtifacts(
  input: ComposeArticleOfferInput,
  lens: JudgeLens,
): readonly ClassifiedArticleArtifact[] {
  const { articleId } = input.spec;
  const common = [
    ...classified(articleId, "judge_prompt", judgePrompt(input.spec, lens)),
    ...classified(articleId, "manuscript", input.manuscriptArtifact),
    ...classified(articleId, "writing_rules", input.spec.writingRules),
  ];
  if (lens === "mechanics" || lens === "shape" || lens === "craft") {
    return common;
  }
  return [
    ...common,
    ...classified(articleId, "article_brief", input.spec.articleBrief),
    ...classified(articleId, "edition_context", input.spec.editionContext),
    ...classifiedMany(articleId, "source", input.spec.sources),
    ...classifiedMany(articleId, "source", input.spec.sourceApprovalArtifacts),
  ];
}

function offerArtifacts(
  input: ComposeArticleOfferInput,
): readonly ClassifiedArticleArtifact[] {
  const { articleId } = input.spec;
  switch (input.role) {
    case "writer":
      return writerArtifacts(input);
    case "measure_article":
      return [
        ...classified(articleId, "manuscript", input.manuscriptArtifact),
        ...classified(articleId, "article_brief", input.spec.articleBrief),
        ...classified(articleId, "edition_context", input.spec.editionContext),
        ...classified(
          articleId,
          "measurement_profile",
          input.spec.measurementProfileArtifact,
        ),
        ...classifiedMany(
          articleId,
          "measurement_input",
          input.spec.measurementInputArtifacts ?? [],
        ),
      ];
    case "editor_decision":
      return [
        ...classified(articleId, "manuscript", input.manuscriptArtifact),
        ...classified(articleId, "article_brief", input.spec.articleBrief),
        ...classifiedMany(articleId, "revision_finding", input.findingArtifacts),
        ...classifiedMany(articleId, "revision_finding", input.rulingArtifacts),
        ...classified(articleId, "working_notes", input.workingNotesArtifact),
      ];
    default:
      return judgeArtifacts(input, input.role);
  }
}

function taskArtifactId(input: ComposeArticleOfferInput): ArtifactId {
  if (input.role === "writer") {
    return input.spec.writerPrompt;
  }
  if (input.role === "measure_article" || input.role === "editor_decision") {
    return input.role === "measure_article"
      ? input.spec.measurementProfileArtifact ?? input.spec.articleBrief
      : input.spec.articleBrief;
  }
  return judgePrompt(input.spec, input.role);
}

function capabilities(role: ArticleOfferRole): readonly WorkerCapability[] {
  switch (role) {
    case "writer":
      return ["text_model", "source_access"];
    case "measure_article":
      return ["subprocess"];
    case "mechanics":
    case "shape":
    case "craft":
      return ["text_model", "source_blind"];
    case "editor_decision":
      return ["human"];
    default:
      return ["text_model", "source_access"];
  }
}

export function composeArticleWorkOffer(
  input: ComposeArticleOfferInput,
): CreateWorkOfferEffect {
  if (
    input.manuscriptArtifact === undefined &&
    input.role !== "writer" &&
    input.role !== "editor_decision"
  ) {
    throw new TypeError(
      `Article ${input.spec.articleId} cannot offer ${input.role} without a manuscript`,
    );
  }
  const artifacts = offerArtifacts(input);
  assertOneArticle(input.spec.articleId, artifacts);
  assertRoleArtifactAccess(input.role as WorkRole, artifacts);

  return {
    type: "create_work_offer",
    actorId: input.actorId,
    actorKey: input.actorKey,
    state: input.state,
    slot: input.slot,
    role: input.role,
    ...(
      input.manuscriptArtifact === undefined && input.role !== "writer"
        ? {}
        : {
            subjectArtifactId:
              input.manuscriptArtifact ?? input.spec.articleBrief,
          }
    ),
    ...(input.iterationId === undefined ? {} : { iterationId: input.iterationId }),
    ...(input.iterationOrdinal === undefined
      ? {}
      : { iterationOrdinal: input.iterationOrdinal }),
    ...(input.parentManuscriptArtifactId === undefined
      ? {}
      : { parentManuscriptArtifactId: input.parentManuscriptArtifactId }),
    ...(input.revisionId === undefined ? {} : { revisionId: input.revisionId }),
    inputArtifacts: artifactIds(artifacts),
    taskArtifactId: taskArtifactId(input),
    contractVersion: `article-${input.role}/1`,
    allowedWorkerCapabilities: capabilities(input.role),
  };
}
