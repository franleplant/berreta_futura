import { parse } from "yaml";

import type { AuthorizedWorker } from "./authority/local-authority.ts";
import type {
  AnswerArtifact,
  ArtifactId,
  JsonObject,
  RunId,
  WorkAnswer,
  WorkClaim,
  WorkOfferId,
  WorkOfferView,
} from "./contracts/index.ts";
import type { RunEngine } from "./run-engine/index.ts";

export class CooperativeModelBridgeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CooperativeModelBridgeError";
  }
}

export type CooperativeClaim = {
  readonly schemaVersion: "cooperative-model-claim/1";
  readonly runId: RunId;
  readonly offerId: WorkOfferId;
  readonly claim: WorkClaim;
};

type CooperativeEngine = Pick<RunEngine, "inspect" | "claimAuthorized" | "heartbeat" | "answer">;

/**
 * Narrow public worker bridge for one model offer. It keeps the RunEngine
 * claim/fence as the authority and translates human-readable Markdown/YAML
 * replies into the immutable answer envelope expected by that offer.
 */
export class CooperativeModelBridge {
  private readonly engine: CooperativeEngine;

  constructor(engine: CooperativeEngine) {
    this.engine = engine;
  }

  async claim(
    runId: RunId,
    offerId: WorkOfferId,
    worker: AuthorizedWorker,
  ): Promise<CooperativeClaim> {
    const view = await this.engine.inspect(runId);
    const offer = view.offers.find((candidate) => candidate.id === offerId);
    if (offer === undefined || offer.status !== "offered") {
      throw new CooperativeModelBridgeError(`offer ${offerId} is not currently available`);
    }
    if (!offer.allowedWorkerCapabilities.includes("text_model")) {
      throw new CooperativeModelBridgeError(`offer ${offerId} is not a text-model offer`);
    }
    const identity = await worker.describe();
    if (identity.authority !== "model" || !identity.capabilities.includes("text_model")) {
      throw new CooperativeModelBridgeError("an authenticated model credential with text_model capability is required");
    }
    const claim = await worker.claim(this.engine, offerId);
    return { schemaVersion: "cooperative-model-claim/1", runId, offerId, claim };
  }

  async heartbeat(ticket: CooperativeClaim): Promise<CooperativeClaim> {
    const claim = await this.engine.heartbeat(ticket.claim);
    return { ...ticket, claim };
  }

  async answerMarkdown(ticket: CooperativeClaim, markdown: string): Promise<void> {
    const offer = await this.offer(ticket);
    await this.engine.answer(ticket.claim, markdownAnswer(offer, markdown));
  }

  async answerYaml(ticket: CooperativeClaim, yaml: string): Promise<void> {
    const offer = await this.offer(ticket);
    await this.engine.answer(ticket.claim, yamlAnswer(offer, yaml));
  }

  private async offer(ticket: CooperativeClaim): Promise<WorkOfferView> {
    const view = await this.engine.inspect(ticket.runId);
    const offer = view.offers.find((candidate) => candidate.id === ticket.offerId);
    if (offer === undefined || offer.status !== "claimed" || offer.activeAttemptId !== ticket.claim.attemptId) {
      throw new CooperativeModelBridgeError(`claim ${ticket.claim.attemptId} is stale`);
    }
    return offer;
  }
}

function markdownAnswer(offer: WorkOfferView, markdown: string): WorkAnswer {
  if (!new Set(["writer", "editorial_writer", "translation_writer"]).has(offer.role)) {
    throw new CooperativeModelBridgeError(`${offer.role} requires a YAML judgment reply`);
  }
  if (!markdown.trim()) throw new CooperativeModelBridgeError("Markdown reply is empty");
  const artifact: AnswerArtifact = {
    kind: offer.role === "writer"
      ? "article_manuscript"
      : offer.role === "editorial_writer"
        ? "editorial_manuscript"
        : "translated_piece",
    schemaVersion: offer.contractVersion,
    mediaType: "text/markdown",
    payload: { kind: "text", text: markdown },
    parents: offer.inputArtifacts.map((artifactId) => ({ artifactId, relation: "model_input" })),
    metadata: {
      cooperative: true,
      role: offer.role,
      inputArtifactIds: offer.inputArtifacts,
      rendererTargetPath: rendererTargetPath(offer),
    },
  };
  const workingNotes: AnswerArtifact | undefined = offer.role === "writer"
    ? {
      kind: "writer_working_notes",
      schemaVersion: offer.contractVersion,
      mediaType: "text/markdown",
      payload: { kind: "text", text: "Cooperative model submitted the manuscript." },
      parents: offer.inputArtifacts.map((artifactId) => ({ artifactId, relation: "model_input" })),
      metadata: { cooperative: true, role: offer.role, inputArtifactIds: offer.inputArtifacts },
    }
    : undefined;
  return {
    contractVersion: offer.contractVersion,
    result: { status: "complete" },
    artifacts: workingNotes === undefined ? [artifact] : [artifact, workingNotes],
    metadata: { cooperative: true },
  };
}

function yamlAnswer(offer: WorkOfferView, yaml: string): WorkAnswer {
  if (new Set(["writer", "editorial_writer", "translation_writer"]).has(offer.role)) {
    throw new CooperativeModelBridgeError(`${offer.role} requires a Markdown manuscript reply`);
  }
  let decoded: unknown;
  try {
    decoded = parse(yaml);
  } catch (error) {
    throw new CooperativeModelBridgeError(`YAML reply is invalid: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!isObject(decoded)) throw new CooperativeModelBridgeError("YAML judgment must be a mapping");
  const result = decoded as JsonObject;
  const kind = `${offer.role}_judgment`;
  return {
    contractVersion: offer.contractVersion,
    result,
    artifacts: [{
      kind,
      schemaVersion: offer.contractVersion,
      mediaType: "application/yaml",
      payload: { kind: "text", text: yaml },
      parents: offer.inputArtifacts.map((artifactId) => ({ artifactId, relation: "model_input" })),
      metadata: { cooperative: true, role: offer.role, inputArtifactIds: offer.inputArtifacts },
    }],
    metadata: { cooperative: true },
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rendererTargetPath(offer: WorkOfferView): string {
  const root = "editions/004-the-systems-around-the-model";
  if (offer.role === "editorial_writer") return `${root}/manuscript/editorial.md`;
  if (offer.role === "writer") {
    const articleId = offer.actorKey.startsWith("article:") ? offer.actorKey.slice("article:".length) : undefined;
    if (articleId === undefined || !articleId) throw new CooperativeModelBridgeError("writer offer has no article identity");
    return `${root}/articles/${articleId}.md`;
  }
  if (offer.role === "translation_writer") {
    const parts = offer.actorKey.split(":");
    const language = parts[1];
    const kind = parts[2];
    const pieceId = parts[3];
    if (language === undefined || kind === undefined || pieceId === undefined) {
      throw new CooperativeModelBridgeError("translation offer has no piece identity");
    }
    return kind === "editorial"
      ? `${root}/translations/${language}/editorial.md`
      : `${root}/translations/${language}/articles/${pieceId}.md`;
  }
  throw new CooperativeModelBridgeError(`no renderer target is defined for ${offer.role}`);
}
