import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { stringify } from "yaml";

import type { ArtifactId, PromotionId, RevisionId, RunId } from "../contracts/index.ts";
import {
  DurableStoreError,
  durableRevisionRelativeDirectory,
  inputRevisionRelativeDirectory,
  parseCompositionDocument,
  resolveCompositionRevision,
  type CompositionDocument,
  type CompositionRevisionBinding,
  type DurableGit,
  type DurableRevisionRef,
  type GitRevisionBinding,
  type InputRevisionRef,
} from "../durable/index.ts";

const REVISION = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;
const COMPOSITION_REVISION = "rev_20260802T200700000Z_bbbbbbbbbbbb" as RevisionId;
const INPUT_REVISION = "rev_20260801T010203004Z_cccccccccccc" as RevisionId;
const SOURCE_INPUT_REVISION = "rev_20260801T010203005Z_dddddddddddd" as RevisionId;
const COMPOSITION_REF = {
  kind: "composition",
  editionId: "004",
  compositionId: "main",
  revisionId: COMPOSITION_REVISION,
} as const;

test("CompositionRevision resolves every ordered durable and layout pin from committed bytes", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-composition-resolver-"));
  try {
    const fixture = await writeCompositionFixture(root);
    const git = new RecordingGit();
    const stage = await resolveCompositionRevision(root, fixture.binding, git);

    assert.equal(stage.schemaVersion, "render-stage/1");
    assert.equal(stage.compositionDocument.articles[0]?.article_id, "first-article");
    assert.equal(stage.compositionDocument.articles[1]?.article_id, "second-article");
    assert.deepEqual(stage.durableInputs.map((revision) => revision.ref.kind), [
      "editorial",
      "article",
      "image",
      "article",
      "image",
    ]);
    assert.deepEqual(stage.inputRevisions.map((revision) => revision.ref.kind), [
      "edition_spec",
      "source_extraction",
    ]);
    assert.deepEqual(git.expectedBindings, [{
      commitOid: fixture.binding.gitCommitOid,
      blobOids: fixture.binding.gitBlobOids,
    }]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("CompositionRevision rejects working-tree-only children and a mismatched public binding", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-composition-resolver-dirty-"));
  try {
    const fixture = await writeCompositionFixture(root);
    const dirtyGit = new RecordingGit();
    dirtyGit.rejectPattern = "/articles/first-article/";
    await assert.rejects(
      resolveCompositionRevision(root, fixture.binding, dirtyGit),
      (error: unknown) => error instanceof DurableStoreError && error.code === "DURABLE_REVISION_UNCOMMITTED",
    );
    await assert.rejects(
      resolveCompositionRevision(root, {
        ...fixture.binding,
        revisionRef: { ...COMPOSITION_REF, compositionId: "other" },
      }, new RecordingGit()),
      (error: unknown) => error instanceof DurableStoreError && error.code === "DURABLE_REVISION_MISSING",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("Composition manifest rejects ambiguous identities, duplicate slots, and language drift", () => {
  const editorial = manuscriptRef("editorial", "opening", "en");
  const article = manuscriptRef("article", "first-article", "en");
  const input: InputRevisionRef = {
    kind: "edition_spec",
    editionId: "004",
    logicalId: "main",
    revisionId: INPUT_REVISION,
  };
  const document: CompositionDocument = {
    schema_version: 1,
    edition_id: "004",
    composition_id: "main",
    editorials: [{ editorial_id: "opening", manuscripts: [{ language: "en", revision: editorial }] }],
    articles: [{ article_id: "first-article", manuscripts: [{ language: "en", revision: article }], images: [] }],
    images: [],
    layout_inputs: [{ slot_id: "edition-spec", revision: input }],
  };
  const decode = (value: unknown) => parseCompositionDocument(Buffer.from(stringify(value)), {
    editionId: "004",
    compositionId: "main",
  });

  assert.throws(() => decode({ ...document, logicalId: "main" }), /unexpected or missing fields/u);
  assert.throws(() => decode({ ...document, articles: [...document.articles, document.articles[0]] }), /article IDs must be unique/u);
  assert.throws(() => decode({
    ...document,
    articles: [{
      ...document.articles[0],
      manuscripts: [{ language: "es", revision: article }],
    }],
  }), /language disagrees/u);
  assert.throws(() => decode({
    ...document,
    layout_inputs: [{ slot_id: "Edición", revision: input }],
  }), /portable lowercase/u);
});

async function writeCompositionFixture(
  root: string,
): Promise<{ readonly binding: CompositionRevisionBinding }> {
  const editorial = manuscriptRef("editorial", "opening", "en");
  const first = manuscriptRef("article", "first-article", "en");
  const second = manuscriptRef("article", "second-article", "en");
  const firstImage = imageRef("first-opener");
  const coverImage = imageRef("cover");
  const layoutInput: InputRevisionRef = {
    kind: "edition_spec",
    editionId: "004",
    logicalId: "main",
    revisionId: INPUT_REVISION,
  };
  const sourceInput: InputRevisionRef = {
    kind: "source_extraction",
    logicalId: "first-source",
    revisionId: SOURCE_INPUT_REVISION,
  };
  await Promise.all([
    writeDurableRevision(root, editorial, "manuscript.md", Buffer.from("# Opening\n")),
    writeDurableRevision(root, first, "manuscript.md", Buffer.from("# First\n"), [sourceInput]),
    writeDurableRevision(root, second, "manuscript.md", Buffer.from("# Second\n"), [sourceInput]),
    writeDurableRevision(root, firstImage, "image.png", pngBytes(1)),
    writeDurableRevision(root, coverImage, "image.png", pngBytes(2)),
    writeInputRevision(root, layoutInput),
    writeInputRevision(root, sourceInput),
  ]);
  const composition: CompositionDocument = {
    schema_version: 1,
    edition_id: "004",
    composition_id: "main",
    editorials: [{
      editorial_id: "opening",
      manuscripts: [{ language: "en", revision: editorial }],
    }],
    articles: [{
      article_id: "first-article",
      manuscripts: [{ language: "en", revision: first }],
      images: [{ slot_id: "opener", revision: firstImage }],
    }, {
      article_id: "second-article",
      manuscripts: [{ language: "en", revision: second }],
      images: [],
    }],
    images: [{ slot_id: "cover", revision: coverImage }],
    layout_inputs: [{ slot_id: "edition-spec", revision: layoutInput }],
  };
  await writeDurableRevision(
    root,
    COMPOSITION_REF,
    "composition.yaml",
    Buffer.from(stringify(composition, { lineWidth: 0 })),
  );
  const relativeDirectory = join("durable", durableRevisionRelativeDirectory(COMPOSITION_REF));
  const repositoryPaths = [
    join(relativeDirectory, "composition.yaml"),
    join(relativeDirectory, "manifest.yaml"),
  ].sort();
  const manifest = await readFile(join(root, relativeDirectory, "manifest.yaml"));
  return {
    binding: {
      revisionRef: COMPOSITION_REF,
      manifestDigest: digest(manifest),
      gitCommitOid: "a".repeat(40),
      gitBlobOids: Object.fromEntries(repositoryPaths.map((path) => [path, "b".repeat(40)])),
    },
  };
}

async function writeDurableRevision(
  root: string,
  ref: DurableRevisionRef,
  payloadName: string,
  bytes: Buffer,
  inputRevisions: readonly InputRevisionRef[] = [],
): Promise<void> {
  const directory = join(root, "durable", durableRevisionRelativeDirectory(ref));
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadName), bytes);
  const identity = ref.kind === "composition"
    ? { composition_id: ref.compositionId }
    : { logical_id: ref.logicalId, ...(ref.kind === "image" ? {} : { language: ref.language }) };
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: ref.kind,
    edition_id: ref.editionId,
    ...identity,
    revision_id: ref.revisionId,
    created_at: "2026-08-02T20:07:00.000Z",
    parent_revision_id: null,
    provenance_kind: "engine_promotion",
    promotion_id: "promotion_fixture" as PromotionId,
    producing_run_id: "run_fixture" as RunId,
    accepted_engine_artifact_ids: ["art_fixture" as ArtifactId],
    decision_engine_artifact_ids: ["art_decision" as ArtifactId],
    input_revisions: inputRevisions,
    input_engine_artifact_ids: [],
    files: [{
      path: payloadName,
      mediaType: payloadName.endsWith(".md") ? "text/markdown" :
        payloadName.endsWith(".png") ? "image/png" : "application/yaml",
      sha256: digest(bytes),
      sizeBytes: bytes.byteLength,
      engineArtifactId: "art_fixture" as ArtifactId,
    }],
  }, { lineWidth: 0 }));
}

async function writeInputRevision(root: string, ref: InputRevisionRef): Promise<void> {
  const directory = join(root, "inputs", inputRevisionRelativeDirectory(ref));
  const payloadName = ref.kind === "edition_spec" ? "edition.yaml" : "extracted.md";
  const bytes = Buffer.from(
    ref.kind === "edition_spec" ? "edition_id: '004'\n" : "# Extracted source\n",
    "utf8",
  );
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadName), bytes);
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: ref.kind,
    logical_id: ref.logicalId,
    ...(ref.kind === "edition_spec" ? { edition_id: ref.editionId } : {}),
    revision_id: ref.revisionId,
    created_at: "2026-08-01T01:02:03.004Z",
    parent_revision_id: null,
    files: [{
      path: payloadName,
      media_type: ref.kind === "edition_spec" ? "application/yaml" : "text/markdown",
      sha256: digest(bytes),
      size_bytes: bytes.byteLength,
    }],
  }, { lineWidth: 0 }));
}

function manuscriptRef(
  kind: "article",
  logicalId: string,
  language: string,
): Extract<DurableRevisionRef, { readonly kind: "article" }>;
function manuscriptRef(
  kind: "editorial",
  logicalId: string,
  language: string,
): Extract<DurableRevisionRef, { readonly kind: "editorial" }>;
function manuscriptRef(
  kind: "article" | "editorial",
  logicalId: string,
  language: string,
): Extract<DurableRevisionRef, { readonly kind: "article" | "editorial" }> {
  return { kind, editionId: "004", logicalId, language, revisionId: REVISION };
}

function imageRef(logicalId: string): Extract<DurableRevisionRef, { readonly kind: "image" }> {
  return { kind: "image", editionId: "004", logicalId, revisionId: REVISION };
}

function pngBytes(marker: number): Buffer {
  return Buffer.concat([Buffer.from("89504e470d0a1a0a", "hex"), Buffer.from([marker])]);
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

class RecordingGit implements Pick<DurableGit, "assertCommitted"> {
  readonly expectedBindings: GitRevisionBinding[] = [];
  rejectPattern: string | undefined;

  async assertCommitted(
    paths: readonly string[],
    expected?: GitRevisionBinding,
  ): Promise<void> {
    if (this.rejectPattern !== undefined && paths.some((path) => path.includes(this.rejectPattern!))) {
      throw new Error("working tree differs from Git");
    }
    if (expected !== undefined) {
      this.expectedBindings.push(expected);
    }
  }
}
