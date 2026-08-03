import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import { stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import {
  inputRevisionRelativeDirectory,
  materializeLegacyDurableMigrationBatch,
  type CompositionDocument,
  type DurableGit,
  type DurableRevisionRef,
  type GitRevisionBinding,
  GitCliDurableGit,
  type InputRevisionRef,
  type HistoricalCompositionEntry,
  type LegacyDurableBatchMigrationPlan,
  type MigrationPlanRevisionRef,
} from "../durable/index.ts";

const execFile = promisify(execFileCallback);

const REVISIONS = {
  articleEn: "rev_20260802T210000000Z_aaaaaaaaaaaa" as RevisionId,
  articleEs: "rev_20260802T210000001Z_bbbbbbbbbbbb" as RevisionId,
  editorialEn: "rev_20260802T210000002Z_cccccccccccc" as RevisionId,
  editorialEs: "rev_20260802T210000003Z_dddddddddddd" as RevisionId,
  image: "rev_20260802T210000004Z_eeeeeeeeeeee" as RevisionId,
  edition: "rev_20260802T200000000Z_gggggggggggg" as RevisionId,
  migrationPlan: "rev_20260802T200000002Z_iiiiiiiiiiii" as RevisionId,
  articleSuccessor: "rev_20260802T210000006Z_jjjjjjjjjjjj" as RevisionId,
  historicalComposition: "rev_20260802T210000007Z_kkkkkkkkkkkk" as RevisionId,
} as const;

const EDITION_REF: InputRevisionRef = {
  kind: "edition_spec",
  editionId: "004",
  logicalId: "main",
  revisionId: REVISIONS.edition,
};
const MIGRATION_PLAN_REF: MigrationPlanRevisionRef = {
  kind: "migration_plan",
  logicalId: "legacy-four-root",
  revisionId: REVISIONS.migrationPlan,
};

test("v2 durable migration supports an entry-only historical batch", async () => {
  const root = await fixture();
  try {
    const plan = await batchPlan(root, {
      entries: [{
        ref: articleRef("en", REVISIONS.articleSuccessor),
        createdAt: "2026-08-02T21:00:00.006Z",
        parentRevisionId: null,
        inputRevisions: [EDITION_REF, MIGRATION_PLAN_REF],
        files: [{
          sourcePath: "legacy/article-en.md",
          targetPath: "manuscript.md",
          mediaType: "text/markdown",
        }],
      }],
      compositions: [],
      sourcePaths: ["legacy/article-en.md"],
    });
    const materialized = await materializeLegacyDurableMigrationBatch(
      root,
      join(root, ".magazine/work"),
      plan,
      new GitCliDurableGit(root),
    );
    assert.equal(materialized.revisions.length, 1);
    assert.equal(materialized.revisions[0]!.ref.revisionId, REVISIONS.articleSuccessor);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 durable migration supports a composition-only historical batch and records caller basis", async () => {
  const root = await fixture();
  try {
    await materializeBaseEntries(root);
    await commitAll(root, "Commit durable composition children");
    const plan = await batchPlan(root, {
      entries: [],
      compositions: [historicalComposition()],
      sourcePaths: ["legacy/edition.yaml"],
    });
    const materialized = await materializeLegacyDurableMigrationBatch(
      root,
      join(root, ".magazine/work"),
      plan,
      new GitCliDurableGit(root),
    );
    assert.equal(materialized.revisions.length, 1);
    const manifest = await readFile(join(
      root,
      `durable/editions/004/compositions/legacy-current/revisions/${REVISIONS.historicalComposition}/manifest.yaml`,
    ), "utf8");
    assert.match(manifest, /basis: exact_legacy_head_snapshot/u);
    assert.match(manifest, /kind: migration_plan/u);
    assert.match(manifest, new RegExp(REVISIONS.migrationPlan));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 durable migration requires committed input, parent, and composition child revisions", async () => {
  const root = await fixture();
  try {
    await materializeBaseEntries(root);
    const entry = {
      ref: articleRef("en", REVISIONS.articleSuccessor),
      createdAt: "2026-08-02T21:00:00.006Z",
      parentRevisionId: REVISIONS.articleEn,
      inputRevisions: [EDITION_REF, MIGRATION_PLAN_REF],
      files: [{ sourcePath: "legacy/article-en.md", targetPath: "manuscript.md", mediaType: "text/markdown" }],
    } as const;
    const entryPlan = await batchPlan(root, { entries: [entry], compositions: [], sourcePaths: ["legacy/article-en.md"] });
    await assert.rejects(
      materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), entryPlan, new RejectingGit("inputs/")),
      /input revision .*not committed exactly/u,
    );
    await assert.rejects(
      materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), entryPlan, new RejectingGit("durable/editions/004/articles/example/en/revisions/")),
      /durable revision .*not committed exactly/u,
    );
    const compositionPlan = await batchPlan(root, {
      entries: [],
      compositions: [historicalComposition()],
      sourcePaths: ["legacy/edition.yaml"],
    });
    await assert.rejects(
      materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), compositionPlan, new RejectingGit("durable/editions/004/images/cover/revisions/")),
      /durable revision .*not committed exactly/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 durable migration installs immutable bound Git blobs after source preflight", async () => {
  const root = await fixture();
  try {
    const entry = {
      ref: articleRef("en", REVISIONS.articleSuccessor),
      createdAt: "2026-08-02T21:00:00.006Z",
      parentRevisionId: null,
      inputRevisions: [EDITION_REF, MIGRATION_PLAN_REF],
      files: [{ sourcePath: "legacy/article-en.md", targetPath: "manuscript.md", mediaType: "text/markdown" }],
    } as const;
    const plan = await batchPlan(root, {
      entries: [entry],
      compositions: [],
      sourcePaths: ["legacy/article-en.md"],
    });
    const git = new MutatingAfterSourcePreflightGit(root, "legacy/article-en.md");
    await materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), plan, git);
    assert.equal(
      await readFile(join(
        root,
        `durable/editions/004/articles/example/en/revisions/${REVISIONS.articleSuccessor}/manuscript.md`,
      ), "utf8"),
      "# Article EN\n",
    );
    assert.equal(await readFile(join(root, "legacy/article-en.md"), "utf8"), "# MUTATED AFTER PREFLIGHT\n");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 durable migration rejects an unrelated migration plan input", async () => {
  const root = await fixture();
  try {
    const unrelated = {
      kind: "migration_plan",
      logicalId: "other-migration",
      revisionId: "rev_20260802T200000003Z_llllllllllll" as RevisionId,
    } as const;
    const plan = await batchPlan(root, {
      entries: [{
        ref: articleRef("en", REVISIONS.articleSuccessor),
        createdAt: "2026-08-02T21:00:00.006Z",
        parentRevisionId: null,
        inputRevisions: [EDITION_REF, unrelated],
        files: [{ sourcePath: "legacy/article-en.md", targetPath: "manuscript.md", mediaType: "text/markdown" }],
      }],
      compositions: [],
      sourcePaths: ["legacy/article-en.md"],
    });
    await assert.rejects(
      materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), plan, new GitCliDurableGit(root)),
      /exact migration plan input revision/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 durable migration rejects additional and duplicate migration plan inputs", async () => {
  const root = await fixture();
  try {
    const unrelated = {
      kind: "migration_plan",
      logicalId: "other-migration",
      revisionId: "rev_20260802T200000003Z_llllllllllll" as RevisionId,
    } as const;
    const entry = {
      ref: articleRef("en", REVISIONS.articleSuccessor),
      createdAt: "2026-08-02T21:00:00.006Z",
      parentRevisionId: null,
      files: [{ sourcePath: "legacy/article-en.md", targetPath: "manuscript.md", mediaType: "text/markdown" }],
    } as const;
    for (const inputRevisions of [
      [EDITION_REF, MIGRATION_PLAN_REF, unrelated],
      [EDITION_REF, MIGRATION_PLAN_REF, MIGRATION_PLAN_REF],
    ] as const) {
      const plan = await batchPlan(root, {
        entries: [{ ...entry, inputRevisions }],
        compositions: [],
        sourcePaths: ["legacy/article-en.md"],
      });
      await assert.rejects(
        materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), plan, new GitCliDurableGit(root)),
        /exactly one exact migration plan input revision/u,
      );
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 historical compositions reject additional and duplicate migration plan inputs", async () => {
  const root = await fixture();
  try {
    const unrelated = {
      kind: "migration_plan",
      logicalId: "other-migration",
      revisionId: "rev_20260802T200000003Z_llllllllllll" as RevisionId,
    } as const;
    for (const extraInputRevisions of [
      [MIGRATION_PLAN_REF, unrelated],
      [MIGRATION_PLAN_REF, MIGRATION_PLAN_REF],
    ] as const) {
      const plan = await batchPlan(root, {
        entries: [],
        compositions: [{ ...historicalComposition(), extraInputRevisions }],
        sourcePaths: ["legacy/edition.yaml"],
      });
      await assert.rejects(
        materializeLegacyDurableMigrationBatch(root, join(root, ".magazine/work"), plan, new GitCliDurableGit(root)),
        /exactly one exact migration plan input revision/u,
      );
    }
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
  await writeInput(root, MIGRATION_PLAN_REF, "inventory.yaml", Buffer.from("migration: legacy-four-root\n"));
  await git(root, ["init", "-q"]);
  await git(root, ["config", "user.name", "Magazine Test"]);
  await git(root, ["config", "user.email", "magazine-test@example.invalid"]);
  await commitAll(root, "Create durable migration fixture");
  return root;
}

async function batchPlan(root: string, options: {
  readonly entries: readonly LegacyDurableBatchMigrationPlan["entries"][number][];
  readonly compositions: readonly HistoricalCompositionEntry[];
  readonly sourcePaths: readonly string[];
}): Promise<LegacyDurableBatchMigrationPlan> {
  const commitOid = (await git(root, ["rev-parse", "HEAD"])).trim();
  const blobOids = Object.fromEntries(await Promise.all(options.sourcePaths.map(async (path) => [
    path,
    (await git(root, ["rev-parse", `HEAD:${path}`])).trim(),
  ])));
  return {
    schemaVersion: "legacy-durable-migration/2",
    migrationId: "legacy-four-root",
    migrationPlanRevision: MIGRATION_PLAN_REF,
    sourceGitBinding: {
      commitOid,
      blobOids,
    },
    entries: options.entries,
    compositions: options.compositions,
  };
}

async function commitAll(root: string, message: string): Promise<void> {
  await git(root, ["add", "."]);
  await git(root, ["commit", "-q", "-m", message]);
}

async function git(root: string, args: readonly string[]): Promise<string> {
  return (await execFile("git", args, { cwd: root, encoding: "utf8" })).stdout;
}

function historicalComposition(): HistoricalCompositionEntry {
  const refs = {
    articleEn: articleRef("en", REVISIONS.articleEn),
    articleEs: articleRef("es", REVISIONS.articleEs),
    editorialEn: editorialRef("en", REVISIONS.editorialEn),
    editorialEs: editorialRef("es", REVISIONS.editorialEs),
    image: imageRef(),
  };
  return {
    ref: {
      kind: "composition",
      editionId: "004",
      compositionId: "legacy-current",
      revisionId: REVISIONS.historicalComposition,
    },
    createdAt: "2026-08-02T21:00:00.007Z",
    parentRevisionId: null,
    sourcePaths: ["legacy/edition.yaml"],
    document: { ...composition(refs), composition_id: "legacy-current" },
    assemblyBasis: "exact_legacy_head_snapshot",
    extraInputRevisions: [MIGRATION_PLAN_REF],
  };
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

async function materializeBaseEntries(root: string): Promise<void> {
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
  ];
  const plan = await batchPlan(root, {
    entries: [
      manuscriptEntry(refs.articleEn, "legacy/article-en.md"),
      manuscriptEntry(refs.articleEs, "legacy/article-es.md"),
      manuscriptEntry(refs.editorialEn, "legacy/editorial-en.md"),
      manuscriptEntry(refs.editorialEs, "legacy/editorial-es.md"),
      {
        ref: refs.image,
        createdAt: "2026-08-02T21:00:00.004Z",
        parentRevisionId: null,
        inputRevisions: [EDITION_REF, MIGRATION_PLAN_REF],
        files: [{
          sourcePath: "legacy/cover.png",
          targetPath: "image.png",
          mediaType: "image/png",
        }],
      },
    ],
    compositions: [],
    sourcePaths,
  });
  await materializeLegacyDurableMigrationBatch(
    root,
    join(root, ".magazine/work"),
    plan,
    new GitCliDurableGit(root),
  );
}

function manuscriptEntry(
  ref: Exclude<DurableRevisionRef, { readonly kind: "composition" | "image" }>,
  sourcePath: string,
) {
  return {
    ref,
    createdAt: "2026-08-02T21:00:00.000Z",
    parentRevisionId: null,
    inputRevisions: [EDITION_REF, MIGRATION_PLAN_REF],
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

class RejectingGit extends FakeGit {
  private readonly rejectedPrefix: string;

  constructor(rejectedPrefix: string) {
    super();
    this.rejectedPrefix = rejectedPrefix;
  }

  override async assertCommitted(
    paths: readonly string[],
    binding?: GitRevisionBinding,
  ): Promise<void> {
    await super.assertCommitted(paths, binding);
    if (paths.some((path) => path.startsWith(this.rejectedPrefix))) {
      throw new Error(`not committed: ${this.rejectedPrefix}`);
    }
  }
}

class MutatingAfterSourcePreflightGit implements Pick<DurableGit, "assertCommitted"> {
  private readonly delegate: GitCliDurableGit;
  private readonly root: string;
  private readonly sourcePath: string;
  private mutated = false;

  constructor(root: string, sourcePath: string) {
    this.root = root;
    this.sourcePath = sourcePath;
    this.delegate = new GitCliDurableGit(root);
  }

  async assertCommitted(paths: readonly string[], binding?: GitRevisionBinding): Promise<void> {
    await this.delegate.assertCommitted(paths, binding);
    if (!this.mutated && binding !== undefined && paths.includes(this.sourcePath)) {
      await writeFile(join(this.root, this.sourcePath), "# MUTATED AFTER PREFLIGHT\n");
      this.mutated = true;
    }
  }
}
