import type { WorkflowContext } from "loops";

import type { ArtifactId, JsonObject, RunId } from "../contracts/index.ts";
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
  readonly imageGenerationAllowed: false;
  readonly editorial: EditionEditorialPlan;
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
  readonly status: "articles_waiting" | "editorial_waiting" | "complete";
  readonly articleExecutionIds: readonly string[];
  readonly children: readonly EditionWorkflowChildResult[];
  readonly selectedImageRevisions: readonly DurableRevisionRef[];
  readonly imageGenerationAllowed: false;
  readonly acceptedEnglishInputsArtifactId?: ArtifactId;
  readonly editorial?: OpeningEditorialWorkflowResult;
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
  return { schemaVersion: "magazine-edition-workflow-result/1", editionId: args.editionId, runId: args.runId, status: "complete", articleExecutionIds: plan.children.map((child) => child.articleExecutionId), children, selectedImageRevisions: args.selectedImageRevisions, imageGenerationAllowed: false, acceptedEnglishInputsArtifactId: accepted.artifactId, editorial };
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
  if (!Array.isArray(value.children) || value.children.length !== 7 || !Array.isArray(value.selectedImageRevisions) || value.selectedImageRevisions.length !== 13 || value.imageGenerationAllowed !== false) throw new Error("Edition plan checkpoint has an invalid child/image set");
  const children = (value.children as unknown[]).map(parseEditionPlanChild);
  if (new Set(children.map((child) => child.articleId)).size !== 7 || new Set(value.articleIds).size !== 7) throw new Error("Edition plan article identities must be unique");
  return Object.freeze({ schemaVersion: "edition-plan-checkpoint/1", editionId: "004", pipelineRef: value.pipelineRef as unknown as EditionPlanCheckpoint["pipelineRef"], pipelineDigest: value.pipelineDigest, articleIds: Object.freeze(value.articleIds as string[]), children: Object.freeze(children), selectedImageRevisions: Object.freeze(value.selectedImageRevisions as DurableRevisionRef[]), imageGenerationAllowed: false, editorial: parseEditionEditorialPlan(value.editorial) });
}

function parseEditionEditorialPlan(value: unknown): EditionEditorialPlan {
  if (!isObject(value) || value.schemaVersion !== "edition-editorial-plan/1" || value.editorialId !== "opening" || !isText(value.brief) || value.maximumReaderPages !== 1 || !Number.isSafeInteger(value.maximumRewrites) || (value.maximumRewrites as number) < 0 || !isText(value.profileArtifactId) || !isText(value.reviewPlanArtifactId) || !isText(value.measurementProfileArtifactId) || !Array.isArray(value.reviewInputArtifactIds) || value.reviewInputArtifactIds.some((id) => !isText(id))) throw new Error("Edition editorial plan is malformed");
  return Object.freeze({ schemaVersion: "edition-editorial-plan/1", editorialId: "opening", brief: value.brief, maximumReaderPages: 1, maximumRewrites: value.maximumRewrites as number, profileArtifactId: value.profileArtifactId as ArtifactId, reviewPlanArtifactId: value.reviewPlanArtifactId as ArtifactId, measurementProfileArtifactId: value.measurementProfileArtifactId as ArtifactId, reviewInputArtifactIds: Object.freeze(value.reviewInputArtifactIds as ArtifactId[]) });
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
function safe(value: string): string { return value.replace(/[^A-Za-z0-9._-]/gu, "_"); }
