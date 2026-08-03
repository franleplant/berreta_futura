import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { test } from "node:test";

import { PythonRendererAdapter } from "../renderer-adapter/index.ts";

test("PythonRendererAdapter confines UV cache state to the caller-owned attempt", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-python-renderer-adapter-"));
  const attemptRoot = join(temporary, "attempt");
  const manifestPath = join(attemptRoot, "request.json");
  const outputRoot = join(attemptRoot, "output");
  const executableDirectory = join(temporary, "bin");
  const fakeUv = join(executableDirectory, "uv");
  const priorPath = process.env.PATH;
  const priorCache = process.env.UV_CACHE_DIR;
  const priorNoSync = process.env.UV_NO_SYNC;

  try {
    await mkdir(outputRoot, { recursive: true });
    await mkdir(executableDirectory, { recursive: true });
    await writeFile(manifestPath, "{}\n", "utf8");
    await writeFile(fakeUv, `#!/usr/bin/env node
const captured = {
  args: process.argv.slice(2),
  cwd: process.cwd(),
  uvCacheDirectory: process.env.UV_CACHE_DIR,
  uvNoSync: process.env.UV_NO_SYNC,
};
process.stdout.write(JSON.stringify({
  schemaVersion: 1,
  rendererContractVersion: "magazine-renderer/1",
  editionId: "fixture-edition",
  files: [],
  layouts: [],
  inputArtifactIds: [],
  tailArtFacts: { captured },
}));
`, "utf8");
    await chmod(fakeUv, 0o700);
    process.env.PATH = `${executableDirectory}${delimiter}${priorPath ?? ""}`;
    process.env.UV_CACHE_DIR = "/forbidden/home/cache";
    process.env.UV_NO_SYNC = "0";

    const adapter = new PythonRendererAdapter(temporary);
    const result = await adapter.render(
      manifestPath,
      outputRoot,
      AbortSignal.timeout(10_000),
    );
    const captured = result.tailArtFacts.captured as {
      readonly args: readonly string[];
      readonly cwd: string;
      readonly uvCacheDirectory: string;
      readonly uvNoSync: string;
    };

    assert.deepEqual(captured.args, [
      "run",
      "--locked",
      "--no-sync",
      "mag-render-adapter",
      resolve(manifestPath),
      resolve(outputRoot),
    ]);
    assert.equal(await realpath(captured.cwd), await realpath(temporary));
    assert.equal(captured.uvCacheDirectory, join(dirname(resolve(manifestPath)), "uv-cache"));
    assert.equal(captured.uvNoSync, "1");
    assert.notEqual(captured.uvCacheDirectory, "/forbidden/home/cache");
  } finally {
    if (priorPath === undefined) delete process.env.PATH;
    else process.env.PATH = priorPath;
    if (priorCache === undefined) delete process.env.UV_CACHE_DIR;
    else process.env.UV_CACHE_DIR = priorCache;
    if (priorNoSync === undefined) delete process.env.UV_NO_SYNC;
    else process.env.UV_NO_SYNC = priorNoSync;
    await rm(temporary, { recursive: true, force: true });
  }
});
