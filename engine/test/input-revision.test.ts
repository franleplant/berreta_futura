import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import {
  InputRevisionError,
  resolveInputRevision,
  type DurableGit,
} from "../durable/index.ts";

const REVISION = "rev_20260801T010203004Z_bbbbbbbbbbbb" as RevisionId;
const REF = {
  kind: "source_extraction",
  logicalId: "source",
  revisionId: REVISION,
} as const;

test("InputRevision resolves only an exact committed manifest and payload tree", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-input-revision-"));
  try {
    await writeFixture(root);
    const asserted: string[][] = [];
    const resolved = await resolveInputRevision(root, REF, {
      assertCommitted: async (paths) => { asserted.push([...paths]); },
    });
    assert.match(resolved.manifestDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.equal(
      resolved.payloadPaths["extracted.md"],
      join(resolved.absoluteDirectory, "extracted.md"),
    );
    assert.deepEqual(asserted, [[
      `inputs/sources/source/extractions/${REVISION}/extracted.md`,
      `inputs/sources/source/extractions/${REVISION}/manifest.yaml`,
    ]]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("InputRevision preserves safe case-sensitive legacy repository paths", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-input-revision-legacy-path-"));
  try {
    await writeFixture(root, "extracted.md", "prompts/README.md");
    const resolved = await resolveInputRevision(root, REF, committedGit());
    assert.equal(resolved.manifest.files[0]?.legacy_source?.repositoryPath, "prompts/README.md");

    await writeFixture(root, "extracted.md", "../outside.md");
    await assert.rejects(resolveInputRevision(root, REF, committedGit()), /repository path is unsafe/u);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("InputRevision rejects tampered, extra, aliased, and working-tree-only bytes", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-input-revision-invalid-"));
  try {
    const directory = await writeFixture(root);
    await writeFile(join(directory, "extracted.md"), "tampered\n", "utf8");
    await assert.rejects(
      resolveInputRevision(root, REF, committedGit()),
      (error: unknown) => error instanceof InputRevisionError && error.code === "INPUT_REVISION_INVALID",
    );

    await writeFixture(root);
    await writeFile(join(directory, "untracked.md"), "not in manifest\n", "utf8");
    await assert.rejects(resolveInputRevision(root, REF, committedGit()));
    await rm(join(directory, "untracked.md"));

    await writeFixture(root, "Extracted.md");
    await assert.rejects(resolveInputRevision(root, REF, committedGit()), /portable lowercase/u);
    await rm(join(directory, "Extracted.md"));

    await writeFixture(root);
    await assert.rejects(
      resolveInputRevision(root, REF, {
        assertCommitted: async () => { throw new Error("dirty"); },
      }),
      (error: unknown) => error instanceof InputRevisionError && error.code === "INPUT_REVISION_UNCOMMITTED",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("run_bootstrap is edition-scoped and rejects edition-spec payload aliases", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-run-bootstrap-"));
  const ref = {
    kind: "run_bootstrap",
    editionId: "004",
    logicalId: "fresh-v2",
    revisionId: REVISION,
  } as const;
  const directory = join(
    root,
    "inputs/editions/004/specs/fresh-v2/revisions",
    REVISION,
  );
  try {
    await mkdir(directory, { recursive: true });
    const payload = Buffer.from("prompt_set: fresh_v2_prompt_set\n", "utf8");
    await writeFile(join(directory, "bootstrap.yaml"), payload);
    await writeFile(join(directory, "manifest.yaml"), stringify({
      schema_version: 1,
      revision_kind: "run_bootstrap",
      logical_id: "fresh-v2",
      edition_id: "004",
      revision_id: REVISION,
      created_at: "2026-08-01T01:02:03.004Z",
      parent_revision_id: null,
      files: [{
        path: "bootstrap.yaml",
        media_type: "application/yaml",
        sha256: `sha256:${createHash("sha256").update(payload).digest("hex")}`,
        size_bytes: payload.byteLength,
      }],
    }, { lineWidth: 0 }));
    const resolved = await resolveInputRevision(root, ref, committedGit());
    assert.equal(resolved.manifest.revision_kind, "run_bootstrap");

    const aliased = Buffer.from("edition_id: '004'\n", "utf8");
    await rm(join(directory, "bootstrap.yaml"));
    await writeFile(join(directory, "edition.yaml"), aliased);
    await writeFile(join(directory, "manifest.yaml"), stringify({
      ...resolved.manifest,
      files: [{
        path: "edition.yaml",
        media_type: "application/yaml",
        sha256: `sha256:${createHash("sha256").update(aliased).digest("hex")}`,
        size_bytes: aliased.byteLength,
      }],
    }, { lineWidth: 0 }));
    await assert.rejects(
      resolveInputRevision(root, ref, committedGit()),
      /run bootstrap revision must contain exactly bootstrap.yaml/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("policy InputRevision has a distinct policies path and exact payload convention", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-policy-input-"));
  const ref = {
    kind: "policy",
    logicalId: "writing-rules",
    revisionId: REVISION,
  } as const;
  const directory = join(root, "inputs/policies/writing-rules/revisions", REVISION);
  try {
    await mkdir(directory, { recursive: true });
    const payload = Buffer.from("# Writing rules\n", "utf8");
    await writeFile(join(directory, "policy.md"), payload);
    await writeFile(join(directory, "manifest.yaml"), stringify({
      schema_version: 1,
      revision_kind: "policy",
      logical_id: "writing-rules",
      revision_id: REVISION,
      created_at: "2026-08-01T01:02:03.004Z",
      parent_revision_id: null,
      files: [{
        path: "policy.md",
        media_type: "text/markdown",
        sha256: `sha256:${createHash("sha256").update(payload).digest("hex")}`,
        size_bytes: payload.byteLength,
      }],
    }, { lineWidth: 0 }));
    const resolved = await resolveInputRevision(root, ref, committedGit());
    assert.equal(resolved.relativeDirectory, `inputs/policies/writing-rules/revisions/${REVISION}`);

    await rm(join(directory, "policy.md"));
    await writeFile(join(directory, "prompt.md"), payload);
    await writeFile(join(directory, "manifest.yaml"), stringify({
      schema_version: 1,
      revision_kind: "policy",
      logical_id: "writing-rules",
      revision_id: REVISION,
      created_at: "2026-08-01T01:02:03.004Z",
      parent_revision_id: null,
      files: [{
        path: "prompt.md",
        media_type: "text/markdown",
        sha256: `sha256:${createHash("sha256").update(payload).digest("hex")}`,
        size_bytes: payload.byteLength,
      }],
    }, { lineWidth: 0 }));
    await assert.rejects(resolveInputRevision(root, ref, committedGit()), /policy\.md/u);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

async function writeFixture(
  root: string,
  payloadPath = "extracted.md",
  legacySourcePath?: string,
): Promise<string> {
  const directory = join(root, "inputs/sources/source/extractions", REVISION);
  await mkdir(directory, { recursive: true });
  const payload = Buffer.from("# Exact extraction\n", "utf8");
  await writeFile(join(directory, payloadPath), payload);
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: "source_extraction",
    logical_id: "source",
    revision_id: REVISION,
    created_at: "2026-08-01T01:02:03.004Z",
    parent_revision_id: null,
    ...(legacySourcePath === undefined ? {} : { migration_id: "legacy-path-test" }),
    files: [{
      path: payloadPath,
      media_type: "text/markdown",
      sha256: `sha256:${createHash("sha256").update(payload).digest("hex")}`,
      size_bytes: payload.byteLength,
      ...(legacySourcePath === undefined ? {} : {
        legacy_source: {
          repositoryPath: legacySourcePath,
          gitCommitOid: "a".repeat(40),
          gitBlobOid: "b".repeat(40),
        },
      }),
    }],
  }, { lineWidth: 0 }));
  return directory;
}

function committedGit(): Pick<DurableGit, "assertCommitted"> {
  return { assertCommitted: async () => {} };
}
