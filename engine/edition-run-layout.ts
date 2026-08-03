import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  access,
  cp,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  rmdir,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import type {
  ActorView,
  ArtifactId,
  ArtifactView,
  DecisionId,
  DecisionView,
  EventId,
  JsonObject,
  RunId,
  RunOutcome,
  RunSpec,
  RunView,
  WorkOfferId,
} from "./contracts/index.ts";
import {
  GitCliDurableGit,
  resolveCompositionRevision,
  type DurableGit,
} from "./durable/index.ts";
import { exportStateMachineTopologyBundle } from "./graph-export.ts";
import {
  exportApprovedRender,
  materializeRenderProjection,
  type ApprovedRenderExportFile,
} from "./run-engine/approved-render-export.ts";
import { SqliteRunEngine } from "./run-engine/run-engine.ts";
import {
  type MigrationPlan,
  type MigrationRequest,
  type RunIdentityView,
  type RunMigrationFence,
  RunEngineError,
} from "./run-engine/types.ts";

export type EditionRunLayoutOptions = {
  readonly editionKey: string;
  /** Defaults to the output root's parent for embedded and test callers. */
  readonly repositoryRoot?: string;
  readonly outputRoot: string;
  /** Test and embedded callers may supply the same narrow verification seam. */
  readonly durableGit?: Pick<DurableGit, "assertCommitted">;
  /** Narrow deterministic seam for migration concurrency and rollback tests. */
  readonly migrationHook?: (point: EditionRunMigrationHook) => void | Promise<void>;
};

export type EditionRunMigrationHook =
  | "migrate.after_fence"
  | "migrate.after_candidate_install"
  | "relocate.after_fence"
  | "relocate.after_candidate_install";

export type EditionRunAllocationOptions = {
  /** A portable, immutable bootstrap identity such as an InputRevision ID. */
  readonly idempotencyKey?: string;
};

export type EditionRunPaths = {
  readonly runName: string;
  readonly internalDirectory: string;
  readonly publicDirectory: string;
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly workDirectory: string;
};

export type OpenEditionRun = EditionRunPaths & {
  readonly runId: RunId;
  readonly engine: SqliteRunEngine;
  close(): void;
};

export type EditionRunPublishOptions = {
  readonly expectedVisualDecisionId?: DecisionId;
};

export type EditionRunReviewProjectionOptions = {
  readonly expectedHeadSequence: number;
  readonly expectedOfferId: WorkOfferId;
  readonly independentCritic: {
    readonly result: "not_run" | "pass";
    readonly note: string;
  };
};

export type EditionRunReviewProjectionResult = {
  readonly runId: RunId;
  readonly runName: string;
  readonly headSequence: number;
  readonly offerId: WorkOfferId;
  readonly publicDirectory: string;
  readonly exportManifestPath: string;
  readonly physicalFileCount: number;
  readonly compositionRevision: CompositionRevisionBinding;
  readonly renderArtifactIds: readonly ArtifactId[];
  readonly renderArtifactSetDigest: string;
};

export type EditionRunPublishResult = {
  readonly runId: RunId;
  readonly runName: string;
  readonly publicDirectory: string;
  readonly exportManifestPath: string;
  readonly compositionRevision: CompositionRevisionBinding;
  readonly visualDecisionId: DecisionId;
};

export type EditionRunMigrationResult = {
  readonly plan: MigrationPlan;
  readonly outcome: RunOutcome;
};

export type EditionRunDiscovery = {
  readonly schemaVersion: "edition-run-discovery/1";
  readonly sourceDirectory: string;
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly databasePresent: boolean;
  readonly artifactDirectoryPresent: boolean;
  readonly artifactFileCount: number;
  readonly expectedRunId: RunId;
  readonly runs: readonly RunIdentityView[];
  readonly identityMatch: boolean;
  readonly verifiedRunName?: string;
  readonly verifiedArtifactIds?: readonly ArtifactId[];
};

export type EditionRunScratch = {
  readonly root: string;
  readonly stagedDirectory: string;
  readonly rendererWorkDirectory: string;
};

type CompositionRevisionBinding = {
  readonly artifactId: ArtifactId;
  readonly editionId: string;
  readonly compositionId: string;
  readonly revisionId: string;
  readonly manifestDigest: string;
  readonly gitCommitOid: string;
  readonly gitBlobOids: Readonly<Record<string, string>>;
};

type CurrentVisualApproval = {
  readonly actor: ActorView;
  readonly decision: DecisionView & {
    readonly artifactId: ArtifactId;
    readonly offerId: WorkOfferId;
  };
  readonly renderArtifactIds: readonly ArtifactId[];
};

type CurrentVisualReview = {
  readonly actor: ActorView;
  readonly offerId: WorkOfferId;
  readonly renderArtifactIds: readonly ArtifactId[];
};

/**
 * Owns the filesystem projection for one edition while RunEngine remains the
 * sole authority for workflow state and immutable artifacts.
 */
export class EditionRunLayout {
  readonly editionKey: string;
  readonly outputRoot: string;
  readonly inputsRoot: string;
  readonly durableRoot: string;
  readonly internalEditionRoot: string;
  readonly publicEditionRoot: string;
  private readonly repositoryRoot: string;
  private readonly durableGit: Pick<DurableGit, "assertCommitted">;
  private readonly migrationHook: (point: EditionRunMigrationHook) => void | Promise<void>;

  constructor(options: EditionRunLayoutOptions) {
    this.editionKey = safeEditionKey(options.editionKey);
    const requestedOutputRoot = resolve(options.outputRoot);
    const projectRoot = resolve(options.repositoryRoot ?? dirname(requestedOutputRoot));
    this.outputRoot = safeOutputRoot(options.outputRoot, projectRoot);
    this.repositoryRoot = projectRoot;
    this.durableGit = options.durableGit ?? new GitCliDurableGit(projectRoot);
    this.migrationHook = options.migrationHook ?? (() => undefined);
    this.inputsRoot = join(projectRoot, "inputs");
    this.durableRoot = join(projectRoot, "durable");
    this.publicEditionRoot = join(this.outputRoot, this.editionKey);
    this.internalEditionRoot = join(projectRoot, ".magazine", this.editionKey);
  }

  async allocate(
    input: RunSpec | ((scratch: EditionRunScratch) => Promise<RunSpec>),
    options: EditionRunAllocationOptions = {},
  ): Promise<OpenEditionRun> {
    const allocationKey = options.idempotencyKey === undefined
      ? undefined
      : safeAllocationKey(options.idempotencyKey);
    const creatingRoot = join(this.internalEditionRoot, ".creating");
    await mkdir(creatingRoot, { recursive: true, mode: 0o700 });
    if (allocationKey === undefined) {
      const stagingDirectory = join(creatingRoot, `run-${randomUUID()}`);
      return this.allocateStaged(input, allocationKey, stagingDirectory);
    }
    const existing = await this.findAllocation(allocationKey);
    if (existing !== undefined) return this.open(existing.id);
    const lock = await this.acquireAllocationLock(allocationKey, creatingRoot);
    if ("existing" in lock) return this.open(lock.existing.id);
    try {
      const raced = await this.findAllocation(allocationKey);
      if (raced !== undefined) return this.open(raced.id);
      const stagingDirectory = join(lock.path, "staging");
      return await this.allocateStaged(input, allocationKey, stagingDirectory);
    } finally {
      await rm(lock.path, { recursive: true, force: true });
    }
  }

  private async allocateStaged(
    input: RunSpec | ((scratch: EditionRunScratch) => Promise<RunSpec>),
    allocationKey: string | undefined,
    stagingDirectory: string,
  ): Promise<OpenEditionRun> {
    await mkdir(stagingDirectory, { mode: 0o700 });
    let engine: SqliteRunEngine | undefined = this.openEngine(stagingDirectory);
    let finalized = false;
    try {
      const bootstrapScratch = {
        root: join(stagingDirectory, "work", "bootstrap"),
        stagedDirectory: join(stagingDirectory, "work", "bootstrap", "staged"),
        rendererWorkDirectory: join(
          stagingDirectory,
          "work",
          "bootstrap",
          "renderer-work",
        ),
      };
      let spec: RunSpec;
      if (typeof input === "function") {
        await Promise.all([
          mkdir(bootstrapScratch.stagedDirectory, { recursive: true, mode: 0o700 }),
          mkdir(bootstrapScratch.rendererWorkDirectory, { recursive: true, mode: 0o700 }),
        ]);
        spec = await input(bootstrapScratch);
      } else {
        spec = input;
      }
      if (allocationKey !== undefined) {
        spec = {
          ...spec,
          metadata: {
            ...(spec.metadata ?? {}),
            editionRunAllocationKey: allocationKey,
          },
        };
      }
      const started = await engine.start(spec);
      const view = await engine.inspect(started.runId);
      await rm(join(stagingDirectory, "work"), { recursive: true, force: true });
      const paths = this.pathsFor(view);
      if (await exists(paths.internalDirectory)) {
        throw new RunEngineError(
          "RUN_LAYOUT_EXISTS",
          `Internal run directory ${paths.internalDirectory} already exists`,
        );
      }
      engine.close();
      engine = undefined;
      await rename(stagingDirectory, paths.internalDirectory);
      finalized = true;
      const reopened = this.openEngine(paths.internalDirectory);
      try {
        const persisted = await reopened.inspect(started.runId);
        if (editionRunName(persisted) !== paths.runName) {
          throw new RunEngineError(
            "RUN_LAYOUT_MISMATCH",
            `Run ${started.runId} does not match internal directory ${paths.runName}`,
          );
        }
      } catch (error) {
        reopened.close();
        throw error;
      }
      return openedRun(started.runId, paths, reopened);
    } catch (error) {
      engine?.close();
      if (!finalized) {
        await rm(stagingDirectory, { recursive: true, force: true });
      }
      throw error;
    }
  }

  async open(runId: RunId): Promise<OpenEditionRun> {
    safeRunId(runId);
    let entries: readonly string[];
    try {
      entries = await readdir(this.internalEditionRoot);
    } catch (error) {
      throw new RunEngineError(
        "RUN_LAYOUT_NOT_FOUND",
        `No internal workspace exists for edition ${this.editionKey}`,
        { cause: error },
      );
    }
    const suffix = `--${runId}`;
    const candidates = entries.filter((entry) => entry.endsWith(suffix));
    if (candidates.length !== 1) {
      throw new RunEngineError(
        candidates.length === 0 ? "RUN_LAYOUT_NOT_FOUND" : "RUN_LAYOUT_AMBIGUOUS",
        `Expected one internal workspace for ${runId}, found ${candidates.length}`,
      );
    }
    const runName = candidates[0];
    if (runName === undefined) {
      throw new RunEngineError("RUN_LAYOUT_NOT_FOUND", `No internal workspace exists for ${runId}`);
    }
    const internalDirectory = join(this.internalEditionRoot, runName);
    const engine = this.openEngine(internalDirectory);
    try {
      const view = await engine.inspect(runId);
      const expectedName = editionRunName(view);
      if (expectedName !== runName) {
        throw new RunEngineError(
          "RUN_LAYOUT_MISMATCH",
          `Run ${runId} belongs in ${expectedName}, not ${runName}`,
        );
      }
      return openedRun(runId, this.pathsFor(view), engine);
    } catch (error) {
      engine.close();
      throw error;
    }
  }

  /** Lists canonical run identities while verifying each directory pairing. */
  async list(): Promise<readonly RunIdentityView[]> {
    let entries: readonly string[];
    try {
      entries = await readdir(this.internalEditionRoot);
    } catch {
      return [];
    }
    const identities: RunIdentityView[] = [];
    for (const entry of entries.filter((candidate) => !candidate.startsWith(".")).sort()) {
      const directory = join(this.internalEditionRoot, entry);
      if (!await isDirectory(directory) || !await isRegularFile(join(directory, "run.sqlite"))) {
        continue;
      }
      const engine = this.openEngine(directory);
      try {
        const runs = await engine.listRuns();
        if (runs.length !== 1) {
          throw new RunEngineError(
            "RUN_LAYOUT_MISMATCH",
            `Canonical directory ${directory} contains ${runs.length} runs`,
          );
        }
        const identity = runs[0]!;
        if (editionRunName(identity) !== entry) {
          throw new RunEngineError(
            "RUN_LAYOUT_MISMATCH",
            `Canonical directory ${entry} does not match run ${identity.id}`,
          );
        }
        identities.push(identity);
      } finally {
        engine.close();
      }
    }
    return identities.sort((left, right) =>
      left.createdAt.localeCompare(right.createdAt) || left.id.localeCompare(right.id)
    );
  }

  /**
   * Inventories one explicitly supplied legacy engine home without inferring
   * authority from its paths. A match is reported only after the public
   * RunEngine projection and representative immutable payloads are readable.
   * Missing homes are observations, not an instruction to initialize them.
   */
  async discover(sourceDirectory: string, expectedRunId: RunId): Promise<EditionRunDiscovery> {
    safeRunId(expectedRunId);
    const source = resolve(sourceDirectory);
    const databasePath = join(source, "run.sqlite");
    const artifactDirectory = join(source, "artifacts");
    const databasePresent = await isRegularFile(databasePath);
    const artifactDirectoryPresent = await isDirectory(artifactDirectory);
    const artifactFileCount = artifactDirectoryPresent
      ? await countRegularFiles(artifactDirectory)
      : 0;
    const base = {
      schemaVersion: "edition-run-discovery/1" as const,
      sourceDirectory: source,
      databasePath,
      artifactDirectory,
      databasePresent,
      artifactDirectoryPresent,
      artifactFileCount,
      expectedRunId,
    };
    if (!databasePresent) {
      return { ...base, runs: [], identityMatch: false };
    }

    const engine = this.openEngine(source);
    try {
      const runs = await engine.listRuns();
      const identity = runs.find((run) => run.id === expectedRunId);
      if (identity === undefined || !artifactDirectoryPresent) {
        return { ...base, runs, identityMatch: false };
      }
      const view = await engine.inspect(expectedRunId);
      const verifiedArtifactIds = relocationVerificationArtifacts(view);
      for (const artifactId of verifiedArtifactIds) {
        await engine.readArtifact(artifactId);
      }
      return {
        ...base,
        runs,
        identityMatch: true,
        verifiedRunName: editionRunName(view),
        verifiedArtifactIds,
      };
    } finally {
      engine.close();
    }
  }

  /**
   * Migrates an internal edition run through a private clone. The original is
   * left untouched until the cloned database and artifact store reopen and
   * verify together. Only after the atomic directory cutover may normal
   * RunEngine advancement dispatch the newly recorded migration effects.
   */
  async migrate(
    runId: RunId,
    request: Omit<MigrationRequest, "runId">,
  ): Promise<EditionRunMigrationResult> {
    let opened: OpenEditionRun | undefined = await this.open(runId);
    const originalDirectory = opened.internalDirectory;
    let originalView: RunView;
    try {
      originalView = await opened.engine.inspect(runId);
    } catch (error) {
      closeIgnoringErrors(opened);
      throw error;
    }
    const migratingRoot = join(this.internalEditionRoot, ".migrating");
    let operationRoot: string;
    try {
      await mkdir(migratingRoot, { recursive: true, mode: 0o700 });
      operationRoot = await mkdtemp(join(migratingRoot, "migration-"));
    } catch (error) {
      closeIgnoringErrors(opened);
      throw error;
    }
    const candidateDirectory = join(operationRoot, "candidate");
    const rollbackDirectory = join(operationRoot, "rollback");
    let fence: RunMigrationFence;
    try {
      fence = await opened.engine.acquireMigrationFence({
        runId,
        expectedHeadSequence: originalView.headSequence,
        expectedHeadEventId: request.expectedHeadEventId as EventId,
        idempotencyKey: relocationFenceKey(
          "migrate",
          originalDirectory,
          runId,
          request.expectedHeadEventId,
        ),
      });
    } catch (error) {
      closeIgnoringErrors(opened);
      await rm(operationRoot, { recursive: true, force: true });
      throw error;
    }
    let candidate: SqliteRunEngine | undefined;
    let confirmed: SqliteRunEngine | undefined;
    let originalMoved = false;
    let candidateInstalled = false;
    let cutoverFence: RunMigrationFence | undefined;
    let cutoverCommitted = false;
    try {
      await this.migrationHook("migrate.after_fence");
      await verifyExactRun(opened.engine, runId, fence);
      await opened.engine.checkpointMigrationFence(fence);
      opened.close();
      opened = undefined;
      await assertSameMigrationDevice(originalDirectory, migratingRoot);
      const sourceInventory = await inventoryRunHome(originalDirectory);
      await cloneRunHome(originalDirectory, candidateDirectory);
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(originalDirectory),
        "Source run changed while its migration clone was copied",
      );
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(candidateDirectory),
        "Migration clone does not match its fenced source",
      );
      candidate = this.openEngine(candidateDirectory);
      await verifyExactRun(candidate, runId, fence);
      await candidate.checkpointMigrationFence(fence);
      candidate.close();
      candidate = undefined;
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(candidateDirectory),
        "Migration clone changed while it was verified",
      );

      candidate = this.openEngine(candidateDirectory);
      await candidate.releaseMigrationFence(fence);
      const plan = await candidate.migrate({ runId, ...request });
      const migrated = await candidate.inspect(runId);
      await verifyMigratedRun(candidate, migrated);
      const migratedHeadEventId = runHeadEventId(migrated);
      cutoverFence = await candidate.acquireMigrationFence({
        runId,
        expectedHeadSequence: migrated.headSequence,
        expectedHeadEventId: migratedHeadEventId,
        idempotencyKey: relocationFenceKey(
          "migrate",
          candidateDirectory,
          runId,
          migratedHeadEventId,
        ),
      });
      await candidate.checkpointMigrationFence(cutoverFence);
      candidate.close();
      candidate = undefined;

      await rename(originalDirectory, rollbackDirectory);
      originalMoved = true;
      await rename(candidateDirectory, originalDirectory);
      candidateInstalled = true;
      await this.migrationHook("migrate.after_candidate_install");

      confirmed = this.openEngine(originalDirectory);
      await verifyExactRun(confirmed, runId, cutoverFence);
      await confirmed.releaseMigrationFence(cutoverFence);
      cutoverCommitted = true;
      const outcome = await confirmed.advance(runId);
      confirmed.close();
      confirmed = undefined;
      await removeCommittedMigrationWorkspace(operationRoot);
      return { plan, outcome };
    } catch (error) {
      closeIgnoringErrors(opened, candidate, confirmed);
      if (cutoverCommitted) {
        await removeCommittedMigrationWorkspace(operationRoot);
        throw error;
      }
      if (originalMoved) {
        try {
          if (candidateInstalled && await exists(originalDirectory)) {
            await rename(originalDirectory, candidateDirectory);
          }
          if (await exists(rollbackDirectory)) {
            await rename(rollbackDirectory, originalDirectory);
          }
        } catch (rollbackError) {
          throw new RunEngineError(
            "MIGRATION_ROLLBACK_FAILED",
            `Migration of ${runId} could not restore its original run directory`,
            { cause: rollbackError },
          );
        }
      }
      if (await exists(originalDirectory)) {
        await releaseMigrationFenceAt(this.openEngine(originalDirectory), fence);
      }
      await rm(operationRoot, { recursive: true, force: true });
      throw error;
    }
  }

  /**
   * Clone a fenced legacy database and artifact store into private staging,
   * verify every immutable payload, then atomically install the clone while
   * retaining the original as the rollback side of the cutover.
   */
  async relocate(sourceDirectory: string, runId: RunId): Promise<OpenEditionRun> {
    safeRunId(runId);
    const source = resolve(sourceDirectory);
    if (!(await exists(source))) {
      return this.open(runId);
    }
    await requirePlainDirectory(source, "legacy run source");

    let sourceEngine: SqliteRunEngine | undefined = this.openEngine(source);
    let view: RunView;
    try {
      view = await sourceEngine.inspect(runId);
    } catch (error) {
      sourceEngine.close();
      throw error;
    }
    let paths: EditionRunPaths;
    let headEventId: EventId;
    try {
      paths = this.pathsFor(view);
      if (source === paths.internalDirectory) {
        return openedRun(runId, paths, sourceEngine);
      }
      assertDisjointMigrationPaths(source, paths.internalDirectory, this.internalEditionRoot);
      if (await exists(paths.internalDirectory)) {
        throw new RunEngineError(
          "RUN_LAYOUT_EXISTS",
          `Both source ${source} and canonical run directory ${paths.internalDirectory} exist`,
        );
      }
      headEventId = runHeadEventId(view);
    } catch (error) {
      closeIgnoringErrors(sourceEngine);
      throw error;
    }
    const migratingRoot = join(this.internalEditionRoot, ".migrating");
    let operationRoot: string;
    try {
      await mkdir(migratingRoot, { recursive: true, mode: 0o700 });
      operationRoot = await mkdtemp(join(migratingRoot, "relocation-"));
    } catch (error) {
      closeIgnoringErrors(sourceEngine);
      throw error;
    }
    const candidateDirectory = join(operationRoot, "candidate");
    const rollbackDirectory = join(operationRoot, "rollback");
    let fence: RunMigrationFence;
    try {
      fence = await sourceEngine.acquireMigrationFence({
        runId,
        expectedHeadSequence: view.headSequence,
        expectedHeadEventId: headEventId,
        idempotencyKey: relocationFenceKey("relocate", source, runId, headEventId),
      });
    } catch (error) {
      closeIgnoringErrors(sourceEngine);
      await rm(operationRoot, { recursive: true, force: true });
      throw error;
    }
    let sourceMoved = false;
    let candidateInstalled = false;
    let fenceReleased = false;
    let candidate: SqliteRunEngine | undefined;
    let reopened: SqliteRunEngine | undefined;
    try {
      await this.migrationHook("relocate.after_fence");
      await verifyExactRun(sourceEngine, runId, fence);
      await sourceEngine.checkpointMigrationFence(fence);
      sourceEngine.close();
      sourceEngine = undefined;
      await assertSameMigrationDevice(source, migratingRoot);
      const sourceInventory = await inventoryRunHome(source);
      await cloneRunHome(source, candidateDirectory);
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(source),
        "Source run changed while its relocation clone was copied",
      );
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(candidateDirectory),
        "Relocation clone does not match its fenced source",
      );
      candidate = this.openEngine(candidateDirectory);
      await verifyExactRun(candidate, runId, fence);
      await candidate.checkpointMigrationFence(fence);
      candidate.close();
      candidate = undefined;
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(candidateDirectory),
        "Relocation clone changed while it was verified",
      );

      await rename(source, rollbackDirectory);
      sourceMoved = true;
      await rename(candidateDirectory, paths.internalDirectory);
      candidateInstalled = true;
      await this.migrationHook("relocate.after_candidate_install");
      reopened = this.openEngine(paths.internalDirectory);
      const persisted = await verifyExactRun(reopened, runId, fence);
      if (editionRunName(persisted) !== paths.runName) {
        throw new RunEngineError(
          "RUN_LAYOUT_MISMATCH",
          `Relocated run ${runId} does not match ${paths.runName}`,
        );
      }
      assertSameRunHomeInventory(
        sourceInventory,
        await inventoryRunHome(paths.internalDirectory),
        "Installed relocation changed before final validation",
      );
      await reopened.releaseMigrationFence(fence);
      fenceReleased = true;
      await removeCommittedMigrationWorkspace(operationRoot);
      return openedRun(runId, paths, reopened);
    } catch (error) {
      closeIgnoringErrors(reopened, candidate, sourceEngine);
      try {
        if (candidateInstalled && await exists(paths.internalDirectory)) {
          await rename(paths.internalDirectory, candidateDirectory);
        }
        if (sourceMoved && await exists(rollbackDirectory)) {
          await rename(rollbackDirectory, source);
        }
      } catch (rollbackError) {
        throw new RunEngineError(
          "RUN_LAYOUT_ROLLBACK_FAILED",
          `Relocation of ${runId} failed and could not be rolled back to ${source}`,
          { cause: rollbackError },
        );
      }
      if (!fenceReleased && await exists(source)) {
        await releaseMigrationFenceAt(this.openEngine(source), fence);
        fenceReleased = true;
      }
      await rm(operationRoot, { recursive: true, force: true });
      throw error;
    }
  }

  async withScratch<Result>(
    runId: RunId,
    operation: (scratch: EditionRunScratch) => Promise<Result>,
  ): Promise<Result> {
    const opened = await this.open(runId);
    const workDirectory = opened.workDirectory;
    opened.close();
    await mkdir(workDirectory, { recursive: true, mode: 0o700 });
    const root = await mkdtemp(join(workDirectory, "operation-"));
    const scratch = {
      root,
      stagedDirectory: join(root, "staged"),
      rendererWorkDirectory: join(root, "renderer-work"),
    };
    await Promise.all([
      mkdir(scratch.stagedDirectory, { mode: 0o700 }),
      mkdir(scratch.rendererWorkDirectory, { mode: 0o700 }),
    ]);
    try {
      return await operation(scratch);
    } finally {
      await rm(root, { recursive: true, force: true });
      try {
        await rmdir(workDirectory);
      } catch {
        // Concurrent operations keep the shared work root until they finish.
      }
    }
  }

  /**
   * Project the exact current render for independent review. This is a
   * read-only workflow operation: it neither claims nor answers the active
   * visual-review offer and confers no approval or release authority.
   */
  async projectReview(
    runId: RunId,
    options: EditionRunReviewProjectionOptions,
  ): Promise<EditionRunReviewProjectionResult> {
    if (!Number.isSafeInteger(options.expectedHeadSequence) || options.expectedHeadSequence < 0) {
      throw new RunEngineError(
        "RENDER_REVIEW_FENCE",
        "Expected head sequence must be a non-negative safe integer",
      );
    }
    const independentCriticNote = options.independentCritic.note.trim();
    if (!independentCriticNote) {
      throw new RunEngineError(
        "RENDER_REVIEW_NOTE",
        "Independent critic note must be non-empty",
      );
    }
    if (!["not_run", "pass"].includes(options.independentCritic.result)) {
      throw new RunEngineError(
        "RENDER_REVIEW_CRITIC",
        "Independent critic result must be pass or not_run",
      );
    }
    const opened = await this.open(runId);
    try {
      const view = await opened.engine.inspect(runId);
      if (view.headSequence !== options.expectedHeadSequence) {
        throw staleReviewProjection(
          runId,
          `Expected head ${options.expectedHeadSequence}, current head is ${view.headSequence}`,
        );
      }
      const review = currentVisualReview(view, options.expectedOfferId);
      const renderArtifacts = artifactsById(view, review.renderArtifactIds);
      const composition = await currentCompositionRevision(
        opened.engine,
        view,
        review.actor,
        review.renderArtifactIds,
      );
      await resolveCompositionRevision(
        this.repositoryRoot,
        {
          revisionRef: {
            kind: "composition",
            editionId: composition.editionId,
            compositionId: composition.compositionId,
            revisionId: composition.revisionId as import("./contracts/index.ts").RevisionId,
          },
          manifestDigest: composition.manifestDigest,
          gitCommitOid: composition.gitCommitOid,
          gitBlobOids: composition.gitBlobOids,
        },
        this.durableGit,
      );
      const { files, pageCounts } = await editionExportFiles(opened.engine, renderArtifacts);
      const topology = await exportStateMachineTopologyBundle();
      const renderArtifactSetDigest = digestArtifactIdSequence(review.renderArtifactIds);
      const projected = await materializeRenderProjection(opened.engine, {
        destinationDirectory: opened.publicDirectory,
        files,
        auxiliaryFiles: topology.files.map((file) => ({
          destination: `state-machine/${file.path}`,
          mediaType: file.mediaType,
          bytes: file.bytes,
        })),
        manifestFile: "export.json",
        manifest: {
          schemaVersion: "edition-run-review-projection/1",
          status: "awaiting_visual_review",
          authority: "non_authoritative_review_projection",
          editionKey: this.editionKey,
          editionId: composition.editionId,
          runId,
          runName: opened.runName,
          createdAt: view.createdAt,
          headSequence: view.headSequence,
          offerId: review.offerId,
          renderActorId: review.actor.id,
          compositionRevision: {
            artifactId: composition.artifactId,
            editionId: composition.editionId,
            compositionId: composition.compositionId,
            revisionId: composition.revisionId,
            manifestDigest: composition.manifestDigest,
            gitCommitOid: composition.gitCommitOid,
            gitBlobOids: composition.gitBlobOids,
          },
          renderArtifactIds: review.renderArtifactIds,
          renderArtifactSetDigest,
          pageCounts,
          independentCritic: {
            result: options.independentCritic.result,
            note: independentCriticNote,
          },
          stateMachineTopology: {
            schemaVersion: "state-machine-topology-projection/1",
            source: "live_xstate_configs_and_runtime_orchestration_declarations",
            directory: "state-machine",
            fileCount: topology.files.length,
          },
          visualDecisionArtifactId: null,
          released: false,
          pressReady: false,
        },
        overwrite: true,
        verifyPdfPageCounts: true,
        verifyBeforePublish: async () => {
          const current = await opened.engine.inspect(runId);
          if (current.headSequence !== options.expectedHeadSequence) {
            throw staleReviewProjection(
              runId,
              `Run changed to head ${current.headSequence} while its review projection was staged`,
            );
          }
          const currentReview = currentVisualReview(current, options.expectedOfferId);
          if (
            currentReview.actor.id !== review.actor.id ||
            !sameSequence(currentReview.renderArtifactIds, review.renderArtifactIds)
          ) {
            throw staleReviewProjection(
              runId,
              "Active visual-review actor or render artifact sequence changed while staging",
            );
          }
        },
      });
      return {
        runId,
        runName: opened.runName,
        headSequence: view.headSequence,
        offerId: review.offerId,
        publicDirectory: opened.publicDirectory,
        exportManifestPath: projected.manifestPath,
        physicalFileCount: projected.physicalFileCount,
        compositionRevision: composition,
        renderArtifactIds: review.renderArtifactIds,
        renderArtifactSetDigest,
      };
    } finally {
      opened.close();
    }
  }

  /** Publish the current human-approved render and its committed composition. */
  async publish(
    runId: RunId,
    options: EditionRunPublishOptions = {},
  ): Promise<EditionRunPublishResult> {
    const opened = await this.open(runId);
    try {
      const view = await opened.engine.inspect(runId);
      const approval = currentVisualApproval(view, options.expectedVisualDecisionId);
      const approvedArtifacts = artifactsById(view, approval.renderArtifactIds);
      const composition = await currentCompositionRevision(
        opened.engine,
        view,
        approval.actor,
        approval.renderArtifactIds,
      );
      await resolveCompositionRevision(
        this.repositoryRoot,
        {
          revisionRef: {
            kind: "composition",
            editionId: composition.editionId,
            compositionId: composition.compositionId,
            revisionId: composition.revisionId as import("./contracts/index.ts").RevisionId,
          },
          manifestDigest: composition.manifestDigest,
          gitCommitOid: composition.gitCommitOid,
          gitBlobOids: composition.gitBlobOids,
        },
        this.durableGit,
      );
      const { files, pageCounts } = await editionExportFiles(
        opened.engine,
        approvedArtifacts,
      );
      const exported = await exportApprovedRender(opened.engine, {
        runId,
        approvedDecisionArtifactId: approval.decision.artifactId,
        destinationDirectory: opened.publicDirectory,
        files,
        manifestFile: "export.json",
        manifest: {
          schemaVersion: "edition-run-export/1",
          editionKey: this.editionKey,
          editionId: composition.editionId,
          run: {
            runId,
            runName: opened.runName,
            createdAt: view.createdAt,
          },
          compositionRevision: {
            artifactId: composition.artifactId,
            editionId: composition.editionId,
            compositionId: composition.compositionId,
            revisionId: composition.revisionId,
            manifestDigest: composition.manifestDigest,
            gitCommitOid: composition.gitCommitOid,
            gitBlobOids: composition.gitBlobOids,
          },
          visualApproval: {
            decisionId: approval.decision.id,
            decisionArtifactId: approval.decision.artifactId,
            offerId: approval.decision.offerId,
          },
          pageCounts,
        },
        expectedHeadSequence: view.headSequence,
        overwrite: true,
      });
      return {
        runId,
        runName: opened.runName,
        publicDirectory: opened.publicDirectory,
        exportManifestPath: exported.manifestPath,
        compositionRevision: composition,
        visualDecisionId: approval.decision.id,
      };
    } finally {
      opened.close();
    }
  }

  pathsFor(run: Pick<RunView, "createdAt" | "id">): EditionRunPaths {
    const runName = editionRunName(run);
    const internalDirectory = join(this.internalEditionRoot, runName);
    return {
      runName,
      internalDirectory,
      publicDirectory: join(this.publicEditionRoot, runName),
      databasePath: join(internalDirectory, "run.sqlite"),
      artifactDirectory: join(internalDirectory, "artifacts"),
      workDirectory: join(internalDirectory, "work"),
    };
  }

  private openEngine(directory: string): SqliteRunEngine {
    return new SqliteRunEngine({
      databasePath: join(directory, "run.sqlite"),
      artifactDirectory: join(directory, "artifacts"),
    });
  }

  private async acquireAllocationLock(
    allocationKey: string,
    creatingRoot: string,
  ): Promise<
    | { readonly path: string; readonly token: string }
    | { readonly existing: RunIdentityView }
  > {
    const lockPath = join(creatingRoot, allocationLockName(allocationKey));
    for (let attempt = 0; attempt < 1_000; attempt += 1) {
      const existing = await this.findAllocation(allocationKey);
      if (existing !== undefined) return { existing };
      const token = randomUUID();
      try {
        await mkdir(lockPath, { mode: 0o700 });
        try {
          await writeFile(
            join(lockPath, "owner.json"),
            `${JSON.stringify({
              schemaVersion: "edition-run-allocation-lock/1",
              allocationKey,
              pid: process.pid,
              token,
            })}\n`,
            { encoding: "utf8", flag: "wx", mode: 0o600 },
          );
        } catch (error) {
          await rm(lockPath, { recursive: true, force: true });
          throw error;
        }
        return { path: lockPath, token };
      } catch (error) {
        if (!hasErrorCode(error, "EEXIST")) throw error;
      }
      if (await recoverAbandonedAllocationLock(lockPath, allocationKey)) continue;
      await delay(10);
    }
    throw new RunEngineError(
      "RUN_LAYOUT_ALLOCATION_BUSY",
      `Allocation ${allocationKey} is still owned by another live creator`,
    );
  }

  private async findAllocation(allocationKey: string): Promise<RunIdentityView | undefined> {
    const matches = (await this.list()).filter(
      (run) => run.metadata.editionRunAllocationKey === allocationKey,
    );
    if (matches.length > 1) {
      throw new RunEngineError(
        "RUN_LAYOUT_AMBIGUOUS",
        `Allocation ${allocationKey} belongs to ${matches.length} canonical runs`,
      );
    }
    return matches[0];
  }
}

function safeOutputRoot(value: string, repositoryRoot: string): string {
  if (value.replaceAll("\\", "/").split("/").some((part) => part === "." || part === "..")) {
    throw new RunEngineError(
      "RUN_LAYOUT_OUTPUT_TRAVERSAL",
      "Output root must not contain traversal components",
    );
  }
  const outputRoot = resolve(value);
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(basename(outputRoot))) {
    throw new RunEngineError(
      "RUN_LAYOUT_OUTPUT_ROOT",
      "Output root must end in a lowercase portable ASCII directory name",
    );
  }
  const protectedRoots = [
    join(repositoryRoot, ".magazine"),
    join(repositoryRoot, "durable"),
    join(repositoryRoot, "inputs"),
  ];
  const outputKey = portablePathKey(outputRoot);
  if (outputKey === portablePathKey(repositoryRoot) || protectedRoots.some((protectedRoot) => {
    const protectedKey = portablePathKey(protectedRoot);
    return outputKey === protectedKey || outputKey.startsWith(`${protectedKey}/`);
  })) {
    throw new RunEngineError(
      "RUN_LAYOUT_OUTPUT_COLLISION",
      "Output root must not collide with the repository or a private immutable root",
    );
  }
  return outputRoot;
}

function portablePathKey(path: string): string {
  return resolve(path).replaceAll("\\", "/").normalize("NFC").toLocaleLowerCase("en-US");
}

export function editionRunName(run: Pick<RunView, "createdAt" | "id">): string {
  const runId = safeRunId(run.id);
  const parsed = new Date(run.createdAt);
  if (!Number.isFinite(parsed.valueOf()) || parsed.toISOString() !== run.createdAt) {
    throw new RunEngineError(
      "RUN_LAYOUT_CREATED_AT",
      `Run ${runId} has non-canonical UTC createdAt ${JSON.stringify(run.createdAt)}`,
    );
  }
  return `${run.createdAt.replaceAll(":", "-")}--${runId}`;
}

function openedRun(
  runId: RunId,
  paths: EditionRunPaths,
  engine: SqliteRunEngine,
): OpenEditionRun {
  return {
    runId,
    ...paths,
    engine,
    close: () => engine.close(),
  };
}

function safeEditionKey(value: string): string {
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(value)) {
    throw new RunEngineError(
      "RUN_LAYOUT_EDITION_KEY",
      "Edition key must use lowercase portable ASCII letters, digits, underscores, or hyphens",
    );
  }
  return value;
}

function safeRunId(value: RunId): RunId {
  if (!/^run_[a-z0-9][a-z0-9_-]*$/.test(value)) {
    throw new RunEngineError(
      "RUN_LAYOUT_RUN_ID",
      "Run ID is not safe for a portable run directory name",
    );
  }
  return value;
}

function safeAllocationKey(value: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value)) {
    throw new RunEngineError(
      "RUN_LAYOUT_ALLOCATION_KEY",
      "Allocation key must be a portable ASCII component",
    );
  }
  return value;
}

function allocationLockName(allocationKey: string): string {
  const key = createHash("sha256").update(allocationKey, "utf8").digest("hex");
  return `allocation-${key}.lock`;
}

async function recoverAbandonedAllocationLock(
  lockPath: string,
  allocationKey: string,
): Promise<boolean> {
  let bytes: string;
  try {
    bytes = await readFile(join(lockPath, "owner.json"), "utf8");
  } catch (error) {
    if (hasErrorCode(error, "ENOENT")) return false;
    throw error;
  }
  let owner: unknown;
  try {
    owner = JSON.parse(bytes);
  } catch (error) {
    throw new RunEngineError(
      "RUN_LAYOUT_ALLOCATION_LOCK_INVALID",
      `Allocation ${allocationKey} has an unreadable lock owner`,
      { cause: error },
    );
  }
  if (
    owner === null ||
    typeof owner !== "object" ||
    Array.isArray(owner) ||
    (owner as Record<string, unknown>).schemaVersion !== "edition-run-allocation-lock/1" ||
    (owner as Record<string, unknown>).allocationKey !== allocationKey ||
    !Number.isSafeInteger((owner as Record<string, unknown>).pid) ||
    typeof (owner as Record<string, unknown>).token !== "string"
  ) {
    throw new RunEngineError(
      "RUN_LAYOUT_ALLOCATION_LOCK_INVALID",
      `Allocation ${allocationKey} has an invalid lock owner`,
    );
  }
  if (processIsAlive((owner as { readonly pid: number }).pid)) return false;
  const recovery = `${lockPath}.recovering-${randomUUID()}`;
  try {
    await rename(lockPath, recovery);
  } catch (error) {
    if (hasErrorCode(error, "ENOENT")) return true;
    throw error;
  }
  await rm(recovery, { recursive: true, force: true });
  return true;
}

function processIsAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return !hasErrorCode(error, "ESRCH");
  }
}

function hasErrorCode(error: unknown, code: string): boolean {
  return typeof error === "object" && error !== null && "code" in error &&
    (error as { readonly code?: unknown }).code === code;
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function isRegularFile(path: string): Promise<boolean> {
  try {
    const info = await lstat(path);
    return info.isFile() && !info.isSymbolicLink();
  } catch {
    return false;
  }
}

async function isDirectory(path: string): Promise<boolean> {
  try {
    const info = await lstat(path);
    return info.isDirectory() && !info.isSymbolicLink();
  } catch {
    return false;
  }
}

async function countRegularFiles(root: string): Promise<number> {
  let count = 0;
  const visit = async (directory: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        await visit(join(directory, entry.name));
      } else if (entry.isFile()) {
        count += 1;
      }
    }
  };
  await visit(root);
  return count;
}

function currentVisualReview(
  view: RunView,
  expectedOfferId: WorkOfferId,
): CurrentVisualReview {
  if (view.status !== "waiting") {
    throw new RunEngineError(
      "RENDER_REVIEW_STATE",
      `Run ${view.id} is ${view.status}, not waiting on its visual-review offer`,
    );
  }
  const active = view.offers.filter((offer) =>
    offer.role === "visual_review" && offer.status === "offered"
  );
  if (active.length !== 1 || active[0]?.id !== expectedOfferId) {
    throw staleReviewProjection(
      view.id,
      `Expected exactly offered visual-review offer ${expectedOfferId}, found ${active.length}`,
    );
  }
  const offer = active[0]!;
  if (
    offer.state !== "awaiting_visual_review" ||
    offer.slot !== "visual_review" ||
    offer.contractVersion !== "visual-review/1" ||
    offer.activeAttemptId != null ||
    offer.requirements?.authority !== "human" ||
    offer.requirements.minimumAssurance !== "local_bearer" ||
    offer.requirements.capabilities.length !== 0
  ) {
    throw new RunEngineError(
      "RENDER_REVIEW_STATE",
      `Offer ${offer.id} is not the exact offered human visual-review contract`,
    );
  }
  if (view.decisions.some((decision) => decision.offerId === offer.id)) {
    throw new RunEngineError(
      "RENDER_REVIEW_STATE",
      `Offer ${offer.id} already has a decision and cannot be projected as pending`,
    );
  }
  const actors = view.actors.filter((actor) => actor.id === offer.actorId);
  if (actors.length !== 1) {
    throw new RunEngineError(
      "RENDER_REVIEW_AMBIGUOUS",
      `Offer ${offer.id} must identify exactly one render actor`,
    );
  }
  const actor = actors[0]!;
  const renderArtifactIds = artifactIdArray(actor.context.renderArtifacts);
  if (
    actor.machine !== "render" ||
    actor.state !== "awaiting_visual_review" ||
    actor.status !== "active" ||
    (actor.context.visualDecisionArtifact !== undefined &&
      actor.context.visualDecisionArtifact !== null) ||
    renderArtifactIds === undefined ||
    renderArtifactIds.length === 0 ||
    new Set(renderArtifactIds).size !== renderArtifactIds.length
  ) {
    throw new RunEngineError(
      "RENDER_REVIEW_STATE",
      `Offer ${offer.id} is not bound to one active awaiting_visual_review render artifact set`,
    );
  }
  const first = offer.inputArtifacts.indexOf(renderArtifactIds[0]!);
  if (
    offer.inputArtifacts.filter((artifactId) => artifactId === offer.taskArtifactId).length !== 1 ||
    first < 0 ||
    !sameSequence(
      offer.inputArtifacts.slice(first, first + renderArtifactIds.length),
      renderArtifactIds,
    ) ||
    renderArtifactIds.some(
      (artifactId) => offer.inputArtifacts.filter((candidate) => candidate === artifactId).length !== 1,
    )
  ) {
    throw new RunEngineError(
      "RENDER_REVIEW_BINDING",
      `Offer ${offer.id} does not name the render actor's exact current artifact sequence`,
    );
  }
  const request = view.artifacts.find((artifact) => artifact.id === offer.taskArtifactId);
  if (
    request?.kind !== "human_decision_request" ||
    request.schemaVersion !== "human-decision-request/3" ||
    request.origin !== "machine"
  ) {
    throw new RunEngineError(
      "RENDER_REVIEW_BINDING",
      `Offer ${offer.id} lacks its exact machine visual-review request artifact`,
    );
  }
  return { actor, offerId: offer.id, renderArtifactIds };
}

function staleReviewProjection(runId: RunId, detail: string): RunEngineError {
  return new RunEngineError(
    "RENDER_REVIEW_STALE",
    `Review projection for ${runId} is stale: ${detail}`,
  );
}

function digestArtifactIdSequence(artifactIds: readonly ArtifactId[]): string {
  return `sha256:${createHash("sha256")
    .update("render-artifact-id-sequence/1\n")
    .update(JSON.stringify(artifactIds))
    .digest("hex")}`;
}

function currentVisualApproval(
  view: RunView,
  expectedDecisionId: DecisionId | undefined,
): CurrentVisualApproval {
  const actors = view.actors.filter((actor) =>
    actor.machine === "render" &&
    typeof actor.context.visualDecisionArtifact === "string" &&
    artifactIdArray(actor.context.renderArtifacts) !== undefined
  );
  if (actors.length !== 1) {
    throw new RunEngineError(
      "RENDER_NOT_APPROVED",
      `Run ${view.id} must have exactly one current render actor with visual approval`,
    );
  }
  const actor = actors[0]!;
  const decisionArtifactId = actor.context.visualDecisionArtifact as ArtifactId;
  const renderArtifactIds = artifactIdArray(actor.context.renderArtifacts)!;
  const decision = view.decisions.find((candidate) =>
    candidate.artifactId === decisionArtifactId
  );
  if (
    decision === undefined ||
    decision.artifactId === undefined ||
    decision.offerId === undefined ||
    decision.choice !== "approved" ||
    decision.authority !== "human"
  ) {
    throw new RunEngineError(
      "RENDER_NOT_APPROVED",
      `Run ${view.id} has no current human-approved visual decision`,
    );
  }
  if (expectedDecisionId !== undefined && decision.id !== expectedDecisionId) {
    throw new RunEngineError(
      "RENDER_EXPORT_STALE",
      `Expected visual decision ${expectedDecisionId}, but current decision is ${decision.id}`,
    );
  }
  const offer = view.offers.find((candidate) => candidate.id === decision.offerId);
  if (offer?.role !== "visual_review") {
    throw new RunEngineError(
      "RENDER_NOT_APPROVED",
      `Decision ${decision.id} is not bound to a visual-review offer`,
    );
  }
  const expected = artifactIdArray(decision.details.expectedRenderArtifactIds);
  const submitted = artifactIdArray(decision.details.submittedRenderArtifactIds);
  if (
    decision.details.accepted !== true ||
    expected === undefined ||
    submitted === undefined ||
    !sameSequence(expected, submitted) ||
    !sameSequence(expected, renderArtifactIds)
  ) {
    throw new RunEngineError(
      "RENDER_APPROVAL_INVALID",
      `Decision ${decision.id} does not approve the render actor's exact current artifact sequence`,
    );
  }
  return {
    actor,
    decision: decision as CurrentVisualApproval["decision"],
    renderArtifactIds,
  };
}

function artifactsById(
  view: RunView,
  artifactIds: readonly ArtifactId[],
): ReadonlyMap<ArtifactId, ArtifactView> {
  const available = new Map(view.artifacts.map((artifact) => [artifact.id, artifact]));
  const selected = new Map<ArtifactId, ArtifactView>();
  for (const artifactId of artifactIds) {
    const artifact = available.get(artifactId);
    if (artifact === undefined) {
      throw new RunEngineError(
        "RENDER_EXPORT_MISSING",
        `Approved artifact ${artifactId} is absent from run ${view.id}`,
      );
    }
    selected.set(artifactId, artifact);
  }
  return selected;
}

async function currentCompositionRevision(
  engine: Pick<SqliteRunEngine, "readArtifact">,
  view: RunView,
  renderActor: ActorView,
  renderArtifactIds: readonly ArtifactId[],
): Promise<CompositionRevisionBinding> {
  const candidates: Array<CompositionRevisionBinding & {
    readonly acceptedArtifactIds: readonly ArtifactId[];
  }> = [];
  for (const artifact of view.artifacts.filter((candidate) =>
    candidate.kind === "durable_revision_bound" &&
    candidate.schemaVersion === "durable-revision-bound/1" &&
    candidate.mediaType === "application/json"
  )) {
    const payload = jsonMapping(
      await engine.readArtifact(artifact.id).then((loaded) => loaded.bytes),
      `durable composition binding ${artifact.id}`,
    );
    const logicalItem = mapping(payload.logicalItem);
    const revisionRef = mapping(payload.revisionRef);
    if (logicalItem?.kind !== "composition" || revisionRef?.kind !== "composition") {
      continue;
    }
    const editionId = commonString(logicalItem.editionId, revisionRef.editionId);
    const compositionId = commonString(logicalItem.compositionId, revisionRef.compositionId);
    const revisionId = commonString(payload.revisionId, revisionRef.revisionId);
    const manifestDigest = stringValue(payload.manifestDigest);
    const gitCommitOid = stringValue(payload.gitCommitOid);
    const gitBlobOids = stringRecord(payload.gitBlobOids);
    const acceptedArtifactIds = artifactIdArray(payload.acceptedArtifactIds);
    if (
      editionId === undefined ||
      compositionId === undefined ||
      revisionId === undefined ||
      manifestDigest === undefined ||
      !/^sha256:[0-9a-f]{64}$/.test(manifestDigest) ||
      gitCommitOid === undefined ||
      !/^[0-9a-f]{40,64}$/.test(gitCommitOid) ||
      gitBlobOids === undefined ||
      Object.keys(gitBlobOids).length === 0 ||
      acceptedArtifactIds === undefined
    ) {
      throw new RunEngineError(
        "COMPOSITION_REVISION_INVALID",
        `Artifact ${artifact.id} is not a complete committed CompositionRevision binding`,
      );
    }
    candidates.push({
      artifactId: artifact.id,
      editionId,
      compositionId,
      revisionId,
      manifestDigest,
      gitCommitOid,
      gitBlobOids,
      acceptedArtifactIds,
    });
  }
  for (const artifact of view.artifacts.filter((candidate) =>
    candidate.kind === "composition_revision_bound" &&
    candidate.schemaVersion === "composition-bootstrap-bound/1" &&
    candidate.mediaType === "application/json" &&
    candidate.origin === "machine"
  )) {
    const payload = jsonMapping(
      await engine.readArtifact(artifact.id).then((loaded) => loaded.bytes),
      `bootstrap composition binding ${artifact.id}`,
    );
    const bootstrapRevision = mapping(payload.bootstrapRevision);
    const compositionRevision = mapping(payload.compositionRevision);
    const revisionRef = mapping(compositionRevision?.revisionRef);
    const editionId = commonString(bootstrapRevision?.editionId, revisionRef?.editionId);
    const compositionId = stringValue(revisionRef?.compositionId);
    const revisionId = stringValue(revisionRef?.revisionId);
    const manifestDigest = stringValue(compositionRevision?.manifestDigest);
    const gitCommitOid = stringValue(compositionRevision?.gitCommitOid);
    const gitBlobOids = stringRecord(compositionRevision?.gitBlobOids);
    if (
      bootstrapRevision?.kind !== "run_bootstrap" ||
      revisionRef?.kind !== "composition" ||
      payload.imageGenerationAllowed !== false ||
      editionId === undefined ||
      compositionId === undefined ||
      revisionId === undefined ||
      manifestDigest === undefined ||
      !/^sha256:[0-9a-f]{64}$/.test(manifestDigest) ||
      gitCommitOid === undefined ||
      !/^[0-9a-f]{40,64}$/.test(gitCommitOid) ||
      gitBlobOids === undefined ||
      Object.keys(gitBlobOids).length === 0
    ) {
      throw new RunEngineError(
        "COMPOSITION_REVISION_INVALID",
        `Artifact ${artifact.id} is not a complete bootstrap CompositionRevision binding`,
      );
    }
    candidates.push({
      artifactId: artifact.id,
      editionId,
      compositionId,
      revisionId,
      manifestDigest,
      gitCommitOid,
      gitBlobOids,
      acceptedArtifactIds: [],
    });
  }

  const referenced = artifactIdsInJson([renderActor.input, renderActor.context]);
  const ancestors = artifactAncestors(view.artifacts, renderArtifactIds);
  const current = candidates.filter((candidate) =>
    referenced.has(candidate.artifactId) ||
    ancestors.has(candidate.artifactId) ||
    candidate.acceptedArtifactIds.some((artifactId) => ancestors.has(artifactId))
  );
  if (current.length !== 1) {
    throw new RunEngineError(
      "COMPOSITION_REVISION_NOT_BOUND",
      `Current render must reference exactly one committed CompositionRevision, found ${current.length}`,
    );
  }
  const selected = current[0]!;
  return {
    artifactId: selected.artifactId,
    editionId: selected.editionId,
    compositionId: selected.compositionId,
    revisionId: selected.revisionId,
    manifestDigest: selected.manifestDigest,
    gitCommitOid: selected.gitCommitOid,
    gitBlobOids: selected.gitBlobOids,
  };
}

async function editionExportFiles(
  engine: Pick<SqliteRunEngine, "readArtifact">,
  approved: ReadonlyMap<ArtifactId, ArtifactView>,
): Promise<{
  readonly files: readonly ApprovedRenderExportFile[];
  readonly pageCounts: Readonly<Record<string, JsonObject>>;
}> {
  const byPath = new Map<string, ArtifactView>();
  for (const artifact of approved.values()) {
    const relativePath = artifact.metadata.relativePath;
    if (typeof relativePath !== "string") continue;
    if (byPath.has(relativePath)) {
      throw new RunEngineError(
        "RENDER_EXPORT_DUPLICATE",
        `Approved artifacts collide at renderer path ${relativePath}`,
      );
    }
    byPath.set(relativePath, artifact);
  }

  const files: ApprovedRenderExportFile[] = [];
  const pageCounts: Record<string, JsonObject> = {};
  for (const language of ["en", "es"] as const) {
    const preflight = requiredRenderArtifact(
      byPath,
      `${language}/preflight.json`,
      "printer_preflight",
      "application/json",
    );
    const counts = preflightPageCounts(jsonMapping(
      await engine.readArtifact(preflight.id).then((loaded) => loaded.bytes),
      `${language} preflight`,
    ));
    pageCounts[language] = counts as unknown as JsonObject;
    const fixed = [
      [`${language}/reader.pdf`, "reader_pdf", "application/pdf", `${language}/reader.pdf`, counts.reader],
      [`${language}/home/booklet-a4.pdf`, "booklet_pdf", "application/pdf", `${language}/booklet.pdf`, counts.booklet],
      [`${language}/home/booklet-a4-cover.pdf`, "render_pdf", "application/pdf", `${language}/booklet-cover.pdf`, counts.bookletCover],
      [`${language}/home/booklet-a4-interior.pdf`, "render_pdf", "application/pdf", `${language}/booklet-interior.pdf`, counts.bookletInterior],
      [`${language}/web-output.zip`, "web_output", "application/zip", `${language}/web.zip`, undefined],
      [`${language}/package.zip`, "package_artifact", "application/zip", `${language}/package.zip`, undefined],
      [`${language}/render-critic.json`, "render_critic_report", "application/json", `${language}/qa/render-critic.json`, undefined],
      [`${language}/preflight.json`, "printer_preflight", "application/json", `${language}/qa/preflight.json`, undefined],
    ] as const;
    for (const [source, kind, mediaType, destination, pageCount] of fixed) {
      const artifact = requiredRenderArtifact(byPath, source, kind, mediaType);
      files.push({
        artifactId: artifact.id,
        destination,
        kind,
        mediaType,
        ...(pageCount === undefined ? {} : { pageCount }),
        ...(kind === "web_output"
          ? {
              unpack: {
                destination: `${language}/web`,
                requiredFiles: ["index.html", "edition.css"],
              },
            }
          : {}),
      });
    }

    files.push(
      ...qaContactSheetSeries(approved, language, "reader"),
      ...qaContactSheetSeries(approved, language, "booklet"),
      ...qaPageSeries(approved, language, "reader-pages", counts.reader),
      ...qaPageSeries(approved, language, "booklet-sides", counts.booklet),
      ...qaPageSeries(
        approved,
        language,
        "cover-booklet-sides",
        counts.bookletCover,
      ),
    );
  }
  return {
    files: files.sort((left, right) => left.destination.localeCompare(right.destination)),
    pageCounts,
  };
}

function requiredRenderArtifact(
  byPath: ReadonlyMap<string, ArtifactView>,
  relativePath: string,
  kind: string,
  mediaType: string,
): ArtifactView {
  const artifact = byPath.get(relativePath);
  if (artifact === undefined || artifact.kind !== kind || artifact.mediaType !== mediaType) {
    throw new RunEngineError(
      "RENDER_EXPORT_MISSING",
      `Approved render needs exact ${kind}/${mediaType} artifact ${relativePath}`,
    );
  }
  return artifact;
}

function qaContactSheetSeries(
  approved: ReadonlyMap<ArtifactId, ArtifactView>,
  language: string,
  series: "reader" | "booklet",
): readonly ApprovedRenderExportFile[] {
  const pattern = new RegExp(
    `^${language}/render-review/${series}-contact-sheet-([0-9]{2,})\\.png$`,
  );
  const matched: Array<{ readonly ordinal: number; readonly artifact: ArtifactView }> = [];
  for (const artifact of approved.values()) {
    const relativePath = artifact.metadata.relativePath;
    if (
      artifact.kind !== "render_review_image" ||
      artifact.mediaType !== "image/png" ||
      typeof relativePath !== "string"
    ) {
      continue;
    }
    const match = pattern.exec(relativePath);
    if (match !== null) {
      matched.push({ ordinal: Number.parseInt(match[1]!, 10), artifact });
    }
  }
  matched.sort((left, right) => left.ordinal - right.ordinal);
  if (
    matched.length === 0 ||
    matched.some((entry, index) => entry.ordinal !== index + 1)
  ) {
    throw new RunEngineError(
      "RENDER_EXPORT_QA_MISSING",
      `Approved ${language} render lacks a contiguous ${series} contact-sheet series`,
    );
  }
  return matched.map(({ artifact, ordinal }) => ({
    artifactId: artifact.id,
    destination:
      `${language}/qa/contact-sheets/${series}-contact-sheet-${String(ordinal).padStart(2, "0")}.png`,
    kind: "render_review_image",
    mediaType: "image/png",
  }));
}

function qaPageSeries(
  approved: ReadonlyMap<ArtifactId, ArtifactView>,
  language: string,
  series: "reader-pages" | "booklet-sides" | "cover-booklet-sides",
  expectedCount: number,
): readonly ApprovedRenderExportFile[] {
  const prefix = `${language}/render-review/${series}/`;
  const artifacts = new Map<string, ArtifactView>();
  for (const artifact of approved.values()) {
    const relativePath = artifact.metadata.relativePath;
    if (
      artifact.kind === "render_review_image" &&
      artifact.mediaType === "image/png" &&
      typeof relativePath === "string" &&
      relativePath.startsWith(prefix)
    ) {
      artifacts.set(relativePath, artifact);
    }
  }
  const files: ApprovedRenderExportFile[] = [];
  for (let ordinal = 1; ordinal <= expectedCount; ordinal += 1) {
    const filename = `page-${String(ordinal).padStart(3, "0")}.png`;
    const relativePath = `${prefix}${filename}`;
    const artifact = artifacts.get(relativePath);
    if (artifact === undefined) {
      throw new RunEngineError(
        "RENDER_EXPORT_QA_MISSING",
        `Approved ${language} render lacks ${relativePath}`,
      );
    }
    files.push({
      artifactId: artifact.id,
      destination: `${language}/qa/pages/${series}/${filename}`,
      kind: "render_review_image",
      mediaType: "image/png",
    });
  }
  if (artifacts.size !== expectedCount) {
    throw new RunEngineError(
      "RENDER_EXPORT_QA_MISMATCH",
      `Approved ${language} ${series} contains ${artifacts.size} pages, expected ${expectedCount}`,
    );
  }
  return files;
}

function preflightPageCounts(payload: Readonly<Record<string, unknown>>): {
  readonly reader: number;
  readonly booklet: number;
  readonly bookletCover: number;
  readonly bookletInterior: number;
} {
  const reader = positiveInteger(mapping(payload.reader)?.page_count);
  const booklet = positiveInteger(mapping(payload.home_booklet)?.sheet_sides);
  const bookletCover = positiveInteger(mapping(payload.home_booklet_cover)?.sheet_sides);
  const bookletInterior = positiveInteger(mapping(payload.home_booklet_interior)?.sheet_sides);
  if (
    reader === undefined ||
    booklet === undefined ||
    bookletCover === undefined ||
    bookletInterior === undefined ||
    booklet !== bookletCover + bookletInterior ||
    reader !== booklet * 2
  ) {
    throw new RunEngineError(
      "RENDER_EXPORT_PAGE_COUNTS",
      "Approved preflight has inconsistent reader and split-booklet page counts",
    );
  }
  return { reader, booklet, bookletCover, bookletInterior };
}

function jsonMapping(bytes: Uint8Array, label: string): Readonly<Record<string, unknown>> {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    const result = mapping(parsed);
    if (result === undefined) throw new Error("expected an object");
    return result;
  } catch (error) {
    throw new RunEngineError(
      "RENDER_EXPORT_JSON",
      `${label} is not a valid JSON object`,
      { cause: error },
    );
  }
}

function mapping(value: unknown): Readonly<Record<string, unknown>> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Readonly<Record<string, unknown>>
    : undefined;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function commonString(left: unknown, right: unknown): string | undefined {
  const first = stringValue(left);
  return first !== undefined && first === stringValue(right) ? first : undefined;
}

function stringRecord(value: unknown): Readonly<Record<string, string>> | undefined {
  const candidate = mapping(value);
  if (
    candidate === undefined ||
    Object.values(candidate).some((item) => typeof item !== "string")
  ) {
    return undefined;
  }
  return Object.fromEntries(
    Object.entries(candidate).sort(([left], [right]) => left.localeCompare(right)),
  ) as Readonly<Record<string, string>>;
}

function positiveInteger(value: unknown): number | undefined {
  return Number.isSafeInteger(value) && (value as number) > 0 ? value as number : undefined;
}

function artifactIdArray(value: unknown): readonly ArtifactId[] | undefined {
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value as unknown as readonly ArtifactId[]
    : undefined;
}

function sameSequence(left: readonly ArtifactId[], right: readonly ArtifactId[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function artifactIdsInJson(values: readonly unknown[]): ReadonlySet<ArtifactId> {
  const result = new Set<ArtifactId>();
  const pending = [...values];
  while (pending.length > 0) {
    const value = pending.pop();
    if (typeof value === "string" && value.startsWith("art_")) {
      result.add(value as ArtifactId);
    } else if (Array.isArray(value)) {
      pending.push(...value);
    } else {
      const object = mapping(value);
      if (object !== undefined) pending.push(...Object.values(object));
    }
  }
  return result;
}

function artifactAncestors(
  artifacts: readonly ArtifactView[],
  roots: readonly ArtifactId[],
): ReadonlySet<ArtifactId> {
  const byId = new Map(artifacts.map((artifact) => [artifact.id, artifact]));
  const ancestors = new Set<ArtifactId>();
  const pending = [...roots];
  while (pending.length > 0) {
    const artifactId = pending.pop();
    if (artifactId === undefined || ancestors.has(artifactId)) continue;
    ancestors.add(artifactId);
    const artifact = byId.get(artifactId);
    if (artifact !== undefined) {
      pending.push(...artifact.parents.map((parent) => parent.artifactId));
    }
  }
  return ancestors;
}

type RunHomeFile = {
  readonly path: string;
  readonly sizeBytes: number;
  readonly sha256: string;
};

type RunHomeInventory = {
  readonly files: readonly RunHomeFile[];
  readonly digest: string;
};

function runHeadEventId(view: RunView): EventId {
  const event = view.events.find((candidate) => candidate.sequence === view.headSequence);
  if (event === undefined) {
    throw new RunEngineError(
      "RUN_LAYOUT_MISMATCH",
      `Run ${view.id} has no event at head sequence ${view.headSequence}`,
    );
  }
  return event.id;
}

function relocationFenceKey(
  operation: "migrate" | "relocate",
  source: string,
  runId: RunId,
  headEventId: string,
): string {
  const digest = createHash("sha256")
    .update(`${operation}\0${resolve(source)}\0${runId}\0${headEventId}`, "utf8")
    .digest("hex");
  return `layout-${operation}:${digest}`;
}

async function verifyExactRun(
  engine: SqliteRunEngine,
  runId: RunId,
  fence: RunMigrationFence,
): Promise<RunView> {
  const runs = await engine.listRuns();
  if (runs.length !== 1 || runs[0]?.id !== runId) {
    throw new RunEngineError(
      "RUN_LAYOUT_MISMATCH",
      `Migration home for ${runId} contains ${runs.length} run identities`,
    );
  }
  const view = await engine.inspect(runId);
  if (
    view.headSequence !== fence.expectedHeadSequence ||
    runHeadEventId(view) !== fence.expectedHeadEventId
  ) {
    throw new RunEngineError(
      "MIGRATION_FENCE_CAS_MISMATCH",
      `Run ${runId} changed after its migration fence was acquired`,
    );
  }
  await verifyMigratedRun(engine, view);
  return view;
}

async function releaseMigrationFenceAt(
  engine: SqliteRunEngine,
  fence: RunMigrationFence,
): Promise<void> {
  try {
    await engine.releaseMigrationFence(fence);
  } finally {
    engine.close();
  }
}

function closeIgnoringErrors(
  ...resources: readonly ({ close(): void } | undefined)[]
): void {
  for (const resource of resources) {
    try {
      resource?.close();
    } catch {
      // Rollback and durable-fence release take precedence over close diagnostics.
    }
  }
}

async function removeCommittedMigrationWorkspace(operationRoot: string): Promise<void> {
  try {
    await rm(operationRoot, { recursive: true, force: true });
  } catch {
    // The installed run is already authoritative; retaining the fenced backup is safer than rollback.
  }
}

async function requirePlainDirectory(path: string, label: string): Promise<void> {
  let info;
  try {
    info = await lstat(path);
  } catch (error) {
    throw new RunEngineError("RUN_LAYOUT_NOT_FOUND", `${label} ${path} does not exist`, {
      cause: error,
    });
  }
  if (info.isSymbolicLink() || !info.isDirectory()) {
    throw new RunEngineError(
      "RUN_LAYOUT_UNSAFE_SOURCE",
      `${label} ${path} must be a real directory, not a symlink or special file`,
    );
  }
}

function assertDisjointMigrationPaths(
  source: string,
  destination: string,
  internalEditionRoot: string,
): void {
  const sourceKey = portablePathKey(source);
  const destinationKey = portablePathKey(destination);
  const editionKey = portablePathKey(internalEditionRoot);
  const creatingKey = portablePathKey(join(internalEditionRoot, ".creating"));
  const migratingKey = portablePathKey(join(internalEditionRoot, ".migrating"));
  if (
    sourceKey === destinationKey ||
    sourceKey.startsWith(`${destinationKey}/`) ||
    destinationKey.startsWith(`${sourceKey}/`) ||
    editionKey === sourceKey ||
    editionKey.startsWith(`${sourceKey}/`) ||
    sourceKey === creatingKey ||
    sourceKey.startsWith(`${creatingKey}/`) ||
    sourceKey === migratingKey ||
    sourceKey.startsWith(`${migratingKey}/`)
  ) {
    throw new RunEngineError(
      "RUN_LAYOUT_PATH_OVERLAP",
      `Relocation source ${source} overlaps its private migration or canonical destination`,
    );
  }
}

async function assertSameMigrationDevice(source: string, migratingRoot: string): Promise<void> {
  const [sourceInfo, migrationInfo] = await Promise.all([
    lstat(source),
    lstat(migratingRoot),
  ]);
  if (
    sourceInfo.isSymbolicLink() ||
    !sourceInfo.isDirectory() ||
    migrationInfo.isSymbolicLink() ||
    !migrationInfo.isDirectory() ||
    sourceInfo.dev !== migrationInfo.dev
  ) {
    throw new RunEngineError(
      "RUN_LAYOUT_CROSS_DEVICE",
      "Run migration source, staging, rollback, and canonical destination must share one device",
    );
  }
}

async function cloneRunHome(source: string, candidate: string): Promise<void> {
  await mkdir(candidate, { mode: 0o700 });
  await cp(join(source, "run.sqlite"), join(candidate, "run.sqlite"), {
    errorOnExist: true,
    force: false,
    preserveTimestamps: true,
  });
  await cp(join(source, "artifacts"), join(candidate, "artifacts"), {
    recursive: true,
    errorOnExist: true,
    force: false,
    preserveTimestamps: true,
    verbatimSymlinks: true,
  });
}

async function inventoryRunHome(root: string): Promise<RunHomeInventory> {
  await requirePlainDirectory(root, "run home");
  const rootInfo = await lstat(root);
  const files: RunHomeFile[] = [];
  await inventoryRegularFile(root, "run.sqlite", rootInfo.dev, files);
  const artifactRoot = join(root, "artifacts");
  await requirePlainDirectory(artifactRoot, "artifact store");
  await inventoryDirectory(root, artifactRoot, rootInfo.dev, files);
  files.sort((left, right) => left.path.localeCompare(right.path));
  const digest = `sha256:${createHash("sha256")
    .update("run-home-inventory/1\n", "utf8")
    .update(JSON.stringify(files), "utf8")
    .digest("hex")}`;
  return { files, digest };
}

async function inventoryDirectory(
  root: string,
  directory: string,
  expectedDevice: number,
  files: RunHomeFile[],
): Promise<void> {
  const entries = await readdir(directory, { withFileTypes: true });
  const aliases = new Set<string>();
  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    const alias = entry.name.normalize("NFC").toLocaleLowerCase("en-US");
    if (aliases.has(alias)) {
      throw new RunEngineError(
        "RUN_LAYOUT_PORTABLE_COLLISION",
        `Run home ${directory} contains case or Unicode aliased entries`,
      );
    }
    aliases.add(alias);
    const absolute = join(directory, entry.name);
    const info = await lstat(absolute);
    if (info.isSymbolicLink() || info.dev !== expectedDevice) {
      throw new RunEngineError(
        "RUN_LAYOUT_UNSAFE_SOURCE",
        `Run home entry ${absolute} is a symlink or mounted on another device`,
      );
    }
    if (info.isDirectory()) {
      await inventoryDirectory(root, absolute, expectedDevice, files);
    } else if (info.isFile()) {
      await inventoryRegularFile(
        root,
        relative(root, absolute).split(sep).join("/"),
        expectedDevice,
        files,
      );
    } else {
      throw new RunEngineError(
        "RUN_LAYOUT_UNSAFE_SOURCE",
        `Run home entry ${absolute} is not a regular file or directory`,
      );
    }
  }
}

async function inventoryRegularFile(
  root: string,
  relativePath: string,
  expectedDevice: number,
  files: RunHomeFile[],
): Promise<void> {
  const absolute = join(root, ...relativePath.split("/"));
  const before = await lstat(absolute, { bigint: true });
  if (
    before.isSymbolicLink() ||
    !before.isFile() ||
    before.dev !== BigInt(expectedDevice) ||
    before.size > BigInt(Number.MAX_SAFE_INTEGER)
  ) {
    throw new RunEngineError(
      "RUN_LAYOUT_UNSAFE_SOURCE",
      `Run home file ${absolute} is not a same-device regular file with a safe size`,
    );
  }
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(absolute)) hash.update(chunk as Buffer);
  const after = await lstat(absolute, { bigint: true });
  if (
    before.dev !== after.dev ||
    before.ino !== after.ino ||
    before.size !== after.size ||
    before.mtimeNs !== after.mtimeNs ||
    before.ctimeNs !== after.ctimeNs
  ) {
    throw new RunEngineError(
      "RUN_LAYOUT_SOURCE_DRIFT",
      `Run home file ${relativePath} changed while it was inventoried`,
    );
  }
  files.push({
    path: relativePath,
    sizeBytes: Number(before.size),
    sha256: `sha256:${hash.digest("hex")}`,
  });
}

function assertSameRunHomeInventory(
  expected: RunHomeInventory,
  actual: RunHomeInventory,
  message: string,
): void {
  if (expected.digest !== actual.digest || JSON.stringify(expected.files) !== JSON.stringify(actual.files)) {
    throw new RunEngineError("RUN_LAYOUT_SOURCE_DRIFT", message);
  }
}

function relocationVerificationArtifacts(view: RunView): readonly ArtifactId[] {
  const renderActor = view.actors.find((actor) => actor.machine === "render");
  const currentRenderIds = Array.isArray(renderActor?.context.renderArtifacts)
    ? renderActor.context.renderArtifacts.filter(
        (value): value is ArtifactId => typeof value === "string",
      )
    : [];
  const currentRender = view.artifacts
    .filter((artifact) => currentRenderIds.includes(artifact.id))
    .sort((left, right) => left.sizeBytes - right.sizeBytes)[0];
  if (currentRender !== undefined) {
    return [currentRender.id];
  }
  const representative = [...view.artifacts].sort(
    (left, right) => right.sizeBytes - left.sizeBytes,
  )[0];
  return representative === undefined ? [] : [representative.id];
}

/** A clone is only a valid candidate when its public projection and every
 * immutable payload can be read with the cloned database's relative paths. */
async function verifyMigratedRun(engine: SqliteRunEngine, view: RunView): Promise<void> {
  for (const artifact of view.artifacts) {
    await engine.readArtifact(artifact.id);
  }
}
