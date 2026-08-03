import { parse } from "yaml";

import type { DurableRevisionRef, InputRevisionRef } from "./types.ts";
import { portableComponent } from "./paths.ts";
import { parseRevisionId } from "./revision-id.ts";

export type ArticleRevisionRef = Extract<DurableRevisionRef, { readonly kind: "article" }>;
export type EditorialRevisionRef = Extract<DurableRevisionRef, { readonly kind: "editorial" }>;
export type ImageRevisionRef = Extract<DurableRevisionRef, { readonly kind: "image" }>;

export type CompositionManuscriptPin<T extends ArticleRevisionRef | EditorialRevisionRef> = {
  readonly language: string;
  readonly revision: T;
};

export type CompositionImagePin = {
  readonly slot_id: string;
  readonly revision: ImageRevisionRef;
};

export type CompositionEditorialPin = {
  readonly editorial_id: string;
  readonly manuscripts: readonly CompositionManuscriptPin<EditorialRevisionRef>[];
};

export type CompositionArticlePin = {
  readonly article_id: string;
  readonly manuscripts: readonly CompositionManuscriptPin<ArticleRevisionRef>[];
  readonly images: readonly CompositionImagePin[];
};

export type CompositionLayoutInputPin = {
  readonly slot_id: string;
  readonly revision: InputRevisionRef;
};

export type CompositionDocument = {
  readonly schema_version: 1;
  readonly edition_id: string;
  readonly composition_id: string;
  readonly editorials: readonly CompositionEditorialPin[];
  readonly articles: readonly CompositionArticlePin[];
  readonly images: readonly CompositionImagePin[];
  readonly layout_inputs: readonly CompositionLayoutInputPin[];
};

export class CompositionSchemaError extends Error {
  readonly code = "COMPOSITION_INVALID";

  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "CompositionSchemaError";
  }
}

export function parseCompositionDocument(
  bytes: Uint8Array,
  expected?: { readonly editionId: string; readonly compositionId: string },
): CompositionDocument {
  let decoded: unknown;
  try {
    decoded = parse(Buffer.from(bytes).toString("utf8"));
  } catch (error) {
    throw invalid("composition payload is not valid YAML or JSON", error);
  }
  const root = objectWithKeys(decoded, [
    "schema_version",
    "edition_id",
    "composition_id",
    "editorials",
    "articles",
    "images",
    "layout_inputs",
  ], "composition");
  if (
    root.schema_version !== 1 ||
    typeof root.edition_id !== "string" ||
    typeof root.composition_id !== "string" ||
    !Array.isArray(root.editorials) || root.editorials.length === 0 ||
    !Array.isArray(root.articles) || root.articles.length === 0 ||
    !Array.isArray(root.images) ||
    !Array.isArray(root.layout_inputs) || root.layout_inputs.length === 0
  ) {
    throw invalid("composition is missing required identity or pin arrays");
  }
  portableComponent(root.edition_id, "composition edition ID");
  portableComponent(root.composition_id, "composition ID");
  if (
    expected !== undefined &&
    (root.edition_id !== expected.editionId || root.composition_id !== expected.compositionId)
  ) {
    throw invalid("composition payload identity disagrees with its DurableRevision");
  }

  const editorials = root.editorials.map((value, index) => editorialPin(value, index, root.edition_id as string));
  const articles = root.articles.map((value, index) => articlePin(value, index, root.edition_id as string));
  const images = root.images.map((value, index) => imagePin(value, `composition images[${index}]`, root.edition_id as string));
  const layoutInputs = root.layout_inputs.map((value, index) => layoutPin(value, index));
  unique(editorials.map((value) => value.editorial_id), "editorial IDs");
  unique(articles.map((value) => value.article_id), "article IDs");
  unique(images.map((value) => value.slot_id), "composition image slots");
  unique(layoutInputs.map((value) => value.slot_id), "layout input slots");

  return {
    schema_version: 1,
    edition_id: root.edition_id,
    composition_id: root.composition_id,
    editorials,
    articles,
    images,
    layout_inputs: layoutInputs,
  };
}

export function compositionDurableRefs(
  composition: CompositionDocument,
): readonly DurableRevisionRef[] {
  return [
    ...composition.editorials.flatMap((editorial) => editorial.manuscripts.map((pin) => pin.revision)),
    ...composition.articles.flatMap((article) => [
      ...article.manuscripts.map((pin) => pin.revision),
      ...article.images.map((pin) => pin.revision),
    ]),
    ...composition.images.map((pin) => pin.revision),
  ];
}

function editorialPin(value: unknown, index: number, editionId: string): CompositionEditorialPin {
  const item = objectWithKeys(value, ["editorial_id", "manuscripts"], `editorials[${index}]`);
  if (typeof item.editorial_id !== "string" || !Array.isArray(item.manuscripts) || item.manuscripts.length === 0) {
    throw invalid(`editorials[${index}] is invalid`);
  }
  portableComponent(item.editorial_id, "editorial ID");
  const manuscripts = item.manuscripts.map((pin, pinIndex) => manuscriptPin(
    pin,
    "editorial",
    `editorials[${index}].manuscripts[${pinIndex}]`,
    editionId,
  ));
  unique(manuscripts.map((pin) => pin.language), `editorial ${item.editorial_id} languages`);
  return { editorial_id: item.editorial_id, manuscripts };
}

function articlePin(value: unknown, index: number, editionId: string): CompositionArticlePin {
  const item = objectWithKeys(value, ["article_id", "manuscripts", "images"], `articles[${index}]`);
  if (
    typeof item.article_id !== "string" ||
    !Array.isArray(item.manuscripts) || item.manuscripts.length === 0 ||
    !Array.isArray(item.images)
  ) {
    throw invalid(`articles[${index}] is invalid`);
  }
  portableComponent(item.article_id, "article ID");
  const manuscripts = item.manuscripts.map((pin, pinIndex) => manuscriptPin(
    pin,
    "article",
    `articles[${index}].manuscripts[${pinIndex}]`,
    editionId,
  ));
  const images = item.images.map((pin, pinIndex) => imagePin(
    pin,
    `articles[${index}].images[${pinIndex}]`,
    editionId,
  ));
  unique(manuscripts.map((pin) => pin.language), `article ${item.article_id} languages`);
  unique(images.map((pin) => pin.slot_id), `article ${item.article_id} image slots`);
  return { article_id: item.article_id, manuscripts, images };
}

function manuscriptPin<T extends "article" | "editorial">(
  value: unknown,
  kind: T,
  label: string,
  editionId: string,
): CompositionManuscriptPin<Extract<DurableRevisionRef, { readonly kind: T }>> {
  const pin = objectWithKeys(value, ["language", "revision"], label);
  if (typeof pin.language !== "string") throw invalid(`${label} has no language`);
  portableComponent(pin.language, "composition language");
  const revision = durableRef(pin.revision, kind, label, editionId) as
    Extract<DurableRevisionRef, { readonly kind: T }>;
  if ((revision as ArticleRevisionRef | EditorialRevisionRef).language !== pin.language) {
    throw invalid(`${label} language disagrees with its DurableRevision`);
  }
  return { language: pin.language, revision } as CompositionManuscriptPin<Extract<DurableRevisionRef, { readonly kind: T }>>;
}

function imagePin(value: unknown, label: string, editionId: string): CompositionImagePin {
  const pin = objectWithKeys(value, ["slot_id", "revision"], label);
  if (typeof pin.slot_id !== "string") throw invalid(`${label} has no slot_id`);
  portableComponent(pin.slot_id, "composition image slot");
  return {
    slot_id: pin.slot_id,
    revision: durableRef(pin.revision, "image", label, editionId),
  };
}

function layoutPin(value: unknown, index: number): CompositionLayoutInputPin {
  const label = `layout_inputs[${index}]`;
  const pin = objectWithKeys(value, ["slot_id", "revision"], label);
  if (typeof pin.slot_id !== "string") throw invalid(`${label} has no slot_id`);
  portableComponent(pin.slot_id, "composition layout slot");
  return { slot_id: pin.slot_id, revision: inputRef(pin.revision, label) };
}

function durableRef<T extends "article" | "editorial" | "image">(
  value: unknown,
  kind: T,
  label: string,
  editionId: string,
): Extract<DurableRevisionRef, { readonly kind: T }> {
  const keys = kind === "image"
    ? ["kind", "editionId", "logicalId", "revisionId"]
    : ["kind", "editionId", "logicalId", "language", "revisionId"];
  const ref = objectWithKeys(value, keys, `${label}.revision`);
  if (
    ref.kind !== kind ||
    ref.editionId !== editionId ||
    typeof ref.logicalId !== "string" ||
    typeof ref.revisionId !== "string" ||
    (kind !== "image" && typeof ref.language !== "string")
  ) {
    throw invalid(`${label} has an invalid ${kind} DurableRevision reference`);
  }
  portableComponent(ref.logicalId, "durable logical ID");
  parseRevisionId(ref.revisionId);
  if (kind !== "image") portableComponent(ref.language as string, "durable language");
  return ref as unknown as Extract<DurableRevisionRef, { readonly kind: T }>;
}

function inputRef(value: unknown, label: string): InputRevisionRef {
  if (!mapping(value) || typeof value.kind !== "string") {
    throw invalid(`${label} has an invalid InputRevision reference`);
  }
  const editionSpec = value.kind === "edition_spec";
  const ref = objectWithKeys(
    value,
    editionSpec ? ["kind", "logicalId", "revisionId", "editionId"] : ["kind", "logicalId", "revisionId"],
    `${label}.revision`,
  );
  if (
    !new Set(["edition_spec", "prompt", "source_capture", "source_extraction"]).has(ref.kind as string) ||
    typeof ref.logicalId !== "string" ||
    typeof ref.revisionId !== "string" ||
    (editionSpec && typeof ref.editionId !== "string")
  ) {
    throw invalid(`${label} has an invalid InputRevision reference`);
  }
  portableComponent(ref.logicalId, "input logical ID");
  parseRevisionId(ref.revisionId);
  if (editionSpec) portableComponent(ref.editionId as string, "input edition ID");
  return ref as unknown as InputRevisionRef;
}

function objectWithKeys(
  value: unknown,
  keys: readonly string[],
  label: string,
): Record<string, unknown> {
  if (!mapping(value)) throw invalid(`${label} must be a mapping`);
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw invalid(`${label} has unexpected or missing fields`);
  }
  return value;
}

function mapping(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function unique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) throw invalid(`${label} must be unique`);
}

function invalid(message: string, cause?: unknown): CompositionSchemaError {
  return new CompositionSchemaError(message, cause === undefined ? undefined : { cause });
}
