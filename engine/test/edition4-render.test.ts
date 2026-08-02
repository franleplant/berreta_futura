import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

import { stageEdition4Fixture } from "../fixtures/edition4.ts";
import { PythonRendererAdapter } from "../renderer-adapter/index.ts";

const EXPECTED_ARTICLE_PAGES = {
  en: {
    "frontier-lab-agent-intrusion": 5,
    "eval-engineering": 6,
    "pragmatic-leverage": 4,
    "from-gpt2-to-kimi3": 6,
    "factory-systems-problem": 2,
    "mcp-in-a-nutshell": 5,
    "mcp-protocol-update": 5,
  },
  es: {
    "frontier-lab-agent-intrusion": 6,
    "eval-engineering": 6,
    "pragmatic-leverage": 4,
    "from-gpt2-to-kimi3": 6,
    "factory-systems-problem": 2,
    "mcp-in-a-nutshell": 5,
    "mcp-protocol-update": 6,
  },
} as const;

test(
  "released edition 4 renders through the immutable bridge without image generation",
  { timeout: 30 * 60_000 },
  async () => {
    const projectRoot = resolve(import.meta.dirname, "../..");
    const temporary = await mkdtemp(join(tmpdir(), "mag-edition4-engine-"));
    try {
      const artifactRoot = join(temporary, "artifacts");
      const fixture = await stageEdition4Fixture(projectRoot, artifactRoot);
      assert.equal(fixture.selectedArtArtifactIds.length, 13);
      assert.equal(fixture.sourceFigureArtifactIds.length, 7);
      assert.equal(
        fixture.entries.filter((entry) => entry.kind === "selected_art").length,
        13,
      );
      assert.equal(
        fixture.entries.some((entry) =>
          entry.target.includes("prototypes/") ||
          (entry.target.includes("cover-candidate-") &&
            !entry.target.endsWith("cover-candidate-wildcard-v2.png"))),
        false,
      );

      const manifestPath = join(temporary, "render-manifest.json");
      await writeFile(manifestPath, JSON.stringify(fixture.manifest), "utf8");
      const adapter = new PythonRendererAdapter(projectRoot);
      const first = join(temporary, "first");
      const second = join(temporary, "second");
      const firstResult = await adapter.render(manifestPath, first, AbortSignal.timeout(14 * 60_000));
      const secondResult = await adapter.render(manifestPath, second, AbortSignal.timeout(14 * 60_000));

      assert.deepEqual(firstResult.layouts, secondResult.layouts);
      assert.deepEqual(firstResult.layouts.map((layout) => layout.language), ["en", "es"]);
      for (const layout of firstResult.layouts) {
        assert.equal(layout.totalPages, layout.language === "en" ? 40 : 44);
        assert.equal(layout.editorialPages, 1);
        assert.equal(layout.figureCount, 7);
        assert.equal(layout.criticResult, "pass");
        assert.deepEqual(
          layout.articlePages,
          EXPECTED_ARTICLE_PAGES[layout.language as "en" | "es"],
        );
      }

      for (const language of ["en", "es"] as const) {
        assert.equal(
          firstResult.files.filter(
            (file) => file.kind === "reader_pdf" && file.path === `${language}/reader.pdf`,
          ).length,
          1,
        );
        assert.equal(
          firstResult.files.filter(
            (file) => file.kind === "booklet_pdf" && file.path === `${language}/home/booklet-a4.pdf`,
          ).length,
          1,
        );
        assert.equal(
          firstResult.files.filter(
            (file) => file.kind === "web_output" && file.path === `${language}/web-output.zip`,
          ).length,
          1,
        );
        assert.equal(
          firstResult.files.filter(
            (file) => file.kind === "package_artifact" && file.path === `${language}/package.zip`,
          ).length,
          1,
        );
        assert.equal(
          firstResult.files.filter(
            (file) =>
              file.kind === "render_critic_report" &&
              file.path === `${language}/render-critic.json`,
          ).length,
          1,
        );
        assert.equal(
          firstResult.files.filter(
            (file) =>
              file.kind === "printer_preflight" &&
              file.path === `${language}/preflight.json`,
          ).length,
          1,
        );
        const critic = JSON.parse(
          await readFile(join(first, language, "render-critic.json"), "utf8"),
        ) as { result: string; visual_review?: { status?: string } };
        assert.equal(critic.result, "pass");
        assert.notEqual(critic.visual_review?.status, "approved");
        const packagedManifest = await readFile(
          join(first, language, "edition-manifest.json"),
          "utf8",
        );
        assert.equal(packagedManifest.includes(projectRoot), false);
        assert.equal(packagedManifest.includes(artifactRoot), false);
        assert.equal(
          (await readFile(join(first, language, "web", "index.html"), "utf8")).includes("<html"),
          true,
        );
      }

      assert.equal(
        firstResult.files.some((file) => file.path.includes("image-generation")),
        false,
      );
      assert.deepEqual(firstResult.inputArtifactIds, fixture.entries.map((entry) => entry.artifactId));
    } finally {
      await rm(temporary, { recursive: true, force: true });
    }
  },
);
