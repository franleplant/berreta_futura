import { createHash } from "node:crypto";
import {
  access,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";

import { parse, stringify } from "yaml";

import type {
  ArtifactId,
  ArtifactView,
  JsonObject,
  RunView,
} from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/index.ts";
import {
  durableRevisionParentRelativeDirectory,
  durableRevisionRelativeDirectory,
} from "./paths.ts";
import { resolveInputRevision } from "./input-revision.ts";
import { parseRevisionId } from "./revision-id.ts";
import { parseCompositionDocument } from "./composition-schema.ts";
import type {
  DurableCheckpointResult,
  DurableFileRecord,
  DurableGit,
  DurableLogicalItem,
  DurablePromotionRequest,
  DurableRevisionManifest,
  DurableRevisionRef,
  GitRevisionBinding,
  ResolvedDurableRevision,
} from "./types.ts";

type PromotionEngine = Pick<RunEngine, "inspect" | "readArtifact">;

export type DurableStoreOptions = {
  readonly repositoryRoot: string;
  readonly workRoot: string;
  readonly git: DurableGit;
  readonly clock?: { now(): Date };
};

export type ValidatedDurableRevisionTree = {
  readonly manifest: DurableRevisionManifest;
  readonly manifestDigest: string;
  readonly payloadPaths: readonly string[];
};

export class DurableStoreError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "DurableStoreError";
    this.code = code;
  }
}

/**
 * The only write seam from accepted EngineArtifacts into Git-backed reusable
 * editorial state. Paths, filenames, provenance, and Git binding are derived
 * and validated here rather than composed by workflow callers.
 */
export class DurableStore {
  readonly repositoryRoot: string;
  readonly inputsRoot: string;
  readonly durableRoot: string;
  readonly workRoot: string;
  private readonly git: DurableGit;
  private readonly clock: { now(): Date };

  constructor(options: DurableStoreOptions) {
    this.repositoryRoot = resolve(options.repositoryRoot);
    this.inputsRoot = join(this.repositoryRoot, "inputs");
    this.durableRoot = join(this.repositoryRoot, "durable");
    this.workRoot = resolve(options.workRoot);
    this.git = options.git;
    this.clock = options.clock ?? { now: () => new Date() };
  }

  async promote(
    engine: PromotionEngine,
    rawRequest: DurablePromotionRequest,
  ): Promise<DurableCheckpointResult> {
    const request = normalizePromotionRequest(rawRequest);
    validateRequest(request);
    const view = await engine.inspect(request.runId);
    const artifacts = validateEngineReferences(view, request);
    await Promise.all(request.inputRevisions.map((ref) =>
      resolveInputRevision(this.repositoryRoot, ref, this.git)
    ));

    const revisionRef: DurableRevisionRef = {
      ...request.logicalItem,
      revisionId: request.revisionId,
    };
    const relativeDirectory = join("durable", durableRevisionRelativeDirectory(revisionRef));
    const destination = containedPath(this.repositoryRoot, relativeDirectory);
    const parentDirectory = containedPath(
      this.durableRoot,
      durableRevisionParentRelativeDirectory(request.logicalItem),
    );
    await validateExpectedParent(
      parentDirectory,
      request.logicalItem,
      request.expectedParentRevisionId,
      request.promotionId,
      this.repositoryRoot,
      this.git,
    );

    const existing = await loadExistingManifest(destination);
    let manifest: DurableRevisionManifest;
    let manifestBytes: Buffer;
    if (existing !== undefined) {
      const materialized = await materializeRecords(engine, request, artifacts);
      manifest = buildManifest(request, materialized.records, existing.manifest.created_at);
      manifestBytes = encodeManifest(manifest);
      if (
        existing.bytes.compare(manifestBytes) !== 0 ||
        existing.manifest.provenance_kind !== "engine_promotion" ||
        existing.manifest.promotion_id !== request.promotionId
      ) {
        throw integrityConflict(`revision target ${relativeDirectory} contains different bytes`);
      }
      await verifyMaterializedFiles(destination, materialized.files);
    } else {
      const materialized = await materializeRecords(engine, request, artifacts);
      manifest = buildManifest(request, materialized.records, this.clock.now().toISOString());
      manifestBytes = encodeManifest(manifest);
      await mkdir(this.workRoot, { recursive: true, mode: 0o700 });
      const candidate = await mkdtemp(join(this.workRoot, `${request.promotionId}-`));
      try {
        for (const file of materialized.files) {
          const path = containedPath(candidate, file.path);
          await mkdir(dirname(path), { recursive: true, mode: 0o700 });
          await writeFile(path, file.bytes, { mode: 0o600 });
        }
        await writeFile(join(candidate, "manifest.yaml"), manifestBytes, { mode: 0o600 });
        await verifyCandidate(candidate, manifest);
        await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
        try {
          await rename(candidate, destination);
        } catch (error) {
          if (await exists(destination)) {
            const raced = await loadExistingManifest(destination);
            if (raced === undefined || raced.bytes.compare(manifestBytes) !== 0) {
              throw integrityConflict(`revision target ${relativeDirectory} raced with different bytes`, error);
            }
          } else {
            throw error;
          }
        }
      } catch (error) {
        await rm(candidate, { recursive: true, force: true });
        throw error;
      }
    }

    const manifestDigest = digest(manifestBytes);
    const repositoryPaths = [
      join(relativeDirectory, "manifest.yaml"),
      ...manifest.files.map((file) => join(relativeDirectory, file.path)),
    ].sort();
    const binding = await this.git.checkpoint({
      promotionId: request.promotionId,
      revision: revisionRef,
      revisionDirectory: destination,
      repositoryPaths,
      manifestDigest,
    });
    validateGitBinding(binding, repositoryPaths);
    return checkpointResult(request, revisionRef, relativeDirectory, manifestDigest, binding);
  }
}

/**
 * Reads a Git-backed revision by its complete public identity. Renderers and
 * composition resolution use this instead of interpreting directory presence
 * as authority.
 */
export async function resolveDurableRevision(
  repositoryRoot: string,
  ref: DurableRevisionRef,
  git: Pick<DurableGit, "assertCommitted">,
  expected?: {
    readonly manifestDigest?: string;
    readonly gitBinding?: GitRevisionBinding;
  },
): Promise<ResolvedDurableRevision> {
  const root = resolve(repositoryRoot);
  const relativeDirectory = join("durable", durableRevisionRelativeDirectory(ref));
  const absoluteDirectory = containedPath(root, relativeDirectory);
  const validated = await validateDurableRevisionTree(absoluteDirectory, ref);
  const manifestDigest = validated.manifestDigest;
  if (expected?.manifestDigest !== undefined && expected.manifestDigest !== manifestDigest) {
    throw integrityConflict(`durable revision ${relativeDirectory} has the wrong manifest digest`);
  }
  const repositoryPaths = [
    join(relativeDirectory, "manifest.yaml"),
    ...validated.manifest.files.map((file) => join(relativeDirectory, file.path)),
  ].sort();
  if (expected?.gitBinding !== undefined) {
    validateGitBinding(expected.gitBinding, repositoryPaths);
  }
  try {
    await git.assertCommitted(repositoryPaths, expected?.gitBinding);
  } catch (error) {
    throw new DurableStoreError(
      "DURABLE_REVISION_UNCOMMITTED",
      `durable revision ${relativeDirectory} is not committed exactly`,
      { cause: error },
    );
  }
  return {
    ref,
    manifest: validated.manifest,
    manifestDigest,
    relativeDirectory,
    absoluteDirectory,
    repositoryPaths,
    payloadPaths: Object.fromEntries(validated.manifest.files.map((file) => [
      file.path,
      containedPath(absoluteDirectory, file.path),
    ])),
  };
}

/** Validates an immutable durable tree before a scoped bootstrap commit. */
export async function validateDurableRevisionTree(
  absoluteDirectory: string,
  ref: DurableRevisionRef,
): Promise<ValidatedDurableRevisionTree> {
  const loaded = await loadExistingManifest(absoluteDirectory);
  if (loaded === undefined) {
    throw new DurableStoreError(
      "DURABLE_REVISION_MISSING",
      `durable revision ${absoluteDirectory} does not exist`,
    );
  }
  if (loaded.manifest.revision_id !== ref.revisionId) {
    throw integrityConflict(`durable revision ${absoluteDirectory} disagrees with its manifest`);
  }
  validateManifestLogicalItem(loaded.manifest, ref);
  await verifyCandidate(absoluteDirectory, loaded.manifest);
  return {
    manifest: loaded.manifest,
    manifestDigest: digest(loaded.bytes),
    payloadPaths: loaded.manifest.files.map((file) => file.path),
  };
}

function validateRequest(request: DurablePromotionRequest): void {
  if (request.schemaVersion !== "durable-checkpoint-request/1") {
    throw new DurableStoreError("DURABLE_REQUEST_INVALID", "unsupported durable checkpoint request");
  }
  parseRevisionId(request.revisionId);
  if (request.acceptedArtifactIds.length === 0 || request.decisionArtifactIds.length === 0) {
    throw new DurableStoreError(
      "DURABLE_REQUEST_INVALID",
      "durable checkpoint requires accepted EngineArtifacts and decisions",
    );
  }
  requireUnique(request.acceptedArtifactIds, "accepted EngineArtifact IDs");
  requireUnique(request.decisionArtifactIds, "decision EngineArtifact IDs");
  requireUnique(request.inputArtifactIds ?? [], "input EngineArtifact IDs");
  requireUnique(request.decisionEvidenceArtifactIds ?? [], "decision evidence EngineArtifact IDs");
  requireUnique(
    (request.inputRevisions ?? []).map((ref) => `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`),
    "InputRevision references",
  );
}

/** Convert the public binding shape to the historical internal projections. */
type NormalizedDurablePromotionRequest = DurablePromotionRequest & {
  readonly inputBindings: readonly import("./types.ts").DurableInputBinding[];
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly inputRevisions: readonly import("./types.ts").InputRevisionRef[];
};

function normalizePromotionRequest(request: DurablePromotionRequest): NormalizedDurablePromotionRequest {
  if (request.inputBindings !== undefined) {
    const inputArtifactIds = request.inputBindings.map((binding) => binding.artifactId);
    const inputRevisions = request.inputRevisions ?? uniqueInputRevisions(request.inputBindings.map((binding) => binding.revision));
    if (
      request.inputArtifactIds !== undefined &&
      !sameSequence(request.inputArtifactIds, inputArtifactIds)
    ) {
      throw new DurableStoreError("DURABLE_INPUT_MISMATCH", "input artifact projections disagree with bindings");
    }
    if (
      request.inputRevisions !== undefined &&
      request.inputBindings.some((binding) => !request.inputRevisions!.some((candidate) => inputRevisionKey(candidate) === inputRevisionKey(binding.revision)))
    ) {
      throw new DurableStoreError("DURABLE_INPUT_MISMATCH", "input revision projections omit a bound revision");
    }
    return { ...request, inputArtifactIds, inputRevisions } as NormalizedDurablePromotionRequest;
  }
  if (request.inputArtifactIds === undefined || request.inputRevisions === undefined) {
    throw new DurableStoreError("DURABLE_REQUEST_INVALID", "durable checkpoint requires exact input bindings");
  }
  return {
    ...request,
    inputBindings: request.inputArtifactIds.map((artifactId, index) => ({
      artifactId,
      revision: request.inputRevisions![index]!,
    })),
  } as NormalizedDurablePromotionRequest;
}

function uniqueInputRevisions(values: readonly import("./types.ts").InputRevisionRef[]): readonly import("./types.ts").InputRevisionRef[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = inputRevisionKey(value);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function sameSequence(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function validateEngineReferences(
  view: RunView,
  request: DurablePromotionRequest,
): readonly ArtifactView[] {
  if (view.id !== request.runId) {
    throw new DurableStoreError("DURABLE_RUN_MISMATCH", "RunEngine returned the wrong run");
  }
  const byId = new Map(view.artifacts.map((artifact) => [artifact.id, artifact]));
  const accepted = request.acceptedArtifactIds.map((artifactId) => {
    const artifact = byId.get(artifactId);
    if (artifact === undefined || artifact.producingRunId !== request.runId) {
      throw new DurableStoreError(
        "DURABLE_ARTIFACT_INVALID",
        `accepted EngineArtifact ${artifactId} is not owned by run ${request.runId}`,
      );
    }
    return artifact;
  });
  const decisions = new Map(
    view.decisions.flatMap((decision) =>
      decision.artifactId === undefined ? [] : [[decision.artifactId, decision] as const]
    ),
  );
  for (const artifactId of request.decisionArtifactIds) {
    const decision = decisions.get(artifactId);
    const artifact = byId.get(artifactId);
    if (
      decision === undefined ||
      decision.offerId === undefined ||
      artifact === undefined ||
      artifact.producingRunId !== request.runId
    ) {
      throw new DurableStoreError(
        "DURABLE_DECISION_INVALID",
        `decision EngineArtifact ${artifactId} is not a persisted work decision`,
      );
    }
    const offer = view.offers.find((candidate) => candidate.id === decision.offerId);
    if (offer?.status !== "answered") {
      throw new DurableStoreError(
        "DURABLE_DECISION_STALE",
        `decision EngineArtifact ${artifactId} is not bound to an answered offer`,
      );
    }
  }
  const exactParents = new Set(accepted.flatMap((artifact) =>
    artifact.parents.map((parent) => parent.artifactId)
  ));
  if (!sameSet(exactParents, new Set(request.inputArtifactIds))) {
    throw new DurableStoreError(
      "DURABLE_INPUT_MISMATCH",
      "accepted EngineArtifact parents do not equal the checkpoint's exact inputs",
    );
  }
  return accepted;
}

async function materializeRecords(
  engine: PromotionEngine,
  request: DurablePromotionRequest,
  artifacts: readonly ArtifactView[],
): Promise<{
  readonly records: readonly DurableFileRecord[];
  readonly files: readonly { path: string; bytes: Buffer }[];
}> {
  const paths = durablePayloadPaths(request, artifacts);
  const files = await Promise.all(request.acceptedArtifactIds.map(async (artifactId, index) => {
    const loaded = await engine.readArtifact(artifactId);
    const artifact = artifacts[index];
    if (artifact === undefined || loaded.artifact.id !== artifact.id) {
      throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", `cannot read ${artifactId}`);
    }
    const bytes = Buffer.from(loaded.bytes);
    if (bytes.byteLength === 0) {
      throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", `${artifactId} is empty`);
    }
    validatePayloadMagic(bytes, artifact.mediaType, artifactId);
    return { path: paths[index]!, bytes };
  }));
  if (request.logicalItem.kind === "composition") {
    const document = parseCompositionDocument(files[0]!.bytes, {
      editionId: request.logicalItem.editionId,
      compositionId: request.logicalItem.compositionId,
    });
    const declared = new Set(document.layout_inputs.map((pin) => inputRevisionKey(pin.revision)));
    const checkpointed = new Set(request.inputRevisions.map(inputRevisionKey));
    if (!sameSet(declared, checkpointed)) {
      throw new DurableStoreError(
        "DURABLE_INPUT_MISMATCH",
        "composition layout inputs do not equal the checkpoint's InputRevisions",
      );
    }
  }
  return {
    files,
    records: files.map((file, index) => ({
      path: file.path,
      mediaType: artifacts[index]!.mediaType,
      sha256: digest(file.bytes),
      sizeBytes: file.bytes.byteLength,
      engineArtifactId: artifacts[index]!.id,
    })),
  };
}

function durablePayloadPaths(
  request: DurablePromotionRequest,
  artifacts: readonly ArtifactView[],
): readonly string[] {
  switch (request.logicalItem.kind) {
    case "article":
      if (artifacts.length < 1 || artifacts.length > 2 || artifacts[0]?.mediaType !== "text/markdown") {
        throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", "article promotion needs Markdown manuscript and optional notes");
      }
      return artifacts.length === 1 ? ["manuscript.md"] : ["manuscript.md", "working-notes.md"];
    case "editorial":
      if (artifacts.length !== 1 || artifacts[0]?.mediaType !== "text/markdown") {
        throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", "editorial promotion needs one Markdown manuscript");
      }
      return ["manuscript.md"];
    case "composition":
      if (artifacts.length !== 1 || !new Set(["application/json", "application/yaml", "text/yaml"]).has(artifacts[0]?.mediaType ?? "")) {
        throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", "composition promotion needs one structured manifest");
      }
      return ["composition.yaml"];
    case "image": {
      if (artifacts.length !== 1 || !artifacts[0]?.mediaType.startsWith("image/")) {
        throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", "image promotion needs one image EngineArtifact");
      }
      return [`image${extensionFor(artifacts[0].mediaType)}`];
    }
  }
}

function extensionFor(mediaType: string): string {
  switch (mediaType) {
    case "image/jpeg": return ".jpg";
    case "image/png": return ".png";
    case "image/svg+xml": return ".svg";
    case "image/webp": return ".webp";
    default: throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", `unsupported durable image type ${mediaType}`);
  }
}

function buildManifest(
  request: DurablePromotionRequest,
  files: readonly DurableFileRecord[],
  createdAt: string,
): DurableRevisionManifest {
  const common = {
    schema_version: 1 as const,
    revision_kind: request.logicalItem.kind,
    edition_id: request.logicalItem.editionId,
    revision_id: request.revisionId,
    created_at: createdAt,
    parent_revision_id: request.expectedParentRevisionId,
    provenance_kind: "engine_promotion" as const,
    promotion_id: request.promotionId,
    producing_run_id: request.runId,
    accepted_engine_artifact_ids: [...request.acceptedArtifactIds],
    decision_engine_artifact_ids: [...request.decisionArtifactIds],
    input_revisions: [...request.inputRevisions],
    input_engine_artifact_ids: [...request.inputArtifactIds],
    files,
  };
  switch (request.logicalItem.kind) {
    case "article":
    case "editorial":
      return {
        ...common,
        revision_kind: request.logicalItem.kind,
        logical_id: request.logicalItem.logicalId,
        language: request.logicalItem.language,
      };
    case "image":
      return {
        ...common,
        revision_kind: "image",
        logical_id: request.logicalItem.logicalId,
      };
    case "composition":
      return {
        ...common,
        revision_kind: "composition",
        composition_id: request.logicalItem.compositionId,
      };
  }
}

function encodeManifest(manifest: DurableRevisionManifest): Buffer {
  return Buffer.from(stringify(manifest, { lineWidth: 0 }), "utf8");
}

async function validateExpectedParent(
  revisionsDirectory: string,
  logicalItem: DurableLogicalItem,
  expected: import("../contracts/index.ts").RevisionId | null,
  promotionId: import("../contracts/index.ts").PromotionId,
  repositoryRoot: string,
  git: DurableGit,
): Promise<void> {
  let children: string[];
  try {
    children = await readdir(revisionsDirectory);
  } catch (error) {
    if (isMissing(error)) {
      if (expected !== null) {
        throw new DurableStoreError("DURABLE_PARENT_MISMATCH", `expected parent ${expected} does not exist`);
      }
      return;
    }
    throw error;
  }
  const manifests = await Promise.all(children.map(async (name) => {
    try {
      parseRevisionId(name);
    } catch (error) {
      throw integrityConflict(`durable revisions directory contains invalid entry ${name}`, error);
    }
    const loaded = await loadExistingManifest(join(revisionsDirectory, name));
    if (loaded === undefined) {
      throw integrityConflict(`durable revision ${name} has no manifest`);
    }
    if (loaded.manifest.revision_id !== name) {
      throw integrityConflict(`durable revision directory ${name} disagrees with its manifest`);
    }
    validateManifestLogicalItem(loaded.manifest, logicalItem);
    return loaded;
  }));
  const revisions = manifests.map((loaded) => loaded.manifest);
  if (expected === null) {
    const samePromotion = revisions.find((manifest) =>
      manifest.provenance_kind === "engine_promotion" &&
      manifest.promotion_id === promotionId
    );
    if (samePromotion !== undefined) return;
    if (revisions.length > 0) {
      throw new DurableStoreError("DURABLE_PARENT_MISMATCH", "an existing logical item requires an expected parent revision");
    }
    return;
  }
  parseRevisionId(expected);
  const parent = revisions.find((manifest) => manifest.revision_id === expected);
  if (parent === undefined) {
    throw new DurableStoreError("DURABLE_PARENT_MISMATCH", `expected parent ${expected} does not exist`);
  }
  const existingChild = revisions.find((manifest) => manifest.parent_revision_id === expected);
  if (
    existingChild !== undefined &&
    (existingChild.provenance_kind !== "engine_promotion" ||
      existingChild.promotion_id !== promotionId)
  ) {
    throw new DurableStoreError("DURABLE_PARENT_MISMATCH", `expected parent ${expected} already has a successor`);
  }
  const parentPath = relative(repositoryRoot, join(revisionsDirectory, expected, "manifest.yaml"));
  await git.assertCommitted([parentPath]);
}

async function verifyCandidate(root: string, manifest: DurableRevisionManifest): Promise<void> {
  const names = (await readdir(root)).sort();
  const expected = ["manifest.yaml", ...manifest.files.map((file) => file.path)].sort();
  if (names.some((name) => name.includes("/"))) {
    throw integrityConflict("durable payload paths must be direct files");
  }
  if (names.length !== expected.length || names.some((name, index) => name !== expected[index])) {
    throw integrityConflict("candidate tree differs from its manifest");
  }
  await verifyMaterializedFiles(root, manifest.files.map((file) => ({
    path: file.path,
    bytes: Buffer.alloc(0),
  })), manifest.files);
}

async function verifyMaterializedFiles(
  root: string,
  files: readonly { path: string; bytes: Buffer }[],
  expectedRecords?: readonly DurableFileRecord[],
): Promise<void> {
  const records = expectedRecords ?? files.map((file) => ({
    path: file.path,
    sha256: digest(file.bytes),
    sizeBytes: file.bytes.byteLength,
  }));
  for (const record of records) {
    const path = containedPath(root, record.path);
    const info = await lstat(path);
    if (info.isSymbolicLink() || !info.isFile()) {
      throw integrityConflict(`durable payload ${record.path} is not a regular file`);
    }
    const bytes = await readFile(path);
    if (bytes.byteLength !== record.sizeBytes || digest(bytes) !== record.sha256) {
      throw integrityConflict(`durable payload ${record.path} failed integrity validation`);
    }
  }
}

async function loadExistingManifest(
  revisionDirectory: string,
): Promise<{ readonly manifest: DurableRevisionManifest; readonly bytes: Buffer } | undefined> {
  try {
    const info = await lstat(revisionDirectory);
    if (info.isSymbolicLink() || !info.isDirectory()) {
      throw integrityConflict(`${revisionDirectory} is not a durable revision directory`);
    }
    const path = join(revisionDirectory, "manifest.yaml");
    const bytes = await readFile(path);
    const manifest = parse(bytes.toString("utf8")) as DurableRevisionManifest;
    validateStoredManifest(manifest);
    return { manifest, bytes };
  } catch (error) {
    if (isMissing(error)) return undefined;
    throw error;
  }
}

function validateStoredManifest(manifest: DurableRevisionManifest): void {
  if (
    manifest.schema_version !== 1 ||
    !new Set(["article", "composition", "editorial", "image"]).has(manifest.revision_kind) ||
    typeof manifest.edition_id !== "string" ||
    typeof manifest.revision_id !== "string" ||
    typeof manifest.created_at !== "string" ||
    (manifest.parent_revision_id !== null && typeof manifest.parent_revision_id !== "string") ||
    !Array.isArray(manifest.input_revisions) ||
    !Array.isArray(manifest.files)
  ) {
    throw integrityConflict("durable manifest is invalid");
  }
  if (manifest.provenance_kind === "engine_promotion") {
    if (
      typeof manifest.promotion_id !== "string" ||
      typeof manifest.producing_run_id !== "string" ||
      !Array.isArray(manifest.accepted_engine_artifact_ids) ||
      !Array.isArray(manifest.decision_engine_artifact_ids) ||
      !Array.isArray(manifest.input_engine_artifact_ids)
    ) {
      throw integrityConflict("engine promotion provenance is invalid");
    }
  } else if (manifest.provenance_kind === "legacy_import") {
    if (
      typeof manifest.migration_id !== "string" ||
      manifest.legacy_run_inventory !== "absent" ||
      !Array.isArray(manifest.legacy_source_bindings) ||
      manifest.legacy_source_bindings.length === 0
    ) {
      throw integrityConflict("legacy import provenance is invalid");
    }
    const sourcePaths = new Set<string>();
    for (const binding of manifest.legacy_source_bindings) {
      if (
        typeof binding.repositoryPath !== "string" ||
        !validGitOid(binding.gitCommitOid) ||
        !validGitOid(binding.gitBlobOid) ||
        !/^sha256:[0-9a-f]{64}$/u.test(binding.sha256) ||
        sourcePaths.has(binding.repositoryPath)
      ) {
        throw integrityConflict("legacy import source binding is invalid");
      }
      sourcePaths.add(binding.repositoryPath);
    }
  } else {
    throw integrityConflict("durable manifest has unknown provenance");
  }
  parseRevisionId(manifest.revision_id);
  if (manifest.parent_revision_id !== null) parseRevisionId(manifest.parent_revision_id);
  if (Number.isNaN(Date.parse(manifest.created_at))) {
    throw integrityConflict("durable manifest has an invalid creation time");
  }
  const filePaths = new Set<string>();
  for (const file of manifest.files) {
    if (
      typeof file !== "object" || file === null ||
      typeof file.path !== "string" ||
      typeof file.mediaType !== "string" ||
      typeof file.sha256 !== "string" ||
      !/^sha256:[0-9a-f]{64}$/u.test(file.sha256) ||
      !Number.isSafeInteger(file.sizeBytes) || file.sizeBytes < 1 ||
      filePaths.has(file.path)
    ) {
      throw integrityConflict("durable manifest has an invalid file record");
    }
    if (manifest.provenance_kind === "engine_promotion") {
      if (
        typeof file.engineArtifactId !== "string" ||
        file.legacySource !== undefined ||
        file.migrationAssembly !== undefined
      ) {
        throw integrityConflict("engine promotion file record has invalid provenance");
      }
    } else if (manifest.provenance_kind === "legacy_import") {
      const legacyBound = file.legacySource !== undefined &&
        typeof file.legacySource.repositoryPath === "string" &&
        validGitOid(file.legacySource.gitCommitOid) &&
        validGitOid(file.legacySource.gitBlobOid);
      const assembled = file.migrationAssembly !== undefined &&
        typeof file.migrationAssembly.basis === "string" &&
        file.migrationAssembly.basis.length > 0;
      if (file.engineArtifactId !== undefined || legacyBound === assembled) {
        throw integrityConflict("legacy import file record has invalid provenance");
      }
    }
    containedPath("/durable-revision", file.path);
    if (file.path.includes("/") || file.path === "manifest.yaml") {
      throw integrityConflict(`durable payload path ${file.path} is invalid`);
    }
    filePaths.add(file.path);
  }
  validateManifestLogicalItem(manifest, manifestToLogicalItem(manifest));
}

function manifestToLogicalItem(manifest: DurableRevisionManifest): DurableLogicalItem {
  switch (manifest.revision_kind) {
    case "article":
    case "editorial":
      return {
        kind: manifest.revision_kind,
        editionId: manifest.edition_id,
        logicalId: manifest.logical_id,
        language: manifest.language,
      };
    case "image":
      return {
        kind: "image",
        editionId: manifest.edition_id,
        logicalId: manifest.logical_id,
      };
    case "composition":
      return {
        kind: "composition",
        editionId: manifest.edition_id,
        compositionId: manifest.composition_id,
      };
  }
}

function validateManifestLogicalItem(
  manifest: DurableRevisionManifest,
  expected: DurableLogicalItem,
): void {
  if (manifest.revision_kind !== expected.kind || manifest.edition_id !== expected.editionId) {
    throw integrityConflict("durable manifest identity does not match its logical item");
  }
  switch (expected.kind) {
    case "article":
    case "editorial":
      if (
        manifest.revision_kind !== expected.kind ||
        manifest.logical_id !== expected.logicalId ||
        manifest.language !== expected.language
      ) {
        throw integrityConflict("durable manuscript manifest identity does not match its path");
      }
      return;
    case "image":
      if (manifest.revision_kind !== "image" || manifest.logical_id !== expected.logicalId) {
        throw integrityConflict("durable image manifest identity does not match its path");
      }
      return;
    case "composition":
      if (
        manifest.revision_kind !== "composition" ||
        manifest.composition_id !== expected.compositionId
      ) {
        throw integrityConflict("durable composition manifest identity does not match its path");
      }
  }
}

function validateGitBinding(binding: GitRevisionBinding, expectedPaths: readonly string[]): void {
  if (!validGitOid(binding.commitOid)) {
    throw new DurableStoreError("DURABLE_GIT_BINDING_INVALID", "Git commit OID is invalid");
  }
  const paths = Object.keys(binding.blobOids).sort();
  if (
    paths.length !== expectedPaths.length ||
    paths.some((path, index) => path !== expectedPaths[index]) ||
    Object.values(binding.blobOids).some((oid) => !validGitOid(oid))
  ) {
    throw new DurableStoreError("DURABLE_GIT_BINDING_INVALID", "Git blob binding does not match durable revision files");
  }
}

function validGitOid(value: string): boolean {
  return /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u.test(value);
}

function checkpointResult(
  request: DurablePromotionRequest,
  revisionRef: DurableRevisionRef,
  relativeDirectory: string,
  manifestDigest: string,
  binding: GitRevisionBinding,
): DurableCheckpointResult {
  const result = {
    revisionId: request.revisionId,
    promotionId: request.promotionId,
      logicalItem: request.logicalItem,
      expectedParentRevisionId: request.expectedParentRevisionId,
      acceptedArtifactIds: [...request.acceptedArtifactIds],
      decisionArtifactIds: [...request.decisionArtifactIds],
      inputArtifactIds: [...request.inputArtifactIds],
      inputRevisions: [...request.inputRevisions],
      manifestDigest,
    gitCommitOid: binding.commitOid,
    gitBlobOids: Object.fromEntries(Object.entries(binding.blobOids).sort(([left], [right]) => left.localeCompare(right))),
    revisionRef,
  };
  return {
    contractVersion: "durable-checkpoint/1",
    result,
    artifacts: [{
      kind: "durable_revision_evidence",
      schemaVersion: "durable-checkpoint/1",
      mediaType: "application/json",
      payload: {
        kind: "json",
        value: {
          ...result,
          revisionPath: relativeDirectory,
        } as unknown as JsonObject,
      },
      parents: [
        ...request.acceptedArtifactIds.map((artifactId) => ({ artifactId, relation: "accepted_output" })),
        ...request.decisionArtifactIds.map((artifactId) => ({ artifactId, relation: "accepted_decision" })),
        ...request.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "checkpoint_input" })),
      ],
      metadata: {
        promotionId: request.promotionId,
        revisionId: request.revisionId,
        manifestDigest,
      },
    }],
    metadata: {
      promotionId: request.promotionId,
      revisionId: request.revisionId,
      revisionPath: relativeDirectory,
    },
  };
}

function validatePayloadMagic(bytes: Buffer, mediaType: string, artifactId: ArtifactId): void {
  if (mediaType === "image/png" && bytes.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") {
    throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", `${artifactId} has invalid PNG magic`);
  }
  if (mediaType === "image/jpeg" && bytes.subarray(0, 2).toString("hex") !== "ffd8") {
    throw new DurableStoreError("DURABLE_ARTIFACT_INVALID", `${artifactId} has invalid JPEG magic`);
  }
}

function containedPath(root: string, child: string): string {
  const base = resolve(root);
  const path = resolve(base, child);
  if (path === base || !path.startsWith(`${base}${sep}`)) {
    throw new DurableStoreError("DURABLE_PATH_INVALID", `path escapes durable root: ${child}`);
  }
  return path;
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function requireUnique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) {
    throw new DurableStoreError("DURABLE_REQUEST_INVALID", `${label} must be unique`);
  }
}

function sameSet(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  return left.size === right.size && [...left].every((value) => right.has(value));
}

function inputRevisionKey(ref: import("./types.ts").InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

function integrityConflict(message: string, cause?: unknown): DurableStoreError {
  return new DurableStoreError(
    "DURABLE_INTEGRITY_CONFLICT",
    message,
    cause === undefined ? undefined : { cause },
  );
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function isMissing(error: unknown): error is NodeJS.ErrnoException {
  return typeof error === "object" && error !== null && "code" in error && error.code === "ENOENT";
}
