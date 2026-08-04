import { z } from "zod";

import type { ArtifactId, JsonObject, JsonValue } from "../../contracts/index.ts";
import type { EditorialReviewResult } from "../../workflows/internal-types.ts";

export const EDITORIAL_REVIEW_MODEL_OUTPUT_VERSION = "editorial-review-model-output/1" as const;

const findingSchema = z.object({
  findingId: z.string().min(1).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/u),
  target: z.literal("editorial:opening"),
  severity: z.enum(["must_fix", "should_fix"]),
  problem: z.string().min(1),
  requestedOutcome: z.string().min(1),
}).strict();

const outputSchema = z.object({
  schemaVersion: z.literal(EDITORIAL_REVIEW_MODEL_OUTPUT_VERSION),
  assessment: z.enum(["pass", "findings", "human_required"]),
  findings: z.array(findingSchema),
}).strict();

const resultSchema = z.object({
  schemaVersion: z.literal("editorial-review-result/1"),
  editionId: z.literal("004"),
  editorialId: z.literal("opening"),
  target: z.literal("editorial:opening"),
  manuscriptArtifactId: z.string().min(1),
  measurementArtifactId: z.string().min(1),
  reviewPlanArtifactId: z.string().min(1),
  reviewCycleId: z.string().min(1),
  assessment: z.enum(["pass", "findings", "human_required"]),
  findings: z.array(findingSchema),
}).strict();

export type EditorialReviewModelOutput = z.infer<typeof outputSchema>;

export const editorialReviewOutputSchema: JsonObject = {
  type: "object",
  additionalProperties: false,
  required: ["schemaVersion", "assessment", "findings"],
  properties: {
    schemaVersion: { type: "string", const: EDITORIAL_REVIEW_MODEL_OUTPUT_VERSION },
    assessment: { type: "string", enum: ["pass", "findings", "human_required"] },
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["findingId", "target", "severity", "problem", "requestedOutcome"],
        properties: {
          findingId: { type: "string", minLength: 1, pattern: "^[A-Za-z0-9][A-Za-z0-9._-]*$" },
          target: { type: "string", const: "editorial:opening" },
          severity: { type: "string", enum: ["must_fix", "should_fix"] },
          problem: { type: "string", minLength: 1 },
          requestedOutcome: { type: "string", minLength: 1 },
        },
      },
    },
  },
};

export function parseEditorialReviewModelOutput(value: unknown): EditorialReviewModelOutput {
  const parsed = outputSchema.safeParse(value);
  if (!parsed.success) throw new Error("editorial reviewer response does not match its pinned contract");
  const ids = parsed.data.findings.map((finding) => finding.findingId);
  if (new Set(ids).size !== ids.length) throw new Error("editorial reviewer repeated a finding identity");
  if (parsed.data.assessment === "pass" && parsed.data.findings.length !== 0) throw new Error("passing editorial review cannot contain findings");
  if (parsed.data.assessment === "findings" && parsed.data.findings.length === 0) throw new Error("editorial findings assessment must contain a finding");
  return parsed.data;
}

export function bindEditorialReviewResult(input: {
  readonly output: EditorialReviewModelOutput;
  readonly manuscriptArtifactId: ArtifactId;
  readonly measurementArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly reviewCycleId: string;
}): EditorialReviewResult {
  return Object.freeze({
    schemaVersion: "editorial-review-result/1",
    editionId: "004",
    editorialId: "opening",
    target: "editorial:opening",
    manuscriptArtifactId: input.manuscriptArtifactId,
    measurementArtifactId: input.measurementArtifactId,
    reviewPlanArtifactId: input.reviewPlanArtifactId,
    reviewCycleId: input.reviewCycleId,
    assessment: input.output.assessment,
    findings: Object.freeze(input.output.findings.map((finding) => Object.freeze({ ...finding }))),
  });
}

export function parseEditorialReviewResult(value: unknown): EditorialReviewResult {
  const parsed = resultSchema.safeParse(value);
  if (!parsed.success) throw new Error("editorial review artifact does not match its pinned contract");
  const ids = parsed.data.findings.map((finding) => finding.findingId);
  if (new Set(ids).size !== ids.length || (parsed.data.assessment === "pass" && parsed.data.findings.length !== 0) || (parsed.data.assessment === "findings" && parsed.data.findings.length === 0)) throw new Error("editorial review artifact has inconsistent findings");
  return parsed.data as unknown as EditorialReviewResult;
}

export function editorialReviewResultJson(value: EditorialReviewResult): JsonValue {
  return value as unknown as JsonValue;
}
