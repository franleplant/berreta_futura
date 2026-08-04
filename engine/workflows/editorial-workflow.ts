import type { WorkflowContext } from "loops";
import { isDeepStrictEqual } from "node:util";
import { parse as parseYaml } from "yaml";

import { createHash } from "node:crypto";
import type { ArtifactId, JsonObject, RunId } from "../contracts/index.ts";
import type { DurablePromotionRequest } from "../durable/types.ts";
import type { ArticleWorkflowPorts, EditorialReviewFinding, MagazineWorkflowContext } from "./internal-types.ts";
import { parseEditorialWriterResult } from "../executors/closed-editorial-writer/result.ts";
import { parseEditorialReviewResult } from "../executors/closed-editorial-reviewer/result.ts";

export const EDITORIAL_WORKFLOW_NAME = "magazine-opening-editorial" as const;
export const EDITORIAL_WORKFLOW_SCHEMA = "magazine-opening-editorial/1" as const;

export type OpeningEditorialWorkflowArgs = {
  readonly schemaVersion: typeof EDITORIAL_WORKFLOW_SCHEMA;
  readonly editionId: "004";
  readonly runId: RunId;
  readonly editionRunId: RunId;
  readonly editorialExecutionId: string;
  readonly editorialId: "opening";
  readonly seedManuscriptArtifactId: ArtifactId;
  readonly measurementProfileArtifactId: ArtifactId;
  readonly profileArtifactId: ArtifactId;
  readonly entryArtifactId: ArtifactId;
  readonly acceptedEnglishInputsArtifactId: ArtifactId;
  readonly articleArtifactIds: readonly ArtifactId[];
  readonly articleExecutionIds: readonly string[];
  readonly maximumReaderPages: 1;
  readonly maximumRewrites: number;
  readonly reviewPlanArtifactId: ArtifactId;
};

export type OpeningEditorialWorkflowResult = {
  readonly schemaVersion: "magazine-opening-editorial-result/1";
  readonly editionId: "004";
  readonly runId: RunId;
  readonly editionRunId: RunId;
  readonly editorialExecutionId: string;
  readonly editorialId: "opening";
  readonly status: "waiting" | "complete" | "aborted";
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly acceptedEnglishInputsArtifactId: ArtifactId;
  readonly articleArtifactIds: readonly ArtifactId[];
  readonly title: string;
  readonly label: string;
  readonly byline: string;
  readonly measurementArtifactId?: ArtifactId;
  readonly decisionArtifactId?: ArtifactId;
  readonly promotionArtifactId?: ArtifactId;
  readonly durableRevisionId?: string;
};

export type EditorialLoopCheckpoint = {
  readonly schemaVersion: "editorial-loop-checkpoint/1";
  readonly runId: RunId;
  readonly editorialExecutionId: string;
  readonly phase: "review" | "rewriting" | "waiting" | "complete" | "aborted";
  readonly ordinal: number;
  readonly rewriteOrdinal: number;
  readonly maximumRewrites: number;
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly reviewPlanArtifactId: ArtifactId;
  readonly humanRulingArtifactIds: readonly ArtifactId[];
  readonly measurementArtifactId?: ArtifactId;
  readonly reviewArtifactIds?: readonly ArtifactId[];
  readonly offerId?: string;
  readonly taskArtifactId?: ArtifactId;
  readonly decisionArtifactId?: ArtifactId;
  readonly decisionChoice?: "accept" | "revise" | "abort";
  readonly writerOperationKey?: string;
  readonly writerOperationInputDigest?: string;
};

export function parseEditorialLoopCheckpoint(value: unknown): EditorialLoopCheckpoint {
  if (!isObject(value)) throw new Error("editorial loop checkpoint must be an object");
  const allowed = new Set(["schemaVersion", "runId", "editorialExecutionId", "phase", "ordinal", "rewriteOrdinal", "maximumRewrites", "manuscriptArtifactId", "revisionRecordArtifactId", "reviewPlanArtifactId", "humanRulingArtifactIds", "measurementArtifactId", "reviewArtifactIds", "offerId", "taskArtifactId", "decisionArtifactId", "decisionChoice", "writerOperationKey", "writerOperationInputDigest"]);
  if (Object.keys(value).some((key) => !allowed.has(key)) || value.schemaVersion !== "editorial-loop-checkpoint/1" || !text(value.runId) || !text(value.editorialExecutionId) || !new Set(["review", "rewriting", "waiting", "complete", "aborted"]).has(value.phase as string)) throw new Error("editorial loop checkpoint identity is invalid");
  for (const key of ["ordinal", "rewriteOrdinal", "maximumRewrites"] as const) if (!Number.isSafeInteger(value[key]) || (value[key] as number) < 0) throw new Error(`editorial loop checkpoint ${key} is invalid`);
  for (const key of ["manuscriptArtifactId", "revisionRecordArtifactId", "reviewPlanArtifactId"] as const) if (!text(value[key])) throw new Error(`editorial loop checkpoint ${key} is invalid`);
  if (!Array.isArray(value.humanRulingArtifactIds) || value.humanRulingArtifactIds.some((id) => !text(id))) throw new Error("editorial loop checkpoint rulings are invalid");
  for (const key of ["measurementArtifactId", "offerId", "taskArtifactId", "decisionArtifactId", "writerOperationKey", "writerOperationInputDigest"] as const) if (value[key] !== undefined && !text(value[key])) throw new Error(`editorial loop checkpoint ${key} is invalid`);
  for (const key of ["reviewArtifactIds"] as const) if (value[key] !== undefined && (!Array.isArray(value[key]) || value[key].some((id) => !text(id)))) throw new Error("editorial loop checkpoint review artifacts are invalid");
  if (value.decisionChoice !== undefined && !new Set(["accept", "revise", "abort"]).has(value.decisionChoice as string)) throw new Error("editorial loop checkpoint decision is invalid");
  return Object.freeze({ ...value, humanRulingArtifactIds: Object.freeze([...(value.humanRulingArtifactIds as ArtifactId[])]), ...(value.reviewArtifactIds === undefined ? {} : { reviewArtifactIds: Object.freeze([...(value.reviewArtifactIds as ArtifactId[])]) }) }) as EditorialLoopCheckpoint;
}

type EditorialRevisionState = {
  readonly manuscriptArtifactId: ArtifactId;
  readonly revisionRecordArtifactId: ArtifactId;
  readonly title: string;
  readonly label: string;
  readonly byline: string;
  readonly operationInputDigest: string;
};

type EditorialDraft = EditorialRevisionState & {
  readonly manuscript: import("../workflow-authority/artifact-ledger.ts").LedgerArtifact;
  readonly notes: import("../workflow-authority/artifact-ledger.ts").LedgerArtifact;
  readonly dispositions: import("../workflow-authority/artifact-ledger.ts").LedgerArtifact;
};

function validateMeasurementExecution(
  execution: unknown,
  args: OpeningEditorialWorkflowArgs,
  ports: ArticleWorkflowPorts,
  manuscriptArtifactId: ArtifactId,
): { readonly measurement: import("./internal-types.ts").EditorialMeasurement; readonly measurementArtifactId: ArtifactId } {
  if (!isObject(execution) || execution.selected !== true || !Array.isArray(execution.artifacts) || execution.artifacts.length !== 1) throw new Error("opening editorial measureEdition did not select one durable result");
  const artifact = execution.artifacts[0] as import("../workflow-authority/artifact-ledger.ts").LedgerArtifact;
  const expectedMaterialIds = [manuscriptArtifactId, ...args.articleArtifactIds, args.measurementProfileArtifactId];
  if (artifact.kind !== "editorial_measurement" || artifact.schemaVersion !== "editorial-measurement/1" || artifact.mediaType !== "application/json" || artifact.origin !== "subprocess" || artifact.producingRunId !== args.runId || !isDeepStrictEqual(artifact.parents, expectedMaterialIds.map((artifactId) => ({ artifactId, relation: "editorial_measurement_input" })))) throw new Error("opening editorial measureEdition artifact has invalid authority or lineage");
  if (artifact.metadata.measurementExecutionClass !== "authenticated_measure_edition/1" || artifact.metadata.access !== "tool" || !text(artifact.metadata.claimId) || !text(artifact.metadata.attemptId) || !text(artifact.metadata.principalId) || !text(artifact.metadata.operationInputDigest)) throw new Error("opening editorial measurement is not bound to an authenticated tool attempt");
  let payload: unknown;
  try { payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(ports.ledger.readArtifact(artifact.id).bytes)); } catch (error) { throw new Error("opening editorial measurement is invalid JSON", { cause: error }); }
  const measurement = parseEditorialMeasurement(payload);
  const expectedInputs = [manuscriptArtifactId, ...args.articleArtifactIds];
  const chromeFits = measurement.labelVisible && measurement.labelFits && measurement.titleVisible && measurement.titleFits && measurement.bylineVisible && measurement.bylineFits;
  if (measurement.editionId !== args.editionId || measurement.editorialId !== args.editorialId || measurement.manuscriptArtifactId !== manuscriptArtifactId || !sameIds(measurement.contentArtifactIds, expectedInputs) || expectedInputs.some((id) => !measurement.inputArtifactIds.includes(id)) || measurement.fits !== (measurement.pageCount === 1 && chromeFits)) throw new Error("opening editorial measurement does not bind the full exact English issue");
  return { measurement, measurementArtifactId: artifact.id };
}

function parseEditorialMeasurement(value: unknown): import("./internal-types.ts").EditorialMeasurement {
  const allowed = new Set(["schemaVersion", "operation", "editionId", "editorialId", "language", "manuscriptArtifactId", "contentArtifactIds", "inputArtifactIds", "pageCount", "maximumReaderPages", "fits", "labelVisible", "labelFits", "titleVisible", "titleFits", "bylineVisible", "bylineFits", "rendererOutputArtifactIds"]);
  if (!isObject(value) || Object.keys(value).some((key) => !allowed.has(key)) || value.schemaVersion !== "editorial-measurement/1" || value.operation !== "measure_edition" || value.editionId !== "004" || value.editorialId !== "opening" || value.language !== "en" || !text(value.manuscriptArtifactId) || !Array.isArray(value.contentArtifactIds) || value.contentArtifactIds.length !== 8 || value.contentArtifactIds.some((id) => !text(id)) || !Array.isArray(value.inputArtifactIds) || value.inputArtifactIds.length < 8 || value.inputArtifactIds.some((id) => !text(id)) || !Number.isSafeInteger(value.pageCount) || (value.pageCount as number) < 0 || value.maximumReaderPages !== 1) throw new Error("opening editorial measurement does not match its strict contract");
  for (const key of ["fits", "labelVisible", "labelFits", "titleVisible", "titleFits", "bylineVisible", "bylineFits"] as const) if (typeof value[key] !== "boolean") throw new Error(`opening editorial measurement ${key} is invalid`);
  if (value.rendererOutputArtifactIds !== undefined && (!Array.isArray(value.rendererOutputArtifactIds) || value.rendererOutputArtifactIds.some((id) => !text(id)))) throw new Error("opening editorial renderer output IDs are invalid");
  return Object.freeze({ ...value, contentArtifactIds: Object.freeze([...(value.contentArtifactIds as ArtifactId[])]), inputArtifactIds: Object.freeze([...(value.inputArtifactIds as ArtifactId[])]), ...(value.rendererOutputArtifactIds === undefined ? {} : { rendererOutputArtifactIds: Object.freeze([...(value.rendererOutputArtifactIds as ArtifactId[])]) }) }) as import("./internal-types.ts").EditorialMeasurement;
}

function validateReviewExecution(
  execution: unknown,
  args: OpeningEditorialWorkflowArgs,
  ports: ArticleWorkflowPorts,
  manuscriptArtifactId: ArtifactId,
  measurementArtifactId: ArtifactId,
  reviewCycleId: string,
): { readonly findings: readonly EditorialReviewFinding[]; readonly artifacts: readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[] } {
  if (!isObject(execution) || execution.selected !== true || !Array.isArray(execution.artifacts) || execution.artifacts.length !== 1) throw new Error("opening editorial review did not select one durable result");
  const artifact = execution.artifacts[0] as import("../workflow-authority/artifact-ledger.ts").LedgerArtifact;
  const expectedInputs = [manuscriptArtifactId, args.reviewPlanArtifactId, measurementArtifactId];
  if (artifact.kind !== "editorial_review_result" || artifact.schemaVersion !== "editorial-review-result/1" || artifact.mediaType !== "application/json" || artifact.origin !== "model" || artifact.producingRunId !== args.runId || !isDeepStrictEqual(artifact.parents, expectedInputs.map((artifactId) => ({ artifactId, relation: "editorial_review_input" })))) throw new Error("opening editorial review artifact has invalid authority or lineage");
  if (artifact.metadata.reviewerExecutionClass !== "closed_editorial_reviewer/1" || artifact.metadata.access !== "source_blind" || !text(artifact.metadata.claimId) || !text(artifact.metadata.attemptId) || !text(artifact.metadata.principalId) || !text(artifact.metadata.operationInputDigest) || !sameIds(artifact.metadata.reviewerInputArtifactIds, expectedInputs)) throw new Error("opening editorial review is not bound to an authenticated source-blind attempt");
  let payload: unknown;
  try { payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(ports.ledger.readArtifact(artifact.id).bytes)); } catch (error) { throw new Error("opening editorial review is invalid JSON", { cause: error }); }
  const result = parseEditorialReviewResult(payload);
  if (result.editionId !== args.editionId || result.editorialId !== args.editorialId || result.target !== "editorial:opening" || result.manuscriptArtifactId !== manuscriptArtifactId || result.measurementArtifactId !== measurementArtifactId || result.reviewPlanArtifactId !== args.reviewPlanArtifactId || result.reviewCycleId !== reviewCycleId || !Array.isArray(execution.findings) || !isDeepStrictEqual(execution.findings, result.findings)) throw new Error("opening editorial review does not bind the exact editorial-only result");
  return { findings: result.findings, artifacts: Object.freeze([artifact]) };
}

function validateWriterExecution(
  execution: unknown,
  args: OpeningEditorialWorkflowArgs,
  ledger: ArticleWorkflowPorts["ledger"],
  currentManuscriptArtifactId: ArtifactId,
  contextArtifactIds: readonly ArtifactId[],
): EditorialDraft {
  if (!isObject(execution) || execution.selected !== true || !Array.isArray(execution.artifacts)) throw new Error("opening editorial writer did not select a durable result");
  const artifacts = execution.artifacts as readonly import("../workflow-authority/artifact-ledger.ts").LedgerArtifact[];
  if (artifacts.length !== 3) throw new Error("opening editorial writer must produce exactly three artifacts");
  const manuscripts = artifacts.filter((artifact) => artifact.kind === "editorial_manuscript" && artifact.mediaType === "text/markdown");
  const notes = artifacts.filter((artifact) => artifact.kind === "editorial_working_notes");
  const dispositions = artifacts.filter((artifact) => artifact.kind === "editorial_finding_dispositions");
  if (manuscripts.length !== 1 || notes.length !== 1 || dispositions.length !== 1) throw new Error("opening editorial writer must produce one manuscript, notes, and dispositions artifact");
  const manuscript = manuscripts[0]!;
  const metadata = manuscript.metadata;
  const expectedInputs = [args.profileArtifactId, ...args.articleArtifactIds, currentManuscriptArtifactId, ...contextArtifactIds];
  const expectedParents = expectedInputs.map((artifactId) => ({ artifactId, relation: "editorial_writer_input" }));
  const lineage = artifacts.map((artifact) => artifact.metadata);
  if (artifacts.some((artifact) => artifact.producingRunId !== args.runId || !isDeepStrictEqual(artifact.parents, expectedParents))) throw new Error("opening editorial outputs do not name the exact writer inputs");
  if (lineage.some((item) => item.writerExecutionClass !== "closed_editorial_writer/1" || item.editorialExecutionId !== args.editorialExecutionId || item.access !== "source_blind" || typeof item.operationInputDigest !== "string" || item.operationInputDigest.length === 0 || !sameIds(item.writerInputArtifactIds, expectedInputs))) throw new Error("opening editorial outputs do not carry the exact closed-writer contract");
  const operationInputDigest = text(metadata.operationInputDigest);
  if (operationInputDigest === undefined) throw new Error("opening editorial outputs have no operation input digest");
  for (const key of ["operationKey", "operationInputDigest", "claimId", "attemptId", "attemptNumber", "principalId"] as const) {
    if (lineage.some((item) => item[key] !== metadata[key])) throw new Error(`opening editorial outputs disagree on ${key}`);
  }
  if (!text(metadata.claimId) || !text(metadata.attemptId) || !text(metadata.principalId) || !text(metadata.operationKey) || !Number.isSafeInteger(metadata.attemptNumber)) throw new Error("opening editorial outputs are not bound to an authenticated selected attempt");
  if (isObject(execution.claim)) {
    for (const key of ["claimId", "operationKey", "operationInputDigest", "attemptId", "attemptNumber", "principalId", "access"] as const) {
      if (execution.claim[key] !== undefined && execution.claim[key] !== metadata[key]) throw new Error(`opening editorial selected claim disagrees on ${key}`);
    }
  }
  const title = text(metadata.title);
  const label = text(metadata.label);
  const byline = text(metadata.byline);
  if (title === undefined || label === undefined || byline === undefined) throw new Error("opening editorial writer output must include a visible title, label, and byline");
  const markdown = new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(manuscript.id).bytes);
  const frontmatterMatch = /^---\n([\s\S]*?)\n---(?:\n|$)/u.exec(markdown);
  if (frontmatterMatch === null) throw new Error("opening editorial manuscript must start with YAML frontmatter");
  let frontmatter: unknown;
  try { frontmatter = parseYaml(frontmatterMatch[1]!); } catch (error) { throw new Error("opening editorial manuscript frontmatter is invalid YAML", { cause: error }); }
  if (!isObject(frontmatter) || frontmatter.label !== label || frontmatter.title !== title || frontmatter.byline !== byline) throw new Error("opening editorial manuscript frontmatter must exactly match label, title, and byline");
  if (isObject(execution.value)) {
    const selected = parseEditorialWriterResult(execution.value);
    const notesText = new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(notes[0]!.id).bytes);
    let dispositionsValue: unknown;
    try { dispositionsValue = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(ledger.readArtifact(dispositions[0]!.id).bytes)); } catch (error) { throw new Error("opening editorial dispositions are invalid JSON", { cause: error }); }
    if (selected.manuscript !== markdown || selected.workingNotes !== notesText || !isDeepStrictEqual(dispositionsValue, { schemaVersion: "editorial-finding-dispositions/1", dispositions: selected.dispositions }) || selected.label !== label || selected.title !== title || selected.byline !== byline) throw new Error("opening editorial artifacts do not match the selected writer result");
  }
  return { manuscript, notes: notes[0]!, dispositions: dispositions[0]!, manuscriptArtifactId: manuscript.id, revisionRecordArtifactId: "" as ArtifactId, title, label, byline, operationInputDigest };
}

async function persistEditorialRevision(
  args: OpeningEditorialWorkflowArgs,
  context: MagazineWorkflowContext,
  ports: ArticleWorkflowPorts,
  draft: EditorialDraft,
  previousRevisionRecordArtifactId: ArtifactId | undefined,
  humanRulingArtifactIds: readonly ArtifactId[],
  ordinal: number,
): Promise<EditorialRevisionState> {
  const revisionRecordArtifactId = `art-editorial-revision-record-${safe(args.editorialExecutionId)}-${ordinal}-${safe(draft.manuscriptArtifactId)}` as ArtifactId;
  await context.step(`editorial.revision-finalize.${ordinal}`, () => {
    const record = {
      schemaVersion: "editorial-revision-record/1",
      editionId: args.editionId,
      editorialId: args.editorialId,
      editorialExecutionId: args.editorialExecutionId,
      acceptedEnglishInputsArtifactId: args.acceptedEnglishInputsArtifactId,
      articleArtifactIds: args.articleArtifactIds,
      manuscriptArtifactId: draft.manuscriptArtifactId,
      workingNotesArtifactId: draft.notes.id,
      findingDispositionsArtifactId: draft.dispositions.id,
      writerOutputArtifactId: draft.manuscriptArtifactId,
      previousRevisionRecordArtifactId,
      routedFindingArtifactIds: [],
      humanRulingArtifactIds,
      ordinal,
      operationInputDigest: draft.operationInputDigest,
    };
    ports.ledger.createArtifact({
      id: revisionRecordArtifactId,
      kind: "editorial_revision_record",
      schemaVersion: "editorial-revision-record/1",
      mediaType: "application/json",
      origin: "machine",
      payload: { kind: "json", value: record as unknown as JsonObject },
      parents: [
        { artifactId: args.acceptedEnglishInputsArtifactId, relation: "editorial_input_set" },
        { artifactId: draft.manuscriptArtifactId, relation: "editorial_manuscript" },
        { artifactId: draft.notes.id, relation: "editorial_working_notes" },
        { artifactId: draft.dispositions.id, relation: "editorial_finding_dispositions" },
        ...(previousRevisionRecordArtifactId === undefined ? [] : [{ artifactId: previousRevisionRecordArtifactId, relation: "previous_editorial_revision" }]),
        ...args.articleArtifactIds.map((artifactId) => ({ artifactId, relation: "editorial_article_input" })),
      ],
      metadata: { editionId: args.editionId, editorialId: args.editorialId, editorialExecutionId: args.editorialExecutionId, manuscriptArtifactId: draft.manuscriptArtifactId, operationInputDigest: draft.operationInputDigest, ordinal },
      runId: args.runId,
    });
    ports.ledger.recordManuscriptArtifact(args.runId, draft.manuscriptArtifactId);
    return revisionRecordArtifactId;
  }, { input: { editorialExecutionId: args.editorialExecutionId, ordinal, manuscriptArtifactId: draft.manuscriptArtifactId, previousRevisionRecordArtifactId: previousRevisionRecordArtifactId ?? null } });
  return { manuscriptArtifactId: draft.manuscriptArtifactId, revisionRecordArtifactId, title: draft.title, label: draft.label, byline: draft.byline, operationInputDigest: draft.operationInputDigest };
}

async function checkpoint(
  context: MagazineWorkflowContext,
  ports: ArticleWorkflowPorts,
  args: OpeningEditorialWorkflowArgs,
  value: Omit<EditorialLoopCheckpoint, "schemaVersion" | "runId" | "editorialExecutionId">,
): Promise<EditorialLoopCheckpoint> {
  return await context.step(`editorial.checkpoint.${value.phase}.${value.rewriteOrdinal}`, () => {
    const checkpointValue = parseEditorialLoopCheckpoint({ schemaVersion: "editorial-loop-checkpoint/1", runId: args.runId, editorialExecutionId: args.editorialExecutionId, ...value });
    const id = `art-editorial-loop-checkpoint-${safe(args.editorialExecutionId)}-${value.phase}-${value.rewriteOrdinal}` as ArtifactId;
    ports.ledger.createArtifact({ id, kind: "editorial_loop_checkpoint", schemaVersion: "editorial-loop-checkpoint/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: checkpointValue as unknown as JsonObject }, parents: [{ artifactId: value.manuscriptArtifactId, relation: "editorial_checkpoint_manuscript" }, { artifactId: value.revisionRecordArtifactId, relation: "editorial_checkpoint_revision" }, { artifactId: args.reviewPlanArtifactId, relation: "editorial_checkpoint_plan" }, ...value.humanRulingArtifactIds.map((artifactId) => ({ artifactId, relation: "editorial_checkpoint_ruling" }))], metadata: { editionId: args.editionId, editorialId: args.editorialId, phase: value.phase, rewriteOrdinal: value.rewriteOrdinal }, runId: args.runId });
    return checkpointValue;
  }, { input: { phase: value.phase, rewriteOrdinal: value.rewriteOrdinal, manuscriptArtifactId: value.manuscriptArtifactId, revisionRecordArtifactId: value.revisionRecordArtifactId, humanRulingArtifactIds: value.humanRulingArtifactIds as unknown as JsonObject } });
}

function result(args: OpeningEditorialWorkflowArgs, status: OpeningEditorialWorkflowResult["status"], current: EditorialRevisionState, metadata: EditorialRevisionState, measurementArtifactId: ArtifactId, decisionArtifactId: ArtifactId): OpeningEditorialWorkflowResult {
  return { schemaVersion: "magazine-opening-editorial-result/1", editionId: args.editionId, runId: args.runId, editionRunId: args.editionRunId, editorialExecutionId: args.editorialExecutionId, editorialId: args.editorialId, status, manuscriptArtifactId: current.manuscriptArtifactId, revisionRecordArtifactId: current.revisionRecordArtifactId, acceptedEnglishInputsArtifactId: args.acceptedEnglishInputsArtifactId, articleArtifactIds: args.articleArtifactIds, title: metadata.title, label: metadata.label, byline: metadata.byline, measurementArtifactId, decisionArtifactId };
}

function initialMetadata(current: EditorialRevisionState): EditorialRevisionState { return current; }

function readPipelineRef(ledger: ArticleWorkflowPorts["ledger"], accepted: import("../workflow-authority/artifact-ledger.ts").LedgerArtifact): import("../durable/types.ts").InputRevisionRef {
  if (accepted.payloadKind !== "json") throw new Error("accepted English inputs are not JSON");
  const value = JSON.parse(Buffer.from(ledger.readArtifact(accepted.id).bytes).toString("utf8")) as { readonly pipelineRef?: unknown };
  if (!isObject(value.pipelineRef) || !text(value.pipelineRef.revisionId) || !text(value.pipelineRef.logicalId) || value.pipelineRef.kind !== "write_pipeline") throw new Error("accepted English inputs have no exact pipeline reference");
  return value.pipelineRef as import("../durable/types.ts").InputRevisionRef;
}

function buildPromotionRequest(args: OpeningEditorialWorkflowArgs, manuscriptArtifactId: ArtifactId, decisionArtifactId: ArtifactId, inputArtifactIds: readonly ArtifactId[], pipelineRef: import("../durable/types.ts").InputRevisionRef): DurablePromotionRequest {
  return { schemaVersion: "durable-checkpoint-request/1", promotionId: `promotion-editorial-${safe(args.runId)}` as never, revisionId: editorialRevisionId(manuscriptArtifactId), runId: args.runId, logicalItem: { kind: "editorial", editionId: args.editionId, logicalId: args.editorialId, language: "en" }, expectedParentRevisionId: null, acceptedArtifactIds: [manuscriptArtifactId], decisionArtifactIds: [decisionArtifactId], decisionEvidenceArtifactIds: [decisionArtifactId], inputBindings: inputArtifactIds.map((artifactId) => ({ artifactId, revision: pipelineRef })), inputRevisions: [pipelineRef], inputArtifactIds: [...inputArtifactIds] };
}

function editorialRevisionId(manuscriptArtifactId: ArtifactId): import("../contracts/index.ts").RevisionId {
  const digest = createHash("sha256").update(manuscriptArtifactId).digest();
  let bits = 0;
  let value = 0;
  let encoded = "";
  const alphabet = "abcdefghijklmnopqrstuvwxyz234567";
  for (const byte of digest) { value = (value << 8) | byte; bits += 8; while (bits >= 5 && encoded.length < 12) { bits -= 5; encoded += alphabet[(value >>> bits) & 31]; value &= (1 << bits) - 1; } if (encoded.length >= 12) break; }
  return `rev_20260804T000000000Z_${encoded}` as import("../contracts/index.ts").RevisionId;
}

export async function runOpeningEditorialWorkflow(
  args: OpeningEditorialWorkflowArgs,
  context: MagazineWorkflowContext,
  ports: ArticleWorkflowPorts,
): Promise<OpeningEditorialWorkflowResult> {
  const parsed = parseOpeningEditorialArgs(args);
  const entry = ports.ledger.requireArtifact(parsed.entryArtifactId);
  if (entry.kind !== "editorial_workflow_entry" || entry.schemaVersion !== "magazine-opening-editorial/1" || entry.payloadKind !== "json" || entry.producingRunId !== parsed.runId) throw new Error("opening editorial entry is not the exact run-owned artifact");
  let entryValue: unknown;
  try { entryValue = JSON.parse(Buffer.from(ports.ledger.readArtifact(entry.id).bytes).toString("utf8")); } catch (error) { throw new Error("opening editorial entry is not valid JSON", { cause: error }); }
  if (!isDeepStrictEqual(entryValue, parsed)) throw new Error("opening editorial args do not match the immutable entry artifact");
  const writer = ports.runEditorialWriter;
  if (writer === undefined) throw new Error("opening editorial requires a closed editorial writer");
  const initial = await context.step("editorial.writer.initial.dispatch", () => writer({
    editorialExecutionId: parsed.editorialExecutionId,
    operationKey: "editorial.writer.initial",
    currentManuscriptArtifactId: parsed.seedManuscriptArtifactId,
    profileArtifactId: parsed.profileArtifactId,
    articleArtifactIds: parsed.articleArtifactIds,
    mode: "initial",
  }, context), { input: { editorialExecutionId: parsed.editorialExecutionId, operationKey: "editorial.writer.initial", currentManuscriptArtifactId: parsed.seedManuscriptArtifactId, profileArtifactId: parsed.profileArtifactId, articleArtifactIds: parsed.articleArtifactIds as unknown as JsonObject } });
  const initialDraft = validateWriterExecution(initial, parsed, ports.ledger, parsed.seedManuscriptArtifactId, []);
  let current = await persistEditorialRevision(parsed, context, ports, initialDraft, undefined, [], 0);
  let rewriteOrdinal = 0;
  let maximumRewrites = parsed.maximumRewrites;
  let humanRulingArtifactIds: ArtifactId[] = [];
  for (;;) {
    const cycleId = `editorial-cycle-${safe(current.revisionRecordArtifactId)}-${rewriteOrdinal}`;
    const measured = ports.measureEditorial;
    if (measured === undefined) throw new Error("opening editorial requires renderer-backed measurement");
    const measurementExecution = await context.step(`editorial.measure.${safe(cycleId)}`, () => {
      const durableContext = context.durableContext?.();
      return measured({ editionId: parsed.editionId, editorialId: parsed.editorialId, manuscriptArtifactId: current.manuscriptArtifactId, articleArtifactIds: parsed.articleArtifactIds, measurementProfileArtifactId: parsed.measurementProfileArtifactId, maximumReaderPages: 1, ...(durableContext === undefined ? {} : { durableContext }) });
    }, { input: { cycleId, manuscriptArtifactId: current.manuscriptArtifactId, articleArtifactIds: parsed.articleArtifactIds as unknown as JsonObject, measurementProfileArtifactId: parsed.measurementProfileArtifactId } });
    const { measurement, measurementArtifactId } = validateMeasurementExecution(measurementExecution, parsed, ports, current.manuscriptArtifactId);
    await context.step(`editorial.measurement-record.${safe(cycleId)}`, () => {
      ports.ledger.recordMeasurement(parsed.runId, measurementArtifactId);
      return measurementArtifactId;
    }, { input: { cycleId, measurementArtifactId, pageCount: measurement.pageCount, fits: measurement.fits } });
    const reviewRunner = ports.runEditorialReview;
    if (reviewRunner === undefined) throw new Error("opening editorial requires a source-blind review runner");
    const reviewExecution = await context.step(`editorial.review.${safe(cycleId)}`, () => reviewRunner({ editionId: parsed.editionId, editorialId: parsed.editorialId, manuscriptArtifactId: current.manuscriptArtifactId, reviewPlanArtifactId: parsed.reviewPlanArtifactId, measurementArtifactId, reviewCycleId: cycleId }, context), { input: { cycleId, manuscriptArtifactId: current.manuscriptArtifactId, reviewPlanArtifactId: parsed.reviewPlanArtifactId, measurementArtifactId } });
    const review = validateReviewExecution(reviewExecution, parsed, ports, current.manuscriptArtifactId, measurementArtifactId, cycleId);
    const reviewArtifactIds = review.artifacts.map((artifact) => artifact.id);
    const blocking = measurement.pageCount !== 1 || !measurement.fits || !measurement.labelVisible || !measurement.labelFits || !measurement.titleVisible || !measurement.titleFits || !measurement.bylineVisible || !measurement.bylineFits || review.findings.some((finding) => finding.severity === "must_fix");
    await checkpoint(context, ports, parsed, { phase: blocking && rewriteOrdinal < maximumRewrites ? "rewriting" : "review", ordinal: rewriteOrdinal, rewriteOrdinal, maximumRewrites, manuscriptArtifactId: current.manuscriptArtifactId, revisionRecordArtifactId: current.revisionRecordArtifactId, reviewPlanArtifactId: parsed.reviewPlanArtifactId, humanRulingArtifactIds, measurementArtifactId, reviewArtifactIds });
    if (blocking && rewriteOrdinal < maximumRewrites) {
      const contextArtifactIds = await context.step(`editorial.revision-context.${safe(cycleId)}`, () => {
        const id = `art-editorial-revision-context-${safe(cycleId)}` as ArtifactId;
        ports.ledger.createArtifact({ id, kind: "editorial_revision_context", schemaVersion: "editorial-revision-context/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-revision-context/1", cycleId, manuscriptArtifactId: current.manuscriptArtifactId, measurementArtifactId, reviewArtifactIds, findings: review.findings, humanRulingArtifactIds } as unknown as JsonObject }, parents: [{ artifactId: current.manuscriptArtifactId, relation: "previous_manuscript" }, { artifactId: measurementArtifactId, relation: "measurement" }, ...reviewArtifactIds.map((artifactId) => ({ artifactId, relation: "review" })), { artifactId: current.revisionRecordArtifactId, relation: "revision_record" }, ...humanRulingArtifactIds.map((artifactId) => ({ artifactId, relation: "human_ruling" }))], metadata: { cycleId, rewriteOrdinal }, runId: parsed.runId });
        return [id, ...reviewArtifactIds] as readonly ArtifactId[];
      }, { input: { cycleId, manuscriptArtifactId: current.manuscriptArtifactId, measurementArtifactId, reviewArtifactIds: reviewArtifactIds as unknown as JsonObject } });
      rewriteOrdinal += 1;
      const next = await context.step(`editorial.writer.rewrite.dispatch.${rewriteOrdinal}`, () => writer({ editorialExecutionId: parsed.editorialExecutionId, operationKey: `editorial.writer.rewrite.${rewriteOrdinal}`, currentManuscriptArtifactId: current.manuscriptArtifactId, profileArtifactId: parsed.profileArtifactId, articleArtifactIds: parsed.articleArtifactIds, mode: "rewrite", revisionContextArtifactIds: contextArtifactIds }, context), { input: { editorialExecutionId: parsed.editorialExecutionId, operationKey: `editorial.writer.rewrite.${rewriteOrdinal}`, currentManuscriptArtifactId: current.manuscriptArtifactId, profileArtifactId: parsed.profileArtifactId, articleArtifactIds: parsed.articleArtifactIds as unknown as JsonObject, revisionContextArtifactIds: contextArtifactIds as unknown as JsonObject } });
      const nextDraft = validateWriterExecution(next, parsed, ports.ledger, current.manuscriptArtifactId, contextArtifactIds);
      current = await persistEditorialRevision(parsed, context, ports, nextDraft, current.revisionRecordArtifactId, humanRulingArtifactIds, rewriteOrdinal);
      continue;
    }
    const taskArtifactId = `art-editorial-decision-task-${safe(cycleId)}` as ArtifactId;
    const offerId = `offer-editorial-${safe(cycleId)}`;
    const inputArtifactIds = [current.manuscriptArtifactId, measurementArtifactId, ...reviewArtifactIds, parsed.acceptedEnglishInputsArtifactId] as ArtifactId[];
    const allowedChoices = blocking ? ["revise", "abort"] as const : ["accept", "revise", "abort"] as const;
    await context.step(`editorial.offer.${safe(cycleId)}`, () => {
      ports.ledger.createArtifact({ id: taskArtifactId, kind: "editorial_decision_task", schemaVersion: "editorial-decision-task/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-decision-task/1", runId: parsed.runId, editorialExecutionId: parsed.editorialExecutionId, cycleId, manuscriptArtifactId: current.manuscriptArtifactId, measurementArtifactId, reviewArtifactIds, allowedChoices } }, parents: inputArtifactIds.map((artifactId) => ({ artifactId, relation: "editorial_decision_evidence" })), metadata: { cycleId, manuscriptArtifactId: current.manuscriptArtifactId, measurementArtifactId }, runId: parsed.runId });
      ports.ledger.createOffer({ id: offerId, runId: parsed.runId, role: "editorial_decision", taskArtifactId, inputArtifactIds, allowedChoices });
      return taskArtifactId;
    }, { input: { cycleId, taskArtifactId, offerId, inputArtifactIds: inputArtifactIds as unknown as JsonObject } });
    await checkpoint(context, ports, parsed, { phase: "waiting", ordinal: rewriteOrdinal, rewriteOrdinal, maximumRewrites, manuscriptArtifactId: current.manuscriptArtifactId, revisionRecordArtifactId: current.revisionRecordArtifactId, reviewPlanArtifactId: parsed.reviewPlanArtifactId, humanRulingArtifactIds, measurementArtifactId, reviewArtifactIds, offerId, taskArtifactId });
    const answer = await context.wait(`editorial.decision.${safe(cycleId)}`, { request: { offerId, taskArtifactId, inputArtifactIds: inputArtifactIds as unknown as JsonObject, cycleId } });
    const decision = ports.ledger.getEditorialDecision(offerId);
    if (decision === undefined || decision.artifactId !== answer.decisionArtifactId) throw new Error("editorial wait answer does not name the exact persisted decision");
    ports.ledger.markOfferAnswered(offerId);
    humanRulingArtifactIds = [...humanRulingArtifactIds, decision.artifactId];
    if (decision.choice === "abort") {
      await checkpoint(context, ports, parsed, { phase: "aborted", ordinal: rewriteOrdinal, rewriteOrdinal, maximumRewrites, manuscriptArtifactId: current.manuscriptArtifactId, revisionRecordArtifactId: current.revisionRecordArtifactId, reviewPlanArtifactId: parsed.reviewPlanArtifactId, humanRulingArtifactIds, measurementArtifactId, reviewArtifactIds, offerId, taskArtifactId, decisionArtifactId: decision.artifactId, decisionChoice: decision.choice });
      return result(parsed, "aborted", current, initialMetadata(current), measurementArtifactId, decision.artifactId);
    }
    if (decision.choice === "revise") {
      if (rewriteOrdinal >= maximumRewrites) maximumRewrites = rewriteOrdinal + 1;
      const contextId = await context.step(`editorial.human-context.${safe(cycleId)}`, () => {
        const id = `art-editorial-human-context-${safe(cycleId)}` as ArtifactId;
        ports.ledger.createArtifact({ id, kind: "editorial_human_ruling_context", schemaVersion: "editorial-human-ruling-context/1", mediaType: "application/json", origin: "machine", payload: { kind: "json", value: { schemaVersion: "editorial-human-ruling-context/1", decisionArtifactId: decision.artifactId, rationale: decision.rationale, choice: decision.choice } }, parents: [{ artifactId: decision.artifactId, relation: "human_ruling" }, { artifactId: current.revisionRecordArtifactId, relation: "revision_record" }], runId: parsed.runId });
        return id;
      }, { input: { cycleId, decisionArtifactId: decision.artifactId } });
      rewriteOrdinal += 1;
      const next = await context.step(`editorial.writer.rewrite.dispatch.${rewriteOrdinal}`, () => writer({ editorialExecutionId: parsed.editorialExecutionId, operationKey: `editorial.writer.rewrite.${rewriteOrdinal}`, currentManuscriptArtifactId: current.manuscriptArtifactId, profileArtifactId: parsed.profileArtifactId, articleArtifactIds: parsed.articleArtifactIds, mode: "rewrite", revisionContextArtifactIds: [contextId] }, context), { input: { editorialExecutionId: parsed.editorialExecutionId, operationKey: `editorial.writer.rewrite.${rewriteOrdinal}`, currentManuscriptArtifactId: current.manuscriptArtifactId, profileArtifactId: parsed.profileArtifactId, articleArtifactIds: parsed.articleArtifactIds as unknown as JsonObject, revisionContextArtifactIds: [contextId] as unknown as JsonObject } });
      current = await persistEditorialRevision(parsed, context, ports, validateWriterExecution(next, parsed, ports.ledger, current.manuscriptArtifactId, [contextId]), current.revisionRecordArtifactId, humanRulingArtifactIds, rewriteOrdinal);
      continue;
    }
    if (decision.choice !== "accept") throw new Error("editorial decision did not produce a terminal or revision transition");
    if (blocking) throw new Error("a blocking editorial revision cannot be accepted");
    if (ports.promoteEditorial === undefined) throw new Error("opening editorial requires durable promotion");
    const manuscriptArtifact = ports.ledger.requireArtifact(current.manuscriptArtifactId);
    const inputIds = manuscriptArtifact.parents.map((parent) => parent.artifactId);
    const acceptedInput = ports.ledger.requireArtifact(parsed.acceptedEnglishInputsArtifactId);
    const pipelineRef = readPipelineRef(ports.ledger, acceptedInput);
    const promotion = await context.step(`editorial.promote.${safe(cycleId)}`, () => ports.promoteEditorial!({ runId: parsed.runId, request: buildPromotionRequest(parsed, current.manuscriptArtifactId, decision.artifactId, inputIds, pipelineRef), reviewer: decision.principalId, rationale: decision.rationale, decisionArtifactId: decision.artifactId, measurementArtifactId }), { input: { cycleId, manuscriptArtifactId: current.manuscriptArtifactId, decisionArtifactId: decision.artifactId, inputArtifactIds: inputIds as unknown as JsonObject } });
    await checkpoint(context, ports, parsed, { phase: "complete", ordinal: rewriteOrdinal, rewriteOrdinal, maximumRewrites, manuscriptArtifactId: current.manuscriptArtifactId, revisionRecordArtifactId: current.revisionRecordArtifactId, reviewPlanArtifactId: parsed.reviewPlanArtifactId, humanRulingArtifactIds, measurementArtifactId, reviewArtifactIds, offerId, taskArtifactId, decisionArtifactId: decision.artifactId, decisionChoice: decision.choice });
    const output = initialMetadata(current);
    return { ...result(parsed, "complete", current, output, measurementArtifactId, decision.artifactId), promotionArtifactId: promotion.promotionArtifactId, durableRevisionId: promotion.durableRevisionId };
  }
}

export default runOpeningEditorialWorkflow;

export function parseOpeningEditorialArgs(value: unknown): OpeningEditorialWorkflowArgs {
  if (!isObject(value) || value.schemaVersion !== EDITORIAL_WORKFLOW_SCHEMA || value.editionId !== "004" || value.editorialId !== "opening") throw new Error("opening editorial args have an invalid identity");
  for (const key of ["runId", "editionRunId", "editorialExecutionId", "seedManuscriptArtifactId", "measurementProfileArtifactId", "profileArtifactId", "entryArtifactId", "acceptedEnglishInputsArtifactId"] as const) if (!text(value[key])) throw new Error(`opening editorial args missing ${key}`);
  if (!Array.isArray(value.articleArtifactIds) || value.articleArtifactIds.length !== 7 || value.articleArtifactIds.some((id) => !text(id)) || !Array.isArray(value.articleExecutionIds) || value.articleExecutionIds.length !== 7 || value.articleExecutionIds.some((id) => !text(id)) || value.maximumReaderPages !== 1 || !Number.isSafeInteger(value.maximumRewrites) || (value.maximumRewrites as number) < 0 || !text(value.reviewPlanArtifactId)) throw new Error("opening editorial args are not the exact seven-article contract");
  return Object.freeze({
    schemaVersion: EDITORIAL_WORKFLOW_SCHEMA,
    editionId: "004",
    runId: value.runId as RunId,
    editionRunId: value.editionRunId as RunId,
    editorialExecutionId: value.editorialExecutionId as string,
    editorialId: "opening",
    seedManuscriptArtifactId: value.seedManuscriptArtifactId as ArtifactId,
    measurementProfileArtifactId: value.measurementProfileArtifactId as ArtifactId,
    profileArtifactId: value.profileArtifactId as ArtifactId,
    entryArtifactId: value.entryArtifactId as ArtifactId,
    acceptedEnglishInputsArtifactId: value.acceptedEnglishInputsArtifactId as ArtifactId,
    articleArtifactIds: Object.freeze(value.articleArtifactIds as ArtifactId[]),
    articleExecutionIds: Object.freeze(value.articleExecutionIds as string[]),
    maximumReaderPages: 1,
    maximumRewrites: value.maximumRewrites as number,
    reviewPlanArtifactId: value.reviewPlanArtifactId as ArtifactId,
  });
}

function parseOpeningEditorialArgsValue(value: unknown): OpeningEditorialWorkflowArgs { return parseOpeningEditorialArgs(value); }

function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function text(value: unknown): string | undefined { return typeof value === "string" && value.trim().length > 0 ? value : undefined; }
function safe(value: string): string { return value.replace(/[^A-Za-z0-9._-]/gu, "_"); }
function sameIds(value: unknown, expected: readonly string[]): boolean {
  return Array.isArray(value) && value.length === expected.length && value.every((id, index) => id === expected[index]);
}
