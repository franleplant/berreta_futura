import { resolve } from "node:path";

import { z } from "zod";

import { runSubprocess } from "../executors/subprocess.ts";
import type { RendererAdapter, RenderResult } from "./protocol.ts";

const resultSchema = z.object({
  schemaVersion: z.literal(1),
  rendererContractVersion: z.literal("magazine-renderer/1"),
  editionId: z.string().min(1),
  files: z.array(z.object({
    path: z.string().min(1),
    mediaType: z.string().min(1),
    kind: z.string().min(1),
  })),
  layouts: z.array(z.object({
    language: z.string().min(1),
    totalPages: z.number().int().nonnegative(),
    editorialPages: z.number().int().nonnegative(),
    articlePages: z.record(z.string(), z.number().int().nonnegative()),
    figureCount: z.number().int().nonnegative(),
    criticResult: z.enum(["pass", "fail", "not_run"]),
  })),
  inputArtifactIds: z.array(z.string()),
  tailArtFacts: z.record(z.string(), z.json()),
});

export class PythonRendererAdapter implements RendererAdapter {
  private readonly projectRoot: string;
  private readonly timeoutMs: number;

  constructor(
    projectRoot: string,
    timeoutMs = 10 * 60_000,
  ) {
    this.projectRoot = projectRoot;
    this.timeoutMs = timeoutMs;
  }

  async render(
    manifestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<RenderResult> {
    const result = await runSubprocess(
      {
        executable: "uv",
        args: [
          "run",
          "--locked",
          "mag-render-adapter",
          resolve(manifestPath),
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
      throw new Error(`renderer result violated its contract: ${parsed.error.message}`);
    }
    return parsed.data as unknown as RenderResult;
  }
}
