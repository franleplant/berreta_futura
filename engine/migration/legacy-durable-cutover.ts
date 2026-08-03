import { execFile as execFileCallback } from "node:child_process";
import { basename, extname, join } from "node:path";
import { promisify } from "node:util";

import { parse } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import type { CompositionDocument } from "../durable/composition-schema.ts";
import { GitCliDurableGit } from "../durable/git-cli.ts";
import { materializeLegacyDurableMigrationBatch } from "../durable/legacy-durable-migration.ts";
import type {
  InputRevisionRef,
  DurableRevisionRef,
} from "../durable/types.ts";
import type {
  HistoricalCompositionEntry,
  LegacyDurableBatchMigrationPlan,
  LegacyDurableRevisionEntry,
  MigrationPlanRevisionRef,
} from "../durable/legacy-durable-migration.ts";
import type {
  LegacyMigrationTarget,
  LegacyRootMigrationPlan,
} from "./legacy-root-migration.ts";

const execFile = promisify(execFileCallback);

export const LEGACY_DURABLE_SOURCE_COMMIT =
  "5097aab2154be41b9315adfc1bf737898217be73";
export const LEGACY_DURABLE_PLAN_REVISION =
  "rev_20260803T054439271Z_bg2bfnprnbd4" as RevisionId;
export const LEGACY_DURABLE_PLAN_PATH =
  `inputs/migrations/legacy-four-root/revisions/${LEGACY_DURABLE_PLAN_REVISION}/inventory.yaml`;

export const LEGACY_DURABLE_BATCH_COUNTS = {
  "001": 11,
  "002": 52,
  "003": 68,
  "004-base": 28,
  "004-rerun": 53,
  compositions: 3,
} as const;

export type LegacyDurableBatchGroup = keyof typeof LEGACY_DURABLE_BATCH_COUNTS;

type LegacyYaml = Record<string, unknown>;

export type LegacyDurablePlanningSources = {
  /** Parsed only from protected Git blobs, never from the working tree. */
  readonly editionDocuments: ReadonlyMap<string, LegacyYaml>;
};

/**
 * Builds a read-only batch from the immutable durable-identity ledger. The
 * planner intentionally never derives a DurableRevision identity from a
 * revisionSlot: the slot is used only to locate exact input revisions in the
 * ledger.
 */
export function planLegacyDurableBatch(
  ledger: LegacyRootMigrationPlan,
  sources: LegacyDurablePlanningSources,
  group: LegacyDurableBatchGroup,
  migrationPlanRevisionId: RevisionId = LEGACY_DURABLE_PLAN_REVISION,
): LegacyDurableBatchMigrationPlan {
  assertLedger(ledger);
  const migrationPlan = migrationPlanRef(ledger.migrationId, migrationPlanRevisionId);
  const inputTargets = indexInputTargets(ledger);
  const selected = ledger.files.flatMap((file) => {
    const target = file.targets[0]!;
    return file.disposition === "import_exact" &&
      target.category === "durable" && targetGroup(file.source.path, target) === group
      ? [{ sourcePath: file.source.path, target }]
      : [];
  });

  const entries = group === "compositions"
    ? []
    : selected.map(({ sourcePath, target }) => durableEntry(
      sourcePath,
      target,
      sources,
      inputTargets,
      migrationPlan,
    ));
  const compositions = group === "compositions"
    ? historicalCompositions(ledger, sources, inputTargets, migrationPlan)
    : [];

  const expected = LEGACY_DURABLE_BATCH_COUNTS[group];
  const actual = group === "compositions" ? compositions.length : entries.length;
  if (actual !== expected) {
    throw new Error(`legacy durable batch ${group} expected ${expected} revisions, found ${actual}`);
  }
  const sourcePaths = [...unique([
    ...entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
    ...compositions.flatMap((entry) => entry.sourcePaths),
  ])].sort();
  const blobs = new Map(ledger.sourceSnapshot.files.map((file) => [file.path, file.blobOid]));
  const blobOids = Object.fromEntries(sourcePaths.map((path) => {
    const oid = blobs.get(path);
    if (oid === undefined) throw new Error(`ledger has no protected blob for ${path}`);
    return [path, oid];
  }));
  return {
    schemaVersion: "legacy-durable-migration/2",
    migrationId: ledger.migrationId,
    migrationPlanRevision: migrationPlan,
    sourceGitBinding: { commitOid: ledger.sourceSnapshot.sourceCommitOid, blobOids },
    entries,
    compositions,
  };
}

/** Reads the ledger at HEAD and all edition YAML only through protected blobs. */
export async function readLegacyDurablePlanningInputs(
  repositoryRoot: string,
  sourceCommit: string,
  migrationPlanRevisionId: RevisionId = LEGACY_DURABLE_PLAN_REVISION,
): Promise<{ readonly ledger: LegacyRootMigrationPlan; readonly sources: LegacyDurablePlanningSources }> {
  if (sourceCommit !== LEGACY_DURABLE_SOURCE_COMMIT) {
    throw new Error(`legacy durable cutover requires protected source commit ${LEGACY_DURABLE_SOURCE_COMMIT}`);
  }
  const planPath = `inputs/migrations/legacy-four-root/revisions/${migrationPlanRevisionId}/inventory.yaml`;
  const ledger = yaml(await gitText(repositoryRoot, ["show", `HEAD:${planPath}`]), planPath) as LegacyRootMigrationPlan;
  assertLedger(ledger);
  if (ledger.sourceSnapshot.sourceCommitOid !== sourceCommit) {
    throw new Error("ledger source commit does not match the command");
  }
  const editionPaths = ledger.files.flatMap((file) => {
    const target = file.targets[0]!;
    return target.revisionKind === "edition_spec" && file.source.path.endsWith(".yaml")
      ? [file.source.path]
      : [];
  });
  const editionDocuments = new Map<string, LegacyYaml>();
  for (const path of editionPaths) {
    editionDocuments.set(path, yaml(await gitText(repositoryRoot, ["show", `${sourceCommit}:${path}`]), path));
  }
  return { ledger, sources: { editionDocuments } };
}

/** Plans or explicitly materializes one ordered historical batch. */
export async function main(argv = process.argv.slice(2)): Promise<void> {
  const [command, sourceCommit, planRevision, group] = argv;
  if ((command !== "plan" && command !== "materialize") ||
    sourceCommit === undefined || planRevision === undefined || !isGroup(group)) {
    throw usage();
  }
  const inputs = await readLegacyDurablePlanningInputs(
    process.cwd(),
    sourceCommit,
    planRevision as RevisionId,
  );
  const plan = planLegacyDurableBatch(inputs.ledger, inputs.sources, group, planRevision as RevisionId);
  const paths = [...unique([
    ...plan.entries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
    ...plan.compositions.flatMap((entry) => entry.sourcePaths),
  ])].sort();
  if (command === "materialize") {
    const materialized = await materializeLegacyDurableMigrationBatch(
      process.cwd(),
      join(process.cwd(), ".magazine", "migrations", plan.migrationId, "durable", group),
      plan,
      new GitCliDurableGit(process.cwd()),
    );
    process.stdout.write(`${JSON.stringify({
      status: "materialized",
      group,
      migrationId: materialized.migrationId,
      sourceCommitOid: plan.sourceGitBinding.commitOid,
      migrationPlanRevisionId: planRevision,
      revisions: materialized.revisions,
      repositoryPaths: materialized.repositoryPaths,
      manifestDigests: materialized.manifestDigests,
    }, null, 2)}\n`);
    return;
  }
  process.stdout.write(`${JSON.stringify({
    status: "planned",
    group,
    migrationId: plan.migrationId,
    sourceCommitOid: plan.sourceGitBinding.commitOid,
    migrationPlanRevisionId: planRevision,
    revisions: plan.entries.length + plan.compositions.length,
    durableEntries: plan.entries.length,
    compositions: plan.compositions.length,
    sourcePaths: paths,
  }, null, 2)}\n`);
}

function durableEntry(
  sourcePath: string,
  target: LegacyMigrationTarget,
  sources: LegacyDurablePlanningSources,
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
  migrationPlan: InputRevisionRef,
): LegacyDurableRevisionEntry {
  const ref = durableRef(target);
  const edition = editionFor(sourcePath, sources.editionDocuments);
  const inputRevisions = target.revisionKind === "article"
    ? articleInputs(edition, inputTargets, migrationPlan)
    : target.revisionKind === "editorial"
      ? editorialInputs(edition, inputTargets, migrationPlan)
      : imageInputs(sourcePath, edition, inputTargets, migrationPlan);
  return {
    ref,
    createdAt: revisionInstant(target.revisionId),
    parentRevisionId: target.parentRevisionId ?? null,
    inputRevisions,
    files: [{ sourcePath, targetPath: target.payloadPath, mediaType: mediaType(sourcePath) }],
  };
}

function historicalCompositions(
  ledger: LegacyRootMigrationPlan,
  sources: LegacyDurablePlanningSources,
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
  migrationPlan: InputRevisionRef,
): readonly HistoricalCompositionEntry[] {
  return ledger.historicalCompositions
    .filter((entry) => entry.editionId !== "004" && entry.state === "legacy-current-snapshot")
    .map((entry) => {
      const editionPath = editionManifestPath(ledger, entry.editionId, "en");
      const spanishPath = editionManifestPath(ledger, entry.editionId, "es");
      const illustrationPath = illustrationManifestPath(ledger, entry.editionId);
      const edition = required(sources.editionDocuments.get(editionPath), editionPath);
      const document = compositionDocument(entry.editionId as "001" | "002" | "003", entry.compositionId, edition, ledger, inputTargets);
      return {
        ref: {
          kind: "composition",
          editionId: entry.editionId,
          compositionId: entry.compositionId,
          revisionId: entry.revisionId,
        },
        createdAt: revisionInstant(entry.revisionId),
        parentRevisionId: null,
        sourcePaths: [...unique([editionPath, spanishPath, ...(illustrationPath === undefined ? [] : [illustrationPath])])].sort(),
        document,
        assemblyBasis: "historical snapshot assembled from protected legacy manifests; no release authority is imported",
        extraInputRevisions: [migrationPlan],
      };
    });
}

function compositionDocument(
  editionId: "001" | "002" | "003",
  compositionId: string,
  edition: LegacyYaml,
  ledger: LegacyRootMigrationPlan,
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
): CompositionDocument {
  const articles = array(edition.articles, "edition articles").map((article) => {
    const articleId = string(object(article, "article").id, "article id");
    return {
      article_id: articleId,
      manuscripts: [
        { language: "en", revision: findDurable(ledger, "article", editionId, articleId, "en") },
        { language: "es", revision: findDurable(ledger, "article", editionId, articleId, "es") },
      ],
      images: imagePins(articleImages(article, edition), ledger),
    };
  });
  const editorialId = "opening";
  const cover = object(edition.cover, "edition cover");
  const images = [
    imagePin("cover", imageByPath(ledger, fullEditionPath(edition, string(cover.art_path, "cover art path")))),
    ...closingPins(edition, ledger),
  ];
  return {
    schema_version: 1,
    edition_id: editionId,
    composition_id: compositionId,
    editorials: [{
      editorial_id: editorialId,
      manuscripts: [
        { language: "en", revision: findDurable(ledger, "editorial", editionId, editorialId, "en") },
        { language: "es", revision: findDurable(ledger, "editorial", editionId, editorialId, "es") },
      ],
    }],
    articles,
    images,
    layout_inputs: [{
      slot_id: "edition-spec",
      revision: editionSpecRef(editionId, inputTargets),
    }],
  };
}

function articleInputs(
  edition: EditionContext,
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
  migrationPlan: InputRevisionRef,
): readonly InputRevisionRef[] {
  const article = object(edition.article, "article manifest entry");
  const sourceIds = array(article.source_ids, "article source_ids").map((id) => string(id, "source id"));
  return uniqueRefs([
    migrationPlan,
    editionSpecRef(edition.editionId, inputTargets, edition.specKey),
    ...sourceInputs(sourceIds, inputTargets),
  ]);
}

function editorialInputs(
  edition: EditionContext,
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
  migrationPlan: InputRevisionRef,
): readonly InputRevisionRef[] {
  const sourceIds = array(edition.edition.sources, "edition sources").map((id) => string(id, "source id"));
  return uniqueRefs([
    migrationPlan,
    editionSpecRef(edition.editionId, inputTargets, edition.specKey),
    ...sourceInputs(sourceIds, inputTargets),
  ]);
}

function imageInputs(
  sourcePath: string,
  edition: EditionContext,
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
  migrationPlan: InputRevisionRef,
): readonly InputRevisionRef[] {
  return imageNamedByEdition(sourcePath, edition)
    ? [migrationPlan, editionSpecRef(edition.editionId, inputTargets, edition.specKey)]
    : [migrationPlan];
}

function sourceInputs(
  sourceIds: readonly string[],
  inputTargets: ReadonlyMap<string, LegacyMigrationTarget>,
): readonly InputRevisionRef[] {
  return sourceIds.flatMap((id) => (["source_capture", "source_extraction"] as const).flatMap((kind) => {
    const target = inputTargets.get(`input:${kind}:${id}`);
    return target === undefined ? [] : [inputRef(target)];
  }));
}

type EditionContext = {
  readonly editionId: string;
  readonly specKey: string;
  readonly root: string;
  readonly edition: LegacyYaml;
  readonly article?: unknown;
  readonly illustrations?: LegacyYaml;
};

function editionFor(sourcePath: string, documents: ReadonlyMap<string, LegacyYaml>): EditionContext {
  const root = editionRoot(sourcePath);
  const editionPath = `${root}/edition.yaml`;
  const edition = required(documents.get(editionPath), editionPath);
  const article = articleIdFromSource(sourcePath) === undefined
    ? undefined
    : required(array(edition.articles, "edition articles").find((value) =>
      object(value, "article").id === articleIdFromSource(sourcePath),
    ), sourcePath);
  const illustrations = documents.get(`${root}/art/illustrations.yaml`);
  return {
    editionId: root.startsWith("editions/rerun-004-") ? "004" : editionNumber(root),
    specKey: root.startsWith("editions/rerun-004-") ? "004-rerun" : editionNumber(root),
    root,
    edition,
    ...(article === undefined ? {} : { article }),
    ...(illustrations === undefined ? {} : { illustrations }),
  };
}

function imageNamedByEdition(sourcePath: string, context: EditionContext): boolean {
  const named = new Set<string>();
  collectArtPaths(context.edition, context.root, named);
  if (context.illustrations !== undefined) collectArtPaths(context.illustrations, context.root, named);
  return named.has(sourcePath);
}

function collectArtPaths(value: unknown, root: string, paths: Set<string>): void {
  if (Array.isArray(value)) {
    for (const item of value) collectArtPaths(item, root, paths);
    return;
  }
  if (!isObject(value)) return;
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "string" &&
      (key === "art_path" || key.endsWith("_art_path") || (key === "path" && /(?:^|\/)art\//u.test(item)))) {
      paths.add(resolveEditionPath(root, item));
    }
    else collectArtPaths(item, root, paths);
  }
}

function articleImages(article: unknown, edition: LegacyYaml): readonly string[] {
  const value = object(article, "article");
  const tail = typeof value.tail_art_path === "string"
    ? [fullEditionPath(edition, value.tail_art_path)]
    : [];
  return tail;
}

function closingPins(edition: LegacyYaml, ledger: LegacyRootMigrationPlan) {
  return array(edition.closing_plates ?? [], "closing plates").map((plate) => {
    const path = string(object(plate, "closing plate").art_path, "closing plate art path");
    const revision = imageByPath(ledger, fullEditionPath(edition, path));
    return imagePin(revision.logicalId, revision);
  });
}

function imagePins(paths: readonly string[], ledger: LegacyRootMigrationPlan) {
  return paths.map((path, index) => imagePin(index === 0 ? "tail" : `tail-${index + 1}`, imageByPath(ledger, path)));
}

function imagePin(slot_id: string, revision: Extract<DurableRevisionRef, { readonly kind: "image" }>) {
  return { slot_id, revision };
}

function imageByPath(ledger: LegacyRootMigrationPlan, sourcePath: string) {
  const match = ledger.files.find((file) => file.source.path === sourcePath && file.targets[0]?.revisionKind === "image");
  if (match === undefined) throw new Error(`no exact durable image identity for ${sourcePath}`);
  return durableRef(match.targets[0]! as LegacyMigrationTarget) as Extract<DurableRevisionRef, { readonly kind: "image" }>;
}

function findDurable<K extends "article" | "editorial">(
  ledger: LegacyRootMigrationPlan,
  kind: K,
  editionId: string,
  logicalId: string,
  language: string,
): Extract<DurableRevisionRef, { readonly kind: K }> {
  const target = ledger.files.map((file) => file.targets[0]!).find((candidate) =>
    candidate.category === "durable" && candidate.revisionKind === kind &&
    candidate.durableIdentity?.editionId === editionId &&
    candidate.durableIdentity.logicalId === logicalId && candidate.durableIdentity.language === language,
  );
  if (target === undefined) throw new Error(`no exact ${kind} revision for ${editionId}/${logicalId}/${language}`);
  return durableRef(target) as Extract<DurableRevisionRef, { readonly kind: K }>;
}

function durableRef(target: LegacyMigrationTarget): Exclude<DurableRevisionRef, { readonly kind: "composition" }> {
  const identity = target.durableIdentity;
  if (target.category !== "durable" || identity === undefined) {
    throw new Error("durable revision must be derived from a ledger durableIdentity");
  }
  if (target.revisionKind === "image") {
    return { kind: "image", editionId: identity.editionId, logicalId: identity.logicalId, revisionId: target.revisionId };
  }
  if ((target.revisionKind !== "article" && target.revisionKind !== "editorial") || identity.language === undefined) {
    throw new Error("ledger durable identity does not match its durable kind");
  }
  return {
    kind: target.revisionKind,
    editionId: identity.editionId,
    logicalId: identity.logicalId,
    language: identity.language,
    revisionId: target.revisionId,
  };
}

function indexInputTargets(ledger: LegacyRootMigrationPlan): ReadonlyMap<string, LegacyMigrationTarget> {
  const targets = new Map<string, LegacyMigrationTarget>();
  for (const file of ledger.files) {
    const target = file.targets[0]!;
    if (target.category === "input") targets.set(target.revisionSlot, target);
  }
  return targets;
}

function editionSpecRef(
  editionId: string,
  targets: ReadonlyMap<string, LegacyMigrationTarget>,
  key = editionId,
): InputRevisionRef {
  const target = required(targets.get(`input:edition_spec:${key}`), `edition specification ${key}`);
  return inputRef(target);
}

function inputRef(target: LegacyMigrationTarget): InputRevisionRef {
  const logicalId = target.revisionSlot.split(":").slice(2).join(":");
  switch (target.revisionKind) {
    case "source_capture":
    case "source_extraction":
      return { kind: target.revisionKind, logicalId, revisionId: target.revisionId };
    case "edition_spec":
      return {
        kind: "edition_spec",
        logicalId: logicalId === "004-rerun" ? "legacy-rerun" : "main",
        editionId: logicalId === "004-rerun" ? "004" : logicalId,
        revisionId: target.revisionId,
      };
    default:
      throw new Error(`target ${target.revisionSlot} is not a supported input revision`);
  }
}

function migrationPlanRef(migrationId: string, revisionId: RevisionId): MigrationPlanRevisionRef {
  return { kind: "migration_plan", logicalId: migrationId, revisionId };
}

function targetGroup(sourcePath: string, target: LegacyMigrationTarget): LegacyDurableBatchGroup | undefined {
  const id = target.durableIdentity?.editionId;
  if (id === "001" || id === "002" || id === "003") return id;
  if (id !== "004") return undefined;
  return sourcePath.startsWith("editions/rerun-004-") ? "004-rerun" : "004-base";
}

function editionManifestPath(ledger: LegacyRootMigrationPlan, editionId: string, language: "en" | "es"): string {
  const suffix = language === "en" ? "/edition.yaml" : "/translations/es/edition.yaml";
  const entry = ledger.files.find((file) => file.source.path.startsWith(`editions/${editionId}-`) && file.source.path.endsWith(suffix));
  if (entry === undefined) throw new Error(`protected Edition ${editionId} ${language} manifest is missing`);
  return entry.source.path;
}

function illustrationManifestPath(ledger: LegacyRootMigrationPlan, editionId: string): string | undefined {
  return ledger.files.find((file) => file.source.path.startsWith(`editions/${editionId}-`) && file.source.path.endsWith("/art/illustrations.yaml"))?.source.path;
}

function fullEditionPath(edition: LegacyYaml, path: string): string {
  const root = editionRootFromId(string(edition.id, "edition id"));
  return resolveEditionPath(root, path);
}

function editionRootFromId(id: string): string {
  const known = {
    "001-the-work-left-to-us": "editions/001-the-work-left-to-us",
    "002-unreleased": "editions/002-unreleased",
    "003-unreleased": "editions/003-unreleased",
  } as const;
  const root = known[id as keyof typeof known];
  if (root === undefined) throw new Error(`unsupported historical edition ${id}`);
  return root;
}

function resolveEditionPath(root: string, path: string): string {
  return path.startsWith("editions/") ? path : `${root}/${path}`;
}

function editionRoot(path: string): string {
  const match = /^(editions\/(?:rerun-)?\d{3}-[^/]+)/u.exec(path);
  if (match === null) throw new Error(`durable source is not in an edition root: ${path}`);
  return match[1]!;
}

function editionNumber(root: string): string {
  const match = /(?:rerun-)?(\d{3})-/u.exec(basename(root));
  if (match === null) throw new Error(`cannot determine edition number from ${root}`);
  return match[1]!;
}

function articleIdFromSource(path: string): string | undefined {
  return /\/articles\/([^/]+)\.md$/u.exec(path)?.[1];
}

function revisionInstant(revisionId: RevisionId): string {
  const match = /^rev_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z_/u.exec(revisionId);
  if (match === null) throw new Error(`cannot read revision time from ${revisionId}`);
  return `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}.${match[7]}Z`;
}

function mediaType(path: string): string {
  switch (extname(path).toLowerCase()) {
    case ".md": return "text/markdown";
    case ".png": return "image/png";
    case ".jpg":
    case ".jpeg": return "image/jpeg";
    case ".webp": return "image/webp";
    default: throw new Error(`unsupported durable payload type: ${path}`);
  }
}

function uniqueRefs(refs: readonly InputRevisionRef[]): readonly InputRevisionRef[] {
  const seen = new Set<string>();
  return refs.filter((ref) => {
    const key = JSON.stringify(ref);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function unique(values: readonly string[]): readonly string[] {
  return [...new Set(values)];
}

function assertLedger(ledger: LegacyRootMigrationPlan): void {
  if (ledger.schemaVersion !== "legacy-root-migration/1" || ledger.durableIdentityContract !== "durable-identity/1") {
    throw new Error("legacy durable cutover requires a durable-identity/1 ledger");
  }
  if (ledger.sourceSnapshot.sourceCommitOid !== LEGACY_DURABLE_SOURCE_COMMIT) {
    throw new Error("legacy durable ledger does not name the protected source commit");
  }
  for (const file of ledger.files) {
    const target = file.targets[0];
    if (target?.category === "durable" && (target.durableIdentity === undefined || target.parentRevisionId === undefined)) {
      throw new Error(`durable ledger target lacks exact identity or parent: ${file.source.path}`);
    }
  }
}

function yaml(text: string, path: string): LegacyYaml {
  const value = parse(text);
  if (!isObject(value)) throw new Error(`${path} is not a YAML mapping`);
  return value;
}

function object(value: unknown, label: string): LegacyYaml {
  if (!isObject(value)) throw new Error(`${label} is not a mapping`);
  return value;
}

function array(value: unknown, label: string): readonly unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} is not an array`);
  return value;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string") throw new Error(`${label} is not a string`);
  return value;
}

function required<T>(value: T | undefined, label: string): T {
  if (value === undefined) throw new Error(`missing ${label}`);
  return value;
}

function isObject(value: unknown): value is LegacyYaml {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isGroup(value: string | undefined): value is LegacyDurableBatchGroup {
  return value !== undefined && value in LEGACY_DURABLE_BATCH_COUNTS;
}

async function gitText(root: string, args: readonly string[]): Promise<string> {
  const result = await execFile("git", args, { cwd: root, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  return result.stdout;
}

function usage(): Error {
  return new Error(
    "usage: legacy-durable-cutover.ts <plan|materialize> <protected-source-commit> <migration-plan-revision-id> " +
    "<001|002|003|004-base|004-rerun|compositions>",
  );
}

if (process.argv[1] !== undefined && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  await main();
}
