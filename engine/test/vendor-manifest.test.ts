import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

test("vendored Loops metadata does not record an absolute source checkout path", async () => {
  const manifestPath = resolve(process.cwd(), "vendor/loops/44ffb8370eeb0ee85ba799dff6dbaa0b8e744b40/manifest.json");
  const text = await readFile(manifestPath, "utf8");
  const manifest = JSON.parse(text) as { readonly source?: Record<string, unknown> };
  assert.equal(manifest.source?.path, undefined);
  assert.doesNotMatch(text, /\/(?:Users|home|private)\//u);
});
