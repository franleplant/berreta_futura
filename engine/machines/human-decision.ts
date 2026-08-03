import type {
  ActorId,
  ArtifactId,
  JsonObject,
  WorkAuthority,
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
  /** Defaults to human. Use only for a machine-owned verification request. */
  readonly authority?: WorkAuthority;
  /** Additional non-authority capabilities, such as source access. */
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
      schemaVersion: "human-decision-request/3",
      mediaType: "application/json",
      origin: "machine",
      payload: {
        kind: "json",
        value: {
          requestKind: input.requestKind,
          requestSchemaVersion: input.requestSchemaVersion,
          actorKey: input.actorKey,
          subjectArtifactId: input.subjectArtifactId ?? null,
          inputArtifactIds: exactInputs,
          choices: input.allowedChoices,
          allowedChoices: input.allowedChoices,
          ...(input.authority === undefined || input.authority === "human"
            ? { intentSchemaVersion: "human-decision-intent/1" }
            : {}),
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
    requirements: {
      authority: input.authority ?? "human",
      capabilities: input.requiredCapabilities ?? [],
      minimumAssurance: "local_bearer",
    },
    // Compatibility only. Authority is carried by `requirements.authority`.
    allowedWorkerCapabilities: [
      ...(input.authority === undefined || input.authority === "human" ? ["human" as const] : []),
      ...(input.requiredCapabilities ?? []),
    ],
  };
  return [request, offer];
}
