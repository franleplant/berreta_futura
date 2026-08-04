import { createHash } from "node:crypto";

import type { AuthorizedWorker } from "../../authority/local-authority.ts";
import type { ArtifactId, JsonObject, JsonValue } from "../../contracts/index.ts";
import { assertArticleExecutionMaterials, type ArticleMaterialSet } from "../../article-production/materials.ts";
import type { ArticleAttemptExecutionResult, ArticleAttemptRunner } from "../../article-production/attempts.ts";
import { ArtifactLedger, type LedgerArtifact } from "../../workflow-authority/artifact-ledger.ts";
import type { ClosedWriterCredentialResource } from "../closed-writer/credentials.ts";
import { invokeOpenAIResponsesCore, OPENAI_RESPONSES_CORE_POLICY } from "../closed-writer/openai-responses-core.ts";
import { assertTranslatedMarkdownStructure } from "./markdown.ts";
import {
  parseTranslationWriterResult,
  translationWriterOutputSchema,
  type TranslationWriterExecutionResult,
  type TranslationWriterResult,
} from "./result.ts";

export const CLOSED_TRANSLATION_WRITER_EXECUTION_CLASS = "closed_translation_writer/1" as const;

export type ClosedTranslationWriterRuntimeIdentity = {
  readonly schemaVersion: "closed-translation-writer-runtime/1";
  readonly executionClass: typeof CLOSED_TRANSLATION_WRITER_EXECUTION_CLASS;
  readonly providerCodec: typeof OPENAI_RESPONSES_CORE_POLICY.providerCodec;
  readonly officialEndpointIdentity: typeof OPENAI_RESPONSES_CORE_POLICY.endpoint;
  readonly model: typeof OPENAI_RESPONSES_CORE_POLICY.model;
  readonly reasoningEffort: typeof OPENAI_RESPONSES_CORE_POLICY.reasoningEffort;
  readonly outputSchemaDigest: string;
  readonly requestPolicy: "one_request_no_tools_no_store_repair/1";
};

export const CLOSED_TRANSLATION_WRITER_RUNTIME_IDENTITY: ClosedTranslationWriterRuntimeIdentity = Object.freeze({
  schemaVersion: "closed-translation-writer-runtime/1",
  executionClass: CLOSED_TRANSLATION_WRITER_EXECUTION_CLASS,
  providerCodec: OPENAI_RESPONSES_CORE_POLICY.providerCodec,
  officialEndpointIdentity: OPENAI_RESPONSES_CORE_POLICY.endpoint,
  model: OPENAI_RESPONSES_CORE_POLICY.model,
  reasoningEffort: OPENAI_RESPONSES_CORE_POLICY.reasoningEffort,
  outputSchemaDigest: `sha256:${createHash("sha256").update(JSON.stringify(translationWriterOutputSchema), "utf8").digest("hex")}`,
  requestPolicy: "one_request_no_tools_no_store_repair/1",
});

export type ClosedTranslationWriterRequest = {
  readonly worker: AuthorizedWorker;
  readonly translationExecutionId: string;
  readonly operationKey: string;
  readonly pieceKind: "article" | "editorial";
  readonly pieceId: string;
  readonly language: string;
  readonly englishArtifactId: ArtifactId;
  readonly englishDigest: string;
  readonly promptArtifactId: ArtifactId;
  readonly inputArtifactIds: readonly ArtifactId[];
};

type TranslationWriterStep = <T>(
  key: string,
  operation: () => Promise<T> | T,
  options: { readonly input: JsonObject; readonly retry: { readonly maxAttempts: 2; readonly retryOn: "retryable" } },
) => Promise<T>;

export type ClosedTranslationWriterExecutor = {
  readonly runtimeIdentity: ClosedTranslationWriterRuntimeIdentity;
  readonly executeInStep: (step: TranslationWriterStep, request: ClosedTranslationWriterRequest) => Promise<TranslationWriterExecutionResult>;
};

export function createClosedTranslationWriterExecutor(input: {
  readonly ledger: ArtifactLedger;
  readonly credentials: ClosedWriterCredentialResource;
}): ClosedTranslationWriterExecutor {
  if (!(input.ledger instanceof ArtifactLedger) || input.credentials.read === undefined) {
    throw new Error("closed translation writer requires a trusted ledger and credential resource");
  }
  const runner = input.ledger.createArticleAttemptRunner();
  return Object.freeze({
    runtimeIdentity: CLOSED_TRANSLATION_WRITER_RUNTIME_IDENTITY,
    executeInStep: async (step, request) => await step(
      request.operationKey,
      async () => await executeAttempt(input.ledger, runner, input.credentials, request),
      {
        input: {
          schemaVersion: "closed-translation-writer-step-input/1",
          translationExecutionId: request.translationExecutionId,
          operationKey: request.operationKey,
          pieceKind: request.pieceKind,
          pieceId: request.pieceId,
          language: request.language,
          englishArtifactId: request.englishArtifactId,
          englishDigest: request.englishDigest,
          promptArtifactId: request.promptArtifactId,
          inputArtifactIds: request.inputArtifactIds as unknown as JsonValue,
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
  request: ClosedTranslationWriterRequest,
): Promise<TranslationWriterExecutionResult> {
  validateRequest(request);
  const run = ledger.requireRunByArticleExecutionId(request.translationExecutionId as never);
  if (run.editionId !== "004" || run.articleId !== request.pieceId || run.manuscriptArtifactId !== request.englishArtifactId) {
    throw new Error("translation run is not bound to the exact English piece");
  }
  const english = ledger.readArtifact(request.englishArtifactId);
  if (english.artifact.digest !== request.englishDigest) throw new Error("translation English artifact digest changed");
  if (english.artifact.mediaType !== "text/markdown") throw new Error("translation English input must be Markdown");
  const prompt = ledger.requireArtifact(request.promptArtifactId);
  if (prompt.mediaType !== "text/markdown") throw new Error("translation prompt must be Markdown");
  const extras = request.inputArtifactIds.filter((id) => id !== request.promptArtifactId).map((id) => ledger.requireArtifact(id));
  if (extras.some((artifact) => artifact.mediaType !== "text/markdown")) throw new Error("translation policy input must be Markdown");
  const materials: ArticleMaterialSet = {
    schemaVersion: "article-material-set/1",
    articleId: request.pieceId,
    role: "writer",
    access: "source_blind",
    manuscriptArtifactId: request.englishArtifactId,
    artifacts: [
      { artifactId: request.englishArtifactId, articleId: request.pieceId, classification: "manuscript" },
      { artifactId: request.promptArtifactId, articleId: request.pieceId, classification: "writer_prompt" },
      ...extras.map((artifact) => ({ artifactId: artifact.id, articleId: request.pieceId, classification: "writing_rules" as const })),
    ],
    artifactIds: [request.englishArtifactId, request.promptArtifactId, ...extras.map((artifact) => artifact.id)],
  };
  assertArticleExecutionMaterials({ articleId: request.pieceId, manuscriptArtifactId: request.englishArtifactId, access: "source_blind", materials });
  const promptText = buildPrompt(ledger, request, english.artifact, prompt, extras);
  if (Buffer.byteLength(promptText, "utf8") > OPENAI_RESPONSES_CORE_POLICY.maxInputBytes) throw new Error("translation input exceeds pinned byte ceiling");
  return await runner.executeModel(
    request.worker,
    {
      rootRunId: run.runId,
      articleExecutionId: request.translationExecutionId as never,
      articleId: request.pieceId,
      operationKey: request.operationKey,
      manuscriptArtifactId: request.englishArtifactId,
      access: "source_blind",
      materials,
    },
    async ({ claim }) => {
      const response = await invokeOpenAIResponsesCore(credentials, promptText, { name: "translation_writer_result", schema: translationWriterOutputSchema });
      const result = parseTranslationWriterResult(response.output);
      if (result.englishSha256 !== `sha256:${request.englishDigest}`) throw new Error("translation result does not pin the exact English digest");
      const englishText = new TextDecoder("utf-8", { fatal: true }).decode(english.bytes);
      assertTranslatedMarkdownStructure(englishText, result.markdown);
      return {
        value: result,
        artifacts: resultArtifacts(result, request, response.responseId, claim, materials),
      };
    },
  ) as unknown as TranslationWriterExecutionResult;
}

function buildPrompt(
  ledger: ArtifactLedger,
  request: ClosedTranslationWriterRequest,
  english: LedgerArtifact,
  prompt: LedgerArtifact,
  extras: readonly LedgerArtifact[],
): string {
  const englishText = new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(english.id).bytes);
  const promptText = new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(prompt.id).bytes);
  const sections = [
    "MAGAZINE CLOSED TRANSLATION WRITER REQUEST",
    `runtimeIdentity=${JSON.stringify(CLOSED_TRANSLATION_WRITER_RUNTIME_IDENTITY)}`,
    `pieceKind=${request.pieceKind}`,
    `pieceId=${request.pieceId}`,
    `language=${request.language}`,
    `englishSha256=sha256:${request.englishDigest}`,
    "Translate into educated castellano with restrained Argentine preferences. Preserve Markdown structure, links, frontmatter keys, and fenced code exactly. Do not add footnotes. Return only the pinned JSON result.",
    artifactSection(prompt, promptText),
    ...extras.map((artifact) => artifactSection(artifact, new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(artifact.id).bytes))),
    artifactSection(english, englishText),
  ];
  return sections.join("\n");
}

function artifactSection(artifact: LedgerArtifact, text: string): string {
  return `--- artifact ${artifact.id} ${artifact.mediaType} sha256:${artifact.digest} ---\n${text}\n--- end artifact ${artifact.id} ---`;
}

function resultArtifacts(
  result: TranslationWriterResult,
  request: ClosedTranslationWriterRequest,
  responseId: string,
  claim: { readonly articleExecutionId: string; readonly operationKey: string; readonly operationInputDigest: string; readonly access: string; readonly attemptId: string; readonly claimId: string },
  materials: ArticleMaterialSet,
) {
  const parents = materials.artifactIds.map((artifactId) => ({ artifactId, relation: "translation_writer_input" }));
  const metadata: JsonObject = {
    schemaVersion: "translation-artifact-metadata/1",
    translationExecutionClass: CLOSED_TRANSLATION_WRITER_EXECUTION_CLASS,
    translationRuntimeIdentity: CLOSED_TRANSLATION_WRITER_RUNTIME_IDENTITY as unknown as JsonObject,
    pieceKind: request.pieceKind,
    pieceId: request.pieceId,
    language: request.language,
    sourceLanguage: "en",
    englishArtifactId: request.englishArtifactId,
    englishDigest: request.englishDigest,
    operationKey: claim.operationKey,
    operationInputDigest: claim.operationInputDigest,
    claimId: claim.claimId,
    attemptId: claim.attemptId,
    access: claim.access,
    translationInputArtifactIds: materials.artifactIds as unknown as JsonValue,
    providerResponseId: responseId,
  };
  return [{
    key: "translated-piece",
    kind: "translated_piece",
    schemaVersion: "translation-writer-result/1",
    mediaType: "text/markdown",
    origin: "model" as const,
    payload: { kind: "text" as const, text: result.markdown },
    parents,
    metadata,
  }];
}

function validateRequest(request: ClosedTranslationWriterRequest): void {
  if (request.translationExecutionId.trim().length === 0 || request.operationKey.trim().length === 0 || request.pieceId.trim().length === 0 || request.language.trim().length === 0) throw new Error("translation request identity is invalid");
  if (request.language === "en" || !/^sha256:[0-9a-f]{64}$/u.test(`sha256:${request.englishDigest}`)) throw new Error("translation request English digest is invalid");
  if (request.inputArtifactIds.length === 0 || !request.inputArtifactIds.includes(request.promptArtifactId)) throw new Error("translation request does not bind its prompt");
}
