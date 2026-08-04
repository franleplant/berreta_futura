import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { test } from "node:test";

import { PythonRendererAdapter } from "../renderer-adapter/index.ts";
import { inspectRendererToolchain } from "../renderer-adapter/toolchain.ts";

test("PythonRendererAdapter confines UV cache state to the caller-owned attempt", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-python-renderer-adapter-"));
  const attemptRoot = join(temporary, "attempt");
  const manifestPath = join(attemptRoot, "request.json");
  const outputRoot = join(attemptRoot, "output");
  const executableDirectory = join(temporary, "bin");
  const fakeUv = join(executableDirectory, "uv");
  const maliciousDirectory = join(temporary, "malicious-bin");
  const maliciousUv = join(maliciousDirectory, "uv");
  const priorPath = process.env.PATH;
  const priorCache = process.env.UV_CACHE_DIR;
  const priorNoSync = process.env.UV_NO_SYNC;

  try {
    await mkdir(outputRoot, { recursive: true });
    await mkdir(executableDirectory, { recursive: true });
    await mkdir(maliciousDirectory, { recursive: true });
    await writeFile(manifestPath, "{}\n", "utf8");
    await writeFile(fakeUv, `#!/usr/bin/env node
if (process.argv[2] === "--version") { process.stdout.write("uv fixture-1\\n"); process.exit(0); }
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
    await writeFile(maliciousUv, "#!/bin/sh\nprintf 'malicious PATH uv was invoked\\n' >&2\nexit 97\n", "utf8");
    await chmod(maliciousUv, 0o700);
    const fakePython = join(executableDirectory, "python");
    await writeFile(fakePython, `#!/usr/bin/env node
process.stdout.write(JSON.stringify({ pythonVersion: "3.12.11", pythonImplementation: "CPython", pythonCacheTag: "cpython-312", platform: "darwin-arm64" }));
`, "utf8");
    await chmod(fakePython, 0o700);
    const expectedToolchain = await inspectRendererToolchain(fakeUv, fakePython);
    process.env.PATH = `${maliciousDirectory}${delimiter}${priorPath ?? ""}`;
    process.env.UV_CACHE_DIR = "/forbidden/home/cache";
    process.env.UV_NO_SYNC = "0";

    const adapter = new PythonRendererAdapter(temporary, undefined, undefined, {
      uvExecutable: fakeUv,
      pythonExecutable: fakePython,
      expected: expectedToolchain,
    });
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
      "--python",
      fakePython,
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
