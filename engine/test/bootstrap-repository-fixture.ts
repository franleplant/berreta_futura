import { execFile as execFileCallback } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";

import { stringify } from "yaml";

import {
  KNOWN_WORK_ROLES,
  type RevisionId,
} from "../contracts/index.ts";
import {
  GitCliDurableGit,
  materializeLegacyDurableRevisions,
  materializeLegacyInputs,
  resolveDurableRevision,
  type CompositionRevisionBinding,
  type DurableRevisionRef,
  type InputRevisionRef,
  type LegacyDurableMigrationPlan,
  type LegacyInputMigrationPlan,
} from "../durable/index.ts";

const execFile = promisify(execFileCallback);

const REVISION = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;
const BOOTSTRAP_REVISION = "rev_20260802T200641637Z_bbbbbbbbbbbb" as RevisionId;

export const bootstrapFixtureRevision = {
  kind: "run_bootstrap",
  editionId: "004",
  logicalId: "fresh-v2",
  revisionId: BOOTSTRAP_REVISION,
} as const;

export type BootstrapRepositoryFixture = {
  readonly bootstrapRevision: typeof bootstrapFixtureRevision;
  readonly compositionBinding: CompositionRevisionBinding;
};

/** Creates a tiny committed repository with the same public bootstrap graph as fresh-v2. */
export async function writeBootstrapRepositoryFixture(
  root: string,
): Promise<BootstrapRepositoryFixture> {
  const sourceFiles: Readonly<Record<string, string | Buffer>> = {
    "editions/fixture-edition/edition.yaml": [
      "schema_version: 1",
      "id: fixture-edition",
      "language: en",
      "sources: [fixture-source]",
      "editorial: manuscript/editorial.md",
      "articles:",
      "  - id: systems",
      "    manuscript: editions/fixture-edition/articles/systems.md",
      "cover:",
      "  art_path: art/cover.png",
      "",
    ].join("\n"),
    "editions/fixture-edition/translations/es/edition.yaml": [
      "schema_version: 1",
      "language: es",
      "editorial:",
      "  path: manuscript/editorial.md",
      "articles:",
      "  - id: systems",
      "    manuscript: articles/systems.md",
      "",
    ].join("\n"),
    "library/sources/fixture-source/record.yaml": "schema_version: 1\nid: fixture-source\n",
    "library/sources/fixture-source/extracted.md": "# Exact extraction\n",
    "legacy/prompt.md": "Preserve the source.\n",
    "legacy/policy.md": "Review exact immutable artifacts.\n",
    "editions/fixture-edition/manuscript/editorial.md": "# Opening\n",
    "editions/fixture-edition/translations/es/manuscript/editorial.md": "# Apertura\n",
    "editions/fixture-edition/articles/systems.md": "# Systems\n",
    "editions/fixture-edition/translations/es/articles/systems.md": "# Sistemas\n",
    "editions/fixture-edition/art/cover.png": Buffer.from("89504e470d0a1a0a", "hex"),
  };
  for (const [path, contents] of Object.entries(sourceFiles)) {
    const absolute = join(root, path);
    await mkdir(join(absolute, ".."), { recursive: true });
    await writeFile(absolute, contents);
  }
  await git(root, ["init"]);
  await git(root, ["config", "user.name", "Magazine Test"]);
  await git(root, ["config", "user.email", "magazine-test@example.invalid"]);
  await git(root, ["add", "legacy", "editions", "library"]);
  await git(root, ["commit", "-m", "Fixture legacy sources"]);

  const gitAuthority = new GitCliDurableGit(root);
  const inputEntries: LegacyInputMigrationPlan["entries"] = [
    {
      ref: editionSpecRef(),
      createdAt: "2026-08-02T20:06:41.636Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "editions/fixture-edition/edition.yaml",
        targetPath: "edition.yaml",
        mediaType: "application/yaml",
      }, {
        sourcePath: "editions/fixture-edition/translations/es/edition.yaml",
        targetPath: "translations/es/edition.yaml",
        mediaType: "application/yaml",
      }],
    },
    {
      ref: captureRef(),
      createdAt: "2026-08-02T20:06:41.636Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "library/sources/fixture-source/record.yaml",
        targetPath: "raw/record.yaml",
        mediaType: "application/yaml",
      }],
    },
    {
      ref: extractionRef(),
      createdAt: "2026-08-02T20:06:41.636Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "library/sources/fixture-source/extracted.md",
        targetPath: "extracted.md",
        mediaType: "text/markdown",
      }],
    },
    {
      ref: promptRef(),
      createdAt: "2026-08-02T20:06:41.636Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "legacy/prompt.md",
        targetPath: "prompt.md",
        mediaType: "text/markdown",
      }, {
        content: "{\"type\":\"string\"}\n",
        generationBasis: "fixture prompt output contract",
        targetPath: "output.schema.json",
        mediaType: "application/json",
      }],
    },
    {
      ref: policyRef(),
      createdAt: "2026-08-02T20:06:41.636Z",
      parentRevisionId: null,
      files: [{
        sourcePath: "legacy/policy.md",
        targetPath: "policy.md",
        mediaType: "text/markdown",
      }],
    },
  ];
  const inputSources = inputEntries.flatMap((entry) => entry.files.flatMap((file) =>
    file.sourcePath === undefined ? [] : [file.sourcePath]
  ));
  const inputPlan: LegacyInputMigrationPlan = {
    schemaVersion: "legacy-input-migration/1",
    migrationId: "bootstrap-fixture-inputs",
    sourceGitBinding: await gitBinding(root, inputSources),
    entries: inputEntries,
  };
  await materializeLegacyInputs(
    root,
    join(root, ".fixture-work", "inputs"),
    inputPlan,
    gitAuthority,
  );

  const durableSources = [
    "editions/fixture-edition/manuscript/editorial.md",
    "editions/fixture-edition/translations/es/manuscript/editorial.md",
    "editions/fixture-edition/articles/systems.md",
    "editions/fixture-edition/translations/es/articles/systems.md",
    "editions/fixture-edition/art/cover.png",
    "editions/fixture-edition/edition.yaml",
  ];
  const durablePlan: LegacyDurableMigrationPlan = {
    schemaVersion: "legacy-durable-migration/1",
    migrationId: "bootstrap-fixture-durable",
    sourceGitBinding: await gitBinding(root, durableSources),
    entries: [
      manuscriptEntry(editorialRef("en"), "editions/fixture-edition/manuscript/editorial.md", [
        editionSpecRef(), promptRef(), policyRef(),
      ]),
      manuscriptEntry(editorialRef("es"), "editions/fixture-edition/translations/es/manuscript/editorial.md", [
        editionSpecRef(), policyRef(),
      ]),
      manuscriptEntry(articleRef("en"), "editions/fixture-edition/articles/systems.md", [
        editionSpecRef(), captureRef(), extractionRef(), promptRef(), policyRef(),
      ]),
      manuscriptEntry(articleRef("es"), "editions/fixture-edition/translations/es/articles/systems.md", [
        editionSpecRef(), policyRef(),
      ]),
      {
        ref: imageRef(),
        createdAt: "2026-08-02T20:06:41.636Z",
        parentRevisionId: null,
        inputRevisions: [editionSpecRef()],
        files: [{
          sourcePath: "editions/fixture-edition/art/cover.png",
          targetPath: "image.png",
          mediaType: "image/png",
        }],
      },
    ],
    composition: {
      ref: compositionRef(),
      createdAt: "2026-08-02T20:06:41.636Z",
      parentRevisionId: null,
      sourcePaths: ["editions/fixture-edition/edition.yaml"],
      document: {
        schema_version: 1,
        edition_id: "004",
        composition_id: "fresh-v2",
        editorials: [{
          editorial_id: "opening",
          manuscripts: [
            { language: "en", revision: editorialRef("en") },
            { language: "es", revision: editorialRef("es") },
          ],
        }],
        articles: [{
          article_id: "systems",
          manuscripts: [
            { language: "en", revision: articleRef("en") },
            { language: "es", revision: articleRef("es") },
          ],
          images: [],
        }],
        images: [{ slot_id: "cover", revision: imageRef() }],
        layout_inputs: [{ slot_id: "edition-spec", revision: editionSpecRef() }],
      },
    },
  };
  await materializeLegacyDurableRevisions(
    root,
    join(root, ".fixture-work", "durable"),
    durablePlan,
    gitAuthority,
  );
  await git(root, ["add", "inputs", "durable"]);
  await git(root, ["commit", "-m", "Fixture immutable composition"]);

  const resolvedComposition = await resolveDurableRevision(
    root,
    compositionRef(),
    gitAuthority,
  );
  const compositionBinding: CompositionRevisionBinding = {
    revisionRef: compositionRef(),
    manifestDigest: resolvedComposition.manifestDigest,
    gitCommitOid: await git(root, ["rev-parse", "HEAD"]),
    gitBlobOids: (await gitBinding(root, resolvedComposition.repositoryPaths)).blobOids,
  };
  const bootstrapPlan: LegacyInputMigrationPlan = {
    schemaVersion: "legacy-input-migration/1",
    migrationId: "bootstrap-fixture-run",
    sourceGitBinding: { commitOid: await git(root, ["rev-parse", "HEAD"]), blobOids: {} },
    entries: [{
      ref: bootstrapFixtureRevision,
      createdAt: "2026-08-02T20:06:41.637Z",
      parentRevisionId: null,
      files: [{
        content: stringify({
          schema_version: 1,
          edition_id: "004",
          composition_revision: {
            revision_ref: {
              kind: "composition",
              edition_id: "004",
              composition_id: "fresh-v2",
              revision_id: REVISION,
            },
            manifest_digest: compositionBinding.manifestDigest,
            git_commit_oid: compositionBinding.gitCommitOid,
            git_blob_oids: compositionBinding.gitBlobOids,
          },
          configured_languages: ["en", "es"],
          selected_image_revision_refs: [{
            kind: "image",
            edition_id: "004",
            logical_id: "cover",
            revision_id: REVISION,
          }],
          image_generation_allowed: false,
          renderer_contract_version: "magazine-renderer/1",
          prompt_set: {
            id: "bootstrap-fixture-prompts",
            role_inputs: roleInputs(),
          },
        }, { lineWidth: 0 }),
        generationBasis: "fixture exact composition execution authority",
        targetPath: "bootstrap.yaml",
        mediaType: "application/yaml",
      }],
    }],
  };
  await materializeLegacyInputs(
    root,
    join(root, ".fixture-work", "bootstrap"),
    bootstrapPlan,
    gitAuthority,
  );
  await git(root, ["add", "inputs"]);
  await git(root, ["commit", "-m", "Fixture run bootstrap"]);
  await rm(join(root, ".fixture-work"), { recursive: true, force: true });
  return { bootstrapRevision: bootstrapFixtureRevision, compositionBinding };
}

function editionSpecRef(): InputRevisionRef {
  return { kind: "edition_spec", editionId: "004", logicalId: "main", revisionId: REVISION };
}

function captureRef(): InputRevisionRef {
  return { kind: "source_capture", logicalId: "source", revisionId: REVISION };
}

function extractionRef(): InputRevisionRef {
  return { kind: "source_extraction", logicalId: "source", revisionId: REVISION };
}

function promptRef(): InputRevisionRef {
  return { kind: "prompt", logicalId: "writer", revisionId: REVISION };
}

function policyRef(): InputRevisionRef {
  return { kind: "policy", logicalId: "render-review", revisionId: REVISION };
}

function editorialRef(
  language: "en" | "es",
): Extract<DurableRevisionRef, { readonly kind: "editorial" }> {
  return { kind: "editorial", editionId: "004", logicalId: "opening", language, revisionId: REVISION };
}

function articleRef(
  language: "en" | "es",
): Extract<DurableRevisionRef, { readonly kind: "article" }> {
  return { kind: "article", editionId: "004", logicalId: "systems", language, revisionId: REVISION };
}

function imageRef(): Extract<DurableRevisionRef, { readonly kind: "image" }> {
  return { kind: "image", editionId: "004", logicalId: "cover", revisionId: REVISION };
}

function compositionRef(): Extract<DurableRevisionRef, { readonly kind: "composition" }> {
  return { kind: "composition", editionId: "004", compositionId: "fresh-v2", revisionId: REVISION };
}

function manuscriptEntry(
  ref: Extract<DurableRevisionRef, { readonly kind: "article" | "editorial" }>,
  sourcePath: string,
  inputRevisions: readonly InputRevisionRef[],
): LegacyDurableMigrationPlan["entries"][number] {
  return {
    ref,
    createdAt: "2026-08-02T20:06:41.636Z",
    parentRevisionId: null,
    inputRevisions,
    files: [{ sourcePath, targetPath: "manuscript.md", mediaType: "text/markdown" }],
  };
}

function roleInputs(): Record<string, unknown> {
  const activeContracts: Readonly<Record<string, string>> = {
    composition_bootstrap: "composition-bootstrap/1",
    measure_edition: "measure-edition/1",
    render: "render-edition/1",
    render_inspection: "render-inspection/1",
  };
  const values: Record<string, unknown> = {};
  for (const role of KNOWN_WORK_ROLES) {
    if (activeContracts[role] !== undefined) {
      values[role] = { kind: "contract", contract_version: activeContracts[role] };
    } else if (role === "visual_review") {
      values[role] = {
        kind: "human",
        authority: "human",
        policy_revision: {
          kind: "policy",
          policy_id: "render-review",
          revision_id: REVISION,
        },
      };
    } else {
      values[role] = { kind: "disabled", reason: disabledReason(role) };
    }
  }
  return values;
}

function disabledReason(role: string): string {
  if (role === "writer" || role === "editorial_writer") return "bootstrap_existing_manuscripts";
  if (role === "translation_writer" || role === "language_review" || role === "language_fit") {
    return "bootstrap_existing_translations";
  }
  if (role === "cover_image" || role === "interior_image" || role === "select_art") {
    return "bootstrap_existing_images";
  }
  if (role === "release_approval") return "stop_unreleased";
  if (role === "render_reconciliation") return "bootstrap_forces_fresh_render";
  return role === "capture_source" || role === "extract_source" || role === "review_source"
    ? "bootstrap_committed_inputs"
    : "bootstrap_committed_composition";
}

async function gitBinding(
  root: string,
  paths: readonly string[],
): Promise<{ readonly commitOid: string; readonly blobOids: Readonly<Record<string, string>> }> {
  const commitOid = await git(root, ["rev-parse", "HEAD"]);
  const blobOids = Object.fromEntries(await Promise.all([...paths].sort().map(async (path) => [
    path,
    await git(root, ["rev-parse", `HEAD:${path}`]),
  ] as const)));
  return { commitOid, blobOids };
}

async function git(root: string, args: readonly string[]): Promise<string> {
  const result = await execFile("git", ["-C", root, ...args], { encoding: "utf8" });
  return result.stdout.trim();
}
