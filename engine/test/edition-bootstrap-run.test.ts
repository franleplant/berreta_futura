import assert from "node:assert/strict";
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type { ArtifactId } from "../contracts/index.ts";
import { EditionBootstrapRunner } from "../edition-bootstrap-run.ts";
import { SubprocessExecutionError } from "../executors/index.ts";
import {
  InMemoryRendererAdapter,
  RENDERER_CONTRACT_VERSION,
  type RenderManifest,
  type RenderResult,
  type RenderedFile,
} from "../renderer-adapter/index.ts";
import { EditionRunLayout } from "../edition-run-layout.ts";
import { writeBootstrapRepositoryFixture } from "./bootstrap-repository-fixture.ts";

test("bootstrap run is idempotent, executes configured work, and stops at exact visual review", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-bootstrap-run-"));
  const outputRoot = join(root, "output");
  const operations: RenderManifest["operation"][] = [];
  try {
    const fixture = await writeBootstrapRepositoryFixture(root);
    const renderer = new InMemoryRendererAdapter(async (manifestPath, destination) => {
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as RenderManifest;
      operations.push(manifest.operation);
      return await renderFixture(manifest, destination);
    });
    const runner = new EditionBootstrapRunner({
      editionKey: "004",
      repositoryRoot: root,
      outputRoot,
      render: {
        primaryLanguage: "en",
        publicationName: "Berreta Futura",
        renderer: "weasyprint",
      },
      rendererAdapter: renderer,
    });

    const first = await runner.run(fixture.bootstrapRevision);
    assert.equal(first.boundary, "human");
    assert.equal(first.pendingHuman?.role, "visual_review");
    assert.match(first.pendingHuman?.offerId ?? "", /^offer_/u);
    const reviewPaths = first.pendingHuman?.reviewArtifacts.map(
      (artifact) => artifact.logicalPath,
    ) ?? [];
    assert.equal(reviewPaths.length, 34);
    assert.ok(reviewPaths.includes("en/reader.pdf"));
    assert.ok(reviewPaths.includes("es/home/booklet-a4.pdf"));
    assert.ok(reviewPaths.includes("es/render-review/reader-pages/page-004.png"));
    assert.deepEqual(operations, ["measure_edition", "render_edition"]);
    assert.ok(first.reviewProjection);
    assert.ok(first.publicDirectory);
    assert.equal(first.reviewProjection.offerId, first.pendingHuman?.offerId);
    const projectionManifest = JSON.parse(
      await readFile(first.reviewProjection.exportManifestPath, "utf8"),
    ) as { readonly independentCritic: { readonly result: string; readonly note: string } };
    assert.deepEqual(projectionManifest.independentCritic, {
      result: "not_run",
      note: "Automated projection of the exact offered render artifacts. This does not answer or approve the human visual-review offer; independent original-resolution visual QA remains required.",
    });
    await access(first.publicDirectory);
    const projectedView = await new EditionRunLayout({
      editionKey: "004",
      repositoryRoot: root,
      outputRoot,
    }).open(first.runId);
    try {
      const view = await projectedView.engine.inspect(first.runId);
      assert.equal(
        view.offers.find((offer) => offer.id === first.pendingHuman?.offerId)?.status,
        "offered",
      );
      assert.equal(view.decisions.some((decision) => decision.offerId === first.pendingHuman?.offerId), false);
    } finally {
      projectedView.close();
    }

    const repeated = await runner.run(fixture.bootstrapRevision);
    assert.equal(repeated.runId, first.runId);
    assert.equal(repeated.runName, first.runName);
    assert.equal(repeated.pendingHuman?.offerId, first.pendingHuman?.offerId);
    assert.deepEqual(operations, ["measure_edition", "render_edition"]);
    assert.equal(
      (await new EditionRunLayout({
        editionKey: "004",
        repositoryRoot: root,
        outputRoot,
      }).list()).length,
      1,
    );

    const opened = await new EditionRunLayout({
      editionKey: "004",
      repositoryRoot: root,
      outputRoot,
    }).open(first.runId);
    try {
      const view = await opened.engine.inspect(first.runId);
      const offer = view.offers.find((candidate) => candidate.id === first.pendingHuman?.offerId);
      assert.ok(offer);
      const actor = view.actors.find((candidate) => candidate.id === offer.actorId);
      assert.ok(actor);
      const renderArtifactIds = actor.context.renderArtifacts;
      assert.ok(
        Array.isArray(renderArtifactIds) &&
        renderArtifactIds.every((artifactId) => typeof artifactId === "string"),
      );
      const approval = {
        decision: "approved" as const,
        renderArtifactIds: renderArtifactIds as unknown as readonly ArtifactId[],
      };
      const claim = await opened.engine.claim(offer.id, {
        principalId: "visual-reviewer",
        displayName: "Visual reviewer",
        authority: "human",
        capabilities: ["human"],
      });
      await opened.engine.answer(claim, {
        contractVersion: offer.contractVersion,
        result: approval,
        artifacts: [{
          kind: "visual_review_decision",
          schemaVersion: offer.contractVersion,
          mediaType: "application/json",
          payload: { kind: "json", value: approval },
        }],
      });
    } finally {
      opened.close();
    }

    const completed = await runner.run(fixture.bootstrapRevision);
    assert.equal(completed.boundary, "terminal");
    assert.equal(completed.status, "complete");
    assert.ok(completed.published);
    assert.ok(completed.publicDirectory);
    await access(completed.published.exportManifestPath);
    assert.equal(
      (await readFile(join(completed.publicDirectory, "en", "reader.pdf")))
        .subarray(0, 5).toString("ascii"),
      "%PDF-",
    );
    assert.deepEqual(operations, ["measure_edition", "render_edition"]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("a fresh invocation resumes one exact persisted retryable machine failure", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-bootstrap-resume-"));
  const outputRoot = join(root, "output");
  const operations: RenderManifest["operation"][] = [];
  let failFirstMeasurement = true;
  try {
    const fixture = await writeBootstrapRepositoryFixture(root);
    const renderer = new InMemoryRendererAdapter(async (manifestPath, destination) => {
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as RenderManifest;
      operations.push(manifest.operation);
      if (manifest.operation === "measure_edition" && failFirstMeasurement) {
        failFirstMeasurement = false;
        throw new Error("temporary renderer failure");
      }
      return await renderFixture(manifest, destination);
    });
    const runner = bootstrapRunner(root, outputRoot, renderer);

    await assert.rejects(
      runner.run(fixture.bootstrapRevision),
      /has no claimable offer and is not at a human or terminal boundary/u,
    );
    const layout = new EditionRunLayout({
      editionKey: "004",
      repositoryRoot: root,
      outputRoot,
    });
    const [identity] = await layout.list();
    assert.ok(identity);
    const failedRunId = identity.id;
    const failed = await layout.open(failedRunId);
    try {
      const view = await failed.engine.inspect(failedRunId);
      assert.equal(view.status, "escalated");
      assert.equal(view.events.filter((event) => event.type === "RETRY").length, 0);
      assert.equal(view.offers.filter((offer) => offer.status === "failed").length, 1);
      assert.equal(view.attempts.filter((attempt) => attempt.status === "failed").length, 1);
    } finally {
      failed.close();
    }
    assert.deepEqual(operations, ["measure_edition"]);

    const resumed = await runner.run(fixture.bootstrapRevision);
    assert.equal(resumed.runId, failedRunId);
    assert.equal(resumed.boundary, "human");
    assert.equal(resumed.pendingHuman?.role, "visual_review");
    assert.deepEqual(
      operations,
      ["measure_edition", "measure_edition", "render_edition"],
    );
    const opened = await layout.open(failedRunId);
    try {
      const view = await opened.engine.inspect(failedRunId);
      const retries = view.events.filter((event) => event.type === "RETRY");
      assert.equal(retries.length, 1);
      assert.equal(retries[0]?.actorId, view.offers.find(
        (offer) => offer.status === "failed",
      )?.actorId);

      const humanOffer = view.offers.find(
        (offer) => offer.id === resumed.pendingHuman?.offerId,
      );
      assert.ok(humanOffer);
      const humanClaim = await opened.engine.claim(humanOffer.id, {
        principalId: "visual-reviewer",
        authority: "human",
        capabilities: ["human"],
      });
      await opened.engine.fail(humanClaim, {
        classification: "retryable",
        message: "reviewer unavailable",
      });
    } finally {
      opened.close();
    }

    await assert.rejects(
      runner.run(fixture.bootstrapRevision),
      /has no claimable offer and is not at a human or terminal boundary/u,
    );
    const humanFailed = await layout.open(failedRunId);
    try {
      const view = await humanFailed.engine.inspect(failedRunId);
      assert.equal(view.events.filter((event) => event.type === "RETRY").length, 1);
      assert.equal(
        view.attempts.filter((attempt) => attempt.worker.authority === "human").length,
        1,
      );
    } finally {
      humanFailed.close();
    }
    assert.deepEqual(
      operations,
      ["measure_edition", "measure_edition", "render_edition"],
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("a fresh invocation never resumes a persisted permanent machine failure", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-edition-bootstrap-permanent-"));
  const outputRoot = join(root, "output");
  let rendererCalls = 0;
  try {
    const fixture = await writeBootstrapRepositoryFixture(root);
    const runner = bootstrapRunner(
      root,
      outputRoot,
      new InMemoryRendererAdapter(() => {
        rendererCalls += 1;
        throw new SubprocessExecutionError(
          "permanent renderer failure",
          "permanent",
          null,
          "",
        );
      }),
    );

    const failed = await runner.run(fixture.bootstrapRevision);
    assert.equal(failed.status, "failed");
    assert.equal(failed.boundary, "terminal");
    assert.equal("publicDirectory" in failed, false);
    const repeated = await runner.run(fixture.bootstrapRevision);
    assert.equal(repeated.status, "failed");
    assert.equal(repeated.runId, failed.runId);
    assert.equal(rendererCalls, 1);

    const layout = new EditionRunLayout({
      editionKey: "004",
      repositoryRoot: root,
      outputRoot,
    });
    const [identity] = await layout.list();
    assert.ok(identity);
    const opened = await layout.open(identity.id);
    try {
      const view = await opened.engine.inspect(identity.id);
      assert.equal(view.events.filter((event) => event.type === "RETRY").length, 0);
      assert.equal([...view.events].reverse().find((event) => event.type === "WORK_FAILED")
        ?.payload.classification, "permanent");
    } finally {
      opened.close();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

function bootstrapRunner(
  root: string,
  outputRoot: string,
  renderer: InMemoryRendererAdapter,
): EditionBootstrapRunner {
  return new EditionBootstrapRunner({
    editionKey: "004",
    repositoryRoot: root,
    outputRoot,
    render: {
      primaryLanguage: "en",
      publicationName: "Berreta Futura",
      renderer: "weasyprint",
    },
    rendererAdapter: renderer,
  });
}

async function renderFixture(
  manifest: RenderManifest,
  destination: string,
): Promise<RenderResult> {
  const layouts = manifest.languages.map((language) => ({
    language,
    totalPages: 8,
    editorialPages: 1,
    articlePages: { systems: 2 },
    figureCount: 1,
    criticResult: manifest.operation === "render_edition"
      ? "pass" as const
      : "not_run" as const,
  }));
  const files: RenderedFile[] = [];
  if (manifest.operation === "render_edition") {
    for (const language of manifest.languages) {
      const directory = join(destination, language);
      await mkdir(directory, { recursive: true });
      const outputs: ReadonlyArray<readonly [string, string, string, string | Buffer]> = [
        ["reader.pdf", "application/pdf", "reader_pdf", pdfBytes(4)],
        ["home/booklet-a4.pdf", "application/pdf", "booklet_pdf", pdfBytes(2)],
        ["home/booklet-a4-cover.pdf", "application/pdf", "render_pdf", pdfBytes(1)],
        ["home/booklet-a4-interior.pdf", "application/pdf", "render_pdf", pdfBytes(1)],
        ["web-output.zip", "application/zip", "web_output", storedZip([
          ["index.html", "<main>fixture</main>"],
          ["edition.css", "body{}\n"],
        ])],
        ["package.zip", "application/zip", "package_artifact", storedZip([
          ["manifest.json", "{}\n"],
        ])],
        ["render-critic.json", "application/json", "render_critic_report", "{\"result\":\"pass\"}\n"],
        ["preflight.json", "application/json", "printer_preflight", JSON.stringify({
          studio: { ready: false, blockers: [] },
          reader: { page_count: 4 },
          home_booklet: { sheet_sides: 2 },
          home_booklet_cover: { sheet_sides: 1 },
          home_booklet_interior: { sheet_sides: 1 },
        })],
        ["render-review/reader-contact-sheet-01.png", "image/png", "render_review_image", pngBytes()],
        ["render-review/booklet-contact-sheet-01.png", "image/png", "render_review_image", pngBytes()],
        ...[1, 2, 3, 4].map((ordinal) => [
          `render-review/reader-pages/page-${String(ordinal).padStart(3, "0")}.png`,
          "image/png",
          "render_review_image",
          pngBytes(),
        ] as const),
        ...[1, 2].map((ordinal) => [
          `render-review/booklet-sides/page-${String(ordinal).padStart(3, "0")}.png`,
          "image/png",
          "render_review_image",
          pngBytes(),
        ] as const),
        ["render-review/cover-booklet-sides/page-001.png", "image/png", "render_review_image", pngBytes()],
      ];
      for (const [name, mediaType, kind, contents] of outputs) {
        await mkdir(join(directory, name, ".."), { recursive: true });
        await writeFile(join(directory, name), contents);
        files.push({ path: `${language}/${name}`, mediaType, kind });
      }
    }
  }
  return {
    schemaVersion: 1,
    rendererContractVersion: RENDERER_CONTRACT_VERSION,
    editionId: manifest.editionId,
    files,
    layouts,
    inputArtifactIds: manifest.inputs.map((input) => input.artifactId),
    tailArtFacts: {},
  };
}

function pdfBytes(pageCount: number): Buffer {
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

function pngBytes(): Buffer {
  return Buffer.from("89504e470d0a1a0a", "hex");
}

function storedZip(entries: readonly (readonly [string, string])[]): Buffer {
  const locals: Buffer[] = [];
  const central: Buffer[] = [];
  let offset = 0;
  for (const [name, text] of entries) {
    const filename = Buffer.from(name, "utf8");
    const bytes = Buffer.from(text, "utf8");
    const checksum = crc32(bytes);
    const local = Buffer.alloc(30 + filename.length + bytes.length);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(checksum, 14);
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
    header.writeUInt32LE(checksum, 16);
    header.writeUInt32LE(bytes.length, 20);
    header.writeUInt32LE(bytes.length, 24);
    header.writeUInt16LE(filename.length, 28);
    header.writeUInt32LE(offset, 42);
    filename.copy(header, 46);
    central.push(header);
    offset += local.length;
  }
  const centralBytes = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralBytes.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, centralBytes, end]);
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
