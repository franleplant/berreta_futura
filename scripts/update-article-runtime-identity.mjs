import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { computeRendererIdentity } from "../engine/workflows/renderer-identity.ts";
import { inspectRendererToolchain } from "../engine/renderer-adapter/toolchain.ts";

const projectRoot = resolve(new URL("..", import.meta.url).pathname);
const manifestPath = resolve(projectRoot, "engine/workflows/article-runtime-identity.json");
const uvExecutable = process.env.MAGAZINE_UV_EXECUTABLE;
const pythonExecutable = process.env.MAGAZINE_PYTHON_EXECUTABLE;
if (uvExecutable === undefined || pythonExecutable === undefined) {
  throw new Error("set MAGAZINE_UV_EXECUTABLE and MAGAZINE_PYTHON_EXECUTABLE to regenerate the pinned renderer identity");
}
const expected = await inspectRendererToolchain(uvExecutable, pythonExecutable);
const identity = await computeRendererIdentity(projectRoot, {
  uvExecutable,
  pythonExecutable,
  expected,
});
await writeFile(manifestPath, `${JSON.stringify(identity, null, 2)}\n`, { mode: 0o644 });
console.log(`Updated ${manifestPath}`);
