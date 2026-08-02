import { assign, setup } from "xstate";

import type {
  ArtifactId,
  JsonObject,
  RenderRunSpec,
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

export const renderMachineVersion = "render/2";
const measureContractVersion = "measure-edition/1";
const renderContractVersion = "render-edition/1";
const inspectionContractVersion = "render-inspection/1";
const visualReviewContractVersion = "visual-review/1";

export type RenderMachineInput = MachineInputBase & {
  readonly spec: RenderRunSpec;
};

export type RenderMachineContext = MachineInputBase & {
  renderManifestArtifact: ArtifactId;
  readonly rendererContractVersion: string;
  readonly printerProfileArtifact: ArtifactId | undefined;
  readonly configuredLanguages: readonly string[];
  readonly studioPolicy: RenderRunSpec["studioPolicy"];
  measurementArtifact: ArtifactId | undefined;
  renderArtifacts: readonly ArtifactId[];
  printerPreflightArtifacts: readonly ArtifactId[];
  studioReady: boolean;
  inspectionArtifact: ArtifactId | undefined;
  visualDecisionArtifact: ArtifactId | undefined;
  findingArtifacts: readonly ArtifactId[];
  visualReviewAttempt: number;
  revision: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type RenderMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "measure_edition" | "render" | "inspection" | "visual_review";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "measure_edition" | "render" | "inspection" | "visual_review";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | {
      readonly type: "REVISION_REQUESTED";
      readonly findingArtifacts: readonly ArtifactId[];
      readonly reason: string;
      readonly renderManifestArtifact?: ArtifactId;
    }
  | { readonly type: "RETRY" };

function artifact(
  event: Extract<RenderMachineEvent, { readonly type: "WORK_COMPLETED" }>,
  kind: string,
): ArtifactId | undefined {
  return event.artifacts.find((candidate) => candidate.kind === kind)?.artifactId;
}

function resultString(event: RenderMachineEvent, key: string): string | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result[key];
  return typeof value === "string" ? value : undefined;
}

function resultBoolean(event: RenderMachineEvent, key: string): boolean | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result[key];
  return typeof value === "boolean" ? value : undefined;
}

function resultStrings(event: RenderMachineEvent, key: string): readonly string[] {
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

function exactArtifacts(
  expected: readonly ArtifactId[],
  actual: readonly string[],
): boolean {
  return exactStrings(expected, actual);
}

function renderedArtifacts(
  event: Extract<RenderMachineEvent, { readonly type: "WORK_COMPLETED" }>,
): readonly ArtifactId[] {
  const nonRenderKinds = new Set([
    "render_inspection",
    "visual_review_decision",
    "edition_measurement",
    "work_answer",
  ]);
  return event.artifacts
    .filter(({ kind }) => !nonRenderKinds.has(kind))
    .map(({ artifactId }) => artifactId);
}

function effect(value: MachineEffect): MachineEffect {
  return value;
}

function baseInputs(context: RenderMachineContext): readonly ArtifactId[] {
  return [
    context.renderManifestArtifact,
    context.printerProfileArtifact,
    ...context.findingArtifacts,
  ].filter((value): value is ArtifactId => value !== undefined);
}

function visualReviewRequestId(context: RenderMachineContext): ArtifactId {
  return `art_${context.actorId}_visual_review_request_${context.revision}_${context.visualReviewAttempt}` as ArtifactId;
}

export const renderMachine = setup({
  types: {
    context: {} as RenderMachineContext,
    events: {} as RenderMachineEvent,
    input: {} as RenderMachineInput,
  },
  guards: {
    measurementPasses: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "measure_edition" &&
      artifact(event, "edition_measurement") !== undefined &&
      (resultString(event, "result") === "pass" ||
        resultBoolean(event, "fits") === true),
    measurementCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "measure_edition",
    renderIsComplete: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "render" &&
      renderedArtifacts(event).length > 0 &&
      exactStrings(
        context.configuredLanguages,
        resultStrings(event, "renderedLanguages"),
      ),
    renderCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "render",
    inspectionPassesExactRender: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "inspection" &&
      artifact(event, "render_inspection") !== undefined &&
      resultString(event, "result") === "pass" &&
      exactArtifacts(
        context.renderArtifacts,
        resultStrings(event, "renderArtifactIds"),
      ) &&
      (context.studioPolicy !== "require_ready_preflight" ||
        (context.printerProfileArtifact !== undefined &&
          context.printerPreflightArtifacts.length ===
            context.configuredLanguages.length &&
          exactArtifacts(
            context.printerPreflightArtifacts,
            resultStrings(event, "printerPreflightArtifactIds"),
          ) &&
          resultBoolean(event, "studioReady") === true)),
    inspectionCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "inspection",
    visualReviewApprovesExactRender: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "visual_review" &&
      artifact(event, "visual_review_decision") !== undefined &&
      resultString(event, "decision") === "approved" &&
      exactArtifacts(
        context.renderArtifacts,
        resultStrings(event, "renderArtifactIds"),
      ),
    visualReviewCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "visual_review",
    failedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" && event.classification === "permanent",
  },
  actions: {
    offerMeasurement: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "measuring",
        role: "measure_edition",
        slot: "measure_edition",
        subjectArtifactId: context.renderManifestArtifact,
        inputArtifacts: baseInputs(context as RenderMachineContext),
        taskArtifactId: context.renderManifestArtifact,
        contractVersion: measureContractVersion,
        allowedWorkerCapabilities: ["subprocess"],
      }),
    ]),
    offerRender: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "rendering",
        role: "render",
        slot: "render",
        subjectArtifactId: context.renderManifestArtifact,
        inputArtifacts: [
          ...baseInputs(context as RenderMachineContext),
          context.measurementArtifact,
        ].filter((value): value is ArtifactId => value !== undefined),
        taskArtifactId: context.renderManifestArtifact,
        contractVersion: context.rendererContractVersion || renderContractVersion,
        allowedWorkerCapabilities: ["subprocess"],
      }),
    ]),
    offerInspection: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "inspecting",
        role: "render_inspection",
        slot: "inspection",
        inputArtifacts: [
          context.renderManifestArtifact,
          context.printerProfileArtifact,
          ...context.renderArtifacts,
          context.measurementArtifact,
        ].filter((value): value is ArtifactId => value !== undefined),
        taskArtifactId: context.renderManifestArtifact,
        contractVersion: inspectionContractVersion,
        allowedWorkerCapabilities: ["subprocess"],
      }),
    ]),
    offerVisualReview: emitEffects(({ context }) => {
      const requestId = visualReviewRequestId(context);
      const inputs = [
        context.renderManifestArtifact,
        ...context.renderArtifacts,
        context.inspectionArtifact,
      ].filter((value): value is ArtifactId => value !== undefined);
      return [
        effect({
          type: "register_artifact",
          actorId: context.actorId,
          slot: "visual_review_request",
          artifact: {
            id: requestId,
            kind: "human_decision_request",
            schemaVersion: "visual-review-request/1",
            mediaType: "application/json",
            origin: "machine",
            payload: {
              kind: "json",
              value: {
                renderManifestArtifactId: context.renderManifestArtifact,
                renderArtifactIds: context.renderArtifacts,
                inspectionArtifactId: context.inspectionArtifact ?? null,
                choices: ["approved", "changes_required"],
              },
            },
            parents: inputs.map((artifactId: ArtifactId) => ({
              artifactId,
              relation: "visual_review_context",
            })),
          },
        }),
        effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_visual_review",
        role: "visual_review",
        slot: "visual_review",
        inputArtifacts: [requestId, ...inputs],
        taskArtifactId: requestId,
        contractVersion: visualReviewContractVersion,
        allowedWorkerCapabilities: ["human"],
        }),
      ];
    }),
    keepMeasurement: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "measure_edition") {
        return {};
      }
      return {
        measurementArtifact:
          artifact(event, "edition_measurement") ?? context.measurementArtifact,
        lastFailure: undefined,
      };
    }),
    keepRender: assign(({ event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "render") {
        return {};
      }
      return {
        renderArtifacts: renderedArtifacts(event),
        printerPreflightArtifacts: event.artifacts
          .filter(({ kind }) => kind === "printer_preflight")
          .map(({ artifactId }) => artifactId),
        studioReady: false,
        inspectionArtifact: undefined,
        visualDecisionArtifact: undefined,
        lastFailure: undefined,
      };
    }),
    keepInspection: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "inspection") {
        return {};
      }
      return {
        inspectionArtifact:
          artifact(event, "render_inspection") ?? context.inspectionArtifact,
        studioReady:
          context.studioPolicy === "require_ready_preflight"
            ? resultBoolean(event, "studioReady") === true
            : false,
        lastFailure: undefined,
      };
    }),
    keepVisualDecision: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "visual_review") {
        return {};
      }
      return {
        visualDecisionArtifact:
          artifact(event, "visual_review_decision") ??
          context.visualDecisionArtifact,
        lastFailure: undefined,
      };
    }),
    recordVisualDecision: emitEffects(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "visual_review") {
        return [];
      }
      const artifactId = artifact(event, "visual_review_decision");
      const submittedRenderArtifactIds = resultStrings(event, "renderArtifactIds");
      const choice = resultString(event, "decision") ?? "unknown";
      return [
        effect({
          type: "record_decision",
          actorId: context.actorId,
          choice,
          authority: "human",
          ...(artifactId === undefined ? {} : { artifactId }),
          details: {
            submittedRenderArtifactIds,
            expectedRenderArtifactIds: context.renderArtifacts,
            accepted:
              choice === "approved" &&
              exactArtifacts(context.renderArtifacts, submittedRenderArtifactIds),
          },
        }),
      ];
    }),
    reopen: assign(({ context, event }) => {
      if (event.type !== "REVISION_REQUESTED") {
        return {};
      }
      return {
        renderManifestArtifact:
          event.renderManifestArtifact ?? context.renderManifestArtifact,
        measurementArtifact: undefined,
        renderArtifacts: [] as readonly ArtifactId[],
        printerPreflightArtifacts: [] as readonly ArtifactId[],
        studioReady: false,
        inspectionArtifact: undefined,
        visualDecisionArtifact: undefined,
        findingArtifacts: event.findingArtifacts,
        visualReviewAttempt: 0,
        revision: context.revision + 1,
        lastFailure: event.reason,
      };
    }),
    publishApproved: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: true,
        outputs: context.renderArtifacts,
        result: {
          status: "approved",
          revision: context.revision,
          renderArtifactIds: context.renderArtifacts,
          inspectionArtifactId: context.inspectionArtifact ?? null,
          visualDecisionArtifactId: context.visualDecisionArtifact ?? null,
          printerProfileArtifactId: context.printerProfileArtifact ?? null,
          printerPreflightArtifactIds: context.printerPreflightArtifacts,
          studioPolicy: context.studioPolicy,
          studioReady: context.studioReady,
        },
      }),
    ]),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "render_failed",
        message: context.lastFailure ?? "Render failed",
      }),
    ]),
    rememberFailure: assign(({ event }) => ({
      lastFailure: event.type === "WORK_FAILED" ? event.message : "Render work failed",
    })),
    rememberRejectedInspection: assign({
      lastFailure: "Machine render inspection rejected the render artifacts",
    }),
    rememberIncompleteRender: assign({
      lastFailure: "Render answer did not cover every configured language and required output kind",
    }),
    rememberRejectedVisual: assign({
      lastFailure: "Independent visual review requested changes",
    }),
    clearFailure: assign({ lastFailure: undefined }),
    beginVisualReviewRetry: assign(({ context }) => ({
      visualReviewAttempt: context.visualReviewAttempt + 1,
    })),
  },
}).createMachine({
  id: "render",
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    renderManifestArtifact: input.spec.renderManifestArtifact,
    rendererContractVersion: input.spec.rendererContractVersion,
    printerProfileArtifact: input.spec.printerProfileArtifact,
    configuredLanguages: input.spec.configuredLanguages,
    studioPolicy: input.spec.studioPolicy,
    measurementArtifact: undefined,
    renderArtifacts: [],
    printerPreflightArtifacts: [],
    studioReady: false,
    inspectionArtifact: undefined,
    visualDecisionArtifact: undefined,
    findingArtifacts: [],
    visualReviewAttempt: 0,
    revision: 0,
    lastFailure: undefined,
  }),
  states: {
    idle: { on: { START: "measuring" } },
    measuring: {
      entry: "offerMeasurement",
      on: {
        WORK_COMPLETED: [
          {
            guard: "measurementPasses",
            actions: "keepMeasurement",
            target: "rendering",
          },
          {
            guard: "measurementCompleted",
            actions: "rememberFailure",
            target: "measurement_rejected",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "measurement_failed" },
        ],
      },
    },
    measurement_failed: {
      on: { RETRY: { actions: "clearFailure", target: "measuring" } },
    },
    measurement_rejected: {
      on: {
        REVISION_REQUESTED: { actions: "reopen", target: "measuring" },
        RETRY: { actions: "clearFailure", target: "measuring" },
      },
    },
    rendering: {
      entry: "offerRender",
      on: {
        WORK_COMPLETED: [
          {
            guard: "renderIsComplete",
            actions: "keepRender",
            target: "inspecting",
          },
          {
            guard: "renderCompleted",
            actions: "rememberIncompleteRender",
            target: "render_failed",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "render_failed" },
        ],
      },
    },
    render_failed: {
      on: { RETRY: { actions: "clearFailure", target: "rendering" } },
    },
    inspecting: {
      entry: "offerInspection",
      on: {
        WORK_COMPLETED: [
          {
            guard: "inspectionPassesExactRender",
            actions: "keepInspection",
            target: "awaiting_visual_review",
          },
          {
            guard: "inspectionCompleted",
            actions: ["keepInspection", "rememberRejectedInspection"],
            target: "inspection_rejected",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "inspection_failed" },
        ],
      },
    },
    inspection_failed: {
      on: { RETRY: { actions: "clearFailure", target: "inspecting" } },
    },
    inspection_rejected: {
      on: {
        REVISION_REQUESTED: { actions: "reopen", target: "measuring" },
        RETRY: { actions: "clearFailure", target: "rendering" },
      },
    },
    awaiting_visual_review: {
      entry: "offerVisualReview",
      on: {
        WORK_COMPLETED: [
          {
            guard: "visualReviewApprovesExactRender",
            actions: ["keepVisualDecision", "recordVisualDecision"],
            target: "approved",
          },
          {
            guard: "visualReviewCompleted",
            actions: [
              "keepVisualDecision",
              "recordVisualDecision",
              "rememberRejectedVisual",
            ],
            target: "visual_changes_required",
          },
        ],
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "visual_review_failed" },
        ],
      },
    },
    visual_review_failed: {
      on: {
        RETRY: {
          actions: ["clearFailure", "beginVisualReviewRetry"],
          target: "awaiting_visual_review",
        },
      },
    },
    visual_changes_required: {
      on: {
        REVISION_REQUESTED: { actions: "reopen", target: "measuring" },
        RETRY: {
          actions: ["clearFailure", "beginVisualReviewRetry"],
          target: "rendering",
        },
      },
    },
    approved: {
      entry: "publishApproved",
      on: {
        REVISION_REQUESTED: { actions: "reopen", target: "measuring" },
      },
    },
    failed: {
      entry: "publishFailure",
      on: { RETRY: { actions: "clearFailure", target: "measuring" } },
    },
  },
});

export function renderInitial(input: RenderMachineInput) {
  return initialMachineTransition(renderMachine, input);
}

export function renderTransition(
  snapshot: JsonMachineSnapshot,
  event: RenderMachineEvent,
) {
  return transitionMachine(renderMachine, snapshot, event);
}
