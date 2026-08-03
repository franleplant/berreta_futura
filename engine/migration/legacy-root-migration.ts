import { createHash } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import {
  mkdir,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, posix, resolve, sep } from "node:path";
import { promisify } from "node:util";

import { parse, stringify } from "yaml";

import { newRevisionId } from "../durable/revision-id.ts";
import type { RevisionId } from "../contracts/index.ts";

const execFile = promisify(execFileCallback);
const LEGACY_ROOTS = ["editions", "library", "prompts"] as const;
const EDITION4_FIXED_COMPOSITION_REVISION =
  "rev_20260802T230000065Z_nn4pdbpswp3n" as RevisionId;

/** The protected pre-cutover snapshot audited on 2026-08-03. */
export const LEGACY_ROOT_BASELINE = {
  fileCount: 933,
  sizeBytes: 525_474_841,
} as const;

export type LegacyGitFile = {
  readonly path: string;
  readonly mode: "100644" | "100755";
  readonly blobOid: string;
  readonly sha256: string;
  readonly sizeBytes: number;
};

export type LegacyGitSnapshot = {
  readonly sourceCommitOid: string;
  readonly files: readonly LegacyGitFile[];
  readonly canonicalInventorySha256: string;
};

export type LegacyDisposition =
  | "import_exact"
  | "reuse_existing"
  | "archive_non_authoritative"
  | "retire_housekeeping";

export type LegacyMigrationCategory = "input" | "durable" | "archive";

export type LegacyDurableIdentity = {
  readonly editionId: string;
  readonly logicalId: string;
  readonly language?: string;
};

export type LegacyMigrationTarget = {
  /** Stable plan slot. It is not a content-derived identity. */
  readonly revisionSlot: string;
  readonly category: LegacyMigrationCategory;
  readonly revisionKind:
    | "source_capture"
    | "source_extraction"
    | "prompt"
    | "policy"
    | "edition_spec"
    | "migration_archive"
    | "article"
    | "editorial"
    | "image";
  readonly revisionId: RevisionId;
  readonly payloadPath: string;
  /** Exact DurableRevision identity. Older superseded ledgers may omit it. */
  readonly durableIdentity?: LegacyDurableIdentity;
  /** Exact legacy lineage. Older superseded ledgers may omit it. */
  readonly parentRevisionId?: RevisionId | null;
  readonly reuseBinding?: "edition4-fixed-revision";
};

export type LegacyFileDisposition = {
  readonly source: LegacyGitFile;
  readonly disposition: LegacyDisposition;
  readonly targets: readonly LegacyMigrationTarget[];
  readonly basis: string;
};

export type HistoricalCompositionPlan = {
  readonly editionId: "001" | "002" | "003" | "004";
  readonly compositionId: string;
  readonly revisionId: RevisionId;
  readonly state: "legacy-current-snapshot" | "reuse-existing";
  readonly sourceCommitOid: string;
  readonly basis: string;
  readonly requiresFreshRunEngineReview: true;
};

export type LegacyRootMigrationPlan = {
  readonly schemaVersion: "legacy-root-migration/1";
  /** Present once every durable target carries its complete public identity. */
  readonly durableIdentityContract?: "durable-identity/1";
  readonly migrationId: string;
  readonly supersedesPlanRevisionId?: RevisionId;
  readonly sourceSnapshot: LegacyGitSnapshot;
  /** Persist this map in the ledger. Replanning must reload, not reallocate it. */
  readonly allocatedRevisionIds: Readonly<Record<string, RevisionId>>;
  readonly files: readonly LegacyFileDisposition[];
  readonly historicalCompositions: readonly HistoricalCompositionPlan[];
  readonly requiredHumanChoices: readonly string[];
  readonly generatedFiles: readonly {
    readonly revisionSlot: string;
    readonly path: string;
    readonly basis: string;
  }[];
};

export type LegacyRootMigrationOptions = {
  readonly migrationId: string;
  /** A reloaded plan's allocation map. Passing it prevents new identities. */
  readonly allocatedRevisionIds?: Readonly<Record<string, RevisionId>>;
  /** Exact already-committed revision bindings, keyed by source path then kind. */
  readonly existingBindingsBySourcePath?: Readonly<Record<
    string,
    Readonly<Partial<Record<LegacyMigrationTarget["revisionKind"], RevisionId>>>
  >>;
  /** Exact semantic DurableRevision identities, keyed by protected source path. */
  readonly durableIdentitiesBySourcePath?: Readonly<Record<string, LegacyDurableIdentity>>;
  /** Successor-ledger repair: prefer an older exact binding over a duplicated allocation. */
  readonly preferExactExistingBindings?: boolean;
  readonly allocateRevisionId?: () => RevisionId;
};

export type ExistingRevisionBindingAudit = {
  readonly bindingsBySourcePath: NonNullable<LegacyRootMigrationOptions["existingBindingsBySourcePath"]>;
  readonly durableIdentitiesBySourcePath: Readonly<Record<string, LegacyDurableIdentity>>;
  readonly boundSourcePaths: number;
  readonly conflicts: readonly string[];
};

export class LegacyRootMigrationError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "LegacyRootMigrationError";
    this.code = code;
  }
}

/**
 * Reads only committed legacy bytes. It deliberately does not stat or read a
 * working-tree path, so a plan remains bound to one protected Git snapshot.
 */
export async function readLegacyGitSnapshot(
  repositoryRoot: string,
  commitish = "HEAD",
): Promise<LegacyGitSnapshot> {
  const root = resolve(repositoryRoot);
  const sourceCommitOid = await gitText(root, ["rev-parse", `${commitish}^{commit}`]);
  const tree = await gitBuffer(root, ["ls-tree", "-r", "-l", "-z", sourceCommitOid, "--", ...LEGACY_ROOTS]);
  const parsed = parseLsTree(tree);
  assertNoUnsafeOrAliasedPaths(parsed.map((file) => file.path));

  const hashes = new Map<string, string>();
  for (const blobOid of [...new Set(parsed.map((file) => file.blobOid))]) {
    const bytes = await gitBuffer(root, ["cat-file", "blob", blobOid]);
    hashes.set(blobOid, sha256(bytes));
  }
  const files = parsed.map((file) => ({ ...file, sha256: required(hashes.get(file.blobOid), file.blobOid) }));
  return {
    sourceCommitOid,
    files,
    canonicalInventorySha256: canonicalInventorySha256(files),
  };
}

/** Use immediately before the one-shot cutover, never as an identity source. */
export function assertLegacyRootBaseline(snapshot: LegacyGitSnapshot): void {
  validateSnapshot(snapshot);
  const bytes = snapshot.files.reduce((total, file) => total + file.sizeBytes, 0);
  if (snapshot.files.length !== LEGACY_ROOT_BASELINE.fileCount || bytes !== LEGACY_ROOT_BASELINE.sizeBytes) {
    throw invalid(
      `protected legacy baseline drifted (files=${snapshot.files.length}, bytes=${bytes}); choose and record a new snapshot explicitly`,
    );
  }
}

/**
 * Derives reuse candidates from committed manifests only, and accepts a
 * binding only when its declared SHA-256 equals the protected source byte.
 */
export async function readExactExistingRevisionBindings(
  repositoryRoot: string,
  snapshot: LegacyGitSnapshot,
): Promise<ExistingRevisionBindingAudit> {
  validateSnapshot(snapshot);
  const root = resolve(repositoryRoot);
  const head = await gitText(root, ["rev-parse", "HEAD^{commit}"]);
  const tree = parseAnyBlobTree(await gitBuffer(root, ["ls-tree", "-r", "-l", "-z", head, "--", "inputs", "durable"]));
  const sourceByPath = new Map(snapshot.files.map((file) => [file.path, file]));
  const candidates = new Map<string, Map<LegacyMigrationTarget["revisionKind"], RevisionId>>();
  const durableIdentities = new Map<string, LegacyDurableIdentity>();
  const conflicts: string[] = [];
  for (const manifestEntry of tree.filter((entry) => entry.path.endsWith("/manifest.yaml"))) {
    const decoded = parse((await gitBuffer(root, ["cat-file", "blob", manifestEntry.blobOid])).toString("utf8"));
    if (!isMapping(decoded) || typeof decoded.revision_kind !== "string" || typeof decoded.revision_id !== "string") continue;
    const kind = decoded.revision_kind as LegacyMigrationTarget["revisionKind"];
    if (!isMigratableKind(kind) || !/^rev_\d{8}T\d{9}Z_[a-z2-7]{12}$/u.test(decoded.revision_id)) continue;
    const revisionId = decoded.revision_id as RevisionId;
    const durableIdentity = durableIdentityFromManifest(decoded, kind);
    const bindings: Array<{ readonly path: string; readonly sha: string }> = [];
    if (Array.isArray(decoded.files)) {
      for (const value of decoded.files) {
        if (!isMapping(value)) continue;
        const legacy = isMapping(value.legacy_source) ? value.legacy_source :
          isMapping(value.legacySource) ? value.legacySource : undefined;
        const digest = typeof value.sha256 === "string" ? value.sha256 : undefined;
        const path = legacy === undefined ? undefined :
          typeof legacy.repositoryPath === "string" ? legacy.repositoryPath :
            typeof legacy.repository_path === "string" ? legacy.repository_path : undefined;
        if (path !== undefined && digest !== undefined) bindings.push({ path, sha: digest });
      }
    }
    if (Array.isArray(decoded.legacy_source_bindings)) {
      for (const value of decoded.legacy_source_bindings) {
        if (!isMapping(value) || typeof value.repositoryPath !== "string" || typeof value.sha256 !== "string") continue;
        bindings.push({ path: value.repositoryPath, sha: value.sha256 });
      }
    }
    for (const binding of bindings) {
      const source = sourceByPath.get(binding.path);
      if (source === undefined || source.sha256 !== binding.sha) continue;
      const byKind = candidates.get(binding.path) ?? new Map();
      const prior = byKind.get(kind);
      if (prior !== undefined && prior !== revisionId) {
        byKind.set(kind, prior.localeCompare(revisionId) <= 0 ? prior : revisionId);
      } else {
        byKind.set(kind, revisionId);
      }
      candidates.set(binding.path, byKind);
      if (durableIdentity !== undefined) {
        const priorIdentity = durableIdentities.get(binding.path);
        if (priorIdentity !== undefined && !sameDurableIdentity(priorIdentity, durableIdentity)) {
          conflicts.push(`${binding.path} (${kind}): conflicting DurableRevision identities`);
          continue;
        }
        durableIdentities.set(binding.path, durableIdentity);
      }
    }
  }
  return {
    bindingsBySourcePath: Object.fromEntries([...candidates].map(([path, values]) => [
      path,
      Object.fromEntries(values),
    ])),
    durableIdentitiesBySourcePath: Object.fromEntries([...durableIdentities].sort(([a], [b]) => a.localeCompare(b))),
    boundSourcePaths: candidates.size,
    conflicts: conflicts.sort(),
  };
}

/**
 * Resolves semantic durable identities from the protected edition manifests.
 * Legacy rerun roots remain separate allocation slots but resolve to the same
 * numeric edition identity, so they become revisions rather than new editions.
 */
export async function readLegacyDurableIdentities(
  repositoryRoot: string,
  snapshot: LegacyGitSnapshot,
  existing: Readonly<Record<string, LegacyDurableIdentity>> = {},
): Promise<Readonly<Record<string, LegacyDurableIdentity>>> {
  validateSnapshot(snapshot);
  const root = resolve(repositoryRoot);
  const identities = new Map<string, LegacyDurableIdentity>();
  for (const file of snapshot.files) {
    const article = articleFile(file.path);
    if (article !== undefined) {
      identities.set(file.path, {
        editionId: durableEditionId(article.editionKey),
        logicalId: article.logicalId,
        language: article.language,
      });
      continue;
    }
    const editorial = editorialFile(file.path);
    if (editorial !== undefined) {
      identities.set(file.path, {
        editionId: durableEditionId(editorial.editionKey),
        logicalId: "opening",
        language: editorial.language,
      });
      continue;
    }
    const image = editionImage(file.path);
    if (image !== undefined) {
      identities.set(file.path, {
        editionId: durableEditionId(image.editionKey),
        logicalId: image.ordinal,
      });
    }
  }

  for (const manifestFile of snapshot.files.filter((file) => /^editions\/[^/]+\/edition\.yaml$/u.test(file.path))) {
    const decoded = parse((await gitBuffer(root, ["cat-file", "blob", manifestFile.blobOid])).toString("utf8"));
    if (!isMapping(decoded)) throw invalid(`edition manifest is not a mapping: ${manifestFile.path}`);
    const editionRoot = posix.dirname(manifestFile.path);
    const key = editionKey(editionRoot.slice("editions/".length));
    const editionId = durableEditionId(key);
    const selected = selectedImageIdentities(decoded, editionRoot, editionId);
    for (const [path, identity] of selected) {
      if (!identities.has(path)) throw invalid(`edition manifest selects an untracked durable image: ${path}`);
      identities.set(path, identity);
    }
  }

  for (const [path, identity] of Object.entries(existing)) {
    const derived = identities.get(path);
    if (derived !== undefined && !sameDurableIdentity(derived, identity)) {
      const image = editionImage(path);
      if (image === undefined || derived.editionId !== identity.editionId || identity.language !== undefined) {
        throw invalid(`protected manifest and existing DurableRevision disagree for ${path}`);
      }
    }
    identities.set(path, identity);
  }

  const protectedPaths = new Set(snapshot.files.map((file) => file.path));
  for (const path of [...identities.keys()].filter((candidate) => candidate.startsWith(
    "editions/rerun-004-the-systems-around-the-model/",
  ))) {
    const counterpart = path.replace(
      "editions/rerun-004-the-systems-around-the-model/",
      "editions/004-the-systems-around-the-model/",
    );
    const identity = identities.get(counterpart);
    if (protectedPaths.has(counterpart) && identity !== undefined) identities.set(path, identity);
  }
  return Object.fromEntries([...identities].sort(([a], [b]) => a.localeCompare(b)));
}

/**
 * Generates a complete, byte-level ledger. It makes no filesystem changes.
 * New RevisionIds are allocated only for missing slots and are returned in the
 * plan so the plan itself is the one-time allocation record.
 */
export function planLegacyRootMigration(
  snapshot: LegacyGitSnapshot,
  options: LegacyRootMigrationOptions,
): LegacyRootMigrationPlan {
  validateSnapshot(snapshot);
  portableName(options.migrationId, "migration ID");
  const existing = { ...(options.allocatedRevisionIds ?? {}) };
  const allocate = options.allocateRevisionId ?? (() => newRevisionId());
  const ids = new Map(Object.entries(existing));
  const revisionId = (slot: string): RevisionId => {
    const prior = ids.get(slot);
    if (prior !== undefined) return prior;
    const next = allocate();
    if ([...ids.values()].includes(next)) {
      throw invalid(`revision allocator returned a duplicate RevisionId for ${slot}`);
    }
    ids.set(slot, next);
    return next;
  };
  const targetFor = <Target extends Omit<LegacyMigrationTarget, "revisionId" | "reuseBinding">>(
    file: LegacyGitFile,
    target: Target,
  ): { readonly disposition: "import_exact" | "reuse_existing"; readonly target: LegacyMigrationTarget } => {
    const bound = options.existingBindingsBySourcePath?.[file.path]?.[target.revisionKind];
    if (bound !== undefined) {
      const existingSlot = ids.get(target.revisionSlot);
      if (existingSlot !== undefined && existingSlot !== bound) {
        if (options.preferExactExistingBindings !== true) {
          throw invalid(`existing revision binding conflicts for ${file.path}`);
        }
      }
      ids.set(target.revisionSlot, bound);
      return {
        disposition: "reuse_existing",
        target: { ...target, revisionId: bound, reuseBinding: "edition4-fixed-revision" },
      };
    }
    return { disposition: "import_exact", target: { ...target, revisionId: revisionId(target.revisionSlot) } };
  };
  const archiveSlot = `input:archive:${options.migrationId}`;
  const sourceIds = sourceDirectoryIds(snapshot.files);
  const extractionIds = new Set(snapshot.files.flatMap((file) => sourceExtractionId(file.path)));
  const editionRootsWithManifest = new Set(snapshot.files.flatMap((file) => {
    const root = editionRoot(file.path);
    return root !== undefined && file.path === `${root}/edition.yaml` ? [root] : [];
  }));
  const disposition: LegacyFileDisposition[] = [];

  for (const file of snapshot.files) {
    const source = sourceFile(file.path);
    if (source !== undefined) {
      const [sourceId, suffix] = source;
      if (suffix === "extracted.md") {
        const slot = `input:source_extraction:${sourceId}`;
        const binding = targetFor(file, {
          revisionSlot: slot,
          category: "input",
          revisionKind: "source_extraction",
          payloadPath: "extracted.md",
        });
        disposition.push(exact(file, binding.disposition, binding.target, "committed source extraction"));
      } else {
        const slot = `input:source_capture:${sourceId}`;
        const binding = targetFor(file, {
          revisionSlot: slot,
          category: "input",
          revisionKind: "source_capture",
          payloadPath: `raw/${portableLegacyPayloadPath(suffix)}`,
        });
        disposition.push(exact(file, binding.disposition, binding.target, "committed source evidence, record, or media"));
      }
      continue;
    }

    const promptId = promptIdFor(file.path);
    if (promptId !== undefined) {
      const slot = `input:prompt:${promptId}`;
      const binding = targetFor(file, {
        revisionSlot: slot,
        category: "input",
        revisionKind: "prompt",
        payloadPath: "prompt.md",
      });
      disposition.push(exact(file, binding.disposition, binding.target, "legacy prompt source"));
      continue;
    }
    if (file.path === "prompts/README.md") {
      const slot = "input:policy:review-bench";
      const binding = targetFor(file, {
        revisionSlot: slot,
        category: "input",
        revisionKind: "policy",
        payloadPath: "policy.md",
      });
      disposition.push(exact(file, binding.disposition, binding.target, "legacy prompt-set policy"));
      continue;
    }

    const article = articleFile(file.path);
    if (article !== undefined) {
      const slot = `durable:article:${article.editionKey}:${article.logicalId}:${article.language}`;
      const binding = targetFor(file, {
        revisionSlot: slot,
        category: "durable",
        revisionKind: "article",
        payloadPath: "manuscript.md",
        durableIdentity: options.durableIdentitiesBySourcePath?.[file.path] ?? {
          editionId: durableEditionId(article.editionKey),
          logicalId: article.logicalId,
          language: article.language,
        },
      });
      disposition.push(exact(file, binding.disposition, binding.target, "legacy article manuscript"));
      continue;
    }
    const editorial = editorialFile(file.path);
    if (editorial !== undefined) {
      const slot = `durable:editorial:${editorial.editionKey}:opening:${editorial.language}`;
      const binding = targetFor(file, {
        revisionSlot: slot,
        category: "durable",
        revisionKind: "editorial",
        payloadPath: "manuscript.md",
        durableIdentity: options.durableIdentitiesBySourcePath?.[file.path] ?? {
          editionId: durableEditionId(editorial.editionKey),
          logicalId: "opening",
          language: editorial.language,
        },
      });
      disposition.push(exact(file, binding.disposition, binding.target, "legacy opening editorial"));
      continue;
    }
    const image = editionImage(file.path);
    if (image !== undefined) {
      const slot = `durable:image:${image.editionKey}:${image.ordinal}`;
      const binding = targetFor(file, {
        revisionSlot: slot,
        category: "durable",
        revisionKind: "image",
        payloadPath: `image${image.extension}`,
        durableIdentity: options.durableIdentitiesBySourcePath?.[file.path] ?? {
          editionId: durableEditionId(image.editionKey),
          logicalId: image.ordinal,
        },
      });
      disposition.push(exact(file, binding.disposition, binding.target, "legacy art asset, including unselected candidates"));
      continue;
    }
    const spec = editionSpec(file.path, editionRootsWithManifest);
    if (spec !== undefined) {
      const slot = `input:edition_spec:${spec.editionKey}`;
      const binding = targetFor(file, {
        revisionSlot: slot,
        category: "input",
        revisionKind: "edition_spec",
        payloadPath: spec.payloadPath,
      });
      disposition.push(exact(file, binding.disposition, binding.target, "edition or layout specification"));
      continue;
    }
    disposition.push(exact(file, "archive_non_authoritative", {
      revisionSlot: archiveSlot,
      category: "archive",
      revisionKind: "migration_archive",
      revisionId: revisionId(archiveSlot),
      payloadPath: `archive/${file.path}`,
    }, "preserved exact legacy record without RunEngine authority"));
  }

  const uniqueSources = sourceIds.length;
  const uniqueExtractions = extractionIds.size;
  if (uniqueSources !== 36 || uniqueExtractions !== 25) {
    throw invalid(`legacy snapshot is not the expected source corpus (sources=${uniqueSources}, extractions=${uniqueExtractions})`);
  }
  const finalDisposition = withDurableParentBindings(disposition);
  assertCompleteLedger(snapshot, finalDisposition);
  const historicalCompositions = historicalCompositionPlans(snapshot.sourceCommitOid, snapshot.files, revisionId);
  const generatedFiles = [
    ...[...ids.keys()].filter((slot) => slot.startsWith("input:prompt:")).map((slot) => ({
      revisionSlot: slot,
      path: "output.schema.json",
      basis: "migration prompt contract, not a legacy byte",
    })),
    ...historicalCompositions.filter((entry) => entry.state === "legacy-current-snapshot").map((entry) => ({
      revisionSlot: `durable:composition:${entry.editionId}:${entry.compositionId}`,
      path: "composition.yaml",
      basis: `${entry.basis}; requires new RunEngine measurement, QA, visual review, and release`,
    })),
  ];
  return {
    schemaVersion: "legacy-root-migration/1",
    durableIdentityContract: "durable-identity/1",
    migrationId: options.migrationId,
    sourceSnapshot: snapshot,
    allocatedRevisionIds: Object.fromEntries([...ids.entries()].sort(([a], [b]) => a.localeCompare(b))),
    files: finalDisposition,
    historicalCompositions,
    requiredHumanChoices: [
      "Protect or tag sourceSnapshot.sourceCommitOid before materialization.",
      "Review the legacy-current-snapshot compositions for Editions 001-003 before any release claim.",
      "Classify archived prototype prose only if it should become reusable editorial work.",
    ],
    generatedFiles,
  };
}

/** A staging-only materializer. Callers must provide explicit authorization. */
export async function materializeLegacyMigrationPlan(
  repositoryRoot: string,
  plan: LegacyRootMigrationPlan,
  stagingRoot: string,
  authorization: { readonly kind: "approved-staging-materialization"; readonly sourceCommitOid: string },
): Promise<void> {
  verifyLegacyRootMigrationPlan(plan);
  if (authorization.sourceCommitOid !== plan.sourceSnapshot.sourceCommitOid) {
    throw invalid("materialization authorization does not name the planned source snapshot");
  }
  const root = resolve(repositoryRoot);
  const actualHead = await gitText(root, ["rev-parse", "HEAD^{commit}"]);
  if (actualHead !== plan.sourceSnapshot.sourceCommitOid) {
    throw invalid("materialization refuses a repository whose HEAD differs from the plan");
  }
  const stage = resolve(stagingRoot);
  await rm(stage, { recursive: true, force: true });
  await mkdir(stage, { recursive: true, mode: 0o700 });
  try {
    for (const entry of plan.files) {
      const target = contained(stage, join("revisions", entry.targets[0]!.revisionSlot, entry.targets[0]!.payloadPath));
      await mkdir(dirname(target), { recursive: true, mode: 0o700 });
      const bytes = await gitBuffer(root, ["cat-file", "blob", entry.source.blobOid]);
      if (bytes.byteLength !== entry.source.sizeBytes || sha256(bytes) !== entry.source.sha256) {
        throw invalid(`Git blob changed while staging ${entry.source.path}`);
      }
      await writeFile(target, bytes, { mode: 0o600 });
    }
    await writeFile(
      contained(stage, "migration-ledger.yaml"),
      stringify(plan, { lineWidth: 0 }),
      { mode: 0o600 },
    );
  } catch (error) {
    await rm(stage, { recursive: true, force: true });
    throw error;
  }
}

/** Verifies plan invariants without treating any legacy state as workflow state. */
export function verifyLegacyRootMigrationPlan(plan: LegacyRootMigrationPlan): void {
  if (plan.schemaVersion !== "legacy-root-migration/1") throw invalid("unknown migration plan schema");
  validateSnapshot(plan.sourceSnapshot);
  assertCompleteLedger(plan.sourceSnapshot, plan.files);
  const ids = Object.entries(plan.allocatedRevisionIds);
  if (new Set(ids.map(([, value]) => value)).size !== ids.length) throw invalid("allocated RevisionIds collide");
  for (const [slot, id] of ids) {
    if (slot.length === 0 || !/^rev_\d{8}T\d{9}Z_[a-z2-7]{12}$/u.test(id)) {
      throw invalid("allocated RevisionIds are malformed");
    }
  }
  for (const file of plan.files) {
    if (file.targets.length !== 1) throw invalid(`legacy file ${file.source.path} has no single primary target`);
    const target = file.targets[0]!;
    if (plan.allocatedRevisionIds[target.revisionSlot] !== target.revisionId) {
      throw invalid(`legacy file ${file.source.path} references an unallocated RevisionId`);
    }
    safeRelative(target.payloadPath);
    if (target.durableIdentity !== undefined) validateDurableIdentity(target);
    if (plan.durableIdentityContract === "durable-identity/1" &&
      target.category === "durable" && target.durableIdentity === undefined) {
      throw invalid(`legacy durable file ${file.source.path} has no exact DurableRevision identity`);
    }
    if (plan.durableIdentityContract === "durable-identity/1" && target.category === "durable") {
      if (target.parentRevisionId === undefined ||
        (target.parentRevisionId !== null && !/^rev_\d{8}T\d{9}Z_[a-z2-7]{12}$/u.test(target.parentRevisionId))) {
        throw invalid(`legacy durable file ${file.source.path} has no exact parent binding`);
      }
    }
  }
  const sources = sourceDirectoryIds(plan.sourceSnapshot.files);
  const extractions = new Set(plan.sourceSnapshot.files.flatMap((file) => sourceExtractionId(file.path)));
  if (sources.length !== 36 || extractions.size !== 25) throw invalid("source/extraction counts drifted");
  if (plan.historicalCompositions.filter((entry) => entry.editionId !== "004").length !== 3) {
    throw invalid("historical composition plan must cover Editions 001 through 003 exactly once");
  }
  for (const composition of plan.historicalCompositions) {
    if (!/^rev_\d{8}T\d{9}Z_[a-z2-7]{12}$/u.test(composition.revisionId)) {
      throw invalid(`historical composition ${composition.editionId} has an invalid RevisionId`);
    }
    if (composition.state === "legacy-current-snapshot" &&
      plan.allocatedRevisionIds[`durable:composition:${composition.editionId}:${composition.compositionId}`] !== composition.revisionId) {
      throw invalid(`historical composition ${composition.editionId} has no persisted allocation`);
    }
  }
}

/**
 * Cutover lint. Production code cannot regain a root reader after migration.
 * Migration modules, migration tests, and immutable provenance ledger text are
 * the only permitted legacy-root references.
 */
export function lintLegacyRootReferences(
  files: readonly { readonly path: string; readonly text: string }[],
): readonly string[] {
  const forbidden = /(?:^|["'`])(?:editions|library|prompts)\//u;
  return files.flatMap((file) => {
    if (isAllowedLegacyReference(file.path)) return [];
    return forbidden.test(file.text) ? [file.path] : [];
  });
}

export async function lintRepositoryForLegacyRootReferences(repositoryRoot: string): Promise<readonly string[]> {
  const files = await sourceFiles(resolve(repositoryRoot));
  return lintLegacyRootReferences(await Promise.all(files.map(async (path) => ({
    path: relativePortable(resolve(repositoryRoot), path),
    text: await readFile(path, "utf8"),
  }))));
}

function parseLsTree(bytes: Buffer): readonly Omit<LegacyGitFile, "sha256">[] {
  return bytes.toString("utf8").split("\0").filter(Boolean).map((line) => {
    const match = /^(100644|100755)\s+blob\s+([0-9a-f]{40,64})\s+(\d+)\t(.+)$/u.exec(line);
    if (match === null) throw invalid(`unsupported git tree entry: ${line.slice(0, 120)}`);
    const [, mode, blobOid, size, path] = match;
    if (mode === undefined || blobOid === undefined || size === undefined || path === undefined) throw invalid("incomplete git tree entry");
    safeRepositoryPath(path);
    return { path, mode: mode as "100644" | "100755", blobOid, sizeBytes: Number(size) };
  }).sort((a, b) => a.path.localeCompare(b.path));
}

function parseAnyBlobTree(bytes: Buffer): readonly {
  readonly path: string;
  readonly blobOid: string;
}[] {
  return bytes.toString("utf8").split("\0").filter(Boolean).map((line) => {
    const match = /^\d{6}\s+blob\s+([0-9a-f]{40,64})\s+\d+\t(.+)$/u.exec(line);
    if (match === null) throw invalid(`unsupported committed tree entry: ${line.slice(0, 120)}`);
    return { blobOid: match[1]!, path: match[2]! };
  });
}

function validateSnapshot(snapshot: LegacyGitSnapshot): void {
  if (!/^[0-9a-f]{40,64}$/u.test(snapshot.sourceCommitOid)) throw invalid("snapshot has invalid source commit");
  if (snapshot.files.length === 0) throw invalid("snapshot is empty");
  assertNoUnsafeOrAliasedPaths(snapshot.files.map((file) => file.path));
  for (const file of snapshot.files) {
    if ((file.mode !== "100644" && file.mode !== "100755") || !/^[0-9a-f]{40,64}$/u.test(file.blobOid) ||
      !/^sha256:[0-9a-f]{64}$/u.test(file.sha256) || !Number.isSafeInteger(file.sizeBytes) || file.sizeBytes < 0) {
      throw invalid(`snapshot file ${file.path} has invalid Git metadata`);
    }
  }
  if (snapshot.canonicalInventorySha256 !== canonicalInventorySha256(snapshot.files)) {
    throw invalid("snapshot canonical inventory digest does not match its records");
  }
}

function assertCompleteLedger(snapshot: LegacyGitSnapshot, entries: readonly LegacyFileDisposition[]): void {
  if (entries.length !== snapshot.files.length) throw invalid("migration ledger does not map every legacy file exactly once");
  const byPath = new Map(entries.map((entry) => [entry.source.path, entry]));
  if (byPath.size !== entries.length || byPath.size !== snapshot.files.length) throw invalid("migration ledger has duplicate or missing source paths");
  for (const source of snapshot.files) {
    const entry = byPath.get(source.path);
    if (entry === undefined || JSON.stringify(entry.source) !== JSON.stringify(source) || entry.targets.length !== 1) {
      throw invalid(`migration ledger does not exactly bind ${source.path}`);
    }
  }
  const targetAliases = new Set<string>();
  for (const entry of entries) {
    for (const target of entry.targets) {
      const key = `${target.revisionSlot}/${target.payloadPath}`.normalize("NFC").toLocaleLowerCase("en-US");
      if (targetAliases.has(key)) {
        throw invalid(`migration ledger has a case or Unicode-normalization target collision: ${key}`);
      }
      targetAliases.add(key);
    }
  }
}

function historicalCompositionPlans(
  sourceCommitOid: string,
  files: readonly LegacyGitFile[],
  revisionId: (slot: string) => RevisionId,
): readonly HistoricalCompositionPlan[] {
  const roots = new Set(files.map((file) => editionRoot(file.path)).filter((root): root is string => root !== undefined));
  const historical = (["001", "002", "003"] as const).map((editionId) => {
    const root = [...roots].find((candidate) => editionNumber(candidate) === editionId);
    if (root === undefined || !files.some((file) => file.path === `${root}/edition.yaml`)) {
      throw invalid(`Edition ${editionId} has no defensible baseline manifest`);
    }
    return {
      editionId,
      compositionId: "legacy-current-snapshot",
      revisionId: revisionId(`durable:composition:${editionId}:legacy-current-snapshot`),
      state: "legacy-current-snapshot" as const,
      sourceCommitOid,
      basis: `baseline ${sourceCommitOid} manifest pins at ${root}; no legacy release claim imported`,
      requiresFreshRunEngineReview: true as const,
    };
  });
  return [
    ...historical,
    {
      editionId: "004" as const,
      compositionId: "fresh-v2",
      revisionId: EDITION4_FIXED_COMPOSITION_REVISION,
      state: "reuse-existing" as const,
      sourceCommitOid,
      basis: "existing Edition 4 fixed composition is reused only after exact manifest and payload proof",
      requiresFreshRunEngineReview: true as const,
    },
  ];
}

function sourceDirectoryIds(files: readonly LegacyGitFile[]): readonly string[] {
  return [...new Set(files.flatMap((file) => {
    const parsed = sourceFile(file.path);
    return parsed === undefined ? [] : [parsed[0]];
  }))].sort();
}

function sourceFile(path: string): readonly [string, string] | undefined {
  const match = /^library\/sources\/([^/]+)\/(.+)$/u.exec(path);
  return match === null ? undefined : [match[1]!, match[2]!];
}

function sourceExtractionId(path: string): readonly string[] {
  const parsed = sourceFile(path);
  return parsed?.[0] !== undefined && parsed[0] !== "" && parsed[1] === "extracted.md" ? [parsed[0]] : [];
}

function promptIdFor(path: string): string | undefined {
  const match = /^prompts\/([a-z0-9][a-z0-9-]*)\.md$/u.exec(path);
  return match === null || match[1] === "README" ? undefined : match[1];
}

function articleFile(path: string): { readonly editionKey: string; readonly logicalId: string; readonly language: string } | undefined {
  const match = /^editions\/([^/]+)\/(?:translations\/([^/]+)\/)?articles\/([^/]+)\.md$/u.exec(path);
  return match === null ? undefined : {
    editionKey: editionKey(match[1]!),
    logicalId: match[3]!,
    language: match[2] ?? "en",
  };
}

function editorialFile(path: string): { readonly editionKey: string; readonly language: string } | undefined {
  const match = /^editions\/([^/]+)\/(?:translations\/([^/]+)\/)?manuscript\/editorial\.md$/u.exec(path);
  return match === null ? undefined : { editionKey: editionKey(match[1]!), language: match[2] ?? "en" };
}

function editionImage(path: string): { readonly editionKey: string; readonly ordinal: string; readonly extension: string } | undefined {
  const match = /^editions\/([^/]+)\/(?:art|prototypes\/assets)\/(.+\.(png|jpe?g|webp))$/iu.exec(path);
  if (match === null) return undefined;
  const ordinal = match[2]!.replace(/\.(png|jpe?g|webp)$/iu, "").replace(/[^a-z0-9]+/giu, "-").replace(/^-+|-+$/gu, "").slice(0, 96);
  return { editionKey: editionKey(match[1]!), ordinal: ordinal || "asset", extension: `.${match[3]!.toLowerCase()}` };
}

function editionSpec(
  path: string,
  rootsWithManifest: ReadonlySet<string>,
): { readonly editionKey: string; readonly payloadPath: string } | undefined {
  const match = /^editions\/([^/]+)\/(.+)$/u.exec(path);
  if (match === null) return undefined;
  if (!rootsWithManifest.has(`editions/${match[1]}`)) return undefined;
  const relative = match[2]!;
  if (
    relative === "edition.yaml" ||
    /^translations\/[^/]+\/edition\.yaml$/u.test(relative) ||
    relative === "art/illustrations.yaml"
  ) return { editionKey: editionKey(match[1]!), payloadPath: relative };
  return undefined;
}

function editionRoot(path: string): string | undefined {
  const match = /^editions\/([^/]+)\//u.exec(path);
  return match === null ? undefined : `editions/${match[1]}`;
}

function editionNumber(root: string): string {
  const match = /^editions\/(\d{3})-/u.exec(root);
  return match?.[1] ?? "";
}

function editionKey(root: string): string {
  const rerun = /^rerun-(\d{3})-/u.exec(root)?.[1];
  if (rerun !== undefined) return `${rerun}-rerun`;
  const number = /^(\d{3})-/u.exec(root)?.[1];
  if (number === undefined) return root.replace(/[^a-z0-9]+/giu, "-").toLowerCase();
  return number;
}

function durableEditionId(key: string): string {
  const rerun = /^(\d{3})-rerun$/u.exec(key)?.[1];
  return rerun ?? key;
}

function selectedImageIdentities(
  edition: Record<string, unknown>,
  root: string,
  editionId: string,
): ReadonlyMap<string, LegacyDurableIdentity> {
  const selected = new Map<string, LegacyDurableIdentity>();
  const add = (candidate: unknown, logicalId: string) => {
    if (typeof candidate !== "string") return;
    portableName(logicalId, "durable logical ID");
    const path = candidate.startsWith("editions/") ? candidate : `${root}/${candidate}`;
    safeRepositoryPath(path);
    const identity = { editionId, logicalId } satisfies LegacyDurableIdentity;
    const prior = selected.get(path);
    if (prior !== undefined && !sameDurableIdentity(prior, identity)) {
      throw invalid(`edition manifest assigns conflicting durable identities to ${path}`);
    }
    selected.set(path, identity);
  };

  if (isMapping(edition.cover)) add(edition.cover.art_path, "cover");
  if (Array.isArray(edition.articles)) {
    for (const article of edition.articles) {
      if (!isMapping(article) || typeof article.id !== "string") continue;
      if (isMapping(article.opener_art)) add(article.opener_art.path, `${article.id}-opener`);
      add(article.tail_art_path, `${article.id}-tail`);
    }
  }
  if (Array.isArray(edition.closing_plates)) {
    for (const plate of edition.closing_plates) {
      if (!isMapping(plate) || typeof plate.art_path !== "string") continue;
      const filename = posix.basename(plate.art_path).replace(/\.(?:png|jpe?g|webp)$/iu, "");
      const logicalId = filename.replace(/[^a-z0-9]+/giu, "-").replace(/^-+|-+$/gu, "").toLowerCase();
      add(plate.art_path, logicalId);
    }
  }
  return selected;
}

function durableIdentityFromManifest(
  manifest: Record<string, unknown>,
  kind: LegacyMigrationTarget["revisionKind"],
): LegacyDurableIdentity | undefined {
  if (kind !== "article" && kind !== "editorial" && kind !== "image") return undefined;
  if (typeof manifest.edition_id !== "string" || typeof manifest.logical_id !== "string") return undefined;
  if (kind !== "image" && typeof manifest.language !== "string") return undefined;
  return {
    editionId: manifest.edition_id,
    logicalId: manifest.logical_id,
    ...(kind === "image" ? {} : { language: manifest.language as string }),
  };
}

function sameDurableIdentity(left: LegacyDurableIdentity, right: LegacyDurableIdentity): boolean {
  return left.editionId === right.editionId &&
    left.logicalId === right.logicalId &&
    left.language === right.language;
}

function withDurableParentBindings(
  entries: readonly LegacyFileDisposition[],
): readonly LegacyFileDisposition[] {
  const bySource = new Map(entries.map((entry) => [entry.source.path, entry]));
  const rerunPrefix = "editions/rerun-004-the-systems-around-the-model/";
  const originalPrefix = "editions/004-the-systems-around-the-model/";
  return entries.map((entry) => {
    const target = entry.targets[0]!;
    if (target.category !== "durable") return entry;
    let parentRevisionId: RevisionId | null = null;
    if (entry.source.path.startsWith(rerunPrefix)) {
      const counterpartPath = entry.source.path.replace(rerunPrefix, originalPrefix);
      const counterpart = bySource.get(counterpartPath);
      const counterpartTarget = counterpart?.targets[0];
      if (counterpartTarget?.category !== "durable" ||
        target.durableIdentity === undefined || counterpartTarget.durableIdentity === undefined ||
        target.revisionKind !== counterpartTarget.revisionKind ||
        !sameDurableIdentity(target.durableIdentity, counterpartTarget.durableIdentity)) {
        throw invalid(`rerun durable item has no exact original identity: ${entry.source.path}`);
      }
      parentRevisionId = counterpartTarget.revisionId;
    }
    return { ...entry, targets: [{ ...target, parentRevisionId }] };
  });
}

function validateDurableIdentity(target: LegacyMigrationTarget): void {
  const identity = target.durableIdentity!;
  if (target.category !== "durable" ||
    (target.revisionKind !== "article" && target.revisionKind !== "editorial" && target.revisionKind !== "image")) {
    throw invalid("only durable article, editorial, and image targets may declare durable identity");
  }
  portableName(identity.editionId, "durable edition ID");
  portableName(identity.logicalId, "durable logical ID");
  if (target.revisionKind === "image") {
    if (identity.language !== undefined) throw invalid("durable image identity must not declare language");
  } else {
    if (identity.language === undefined) throw invalid("durable manuscript identity must declare language");
    portableName(identity.language, "durable language");
  }
}

function exact(
  source: LegacyGitFile,
  disposition: LegacyDisposition,
  target: LegacyMigrationTarget,
  basis: string,
): LegacyFileDisposition {
  return { source, disposition, targets: [target], basis };
}

function canonicalInventorySha256(files: readonly LegacyGitFile[]): string {
  const canonical = [...files].sort((a, b) => a.path.localeCompare(b.path)).map((file) =>
    `${file.path}\0${file.mode}\0${file.blobOid}\0${file.sha256}\0${file.sizeBytes}\n`
  ).join("");
  return sha256(Buffer.from(canonical, "utf8"));
}

function sha256(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function assertNoUnsafeOrAliasedPaths(paths: readonly string[]): void {
  const aliases = new Set<string>();
  for (const path of paths) {
    safeRepositoryPath(path);
    const key = path.normalize("NFC").toLocaleLowerCase("en-US");
    if (aliases.has(key)) throw invalid(`legacy inventory has a case or Unicode-normalization alias: ${path}`);
    aliases.add(key);
  }
}

function safeRepositoryPath(path: string): void {
  if (!LEGACY_ROOTS.some((root) => path === root || path.startsWith(`${root}/`))) {
    throw invalid(`legacy inventory path is outside the protected roots: ${path}`);
  }
  safeRelative(path);
}

function safeRelative(path: string): void {
  if (path.length === 0 || path.includes("\\") || path.includes("\0") || posix.isAbsolute(path) ||
    posix.normalize(path) !== path || path.split("/").some((part) => part === "" || part === "." || part === "..")) {
    throw invalid(`unsafe relative path: ${path}`);
  }
}

function portableLegacyPayloadPath(path: string): string {
  const portable = path.split("/").map((component) => component.normalize("NFC").toLowerCase()).join("/");
  safeRelative(portable);
  for (const component of portable.split("/")) portableName(component, "legacy payload component");
  return portable;
}

function portableName(value: string, label: string): void {
  if (!/^[a-z0-9][a-z0-9._-]{0,127}$/u.test(value)) throw invalid(`invalid ${label}: ${value}`);
}

function contained(root: string, child: string): string {
  const base = resolve(root);
  const target = resolve(base, child);
  if (target === base || !target.startsWith(`${base}${sep}`)) throw invalid(`path escapes staging root: ${child}`);
  return target;
}

function relativePortable(root: string, path: string): string {
  const relative = path.slice(root.length + 1).replaceAll("\\", "/");
  safeRelative(relative);
  return relative;
}

function required<T>(value: T | undefined, label: string): T {
  if (value === undefined) throw invalid(`missing value: ${label}`);
  return value;
}

function isMapping(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isMigratableKind(value: string): value is LegacyMigrationTarget["revisionKind"] {
  return [
    "source_capture",
    "source_extraction",
    "prompt",
    "policy",
    "edition_spec",
    "article",
    "editorial",
    "image",
  ].includes(value);
}

function invalid(message: string): LegacyRootMigrationError {
  return new LegacyRootMigrationError("LEGACY_ROOT_MIGRATION_INVALID", message);
}

async function gitBuffer(root: string, args: readonly string[]): Promise<Buffer> {
  try {
    const result = await execFile("git", args, { cwd: root, encoding: "buffer", maxBuffer: 16 * 1024 * 1024 });
    return Buffer.from(result.stdout);
  } catch (error) {
    throw new LegacyRootMigrationError("LEGACY_ROOT_MIGRATION_GIT", `git ${args[0]} failed`, { cause: error });
  }
}

async function gitText(root: string, args: readonly string[]): Promise<string> {
  return (await gitBuffer(root, args)).toString("utf8").trim();
}

function isAllowedLegacyReference(path: string): boolean {
  return path.startsWith("engine/migration/") ||
    /(^|\/)engine\/test\/.*migration.*\.test\.ts$/u.test(path) ||
    path.startsWith("docs/adr/");
}

async function sourceFiles(root: string, prefix = ""): Promise<readonly string[]> {
  const ignored = new Set([".git", "node_modules", ".magazine", "output", "editions", "library", "prompts"]);
  const entries = await readdir(join(root, prefix), { withFileTypes: true });
  const result: string[] = [];
  for (const entry of entries) {
    if (ignored.has(entry.name) && prefix === "") continue;
    const next = join(prefix, entry.name);
    if (entry.isDirectory()) result.push(...await sourceFiles(root, next));
    else if (entry.isFile() && /\.(?:ts|tsx|md|json|yaml|yml|toml)$/u.test(entry.name)) result.push(join(root, next));
  }
  return result;
}
