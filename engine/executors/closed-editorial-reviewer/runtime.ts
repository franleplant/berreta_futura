import { createHash } from "node:crypto";

import type { ArticleMaterialSet } from "../../article-production/materials.ts";
import type { ArticleAttemptRunner } from "../../article-production/attempts.ts";
import type { AuthorizedWorker } from "../../authority/local-authority.ts";
import type { ArtifactId, JsonObject, JsonValue } from "../../contracts/index.ts";
import type { ArticleAttemptExecutionResult, EditorialReviewResult } from "../../workflows/internal-types.ts";
import { ArtifactLedger, type LedgerArtifact } from "../../workflow-authority/artifact-ledger.ts";
import type { ClosedWriterCredentialResource } from "../closed-writer/credentials.ts";
import { invokeOpenAIResponsesCore, OPENAI_RESPONSES_CORE_POLICY } from "../closed-writer/openai-responses-core.ts";
import { bindEditorialReviewResult, editorialReviewOutputSchema, editorialReviewResultJson, parseEditorialReviewModelOutput } from "./result.ts";

export const CLOSED_EDITORIAL_REVIEWER_EXECUTION_CLASS = "closed_editorial_reviewer/1" as const;

export const CLOSED_EDITORIAL_REVIEWER_RUNTIME_IDENTITY = Object.freeze({
  schemaVersion: "closed-editorial-reviewer-runtime/1",
  executionClass: CLOSED_EDITORIAL_REVIEWER_EXECUTION_CLASS,
  providerCodec: OPENAI_RESPONSES_CORE_POLICY.providerCodec,
  officialEndpointIdentity: OPENAI_RESPONSES_CORE_POLICY.endpoint,
  model: OPENAI_RESPONSES_CORE_POLICY.model,
  reasoningEffort: OPENAI_RESPONSES_CORE_POLICY.reasoningEffort,
  outputSchemaDigest: `sha256:${createHash("sha256").update(JSON.stringify(editorialReviewOutputSchema), "utf8").digest("hex")}`,
  requestPolicy: "one_request_no_tools_no_store/1",
});

type EditorialReviewerRequest = {
  readonly worker: AuthorizedWorker;
  readonly editorialExecutionId: string;
  readonly operationKey: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly reviewCycleId: string;
};

type EditorialReviewerStep = <T>(
  key: string,
  operation: () => Promise<T> | T,
  options: { readonly input: JsonObject; readonly retry: { readonly maxAttempts: 2; readonly retryOn: "retryable" } },
) => Promise<T>;

export type ClosedEditorialReviewerExecutor = {
  readonly executeInStep: (step: EditorialReviewerStep, request: EditorialReviewerRequest) => Promise<ArticleAttemptExecutionResult<EditorialReviewResult>>;
};

export function createClosedEditorialReviewerExecutor(input: {
  readonly ledger: ArtifactLedger;
  readonly credentials: ClosedWriterCredentialResource;
  readonly attemptRunner?: ArticleAttemptRunner;
}): ClosedEditorialReviewerExecutor {
  if (!(input.ledger instanceof ArtifactLedger) || input.credentials.read === undefined) throw new Error("closed editorial reviewer requires a trusted ledger and credential resource");
  const runner = input.attemptRunner ?? input.ledger.createArticleAttemptRunner();
  return Object.freeze({
    executeInStep: async (step, request) => await step(request.operationKey, async () => await executeAttempt(input.ledger, runner, input.credentials, request), {
      input: {
        schemaVersion: "closed-editorial-reviewer-step-input/1",
        editorialExecutionId: request.editorialExecutionId,
        operationKey: request.operationKey,
        manuscriptArtifactId: request.manuscriptArtifactId,
        reviewPlanArtifactId: request.reviewPlanArtifactId,
        measurementArtifactId: request.measurementArtifactId,
        reviewCycleId: request.reviewCycleId,
      },
      retry: { maxAttempts: 2, retryOn: "retryable" },
    }),
  });
}

async function executeAttempt(
  ledger: ArtifactLedger,
  runner: ArticleAttemptRunner,
  credentials: ClosedWriterCredentialResource,
  request: EditorialReviewerRequest,
): Promise<ArticleAttemptExecutionResult<EditorialReviewResult>> {
  const run = ledger.requireRunByArticleExecutionId(request.editorialExecutionId as never);
  if (run.articleId !== "opening" || run.editionId !== "004" || run.manuscriptArtifactId !== request.manuscriptArtifactId) throw new Error("editorial reviewer request is stale");
  const manuscript = requireArtifact(ledger, request.manuscriptArtifactId, "editorial_manuscript", "text/markdown");
  const plan = requireArtifact(ledger, request.reviewPlanArtifactId, "editorial_review_plan", "application/json");
  const measurement = requireArtifact(ledger, request.measurementArtifactId, "editorial_measurement", "application/json");
  const ids = [manuscript.id, plan.id, measurement.id] as const;
  const materials: ArticleMaterialSet = {
    schemaVersion: "article-material-set/1",
    articleId: "opening",
    role: "craft",
    access: "source_blind",
    manuscriptArtifactId: manuscript.id,
    artifacts: [
      { artifactId: manuscript.id, articleId: "opening", classification: "manuscript" },
      { artifactId: plan.id, articleId: "opening", classification: "judge_prompt" },
      { artifactId: measurement.id, articleId: "opening", classification: "measurement_input" },
    ],
    artifactIds: ids,
  };
  return await runner.executeModel(request.worker, {
    rootRunId: run.runId,
    articleExecutionId: request.editorialExecutionId as never,
    articleId: "opening",
    operationKey: request.operationKey,
    manuscriptArtifactId: manuscript.id,
    access: "source_blind",
    materials,
  }, async ({ claim }) => {
    const prompt = buildPrompt(ledger, [manuscript, plan, measurement]);
    if (Buffer.byteLength(prompt, "utf8") > OPENAI_RESPONSES_CORE_POLICY.maxInputBytes) throw new Error("editorial reviewer input exceeds pinned byte ceiling");
    const response = await invokeOpenAIResponsesCore(credentials, prompt, { name: "editorial_review_model_output", schema: editorialReviewOutputSchema });
    const value = bindEditorialReviewResult({ output: parseEditorialReviewModelOutput(response.output), manuscriptArtifactId: manuscript.id, reviewPlanArtifactId: plan.id, measurementArtifactId: measurement.id, reviewCycleId: request.reviewCycleId });
    return {
      value,
      artifacts: [{
        key: "result",
        kind: "editorial_review_result",
        schemaVersion: "editorial-review-result/1",
        mediaType: "application/json",
        origin: "model",
        payload: { kind: "json", value: editorialReviewResultJson(value) },
        parents: ids.map((artifactId) => ({ artifactId, relation: "editorial_review_input" })),
        metadata: {
          editionId: "004",
          editorialId: "opening",
          target: "editorial:opening",
          reviewCycleId: request.reviewCycleId,
          reviewerExecutionClass: CLOSED_EDITORIAL_REVIEWER_EXECUTION_CLASS,
          reviewerRuntimeIdentity: CLOSED_EDITORIAL_REVIEWER_RUNTIME_IDENTITY as unknown as JsonObject,
          reviewerInputArtifactIds: ids as unknown as JsonValue,
          providerResponseId: response.responseId,
          operationInputDigest: claim.operationInputDigest,
        },
      }],
    };
  });
}

function requireArtifact(ledger: ArtifactLedger, id: ArtifactId, kind: string, mediaType: string): LedgerArtifact {
  const artifact = ledger.requireArtifact(id);
  if (artifact.kind !== kind || artifact.mediaType !== mediaType) throw new Error(`editorial reviewer input ${id} has the wrong contract`);
  return artifact;
}

function buildPrompt(ledger: ArtifactLedger, artifacts: readonly LedgerArtifact[]): string {
  return [
    "MAGAZINE CLOSED OPENING EDITORIAL REVIEW REQUEST",
    `runtimeIdentity=${JSON.stringify(CLOSED_EDITORIAL_REVIEWER_RUNTIME_IDENTITY)}`,
    "Review only editorial:opening. The article manuscripts and source evidence are unavailable and out of scope.",
    "Return only the JSON value described by the pinned response schema.",
    ...artifacts.map((artifact) => {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(artifact.id).bytes);
      return `--- artifact ${artifact.id} ${artifact.mediaType} sha256:${artifact.digest} ---\n${text}\n--- end artifact ${artifact.id} ---`;
    }),
  ].join("\n");
}
