import type { ArtifactId, JsonObject } from "../contracts/index.ts";

export const SOURCE_CONTRACT_VERSION = "magazine-source/1";

/**
 * Immutable, path-free instructions stored as a RunEngine artifact.
 *
 * SourceArchiveExecutor turns this profile into SourceRequest only after it has
 * copied every named artifact into an executor-owned root. Repository paths and
 * RunEngine storage paths therefore never become workflow inputs.
 */
export type SourceCaptureProfile = {
  readonly schemaVersion: 1;
  readonly sourceContractVersion: typeof SOURCE_CONTRACT_VERSION;
  readonly sourceId: string;
  readonly leadArtifactId: ArtifactId;
  readonly files: readonly {
    readonly artifactId: ArtifactId;
    readonly targetPath: string;
  }[];
  readonly metadata?: JsonObject;
};

export type SourceBundleInput = {
  readonly artifactId: ArtifactId;
  readonly sourcePath: string;
  readonly targetPath: string;
};

export type SourceRequest = {
  readonly schemaVersion: 1;
  readonly sourceContractVersion: typeof SOURCE_CONTRACT_VERSION;
  readonly sourceId: string;
  readonly leadArtifactId: ArtifactId;
  readonly artifactRoot: string;
  readonly files: readonly SourceBundleInput[];
  readonly metadata?: JsonObject;
};

export type SourceResult = {
  readonly schemaVersion: 1;
  readonly sourceContractVersion: typeof SOURCE_CONTRACT_VERSION;
  readonly sourceId: string;
  readonly files: readonly { readonly path: string; readonly kind: string }[];
  readonly inputArtifactIds: readonly ArtifactId[];
};

export interface SourceAdapter {
  archive(
    requestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<SourceResult>;
}
