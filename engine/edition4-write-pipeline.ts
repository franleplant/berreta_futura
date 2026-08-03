import { stringify } from "yaml";

import type { RevisionId } from "./contracts/index.ts";
import {
  materializeNativeInputRevision,
  newRevisionId,
  type InputRevisionRef,
  type MaterializedNativeInputRevision,
} from "./durable/index.ts";

const EDITION_SPEC = input("edition_spec", "main", "rev_20260802T230000034Z_nvdvmifoqlet", "004");
const WRITING_RULES = input("policy", "writing-rules", "rev_20260802T230000031Z_ryqeuddxgzli");
const REVIEW_BENCH = input("policy", "review-bench", "rev_20260803T052536962Z_q6bfqbkwpe4h");
const EDITORIAL_POLICY = input("policy", "editorial-policy", "rev_20260802T230000032Z_ydz3343qcwis");
const PROMPTS = {
  edit: input("prompt", "faithful-edit", "rev_20260802T230000022Z_rafete5xuo7q"),
  synthesis: input("prompt", "faithful-synthesis", "rev_20260802T230000023Z_usfgg5a6f375"),
  opening: input("prompt", "opening-editorial", "rev_20260802T230000026Z_wnfh2ok36agc"),
  evidence: input("prompt", "evidence-review", "rev_20260802T230000021Z_l2cblwvt2377"),
  worth: input("prompt", "worth-review", "rev_20260802T230000029Z_ovzbke33tp7j"),
  craft: input("prompt", "craft-review", "rev_20260802T230000019Z_fwfi5ddi3mru"),
};

const SOURCES = [
  source("anatomy-of-a-frontier-lab-agent-intrusion-a-tech-8088c1df", "rev_20260802T230000000Z_k53nh5xeumpz", "rev_20260802T230000009Z_pnitcpinodrl"),
  source("eval-engineering-the-step-that-turns-a-200-model-9f6f868f", "rev_20260802T230000001Z_qasyw5wztscv", "rev_20260802T230000010Z_lt4zgvv4rf5n"),
  source("pragmatic-leverage-in-the-software-factory-09879736", "rev_20260802T230000002Z_fu55xgo3jx4a", "rev_20260802T230000011Z_tws2rukw26uc"),
  source("22580-from-gpt2-to-kimi3-explained-8f01b0fe", "rev_20260802T230000003Z_vbxyqxotuugm", "rev_20260802T230000012Z_q7nfhrrpiizm"),
  source("architecture-overview-ce5cb1d1", "rev_20260802T230000004Z_vkooja45s3ic", "rev_20260802T230000013Z_xtdcxicbrsrw"),
  source("the-2026-07-28-mcp-specification-release-candida-1a1752b8", "rev_20260802T230000005Z_d3jdf4sucrfp", "rev_20260802T230000014Z_3eoxg74rsw6f"),
  source("software-factories-are-super-real-but-the-factor-ab8ad3ab", "rev_20260802T230000006Z_kyfnqaqayltu", "rev_20260802T230000015Z_exb6ila5bcjf"),
  source("factories-are-not-a-token-or-llm-problem-ba5fabbf", "rev_20260802T230000007Z_ngft3xfbgzib", "rev_20260802T230000016Z_oa3hzaxnhkae"),
  source("do-not-make-the-service-bus-non-deterministic-3a92442c", "rev_20260802T230000008Z_fuu6aytbkrfc", "rev_20260802T230000017Z_yplg2plpqd4a"),
] as const;

const IMAGES = [
  image("cover", "rev_20260802T230000052Z_txj4db7zordq"), image("frontier-lab-agent-intrusion-opener", "rev_20260802T230000053Z_7pcs4bj3w7g4"), image("eval-engineering-opener", "rev_20260802T230000054Z_zhx3g4zhpfor"), image("pragmatic-leverage-opener", "rev_20260802T230000055Z_bbwuyjtf2sxd"), image("from-gpt2-to-kimi3-opener", "rev_20260802T230000056Z_vxv4c6xsm4bh"), image("factory-systems-problem-opener", "rev_20260802T230000057Z_czv32wvq5vfh"), image("mcp-in-a-nutshell-opener", "rev_20260802T230000058Z_rcyepzxovpxf"), image("mcp-protocol-update-opener", "rev_20260802T230000059Z_o4tqx3zfdqx3"), image("factory-systems-problem-tail", "rev_20260802T230000060Z_3lkr2wkhk5vd"), image("mcp-in-a-nutshell-tail", "rev_20260802T230000061Z_24acmz3cblej"), image("closing-signal-gates", "rev_20260802T230000062Z_qomqcv4kmony"), image("closing-memory-rings", "rev_20260802T230000063Z_g4qgy4kwqze4"), image("closing-protocol-exchange", "rev_20260802T230000064Z_nuozv3jq6crb"),
] as const;

export async function materializeEdition4TranslationPrompt(
  repositoryRoot: string,
  workRoot: string,
  now = new Date(),
): Promise<MaterializedNativeInputRevision> {
  const ref = { kind: "prompt" as const, logicalId: "translation-es", revisionId: newRevisionId(now) };
  return materializeNativeInputRevision(repositoryRoot, workRoot, {
    ref, createdAt: now.toISOString(), parentRevisionId: null,
    files: [
      { path: "prompt.md", mediaType: "text/markdown", content: TRANSLATION_PROMPT },
      { path: "output.schema.json", mediaType: "application/json", content: `${JSON.stringify({ type: "object", required: ["english_sha256", "markdown"], properties: { english_sha256: { type: "string", pattern: "^sha256:[0-9a-f]{64}$" }, markdown: { type: "string" } }, additionalProperties: false }, null, 2)}\n` },
    ],
  });
}

export async function materializeEdition4WritePipeline(
  repositoryRoot: string,
  workRoot: string,
  translationPrompt: InputRevisionRef,
  now = new Date(),
): Promise<MaterializedNativeInputRevision> {
  const ref = { kind: "write_pipeline" as const, editionId: "004", logicalId: "edition4-write", revisionId: newRevisionId(now) };
  return materializeNativeInputRevision(repositoryRoot, workRoot, {
    ref, createdAt: now.toISOString(), parentRevisionId: null,
    files: [{ path: "production.yaml", mediaType: "application/yaml", content: stringify(production(translationPrompt), { lineWidth: 0 }) }],
  });
}

export function edition4WritePipelineDocument(translationPrompt: InputRevisionRef): Record<string, unknown> {
  return production(translationPrompt);
}

function production(translationPrompt: InputRevisionRef): Record<string, unknown> {
  if (translationPrompt.kind !== "prompt") throw new Error("Edition 004 write pipeline requires a prompt InputRevision for Spanish translation");
  const article = (articleId: string, byline: string, sourceIds: readonly string[], mode: "faithful_edit" | "faithful_synthesis") => ({
    article_id: articleId, content_mode: mode, byline, source_ids: sourceIds, source_authors: [byline],
    brief: `Create a fresh source-faithful manuscript for ${articleId} from every assigned extraction.`,
    writer_prompt: mode === "faithful_edit" ? PROMPTS.edit : PROMPTS.synthesis,
    judge_prompts: { worth: PROMPTS.worth, evidence: PROMPTS.evidence, craft: PROMPTS.craft },
    input_revisions: [WRITING_RULES, REVIEW_BENCH], parent: null, maximum_reader_pages: 7, max_iterations: 3, model_policy: terra(),
  });
  const articles = [
    article("frontier-lab-agent-intrusion", "Hugo Larcher, Adrien Carreira, raphael g, Christophe Rannou", [SOURCES[0].source_id], "faithful_synthesis"),
    article("eval-engineering", "Argona", [SOURCES[1].source_id], "faithful_synthesis"),
    article("pragmatic-leverage", "Dex Horthy", [SOURCES[2].source_id], "faithful_edit"),
    article("from-gpt2-to-kimi3", "ali", [SOURCES[3].source_id], "faithful_synthesis"),
    article("factory-systems-problem", "Geoffrey Huntley", [SOURCES[6].source_id, SOURCES[7].source_id, SOURCES[8].source_id], "faithful_edit"),
    article("mcp-in-a-nutshell", "Model Context Protocol", [SOURCES[4].source_id], "faithful_synthesis"),
    article("mcp-protocol-update", "David Soria Parra, Den Delimarsky", [SOURCES[5].source_id], "faithful_synthesis"),
  ];
  const pieces = [...articles.map((item) => item.article_id), "opening"];
  return { schema_version: 1, edition_id: "004", pipeline_id: "edition4-write", edition_spec: EDITION_SPEC, sources: SOURCES, articles,
    editorial: { editorial_id: "opening", brief: "Develop the issue's unifying idea without becoming an article-by-article summary.", writer_prompt: PROMPTS.opening, input_revisions: [WRITING_RULES, EDITORIAL_POLICY], parent: null, maximum_reader_pages: 1, model_policy: terra() },
    translations: [{ language: "es", source_language: "en", prompt: documentInput(translationPrompt), input_revisions: [WRITING_RULES], parents: Object.fromEntries(pieces.map((piece) => [piece, null])), maximum_reader_pages: 7, model_policy: terra() }],
    images: IMAGES, layout_inputs: [EDITION_SPEC], renderer_inputs: [
      { input: EDITION_SPEC, payload_path: "edition.yaml", renderer_target_path: "editions/004-the-systems-around-the-model/edition.yaml" },
      { input: EDITION_SPEC, payload_path: "art/illustrations.yaml", renderer_target_path: "editions/004-the-systems-around-the-model/art/illustrations.yaml" },
      { input: EDITION_SPEC, payload_path: "translations/es/edition.yaml", renderer_target_path: "editions/004-the-systems-around-the-model/translations/es/edition.yaml" },
      { input: WRITING_RULES, payload_path: "policy.md", renderer_target_path: "editions/004-the-systems-around-the-model/design/writing-rules.md" },
    ], render: { primary_language: "en", publication_name: "Berreta Futura", renderer: "weasyprint", configured_languages: ["en", "es"], studio_policy: "home_ready_studio_blocked" } };
}

function source(sourceId: string, capture: string, extraction: string) { return { source_id: sourceId, capture: input("source_capture", sourceId, capture), extraction: input("source_extraction", sourceId, extraction) }; }
function image(logicalId: string, revisionId: string) { return { kind: "image", edition_id: "004", logical_id: logicalId, revision_id: revisionId }; }
function input(kind: string, logicalId: string, revisionId: string, editionId?: string): any { return { kind, logical_id: logicalId, revision_id: revisionId, ...(editionId === undefined ? {} : { edition_id: editionId }) }; }
function documentInput(ref: InputRevisionRef): Record<string, string> { return { kind: ref.kind, logical_id: ref.logicalId, revision_id: ref.revisionId, ...(ref.editionId === undefined ? {} : { edition_id: ref.editionId }) }; }
function terra() { return { default: { adapter: "cooperative", model: "gpt-5.6-terra", reasoning_effort: "high" } }; }

const TRANSLATION_PROMPT = `# Spanish translation\n\nTranslate the approved English Markdown into educated castellano. Use restrained Argentine preferences only when natural; otherwise use neutral Spain-compatible Spanish. Do not use slang or generic regionalisms.\n\nPreserve the English Markdown structure exactly: headings, paragraph order, lists, links, emphasis, tables, block quotes, and fenced code blocks. A fenced code block must remain one contiguous exact block. Do not add CommonMark footnotes.\n\nReturn an object with the exact SHA-256 pin of the English input as \`english_sha256\` and the translated Markdown as \`markdown\`. Do not change, omit, or invent an English hash pin.`;
