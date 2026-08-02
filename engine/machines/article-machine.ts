import { assign, setup } from "xstate";

import type {
  ArtifactId,
  ArticleRunSpec,
  JudgeLens,
  JsonObject,
  IterationId,
  RevisionId,
  WorkOfferId,
} from "../contracts/index.ts";
import { composeArticleWorkOffer, type ArticleOfferRole } from "../task-composer/index.ts";
import {
  emitEffects,
  initialMachineTransition,
  transitionMachine,
  type JsonMachineSnapshot,
  type MachineEffect,
  type MachineInputBase,
} from "./runtime.ts";

export const articleMachineVersion = "article/2";

export type ArticleMachineInput = MachineInputBase & {
  readonly spec: ArticleRunSpec;
};

export type ArticleCheckStatus =
  | "blocking"
  | "finding"
  | "not_applicable"
  | "pass"
  | "pending"
  | "skipped";

export type ArticleCheckResult = {
  readonly status: ArticleCheckStatus;
  readonly artifacts: readonly ArtifactId[];
  readonly result: JsonObject;
};

type ArticleChecks = Record<"measure_article" | JudgeLens, ArticleCheckResult>;

export type ArticleIterationRecord = {
  readonly iteration: number;
  readonly manuscriptArtifact?: ArtifactId;
  readonly parentManuscriptArtifact?: ArtifactId;
  readonly workingNotesArtifact?: ArtifactId;
  readonly findingArtifacts: readonly ArtifactId[];
  readonly rulingArtifacts: readonly ArtifactId[];
  readonly checks: ArticleChecks;
  readonly decision: string;
};

export type ArticleMachineContext = MachineInputBase & {
  readonly spec: ArticleRunSpec;
  manuscriptArtifact: ArtifactId | undefined;
  parentManuscriptArtifact: ArtifactId | undefined;
  workingNotesArtifact: ArtifactId | undefined;
  carriedFindingArtifacts: readonly ArtifactId[];
  carriedRulingArtifacts: readonly ArtifactId[];
  checks: ArticleChecks;
  iteration: number;
  iterationId: IterationId;
  revisionId: RevisionId;
  effectiveMaxIterations: number;
  history: readonly ArticleIterationRecord[];
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

type ArticleSlot =
  | "budget_decision"
  | "craft"
  | "editor_decision"
  | "evidence"
  | "mechanics"
  | "measure_article"
  | "shape"
  | "teaching"
  | "worth"
  | "writer";

export type ArticleMachineEvent =
  | { readonly type: "START" }
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: ArticleSlot;
      readonly offerId?: WorkOfferId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: ArticleSlot;
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | {
      readonly type: "REVISION_REQUESTED";
      readonly findingArtifacts: readonly ArtifactId[];
      readonly rulingArtifacts?: readonly ArtifactId[];
      readonly reason: string;
    }
  | {
      readonly type: "EDITOR_DECISION_REQUIRED";
      readonly findingArtifacts: readonly ArtifactId[];
      readonly reason: string;
    }
  | { readonly type: "RETRY" };

const judgeLenses: readonly JudgeLens[] = [
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
];

const stageSlots = {
  stage_1: ["measure_article", "worth", "mechanics"],
  stage_2: ["evidence", "shape"],
  stage_3: ["teaching", "craft"],
} as const;

function emptyCheck(status: ArticleCheckStatus = "pending"): ArticleCheckResult {
  return { status, artifacts: [], result: {} };
}

function initialChecks(spec: ArticleRunSpec): ArticleChecks {
  const enabled = new Set(spec.policy.enabledLenses);
  return {
    measure_article: emptyCheck(),
    worth: emptyCheck(enabled.has("worth") ? "pending" : "not_applicable"),
    mechanics: emptyCheck(enabled.has("mechanics") ? "pending" : "not_applicable"),
    evidence: emptyCheck(enabled.has("evidence") ? "pending" : "not_applicable"),
    shape: emptyCheck(enabled.has("shape") ? "pending" : "not_applicable"),
    teaching: emptyCheck(
      spec.policy.teaching === "applicable" && enabled.has("teaching")
        ? "pending"
        : "not_applicable",
    ),
    craft: emptyCheck(enabled.has("craft") ? "pending" : "not_applicable"),
  };
}

function artifact(
  event: Extract<ArticleMachineEvent, { readonly type: "WORK_COMPLETED" }>,
  kinds: readonly string[],
): ArtifactId | undefined {
  return event.artifacts.find((candidate) => kinds.includes(candidate.kind))?.artifactId;
}

function resultString(result: JsonObject, key: string): string | undefined {
  const value = result[key];
  return typeof value === "string" ? value : undefined;
}

function resultBoolean(result: JsonObject, key: string): boolean | undefined {
  const value = result[key];
  return typeof value === "boolean" ? value : undefined;
}

function resultNumber(result: JsonObject, key: string): number | undefined {
  const value = result[key];
  return typeof value === "number" ? value : undefined;
}

function choice(event: ArticleMachineEvent): string | undefined {
  return event.type === "WORK_COMPLETED"
    ? resultString(event.result, "choice") ?? resultString(event.result, "decision")
    : undefined;
}

function isHumanSlot(
  event: ArticleMachineEvent,
  slot: "budget_decision" | "editor_decision",
): boolean {
  return event.type === "WORK_COMPLETED" && event.slot === slot;
}

function isApplicable(context: ArticleMachineContext, lens: JudgeLens): boolean {
  return context.checks[lens].status === "pending";
}

function judgmentStatus(
  context: ArticleMachineContext,
  lens: JudgeLens,
  result: JsonObject,
): ArticleCheckStatus {
  if (resultString(result, "status") === "not_applicable") {
    return "not_applicable";
  }
  const decision =
    resultString(result, "decision") ??
    resultString(result, "verdict") ??
    resultString(result, "status");
  const approved = resultBoolean(result, "approved");
  const blocking = resultBoolean(result, "blocking") === true;
  const findings = result.findings;
  const hasFindings = Array.isArray(findings) && findings.length > 0;
  if (blocking || decision === "block" || decision === "blocking") {
    return "blocking";
  }
  if (
    hasFindings ||
    decision === "revise" ||
    decision === "changes_required" ||
    decision === "reject" ||
    approved === false
  ) {
    return context.spec.policy.blockingLenses.includes(lens) ? "blocking" : "finding";
  }
  if (
    approved === true ||
    decision === "approve" ||
    decision === "approved" ||
    decision === "pass" ||
    decision === "ok"
  ) {
    return "pass";
  }
  return context.spec.policy.blockingLenses.includes(lens) ? "blocking" : "finding";
}

function measurementStatus(
  context: ArticleMachineContext,
  result: JsonObject,
): ArticleCheckStatus {
  const pages = resultNumber(result, "pageCount") ?? resultNumber(result, "articlePages");
  const fits = resultBoolean(result, "fits");
  const openerFits = resultBoolean(result, "openerFits");
  if (
    fits === false ||
    openerFits === false ||
    (pages !== undefined && pages > context.spec.policy.maximumReaderPages)
  ) {
    return "blocking";
  }
  return fits === true || pages !== undefined || resultString(result, "status") === "pass"
    ? "pass"
    : "finding";
}

function checkFromEvent(
  context: ArticleMachineContext,
  event: Extract<ArticleMachineEvent, { readonly type: "WORK_COMPLETED" }>,
): ArticleCheckResult {
  const artifacts = event.artifacts.map((item) => item.artifactId);
  if (event.slot === "measure_article") {
    return { status: measurementStatus(context, event.result), artifacts, result: event.result };
  }
  if (!judgeLenses.includes(event.slot as JudgeLens)) {
    throw new TypeError(`Slot ${event.slot} is not an article check`);
  }
  const lens = event.slot as JudgeLens;
  return {
    status: judgmentStatus(context, lens, event.result),
    artifacts,
    result: event.result,
  };
}

function stageCompleteAfter(
  context: ArticleMachineContext,
  event: ArticleMachineEvent,
  slots: readonly ("measure_article" | JudgeLens)[],
): boolean {
  return slots.every(
    (slot) =>
      context.checks[slot].status !== "pending" ||
      (event.type === "WORK_COMPLETED" && event.slot === slot),
  );
}

function stageComplete(
  context: ArticleMachineContext,
  slots: readonly ("measure_article" | JudgeLens)[],
): boolean {
  return slots.every((slot) => context.checks[slot].status !== "pending");
}

function stageBlocks(context: ArticleMachineContext, slots: readonly ("measure_article" | JudgeLens)[]): boolean {
  return slots.some((slot) => context.checks[slot].status === "blocking");
}

function findings(context: ArticleMachineContext): readonly ArtifactId[] {
  return Object.values(context.checks).flatMap((check) =>
    check.status === "finding" || check.status === "blocking" ? check.artifacts : [],
  );
}

function needsRevision(context: ArticleMachineContext): boolean {
  return Object.values(context.checks).some(
    (check) => check.status === "finding" || check.status === "blocking",
  );
}

function wants(context: ArticleMachineContext, decisions: readonly string[]): boolean {
  return Object.values(context.checks).some((check) => {
    const value = resultString(check.result, "decision");
    return value !== undefined && decisions.includes(value);
  });
}

function iterationRecord(
  context: ArticleMachineContext,
  decision: string,
): ArticleIterationRecord {
  return {
    iteration: context.iteration,
    ...(context.manuscriptArtifact === undefined
      ? {}
      : { manuscriptArtifact: context.manuscriptArtifact }),
    ...(context.parentManuscriptArtifact === undefined
      ? {}
      : { parentManuscriptArtifact: context.parentManuscriptArtifact }),
    ...(context.workingNotesArtifact === undefined
      ? {}
      : { workingNotesArtifact: context.workingNotesArtifact }),
    findingArtifacts: findings(context),
    rulingArtifacts: context.carriedRulingArtifacts,
    checks: context.checks,
    decision,
  };
}

function iterationId(actorId: string, iteration: number): IterationId {
  return `iteration_${actorId}_${iteration}` as IterationId;
}

function revisionId(actorId: string, iteration: number): RevisionId {
  return `revision_${actorId}_${iteration}` as RevisionId;
}

function offer(
  context: ArticleMachineContext,
  role: ArticleOfferRole,
  slot: ArticleSlot,
  state: string,
): MachineEffect {
  return composeArticleWorkOffer({
    actorId: context.actorId,
    actorKey: context.logicalKey,
    state,
    spec: context.spec,
    role,
    slot,
    ...(context.manuscriptArtifact === undefined
      ? {}
      : { manuscriptArtifact: context.manuscriptArtifact }),
    findingArtifacts: context.carriedFindingArtifacts,
    rulingArtifacts: context.carriedRulingArtifacts,
    ...(context.workingNotesArtifact === undefined
      ? {}
      : { workingNotesArtifact: context.workingNotesArtifact }),
    iterationId: context.iterationId,
    iterationOrdinal: context.iteration,
    revisionId: context.revisionId,
    ...(context.parentManuscriptArtifact === undefined
      ? {}
      : { parentManuscriptArtifactId: context.parentManuscriptArtifact }),
  });
}

function stageOffers(
  context: ArticleMachineContext,
  stage: keyof typeof stageSlots,
): readonly MachineEffect[] {
  return stageSlots[stage]
    .filter((slot) => context.checks[slot].status === "pending")
    .map((slot) => offer(context, slot, slot, stage));
}

function humanOfferEffects(
  context: ArticleMachineContext,
  slot: "budget_decision" | "editor_decision",
  state: "awaiting_editor" | "escalated",
): readonly MachineEffect[] {
  const work = offer(context, "editor_decision", slot, state);
  if (work.type !== "create_work_offer") {
    return [work];
  }
  const requestId =
    `art_${context.actorId}_${slot}_request_${context.iteration}` as ArtifactId;
  const choices =
    slot === "budget_decision"
      ? ["increase_budget", "accept", "drop"]
      : ["revise", "accept", "drop"];
  return [
    effect({
      type: "register_artifact",
      actorId: context.actorId,
      slot: `${slot}_request`,
      artifact: {
        id: requestId,
        kind: "human_decision_request",
        schemaVersion: "article-decision-request/1",
        mediaType: "application/json",
        origin: "machine",
        payload: {
          kind: "json",
          value: {
            articleId: context.spec.articleId,
            iterationId: context.iterationId,
            revisionId: context.revisionId,
            manuscriptArtifactId: context.manuscriptArtifact ?? null,
            findingArtifactIds: context.carriedFindingArtifacts,
            rulingArtifactIds: context.carriedRulingArtifacts,
            choices,
            currentIterationBudget: context.effectiveMaxIterations,
          },
        },
        parents: work.inputArtifacts.map((artifactId: ArtifactId) => ({
          artifactId,
          relation: "decision_context",
        })),
      },
    }),
    effect({
      ...work,
      taskArtifactId: requestId,
      inputArtifacts: [requestId, ...work.inputArtifacts],
    }),
  ];
}

function effect(value: object): MachineEffect {
  return value as MachineEffect;
}

export const articleMachine = setup({
  types: {
    context: {} as ArticleMachineContext,
    events: {} as ArticleMachineEvent,
    input: {} as ArticleMachineInput,
  },
  guards: {
    hasNoBudget: ({ context }) => context.effectiveMaxIterations <= 0,
    hasInitialManuscript: ({ context }) => context.manuscriptArtifact !== undefined,
    writerCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "writer" &&
      artifact(event, ["article_manuscript", "manuscript"]) !== undefined,
    stage1Completed: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      stageSlots.stage_1.includes(event.slot as (typeof stageSlots.stage_1)[number]) &&
      stageCompleteAfter(context, event, stageSlots.stage_1),
    isStage1Work: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      stageSlots.stage_1.includes(event.slot as (typeof stageSlots.stage_1)[number]),
    stage2Completed: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      stageSlots.stage_2.includes(event.slot as (typeof stageSlots.stage_2)[number]) &&
      stageCompleteAfter(context, event, stageSlots.stage_2),
    isStage2Work: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      stageSlots.stage_2.includes(event.slot as (typeof stageSlots.stage_2)[number]),
    stage3Completed: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      stageSlots.stage_3.includes(event.slot as (typeof stageSlots.stage_3)[number]) &&
      stageCompleteAfter(context, event, stageSlots.stage_3),
    isStage3Work: ({ event }) =>
      event.type === "WORK_COMPLETED" &&
      stageSlots.stage_3.includes(event.slot as (typeof stageSlots.stage_3)[number]),
    stage1Blocking: ({ context }) => stageBlocks(context, stageSlots.stage_1),
    stage2Blocking: ({ context }) => stageBlocks(context, stageSlots.stage_2),
    stage1AlreadyComplete: ({ context }) => stageComplete(context, stageSlots.stage_1),
    stage2AlreadyComplete: ({ context }) => stageComplete(context, stageSlots.stage_2),
    stage3AlreadyComplete: ({ context }) => stageComplete(context, stageSlots.stage_3),
    wantsDrop: ({ context }) => wants(context, ["drop"]),
    needsEditor: ({ context }) => wants(context, ["editor_decision", "human_decision"]),
    passes: ({ context }) => !needsRevision(context),
    canRevise: ({ context }) => context.iteration < context.effectiveMaxIterations,
    failedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" && event.classification === "permanent",
    stage1FailedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" &&
      event.classification === "permanent" &&
      stageSlots.stage_1.includes(event.slot as (typeof stageSlots.stage_1)[number]),
    stage1RetryableFailure: ({ event }) =>
      event.type === "WORK_FAILED" &&
      event.classification !== "permanent" &&
      stageSlots.stage_1.includes(event.slot as (typeof stageSlots.stage_1)[number]),
    stage2FailedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" &&
      event.classification === "permanent" &&
      stageSlots.stage_2.includes(event.slot as (typeof stageSlots.stage_2)[number]),
    stage2RetryableFailure: ({ event }) =>
      event.type === "WORK_FAILED" &&
      event.classification !== "permanent" &&
      stageSlots.stage_2.includes(event.slot as (typeof stageSlots.stage_2)[number]),
    stage3FailedPermanently: ({ event }) =>
      event.type === "WORK_FAILED" &&
      event.classification === "permanent" &&
      stageSlots.stage_3.includes(event.slot as (typeof stageSlots.stage_3)[number]),
    stage3RetryableFailure: ({ event }) =>
      event.type === "WORK_FAILED" &&
      event.classification !== "permanent" &&
      stageSlots.stage_3.includes(event.slot as (typeof stageSlots.stage_3)[number]),
    editorAnswer: ({ event }) => isHumanSlot(event, "editor_decision"),
    editorAccepts: ({ event }) =>
      isHumanSlot(event, "editor_decision") &&
      (choice(event) === "accept" || choice(event) === "approve"),
    editorDrops: ({ event }) =>
      isHumanSlot(event, "editor_decision") && choice(event) === "drop",
    editorRevises: ({ context, event }) => {
      const requested = resultNumber(
        event.type === "WORK_COMPLETED" ? event.result : {},
        "maxIterations",
      );
      return (
        isHumanSlot(event, "editor_decision") &&
        (choice(event) === "revise" || choice(event) === "increase_budget") &&
        (context.iteration < context.effectiveMaxIterations ||
          (requested !== undefined &&
            requested >=
              (context.manuscriptArtifact === undefined
                ? context.iteration
                : context.iteration + 1)))
      );
    },
    budgetAccepts: ({ context, event }) =>
      context.manuscriptArtifact !== undefined &&
      isHumanSlot(event, "budget_decision") &&
      (choice(event) === "accept" || choice(event) === "approve"),
    budgetDrops: ({ event }) =>
      isHumanSlot(event, "budget_decision") && choice(event) === "drop",
    budgetRevises: ({ context, event }) => {
      const requested = resultNumber(
        event.type === "WORK_COMPLETED" ? event.result : {},
        "maxIterations",
      );
      return (
        isHumanSlot(event, "budget_decision") &&
        (choice(event) === "revise" || choice(event) === "increase_budget") &&
        (context.iteration < context.effectiveMaxIterations ||
          (requested !== undefined &&
            requested >=
              (context.manuscriptArtifact === undefined
                ? context.iteration
                : context.iteration + 1)))
      );
    },
    externalCanRevise: ({ context }) =>
      context.iteration < context.effectiveMaxIterations,
  },
  actions: {
    offerWriter: emitEffects(({ context }) => [offer(context, "writer", "writer", "drafting")]),
    offerStage1: emitEffects(({ context }) => stageOffers(context, "stage_1")),
    offerStage2: emitEffects(({ context }) => stageOffers(context, "stage_2")),
    offerStage3: emitEffects(({ context }) => stageOffers(context, "stage_3")),
    offerEditor: emitEffects(({ context }) =>
      humanOfferEffects(context, "editor_decision", "awaiting_editor"),
    ),
    offerBudgetDecision: emitEffects(({ context }) =>
      humanOfferEffects(context, "budget_decision", "escalated"),
    ),
    publishSettled: emitEffects(({ context }) =>
      context.manuscriptArtifact === undefined
        ? []
        : [
            effect({
              type: "complete_actor",
              actorId: context.actorId,
              accepting: true,
              outputs: [context.manuscriptArtifact],
              result: {
                articleId: context.spec.articleId,
                iteration: context.iteration,
                status: "settled",
              },
            }),
          ],
    ),
    publishDropped: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: false,
        outputs: context.manuscriptArtifact === undefined ? [] : [context.manuscriptArtifact],
        result: { articleId: context.spec.articleId, status: "dropped" },
      }),
    ]),
    publishEscalated: emitEffects(({ context }) => [
      effect({
        type: "complete_actor",
        actorId: context.actorId,
        accepting: false,
        outputs: context.manuscriptArtifact === undefined ? [] : [context.manuscriptArtifact],
        result: {
          articleId: context.spec.articleId,
          iteration: context.iteration,
          status: "escalated",
        },
      }),
    ]),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "article_failed",
        message: context.lastFailure ?? "Article work failed",
      }),
    ]),
    recordMachineDecision: emitEffects(({ context }) => [
      effect({
        type: "record_decision",
        actorId: context.actorId,
        iterationId: context.iterationId,
        choice: wants(context, ["drop"])
          ? "drop"
          : !needsRevision(context)
            ? "pass"
            : context.iteration < context.effectiveMaxIterations
              ? "revise"
              : "budget_exhausted",
        authority: "machine",
        details: { articleId: context.spec.articleId, iteration: context.iteration },
      }),
    ]),
    recordHumanDecision: emitEffects(({ context, event }) => [
      effect({
        type: "record_decision",
        actorId: context.actorId,
        iterationId: context.iterationId,
        choice: choice(event) ?? "unknown",
        authority: "human",
        details: { articleId: context.spec.articleId, iteration: context.iteration },
      }),
    ]),
    keepWriter: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "writer") {
        return {};
      }
      return {
        manuscriptArtifact:
          artifact(event, ["article_manuscript", "manuscript"]) ?? context.manuscriptArtifact,
        workingNotesArtifact:
          artifact(event, ["writer_working_notes", "working_notes"]) ??
          context.workingNotesArtifact,
        carriedFindingArtifacts: [] as readonly ArtifactId[],
        carriedRulingArtifacts: [] as readonly ArtifactId[],
        lastFailure: undefined,
      };
    }),
    keepCheck: assign(({ context, event }) => {
      if (
        event.type !== "WORK_COMPLETED" ||
        event.slot === "writer" ||
        event.slot === "editor_decision" ||
        event.slot === "budget_decision"
      ) {
        return {};
      }
      return {
        checks: { ...context.checks, [event.slot]: checkFromEvent(context, event) },
      };
    }),
    skipAfterStage1: assign(({ context }) => ({
      checks: {
        ...context.checks,
        evidence:
          context.checks.evidence.status === "pending"
            ? emptyCheck("skipped")
            : context.checks.evidence,
        shape:
          context.checks.shape.status === "pending"
            ? emptyCheck("skipped")
            : context.checks.shape,
        teaching:
          context.checks.teaching.status === "pending"
            ? emptyCheck("skipped")
            : context.checks.teaching,
        craft:
          context.checks.craft.status === "pending"
            ? emptyCheck("skipped")
            : context.checks.craft,
      },
    })),
    skipAfterStage2: assign(({ context }) => ({
      checks: {
        ...context.checks,
        teaching:
          context.checks.teaching.status === "pending"
            ? emptyCheck("skipped")
            : context.checks.teaching,
        craft:
          context.checks.craft.status === "pending"
            ? emptyCheck("skipped")
            : context.checks.craft,
      },
    })),
    prepareRevision: assign(({ context }) => ({
      history: [...context.history, iterationRecord(context, "revise")],
      parentManuscriptArtifact: context.manuscriptArtifact,
      carriedFindingArtifacts: findings(context),
      checks: initialChecks(context.spec),
      iteration: context.iteration + 1,
      iterationId: iterationId(context.actorId, context.iteration + 1),
      revisionId: revisionId(context.actorId, context.iteration + 1),
      lastFailure: undefined,
    })),
    prepareExternalRevision: assign(({ context, event }) => {
      if (event.type !== "REVISION_REQUESTED") {
        return {};
      }
      return {
        history: [...context.history, iterationRecord(context, "revision_requested")],
        parentManuscriptArtifact: context.manuscriptArtifact,
        carriedFindingArtifacts: event.findingArtifacts,
        carriedRulingArtifacts: event.rulingArtifacts ?? [],
        checks: initialChecks(context.spec),
        iteration: context.iteration + 1,
        iterationId: iterationId(context.actorId, context.iteration + 1),
        revisionId: revisionId(context.actorId, context.iteration + 1),
        lastFailure: event.reason,
      };
    }),
    rememberEditorRequest: assign(({ event }) => ({
      carriedFindingArtifacts:
        event.type === "EDITOR_DECISION_REQUIRED" ? event.findingArtifacts : [],
      lastFailure:
        event.type === "EDITOR_DECISION_REQUIRED" ? event.reason : undefined,
    })),
    applyHumanRevision: assign(({ context, event }) => {
      const requested = resultNumber(
        event.type === "WORK_COMPLETED" ? event.result : {},
        "maxIterations",
      );
      const nextIteration =
        context.manuscriptArtifact === undefined
          ? context.iteration
          : context.iteration + 1;
      return {
        history:
          context.manuscriptArtifact === undefined
            ? context.history
            : [...context.history, iterationRecord(context, "human_revise")],
        parentManuscriptArtifact: context.manuscriptArtifact,
        carriedFindingArtifacts: findings(context),
        checks: initialChecks(context.spec),
        iteration: nextIteration,
        iterationId: iterationId(context.actorId, nextIteration),
        revisionId: revisionId(context.actorId, nextIteration),
        effectiveMaxIterations:
          requested === undefined
            ? context.effectiveMaxIterations
            : Math.max(context.effectiveMaxIterations, requested),
        lastFailure: undefined,
      };
    }),
    archivePass: assign(({ context }) => ({
      history: [...context.history, iterationRecord(context, "pass")],
    })),
    archiveDrop: assign(({ context }) => ({
      history: [...context.history, iterationRecord(context, "drop")],
    })),
    rememberFailure: assign(({ event }) => ({
      lastFailure: event.type === "WORK_FAILED" ? event.message : "Article work failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
  },
}).createMachine({
  id: "article",
  version: articleMachineVersion,
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    ...(input.parentActorId === undefined ? {} : { parentActorId: input.parentActorId }),
    spec: input.spec,
    manuscriptArtifact: input.spec.initialManuscript,
    parentManuscriptArtifact: undefined,
    workingNotesArtifact: undefined,
    carriedFindingArtifacts: [],
    carriedRulingArtifacts: [],
    checks: initialChecks(input.spec),
    iteration: 1,
    iterationId: iterationId(input.actorId, 1),
    revisionId: revisionId(input.actorId, 1),
    effectiveMaxIterations: input.spec.policy.maxIterations,
    history: [],
    lastFailure: undefined,
  }),
  states: {
    idle: { on: { START: "initializing" } },
    initializing: {
      always: [
        { guard: "hasNoBudget", target: "escalated" },
        { guard: "hasInitialManuscript", target: "stage_1" },
        { target: "drafting" },
      ],
    },
    drafting: {
      entry: "offerWriter",
      on: {
        WORK_COMPLETED: {
          guard: "writerCompleted",
          actions: "keepWriter",
          target: "stage_1",
        },
        WORK_FAILED: [
          {
            guard: "failedPermanently",
            actions: "rememberFailure",
            target: "failed",
          },
          { actions: "rememberFailure", target: "drafting", reenter: true },
        ],
        EDITOR_DECISION_REQUIRED: {
          actions: "rememberEditorRequest",
          target: "awaiting_editor",
        },
      },
    },
    stage_1: {
      entry: "offerStage1",
      always: { guard: "stage1AlreadyComplete", target: "stage_1_decision" },
      on: {
        WORK_COMPLETED: [
          {
            guard: "stage1Completed",
            actions: "keepCheck",
            target: "stage_1_decision",
          },
          { guard: "isStage1Work", actions: "keepCheck" },
        ],
        WORK_FAILED: [
          { guard: "stage1FailedPermanently", actions: "rememberFailure", target: "failed" },
          { guard: "stage1RetryableFailure", target: "stage_1", reenter: true },
        ],
      },
    },
    stage_1_decision: {
      always: [
        { guard: "stage1Blocking", actions: "skipAfterStage1", target: "deciding" },
        { target: "stage_2" },
      ],
    },
    stage_2: {
      entry: "offerStage2",
      always: { guard: "stage2AlreadyComplete", target: "stage_2_decision" },
      on: {
        WORK_COMPLETED: [
          {
            guard: "stage2Completed",
            actions: "keepCheck",
            target: "stage_2_decision",
          },
          { guard: "isStage2Work", actions: "keepCheck" },
        ],
        WORK_FAILED: [
          { guard: "stage2FailedPermanently", actions: "rememberFailure", target: "failed" },
          { guard: "stage2RetryableFailure", target: "stage_2", reenter: true },
        ],
      },
    },
    stage_2_decision: {
      always: [
        { guard: "stage2Blocking", actions: "skipAfterStage2", target: "deciding" },
        { target: "stage_3" },
      ],
    },
    stage_3: {
      entry: "offerStage3",
      always: { guard: "stage3AlreadyComplete", target: "deciding" },
      on: {
        WORK_COMPLETED: [
          {
            guard: "stage3Completed",
            actions: "keepCheck",
            target: "deciding",
          },
          { guard: "isStage3Work", actions: "keepCheck" },
        ],
        WORK_FAILED: [
          { guard: "stage3FailedPermanently", actions: "rememberFailure", target: "failed" },
          { guard: "stage3RetryableFailure", target: "stage_3", reenter: true },
        ],
      },
    },
    deciding: {
      always: [
        { guard: "wantsDrop", actions: ["archiveDrop", "recordMachineDecision"], target: "dropped" },
        { guard: "needsEditor", target: "awaiting_editor" },
        { guard: "passes", actions: ["archivePass", "recordMachineDecision"], target: "settled" },
        { guard: "canRevise", actions: ["recordMachineDecision", "prepareRevision"], target: "drafting" },
        { actions: "recordMachineDecision", target: "escalated" },
      ],
    },
    awaiting_editor: {
      entry: "offerEditor",
      on: {
        WORK_COMPLETED: [
          { guard: "editorAccepts", actions: ["recordHumanDecision", "archivePass"], target: "settled" },
          { guard: "editorDrops", actions: ["recordHumanDecision", "archiveDrop"], target: "dropped" },
          { guard: "editorRevises", actions: ["recordHumanDecision", "applyHumanRevision"], target: "drafting" },
          { guard: "editorAnswer", actions: "recordHumanDecision", target: "escalated" },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    settled: {
      entry: "publishSettled",
      on: {
        REVISION_REQUESTED: [
          { guard: "externalCanRevise", actions: "prepareExternalRevision", target: "drafting" },
          { actions: "prepareExternalRevision", target: "escalated" },
        ],
        EDITOR_DECISION_REQUIRED: {
          actions: "rememberEditorRequest",
          target: "awaiting_editor",
        },
      },
    },
    escalated: {
      entry: ["publishEscalated", "offerBudgetDecision"],
      on: {
        WORK_COMPLETED: [
          { guard: "budgetAccepts", actions: ["recordHumanDecision", "archivePass"], target: "settled" },
          { guard: "budgetDrops", actions: ["recordHumanDecision", "archiveDrop"], target: "dropped" },
          { guard: "budgetRevises", actions: ["recordHumanDecision", "applyHumanRevision"], target: "drafting" },
        ],
      },
    },
    dropped: { entry: "publishDropped", type: "final" },
    failed: { entry: "publishFailure", type: "final" },
  },
});

export function articleInitial(input: ArticleMachineInput) {
  return initialMachineTransition(articleMachine, input);
}

export function articleTransition(
  snapshot: JsonMachineSnapshot,
  event: ArticleMachineEvent,
) {
  return transitionMachine(articleMachine, snapshot, event);
}
