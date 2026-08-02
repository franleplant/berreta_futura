import type {
  ActorId,
  ArtifactId,
  JsonObject,
  WorkRole,
  WorkerCapability,
} from "../contracts/index.ts";
import type { MachineEffect } from "./runtime.ts";

export type HumanDecisionOfferInput = {
  readonly actorId: ActorId;
  readonly actorKey: string;
  readonly state: string;
  readonly role: WorkRole;
  readonly slot: string;
  readonly requestArtifactId: ArtifactId;
  readonly requestSchemaVersion: string;
  readonly requestKind: string;
  readonly subjectArtifactId?: ArtifactId;
  readonly inputArtifacts: readonly ArtifactId[];
  readonly allowedChoices: readonly string[];
  readonly contractVersion: string;
  readonly requiredCapabilities?: readonly WorkerCapability[];
  readonly details?: JsonObject;
};

/**
 * Creates one immutable authority request and the human offer bound to it.
 * Callers choose the stable request ID from actor-local revision state.
 */
export function humanDecisionOffer(
  input: HumanDecisionOfferInput,
): readonly MachineEffect[] {
  const exactInputs = [...new Set(input.inputArtifacts)];
  const request: MachineEffect = {
    type: "register_artifact",
    actorId: input.actorId,
    slot: `${input.slot}_request`,
    artifact: {
      id: input.requestArtifactId,
      kind: "human_decision_request",
      schemaVersion: input.requestSchemaVersion,
      mediaType: "application/json",
      origin: "machine",
      payload: {
        kind: "json",
        value: {
          requestKind: input.requestKind,
          actorKey: input.actorKey,
          subjectArtifactId: input.subjectArtifactId ?? null,
          inputArtifactIds: exactInputs,
          choices: input.allowedChoices,
          allowedChoices: input.allowedChoices,
          ...(input.details ?? {}),
        },
      },
      parents: exactInputs.map((artifactId) => ({
        artifactId,
        relation: "decision_context",
      })),
    },
  };
  const offer: MachineEffect = {
    type: "create_work_offer",
    actorId: input.actorId,
    actorKey: input.actorKey,
    state: input.state,
    role: input.role,
    slot: input.slot,
    ...(input.subjectArtifactId === undefined
      ? {}
      : { subjectArtifactId: input.subjectArtifactId }),
    inputArtifacts: [input.requestArtifactId, ...exactInputs],
    taskArtifactId: input.requestArtifactId,
    contractVersion: input.contractVersion,
    allowedWorkerCapabilities: input.requiredCapabilities ?? ["human"],
  };
  return [request, offer];
}
