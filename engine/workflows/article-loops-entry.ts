import { createRequire } from "node:module";
import { dirname } from "node:path";
import { isDeepStrictEqual } from "node:util";
import type { WorkflowGlobals } from "@loops/core";

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
 * The function hashed by Loops is the same function executed by the durable
 * adapter. Ports are injected by the private adapter and never serialized.
 */
export default async function articleLoopsEntry(
  globals: WorkflowGlobals,
  ports: ArticleWorkflowPorts,
): Promise<unknown> {
  if (ARTICLE_RUNTIME_GRAPH !== "magazine-article-runtime/1") {
    throw new Error("Magazine article runtime graph identity is invalid");
  }
  const args = globals.args as ArticleRuntimeStartArgs | undefined;
  if (args === undefined) throw new Error("Magazine article workflow requires immutable args");
  assertEntryBinding(args, ports);
  const context: MagazineWorkflowContext = {
    durableContext: () => globals.durableContext?.() as WorkflowDurableContext | undefined,
    reviewStepResultSchema: reviewStepCheckpointSchema,
    step: async (key, fn, options) => {
      if (options.retry === undefined && options.schema === undefined && options.label === undefined) {
        return await globals.step(key, fn, { input: options.input });
      }
      const retryOptions = options.retry;
      const retryOn: "always" | "never" | "retryable" | string[] | undefined = retryOptions === undefined
        ? undefined
        : typeof retryOptions.retryOn === "string" || retryOptions.retryOn === undefined
          ? retryOptions.retryOn
          : [...retryOptions.retryOn];
      return await globals.step(key, fn, {
        input: options.input,
        ...(options.schema === undefined ? {} : { schema: options.schema as never }),
        ...(options.label === undefined ? {} : { label: options.label }),
        retry: {
          ...(retryOptions?.maxAttempts === undefined ? {} : { maxAttempts: retryOptions.maxAttempts }),
          ...(retryOptions?.backoffMs === undefined ? {} : { backoffMs: retryOptions.backoffMs }),
          ...(retryOptions?.backoffMultiplier === undefined ? {} : { backoffMultiplier: retryOptions.backoffMultiplier }),
          ...(retryOn === undefined ? {} : { retryOn }),
        },
      });
    },
    parallel: async <T>(thunks: readonly (() => Promise<T> | T)[], options?: { readonly failureMode?: "fail-fast" | "collect" }): Promise<readonly (T | null)[]> => {
      if (options === undefined) return await globals.parallel([...thunks]);
      return await globals.parallel([...thunks], options) as unknown as readonly (T | null)[];
    },
    wait: async (key, options): Promise<ArticleDecisionAnswer> => {
      const answer = await globals.wait(key, {
        schema: decisionSchema as never,
        request: options.request,
      });
      if (typeof answer !== "object" || answer === null || typeof (answer as { decisionArtifactId?: unknown }).decisionArtifactId !== "string") {
        throw new Error("Loops returned an invalid article decision payload");
      }
      return answer as ArticleDecisionAnswer;
    },
  };
  return await runArticleWorkflow(args, context, ports);
}

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

// Loops currently ships its durable-schema converter with its own Zod major.
// Resolve that exact copy instead of the magazine application's renderer Zod.
const require = createRequire(import.meta.url);
const loopsZod = (require(require.resolve("zod", { paths: [dirname(require.resolve("@loops/core"))] })) as {
  readonly z: {
    readonly object: (shape: Record<string, unknown>) => { readonly strict: () => unknown };
    readonly string: () => { readonly optional: () => unknown };
    readonly literal: (value: string) => unknown;
    readonly enum: (values: readonly string[]) => unknown;
    readonly array: (value: unknown) => unknown;
  };
});
const decisionSchema = loopsZod.z.object({ decisionArtifactId: loopsZod.z.string() });
const reviewStepCheckpointSchema = loopsZod.z.object({
  schemaVersion: loopsZod.z.literal("article-review-checkpoint/1"),
  status: loopsZod.z.enum(["completed", "skipped"]),
  waveId: loopsZod.z.string(),
  checkId: loopsZod.z.string(),
  kind: loopsZod.z.enum(["model_review", "article_measurement"]),
  key: loopsZod.z.string(),
  manuscriptArtifactId: loopsZod.z.string(),
  manuscriptRevisionId: loopsZod.z.string(),
  materialArtifactIds: loopsZod.z.array(loopsZod.z.string()),
  outputArtifactIds: loopsZod.z.array(loopsZod.z.string()),
  resultArtifactId: loopsZod.z.string().optional(),
  reviewerId: loopsZod.z.string().optional(),
  assessment: loopsZod.z.enum(["pass", "findings", "human_required", "not_applicable"]),
  findingArtifactIds: loopsZod.z.array(loopsZod.z.string()),
}).strict();
