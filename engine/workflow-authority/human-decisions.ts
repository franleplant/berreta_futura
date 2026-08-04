import type { ArticleDecisionRequest, AuthenticatedHuman, EditorialDecisionRequest } from "../contracts/workflow-run.ts";
import type { WorkflowWaitContext } from "../workflows/internal-types.ts";
import type { LedgerDecision } from "./artifact-ledger.ts";

/**
 * Narrow public surface for authenticated human decisions.
 *
 * The implementation and its persistence capability live in
 * ArtifactLedger.createHumanDecisionAuthority(). This file intentionally
 * exports a type only: there is no constructible decision authority or raw
 * decision persistence function in the module namespace.
 */
export type HumanDecisionAuthority = {
  readonly decide: (
    human: AuthenticatedHuman,
    request: ArticleDecisionRequest,
    durableContext: WorkflowWaitContext,
  ) => Promise<LedgerDecision>;
  readonly decideEditorial: (
    human: AuthenticatedHuman,
    request: EditorialDecisionRequest,
    durableContext: WorkflowWaitContext,
  ) => Promise<import("./artifact-ledger.ts").LedgerEditorialDecision>;
};
