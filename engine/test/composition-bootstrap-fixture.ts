import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

import { stringify } from "yaml";

import type {
  ArtifactId,
  PromotionId,
  RevisionId,
  RunId,
} from "../contracts/index.ts";
import { KNOWN_WORK_ROLES } from "../contracts/index.ts";
import {
  durableRevisionRelativeDirectory,
  inputRevisionRelativeDirectory,
  type DurableGit,
  type DurableRevisionRef,
  type InputRevisionRef,
} from "../durable/index.ts";

export const BOOTSTRAP_FIXTURE_REVISION =
  "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;

export const BOOTSTRAP_FIXTURE_REF = {
  kind: "run_bootstrap",
  editionId: "004",
  logicalId: "run-bootstrap",
  revisionId: BOOTSTRAP_FIXTURE_REVISION,
} as const;

export const BOOTSTRAP_FIXTURE_COMPOSITION_REF = {
  kind: "composition",
  editionId: "004",
  compositionId: "fresh-v2",
  revisionId: BOOTSTRAP_FIXTURE_REVISION,
} as const;

export type CompositionBootstrapRepositoryFixture = {
  readonly bootstrapRevision: typeof BOOTSTRAP_FIXTURE_REF;
  readonly compositionRevision: typeof BOOTSTRAP_FIXTURE_COMPOSITION_REF;
  readonly coverRevision: Extract<DurableRevisionRef, { readonly kind: "image" }>;
  readonly bootstrapDocument: Record<string, unknown>;
};

/**
 * Writes one complete, physically resolvable bootstrap graph beneath a test
 * repository root. Git authority remains a separately injected narrow seam.
 */
export async function writeCompositionBootstrapRepositoryFixture(
  repositoryRoot: string,
): Promise<CompositionBootstrapRepositoryFixture> {
  const editorialEn = manuscript("editorial", "opening", "en");
  const editorialEs = manuscript("editorial", "opening", "es");
  const articleEn = manuscript("article", "model-systems", "en");
  const articleEs = manuscript("article", "model-systems", "es");
  const coverRevision = {
    kind: "image",
    editionId: "004",
    logicalId: "cover",
    revisionId: BOOTSTRAP_FIXTURE_REVISION,
  } as const;
  const editionSpec = {
    kind: "edition_spec",
    editionId: "004",
    logicalId: "edition",
    revisionId: BOOTSTRAP_FIXTURE_REVISION,
  } as const;
  await Promise.all([
    writeDurable(repositoryRoot, editorialEn, "manuscript.md", "# Opening\n"),
    writeDurable(repositoryRoot, editorialEs, "manuscript.md", "# Apertura\n"),
    writeDurable(repositoryRoot, articleEn, "manuscript.md", "# Systems\n"),
    writeDurable(repositoryRoot, articleEs, "manuscript.md", "# Sistemas\n"),
    writeDurable(
      repositoryRoot,
      coverRevision,
      "image.png",
      Buffer.from("89504e470d0a1a0a", "hex"),
    ),
    writeInput(repositoryRoot, editionSpec, "edition.yaml", "edition_id: '004'\n"),
    writeVisualReviewPolicy(repositoryRoot),
  ]);

  const compositionDocument = {
    schema_version: 1,
    edition_id: "004",
    composition_id: BOOTSTRAP_FIXTURE_COMPOSITION_REF.compositionId,
    editorials: [{
      editorial_id: "opening",
      manuscripts: [
        { language: "en", revision: editorialEn },
        { language: "es", revision: editorialEs },
      ],
    }],
    articles: [{
      article_id: "model-systems",
      manuscripts: [
        { language: "en", revision: articleEn },
        { language: "es", revision: articleEs },
      ],
      images: [],
    }],
    images: [{ slot_id: "cover", revision: coverRevision }],
    layout_inputs: [{ slot_id: "edition-spec", revision: editionSpec }],
  };
  await writeDurable(
    repositoryRoot,
    BOOTSTRAP_FIXTURE_COMPOSITION_REF,
    "composition.yaml",
    stringify(compositionDocument, { lineWidth: 0 }),
  );

  const compositionDirectory = join(
    "durable",
    durableRevisionRelativeDirectory(BOOTSTRAP_FIXTURE_COMPOSITION_REF),
  );
  const bootstrapDocument = {
    schema_version: 1,
    edition_id: "004",
    composition_revision: {
      revision_ref: {
        kind: "composition",
        edition_id: "004",
        composition_id: BOOTSTRAP_FIXTURE_COMPOSITION_REF.compositionId,
        revision_id: BOOTSTRAP_FIXTURE_REVISION,
      },
      manifest_digest: digest(await readFile(
        join(repositoryRoot, compositionDirectory, "manifest.yaml"),
      )),
      git_commit_oid: "a".repeat(40),
      git_blob_oids: Object.fromEntries([
        join(compositionDirectory, "composition.yaml"),
        join(compositionDirectory, "manifest.yaml"),
      ].sort().map((path) => [path, "b".repeat(40)])),
    },
    configured_languages: ["en", "es"],
    selected_image_revision_refs: [{
      kind: "image",
      edition_id: "004",
      logical_id: "cover",
      revision_id: BOOTSTRAP_FIXTURE_REVISION,
    }],
    image_generation_allowed: false,
    renderer_contract_version: "magazine-renderer/1",
    prompt_set: {
      id: "fresh-v2-prompt-set",
      role_inputs: bootstrapRoleInputs(),
    },
  };
  await writeInput(
    repositoryRoot,
    BOOTSTRAP_FIXTURE_REF,
    "bootstrap.yaml",
    stringify(bootstrapDocument, { lineWidth: 0 }),
  );
  return {
    bootstrapRevision: BOOTSTRAP_FIXTURE_REF,
    compositionRevision: BOOTSTRAP_FIXTURE_COMPOSITION_REF,
    coverRevision,
    bootstrapDocument,
  };
}

export function committedFixtureGit(): Pick<DurableGit, "assertCommitted"> {
  return { assertCommitted: async () => {} };
}

function bootstrapRoleInputs(): Record<string, unknown> {
  const contracts: Record<string, string> = {
    measure_edition: "measure-edition/1",
    render: "render-edition/1",
    render_inspection: "render-inspection/1",
    composition_bootstrap: "composition-bootstrap/1",
  };
  const disabled: Record<string, string> = {
    capture_source: "bootstrap_committed_inputs",
    extract_source: "bootstrap_committed_inputs",
    review_source: "bootstrap_committed_inputs",
    close_collection: "bootstrap_committed_composition",
    plan_edition: "bootstrap_committed_composition",
    writer: "bootstrap_existing_manuscripts",
    measure_article: "bootstrap_committed_composition",
    worth: "bootstrap_committed_composition",
    mechanics: "bootstrap_committed_composition",
    evidence: "bootstrap_committed_composition",
    shape: "bootstrap_committed_composition",
    teaching: "bootstrap_committed_composition",
    craft: "bootstrap_committed_composition",
    editorial_writer: "bootstrap_existing_manuscripts",
    edition_review: "bootstrap_committed_composition",
    translation_writer: "bootstrap_existing_translations",
    language_review: "bootstrap_existing_translations",
    language_fit: "bootstrap_existing_translations",
    cover_image: "bootstrap_existing_images",
    interior_image: "bootstrap_existing_images",
    select_art: "bootstrap_existing_images",
    render_reconciliation: "bootstrap_forces_fresh_render",
    release_approval: "stop_unreleased",
    durable_checkpoint: "bootstrap_committed_composition",
    editor_decision: "bootstrap_committed_composition",
  };
  return Object.fromEntries(KNOWN_WORK_ROLES.map((role) => {
    const contractVersion = contracts[role];
    if (contractVersion !== undefined) {
      return [role, { kind: "contract", contract_version: contractVersion }];
    }
    if (role === "visual_review") {
      return [role, {
        kind: "human",
        authority: "human",
        policy_revision: {
          kind: "policy",
          policy_id: "render-review",
          revision_id: BOOTSTRAP_FIXTURE_REVISION,
        },
      }];
    }
    const reason = disabled[role];
    if (reason === undefined) {
      throw new Error(`bootstrap fixture lacks role authority for ${role}`);
    }
    return [role, { kind: "disabled", reason }];
  }));
}

async function writeVisualReviewPolicy(repositoryRoot: string): Promise<void> {
  await writeInput(repositoryRoot, {
    kind: "policy",
    logicalId: "render-review",
    revisionId: BOOTSTRAP_FIXTURE_REVISION,
  }, "policy.md", "Review the exact original-resolution render.\n");
}

async function writeInput(
  repositoryRoot: string,
  ref: InputRevisionRef,
  payloadPath: string,
  contents: string,
): Promise<void> {
  const directory = join(repositoryRoot, "inputs", inputRevisionRelativeDirectory(ref));
  const bytes = Buffer.from(contents);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadPath), bytes);
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: ref.kind,
    logical_id: ref.logicalId,
    ...(ref.kind === "edition_spec" || ref.kind === "run_bootstrap"
      ? { edition_id: ref.editionId }
      : {}),
    revision_id: ref.revisionId,
    created_at: "2026-08-02T20:06:41.636Z",
    parent_revision_id: null,
    files: [fileRecord(
      payloadPath,
      payloadPath.endsWith(".md") ? "text/markdown" : "application/yaml",
      bytes,
    )],
  }, { lineWidth: 0 }));
}

async function writeDurable(
  repositoryRoot: string,
  ref: DurableRevisionRef,
  payloadPath: string,
  contents: string | Buffer,
): Promise<void> {
  const directory = join(repositoryRoot, "durable", durableRevisionRelativeDirectory(ref));
  const bytes = Buffer.isBuffer(contents) ? contents : Buffer.from(contents);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadPath), bytes);
  const identity = ref.kind === "composition"
    ? { composition_id: ref.compositionId }
    : {
        logical_id: ref.logicalId,
        ...(ref.kind === "image" ? {} : { language: ref.language }),
      };
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: ref.kind,
    edition_id: ref.editionId,
    ...identity,
    revision_id: ref.revisionId,
    created_at: "2026-08-02T20:06:41.636Z",
    parent_revision_id: null,
    provenance_kind: "engine_promotion",
    promotion_id: "promotion_fixture" as PromotionId,
    producing_run_id: "run_fixture" as RunId,
    accepted_engine_artifact_ids: ["art_fixture" as ArtifactId],
    decision_engine_artifact_ids: ["art_decision" as ArtifactId],
    input_revisions: [],
    input_engine_artifact_ids: [],
    files: [fileRecord(
      payloadPath,
      payloadPath.endsWith(".md")
        ? "text/markdown"
        : payloadPath.endsWith(".png")
          ? "image/png"
          : "application/yaml",
      bytes,
      true,
    )],
  }, { lineWidth: 0 }));
}

function manuscript(
  kind: "article" | "editorial",
  logicalId: string,
  language: string,
): DurableRevisionRef {
  return {
    kind,
    editionId: "004",
    logicalId,
    language,
    revisionId: BOOTSTRAP_FIXTURE_REVISION,
  };
}

function fileRecord(
  path: string,
  mediaType: string,
  bytes: Buffer,
  durable = false,
): Record<string, unknown> {
  return {
    path,
    ...(durable
      ? { mediaType, sizeBytes: bytes.byteLength, engineArtifactId: "art_fixture" }
      : { media_type: mediaType, size_bytes: bytes.byteLength }),
    sha256: digest(bytes),
  };
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}
