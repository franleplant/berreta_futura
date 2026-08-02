import { assign, setup } from "xstate";

import type { ArtifactId, JsonObject, WorkOfferId } from "../contracts/index.ts";
import {
  emitEffects,
  initialMachineTransition,
  transitionMachine,
  type EditionReviewRunSpec,
  type JsonMachineSnapshot,
  type MachineEffect,
  type MachineInputBase,
} from "./runtime.ts";
import { humanDecisionOffer } from "./human-decision.ts";

export const editionReviewMachineVersion = "edition-review/1";

export type EditionReviewMachineInput = MachineInputBase & {
  readonly spec: EditionReviewRunSpec;
};

export type EditionReviewRoute = {
  readonly target: string;
  readonly findingArtifactId: ArtifactId;
};

export type EditionReviewMachineContext = MachineInputBase & {
  readonly spec: EditionReviewRunSpec;
  reviewArtifact: ArtifactId | undefined;
  routes: readonly EditionReviewRoute[];
  revision: number;
  editorRequestOrdinal: number;
  lastFailure: string | undefined;
};

type CompletedArtifact = { readonly artifactId: ArtifactId; readonly kind: string };

export type EditionReviewMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "edition_review" | "editor_decision";
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "edition_review" | "editor_decision";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | {
      readonly type: "REVISION_REQUESTED";
      readonly findingArtifacts: readonly ArtifactId[];
      readonly reason: string;
    }
  | { readonly type: "RETRY" };

function effect(value: object): MachineEffect {
  return value as MachineEffect;
}

function artifact(
  event: Extract<EditionReviewMachineEvent, { readonly type: "WORK_COMPLETED" }>,
  kind: string,
): ArtifactId | undefined {
  return event.artifacts.find((candidate) => candidate.kind === kind)?.artifactId;
}

function decision(event: EditionReviewMachineEvent): string | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result.decision ?? event.result.choice;
  return typeof value === "string" ? value : undefined;
}

function parseRoutes(result: JsonObject): readonly EditionReviewRoute[] {
  if (!Array.isArray(result.routes)) {
    return [];
  }
  return result.routes.flatMap((candidate) => {
    if (
      typeof candidate !== "object" ||
      candidate === null ||
      Array.isArray(candidate)
    ) {
      return [];
    }
    const target = candidate.target;
    const findingArtifactId = candidate.findingArtifactId;
    return typeof target === "string" && typeof findingArtifactId === "string"
      ? [{ target, findingArtifactId: findingArtifactId as ArtifactId }]
      : [];
  });
}

function inputs(context: EditionReviewMachineContext): readonly ArtifactId[] {
  return [
    context.spec.editionBrief,
    ...context.spec.articleArtifacts.map((item) => item.artifactId),
    context.spec.editorialArtifact,
  ];
}

export const editionReviewMachine = setup({
  types: {
    context: {} as EditionReviewMachineContext,
    events: {} as EditionReviewMachineEvent,
    input: {} as EditionReviewMachineInput,
  },
  guards: {
    approved: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "edition_review" &&
      (decision(event) === "approve" ||
        decision(event) === "approved" ||
        decision(event) === "pass"),
    routesFindings: ({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "edition_review") {
        return false;
      }
      const routes = parseRoutes(event.result);
      const validTargets = new Set([
        "editorial",
        ...context.spec.articleArtifacts.map((article) => article.articleId),
      ]);
      return routes.length > 0 && routes.every((route) => validTargets.has(route.target));
    },
    needsEditor: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "edition_review" &&
      (decision(event) === "editor_decision" || decision(event) === "human_decision"),
    isReviewAnswer: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "edition_review",
    humanApproves: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      (decision(event) === "accept" || decision(event) === "approve"),
    humanRetries: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "editor_decision" &&
      (decision(event) === "revise" || decision(event) === "retry"),
    isEditorAnswer: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "editor_decision",
  },
  actions: {
    offerReview: emitEffects(({ context }) => [
      effect({
        type: "create_work_offer",
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "reviewing",
        role: "edition_review",
        slot: "edition_review",
        subjectArtifactId: context.spec.editorialArtifact,
        inputArtifacts: inputs(context),
        taskArtifactId: context.spec.editionBrief,
        contractVersion: "edition-review/1",
        allowedWorkerCapabilities: ["text_model", "source_blind"],
      }),
    ]),
    offerEditor: emitEffects(({ context }) => {
      const editorInputs = [
          ...inputs(context),
          ...(context.reviewArtifact === undefined ? [] : [context.reviewArtifact]),
          ...context.routes.map((route: EditionReviewRoute) => route.findingArtifactId),
        ];
      return humanDecisionOffer({
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_editor",
        role: "editor_decision",
        slot: "editor_decision",
        requestArtifactId:
          `art_${context.actorId}_edition_review_request_${context.editorRequestOrdinal}` as ArtifactId,
        requestSchemaVersion: "edition-review-decision-request/1",
        requestKind: "edition_review_editor_decision",
        ...(context.reviewArtifact === undefined
          ? {}
          : { subjectArtifactId: context.reviewArtifact }),
        inputArtifacts: editorInputs,
        allowedChoices: ["accept", "approve", "reject", "retry", "revise"],
        contractVersion: "edition-review-editor/1",
        details: {
          editionId: context.spec.editionId,
          revision: context.revision,
          reviewArtifactId: context.reviewArtifact ?? null,
          routes: context.routes.map((route: EditionReviewRoute) => ({
            target: route.target,
            findingArtifactId: route.findingArtifactId,
          })),
        },
      });
    }),
    keepReview: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED") {
        return {};
      }
      return {
        reviewArtifact:
          artifact(event, "edition_review") ??
          artifact(event, "edition_review_decision") ??
          context.reviewArtifact,
        routes: parseRoutes(event.result),
        lastFailure: undefined,
      };
    }),
    beginRevision: assign(({ context }) => ({ revision: context.revision + 1 })),
    recordDecision: emitEffects(({ context, event }) => [
      effect({
        type: "record_decision",
        actorId: context.actorId,
        choice: decision(event) ?? "unknown",
        authority:
          event.type === "WORK_COMPLETED" && event.slot === "editor_decision"
            ? "human"
            : "machine",
        ...(context.reviewArtifact === undefined ? {} : { artifactId: context.reviewArtifact }),
      }),
    ]),
    publishApproved: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: true,
        outputs: context.reviewArtifact === undefined ? [] : [context.reviewArtifact],
        result: {
          editionId: context.spec.editionId,
          status: "approved",
          revision: context.revision,
        },
      }),
    ]),
    publishRouted: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: false,
        outputs: context.reviewArtifact === undefined ? [] : [context.reviewArtifact],
        result: {
          editionId: context.spec.editionId,
          status: "revisions_routed",
          routes: context.routes.map((route: EditionReviewRoute) => ({
            target: route.target,
            findingArtifactId: route.findingArtifactId,
          })),
        },
      }),
    ]),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "edition_review_failed",
        message: context.lastFailure ?? "Edition review failed",
      }),
    ]),
    rememberFailure: assign(({ event }) => ({
      lastFailure: event.type === "WORK_FAILED" ? event.message : "Edition review failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
    bumpEditorRequest: assign(({ context }) => ({
      editorRequestOrdinal: context.editorRequestOrdinal + 1,
    })),
  },
}).createMachine({
  id: "edition-review",
  version: editionReviewMachineVersion,
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    ...(input.parentActorId === undefined ? {} : { parentActorId: input.parentActorId }),
    spec: input.spec,
    reviewArtifact: undefined,
    routes: [],
    revision: 0,
    editorRequestOrdinal: 0,
    lastFailure: undefined,
  }),
  states: {
    idle: { on: { START: "reviewing" } },
    reviewing: {
      entry: "offerReview",
      on: {
        WORK_COMPLETED: [
          { guard: "approved", actions: ["keepReview", "recordDecision"], target: "approved" },
          {
            guard: "routesFindings",
            actions: ["keepReview", "recordDecision"],
            target: "revisions_routed",
          },
          { guard: "needsEditor", actions: "keepReview", target: "awaiting_editor" },
          { guard: "isReviewAnswer", actions: ["keepReview", "rememberFailure"], target: "failed" },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    awaiting_editor: {
      entry: ["bumpEditorRequest", "offerEditor"],
      on: {
        WORK_COMPLETED: [
          { guard: "humanApproves", actions: "recordDecision", target: "approved" },
          { guard: "humanRetries", actions: ["recordDecision", "beginRevision"], target: "reviewing" },
          { guard: "isEditorAnswer", actions: ["recordDecision", "rememberFailure"], target: "failed" },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    revisions_routed: {
      entry: "publishRouted",
      on: {
        REVISION_REQUESTED: { actions: "beginRevision", target: "reviewing" },
      },
    },
    approved: {
      entry: "publishApproved",
      on: {
        REVISION_REQUESTED: { actions: "beginRevision", target: "reviewing" },
      },
    },
    failed: {
      entry: "publishFailure",
      on: { RETRY: { actions: "clearFailure", target: "reviewing" } },
    },
  },
});

export function editionReviewInitial(input: EditionReviewMachineInput) {
  return initialMachineTransition(editionReviewMachine, input);
}

export function editionReviewTransition(
  snapshot: JsonMachineSnapshot,
  event: EditionReviewMachineEvent,
) {
  return transitionMachine(editionReviewMachine, snapshot, event);
}
