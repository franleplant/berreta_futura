import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type { RevisionId } from "../contracts/index.ts";
import {
  materializeNativeInputRevision,
  resolveInputRevision,
} from "../durable/index.ts";

const revisionId = "rev_20260803T120000000Z_aaaaaaaaaaaa" as RevisionId;
const ref = { kind: "prompt" as const, logicalId: "translation-es", revisionId };

test("native input materializer creates an idempotent, resolvable immutable revision", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-native-input-"));
  try {
    const request = {
      ref,
      createdAt: "2026-08-03T12:00:00.000Z",
      parentRevisionId: null,
      files: [
        { path: "prompt.md", mediaType: "text/markdown", content: "Translate faithfully.\n" },
        { path: "output.schema.json", mediaType: "application/json", content: "{}\n" },
      ],
    } as const;
    const first = await materializeNativeInputRevision(root, root, request);
    const second = await materializeNativeInputRevision(root, root, request);
    assert.equal(second.manifestDigest, first.manifestDigest);
    const resolved = await resolveInputRevision(root, ref, {
      assertCommitted: async (paths) => {
        assert.deepEqual(paths, first.repositoryPaths);
      },
    });
    assert.equal(resolved.payloadPaths["prompt.md"]?.endsWith("prompt.md"), true);
    assert.equal(resolved.manifest.migration_id, undefined);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("native write pipelines live under the edition specs root", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-native-pipeline-"));
  const pipeline = {
    kind: "write_pipeline" as const,
    editionId: "004",
    logicalId: "edition4-write",
    revisionId: "rev_20260803T120000001Z_aaaaaaaaaaaa" as RevisionId,
  };
  try {
    const materialized = await materializeNativeInputRevision(root, root, {
      ref: pipeline,
      createdAt: "2026-08-03T12:00:00.001Z",
      parentRevisionId: null,
      files: [{ path: "production.yaml", mediaType: "application/yaml", content: "schema_version: 1\n" }],
    });
    assert.equal(
      materialized.relativeDirectory,
      "inputs/editions/004/specs/write-pipeline/revisions/rev_20260803T120000001Z_aaaaaaaaaaaa",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
