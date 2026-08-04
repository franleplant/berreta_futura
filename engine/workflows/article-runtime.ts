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

/** Included in the fixed Loops source graph. */
export const ARTICLE_RUNTIME_GRAPH = "magazine-article-runtime/1" as const;

export function createArticleWorkflowPorts(options: {
  readonly ledger: ArtifactLedger;
  readonly repositoryRoot: string;
  readonly workRoot: string;
  readonly renderer: NonNullable<MagazineWorkflowEngineOptions["renderer"]>;
  readonly projectRoot: string;
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
  return {
    ledger: options.ledger,
    measureArticle: async (input): Promise<ArticleMeasurement> => {
      const result = await measureArticle({
        adapter,
        artifacts: {
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
    requireDecision: (artifactId) => {
      const artifact = options.ledger.requireArtifact(artifactId);
      const runId = artifact.producingRunId;
      if (runId === undefined) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${artifactId} has no producing run`);
      const decision = options.ledger.requireDecisionForRun(runId);
      if (decision.artifactId !== artifactId) throw new ArtifactLedgerError("DECISION_NOT_FOUND", `Decision artifact ${artifactId} is not current`);
      return decision;
    },
    promote: async (input): Promise<ArticleWorkflowResult> => {
      const promotion = await promotions.promote({
        runId: input.request.runId,
        articleId: input.request.logicalItem.kind === "article" ? input.request.logicalItem.logicalId : "",
        manuscriptArtifactId: input.request.acceptedArtifactIds[0]!,
        measurementArtifactId: measurementId(input.request.runId),
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
        measurementArtifactId: measurementId(input.request.runId),
        decisionArtifactId: input.request.decisionArtifactIds[0]!,
        promotionId: promotion.promotionId,
        durableRevisionId: promotion.durableRevisionId,
      };
    },
  };
}

void ARTICLE_RUNTIME_GRAPH;
