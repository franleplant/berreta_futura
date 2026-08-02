import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { PythonRendererAdapter } from "./renderer-adapter/index.ts";
import { SqliteRunEngine } from "./run-engine/index.ts";
import { driveEdition4Durably } from "./fixtures/edition4-durable.ts";

const outputRoot = resolve(process.argv[2] ?? "runs/edition4-durable");
const runId = process.argv[3] as import("./contracts/index.ts").RunId | undefined;
const projectRoot = resolve(import.meta.dirname, "..");
await mkdir(outputRoot, { recursive: true });
const engine = new SqliteRunEngine({
  databasePath: join(outputRoot, "run.sqlite"),
  artifactDirectory: join(outputRoot, "artifacts"),
});
try {
  const completed = await driveEdition4Durably({
    engine,
    projectRoot,
    stagingDirectory: join(outputRoot, "staged"),
    renderer: new PythonRendererAdapter(projectRoot),
    rendererWorkDirectory: join(outputRoot, "renderer-work"),
    ...(runId === undefined ? {} : { runId }),
    onRunStarted: async (startedRunId) => {
      await writeFile(
        join(outputRoot, "run.json"),
        `${JSON.stringify({ runId: startedRunId })}\n`,
        "utf8",
      );
    },
  });
  process.stdout.write(`${JSON.stringify({ runId: completed.runId, status: completed.view.status })}\n`);
} finally {
  engine.close();
}
