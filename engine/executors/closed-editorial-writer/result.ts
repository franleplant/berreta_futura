import { z } from "zod";

import type { JsonObject, JsonValue } from "../../contracts/index.ts";

export const EDITORIAL_WRITER_RESULT_CONTRACT_VERSION = "editorial-writer-result/1" as const;

const editorialWriterResultSchema = z.object({
  schemaVersion: z.literal(EDITORIAL_WRITER_RESULT_CONTRACT_VERSION),
  label: z.string().min(1),
  title: z.string().min(1),
  byline: z.string().min(1),
  manuscript: z.string().min(1),
  workingNotes: z.string(),
  dispositions: z.array(z.object({
    findingId: z.string().min(1),
    status: z.enum(["addressed", "declined", "superseded"]),
    explanation: z.string(),
  }).strict()),
}).strict();

export type EditorialWriterResult = z.infer<typeof editorialWriterResultSchema>;

export type EditorialWriterExecutionResult = {
  readonly selected: true;
  readonly value: EditorialWriterResult;
  readonly claim?: {
    readonly claimId: string;
    readonly operationKey: string;
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

export const editorialWriterOutputSchema: JsonObject = {
  type: "object",
  additionalProperties: false,
  required: ["schemaVersion", "label", "title", "byline", "manuscript", "workingNotes", "dispositions"],
  properties: {
    schemaVersion: { type: "string", const: EDITORIAL_WRITER_RESULT_CONTRACT_VERSION },
    label: { type: "string", minLength: 1 },
    title: { type: "string", minLength: 1 },
    byline: { type: "string", minLength: 1 },
    manuscript: { type: "string", minLength: 1 },
    workingNotes: { type: "string" },
    dispositions: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["findingId", "status", "explanation"],
        properties: {
          findingId: { type: "string", minLength: 1 },
          status: { type: "string", enum: ["addressed", "declined", "superseded"] },
          explanation: { type: "string" },
        },
      },
    },
  },
};

export class EditorialWriterResultError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "EditorialWriterResultError";
    this.code = code;
  }
}

export function parseEditorialWriterResult(value: unknown): EditorialWriterResult {
  const parsed = editorialWriterResultSchema.safeParse(value);
  if (!parsed.success) throw new EditorialWriterResultError("EDITORIAL_WRITER_RESULT_INVALID", "editorial writer response does not match its pinned contract");
  return parsed.data;
}

export function asJsonValue(value: EditorialWriterResult): JsonValue {
  return value as unknown as JsonValue;
}
