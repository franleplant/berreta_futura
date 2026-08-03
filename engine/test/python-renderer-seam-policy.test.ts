import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { test } from "node:test";

test("Python is limited to the renderer subprocess closure", async () => {
  const root = resolve(import.meta.dirname, "../..");
  const pyproject = await readFile(resolve(root, "pyproject.toml"), "utf8");
  assert.match(pyproject, /^mag-render-adapter = "magazine\.engine_render_bridge:main"$/m);
  assert.doesNotMatch(pyproject, /^mag = |mag-source-adapter|pytest/m);

  const modules = (await readdir(resolve(root, "src/magazine")))
    .filter((entry) => entry.endsWith(".py"))
    .sort();
  assert.deepEqual(modules, [
    "__init__.py",
    "booklet.py",
    "concurrency.py",
    "cover.py",
    "document_structure.py",
    "engine_render_bridge.py",
    "errors.py",
    "extraction.py",
    "html_edition.py",
    "image_contrast.py",
    "io.py",
    "manifest.py",
    "media_schema.py",
    "package.py",
    "preflight.py",
    "publication_document.py",
    "reader_layout.py",
    "reader_text.py",
    "records.py",
    "render.py",
    "render_critic.py",
    "render_engine.py",
    "weasyprint_adapter.py",
    "web_edition.py",
  ]);

  const initializer = await readFile(resolve(root, "src/magazine/__init__.py"), "utf8");
  assert.doesNotMatch(initializer, /compiler|release/);
  const critic = await readFile(resolve(root, "src/magazine/render_critic.py"), "utf8");
  assert.doesNotMatch(critic, /render_review/);
});
