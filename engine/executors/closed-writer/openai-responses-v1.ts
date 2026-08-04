import type { ClosedWriterCredentialResource } from "./credentials.ts";
import { writerOutputSchema } from "./writer-result.ts";
import {
  buildOpenAIResponsesCoreRequest,
  classifyOpenAIResponsesCoreStatus,
  invokeOpenAIResponsesCore,
  parseOpenAIResponsesCoreBytes,
  parseOpenAIResponsesCoreEnvelope,
  OPENAI_RESPONSES_CORE_POLICY,
  OpenAIResponsesCoreError,
  type OpenAIResponsesRequest as CoreOpenAIResponsesRequest,
  type OpenAIResponsesResult as CoreOpenAIResponsesResult,
} from "./openai-responses-core.ts";

export const OPENAI_RESPONSES_V1_POLICY = Object.freeze({
  providerCodec: OPENAI_RESPONSES_CORE_POLICY.providerCodec,
  endpoint: OPENAI_RESPONSES_CORE_POLICY.endpoint,
  model: OPENAI_RESPONSES_CORE_POLICY.model,
  reasoningEffort: OPENAI_RESPONSES_CORE_POLICY.reasoningEffort,
  maxInputBytes: OPENAI_RESPONSES_CORE_POLICY.maxInputBytes,
  maxOutputTokens: OPENAI_RESPONSES_CORE_POLICY.maxOutputTokens,
  maxResponseBytes: OPENAI_RESPONSES_CORE_POLICY.maxResponseBytes,
  timeoutMs: OPENAI_RESPONSES_CORE_POLICY.timeoutMs,
} as const);

/** Backward-compatible writer error name over the shared closed transport. */
export class OpenAIResponsesError extends OpenAIResponsesCoreError {
  constructor(code: string, message: string, retryable = false, options?: ErrorOptions) {
    super(code, message, retryable, options);
    this.name = "OpenAIResponsesError";
  }
}

export type OpenAIResponsesResult = CoreOpenAIResponsesResult;
export type OpenAIResponsesRequest = CoreOpenAIResponsesRequest;

export function buildOpenAIResponsesRequest(prompt: string, apiKey: string): OpenAIResponsesRequest {
  return buildOpenAIResponsesCoreRequest(prompt, apiKey, {
    name: "article_writer_result",
    schema: writerOutputSchema,
  });
}

export async function invokeOpenAIResponsesV1(
  credentials: ClosedWriterCredentialResource,
  prompt: string,
): Promise<OpenAIResponsesResult> {
  try {
    return await invokeOpenAIResponsesCore(credentials, prompt, {
      name: "article_writer_result",
      schema: writerOutputSchema,
    });
  } catch (error) {
    throw asWriterError(error);
  }
}

export function parseOpenAIResponsesBytes(bytes: Uint8Array): OpenAIResponsesResult {
  try {
    return parseOpenAIResponsesCoreBytes(bytes);
  } catch (error) {
    throw asWriterError(error);
  }
}

export function parseOpenAIResponsesEnvelope(value: unknown): OpenAIResponsesResult {
  try {
    return parseOpenAIResponsesCoreEnvelope(value);
  } catch (error) {
    throw asWriterError(error);
  }
}

export function classifyOpenAIResponsesStatus(status: number): OpenAIResponsesError {
  const error = classifyOpenAIResponsesCoreStatus(status);
  return new OpenAIResponsesError(error.code, error.message, error.retryable, { cause: error });
}

function asWriterError(error: unknown): OpenAIResponsesError {
  if (error instanceof OpenAIResponsesError) return error;
  if (error instanceof OpenAIResponsesCoreError) return new OpenAIResponsesError(error.code, error.message, error.retryable, { cause: error });
  return new OpenAIResponsesError("WRITER_REQUEST_FAILED", "closed writer request failed", true, { cause: error });
}
