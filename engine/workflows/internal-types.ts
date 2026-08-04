import type { JsonObject } from "../contracts/json.ts";
import type {
  ArticleDecisionAnswer,
  ArticleInputBinding,
  ArticleWorkflowResult,
  ArticleWorkflowRouteResult,
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
import type { DurableLogicalItem, InputRevisionRef } from "../durable/types.ts";
import type { LoopsArticleEntryInput } from "../durable/write-pipeline.ts";
import type {
  ArtifactLedger,
  LedgerArtifactInput,
  LedgerDecision,
} from "../workflow-authority/artifact-ledger.ts";
import type { RendererIdentity } from "./renderer-identity.ts";
import type { ScopedArticleMeasurementArtifactReader } from "../renderer-adapter/article-measurement.ts";
import type { ArticleReviewPanelInput, ArticleReviewPanelResult } from "./article-review-panel.ts";
import type { WriterResult } from "../executors/closed-writer/writer-result.ts";
import type {
  ArticleMaterialContext,
  ArticleMaterialSelectionContext,
} from "../article-production/materials.ts";
import type { TranslationWriterExecutionResult } from "../executors/closed-translation-writer/result.ts";

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
  /** Number of writer rewrites already consumed by this article execution. */
  readonly rewriteOrdinal?: number;
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

export type EditorialMeasurement = {
  readonly schemaVersion: "editorial-measurement/1";
  readonly operation: "measure_edition";
  readonly editionId: "004";
  readonly editorialId: "opening";
  readonly language: "en";
  readonly manuscriptArtifactId: ArtifactId;
  readonly contentArtifactIds: readonly ArtifactId[];
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly pageCount: number;
  readonly maximumReaderPages: 1;
  readonly fits: boolean;
  readonly labelVisible: boolean;
  readonly labelFits: boolean;
  readonly titleVisible: boolean;
  readonly titleFits: boolean;
  readonly bylineVisible: boolean;
  readonly bylineFits: boolean;
  readonly rendererOutputArtifactIds?: readonly ArtifactId[];
};

export type EditorialReviewFinding = {
  readonly findingId: string;
  readonly target: "editorial:opening";
  readonly severity: "must_fix" | "should_fix";
  readonly problem: string;
  readonly requestedOutcome: string;
};

export type EditorialReviewResult = {
  readonly schemaVersion: "editorial-review-result/1";
  readonly editionId: "004";
  readonly editorialId: "opening";
  readonly target: "editorial:opening";
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly reviewCycleId: string;
  readonly assessment: "pass" | "findings" | "human_required";
  readonly findings: readonly EditorialReviewFinding[];
};

export type EditorialReviewExecutionResult = {
  readonly selected: true;
  readonly findings: readonly EditorialReviewFinding[];
  readonly artifacts: readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
} | {
  readonly selected: false;
  readonly reason: "already_selected" | "stale";
  readonly artifacts: readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
};

export type EditorialPromotionResult = {
  readonly promotionArtifactId: ArtifactId;
  readonly durableRevisionId: string;
  readonly manifestDigest: string;
  readonly gitCommitOid: string;
};

export type TranslationWriterInput = {
  readonly translationExecutionId: string;
  readonly operationKey: string;
  readonly pieceKind: "article" | "editorial";
  readonly pieceId: string;
  readonly language: string;
  readonly englishArtifactId: ArtifactId;
  readonly englishDigest: string;
  readonly promptArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
};

export type TranslationPromotionResult = {
  readonly durableRevisionId: string;
  readonly manifestDigest: string;
  readonly gitCommitOid: string;
  readonly gitBlobOids: Readonly<Record<string, string>>;
};

export type CompositionPromotionResult = TranslationPromotionResult;

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
  /** Closed, source-aware writer. The durable adapter owns its retry policy. */
  readonly runWriter?: (
    input: {
      readonly articleExecutionId: ArticleExecutionId;
      readonly operationKey: string;
      readonly currentManuscriptArtifactId: ArtifactId;
      readonly productionProfileArtifactId: ArtifactId;
    } & ({
      /** Initial writing consumes the committed source package only. */
      readonly mode: "initial";
      readonly revisionContextArtifactId?: never;
    } | {
      /** Rewrite writing consumes the exact ID-only revision context. */
      readonly mode: "rewrite";
      readonly revisionContextArtifactId: ArtifactId;
    }),
    context: MagazineWorkflowContext,
  ) => Promise<ArticleAttemptExecutionResult<WriterResult>>;
  /** Closed, source-blind writer for the opening editorial child. */
  readonly runEditorialWriter?: (
    input: {
      readonly editorialExecutionId: string;
      readonly operationKey: string;
      readonly currentManuscriptArtifactId: ArtifactId;
      readonly profileArtifactId: ArtifactId;
      readonly articleArtifactIds: readonly ArtifactId[];
      readonly mode?: "initial" | "rewrite";
      readonly revisionContextArtifactIds?: readonly ArtifactId[];
    },
    context: MagazineWorkflowContext,
  ) => Promise<import("../executors/closed-editorial-writer/result.ts").EditorialWriterExecutionResult>;
  /** Renderer-backed measurement for the current opening editorial revision. */
  readonly measureEditorial?: (input: {
    readonly editionId: "004";
    readonly editorialId: "opening";
    readonly manuscriptArtifactId: ArtifactId;
    readonly articleArtifactIds: readonly ArtifactId[];
    readonly measurementProfileArtifactId: ArtifactId;
    readonly maximumReaderPages: 1;
    readonly rendererIdentity?: RendererIdentity;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<ArticleAttemptExecutionResult<EditorialMeasurement>>;
  /** Source-blind editorial review over one exact manuscript revision. */
  readonly runEditorialReview?: (
    input: {
      readonly editionId: "004";
      readonly editorialId: "opening";
      readonly manuscriptArtifactId: ArtifactId;
      readonly reviewPlanArtifactId: ArtifactId;
      readonly measurementArtifactId: ArtifactId;
      readonly reviewCycleId: string;
    },
    context: MagazineWorkflowContext,
  ) => Promise<EditorialReviewExecutionResult>;
  /** Git-backed promotion of the exact accepted editorial revision. */
  readonly promoteEditorial?: (input: {
    readonly runId: RunId;
    readonly request: DurablePromotionRequest;
    readonly reviewer: string;
    readonly rationale: string;
    readonly decisionArtifactId: ArtifactId;
    readonly measurementArtifactId: ArtifactId;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<EditorialPromotionResult>;
  /** Closed, source-blind Spanish translation worker. */
  readonly runTranslationWriter?: (
    input: TranslationWriterInput,
    context: MagazineWorkflowContext,
  ) => Promise<TranslationWriterExecutionResult>;
  /** Git-backed promotion of one exact translated manuscript. */
  readonly promoteTranslation?: (input: {
    readonly runId: RunId;
    readonly pieceKind: "article" | "editorial";
    readonly pieceId: string;
    readonly language: string;
    readonly manuscriptArtifactId: ArtifactId;
    readonly englishArtifactId: ArtifactId;
    readonly promptArtifactId: ArtifactId;
    readonly inputArtifactIds: readonly ArtifactId[];
    readonly inputArtifactBindings: readonly { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef }[];
    readonly inputRevisions: readonly InputRevisionRef[];
    readonly expectedParentRevisionId: RevisionId | null;
    readonly decisionArtifactId: ArtifactId;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<TranslationPromotionResult>;
  /** Git-backed promotion of the exact root composition document. */
  readonly promoteComposition?: (input: {
    readonly runId: RunId;
    readonly compositionArtifactId: ArtifactId;
    readonly compositionId: string;
    readonly revisionId: RevisionId;
    readonly inputArtifactIds: readonly ArtifactId[];
    readonly inputRevisions: readonly InputRevisionRef[];
    readonly layoutInputBindings: readonly { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef }[];
    readonly decisionArtifactId: ArtifactId;
    readonly durableContext?: WorkflowDurableContext;
  }) => Promise<CompositionPromotionResult>;
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
  /** Number of writer rewrites already consumed by this execution. */
  readonly rewriteOrdinal?: number;
  readonly articleId: string;
  readonly editionId: string;
  readonly language: string;
  readonly logicalItem: Extract<DurableLogicalItem, { readonly kind: "article" }>;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly expectedParentRevisionId: RevisionId | null;
  readonly promotionId: PromotionId;
  /** Exact run-owned resolved profile envelope consumed by the closed writer. */
  readonly productionProfileArtifactId?: ArtifactId;
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
  readonly result?: ArticleWorkflowResult | ArticleWorkflowRouteResult;
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
