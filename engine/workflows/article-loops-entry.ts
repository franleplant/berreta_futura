import { AsyncLocalStorage } from "node:async_hooks";
import { isDeepStrictEqual } from "node:util";
import type { WorkflowGlobals } from "@loops/core";
import type { WorkflowContext } from "loops";
import { invokeWorkflow } from "loops";
import { z } from "zod/v3";

import type { ArticleDecisionAnswer } from "../contracts/workflow-run.ts";
import type {
  ArticleRuntimeStartArgs,
  ArticleWorkflowPorts,
  MagazineWorkflowContext,
  WorkflowDurableContext,
} from "./internal-types.ts";
import { runArticleWorkflow } from "./article-workflow.ts";
import { ARTICLE_RUNTIME_GRAPH } from "./article-runtime.ts";

/** Static metadata used by Loops source-graph pinning and inspection. */
export const meta = {
  name: "magazine-article",
  description: "Measure an immutable article and wait for an authenticated editorial decision.",
};

/**
 * Run the fixed article script with host-owned ports. Ports are process-local
 * capabilities and never become part of the immutable workflow args.
 * AsyncLocalStorage keeps concurrent root and child invocations isolated.
 */
export function invokeArticleWorkflowWithPorts(
  globals: WorkflowGlobals,
  ports: ArticleWorkflowPorts,
  args: ArticleRuntimeStartArgs = globals.args as ArticleRuntimeStartArgs,
): Promise<unknown> {
  const scopedGlobals = args === globals.args ? globals : { ...globals, args };
  return articleWorkflowPortsStorage.run(ports, () => invokeWorkflow(
    scopedGlobals,
    run,
  ));
}

/**
 * Explicit Loops workflow entry. The host adapter binds ports around this
 * function; the workflow itself receives only its immutable `ctx.input`.
 */
export default async function run(
  context: WorkflowContext<ArticleRuntimeStartArgs>,
): Promise<unknown> {
  const ports = articleWorkflowPortsStorage.getStore();
  if (ports === undefined) throw new Error("Magazine article workflow requires host-bound ports");
  if (ARTICLE_RUNTIME_GRAPH !== "magazine-article-runtime/1") {
    throw new Error("Magazine article runtime graph identity is invalid");
  }
  const args = context.input;
  assertEntryBinding(args, ports);
  const workflowContext: MagazineWorkflowContext = {
    durableContext: () => context.durableContext?.() as WorkflowDurableContext | undefined,
    reviewStepResultSchema: reviewStepCheckpointSchema,
    step: async <T>(key: string, fn: () => Promise<T> | T, options: Parameters<MagazineWorkflowContext["step"]>[2]): Promise<T> => {
      const retryOptions = options.retry;
      const retryOn: "always" | "never" | "retryable" | string[] | undefined = retryOptions === undefined
        ? undefined
        : typeof retryOptions.retryOn === "string" || retryOptions.retryOn === undefined
          ? retryOptions.retryOn
          : [...retryOptions.retryOn];
      return await context.step(key, fn, {
        input: options.input,
        ...(options.schema === undefined ? {} : { schema: options.schema as never }),
        ...(options.label === undefined ? {} : { label: options.label }),
        retry: {
          ...(retryOptions?.maxAttempts === undefined ? {} : { maxAttempts: retryOptions.maxAttempts }),
          ...(retryOptions?.backoffMs === undefined ? {} : { backoffMs: retryOptions.backoffMs }),
          ...(retryOptions?.backoffMultiplier === undefined ? {} : { backoffMultiplier: retryOptions.backoffMultiplier }),
          ...(retryOn === undefined ? {} : { retryOn }),
        },
      }) as T;
    },
    parallel: async <T>(thunks: readonly (() => Promise<T> | T)[], options?: { readonly failureMode?: "fail-fast" | "collect" }): Promise<readonly (T | null)[]> => {
      if (options === undefined) return await context.parallel([...thunks]);
      return await context.parallel([...thunks], options) as unknown as readonly (T | null)[];
    },
    wait: async (key, options): Promise<ArticleDecisionAnswer> => {
      const answer = await context.wait(key, {
        schema: decisionSchema as never,
        request: options.request,
      });
      if (typeof answer !== "object" || answer === null || typeof (answer as { decisionArtifactId?: unknown }).decisionArtifactId !== "string") {
        throw new Error("Loops returned an invalid article decision payload");
      }
      return answer as ArticleDecisionAnswer;
    },
  };
  return await runArticleWorkflow(args, workflowContext, ports);
}

const articleWorkflowPortsStorage = new AsyncLocalStorage<ArticleWorkflowPorts>();

function assertEntryBinding(args: ArticleRuntimeStartArgs, ports: ArticleWorkflowPorts): void {
  const artifact = ports.ledger.requireArtifact(args.entryArtifactId);
  if (
    artifact.kind !== "article_workflow_entry"
    || artifact.schemaVersion !== "loops-article-entry-input/1"
    || artifact.payloadKind !== "json"
    || artifact.producingRunId !== args.runId
    || artifact.metadata.articleId !== args.articleId
  ) {
    throw new Error("Article workflow entry artifact is not the exact run-owned entry");
  }
  const value = ports.ledger.readArtifact(args.entryArtifactId).bytes;
  let decoded: unknown;
  try {
    decoded = JSON.parse(Buffer.from(value).toString("utf8"));
  } catch (error) {
    throw new Error("Article workflow entry artifact is not valid JSON", { cause: error });
  }
  if (!isDeepStrictEqual(decoded, args.entry)) {
    throw new Error("Article workflow args do not match the immutable entry artifact");
  }
}

const decisionSchema = z.object({ decisionArtifactId: z.string() });
const reviewStepCheckpointSchema = z.object({
  schemaVersion: z.literal("article-review-checkpoint/1"),
  status: z.enum(["completed", "skipped"]),
  waveId: z.string(),
  checkId: z.string(),
  kind: z.enum(["model_review", "article_measurement"]),
  key: z.string(),
  manuscriptArtifactId: z.string(),
  manuscriptRevisionId: z.string(),
  materialArtifactIds: z.array(z.string()),
  outputArtifactIds: z.array(z.string()),
  resultArtifactId: z.string().optional(),
  reviewerId: z.string().optional(),
  assessment: z.enum(["pass", "findings", "human_required", "not_applicable"]),
  findingArtifactIds: z.array(z.string()),
}).strict();
