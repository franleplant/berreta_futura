import { createRequire } from "node:module";
import { dirname } from "node:path";
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
  const context: MagazineWorkflowContext = {
    durableContext: () => globals.durableContext?.() as WorkflowDurableContext | undefined,
    step: async (key, fn, options) => await globals.step(key, fn, { input: options.input }),
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

// Loops currently ships its durable-schema converter with its own Zod major.
// Resolve that exact copy instead of the magazine application's renderer Zod.
const require = createRequire(import.meta.url);
const loopsZod = (require(require.resolve("zod", { paths: [dirname(require.resolve("@loops/core"))] })) as {
  readonly z: { readonly object: (shape: Record<string, unknown>) => unknown; readonly string: () => unknown };
});
const decisionSchema = loopsZod.z.object({ decisionArtifactId: loopsZod.z.string() });
