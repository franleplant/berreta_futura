import type { JsonObject } from "../contracts/json.ts";
import type {
  ArticleDecisionAnswer,
  ArticleInputBinding,
  ArticleStartRequest,
  ArticleWorkflowResult,
} from "../contracts/workflow-run.ts";
import type { DurablePromotionRequest } from "../durable/types.ts";
import type {
  ArticleExecutionId,
  ArtifactId,
  AttemptId,
  ManuscriptRevisionId,
} from "../contracts/ids.ts";
import type {
  ArtifactLedger,
  LedgerArtifactInput,
  LedgerDecision,
} from "../workflow-authority/artifact-ledger.ts";
import type { RendererIdentity } from "./renderer-identity.ts";

/** Provenance copied from Loops, stored as evidence but never as authority. */
export type WorkflowAttemptContext = {
  readonly runId: string;
  readonly invocationId: string;
  readonly parentInvocationId?: string;
  readonly workflowName: string;
  readonly workflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly callId: string;
  readonly attemptId: string;
  readonly attemptNumber: number;
  readonly key: string;
  readonly kind: "agent" | "step";
};

/** Human waits intentionally have no attempt fields. */
export type WorkflowWaitContext = {
  readonly runId: string;
  readonly invocationId: string;
  readonly parentInvocationId?: string;
  readonly workflowName: string;
  readonly workflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly callId: string;
  readonly waitId: string;
  readonly key: string;
  readonly kind: "wait";
};

/** Root invocation provenance used for run observations. */
export type WorkflowInvocationContext = {
  readonly runId: string;
  readonly invocationId: string;
  readonly parentInvocationId?: string;
  readonly workflowName: string;
  readonly workflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly kind: "workflow";
};

export type WorkflowDurableContext =
  | WorkflowAttemptContext
  | WorkflowWaitContext
  | WorkflowInvocationContext;

/**
 * Magazine identity for one article execution. Loops context is copied as
 * evidence, but never becomes the article's identity or authority.
 */
export type ArticleExecutionContext = {
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId?: string;
  readonly durableContext?: WorkflowDurableContext;
};

/** A claimed model/tool execution owned by the magazine authority. */
export type ArticleAttemptClaim = {
  readonly schemaVersion: "article-attempt-claim/1";
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly operationKey: string;
  readonly role: "model" | "tool";
  readonly access: "source_aware" | "source_blind" | "tool";
  readonly manuscriptArtifactId: ArtifactId;
  readonly manuscriptRevisionId: ManuscriptRevisionId;
  /** Magazine claim identity. Loops attemptId is retained in durableContext. */
  readonly claimId: AttemptId;
  /** Monotonic magazine claim number for this operation. */
  readonly claimSequence: number;
  readonly attemptId: string;
  readonly attemptNumber: number;
  readonly fence: number;
  readonly principalId: string;
  readonly credentialProfileId: string;
  readonly authority: "model" | "tool";
  readonly capabilities: readonly string[];
  readonly leaseExpiresAt: string;
  readonly durableContext: WorkflowAttemptContext;
};

export type ArticleAttemptArtifactSeed = Omit<LedgerArtifactInput, "id" | "runId" | "durableContext"> & {
  /** Stable name within one attempt. The final artifact ID is authority-derived. */
  readonly key: string;
};

export type ArticleAttemptExecutionResult<T> = {
  readonly selected: true;
  readonly value: T;
  readonly claim: ArticleAttemptClaim;
  readonly artifacts: readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
} | {
  readonly selected: false;
  readonly reason: "already_selected" | "stale";
  readonly claim?: ArticleAttemptClaim;
  readonly artifacts: readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
};

export type ArticleMeasurement = {
  readonly schemaVersion: "article-measurement/1";
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly pageCount: number;
  readonly maximumReaderPages: number;
  readonly fits: boolean;
  readonly openerFits: boolean;
  readonly layouts: readonly JsonObject[];
  readonly inputArtifactIds: readonly ArtifactId[];
};

/** Private ports used by the fixed article workflow source graph. */
export type ArticleWorkflowPorts = {
  readonly ledger: ArtifactLedger;
  readonly measureArticle: (input: {
    readonly articleId: string;
    readonly manuscriptArtifactId: ArtifactId;
    readonly measurementProfileArtifactId: ArtifactId;
    readonly rendererIdentity: RendererIdentity;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<ArticleMeasurement>;
  readonly requireDecision: (decisionArtifactId: ArtifactId) => LedgerDecision;
  readonly promote: (input: {
    readonly articleExecutionId: ArticleExecutionId;
    readonly request: DurablePromotionRequest;
    readonly reviewer: string;
    readonly rationale: string;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<ArticleWorkflowResult>;
};

/** Internal args; the public request cannot inject the renderer identity. */
export type ArticleRuntimeStartArgs = ArticleStartRequest & {
  readonly articleExecutionId: ArticleExecutionId;
  readonly rendererIdentity: RendererIdentity;
};

export type MagazineWorkflowContext = {
  readonly durableContext?: () => WorkflowDurableContext | undefined;
  readonly step: <T>(
    key: string,
    fn: () => Promise<T> | T,
    options: { readonly input: JsonObject },
  ) => Promise<T>;
  readonly wait: (
    key: string,
    options: { readonly request: JsonObject },
  ) => Promise<ArticleDecisionAnswer>;
};

export type MagazineLoopsInspection = {
  readonly runId: string;
  readonly status: "running" | "waiting" | "completed" | "failed" | "canceled";
  readonly workflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly result?: ArticleWorkflowResult;
  readonly invocations: readonly MagazineLoopsInvocation[];
  readonly calls: readonly MagazineLoopsCall[];
  readonly waits: readonly MagazineLoopsWait[];
};

export type MagazineLoopsInvocation = {
  readonly invocationId: string;
  readonly parentInvocationId?: string;
  readonly workflowName: string;
  readonly workflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly status: string;
};

export type MagazineLoopsCall = {
  readonly callId: string;
  readonly invocationId: string;
  readonly key: string;
  readonly kind: "step" | "wait" | "workflow" | "agent";
  readonly status: string;
  readonly result?: unknown;
  readonly attempts: readonly MagazineLoopsAttempt[];
};

export type MagazineLoopsAttempt = {
  readonly attemptId: string;
  readonly attemptNumber: number;
  readonly status: string;
};

export type MagazineLoopsWait = {
  readonly waitId: string;
  readonly callId: string;
  readonly invocationId: string;
  readonly key: string;
  readonly status: string;
  readonly request?: unknown;
  readonly answer?: unknown;
};
