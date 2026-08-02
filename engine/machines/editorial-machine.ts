import { assign, setup } from "xstate";

import type {
  ArtifactId,
  EditorialRunSpec,
  JsonObject,
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

export const editorialMachineVersion = "editorial/1";
const writerContractVersion = "editorial-writer/1";
const editorDecisionContractVersion = "editor-decision/1";

export type EditorialMachineInput = MachineInputBase & {
  readonly spec: EditorialRunSpec;
};

export type EditorialMachineContext = MachineInputBase & {
  readonly editorialId: string;
  readonly briefArtifact: ArtifactId;
  readonly writingRules: ArtifactId;
  articleArtifacts: readonly ArtifactId[];
  manuscriptArtifact: ArtifactId | undefined;
  revisionArtifacts: readonly ArtifactId[];
  revision: number;
  editorRequestOrdinal: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type EditorialMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "draft" | "editor_decision";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "draft" | "editor_decision";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | {
      readonly type: "REVISION_REQUESTED";
      readonly findingArtifacts: readonly ArtifactId[];
      readonly articleArtifacts?: readonly ArtifactId[];
      readonly reason?: string;
    }
  | {
      readonly type: "EDITOR_DECISION_REQUIRED";
      readonly findingArtifacts: readonly ArtifactId[];
    }
  | { readonly type: "RETRY" };

function artifact(
  event: Extract<EditorialMachineEvent, { readonly type: "WORK_COMPLETED" }>,
  kind: string,
): ArtifactId | undefined {
  return event.artifacts.find((candidate) => candidate.kind === kind)?.artifactId;
}

function choice(event: EditorialMachineEvent): string | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result.choice;
  return typeof value === "string" ? value : undefined;
}

function effect(value: MachineEffect): MachineEffect {
  return value;
}

function draftInputs(context: EditorialMachineContext): readonly ArtifactId[] {
  return [
    context.briefArtifact,
    context.writingRules,
    ...context.articleArtifacts,
    context.manuscriptArtifact,
    ...context.revisionArtifacts,
  ].filter((value): value is ArtifactId => value !== undefined);
}

export const editorialMachine = setup({
  types: {
    context: {} as EditorialMachineContext,
    events: {} as EditorialMachineEvent,
    input: {} as EditorialMachineInput,
  },
  guards: {
    hasManuscript: ({ context }) => context.manuscriptArtifact !== undefined,
    draftCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "draft" &&
      artifact(event, "editorial_manuscript") !== undefined,
    decisionAccepts: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      choice(event) === "accept",
    decisionRevises: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      choice(event) === "revise",
    editorDecisionCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "editor_decision",
    failedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" && event.classification === "permanent",
  },
  actions: {
    offerDraft: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "drafting",
        role: "editorial_writer",
        slot: "draft",
        subjectArtifactId: context.manuscriptArtifact ?? context.briefArtifact,
        inputArtifacts: draftInputs(context as EditorialMachineContext),
        taskArtifactId: context.briefArtifact,
        contractVersion: writerContractVersion,
        allowedWorkerCapabilities: ["text_model", "source_blind"],
      }),
    ]),
    offerEditorDecision: emitEffects(({ context }) =>
      humanDecisionOffer({
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_editor",
        role: "editor_decision",
        slot: "editor_decision",
        requestArtifactId:
          `art_${context.actorId}_editorial_request_${context.editorRequestOrdinal}` as ArtifactId,
        requestSchemaVersion: "editorial-decision-request/1",
        requestKind: "editorial_decision",
        ...(context.manuscriptArtifact === undefined
          ? {}
          : { subjectArtifactId: context.manuscriptArtifact }),
        inputArtifacts: draftInputs(context as EditorialMachineContext),
        allowedChoices: ["accept", "reject", "revise"],
        contractVersion: editorDecisionContractVersion,
        details: {
          editorialId: context.editorialId,
          revision: context.revision,
          manuscriptArtifactId: context.manuscriptArtifact ?? null,
          articleArtifactIds: context.articleArtifacts,
          findingArtifactIds: context.revisionArtifacts,
        },
      }),
    ),
    keepDraft: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "draft") {
        return {};
      }
      return {
        manuscriptArtifact:
          artifact(event, "editorial_manuscript") ?? context.manuscriptArtifact,
        revisionArtifacts: [] as readonly ArtifactId[],
        lastFailure: undefined,
      };
    }),
    keepRevision: assign(({ context, event }) => {
      if (
        event.type !== "REVISION_REQUESTED" &&
        event.type !== "EDITOR_DECISION_REQUIRED"
      ) {
        return {};
      }
      return {
        revisionArtifacts: event.findingArtifacts,
        ...(event.type === "REVISION_REQUESTED" &&
        event.articleArtifacts !== undefined
          ? { articleArtifacts: event.articleArtifacts }
          : {}),
        revision: context.revision + 1,
        lastFailure:
          event.type === "REVISION_REQUESTED" ? event.reason : undefined,
      };
    }),
    recordEditorDecision: emitEffects(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "editor_decision") {
        return [];
      }
      const decisionArtifactId = artifact(event, "editor_decision");
      return [
        effect({
          type: "record_decision",
          actorId: context.actorId,
          choice: choice(event) ?? "unknown",
          authority: "human",
          ...(decisionArtifactId === undefined ? {} : { artifactId: decisionArtifactId }),
        }),
      ];
    }),
    publishSettled: emitEffects(({ context }) => {
      if (context.manuscriptArtifact === undefined) {
        return [];
      }
      return [
        effect({
          type: "complete_actor",
          actorId: context.actorId,
          accepting: true,
          outputs: [context.manuscriptArtifact],
          result: {
            editorialId: context.editorialId,
            revision: context.revision,
            status: "settled",
          },
        }),
      ];
    }),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "editorial_failed",
        message: context.lastFailure ?? "Editorial work failed",
      }),
    ]),
    rememberFailure: assign(({ event }) => ({
      lastFailure: event.type === "WORK_FAILED" ? event.message : "Editorial work failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
    bumpEditorRequest: assign(({ context }) => ({
      editorRequestOrdinal: context.editorRequestOrdinal + 1,
    })),
  },
}).createMachine({
  id: "editorial",
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    editorialId: input.spec.editorialId,
    briefArtifact: input.spec.briefArtifact,
    writingRules: input.spec.writingRules,
    articleArtifacts: input.spec.articleArtifacts ?? [],
    manuscriptArtifact: input.spec.initialManuscript,
    revisionArtifacts: [],
    revision: 0,
    editorRequestOrdinal: 0,
    lastFailure: undefined,
  }),
  states: {
    idle: {
      on: {
        START: [
          { guard: "hasManuscript", target: "settled" },
          { target: "drafting" },
        ],
      },
    },
    drafting: {
      entry: "offerDraft",
      on: {
        WORK_COMPLETED: {
          guard: "draftCompleted",
          actions: "keepDraft",
          target: "settled",
        },
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "draft_failed" },
        ],
        EDITOR_DECISION_REQUIRED: {
          actions: "keepRevision",
          target: "awaiting_editor",
        },
      },
    },
    draft_failed: {
      on: {
        RETRY: { actions: "clearFailure", target: "drafting" },
        EDITOR_DECISION_REQUIRED: {
          actions: "keepRevision",
          target: "awaiting_editor",
        },
      },
    },
    awaiting_editor: {
      entry: ["bumpEditorRequest", "offerEditorDecision"],
      on: {
        WORK_COMPLETED: [
          {
            guard: "decisionAccepts",
            actions: "recordEditorDecision",
            target: "settled",
          },
          {
            guard: "decisionRevises",
            actions: "recordEditorDecision",
            target: "drafting",
          },
          {
            guard: "editorDecisionCompleted",
            actions: ["recordEditorDecision", "rememberFailure"],
            target: "failed",
          },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "editor_decision_failed" },
      },
    },
    editor_decision_failed: {
      on: { RETRY: { actions: "clearFailure", target: "awaiting_editor" } },
    },
    settled: {
      entry: "publishSettled",
      on: {
        REVISION_REQUESTED: {
          actions: "keepRevision",
          target: "drafting",
        },
        EDITOR_DECISION_REQUIRED: {
          actions: "keepRevision",
          target: "awaiting_editor",
        },
      },
    },
    failed: {
      entry: "publishFailure",
      on: { RETRY: { actions: "clearFailure", target: "drafting" } },
    },
  },
});

export function editorialInitial(input: EditorialMachineInput) {
  return initialMachineTransition(editorialMachine, input);
}

export function editorialTransition(
  snapshot: JsonMachineSnapshot,
  event: EditorialMachineEvent,
) {
  return transitionMachine(editorialMachine, snapshot, event);
}
