import { isDeepStrictEqual } from "node:util";

import { z } from "zod";

import type { AnswerArtifact, JsonObject, WorkRole } from "../contracts/index.ts";
import { approvedProductionPlanSchema } from "../contracts/index.ts";
import { RunEngineError } from "./types.ts";

type ResultContract = {
  readonly role: WorkRole;
  readonly contractVersion: string;
  readonly schema: z.ZodType;
  readonly validateArtifacts?: ArtifactValidator;
};

type ArtifactValidator = (
  result: JsonObject,
  artifacts: readonly AnswerArtifact[],
) => string | undefined;

type ArtifactRequirement = {
  readonly label: string;
  readonly kinds: readonly string[];
  readonly minimum: number;
  readonly maximum?: number;
};

function requireArtifacts(
  ...requirements: readonly ArtifactRequirement[]
): ArtifactValidator {
  return (_result, artifacts) => {
    for (const requirement of requirements) {
      const count = artifacts.filter((artifact) =>
        requirement.kinds.includes(artifact.kind)
      ).length;
      if (count < requirement.minimum) {
        return `${requirement.label} requires at least ${requirement.minimum}, received ${count}`;
      }
      if (requirement.maximum !== undefined && count > requirement.maximum) {
        return `${requirement.label} permits at most ${requirement.maximum}, received ${count}`;
      }
    }
    return undefined;
  };
}

function exactlyOne(label: string, ...kinds: readonly string[]): ArtifactValidator {
  return requireArtifacts({ label, kinds, minimum: 1, maximum: 1 });
}

function atLeastOne(label: string, ...kinds: readonly string[]): ArtifactValidator {
  return requireArtifacts({ label, kinds, minimum: 1 });
}

function validateEditionPlanArtifacts(
  result: JsonObject,
  artifacts: readonly AnswerArtifact[],
): string | undefined {
  const cardinality = exactlyOne("edition plan", "edition_plan")(result, artifacts);
  if (cardinality !== undefined) {
    return cardinality;
  }
  const plan = artifacts.find((artifact) => artifact.kind === "edition_plan");
  if (
    plan === undefined ||
    plan.mediaType !== "application/json" ||
    plan.payload.kind !== "json"
  ) {
    return "edition plan must be one JSON artifact";
  }
  if (!isDeepStrictEqual(plan.payload.value, result.productionPlan)) {
    return "edition plan artifact payload must equal result.productionPlan";
  }
  return undefined;
}

const validateWriterArtifacts = requireArtifacts(
  {
    label: "article manuscript",
    kinds: ["article_manuscript", "manuscript"],
    minimum: 1,
    maximum: 1,
  },
  {
    label: "writer working notes",
    kinds: ["writer_working_notes", "working_notes"],
    minimum: 1,
    maximum: 1,
  },
);

const validateEditionReviewArtifacts: ArtifactValidator = (result, artifacts) => {
  const reviewError = exactlyOne(
    "edition review",
    "edition_review",
    "edition_review_decision",
  )(result, artifacts);
  if (reviewError !== undefined) {
    return reviewError;
  }
  const routes = Array.isArray(result.routes) ? result.routes : [];
  const findings = new Set(
    artifacts
      .filter((artifact) => artifact.kind === "finding" && artifact.id !== undefined)
      .map((artifact) => artifact.id),
  );
  for (const route of routes) {
    if (
      typeof route !== "object" ||
      route === null ||
      Array.isArray(route) ||
      typeof route.findingArtifactId !== "string" ||
      !findings.has(route.findingArtifactId)
    ) {
      return "every routed findingArtifactId must name a finding artifact in the same answer";
    }
  }
  return undefined;
};

const validateRenderArtifacts: ArtifactValidator = (result, artifacts) => {
  const languages = Array.isArray(result.renderedLanguages) &&
    result.renderedLanguages.every((language) => typeof language === "string")
    ? result.renderedLanguages
    : [];
  if (languages.length === 0 || new Set(languages).size !== languages.length) {
    return "renderedLanguages must be a non-empty unique list";
  }
  for (const kind of [
    "reader_pdf",
    "web_output",
    "booklet_pdf",
    "package_artifact",
    "render_critic_report",
    "printer_preflight",
  ]) {
    const outputs = artifacts.filter((artifact) => artifact.kind === kind);
    if (outputs.length !== languages.length) {
      return `render requires one ${kind} per rendered language, expected ${languages.length}, received ${outputs.length}`;
    }
    const paths = outputs.map((artifact) => artifact.metadata?.relativePath);
    if (
      paths.some((path) => typeof path !== "string") ||
      new Set(paths).size !== paths.length
    ) {
      return `${kind} artifacts require unique relativePath metadata`;
    }
    const outputLanguages = paths.map(
      (path) => (path as string).split("/")[0] ?? "",
    );
    if (
      new Set(outputLanguages).size !== outputLanguages.length ||
      outputLanguages.some((language) => !languages.includes(language))
    ) {
      return `${kind} artifacts must map exactly to renderedLanguages by relativePath`;
    }
  }
  return undefined;
};

const artifactOnlyResult = z.object({
  status: z.enum(["complete", "completed"]).optional(),
}).strict();

const findings = z.array(z.json());
const scores = z.record(z.string(), z.json());

const judgeDecision = z.enum([
  "approve",
  "approved",
  "block",
  "blocking",
  "changes_required",
  "drop",
  "editor_decision",
  "human_decision",
  "not_applicable",
  "ok",
  "pass",
  "reject",
  "revise",
]);

const judgeResult = z.object({
  result: z.enum(["approved", "changes_required"]).optional(),
  decision: judgeDecision.optional(),
  verdict: judgeDecision.optional(),
  status: z.enum([
    "approved",
    "blocking",
    "changes_required",
    "finding",
    "not_applicable",
    "pass",
  ]).optional(),
  approved: z.boolean().optional(),
  blocking: z.boolean().optional(),
  findings: findings.optional(),
  scores: scores.optional(),
  notes: z.string().optional(),
}).strict().refine(
  (value) =>
    value.result !== undefined ||
    value.decision !== undefined ||
    value.verdict !== undefined ||
    value.status !== undefined ||
    value.approved !== undefined ||
    value.blocking !== undefined ||
    value.findings !== undefined,
  { message: "a judge result must include a verdict or findings" },
);

const articleMeasurementResult = z.object({
  fits: z.boolean().optional(),
  openerFits: z.boolean().optional(),
  pageCount: z.number().int().nonnegative().optional(),
  articlePages: z.number().int().nonnegative().optional(),
  status: z.enum(["blocking", "fail", "pass"]).optional(),
}).strict().refine(
  (value) =>
    value.fits !== undefined ||
    value.pageCount !== undefined ||
    value.articlePages !== undefined ||
    value.status !== undefined,
  { message: "an article measurement must include fit, pages, or status" },
);

const articleEditorResult = z.object({
  choice: z.enum(["accept", "approve", "drop", "increase_budget", "revise"]),
  maxIterations: z.number().int().positive().optional(),
  rationale: z.string().optional(),
}).strict();

const sourceReviewResult = z.object({
  decision: z.enum(["approved", "changes_required", "reject", "revise"]),
  findings: findings.optional(),
  notes: z.string().optional(),
}).strict();

const sourceCaptureResult = z.union([
  artifactOnlyResult,
  z.object({
    sourceId: z.string().min(1),
    rawBundleArtifactId: z.string().min(1),
    inputArtifactIds: z.array(z.string().min(1)),
  }).strict(),
]);

const collectionCloseResult = z.object({
  choice: z.enum(["approve", "close", "closed"]),
  rationale: z.string().optional(),
}).strict();

const editionPlanResult = z.object({
  choice: z.enum(["accept", "approve"]),
  productionPlan: approvedProductionPlanSchema,
  rationale: z.string().optional(),
}).strict();

const editionReviewRoute = z.object({
  target: z.string().min(1),
  findingArtifactId: z.string().min(1),
}).strict();

const editionReviewResult = z.object({
  decision: z.enum([
    "approve",
    "approved",
    "changes_required",
    "editor_decision",
    "human_decision",
    "pass",
    "revise",
  ]).optional(),
  choice: z.enum([
    "approve",
    "approved",
    "changes_required",
    "editor_decision",
    "human_decision",
    "pass",
    "revise",
  ]).optional(),
  result: z.enum(["approved", "changes_required"]).optional(),
  routes: z.array(editionReviewRoute).optional(),
  findings: findings.optional(),
  scores: scores.optional(),
  notes: z.string().optional(),
}).strict().refine(
  (value) =>
    value.decision !== undefined ||
    value.choice !== undefined ||
    value.result !== undefined,
  { message: "an edition review must include a decision" },
);

const languageReviewResult = z.object({
  decision: z.enum([
    "approved",
    "changes_required",
    "editor_decision",
    "reject",
    "revise",
  ]),
  findings: findings.optional(),
  scores: scores.optional(),
  notes: z.string().optional(),
}).strict();

const fitResult = z.object({
  fits: z.boolean().optional(),
  decision: z.enum(["editor_decision", "revise"]).optional(),
  pageCount: z.number().int().nonnegative().optional(),
  articlePages: z.number().int().nonnegative().optional(),
}).strict().refine(
  (value) => value.fits !== undefined || value.decision !== undefined,
  { message: "a language fit result must include fits or a decision" },
);

const artSelectionResult = z.discriminatedUnion("choice", [
  z.object({
    choice: z.literal("select"),
    selectedArtifactId: z.string().min(1),
    rationale: z.string().optional(),
  }).strict(),
  z.object({
    choice: z.literal("drop"),
    rationale: z.string().optional(),
  }).strict(),
]);

const editionMeasurementResult = z.object({
  result: z.enum(["fail", "pass"]).optional(),
  fits: z.boolean().optional(),
  pageCount: z.number().int().nonnegative().optional(),
  layouts: z.array(z.json()).optional(),
  measuredLanguages: z.array(z.string().min(1)).optional(),
  inputArtifactIds: z.array(z.string().min(1)).optional(),
}).strict().refine(
  (value) => value.result !== undefined || value.fits !== undefined,
  { message: "an edition measurement must include result or fits" },
);

const renderResult = z.object({
  renderedLanguages: z.array(z.string().min(1)),
  editionId: z.string().min(1).optional(),
  rendererContractVersion: z.string().min(1).optional(),
  schemaVersion: z.number().int().positive().optional(),
  files: z.array(z.json()).optional(),
  layouts: z.array(z.json()).optional(),
  inputArtifactIds: z.array(z.string().min(1)).optional(),
  tailArtFacts: z.record(z.string(), z.json()).optional(),
}).strict();

const renderInspectionResult = z.object({
  result: z.enum(["fail", "pass"]),
  renderArtifactIds: z.array(z.string().min(1)),
  printerPreflightArtifactIds: z.array(z.string().min(1)),
  studioReady: z.boolean(),
  findings: findings.optional(),
  notes: z.string().optional(),
}).strict();

const visualReviewResult = z.object({
  decision: z.enum(["approved", "changes_required", "reject"]),
  renderArtifactIds: z.array(z.string().min(1)),
  findings: findings.optional(),
  notes: z.string().optional(),
}).strict();

const releaseApprovalResult = z.object({
  choice: z.enum(["approve", "reject"]),
  publicationArtifactId: z.string().min(1),
  sourceArtifactIds: z.array(z.string().min(1)),
  rationale: z.string().optional(),
}).strict();

const editorDecisionSchemas = {
  "editor-decision/1": z.object({
    choice: z.enum(["accept", "reject", "revise"]),
    rationale: z.string().optional(),
  }).strict(),
  "translation-editor-decision/1": z.object({
    choice: z.enum(["accept", "reject", "revise"]),
    rationale: z.string().optional(),
  }).strict(),
  "edition-review-editor/1": z.object({
    choice: z.enum(["accept", "approve", "reject", "retry", "revise"]),
    rationale: z.string().optional(),
  }).strict(),
  "edition-editor/1": z.object({
    choice: z.enum(["drop", "resume", "retry"]),
    rationale: z.string().optional(),
  }).strict(),
} as const;

const contracts: readonly ResultContract[] = [
  { role: "capture_source", contractVersion: "capture-source/1", schema: sourceCaptureResult, validateArtifacts: requireArtifacts(
    { label: "raw source bundle", kinds: ["raw_source_bundle"], minimum: 1, maximum: 1 },
    { label: "raw source evidence", kinds: ["raw_evidence"], minimum: 1 },
    { label: "source metadata", kinds: ["source_metadata"], minimum: 1, maximum: 1 },
  ) },
  { role: "extract_source", contractVersion: "extract-source/1", schema: artifactOnlyResult, validateArtifacts: exactlyOne("source extraction", "source_extraction") },
  { role: "review_source", contractVersion: "review-source/1", schema: sourceReviewResult, validateArtifacts: exactlyOne("source review decision", "source_review_decision") },
  { role: "close_collection", contractVersion: "close-collection/1", schema: collectionCloseResult, validateArtifacts: exactlyOne("collection decision", "collection_decision") },
  { role: "plan_edition", contractVersion: "edition-plan/1", schema: editionPlanResult, validateArtifacts: validateEditionPlanArtifacts },
  { role: "writer", contractVersion: "article-writer/1", schema: artifactOnlyResult, validateArtifacts: validateWriterArtifacts },
  { role: "measure_article", contractVersion: "article-measure_article/1", schema: articleMeasurementResult, validateArtifacts: exactlyOne("article measurement", "article_measurement") },
  { role: "worth", contractVersion: "article-worth/1", schema: judgeResult },
  { role: "mechanics", contractVersion: "article-mechanics/1", schema: judgeResult },
  { role: "evidence", contractVersion: "article-evidence/1", schema: judgeResult },
  { role: "shape", contractVersion: "article-shape/1", schema: judgeResult },
  { role: "teaching", contractVersion: "article-teaching/1", schema: judgeResult },
  { role: "craft", contractVersion: "article-craft/1", schema: judgeResult },
  { role: "editor_decision", contractVersion: "article-editor_decision/1", schema: articleEditorResult, validateArtifacts: exactlyOne("article editor decision", "editor_decision") },
  { role: "editorial_writer", contractVersion: "editorial-writer/1", schema: artifactOnlyResult, validateArtifacts: exactlyOne("editorial manuscript", "editorial_manuscript") },
  { role: "editor_decision", contractVersion: "editor-decision/1", schema: editorDecisionSchemas["editor-decision/1"], validateArtifacts: exactlyOne("editor decision", "editor_decision") },
  { role: "edition_review", contractVersion: "edition-review/1", schema: editionReviewResult, validateArtifacts: validateEditionReviewArtifacts },
  { role: "editor_decision", contractVersion: "edition-review-editor/1", schema: editorDecisionSchemas["edition-review-editor/1"], validateArtifacts: exactlyOne("edition review editor decision", "editor_decision") },
  { role: "translation_writer", contractVersion: "translation-writer/1", schema: artifactOnlyResult, validateArtifacts: atLeastOne("translation", "translation", "translation_bundle", "translated_piece") },
  { role: "language_review", contractVersion: "language-review/1", schema: languageReviewResult, validateArtifacts: exactlyOne("language review", "language_review") },
  { role: "language_fit", contractVersion: "language-fit/1", schema: fitResult, validateArtifacts: exactlyOne("language measurement", "language_measurement") },
  { role: "editor_decision", contractVersion: "translation-editor-decision/1", schema: editorDecisionSchemas["translation-editor-decision/1"], validateArtifacts: exactlyOne("translation editor decision", "editor_decision") },
  { role: "cover_image", contractVersion: "cover-image/1", schema: artifactOnlyResult, validateArtifacts: atLeastOne("cover art candidate", "art_candidate", "cover_art_candidate") },
  { role: "interior_image", contractVersion: "interior-image/1", schema: artifactOnlyResult, validateArtifacts: atLeastOne("interior art candidate", "art_candidate", "interior_art_candidate") },
  { role: "select_art", contractVersion: "select-art/1", schema: artSelectionResult, validateArtifacts: exactlyOne("art selection", "art_selection") },
  { role: "measure_edition", contractVersion: "measure-edition/1", schema: editionMeasurementResult, validateArtifacts: exactlyOne("edition measurement", "edition_measurement") },
  { role: "render", contractVersion: "render-edition/1", schema: renderResult, validateArtifacts: validateRenderArtifacts },
  { role: "render", contractVersion: "magazine-renderer/1", schema: renderResult, validateArtifacts: validateRenderArtifacts },
  { role: "render_inspection", contractVersion: "render-inspection/1", schema: renderInspectionResult, validateArtifacts: exactlyOne("render inspection", "render_inspection") },
  { role: "visual_review", contractVersion: "visual-review/1", schema: visualReviewResult, validateArtifacts: exactlyOne("visual review decision", "visual_review_decision") },
  { role: "release_approval", contractVersion: "release-approval/1", schema: releaseApprovalResult, validateArtifacts: exactlyOne("release decision", "release_decision") },
  { role: "editor_decision", contractVersion: "edition-editor/1", schema: editorDecisionSchemas["edition-editor/1"], validateArtifacts: exactlyOne("edition editor decision", "editor_decision") },
];

function requireWorkResultContract(
  role: WorkRole,
  contractVersion: string,
): ResultContract {
  const contract = contracts.find(
    (candidate) =>
      candidate.role === role && candidate.contractVersion === contractVersion,
  );
  if (contract === undefined) {
    throw new RunEngineError(
      "ANSWER_RESULT_CONTRACT_UNKNOWN",
      `No result contract is registered for ${role} at ${contractVersion}`,
    );
  }
  return contract;
}

export function assertWorkResultContractRegistered(
  role: WorkRole,
  contractVersion: string,
): void {
  requireWorkResultContract(role, contractVersion);
}

export function validateWorkResult(
  role: WorkRole,
  contractVersion: string,
  result: JsonObject,
  artifacts: readonly AnswerArtifact[],
): void {
  const contract = requireWorkResultContract(role, contractVersion);
  const parsed = contract.schema.safeParse(result);
  if (!parsed.success) {
    throw new RunEngineError(
      "ANSWER_RESULT_INVALID",
      `Answer result violates ${role} at ${contractVersion}: ${z.prettifyError(parsed.error)}`,
    );
  }
  const artifactError = contract.validateArtifacts?.(result, artifacts);
  if (artifactError !== undefined) {
    throw new RunEngineError(
      "ANSWER_ARTIFACTS_INVALID",
      `Answer artifacts violate ${role} at ${contractVersion}: ${artifactError}`,
    );
  }
}
