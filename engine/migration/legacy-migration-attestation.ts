import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { promisify } from "node:util";

import { parse, stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import { validateInputRevisionTree } from "../durable/input-revision.ts";
import {
  durableRevisionRelativeDirectory,
  inputRevisionRelativeDirectory,
} from "../durable/paths.ts";
import { newRevisionId, parseRevisionId } from "../durable/revision-id.ts";
import type {
  DurableRevisionRef,
  InputRevisionRef,
} from "../durable/types.ts";
import {
  verifyLegacyRootMigrationPlan,
  type HistoricalCompositionPlan,
  type LegacyFileDisposition,
  type LegacyMigrationTarget,
  type LegacyRootMigrationPlan,
} from "./legacy-root-migration.ts";

const execFile = promisify(execFileCallback);
const MIGRATION_ID = "legacy-four-root";
const LEGACY_ROOTS = ["editions", "library", "prompts"] as const;
const EDITION_4_IMAGE_ROOT = "durable/editions/004/images";

type GitTreeEntry = {
  readonly repositoryPath: string;
  readonly mode: string;
  readonly gitBlobOid: string;
  readonly sizeBytes: number;
};

export type AttestedGitFile = GitTreeEntry & {
  readonly gitCommitOid: string;
  readonly sha256: string;
};

export type LegacySourceRowAttestation = {
  readonly source: AttestedGitFile;
  readonly disposition: LegacyFileDisposition["disposition"];
  readonly basis: string;
  readonly target: {
    readonly category: LegacyMigrationTarget["category"];
    readonly revisionKind: LegacyMigrationTarget["revisionKind"];
    readonly revisionId: RevisionId;
    readonly revisionRef: InputRevisionRef | DurableRevisionRef;
    readonly revisionDirectory: string;
    readonly plannedPayloadPath: string;
    readonly payloadPathResolution: "exact_plan_path" | "committed_reuse_binding";
    readonly manifest: AttestedGitFile;
    readonly payload: AttestedGitFile;
    readonly manifestSourceBinding: {
      readonly repositoryPath: string;
      readonly gitCommitOid: string;
      readonly gitBlobOid: string;
    };
    readonly manifestSourceCommitProof: AttestedGitFile;
  };
  readonly exactPayloadBytes: true;
};

export type GeneratedFileAttestation = {
  readonly revisionSlot: string;
  readonly basis: string;
  readonly revisionRef: InputRevisionRef | DurableRevisionRef;
  readonly revisionDirectory: string;
  readonly manifest: AttestedGitFile;
  readonly payload: AttestedGitFile;
  readonly manifestGenerationBasis: string;
};

export type HistoricalCompositionAttestation = HistoricalCompositionPlan & {
  readonly revisionRef: DurableRevisionRef;
  readonly revisionDirectory: string;
  readonly manifest: AttestedGitFile;
  readonly payload: AttestedGitFile;
  readonly manifestGenerationBasis: string;
};

export type LegacyMigrationAttestation = {
  readonly schemaVersion: "legacy-migration-attestation/1";
  readonly migrationId: string;
  readonly migrationPlan: {
    readonly revision: InputRevisionRef;
    readonly manifest: AttestedGitFile;
    readonly inventory: AttestedGitFile;
  };
  readonly protectedSource: {
    readonly commitOid: string;
    readonly canonicalInventorySha256: string;
    readonly fileCount: number;
    readonly sizeBytes: number;
  };
  readonly targetSnapshotCommitOid: string;
  readonly sourceRows: readonly LegacySourceRowAttestation[];
  readonly generatedFiles: readonly GeneratedFileAttestation[];
  readonly historicalCompositions: readonly HistoricalCompositionAttestation[];
  readonly preExistingEdition4ImageFiles: readonly {
    readonly source: AttestedGitFile;
    readonly target: AttestedGitFile;
    readonly unchanged: true;
  }[];
  readonly summary: {
    readonly sourceRows: number;
    readonly sourceBytes: number;
    readonly dispositions: Readonly<Record<LegacyFileDisposition["disposition"], number>>;
    readonly generatedFiles: number;
    readonly historicalCompositions: number;
    readonly preExistingEdition4ImageFiles: number;
  };
  readonly cutover: {
    readonly status: "ready_for_atomic_legacy_root_deletion";
    readonly protectedSourceCommitRecoverable: true;
    readonly allLegacyFilesAccountedFor: true;
    readonly allTargetsCommitted: true;
    readonly exactPayloadBytes: true;
    readonly generatedPlanFilesCommitted: true;
    readonly preExistingEdition4ImageBlobOidsUnchanged: true;
    readonly releaseAuthorityImported: false;
    readonly freshRunEngineReviewStillRequired: true;
  };
};

export type MaterializedLegacyMigrationAttestation = {
  readonly ref: InputRevisionRef;
  readonly repositoryPaths: readonly string[];
  readonly attestation: LegacyMigrationAttestation;
};

export type GitBlobDigest = {
  readonly sha256: string;
  readonly sizeBytes: number;
};

/** Rejects a ledger whose recorded SHA-256 does not match the protected Git object bytes. */
export function verifyLegacySourceBlobDigests(
  plan: LegacyRootMigrationPlan,
  digestsByBlobOid: ReadonlyMap<string, GitBlobDigest>,
): void {
  for (const file of plan.sourceSnapshot.files) {
    const actual = digestsByBlobOid.get(file.blobOid);
    if (actual === undefined || actual.sha256 !== file.sha256 || actual.sizeBytes !== file.sizeBytes) {
      throw new Error(`protected source blob digest differs from migration plan: ${file.path}`);
    }
  }
}

/** Emits a value-only YAML document so sorted output cannot precede an alias anchor. */
export function serializeLegacyMigrationAttestation(attestation: LegacyMigrationAttestation): Buffer {
  const detached = JSON.parse(JSON.stringify(attestation)) as LegacyMigrationAttestation;
  return Buffer.from(stringify(detached, { lineWidth: 0, sortMapEntries: true }), "utf8");
}

/**
 * Proves that every protected legacy blob has one exact committed destination
 * before the legacy roots are removed. This reads Git objects, never mutable
 * workflow state, and does not confer release authority.
 */
export async function buildLegacyMigrationAttestation(
  repositoryRoot: string,
  sourceCommitish: string,
  planRevisionId: RevisionId,
  targetSnapshotCommitish = "HEAD",
): Promise<LegacyMigrationAttestation> {
  const root = resolve(repositoryRoot);
  const sourceCommitOid = await gitText(root, ["rev-parse", `${sourceCommitish}^{commit}`]);
  const headCommitOid = await gitText(root, ["rev-parse", "HEAD^{commit}"]);
  const targetSnapshotCommitOid = await gitText(root, ["rev-parse", `${targetSnapshotCommitish}^{commit}`]);
  if (targetSnapshotCommitOid !== headCommitOid) {
    await assertGitAncestor(root, targetSnapshotCommitOid, headCommitOid);
  }
  const planPath = planRepositoryPath(planRevisionId, "inventory.yaml");
  const planManifestPath = planRepositoryPath(planRevisionId, "manifest.yaml");
  const targetTree = await readGitTree(root, targetSnapshotCommitOid, ["inputs", "durable"]);
  const sourceLegacyTree = await readGitTree(root, sourceCommitOid, [...LEGACY_ROOTS]);
  const sourceEdition4Images = await readGitTree(root, sourceCommitOid, [EDITION_4_IMAGE_ROOT]);
  const planTreeEntry = requiredTree(targetTree, planPath);
  const planManifestTreeEntry = requiredTree(targetTree, planManifestPath);
  const initialBlobs = await readGitBlobs(root, [planTreeEntry.gitBlobOid, planManifestTreeEntry.gitBlobOid]);
  const planBytes = requiredBlob(initialBlobs, planTreeEntry.gitBlobOid);
  const plan = parse(planBytes.toString("utf8")) as LegacyRootMigrationPlan;
  verifyLegacyRootMigrationPlan(plan);
  if (plan.migrationId !== MIGRATION_ID || plan.sourceSnapshot.sourceCommitOid !== sourceCommitOid) {
    throw new Error("migration plan does not bind the requested protected source commit");
  }
  verifyProtectedSourceTree(plan, sourceLegacyTree);
  const protectedBlobDigests = await hashGitBlobs(
    root,
    plan.sourceSnapshot.files.map((file) => file.blobOid),
  );
  verifyLegacySourceBlobDigests(plan, protectedBlobDigests);

  const revisionCache = new Map<string, RevisionBinding>();
  const sourceTargets: SourceTargetDraft[] = [];
  for (const entry of plan.files) {
    const target = entry.targets[0];
    if (target === undefined) throw new Error(`legacy source has no target: ${entry.source.path}`);
    const ref = targetRef(target, plan.migrationId);
    const revisionDirectory = targetRevisionDirectory(ref);
    const manifestPath = `${revisionDirectory}/manifest.yaml`;
    const manifestTree = requiredTree(targetTree, manifestPath);
    const sourceTree = requiredTree(sourceLegacyTree, entry.source.path);
    assertSourceTreeEntry(entry, sourceTree, sourceCommitOid);
    const key = `${manifestPath}\0${JSON.stringify(ref)}`;
    revisionCache.set(key, {
      ref,
      revisionDirectory,
      manifestPath,
      manifestTree,
    });
    sourceTargets.push({ entry, target, ref, revisionDirectory, manifestPath, manifestTree });
  }

  const generatedDrafts = plan.generatedFiles.map((generated) => {
    const ref = generatedRef(plan, generated.revisionSlot);
    const revisionDirectory = targetRevisionDirectory(ref);
    const manifestPath = `${revisionDirectory}/manifest.yaml`;
    const payloadPath = `${revisionDirectory}/${generated.path}`;
    const manifestTree = requiredTree(targetTree, manifestPath);
    const payloadTree = requiredTree(targetTree, payloadPath);
    revisionCache.set(`${manifestPath}\0${JSON.stringify(ref)}`, {
      ref,
      revisionDirectory,
      manifestPath,
      manifestTree,
    });
    return { generated, ref, revisionDirectory, manifestPath, manifestTree, payloadPath, payloadTree };
  });

  const compositionDrafts = plan.historicalCompositions.map((composition) => {
    const ref: DurableRevisionRef = {
      kind: "composition",
      editionId: composition.editionId,
      compositionId: composition.compositionId,
      revisionId: composition.revisionId,
    };
    const revisionDirectory = targetRevisionDirectory(ref);
    const manifestPath = `${revisionDirectory}/manifest.yaml`;
    const payloadPath = `${revisionDirectory}/composition.yaml`;
    const manifestTree = requiredTree(targetTree, manifestPath);
    const payloadTree = requiredTree(targetTree, payloadPath);
    revisionCache.set(`${manifestPath}\0${JSON.stringify(ref)}`, {
      ref,
      revisionDirectory,
      manifestPath,
      manifestTree,
    });
    return { composition, ref, revisionDirectory, manifestPath, manifestTree, payloadPath, payloadTree };
  });

  const targetEdition4Images = await readGitTree(root, targetSnapshotCommitOid, [EDITION_4_IMAGE_ROOT]);
  if (sourceEdition4Images.size === 0) throw new Error("protected snapshot has no pre-existing Edition 4 image files");
  const edition4Pairs = [...sourceEdition4Images.values()].sort(byPath).map((source) => {
    const target = requiredTree(targetEdition4Images, source.repositoryPath);
    if (source.mode !== target.mode || source.gitBlobOid !== target.gitBlobOid || source.sizeBytes !== target.sizeBytes) {
      throw new Error(`pre-existing Edition 4 image file changed: ${source.repositoryPath}`);
    }
    return { source, target };
  });

  const blobOids = [
    ...[...revisionCache.values()].map((value) => value.manifestTree.gitBlobOid),
    ...generatedDrafts.map((value) => value.payloadTree.gitBlobOid),
    ...compositionDrafts.map((value) => value.payloadTree.gitBlobOid),
    ...edition4Pairs.map((value) => value.source.gitBlobOid),
  ];
  const blobs = await readGitBlobs(root, blobOids);
  const revisions = new Map<string, ResolvedRevisionBinding>();
  for (const [key, binding] of revisionCache) {
    const manifestBytes = requiredBlob(blobs, binding.manifestTree.gitBlobOid);
    const manifest = mapping(parse(manifestBytes.toString("utf8")), `manifest ${binding.manifestPath}`);
    validateManifestIdentity(manifest, binding.ref);
    revisions.set(key, {
      ...binding,
      manifest,
      manifestBinding: attestTreeEntry(
        binding.manifestTree,
        targetSnapshotCommitOid,
        sha256(manifestBytes),
      ),
    });
  }

  const sourceRows = sourceTargets.map((draft): LegacySourceRowAttestation => {
    const revision = requiredRevision(revisions, draft.manifestPath, draft.ref);
    const resolved = exactManifestFile(
      revision.manifest,
      draft.entry,
      draft.target.category,
      draft.target.payloadPath,
    );
    if (resolved.path !== draft.target.payloadPath && draft.entry.disposition !== "reuse_existing") {
      throw new Error(`new migration target did not use its planned payload path: ${draft.entry.source.path}`);
    }
    const payloadTree = requiredTree(targetTree, `${draft.revisionDirectory}/${resolved.path}`);
    if (payloadTree.gitBlobOid !== draft.entry.source.blobOid ||
      payloadTree.sizeBytes !== draft.entry.source.sizeBytes) {
      throw new Error(`committed target payload differs from protected source: ${draft.entry.source.path}`);
    }
    const sourceDigest = requiredDigest(protectedBlobDigests, draft.entry.source.blobOid);
    const declaredBinding = manifestSourceBinding(resolved.file, draft.target.category);
    return {
      source: attestTreeEntry(
        requiredTree(sourceLegacyTree, draft.entry.source.path),
        sourceCommitOid,
        sourceDigest.sha256,
      ),
      disposition: draft.entry.disposition,
      basis: draft.entry.basis,
      target: {
        category: draft.target.category,
        revisionKind: draft.target.revisionKind,
        revisionId: draft.target.revisionId,
        revisionRef: draft.ref,
        revisionDirectory: draft.revisionDirectory,
        plannedPayloadPath: draft.target.payloadPath,
        payloadPathResolution: resolved.path === draft.target.payloadPath
          ? "exact_plan_path"
          : "committed_reuse_binding",
        manifest: revision.manifestBinding,
        payload: attestTreeEntry(payloadTree, targetSnapshotCommitOid, sourceDigest.sha256),
        manifestSourceBinding: declaredBinding,
        manifestSourceCommitProof: {
          repositoryPath: declaredBinding.repositoryPath,
          mode: draft.entry.source.mode,
          gitBlobOid: declaredBinding.gitBlobOid,
          sizeBytes: sourceDigest.sizeBytes,
          gitCommitOid: declaredBinding.gitCommitOid,
          sha256: sourceDigest.sha256,
        },
      },
      exactPayloadBytes: true,
    };
  });
  await verifyManifestSourceCommitProofs(root, sourceRows, sourceCommitOid);

  const generatedFiles = generatedDrafts.map((draft): GeneratedFileAttestation => {
    const revision = requiredRevision(revisions, draft.manifestPath, draft.ref);
    const category = draft.ref.kind === "composition" ? "durable" : "input";
    const file = manifestFile(revision.manifest, draft.generated.path, category);
    const bytes = requiredBlob(blobs, draft.payloadTree.gitBlobOid);
    validateManifestPayload(file, category, sha256(bytes), bytes.byteLength);
    return {
      revisionSlot: draft.generated.revisionSlot,
      basis: draft.generated.basis,
      revisionRef: draft.ref,
      revisionDirectory: draft.revisionDirectory,
      manifest: revision.manifestBinding,
      payload: attestTreeEntry(draft.payloadTree, targetSnapshotCommitOid, sha256(bytes)),
      manifestGenerationBasis: generationBasis(file, category),
    };
  });

  const historicalCompositions = compositionDrafts.map((draft): HistoricalCompositionAttestation => {
    const revision = requiredRevision(revisions, draft.manifestPath, draft.ref);
    const file = manifestFile(revision.manifest, "composition.yaml", "durable");
    const bytes = requiredBlob(blobs, draft.payloadTree.gitBlobOid);
    validateManifestPayload(file, "durable", sha256(bytes), bytes.byteLength);
    return {
      ...draft.composition,
      revisionRef: draft.ref,
      revisionDirectory: draft.revisionDirectory,
      manifest: revision.manifestBinding,
      payload: attestTreeEntry(draft.payloadTree, targetSnapshotCommitOid, sha256(bytes)),
      manifestGenerationBasis: generationBasis(file, "durable"),
    };
  });

  const preExistingEdition4ImageFiles = edition4Pairs.map(({ source, target }) => {
    const bytes = requiredBlob(blobs, source.gitBlobOid);
    const digest = sha256(bytes);
    return {
      source: attestTreeEntry(source, sourceCommitOid, digest),
      target: attestTreeEntry(target, targetSnapshotCommitOid, digest),
      unchanged: true as const,
    };
  });

  const planManifestBytes = requiredBlob(initialBlobs, planManifestTreeEntry.gitBlobOid);
  const result: LegacyMigrationAttestation = {
    schemaVersion: "legacy-migration-attestation/1",
    migrationId: plan.migrationId,
    migrationPlan: {
      revision: { kind: "migration_plan", logicalId: plan.migrationId, revisionId: planRevisionId },
      manifest: attestTreeEntry(planManifestTreeEntry, targetSnapshotCommitOid, sha256(planManifestBytes)),
      inventory: attestTreeEntry(planTreeEntry, targetSnapshotCommitOid, sha256(planBytes)),
    },
    protectedSource: {
      commitOid: sourceCommitOid,
      canonicalInventorySha256: plan.sourceSnapshot.canonicalInventorySha256,
      fileCount: plan.sourceSnapshot.files.length,
      sizeBytes: plan.sourceSnapshot.files.reduce((total, file) => total + file.sizeBytes, 0),
    },
    targetSnapshotCommitOid,
    sourceRows,
    generatedFiles,
    historicalCompositions,
    preExistingEdition4ImageFiles,
    summary: {
      sourceRows: sourceRows.length,
      sourceBytes: sourceRows.reduce((total, row) => total + row.source.sizeBytes, 0),
      dispositions: dispositionCounts(sourceRows),
      generatedFiles: generatedFiles.length,
      historicalCompositions: historicalCompositions.length,
      preExistingEdition4ImageFiles: preExistingEdition4ImageFiles.length,
    },
    cutover: {
      status: "ready_for_atomic_legacy_root_deletion",
      protectedSourceCommitRecoverable: true,
      allLegacyFilesAccountedFor: true,
      allTargetsCommitted: true,
      exactPayloadBytes: true,
      generatedPlanFilesCommitted: true,
      preExistingEdition4ImageBlobOidsUnchanged: true,
      releaseAuthorityImported: false,
      freshRunEngineReviewStillRequired: true,
    },
  };
  verifyLegacyMigrationAttestation(result, plan);
  if (targetSnapshotCommitOid !== headCommitOid) {
    const headTree = await readGitTree(root, headCommitOid, ["inputs", "durable"]);
    verifyAttestedTargetFilesStillCurrent(result, targetTree, headTree);
  }
  return result;
}

export async function materializeLegacyMigrationAttestation(
  repositoryRoot: string,
  sourceCommitish: string,
  planRevisionId: RevisionId,
  revisionId: RevisionId = newRevisionId(),
  targetSnapshotCommitish = "HEAD",
): Promise<MaterializedLegacyMigrationAttestation> {
  const root = resolve(repositoryRoot);
  const ref: InputRevisionRef = {
    kind: "migration_attestation",
    logicalId: MIGRATION_ID,
    revisionId: parseRevisionId(revisionId),
  };
  const destination = join(root, "inputs", inputRevisionRelativeDirectory(ref));
  if (await exists(destination)) throw new Error(`migration attestation already exists: ${destination}`);
  const attestation = await buildLegacyMigrationAttestation(
    root,
    sourceCommitish,
    planRevisionId,
    targetSnapshotCommitish,
  );
  const destinationParent = dirname(destination);
  await mkdir(destinationParent, { recursive: true, mode: 0o700 });
  const candidate = await mkdtemp(join(destinationParent, ".legacy-attestation-stage-"));
  try {
    const payload = serializeLegacyMigrationAttestation(attestation);
    const manifest = Buffer.from(stringify({
      schema_version: 1,
      revision_kind: "migration_attestation",
      logical_id: MIGRATION_ID,
      revision_id: revisionId,
      created_at: revisionInstant(revisionId),
      parent_revision_id: null,
      migration_id: MIGRATION_ID,
      files: [{
        path: "attestation.yaml",
        media_type: "application/yaml",
        sha256: sha256(payload),
        size_bytes: payload.byteLength,
        generated_by_migration: {
          basis: `exact cutover proof for ${attestation.protectedSource.commitOid} into ${attestation.targetSnapshotCommitOid} under plan ${planRevisionId}`,
        },
      }],
    }, { lineWidth: 0 }), "utf8");
    await writeFile(join(candidate, "attestation.yaml"), payload, { flag: "wx", mode: 0o600 });
    await writeFile(join(candidate, "manifest.yaml"), manifest, { flag: "wx", mode: 0o600 });
    await validateInputRevisionTree(candidate, ref);
    await rename(candidate, destination);
    await validateInputRevisionTree(destination, ref);
    const relative = join("inputs", inputRevisionRelativeDirectory(ref));
    return {
      ref,
      repositoryPaths: [`${relative}/attestation.yaml`, `${relative}/manifest.yaml`].sort(),
      attestation,
    };
  } finally {
    await rm(candidate, { recursive: true, force: true });
  }
}

export function verifyLegacyMigrationAttestation(
  attestation: LegacyMigrationAttestation,
  plan: LegacyRootMigrationPlan,
): void {
  verifyLegacyRootMigrationPlan(plan);
  if (attestation.schemaVersion !== "legacy-migration-attestation/1" ||
    attestation.migrationId !== plan.migrationId ||
    attestation.protectedSource.commitOid !== plan.sourceSnapshot.sourceCommitOid ||
    attestation.protectedSource.canonicalInventorySha256 !== plan.sourceSnapshot.canonicalInventorySha256 ||
    attestation.protectedSource.fileCount !== plan.sourceSnapshot.files.length ||
    attestation.protectedSource.sizeBytes !== plan.sourceSnapshot.files.reduce((total, file) => total + file.sizeBytes, 0)) {
    throw new Error("migration attestation source identity does not match its plan");
  }
  const planByPath = new Map(plan.files.map((entry) => [entry.source.path, entry]));
  if (attestation.sourceRows.length !== plan.files.length ||
    new Set(attestation.sourceRows.map((row) => row.source.repositoryPath)).size !== plan.files.length) {
    throw new Error("migration attestation does not contain one row per protected source file");
  }
  for (const row of attestation.sourceRows) {
    const planned = planByPath.get(row.source.repositoryPath);
    if (planned === undefined || row.disposition !== planned.disposition || row.basis !== planned.basis ||
      row.source.gitCommitOid !== plan.sourceSnapshot.sourceCommitOid ||
      row.source.gitBlobOid !== planned.source.blobOid || row.source.sha256 !== planned.source.sha256 ||
      row.source.sizeBytes !== planned.source.sizeBytes || row.target.payload.gitBlobOid !== row.source.gitBlobOid ||
      row.target.payload.sha256 !== row.source.sha256 || row.target.payload.sizeBytes !== row.source.sizeBytes ||
      row.target.payload.gitCommitOid !== attestation.targetSnapshotCommitOid || row.exactPayloadBytes !== true) {
      throw new Error(`migration attestation row differs from its plan: ${row.source.repositoryPath}`);
    }
    const target = planned.targets[0];
    if (target === undefined || row.target.category !== target.category ||
      row.target.revisionKind !== target.revisionKind || row.target.revisionId !== target.revisionId ||
      row.target.plannedPayloadPath !== target.payloadPath ||
      (row.target.payloadPathResolution === "committed_reuse_binding" && row.disposition !== "reuse_existing") ||
      (row.target.payloadPathResolution === "exact_plan_path" &&
        row.target.payload.repositoryPath !== `${row.target.revisionDirectory}/${target.payloadPath}`)) {
      throw new Error(`migration attestation target differs from its plan: ${row.source.repositoryPath}`);
    }
    const declared = row.target.manifestSourceBinding;
    const proof = row.target.manifestSourceCommitProof;
    if (declared.repositoryPath !== row.source.repositoryPath || declared.gitBlobOid !== row.source.gitBlobOid ||
      proof.repositoryPath !== declared.repositoryPath || proof.gitCommitOid !== declared.gitCommitOid ||
      proof.gitBlobOid !== declared.gitBlobOid || proof.sha256 !== row.source.sha256 ||
      proof.sizeBytes !== row.source.sizeBytes || proof.mode !== row.source.mode ||
      (row.disposition !== "reuse_existing" && declared.gitCommitOid !== attestation.protectedSource.commitOid)) {
      throw new Error(`migration attestation manifest source proof is invalid: ${row.source.repositoryPath}`);
    }
  }
  if (attestation.generatedFiles.length !== plan.generatedFiles.length ||
    !sameStrings(attestation.generatedFiles.map(generatedKey), plan.generatedFiles.map(generatedKey))) {
    throw new Error("migration attestation generated-file inventory differs from its plan");
  }
  if (attestation.historicalCompositions.length !== plan.historicalCompositions.length ||
    !sameStrings(
      attestation.historicalCompositions.map(compositionKey),
      plan.historicalCompositions.map(compositionKey),
    )) {
    throw new Error("migration attestation composition inventory differs from its plan");
  }
  if (attestation.preExistingEdition4ImageFiles.length === 0 ||
    attestation.preExistingEdition4ImageFiles.some((entry) => entry.unchanged !== true ||
      entry.source.repositoryPath !== entry.target.repositoryPath ||
      entry.source.gitBlobOid !== entry.target.gitBlobOid ||
      entry.source.sha256 !== entry.target.sha256 ||
      entry.source.sizeBytes !== entry.target.sizeBytes)) {
    throw new Error("migration attestation does not preserve pre-existing Edition 4 image blobs");
  }
  const expectedDispositions = dispositionCounts(attestation.sourceRows);
  if (attestation.summary.sourceRows !== attestation.sourceRows.length ||
    attestation.summary.sourceBytes !== attestation.sourceRows.reduce((sum, row) => sum + row.source.sizeBytes, 0) ||
    attestation.summary.dispositions.import_exact !== expectedDispositions.import_exact ||
    attestation.summary.dispositions.reuse_existing !== expectedDispositions.reuse_existing ||
    attestation.summary.dispositions.archive_non_authoritative !== expectedDispositions.archive_non_authoritative ||
    attestation.summary.dispositions.retire_housekeeping !== expectedDispositions.retire_housekeeping ||
    attestation.summary.generatedFiles !== attestation.generatedFiles.length ||
    attestation.summary.historicalCompositions !== attestation.historicalCompositions.length ||
    attestation.summary.preExistingEdition4ImageFiles !== attestation.preExistingEdition4ImageFiles.length) {
    throw new Error("migration attestation summary is inconsistent");
  }
  if (attestation.cutover.status !== "ready_for_atomic_legacy_root_deletion" ||
    attestation.cutover.protectedSourceCommitRecoverable !== true ||
    attestation.cutover.allLegacyFilesAccountedFor !== true ||
    attestation.cutover.allTargetsCommitted !== true ||
    attestation.cutover.exactPayloadBytes !== true ||
    attestation.cutover.generatedPlanFilesCommitted !== true ||
    attestation.cutover.preExistingEdition4ImageBlobOidsUnchanged !== true ||
    attestation.cutover.releaseAuthorityImported !== false ||
    attestation.cutover.freshRunEngineReviewStillRequired !== true) {
    throw new Error("migration attestation is not cutover-ready");
  }
}

export async function readCommittedLegacyMigrationAttestation(
  repositoryRoot: string,
  revisionId: RevisionId,
): Promise<LegacyMigrationAttestation> {
  const ref: InputRevisionRef = { kind: "migration_attestation", logicalId: MIGRATION_ID, revisionId };
  const path = join(resolve(repositoryRoot), "inputs", inputRevisionRelativeDirectory(ref), "attestation.yaml");
  return parse(await readFile(path, "utf8")) as LegacyMigrationAttestation;
}

type RevisionBinding = {
  readonly ref: InputRevisionRef | DurableRevisionRef;
  readonly revisionDirectory: string;
  readonly manifestPath: string;
  readonly manifestTree: GitTreeEntry;
};

type ResolvedRevisionBinding = RevisionBinding & {
  readonly manifest: Record<string, unknown>;
  readonly manifestBinding: AttestedGitFile;
};

type SourceTargetDraft = RevisionBinding & {
  readonly entry: LegacyFileDisposition;
  readonly target: LegacyMigrationTarget;
};

function targetRef(target: LegacyMigrationTarget, migrationId: string): InputRevisionRef | DurableRevisionRef {
  if (target.category === "durable") {
    const identity = target.durableIdentity;
    if (identity === undefined) throw new Error(`durable target has no public identity: ${target.revisionSlot}`);
    if (target.revisionKind === "image") {
      return {
        kind: "image",
        editionId: identity.editionId,
        logicalId: identity.logicalId,
        revisionId: target.revisionId,
      };
    }
    if ((target.revisionKind !== "article" && target.revisionKind !== "editorial") || identity.language === undefined) {
      throw new Error(`durable target identity does not match its kind: ${target.revisionSlot}`);
    }
    return {
      kind: target.revisionKind,
      editionId: identity.editionId,
      logicalId: identity.logicalId,
      language: identity.language,
      revisionId: target.revisionId,
    };
  }
  const logical = target.revisionSlot.split(":").slice(2).join(":");
  switch (target.revisionKind) {
    case "source_capture":
    case "source_extraction":
    case "prompt":
    case "policy":
      return { kind: target.revisionKind, logicalId: logical, revisionId: target.revisionId };
    case "edition_spec":
      return {
        kind: "edition_spec",
        editionId: logical === "004-rerun" ? "004" : logical,
        logicalId: logical === "004-rerun" ? "legacy-rerun" : "main",
        revisionId: target.revisionId,
      };
    case "migration_archive":
      return { kind: "migration_archive", logicalId: migrationId, revisionId: target.revisionId };
    default:
      throw new Error(`unsupported input target: ${target.revisionSlot}`);
  }
}

function generatedRef(plan: LegacyRootMigrationPlan, revisionSlot: string): InputRevisionRef | DurableRevisionRef {
  const matching = plan.files.map((file) => file.targets[0]!).find((target) => target.revisionSlot === revisionSlot);
  if (matching !== undefined) return targetRef(matching, plan.migrationId);
  const composition = plan.historicalCompositions.find((entry) =>
    revisionSlot === `durable:composition:${entry.editionId}:${entry.compositionId}`
  );
  if (composition === undefined) throw new Error(`generated file has no revision identity: ${revisionSlot}`);
  return {
    kind: "composition",
    editionId: composition.editionId,
    compositionId: composition.compositionId,
    revisionId: composition.revisionId,
  };
}

function targetRevisionDirectory(ref: InputRevisionRef | DurableRevisionRef): string {
  return ref.kind === "article" || ref.kind === "editorial" || ref.kind === "image" || ref.kind === "composition"
    ? `durable/${durableRevisionRelativeDirectory(ref)}`
    : `inputs/${inputRevisionRelativeDirectory(ref)}`;
}

function validateManifestIdentity(manifest: Record<string, unknown>, ref: InputRevisionRef | DurableRevisionRef): void {
  if (manifest.revision_kind !== ref.kind || manifest.revision_id !== ref.revisionId) {
    throw new Error(`committed target manifest identity differs from ${JSON.stringify(ref)}`);
  }
  if ("editionId" in ref && manifest.edition_id !== ref.editionId) {
    throw new Error(`committed target manifest edition differs from ${JSON.stringify(ref)}`);
  }
  if (ref.kind === "composition") {
    if (manifest.composition_id !== ref.compositionId) throw new Error("composition manifest logical identity differs");
  } else if (manifest.logical_id !== ref.logicalId) {
    throw new Error(`committed target manifest logical identity differs from ${JSON.stringify(ref)}`);
  }
  if ((ref.kind === "article" || ref.kind === "editorial") && manifest.language !== ref.language) {
    throw new Error(`committed target manifest language differs from ${JSON.stringify(ref)}`);
  }
}

function manifestFile(
  manifest: Record<string, unknown>,
  payloadPath: string,
  category: LegacyMigrationTarget["category"] | "input" | "durable",
): Record<string, unknown> {
  const files = manifest.files;
  if (!Array.isArray(files)) throw new Error("committed target manifest has no files array");
  const file = files.find((candidate) => mapping(candidate, "manifest file").path === payloadPath);
  if (file === undefined) throw new Error(`committed target manifest does not declare ${payloadPath}`);
  const result = mapping(file, `manifest file ${payloadPath}`);
  if (category === "archive" && manifest.revision_kind !== "migration_archive") {
    throw new Error("archive target is not a migration archive revision");
  }
  return result;
}

function exactManifestFile(
  manifest: Record<string, unknown>,
  entry: LegacyFileDisposition,
  category: LegacyMigrationTarget["category"],
  plannedPayloadPath: string,
): { readonly file: Record<string, unknown>; readonly path: string } {
  const files = manifest.files;
  if (!Array.isArray(files)) throw new Error("committed target manifest has no files array");
  const candidates = files.map((value) => mapping(value, "manifest file")).filter((file) => {
    try {
      const binding = manifestSourceBinding(file, category);
      return binding.repositoryPath === entry.source.path && binding.gitBlobOid === entry.source.blobOid;
    } catch {
      return false;
    }
  });
  if (candidates.length !== 1) {
    throw new Error(`target manifest has ${candidates.length} exact bindings for ${entry.source.path}`);
  }
  const file = candidates[0]!;
  if (typeof file.path !== "string") throw new Error(`target manifest payload path is invalid for ${entry.source.path}`);
  validateManifestPayload(file, category, entry.source.sha256, entry.source.sizeBytes);
  const binding = manifestSourceBinding(file, category);
  if (binding.repositoryPath !== entry.source.path || binding.gitBlobOid !== entry.source.blobOid) {
    throw new Error(`target manifest provenance differs from protected source: ${entry.source.path}`);
  }
  if (file.path !== plannedPayloadPath && entry.disposition !== "reuse_existing") {
    throw new Error(`target manifest path differs from the migration plan for ${entry.source.path}`);
  }
  return { file, path: file.path };
}

function validateManifestPayload(
  file: Record<string, unknown>,
  category: LegacyMigrationTarget["category"] | "input" | "durable",
  expectedSha256: string,
  expectedSize: number,
): void {
  const size = category === "durable" ? file.sizeBytes : file.size_bytes;
  if (file.sha256 !== expectedSha256 || size !== expectedSize) {
    throw new Error(`target manifest payload digest differs for ${String(file.path)}`);
  }
}

function manifestSourceBinding(
  file: Record<string, unknown>,
  category: LegacyMigrationTarget["category"],
): { readonly repositoryPath: string; readonly gitCommitOid: string; readonly gitBlobOid: string } {
  const value = category === "durable" ? file.legacySource : file.legacy_source;
  const binding = mapping(value, `legacy source binding for ${String(file.path)}`);
  if (typeof binding.repositoryPath !== "string" || typeof binding.gitCommitOid !== "string" ||
    typeof binding.gitBlobOid !== "string") {
    throw new Error(`legacy source binding is malformed for ${String(file.path)}`);
  }
  return {
    repositoryPath: binding.repositoryPath,
    gitCommitOid: binding.gitCommitOid,
    gitBlobOid: binding.gitBlobOid,
  };
}

function generationBasis(
  file: Record<string, unknown>,
  category: "input" | "durable",
): string {
  const provenance = mapping(
    category === "durable" ? file.migrationAssembly : file.generated_by_migration,
    `generation provenance for ${String(file.path)}`,
  );
  if (typeof provenance.basis !== "string" || provenance.basis.length === 0) {
    throw new Error(`generation basis is missing for ${String(file.path)}`);
  }
  return provenance.basis;
}

function assertSourceTreeEntry(
  entry: LegacyFileDisposition,
  tree: GitTreeEntry,
  commitOid: string,
): void {
  if (entry.source.path !== tree.repositoryPath || entry.source.mode !== tree.mode ||
    entry.source.blobOid !== tree.gitBlobOid || entry.source.sizeBytes !== tree.sizeBytes ||
    commitOid.length === 0) {
    throw new Error(`protected source tree differs from plan: ${entry.source.path}`);
  }
}

function verifyProtectedSourceTree(plan: LegacyRootMigrationPlan, tree: ReadonlyMap<string, GitTreeEntry>): void {
  if (tree.size !== plan.sourceSnapshot.files.length) {
    throw new Error(`protected source tree count differs from plan: ${tree.size}`);
  }
  for (const entry of plan.files) {
    assertSourceTreeEntry(entry, requiredTree(tree, entry.source.path), plan.sourceSnapshot.sourceCommitOid);
  }
}

function requiredRevision(
  revisions: ReadonlyMap<string, ResolvedRevisionBinding>,
  manifestPath: string,
  ref: InputRevisionRef | DurableRevisionRef,
): ResolvedRevisionBinding {
  const value = revisions.get(`${manifestPath}\0${JSON.stringify(ref)}`);
  if (value === undefined) throw new Error(`missing resolved target revision ${manifestPath}`);
  return value;
}

function attestTreeEntry(entry: GitTreeEntry, commitOid: string, digest: string): AttestedGitFile {
  return { ...entry, gitCommitOid: commitOid, sha256: digest };
}

function dispositionCounts(rows: readonly LegacySourceRowAttestation[]): Record<LegacyFileDisposition["disposition"], number> {
  return {
    import_exact: rows.filter((row) => row.disposition === "import_exact").length,
    reuse_existing: rows.filter((row) => row.disposition === "reuse_existing").length,
    archive_non_authoritative: rows.filter((row) => row.disposition === "archive_non_authoritative").length,
    retire_housekeeping: rows.filter((row) => row.disposition === "retire_housekeeping").length,
  };
}

function generatedKey(value: { readonly revisionSlot: string; readonly basis: string }): string {
  return `${value.revisionSlot}\0${value.basis}`;
}

function compositionKey(value: Pick<HistoricalCompositionPlan, "editionId" | "compositionId" | "revisionId" | "state">): string {
  return `${value.editionId}\0${value.compositionId}\0${value.revisionId}\0${value.state}`;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return JSON.stringify([...left].sort()) === JSON.stringify([...right].sort());
}

async function assertGitAncestor(
  repositoryRoot: string,
  ancestorCommitOid: string,
  descendantCommitOid: string,
): Promise<void> {
  try {
    await execFile("git", ["merge-base", "--is-ancestor", ancestorCommitOid, descendantCommitOid], {
      cwd: repositoryRoot,
      encoding: "utf8",
    });
  } catch (error) {
    throw new Error(
      `explicit target snapshot ${ancestorCommitOid} is not an ancestor of HEAD ${descendantCommitOid}`,
      { cause: error },
    );
  }
}

function verifyAttestedTargetFilesStillCurrent(
  attestation: LegacyMigrationAttestation,
  targetTree: ReadonlyMap<string, GitTreeEntry>,
  headTree: ReadonlyMap<string, GitTreeEntry>,
): void {
  const paths = new Set<string>([
    attestation.migrationPlan.manifest.repositoryPath,
    attestation.migrationPlan.inventory.repositoryPath,
    ...attestation.sourceRows.flatMap((row) => [
      row.target.manifest.repositoryPath,
      row.target.payload.repositoryPath,
    ]),
    ...attestation.generatedFiles.flatMap((entry) => [
      entry.manifest.repositoryPath,
      entry.payload.repositoryPath,
    ]),
    ...attestation.historicalCompositions.flatMap((entry) => [
      entry.manifest.repositoryPath,
      entry.payload.repositoryPath,
    ]),
    ...attestation.preExistingEdition4ImageFiles.map((entry) => entry.target.repositoryPath),
  ]);
  for (const path of paths) {
    const target = requiredTree(targetTree, path);
    const current = requiredTree(headTree, path);
    if (target.mode !== current.mode || target.gitBlobOid !== current.gitBlobOid ||
      target.sizeBytes !== current.sizeBytes) {
      throw new Error(`explicit target snapshot migration file differs from HEAD: ${path}`);
    }
  }
}

export async function verifyManifestSourceCommitProofs(
  repositoryRoot: string,
  rows: readonly LegacySourceRowAttestation[],
  protectedSourceCommitOid: string,
): Promise<void> {
  const byCommit = new Map<string, LegacySourceRowAttestation[]>();
  for (const row of rows) {
    const commit = row.target.manifestSourceBinding.gitCommitOid;
    if (!/^[0-9a-f]{40,64}$/u.test(commit)) {
      throw new Error(`target manifest has an invalid source commit: ${row.source.repositoryPath}`);
    }
    if (row.disposition !== "reuse_existing" && commit !== protectedSourceCommitOid) {
      throw new Error(`new target manifest does not bind the protected source commit: ${row.source.repositoryPath}`);
    }
    const current = byCommit.get(commit) ?? [];
    current.push(row);
    byCommit.set(commit, current);
  }
  for (const [commit, matchingRows] of byCommit) {
    let resolved: string;
    try {
      resolved = await gitText(repositoryRoot, ["rev-parse", `${commit}^{commit}`]);
    } catch (error) {
      throw new Error(`manifest source commit is not recoverable: ${commit}`, { cause: error });
    }
    if (resolved !== commit) throw new Error(`manifest source commit is not exact: ${commit}`);
    const tree = await readGitTree(repositoryRoot, commit, [...LEGACY_ROOTS]);
    for (const row of matchingRows) {
      const proof = row.target.manifestSourceCommitProof;
      const actual = requiredTree(tree, proof.repositoryPath);
      if (actual.mode !== proof.mode || actual.gitBlobOid !== proof.gitBlobOid ||
        actual.sizeBytes !== proof.sizeBytes || proof.gitCommitOid !== commit ||
        proof.sha256 !== row.source.sha256) {
        throw new Error(`manifest-declared source binding is not exact: ${proof.repositoryPath}`);
      }
    }
  }
}

async function hashGitBlobs(
  repositoryRoot: string,
  requestedOids: readonly string[],
): Promise<ReadonlyMap<string, GitBlobDigest>> {
  const oids = [...new Set(requestedOids)];
  if (oids.length === 0) return new Map();
  const child = spawn("git", ["cat-file", "--batch"], {
    cwd: repositoryRoot,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const stderr: Buffer[] = [];
  child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
  const closed = new Promise<void>((accept, reject) => {
    child.on("error", reject);
    child.on("close", (code) => code === 0
      ? accept()
      : reject(new Error(`git cat-file failed (${code ?? "signal"}): ${Buffer.concat(stderr).toString("utf8")}`)));
  });
  child.stdin.end(`${oids.join("\n")}\n`, "utf8");

  const result = new Map<string, GitBlobDigest>();
  let buffer = Buffer.alloc(0);
  let index = 0;
  let active: {
    readonly oid: string;
    readonly sizeBytes: number;
    readonly hash: ReturnType<typeof createHash>;
    remaining: number;
  } | undefined;
  for await (const value of child.stdout) {
    const chunk = Buffer.isBuffer(value) ? value : Buffer.from(value);
    buffer = buffer.byteLength === 0 ? chunk : Buffer.concat([buffer, chunk]);
    while (true) {
      if (active === undefined) {
        const newline = buffer.indexOf(0x0a);
        if (newline < 0) break;
        const expectedOid = oids[index];
        if (expectedOid === undefined) throw new Error("git cat-file returned an unexpected blob");
        const header = buffer.subarray(0, newline).toString("utf8");
        const match = /^([0-9a-f]{40,64}) blob (\d+)$/u.exec(header);
        if (match === null || match[1] !== expectedOid) {
          throw new Error(`git cat-file returned an invalid header for ${expectedOid}`);
        }
        const sizeBytes = Number(match[2]!);
        if (!Number.isSafeInteger(sizeBytes) || sizeBytes < 0) {
          throw new Error(`git cat-file returned an invalid size for ${expectedOid}`);
        }
        active = { oid: expectedOid, sizeBytes, remaining: sizeBytes, hash: createHash("sha256") };
        buffer = buffer.subarray(newline + 1);
      }
      if (active.remaining > 0) {
        if (buffer.byteLength === 0) break;
        const take = Math.min(active.remaining, buffer.byteLength);
        active.hash.update(buffer.subarray(0, take));
        active.remaining -= take;
        buffer = buffer.subarray(take);
        if (active.remaining > 0) break;
      }
      if (buffer.byteLength === 0) break;
      if (buffer[0] !== 0x0a) throw new Error(`git cat-file truncated blob ${active.oid}`);
      buffer = buffer.subarray(1);
      result.set(active.oid, {
        sha256: `sha256:${active.hash.digest("hex")}`,
        sizeBytes: active.sizeBytes,
      });
      active = undefined;
      index += 1;
    }
  }
  await closed;
  if (active !== undefined || buffer.byteLength !== 0 || index !== oids.length) {
    throw new Error("git cat-file did not return every requested protected blob");
  }
  return result;
}

async function readGitTree(
  repositoryRoot: string,
  commitOid: string,
  paths: readonly string[],
): Promise<ReadonlyMap<string, GitTreeEntry>> {
  const bytes = await gitBuffer(repositoryRoot, ["ls-tree", "-r", "-l", "-z", commitOid, "--", ...paths]);
  const result = new Map<string, GitTreeEntry>();
  for (const record of bytes.toString("utf8").split("\0").filter((value) => value.length > 0)) {
    const tab = record.indexOf("\t");
    if (tab < 0) throw new Error("git ls-tree returned a malformed record");
    const metadata = record.slice(0, tab);
    const repositoryPath = record.slice(tab + 1);
    const match = /^(\d{6}) blob ([0-9a-f]{40,64})\s+(\d+)$/u.exec(metadata);
    if (match === null) throw new Error(`git tree contains an unsupported entry: ${repositoryPath}`);
    const entry: GitTreeEntry = {
      repositoryPath,
      mode: match[1]!,
      gitBlobOid: match[2]!,
      sizeBytes: Number(match[3]!),
    };
    if (!Number.isSafeInteger(entry.sizeBytes) || result.has(repositoryPath)) {
      throw new Error(`git tree contains an invalid or duplicate entry: ${repositoryPath}`);
    }
    result.set(repositoryPath, entry);
  }
  return result;
}

async function readGitBlobs(
  repositoryRoot: string,
  requestedOids: readonly string[],
): Promise<ReadonlyMap<string, Buffer>> {
  const oids = [...new Set(requestedOids)];
  if (oids.length === 0) return new Map();
  const child = spawn("git", ["cat-file", "--batch"], {
    cwd: repositoryRoot,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
  child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
  const done = new Promise<void>((accept, reject) => {
    child.on("error", reject);
    child.on("close", (code) => code === 0
      ? accept()
      : reject(new Error(`git cat-file failed (${code ?? "signal"}): ${Buffer.concat(stderr).toString("utf8")}`)));
  });
  child.stdin.end(`${oids.join("\n")}\n`, "utf8");
  await done;
  const bytes = Buffer.concat(stdout);
  const result = new Map<string, Buffer>();
  let offset = 0;
  for (const oid of oids) {
    const newline = bytes.indexOf(0x0a, offset);
    if (newline < 0) throw new Error(`git cat-file omitted header for ${oid}`);
    const header = bytes.subarray(offset, newline).toString("utf8");
    const match = /^([0-9a-f]{40,64}) blob (\d+)$/u.exec(header);
    if (match === null || match[1] !== oid) throw new Error(`git cat-file returned an invalid header for ${oid}`);
    const size = Number(match[2]!);
    const start = newline + 1;
    const end = start + size;
    if (bytes[end] !== 0x0a) throw new Error(`git cat-file truncated blob ${oid}`);
    result.set(oid, bytes.subarray(start, end));
    offset = end + 1;
  }
  if (offset !== bytes.byteLength) throw new Error("git cat-file returned trailing data");
  return result;
}

function requiredTree(tree: ReadonlyMap<string, GitTreeEntry>, path: string): GitTreeEntry {
  const value = tree.get(path);
  if (value === undefined) throw new Error(`committed migration target is missing: ${path}`);
  return value;
}

function requiredBlob(blobs: ReadonlyMap<string, Buffer>, oid: string): Buffer {
  const value = blobs.get(oid);
  if (value === undefined) throw new Error(`Git blob was not loaded: ${oid}`);
  return value;
}

function requiredDigest(digests: ReadonlyMap<string, GitBlobDigest>, oid: string): GitBlobDigest {
  const value = digests.get(oid);
  if (value === undefined) throw new Error(`Git blob digest was not computed: ${oid}`);
  return value;
}

function mapping(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} is not a mapping`);
  }
  return value as Record<string, unknown>;
}

function byPath(left: GitTreeEntry, right: GitTreeEntry): number {
  return left.repositoryPath.localeCompare(right.repositoryPath);
}

function planRepositoryPath(revisionId: RevisionId, name: "inventory.yaml" | "manifest.yaml"): string {
  return `inputs/migrations/${MIGRATION_ID}/revisions/${revisionId}/${name}`;
}

function revisionInstant(revisionId: RevisionId): string {
  const match = /^rev_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z_/u.exec(revisionId);
  if (match === null) throw new Error(`cannot read RevisionId time: ${revisionId}`);
  return `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}.${match[7]}Z`;
}

function sha256(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

async function gitText(root: string, args: readonly string[]): Promise<string> {
  const result = await execFile("git", args, { cwd: root, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  return result.stdout.trim();
}

async function gitBuffer(root: string, args: readonly string[]): Promise<Buffer> {
  const result = await execFile("git", args, { cwd: root, encoding: "buffer", maxBuffer: 64 * 1024 * 1024 });
  return Buffer.from(result.stdout);
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if (typeof error === "object" && error !== null && "code" in error && error.code === "ENOENT") return false;
    throw error;
  }
}
