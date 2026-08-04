import type {
  ActorId,
  ArtifactId,
  ArticleRunSpec,
  RevisionId,
  IterationId,
  OfferRequirements,
  WorkerCapability,
} from "../contracts/index.ts";
import type { CreateWorkOfferEffect } from "../machines/runtime.ts";
import {
  selectLegacyArticleMaterialSet,
  type ArticleOfferRole,
} from "../article-production/materials.ts";

export type { ArticleOfferRole } from "../article-production/materials.ts";

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

function taskArtifactId(input: ComposeArticleOfferInput): ArtifactId {
  if (input.role === "writer") {
    return input.spec.writerPrompt;
  }
  if (input.role === "measure_article" || input.role === "editor_decision") {
    return input.role === "measure_article"
      ? input.spec.measurementProfileArtifact ?? input.spec.articleBrief
      : input.spec.articleBrief;
  }
  const prompt = input.spec.judgePrompts[input.role];
  if (prompt === undefined) {
    throw new TypeError(`Article ${input.spec.articleId} has no prompt for ${input.role}`);
  }
  return prompt;
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
      return [];
    default:
      return ["text_model", "source_access"];
  }
}

function requirements(role: ArticleOfferRole): OfferRequirements {
  return {
    authority: role === "editor_decision"
      ? "human"
      : role === "measure_article"
        ? "tool"
        : "model",
    capabilities: capabilities(role),
    minimumAssurance: "local_bearer",
  };
}

function legacyCapabilities(role: ArticleOfferRole): readonly WorkerCapability[] {
  return role === "editor_decision" ? ["human"] : capabilities(role);
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
  const artifacts = selectLegacyArticleMaterialSet({
    articleId: input.spec.articleId,
    spec: input.spec,
    role: input.role,
    ...(input.manuscriptArtifact === undefined ? {} : { manuscriptArtifact: input.manuscriptArtifact }),
    ...(input.findingArtifacts === undefined ? {} : { findingArtifacts: input.findingArtifacts }),
    ...(input.rulingArtifacts === undefined ? {} : { rulingArtifacts: input.rulingArtifacts }),
    ...(input.workingNotesArtifact === undefined ? {} : { workingNotesArtifact: input.workingNotesArtifact }),
  });

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
    inputArtifacts: artifacts.artifactIds,
    taskArtifactId: taskArtifactId(input),
    contractVersion: `article-${input.role}/1`,
    requirements: requirements(input.role),
    // Compatibility only. Human authority is represented by requirements.
    allowedWorkerCapabilities: legacyCapabilities(input.role),
  };
}
