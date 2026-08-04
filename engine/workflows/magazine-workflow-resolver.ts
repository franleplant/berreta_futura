import { dirname, resolve } from "node:path";

import type {
  WorkflowDescriptor,
  Runtime,
  RuntimeConfig,
} from "@loops/core";
import { loadWorkflowScript } from "@loops/workflow";

import type { ArticleRuntimeStartArgs, ArticleWorkflowPorts } from "./internal-types.ts";
import { invokeArticleWorkflowWithPorts } from "./article-loops-entry.ts";

/** The only child workflow currently exposed by the Magazine host. */
export const MAGAZINE_ARTICLE_WORKFLOW_NAME = "magazine-article" as const;
export const MAGAZINE_ARTICLE_WORKFLOW_ENTRY = "engine/workflows/article-loops-entry.ts" as const;

type RuntimeWithGlobals = Pick<Runtime, "globals"> & {
  readonly currentWorkflowBaseDir?: () => string | undefined;
};

export type MagazineWorkflowResolverOptions = {
  readonly projectRoot: string;
  readonly articlePorts: ArticleWorkflowPorts;
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
  const entryPath = resolve(options.projectRoot, MAGAZINE_ARTICLE_WORKFLOW_ENTRY);
  let modulePromise: ReturnType<typeof loadWorkflowScript> | undefined;
  return async (nameOrRef, _args, runtime): Promise<WorkflowDescriptor> => {
    const runtimeWithGlobals = runtime as RuntimeWithGlobals;
    const baseDir = runtimeWithGlobals.currentWorkflowBaseDir?.() ?? options.projectRoot;
    const requestedPath = typeof nameOrRef === "string"
      ? resolve(baseDir, nameOrRef)
      : resolve(baseDir, nameOrRef.scriptPath);
    if (requestedPath !== entryPath) {
      throw new Error(`Magazine workflow resolver only permits ${MAGAZINE_ARTICLE_WORKFLOW_ENTRY}`);
    }
    modulePromise ??= loadWorkflowScript(entryPath);
    const articleModule = await modulePromise;
    if (articleModule.meta.name !== MAGAZINE_ARTICLE_WORKFLOW_NAME) {
      throw new Error("Magazine article workflow metadata changed");
    }
    const descriptor: WorkflowDescriptor = {
      name: articleModule.meta.name,
      version: articleModule.version,
      baseDir: dirname(entryPath),
      run: async (childArgs: unknown, childRuntime: unknown): Promise<unknown> => {
        if (!isArticleRuntimeStartArgs(childArgs)) {
          throw new Error("Magazine article child args are not authenticated launch args");
        }
        const childGlobals = (childRuntime as RuntimeWithGlobals).globals;
        return await invokeArticleWorkflowWithPorts(
          childGlobals,
          options.articlePorts,
          childArgs,
        );
      },
    };
    return descriptor;
  };
}

/** Return the fixed child reference callers may pass to `ctx.workflow`. */
export function magazineArticleWorkflowRef(): { readonly scriptPath: string } {
  return Object.freeze({ scriptPath: MAGAZINE_ARTICLE_WORKFLOW_ENTRY });
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
