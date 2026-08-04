import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";

import type { AuthorizedWorker } from "../../authority/local-authority.ts";
import {
  assertArticleExecutionMaterials,
  selectArticleWriterMaterials,
  type ArticleMaterialContext,
  type ArticleMaterialSelectionContext,
  type ArticleMaterialSet,
} from "../../article-production/materials.ts";
import type {
  ArticleExecutionId,
  ArtifactId,
  JsonObject,
  JsonValue,
} from "../../contracts/index.ts";
import type {
  ResolvedArticleProductionProfile,
  ResolvedReviewPlan,
} from "../../contracts/production-plan.ts";
import {
  articleRevisionContextParents,
  parseArticleRevisionContext,
  type ArticleRevisionContext,
} from "../../article-production/revision.ts";
import { articleReviewRouteSchema, type ArticleReviewRoute } from "../../article-production/review-cycle.ts";
import type { LoopsArticleEntryInput } from "../../durable/write-pipeline.ts";
import type { InputRevisionRef } from "../../durable/types.ts";
import type { ArticleAttemptExecutionResult, ArticleAttemptRunner } from "../../article-production/attempts.ts";
import { ArtifactLedger, type LedgerArtifact } from "../../workflow-authority/artifact-ledger.ts";
import type { ClosedWriterCredentialResource } from "./credentials.ts";
import { OPENAI_RESPONSES_V1_POLICY, invokeOpenAIResponsesV1 } from "./openai-responses-v1.ts";
import {
  digestJson,
  parseWriterResult,
  stableJson,
  validateWriterResult,
  writerOutputSchema,
  type RevisionFinding,
  type WriterResult,
} from "./writer-result.ts";

export const CLOSED_WRITER_EXECUTION_CLASS = "closed_writer/1" as const;
const PROFILE_ENVELOPE_VERSION = "resolved-article-production-profile/1" as const;
const REVISION_BRIEF_VERSION = "article-revision-brief/1" as const;
const FIXED_RETRY = Object.freeze({ maxAttempts: 2, retryOn: "retryable" as const });

const REQUEST_POLICY: JsonObject = {
  schemaVersion: "openai-responses-request-policy/1",
  requestCount: 1,
  store: false,
  tools: "omitted",
  sessions: "omitted",
  repairRequests: 0,
  retry: FIXED_RETRY,
};

export type ClosedWriterRuntimeIdentity = {
  readonly schemaVersion: "closed-writer-runtime/1";
  readonly executionClass: typeof CLOSED_WRITER_EXECUTION_CLASS;
  readonly providerCodec: typeof OPENAI_RESPONSES_V1_POLICY.providerCodec;
  readonly officialEndpointIdentity: typeof OPENAI_RESPONSES_V1_POLICY.endpoint;
  readonly model: typeof OPENAI_RESPONSES_V1_POLICY.model;
  readonly reasoningEffort: typeof OPENAI_RESPONSES_V1_POLICY.reasoningEffort;
  readonly outputSchemaDigest: string;
  readonly requestPolicyDigest: string;
  readonly maxInputBytes: number;
  readonly maxOutputTokens: number;
  readonly maxResponseBytes: number;
  readonly timeoutMs: number;
};

export const CLOSED_WRITER_RUNTIME_IDENTITY: ClosedWriterRuntimeIdentity = Object.freeze({
  schemaVersion: "closed-writer-runtime/1",
  executionClass: CLOSED_WRITER_EXECUTION_CLASS,
  providerCodec: OPENAI_RESPONSES_V1_POLICY.providerCodec,
  officialEndpointIdentity: OPENAI_RESPONSES_V1_POLICY.endpoint,
  model: OPENAI_RESPONSES_V1_POLICY.model,
  reasoningEffort: OPENAI_RESPONSES_V1_POLICY.reasoningEffort,
  outputSchemaDigest: `sha256:${digestJson(writerOutputSchema)}`,
  requestPolicyDigest: `sha256:${digestJson(REQUEST_POLICY)}`,
  maxInputBytes: OPENAI_RESPONSES_V1_POLICY.maxInputBytes,
  maxOutputTokens: OPENAI_RESPONSES_V1_POLICY.maxOutputTokens,
  maxResponseBytes: OPENAI_RESPONSES_V1_POLICY.maxResponseBytes,
  timeoutMs: OPENAI_RESPONSES_V1_POLICY.timeoutMs,
});

export type ClosedWriterProfileEnvelope = {
  readonly schemaVersion: typeof PROFILE_ENVELOPE_VERSION;
  readonly entry: LoopsArticleEntryInput;
  readonly articleBriefArtifactId?: ArtifactId;
  readonly editionContextArtifactId?: ArtifactId;
  readonly sourceApprovalArtifactIds?: readonly ArtifactId[];
  readonly writerReviewMaterialArtifacts?: Readonly<Record<string, ArtifactId>>;
};

type ClosedWriterExecutionRequestBase = {
  readonly worker: AuthorizedWorker;
  readonly articleExecutionId: ArticleExecutionId;
  readonly operationKey: string;
  readonly currentManuscriptArtifactId: ArtifactId;
  readonly productionProfileArtifactId: ArtifactId;
};

export type ClosedWriterExecutionRequest = ClosedWriterExecutionRequestBase & ({
  /** Initial writer calls have no prior revision package. */
  readonly mode?: "initial";
  readonly revisionContextArtifactId?: never;
} | {
  /** Rewrites must name the exact immutable ID-only revision context. */
  readonly mode: "rewrite";
  /** ID-only package containing the exact current brief, route, and carry set. */
  readonly revisionContextArtifactId: ArtifactId;
});

export type ClosedWriterStep = <T>(
  key: string,
  operation: () => Promise<T> | T,
  options: { readonly input: JsonObject; readonly retry: typeof FIXED_RETRY },
) => Promise<T>;

export type ClosedWriterExecutor = {
  readonly runtimeIdentity: ClosedWriterRuntimeIdentity;
  executeInStep(
    step: ClosedWriterStep,
    request: ClosedWriterExecutionRequest,
  ): Promise<ArticleAttemptExecutionResult<WriterResult>>;
};

export type CreateClosedWriterExecutorConfig = {
  readonly ledger: ArtifactLedger;
  readonly credentials: ClosedWriterCredentialResource;
};

export class ClosedWriterError extends Error {
  readonly code: string;
  readonly retryable = false;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "ClosedWriterError";
    this.code = code;
  }
}

/** The only production construction seam. Transport and all policy choices are fixed. */
export function createClosedWriterExecutor(config: CreateClosedWriterExecutorConfig): ClosedWriterExecutor {
  if (!(config.ledger instanceof ArtifactLedger) || config.credentials.read === undefined) {
    throw new ClosedWriterError("WRITER_FACTORY_INVALID", "closed writer requires a trusted ledger and credential resource");
  }
  const runner = config.ledger.createArticleAttemptRunner();
  return Object.freeze({
    runtimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY,
    executeInStep: async (step, request) => await step(
      request.operationKey,
      async () => await executeAttempt(config.ledger, runner, config.credentials, request),
      {
        input: stepInput(request),
        retry: FIXED_RETRY,
      },
    ),
  });
}

async function executeAttempt(
  ledger: ArtifactLedger,
  runner: ArticleAttemptRunner,
  credentials: ClosedWriterCredentialResource,
  request: ClosedWriterExecutionRequest,
): Promise<ArticleAttemptExecutionResult<WriterResult>> {
  validateRequest(request);
  const loaded = loadWriterPackage(ledger, request);
  const prompt = buildCanonicalPrompt(loaded);
  const promptBytes = Buffer.byteLength(prompt, "utf8");
  if (promptBytes > CLOSED_WRITER_RUNTIME_IDENTITY.maxInputBytes) {
    throw new ClosedWriterError("WRITER_INPUT_TOO_LARGE", "lossless writer input exceeds the pinned byte ceiling");
  }
  return await runner.executeModel(
    request.worker,
    {
      rootRunId: loaded.run.runId,
      articleExecutionId: request.articleExecutionId,
      articleId: loaded.entry.articleId,
      operationKey: request.operationKey,
      manuscriptArtifactId: request.currentManuscriptArtifactId,
      access: "source_aware",
      materials: loaded.materials,
    },
    async ({ claim, materials }) => {
      if (!isDeepStrictEqual(materials, loaded.materials)) {
        throw new ClosedWriterError("WRITER_MATERIAL_CHANGED", "claimed writer materials differ from the ledger-owned package");
      }
      const response = await invokeOpenAIResponsesV1(credentials, prompt);
      const result = parseWriterResult(response.output);
      validateWriterResult(result, loaded.entry.productionProfile, loaded.findings);
      return {
        value: result,
        artifacts: resultArtifacts(result, loaded, response.responseId, claim),
      };
    },
  );
}

type LoadedWriterPackage = {
  readonly run: ReturnType<ArtifactLedger["requireRunByArticleExecutionId"]>;
  readonly profileArtifact: LedgerArtifact;
  readonly profileBytes: Uint8Array;
  readonly envelope: ClosedWriterProfileEnvelope;
  readonly entry: LoopsArticleEntryInput;
  readonly materials: ArticleMaterialSet;
  readonly materialBytes: readonly { readonly artifact: LedgerArtifact; readonly classification: string; readonly bytes: Uint8Array }[];
  readonly revisionContext?: { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array; readonly value: ArticleRevisionContext };
  readonly route?: { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array; readonly value: ArticleReviewRoute };
  readonly revisionBrief?: { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array; readonly value: RevisionBrief };
  readonly findings: readonly RevisionFinding[];
};

function loadWriterPackage(ledger: ArtifactLedger, request: ClosedWriterExecutionRequest): LoadedWriterPackage {
  const run = ledger.requireRunByArticleExecutionId(request.articleExecutionId);
  if (run.manuscriptArtifactId !== request.currentManuscriptArtifactId) {
    throw new ClosedWriterError("WRITER_MANUSCRIPT_STALE", "writer request does not name the run's current manuscript");
  }
  const profileRead = ledger.readArtifact(request.productionProfileArtifactId);
  const profileArtifact = profileRead.artifact;
  if (profileArtifact.kind !== "resolved_article_production_profile" || profileArtifact.schemaVersion !== PROFILE_ENVELOPE_VERSION || profileArtifact.payloadKind !== "json" || profileArtifact.producingRunId !== run.runId) {
    throw new ClosedWriterError("WRITER_PROFILE_INVALID", "writer profile is not the exact run-owned resolved profile artifact");
  }
  const envelope = parseProfileEnvelope(profileRead.bytes);
  const entry = envelope.entry;
  if (entry.articleId !== run.articleId || entry.productionProfile.writerResultContractVersion !== "article-writer-result/1") {
    throw new ClosedWriterError("WRITER_PROFILE_MISMATCH", "writer profile does not match the article run");
  }
  assertFixedModelPolicy(entry);
  assertProfileParents(ledger, profileArtifact, entry);

  const revisionContext = request.revisionContextArtifactId === undefined
    ? undefined
    : readRevisionContext(
      ledger,
      request.revisionContextArtifactId,
      run.runId,
      request.articleExecutionId,
      request.currentManuscriptArtifactId,
    );
  const revisionBrief = revisionContext === undefined
    ? undefined
    : readRevisionBrief(
      ledger,
      revisionContext.value.revisionBriefArtifactId,
      run.runId,
      entry.articleId,
      request.currentManuscriptArtifactId,
    );
  const route = revisionContext === undefined
    ? undefined
    : readRevisionRoute(
      ledger,
      revisionContext.value.routeArtifactId,
      run.runId,
      entry.articleId,
      request.currentManuscriptArtifactId,
      revisionContext.value.cycleId,
      revisionContext.value.revisionBriefArtifactId,
    );
  if (revisionContext !== undefined && revisionBrief !== undefined && route !== undefined && (revisionBrief.value.cycleId !== revisionContext.value.cycleId || revisionBrief.value.rewriteOrdinal !== revisionContext.value.rewriteOrdinal || route.value.rewriteOrdinal !== revisionContext.value.rewriteOrdinal)) {
    throw new ClosedWriterError("WRITER_REVISION_CONTEXT_INVALID", "writer revision context, brief, and route disagree on the current cycle");
  }

  const context: ArticleMaterialContext = {
    articleId: entry.articleId,
    contentMode: entry.contentMode,
    sourceIds: entry.sourceIds,
    productionProfile: entry.productionProfile,
    writingRulesArtifactId: entry.writingRulesArtifactId,
    reviewPlan: entry.reviewPlan,
    materializedInputs: entry.materializedInputs,
    ...(envelope.articleBriefArtifactId === undefined ? {} : { articleBriefArtifactId: envelope.articleBriefArtifactId }),
    ...(envelope.editionContextArtifactId === undefined ? {} : { editionContextArtifactId: envelope.editionContextArtifactId }),
    ...(revisionContext === undefined ? {} : {
      revisionContextArtifactId: request.revisionContextArtifactId,
      revisionBriefArtifactId: revisionContext.value.revisionBriefArtifactId,
      routeArtifactId: revisionContext.value.routeArtifactId,
      ...(revisionContext.value.priorWorkingNotesArtifactId === undefined ? {} : { priorWorkingNotesArtifactId: revisionContext.value.priorWorkingNotesArtifactId }),
      ...(revisionContext.value.priorFindingDispositionsArtifactId === undefined ? {} : { priorFindingDispositionsArtifactId: revisionContext.value.priorFindingDispositionsArtifactId }),
      priorReviewMaterialArtifactIds: revisionContext.value.priorReviewMaterialArtifactIds,
      humanRulingArtifactIds: revisionContext.value.humanRulingArtifactIds,
      ...(revisionContext.value.editorDecisionArtifactId === undefined ? {} : { editorDecisionArtifactId: revisionContext.value.editorDecisionArtifactId }),
    }),
    ...(envelope.sourceApprovalArtifactIds === undefined ? {} : { sourceApprovalArtifactIds: envelope.sourceApprovalArtifactIds }),
    ...(envelope.writerReviewMaterialArtifacts === undefined ? {} : { writerReviewMaterialArtifacts: envelope.writerReviewMaterialArtifacts }),
  };
  const selection: ArticleMaterialSelectionContext = {
    manuscriptArtifactId: request.currentManuscriptArtifactId,
    ...(envelope.writerReviewMaterialArtifacts === undefined ? {} : { writerReviewMaterialArtifacts: envelope.writerReviewMaterialArtifacts }),
  };
  const materials = selectArticleWriterMaterials(context, selection);
  assertArticleExecutionMaterials({
    articleId: entry.articleId,
    manuscriptArtifactId: request.currentManuscriptArtifactId,
    access: "source_aware",
    materials,
  });
  const profileParents = new Set(profileArtifact.parents.map((parent) => parent.artifactId));
  const declaredMaterialIds = new Set(entry.materializedInputs.flatMap((input) => input.artifacts.map((artifact) => artifact.artifactId)));
  const revisionParents = new Set(revisionContext?.artifact.parents.map((parent) => parent.artifactId) ?? []);
  const materialBytes = materials.artifacts.map((material) => {
    const read = ledger.readArtifact(material.artifactId);
    if (material.artifactId !== request.currentManuscriptArtifactId && material.artifactId !== request.revisionContextArtifactId && !revisionParents.has(material.artifactId) && !profileParents.has(material.artifactId) && !declaredMaterialIds.has(material.artifactId)) {
      throw new ClosedWriterError("WRITER_MATERIAL_LINEAGE_INVALID", "writer material is not bound by the resolved profile lineage");
    }
    return { artifact: read.artifact, classification: material.classification, bytes: read.bytes };
  });
  const findings = revisionBrief === undefined ? [] : revisionFindings(revisionBrief.value);
  return {
    run,
    profileArtifact,
    profileBytes: profileRead.bytes,
    envelope,
    entry,
    materials,
    materialBytes,
    ...(revisionContext === undefined ? {} : { revisionContext }),
    ...(route === undefined ? {} : { route }),
    ...(revisionBrief === undefined ? {} : { revisionBrief }),
    findings,
  };
}

function buildCanonicalPrompt(loaded: LoadedWriterPackage): string {
  const findingManifest = buildFindingManifest(loaded.findings);
  const sections = [
    "MAGAZINE CLOSED WRITER REQUEST",
    `runtimeIdentity=${stableJson(CLOSED_WRITER_RUNTIME_IDENTITY as unknown as JsonObject)}`,
    `articleId=${loaded.entry.articleId}`,
    `contentMode=${loaded.entry.contentMode}`,
    `byline=${JSON.stringify(loaded.entry.byline)}`,
    `sourceAuthors=${stableJson(loaded.entry.sourceAuthors as unknown as JsonValue)}`,
    `brief=${JSON.stringify(loaded.entry.brief)}`,
    `findingManifest=${stableJson(findingManifest as unknown as JsonValue)}`,
    "Return only the JSON value described by the pinned response schema.",
    artifactSection(loaded.profileArtifact, "resolved_profile", loaded.profileBytes),
    ...loaded.materialBytes.map(({ artifact, classification, bytes }) => artifactSection(artifact, classification, bytes)),
  ];
  return sections.join("\n");
}

export function buildFindingManifest(findings: readonly RevisionFinding[]): JsonValue {
  return findings.map((finding) => ({
    findingId: `${finding.reviewResultArtifactId}#${finding.localId}`,
    reviewResultArtifactId: finding.reviewResultArtifactId,
    localId: finding.localId,
    contentDigest: finding.contentDigest,
  })).sort((left, right) => left.findingId.localeCompare(right.findingId));
}

function artifactSection(artifact: LedgerArtifact, classification: string, bytes: Uint8Array): string {
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new ClosedWriterError("WRITER_MATERIAL_INVALID", "closed writer material is not valid UTF-8");
  }
  return [
    `--- artifact ${artifact.id} ${classification} ${artifact.mediaType} sha256:${artifact.digest} ---`,
    text,
    `--- end artifact ${artifact.id} ---`,
  ].join("\n");
}

function resultArtifacts(
  result: WriterResult,
  loaded: LoadedWriterPackage,
  responseId: string,
  claim: { readonly articleExecutionId: string; readonly operationKey: string; readonly access: string },
) {
  const prompt = buildCanonicalPrompt(loaded);
  const parents = uniqueIds([
    loaded.profileArtifact.id,
    ...loaded.materials.artifactIds,
  ]).map((artifactId) => ({ artifactId, relation: "writer_input" }));
  const writerInputArtifactIds = parents.map((parent) => parent.artifactId);
  const metadata: JsonObject = {
    articleId: loaded.entry.articleId,
    revisionId: `writer-revision:${claim.articleExecutionId}:${claim.operationKey}`,
    articleExecutionId: claim.articleExecutionId,
    operationKey: claim.operationKey,
    access: claim.access,
    writerExecutionClass: CLOSED_WRITER_EXECUTION_CLASS,
    writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY as unknown as JsonObject,
    writerInputArtifactIds: writerInputArtifactIds as unknown as JsonValue,
    writerPromptDigest: `sha256:${createHash("sha256").update(prompt, "utf8").digest("hex")}`,
    providerResponseId: responseId,
    ...(loaded.revisionContext === undefined ? {} : { revisionContextArtifactId: loaded.revisionContext.artifact.id }),
    ...(loaded.revisionBrief === undefined ? {} : { revisionBriefArtifactId: loaded.revisionBrief.artifact.id }),
    ...(loaded.route === undefined ? {} : { routeArtifactId: loaded.route.artifact.id }),
    ...(loaded.revisionContext === undefined ? {} : { cycleId: loaded.revisionContext.value.cycleId, rewriteOrdinal: loaded.revisionContext.value.rewriteOrdinal }),
  };
  return [
    {
      key: "manuscript",
      kind: "article_manuscript",
      schemaVersion: "article-manuscript/1",
      mediaType: "text/markdown",
      origin: "model" as const,
      payload: { kind: "text" as const, text: result.manuscript },
      parents,
      metadata,
    },
    {
      key: "working-notes",
      kind: "writer_working_notes",
      schemaVersion: "writer-working-notes/1",
      mediaType: "text/plain",
      origin: "model" as const,
      payload: { kind: "text" as const, text: result.workingNotes },
      parents,
      metadata,
    },
    {
      key: "finding-dispositions",
      kind: "writer_finding_dispositions",
      schemaVersion: "writer-finding-dispositions/1",
      mediaType: "application/json",
      origin: "model" as const,
      payload: { kind: "json" as const, value: { schemaVersion: "writer-finding-dispositions/1", dispositions: result.dispositions as unknown as JsonValue } },
      parents,
      metadata,
    },
    ...result.reviewMaterials.map((material) => ({
      key: `review-material:${material.materialId}`,
      kind: "writer_review_material",
      schemaVersion: "writer-review-material/1",
      mediaType: "application/json",
      origin: "model" as const,
      payload: { kind: "json" as const, value: material as unknown as JsonValue },
      parents,
      metadata: { ...metadata, materialId: material.materialId, materialSchemaVersion: material.schemaVersion },
    })),
  ];
}

function parseProfileEnvelope(bytes: Uint8Array): ClosedWriterProfileEnvelope {
  const value = parseJsonBytes(bytes, "writer profile");
  exactKeys(value, ["schemaVersion", "entry", "articleBriefArtifactId", "editionContextArtifactId", "sourceApprovalArtifactIds", "writerReviewMaterialArtifacts"], "writer profile");
  if (value.schemaVersion !== PROFILE_ENVELOPE_VERSION) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "writer profile schema is invalid");
  const entry = parseEntry(value.entry);
  optionalArtifactId(value.articleBriefArtifactId, "articleBriefArtifactId");
  optionalArtifactId(value.editionContextArtifactId, "editionContextArtifactId");
  const sourceApprovalArtifactIds = optionalArtifactIds(value.sourceApprovalArtifactIds, "sourceApprovalArtifactIds");
  const writerReviewMaterialArtifacts = optionalArtifactMap(value.writerReviewMaterialArtifacts, "writerReviewMaterialArtifacts");
  return {
    schemaVersion: PROFILE_ENVELOPE_VERSION,
    entry,
    ...(value.articleBriefArtifactId === undefined ? {} : { articleBriefArtifactId: value.articleBriefArtifactId as ArtifactId }),
    ...(value.editionContextArtifactId === undefined ? {} : { editionContextArtifactId: value.editionContextArtifactId as ArtifactId }),
    ...(sourceApprovalArtifactIds === undefined ? {} : { sourceApprovalArtifactIds }),
    ...(writerReviewMaterialArtifacts === undefined ? {} : { writerReviewMaterialArtifacts }),
  };
}

function parseEntry(value: unknown): LoopsArticleEntryInput {
  const entry = plainObject(value, "writer entry");
  exactKeys(entry, ["schemaVersion", "articleId", "contentMode", "byline", "sourceIds", "sourceAuthors", "brief", "maximumReaderPages", "modelPolicy", "productionProfile", "writingRulesArtifactId", "reviewPlan", "materializedInputs", "inputBindings"], "writer entry");
  if (entry.schemaVersion !== "loops-article-entry-input/1" || !text(entry.articleId) || !text(entry.byline) || !text(entry.brief) || !Number.isSafeInteger(entry.maximumReaderPages) || (entry.maximumReaderPages as number) <= 0) {
    throw new ClosedWriterError("WRITER_PROFILE_INVALID", "writer entry identity is invalid");
  }
  if (!new Set(["faithful_edit", "faithful_synthesis", "original_synthesis"]).has(entry.contentMode as string) || !stringArray(entry.sourceIds) || !stringArray(entry.sourceAuthors) || !text(entry.writingRulesArtifactId)) {
    throw new ClosedWriterError("WRITER_PROFILE_INVALID", "writer entry policy is invalid");
  }
  validateModelPolicy(entry.modelPolicy);
  validateResolvedProfile(entry.productionProfile);
  validateReviewPlan(entry.reviewPlan);
  validateMaterializedInputs(entry.materializedInputs);
  validateInputBindings(entry.inputBindings);
  return entry as unknown as LoopsArticleEntryInput;
}

function assertProfileParents(ledger: ArtifactLedger, artifact: LedgerArtifact, entry: LoopsArticleEntryInput): void {
  const expected = entry.inputBindings.map((binding) => binding.artifactId);
  const actual = artifact.parents.map((parent) => parent.artifactId);
  if (!sameStrings(expected, actual) || new Set(actual).size !== actual.length || artifact.parents.some((parent) => parent.relation !== "input_binding")) {
    throw new ClosedWriterError("WRITER_PROFILE_LINEAGE_INVALID", "resolved writer profile parents do not equal its exact input bindings");
  }
  for (const binding of entry.inputBindings) {
    const bound = ledger.requireArtifact(binding.artifactId);
    if (bound.metadata.revisionId !== binding.revision.revisionId || !isDeepStrictEqual(bound.metadata.inputRevision, binding.revision)) {
      throw new ClosedWriterError("WRITER_PROFILE_LINEAGE_INVALID", "resolved writer profile input binding does not match ledger metadata");
    }
  }
}

type RevisionBrief = {
  readonly schemaVersion: typeof REVISION_BRIEF_VERSION;
  readonly articleId: string;
  readonly manuscriptArtifactId: ArtifactId;
  readonly mustFix: readonly JsonObject[];
  readonly consider: readonly JsonObject[];
  readonly humanRulings: readonly ArtifactId[];
  readonly reviewResultArtifactIds: readonly ArtifactId[];
  readonly measurementArtifactId: ArtifactId;
  readonly reviewOutputArtifactIds: readonly ArtifactId[];
  readonly iterationId: string;
  readonly cycleId?: string;
  readonly manuscriptRevisionId?: string;
  readonly reviewPlanArtifactId?: ArtifactId;
  readonly rewriteOrdinal?: number;
};

function readRevisionContext(
  ledger: ArtifactLedger,
  artifactId: ArtifactId,
  runId: string,
  articleExecutionId: ArticleExecutionId,
  manuscriptArtifactId: ArtifactId,
): { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array; readonly value: ArticleRevisionContext } {
  const read = ledger.readArtifact(artifactId);
  if (read.artifact.kind !== "article_revision_context" || read.artifact.schemaVersion !== "article-revision-context/1" || read.artifact.mediaType !== "application/json" || read.artifact.payloadKind !== "json" || read.artifact.producingRunId !== runId) {
    throw new ClosedWriterError("WRITER_REVISION_CONTEXT_INVALID", "writer revision context is not the exact run-owned artifact");
  }
  let value: ArticleRevisionContext;
  try {
    value = parseArticleRevisionContext(parseJsonBytes(read.bytes, "revision context"));
  } catch (error) {
    if (error instanceof ClosedWriterError) throw error;
    throw new ClosedWriterError("WRITER_REVISION_CONTEXT_INVALID", "writer revision context does not match its strict schema", { cause: error });
  }
  if (value.articleExecutionId !== articleExecutionId || value.previousManuscriptArtifactId !== manuscriptArtifactId || read.artifact.metadata.articleExecutionId !== articleExecutionId || read.artifact.metadata.cycleId !== value.cycleId || read.artifact.metadata.rewriteOrdinal !== value.rewriteOrdinal) {
    throw new ClosedWriterError("WRITER_REVISION_CONTEXT_INVALID", "writer revision context does not match the current article execution");
  }
  const expectedParents = articleRevisionContextParents(value);
  if (!sameParents(read.artifact.parents, expectedParents)) {
    throw new ClosedWriterError("WRITER_REVISION_CONTEXT_LINEAGE_INVALID", "revision context parents do not equal its exact immutable references");
  }
  for (const parent of expectedParents) ledger.requireArtifact(parent.artifactId);
  return { artifact: read.artifact, bytes: read.bytes, value };
}

function readRevisionRoute(
  ledger: ArtifactLedger,
  artifactId: ArtifactId,
  runId: string,
  articleId: string,
  manuscriptArtifactId: ArtifactId,
  cycleId: string,
  revisionBriefArtifactId: ArtifactId,
): { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array; readonly value: ArticleReviewRoute } {
  const read = ledger.readArtifact(artifactId);
  if (read.artifact.kind !== "article_review_route" || read.artifact.schemaVersion !== "article-review-route/1" || read.artifact.mediaType !== "application/json" || read.artifact.payloadKind !== "json" || read.artifact.producingRunId !== runId) {
    throw new ClosedWriterError("WRITER_REVIEW_ROUTE_INVALID", "writer route is not the exact run-owned artifact");
  }
  let raw: unknown;
  try { raw = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(read.bytes)); } catch (error) {
    throw new ClosedWriterError("WRITER_REVIEW_ROUTE_INVALID", "writer route is not valid JSON", { cause: error });
  }
  const parsed = articleReviewRouteSchema.safeParse(raw);
  if (!parsed.success) throw new ClosedWriterError("WRITER_REVIEW_ROUTE_INVALID", "writer route does not match its strict schema");
  const value = parsed.data as unknown as ArticleReviewRoute;
  if (value.articleId !== articleId || value.manuscriptArtifactId !== manuscriptArtifactId || value.cycleId !== cycleId || read.artifact.parents.length !== 1 || read.artifact.parents[0]?.artifactId !== revisionBriefArtifactId) {
    throw new ClosedWriterError("WRITER_REVIEW_ROUTE_INVALID", "writer route does not match the current revision context");
  }
  if (read.artifact.parents.length !== 1 || read.artifact.parents[0]?.relation !== "revision_brief") {
    throw new ClosedWriterError("WRITER_REVIEW_ROUTE_LINEAGE_INVALID", "writer route parent is not the exact revision brief");
  }
  return { artifact: read.artifact, bytes: read.bytes, value };
}

function readRevisionBrief(
  ledger: ArtifactLedger,
  artifactId: ArtifactId,
  runId: string,
  articleId: string,
  manuscriptArtifactId: ArtifactId,
): { readonly artifact: LedgerArtifact; readonly bytes: Uint8Array; readonly value: RevisionBrief } {
  const read = ledger.readArtifact(artifactId);
  if (read.artifact.kind !== "article_revision_brief" || read.artifact.schemaVersion !== REVISION_BRIEF_VERSION || read.artifact.payloadKind !== "json" || read.artifact.producingRunId !== runId) {
    throw new ClosedWriterError("WRITER_REVISION_BRIEF_INVALID", "writer revision brief is not the exact run-owned artifact");
  }
  const raw = parseJsonBytes(read.bytes, "revision brief");
  exactKeys(raw, ["schemaVersion", "articleId", "iterationId", "manuscriptArtifactId", "mustFix", "consider", "humanRulings", "reviewResultArtifactIds", "measurementArtifactId", "reviewOutputArtifactIds", "cycleId", "manuscriptRevisionId", "reviewPlanArtifactId", "rewriteOrdinal"], "revision brief");
  if (raw.schemaVersion !== REVISION_BRIEF_VERSION || raw.articleId !== articleId || raw.manuscriptArtifactId !== manuscriptArtifactId || !text(raw.iterationId) || !text(raw.measurementArtifactId)) {
    throw new ClosedWriterError("WRITER_REVISION_BRIEF_INVALID", "writer revision brief does not match the current manuscript");
  }
  const mustFix = jsonObjectArray(raw.mustFix, "mustFix");
  const consider = jsonObjectArray(raw.consider, "consider");
  const humanRulings = artifactIdsValue(raw.humanRulings, "humanRulings");
  const reviewResultArtifactIds = artifactIdsValue(raw.reviewResultArtifactIds, "reviewResultArtifactIds");
  const reviewOutputArtifactIds = artifactIdsValue(raw.reviewOutputArtifactIds, "reviewOutputArtifactIds");
  const expectedParents = [manuscriptArtifactId, ...reviewResultArtifactIds, raw.measurementArtifactId as ArtifactId, ...reviewOutputArtifactIds, ...humanRulings];
  if (!sameStrings(read.artifact.parents.map((parent) => parent.artifactId), expectedParents) || new Set(expectedParents).size !== expectedParents.length) {
    throw new ClosedWriterError("WRITER_REVISION_BRIEF_LINEAGE_INVALID", "revision brief parents do not equal its immutable references");
  }
  return {
    artifact: read.artifact,
    bytes: read.bytes,
    value: {
      schemaVersion: REVISION_BRIEF_VERSION,
      articleId,
      manuscriptArtifactId,
      mustFix,
      consider,
      humanRulings,
      reviewResultArtifactIds,
      measurementArtifactId: raw.measurementArtifactId as ArtifactId,
      reviewOutputArtifactIds,
      iterationId: raw.iterationId as string,
      ...(raw.cycleId === undefined ? {} : { cycleId: raw.cycleId as string }),
      ...(raw.manuscriptRevisionId === undefined ? {} : { manuscriptRevisionId: raw.manuscriptRevisionId as string }),
      ...(raw.reviewPlanArtifactId === undefined ? {} : { reviewPlanArtifactId: raw.reviewPlanArtifactId as ArtifactId }),
      ...(raw.rewriteOrdinal === undefined ? {} : { rewriteOrdinal: raw.rewriteOrdinal as number }),
    },
  };
}

function revisionFindings(brief: RevisionBrief): readonly RevisionFinding[] {
  return [...brief.mustFix, ...brief.consider].map((finding) => {
    const reviewResultArtifactId = finding.reviewResultArtifactId;
    const localId = finding.localId;
    if (!text(reviewResultArtifactId) || !text(localId) || !brief.reviewResultArtifactIds.includes(reviewResultArtifactId as ArtifactId)) {
      throw new ClosedWriterError("WRITER_REVISION_BRIEF_INVALID", "revision brief finding identity is invalid");
    }
    return {
      reviewResultArtifactId,
      localId,
      contentDigest: createHash("sha256").update(stableJson(finding), "utf8").digest("hex"),
    };
  });
}

function assertFixedModelPolicy(entry: LoopsArticleEntryInput): void {
  const choice = entry.modelPolicy.roles?.writer ?? entry.modelPolicy.default;
  if (choice.adapter !== OPENAI_RESPONSES_V1_POLICY.providerCodec || choice.model !== OPENAI_RESPONSES_V1_POLICY.model || choice.reasoningEffort !== OPENAI_RESPONSES_V1_POLICY.reasoningEffort || choice.settings !== undefined) {
    throw new ClosedWriterError("WRITER_RUNTIME_MISMATCH", "immutable writer model policy does not match the fixed runtime identity");
  }
}

function stepInput(request: ClosedWriterExecutionRequest): JsonObject {
  return {
    schemaVersion: "closed-writer-step-input/1",
    articleExecutionId: request.articleExecutionId,
    operationKey: request.operationKey,
    currentManuscriptArtifactId: request.currentManuscriptArtifactId,
    productionProfileArtifactId: request.productionProfileArtifactId,
    ...(request.revisionContextArtifactId === undefined ? {} : { revisionContextArtifactId: request.revisionContextArtifactId }),
    writerRuntimeIdentity: CLOSED_WRITER_RUNTIME_IDENTITY as unknown as JsonObject,
  };
}

function validateRequest(request: ClosedWriterExecutionRequest): void {
  if (!text(request.articleExecutionId) || !text(request.operationKey) || !text(request.currentManuscriptArtifactId) || !text(request.productionProfileArtifactId) || request.revisionContextArtifactId !== undefined && !text(request.revisionContextArtifactId)) {
    throw new ClosedWriterError("WRITER_REQUEST_INVALID", "closed writer request requires exact immutable IDs");
  }
  const mode = request.mode ?? "initial";
  if (mode === "rewrite" && request.revisionContextArtifactId === undefined) {
    throw new ClosedWriterError("WRITER_MODE_INVALID", "rewrite writer requests require an exact revision context artifact");
  }
  if (mode === "initial" && request.revisionContextArtifactId !== undefined) {
    throw new ClosedWriterError("WRITER_MODE_INVALID", "initial writer requests cannot carry a revision context artifact");
  }
}

function validateModelPolicy(value: unknown): void {
  const policy = plainObject(value, "model policy");
  exactKeys(policy, ["default", "roles"], "model policy");
  validateModelChoice(policy.default);
  if (policy.roles !== undefined) {
    const roles = plainObject(policy.roles, "model policy roles");
    for (const choice of Object.values(roles)) validateModelChoice(choice);
  }
}

function validateModelChoice(value: unknown): void {
  const choice = plainObject(value, "model choice");
  exactKeys(choice, ["adapter", "model", "reasoningEffort", "settings"], "model choice");
  if (!text(choice.adapter) || !text(choice.model) || choice.reasoningEffort !== undefined && !text(choice.reasoningEffort) || choice.settings !== undefined) {
    throw new ClosedWriterError("WRITER_PROFILE_INVALID", "model choice is invalid");
  }
}

function validateResolvedProfile(value: unknown): asserts value is ResolvedArticleProductionProfile {
  const profile = plainObject(value, "resolved production profile");
  exactKeys(profile, ["schemaVersion", "profileId", "formatId", "profileArtifactId", "writerPromptArtifactId", "writerResultContractVersion", "reviewMaterials", "reviewPlanArtifactId", "writingRulesArtifactId", "writingPolicyArtifactIds", "maximumRewrites"], "resolved production profile");
  if (profile.schemaVersion !== PROFILE_ENVELOPE_VERSION || !text(profile.profileId) || !text(profile.formatId) || !text(profile.profileArtifactId) || !text(profile.writerPromptArtifactId) || profile.writerResultContractVersion !== "article-writer-result/1" || !text(profile.reviewPlanArtifactId) || !text(profile.writingRulesArtifactId) || !Number.isSafeInteger(profile.maximumRewrites) || (profile.maximumRewrites as number) < 0 || !stringArray(profile.writingPolicyArtifactIds)) {
    throw new ClosedWriterError("WRITER_PROFILE_INVALID", "resolved production profile is invalid");
  }
  if (!Array.isArray(profile.reviewMaterials)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "resolved production profile materials are invalid");
  for (const value of profile.reviewMaterials) {
    const material = plainObject(value, "review material declaration");
    exactKeys(material, ["materialId", "schemaArtifactId", "schemaVersion", "required"], "review material declaration");
    if (!text(material.materialId) || !text(material.schemaArtifactId) || !text(material.schemaVersion) || typeof material.required !== "boolean") throw new ClosedWriterError("WRITER_PROFILE_INVALID", "review material declaration is invalid");
  }
}

function validateReviewPlan(value: unknown): asserts value is ResolvedReviewPlan {
  const plan = plainObject(value, "review plan");
  exactKeys(plan, ["schemaVersion", "reviewPlanArtifactId", "checks", "waves"], "review plan");
  if (plan.schemaVersion !== "resolved-article-review-plan/1" || !text(plan.reviewPlanArtifactId) || !Array.isArray(plan.checks) || !Array.isArray(plan.waves)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "review plan is invalid");
}

function validateMaterializedInputs(value: unknown): void {
  if (!Array.isArray(value)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "materialized inputs are invalid");
  for (const candidate of value) {
    const input = plainObject(candidate, "materialized input");
    exactKeys(input, ["ref", "artifacts"], "materialized input");
    validateRevisionRef(input.ref);
    if (!Array.isArray(input.artifacts)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "materialized input artifacts are invalid");
    for (const item of input.artifacts) {
      const artifact = plainObject(item, "materialized input artifact");
      exactKeys(artifact, ["path", "artifactId"], "materialized input artifact");
      if (!text(artifact.path) || !text(artifact.artifactId)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "materialized input artifact is invalid");
    }
  }
}

function validateInputBindings(value: unknown): void {
  if (!Array.isArray(value) || value.length === 0) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "writer input bindings are invalid");
  for (const candidate of value) {
    const binding = plainObject(candidate, "input binding");
    exactKeys(binding, ["artifactId", "revision"], "input binding");
    if (!text(binding.artifactId)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "input binding artifact is invalid");
    validateRevisionRef(binding.revision);
  }
}

function validateRevisionRef(value: unknown): asserts value is InputRevisionRef {
  const ref = plainObject(value, "input revision");
  exactKeys(ref, ["kind", "logicalId", "revisionId", "editionId"], "input revision");
  if (!text(ref.kind) || !text(ref.logicalId) || !text(ref.revisionId) || ref.editionId !== undefined && !text(ref.editionId)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", "input revision is invalid");
}

function parseJsonBytes(bytes: Uint8Array, label: string): Record<string, unknown> {
  try {
    return plainObject(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)), label);
  } catch (error) {
    if (error instanceof ClosedWriterError) throw error;
    throw new ClosedWriterError("WRITER_PROFILE_INVALID", `${label} is not strict JSON`);
  }
}

function plainObject(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", `${label} is invalid`);
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, allowed: readonly string[], label: string): void {
  const set = new Set(allowed);
  if (Object.keys(value).some((key) => !set.has(key))) throw new ClosedWriterError("WRITER_PROFILE_INVALID", `${label} contains an unknown field`);
}

function text(value: unknown): value is string { return typeof value === "string" && value.trim().length > 0; }
function stringArray(value: unknown): value is string[] { return Array.isArray(value) && value.every(text); }
function optionalArtifactId(value: unknown, label: string): void { if (value !== undefined && !text(value)) throw new ClosedWriterError("WRITER_PROFILE_INVALID", `${label} is invalid`); }
function optionalArtifactIds(value: unknown, label: string): readonly ArtifactId[] | undefined { return value === undefined ? undefined : artifactIdsValue(value, label); }
function optionalArtifactMap(value: unknown, label: string): Readonly<Record<string, ArtifactId>> | undefined {
  if (value === undefined) return undefined;
  const map = plainObject(value, label);
  if (Object.values(map).some((item) => !text(item))) throw new ClosedWriterError("WRITER_PROFILE_INVALID", `${label} is invalid`);
  return map as Readonly<Record<string, ArtifactId>>;
}
function artifactIdsValue(value: unknown, label: string): readonly ArtifactId[] { if (!stringArray(value) || new Set(value).size !== value.length) throw new ClosedWriterError("WRITER_REVISION_BRIEF_INVALID", `${label} is invalid`); return value as ArtifactId[]; }
function jsonObjectArray(value: unknown, label: string): readonly JsonObject[] { if (!Array.isArray(value) || value.some((item) => typeof item !== "object" || item === null || Array.isArray(item))) throw new ClosedWriterError("WRITER_REVISION_BRIEF_INVALID", `${label} is invalid`); return value as JsonObject[]; }
function sameStrings(left: readonly string[], right: readonly string[]): boolean { return left.length === right.length && left.every((value, index) => value === right[index]); }
function sameParents(left: readonly { readonly artifactId: ArtifactId; readonly relation: string }[], right: readonly { readonly artifactId: ArtifactId; readonly relation: string }[]): boolean {
  return left.length === right.length && left.every((parent, index) => {
    const expected = right[index];
    return expected !== undefined && expected.artifactId === parent.artifactId && expected.relation === parent.relation;
  });
}
function uniqueIds(values: readonly ArtifactId[]): readonly ArtifactId[] { return [...new Set(values)]; }
