import { createHash } from "node:crypto";

import { z } from "zod";

import type { JsonObject, JsonValue } from "../../contracts/index.ts";
import type { ResolvedArticleProductionProfile } from "../../contracts/production-plan.ts";

export const ARTICLE_WRITER_RESULT_CONTRACT_VERSION = "article-writer-result/1" as const;

const findingRefSchema = z.object({
  reviewResultArtifactId: z.string().min(1),
  localId: z.string().min(1),
  contentDigest: z.string().regex(/^[0-9a-f]{64}$/u),
}).strict();

const writerResultSchema = z.object({
  schemaVersion: z.literal(ARTICLE_WRITER_RESULT_CONTRACT_VERSION),
  manuscript: z.string().min(1),
  workingNotes: z.string(),
  dispositions: z.array(z.object({
    finding: findingRefSchema,
    status: z.enum(["addressed", "declined", "superseded"]),
    explanation: z.string(),
  }).strict()),
  reviewMaterials: z.array(z.object({
    materialId: z.string().min(1),
    schemaVersion: z.string().min(1),
    value: z.json(),
  }).strict()),
}).strict();

export type WriterResult = z.infer<typeof writerResultSchema>;

export class ClosedWriterResultError extends Error {
  readonly code: string;
  readonly retryable = false;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ClosedWriterResultError";
    this.code = code;
  }
}

export const writerOutputSchema: JsonObject = {
  type: "object",
  additionalProperties: false,
  required: ["schemaVersion", "manuscript", "workingNotes", "dispositions", "reviewMaterials"],
  properties: {
    schemaVersion: { type: "string", const: ARTICLE_WRITER_RESULT_CONTRACT_VERSION },
    manuscript: { type: "string", minLength: 1 },
    workingNotes: { type: "string" },
    dispositions: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["finding", "status", "explanation"],
        properties: {
          finding: {
            type: "object",
            additionalProperties: false,
            required: ["reviewResultArtifactId", "localId", "contentDigest"],
            properties: {
              reviewResultArtifactId: { type: "string", minLength: 1 },
              localId: { type: "string", minLength: 1 },
              contentDigest: { type: "string", pattern: "^[0-9a-f]{64}$" },
            },
          },
          status: { type: "string", enum: ["addressed", "declined", "superseded"] },
          explanation: { type: "string" },
        },
      },
    },
    reviewMaterials: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["materialId", "schemaVersion", "value"],
        properties: {
          materialId: { type: "string", minLength: 1 },
          schemaVersion: { type: "string", minLength: 1 },
          value: {},
        },
      },
    },
  },
};

export type RevisionFinding = {
  readonly reviewResultArtifactId: string;
  readonly localId: string;
  readonly contentDigest: string;
};

export function parseWriterResult(value: unknown): WriterResult {
  const parsed = writerResultSchema.safeParse(value);
  if (!parsed.success) {
    throw new ClosedWriterResultError("WRITER_RESULT_INVALID", "writer response does not match the pinned result schema");
  }
  return parsed.data;
}

export function validateWriterResult(
  result: WriterResult,
  profile: ResolvedArticleProductionProfile,
  findings: readonly RevisionFinding[],
): void {
  if (profile.writerResultContractVersion !== ARTICLE_WRITER_RESULT_CONTRACT_VERSION) {
    throw new ClosedWriterResultError("WRITER_RESULT_CONTRACT_MISMATCH", "production profile does not pin the writer result contract");
  }
  const expectedFindings = new Map(findings.map((finding) => [findingKey(finding), finding]));
  if (expectedFindings.size !== findings.length) {
    throw new ClosedWriterResultError("WRITER_FINDING_DUPLICATE", "revision brief repeats a finding identity");
  }
  const seenFindings = new Set<string>();
  for (const disposition of result.dispositions) {
    const key = findingKey(disposition.finding);
    const expected = expectedFindings.get(key);
    if (expected === undefined || expected.contentDigest !== disposition.finding.contentDigest) {
      throw new ClosedWriterResultError("WRITER_FINDING_UNKNOWN", "writer disposition does not bind an exact active finding");
    }
    if (seenFindings.has(key)) {
      throw new ClosedWriterResultError("WRITER_FINDING_DUPLICATE", "writer response repeats a finding disposition");
    }
    seenFindings.add(key);
  }
  if (seenFindings.size !== expectedFindings.size) {
    throw new ClosedWriterResultError("WRITER_FINDING_MISSING", "writer response does not disposition every active finding");
  }

  const declarations = new Map(profile.reviewMaterials.map((material) => [material.materialId, material]));
  const seenMaterials = new Set<string>();
  for (const material of result.reviewMaterials) {
    const declaration = declarations.get(material.materialId);
    if (declaration === undefined) {
      throw new ClosedWriterResultError("WRITER_MATERIAL_UNDECLARED", "writer response contains an undeclared review material");
    }
    if (seenMaterials.has(material.materialId)) {
      throw new ClosedWriterResultError("WRITER_MATERIAL_DUPLICATE", "writer response repeats a review material");
    }
    if (declaration.schemaVersion !== material.schemaVersion) {
      throw new ClosedWriterResultError("WRITER_MATERIAL_SCHEMA_MISMATCH", "writer review material does not match its pinned schema version");
    }
    seenMaterials.add(material.materialId);
  }
  for (const declaration of profile.reviewMaterials) {
    if (declaration.required && !seenMaterials.has(declaration.materialId)) {
      throw new ClosedWriterResultError("WRITER_MATERIAL_MISSING", "writer response omitted a required review material");
    }
  }
}

export function digestJson(value: JsonValue | JsonObject): string {
  return createHash("sha256").update(stableJson(value), "utf8").digest("hex");
}

export function stableJson(value: JsonValue | JsonObject): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => stableJson(item)).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson((value as JsonObject)[key]!)}`).join(",")}}`;
}

function findingKey(finding: Pick<RevisionFinding, "reviewResultArtifactId" | "localId">): string {
  return `${finding.reviewResultArtifactId}\u0000${finding.localId}`;
}
