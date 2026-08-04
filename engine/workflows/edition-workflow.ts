import type { WorkflowContext } from "loops";

import type { ArtifactId, JsonObject, RunId } from "../contracts/index.ts";
import type { InputRevisionRef, DurableRevisionRef } from "../durable/types.ts";
import type { ArticleRuntimeStartArgs } from "./internal-types.ts";
import { magazineArticleWorkflowRef } from "./magazine-workflow-resolver.ts";

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

export type EditionPlanCheckpoint = {
  readonly schemaVersion: "edition-plan-checkpoint/1";
  readonly editionId: string;
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
  readonly status: "articles_waiting" | "complete";
  readonly articleExecutionIds: readonly string[];
  readonly children: readonly EditionWorkflowChildResult[];
  readonly selectedImageRevisions: readonly DurableRevisionRef[];
  readonly imageGenerationAllowed: false;
};

export default async function run(
  context: WorkflowContext<EditionWorkflowArgs>,
): Promise<EditionWorkflowResult> {
  const args = parseEditionWorkflowArgs(context.input);
  const plan = parseEditionPlanCheckpoint(await context.step(
    "edition.plan",
    () => parseEditionPlanCheckpoint(args.plan),
    {
      input: {
        schemaVersion: args.plan.schemaVersion,
        editionId: args.editionId,
        pipelineRef: args.plan.pipelineRef as unknown as JsonObject,
        pipelineDigest: args.plan.pipelineDigest,
        articleIds: args.plan.articleIds as unknown as JsonObject,
        selectedImageRevisions: args.plan.selectedImageRevisions as unknown as JsonObject,
        imageGenerationAllowed: false,
      },
    },
  ));

  const values = await context.parallel(
    plan.children.map((planned) => {
      const child = args.children.find((candidate) => candidate.articleId === planned.articleId);
      if (child === undefined) throw new Error(`Edition plan has no launch args for ${planned.articleId}`);
      return async () => {
        const result = await context.workflow(
          magazineArticleWorkflowRef(),
          child.args,
          { key: `article.${child.articleId}` },
        );
        return {
          articleId: child.articleId,
          articleExecutionId: child.articleExecutionId,
          runId: child.runId,
          result,
        } satisfies EditionWorkflowChildResult;
      };
    }),
  );

  const children = values.filter((value): value is EditionWorkflowChildResult => value !== null);
  return {
    schemaVersion: "magazine-edition-workflow-result/1",
    editionId: args.editionId,
    runId: args.runId,
    status: children.length === plan.children.length ? "complete" : "articles_waiting",
    articleExecutionIds: plan.children.map((child) => child.articleExecutionId),
    children,
    selectedImageRevisions: args.selectedImageRevisions,
    imageGenerationAllowed: false,
  };
}

export function parseEditionWorkflowArgs(value: unknown): EditionWorkflowArgs {
  if (!isObject(value) || value.schemaVersion !== EDITION_WORKFLOW_SCHEMA || value.editionId !== "004") {
    throw new Error("Edition workflow args are not the immutable Edition 4 contract");
  }
  if (!isText(value.runId) || !isText(value.editionExecutionId) || !isText(value.planArtifactId) || !isText(value.entryArtifactId)) {
    throw new Error("Edition workflow args have incomplete root identity");
  }
  if (value.imageGenerationAllowed !== false || !Array.isArray(value.selectedImageRevisions)) {
    throw new Error("Edition 4 workflow cannot enable image generation");
  }
  if (!Array.isArray(value.children) || value.children.length !== 7) {
    throw new Error("Edition 4 workflow requires exactly seven article children");
  }
  const plan = parseEditionPlanCheckpoint(value.plan);
  const children = (value.children as unknown[]).map(parseEditionArticleChild);
  if (new Set(children.map((child) => child.articleId)).size !== children.length) {
    throw new Error("Edition 4 article child IDs must be unique");
  }
  for (const child of children) {
    if (
      child.args.runId !== child.runId ||
      child.args.articleExecutionId !== child.articleExecutionId ||
      child.args.articleId !== child.articleId ||
      child.args.editionId !== "004" ||
      child.args.entry.articleId !== child.articleId
    ) {
      throw new Error(`Edition child ${child.articleId} is not bound to its authenticated launch args`);
    }
  }
  if (children.some((child) => !plan.articleIds.includes(child.articleId))) {
    throw new Error("Edition 4 child is not present in the immutable plan");
  }
  return Object.freeze({
    schemaVersion: EDITION_WORKFLOW_SCHEMA,
    editionId: "004",
    runId: value.runId as RunId,
    editionExecutionId: value.editionExecutionId,
    planArtifactId: value.planArtifactId as ArtifactId,
    entryArtifactId: value.entryArtifactId as ArtifactId,
    plan,
    children: Object.freeze(children),
    selectedImageRevisions: Object.freeze(value.selectedImageRevisions as DurableRevisionRef[]),
    imageGenerationAllowed: false,
  });
}

export function parseEditionPlanCheckpoint(value: unknown): EditionPlanCheckpoint {
  if (!isObject(value) || value.schemaVersion !== "edition-plan-checkpoint/1" || value.editionId !== "004") {
    throw new Error("Edition plan checkpoint has an invalid identity");
  }
  if (!isObject(value.pipelineRef) || value.pipelineRef.kind !== "write_pipeline" || !isText(value.pipelineRef.logicalId) || !isText(value.pipelineRef.revisionId) || value.pipelineRef.editionId !== "004") {
    throw new Error("Edition plan checkpoint has an invalid write-pipeline pin");
  }
  if (!isText(value.pipelineDigest) || !Array.isArray(value.articleIds) || value.articleIds.length !== 7 || value.articleIds.some((id) => !isText(id))) {
    throw new Error("Edition plan checkpoint must name seven article IDs");
  }
  if (!Array.isArray(value.children) || value.children.length !== 7) throw new Error("Edition plan checkpoint must name seven children");
  if (!Array.isArray(value.selectedImageRevisions) || value.selectedImageRevisions.length !== 13 || value.imageGenerationAllowed !== false) {
    throw new Error("Edition plan checkpoint must pin thirteen existing images and disable generation");
  }
  const children = (value.children as unknown[]).map(parseEditionPlanChild);
  if (new Set(children.map((child) => child.articleId)).size !== children.length || new Set(value.articleIds).size !== value.articleIds.length) {
    throw new Error("Edition plan article identities must be unique");
  }
  return Object.freeze({
    schemaVersion: "edition-plan-checkpoint/1",
    editionId: "004",
    pipelineRef: value.pipelineRef as unknown as EditionPlanCheckpoint["pipelineRef"],
    pipelineDigest: value.pipelineDigest,
    articleIds: Object.freeze(value.articleIds as string[]),
    children: Object.freeze(children),
    selectedImageRevisions: Object.freeze(value.selectedImageRevisions as DurableRevisionRef[]),
    imageGenerationAllowed: false,
  });
}

function parseEditionPlanChild(value: unknown): EditionPlanCheckpoint["children"][number] {
  if (!isObject(value) || !isText(value.articleId) || !isText(value.articleExecutionId) || !isText(value.runId) || !Array.isArray(value.sourceIds) || value.sourceIds.some((id) => !isText(id)) || !Array.isArray(value.sourceLineage)) {
    throw new Error("Edition plan child is malformed");
  }
  return Object.freeze({
    articleId: value.articleId,
    articleExecutionId: value.articleExecutionId,
    runId: value.runId as RunId,
    sourceIds: Object.freeze(value.sourceIds as string[]),
    sourceLineage: Object.freeze(value.sourceLineage.map(parseSourceLineage)),
  });
}

function parseEditionArticleChild(value: unknown): EditionArticleChild {
  if (!isObject(value) || !isText(value.articleId) || !isText(value.articleExecutionId) || !isText(value.runId) || !Array.isArray(value.sourceIds) || !Array.isArray(value.sourceLineage) || !isObject(value.args)) {
    throw new Error("Edition article child launch is malformed");
  }
  return Object.freeze({
    articleId: value.articleId,
    articleExecutionId: value.articleExecutionId,
    runId: value.runId as RunId,
    sourceIds: Object.freeze(value.sourceIds as string[]),
    sourceLineage: Object.freeze(value.sourceLineage.map(parseSourceLineage)),
    args: value.args as unknown as ArticleRuntimeStartArgs,
  });
}

function parseSourceLineage(value: unknown): EditionSourceLineage {
  if (!isObject(value) || !isText(value.sourceId) || !isObject(value.capture) || !isObject(value.extraction) || !Array.isArray(value.captureArtifactIds) || !Array.isArray(value.extractionArtifactIds) || value.captureArtifactIds.some((id) => !isText(id)) || value.extractionArtifactIds.some((id) => !isText(id))) {
    throw new Error("Edition source lineage is malformed");
  }
  return Object.freeze({
    sourceId: value.sourceId,
    capture: value.capture as unknown as InputRevisionRef,
    extraction: value.extraction as unknown as InputRevisionRef,
    captureArtifactIds: Object.freeze(value.captureArtifactIds as ArtifactId[]),
    extractionArtifactIds: Object.freeze(value.extractionArtifactIds as ArtifactId[]),
  });
}

function isObject(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}
