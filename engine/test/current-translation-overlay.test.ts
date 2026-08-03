import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  materializeCurrentTranslationOverlays,
  materializeReducedMeasurementEdition,
} from "../executors/renderer.ts";

test("renderer stages a Spanish overlay with hashes from exact current English inputs", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-current-es-overlay-"));
  try {
    const template = join(root, "template.yaml");
    const editorial = join(root, "editorial.md");
    const article = join(root, "article.md");
    await writeFile(template, [
      "language: es",
      "editorial:",
      "  path: manuscript/editorial.md",
      "  source_sha256: stale",
      "articles:",
      "  - id: one",
      "    manuscript: articles/one.md",
      "    source_sha256: stale",
      "",
    ].join("\n"));
    await writeFile(editorial, "fresh editorial\n");
    await writeFile(article, "fresh article\n");
    const inputs = await materializeCurrentTranslationOverlays([
      {
        artifactId: "art_template" as never,
        sourcePath: template,
        targetPath: "editions/004-the-systems-around-the-model/translations/es/edition.template.yaml",
      },
      {
        artifactId: "art_current_editorial" as never,
        sourcePath: editorial,
        targetPath: "editions/004-the-systems-around-the-model/manuscript/editorial.md",
      },
      {
        artifactId: "art_current_article" as never,
        sourcePath: article,
        targetPath: "editions/004-the-systems-around-the-model/articles/one.md",
      },
    ], root);
    const active = inputs.find((input) => input.artifactId === "art_template");
    assert.ok(active);
    assert.equal(active.targetPath, "editions/004-the-systems-around-the-model/translations/es/edition.yaml");
    const overlay = JSON.parse(await readFile(active.sourcePath, "utf8")) as {
      editorial: { source_sha256: string };
      articles: Array<{ source_sha256: string }>;
    };
    assert.match(overlay.editorial.source_sha256, /^[0-9a-f]{64}$/u);
    assert.match(overlay.articles[0]!.source_sha256, /^[0-9a-f]{64}$/u);
    assert.notEqual(overlay.editorial.source_sha256, overlay.articles[0]!.source_sha256);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("isolated measurement stages a one-piece manifest without historical manuscripts", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-reduced-measurement-"));
  try {
    const edition = join(root, "edition.yaml");
    await writeFile(edition, JSON.stringify({
      id: "004-the-systems-around-the-model",
      language: "en",
      sources: ["one", "two"],
      editorial: "manuscript/editorial.md",
      closing_plates: [{ title: "old" }],
      articles: [
        { id: "one", source_ids: ["one"], manuscript: "editions/004-the-systems-around-the-model/articles/one.md" },
        { id: "two", source_ids: ["two"], manuscript: "editions/004-the-systems-around-the-model/articles/two.md" },
      ],
    }));
    const inputs = await materializeReducedMeasurementEdition([{
      artifactId: "art_edition" as never,
      sourcePath: edition,
      targetPath: "editions/004-the-systems-around-the-model/edition.yaml",
    }], root, "one", "en");
    const reduced = JSON.parse(await readFile(inputs[0]!.sourcePath, "utf8")) as {
      articles: Array<{ id: string }>;
      sources: string[];
      editorial: null;
      closing_plates: unknown[];
    };
    assert.deepEqual(reduced.articles.map((article) => article.id), ["one"]);
    assert.deepEqual(reduced.sources, ["one"]);
    assert.equal(reduced.editorial, null);
    assert.deepEqual(reduced.closing_plates, []);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
