import { dirname, resolve } from "node:path";

import type {
  WorkflowDescriptor,
  Runtime,
  RuntimeConfig,
} from "@loops/core";
import { loadWorkflowScript } from "@loops/workflow";

import type { ArticleRuntimeStartArgs, ArticleWorkflowPorts } from "./internal-types.ts";
import { invokeArticleWorkflowWithPorts } from "./article-loops-entry.ts";
import { invokeEditorialWorkflowWithPorts } from "./editorial-loops-entry.ts";
import { EDITORIAL_WORKFLOW_NAME, type OpeningEditorialWorkflowArgs } from "./editorial-workflow.ts";

/** The only child workflow currently exposed by the Magazine host. */
export const MAGAZINE_ARTICLE_WORKFLOW_NAME = "magazine-article" as const;
export const MAGAZINE_ARTICLE_WORKFLOW_ENTRY = "engine/workflows/article-loops-entry.ts" as const;
export const MAGAZINE_EDITORIAL_WORKFLOW_NAME = EDITORIAL_WORKFLOW_NAME;
export const MAGAZINE_EDITORIAL_WORKFLOW_ENTRY = "engine/workflows/editorial-loops-entry.ts" as const;

type RuntimeWithGlobals = Pick<Runtime, "globals"> & {
  readonly currentWorkflowBaseDir?: () => string | undefined;
};

export type MagazineWorkflowResolverOptions = {
  readonly projectRoot: string;
  readonly articlePorts: ArticleWorkflowPorts;
  /** Test-only completed child seam for exercising the public edition join. */
  readonly articleWorkflowStub?: (args: ArticleRuntimeStartArgs) => Promise<unknown> | unknown;
};

/**
 * Create the fixed resolver used by Magazine's Loops runtime. Resolution is
 * limited to the immutable article entry, and every descriptor gets the
 * source-graph hash produced by Loops' loader. The descriptor's execution
 * closes over host-owned ports only; child args remain immutable JSON.
 */
export function createMagazineWorkflowResolver(
  options: MagazineWorkflowResolverOptions,
): NonNullable<RuntimeConfig["workflowResolver"]> {
  const articleEntryPath = resolve(options.projectRoot, MAGAZINE_ARTICLE_WORKFLOW_ENTRY);
  const editorialEntryPath = resolve(options.projectRoot, MAGAZINE_EDITORIAL_WORKFLOW_ENTRY);
  let articleModulePromise: ReturnType<typeof loadWorkflowScript> | undefined;
  let editorialModulePromise: ReturnType<typeof loadWorkflowScript> | undefined;
  return async (nameOrRef, _args, runtime): Promise<WorkflowDescriptor> => {
    const runtimeWithGlobals = runtime as RuntimeWithGlobals;
    const baseDir = runtimeWithGlobals.currentWorkflowBaseDir?.() ?? options.projectRoot;
    const requestedPath = typeof nameOrRef === "string"
      ? resolve(baseDir, nameOrRef)
      : resolve(baseDir, nameOrRef.scriptPath);
    if (requestedPath === articleEntryPath) {
      articleModulePromise ??= loadWorkflowScript(articleEntryPath);
      const articleModule = await articleModulePromise;
      if (articleModule.meta.name !== MAGAZINE_ARTICLE_WORKFLOW_NAME) throw new Error("Magazine article workflow metadata changed");
      return {
        name: articleModule.meta.name,
        version: articleModule.version,
        baseDir: dirname(articleEntryPath),
        run: async (childArgs: unknown, childRuntime: unknown): Promise<unknown> => {
          if (!isArticleRuntimeStartArgs(childArgs)) throw new Error("Magazine article child args are not authenticated launch args");
          if (options.articleWorkflowStub !== undefined) {
            return await (childRuntime as RuntimeWithGlobals).globals.step(
              "article.stub-complete",
              () => options.articleWorkflowStub!(childArgs),
            );
          }
          return await invokeArticleWorkflowWithPorts((childRuntime as RuntimeWithGlobals).globals, options.articlePorts, childArgs);
        },
      } satisfies WorkflowDescriptor;
    }
    if (requestedPath === editorialEntryPath) {
      editorialModulePromise ??= loadWorkflowScript(editorialEntryPath);
      const editorialModule = await editorialModulePromise;
      if (editorialModule.meta.name !== MAGAZINE_EDITORIAL_WORKFLOW_NAME) throw new Error("Magazine editorial workflow metadata changed");
      return {
        name: editorialModule.meta.name,
        version: editorialModule.version,
        baseDir: dirname(editorialEntryPath),
        run: async (childArgs: unknown, childRuntime: unknown): Promise<unknown> => {
          if (!isEditorialWorkflowArgs(childArgs)) throw new Error("Magazine editorial child args are not authenticated launch args");
          return await invokeEditorialWorkflowWithPorts((childRuntime as RuntimeWithGlobals).globals, options.articlePorts, childArgs);
        },
      } satisfies WorkflowDescriptor;
    }
    throw new Error(`Magazine workflow resolver only permits ${MAGAZINE_ARTICLE_WORKFLOW_ENTRY} and ${MAGAZINE_EDITORIAL_WORKFLOW_ENTRY}`);
  };
}

function isEditorialWorkflowArgs(value: unknown): value is OpeningEditorialWorkflowArgs {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return record.schemaVersion === "magazine-opening-editorial/1"
    && record.editionId === "004"
    && record.editorialId === "opening"
    && typeof record.runId === "string"
    && typeof record.editorialExecutionId === "string"
    && typeof record.profileArtifactId === "string"
    && Array.isArray(record.articleArtifactIds)
    && record.articleArtifactIds.length === 7;
}

/** Return the fixed child reference callers may pass to `ctx.workflow`. */
export function magazineArticleWorkflowRef(): { readonly scriptPath: string } {
  return Object.freeze({ scriptPath: MAGAZINE_ARTICLE_WORKFLOW_ENTRY });
}

export function magazineEditorialWorkflowRef(): { readonly scriptPath: string } {
  return Object.freeze({ scriptPath: MAGAZINE_EDITORIAL_WORKFLOW_ENTRY });
}

function isArticleRuntimeStartArgs(value: unknown): value is ArticleRuntimeStartArgs {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return typeof record.runId === "string"
    && typeof record.articleExecutionId === "string"
    && typeof record.articleId === "string"
    && typeof record.editionId === "string"
    && typeof record.entryArtifactId === "string"
    && typeof record.manuscriptArtifactId === "string"
    && typeof record.measurementProfileArtifactId === "string"
    && typeof record.entry === "object"
    && record.entry !== null;
}
