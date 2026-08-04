import { GitCliDurableGit } from "../durable/git-cli.ts";
import { ArticlePromotionAuthority, DurableStoreArticlePromotionSink } from "../workflow-authority/article-promotion.ts";
import { ArtifactLedger, ArtifactLedgerError } from "../workflow-authority/artifact-ledger.ts";
import { measureArticle } from "../renderer-adapter/article-measurement.ts";
import { PythonRendererAdapter } from "../renderer-adapter/python-renderer.ts";
import type { ArticleMeasurement, ArticleWorkflowPorts } from "./internal-types.ts";
import type { MagazineWorkflowEngineOptions } from "../contracts/workflow-run.ts";
import type { ArticleWorkflowResult } from "../contracts/workflow-run.ts";
import { measurementId } from "./article-workflow.ts";
import { readVerifiedRendererIdentity } from "./renderer-identity.ts";
import { runArticleReviewPanel } from "./article-review-panel.ts";
import type { AuthorizedWorker } from "../authority/local-authority.ts";
import { createClosedReviewerExecutor, type ClosedReviewerExecutor } from "../executors/closed-reviewer/runtime.ts";
import { createClosedWriterExecutor, type ClosedWriterExecutor } from "../executors/closed-writer/runtime.ts";
import { readOpenAIAPIKey } from "../executors/closed-writer/credentials.ts";

/** Included in the fixed Loops source graph. */
export const ARTICLE_RUNTIME_GRAPH = "magazine-article-runtime/1" as const;

export function createArticleWorkflowPorts(options: {
  readonly ledger: ArtifactLedger;
  readonly repositoryRoot: string;
  readonly workRoot: string;
  readonly renderer: NonNullable<MagazineWorkflowEngineOptions["renderer"]>;
  readonly projectRoot: string;
  readonly articleReviewWorkers?: NonNullable<MagazineWorkflowEngineOptions["articleReviewWorkers"]>;
  readonly articleWriter?: MagazineWorkflowEngineOptions["articleWriter"];
  readonly articleReviewCredentials?: NonNullable<MagazineWorkflowEngineOptions["articleReviewCredentials"]>;
}): ArticleWorkflowPorts {
  const rendererProjectRoot = options.renderer.projectRoot ?? options.projectRoot;
  const adapter = new PythonRendererAdapter(
    rendererProjectRoot,
    options.renderer.timeoutMs,
    () => readVerifiedRendererIdentity(rendererProjectRoot, undefined, options.renderer.toolchain),
    options.renderer.toolchain,
  );
  const promotionSink = new DurableStoreArticlePromotionSink({
    repositoryRoot: options.repositoryRoot,
    workRoot: options.workRoot,
    git: new GitCliDurableGit(options.repositoryRoot),
    evidence: {
      inspect: async (runId) => options.ledger.durableEvidence(runId),
      readArtifact: async (artifactId) => options.ledger.readArtifact(artifactId),
    },
  });
  const promotions = new ArticlePromotionAuthority({ ledger: options.ledger, sink: promotionSink });
  const attemptRunner = options.ledger.createArticleAttemptRunner();
  let reviewWorkers: Promise<{
    readonly sourceAwareReviewer: AuthorizedWorker;
    readonly sourceBlindReviewer: AuthorizedWorker;
    readonly measurementTool: AuthorizedWorker;
  }> | undefined;
  let reviewerExecutor: ClosedReviewerExecutor | undefined;
  let writerExecutor: ClosedWriterExecutor | undefined;
  const ensureReviewWorkers = async () => {
    reviewWorkers ??= (async () => {
      const workers = options.articleReviewWorkers;
      if (workers === undefined) throw new Error("Article review runtime requires three authenticated workers");
      const descriptions = await Promise.all([
        workers.sourceAwareReviewer.describe(),
        workers.sourceBlindReviewer.describe(),
        workers.measurementTool.describe(),
      ]);
      const writerDescription = options.articleWriter === undefined ? undefined : await options.articleWriter.describe();
      const allDescriptions = writerDescription === undefined ? descriptions : [...descriptions, writerDescription];
      const principalIds = allDescriptions.map((description) => description.principalId);
      const credentialIds = allDescriptions.map((description) => description.credentialProfileId);
      if (new Set(principalIds).size !== principalIds.length || new Set(credentialIds).size !== credentialIds.length) {
        throw new Error("Article review workers must use distinct authenticated principal and credential IDs");
      }
      const aware = descriptions[0]!;
      const blind = descriptions[1]!;
      const tool = descriptions[2]!;
      if (aware.authority !== "model" || !exactCapabilities(aware.capabilities, ["source_access", "text_model"])) {
        throw new Error("Source-aware reviewer must be an authenticated model with text_model and source_access only");
      }
      if (blind.authority !== "model" || !exactCapabilities(blind.capabilities, ["source_blind", "text_model"])) {
        throw new Error("Source-blind reviewer must be an authenticated model with text_model and source_blind only");
      }
      if (tool.authority !== "tool" || !exactCapabilities(tool.capabilities, ["subprocess"])) {
        throw new Error("Measurement tool must be an authenticated subprocess worker");
      }
      if (writerDescription !== undefined && (writerDescription.authority !== "model" || !exactCapabilities(writerDescription.capabilities, ["source_access", "text_model"]))) {
        throw new Error("Article writer must be an authenticated source-aware model with text_model and source_access only");
      }
      return workers;
    })();
    return await reviewWorkers;
  };
  return {
    ledger: options.ledger,
    validateRuntimeResources: async () => {
      await ensureReviewWorkers();
      const credentials = options.articleReviewCredentials;
      if (credentials === undefined) throw new Error("Article review runtime requires a closed reviewer credential resource");
      // Validate the resource before any ledger/run/Loops mutation. Do not
      // retain or log the secret returned by this probe.
      await readOpenAIAPIKey(credentials);
      // The writer shares the owner-private credential resource, but has its
      // own authenticated worker identity when supplied. Existing clean
      // review runs do not need to construct a writer until a rewrite route.
      if (options.articleWriter !== undefined) await options.articleWriter.describe();
    },
    measureArticle: async (input): Promise<ArticleMeasurement> => {
      const result = await measureArticle({
        adapter,
        artifacts: input.artifacts ?? {
          readBytes: async (artifactId) => options.ledger.readArtifact(artifactId).bytes,
          readText: async (artifactId) => Buffer.from(options.ledger.readArtifact(artifactId).bytes).toString("utf8"),
        },
        workDirectory: options.renderer.workDirectory,
        articleId: input.articleId,
        manuscriptArtifactId: input.manuscriptArtifactId,
        measurementProfileArtifactId: input.measurementProfileArtifactId,
        rendererIdentity: input.rendererIdentity,
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
      });
      return result;
    },
    runReviewPanel: async (input, context) => {
      const workers = await ensureReviewWorkers();
      const credentials = options.articleReviewCredentials;
      if (credentials === undefined) throw new Error("Article review runtime requires a closed reviewer credential resource");
      reviewerExecutor ??= createClosedReviewerExecutor({ ledger: options.ledger, credentials, attemptRunner });
      return await runArticleReviewPanel(input, context, {
        ledger: options.ledger,
        attemptRunner,
        reviewerFor: async (check) => check.access === "source_aware" ? workers.sourceAwareReviewer : workers.sourceBlindReviewer,
        toolWorkerFor: async () => workers.measurementTool,
        runModelReview: async ({ claim, check, materials, manuscriptArtifactId, manuscriptRevisionId }) => await reviewerExecutor!.review({
          check: {
            id: check.id,
            role: check.role,
            access: check.access,
            authority: check.authority,
            promptArtifactId: check.promptArtifactId,
            reviewPlanArtifactId: input.materialContext.reviewPlan.reviewPlanArtifactId,
          },
          materials,
          manuscriptArtifactId,
          manuscriptRevisionId,
          claim,
        }),
        measureArticle: async (measurement) => await measureArticle({
          adapter,
          artifacts: measurement.artifacts ?? {
            readBytes: async (artifactId) => options.ledger.readArtifact(artifactId).bytes,
            readText: async (artifactId) => Buffer.from(options.ledger.readArtifact(artifactId).bytes).toString("utf8"),
          },
          workDirectory: options.renderer.workDirectory,
          articleId: measurement.articleId,
          manuscriptArtifactId: measurement.manuscriptArtifactId,
          measurementProfileArtifactId: measurement.measurementProfileArtifactId,
          rendererIdentity: measurement.rendererIdentity,
          ...(measurement.durableContext === undefined ? {} : { durableContext: measurement.durableContext }),
        }),
      });
    },
    runWriter: async (input, context) => {
      const workers = await ensureReviewWorkers();
      const credentials = options.articleReviewCredentials;
      if (credentials === undefined) throw new Error("Article writer runtime requires a closed writer credential resource");
      const worker = options.articleWriter;
      if (worker === undefined) throw new Error("Article route requires an authenticated article writer worker");
      writerExecutor ??= createClosedWriterExecutor({ ledger: options.ledger, credentials });
      return await writerExecutor.executeInStep(
        async (key, operation, stepOptions) => await context.step(key, operation, {
          input: stepOptions.input,
          retry: stepOptions.retry,
          label: "article.writer",
        }),
        {
          worker,
          mode: "rewrite",
          articleExecutionId: input.articleExecutionId,
          operationKey: input.operationKey,
          currentManuscriptArtifactId: input.currentManuscriptArtifactId,
          productionProfileArtifactId: input.productionProfileArtifactId,
          revisionContextArtifactId: input.revisionContextArtifactId,
        },
      );
    },
    requireDecision: (artifactId) => {
      const artifact = options.ledger.requireArtifact(artifactId);
      const runId = artifact.producingRunId;
      if (runId === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${artifactId} has no producing run`);
      const decision = options.ledger.getDecisionByArtifactId(runId, artifactId);
      if (decision === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${artifactId} is not current`);
      return decision;
    },
    promote: async (input): Promise<ArticleWorkflowResult> => {
      const promotion = await promotions.promote({
        runId: input.request.runId,
        articleId: input.request.logicalItem.kind === "article" ? input.request.logicalItem.logicalId : "",
        manuscriptArtifactId: input.request.acceptedArtifactIds[0]!,
        measurementArtifactId: input.measurementArtifactId ?? measurementId(input.request.runId),
        decisionArtifactId: input.request.decisionArtifactIds[0]!,
        reviewer: input.reviewer,
        rationale: input.rationale,
        request: input.request,
        ...(input.durableContext === undefined ? {} : { durableContext: input.durableContext }),
      });
      return {
        schemaVersion: "magazine-article-workflow-result/1",
        runId: input.request.runId,
        articleExecutionId: input.articleExecutionId,
        articleId: input.request.logicalItem.kind === "article" ? input.request.logicalItem.logicalId : "",
        status: "complete",
        manuscriptArtifactId: input.request.acceptedArtifactIds[0]!,
        ...(options.ledger.requireRun(input.request.runId).currentRevisionRecordArtifactId === undefined ? {} : { currentRevisionRecordArtifactId: options.ledger.requireRun(input.request.runId).currentRevisionRecordArtifactId }),
        measurementArtifactId: input.measurementArtifactId ?? measurementId(input.request.runId),
        decisionArtifactId: input.request.decisionArtifactIds[0]!,
        promotionId: promotion.promotionId,
        durableRevisionId: promotion.durableRevisionId,
      };
    },
  };
}

function exactCapabilities(actual: readonly string[], expected: readonly string[]): boolean {
  if (actual.length !== expected.length) return false;
  const wanted = new Set(expected);
  return actual.every((capability) => wanted.has(capability));
}

void ARTICLE_RUNTIME_GRAPH;
