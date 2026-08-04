import { Agent as HttpsAgent, request as nodeHttpsRequest, type RequestOptions } from "node:https";

import type { JsonObject, JsonValue } from "../../contracts/index.ts";

const OFFICIAL_HOSTNAME = "api.openai.com";
const OFFICIAL_PATH = "/v1/responses";

/** The fixed transport policy shared by every closed OpenAI executor. */
export const OPENAI_RESPONSES_CORE_POLICY = Object.freeze({
  providerCodec: "openai-responses-v1",
  endpoint: `https://${OFFICIAL_HOSTNAME}${OFFICIAL_PATH}`,
  model: "gpt-5.6-terra",
  reasoningEffort: "high",
  maxInputBytes: 512 * 1024,
  maxOutputTokens: 32_768,
  maxResponseBytes: 2 * 1024 * 1024,
  timeoutMs: 30 * 60_000,
} as const);

const httpsRequest = nodeHttpsRequest;
const httpsAgent = new HttpsAgent({
  keepAlive: false,
  rejectUnauthorized: true,
  minVersion: "TLSv1.2",
});

export type OpenAIResponsesCredentialResource = {
  readonly schemaVersion: "closed-writer-credential-resource/1";
  readonly read: () => Promise<Readonly<Record<string, string>>> | Readonly<Record<string, string>>;
};

export type OpenAIResponsesResult = {
  readonly responseId: string;
  readonly output: JsonValue;
  readonly usage?: JsonObject;
};

export type OpenAIResponsesRequest = {
  readonly options: RequestOptions;
  readonly body: string;
};

export type OpenAIResponsesSchema = {
  readonly name: string;
  readonly schema: JsonObject;
};

export class OpenAIResponsesCoreError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, retryable = false, options?: ErrorOptions) {
    super(message, options);
    this.name = "OpenAIResponsesCoreError";
    this.code = code;
    this.retryable = retryable;
  }
}

/**
 * Build the one-shot request. The destination, TLS settings, model, and
 * request shape are intentionally not caller-configurable.
 */
export function buildOpenAIResponsesCoreRequest(
  prompt: string,
  apiKey: string,
  output: OpenAIResponsesSchema,
): OpenAIResponsesRequest {
  const body = JSON.stringify({
    model: OPENAI_RESPONSES_CORE_POLICY.model,
    reasoning: { effort: OPENAI_RESPONSES_CORE_POLICY.reasoningEffort },
    store: false,
    max_output_tokens: OPENAI_RESPONSES_CORE_POLICY.maxOutputTokens,
    input: [{ role: "user", content: [{ type: "input_text", text: prompt }] }],
    text: {
      format: {
        type: "json_schema",
        name: output.name,
        strict: true,
        schema: output.schema,
      },
    },
  });
  return {
    options: {
      protocol: "https:",
      hostname: OFFICIAL_HOSTNAME,
      port: 443,
      path: OFFICIAL_PATH,
      method: "POST",
      rejectUnauthorized: true,
      servername: OFFICIAL_HOSTNAME,
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
        "content-length": Buffer.byteLength(body),
      },
    },
    body,
  };
}

/** Execute a closed request through the fixed node:https transport. */
export async function invokeOpenAIResponsesCore(
  credentials: OpenAIResponsesCredentialResource,
  prompt: string,
  output: OpenAIResponsesSchema,
): Promise<OpenAIResponsesResult> {
  const environment = await readCredentialEnvironment(credentials);
  const apiKey = environment.OPENAI_API_KEY;
  const request = buildOpenAIResponsesCoreRequest(prompt, apiKey, output);
  const bytes = await postOnce(request);
  return parseOpenAIResponsesCoreBytes(bytes);
}

export function parseOpenAIResponsesCoreBytes(bytes: Uint8Array): OpenAIResponsesResult {
  if (bytes.byteLength > OPENAI_RESPONSES_CORE_POLICY.maxResponseBytes) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_TOO_LARGE", "closed response exceeds its pinned byte ceiling");
  }
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response is not valid UTF-8");
  }
  let envelope: unknown;
  try {
    envelope = JSON.parse(text);
  } catch {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response is not JSON");
  }
  return parseOpenAIResponsesCoreEnvelope(envelope);
}

export function parseOpenAIResponsesCoreEnvelope(value: unknown): OpenAIResponsesResult {
  const envelope = object(value, "response");
  exactAllowedKeys(envelope, [
    "id", "object", "created_at", "status", "background", "billing", "completed_at", "conversation",
    "error", "incomplete_details", "instructions", "max_output_tokens", "max_tool_calls", "model", "output",
    "parallel_tool_calls", "previous_response_id", "prompt", "prompt_cache_key", "prompt_cache_retention",
    "reasoning", "safety_identifier", "service_tier", "store", "temperature", "text", "tool_choice", "tools",
    "top_logprobs", "top_p", "truncation", "usage", "user", "metadata", "output_text",
  ], "response");
  if (typeof envelope.id !== "string" || envelope.id.length === 0 || envelope.object !== "response" || envelope.status !== "completed") {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response is not a completed Responses envelope");
  }
  if (envelope.error !== undefined && envelope.error !== null || envelope.incomplete_details !== undefined && envelope.incomplete_details !== null) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response reports an incomplete or failed request");
  }
  if (!Array.isArray(envelope.output)) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response output is invalid");
  }
  const messages: Record<string, unknown>[] = [];
  for (const item of envelope.output) {
    const outputItem = object(item, "output item");
    if (outputItem.type === "reasoning") {
      validateReasoningItem(outputItem);
    } else if (outputItem.type === "message") {
      messages.push(outputItem);
    } else {
      throw new OpenAIResponsesCoreError("WRITER_TOOL_ACTIVITY", "closed response contains a tool or unknown output item");
    }
  }
  if (messages.length !== 1) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response must contain exactly one output message");
  }
  const message = messages[0]!;
  exactAllowedKeys(message, ["id", "type", "status", "role", "content", "phase"], "output message");
  if (message.role !== "assistant" || message.status !== "completed" || !Array.isArray(message.content) || message.content.length !== 1) {
    throw new OpenAIResponsesCoreError("WRITER_TOOL_ACTIVITY", "closed response contains a non-assistant or incomplete output message");
  }
  const content = object(message.content[0], "message content");
  exactAllowedKeys(content, ["type", "text", "annotations", "logprobs"], "message content");
  if (content.type !== "output_text" || typeof content.text !== "string") {
    throw new OpenAIResponsesCoreError("WRITER_TOOL_ACTIVITY", "closed response contains non-text output");
  }
  let output: unknown;
  try {
    output = JSON.parse(content.text);
  } catch {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response output text is not JSON");
  }
  if (!isJsonValue(output)) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response output is not JSON data");
  }
  const usage = envelope.usage;
  if (usage !== undefined && (typeof usage !== "object" || usage === null || Array.isArray(usage) || !isJsonValue(usage))) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response usage is invalid");
  }
  return { responseId: envelope.id, output, ...(usage === undefined ? {} : { usage: usage as JsonObject }) };
}

async function readCredentialEnvironment(credentials: OpenAIResponsesCredentialResource): Promise<{ readonly OPENAI_API_KEY: string }> {
  if (credentials.schemaVersion !== "closed-writer-credential-resource/1") {
    throw new OpenAIResponsesCoreError("WRITER_CREDENTIAL_INVALID", "closed response credentials are unavailable or invalid");
  }
  let environment: Readonly<Record<string, string>>;
  try {
    environment = await credentials.read();
  } catch (error) {
    throw new OpenAIResponsesCoreError("WRITER_CREDENTIAL_INVALID", "closed response credentials are unavailable or invalid", false, { cause: error });
  }
  if (environment === null || typeof environment !== "object" || Array.isArray(environment)) {
    throw new OpenAIResponsesCoreError("WRITER_CREDENTIAL_INVALID", "closed response credentials are unavailable or invalid");
  }
  const keys = Object.keys(environment);
  const value = environment.OPENAI_API_KEY;
  if (keys.length !== 1 || keys[0] !== "OPENAI_API_KEY" || typeof value !== "string" || value.trim().length === 0 || /[\r\n]/u.test(value)) {
    throw new OpenAIResponsesCoreError("WRITER_CREDENTIAL_INVALID", "closed response credentials are unavailable or invalid");
  }
  return { OPENAI_API_KEY: value };
}

function postOnce(request: OpenAIResponsesRequest): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (error?: Error, bytes?: Buffer): void => {
      if (settled) return;
      settled = true;
      if (error !== undefined) reject(error);
      else resolve(bytes ?? Buffer.alloc(0));
    };
    const outgoing = httpsRequest({ ...request.options, agent: httpsAgent }, (response) => {
      const status = response.statusCode ?? 0;
      if (status < 200 || status >= 300) {
        response.destroy();
        finish(classifyOpenAIResponsesCoreStatus(status));
        return;
      }
      const declaredLength = parseContentLength(response.headers["content-length"]);
      if (declaredLength !== undefined && declaredLength > OPENAI_RESPONSES_CORE_POLICY.maxResponseBytes) {
        response.destroy();
        finish(new OpenAIResponsesCoreError("WRITER_RESPONSE_TOO_LARGE", "closed response exceeds its pinned byte ceiling"));
        return;
      }
      const chunks: Buffer[] = [];
      let size = 0;
      response.on("data", (chunk: Buffer | Uint8Array | string) => {
        if (settled) return;
        const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        size += bytes.byteLength;
        if (size > OPENAI_RESPONSES_CORE_POLICY.maxResponseBytes) {
          response.destroy();
          finish(new OpenAIResponsesCoreError("WRITER_RESPONSE_TOO_LARGE", "closed response exceeds its pinned byte ceiling"));
          return;
        }
        chunks.push(bytes);
      });
      response.once("end", () => finish(undefined, Buffer.concat(chunks, size)));
      response.once("error", (error) => finish(transportError(error)));
      response.once("aborted", () => finish(new OpenAIResponsesCoreError("WRITER_REQUEST_FAILED", "closed response was interrupted", true)));
    });
    outgoing.setTimeout(OPENAI_RESPONSES_CORE_POLICY.timeoutMs, () => {
      const error = new OpenAIResponsesCoreError("WRITER_REQUEST_TIMEOUT", "closed request timed out", true);
      outgoing.destroy(error);
      finish(error);
    });
    outgoing.once("error", (error) => finish(error instanceof OpenAIResponsesCoreError ? error : transportError(error)));
    outgoing.end(request.body);
  });
}

export function classifyOpenAIResponsesCoreStatus(status: number): OpenAIResponsesCoreError {
  if (status >= 300 && status < 400) {
    return new OpenAIResponsesCoreError("WRITER_REDIRECT_REJECTED", `closed request returned HTTP ${status}`);
  }
  return new OpenAIResponsesCoreError(
    "WRITER_REQUEST_FAILED",
    `closed request returned HTTP ${status}`,
    status === 408 || status === 409 || status === 429 || status >= 500,
  );
}

function validateReasoningItem(item: Record<string, unknown>): void {
  exactAllowedKeys(item, ["id", "type", "summary", "status", "encrypted_content"], "reasoning output");
  if (typeof item.id !== "string" || item.id.length === 0 || !Array.isArray(item.summary) ||
      item.status !== undefined && item.status !== "completed" ||
      item.encrypted_content !== undefined && typeof item.encrypted_content !== "string") {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response reasoning output is invalid");
  }
  for (const candidate of item.summary) {
    const summary = object(candidate, "reasoning summary");
    exactAllowedKeys(summary, ["type", "text"], "reasoning summary");
    if (summary.type !== "summary_text" || typeof summary.text !== "string") {
      throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", "closed response reasoning summary is invalid");
    }
  }
}

function parseContentLength(value: string | string[] | undefined): number | undefined {
  if (typeof value !== "string" || !/^\d+$/u.test(value)) return undefined;
  const length = Number(value);
  return Number.isSafeInteger(length) ? length : undefined;
}

function transportError(error: unknown): OpenAIResponsesCoreError {
  const cause = error instanceof Error ? new Error("network request failed", { cause: error }) : undefined;
  return new OpenAIResponsesCoreError("WRITER_REQUEST_FAILED", "closed request failed", true, { cause });
}

function object(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", `closed ${label} is invalid`);
  }
  return value as Record<string, unknown>;
}

function exactAllowedKeys(value: Record<string, unknown>, allowed: readonly string[], label: string): void {
  const set = new Set(allowed);
  if (Object.keys(value).some((key) => !set.has(key))) {
    throw new OpenAIResponsesCoreError("WRITER_RESPONSE_INVALID", `closed ${label} contains an unknown field`);
  }
}

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(isJsonValue);
  return typeof value === "object" && Object.values(value as Record<string, unknown>).every(isJsonValue);
}
