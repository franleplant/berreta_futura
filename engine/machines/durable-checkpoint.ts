import type {
  ActorId,
  ArtifactId,
  RevisionId,
} from "../contracts/index.ts";
import type { DurableLogicalItem, InputRevisionRef } from "../durable/types.ts";
import type { MachineEffect } from "./runtime.ts";

export const durableCheckpointContractVersion = "durable-checkpoint/1";
export const durableCheckpointRequestSchemaVersion = "durable-checkpoint-request/1";

export type DurableCheckpointOfferInput = {
  readonly actorId: ActorId;
  readonly actorKey: string;
  readonly state: string;
  readonly logicalItem: DurableLogicalItem;
  readonly expectedParentRevisionId?: RevisionId;
  readonly acceptedArtifactId: ArtifactId;
  readonly inputRevisions?: readonly InputRevisionRef[];
};

/**
 * Opens the authority boundary. RunEngine derives and pins committed lineage
 * in the immutable task, so state machines never reconstruct parents from
 * mutable paths or stale context.
 */
export function durableCheckpointOffer(
  input: DurableCheckpointOfferInput,
): readonly MachineEffect[] {
  return [{
      type: "open_durable_checkpoint",
      actorId: input.actorId,
      actorKey: input.actorKey,
      state: input.state,
      logicalItem: input.logicalItem,
      acceptedArtifactId: input.acceptedArtifactId,
      ...(input.expectedParentRevisionId === undefined
        ? {}
        : { expectedParentRevisionId: input.expectedParentRevisionId }),
      ...(input.inputRevisions === undefined ? {} : { inputRevisions: input.inputRevisions }),
  }];
}

export function durableRevisionArtifact(
  artifacts: readonly { readonly artifactId: ArtifactId; readonly kind: string }[],
): ArtifactId | undefined {
  return artifacts.find((artifact) => artifact.kind === "durable_revision_bound")?.artifactId;
}
