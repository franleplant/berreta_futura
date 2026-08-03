import { assign, setup } from "xstate";

import type {
  ArtifactId,
  JsonObject,
  RevisionId,
  TranslationRunSpec,
  WorkOfferId,
} from "../contracts/index.ts";
import type { InputRevisionRef } from "../durable/types.ts";
import {
  emitEffects,
  initialMachineTransition,
  transitionMachine,
  type JsonMachineSnapshot,
  type MachineEffect,
  type MachineInputBase,
} from "./runtime.ts";
import { humanDecisionOffer } from "./human-decision.ts";
import {
  durableCheckpointOffer,
  durableRevisionArtifact,
} from "./durable-checkpoint.ts";

export const translationMachineVersion = "translation/2";
const draftContractVersion = "translation-writer/1";
const reviewContractVersion = "language-review/1";
const fitContractVersion = "language-fit/1";
const editorContractVersion = "translation-editor-decision/1";

export type TranslationMachineInput = MachineInputBase & {
  readonly spec: TranslationRunSpec;
};

export type TranslationMachineContext = MachineInputBase & {
  readonly editionId: string | undefined;
  readonly pieceKind: "article" | "editorial";
  readonly pieceId: string;
  readonly language: string;
  readonly sourceLanguage: string;
  readonly promptArtifact: ArtifactId;
  readonly measurementProfileArtifact: ArtifactId | undefined;
  readonly measurementInputArtifacts: readonly ArtifactId[];
  readonly inputRevisions: readonly InputRevisionRef[] | undefined;
  readonly maximumReaderPages: number;
  englishArtifacts: readonly ArtifactId[];
  translationArtifacts: readonly ArtifactId[];
  reviewArtifact: ArtifactId | undefined;
  measurementArtifact: ArtifactId | undefined;
  editorDecisionArtifact: ArtifactId | undefined;
  boundRevisionId: RevisionId | undefined;
  durableRevisionArtifact: ArtifactId | undefined;
  findingArtifacts: readonly ArtifactId[];
  editorCheckpoint: "language_review" | "language_fit" | undefined;
  revision: number;
  editorRequestOrdinal: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type TranslationMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "draft" | "language_review" | "language_fit" | "editor_decision" | "durable_checkpoint";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "draft" | "language_review" | "language_fit" | "editor_decision" | "durable_checkpoint";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | {
      readonly type: "REVISION_REQUESTED";
      readonly englishArtifacts?: readonly ArtifactId[];
      readonly findingArtifacts?: readonly ArtifactId[];
      readonly reason?: string;
    }
  | { readonly type: "RETRY" };

function artifact(
  event: Extract<TranslationMachineEvent, { readonly type: "WORK_COMPLETED" }>,
  kind: string,
): ArtifactId | undefined {
  return event.artifacts.find((candidate) => candidate.kind === kind)?.artifactId;
}

function resultString(
  event: TranslationMachineEvent,
  key: string,
): string | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result[key];
  return typeof value === "string" ? value : undefined;
}

function resultBoolean(
  event: TranslationMachineEvent,
  key: string,
): boolean | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result[key];
  return typeof value === "boolean" ? value : undefined;
}

function translatedArtifacts(
  event: Extract<TranslationMachineEvent, { readonly type: "WORK_COMPLETED" }>,
): readonly ArtifactId[] {
  return event.artifacts
    .filter(
      ({ kind }) =>
        kind === "translation" ||
        kind === "translation_bundle" ||
        kind === "translated_piece",
    )
    .map(({ artifactId }) => artifactId);
}

function effect(value: MachineEffect): MachineEffect {
  return value;
}

function allInputs(context: TranslationMachineContext): readonly ArtifactId[] {
  return [
    ...context.englishArtifacts,
    context.promptArtifact,
    ...context.translationArtifacts,
    ...context.findingArtifacts,
    context.reviewArtifact,
    context.measurementArtifact,
  ].filter((value): value is ArtifactId => value !== undefined);
}

export const translationMachine = setup({
  types: {
    context: {} as TranslationMachineContext,
    events: {} as TranslationMachineEvent,
    input: {} as TranslationMachineInput,
  },
  guards: {
    hasInitialTranslation: ({ context }) => context.translationArtifacts.length > 0,
    draftCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "draft" &&
      translatedArtifacts(event).length > 0,
    reviewApproved: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "language_review" &&
      resultString(event, "decision") === "approved",
    reviewNeedsEditor: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "language_review" &&
      resultString(event, "decision") === "editor_decision",
    languageReviewCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "language_review",
    fitPasses: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "language_fit" &&
      resultBoolean(event, "fits") === true,
    fitNeedsEditor: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "language_fit" &&
      resultString(event, "decision") === "editor_decision",
    languageFitCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "language_fit",
    editorAcceptsReview: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      resultString(event, "choice") === "accept" &&
      context.editorCheckpoint === "language_review",
    editorAcceptsFit: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      resultString(event, "choice") === "accept" &&
      context.editorCheckpoint === "language_fit",
    editorRetries: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      resultString(event, "choice") === "revise",
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
        role: "translation_writer",
        slot: "draft",
        inputArtifacts: [
          ...context.englishArtifacts,
          context.promptArtifact,
          ...context.findingArtifacts,
          ...context.translationArtifacts,
        ],
        taskArtifactId: context.promptArtifact,
        contractVersion: draftContractVersion,
        requirements: { authority: "model", capabilities: ["text_model"], minimumAssurance: "local_bearer" },
        allowedWorkerCapabilities: ["text_model"],
      }),
    ]),
    offerReview: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "language_review",
        role: "language_review",
        slot: "language_review",
        inputArtifacts: [
          ...context.englishArtifacts,
          ...context.translationArtifacts,
          context.promptArtifact,
        ],
        taskArtifactId: context.promptArtifact,
        contractVersion: reviewContractVersion,
        requirements: { authority: "model", capabilities: ["text_model"], minimumAssurance: "local_bearer" },
        allowedWorkerCapabilities: ["text_model"],
      }),
    ]),
    offerFit: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "language_fit",
        role: "language_fit",
        slot: "language_fit",
        ...(context.translationArtifacts[0] === undefined
          ? {}
          : { subjectArtifactId: context.translationArtifacts[0] }),
        inputArtifacts: [
          ...context.englishArtifacts,
          ...context.translationArtifacts,
          context.reviewArtifact,
          context.measurementProfileArtifact,
          ...context.measurementInputArtifacts,
        ].filter((value): value is ArtifactId => value !== undefined),
        taskArtifactId: context.measurementProfileArtifact ?? context.promptArtifact,
        contractVersion: fitContractVersion,
        requirements: { authority: "tool", capabilities: ["subprocess"], minimumAssurance: "local_bearer" },
        allowedWorkerCapabilities: ["subprocess"],
      }),
    ]),
    offerEditor: emitEffects(({ context }) => {
      const subjectArtifactId =
        context.editorCheckpoint === "language_fit"
          ? context.measurementArtifact
          : context.reviewArtifact;
      return humanDecisionOffer({
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_editor",
        role: "editor_decision",
        slot: "editor_decision",
        requestArtifactId:
          `art_${context.actorId}_translation_request_${context.editorRequestOrdinal}` as ArtifactId,
        requestSchemaVersion: "translation-decision-request/1",
        requestKind: "translation_editor_decision",
        ...(subjectArtifactId === undefined ? {} : { subjectArtifactId }),
        inputArtifacts: allInputs(context as TranslationMachineContext),
        allowedChoices: ["accept", "reject", "revise"],
        contractVersion: editorContractVersion,
        details: {
          language: context.language,
          sourceLanguage: context.sourceLanguage,
          checkpoint: context.editorCheckpoint ?? null,
          revision: context.revision,
          englishArtifactIds: context.englishArtifacts,
          translationArtifactIds: context.translationArtifacts,
          reviewArtifactId: context.reviewArtifact ?? null,
          measurementArtifactId: context.measurementArtifact ?? null,
          findingArtifactIds: context.findingArtifacts,
        },
      });
    }),
    offerDurableCheckpoint: emitEffects(({ context }) => {
      const acceptedArtifactId = context.translationArtifacts[0];
      return acceptedArtifactId === undefined
        ? []
        : durableCheckpointOffer({
            actorId: context.actorId,
            actorKey: context.logicalKey,
            state: "accepted_pending_durable",
            logicalItem: {
              kind: context.pieceKind,
              editionId: context.editionId ?? "standalone",
              logicalId: context.pieceId,
              language: context.language,
            },
            ...(context.boundRevisionId === undefined
              ? {}
              : { expectedParentRevisionId: context.boundRevisionId }),
            acceptedArtifactId,
            ...(context.inputRevisions === undefined
              ? {}
              : { inputRevisions: context.inputRevisions }),
          });
    }),
    keepDraft: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "draft") {
        return {};
      }
      const outputs = translatedArtifacts(event);
      return {
        translationArtifacts:
          outputs.length === 0 ? context.translationArtifacts : outputs,
        reviewArtifact: undefined,
        measurementArtifact: undefined,
        editorDecisionArtifact: undefined,
        findingArtifacts: [] as readonly ArtifactId[],
        editorCheckpoint: undefined,
        lastFailure: undefined,
      };
    }),
    keepReview: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "language_review") {
        return {};
      }
      return {
        reviewArtifact: artifact(event, "language_review") ?? context.reviewArtifact,
        findingArtifacts: event.artifacts
          .filter(({ kind }) => kind === "finding")
          .map(({ artifactId }) => artifactId),
        editorCheckpoint:
          resultString(event, "decision") === "editor_decision"
            ? "language_review" as const
            : undefined,
        lastFailure: undefined,
      };
    }),
    keepFit: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "language_fit") {
        return {};
      }
      return {
        measurementArtifact:
          artifact(event, "language_measurement") ?? context.measurementArtifact,
        editorCheckpoint:
          resultString(event, "decision") === "editor_decision"
            ? "language_fit" as const
            : undefined,
        lastFailure: undefined,
      };
    }),
    reopen: assign(({ context, event }) => {
      if (event.type !== "REVISION_REQUESTED") {
        return {};
      }
      return {
        englishArtifacts: event.englishArtifacts ?? context.englishArtifacts,
        findingArtifacts: event.findingArtifacts ?? context.findingArtifacts,
        revision: context.revision + 1,
        reviewArtifact: undefined,
        measurementArtifact: undefined,
        editorDecisionArtifact: undefined,
        editorCheckpoint: undefined,
        lastFailure: event.reason,
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
          choice: resultString(event, "choice") ?? "unknown",
          authority: "human",
          ...(decisionArtifactId === undefined ? {} : { artifactId: decisionArtifactId }),
        }),
      ];
    }),
    keepEditorDecision: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "editor_decision") {
        return {};
      }
      return {
        editorDecisionArtifact:
          artifact(event, "editor_decision") ?? context.editorDecisionArtifact,
      };
    }),
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
    publishSettled: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: true,
        outputs: context.translationArtifacts,
        result: {
          pieceKind: context.pieceKind,
          pieceId: context.pieceId,
          language: context.language,
          sourceLanguage: context.sourceLanguage,
          revision: context.revision,
          status: "settled",
          translationArtifactIds: context.translationArtifacts,
          reviewArtifactId: context.reviewArtifact ?? null,
          measurementArtifactId: context.measurementArtifact ?? null,
          editorDecisionArtifactId: context.editorDecisionArtifact ?? null,
          durableRevisionArtifactId: context.durableRevisionArtifact ?? null,
          revisionId: context.boundRevisionId ?? null,
        },
      }),
    ]),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "translation_failed",
        message: context.lastFailure ?? `Translation ${context.language} failed`,
      }),
    ]),
    rememberFailure: assign(({ event }) => ({
      lastFailure:
        event.type === "WORK_FAILED" ? event.message : "Translation work failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
    clearEditorCheckpoint: assign({ editorCheckpoint: undefined }),
    bumpEditorRequest: assign(({ context }) => ({
      editorRequestOrdinal: context.editorRequestOrdinal + 1,
    })),
  },
}).createMachine({
  id: "translation",
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    editionId: input.spec.editionId,
    pieceKind: input.spec.pieceKind,
    pieceId: input.spec.pieceId,
    language: input.spec.language,
    sourceLanguage: input.spec.sourceLanguage,
    promptArtifact: input.spec.promptArtifact,
    measurementProfileArtifact: input.spec.measurementProfileArtifact,
    measurementInputArtifacts: input.spec.measurementInputArtifacts ?? [],
    inputRevisions: input.spec.inputRevisions,
    maximumReaderPages: input.spec.maximumReaderPages,
    englishArtifacts: input.spec.englishArtifacts,
    translationArtifacts: input.spec.initialTranslationArtifacts ?? [],
    reviewArtifact: undefined,
    measurementArtifact: undefined,
    editorDecisionArtifact: undefined,
    boundRevisionId: input.spec.durableParentRevisionId,
    durableRevisionArtifact: undefined,
    findingArtifacts: [],
    editorCheckpoint: undefined,
    revision: 0,
    editorRequestOrdinal: 0,
    lastFailure: undefined,
  }),
  states: {
    idle: {
      on: {
        START: [
          { guard: "hasInitialTranslation", target: "language_review" },
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
          target: "language_review",
        },
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "draft_failed" },
        ],
      },
    },
    draft_failed: {
      on: { RETRY: { actions: "clearFailure", target: "drafting" } },
    },
    language_review: {
      entry: "offerReview",
      on: {
        WORK_COMPLETED: [
          {
            guard: "reviewApproved",
            actions: "keepReview",
            target: "language_fit",
          },
          {
            guard: "reviewNeedsEditor",
            actions: "keepReview",
            target: "awaiting_editor",
          },
          {
            guard: "languageReviewCompleted",
            actions: "keepReview",
            target: "drafting",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "review_failed" },
        ],
      },
    },
    review_failed: {
      on: { RETRY: { actions: "clearFailure", target: "language_review" } },
    },
    language_fit: {
      entry: "offerFit",
      on: {
        WORK_COMPLETED: [
          {
            guard: "fitPasses",
            actions: "keepFit",
            target: "accepted_pending_durable",
          },
          {
            guard: "fitNeedsEditor",
            actions: "keepFit",
            target: "awaiting_editor",
          },
          {
            guard: "languageFitCompleted",
            actions: "keepFit",
            target: "drafting",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "fit_failed" },
        ],
      },
    },
    fit_failed: {
      on: { RETRY: { actions: "clearFailure", target: "language_fit" } },
    },
    awaiting_editor: {
      entry: ["bumpEditorRequest", "offerEditor"],
      on: {
        WORK_COMPLETED: [
          {
            guard: "editorAcceptsReview",
            actions: ["keepEditorDecision", "recordEditorDecision", "clearEditorCheckpoint"],
            target: "language_fit",
          },
          {
            guard: "editorAcceptsFit",
            actions: ["keepEditorDecision", "recordEditorDecision", "clearEditorCheckpoint"],
            target: "accepted_pending_durable",
          },
          {
            guard: "editorRetries",
            actions: ["keepEditorDecision", "recordEditorDecision"],
            target: "drafting",
          },
          {
            guard: "editorDecisionCompleted",
            actions: ["keepEditorDecision", "recordEditorDecision", "rememberFailure"],
            target: "failed",
          },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "editor_failed" },
      },
    },
    editor_failed: {
      on: { RETRY: { actions: "clearFailure", target: "awaiting_editor" } },
    },
    accepted_pending_durable: {
      entry: "offerDurableCheckpoint",
      on: {
        WORK_COMPLETED: {
          guard: "durableCheckpointCompleted",
          actions: "keepDurableRevision",
          target: "settled",
        },
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    settled: {
      entry: "publishSettled",
      on: {
        REVISION_REQUESTED: { actions: "reopen", target: "drafting" },
      },
    },
    failed: {
      entry: "publishFailure",
      on: { RETRY: { actions: "clearFailure", target: "drafting" } },
    },
  },
});

export function translationInitial(input: TranslationMachineInput) {
  return initialMachineTransition(translationMachine, input);
}

export function translationTransition(
  snapshot: JsonMachineSnapshot,
  event: TranslationMachineEvent,
) {
  return transitionMachine(translationMachine, snapshot, event);
}
