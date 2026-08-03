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

import { stringify } from "yaml";

import { newRevisionId } from "../durable/revision-id.ts";
import type { RevisionId } from "../contracts/index.ts";

const execFile = promisify(execFileCallback);
const LEGACY_ROOTS = ["editions", "library", "prompts"] as const;
const EDITION4_ROOT = "editions/004-the-systems-around-the-model";
const EDITION4_SOURCE_IDS = new Set([
  "anatomy-of-a-frontier-lab-agent-intrusion-a-tech-8088c1df",
  "eval-engineering-the-step-that-turns-a-200-model-9f6f868f",
  "pragmatic-leverage-in-the-software-factory-09879736",
  "22580-from-gpt2-to-kimi3-explained-8f01b0fe",
  "architecture-overview-ce5cb1d1",
  "the-2026-07-28-mcp-specification-release-candida-1a1752b8",
  "software-factories-are-super-real-but-the-factor-ab8ad3ab",
  "factories-are-not-a-token-or-llm-problem-ba5fabbf",
  "do-not-make-the-service-bus-non-deterministic-3a92442c",
]);
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
  readonly migrationId: string;
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
  readonly allocateRevisionId?: () => RevisionId;
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
export async function readLegacyGitSnapshot(repositoryRoot: string): Promise<LegacyGitSnapshot> {
  const root = resolve(repositoryRoot);
  const sourceCommitOid = await gitText(root, ["rev-parse", "HEAD^{commit}"]);
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
        disposition.push(exact(file, EDITION4_SOURCE_IDS.has(sourceId) ? "reuse_existing" : "import_exact", {
          revisionSlot: slot,
          category: "input",
          revisionKind: "source_extraction",
          revisionId: revisionId(slot),
          payloadPath: "extracted.md",
          ...(EDITION4_SOURCE_IDS.has(sourceId) ? { reuseBinding: "edition4-fixed-revision" as const } : {}),
        }, "committed source extraction"));
      } else {
        const slot = `input:source_capture:${sourceId}`;
        disposition.push(exact(file, EDITION4_SOURCE_IDS.has(sourceId) ? "reuse_existing" : "import_exact", {
          revisionSlot: slot,
          category: "input",
          revisionKind: "source_capture",
          revisionId: revisionId(slot),
          payloadPath: `raw/${suffix}`,
          ...(EDITION4_SOURCE_IDS.has(sourceId) ? { reuseBinding: "edition4-fixed-revision" as const } : {}),
        }, "committed source evidence, record, or media"));
      }
      continue;
    }

    const promptId = promptIdFor(file.path);
    if (promptId !== undefined) {
      const slot = `input:prompt:${promptId}`;
      disposition.push(exact(file, "import_exact", {
        revisionSlot: slot,
        category: "input",
        revisionKind: "prompt",
        revisionId: revisionId(slot),
        payloadPath: "prompt.md",
      }, "legacy prompt source"));
      continue;
    }
    if (file.path === "prompts/README.md") {
      const slot = "input:policy:review-bench";
      disposition.push(exact(file, "import_exact", {
        revisionSlot: slot,
        category: "input",
        revisionKind: "policy",
        revisionId: revisionId(slot),
        payloadPath: "policy.md",
      }, "legacy prompt-set policy"));
      continue;
    }

    const article = articleFile(file.path);
    if (article !== undefined) {
      const slot = `durable:article:${article.editionKey}:${article.logicalId}:${article.language}`;
      disposition.push(exact(file, isEdition4Original(file.path) ? "reuse_existing" : "import_exact", {
        revisionSlot: slot,
        category: "durable",
        revisionKind: "article",
        revisionId: revisionId(slot),
        payloadPath: "manuscript.md",
        ...(isEdition4Original(file.path) ? { reuseBinding: "edition4-fixed-revision" as const } : {}),
      }, "legacy article manuscript"));
      continue;
    }
    const editorial = editorialFile(file.path);
    if (editorial !== undefined) {
      const slot = `durable:editorial:${editorial.editionKey}:opening:${editorial.language}`;
      disposition.push(exact(file, isEdition4Original(file.path) ? "reuse_existing" : "import_exact", {
        revisionSlot: slot,
        category: "durable",
        revisionKind: "editorial",
        revisionId: revisionId(slot),
        payloadPath: "manuscript.md",
        ...(isEdition4Original(file.path) ? { reuseBinding: "edition4-fixed-revision" as const } : {}),
      }, "legacy opening editorial"));
      continue;
    }
    const image = editionImage(file.path);
    if (image !== undefined) {
      const slot = `durable:image:${image.editionKey}:${image.ordinal}`;
      disposition.push(exact(file, isSelectedEdition4Image(file.path) ? "reuse_existing" : "import_exact", {
        revisionSlot: slot,
        category: "durable",
        revisionKind: "image",
        revisionId: revisionId(slot),
        payloadPath: `image${image.extension}`,
        ...(isSelectedEdition4Image(file.path) ? { reuseBinding: "edition4-fixed-revision" as const } : {}),
      }, "legacy art asset, including unselected candidates"));
      continue;
    }
    const spec = editionSpec(file.path, editionRootsWithManifest);
    if (spec !== undefined) {
      const slot = `input:edition_spec:${spec.editionKey}`;
      disposition.push(exact(file, "import_exact", {
        revisionSlot: slot,
        category: "input",
        revisionKind: "edition_spec",
        revisionId: revisionId(slot),
        payloadPath: spec.payloadPath,
      }, "edition or layout specification"));
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
  assertCompleteLedger(snapshot, disposition);
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
    migrationId: options.migrationId,
    sourceSnapshot: snapshot,
    allocatedRevisionIds: Object.fromEntries([...ids.entries()].sort(([a], [b]) => a.localeCompare(b))),
    files: disposition,
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
    relative === "art/illustrations.yaml" ||
    /^art\/cover-candidates(?:-[a-z0-9-]+)?\.yaml$/u.test(relative)
  ) return { editionKey: editionKey(match[1]!), payloadPath: relative };
  return undefined;
}

function isEdition4Original(path: string): boolean {
  return path.startsWith(`${EDITION4_ROOT}/articles/`) ||
    path.startsWith(`${EDITION4_ROOT}/translations/es/articles/`) ||
    path === `${EDITION4_ROOT}/manuscript/editorial.md` ||
    path === `${EDITION4_ROOT}/translations/es/manuscript/editorial.md`;
}

function isSelectedEdition4Image(path: string): boolean {
  return path === `${EDITION4_ROOT}/art/cover-candidate-wildcard-v2.png` ||
    /^editions\/004-the-systems-around-the-model\/art\/article-openers\/.+\.png$/u.test(path) ||
    path === `${EDITION4_ROOT}/art/article-tails/factory-systems-problem.png` ||
    path === `${EDITION4_ROOT}/art/article-tails/mcp-four-vignettes.png` ||
    path === `${EDITION4_ROOT}/art/closing-signal-gates-manga.png` ||
    path === `${EDITION4_ROOT}/art/closing-memory-rings-manga.png` ||
    path === `${EDITION4_ROOT}/art/closing-protocol-exchange-manga.png`;
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
