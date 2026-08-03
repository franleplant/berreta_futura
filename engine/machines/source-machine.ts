import { assign, setup } from "xstate";

import type {
  ArtifactId,
  JsonObject,
  SourceRunSpec,
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

export const sourceMachineVersion = "source/3";
const captureContractVersion = "capture-source/1";
const extractionContractVersion = "extract-source/1";
const reviewContractVersion = "review-source/1";

export type SourceMachineInput = MachineInputBase & {
  readonly spec: SourceRunSpec;
};

export type SourceMachineContext = MachineInputBase & {
  readonly sourceId: string;
  readonly leadArtifact: ArtifactId;
  readonly captureProfileArtifact: ArtifactId | undefined;
  readonly captureInputArtifacts: readonly ArtifactId[];
  rawBundleArtifact: ArtifactId | undefined;
  rawEvidenceArtifacts: readonly ArtifactId[];
  extractionArtifact: ArtifactId | undefined;
  metadataArtifact: ArtifactId | undefined;
  approvalArtifact: ArtifactId | undefined;
  revision: number;
  reviewRequestOrdinal: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type SourceMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "capture" | "extract" | "review";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "capture" | "extract" | "review";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | { readonly type: "RETRY" }
  | { readonly type: "REVISION_REQUESTED"; readonly reason?: string };

function artifact(
  event: Extract<SourceMachineEvent, { readonly type: "WORK_COMPLETED" }>,
  kind: string,
): ArtifactId | undefined {
  return event.artifacts.find((candidate) => candidate.kind === kind)?.artifactId;
}

function resultString(result: JsonObject, key: string): string | undefined {
  const value = result[key];
  return typeof value === "string" ? value : undefined;
}

function outputArtifacts(context: SourceMachineContext): readonly ArtifactId[] {
  return [
    context.leadArtifact,
    context.rawBundleArtifact,
    ...context.rawEvidenceArtifacts,
    context.extractionArtifact,
    context.metadataArtifact,
    context.approvalArtifact,
  ].filter((value): value is ArtifactId => value !== undefined);
}

function effect(value: MachineEffect): MachineEffect {
  return value;
}

export const sourceMachine = setup({
  types: {
    context: {} as SourceMachineContext,
    events: {} as SourceMachineEvent,
    input: {} as SourceMachineInput,
  },
  guards: {
    hasExtraction: ({ context }) => context.extractionArtifact !== undefined,
    hasRawEvidenceBundle: ({ context }) =>
      context.rawBundleArtifact !== undefined && context.rawEvidenceArtifacts.length > 0,
    captureCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "capture" &&
      artifact(event, "raw_source_bundle") !== undefined &&
      event.artifacts.some((candidate) => candidate.kind === "raw_evidence"),
    extractionCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "extract" &&
      artifact(event, "source_extraction") !== undefined,
    reviewApproved: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "review" &&
      resultString(event.result, "decision") === "approved" &&
      artifact(event, "source_review_decision") !== undefined,
    reviewCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "review",
    failedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" && event.classification === "permanent",
  },
  actions: {
    offerCapture: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "capturing",
        role: "capture_source",
        slot: "capture",
        subjectArtifactId: context.leadArtifact,
        inputArtifacts: [
          context.leadArtifact,
          context.captureProfileArtifact,
          ...context.captureInputArtifacts,
        ].filter((value): value is ArtifactId => value !== undefined),
        taskArtifactId: context.captureProfileArtifact ?? context.leadArtifact,
        contractVersion: captureContractVersion,
        requirements: { authority: "tool", capabilities: ["subprocess", "source_access"], minimumAssurance: "local_bearer" },
        allowedWorkerCapabilities: ["subprocess", "source_access"],
      }),
    ]),
    offerExtraction: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "extracting",
        role: "extract_source",
        slot: "extract",
        subjectArtifactId: context.rawBundleArtifact,
        inputArtifacts: [
          context.rawBundleArtifact,
          ...context.rawEvidenceArtifacts,
          context.leadArtifact,
        ].filter(
          (value): value is ArtifactId => value !== undefined,
        ),
        taskArtifactId: context.leadArtifact,
        contractVersion: extractionContractVersion,
        requirements: { authority: "model", capabilities: ["text_model", "source_access"], minimumAssurance: "local_bearer" },
        allowedWorkerCapabilities: ["text_model", "source_access"],
      }),
    ]),
    offerReview: emitEffects(({ context }) => {
      const inputs = outputArtifacts(context as SourceMachineContext);
      return humanDecisionOffer({
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_source_review",
        role: "review_source",
        slot: "review",
        requestArtifactId:
          `art_${context.actorId}_source_review_request_${context.reviewRequestOrdinal}` as ArtifactId,
        requestSchemaVersion: "source-review-request/1",
        requestKind: "source_review",
        ...(context.extractionArtifact === undefined
          ? {}
          : { subjectArtifactId: context.extractionArtifact }),
        inputArtifacts: inputs,
        allowedChoices: ["approved", "changes_required", "reject", "revise"],
        contractVersion: reviewContractVersion,
        requiredCapabilities: ["source_access"],
        details: {
          sourceId: context.sourceId,
          leadArtifactId: context.leadArtifact,
          rawBundleArtifactId: context.rawBundleArtifact ?? null,
          rawEvidenceArtifactIds: context.rawEvidenceArtifacts,
          extractionArtifactId: context.extractionArtifact ?? null,
          metadataArtifactId: context.metadataArtifact ?? null,
          approvalArtifactId: context.approvalArtifact ?? null,
        },
      });
    }),
    publishReady: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: true,
        outputs: outputArtifacts(context as SourceMachineContext),
        result: {
          sourceId: context.sourceId,
          status: "ready",
          rawBundleArtifactId: context.rawBundleArtifact ?? null,
          extractionArtifactId: context.extractionArtifact ?? null,
          metadataArtifactId: context.metadataArtifact ?? null,
          approvalArtifactId: context.approvalArtifact ?? null,
        },
      }),
    ]),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "source_failed",
        message: context.lastFailure ?? "Source preparation failed",
      }),
    ]),
    recordApproval: emitEffects(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "review") {
        return [];
      }
      const decisionArtifactId = artifact(event, "source_review_decision");
      return [
        effect({
          type: "record_decision",
          actorId: context.actorId,
          choice: resultString(event.result, "decision") ?? "unknown",
          authority: "human",
          ...(decisionArtifactId === undefined ? {} : { artifactId: decisionArtifactId }),
        }),
      ];
    }),
    keepCapture: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "capture") {
        return {};
      }
      return {
        rawBundleArtifact: artifact(event, "raw_source_bundle") ?? context.rawBundleArtifact,
        rawEvidenceArtifacts: event.artifacts
          .filter(({ kind }) => kind === "raw_evidence")
          .map(({ artifactId }) => artifactId),
        metadataArtifact: artifact(event, "source_metadata") ?? context.metadataArtifact,
        lastFailure: undefined,
      };
    }),
    keepExtraction: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "extract") {
        return {};
      }
      return {
        extractionArtifact: artifact(event, "source_extraction") ?? context.extractionArtifact,
        metadataArtifact: artifact(event, "source_metadata") ?? context.metadataArtifact,
        lastFailure: undefined,
      };
    }),
    keepApproval: assign(({ context, event }) => ({
      approvalArtifact:
        event.type === "WORK_COMPLETED" && event.slot === "review"
          ? artifact(event, "source_review_decision") ?? context.approvalArtifact
          : context.approvalArtifact,
      lastFailure: undefined,
    })),
    requestRevision: assign(({ context, event }) => ({
      approvalArtifact: undefined,
      revision: context.revision + 1,
      lastFailure:
        event.type === "REVISION_REQUESTED" ? event.reason : "Source review requested revision",
    })),
    rememberFailure: assign(({ event }) => ({
      lastFailure: event.type === "WORK_FAILED" ? event.message : "Source work failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
    bumpReviewRequest: assign(({ context }) => ({
      reviewRequestOrdinal: context.reviewRequestOrdinal + 1,
    })),
  },
}).createMachine({
  id: "source",
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    sourceId: input.spec.sourceId,
    leadArtifact: input.spec.leadArtifact,
    captureProfileArtifact: input.spec.captureProfileArtifact,
    captureInputArtifacts: input.spec.captureInputArtifacts ?? [],
    rawBundleArtifact: input.spec.rawBundleArtifact,
    rawEvidenceArtifacts: input.spec.rawEvidenceArtifacts ?? [],
    extractionArtifact: input.spec.extractionArtifact,
    metadataArtifact: input.spec.metadataArtifact,
    // A review decision belongs to one offer in one run. Even a persisted
    // historical decision cannot pre-approve this source actor: its current
    // capture and extraction must be reviewed through the offer emitted here.
    approvalArtifact: undefined,
    revision: 0,
    reviewRequestOrdinal: 0,
    lastFailure: undefined,
  }),
  states: {
    idle: {
      on: {
        START: [
          { guard: "hasExtraction", target: "awaiting_source_review" },
          { guard: "hasRawEvidenceBundle", target: "extracting" },
          { target: "capturing" },
        ],
      },
    },
    capturing: {
      entry: "offerCapture",
      on: {
        WORK_COMPLETED: {
          guard: "captureCompleted",
          actions: "keepCapture",
          target: "extracting",
        },
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "source_failed",
          },
          { actions: "rememberFailure", target: "capture_failed" },
        ],
      },
    },
    capture_failed: {
      on: { RETRY: { actions: "clearFailure", target: "capturing" } },
    },
    extracting: {
      entry: "offerExtraction",
      on: {
        WORK_COMPLETED: {
          guard: "extractionCompleted",
          actions: "keepExtraction",
          target: "awaiting_source_review",
        },
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "source_failed",
          },
          { actions: "rememberFailure", target: "extraction_failed" },
        ],
      },
    },
    extraction_failed: {
      on: { RETRY: { actions: "clearFailure", target: "extracting" } },
    },
    awaiting_source_review: {
      entry: ["bumpReviewRequest", "offerReview"],
      on: {
        WORK_COMPLETED: [
          {
            guard: "reviewApproved",
            actions: ["recordApproval", "keepApproval"],
            target: "ready",
          },
          {
            guard: "reviewCompleted",
            actions: ["recordApproval", "requestRevision"],
            target: "extracting",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "source_failed",
          },
          { actions: "rememberFailure", target: "review_failed" },
        ],
        REVISION_REQUESTED: {
          actions: "requestRevision",
          target: "extracting",
        },
      },
    },
    review_failed: {
      on: { RETRY: { actions: "clearFailure", target: "awaiting_source_review" } },
    },
    ready: {
      entry: "publishReady",
      on: {
        REVISION_REQUESTED: {
          actions: "requestRevision",
          target: "extracting",
        },
      },
    },
    source_failed: {
      entry: "publishFailure",
      on: { RETRY: { actions: "clearFailure", target: "capturing" } },
    },
  },
});

export function sourceInitial(input: SourceMachineInput) {
  return initialMachineTransition(sourceMachine, input);
}

export function sourceTransition(
  snapshot: JsonMachineSnapshot,
  event: SourceMachineEvent,
) {
  return transitionMachine(sourceMachine, snapshot, event);
}
