import { AsyncLocalStorage } from "node:async_hooks";
import type { WorkflowGlobals } from "@loops/core";
import type { WorkflowContext } from "loops";
import { invokeWorkflow } from "loops";
import { z } from "zod/v3";

import type { ArticleWorkflowPorts, MagazineWorkflowContext } from "./internal-types.ts";
import {
  runOpeningEditorialWorkflow,
  type OpeningEditorialWorkflowArgs,
} from "./editorial-workflow.ts";

export const meta = {
  name: "magazine-opening-editorial",
  description: "Durable source-blind opening editorial writer for the English Edition 4 issue.",
};

export function invokeEditorialWorkflowWithPorts(
  globals: WorkflowGlobals,
  ports: ArticleWorkflowPorts,
  args: OpeningEditorialWorkflowArgs = globals.args as OpeningEditorialWorkflowArgs,
): Promise<unknown> {
  const scopedGlobals = args === globals.args ? globals : { ...globals, args };
  return editorialPortsStorage.run(ports, () => invokeWorkflow(scopedGlobals, run));
}

export default async function run(context: WorkflowContext<OpeningEditorialWorkflowArgs>): Promise<unknown> {
  const ports = editorialPortsStorage.getStore();
  if (ports === undefined) throw new Error("Magazine editorial workflow requires host-bound ports");
  const workflowContext: MagazineWorkflowContext = {
    durableContext: () => context.durableContext?.() as never,
    step: async (key, fn, options) => await context.step(key, fn, {
      input: options.input,
      ...(options.schema === undefined ? {} : { schema: options.schema as never }),
      ...(options.label === undefined ? {} : { label: options.label }),
      ...(options.retry === undefined ? {} : { retry: options.retry as never }),
    }) as never,
    parallel: async (thunks, options) => await context.parallel([...thunks], options as never) as never,
    wait: async (key, options) => {
      const answer = await context.wait(key, {
        schema: editorialDecisionAnswerSchema as never,
        request: options.request,
      });
      if (typeof answer !== "object" || answer === null || typeof (answer as { readonly decisionArtifactId?: unknown }).decisionArtifactId !== "string") {
        throw new Error("Loops returned an invalid editorial decision payload");
      }
      return answer as { readonly decisionArtifactId: import("../contracts/index.ts").ArtifactId };
    },
  };
  return await runOpeningEditorialWorkflow(context.input, workflowContext, ports);
}

const editorialPortsStorage = new AsyncLocalStorage<ArticleWorkflowPorts>();
const editorialDecisionAnswerSchema = z.object({ decisionArtifactId: z.string() }).strict();
