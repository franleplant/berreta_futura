import type { ArtifactId, WorkRole } from "../contracts/index.ts";

export type ArticleArtifactClassification =
  | "article_brief"
  | "edition_context"
  | "judge_prompt"
  | "manuscript"
  | "measurement_input"
  | "measurement_profile"
  | "revision_finding"
  | "source"
  | "working_notes"
  | "writer_policy"
  | "writer_prompt"
  | "writing_rules";

export type ClassifiedArticleArtifact = {
  readonly artifactId: ArtifactId;
  readonly articleId: string;
  readonly classification: ArticleArtifactClassification;
};

const sourceBlindRoles = new Set<WorkRole>(["mechanics", "shape", "craft"]);

const sourceBlindClasses = new Set<ArticleArtifactClassification>([
  "judge_prompt",
  "manuscript",
  "writing_rules",
]);

export class SourceIsolationError extends Error {
  readonly role: WorkRole;
  readonly artifactId: ArtifactId;
  readonly classification: ArticleArtifactClassification;

  constructor(role: WorkRole, artifact: ClassifiedArticleArtifact) {
    super(
      `Role ${role} cannot read ${artifact.classification} artifact ${artifact.artifactId}`,
    );
    this.name = "SourceIsolationError";
    this.role = role;
    this.artifactId = artifact.artifactId;
    this.classification = artifact.classification;
  }
}

export function assertOneArticle(
  articleId: string,
  artifacts: readonly ClassifiedArticleArtifact[],
): void {
  for (const artifact of artifacts) {
    if (artifact.articleId !== articleId) {
      throw new TypeError(
        `Article ${articleId} offer cannot include artifact for ${artifact.articleId}`,
      );
    }
  }
}

export function assertRoleArtifactAccess(
  role: WorkRole,
  artifacts: readonly ClassifiedArticleArtifact[],
): void {
  if (!sourceBlindRoles.has(role)) {
    return;
  }
  for (const artifact of artifacts) {
    if (!sourceBlindClasses.has(artifact.classification)) {
      throw new SourceIsolationError(role, artifact);
    }
  }
}

export function artifactIds(
  artifacts: readonly ClassifiedArticleArtifact[],
): readonly ArtifactId[] {
  const seen = new Set<ArtifactId>();
  const ids: ArtifactId[] = [];
  for (const artifact of artifacts) {
    if (seen.has(artifact.artifactId)) {
      continue;
    }
    seen.add(artifact.artifactId);
    ids.push(artifact.artifactId);
  }
  return ids;
}
