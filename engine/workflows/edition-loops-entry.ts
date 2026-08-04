import { AsyncLocalStorage } from "node:async_hooks";
import type { WorkflowGlobals } from "@loops/core";
import type { WorkflowContext } from "loops";
import { invokeWorkflow } from "loops";

import { EDITION_WORKFLOW_NAME, type EditionWorkflowArgs } from "./edition-workflow.ts";
import runEditionWorkflow from "./edition-workflow.ts";
import type { ArticleWorkflowPorts } from "./internal-types.ts";

export const meta = {
  name: "magazine-edition",
  description: "Durable Edition 4 root that plans and launches seven source-faithful article children.",
};

export function invokeEditionWorkflowWithPorts(
  globals: WorkflowGlobals,
  ports: ArticleWorkflowPorts,
  args: EditionWorkflowArgs = globals.args as EditionWorkflowArgs,
): Promise<unknown> {
  const scopedGlobals = args === globals.args ? globals : { ...globals, args };
  return editionPortsStorage.run(ports, () => invokeWorkflow(scopedGlobals, run));
}

export default async function run(
  context: WorkflowContext<EditionWorkflowArgs>,
): Promise<unknown> {
  const ports = editionPortsStorage.getStore();
  if (ports === undefined) throw new Error("Magazine edition workflow requires host-bound article ports");
  return await runEditionWorkflow(context, ports);
}

const editionPortsStorage = new AsyncLocalStorage<ArticleWorkflowPorts>();
