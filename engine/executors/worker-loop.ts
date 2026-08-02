import type {
  ModelChoice,
  ModelPolicy,
  RunId,
  RunView,
  WorkAnswer,
  WorkClaim,
  WorkFailure,
  WorkOfferId,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import type { ArtifactReader, Executor } from "./types.ts";
import {
  SubprocessExecutionError,
} from "./subprocess.ts";

export interface WorkEngine extends ArtifactReader {
  inspect(runId: RunId): Promise<RunView>;
  claim(offerId: WorkOfferId, worker: WorkerIdentity): Promise<WorkClaim>;
  heartbeat(claim: WorkClaim): Promise<WorkClaim>;
  answer(claim: WorkClaim, answer: WorkAnswer): Promise<RunView>;
  fail(claim: WorkClaim, failure: WorkFailure): Promise<RunView>;
}

export type ExecutorRegistration = {
  readonly executor: Executor;
  readonly adapter?: string;
  readonly model?: string;
  readonly reasoningEffort?: string;
  readonly roles?: readonly string[];
  readonly principalPrefix?: string;
};

export interface ExecutorResolver {
  resolve(view: RunView, offer: WorkOfferView): Executor | undefined;
}

export type WorkerLoopResult = {
  readonly answered: readonly WorkOfferId[];
  readonly failed: readonly WorkOfferId[];
  readonly skipped: readonly WorkOfferId[];
  readonly superseded: readonly WorkOfferId[];
};

export type ExecuteAvailableWorkOptions = {
  readonly heartbeatIntervalMs?: number;
  readonly attemptTimeoutMs?: number;
  readonly maxConcurrency?: number;
  readonly now?: () => Date;
};

export type RunWorkerOptions = ExecuteAvailableWorkOptions & {
  readonly pollIntervalMs?: number;
  readonly once?: boolean;
};

export class WorkerConfigurationError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "WorkerConfigurationError";
    this.code = code;
  }
}

type OfferDisposition = "answered" | "failed" | "skipped" | "superseded";

const DEFAULT_HEARTBEAT_INTERVAL_MS = 30_000;
const DEFAULT_ATTEMPT_TIMEOUT_MS = 30 * 60_000;
const DEFAULT_POLL_INTERVAL_MS = 1_000;

/**
 * Resolves immutable work against frozen actor input. Model-backed work must
 * match the exact adapter, model, and reasoning policy. Non-model work must be
 * bound to a role explicitly, so an unrelated subprocess cannot claim it.
 */
export class ConfiguredExecutorResolver implements ExecutorResolver {
  private readonly registrations: readonly ExecutorRegistration[];

  constructor(registrations: readonly ExecutorRegistration[]) {
    this.registrations = [...registrations];
  }

  resolve(view: RunView, offer: WorkOfferView): Executor | undefined {
    const actor = view.actors.find((candidate) => candidate.id === offer.actorId);
    if (actor === undefined) {
      throw new WorkerConfigurationError(
        "OFFER_ACTOR_MISSING",
        `Offer ${offer.id} references actor ${offer.actorId}, which is absent from its run`,
      );
    }
    const modelBacked =
      offer.allowedWorkerCapabilities.includes("text_model") ||
      offer.allowedWorkerCapabilities.includes("image_model");
    const modelChoice = modelBacked ? modelChoiceFor(actor.input, offer) : undefined;
    const matches = this.registrations.filter((registration) => {
      if (!registration.executor.accepts(offer)) {
        return false;
      }
      const explicitRole = registration.roles?.includes(offer.role) ?? false;
      if (modelChoice === undefined) {
        return explicitRole;
      }
      if (
        registration.adapter !== modelChoice.adapter ||
        registration.model !== modelChoice.model
      ) {
        return false;
      }
      if (
        registration.reasoningEffort !== undefined &&
        registration.reasoningEffort !== modelChoice.reasoningEffort
      ) {
        return false;
      }
      return registration.roles === undefined || explicitRole;
    });
    if (
      offer.allowedWorkerCapabilities.includes("text_model") &&
      modelChoice === undefined &&
      matches.length === 0
    ) {
      throw new WorkerConfigurationError(
        "MODEL_POLICY_MISSING",
        `Text-model offer ${offer.id} (${offer.role}) has no immutable model policy and no explicit role executor`,
      );
    }
    if (matches.length > 1) {
      throw new WorkerConfigurationError(
        "EXECUTOR_AMBIGUOUS",
        `Offer ${offer.id} (${offer.role}) matches multiple configured executors: ${matches
          .map(({ executor }) => executor.id)
          .join(", ")}`,
      );
    }
    const selected = matches[0];
    if (selected === undefined) {
      if (!offer.allowedWorkerCapabilities.includes("human")) {
        throw new WorkerConfigurationError(
          "EXECUTOR_NOT_CONFIGURED",
          `No configured executor matches ${offer.role} offer ${offer.id}`,
        );
      }
      return undefined;
    }
    return bindExecutorIdentity(selected, offer);
  }
}

/** Executes one claimable snapshot. Machines remain the sole orchestration authority. */
export async function executeAvailableWork(
  engine: WorkEngine,
  runId: RunId,
  executors: readonly Executor[] | ExecutorResolver,
  signal: AbortSignal,
  options: ExecuteAvailableWorkOptions = {},
): Promise<WorkerLoopResult> {
  validatePositiveInteger(
    options.heartbeatIntervalMs ?? DEFAULT_HEARTBEAT_INTERVAL_MS,
    "heartbeatIntervalMs",
  );
  validatePositiveInteger(
    options.attemptTimeoutMs ?? DEFAULT_ATTEMPT_TIMEOUT_MS,
    "attemptTimeoutMs",
  );
  const maxConcurrency = options.maxConcurrency ?? 1;
  validatePositiveInteger(maxConcurrency, "maxConcurrency");

  const view = await engine.inspect(runId);
  const resolver = isExecutorResolver(executors)
    ? executors
    : new LegacyExecutorResolver(executors);
  const nowMs = (options.now ?? (() => new Date()))().getTime();
  const claimable = view.offers.filter((offer) => isClaimable(view, offer, nowMs));
  const dispositions = new Map<WorkOfferId, OfferDisposition>();

  for (let offset = 0; offset < claimable.length; offset += maxConcurrency) {
    if (signal.aborted) {
      break;
    }
    const batch = claimable.slice(offset, offset + maxConcurrency);
    const scheduled = batch.map((offer) => ({
      offer,
      executor: signal.aborted ? undefined : resolver.resolve(view, offer),
    }));
    const results = await Promise.all(scheduled.map(async ({ offer, executor }) => {
      if (signal.aborted || executor === undefined) {
        return [offer.id, "skipped"] as const;
      }
      return [
        offer.id,
        await executeOffer(engine, executor, offer, signal, options),
      ] as const;
    }));
    for (const [offerId, disposition] of results) {
      dispositions.set(offerId, disposition);
    }
  }

  return resultFromDispositions(claimable, dispositions);
}

/**
 * Polls until the run becomes terminal or the caller cancels. With `once`, it
 * executes a single claimable snapshot, which is useful for schedulers and CI.
 */
export async function runWorker(
  engine: WorkEngine,
  runId: RunId,
  executors: readonly Executor[] | ExecutorResolver,
  signal: AbortSignal,
  options: RunWorkerOptions = {},
): Promise<WorkerLoopResult> {
  const pollIntervalMs = options.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS;
  validatePositiveInteger(pollIntervalMs, "pollIntervalMs");
  const aggregate: Record<keyof WorkerLoopResult, WorkOfferId[]> = {
    answered: [],
    failed: [],
    skipped: [],
    superseded: [],
  };

  while (!signal.aborted) {
    const result = await executeAvailableWork(engine, runId, executors, signal, options);
    mergeResult(aggregate, result);
    const view = await engine.inspect(runId);
    if (options.once === true || isTerminalRun(view)) {
      break;
    }
    if (result.answered.length === 0 && result.failed.length === 0) {
      await abortableDelay(pollIntervalMs, signal);
    }
  }
  return aggregate;
}

async function executeOffer(
  engine: WorkEngine,
  executor: Executor,
  offer: WorkOfferView,
  parentSignal: AbortSignal,
  options: ExecuteAvailableWorkOptions,
): Promise<OfferDisposition> {
  let claim: WorkClaim;
  try {
    claim = await engine.claim(offer.id, executor.worker);
  } catch (error) {
    if (errorCode(error) === "WORK_UNAVAILABLE") {
      return "skipped";
    }
    throw error;
  }

  const control = createAttemptControl(
    parentSignal,
    options.attemptTimeoutMs ?? DEFAULT_ATTEMPT_TIMEOUT_MS,
  );
  const context = { claim, offer, artifacts: engine, signal: control.signal };
  let executionSettled = false;
  let releaseDeferred = false;
  const execution = Promise.resolve().then(async () => {
    try {
      return await executor.execute(context);
    } finally {
      executionSettled = true;
    }
  });
  // A timed-out executor is fenced immediately. Its underlying adapter still
  // owns cleanup and gets a chance to stop after observing the abort signal.
  void execution.catch(() => undefined);
  const heartbeat = heartbeatClaim(
    engine,
    claim,
    safeHeartbeatInterval(
      claim,
      options.heartbeatIntervalMs ?? DEFAULT_HEARTBEAT_INTERVAL_MS,
    ),
    control,
  );

  try {
    const answer = await raceWithAbort(execution, control.signal);
    control.stopHeartbeat();
    await heartbeat;
    control.throwIfAborted();
    const view = await engine.answer(claim, answer);
    return acceptedAnswer(view, claim) ? "answered" : "superseded";
  } catch (error) {
    control.stopHeartbeat();
    await heartbeat.catch(() => undefined);
    const failure = classifyFailure(error, executor.id, control);
    const view = await engine.fail(claim, failure);
    if (!executionSettled) {
      releaseDeferred = true;
      void execution.then(
        async () => await executor.release?.(context),
        async () => await executor.release?.(context),
      ).catch(() => undefined);
    }
    if (acceptedAnswer(view, claim)) {
      return "answered";
    }
    return acceptedFailure(view, claim) ? "failed" : "superseded";
  } finally {
    control.dispose();
    if (!releaseDeferred) {
      await executor.release?.(context);
    }
  }
}

class AttemptControl {
  readonly signal: AbortSignal;
  private readonly attempt = new AbortController();
  private readonly heartbeat = new AbortController();
  private readonly parent: AbortSignal;
  private readonly timeout: ReturnType<typeof setTimeout>;
  private heartbeatFailure: unknown;
  private timeoutFired = false;
  private readonly abortFromParent: () => void;

  constructor(parent: AbortSignal, timeoutMs: number) {
    this.parent = parent;
    this.signal = this.attempt.signal;
    this.abortFromParent = () => this.attempt.abort(new AttemptAbort("canceled"));
    if (parent.aborted) {
      this.abortFromParent();
    } else {
      parent.addEventListener("abort", this.abortFromParent, { once: true });
    }
    this.timeout = setTimeout(() => {
      this.timeoutFired = true;
      this.attempt.abort(new AttemptAbort("timeout"));
    }, timeoutMs);
  }

  get heartbeatSignal(): AbortSignal {
    return this.heartbeat.signal;
  }

  abortForHeartbeat(error: unknown): void {
    this.heartbeatFailure = error;
    this.attempt.abort(new AttemptAbort("stale", error));
  }

  stopHeartbeat(): void {
    this.heartbeat.abort();
  }

  throwIfAborted(): void {
    if (this.signal.aborted) {
      throw this.signal.reason ?? new AttemptAbort("canceled");
    }
  }

  classification(): "canceled" | "timeout" | undefined {
    if (this.timeoutFired) {
      return "timeout";
    }
    if (this.parent.aborted || this.heartbeatFailure !== undefined) {
      return "canceled";
    }
    return undefined;
  }

  dispose(): void {
    clearTimeout(this.timeout);
    this.heartbeat.abort();
    this.parent.removeEventListener("abort", this.abortFromParent);
  }
}

class AttemptAbort extends Error {
  readonly classification: "canceled" | "stale" | "timeout";

  constructor(
    classification: "canceled" | "stale" | "timeout",
    options?: unknown,
  ) {
    super(`Attempt ${classification}`, options instanceof Error ? { cause: options } : undefined);
    this.name = "AttemptAbort";
    this.classification = classification;
  }
}

function createAttemptControl(parent: AbortSignal, timeoutMs: number): AttemptControl {
  return new AttemptControl(parent, timeoutMs);
}

async function heartbeatClaim(
  engine: WorkEngine,
  initialClaim: WorkClaim,
  intervalMs: number,
  control: AttemptControl,
): Promise<void> {
  let claim = initialClaim;
  try {
    while (!control.heartbeatSignal.aborted) {
      await abortableDelay(intervalMs, control.heartbeatSignal);
      if (control.heartbeatSignal.aborted) {
        break;
      }
      claim = await engine.heartbeat(claim);
    }
  } catch (error) {
    if (!control.heartbeatSignal.aborted) {
      control.abortForHeartbeat(error);
      throw error;
    }
  }
}

function classifyFailure(
  error: unknown,
  executorId: string,
  control: AttemptControl,
): WorkFailure {
  const controlled = control.classification();
  if (controlled !== undefined) {
    return {
      classification: controlled,
      message: `${executorId}: attempt ${controlled}`,
    };
  }
  if (error instanceof AttemptAbort) {
    return {
      classification: error.classification === "timeout" ? "timeout" : "canceled",
      message: `${executorId}: ${error.message}`,
    };
  }
  if (error instanceof SubprocessExecutionError) {
    return {
      classification: error.classification,
      message: `${executorId}: ${error.message}`,
      details: { exitCode: error.exitCode, stderr: error.stderr },
    };
  }
  if (errorCode(error)?.startsWith("ANSWER_") === true) {
    return {
      classification: "permanent",
      message: `${executorId}: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
  return {
    classification: "retryable",
    message: `${executorId}: ${error instanceof Error ? error.message : String(error)}`,
  };
}

function modelChoiceFor(input: unknown, offer: WorkOfferView): ModelChoice | undefined {
  if (!isRecord(input)) {
    return undefined;
  }
  const spec = input.spec;
  if (!isRecord(spec) || !isRecord(spec.modelPolicy)) {
    return undefined;
  }
  const policy = spec.modelPolicy as ModelPolicy;
  const selected = isRecord(policy.roles) && isRecord(policy.roles[offer.role])
    ? policy.roles[offer.role]
    : policy.default;
  if (
    !isRecord(selected) ||
    typeof selected.adapter !== "string" ||
    typeof selected.model !== "string"
  ) {
    return undefined;
  }
  return selected as ModelChoice;
}

function bindExecutorIdentity(
  registration: ExecutorRegistration,
  offer: WorkOfferView,
): Executor {
  const executor = registration.executor;
  const principalPrefix = registration.principalPrefix ?? executor.worker.principalId;
  return {
    id: executor.id,
    capabilities: executor.capabilities,
    worker: {
      ...executor.worker,
      principalId: `${principalPrefix}:${offer.role}:${offer.id}`,
      displayName: executor.worker.displayName ?? executor.id,
    },
    accepts: (candidate) => candidate.id === offer.id && executor.accepts(candidate),
    execute: async (context) => await executor.execute(context),
    ...(executor.release === undefined
      ? {}
      : { release: async (context) => await executor.release?.(context) }),
  };
}

class LegacyExecutorResolver implements ExecutorResolver {
  private readonly executors: readonly Executor[];

  constructor(executors: readonly Executor[]) {
    this.executors = executors;
  }

  resolve(_view: RunView, offer: WorkOfferView): Executor | undefined {
    return this.executors.find((candidate) => candidate.accepts(offer));
  }
}

function isExecutorResolver(
  value: readonly Executor[] | ExecutorResolver,
): value is ExecutorResolver {
  return !Array.isArray(value);
}

function isClaimable(view: RunView, offer: WorkOfferView, nowMs: number): boolean {
  if (offer.status === "offered") {
    return true;
  }
  if (offer.status !== "claimed" || offer.activeAttemptId === undefined) {
    return false;
  }
  const attempt = view.attempts.find((candidate) => candidate.id === offer.activeAttemptId);
  return attempt?.status === "active" && Date.parse(attempt.leaseExpiresAt) <= nowMs;
}

function acceptedAnswer(view: RunView, claim: WorkClaim): boolean {
  const attempt = view.attempts.find((candidate) => candidate.id === claim.attemptId);
  const offer = view.offers.find((candidate) => candidate.id === claim.offerId);
  return attempt?.status === "answered" && offer?.status === "answered";
}

function acceptedFailure(view: RunView, claim: WorkClaim): boolean {
  const attempt = view.attempts.find((candidate) => candidate.id === claim.attemptId);
  const offer = view.offers.find((candidate) => candidate.id === claim.offerId);
  return (
    (attempt?.status === "failed" || attempt?.status === "timed_out") &&
    (offer?.status === "failed" || offer?.status === "canceled")
  );
}

function isTerminalRun(view: RunView): boolean {
  return view.status === "complete" || view.status === "failed";
}

function safeHeartbeatInterval(claim: WorkClaim, configuredMs: number): number {
  const remainingMs = Date.parse(claim.leaseExpiresAt) - Date.now();
  if (!Number.isFinite(remainingMs)) {
    return configuredMs;
  }
  return Math.max(1, Math.min(configuredMs, Math.floor(remainingMs / 3)));
}

async function raceWithAbort<T>(work: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) {
    throw signal.reason ?? new AttemptAbort("canceled");
  }
  let abort: (() => void) | undefined;
  const canceled = new Promise<never>((_resolve, reject) => {
    abort = () => reject(signal.reason ?? new AttemptAbort("canceled"));
    signal.addEventListener("abort", abort, { once: true });
  });
  try {
    return await Promise.race([work, canceled]);
  } finally {
    if (abort !== undefined) {
      signal.removeEventListener("abort", abort);
    }
  }
}

async function abortableDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return;
  }
  await new Promise<void>((resolveDelay) => {
    const timeout = setTimeout(done, milliseconds);
    timeout.unref();
    function done(): void {
      clearTimeout(timeout);
      signal.removeEventListener("abort", done);
      resolveDelay();
    }
    signal.addEventListener("abort", done, { once: true });
  });
}

function resultFromDispositions(
  offers: readonly WorkOfferView[],
  dispositions: ReadonlyMap<WorkOfferId, OfferDisposition>,
): WorkerLoopResult {
  const result: Record<keyof WorkerLoopResult, WorkOfferId[]> = {
    answered: [],
    failed: [],
    skipped: [],
    superseded: [],
  };
  for (const offer of offers) {
    const disposition = dispositions.get(offer.id) ?? "skipped";
    result[disposition].push(offer.id);
  }
  return result;
}

function mergeResult(
  destination: Record<keyof WorkerLoopResult, WorkOfferId[]>,
  source: WorkerLoopResult,
): void {
  for (const key of Object.keys(destination) as readonly (keyof WorkerLoopResult)[]) {
    for (const offerId of source[key]) {
      if (!destination[key].includes(offerId)) {
        destination[key].push(offerId);
      }
    }
  }
}

function validatePositiveInteger(value: number, label: string): void {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new WorkerConfigurationError(
      "WORKER_OPTION_INVALID",
      `${label} must be a positive integer`,
    );
  }
}

function errorCode(error: unknown): string | undefined {
  return isRecord(error) && typeof error.code === "string" ? error.code : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
