import type {
  AnswerArtifact,
  ArtifactId,
  JsonObject,
  PromotionId,
  RevisionId,
  RunId,
} from "../contracts/index.ts";

export type DurableRevisionKind = "article" | "composition" | "editorial" | "image";

type DurableLogicalBase = {
  readonly editionId: string;
};

export type DurableLogicalItem = DurableLogicalBase & ({
  readonly kind: "article";
  readonly logicalId: string;
  readonly language: string;
} | {
  readonly kind: "editorial";
  readonly logicalId: string;
  readonly language: string;
} | {
  readonly kind: "image";
  readonly logicalId: string;
  readonly language?: never;
} | {
  readonly kind: "composition";
  readonly compositionId: string;
  readonly language?: never;
});

export type DurableRevisionRef = DurableLogicalItem & {
  readonly revisionId: RevisionId;
};

export type InputRevisionKind =
  | "edition_spec"
  | "policy"
  | "prompt"
  | "run_bootstrap"
  | "source_capture"
  | "source_extraction";

export type InputRevisionRef = ({
  readonly kind: "edition_spec";
  readonly logicalId: string;
  readonly revisionId: RevisionId;
  readonly editionId: string;
} | {
  readonly kind: "run_bootstrap";
  readonly logicalId: string;
  readonly revisionId: RevisionId;
  readonly editionId: string;
} | {
  readonly kind: Exclude<InputRevisionKind, "edition_spec" | "run_bootstrap">;
  readonly logicalId: string;
  readonly revisionId: RevisionId;
  readonly editionId?: never;
});

export type DurablePromotionRequest = {
  readonly schemaVersion: "durable-checkpoint-request/1";
  readonly promotionId: PromotionId;
  readonly revisionId: RevisionId;
  readonly runId: RunId;
  readonly logicalItem: DurableLogicalItem;
  readonly expectedParentRevisionId: RevisionId | null;
  readonly acceptedArtifactIds: readonly ArtifactId[];
  readonly decisionArtifactIds: readonly ArtifactId[];
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly inputArtifactIds: readonly ArtifactId[];
};

type DurableFileRecordBase = {
  readonly path: string;
  readonly mediaType: string;
  readonly sha256: string;
  readonly sizeBytes: number;
};

export type LegacySourceBinding = {
  readonly repositoryPath: string;
  readonly gitCommitOid: string;
  readonly gitBlobOid: string;
};

export type LegacySourceDigestBinding = LegacySourceBinding & {
  readonly sha256: string;
};

export type DurableFileRecord = DurableFileRecordBase & ({
  readonly engineArtifactId: ArtifactId;
  readonly legacySource?: never;
  readonly migrationAssembly?: never;
} | {
  readonly engineArtifactId?: never;
  readonly legacySource: LegacySourceBinding;
  readonly migrationAssembly?: never;
} | {
  readonly engineArtifactId?: never;
  readonly legacySource?: never;
  readonly migrationAssembly: {
    readonly basis: string;
  };
});

type DurableRevisionManifestBase = {
  readonly schema_version: 1;
  readonly revision_kind: DurableRevisionKind;
  readonly edition_id: string;
  readonly revision_id: RevisionId;
  readonly created_at: string;
  readonly parent_revision_id: RevisionId | null;
  readonly input_revisions: readonly InputRevisionRef[];
  readonly files: readonly DurableFileRecord[];
};

type EnginePromotionProvenance = {
  readonly provenance_kind: "engine_promotion";
  readonly promotion_id: PromotionId;
  readonly producing_run_id: RunId;
  readonly accepted_engine_artifact_ids: readonly ArtifactId[];
  readonly decision_engine_artifact_ids: readonly ArtifactId[];
  readonly input_engine_artifact_ids: readonly ArtifactId[];
};

type LegacyImportProvenance = {
  readonly provenance_kind: "legacy_import";
  readonly migration_id: string;
  readonly legacy_run_inventory: "absent";
  readonly legacy_source_bindings: readonly LegacySourceDigestBinding[];
};

type DurableRevisionIdentity = {
  readonly revision_kind: "article";
  readonly logical_id: string;
  readonly language: string;
} | {
  readonly revision_kind: "editorial";
  readonly logical_id: string;
  readonly language: string;
} | {
  readonly revision_kind: "image";
  readonly logical_id: string;
  readonly language?: never;
} | {
  readonly revision_kind: "composition";
  readonly composition_id: string;
  readonly language?: never;
};

export type EngineDurableRevisionManifest = DurableRevisionManifestBase &
  EnginePromotionProvenance & DurableRevisionIdentity;

export type LegacyDurableRevisionManifest = DurableRevisionManifestBase &
  LegacyImportProvenance & DurableRevisionIdentity;

export type DurableRevisionManifest =
  | EngineDurableRevisionManifest
  | LegacyDurableRevisionManifest;

export type GitRevisionBinding = {
  readonly commitOid: string;
  readonly blobOids: Readonly<Record<string, string>>;
};

export type GitCheckpointRequest = {
  readonly promotionId: PromotionId;
  readonly revision: DurableRevisionRef;
  readonly revisionDirectory: string;
  readonly repositoryPaths: readonly string[];
  readonly manifestDigest: string;
};

export interface DurableGit {
  assertCommitted(
    repositoryPaths: readonly string[],
    expectedBinding?: GitRevisionBinding,
  ): Promise<void>;
  checkpoint(request: GitCheckpointRequest): Promise<GitRevisionBinding>;
}

export type ResolvedDurableRevision = {
  readonly ref: DurableRevisionRef;
  readonly manifest: DurableRevisionManifest;
  readonly manifestDigest: string;
  readonly relativeDirectory: string;
  readonly absoluteDirectory: string;
  readonly repositoryPaths: readonly string[];
  readonly payloadPaths: Readonly<Record<string, string>>;
};

export type DurableCheckpointResult = {
  readonly contractVersion: "durable-checkpoint/1";
  readonly result: {
    readonly revisionId: RevisionId;
    readonly promotionId: PromotionId;
    readonly logicalItem: DurableLogicalItem;
    readonly expectedParentRevisionId: RevisionId | null;
    readonly manifestDigest: string;
    readonly gitCommitOid: string;
    readonly gitBlobOids: Readonly<Record<string, string>>;
    readonly revisionRef: DurableRevisionRef;
  };
  readonly artifacts: readonly [AnswerArtifact];
  readonly metadata: JsonObject;
};
