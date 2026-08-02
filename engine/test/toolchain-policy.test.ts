import { access, readFile } from "node:fs/promises";
import { constants } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

test("the XState engine toolchain is exactly pinned", async () => {
  const root = resolve(import.meta.dirname, "../..");
  const packageJson = JSON.parse(
    await readFile(resolve(root, "package.json"), "utf8"),
  ) as {
    readonly engines: Readonly<Record<string, string>>;
    readonly dependencies: Readonly<Record<string, string>>;
    readonly devDependencies: Readonly<Record<string, string>>;
  };

  await access(resolve(root, "package-lock.json"), constants.R_OK);
  assert.equal(
    (await readFile(resolve(root, ".node-version"), "utf8")).trim(),
    "24.11.1",
  );
  assert.equal(packageJson.engines.node, "24.11.1");
  assert.equal(packageJson.dependencies.xstate, "5.32.5");
  assert.equal(packageJson.devDependencies.typescript, "7.0.2");
  for (const versions of [
    packageJson.dependencies,
    packageJson.devDependencies,
  ]) {
    assert.equal(
      Object.values(versions).some((version) => /^[~^<>]/.test(version)),
      false,
    );
  }
});
