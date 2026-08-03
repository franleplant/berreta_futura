import type {
  WorkAnswer,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import {
  DurableStore,
  type DurablePromotionRequest,
} from "../durable/index.ts";
import type { RunEngine } from "../run-engine/index.ts";
import { permanentAdapterError } from "./adapter-workspace.ts";
import type { Executor, ExecutorContext } from "./types.ts";

export type DurableCheckpointImplementation = {
  checkpoint(context: ExecutorContext): Promise<WorkAnswer>;
};

type PromotionRunEngine = Pick<RunEngine, "inspect" | "readArtifact">;

/** Connects the durable worker offer to the one Git-backed promotion seam. */
export class DurableStoreCheckpointImplementation implements DurableCheckpointImplementation {
  private readonly engine: PromotionRunEngine;
  private readonly store: DurableStore;

  constructor(
    engine: PromotionRunEngine,
    store: DurableStore,
  ) {
    this.engine = engine;
    this.store = store;
  }

  async checkpoint(context: ExecutorContext): Promise<WorkAnswer> {
    if (context.signal.aborted) {
      throw permanentAdapterError("durable checkpoint was canceled before promotion");
    }
    let decoded: unknown;
    try {
      decoded = JSON.parse(await context.artifacts.readText(context.offer.taskArtifactId));
    } catch {
      throw permanentAdapterError("durable checkpoint task is not valid JSON");
    }
    if (!isPromotionRequest(decoded) || decoded.runId !== context.offer.runId) {
      throw permanentAdapterError("durable checkpoint task does not match its offered run");
    }
    return this.store.promote(this.engine, decoded);
  }
}

/**
 * A narrow promotion seam. It only handles the immutable checkpoint offer and
 * deliberately delegates repository writes to an injected implementation.
 */
export class DurableCheckpointExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities = ["subprocess"] as const;

  constructor(
    implementation: DurableCheckpointImplementation,
    options: { readonly id?: string; readonly principalId?: string } = {},
  ) {
    this.implementation = implementation;
    this.id = options.id ?? "durable-checkpoint";
    this.worker = {
      principalId: options.principalId ?? this.id,
      authority: "tool",
      capabilities: this.capabilities,
      displayName: "Durable revision checkpoint",
    };
  }

  private readonly implementation: DurableCheckpointImplementation;

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "durable_checkpoint";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    const answer = await this.implementation.checkpoint(context);
    if (answer.contractVersion !== "durable-checkpoint/1") {
      throw permanentAdapterError("durable checkpoint implementation returned the wrong contract");
    }
    return answer;
  }
}

function isPromotionRequest(value: unknown): value is DurablePromotionRequest {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const request = value as Record<string, unknown>;
  return request.schemaVersion === "durable-checkpoint-request/1" &&
    typeof request.promotionId === "string" &&
    typeof request.revisionId === "string" &&
    typeof request.runId === "string" &&
    typeof request.logicalItem === "object" && request.logicalItem !== null &&
    Array.isArray(request.acceptedArtifactIds) &&
    Array.isArray(request.decisionArtifactIds) &&
    Array.isArray(request.inputRevisions) &&
    Array.isArray(request.inputArtifactIds);
}
