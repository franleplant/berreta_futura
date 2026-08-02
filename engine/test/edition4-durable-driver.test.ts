import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";

import { driveEdition4Durably } from "../fixtures/edition4-durable.ts";
import { InMemoryRendererAdapter, type RenderManifest } from "../renderer-adapter/index.ts";
import { SqliteRunEngine } from "../run-engine/index.ts";

test("Edition 4 durable driver advances the public RunEngine lifecycle", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-edition4-durable-driver-"));
  const engine = new SqliteRunEngine({
    databasePath: join(temporary, "run.sqlite"),
    artifactDirectory: join(temporary, "artifacts"),
  });
  const operations: RenderManifest["operation"][] = [];
  const adapter = new InMemoryRendererAdapter(async (requestPath, destination) => {
    const manifest = JSON.parse(await readFile(requestPath, "utf8")) as RenderManifest;
    operations.push(manifest.operation);
    const layouts = manifest.languages.map((language) => ({
      language,
      totalPages: 32,
      editorialPages: 1,
      articlePages: {},
      figureCount: 7,
      criticResult: manifest.operation === "render_edition" ? "pass" as const : "not_run" as const,
    }));
    if (manifest.operation === "render_edition") {
      for (const language of manifest.languages) {
        await mkdir(join(destination, language), { recursive: true });
        for (const [name, contents] of [
          ["reader.pdf", "%PDF fixture"],
          ["web.html", "<main>fixture</main>"],
          ["booklet.pdf", "%PDF booklet fixture"],
          ["package.zip", "fixture package"],
          ["render-critic.json", "{\"result\":\"pass\"}"],
          ["preflight.json", "{\"result\":\"pass\"}"],
        ] as const) {
          await writeFile(join(destination, language, name), contents, "utf8");
        }
      }
      return {
        schemaVersion: 1,
        rendererContractVersion: "magazine-renderer/1",
        editionId: manifest.editionId,
        files: manifest.languages.flatMap((language) => [
          { path: `${language}/reader.pdf`, mediaType: "application/pdf", kind: "reader_pdf" },
          { path: `${language}/web.html`, mediaType: "text/html", kind: "web_output" },
          { path: `${language}/booklet.pdf`, mediaType: "application/pdf", kind: "booklet_pdf" },
          { path: `${language}/package.zip`, mediaType: "application/zip", kind: "package_artifact" },
          { path: `${language}/render-critic.json`, mediaType: "application/json", kind: "render_critic_report" },
          { path: `${language}/preflight.json`, mediaType: "application/json", kind: "printer_preflight" },
        ]),
        layouts,
        inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
        tailArtFacts: {},
      };
    }
    return {
      schemaVersion: 1,
      rendererContractVersion: "magazine-renderer/1",
      editionId: manifest.editionId,
      files: [],
      layouts,
      inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
      tailArtFacts: {},
    };
  });
  try {
    const completed = await driveEdition4Durably({
      engine,
      projectRoot: resolve(import.meta.dirname, "../.."),
      stagingDirectory: join(temporary, "staged"),
      renderer: adapter,
      rendererWorkDirectory: join(temporary, "renderer-work"),
      approveVisualReview: true,
    });
    assert.equal(completed.view.status, "complete");
    assert.deepEqual(operations, ["measure_edition", "render_edition"]);
    assert.equal(
      completed.view.actors.filter((actor) => actor.machine === "source" && actor.status === "accepting").length,
      9,
    );
    assert.equal(
      completed.view.artifacts.filter((artifact) => artifact.kind === "selected_art").length,
      13,
    );
    assert.equal(completed.view.artifacts.filter((artifact) => artifact.kind === "reader_pdf").length, 2);
  } finally {
    engine.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
