import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import type { ArtifactId, RunId } from "../contracts/index.ts";
import {
  exportApprovedRender,
  type ApprovedRenderExportPlan,
} from "../run-engine/index.ts";

const RUN_ID = "run_approved-render-export" as RunId;
const APPROVAL_ARTIFACT = "art_approved-visual-review" as ArtifactId;
const READER = "art_reader-current" as ArtifactId;
const BOOKLET = "art_booklet-current" as ArtifactId;
const WEB = "art_web-current" as ArtifactId;
const SECOND_WEB = "art_web-second-current" as ArtifactId;
const PREFLIGHT = "art_preflight-current" as ArtifactId;
const CRITIC = "art_critic-current" as ArtifactId;
const HISTORICAL_READER = "art_reader-historical" as ArtifactId;

test("approved render export turns opaque RunEngine payloads into named extensions from the exact approved artifacts", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const result = await exportApprovedRender(fixtureEngine(), plan(join(temporary, "deliverables")));

    assert.equal(result.decisionArtifactId, APPROVAL_ARTIFACT);
    assert.deepEqual(await readFile(join(result.destinationDirectory, "en", "reader.pdf")), pdfBytes());
    assert.equal((await readFile(join(result.destinationDirectory, "en", "reader.pdf"))).subarray(0, 5).toString("ascii"), "%PDF-");
    assert.equal((await readFile(join(result.destinationDirectory, "en", "web.zip"))).subarray(0, 4).toString("ascii"), "PK\x03\x04");
    assert.equal(await readFile(join(result.destinationDirectory, "en", "web", "index.html"), "utf8"), "<main>accepted</main>");
    assert.equal(await readFile(join(result.destinationDirectory, "en", "web", "assets", "edition.css"), "utf8"), "body{}\n");

    const manifest = JSON.parse(await readFile(result.manifestPath, "utf8")) as {
      runId: string;
      approvedDecision: { decisionArtifactId: string; offerId: string };
      files: Array<{ destination: string; artifactId: string }>;
    };
    assert.equal(manifest.runId, RUN_ID);
    assert.deepEqual(manifest.approvedDecision, {
      decisionArtifactId: APPROVAL_ARTIFACT,
      decisionId: "decision_approved-visual-review",
      offerId: "offer_visual-review",
    });
    assert.deepEqual(manifest.files.map((file) => [file.destination, file.artifactId]), [
      ["en/reader.pdf", READER],
      ["en/web.zip", WEB],
    ]);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export refuses historical artifacts and traversal before publishing", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    const historicalPlan = {
      ...plan(destination),
      files: [{ artifactId: HISTORICAL_READER, destination: "en/reader.pdf", kind: "reader_pdf", mediaType: "application/pdf" }],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(
      exportApprovedRender(fixtureEngine(), historicalPlan),
      { code: "RENDER_NOT_APPROVED" },
    );

    const traversalPlan = {
      ...plan(destination),
      files: [{ artifactId: READER, destination: "../reader.pdf", kind: "reader_pdf", mediaType: "application/pdf" }],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(
      exportApprovedRender(fixtureEngine(), traversalPlan),
      { code: "RENDER_EXPORT_PATH" },
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects a stale visual decision even when its recorded choice says approved", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    await assert.rejects(
      exportApprovedRender(fixtureEngine({
        approval: {
          accepted: false,
          expectedRenderArtifactIds: [READER, WEB],
        },
      }), plan(destination)),
      { code: "RENDER_APPROVAL_INVALID" },
    );
    await assert.rejects(
      exportApprovedRender(fixtureEngine({
        approval: {
          accepted: true,
          expectedRenderArtifactIds: [WEB, READER],
        },
      }), plan(destination)),
      { code: "RENDER_APPROVAL_INVALID" },
    );
    assert.equal(await missing(destination), true);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects media magic mismatches and unpack/file collisions", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    const badPdfEngine = fixtureEngine({ reader: Buffer.from("not a pdf") });
    await assert.rejects(exportApprovedRender(badPdfEngine, plan(destination)), { code: "RENDER_EXPORT_MAGIC" });
    assert.equal(await missing(destination), true);

    const badZipEngine = fixtureEngine({ web: Buffer.from("not a zip") });
    await assert.rejects(exportApprovedRender(badZipEngine, plan(destination)), { code: "RENDER_EXPORT_MAGIC" });

    const collisionPlan = {
      ...plan(destination),
      files: [{
        artifactId: WEB,
        destination: "en/web.zip",
        kind: "web_output",
        mediaType: "application/zip",
        unpack: { destination: "en/web.zip", requiredFiles: ["index.html"] },
      }],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(exportApprovedRender(fixtureEngine(), collisionPlan), { code: "RENDER_EXPORT_PATH" });

    const overlapPlan = {
      ...plan(destination),
      files: [
        {
          artifactId: WEB,
          destination: "en/web.zip",
          kind: "web_output",
          mediaType: "application/zip",
          unpack: { destination: "en/web", requiredFiles: ["index.html"] },
        },
        {
          artifactId: READER,
          destination: "en/reader.pdf",
          kind: "reader_pdf",
          mediaType: "application/pdf",
          unpack: { destination: "en/web/assets", requiredFiles: ["index.html"] },
        },
      ],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(exportApprovedRender(fixtureEngine(), overlapPlan), { code: "RENDER_EXPORT_PATH" });

    const wrongExtensionPlan = {
      ...plan(destination),
      files: [{ artifactId: READER, destination: "en/reader", kind: "reader_pdf", mediaType: "application/pdf" }],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(exportApprovedRender(fixtureEngine(), wrongExtensionPlan), { code: "RENDER_EXPORT_EXTENSION" });

    const duplicateDestinationPlan = {
      ...plan(destination),
      files: [
        { artifactId: READER, destination: "en/render.pdf", kind: "reader_pdf", mediaType: "application/pdf" },
        { artifactId: WEB, destination: "en/render.pdf", kind: "web_output", mediaType: "application/zip" },
      ],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(exportApprovedRender(fixtureEngine(), duplicateDestinationPlan), { code: "RENDER_EXPORT_DUPLICATE" });

    const duplicateArtifactPlan = {
      ...plan(destination),
      files: [
        { artifactId: READER, destination: "en/reader.pdf", kind: "reader_pdf", mediaType: "application/pdf" },
        { artifactId: READER, destination: "es/reader.pdf", kind: "reader_pdf", mediaType: "application/pdf" },
      ],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(exportApprovedRender(fixtureEngine(), duplicateArtifactPlan), { code: "RENDER_EXPORT_DUPLICATE" });
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects Finder-equivalent path aliases before publishing", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    const collidingPlans: readonly ApprovedRenderExportPlan[] = [
      {
        ...plan(destination),
        files: [{
          artifactId: PREFLIGHT,
          destination: "Manifest.json",
          kind: "printer_preflight",
          mediaType: "application/json",
        }],
      },
      {
        ...plan(destination),
        files: [
          { artifactId: READER, destination: "en/Reader.pdf", kind: "reader_pdf", mediaType: "application/pdf" },
          { artifactId: BOOKLET, destination: "en/reader.pdf", kind: "booklet_pdf", mediaType: "application/pdf" },
        ],
      },
      {
        ...plan(destination),
        files: [
          { artifactId: PREFLIGHT, destination: "en/café.json", kind: "printer_preflight", mediaType: "application/json" },
          { artifactId: CRITIC, destination: "en/cafe\u0301.json", kind: "render_critic_report", mediaType: "application/json" },
        ],
      },
      {
        ...plan(destination),
        files: [
          {
            artifactId: WEB,
            destination: "en/first.zip",
            kind: "web_output",
            mediaType: "application/zip",
            unpack: { destination: "en/Web", requiredFiles: ["index.html"] },
          },
          {
            artifactId: SECOND_WEB,
            destination: "en/second.zip",
            kind: "web_output",
            mediaType: "application/zip",
            unpack: { destination: "en/web/assets", requiredFiles: ["index.html"] },
          },
        ],
      },
    ];
    for (const collidingPlan of collidingPlans) {
      await assert.rejects(
        exportApprovedRender(fixtureEngine(), collidingPlan),
        { code: /RENDER_EXPORT_(?:DUPLICATE|PATH)/ },
      );
      assert.equal(await missing(destination), true);
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects a required web file stored as a Unix symlink", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    const outside = join(temporary, "outside.html");
    await writeFile(outside, "outside stays unchanged", "utf8");
    const web = storedZip([
      ["index.html", outside, 0o120777],
      ["assets/edition.css", "body{}\n", 0o100644],
    ]);

    await assert.rejects(
      exportApprovedRender(fixtureEngine({ web }), plan(destination)),
      { code: "RENDER_EXPORT_ZIP" },
    );
    assert.equal(await readFile(outside, "utf8"), "outside stays unchanged");
    assert.equal(await missing(destination), true);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects a Unix FIFO even when required web files are regular", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    const web = storedZip([
      ["index.html", "<main>accepted</main>", 0o100644],
      ["assets/edition.css", "body{}\n", 0o100644],
      ["assets/render-events", "", 0o010644],
    ]);

    await assert.rejects(
      exportApprovedRender(fixtureEngine({ web }), plan(destination)),
      { code: "RENDER_EXPORT_ZIP" },
    );
    assert.equal(await missing(destination), true);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects Finder-equivalent ZIP entry aliases", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    for (const web of [
      storedZip([
        ["index.html", "<main>accepted</main>", 0o100644],
        ["assets/Logo.png", "first", 0o100644],
        ["assets/logo.png", "second", 0o100644],
      ]),
      storedZip([
        ["index.html", "<main>accepted</main>", 0o100644],
        ["assets/café.json", "first", 0o100644],
        ["assets/cafe\u0301.json", "second", 0o100644],
      ]),
    ]) {
      await assert.rejects(
        exportApprovedRender(fixtureEngine({ web }), plan(destination)),
        { code: "RENDER_EXPORT_ZIP" },
      );
      assert.equal(await missing(destination), true);
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export rejects non-canonical ZIP path components before unzip", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    for (const web of [
      storedZip([
        ["index.html", "<main>accepted</main>", 0o100644],
        ["assets/", "", 0o040755],
        ["assets//", "", 0o040755],
      ]),
      storedZip([
        ["index.html", "<main>accepted</main>", 0o100644],
        ["assets/", "", 0o040755],
        ["assets/./", "", 0o040755],
      ]),
      storedZip([
        ["index.html", "<main>accepted</main>", 0o100644],
        ["assets//logo.png", "aliased", 0o100644],
      ]),
      storedZip([
        ["index.html", "<main>accepted</main>", 0o100644],
        ["assets/./logo.png", "aliased", 0o100644],
      ]),
    ]) {
      await assert.rejects(
        exportApprovedRender(fixtureEngine({ web }), plan(destination)),
        (error: unknown) => {
          assert.equal((error as { readonly code?: string }).code, "RENDER_EXPORT_ZIP");
          assert.match((error as Error).message, /unsafe entry/);
          return true;
        },
      );
      assert.equal(await missing(destination), true);
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("approved render export refuses implicit overwrite and preserves the old directory on a failed replacement", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-approved-render-export-"));
  try {
    const destination = join(temporary, "deliverables");
    await writeFile(join(temporary, "seed"), "seed");
    await writeFile(join(temporary, "deliverables"), "not a directory");
    await assert.rejects(exportApprovedRender(fixtureEngine(), plan(destination)), { code: "RENDER_EXPORT_EXISTS" });

    await rm(destination, { force: true });
    await exportApprovedRender(fixtureEngine(), { ...plan(destination), overwrite: true });
    await writeFile(join(destination, "keep.txt"), "old export");
    const invalidReplacement = {
      ...plan(destination),
      overwrite: true,
      files: [{ artifactId: READER, destination: "en/reader.pdf", kind: "wrong_kind", mediaType: "application/pdf" }],
    } satisfies ApprovedRenderExportPlan;
    await assert.rejects(exportApprovedRender(fixtureEngine(), invalidReplacement), { code: "RENDER_EXPORT_MISMATCH" });
    assert.equal(await readFile(join(destination, "keep.txt"), "utf8"), "old export");

    const replaced = await exportApprovedRender(fixtureEngine(), { ...plan(destination), overwrite: true });
    await assert.rejects(readFile(join(replaced.destinationDirectory, "keep.txt")));
    assert.deepEqual(await readFile(join(replaced.destinationDirectory, "en", "reader.pdf")), pdfBytes());
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

function plan(destinationDirectory: string): ApprovedRenderExportPlan {
  return {
    runId: RUN_ID,
    approvedDecisionArtifactId: APPROVAL_ARTIFACT,
    destinationDirectory,
    files: [
      { artifactId: READER, destination: "en/reader.pdf", kind: "reader_pdf", mediaType: "application/pdf" },
      {
        artifactId: WEB,
        destination: "en/web.zip",
        kind: "web_output",
        mediaType: "application/zip",
        unpack: { destination: "en/web", requiredFiles: ["index.html", "assets/edition.css"] },
      },
    ],
  };
}

function fixtureEngine(overrides: {
  readonly reader?: Buffer;
  readonly web?: Buffer;
  readonly approval?: Readonly<Record<string, unknown>>;
} = {}): Parameters<typeof exportApprovedRender>[0] {
  const artifacts = new Map<ArtifactId, { kind: string; mediaType: string; bytes: Buffer }>([
    [READER, { kind: "reader_pdf", mediaType: "application/pdf", bytes: overrides.reader ?? pdfBytes() }],
    [BOOKLET, { kind: "booklet_pdf", mediaType: "application/pdf", bytes: pdfBytes() }],
    [WEB, { kind: "web_output", mediaType: "application/zip", bytes: overrides.web ?? storedZip([[
      "index.html", "<main>accepted</main>", 0o100644,
    ], ["assets/edition.css", "body{}\n", 0o100644]]) }],
    [SECOND_WEB, { kind: "web_output", mediaType: "application/zip", bytes: storedZip([[
      "index.html", "<main>second</main>", 0o100644,
    ]]) }],
    [PREFLIGHT, { kind: "printer_preflight", mediaType: "application/json", bytes: Buffer.from("{\"passed\":true}") }],
    [CRITIC, { kind: "render_critic_report", mediaType: "application/json", bytes: Buffer.from("{\"result\":\"pass\"}") }],
    [HISTORICAL_READER, { kind: "reader_pdf", mediaType: "application/pdf", bytes: Buffer.from("%PDF-historical") }],
  ]);
  return {
    inspect: async () => ({
      id: RUN_ID,
      decisions: [{
        id: "decision_approved-visual-review",
        artifactId: APPROVAL_ARTIFACT,
        choice: "approved",
        authority: "human",
        offerId: "offer_visual-review",
        details: {
          submittedRenderArtifactIds: [READER, BOOKLET, WEB, SECOND_WEB, PREFLIGHT, CRITIC],
          expectedRenderArtifactIds: [READER, BOOKLET, WEB, SECOND_WEB, PREFLIGHT, CRITIC],
          accepted: true,
          ...overrides.approval,
        },
      }],
      offers: [{ id: "offer_visual-review", role: "visual_review" }],
    }),
    readArtifact: async (artifactId: ArtifactId) => {
      const artifact = artifacts.get(artifactId);
      assert.ok(artifact, `unexpected artifact read: ${artifactId}`);
      return {
        artifact: {
          id: artifactId,
          kind: artifact.kind,
          mediaType: artifact.mediaType,
        },
        bytes: artifact.bytes,
      };
    },
  } as unknown as Parameters<typeof exportApprovedRender>[0];
}

async function missing(path: string): Promise<boolean> {
  try {
    await readFile(path);
    return false;
  } catch {
    return true;
  }
}

function pdfBytes(): Buffer {
  return Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n", "ascii");
}

function storedZip(entries: readonly (readonly [string, string, number?])[]): Buffer {
  const locals: Buffer[] = [];
  const central: Buffer[] = [];
  let offset = 0;
  for (const [name, text, unixMode] of entries) {
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
    header.writeUInt16LE(unixMode === undefined ? 20 : 0x0314, 4);
    header.writeUInt16LE(20, 6);
    header.writeUInt32LE(crc, 16);
    header.writeUInt32LE(bytes.length, 20);
    header.writeUInt32LE(bytes.length, 24);
    header.writeUInt16LE(filename.length, 28);
    if (unixMode !== undefined) {
      header.writeUInt32LE((unixMode << 16) >>> 0, 38);
    }
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
