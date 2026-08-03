import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { stringify } from "yaml";

import type { ArtifactId, PromotionId, RevisionId, RunId, WorkOfferView } from "../contracts/index.ts";
import { KNOWN_WORK_ROLES } from "../contracts/index.ts";
import {
  durableRevisionRelativeDirectory,
  inputRevisionRelativeDirectory,
  type DurableGit,
  type DurableRevisionRef,
  type InputRevisionRef,
} from "../durable/index.ts";
import {
  CompositionBootstrapExecutor,
  resolveCompositionBootstrap,
} from "../executors/index.ts";

const REVISION = "rev_20260802T200641636Z_aaaaaaaaaaaa" as RevisionId;
const BOOTSTRAP = {
  kind: "run_bootstrap",
  editionId: "004",
  logicalId: "fresh-v2",
  revisionId: REVISION,
} as const;

test("composition bootstrap executor resolves only the declared committed composition and role authority", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-composition-bootstrap-"));
  try {
    const fixture = await writeFixture(root);
    const asserted: string[][] = [];
    const git: Pick<DurableGit, "assertCommitted"> = {
      assertCommitted: async (paths) => { asserted.push([...paths]); },
    };
    const resolved = await resolveCompositionBootstrap(root, BOOTSTRAP, git);
    assert.deepEqual(resolved.configuredLanguages, ["en", "es"]);
    assert.deepEqual(resolved.selectedImageRevisionRefs, [fixture.cover]);
    assert.equal(resolved.imageGenerationAllowed, false);
    assert.equal(resolved.rendererContractVersion, "magazine-renderer/1");
    assert.equal(resolved.promptSet.roleInputs.writer.kind, "disabled");
    assert.equal(resolved.promptSet.roleInputs.cover_image.kind, "disabled");
    assert.ok(asserted.some((paths) => paths.some((path) => path.endsWith("bootstrap.yaml"))));

    const executor = new CompositionBootstrapExecutor({ repositoryRoot: root, git });
    const answer = await executor.execute({
      claim: {} as never,
      offer: {
        role: "composition_bootstrap",
        contractVersion: "composition-bootstrap/1",
        taskArtifactId: "art-bootstrap-task" as ArtifactId,
      } as WorkOfferView,
      artifacts: {
        readBytes: async () => Buffer.alloc(0),
        readText: async () => JSON.stringify({
          requestKind: "composition_bootstrap",
          actorKey: "edition",
          subjectArtifactId: null,
          inputArtifactIds: ["art-render-assembly"],
          choices: ["verify"],
          allowedChoices: ["verify"],
          bootstrapRevision: BOOTSTRAP,
          imageGenerationAllowed: false,
        }),
      },
      signal: new AbortController().signal,
    });
    assert.deepEqual(answer.artifacts[0]?.payload, { kind: "json", value: answer.result });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("composition bootstrap rejects image-generation enablement before it can become an authority input", async () => {
  const root = await mkdtemp(join(tmpdir(), "mag-composition-bootstrap-invalid-"));
  try {
    const fixture = await writeFixture(root);
    await writeInput(root, BOOTSTRAP, "bootstrap.yaml", stringify({
      ...fixture.bootstrapDocument,
      image_generation_allowed: true,
    }, { lineWidth: 0 }));
    await assert.rejects(
      resolveCompositionBootstrap(root, BOOTSTRAP, committedGit()),
      /image_generation_allowed/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

async function writeFixture(root: string): Promise<{
  readonly cover: Extract<DurableRevisionRef, { readonly kind: "image" }>;
  readonly bootstrapDocument: Record<string, unknown>;
}> {
  const editorialEn = manuscript("editorial", "opening", "en");
  const editorialEs = manuscript("editorial", "opening", "es");
  const articleEn = manuscript("article", "model-systems", "en");
  const articleEs = manuscript("article", "model-systems", "es");
  const cover = { kind: "image", editionId: "004", logicalId: "cover", revisionId: REVISION } as const;
  const composition = {
    kind: "composition",
    editionId: "004",
    compositionId: "fresh-v2",
    revisionId: REVISION,
  } as const;
  const editionSpec = {
    kind: "edition_spec",
    editionId: "004",
    logicalId: "edition",
    revisionId: REVISION,
  } as const;
  await Promise.all([
    writeDurable(root, editorialEn, "manuscript.md", "# Opening\n"),
    writeDurable(root, editorialEs, "manuscript.md", "# Apertura\n"),
    writeDurable(root, articleEn, "manuscript.md", "# Systems\n"),
    writeDurable(root, articleEs, "manuscript.md", "# Sistemas\n"),
    writeDurable(root, cover, "image.png", Buffer.from("89504e470d0a1a0a", "hex")),
    writeInput(root, editionSpec, "edition.yaml", "edition_id: '004'\n"),
  ]);
  const compositionDocument = {
    schema_version: 1,
    edition_id: "004",
    composition_id: "fresh-v2",
    editorials: [{ editorial_id: "opening", manuscripts: [
      { language: "en", revision: editorialEn }, { language: "es", revision: editorialEs },
    ] }],
    articles: [{ article_id: "model-systems", manuscripts: [
      { language: "en", revision: articleEn }, { language: "es", revision: articleEs },
    ], images: [] }],
    images: [{ slot_id: "cover", revision: cover }],
    layout_inputs: [{ slot_id: "edition-spec", revision: editionSpec }],
  };
  await writeDurable(root, composition, "composition.yaml", stringify(compositionDocument, { lineWidth: 0 }));
  const compositionDirectory = join("durable", durableRevisionRelativeDirectory(composition));
  const roleInputs = await writeRoleInputs(root);
  const bootstrapDocument = {
    schema_version: 1,
    edition_id: "004",
    composition_revision: {
      revision_ref: {
        kind: "composition",
        edition_id: "004",
        composition_id: "fresh-v2",
        revision_id: REVISION,
      },
      manifest_digest: digest(await readFile(join(root, compositionDirectory, "manifest.yaml"))),
      git_commit_oid: "a".repeat(40),
      git_blob_oids: Object.fromEntries([
        join(compositionDirectory, "composition.yaml"),
        join(compositionDirectory, "manifest.yaml"),
      ].sort().map((path) => [path, "b".repeat(40)])),
    },
    configured_languages: ["en", "es"],
    selected_image_revision_refs: [{
      kind: "image", edition_id: "004", logical_id: "cover", revision_id: REVISION,
    }],
    image_generation_allowed: false,
    renderer_contract_version: "magazine-renderer/1",
    prompt_set: { id: "fresh-v2-prompt-set", role_inputs: roleInputs },
  };
  await writeInput(root, BOOTSTRAP, "bootstrap.yaml", stringify(bootstrapDocument, { lineWidth: 0 }));
  return { cover, bootstrapDocument };
}

async function writeRoleInputs(root: string): Promise<Record<string, unknown>> {
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
  const inputs: Record<string, unknown> = {};
  for (const role of KNOWN_WORK_ROLES) {
    if (contracts[role] !== undefined) {
      inputs[role] = { kind: "contract", contract_version: contracts[role] };
    } else if (role === "visual_review") {
      await writeInput(root, {
        kind: "policy",
        logicalId: "render-review",
        revisionId: REVISION,
      }, "policy.md", "Review the exact original-resolution render.\n");
      inputs[role] = {
        kind: "human",
        authority: "human",
        policy_revision: { kind: "policy", policy_id: "render-review", revision_id: REVISION },
      };
    } else if (disabled[role] !== undefined) {
      inputs[role] = { kind: "disabled", reason: disabled[role] };
    } else {
      throw new Error(`fixture lacks role input for ${role}`);
    }
  }
  return inputs;
}

async function writeInput(
  root: string,
  ref: InputRevisionRef,
  payloadPath: string,
  contents: string,
): Promise<void> {
  const directory = join(root, "inputs", inputRevisionRelativeDirectory(ref));
  const bytes = Buffer.from(contents);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadPath), bytes);
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1,
    revision_kind: ref.kind,
    logical_id: ref.logicalId,
    ...(ref.kind === "edition_spec" || ref.kind === "run_bootstrap" ? { edition_id: ref.editionId } : {}),
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
  root: string,
  ref: DurableRevisionRef,
  payloadPath: string,
  contents: string | Buffer,
): Promise<void> {
  const directory = join(root, "durable", durableRevisionRelativeDirectory(ref));
  const bytes = Buffer.isBuffer(contents) ? contents : Buffer.from(contents);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, payloadPath), bytes);
  const identity = ref.kind === "composition"
    ? { composition_id: ref.compositionId }
    : { logical_id: ref.logicalId, ...(ref.kind === "image" ? {} : { language: ref.language }) };
  await writeFile(join(directory, "manifest.yaml"), stringify({
    schema_version: 1, revision_kind: ref.kind, edition_id: ref.editionId, ...identity,
    revision_id: ref.revisionId, created_at: "2026-08-02T20:06:41.636Z", parent_revision_id: null,
    provenance_kind: "engine_promotion", promotion_id: "promotion_fixture" as PromotionId,
    producing_run_id: "run_fixture" as RunId,
    accepted_engine_artifact_ids: ["art_fixture" as ArtifactId],
    decision_engine_artifact_ids: ["art_decision" as ArtifactId],
    input_revisions: [], input_engine_artifact_ids: [],
    files: [fileRecord(payloadPath, payloadPath.endsWith(".md") ? "text/markdown" :
      payloadPath.endsWith(".png") ? "image/png" : "application/yaml", bytes, true)],
  }, { lineWidth: 0 }));
}

function manuscript(kind: "article" | "editorial", logicalId: string, language: string): DurableRevisionRef {
  return { kind, editionId: "004", logicalId, language, revisionId: REVISION };
}

function fileRecord(path: string, mediaType: string, bytes: Buffer, durable = false): Record<string, unknown> {
  return {
    path,
    ...(durable ? { mediaType, sizeBytes: bytes.byteLength, engineArtifactId: "art_fixture" } : {
      media_type: mediaType, size_bytes: bytes.byteLength,
    }),
    sha256: digest(bytes),
  };
}

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function committedGit(): Pick<DurableGit, "assertCommitted"> {
  return { assertCommitted: async () => {} };
}
