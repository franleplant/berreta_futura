import type { ArtifactId, PromotionId, RevisionId, RunId, RunView } from "../contracts/index.ts";
import type {
  ArticlePromotion,
} from "../contracts/workflow-run.ts";
import type { WorkflowDurableContext } from "../workflows/internal-types.ts";
import {
  DurableStore,
  type DurableCheckpointResult,
  type DurableGit,
  type DurablePromotionRequest,
} from "../durable/index.ts";
import {
  ArtifactLedgerError,
  type ArtifactLedger,
  type LedgerPromotion,
} from "./artifact-ledger.ts";

export interface DurablePromotionEvidenceSource {
  inspect(runId: RunId): Promise<RunView>;
  readArtifact(artifactId: ArtifactId): Promise<{
    readonly artifact: import("../contracts/index.ts").ArtifactView;
    readonly bytes: Uint8Array;
  }>;
}

export type DurableArticlePromotionSink = {
  promote(input: {
    readonly request: DurablePromotionRequest;
    readonly reviewer: string;
    readonly rationale: string;
  }): Promise<DurableCheckpointResult["result"]>;
};

/** Real Git-backed promotion adapter. It has no fabricated revision fallback. */
export class DurableStoreArticlePromotionSink implements DurableArticlePromotionSink {
  readonly #store: DurableStore;
  readonly #evidence: DurablePromotionEvidenceSource;

  constructor(options: {
    readonly repositoryRoot: string;
    readonly workRoot: string;
    readonly git: DurableGit;
    readonly evidence: DurablePromotionEvidenceSource;
  }) {
    this.#store = new DurableStore({
      repositoryRoot: options.repositoryRoot,
      workRoot: options.workRoot,
      git: options.git,
    });
    this.#evidence = options.evidence;
  }

  async promote(input: {
    readonly request: DurablePromotionRequest;
    readonly reviewer: string;
    readonly rationale: string;
  }): Promise<DurableCheckpointResult["result"]> {
    const result = await this.#store.promote(this.#evidence, input.request);
    return result.result;
  }
}

export type ArticlePromotionRequest = {
  readonly runId: RunId;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly decisionArtifactId: ArtifactId;
  readonly reviewer: string;
  readonly rationale: string;
  readonly request: DurablePromotionRequest;
  readonly durableContext?: WorkflowDurableContext;
};

export type ArticlePromotionAuthorityOptions = {
  readonly ledger: ArtifactLedger;
  readonly sink: DurableArticlePromotionSink;
  readonly clock?: { readonly now: () => Date };
};

export class ArticlePromotionAuthority {
  readonly #ledger: ArtifactLedger;
  readonly #sink: DurableArticlePromotionSink;
  readonly #clock: { readonly now: () => Date };

  constructor(options: ArticlePromotionAuthorityOptions) {
    this.#ledger = options.ledger;
    this.#sink = options.sink;
    this.#clock = options.clock ?? { now: () => new Date() };
  }

  async promote(request: ArticlePromotionRequest): Promise<ArticlePromotion> {
    const run = this.#ledger.requireRun(request.runId);
    const decisionArtifactId = request.request.decisionArtifactIds[0];
    const decision = decisionArtifactId === undefined
      ? undefined
      : this.#ledger.getDecisionByArtifactId(request.runId, decisionArtifactId);
    if (decision === undefined) {
      throw new ArtifactLedgerError("PROMOTION_INVALID", "Durable promotion decision artifact does not match the accepted offer");
    }
    const decisionEvidence = request.request.decisionEvidenceArtifactIds ?? decision.inputArtifactIds;
    if (!sameStrings(decisionEvidence, decision.inputArtifactIds)) {
      throw new ArtifactLedgerError("PROMOTION_INVALID", "Durable promotion evidence does not match the answered decision");
    }
    if (decision.choice !== "accept") {
      throw new ArtifactLedgerError("ARTICLE_NOT_ACCEPTED", `Article ${run.articleId} was not accepted`);
    }
    if (
      request.request.runId !== request.runId ||
      request.request.acceptedArtifactIds.length !== 1 ||
      request.request.acceptedArtifactIds[0] !== run.manuscriptArtifactId ||
      request.request.decisionArtifactIds.length !== 1 ||
      request.request.decisionArtifactIds[0] !== decision.artifactId ||
      request.request.logicalItem.kind !== "article" ||
      request.request.logicalItem.editionId !== run.editionId
    ) {
      throw new ArtifactLedgerError("PROMOTION_INVALID", "Durable promotion request is not bound to the exact article facts");
    }
    const reviewer = request.reviewer.trim();
    const rationale = request.rationale.trim();
    if (reviewer.length === 0 || rationale.length === 0) {
      throw new ArtifactLedgerError("PROMOTION_INVALID", "Durable promotion requires reviewer and rationale");
    }
    const existing = this.#ledger.getPromotion(request.runId);
    if (existing !== undefined) return toPublicPromotion(existing);
    const promoted = await this.#sink.promote({ request: request.request, reviewer, rationale });
    validatePromotionResult(request.request, promoted);
    const promotionArtifactId = `art-promotion-${safeIdentity(request.runId)}` as ArtifactId;
    this.#ledger.createArtifact({
      id: promotionArtifactId,
      kind: "article_durable_promotion",
      schemaVersion: "article-durable-promotion/1",
      mediaType: "application/json",
      origin: "machine",
      payload: {
        kind: "json",
        value: {
          schemaVersion: "article-durable-promotion/1",
          promotionId: request.request.promotionId,
          durableRevisionId: promoted.revisionId,
          manifestDigest: promoted.manifestDigest,
          gitCommitOid: promoted.gitCommitOid,
          gitBlobOids: promoted.gitBlobOids,
          runId: request.runId,
          articleId: run.articleId,
          manuscriptArtifactId: run.manuscriptArtifactId,
          measurementArtifactId: request.measurementArtifactId,
          decisionArtifactId: decision.artifactId,
          reviewer,
          rationale,
        },
      },
      parents: decisionEvidence.map((artifactId) => ({ artifactId, relation: "decision_evidence" })),
      metadata: {
        promotionId: request.request.promotionId,
        durableRevisionId: promoted.revisionId,
        decisionEvidenceArtifactIds: decisionEvidence as unknown as import("../contracts/index.ts").JsonValue,
      },
      runId: request.runId,
      ...(request.durableContext === undefined ? {} : { durableContext: request.durableContext }),
    });
    const result: LedgerPromotion = {
      promotionId: request.request.promotionId,
      runId: request.runId,
      articleId: run.articleId,
      manuscriptArtifactId: run.manuscriptArtifactId,
      measurementArtifactId: request.measurementArtifactId,
      decisionArtifactId: decision.artifactId,
      reviewer,
      rationale,
      durableRevisionId: promoted.revisionId,
      manifestDigest: promoted.manifestDigest,
      gitCommitOid: promoted.gitCommitOid,
      gitBlobOids: promoted.gitBlobOids,
      revisionId: request.request.revisionId,
      expectedParentRevisionId: request.request.expectedParentRevisionId,
      inputRevisions: inputRevisions(request.request) as readonly import("../contracts/index.ts").JsonObject[],
      acceptedArtifactIds: request.request.acceptedArtifactIds,
      decisionArtifactIds: request.request.decisionArtifactIds,
      inputArtifactIds: inputArtifactIds(request.request),
      createdAt: this.#clock.now().toISOString(),
    };
    return toPublicPromotion(this.#ledger.recordPromotion(result));
  }
}

function toPublicPromotion(value: LedgerPromotion): ArticlePromotion {
  return {
    promotionId: value.promotionId as PromotionId,
    runId: value.runId,
    articleId: value.articleId,
    manuscriptArtifactId: value.manuscriptArtifactId,
    measurementArtifactId: value.measurementArtifactId,
    decisionArtifactId: value.decisionArtifactId,
    reviewer: value.reviewer,
    rationale: value.rationale,
    durableRevisionId: value.durableRevisionId as RevisionId,
    manifestDigest: value.manifestDigest,
    gitCommitOid: value.gitCommitOid,
    gitBlobOids: value.gitBlobOids,
    createdAt: value.createdAt,
  };
}

function safeIdentity(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9_.-]/gu, "_");
  return normalized.length > 160 ? normalized.slice(0, 160) : normalized;
}

function inputArtifactIds(request: DurablePromotionRequest): readonly ArtifactId[] {
  return request.inputBindings?.map((binding) => binding.artifactId) ?? request.inputArtifactIds ?? [];
}

function inputRevisions(request: DurablePromotionRequest): readonly import("../durable/types.ts").InputRevisionRef[] {
  if (request.inputRevisions !== undefined) return request.inputRevisions;
  const seen = new Set<string>();
  return (request.inputBindings ?? []).flatMap((binding) => {
    const revision = binding.revision;
    const key = `${revision.kind}:${revision.editionId ?? ""}:${revision.logicalId}:${revision.revisionId}`;
    if (seen.has(key)) return [];
    seen.add(key);
    return [revision];
  });
}

function validatePromotionResult(
  request: DurablePromotionRequest,
  result: DurableCheckpointResult["result"],
): void {
  if (
    result.promotionId !== request.promotionId ||
    result.revisionId !== request.revisionId ||
    JSON.stringify(result.logicalItem) !== JSON.stringify(request.logicalItem) ||
    result.expectedParentRevisionId !== request.expectedParentRevisionId ||
    !sameStrings(result.acceptedArtifactIds, request.acceptedArtifactIds) ||
    !sameStrings(result.decisionArtifactIds, request.decisionArtifactIds) ||
    !sameStrings(result.inputArtifactIds, inputArtifactIds(request)) ||
    JSON.stringify(result.revisionRef) !== JSON.stringify({ ...request.logicalItem, revisionId: request.revisionId })
  ) {
    throw new ArtifactLedgerError("PROMOTION_RESPONSE_MISMATCH", "Durable promotion response does not match the exact request");
  }
  if (!/^sha256:[0-9a-f]{64}$/u.test(result.manifestDigest)) {
    throw new ArtifactLedgerError("PROMOTION_RESPONSE_INVALID", "Durable promotion response has an invalid manifest digest");
  }
  if (!/^[0-9a-f]{40}$/u.test(result.gitCommitOid) || Object.values(result.gitBlobOids).some((oid) => !/^[0-9a-f]{40}$/u.test(oid))) {
    throw new ArtifactLedgerError("PROMOTION_RESPONSE_INVALID", "Durable promotion response has an invalid Git binding");
  }
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
