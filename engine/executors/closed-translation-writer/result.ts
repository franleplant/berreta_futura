import { z } from "zod";

import type { JsonObject, JsonValue } from "../../contracts/index.ts";

export const TRANSLATION_WRITER_RESULT_CONTRACT_VERSION = "translation-writer-result/1" as const;

const translationWriterResultSchema = z.object({
  schemaVersion: z.literal(TRANSLATION_WRITER_RESULT_CONTRACT_VERSION),
  englishSha256: z.string().regex(/^sha256:[0-9a-f]{64}$/u),
  markdown: z.string().min(1),
}).strict();

export type TranslationWriterResult = z.infer<typeof translationWriterResultSchema>;

export type TranslationWriterExecutionResult = {
  readonly selected: true;
  readonly value: TranslationWriterResult;
  readonly adopted?: false;
  readonly claim?: {
    readonly claimId: string;
    readonly operationKey: string;
    readonly operationInputDigest?: string;
  };
  readonly artifacts: readonly import("../../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
} | {
  readonly selected: true;
  readonly adopted: true;
  readonly artifacts: readonly import("../../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
} | {
  readonly selected: false;
  readonly reason: "already_selected" | "stale";
  readonly artifacts: readonly import("../../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
};

export const translationWriterOutputSchema: JsonObject = {
  type: "object",
  additionalProperties: false,
  required: ["schemaVersion", "englishSha256", "markdown"],
  properties: {
    schemaVersion: { type: "string", const: TRANSLATION_WRITER_RESULT_CONTRACT_VERSION },
    englishSha256: { type: "string", pattern: "^sha256:[0-9a-f]{64}$" },
    markdown: { type: "string", minLength: 1 },
  },
};

export class TranslationWriterResultError extends Error {
  readonly code = "TRANSLATION_WRITER_RESULT_INVALID";

  constructor(message: string) {
    super(message);
    this.name = "TranslationWriterResultError";
  }
}

export function parseTranslationWriterResult(value: unknown): TranslationWriterResult {
  const parsed = translationWriterResultSchema.safeParse(value);
  if (!parsed.success) throw new TranslationWriterResultError("translation writer response does not match its pinned contract");
  return parsed.data;
}

export function asJsonValue(value: TranslationWriterResult): JsonValue {
  return value as unknown as JsonValue;
}
