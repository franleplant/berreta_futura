import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";

import type { ArtifactId } from "../contracts/index.ts";
import { createConfiguredWorker } from "../executors/configured-worker.ts";
import {
  LocalSourceAdapter,
  SOURCE_CONTRACT_VERSION,
  type SourceRequest,
} from "../source-adapter/index.ts";

function id(value: string): ArtifactId {
  return value as ArtifactId;
}

test("configured workers use the TypeScript source archive without a Python project root", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-configured-worker-"));
  try {
    await assert.doesNotReject(createConfiguredWorker({
      schemaVersion: 1,
      executors: [{
        kind: "source_archive",
        id: "local-source",
        workDirectory: "/private/tmp/local-source",
      }],
    }, { authorityDirectory: join(temporary, "authority") }));
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("local source adapter archives only named immutable files into the owned destination", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-local-source-adapter-"));
  try {
    const artifacts = join(temporary, "artifacts");
    const destination = join(temporary, "destination");
    await mkdir(artifacts);
    const lead = join(artifacts, "lead.txt");
    const capture = join(artifacts, "capture.html");
    await writeFile(lead, "https://example.invalid/article", "utf8");
    await writeFile(capture, "<main>evidence</main>", "utf8");
    const request: SourceRequest = {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: "example-source",
      leadArtifactId: id("lead-artifact"),
      artifactRoot: artifacts,
      files: [
        { artifactId: id("lead-artifact"), sourcePath: lead, targetPath: "raw/lead.txt" },
        { artifactId: id("capture-artifact"), sourcePath: capture, targetPath: "raw/capture.html" },
      ],
    };
    const requestPath = join(temporary, "request.json");
    await writeFile(requestPath, JSON.stringify(request), "utf8");

    const result = await new LocalSourceAdapter().archive(
      requestPath,
      destination,
      new AbortController().signal,
    );

    assert.deepEqual(result, {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: "example-source",
      files: [
        { path: "raw/lead.txt", kind: "raw_evidence" },
        { path: "raw/capture.html", kind: "raw_evidence" },
      ],
      inputArtifactIds: ["lead-artifact", "lead-artifact", "capture-artifact"],
    });
    assert.equal(await readFile(join(destination, "raw", "capture.html"), "utf8"), "<main>evidence</main>");
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("local source adapter rejects source escape and unsafe output paths", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-local-source-security-"));
  try {
    const artifacts = join(temporary, "artifacts");
    await mkdir(artifacts);
    const source = join(artifacts, "capture.html");
    await writeFile(source, "<main>evidence</main>", "utf8");
    const request: SourceRequest = {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: "example-source",
      leadArtifactId: id("lead-artifact"),
      artifactRoot: artifacts,
      files: [
        {
          artifactId: id("capture-artifact"),
          sourcePath: resolve(temporary, "outside.html"),
          targetPath: "../escape.html",
        },
      ],
    };
    const requestPath = join(temporary, "request.json");
    await writeFile(requestPath, JSON.stringify(request), "utf8");

    await assert.rejects(
      new LocalSourceAdapter().archive(
        requestPath,
        join(temporary, "destination"),
        new AbortController().signal,
      ),
      /unsafe targetPath|must be a regular file beneath artifactRoot/,
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("local source adapter rejects an intermediate symlink that physically escapes artifactRoot", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-local-source-realpath-"));
  try {
    const artifacts = join(temporary, "artifacts");
    const outside = join(temporary, "outside");
    await mkdir(artifacts);
    await mkdir(outside);
    await writeFile(join(outside, "capture.html"), "<main>outside</main>", "utf8");
    await symlink(outside, join(artifacts, "linked"));
    const request: SourceRequest = {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: "example-source",
      leadArtifactId: id("lead-artifact"),
      artifactRoot: artifacts,
      files: [{
        artifactId: id("capture-artifact"),
        sourcePath: join(artifacts, "linked", "capture.html"),
        targetPath: "raw/capture.html",
      }],
    };
    const requestPath = join(temporary, "request.json");
    await writeFile(requestPath, JSON.stringify(request), "utf8");

    await assert.rejects(
      new LocalSourceAdapter().archive(
        requestPath,
        join(temporary, "destination"),
        new AbortController().signal,
      ),
      /physically resolve beneath artifactRoot/u,
    );
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});
