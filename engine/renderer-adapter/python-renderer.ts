import { dirname, join, resolve } from "node:path";
import { readFile } from "node:fs/promises";

import { z } from "zod";

import { SubprocessExecutionError, runSubprocess } from "../executors/subprocess.ts";
import type { RendererAdapter, RenderResult } from "./protocol.ts";
import {
  assertRendererIdentity,
  type RendererIdentity,
} from "../workflows/renderer-identity.ts";
import {
  assertToolchainIdentity,
  probeRendererToolchain,
} from "./toolchain.ts";
import type { RendererToolchainResource } from "../contracts/workflow-run.ts";

export type RendererIdentityProvider =
  | RendererIdentity
  | (() => RendererIdentity | Promise<RendererIdentity>);

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
    articleOpenerFits: z.record(z.string(), z.boolean()).optional(),
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
    rendererIdentity?: RendererIdentityProvider,
    toolchain?: RendererToolchainResource,
  ) {
    this.projectRoot = projectRoot;
    this.timeoutMs = timeoutMs;
    this.rendererIdentity = rendererIdentity;
    this.toolchain = toolchain;
  }

  private readonly rendererIdentity: RendererIdentityProvider | undefined;
  private readonly toolchain: RendererToolchainResource | undefined;

  async render(
    manifestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<RenderResult> {
    const resolvedManifestPath = resolve(manifestPath);
    const uvCacheDirectory = join(dirname(resolvedManifestPath), "uv-cache");
    const toolchainIdentity = await this.verifyRendererIdentity(resolvedManifestPath);
    const toolchain = this.toolchain;
    if (toolchain === undefined) {
      throw new Error("PythonRendererAdapter requires an explicit renderer toolchain resource");
    }
    let result;
    try {
      result = await runSubprocess(
        {
          executable: toolchain.uvExecutable,
          args: [
            "run",
            "--python",
            toolchain.pythonExecutable,
            "--locked",
            "--no-sync",
            "mag-render-adapter",
            resolvedManifestPath,
            resolve(destination),
          ],
          cwd: this.projectRoot,
          env: {
            UV_CACHE_DIR: uvCacheDirectory,
            UV_NO_SYNC: "1",
            PYTHONDONTWRITEBYTECODE: "1",
          },
          timeoutMs: this.timeoutMs,
          stdin: "",
        },
        signal,
      );
    } catch (error) {
      if (error instanceof SubprocessExecutionError && error.stderr.trim()) {
        throw new SubprocessExecutionError(
          `${error.message}: ${error.stderr.trim()}`,
          error.classification,
          error.exitCode,
          error.stderr,
        );
      }
      throw error;
    }
    void toolchainIdentity;
    const parsed = resultSchema.safeParse(JSON.parse(result.stdout));
    if (!parsed.success) {
      throw new Error(`renderer result violated its contract: ${parsed.error.message}`);
    }
    return parsed.data as unknown as RenderResult;
  }

  /** Recheck the pinned renderer closure after the request is materialized. */
  private async verifyRendererIdentity(manifestPath: string): Promise<RendererIdentity["toolchain"]> {
    const toolchain = this.toolchain;
    if (toolchain === undefined) {
      throw new Error("PythonRendererAdapter requires an explicit renderer toolchain resource");
    }
    const actualToolchain = await probeRendererToolchain(toolchain);
    if (this.rendererIdentity === undefined) return actualToolchain;
    const expected = typeof this.rendererIdentity === "function"
      ? await this.rendererIdentity()
      : this.rendererIdentity;
    const request = JSON.parse(await readFile(manifestPath, "utf8")) as {
      readonly metadata?: { readonly rendererIdentity?: unknown };
    };
    if (request.metadata?.rendererIdentity === undefined) {
      throw new Error("renderer request does not carry its pinned renderer identity");
    }
    const actual = request.metadata.rendererIdentity as RendererIdentity;
    assertRendererIdentity(expected, actual, "renderer request identity");
    if (expected.toolchain === undefined || actualToolchain === undefined) {
      throw new Error("renderer request does not carry its pinned toolchain identity");
    }
    assertToolchainIdentity(expected.toolchain, actualToolchain);
    return actualToolchain;
  }
}
