import type { WorkflowContext } from "loops";
import { stringify as stringifyYaml } from "yaml";
import { createHash } from "node:crypto";
import { assertTranslatedMarkdownStructure } from "../executors/closed-translation-writer/markdown.ts";

import type { ArtifactId, JsonObject, RevisionId, RunId } from "../contracts/index.ts";
import type { InputRevisionRef, DurableRevisionRef } from "../durable/types.ts";
import type { ArticleRuntimeStartArgs, ArticleWorkflowPorts } from "./internal-types.ts";
import { magazineArticleWorkflowRef, magazineEditorialWorkflowRef } from "./magazine-workflow-resolver.ts";
import type { OpeningEditorialWorkflowArgs, OpeningEditorialWorkflowResult } from "./editorial-workflow.ts";

export const EDITION_WORKFLOW_NAME = "magazine-edition" as const;
export const EDITION_WORKFLOW_SCHEMA = "magazine-edition-workflow/1" as const;

export type EditionSourceLineage = {
  readonly sourceId: string;
  readonly capture: InputRevisionRef;
  readonly extraction: InputRevisionRef;
  readonly captureArtifactIds: readonly ArtifactId[];
  readonly extractionArtifactIds: readonly ArtifactId[];
};

export type EditionArticleChild = {
  readonly articleId: string;
  readonly articleExecutionId: string;
  readonly runId: RunId;
  readonly sourceIds: readonly string[];
  readonly sourceLineage: readonly EditionSourceLineage[];
  readonly args: ArticleRuntimeStartArgs;
};

export type EditionEditorialPlan = {
  readonly schemaVersion: "edition-editorial-plan/1";
  readonly editorialId: "opening";
  readonly brief: string;
  readonly maximumReaderPages: 1;
  readonly maximumRewrites: number;
  readonly profileArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly reviewInputArtifactIds: readonly ArtifactId[];
};

export type EditionTranslationPlan = {
  readonly schemaVersion: "edition-translation-plan/1";
  readonly language: "es";
  readonly sourceLanguage: "en";
  readonly promptRevision: InputRevisionRef;
  readonly promptArtifactId: ArtifactId;
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly inputArtifactBindings: readonly { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef }[];
  readonly maximumReaderPages: 7;
  readonly pieceIds: readonly string[];
  readonly parentRevisionIds: Readonly<Record<string, string | null>>;
};

export type EditionPlanCheckpoint = {
  readonly schemaVersion: "edition-plan-checkpoint/1";
  readonly editionId: "004";
  readonly pipelineRef: Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>;
  readonly pipelineDigest: string;
  readonly articleIds: readonly string[];
  readonly children: readonly {
    readonly articleId: string;
    readonly articleExecutionId: string;
    readonly runId: RunId;
    readonly sourceIds: readonly string[];
    readonly sourceLineage: readonly EditionSourceLineage[];
  }[];
  readonly selectedImageRevisions: readonly DurableRevisionRef[];
  readonly layoutInputRevisions: readonly InputRevisionRef[];
  readonly layoutInputArtifactIds: readonly ArtifactId[];
  readonly layoutInputBindings: readonly { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef }[];
  readonly imageGenerationAllowed: false;
  readonly editorial: EditionEditorialPlan;
  readonly translations: readonly EditionTranslationPlan[];
};

export type AcceptedEnglishArticle = {
  readonly ordinal: number;
  readonly articleId: string;
  readonly articleExecutionId: string;
  readonly childRunId: RunId;
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly decisionArtifactId: ArtifactId;
  readonly durableRevisionId: string;
};

export type AcceptedEnglishIssueInputs = {
  readonly schemaVersion: "accepted-english-issue-inputs/1";
  readonly editionId: "004";
  readonly pipelineRef: EditionPlanCheckpoint["pipelineRef"];
  readonly pipelineDigest: string;
  readonly articleCount: 7;
  readonly articles: readonly AcceptedEnglishArticle[];
};

type TranslationTask = {
  readonly pieceKind: "article" | "editorial";
  readonly pieceId: string;
  readonly translationExecutionId: string;
  readonly runId: RunId;
  readonly profileArtifactId: ArtifactId;
  readonly entryArtifactId: ArtifactId;
  readonly englishArtifactId: ArtifactId;
  readonly englishDigest: string;
  readonly englishRevision: DurableRevisionRef;
  readonly promptArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
  readonly inputArtifactBindings: readonly { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef }[];
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly expectedParentRevisionId: string | null;
};

type TranslatedPiece = {
  readonly pieceKind: "article" | "editorial";
  readonly pieceId: string;
  readonly englishArtifactId: ArtifactId;
  readonly translatedArtifactId: ArtifactId;
  readonly englishRevision: DurableRevisionRef;
  readonly spanishRevision: DurableRevisionRef;
  readonly promotion: import("./internal-types.ts").TranslationPromotionResult;
};

export type EditionWorkflowArgs = {
  readonly schemaVersion: typeof EDITION_WORKFLOW_SCHEMA;
  readonly editionId: "004";
  readonly runId: RunId;
  readonly editionExecutionId: string;
  readonly planArtifactId: ArtifactId;
  readonly entryArtifactId: ArtifactId;
  readonly plan: EditionPlanCheckpoint;
  readonly children: readonly EditionArticleChild[];
  readonly selectedImageRevisions: readonly DurableRevisionRef[];
  readonly imageGenerationAllowed: false;
};

export type EditionWorkflowChildResult = {
  readonly articleId: string;
  readonly articleExecutionId: string;
  readonly runId: RunId;
  readonly result: unknown;
};

export type EditionWorkflowResult = {
  readonly schemaVersion: "magazine-edition-workflow-result/1";
  readonly editionId: "004";
  readonly runId: RunId;
  readonly status: "articles_waiting" | "editorial_waiting" | "translation_waiting" | "complete";
  readonly articleExecutionIds: readonly string[];
  readonly children: readonly EditionWorkflowChildResult[];
  readonly selectedImageRevisions: readonly DurableRevisionRef[];
  readonly imageGenerationAllowed: false;
  readonly acceptedEnglishInputsArtifactId?: ArtifactId;
  readonly editorial?: OpeningEditorialWorkflowResult;
  readonly translationArtifactIds?: readonly ArtifactId[];
  readonly compositionArtifactId?: ArtifactId;
  readonly compositionRevisionId?: string;
};

export default async function run(
  context: WorkflowContext<EditionWorkflowArgs>,
  ports?: ArticleWorkflowPorts,
): Promise<EditionWorkflowResult> {
  const args = parseEditionWorkflowArgs(context.input);
  const plan = parseEditionPlanCheckpoint(await context.step(
    "edition.plan",
    () => parseEditionPlanCheckpoint(args.plan),
    { input: args.plan as unknown as JsonObject },
  ));
  const values = await context.parallel(plan.children.map((planned) => {
    const child = args.children.find((candidate) => candidate.articleId === planned.articleId);
    if (child === undefined) throw new Error(`Edition plan has no launch args for ${planned.articleId}`);
    return async () => {
      const result = await context.workflow(magazineArticleWorkflowRef(), child.args, { key: `article.${child.articleId}` });
      return { articleId: child.articleId, articleExecutionId: child.articleExecutionId, runId: child.runId, result } satisfies EditionWorkflowChildResult;
    };
  }));
  const children = values.filter((value): value is EditionWorkflowChildResult => value !== null);
  if (children.length !== plan.children.length) {
    return { schemaVersion: "magazine-edition-workflow-result/1", editionId: args.editionId, runId: args.runId, status: "articles_waiting", articleExecutionIds: plan.children.map((child) => child.articleExecutionId), children, selectedImageRevisions: args.selectedImageRevisions, imageGenerationAllowed: false };
  }
  if (ports === undefined) throw new Error("Edition English issue phase requires host-bound ports");
  const accepted = await context.step(
    "edition.english-inputs",
    () => freezeAcceptedEnglishInputs(args, plan, children, ports),
    { input: { editionId: args.editionId, pipelineRef: plan.pipelineRef as unknown as JsonObject, pipelineDigest: plan.pipelineDigest, childResults: children.map((child) => child.result) as unknown as JsonObject } },
  ) as { readonly artifactId: ArtifactId; readonly value: AcceptedEnglishIssueInputs };
  const editorialArgs = await context.step(
    "edition.editorial-inputs",
    () => createEditorialChildArgs(args, plan, accepted.artifactId, accepted.value, ports),
    { input: { acceptedEnglishInputsArtifactId: accepted.artifactId, articleArtifactIds: accepted.value.articles.map((article) => article.manuscriptArtifactId) as unknown as JsonObject, editorialProfileArtifactId: plan.editorial.profileArtifactId } },
  );
  const editorial = await context.workflow(magazineEditorialWorkflowRef(), editorialArgs, { key: "editorial.opening" }) as OpeningEditorialWorkflowResult;
  if (editorial.status !== "complete") {
    return { schemaVersion: "magazine-edition-workflow-result/1", editionId: args.editionId, runId: args.runId, status: "editorial_waiting", articleExecutionIds: plan.children.map((child) => child.articleExecutionId), children, selectedImageRevisions: args.selectedImageRevisions, imageGenerationAllowed: false, acceptedEnglishInputsArtifactId: accepted.artifactId, editorial };
  }
  // Keep the existing article/editorial integration fixtures useful while
  // the host does not opt into Spanish work. Production Edition 4 supplies
  // the closed translation worker and therefore takes the durable branch.
  if (ports.runTranslationWriter === undefined || ports.promoteTranslation === undefined) {
    return { schemaVersion: "magazine-edition-workflow-result/1", editionId: args.editionId, runId: args.runId, status: "complete", articleExecutionIds: plan.children.map((child) => child.articleExecutionId), children, selectedImageRevisions: args.selectedImageRevisions, imageGenerationAllowed: false, acceptedEnglishInputsArtifactId: accepted.artifactId, editorial };
  }
  const translationTasks = await context.step(
    "edition.translation.prepare",
    () => prepareTranslationTasks(args, plan, accepted.value, editorial, ports),
    { input: { acceptedEnglishInputsArtifactId: accepted.artifactId, editorialManuscriptArtifactId: editorial.manuscriptArtifactId, pieceIds: plan.translations[0]!.pieceIds as unknown as JsonObject } },
  );
  const translated = await context.parallel((translationTasks as readonly TranslationTask[]).map((task) => async () => {
    const execution = await ports.runTranslationWriter!({
      translationExecutionId: task.translationExecutionId,
      operationKey: `translation.writer.${task.pieceKind}.${safe(task.pieceId)}`,
      pieceKind: task.pieceKind,
      pieceId: task.pieceId,
      language: "es",
      englishArtifactId: task.englishArtifactId,
      englishDigest: task.englishDigest,
      promptArtifactId: task.promptArtifactId,
      inputArtifactIds: task.inputArtifactIds,
    }, context as unknown as import("./internal-types.ts").MagazineWorkflowContext);
    return await context.step(
      `edition.translation.promote.${task.pieceKind}.${safe(task.pieceId)}`,
      () => finalizeTranslation(args, task, execution, ports),
      { input: { pieceKind: task.pieceKind, pieceId: task.pieceId, englishArtifactId: task.englishArtifactId, promptArtifactId: task.promptArtifactId, inputArtifactIds: task.inputArtifactIds as unknown as JsonObject } },
    );
  }));
  const pieces = translated.filter((value): value is TranslatedPiece => value !== null);
  if (pieces.length !== translationTasks.length) {
    return { schemaVersion: "magazine-edition-workflow-result/1", editionId: args.editionId, runId: args.runId, status: "translation_waiting", articleExecutionIds: plan.children.map((child) => child.articleExecutionId), children, selectedImageRevisions: args.selectedImageRevisions, imageGenerationAllowed: false, acceptedEnglishInputsArtifactId: accepted.artifactId, editorial, translationArtifactIds: pieces.map((piece) => piece.translatedArtifactId) };
  }
  const composition = await context.step(
    "edition.composition.finalize",
    () => finalizeComposition(args, plan, accepted.value, editorial, pieces, ports),
    { input: { acceptedEnglishInputsArtifactId: accepted.artifactId, editorialManuscriptArtifactId: editorial.manuscriptArtifactId, translatedArtifactIds: pieces.map((piece) => piece.translatedArtifactId) as unknown as JsonObject, selectedImageRevisions: args.selectedImageRevisions as unknown as JsonObject, layoutInputArtifactIds: plan.layoutInputArtifactIds as unknown as JsonObject } },
  );
  return { schemaVersion: "magazine-edition-workflow-result/1", editionId: args.editionId, runId: args.runId, status: "complete", articleExecutionIds: plan.children.map((child) => child.articleExecutionId), children, selectedImageRevisions: args.selectedImageRevisions, imageGenerationAllowed: false, acceptedEnglishInputsArtifactId: accepted.artifactId, editorial, translationArtifactIds: pieces.map((piece) => piece.translatedArtifactId), compositionArtifactId: composition.compositionArtifactId, compositionRevisionId: composition.compositionRevisionId };
}

export function parseEditionWorkflowArgs(value: unknown): EditionWorkflowArgs {
  if (!isObject(value) || value.schemaVersion !== EDITION_WORKFLOW_SCHEMA || value.editionId !== "004") throw new Error("Edition workflow args are not the immutable Edition 4 contract");
  if (!isText(value.runId) || !isText(value.editionExecutionId) || !isText(value.planArtifactId) || !isText(value.entryArtifactId)) throw new Error("Edition workflow args have incomplete root identity");
  if (value.imageGenerationAllowed !== false || !Array.isArray(value.selectedImageRevisions)) throw new Error("Edition 4 workflow cannot enable image generation");
  if (!Array.isArray(value.children) || value.children.length !== 7) throw new Error("Edition 4 workflow requires exactly seven article children");
  const plan = parseEditionPlanCheckpoint(value.plan);
  const children = (value.children as unknown[]).map(parseEditionArticleChild);
  if (new Set(children.map((child) => child.articleId)).size !== 7 || children.some((child) => !plan.articleIds.includes(child.articleId))) throw new Error("Edition 4 article child IDs are not the immutable plan");
  for (const child of children) if (child.args.runId !== child.runId || child.args.articleExecutionId !== child.articleExecutionId || child.args.articleId !== child.articleId || child.args.editionId !== "004" || child.args.entry.articleId !== child.articleId) throw new Error(`Edition child ${child.articleId} is not bound to its authenticated launch args`);
  return Object.freeze({ schemaVersion: EDITION_WORKFLOW_SCHEMA, editionId: "004", runId: value.runId as RunId, editionExecutionId: value.editionExecutionId, planArtifactId: value.planArtifactId as ArtifactId, entryArtifactId: value.entryArtifactId as ArtifactId, plan, children: Object.freeze(children), selectedImageRevisions: Object.freeze(value.selectedImageRevisions as DurableRevisionRef[]), imageGenerationAllowed: false });
}

export function parseEditionPlanCheckpoint(value: unknown): EditionPlanCheckpoint {
  if (!isObject(value) || value.schemaVersion !== "edition-plan-checkpoint/1" || value.editionId !== "004") throw new Error("Edition plan checkpoint has an invalid identity");
  if (!isObject(value.pipelineRef) || value.pipelineRef.kind !== "write_pipeline" || !isText(value.pipelineRef.logicalId) || !isText(value.pipelineRef.revisionId) || value.pipelineRef.editionId !== "004") throw new Error("Edition plan checkpoint has an invalid write-pipeline pin");
  if (!isText(value.pipelineDigest) || !Array.isArray(value.articleIds) || value.articleIds.length !== 7 || value.articleIds.some((id) => !isText(id))) throw new Error("Edition plan checkpoint must name seven article IDs");
  if (!Array.isArray(value.children) || value.children.length !== 7 || !Array.isArray(value.selectedImageRevisions) || value.selectedImageRevisions.length !== 13 || value.imageGenerationAllowed !== false || !Array.isArray(value.layoutInputRevisions) || !Array.isArray(value.layoutInputArtifactIds) || !Array.isArray(value.layoutInputBindings) || value.layoutInputRevisions.length === 0 || !Array.isArray(value.translations) || value.translations.length !== 1) throw new Error("Edition plan checkpoint has an invalid child/image/language set");
  const selectedImages = value.selectedImageRevisions as unknown[];
  if (selectedImages.some((image) => !isObject(image) || image.kind !== "image" || image.editionId !== "004" || !isText(image.logicalId) || !isText(image.revisionId)) || new Set(selectedImages.map((image) => isObject(image) ? image.logicalId : undefined)).size !== 13 || new Set(selectedImages.map((image) => isObject(image) ? image.revisionId : undefined)).size !== 13) throw new Error("Edition plan must pin thirteen unique Edition 4 image revisions");
  if (new Set(value.layoutInputArtifactIds as unknown[]).size !== value.layoutInputArtifactIds.length || (value.layoutInputBindings as unknown[]).some((binding) => !isObject(binding) || !isText(binding.artifactId) || !isObject(binding.revision)) || (value.layoutInputBindings as unknown[]).length !== value.layoutInputArtifactIds.length || !sameTextSequence((value.layoutInputBindings as Record<string, unknown>[]).map((binding) => binding.artifactId as string), value.layoutInputArtifactIds as string[])) throw new Error("Edition layout inputs are not bound to exact artifacts");
  const children = (value.children as unknown[]).map(parseEditionPlanChild);
  if (new Set(children.map((child) => child.articleId)).size !== 7 || new Set(value.articleIds).size !== 7) throw new Error("Edition plan article identities must be unique");
  return Object.freeze({ schemaVersion: "edition-plan-checkpoint/1", editionId: "004", pipelineRef: value.pipelineRef as unknown as EditionPlanCheckpoint["pipelineRef"], pipelineDigest: value.pipelineDigest, articleIds: Object.freeze(value.articleIds as string[]), children: Object.freeze(children), selectedImageRevisions: Object.freeze(value.selectedImageRevisions as DurableRevisionRef[]), layoutInputRevisions: Object.freeze(value.layoutInputRevisions as InputRevisionRef[]), layoutInputArtifactIds: Object.freeze(value.layoutInputArtifactIds as ArtifactId[]), layoutInputBindings: Object.freeze((value.layoutInputBindings as unknown[]).map(parseInputArtifactBinding)), imageGenerationAllowed: false, editorial: parseEditionEditorialPlan(value.editorial), translations: Object.freeze((value.translations as unknown[]).map(parseEditionTranslationPlan)) });
}

function parseEditionEditorialPlan(value: unknown): EditionEditorialPlan {
  if (!isObject(value) || value.schemaVersion !== "edition-editorial-plan/1" || value.editorialId !== "opening" || !isText(value.brief) || value.maximumReaderPages !== 1 || !Number.isSafeInteger(value.maximumRewrites) || (value.maximumRewrites as number) < 0 || !isText(value.profileArtifactId) || !isText(value.reviewPlanArtifactId) || !isText(value.measurementProfileArtifactId) || !Array.isArray(value.reviewInputArtifactIds) || value.reviewInputArtifactIds.some((id) => !isText(id))) throw new Error("Edition editorial plan is malformed");
  return Object.freeze({ schemaVersion: "edition-editorial-plan/1", editorialId: "opening", brief: value.brief, maximumReaderPages: 1, maximumRewrites: value.maximumRewrites as number, profileArtifactId: value.profileArtifactId as ArtifactId, reviewPlanArtifactId: value.reviewPlanArtifactId as ArtifactId, measurementProfileArtifactId: value.measurementProfileArtifactId as ArtifactId, reviewInputArtifactIds: Object.freeze(value.reviewInputArtifactIds as ArtifactId[]) });
}

function parseEditionTranslationPlan(value: unknown): EditionTranslationPlan {
  if (!isObject(value) || value.schemaVersion !== "edition-translation-plan/1" || value.language !== "es" || value.sourceLanguage !== "en" || !isObject(value.promptRevision) || !isText(value.promptArtifactId) || !Array.isArray(value.inputRevisions) || !Array.isArray(value.inputArtifactIds) || !Array.isArray(value.inputArtifactBindings) || value.inputRevisions.length === 0 || value.maximumReaderPages !== 7 || !Array.isArray(value.pieceIds) || value.pieceIds.length !== 8 || value.pieceIds.some((id) => !isText(id)) || new Set(value.pieceIds).size !== 8 || !isObject(value.parentRevisionIds) || value.inputArtifactBindings.length !== value.inputArtifactIds.length || value.inputArtifactBindings.some((binding) => !isObject(binding) || !isText(binding.artifactId) || !isObject(binding.revision)) || new Set(value.inputArtifactIds as unknown[]).size !== value.inputArtifactIds.length || !sameTextSequence((value.inputArtifactBindings as Record<string, unknown>[]).map((binding) => binding.artifactId as string), value.inputArtifactIds as string[])) throw new Error("Edition translation plan is malformed");
  const parentRevisionIds: Record<string, string | null> = {};
  for (const pieceId of value.pieceIds as string[]) {
    const parent = value.parentRevisionIds[pieceId];
    if (parent !== null && !isText(parent)) throw new Error(`Edition translation parent for ${pieceId} is malformed`);
    parentRevisionIds[pieceId] = parent as string | null;
  }
  return Object.freeze({ schemaVersion: "edition-translation-plan/1", language: "es", sourceLanguage: "en", promptRevision: value.promptRevision as unknown as InputRevisionRef, promptArtifactId: value.promptArtifactId as ArtifactId, inputRevisions: Object.freeze(value.inputRevisions as InputRevisionRef[]), inputArtifactIds: Object.freeze(value.inputArtifactIds as ArtifactId[]), inputArtifactBindings: Object.freeze((value.inputArtifactBindings as unknown[]).map(parseInputArtifactBinding)), maximumReaderPages: 7, pieceIds: Object.freeze(value.pieceIds as string[]), parentRevisionIds: Object.freeze(parentRevisionIds) });
}

function parseInputArtifactBinding(value: unknown): { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef } {
  if (!isObject(value) || !isText(value.artifactId) || !isObject(value.revision)) throw new Error("Edition input artifact binding is malformed");
  return Object.freeze({ artifactId: value.artifactId as ArtifactId, revision: value.revision as unknown as InputRevisionRef });
}

function parseEditionPlanChild(value: unknown): EditionPlanCheckpoint["children"][number] {
  if (!isObject(value) || !isText(value.articleId) || !isText(value.articleExecutionId) || !isText(value.runId) || !Array.isArray(value.sourceIds) || value.sourceIds.some((id) => !isText(id)) || !Array.isArray(value.sourceLineage)) throw new Error("Edition plan child is malformed");
  return Object.freeze({ articleId: value.articleId, articleExecutionId: value.articleExecutionId, runId: value.runId as RunId, sourceIds: Object.freeze(value.sourceIds as string[]), sourceLineage: Object.freeze(value.sourceLineage.map(parseSourceLineage)) });
}

function parseEditionArticleChild(value: unknown): EditionArticleChild {
  if (!isObject(value) || !isText(value.articleId) || !isText(value.articleExecutionId) || !isText(value.runId) || !Array.isArray(value.sourceIds) || !Array.isArray(value.sourceLineage) || !isObject(value.args)) throw new Error("Edition article child launch is malformed");
  return Object.freeze({ articleId: value.articleId, articleExecutionId: value.articleExecutionId, runId: value.runId as RunId, sourceIds: Object.freeze(value.sourceIds as string[]), sourceLineage: Object.freeze(value.sourceLineage.map(parseSourceLineage)), args: value.args as unknown as ArticleRuntimeStartArgs });
}

function parseSourceLineage(value: unknown): EditionSourceLineage {
  if (!isObject(value) || !isText(value.sourceId) || !isObject(value.capture) || !isObject(value.extraction) || !Array.isArray(value.captureArtifactIds) || !Array.isArray(value.extractionArtifactIds) || value.captureArtifactIds.some((id) => !isText(id)) || value.extractionArtifactIds.some((id) => !isText(id))) throw new Error("Edition source lineage is malformed");
  return Object.freeze({ sourceId: value.sourceId, capture: value.capture as unknown as InputRevisionRef, extraction: value.extraction as unknown as InputRevisionRef, captureArtifactIds: Object.freeze(value.captureArtifactIds as ArtifactId[]), extractionArtifactIds: Object.freeze(value.extractionArtifactIds as ArtifactId[]) });
}

async function prepareTranslationTasks(
  args: EditionWorkflowArgs,
  plan: EditionPlanCheckpoint,
  accepted: AcceptedEnglishIssueInputs,
  editorial: OpeningEditorialWorkflowResult,
  ports: ArticleWorkflowPorts,
): Promise<readonly TranslationTask[]> {
  const translation = plan.translations[0];
  if (translation === undefined) throw new Error("Edition 4 has no Spanish translation plan");
  if (!isText(editorial.durableRevisionId)) throw new Error("accepted opening editorial has no durable revision");
  const editorialEnglish: DurableRevisionRef = { kind: "editorial", editionId: "004", logicalId: "opening", language: "en", revisionId: editorial.durableRevisionId as never };
  const pieces: readonly { readonly pieceKind: "article" | "editorial"; readonly pieceId: string; readonly englishArtifactId: ArtifactId; readonly englishRevision: DurableRevisionRef; readonly expectedParentRevisionId: string | null }[] = [
    ...accepted.articles.map((article) => ({ pieceKind: "article" as const, pieceId: article.articleId, englishArtifactId: article.manuscriptArtifactId, englishRevision: { kind: "article" as const, editionId: "004", logicalId: article.articleId, language: "en", revisionId: article.durableRevisionId as never }, expectedParentRevisionId: translation.parentRevisionIds[article.articleId] ?? null })),
    { pieceKind: "editorial", pieceId: "opening", englishArtifactId: editorial.manuscriptArtifactId, englishRevision: editorialEnglish, expectedParentRevisionId: translation.parentRevisionIds.opening ?? null },
  ];
  const inputArtifactBindings = [
    { artifactId: translation.promptArtifactId, revision: translation.promptRevision },
    ...translation.inputArtifactBindings,
  ] as readonly { readonly artifactId: ArtifactId; readonly revision: InputRevisionRef }[];
  const inputArtifactIds = inputArtifactBindings.map((binding) => binding.artifactId) as readonly ArtifactId[];
  const inputRevisions = uniqueInputRevisions(inputArtifactBindings.map((binding) => binding.revision));
  return pieces.map((piece) => {
    const identity = `${args.runId}:${piece.pieceKind}:${piece.pieceId}`;
    const runId = `translation-${safe(identity)}` as RunId;
    const translationExecutionId = `translation-execution-${safe(identity)}`;
    const profileArtifactId = `art-translation-profile-${safe(identity)}` as ArtifactId;
    const entryArtifactId = `art-translation-entry-${safe(identity)}` as ArtifactId;
    const english = ports.ledger.requireArtifact(piece.englishArtifactId);
    const task: TranslationTask = {
      pieceKind: piece.pieceKind,
      pieceId: piece.pieceId,
      translationExecutionId,
      runId,
      profileArtifactId,
      entryArtifactId,
      englishArtifactId: piece.englishArtifactId,
      englishDigest: english.digest,
      englishRevision: piece.englishRevision,
      promptArtifactId: translation.promptArtifactId,
      inputArtifactIds: inputArtifactIds,
      inputArtifactBindings,
      inputRevisions,
      expectedParentRevisionId: piece.expectedParentRevisionId,
    };
    const profile = {
      schemaVersion: "translation-profile/1",
      editionId: "004",
      pieceKind: piece.pieceKind,
      pieceId: piece.pieceId,
      language: "es",
      sourceLanguage: "en",
      englishArtifactId: piece.englishArtifactId,
      englishDigest: english.digest,
      promptArtifactId: translation.promptArtifactId,
      inputArtifactIds,
      inputRevisions,
    } as unknown as JsonObject;
    ports.ledger.createRun({ runId, articleExecutionId: translationExecutionId as never, articleId: piece.pieceId, editionId: "004", workflowVersion: "translation-writer/1", loopsRunId: args.runId, manuscriptArtifactId: piece.englishArtifactId, args: task as unknown as JsonObject });
    ports.ledger.createArtifact({ id: profileArtifactId, kind: "translation_profile", schemaVersion: "translation-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: profile }, parents: inputArtifactIds.map((artifactId) => ({ artifactId, relation: "translation_input" })), metadata: { editionId: "004", pieceKind: piece.pieceKind, pieceId: piece.pieceId, language: "es", englishArtifactId: piece.englishArtifactId, englishDigest: english.digest }, runId });
    ports.ledger.createArtifact({ id: entryArtifactId, kind: "translation_workflow_entry", schemaVersion: "translation-workflow-entry/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: task as unknown as JsonObject }, parents: [{ artifactId: profileArtifactId, relation: "translation_profile" }, { artifactId: piece.englishArtifactId, relation: "english_manuscript" }], metadata: { editionId: "004", pieceKind: piece.pieceKind, pieceId: piece.pieceId, language: "es", englishArtifactId: piece.englishArtifactId, englishDigest: english.digest }, runId });
    return task;
  });
}

async function finalizeTranslation(
  args: EditionWorkflowArgs,
  task: TranslationTask,
  execution: import("../executors/closed-translation-writer/result.ts").TranslationWriterExecutionResult,
  ports: ArticleWorkflowPorts,
): Promise<TranslatedPiece> {
  if (!execution.selected || execution.artifacts.length !== 1) throw new Error(`translation ${task.pieceId} did not select one durable result`);
  const artifact = execution.artifacts[0]!;
  const expectedParents = [task.englishArtifactId, ...task.inputArtifactIds].map((artifactId) => ({ artifactId, relation: "translation_writer_input" }));
  if (artifact.kind !== "translated_piece" || artifact.schemaVersion !== "translation-writer-result/1" || artifact.mediaType !== "text/markdown" || artifact.producingRunId !== task.runId || !sameParents(artifact.parents, expectedParents)) throw new Error(`translation ${task.pieceId} output has invalid identity or lineage`);
  if (artifact.metadata.translationExecutionClass !== "closed_translation_writer/1" || artifact.metadata.pieceId !== task.pieceId || artifact.metadata.language !== "es" || artifact.metadata.englishArtifactId !== task.englishArtifactId || artifact.metadata.englishDigest !== task.englishDigest || !sameIds(artifact.metadata.translationInputArtifactIds, [task.englishArtifactId, ...task.inputArtifactIds])) throw new Error(`translation ${task.pieceId} output is not bound to the exact English input`);
  const value = ("value" in execution ? execution.value : undefined) ?? (() => {
    const textValue = new TextDecoder("utf-8", { fatal: true }).decode(ports.ledger.readArtifact(artifact.id).bytes);
    return { schemaVersion: "translation-writer-result/1", englishSha256: `sha256:${task.englishDigest}`, markdown: textValue } as const;
  })();
  if (value.englishSha256 !== `sha256:${task.englishDigest}`) throw new Error(`translation ${task.pieceId} does not pin the exact English digest`);
  const englishText = new TextDecoder("utf-8", { fatal: true }).decode(ports.ledger.readArtifact(task.englishArtifactId).bytes);
  const translatedText = new TextDecoder("utf-8", { fatal: true }).decode(ports.ledger.readArtifact(artifact.id).bytes);
  if (translatedText !== value.markdown) throw new Error(`translation ${task.pieceId} artifact bytes disagree with selected output`);
  assertTranslatedMarkdownStructure(englishText, translatedText);
  const decisionArtifactId = `art-translation-decision-${safe(task.translationExecutionId)}` as ArtifactId;
  ports.ledger.createArtifact({ id: decisionArtifactId, kind: "translation_machine_decision", schemaVersion: "translation-machine-decision/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "translation-machine-decision/1", pieceKind: task.pieceKind, pieceId: task.pieceId, language: "es", englishArtifactId: task.englishArtifactId, translatedArtifactId: artifact.id, englishDigest: task.englishDigest } }, parents: [{ artifactId: task.englishArtifactId, relation: "english_input" }, { artifactId: artifact.id, relation: "translated_piece" }, ...task.inputArtifactIds.map((artifactId) => ({ artifactId, relation: "translation_input" }))], metadata: { pieceKind: task.pieceKind, pieceId: task.pieceId, language: "es", englishArtifactId: task.englishArtifactId, englishDigest: task.englishDigest }, runId: task.runId });
  const promotion = await ports.promoteTranslation!({ runId: task.runId, pieceKind: task.pieceKind, pieceId: task.pieceId, language: "es", manuscriptArtifactId: artifact.id, englishArtifactId: task.englishArtifactId, promptArtifactId: task.promptArtifactId, inputArtifactIds: [task.englishArtifactId, ...task.inputArtifactIds], inputArtifactBindings: task.inputArtifactBindings, inputRevisions: task.inputRevisions, expectedParentRevisionId: task.expectedParentRevisionId as RevisionId | null, decisionArtifactId });
  const spanishRevision: DurableRevisionRef = { kind: task.pieceKind, editionId: "004", logicalId: task.pieceId, language: "es", revisionId: promotion.durableRevisionId as never };
  return { pieceKind: task.pieceKind, pieceId: task.pieceId, englishArtifactId: task.englishArtifactId, translatedArtifactId: artifact.id, englishRevision: task.englishRevision, spanishRevision, promotion };
}

async function finalizeComposition(
  args: EditionWorkflowArgs,
  plan: EditionPlanCheckpoint,
  accepted: AcceptedEnglishIssueInputs,
  editorial: OpeningEditorialWorkflowResult,
  translated: readonly TranslatedPiece[],
  ports: ArticleWorkflowPorts,
): Promise<{ readonly compositionArtifactId: ArtifactId; readonly compositionRevisionId: string }> {
  const compositionId = `loops-${safe(args.runId)}`;
  const revisionId = stableRevision(`${args.runId}:composition:${translated.map((piece) => `${piece.pieceId}:${piece.spanishRevision.revisionId}`).join(",")}`);
  const byPiece = new Map(translated.map((piece) => [piece.pieceId, piece]));
  const editorialPiece = byPiece.get("opening");
  if (editorialPiece === undefined || !isText(editorial.durableRevisionId)) throw new Error("composition is missing the translated opening editorial");
  const englishEditorial: DurableRevisionRef = { kind: "editorial", editionId: "004", logicalId: "opening", language: "en", revisionId: editorial.durableRevisionId as never };
  const document = {
    schema_version: 1,
    edition_id: "004",
    composition_id: compositionId,
    editorials: [{ editorial_id: "opening", manuscripts: [{ language: "en", revision: englishEditorial }, { language: "es", revision: editorialPiece.spanishRevision }] }],
    articles: accepted.articles.map((article) => {
      const piece = byPiece.get(article.articleId);
      if (piece === undefined) throw new Error(`composition is missing translated article ${article.articleId}`);
      return { article_id: article.articleId, manuscripts: [{ language: "en", revision: piece.englishRevision }, { language: "es", revision: piece.spanishRevision }], images: [] };
    }),
    images: plan.selectedImageRevisions.filter((revision): revision is Extract<DurableRevisionRef, { readonly kind: "image" }> => revision.kind === "image").map((revision) => ({ slot_id: revision.logicalId, revision })),
    layout_inputs: plan.layoutInputRevisions.map((revision, index) => ({ slot_id: `layout-${index + 1}`, revision })),
  } as const;
  const parentIds = [...accepted.articles.map((article) => article.manuscriptArtifactId), editorial.manuscriptArtifactId, ...translated.map((piece) => piece.translatedArtifactId), ...plan.layoutInputArtifactIds] as ArtifactId[];
  const uniqueParents = [...new Set(parentIds)];
  const compositionArtifactId = `art-composition-document-${safe(args.runId)}` as ArtifactId;
  ports.ledger.createArtifact({ id: compositionArtifactId, kind: "composition_revision", schemaVersion: "composition-revision/1", mediaType: "application/yaml", origin: "machine", payload: { kind: "text", text: stringifyYaml(document, { lineWidth: 0 }) }, parents: uniqueParents.map((artifactId) => ({ artifactId, relation: "composition_input" })), metadata: { editionId: "004", compositionId, compositionRevisionId: revisionId, imageGenerationAllowed: false, selectedImageRevisionIds: plan.selectedImageRevisions.map((image) => image.revisionId) as unknown as JsonObject, englishArtifactIds: [...accepted.articles.map((article) => article.manuscriptArtifactId), editorial.manuscriptArtifactId] as unknown as JsonObject, spanishArtifactIds: translated.map((piece) => piece.translatedArtifactId) as unknown as JsonObject }, runId: args.runId });
  const decisionArtifactId = `art-composition-decision-${safe(args.runId)}` as ArtifactId;
  ports.ledger.createArtifact({ id: decisionArtifactId, kind: "composition_machine_decision", schemaVersion: "composition-machine-decision/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "composition-machine-decision/1", compositionId, compositionRevisionId: revisionId, imageGenerationAllowed: false, selectedImageRevisions: plan.selectedImageRevisions } as unknown as JsonObject }, parents: [{ artifactId: compositionArtifactId, relation: "composition_revision" }, ...uniqueParents.map((artifactId) => ({ artifactId, relation: "composition_input" }))], metadata: { editionId: "004", compositionId, compositionRevisionId: revisionId, imageGenerationAllowed: false }, runId: args.runId });
  let promotedRevisionId = revisionId;
  if (ports.promoteComposition !== undefined) {
    const promotion = await ports.promoteComposition({ runId: args.runId, compositionArtifactId, compositionId, revisionId: revisionId as RevisionId, inputArtifactIds: uniqueParents, inputRevisions: plan.layoutInputRevisions, layoutInputBindings: plan.layoutInputBindings, decisionArtifactId });
    promotedRevisionId = promotion.durableRevisionId;
  }
  return { compositionArtifactId, compositionRevisionId: promotedRevisionId };
}

function freezeAcceptedEnglishInputs(args: EditionWorkflowArgs, plan: EditionPlanCheckpoint, children: readonly EditionWorkflowChildResult[], ports: ArticleWorkflowPorts): { readonly artifactId: ArtifactId; readonly value: AcceptedEnglishIssueInputs } {
  if (children.length !== 7 || plan.children.length !== 7) throw new Error("Edition English join requires exactly seven children");
  const byId = new Map(children.map((child) => [child.articleId, child]));
  const articles: AcceptedEnglishArticle[] = [];
  for (const [ordinal, planned] of plan.children.entries()) {
    const child = byId.get(planned.articleId);
    if (child === undefined) throw new Error(`Edition English join is missing ${planned.articleId}`);
    const result = child.result;
    if (!isObject(result) || result.schemaVersion !== "magazine-article-workflow-result/1" || result.status !== "complete" || result.runId !== planned.runId || result.articleExecutionId !== planned.articleExecutionId || result.articleId !== planned.articleId || !isText(result.manuscriptArtifactId) || !isText(result.currentRevisionRecordArtifactId) || !isText(result.measurementArtifactId) || !isText(result.decisionArtifactId) || !isText(result.durableRevisionId)) throw new Error(`Edition English child ${planned.articleId} is not a completed promoted article`);
    const run = ports.ledger.requireRun(planned.runId);
    if (run.articleId !== planned.articleId || run.articleExecutionId !== planned.articleExecutionId || run.editionId !== "004" || run.loopsRunId !== args.runId || run.manuscriptArtifactId !== result.manuscriptArtifactId || run.currentRevisionRecordArtifactId !== result.currentRevisionRecordArtifactId) throw new Error(`Edition English child ${planned.articleId} projection is stale or not promoted`);
    const manuscript = ports.ledger.requireArtifact(result.manuscriptArtifactId as ArtifactId);
    const record = ports.ledger.requireArtifact(result.currentRevisionRecordArtifactId as ArtifactId);
    const revisionIdentityMismatches = [
      manuscript.kind !== "article_manuscript" ? `manuscript.kind=${manuscript.kind}` : undefined,
      manuscript.mediaType !== "text/markdown" ? `manuscript.mediaType=${manuscript.mediaType}` : undefined,
      manuscript.producingRunId !== planned.runId ? `manuscript.producingRunId=${manuscript.producingRunId ?? "<none>"} expected=${planned.runId}` : undefined,
      record.kind !== "article_revision_record" ? `record.kind=${record.kind}` : undefined,
      record.producingRunId !== planned.runId ? `record.producingRunId=${record.producingRunId ?? "<none>"} expected=${planned.runId}` : undefined,
      record.metadata.manuscriptArtifactId !== manuscript.id ? `record.metadata.manuscriptArtifactId=${record.metadata.manuscriptArtifactId ?? "<none>"} expected=${manuscript.id}` : undefined,
    ].filter((value): value is string => value !== undefined);
    if (revisionIdentityMismatches.length > 0) throw new Error(`Edition English child ${planned.articleId} revision identity is invalid: ${revisionIdentityMismatches.join(", ")}`);
    for (const id of [result.measurementArtifactId, result.decisionArtifactId] as const) if (ports.ledger.requireArtifact(id as ArtifactId).producingRunId !== planned.runId) throw new Error(`Edition English child ${planned.articleId} evidence is not run-owned`);
    articles.push({ ordinal, articleId: planned.articleId, articleExecutionId: planned.articleExecutionId, childRunId: planned.runId, manuscriptArtifactId: manuscript.id, revisionRecordArtifactId: record.id, measurementArtifactId: result.measurementArtifactId as ArtifactId, decisionArtifactId: result.decisionArtifactId as ArtifactId, durableRevisionId: result.durableRevisionId });
  }
  const value: AcceptedEnglishIssueInputs = { schemaVersion: "accepted-english-issue-inputs/1", editionId: "004", pipelineRef: plan.pipelineRef, pipelineDigest: plan.pipelineDigest, articleCount: 7, articles: Object.freeze(articles) };
  const artifactId = `art-accepted-english-issue-inputs-${safe(args.runId)}` as ArtifactId;
  ports.ledger.createArtifact({ id: artifactId, kind: "accepted_english_issue_inputs", schemaVersion: "accepted-english-issue-inputs/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: value as unknown as JsonObject }, parents: articles.flatMap((article) => [{ artifactId: article.manuscriptArtifactId, relation: "accepted_article_manuscript" }, { artifactId: article.revisionRecordArtifactId, relation: "accepted_article_revision" }, { artifactId: article.measurementArtifactId, relation: "accepted_article_measurement" }, { artifactId: article.decisionArtifactId, relation: "accepted_article_decision" }]), metadata: { editionId: "004", pipelineRevisionId: plan.pipelineRef.revisionId, pipelineDigest: plan.pipelineDigest, articleCount: 7 }, runId: args.runId });
  return { artifactId, value };
}

function createEditorialChildArgs(args: EditionWorkflowArgs, plan: EditionPlanCheckpoint, acceptedArtifactId: ArtifactId, accepted: AcceptedEnglishIssueInputs, ports: ArticleWorkflowPorts): OpeningEditorialWorkflowArgs {
  const runId = `editorial-${safe(args.runId)}` as RunId;
  const editorialExecutionId = `editorial-execution-${safe(args.runId)}`;
  const seedId = `art-editorial-input-set-${safe(args.runId)}` as ArtifactId;
  const profileId = `art-editorial-profile-${safe(args.runId)}` as ArtifactId;
  const measurementProfileId = `art-editorial-measurement-profile-${safe(args.runId)}` as ArtifactId;
  const entryId = `art-editorial-workflow-entry-${safe(args.runId)}` as ArtifactId;
  const baseProfile = ports.ledger.requireArtifact(plan.editorial.profileArtifactId);
  const baseMeasurementProfile = ports.ledger.requireArtifact(plan.editorial.measurementProfileArtifactId);
  if (baseProfile.kind !== "resolved_editorial_profile" || baseProfile.schemaVersion !== "resolved-editorial-profile/1") throw new Error("Edition editorial plan profile is not the exact resolved profile");
  if (baseMeasurementProfile.kind !== "editorial_measurement_profile" || baseMeasurementProfile.schemaVersion !== "editorial-measurement-profile/1" || baseMeasurementProfile.payloadKind !== "json") throw new Error("Edition editorial measurement profile is not the exact resolved renderer profile");
  ports.ledger.createArtifact({ id: seedId, kind: "editorial_input_set", schemaVersion: "editorial-input-set/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-input-set/1", articleArtifactIds: accepted.articles.map((article) => article.manuscriptArtifactId), acceptedEnglishInputsArtifactId: acceptedArtifactId } }, parents: [{ artifactId: acceptedArtifactId, relation: "accepted_english_inputs" }, ...accepted.articles.map((article) => ({ artifactId: article.manuscriptArtifactId, relation: "editorial_article_input" }))] });
  const childArgs: OpeningEditorialWorkflowArgs = { schemaVersion: "magazine-opening-editorial/1", editionId: "004", runId, editionRunId: args.runId, editorialExecutionId, editorialId: "opening", seedManuscriptArtifactId: seedId, measurementProfileArtifactId: measurementProfileId, profileArtifactId: profileId, entryArtifactId: entryId, acceptedEnglishInputsArtifactId: acceptedArtifactId, articleArtifactIds: accepted.articles.map((article) => article.manuscriptArtifactId), articleExecutionIds: accepted.articles.map((article) => article.articleExecutionId), maximumReaderPages: 1, maximumRewrites: plan.editorial.maximumRewrites, reviewPlanArtifactId: plan.editorial.reviewPlanArtifactId };
  ports.ledger.createRun({ runId, articleExecutionId: editorialExecutionId as never, articleId: "opening", editionId: "004", workflowVersion: "opening-editorial/1", loopsRunId: args.runId, manuscriptArtifactId: seedId, args: childArgs as unknown as JsonObject });
  ports.ledger.createArtifact({ id: profileId, kind: "resolved_editorial_profile", schemaVersion: "resolved-editorial-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: JSON.parse(Buffer.from(ports.ledger.readArtifact(baseProfile.id).bytes).toString("utf8")) as JsonObject }, parents: baseProfile.parents, metadata: { editionId: "004", editorialId: "opening", baseProfileArtifactId: baseProfile.id }, runId });
  ports.ledger.createArtifact({ id: measurementProfileId, kind: "editorial_measurement_profile", schemaVersion: "editorial-measurement-profile/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: JSON.parse(Buffer.from(ports.ledger.readArtifact(baseMeasurementProfile.id).bytes).toString("utf8")) as JsonObject }, parents: [{ artifactId: baseMeasurementProfile.id, relation: "base_measurement_profile" }, ...baseMeasurementProfile.parents], metadata: { editionId: "004", editorialId: "opening", maximumReaderPages: 1, baseMeasurementProfileArtifactId: baseMeasurementProfile.id }, runId });
  ports.ledger.createArtifact({ id: entryId, kind: "editorial_workflow_entry", schemaVersion: "magazine-opening-editorial/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: childArgs as unknown as JsonObject }, parents: [{ artifactId: profileId, relation: "editorial_profile" }, { artifactId: acceptedArtifactId, relation: "accepted_english_inputs" }], metadata: { editionId: "004", editorialId: "opening" }, runId });
  return childArgs;
}

function isObject(value: unknown): value is Record<string, any> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function isText(value: unknown): value is string { return typeof value === "string" && value.length > 0; }
function sameTextSequence(actual: readonly string[], expected: readonly string[]): boolean { return actual.length === expected.length && actual.every((value, index) => value === expected[index]); }
function safe(value: string): string { return value.replace(/[^A-Za-z0-9._-]/gu, "_"); }
function sameParents(actual: readonly { readonly artifactId: string; readonly relation: string }[], expected: readonly { readonly artifactId: string; readonly relation: string }[]): boolean { return actual.length === expected.length && actual.every((parent, index) => parent.artifactId === expected[index]?.artifactId && parent.relation === expected[index]?.relation); }
function sameIds(value: unknown, expected: readonly string[]): boolean { return Array.isArray(value) && value.length === expected.length && value.every((id, index) => id === expected[index]); }
function uniqueInputRevisions(values: readonly InputRevisionRef[]): readonly InputRevisionRef[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = `${value.kind}:${value.editionId ?? ""}:${value.logicalId}:${value.revisionId}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function stableRevision(value: string): string { const digest = createHash("sha256").update(value).digest(); const alphabet = "abcdefghijklmnopqrstuvwxyz234567"; let bits = 0; let buffer = 0; let suffix = ""; for (const byte of digest) { buffer = (buffer << 8) | byte; bits += 8; while (bits >= 5 && suffix.length < 12) { bits -= 5; suffix += alphabet[(buffer >>> bits) & 31]!; buffer &= (1 << bits) - 1; } if (suffix.length === 12) break; } return `rev_20260804T000000000Z_${suffix}`; }
