import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import {
  inputRevisionRelativeDirectory,
  materializeLegacyDurableRevisions,
  type CompositionDocument,
  type DurableGit,
  type DurableRevisionRef,
  type GitRevisionBinding,
  type InputRevisionRef,
  type LegacyDurableMigrationPlan,
} from "../durable/index.ts";

const REVISIONS = {
  articleEn: "rev_20260802T210000000Z_aaaaaaaaaaaa" as RevisionId,
  articleEs: "rev_20260802T210000001Z_bbbbbbbbbbbb" as RevisionId,
  editorialEn: "rev_20260802T210000002Z_cccccccccccc" as RevisionId,
  editorialEs: "rev_20260802T210000003Z_dddddddddddd" as RevisionId,
  image: "rev_20260802T210000004Z_eeeeeeeeeeee" as RevisionId,
  composition: "rev_20260802T210000005Z_ffffffffffff" as RevisionId,
  edition: "rev_20260802T200000000Z_gggggggggggg" as RevisionId,
  bootstrap: "rev_20260802T200000001Z_hhhhhhhhhhhh" as RevisionId,
} as const;

const EDITION_REF: InputRevisionRef = {
  kind: "edition_spec",
  editionId: "004",
  logicalId: "main",
  revisionId: REVISIONS.edition,
};
const BOOTSTRAP_REF: Extract<InputRevisionRef, { readonly kind: "run_bootstrap" }> = {
  kind: "run_bootstrap",
  editionId: "004",
  logicalId: "fresh-v2",
  revisionId: REVISIONS.bootstrap,
};

test("legacy durable migration preserves honest source provenance and imports one fresh composition", async () => {
  const root = await fixture();
  try {
    const git = new FakeGit();
    const plan = migrationPlan();
    const first = await materializeLegacyDurableRevisions(
      root,
      join(root, ".magazine/004/migration/work/durable"),
      plan,
      git,
    );
    const retried = await materializeLegacyDurableRevisions(
      root,
      join(root, ".magazine/004/migration/work/durable"),
      plan,
      git,
    );
    assert.deepEqual(retried, first);
    assert.equal(first.revisions.length, 6);
    assert.ok(first.repositoryPaths.every((path) => path.startsWith("durable/")));
    assert.equal(git.assertions.length, 2);

    const articleManifest = await readFile(join(
      root,
      `durable/editions/004/articles/example/en/revisions/${REVISIONS.articleEn}/manifest.yaml`,
    ), "utf8");
    assert.match(articleManifest, /provenance_kind: legacy_import/u);
    assert.match(articleManifest, /legacy_run_inventory: absent/u);
    assert.match(articleManifest, /repositoryPath: legacy\/article-en\.md/u);
    assert.doesNotMatch(articleManifest, /producing_run_id|promotion_id|decision_engine/u);

    const compositionManifest = await readFile(join(
      root,
      `durable/editions/004/compositions/fresh-v2/revisions/${REVISIONS.composition}/manifest.yaml`,
    ), "utf8");
    assert.match(compositionManifest, /provenance_kind: legacy_import/u);
    assert.match(compositionManifest, /repositoryPath: legacy\/edition\.yaml/u);
    assert.match(compositionManifest, /fresh_v2_composition_from_committed_legacy_inventory/u);
    assert.doesNotMatch(compositionManifest, /bootstrap_revision|producing_run_id/u);
    assert.equal(
      await readFile(join(
        root,
        `durable/editions/004/images/cover/revisions/${REVISIONS.image}/image.png`,
      )).then((bytes) => bytes.compare(PNG)),
      0,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("legacy durable migration rejects mismatched Git scope and immutable target conflicts", async () => {
  const root = await fixture();
  try {
    const plan = migrationPlan();
    await assert.rejects(
      materializeLegacyDurableRevisions(root, join(root, ".magazine/work"), {
        ...plan,
        sourceGitBinding: {
          ...plan.sourceGitBinding,
          blobOids: { "legacy/article-en.md": "b".repeat(40) },
        },
      }, new FakeGit()),
      /source Git binding does not match/u,
    );

    await materializeLegacyDurableRevisions(
      root,
      join(root, ".magazine/work"),
      plan,
      new FakeGit(),
    );
    const changed: LegacyDurableMigrationPlan = {
      ...plan,
      composition: {
        ...plan.composition,
        document: {
          ...plan.composition.document,
          images: [{
            slot_id: "different-cover-slot",
            revision: imageRef(),
          }],
        },
      },
    };
    await assert.rejects(
      materializeLegacyDurableRevisions(root, join(root, ".magazine/work"), changed, new FakeGit()),
      /contains different bytes/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

const PNG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 1, 2, 3, 4]);

async function fixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "mag-legacy-durable-"));
  await mkdir(join(root, "legacy"), { recursive: true });
  await writeFile(join(root, "legacy/article-en.md"), "# Article EN\n");
  await writeFile(join(root, "legacy/article-es.md"), "# Article ES\n");
  await writeFile(join(root, "legacy/editorial-en.md"), "# Editorial EN\n");
  await writeFile(join(root, "legacy/editorial-es.md"), "# Editorial ES\n");
  await writeFile(join(root, "legacy/cover.png"), PNG);
  await writeFile(join(root, "legacy/edition.yaml"), "edition_id: '004'\n");
  await writeInput(root, EDITION_REF, "edition.yaml", Buffer.from("edition_id: '004'\n"));
  await writeInput(
    root,
    BOOTSTRAP_REF,
    "bootstrap.yaml",
    Buffer.from("prompt_set: fresh_v2_prompt_set\n"),
  );
  return root;
}

async function writeInput(
  root: string,
  ref: InputRevisionRef,
  payloadName: string,
  payload: Buffer,
): Promise<void> {
  const directory = join(root, "inputs", inputRevisionRelativeDirectory(ref));
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadName), payload);
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: ref.kind,
    logical_id: ref.logicalId,
    edition_id: ref.editionId,
    revision_id: ref.revisionId,
    created_at: "2026-08-02T20:00:00.000Z",
    parent_revision_id: null,
    files: [{
      path: payloadName,
      media_type: "application/yaml",
      sha256: digest(payload),
      size_bytes: payload.byteLength,
    }],
  }, { lineWidth: 0 }));
}

function migrationPlan(): LegacyDurableMigrationPlan {
  const refs = {
    articleEn: articleRef("en", REVISIONS.articleEn),
    articleEs: articleRef("es", REVISIONS.articleEs),
    editorialEn: editorialRef("en", REVISIONS.editorialEn),
    editorialEs: editorialRef("es", REVISIONS.editorialEs),
    image: imageRef(),
  };
  const sourcePaths = [
    "legacy/article-en.md",
    "legacy/article-es.md",
    "legacy/cover.png",
    "legacy/editorial-en.md",
    "legacy/editorial-es.md",
    "legacy/edition.yaml",
  ];
  return {
    schemaVersion: "legacy-durable-migration/1",
    migrationId: "edition4-fresh-v2",
    sourceGitBinding: {
      commitOid: "a".repeat(40),
      blobOids: Object.fromEntries(sourcePaths.map((path) => [path, "b".repeat(40)])),
    },
    entries: [
      manuscriptEntry(refs.articleEn, "legacy/article-en.md"),
      manuscriptEntry(refs.articleEs, "legacy/article-es.md"),
      manuscriptEntry(refs.editorialEn, "legacy/editorial-en.md"),
      manuscriptEntry(refs.editorialEs, "legacy/editorial-es.md"),
      {
        ref: refs.image,
        createdAt: "2026-08-02T21:00:00.004Z",
        parentRevisionId: null,
        inputRevisions: [EDITION_REF],
        files: [{
          sourcePath: "legacy/cover.png",
          targetPath: "image.png",
          mediaType: "image/png",
        }],
      },
    ],
    composition: {
      ref: {
        kind: "composition",
        editionId: "004",
        compositionId: "fresh-v2",
        revisionId: REVISIONS.composition,
      },
      createdAt: "2026-08-02T21:00:00.005Z",
      parentRevisionId: null,
      sourcePaths: ["legacy/edition.yaml"],
      document: composition(refs),
    },
  };
}

function manuscriptEntry(
  ref: Exclude<DurableRevisionRef, { readonly kind: "composition" | "image" }>,
  sourcePath: string,
) {
  return {
    ref,
    createdAt: "2026-08-02T21:00:00.000Z",
    parentRevisionId: null,
    inputRevisions: [EDITION_REF],
    files: [{ sourcePath, targetPath: "manuscript.md", mediaType: "text/markdown" }],
  } as const;
}

function articleRef(language: string, revisionId: RevisionId) {
  return { kind: "article", editionId: "004", logicalId: "example", language, revisionId } as const;
}

function editorialRef(language: string, revisionId: RevisionId) {
  return { kind: "editorial", editionId: "004", logicalId: "opening", language, revisionId } as const;
}

function imageRef() {
  return {
    kind: "image",
    editionId: "004",
    logicalId: "cover",
    revisionId: REVISIONS.image,
  } as const;
}

function composition(refs: {
  readonly articleEn: ReturnType<typeof articleRef>;
  readonly articleEs: ReturnType<typeof articleRef>;
  readonly editorialEn: ReturnType<typeof editorialRef>;
  readonly editorialEs: ReturnType<typeof editorialRef>;
  readonly image: ReturnType<typeof imageRef>;
}): CompositionDocument {
  return {
    schema_version: 1,
    edition_id: "004",
    composition_id: "fresh-v2",
    editorials: [{
      editorial_id: "opening",
      manuscripts: [
        { language: "en", revision: refs.editorialEn },
        { language: "es", revision: refs.editorialEs },
      ],
    }],
    articles: [{
      article_id: "example",
      manuscripts: [
        { language: "en", revision: refs.articleEn },
        { language: "es", revision: refs.articleEs },
      ],
      images: [{ slot_id: "opener", revision: refs.image }],
    }],
    images: [{ slot_id: "cover", revision: refs.image }],
    layout_inputs: [{ slot_id: "edition", revision: EDITION_REF }],
  };
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

class FakeGit implements Pick<DurableGit, "assertCommitted"> {
  readonly assertions: Array<{
    readonly paths: readonly string[];
    readonly binding: GitRevisionBinding | undefined;
  }> = [];

  async assertCommitted(paths: readonly string[], binding?: GitRevisionBinding): Promise<void> {
    this.assertions.push({ paths, binding });
  }
}
