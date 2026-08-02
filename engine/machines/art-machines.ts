import { assign, setup } from "xstate";

import type {
  ArtifactId,
  JsonObject,
  RegisteredArtSpec,
  WorkOfferId,
} from "../contracts/index.ts";
import {
  emitEffects,
  initialMachineTransition,
  transitionMachine,
  type JsonMachineSnapshot,
  type MachineEffect,
  type MachineInputBase,
} from "./runtime.ts";
import { humanDecisionOffer } from "./human-decision.ts";

export const artMachineVersion = "art/1";
export const coverArtMachineVersion = artMachineVersion;
export const interiorArtMachineVersion = artMachineVersion;
const coverImageContractVersion = "cover-image/1";
const interiorImageContractVersion = "interior-image/1";
const selectionContractVersion = "select-art/1";

export type ArtMachineInput = MachineInputBase & {
  readonly spec: RegisteredArtSpec;
};

export type ArtMachineContext = MachineInputBase & {
  readonly key: string;
  readonly role: "cover" | "interior";
  readonly briefArtifact: ArtifactId;
  readonly required: boolean;
  dependencyArtifacts: readonly ArtifactId[];
  registeredArtifact: ArtifactId | undefined;
  candidates: readonly ArtifactId[];
  revision: number;
  selectionRequestOrdinal: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type ArtMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "generate" | "select";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "generate" | "select";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | {
      readonly type: "REVISION_REQUESTED";
      readonly reason?: string;
      readonly dependencyArtifacts?: readonly ArtifactId[];
    }
  | { readonly type: "RETRY" };

function generatedCandidates(
  event: Extract<ArtMachineEvent, { readonly type: "WORK_COMPLETED" }>,
): readonly ArtifactId[] {
  return event.artifacts
    .filter(
      ({ kind }) =>
        kind === "art_candidate" ||
        kind === "cover_art_candidate" ||
        kind === "interior_art_candidate",
    )
    .map(({ artifactId }) => artifactId);
}

function selectedArtifact(event: ArtMachineEvent): ArtifactId | undefined {
  if (event.type !== "WORK_COMPLETED" || event.slot !== "select") {
    return undefined;
  }
  const selected = event.result.selectedArtifactId;
  return typeof selected === "string" ? (selected as ArtifactId) : undefined;
}

function selectionChoice(event: ArtMachineEvent): string | undefined {
  if (event.type !== "WORK_COMPLETED" || event.slot !== "select") {
    return undefined;
  }
  const choice = event.result.choice;
  return typeof choice === "string" ? choice : undefined;
}

function decisionArtifact(event: ArtMachineEvent): ArtifactId | undefined {
  if (event.type !== "WORK_COMPLETED" || event.slot !== "select") {
    return undefined;
  }
  return event.artifacts.find(({ kind }) => kind === "art_selection")?.artifactId;
}

function effect(value: MachineEffect): MachineEffect {
  return value;
}

function createArtMachine(expectedRole: "cover" | "interior") {
  return setup({
    types: {
      context: {} as ArtMachineContext,
      events: {} as ArtMachineEvent,
      input: {} as ArtMachineInput,
    },
    guards: {
      hasRegisteredArtifact: ({ context }) =>
        context.registeredArtifact !== undefined,
      generatedCandidates: ({ event }) =>
        event.type === "WORK_COMPLETED" &&
        event.slot === "generate" &&
        generatedCandidates(event).length > 0,
      selectedKnownCandidate: ({ context, event }) => {
        const selected = selectedArtifact(event);
        return (
          selectionChoice(event) === "select" &&
          selected !== undefined &&
          context.candidates.includes(selected)
        );
      },
      selectionCompleted: ({ event }) =>
        event.type === "WORK_COMPLETED" && event.slot === "select",
      failedPermanently: ({ event }) =>
        event.type === "WORK_FAILED" && event.classification === "permanent",
    },
    actions: {
      offerGeneration: emitEffects(({ context }) => [
        effect({
          type: "create_work_offer",
          actorId: context.actorId,
          actorKey: context.logicalKey,
          state: "generating",
          role: context.role === "cover" ? "cover_image" : "interior_image",
          slot: "generate",
          inputArtifacts: [context.briefArtifact, ...context.dependencyArtifacts],
          taskArtifactId: context.briefArtifact,
          contractVersion:
            context.role === "cover"
              ? coverImageContractVersion
              : interiorImageContractVersion,
          allowedWorkerCapabilities: ["image_model"],
        }),
      ]),
      offerSelection: emitEffects(({ context }) => {
        const selectionInputs = [
            context.briefArtifact,
            ...context.dependencyArtifacts,
            ...context.candidates,
          ];
        return humanDecisionOffer({
          actorId: context.actorId,
          actorKey: context.logicalKey,
          state: "awaiting_selection",
          role: "select_art",
          slot: "select",
          requestArtifactId:
            `art_${context.actorId}_art_selection_request_${context.selectionRequestOrdinal}` as ArtifactId,
          requestSchemaVersion: "art-selection-request/1",
          requestKind: "art_selection",
          inputArtifacts: selectionInputs,
          allowedChoices: context.required ? ["select"] : ["select", "drop"],
          contractVersion: selectionContractVersion,
          details: {
            artKey: context.key,
            role: context.role,
            required: context.required,
            revision: context.revision,
            briefArtifactId: context.briefArtifact,
            dependencyArtifactIds: context.dependencyArtifacts,
            candidateArtifactIds: context.candidates,
          },
        });
      }),
      keepCandidates: assign(({ context, event }) => {
        if (event.type !== "WORK_COMPLETED" || event.slot !== "generate") {
          return {};
        }
        const candidates = generatedCandidates(event);
        return {
          candidates: candidates.length === 0 ? context.candidates : candidates,
          lastFailure: undefined,
        };
      }),
      keepSelection: assign(({ event }) => ({
        registeredArtifact: selectedArtifact(event),
        lastFailure: undefined,
      })),
      recordSelection: emitEffects(({ context, event }) => {
        if (event.type !== "WORK_COMPLETED" || event.slot !== "select") {
          return [];
        }
        const artifactId = decisionArtifact(event);
        return [
          effect({
            type: "record_decision",
            actorId: context.actorId,
            choice: selectionChoice(event) ?? "unknown",
            authority: "human",
            ...(artifactId === undefined ? {} : { artifactId }),
          }),
        ];
      }),
      publishRegistered: emitEffects(({ context }) => {
        if (context.registeredArtifact === undefined) {
          return [];
        }
        return [
          effect({
            type: "complete_actor",
            actorId: context.actorId,
            accepting: true,
            outputs: [context.registeredArtifact],
            result: {
              key: context.key,
              role: context.role,
              revision: context.revision,
              status: "registered",
            },
          }),
        ];
      }),
      publishOptionalDrop: emitEffects(({ context }) => [
        effect({
          type: "complete_actor",
          actorId: context.actorId,
          accepting: true,
          outputs: [],
          result: { key: context.key, role: context.role, status: "not_required" },
        }),
      ]),
      publishFailure: emitEffects(({ context }) => [
        effect({
          type: "fail_actor",
          actorId: context.actorId,
          classification: "art_failed",
          message: context.lastFailure ?? `Art ${context.key} failed`,
        }),
      ]),
      reopen: assign(({ context, event }) => ({
        registeredArtifact: undefined,
        candidates: [] as readonly ArtifactId[],
        ...(event.type === "REVISION_REQUESTED" &&
        event.dependencyArtifacts !== undefined
          ? { dependencyArtifacts: event.dependencyArtifacts }
          : {}),
        revision: context.revision + 1,
        lastFailure:
          event.type === "REVISION_REQUESTED" ? event.reason : undefined,
      })),
      rememberFailure: assign(({ event }) => ({
        lastFailure: event.type === "WORK_FAILED" ? event.message : "Art work failed",
      })),
      clearFailure: assign({ lastFailure: undefined }),
      bumpSelectionRequest: assign(({ context }) => ({
        selectionRequestOrdinal: context.selectionRequestOrdinal + 1,
      })),
    },
  }).createMachine({
    id: `${expectedRole}-art`,
    initial: "idle",
    context: ({ input }) => ({
      actorId: input.actorId,
      logicalKey: input.logicalKey,
      key: input.spec.key,
      role: input.spec.role,
      briefArtifact: input.spec.briefArtifact,
      required: input.spec.required,
      dependencyArtifacts: input.spec.dependencyArtifacts ?? [],
      registeredArtifact: input.spec.artifactId,
      candidates: [],
      revision: 0,
      selectionRequestOrdinal: 0,
      lastFailure: undefined,
    }),
    states: {
      idle: {
        on: {
          START: [
            {
              guard: ({ context }) =>
                context.role !== expectedRole,
              actions: assign({ lastFailure: `Expected ${expectedRole} art` }),
              target: "failed",
            },
            { guard: "hasRegisteredArtifact", target: "registered" },
            { target: "generating" },
          ],
        },
      },
      generating: {
        entry: "offerGeneration",
        on: {
          WORK_COMPLETED: {
            guard: "generatedCandidates",
            actions: "keepCandidates",
            target: "awaiting_selection",
          },
          WORK_FAILED: [
            {
              guard: "failedPermanently",
              actions: "rememberFailure",
              target: "failed",
            },
            { actions: "rememberFailure", target: "generation_failed" },
          ],
        },
      },
      generation_failed: {
        on: {
          RETRY: { actions: "clearFailure", target: "generating" },
          WORK_COMPLETED: {
            guard: ({ context, event }) =>
              !context.required &&
              event.type === "WORK_COMPLETED" &&
              event.slot === "generate" &&
              event.result.choice === "drop",
            target: "not_required",
          },
        },
      },
      awaiting_selection: {
        entry: ["bumpSelectionRequest", "offerSelection"],
        on: {
          WORK_COMPLETED: [
            {
              guard: "selectedKnownCandidate",
              actions: ["recordSelection", "keepSelection"],
              target: "registered",
            },
            {
              guard: ({ context, event }) =>
                !context.required &&
                event.type === "WORK_COMPLETED" &&
                event.slot === "select" &&
                selectionChoice(event) === "drop",
              actions: "recordSelection",
              target: "not_required",
            },
            {
              guard: "selectionCompleted",
              actions: "recordSelection",
              target: "generating",
            },
          ],
          WORK_FAILED: [
            {
              guard: "failedPermanently",
              actions: "rememberFailure",
              target: "failed",
            },
            { actions: "rememberFailure", target: "selection_failed" },
          ],
        },
      },
      selection_failed: {
        on: { RETRY: { actions: "clearFailure", target: "awaiting_selection" } },
      },
      registered: {
        entry: "publishRegistered",
        on: {
          REVISION_REQUESTED: { actions: "reopen", target: "generating" },
        },
      },
      not_required: {
        entry: "publishOptionalDrop",
        on: {
          REVISION_REQUESTED: { actions: "reopen", target: "generating" },
        },
      },
      failed: {
        entry: "publishFailure",
        on: { RETRY: { actions: "clearFailure", target: "generating" } },
      },
    },
  });
}

export const coverArtMachine = createArtMachine("cover");
export const interiorArtMachine = createArtMachine("interior");

export function coverArtInitial(input: ArtMachineInput) {
  return initialMachineTransition(coverArtMachine, input);
}

export function coverArtTransition(
  snapshot: JsonMachineSnapshot,
  event: ArtMachineEvent,
) {
  return transitionMachine(coverArtMachine, snapshot, event);
}

export function interiorArtInitial(input: ArtMachineInput) {
  return initialMachineTransition(interiorArtMachine, input);
}

export function interiorArtTransition(
  snapshot: JsonMachineSnapshot,
  event: ArtMachineEvent,
) {
  return transitionMachine(interiorArtMachine, snapshot, event);
}
