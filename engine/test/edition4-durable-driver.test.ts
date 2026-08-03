import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";

import type {
  ArtifactId,
  ArtifactSeed,
  DecisionId,
  EditionRootRunSpec,
} from "../contracts/index.ts";
import { EditionRunLayout } from "../edition-run-layout.ts";
import {
  createEdition4DurableFixture,
  driveEdition4Durably,
} from "../fixtures/edition4-durable.ts";
import { InMemoryRendererAdapter, type RenderManifest } from "../renderer-adapter/index.ts";
import {
  BOOTSTRAP_FIXTURE_REF,
  committedFixtureGit,
  writeCompositionBootstrapRepositoryFixture,
} from "./composition-bootstrap-fixture.ts";

test("Edition 4 publishes only the current composition-bound approved render", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-edition4-layout-"));
  const projectRoot = resolve(import.meta.dirname, "../..");
  const repositoryRoot = join(temporary, "repository");
  const durableGit = committedFixtureGit();
  const layout = new EditionRunLayout({
    editionKey: "004",
    repositoryRoot,
    outputRoot: join(temporary, "output"),
    durableGit,
  });
  const operations: RenderManifest["operation"][] = [];
  try {
    await writeCompositionBootstrapRepositoryFixture(repositoryRoot);
    const allocated = await layout.allocate(async (scratch) => {
      const fixture = await createEdition4DurableFixture(
        projectRoot,
        scratch.stagedDirectory,
      );
      const spec = withBootstrapRenderAssembly(fixture.spec);
      return {
        ...spec,
        metadata: {
          ...spec.metadata,
          fixture: "edition4-composition-bootstrap",
          imageGenerationAllowed: false,
        },
        edition: {
          ...spec.edition,
          execution: {
            kind: "bootstrap_composition",
            bootstrapRevision: BOOTSTRAP_FIXTURE_REF,
            postRender: "stop_unreleased",
          },
        },
      };
    });
    const runId = allocated.runId;
    allocated.close();

    const completed = await layout.withScratch(runId, async (scratch) => {
      const active = await layout.open(runId);
      try {
        return await driveEdition4Durably({
          engine: active.engine,
          projectRoot,
          stagingDirectory: scratch.stagedDirectory,
          renderer: publicationRenderer(operations),
          rendererWorkDirectory: scratch.rendererWorkDirectory,
          runId,
          compositionBootstrap: {
            repositoryRoot,
            git: durableGit,
          },
          approveVisualReview: true,
        });
      } finally {
        active.close();
      }
    });
    assert.equal(completed.view.status, "complete");
    assert.deepEqual(operations, ["measure_edition", "render_edition"]);
    assert.equal(
      completed.view.offers.filter(
        (offer) => offer.role === "release_approval" && offer.status === "offered",
      ).length,
      0,
    );
    assert.equal(
      completed.view.actors.find((actor) => actor.machine === "edition")?.state,
      "bootstrap_render_approved",
    );
    const renderActor = completed.view.actors.find((actor) => actor.machine === "render");
    assert.ok(renderActor);
    const visualDecision = completed.view.decisions.find(
      (decision) => decision.artifactId === renderActor.context.visualDecisionArtifact,
    );
    assert.ok(visualDecision);
    assert.ok(visualDecision.offerId);
    await assert.rejects(
      layout.projectReview(runId, {
        expectedHeadSequence: completed.view.headSequence,
        expectedOfferId: visualDecision.offerId,
        independentCritic: {
          result: "pass",
          note: "Completed renders cannot be projected as pending review.",
        },
      }),
      { code: "RENDER_REVIEW_STATE" },
    );

    await assert.rejects(
      layout.publish(runId, {
        expectedVisualDecisionId: "decision_stale" as DecisionId,
      }),
      { code: "RENDER_EXPORT_STALE" },
    );
    await assert.rejects(access(layout.pathsFor(completed.view).publicDirectory));

    const published = await layout.publish(runId, {
      expectedVisualDecisionId: visualDecision.id as DecisionId,
    });
    assert.equal(published.visualDecisionId, visualDecision.id);
    assert.equal(published.compositionRevision.compositionId, "fresh-v2");
    assert.deepEqual(await fileTree(published.publicDirectory), expectedPublicFiles());
    assert.equal(
      (await readFile(join(published.publicDirectory, "en", "reader.pdf")))
        .subarray(0, 5).toString("ascii"),
      "%PDF-",
    );

    const manifest = JSON.parse(await readFile(published.exportManifestPath, "utf8")) as {
      readonly schemaVersion: string;
      readonly pageCounts: Readonly<Record<string, {
        readonly reader: number;
        readonly booklet: number;
        readonly bookletCover: number;
        readonly bookletInterior: number;
      }>>;
      readonly outputs: readonly {
        readonly artifactId: string;
        readonly destination: string;
        readonly digest: string;
        readonly mediaType: string;
        readonly pageCount: number | null;
      }[];
    };
    assert.equal(manifest.schemaVersion, "edition-run-export/1");
    assert.deepEqual(manifest.pageCounts, {
      en: { reader: 40, booklet: 20, bookletCover: 2, bookletInterior: 18 },
      es: { reader: 44, booklet: 22, bookletCover: 2, bookletInterior: 20 },
    });
    assert.equal(manifest.outputs.length, 156);
    assert.ok(manifest.outputs.every((output) => /^sha256:[0-9a-f]{64}$/.test(output.digest)));
    const split = manifest.outputs.filter((output) =>
      output.destination.startsWith("en/booklet-") && output.destination !== "en/booklet.pdf"
    );
    assert.deepEqual(split.map((output) => output.pageCount).sort((a, b) => (a ?? 0) - (b ?? 0)), [2, 18]);
    assert.equal(new Set(split.map((output) => output.artifactId)).size, 2);

    const firstManifest = await readFile(published.exportManifestPath);
    const repeated = await layout.publish(runId, {
      expectedVisualDecisionId: visualDecision.id as DecisionId,
    });
    assert.deepEqual(await readFile(repeated.exportManifestPath), firstManifest);
    assert.deepEqual(await fileTree(repeated.publicDirectory), expectedPublicFiles());
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("Edition 4 atomically projects the exact offered visual-review render without answering it", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-edition4-review-projection-"));
  const projectRoot = resolve(import.meta.dirname, "../..");
  const repositoryRoot = join(temporary, "repository");
  const durableGit = committedFixtureGit();
  const layout = new EditionRunLayout({
    editionKey: "004",
    repositoryRoot,
    outputRoot: join(temporary, "output"),
    durableGit,
  });
  const criticNote = "Independent visual QA passed for the exact EN/ES reader and booklet artifacts at original resolution. Human visual-review decision remains pending. Studio preflight remains blocked by missing PDF/X-4/output intent and bleed configuration, cover art below 300 ppi target, and the low-contrast attention-progression figure; this projection is not press-ready or released.";
  try {
    await writeCompositionBootstrapRepositoryFixture(repositoryRoot);
    const allocated = await layout.allocate(async (scratch) => {
      const fixture = await createEdition4DurableFixture(projectRoot, scratch.stagedDirectory);
      const spec = withBootstrapRenderAssembly(fixture.spec);
      return {
        ...spec,
        edition: {
          ...spec.edition,
          execution: {
            kind: "bootstrap_composition" as const,
            bootstrapRevision: BOOTSTRAP_FIXTURE_REF,
            postRender: "stop_unreleased" as const,
          },
        },
      };
    });
    const runId = allocated.runId;
    allocated.close();
    const waiting = await layout.withScratch(runId, async (scratch) => {
      const active = await layout.open(runId);
      try {
        return await driveEdition4Durably({
          engine: active.engine,
          projectRoot,
          stagingDirectory: scratch.stagedDirectory,
          renderer: publicationRenderer([]),
          rendererWorkDirectory: scratch.rendererWorkDirectory,
          runId,
          compositionBootstrap: { repositoryRoot, git: durableGit },
        });
      } finally {
        active.close();
      }
    });
    assert.equal(waiting.view.status, "waiting");
    const offer = waiting.view.offers.find((candidate) =>
      candidate.role === "visual_review" && candidate.status === "offered"
    );
    assert.ok(offer);
    assert.equal(offer.state, "awaiting_visual_review");
    assert.deepEqual(offer.allowedWorkerCapabilities, ["human"]);

    await assert.rejects(
      layout.projectReview(runId, {
        expectedHeadSequence: waiting.view.headSequence - 1,
        expectedOfferId: offer.id,
        independentCritic: { result: "pass", note: criticNote },
      }),
      { code: "RENDER_REVIEW_STALE" },
    );
    await assert.rejects(access(layout.pathsFor(waiting.view).publicDirectory));
    await assert.rejects(
      layout.projectReview(runId, {
        expectedHeadSequence: waiting.view.headSequence,
        expectedOfferId: "offer_stale" as typeof offer.id,
        independentCritic: { result: "pass", note: criticNote },
      }),
      { code: "RENDER_REVIEW_STALE" },
    );

    const projected = await layout.projectReview(runId, {
      expectedHeadSequence: waiting.view.headSequence,
      expectedOfferId: offer.id,
      independentCritic: { result: "pass", note: criticNote },
    });
    assert.equal(projected.headSequence, waiting.view.headSequence);
    assert.equal(projected.offerId, offer.id);
    assert.equal(projected.physicalFileCount, 169);
    assert.deepEqual(await fileTree(projected.publicDirectory), expectedReviewProjectionFiles());
    const after = await layout.open(runId);
    try {
      const unchanged = await after.engine.inspect(runId);
      assert.equal(unchanged.headSequence, waiting.view.headSequence);
      assert.equal(
        unchanged.offers.find((candidate) => candidate.id === offer.id)?.status,
        "offered",
      );
      assert.equal(unchanged.decisions.some((decision) => decision.offerId === offer.id), false);
    } finally {
      after.close();
    }

    const manifest = JSON.parse(await readFile(projected.exportManifestPath, "utf8")) as {
      readonly schemaVersion: string;
      readonly status: string;
      readonly authority: string;
      readonly headSequence: number;
      readonly offerId: string;
      readonly renderArtifactIds: readonly string[];
      readonly renderArtifactSetDigest: string;
      readonly independentCritic: { readonly result: string; readonly note: string };
      readonly stateMachineTopology: {
        readonly schemaVersion: string;
        readonly source: string;
        readonly directory: string;
        readonly fileCount: number;
      };
      readonly physicalFileCount: number;
      readonly pageCounts: Readonly<Record<string, unknown>>;
      readonly outputs: readonly {
        readonly artifactId: string;
        readonly destination: string;
        readonly digest: string;
        readonly mediaType: string;
        readonly pageCount: number | null;
      }[];
      readonly auxiliaryOutputs: readonly {
        readonly destination: string;
        readonly digest: string;
        readonly mediaType: string;
        readonly sizeBytes: number;
      }[];
      readonly visualDecisionArtifactId: null;
      readonly released: boolean;
      readonly pressReady: boolean;
    };
    assert.equal(manifest.schemaVersion, "edition-run-review-projection/1");
    assert.equal(manifest.status, "awaiting_visual_review");
    assert.equal(manifest.authority, "non_authoritative_review_projection");
    assert.equal(manifest.headSequence, waiting.view.headSequence);
    assert.equal(manifest.offerId, offer.id);
    assert.deepEqual(manifest.renderArtifactIds, projected.renderArtifactIds);
    assert.equal(manifest.renderArtifactIds.length, 156);
    assert.match(manifest.renderArtifactSetDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.deepEqual(manifest.independentCritic, { result: "pass", note: criticNote });
    assert.equal(manifest.visualDecisionArtifactId, null);
    assert.equal(manifest.released, false);
    assert.equal(manifest.pressReady, false);
    assert.equal(manifest.physicalFileCount, 169);
    assert.equal(manifest.outputs.length, 156);
    assert.ok(manifest.outputs.every((output) => /^sha256:[0-9a-f]{64}$/u.test(output.digest)));
    assert.equal(new Set(manifest.outputs.map((output) => output.artifactId)).size, 156);
    assert.deepEqual(manifest.stateMachineTopology, {
      schemaVersion: "state-machine-topology-projection/1",
      source: "live_xstate_configs_and_runtime_orchestration_declarations",
      directory: "state-machine",
      fileCount: 8,
    });
    assert.deepEqual(
      manifest.auxiliaryOutputs.map((output) => output.destination),
      stateMachineFiles(),
    );
    for (const output of manifest.auxiliaryOutputs) {
      const bytes = await readFile(join(projected.publicDirectory, output.destination));
      assert.equal(output.sizeBytes, bytes.byteLength);
      assert.equal(
        output.digest,
        `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
      );
    }
    for (const name of ["machine-topology.png", "magazine-orchestration.png"]) {
      assert.deepEqual(
        [...(await readFile(join(projected.publicDirectory, "state-machine", name))).subarray(0, 8)],
        [137, 80, 78, 71, 13, 10, 26, 10],
      );
    }
    assert.deepEqual(manifest.pageCounts, {
      en: { reader: 40, booklet: 20, bookletCover: 2, bookletInterior: 18 },
      es: { reader: 44, booklet: 22, bookletCover: 2, bookletInterior: 20 },
    });
    assert.deepEqual(
      manifest.outputs
        .filter((output) => output.mediaType === "application/pdf")
        .map((output) => [output.destination, output.pageCount]),
      [
        ["en/booklet-cover.pdf", 2],
        ["en/booklet-interior.pdf", 18],
        ["en/booklet.pdf", 20],
        ["en/reader.pdf", 40],
        ["es/booklet-cover.pdf", 2],
        ["es/booklet-interior.pdf", 20],
        ["es/booklet.pdf", 22],
        ["es/reader.pdf", 44],
      ],
    );
    const firstManifest = await readFile(projected.exportManifestPath);
    const repeated = await layout.projectReview(runId, {
      expectedHeadSequence: waiting.view.headSequence,
      expectedOfferId: offer.id,
      independentCritic: { result: "pass", note: criticNote },
    });
    assert.deepEqual(await readFile(repeated.exportManifestPath), firstManifest);
    assert.deepEqual(await fileTree(repeated.publicDirectory), expectedReviewProjectionFiles());
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

function withBootstrapRenderAssembly(spec: EditionRootRunSpec): EditionRootRunSpec {
  const renderAssemblyId = "edition4-bootstrap-render-assembly" as ArtifactId;
  const content = spec.artifacts
    .filter((artifact) => ["article_manuscript", "editorial_manuscript"].includes(artifact.kind))
    .map((artifact) => artifact.id);
  const translations = spec.artifacts
    .filter((artifact) => artifact.kind === "translation_bundle")
    .map((artifact) => artifact.id);
  const art = spec.artifacts
    .filter((artifact) => artifact.kind === "selected_art")
    .map((artifact) => artifact.id);
  const renderProfileArtifactId = spec.edition.render.renderManifestArtifact;
  const printerProfileArtifactId = spec.edition.render.printerProfileArtifact ?? null;
  const assembly = {
    editionId: spec.edition.editionId,
    content,
    translations,
    translationProofs: [],
    art,
    editionApproval: [],
    configuredLanguages: spec.edition.render.configuredLanguages,
    renderProfileArtifactId,
    printerProfileArtifactId,
  };
  const renderAssembly: ArtifactSeed = {
    id: renderAssemblyId,
    kind: "render_manifest",
    schemaVersion: "render-assembly/1",
    mediaType: "application/json",
    origin: "imported",
    payload: { kind: "json", value: assembly },
    parents: [
      ...content.map((artifactId) => ({ artifactId, relation: "content" })),
      ...translations.map((artifactId) => ({ artifactId, relation: "translation" })),
      ...art.map((artifactId) => ({ artifactId, relation: "selected_art" })),
      { artifactId: renderProfileArtifactId, relation: "render_profile" },
      ...(printerProfileArtifactId === null
        ? []
        : [{ artifactId: printerProfileArtifactId, relation: "printer_profile" }]),
    ],
  };
  return {
    ...spec,
    artifacts: [...spec.artifacts, renderAssembly],
    edition: {
      ...spec.edition,
      render: {
        ...spec.edition.render,
        renderManifestArtifact: renderAssemblyId,
      },
    },
  };
}

function publicationRenderer(
  operations: RenderManifest["operation"][],
): InMemoryRendererAdapter {
  return new InMemoryRendererAdapter(async (requestPath, destination) => {
    const manifest = JSON.parse(await readFile(requestPath, "utf8")) as RenderManifest;
    operations.push(manifest.operation);
    const layouts = manifest.languages.map((language) => ({
      language,
      totalPages: language === "en" ? 40 : 44,
      editorialPages: 1,
      articlePages: {},
      figureCount: 7,
      criticResult: manifest.operation === "render_edition" ? "pass" as const : "not_run" as const,
    }));
    if (manifest.operation !== "render_edition") {
      return {
        schemaVersion: 1,
        rendererContractVersion: "magazine-renderer/1",
        editionId: manifest.editionId,
        files: [],
        layouts,
        inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
        tailArtFacts: {},
      };
    }

    const files: Array<{
      readonly path: string;
      readonly mediaType: string;
      readonly kind: string;
      readonly bytes: Uint8Array;
    }> = [];
    for (const language of manifest.languages) {
      const counts = language === "en"
        ? { reader: 40, booklet: 20, cover: 2, interior: 18 }
        : { reader: 44, booklet: 22, cover: 2, interior: 20 };
      files.push(
        renderFile(`${language}/reader.pdf`, "application/pdf", "reader_pdf", pdf(counts.reader)),
        renderFile(`${language}/home/booklet-a4.pdf`, "application/pdf", "booklet_pdf", pdf(counts.booklet)),
        renderFile(`${language}/home/booklet-a4-cover.pdf`, "application/pdf", "render_pdf", pdf(counts.cover)),
        renderFile(`${language}/home/booklet-a4-interior.pdf`, "application/pdf", "render_pdf", pdf(counts.interior)),
        renderFile(`${language}/web-output.zip`, "application/zip", "web_output", storedZip([
          ["index.html", `<main lang="${language}">fixture</main>`],
          ["edition.css", "body{}\n"],
        ])),
        renderFile(`${language}/package.zip`, "application/zip", "package_artifact", storedZip([
          ["README.txt", "fixture package"],
        ])),
        renderFile(`${language}/render-critic.json`, "application/json", "render_critic_report", json({ result: "pass" })),
        renderFile(`${language}/preflight.json`, "application/json", "printer_preflight", json({
          result: "home_ready_studio_blocked",
          reader: { page_count: counts.reader },
          home_booklet: { sheet_sides: counts.booklet },
          home_booklet_cover: { sheet_sides: counts.cover },
          home_booklet_interior: { sheet_sides: counts.interior },
        })),
      );
      for (const [series, count] of [
        ["reader-contact-sheet", Math.ceil(counts.reader / 16)],
        ["booklet-contact-sheet", Math.ceil(counts.booklet / 16)],
      ] as const) {
        for (let page = 1; page <= count; page += 1) {
          files.push(renderFile(
            `${language}/render-review/${series}-${String(page).padStart(2, "0")}.png`,
            "image/png",
            "render_review_image",
            png(),
          ));
        }
      }
      for (const [series, count] of [
        ["reader-pages", counts.reader],
        ["booklet-sides", counts.booklet],
        ["cover-booklet-sides", counts.cover],
      ] as const) {
        for (let page = 1; page <= count; page += 1) {
          files.push(renderFile(
            `${language}/render-review/${series}/page-${String(page).padStart(3, "0")}.png`,
            "image/png",
            "render_review_image",
            png(),
          ));
        }
      }
    }
    for (const file of files) {
      const path = join(destination, file.path);
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, file.bytes);
    }
    return {
      schemaVersion: 1,
      rendererContractVersion: "magazine-renderer/1",
      editionId: manifest.editionId,
      files: files.map(({ path, mediaType, kind }) => ({ path, mediaType, kind })),
      layouts,
      inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
      tailArtFacts: {},
    };
  });
}

function renderFile(
  path: string,
  mediaType: string,
  kind: string,
  bytes: Uint8Array,
) {
  return { path, mediaType, kind, bytes } as const;
}

function pdf(pageCount: number): Buffer {
  const chunks = [Buffer.from("%PDF-1.4\n", "ascii")];
  const offsets = [0];
  let length = chunks[0]!.length;
  const addObject = (ordinal: number, body: string): void => {
    offsets[ordinal] = length;
    const chunk = Buffer.from(`${ordinal} 0 obj\n${body}\nendobj\n`, "ascii");
    chunks.push(chunk);
    length += chunk.length;
  };
  addObject(1, "<< /Type /Catalog /Pages 2 0 R >>");
  addObject(
    2,
    `<< /Type /Pages /Kids [${[...Array(pageCount)].map((_, index) => `${index + 3} 0 R`).join(" ")}] /Count ${pageCount} >>`,
  );
  for (let index = 0; index < pageCount; index += 1) {
    addObject(index + 3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] >>");
  }
  const xrefOffset = length;
  const objectCount = pageCount + 2;
  const xref = [
    `xref\n0 ${objectCount + 1}\n`,
    "0000000000 65535 f \n",
    ...offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`),
    `trailer\n<< /Size ${objectCount + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`,
  ].join("");
  return Buffer.concat([...chunks, Buffer.from(xref, "ascii")]);
}

function png(): Buffer {
  return Buffer.from("89504e470d0a1a0a00000000", "hex");
}

function json(value: unknown): Buffer {
  return Buffer.from(`${JSON.stringify(value)}\n`, "utf8");
}

async function fileTree(root: string): Promise<readonly string[]> {
  const result: string[] = [];
  const visit = async (directory: string, prefix: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        await visit(join(directory, entry.name), relative);
      } else {
        result.push(relative);
      }
    }
  };
  await visit(root, "");
  return result.sort();
}

function expectedPublicFiles(): readonly string[] {
  const counts = {
    en: { reader: 40, booklet: 20, cover: 2 },
    es: { reader: 44, booklet: 22, cover: 2 },
  } as const;
  return [
    "export.json",
    ...(["en", "es"] as const).flatMap((language) => {
      const pageCounts = counts[language];
      return [
        `${language}/booklet-cover.pdf`,
        `${language}/booklet-interior.pdf`,
        `${language}/booklet.pdf`,
        `${language}/package.zip`,
        ...[...Array(Math.ceil(pageCounts.reader / 16))].map((_, index) =>
          `${language}/qa/contact-sheets/reader-contact-sheet-${String(index + 1).padStart(2, "0")}.png`
        ),
        ...[...Array(Math.ceil(pageCounts.booklet / 16))].map((_, index) =>
          `${language}/qa/contact-sheets/booklet-contact-sheet-${String(index + 1).padStart(2, "0")}.png`
        ),
        ...[...Array(pageCounts.reader)].map((_, index) =>
          `${language}/qa/pages/reader-pages/page-${String(index + 1).padStart(3, "0")}.png`
        ),
        ...[...Array(pageCounts.booklet)].map((_, index) =>
          `${language}/qa/pages/booklet-sides/page-${String(index + 1).padStart(3, "0")}.png`
        ),
        ...[...Array(pageCounts.cover)].map((_, index) =>
          `${language}/qa/pages/cover-booklet-sides/page-${String(index + 1).padStart(3, "0")}.png`
        ),
        `${language}/qa/preflight.json`,
        `${language}/qa/render-critic.json`,
        `${language}/reader.pdf`,
        `${language}/web.zip`,
        `${language}/web/edition.css`,
        `${language}/web/index.html`,
      ];
    }),
  ].sort();
}

function stateMachineFiles(): readonly string[] {
  return [
    "state-machine/machine-topology.html",
    "state-machine/machine-topology.svg",
    "state-machine/machine-topology.png",
    "state-machine/machine-topology.json",
    "state-machine/magazine-orchestration.html",
    "state-machine/magazine-orchestration.svg",
    "state-machine/magazine-orchestration.png",
    "state-machine/magazine-orchestration.json",
  ];
}

function expectedReviewProjectionFiles(): readonly string[] {
  return [...expectedPublicFiles(), ...stateMachineFiles()].sort();
}

function storedZip(entries: readonly (readonly [string, string])[]): Buffer {
  const locals: Buffer[] = [];
  const central: Buffer[] = [];
  let offset = 0;
  for (const [name, text] of entries) {
    const filename = Buffer.from(name, "utf8");
    const bytes = Buffer.from(text, "utf8");
    const crc = crc32(bytes);
    const local = Buffer.alloc(30 + filename.length + bytes.length);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(bytes.length, 18);
    local.writeUInt32LE(bytes.length, 22);
    local.writeUInt16LE(filename.length, 26);
    filename.copy(local, 30);
    bytes.copy(local, 30 + filename.length);
    locals.push(local);

    const header = Buffer.alloc(46 + filename.length);
    header.writeUInt32LE(0x02014b50, 0);
    header.writeUInt16LE(20, 4);
    header.writeUInt16LE(20, 6);
    header.writeUInt32LE(crc, 16);
    header.writeUInt32LE(bytes.length, 20);
    header.writeUInt32LE(bytes.length, 24);
    header.writeUInt16LE(filename.length, 28);
    header.writeUInt32LE(offset, 42);
    filename.copy(header, 46);
    central.push(header);
    offset += local.length;
  }
  const directory = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(directory.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, directory, end]);
}

function crc32(bytes: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
