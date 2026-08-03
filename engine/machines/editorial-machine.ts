import { assign, setup } from "xstate";

import type {
  ArtifactId,
  EditorialRunSpec,
  JsonObject,
  RevisionId,
  WorkOfferId,
} from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  durableCheckpointOffer,
  durableRevisionArtifact,
} from "./durable-checkpoint.ts";
import {
  emitEffects,
  initialMachineTransition,
  transitionMachine,
  type JsonMachineSnapshot,
  type MachineEffect,
  type MachineInputBase,
} from "./runtime.ts";
import { humanDecisionOffer } from "./human-decision.ts";

export const editorialMachineVersion = "editorial/2";
const writerContractVersion = "editorial-writer/1";
const editorDecisionContractVersion = "editor-decision/1";

export type EditorialMachineInput = MachineInputBase & {
  readonly spec: EditorialRunSpec;
};

export type EditorialMachineContext = MachineInputBase & {
  readonly editionId: string | undefined;
  readonly editorialId: string;
  readonly briefArtifact: ArtifactId;
  readonly writingRules: ArtifactId;
  readonly inputRevisions: readonly InputRevisionRef[];
  articleArtifacts: readonly ArtifactId[];
  manuscriptArtifact: ArtifactId | undefined;
  revisionArtifacts: readonly ArtifactId[];
  revision: number;
  boundRevisionId: RevisionId | undefined;
  durableRevisionArtifact: ArtifactId | undefined;
  editorDecisionArtifact: ArtifactId | undefined;
  editorRequestOrdinal: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type EditorialMachineEvent =
  | { readonly type: "START" }
  | { readonly type: "MIGRATION_DURABLE_BACKFILL" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "draft" | "editor_decision" | "durable_checkpoint";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "draft" | "editor_decision" | "durable_checkpoint";
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

function editorialRevisionId(context: EditorialMachineContext): RevisionId {
  return `revision_${context.actorId}_${context.revision}` as RevisionId;
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
    durableCheckpointCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "durable_checkpoint" &&
      durableRevisionArtifact(event.artifacts) !== undefined,
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
        requirements: { authority: "model", capabilities: ["text_model", "source_blind"], minimumAssurance: "local_bearer" },
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
    rememberEditorDecision: assign(({ event }) => ({
      editorDecisionArtifact:
        event.type === "WORK_COMPLETED" && event.slot === "editor_decision"
          ? artifact(event, "editor_decision")
          : undefined,
    })),
    offerDurableCheckpoint: emitEffects(({ context }) =>
      context.manuscriptArtifact === undefined
        ? []
        : durableCheckpointOffer({
            actorId: context.actorId,
            actorKey: context.logicalKey,
            state: "accepted_pending_durable",
            logicalItem: {
              kind: "editorial",
              editionId: context.editionId ?? "standalone",
              logicalId: context.editorialId,
              language: "en",
            },
            ...(context.boundRevisionId === undefined
              ? {}
              : { expectedParentRevisionId: context.boundRevisionId }),
            acceptedArtifactId: context.manuscriptArtifact,
            ...(context.inputRevisions.length === 0
              ? {}
              : { inputRevisions: context.inputRevisions }),
          }),
    ),
    keepDurableRevision: assign(({ context, event }) => ({
      boundRevisionId:
        event.type === "WORK_COMPLETED" && typeof event.result.revisionId === "string"
          ? event.result.revisionId as RevisionId
          : context.boundRevisionId,
      durableRevisionArtifact:
        event.type === "WORK_COMPLETED" && event.slot === "durable_checkpoint"
          ? durableRevisionArtifact(event.artifacts)
          : context.durableRevisionArtifact,
    })),
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
            status: "durable_bound",
            durableRevisionArtifactId: context.durableRevisionArtifact ?? null,
            revisionId: context.boundRevisionId ?? null,
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
    editionId: input.spec.editionId,
    briefArtifact: input.spec.briefArtifact,
    writingRules: input.spec.writingRules,
    inputRevisions: input.spec.inputRevisions ?? [],
    articleArtifacts: input.spec.articleArtifacts ?? [],
    manuscriptArtifact: input.spec.initialManuscript,
    revisionArtifacts: [],
    revision: 0,
    boundRevisionId: input.spec.durableParentRevisionId,
    durableRevisionArtifact: undefined,
    editorDecisionArtifact: undefined,
    editorRequestOrdinal: 0,
    lastFailure: undefined,
  }),
  states: {
    idle: {
      on: {
        START: [
          { guard: "hasManuscript", target: "accepted_pending_durable" },
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
          target: "accepted_pending_durable",
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
            actions: ["recordEditorDecision", "rememberEditorDecision"],
            target: "accepted_pending_durable",
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
    accepted_pending_durable: {
      entry: "offerDurableCheckpoint",
      on: {
        MIGRATION_DURABLE_BACKFILL: { target: "accepted_pending_durable", reenter: true },
        WORK_COMPLETED: {
          guard: "durableCheckpointCompleted",
          actions: "keepDurableRevision",
          target: "durable_bound",
        },
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    durable_bound: {
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
