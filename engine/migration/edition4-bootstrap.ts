import { execFile as execFileCallback } from "node:child_process";
import { readFile } from "node:fs/promises";
import { basename, extname, posix, relative, resolve } from "node:path";
import { promisify } from "node:util";

import { parse, stringify } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import type {
  CompositionDocument,
  CompositionRevisionBinding,
  DurableRevisionRef,
  InputRevisionRef,
  LegacyDurableMigrationPlan,
  LegacyDurableRevisionEntry,
  LegacyInputMigrationPlan,
} from "../durable/index.ts";
import { edition4SelectedArtPaths } from "../fixtures/edition4.ts";

const execFile = promisify(execFileCallback);
const EDITION_ID = "004";
const EDITION_ROOT = "editions/004-the-systems-around-the-model";
const MIGRATION_ID = "edition4-fresh-v2";
const PROMPT_SET_ID = "fresh_v2_prompt_set";

const SOURCE_IDS = [
  "anatomy-of-a-frontier-lab-agent-intrusion-a-tech-8088c1df",
  "eval-engineering-the-step-that-turns-a-200-model-9f6f868f",
  "pragmatic-leverage-in-the-software-factory-09879736",
  "22580-from-gpt2-to-kimi3-explained-8f01b0fe",
  "architecture-overview-ce5cb1d1",
  "the-2026-07-28-mcp-specification-release-candida-1a1752b8",
  "software-factories-are-super-real-but-the-factor-ab8ad3ab",
  "factories-are-not-a-token-or-llm-problem-ba5fabbf",
  "do-not-make-the-service-bus-non-deterministic-3a92442c",
] as const;

const ARTICLE_IDS = [
  "frontier-lab-agent-intrusion",
  "eval-engineering",
  "pragmatic-leverage",
  "from-gpt2-to-kimi3",
  "factory-systems-problem",
  "mcp-in-a-nutshell",
  "mcp-protocol-update",
] as const;

const PROMPT_IDS = [
  "cover-art-candidates",
  "craft-review",
  "edition-review",
  "evidence-review",
  "faithful-edit",
  "faithful-synthesis",
  "in-a-nutshell",
  "mechanics-review",
  "opening-editorial",
  "shape-review",
  "teaching-review",
  "worth-review",
] as const;

const REVISION_IDS = [
  "rev_20260802T230000000Z_k53nh5xeumpz",
  "rev_20260802T230000001Z_qasyw5wztscv",
  "rev_20260802T230000002Z_fu55xgo3jx4a",
  "rev_20260802T230000003Z_vbxyqxotuugm",
  "rev_20260802T230000004Z_vkooja45s3ic",
  "rev_20260802T230000005Z_d3jdf4sucrfp",
  "rev_20260802T230000006Z_kyfnqaqayltu",
  "rev_20260802T230000007Z_ngft3xfbgzib",
  "rev_20260802T230000008Z_fuu6aytbkrfc",
  "rev_20260802T230000009Z_pnitcpinodrl",
  "rev_20260802T230000010Z_lt4zgvv4rf5n",
  "rev_20260802T230000011Z_tws2rukw26uc",
  "rev_20260802T230000012Z_q7nfhrrpiizm",
  "rev_20260802T230000013Z_xtdcxicbrsrw",
  "rev_20260802T230000014Z_3eoxg74rsw6f",
  "rev_20260802T230000015Z_exb6ila5bcjf",
  "rev_20260802T230000016Z_oa3hzaxnhkae",
  "rev_20260802T230000017Z_yplg2plpqd4a",
  "rev_20260802T230000018Z_pvdqmaipnmxj",
  "rev_20260802T230000019Z_fwfi5ddi3mru",
  "rev_20260802T230000020Z_lwwllzbsfftp",
  "rev_20260802T230000021Z_l2cblwvt2377",
  "rev_20260802T230000022Z_rafete5xuo7q",
  "rev_20260802T230000023Z_usfgg5a6f375",
  "rev_20260802T230000024Z_ev4sqevjeryq",
  "rev_20260802T230000025Z_tu2vw2w2vrcz",
  "rev_20260802T230000026Z_wnfh2ok36agc",
  "rev_20260802T230000027Z_3lmwetxgubwa",
  "rev_20260802T230000028Z_xbcule3r4ba7",
  "rev_20260802T230000029Z_ovzbke33tp7j",
  "rev_20260802T230000030Z_3yvkse32mq6z",
  "rev_20260802T230000031Z_ryqeuddxgzli",
  "rev_20260802T230000032Z_ydz3343qcwis",
  "rev_20260802T230000033Z_b2buhltexcey",
  "rev_20260802T230000034Z_nvdvmifoqlet",
  "rev_20260802T230000035Z_poyigg2sur72",
  "rev_20260802T230000036Z_h5olngknb7m4",
  "rev_20260802T230000037Z_zvh7vggje5fs",
  "rev_20260802T230000038Z_gljpurhpz2a2",
  "rev_20260802T230000039Z_3z5epujlhrg4",
  "rev_20260802T230000040Z_dbonnqzwxxoj",
  "rev_20260802T230000041Z_faq5uf6ybmd3",
  "rev_20260802T230000042Z_ijlzqdn2akcq",
  "rev_20260802T230000043Z_prf2suz5toh2",
  "rev_20260802T230000044Z_hlzpizoc4ncd",
  "rev_20260802T230000045Z_himjcmbrwz3c",
  "rev_20260802T230000046Z_p2orkjcw42u7",
  "rev_20260802T230000047Z_kj32cx2lgs54",
  "rev_20260802T230000048Z_r2en2c3aijtn",
  "rev_20260802T230000049Z_gzkugvvimnai",
  "rev_20260802T230000050Z_st4fqgtpcwqd",
  "rev_20260802T230000051Z_4yhjmtmbqohy",
  "rev_20260802T230000052Z_txj4db7zordq",
  "rev_20260802T230000053Z_7pcs4bj3w7g4",
  "rev_20260802T230000054Z_zhx3g4zhpfor",
  "rev_20260802T230000055Z_bbwuyjtf2sxd",
  "rev_20260802T230000056Z_vxv4c6xsm4bh",
  "rev_20260802T230000057Z_czv32wvq5vfh",
  "rev_20260802T230000058Z_rcyepzxovpxf",
  "rev_20260802T230000059Z_o4tqx3zfdqx3",
  "rev_20260802T230000060Z_3lkr2wkhk5vd",
  "rev_20260802T230000061Z_24acmz3cblej",
  "rev_20260802T230000062Z_qomqcv4kmony",
  "rev_20260802T230000063Z_g4qgy4kwqze4",
  "rev_20260802T230000064Z_nuozv3jq6crb",
  "rev_20260802T230000065Z_nn4pdbpswp3n",
] as unknown as readonly RevisionId[];

const captureRevisionIds = indexed(SOURCE_IDS, REVISION_IDS.slice(0, 9));
const extractionRevisionIds = indexed(SOURCE_IDS, REVISION_IDS.slice(9, 18));
const promptRevisionIds = indexed(PROMPT_IDS, REVISION_IDS.slice(18, 30));
const policyRevisionIds = {
  "review-bench": REVISION_IDS[30]!,
  "writing-rules": REVISION_IDS[31]!,
  "editorial-policy": REVISION_IDS[32]!,
  "render-review": REVISION_IDS[33]!,
} as const;
const editionSpecRevisionId = REVISION_IDS[34]!;
export const edition4RunBootstrapRevisionId = REVISION_IDS[35]!;
const articleEnRevisionIds = indexed(ARTICLE_IDS, REVISION_IDS.slice(36, 43));
const articleEsRevisionIds = indexed(ARTICLE_IDS, REVISION_IDS.slice(43, 50));
const editorialEnRevisionId = REVISION_IDS[50]!;
const editorialEsRevisionId = REVISION_IDS[51]!;
const imageRevisionIds = REVISION_IDS.slice(52, 65);
const compositionRevisionId = REVISION_IDS[65]!;

export type Edition4PhaseOnePlan = {
  readonly schemaVersion: "edition4-fresh-v2-plan/1";
  readonly sourceHeadCommitOid: string;
  readonly inputPlan: LegacyInputMigrationPlan;
  readonly durablePlan: LegacyDurableMigrationPlan;
  readonly counts: {
    readonly inputRevisions: 35;
    readonly durableRevisions: 30;
    readonly sourceCaptures: 9;
    readonly sourceExtractions: 9;
    readonly prompts: 12;
    readonly policies: 4;
    readonly articles: 14;
    readonly editorials: 2;
    readonly selectedImages: 13;
    readonly compositions: 1;
  };
};

export async function buildEdition4PhaseOnePlan(
  repositoryRoot: string,
): Promise<Edition4PhaseOnePlan> {
  const root = resolve(repositoryRoot);
  const editionPath = `${EDITION_ROOT}/edition.yaml`;
  const translationPath = `${EDITION_ROOT}/translations/es/edition.yaml`;
  const edition = mapping(parse(await readFile(resolve(root, editionPath), "utf8")), "edition");
  const translation = mapping(
    parse(await readFile(resolve(root, translationPath), "utf8")),
    "translation edition",
  );
  const inputEntries: LegacyInputMigrationPlan["entries"][number][] = [];

  for (const sourceId of SOURCE_IDS) {
    const prefix = `library/sources/${sourceId}`;
    const sourceFiles = await trackedUnder(root, prefix);
    const captureFiles = sourceFiles.filter((path) =>
      path === `${prefix}/record.yaml` ||
      path.startsWith(`${prefix}/raw/`) ||
      path.startsWith(`${prefix}/media/`)
    );
    if (!sourceFiles.includes(`${prefix}/extracted.md`) || captureFiles.length === 0) {
      throw new Error(`source ${sourceId} has no complete tracked capture and extraction`);
    }
    inputEntries.push({
      ref: sourceCaptureRef(sourceId),
      createdAt: createdAt(captureRevisionIds[sourceId]!),
      parentRevisionId: null,
      files: captureFiles.map((sourcePath) => ({
        sourcePath,
        targetPath: captureTarget(prefix, sourcePath),
        mediaType: mediaType(sourcePath),
      })),
    }, {
      ref: sourceExtractionRef(sourceId),
      createdAt: createdAt(extractionRevisionIds[sourceId]!),
      parentRevisionId: null,
      files: [{
        sourcePath: `${prefix}/extracted.md`,
        targetPath: "extracted.md",
        mediaType: "text/markdown",
      }],
    });
  }

  for (const promptId of PROMPT_IDS) {
    inputEntries.push({
      ref: promptRef(promptId),
      createdAt: createdAt(promptRevisionIds[promptId]!),
      parentRevisionId: null,
      files: [{
        sourcePath: `prompts/${promptId}.md`,
        targetPath: "prompt.md",
        mediaType: "text/markdown",
      }, {
        content: promptOutputSchema(promptId),
        generationBasis: `fresh_v2_prompt_set output contract for ${promptId}`,
        targetPath: "output.schema.json",
        mediaType: "application/json",
      }],
    });
  }

  const policySources = {
    "review-bench": "prompts/README.md",
    "writing-rules": "docs/WRITING_RULES.md",
    "editorial-policy": "docs/EDITORIAL_POLICY.md",
    "render-review": "docs/DESIGN_SYSTEM.md",
  } as const;
  for (const [policyId, sourcePath] of Object.entries(policySources)) {
    const revisionId = policyRevisionIds[policyId as keyof typeof policyRevisionIds];
    inputEntries.push({
      ref: policyRef(policyId, revisionId),
      createdAt: createdAt(revisionId),
      parentRevisionId: null,
      files: [{ sourcePath, targetPath: "policy.md", mediaType: "text/markdown" }],
    });
  }

  const editionSpecSources = [
    editionPath,
    translationPath,
    `${EDITION_ROOT}/art/illustrations.yaml`,
    "design/covers/canto-vivo/design.toml",
    "design/covers/canto-vivo/references/en.png",
    "design/covers/canto-vivo/references/es.png",
    "design/covers/canto-vivo/back-references/en.png",
    "design/covers/canto-vivo/back-references/es.png",
  ];
  inputEntries.push({
    ref: editionSpecRef(),
    createdAt: createdAt(editionSpecRevisionId),
    parentRevisionId: null,
    files: editionSpecSources.map((sourcePath) => ({
      sourcePath,
      targetPath: editionSpecTarget(sourcePath),
      mediaType: mediaType(sourcePath),
    })),
  });

  const inputSourcePaths = sourcePaths(inputEntries);
  const inputPlan: LegacyInputMigrationPlan = {
    schemaVersion: "legacy-input-migration/1",
    migrationId: MIGRATION_ID,
    sourceGitBinding: await gitBinding(root, inputSourcePaths),
    entries: inputEntries,
  };

  const articleSpecs = objectArray(edition.articles, "edition articles");
  const translatedById = new Map(objectArray(translation.articles, "translated articles").map(
    (value) => [requiredString(value, "id"), value],
  ));
  const durableEntries: LegacyDurableRevisionEntry[] = [];
  for (const articleId of ARTICLE_IDS) {
    const article = requiredById(articleSpecs, articleId);
    const translated = translatedById.get(articleId);
    if (translated === undefined) throw new Error(`missing Spanish article ${articleId}`);
    const sourceInputRefs = stringArray(article.source_ids, `${articleId} sources`).flatMap(
      (sourceId) => [sourceCaptureRef(sourceId), sourceExtractionRef(sourceId)],
    );
    const promptId = writerPrompt(requiredString(article, "content_mode"));
    const commonInputs = [
      editionSpecRef(),
      ...sourceInputRefs,
      promptRef(promptId),
      policyRef("writing-rules", policyRevisionIds["writing-rules"]),
      policyRef("editorial-policy", policyRevisionIds["editorial-policy"]),
    ];
    durableEntries.push(manuscriptEntry(
      articleRef(articleId, "en"),
      requiredString(article, "manuscript"),
      commonInputs,
    ), manuscriptEntry(
      articleRef(articleId, "es"),
      `${EDITION_ROOT}/translations/es/${requiredString(translated, "manuscript")}`,
      [
        editionSpecRef(),
        ...sourceInputRefs,
        policyRef("writing-rules", policyRevisionIds["writing-rules"]),
        policyRef("editorial-policy", policyRevisionIds["editorial-policy"]),
      ],
    ));
  }
  durableEntries.push(manuscriptEntry(
    editorialRef("en"),
    `${EDITION_ROOT}/manuscript/editorial.md`,
    [
      editionSpecRef(),
      promptRef("opening-editorial"),
      policyRef("writing-rules", policyRevisionIds["writing-rules"]),
      policyRef("editorial-policy", policyRevisionIds["editorial-policy"]),
    ],
  ), manuscriptEntry(
    editorialRef("es"),
    `${EDITION_ROOT}/translations/es/manuscript/editorial.md`,
    [
      editionSpecRef(),
      policyRef("writing-rules", policyRevisionIds["writing-rules"]),
      policyRef("editorial-policy", policyRevisionIds["editorial-policy"]),
    ],
  ));

  const selectedArtPaths = await edition4SelectedArtPaths(root);
  const imageInventory = imageEntries(articleSpecs, selectedArtPaths);
  if (imageInventory.length !== 13) throw new Error("Edition 4 must bind exactly 13 selected images");
  for (const image of imageInventory) {
    durableEntries.push({
      ref: image.ref,
      createdAt: createdAt(image.ref.revisionId),
      parentRevisionId: null,
      inputRevisions: [editionSpecRef()],
      files: [{
        sourcePath: image.sourcePath,
        targetPath: `image${canonicalImageExtension(image.sourcePath)}`,
        mediaType: mediaType(image.sourcePath),
      }],
    });
  }

  const document = compositionDocument(imageInventory);
  const compositionSources = [
    editionPath,
    translationPath,
    `${EDITION_ROOT}/art/illustrations.yaml`,
  ];
  const durableSourcePaths = uniqueSorted([
    ...durableEntries.flatMap((entry) => entry.files.map((file) => file.sourcePath)),
    ...compositionSources,
  ]);
  const durablePlan: LegacyDurableMigrationPlan = {
    schemaVersion: "legacy-durable-migration/1",
    migrationId: MIGRATION_ID,
    sourceGitBinding: await gitBinding(root, durableSourcePaths),
    entries: durableEntries,
    composition: {
      ref: compositionRef(),
      createdAt: createdAt(compositionRevisionId),
      parentRevisionId: null,
      sourcePaths: compositionSources,
      document,
    },
  };
  return {
    schemaVersion: "edition4-fresh-v2-plan/1",
    sourceHeadCommitOid: inputPlan.sourceGitBinding.commitOid,
    inputPlan,
    durablePlan,
    counts: {
      inputRevisions: 35,
      durableRevisions: 30,
      sourceCaptures: 9,
      sourceExtractions: 9,
      prompts: 12,
      policies: 4,
      articles: 14,
      editorials: 2,
      selectedImages: 13,
      compositions: 1,
    },
  };
}

export async function buildEdition4RunBootstrapPlan(
  repositoryRoot: string,
  binding: CompositionRevisionBinding,
): Promise<LegacyInputMigrationPlan> {
  if (JSON.stringify(binding.revisionRef) !== JSON.stringify(compositionRef())) {
    throw new Error("composition binding is not the planned Edition 4 fresh-v2 revision");
  }
  const root = resolve(repositoryRoot);
  const commitOid = await git(root, ["rev-parse", "HEAD"]);
  const bootstrap = {
    schema_version: 1,
    edition_id: EDITION_ID,
    composition_revision: {
      revision_ref: snakeDurableRef(binding.revisionRef),
      manifest_digest: binding.manifestDigest,
      git_commit_oid: binding.gitCommitOid,
      git_blob_oids: binding.gitBlobOids,
    },
    configured_languages: ["en", "es"],
    selected_image_revision_refs: compositionImageRefs().map(snakeDurableRef),
    image_generation_allowed: false,
    renderer_contract_version: "magazine-renderer/1",
    prompt_set: {
      id: PROMPT_SET_ID,
      role_inputs: bootstrapRoleInputs(),
    },
  };
  return {
    schemaVersion: "legacy-input-migration/1",
    migrationId: `${MIGRATION_ID}-bootstrap`,
    sourceGitBinding: { commitOid, blobOids: {} },
    entries: [{
      ref: runBootstrapRef(),
      createdAt: createdAt(edition4RunBootstrapRevisionId),
      parentRevisionId: null,
      files: [{
        content: stringify(bootstrap, { lineWidth: 0 }),
        generationBasis: "fresh v2 committed composition and exhaustive execution role bindings",
        targetPath: "bootstrap.yaml",
        mediaType: "application/yaml",
      }],
    }],
  };
}

export function edition4CompositionRef() {
  return compositionRef();
}

function sourceCaptureRef(sourceId: string): InputRevisionRef {
  return { kind: "source_capture", logicalId: sourceId, revisionId: captureRevisionIds[sourceId]! };
}

function sourceExtractionRef(sourceId: string): InputRevisionRef {
  return { kind: "source_extraction", logicalId: sourceId, revisionId: extractionRevisionIds[sourceId]! };
}

function promptRef(promptId: string): InputRevisionRef {
  const revisionId = promptRevisionIds[promptId];
  if (revisionId === undefined) throw new Error(`unknown prompt ${promptId}`);
  return { kind: "prompt", logicalId: promptId, revisionId };
}

function policyRef(policyId: string, revisionId: RevisionId): InputRevisionRef {
  return { kind: "policy", logicalId: policyId, revisionId };
}

function editionSpecRef(): InputRevisionRef {
  return {
    kind: "edition_spec",
    editionId: EDITION_ID,
    logicalId: "main",
    revisionId: editionSpecRevisionId,
  };
}

function runBootstrapRef(): Extract<InputRevisionRef, { readonly kind: "run_bootstrap" }> {
  return {
    kind: "run_bootstrap",
    editionId: EDITION_ID,
    logicalId: "fresh-v2",
    revisionId: edition4RunBootstrapRevisionId,
  };
}

function articleRef(
  articleId: string,
  language: "en" | "es",
): Extract<DurableRevisionRef, { readonly kind: "article" }> {
  return {
    kind: "article" as const,
    editionId: EDITION_ID,
    logicalId: articleId,
    language,
    revisionId: language === "en" ? articleEnRevisionIds[articleId]! : articleEsRevisionIds[articleId]!,
  };
}

function editorialRef(
  language: "en" | "es",
): Extract<DurableRevisionRef, { readonly kind: "editorial" }> {
  return {
    kind: "editorial" as const,
    editionId: EDITION_ID,
    logicalId: "opening",
    language,
    revisionId: language === "en" ? editorialEnRevisionId : editorialEsRevisionId,
  };
}

function compositionRef(): Extract<DurableRevisionRef, { readonly kind: "composition" }> {
  return {
    kind: "composition" as const,
    editionId: EDITION_ID,
    compositionId: "fresh-v2",
    revisionId: compositionRevisionId,
  };
}

function imageRefs(): readonly Extract<DurableRevisionRef, { readonly kind: "image" }>[] {
  const logicalIds = [
    "cover",
    ...ARTICLE_IDS.map((id) => `${id}-opener`),
    "factory-systems-problem-tail",
    "mcp-in-a-nutshell-tail",
    "closing-signal-gates",
    "closing-memory-rings",
    "closing-protocol-exchange",
  ];
  return logicalIds.map((logicalId, index) => ({
    kind: "image" as const,
    editionId: EDITION_ID,
    logicalId,
    revisionId: imageRevisionIds[index]!,
  }));
}

function compositionImageRefs(): readonly Extract<DurableRevisionRef, { readonly kind: "image" }>[] {
  const byLogicalId = new Map(imageRefs().map((ref) => [ref.logicalId, ref]));
  return [
    ...ARTICLE_IDS.flatMap((articleId) => [
      requiredImage(byLogicalId, `${articleId}-opener`),
      ...(articleId === "factory-systems-problem" || articleId === "mcp-in-a-nutshell"
        ? [requiredImage(byLogicalId, `${articleId}-tail`)]
        : []),
    ]),
    requiredImage(byLogicalId, "cover"),
    requiredImage(byLogicalId, "closing-signal-gates"),
    requiredImage(byLogicalId, "closing-memory-rings"),
    requiredImage(byLogicalId, "closing-protocol-exchange"),
  ];
}

function imageEntries(
  articleSpecs: readonly Record<string, unknown>[],
  selectedArtPaths: readonly string[],
) {
  const refs = imageRefs();
  const paths = [
    `${EDITION_ROOT}/art/cover-candidate-wildcard-v2.png`,
    ...ARTICLE_IDS.map((id) => requiredString(requiredById(articleSpecs, id).opener_art, "path")),
    `${EDITION_ROOT}/art/article-tails/factory-systems-problem.png`,
    `${EDITION_ROOT}/art/article-tails/mcp-four-vignettes.png`,
    `${EDITION_ROOT}/art/closing-signal-gates-manga.png`,
    `${EDITION_ROOT}/art/closing-memory-rings-manga.png`,
    `${EDITION_ROOT}/art/closing-protocol-exchange-manga.png`,
  ];
  if (!sameSet(new Set(paths), new Set(selectedArtPaths))) {
    throw new Error("selected image inventory disagrees with the Edition 4 fixture");
  }
  return refs.map((ref, index) => ({ ref, sourcePath: paths[index]! }));
}

function compositionDocument(
  images: ReturnType<typeof imageEntries>,
): CompositionDocument {
  const imageByLogical = new Map(images.map((image) => [image.ref.logicalId, image.ref]));
  return {
    schema_version: 1,
    edition_id: EDITION_ID,
    composition_id: "fresh-v2",
    editorials: [{
      editorial_id: "opening",
      manuscripts: [
        { language: "en", revision: editorialRef("en") },
        { language: "es", revision: editorialRef("es") },
      ],
    }],
    articles: ARTICLE_IDS.map((articleId) => ({
      article_id: articleId,
      manuscripts: [
        { language: "en", revision: articleRef(articleId, "en") },
        { language: "es", revision: articleRef(articleId, "es") },
      ],
      images: [
        { slot_id: "opener", revision: requiredImage(imageByLogical, `${articleId}-opener`) },
        ...(articleId === "factory-systems-problem" || articleId === "mcp-in-a-nutshell"
          ? [{ slot_id: "tail", revision: requiredImage(imageByLogical, `${articleId}-tail`) }]
          : []),
      ],
    })),
    images: images
      .filter((image) => image.ref.logicalId === "cover" || image.ref.logicalId.startsWith("closing-"))
      .map((image) => ({ slot_id: image.ref.logicalId, revision: image.ref })),
    layout_inputs: [{ slot_id: "edition-spec", revision: editionSpecRef() }],
  };
}

function manuscriptEntry(
  ref: Exclude<DurableRevisionRef, { readonly kind: "image" | "composition" }>,
  sourcePath: string,
  inputRevisions: readonly InputRevisionRef[],
): LegacyDurableRevisionEntry {
  return {
    ref,
    createdAt: createdAt(ref.revisionId),
    parentRevisionId: null,
    inputRevisions,
    files: [{ sourcePath, targetPath: "manuscript.md", mediaType: "text/markdown" }],
  };
}

function bootstrapRoleInputs(): Record<string, unknown> {
  const disabled = (reason: string) => ({ kind: "disabled", reason });
  return {
    capture_source: disabled("bootstrap_committed_inputs"),
    extract_source: disabled("bootstrap_committed_inputs"),
    review_source: disabled("bootstrap_committed_inputs"),
    close_collection: disabled("bootstrap_committed_composition"),
    plan_edition: disabled("bootstrap_committed_composition"),
    writer: disabled("bootstrap_existing_manuscripts"),
    measure_article: disabled("bootstrap_committed_composition"),
    worth: disabled("bootstrap_committed_composition"),
    mechanics: disabled("bootstrap_committed_composition"),
    evidence: disabled("bootstrap_committed_composition"),
    shape: disabled("bootstrap_committed_composition"),
    teaching: disabled("bootstrap_committed_composition"),
    craft: disabled("bootstrap_committed_composition"),
    editorial_writer: disabled("bootstrap_existing_manuscripts"),
    edition_review: disabled("bootstrap_committed_composition"),
    translation_writer: disabled("bootstrap_existing_translations"),
    language_review: disabled("bootstrap_existing_translations"),
    language_fit: disabled("bootstrap_existing_translations"),
    cover_image: disabled("bootstrap_existing_images"),
    interior_image: disabled("bootstrap_existing_images"),
    select_art: disabled("bootstrap_existing_images"),
    measure_edition: { kind: "contract", contract_version: "measure-edition/1" },
    render: { kind: "contract", contract_version: "render-edition/1" },
    render_reconciliation: disabled("bootstrap_forces_fresh_render"),
    render_inspection: { kind: "contract", contract_version: "render-inspection/1" },
    visual_review: {
      kind: "human",
      authority: "human",
      policy_revision: snakeInputRef(policyRef("render-review", policyRevisionIds["render-review"])),
    },
    release_approval: disabled("stop_unreleased"),
    durable_checkpoint: disabled("bootstrap_committed_composition"),
    composition_bootstrap: { kind: "contract", contract_version: "composition-bootstrap/1" },
    editor_decision: disabled("bootstrap_committed_composition"),
  };
}

function snakeInputRef(ref: InputRevisionRef): Record<string, unknown> {
  if (ref.kind === "prompt") {
    return { kind: "prompt", prompt_id: ref.logicalId, revision_id: ref.revisionId };
  }
  if (ref.kind === "policy") {
    return { kind: "policy", policy_id: ref.logicalId, revision_id: ref.revisionId };
  }
  return {
    kind: ref.kind,
    logical_id: ref.logicalId,
    ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }),
    revision_id: ref.revisionId,
  };
}

function snakeDurableRef(ref: DurableRevisionRef): Record<string, unknown> {
  return ref.kind === "composition"
    ? {
        kind: "composition",
        edition_id: ref.editionId,
        composition_id: ref.compositionId,
        revision_id: ref.revisionId,
      }
    : {
        kind: ref.kind,
        edition_id: ref.editionId,
        logical_id: ref.logicalId,
        ...(ref.language === undefined ? {} : { language: ref.language }),
        revision_id: ref.revisionId,
      };
}

function writerPrompt(contentMode: string): typeof PROMPT_IDS[number] {
  switch (contentMode) {
    case "faithful_edit": return "faithful-edit";
    case "faithful_synthesis": return "faithful-synthesis";
    case "in_a_nutshell": return "in-a-nutshell";
    default: throw new Error(`Edition 4 has unsupported content mode ${contentMode}`);
  }
}

function promptOutputSchema(promptId: string): string {
  const markdown = new Set([
    "faithful-edit",
    "faithful-synthesis",
    "in-a-nutshell",
    "opening-editorial",
  ]).has(promptId);
  return `${JSON.stringify({
    $schema: "https://json-schema.org/draft/2020-12/schema",
    title: `${promptId} output`,
    ...(markdown
      ? { type: "string", contentMediaType: "text/markdown" }
      : { type: "object", additionalProperties: true }),
  }, null, 2)}\n`;
}

function sourcePaths(entries: LegacyInputMigrationPlan["entries"]): string[] {
  return uniqueSorted(entries.flatMap((entry) => entry.files.flatMap((file) =>
    file.sourcePath === undefined ? [] : [file.sourcePath]
  )));
}

async function trackedUnder(root: string, prefix: string): Promise<string[]> {
  const output = await gitRaw(root, ["ls-files", "-z", "--", prefix]);
  return output.split("\0").filter(Boolean).sort();
}

async function gitBinding(root: string, paths: readonly string[]) {
  const commitOid = await git(root, ["rev-parse", "HEAD"]);
  const output = await gitRaw(root, ["ls-files", "-s", "-z", "--", ...paths]);
  const blobOids: Record<string, string> = {};
  for (const entry of output.split("\0").filter(Boolean)) {
    const matched = /^\d+ ([0-9a-f]{40,64}) \d\t(.+)$/u.exec(entry);
    if (matched === null) throw new Error(`cannot parse Git index entry ${entry}`);
    blobOids[matched[2]!] = matched[1]!;
  }
  if (!sameSet(new Set(paths), new Set(Object.keys(blobOids)))) {
    throw new Error("Git binding does not cover the exact migration source path set");
  }
  return { commitOid, blobOids: Object.fromEntries(Object.entries(blobOids).sort()) };
}

async function git(root: string, args: readonly string[]): Promise<string> {
  return (await gitRaw(root, args)).trim();
}

async function gitRaw(root: string, args: readonly string[]): Promise<string> {
  const result = await execFile("git", ["-C", root, ...args], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  return result.stdout;
}

function captureTarget(prefix: string, sourcePath: string): string {
  const local = posix.relative(prefix, sourcePath);
  if (local === "record.yaml") return "raw/record.yaml";
  if (local.startsWith("raw/")) return `raw/captures/${local.slice(4)}`;
  if (local.startsWith("media/")) return `raw/media/${local.slice(6)}`;
  throw new Error(`unsupported capture source path ${sourcePath}`);
}

function editionSpecTarget(sourcePath: string): string {
  if (sourcePath === `${EDITION_ROOT}/edition.yaml`) return "edition.yaml";
  if (sourcePath.startsWith(`${EDITION_ROOT}/`)) return sourcePath.slice(EDITION_ROOT.length + 1);
  return sourcePath;
}

function mediaType(path: string): string {
  switch (extname(path).toLowerCase()) {
    case ".md": return "text/markdown";
    case ".yaml":
    case ".yml": return "application/yaml";
    case ".json": return "application/json";
    case ".toml": return "application/toml";
    case ".txt": return "text/plain";
    case ".pdf": return "application/pdf";
    case ".png": return "image/png";
    case ".jpg":
    case ".jpeg": return "image/jpeg";
    case ".svg": return "image/svg+xml";
    case ".webp": return "image/webp";
    default: return "application/octet-stream";
  }
}

function canonicalImageExtension(path: string): string {
  const extension = extname(path).toLowerCase();
  if (![".jpg", ".png", ".svg", ".webp"].includes(extension)) {
    throw new Error(`unsupported selected image extension ${path}`);
  }
  return extension;
}

function createdAt(revisionId: RevisionId): string {
  const matched = /^rev_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z_/u.exec(revisionId);
  if (matched === null) throw new Error(`invalid planned RevisionId ${revisionId}`);
  return `${matched[1]}-${matched[2]}-${matched[3]}T${matched[4]}:${matched[5]}:${matched[6]}.${matched[7]}Z`;
}

function indexed(keys: readonly string[], values: readonly RevisionId[]): Record<string, RevisionId> {
  if (keys.length !== values.length) throw new Error("revision allocation count mismatch");
  return Object.fromEntries(keys.map((key, index) => [key, values[index]!])) as Record<string, RevisionId>;
}

function mapping(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be a mapping`);
  }
  return value as Record<string, unknown>;
}

function objectArray(value: unknown, label: string): readonly Record<string, unknown>[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  return value.map((item, index) => mapping(item, `${label}[${index}]`));
}

function stringArray(value: unknown, label: string): readonly string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error(`${label} must be a string array`);
  }
  return value as readonly string[];
}

function requiredString(value: unknown, key: string): string {
  const object = mapping(value, key);
  const result = object[key];
  if (typeof result !== "string") throw new Error(`${key} must be a string`);
  return result;
}

function requiredById(
  values: readonly Record<string, unknown>[],
  id: string,
): Record<string, unknown> {
  const value = values.find((candidate) => candidate.id === id);
  if (value === undefined) throw new Error(`missing item ${id}`);
  return value;
}

function requiredImage(
  values: ReadonlyMap<string, Extract<DurableRevisionRef, { readonly kind: "image" }>>,
  logicalId: string,
) {
  const value = values.get(logicalId);
  if (value === undefined) throw new Error(`missing selected image ${logicalId}`);
  return value;
}

function uniqueSorted(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

function sameSet(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  return left.size === right.size && [...left].every((value) => right.has(value));
}
