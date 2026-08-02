import { resolve } from "node:path";

import { z } from "zod";

import { runSubprocess } from "../executors/subprocess.ts";
import type { SourceAdapter, SourceResult } from "./protocol.ts";

const resultSchema = z.object({
  schemaVersion: z.literal(1),
  sourceContractVersion: z.literal("magazine-source/1"),
  sourceId: z.string().min(1),
  files: z.array(z.object({ path: z.string().min(1), kind: z.string().min(1) })),
  inputArtifactIds: z.array(z.string()),
});

export class PythonSourceAdapter implements SourceAdapter {
  private readonly projectRoot: string;
  private readonly timeoutMs: number;

  constructor(
    projectRoot: string,
    timeoutMs = 2 * 60_000,
  ) {
    this.projectRoot = projectRoot;
    this.timeoutMs = timeoutMs;
  }

  async archive(
    requestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<SourceResult> {
    const result = await runSubprocess(
      {
        executable: "uv",
        args: [
          "run",
          "--locked",
          "mag-source-adapter",
          resolve(requestPath),
          resolve(destination),
        ],
        cwd: this.projectRoot,
        timeoutMs: this.timeoutMs,
        stdin: "",
      },
      signal,
    );
    const parsed = resultSchema.safeParse(JSON.parse(result.stdout));
    if (!parsed.success) {
      throw new Error(`source result violated its contract: ${parsed.error.message}`);
    }
    return parsed.data as unknown as SourceResult;
  }
}
