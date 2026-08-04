import { createHash } from "node:crypto";

import type { AuthorizedWorker } from "../../authority/local-authority.ts";
import type { ArtifactId, JsonObject, JsonValue } from "../../contracts/index.ts";
import type { ArticleMaterialSet } from "../../article-production/materials.ts";
import type { ArticleAttemptExecutionResult, ArticleAttemptRunner } from "../../article-production/attempts.ts";
import { ArtifactLedger, type LedgerArtifact } from "../../workflow-authority/artifact-ledger.ts";
import type { ClosedWriterCredentialResource } from "../closed-writer/credentials.ts";
import {
  invokeOpenAIResponsesCore,
  OPENAI_RESPONSES_CORE_POLICY,
} from "../closed-writer/openai-responses-core.ts";
import {
  EDITORIAL_WRITER_RESULT_CONTRACT_VERSION,
  editorialWriterOutputSchema,
  parseEditorialWriterResult,
  type EditorialWriterExecutionResult,
  type EditorialWriterResult,
} from "./result.ts";

export const CLOSED_EDITORIAL_WRITER_EXECUTION_CLASS = "closed_editorial_writer/1" as const;

export type ClosedEditorialWriterRuntimeIdentity = {
  readonly schemaVersion: "closed-editorial-writer-runtime/1";
  readonly executionClass: typeof CLOSED_EDITORIAL_WRITER_EXECUTION_CLASS;
  readonly providerCodec: typeof OPENAI_RESPONSES_CORE_POLICY.providerCodec;
  readonly officialEndpointIdentity: typeof OPENAI_RESPONSES_CORE_POLICY.endpoint;
  readonly model: typeof OPENAI_RESPONSES_CORE_POLICY.model;
  readonly reasoningEffort: typeof OPENAI_RESPONSES_CORE_POLICY.reasoningEffort;
  readonly outputSchemaDigest: string;
  readonly requestPolicy: "one_request_no_tools_no_store/1";
};

export const CLOSED_EDITORIAL_WRITER_RUNTIME_IDENTITY: ClosedEditorialWriterRuntimeIdentity = Object.freeze({
  schemaVersion: "closed-editorial-writer-runtime/1",
  executionClass: CLOSED_EDITORIAL_WRITER_EXECUTION_CLASS,
  providerCodec: OPENAI_RESPONSES_CORE_POLICY.providerCodec,
  officialEndpointIdentity: OPENAI_RESPONSES_CORE_POLICY.endpoint,
  model: OPENAI_RESPONSES_CORE_POLICY.model,
  reasoningEffort: OPENAI_RESPONSES_CORE_POLICY.reasoningEffort,
  outputSchemaDigest: `sha256:${createHash("sha256").update(JSON.stringify(editorialWriterOutputSchema), "utf8").digest("hex")}`,
  requestPolicy: "one_request_no_tools_no_store/1",
});

type ClosedEditorialWriterRequest = {
  readonly worker: AuthorizedWorker;
  readonly editorialExecutionId: string;
  readonly operationKey: string;
  readonly currentManuscriptArtifactId: ArtifactId;
  readonly profileArtifactId: ArtifactId;
  readonly articleArtifactIds: readonly ArtifactId[];
  readonly mode?: "initial" | "rewrite";
  readonly revisionContextArtifactIds?: readonly ArtifactId[];
};

type EditorialWriterStep = <T>(
  key: string,
  operation: () => Promise<T> | T,
  options: { readonly input: JsonObject; readonly retry: { readonly maxAttempts: 2; readonly retryOn: "retryable" } },
) => Promise<T>;

export type ClosedEditorialWriterExecutor = {
  readonly runtimeIdentity: ClosedEditorialWriterRuntimeIdentity;
  readonly executeInStep: (step: EditorialWriterStep, request: ClosedEditorialWriterRequest) => Promise<EditorialWriterExecutionResult>;
};

export function createClosedEditorialWriterExecutor(input: {
  readonly ledger: ArtifactLedger;
  readonly credentials: ClosedWriterCredentialResource;
}): ClosedEditorialWriterExecutor {
  if (!(input.ledger instanceof ArtifactLedger) || input.credentials.read === undefined) {
    throw new Error("closed editorial writer requires a trusted ledger and credential resource");
  }
  const runner = input.ledger.createArticleAttemptRunner();
  return Object.freeze({
    runtimeIdentity: CLOSED_EDITORIAL_WRITER_RUNTIME_IDENTITY,
    executeInStep: async (step, request) => await step(
      request.operationKey,
      async () => await executeAttempt(input.ledger, runner, input.credentials, request),
      {
        input: {
          editorialExecutionId: request.editorialExecutionId,
          operationKey: request.operationKey,
          currentManuscriptArtifactId: request.currentManuscriptArtifactId,
          profileArtifactId: request.profileArtifactId,
          articleArtifactIds: request.articleArtifactIds as unknown as JsonValue,
          ...(request.mode === undefined ? {} : { mode: request.mode }),
          ...(request.revisionContextArtifactIds === undefined ? {} : { revisionContextArtifactIds: request.revisionContextArtifactIds as unknown as JsonValue }),
        },
        retry: { maxAttempts: 2, retryOn: "retryable" },
      },
    ),
  });
}

async function executeAttempt(
  ledger: ArtifactLedger,
  runner: ArticleAttemptRunner,
  credentials: ClosedWriterCredentialResource,
  request: ClosedEditorialWriterRequest,
): Promise<EditorialWriterExecutionResult> {
  const run = ledger.requireRunByArticleExecutionId(request.editorialExecutionId as never);
  if (run.articleId !== "opening" || run.editionId !== "004") throw new Error("editorial writer run is not bound to opening Edition 4");
  if (run.manuscriptArtifactId !== request.currentManuscriptArtifactId) throw new Error("editorial writer manuscript is stale");
  const profile = ledger.requireArtifact(request.profileArtifactId);
  if (profile.kind !== "resolved_editorial_profile" || profile.schemaVersion !== "resolved-editorial-profile/1" || profile.payloadKind !== "json" || profile.producingRunId !== run.runId) {
    throw new Error("editorial writer profile is not the exact run-owned profile");
  }
  const inputArtifacts = request.articleArtifactIds.map((id) => ledger.requireArtifact(id));
  if (inputArtifacts.length !== 7 || new Set(inputArtifacts.map((artifact) => artifact.id)).size !== 7) throw new Error("editorial writer requires exactly seven accepted articles");
  if (inputArtifacts.some((artifact) => artifact.kind !== "article_manuscript" || artifact.mediaType !== "text/markdown")) throw new Error("editorial writer received a non-manuscript input");
  const contextArtifacts = (request.revisionContextArtifactIds ?? []).map((id) => ledger.requireArtifact(id));
  if ((request.mode ?? "initial") === "initial" && contextArtifacts.length > 0) throw new Error("initial editorial writer cannot receive revision context");
  if ((request.mode ?? "initial") === "rewrite" && contextArtifacts.length === 0) throw new Error("editorial rewrite requires immutable revision context");
  if (contextArtifacts.some((artifact) => artifact.producingRunId !== run.runId)) throw new Error("editorial revision context is not run-owned");
  const materialArtifacts: ArticleMaterialSet = {
    schemaVersion: "article-material-set/1",
    articleId: "opening",
    role: "writer",
    access: "source_blind",
    manuscriptArtifactId: request.currentManuscriptArtifactId,
    artifacts: [
      { artifactId: request.currentManuscriptArtifactId, articleId: "opening", classification: "manuscript" as const },
      ...inputArtifacts.map((artifact) => ({ artifactId: artifact.id, articleId: "opening", classification: "manuscript" as const })),
      ...contextArtifacts.map((artifact) => ({ artifactId: artifact.id, articleId: "opening", classification: "writer_review_material" as const })),
    ],
    artifactIds: [request.currentManuscriptArtifactId, ...inputArtifacts.map((artifact) => artifact.id), ...contextArtifacts.map((artifact) => artifact.id)],
  };
  const prompt = buildPrompt(ledger, profile, inputArtifacts, request.currentManuscriptArtifactId, contextArtifacts, request.mode ?? "initial");
  if (Buffer.byteLength(prompt, "utf8") > OPENAI_RESPONSES_CORE_POLICY.maxInputBytes) throw new Error("editorial writer input exceeds pinned byte ceiling");
  return await runner.executeModel(
    request.worker,
    {
      rootRunId: run.runId,
      articleExecutionId: request.editorialExecutionId as never,
      articleId: "opening",
      operationKey: request.operationKey,
      manuscriptArtifactId: request.currentManuscriptArtifactId,
      access: "source_blind",
      materials: materialArtifacts,
    },
    async ({ claim }) => {
      const response = await invokeOpenAIResponsesCore(credentials, prompt, { name: "editorial_writer_result", schema: editorialWriterOutputSchema });
      const result = parseEditorialWriterResult(response.output);
      return {
        value: result,
        artifacts: resultArtifacts(result, profile, inputArtifacts, request.currentManuscriptArtifactId, contextArtifacts, response.responseId, claim),
      };
    },
  ) as unknown as EditorialWriterExecutionResult;
}

function buildPrompt(ledger: ArtifactLedger, profile: LedgerArtifact, articles: readonly LedgerArtifact[], currentManuscriptArtifactId: ArtifactId, contextArtifacts: readonly LedgerArtifact[], mode: "initial" | "rewrite"): string {
  const sections = [
    "MAGAZINE CLOSED OPENING EDITORIAL WRITER REQUEST",
    `runtimeIdentity=${JSON.stringify(CLOSED_EDITORIAL_WRITER_RUNTIME_IDENTITY)}`,
    "The seven article manuscripts below are the complete allowed English issue set. Do not read or infer source evidence.",
    artifactSection(profile, ledger),
    ...articles.map((artifact) => artifactSection(artifact, ledger)),
    ...(mode === "rewrite" ? [
      "This is a rewrite. Preserve the approved editorial direction while addressing the exact immutable review context below.",
      artifactSection(ledger.requireArtifact(currentManuscriptArtifactId), ledger),
      ...contextArtifacts.map((artifact) => artifactSection(artifact, ledger)),
    ] : []),
    "Return only the JSON value described by the pinned response schema.",
  ];
  return sections.join("\n");
}

function artifactSection(artifact: LedgerArtifact, ledger: ArtifactLedger): string {
  const bytes = ledger.readArtifact(artifact.id).bytes;
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  return `--- artifact ${artifact.id} ${artifact.mediaType} sha256:${artifact.digest} ---\n${text}\n--- end artifact ${artifact.id} ---`;
}

function resultArtifacts(
  result: EditorialWriterResult,
  profile: LedgerArtifact,
  articles: readonly LedgerArtifact[],
  currentManuscriptArtifactId: ArtifactId,
  contextArtifacts: readonly LedgerArtifact[],
  responseId: string,
  claim: { readonly articleExecutionId: string; readonly operationKey: string; readonly operationInputDigest: string; readonly access: string; readonly attemptId: string },
) {
  const parents = [profile.id, ...articles.map((artifact) => artifact.id), currentManuscriptArtifactId, ...contextArtifacts.map((artifact) => artifact.id)].map((artifactId) => ({ artifactId, relation: "editorial_writer_input" }));
  const metadata: JsonObject = {
    editorialId: "opening",
    editorialExecutionId: claim.articleExecutionId,
    operationKey: claim.operationKey,
    operationInputDigest: claim.operationInputDigest,
    access: claim.access,
    writerExecutionClass: CLOSED_EDITORIAL_WRITER_EXECUTION_CLASS,
    writerRuntimeIdentity: CLOSED_EDITORIAL_WRITER_RUNTIME_IDENTITY as unknown as JsonObject,
    writerInputArtifactIds: parents.map((parent) => parent.artifactId) as unknown as JsonValue,
    providerResponseId: responseId,
    revisionId: `editorial-${claim.attemptId}`,
  };
  return [
    { key: "manuscript", kind: "editorial_manuscript", schemaVersion: "editorial-manuscript/1", mediaType: "text/markdown", origin: "model" as const, payload: { kind: "text" as const, text: result.manuscript }, parents, metadata: { ...metadata, title: result.title, label: result.label, byline: result.byline } },
    { key: "working-notes", kind: "editorial_working_notes", schemaVersion: "editorial-working-notes/1", mediaType: "text/plain", origin: "model" as const, payload: { kind: "text" as const, text: result.workingNotes }, parents, metadata },
    { key: "finding-dispositions", kind: "editorial_finding_dispositions", schemaVersion: "editorial-finding-dispositions/1", mediaType: "application/json", origin: "model" as const, payload: { kind: "json" as const, value: { schemaVersion: "editorial-finding-dispositions/1", dispositions: result.dispositions as unknown as JsonValue } }, parents, metadata },
  ];
}
