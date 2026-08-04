import type { JsonObject } from "../contracts/json.ts";
import type {
  ArticleDecisionAnswer,
  ArticleInputBinding,
  ArticleWorkflowResult,
} from "../contracts/workflow-run.ts";
import type { DurablePromotionRequest } from "../durable/types.ts";
import type {
  ArticleExecutionId,
  ArtifactId,
  AttemptId,
  ManuscriptRevisionId,
  PromotionId,
  RevisionId,
  RunId,
} from "../contracts/ids.ts";
import type { DurableLogicalItem } from "../durable/types.ts";
import type { LoopsArticleEntryInput } from "../durable/write-pipeline.ts";
import type {
  ArtifactLedger,
  LedgerArtifactInput,
  LedgerDecision,
} from "../workflow-authority/artifact-ledger.ts";
import type { RendererIdentity } from "./renderer-identity.ts";
import type { ScopedArticleMeasurementArtifactReader } from "../renderer-adapter/article-measurement.ts";
import type { ArticleReviewPanelInput, ArticleReviewPanelResult } from "./article-review-panel.ts";
import type {
  ArticleMaterialContext,
  ArticleMaterialSelectionContext,
} from "../article-production/materials.ts";

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
  /** Digest of the complete immutable operation input set. */
  readonly operationInputDigest: string;
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
  readonly adopted?: false;
  readonly claim: ArticleAttemptClaim;
  readonly artifacts: readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
} | {
  /** A committed result adopted after a caller crashed or lost the CAS. */
  readonly selected: true;
  readonly adopted: true;
  readonly claim?: ArticleAttemptClaim;
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
  /** Attempt-selected renderer output artifacts, when produced by a panel. */
  readonly rendererOutputArtifactIds?: readonly ArtifactId[];
};

/** Private ports used by the fixed article workflow source graph. */
export type ArticleWorkflowPorts = {
  readonly ledger: ArtifactLedger;
  /** Validate all process-local resources before a run is persisted. */
  readonly validateRuntimeResources?: () => Promise<void>;
  readonly measureArticle: (input: {
    readonly articleId: string;
    readonly manuscriptArtifactId: ArtifactId;
    readonly measurementProfileArtifactId: ArtifactId;
    readonly rendererIdentity: RendererIdentity;
    /** Exact material package for measurement; no ledger fallback is allowed. */
    readonly artifacts?: ScopedArticleMeasurementArtifactReader;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<ArticleMeasurement>;
  /** Data-driven review panel. Every article run executes the declared plan. */
  readonly runReviewPanel: (
    input: ArticleReviewPanelInput,
    context: MagazineWorkflowContext,
  ) => Promise<ArticleReviewPanelResult>;
  readonly requireDecision: (decisionArtifactId: ArtifactId) => LedgerDecision;
  readonly promote: (input: {
    readonly articleExecutionId: ArticleExecutionId;
    readonly request: DurablePromotionRequest;
    readonly measurementArtifactId?: ArtifactId;
    readonly reviewer: string;
    readonly rationale: string;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<ArticleWorkflowResult>;
};

/** Internal args; the public request cannot inject the renderer identity. */
export type ArticleRuntimeStartArgs = {
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly editionId: string;
  readonly language: string;
  readonly logicalItem: Extract<DurableLogicalItem, { readonly kind: "article" }>;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly expectedParentRevisionId: RevisionId | null;
  readonly promotionId: PromotionId;
  readonly revisionId: RevisionId;
  readonly entryArtifactId: ArtifactId;
  /** Exact immutable profile-backed workflow input. */
  readonly entry: LoopsArticleEntryInput;
  readonly rendererIdentity: RendererIdentity;
  /** Frozen review inputs for the Loops article workflow. */
  readonly review: {
    readonly materialContext: ArticleMaterialContext;
    readonly materialSelection?: ArticleMaterialSelectionContext;
    readonly teaching?: "applicable" | "not_applicable";
  };
};

export type MagazineWorkflowContext = {
  readonly durableContext?: () => WorkflowDurableContext | undefined;
  readonly step: <T>(
    key: string,
    fn: () => Promise<T> | T,
    options: {
      readonly input: JsonObject;
      readonly schema?: unknown;
      readonly label?: string;
      readonly retry?: {
        readonly maxAttempts?: number;
        readonly backoffMs?: number;
        readonly backoffMultiplier?: number;
        readonly retryOn?: "always" | "never" | "retryable" | readonly string[];
      };
    },
  ) => Promise<T>;
  /** The Loops-native strict output schema, supplied by the entry adapter. */
  readonly reviewStepResultSchema?: unknown;
  /** Loops' durable barrier. Each thunk must checkpoint its own stable key. */
  readonly parallel: <T>(
    thunks: readonly (() => Promise<T> | T)[],
    options?: { readonly failureMode?: "fail-fast" | "collect" },
  ) => Promise<readonly (T | null)[]>;
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
