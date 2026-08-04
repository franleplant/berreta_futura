/**
 * Compatibility exports for the old task-composer path. Material policy lives
 * in `article-production/materials.ts` so Loops and legacy offers share one
 * source-isolation seam.
 */
export {
  SourceExposureConflictError,
  SourceIsolationError,
  artifactIds,
  assertMaterialAccess,
  assertOneArticle,
  assertPrincipalExposureIsolated,
  accessForRole,
} from "../article-production/materials.ts";
export type {
  ArticleArtifactClassification,
  ArticleExposure,
  ClassifiedArticleArtifact,
} from "../article-production/materials.ts";
