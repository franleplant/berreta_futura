import { assign, setup } from "xstate";

import type {
  ActorId,
  ApprovedProductionPlan,
  ArticleRunSpec,
  ArtifactId,
  EditionRunSpec,
  JsonObject,
  RegisteredArtSpec,
  SourceRunSpec,
  TranslationRunSpec,
  WorkOfferId,
} from "../contracts/index.ts";
import { parseApprovedProductionPlan } from "../contracts/index.ts";
import {
  emitEffects,
  initialMachineTransition,
  transitionMachine,
  type ChildSpawnedEvent,
  type ChildStatusEvent,
  type EditionReviewRunSpec,
  type JsonMachineSnapshot,
  type MachineEffect,
  type MachineInputBase,
  type MachineKind,
  type MachineSpawnSpec,
} from "./runtime.ts";
import {
  ProductionPlanError,
  resolveApprovedProductionPlan,
  resolvePreplannedProduction,
  type ReadySourceExtraction,
  type ResolvedProductionPlan,
} from "./production-plan.ts";
import { humanDecisionOffer } from "./human-decision.ts";

export const editionMachineVersion = "edition/2";

export type EditionMachineInput = MachineInputBase & {
  readonly spec: EditionRunSpec;
};

type ChildRecord = {
  readonly actorId?: ActorId;
  readonly machine?: Exclude<MachineKind, "edition">;
  readonly status: "accepting" | "active" | "done" | "failed";
  readonly outputs: readonly ArtifactId[];
  readonly result: JsonObject;
};

export type EditionMachineContext = MachineInputBase & {
  readonly spec: EditionRunSpec;
  sources: readonly SourceRunSpec[];
  children: Readonly<Record<string, ChildRecord>>;
  planningArtifact: ArtifactId | undefined;
  resolvedPlan: ResolvedProductionPlan | undefined;
  reviewCycle: number;
  renderCycle: number;
  closeRequestOrdinal: number;
  planRequestOrdinal: number;
  editorRequestOrdinal: number;
  routedArticleKeys: readonly string[];
  routedFindingArtifacts: readonly ArtifactId[];
  lastFailure: string | undefined;
};

type CompletedArtifact = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type EditionMachineEvent =
  | { readonly type: "START" }
  | { readonly type: "LEAD_RECEIVED"; readonly source: SourceRunSpec }
  | ChildSpawnedEvent
  | ChildStatusEvent
  | {
      readonly type: "WORK_COMPLETED";
      readonly slot: "close_collection" | "plan_edition" | "editor_decision";
      readonly offerId?: WorkOfferId;
      readonly taskArtifactId?: ArtifactId;
      readonly artifacts: readonly CompletedArtifact[];
      readonly result: JsonObject;
    }
  | {
      readonly type: "WORK_FAILED";
      readonly slot: "close_collection" | "plan_edition" | "editor_decision";
      readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
      readonly message: string;
    }
  | { readonly type: "RETRY" };

function effect(value: object): MachineEffect {
  return value as MachineEffect;
}

function spawn(
  context: EditionMachineContext,
  machine: Exclude<MachineKind, "edition">,
  logicalKey: string,
  spec: MachineSpawnSpec,
): MachineEffect {
  return effect({
    type: "spawn_actor",
    parentActorId: context.actorId,
    machine,
    logicalKey,
    spec,
  });
}

function sourceKey(sourceId: string): string {
  return `source:${sourceId}`;
}

function articleKey(articleId: string): string {
  return `article:${articleId}`;
}

function artKey(key: string): string {
  return `art:${key}`;
}

function translationKey(language: string, cycle: number): string {
  return `translation:${language}:${cycle}`;
}

function reviewKey(cycle: number): string {
  return `edition-review:${cycle}`;
}

function renderKey(cycle: number): string {
  return `render:${cycle}`;
}

function statusAfter(
  context: EditionMachineContext,
  event: EditionMachineEvent,
  key: string,
): ChildRecord["status"] | undefined {
  return event.type === "CHILD_STATUS" && event.childKey === key
    ? event.status
    : context.children[key]?.status;
}

function resultAfter(
  context: EditionMachineContext,
  event: EditionMachineEvent,
  key: string,
): JsonObject {
  return event.type === "CHILD_STATUS" && event.childKey === key
    ? event.result
    : context.children[key]?.result ?? {};
}

function outputsAfter(
  context: EditionMachineContext,
  event: EditionMachineEvent,
  key: string,
): readonly ArtifactId[] {
  return event.type === "CHILD_STATUS" && event.childKey === key
    ? event.outputs
    : context.children[key]?.outputs ?? [];
}

function allAcceptingAfter(
  context: EditionMachineContext,
  event: EditionMachineEvent,
  keys: readonly string[],
): boolean {
  return keys.every((key) => {
    const status = statusAfter(context, event, key);
    return status === "accepting" || status === "done";
  });
}

function sourceKeys(context: EditionMachineContext): readonly string[] {
  return context.sources.map((source) => sourceKey(source.sourceId));
}

function specWithCollectedSources(context: EditionMachineContext): EditionRunSpec {
  return { ...context.spec, sources: context.sources };
}

function plannedArticles(context: EditionMachineContext): readonly ArticleRunSpec[] {
  return context.resolvedPlan?.articles ?? context.spec.articles;
}

function plannedArt(context: EditionMachineContext): readonly RegisteredArtSpec[] {
  return context.resolvedPlan?.art ?? context.spec.art;
}

function plannedTranslations(
  context: EditionMachineContext,
): readonly TranslationRunSpec[] {
  return context.resolvedPlan?.translations ?? context.spec.translations;
}

function articleKeys(context: EditionMachineContext): readonly string[] {
  return plannedArticles(context).map((article) => articleKey(article.articleId));
}

function artKeys(context: EditionMachineContext): readonly string[] {
  return plannedArt(context).map((art) => artKey(art.key));
}

function translationKeys(context: EditionMachineContext): readonly string[] {
  return plannedTranslations(context).map((translation) =>
    translationKey(translation.language, context.reviewCycle),
  );
}

function readySourceExtractions(
  context: EditionMachineContext,
): readonly ReadySourceExtraction[] {
  return context.sources.flatMap((source) => {
    const result = context.children[sourceKey(source.sourceId)]?.result;
    const value = result?.extractionArtifactId;
    const approval = result?.approvalArtifactId;
    return typeof value === "string"
      ? [{
          sourceId: source.sourceId,
          extractionArtifactId: value as ArtifactId,
          ...(typeof approval === "string" ? { approvalArtifactId: approval as ArtifactId } : {}),
        }]
      : [];
  });
}

function productionPlanArtifact(
  event: EditionMachineEvent,
): CompletedArtifact | undefined {
  return event.type === "WORK_COMPLETED" && event.slot === "plan_edition"
    ? event.artifacts.find((artifact) => artifact.kind === "edition_plan")
    : undefined;
}

function resolvedPlanFromEvent(
  context: EditionMachineContext,
  event: EditionMachineEvent,
): ResolvedProductionPlan | undefined {
  if (productionPlanArtifact(event) === undefined || event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  try {
    const plan: ApprovedProductionPlan = parseApprovedProductionPlan(
      event.result.productionPlan,
    );
    return resolveApprovedProductionPlan(
      plan,
      specWithCollectedSources(context),
      readySourceExtractions(context),
    );
  } catch {
    return undefined;
  }
}

function productionPlanFailure(
  context: EditionMachineContext,
  event?: EditionMachineEvent,
): string {
  try {
    if (event === undefined) {
      resolvePreplannedProduction(
        specWithCollectedSources(context),
        readySourceExtractions(context),
      );
      return "Preplanned production inputs are valid";
    }
    const artifact = productionPlanArtifact(event);
    if (artifact === undefined) {
      return "The plan answer did not include an edition_plan artifact";
    }
    if (event.type !== "WORK_COMPLETED") {
      return "The plan answer did not complete work";
    }
    const plan = parseApprovedProductionPlan(event.result.productionPlan);
    resolveApprovedProductionPlan(
      plan,
      specWithCollectedSources(context),
      readySourceExtractions(context),
    );
    return "Approved production plan is valid";
  } catch (error) {
    if (error instanceof ProductionPlanError || error instanceof Error) {
      return error.message;
    }
    return "Approved production plan is invalid";
  }
}

function resultStatus(result: JsonObject): string | undefined {
  return typeof result.status === "string" ? result.status : undefined;
}

function choice(event: EditionMachineEvent): string | undefined {
  if (event.type !== "WORK_COMPLETED") {
    return undefined;
  }
  const value = event.result.choice ?? event.result.decision;
  return typeof value === "string" ? value : undefined;
}

function collectionCloseRequestArtifact(
  context: EditionMachineContext,
): ArtifactId {
  return `art_${context.actorId}_collection_close_request_${context.closeRequestOrdinal}` as ArtifactId;
}

function currentArticleArtifacts(context: EditionMachineContext): EditionReviewRunSpec["articleArtifacts"] {
  return plannedArticles(context).flatMap((article) => {
    const output = context.children[articleKey(article.articleId)]?.outputs[0];
    return output === undefined ? [] : [{ articleId: article.articleId, artifactId: output }];
  });
}

function currentEditorialArtifact(context: EditionMachineContext): ArtifactId | undefined {
  return context.children.editorial?.outputs[0];
}

function hasDeclaredDependencies(art: RegisteredArtSpec): boolean {
  return (
    art.dependencies?.editorial === true ||
    (art.dependencies?.articleIds.length ?? 0) > 0
  );
}

function dependencyArtifactsForArt(
  context: EditionMachineContext,
  art: RegisteredArtSpec,
  editorialArtifact?: ArtifactId,
): readonly ArtifactId[] | undefined {
  const articleArtifacts = (art.dependencies?.articleIds ?? []).map((articleId) =>
    context.children[articleKey(articleId)]?.outputs[0],
  );
  if (articleArtifacts.some((artifactId) => artifactId === undefined)) {
    return undefined;
  }
  const currentEditorial = editorialArtifact ?? currentEditorialArtifact(context);
  if (art.dependencies?.editorial === true && currentEditorial === undefined) {
    return undefined;
  }
  return [
    ...articleArtifacts.filter((value): value is ArtifactId => value !== undefined),
    ...(art.dependencies?.editorial === true && currentEditorial !== undefined
      ? [currentEditorial]
      : []),
  ];
}

function reviewSpec(context: EditionMachineContext): EditionReviewRunSpec | undefined {
  const editorialArtifact = currentEditorialArtifact(context);
  const articleArtifacts = currentArticleArtifacts(context);
  if (
    editorialArtifact === undefined ||
    articleArtifacts.length !== plannedArticles(context).length
  ) {
    return undefined;
  }
  return {
    editionId: context.spec.editionId,
    editionBrief: context.spec.editionBrief,
    articleArtifacts,
    editorialArtifact,
    modelPolicy: context.spec.modelPolicy,
  };
}

function routedKeys(result: JsonObject): readonly string[] {
  if (!Array.isArray(result.routes)) {
    return [];
  }
  return result.routes.flatMap((route) => {
    if (typeof route !== "object" || route === null || Array.isArray(route)) {
      return [];
    }
    return typeof route.target === "string" && route.target !== "editorial"
      ? [articleKey(route.target)]
      : [];
  });
}

function routedFindings(result: JsonObject): readonly {
  readonly target: string;
  readonly findingArtifactId: ArtifactId;
}[] {
  if (!Array.isArray(result.routes)) {
    return [];
  }
  return result.routes.flatMap((route) => {
    if (typeof route !== "object" || route === null || Array.isArray(route)) {
      return [];
    }
    return typeof route.target === "string" && typeof route.findingArtifactId === "string"
      ? [{ target: route.target, findingArtifactId: route.findingArtifactId as ArtifactId }]
      : [];
  });
}

function generatedArtifactId(
  context: EditionMachineContext,
  kind: "render-manifest" | "render-set",
): ArtifactId {
  return `art_${context.actorId}_${kind}_${context.renderCycle}` as ArtifactId;
}

function currentContentArtifacts(context: EditionMachineContext): readonly ArtifactId[] {
  return [
    ...plannedArticles(context).flatMap(
      (article) => context.children[articleKey(article.articleId)]?.outputs ?? [],
    ),
    ...(context.children.editorial?.outputs ?? []),
  ];
}

function currentTranslationArtifacts(context: EditionMachineContext): readonly ArtifactId[] {
  return translationKeys(context).flatMap((key) => {
    const child = context.children[key];
    const declared = child?.result.translationArtifactIds;
    return Array.isArray(declared) && declared.every((value) => typeof value === "string")
      ? declared.map((value) => value as ArtifactId)
      : child?.outputs ?? [];
  });
}

function currentTranslationProofArtifacts(
  context: EditionMachineContext,
): readonly ArtifactId[] {
  return translationKeys(context).flatMap((key) => {
    const result = context.children[key]?.result ?? {};
    return [
      result.reviewArtifactId,
      result.measurementArtifactId,
      result.editorDecisionArtifactId,
    ].filter((value): value is ArtifactId => typeof value === "string");
  });
}

function currentArtArtifacts(context: EditionMachineContext): readonly ArtifactId[] {
  return artKeys(context).flatMap((key) => context.children[key]?.outputs ?? []);
}

function currentSourceArtifacts(context: EditionMachineContext): readonly ArtifactId[] {
  return [...new Set([
    ...context.sources.flatMap(sourceInputArtifacts),
    ...sourceKeys(context).flatMap((key) => context.children[key]?.outputs ?? []),
  ])];
}

function sourceInputArtifacts(source: SourceRunSpec): readonly ArtifactId[] {
  return [
    source.leadArtifact,
    source.captureProfileArtifact,
    ...(source.captureInputArtifacts ?? []),
    source.rawBundleArtifact,
    ...(source.rawEvidenceArtifacts ?? []),
    source.extractionArtifact,
    source.metadataArtifact,
    source.approvalArtifact,
  ].filter((value): value is ArtifactId => value !== undefined);
}

export const editionMachine = setup({
  types: {
    context: {} as EditionMachineContext,
    events: {} as EditionMachineEvent,
    input: {} as EditionMachineInput,
  },
  guards: {
    noSources: ({ context }) => context.sources.length === 0,
    allSourcesReady: ({ context, event }) =>
      allAcceptingAfter(context, event, sourceKeys(context)),
    allSourcesCurrentlyReady: ({ context }) =>
      allAcceptingAfter(context, { type: "START" }, sourceKeys(context)),
    hasPlanning: ({ context }) => context.planningArtifact !== undefined,
    hasValidPreplannedProduction: ({ context }) => {
      if (context.planningArtifact === undefined) {
        return false;
      }
      try {
        resolvePreplannedProduction(
          specWithCollectedSources(context),
          readySourceExtractions(context),
        );
        return true;
      } catch {
        return false;
      }
    },
    collectionClosed: ({ context, event }) =>
      event.type === "WORK_COMPLETED" &&
      event.slot === "close_collection" &&
      event.taskArtifactId === collectionCloseRequestArtifact(context) &&
      ["close", "closed", "approve"].includes(choice(event) ?? ""),
    planCompleted: ({ context, event }) =>
      resolvedPlanFromEvent(context, event) !== undefined,
    planAnswerCompleted: ({ event }) =>
      event.type === "WORK_COMPLETED" && event.slot === "plan_edition",
    allArticlesReady: ({ context, event }) =>
      allAcceptingAfter(context, event, articleKeys(context)),
    allArticlesCurrentlyReady: ({ context }) =>
      articleKeys(context).every((key) => {
        const status = context.children[key]?.status;
        return status === "accepting" || status === "done";
      }),
    editorialAndArtReady: ({ context, event }) =>
      allAcceptingAfter(context, event, ["editorial", ...artKeys(context)]),
    editorialCompletedWithDependentArt: ({ context, event }) =>
      event.type === "CHILD_STATUS" &&
      event.childKey === "editorial" &&
      (event.status === "accepting" || event.status === "done") &&
      plannedArt(context).some(hasDeclaredDependencies),
    reviewApproved: ({ context, event }) => {
      const key = reviewKey(context.reviewCycle);
      return (
        (statusAfter(context, event, key) === "accepting" ||
          statusAfter(context, event, key) === "done") &&
        resultStatus(resultAfter(context, event, key)) === "approved"
      );
    },
    reviewRouted: ({ context, event }) =>
      resultStatus(resultAfter(context, event, reviewKey(context.reviewCycle))) ===
      "revisions_routed",
    allTranslationsReady: ({ context, event }) =>
      allAcceptingAfter(context, event, translationKeys(context)),
    noTranslations: ({ context }) => plannedTranslations(context).length === 0,
    renderApproved: ({ context, event }) =>
      statusAfter(context, event, renderKey(context.renderCycle)) === "accepting" &&
      resultStatus(resultAfter(context, event, renderKey(context.renderCycle))) === "approved",
    releaseComplete: ({ context, event }) =>
      statusAfter(context, event, `release:${context.renderCycle}`) === "accepting" &&
      resultStatus(resultAfter(context, event, `release:${context.renderCycle}`)) === "released",
    releaseDryRunComplete: ({ context, event }) =>
      statusAfter(context, event, `release:${context.renderCycle}`) === "done" &&
      resultStatus(resultAfter(context, event, `release:${context.renderCycle}`)) ===
        "dry_run_complete",
    releaseRejected: ({ context, event }) =>
      statusAfter(context, event, `release:${context.renderCycle}`) === "done" &&
      resultStatus(resultAfter(context, event, `release:${context.renderCycle}`)) ===
        "release_rejected",
    childFailed: ({ event }) => event.type === "CHILD_STATUS" && event.status === "failed",
    childNeedsEditor: ({ event }) =>
      event.type === "CHILD_STATUS" &&
      resultStatus(event.result) === "dropped",
    humanRetries: ({ event }) => choice(event) === "retry" || choice(event) === "resume",
  },
  actions: {
    spawnSources: emitEffects(({ context }) =>
      context.sources.map((source: EditionRunSpec["sources"][number]) =>
        spawn(context, "source", sourceKey(source.sourceId), source),
      ),
    ),
    spawnReceivedSource: emitEffects(({ context, event }) =>
      event.type === "LEAD_RECEIVED"
        ? [spawn(context, "source", sourceKey(event.source.sourceId), event.source)]
        : [],
    ),
    rememberReceivedSource: assign(({ context, event }) => {
      if (
        event.type !== "LEAD_RECEIVED" ||
        context.sources.some((source) => source.sourceId === event.source.sourceId)
      ) {
        return {};
      }
      return { sources: [...context.sources, event.source] };
    }),
    offerCloseCollection: emitEffects(({ context }) => {
      const sourceArtifacts = currentSourceArtifacts(context);
      return humanDecisionOffer({
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "collecting",
        role: "close_collection",
        slot: "close_collection",
        requestArtifactId: collectionCloseRequestArtifact(context),
        requestSchemaVersion: "collection-close-request/1",
        requestKind: "collection_close",
        subjectArtifactId: context.spec.editionBrief,
        inputArtifacts: [context.spec.editionBrief, ...sourceArtifacts],
        allowedChoices: ["approve", "close", "closed"],
        contractVersion: "close-collection/1",
        details: {
          editionId: context.spec.editionId,
          editionBriefArtifactId: context.spec.editionBrief,
          sourceArtifactIds: sourceArtifacts,
        },
      });
    }),
    recordCollectionClose: emitEffects(({ context, event }) => {
      const decisionArtifactId = event.type === "WORK_COMPLETED"
        ? event.artifacts.find(
            (artifact: CompletedArtifact) => artifact.kind === "collection_decision",
          )?.artifactId
        : undefined;
      return [
        effect({
          type: "record_decision",
          actorId: context.actorId,
          choice: "close_collection",
          authority: "human",
          ...(decisionArtifactId === undefined ? {} : { artifactId: decisionArtifactId }),
          details: {
            editionId: context.spec.editionId,
            sourceArtifactIds: currentSourceArtifacts(context),
          },
        }),
      ];
    }),
    offerPlan: emitEffects(({ context }) =>
      context.planningArtifact !== undefined
        ? []
        : humanDecisionOffer({
            actorId: context.actorId,
            actorKey: context.logicalKey,
            state: "planning",
            role: "plan_edition",
            slot: "plan_edition",
            requestArtifactId:
              `art_${context.actorId}_edition_plan_request_${context.planRequestOrdinal}` as ArtifactId,
            requestSchemaVersion: "edition-plan-request/1",
            requestKind: "edition_planning",
            subjectArtifactId: context.spec.editionBrief,
            inputArtifacts: [
              context.spec.editionBrief,
              ...currentSourceArtifacts(context),
            ],
            allowedChoices: ["accept", "approve"],
            contractVersion: "edition-plan/1",
            details: {
              editionId: context.spec.editionId,
              editionBriefArtifactId: context.spec.editionBrief,
              readySources: readySourceExtractions(context).map((source) => ({
                sourceId: source.sourceId,
                extractionArtifactId: source.extractionArtifactId,
              })),
              configuredLanguages: context.spec.render.configuredLanguages,
              sourceAssignmentPolicy:
                context.spec.sourceAssignmentPolicy ?? "at_least_once",
            },
          }),
    ),
    recordPlanningDecision: emitEffects(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "plan_edition") {
        return [];
      }
      const planArtifactId = event.artifacts.find(
        (artifact: CompletedArtifact) => artifact.kind === "edition_plan",
      )?.artifactId;
      return [effect({
        type: "record_decision",
        actorId: context.actorId,
        choice: choice(event) ?? "approve",
        authority: "human",
        ...(planArtifactId === undefined ? {} : { artifactId: planArtifactId }),
        details: {
          editionId: context.spec.editionId,
          articleIds:
            resolvedPlanFromEvent(context, event)?.articles.map(
              (article) => article.articleId,
            ) ?? [],
          sourceArtifactIds: currentSourceArtifacts(context),
        },
      })];
    }),
    spawnArticlesAndArt: emitEffects(({ context }) => [
      ...plannedArticles(context).map((article) =>
        spawn(context, "article", articleKey(article.articleId), article),
      ),
      ...plannedArt(context).filter((art) => !hasDeclaredDependencies(art)).map((art) =>
        spawn(
          context,
          art.role === "cover" ? "cover_art" : "interior_art",
          artKey(art.key),
          art,
        ),
      ),
    ]),
    refreshDependentArt: emitEffects(({ context, event }) => {
      if (event.type !== "CHILD_STATUS" || event.childKey !== "editorial") {
        return [];
      }
      const editorialArtifact = event.outputs[0];
      return plannedArt(context).flatMap((art) => {
        if (!hasDeclaredDependencies(art)) {
          return [];
        }
        const dependencyArtifacts = dependencyArtifactsForArt(
          context,
          art,
          editorialArtifact,
        );
        if (dependencyArtifacts === undefined) {
          return [];
        }
        if (context.children[artKey(art.key)] === undefined) {
          return [
            spawn(
              context,
              art.role === "cover" ? "cover_art" : "interior_art",
              artKey(art.key),
              { ...art, dependencyArtifacts },
            ),
          ];
        }
        return [
          effect({
            type: "send_actor_event",
            actorId: context.actorId,
            target: { childKey: artKey(art.key) },
            event: {
              type: "REVISION_REQUESTED",
              dependencyArtifacts,
              reason: "Declared article or editorial dependencies changed",
            },
          }),
        ];
      });
    }),
    startEditorial: emitEffects(({ context }) => {
      if (context.children.editorial === undefined) {
        return [
          spawn(context, "editorial", "editorial", {
            ...context.spec.editorial,
            articleArtifacts: currentArticleArtifacts(context).map(
              (article) => article.artifactId,
            ),
          }),
        ];
      }
      return [
        effect({
          type: "send_actor_event",
          actorId: context.actorId,
          target: { childKey: "editorial" },
          event: {
            type: "REVISION_REQUESTED",
            articleArtifacts: currentArticleArtifacts(context).map(
              (article) => article.artifactId,
            ),
            findingArtifacts: context.routedFindingArtifacts,
            reason: "English articles changed after edition review",
          },
        }),
      ];
    }),
    startEditionReview: emitEffects(({ context }) => {
      const spec = reviewSpec(context);
      return spec === undefined
        ? []
        : [spawn(context, "edition_review", reviewKey(context.reviewCycle), spec)];
    }),
    spawnTranslations: emitEffects(({ context }) =>
      plannedTranslations(context).map(
        (translation) =>
        spawn(
          context,
          "translation",
          translationKey(translation.language, context.reviewCycle),
          {
            ...translation,
            englishArtifacts: currentContentArtifacts(context),
          },
        ),
      ),
    ),
    registerRenderManifest: emitEffects(({ context }) => {
      const content = currentContentArtifacts(context);
      const translations = currentTranslationArtifacts(context);
      const translationProofs = currentTranslationProofArtifacts(context);
      const art = currentArtArtifacts(context);
      const editionApproval =
        context.children[reviewKey(context.reviewCycle)]?.outputs ?? [];
      const parents = [
        ...content.map((artifactId: ArtifactId) => ({ artifactId, relation: "content" })),
        ...translations.map((artifactId: ArtifactId) => ({
          artifactId,
          relation: "translation",
        })),
        ...translationProofs.map((artifactId: ArtifactId) => ({
          artifactId,
          relation: "translation_approval",
        })),
        ...art.map((artifactId: ArtifactId) => ({ artifactId, relation: "selected_art" })),
        ...editionApproval.map((artifactId: ArtifactId) => ({
          artifactId,
          relation: "edition_approval",
        })),
        {
          artifactId: context.spec.render.renderManifestArtifact,
          relation: "render_profile",
        },
        ...(context.spec.render.printerProfileArtifact === undefined
          ? []
          : [
              {
                artifactId: context.spec.render.printerProfileArtifact,
                relation: "printer_profile",
              },
            ]),
      ];
      return [
        effect({
          type: "register_artifact",
          actorId: context.actorId,
          slot: "render_manifest",
          artifact: {
            id: generatedArtifactId(context, "render-manifest"),
            kind: "render_manifest",
            schemaVersion: "1",
            mediaType: "application/json",
            origin: "machine",
            payload: {
              kind: "json",
              value: {
                editionId: context.spec.editionId,
                content,
                translations,
                translationProofs,
                art,
                editionApproval,
                configuredLanguages: context.spec.render.configuredLanguages,
                renderProfileArtifactId: context.spec.render.renderManifestArtifact,
                printerProfileArtifactId:
                  context.spec.render.printerProfileArtifact ?? null,
              },
            },
            parents,
          },
        }),
      ];
    }),
    spawnRender: emitEffects(({ context }) => [
      spawn(context, "render", renderKey(context.renderCycle), {
        ...context.spec.render,
        renderManifestArtifact: generatedArtifactId(context, "render-manifest"),
      }),
    ]),
    registerRenderSet: emitEffects(({ context }) => {
      const child = context.children[renderKey(context.renderCycle)];
      const declared = child?.result.renderArtifactIds;
      const renderArtifacts =
        Array.isArray(declared) && declared.every((value) => typeof value === "string")
          ? declared.map((value) => value as ArtifactId)
          : child?.outputs ?? [];
      const inspectionArtifactId =
        typeof child?.result.inspectionArtifactId === "string"
          ? child.result.inspectionArtifactId as ArtifactId
          : undefined;
      const visualDecisionArtifactId =
        typeof child?.result.visualDecisionArtifactId === "string"
          ? child.result.visualDecisionArtifactId as ArtifactId
          : undefined;
      const printerPreflightArtifactIds =
        Array.isArray(child?.result.printerPreflightArtifactIds) &&
        child.result.printerPreflightArtifactIds.every(
          (value: unknown) => typeof value === "string",
        )
          ? child.result.printerPreflightArtifactIds.map(
              (value: unknown) => value as ArtifactId,
            )
          : [];
      return [
        effect({
          type: "register_artifact",
          actorId: context.actorId,
          slot: "approved_render_set",
          artifact: {
            id: generatedArtifactId(context, "render-set"),
            kind: "approved_render_set",
            schemaVersion: "1",
            mediaType: "application/json",
            origin: "machine",
            payload: {
              kind: "json",
              value: {
                editionId: context.spec.editionId,
                renderArtifactIds: renderArtifacts,
                inspectionArtifactId: inspectionArtifactId ?? null,
                visualDecisionArtifactId: visualDecisionArtifactId ?? null,
                printerProfileArtifactId:
                  context.spec.render.printerProfileArtifact ?? null,
                printerPreflightArtifactIds,
                studioPolicy: context.spec.render.studioPolicy,
                studioReady: child?.result.studioReady === true,
              },
            },
            parents: [
              ...renderArtifacts.map((artifactId: ArtifactId) => ({
                artifactId,
                relation: "approved_render",
              })),
              ...(inspectionArtifactId === undefined
                ? []
                : [{ artifactId: inspectionArtifactId, relation: "render_inspection" }]),
              ...(visualDecisionArtifactId === undefined
                ? []
                : [{ artifactId: visualDecisionArtifactId, relation: "visual_approval" }]),
            ],
          },
        }),
      ];
    }),
    spawnRelease: emitEffects(({ context }) => {
      const renderResult = context.children[renderKey(context.renderCycle)]?.result ?? {};
      const printerPreflightArtifacts =
        Array.isArray(renderResult.printerPreflightArtifactIds) &&
        renderResult.printerPreflightArtifactIds.every(
          (value: unknown) => typeof value === "string",
        )
          ? renderResult.printerPreflightArtifactIds.map(
              (value: unknown) => value as ArtifactId,
            )
          : [];
      const spec = {
        ...context.spec.release,
        publicationArtifact: generatedArtifactId(context, "render-set"),
        sourceArtifacts: currentSourceArtifacts(context),
        ...(context.spec.render.printerProfileArtifact === undefined
          ? {}
          : { printerProfileArtifact: context.spec.render.printerProfileArtifact }),
        printerPreflightArtifacts,
        studioReady: renderResult.studioReady === true,
      };
      return [spawn(context, "release", `release:${context.renderCycle}`, spec)];
    }),
    retryRelease: emitEffects(({ context }) => [
      effect({
        type: "send_actor_event",
        actorId: context.actorId,
        target: { childKey: `release:${context.renderCycle}` },
        event: { type: "RETRY" },
      }),
    ]),
    routeReviewFindings: emitEffects(({ context, event }) => {
      if (event.type !== "CHILD_STATUS") {
        return [];
      }
      const routes = routedFindings(event.result);
      const findingsByArticle = new Map<string, ArtifactId[]>();
      for (const route of routes) {
        if (route.target === "editorial") {
          continue;
        }
        const findings = findingsByArticle.get(route.target) ?? [];
        findings.push(route.findingArtifactId);
        findingsByArticle.set(route.target, findings);
      }
      const articleEffects = [...findingsByArticle.entries()].map(
        ([target, findingArtifacts]) =>
          effect({
            type: "send_actor_event",
            actorId: context.actorId,
            target: { childKey: articleKey(target) },
            event: {
              type: "REVISION_REQUESTED",
              findingArtifacts,
              reason: "Edition review routed a finding",
            },
          }),
      );
      return articleEffects;
    }),
    offerEditor: emitEffects(({ context }) =>
      humanDecisionOffer({
        actorId: context.actorId,
        actorKey: context.logicalKey,
        state: "awaiting_editor",
        role: "editor_decision",
        slot: "editor_decision",
        requestArtifactId:
          `art_${context.actorId}_edition_editor_request_${context.editorRequestOrdinal}` as ArtifactId,
        requestSchemaVersion: "edition-editor-request/1",
        requestKind: "edition_editor_decision",
        subjectArtifactId: context.spec.editionBrief,
        inputArtifacts: [
          context.spec.editionBrief,
          ...currentContentArtifacts(context),
          ...context.routedFindingArtifacts,
        ],
        allowedChoices: ["drop", "resume", "retry"],
        contractVersion: "edition-editor/1",
        details: {
          editionId: context.spec.editionId,
          reviewCycle: context.reviewCycle,
          routedArticleKeys: context.routedArticleKeys,
          findingArtifactIds: context.routedFindingArtifacts,
          lastFailure: context.lastFailure ?? null,
        },
      }),
    ),
    publishReleased: emitEffects(({ context }) => {
      const outputs = context.children[`release:${context.renderCycle}`]?.outputs ?? [];
      return [
        effect({
          type: "complete_actor",
          actorId: context.actorId,
          accepting: true,
          outputs,
          result: { editionId: context.spec.editionId, status: "released" },
        }),
      ];
    }),
    publishDryRun: emitEffects(({ context }) => {
      const outputs = context.children[`release:${context.renderCycle}`]?.outputs ?? [];
      return [
        effect({
          type: "complete_actor",
          actorId: context.actorId,
          accepting: false,
          outputs,
          result: { editionId: context.spec.editionId, status: "dry_run_complete" },
        }),
      ];
    }),
    publishFailure: emitEffects(({ context }) => [
      effect({
        type: "fail_actor",
        actorId: context.actorId,
        classification: "edition_failed",
        message: context.lastFailure ?? "Edition production failed",
      }),
    ]),
    rememberChild: assign(({ context, event }) => {
      if (event.type === "CHILD_SPAWNED") {
        const current = context.children[event.childKey];
        return {
          children: {
            ...context.children,
            [event.childKey]: {
              ...(current ?? {
                status: "active" as const,
                outputs: [],
                result: {},
              }),
              actorId: event.childActorId,
              machine: event.machine,
            },
          },
        };
      }
      if (event.type === "CHILD_STATUS") {
        return {
          children: {
            ...context.children,
            [event.childKey]: {
              ...context.children[event.childKey],
              actorId: event.childActorId,
              status: event.status,
              outputs: event.outputs,
              result: event.result,
            },
          },
        };
      }
      return {};
    }),
    keepPlan: assign(({ context, event }) => {
      if (event.type !== "WORK_COMPLETED" || event.slot !== "plan_edition") {
        return {};
      }
      return {
        planningArtifact:
          event.artifacts.find((item) => item.kind === "edition_plan")?.artifactId ??
          context.planningArtifact,
        resolvedPlan: resolvedPlanFromEvent(context, event),
      };
    }),
    keepPreplannedProduction: assign(({ context }) => ({
      resolvedPlan: resolvePreplannedProduction(
        specWithCollectedSources(context),
        readySourceExtractions(context),
      ),
    })),
    rememberInvalidPreplannedProduction: assign(({ context }) => ({
      lastFailure: productionPlanFailure(context),
    })),
    rememberInvalidProductionPlan: assign(({ context, event }) => ({
      lastFailure: productionPlanFailure(context, event),
    })),
    beginRoutedRevision: assign(({ context, event }) => {
      if (event.type !== "CHILD_STATUS") {
        return {};
      }
      const routed = routedKeys(event.result);
      const children = { ...context.children };
      for (const key of routed) {
        const current = children[key];
        if (current !== undefined) {
          children[key] = { ...current, status: "active" };
        }
      }
      const editorial = children.editorial;
      if (editorial !== undefined) {
        children.editorial = { ...editorial, status: "active" };
      }
      for (const art of plannedArt(context).filter(hasDeclaredDependencies)) {
        const key = artKey(art.key);
        const current = children[key];
        if (current !== undefined) {
          children[key] = { ...current, status: "active" };
        }
      }
      return {
        children,
        routedArticleKeys: routed,
        routedFindingArtifacts: routedFindings(event.result).map(
          (route) => route.findingArtifactId,
        ),
        reviewCycle: context.reviewCycle + 1,
      };
    }),
    rememberFailure: assign(({ event }) => ({
      lastFailure:
        event.type === "WORK_FAILED"
          ? event.message
          : event.type === "CHILD_STATUS"
            ? `Child ${event.childKey} failed`
            : "Edition production failed",
    })),
    clearFailure: assign({ lastFailure: undefined }),
    bumpCloseRequest: assign(({ context }) => ({
      closeRequestOrdinal: context.closeRequestOrdinal + 1,
    })),
    bumpPlanRequest: assign(({ context }) => ({
      planRequestOrdinal: context.planRequestOrdinal + 1,
    })),
    bumpEditorRequest: assign(({ context }) => ({
      editorRequestOrdinal: context.editorRequestOrdinal + 1,
    })),
  },
}).createMachine({
  id: "edition",
  version: editionMachineVersion,
  initial: "idle",
  context: ({ input }) => ({
    actorId: input.actorId,
    logicalKey: input.logicalKey,
    ...(input.parentActorId === undefined ? {} : { parentActorId: input.parentActorId }),
    spec: input.spec,
    sources: input.spec.sources,
    children: {},
    planningArtifact: input.spec.planningArtifact,
    resolvedPlan: undefined,
    reviewCycle: 0,
    renderCycle: 0,
    closeRequestOrdinal: 0,
    planRequestOrdinal: 0,
    editorRequestOrdinal: 0,
    routedArticleKeys: [],
    routedFindingArtifacts: [],
    lastFailure: undefined,
  }),
  states: {
    idle: {
      on: {
        START: { actions: "spawnSources", target: "collecting" },
      },
    },
    collecting: {
      entry: ["bumpCloseRequest", "offerCloseCollection"],
      on: {
        LEAD_RECEIVED: {
          actions: ["rememberReceivedSource", "spawnReceivedSource"],
          target: "collecting",
          reenter: true,
        },
        WORK_COMPLETED: {
          guard: "collectionClosed",
          actions: "recordCollectionClose",
          target: "collection_closed",
        },
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { actions: "rememberChild" },
        ],
      },
    },
    collection_closed: {
      always: {
        guard: "allSourcesCurrentlyReady",
        target: "planning",
      },
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          {
            guard: "childFailed",
            actions: ["rememberChild", "rememberFailure"],
            target: "failed",
          },
          {
            guard: "allSourcesReady",
            actions: "rememberChild",
            target: "planning",
          },
          { actions: "rememberChild" },
        ],
      },
    },
    planning: {
      entry: ["bumpPlanRequest", "offerPlan"],
      always: [
        {
          guard: "hasValidPreplannedProduction",
          actions: "keepPreplannedProduction",
          target: "producing_articles",
        },
        {
          guard: "hasPlanning",
          actions: "rememberInvalidPreplannedProduction",
          target: "failed",
        },
      ],
      on: {
        WORK_COMPLETED: [
          {
            guard: "planCompleted",
            actions: ["keepPlan", "recordPlanningDecision"],
            target: "producing_articles",
          },
          {
            guard: "planAnswerCompleted",
            actions: "rememberInvalidProductionPlan",
            target: "failed",
          },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    producing_articles: {
      entry: "spawnArticlesAndArt",
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "childNeedsEditor", actions: "rememberChild", target: "awaiting_editor" },
          { guard: "allArticlesReady", actions: "rememberChild", target: "producing_editorial" },
          { actions: "rememberChild" },
        ],
      },
    },
    producing_editorial: {
      entry: "startEditorial",
      always: { guard: "editorialAndArtReady", target: "edition_review" },
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "childNeedsEditor", actions: "rememberChild", target: "awaiting_editor" },
          {
            guard: "editorialCompletedWithDependentArt",
            actions: ["rememberChild", "refreshDependentArt"],
          },
          { guard: "editorialAndArtReady", actions: "rememberChild", target: "edition_review" },
          { actions: "rememberChild" },
        ],
      },
    },
    edition_review: {
      entry: "startEditionReview",
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "reviewApproved", actions: "rememberChild", target: "translating" },
          {
            guard: "reviewRouted",
            actions: [
              "rememberChild",
              "routeReviewFindings",
              "beginRoutedRevision",
            ],
            target: "revising_content",
          },
          { guard: "childNeedsEditor", actions: "rememberChild", target: "awaiting_editor" },
          { actions: "rememberChild" },
        ],
      },
    },
    revising_content: {
      always: {
        guard: "allArticlesCurrentlyReady",
        target: "producing_editorial",
      },
      on: {
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "allArticlesReady", actions: "rememberChild", target: "producing_editorial" },
          { actions: "rememberChild" },
        ],
      },
    },
    translating: {
      entry: "spawnTranslations",
      always: { guard: "noTranslations", target: "assembling" },
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "allTranslationsReady", actions: "rememberChild", target: "assembling" },
          { actions: "rememberChild" },
        ],
      },
    },
    assembling: { entry: "registerRenderManifest", always: "rendering" },
    rendering: {
      entry: "spawnRender",
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "renderApproved", actions: "rememberChild", target: "awaiting_release_approval" },
          { actions: "rememberChild" },
        ],
      },
    },
    awaiting_release_approval: {
      entry: ["registerRenderSet", "spawnRelease"],
      on: {
        CHILD_SPAWNED: { actions: "rememberChild" },
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "releaseComplete", actions: "rememberChild", target: "released" },
          {
            guard: "releaseDryRunComplete",
            actions: "rememberChild",
            target: "dry_run_complete",
          },
          {
            guard: "releaseRejected",
            actions: "rememberChild",
            target: "release_rejected",
          },
          { actions: "rememberChild" },
        ],
      },
    },
    release_rejected: {
      on: {
        RETRY: { actions: "retryRelease", target: "retrying_release" },
      },
    },
    retrying_release: {
      on: {
        CHILD_STATUS: [
          { guard: "childFailed", actions: ["rememberChild", "rememberFailure"], target: "failed" },
          { guard: "releaseComplete", actions: "rememberChild", target: "released" },
          {
            guard: "releaseDryRunComplete",
            actions: "rememberChild",
            target: "dry_run_complete",
          },
          { guard: "releaseRejected", actions: "rememberChild", target: "release_rejected" },
          { actions: "rememberChild" },
        ],
      },
    },
    awaiting_editor: {
      entry: ["bumpEditorRequest", "offerEditor"],
      on: {
        WORK_COMPLETED: [
          { guard: "humanRetries", target: "revising_content" },
          { actions: "rememberFailure", target: "failed" },
        ],
        WORK_FAILED: { actions: "rememberFailure", target: "failed" },
      },
    },
    released: { entry: "publishReleased", type: "final" },
    dry_run_complete: { entry: "publishDryRun", type: "final" },
    failed: {
      entry: "publishFailure",
      on: { RETRY: { actions: "clearFailure", target: "revising_content" } },
    },
  },
});

export function editionInitial(input: EditionMachineInput) {
  return initialMachineTransition(editionMachine, input);
}

export function editionTransition(
  snapshot: JsonMachineSnapshot,
  event: EditionMachineEvent,
) {
  return transitionMachine(editionMachine, snapshot, event);
}
