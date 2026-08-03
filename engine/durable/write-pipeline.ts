import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { z } from "zod";
import { parse } from "yaml";

import type { ModelPolicy } from "../contracts/index.ts";
import { resolveInputRevision, type ResolvedInputRevision } from "./input-revision.ts";
import { portableComponent } from "./paths.ts";
import { parseRevisionId } from "./revision-id.ts";
import type {
  DurableGit,
  DurableRevisionRef,
  InputRevisionRef,
} from "./types.ts";

type WritePipelineRef = Extract<InputRevisionRef, { readonly kind: "write_pipeline" }>;
type ArticleParent = Extract<DurableRevisionRef, { readonly kind: "article" }>;
type EditorialParent = Extract<DurableRevisionRef, { readonly kind: "editorial" }>;
type ImageRevision = Extract<DurableRevisionRef, { readonly kind: "image" }>;

export type WritePipelineSource = {
  readonly sourceId: string;
  readonly capture: Extract<InputRevisionRef, { readonly kind: "source_capture" }>;
  readonly extraction: Extract<InputRevisionRef, { readonly kind: "source_extraction" }>;
};

export type WritePipelineArticle = {
  readonly articleId: string;
  readonly contentMode: "faithful_edit" | "faithful_synthesis" | "original_synthesis";
  readonly byline: string;
  readonly sourceIds: readonly string[];
  readonly sourceAuthors: readonly string[];
  readonly brief: string;
  readonly writerPrompt: Extract<InputRevisionRef, { readonly kind: "prompt" }>;
  readonly judgePrompts: Readonly<Record<string, Extract<InputRevisionRef, { readonly kind: "prompt" }>>>;
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly parent: ArticleParent | null;
  readonly maximumReaderPages: number;
  readonly maxIterations: number;
  readonly modelPolicy: ModelPolicy;
};

export type WritePipelineEditorial = {
  readonly editorialId: string;
  readonly brief: string;
  readonly writerPrompt: Extract<InputRevisionRef, { readonly kind: "prompt" }>;
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly parent: EditorialParent | null;
  readonly maximumReaderPages: number;
  readonly modelPolicy: ModelPolicy;
};

export type WritePipelineTranslation = {
  readonly language: string;
  readonly sourceLanguage: "en";
  readonly prompt: Extract<InputRevisionRef, { readonly kind: "prompt" }>;
  readonly inputRevisions: readonly InputRevisionRef[];
  readonly parents: Readonly<Record<string, ArticleParent | EditorialParent | null>>;
  readonly maximumReaderPages: number;
  readonly modelPolicy: ModelPolicy;
};

/** One immutable input payload staged at one exact renderer-relative target. */
export type WritePipelineRendererInput = {
  readonly input: InputRevisionRef;
  readonly payloadPath: string;
  readonly rendererTargetPath: string;
};

export type WritePipelineDocument = {
  readonly schemaVersion: 1;
  readonly editionId: string;
  readonly pipelineId: string;
  readonly editionSpec: Extract<InputRevisionRef, { readonly kind: "edition_spec" }>;
  readonly sources: readonly WritePipelineSource[];
  readonly articles: readonly WritePipelineArticle[];
  readonly editorial: WritePipelineEditorial;
  readonly translations: readonly WritePipelineTranslation[];
  readonly images: readonly ImageRevision[];
  readonly layoutInputs: readonly InputRevisionRef[];
  readonly rendererInputs: readonly WritePipelineRendererInput[];
  readonly render: {
    readonly primaryLanguage: string;
    readonly publicationName: string;
    readonly renderer: "reportlab" | "weasyprint";
    readonly configuredLanguages: readonly string[];
    readonly studioPolicy: "home_ready_studio_blocked" | "require_ready_preflight" | "not_applicable";
  };
};

export type ResolvedWritePipeline = {
  readonly revision: ResolvedInputRevision;
  readonly document: WritePipelineDocument;
  /** Every exact Git-bound input the plan directly names, deduplicated by identity. */
  readonly inputs: readonly ResolvedInputRevision[];
};

export class WritePipelineError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "WritePipelineError";
    this.code = code;
  }
}

/**
 * Loads the committed, immutable authority for a real writing run. This is
 * deliberately separate from a CompositionRevision: it names sources and
 * prompts for creating new manuscripts, rather than old selected manuscripts.
 */
export async function resolveWritePipeline(
  repositoryRoot: string,
  ref: WritePipelineRef,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<ResolvedWritePipeline> {
  const revision = await resolveInputRevision(repositoryRoot, ref, git);
  const productionPath = revision.payloadPaths["production.yaml"];
  if (productionPath === undefined || Object.keys(revision.payloadPaths).length !== 1) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "write pipeline must contain production.yaml only");
  }
  let value: unknown;
  try {
    value = parse(await readFile(productionPath, "utf8"));
  } catch (error) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "production.yaml is unreadable", { cause: error });
  }
  const document = parseWritePipelineDocument(value, ref);
  const refs = uniqueRefs([
    document.editionSpec,
    ...document.sources.flatMap((source) => [source.capture, source.extraction]),
    ...document.articles.flatMap((article) => [
      article.writerPrompt,
      ...Object.values(article.judgePrompts),
      ...article.inputRevisions,
    ]),
    document.editorial.writerPrompt,
    ...document.editorial.inputRevisions,
    ...document.translations.flatMap((translation) => [translation.prompt, ...translation.inputRevisions]),
    ...document.layoutInputs,
    ...document.rendererInputs.map((input) => input.input),
  ]);
  const inputs = await Promise.all(refs.map(async (input) =>
    await resolveInputRevision(repositoryRoot, input, git)
  ));
  return { revision, document, inputs };
}

export function parseWritePipelineDocument(value: unknown, ref: WritePipelineRef): WritePipelineDocument {
  const parsed = writePipelineSchema.safeParse(value);
  if (!parsed.success) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", parsed.error.message);
  }
  const raw = parsed.data;
  if (raw.schema_version !== 1 || raw.edition_id !== ref.editionId) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "pipeline identity does not match its InputRevision");
  }
  portableComponent(raw.pipeline_id, "write pipeline ID");
  const editionSpec = inputRef(raw.edition_spec, "edition_spec") as Extract<InputRevisionRef, { readonly kind: "edition_spec" }>;
  if (editionSpec.editionId !== ref.editionId) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "edition spec belongs to another edition");
  }
  const sources = raw.sources.map((source) => ({
    sourceId: component(source.source_id, "source ID"),
    capture: inputRef(source.capture, "source_capture") as WritePipelineSource["capture"],
    extraction: inputRef(source.extraction, "source_extraction") as WritePipelineSource["extraction"],
  }));
  unique(sources.map((source) => source.sourceId), "source IDs");
  const sourceIds = new Set(sources.map((source) => source.sourceId));
  const articles = raw.articles.map((article) => {
    const articleId = component(article.article_id, "article ID");
    const articleSources = article.source_ids.map((sourceId) => component(sourceId, "article source ID"));
    unique(articleSources, `article ${articleId} sources`);
    if (articleSources.some((sourceId) => !sourceIds.has(sourceId))) {
      throw new WritePipelineError("WRITE_PIPELINE_INVALID", `article ${articleId} names an unknown source`);
    }
    if (article.content_mode !== "original_synthesis" && article.source_authors.length === 0) {
      throw new WritePipelineError("WRITE_PIPELINE_INVALID", `faithful article ${articleId} needs source authors`);
    }
    if (article.judge_prompts.evidence === undefined) {
      throw new WritePipelineError("WRITE_PIPELINE_INVALID", `article ${articleId} must pin the evidence review prompt`);
    }
    return {
      articleId,
      contentMode: article.content_mode,
      byline: requiredText(article.byline, `article ${articleId} byline`),
      sourceIds: articleSources,
      sourceAuthors: article.source_authors.map((author) => requiredText(author, `article ${articleId} source author`)),
      brief: requiredText(article.brief, `article ${articleId} brief`),
      writerPrompt: inputRef(article.writer_prompt, "prompt") as WritePipelineArticle["writerPrompt"],
      judgePrompts: Object.fromEntries(Object.entries(article.judge_prompts).map(([role, prompt]) => [
        component(role, "judge role"), inputRef(prompt, "prompt"),
      ])) as WritePipelineArticle["judgePrompts"],
      inputRevisions: uniqueRefs(article.input_revisions.map((input) => inputRef(input))),
      parent: durableRef(article.parent, "article", ref.editionId) as ArticleParent | null,
      maximumReaderPages: positive(article.maximum_reader_pages, `article ${articleId} maximum pages`, 7),
      maxIterations: positive(article.max_iterations, `article ${articleId} max iterations`, Number.MAX_SAFE_INTEGER),
      modelPolicy: modelPolicy(article.model_policy),
    };
  });
  unique(articles.map((article) => article.articleId), "article IDs");
  const editorial = {
    editorialId: component(raw.editorial.editorial_id, "editorial ID"),
    brief: requiredText(raw.editorial.brief, "editorial brief"),
    writerPrompt: inputRef(raw.editorial.writer_prompt, "prompt") as WritePipelineEditorial["writerPrompt"],
    inputRevisions: uniqueRefs(raw.editorial.input_revisions.map((input) => inputRef(input))),
    parent: durableRef(raw.editorial.parent, "editorial", ref.editionId) as EditorialParent | null,
    maximumReaderPages: positive(raw.editorial.maximum_reader_pages, "editorial maximum pages", 1),
    modelPolicy: modelPolicy(raw.editorial.model_policy),
  } satisfies WritePipelineEditorial;
  const knownPieces = new Set([...articles.map((article) => article.articleId), editorial.editorialId]);
  const translations = raw.translations.map((translation) => {
    const parents = Object.fromEntries(Object.entries(translation.parents).map(([pieceId, parent]) => {
      if (!knownPieces.has(pieceId)) {
        throw new WritePipelineError("WRITE_PIPELINE_INVALID", `translation parent names unknown piece ${pieceId}`);
      }
      const kind = pieceId === editorial.editorialId ? "editorial" : "article";
      return [pieceId, durableRef(parent, kind, ref.editionId)];
    }));
    if (Object.keys(parents).length !== knownPieces.size || Object.keys(parents).some((piece) => !knownPieces.has(piece))) {
      throw new WritePipelineError("WRITE_PIPELINE_INVALID", "translation parents must name every English piece exactly once");
    }
    return {
      language: component(translation.language, "translation language"),
      sourceLanguage: translation.source_language,
      prompt: inputRef(translation.prompt, "prompt") as WritePipelineTranslation["prompt"],
      inputRevisions: uniqueRefs(translation.input_revisions.map((input) => inputRef(input))),
      parents: parents as WritePipelineTranslation["parents"],
      maximumReaderPages: positive(translation.maximum_reader_pages, "translation maximum pages", 7),
      modelPolicy: modelPolicy(translation.model_policy),
    } satisfies WritePipelineTranslation;
  });
  unique(translations.map((translation) => translation.language), "translation languages");
  const images = raw.images.map((image) => durableRef(image, "image", ref.editionId) as ImageRevision);
  unique(images.map((image) => image.logicalId), "image revisions");
  if (images.length !== 13) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "Edition 4 write pipeline must pin exactly 13 selected images");
  }
  const layoutInputs = uniqueRefs(raw.layout_inputs.map((input) => inputRef(input)));
  const rendererInputs = raw.renderer_inputs.map((input) => ({
    input: inputRef(input.input),
    payloadPath: payloadPath(input.payload_path),
    rendererTargetPath: rendererTargetPath(input.renderer_target_path),
  }));
  unique(
    rendererInputs.map((input) => `${input.input.kind}:${input.input.editionId ?? ""}:${input.input.logicalId}:${input.input.revisionId}:${input.payloadPath}`),
    "renderer input payloads",
  );
  unique(rendererInputs.map((input) => input.rendererTargetPath), "renderer target paths");
  const configuredLanguages = raw.render.configured_languages.map((language) => component(language, "render language"));
  unique(configuredLanguages, "render languages");
  if (!configuredLanguages.includes("en") || !translations.every((translation) => configuredLanguages.includes(translation.language))) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "render languages must include English and every translation");
  }
  return {
    schemaVersion: 1,
    editionId: ref.editionId,
    pipelineId: raw.pipeline_id,
    editionSpec,
    sources,
    articles,
    editorial,
    translations,
    images,
    layoutInputs,
    rendererInputs,
    render: {
      primaryLanguage: component(raw.render.primary_language, "primary language"),
      publicationName: requiredText(raw.render.publication_name, "publication name"),
      renderer: raw.render.renderer,
      configuredLanguages,
      studioPolicy: raw.render.studio_policy,
    },
  };
}

const inputRefSchema = z.object({
  kind: z.string().min(1),
  logical_id: z.string().min(1),
  revision_id: z.string().min(1),
  edition_id: z.string().min(1).optional(),
}).strict();

const rendererInputSchema = z.object({
  input: inputRefSchema,
  payload_path: z.string().min(1),
  renderer_target_path: z.string().min(1),
}).strict();

const durableRefSchema = z.object({
  kind: z.string().min(1),
  edition_id: z.string().min(1),
  logical_id: z.string().min(1),
  language: z.string().min(1).optional(),
  revision_id: z.string().min(1),
}).strict().nullable();

const modelChoiceSchema = z.object({
  adapter: z.string().min(1),
  model: z.string().min(1),
  reasoning_effort: z.string().min(1).optional(),
  settings: z.record(z.string(), z.json()).optional(),
}).strict();
const modelPolicySchema = z.object({
  default: modelChoiceSchema,
  roles: z.record(z.string().min(1), modelChoiceSchema).optional(),
}).strict();

const writePipelineSchema = z.object({
  schema_version: z.literal(1),
  edition_id: z.string().min(1),
  pipeline_id: z.string().min(1),
  edition_spec: inputRefSchema,
  sources: z.array(z.object({
    source_id: z.string().min(1), capture: inputRefSchema, extraction: inputRefSchema,
  }).strict()).min(1),
  articles: z.array(z.object({
    article_id: z.string().min(1),
    content_mode: z.enum(["faithful_edit", "faithful_synthesis", "original_synthesis"]),
    byline: z.string().min(1),
    source_ids: z.array(z.string().min(1)).min(1),
    source_authors: z.array(z.string().min(1)),
    brief: z.string().min(1),
    writer_prompt: inputRefSchema,
    judge_prompts: z.record(z.string().min(1), inputRefSchema),
    input_revisions: z.array(inputRefSchema).min(1),
    parent: durableRefSchema,
    maximum_reader_pages: z.number().int().positive(),
    max_iterations: z.number().int().positive(),
    model_policy: modelPolicySchema,
  }).strict()).length(7),
  editorial: z.object({
    editorial_id: z.string().min(1), brief: z.string().min(1), writer_prompt: inputRefSchema,
    input_revisions: z.array(inputRefSchema).min(1), parent: durableRefSchema,
    maximum_reader_pages: z.number().int().positive(), model_policy: modelPolicySchema,
  }).strict(),
  translations: z.array(z.object({
    language: z.string().min(1), source_language: z.literal("en"), prompt: inputRefSchema,
    input_revisions: z.array(inputRefSchema).min(1), parents: z.record(z.string().min(1), durableRefSchema),
    maximum_reader_pages: z.number().int().positive(), model_policy: modelPolicySchema,
  }).strict()).min(1),
  images: z.array(durableRefSchema).length(13),
  layout_inputs: z.array(inputRefSchema).min(1),
  renderer_inputs: z.array(rendererInputSchema).min(1),
  render: z.object({
    primary_language: z.string().min(1), publication_name: z.string().min(1),
    renderer: z.enum(["reportlab", "weasyprint"]), configured_languages: z.array(z.string().min(1)).min(1),
    studio_policy: z.enum(["home_ready_studio_blocked", "require_ready_preflight", "not_applicable"]),
  }).strict(),
}).strict();

function inputRef(value: z.infer<typeof inputRefSchema>, expectedKind?: InputRevisionRef["kind"]): InputRevisionRef {
  if (expectedKind !== undefined && value.kind !== expectedKind) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", `expected ${expectedKind} input revision, got ${value.kind}`);
  }
  const editionBound = value.kind === "edition_spec" || value.kind === "run_bootstrap" || value.kind === "write_pipeline";
  if (editionBound !== (value.edition_id !== undefined)) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", `input ${value.logical_id} has an invalid edition binding`);
  }
  component(value.logical_id, "input logical ID");
  parseRevisionId(value.revision_id);
  if (editionBound) component(value.edition_id!, "input edition ID");
  return {
    kind: value.kind,
    logicalId: value.logical_id,
    revisionId: value.revision_id,
    ...(editionBound ? { editionId: value.edition_id! } : {}),
  } as InputRevisionRef;
}

function durableRef(
  value: z.infer<typeof durableRefSchema>,
  expectedKind: "article" | "editorial" | "image",
  editionId: string,
): DurableRevisionRef | null {
  if (value === null) return null;
  if (value.kind !== expectedKind || value.edition_id !== editionId) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", `invalid ${expectedKind} durable parent`);
  }
  component(value.logical_id, "durable logical ID");
  parseRevisionId(value.revision_id);
  if (expectedKind === "image") {
    if (value.language !== undefined) throw new WritePipelineError("WRITE_PIPELINE_INVALID", "image revisions cannot carry a language");
    return {
      kind: "image",
      editionId,
      logicalId: value.logical_id,
      revisionId: value.revision_id as ImageRevision["revisionId"],
    };
  }
  if (value.language === undefined) throw new WritePipelineError("WRITE_PIPELINE_INVALID", `${expectedKind} parent needs a language`);
  component(value.language, "durable language");
  return { kind: expectedKind, editionId, logicalId: value.logical_id, language: value.language, revisionId: value.revision_id } as DurableRevisionRef;
}

function modelPolicy(value: z.infer<typeof modelPolicySchema>): ModelPolicy {
  const convert = (choice: z.infer<typeof modelChoiceSchema>) => ({
    adapter: choice.adapter,
    model: choice.model,
    ...(choice.reasoning_effort === undefined ? {} : { reasoningEffort: choice.reasoning_effort }),
    ...(choice.settings === undefined ? {} : { settings: choice.settings }),
  });
  return {
    default: convert(value.default),
    ...(value.roles === undefined ? {} : {
      roles: Object.fromEntries(Object.entries(value.roles).map(([role, choice]) => [role, convert(choice)])),
    }),
  };
}

function positive(value: number, label: string, maximum: number): number {
  if (!Number.isSafeInteger(value) || value < 1 || value > maximum) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", `${label} is out of range`);
  }
  return value;
}

function component(value: string, label: string): string {
  return portableComponent(value, label);
}

function requiredText(value: string, label: string): string {
  if (!value.trim()) throw new WritePipelineError("WRITE_PIPELINE_INVALID", `${label} is empty`);
  return value;
}

function payloadPath(value: string): string {
  if (value.startsWith("/") || value.split("/").some((part) => part === "" || part === "." || part === "..")) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "renderer payload path is unsafe");
  }
  return value;
}

function rendererTargetPath(value: string): string {
  if (value.startsWith("/") || value.includes("\\") || value.split("/").some((part) => part === "" || part === "." || part === "..")) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", "renderer target path is unsafe");
  }
  return value;
}

function unique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) {
    throw new WritePipelineError("WRITE_PIPELINE_INVALID", `${label} must be unique`);
  }
}

function inputKey(ref: InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

function uniqueRefs(refs: readonly InputRevisionRef[]): readonly InputRevisionRef[] {
  const seen = new Set<string>();
  return refs.filter((ref) => {
    const key = inputKey(ref);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
