import { assign, setup } from "xstate";

import type {
  ArtifactId,
  JsonObject,
  ReleaseRunSpec,
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

export const releaseMachineVersion = "release/1";
const releaseApprovalContractVersion = "release-approval/1";

export type ReleaseMachineInput = MachineInputBase & {
  readonly spec: ReleaseRunSpec;
};

export type ReleaseMachineContext = MachineInputBase & {
  readonly publicationArtifact: ArtifactId;
  readonly sourceArtifacts: readonly ArtifactId[];
  readonly dryRun: boolean;
  readonly target: ReleaseRunSpec["target"];
  readonly printerProfileArtifact: ArtifactId | undefined;
  readonly printerPreflightArtifacts: readonly ArtifactId[];
  readonly studioReady: boolean;
  approvalAttempt: number;
  decisionArtifact: ArtifactId | undefined;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type ReleaseMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "release_approval";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "release_approval";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | { readonly type: "RETRY" };

function resultString(event: ReleaseMachineEvent, key: string): string | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result[key];
  return typeof value === "string" ? value : undefined;
}

function resultStrings(
  event: ReleaseMachineEvent,
  key: string,
): readonly string[] {
  if (event.type !== "WORK_COMPLETED") {
    return [];
  }
  const value = event.result[key];
  return Array.isArray(value) && value.every((entry) => typeof entry === "string")
    ? value
    : [];
}

function exactStrings(left: readonly string[], right: readonly string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  const expected = new Set(left);
  return (
    expected.size === left.length &&
    new Set(right).size === right.length &&
    right.every((value) => expected.has(value))
  );
}

function decisionArtifact(event: ReleaseMachineEvent): ArtifactId | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  return event.artifacts.find(({ kind }) => kind === "release_decision")?.artifactId;
}

function effect(value: MachineEffect): MachineEffect {
  return value;
}

function approvalRequestId(context: ReleaseMachineContext): ArtifactId {
  return `art_${context.actorId}_release_approval_request_${context.approvalAttempt}` as ArtifactId;
}

export const releaseMachine = setup({
  types: {
    context: {} as ReleaseMachineContext,
    events: {} as ReleaseMachineEvent,
    input: {} as ReleaseMachineInput,
  },
  guards: {
    approvalNamesExactInputs: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "release_approval" &&
      resultString(event, "choice") === "approve" &&
      resultString(event, "publicationArtifactId") ===
        context.publicationArtifact &&
      exactStrings(
        context.sourceArtifacts,
        resultStrings(event, "sourceArtifactIds"),
      ) &&
      (context.dryRun ||
        context.target !== "press" ||
        (context.printerProfileArtifact !== undefined &&
          context.printerPreflightArtifacts.length > 0 &&
          context.studioReady)) &&
      decisionArtifact(event) !== undefined,
    releaseApprovalCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "release_approval",
    failedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" && event.classification === "permanent",
  },
  actions: {
    offerApproval: emitEffects(({ context }) => {
      const requestId = approvalRequestId(context);
      const inputs = [
        context.publicationArtifact,
        ...context.sourceArtifacts,
        context.printerProfileArtifact,
        ...context.printerPreflightArtifacts,
      ].filter((value): value is ArtifactId => value !== undefined);
      return [
        effect({
          type: "register_artifact",
          actorId: context.actorId,
          slot: "release_approval_request",
          artifact: {
            id: requestId,
            kind: "human_decision_request",
            schemaVersion: "human-decision-request/3",
            mediaType: "application/json",
            origin: "machine",
            payload: {
              kind: "json",
              value: {
                publicationArtifactId: context.publicationArtifact,
                sourceArtifactIds: context.sourceArtifacts,
                choices: ["approve", "reject"],
                dryRun: context.dryRun,
                releaseTarget: context.target,
                printerProfileArtifactId: context.printerProfileArtifact ?? null,
                printerPreflightArtifactIds: context.printerPreflightArtifacts,
                studioReady: context.studioReady,
                inputArtifactIds: inputs,
                intentSchemaVersion: "human-decision-intent/1",
                releaseLabel:
                  context.target === "press"
                    ? context.studioReady
                      ? "press_ready"
                      : "press_blocked"
                    : context.target === "web"
                      ? "web_release"
                      : "private_release",
              },
            },
            parents: inputs.map((artifactId: ArtifactId) => ({
              artifactId,
              relation: "release_context",
            })),
          },
        }),
        effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_release_approval",
        role: "release_approval",
        slot: "release_approval",
        subjectArtifactId: context.publicationArtifact,
        inputArtifacts: [requestId, ...inputs],
        taskArtifactId: requestId,
        contractVersion: releaseApprovalContractVersion,
        requirements: { authority: "human", capabilities: [], minimumAssurance: "local_bearer" },
        allowedWorkerCapabilities: ["human"],
        }),
      ];
    }),
    keepDecision: assign(({ context, event }) => ({
      decisionArtifact: decisionArtifact(event) ?? context.decisionArtifact,
      lastFailure: undefined,
    })),
    recordDecision: emitEffects(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED") {
        return [];
      }
      const artifactId = decisionArtifact(event);
      const submittedPublicationArtifactId =
        resultString(event, "publicationArtifactId") ?? null;
      const submittedSourceArtifactIds = resultStrings(event, "sourceArtifactIds");
      const choice = resultString(event, "choice") ?? "unknown";
      return [
        effect({
          type: "record_decision",
          actorId: context.actorId,
          choice,
          authority: "human",
          ...(artifactId === undefined ? {} : { artifactId }),
          details: {
            submittedPublicationArtifactId,
            submittedSourceArtifactIds,
            expectedPublicationArtifactId: context.publicationArtifact,
            expectedSourceArtifactIds: context.sourceArtifacts,
            accepted:
              choice === "approve" &&
              submittedPublicationArtifactId === context.publicationArtifact &&
              exactStrings(context.sourceArtifacts, submittedSourceArtifactIds),
            dryRun: context.dryRun,
            releaseTarget: context.target,
            printerProfileArtifactId: context.printerProfileArtifact ?? null,
            printerPreflightArtifactIds: context.printerPreflightArtifacts,
            studioReady: context.studioReady,
          },
        }),
      ];
    }),
    publishReleased: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: true,
        outputs: [context.publicationArtifact],
        result: {
          status: "released",
          publicationArtifactId: context.publicationArtifact,
          sourceArtifactIds: context.sourceArtifacts,
          decisionArtifactId: context.decisionArtifact ?? null,
          releaseTarget: context.target,
          releaseLabel:
            context.target === "press" ? "press_ready" : `${context.target}_release`,
          studioReady: context.studioReady,
        },
      }),
    ]),
    publishDryRun: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: false,
        outputs: [context.publicationArtifact],
        result: {
          status: "dry_run_complete",
          publicationArtifactId: context.publicationArtifact,
          sourceArtifactIds: context.sourceArtifacts,
          decisionArtifactId: context.decisionArtifact ?? null,
          releaseTarget: context.target,
          releaseLabel: "dry_run",
          studioReady: context.studioReady,
        },
      }),
    ]),
    publishRejected: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: false,
        outputs: [],
        result: {
          status: "release_rejected",
          publicationArtifactId: context.publicationArtifact,
        },
      }),
    ]),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "release_approval_failed",
        message: context.lastFailure ?? "Release approval failed",
      }),
    ]),
    rememberFailure: assign(({ event }) => ({
      lastFailure:
        event.type === "WORK_FAILED" ? event.message : "Release approval failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
    beginApprovalRetry: assign(({ context }) => ({
      approvalAttempt: context.approvalAttempt + 1,
    })),
  },
}).createMachine({
  id: "release",
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    publicationArtifact: input.spec.publicationArtifact,
    sourceArtifacts: input.spec.sourceArtifacts,
    dryRun: input.spec.dryRun,
    target: input.spec.target,
    printerProfileArtifact: input.spec.printerProfileArtifact,
    printerPreflightArtifacts: input.spec.printerPreflightArtifacts ?? [],
    studioReady: input.spec.studioReady ?? false,
    approvalAttempt: 0,
    decisionArtifact: undefined,
    lastFailure: undefined,
  }),
  states: {
    idle: { on: { START: "awaiting_release_approval" } },
    awaiting_release_approval: {
      entry: "offerApproval",
      on: {
        WORK_COMPLETED: [
          {
            guard: "approvalNamesExactInputs",
            actions: ["keepDecision", "recordDecision"],
            target: "approved",
          },
          {
            guard: "releaseApprovalCompleted",
            actions: ["keepDecision", "recordDecision"],
            target: "rejected",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "approval_failed" },
        ],
      },
    },
    approval_failed: {
      on: {
        RETRY: {
          actions: ["clearFailure", "beginApprovalRetry"],
          target: "awaiting_release_approval",
        },
      },
    },
    rejected: {
      entry: "publishRejected",
      on: {
        RETRY: {
          actions: "beginApprovalRetry",
          target: "awaiting_release_approval",
        },
      },
    },
    approved: {
      always: [
        { guard: ({ context }) => context.dryRun, target: "dry_run_complete" },
        { target: "released" },
      ],
    },
    dry_run_complete: {
      type: "final",
      entry: "publishDryRun",
    },
    released: {
      type: "final",
      entry: "publishReleased",
    },
    failed: {
      entry: "publishFailure",
      on: {
        RETRY: {
          actions: ["clearFailure", "beginApprovalRetry"],
          target: "awaiting_release_approval",
        },
      },
    },
  },
});

export function releaseInitial(input: ReleaseMachineInput) {
  return initialMachineTransition(releaseMachine, input);
}

export function releaseTransition(
  snapshot: JsonMachineSnapshot,
  event: ReleaseMachineEvent,
) {
  return transitionMachine(releaseMachine, snapshot, event);
}
