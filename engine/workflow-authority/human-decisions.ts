import type { ArtifactId, JsonObject, RunId } from "../contracts/index.ts";
import type {
  ArticleDecisionRequest,
  AuthenticatedHuman,
} from "../contracts/workflow-run.ts";
import type { WorkflowDurableContext } from "../workflows/internal-types.ts";
import { AuthorizedWorker } from "../authority/local-authority.ts";
import {
  ArtifactLedgerError,
  type ArtifactLedger,
  type LedgerDecision,
  type LedgerOffer,
} from "./artifact-ledger.ts";

export type HumanDecisionAuthorityOptions = {
  readonly ledger: ArtifactLedger;
  readonly clock?: { readonly now: () => Date };
};

/**
 * Validates exact active offers at the magazine boundary.  Loops only stores
 * the wait; it never decides who may answer or which immutable inputs are
 * being approved.
 */
export class HumanDecisionAuthority {
  readonly #ledger: ArtifactLedger;
  readonly #clock: { readonly now: () => Date };

  constructor(options: HumanDecisionAuthorityOptions) {
    this.#ledger = options.ledger;
    this.#clock = options.clock ?? { now: () => new Date() };
  }

  async decide(
    human: AuthenticatedHuman,
    request: ArticleDecisionRequest,
    durableContext?: WorkflowDurableContext,
  ): Promise<LedgerDecision> {
    if (!(human instanceof AuthorizedWorker)) {
      throw new ArtifactLedgerError(
        "HUMAN_AUTHORITY_REQUIRED",
        "A decision requires an AuthorizedWorker session minted by LocalAuthorityStore",
      );
    }
    const description = await human.describe();
    if (description.authority !== "human" || description.grantIds.length === 0) {
      throw new ArtifactLedgerError(
        "HUMAN_AUTHORITY_REQUIRED",
        "Only an authenticated human may answer an article decision offer",
      );
    }
    const existing = this.#ledger.getDecision(request.offerId);
    if (existing !== undefined) {
      if (
        existing.runId !== request.runId
        || existing.taskArtifactId !== request.taskArtifactId
        || !sameStrings(existing.inputArtifactIds, request.inputArtifactIds)
        || existing.choice !== request.choice
        || existing.rationale !== request.rationale.trim()
        || existing.principalId !== description.principalId
        || existing.credentialProfileId !== description.credentialProfileId
      ) {
        throw new ArtifactLedgerError("DECISION_ALREADY_RECORDED", `Offer ${request.offerId} already has a different decision`);
      }
      return existing;
    }
    const offer = this.#ledger.requireOffer(request.offerId);
    assertExactOffer(offer, request);
    const rationale = request.rationale.trim();
    if (rationale.length === 0) {
      throw new ArtifactLedgerError("DECISION_INVALID", "A human decision requires a rationale");
    }
    const artifactId = decisionArtifactId(request.offerId);
    this.#ledger.createArtifact({
      id: artifactId,
      kind: "article_human_decision",
      schemaVersion: "article-human-decision/1",
      mediaType: "application/json",
      origin: "human",
      payload: {
        kind: "json",
        value: {
          schemaVersion: "article-human-decision/1",
          offerId: request.offerId,
          taskArtifactId: request.taskArtifactId,
          inputArtifactIds: request.inputArtifactIds,
          principalId: description.principalId,
          credentialProfileId: description.credentialProfileId,
          choice: request.choice,
          rationale,
        },
      },
      parents: [
        { artifactId: request.taskArtifactId, relation: "decision_task" },
        ...request.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "decision_input" })),
      ],
      metadata: {
        offerId: request.offerId,
        principalId: description.principalId,
        choice: request.choice,
      },
      runId: request.runId,
      ...(durableContext === undefined ? {} : { durableContext }),
    });
    return this.#ledger.recordDecision({
      id: decisionRecordId(request.offerId),
      runId: request.runId,
      offerId: request.offerId,
      taskArtifactId: request.taskArtifactId,
      inputArtifactIds: request.inputArtifactIds,
      principalId: description.principalId,
      credentialProfileId: description.credentialProfileId,
      choice: request.choice,
      rationale,
      artifactId,
      createdAt: this.#clock.now().toISOString(),
    });
  }
}

function assertExactOffer(offer: LedgerOffer, request: ArticleDecisionRequest): void {
  if (offer.runId !== request.runId) {
    throw new ArtifactLedgerError("OFFER_RUN_MISMATCH", `Offer ${request.offerId} belongs to another run`);
  }
  if (offer.status !== "active") {
    throw new ArtifactLedgerError("OFFER_STALE", `Offer ${request.offerId} is no longer active`);
  }
  if (offer.taskArtifactId !== request.taskArtifactId) {
    throw new ArtifactLedgerError("OFFER_INPUT_MISMATCH", "Decision task is not the exact active task artifact");
  }
  if (!sameStrings(offer.inputArtifactIds, request.inputArtifactIds)) {
    throw new ArtifactLedgerError("OFFER_INPUT_MISMATCH", "Decision inputs are not the exact active input artifacts");
  }
  if (!offer.allowedChoices.includes(request.choice)) {
    throw new ArtifactLedgerError("CHOICE_INVALID", `Choice ${request.choice} is not allowed by the active offer`);
  }
}

export function decisionArtifactId(offerId: string): ArtifactId {
  return `art-decision-${safeIdentity(offerId)}` as ArtifactId;
}

export function decisionRecordId(offerId: string): string {
  return `decision-${safeIdentity(offerId)}`;
}

function safeIdentity(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9_.-]/gu, "_");
  return normalized.length > 180 ? normalized.slice(0, 180) : normalized;
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
