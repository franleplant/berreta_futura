import type { ArtifactSeed } from "./artifact.ts";
import type {
  ActorId,
  ArtifactId,
  DecisionId,
  EventId,
  RunId,
  WorkOfferId,
} from "./ids.ts";
import type { JsonObject, JsonValue } from "./json.ts";
import type {
  ProductionDependency,
  SourceAssignmentPolicy,
} from "./production-plan.ts";
import type { WorkOfferView } from "./work.ts";
import type { DurableRevisionRef, InputRevisionRef } from "../durable/types.ts";

export const ARTICLE_LENSES = [
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
] as const;

export type JudgeLens = (typeof ARTICLE_LENSES)[number];

export type ModelChoice = {
  readonly adapter: string;
  readonly model: string;
  readonly reasoningEffort?: string;
  readonly settings?: JsonObject;
};

export type ModelPolicy = {
  readonly default: ModelChoice;
  readonly roles?: Readonly<Record<string, ModelChoice>>;
};

export type ArticlePolicy = {
  readonly maxIterations: number;
  readonly maximumReaderPages: number;
  readonly teaching: "applicable" | "not_applicable";
  readonly enabledLenses: readonly JudgeLens[];
  readonly blockingLenses: readonly JudgeLens[];
};

export type ArticleContentMode =
  | "faithful_edit"
  | "faithful_synthesis"
  | "original_synthesis";

export type ArticleAttribution =
  | {
      readonly kind: "source_author";
      readonly byline: string;
      readonly sourceAuthors: readonly string[];
      readonly sourceIds: readonly string[];
    }
  | {
      readonly kind: "magazine";
      readonly byline: string;
    };

export type ArticleRunSpec = {
  /** Edition identity is supplied by EditionMachine when this is a child actor. */
  readonly editionId?: string;
  readonly articleId: string;
  readonly contentMode: ArticleContentMode;
  readonly attribution: ArticleAttribution;
  readonly editionContext?: ArtifactId;
  readonly articleBrief: ArtifactId;
  readonly sources: readonly ArtifactId[];
  /** Human source-review decisions, ordered to match `sources` when supplied. */
  readonly sourceApprovalArtifacts: readonly ArtifactId[];
  readonly writerPrompt: ArtifactId;
  /** Immutable writer policy records, supplied in this exact order when present. */
  readonly contentModeArtifact?: ArtifactId;
  readonly attributionArtifact?: ArtifactId;
  readonly editorialPolicyArtifact?: ArtifactId;
  readonly modelPolicyArtifact?: ArtifactId;
  readonly judgePrompts: Readonly<Partial<Record<JudgeLens, ArtifactId>>>;
  readonly writingRules: ArtifactId;
  readonly measurementProfileArtifact?: ArtifactId;
  readonly measurementInputArtifacts?: readonly ArtifactId[];
  /** Git-bound inputs that must be pinned into the resulting DurableRevision. */
  readonly inputRevisions?: readonly InputRevisionRef[];
  /** Exact prior DurableRevision, if this fresh manuscript supersedes one. */
  readonly durableParentRevisionId?: import("./ids.ts").RevisionId;
  readonly initialManuscript?: ArtifactId;
  readonly policy: ArticlePolicy;
  readonly modelPolicy: ModelPolicy;
};

/**
 * An edition's configured article binds stable source identities only. Exact
 * extraction and review-decision artifacts are resolved after collection.
 */
export type PreplannedArticleRunSpec = Omit<
  ArticleRunSpec,
  "sources" | "sourceApprovalArtifacts"
> & {
  readonly sourceIds: readonly string[];
};

export type SourceRunSpec = {
  readonly sourceId: string;
  readonly leadArtifact: ArtifactId;
  readonly captureProfileArtifact?: ArtifactId;
  readonly captureInputArtifacts?: readonly ArtifactId[];
  readonly rawBundleArtifact?: ArtifactId;
  readonly rawEvidenceArtifacts?: readonly ArtifactId[];
  readonly extractionArtifact?: ArtifactId;
  readonly metadataArtifact?: ArtifactId;
  /** Immutable human source-review decision that approved this prepared source. */
  readonly approvalArtifact?: ArtifactId;
};

export type SubmitLeadRequest = {
  readonly source: SourceRunSpec;
  readonly artifacts: readonly ArtifactSeed[];
};

export type EditorialRunSpec = {
  readonly editionId?: string;
  readonly editorialId: string;
  readonly briefArtifact: ArtifactId;
  readonly writingRules: ArtifactId;
  readonly articleArtifacts?: readonly ArtifactId[];
  readonly initialManuscript?: ArtifactId;
  /** Git-bound inputs that must be pinned into the resulting DurableRevision. */
  readonly inputRevisions?: readonly InputRevisionRef[];
  /** Exact prior DurableRevision, if this fresh editorial supersedes one. */
  readonly durableParentRevisionId?: import("./ids.ts").RevisionId;
  readonly modelPolicy: ModelPolicy;
};

export type TranslationRunSpec = {
  /** Edition identity is supplied by EditionMachine when this is a child actor. */
  readonly editionId?: string;
  /** One translation actor owns one exact English article or opening editorial. */
  readonly pieceKind: "article" | "editorial";
  readonly pieceId: string;
  readonly language: string;
  readonly sourceLanguage: string;
  /** Exactly one current source-piece artifact, retained as an array for task compatibility. */
  readonly englishArtifacts: readonly ArtifactId[];
  readonly promptArtifact: ArtifactId;
  readonly measurementProfileArtifact?: ArtifactId;
  readonly measurementInputArtifacts?: readonly ArtifactId[];
  /** Git-bound inputs that must be pinned into the resulting DurableRevision. */
  readonly inputRevisions?: readonly InputRevisionRef[];
  /** Exact prior DurableRevision for this language and piece. */
  readonly durableParentRevisionId?: import("./ids.ts").RevisionId;
  readonly initialTranslationArtifacts?: readonly ArtifactId[];
  readonly maximumReaderPages: number;
  readonly modelPolicy: ModelPolicy;
};

export type RegisteredArtSpec = {
  readonly editionId?: string;
  readonly key: string;
  readonly role: "cover" | "interior";
  readonly artifactId?: ArtifactId;
  readonly briefArtifact: ArtifactId;
  readonly required: boolean;
  readonly dependencies?: ProductionDependency;
  readonly dependencyArtifacts?: readonly ArtifactId[];
};

export type RenderRunSpec = {
  readonly renderManifestArtifact: ArtifactId;
  readonly compositionRevisionArtifact?: ArtifactId;
  readonly compositionId?: string;
  readonly rendererContractVersion: string;
  readonly printerProfileArtifact?: ArtifactId;
  /** Git-bound layout and renderer inputs pinned by a CompositionRevision. */
  readonly layoutInputRevisions?: readonly InputRevisionRef[];
  readonly configuredLanguages: readonly string[];
  /** Preselected immutable art, bound directly without any art-machine offer. */
  readonly selectedArtArtifacts?: readonly ArtifactId[];
  /** Exact durable image revisions corresponding to preselected art artifacts. */
  readonly selectedArtRevisions?: readonly Extract<DurableRevisionRef, { readonly kind: "image" }>[];
  readonly studioPolicy:
    | "not_applicable"
    | "home_ready_studio_blocked"
    | "require_ready_preflight";
};

export type ReleaseRunSpec = {
  readonly publicationArtifact: ArtifactId;
  readonly sourceArtifacts: readonly ArtifactId[];
  readonly dryRun: boolean;
  readonly target: "press" | "private" | "web";
  readonly printerProfileArtifact?: ArtifactId;
  readonly printerPreflightArtifacts?: readonly ArtifactId[];
  readonly studioReady?: boolean;
};

/**
 * Selects the immutable starting authority for an edition run. A normal
 * production run begins with the configured collection and production plan.
 * A bootstrap run instead starts from one committed CompositionRevision named
 * by its exact run-bootstrap input revision, and can only stop before release.
 */
export type EditionExecution =
  | { readonly kind: "produce" }
  | {
      readonly kind: "bootstrap_composition";
      readonly bootstrapRevision: Extract<
        InputRevisionRef,
        { readonly kind: "run_bootstrap" }
      >;
      readonly postRender: "stop_unreleased";
    };

export type EditionRunSpec = {
  readonly editionId: string;
  readonly execution: EditionExecution;
  readonly editionBrief: ArtifactId;
  readonly planningArtifact?: ArtifactId;
  readonly sourceAssignmentPolicy?: SourceAssignmentPolicy;
  readonly sources: readonly SourceRunSpec[];
  /** Configured articles use sourceIds; legacy resolved articles are normalized at collection. */
  readonly articles: readonly (PreplannedArticleRunSpec | ArticleRunSpec)[];
  readonly editorial: EditorialRunSpec;
  readonly translations: readonly TranslationRunSpec[];
  readonly art: readonly RegisteredArtSpec[];
  readonly render: RenderRunSpec;
  readonly release: ReleaseRunSpec;
  readonly modelPolicy: ModelPolicy;
};

type BaseRunSpec = {
  readonly schemaVersion: 1;
  readonly artifacts: readonly ArtifactSeed[];
  readonly metadata?: JsonObject;
};

export type ArticleRootRunSpec = BaseRunSpec & {
  readonly kind: "article";
  readonly article: ArticleRunSpec;
};

export type EditionRootRunSpec = BaseRunSpec & {
  readonly kind: "edition";
  readonly edition: EditionRunSpec;
};

export type RunSpec = ArticleRootRunSpec | EditionRootRunSpec;

export type RunInputChange =
  | { readonly kind: "replace_artifact"; readonly from: ArtifactId; readonly to: ArtifactSeed }
  | { readonly kind: "replace_spec"; readonly path: string; readonly value: JsonValue };

export type ArticlePromotionRequest = {
  readonly reviewer: string;
  readonly rationale: string;
  readonly comparedRunIds: readonly RunId[];
};

export type ArticlePromotionView = {
  readonly id: string;
  readonly runId: RunId;
  readonly selectedArtifactId: ArtifactId;
  readonly policyArtifactId: ArtifactId;
  readonly reviewer: string;
  readonly rationale: string;
  readonly comparedRunIds: readonly RunId[];
  readonly createdAt: string;
};

export type RunStatus =
  | "awaiting_editor"
  | "complete"
  | "escalated"
  | "failed"
  | "running"
  | "waiting";

export type RunOutcome =
  | { readonly status: "running"; readonly runId: RunId }
  | { readonly status: "waiting"; readonly runId: RunId; readonly offers: readonly WorkOfferView[] }
  | { readonly status: "awaiting_editor"; readonly runId: RunId; readonly offers: readonly WorkOfferView[] }
  | { readonly status: "complete"; readonly runId: RunId; readonly outputs: readonly ArtifactId[] }
  | { readonly status: "escalated"; readonly runId: RunId; readonly actors: readonly ActorId[] }
  | { readonly status: "failed"; readonly runId: RunId; readonly failures: readonly FailureView[] };

export type FailureView = {
  readonly actorId?: ActorId;
  readonly message: string;
  readonly classification: string;
};

export type EventView = {
  readonly id: EventId;
  readonly sequence: number;
  readonly actorId: ActorId;
  readonly type: string;
  readonly payload: JsonObject;
  readonly previousState?: string;
  readonly nextState: string;
  readonly causationEventId?: EventId;
  readonly recordedAt: string;
};

export type DecisionView = {
  readonly id: DecisionId;
  readonly actorId: ActorId;
  readonly offerId?: WorkOfferId;
  readonly subjectArtifactId?: ArtifactId;
  readonly principalId: string;
  readonly choice: string;
  readonly authority: string;
  readonly artifactId?: ArtifactId;
  readonly authorizationId?: string;
  readonly details: JsonObject;
  readonly createdAt: string;
};
