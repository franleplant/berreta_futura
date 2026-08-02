import type { ArtifactId, JsonObject } from "../contracts/index.ts";

export const RENDERER_CONTRACT_VERSION = "magazine-renderer/1";

/**
 * Path-free renderer configuration stored as an immutable engine artifact.
 * Absolute source paths and artifactRoot belong only to the transport manifest
 * materialized by RendererExecutor for one claimed attempt.
 */
export type RenderExecutionProfile = {
  readonly schemaVersion: 1;
  readonly rendererContractVersion: typeof RENDERER_CONTRACT_VERSION;
  readonly primaryLanguage: string;
  readonly publicationName: string;
  readonly renderer: "reportlab" | "weasyprint";
  readonly design?: string;
  readonly inputs: readonly {
    readonly artifactId: ArtifactId;
    readonly targetPath: string;
  }[];
  readonly metadata?: JsonObject;
};

/** Immutable inputs for measuring one article in representative edition placement. */
export type ArticleMeasurementProfile = RenderExecutionProfile & {
  readonly articleId: string;
  readonly editionId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly maximumReaderPages: number;
};

/** Immutable inputs for measuring every translated piece in one language. */
export type LanguageFitProfile = RenderExecutionProfile & {
  readonly editionId: string;
  readonly language: string;
  readonly translatedPieces: readonly {
    readonly articleId: string;
    readonly artifactId: ArtifactId;
    readonly maximumReaderPages: number;
  }[];
};

/** The machine-owned assembly artifact consumed by RendererExecutor. */
export type RenderAssemblyManifest = {
  readonly editionId: string;
  readonly content: readonly ArtifactId[];
  readonly translations: readonly ArtifactId[];
  readonly translationProofs: readonly ArtifactId[];
  readonly art: readonly ArtifactId[];
  readonly editionApproval: readonly ArtifactId[];
  readonly configuredLanguages: readonly string[];
  readonly renderProfileArtifactId: ArtifactId;
  readonly printerProfileArtifactId: ArtifactId | null;
};

export type StagedFile = {
  readonly artifactId: ArtifactId;
  readonly sourcePath: string;
  readonly targetPath: string;
};

export type RenderManifest = {
  readonly schemaVersion: 1;
  readonly rendererContractVersion: typeof RENDERER_CONTRACT_VERSION;
  readonly operation: "measure_article" | "measure_edition" | "render_edition";
  readonly editionId: string;
  readonly articleId?: string;
  readonly primaryLanguage: string;
  readonly languages: readonly string[];
  readonly publicationName: string;
  readonly renderer: "reportlab" | "weasyprint";
  readonly artifactRoot: string;
  readonly design?: string;
  readonly inputs: readonly StagedFile[];
  readonly metadata?: JsonObject;
};

export type RenderedFile = {
  readonly path: string;
  readonly mediaType: string;
  readonly kind: string;
};

export type LanguageLayout = {
  readonly language: string;
  readonly totalPages: number;
  readonly editorialPages: number;
  readonly articlePages: Readonly<Record<string, number>>;
  readonly figureCount: number;
  readonly criticResult: "pass" | "fail" | "not_run";
};

export type RenderResult = {
  readonly schemaVersion: 1;
  readonly rendererContractVersion: typeof RENDERER_CONTRACT_VERSION;
  readonly editionId: string;
  readonly files: readonly RenderedFile[];
  readonly layouts: readonly LanguageLayout[];
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly tailArtFacts: JsonObject;
};

export interface RendererAdapter {
  render(
    manifestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<RenderResult>;
}
