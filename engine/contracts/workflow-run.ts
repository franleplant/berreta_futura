import type { ArticleExecutionId, ArtifactId, PromotionId, RevisionId, RunId } from "./ids.ts";
import type { JsonObject } from "./json.ts";
import type { InputRevisionRef, DurableLogicalItem } from "../durable/types.ts";

export type ArticleHumanChoice = "accept" | "revise" | "drop";

/** One immutable source/input identity approved by an article run. */
export type ArticleInputBinding = {
  readonly artifactId: ArtifactId;
  readonly revision: InputRevisionRef;
};

export type ArticleWorkflowStatus =
  | "running"
  | "waiting"
  | "complete"
  | "dropped"
  | "failed";

/**
 * Caller-owned renderer executables. Paths are operational handles only and
 * must never be persisted in a run, artifact, profile, or manifest.
 */
export type RendererToolchainResource = {
  readonly uvExecutable: string;
  readonly pythonExecutable: string;
  readonly expected: {
    readonly uvSha256: `sha256:${string}`;
    readonly uvVersion: string;
    readonly pythonSha256: `sha256:${string}`;
    readonly pythonVersion: string;
    readonly pythonImplementation: string;
    readonly pythonCacheTag: string;
    readonly platform: `${NodeJS.Platform}-${string}`;
  };
};

/**
 * All article inputs are immutable artifacts. The workflow never imports a
 * raw manuscript string. `manuscriptArtifactId` names the immutable seed; the
 * first durable step derives the run-owned manuscript that is measured and
 * promoted. Input artifacts and their Git revisions travel as one exact list
 * of bindings so the two lists cannot drift apart.
 */
export type ArticleStartRequest = {
  readonly runId?: RunId;
  /** Optional stable magazine identity. It must not be derived from the Loops root run. */
  readonly articleExecutionId?: ArticleExecutionId;
  readonly articleId: string;
  readonly editionId: string;
  readonly logicalItem: Extract<DurableLogicalItem, { readonly kind: "article" }>;
  readonly language: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly inputBindings: readonly ArticleInputBinding[];
  readonly expectedParentRevisionId: RevisionId | null;
  /** Optional caller hint. The public engine generates this identity when omitted. */
  readonly promotionId?: PromotionId;
  /** Optional caller hint. The public engine generates this identity when omitted. */
  readonly revisionId?: RevisionId;
};

export type ArticleDecisionAnswer = {
  readonly decisionArtifactId: ArtifactId;
};

export type ArticleWorkflowResult = {
  readonly schemaVersion: "magazine-article-workflow-result/1";
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly status: Exclude<ArticleWorkflowStatus, "running" | "waiting">;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly decisionArtifactId: ArtifactId;
  readonly promotionId?: PromotionId;
  readonly durableRevisionId?: RevisionId;
};

export type ArticleOfferView = {
  readonly id: string;
  readonly runId: RunId;
  readonly role: "article_decision";
  readonly status: "active" | "answered";
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly allowedChoices: readonly ArticleHumanChoice[];
  readonly createdAt: string;
  readonly waitId?: string;
  readonly decisionArtifactId: ArtifactId;
};

export type ArticleWorkflowView = {
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly editionId: string;
  readonly status: ArticleWorkflowStatus;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly measurementArtifactId?: ArtifactId;
  readonly decisionArtifactId?: ArtifactId;
  readonly promotionId?: PromotionId;
  readonly durableRevisionId?: RevisionId;
  readonly activeOffer?: ArticleOfferView;
  readonly artifacts: readonly ArtifactId[];
  readonly loopsRunId: string;
  readonly loopsWorkflowVersion: string;
  readonly workflowPin?: JsonObject;
  readonly error?: string;
};

/** A real authenticated session minted by LocalAuthorityStore. */
export type AuthenticatedHuman = import("../authority/local-authority.ts").AuthorizedWorker;

export type ArticleDecisionRequest = {
  readonly runId: RunId;
  readonly offerId: string;
  readonly taskArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly choice: ArticleHumanChoice;
  readonly rationale: string;
  /** Canonical review finding IDs explicitly approved by an editor. */
  readonly approvedFindingIds?: readonly string[];
  /** Additional writer rewrites granted by an editor. */
  readonly additionalRewriteBudget?: number;
};

/** A typed handoff until the next article rewrite-loop slice is available. */
export type ArticleWorkflowRouteResult = {
  readonly schemaVersion: "magazine-article-route-result/1";
  readonly runId: RunId;
  readonly articleExecutionId: ArticleExecutionId;
  readonly articleId: string;
  readonly status: "rewrite_pending";
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly revisionBriefArtifactId: ArtifactId;
  readonly routeArtifactId: ArtifactId;
  readonly route: JsonObject;
};

export type ArticlePromotion = {
  readonly promotionId: PromotionId;
  readonly runId: RunId;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly decisionArtifactId: ArtifactId;
  readonly reviewer: string;
  readonly rationale: string;
  readonly durableRevisionId: RevisionId;
  readonly manifestDigest: string;
  readonly gitCommitOid: string;
  readonly gitBlobOids: Readonly<Record<string, string>>;
  readonly createdAt: string;
};

export type MagazineWorkflowEngineOptions = {
  readonly databasePath: string;
  readonly loopsDatabasePath: string;
  readonly projectRoot: string;
  readonly repositoryRoot: string;
  readonly workRoot: string;
  readonly renderer: {
    readonly workDirectory: string;
    readonly projectRoot?: string;
    readonly timeoutMs?: number;
    readonly toolchain: RendererToolchainResource;
  };
  readonly clock?: { readonly now: () => Date };
  /** Authenticated, role-specific workers for the durable article review panel. */
  readonly articleReviewWorkers?: {
    readonly sourceAwareReviewer: import("../authority/local-authority.ts").AuthorizedWorker;
    readonly sourceBlindReviewer: import("../authority/local-authority.ts").AuthorizedWorker;
    readonly measurementTool: import("../authority/local-authority.ts").AuthorizedWorker;
  };
  /** Owner-private OpenAI credential resource used by the closed reviewer. */
  readonly articleReviewCredentials?: import("../executors/closed-writer/credentials.ts").ClosedWriterCredentialResource;
  /** Operational lease time is separate from the domain timestamp clock. */
  readonly attemptClock?: import("../workflow-authority/artifact-ledger.ts").OperationalLeaseClock;
};
