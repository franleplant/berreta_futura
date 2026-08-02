import type {
  ArtifactId,
  DecisionView,
  IterationView,
  JsonObject,
  RunId,
  RunView,
} from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/types.ts";

export type ArticleRunComparison = {
  readonly runId: RunId;
  readonly status: RunView["status"];
  readonly finalArtifacts: readonly ArtifactId[];
  readonly finalManuscripts: readonly {
    readonly artifactId: ArtifactId;
    readonly text: string;
  }[];
  readonly iterations: number;
  readonly revisionHistory: readonly IterationView[];
  readonly findings: readonly ArtifactId[];
  readonly decisions: readonly string[];
  readonly decisionRecords: readonly DecisionView[];
  readonly measurementArtifacts: readonly ArtifactId[];
  readonly configurationArtifacts: readonly ArtifactId[];
  readonly modelMetadata: readonly JsonObject[];
  readonly attempts: number;
  readonly latencyMs: number;
};

export type ArticleComparison = {
  readonly runs: readonly ArticleRunComparison[];
  readonly pairwiseDiffs: readonly {
    readonly leftRunId: RunId;
    readonly rightRunId: RunId;
    readonly changedLines: number;
  }[];
};

export async function compareArticleRuns(
  engine: RunEngine,
  runIds: readonly RunId[],
): Promise<ArticleComparison> {
  if (runIds.length < 2) {
    throw new Error("article comparison requires at least two runs");
  }
  const views = await Promise.all(runIds.map(async (runId) => await engine.inspect(runId)));
  const runs = await Promise.all(
    views.map(async (view): Promise<ArticleRunComparison> => {
      const root = view.actors.find((actor) => actor.parentActorId === undefined);
      const finalArtifacts = root?.outputs ?? [];
      const finalManuscripts = await Promise.all(
        finalArtifacts.map(async (artifactId) => ({
          artifactId,
          text: await engine.readText(artifactId),
        })),
      );
      const started = Date.parse(view.createdAt);
      const finished = Date.parse(view.updatedAt);
      return {
        runId: view.id,
        status: view.status,
        finalArtifacts,
        finalManuscripts,
        iterations: view.iterations.length,
        revisionHistory: view.iterations,
        findings: view.artifacts
          .filter((artifact) => artifact.kind.includes("finding"))
          .map((artifact) => artifact.id),
        decisions: view.decisions.map((decision) => decision.choice),
        decisionRecords: view.decisions,
        measurementArtifacts: view.artifacts
          .filter((artifact) => artifact.kind.includes("measurement"))
          .map((artifact) => artifact.id),
        configurationArtifacts: view.artifacts
          .filter((artifact) =>
            ["brief", "prompt", "rules", "policy"].some((token) =>
              artifact.kind.includes(token),
            ),
          )
          .map((artifact) => artifact.id),
        modelMetadata: view.artifacts
          .map((artifact) => artifact.metadata)
          .filter((metadata) =>
            ["model", "adapter", "durationMs", "cost"].some(
              (key) => metadata[key] !== undefined,
            ),
          ),
        attempts: view.attempts.length,
        latencyMs: Math.max(0, finished - started),
      };
    }),
  );
  return {
    runs,
    pairwiseDiffs: runs.flatMap((left, leftIndex) =>
      runs.slice(leftIndex + 1).map((right) => ({
        leftRunId: left.runId,
        rightRunId: right.runId,
        changedLines: changedLineCount(
          left.finalManuscripts[0]?.text ?? "",
          right.finalManuscripts[0]?.text ?? "",
        ),
      })),
    ),
  };
}

function changedLineCount(left: string, right: string): number {
  const leftLines = left.split("\n");
  const rightLines = right.split("\n");
  const length = Math.max(leftLines.length, rightLines.length);
  let changed = 0;
  for (let index = 0; index < length; index += 1) {
    if (leftLines[index] !== rightLines[index]) {
      changed += 1;
    }
  }
  return changed;
}
